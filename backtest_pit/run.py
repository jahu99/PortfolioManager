"""Command line: point-in-time factor evaluation + top-N portfolio simulation.

Examples
--------
Use the repo's existing price cache (about 2 years, good for a smoke test)::

    python -m backtest_pit.run --prices-dir data/cache/prices --format pickle

Use a longer history downloaded with ``python -m backtest_pit.download``::

    python -m backtest_pit.run --prices-dir data/pit_prices --format csv \\
        --horizons 21 63 126 252 --benchmark SPY
"""
from __future__ import annotations

import argparse
import os

import numpy as np
import pandas as pd

from .data import load_csv_dir, load_pickle_dir
from .evaluate import eligibility, evaluate_factor, month_end_positions
from .exits import ExitModel, exit_event_summary
from .factors import FACTORS, compute_factors


def _run_vwrp_vwap_ema(panel, ticker, cost_bps, out_dir):
    """Research-only rolling daily VWAP/EMA crossover with next-close execution."""
    import numpy as np
    import pandas as pd

    for field in ("close", "volume", "adj_close"):
        if ticker not in getattr(panel, field).columns:
            raise ValueError(f"{ticker!r} missing from panel.{field}")

    data = pd.DataFrame({
        "close": panel.close[ticker],
        "volume": panel.volume[ticker],
        "adj_close": panel.adj_close[ticker],
    }).dropna()

    # Exclude today's potentially incomplete bar.
    cutoff = pd.Timestamp.today().normalize() - pd.Timedelta(days=1)
    data = data.loc[data.index <= cutoff]
    data = data.loc[(data["close"] > 0) & (data["volume"] > 0)]

    if len(data) < 220:
        raise ValueError(
            f"Only {len(data)} usable daily observations for {ticker}; "
            "need at least 220."
        )

    # Daily-bar rolling VWAP proxy, not intraday session VWAP.
    rolling_value = (data["close"] * data["volume"]).rolling(
        20, min_periods=20
    ).sum()
    rolling_volume = data["volume"].rolling(20, min_periods=20).sum()
    data["rolling_vwap20"] = rolling_value / rolling_volume
    data["ema20"] = data["close"].ewm(
        span=20, adjust=False, min_periods=20
    ).mean()

    data = data.dropna(subset=["rolling_vwap20", "ema20"]).copy()
    if len(data) < 2:
        raise ValueError("Insufficient overlapping VWAP/EMA observations.")

    above = data["rolling_vwap20"] > data["ema20"]
    previously_above = above.shift(1, fill_value=False)
    previously_below_or_equal = (
        data["rolling_vwap20"].shift(1) <= data["ema20"].shift(1)
    )
    previously_above_or_equal = (
        data["rolling_vwap20"].shift(1) >= data["ema20"].shift(1)
    )

    cross_up = above & previously_below_or_equal
    cross_down = (~above) & previously_above_or_equal

    # Maintain state between crossovers: buy on cross-up, exit on cross-down.
    state = []
    invested = False
    for up, down in zip(cross_up, cross_down):
        if up:
            invested = True
        elif down:
            invested = False
        state.append(invested)

    data["buy_signal"] = cross_up.astype(int)
    data["sell_signal"] = cross_down.astype(int)
    data["signal_position"] = state

    # Signal at close t is executed at close t+1.
    data["asset_return"] = data["adj_close"].pct_change().fillna(0.0)
    data["strategy_position"] = (
        data["signal_position"].shift(1).fillna(False).astype(int)
    )
    data["buy_hold_position"] = 1

    rate = float(cost_bps) / 10000.0
    rows = []
    equity_frames = {}

    for name, position_col in (
        ("vwap20_cross_ema20", "strategy_position"),
        ("buy_hold", "buy_hold_position"),
    ):
        position = data[position_col].astype(int)
        turnover = position.diff().abs()
        if len(turnover):
            turnover.iloc[0] = position.iloc[0]

        # A close-to-close return is earned by the position held at the
        # previous close; costs are charged on the current close's trade.
        held_over_interval = position.shift(1).fillna(0).astype(float)
        costs = turnover.fillna(0.0) * rate
        net_return = held_over_interval * data["asset_return"] - costs
        equity = (1.0 + net_return).cumprod()
        drawdown = equity / equity.cummax() - 1.0

        years = (data.index[-1] - data.index[0]).days / 365.25
        final_equity = float(equity.iloc[-1])
        cagr = (
            final_equity ** (1.0 / years) - 1.0
            if years > 0 and final_equity > 0 else float("nan")
        )

        rows.append({
            "strategy": name,
            "start": str(data.index[0].date()),
            "end": str(data.index[-1].date()),
            "observations": len(data),
            "total_return": final_equity - 1.0,
            "annualised_return": cagr,
            "annualised_volatility": float(net_return.std(ddof=1) * np.sqrt(252)),
            "max_drawdown": float(drawdown.min()),
            "time_invested_pct": float(position.mean() * 100.0),
            "position_changes": int(turnover.sum()),
            "estimated_cost_pct_of_initial_capital": float(costs.sum() * 100.0),
        })
        equity_frames[name] = pd.DataFrame({
            "close": data["close"],
            "adj_close": data["adj_close"],
            "volume": data["volume"],
            "rolling_vwap20": data["rolling_vwap20"],
            "ema20": data["ema20"],
            "buy_signal": data["buy_signal"],
            "sell_signal": data["sell_signal"],
            "position_at_close": position,
            "turnover": turnover,
            "asset_return": data["asset_return"],
            "net_return": net_return,
            "equity": equity,
        })

    os.makedirs(out_dir, exist_ok=True)
    pd.DataFrame(rows).to_csv(
        os.path.join(out_dir, f"{ticker}_vwap20_ema20_summary.csv"),
        index=False,
    )
    for name, frame in equity_frames.items():
        frame.to_csv(
            os.path.join(out_dir, f"{ticker}_vwap20_ema20_{name}.csv")
        )

    print(f"Research-only daily rolling VWAP-20 / EMA-20: {ticker}")
    print("Signal: VWAP crosses above EMA; exit when VWAP crosses below EMA.")
    print("Execution: next session close; returns use adjusted close.")
    print(f"Cost: {cost_bps:.1f} bps per one-way position change.")
    print(pd.DataFrame(rows).to_string(
        index=False, float_format=lambda x: f"{x:.4f}"
    ))
    print(f"Wrote results to {out_dir}")


