import sqlite3
import pandas as pd
from datetime import datetime

from data.database import get_connection



# ---------------------------------
# Get recommendations that need checking
# ---------------------------------

def get_open_recommendations():

    conn = get_connection()


    query = """
        SELECT

            id,

            date,

            ticker,

            signal,

            investment_score,

            technical_score,

            quality_score,

            price

        FROM recommendations

        WHERE evaluated = 0

        ORDER BY date ASC
    """


    df = pd.read_sql_query(
        query,
        conn
    )


    conn.close()


    return df

    conn = get_connection()


    query = """
        SELECT

            r.id,

            r.date,

            r.ticker,

            r.signal,

            r.investment_score,

            r.technical_score,

            r.quality_score,

            r.price

        FROM recommendations r


        WHERE r.id NOT IN (

            SELECT recommendation_id

            FROM recommendation_evaluations

        )


        ORDER BY r.date ASC

    """

    df = pd.read_sql_query(
        query,
        conn
    )


    conn.close()


    return df



# ---------------------------------
# Get recommendation history
# ---------------------------------

def get_recommendation_history():

    conn = get_connection()


    query = """
        SELECT

            *

        FROM recommendations

        ORDER BY date DESC
    """


    df = pd.read_sql_query(
        query,
        conn
    )


    conn.close()


    return df



# ---------------------------------
# Get performance summary
# ---------------------------------

def get_performance_summary():

    conn = get_connection()


    query = """

        SELECT

            signal AS Signal,

            days_after AS Days_After,

            COUNT(id) AS Evaluations,


            ROUND(
                AVG(return_percent),
                2
            ) AS Average_Return_Percent,


            ROUND(
                SUM(
                    CASE
                        WHEN return_percent > 0
                        THEN 1
                        ELSE 0
                    END
                ) * 100.0 / COUNT(id),
                2
            ) AS Win_Rate_Percent


        FROM recommendation_evaluations


        GROUP BY

            signal,

            days_after


        ORDER BY

            days_after ASC,

            Average_Return_Percent DESC

    """


    df = pd.read_sql_query(
        query,
        conn
    )


    conn.close()


    return df

    conn = get_connection()


    query = """
        SELECT

            r.signal AS Signal,

            COUNT(o.id) AS Recommendations,

            ROUND(
                AVG(o.return_percent),
                2
            ) AS Average_Return_Percent,

            ROUND(
                SUM(
                    CASE
                        WHEN o.return_percent > 0
                        THEN 1
                        ELSE 0
                    END
                ) * 100.0 / COUNT(o.id),
                2
            ) AS Win_Rate_Percent


        FROM recommendations r


        JOIN outcomes o

        ON r.id = o.recommendation_id


        GROUP BY r.signal


        ORDER BY Average_Return_Percent DESC

    """


    df = pd.read_sql_query(
        query,
        conn
    )


    conn.close()


    return df

    conn = get_connection()


    query = """
        SELECT

            r.signal AS Signal,

            COUNT(o.id) AS Recommendations,

            ROUND(
                AVG(o.return_percent),
                2
            ) AS Average_Return_Percent,

            ROUND(
                SUM(
                    CASE
                        WHEN o.return_percent > 0
                        THEN 1
                        ELSE 0
                    END
                ) * 100.0 / COUNT(o.id),
                2
            ) AS Win_Rate_Percent


        FROM recommendations r


        JOIN outcomes o

        ON r.ticker = o.ticker


        GROUP BY r.signal

        ORDER BY Average_Return_Percent DESC

    """


    df = pd.read_sql_query(
        query,
        conn
    )


    conn.close()


    return df

    conn = get_connection()


    query = """
        SELECT

            r.signal,

            COUNT(o.id) AS Count,

            ROUND(
                AVG(o.return_percent),
                2
            ) AS Average_Return,

            ROUND(
                SUM(
                    CASE
                        WHEN o.return_percent > 0
                        THEN 1
                        ELSE 0
                    END
                ) * 100.0 / COUNT(o.id),
                2
            ) AS Win_Rate


        FROM recommendations r


        JOIN outcomes o

        ON r.id = o.recommendation_id


        GROUP BY r.signal

    """


    df = pd.read_sql_query(
        query,
        conn
    )


    conn.close()


    return df

