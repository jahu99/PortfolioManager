import os
import json


STATIC_CACHE = "data/cache/company_static.json"

MIN_MARKET_CAP = 300_000_000


# -------------------------------------------------------
# Load static company metadata
# -------------------------------------------------------

def load_company_static():

    if not os.path.exists(STATIC_CACHE):

        raise FileNotFoundError(
            "company_static.json missing"
        )

    with open(
        STATIC_CACHE,
        "r"
    ) as f:

        data = json.load(f)


    companies = data.get(
        "companies",
        {}
    )


    print(
        f"Company static cache loaded: {len(companies)}"
    )


    return companies



# -------------------------------------------------------
# Static investability rules
# -------------------------------------------------------

def check_static_filters(
    ticker,
    static_data
):

    info = static_data.get(
        ticker
    )


    if info is None:
        return False


    # Must be normal equity

    if info.get(
        "quoteType",
        ""
    ) != "EQUITY":

        return False


    # Must have exchange

    if info.get(
        "exchange",
        ""
    ) == "":

        return False



    # Must have market cap

    if info.get(
        "marketCap",
        0
    ) < MIN_MARKET_CAP:

        return False


    return True



# -------------------------------------------------------
# Public filter
# -------------------------------------------------------

def filter_investable_universe(
    tickers
):


    print(
        "\nSTARTING STATIC INVESTABILITY FILTER"
    )


    print(
        f"Input universe: {len(tickers)}"
    )


    companies = load_company_static()


    candidates = []


    for i, ticker in enumerate(
        tickers,
        start=1
    ):


        print(
            f"Filtering {i}/{len(tickers)} {ticker}"
        )


        try:


            if check_static_filters(
                ticker,
                companies
            ):

                candidates.append(
                    ticker
                )


        except Exception as e:

            print(
                f"{ticker}: filter error {e}"
            )



    print(
        "\nSTATIC FILTER COMPLETE"
    )


    print(
        f"Removed: {len(tickers)-len(candidates)}"
    )


    print(
        f"Investable candidates: {len(candidates)}"
    )


    return candidates