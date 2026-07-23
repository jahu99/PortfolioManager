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


    # ---------------------------------
    # Trend Score (40)
    # ---------------------------------

    distance200 = (
        (latest["Close"] - latest["SMA200"])
        /
        latest["SMA200"]
    ) * 100


    if distance200 > 15:

        trend_score += 25
        reasons.append(
            "Strongly above 200 DMA"
        )

    elif distance200 > 5:

        trend_score += 20
        reasons.append(
            "Above 200 DMA"
        )

    elif distance200 > 0:

        trend_score += 10
        reasons.append(
            "Slightly above 200 DMA"
        )

    else:

        reasons.append(
            "Below 200 DMA"
        )



    distance50 = (
        (latest["Close"] - latest["SMA50"])
        /
        latest["SMA50"]
    ) * 100


    if distance50 > 10:

        trend_score += 15
        reasons.append(
            "Strongly above 50 DMA"
        )

    elif distance50 > 3:

        trend_score += 10
        reasons.append(
            "Above 50 DMA"
        )

    elif distance50 > 0:

        trend_score += 5
        reasons.append(
            "Slightly above 50 DMA"
        )

    else:

        reasons.append(
            "Below 50 DMA"
        )



    # Trend structure

    if latest["SMA50"] < latest["SMA200"]:

        risk_score -= 10

        reasons.append(
            "50 DMA below 200 DMA"
        )



    # ---------------------------------
    # Momentum Score (45)
    # ---------------------------------

    rsi = latest["RSI"]


    if 55 <= rsi <= 65:

        momentum_score += 15

        reasons.append(
            "Ideal RSI"
        )

    elif 50 <= rsi < 55:

        momentum_score += 12

        reasons.append(
            "Healthy RSI"
        )

    elif 65 < rsi <= 70:

        momentum_score += 10

        reasons.append(
            "Strong RSI"
        )

    elif 45 <= rsi < 50:

        momentum_score += 5

        reasons.append(
            "Neutral RSI"
        )

    else:

        reasons.append(
            "Weak RSI"
        )



    # MACD

    if latest["MACD"] > latest["MACD_signal"]:

        momentum_score += 15

        reasons.append(
            "MACD bullish"
        )

    else:

        reasons.append(
            "MACD bearish"
        )



    # 3 month momentum

    rtn = latest["Return_3m"] * 100


    if rtn > 30:

        momentum_score += 15

        reasons.append(
            "Excellent 3 month momentum"
        )

    elif rtn > 15:

        momentum_score += 12

        reasons.append(
            "Strong 3 month momentum"
        )

    elif rtn > 5:

        momentum_score += 8

        reasons.append(
            "Positive 3 month momentum"
        )

    elif rtn > 0:

        momentum_score += 4

        reasons.append(
            "Slightly positive momentum"
        )

    else:

        reasons.append(
            "Negative 3 month momentum"
        )



    # ---------------------------------
    # Volume Score (15)
    # ---------------------------------

    volume_ratio = (
        latest["Volume"]
        /
        latest["Volume_avg"]
    )


    if volume_ratio > 2:

        volume_score += 15

        reasons.append(
            "Exceptional volume"
        )

    elif volume_ratio > 1.5:

        volume_score += 12

        reasons.append(
            "Strong volume"
        )

    elif volume_ratio > 1.2:

        volume_score += 8

        reasons.append(
            "Above average volume"
        )

    elif volume_ratio > 1:

        volume_score += 5

        reasons.append(
            "Volume improving"
        )

    else:

        reasons.append(
            "Weak volume"
        )



    # ---------------------------------
    # Risk penalties
    # ---------------------------------

    if latest["Close"] < latest["SMA200"]:

        risk_score -= 8

        reasons.append(
            "Below 200 DMA"
        )



    if latest["Close"] < latest["SMA50"]:

        risk_score -= 3

        reasons.append(
            "Below 50 DMA"
        )



    if rsi > 75:

        risk_score -= 5

        reasons.append(
            "Overbought"
        )



    if rsi < 35:

        risk_score -= 5

        reasons.append(
            "Oversold"
        )



    if risk_score < 0:

        risk_score = 0



    # ---------------------------------
    # Base score
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



    # ---------------------------------
    # Leadership bonuses
    # ---------------------------------

    if (
        distance200 > 15
        and rtn > 15
    ):

        score += 5

        reasons.append(
            "Strong price leadership"
        )



    if (
        latest["MACD"]
        >
        latest["MACD_signal"]
        and rsi >= 50
    ):

        score += 3

        reasons.append(
            "Positive momentum confirmation"
        )



    if volume_ratio > 1.2:

        score += 2

        reasons.append(
            "Institutional interest"
        )



    # ---------------------------------
    # Final score
    # ---------------------------------

    if score > 100:

        score = 100



    return round(score), reasons