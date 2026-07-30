import pandas as pd


def generate_portfolio_manager_review(
    portfolio_summary,
    sector_summary,
    decisions,
    trade_plan,
    portfolio_health=None
):

    """
    Generates portfolio manager intelligence.

    Portfolio Health is the source of truth.
    This layer explains the implications.
    """

    review = {

        "Portfolio Rating": 0,

        "Market View": "Neutral",

        "Portfolio Status": "",

        "Key Strengths": [],

        "Key Risks": [],

        "Priority Actions": [],

        "AI Summary": ""

    }

    print("DEBUG: PORTFOLIO MANAGER FUNCTION CALLED")


    # ---------------------------------
    # Safety checks
    # ---------------------------------

    if portfolio_summary is None:
        portfolio_summary = pd.DataFrame()


    if sector_summary is None:
        sector_summary = pd.DataFrame()


    if decisions is None:
        decisions = pd.DataFrame()


    if trade_plan is None:
        trade_plan = pd.DataFrame()



    # ---------------------------------
    # Portfolio Health authority
    # ---------------------------------

    score = 50


    if portfolio_health:

        score = portfolio_health.get(
            "Health Score",
            50
        )


        review["Portfolio Rating"] = score


        review["Key Strengths"].extend(
            portfolio_health.get(
                "Strengths",
                []
            )
        )


        review["Key Risks"].extend(
            portfolio_health.get(
                "Risks",
                []
            )
        )



    # ---------------------------------
    # Holding insights
    # ---------------------------------

    if not portfolio_summary.empty:

        for _, row in portfolio_summary.iterrows():

            ticker = row.get(
                "Ticker",
                "Unknown"
            )


            investment_score = row.get(
                "Investment Score",
                0
            )


            allocation = row.get(
                "Allocation %",
                0
            )


            if investment_score >= 80:

                review["Key Strengths"].append(
                    f"{ticker} is a high conviction holding"
                )


            if allocation >= 40:

                review["Key Risks"].append(
                    f"{ticker} has excessive portfolio concentration"
                )

                review["Priority Actions"].append(
                    f"Review {ticker} position sizing"
                )



    # ---------------------------------
    # Decision interpretation
    # ---------------------------------

    if not decisions.empty:

        reduce_count = len(
            decisions[
                decisions["Action"]
                .astype(str)
                .str.contains(
                    "REDUCE"
                )
            ]
        )


        add_count = len(
            decisions[
                decisions["Action"]
                .astype(str)
                .str.contains(
                    "ADD"
                )
            ]
        )


        if reduce_count:

            review["Priority Actions"].append(
                f"{reduce_count} holdings require review or reduction"
            )


        if add_count:

            review["Priority Actions"].append(
                f"{add_count} diversification opportunities identified"
            )



    # ---------------------------------
    # Trade plan interpretation
    # ---------------------------------

    if not trade_plan.empty:

        review["Priority Actions"].append(
            f"{len(trade_plan)} portfolio trades recommended"
        )



    # ---------------------------------
    # Remove duplicates
    # ---------------------------------

    review["Key Strengths"] = list(
        dict.fromkeys(
            review["Key Strengths"]
        )
    )


    review["Key Risks"] = list(
        dict.fromkeys(
            review["Key Risks"]
        )
    )


    review["Priority Actions"] = list(
        dict.fromkeys(
            review["Priority Actions"]
        )
    )



    # ---------------------------------
    # Portfolio classification
    # ---------------------------------

    if score >= 80:

        review["Market View"] = "Positive"

        review["Portfolio Status"] = (
            "Portfolio is healthy with manageable risks"
        )


    elif score >= 60:

        review["Market View"] = "Neutral"

        review["Portfolio Status"] = (
            "Portfolio is acceptable but requires attention"
        )


    else:

        review["Market View"] = "Cautious"

        review["Portfolio Status"] = (
            "Portfolio requires restructuring"
        )



    # ---------------------------------
    # AI summary
    # ---------------------------------

    review["AI Summary"] = (

        f"Portfolio rating is {score}/100. "

        f"Overall market view is "
        f"{review['Market View']}. "

        f"{review['Portfolio Status']}. "

        f"The portfolio has "
        f"{len(review['Key Risks'])} identified risks "
        f"and "
        f"{len(review['Priority Actions'])} priority actions."

    )


    return review