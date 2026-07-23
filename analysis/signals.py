def generate_signal(
    investment_score,
    quality_score,
    technical_score,
    df
):

    latest = df.iloc[-1]

    price = float(latest["Close"])
    sma50 = float(latest["SMA50"])
    sma200 = float(latest["SMA200"])
    rsi = float(latest["RSI"])


    # ---------------------------------
    # Strong Buy
    # ---------------------------------

    if (
        investment_score >= 85
        and technical_score >= 75
        and quality_score >= 70
        and price > sma200
        and 45 <= rsi <= 75
    ):

        return "STRONG BUY"



    # ---------------------------------
    # Buy
    # ---------------------------------

    elif investment_score >= 75:

        return "BUY"



    # ---------------------------------
    # Watch
    # ---------------------------------

    elif investment_score >= 65:

        return "WATCH"



    # ---------------------------------
    # Hold
    # ---------------------------------

    elif investment_score >= 50:

        return "HOLD"



    # ---------------------------------
    # Sell
    # ---------------------------------

    else:

        return "SELL"