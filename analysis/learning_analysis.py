import pandas as pd


# ============================================================
# Recommendation Learning Analysis
# ============================================================


def _bucket_score(score):

    """
    Convert numeric scores into learning buckets.
    """

    try:
        score = float(score)

    except Exception:
        return "Unknown"


    if score >= 80:
        return "80+"

    elif score >= 60:
        return "60-79"

    elif score >= 40:
        return "40-59"

    else:
        return "<40"



# ============================================================
# Generic bucket analysis
# ============================================================


def analyse_score_bucket(
    df,
    score_column
):

    if (
        df is None
        or df.empty
        or score_column not in df.columns
    ):
        return pd.DataFrame()


    temp = df.copy()


    temp["Score Bucket"] = (
        temp[score_column]
        .apply(_bucket_score)
    )


    result = (

        temp

        .groupby("Score Bucket")

        .agg(

            Recommendations=(
                score_column,
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
            ),

            Losses=(
                "Outcome",
                lambda x:
                (
                    x=="LOSS"
                ).sum()
            )

        )

        .reset_index()

    )


    result["Win Rate %"] = (

        result["Wins"]

        /

        result["Recommendations"]

        *

        100

    ).round(2)


    result["Average_Return"] = (
        result["Average_Return"]
        .round(2)
    )


    return result



# ============================================================
# Signal performance
# ============================================================


def analyse_signal_performance(
    df
):

    if (
        df is None
        or df.empty
        or "Signal" not in df.columns
    ):
        return pd.DataFrame()



    result = (

        df

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
            ),

            Losses=(
                "Outcome",
                lambda x:
                (
                    x=="LOSS"
                ).sum()
            )

        )

        .reset_index()

    )


    result["Win Rate %"] = (

        result["Wins"]

        /

        result["Recommendations"]

        *

        100

    ).round(2)



    result["Average_Return"] = (
        result["Average_Return"]
        .round(2)
    )


    return result



# ============================================================
# Component analysis
# ============================================================


def analyse_components(
    df
):

    components = [

        "Investment Score",
        "Technical Score",
        "Quality Score",
        "Growth Score",
        "Momentum Score",
        "Risk Score"

    ]


    output = []


    for component in components:


        if component not in df.columns:

            continue


        analysis = analyse_score_bucket(
            df,
            component
        )


        if analysis.empty:

            continue


        analysis.insert(
            0,
            "Component",
            component
        )


        output.append(
            analysis
        )



    if not output:

        return pd.DataFrame()



    return pd.concat(
        output,
        ignore_index=True
    )



# ============================================================
# Full learning report
# ============================================================


def run_learning_analysis(
    recommendation_history
):

    print(
        "LEARNING ANALYSIS START"
    )


    if (
        recommendation_history is None
        or recommendation_history.empty
    ):

        return {

            "Investment Score Analysis":
                pd.DataFrame(),

            "Signal Analysis":
                pd.DataFrame(),

            "Component Analysis":
                pd.DataFrame()

        }



    df = (
        recommendation_history
        .copy()
    )



    investment_analysis = analyse_score_bucket(
        df,
        "Investment Score"
    )


    signal_analysis = analyse_signal_performance(
        df
    )


    component_analysis = analyse_components(
        df
    )



    print(
        "INVESTMENT SCORE ANALYSIS"
    )

    print(
        investment_analysis
    )


    print(
        "SIGNAL ANALYSIS"
    )

    print(
        signal_analysis
    )


    print(
        "COMPONENT ANALYSIS"
    )

    print(
        component_analysis
    )



    return {

        "Investment Score Analysis":
            investment_analysis,

        "Signal Analysis":
            signal_analysis,

        "Component Analysis":
            component_analysis

    }