import pandas as pd


def generate_final_portfolio_decision(
    ticker,
    investment_decision,
    ai_review,
    portfolio_manager_review,
    portfolio_health=None
):
    """
    Portfolio Decision Consolidator

    Purpose:
    Combines:
    - Investment decision engine
    - AI portfolio review
    - Portfolio manager review
    - Portfolio health

    Produces one final portfolio action.
    """

    final_action = "HOLD"
    confidence = "Medium"

    reasons = []
    risks = []
    actions = []

    capital_action = (
        "Maintain existing allocation"
    )

    review_trigger = [
        "Investment score falls below 60",
        "Trend breaks below 200 DMA"
    ]


    # -------------------------------------------------
    # Extract investment decision
    # -------------------------------------------------

    investment_action = None

    if isinstance(
        investment_decision,
        dict
    ):

        investment_action = (
            investment_decision.get(
                "Action"
            )
        )

        reason = investment_decision.get(
            "Reason"
        )

        if reason:
            reasons.append(
                reason
            )


    elif isinstance(
        investment_decision,
        pd.Series
    ):

        investment_action = (
            investment_decision.get(
                "Action"
            )
        )

        reason = investment_decision.get(
            "Reason"
        )

        if reason:
            reasons.append(
                reason
            )



    # -------------------------------------------------
    # Extract AI recommendation
    # -------------------------------------------------

    ai_action = None


    if isinstance(
        ai_review,
        dict
    ):

        ai_action = (
            ai_review.get(
                "AI Holding Decision"
            )
        )

        ai_risks = ai_review.get(
            "AI Holding Risks",
            []
        )

        risks.extend(
            ai_risks
        )


        ai_actions = ai_review.get(
            "AI Holding Actions",
            []
        )

        actions.extend(
            ai_actions
        )


        ai_reasons = ai_review.get(
            "AI Holding Reasons",
            []
        )

        reasons.extend(
            ai_reasons
        )



    # -------------------------------------------------
    # Extract portfolio manager view
    # -------------------------------------------------

    manager_risks = []

    if isinstance(
        portfolio_manager_review,
        dict
    ):

        manager_risks = (
            portfolio_manager_review.get(
                "Key Risks",
                []
            )
        )


        risks.extend(
            manager_risks
        )



    # -------------------------------------------------
    # Portfolio health overlay
    # -------------------------------------------------

    health_score = 100


    if isinstance(
        portfolio_health,
        dict
    ):

        health_score = (
            portfolio_health.get(
                "Health Score",
                100
            )
        )


    # -------------------------------------------------
    # Decision hierarchy
    # -------------------------------------------------

    #
    # Reduce / Exit always wins
    #

    if (
        investment_action in [
            "REDUCE",
            "SELL",
            "EXIT"
        ]
        or ai_action in [
            "REDUCE",
            "SELL"
        ]
    ):

        final_action = "REDUCE"

        confidence = "High"

        capital_action = (
            "Reallocate capital to stronger opportunities"
        )



    #
    # Portfolio risk can prevent additions
    #

    elif (
        ai_action == "HOLD"
        and len(manager_risks) > 0
    ):

        final_action = "HOLD"

        confidence = "High"

        capital_action = (
            "Do not increase until portfolio risks improve"
        )



    #
    # Strong opportunity
    #

    elif (
        investment_action == "ADD"
        and health_score >= 70
    ):

        final_action = "ADD"

        confidence = "High"

        capital_action = (
            "Increase allocation gradually"
        )



    #
    # Default
    #

    else:

        final_action = "HOLD"

        confidence = "Medium"



    # -------------------------------------------------
    # Remove duplicates
    # -------------------------------------------------

    reasons = list(
        dict.fromkeys(
            reasons
        )
    )

    risks = list(
        dict.fromkeys(
            risks
        )
    )

    actions = list(
        dict.fromkeys(
            actions
        )
    )



    return {

        "Ticker": ticker,

        "Final Action": final_action,

        "Confidence": confidence,

        "Reasons": reasons,

        "Risks": risks,

        "Actions": actions,

        "Capital Allocation Action":
            capital_action,

        "Review Triggers":
            review_trigger

    }