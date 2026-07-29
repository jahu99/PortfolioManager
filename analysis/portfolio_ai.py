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


    # -----------------------------
    # Decision logic
    # -----------------------------

    if investment_score >= 80:

        decision = "HOLD"

        reasons.append(
            "High investment score"
        )


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


    # -----------------------------
    # Quality assessment
    # -----------------------------

    if quality_score >= 70:

        reasons.append(
            "Strong business quality"
        )

    elif quality_score < 50:

        risks.append(
            "Quality below preferred level"
        )


    # -----------------------------
    # Technical assessment
    # -----------------------------

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


    # -----------------------------
    # Review triggers
    # -----------------------------

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
            review_triggers
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


    # Convert DataFrame to records if required

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