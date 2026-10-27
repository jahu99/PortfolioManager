"""Causal (point-in-time) factors, computed for every date at once.

Every factor here uses only rolling / shifted / exponentially weighted
operations, which look backwards, so the value on row ``t`` depends only on
data up to and including ``t``. ``tests/test_pit_backtest.py`` verifies this by
corrupting all data after ``t`` and checking row ``t`` does not change.

What is deliberately NOT here: the quality and growth scores. They come from a
Yahoo snapshot of *today's* fundamentals, so using them to score the past would
leak the future. They can only be backtested with point-in-time fundamentals
(e.g. SEC filings dated by filing date).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .data import PricePanel


def sma(x: pd.DataFrame, window: int) -> pd.DataFrame:
    return x.rolling(window, min_periods=window).mean()


def rsi_wilder(close: pd.DataFrame, window: int = 14) -> pd.DataFrame:
    """Wilder RSI, same definition as ``ta.momentum.RSIIndicator``."""
    diff = close.diff(1)
    up = diff.clip(lower=0.0)
    down = (-diff).clip(lower=0.0)
    alpha = 1.0 / window
    ema_up = up.ewm(alpha=alpha, min_periods=window, adjust=False).mean()
    ema_dn = down.ewm(alpha=alpha, min_periods=window, adjust=False).mean()
    rs = ema_up / ema_dn
    rsi = 100.0 - 100.0 / (1.0 + rs)
    rsi = rsi.where(ema_dn != 0, 100.0)
    return rsi.where(ema_up.notna() & ema_dn.notna())


def _frame(values, like: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(values, index=like.index, columns=like.columns)


def technical_score(close: pd.DataFrame, volume: pd.DataFrame) -> pd.DataFrame:
    """Vectorised copy of ``analysis/scorer.py::score_stock`` (0-100).

    Trend 40 (close>SMA200 25, close>SMA50 15) + momentum 30 (RSI in 50-70: 15;
    3m return >20%: 15, >0: 8) + volume 20 (ratio >1.5: 20, >1.2: 10) + risk 10
    (close>SMA200: 10 else 2), capped at 100. NaN until all inputs exist.
    """
    sma50, sma200 = sma(close, 50), sma(close, 200)
    rsi = rsi_wilder(close, 14)
    ret3m = close / close.shift(63) - 1.0
    vol_avg = volume.rolling(20, min_periods=20).mean()
    ratio = volume / vol_avg.where(vol_avg > 0)

    valid = (close.notna() & volume.notna() & sma200.notna() & rsi.notna()
             & ret3m.notna() & vol_avg.notna())

    trend = 25.0 * (close > sma200) + 15.0 * (close > sma50)
    mom = 15.0 * ((rsi >= 50) & (rsi <= 70)) + _frame(
        np.where(ret3m > 0.20, 15.0, np.where(ret3m > 0, 8.0, 0.0)), close)
    vol = _frame(np.where(ratio > 1.5, 20.0, np.where(ratio > 1.2, 10.0, 0.0)), close)
    risk = _frame(np.where(close > sma200, 10.0, 2.0), close)

    score = (trend + mom + vol + risk).clip(upper=100.0)
    return score.where(valid)


def momentum(adj_close: pd.DataFrame, lookback: int, skip: int = 21) -> pd.DataFrame:
    """Classic momentum: return from ``lookback`` days ago to ``skip`` days ago."""
    return adj_close.shift(skip) / adj_close.shift(lookback) - 1.0


def random_factor(like: pd.DataFrame, seed: int = 0) -> pd.DataFrame:
    """Pure-noise control. A sound harness must find nothing in this."""
    rng = np.random.default_rng(seed)
    return _frame(rng.standard_normal(like.shape), like).where(like.notna())


def _f_technical(p: PricePanel, seed: int) -> pd.DataFrame:
    return technical_score(p.close, p.volume)


def _f_mom_12_1(p: PricePanel, seed: int) -> pd.DataFrame:
    return momentum(p.adj_close, 252, 21)


def _f_mom_6_1(p: PricePanel, seed: int) -> pd.DataFrame:
    return momentum(p.adj_close, 126, 21)


def _f_random(p: PricePanel, seed: int) -> pd.DataFrame:
    return random_factor(p.close, seed)


# Add your own: register a function (PricePanel, seed) -> DataFrame (date x ticker).
FACTORS = {
    "technical_score": _f_technical,
    "mom_12_1": _f_mom_12_1,
    "mom_6_1": _f_mom_6_1,
    "random": _f_random,
}


def compute_factors(panel: PricePanel, names=None, seed: int = 0) -> dict:
    names = list(names) if names else list(FACTORS)
    unknown = [n for n in names if n not in FACTORS]
    if unknown:
        raise KeyError(f"unknown factor(s): {unknown}; available: {list(FACTORS)}")
    return {n: FACTORS[n](panel, seed) for n in names}
