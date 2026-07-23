import yfinance as yf
import pandas as pd
import os


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
    # Download
    # -----------------------------

    print(
        f"Downloading {ticker}"
    )


    df = yf.download(
        ticker,
        period="2y",
        progress=False,
        auto_adjust=False
    )


    if df.empty:

        return pd.DataFrame()



    # Handle yfinance multi columns

    if isinstance(
        df.columns,
        pd.MultiIndex
    ):

        df.columns = (
            df.columns
            .get_level_values(0)
        )



    # Save cache

    df.to_pickle(
        cache_file
    )


    return df