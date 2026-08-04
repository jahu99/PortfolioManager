import pandas as pd

from data.database import get_connection



def get_reliability(count):

    if count < 20:
        return 0

    return 1



def get_adaptive_adjustments():

    """
    Converts historical recommendation performance
    into scoring adjustments.

    Returns:

    {
       ("BUY","High","Technology"): -5,
       ("WATCH","Good","Financial Services"): +3
    }

    """

    print(
        "ADAPTIVE LEARNING ENGINE START"
    )


    try:

        conn = get_connection()


        query = """

        SELECT

            Signal,

            Investment_Score,

            Sector,

            AVG(return_percent) AS avg_return,

            COUNT(*) AS samples


        FROM recommendation_evaluations


        GROUP BY

            Signal,

            Investment_Score,

            Sector

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


        samples = int(
            row["samples"]
        )


        if samples < 20:

            continue



        signal = row["Signal"]


        sector = row["Sector"]



        score = float(
            row["Investment_Score"]
        )


        avg_return = float(
            row["avg_return"]
        )



        # score bucket

        if score >= 85:

            bucket = "High"

        elif score >= 70:

            bucket = "Good"

        elif score >= 50:

            bucket = "Medium"

        else:

            bucket = "Low"



        #
        # Convert performance
        # into score adjustment
        #

        adjustment = avg_return * 5



        adjustment = max(

            min(

                adjustment,

                10

            ),

            -10

        )



        adjustments[

            (
                signal,
                bucket,
                sector

            )

        ] = round(

            adjustment,

            2

        )



    print(

        "ADAPTIVE ADJUSTMENTS:",

        adjustments

    )


    return adjustments