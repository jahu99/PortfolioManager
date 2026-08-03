import os
import json
import yfinance as yf
from datetime import datetime, timedelta


CACHE_FILE = "data/cache/company_static.json"


# -------------------------------------------------
# Load static company cache
# -------------------------------------------------

def load_company_cache():

    if not os.path.exists(CACHE_FILE):
        return {}

    try:

        with open(CACHE_FILE, "r") as f:
            data = json.load(f)


        cache_date = datetime.strptime(
            data["date"],
            "%Y-%m-%d"
        )


        # Refresh every 30 days
        if datetime.today() - cache_date < timedelta(days=30):

            companies = data.get(
                "companies",
                {}
            )


            print(
                f"Using company static cache: {len(companies)}"
            )


            return companies


    except Exception as e:

        print(
            f"Company cache load error: {e}"
        )


    return {}



# -------------------------------------------------
# Save static company cache
# -------------------------------------------------

def save_company_cache(companies):

    os.makedirs(
        "data/cache",
        exist_ok=True
    )


    data = {

        "date":
            datetime.today().strftime(
                "%Y-%m-%d"
            ),

        "companies":
            companies
    }


    with open(
        CACHE_FILE,
        "w"
    ) as f:

        json.dump(
            data,
            f,
            indent=4
        )


    print(
        f"Company static cache saved: {len(companies)}"
    )



# -------------------------------------------------
# Build static company metadata cache
# -------------------------------------------------

import time


def build_company_static_cache(tickers):

    companies = load_company_cache()


    print(
        f"Existing static cache: {len(companies)}"
    )


    for i, ticker in enumerate(
        tickers,
        start=1
    ):


        # already good
        if (
            ticker in companies
            and companies[ticker].get("marketCap",0) > 0
            and companies[ticker].get("quoteType","") != ""
        ):
            continue


        print(
            f"Static metadata {i}/{len(tickers)} {ticker}"
        )


        try:

            stock = yf.Ticker(
                ticker
            )


            fast = stock.fast_info


            companies[ticker] = {

                "marketCap":
                    float(
                        fast.get(
                            "marketCap",
                            0
                        )
                    ),


                "exchange":
                    fast.get(
                        "exchange",
                        ""
                    ),


                "quoteType":
                    fast.get(
                        "quoteType",
                        ""
                    )

            }


            # slow Yahoo down
            time.sleep(
                0.5
            )


        except Exception as e:


            print(
                f"{ticker}: skipped"
            )


            companies[ticker] = {

                "marketCap":0,

                "exchange":"",

                "quoteType":""

            }


            time.sleep(
                2
            )



        # save every 100 records
        if i % 100 == 0:

            save_company_cache(
                companies
            )


    save_company_cache(
        companies
    )


    return companies