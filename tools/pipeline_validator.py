def validate_dataframe(df, name, required_columns):

    print("\n-----------------------")
    print(f"VALIDATING {name}")
    print("-----------------------")

    if df is None:
        print("ERROR: dataframe is None")
        return False

    print("Shape:", df.shape)

    missing = [
        c for c in required_columns
        if c not in df.columns
    ]

    if missing:
        print("MISSING COLUMNS:", missing)
        return False

    print("Columns OK")

    return True