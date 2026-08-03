from analysis.adaptive_learning import get_adaptive_adjustments
from analysis.investment_score import calculate_investment_score


def safe_divide(
    numerator,
    denominator,
    default=0
):

    try:

        if denominator in (0, None):

            return default


        return numerator / denominator


    except Exception:

        return default
    
# =====================================================
# Stock Scoring Engine
# =====================================================


import pandas as pd


def score_stock(df):

    """
    Technical scoring engine.

    Returns:
    - Technical Score
    - Trend Score
    - Momentum Score
    - Volume Score
    - Risk Score
    - Reasons
    - Risks
    """

    technical_score = 0

    trend_score = 0
    momentum_score = 0
    volume_score = 0
    risk_score = 0

    reasons = []
    risks = []


    if df.empty:
        return {
            "Technical Score": 0,
            "Trend Score": 0,
            "Momentum Score": 0,
            "Volume Score": 0,
            "Risk Score": 0,
            "Technical Reasons": [],
            "Technical Risks": []
        }


    latest = df.iloc[-1]


    try:

        close = float(
            latest["Close"]
        )

        sma50 = float(
            latest["SMA50"]
        )

        sma200 = float(
            latest["SMA200"]
        )

        rsi = float(
            latest["RSI"]
        )

        return_3m = float(
            latest["Return_3m"]
        )

        volume = float(
            latest["Volume"]
        )

        volume_avg = float(
            latest["Volume_avg"]
        )


    except Exception as e:

        print(
            f"Score data error: {e}"
        )

        return {
            "Technical Score": 0,
            "Trend Score": 0,
            "Momentum Score": 0,
            "Volume Score": 0,
            "Risk Score": 0,
            "Technical Reasons": [],
            "Technical Risks": []
        }



    # =============================
    # TREND SCORE (40)
    # =============================

    if close > sma200:

        trend_score += 25

        reasons.append(
            "Price above 200 DMA"
        )

    else:

        risks.append(
            "Price below 200 DMA"
        )


    if close > sma50:

        trend_score += 15

        reasons.append(
            "Price above 50 DMA"
        )

    else:

        risks.append(
            "Price below 50 DMA"
        )



    # =============================
    # MOMENTUM SCORE (30)
    # =============================

    if 50 <= rsi <= 70:

        momentum_score += 15

        reasons.append(
            "Healthy RSI momentum"
        )


    elif rsi > 70:

        risks.append(
            "Overbought RSI"
        )


    elif rsi < 40:

        risks.append(
            "Weak RSI momentum"
        )



    if return_3m > 0.20:

        momentum_score += 15

        reasons.append(
            "Strong 3 month return"
        )


    elif return_3m > 0:

        momentum_score += 8

        reasons.append(
            "Positive 3 month return"
        )


    else:

        risks.append(
            "Negative 3 month return"
        )



    # =============================
    # VOLUME SCORE (20)
    # =============================

    if volume_avg > 0:

        volume_ratio = (
            volume /
            volume_avg
        )

    else:

        volume_ratio = 0



    if volume_ratio > 1.5:

        volume_score += 20

        reasons.append(
            "Strong volume confirmation"
        )


    elif volume_ratio > 1.2:

        volume_score += 10

        reasons.append(
            "Improving volume"
        )


    else:

        risks.append(
            "Weak volume confirmation"
        )



    # =============================
    # RISK SCORE (10)
    # =============================

    if close > sma200:

        risk_score += 10

    else:

        risk_score += 2



    # =============================
    # FINAL SCORE
    # =============================

    technical_score = (
        trend_score
        +
        momentum_score
        +
        volume_score
        +
        risk_score
    )


    technical_score = min(
        technical_score,
        100
    )


    return {

        "Technical Score": technical_score,

        "Trend Score": trend_score,

        "Momentum Score": momentum_score,

        "Volume Score": volume_score,

        "Risk Score": risk_score,

        "Technical Reasons": reasons,

        "Technical Risks": risks

    }