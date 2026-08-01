import sqlite3
import os
import pandas as pd
from datetime import datetime


DATABASE_PATH = os.path.join(
    os.path.dirname(__file__),
    "portfolio_manager.db"
)


# -------------------------------------------------
# Connection
# -------------------------------------------------

def get_connection():

    return sqlite3.connect(
        DATABASE_PATH
    )



# -------------------------------------------------
# Initialise database
# -------------------------------------------------

def initialise_database():

    conn = get_connection()
    cursor = conn.cursor()


    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS recommendations
        (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            date TEXT NOT NULL,

            ticker TEXT NOT NULL,

            signal TEXT,

            investment_score INTEGER,

            technical_score INTEGER,

            quality_score INTEGER,

            price REAL,

            confidence TEXT,

            confidence_score REAL,

            confidence_reasons TEXT,

            evaluated INTEGER DEFAULT 0
        )
        """
    )


    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS recommendation_evaluations
        (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            recommendation_id INTEGER,

            evaluation_date TEXT,

            days_after INTEGER,

            price REAL,

            return_percent REAL,

            outcome TEXT,

            success INTEGER,

            FOREIGN KEY(
                recommendation_id
            )
            REFERENCES recommendations(id)

        )
        """
    )


    conn.commit()
    conn.close()


    print(
        "Database initialised"
    )



# -------------------------------------------------
# Save recommendations
# -------------------------------------------------

def save_recommendations(
    stock_results
):

    if not stock_results:
        return


    conn = get_connection()
    cursor = conn.cursor()


    today = datetime.today().strftime(
        "%Y-%m-%d"
    )


    cursor.execute(
        """
        SELECT COUNT(*)
        FROM recommendations
        WHERE date = ?
        """,
        (today,)
    )


    if cursor.fetchone()[0] > 0:

        print(
            "Recommendations already saved for today"
        )

        conn.close()
        return



    saved = 0


    for stock in stock_results:


        cursor.execute(
            """
            INSERT INTO recommendations
            (

                date,
                ticker,
                signal,
                investment_score,
                technical_score,
                quality_score,
                growth_score,
                price,
                confidence,
                confidence_score,
                confidence_reasons

            )

            VALUES (?,?,?,?,?,?,?,?,?,?,?)

            """,

            (

                today,

                stock["Ticker"],

                stock.get(
                    "Signal",
                    ""
                ),

                stock.get(
                    "Investment Score",
                    0
                ),

                stock.get(
                    "Technical Score",
                    0
                ),

                stock.get(
                    "Quality Score",
                    0
                ),

                stock.get("Growth Score", 0),

                stock.get(
                    "Price",
                    0
                ),

                stock.get(
                    "Confidence",
                    ""
                ),

                stock.get(
                    "Confidence Score",
                    0
                ),

                str(
                    stock.get(
                        "Confidence Reasons",
                        []
                    )
                )

            )

        )


        saved += 1



    conn.commit()
    conn.close()


    print(
        f"Saved {saved} recommendations"
    )



# -------------------------------------------------
# Get open recommendations
# -------------------------------------------------

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
            price,
            confidence,
            confidence_score,
            confidence_reasons

        FROM recommendations

        WHERE evaluated = 0

        AND date <= DATE('now','-5 days')

        ORDER BY date ASC
        """


    df = pd.read_sql_query(
        query,
        conn
    )


    conn.close()


    return df



# -------------------------------------------------
# Save evaluations
# -------------------------------------------------

def save_recommendation_evaluations(
    evaluations
):

    if evaluations is None:
        return

    if evaluations.empty:
        return


    conn = get_connection()
    cursor = conn.cursor()


    saved = 0


    for _, row in evaluations.iterrows():


        recommendation_id = row[
            "recommendation_id"
        ]

        days_after = row[
            "days_after"
        ]


        cursor.execute(
            """
            SELECT COUNT(*)
            FROM recommendation_evaluations
            WHERE recommendation_id = ?
            AND days_after = ?
            """,
            (
                recommendation_id,
                days_after
            )
        )


        exists = cursor.fetchone()[0]


        if exists:
            continue



        cursor.execute(
            """
            INSERT INTO recommendation_evaluations
            (
                recommendation_id,
                ticker,
                evaluation_date,
                days_after,
                price,
                return_percent,
                outcome,
                signal,
                investment_score,
                technical_score,
                quality_score
            )

            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

            """,
            (
                row["recommendation_id"],
                row["ticker"],
                row["evaluation_date"],
                row["days_after"],
                row["price"],
                row["return_percent"],
                row["outcome"],
                row.get("Signal"),
                row.get("Investment Score"),
                row.get("Technical Score"),
                row.get("Quality Score")
            )
        )


        cursor.execute(
            """
            UPDATE recommendations
            SET evaluated = 1
            WHERE id = ?
            """,
            (
                recommendation_id,
            )
        )


        saved += 1



    conn.commit()
    conn.close()


    print(
        f"Saved {saved} recommendation evaluations"
    )


# -------------------------------------------------
# Evaluation history
# -------------------------------------------------

def get_evaluation_history():


    conn = get_connection()


    df = pd.read_sql_query(

        """

        SELECT

            *

        FROM recommendation_evaluations

        ORDER BY evaluation_date DESC

        """,

        conn

    )


    conn.close()


    return df