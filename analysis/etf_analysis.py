"""
etf_analysis.py

Purpose
-------
Provides ETF-specific analysis for portfolio holdings and ETF
opportunities.

Responsibilities
----------------
1. Analyse ETF price history.
2. Calculate MA50 and MA200.
3. Calculate 6-month and 12-month returns.
4. Calculate an ETF-specific trend/momentum score.
5. Generate an ETF signal.
6. Provide human-readable reasons and risks.

ETF scoring
-----------
Maximum score: 100

Price > MA50:
    +20

Price > MA200:
    +25

MA50 > MA200:
    +20

Positive 6-month return:
    +20

Positive 12-month return:
    +15

Signals
-------
75+:
    BUY

50-74:
    HOLD

Below 50:
    SELL

Important design principle
--------------------------
ETFs are analysed separately from individual stocks.

They do not use:
    - Stock Momentum Score
    - Stock Quality Score
    - Stock Investment Score
    - Stock RSI scoring
    - Stock fundamental analysis

The ETF analysis produces the evidence required by the
portfolio decision engine. The portfolio decision engine
is responsible for deciding whether an ETF should actually
be bought, held, watched or reduced.
"""

import pandas as pd


# ============================================================
# SAFE FLOAT
# ============================================================

def safe_float(value, default=0.0):
    """
    Safely convert a value to float.
    """

    try:

        if value is None:
            return default

        if pd.isna(value):
            return default

        return float(value)

    except Exception:

        return default


# ============================================================
# GET CLOSE SERIES
# ============================================================

def get_close_series(data):
    """
    Extract a clean one-dimensional Close price Series.

    Handles both Series and DataFrame structures returned by
    yfinance.
    """

    if data is None:
        return pd.Series(dtype=float)

    if isinstance(data, pd.Series):

        close = data

    elif isinstance(data, pd.DataFrame):

        if "Close" not in data.columns:
            return pd.Series(dtype=float)

        close = data["Close"]

        # Protect against MultiIndex / nested DataFrame output.
        if isinstance(close, pd.DataFrame):

            close = close.iloc[:, 0]

    else:

        return pd.Series(dtype=float)

    close = (
        pd.to_numeric(
            close,
            errors="coerce"
        )
        .dropna()
    )

    return close


# ============================================================
# ETF SCORE
# ============================================================

