import pandas as pd
import os


def get_sp500_universe():

    """
    Loads S&P 500 tickers from local CSV.
    """

    file_path = os.path.join(
        os.path.dirname(__file__),
        "sp500.csv"
    )


    try:

        df = pd.read_csv(
            file_path
        )


        tickers = df["Ticker"].tolist()


        print(
            f"Loaded {len(tickers)} stocks from local universe"
        )


        return tickers



    except Exception as e:

        print(
            f"Could not load stock universe: {e}"
        )

        return []