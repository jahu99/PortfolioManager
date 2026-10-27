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
from .factors import FACTORS, compute_factors
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


def build_report(meta: dict, summary: pd.DataFrame, ports: dict, n_tests: int, min_indep: int = 12) -> str:
    L = []
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
    L.append("- **The random factor is your noise gauge.** If it shows a 'significant' result, the harness or the "
             "sample is broken; real factors must clearly beat its spread.\n")

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
    prow = []
    for name, s in ports.items():
        if s.get("n_periods", 0) == 0:
            prow.append([name, 0] + ["n/a"] * 8)
            continue
        prow.append([name, s["n_periods"], _pct(s["total_net"]), _pct(s["total_universe"]),
                     _cell(s["mean_monthly_excess"], s["excess_lo"], s["excess_hi"], s["n_periods"] >= min_indep, _pct),
                     _pct(s["months_beating_universe"], 0), _pct(s["avg_turnover"], 0), _pct(s["total_cost"]),
                     _pct(s["max_drawdown"]), _num(s["avg_tied_at_top"], 0)])
    L.append(_md_table(["factor", "months", "net total", "universe total", "mean monthly excess [95% CI]",
                        "months beating", "avg turnover", "total costs", "max drawdown", "tied@top"], prow))
    L.append("\n'universe' is the raw equal-weight average of every eligible name, i.e. what picking at random "
             "would earn before costs. Do not annualise: with under three years of months it is extrapolation.")
    rnd = ports.get("random", {})
    if rnd.get("n_periods", 0) > 2 and not np.isnan(rnd.get("excess_se", float("nan"))):
        se = rnd["excess_se"]
        L.append(f"\n**Noise floor:** the random portfolio's monthly excess has a standard error of {_pct(se)} over "
                 f"{rnd['n_periods']} months, so an edge smaller than roughly {_pct(2 * se)} per month cannot be "
                 "told apart from luck in this sample.\n")

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
    ap.add_argument("--n-boot", type=int, default=5000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out-dir", default="reports/pit_backtest")
    a = ap.parse_args(argv)

    loader = load_pickle_dir if a.format == "pickle" else load_csv_dir
    panel = loader(a.prices_dir, max_tickers=a.max_tickers)
    elig = eligibility(panel, a.min_price, a.min_dollar_volume)
    positions = month_end_positions(panel.index)
    factors = compute_factors(panel, a.factors, a.seed)
    n_tests = len(factors) * len(a.horizons)

    rows, per_date, ports = [], {}, {}
    for name, fac in factors.items():
        for h in a.horizons:
            row, pdte = evaluate_factor(name, fac, panel.adj_close, elig, positions, h, a.lag, n_tests,
                                        min_names=a.min_names, n_boot=a.n_boot, seed=a.seed)
            rows.append(row)
            if not pdte.empty:
                per_date[(name, h)] = pdte
        sim = simulate_top_n(panel, fac, elig, positions, a.top_n, a.exit_rank, a.lag, a.cost_bps, a.seed,
                             a.benchmark)
        ports[name] = summarize_portfolio(sim, a.n_boot, a.seed)
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
            "min_dollar_volume": a.min_dollar_volume}
    report = build_report(meta, summary, ports, n_tests, a.min_independent)
    with open(os.path.join(a.out_dir, "report.md"), "w") as fh:
        fh.write(report)
    print(report)
    print(f"Wrote results to {a.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
