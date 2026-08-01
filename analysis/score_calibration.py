import pandas as pd

from data.database import get_connection


def calculate_score_calibration():

    conn = get_connection()

    query = """
    SELECT
        ticker,
        signal,
        investment_score,
        technical_score,
        quality_score,
        return_percent
    FROM recommendation_evaluations
    """

    df = pd.read_sql_query(
        query,
        conn
    )

    conn.close()


    if df.empty:

        return {
            "Summary": pd.DataFrame(),
            "Correlation": pd.DataFrame(),
            "Buckets": pd.DataFrame()
        }


    # ---------------------------------
    # Summary
    # ---------------------------------

    summary = pd.DataFrame(
        {
            "Evaluations": [
                len(df)
            ],

            "Unique Stocks": [
                df["ticker"].nunique()
            ],

            "Average Return %": [
                round(
                    df["return_percent"].mean(),
                    2
                )
            ],

            "Median Return %": [
                round(
                    df["return_percent"].median(),
                    2
                )
            ],

            "Win Rate %": [
                round(
                    (
                        df["return_percent"] > 0
                    ).mean()
                    *
                    100,
                    2
                )
            ]
        }
    )


    # ---------------------------------
    # Factor Correlations
    # ---------------------------------

    factors = [

        "investment_score",

        "technical_score",

        "quality_score"

    ]


    correlation_results = []


    for factor in factors:


        correlation = df[
            [
                factor,
                "return_percent"
            ]
        ].corr().iloc[0,1]


        correlation_results.append(
            {
                "Factor":
                    factor.replace(
                        "_",
                        " "
                    ).title(),

                "Correlation":
                    round(
                        correlation,
                        3
                    )
            }
        )


    correlations = pd.DataFrame(
        correlation_results
    )


    # ---------------------------------
    # Score Buckets
    # ---------------------------------

    bins = [
        0,
        49,
        59,
        69,
        79,
        89,
        100
    ]


    labels = [
        "<50",
        "50-59",
        "60-69",
        "70-79",
        "80-89",
        "90-100"
    ]


    df["Score Bucket"] = pd.cut(
        df["investment_score"],
        bins=bins,
        labels=labels
    )


    buckets = (

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
                    round(
                        (
                            x > 0
                        )
                        .mean()
                        *
                        100,
                        2
                    )
            )
        )
        .reset_index()

    )


    buckets["Average_Return"] = buckets[
        "Average_Return"
    ].round(2)


    return {

        "Raw Data": df,

        "Summary": summary,

        "Correlation": correlations,

        "Buckets": buckets

    }

def get_calibrated_weights():

    results = calculate_score_calibration()

    correlations = results["Correlation"]


    # ---------------------------------
    # Default operating weights
    # ---------------------------------

    default_weights = {

        "Technical Weight": 0.45,

        "Quality Weight": 0.30,

        "Growth Weight": 0.25

    }


    if correlations.empty:

        return default_weights



    correlation_map = dict(
        zip(
            correlations["Factor"],
            correlations["Correlation"]
        )
    )


    technical = correlation_map.get(
        "Technical Score",
        0
    )

    quality = correlation_map.get(
        "Quality Score",
        0
    )


    # ---------------------------------
    # Calibration safety
    #
    # Do not allow negative
    # historical results to
    # destroy the scoring model
    # ---------------------------------

    technical = max(
        technical,
        0.05
    )

    quality = max(
        quality,
        0.05
    )


    total = (
        technical
        +
        quality
    )


    if total == 0:

        return default_weights



    calibrated_technical = technical / total

    calibrated_quality = quality / total


    # Blend calibration with defaults
    # to avoid overfitting small samples

    final_technical = (
        calibrated_technical * 0.3
        +
        0.45 * 0.7
    )


    final_quality = (
        calibrated_quality * 0.3
        +
        0.30 * 0.7
    )


    final_growth = (
        1
        -
        final_technical
        -
        final_quality
    )


    return {

        "Technical Weight":
            round(final_technical,2),

        "Quality Weight":
            round(final_quality,2),

        "Growth Weight":
            round(final_growth,2)

    }

if __name__ == "__main__":


    results = calculate_score_calibration()


    print("\n===== SUMMARY =====")

    print(
        results["Summary"]
    )


    print("\n===== FACTOR CORRELATION =====")

    print(
        results["Correlation"]
    )


    print("\n===== SCORE BUCKETS =====")

    print(
        results["Buckets"]
    )