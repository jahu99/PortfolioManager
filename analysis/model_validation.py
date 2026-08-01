import pandas as pd

from data.database import get_connection


def load_validation_data():

    conn = get_connection()

    query = """
    SELECT
        recommendation_id,
        ticker,
        signal,
        evaluation_date,
        days_after,
        price,
        return_percent,
        outcome,
        investment_score,
        technical_score,
        quality_score

    FROM recommendation_evaluations

    """

    df = pd.read_sql_query(
        query,
        conn
    )

    conn.close()

    return df



def calculate_summary_metrics(df):

    if df.empty:
        return pd.DataFrame()


    return pd.DataFrame(
        [{
            "Evaluations": len(df),

            "Unique Stocks":
                df["ticker"].nunique(),

            "Average Return %":
                round(
                    df["return_percent"].mean(),
                    2
                ),

            "Median Return %":
                round(
                    df["return_percent"].median(),
                    2
                ),

            "Win Rate %":
                round(
                    (
                        df["return_percent"] > 0
                    ).mean()
                    *
                    100,
                    2
                )
        }]
    )



def calculate_signal_performance(df):

    if df.empty:
        return pd.DataFrame()


    result = (
        df
        .groupby("signal")
        .agg(
            Count=(
                "ticker",
                "count"
            ),

            Average_Return=(
                "return_percent",
                "mean"
            ),

            Win_Rate=(
                "return_percent",
                lambda x:
                    (x > 0).mean()*100
            )
        )
        .reset_index()
    )


    result["Average_Return"] = (
        result["Average_Return"]
        .round(2)
    )

    result["Win_Rate"] = (
        result["Win_Rate"]
        .round(2)
    )


    return result



def calculate_score_performance(df):

    if df.empty:
        return pd.DataFrame()


    df = df.copy()


    df["Score Bucket"] = pd.cut(
        df["investment_score"],

        bins=[
            0,
            49,
            59,
            69,
            79,
            89,
            100
        ],

        labels=[
            "<50",
            "50-59",
            "60-69",
            "70-79",
            "80-89",
            "90-100"
        ]
    )


    result = (
        df
        .groupby(
            "Score Bucket",
            observed=False
        )
        .agg(

            Count=(
                "ticker",
                "count"
            ),

            Average_Return=(
                "return_percent",
                "mean"
            ),

            Win_Rate=(
                "return_percent",
                lambda x:
                (x > 0).mean()*100
            )

        )
        .reset_index()
    )


    result["Average_Return"] = (
        result["Average_Return"]
        .round(2)
    )


    result["Win_Rate"] = (
        result["Win_Rate"]
        .round(2)
    )


    return result



def calculate_factor_performance(df):

    if df.empty:
        return pd.DataFrame()


    return pd.DataFrame(
        {

            "Factor":
            [
                "Investment Score",
                "Technical Score",
                "Quality Score"
            ],

            "Correlation":
            [

                df["investment_score"]
                .corr(
                    df["return_percent"]
                ),

                df["technical_score"]
                .corr(
                    df["return_percent"]
                ),

                df["quality_score"]
                .corr(
                    df["return_percent"]
                )

            ]

        }
    ).round(3)



def calculate_model_validation():

    df = load_validation_data()


    return {

        "Raw Data":
            df,

        "Summary":
            calculate_summary_metrics(df),

        "Signal Performance":
            calculate_signal_performance(df),

        "Score Performance":
            calculate_score_performance(df),

        "Factor Performance":
            calculate_factor_performance(df)

    }