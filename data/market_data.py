import os
import math
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
    Return the latest trading date containing a usable Close price.

    A row may exist for the current trading session while the daily
    candle is still incomplete. Such a row must not be treated as
    the latest completed market observation.

    The Close price is the minimum requirement because the technical
    indicator pipeline depends on it.
    """
    if df is None or df.empty:
        return None

    try:
        if "Close" not in df.columns:
            return None

        usable = df.loc[
            pd.to_numeric(
                df["Close"],
                errors="coerce"
            ).notna()
        ]

        if usable.empty:
            return None

        index = pd.to_datetime(
            usable.index
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


def _ohlc_is_valid(df, observation_date=None):
    """
    Validate OHLC values for a specific completed observation.
    """

    required_columns = [
        "Open",
        "High",
        "Low",
        "Close",
    ]

    if df is None or df.empty:
        return False

    if not all(
        column in df.columns
        for column in required_columns
    ):
        return False

    try:
        index_dates = pd.to_datetime(df.index).date

        if observation_date is not None:
            mask = [
                date == observation_date
                for date in index_dates
            ]

            rows = df.loc[mask]

            if rows.empty:
                return False

            row = rows.iloc[-1]

        else:
            row = df.iloc[-1]

        values = {}

        for column in required_columns:
            value = pd.to_numeric(
                pd.Series([row[column]]),
                errors="coerce"
            ).iloc[0]

            if pd.isna(value):
                return False

            value = float(value)

            if not math.isfinite(value) or value <= 0:
                return False

            values[column] = value

        if not (
            values["High"] >= max(
                values["Open"],
                values["Close"]
            )
            and
            values["Low"] <= min(
                values["Open"],
                values["Close"]
            )
            and
            values["High"] >= values["Low"]
        ):
            return False

        return True

    except (TypeError, ValueError, IndexError, KeyError):
        return False


def _cache_is_current(df):
    """
    Require the latest completed US trading session
    and a structurally valid OHLC observation.
    """

    cached_date = _latest_cached_date(df)

    if cached_date is None:
        return False

    expected_date = (
        _latest_completed_us_trading_date()
    )

    if cached_date < expected_date:
        return False

    return _ohlc_is_valid(
        df,
        observation_date=expected_date
    )


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
            if not force_refresh and os.path.exists(cache_file):

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
        # VALIDATE AND SAVE RAW DATA
        # ====================================================

        expected_date = (
            _latest_completed_us_trading_date()
        )

        if not _ohlc_is_valid(
            df,
            observation_date=expected_date
        ):
            print(
                f"{ticker}: DATA_QUALITY_FAILURE - "
                f"invalid or incomplete OHLC data "
                f"for {expected_date}; "
                f"existing cache preserved."
            )

            if not force_refresh and os.path.exists(cache_file):
                try:
                    cached = pd.read_parquet(
                        cache_file
                    )

                    if not cached.empty:
                        return cached

                except Exception:
                    pass

            return pd.DataFrame()

        # Only cache datasets large enough to support the
        # technical indicators used by the application.

        if len(df) >= 200:

            temp_cache_file = (
                cache_file + ".tmp.parquet"
            )

            try:
                df.to_parquet(
                    temp_cache_file
                )

                os.replace(
                    temp_cache_file,
                    cache_file
                )

                latest_date = (
                    _latest_cached_date(df)
                )

                print(
                    f"{ticker}: "
                    f"FRESH_DOWNLOAD_VALIDATED "
                    f"(latest: {latest_date})"
                )

            except Exception as e:

                if os.path.exists(temp_cache_file):
                    os.remove(temp_cache_file)

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

        if not force_refresh and os.path.exists(cache_file):

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