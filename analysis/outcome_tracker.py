# analysis/outcome_tracker.py

import pandas as pd

from data.market_data import get_stock_data


# =====================================================
# Evaluation horizons
# =====================================================

EVALUATION_HORIZONS = [
    5,
    10,
    20,
    60
]


# =====================================================
# Run-level price cache
# =====================================================
#
# This prevents the same ticker being loaded repeatedly
# during a single evaluation run.
#
# The underlying data is supplied by market_data.py,
# which already maintains the parquet price cache.
# =====================================================

PRICE_HISTORY_CACHE = {}


# =====================================================
# Price history
# =====================================================

# =====================================================
# Price history
# =====================================================

def load_price_history(
    ticker,
    recommendation_date,
    today=None
):
    """
    Load raw historical OHLCV data for outcome evaluation.

    Cache policy
    ------------
    The cache contains RAW PRICE DATA ONLY.

    We reuse cached data when it already contains the
    latest available trading session.

    If the cache is missing newer data, only the missing
    period is downloaded and merged into the cache.

    No scores, indicators, signals, recommendations,
    outcomes or learning results are cached here.
    """

    import os
    import yfinance as yf

    CACHE_DIR = "cache/prices"

    os.makedirs(
        CACHE_DIR,
        exist_ok=True
    )

    try:

        recommendation_date = (
            pd.to_datetime(
                recommendation_date
            )
            .normalize()
        )

        if today is None:

            today = (
                pd.Timestamp.today()
                .normalize()
            )

        if today <= recommendation_date:

            return pd.Series(
                dtype=float
            )

        cache_file = os.path.join(
            CACHE_DIR,
            f"{ticker}_evaluation.parquet"
        )

        cached = None

        # =================================================
        # Load existing raw evaluation cache
        # =================================================

        if os.path.exists(cache_file):

            try:

                cached = pd.read_parquet(
                    cache_file
                )

                if not cached.empty:

                    cached.index = pd.to_datetime(
                        cached.index
                    ).normalize()

                    cached = (
                        cached
                        .sort_index()
                        .loc[
                            ~cached.index.duplicated(
                                keep="last"
                            )
                        ]
                    )

            except Exception as e:

                print(
                    f"{ticker}: "
                    f"evaluation cache read failed: {e}"
                )

                cached = None

        # =================================================
        # Determine latest cached date
        # =================================================

        latest_cached_date = None

        if (
            cached is not None
            and not cached.empty
        ):

            latest_cached_date = (
                cached.index.max()
            )

        # =================================================
        # Determine whether refresh is required
        # =================================================

        # We deliberately allow today's date to be a
        # non-trading day. Yahoo will simply return the
        # latest available trading session.

        needs_refresh = (
            cached is None
            or cached.empty
            or latest_cached_date < today
        )

        # =================================================
        # Download only when required
        # =================================================

        if needs_refresh:

            if latest_cached_date is not None:

                download_start = (
                    latest_cached_date
                    +
                    pd.Timedelta(days=1)
                )

            else:

                # Need enough history to cover the
                # recommendation date plus all evaluation
                # horizons.

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

            data = yf.download(
                ticker,
                start=download_start,
                end=download_end,
                progress=False,
                auto_adjust=False
            )

            if not data.empty:

                # Flatten yfinance MultiIndex columns.

                if isinstance(
                    data.columns,
                    pd.MultiIndex
                ):

                    data.columns = (
                        data.columns
                        .get_level_values(0)
                    )

                data.index = pd.to_datetime(
                    data.index
                ).normalize()

                data = (
                    data
                    .sort_index()
                    .loc[
                        ~data.index.duplicated(
                            keep="last"
                        )
                    ]
                )

                # -------------------------------------------------
                # Merge RAW OHLCV data only
                # -------------------------------------------------

                if (
                    cached is not None
                    and not cached.empty
                ):

                    cached = pd.concat(
                        [
                            cached,
                            data
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

                # -------------------------------------------------
                # Save RAW price data only
                # -------------------------------------------------

                try:

                    cached.to_parquet(
                        cache_file
                    )

                except Exception as e:

                    print(
                        f"{ticker}: "
                        f"evaluation cache save failed: {e}"
                    )

        # =================================================
        # Validate history
        # =================================================

        if (
            cached is None
            or cached.empty
        ):

            return pd.Series(
                dtype=float
            )

        # =================================================
        # Extract Close
        # =================================================

        close = cached["Close"]

        if isinstance(
            close,
            pd.DataFrame
        ):

            close = close.iloc[:, 0]

        close = (
            close
            .dropna()
            .sort_index()
        )

        # We need the recommendation date and everything
        # after it for trading-day evaluation.

        close = close[
            close.index >= (
                recommendation_date
                -
                pd.Timedelta(days=5)
            )
        ]

        return close

    except Exception as e:

        print(
            f"Historical price error "
            f"{ticker}: {e}"
        )

        return pd.Series(
            dtype=float
        )
# =====================================================
# Trading days elapsed
# =====================================================

def get_trading_days_elapsed(
    close,
    recommendation_date
):
    """
    Return the number of completed trading sessions
    following the recommendation date.

    Example:

        recommendation Friday
        Monday = session 1
        Tuesday = session 2
    """

    try:

        if close is None or close.empty:

            return None


        recommendation_date = (
            pd.to_datetime(
                recommendation_date
            )
            .normalize()
        )


        future_dates = close.index[
            close.index > recommendation_date
        ]


        return len(
            future_dates
        )


    except Exception as e:

        print(
            "Trading-day calculation error:",
            e
        )

        return None


# =====================================================
# Evaluation price
# =====================================================

def get_evaluation_price(
    close,
    recommendation_date,
    days
):
    """
    Return the closing price after exactly `days`
    trading sessions following the recommendation date.

    Day 1 = first trading session after recommendation.
    """

    try:

        if close is None or close.empty:

            return None


        recommendation_date = (
            pd.to_datetime(
                recommendation_date
            )
            .normalize()
        )


        future_prices = close[
            close.index > recommendation_date
        ]


        if len(future_prices) < days:

            return None


        price = future_prices.iloc[
            days - 1
        ]


        return float(
            price
        )


    except Exception as e:

        print(
            f"Evaluation price error: {e}"
        )

        return None


# =====================================================
# Outcome
# =====================================================

def calculate_outcome(
    return_percent
):
    """
    Classify the outcome of a recommendation.

    SUCCESS:
        +5% or better

    FAILED:
        -5% or worse

    FLAT:
        Between -5% and +5%
    """

    if return_percent >= 5:

        return "SUCCESS"


    elif return_percent <= -5:

        return "FAILED"


    return "FLAT"


# =====================================================
# Main evaluation engine
# =====================================================

def calculate_evaluations(
    recommendations
):
    """
    Evaluate recommendation performance at:

        5 trading days
        10 trading days
        20 trading days
        60 trading days

    The function:

        1. Reuses the existing market-data parquet cache.
        2. Loads each ticker only once per run.
        3. Reuses that history for all recommendations
           for the ticker.
        4. Creates one evaluation row per completed
           recommendation/horizon combination.
    """

    print(
        "OUTCOME EVALUATION START"
    )


    # -------------------------------------------------
    # Clear run-level cache
    # -------------------------------------------------

    PRICE_HISTORY_CACHE.clear()


    # -------------------------------------------------
    # No recommendations
    # -------------------------------------------------

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


    # =================================================
    # Identify unique tickers
    # =================================================

    tickers = set()


    for _, row in recommendations.iterrows():

        ticker = str(
            row.get(
                "ticker",
                ""
            )
        ).upper().strip()


        if ticker:

            tickers.add(
                ticker
            )


    print(
        "UNIQUE EVALUATION TICKERS:",
        len(tickers)
    )


    # =================================================
    # Load price history once per ticker
    # =================================================
    #
    # IMPORTANT:
    #
    # This is now the only loading phase.
    #
    # Each ticker calls get_stock_data() once.
    #
    # If the parquet cache is valid:
    #
    #     ticker: loaded from cache
    #
    # No Yahoo download occurs.
    # =================================================

    for ticker in sorted(
        tickers
    ):

        print(
            f"Loading price history: {ticker}"
        )


        close = load_price_history(
            ticker,
            None,
            today
        )


        if close is None or close.empty:

            print(
                f"{ticker}: "
                f"historical price data unavailable"
            )


    print(
        "PRICE HISTORY CACHE COMPLETE:",
        len(PRICE_HISTORY_CACHE),
        "tickers"
    )


    # =================================================
    # Process recommendations
    # =================================================

    for _, row in recommendations.iterrows():

        ticker = str(
            row.get(
                "ticker",
                ""
            )
        ).upper().strip()


        print(
            "Evaluating",
            ticker
        )


        try:

            # -----------------------------------------
            # Recommendation ID
            # -----------------------------------------

            recommendation_id = row.get(
                "id"
            )


            # -----------------------------------------
            # Recommendation date
            # -----------------------------------------

            recommendation_date = pd.to_datetime(
                row.get(
                    "date"
                ),
                errors="coerce"
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


            # -----------------------------------------
            # Price history from run-level cache
            # -----------------------------------------

            close = PRICE_HISTORY_CACHE.get(
                ticker,
                pd.Series(
                    dtype=float
                )
            )


            if close is None or close.empty:

                print(
                    f"{ticker}: "
                    f"historical price data unavailable"
                )

                continue


            # -----------------------------------------
            # Trading sessions elapsed
            # -----------------------------------------

            trading_days_elapsed = (
                get_trading_days_elapsed(
                    close,
                    recommendation_date
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


            # -----------------------------------------
            # Starting price
            # -----------------------------------------

            start_price = row.get(
                "price",
                0
            )


            try:

                start_price = float(
                    start_price
                )

            except Exception:

                print(
                    f"{ticker}: "
                    f"invalid starting price"
                )

                continue


            if start_price <= 0:

                print(
                    f"{ticker}: "
                    f"invalid starting price "
                    f"{start_price}"
                )

                continue


            # =========================================
            # Evaluation horizons
            # =========================================

            for horizon in EVALUATION_HORIZONS:

                # -------------------------------------
                # Not enough trading sessions
                # -------------------------------------

                if trading_days_elapsed < horizon:

                    print(
                        f"{ticker}: "
                        f"{horizon}-trading-day "
                        f"evaluation not ready yet "
                        f"({trading_days_elapsed}/"
                        f"{horizon} sessions)"
                    )

                    continue


                # -------------------------------------
                # Evaluation price
                # -------------------------------------

                evaluation_price = (
                    get_evaluation_price(
                        close,
                        recommendation_date,
                        horizon
                    )
                )


                if evaluation_price is None:

                    print(
                        f"{ticker}: "
                        f"{horizon}-trading-day "
                        f"price unavailable"
                    )

                    continue


                # -------------------------------------
                # Return
                # -------------------------------------

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

                    2

                )


                # -------------------------------------
                # Outcome
                # -------------------------------------

                outcome = calculate_outcome(
                    return_percent
                )


                # -------------------------------------
                # Evaluation date
                # -------------------------------------

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


                # -------------------------------------
                # Store evaluation
                # -------------------------------------

                evaluations.append(

                    {

                        "recommendation_id":
                            recommendation_id,

                        "ticker":
                            ticker,

                        "signal":
                            row.get(
                                "signal",
                                ""
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
                                4
                            ),

                        "evaluation_price":
                            round(
                                evaluation_price,
                                4
                            ),

                        "return_percent":
                            return_percent,

                        "outcome":
                            outcome,

                        "investment_score":
                            row.get(
                                "investment_score",
                                0
                            ),

                        "technical_score":
                            row.get(
                                "technical_score",
                                0
                            ),

                        "quality_score":
                            row.get(
                                "quality_score",
                                0
                            ),

                        "growth_score":
                            row.get(
                                "growth_score",
                                0
                            ),

                        "confidence_score":
                            row.get(
                                "confidence_score",
                                0
                            )

                    }

                )


                print(
                    f"DEBUG EVALUATION "
                    f"{ticker} "
                    f"{horizon} days "
                    f"{return_percent:.2f}% "
                    f"{outcome}"
                )


        except Exception as e:

            print(
                f"Evaluation error "
                f"{ticker}: {e}"
            )

            continue


    # =================================================
    # Create DataFrame
    # =================================================

    if not evaluations:

        print(
            "NO EVALUATIONS CREATED"
        )

        return pd.DataFrame()


    df = pd.DataFrame(
        evaluations
    )


    # =================================================
    # Final ordering
    # =================================================

    if not df.empty:

        sort_columns = [
            column
            for column in [
                "recommendation_date",
                "ticker",
                "days_after"
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


    print(
        "EVALUATIONS CREATED:",
        df.shape
    )


    return df