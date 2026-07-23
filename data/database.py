import sqlite3
import os
from datetime import datetime


DATABASE_FILE = os.path.join(
    os.path.dirname(__file__),
    "portfolio_manager.db"
)



# ---------------------------------
# Connection
# ---------------------------------

def get_connection():

    return sqlite3.connect(
        DATABASE_FILE
    )



# ---------------------------------
# Initialise database
# ---------------------------------

def initialise_database():

    conn = get_connection()

    cursor = conn.cursor()



    # ---------------------------------
    # Recommendations
    # ---------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS recommendations (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            date TEXT NOT NULL,

            ticker TEXT NOT NULL,

            signal TEXT,

            investment_score INTEGER,

            technical_score INTEGER,

            quality_score INTEGER,

            price REAL

        )
        """
    )



    # ---------------------------------
    # Outcomes
    # ---------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS outcomes (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            ticker TEXT NOT NULL,

            check_date TEXT NOT NULL,

            price REAL,

            return_percent REAL

        )
        """
    )



    conn.commit()

    conn.close()



# ---------------------------------
# Save daily recommendations
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



    # ---------------------------------
    # Prevent duplicate daily saves
    # ---------------------------------

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
            f"Recommendations already saved for {today}. Skipping database update."
        )

        conn.close()

        return



    # ---------------------------------
    # Insert recommendations
    # ---------------------------------

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

                price

            )

            VALUES (?, ?, ?, ?, ?, ?, ?)

            """,

            (

                today,

                stock.get(
                    "Ticker"
                ),

                stock.get(
                    "Signal"
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

                stock.get(
                    "Price",
                    0
                )

            )

        )



    conn.commit()

    conn.close()



    print(
        f"Saved {len(stock_results)} recommendations to database"
    )



# ---------------------------------
# Save outcomes
# ---------------------------------

def save_outcomes(
    outcomes
):


    if outcomes is None:

        return



    if outcomes.empty:

        return



    conn = get_connection()

    cursor = conn.cursor()



    for _, row in outcomes.iterrows():


        cursor.execute(
            """

            INSERT INTO outcomes

            (

                ticker,

                check_date,

                price,

                return_percent

            )

            VALUES (?, ?, ?, ?)

            """,

            (

                row["Ticker"],

                row["Check Date"],

                row["Current Price"],

                row["Return %"]

            )

        )



    conn.commit()

    conn.close()



    print(
        f"Saved {len(outcomes)} outcomes"
    )