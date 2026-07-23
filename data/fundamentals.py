import json
import os
import yfinance as yf


CACHE_DIR = "data/cache/fundamentals"



def get_fundamentals(ticker):

    os.makedirs(
        CACHE_DIR,
        exist_ok=True
    )


    cache_file = os.path.join(
        CACHE_DIR,
        f"{ticker}.json"
    )


    if os.path.exists(cache_file):

        with open(cache_file) as f:

            return json.load(f)



    print(
        f"Getting fundamentals {ticker}"
    )


    stock = yf.Ticker(
        ticker
    )


    info = stock.info



    fundamentals = {

        "Revenue Growth":
            info.get(
                "revenueGrowth",
                0
            ),

        "Profit Margin":
            info.get(
                "profitMargins",
                0
            ),

        "Return on Equity":
            info.get(
                "returnOnEquity",
                0
            ),

        "Debt to Equity":
            info.get(
                "debtToEquity",
                0
            ),

        "Sector":
            info.get(
                "sector",
                "Unknown"
            ),

        "Industry":
            info.get(
                "industry",
                "Unknown"
            )

    }



    with open(
        cache_file,
        "w"
    ) as f:

        json.dump(
            fundamentals,
            f
        )


    return fundamentals