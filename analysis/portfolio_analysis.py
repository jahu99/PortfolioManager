"""
portfolio_analysis.py

Purpose
-------
Analyses the user's existing portfolio holdings.

Responsibilities
----------------
1. Classify each holding as STOCK, ETF, or CASH.
2. Calculate portfolio allocation percentages.
3. Download stock and ETF price history efficiently.
4. Calculate stock trend measures using MA50 and MA200.
5. Attach stock scoring and sector metadata from stock analysis.
6. Attach ETF-specific analysis from etf_analysis.py.
7. Keep ETFs outside the stock technical-analysis framework.
8. Return a clean DataFrame used by the portfolio decision,
   recommendation, optimisation and reporting modules.

Important design principle
--------------------------
Stocks and ETFs are separate analytical asset classes.

STOCKS:
    - Stock technical analysis
    - Momentum Score
    - Quality Score
    - Investment Score
    - Momentum Signal

ETFs:
    - ETF-specific technical analysis
    - ETF Score
    - ETF Signal
    - ETF-specific reasons and risks
    - NO stock Investment Score
    - NO stock Quality Score

CASH:
    - Treated as cash rather than an investment security.
"""

import yfinance as yf
import pandas as pd

from analysis.etf_analysis import analyse_etf


# ============================================================
# KNOWN ETF HOLDINGS
# ============================================================

ETF_TICKERS = {
    "IWDA",
    "VUAA",
    "SEC0",
    "AEMD"
}


# ============================================================
# SECURITY CLASSIFICATION
# ============================================================

def classify_security(ticker, name=""):

    ticker = str(ticker).upper().strip()
    name = str(name).upper().strip()

    if ticker == "CASH":
        return "CASH"

    if ticker in ETF_TICKERS:
        return "ETF"

    if "ETF" in name:
        return "ETF"

    if "ISHARES" in name:
        return "ETF"

    if "VANGUARD" in name:
        return "ETF"

    if "AMUNDI" in name:
        return "ETF"

    return "STOCK"


# ============================================================
# CLOSE SERIES HELPER
# ============================================================

def get_close_series(data):

    if data is None or data.empty:
        return pd.Series(dtype=float)

    if "Close" not in data.columns:
        return pd.Series(dtype=float)

    close = data["Close"]

    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]

    return (
        pd.to_numeric(
            close,
            errors="coerce"
        )
        .dropna()
    )


# ============================================================
# DOWNLOAD PRICE DATA
# ============================================================

def download_price_data(tickers, label):

    if not tickers:
        return {}

    tickers = sorted(
        set(
            str(t).upper().strip()
            for t in tickers
            if t
        )
    )

    if not tickers:
        return {}

    print(
        f"Downloading portfolio price data for "
        f"{len(tickers)} {label}..."
    )

    try:

        data = yf.download(
            tickers=tickers,
            period="1y",
            progress=False,
            auto_adjust=False,
            group_by="column",
            threads=True
        )

    except Exception as e:

        print(
            f"{label.title()} price download failed:",
            e
        )

        return {}

    if data is None or data.empty:
        return {}

    price_data = {}

    # ========================================================
    # MULTI-TICKER RESPONSE
    # ========================================================

    if isinstance(
        data.columns,
        pd.MultiIndex
    ):

        level0 = {
            str(x).upper()
            for x in data.columns.get_level_values(0)
        }

        level1 = {
            str(x).upper()
            for x in data.columns.get_level_values(1)
        }

        # ----------------------------------------------------
        # Format:
        #
        # Close -> Ticker
        # ----------------------------------------------------

        if "CLOSE" in level0:

            for ticker in tickers:

                try:

                    close = data[
                        "Close",
                        ticker
                    ]

                except Exception:

                    continue

                if isinstance(
                    close,
                    pd.DataFrame
                ):

                    close = close.iloc[:, 0]

                close = (
                    pd.to_numeric(
                        close,
                        errors="coerce"
                    )
                    .dropna()
                )

                if not close.empty:
                    price_data[ticker] = close

        # ----------------------------------------------------
        # Format:
        #
        # Ticker -> Close
        # ----------------------------------------------------

        elif "CLOSE" in level1:

            for ticker in tickers:

                try:

                    close = data[
                        ticker,
                        "Close"
                    ]

                except Exception:

                    continue

                if isinstance(
                    close,
                    pd.DataFrame
                ):

                    close = close.iloc[:, 0]

                close = (
                    pd.to_numeric(
                        close,
                        errors="coerce"
                    )
                    .dropna()
                )

                if not close.empty:
                    price_data[ticker] = close

    # ========================================================
    # SINGLE-TICKER RESPONSE
    # ========================================================

    else:

        if "Close" in data.columns:

            close = (
                pd.to_numeric(
                    data["Close"],
                    errors="coerce"
                )
                .dropna()
            )

            if not close.empty:
                price_data[tickers[0]] = close

    print(
        f"{label.title()} price data loaded for "
        f"{len(price_data)} securities"
    )

    return price_data


