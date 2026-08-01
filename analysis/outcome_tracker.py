import pandas as pd

from datetime import datetime

from data.market_data import get_price_after_days


EVALUATION_HORIZONS = [
    5,
    10,
    20,
    60
]


# -------------------------------------------------
# Calculate recommendation evaluations
# -------------------------------------------------

def calculate_evaluations(recommendations):

    print(
        "OUTCOME EVALUATION START"
    )


    if (
        recommendations is None
        or recommendations.empty
    ):

        return pd.DataFrame()



    evaluations = []



    for _, row in recommendations.iterrows():

        try:


            recommendation_id = row["id"]

            ticker = row["ticker"]

            start_price = float(
                row["price"]
            )

            recommendation_date = row["date"]



            rec_date = datetime.strptime(
                recommendation_date,
                "%Y-%m-%d"
            )


            age = (
                datetime.today()
                -
                rec_date
            ).days



            # -----------------------------------------
            # Evaluate each investment horizon
            # -----------------------------------------

            for horizon in EVALUATION_HORIZONS:


                if age < horizon:

                    continue



                evaluation_price = get_price_after_days(
                    ticker,
                    recommendation_date,
                    horizon
                )


                if evaluation_price is None:

                    continue



                evaluation_price = float(
                    evaluation_price
                )



                return_pct = round(
                    (
                        (
                            evaluation_price
                            -
                            start_price
                        )
                        /
                        start_price
                    )
                    *
                    100,
                    2
                )



                if return_pct >= 5:

                    outcome = "SUCCESS"


                elif return_pct <= -5:

                    outcome = "FAILED"


                else:

                    outcome = "FLAT"



                print(
                    "DEBUG EVALUATION:",
                    ticker,
                    "Horizon:",
                    horizon,
                    "Start:",
                    start_price,
                    "End:",
                    evaluation_price,
                    "Return:",
                    return_pct
                )



                evaluations.append(

                    {

                        # -------------------------
                        # Database fields
                        # -------------------------

                        "recommendation_id":
                            recommendation_id,


                        "ticker":
                            ticker,


                        "evaluation_date":
                            datetime.today()
                            .strftime("%Y-%m-%d"),


                        "days_after":
                            horizon,


                        "price":
                            evaluation_price,


                        "return_percent":
                            return_pct,


                        "outcome":
                            outcome,



                        # -------------------------
                        # Learning fields
                        # -------------------------

                        "Signal":
                            row.get(
                                "signal",
                                ""
                            ),


                        "Investment Score":
                            row.get(
                                "investment_score",
                                0
                            ),


                        "Technical Score":
                            row.get(
                                "technical_score",
                                0
                            ),


                        "Quality Score":
                            row.get(
                                "quality_score",
                                0
                            )

                    }

                )



        except Exception as e:


            print(
                f"EVALUATION ERROR {row.get('ticker')}: {e}"
            )

            import traceback
            traceback.print_exc()



    if not evaluations:

        return pd.DataFrame()



    df = pd.DataFrame(
        evaluations
    )



    print(
        "EVALUATIONS CREATED:",
        len(df)
    )



    return df