from data.market_data import get_stock_data
from analysis.indicators import add_indicators
from analysis.scorer import score_stock


FAST_MIN_PRICE = 5
FAST_MIN_VOLUME = 250_000

PRICE_PERIOD = "18mo"


def run_market_scan(
    tickers,
    limit=200
):

    print(
        f"MARKET SCAN START: {len(tickers)} tickers"
    )


    fast_candidates = []


    # ---------------------------------
    # STAGE 1 - PRICE / LIQUIDITY FILTER
    # ---------------------------------

    print(
        "STARTING FAST TECHNICAL FILTER"
    )


    for i, ticker in enumerate(
        tickers,
        1
    ):

        if i % 50 == 0:
            print(
                f"Fast scan progress {i}/{len(tickers)}"
            )


        try:

            df = get_stock_data(
                ticker,
                period=PRICE_PERIOD
            )


            if df is None or df.empty:
                continue


            if len(df) < 200:
                continue


            latest = df.iloc[-1]


            price = float(
                latest["Close"]
            )


            avg_volume = float(
                df["Volume"]
                .tail(20)
                .mean()
            )


            if price < FAST_MIN_PRICE:
                continue


            if avg_volume < FAST_MIN_VOLUME:
                continue


            fast_candidates.append(
                ticker
            )


        except Exception as e:

            print(
                f"{ticker} fast filter failed: {e}"
            )



    print(
        f"FAST FILTER COMPLETE: {len(fast_candidates)} candidates"
    )



    # ---------------------------------
    # STAGE 2 - FULL TECHNICAL ANALYSIS
    # ---------------------------------

    candidates = []


    print(
        "STARTING FULL TECHNICAL SCAN"
    )


    for i, ticker in enumerate(
        fast_candidates,
        1
    ):


        if i % 25 == 0:
            print(
                f"Technical scan progress {i}/{len(fast_candidates)}"
            )


        try:


            # Same cached dataset
            df = get_stock_data(
                ticker,
                period=PRICE_PERIOD
            )


            if df is None or df.empty:
                continue


            if len(df) < 200:
                continue



            df = add_indicators(
                df
            )


            score_result = score_stock(
                df
            )


            candidates.append(
                {
                    "Ticker": ticker,

                    "df": df,

                    "Technical Score":
                        score_result.get(
                            "Technical Score",
                            0
                        ),

                    "Score Result":
                        score_result
                }
            )



        except Exception as e:

            print(
                f"{ticker} technical scan failed: {e}"
            )



    # ---------------------------------
    # SORT RESULTS
    # ---------------------------------

    candidates = sorted(
        candidates,
        key=lambda x:
            x.get(
                "Technical Score",
                0
            ),
        reverse=True
    )


    print(
        f"TECHNICAL SCAN COMPLETE: {len(candidates)} candidates"
    )


    print(
        f"RETURNING TOP {limit}"
    )


    return candidates[:limit]