import json
import os
import yfinance as yf


CACHE_DIR = "data/cache/fundamentals"

FUNDAMENTALS_CACHE_VERSION = 2


def get_fundamentals(ticker):

    os.makedirs(
        CACHE_DIR,
        exist_ok=True
    )

    cache_file = os.path.join(
        CACHE_DIR,
        f"{ticker}.json"
    )

    # ---------------------------------------------------------
    # Fundamentals cache
    #
    # Version 2 adds valuation telemetry.
    # Existing version 1 caches are refreshed once so that
    # valuation data is populated.
    # ---------------------------------------------------------

    if os.path.exists(cache_file):

        try:

            with open(cache_file) as f:

                cached_fundamentals = json.load(f)

            if (
                cached_fundamentals.get(
                    "_fundamentals_cache_version"
                )
                == FUNDAMENTALS_CACHE_VERSION
            ):

                return cached_fundamentals

        except (
            OSError,
            json.JSONDecodeError,
            TypeError,
            AttributeError
        ):

            pass

    print(
        f"Getting fundamentals {ticker}"
    )

    stock = yf.Ticker(
        ticker
    )

    info = stock.info

    fundamentals = {

        "_fundamentals_cache_version":
            FUNDAMENTALS_CACHE_VERSION,

        "Name":
            info.get(
                "longName",
                info.get(
                    "shortName",
                    ticker
                )
            ),

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
            ),

        # -----------------------------------------------------
        # Valuation telemetry
        #
        # These values are observational only at this stage.
        # They do NOT affect Quality, Growth, Investment Score
        # or portfolio decisions.
        # -----------------------------------------------------

        "PE Ratio":
            info.get(
                "trailingPE"
            ),

        "Forward PE":
            info.get(
                "forwardPE"
            ),

        "PEG Ratio":
            info.get(
                "pegRatio"
            ),

        "Price to Sales":
            info.get(
                "priceToSalesTrailing12Months"
            ),

        "EV to EBITDA":
            info.get(
                "enterpriseToEbitda"
            ),

        "Free Cash Flow":
            info.get(
                "freeCashflow"
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