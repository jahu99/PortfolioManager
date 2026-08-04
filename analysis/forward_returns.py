import pandas as pd


def calculate_forward_returns(
    df,
    price_column="Close"
):
    """
    Adds forward performance outcomes.

    Required columns:
        Ticker
        Date
        Close

    Adds:
        Forward Return 5D
        Forward Return 10D
    """

    if df is None or df.empty:
        return df


    df = df.copy()


    required = [
        "Ticker",
        "Date",
        price_column
    ]


    for col in required:
        if col not in df.columns:
            return df


    df["Date"] = pd.to_datetime(
        df["Date"],
        errors="coerce"
    )


    df[price_column] = pd.to_numeric(
        df[price_column],
        errors="coerce"
    )


    df = (
        df
        .sort_values(
            [
                "Ticker",
                "Date"
            ]
        )
    )


    df["Forward Return 5D"] = (
        df
        .groupby("Ticker")[price_column]
        .shift(-5)
        /
        df[price_column]
        -
        1
    ) * 100


    df["Forward Return 10D"] = (
        df
        .groupby("Ticker")[price_column]
        .shift(-10)
        /
        df[price_column]
        -
        1
    ) * 100


    return df