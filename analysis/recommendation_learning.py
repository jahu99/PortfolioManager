import pandas as pd


def calculate_recommendation_learning(
    recommendation_history
):
    """
    Analyse recommendation performance.

    Input dataframe must contain:
    - Signal
    - Investment Score
    - Outcome
    - Return %
    """

    print(
        "RECOMMENDATION LEARNING ENGINE START"
    )


    if (
        recommendation_history is None
        or recommendation_history.empty
    ):

        return {

            "Total Recommendations": 0,
            "Evaluated Recommendations": 0,
            "Successful Recommendations": 0,
            "Failed Recommendations": 0,
            "Win Rate %": 0,
            "Signal Learning": pd.DataFrame()

        }



    df = recommendation_history.copy()


    total = len(df)


    evaluated = df[
        df["Outcome"].notna()
    ]


    evaluated_count = len(
        evaluated
    )


    successful = len(
        evaluated[
            evaluated["Outcome"] == "WIN"
        ]
    )


    failed = len(
        evaluated[
            evaluated["Outcome"] == "LOSS"
        ]
    )


    win_rate = 0


    if evaluated_count > 0:

        win_rate = round(
            successful /
            evaluated_count
            *
            100,
            2
        )



    # ------------------------------
    # Signal learning
    # ------------------------------

    signal_learning = pd.DataFrame()


    if evaluated_count > 0:


        signal_learning = (

            evaluated

            .groupby("Signal")

            .agg(

                Recommendations=(
                    "Signal",
                    "count"
                ),

                Average_Return=(
                    "Return %",
                    "mean"
                ),

                Wins=(
                    "Outcome",
                    lambda x:
                    (
                        x=="WIN"
                    ).sum()
                )

            )

            .reset_index()

        )


        signal_learning["Win Rate %"] = (

            signal_learning["Wins"]

            /

            signal_learning["Recommendations"]

            *

            100

        ).round(2)



    print()

    print(
        "RECOMMENDATION LEARNING"
    )

    print(
        "Total Recommendations:",
        total
    )

    print(
        "Evaluated Recommendations:",
        evaluated_count
    )

    print(
        "Successful Recommendations:",
        successful
    )

    print(
        "Failed Recommendations:",
        failed
    )

    print(
        "Win Rate %",
        win_rate
    )


    return {


        "Total Recommendations":
            total,


        "Evaluated Recommendations":
            evaluated_count,


        "Successful Recommendations":
            successful,


        "Failed Recommendations":
            failed,


        "Win Rate %":
            win_rate,


        "Signal Learning":
            signal_learning

    }