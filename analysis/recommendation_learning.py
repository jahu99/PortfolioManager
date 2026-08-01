import pandas as pd


def calculate_recommendation_learning(
    recommendation_history
):

    print(
        "RECOMMENDATION LEARNING ENGINE START"
    )


    if (
        recommendation_history is None
        or recommendation_history.empty
    ):

        return {

            "Overall": {},

            "Horizon Learning": {}

        }


    df = recommendation_history.copy()


    # ---------------------------------
    # Normalise column names
    # ---------------------------------

    df.rename(
        columns={

            "Days After":
                "days_after",

            "Return %":
                "return_percent",

        },

        inplace=True

    )


    print(
        "LEARNING DATASET:",
        df.shape
    )


    print(
        df.head()
    )


    # ---------------------------------
    # Ensure required columns exist
    # ---------------------------------

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

            return {

                "Overall": {},

                "Horizon Learning": {}

            }



    # ---------------------------------
    # Overall statistics
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


    win_rate = (

        round(
            successful / total * 100,
            2
        )

        if total > 0

        else 0

    )


    overall = {

        "Total Recommendations":
            total,

        "Successful Recommendations":
            successful,

        "Failed Recommendations":
            failed,

        "Win Rate %":
            win_rate

    }



    # ---------------------------------
    # Horizon learning
    # ---------------------------------

    horizon_learning = {}


    for horizon in sorted(
        int(x) for x in df["days_after"].unique()
    ):


        print()

        print(
            "ANALYSING HORIZON:",
            horizon
        )


        hdf = df[
            df["days_after"] == horizon
        ].copy()



        # -----------------------------
        # Signal performance
        # -----------------------------

        signal_learning = (

            hdf

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


        signal_learning[

            "Win Rate %"

        ] = (

            signal_learning["Wins"]

            /

            signal_learning["Recommendations"]

            *

            100

        ).round(2)



        # -----------------------------
        # Investment score buckets
        # -----------------------------

        hdf["Score Bucket"] = pd.cut(

            hdf[
                "Investment Score"
            ],

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

            ]

        )


        score_learning = (

            hdf

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


        score_learning[

            "Win Rate %"

        ] = (

            score_learning["Wins"]

            /

            score_learning["Recommendations"]

            *

            100

        ).round(2)



        # -----------------------------
        # Component correlation
        # -----------------------------

        component_learning = pd.DataFrame()


        component_rows = []


        for component in [

            "Investment Score",

            "Technical Score",

            "Quality Score"

        ]:


            if component in hdf.columns:


                component_rows.append(

                    {

                        "Component":
                            component,

                        "Correlation":
                            round(

                                hdf[
                                    component
                                ]

                                .corr(

                                    hdf[
                                        "return_percent"
                                    ]

                                ),

                                3

                            )

                    }

                )


        if component_rows:

            component_learning = pd.DataFrame(
                component_rows
            )



        horizon_learning[horizon] = {


            "Recommendations":
                len(hdf),


            "Average Return %":
                round(

                    hdf[
                        "return_percent"
                    ]

                    .mean(),

                    2

                ),


            "Signal Learning":
                signal_learning,


            "Score Learning":
                score_learning,


            "Component Learning":
                component_learning

        }



    print()

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
            horizon_learning

    }