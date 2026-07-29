import pandas as pd


def calculate_factor_performance(
    historical_data,
    return_period="3M"
):
    """
    Analyse which factors contribute to future performance.

    historical_data:
        Recommendation history dataframe

    return_period:
        1M, 3M, 6M, 12M
    """

    if historical_data is None:
        return pd.DataFrame()


    if historical_data.empty:
        return pd.DataFrame()


    return_column = f"Return_{return_period}"


    if return_column not in historical_data.columns:
        return pd.DataFrame()


    results = []


    factors = {

        "Trend Score": "Trend Score",

        "Momentum Score": "Momentum Score",

        "Quality Score": "Quality Score",

        "Growth Score": "Growth Score",

        "Investment Score": "Investment Score",

        "RSI": "RSI",

        "ROE": "Return on Equity",

        "Revenue Growth": "Revenue Growth",

        "Debt To Equity": "Debt to Equity"

    }


    for name, column in factors.items():


        if column not in historical_data.columns:
            continue


        df = historical_data[
            [
                column,
                return_column
            ]
        ].dropna()


        if len(df) < 10:
            continue


        avg_return = (
            df[return_column]
            .mean()
        )


        win_rate = (
            (
                df[return_column] > 0
            )
            .mean()
            * 100
        )


        correlation = (
            df[column]
            .corr(
                df[return_column]
            )
        )


        results.append(

            {

                "Factor": name,

                "Samples": len(df),

                "Average Return %": round(
                    avg_return,
                    2
                ),

                "Win Rate %": round(
                    win_rate,
                    2
                ),

                "Correlation": round(
                    correlation,
                    3
                )

            }

        )


    result_df = pd.DataFrame(results)


    if not result_df.empty:

        result_df = (
            result_df
            .sort_values(
                "Correlation",
                ascending=False
            )
        )


    return result_df