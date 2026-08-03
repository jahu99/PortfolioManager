import pandas as pd

from config.investment_config import (
    AVAILABLE_CASH,
    CASH_RESERVE_PERCENT,
    MIN_TRADE_VALUE,
    MAX_TRADE_VALUE,
    MIN_BUY_SCORE,
    MIN_QUALITY_SCORE,
    TARGET_SECTOR_ALLOCATIONS,

    INVESTMENT_SCORE_WEIGHT,
    QUALITY_SCORE_WEIGHT,
    SECTOR_NEED_WEIGHT,
    CONFIDENCE_WEIGHT
)


# ==================================================
# Confidence scoring
# ==================================================

def confidence_score(value):

    return {
        "High": 100,
        "Medium": 70,
        "Low": 40
    }.get(str(value), 50)



# ==================================================
# Opportunity scoring
# ==================================================

def allocation_score(stock, sector_summary):

    investment = float(
        stock.get(
            "Investment Score",
            0
        )
    )

    quality = float(
        stock.get(
            "Quality Score",
            0
        )
    )

    confidence = confidence_score(
        stock.get(
            "Confidence",
            "Medium"
        )
    )

    sector = stock.get(
        "Sector",
        ""
    )


    sector_need = 50


    if (
        sector_summary is not None
        and not sector_summary.empty
        and "Sector" in sector_summary.columns
    ):

        match = sector_summary[
            sector_summary["Sector"] == sector
        ]


        if not match.empty:

            if match.iloc[0].get("Action") == "ADD":
                sector_need = 100


    return round(

        investment * INVESTMENT_SCORE_WEIGHT
        +
        quality * QUALITY_SCORE_WEIGHT
        +
        sector_need * SECTOR_NEED_WEIGHT
        +
        confidence * CONFIDENCE_WEIGHT,

        2
    )



# ==================================================
# Sector exposure
# ==================================================

def sector_exposure(portfolio):

    if portfolio is None or portfolio.empty:
        return pd.DataFrame()


    if (
        "Sector" not in portfolio.columns
        or "Current Value" not in portfolio.columns
    ):
        return pd.DataFrame()


    total = portfolio["Current Value"].sum()


    if total == 0:
        return pd.DataFrame()


    result = (
        portfolio
        .groupby("Sector")["Current Value"]
        .sum()
        .reset_index()
    )


    result["Allocation %"] = (
        result["Current Value"]
        /
        total
        *
        100
    )


    return result



# ==================================================
# Core holding protection
# ==================================================

def is_core_holding(holding):

    #
    # Prefer scanner scores if available
    # Otherwise keep existing portfolio scores
    #

    score = float(
        holding.get(
            "Investment Score_Scanner",
            holding.get(
                "Investment Score",
                0
            )
        )
        or 0
    )


    quality = float(
        holding.get(
            "Quality Score_Scanner",
            holding.get(
                "Quality Score",
                0
            )
        )
        or 0
    )


    signal = str(
        holding.get(
            "Signal",
            ""
        )
    )


    return (

        score >= 85
        and
        quality >= 55

    ) or signal in [

        "BUY",
        "STRONG BUY"

    ]



# ==================================================
# Reduction recommendations
# ==================================================

