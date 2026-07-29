import pandas as pd

from analysis.confidence import calculate_confidence



def generate_recommendation(
    ticker,
    signal,
    investment_score,
    technical_score,
    quality_score,
    growth_score,
    technical_reasons,
    quality_reasons,
    signal_performance=None,
    score_bucket_performance=None
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
        "Negative earnings growth",
        "Weak volume"

    ]


    for reason in explanation:

        if reason in risk_keywords:

            risks.append(reason)



    # ---------------------------------
    # Quality-adjusted recommendation
    # ---------------------------------

    if (
        investment_score >= 85
        and quality_score >= 75
    ):

        recommendation = "STRONG BUY"


    elif (
        investment_score >= 75
        and quality_score >= 65
    ):

        recommendation = "BUY"


    elif investment_score >= 65:

        recommendation = "WATCH"


    else:

        recommendation = "HOLD" 

    # ---------------------------------
    # Internal conviction score
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

    if growth_score >= 80:
        conviction += 2

    elif growth_score >= 65:
        conviction += 1

    if len(risks) == 0:

        conviction += 1



    # ---------------------------------
    # Historical confidence engine
    # ---------------------------------

    historical_confidence = calculate_confidence(

        investment_score,
        technical_score,
        quality_score,
        growth_score,
        risks,
        signal_performance, 
        score_bucket_performance

    )


    confidence_score = historical_confidence.get(
        "Confidence",
        50
    )


    confidence_reasons = historical_confidence.get(
        "Confidence Reasons",
        []
    )



    # ---------------------------------
    # Combine conviction + evidence
    # ---------------------------------

    if (
        confidence_score >= 80
        and conviction >= 4
    ):

        confidence = "High"


    elif (
        confidence_score >= 60
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


        "Signal": signal,


        "Recommendation": recommendation,


        "Investment Score": investment_score,


        "Technical Score": technical_score,


        "Quality Score": quality_score,


        "Confidence": confidence,


        "Confidence Score": confidence_score,


        "Confidence Reasons":
            confidence_reasons,


        "Reasons":
            explanation[:6],


        "Risks":
            risks[:5]

    }