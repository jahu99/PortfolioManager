import pandas as pd
import yfinance as yf


def get_last_trading_day(
    ticker="SPY",
    reference_date=None
):
    """
    Returns the most recent trading day
    on or before reference_date.

    Uses SPY as market calendar proxy.
    """

    if reference_date is None:

        reference_date = pd.Timestamp.today()


    reference_date = pd.to_datetime(
        reference_date
    )


    data = yf.download(
        ticker,
        start=(
            reference_date
            -
            pd.Timedelta(days=10)
        ),
        end=(
            reference_date
            +
            pd.Timedelta(days=1)
        ),
        progress=False,
        auto_adjust=False
    )


    if data.empty:

        return None


    trading_dates = data.index


    valid_dates = trading_dates[
        trading_dates <= reference_date
    ]


    if len(valid_dates) == 0:

        return None


    return valid_dates[-1].strftime(
        "%Y-%m-%d"
    )



def get_next_trading_day(
    ticker="SPY",
    reference_date=None
):
    """
    Returns first trading day
    after reference_date.
    """

    if reference_date is None:

        reference_date = pd.Timestamp.today()


    reference_date = pd.to_datetime(
        reference_date
    )


    data = yf.download(
        ticker,
        start=reference_date,
        end=(
            reference_date
            +
            pd.Timedelta(days=10)
        ),
        progress=False,
        auto_adjust=False
    )


    if data.empty:

        return None


    trading_dates = data.index


    future_dates = trading_dates[
        trading_dates > reference_date
    ]


    if len(future_dates) == 0:

        return None


    return future_dates[0].strftime(
        "%Y-%m-%d"
    )