def generate_reductions(portfolio):

    reductions = []


    exposure = sector_exposure(
        portfolio
    )


    if exposure.empty:
        return reductions


    total_value = portfolio[
        "Current Value"
    ].sum()



    for _, row in exposure.iterrows():

        sector = row["Sector"]

        current = float(
            row["Allocation %"]
        )


        target = TARGET_SECTOR_ALLOCATIONS.get(
            sector,
            10
        )


        if current <= target:
            continue



        required = round(

            total_value
            *
            (
                current - target
            )
            /
            100,

            2
        )


        holdings = portfolio[
            portfolio["Sector"] == sector
        ].copy()



        # weakest first
        if "Investment Score_Scanner" in holdings.columns:

            holdings["Sort Score"] = (
                holdings[
                    "Investment Score_Scanner"
                ]
                .fillna(0)
            )

        elif "Investment Score" in holdings.columns:

            holdings["Sort Score"] = (
                holdings[
                    "Investment Score"
                ]
                .fillna(0)
            )

        else:

            holdings["Sort Score"] = 0



        holdings = holdings.sort_values(
            "Sort Score"
        )


        sells = []

        protected = []

        remaining = required



        for _, holding in holdings.iterrows():

            ticker = holding["Ticker"]


            if is_core_holding(
                holding
            ):

                protected.append(
                    {
                        "Ticker": ticker,
                        "Reason":
                            "Protected core holding"
                    }
                )

                continue



            if remaining <= 0:
                break



            value = float(
                holding[
                    "Current Value"
                ]
            )


            sell_amount = min(
                value,
                remaining
            )


            sells.append(
                {
                    "Ticker": ticker,
                    "Sell Amount": round(
                        sell_amount,
                        2
                    ),
                    "Reason":
                        "Reduce overweight sector exposure"
                }
            )


            remaining -= sell_amount



        reductions.append(
            {
                "Sector": sector,

                "Current Allocation %":
                    round(current,2),

                "Target Allocation %":
                    target,

                "Reduction Required":
                    required,

                "Reduction Achieved":
                    round(
                        required - remaining,
                        2
                    ),

                "Reduction Remaining":
                    round(
                        remaining,
                        2
                    ),

                "Rebalance Status":
                    "COMPLETE"
                    if remaining <= 0
                    else "PARTIAL",

                "Sell Candidates":
                    sells,

                "Protected Holdings":
                    protected
            }
        )


    return reductions



# ==================================================
# Main capital allocator
# ==================================================

def generate_capital_allocation(
    portfolio_summary,
    opportunities,
    sector_summary,
    alerts=None
):


    result = {

        "Available Cash":
            AVAILABLE_CASH,

        "Cash Remaining":
            AVAILABLE_CASH,

        "BUY": [],

        "REDUCE": [],

        "AVOID": [],

        "RISKS": []

    }



    result["REDUCE"] = generate_reductions(
        portfolio_summary
    )



    for item in result["REDUCE"]:

        result["AVOID"].append(
            {
                "Sector":
                    item["Sector"],

                "Action":
                    "Avoid new purchases",

                "Reason":
                    "Sector allocation above target"
            }
        )



    if alerts:

        result["RISKS"] = alerts



    if (
        opportunities is None
        or opportunities.empty
    ):

        return result



    candidates = opportunities.copy()



    candidates["Allocation Score"] = candidates.apply(

        lambda x:
            allocation_score(
                x,
                sector_summary
            ),

        axis=1

    )



    candidates = candidates[

        (candidates["Investment Score"]
         >=
         MIN_BUY_SCORE)

        &
        (candidates["Quality Score"]
         >=
         MIN_QUALITY_SCORE)

        &
        (
            candidates["Signal"]
            .isin(
                [
                    "BUY",
                    "STRONG BUY"
                ]
            )
        )

    ].sort_values(

        "Allocation Score",
        ascending=False

    )



    reserve = (
        AVAILABLE_CASH
        *
        CASH_RESERVE_PERCENT
        /
        100
    )


    cash = AVAILABLE_CASH - reserve



    for _, stock in candidates.iterrows():

        if cash < MIN_TRADE_VALUE:
            break


        amount = min(
            MAX_TRADE_VALUE,
            cash
        )


        result["BUY"].append(

            {
                "Ticker":
                    stock["Ticker"],

                "Sector":
                    stock.get(
                        "Sector"
                    ),

                "Amount":
                    round(
                        amount,
                        2
                    ),

                "Investment Score":
                    stock["Investment Score"],

                "Quality Score":
                    stock["Quality Score"],

                "Confidence":
                    stock.get(
                        "Confidence"
                    ),

                "Reason":
                    "High conviction opportunity"

            }

        )


        cash -= amount



    result["Cash Remaining"] = round(
        cash + reserve,
        2
    )


    return result