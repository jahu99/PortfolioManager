"""
BUY NEW Entry Quality — Shadow Mode.

Purpose
-------
Measure whether a stock appears to be a sensible entry point for a NEW
position, independently of the existing Investment Score and signal.

This module is observational only.

IMPORTANT
---------
Entry Quality does NOT:
    - change Technical Score
    - change Quality Score
    - change Growth Score
    - change Investment Score
    - change Signal
    - approve/reject BUY NEW
    - change deterministic governance
    - change LLM reconciliation

It exists initially to collect evidence for later calibration.
"""

from __future__ import annotations

from typing import Any

import pandas as pd


# ---------------------------------------------------------------------------
# Provisional shadow-mode classification bands.
#
# These are descriptive telemetry bands only. They are NOT BUY NEW gates.
# ---------------------------------------------------------------------------

REASONABLE_MAX_SMA50_EXTENSION = 5.0
MODERATELY_EXTENDED_MAX_SMA50_EXTENSION = 10.0
EXTENDED_MAX_SMA50_EXTENSION = 15.0


def _safe_float(value: Any) -> float | None:
    """Return a finite float or None."""

    try:
        if value is None:
            return None

        numeric = float(value)

        if pd.isna(numeric):
            return None

        return numeric

    except (TypeError, ValueError):
        return None


def _percentage_above(
    price: Any,
    moving_average: Any,
) -> float | None:
    """
    Calculate percentage by which price is above a moving average.

    Example
    -------
    price = 120
    SMA50  = 100

    returns 20.0
    """

    price_value = _safe_float(price)
    average_value = _safe_float(moving_average)

    if price_value is None:
        return None

    if average_value is None:
        return None

    if average_value <= 0:
        return None

    return (
        (price_value - average_value)
        / average_value
        * 100.0
    )


def _historical_return(
    df: pd.DataFrame,
    periods: int,
) -> float | None:
    """
    Calculate percentage return over the requested number of trading days.

    periods=5 means current close versus the close five trading observations
    earlier.

    Returns None when insufficient valid price history exists.
    """

    if not isinstance(df, pd.DataFrame):
        return None

    if "Close" not in df.columns:
        return None

    if len(df) <= periods:
        return None

    try:
        current_price = _safe_float(
            df["Close"].iloc[-1]
        )

        previous_price = _safe_float(
            df["Close"].iloc[-(periods + 1)]
        )

        if current_price is None:
            return None

        if previous_price is None:
            return None

        if previous_price <= 0:
            return None

        return (
            (current_price - previous_price)
            / previous_price
            * 100.0
        )

    except (IndexError, TypeError, ValueError):
        return None


def classify_entry_quality(
    extension_sma50_pct: float | None,
) -> str:
    """
    Provide a provisional shadow-mode entry classification.

    This classification is informational only and MUST NOT be used as
    a BUY NEW decision gate at this stage.
    """

    if extension_sma50_pct is None:
        return "UNKNOWN"

    if extension_sma50_pct <= REASONABLE_MAX_SMA50_EXTENSION:
        return "REASONABLE"

    if extension_sma50_pct <= MODERATELY_EXTENDED_MAX_SMA50_EXTENSION:
        return "MODERATELY EXTENDED"

    if extension_sma50_pct <= EXTENDED_MAX_SMA50_EXTENSION:
        return "EXTENDED"

    return "HIGHLY EXTENDED"


def assess_entry_quality(
    df: pd.DataFrame,
) -> dict[str, Any]:
    """
    Calculate BUY NEW entry-quality telemetry.

    Returns a flat dictionary suitable for inclusion in the existing
    stock-result record and recommendation evidence snapshot.
    """

    if not isinstance(df, pd.DataFrame) or df.empty:
        return {
            "Extension SMA50 %": None,
            "Extension SMA200 %": None,
            "Return 5D %": None,
            "Return 10D %": None,
            "Return 20D %": None,
            "Entry Quality": "UNKNOWN",
            "Entry Quality Mode": "SHADOW",
        }

    latest = df.iloc[-1]

    price = latest.get("Close")
    sma50 = latest.get("SMA50")
    sma200 = latest.get("SMA200")

    extension_sma50_pct = _percentage_above(
        price,
        sma50,
    )

    extension_sma200_pct = _percentage_above(
        price,
        sma200,
    )

    return_5d_pct = _historical_return(
        df,
        5,
    )

    return_10d_pct = _historical_return(
        df,
        10,
    )

    return_20d_pct = _historical_return(
        df,
        20,
    )

    return {
        "Extension SMA50 %": (
            round(extension_sma50_pct, 2)
            if extension_sma50_pct is not None
            else None
        ),
        "Extension SMA200 %": (
            round(extension_sma200_pct, 2)
            if extension_sma200_pct is not None
            else None
        ),
        "Return 5D %": (
            round(return_5d_pct, 2)
            if return_5d_pct is not None
            else None
        ),
        "Return 10D %": (
            round(return_10d_pct, 2)
            if return_10d_pct is not None
            else None
        ),
        "Return 20D %": (
            round(return_20d_pct, 2)
            if return_20d_pct is not None
            else None
        ),
        "Entry Quality": classify_entry_quality(
            extension_sma50_pct
        ),
        "Entry Quality Mode": "SHADOW",
    }


__all__ = [
    "assess_entry_quality",
    "classify_entry_quality",
]
