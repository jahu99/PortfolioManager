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