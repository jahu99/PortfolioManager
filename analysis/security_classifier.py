"""
security_classifier.py

Purpose
-------
Provides the single source of truth for classifying portfolio
securities as STOCK, ETF, or CASH.

The portfolio uses exchange-qualified Yahoo Finance tickers such
as IWDA.L, VUAA.L and SEC0.DE. Classification therefore checks
both the full ticker and the base ticker without the exchange
suffix.

ETF classification can also use the security name as a fallback.
"""

ETF_TICKERS = {
    "IWDA",
    "AEMD",
    "VUAA",
    "SEC0",
}


def classify_security(ticker, name=""):
    """
    Classify a security as STOCK, ETF, or CASH.

    Handles exchange-qualified tickers such as:
        IWDA.L
        VUAA.L
        SEC0.DE
        AEMD.L
    """

    ticker = str(ticker).upper().strip()
    name = str(name).upper().strip()

    # ---------------------------------------------------------
    # CASH
    # ---------------------------------------------------------

    if ticker == "CASH":
        return "CASH"

    # ---------------------------------------------------------
    # Normalise exchange-qualified ticker
    #
    # IWDA.L  -> IWDA
    # VUAA.L  -> VUAA
    # SEC0.DE -> SEC0
    # AEMD.L  -> AEMD
    # ---------------------------------------------------------

    base_ticker = ticker.split(".", 1)[0]

    # ---------------------------------------------------------
    # Explicit ETF knowledge
    # ---------------------------------------------------------

    if base_ticker in ETF_TICKERS:
        return "ETF"

    # ---------------------------------------------------------
    # Name-based ETF detection
    # ---------------------------------------------------------

    if "ETF" in name:
        return "ETF"

    if "ISHARES" in name:
        return "ETF"

    if "VANGUARD" in name:
        return "ETF"

    if "AMUNDI" in name:
        return "ETF"

    if "UCITS" in name:
        return "ETF"

    return "STOCK"