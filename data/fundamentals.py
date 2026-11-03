import json
import os
import math
from datetime import datetime, timezone, timedelta
import yfinance as yf


CACHE_DIR = "data/cache/fundamentals"

FUNDAMENTALS_CACHE_VERSION = 5


def get_fundamentals(ticker):

    os.makedirs(
        CACHE_DIR,
        exist_ok=True
    )

    cache_file = os.path.join(
        CACHE_DIR,
        f"{ticker}.json"
    )

    # ---------------------------------------------------------
    # Fundamentals cache
    #
    # Version 2 adds valuation telemetry.
    # Existing version 1 caches are refreshed once so that
    # valuation data is populated.
    # ---------------------------------------------------------

    if os.path.exists(cache_file):

        try:

            with open(cache_file) as f:

                cached_fundamentals = json.load(f)

            if (
                cached_fundamentals.get(
                    "_fundamentals_cache_version"
                )
                == FUNDAMENTALS_CACHE_VERSION
            ):

                return cached_fundamentals

        except (
            OSError,
            json.JSONDecodeError,
            TypeError,
            AttributeError
        ):

            pass

    print(
        f"Getting fundamentals {ticker}"
    )

    stock = yf.Ticker(
        ticker
    )

    info = stock.info

    fundamentals = {

        "_fundamentals_cache_version":
            FUNDAMENTALS_CACHE_VERSION,

        "Name":
            info.get(
                "longName",
                info.get(
                    "shortName",
                    ticker
                )
            ),

        "Revenue Growth":
            info.get(
                "revenueGrowth"
            ),

        "Earnings Growth":
            info.get(
                "earningsGrowth"
            ),

        "Profit Margin":
            info.get(
                "profitMargins"
            ),

        "Return on Equity":
            info.get(
                "returnOnEquity"
            ),

        "Debt to Equity":
            info.get(
                "debtToEquity"
            ),
        "Sector":
            info.get(
                "sector",
                "Unknown"
            ),

        "Industry":
            info.get(
                "industry",
                "Unknown"
            ),

                "Country":
            info.get(
                "country"
            ),

        "Exchange":
            info.get(
                "exchange"
            ),

        "Quote Type":
            info.get(
                "quoteType"
            ),

        # -----------------------------------------------------
        # Valuation telemetry
        #
        # These values are observational only at this stage.
        # They do NOT affect Quality, Growth, Investment Score
        # or portfolio decisions.
        # -----------------------------------------------------

        "PE Ratio":
            info.get(
                "trailingPE"
            ),

        "Forward PE":
            info.get(
                "forwardPE"
            ),

        "PEG Ratio":
            info.get(
                "pegRatio"
            ),

        "Price to Sales":
            info.get(
                "priceToSalesTrailing12Months"
            ),

        "EV to EBITDA":
            info.get(
                "enterpriseToEbitda"
            ),

        "Free Cash Flow":
            info.get(
                "freeCashflow"
            )
    }

    with open(
        cache_file,
        "w"
    ) as f:

        json.dump(
            fundamentals,
            f
        )

    return fundamentals


# ============================================================
# SHADOW FINANCIAL RESILIENCE — ANNUAL STATEMENT DATA
# ============================================================

FINANCIAL_STATEMENTS_CACHE_DIR = (
    "data/cache/financial_statements"
)

FINANCIAL_STATEMENTS_CACHE_VERSION = 1
FINANCIAL_STATEMENTS_CACHE_MAX_AGE_DAYS = 7


def _statement_frame_to_records(statement):

    if statement is None or getattr(statement, "empty", True):
        return []

    records = []

    for period in statement.columns:

        try:
            period_end = period.strftime("%Y-%m-%d")
        except (AttributeError, ValueError):
            period_end = str(period)[:10]

        record = {
            "period_end": period_end
        }

        try:
            values = statement[period]
        except (KeyError, TypeError, ValueError):
            continue

        for line_item, value in values.items():

            try:
                numeric_value = float(value)
            except (TypeError, ValueError, OverflowError):
                continue

            if math.isfinite(numeric_value):
                record[str(line_item)] = numeric_value

        if len(record) > 1:
            records.append(record)

    return records


def get_financial_statements(ticker):

    ticker = str(ticker or "").strip().upper()

    if not ticker:
        return {
            "Ticker": None,
            "Status": "UNAVAILABLE",
            "Source": "Yahoo Finance via yfinance",
            "Annual": {},
            "Errors": ["Ticker was empty."],
        }

    os.makedirs(
        FINANCIAL_STATEMENTS_CACHE_DIR,
        exist_ok=True
    )

    safe_ticker = ticker.replace("/", "_")

    cache_file = os.path.join(
        FINANCIAL_STATEMENTS_CACHE_DIR,
        f"{safe_ticker}.json"
    )

    # --------------------------------------------------------
    # Reuse a recent cache entry.
    # --------------------------------------------------------

    if os.path.exists(cache_file):

        try:
            with open(cache_file) as f:
                cached = json.load(f)

            retrieved_at = datetime.fromisoformat(
                cached.get("Retrieved At", "")
            )

            if retrieved_at.tzinfo is None:
                retrieved_at = retrieved_at.replace(
                    tzinfo=timezone.utc
                )

            age = (
                datetime.now(timezone.utc) - retrieved_at
            )

            if (
                cached.get(
                    "_financial_statements_cache_version"
                ) == FINANCIAL_STATEMENTS_CACHE_VERSION
                and timedelta(0) <= age <= timedelta(
                    days=FINANCIAL_STATEMENTS_CACHE_MAX_AGE_DAYS
                )
            ):
                return cached

        except (
            OSError,
            json.JSONDecodeError,
            TypeError,
            ValueError,
            AttributeError,
        ):
            pass

    # --------------------------------------------------------
    # Retrieve annual statements.
    # --------------------------------------------------------

    stock = yf.Ticker(ticker)

    statement_sources = {
        "balance_sheet": "balance_sheet",
        "income_statement": "income_stmt",
        "cash_flow": "cashflow",
    }

    annual = {}
    errors = []

    for output_key, yfinance_attribute in statement_sources.items():

        try:
            statement = getattr(
                stock,
                yfinance_attribute
            )

            annual[output_key] = (
                _statement_frame_to_records(statement)
            )

        except Exception as exc:

            annual[output_key] = []

            errors.append(
                f"{output_key}: {type(exc).__name__}: {exc}"
            )

    available_count = sum(
        bool(annual.get(key))
        for key in statement_sources
    )

    status = (
        "AVAILABLE"
        if available_count == 3
        else "PARTIAL"
        if available_count > 0
        else "UNAVAILABLE"
    )

    result = {
        "_financial_statements_cache_version":
            FINANCIAL_STATEMENTS_CACHE_VERSION,

        "Ticker":
            ticker,

        "Source":
            "Yahoo Finance via yfinance",

        "Retrieved At":
            datetime.now(timezone.utc).isoformat(),

        "Status":
            status,

        "Annual":
            annual,

        "Errors":
            errors,
    }

    # Do not persist a completely empty response.
    if available_count > 0:

        with open(cache_file, "w") as f:
            json.dump(result, f)

    return result
