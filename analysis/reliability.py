import pandas as pd


def calculate_reliability_score(
    learning_summary,
    signal,
    sector=None
):

    """
    Adjust score based on historical recommendation success
    """

    default_reliability = 50


    if not learning_summary:
        return default_reliability



    try:

        signal_perf = (
            learning_summary
            .get(
                "Signal Performance",
                pd.DataFrame()
            )
        )


        if isinstance(
            signal_perf,
            pd.DataFrame
        ):

            match = signal_perf[
                signal_perf["Signal"]
                ==
                signal
            ]


            if not match.empty:

                return float(
                    match.iloc[0]
                    [
                    "Win Rate %"
                    ]
                )


    except Exception:

        pass



    return default_reliability



def adjust_investment_score(
    investment_score,
    reliability
):

    """
    Reliability multiplier

    50% reliability = neutral
    >50 improves score
    <50 reduces score
    """

    multiplier = (
        0.75
        +
        (
            reliability / 100
        )
        *
        0.5
    )


    adjusted = (
        investment_score
        *
        multiplier
    )


    return round(
        min(
            adjusted,
            100
        ),
        1
    )