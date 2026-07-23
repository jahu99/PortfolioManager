def screen_stock(df):

    latest = df.iloc[-1]

    score = 0
    signals = []


    if latest.Close > latest.MA200:
        score += 20
        signals.append("Above 200 DMA")

    if latest.MA50 > latest.MA150 > latest.MA200:
        score += 20
        signals.append("Strong trend")

    if 60 <= latest.RSI <= 75:
        score += 15
        signals.append("Momentum RSI")

    if latest.REL_VOLUME > 1.5:
        score += 15
        signals.append("Volume expansion")

    if latest.Close >= latest["52W_HIGH"] * .85:
        score += 15
        signals.append("Near highs")

    if latest.MACD > latest.MACD_SIGNAL:
        score += 15
        signals.append("MACD bullish")


    return {
        "score": score,
        "signals": signals
    }