def get_signal_performance():

    conn = get_connection()


    query = """

        SELECT

            signal AS Signal,

            COUNT(id) AS Evaluations,


            ROUND(
                AVG(return_percent),
                2
            ) AS Average_Return_Percent,


            ROUND(
                SUM(
                    CASE
                        WHEN outcome = 'WIN'
                        THEN 1
                        ELSE 0
                    END
                ) * 100.0 / COUNT(id),
                2
            ) AS Win_Rate_Percent


        FROM recommendation_evaluations


        GROUP BY signal


        ORDER BY Average_Return_Percent DESC

    """


    df = pd.read_sql_query(
        query,
        conn
    )


    conn.close()


    return df

def get_horizon_performance():

    conn = get_connection()


    query = """

        SELECT

            days_after AS Days_After,

            COUNT(id) AS Evaluations,


            ROUND(
                AVG(return_percent),
                2
            ) AS Average_Return_Percent,


            ROUND(
                SUM(
                    CASE
                        WHEN outcome = 'WIN'
                        THEN 1
                        ELSE 0
                    END
                ) * 100.0 / COUNT(id),
                2
            ) AS Win_Rate_Percent


        FROM recommendation_evaluations


        GROUP BY days_after


        ORDER BY days_after ASC

    """


    df = pd.read_sql_query(
        query,
        conn
    )


    conn.close()


    return df

def get_score_performance():

    conn = get_connection()


    query = """

        SELECT

            CASE

                WHEN r.investment_score >= 80
                THEN '80-100'


                WHEN r.investment_score >= 70
                THEN '70-79'


                ELSE '<70'

            END AS Score_Band,


            COUNT(e.id) AS Evaluations,


            ROUND(
                AVG(e.return_percent),
                2
            ) AS Average_Return_Percent,


            ROUND(
                SUM(
                    CASE
                        WHEN e.outcome = 'WIN'
                        THEN 1
                        ELSE 0
                    END
                ) * 100.0 / COUNT(e.id),
                2
            ) AS Win_Rate_Percent


        FROM recommendation_evaluations e


        JOIN recommendations r

        ON e.recommendation_id = r.id


        GROUP BY Score_Band


        ORDER BY Average_Return_Percent DESC

    """


    df = pd.read_sql_query(
        query,
        conn
    )


    conn.close()


    return df

def get_signal_horizon_performance():

    conn = get_connection()


    query = """

        SELECT

            signal AS Signal,

            days_after AS Days_After,

            COUNT(id) AS Evaluations,


            ROUND(
                AVG(return_percent),
                2
            ) AS Average_Return_Percent,


            ROUND(
                SUM(
                    CASE
                        WHEN outcome = 'WIN'
                        THEN 1
                        ELSE 0
                    END
                ) * 100.0 / COUNT(id),
                2
            ) AS Win_Rate_Percent


        FROM recommendation_evaluations


        GROUP BY
            signal,
            days_after


        ORDER BY
            signal,
            days_after

    """


    df = pd.read_sql_query(
        query,
        conn
    )


    conn.close()


    return df

def get_score_horizon_performance():

    conn = get_connection()


    query = """

        SELECT


            CASE

                WHEN r.investment_score >= 80
                THEN '80-100'


                WHEN r.investment_score >= 70
                THEN '70-79'


                ELSE '<70'


            END AS Score_Band,


            e.days_after AS Days_After,


            COUNT(e.id) AS Evaluations,


            ROUND(
                AVG(e.return_percent),
                2
            ) AS Average_Return_Percent,


            ROUND(
                SUM(
                    CASE
                        WHEN e.outcome = 'WIN'
                        THEN 1
                        ELSE 0
                    END
                ) * 100.0 / COUNT(e.id),
                2
            ) AS Win_Rate_Percent


        FROM recommendation_evaluations e


        JOIN recommendations r

        ON e.recommendation_id = r.id


        GROUP BY

            Score_Band,

            e.days_after


        ORDER BY

            Score_Band,

            e.days_after

    """


    df = pd.read_sql_query(
        query,
        conn
    )


    conn.close()


    return df

