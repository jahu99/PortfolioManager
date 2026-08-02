from data.database import get_connection
import pandas as pd


def detect_recommendation_changes(today_df):

    conn = get_connection()

    previous = pd.read_sql_query(
        """
        SELECT *
        FROM recommendations
        WHERE id NOT IN (
            SELECT MAX(id)
            FROM recommendations
        )
        """,
        conn
    )

    conn.close()


    if previous.empty:
        return pd.DataFrame()


    events = []


    for _, row in today_df.iterrows():

        ticker = row["Ticker"]

        old = previous[
            previous["ticker"] == ticker
        ]


        if old.empty:
            continue


        old = old.iloc[-1]


        if row["Signal"] != old["signal"]:

            events.append(
                {
                    "Ticker": ticker,
                    "Old Signal": old["signal"],
                    "New Signal": row["Signal"],
                    "Old Score": old["investment_score"],
                    "New Score": row["Investment Score"],
                    "Event": "SIGNAL CHANGE"
                }
            )


    return pd.DataFrame(events)