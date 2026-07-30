def score_stock(df):

    latest = df.iloc[-1]

    reasons = []


    # ---------------------------------
    # Individual category scores
    # ---------------------------------

    trend_score = 0
    momentum_score = 0
    volume_score = 0
    risk_score = 15


    close = latest["Close"]
    sma50 = latest["SMA50"]
    sma200 = latest["SMA200"]
    rsi = latest["RSI"]
    rtn = latest["Return_3m"] * 100


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



    # Long term trend

    if distance200 > 0:

        trend_score += 15

        reasons.append(
            "Above 200 DMA"
        )

    else:

        reasons.append(
            "Below 200 DMA"
        )

        risk_score -= 8



    # Avoid chasing extended stocks

    if 0 <= distance50 <= 5:

        trend_score += 15

        reasons.append(
            "Healthy position near 50 DMA"
        )


    elif distance50 > 15:

        trend_score += 2

        risk_score -= 10

        reasons.append(
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



    # Trend structure

    if sma50 > sma200:

        trend_score += 10

        reasons.append(
            "Positive long term trend"
        )

    else:

        risk_score -= 5

        reasons.append(
            "Weak trend structure"
        )



    # ---------------------------------
    # Momentum Score (35)
    # ---------------------------------


    # RSI entry quality

    if 50 <= rsi <= 65:

        momentum_score += 15

        reasons.append(
            "Optimal RSI entry zone"
        )


    elif 65 < rsi <= 70:

        momentum_score += 8

        reasons.append(
            "Strong but approaching overbought"
        )


    elif rsi > 70:

        momentum_score -= 5

        reasons.append(
            "Overbought RSI"
        )


    elif 40 <= rsi < 50:

        momentum_score += 5

        reasons.append(
            "Recovering RSI"
        )


    else:

        reasons.append(
            "Weak RSI"
        )



    # MACD confirmation

    if latest["MACD"] > latest["MACD_signal"]:

        momentum_score += 10

        reasons.append(
            "MACD bullish"
        )

    else:

        reasons.append(
            "MACD bearish"
        )



    # Moderate momentum preferred

    if 5 <= rtn <= 25:

        momentum_score += 10

        reasons.append(
            "Healthy momentum"
        )


    elif rtn > 40:

        risk_score -= 5

        reasons.append(
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

        reasons.append(
            "Weak volume"
        )



    # ---------------------------------
    # Risk controls
    # ---------------------------------


    if rsi > 75:

        risk_score -= 8

        reasons.append(
            "Extreme overbought"
        )


    if close < sma50:

        risk_score -= 3

        reasons.append(
            "Below 50 DMA"
        )


    if close < sma200:

        risk_score -= 5

        reasons.append(
            "Below 200 DMA"
        )


    if risk_score < 0:

        risk_score = 0



    # ---------------------------------
    # Final score
    # ---------------------------------

    score = (
        trend_score
        +
        momentum_score
        +
        volume_score
        +
        risk_score
    )



    if score > 100:

        score = 100


    if score < 0:

        score = 0



    return round(score), reasons