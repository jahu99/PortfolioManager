import math
import pandas as pd

STARTER_POSITION_VALUE = 500
MAX_NEW_POSITIONS = 5

# New money available to invest each run
# Set to 0 if you only want to rebalance.
NEW_CASH_AVAILABLE = 2500


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
    else:
        return "Low"


def generate_trade_plan(
    portfolio_summary,
    sector_optimisation,
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

    # ---------------------------------
    # Sector targets
    # ---------------------------------

    sector_targets = {}

    if (
        sector_optimisation is not None
        and not sector_optimisation.empty
    ):

        for _, row in sector_optimisation.iterrows():

            sector_targets[row["Sector"]] = {

                "Current":
                    row.get(
                        "Current %",
                        0
                    ),

                "Target":
                    row.get(
                        "Target %",
                        0
                    )

            }

    # ---------------------------------
    # SELL analysis
    # ---------------------------------

    sold_tickers = set()

    for _, holding in portfolio_summary.iterrows():

        ticker = holding["Ticker"]

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

        target_allocation = sector_targets.get(
            sector,
            {}
        ).get(
            "Target",
            allocation
        )

        if allocation > target_allocation + 5:

            excess = (
                allocation -
                target_allocation
            )

            sell_value = (
                excess /
                100
            ) * total_value

            price = holding.get(
                "Current Price",
                0
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

                    "Trade Value":
                        round(
                            -sell_value,
                            2
                        ),

                    "Shares": -shares,

                    "Current Allocation %":
                        round(
                            allocation,
                            2
                        ),

                    "Target Allocation %":
                        round(
                            target_allocation,
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

                    "Confidence": "High",

                    "Reason":
                        f"{sector} above target allocation"

                }
            )

            sold_tickers.add(
                ticker
            )

    # ---------------------------------
    # BUY candidate selection
    # ---------------------------------

    candidates = []

    for stock in stock_results:

        ticker = stock.get(
            "Ticker"
        )

        if ticker in sold_tickers:
            continue

        signal = stock.get(
            "Signal",
            ""
        )

        investment_score = stock.get(
            "Investment Score",
            0
        )

        quality_score = stock.get(
            "Quality Score",
            0
        )

        if signal not in [
            "BUY",
            "STRONG BUY"
        ]:
            continue

        if investment_score < 80:
            continue

        candidates.append(
            stock
        )

    candidates = sorted(
        candidates,
        key=lambda x:
            x.get(
                "Investment Score",
                0
            ),
        reverse=True
    )

    # ---------------------------------
    # Available capital
    # ---------------------------------

    sell_capital = sum(
        -x["Trade Value"]
        for x in trades
        if x["Action"] == "SELL"
    )

    available_capital = (
        sell_capital +
        NEW_CASH_AVAILABLE
    )

    if available_capital <= 0:

        print(
            "No capital available for buys."
        )

        return pd.DataFrame(
            trades
        )

    if len(candidates) == 0:

        print(
            "No qualifying BUY candidates."
        )

        return pd.DataFrame(
            trades
        )

    # ---------------------------------
    # Starter allocations
    # ---------------------------------

    selected_candidates = candidates[
        :MAX_NEW_POSITIONS
    ]

    buy_budget = min(
        available_capital,
        STARTER_POSITION_VALUE *
        len(selected_candidates)
    )

    allocation_per_stock = (
        buy_budget /
        len(selected_candidates)
    )

    priority = 2

    for stock in selected_candidates:

        ticker = stock["Ticker"]

        price = stock.get(
            "Price",
            0
        )

        if price <= 0:
            continue

        shares = math.floor(
            allocation_per_stock /
            price
        )

        if shares <= 0:
            continue

        investment_score = stock.get(
            "Investment Score",
            0
        )

        quality_score = stock.get(
            "Quality Score",
            0
        )

        signal = stock.get(
            "Signal",
            ""
        )

        confidence = calculate_confidence(
            investment_score,
            quality_score,
            signal
        )

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

                "Trade Value":
                    round(
                        allocation_per_stock,
                        2
                    ),

                "Shares": shares,

                "Current Allocation %": 0,

                "Target Allocation %": 5,

                "Investment Score":
                    investment_score,

                "Quality Score":
                    quality_score,

                "Signal": signal,

                "Confidence":
                    confidence,

                "Reason":
                    "Starter position using available capital"

            }
        )

        priority += 1

    print(
        f"Trade plan generated: {len(trades)} trades"
    )

    return pd.DataFrame(
        trades
    )