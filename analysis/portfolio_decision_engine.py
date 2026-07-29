def generate_portfolio_decisions(
    holdings,
    opportunities
):

    decisions = []


    # -----------------------------
    # Analyse current holdings
    # -----------------------------

    holding_tickers = set(
        holdings["Ticker"]
        if hasattr(holdings, "columns")
        else []
    )


    # -----------------------------
    # Review existing holdings
    # -----------------------------

    for _, stock in opportunities.iterrows():

        ticker = stock.get(
            "Ticker"
        )

        investment_score = stock.get(
            "Investment Score",
            0
        )

        quality_score = stock.get(
            "Quality Score",
            0
        )

        ai_decision = stock.get(
            "AI Decision",
            ""
        )

        confidence = stock.get(
            "AI Conviction",
            "Low"
        )


        # Existing holding
        if ticker in holding_tickers:


            if investment_score < 50:

                decisions.append(
                    {
                        "Ticker": ticker,
                        "Action": "REDUCE",
                        "Reason":
                            "Existing holding has weak investment score",
                        "Investment Score":
                            investment_score,
                        "Quality Score":
                            quality_score,
                        "Conviction":
                            confidence
                    }
                )


            elif ai_decision == "BUY":

                decisions.append(
                    {
                        "Ticker": ticker,
                        "Action": "HOLD / ADD",
                        "Reason":
                            "Existing holding remains attractive",
                        "Investment Score":
                            investment_score,
                        "Quality Score":
                            quality_score,
                        "Conviction":
                            confidence
                    }
                )


            else:

                decisions.append(
                    {
                        "Ticker": ticker,
                        "Action": "HOLD",
                        "Reason":
                            "No significant change required",
                        "Investment Score":
                            investment_score,
                        "Quality Score":
                            quality_score,
                        "Conviction":
                            confidence
                    }
                )


        # New opportunity
        else:


            if (
                ai_decision == "BUY"
                and investment_score >= 75
            ):

                decisions.append(
                    {
                        "Ticker": ticker,
                        "Action": "BUY",
                        "Reason":
                            "High conviction opportunity",
                        "Investment Score":
                            investment_score,
                        "Quality Score":
                            quality_score,
                        "Conviction":
                            confidence
                    }
                )


    return decisions