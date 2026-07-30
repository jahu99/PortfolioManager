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