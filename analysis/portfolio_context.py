import pandas as pd


def evaluate_portfolio_context(
    stock,
    portfolio_summary,
    sector_summary,
    portfolio_health
):
    """
    Portfolio Context Engine

    Purpose:
    - Provides a single portfolio decision layer
    - Considers stock quality + portfolio risk
    - Used by Growth Plan, AI Review and Portfolio Manager

    Returns:
    Standardised portfolio decision object
    """

    # -----------------------------
    # Extract stock information
    # -----------------------------

    ticker = stock.get("Ticker", "")

    investment_score = stock.get(
        "Investment Score",
        0
    )

    quality_score = stock.get(
        "Quality Score",
        0
    )

    technical_score = stock.get(
        "Technical Score",
        0
    )

    signal = stock.get(
        "Signal",
        "HOLD"
    )

    sector = stock.get(
        "Sector",
        "Unknown"
    )


    reasons = []
    risks = []
    actions = []


    # -----------------------------
    # Portfolio position analysis
    # -----------------------------

    allocation = 0

    if (
        portfolio_summary is not None
        and not portfolio_summary.empty
        and "Ticker" in portfolio_summary.columns
    ):

        holding = portfolio_summary[
            portfolio_summary["Ticker"] == ticker
        ]

        if not holding.empty:

            if "Allocation %" in holding.columns:

                allocation = float(
                    holding.iloc[0]["Allocation %"]
                )


    # -----------------------------
    # Sector exposure analysis
    # -----------------------------

    sector_allocation = 0

    if (
        sector_summary is not None
        and not sector_summary.empty
        and "Sector" in sector_summary.columns
    ):

        sector_row = sector_summary[
            sector_summary["Sector"] == sector
        ]

        if not sector_row.empty:

            if "Allocation %" in sector_row.columns:

                sector_allocation = float(
                    sector_row.iloc[0]["Allocation %"]
                )


    # -----------------------------
    # Default settings
    # -----------------------------

    decision = "HOLD"

    conviction = "Medium"

    priority = 3

    target_allocation = 5

    maximum_allocation = 8



    # -----------------------------
    # Strong investment candidates
    # -----------------------------

    if investment_score >= 80:

        reasons.append(
            "High investment score"
        )

        if quality_score >= 70:

            reasons.append(
                "Strong business quality"
            )


        if technical_score >= 70:

            reasons.append(
                "Positive technical momentum"
            )


        if allocation < maximum_allocation:

            decision = "ADD"

            priority = 1

            conviction = "High"

            actions.append(
                "Consider increasing position"
            )


        else:

            decision = "HOLD"

            conviction = "Medium"

            actions.append(
                "Maintain position size"
            )


    # -----------------------------
    # Medium candidates
    # -----------------------------

    elif investment_score >= 60:

        decision = "HOLD"

        priority = 2

        conviction = "Medium"

        reasons.append(
            "Acceptable investment profile"
        )

        actions.append(
            "Monitor position"
        )


    # -----------------------------
    # Weak candidates
    # -----------------------------

    else:

        risks.append(
            "Weak investment score"
        )


        if quality_score < 50:

            risks.append(
                "Quality below preferred threshold"
            )


        if technical_score < 50:

            risks.append(
                "Weak technical momentum"
            )


        if allocation > 10:

            decision = "REDUCE"

            priority = 1

            conviction = "High"

            actions.append(
                "Reduce oversized position"
            )

        else:

            decision = "AVOID"

            priority = 4

            conviction = "Low"

            actions.append(
                "Do not increase position"
            )


    # -----------------------------
    # Portfolio risk overlay
    # -----------------------------

    if sector_allocation > 40:

        risks.append(
            f"High {sector} sector concentration"
        )


        if decision == "ADD":

            decision = "HOLD"

            actions.append(
                "Avoid adding until diversification improves"
            )


    # -----------------------------
    # Portfolio health overlay
    # -----------------------------

    if isinstance(
        portfolio_health,
        dict
    ):

        health_score = portfolio_health.get(
            "Health Score",
            100
        )

        if health_score < 70:

            risks.append(
                "Portfolio health requires improvement"
            )


    # -----------------------------
    # Review triggers
    # -----------------------------

    review_trigger = [
        "Investment score falls below 60",
        "Trend breaks below 200 DMA"
    ]


    return {

        "Ticker": ticker,

        "Decision": decision,

        "Conviction": conviction,

        "Priority": priority,

        "Investment Score": investment_score,

        "Quality Score": quality_score,

        "Technical Score": technical_score,

        "Sector": sector,

        "Allocation %": round(
            allocation,
            2
        ),

        "Sector Allocation %": round(
            sector_allocation,
            2
        ),

        "Target Allocation %": target_allocation,

        "Maximum Allocation %": maximum_allocation,

        "Reasons": reasons,

        "Risks": risks,

        "Actions": actions,

        "Diversification Impact":
            "Negative"
            if sector_allocation > 40
            else "Positive",

        "Review Triggers": review_trigger

    }