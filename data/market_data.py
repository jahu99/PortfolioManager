import yfinance as yf
import pandas as pd
import os
from datetime import datetime, timedelta


CACHE_DIR = "data/cache/prices"



def get_stock_data(ticker):

    os.makedirs(
        CACHE_DIR,
        exist_ok=True
    )


    cache_file = os.path.join(
        CACHE_DIR,
        f"{ticker}.pkl"
    )


    # -----------------------------
    # Load cache
    # -----------------------------

    if os.path.exists(cache_file):

        try:

            return pd.read_pickle(
                cache_file
            )

        except Exception:

            pass



    # -----------------------------
    # Download historical data
    # -----------------------------

    print(
        f"Downloading historical data {ticker}"
    )


    df = yf.download(
        ticker,
        period="2y",
        progress=False,
        auto_adjust=False
    )


    if df.empty:

        return pd.DataFrame()



    if isinstance(
        df.columns,
        pd.MultiIndex
    ):

        df.columns = (
            df.columns
            .get_level_values(0)
        )



    df.to_pickle(
        cache_file
    )


    return df





# =================================
# LIVE PRICE FOR EVALUATION ENGINE
# =================================

def get_current_price(ticker):


    try:

        print(
            f"Fetching live price {ticker}"
        )


        df = yf.download(
            ticker,
            period="5d",
            progress=False,
            auto_adjust=False
        )


        if df.empty:

            return None



        if isinstance(
            df.columns,
            pd.MultiIndex
        ):

            df.columns = (
                df.columns
                .get_level_values(0)
            )



        price = float(
            df["Close"]
            .iloc[-1]
        )


        return price



    except Exception as e:


        print(
            f"Live price error {ticker}: {e}"
        )


        return None
    
# =================================
# HISTORICAL PRICE LOOKUP
# =================================

def get_price_on_date(
    ticker,
    target_date
):

    try:

        df = get_stock_data(
            ticker
        )

        if df.empty:

            return None

        if isinstance(
            target_date,
            str
        ):

            target_date = pd.to_datetime(
                target_date
            )

        # Ensure index is datetime
        df.index = pd.to_datetime(
            df.index
        )

        # Find first trading day
        future_prices = df[
            df.index >= target_date
        ]

        if future_prices.empty:

            return None

        return float(
            future_prices["Close"]
            .iloc[0]
        )

    except Exception as e:

        print(
            f"Historical price error {ticker}: {e}"
        )

        return None



# =================================
# PRICE AFTER N DAYS
# =================================

def get_price_after_days(
    ticker,
    recommendation_date,
    days_after
):

    if isinstance(
        recommendation_date,
        str
    ):

        recommendation_date = pd.to_datetime(
            recommendation_date
        )

    evaluation_date = (
        recommendation_date
        +
        timedelta(days=days_after)
    )

    return get_price_on_date(
        ticker,
        evaluation_date
    )