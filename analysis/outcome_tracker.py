
"""
Outcome Tracker

Purpose
-------
Evaluate historical stock recommendations against realised market
performance at the agreed learning milestones:

    - 5 trading days
    - 10 trading days
    - 60 trading days

This module is the source of truth for realised recommendation outcomes.

Architecture
------------

    recommendations
            |
            v
    outcome_tracker.py
            |
            v
    recommendation_evaluations
            |
            v
    recommendation_learning.py
            |
            v
    recommendation_intelligence.py
            |
            v
    AI Decision Context
            |
            v
    Governed Portfolio Decision

Important
---------
- Only 5, 10 and 60 trading-day milestones are evaluated.
- 20 trading days is deliberately NOT a learning milestone.
- Raw OHLCV data is the only data cached by this module.
- Completed evaluations contain realised return/outcome data.
- Future/uncompleted milestones are simply omitted.
- Historical recommendation scores are copied into each completed
  evaluation so learning can relate outcomes to the score at the
  time of recommendation.
- No recommendation scores or weights are recalculated here.
- No portfolio decisions are made here.
"""

from __future__ import annotations

import os

import pandas as pd
import yfinance as yf


# ============================================================
# Evaluation horizons
# ============================================================

EVALUATION_HORIZONS = [
    5,
    10,
    60,
]


# ============================================================
# Run-level price cache
# ============================================================

# Raw Close price series only.
#
# This prevents the same ticker being loaded repeatedly during
# a single evaluation run.

PRICE_HISTORY_CACHE: dict[str, pd.Series] = {}


# ============================================================
# Starting price helper
# ============================================================

def safe_start_price(
    value,
):
    """
    Safely convert the recommendation starting price to a valid
    positive float.
    """

    try:

        if value is None:
            return None

        price = float(
            value
        )

        if price <= 0:
            return None

        return price

    except (
        TypeError,
        ValueError,
    ):

        return None


# ============================================================
# Price history
# ============================================================

