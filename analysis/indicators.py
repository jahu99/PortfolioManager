import pandas as pd
import ta


def add_indicators(df):

    df = df.copy()

    # Moving averages
    df["SMA50"] = (
        df["Close"]
        .rolling(window=50)
        .mean()
    )

    df["SMA200"] = (
        df["Close"]
        .rolling(window=200)
        .mean()
    )

    # RSI
    rsi = ta.momentum.RSIIndicator(
        close=df["Close"],
        window=14
    )

    df["RSI"] = rsi.rsi()

    # MACD
    macd = ta.trend.MACD(
        close=df["Close"]
    )

    df["MACD"] = macd.macd()

    df["MACD_signal"] = (
        macd.macd_signal()
    )

    # Volume average
    df["Volume_avg"] = (
        df["Volume"]
        .rolling(window=20)
        .mean()
    )

    # 3 month return (~63 trading days)
    df["Return_3m"] = (
        df["Close"]
        .pct_change(periods=63)
    )

    # Remove rows where indicators are not available
    df = df.dropna()

    return df