import pandas as pd
from datetime import datetime
from data.database import get_connection


def evaluate_recommendations():

    conn = get_connection()

    recommendations = pd.read_sql_query(
        """
        SELECT *
        FROM recommendations
        WHERE evaluated = 0
        """,
        conn
    )

    if recommendations.empty:
        print("No recommendations requiring evaluation")
        conn.close()
        return


    print(
        f"Evaluating {len(recommendations)} recommendations"
    )


    # Placeholder:
    # next step will fetch current prices
    # calculate returns
    # write outcomes


    conn.close()