def calculate_etf_score(close):
    """
    Calculate the ETF technical score.

    Scoring:

        Price > MA50       +20
        Price > MA200      +25
        MA50 > MA200       +20
        6M return > 0      +20
        12M return > 0     +15

    Returns
    -------
    dict

        Contains the score, indicators, signal, reasons and
        risks.
    """

    close = get_close_series(close)

    if close.empty:

        return {

            "ETF Score": 0,

            "ETF Signal":
                "UNKNOWN",

            "Current Price":
                None,

            "MA50":
                None,

            "MA200":
                None,

            "6M Return %":
                None,

            "12M Return %":
                None,

            "ETF Reasons":
                "ETF price history unavailable",

            "ETF Risks":
                "Insufficient market data"

        }

    # ========================================================
    # CURRENT PRICE
    # ========================================================

    current_price = safe_float(
        close.iloc[-1]
    )

    # ========================================================
    # MOVING AVERAGES
    # ========================================================

    if len(close) >= 50:

        ma50 = safe_float(
            close.tail(50).mean()
        )

    else:

        ma50 = None

    if len(close) >= 200:

        ma200 = safe_float(
            close.tail(200).mean()
        )

    else:

        # Use available history rather than failing.
        ma200 = safe_float(
            close.mean()
        )

    # ========================================================
    # RETURNS
    #
    # Approximate trading-day periods:
    #
    # 6 months  = ~126 trading days
    # 12 months = ~252 trading days
    # ========================================================

    return_6m = None
    return_12m = None

    if len(close) > 126:

        six_month_price = safe_float(
            close.iloc[-127]
        )

        if six_month_price > 0:

            return_6m = (
                (
                    current_price /
                    six_month_price
                ) - 1
            ) * 100

    if len(close) > 252:

        twelve_month_price = safe_float(
            close.iloc[-253]
        )

        if twelve_month_price > 0:

            return_12m = (
                (
                    current_price /
                    twelve_month_price
                ) - 1
            ) * 100

    # ========================================================
    # SCORE
    # ========================================================

    score = 0

    reasons = []

    risks = []

    # --------------------------------------------------------
    # PRICE VS MA50
    # --------------------------------------------------------

    if ma50 is not None:

        if current_price > ma50:

            score += 20

            reasons.append(
                "Price above 50-day moving average"
            )

        else:

            risks.append(
                "Price below 50-day moving average"
            )

    else:

        risks.append(
            "Insufficient history for 50-day moving average"
        )

    # --------------------------------------------------------
    # PRICE VS MA200
    # --------------------------------------------------------

    if ma200 is not None:

        if current_price > ma200:

            score += 25

            reasons.append(
                "Price above 200-day moving average"
            )

        else:

            risks.append(
                "Price below 200-day moving average"
            )

    else:

        risks.append(
            "Insufficient history for 200-day moving average"
        )

    # --------------------------------------------------------
    # MA50 VS MA200
    # --------------------------------------------------------

    if (
        ma50 is not None
        and
        ma200 is not None
    ):

        if ma50 > ma200:

            score += 20

            reasons.append(
                "50-day moving average above 200-day "
                "moving average"
            )

        else:

            risks.append(
                "50-day moving average below 200-day "
                "moving average"
            )

    # --------------------------------------------------------
    # 6-MONTH RETURN
    # --------------------------------------------------------

    if return_6m is not None:

        if return_6m > 0:

            score += 20

            reasons.append(
                f"Positive 6-month return "
                f"({return_6m:.1f}%)"
            )

        else:

            risks.append(
                f"Negative 6-month return "
                f"({return_6m:.1f}%)"
            )

    else:

        risks.append(
            "Insufficient history for 6-month return"
        )

    # --------------------------------------------------------
    # 12-MONTH RETURN
    # --------------------------------------------------------

    if return_12m is not None:

        if return_12m > 0:

            score += 15

            reasons.append(
                f"Positive 12-month return "
                f"({return_12m:.1f}%)"
            )

        else:

            risks.append(
                f"Negative 12-month return "
                f"({return_12m:.1f}%)"
            )

    else:

        risks.append(
            "Insufficient history for 12-month return"
        )

    # ========================================================
    # SIGNAL
    # ========================================================

    if score >= 75:

        signal = "BUY"

    elif score >= 50:

        signal = "HOLD"

    else:

        signal = "SELL"

    # ========================================================
    # FALLBACK TEXT
    # ========================================================

    if not reasons:

        reasons_text = (
            "No positive ETF technical indicators"
        )

    else:

        reasons_text = "; ".join(
            reasons
        )

    if not risks:

        risks_text = (
            "No major ETF technical risks identified"
        )

    else:

        risks_text = "; ".join(
            risks
        )

    # ========================================================
    # RETURN
    # ========================================================

    return {

        "ETF Score":
            score,

        "ETF Signal":
            signal,

        "Current Price":
            current_price,

        "MA50":
            ma50,

        "MA200":
            ma200,

        "6M Return %":
            return_6m,

        "12M Return %":
            return_12m,

        "ETF Reasons":
            reasons_text,

        "ETF Risks":
            risks_text

    }


# ============================================================
# ANALYSE ETF
# ============================================================

def analyse_etf(
    ticker,
    price_data
):
    """
    Analyse one ETF.

    Parameters
    ----------
    ticker : str
        ETF ticker symbol.

    price_data : pandas Series or DataFrame
        Historical ETF price data.

    Returns
    -------
    dict
        ETF analysis result.
    """

    ticker = str(
        ticker
    ).upper().strip()

    analysis = calculate_etf_score(
        price_data
    )

    return {

        "Ticker":
            ticker,

        "Type":
            "ETF",

        **analysis

    }


# ============================================================
# ANALYSE MULTIPLE ETFS
# ============================================================

def analyse_etfs(
    price_data
):
    """
    Analyse multiple ETFs.

    Parameters
    ----------
    price_data : dict
        Dictionary in the form:

            {
                "IWDA": close_series,
                "VUAA": close_series,
                ...
            }

    Returns
    -------
    pandas.DataFrame
        One row per ETF.
    """

    results = []

    if not isinstance(
        price_data,
        dict
    ):

        return pd.DataFrame()

    for ticker, data in price_data.items():

        result = analyse_etf(
            ticker=ticker,
            price_data=data
        )

        results.append(
            result
        )

    if not results:

        return pd.DataFrame()

    return pd.DataFrame(
        results
    )