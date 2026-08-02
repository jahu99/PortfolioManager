import pandas as pd


# -------------------------------------------------
# Reliability classification
# -------------------------------------------------

def get_reliability(count):

    if count < 20:
        return "INSUFFICIENT DATA"

    elif count < 50:
        return "LOW CONFIDENCE"

    else:
        return "VALID"



def calculate_recommendation_learning(
    recommendation_history
):

    print(
        "RECOMMENDATION LEARNING ENGINE START"
    )


    empty_result = {

        "Overall": {},

        "Horizon Learning": {},

        "Signal Performance": pd.DataFrame(),

        "Score Bucket Performance": pd.DataFrame(),

        "Component Score Performance": pd.DataFrame()

    }


    if (
        recommendation_history is None
        or recommendation_history.empty
    ):

        return empty_result



    df = recommendation_history.copy()



    # ---------------------------------
    # Normalise columns
    # ---------------------------------

    df.rename(
        columns={

            "Days After":
                "days_after",

            "Return %":
                "return_percent"

        },

        inplace=True
    )



    print(
        "LEARNING DATASET:",
        df.shape
    )



    required_columns = [

        "Signal",

        "Investment Score",

        "return_percent",

        "Outcome",

        "days_after"

    ]



    for col in required_columns:

        if col not in df.columns:

            print(
                f"MISSING COLUMN: {col}"
            )

            return empty_result



    # ---------------------------------
    # Overall performance
    # ---------------------------------

    total = len(df)


    successful = len(
        df[
            df["Outcome"] == "SUCCESS"
        ]
    )


    failed = len(
        df[
            df["Outcome"] == "FAILED"
        ]
    )


    overall = {

        "Total Recommendations":
            total,

        "Successful Recommendations":
            successful,

        "Failed Recommendations":
            failed,

        "Win Rate %":
            round(
                successful / total * 100,
                2
            )
            if total
            else 0,

        "Reliability":
            get_reliability(
                total
            )

    }



    # ---------------------------------
    # Signal performance
    # ---------------------------------

    signal_performance = (

        df

        .groupby("Signal")

        .agg(

            Recommendations=
            (
                "Signal",
                "count"
            ),

            Average_Return=
            (
                "return_percent",
                "mean"
            ),

            Wins=
            (
                "Outcome",
                lambda x:
                (
                    x == "SUCCESS"
                ).sum()
            )

        )

        .reset_index()

    )


    signal_performance["Win Rate %"] = (

        signal_performance["Wins"]

        /

        signal_performance["Recommendations"]

        *

        100

    ).round(2)



    signal_performance["Reliability"] = (

        signal_performance["Recommendations"]

        .apply(
            get_reliability
        )

    )



    # ---------------------------------
    # Score bucket performance
    # ---------------------------------

    df["Score Bucket"] = pd.cut(

        df["Investment Score"],

        bins=[

            0,
            50,
            70,
            85,
            100

        ],

        labels=[

            "Low",
            "Medium",
            "Good",
            "High"

        ],

        include_lowest=True

    )



    score_bucket_performance = (

        df

        .groupby(
            "Score Bucket",
            observed=False
        )

        .agg(

            Recommendations=
            (
                "Investment Score",
                "count"
            ),

            Average_Return=
            (
                "return_percent",
                "mean"
            ),

            Wins=
            (
                "Outcome",
                lambda x:
                (
                    x == "SUCCESS"
                ).sum()
            )

        )

        .reset_index()

    )



    score_bucket_performance["Win Rate %"] = (

        score_bucket_performance["Wins"]

        /

        score_bucket_performance["Recommendations"]

        *

        100

    ).round(2)



    score_bucket_performance["Reliability"] = (

        score_bucket_performance["Recommendations"]

        .apply(
            get_reliability
        )

    )



    # ---------------------------------
    # Component performance
    # ---------------------------------

    component_rows = []


    for component in [

        "Investment Score",

        "Technical Score",

        "Quality Score",

        "Growth Score"

    ]:


        if component in df.columns:


            correlation = None


            if len(df) >= 20:

                correlation = round(

                    df[component]

                    .corr(
                        df["return_percent"]
                    ),

                    3

                )


            component_rows.append(

                {

                    "Component":
                        component,

                    "Correlation":
                        correlation,

                    "Reliability":
                        get_reliability(
                            len(df)
                        )

                }

            )



    component_score_performance = pd.DataFrame(
        component_rows
    )



    # ---------------------------------
    # Horizon learning
    # ---------------------------------

    horizon_learning = {}



    for horizon in sorted(

        df["days_after"]

        .dropna()

        .astype(int)

        .unique()

    ):


        print(
            "ANALYSING HORIZON:",
            horizon
        )


        hdf = df[
            df["days_after"] == horizon
        ]



        horizon_learning[horizon] = {

            "Recommendations":
                len(hdf),


            "Average Return %":
                round(
                    hdf["return_percent"].mean(),
                    2
                ),


            "Reliability":
                get_reliability(
                    len(hdf)
                )

        }



    print(
        "RECOMMENDATION LEARNING COMPLETE"
    )


    print(
        "HORIZONS:",
        list(
            horizon_learning.keys()
        )
    )



    return {


        "Overall":
            overall,


        "Horizon Learning":
            horizon_learning,


        "Signal Performance":
            signal_performance,


        "Score Bucket Performance":
            score_bucket_performance,


        "Component Score Performance":
            component_score_performance

    }