def load_price_history(
    ticker,
    recommendation_date,
    today=None,
):
    """
    Load raw historical Close prices for outcome evaluation.

    Parameters
    ----------
    ticker:
        Security ticker.

    recommendation_date:
        Earliest recommendation date that must be covered.

    today:
        Current evaluation date.

    Returns
    -------
    pandas.Series
        Raw closing prices indexed by trading date.

    Cache policy
    ------------
    Only raw market prices are cached.

    The cache is refreshed when it does not contain the latest
    available market session. No recommendation, score, signal or
    learning result is stored in this cache.
    """

    CACHE_DIR = "cache/prices"

    os.makedirs(
        CACHE_DIR,
        exist_ok=True,
    )

    try:

        ticker = str(
            ticker
        ).strip().upper()

        if not ticker:
            return pd.Series(
                dtype=float
            )

        recommendation_date = (
            pd.to_datetime(
                recommendation_date,
                errors="coerce",
            )
            .normalize()
        )

        if pd.isna(
            recommendation_date
        ):
            return pd.Series(
                dtype=float
            )

        if today is None:

            today = (
                pd.Timestamp.today()
                .normalize()
            )

        else:

            today = (
                pd.to_datetime(
                    today,
                    errors="coerce",
                )
                .normalize()
            )

        if pd.isna(today):
            return pd.Series(
                dtype=float
            )

        if today <= recommendation_date:
            return pd.Series(
                dtype=float
            )

        cache_file = os.path.join(
            CACHE_DIR,
            f"{ticker}_evaluation.parquet",
        )

        cached = None

        # --------------------------------------------------------
        # Load existing raw evaluation cache
        # --------------------------------------------------------

        if os.path.exists(
            cache_file
        ):

            try:

                cached = pd.read_parquet(
                    cache_file
                )

                if not cached.empty:

                    cached.index = (
                        pd.to_datetime(
                            cached.index,
                            errors="coerce",
                        )
                        .normalize()
                    )

                    cached = cached[
                        ~cached.index.isna()
                    ]

                    cached = (
                        cached
                        .sort_index()
                        .loc[
                            ~cached.index.duplicated(
                                keep="last"
                            )
                        ]
                    )

            except Exception as exc:

                print(
                    f"{ticker}: "
                    f"evaluation cache read failed: {exc}"
                )

                cached = None

        # --------------------------------------------------------
        # Determine latest cached date
        # --------------------------------------------------------

        latest_cached_date = None

        if (
            cached is not None
            and not cached.empty
        ):

            latest_cached_date = (
                cached.index.max()
            )

        # --------------------------------------------------------
        # Determine whether refresh is required
        # --------------------------------------------------------

        needs_refresh = (
            cached is None
            or cached.empty
            or latest_cached_date < today
        )

        # --------------------------------------------------------
        # Download only when required
        # --------------------------------------------------------

        if needs_refresh:

            if latest_cached_date is not None:

                download_start = (
                    latest_cached_date
                    +
                    pd.Timedelta(days=1)
                )

            else:

                # Include a small buffer before the earliest
                # recommendation date.
                download_start = (
                    recommendation_date
                    -
                    pd.Timedelta(days=10)
                )

            download_end = (
                today
                +
                pd.Timedelta(days=1)
            )

            print(
                f"{ticker}: "
                f"updating raw price cache "
                f"{download_start.date()} -> "
                f"{today.date()}"
            )

            try:

                data = yf.download(
                    ticker,
                    start=download_start,
                    end=download_end,
                    progress=False,
                    auto_adjust=False,
                )

            except Exception as exc:

                print(
                    f"{ticker}: "
                    f"Yahoo download failed: {exc}"
                )

                data = pd.DataFrame()

            if not data.empty:

                # Flatten yfinance MultiIndex columns.
                if isinstance(
                    data.columns,
                    pd.MultiIndex,
                ):

                    data.columns = (
                        data.columns
                        .get_level_values(0)
                    )

                data.index = (
                    pd.to_datetime(
                        data.index,
                        errors="coerce",
                    )
                    .normalize()
                )

                data = data[
                    ~data.index.isna()
                ]

                data = (
                    data
                    .sort_index()
                    .loc[
                        ~data.index.duplicated(
                            keep="last"
                        )
                    ]
                )

                # Raw OHLCV merge only.
                if (
                    cached is not None
                    and not cached.empty
                ):

                    cached = pd.concat(
                        [
                            cached,
                            data,
                        ]
                    )

                    cached = (
                        cached
                        .sort_index()
                        .loc[
                            ~cached.index.duplicated(
                                keep="last"
                            )
                        ]
                    )

                else:

                    cached = data

                # Save raw price data only.
                try:

                    cached.to_parquet(
                        cache_file
                    )

                except Exception as exc:

                    print(
                        f"{ticker}: "
                        f"evaluation cache save failed: {exc}"
                    )

        # --------------------------------------------------------
        # Validate history
        # --------------------------------------------------------

        if (
            cached is None
            or cached.empty
            or "Close" not in cached.columns
        ):

            return pd.Series(
                dtype=float
            )

        # --------------------------------------------------------
        # Extract Close
        # --------------------------------------------------------

        close = cached[
            "Close"
        ]

        if isinstance(
            close,
            pd.DataFrame,
        ):

            close = close.iloc[
                :,
                0,
            ]

        close.index = (
            pd.to_datetime(
                close.index,
                errors="coerce",
            )
            .normalize()
        )

        close = close[
            ~close.index.isna()
        ]

        close = (
            close
            .dropna()
            .sort_index()
        )

        # Keep the recommendation date and everything after it.
        close = close[
            close.index >= (
                recommendation_date
                -
                pd.Timedelta(days=5)
            )
        ]

        return close

    except Exception as exc:

        print(
            f"Historical price error "
            f"{ticker}: {exc}"
        )

        return pd.Series(
            dtype=float
        )


# ============================================================
# Trading days elapsed
# ============================================================

