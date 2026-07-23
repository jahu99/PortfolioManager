import pandas as pd



def generate_rebalance_recommendations(
    portfolio_summary,
    sector_optimisation,
    stock_results
):

    recommendations = []


    if (
        portfolio_summary is None
        or portfolio_summary.empty
        or sector_optimisation is None
        or sector_optimisation.empty
    ):
        return pd.DataFrame()



    # ---------------------------------
    # Identify sector actions
    # ---------------------------------

    sectors_to_add = []
    sectors_to_reduce = []


    for _, row in sector_optimisation.iterrows():

        action = row.get(
            "Action",
            ""
        )

        sector = row.get(
            "Sector",
            "Unknown"
        )


        if action == "ADD":

            sectors_to_add.append(
                sector
            )


        elif action == "REDUCE":

            sectors_to_reduce.append(
                sector
            )



    # ---------------------------------
    # REDUCE recommendations
    # ---------------------------------

    for sector in sectors_to_reduce:


        sector_holdings = portfolio_summary[
            portfolio_summary["Sector"] == sector
        ]


        if sector_holdings.empty:

            continue



        # weakest holding in overweight sector

        if "Investment Score" in sector_holdings.columns:

            weakest = sector_holdings.sort_values(
                by="Investment Score",
                ascending=True
            ).iloc[0]

        else:

            weakest = sector_holdings.iloc[0]



        ticker = weakest.get(
            "Ticker",
            ""
        )


        if ticker == "":

            continue



        recommendations.append(
            {

                "Action":
                    "REDUCE",

                "Ticker":
                    ticker,

                "Sector":
                    sector,

                "Investment Score":
                    weakest.get(
                        "Investment Score",
                        None
                    ),

                "Allocation %":
                    weakest.get(
                        "Allocation %",
                        None
                    ),

                "Reason":
                    (
                        f"{sector} overweight. "
                        "Reduce weakest holding first."
                    )

            }
        )



    # ---------------------------------
    # ADD recommendations
    # ---------------------------------

    stocks = (
        stock_results
        if isinstance(
            stock_results,
            pd.DataFrame
        )
        else pd.DataFrame(
            stock_results
        )
    )


    if stocks.empty:

        return pd.DataFrame(
            recommendations
        )



    # Support alternate ticker naming

    if "Ticker" not in stocks.columns:

        if "Symbol" in stocks.columns:

            stocks["Ticker"] = stocks["Symbol"]

        elif "ticker" in stocks.columns:

            stocks["Ticker"] = stocks["ticker"]

        else:

            return pd.DataFrame(
                recommendations
            )



    # Find underweight sector candidates

    candidates = stocks[
        stocks["Sector"].isin(
            sectors_to_add
        )
    ]



    candidates = candidates[
        candidates["Signal"].isin(
            [
                "BUY",
                "STRONG BUY"
            ]
        )
    ]



    candidates = candidates[
        candidates["Investment Score"] >= 75
    ]



    candidates = candidates.sort_values(
        by="Investment Score",
        ascending=False
    )



    # ---------------------------------
    # Select best stock per sector
    # ---------------------------------

    for sector in sectors_to_add:


        sector_candidates = candidates[
            candidates["Sector"] == sector
        ]



        if sector_candidates.empty:

            continue



        best = sector_candidates.iloc[0]



        ticker = str(
            best.get(
                "Ticker",
                ""
            )
        ).strip()



        # Prevent blank ADD rows

        if ticker == "":

            print(
                "Skipping ADD recommendation - missing ticker"
            )

            print(
                best
            )

            continue



        recommendations.append(
            {

                "Action":
                    "ADD",

                "Ticker":
                    ticker,

                "Sector":
                    sector,

                "Investment Score":
                    best.get(
                        "Investment Score",
                        None
                    ),

                "Allocation %":
                    None,

                "Reason":
                    (
                        "Highest-rated stock "
                        "in underweight sector"
                    )

            }
        )



    return pd.DataFrame(
        recommendations
    )