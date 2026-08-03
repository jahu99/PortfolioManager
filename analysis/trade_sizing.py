import math
import pandas as pd


STARTER_POSITION_VALUE = 500
MAX_NEW_POSITIONS = 5


# -------------------------------------------------------
# Confidence scoring
# -------------------------------------------------------

def calculate_confidence(
    investment_score,
    quality_score,
    signal
):

    score = 0

    if investment_score >= 80:
        score += 40
    elif investment_score >= 70:
        score += 25

    if quality_score >= 70:
        score += 30
    elif quality_score >= 50:
        score += 15

    if signal == "STRONG BUY":
        score += 30
    elif signal == "BUY":
        score += 20


    if score >= 80:
        return "High"

    elif score >= 50:
        return "Medium"

    return "Low"



# -------------------------------------------------------
# Extract sector targets
# -------------------------------------------------------

def build_sector_targets(
    portfolio_optimisation
):

    targets = {}


    if (
        portfolio_optimisation is None
        or not isinstance(
            portfolio_optimisation,
            pd.DataFrame
        )
        or portfolio_optimisation.empty
    ):
        return targets


    for _, row in portfolio_optimisation.iterrows():

        sector = row.get(
            "Sector"
        )

        if not sector:
            continue


        current = row.get(
            "Current %",
            row.get(
                "Current Allocation %",
                0
            )
        )


        target = row.get(
            "Target %",
            row.get(
                "Target Allocation %",
                0
            )
        )


        action = row.get(
            "Action",
            ""
        )


        targets[sector] = {

            "Current": current,
            "Target": target,
            "Action": action

        }


    return targets



# -------------------------------------------------------
# Generate trade plan
# -------------------------------------------------------

