import sqlite3
import pandas as pd

DB = "portfolio_manager.db"

conn = sqlite3.connect(DB)

print("\nDATABASE TABLES")
print("=" * 80)

tables = pd.read_sql_query(
    """
    SELECT name
    FROM sqlite_master
    WHERE type='table'
    ORDER BY name
    """,
    conn
)

print(tables.to_string(index=False))

for table in tables["name"]:

    print("\n")
    print("=" * 80)
    print(f"TABLE: {table}")
    print("=" * 80)

    try:

        columns = pd.read_sql_query(
            f'PRAGMA table_info("{table}")',
            conn
        )

        print("\nCOLUMNS:")
        print(
            columns[
                ["name", "type"]
            ].to_string(index=False)
        )

        count = pd.read_sql_query(
            f'SELECT COUNT(*) AS rows FROM "{table}"',
            conn
        )

        print(
            "\nROWS:",
            count.iloc[0]["rows"]
        )

        sample = pd.read_sql_query(
            f'SELECT * FROM "{table}" LIMIT 5',
            conn
        )

        print("\nSAMPLE:")
        print(sample.to_string(index=False))

    except Exception as e:

        print(
            f"Could not inspect {table}: {e}"
        )


conn.close()