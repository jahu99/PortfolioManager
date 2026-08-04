import pandas as pd


def generate_portfolio_decisions(
    holdings,
    opportunities
):
    """
    Generates BUY / HOLD / REDUCE / SELL decisions
    for existing portfolio holdings and new opportunities.

    ETFs are ignored for decision making.
    """


    decisions = []


    if holdings is None or holdings.empty:
        holdings = pd.DataFrame()


    if opportunities is None:
        opportunities = pd.DataFrame()



    # -----------------------------------
    # Create scanner lookup
    # -----------------------------------

    scanner = {}

    if not opportunities.empty:

        for _, row in opportunities.iterrows():

            ticker = row.get(
                "Ticker"
            )

            if ticker:

                scanner[ticker] = row



    # -----------------------------------
    # Existing holdings
    # -----------------------------------

    for _, holding in holdings.iterrows():

        ticker = holding.get(
            "Ticker"
        )


        asset_type = holding.get(
            "Type",
            "STOCK"
        )


        # Ignore ETFs
        if asset_type == "ETF":

            continue



        data = scanner.get(
            ticker,
            {}
        )


        investment_score = float(
            data.get(
                "Investment Score",
                holding.get(
                    "Investment Score",
                    0
                )
                or 0
            )
        )


        quality_score = float(
            data.get(
                "Quality Score",
                holding.get(
                    "Quality Score",
                    0
                )
                or 0
            )
        )


        trend = data.get(
            "Trend",
            holding.get(
                "Trend",
                "Unknown"
            )
        )


        signal = data.get(
            "Signal",
            ""
        )


        confidence = data.get(
            "Confidence",
            "Unknown"
        )



        # -----------------------------
        # Decision rules
        # -----------------------------


        # Weak investment case
        if (
            investment_score < 50
            and
            quality_score < 40
        ):


            action = "SELL"

            reason = (
                "Weak investment score "
                "and poor quality metrics"
            )



        elif (
            investment_score < 65
            and
            trend == "Negative"
        ):


            action = "REDUCE"

            reason = (
                "Negative trend and "
                "weakening investment case"
            )



        elif (
            signal in
            [
                "BUY",
                "STRONG BUY"
            ]
            and
            investment_score >= 85
        ):


            action = "BUY"

            reason = (
                "Existing holding remains "
                "high conviction"
            )



        else:


            action = "HOLD"

            reason = (
                "Holding remains appropriate"
            )



        decisions.append(

            {
                "Ticker": ticker,
                "Action": action,
                "Reason": reason,
                "Investment Score":
                    investment_score,
                "Quality Score":
                    quality_score,
                "Trend":
                    trend,
                "Confidence":
                    confidence,
                "Current Allocation %":
                    holding.get(
                        "Allocation %",
                        0
                    )
            }

        )



    # -----------------------------------
    # New opportunities
    # -----------------------------------

    existing = set(
        holdings["Ticker"]
        if "Ticker" in holdings.columns
        else []
    )


    for ticker, stock in scanner.items():


        if ticker in existing:
            continue


        investment_score = float(
            stock.get(
                "Investment Score",
                0
            )
        )


        quality_score = float(
            stock.get(
                "Quality Score",
                0
            )
        )


        signal = stock.get(
            "Signal",
            ""
        )


        if (
            signal in
            [
                "BUY",
                "STRONG BUY"
            ]
            and
            investment_score >= 75
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
                    "Confidence":
                        stock.get(
                            "Confidence",
                            "Unknown"
                        )
                }

            )


    return decisions