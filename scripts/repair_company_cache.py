import json
import time
import yfinance as yf


CACHE_FILE = "data/cache/company_static.json"

BATCH_SIZE = 25
SLEEP_SECONDS = 2


def load_cache():

    with open(CACHE_FILE, "r") as f:
        return json.load(f)



def save_cache(data):

    with open(CACHE_FILE, "w") as f:
        json.dump(
            data,
            f,
            indent=4
        )



def is_bad_record(company):

    return (
        company.get("marketCap", 0) == 0
        or company.get("quoteType", "") != "EQUITY"
        or company.get("exchange", "") == ""
    )



data = load_cache()

companies = data["companies"]


bad = [
    ticker
    for ticker, company in companies.items()
    if is_bad_record(company)
]


print(
    f"Bad records found: {len(bad)}"
)


fixed = 0


for start in range(
    0,
    len(bad),
    BATCH_SIZE
):

    batch = bad[start:start+BATCH_SIZE]


    print(
        f"\nRepair batch {start+1}-{start+len(batch)}"
    )


    for ticker in batch:

        old = companies[ticker]


        try:

            print(
                f"Refreshing {ticker}"
            )


            stock = yf.Ticker(
                ticker
            )


            market_cap = 0
            exchange = ""
            quote_type = ""
            sector = old.get(
                "sector",
                "Unknown"
            )
            industry = old.get(
                "industry",
                "Unknown"
            )


            # ----------------------------
            # Fast metadata first
            # ----------------------------

            try:

                fast = stock.fast_info


                market_cap = fast.get(
                    "market_cap",
                    0
                )

                exchange = fast.get(
                    "exchange",
                    ""
                )


            except Exception:

                pass



            # ----------------------------
            # Detailed metadata fallback
            # ----------------------------

            try:

                info = stock.info


                sector = info.get(
                    "sector",
                    sector
                )

                industry = info.get(
                    "industry",
                    industry
                )

                quote_type = info.get(
                    "quoteType",
                    ""
                )


                if not market_cap:

                    market_cap = info.get(
                        "marketCap",
                        0
                    )


                if not exchange:

                    exchange = info.get(
                        "exchange",
                        ""
                    )


            except Exception:

                pass



            # ----------------------------
            # Only save valid updates
            # ----------------------------

            if (
                market_cap
                and exchange
            ):

                companies[ticker] = {

                    "sector":
                        sector,

                    "industry":
                        industry,

                    "marketCap":
                        market_cap,

                    "quoteType":
                        quote_type
                        or "EQUITY",

                    "exchange":
                        exchange
                }


                fixed += 1

                print(
                    f"{ticker}: FIXED"
                )


            else:

                print(
                    f"{ticker}: no valid data - keeping existing"
                )


        except Exception as e:

            print(
                f"{ticker}: FAILED {e}"
            )


        time.sleep(
            SLEEP_SECONDS
        )


    save_cache(
        data
    )


    print(
        "Batch saved"
    )



print(
    f"\nRepair complete. Fixed: {fixed}"
)