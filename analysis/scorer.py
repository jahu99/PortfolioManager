from analysis.adaptive_learning import get_adaptive_adjustments


def score_stock(df):

    latest = df.iloc[-1]

    reasons = []
    risks = []


    # ---------------------------------
    # Base category scores
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



    # Long term trend filter

    if distance200 > 0:

        trend_score += 8

        reasons.append(
            "Above 200 DMA"
        )

    else:

        risks.append(
            "Below 200 DMA"
        )

        risk_score -= 8



    # Entry position relative to 50 DMA

    if 0 <= distance50 <= 3:

        trend_score += 15

        reasons.append(
            "Near 50 DMA entry zone"
        )


    elif distance50 > 15:

        trend_score -= 5

        risk_score -= 5

        risks.append(
            "Overextended above 50 DMA"
        )


    elif distance50 > 5:

        trend_score += 2

        risks.append(
            "Extended above 50 DMA"
        )


    else:

        trend_score += 8

        reasons.append(
            "Pullback opportunity"
        )



    # Trend structure

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

    # Prefer earlier momentum

    if 45 <= rsi <= 60:

        momentum_score += 15

        reasons.append(
            "Healthy RSI entry zone"
        )


    elif 60 < rsi <= 70:

        momentum_score += 8

        reasons.append(
            "Strong momentum"
        )


    elif rsi > 70:

        risks.append(
            "Overbought RSI"
        )

        risk_score -= 5


    elif 35 <= rsi < 45:

        momentum_score += 5

        reasons.append(
            "Recovering momentum"
        )


    else:

        risks.append(
            "Weak RSI"
        )



    # MACD

    if latest["MACD"] > latest["MACD_signal"]:

        momentum_score += 10

        reasons.append(
            "MACD bullish"
        )

    else:

        risks.append(
            "MACD bearish"
        )



    # Recent performance

    if 0 <= rtn <= 15:

        momentum_score += 10

        reasons.append(
            "Healthy recent momentum"
        )


    elif rtn > 25:

        risk_score -= 8

        risks.append(
            "Extended recent performance"
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
        float(latest["Volume"])
        /
        float(latest["Volume_avg"])
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
    # Risk adjustments
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
    # Technical Score
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
    # Adaptive adjustment
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



    return {


        "Score": round(
            base_score
        ),


        "Technical Score": round(
            technical_score
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


        # Maintains compatibility
        "Investment Score": round(
            technical_score
        ),


        "Confidence": confidence,


        "Technical Reasons": reasons,

        "Technical Risks": risks,


        "Recommendation Reasons": reasons,

        "Recommendation Risks": risks

    }