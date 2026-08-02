# analysis/outcome_tracker.py

import pandas as pd

from datetime import datetime

from analysis.recommendation_evaluator import get_price_after_days

EVALUATION_HORIZONS = [
    5,
    10,
    20,
    60
]


def calculate_evaluations(recommendations):

    print(
        "OUTCOME EVALUATION START"
    )


    if (
        recommendations is None
        or recommendations.empty
    ):

        print(
            "NO RECOMMENDATIONS"
        )

        return pd.DataFrame()



    evaluations = []


    today = datetime.today()


    for _, row in recommendations.iterrows():

        ticker = row["ticker"]

        print(
            "Evaluating",
            ticker
        )


        try:

            recommendation_id = row["id"]

            recommendation_date = pd.to_datetime(
                row["date"]
            )


            age_days = (
                today -
                recommendation_date
            ).days



            for horizon in EVALUATION_HORIZONS:


                if age_days < horizon:

                    print(
                        f"{ticker}: {horizon} trading days unavailable yet"
                    )

                    continue



                evaluation_price = get_price_after_days(
                    ticker,
                    recommendation_date,
                    horizon
                )


                if evaluation_price is None:

                    print(
                        f"No price found {ticker} horizon {horizon}"
                    )

                    continue



                start_price = float(
                    row["price"]
                )


                evaluation_price = float(
                    evaluation_price
                )


                return_percent = round(

                    (
                        (
                            evaluation_price -
                            start_price
                        )
                        /
                        start_price
                    )
                    *
                    100,

                    2

                )



                if return_percent >= 5:

                    outcome = "SUCCESS"


                elif return_percent <= -5:

                    outcome = "FAILED"


                else:

                    outcome = "FLAT"



                evaluations.append(

                    {

                        "recommendation_id":
                            recommendation_id,

                        "ticker":
                            ticker,

                        "evaluation_date":
                            today.strftime(
                                "%Y-%m-%d"
                            ),

                        "days_after":
                            horizon,

                        "price":
                            evaluation_price,

                        "return_percent":
                            return_percent,

                        "outcome":
                            outcome,

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


                print(

                    "DEBUG EVALUATION:",
                    ticker,
                    "Days:",
                    horizon,
                    "Return:",
                    return_percent

                )


        except Exception as e:


            print(
                f"EVALUATION ERROR {ticker}: {e}"
            )



    if not evaluations:

        print(
            "NO EVALUATIONS CREATED"
        )

        return pd.DataFrame()



    df = pd.DataFrame(
        evaluations
    )


    print(
        "EVALUATIONS CREATED:",
        df.shape
    )


    return df