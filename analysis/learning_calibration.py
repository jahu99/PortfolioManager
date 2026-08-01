import pandas as pd
from data.database import get_connection


# ==========================================
# Learning Calibration Engine
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

        e.days_after AS Days_After,

        e.return_percent AS Return_Percent,

        e.outcome AS Outcome


    FROM recommendations r


    JOIN recommendation_evaluations e


    ON r.id = e.recommendation_id


    """


    df = pd.read_sql(
        query,
        conn
    )


    return df



# ==========================================
# Score Calibration
# ==========================================


def analyse_scores(df):

    print(
        "\nSCORE CALIBRATION"
    )


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
        ]

    )


    result = (

        df

        .groupby(
            "Score Bucket",
            observed=False
        )

        .agg(

            Recommendations=(
                "Ticker",
                "count"
            ),

            Average_Return=(
                "Return_Percent",
                "mean"
            ),

            Win_Rate=(
                "Outcome",
                lambda x:
                (
                    x=="SUCCESS"
                ).mean()*100
            )

        )

        .reset_index()

    )


    result["Win_Rate"] = (
        result["Win_Rate"]
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

            Recommendations=(
                "Ticker",
                "count"
            ),

            Average_Return=(
                "Return_Percent",
                "mean"
            ),

            Win_Rate=(
                "Outcome",
                lambda x:
                (
                    x=="SUCCESS"
                ).mean()*100
            )

        )

        .reset_index()

    )


    result["Win_Rate"] = (
        result["Win_Rate"]
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


    result = pd.DataFrame({

        "Component":

        [
            "Investment Score",
            "Technical Score",
            "Quality Score"
        ],


        "Correlation":

        [

            df[
                [
                    "Investment_Score",
                    "Return_Percent"
                ]
            ]
            .corr()
            .iloc[0,1],


            df[
                [
                    "Technical_Score",
                    "Return_Percent"
                ]
            ]
            .corr()
            .iloc[0,1],


            df[
                [
                    "Quality_Score",
                    "Return_Percent"
                ]
            ]
            .corr()
            .iloc[0,1]

        ]

    })


    result["Correlation"] = (
        result["Correlation"]
        .round(3)
    )


    print(result)


    return result



# ==========================================
# Main Calibration Runner
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

        return



    score_results = analyse_scores(df)


    signal_results = analyse_signals(df)


    component_results = analyse_components(df)


    return {


        "Score Calibration":
            score_results,


        "Signal Calibration":
            signal_results,


        "Component Calibration":
            component_results

    }