def _run_vwrp_ema_regime(panel, ticker, cost_bps, out_dir):
    """Research-only EMA regime test; signals execute at the next close."""
    import numpy as np
    import pandas as pd

    if ticker not in panel.adj_close.columns:
        raise ValueError(
            f"{ticker!r} is not in the loaded price panel. "
            "Load a price folder containing that ticker."
        )

    price = panel.adj_close[ticker].dropna().astype(float)
    price = price.loc[:pd.Timestamp.today().normalize() - pd.Timedelta(days=1)]

    if len(price) < 220:
        raise ValueError(
            f"Only {len(price)} usable observations for {ticker}; "
            "at least 220 are required for the EMA-200 test."
        )

    ema50 = price.ewm(span=50, adjust=False, min_periods=50).mean()
    ema200 = price.ewm(span=200, adjust=False, min_periods=200).mean()

    signal = pd.DataFrame(index=price.index)
    signal["buy_hold"] = True
    signal["ema50"] = price > ema50
    signal["ema200"] = price > ema200
    signal["ema50_and_ema200"] = (price > ema50) & (price > ema200)

    # Signal at close t; position changes at close t+1.
    # Start comparison only after both EMAs are available.
    valid = ema200.notna()
    price = price.loc[valid]
    signal = signal.loc[valid]
    ema50 = ema50.loc[valid]
    ema200 = ema200.loc[valid]

    # A close-to-close return is earned only if invested at the prior close.
    asset_return = price.pct_change()
    strategies = {}
    summary = []

    for name in signal.columns:
        position = signal[name].shift(1).fillna(False).astype(bool)
        position.iloc[0] = True if name == "buy_hold" else False

        turnover = position.astype(int).diff().abs()
        if len(turnover):
            turnover.iloc[0] = int(position.iloc[0])

        cost = turnover * (float(cost_bps) / 10000.0)
        net_return = (position.astype(float) * asset_return.fillna(0.0)) - cost
        net_return.iloc[0] = 0.0

        equity = (1.0 + net_return).cumprod()
        elapsed_years = (price.index[-1] - price.index[0]).days / 365.25
        total_return = float(equity.iloc[-1] - 1.0)
        annual_return = (
            float(equity.iloc[-1] ** (1.0 / elapsed_years) - 1.0)
            if elapsed_years > 0 and equity.iloc[-1] > 0 else float("nan")
        )
        annual_volatility = float(net_return.std(ddof=1) * np.sqrt(252))
        drawdown = equity / equity.cummax() - 1.0

        summary.append({
            "strategy": name,
            "start": str(price.index[0].date()),
            "end": str(price.index[-1].date()),
            "observations": len(price),
            "total_return": total_return,
            "annualised_return": annual_return,
            "annualised_volatility": annual_volatility,
            "max_drawdown": float(drawdown.min()),
            "time_invested_pct": float(position.mean() * 100.0),
            "position_changes": int(turnover.sum()),
            "estimated_cost_pct_of_initial_capital": float(cost.sum() * 100.0),
        })
        strategies[name] = pd.DataFrame({
            "adjusted_close": price,
            "ema50": ema50,
            "ema200": ema200,
            "position": position.astype(int),
            "asset_return": asset_return,
            "turnover": turnover,
            "estimated_cost": cost,
            "net_return": net_return,
            "equity": equity,
        })

    os.makedirs(out_dir, exist_ok=True)
    pd.DataFrame(summary).to_csv(
        os.path.join(out_dir, f"{ticker}_ema_regime_summary.csv"), index=False
    )
    for name, frame in strategies.items():
        frame.to_csv(os.path.join(out_dir, f"{ticker}_ema_regime_{name}.csv"))

    print(f"EMA regime research: {ticker}")
    print(f"Signal/return series: {price.index[0].date()} to {price.index[-1].date()}")
    print(f"Transaction cost assumption: {cost_bps:.1f} bps per position change")
    print(pd.DataFrame(summary).to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    print(f"Wrote EMA regime results to {out_dir}")

from .portfolio import simulate_top_n, summarize_portfolio


def _pct(x, d=2):
    return "n/a" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{100 * x:.{d}f}%"


def _num(x, d=3):
    return "n/a" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.{d}f}"


