def generate_holding_review(
    holding,
    stock_result
):

    ticker = holding["Ticker"]

    decision = "HOLD"
    conviction = "Medium"

    reasons = []
    risks = []
    actions = []
    review_triggers = []


    investment_score = stock_result.get(
        "Investment Score",
        0
    )

    quality_score = stock_result.get(
        "Quality Score",
        0
    )

    signal = stock_result.get(
        "Signal",
        "UNKNOWN"
    )


    allocation = holding.get(
        "Allocation %",
        0
    )

    sector_allocation = holding.get(
        "Sector Allocation %",
        0
    )

    sector_risk = holding.get(
        "Sector Risk",
        "Low"
    )


    # ---------------------------------
    # Investment quality assessment
    # ---------------------------------

    if investment_score >= 80:

        reasons.append(
            "High investment score"
        )

        conviction = "High"


    elif investment_score >= 60:

        decision = "REVIEW"

        reasons.append(
            "Moderate investment score"
        )


    else:

        decision = "REDUCE"

        risks.append(
            "Weak investment score"
        )

        actions.append(
            "Consider reducing position"
        )

        conviction = "Low"



    # ---------------------------------
    # Business quality
    # ---------------------------------

    if quality_score >= 70:

        reasons.append(
            "Strong business quality"
        )


    elif quality_score < 50:

        risks.append(
            "Quality below preferred level"
        )

        if decision == "HOLD":
            decision = "REVIEW"



    # ---------------------------------
    # Technical signal
    # ---------------------------------

    if signal in [
        "BUY",
        "STRONG BUY"
    ]:

        reasons.append(
            "Positive technical signal"
        )


    elif signal in [
        "SELL",
        "STRONG SELL"
    ]:

        risks.append(
            "Negative technical signal"
        )

        decision = "REDUCE"




    # ---------------------------------
    # Portfolio concentration
    # ---------------------------------

    concentration_risk = 0


    # Single holding concentration

    if allocation >= 50:

        risks.append(
            "Extreme single stock concentration"
        )

        actions.append(
            "Consider reducing position size"
        )

        concentration_risk += 30


    elif allocation >= 35:

        risks.append(
            "High single stock concentration"
        )

        actions.append(
            "Monitor position sizing"
        )

        concentration_risk += 15


    elif allocation >= 20:

        risks.append(
            "Large portfolio position"
        )

        actions.append(
            "Avoid increasing position"
        )

        concentration_risk += 5



    # Sector concentration

    if sector_allocation >= 70:

        risks.append(
            "Extreme sector concentration risk"
        )

        actions.append(
            "Increase diversification outside sector"
        )

        concentration_risk += 20


    elif sector_allocation >= 40:

        risks.append(
            "Sector concentration risk"
        )

        concentration_risk += 10




    # ---------------------------------
    # Final decision adjustment
    # ---------------------------------

    # Strong companies get REVIEW not REDUCE

    if concentration_risk >= 30:

        if investment_score < 70 or quality_score < 50:

            decision = "REDUCE"

            conviction = "High"

        else:

            decision = "REVIEW"

            conviction = "Medium"



    # Clean up duplicates

    risks = list(dict.fromkeys(risks))
    reasons = list(dict.fromkeys(reasons))
    actions = list(dict.fromkeys(actions))


    # ---------------------------------
    # Review triggers
    # ---------------------------------

    review_triggers.extend(
        [
            "Investment score falls below 60",
            "Trend breaks below 200 DMA"
        ]
    )


    return {

        "Ticker": ticker,

        "AI Holding Decision":
            decision,

        "AI Holding Conviction":
            conviction,

        "AI Holding Reasons":
            reasons,

        "AI Holding Risks":
            risks,

        "AI Holding Actions":
            actions,

        "AI Holding Review Triggers":
            review_triggers,

        "Allocation %":
            allocation,

        "Sector Allocation %":
            sector_allocation,

        "Sector Risk":
            sector_risk
    }





def generate_portfolio_review(
    holdings,
    results
):

    reviews = []


    results_lookup = {
        r["Ticker"]: r
        for r in results
    }


    if hasattr(holdings, "to_dict"):

        holdings = holdings.to_dict(
            "records"
        )


    for holding in holdings:

        ticker = holding["Ticker"]


        if ticker in results_lookup:

            review = generate_holding_review(
                holding,
                results_lookup[ticker]
            )

            reviews.append(
                review
            )


    return reviews