# ============================================================
# MAIN PORTFOLIO ANALYSIS
# ============================================================

def analyse_portfolio(
    holdings,
    stock_results=None
):

    results = []

    # ========================================================
    # STOCK METADATA LOOKUP
    # ========================================================

    stock_lookup = {}

    if stock_results is not None:

        if isinstance(
            stock_results,
            pd.DataFrame
        ):

            stock_rows = stock_results.to_dict(
                "records"
            )

        elif isinstance(
            stock_results,
            list
        ):

            stock_rows = stock_results

        else:

            stock_rows = []

        for stock in stock_rows:

            if not isinstance(
                stock,
                dict
            ):
                continue

            ticker = str(
                stock.get(
                    "Ticker",
                    ""
                )
            ).upper().strip()

            if not ticker:
                continue

            stock_lookup[ticker] = {

                "Score":
                    stock.get("Score"),

                "Signal":
                    stock.get("Signal"),

                "Quality Score":
                    stock.get(
                        "Quality Score"
                    ),

                "Investment Score":
                    stock.get(
                        "Investment Score"
                    ),

                "Sector":
                    stock.get(
                        "Sector",
                        "Unknown"
                    ),

                "Industry":
                    stock.get(
                        "Industry",
                        "Unknown"
                    )
            }

    # ========================================================
    # VALIDATE PORTFOLIO
    # ========================================================

    required = [
        "Ticker",
        "Name",
        "Shares",
        "Current Value"
    ]

    missing = [
        c
        for c in required
        if c not in holdings.columns
    ]

    if missing:

        raise ValueError(
            f"Missing portfolio columns: {missing}"
        )

    holdings = holdings.copy()

    holdings["Shares"] = pd.to_numeric(
        holdings["Shares"],
        errors="coerce"
    )

    holdings["Current Value"] = pd.to_numeric(
        holdings["Current Value"],
        errors="coerce"
    )

    holdings["Ticker"] = (
        holdings["Ticker"]
        .astype(str)
        .str.upper()
        .str.strip()
    )

    holdings = holdings.dropna(
        subset=[
            "Ticker",
            "Current Value"
        ]
    )

    holdings = holdings[
        holdings["Ticker"] != "TOTAL"
    ]

    # ========================================================
    # TOTAL PORTFOLIO VALUE
    # ========================================================

    total_value = float(
        holdings[
            "Current Value"
        ].sum()
    )

    if total_value <= 0:

        raise ValueError(
            "Portfolio value invalid"
        )

    # ========================================================
    # IDENTIFY STOCKS AND ETFS
    # ========================================================

    stock_tickers = []
    etf_tickers = []

    for _, row in holdings.iterrows():

        ticker = row["Ticker"]

        security_type = classify_security(
            ticker,
            row["Name"]
        )

        if security_type == "STOCK":

            stock_tickers.append(
                ticker
            )

        elif security_type == "ETF":

            etf_tickers.append(
                ticker
            )

    # ========================================================
    # DOWNLOAD STOCK PRICES
    # ========================================================

    stock_price_data = download_price_data(
        stock_tickers,
        "stocks"
    )

    # ========================================================
    # DOWNLOAD ETF PRICES
    # ========================================================

    etf_price_data = download_price_data(
        etf_tickers,
        "ETFs"
    )

    # ========================================================
    # ANALYSE EACH HOLDING
    # ========================================================

    for _, row in holdings.iterrows():

        ticker = row["Ticker"]
        name = row["Name"]
        shares = row["Shares"]

        current_value = float(
            row["Current Value"]
        )

        security_type = classify_security(
            ticker,
            name
        )

        base = {

            "Ticker":
                ticker,

            "Name":
                name,

            "Type":
                security_type,

            "Shares":
                shares,

            "Current Value":
                current_value,

            "Allocation %":
                round(
                    current_value /
                    total_value *
                    100,
                    2
                )
        }

        # ====================================================
        # CASH
        # ====================================================

        if security_type == "CASH":

            results.append({

                **base,

                "Sector":
                    "Cash",

                "Industry":
                    "Cash",

                "Trend":
                    "Cash",

                "Current Price":
                    None,

                "MA50":
                    None,

                "MA200":
                    None,

                "Momentum Score":
                    None,

                "Momentum Signal":
                    "N/A",

                "Quality Score":
                    None,

                "Investment Score":
                    None,

                "ETF Score":
                    None,

                "ETF Signal":
                    "N/A",

                "ETF Reasons":
                    None,

                "ETF Risks":
                    None
            })

            continue

        # ====================================================
        # ETF
        # ====================================================

        if security_type == "ETF":

            print(
                f"Analysing ETF holding: {ticker}"
            )

            close = etf_price_data.get(
                ticker
            )

            if close is None or close.empty:

                print(
                    f"{ticker}: ETF price data unavailable"
                )

                results.append({

                    **base,

                    "Sector":
                        "ETF",

                    "Industry":
                        "Fund",

                    "Trend":
                        "Unknown",

                    "Current Price":
                        None,

                    "MA50":
                        None,

                    "MA200":
                        None,

                    "Momentum Score":
                        None,

                    "Momentum Signal":
                        "N/A",

                    "Quality Score":
                        None,

                    "Investment Score":
                        None,

                    "ETF Score":
                        0,

                    "ETF Signal":
                        "UNKNOWN",

                    "ETF Reasons":
                        "ETF price history unavailable",

                    "ETF Risks":
                        "Insufficient market data"
                })

                continue

            etf_result = analyse_etf(
                ticker=ticker,
                price_data=close
            )

            results.append({

                **base,

                "Sector":
                    "ETF",

                "Industry":
                    "Fund",

                "Trend":
                    (
                        "Positive"
                        if (
                            etf_result.get(
                                "Current Price"
                            ) is not None
                            and
                            etf_result.get(
                                "MA200"
                            ) is not None
                            and
                            etf_result[
                                "Current Price"
                            ] >
                            etf_result[
                                "MA200"
                            ]
                        )
                        else "Negative"
                    ),

                "Current Price":
                    etf_result.get(
                        "Current Price"
                    ),

                "MA50":
                    etf_result.get(
                        "MA50"
                    ),

                "MA200":
                    etf_result.get(
                        "MA200"
                    ),

                "Momentum Score":
                    None,

                "Momentum Signal":
                    "N/A",

                "Quality Score":
                    None,

                "Investment Score":
                    None,

                "ETF Score":
                    etf_result.get(
                        "ETF Score"
                    ),

                "ETF Signal":
                    etf_result.get(
                        "ETF Signal"
                    ),

                "6M Return %":
                    etf_result.get(
                        "6M Return %"
                    ),

                "12M Return %":
                    etf_result.get(
                        "12M Return %"
                    ),

                "ETF Reasons":
                    etf_result.get(
                        "ETF Reasons"
                    ),

                "ETF Risks":
                    etf_result.get(
                        "ETF Risks"
                    )
            })

            continue

        # ====================================================
        # STOCK
        # ====================================================

        metadata = stock_lookup.get(
            ticker,
            {}
        )

        try:

            print(
                f"Analysing portfolio holding: {ticker}"
            )

            close = stock_price_data.get(
                ticker
            )

            if close is None or close.empty:

                results.append({

                    **base,

                    "Sector":
                        metadata.get(
                            "Sector",
                            "Unknown"
                        ),

                    "Industry":
                        metadata.get(
                            "Industry",
                            "Unknown"
                        ),

                    "Trend":
                        "Unknown",

                    "Current Price":
                        None,

                    "MA50":
                        None,

                    "MA200":
                        None,

                    "Momentum Score":
                        metadata.get(
                            "Score"
                        ),

                    "Momentum Signal":
                        metadata.get(
                            "Signal"
                        ),

                    "Quality Score":
                        metadata.get(
                            "Quality Score"
                        ),

                    "Investment Score":
                        metadata.get(
                            "Investment Score"
                        ),

                    "ETF Score":
                        None,

                    "ETF Signal":
                        "N/A",

                    "ETF Reasons":
                        None,

                    "ETF Risks":
                        None
                })

                continue

            close = (
                pd.to_numeric(
                    close,
                    errors="coerce"
                )
                .dropna()
            )

            if len(close) < 50:

                results.append({

                    **base,

                    "Sector":
                        metadata.get(
                            "Sector",
                            "Unknown"
                        ),

                    "Industry":
                        metadata.get(
                            "Industry",
                            "Unknown"
                        ),

                    "Trend":
                        "Unknown",

                    "Current Price":
                        float(close.iloc[-1])
                        if not close.empty
                        else None,

                    "MA50":
                        None,

                    "MA200":
                        None,

                    "Momentum Score":
                        metadata.get(
                            "Score"
                        ),

                    "Momentum Signal":
                        metadata.get(
                            "Signal"
                        ),

                    "Quality Score":
                        metadata.get(
                            "Quality Score"
                        ),

                    "Investment Score":
                        metadata.get(
                            "Investment Score"
                        ),

                    "ETF Score":
                        None,

                    "ETF Signal":
                        "N/A",

                    "ETF Reasons":
                        None,

                    "ETF Risks":
                        None
                })

                continue

            current_price = float(
                close.iloc[-1]
            )

            ma50 = float(
                close.tail(50).mean()
            )

            ma200 = float(
                close.tail(200).mean()
            )

            if (
                current_price > ma50
                and
                current_price > ma200
            ):

                trend = "Positive"

            elif current_price < ma200:

                trend = "Negative"

            else:

                trend = "Neutral"

            results.append({

                **base,

                "Current Price":
                    current_price,

                "MA50":
                    ma50,

                "MA200":
                    ma200,

                "Trend":
                    trend,

                "Sector":
                    metadata.get(
                        "Sector",
                        "Unknown"
                    ),

                "Industry":
                    metadata.get(
                        "Industry",
                        "Unknown"
                    ),

                "Momentum Score":
                    metadata.get(
                        "Score"
                    ),

                "Momentum Signal":
                    metadata.get(
                        "Signal"
                    ),

                "Quality Score":
                    metadata.get(
                        "Quality Score"
                    ),

                "Investment Score":
                    metadata.get(
                        "Investment Score"
                    ),

                "ETF Score":
                    None,

                "ETF Signal":
                    "N/A",

                "ETF Reasons":
                    None,

                "ETF Risks":
                    None
            })

        except Exception as e:

            print(
                f"Portfolio analysis failed "
                f"{ticker}: {e}"
            )

            results.append({

                **base,

                "Sector":
                    metadata.get(
                        "Sector",
                        "Unknown"
                    ),

                "Industry":
                    metadata.get(
                        "Industry",
                        "Unknown"
                    ),

                "Trend":
                    "Unknown",

                "Current Price":
                    None,

                "MA50":
                    None,

                "MA200":
                    None,

                "Momentum Score":
                    metadata.get(
                        "Score"
                    ),

                "Momentum Signal":
                    metadata.get(
                        "Signal"
                    ),

                "Quality Score":
                    metadata.get(
                        "Quality Score"
                    ),

                "Investment Score":
                    metadata.get(
                        "Investment Score"
                    ),

                "ETF Score":
                    None,

                "ETF Signal":
                    "N/A",

                "ETF Reasons":
                    None,

                "ETF Risks":
                    None
            })

    return pd.DataFrame(
        results
    )