"""Top-N portfolio simulation with rank hysteresis, costs and turnover.

Monthly rebalance, equal weight. A held name is kept while its rank is within
``exit_rank`` (default = ``top_n``, i.e. no hysteresis); empty slots are filled
with the best-ranked non-held names. Ties are broken at random, not
alphabetically (the live allocator breaks ties alphabetically, which is
arbitrary and, for a coarse score, decides most of the selection).

Cost model: ``cost_bps`` is charged on every unit of traded notional, both
buying and selling. The first rebalance buys the whole portfolio (turnover 1).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .data import PricePanel
from .evaluate import block_bootstrap_ci


def _rank_desc_random_ties(s: pd.Series, rng: np.random.Generator) -> pd.Series:
    perm = rng.permutation(len(s))
    return s.iloc[perm].rank(method="first", ascending=False).reindex(s.index)


def simulate_top_n(panel: PricePanel, score: pd.DataFrame, elig: pd.DataFrame, positions: np.ndarray,
                   top_n: int = 20, exit_rank: int | None = None, lag: int = 1, cost_bps: float = 20.0,
                   seed: int = 0, benchmark: str | None = None) -> pd.DataFrame:
    adj = panel.adj_close
    adj_exit = adj.ffill()
    exit_rank = exit_rank or top_n
    rng = np.random.default_rng(seed)
    held: list = []
    prev_w = pd.Series(dtype=float)
    rows = []
    for k in range(len(positions) - 1):
        p = int(positions[k])
        e0, e1 = p + lag, int(positions[k + 1]) + lag
        if e1 >= len(adj):
            break
        s = score.iloc[p]
        ok = s.notna() & elig.iloc[p].astype(bool) & adj.iloc[e0].notna()
        if int(ok.sum()) < max(top_n, 1):
            continue
        s = s[ok]
        rank = _rank_desc_random_ties(s, rng)
        keep = [t for t in held if t in rank.index and rank[t] <= exit_rank]
        pool = rank.drop(index=keep).sort_values()
        sel = keep + list(pool.index[: top_n - len(keep)])
        w = pd.Series(1.0 / len(sel), index=sel)

        r_sel = adj_exit.iloc[e1][sel] / adj.iloc[e0][sel] - 1.0
        gross = float((w * r_sel).sum())
        union = w.index.union(prev_w.index)
        turnover = float((w.reindex(union, fill_value=0.0) - prev_w.reindex(union, fill_value=0.0)).abs().sum())
        cost = cost_bps / 1e4 * turnover

        univ = ok[ok].index
        r_u = adj_exit.iloc[e1][univ] / adj.iloc[e0][univ] - 1.0
        bench_ew = float(r_u.mean())  # raw equal-weight universe: the expected return of a random pick
        row = {"signal_date": adj.index[p], "n_held": len(sel), "tied_at_top": float((s == s.max()).sum()),
               "gross": gross, "turnover": turnover, "cost": cost, "net": gross - cost, "bench_ew": bench_ew}
        if benchmark and benchmark in adj.columns and pd.notna(adj.iloc[e0][benchmark]):
            row["bench_ticker"] = float(adj_exit.iloc[e1][benchmark] / adj.iloc[e0][benchmark] - 1.0)
        rows.append(row)

        drifted = w * (1.0 + r_sel)
        prev_w = drifted / drifted.sum()
        held = list(sel)
    return pd.DataFrame(rows).set_index("signal_date") if rows else pd.DataFrame()


def summarize_portfolio(sim: pd.DataFrame, n_boot: int = 5000, seed: int = 0) -> dict:
    if sim.empty:
        return {"n_periods": 0}
    net = sim["net"]
    equity = (1 + net).cumprod()
    out = {
        "n_periods": int(len(net)),
        "total_net": float(equity.iloc[-1] - 1),
        "total_universe": float((1 + sim["bench_ew"]).prod() - 1),
        "avg_turnover": float(sim["turnover"].mean()),
        "total_cost": float(sim["cost"].sum()),
        "max_drawdown": float((equity / equity.cummax() - 1).min()),
        "months_beating_universe": float((net > sim["bench_ew"]).mean()),
        "avg_tied_at_top": float(sim["tied_at_top"].mean()),
    }
    excess = net - sim["bench_ew"]
    lo, hi = block_bootstrap_ci(excess.values, 1, n_boot, (0.05,), seed)[0]
    out.update({"mean_monthly_excess": float(excess.mean()), "excess_lo": lo, "excess_hi": hi,
                "excess_se": float(excess.std(ddof=1) / np.sqrt(len(excess))) if len(excess) > 1 else float("nan")})
    if "bench_ticker" in sim:
        out["total_benchmark_ticker"] = float((1 + sim["bench_ticker"]).prod() - 1)
    return out
