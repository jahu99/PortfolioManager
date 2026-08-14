import os
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf


CACHE_DIR = "cache/prices"

os.makedirs(
    CACHE_DIR,
    exist_ok=True
)


# ============================================================
# CACHE HELPERS
# ============================================================

def _cache_file(ticker, period):
    """
    Return the cache filename for a ticker/period combination.
    """

    safe_ticker = str(ticker).upper().strip()

    return os.path.join(
        CACHE_DIR,
        f"{safe_ticker}_{period}.parquet"
    )


def _latest_cached_date(df):
    """
    Return the latest trading date contained in cached data.
    """

    if df is None or df.empty:
        return None

    try:

        index = pd.to_datetime(
            df.index
        )

        return index.max().date()

    except Exception:

        return None


def _latest_completed_us_trading_date():
    """
    Determine the latest date for which a completed US daily
    market candle should be available.

    Before the US session has completed, the latest valid daily
    candle is the previous US trading day.

    This deliberately does NOT use the local file modification
    time as the definition of freshness.
    """

    now = datetime.now()

    # --------------------------------------------------------
    # Convert current UK/local time approximately into the
    # US market schedule.
    #
    # The exact DST handling is deliberately conservative:
    # we only consider today's US session complete after
    # approximately 22:30 UK time.
    #
    # The agent's important morning run is before 14:30 UK,
    # so the previous completed US session is used.
    # --------------------------------------------------------

    current_date = now.date()

    # Before US market close:
    # today's daily candle is not considered complete.
    if now.hour < 22:

        candidate = current_date - timedelta(
            days=1
        )

    else:

        candidate = current_date

    # --------------------------------------------------------
    # Walk backwards over weekends.
    #
    # Monday morning -> Friday
    # Sunday -> Friday
    # Saturday -> Friday
    # --------------------------------------------------------

    while candidate.weekday() >= 5:

        candidate -= timedelta(
            days=1
        )

    return candidate


def _cache_is_current(df):
    """
    Determine whether cached data contains the latest completed
    US trading session.
    """

    cached_date = _latest_cached_date(
        df
    )

    if cached_date is None:
        return False

    latest_expected_date = (
        _latest_completed_us_trading_date()
    )

    return cached_date >= latest_expected_date


# ============================================================
# MARKET DATA
# ============================================================

def get_stock_data(
    ticker,
    period="1y",
    force_refresh=False
):

    """
    Get historical OHLCV data.

    Cache behaviour:

        First run of the day:
            Download fresh data if Yahoo has a newer completed
            daily candle than the cache.

        Subsequent intraday runs:
            Reuse the cached raw market data.

        force_refresh=True:
            Always download fresh data.

    Important:
        Only raw OHLCV data is cached.

        Indicators, scores, signals and recommendations are
        recalculated on every run from the raw data.
    """

    ticker = str(
        ticker
    ).upper().strip()

    cache_file = _cache_file(
        ticker,
        period
    )

    # ========================================================
    # LOAD CACHE
    # ========================================================

    if (
        os.path.exists(cache_file)
        and not force_refresh
    ):

        try:

            df = pd.read_parquet(
                cache_file
            )

            # ------------------------------------------------
            # Use cache only if it contains the latest
            # completed US trading session.
            # ------------------------------------------------

            if _cache_is_current(df):

                cached_date = (
                    _latest_cached_date(df)
                )

                print(
                    f"{ticker}: "
                    f"loaded from cache "
                    f"(latest data: {cached_date})"
                )

                return df

            else:

                cached_date = (
                    _latest_cached_date(df)
                )

                expected_date = (
                    _latest_completed_us_trading_date()
                )

                print(
                    f"{ticker}: "
                    f"cache stale "
                    f"(cached: {cached_date}, "
                    f"expected: {expected_date})"
                )

        except Exception as e:

            print(
                f"{ticker}: "
                f"cache read failed: {e}"
            )

    # ========================================================
    # DOWNLOAD FRESH DATA
    # ========================================================

    print(
        f"Downloading fresh market data: {ticker}"
    )

    try:

        df = yf.download(
            ticker,
            period=period,
            interval="1d",
            auto_adjust=False,
            progress=False
        )

        if df is None or df.empty:

            print(
                f"{ticker}: Yahoo returned no data"
            )

            # If fresh download fails but a cache exists,
            # use the cache rather than losing the stock.
            if os.path.exists(cache_file):

                try:

                    cached = pd.read_parquet(
                        cache_file
                    )

                    if not cached.empty:

                        print(
                            f"{ticker}: "
                            f"using existing cache "
                            f"after Yahoo failure"
                        )

                        return cached

                except Exception:
                    pass

            return pd.DataFrame()

        # ====================================================
        # NORMALISE YFINANCE COLUMNS
        # ====================================================

        if isinstance(
            df.columns,
            pd.MultiIndex
        ):

            df.columns = (
                df.columns
                .get_level_values(0)
            )

        # ----------------------------------------------------
        # Remove rows containing no usable market data.
        # ----------------------------------------------------

        df = df.dropna(
            how="all"
        )

        if df.empty:

            return pd.DataFrame()

        # ====================================================
        # NORMALISE INDEX
        # ====================================================

        try:

            df.index = pd.to_datetime(
                df.index
            )

        except Exception:
            pass

        # ====================================================
        # SAVE RAW DATA
        # ====================================================

        try:

            # Only cache datasets large enough to support the
            # technical indicators used by the application.
            if len(df) >= 200:

                df.to_parquet(
                    cache_file
                )

                latest_date = (
                    _latest_cached_date(df)
                )

                print(
                    f"{ticker}: "
                    f"fresh data cached "
                    f"(latest: {latest_date})"
                )

        except Exception as e:

            print(
                f"{ticker}: "
                f"cache save failed: {e}"
            )

        return df

    # ========================================================
    # ERROR HANDLING
    # ========================================================

    except Exception as e:

        print(
            f"Market data error "
            f"{ticker}: {e}"
        )

        # ----------------------------------------------------
        # If Yahoo fails because of rate limiting or a
        # temporary network problem, fall back to the cache.
        #
        # This protects the scanner from completely failing,
        # while still preferring fresh data whenever Yahoo is
        # available.
        # ----------------------------------------------------

        if os.path.exists(cache_file):

            try:

                cached = pd.read_parquet(
                    cache_file
                )

                if not cached.empty:

                    print(
                        f"{ticker}: "
                        f"Yahoo download failed - "
                        f"using existing cache"
                    )

                    return cached

            except Exception:
                pass

        return pd.DataFrame()