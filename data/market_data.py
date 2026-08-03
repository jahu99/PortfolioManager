import os
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta


CACHE_DIR = "cache/prices"


os.makedirs(
    CACHE_DIR,
    exist_ok=True
)


def get_stock_data(
    ticker,
    period="1y",
    force_refresh=False
):

    """
    Get historical OHLCV data.

    Cache:
        - Raw market prices only

    Do not cache:
        - indicators
        - scores
        - signals
    """


    cache_file = os.path.join(
        CACHE_DIR,
        f"{ticker}_{period}.parquet"
    )


    # ----------------------------------
    # Load cache if available
    # ----------------------------------

    if (
        os.path.exists(cache_file)
        and not force_refresh
    ):

        try:

            df = pd.read_parquet(
                cache_file
            )


            # Refresh if older than 24 hours

            modified = datetime.fromtimestamp(
                os.path.getmtime(cache_file)
            )


            age = datetime.now() - modified


            if age < timedelta(hours=24):
                
                print(
                    f"{ticker}: loaded from cache ({age.seconds//3600}h old)"
                )

                return df


        except Exception:

            pass



    # ----------------------------------
    # Download fresh data
    # ----------------------------------

    print(
        f"Downloading historical data {ticker}"
    )


    try:

        df = yf.download(
            ticker,
            period=period,
            interval="1d",
            auto_adjust=False,
            progress=False
        )


        if df.empty:

            return pd.DataFrame()



        # Flatten yfinance columns

        if isinstance(
            df.columns,
            pd.MultiIndex
        ):

            df.columns = (
                df.columns
                .get_level_values(0)
            )


        df = df.dropna()



        # Save raw data

        try:

            if len(df) >= 200:
                df.to_parquet(cache_file)

        except Exception as e:

            print(
                f"Cache save failed {ticker}: {e}"
            )



        return df



    except Exception as e:

        print(
            f"Market data error {ticker}: {e}"
        )

        return pd.DataFrame()