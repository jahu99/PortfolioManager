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

    Portfolio health is the source of truth.
    This layer explains the result.
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
    # Use portfolio health as authority
    # ---------------------------------

    if portfolio_health:

        score = portfolio_health.get(
            "Health Score",
            50
        )

        review["Portfolio Rating"] = score


        review["Key Strengths"] = (
            portfolio_health.get(
                "Strengths",
                []
            )
        )


        review["Key Risks"] = (
            portfolio_health.get(
                "Risks",
                []
            )
        )


    else:

        score = 50
    
    # ---------------------------------
    # Holding strengths
    # ---------------------------------

    if not portfolio_summary.empty:

        strong_holdings = portfolio_summary[
            portfolio_summary["Investment Score"] >= 80
        ]


        for _, row in strong_holdings.iterrows():

            review["Key Strengths"].append(
                f"{row['Ticker']} is a high conviction holding"
            )

    # ---------------------------------
    # Portfolio investment quality analysis
    # ---------------------------------

    if not portfolio_summary.empty:

        avg_score = (
            portfolio_summary[
                "Investment Score"
            ]
            .mean()
        )


        if avg_score >= 75:

            review["Key Strengths"].append(
                "Portfolio has strong average investment scores"
            )


        elif avg_score < 60:

            review["Key Risks"].append(
                "Portfolio has weak average investment scores"
            )


        strongest = portfolio_summary.loc[
            portfolio_summary[
                "Investment Score"
            ].idxmax()
        ]


        weakest = portfolio_summary.loc[
            portfolio_summary[
                "Investment Score"
            ].idxmin()
        ]


        review["Key Strengths"].append(
            f"{strongest['Ticker']} is the strongest holding by investment score"
        )


        review["Key Risks"].append(
            f"{weakest['Ticker']} is the weakest holding by investment score"
        )


    # ---------------------------------
    # Holding concentration analysis
    # ---------------------------------

    if not portfolio_summary.empty:

        for _, row in portfolio_summary.iterrows():

            ticker = row.get(
                "Ticker",
                "Unknown"
            )

            allocation = row.get(
                "Allocation %",
                0
            )


            if allocation >= 40:

                review["Key Risks"].append(
                    f"{ticker} represents excessive portfolio concentration"
                )

                review["Priority Actions"].append(
                    f"Consider reducing {ticker} position size"
                )


            elif allocation >= 25:

                review["Key Risks"].append(
                    f"{ticker} has high portfolio weighting"
                )

    # ---------------------------------
    # Sector concentration analysis
    # ---------------------------------

    if not sector_summary.empty:

        for _, row in sector_summary.iterrows():

            sector = row.get(
                "Sector",
                "Unknown"
            )

            allocation = row.get(
                "Allocation %",
                0
            )


            if allocation >= 40:

                review["Key Risks"].append(
                    f"{sector} sector concentration risk"
                )

                review["Priority Actions"].append(
                    "Increase diversification outside concentrated sectors"
                )

    # ---------------------------------
    # Health-based portfolio actions
    # ---------------------------------

    if portfolio_health:

        health_score = portfolio_health.get(
            "Health Score",
            50
        )


        if health_score < 70:

            review["Priority Actions"].append(
                "Review portfolio concentration and rebalance toward target allocation"
            )


        if health_score < 50:

            review["Priority Actions"].append(
                "Consider structural portfolio changes"
            )

    # ---------------------------------
    # Add decision intelligence
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


        if reduce_count > 0:

            review["Priority Actions"].append(
                f"{reduce_count} holdings require review or reduction"
            )


        if add_count > 0:

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



    # Remove duplicates

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
    # AI Summary
    # ---------------------------------

    review["AI Summary"] = (

        f"Portfolio rating is {score}/100. "

        f"Overall market view is "
        f"{review['Market View']}. "

        f"{review['Portfolio Status']} "

        f"The portfolio contains "
        f"{len(review['Key Risks'])} identified risks "
        f"and "
        f"{len(review['Priority Actions'])} priority actions."

    )


    return review