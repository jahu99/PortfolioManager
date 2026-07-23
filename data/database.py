import sqlite3
import os
from datetime import datetime


DATABASE_FILE = os.path.join(
    os.path.dirname(__file__),
    "portfolio_manager.db"
)



def get_connection():

    return sqlite3.connect(
        DATABASE_FILE
    )



def initialise_database():

    conn = get_connection()

    cursor = conn.cursor()


    # ---------------------------------
    # Recommendations table
    # ---------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS recommendations (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            date TEXT,

            ticker TEXT,

            signal TEXT,

            investment_score INTEGER,

            technical_score INTEGER,

            quality_score INTEGER,

            price REAL

        )
        """
    )



    # ---------------------------------
    # Future outcomes table
    # ---------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS outcomes (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            recommendation_id INTEGER,

            check_date TEXT,

            price REAL,

            return_percent REAL,

            FOREIGN KEY(
                recommendation_id
            )
            REFERENCES recommendations(id)

        )
        """
    )



    conn.commit()

    conn.close()



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