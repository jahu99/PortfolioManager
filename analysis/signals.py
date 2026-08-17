# analysis/signals.py
"""
Generates the stock-level trading signal from the Investment Score
and supporting technical / quality conditions.

Architecture:

    Investment Score
          +
    Technical Score
          +
    Quality Score
          +
    Market Conditions
          |
          v
       Signal
          |
          v
    Portfolio Decision Engine
          |
          v
    BUY / BUY MORE / HOLD / REDUCE / SELL

IMPORTANT:

The signal is a stock-level assessment.

It does NOT determine whether an existing position should be
REDUCED or completely SOLD.

That decision belongs to the portfolio decision engine, which
must consider:

    - current position size
    - portfolio concentration
    - sector exposure
    - conviction
    - risk
    - capital availability
    - historical recommendation reliability

HOLD remains the preferred default where there is insufficient
evidence for a stronger action.
"""


def generate_signal(
    investment_score,
    quality_score,
    technical_score,
    df
):
    """
    Generate a stock-level signal.

    Returns:

        STRONG BUY
        BUY
        WATCH
        HOLD
        SELL
        STRONG SELL
    """

    latest = df.iloc[-1]

    price = float(
        latest["Close"]
    )

    sma200 = float(
        latest["SMA200"]
    )

    rsi = float(
        latest["RSI"]
    )


    # =================================================
    # STRONG BUY
    # =================================================
    #
    # Requires strong overall conviction AND supporting
    # technical and quality conditions.
    #

    if (
        investment_score >= 80
        and technical_score >= 75
        and quality_score >= 60
        and price > sma200
        and 40 <= rsi <= 75
    ):

        return "STRONG BUY"


    # =================================================
    # BUY
    # =================================================

    elif investment_score >= 70:

        return "BUY"


    # =================================================
    # WATCH
    # =================================================
    #
    # Potential opportunity, but not enough conviction
    # for a BUY.
    #

    elif investment_score >= 60:

        return "WATCH"


    # =================================================
    # HOLD
    # =================================================
    #
    # This is deliberately the broad default zone.
    #

    elif investment_score >= 45:

        return "HOLD"


    # =================================================
    # STRONG SELL
    # =================================================
    #
    # Genuine deterioration across the overall score
    # and technical trend.
    #
    # This is intentionally difficult to trigger.
    #

    elif (
        investment_score < 30
        and technical_score < 40
        and price < sma200
        and rsi < 40
    ):

        return "STRONG SELL"


    # =================================================
    # SELL
    # =================================================
    #
    # Weak stock, but not necessarily severe enough
    # to justify an immediate full exit.
    #

    else:

        return "SELL"