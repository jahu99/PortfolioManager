import pandas as pd


# =====================================================
# Horizon Learning Engine
# =====================================================

def calculate_horizon_learning(
    recommendation_history
):

    print(
        "HORIZON LEARNING ENGINE START"
    )


    empty_result = {

        "Horizon Summary":
            pd.DataFrame(),

        "Best Horizon":
            None,

        "Horizon Insights":
            []

    }


    if (
        recommendation_history is None
        or recommendation_history.empty
    ):

        print(
            "NO HORIZON DATA"
        )

        return empty_result



    df = recommendation_history.copy()



    # -------------------------------------------------
    # Normalise columns
    # -------------------------------------------------

    df.rename(
        columns={

            "Days After":
                "days_after",

            "Return %":
                "return_percent",

            "Investment Score":
                "investment_score"

        },

        inplace=True
    )


    print(
        "HORIZON DATASET:",
        df.shape
    )



    required = [

        "days_after",

        "return_percent",

        "Outcome"

    ]


    for col in required:

        if col not in df.columns:

            print(
                "MISSING COLUMN:",
                col
            )

            return empty_result



    # -------------------------------------------------
    # Horizon statistics
    # -------------------------------------------------

    rows = []


    for horizon in sorted(

        df["days_after"]
        .dropna()
        .astype(int)
        .unique()

    ):


        hdf = df[

            df["days_after"]
            .astype(int)
            ==
            int(horizon)

        ]


        recommendations = len(hdf)


        wins = (

            hdf["Outcome"]
            ==
            "SUCCESS"

        ).sum()


        failures = (

            hdf["Outcome"]
            ==
            "FAILED"

        ).sum()


        average_return = (

            hdf["return_percent"]
            .mean()

        )


        win_rate = (

            wins
            /
            recommendations
            *
            100

        ) if recommendations else 0



        rows.append(

            {

                "Days":
                    int(horizon),

                "Recommendations":
                    recommendations,

                "Average Return %":
                    round(
                        average_return,
                        2
                    ),

                "Wins":
                    int(wins),

                "Failures":
                    int(failures),

                "Win Rate %":
                    round(
                        win_rate,
                        2
                    )

            }

        )



    horizon_summary = pd.DataFrame(
        rows
    )



    # -------------------------------------------------
    # Reliability assessment
    # -------------------------------------------------

    def reliability(row):

        if row["Recommendations"] < 25:

            return "INSUFFICIENT DATA"


        if row["Win Rate %"] < 30:

            return "LOW CONFIDENCE"


        return "VALID"



    if not horizon_summary.empty:

        horizon_summary["Reliability"] = (

            horizon_summary
            .apply(
                reliability,
                axis=1
            )

        )



    # -------------------------------------------------
    # Best Horizon Selection
    # -------------------------------------------------

    best_horizon = None


    if not horizon_summary.empty:


        candidates = horizon_summary[

            (horizon_summary["Reliability"] == "VALID")

            &

            (horizon_summary["Recommendations"] >= 25)

        ]



        if not candidates.empty:


            candidates = candidates.sort_values(

                by=[

                    "Win Rate %",

                    "Average Return %"

                ],

                ascending=False

            )


            best_horizon = int(

                candidates.iloc[0]["Days"]

            )



    # -------------------------------------------------
    # Insights
    # -------------------------------------------------

    insights = []



    if best_horizon is not None:


        best = horizon_summary[

            horizon_summary["Days"]
            ==
            best_horizon

        ].iloc[0]


        insights.append(

            f"""
Best horizon identified:

{best_horizon} trading days

Average Return:
{best['Average Return %']}%

Win Rate:
{best['Win Rate %']}%

"""

        )


    else:


        insights.append(

            """
No reliable horizon identified yet.

Continue collecting evaluation data.

"""

        )



    for _, row in horizon_summary.iterrows():


        if row["Average Return %"] < 0:


            insights.append(

                f"""
{row['Days']} day horizon currently
shows negative average performance.

"""

            )



    print(
        "HORIZON LEARNING COMPLETE"
    )


    print(
        horizon_summary
    )



    return {


        "Horizon Summary":
            horizon_summary,


        "Best Horizon":
            best_horizon,


        "Horizon Insights":
            insights

    }


    # -------------------------------------------------
    # Reliability
    # -------------------------------------------------

    def reliability(row):

        if row["Recommendations"] < 25:

            return "INSUFFICIENT DATA"


        if row["Win Rate %"] < 30:

            return "LOW CONFIDENCE"


        return "VALID"



    if not horizon_summary.empty:

        horizon_summary["Reliability"] = (

            horizon_summary
            .apply(
                reliability,
                axis=1
            )

        )



    # -------------------------------------------------
    # Best horizon selection
    # -------------------------------------------------

    best_horizon = None


    if not horizon_summary.empty:


        candidates = horizon_summary[

            (horizon_summary["Reliability"] == "VALID")

            &

            (horizon_summary["Recommendations"] >= 25)

            &

            (horizon_summary["Average Return %"] > 0)

        ]



        if not candidates.empty:


            candidates = candidates.sort_values(

                by=[

                    "Average Return %",

                    "Win Rate %"

                ],

                ascending=False

            )


            best_horizon = int(

                candidates.iloc[0]["Days"]

            )



    # -------------------------------------------------
    # Insights
    # -------------------------------------------------

    insights = []



    if best_horizon:


        best = horizon_summary[

            horizon_summary["Days"]
            ==
            best_horizon

        ].iloc[0]


        insights.append(

            f"""
Best horizon identified:

{best_horizon} trading days

Average Return:
{best['Average Return %']}%

Win Rate:
{best['Win Rate %']}%

"""

        )


    else:


        insights.append(

            """
No reliable profitable horizon identified yet.

Continue collecting evaluation data.

"""

        )



    for _, row in horizon_summary.iterrows():


        if row["Average Return %"] < 0:


            insights.append(

                f"""
{row['Days']} day horizon currently
shows negative average performance.

"""

            )



    print(
        "HORIZON LEARNING COMPLETE"
    )


    print(
        horizon_summary
    )



    return {


        "Horizon Summary":
            horizon_summary,


        "Best Horizon":
            best_horizon,


        "Horizon Insights":
            insights

    }




# =====================================================
# Runner
# =====================================================

def run_horizon_learning():


    print(
        "RUNNING HORIZON LEARNING"
    )


    from data.database_queries import get_learning_history



    history = get_learning_history()



    return calculate_horizon_learning(

        history

    )