import yfinance as yf
import pandas as pd
import os
from datetime import datetime, timedelta


# =================================
# Historical price cache
# =================================

CACHE_DIR = "data/cache/prices"

CACHE_MAX_AGE_DAYS = 30



# =================================
# Helpers
# =================================

def clean_yfinance_dataframe(df):

    if isinstance(
        df.columns,
        pd.MultiIndex
    ):

        df.columns = (
            df.columns
            .get_level_values(0)
        )

    return df



def extract_close_price(df):

    close = df["Close"]

    if isinstance(
        close,
        pd.DataFrame
    ):

        close = close.iloc[:,0]


    return float(
        close.iloc[-1]
    )



# =================================
# Historical stock data
# =================================

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
    # Load historical cache
    # -----------------------------

    if cache_is_fresh(
        cache_file
    ):


        try:

            return pd.read_pickle(
                cache_file
            )


        except Exception:

            pass



    print(
        f"Downloading historical data {ticker}"
    )



    try:

        df = yf.download(
            ticker,
            period="2y",
            progress=False,
            auto_adjust=False
        )


        if df.empty:

            return pd.DataFrame()



        df = clean_yfinance_dataframe(
            df
        )


        df.to_pickle(
            cache_file
        )


        return df



    except Exception as e:


        print(
            f"Historical download error {ticker}: {e}"
        )


        return pd.DataFrame()



# =================================
# LIVE PRICE
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



        df = clean_yfinance_dataframe(
            df
        )


        price = extract_close_price(
            df
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



        target_date = pd.to_datetime(
            target_date
        )


        df.index = pd.to_datetime(
            df.index
        )


        prices = df[
            df.index >= target_date
        ]



        if prices.empty:

            return None



        price = prices["Close"].iloc[0]


        if isinstance(
            price,
            pd.Series
        ):

            price = price.iloc[0]


        return float(price)



    except Exception as e:


        print(
            f"Historical price error {ticker}: {e}"
        )


        return None



# =================================
# PRICE AFTER N BUSINESS DAYS
# =================================

def get_price_after_days(
    ticker,
    start_date,
    days
):


    try:


        start = pd.to_datetime(
            start_date
        )


        target_date = (
            start
            +
            pd.offsets.BDay(days)
        )



        if target_date > pd.Timestamp.today():

            print(
                f"{ticker}: {days} trading days unavailable yet"
            )

            return None



        df = get_stock_data(
            ticker
        )


        if df.empty:

            return None



        df.index = pd.to_datetime(
            df.index
        )



        prices = df[
            df.index >= target_date
        ]



        if prices.empty:

            return None



        price = prices["Close"].iloc[0]


        if isinstance(
            price,
            pd.Series
        ):

            price = price.iloc[0]


        return float(price)



    except Exception as e:


        print(
            f"Price lookup error {ticker}: {e}"
        )


        return None



# =================================
# Historical cache validation
# =================================

def cache_is_fresh(
    cache_file
):


    if not os.path.exists(
        cache_file
    ):

        return False



    modified_time = datetime.fromtimestamp(
        os.path.getmtime(
            cache_file
        )
    )


    age = (
        datetime.now()
        -
        modified_time
    )


    return age < timedelta(
        days=CACHE_MAX_AGE_DAYS
    )