def get_trading_days_elapsed(
    close,
    recommendation_date,
):
    """
    Return the number of completed trading sessions after the
    recommendation date.

    The recommendation date itself is excluded.

    Example
    -------
    Recommendation Friday:

        Monday = trading day 1
        Tuesday = trading day 2
    """

    try:

        if (
            close is None
            or close.empty
        ):

            return None

        recommendation_date = (
            pd.to_datetime(
                recommendation_date,
                errors="coerce",
            )
            .normalize()
        )

        if pd.isna(
            recommendation_date
        ):

            return None

        future_dates = close.index[
            close.index > recommendation_date
        ]

        return len(
            future_dates
        )

    except Exception as exc:

        print(
            "Trading-day calculation error:",
            exc,
        )

        return None


# ============================================================
# Evaluation price
# ============================================================

def get_evaluation_price(
    close,
    recommendation_date,
    days,
):
    """
    Return the closing price exactly `days` completed trading
    sessions after the recommendation date.

    Day 1 is the first trading session after the recommendation.
    """

    try:

        if (
            close is None
            or close.empty
        ):

            return None

        recommendation_date = (
            pd.to_datetime(
                recommendation_date,
                errors="coerce",
            )
            .normalize()
        )

        if pd.isna(
            recommendation_date
        ):

            return None

        future_prices = close[
            close.index > recommendation_date
        ]

        if len(
            future_prices
        ) < days:

            return None

        price = future_prices.iloc[
            days - 1
        ]

        return float(
            price
        )

    except Exception as exc:

        print(
            f"Evaluation price error: {exc}"
        )

        return None


# ============================================================
# Outcome
# ============================================================

def calculate_outcome(
    return_percent,
):
    """
    Classify an evaluation result.

    SUCCESS:
        +5% or better

    FAILED:
        -5% or worse

    FLAT:
        Between -5% and +5%
    """

    if return_percent >= 5:
        return "SUCCESS"

    if return_percent <= -5:
        return "FAILED"

    return "FLAT"


# ============================================================
# Recommendation date lookup
# ============================================================

def build_ticker_recommendation_dates(
    recommendations,
):
    """
    Determine the earliest recommendation date for each ticker.

    Each ticker is loaded once per evaluation run, using the earliest
    recommendation date as the required starting point for raw price
    history.
    """

    result = {}

    if (
        recommendations is None
        or recommendations.empty
    ):

        return result

    for _, row in recommendations.iterrows():

        ticker = str(
            row.get(
                "ticker",
                "",
            )
        ).upper().strip()

        if not ticker:
            continue

        recommendation_date = pd.to_datetime(
            row.get(
                "date"
            ),
            errors="coerce",
        )

        if pd.isna(
            recommendation_date
        ):

            continue

        recommendation_date = (
            recommendation_date
            .normalize()
        )

        existing = result.get(
            ticker
        )

        if (
            existing is None
            or
            recommendation_date < existing
        ):

            result[
                ticker
            ] = recommendation_date

    return result


# ============================================================
# Main evaluation engine
# ============================================================