def generate_trade_plan(
    portfolio_summary,
    portfolio_optimisation,
    stock_results
):

    trades = []


    if (
        portfolio_summary is None
        or portfolio_summary.empty
    ):
        return pd.DataFrame()



    total_value = portfolio_summary[
        "Current Value"
    ].sum()


    if total_value <= 0:
        return pd.DataFrame()



    sector_targets = build_sector_targets(
        portfolio_optimisation
    )


    sold_tickers = set()



    # ---------------------------------------------------
    # SELL overweight positions
    # ---------------------------------------------------

    for _, holding in portfolio_summary.iterrows():


        ticker = holding.get(
            "Ticker",
            ""
        )


        sector = holding.get(
            "Sector",
            "Unknown"
        )


        current_value = holding.get(
            "Current Value",
            0
        )


        allocation = (
            current_value /
            total_value
        ) * 100



        target = sector_targets.get(
            sector,
            {}
        ).get(
            "Target",
            allocation
        )



        if allocation > target + 5:


            sell_value = (
                allocation -
                target
            ) / 100 * total_value



            price = holding.get(
                "Current Price",
                holding.get(
                    "Price",
                    0
                )
            )


            if price <= 0:
                continue



            shares = math.floor(
                sell_value /
                price
            )


            if shares <= 0:
                continue



            trades.append(
                {

                    "Priority": 1,
                    "Action": "SELL",
                    "Ticker": ticker,
                    "Sector": sector,
                    "Trade Value": round(
                        -sell_value,
                        2
                    ),
                    "Shares": -shares,
                    "Current Allocation %": round(
                        allocation,
                        2
                    ),
                    "Target Allocation %": round(
                        target,
                        2
                    ),
                    "Investment Score":
                        holding.get(
                            "Investment Score",
                            0
                        ),
                    "Quality Score":
                        holding.get(
                            "Quality Score",
                            0
                        ),
                    "Signal":
                        holding.get(
                            "Signal",
                            ""
                        ),
                    "Confidence":
                        "High",
                    "Reason":
                        f"{sector} above target allocation"

                }
            )


            sold_tickers.add(
                ticker
            )



    # ---------------------------------------------------
    # Normalise stock results
    # ---------------------------------------------------

    if isinstance(
        stock_results,
        list
    ):

        stocks = pd.DataFrame(
            stock_results
        )

    else:

        stocks = stock_results.copy()



    if stocks is None or stocks.empty:
        return pd.DataFrame(trades)



    if "Ticker" not in stocks.columns:

        if "Symbol" in stocks.columns:
            stocks["Ticker"] = stocks["Symbol"]

        elif "ticker" in stocks.columns:
            stocks["Ticker"] = stocks["ticker"]

        else:
            return pd.DataFrame(trades)



    # ---------------------------------------------------
    # BUY candidates
    # ---------------------------------------------------

    candidates = stocks.copy()


    candidates = candidates[
        candidates["Signal"].isin(
            [
                "BUY",
                "STRONG BUY"
            ]
        )
    ]



    if "Investment Score" in candidates.columns:

        candidates = candidates[
            candidates["Investment Score"] >= 75
        ]



    candidates = candidates.sort_values(
        by="Investment Score",
        ascending=False
    )



    # ---------------------------------------------------
    # Rebalance BUYs first
    # ---------------------------------------------------

    priority = 2


    for sector, details in sector_targets.items():


        if details["Action"] not in [
            "ADD",
            "BUY"
        ]:
            continue



        sector_candidates = candidates[
            candidates["Sector"] == sector
        ]



        if sector_candidates.empty:
            continue



        stock = sector_candidates.iloc[0]


        ticker = stock["Ticker"]


        if ticker in sold_tickers:
            continue



        trades.append(
            {

                "Priority": priority,
                "Action": "BUY",
                "Ticker": ticker,
                "Sector": sector,
                "Trade Value": STARTER_POSITION_VALUE,
                "Shares": math.floor(
                    STARTER_POSITION_VALUE /
                    stock.get(
                        "Price",
                        1
                    )
                ),
                "Current Allocation %": 0,
                "Target Allocation %": 5,
                "Investment Score":
                    stock.get(
                        "Investment Score",
                        0
                    ),
                "Quality Score":
                    stock.get(
                        "Quality Score",
                        0
                    ),
                "Signal":
                    stock.get(
                        "Signal",
                        ""
                    ),
                "Confidence":
                    calculate_confidence(
                        stock.get(
                            "Investment Score",
                            0
                        ),
                        stock.get(
                            "Quality Score",
                            0
                        ),
                        stock.get(
                            "Signal",
                            ""
                        )
                    ),
                "Reason":
                    "Portfolio rebalance recommendation"

            }
        )


        priority += 1



    # ---------------------------------------------------
    # High conviction additions
    # ---------------------------------------------------

    existing = {
        x["Ticker"]
        for x in trades
    }



    for _, stock in candidates.iterrows():


        if len(
            trades
        ) >= MAX_NEW_POSITIONS + 2:
            break



        ticker = stock["Ticker"]


        if ticker in existing:
            continue



        trades.append(
            {

                "Priority": priority,
                "Action": "BUY",
                "Ticker": ticker,
                "Sector":
                    stock.get(
                        "Sector",
                        ""
                    ),
                "Trade Value": STARTER_POSITION_VALUE,
                "Shares": math.floor(
                    STARTER_POSITION_VALUE /
                    stock.get(
                        "Price",
                        1
                    )
                ),
                "Current Allocation %": 0,
                "Target Allocation %": 5,
                "Investment Score":
                    stock.get(
                        "Investment Score",
                        0
                    ),
                "Quality Score":
                    stock.get(
                        "Quality Score",
                        0
                    ),
                "Signal":
                    stock.get(
                        "Signal",
                        ""
                    ),
                "Confidence":
                    calculate_confidence(
                        stock.get(
                            "Investment Score",
                            0
                        ),
                        stock.get(
                            "Quality Score",
                            0
                        ),
                        stock.get(
                            "Signal",
                            ""
                        )
                    ),
                "Reason":
                    "High conviction opportunity"

            }
        )


        priority += 1



    return pd.DataFrame(
        trades
    )