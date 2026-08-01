import pandas as pd
from data.database import get_connection


def get_adaptive_adjustments():

    """
    Learns from historical recommendation outcomes.

    Returns:
    {
        "BUY": adjustment,
        "SELL": adjustment,
        "HOLD": adjustment,
        "WATCH": adjustment
    }
    """

    print("ADAPTIVE LEARNING ENGINE START")


    try:

        conn = get_connection()


        query = """
        SELECT
            Signal,
            AVG(return_percent) AS avg_return,
            COUNT(*) AS samples
        FROM recommendation_evaluations
        GROUP BY Signal
        """


        df = pd.read_sql(
            query,
            conn
        )


        conn.close()


    except Exception as e:

        print(
            "Adaptive learning failed:",
            e
        )

        return {}


    if df.empty:

        return {}


    adjustments = {}


    for _, row in df.iterrows():

        signal = row["Signal"]

        avg_return = row["avg_return"]

        samples = row["samples"]


        #
        # Only trust signals with enough history
        #

        if samples < 10:

            adjustments[signal] = 0

            continue


        #
        # Convert historical performance
        # into score adjustment
        #

        adjustment = avg_return * 3


        #
        # Limit influence
        #

        adjustment = max(
            min(
                adjustment,
                15
            ),
            -15
        )


        adjustments[signal] = round(
            adjustment,
            2
        )


    print(
        "ADAPTIVE ADJUSTMENTS:",
        adjustments
    )


    return adjustments