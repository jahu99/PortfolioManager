import pandas as pd


def generate_final_portfolio_decisions(
    portfolio_summary,
    decisions,
    portfolio_ai_review,
    portfolio_manager_review,
    portfolio_health
):
    """
    Consolidates all portfolio intelligence layers into a final
    portfolio manager recommendation.

    Inputs:
        portfolio_summary      - current holdings and allocations
        decisions              - decision engine output
        portfolio_ai_review    - AI holding analysis
        portfolio_manager_review - portfolio level assessment
        portfolio_health       - portfolio risk assessment

    Returns:
        DataFrame containing final portfolio actions
    """

    print("FINAL PORTFOLIO DECISION ENGINE START")


    if portfolio_summary is None:
        portfolio_summary = pd.DataFrame()

    if decisions is None:
        decisions = pd.DataFrame()

    if portfolio_ai_review is None:
        portfolio_ai_review = []



    final_decisions = []


    # Convert AI review into lookup

    ai_lookup = {}

    for review in portfolio_ai_review:

        if isinstance(review, dict):

            ticker = review.get(
                "Ticker"
            )

            if ticker:
                ai_lookup[ticker] = review



    # Portfolio health context

    health_score = None
    health_rating = None
    health_risks = []


    if isinstance(
        portfolio_health,
        dict
    ):

        health_score = portfolio_health.get(
            "Health Score"
        )

        health_rating = portfolio_health.get(
            "Rating"
        )

        health_risks = portfolio_health.get(
            "Risks",
            []
        )



    # Manager context

    manager_summary = ""

    if isinstance(
        portfolio_manager_review,
        dict
    ):

        manager_summary = portfolio_manager_review.get(
            "AI Summary",
            ""
        )



    # Process decisions

    for _, decision in decisions.iterrows():


        ticker = decision.get(
            "Ticker",
            ""
        )


        if not ticker:
            continue



        ai_review = ai_lookup.get(
            ticker,
            {}
        )


        action = decision.get(
            "Action",
            "REVIEW"
        )


        conviction = (
            ai_review.get(
                "AI Holding Conviction",
                "Medium"
            )
        )


        risks = ai_review.get(
            "AI Holding Risks",
            []
        )


        reasons = ai_review.get(
            "AI Holding Reasons",
            []
        )


        ai_action = ai_review.get(
            "AI Holding Actions",
            []
        )



        # ---------------------------------
        # Capital decision logic
        # ---------------------------------

        if action in [
            "REDUCE",
            "SELL"
        ]:

            capital_action = (
                "Free capital for stronger opportunities"
            )


        elif action in [
            "ADD",
            "BUY"
        ]:

            capital_action = (
                "Consider increasing allocation"
            )


        elif action in [
            "HOLD / ADD",
            "HOLD"
        ]:

            capital_action = (
                "Maintain position size"
            )


        else:

            capital_action = (
                "Review allocation"
            )



        # ---------------------------------
        # Final recommendation text
        # ---------------------------------

        final_reason = []


        if reasons:

            final_reason.extend(
                reasons
            )


        if risks:

            final_reason.extend(
                risks
            )


        if health_risks:

            final_reason.append(
                "Portfolio health requires monitoring"
            )



        final_decisions.append(

            {
                "Ticker": ticker,

                "Position Type":
                    "CURRENT HOLDING"
                    if (
                        not portfolio_summary.empty
                        and "Ticker" in portfolio_summary.columns
                        and ticker in portfolio_summary["Ticker"].values
                    )
                    else "REBALANCE CANDIDATE",
                "Final Action": action,

                "Conviction": conviction,

                "Capital Decision": capital_action,

                "Investment Score":
                    decision.get(
                        "Investment Score",
                        None
                    ),

                "Reason":
                    "; ".join(
                        final_reason
                    ),

                "AI Actions":
                    "; ".join(
                        ai_action
                    ),

                "Portfolio Health Score":
                    health_score,

                "Portfolio Health Rating":
                    health_rating,

                "Manager Summary":
                    manager_summary

            }

        )



    result = pd.DataFrame(final_decisions)

    result["Sort Order"] = (
        result["Position Type"]
        .map(
            {
                "CURRENT HOLDING": 1,
                "REBALANCE CANDIDATE": 2
            }
        )
    )

    result = (
        result
        .sort_values(
            [
                "Sort Order",
                "Final Action"
            ]
        )
        .drop(
            columns=["Sort Order"]
        )
        .reset_index(drop=True)
    )


    print(
        "FINAL PORTFOLIO DECISION SIZE:",
        result.shape
    )


    return result