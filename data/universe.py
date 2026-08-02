import pandas as pd
import os


BASE_PATH = os.path.dirname(__file__)


# -------------------------------------------------
# S&P 500
# -------------------------------------------------

def get_sp500_universe():

    """
    Loads S&P 500 tickers from local CSV.
    """

    file_path = os.path.join(
        BASE_PATH,
        "sp500.csv"
    )

    try:

        df = pd.read_csv(
            file_path
        )

        tickers = (
            df["Ticker"]
            .dropna()
            .astype(str)
            .tolist()
        )

        print(
            f"Loaded {len(tickers)} stocks from S&P500 universe"
        )

        return tickers


    except Exception as e:

        print(
            f"S&P500 universe error: {e}"
        )

        return []



# -------------------------------------------------
# Nasdaq
# -------------------------------------------------

def get_nasdaq_universe():

    """
    Loads Nasdaq-listed tickers.
    """

    file_path = os.path.join(
        BASE_PATH,
        "nasdaq.csv"
    )


    try:

        df = pd.read_csv(
            file_path
        )


        tickers = (
            df["Ticker"]
            .dropna()
            .astype(str)
            .tolist()
        )


        print(
            f"Loaded {len(tickers)} stocks from Nasdaq universe"
        )


        return tickers



    except Exception as e:

        print(
            f"Nasdaq universe error: {e}"
        )

        return []



# -------------------------------------------------
# User holdings
# -------------------------------------------------

def get_holdings_universe():

    """
    Always include stocks the user owns.
    """

    file_path = os.path.join(
        os.path.dirname(BASE_PATH),
        "portfolio",
        "holdings.csv"
    )


    try:

        df = pd.read_csv(
            file_path
        )


        tickers = (
            df["Ticker"]
            .dropna()
            .astype(str)
            .tolist()
        )


        print(
            f"Loaded {len(tickers)} portfolio holdings"
        )


        return tickers



    except Exception as e:

        print(
            f"Holdings universe error: {e}"
        )

        return []



# -------------------------------------------------
# Combined universe
# -------------------------------------------------

def get_market_universe():

    """
    Combines:

    - S&P500
    - Nasdaq
    - User holdings

    Removes duplicates.
    """


    universe = set()


    universe.update(
        get_sp500_universe()
    )


    universe.update(
        get_nasdaq_universe()
    )


    universe.update(
        get_holdings_universe()
    )


    universe = sorted(
        universe
    )


    print(
        f"TOTAL MARKET UNIVERSE: {len(universe)} stocks"
    )


    return universe