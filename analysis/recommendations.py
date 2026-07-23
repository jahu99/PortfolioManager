def generate_recommendation(
    ticker,
    signal,
    investment_score,
    technical_score,
    quality_score,
    technical_reasons,
    quality_reasons
):

    explanation = []
    risks = []


    # ---------------------------------
    # Collect positive factors
    # ---------------------------------

    for reason in (
        technical_reasons
        +
        quality_reasons
    ):

        if reason not in explanation:

            explanation.append(reason)



    # ---------------------------------
    # Identify risks
    # ---------------------------------

    risk_keywords = [

        "Below 200 DMA",
        "Below 50 DMA",
        "Weak RSI",
        "MACD bearish",
        "Overbought",
        "High debt",
        "Negative revenue growth",
        "Negative earnings growth"

    ]


    for reason in explanation:

        if reason in risk_keywords:

            risks.append(reason)



    # ---------------------------------
    # Final recommendation
    # ---------------------------------

    if investment_score >= 85:

        recommendation = "STRONG BUY"


    elif investment_score >= 75:

        recommendation = "BUY"


    elif investment_score >= 65:

        recommendation = "WATCH"


    else:

        recommendation = "HOLD"



    # ---------------------------------
    # Confidence calculation
    # ---------------------------------

    conviction = 0


    if technical_score >= 80:

        conviction += 2

    elif technical_score >= 70:

        conviction += 1



    if quality_score >= 80:

        conviction += 2

    elif quality_score >= 65:

        conviction += 1



    if len(risks) == 0:

        conviction += 1



    if (
        investment_score >= 85
        and conviction >= 4
    ):

        confidence = "High"


    elif (
        investment_score >= 70
        and conviction >= 2
    ):

        confidence = "Medium"


    else:

        confidence = "Low"



    # ---------------------------------
    # Return recommendation object
    # ---------------------------------

    return {

        "Ticker": ticker,

        "Recommendation": recommendation,

        "Investment Score": investment_score,

        "Technical Score": technical_score,

        "Quality Score": quality_score,

        "Confidence": confidence,

        "Reasons": explanation[:6],

        "Risks": risks[:5]

    }