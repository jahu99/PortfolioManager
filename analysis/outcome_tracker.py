import pandas as pd
from datetime import datetime

from data.market_data import get_stock_data



EVALUATION_PERIODS = [
    5,
    21,
    63
]



def calculate_evaluations(
    recommendations
):


    evaluations = []


    if (
        recommendations is None
        or recommendations.empty
    ):

        return pd.DataFrame()



    today = pd.Timestamp.now()



    for _, row in recommendations.iterrows():


        try:

            recommendation_date = pd.to_datetime(
                row["date"]
            )


            calendar_days_elapsed = (
                today - recommendation_date
            ).days



            ticker = row["ticker"]



            # ---------------------------------
            # Check evaluation milestones
            # ---------------------------------

            for period in EVALUATION_PERIODS:


                if calendar_days_elapsed < period:
                    continue



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



                if return_percent > 0.5:

                    outcome = "WIN"


                elif return_percent < -0.5:

                     outcome = "LOSS"


                else:

                    outcome = "FLAT"



                evaluations.append(
                    {

                        "recommendation_id":
                            row["id"],


                        "ticker":
                            ticker,


                        "signal":
                            row["signal"],


                        "evaluation_date":
                            today.strftime(
                                "%Y-%m-%d"
                            ),


                        "days_after":
                            period,


                        "price":
                            round(
                                current_price,
                                2
                            ),


                        "return_percent":
                            round(
                                return_percent,
                                2
                            ),


                        "outcome":
                            outcome

                    }
                )



        except Exception as e:


            print(
                f"Evaluation error {row.get('ticker')}: {e}"
            )



    return pd.DataFrame(
        evaluations
    )