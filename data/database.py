import sqlite3
import os
from datetime import datetime



# ---------------------------------
# Database location
# ---------------------------------

DATABASE_PATH = os.path.join(
    os.path.dirname(__file__),
    "portfolio_manager.db"
)



# ---------------------------------
# Connection
# ---------------------------------

def get_connection():

    return sqlite3.connect(
        DATABASE_PATH
    )



# ---------------------------------
# Initialise database
# ---------------------------------

def initialise_database():

    conn = get_connection()

    cursor = conn.cursor()



    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS recommendations
        (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            date TEXT,

            ticker TEXT,

            signal TEXT,

            investment_score INTEGER,

            technical_score INTEGER,

            quality_score INTEGER,

            price REAL,

            evaluated INTEGER DEFAULT 0

        )
        """
    )



    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS outcomes
        (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            recommendation_id INTEGER,

            check_date TEXT,

            price REAL,

            return_percent REAL,

            days_after INTEGER,

            FOREIGN KEY(
                recommendation_id
            )
            REFERENCES recommendations(id)

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

            FOREIGN KEY(
                recommendation_id
            )
            REFERENCES recommendations(id)

        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS recommendation_learning (

       id INTEGER PRIMARY KEY AUTOINCREMENT,

        ticker TEXT,

        recommendation_date TEXT,

        signal TEXT,

        investment_score INTEGER,

        confidence_score REAL,

        entry_price REAL,

        exit_price REAL,

        return_percent REAL,

        outcome TEXT,

        evaluation_period INTEGER,

        created_at TEXT

        )
        """
    )

    conn.commit()

    conn.close()



    print(
        "Database initialised"
    )



# ---------------------------------
# Save recommendations
# ---------------------------------

def save_recommendations(
    stock_results
):


    if not stock_results:

        return



    conn = get_connection()

    cursor = conn.cursor()



    today = datetime.now().strftime(
        "%Y-%m-%d"
    )



    # Prevent duplicate daily saves

    cursor.execute(
        """
        SELECT COUNT(*)

        FROM recommendations

        WHERE date = ?

        """,
        (
            today,
        )
    )


    existing = cursor.fetchone()[0]



    if existing > 0:

        print(
            f"Recommendations already saved for {today}. Skipping database update"
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

                price, 

                confidence, 

                confidence_score, 
                
                confidence_reasons

            )

            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

            """,
            (

                today,

                stock["Ticker"],

                stock["Signal"],

                stock["Investment Score"],

                stock["Technical Score"],

                stock["Quality Score"],

                stock["Price"],

                stock["Confidence"],

                stock["Confidence Score"],

                str(stock["Confidence Reasons"])

            )
        )


        saved += 1



    conn.commit()

    conn.close()



    print(
        f"Saved {saved} recommendations"
    )



# ---------------------------------
# Save recommendation outcomes
# ---------------------------------

def save_outcomes(outcomes):

    if outcomes is None:
        return

    if outcomes.empty:
        return


    conn = get_connection()

    cursor = conn.cursor()


    for _, row in outcomes.iterrows():

        
        # Prevent duplicate outcome records

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM outcomes
            WHERE recommendation_id = ?
            AND days_after = ?
            """,
            (
                row["recommendation_id"],
                row["days_after"]
            )
        )
        existing = cursor.fetchone()[0]

        if existing == 0:
             continue

        cursor.execute(
            """
            INSERT INTO outcomes
            (
                recommendation_id,
                check_date,
                price,
                return_percent,
                days_after
            )

            VALUES (?, ?, ?, ?, ?)

            """,
            (
                row["recommendation_id"],
                row["evaluation_date"],
                row["price"],
                row["return_percent"],
                row["days_after"]
            )
        )


    conn.commit()

    conn.close()

# ---------------------------------
# Mark recommendation evaluated
# ---------------------------------

def mark_recommendation_evaluated(
    recommendation_id
):

    conn = get_connection()

    cursor = conn.cursor()


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


    conn.commit()

    conn.close()

# ---------------------------------
# Load recommendation history
# ---------------------------------

def get_recommendation_history():

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
            evaluated
        FROM recommendations
        ORDER BY date DESC
    """

    import pandas as pd

    df = pd.read_sql_query(
        query,
        conn
    )

    conn.close()

    return df


# ---------------------------------
# Save recommendation evaluations
# ---------------------------------

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

        cursor.execute(
            """
            SELECT COUNT(*)

            FROM recommendation_evaluations

            WHERE recommendation_id = ?

            AND days_after = ?

            """,
            (
                row["recommendation_id"],
                row["days_after"]
            )
        )


        exists = cursor.fetchone()[0]


        if exists > 0:
            continue


        cursor.execute(
            """
            INSERT INTO recommendation_evaluations
            (
                recommendation_id,
                evaluation_date,
                days_after,
                price,
                return_percent,
                outcome
            )

            VALUES (?, ?, ?, ?, ?, ?)

            """,
            (
                row["recommendation_id"],
                row["evaluation_date"],
                row["days_after"],
                row["price"],
                row["return_percent"],
                row["outcome"]
            )
        )


        saved += 1


    conn.commit()

    conn.close()


    print(
        f"Saved {saved} recommendation evaluations"
    )
    