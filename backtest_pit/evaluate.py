"""Cross-sectional evaluation of a factor against forward returns.

Conventions that remove the usual ways a backtest flatters itself:

* Signal at the close of day ``t`` is traded at the close of ``t + lag``
  (default lag 1), so the day-``t`` move that produced the signal is not earned.
* Forward returns use dividend-adjusted prices (total return).
* Eligibility (price, liquidity) is computed causally from data up to ``t``.
* Confidence intervals come from a moving-block bootstrap over signal dates,
  with a block long enough to cover overlapping forward windows, and a second
  Bonferroni-adjusted interval to account for how many things were tested.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .data import PricePanel

TRADING_DAYS_PER_MONTH = 21


def month_end_positions(index: pd.DatetimeIndex) -> np.ndarray:
    """Row positions of the last trading day of each calendar month."""
    keys = np.asarray(index.year) * 100 + np.asarray(index.month)
    s = pd.Series(np.arange(len(index)), index=keys)
    return s.groupby(level=0).max().to_numpy()


def eligibility(panel: PricePanel, min_price: float = 5.0,
                min_dollar_volume: float = 1_000_000.0, window: int = 20) -> pd.DataFrame:
    """Causal tradability mask: price floor and median 20-day dollar volume floor."""
    dollar_vol = (panel.close * panel.volume).rolling(window, min_periods=window).median()
    return ((panel.close >= min_price) & (dollar_vol >= min_dollar_volume)).fillna(False)


def forward_returns(adj: pd.DataFrame, positions: np.ndarray, horizon: int, lag: int = 1) -> pd.DataFrame:
    """Total return from close ``t+lag`` to close ``t+lag+horizon``, indexed by signal date ``t``.

    If a name stops trading before the exit date, its last available price is
    used (so a collapse before delisting is counted rather than dropped). Names
    with no entry price are NaN.
    """
    entry = positions + lag
    exit_ = entry + horizon
    ok = exit_ < len(adj)
    if not ok.any():
        return pd.DataFrame(columns=adj.columns, dtype=float)
    adj_exit = adj.ffill()
    e = adj.iloc[entry[ok]].to_numpy()
    x = adj_exit.iloc[exit_[ok]].to_numpy()
    with np.errstate(divide="ignore", invalid="ignore"):
        fr = x / e - 1.0
    return pd.DataFrame(fr, index=adj.index[positions[ok]], columns=adj.columns)


def block_bootstrap_ci(x, block: int = 1, n_boot: int = 5000, alphas=(0.05,), seed: int = 0):
    """Moving-block bootstrap CI(s) for the mean of a (possibly autocorrelated) series."""
    x = np.asarray(x, dtype=float)
    x = x[~np.isnan(x)]
    n = len(x)
    if n < 3:
        return [(float("nan"), float("nan")) for _ in alphas]
    block = int(max(1, min(block, n)))
    rng = np.random.default_rng(seed)
    n_blocks = math.ceil(n / block)
    starts = rng.integers(0, n - block + 1, size=(n_boot, n_blocks))
    idx = (starts[:, :, None] + np.arange(block)[None, None, :]).reshape(n_boot, -1)[:, :n]
    means = x[idx].mean(axis=1)
    return [(float(np.quantile(means, a / 2)), float(np.quantile(means, 1 - a / 2))) for a in alphas]


def _tie_random_rank(s: pd.Series, rng: np.random.Generator) -> pd.Series:
    """Ranks ascending, ties broken at random (not alphabetically)."""
    perm = rng.permutation(len(s))
    return s.iloc[perm].rank(method="first").reindex(s.index)


def cross_section_stats(factor: pd.DataFrame, fwd: pd.DataFrame, elig: pd.DataFrame,
                        q: int = 5, winsor=(0.01, 0.99), min_names: int = 50, seed: int = 0):
    """Per signal date: rank IC, quantile mean returns, #names, #names tied at the top score."""
    ics, quants, names, ties = {}, {}, {}, {}
    fac = factor.reindex(fwd.index)
    el = elig.reindex(fwd.index).fillna(False)
    for k, d in enumerate(fwd.index):
        f, r = fac.loc[d], fwd.loc[d]
        m = f.notna() & r.notna() & el.loc[d].astype(bool)
        n = int(m.sum())
        if n < min_names:
            continue
        f, r = f[m], r[m]
        rng = np.random.default_rng(seed + k)
        rw = r.clip(r.quantile(winsor[0]), r.quantile(winsor[1]))
        bucket = pd.qcut(_tie_random_rank(f, rng), q, labels=False)
        means = rw.groupby(bucket).mean()
        ics[d] = f.rank().corr(r.rank())
        quants[d] = [float(means.get(i, np.nan)) for i in range(q)] + [float(rw.mean())]
        names[d] = n
        ties[d] = float((f == f.max()).sum())
    cols = [f"Q{i + 1}" for i in range(q)] + ["universe"]
    return (pd.Series(ics, dtype=float), pd.DataFrame.from_dict(quants, orient="index", columns=cols),
            pd.Series(names, dtype=float), pd.Series(ties, dtype=float))


def evaluate_factor(name: str, factor: pd.DataFrame, adj: pd.DataFrame, elig: pd.DataFrame,
                    positions: np.ndarray, horizon: int, lag: int = 1, n_tests: int = 1,
                    q: int = 5, min_names: int = 50, n_boot: int = 5000, seed: int = 0):
    """Returns (summary_dict, per_date_frame)."""
    fwd = forward_returns(adj, positions, horizon, lag)
    ic, quants, names, ties = cross_section_stats(factor, fwd, elig, q=q, min_names=min_names, seed=seed)
    row = {"factor": name, "horizon_days": horizon, "n_dates": int(len(ic))}
    nan = float("nan")
    if len(ic) == 0:
        row.update({k: nan for k in (
            "indep_periods", "mean_names", "mean_tied_at_top", "mean_ic", "ic_lo", "ic_hi", "ic_adj_lo",
            "ic_adj_hi", "ic_hit_rate", "top_vs_universe", "tvu_lo", "tvu_hi", "tvu_adj_lo", "tvu_adj_hi",
            "top_vs_bottom")})
        return row, pd.DataFrame()
    block = max(1, math.ceil(horizon / TRADING_DAYS_PER_MONTH))
    alphas = (0.05, 0.05 / max(1, n_tests))
    (ic_lo, ic_hi), (ic_alo, ic_ahi) = block_bootstrap_ci(ic.values, block, n_boot, alphas, seed)
    top = f"Q{q}"
    tvu = (quants[top] - quants["universe"])
    tvb = (quants[top] - quants["Q1"])
    (t_lo, t_hi), (t_alo, t_ahi) = block_bootstrap_ci(tvu.values, block, n_boot, alphas, seed)
    row.update({
        "indep_periods": len(ic) * min(1.0, TRADING_DAYS_PER_MONTH / horizon),
        "mean_names": float(names.mean()),
        "mean_tied_at_top": float(ties.mean()),
        "mean_ic": float(ic.mean()), "ic_lo": ic_lo, "ic_hi": ic_hi, "ic_adj_lo": ic_alo, "ic_adj_hi": ic_ahi,
        "ic_hit_rate": float((ic > 0).mean()),
        "top_vs_universe": float(tvu.mean()), "tvu_lo": t_lo, "tvu_hi": t_hi, "tvu_adj_lo": t_alo, "tvu_adj_hi": t_ahi,
        "top_vs_bottom": float(tvb.mean()),
    })
    per_date = quants.copy()
    per_date.insert(0, "ic", ic)
    per_date["names"] = names
    per_date["tied_at_top"] = ties
    return row, per_date
