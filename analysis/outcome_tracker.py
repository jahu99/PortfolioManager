import pandas as pd

from data.market_data import get_stock_data



def calculate_outcomes(
    recommendations
):

    outcomes = []


    if (
        recommendations is None
        or recommendations.empty
    ):

        return pd.DataFrame()



    for _, row in recommendations.iterrows():

        ticker = row["ticker"]


        try:

            df = get_stock_data(
                ticker
            )


            if df.empty:
                continue



            latest = df.iloc[-1]


            current_price = float(
                latest["Close"]
            )


            start_price = float(
                row["price"]
            )



            if start_price <= 0:
                continue



            return_percent = (

                (
                    current_price
                    -
                    start_price
                )
                /
                start_price

            ) * 100



            outcomes.append(
                {

                    "Ticker":
                        ticker,

                    "Signal":
                        row["signal"],

                    "Investment Score":
                        row["investment_score"],

                    "Start Price":
                        start_price,

                    "Current Price":
                        round(
                            current_price,
                            2
                        ),

                    "Return %":
                        round(
                            return_percent,
                            2
                        ),

                    "Check Date":
                        pd.Timestamp.now().strftime(
                            "%Y-%m-%d"
                        )

                }
            )



        except Exception as e:

            print(
                f"Outcome error {ticker}: {e}"
            )



    return pd.DataFrame(
        outcomes
    )