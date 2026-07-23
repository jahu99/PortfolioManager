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

        ORDER BY date ASC
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

        ON r.ticker = o.ticker


        GROUP BY r.signal

    """


    df = pd.read_sql_query(
        query,
        conn
    )


    conn.close()


    return df