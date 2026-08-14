import pandas as pd


# ============================================================
# SECTOR ANALYSIS
# ============================================================

def analyse_sectors(
    portfolio_summary,
    stock_results=None
):

    sector_results = []


    if (
        portfolio_summary is None
        or
        portfolio_summary.empty
    ):

        return pd.DataFrame()


    # ========================================================
    # BUILD SECTOR LOOKUP
    # ========================================================

    sector_lookup = {}


    if stock_results is not None:

        if isinstance(
            stock_results,
            pd.DataFrame
        ):

            rows = stock_results.to_dict(
                "records"
            )

        elif isinstance(
            stock_results,
            list
        ):

            rows = stock_results

        else:

            rows = []


        for row in rows:

            if not isinstance(
                row,
                dict
            ):
                continue


            ticker = str(
                row.get(
                    "Ticker",
                    ""
                )
            ).upper().strip()


            if ticker == "":
                continue


            sector_lookup[ticker] = row.get(
                "Sector",
                "Unknown"
            )


    # ========================================================
    # PROCESS HOLDINGS
    # ========================================================

    for _, holding in portfolio_summary.iterrows():

        ticker = str(
            holding.get(
                "Ticker",
                ""
            )
        ).upper().strip()


        value = pd.to_numeric(
            holding.get(
                "Current Value",
                0
            ),
            errors="coerce"
        )


        if pd.isna(value):

            value = 0.0


        # ----------------------------------------------------
        # CASH
        # ----------------------------------------------------

        if ticker == "CASH":

            sector = "Cash"


        # ----------------------------------------------------
        # ETF
        # ----------------------------------------------------

        elif holding.get(
            "Type",
            ""
        ) == "ETF":

            sector = "ETF"


        # ----------------------------------------------------
        # EXISTING PORTFOLIO DATA
        # ----------------------------------------------------

        elif (
            "Sector" in holding.index
            and
            pd.notna(
                holding["Sector"]
            )
            and
            str(
                holding["Sector"]
            ).strip()
            not in [
                "",
                "Unknown",
                "nan"
            ]
        ):

            sector = str(
                holding["Sector"]
            )


        # ----------------------------------------------------
        # SCANNER LOOKUP
        # ----------------------------------------------------

        elif ticker in sector_lookup:

            sector = sector_lookup[
                ticker
            ]

            if not sector:

                sector = "Unknown"


        # ----------------------------------------------------
        # FALLBACK
        # ----------------------------------------------------

        else:

            sector = "Unknown"


        sector_results.append({

            "Ticker":
                ticker,

            "Sector":
                sector,

            "Current Value":
                float(value)

        })


    # ========================================================
    # DATAFRAME
    # ========================================================

    sector_df = pd.DataFrame(
        sector_results
    )


    if sector_df.empty:

        return sector_df


    # ========================================================
    # TOTAL VALUE
    # ========================================================

    total_value = float(
        sector_df[
            "Current Value"
        ].sum()
    )


    if total_value <= 0:

        sector_df[
            "Allocation %"
        ] = 0.0

    else:

        sector_df[
            "Allocation %"
        ] = (
            sector_df[
                "Current Value"
            ]
            /
            total_value
            *
            100
        ).round(2)


    # ========================================================
    # SECTOR SUMMARY
    # ========================================================

    sector_summary = (
        sector_df
        .groupby(
            "Sector",
            as_index=False
        )[
            "Current Value"
        ]
        .sum()
    )


    sector_summary[
        "Allocation %"
    ] = (
        sector_summary[
            "Current Value"
        ]
        /
        total_value
        *
        100
    ).round(2)


    return sector_summary