def calculate_evaluations(
    recommendations,
):
    """
    Evaluate recommendation performance at the agreed milestones:

        5 trading days
        10 trading days
        60 trading days

    Only completed evaluations are returned.

    The function:

        1. Reuses the raw market-data parquet cache.
        2. Determines the earliest recommendation date per ticker.
        3. Loads each ticker once per run.
        4. Stores the resulting Close series in the run-level cache.
        5. Reuses that history for all recommendations for the ticker.
        6. Creates one row per completed recommendation/horizon.
        7. Never creates rows for milestones that have not yet completed.

    This function is the source of realised outcome evidence.
    Downstream learning should consume its completed evaluation rows.
    """

    print(
        "OUTCOME EVALUATION START"
    )

    # --------------------------------------------------------
    # Clear run-level cache
    # --------------------------------------------------------

    PRICE_HISTORY_CACHE.clear()

    # --------------------------------------------------------
    # No recommendations
    # --------------------------------------------------------

    if (
        recommendations is None
        or recommendations.empty
    ):

        print(
            "NO RECOMMENDATIONS"
        )

        return pd.DataFrame()

    evaluations = []

    today = (
        pd.Timestamp.today()
        .normalize()
    )

    # ========================================================
    # Identify unique tickers and earliest dates
    # ========================================================

    ticker_recommendation_dates = (
        build_ticker_recommendation_dates(
            recommendations
        )
    )

    tickers = set(
        ticker_recommendation_dates.keys()
    )

    print(
        "UNIQUE EVALUATION TICKERS:",
        len(tickers),
    )

    # ========================================================
    # Load price history once per ticker
    # ========================================================

    for ticker in sorted(
        tickers
    ):

        print(
            f"Loading price history: {ticker}"
        )

        recommendation_date = (
            ticker_recommendation_dates[
                ticker
            ]
        )

        close = load_price_history(
            ticker,
            recommendation_date,
            today,
        )

        if (
            close is None
            or close.empty
        ):

            print(
                f"{ticker}: "
                f"historical price data unavailable"
            )

            continue

        # IMPORTANT:
        # The previous implementation loaded the data but did not
        # store it in PRICE_HISTORY_CACHE. The processing phase then
        # retrieved an empty cache. Store the loaded raw Close series.
        PRICE_HISTORY_CACHE[
            ticker
        ] = close

    print(
        "PRICE HISTORY CACHE COMPLETE:",
        len(
            PRICE_HISTORY_CACHE
        ),
        "tickers",
    )

    # ========================================================
    # Process recommendations
    # ========================================================

    for _, row in recommendations.iterrows():

        ticker = str(
            row.get(
                "ticker",
                "",
            )
        ).upper().strip()

        if not ticker:
            continue

        print(
            "Evaluating",
            ticker,
        )

        try:

            # ------------------------------------------------
            # Recommendation ID
            # ------------------------------------------------

            recommendation_id = row.get(
                "id"
            )

            # ------------------------------------------------
            # Recommendation date
            # ------------------------------------------------

            recommendation_date = pd.to_datetime(
                row.get(
                    "date"
                ),
                errors="coerce",
            )

            if pd.isna(
                recommendation_date
            ):

                print(
                    f"{ticker}: "
                    f"invalid recommendation date"
                )

                continue

            recommendation_date = (
                recommendation_date
                .normalize()
            )

            # ------------------------------------------------
            # Price history from run-level cache
            # ------------------------------------------------

            close = PRICE_HISTORY_CACHE.get(
                ticker
            )

            if (
                close is None
                or close.empty
            ):

                print(
                    f"{ticker}: "
                    f"historical price data unavailable"
                )

                continue

            # ------------------------------------------------
            # Trading sessions elapsed
            # ------------------------------------------------

            trading_days_elapsed = (
                get_trading_days_elapsed(
                    close,
                    recommendation_date,
                )
            )

            if trading_days_elapsed is None:

                print(
                    f"{ticker}: "
                    f"unable to determine trading sessions"
                )

                continue

            print(
                f"DEBUG EVALUATOR: "
                f"{ticker} "
                f"{trading_days_elapsed} "
                f"{row.get('investment_score', 0)} "
                f"{row.get('technical_score', 0)} "
                f"{row.get('quality_score', 0)} "
                f"{row.get('growth_score', 0)} "
                f"{row.get('confidence_score', 0)}"
            )

            # ------------------------------------------------
            # Starting price
            # ------------------------------------------------

            start_price = safe_start_price(
                row.get(
                    "price",
                    0,
                )
            )

            if start_price is None:

                print(
                    f"{ticker}: "
                    f"invalid starting price"
                )

                continue

            # =================================================
            # Evaluation horizons
            # =================================================

            for horizon in EVALUATION_HORIZONS:

                # ---------------------------------------------
                # Not enough trading sessions
                # ---------------------------------------------

                if (
                    trading_days_elapsed
                    <
                    horizon
                ):

                    print(
                        f"{ticker}: "
                        f"{horizon}-trading-day "
                        f"evaluation not ready yet "
                        f"({trading_days_elapsed}/"
                        f"{horizon} sessions)"
                    )

                    continue

                # ---------------------------------------------
                # Evaluation price
                # ---------------------------------------------

                evaluation_price = (
                    get_evaluation_price(
                        close,
                        recommendation_date,
                        horizon,
                    )
                )

                if evaluation_price is None:

                    print(
                        f"{ticker}: "
                        f"{horizon}-trading-day "
                        f"price unavailable"
                    )

                    continue

                # ---------------------------------------------
                # Return
                # ---------------------------------------------

                return_percent = round(
                    (
                        (
                            evaluation_price
                            -
                            start_price
                        )
                        /
                        start_price
                    )
                    * 100,
                    2,
                )

                # ---------------------------------------------
                # Outcome
                # ---------------------------------------------

                outcome = calculate_outcome(
                    return_percent
                )

                # ---------------------------------------------
                # Evaluation date
                # ---------------------------------------------

                future_dates = close.index[
                    close.index > recommendation_date
                ]

                if len(
                    future_dates
                ) >= horizon:

                    evaluation_date = (
                        future_dates[
                            horizon - 1
                        ]
                    )

                else:

                    evaluation_date = today

                # ---------------------------------------------
                # Store completed evaluation
                # ---------------------------------------------

                evaluations.append(
                    {
                        "recommendation_id":
                            recommendation_id,

                        "ticker":
                            ticker,

                        "signal":
                            row.get(
                                "signal",
                                "",
                            ),

                        "recommendation_date":
                            recommendation_date,

                        "evaluation_date":
                            evaluation_date,

                        "days_after":
                            horizon,

                        "start_price":
                            round(
                                start_price,
                                4,
                            ),

                        "evaluation_price":
                            round(
                                evaluation_price,
                                4,
                            ),

                        "return_percent":
                            return_percent,

                        "outcome":
                            outcome,

                        "investment_score":
                            row.get(
                                "investment_score",
                                0,
                            ),

                        "technical_score":
                            row.get(
                                "technical_score",
                                0,
                            ),

                        "quality_score":
                            row.get(
                                "quality_score",
                                0,
                            ),

                        "growth_score":
                            row.get(
                                "growth_score",
                                0,
                            ),

                        "confidence_score":
                            row.get(
                                "confidence_score",
                                0,
                            ),
                    }
                )

                print(
                    f"DEBUG EVALUATION "
                    f"{ticker} "
                    f"{horizon} days "
                    f"{return_percent:.2f}% "
                    f"{outcome}"
                )

        except Exception as exc:

            print(
                f"Evaluation error "
                f"{ticker}: {exc}"
            )

            continue

    # ========================================================
    # Create DataFrame
    # ========================================================

    if not evaluations:

        print(
            "NO EVALUATIONS CREATED"
        )

        return pd.DataFrame()

    df = pd.DataFrame(
        evaluations
    )

    # ========================================================
    # Final ordering
    # ========================================================

    if not df.empty:

        sort_columns = [
            column
            for column in [
                "recommendation_date",
                "ticker",
                "days_after",
            ]
            if column in df.columns
        ]

        if sort_columns:

            df = (
                df
                .sort_values(
                    sort_columns
                )
                .reset_index(
                    drop=True
                )
            )

    # ========================================================
    # Diagnostics
    # ========================================================

    print(
        "EVALUATIONS CREATED:",
        df.shape,
    )

    if not df.empty:

        print(
            "\nEVALUATION HORIZON COUNTS:"
        )

        print(
            df[
                "days_after"
            ]
            .value_counts()
            .sort_index()
            .to_string()
        )

    return df


# ============================================================
# Module test
# ============================================================

if __name__ == "__main__":

    print(
        "Outcome Tracker"
    )

    print(
        "Evaluation horizons:",
        EVALUATION_HORIZONS,
    )

    print(
        "Expected milestones: "
        "5, 10, 60 trading days"
    )
