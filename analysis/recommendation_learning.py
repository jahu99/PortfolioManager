import pandas as pd
import numpy as np


# =====================================================
# Helpers
# =====================================================

def safe_correlation(df, x, y):

    if x not in df.columns:
        return 0

    if y not in df.columns:
        return 0


    data = df[[x, y]].copy()


    data[x] = pd.to_numeric(
        data[x],
        errors="coerce"
    )

    data[y] = pd.to_numeric(
        data[y],
        errors="coerce"
    )


    data = data.dropna()


    if len(data) < 5:
        return 0


    if data[x].nunique() <= 1:
        return 0


    if data[y].nunique() <= 1:
        return 0


    corr = data[x].corr(
        data[y]
    )


    if pd.isna(corr):
        return 0


    return round(
        corr,
        3
    )



def calculate_win_rate(series):

    if len(series) == 0:
        return 0


    return round(
        (
            (series > 0)
            .sum()
            /
            len(series)
        )
        *
        100,
        2
    )



# =====================================================
# Main Recommendation Learning Engine
# =====================================================

def calculate_recommendation_learning(history):


    print(
        "RECOMMENDATION LEARNING ENGINE START"
    )


    if history is None:

        history = pd.DataFrame()



    if history.empty:


        return {

            "Overall":
            {

                "Reliability":
                    "NO DATA"

            }

        }



    df = history.copy()



    print(
        "LEARNING DATASET:",
        df.shape
    )



    # -------------------------------------------------
    # Normalise returns
    # -------------------------------------------------

    for col in [

        "Return %",
        "Forward Return 5D",
        "Forward Return 10D"

    ]:


        if col in df.columns:

            df[col] = pd.to_numeric(
                df[col],
                errors="coerce"
            )



    # -------------------------------------------------
    # Horizon performance
    # -------------------------------------------------

    horizons = {}


    for days, column in [

        (5, "Forward Return 5D"),

        (10, "Forward Return 10D")

    ]:


        if column not in df.columns:

            horizons[days] = {

                "Recommendations":0,
                "Average Return %":0,
                "Win Rate %":0,
                "Reliability":"NO DATA"

            }

            continue



        returns = (
            df[column]
            .dropna()
        )


        horizons[days] = {


            "Recommendations":
                len(returns),


            "Average Return %":
                round(
                    returns.mean(),
                    2
                ),


            "Win Rate %":
                calculate_win_rate(
                    returns
                ),


            "Reliability":

                (
                    "VALID"
                    if len(returns) >= 20
                    else
                    "INSUFFICIENT DATA"
                )

        }



    # -------------------------------------------------
    # Signal performance
    # -------------------------------------------------

    signal_rows = []


    if "Signal" in df.columns:


        for signal, group in df.groupby(
            "Signal"
        ):


            returns = (

                group
                .get(
                    "Forward Return 5D",
                    pd.Series()
                )
                .dropna()

            )


            signal_rows.append(

                {

                "Signal":
                    signal,


                "Recommendations":
                    len(returns),


                "Average Return %":
                    round(
                        returns.mean()
                        if len(returns)
                        else 0,
                        2
                    ),


                "Win Rate %":
                    calculate_win_rate(
                        returns
                    )

                }

            )



    # -------------------------------------------------
    # Component analysis
    # NOTE:
    # Reporting only.
    # Weight changes handled by weight_optimizer.py
    # -------------------------------------------------

    component_rows = []


    for component in [

        "Investment Score",

        "Technical Score",

        "Quality Score",

        "Growth Score",

        "Confidence Score"

    ]:


        component_rows.append(

            {

            "Component":
                component,


            "Correlation":
                safe_correlation(

                    df,

                    component,

                    "Forward Return 5D"

                )

            }

        )



    # -------------------------------------------------
    # Overall
    # -------------------------------------------------

    returns = (

        df
        .get(
            "Forward Return 5D",
            pd.Series()
        )
        .dropna()

    )


    overall = {


        "Total Recommendations":

            len(returns),


        "Successful Recommendations":

            int(
                (
                    returns > 0
                )
                .sum()
            ),


        "Failed Recommendations":

            int(
                (
                    returns <= 0
                )
                .sum()
            ),


        "Win Rate %":

            calculate_win_rate(
                returns
            ),


        "Average Return %":

            round(
                returns.mean()
                if len(returns)
                else 0,
                2
            ),


        "Reliability":

            (
                "VALID"
                if len(returns) >= 20
                else
                "NO DATA"
            )

    }



    print(
        "RECOMMENDATION LEARNING COMPLETE"
    )


    return {


        "Overall":
            overall,


        "Horizon Learning":
            horizons,


        "Signal Performance":
            pd.DataFrame(
                signal_rows
            ),


        "Component Score Performance":
            pd.DataFrame(
                component_rows
            )

    }