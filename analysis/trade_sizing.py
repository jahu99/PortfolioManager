import math
import pandas as pd


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

                "Current": row.get("Current %", 0),
                "Target": row.get("Target %", 0)

            }


    # ---------------------------------
    # SELL recommendations
    # ---------------------------------

    sold_tickers = set()

    for _, holding in portfolio_summary.iterrows():

        ticker = holding["Ticker"]

        sector = holding.get(
            "Sector",
            "Unknown"
        )

        current_value = holding[
            "Current Value"
        ]

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

            excess = allocation - target

            sell_value = (
                excess / 100
            ) * total_value

            price = holding.get(
                "Current Price",
                0
            )

            if price <= 0:
                continue

            shares = math.floor(
                sell_value / price
            )

            if shares <= 0:
                continue

            trades.append(
                {

                    "Action": "SELL",

                    "Ticker": ticker,

                    "Sector": sector,

                    "Trade Value": round(
                        -sell_value,
                        2
                    ),

                    "Shares": -shares,

                    "Reason":
                        f"{sector} above target allocation"

                }
            )

            sold_tickers.add(
                ticker
            )


    # ---------------------------------
    # BUY candidates
    # ---------------------------------

    candidates = []

    for stock in stock_results:

        # Never buy something
        # we are already selling

        if stock["Ticker"] in sold_tickers:
            continue

        if stock.get(
            "Signal"
        ) not in [
            "BUY",
            "STRONG BUY"
        ]:
            continue

        if stock.get(
            "Investment Score",
            0
        ) < 80:
            continue

        candidates.append(
            stock
        )


    candidates = sorted(
        candidates,
        key=lambda x:
            x["Investment Score"],
        reverse=True
    )


    cash_available = sum(
        -x["Trade Value"]
        for x in trades
    )


    if (
        cash_available <= 0
        or len(candidates) == 0
    ):

        return pd.DataFrame(
            trades
        )


    allocation = (
        cash_available /
        min(
            len(candidates),
            5
        )
    )


    bought = set()

    for stock in candidates[:5]:

        ticker = stock["Ticker"]

        if ticker in bought:
            continue

        price = stock.get(
            "Price",
            0
        )

        if price <= 0:
            continue

        shares = math.floor(
            allocation /
            price
        )

        if shares <= 0:
            continue

        trades.append(
            {

                "Action": "BUY",

                "Ticker": ticker,

                "Sector": stock.get(
                    "Sector",
                    ""
                ),

                "Trade Value": round(
                    allocation,
                    2
                ),

                "Shares": shares,

                "Reason":
                    "High investment score and portfolio diversification"

            }
        )

        bought.add(
            ticker
        )


    return pd.DataFrame(
        trades
    )