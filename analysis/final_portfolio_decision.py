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

    Returns:
        DataFrame containing final portfolio actions
    """

    print("FINAL PORTFOLIO DECISION ENGINE START")


    # ---------------------------------
    # Safety defaults
    # ---------------------------------

    if portfolio_summary is None:
        portfolio_summary = pd.DataFrame()


    if decisions is None:
        decisions = pd.DataFrame()


    if portfolio_ai_review is None:
        portfolio_ai_review = []


    output_columns = [

        "Ticker",
        "Position Type",
        "Final Action",
        "Conviction",
        "Capital Decision",
        "Investment Score",
        "Reason",
        "AI Actions",
        "Portfolio Health Score",
        "Portfolio Health Rating",
        "Manager Summary"

    ]


    final_decisions = []


    # ---------------------------------
    # AI review lookup
    # ---------------------------------

    ai_lookup = {}


    for review in portfolio_ai_review:

        if isinstance(review, dict):

            ticker = review.get(
                "Ticker"
            )

            if ticker:

                ai_lookup[ticker] = review



    # ---------------------------------
    # Portfolio health context
    # ---------------------------------

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


    if isinstance(
        health_risks,
        str
    ):

        health_risks = [
            health_risks
        ]



    # ---------------------------------
    # Manager context
    # ---------------------------------

    manager_summary = ""


    if isinstance(
        portfolio_manager_review,
        dict
    ):

        manager_summary = portfolio_manager_review.get(
            "AI Summary",
            ""
        )



    # ---------------------------------
    # Process decisions
    # ---------------------------------

    if not decisions.empty:


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


            conviction = ai_review.get(
                "AI Holding Conviction",
                "Medium"
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



            # Normalise lists

            if isinstance(
                risks,
                str
            ):

                risks = [
                    risks
                ]


            if isinstance(
                reasons,
                str
            ):

                reasons = [
                    reasons
                ]


            if isinstance(
                ai_action,
                str
            ):

                ai_action = [
                    ai_action
                ]



            # ---------------------------------
            # Capital decision
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
            # Reason aggregation
            # ---------------------------------

            final_reason = []


            final_reason.extend(
                reasons
            )


            final_reason.extend(
                risks
            )


            if health_risks:

                final_reason.append(
                    "Portfolio health requires monitoring"
                )



            # ---------------------------------
            # Append decision
            # ---------------------------------

            final_decisions.append(

                {

                    "Ticker":
                        ticker,


                    "Position Type":
                        (
                            "CURRENT HOLDING"
                            if (
                                not portfolio_summary.empty
                                and "Ticker" in portfolio_summary.columns
                                and ticker in portfolio_summary["Ticker"].values
                            )
                            else
                            "REBALANCE CANDIDATE"
                        ),


                    "Final Action":
                        action,


                    "Conviction":
                        conviction,


                    "Capital Decision":
                        capital_action,


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



    # ---------------------------------
    # Create dataframe safely
    # ---------------------------------

    if not final_decisions:


        print(
            "NO FINAL PORTFOLIO DECISIONS GENERATED"
        )


        return pd.DataFrame(
            columns=output_columns
        )



    result = pd.DataFrame(
        final_decisions
    )


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
            columns=[
                "Sort Order"
            ]
        )

        .reset_index(
            drop=True
        )

    )


    print(
        "FINAL PORTFOLIO DECISION SIZE:",
        result.shape
    )


    return result