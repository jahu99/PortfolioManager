"""
recommendations.py

Purpose:
    Generates investment recommendations for portfolio securities.

    Stocks use the full investment recommendation model, combining:
        - Technical score
        - Quality score
        - Growth score
        - Investment score
        - Historical signal performance
        - Historical score-bucket performance
        - Identified risks

    ETFs are handled separately. They are treated as portfolio holdings
    rather than individual stock-selection opportunities and therefore
    do not receive stock-specific BUY / SELL recommendations or scores.

    The module also calculates recommendation confidence using the
    confidence engine.
"""


import pandas as pd

from analysis.confidence import calculate_confidence


# =====================================================
# Helpers
# =====================================================

def safe_float(value):

    try:

        return float(value)

    except Exception:

        return 0.0


def get_score_bucket(score):

    score = safe_float(score)

    if score >= 85:

        return "High"

    elif score >= 70:

        return "Good"

    elif score >= 50:

        return "Medium"

    else:

        return "Low"


# =====================================================
# Recommendation Engine
# =====================================================

def generate_recommendation(

    ticker,

    signal,

    investment_score,

    technical_score,

    quality_score,

    growth_score,

    technical_reasons,

    quality_reasons,

    sector="Unknown",

    signal_performance=None,

    score_bucket_performance=None,

    security_type="STOCK"

):

    """
    Generate an investment recommendation.

    STOCK:
        Uses the normal investment recommendation engine.

    ETF:
        Returns HOLD because ETFs are managed as portfolio assets
        rather than individual stock-selection opportunities.

    Returns:
        Dictionary containing recommendation, scores, confidence,
        reasons and risks.
    """


    # =================================================
    # ETF HANDLING
    #
    # ETFs do not use the individual-stock
    # recommendation model.
    # =================================================

    if str(security_type).upper().strip() == "ETF":

        return {

            "Ticker":
                ticker,

            "Signal":
                signal,

            "Recommendation":
                "HOLD",

            "Investment Score":
                None,

            "Original Investment Score":
                None,

            "Technical Score":
                None,

            "Quality Score":
                None,

            "Growth Score":
                None,

            "Score Bucket":
                "N/A",

            "Sector":
                sector,

            "Confidence":
                "N/A",

            "Confidence Score":
                None,

            "Confidence Reasons":
                [
                    "ETF — individual stock analysis not applied"
                ],

            "Reasons":
                [
                    "ETF treated as a portfolio holding"
                ],

            "Risks":
                []

        }


    # =================================================
    # STOCK RECOMMENDATION LOGIC
    # =================================================

    explanation = []

    risks = []


    investment_score = safe_float(
        investment_score
    )

    technical_score = safe_float(
        technical_score
    )

    quality_score = safe_float(
        quality_score
    )

    growth_score = safe_float(
        growth_score
    )


    # =================================================
    # COLLECT EVIDENCE
    # =================================================

    for reason in (

        (technical_reasons or [])

        +

        (quality_reasons or [])

    ):

        if reason not in explanation:

            explanation.append(
                reason
            )


    # =================================================
    # RISK DETECTION
    # =================================================

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


    for item in explanation:

        for keyword in risk_keywords:

            if keyword.lower() in item.lower():

                if item not in risks:

                    risks.append(
                        item
                    )


    # =================================================
    # HISTORICAL SIGNAL ADJUSTMENT
    # =================================================

    historical_penalty = 0


    if isinstance(

        signal_performance,

        pd.DataFrame

    ):

        try:

            row = signal_performance[

                signal_performance["Signal"]

                ==

                signal

            ]


            if not row.empty:

                avg_return = float(

                    row.iloc[0][
                        "Average_Return"
                    ]

                )


                if avg_return < 0:

                    historical_penalty = -5

                    risks.append(

                        "Historical signal performance weak"

                    )


        except Exception:

            pass


    # =================================================
    # ADJUSTED INVESTMENT SCORE
    # =================================================

    adjusted_score = (

        investment_score

        +

        historical_penalty

    )


    adjusted_score = max(

        min(

            adjusted_score,

            100

        ),

        0

    )


    # =================================================
    # RECOMMENDATION RULES
    # =================================================

    if (

        adjusted_score >= 90

        and

        quality_score >= 75

        and

        len(risks) <= 1

    ):

        recommendation = "STRONG BUY"


    elif (

        adjusted_score >= 80

        and

        quality_score >= 65

        and

        len(risks) <= 2

    ):

        recommendation = "BUY"


    elif adjusted_score >= 65:

        recommendation = "WATCH"


    else:

        recommendation = "HOLD"


    # =================================================
    # CONVICTION CALCULATION
    # =================================================

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


    # =================================================
    # CONFIDENCE ENGINE
    # =================================================

    historical_confidence = calculate_confidence(

        adjusted_score,

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


    # =================================================
    # CONFIDENCE LEVEL
    # =================================================

    if (

        confidence_score >= 80

        and

        conviction >= 4

    ):

        confidence = "High"


    elif (

        confidence_score >= 60

        and

        conviction >= 2

    ):

        confidence = "Medium"


    else:

        confidence = "Low"


    # =================================================
    # RETURN STOCK RECOMMENDATION
    # =================================================

    return {

        "Ticker":
            ticker,

        "Signal":
            signal,

        "Recommendation":
            recommendation,

        "Investment Score":
            round(
                adjusted_score,
                1
            ),

        "Original Investment Score":
            investment_score,

        "Technical Score":
            technical_score,

        "Quality Score":
            quality_score,

        "Growth Score":
            growth_score,

        "Score Bucket":
            get_score_bucket(
                adjusted_score
            ),

        "Sector":
            sector,

        "Confidence":
            confidence,

        "Confidence Score":
            confidence_score,

        "Confidence Reasons":
            confidence_reasons,

        "Reasons":
            explanation[:6],

        "Risks":
            list(
                set(
                    risks[:5]
                )
            )

    }