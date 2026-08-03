# portfolio/portfolio.py

import pandas as pd
from pathlib import Path


HOLDINGS_FILE = Path(
    "portfolio/holdings_raw.csv"
)


def get_portfolio():

    """
    Load current Revolut portfolio.

    Expected CSV:

    Ticker,Name,Quantity,Market Value

    Returns:

    Ticker
    Name
    Shares
    Current Value
    Allocation %
    """

    if not HOLDINGS_FILE.exists():

        raise FileNotFoundError(
            f"Missing file: {HOLDINGS_FILE}"
        )


    df = pd.read_csv(
        HOLDINGS_FILE
    )


    required = [

        "Ticker",
        "Name",
        "Quantity",
        "Market Value"

    ]


    missing = [

        c for c in required
        if c not in df.columns

    ]


    if missing:

        raise ValueError(
            f"Missing columns: {missing}"
        )



    # -----------------------------
    # Clean fields
    # -----------------------------

    df["Ticker"] = (

        df["Ticker"]
        .astype(str)
        .str.upper()
        .str.strip()

    )


    df["Quantity"] = pd.to_numeric(

        df["Quantity"],

        errors="coerce"

    )


    df["Market Value"] = pd.to_numeric(

        df["Market Value"],

        errors="coerce"

    )



    # Remove invalid rows

    df = df.dropna(

        subset=[

            "Ticker",
            "Market Value"

        ]

    )



    # Remove TOTAL row if present

    df = df[

        ~df["Ticker"].isin(
            [
                "TOTAL"
            ]
        )

    ]



    # -----------------------------
    # Calculate allocation
    # -----------------------------

    total = df[
        "Market Value"
    ].sum()



    if total <= 0:

        raise ValueError(
            "Portfolio value invalid"
        )



    df["Allocation %"] = (

        df["Market Value"]

        /

        total

        *

        100

    ).round(2)



    # -----------------------------
    # Rename for reporting
    # -----------------------------

    df = df.rename(

        columns={

            "Quantity":
                "Shares",

            "Market Value":
                "Current Value"

        }

    )



    return df



def get_portfolio_value():

    df = get_portfolio()


    return round(

        df["Current Value"]
        .sum(),

        2

    )