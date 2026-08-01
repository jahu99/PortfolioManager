def generate_signal(
    investment_score,
    quality_score,
    technical_score,
    df
):

    latest = df.iloc[-1]

    price = float(latest["Close"])
    sma200 = float(latest["SMA200"])
    rsi = float(latest["RSI"])


    if (
        investment_score >= 80
        and technical_score >= 75
        and quality_score >= 60
        and price > sma200
        and 40 <= rsi <= 75
    ):
        return "STRONG BUY"


    elif investment_score >= 70:
        return "BUY"


    elif investment_score >= 60:
        return "WATCH"


    elif investment_score >= 45:
        return "HOLD"


    else:
        return "SELL"