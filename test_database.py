import pandas as pd
from data.database import get_connection

conn = get_connection()

print(pd.read_sql_query(
    "SELECT * FROM outcomes LIMIT 5",
    conn
))

conn.close()