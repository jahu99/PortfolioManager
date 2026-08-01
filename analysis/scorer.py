from analysis.adaptive_learning import get_adaptive_adjustments


def score_stock(df):

    latest = df.iloc[-1]

    reasons = []
    risks = []


    # ---------------------------------
    # Individual category scores
    # ---------------------------------

    trend_score = 0
    momentum_score = 0
    volume_score = 0
    risk_score = 15


    close = float(latest["Close"])
    sma50 = float(latest["SMA50"])
    sma200 = float(latest["SMA200"])
    rsi = float(latest["RSI"])

    rtn = float(latest["Return_3m"]) * 100


    # ---------------------------------
    # Trend Score (40)
    # ---------------------------------

    distance200 = (
        (close - sma200)
        /
        sma200
    ) * 100


    distance50 = (
        (close - sma50)
        /
        sma50
    ) * 100



    if distance200 > 0:

        trend_score += 15

        reasons.append(
            "Above 200 DMA"
        )

    else:

        risks.append(
            "Below 200 DMA"
        )

        risk_score -= 8



    if 0 <= distance50 <= 5:

        trend_score += 15

        reasons.append(
            "Healthy position near 50 DMA"
        )


    elif distance50 > 15:

        trend_score += 2

        risk_score -= 10

        risks.append(
            "Overextended above 50 DMA"
        )


    elif distance50 > 5:

        trend_score += 8

        reasons.append(
            "Moderately above 50 DMA"
        )


    else:

        trend_score += 5

        reasons.append(
            "Pullback opportunity"
        )



    if sma50 > sma200:

        trend_score += 10

        reasons.append(
            "Positive long term trend"
        )

    else:

        risk_score -= 5

        risks.append(
            "Weak trend structure"
        )



    # ---------------------------------
    # Momentum Score (35)
    # ---------------------------------

    if 50 <= rsi <= 65:

        momentum_score += 15

        reasons.append(
            "Optimal RSI entry zone"
        )


    elif 65 < rsi <= 70:

        momentum_score += 8

        reasons.append(
            "Strong momentum"
        )


    elif rsi > 70:

        risks.append(
            "Overbought RSI"
        )


    elif 40 <= rsi < 50:

        momentum_score += 5

        reasons.append(
            "Recovering RSI"
        )


    else:

        risks.append(
            "Weak RSI"
        )



    if latest["MACD"] > latest["MACD_signal"]:

        momentum_score += 10

        reasons.append(
            "MACD bullish"
        )

    else:

        risks.append(
            "MACD bearish"
        )



    if 5 <= rtn <= 25:

        momentum_score += 10

        reasons.append(
            "Healthy 3 month momentum"
        )


    elif rtn > 40:

        risk_score -= 5

        risks.append(
            "Momentum may be exhausted"
        )


    elif rtn > 0:

        momentum_score += 5

        reasons.append(
            "Positive momentum"
        )



    # ---------------------------------
    # Volume Score (15)
    # ---------------------------------

    volume_ratio = (
        latest["Volume"]
        /
        latest["Volume_avg"]
    )


    if volume_ratio > 1.5:

        volume_score += 15

        reasons.append(
            "Strong volume confirmation"
        )


    elif volume_ratio > 1.2:

        volume_score += 10

        reasons.append(
            "Improving volume"
        )


    elif volume_ratio > 1:

        volume_score += 5

        reasons.append(
            "Average volume"
        )


    else:

        risks.append(
            "Weak volume"
        )



    # ---------------------------------
    # Risk Score
    # ---------------------------------

    if rsi > 75:

        risk_score -= 8

        risks.append(
            "Extreme overbought"
        )


    if close < sma50:

        risk_score -= 3

        risks.append(
            "Below 50 DMA"
        )


    if close < sma200:

        risk_score -= 5

        risks.append(
            "Below 200 DMA"
        )


    risk_score = max(
        risk_score,
        0
    )



    # ---------------------------------
    # Base Technical Score
    # ---------------------------------

    base_score = (
        trend_score
        +
        momentum_score
        +
        volume_score
        +
        risk_score
    )


    base_score = max(
        min(
            base_score,
            100
        ),
        0
    )



    # ---------------------------------
    # Adaptive Learning Adjustment
    # ---------------------------------

    adaptive_adjustment = 0


    try:

        adjustments = get_adaptive_adjustments()


        signal = latest.get(
            "Signal",
            "BUY"
        )


        adaptive_adjustment = adjustments.get(
            signal,
            0
        )


    except Exception:

        adaptive_adjustment = 0



    technical_score = (
        base_score
        +
        adaptive_adjustment
    )


    technical_score = max(
        min(
            technical_score,
            100
        ),
        0
    )



    # ---------------------------------
    # Confidence
    # ---------------------------------

    confidence = round(
        (
            (
                trend_score / 40
                +
                momentum_score / 35
                +
                volume_score / 15
                +
                risk_score / 15
            )
            /
            4
        )
        *
        100,
        1
    )



    # ---------------------------------
    # Return Contract
    # Compatible with main.py
    # ---------------------------------

    return {

        "Technical Score": round(
            technical_score
        ),

        "Score": round(
            base_score
        ),


        "Trend Score": round(
            trend_score
        ),

        "Momentum Score": round(
            momentum_score
        ),

        "Volume Score": round(
            volume_score
        ),

        "Risk Score": round(
            risk_score
        ),


        "Adaptive Adjustment": round(
            adaptive_adjustment,
            2
        ),


        "Investment Score": round(
            technical_score
        ),


        "Confidence": confidence,


        "Technical Reasons": reasons,

        "Technical Risks": risks,


        # Backwards compatibility
        "Recommendation Reasons": reasons,

        "Recommendation Risks": risks

    }