import pandas as pd

from data.database import get_connection


# ==========================================
# Learning Calibration Engine
# ==========================================


MIN_SAMPLE_LOW = 10
MIN_SAMPLE_ACTIONABLE = 30



# ==========================================
# Load Learning Data
# ==========================================


def load_learning_data():

    conn = get_connection()


    query = """

    SELECT

        r.ticker AS Ticker,

        r.date AS Recommendation_Date,

        r.signal AS Signal,

        r.investment_score AS Investment_Score,

        r.technical_score AS Technical_Score,

        r.quality_score AS Quality_Score,

        r.growth_score AS Growth_Score,

        r.confidence_score AS Confidence_Score,

        e.days_after AS Days_After,

        e.return_percent AS Return_Percent,

        e.outcome AS Outcome


    FROM recommendations r


    JOIN recommendation_evaluations e


    ON r.id = e.recommendation_id


    ORDER BY

        e.evaluation_date DESC

    """


    df = pd.read_sql(
        query,
        conn
    )


    conn.close()


    return df




# ==========================================
# Reliability Helper
# ==========================================


def calculate_reliability(samples):


    if samples < MIN_SAMPLE_LOW:

        return "INSUFFICIENT DATA"


    elif samples < MIN_SAMPLE_ACTIONABLE:

        return "LOW CONFIDENCE"


    else:

        return "VALID"




# ==========================================
# Score Calibration
# ==========================================


def analyse_scores(df):

    print(
        "\nSCORE CALIBRATION"
    )


    df = df.copy()


    df["Score Bucket"] = pd.cut(

        df["Investment_Score"],

        bins=[

            0,
            50,
            65,
            80,
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



    result = (

        df

        .groupby(
            "Score Bucket",
            observed=False
        )

        .agg(

            Recommendations=
            (
                "Ticker",
                "count"
            ),

            Average_Return=
            (
                "Return_Percent",
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



    result["Win_Rate"] = (

        result["Wins"]

        /

        result["Recommendations"]

        *

        100

    ).round(2)



    result["Reliability"] = (

        result["Recommendations"]

        .apply(
            calculate_reliability
        )

    )


    result["Average_Return"] = (
        result["Average_Return"]
        .round(2)
    )


    print(result)


    return result




# ==========================================
# Signal Calibration
# ==========================================


def analyse_signals(df):

    print(
        "\nSIGNAL CALIBRATION"
    )


    result = (

        df

        .groupby(
            "Signal"
        )

        .agg(

            Recommendations=
            (
                "Ticker",
                "count"
            ),

            Average_Return=
            (
                "Return_Percent",
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



    result["Win_Rate"] = (

        result["Wins"]

        /

        result["Recommendations"]

        *

        100

    ).round(2)



    result["Reliability"] = (

        result["Recommendations"]

        .apply(
            calculate_reliability
        )

    )



    result["Average_Return"] = (

        result["Average_Return"]

        .round(2)

    )


    print(result)


    return result




# ==========================================
# Component Analysis
# ==========================================


def analyse_components(df):

    print(
        "\nCOMPONENT CALIBRATION"
    )


    components = [

        "Investment_Score",

        "Technical_Score",

        "Quality_Score",

        "Growth_Score",

        "Confidence_Score"

    ]


    rows = []



    for component in components:


        if component in df.columns:


            correlation = (

                df[component]

                .corr(
                    df["Return_Percent"]
                )

            )


            if pd.isna(correlation):

                correlation = 0



            rows.append(

                {

                    "Component":
                        component.replace(
                            "_",
                            " "
                        ),

                    "Correlation":
                        round(
                            correlation,
                            3
                        )

                }

            )



    result = pd.DataFrame(
        rows
    )



    result["Reliability"] = "VALID"



    print(result)


    return result




# ==========================================
# Calibration Actions
# ==========================================


def generate_calibration_actions(

    score_results,

    signal_results,

    component_results

):


    print(
        "\nCALIBRATION ACTIONS"
    )



    actions = []



    # --------------------------
    # Signals
    # --------------------------


    for _, row in signal_results.iterrows():


        if (

            row["Reliability"]
            == "VALID"

            and

            row["Average_Return"] < 0

        ):


            actions.append(

                {

                    "Area":
                        "Signal",

                    "Item":
                        row["Signal"],

                    "Issue":
                        (
                            f"Average return "
                            f"{row['Average_Return']}%"
                        ),

                    "Recommendation":
                        "Review signal threshold"

                }

            )




    # --------------------------
    # Score buckets
    # --------------------------


    for _, row in score_results.iterrows():


        if (

            row["Reliability"]
            == "VALID"

            and

            row["Average_Return"] < 0

        ):


            actions.append(

                {

                    "Area":
                        "Score Bucket",

                    "Item":
                        row["Score Bucket"],

                    "Issue":
                        (
                            f"Negative return "
                            f"{row['Average_Return']}%"
                        ),

                    "Recommendation":
                        "Review scoring weights"

                }

            )




    # --------------------------
    # Components
    # --------------------------


    for _, row in component_results.iterrows():


        correlation = row[
            "Correlation"
        ]



        if correlation < 0:


            actions.append(

                {

                    "Area":
                        "Component",

                    "Item":
                        row["Component"],

                    "Issue":
                        (
                            f"Negative correlation "
                            f"{correlation}"
                        ),

                    "Recommendation":
                        "Reduce weighting"

                }

            )



        elif correlation > 0.3:


            actions.append(

                {

                    "Area":
                        "Component",

                    "Item":
                        row["Component"],

                    "Issue":
                        (
                            f"Strong correlation "
                            f"{correlation}"
                        ),

                    "Recommendation":
                        "Consider increasing weighting"

                }

            )



    return pd.DataFrame(
        actions
    )




# ==========================================
# Main Runner
# ==========================================


def run_learning_calibration():


    print(
        "LEARNING CALIBRATION START"
    )



    df = load_learning_data()



    print(
        "Learning records:",
        len(df)
    )



    if df.empty:


        print(
            "No learning data available"
        )


        return {}




    score_results = analyse_scores(
        df
    )



    signal_results = analyse_signals(
        df
    )



    component_results = analyse_components(
        df
    )



    calibration_actions = generate_calibration_actions(

        score_results,

        signal_results,

        component_results

    )



    print(
        "\nLEARNING CALIBRATION COMPLETE"
    )


    return {


        "Score Calibration":

            score_results,


        "Signal Calibration":

            signal_results,


        "Component Calibration":

            component_results,


        "Calibration Actions":

            calibration_actions

    }