def _md_table(headers, rows) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def _cell(mean, lo, hi, reliable, fmt) -> str:
    """Mean with an interval, or a refusal to show one when there are too few independent periods."""
    if not reliable:
        return f"{fmt(mean)} [too few periods]"
    return f"{fmt(mean)} [{fmt(lo)}, {fmt(hi)}]"


def _ex_cell(s, prefix, reliable) -> str:
    return _cell(s[f"{prefix}_mean"], s[f"{prefix}_adj_lo"], s[f"{prefix}_adj_hi"], reliable, _pct)


def build_report(meta: dict, summary: pd.DataFrame, ports: dict, n_tests: int, min_indep: int = 12,
                 halves: dict | None = None, exit_info: dict | None = None) -> str:
    L = []
    bench = meta.get("benchmark") or "benchmark"
    L.append("# Point-in-time backtest report\n")
    L.append(f"- Universe: **{meta['n_tickers']}** tickers loaded, **{meta['n_dates']}** trading days "
             f"({meta['start']} to {meta['end']}); {meta['n_signal_dates']} month-end signal dates.")
    L.append(f"- Execution: signal at close of day t, traded at close of t+{meta['lag']}; returns are total return "
             f"(dividend-adjusted). Eligibility: price >= {meta['min_price']}, 20-day median dollar volume >= "
             f"{meta['min_dollar_volume']:,.0f}.")
    L.append(f"- Portfolio: top {meta['top_n']} (exit rank {meta['exit_rank']}), monthly, equal weight, "
             f"{meta['cost_bps']} bps per unit traded.")
    L.append(f"- Tests run: **{n_tests}** (factor x horizon). Two intervals are shown: plain 95%, and a "
             f"Bonferroni-adjusted one (alpha = 0.05/{n_tests}). Trust the adjusted one.\n")

    L.append("## Read this first\n")
    L.append("- **Survivorship bias.** The universe is whatever tickers were in the price folder, i.e. names that "
             "exist today. Companies that failed or were delisted are missing, which flatters every long-only test. "
             "A credible test needs historical index/exchange membership including dead names.")
    L.append("- **Quality and growth scores are not tested.** They come from today's fundamentals snapshot, so "
             "scoring the past with them leaks the future. Only price/volume-based factors appear here.")
    L.append("- **Short samples are exploratory.** With few monthly dates the intervals are wide; overlapping "
             "forward windows make horizons >1 month even less independent (see 'indep').")
    L.append("- **The random portfolio is a diagnostic baseline, not a pass/fail test.** "
             "Its returns include trading costs, while the equal-weight universe benchmark is gross. "
            "Underperformance versus that benchmark does not by itself indicate a broken harness.\n")
    L.append("## Factor evaluation (rank IC and quintile returns)\n")
    L.append("IC = cross-sectional rank correlation between the factor and subsequent return, averaged over "
             "month-end dates. `top - universe` = mean return of the top quintile minus the equal-weight universe "
             "over the horizon (winsorised 1/99%).\n")
    rows = []
    for _, r in summary.iterrows():
        ok = bool(r["indep_periods"] >= min_indep)
        rows.append([
            r["factor"], int(r["horizon_days"]), int(r["n_dates"]), _num(r["indep_periods"], 1),
            int(round(r["mean_names"])) if not np.isnan(r["mean_names"]) else "n/a",
            _num(r["mean_tied_at_top"], 0),
            _cell(r["mean_ic"], r["ic_adj_lo"], r["ic_adj_hi"], ok, _num),
            _pct(r["ic_hit_rate"], 0),
            _cell(r["top_vs_universe"], r["tvu_adj_lo"], r["tvu_adj_hi"], ok, _pct),
            _pct(r["top_vs_bottom"]),
        ])
    L.append(_md_table(["factor", "horizon (d)", "dates", "indep", "names", "tied@top", "mean IC [adj 95% CI]",
                        "IC>0", "top-universe [adj 95% CI]", "top-bottom"], rows))
    L.append(f"\n`indep` = approximate number of non-overlapping periods. Intervals are withheld below {min_indep}: a "
             "bootstrap over so few independent observations is not trustworthy, so those rows are exploratory "
             "only. `tied@top` = names sharing the single highest score on a typical date; for a coarse score "
             "'top N' is then partly a coin toss among ties.\n")

    L.append("## Top-N portfolio (monthly, after costs)\n")
    prow, erow = [], []
    has_bm = any("excess_bm_mean" in s_ for s_ in ports.values())
    for name, s in ports.items():
        if s.get("n_periods", 0) == 0:
            prow.append([name, 0] + ["n/a"] * 7)
            continue
        rel = s["n_periods"] >= min_indep
        prow.append([name, s["n_periods"], _pct(s["total_net"]), _pct(s["total_universe"]),
                     _pct(s.get("total_benchmark_ticker", float("nan"))),
                     _pct(s["months_beating_universe"], 0), _pct(s["avg_turnover"], 0), _pct(s["total_cost"]),
                     _pct(s["max_drawdown"])])
        er = [name, _ex_cell(s, "excess", rel)]
        if has_bm:
            er.append(_ex_cell(s, "excess_bm", rel) if "excess_bm_mean" in s else "n/a")
        er.append(_num(s["avg_tied_at_top"], 0))
        erow.append(er)
    L.append(_md_table(["factor", "months", "net total", "universe total", f"{bench} total", "months beating universe",
                        "avg turnover", "total costs", "max drawdown"], prow))
    L.append("\n**Mean monthly excess return** (net of costs; moving-block bootstrap, 3-month blocks; "
             f"Bonferroni-adjusted 95% interval across {len(ports)} portfolio strategies):\n")
    L.append(_md_table(["factor", "vs equal-weight universe [adj 95% CI]"]
                       + ([f"vs {bench} [adj 95% CI]"] if has_bm else []) + ["tied@top"], erow))
    L.append("\n'universe' is the raw equal-weight average of every eligible name, i.e. what picking at random "
             "would earn before costs; it is the like-for-like baseline. Do not annualise automatically: full-sample results span the reported dates, but "
             "annualised returns can obscure regime dependence and uncertainty, especially in shorter subperiods.")
    gaps = [(n_, s_["universe_minus_bm_mean"]) for n_, s_ in ports.items() if "universe_minus_bm_mean" in s_]
    if gaps:
        g = float(np.nanmean([x for _, x in gaps]))
        L.append(f"\n**Benchmark gap:** the equal-weight universe beat {bench} by {_pct(g)} per month on average. "
                 "That gap mixes survivorship (today's survivors are in the universe), equal-weight versus "
                 "cap-weight, and size/value tilt. It is not an edge of the model; read excess vs the universe "
                 f"as the model's contribution and excess vs {bench} as what an investor actually keeps over an "
                 "index fund.")
    rnd = ports.get("random", {})
    if rnd.get("n_periods", 0) > 2 and not np.isnan(rnd.get("excess_se", float("nan"))):
        se = rnd["excess_se"]
        L.append(f"\n**Noise floor:** the random portfolio's monthly excess has a standard error of {_pct(se)} over "
                 f"{rnd['n_periods']} months, so an edge smaller than roughly {_pct(2 * se)} per month cannot be "
                 "told apart from luck in this sample.\n")

    if halves:
        L.append("## Top-N portfolio by half of the sample\n")
        L.append("A real effect should show up in both halves. One strong half and one flat half usually means "
                 "luck, a regime, or a data artefact.\n")
        hrows = []
        for name, pair in halves.items():
            for label, s in zip(("first half", "second half"), pair or (None, None)):
                if not s or s.get("n_periods", 0) == 0:
                    continue
                hrows.append([name, label, f"{s['start']} to {s['end']}", s["n_periods"], _pct(s["total_net"]),
                              _pct(s["total_universe"]), _pct(s.get("total_benchmark_ticker", float("nan"))),
                              _ex_cell(s, "excess", s["n_periods"] >= min_indep)])
        L.append(_md_table(["factor", "half", "period", "months", "net total", "universe total", f"{bench} total",
                            "mean monthly excess vs universe [adj 95% CI]"], hrows))
        L.append("")
    if exit_info:
        L.append("## Exit assumptions\n")
        L.append(f"Delisting return applied after a series ends for good: **{_pct(exit_info['delist_return'])}**; "
                 f"a series ending within {exit_info['grace_days']} trading days of the panel end is treated as data "
                 f"lag, not a delisting. Names whose price series ends early: **{len(exit_info['terminated'])}**"
                 + (f" ({', '.join(map(str, exit_info['terminated'][:15]))}"
                    f"{', ...' if len(exit_info['terminated']) > 15 else ''})." if exit_info["terminated"] else "."))
        L.append("")
        frac = len(exit_info["terminated"]) / max(1, meta["n_tickers"])
        if frac > 0.02:
            L.append(f"> **Warning:** {_pct(frac, 0)} of tickers stop before the end of the panel. A real delisting "
                     "rate is a few percent over a decade, so this is almost certainly stale or ragged data (files "
                     "downloaded on different days, or names that stopped updating), not delistings. Re-download "
                     "everything in one run before trusting any delisting haircut.\n")
        L.append(_md_table(["horizon (d)", "observations", "gap-filled exits", "terminal exits"],
                           [[e["horizon_days"], e["observations"], e["gap_filled"], e["terminal"]]
                            for e in exit_info["events"]]))
        L.append("\nGap-filled = exit price carried forward over a missing bar. Terminal = the name had stopped "
                 "trading. Terminal flags are inferred from price-series endings, not confirmed delistings. A zero terminal-exit count means no scheduled exits encountered a flagged terminal observation; it does not validate delisting robustness. "
                 "The configured haircut cannot affect securities absent from the input files, and early-ending series may reflect stale or incomplete downloads rather than delistings. Re-run with "
                 "`--delist-return -0.3` only as a sensitivity check after the universe and terminal events have been validated.\n")
    L.append("## How to decide\n")
    L.append("A factor earns a place in the live score only if **all** hold: the adjusted IC interval excludes zero; "
             "IC is positive in most dates; the top-N portfolio beats the universe after costs with an interval "
             "that excludes zero; and the result holds in each half of the sample. Otherwise treat it as noise.")
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prices-dir", required=True)
    ap.add_argument("--format", choices=["pickle", "csv"], default="csv")
    ap.add_argument("--factors", nargs="+", default=list(FACTORS), choices=list(FACTORS))
    ap.add_argument("--horizons", nargs="+", type=int, default=[21, 63])
    ap.add_argument("--lag", type=int, default=1, help="days between signal close and trade close")
    ap.add_argument("--top-n", type=int, default=20)
    ap.add_argument("--exit-rank", type=int, default=None, help="keep held names while rank <= this (hysteresis)")
    ap.add_argument("--cost-bps", type=float, default=20.0)
    ap.add_argument("--min-price", type=float, default=5.0)
    ap.add_argument("--min-dollar-volume", type=float, default=1_000_000.0)
    ap.add_argument("--min-names", type=int, default=50)
    ap.add_argument("--benchmark", default=None, help="ticker present in the price folder, e.g. SPY")
    ap.add_argument("--max-tickers", type=int, default=None)
    ap.add_argument("--min-independent", type=int, default=12, help="withhold intervals below this many periods")
    ap.add_argument("--delist-return", type=float, default=0.0,
                    help="return applied after a series ends for good (e.g. -0.3); 0 keeps the last price")
    ap.add_argument("--exit-grace-days", type=int, default=5,
                    help="series ending within this many rows of the panel end are treated as data lag")
    ap.add_argument("--n-boot", type=int, default=5000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out-dir", default="reports/pit_backtest")
    ap.add_argument("--vwrp-ema-regime", action="store_true", help="run standalone EMA regime research instead of the factor suite")
    ap.add_argument("--vwrp-vwap-ema", action="store_true", help="run research-only rolling VWAP-20/EMA-20 crossover test")
    ap.add_argument("--ema-ticker", default="VWRP.L", help="ticker used by --vwrp-ema-regime")
    a = ap.parse_args(argv)
    if a.vwrp_vwap_ema:
        loader = load_pickle_dir if a.format == "pickle" else load_csv_dir
        panel = loader(a.prices_dir, tickers=[a.ema_ticker])
        _run_vwrp_vwap_ema(panel, a.ema_ticker, a.cost_bps, a.out_dir)
        return 0
    if a.vwrp_ema_regime:
        loader = load_pickle_dir if a.format == "pickle" else load_csv_dir
        panel = loader(a.prices_dir, tickers=[a.ema_ticker])
        _run_vwrp_ema_regime(panel, a.ema_ticker, a.cost_bps, a.out_dir)
        return 0

    loader = load_pickle_dir if a.format == "pickle" else load_csv_dir
    panel = loader(a.prices_dir, max_tickers=a.max_tickers)
    elig = eligibility(panel, a.min_price, a.min_dollar_volume)
    positions = month_end_positions(panel.index)
    factors = compute_factors(panel, a.factors, a.seed)
    n_tests = len(factors) * len(a.horizons)
    exits = ExitModel(a.delist_return, a.exit_grace_days).build(panel.adj_close)
    exit_info = {"delist_return": a.delist_return, "grace_days": a.exit_grace_days,
                 "terminated": exits.terminated_names,
                 "events": [exit_event_summary(panel.adj_close, exits, positions, h, a.lag) for h in a.horizons]}

    rows, per_date, ports, halves = [], {}, {}, {}
    for name, fac in factors.items():
        for h in a.horizons:
            row, pdte = evaluate_factor(name, fac, panel.adj_close, elig, positions, h, a.lag, n_tests,
                                        min_names=a.min_names, n_boot=a.n_boot, seed=a.seed, exits=exits)
            rows.append(row)
            if not pdte.empty:
                per_date[(name, h)] = pdte
        sim = simulate_top_n(panel, fac, elig, positions, a.top_n, a.exit_rank, a.lag, a.cost_bps, a.seed,
                             a.benchmark, exits)
        ports[name] = summarize_portfolio(sim, a.n_boot, a.seed, len(factors))
        mid = len(sim) // 2
        if mid >= 1:
            halves[name] = (summarize_portfolio(sim.iloc[:mid], a.n_boot, a.seed, len(factors)),
                            summarize_portfolio(sim.iloc[mid:], a.n_boot, a.seed, len(factors)))
        os.makedirs(a.out_dir, exist_ok=True)
        if not sim.empty:
            sim.to_csv(os.path.join(a.out_dir, f"portfolio_{name}.csv"))

    summary = pd.DataFrame(rows)
    os.makedirs(a.out_dir, exist_ok=True)
    summary.to_csv(os.path.join(a.out_dir, "factor_summary.csv"), index=False)
    for (name, h), df in per_date.items():
        df.to_csv(os.path.join(a.out_dir, f"per_date_{name}_{h}d.csv"))

    meta = {"n_tickers": len(panel.tickers), "n_dates": len(panel.index), "start": panel.index[0].date(),
            "end": panel.index[-1].date(), "n_signal_dates": len(positions), "lag": a.lag, "top_n": a.top_n,
            "exit_rank": a.exit_rank or a.top_n, "cost_bps": a.cost_bps, "min_price": a.min_price,
            "min_dollar_volume": a.min_dollar_volume, "benchmark": a.benchmark}
    report = build_report(meta, summary, ports, n_tests, a.min_independent, halves, exit_info)
    with open(os.path.join(a.out_dir, "report.md"), "w") as fh:
        fh.write(report)
    print(report)
    print(f"Wrote results to {a.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
