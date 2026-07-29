import pandas as pd


def generate_recommendation_intelligence(
    results,
    signal_performance,
    score_bucket_performance,
    component_score_performance
):

    print("RECOMMENDATION INTELLIGENCE START")
    print(f"INPUT RESULTS: {len(results)}")


    intelligence = []


    if results is None or len(results) == 0:

        print("NO RESULTS PROVIDED")

        return pd.DataFrame()



    for stock in results:


        ticker = stock.get(
            "Ticker",
            "UNKNOWN"
        )


        signal = stock.get(
            "Signal",
            "UNKNOWN"
        )


        score = stock.get(
            "Investment Score",
            0
        )


        notes = []


        row = {

            "Ticker": ticker,

            "Signal": signal,

            "Investment Score": score,

            "Confidence":
                stock.get(
                    "Confidence",
                    "Unknown"
                ),


            "Recommendation Strength":
                (
                    "Strong"
                    if score >= 80
                    else
                    "Moderate"
                    if score >= 65
                    else
                    "Weak"
                ),


            "Historical Signal Evidence":
                "Unavailable",


            "Score Bucket Evidence":
                "Unavailable",


            "Component Evidence":
                "Unavailable",


            "Intelligence Notes":
                ""

        }



        # -------------------------
        # Historical signal evidence
        # -------------------------

        if (
            signal_performance is not None
            and not signal_performance.empty
        ):

            matching = signal_performance[
                signal_performance["Signal"]
                ==
                signal
            ]


            if not matching.empty:

                row[
                    "Historical Signal Evidence"
                ] = str(
                    matching.iloc[0].to_dict()
                )

                notes.append(
                    "Historical signal data available"
                )



        # -------------------------
        # Score bucket evidence
        # -------------------------

        if (
            score_bucket_performance is not None
            and not score_bucket_performance.empty
        ):

            row[
                "Score Bucket Evidence"
            ] = str(
                score_bucket_performance.to_dict(
                    "records"
                )
            )

            notes.append(
                "Score bucket history available"
            )



        # -------------------------
        # Component evidence
        # -------------------------

        if (
            component_score_performance is not None
            and not component_score_performance.empty
        ):

            row[
                "Component Evidence"
            ] = str(
                component_score_performance.to_dict(
                    "records"
                )
            )


            notes.append(
                "Component scoring history available"
            )



        row[
            "Intelligence Notes"
        ] = "; ".join(notes)



        intelligence.append(
            row
        )


       



    df = pd.DataFrame(
        intelligence
    )


    print(
        f"FINAL INTELLIGENCE DATAFRAME SIZE: {df.shape}"
    )


    print(
        df.head()
    )


    return df