def get_score_bucket_performance():

    import pandas as pd
    from data.database import get_connection


    conn = get_connection()


    query = """
    SELECT
        r.investment_score,
        e.return_percent

    FROM recommendations r

    JOIN recommendation_evaluations e

        ON r.id = e.recommendation_id

    WHERE r.investment_score IS NOT NULL

    AND e.return_percent IS NOT NULL
    """


    df = pd.read_sql_query(
        query,
        conn
    )


    conn.close()


    if df.empty:

        return pd.DataFrame()



    def score_bucket(score):

        if score >= 90:
            return "90-100"

        elif score >= 80:
            return "80-89"

        elif score >= 70:
            return "70-79"

        elif score >= 60:
            return "60-69"

        else:
            return "<60"



    df["Score Bucket"] = (
        df["investment_score"]
        .apply(score_bucket)
    )


    summary = (
        df
        .groupby("Score Bucket")
        .agg(

            Evaluations=(
                "return_percent",
                "count"
            ),

            Average_Return_Percent=(
                "return_percent",
                "mean"
            ),

            Win_Rate_Percent=(
                "return_percent",
                lambda x:
                    (x > 0).mean() * 100
            )
        )
        .reset_index()
    )


    summary[
        "Average_Return_Percent"
    ] = summary[
        "Average_Return_Percent"
    ].round(2)


    summary[
        "Win_Rate_Percent"
    ] = summary[
        "Win_Rate_Percent"
    ].round(2)



    return summary

def get_component_score_performance():

    import pandas as pd
    from data.database import get_connection


    conn = get_connection()


    query = """
    SELECT

        r.technical_score,
        r.quality_score,
        e.return_percent

    FROM recommendations r

    JOIN recommendation_evaluations e

        ON r.id = e.recommendation_id

    WHERE e.return_percent IS NOT NULL

    AND r.technical_score IS NOT NULL

    AND r.quality_score IS NOT NULL

    """


    df = pd.read_sql_query(
        query,
        conn
    )


    conn.close()



    if df.empty:

        return pd.DataFrame()



    results = []



    def bucket(score):

        if score >= 90:
            return "90-100"

        elif score >= 80:
            return "80-89"

        elif score >= 70:
            return "70-79"

        elif score >= 60:
            return "60-69"

        else:
            return "<60"



    for component in [
        "Technical Score",
        "Quality Score"
    ]:


        column = (
            "technical_score"
            if component == "Technical Score"
            else "quality_score"
        )


        temp = df.copy()


        temp["Score Bucket"] = (
            temp[column]
            .apply(bucket)
        )


        summary = (
            temp
            .groupby("Score Bucket")
            .agg(

                Evaluations=(
                    "return_percent",
                    "count"
                ),

                Average_Return_Percent=(
                    "return_percent",
                    "mean"
                ),

                Win_Rate_Percent=(
                    "return_percent",
                    lambda x:
                        (x > 0).mean() * 100
                )

            )
            .reset_index()
        )


        summary.insert(
            0,
            "Component",
            component
        )


        results.append(
            summary
        )



    output = pd.concat(
        results,
        ignore_index=True
    )


    output[
        "Average_Return_Percent"
    ] = output[
        "Average_Return_Percent"
    ].round(2)


    output[
        "Win_Rate_Percent"
    ] = output[
        "Win_Rate_Percent"
    ].round(2)



    return output

def get_signal_horizon_performance():

    import pandas as pd
    from data.database import get_connection


    conn = get_connection()


    query = """

    SELECT

        r.signal,

        e.days_after,

        e.return_percent

    FROM recommendations r


    JOIN recommendation_evaluations e

        ON r.id = e.recommendation_id


    WHERE e.return_percent IS NOT NULL

    """



    df = pd.read_sql_query(
        query,
        conn
    )


    conn.close()



    if df.empty:

        return pd.DataFrame()



    summary = (

        df

        .groupby(
            [
                "signal",
                "days_after"
            ]
        )

        .agg(

            Evaluations=(
                "return_percent",
                "count"
            ),

            Average_Return_Percent=(
                "return_percent",
                "mean"
            ),

            Win_Rate_Percent=(
                "return_percent",
                lambda x:
                (x > 0).mean() * 100
            )

        )

        .reset_index()

    )



    summary[
        "Average_Return_Percent"
    ] = summary[
        "Average_Return_Percent"
    ].round(2)



    summary[
        "Win_Rate_Percent"
    ] = summary[
        "Win_Rate_Percent"
    ].round(2)



    return summary