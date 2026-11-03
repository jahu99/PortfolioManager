"""
Portfolio Reallocation Engine

Purpose
-------

Perform whole-portfolio capital reallocation downstream from the
Final Portfolio Decision layer.

The Final Portfolio Decision answers:

    "What is the appropriate decision for this asset individually?"

The Portfolio Reallocation Engine answers:

    "Given the entire portfolio, where should capital be allocated
    to maximise portfolio growth subject to diversification and
    governance constraints?"

Core principles
---------------

- Review the entire portfolio, not only explicit REDUCE / SELL decisions.

- HOLD does not mean permanently untouchable.

- A HOLD position may become a funding candidate when a materially
  stronger opportunity exists elsewhere.

- Explicit SELL decisions remain strong funding candidates.

- Explicit REDUCE decisions remain preferred funding candidates.

- Strong BUY NEW and BUY MORE opportunities compete for capital.

- Existing holdings compete with new opportunities.

- Capital should move only when the destination represents a
  meaningful improvement over the source.

- Avoid unnecessary turnover.

- Preserve diversification.

- Respect maximum position sizing.

- CASH is not an investment candidate.

- The engine produces recommendations and a proposed reallocation plan.
  It does not execute trades.
"""

import os

import pandas as pd


from config.investment_config import (
    MAX_POSITION_PERCENT
)

from analysis.structural_risk import (
        assess_structural_risk,
)

from analysis.portfolio_reallocation_audit import (
    build_reallocation_audit,
)


# ============================================================
# CONFIGURATION
# ============================================================

HOLDINGS_FILE = "portfolio/holdings_raw.csv"


# Minimum portfolio movement required before recommending a trade.
MIN_REALLOCATION_VALUE = 5.00


# HOLD positions below this score become potential funding candidates
# if stronger opportunities exist.
WEAK_HOLD_SCORE = 60.0


# HOLD positions below this score are stronger funding candidates.
VERY_WEAK_HOLD_SCORE = 45.0


# Strong opportunities eligible to receive capital.
MIN_DESTINATION_SCORE = 75.0


# Maximum percentage of a portfolio position that can be reduced
# by this engine in a single run unless the upstream final decision
# explicitly says SELL.
MAX_OPPORTUNITY_REDUCTION_PERCENT = 50.0


# Cash added to the portfolio at each assessment.
# This mirrors the discretionary cash contribution used by the
# original capital allocation process.
ASSESSMENT_CASH_CONTRIBUTION = 15.0


# Minimum score advantage required before a HOLD position may be
# challenged as a source of capital for a materially stronger
# governed destination.
MIN_REALLOCATION_SCORE_ADVANTAGE = 10.0

# ============================================================
# REALLOCATION GOVERNANCE
# ============================================================

# Normal minimum transaction size.
MIN_REALLOCATION_VALUE = 5.00

# Cash added by the investor at each assessment.
ASSESSMENT_CASH_CONTRIBUTION = 15.00


# ------------------------------------------------------------
# HOLD CHALLENGE GOVERNANCE
# ------------------------------------------------------------

# HOLD positions are not automatically funding sources.
#
# A HOLD may only be challenged when it is genuinely weak and
# there is a materially stronger governed destination.

HOLD_CHALLENGE_MAX_SCORE = 55.0

# The destination must be materially stronger than the HOLD
# position before capital can be reallocated.

HOLD_CHALLENGE_MIN_SCORE_IMPROVEMENT = 15.0

# Maximum proportion released from a challenged HOLD.

HOLD_CHALLENGE_RELEASE_PCT = 25.0


# ------------------------------------------------------------
# CORE ASSET PROTECTION
# ------------------------------------------------------------

# Broad/core ETFs should not automatically be sold merely
# because an individual stock has a higher Investment Score.

PROTECT_ETF_HOLDINGS = True


# ------------------------------------------------------------
# DESTINATION CONCENTRATION GOVERNANCE
# ------------------------------------------------------------

# Prevent recalibration from pouring all available capital into
# the first-ranked destination.

MAX_DESTINATION_SHARE_OF_REALLOCATION = 0.35


# ============================================================
# DESTINATION ALLOCATION
# ============================================================

MAX_REALLOCATION_DESTINATIONS = 5

MIN_REALLOCATION_TRADE_VALUE = 2.00

# ============================================================
# HOLD CHALLENGE GOVERNANCE
# ============================================================

# HOLD is the default portfolio decision.
# Automatic capital recycling from HOLD positions is deliberately
# restrictive and must never behave like implicit SELL governance.

HOLD_CHALLENGE_MAX_SCORE = 50.0

# A destination must be materially superior before a weak HOLD can
# be challenged for capital recycling.
MIN_HOLD_CHALLENGE_SCORE_ADVANTAGE = 25.0

# Maximum automatic recycling from a HOLD position.
MAX_WEAK_HOLD_REDUCTION_PERCENT = 10.0
MAX_VERY_WEAK_HOLD_REDUCTION_PERCENT = 15.0

# Avoid creating trivial portfolio churn.
MIN_HOLD_CHALLENGE_RELEASE_VALUE = 3.00

MIN_MEANINGFUL_DEPLOYMENT_VALUE = 7.5

# ============================================================
# HELPERS
# ============================================================

def safe_float(value, default=0.0):

    try:

        if value is None:
            return default

        if isinstance(value, (list, tuple)):
            return default

        if hasattr(value, "iloc"):

            if len(value) == 0:
                return default

            value = value.iloc[0]

        if pd.isna(value):
            return default

        return float(value)

    except Exception:

        return default


def clean_ticker(value):

    if value is None:
        return ""

    return str(value).strip().upper()


def normalise_action(value):

    if value is None:
        return "HOLD"

    return str(value).strip().upper()


def get_score(row):

    """
    Return the allocation-relevant score.

    Final Portfolio Decisions currently expose Investment Score
    for reporting compatibility.

    For ETFs this may represent the ETF allocation score.
    """

    return safe_float(

        row.get(

            "Investment Score",

            row.get(

                "investment_score",

                row.get(

                    "ETF Score",

                    row.get(

                        "etf_score",

                        0

                    )

                )

            )

        )

    )


def load_actual_holdings():

    """
    Load actual portfolio holdings.

    Quantity > 0 means owned.
    """

    if not os.path.exists(HOLDINGS_FILE):

        print(
            f"WARNING: {HOLDINGS_FILE} not found."
        )

        return pd.DataFrame()

    try:

        holdings = pd.read_csv(
            HOLDINGS_FILE
        )

    except Exception as e:

        print(
            f"Unable to read holdings file: {e}"
        )

        return pd.DataFrame()

    required_columns = [

        "Ticker",

        "Quantity",

        "Market Value"

    ]

    missing = [

        column

        for column in required_columns

        if column not in holdings.columns

    ]

    if missing:

        print(
            f"Holdings file missing columns: {missing}"
        )

        return pd.DataFrame()

    holdings = holdings.copy()

    holdings["Ticker"] = (

        holdings["Ticker"]

        .astype(str)

        .str.strip()

        .str.upper()

    )

    holdings["Quantity"] = pd.to_numeric(

        holdings["Quantity"],

        errors="coerce"

    ).fillna(0)

    holdings["Market Value"] = pd.to_numeric(

        holdings["Market Value"],

        errors="coerce"

    ).fillna(0)

    holdings = holdings.loc[
        holdings["Ticker"] != "CASH"
    ]

    holdings = holdings.loc[
        holdings["Quantity"] > 0
    ]

    return holdings


def load_actual_cash_balance():
    """
    Read existing portfolio cash from holdings_raw.csv.

    Cash is valued by Market Value, not Quantity. This is deliberately
    separate from load_actual_holdings(), which excludes CASH from
    security-position calculations.
    """
    if not os.path.exists(HOLDINGS_FILE):
        return 0.0

    try:
        holdings = pd.read_csv(HOLDINGS_FILE)
    except Exception as exc:
        print(f"WARNING: Unable to read cash balance: {exc}")
        return 0.0

    required = {"Ticker", "Market Value"}
    if not required.issubset(holdings.columns):
        print(
            "WARNING: Cannot read existing cash; holdings file "
            "requires Ticker and Market Value columns."
        )
        return 0.0

    cash_rows = holdings.loc[
        holdings["Ticker"].astype(str).str.strip().str.upper() == "CASH"
    ]

    cash_values = pd.to_numeric(
        cash_rows["Market Value"],
        errors="coerce"
    ).fillna(0.0)

    return round(max(0.0, float(cash_values.sum())), 2)


# ============================================================
# DECISION NORMALISATION
# ============================================================

def normalise_final_decisions(final_portfolio_decisions):

    """
    Convert final decisions into a DataFrame.
    """

    if final_portfolio_decisions is None:

        return pd.DataFrame()

    if isinstance(
        final_portfolio_decisions,
        pd.DataFrame
    ):

        decisions = (
            final_portfolio_decisions.copy()
        )

    elif isinstance(
        final_portfolio_decisions,
        list
    ):

        decisions = pd.DataFrame(
            final_portfolio_decisions
        )

    else:

        return pd.DataFrame()

    if decisions.empty:

        return decisions

    if "Ticker" not in decisions.columns:

        return pd.DataFrame()

    decisions["Ticker"] = (

        decisions["Ticker"]

        .astype(str)

        .str.strip()

        .str.upper()

    )

    if "Final Decision" not in decisions.columns:

        if "Action" in decisions.columns:

            decisions["Final Decision"] = (
                decisions["Action"]
            )

        elif "Proposed Action" in decisions.columns:

            decisions["Final Decision"] = (
                decisions["Proposed Action"]
            )

        else:

            decisions["Final Decision"] = "HOLD"

    decisions["Final Decision"] = (

        decisions["Final Decision"]

        .fillna("HOLD")

        .astype(str)

        .str.strip()

        .str.upper()

    )

    return decisions


# ============================================================
# FUNDING PRIORITY
# ============================================================

def get_funding_priority(
    final_decision,
    score,
    market_value
):
    """
    Calculate how attractive an existing position is as a
    source of capital.

    Higher values mean stronger funding candidates.

    Priority hierarchy is structurally enforced:

    1. SELL
    2. REDUCE
    3. Weak HOLD

    Investment quality and position size rank candidates
    within their governance category but cannot cause a lower
    governance category to outrank a higher one.
    """

    final_decision = normalise_action(
        final_decision
    )

    score = safe_float(
        score
    )

    market_value = safe_float(
        market_value
    )

    # ====================================================
    # GOVERNANCE PRIORITY BANDS
    #
    # These bands deliberately do not overlap.
    # ====================================================

    if final_decision == "SELL":

        base_priority = 300.0

    elif final_decision.startswith(
        "REDUCE"
    ):

        base_priority = 200.0

    else:

        base_priority = 100.0

    # ====================================================
    # RELATIVE INVESTMENT QUALITY
    #
    # Used only to rank positions within their governance
    # category.
    # ====================================================

    quality_priority = 0.0

    if score < VERY_WEAK_HOLD_SCORE:

        quality_priority = 50.0

    elif score < WEAK_HOLD_SCORE:

        quality_priority = 30.0

    elif score < 75.0:

        quality_priority = 15.0

    elif score < 85.0:

        quality_priority = 5.0

    # ====================================================
    # POSITION SIZE
    #
    # Used only as a secondary ranking factor.
    # ====================================================

    size_priority = min(
        market_value / 10.0,
        20.0
    )

    return round(
        base_priority
        + quality_priority
        + size_priority,
        2
    )

def get_position_capacity(
    current_value,
    total_portfolio_value
):

    """
    Calculate how much additional capital can be allocated
    to a position before reaching MAX_POSITION_PERCENT.
    """

    current_value = safe_float(
        current_value
    )

    total_portfolio_value = safe_float(
        total_portfolio_value
    )

    if total_portfolio_value <= 0:

        return 0.0

    maximum_position_value = (

        total_portfolio_value

        *

        safe_float(
            MAX_POSITION_PERCENT
        )

        /

        100

    )

    capacity = (

        maximum_position_value

        -

        current_value

    )

    return round(

        max(
            0.0,
            capacity
        ),

        2

    )


def select_deployment_destinations(
    eligible_destinations,
    total_available_capital,
    meaningful_deployment_value=MIN_MEANINGFUL_DEPLOYMENT_VALUE
):
    """
    Select the number of destinations that can receive
    meaningful capital deployment.

    Capital is concentrated into the highest-priority governed
    destinations when available capital is limited.
    """

    if not eligible_destinations:
        return []

    ranked_destinations = sorted(
        eligible_destinations,
        key=lambda destination: (
            -safe_float(
                destination.get(
                    "Allocation Weight",
                    0
                )
            ),
            -safe_float(
                destination.get(
                    "Investment Score",
                    0
                )
            ),
            clean_ticker(
                destination.get(
                    "Ticker",
                    ""
                )
            )
        )
    )

    meaningful_deployment_value = max(
        1.0,
        safe_float(
            meaningful_deployment_value
        )
    )

    destination_count = max(
        1,
        int(
            total_available_capital
            // meaningful_deployment_value
        )
    )

    destination_count = min(
        destination_count,
        MAX_REALLOCATION_DESTINATIONS,
        len(ranked_destinations)
    )

    return ranked_destinations[
        :destination_count
    ]


# ============================================================
# DESTINATION PRIORITY
# ============================================================

def get_destination_priority(
    final_decision,
    score,
    owned
):
    """
    Calculate attractiveness as a destination for capital.

    Portfolio recalibration does not make investment decisions.

    Only authoritative Final Portfolio Decisions of BUY MORE
    and BUY NEW are eligible destinations.

    HOLD positions are protected and remain unchanged.
    SELL and REDUCE positions are funding sources.
    """

    final_decision = normalise_action(
        final_decision
    )

    score = safe_float(
        score
    )

    if final_decision in {
        "BUY MORE",
        "BUY NEW"
    }:
        return score

    return 0.0

# ============================================================
# HOLD CHALLENGE / FUNDING HELPERS
# ============================================================

def is_hold_funding_eligible(position):
    """
    Determine whether a HOLD position is structurally eligible
    for a portfolio-level capital recycling challenge.

    HOLD remains the default portfolio decision.

    ETFs are protected automatically because they may represent
    core, diversification, or strategic portfolio exposure.

    Individual stocks may proceed to the stricter evidence test,
    but eligibility alone does not authorise capital recycling.
    """

    final_decision = normalise_action(
        position.get(
            "Final Decision",
            "HOLD"
        )
    )

    asset_type = str(
        position.get(
            "Asset Type",
            ""
        )
    ).strip().upper()

    # This helper applies only to HOLD positions.
    if final_decision != "HOLD":
        return False

    # ETFs are protected from automatic opportunity-based
    # capital recycling.
    if asset_type == "ETF":
        return False

    # Unknown asset types are protected by default.
    if asset_type != "STOCK":
        return False

    return True


def _normalise_economic_sector(value):
    """Accept economic-sector labels, not instrument-type labels."""
    sector = str(value or "").strip()
    if not sector:
        return ""

    invalid_labels = {
        "ETF", "STOCK", "EQUITY", "SHARE",
        "CASH", "BOND", "FUND", "MUTUAL FUND", "INDEX FUND",
    }
    return "" if sector.upper() in invalid_labels else sector


def _build_price_deterioration_assessment(ticker):
    """Return advisory-only price-risk evidence; never alter trade decisions."""
    result = {
        "status": "UNASSESSED",
        "source": "cache/prices/{TICKER}_1y.parquet (cache-only)",
        "observation_date": None,
        "freshness": "UNKNOWN",
        "return_20_session_percent": None,
        "return_60_session_percent": None,
        "drawdown_from_52w_intraday_high_percent": None,
        "severity": "UNKNOWN",
        "reasons": [],
    }

    try:
        from data import market_data

        # SHADOW risk assessment must never trigger live market-data downloads.
        cache_file = market_data._cache_file(ticker, "1y")

        if not os.path.exists(cache_file):
            result["reasons"].append(
                "No cached historical price observations; "
                "network refresh intentionally skipped."
            )
            return result

        data = pd.read_parquet(cache_file)

        if data is None or data.empty:
            result["reasons"].append(
                "No historical price observations returned."
            )
            return result

        data = data.copy()
        data.index = pd.to_datetime(data.index, errors="coerce")
        data = data.loc[~data.index.isna()].sort_index()
        data = data.loc[~data.index.duplicated(keep="last")]

        if data.empty:
            result["reasons"].append(
                "Historical price dates are invalid."
            )
            return result

        latest_date = pd.Timestamp(data.index[-1]).normalize()
        result["observation_date"] = latest_date.strftime("%Y-%m-%d")

        latest_session_fn = getattr(
            market_data, "_latest_completed_us_trading_date", None
        )

        if callable(latest_session_fn):
            expected_date = pd.Timestamp(
                latest_session_fn()
            ).normalize()
            fresh = latest_date >= expected_date
        else:
            fresh = (
                pd.Timestamp.now().normalize() - latest_date
            ).days <= 5

        result["freshness"] = "CURRENT" if fresh else "STALE"

        if not fresh:
            result["reasons"].append(
                "Latest observation is older than the expected completed US "
                "trading session; price risk remains unassessed."
            )
            return result

        if "Close" not in data.columns:
            result["reasons"].append(
                "Historical data has no Close column."
            )
            return result

        close = pd.to_numeric(
            data["Close"], errors="coerce"
        ).dropna()

        if close.empty or float(close.iloc[-1]) <= 0:
            result["reasons"].append(
                "No valid latest closing price is available."
            )
            return result

        latest_close = float(close.iloc[-1])

        if len(close) >= 21 and float(close.iloc[-21]) > 0:
            result["return_20_session_percent"] = round(
                (latest_close / float(close.iloc[-21]) - 1) * 100,
                2,
            )
        else:
            result["reasons"].append(
                "Insufficient data for a 20-session return."
            )

        if len(close) >= 61 and float(close.iloc[-61]) > 0:
            result["return_60_session_percent"] = round(
                (latest_close / float(close.iloc[-61]) - 1) * 100,
                2,
            )
        else:
            result["reasons"].append(
                "Insufficient data for a 60-session return."
            )

        if "High" in data.columns:
            high = pd.to_numeric(
                data["High"], errors="coerce"
            ).dropna().tail(252)

            if not high.empty and float(high.max()) > 0:
                result[
                    "drawdown_from_52w_intraday_high_percent"
                ] = round(
                    (latest_close / float(high.max()) - 1) * 100,
                    2,
                )
            else:
                result["reasons"].append(
                    "No valid daily highs available."
                )
        else:
            result["reasons"].append(
                "Historical data has no High column."
            )

        r20 = result["return_20_session_percent"]
        r60 = result["return_60_session_percent"]
        dd = result["drawdown_from_52w_intraday_high_percent"]

        # Incomplete history must never be labelled assessed or low risk.
        if r20 is None or r60 is None or dd is None:
            result["severity"] = "UNKNOWN"
            result["reasons"].append(
                "Incomplete price history; full price-risk assessment unavailable."
            )
            return result

        if r60 <= -25 or dd <= -40:
            result["severity"] = "HIGH"
            result["reasons"].append(
                "Severe price deterioration review threshold breached."
            )
        elif r20 <= -10 or r60 <= -15 or dd <= -25:
            result["severity"] = "REVIEW"
            result["reasons"].append(
                "Price deterioration review threshold breached."
            )
        else:
            result["severity"] = "NO_THRESHOLD_BREACH"
            result["reasons"].append(
                "No configured price review threshold breached; this does not "
                "establish that the stock is low risk."
            )

        result["status"] = "ASSESSED"
        return result

    except Exception as exc:
        result["reasons"].append(
            "Price-risk assessment failed: " + type(exc).__name__ + "."
        )
        return result

def _build_macro_regime_assessment():
    """Assess cache-only macro-risk proxies for SHADOW review.

    The three original indicators determine the composite regime.
    Additional yield and yield-curve indicators are diagnostic only.
    Missing or stale inputs remain UNASSESSED; this function never
    refreshes market data.
    """
    from data import market_data

    result = {
        "status": "UNASSESSED",
        "regime": "UNASSESSED",
        "as_of": None,
        "indicators": [],
        "historical_pre_trade_status": "NOT_ASSESSED",
        "historical_pre_trade_reason": (
            "The current assessment has no purchase date or point-in-time macro "
            "snapshot. Current cached data cannot establish what was knowable "
            "before a historical purchase."
        ),
        "advisory_only": True,
    }

    today = pd.Timestamp.now().normalize()
    cache = {}

    def load_closes(ticker):
        if ticker in cache:
            return cache[ticker]

        path = market_data._cache_file(ticker, "1y")
        if not os.path.exists(path):
            cache[ticker] = (
                None,
                "No cached history; network refresh skipped.",
            )
            return cache[ticker]

        try:
            frame = pd.read_parquet(path)

            if frame is None or frame.empty or "Close" not in frame.columns:
                cache[ticker] = (
                    None,
                    "Cached history has no usable Close column.",
                )
                return cache[ticker]

            frame = frame.copy()
            frame.index = pd.to_datetime(frame.index, errors="coerce")
            frame = frame.loc[~frame.index.isna()].sort_index()
            frame = frame.loc[~frame.index.duplicated(keep="last")]

            price_column = (
                "Adj Close"
                if ticker not in {"^TNX", "^IRX", "^FVX", "CL=F"}
                and "Adj Close" in frame.columns
                else "Close"
            )

            closes = pd.to_numeric(
                frame[price_column],
                errors="coerce",
            ).dropna()

            if closes.empty:
                cache[ticker] = (
                    None,
                    "No valid cached closing observations.",
                )
                return cache[ticker]

            latest_date = pd.Timestamp(closes.index[-1])
            if latest_date.tzinfo is not None:
                latest_date = latest_date.tz_localize(None)

            observation_age_days = (
                today - latest_date.normalize()
            ).days

            if observation_age_days < 0:
                cache[ticker] = (
                    None,
                    f"Invalid future-dated observation: "
                    f"{latest_date:%Y-%m-%d}.",
                )
                return cache[ticker]

            if observation_age_days > 5:
                cache[ticker] = (
                    None,
                    f"Cached data stale; latest observation "
                    f"{latest_date:%Y-%m-%d}.",
                )
                return cache[ticker]

            cache[ticker] = (closes, None)
            return cache[ticker]

        except Exception as exc:
            cache[ticker] = (
                None,
                f"Cache read failed: {type(exc).__name__}.",
            )
            return cache[ticker]

    def base_indicator(name, proxy, ticker_list, metric):
        return {
            "Indicator": name,
            "Proxy": proxy,
            "Tickers": ticker_list,
            "Metric": metric,
            "Status": "UNASSESSED",
            "Observation Date": None,
            "Value": None,
            "Threshold Basis": "PROVISIONAL SHADOW REVIEW THRESHOLDS",
            "Evidence": "",
            "Advisory Only": True,
            "Regime Contribution": True,
            "Data Source": "Local cached market-price history",
            "Retrieval Mode": "CACHE_ONLY",
        }

    # ------------------------------------------------------------
    # COMPOSITE INDICATOR 1: US 10-YEAR TREASURY YIELD CHANGE
    # ------------------------------------------------------------

    row = base_indicator(
        "US 10-year Treasury yield change",
        "^TNX cached close; yield-change proxy, not a complete rate outlook",
        "^TNX",
        "20-session change (basis points)",
    )

    closes, error = load_closes("^TNX")

    if closes is None:
        row["Evidence"] = error

    elif len(closes) < 21 or float(closes.iloc[-21]) <= 0:
        row["Evidence"] = (
            f"Insufficient cached history: {len(closes)} observations; "
            "need 21."
        )

    else:
        latest = float(closes.iloc[-1])
        change_bps = (latest - float(closes.iloc[-21])) * 10.0

        row["Observation Date"] = pd.Timestamp(
            closes.index[-1]
        ).strftime("%Y-%m-%d")
        row["Value"] = round(change_bps, 1)

        if change_bps >= 60:
            row["Status"] = "HIGH RISK SIGNAL"
        elif change_bps >= 35:
            row["Status"] = "ELEVATED RISK SIGNAL"
        else:
            row["Status"] = "NO CONFIGURED THRESHOLD BREACH"

        row["Evidence"] = (
            f"20-session yield change {change_bps:+.1f} bps; provisional "
            "review threshold +35 bps and high-risk threshold +60 bps."
        )

    result["indicators"].append(row)

    # ------------------------------------------------------------
    # COMPOSITE INDICATOR 2: CRUDE OIL PRICE CHANGE
    # ------------------------------------------------------------

    row = base_indicator(
        "Crude oil price change",
        "CL=F cached close; energy-price/inflation-pressure proxy",
        "CL=F",
        "20-session return (%)",
    )

    closes, error = load_closes("CL=F")

    if closes is None:
        row["Evidence"] = error

    elif len(closes) < 21 or float(closes.iloc[-21]) <= 0:
        row["Evidence"] = (
            f"Insufficient cached history: {len(closes)} observations; "
            "need 21."
        )

    else:
        latest = float(closes.iloc[-1])
        change_pct = (
            latest / float(closes.iloc[-21]) - 1.0
        ) * 100.0

        row["Observation Date"] = pd.Timestamp(
            closes.index[-1]
        ).strftime("%Y-%m-%d")
        row["Value"] = round(change_pct, 2)

        if change_pct >= 20:
            row["Status"] = "HIGH RISK SIGNAL"
        elif change_pct >= 10:
            row["Status"] = "ELEVATED RISK SIGNAL"
        else:
            row["Status"] = "NO CONFIGURED THRESHOLD BREACH"

        row["Evidence"] = (
            f"20-session crude-oil return {change_pct:+.2f}%; provisional "
            "review threshold +10% and high-risk threshold +20%. An "
            "oil-price rise can affect sectors differently."
        )

    result["indicators"].append(row)

    # ------------------------------------------------------------
    # COMPOSITE INDICATOR 3: CREDIT-RISK APPETITE PROXY
    # HYG/LQD is not a direct credit-spread measurement.
    # ------------------------------------------------------------

    row = base_indicator(
        "Credit-risk appetite proxy",
        "HYG relative to LQD cached 20-session returns; not a measured credit spread",
        "HYG; LQD",
        "HYG return minus LQD return (percentage points)",
    )

    hyg, hyg_error = load_closes("HYG")
    lqd, lqd_error = load_closes("LQD")

    if hyg is None or lqd is None:
        row["Evidence"] = "; ".join(
            error for error in (hyg_error, lqd_error) if error
        )
    else:
        # Align both series on identical observation dates.
        hyg_series = hyg.copy()
        lqd_series = lqd.copy()

        hyg_index = pd.DatetimeIndex(
            pd.to_datetime(hyg_series.index, errors="coerce")
        )
        lqd_index = pd.DatetimeIndex(
            pd.to_datetime(lqd_series.index, errors="coerce")
        )

        if hyg_index.tz is not None:
            hyg_index = hyg_index.tz_localize(None)
        if lqd_index.tz is not None:
            lqd_index = lqd_index.tz_localize(None)

        hyg_series.index = hyg_index
        lqd_series.index = lqd_index

        hyg_series = hyg_series.loc[~hyg_series.index.isna()]
        lqd_series = lqd_series.loc[~lqd_series.index.isna()]

        # Recheck uniqueness after timezone normalisation.
        hyg_series = hyg_series.loc[
            ~hyg_series.index.duplicated(keep="last")
        ].sort_index()
        lqd_series = lqd_series.loc[
            ~lqd_series.index.duplicated(keep="last")
        ].sort_index()

        common = pd.concat(
            [
                hyg_series.rename("HYG"),
                lqd_series.rename("LQD"),
            ],
            axis=1,
            join="inner",
        ).dropna().sort_index()

        if len(common) < 21:
            row["Evidence"] = (
                "Insufficient common-date history for HYG and LQD; "
                "need at least 21 shared observations."
            )
        elif (
            float(common["HYG"].iloc[-21]) <= 0
            or float(common["LQD"].iloc[-21]) <= 0
            or float(common["HYG"].iloc[-1]) <= 0
            or float(common["LQD"].iloc[-1]) <= 0
        ):
            row["Evidence"] = (
                "Invalid starting or ending price in the aligned HYG/LQD "
                "history; relative performance not assessed."
            )
        else:
            hyg_return = (
                float(common["HYG"].iloc[-1])
                / float(common["HYG"].iloc[-21]) - 1.0
            ) * 100.0

            lqd_return = (
                float(common["LQD"].iloc[-1])
                / float(common["LQD"].iloc[-21]) - 1.0
            ) * 100.0

            relative = hyg_return - lqd_return
            observation_date = pd.Timestamp(common.index[-1])

            row["Observation Date"] = observation_date.strftime("%Y-%m-%d")
            row["Value"] = round(relative, 2)

            if relative <= -6:
                row["Status"] = "HIGH RISK SIGNAL"
            elif relative <= -3:
                row["Status"] = "ELEVATED RISK SIGNAL"
            else:
                row["Status"] = "NO CONFIGURED THRESHOLD BREACH"

            row["Evidence"] = (
                f"HYG 20-session return {hyg_return:+.2f}%; "
                f"LQD {lqd_return:+.2f}%; relative performance "
                f"{relative:+.2f} percentage points over common dates "
                f"({pd.Timestamp(common.index[-21]):%Y-%m-%d} to "
                f"{observation_date:%Y-%m-%d}). Provisional review "
                "threshold -3 pp and high-risk threshold -6 pp; this "
                "is not a direct credit-spread measurement."
            )

    result["indicators"].append(row)

    # ------------------------------------------------------------
    # COMPOSITE REGIME: ONLY THE THREE ORIGINAL INDICATORS
    # ------------------------------------------------------------

    regime_indicators = [
        item
        for item in result["indicators"]
        if item.get("Regime Contribution", True)
    ]

    # --------------------------------------------------------
    # DIAGNOSTIC-ONLY TREASURY INDICATORS
    # --------------------------------------------------------
    # These indicators are advisory-only and do not contribute
    # to the composite regime classification.

    def append_yield_change_diagnostic(name, ticker):
        row = base_indicator(
            name,
            f"{ticker} cached close; diagnostic-only Treasury yield change",
            ticker,
            "20-session change (basis points)",
        )
        row["Regime Contribution"] = False
        row["Threshold Basis"] = "DIAGNOSTIC ONLY — NO REGIME THRESHOLD"

        closes, error = load_closes(ticker)

        if closes is None:
            row["Evidence"] = error
        elif len(closes) < 21 or float(closes.iloc[-21]) <= 0:
            row["Evidence"] = (
                f"Insufficient cached history: {len(closes)} observations; "
                "need 21."
            )
        else:
            latest = float(closes.iloc[-1])
            previous = float(closes.iloc[-21])
            change_bps = (latest - previous) * 10.0

            row["Observation Date"] = pd.Timestamp(
                closes.index[-1]
            ).strftime("%Y-%m-%d")
            row["Value"] = round(change_bps, 1)
            row["Status"] = "DIAGNOSTIC ONLY"
            row["Evidence"] = (
                f"20-session yield change {change_bps:+.1f} bps. "
                "Informational only; excluded from regime classification."
            )

        result["indicators"].append(row)

    append_yield_change_diagnostic(
        "US 3-month Treasury yield change",
        "^IRX",
    )
    append_yield_change_diagnostic(
        "US 5-year Treasury yield change",
        "^FVX",
    )

    # US 10-year minus 3-month Treasury yield spread.
    # Yahoo yield tickers are quoted in tenths of a percentage point.
    row = base_indicator(
        "US 10-year minus 3-month Treasury yield curve",
        "^TNX minus ^IRX cached closes; diagnostic-only yield-curve proxy",
        "^TNX; ^IRX",
        "Yield spread (percentage points)",
    )
    row["Regime Contribution"] = False
    row["Threshold Basis"] = "DIAGNOSTIC ONLY — NO REGIME THRESHOLD"

    ten_year, ten_year_error = load_closes("^TNX")
    three_month, three_month_error = load_closes("^IRX")

    if ten_year is None or three_month is None:
        row["Evidence"] = "; ".join(
            error
            for error in (ten_year_error, three_month_error)
            if error
        )
    elif ten_year.empty or three_month.empty:
        row["Evidence"] = "No usable aligned Treasury yield observations."
    else:
        ten_date = pd.Timestamp(ten_year.index[-1])
        three_date = pd.Timestamp(three_month.index[-1])

        if ten_date.tzinfo is not None:
            ten_date = ten_date.tz_localize(None)
        if three_date.tzinfo is not None:
            three_date = three_date.tz_localize(None)

        if abs(
            (ten_date.normalize() - three_date.normalize()).days
        ) > 3:
            row["Evidence"] = (
                "Treasury yield observations are not date-aligned "
                f"({ten_date:%Y-%m-%d} vs {three_date:%Y-%m-%d}); "
                "yield spread not assessed."
            )
        else:
            spread = (
                float(ten_year.iloc[-1])
                - float(three_month.iloc[-1])
            ) / 10.0

            row["Observation Date"] = min(
                ten_date, three_date
            ).strftime("%Y-%m-%d")
            row["Value"] = round(spread, 3)
            row["Status"] = "DIAGNOSTIC ONLY"
            row["Evidence"] = (
                f"10-year minus 3-month yield spread {spread:+.3f} "
                "percentage points. Informational only; excluded from "
                "regime classification."
            )

    result["indicators"].append(row)

    assessed = [
        item
        for item in result["indicators"]
        if item["Status"] != "UNASSESSED"
    ]

    regime_assessed = [
        item
        for item in regime_indicators
        if item["Status"] != "UNASSESSED"
    ]

    high_count = sum(
        item["Status"] == "HIGH RISK SIGNAL"
        for item in regime_assessed
    )
    elevated_count = sum(
        item["Status"] == "ELEVATED RISK SIGNAL"
        for item in regime_assessed
    )

    result["assessed_indicator_count"] = len(assessed)
    result["indicator_count"] = len(result["indicators"])
    result["regime_indicator_count"] = len(regime_indicators)
    result["regime_assessed_indicator_count"] = len(regime_assessed)
    result["high_risk_signal_count"] = high_count
    result["elevated_risk_signal_count"] = elevated_count

    dates = [
        item["Observation Date"]
        for item in regime_assessed
        if item["Observation Date"]
    ]
    result["as_of"] = max(dates) if dates else None
    result["oldest_observation_date"] = min(dates) if dates else None
    result["latest_observation_date"] = max(dates) if dates else None
    result["assessment_timestamp"] = pd.Timestamp.now(
        tz="UTC"
    ).isoformat()

    result["assessment_completeness"] = (
        "COMPLETE"
        if len(regime_assessed) == len(regime_indicators)
        else "PARTIAL"
    )
    result["coverage_percent"] = round(
        len(regime_assessed) / len(regime_indicators) * 100,
        1,
    ) if regime_indicators else 0.0
    result["missing_indicator_count"] = (
        len(regime_indicators) - len(regime_assessed)
    )

    if high_count or elevated_count >= 2:
        result["status"] = "ADVERSE"
        result["signal_status"] = "ADVERSE"
        result["regime"] = (
            "ADVERSE"
            if result["assessment_completeness"] == "COMPLETE"
            else "ADVERSE — PARTIALLY ASSESSED"
        )
        result["summary"] = (
            f"Macro-risk proxy review signals detected: {high_count} high "
            f"and {elevated_count} elevated among the three composite "
            f"proxies. Coverage: {len(regime_assessed)}/"
            f"{len(regime_indicators)}. Review candidate sensitivity and "
            "sizing; incomplete coverage limits confidence."
        )

    elif elevated_count == 1:
        result["status"] = "CAUTION"
        result["signal_status"] = "CAUTION"
        result["regime"] = (
            "CAUTION"
            if result["assessment_completeness"] == "COMPLETE"
            else "CAUTION — PARTIALLY ASSESSED"
        )
        result["summary"] = (
            "One configured macro proxy has an elevated-risk signal. "
            f"{len(regime_assessed)} of {len(regime_indicators)} "
            "composite proxies were assessed. Review sensitive candidates; "
            "incomplete coverage limits confidence."
        )

    elif result["assessment_completeness"] == "COMPLETE":
        result["status"] = "NEUTRAL"
        result["signal_status"] = "NO CONFIGURED THRESHOLD BREACH"
        result["regime"] = "NEUTRAL"
        result["summary"] = (
            "All three configured composite macro proxies were assessed "
            "without a configured risk threshold breach. This is not a "
            "forecast or proof that macro risk is low."
        )

    else:
        result["status"] = "UNASSESSED"
        result["signal_status"] = "UNASSESSED"
        result["regime"] = "PARTIALLY ASSESSED — NO COMPLETE REGIME"
        result["summary"] = (
            f"Only {len(regime_assessed)} of {len(regime_indicators)} "
            "composite macro proxies were assessed. A complete macro "
            "regime cannot be assigned; missing inputs are not treated "
            "as low risk."
        )

    result["limitations"] = [
        "This is a limited macro-proxy screen, not a full macroeconomic regime model.",
        "The configured thresholds are provisional and require validation before use beyond SHADOW review.",
        "No CPI/inflation-release surprises, central-bank expectations, real yields, FX, or economic-growth surprises are directly assessed.",
        "HYG/LQD relative performance is a credit-risk-appetite proxy, not a measured credit spread.",
        "The 3-month and 5-year yield changes and 10-year-minus-3-month curve are diagnostic only and do not affect the composite regime until calibrated.",
        "No purchase-date or point-in-time macro snapshots were supplied; historical pre-purchase warnings remain unassessed.",
    ]

    return result

def _build_market_risk_assessment(
    final_portfolio_decisions,
    portfolio_value,
    market_intelligence=None,
    reallocation=None,
    financial_statements_by_ticker=None,
):
    """
    Build an advisory-only market and portfolio risk assessment.

    This function does not change production decisions,
    allocation eligibility, trade sizing, or reallocation.
    """

    from analysis.security_classifier import classify_security

    # --------------------------------------------------------
    assessment = {
        "mode": "SHADOW",
        "macro_risk_status": "UNASSESSED",
        "macro_news_assessment": {
            "status": "UNASSESSED",
            "summary": "Macro news has not been screened.",
            "as_of": None,
            "items": [],
            "limitations": [],
            "advisory_only": True,
        },
        "portfolio_concentration": [],
        "proposed_portfolio_concentration": [],
        "portfolio_exposure_comparison": [],
        "exposure_validation": [],
        "classification_coverage": [],
        "known_etf_holdings": [],
        "company_risk_flags": [],
        "individual_stock_assessments": [],
        "financial_resilience_evidence": [],
        "transaction_risk_reviews": [],
        "common_theme_exposure": [],
        "explicit_investment_theme_assessment": [],
        "recommendations": [],
        "macro_stress_scenarios": [],
        "data_quality": {
            "portfolio_data_available": False,
            "market_intelligence_available": False,
            "financial_statements_received": 0,
            "financial_statements_with_data": 0,
            "financial_statements_unavailable": 0,
            "transaction_data_available": False,
            "sector_country_classification_available": False,
            "instrument_type_classification_available": False,
            "known_etf_holdings_count": 0,
            "known_etf_holdings_value": 0.0,
            "etf_lookthrough_assessed": False,
            "current_sector_classification_complete": False,
            "current_country_classification_complete": False,
            "proposed_exposure_calculated": False,
            "macro_risk_assessed": False,
            "correlated_theme_assessed": False,
        },
        "limitations": [
            "Macro risk is screened using a limited cache-only proxy set; a complete macroeconomic regime is not assessed.",
            "Company news headlines are not independently sentiment-scored.",
            "Analyst target upside is an indicator, not a reliable forecast.",
            "Earnings risk requires a reliable event date and current date.",
            "Correlated investment themes require explicit sector, industry, "
            "or theme data.",
            "Proposed exposure is an estimate based on the supplied holdings "
            "and transaction records; it is not an execution or live-price forecast.",
            "This assessment does not change reallocation decisions.",
        ],
    }

    # --------------------------------------------------------
    # SHADOW BROAD-MARKET STRESS INDICATORS
    # --------------------------------------------------------
    # These indicators provide market context only.
    # They do not change production decisions or trade sizing.

    from datetime import datetime
    from data import market_data

    def _load_cached_market_prices(ticker):
        """
        Read existing local price history only.

        SHADOW risk assessment must not trigger network retrieval.
        Returns (prices, reason); reason is populated when unavailable.
        """
        try:
            cache_errors = []

            # Prefer the longer history, but use an existing one-year
            # cache when the two-year cache is absent or unusable.
            for period in ("2y", "1y"):
                cache_file = market_data._cache_file(ticker, period)

                if not os.path.exists(cache_file):
                    continue

                try:
                    prices = pd.read_parquet(cache_file)
                except Exception as exc:
                    cache_errors.append(
                        f"{period} cache read failed ({type(exc).__name__})."
                    )
                    continue

                if not isinstance(prices, pd.DataFrame):
                    cache_errors.append(
                        f"{period} cache is not a DataFrame."
                    )
                    continue

                if prices.empty:
                    cache_errors.append(
                        f"{period} cache is empty."
                    )
                    continue

                return prices, None

            if cache_errors:
                return None, "No usable local cached price history. " + " ".join(
                    cache_errors
                )

            return None, "No local cached price history (checked 2y and 1y caches)."

        except Exception as exc:
            return None, f"Cache lookup failed ({type(exc).__name__})."
    assessment["market_stress_indicators"] = []
    assessment["market_breadth_indicators"] = []

    assessment["data_quality"]["market_stress_assessed"] = False
    assessment["data_quality"]["market_benchmarks_available"] = 0

    benchmark_definitions = [
        {
            "ticker": "^GSPC",
            "name": "S&P 500",
            "role": "Broad US equity market",
            "return_20d_stress": -5.0,
            "return_60d_stress": -10.0,
        },
        {
            "ticker": "QQQ",
            "name": "Nasdaq-100 ETF",
            "role": "Growth and technology-sensitive market",
            "return_20d_stress": -7.0,
            "return_60d_stress": -12.0,
        },
        {
            "ticker": "^VIX",
            "name": "VIX",
            "role": "Implied US equity-market volatility",
            "return_20d_stress": None,
            "return_60d_stress": None,
        },
    ]

    assessment["data_quality"]["market_benchmarks_expected"] = len(
        benchmark_definitions
    )

    today = pd.Timestamp(datetime.now().date())

    try:
        latest_expected_market_session = pd.Timestamp(
            market_data._latest_completed_us_trading_date()
        ).normalize()
    except Exception:
        latest_expected_market_session = None

    assessment["data_quality"]["market_benchmark_latest_expected_session"] = (
        latest_expected_market_session.strftime("%Y-%m-%d")
        if latest_expected_market_session is not None
        else None
    )

    for benchmark in benchmark_definitions:
        ticker = benchmark["ticker"]

        indicator = {
            "Ticker": ticker,
            "Benchmark": benchmark["name"],
            "Role": benchmark["role"],
            "Status": "UNASSESSED",
            "Assessment Completeness": "UNASSESSED",
            "Missing Metrics": [],
            "Latest Observation": None,
            "Expected Latest Session": (
                latest_expected_market_session.strftime("%Y-%m-%d")
                if latest_expected_market_session is not None
                else None
            ),
            "Observation Alignment": "UNASSESSED",
            "Return 20 Sessions %": None,
            "Return 60 Sessions %": None,
            "Realised Volatility 20 Sessions % Annualised": None,
            "Drawdown From 52 Week High %": None,
            "VIX Level": None,
            "Evidence": "",
            "Threshold Basis": "PROVISIONAL SHADOW THRESHOLDS",
            "Advisory Only": True,
        }

        try:
            prices, cache_error = _load_cached_market_prices(ticker)

            if (
                prices is None
                or prices.empty
                or "Close" not in prices.columns
            ):
                indicator["Evidence"] = (
                    cache_error
                    or "Cached data has no usable Close column."
                )
                assessment["market_stress_indicators"].append(indicator)
                continue
            prices = prices.copy()
            prices.index = pd.to_datetime(prices.index)
            prices = prices.sort_index()

            price_column = (
                "Adj Close"
                if ticker != "^VIX" and "Adj Close" in prices.columns
                else "Close"
            )

            closes = pd.to_numeric(
                prices[price_column],
                errors="coerce",
            ).dropna()

            if closes.empty:
                indicator["Evidence"] = "No valid closing prices."
                assessment["market_stress_indicators"].append(indicator)
                continue

            latest_date = pd.Timestamp(closes.index[-1])

            if latest_date.tzinfo is not None:
                latest_date = latest_date.tz_localize(None)

            indicator["Latest Observation"] = latest_date.strftime("%Y-%m-%d")

            # Avoid interpreting stale cached prices as current conditions.
            if (today - latest_date.normalize()).days < 0 or (today - latest_date.normalize()).days > 5:
                indicator["Evidence"] = (
                    "Latest observation is future-dated or more than five calendar days old."
                )
                assessment["market_stress_indicators"].append(indicator)
                continue

            latest = float(closes.iloc[-1])

            if latest <= 0:
                indicator["Evidence"] = "Latest closing value is not positive."
                assessment["market_stress_indicators"].append(indicator)
                continue

            if ticker == "^VIX":
                indicator["VIX Level"] = round(latest, 2)
                indicator["Assessment Completeness"] = "COMPLETE"
                indicator["Missing Metrics"] = []

                if latest >= 30:
                    indicator["Status"] = "HIGH STRESS"
                elif latest >= 25:
                    indicator["Status"] = "ELEVATED STRESS"
                else:
                    indicator["Status"] = "NO VIX THRESHOLD BREACH"

                indicator["Evidence"] = (
                    f"VIX close {latest:.2f}; "
                    "25 and 30 are provisional review thresholds."
                )

            else:
                if len(closes) >= 21:
                    return_20d = (
                        latest / float(closes.iloc[-21]) - 1
                    ) * 100

                    indicator["Return 20 Sessions %"] = round(
                        return_20d, 2
                    )

                if len(closes) >= 61:
                    return_60d = (
                        latest / float(closes.iloc[-61]) - 1
                    ) * 100

                    indicator["Return 60 Sessions %"] = round(
                        return_60d, 2
                    )

                daily_returns = closes.pct_change().dropna()

                if len(daily_returns) >= 20:
                    realised_volatility = (
                        daily_returns.tail(20).std() * (252 ** 0.5) * 100
                    )

                    indicator[
                        "Realised Volatility 20 Sessions % Annualised"
                    ] = round(float(realised_volatility), 2)

                if len(closes) >= 252:
                    trailing_high = closes.tail(252).max()

                    indicator["Drawdown From 52 Week High %"] = round(
                        (latest / float(trailing_high) - 1) * 100,
                        2,
                    )

                return_20d = indicator["Return 20 Sessions %"]
                return_60d = indicator["Return 60 Sessions %"]
                volatility_20d = indicator[
                    "Realised Volatility 20 Sessions % Annualised"
                ]
                drawdown_52w = indicator[
                    "Drawdown From 52 Week High %"
                ]
                missing_metrics = []
                if indicator["Return 20 Sessions %"] is None:
                    missing_metrics.append("20-session return")
                if indicator["Return 60 Sessions %"] is None:
                    missing_metrics.append("60-session return")
                if indicator["Realised Volatility 20 Sessions % Annualised"] is None:
                    missing_metrics.append("20-session realised volatility")
                if indicator["Drawdown From 52 Week High %"] is None:
                    missing_metrics.append("252-session drawdown")

                # Provisional shadow-only review thresholds.
                breaches = []
                high_stress_signals = []

                if (
                    return_20d is not None
                    and return_20d <= benchmark["return_20d_stress"]
                ):
                    breaches.append(
                        f"20-session return {return_20d:.2f}% "
                        f"(threshold {benchmark['return_20d_stress']:.2f}%)"
                    )

                if (
                    return_60d is not None
                    and return_60d <= benchmark["return_60d_stress"]
                ):
                    breaches.append(
                        f"60-session return {return_60d:.2f}% "
                        f"(threshold {benchmark['return_60d_stress']:.2f}%)"
                    )

                if drawdown_52w is not None:
                    if drawdown_52w <= -15.0:
                        high_stress_signals.append(
                            f"52-week-high drawdown {drawdown_52w:.2f}% "
                            "(provisional high-stress threshold -15.00%)"
                        )
                    elif drawdown_52w <= -10.0:
                        breaches.append(
                            f"52-week-high drawdown {drawdown_52w:.2f}% "
                            "(provisional review threshold -10.00%)"
                        )

                if volatility_20d is not None:
                    if volatility_20d >= 40.0:
                        high_stress_signals.append(
                            f"Annualised realised volatility "
                            f"{volatility_20d:.2f}% "
                            "(provisional high-stress threshold 40.00%)"
                        )
                    elif volatility_20d >= 30.0:
                        breaches.append(
                            f"Annualised realised volatility "
                            f"{volatility_20d:.2f}% "
                            "(provisional review threshold 30.00%)"
                        )

                if high_stress_signals:
                    indicator["Status"] = "HIGH STRESS"
                    breaches.extend(high_stress_signals)
                    indicator["Evidence"] = "; ".join(breaches)
                elif breaches:
                    indicator["Status"] = "ELEVATED STRESS"
                    indicator["Evidence"] = "; ".join(breaches)
                else:
                    indicator["Status"] = (
                        "NO PROVISIONAL THRESHOLD BREACH"
                    )
                    indicator["Evidence"] = (
                        "No provisional return, drawdown or realised-volatility "
                        "threshold breached. Broader macroeconomic and "
                        "geopolitical risks remain outside this assessment."
                    )

                indicator["Missing Metrics"] = missing_metrics
                indicator["Assessment Completeness"] = (
                    "PARTIAL" if missing_metrics else "COMPLETE"
                )
                if missing_metrics:
                    if indicator["Status"] == "NO PROVISIONAL THRESHOLD BREACH":
                        indicator["Status"] = (
                            "PARTIALLY ASSESSED — NO PROVISIONAL THRESHOLD BREACH"
                        )
                    indicator["Evidence"] += (
                        " Metrics unavailable: "
                        + ", ".join(missing_metrics)
                        + "."
                    )
                if all(value is None for value in (
                    indicator["Return 20 Sessions %"],
                    indicator["Return 60 Sessions %"],
                    indicator["Realised Volatility 20 Sessions % Annualised"],
                    indicator["Drawdown From 52 Week High %"],
                )):
                    indicator["Status"] = "UNASSESSED"
                    indicator["Assessment Completeness"] = "UNASSESSED"
                    indicator["Evidence"] = (
                        "Fresh observation available, but insufficient history; no 20-session return, "
                        "60-session return, realised volatility or "
                        "252-session drawdown could be calculated."
                    )
                indicator["Threshold Basis"] = (
                    "PROVISIONAL SHADOW REVIEW THRESHOLDS: "
                    f"20-session return {benchmark['return_20d_stress']}%; "
                    f"60-session return {benchmark['return_60d_stress']}%; "
                    "drawdown review -10%, high stress -15%; "
                    "annualised realised volatility review 30%, "
                    "high stress 40%."
                )

            if latest_expected_market_session is None:
                indicator["Observation Alignment"] = "NOT VERIFIED"
                if indicator["Assessment Completeness"] != "UNASSESSED":
                    indicator["Assessment Completeness"] = "PARTIAL"
                indicator["Evidence"] += (
                    " Latest completed US market session could not be verified."
                )
            elif latest_date.normalize() < latest_expected_market_session:
                indicator["Observation Alignment"] = (
                    "BEHIND LATEST COMPLETED SESSION"
                )
                if indicator["Assessment Completeness"] != "UNASSESSED":
                    indicator["Assessment Completeness"] = "PARTIAL"

                if indicator["Status"] == "NO VIX THRESHOLD BREACH":
                    indicator["Status"] = (
                        "PARTIALLY ASSESSED — NO VIX THRESHOLD BREACH"
                    )
                elif indicator["Status"] == "NO PROVISIONAL THRESHOLD BREACH":
                    indicator["Status"] = (
                        "PARTIALLY ASSESSED — NO PROVISIONAL THRESHOLD BREACH"
                    )

                indicator["Evidence"] += (
                    " Observation is behind latest completed US market session "
                    f"({latest_expected_market_session:%Y-%m-%d})."
                )
            else:
                indicator["Observation Alignment"] = "ALIGNED"

        except Exception as exc:
            indicator["Status"] = "UNASSESSED"
            indicator["Evidence"] = (
                f"Benchmark assessment failed: {type(exc).__name__}: {exc}"
            )

        assessment["market_stress_indicators"].append(indicator)

    assessed_benchmarks = [
        item
        for item in assessment["market_stress_indicators"]
        if item["Status"] != "UNASSESSED"
    ]

    _benchmarks_expected = assessment["data_quality"][
        "market_benchmarks_expected"
    ]
    _benchmarks_complete = sum(
        item.get("Assessment Completeness") == "COMPLETE"
        for item in assessment["market_stress_indicators"]
    )
    _benchmarks_partial = sum(
        item.get("Assessment Completeness") == "PARTIAL"
        for item in assessment["market_stress_indicators"]
    )
    _benchmarks_available = _benchmarks_complete + _benchmarks_partial
    assessment["data_quality"]["market_benchmarks_available"] = (
        _benchmarks_available
    )
    assessment["data_quality"]["market_benchmarks_unavailable"] = (
        _benchmarks_expected - _benchmarks_available
    )
    assessment["data_quality"]["market_benchmarks_assessment_unavailable"] = (
        _benchmarks_expected
        - _benchmarks_complete
        - _benchmarks_partial
    )
    assessment["data_quality"]["market_stress_coverage_status"] = (
        "COMPLETE"
        if _benchmarks_complete == _benchmarks_expected
        else "PARTIAL"
        if (_benchmarks_complete + _benchmarks_partial) > 0
        else "UNAVAILABLE"
    )
    assessment["data_quality"]["market_stress_assessed"] = bool(
        assessed_benchmarks
    )

    if assessed_benchmarks:
        stress_count = sum(
            item["Status"] in ("HIGH STRESS", "ELEVATED STRESS")
            for item in assessed_benchmarks
        )

        if stress_count:
            coverage_is_partial = (
                assessment["data_quality"]["market_stress_coverage_status"]
                != "COMPLETE"
            )
            assessment["market_stress_status"] = (
                "STRESS SIGNAL DETECTED — PARTIAL COVERAGE"
                if coverage_is_partial
                else "STRESS SIGNAL DETECTED"
            )
            assessment["recommendations"].append({
                "Priority": "REVIEW",
                "Recommendation": (
                    "Review proposed allocation sizing and timing against "
                    "the broad-market stress indicators before implementation."
                ),
                "Evidence": (
                    f"{stress_count} assessed benchmark(s) breached "
                    "a provisional stress threshold."
                    + (
                        " Overall benchmark coverage is partial; treat this "
                        "as a qualified market-stress signal."
                        if coverage_is_partial
                        else ""
                    )
                ),
                "Governance": "ADVISORY ONLY — NO AUTOMATIC DECISION CHANGE",
            })
        elif assessment["data_quality"]["market_stress_coverage_status"] != "COMPLETE":
            assessment["market_stress_status"] = (
                "PARTIALLY ASSESSED — NO BREACH IN AVAILABLE BENCHMARKS"
            )
        else:
            assessment["market_stress_status"] = (
                "NO PROVISIONAL STRESS THRESHOLD BREACH"
            )
    else:
        assessment["market_stress_status"] = "UNASSESSED"

    # --------------------------------------------------------
    # SHADOW MARKET BREADTH / RELATIVE STRENGTH
    # --------------------------------------------------------
    # These indicators are diagnostic only. They do not feed
    # production decisions, allocation eligibility or sizing.
    #
    # RSP/SPY: equal-weight versus capitalisation-weighted S&P 500.
    # IWM/SPY: US small-cap versus broad-market relative strength.
    # QQQ/SPY: Nasdaq-100 versus broad-market relative strength.
    # MAG7: simple average of seven constituent returns versus SPY.
    #
    # All comparisons use common observation dates. No signal
    # thresholds are applied.

    def _leadership_closes(data):
        """Return usable prices and explicitly identify the selected price basis."""
        if data is None or data.empty:
            return None, None

        frame = data.copy()
        frame.index = pd.to_datetime(frame.index, errors="coerce")
        frame = frame.loc[~frame.index.isna()]

        if getattr(frame.index, "tz", None) is not None:
            frame.index = frame.index.tz_localize(None)

        frame = frame.sort_index()
        frame = frame.loc[~frame.index.duplicated(keep="last")]

        if "Adj Close" in frame.columns:
            adjusted = pd.to_numeric(
                frame["Adj Close"], errors="coerce"
            ).dropna()
            adjusted = adjusted[adjusted > 0]
        else:
            adjusted = pd.Series(dtype="float64")

        if not adjusted.empty:
            return adjusted, "Adj Close"

        if "Close" not in frame.columns:
            return None, None

        closes = pd.to_numeric(
            frame["Close"], errors="coerce"
        ).dropna()
        closes = closes[closes > 0]

        if closes.empty:
            return None, None

        return closes, "Close (fallback)"


    def _leadership_series(ticker):
        """Load one ticker and retain auditable price-source/freshness metadata."""
        provenance = {
            "Ticker": ticker,
            "Retrieval Status": "UNASSESSED",
            "Price Column": None,
            "Price Basis": None,
            "Latest Observation": None,
            "Observation Age Days": None,
            "Freshness Status": "UNASSESSED",
        }

        try:
            data, cache_error = _load_cached_market_prices(ticker)

            if data is None:
                provenance["Retrieval Status"] = "CACHE UNAVAILABLE"
                provenance["Retrieval Detail"] = cache_error
                return None, f"{ticker}: {cache_error}", provenance

            closes, price_basis = _leadership_closes(data)

            if closes is None:
                provenance["Retrieval Status"] = "MISSING OR UNUSABLE"
                provenance["Retrieval Detail"] = (
                    "Cached data contains no usable closing-price history."
                )
                return None, (
                    f"{ticker}: no usable closing-price history."
                ), provenance
            latest_date = pd.Timestamp(closes.index[-1])

            if latest_date.tzinfo is not None:
                latest_date = latest_date.tz_localize(None)

            age_days = (
                pd.Timestamp(datetime.now().date())
                - latest_date.normalize()
            ).days

            if age_days < 0 or age_days > 5:
                provenance.update({
                    "Retrieval Status": "UNAVAILABLE - INVALID FRESHNESS",
                    "Price Column": (
                        "Adj Close" if price_basis == "Adj Close" else "Close"
                    ),
                    "Price Basis": price_basis,
                    "Latest Observation": latest_date.strftime("%Y-%m-%d"),
                    "Observation Age Days": age_days,
                    "Freshness Status": (
                        "FUTURE-DATED" if age_days < 0 else "STALE"
                    ),
                })
                freshness_reason = (
                    "future-dated"
                    if age_days < 0
                    else "more than five calendar days old"
                )
                return None, (
                    f"{ticker}: latest observation "
                    f"{latest_date:%Y-%m-%d} is {freshness_reason}."
                ), provenance

            provenance.update({
                "Retrieval Status": "AVAILABLE",
                "Price Column": (
                    "Adj Close" if price_basis == "Adj Close" else "Close"
                ),
                "Price Basis": price_basis,
                "Latest Observation": latest_date.strftime("%Y-%m-%d"),
                "Observation Age Days": age_days,
                "Freshness Status": "FRESH",
            })
            return closes.rename(ticker), None, provenance

        except Exception as exc:
            provenance["Retrieval Status"] = "RETRIEVAL FAILED"
            return None, (
                f"{ticker}: data retrieval failed ({type(exc).__name__})."
            ), provenance


    def _aligned_leadership_prices(tickers):
        series = []
        errors = []
        provenance = []

        for ticker in tickers:
            closes, error, ticker_provenance = _leadership_series(ticker)
            provenance.append(ticker_provenance)

            if closes is None:
                errors.append(error)
            else:
                series.append(closes)

        if errors:
            return None, "; ".join(errors), provenance

        aligned = pd.concat(
            series, axis=1, join="inner"
        ).dropna().sort_index()

        if aligned.empty:
            return None, (
                "No common valid observation dates across "
                + ", ".join(tickers) + "."
            ), provenance

        return aligned, None, provenance


    def _relative_strength_indicator(
        name,
        numerator_ticker,
        denominator_ticker="SPY",
    ):
        row = {
            "Indicator": name,
            "Status": "UNASSESSED",
            "Latest Observation": None,
            "Relative Change 20 Sessions %": None,
            "Relative Change 60 Sessions %": None,
            "Evidence": "",
            "Interpretation": (
                "Positive values indicate improving relative strength "
                "versus the comparison benchmark; negative values "
                "indicate weakening relative strength."
            ),
            "Advisory Only": True,
        }

        aligned, error, provenance = _aligned_leadership_prices(
            [numerator_ticker, denominator_ticker]
        )
        row["Ticker Data Provenance"] = provenance

        if aligned is None:
            row["Evidence"] = error
            return row

        latest_date = pd.Timestamp(aligned.index[-1])
        today_date = pd.Timestamp(datetime.now().date())
        age_days = (today_date - latest_date.normalize()).days

        row["Latest Observation"] = latest_date.strftime("%Y-%m-%d")

        if age_days < 0 or age_days > 5:
            row["Evidence"] = (
                f"Latest common observation is {age_days} calendar "
                "days old; treated as stale or invalid."
            )
            return row

        ratio = (
            aligned[numerator_ticker]
            / aligned[denominator_ticker]
        )

        if len(ratio) >= 21:
            row["Relative Change 20 Sessions %"] = round(
                (float(ratio.iloc[-1]) / float(ratio.iloc[-21]) - 1.0)
                * 100.0,
                2,
            )

        if len(ratio) >= 61:
            row["Relative Change 60 Sessions %"] = round(
                (float(ratio.iloc[-1]) / float(ratio.iloc[-61]) - 1.0)
                * 100.0,
                2,
            )

        if (
            row["Relative Change 20 Sessions %"] is None
            and row["Relative Change 60 Sessions %"] is None
        ):
            row["Evidence"] = (
                f"Only {len(ratio)} common observations available; "
                "at least 21 are required for a 20-session comparison."
            )
            return row

        row["Status"] = "ASSESSED — NO THRESHOLDS"
        row["Evidence"] = (
            f"{numerator_ticker}/{denominator_ticker} relative-price "
            f"change calculated over {len(ratio)} common observation "
            "dates, using adjusted closes where available. "
            "No signal thresholds applied."
        )

        return row

    leadership_indicators = [
        _relative_strength_indicator(
            "RSP/SPY Relative Strength",
            "RSP",
        ),
        _relative_strength_indicator(
            "IWM/SPY Small-Cap Relative Strength",
            "IWM",
        ),
        _relative_strength_indicator(
            "QQQ/SPY Nasdaq-100 Relative Strength",
            "QQQ",
        ),
    ]

    # MAG7 constituent leadership: simple equal-weight average of
    # the seven individual period returns, less the SPY period return.
    # This is not a daily-rebalanced equal-weight index.

    mag7_tickers = [
        "AAPL",
        "MSFT",
        "AMZN",
        "GOOGL",
        "META",
        "NVDA",
        "TSLA",
    ]

    mag7_row = {
        "Indicator": "MAG7 Equal-Weight Relative Performance vs SPY",
        "Status": "UNASSESSED",
        "Latest Observation": None,
        "Relative Change 20 Sessions %": None,
        "Relative Change 60 Sessions %": None,
        "Evidence": "",
        "Interpretation": (
            "Positive values indicate that the simple average MAG7 "
            "constituent return exceeded SPY; negative values indicate "
            "underperformance."
        ),
        "Advisory Only": True,
        "Constituent Coverage": 0,
        "Constituents Required": 7,
    }

    mag7_aligned, mag7_error, mag7_provenance = (
        _aligned_leadership_prices(mag7_tickers + ["SPY"])
    )
    mag7_row["Ticker Data Provenance"] = mag7_provenance
    mag7_row["Constituent Coverage"] = sum(
        item["Retrieval Status"] == "AVAILABLE"
        for item in mag7_provenance
        if item["Ticker"] in mag7_tickers
    )
    missing_mag7 = [
        item["Ticker"]
        for item in mag7_provenance
        if item["Ticker"] in mag7_tickers
        and item["Retrieval Status"] != "AVAILABLE"
    ]

    if mag7_aligned is None:
        mag7_row["Evidence"] = (
            "MAG7 assessment requires valid histories for all seven "
            "constituents and SPY. "
            f"Retrieved {mag7_row['Constituent Coverage']}/7 MAG7 constituents. "
            f"Unavailable constituents: {', '.join(missing_mag7) or 'none'}. "
            + str(mag7_error)
        )
    else:
        latest_date = pd.Timestamp(mag7_aligned.index[-1])
        today_date = pd.Timestamp(datetime.now().date())
        age_days = (today_date - latest_date.normalize()).days

        mag7_row["Latest Observation"] = latest_date.strftime("%Y-%m-%d")
        if age_days < 0 or age_days > 5:
            mag7_row["Evidence"] = (
                f"Latest common observation is {age_days} calendar "
                "days old; treated as stale or invalid."
            )
        else:
            for lookback, field in (
                (21, "Relative Change 20 Sessions %"),
                (61, "Relative Change 60 Sessions %"),
            ):
                if len(mag7_aligned) < lookback:
                    continue

                start_prices = mag7_aligned.iloc[-lookback]
                end_prices = mag7_aligned.iloc[-1]

                constituent_returns = (
                    end_prices[mag7_tickers]
                    / start_prices[mag7_tickers]
                    - 1.0
                ) * 100.0

                spy_return = (
                    float(end_prices["SPY"])
                    / float(start_prices["SPY"])
                    - 1.0
                ) * 100.0

                equal_weight_return = float(
                    constituent_returns.mean()
                )

                mag7_row[field] = round(
                    equal_weight_return - spy_return,
                    2,
                )

            if (
                mag7_row["Relative Change 20 Sessions %"] is None
                and mag7_row["Relative Change 60 Sessions %"] is None
            ):
                mag7_row["Evidence"] = (
                    f"Only {len(mag7_aligned)} common observations "
                    "available; at least 21 are required."
                )
            else:
                mag7_row["Status"] = "ASSESSED — NO THRESHOLDS"
                mag7_row["Evidence"] = (
                    "Simple arithmetic average of the seven MAG7 "
                    "constituents' period returns, less SPY's period "
                    "return, calculated on common dates. This is not "
                    "a daily-rebalanced equal-weight index. "
                    "No signal thresholds applied."
                )

    leadership_indicators.append(mag7_row)

    # Relative-strength comparisons are leadership indicators.
    # They are not constituent-level market breadth measurements.
    assessment["market_leadership_indicators"] = (
        leadership_indicators
    )

    # ------------------------------------------------------------
    # CONSTITUENT-LEVEL MARKET BREADTH (SHADOW / CACHE ONLY)
    # ------------------------------------------------------------
    # Input contract:
    # data/cache/market_breadth/sp500_constituents.csv
    #
    # Required columns:
    # Ticker, Sector, Effective From, Effective To, Source, Retrieved At
    #
    # One row represents one membership interval. Effective To may be
    # blank for a currently active membership. The file must contain
    # dated membership records; a ticker list without effective dates
    # is not accepted.
    #
    # All price inputs come from the existing local market-price cache.
    # This assessment never downloads or refreshes constituent prices.

    def _build_constituent_market_breadth():
        universe_path = os.path.join(
            "data",
            "cache",
            "market_breadth",
            "sp500_constituents.csv",
        )

        result = {
            "status": "UNASSESSED",
            "as_of": None,
            "universe_file": universe_path,
            "universe_source": [],
            "universe_retrieved_at": None,
            "active_constituents_expected": 0,
            "price_history_available": 0,
            "price_history_unavailable": 0,
            "invalid_universe_rows": 0,
            "historical_backtest_eligible": False,
            "point_in_time_membership_status": "NOT_VALIDATED",
            "reason": "",
            "limitations": [
                "A current constituent snapshot is not sufficient for historical backtesting.",
                "The cumulative advance/decline line is not calculated until historical point-in-time membership completeness is validated.",
                "52-week highs and lows are based on adjusted closing prices, not intraday highs and lows.",
                "Sector returns are equal-weighted constituent returns, not official sector-index returns.",
                "No investment or reallocation thresholds are applied.",
            ],
            "price_data_provenance": [],
            "advisory_only": True,
        }

        empty = [], []

        if not os.path.isfile(universe_path):
            result["reason"] = (
                "Constituent universe file is missing. Create the dated "
                "CSV using the required columns documented in the assessment."
            )
            return result, *empty

        try:
            universe = pd.read_csv(
                universe_path,
                dtype=str,
                keep_default_na=False,
            )
        except Exception as exc:
            result["reason"] = (
                f"Constituent universe could not be read: {type(exc).__name__}."
            )
            return result, *empty

        if universe.empty:
            result["reason"] = "Constituent universe file contains no rows."
            return result, *empty

        normalised_columns = {
            str(column).strip().casefold().replace("_", " "): column
            for column in universe.columns
        }

        required_columns = {
            "ticker",
            "sector",
            "effective from",
            "effective to",
            "source",
            "retrieved at",
        }

        missing_columns = sorted(
            required_columns - set(normalised_columns)
        )

        if missing_columns:
            result["reason"] = (
                "Constituent universe is missing required columns: "
                + ", ".join(missing_columns)
            )
            return result, *empty

        rename_columns = {
            normalised_columns[name]: name
            for name in required_columns
        }
        universe = universe.rename(columns=rename_columns)

        for column in ("ticker", "sector", "source"):
            universe[column] = (
                universe[column].astype(str).str.strip()
            )

        universe["ticker"] = universe["ticker"].str.upper()
        universe["sector"] = universe["sector"].replace("", "UNCLASSIFIED")
        universe["_effective_from"] = pd.to_datetime(
            universe["effective from"],
            errors="coerce",
        ).dt.normalize()
        universe["_effective_to"] = pd.to_datetime(
            universe["effective to"].replace("", pd.NA),
            errors="coerce",
        ).dt.normalize()

        # A blank end date means an open-ended membership interval.
        # A non-blank but unparseable date is invalid and must not
        # silently become an open-ended membership record.
        effective_to_text = (
            universe["effective to"]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        universe["_effective_to_invalid"] = (
            effective_to_text.ne("")
            & universe["_effective_to"].isna()
        )

        universe["_retrieved_at"] = pd.to_datetime(
            universe["retrieved at"],
            errors="coerce",
            utc=True,
        )

        valid_rows = (
            universe["ticker"].ne("")
            & universe["source"].ne("")
            & universe["_effective_from"].notna()
            & ~universe["_effective_to_invalid"]
            & universe["_retrieved_at"].notna()
            & (
                universe["_effective_to"].isna()
                | universe["_effective_to"].ge(
                    universe["_effective_from"]
                )
            )
            & (
                universe["_retrieved_at"]
                <= pd.Timestamp.now(tz="UTC")
            )
        )

        result["invalid_universe_rows"] = int((~valid_rows).sum())

        # Preserve rejected records so potentially active membership
        # omissions can be detected after establishing the SPY as-of date.
        invalid_universe = universe.loc[~valid_rows].copy()

        universe = universe.loc[valid_rows].copy()

        # Reject ambiguous historical membership intervals.
        # Effective To is inclusive; a blank end date is open-ended.
        overlap_tickers = []

        for ticker, ticker_rows in universe.groupby("ticker"):
            ticker_rows = ticker_rows.sort_values(
                "_effective_from"
            )

            previous_max_end = None

            for _, membership in ticker_rows.iterrows():
                current_start = membership["_effective_from"]
                current_end = membership["_effective_to"]

                if (
                    previous_max_end is not None
                    and current_start <= previous_max_end
                ):
                    overlap_tickers.append(ticker)
                    break

                if pd.isna(current_end):
                    previous_max_end = pd.Timestamp.max
                elif previous_max_end is None:
                    previous_max_end = current_end
                else:
                    previous_max_end = max(
                        previous_max_end,
                        current_end,
                    )

        if overlap_tickers:
            overlap_tickers = sorted(set(overlap_tickers))

            result["reason"] = (
                "Ambiguous historical membership: overlapping "
                "effective-date intervals found for "
                + ", ".join(overlap_tickers[:20])
            )
            result["overlapping_membership_tickers"] = len(
                overlap_tickers
            )
            return result, *empty

        if universe.empty and invalid_universe.empty:
            result["reason"] = (
                "No valid constituent records remain after validating "
                "ticker, source, effective dates and retrieval timestamp."
            )
            return result, *empty

        # Anchor membership and prices to the latest valid SPY session.
        spy_closes, spy_error, spy_provenance = _leadership_series("SPY")

        if spy_closes is None or len(spy_closes) < 2:
            result["reason"] = (
                "Unable to establish the latest and previous market sessions "
                "from cached SPY history: "
                + str(spy_error or "insufficient SPY observations")
            )
            return result, *empty

        spy_closes = spy_closes.copy()
        spy_closes.index = pd.DatetimeIndex(
            pd.to_datetime(spy_closes.index, errors="coerce")
        ).normalize()
        spy_closes = spy_closes.loc[
            ~spy_closes.index.isna()
        ].sort_index()
        spy_closes = spy_closes.loc[
            ~spy_closes.index.duplicated(keep="last")
        ]

        if len(spy_closes) < 2:
            result["reason"] = (
                "SPY history has fewer than two valid market sessions."
            )
            return result, *empty

        as_of = pd.Timestamp(spy_closes.index[-1]).normalize()
        previous_session = pd.Timestamp(
            spy_closes.index[-2]
        ).normalize()

        result["as_of"] = as_of.strftime("%Y-%m-%d")

        # Fail closed if an invalid membership record could be active
        # on the assessment date. A missing or malformed boundary is
        # treated as unknown, not as evidence that the record is inactive.
        if not invalid_universe.empty:
            invalid_start = invalid_universe["_effective_from"]
            invalid_end = invalid_universe["_effective_to"]

            potentially_active = (
                (invalid_start.isna() | invalid_start.le(as_of))
                & (invalid_end.isna() | invalid_end.ge(as_of))
            )

            potentially_active_rows = invalid_universe.loc[
                potentially_active
            ]

            result["potentially_active_invalid_rows"] = int(
                len(potentially_active_rows)
            )

            if not potentially_active_rows.empty:
                invalid_tickers = sorted(
                    ticker
                    for ticker in potentially_active_rows["ticker"]
                    .astype(str)
                    .str.strip()
                    .str.upper()
                    .unique()
                    .tolist()
                    if ticker
                )

                result["reason"] = (
                    "Incomplete constituent universe: "
                    f"{len(potentially_active_rows)} invalid membership "
                    "record(s) could be effective on "
                    f"{as_of:%Y-%m-%d}. Correct the membership data "
                    "before assessing market breadth."
                    + (
                        " Affected tickers: "
                        + ", ".join(invalid_tickers[:20])
                        if invalid_tickers
                        else ""
                    )
                )
                return result, *empty

        universe["_retrieved_date"] = (
            universe["_retrieved_at"]
            .dt.tz_convert(None)
            .dt.normalize()
        )

        active = universe.loc[
            universe["_effective_from"].le(as_of)
            & (
                universe["_effective_to"].isna()
                | universe["_effective_to"].ge(as_of)
            )
        ].copy()

        if active.empty:
            result["reason"] = (
                "No constituent membership records are effective on "
                f"{as_of:%Y-%m-%d}."
            )
            return result, *empty

        duplicate_tickers = active.loc[
            active["ticker"].duplicated(keep=False),
            "ticker",
        ].unique().tolist()

        if duplicate_tickers:
            result["reason"] = (
                "Ambiguous active membership: duplicate active ticker "
                "records found for "
                + ", ".join(sorted(duplicate_tickers)[:20])
            )
            return result, *empty

        today = pd.Timestamp(datetime.now().date())
        retrieval_age = (
            today - active["_retrieved_date"]
        ).dt.days

        if retrieval_age.isna().any() or (retrieval_age < 0).any():
            result["reason"] = (
                "Constituent universe contains invalid or future retrieval dates."
            )
            return result, *empty

        if (retrieval_age > 90).any():
            result["reason"] = (
                "Constituent universe is stale: at least one active record "
                "was retrieved more than 90 days ago."
            )
            return result, *empty

        result["active_constituents_expected"] = int(len(active))
        result["universe_source"] = sorted(
            active["source"].dropna().astype(str).unique().tolist()
        )
        result["universe_retrieved_at"] = str(
            active["_retrieved_at"].max()
        )

        spy_return_20 = (
            float(spy_closes.iloc[-1])
            / float(spy_closes.iloc[-21]) - 1.0
        ) * 100.0 if len(spy_closes) >= 21 else None

        spy_return_60 = (
            float(spy_closes.iloc[-1])
            / float(spy_closes.iloc[-61]) - 1.0
        ) * 100.0 if len(spy_closes) >= 61 else None

        constituent_rows = []

        for record in active.itertuples(index=False):
            ticker = str(getattr(record, "ticker")).strip().upper()
            sector = str(getattr(record, "sector") or "UNCLASSIFIED").strip()

            closes, error, provenance = _leadership_series(ticker)

            provenance_row = dict(provenance)
            provenance_row["Ticker"] = ticker
            provenance_row["Sector"] = sector

            if closes is None:
                provenance_row["Breadth Eligibility"] = "UNAVAILABLE"
                provenance_row["Breadth Exclusion Reason"] = str(error)
                result["price_data_provenance"].append(provenance_row)
                continue

            closes = closes.copy()
            closes.index = pd.DatetimeIndex(
                pd.to_datetime(closes.index, errors="coerce")
            ).normalize()
            closes = closes.loc[
                ~closes.index.isna()
            ].sort_index()
            closes = closes.loc[
                ~closes.index.duplicated(keep="last")
            ]
            closes = closes.loc[closes.index <= as_of]

            if closes.empty or pd.Timestamp(closes.index[-1]) != as_of:
                provenance_row["Breadth Eligibility"] = "UNAVAILABLE"
                provenance_row["Breadth Exclusion Reason"] = (
                    "No constituent closing price on the SPY assessment date."
                )
                result["price_data_provenance"].append(provenance_row)
                continue

            closes = pd.to_numeric(
                closes,
                errors="coerce",
            ).dropna()
            closes = closes[closes > 0]

            if closes.empty or pd.Timestamp(closes.index[-1]) != as_of:
                provenance_row["Breadth Eligibility"] = "UNAVAILABLE"
                provenance_row["Breadth Exclusion Reason"] = (
                    "No valid positive closing price on the assessment date."
                )
                result["price_data_provenance"].append(provenance_row)
                continue

            latest_close = float(closes.iloc[-1])
            previous_close = (
                float(closes.loc[previous_session])
                if previous_session in closes.index
                else None
            )

            above_50 = None
            above_200 = None
            new_high_52w = None
            new_low_52w = None
            return_20 = None
            return_60 = None

            if len(closes) >= 50:
                above_50 = latest_close > float(closes.tail(50).mean())

            if len(closes) >= 200:
                above_200 = latest_close > float(closes.tail(200).mean())

            if len(closes) >= 252:
                trailing_252 = closes.tail(252)
                high_252 = float(trailing_252.max())
                low_252 = float(trailing_252.min())
                tolerance = max(abs(latest_close), 1.0) * 1e-8
                new_high_52w = latest_close >= high_252 - tolerance
                new_low_52w = latest_close <= low_252 + tolerance

            if len(closes) >= 21:
                return_20 = (
                    latest_close / float(closes.iloc[-21]) - 1.0
                ) * 100.0

            if len(closes) >= 61:
                return_60 = (
                    latest_close / float(closes.iloc[-61]) - 1.0
                ) * 100.0

            advance_state = None

            if previous_close is not None:
                if latest_close > previous_close:
                    advance_state = "ADVANCE"
                elif latest_close < previous_close:
                    advance_state = "DECLINE"
                else:
                    advance_state = "UNCHANGED"

            constituent_rows.append({
                "Ticker": ticker,
                "Sector": sector or "UNCLASSIFIED",
                "Price Available": True,
                "Advance State": advance_state,
                "Above 50D MA": above_50,
                "Above 200D MA": above_200,
                "New 52W High": new_high_52w,
                "New 52W Low": new_low_52w,
                "Return 20 Sessions %": return_20,
                "Return 60 Sessions %": return_60,
            })

            provenance_row["Breadth Eligibility"] = "AVAILABLE"
            provenance_row["Breadth Exclusion Reason"] = None
            provenance_row["Breadth Observation Date"] = (
                as_of.strftime("%Y-%m-%d")
            )
            provenance_row["Observations Available"] = int(len(closes))
            result["price_data_provenance"].append(provenance_row)

        result["price_history_available"] = len(constituent_rows)
        result["price_history_unavailable"] = (
            result["active_constituents_expected"]
            - result["price_history_available"]
        )

        if not constituent_rows:
            result["reason"] = (
                "No active constituents have usable cached prices on "
                f"the SPY assessment date {as_of:%Y-%m-%d}."
            )
            return result, *empty

        def _valid_rows(field):
            return [
                row for row in constituent_rows
                if row.get(field) is not None
            ]

        def _metric_status(available, expected):
            if available <= 0:
                return "UNASSESSED"
            if (
                available == expected
                and result["invalid_universe_rows"] == 0
            ):
                return "ASSESSED — FULL COVERAGE"
            return "ASSESSED — PARTIAL COVERAGE"

        expected = result["active_constituents_expected"]
        breadth_rows = []

        def _append_breadth_metric(
            name,
            value,
            units,
            available,
            method,
            extra=None,
        ):
            row = {
                "Indicator": name,
                "Value": value,
                "Units": units,
                "As Of": as_of.strftime("%Y-%m-%d"),
                "Available Constituents": int(available),
                "Expected Constituents": int(expected),
                "Coverage %": (
                    round(available / expected * 100.0, 2)
                    if expected else None
                ),
                "Status": _metric_status(available, expected),
                "Method": method,
                "Advisory Only": True,
            }
            if extra:
                row.update(extra)
            breadth_rows.append(row)

        ad_rows = _valid_rows("Advance State")
        advances = sum(
            row["Advance State"] == "ADVANCE" for row in ad_rows
        )
        declines = sum(
            row["Advance State"] == "DECLINE" for row in ad_rows
        )
        unchanged = sum(
            row["Advance State"] == "UNCHANGED" for row in ad_rows
        )
        net_advances = advances - declines

        _append_breadth_metric(
            "Advance / Decline",
            net_advances if ad_rows else None,
            "Net advances",
            len(ad_rows),
            (
                f"Constituent close-to-close direction from "
                f"{previous_session:%Y-%m-%d} to {as_of:%Y-%m-%d}; "
                "only constituents with prices on both exact market sessions."
            ),
            {
                "Advancers": advances,
                "Decliners": declines,
                "Unchanged": unchanged,
                "Net Advances": net_advances if ad_rows else None,
                "Advance / Decline Ratio": (
                    round(advances / declines, 3)
                    if declines else None
                ),
            },
        )

        for field, label in (
            ("Above 50D MA", "Constituents Above 50-Day Moving Average"),
            ("Above 200D MA", "Constituents Above 200-Day Moving Average"),
        ):
            valid = _valid_rows(field)
            count_above = sum(row[field] is True for row in valid)
            _append_breadth_metric(
                label,
                round(count_above / len(valid) * 100.0, 2)
                if valid else None,
                "%",
                len(valid),
                "Latest adjusted close above the mean of the trailing "
                f"{50 if field == 'Above 50D MA' else 200} valid daily adjusted closes.",
                {"Above Moving Average": count_above},
            )

        high_rows = _valid_rows("New 52W High")
        low_rows = _valid_rows("New 52W Low")
        high_count = sum(row["New 52W High"] is True for row in high_rows)
        low_count = sum(row["New 52W Low"] is True for row in low_rows)

        _append_breadth_metric(
            "52-Week Closing Highs",
            high_count if high_rows else None,
            "Constituents",
            len(high_rows),
            "Latest adjusted close equals the highest of the trailing 252 valid adjusted closes.",
        )
        _append_breadth_metric(
            "52-Week Closing Lows",
            low_count if low_rows else None,
            "Constituents",
            len(low_rows),
            "Latest adjusted close equals the lowest of the trailing 252 valid adjusted closes.",
        )
        _append_breadth_metric(
            "Net 52-Week Highs",
            high_count - low_count if high_rows and low_rows else None,
            "Net constituents",
            min(len(high_rows), len(low_rows)),
            "52-week closing highs less 52-week closing lows.",
            {
                "52-Week Highs": high_count if high_rows else None,
                "52-Week Lows": low_count if low_rows else None,
            },
        )

        sector_rows = []
        sector_groups = {}

        for row in constituent_rows:
            sector = row.get("Sector") or "UNCLASSIFIED"
            sector_groups.setdefault(sector, []).append(row)

        for sector, rows in sorted(sector_groups.items()):
            sector_expected = sum(
                str(item.get("sector") or "UNCLASSIFIED") == sector
                for item in active[["ticker", "sector"]].to_dict("records")
            )
            sector_price_rows = [
                row for row in rows if row.get("Price Available")
            ]
            sector_ad_rows = [
                row for row in rows if row.get("Advance State") is not None
            ]
            sector_50_rows = _valid_rows("Above 50D MA")
            sector_200_rows = _valid_rows("Above 200D MA")

            # Restrict each metric to the current sector.
            sector_50_rows = [
                row for row in sector_50_rows if row["Sector"] == sector
            ]
            sector_200_rows = [
                row for row in sector_200_rows if row["Sector"] == sector
            ]

            sector_high_rows = [
                row for row in rows if row.get("New 52W High") is not None
            ]
            sector_low_rows = [
                row for row in rows if row.get("New 52W Low") is not None
            ]

            sector_advances = sum(
                row["Advance State"] == "ADVANCE"
                for row in sector_ad_rows
            )
            sector_declines = sum(
                row["Advance State"] == "DECLINE"
                for row in sector_ad_rows
            )

            returns_20 = [
                row["Return 20 Sessions %"]
                for row in rows
                if row.get("Return 20 Sessions %") is not None
            ]
            returns_60 = [
                row["Return 60 Sessions %"]
                for row in rows
                if row.get("Return 60 Sessions %") is not None
            ]

            sector_return_20 = (
                sum(returns_20) / len(returns_20)
                if returns_20 else None
            )
            sector_return_60 = (
                sum(returns_60) / len(returns_60)
                if returns_60 else None
            )

            sector_above_50 = sum(
                row["Above 50D MA"] is True
                for row in sector_50_rows
            )
            sector_above_200 = sum(
                row["Above 200D MA"] is True
                for row in sector_200_rows
            )
            sector_highs = sum(
                row["New 52W High"] is True
                for row in sector_high_rows
            )
            sector_lows = sum(
                row["New 52W Low"] is True
                for row in sector_low_rows
            )

            sector_rows.append({
                "Sector": sector,
                "As Of": as_of.strftime("%Y-%m-%d"),
                "Active Constituents": int(sector_expected),
                "Price History Available": len(sector_price_rows),
                "Price Coverage %": (
                    round(
                        len(sector_price_rows) / sector_expected * 100.0,
                        2,
                    )
                    if sector_expected else None
                ),
                "Advancers": sector_advances,
                "Decliners": sector_declines,
                "Net Advances": (
                    sector_advances - sector_declines
                    if sector_ad_rows else None
                ),
                "Above 50D MA %": (
                    round(
                        sector_above_50 / len(sector_50_rows) * 100.0,
                        2,
                    )
                    if sector_50_rows else None
                ),
                "Above 50D MA Coverage": len(sector_50_rows),
                "Above 200D MA %": (
                    round(
                        sector_above_200 / len(sector_200_rows) * 100.0,
                        2,
                    )
                    if sector_200_rows else None
                ),
                "Above 200D MA Coverage": len(sector_200_rows),
                "52W Highs": sector_highs if sector_high_rows else None,
                "52W Lows": sector_lows if sector_low_rows else None,
                "Equal-Weight Return 20 Sessions %": (
                    round(sector_return_20, 2)
                    if sector_return_20 is not None else None
                ),
                "Relative Return vs SPY 20 Sessions %": (
                    round(sector_return_20 - spy_return_20, 2)
                    if sector_return_20 is not None
                    and spy_return_20 is not None else None
                ),
                "Equal-Weight Return 60 Sessions %": (
                    round(sector_return_60, 2)
                    if sector_return_60 is not None else None
                ),
                "Relative Return vs SPY 60 Sessions %": (
                    round(sector_return_60 - spy_return_60, 2)
                    if sector_return_60 is not None
                    and spy_return_60 is not None else None
                ),
                "Return 20 Sessions Coverage": len(returns_20),
                "Return 60 Sessions Coverage": len(returns_60),
                "Status": (
                    "ASSESSED — FULL PRICE COVERAGE"
                    if len(sector_price_rows) == sector_expected
                    and result["invalid_universe_rows"] == 0
                    else "ASSESSED — PARTIAL PRICE COVERAGE"
                ),
                "Advisory Only": True,
            })

        assessed_metrics = [
            row for row in breadth_rows
            if row["Status"] != "UNASSESSED"
        ]

        if not assessed_metrics:
            result["reason"] = (
                "Constituent universe loaded, but no breadth measures "
                "have sufficient price history."
            )
        else:
            all_full = all(
                row["Status"] == "ASSESSED — FULL COVERAGE"
                for row in assessed_metrics
            )
            result["status"] = (
                "ASSESSED — FULL COVERAGE"
                if all_full
                else "ASSESSED — PARTIAL COVERAGE"
            )
            result["reason"] = (
                f"Calculated constituent breadth for {len(constituent_rows)} "
                f"of {expected} active constituents as of {as_of:%Y-%m-%d}. "
                f"{result['price_history_unavailable']} constituents lacked "
                "usable prices on the assessment date. Metric-level coverage "
                "is reported separately."
            )

        return result, breadth_rows, sector_rows

    breadth_assessment, breadth_rows, sector_rows = (
        _build_constituent_market_breadth()
    )

    assessment["market_breadth_assessment"] = breadth_assessment
    assessment["market_breadth_indicators"] = breadth_rows
    assessment["market_sector_breadth"] = sector_rows

    assessment["data_quality"]["market_breadth_assessed"] = (
        breadth_assessment["status"].startswith("ASSESSED")
    )
    assessment["data_quality"]["market_breadth_status"] = (
        breadth_assessment["status"]
    )
    assessment["data_quality"]["market_breadth_constituents_expected"] = (
        breadth_assessment["active_constituents_expected"]
    )
    assessment["data_quality"]["market_breadth_price_histories_available"] = (
        breadth_assessment["price_history_available"]
    )
    assessment["data_quality"]["market_breadth_price_histories_unavailable"] = (
        breadth_assessment["price_history_unavailable"]
    )
    assessment["data_quality"]["market_breadth_invalid_universe_rows"] = (
        breadth_assessment["invalid_universe_rows"]
    )

    assessment["data_quality"]["market_leadership_assessed"] = any(
        item["Status"] == "ASSESSED — NO THRESHOLDS"
        for item in leadership_indicators
    )
    assessment["data_quality"]["market_leadership_indicator_count"] = len(
        leadership_indicators
    )
    assessment["data_quality"]["market_leadership_assessed_count"] = sum(
        item["Status"] == "ASSESSED — NO THRESHOLDS"
        for item in leadership_indicators
    )
    assessment["data_quality"]["mag7_constituent_coverage"] = (
        mag7_row["Constituent Coverage"]
    )

    _leadership_provenance_by_ticker = {}
    for _indicator in leadership_indicators:
        for _item in _indicator.get("Ticker Data Provenance", []):
            if isinstance(_item, dict):
                _leadership_provenance_by_ticker[_item["Ticker"]] = _item

    _leadership_provenance = list(
        _leadership_provenance_by_ticker.values()
    )

    assessment["market_leadership_data_provenance"] = (
        _leadership_provenance
    )

    assessment["data_quality"]["market_leadership_tickers_expected"] = (
        len(_leadership_provenance)
    )
    assessment["data_quality"]["market_leadership_tickers_available"] = sum(
        item.get("Retrieval Status") == "AVAILABLE"
        for item in _leadership_provenance
    )
    assessment["data_quality"]["market_leadership_tickers_unavailable"] = sum(
        item.get("Retrieval Status") != "AVAILABLE"
        for item in _leadership_provenance
    )
    assessment["data_quality"]["market_leadership_tickers_stale"] = sum(
        item.get("Freshness Status") in {"STALE", "FUTURE-DATED"}
        for item in _leadership_provenance
    )
    assessment["data_quality"]["market_leadership_close_fallback_count"] = sum(
        item.get("Price Basis") == "Close (fallback)"
        for item in _leadership_provenance
    )


    # CACHE-ONLY MACRO PROXY ASSESSMENT (SHADOW)    # CACHE-ONLY MACRO PROXY ASSESSMENT (SHADOW)
    # --------------------------------------------------------
    macro_assessment = _build_macro_regime_assessment()
    assessment["macro_risk_assessment"] = macro_assessment
    assessment["macro_risk_status"] = macro_assessment["status"]
    assessment["data_quality"]["macro_risk_assessed"] = (
        macro_assessment["status"] != "UNASSESSED"
    )
    assessment["data_quality"]["macro_proxy_indicators_assessed"] = (
        macro_assessment.get("regime_assessed_indicator_count", 0)
    )

    assessment["data_quality"]["macro_proxy_indicators_total"] = (
        macro_assessment.get("regime_indicator_count", 0)
    )
    assessment["data_quality"]["macro_proxy_coverage_percent"] = (
        macro_assessment.get("coverage_percent", 0.0)
    )
    assessment["data_quality"]["macro_assessment_completeness"] = (
        macro_assessment.get("assessment_completeness", "UNASSESSED")
    )
    assessment["data_quality"]["macro_missing_indicator_count"] = (
        macro_assessment.get("missing_indicator_count", 0)
    )


    # ------------------------------------------------------------
    # STRUCTURED MACRO-THEME EVIDENCE (SHADOW / ADVISORY ONLY)
    # ------------------------------------------------------------

    _macro_indicators_by_name = {
        item.get("Indicator"): item
        for item in macro_assessment.get("indicators", [])
        if isinstance(item, dict)
    }

    def _theme_observation(
        indicator,
        date_field,
        value_fields,
    ):
        """Return a traceable observation only when date and values exist."""
        if not isinstance(indicator, dict):
            return None

        observed_at = indicator.get(date_field)
        if not observed_at:
            return None

        values = {}
        for field in value_fields:
            value = indicator.get(field)
            try:
                present = value is not None and bool(pd.notna(value))
            except (TypeError, ValueError):
                present = False

            if present:
                values[field] = value

        if not values:
            return None

        return {
            "indicator": (
                indicator.get("Indicator")
                or indicator.get("Benchmark")
            ),
            "ticker": (
                indicator.get("Tickers")
                or indicator.get("Ticker")
            ),
            "observed_at": str(observed_at),
            "values": values,
            "status": indicator.get("Status", "UNASSESSED"),
            "evidence": indicator.get("Evidence"),
        }


    def _theme_evidence_record(theme, observations, limitation):
        usable_observations = []

        for item in observations:
            if not isinstance(item, dict):
                continue

            status = str(
                item.get("status") or "UNASSESSED"
            ).strip().upper()

            if status in {
                "DIAGNOSTIC ONLY",
                "UNASSESSED",
            }:
                continue

            if not item.get("observed_at"):
                continue

            if not item.get("values"):
                continue

            usable_observations.append(item)

        observation_dates = [
            item["observed_at"]
            for item in usable_observations
        ]

        available = bool(usable_observations and observation_dates)

        return {
            "theme": theme,
            "source": (
                "Cached market-price history via data.market_data"
                if available else None
            ),
            "observed_at": (
                max(observation_dates) if available else None
            ),
            "observation": (
                usable_observations if available else None
            ),
            "value": None,
            "status": (
                "MEASURED_PROXY_AVAILABLE"
                if available else "UNASSESSED"
            ),
            "limitations": [limitation],
            "advisory_only": True,
        }


    _interest_rate_observations = [
        _theme_observation(
            _macro_indicators_by_name.get(name),
            "Observation Date",
            ["Value"],
        )
        for name in (
            "US 10-year Treasury yield change",
            "US 3-month Treasury yield change",
            "US 5-year Treasury yield change",
            "US 10-year minus 3-month Treasury yield curve",
        )
    ]

    _oil_observation = _theme_observation(
        _macro_indicators_by_name.get("Crude oil price change"),
        "Observation Date",
        ["Value"],
    )

    _market_stress_observations = []
    for _benchmark in assessment.get("market_stress_indicators", []):
        if not isinstance(_benchmark, dict):
            continue

        if _benchmark.get("Benchmark") not in {
            "S&P 500",
            "Nasdaq-100 ETF",
            "VIX",
        }:
            continue

        _market_stress_observations.append(
            _theme_observation(
                _benchmark,
                "Latest Observation",
                [
                    "Return 20 Sessions %",
                    "Return 60 Sessions %",
                    "Realised Volatility 20 Sessions % Annualised",
                    "Drawdown From 52 Week High %",
                    "VIX Level",
                ],
            )
        )

    assessment["macro_theme_evidence"] = [
        _theme_evidence_record(
            "INTEREST_RATES",
            _interest_rate_observations,
            (
                "Treasury yields are market proxies, not a forecast of "
                "central-bank policy or company-specific financing costs. "
                "The 3-month, 5-year and yield-curve indicators remain "
                "diagnostic-only."
            ),
        ),
        _theme_evidence_record(
            "INFLATION",
            [_oil_observation],
            (
                "Crude oil price change is an energy-cost and inflation-"
                "pressure proxy, not a direct CPI or broad inflation measure. "
                "Sector impacts can differ."
            ),
        ),
        _theme_evidence_record(
            "AI_BORROWING_AND_CREDIT",
            [],
            (
                "No AI-specific borrowing, debt-maturity or financing-cost "
                "measure is available here. The broad HYG/LQD credit-risk-"
                "appetite proxy does not establish AI-sector borrowing risk."
            ),
        ),
        _theme_evidence_record(
            "MARKET_DOWNTURN",
            _market_stress_observations,
            (
                "Broad-market returns, drawdown, volatility and VIX are "
                "market-stress proxies; they do not independently establish "
                "a recession or predict a future downturn. Thresholds remain "
                "provisional."
            ),
        ),
        _theme_evidence_record(
            "TRADE_AND_GEOPOLITICS",
            [],
            (
                "No structured quantitative trade or geopolitical risk "
                "measure is available in this assessment. News matches "
                "remain unvalidated review signals."
            ),
        ),
    ]


    if macro_assessment["status"] in {"ADVERSE", "CAUTION"}:
        assessment["recommendations"].append({
            "Priority": "REVIEW",
            "Recommendation": (
                "Review proposed purchases against the macro-risk proxy signals; "
                "consider staged entry or reduced proposed sizing where the candidate "
                "is sensitive to the flagged driver."
            ),
            "Evidence": macro_assessment["summary"],
            "Governance": "ADVISORY ONLY — NO AUTOMATIC DECISION CHANGE",
        })

    # --------------------------------------------------------
    # READ-ONLY SECURITY METADATA FOR SHADOW EXPOSURE
    # --------------------------------------------------------
    import json
    import sqlite3
    from pathlib import Path

    # Read existing fundamentals cache only; never request data from Yahoo here.
    fundamentals_by_ticker = {}
    fundamentals_cache_dir = Path("data/cache/fundamentals")

    if fundamentals_cache_dir.exists():
        for cache_file in fundamentals_cache_dir.glob("*.json"):
            try:
                cached = json.loads(cache_file.read_text())
                quote_type = str(cached.get("Quote Type") or "").strip().upper()

                if quote_type in {"ETF", "EQUITY"}:
                    fundamentals_by_ticker[cache_file.stem.upper()] = quote_type
            except (OSError, ValueError, TypeError):
                continue

    metadata_by_ticker = {}
    metadata_db_path = Path("data/portfolio_manager.db")
    metadata_error = None

    try:
        with sqlite3.connect(str(metadata_db_path)) as metadata_connection:
            metadata_connection.row_factory = sqlite3.Row

            evidence_rows = metadata_connection.execute("""
                SELECT ticker, sector, industry, capture_date
                FROM recommendation_evidence
                WHERE ticker IS NOT NULL AND TRIM(ticker) <> ''
                ORDER BY capture_date DESC, id DESC
            """).fetchall()

            for record in evidence_rows:
                metadata_ticker = str(record["ticker"] or "").strip().upper()
                if not metadata_ticker:
                    continue

                metadata = metadata_by_ticker.setdefault(
                    metadata_ticker,
                    {
                        "sector": "",
                        "industry": "",
                        "capture_date": "",
                        "asset_type": "",
                    },
                )

                capture_date = str(record["capture_date"] or "").strip()
                if not metadata["capture_date"] and capture_date:
                    metadata["capture_date"] = capture_date

                sector = str(record["sector"] or "").strip()
                if sector.upper() in {"UNKNOWN", "N/A", "NA", "NONE", "NULL"}:
                    sector = ""
                if not metadata["sector"] and sector:
                    metadata["sector"] = sector

                industry = str(record["industry"] or "").strip()
                if industry.upper() in {"UNKNOWN", "N/A", "NA", "NONE", "NULL"}:
                    industry = ""
                if not metadata["industry"] and industry:
                    metadata["industry"] = industry

            audit_rows = metadata_connection.execute("""
                SELECT ticker, asset_type
                FROM audit_decisions
                WHERE ticker IS NOT NULL AND TRIM(ticker) <> ''
                  AND asset_type IS NOT NULL AND TRIM(asset_type) <> ''
                ORDER BY created_at DESC, id DESC
            """).fetchall()

            seen_asset_types = set()
            for record in audit_rows:
                metadata_ticker = str(record["ticker"]).strip().upper()
                if not metadata_ticker or metadata_ticker in seen_asset_types:
                    continue
                seen_asset_types.add(metadata_ticker)
                metadata_by_ticker.setdefault(metadata_ticker, {
                    "sector": "",
                    "industry": "",
                    "capture_date": "",
                    "asset_type": "",
                })
                metadata_by_ticker[metadata_ticker]["asset_type"] = (
                    str(record["asset_type"]).strip().upper()
                )

    except (sqlite3.Error, OSError) as exc:
        metadata_error = str(exc)
        metadata_by_ticker = {}

    assessment["data_quality"]["exposure_metadata_enrichment_available"] = (
        metadata_error is None
    )
    assessment["data_quality"]["exposure_metadata_tickers_available"] = len(
        metadata_by_ticker
    )
    assessment["data_quality"]["exposure_metadata_latest_capture_date"] = max(
        (
            item["capture_date"]
            for item in metadata_by_ticker.values()
            if item["capture_date"]
        ),
        default=None,
    )
    if metadata_error:
        assessment["data_quality"]["exposure_metadata_error"] = metadata_error

    # NORMALISE INPUTS
    # --------------------------------------------------------

    if isinstance(final_portfolio_decisions, pd.DataFrame):
        rows = final_portfolio_decisions.to_dict("records")
    elif final_portfolio_decisions is None:
        rows = []
    else:
        rows = list(final_portfolio_decisions)

    if isinstance(market_intelligence, pd.DataFrame):
        intelligence_rows = market_intelligence.to_dict("records")
    elif market_intelligence is None:
        intelligence_rows = []
    else:
        intelligence_rows = list(market_intelligence)

    if isinstance(reallocation, pd.DataFrame):
        transaction_rows = reallocation.to_dict("records")
    elif reallocation is None:
        transaction_rows = []
    else:
        transaction_rows = list(reallocation)

    def _classify_company_intelligence_evidence(record):
        """
        PARTIAL means at least one substantive field is present.
        It does not imply comprehensive company-risk coverage.
        """
        if not isinstance(record, dict):
            return "UNAVAILABLE"

        def _company_text(value):
            if value is None:
                return ""
            try:
                if pd.isna(value):
                    return ""
            except (TypeError, ValueError):
                pass
            return str(value).strip()

        def _company_value_present(value):
            if value is None:
                return False
            try:
                if pd.isna(value):
                    return False
            except (TypeError, ValueError):
                pass
            return bool(str(value).strip())

        source_label = _company_text(record.get("Source"))
        if not source_label or source_label.upper() == "UNAVAILABLE":
            return "UNAVAILABLE"

        numeric_fields = (
            "Analyst Mean Score",
            "Analyst Target Mean",
            "Analyst Target High",
            "Analyst Target Low",
            "Current Price",
            "Analyst Target Upside %",
        )

        for field in numeric_fields:
            value = record.get(field)
            if not _company_value_present(value):
                continue
            try:
                numeric_value = float(
                    str(value).replace("%", "").replace(",", "")
                )
                if (
                    pd.notna(numeric_value)
                    and numeric_value not in (
                        float("inf"),
                        float("-inf"),
                    )
                    and (
                        field == "Analyst Target Upside %"
                        or numeric_value > 0
                    )
                ):
                    return "PARTIAL"
            except (TypeError, ValueError):
                continue

        recommendation = _company_text(
            record.get("Analyst Recommendation")
        ).upper()
        if recommendation not in {"", "UNKNOWN", "NONE", "N/A", "NA"}:
            return "PARTIAL"

        earnings_status = _company_text(
            record.get("Earnings Status")
        ).upper()
        if (
            earnings_status == "SCHEDULED"
            and _company_value_present(record.get("Next Earnings Date"))
        ):
            return "PARTIAL"

        headlines = record.get("News Headlines")
        if isinstance(headlines, (list, tuple)):
            if any(
                str(item).strip()
                for item in headlines
                if item is not None
            ):
                return "PARTIAL"
        elif isinstance(headlines, str) and headlines.strip():
            return "PARTIAL"

        return "UNAVAILABLE"

    _intelligence_evidence_classes = [
        _classify_company_intelligence_evidence(record)
        for record in intelligence_rows
    ]
    _intelligence_records_with_evidence = sum(
        status == "PARTIAL"
        for status in _intelligence_evidence_classes
    )

    assessment["data_quality"]["portfolio_data_available"] = bool(rows)
    assessment["data_quality"]["market_intelligence_available"] = bool(
        intelligence_rows
    )
    assessment["data_quality"]["market_intelligence_records_received"] = (
        len(intelligence_rows)
    )
    assessment["data_quality"]["market_intelligence_records_with_evidence"] = (
        _intelligence_records_with_evidence
    )
    assessment["data_quality"]["market_intelligence_records_unavailable"] = (
        len(intelligence_rows) - _intelligence_records_with_evidence
    )
    assessment["data_quality"]["market_intelligence_evidence_available"] = (
        _intelligence_records_with_evidence > 0
    )
    assessment["data_quality"]["transaction_data_available"] = bool(
        transaction_rows
    )

    # --------------------------------------------------------
    # CANDIDATE-LEVEL MACRO SENSITIVITY (HEURISTIC, SHADOW ONLY)
    # --------------------------------------------------------
    # Sector/industry labels indicate a review hypothesis, not a measured stock beta.
    assessment["candidate_macro_reviews"] = []
    _macro = assessment.get("macro_risk_assessment", {})
    _macro_indicators = {
        item.get("Indicator"): item
        for item in _macro.get("indicators", [])
    }
    _yield_indicator = _macro_indicators.get("US 10-year Treasury yield change", {})
    _oil_indicator = _macro_indicators.get("Crude oil price change", {})
    _credit_indicator = _macro_indicators.get("Credit-risk appetite proxy", {})
    _flagged_macro_statuses = {"HIGH RISK SIGNAL", "ELEVATED RISK SIGNAL"}

    _candidate_rows = {}
    for _row in rows:
        _ticker = clean_ticker(_row.get("Ticker", ""))
        _decision = normalise_action(
            _row.get("Final Decision", _row.get("Action", _row.get("Recommendation", "")))
        )
        if _ticker and _decision in {"BUY NEW", "BUY MORE"}:
            _candidate_rows[_ticker] = dict(_row)

    for _transaction in transaction_rows:
        _ticker = clean_ticker(_transaction.get("Destination Ticker", ""))
        if _ticker and _ticker not in {"CASH", "ASSESSMENT CASH", "ASSESSMENT_CASH"}:
            _candidate_rows.setdefault(_ticker, dict(_transaction))

    _rate_sensitive_sectors = {
        "TECHNOLOGY", "COMMUNICATION SERVICES", "CONSUMER CYCLICAL",
        "CONSUMER DISCRETIONARY", "REAL ESTATE", "UTILITIES",
    }
    _credit_sensitive_sectors = {
        "FINANCIAL SERVICES", "REAL ESTATE", "CONSUMER CYCLICAL",
        "CONSUMER DISCRETIONARY",
    }
    _oil_cost_sensitive_sectors = {
        "INDUSTRIALS", "CONSUMER CYCLICAL", "CONSUMER DISCRETIONARY",
        "CONSUMER DEFENSIVE", "MATERIALS",
    }

    for _ticker, _candidate in sorted(_candidate_rows.items()):
        _metadata = metadata_by_ticker.get(_ticker, {})
        _sector = _normalise_economic_sector(
            _candidate.get("Sector") or _metadata.get("sector", "")
        )
        _industry = str(
            _candidate.get("Industry") or _candidate.get("industry")
            or _metadata.get("industry", "") or ""
        ).strip()
        _decision = normalise_action(
            _candidate.get("Final Decision", _candidate.get("Action", _candidate.get("Recommendation", "")))
        )
        _sensitivities = []
        _reasons = []

        if _sector.upper() in _rate_sensitive_sectors:
            _sensitivities.append("INTEREST_RATE / VALUATION SENSITIVITY HYPOTHESIS")
            if _yield_indicator.get("Status") in _flagged_macro_statuses:
                _reasons.append(
                    "The cached 10-year yield proxy has an elevated/high signal; "
                    "review valuation and financing sensitivity."
                )

        if _sector.upper() in _credit_sensitive_sectors:
            _sensitivities.append("CREDIT / FINANCING SENSITIVITY HYPOTHESIS")
            if _credit_indicator.get("Status") in _flagged_macro_statuses:
                _reasons.append(
                    "The HYG-versus-LQD credit-risk-appetite proxy has an "
                    "elevated/high signal; review financing and demand sensitivity."
                )

        if _sector.upper() in _oil_cost_sensitive_sectors:
            _sensitivities.append("ENERGY-COST SENSITIVITY HYPOTHESIS")
            if _oil_indicator.get("Status") in _flagged_macro_statuses:
                _reasons.append(
                    "The crude-oil proxy has an elevated/high rising-price signal; "
                    "review energy-input and transport-cost exposure."
                )
        elif _sector.upper() == "ENERGY":
            _sensitivities.append("COMMODITY-PRICE SENSITIVITY; DIRECTION COMPANY-SPECIFIC")
            if _oil_indicator.get("Status") in _flagged_macro_statuses:
                _reasons.append(
                    "The crude-oil proxy has an elevated/high signal; assess whether "
                    "the candidate benefits or is harmed based on its actual business model."
                )

        _candidate_status = (
            "REVIEW" if _reasons
            else "SENSITIVITY MAPPED" if _sensitivities
            else "UNASSESSED"
        )
        assessment["candidate_macro_reviews"].append({
            "Ticker": _ticker,
            "Final Decision": _decision,
            "Sector": _sector or None,
            "Industry": _industry or None,
            "Macro Sensitivity Hypotheses": "; ".join(_sensitivities) or None,
            "Macro Signal Status": _candidate_status,
            "Review Required": bool(_reasons),
            "Reasons": "; ".join(_reasons) if _reasons else (
                "Sector/industry mapping is a heuristic only; no mapped proxy threshold "
                "breach was identified, or the required proxy was unassessed."
                if _sensitivities else
                "No supported sector/industry sensitivity mapping; candidate macro sensitivity remains unassessed."
            ),
            "Evidence Scope": "Sector/industry heuristic plus cache-only macro proxies; not a measured company beta or causal forecast.",
            "Advisory Only": True,
        })
        if _reasons:
            assessment["recommendations"].append({
                "action": "REVIEW_CANDIDATE_MACRO_SENSITIVITY",
                "subject": _ticker,
                "reason": "; ".join(_reasons),
                "confidence": "LOW — SECTOR/INDUSTRY HEURISTIC",
                "evidence_type": "CACHE_ONLY_MACRO_PROXY_AND_SECTOR_MAPPING",
                "advisory_only": True,
                "governance": "NO AUTOMATIC DECISION OR ALLOCATION CHANGE",
            })

    portfolio_value = safe_float(portfolio_value)

    def _is_present(value):
        if value is None:
            return False

        try:
            if pd.isna(value):
                return False
        except (TypeError, ValueError):
            pass

        if isinstance(value, (list, tuple, dict, set)):
            return bool(value)

        return bool(str(value).strip())

    def _normalise_text(value):
        if not _is_present(value):
            return ""
        return str(value).strip()

    def _ticker_set(values):
        return {
            ticker
            for value in values
            if (ticker := clean_ticker(value))
        }

    # --------------------------------------------------------
    # IDENTIFY PROPOSED TRANSACTION ROLES
    # --------------------------------------------------------

    source_tickers = _ticker_set(
        transaction.get("Source Ticker", "")
        for transaction in transaction_rows
    )

    destination_tickers = _ticker_set(
        transaction.get("Destination Ticker", "")
        for transaction in transaction_rows
    )

    # A positive current market value is required before a decision
    # row is treated as evidence of an existing holding.
    held_tickers = set()

    for row in rows:
        ticker = clean_ticker(row.get("Ticker", ""))

        current_value = safe_float(
            row.get(
                "Current Value",
                row.get("Market Value", 0),
            )
        )

        if ticker and current_value > 0:
            held_tickers.add(ticker)

    # --------------------------------------------------------
    # CURRENT AND PROPOSED PORTFOLIO EXPOSURE
    # --------------------------------------------------------

    # Keep one position record per ticker. Transactions are transfers of
    # capital: reduce an existing source holding and increase a destination.
    # Cash contributions are external capital, not existing security holdings.
    current_positions = {}
    sector_values = {}
    country_values = {}
    industry_values = {}
    missing_industry_tickers = []
    current_classified_sector_value = 0.0
    current_classified_country_value = 0.0
    current_holdings_value = 0.0
    missing_sector_tickers = []
    missing_country_tickers = []

    duplicate_position_rows = []


    for row in rows:
        ticker = clean_ticker(row.get("Ticker", ""))
        current_value = safe_float(
            row.get("Current Value", row.get("Market Value", 0))
        )
        if not ticker or current_value <= 0 or ticker == "CASH":
            continue

        metadata = metadata_by_ticker.get(ticker, {})
        sector = _normalise_economic_sector(
            row.get("Sector") or metadata.get("sector", "")
        )
        if sector.upper() in {"ETF", "ETP", "EXCHANGE TRADED FUND", "EXCHANGE-TRADED FUND"}:
            sector = ""

        country = _normalise_text(row.get("Country", row.get("country")))
        industry = _normalise_text(
            row.get("Industry") or row.get("industry")
            or metadata.get("industry", "")
        )
        if industry.upper() in {"", "N/A", "NA", "UNKNOWN", "NONE", "NULL", "ETF", "ETP"}:
            industry = ""
        asset_type = _normalise_text(
            row.get("Asset Type", row.get("asset_type", ""))
        ).upper()

        if not asset_type:
            asset_type = _normalise_text(metadata.get("asset_type", "")).upper()

        if not asset_type:
            cached_quote_type = fundamentals_by_ticker.get(ticker, "")
            if cached_quote_type == "ETF":
                asset_type = "ETF"
            elif cached_quote_type == "EQUITY":
                asset_type = "STOCK"

        if ticker in current_positions:
            existing = current_positions[ticker]
            duplicate_position_rows.append({
                "ticker": ticker,
                "existing_value": round(safe_float(existing.get("value")), 2),
                "duplicate_value": round(current_value, 2),
                "values_match": abs(safe_float(existing.get("value")) - current_value) <= 0.01,
            })
            # Do not double-count a ticker in portfolio totals. If duplicate
            # rows disagree, retain the first row and explicitly fail validation
            # rather than silently choosing one value as authoritative.
            if abs(safe_float(existing.get("value")) - current_value) > 0.01:
                continue
            # Keep the first row's classifications as the consistent baseline;
            # duplicate metadata must be reconciled upstream rather than patched
            # into the position map without rebuilding exposure totals.
            continue

        current_holdings_value += current_value
        current_positions[ticker] = {
            "value": current_value,
            "sector": sector,
            "country": country,
            "industry": industry,
            "asset_type": asset_type,
        }

        # Industry concentration is measured only for non-ETF holdings.
        # ETF look-through remains unassessed; record the gap explicitly.
        if asset_type == "ETF":
            missing_industry_tickers.append(ticker)
        elif industry:
            industry_values[industry] = industry_values.get(industry, 0.0) + current_value
        else:
            missing_industry_tickers.append(ticker)

        if asset_type == "ETF":
            assessment["known_etf_holdings"].append({
                "ticker": ticker,
                "current_value": round(current_value, 2),
                "sector_lookthrough_status": "NOT_ASSESSED",
                "country_lookthrough_status": "NOT_ASSESSED",
            })

        if sector and asset_type != "ETF":
            sector_values[sector] = sector_values.get(sector, 0.0) + current_value
            current_classified_sector_value += current_value
        else:
            missing_sector_tickers.append(ticker)
        if country and asset_type != "ETF":
            country_values[country] = country_values.get(country, 0.0) + current_value
            current_classified_country_value += current_value
        else:
            # ETF listing/domicile is not underlying geographic exposure.
            # Keep ETF country look-through unclassified until assessed.
            missing_country_tickers.append(ticker)

    known_etf_holdings = assessment["known_etf_holdings"]
    assessment["data_quality"]["instrument_type_classification_available"] = any(
        position.get("asset_type") for position in current_positions.values()
    )
    assessment["data_quality"]["known_etf_holdings_count"] = len(
        known_etf_holdings
    )
    assessment["data_quality"]["known_etf_holdings_value"] = round(
        sum(item["current_value"] for item in known_etf_holdings), 2
    )

    # Use the reconciled value of unique, positive-value owned positions
    # as the denominator for all current-portfolio coverage metrics.
    _coverage_denominator = max(
        float(current_holdings_value or 0.0),
        0.0
    )

    _unclassified_sector_labels = {"", "unknown", "unclassified", "etf", "etp"}
    _classified_sector_value = sum(
        max(float(value or 0.0), 0.0)
        for name, value in sector_values.items()
        if str(name).strip().lower() not in _unclassified_sector_labels
    )
    _classified_country_value = sum(
        max(float(value or 0.0), 0.0)
        for name, value in country_values.items()
        if str(name).strip().lower() not in _unclassified_sector_labels
    )
    _etf_value = float(
        assessment["data_quality"].get("known_etf_holdings_value", 0.0) or 0.0
    )

    assessment["data_quality"]["current_sector_classification_coverage_percent"] = (
        round(min(_classified_sector_value / current_holdings_value * 100.0, 100.0), 2)
        if current_holdings_value > 0 else 0.0
    )
    assessment["data_quality"]["current_country_classification_coverage_percent"] = (
        round(min(_classified_country_value / current_holdings_value * 100.0, 100.0), 2)
        if current_holdings_value > 0 else 0.0
    )
    assessment["data_quality"]["etf_unassessed_portfolio_percent"] = (
        round(min(_etf_value / _coverage_denominator * 100.0, 100.0), 2)
        if _coverage_denominator > 0 else 0.0
    )
    assessment["data_quality"]["etf_lookthrough_status"] = (
        "NOT_ASSESSED" if _etf_value > 0 else "NOT_APPLICABLE"
    )

    dq = assessment["data_quality"]

    # Availability and completeness are separate:
    # partial classifications remain usable, but must not imply full coverage.
    dq["current_sector_classification_available"] = (
        current_classified_sector_value > 0
    )
    dq["current_country_classification_available"] = (
        current_classified_country_value > 0
    )

    dq["current_sector_classification_complete"] = (
        current_holdings_value <= 0
        or (
            not missing_sector_tickers
            and current_classified_sector_value >= current_holdings_value - 0.01
        )
    )
    dq["current_country_classification_complete"] = (
        current_holdings_value <= 0
        or (
            not missing_country_tickers
            and current_classified_country_value >= current_holdings_value - 0.01
        )
    )

    # Retain the legacy combined field for existing consumers.
    # It means both dimensions have some usable classification, not full coverage.
    dq["sector_country_classification_available"] = (
        dq["current_sector_classification_available"]
        and dq["current_country_classification_available"]
    )

    # Build a projected copy and apply each proposed transfer. Source amounts
    # are subtracted only from known current holdings; cash/contribution sources
    # are not treated as securities. Destination classifications come from the
    # transaction, falling back to the existing holding where available.
    proposed_positions = {
        ticker: dict(position) for ticker, position in current_positions.items()
    }
    external_cash_allocated = 0.0
    existing_cash_allocated = 0.0
    transaction_amounts_valid = bool(transaction_rows)

    for transaction in transaction_rows:
        amount = safe_float(
            transaction.get(
                "Reallocated Capital",
                transaction.get("Released Capital", 0),
            )
        )
        if amount <= 0:
            continue

        source_ticker = clean_ticker(transaction.get("Source Ticker", ""))
        destination_ticker = clean_ticker(transaction.get("Destination Ticker", ""))
        source_action = _normalise_text(transaction.get("Source Action", "" )).upper()
        is_cash_source = (
            "CASH" in source_action
            or source_ticker in {"CASH", "ASSESSMENT CASH", "ASSESSMENT_CASH"}
        )

        if source_ticker and source_ticker in proposed_positions and not is_cash_source:
            proposed_positions[source_ticker]["value"] = max(
                0.0, proposed_positions[source_ticker]["value"] - amount
            )

        # Only the explicitly added assessment contribution is
        # additional to the upstream portfolio-value denominator.
        # Existing portfolio cash transfers must not inflate it.
        if source_ticker in {"ASSESSMENT CASH", "ASSESSMENT_CASH"}:
            external_cash_allocated += amount
        elif (
            source_ticker == "CASH"
            and source_action == "EXISTING CASH"
        ):
            existing_cash_allocated += amount

        if destination_ticker and destination_ticker not in {"CASH", "ASSESSMENT CASH", "ASSESSMENT_CASH"}:
            destination = proposed_positions.setdefault(
                destination_ticker,
                {
                    "value": 0.0,
                    "sector": "",
                    "country": "",
                    "asset_type": "",
                },
            )

            destination["value"] += amount
            tx_sector = _normalise_economic_sector(transaction.get("Sector"))
            tx_country = _normalise_text(
                transaction.get("Country", transaction.get("country"))
            )

            if tx_sector:
                destination["sector"] = tx_sector

            if tx_country:
                destination["country"] = tx_country

            tx_industry = _normalise_text(
                transaction.get("Industry")
                or transaction.get("industry", "")
                or metadata_by_ticker.get(destination_ticker, {}).get(
                    "industry", ""
                )
            )

            if tx_industry.upper() in {"N/A", "NA", "UNKNOWN", "NONE", "NULL", "ETF", "ETP"}:
                tx_industry = ""
            if tx_industry:
                destination["industry"] = tx_industry

            tx_asset_type = _normalise_text(
                transaction.get("Asset Type", transaction.get("asset_type", ""))
            ).upper()

            if tx_asset_type:
                destination["asset_type"] = tx_asset_type

    # --------------------------------------------------------
    # SHADOW HOLDING MARKET SENSITIVITY AND CO-MOVEMENT
    # --------------------------------------------------------
    # Historical relationships only. These do not change trades,
    # eligibility, allocation, or production portfolio decisions.

    assessment["holding_market_sensitivity"] = []
    assessment["correlated_holding_clusters"] = []
    assessment["data_quality"]["holding_sensitivity_assessed"] = False
    assessment["data_quality"]["holding_price_series_expected"] = 0
    assessment["data_quality"]["holding_price_series_available"] = 0
    assessment["data_quality"]["holding_price_series_unavailable"] = 0
    assessment["data_quality"]["holding_correlations_insufficient_data"] = 0

    from datetime import datetime as _sensitivity_datetime

    _sensitivity_today = pd.Timestamp(_sensitivity_datetime.now().date())
    _sensitivity_prices = {}
    _sensitivity_unavailable = []

    # Include both existing holdings and proposed destinations.
    _sensitivity_tickers = sorted({
        ticker
        for positions in (current_positions, proposed_positions)
        for ticker, position in positions.items()
        if safe_float(position.get("value", 0)) > 0
        and ticker not in {"CASH", "ASSESSMENT CASH", "ASSESSMENT_CASH"}
    })

    _sensitivity_proposed_holdings_value = sum(
        safe_float(position.get("value", 0))
        for position in proposed_positions.values()
        if safe_float(position.get("value", 0)) > 0
    )

    _sensitivity_benchmarks = {
        "^GSPC": "S&P 500",
        "QQQ": "Nasdaq-100",
    }

    for _ticker in sorted(set(_sensitivity_tickers) | set(_sensitivity_benchmarks)):
        try:
            _prices, _cache_error = _load_cached_market_prices(_ticker)

            if (
                _prices is None
                or _prices.empty
                or "Close" not in _prices.columns
            ):
                _sensitivity_unavailable.append((
                    _ticker,
                    _cache_error or "Cached data has no usable Close column",
                ))
                continue
            _prices = _prices.copy()
            _prices.index = pd.to_datetime(_prices.index)
            if _prices.index.tz is not None:
                _prices.index = _prices.index.tz_localize(None)
            _prices = _prices.sort_index()

            _price_column = (
                "Adj Close"
                if _ticker not in {"^GSPC", "^VIX"}
                and "Adj Close" in _prices.columns
                else "Close"
            )
            _closes = pd.to_numeric(
                _prices[_price_column], errors="coerce"
            ).dropna()

            if len(_closes) < 61:
                _sensitivity_unavailable.append(
                    (_ticker, f"Insufficient history: {len(_closes)} prices")
                )
                continue

            _latest_date = pd.Timestamp(_closes.index[-1])
            if _latest_date.tzinfo is not None:
                _latest_date = _latest_date.tz_localize(None)

            _sensitivity_age_days = (
                _sensitivity_today - _latest_date.normalize()
            ).days

            if _sensitivity_age_days < 0:
                _sensitivity_unavailable.append(
                    (_ticker, f"Future-dated prices: latest {_latest_date.date()}")
                )
                continue

            if _sensitivity_age_days > 5:
                _sensitivity_unavailable.append(
                    (_ticker, f"Stale prices: latest {_latest_date.date()}")
                )
                continue
            _returns = _closes.pct_change().replace(
                [float("inf"), float("-inf")], float("nan")
            ).dropna()

            if len(_returns) < 60:
                _sensitivity_unavailable.append(
                    (_ticker, f"Insufficient daily returns: {len(_returns)}")
                )
                continue

            _sensitivity_prices[_ticker] = _returns

        except Exception as _exc:
            _sensitivity_unavailable.append(
                (_ticker, f"Price load failed: {type(_exc).__name__}")
            )

    _sensitivity_benchmark_returns = {
        _ticker: _sensitivity_prices[_ticker]
        for _ticker in _sensitivity_benchmarks
        if _ticker in _sensitivity_prices
    }

    _sp500_returns = _sensitivity_benchmark_returns.get("^GSPC")
    _down_market_dates = set()

    if _sp500_returns is not None and len(_sp500_returns) >= 60:
        _down_cutoff = _sp500_returns.quantile(0.20)
        _down_market_dates = set(
            _sp500_returns[_sp500_returns <= _down_cutoff].index
        )

    for _ticker in _sensitivity_tickers:
        _current = current_positions.get(_ticker, {})
        _proposed = proposed_positions.get(_ticker, {})
        _current_value = safe_float(_current.get("value", 0))
        _proposed_value = safe_float(_proposed.get("value", 0))

        _row = {
            "Ticker": _ticker,
            "Current Value": round(_current_value, 2),
            "Proposed Value": round(_proposed_value, 2),
            "Current Weight %": round(
                100 * _current_value / current_holdings_value, 2
            ) if current_holdings_value > 0 else None,
            "Proposed Weight %": round(
                100 * _proposed_value / _sensitivity_proposed_holdings_value, 2
            ) if _sensitivity_proposed_holdings_value > 0 else None,
            "Latest Price Observation": None,
            "S&P 500 Correlation": None,
            "S&P 500 Overlap Sessions": 0,
            "Nasdaq-100 Correlation": None,
            "Nasdaq-100 Overlap Sessions": 0,
            "Mean Return On Worst S&P 500 Days %": None,
            "Negative Return Frequency On Worst S&P 500 Days %": None,
            "Downside Overlap Sessions": 0,
            "Status": "UNASSESSED",
            "Evidence": "",
            "Advisory Only": True,
        }

        _holding_returns = _sensitivity_prices.get(_ticker)

        if _holding_returns is None:
            _reason = next(
                (
                    _reason for _failed_ticker, _reason
                    in _sensitivity_unavailable
                    if _failed_ticker == _ticker
                ),
                "No usable price series",
            )
            _row["Evidence"] = _reason
            assessment["holding_market_sensitivity"].append(_row)
            continue

        _row["Latest Price Observation"] = str(
            _holding_returns.index[-1].date()
        )
        _valid_correlations = 0

        for _benchmark_ticker, _benchmark_name in _sensitivity_benchmarks.items():
            _benchmark_returns = _sensitivity_benchmark_returns.get(
                _benchmark_ticker
            )
            if _benchmark_returns is None:
                continue

            _paired = pd.concat(
                [_holding_returns, _benchmark_returns],
                axis=1,
                join="inner",
            ).dropna()

            _correlation_key = (
                "S&P 500 Correlation"
                if _benchmark_ticker == "^GSPC"
                else "Nasdaq-100 Correlation"
            )
            _overlap_key = (
                "S&P 500 Overlap Sessions"
                if _benchmark_ticker == "^GSPC"
                else "Nasdaq-100 Overlap Sessions"
            )
            _row[_overlap_key] = len(_paired)

            if (
                len(_paired) >= 60
                and _paired.iloc[:, 0].std() > 0
                and _paired.iloc[:, 1].std() > 0
            ):
                _correlation_value = float(
                    _paired.iloc[:, 0].corr(_paired.iloc[:, 1])
                )

                # Only count a correlation when the result is finite
                # and within the mathematically valid correlation range.
                if (
                    pd.notna(_correlation_value)
                    and -1.0 <= _correlation_value <= 1.0
                ):
                    _row[_correlation_key] = round(
                        _correlation_value, 3
                    )
                    _valid_correlations += 1

        if _sp500_returns is not None and _down_market_dates:
            _down_holding_returns = _holding_returns[
                _holding_returns.index.isin(_down_market_dates)
            ].dropna()

            _row["Downside Overlap Sessions"] = len(_down_holding_returns)

            if len(_down_holding_returns) >= 30:
                _row["Mean Return On Worst S&P 500 Days %"] = round(
                    float(_down_holding_returns.mean() * 100), 3
                )
                _row["Negative Return Frequency On Worst S&P 500 Days %"] = round(
                    float((_down_holding_returns < 0).mean() * 100), 1
                )

        _row["Status"] = (
            "ASSESSED" if _valid_correlations > 0 else "INSUFFICIENT OVERLAP"
        )
        _row["Evidence"] = (
            "Historical daily returns; correlations use overlapping sessions. "
            "Worst-market-day statistics use the S&P 500 bottom 20% of observed "
            "daily returns and require at least 30 overlapping sessions."
        )
        assessment["holding_market_sensitivity"].append(_row)

    # Pairwise correlations use pair-specific overlapping dates. They do not
    # require every portfolio holding to have data on the same dates.
    _pairwise_count = 0

    for _i, _ticker_a in enumerate(_sensitivity_tickers):
        _returns_a = _sensitivity_prices.get(_ticker_a)
        if _returns_a is None:
            continue

        for _ticker_b in _sensitivity_tickers[_i + 1:]:
            _returns_b = _sensitivity_prices.get(_ticker_b)
            if _returns_b is None:
                continue

            _paired = pd.concat(
                [_returns_a, _returns_b], axis=1, join="inner"
            ).dropna()

            if len(_paired) < 60:
                assessment["data_quality"][
                    "holding_correlations_insufficient_data"
                ] += 1
                continue

            if _paired.iloc[:, 0].std() <= 0 or _paired.iloc[:, 1].std() <= 0:
                continue

            _correlation = float(
                _paired.iloc[:, 0].corr(_paired.iloc[:, 1])
            )

            # Build the pair first so downside correlation can also determine inclusion.
            _pair_row = {
                "Ticker A": _ticker_a,
                "Ticker B": _ticker_b,
                "Correlation": round(_correlation, 3),
                "Overlap Sessions": len(_paired),
                "Downside Correlation": None,
                "Downside Overlap Sessions": 0,
                "Current Combined Value": round(
                    safe_float(current_positions.get(_ticker_a, {}).get("value", 0))
                    + safe_float(current_positions.get(_ticker_b, {}).get("value", 0)),
                    2,
                ),
                "Proposed Combined Value": round(
                    safe_float(proposed_positions.get(_ticker_a, {}).get("value", 0))
                    + safe_float(proposed_positions.get(_ticker_b, {}).get("value", 0)),
                    2,
                ),
                "Evidence": "Historical daily-return correlation; not proof of common causation.",
                "Advisory Only": True,
            }

            if _sp500_returns is not None and _down_market_dates:
                _down_dates = _paired.index.intersection(
                    pd.Index(_down_market_dates)
                )
                _down_pair = _paired.loc[_down_dates]

                _pair_row["Downside Overlap Sessions"] = len(_down_pair)
                if (
                    len(_down_pair) >= 30
                    and _down_pair.iloc[:, 0].std() > 0
                    and _down_pair.iloc[:, 1].std() > 0
                ):
                    _pair_row["Downside Correlation"] = round(
                        float(
                            _down_pair.iloc[:, 0].corr(_down_pair.iloc[:, 1])
                        ),
                        3,
                    )

            # Include pairs with either strong overall correlation or strong
            # downside correlation. Missing downside data does not qualify a pair.
            if (
                _correlation < 0.65
                and (
                    _pair_row["Downside Correlation"] is None
                    or _pair_row["Downside Correlation"] < 0.65
                )
            ):
                continue

            assessment["correlated_holding_clusters"].append(_pair_row)
            _pairwise_count += 1

    assessment["correlated_holding_clusters"].sort(
        key=lambda item: item["Correlation"], reverse=True
    )

    assessment["data_quality"]["holding_price_series_expected"] = len(
        _sensitivity_tickers
    )
    assessment["data_quality"]["holding_price_series_available"] = sum(
        ticker in _sensitivity_prices
        for ticker in _sensitivity_tickers
    )
    assessment["data_quality"]["holding_price_series_unavailable"] = sum(
        ticker not in _sensitivity_prices
        for ticker in _sensitivity_tickers
    )
    assessment["data_quality"]["holding_sensitivity_assessed"] = any(
        item.get("Status") == "ASSESSED"
        for item in assessment["holding_market_sensitivity"]
    )
    # Price correlation identifies co-movement, not shared investment themes.
    # Theme assessment remains unavailable until explicit theme mappings exist.
    assessment["data_quality"]["correlated_theme_assessed"] = False
    assessment["holding_market_sensitivity_unavailable"] = [
        {"Ticker": ticker, "Reason": reason, "Advisory Only": True}
        for ticker, reason in _sensitivity_unavailable
    ]

    if not assessment["data_quality"]["holding_sensitivity_assessed"]:
        assessment["limitations"].append(
            "Holding market sensitivity could not be fully assessed because "
            "usable benchmark or holding price history was unavailable."
        )

    assessment["limitations"].append(
        "Historical correlations and downside co-movement are descriptive, "
        "not forecasts; relationships can change during market stress."
    )
    assessment["limitations"].append(
        "ETF correlations do not replace underlying ETF holdings look-through."
    )

    proposed_sector_values = {}
    proposed_country_values = {}
    proposed_industry_values = {}
    proposed_missing_industry_tickers = []
    proposed_holdings_value = 0.0
    proposed_classified_sector_value = 0.0
    proposed_classified_country_value = 0.0
    proposed_missing_sector_tickers = []
    proposed_missing_country_tickers = []

    for ticker, position in proposed_positions.items():
        value = safe_float(position.get("value", 0))
        if value <= 0:
            continue
        proposed_holdings_value += value
        sector = _normalise_economic_sector(position.get("sector"))
        country = _normalise_text(position.get("country"))
        industry = _normalise_text(position.get("industry"))
        if industry.upper() in {"", "N/A", "NA", "UNKNOWN", "NONE", "NULL", "ETF", "ETP"}:
            industry = ""

        if position.get("asset_type") == "ETF":
            proposed_missing_industry_tickers.append(ticker)
        elif industry:
            proposed_industry_values[industry] = (
                proposed_industry_values.get(industry, 0.0) + value
            )
        else:
            proposed_missing_industry_tickers.append(ticker)

        known_etf_tickers = {
            str(item.get("ticker", "")).strip().upper()
            for item in assessment.get("known_etf_holdings", [])
        }

        is_known_etf = str(ticker).strip().upper() in known_etf_tickers

        if (
            sector
            and str(position.get("asset_type", "")).strip().upper() != "ETF"
            and not is_known_etf
        ):
            proposed_sector_values[sector] = (
                proposed_sector_values.get(sector, 0.0) + value
            )
            proposed_classified_sector_value += value
        else:
            proposed_missing_sector_tickers.append(ticker)
        if country and position.get("asset_type", "").strip().upper() != "ETF" and not is_known_etf:
            proposed_country_values[country] = proposed_country_values.get(country, 0.0) + value
            proposed_classified_country_value += value
        else:
            # Keep known ETFs unclassified for country exposure until
            # underlying geographic look-through is available.
            proposed_missing_country_tickers.append(ticker)

    # Retain total portfolio values for cash reconciliation. Concentration
    # percentages use the separate owned-security-holdings denominators below.
    proposed_portfolio_value = max(0.0, portfolio_value) + external_cash_allocated

    # Explicit denominator definitions for SHADOW reporting.
    assessment["exposure_denominators"] = {
        "current_portfolio_concentration": {
            "value": round(current_holdings_value, 2),
            "basis": "UNIQUE_POSITIVE_VALUE_SECURITY_HOLDINGS",
            "description": (
                "Reconciled current positive-value security holdings; excludes cash "
                "and duplicate position rows."
            ),
        },
        "proposed_portfolio_concentration": {
            "value": round(proposed_holdings_value, 2),
            "basis": "PROJECTED_POSITIVE_VALUE_SECURITY_HOLDINGS",
            "description": (
                "Projected positive-value security holdings after proposed transactions; "
                "excludes any unallocated cash."
            ),
        },
        "current_total_portfolio_value": {
            "value": round(max(0.0, portfolio_value), 2),
            "basis": "UPSTREAM_PORTFOLIO_VALUE",
            "description": (
                "Whole-portfolio value including cash; retained for portfolio and "
                "cash reconciliation, not security concentration."
            ),
        },
        "proposed_total_portfolio_value": {
            "value": round(proposed_portfolio_value, 2),
            "basis": "UPSTREAM_PORTFOLIO_VALUE_PLUS_EXTERNAL_ASSESSMENT_CASH",
            "description": (
                "Projected whole-portfolio value including any unallocated cash."
            ),
        },
        "current_classification_coverage": {
            "value": round(current_holdings_value, 2),
            "basis": "UNIQUE_POSITIVE_VALUE_SECURITY_HOLDINGS",
            "description": (
                "Reconciled current security holdings; excludes cash and duplicate rows."
            ),
        },
        "proposed_classification_coverage": {
            "value": round(proposed_holdings_value, 2),
            "basis": "PROJECTED_POSITIVE_VALUE_SECURITY_HOLDINGS",
            "description": (
                "Projected security holdings after the proposed transactions."
            ),
        },
    }

    assessment["data_quality"]["proposed_exposure_calculated"] = (
        portfolio_value > 0 and bool(transaction_rows)
    )

    assessment["classification_coverage"] = [
        {
            "portfolio_state": "CURRENT",
            "classification": "SECTOR",
            "classified_value": round(current_classified_sector_value, 2),
            "classified_percent_of_holdings": round(
                current_classified_sector_value / current_holdings_value * 100.0, 2
            ) if current_holdings_value > 0 else None,
            "unclassified_value": round(max(0.0, current_holdings_value - current_classified_sector_value), 2),
            "unclassified_tickers": sorted(missing_sector_tickers),
        },
        {
            "portfolio_state": "CURRENT",
            "classification": "COUNTRY",
            "classified_value": round(current_classified_country_value, 2),
            "classified_percent_of_holdings": round(
                current_classified_country_value / current_holdings_value * 100.0, 2
            ) if current_holdings_value > 0 else None,
            "unclassified_value": round(max(0.0, current_holdings_value - current_classified_country_value), 2),
            "unclassified_tickers": sorted(missing_country_tickers),
        },
        {
            "portfolio_state": "CURRENT",
            "classification": "INDUSTRY",
            "classified_value": round(sum(industry_values.values()), 2),
            "classified_percent_of_holdings": round(
                sum(industry_values.values()) / current_holdings_value * 100.0, 2
            ) if current_holdings_value > 0 else None,
            "unclassified_value": round(max(0.0, current_holdings_value - sum(industry_values.values())), 2),
            "unclassified_tickers": sorted(missing_industry_tickers),
        },
        {
            "portfolio_state": "PROPOSED",
            "classification": "SECTOR",
            "classified_value": round(proposed_classified_sector_value, 2),
            "classified_percent_of_holdings": round(
                proposed_classified_sector_value / proposed_holdings_value * 100.0, 2
            ) if proposed_holdings_value > 0 else None,
            "unclassified_value": round(max(0.0, proposed_holdings_value - proposed_classified_sector_value), 2),
            "unclassified_tickers": sorted(proposed_missing_sector_tickers),
        },
        {
            "portfolio_state": "PROPOSED",
            "classification": "COUNTRY",
            "classified_value": round(proposed_classified_country_value, 2),
            "classified_percent_of_holdings": round(
                proposed_classified_country_value / proposed_holdings_value * 100.0, 2
            ) if proposed_holdings_value > 0 else None,
            "unclassified_value": round(max(0.0, proposed_holdings_value - proposed_classified_country_value), 2),
            "unclassified_tickers": sorted(proposed_missing_country_tickers),
        },
        {
            "portfolio_state": "PROPOSED",
            "classification": "INDUSTRY",
            "classified_value": round(sum(proposed_industry_values.values()), 2),
            "classified_percent_of_holdings": round(
                sum(proposed_industry_values.values()) / proposed_holdings_value * 100.0, 2
            ) if proposed_holdings_value > 0 else None,
            "unclassified_value": round(max(0.0, proposed_holdings_value - sum(proposed_industry_values.values())), 2),
            "unclassified_tickers": sorted(proposed_missing_industry_tickers),
        },
    ]

    # --------------------------------------------------------
    # MEASURED SECTOR / INDUSTRY CLASSIFICATION OVERLAP
    # SHADOW ONLY — descriptive, not an allocation rule.
    # --------------------------------------------------------

    _overlap_groups = {}

    for _state, _positions, _denominator in (
        ("CURRENT", current_positions, current_holdings_value),
        ("PROPOSED", proposed_positions, proposed_holdings_value),
    ):
        for _ticker, _position in _positions.items():
            _value = max(0.0, safe_float(_position.get("value", 0)))
            if _value <= 0:
                continue

            # ETF constituent exposure is not available here.
            if str(_position.get("asset_type", "")).strip().upper() == "ETF":
                continue

            for _classification, _raw_label in (
                ("SECTOR", _normalise_economic_sector(_position.get("sector"))),
                ("INDUSTRY", _normalise_text(_position.get("industry"))),
            ):
                _label = str(_raw_label or "").strip()
                if _label.upper() in {
                    "", "N/A", "NA", "UNKNOWN", "NONE", "NULL",
                    "UNCLASSIFIED", "ETF", "ETP",
                }:
                    continue

                _key = (_classification, _label.upper())
                _group = _overlap_groups.setdefault(
                    _key,
                    {
                        "classification": _classification,
                        "label": _label,
                        "current_tickers": [],
                        "current_value": 0.0,
                        "proposed_tickers": [],
                        "proposed_value": 0.0,
                    },
                )

                _ticker_field = (
                    "current_tickers"
                    if _state == "CURRENT"
                    else "proposed_tickers"
                )
                _value_field = (
                    "current_value"
                    if _state == "CURRENT"
                    else "proposed_value"
                )

                _group[_ticker_field].append(_ticker)
                _group[_value_field] += _value

    for _key in sorted(_overlap_groups):
        _group = _overlap_groups[_key]
        _current_tickers = sorted(set(_group["current_tickers"]))
        _proposed_tickers = sorted(set(_group["proposed_tickers"]))
        _current_amount = _group["current_value"]
        _proposed_amount = _group["proposed_value"]

        assessment["common_theme_exposure"].append({
            "classification": _group["classification"],
            "classification_label": _group["label"],
            "current_tickers": _current_tickers,
            "current_holding_count": len(_current_tickers),
            "current_exposure_value": round(_current_amount, 2),
            "current_exposure_percent_of_holdings": round(
                100.0 * _current_amount / current_holdings_value, 2
            ) if current_holdings_value > 0 else None,
            "proposed_tickers": _proposed_tickers,
            "proposed_holding_count": len(_proposed_tickers),
            "proposed_exposure_value": round(_proposed_amount, 2),
            "proposed_exposure_percent_of_holdings": round(
                100.0 * _proposed_amount / proposed_holdings_value, 2
            ) if proposed_holdings_value > 0 else None,
            "evidence": "Existing reconciled sector/industry classifications.",
            "advisory_only": True,
        })

    assessment["common_theme_exposure"].sort(
        key=lambda item: (
            item["classification"],
            -max(
                item["current_exposure_value"],
                item["proposed_exposure_value"],
            ),
            item["classification_label"],
        )
    )

    # Explicit investment themes are deliberately not inferred from
    # sector/industry labels or historical price correlation.
    # Source-backed company-to-theme mapping is not currently available.
    assessment["explicit_investment_theme_assessment"] = [
        {
            "theme": _theme,
            "status": "UNASSESSED — SOURCE-BACKED MAPPING REQUIRED",
            "evidence_available": False,
            "advisory_only": True,
        }
        for _theme in (
            "AI INFRASTRUCTURE",
            "SEMICONDUCTORS",
            "CLOUD INFRASTRUCTURE",
            "DIGITAL ADVERTISING",
        )
    ]
    assessment["data_quality"]["correlated_theme_assessed"] = False

    assessment["limitations"].append(
        "Sector and industry overlap measures use available company "
        "classifications; they do not establish common investment themes."
    )
    assessment["limitations"].append(
        "Explicit investment themes remain unassessed until source-backed "
        "company-to-theme mappings are available. Price correlation is not "
        "evidence of a shared investment theme."
    )

    known_etf_tickers = {
        item["ticker"] for item in assessment["known_etf_holdings"]
    }
    for coverage in assessment["classification_coverage"]:
        unclassified = set(coverage.get("unclassified_tickers", []))
        etf_gaps = sorted(unclassified & known_etf_tickers)
        coverage["unclassified_etf_tickers"] = etf_gaps
        coverage["unclassified_other_tickers"] = sorted(unclassified - known_etf_tickers)
        coverage["look_through_required"] = bool(etf_gaps)

    if current_holdings_value > 0 or proposed_holdings_value > 0:
        for exposure_type, current_exposures, proposed_exposures in (
            ("SECTOR", sector_values, proposed_sector_values),
            ("COUNTRY", country_values, proposed_country_values),
            ("INDUSTRY", industry_values, proposed_industry_values),
        ):
            all_names = set(current_exposures) | set(proposed_exposures)
            for name in sorted(all_names):
                current_amount = current_exposures.get(name, 0.0)
                proposed_amount = proposed_exposures.get(name, 0.0)
                current_pct = (
                    current_amount / current_holdings_value * 100.0
                    if current_holdings_value > 0 else 0.0
                )
                proposed_pct = (
                    proposed_amount / proposed_holdings_value * 100.0
                    if proposed_holdings_value > 0 else 0.0
                )
                comparison = {
                    "type": exposure_type,
                    "name": name,
                    "current_value": round(current_amount, 2),
                    "current_percent": round(current_pct, 2),
                    "proposed_value": round(proposed_amount, 2),
                    "proposed_percent": round(proposed_pct, 2),
                    "change_percentage_points": round(proposed_pct - current_pct, 2),
                    "current_denominator_value": round(
                        current_holdings_value, 2
                    ),
                    "current_denominator_basis": "UNIQUE_POSITIVE_VALUE_SECURITY_HOLDINGS",
                    "proposed_denominator_value": round(
                        proposed_holdings_value, 2
                    ),
                    "proposed_denominator_basis": (
                        "PROJECTED_POSITIVE_VALUE_SECURITY_HOLDINGS"
                    ),
                    "measurement": "ESTIMATED_PROPOSED_EXPOSURE",
                    "advisory_only": True,
                }
                assessment["portfolio_exposure_comparison"].append(comparison)
                if current_pct >= 30.0:
                    assessment["portfolio_concentration"].append({
                        "type": exposure_type,
                        "name": name,
                        "exposure_value": round(current_amount, 2),
                        "exposure_percent": round(current_pct, 2),
                        "denominator_value": round(current_holdings_value, 2),
                        "denominator_basis": "UNIQUE_POSITIVE_VALUE_SECURITY_HOLDINGS",
                        "measurement": "CURRENT_OBSERVED_EXPOSURE",
                        "trigger": "REVIEW_AT_30_PERCENT",
                    })
                if proposed_pct >= 30.0:
                    proposed_record = {
                        "type": exposure_type,
                        "name": name,
                        "exposure_value": round(proposed_amount, 2),
                        "exposure_percent": round(proposed_pct, 2),
                        "change_percentage_points": round(proposed_pct - current_pct, 2),
                        "measurement": "ESTIMATED_PROPOSED_EXPOSURE",
                        "trigger": "REVIEW_AT_30_PERCENT",
                        "denominator_value": round(proposed_holdings_value, 2),
                        "denominator_basis": (
                            "PROJECTED_POSITIVE_VALUE_SECURITY_HOLDINGS"
                        )
                    }
                    assessment["proposed_portfolio_concentration"].append(proposed_record)
                if proposed_pct >= 30.0 and proposed_pct > current_pct + 0.01:
                    assessment["recommendations"].append({
                        "action": "REVIEW_PROPOSED_CONCENTRATION_INCREASE",
                        "subject": name,
                        "reason": (
                            f"Estimated {exposure_type.lower()} exposure increases from "
                            f"{current_pct:.1f}% to {proposed_pct:.1f}% and reaches or exceeds "
                            "the 30% review threshold. Validate before acting."
                        ),
                        "confidence": "MEDIUM",
                        "evidence_type": "ESTIMATED_POST_REALLOCATION_EXPOSURE",
                        "advisory_only": True,
                    })
                elif current_pct >= 30.0:
                    assessment["recommendations"].append({
                        "action": "REVIEW_CONCENTRATION",
                        "subject": name,
                        "reason": (
                            f"Current {exposure_type.lower()} exposure is {current_pct:.1f}% "
                            "of owned security holdings. Review the exposure before increasing it further."
                        ),
                        "confidence": "HIGH",
                        "evidence_type": "OBSERVED_PORTFOLIO_EXPOSURE",
                        "advisory_only": True,
                    })
    else:
        assessment["limitations"].append(
            "Security holdings value is missing or non-positive; holdings concentration percentages cannot be calculated."
        )

    # --------------------------------------------------------
    # EXPOSURE CONSISTENCY VALIDATION (ADVISORY ONLY)
    # --------------------------------------------------------

    def _add_exposure_check(check, status, observed, expected, detail):
        assessment["exposure_validation"].append({
            "check": check,
            "status": status,
            "observed": observed,
            "expected": expected,
            "detail": detail,
            "advisory_only": True,
        })

    if duplicate_position_rows:
        conflicts = [item for item in duplicate_position_rows if not item["values_match"]]
        _add_exposure_check(
            "DUPLICATE_CURRENT_POSITION_TICKERS",
            "FAIL" if conflicts else "WARN",
            len(duplicate_position_rows),
            0,
            "Duplicate ticker rows were found. Matching-value duplicates were counted once; conflicting values were not summed and require authoritative-source reconciliation. "
            + str(duplicate_position_rows),
        )
    else:
        _add_exposure_check(
            "DUPLICATE_CURRENT_POSITION_TICKERS", "PASS", 0, 0,
            "No duplicate positive-value current-position tickers were found.",
        )

    baseline_unallocated = portfolio_value - current_holdings_value

    # Independently verify the portfolio residual against the cash recorded
    # in holdings_raw.csv. A residual alone is not evidence of cash.
    actual_cash_balance = None
    cash_evidence_detail = (
        f"Cash evidence unavailable: {HOLDINGS_FILE} does not exist."
    )

    if os.path.exists(HOLDINGS_FILE):
        try:
            cash_source = pd.read_csv(HOLDINGS_FILE)
            required_cash_columns = {"Ticker", "Market Value"}

            if not required_cash_columns.issubset(cash_source.columns):
                cash_evidence_detail = (
                    f"Cash evidence unavailable: {HOLDINGS_FILE} "
                    "does not contain Ticker and Market Value columns."
                )
            else:
                cash_mask = (
                    cash_source["Ticker"].astype(str).str.strip().str.upper()
                    == "CASH"
                )
                cash_rows = cash_source.loc[cash_mask]
                cash_values = pd.to_numeric(
                    cash_rows["Market Value"],
                    errors="coerce",
                )

                if not cash_rows.empty and (
                    cash_values.isna().any()
                    or (cash_values < -0.01).any()
                ):
                    cash_evidence_detail = (
                        "Cash evidence is incomplete or contains a negative "
                        "cash row; the balance cannot be verified."
                    )
                else:
                    cash_total = float(cash_values.sum())
                    if cash_total < -0.01:
                        cash_evidence_detail = (
                            "The net cash balance in the holdings file is "
                            "negative and cannot be treated as deployable cash."
                        )
                    else:
                        actual_cash_balance = round(max(0.0, cash_total), 2)
                        cash_evidence_detail = (
                            f"Verified existing cash from {HOLDINGS_FILE}: "
                            f"£{actual_cash_balance:.2f} across "
                            f"{len(cash_rows)} CASH row(s)."
                        )

        except Exception as exc:
            cash_evidence_detail = (
                f"Unable to independently read existing cash from "
                f"{HOLDINGS_FILE}: {exc}"
            )

    assessment["data_quality"]["existing_cash_balance_evidence_status"] = (
        "AVAILABLE" if actual_cash_balance is not None else "UNASSESSED"
    )
    assessment["data_quality"]["existing_cash_balance_value"] = (
        actual_cash_balance
    )

    if actual_cash_balance is None:
        reconciliation_status = "UNASSESSED"
        reconciliation_detail = (
            f"Portfolio residual is £{baseline_unallocated:.2f}, but it "
            f"cannot be verified as cash. {cash_evidence_detail}"
        )
        expected_cash_value = None
    else:
        cash_variance = baseline_unallocated - actual_cash_balance
        expected_cash_value = actual_cash_balance

        if baseline_unallocated < -0.02 or cash_variance < -0.02:
            reconciliation_status = "FAIL"
            reconciliation_detail = (
                f"Portfolio residual is £{baseline_unallocated:.2f}, "
                f"while verified cash is £{actual_cash_balance:.2f}. "
                f"Difference: £{cash_variance:.2f}. Recorded securities "
                "plus verified cash exceed the upstream portfolio value."
            )
        elif abs(cash_variance) <= 0.02:
            reconciliation_status = "PASS"
            reconciliation_detail = (
                f"Portfolio residual of £{baseline_unallocated:.2f} "
                f"matches verified cash of £{actual_cash_balance:.2f} "
                "within tolerance."
            )
        else:
            reconciliation_status = "WARN"
            reconciliation_detail = (
                f"Portfolio residual is £{baseline_unallocated:.2f}, "
                f"but verified cash is £{actual_cash_balance:.2f}. "
                f"Unexplained difference: £{cash_variance:.2f}; "
                "the difference is not assumed to be cash."
            )

    _add_exposure_check(
        "CURRENT_PORTFOLIO_VALUE_RECONCILIATION",
        reconciliation_status,
        round(baseline_unallocated, 2),
        expected_cash_value,
        reconciliation_detail,
    )

    source_totals = {}
    invalid_transactions = []
    for index, transaction in enumerate(transaction_rows, start=1):
        amount = safe_float(transaction.get("Reallocated Capital", transaction.get("Released Capital", 0)))
        source_ticker = clean_ticker(transaction.get("Source Ticker", ""))
        destination_ticker = clean_ticker(transaction.get("Destination Ticker", ""))
        source_action = _normalise_text(transaction.get("Source Action", "")).upper()
        is_cash_source = "CASH" in source_action or source_ticker in {"CASH", "ASSESSMENT CASH", "ASSESSMENT_CASH"}
        if amount <= 0 or (not source_ticker and not destination_ticker):
            invalid_transactions.append({"row": index, "amount": round(amount, 2), "source": source_ticker, "destination": destination_ticker})
        if source_ticker and not is_cash_source:
            source_totals[source_ticker] = source_totals.get(source_ticker, 0.0) + max(0.0, amount)

    _add_exposure_check(
        "TRANSACTION_ROW_VALIDITY",
        "FAIL" if invalid_transactions else "PASS",
        len(invalid_transactions), 0,
        "Each transaction must have a positive amount and at least one source/destination ticker. Invalid rows: " + str(invalid_transactions),
    )

    missing_sources = [ticker for ticker in sorted(source_totals) if ticker not in current_positions]
    _add_exposure_check(
        "FUNDING_SOURCE_POSITION_MATCH",
        "FAIL" if missing_sources else "PASS",
        len(missing_sources), 0,
        "Non-cash funding sources must match a current position. Unmatched source tickers: " + str(missing_sources),
    )

    overdrawn_sources = []
    for ticker, amount in sorted(source_totals.items()):
        position_value = safe_float(current_positions.get(ticker, {}).get("value", 0))
        if ticker in current_positions and amount > position_value + 0.01:
            overdrawn_sources.append({
                "ticker": ticker,
                "proposed_funding": round(amount, 2),
                "current_value": round(position_value, 2),
            })
    _add_exposure_check(
        "FUNDING_DOES_NOT_EXCEED_POSITION_VALUE",
        "FAIL" if overdrawn_sources else "PASS",
        len(overdrawn_sources), 0,
        "Total proposed funding from any holding must not exceed its current value. Exceptions: " + str(overdrawn_sources),
    )

    expected_proposed_holdings = (
        current_holdings_value
        + existing_cash_allocated
        + external_cash_allocated
    )
    holdings_residual = proposed_holdings_value - expected_proposed_holdings
    _add_exposure_check(
        "PROPOSED_HOLDINGS_RECONCILIATION",
        "FAIL" if abs(holdings_residual) > 0.02 else "PASS",
        round(proposed_holdings_value, 2),
        round(expected_proposed_holdings, 2),
        f"Proposed security holdings should equal current security holdings plus existing portfolio cash allocated and external assessment cash allocated, after internal source-to-destination transfers net to zero. Residual: {holdings_residual:.2f}.",
    )

    expected_unallocated = (
        baseline_unallocated - existing_cash_allocated
    )
    proposed_unallocated = proposed_portfolio_value - proposed_holdings_value
    unallocated_residual = proposed_unallocated - expected_unallocated
    _add_exposure_check(
        "PROPOSED_PORTFOLIO_DENOMINATOR_RECONCILIATION",
        "FAIL" if abs(unallocated_residual) > 0.02 else "PASS",
        round(proposed_unallocated, 2),
        round(expected_unallocated, 2),
        f"Expected unallocated value equals baseline unallocated portfolio value less existing portfolio cash allocated to destinations. External assessment cash increases both the proposed denominator and proposed holdings; internal transfers net to zero. Residual: {unallocated_residual:.2f}.",
    )

    _add_exposure_check(
        "CURRENT_SECTOR_CLASSIFICATION_COVERAGE",
        "PASS" if not missing_sector_tickers else "WARN",
        round(current_classified_sector_value, 2),
        round(current_holdings_value, 2),
        "Unclassified tickers: " + str(sorted(set(missing_sector_tickers))),
    )
    _add_exposure_check(
        "CURRENT_COUNTRY_CLASSIFICATION_COVERAGE",
        "PASS" if not missing_country_tickers else "WARN",
        round(current_classified_country_value, 2),
        round(current_holdings_value, 2),
        "Unclassified tickers include ETFs or other instruments whose underlying geographic exposure may require look-through; do not infer exposure from listing country. Tickers: " + str(sorted(set(missing_country_tickers))),
    )
    _add_exposure_check(
        "PROPOSED_SECTOR_CLASSIFICATION_COVERAGE",
        "PASS" if not proposed_missing_sector_tickers else "WARN",
        round(proposed_classified_sector_value, 2),
        round(proposed_holdings_value, 2),
        "Unclassified tickers: " + str(sorted(set(proposed_missing_sector_tickers))),
    )
    _add_exposure_check(
        "PROPOSED_COUNTRY_CLASSIFICATION_COVERAGE",
        "PASS" if not proposed_missing_country_tickers else "WARN",
        round(proposed_classified_country_value, 2),
        round(proposed_holdings_value, 2),
        "Country exposure remains incomplete where domicile/underlying-asset data is unavailable. Unclassified tickers: " + str(sorted(set(proposed_missing_country_tickers))),
    )

    # --------------------------------------------------------
    # COMPANY-LEVEL INTELLIGENCE
    # --------------------------------------------------------

    intelligence_by_ticker = {}

    for row in intelligence_rows:
        ticker = clean_ticker(row.get("Ticker", ""))

        if ticker:
            intelligence_by_ticker[ticker] = row

    # --------------------------------------------------------
    # MACRO-RELATED NEWS SCREEN (SHADOW / ADVISORY ONLY)
    # --------------------------------------------------------
    # Reuse existing Market Intelligence headlines. A keyword match
    # identifies a topic for human review; it does not imply adverse
    # sentiment, materiality, causality, or a forecast.

    from datetime import date

    macro_keyword_groups = {
        "INFLATION": (
            "inflation", "cpi", "pce", "consumer prices",
            "producer prices", "price pressures", "disinflation",
            "deflation",
        ),
        "CENTRAL_BANK_AND_RATES": (
            "central bank", "federal reserve", "the fed",
            "bank of england", "boe", "ecb", "interest rate",
            "rate hike", "rate cut", "monetary policy",
            "hawkish", "dovish", "quantitative tightening",
            "quantitative easing", "treasury yield",
        ),
        "GROWTH_AND_EMPLOYMENT": (
            "recession", "gross domestic product", "gdp",
            "pmi", "unemployment", "payrolls", "jobless",
            "economic slowdown", "economic contraction",
            "growth forecast", "manufacturing activity",
        ),
        "TRADE_AND_GEOPOLITICS": (
            "tariff", "sanctions", "trade war", "export controls",
            "geopolitical", "geopolitics", "invasion", "blockade",
            "shipping disruption", "supply chain disruption",
            "supply-chain disruption", "military conflict",
        ),
        "ENERGY_AND_COMMODITIES": (
            "crude oil", "oil supply", "oil prices", "opec",
            "natural gas prices", "energy shock", "energy supply",
            "commodity prices",
        ),
        "CREDIT_AND_FINANCIAL_STABILITY": (
            "credit spread", "credit crunch", "banking stress",
            "liquidity crisis", "sovereign debt", "bond selloff",
            "financial stability", "credit default",
            "bank failure", "debt crisis",
        ),
    }

    macro_news_by_key = {}
    headlines_field_seen = False

    for ticker, intelligence_row in intelligence_by_ticker.items():
        raw_headlines = intelligence_row.get("News Headlines")

        if raw_headlines is None:
            continue

        headlines_field_seen = True

        if isinstance(raw_headlines, str):
            headline_records = [
                {"headline": part.strip()}
                for part in raw_headlines.replace("\r", "\n").split("\n")
                for part in part.split(";")
                if part.strip()
            ]
        elif isinstance(raw_headlines, dict):
            headline_records = [raw_headlines]
        elif isinstance(raw_headlines, (list, tuple)):
            headline_records = []
            for entry in raw_headlines:
                if isinstance(entry, dict):
                    headline_records.append(entry)
                elif isinstance(entry, str) and entry.strip():
                    headline_records.append({"headline": entry.strip()})
        else:
            headline_records = []

        for headline_record in headline_records:
            if isinstance(headline_record, str):
                headline_record = {"headline": headline_record}

            headline = (
                headline_record.get("headline")
                or headline_record.get("title")
                or headline_record.get("Headline")
                or headline_record.get("Title")
            )

            if not isinstance(headline, str) or not headline.strip():
                continue

            headline = " ".join(headline.split())
            headline_lower = headline.casefold()

            matched_categories = [
                category
                for category, keywords in macro_keyword_groups.items()
                if any(keyword in headline_lower for keyword in keywords)
            ]

            if not matched_categories:
                continue

            # Deduplicate identical headlines across ticker records.
            dedupe_key = headline_lower
            item = macro_news_by_key.get(dedupe_key)

            if item is None:
                item = {
                    "Category": "; ".join(matched_categories),
                    "Headline": headline,
                    "Related Tickers": [],
                    "Published Date": (
                        headline_record.get("published")
                        or headline_record.get("published_at")
                        or headline_record.get("date")
                        or headline_record.get("Published Date")
                    ),
                    "Source": (
                        headline_record.get("publisher")
                        or headline_record.get("source")
                        or headline_record.get("Source")
                    ),
                    "Screening Basis": "MACRO KEYWORD MATCH",
                    "Interpretation": (
                        "Potential macro topic; verify recency, source, "
                        "direction and portfolio relevance manually."
                    ),
                    "Advisory Only": True,
                }
                macro_news_by_key[dedupe_key] = item

            if ticker not in item["Related Tickers"]:
                item["Related Tickers"].append(ticker)

            # Do not infer missing source/date metadata.
            if not item["Published Date"]:
                item["Published Date"] = None
            if not item["Source"]:
                item["Source"] = None

    macro_news_items = list(macro_news_by_key.values())

    if macro_news_items:
        macro_news_status = "REVIEW SIGNALS IDENTIFIED"
        macro_news_summary = (
            f"{len(macro_news_items)} distinct headline(s) matched macro "
            "keywords. Matches are review prompts, not confirmed adverse events."
        )
    elif headlines_field_seen:
        macro_news_status = "NO MACRO KEYWORD MATCH"
        macro_news_summary = (
            "No supplied headlines matched the configured macro keywords. "
            "This does not establish that macro risk is absent."
        )
    else:
        macro_news_status = "UNASSESSED"
        macro_news_summary = (
            "No usable News Headlines field was found in the supplied "
            "Market Intelligence rows."
        )


    # ------------------------------------------------------------
    # MACRO NEWS FRESHNESS AND PORTFOLIO RELEVANCE
    #
    # Enrich existing keyword matches only. This is advisory
    # metadata; it does not change portfolio decisions or sizing.
    # ------------------------------------------------------------
    from datetime import datetime, date, timezone
    from email.utils import parsedate_to_datetime
    import ast

    _macro_now = datetime.now(timezone.utc)

    _macro_sector_terms = {
        "INFLATION": (
            "consumer discretionary", "consumer cyclical",
            "consumer staples", "consumer defensive",
            "utilities", "real estate", "industrials",
            "materials", "financial",
        ),
        "CENTRAL_BANK_AND_RATES": (
            "financial", "real estate", "utilities",
            "technology", "consumer discretionary",
            "consumer cyclical",
        ),
        "GROWTH_AND_EMPLOYMENT": (
            "consumer discretionary", "consumer cyclical",
            "industrials", "financial", "technology",
            "materials",
        ),
        "TRADE_AND_GEOPOLITICS": (
            "energy", "industrials", "materials",
            "technology", "consumer staples",
            "consumer defensive", "communication services",
        ),
        "ENERGY_AND_COMMODITIES": (
            "energy", "materials", "industrials", "utilities",
        ),
        "CREDIT_AND_FINANCIAL_STABILITY": (
            "financial", "real estate", "technology",
            "consumer discretionary", "consumer cyclical",
        ),
    }

    _macro_industry_terms = {
        "TRADE_AND_GEOPOLITICS": (
            "shipping", "tanker", "marine", "defence",
            "defense", "airline", "semiconductor",
            "freight", "logistics",
        ),
        "ENERGY_AND_COMMODITIES": (
            "oil", "gas", "energy", "mining", "metals",
            "commodit", "shipping", "tanker", "marine",
        ),
        "CENTRAL_BANK_AND_RATES": (
            "bank", "mortgage", "reit", "lending",
        ),
        "CREDIT_AND_FINANCIAL_STABILITY": (
            "bank", "credit", "lending", "mortgage",
            "insurance", "reit", "real estate",
        ),
    }

    def _macro_parse_date(value):
        if value is None or value == "":
            return None

        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, date):
            parsed = datetime(
                value.year, value.month, value.day,
                tzinfo=timezone.utc,
            )
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            timestamp = float(value)
            if timestamp > 100_000_000_000:
                timestamp /= 1000.0
            try:
                parsed = datetime.fromtimestamp(
                    timestamp, tz=timezone.utc
                )
            except (OverflowError, OSError, ValueError):
                return None
        else:
            text = str(value).strip()
            if not text:
                return None

            try:
                parsed = datetime.fromisoformat(
                    text.replace("Z", "+00:00")
                )
            except (TypeError, ValueError):
                try:
                    parsed = parsedate_to_datetime(text)
                except (TypeError, ValueError, OverflowError):
                    return None

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)

        return parsed.astimezone(timezone.utc)


    cash_tickers = {"CASH", "ASSESSMENT CASH", "ASSESSMENT_CASH"}

    buy_new_tickers = set()

    for decision_row in rows:
        ticker = clean_ticker(decision_row.get("Ticker", ""))
        decision = _normalise_text(
            decision_row.get(
                "Final Decision",
                decision_row.get(
                    "Action",
                    decision_row.get("Recommendation", decision_row.get("Decision", "")),
                ),
            ),
        ).upper()

        if ticker and ticker not in cash_tickers and decision == "BUY NEW":
            buy_new_tickers.add(ticker)

    _macro_roles_by_ticker = {}

    for _ticker in held_tickers:
        _macro_roles_by_ticker.setdefault(
            clean_ticker(_ticker), []
        ).append("CURRENT_HOLDING")

    for _ticker in source_tickers:
        _macro_roles_by_ticker.setdefault(
            clean_ticker(_ticker), []
        ).append("PROPOSED_FUNDING_SOURCE")

    for _ticker in destination_tickers:
        _macro_roles_by_ticker.setdefault(
            clean_ticker(_ticker), []
        ).append("PROPOSED_DESTINATION")

    for _ticker in buy_new_tickers:
        _macro_roles_by_ticker.setdefault(
            clean_ticker(_ticker), []
        ).append("BUY_NEW_CANDIDATE")

    _macro_sector_by_ticker = {}

    for _ticker, _row in intelligence_by_ticker.items():
        _macro_sector_by_ticker[clean_ticker(_ticker)] = {
            "sector": str(
                _row.get("Sector", _row.get("sector", "")) or ""
            ).strip().lower(),
            "industry": str(
                _row.get("Industry", _row.get("industry", "")) or ""
            ).strip().lower(),
        }

    for _item in macro_news_items:
        _raw_date = _item.get("Published Date")
        _published = _macro_parse_date(_raw_date)

        if _raw_date is None or not str(_raw_date).strip():
            _item["Freshness Status"] = "MISSING DATE"
            _item["Age Days"] = None
            _item["Freshness Interpretation"] = (
                "Recency cannot be established because the publication "
                "date was not supplied."
            )
        elif _published is None:
            _item["Freshness Status"] = "INVALID DATE"
            _item["Age Days"] = None
            _item["Freshness Interpretation"] = (
                "A publication date was supplied but could not be parsed."
            )
        else:
            _age_days = (_macro_now - _published).days
            _item["Age Days"] = _age_days

            if _age_days < -1:
                _item["Freshness Status"] = "FUTURE DATE"
                _item["Freshness Interpretation"] = (
                    "The supplied publication date is in the future; "
                    "verify the source metadata."
                )
            elif _age_days <= 7:
                _item["Freshness Status"] = "FRESH"
                _item["Freshness Interpretation"] = (
                    "Published within the last 7 days; verify the source "
                    "and whether the event remains relevant."
                )
            elif _age_days <= 30:
                _item["Freshness Status"] = "AGEING"
                _item["Freshness Interpretation"] = (
                    "Published 8–30 days ago; verify whether the event "
                    "or its consequences remain current."
                )
            else:
                _item["Freshness Status"] = "STALE"
                _item["Freshness Interpretation"] = (
                    "Published more than 30 days ago; do not treat as "
                    "a current risk signal without fresh corroboration."
                )

        _related = _item.get("Related Tickers", [])
        if isinstance(_related, str):
            try:
                _parsed_related = ast.literal_eval(_related)
                _related = (
                    _parsed_related
                    if isinstance(_parsed_related, (list, tuple, set))
                    else [_related]
                )
            except (SyntaxError, ValueError):
                _related = [_related]

        if not isinstance(_related, (list, tuple, set)):
            _related = []

        _related_tickers = {
            clean_ticker(value)
            for value in _related
            if clean_ticker(value)
        }

        _category = str(_item.get("Category", "") or "").strip().upper()
        _direct = sorted(
            ticker for ticker in _related_tickers
            if _macro_roles_by_ticker.get(ticker)
        )

        _potential = {}

        _sector_terms = _macro_sector_terms.get(_category, ())
        _industry_terms = _macro_industry_terms.get(_category, ())

        for _ticker, _details in _macro_sector_by_ticker.items():
            if not _macro_roles_by_ticker.get(_ticker):
                continue

            _sector = _details["sector"]
            _industry = _details["industry"]

            _sector_match = any(
                term in _sector for term in _sector_terms
            )
            _industry_match = any(
                term in _industry for term in _industry_terms
            )

            if _sector_match or _industry_match:
                _basis = []
                if _sector_match:
                    _basis.append("sector")
                if _industry_match:
                    _basis.append("industry")

                _potential[_ticker] = (
                    ", ".join(_basis)
                    + " heuristic; verify manually"
                )

        for _ticker in _direct:
            _potential.setdefault(
                _ticker,
                "direct headline ticker linked to portfolio role",
            )

        _item["Direct Portfolio Tickers"] = [
            {
                "Ticker": ticker,
                "Roles": sorted(set(_macro_roles_by_ticker[ticker])),
            }
            for ticker in _direct
        ]

        _item["Potentially Relevant Tickers"] = [
            {
                "Ticker": ticker,
                "Roles": sorted(set(_macro_roles_by_ticker[ticker])),
                "Relevance Basis": _potential[ticker],
            }
            for ticker in sorted(_potential)
        ]

        if _direct and len(_potential) > len(_direct):
            _item["Portfolio Relevance"] = (
                "DIRECT LINK AND POTENTIAL SECTOR/INDUSTRY OVERLAP"
            )
        elif _direct:
            _item["Portfolio Relevance"] = "DIRECT PORTFOLIO LINK"
        elif _potential:
            _item["Portfolio Relevance"] = (
                "POTENTIAL SECTOR/INDUSTRY OVERLAP"
            )
        else:
            _item["Portfolio Relevance"] = (
                "NO MATCH FOUND IN AVAILABLE SECTOR/INDUSTRY DATA"
            )

        _item["Relevance Limitation"] = (
            "Sector and industry matches are heuristic, not measured "
            "sensitivity or evidence of a positive or negative price impact."
        )
        _item["Advisory Only"] = True


    assessment["macro_news_assessment"] = {
        "status": macro_news_status,
        "summary": macro_news_summary,
        "as_of": date.today().isoformat(),
        "items": macro_news_items,
        "limitations": [
            "This is a keyword screen, not sentiment analysis or an event-impact model.",
            "Headline availability, freshness and coverage depend on existing Market Intelligence.",
            "Published dates and publishers are shown only when supplied by the source.",
            "A keyword match does not establish whether an event is adverse or material to a holding.",
            "No historical point-in-time news archive is used for pre-trade stress testing.",
            "This assessment is SHADOW-only and does not change decisions, eligibility, sizing or trades.",
        ],
        "advisory_only": True,
    }

    assessment["data_quality"]["macro_news_assessed"] = headlines_field_seen
    assessment["data_quality"]["macro_news_matches"] = len(macro_news_items)

    if macro_news_items:
        assessment["recommendations"].append({
            "action": "REVIEW_MACRO_NEWS_WARNINGS",
            "subject": "PORTFOLIO",
            "reason": (
                f"{len(macro_news_items)} distinct headline(s) matched "
                "macro keywords; review the headlines and their relevance "
                "to portfolio exposures."
            ),
            "confidence": "LOW — KEYWORD SCREEN",
            "evidence_type": "EXISTING_MARKET_INTELLIGENCE_HEADLINES",
            "advisory_only": True,
            "governance": "NO AUTOMATIC DECISION OR ALLOCATION CHANGE",
        })


    relevant_tickers = (
        held_tickers | source_tickers | destination_tickers | buy_new_tickers
    ) - cash_tickers

    for ticker in sorted(relevant_tickers):
        row = intelligence_by_ticker.get(ticker)

        roles = []

        if ticker in held_tickers:
            roles.append("CURRENT_HOLDING")

        if ticker in source_tickers:
            roles.append("PROPOSED_FUNDING_SOURCE")

        if ticker in destination_tickers:
            roles.append("PROPOSED_DESTINATION")

        price_risk = _build_price_deterioration_assessment(ticker)

        if price_risk["status"] != "ASSESSED":
            assessment["recommendations"].append({
                "action": "REVIEW_DATA_GAP",
                "subject": ticker,
                "reason": "Price risk unassessed: " + "; ".join(price_risk["reasons"]),
                "confidence": "LOW",
                "evidence_type": "PRICE_HISTORY_UNAVAILABLE",
                "portfolio_roles": roles,
                "advisory_only": True,
            })
        elif price_risk["severity"] in {"REVIEW", "HIGH"}:
            assessment["recommendations"].append({
                "action": "PRICE_DETERIORATION_REVIEW",
                "subject": ticker,
                "reason": "; ".join(price_risk["reasons"]),
                "confidence": "MEDIUM",
                "evidence_type": "HISTORICAL_PRICE_DETERIORATION",
                "portfolio_roles": roles,
                "advisory_only": True,
            })

        if row is None:
            is_etf = (
                fundamentals_by_ticker.get(ticker, "").upper() == "ETF"
                or str(
                    metadata_by_ticker.get(ticker, {}).get("asset_type", "")
                ).strip().upper() == "ETF"
                or any(
                    item.get("ticker") == ticker
                    for item in assessment.get("known_etf_holdings", [])
                )
            )

            if is_etf:
                assessment["recommendations"].append({
                    "action": "REVIEW_DATA_GAP",
                    "subject": ticker,
                    "reason": (
                        "ETF market intelligence is unavailable. "
                        "Underlying holdings, sector exposure and country "
                        "exposure have not been assessed."
                    ),
                    "confidence": "LOW",
                    "evidence_type": "ETF_LOOKTHROUGH_UNASSESSED",
                    "portfolio_roles": roles,
                    "advisory_only": True,
                })
                continue

            flag = {
                "ticker": ticker,
                "portfolio_roles": roles,
                "price_risk": price_risk,
                "intelligence_available": False,
                "evidence_quality": "UNAVAILABLE",
                "news_headlines_available": False,
                "earnings_status": None,
                "analyst_target_upside_percent": None,
                "review_required": True,
                "severity": "UNKNOWN",
                "reasons": [
                    "No matching market-intelligence record is available."
                ],
            }

            assessment["company_risk_flags"].append(flag)

            assessment["recommendations"].append({
                "action": "REVIEW_DATA_GAP",
                "subject": ticker,
                "reason": (
                    "Company-level risk could not be assessed because "
                    "matching market intelligence is unavailable."
                ),
                "confidence": "LOW",
                "evidence_type": "MISSING_INTELLIGENCE",
                "portfolio_roles": roles,
                "advisory_only": True,
            })

            continue

        evidence_quality = _classify_company_intelligence_evidence(row)
        headlines = row.get("News Headlines")
        earnings_status = _normalise_text(
            row.get("Earnings Status")
        ).upper()
        target_upside = row.get("Analyst Target Upside %")

        unavailable = evidence_quality == "UNAVAILABLE"

        flag = {
            "ticker": ticker,
            "portfolio_roles": roles,
            "price_risk": price_risk,
            "intelligence_available": not unavailable,
            "evidence_quality": evidence_quality,
            "news_headlines_available": _is_present(headlines),
            "earnings_status": earnings_status or None,
            "analyst_target_upside_percent": None,
            "review_required": unavailable,
            "severity": "UNKNOWN" if unavailable else "NOT_ASSESSED",
            "reasons": [],
            "verification_reasons": [],
        }

        if unavailable:
            flag["reasons"].append(
                "Market-intelligence collection failed or was unavailable."
            )

        if _is_present(target_upside) and not unavailable:
            try:
                upside = float(
                    str(target_upside)
                    .replace("%", "")
                    .replace(",", "")
                )

                flag["analyst_target_upside_percent"] = round(upside, 2)

                if upside < 0:
                    flag["review_required"] = True
                    flag["severity"] = "REVIEW"
                    flag["reasons"].append(
                        "Analyst mean target is below the current price. "
                        "This is a review signal, not a reliable forecast."
                    )

            except (TypeError, ValueError):
                flag["reasons"].append(
                    "Analyst target upside is present but cannot be parsed."
                )

        if earnings_status and earnings_status != "UNKNOWN" and not unavailable:
            flag["verification_reasons"].append(
                f"Earnings status reported as {earnings_status}; "
                "event timing and potential impact require verification."
            )

        if _is_present(headlines) and not unavailable:
            flag["verification_reasons"].append(
                "Company news is available but has not been sentiment-scored."
            )

        if flag["review_required"] and not unavailable:
            assessment["recommendations"].append({
                "action": "INVESTIGATE_COMPANY_RISK",
                "subject": ticker,
                "reason": "; ".join(flag["reasons"]),
                "confidence": "MEDIUM",
                "evidence_type": "ANALYST_TARGET_SIGNAL",
                "portfolio_roles": roles,
                "advisory_only": True,
            })

        if unavailable:
            assessment["recommendations"].append({
                "action": "REVIEW_DATA_GAP",
                "subject": ticker,
                "reason": (
                    "Risk information is unavailable. Do not interpret "
                    "missing signals as evidence of low risk."
                ),
                "confidence": "LOW",
                "evidence_type": "INTELLIGENCE_SOURCE_UNAVAILABLE",
                "portfolio_roles": roles,
                "advisory_only": True,
            })

        if (
            flag["news_headlines_available"]
            or flag["earnings_status"]
            or flag["analyst_target_upside_percent"] is not None
            or unavailable
            or price_risk["status"] != "ASSESSED"
            or price_risk["severity"] in {"REVIEW", "HIGH"}
        ):
            assessment["company_risk_flags"].append(flag)

    # --------------------------------------------------------
    # TRANSACTION-AWARE RISK REVIEWS
    # --------------------------------------------------------

    flags_by_ticker = {
        flag["ticker"]: flag
        for flag in assessment["company_risk_flags"]
    }

    decision_by_ticker = {}
    for decision_row in rows:
        ticker = clean_ticker(decision_row.get("Ticker", ""))
        if ticker:
            decision_by_ticker[ticker] = decision_row

    for ticker in sorted(relevant_tickers):
        if not ticker or ticker in cash_tickers:
            continue
        roles = []
        if ticker in held_tickers:
            roles.append("CURRENT_HOLDING")
        if ticker in buy_new_tickers:
            roles.append("BUY_NEW_CANDIDATE")
        if ticker in source_tickers:
            roles.append("PROPOSED_FUNDING_SOURCE")
        if ticker in destination_tickers:
            roles.append("PROPOSED_DESTINATION")

        intelligence = intelligence_by_ticker.get(ticker)
        flag = flags_by_ticker.get(ticker)
        decision_row = decision_by_ticker.get(ticker, {})
        evidence_quality = (
            _classify_company_intelligence_evidence(intelligence)
            if intelligence is not None else "UNAVAILABLE"
        )
        evidence_available = evidence_quality == "PARTIAL"

        is_etf = (
            fundamentals_by_ticker.get(ticker, "").upper() == "ETF"
            or str(
                metadata_by_ticker.get(ticker, {}).get("asset_type", "")
            ).strip().upper() == "ETF"
            or any(
                item.get("ticker") == ticker
                for item in assessment.get("known_etf_holdings", [])
            )
        )

        risk_reasons = list((flag or {}).get("reasons") or [])
        verification_reasons = list(
            (flag or {}).get("verification_reasons") or []
        )
        reasons = risk_reasons + [
            reason for reason in verification_reasons
            if reason not in risk_reasons
        ]

        price_risk = (flag or {}).get("price_risk") or {}
        price_status = price_risk.get("status", "UNASSESSED")
        price_severity = price_risk.get("severity", "UNKNOWN")
        price_review = (
            price_status == "ASSESSED"
            and price_severity in {"REVIEW", "HIGH"}
        )

        if price_review:
            # Price deterioration is a review signal, not an automatic trade instruction.
            status = "REVIEW_REQUIRED"
            severity = price_severity
            confidence = "MEDIUM"
            action = (
                "INVESTIGATE_BEFORE_ENTRY"
                if ticker in buy_new_tickers
                else "REVIEW_EXISTING_HOLDING"
            )
            reasons.extend(
                reason for reason in (price_risk.get("reasons") or [])
                if reason not in reasons
            )
            if not evidence_available:
                reasons.append(
                    "Company-level risk remains incomplete because usable "
                    "market-intelligence evidence is unavailable."
                )
        elif not evidence_available:
            status = "ASSESSMENT_INCOMPLETE"
            severity = "UNKNOWN"
            confidence = "LOW"

            if is_etf:
                action = "REVIEW_ETF_LOOKTHROUGH"
                reasons.append(
                    "ETF underlying holdings and look-through sector/country "
                    "exposures have not been assessed. This is not a company-level "
                    "risk assessment."
                )
            else:
                action = (
                    "COMPLETE_RISK_REVIEW_BEFORE_ENTRY"
                    if ticker in buy_new_tickers
                    else "REVIEW_MISSING_RISK_DATA"
                )
                if not reasons:
                    reasons = [
                        "No usable market-intelligence record is available; "
                        "risk is unassessed."
                    ]
        elif flag and flag.get("review_required"):
            status = "REVIEW_REQUIRED"
            severity = flag.get("severity", "REVIEW")
            confidence = "MEDIUM"
            action = (
                "INVESTIGATE_BEFORE_ENTRY"
                if ticker in buy_new_tickers
                else "REVIEW_EXISTING_HOLDING"
            )
        elif risk_reasons:
            status = "MONITOR_AND_VERIFY"
            severity = (
                flag.get("severity", "NOT_FULLY_ASSESSED")
                if flag else "NOT_FULLY_ASSESSED"
            )
            confidence = "LOW"
            action = "VERIFY_EVIDENCE_AND_MONITOR"
        else:
            status = "NO_ADVERSE_FLAG_IN_CHECKED_FIELDS"
            severity = "NOT_FULLY_ASSESSED"
            confidence = "LOW"
            action = "CONTINUE_STANDARD_MONITORING"

            if not risk_reasons:
                reasons.insert(
                    0,
                    "No adverse flag in the limited fields checked; "
                    "this is not a comprehensive risk clearance."
                )

        position = current_positions.get(ticker, {})
        decision = _normalise_text(
            decision_row.get("Final Decision", decision_row.get("Action", decision_row.get("Recommendation", decision_row.get("Decision", ""))))
        )
        assessment["individual_stock_assessments"].append({
            "ticker": ticker,
            "portfolio_roles": ", ".join(roles),
            "final_decision": decision,
            "current_value": round(safe_float(position.get("value", 0)), 2),
            "risk_status": status,
            "risk_severity": severity,
            "recommended_action": action,
            "reason": "; ".join(str(reason) for reason in reasons),
            "evidence_available": evidence_available,
            "evidence_quality": evidence_quality,
            "evidence_scope": "Existing market-intelligence fields only; macro, correlated-theme and comprehensive company risk are not assessed here.",
            "confidence": confidence,
            "advisory_only": True,
        })

    for transaction in transaction_rows:
        source_ticker = clean_ticker(
            transaction.get("Source Ticker", "")
        )
        destination_ticker = clean_ticker(
            transaction.get("Destination Ticker", "")
        )

        amount = safe_float(
            transaction.get(
                "Reallocated Capital",
                transaction.get("Released Capital", 0),
            )
        )

        if source_ticker in cash_tickers:
            source_ticker = ""
        if destination_ticker in cash_tickers:
            destination_ticker = ""

        if not source_ticker and not destination_ticker:
            continue

        source_flag = flags_by_ticker.get(source_ticker)
        destination_flag = flags_by_ticker.get(destination_ticker)

        review_reasons = []
        assessment_required_reasons = []

        for role, ticker, flag in (
            ("Funding source", source_ticker, source_flag),
            ("Destination", destination_ticker, destination_flag),
        ):
            if not ticker:
                continue

            if flag is None:
                assessment_required_reasons.append(
                    f"{role} {ticker} has no company-risk assessment record."
                )
                continue

            price_risk = flag.get("price_risk") or {}
            price_severity = price_risk.get("severity")
            if (
                price_risk.get("status") == "ASSESSED"
                and price_severity in {"REVIEW", "HIGH"}
            ):
                price_reasons = price_risk.get("reasons") or []
                detail = "; ".join(str(reason) for reason in price_reasons)
                review_reasons.append(
                    f"{role} {ticker} has {price_severity} historical "
                    f"price-deterioration risk"
                    + (f": {detail}" if detail else ".")
                )

            if flag.get("review_required"):
                review_reasons.append(
                    f"{role} {ticker} has a company-risk review flag."
                )
            elif flag.get("severity") == "UNKNOWN":
                assessment_required_reasons.append(
                    f"{role} {ticker} company-risk severity is UNKNOWN; "
                    "further company-risk assessment is required."
                )

        review = {
            "source_ticker": source_ticker or None,
            "destination_ticker": destination_ticker or None,
            "reallocated_capital": round(amount, 2),
            "review_required": bool(
                review_reasons or assessment_required_reasons
            ),
            "assessment_status": (
                "REVIEW"
                if review_reasons
                else "ASSESSMENT_REQUIRED"
                if assessment_required_reasons
                else "NO_FLAGGED_ISSUE"
            ),
            "reasons": review_reasons + assessment_required_reasons,
            "advisory_only": True,
        }

        assessment["transaction_risk_reviews"].append(review)

        if review_reasons or assessment_required_reasons:
            is_review = bool(review_reasons)

            assessment["recommendations"].append({
                "action": (
                    "REVIEW_PROPOSED_TRANSACTION"
                    if is_review
                    else "ASSESS_TRANSACTION_RISK"
                ),
                "subject": (
                    f"{source_ticker or 'CASH'} -> "
                    f"{destination_ticker or 'CASH'}"
                ),
                "reason": "; ".join(
                    review_reasons + assessment_required_reasons
                ),
                "confidence": "MEDIUM",
                "evidence_type": (
                    "TRANSACTION_LINKED_COMPANY_RISK"
                    if is_review
                    else "TRANSACTION_RISK_ASSESSMENT_GAP"
                ),
                "reallocated_capital": round(amount, 2),
                "advisory_only": True,
            })

    # --------------------------------------------------------
    # MACRO STRESS SCENARIOS — PORTFOLIO TRANSMISSION (SHADOW)
    # --------------------------------------------------------
    # Sector exposure is a review proxy, not a measured beta or loss forecast.
    _scenario_definitions = {
        "GROWTH_SLOWDOWN": {
            "scenario": "Growth slowdown / recession",
            "channels": "Weaker demand, earnings pressure and lower risk appetite",
            "sectors": {"FINANCIAL SERVICES", "CONSUMER CYCLICAL", "CONSUMER DISCRETIONARY", "INDUSTRIALS", "MATERIALS", "ENERGY", "REAL ESTATE"},
            "indicators": {"S&P 500", "Nasdaq-100 ETF", "Credit-risk appetite proxy"},
        },
        "INFLATION_ENERGY_SHOCK": {
            "scenario": "Renewed inflation / energy shock",
            "channels": "Higher energy/input costs and potential margin pressure",
            "sectors": {"ENERGY", "MATERIALS", "INDUSTRIALS", "CONSUMER CYCLICAL", "CONSUMER DISCRETIONARY", "CONSUMER DEFENSIVE", "UTILITIES"},
            "indicators": {"Crude oil price change"},
        },
        "INTEREST_RATE_SHOCK": {
            "scenario": "Interest-rate shock",
            "channels": "Higher discount rates, financing costs and valuation pressure",
            "sectors": {"TECHNOLOGY", "COMMUNICATION SERVICES", "CONSUMER CYCLICAL", "CONSUMER DISCRETIONARY", "REAL ESTATE", "UTILITIES"},
            "indicators": {"US 10-year Treasury yield change"},
        },
        "CREDIT_LIQUIDITY_STRESS": {
            "scenario": "Credit and liquidity stress",
            "channels": "Tighter financing, refinancing risk and correlated drawdowns",
            "sectors": {"FINANCIAL SERVICES", "REAL ESTATE", "CONSUMER CYCLICAL", "CONSUMER DISCRETIONARY", "INDUSTRIALS"},
            "indicators": {"Credit-risk appetite proxy", "VIX"},
        },
        "GEOPOLITICAL_TRADE_SHOCK": {
            "scenario": "Geopolitical / trade shock",
            "channels": "Trade restrictions, supply disruption and country/industry-specific costs",
            "sectors": {"ENERGY", "MATERIALS", "INDUSTRIALS", "TECHNOLOGY", "CONSUMER DEFENSIVE"},
            "indicators": set(),
        },
    }
    _macro_by_name = {
        item.get("Indicator"): item
        for item in assessment.get("macro_risk_assessment", {}).get("indicators", [])
    }
    _market_by_name = {
        item.get("Benchmark"): item
        for item in assessment.get("market_stress_indicators", [])
    }
    _risk_statuses = {"HIGH RISK SIGNAL", "ELEVATED RISK SIGNAL", "HIGH STRESS", "ELEVATED STRESS"}
    _clear_statuses = {"NO CONFIGURED THRESHOLD BREACH", "NO PROVISIONAL THRESHOLD BREACH", "NO VIX THRESHOLD BREACH"}

    for _scenario_id, _definition in _scenario_definitions.items():
        _evidence = []
        for _name in sorted(_definition["indicators"]):
            _indicator = _macro_by_name.get(_name) or _market_by_name.get(_name)
            if _indicator:
                _evidence.append({
                    "indicator": _name,
                    "status": _indicator.get("Status", "UNASSESSED"),
                    "observation_date": _indicator.get("Observation Date", _indicator.get("Latest Observation")),
                    "value": _indicator.get("Value", _indicator.get("VIX Level")),
                    "evidence": _indicator.get("Evidence", ""),
                })
        _statuses = [str(item.get("status", "UNASSESSED")).upper() for item in _evidence]
        if _scenario_id == "GEOPOLITICAL_TRADE_SHOCK":
            _status = "UNASSESSED"
            _status_reason = "No validated geopolitical/trade trigger is integrated; headlines alone are not treated as confirmed risk evidence."
        elif any(value in _risk_statuses for value in _statuses):
            _status = "SIGNAL_DETECTED"
            _status_reason = "At least one linked market/macro proxy breached a provisional review threshold."
        elif (
            len(_evidence) == len(_definition["indicators"])
            and _statuses
            and all(value in _clear_statuses for value in _statuses)
        ):
            _status = "NO_CONFIGURED_TRIGGER"
            _status_reason = "All configured linked proxies were assessed without a configured threshold breach; this does not rule out the scenario."
        else:
            _status = "UNASSESSED"
            _status_reason = "Linked indicators are missing, stale or not assessed; missing data is not low risk."

        _current_rows, _proposed_rows = [], []
        _current_value = _proposed_value = 0.0
        _current_unmapped = _proposed_unmapped = 0.0
        for _ticker, _position in current_positions.items():
            _value = max(0.0, safe_float(_position.get("value", 0)))
            _sector = _normalise_economic_sector(_position.get("sector")).upper()
            _mapped = _sector in _definition["sectors"] and str(_position.get("asset_type", "")).upper() != "ETF"
            if _mapped:
                _current_value += _value
                _current_rows.append({"ticker": _ticker, "sector": _position.get("sector"), "value": round(_value, 2)})
            elif not _sector or str(_position.get("asset_type", "")).upper() == "ETF":
                _current_unmapped += _value
        for _ticker, _position in proposed_positions.items():
            _value = max(0.0, safe_float(_position.get("value", 0)))
            _sector = _normalise_economic_sector(_position.get("sector")).upper()
            _mapped = _sector in _definition["sectors"] and str(_position.get("asset_type", "")).upper() != "ETF"
            if _mapped:
                _proposed_value += _value
                _proposed_rows.append({"ticker": _ticker, "sector": _position.get("sector"), "value": round(_value, 2)})
            elif not _sector or str(_position.get("asset_type", "")).upper() == "ETF":
                _proposed_unmapped += _value
        _current_pct = 100 * _current_value / current_holdings_value if current_holdings_value > 0 else None
        _proposed_pct = 100 * _proposed_value / proposed_holdings_value if proposed_holdings_value > 0 else None
        _current_rows.sort(key=lambda item: item["value"], reverse=True)
        _proposed_rows.sort(key=lambda item: item["value"], reverse=True)
        assessment["macro_stress_scenarios"].append({
            "scenario_id": _scenario_id,
            "scenario": _definition["scenario"],
            "status": _status,
            "transmission_channels": _definition["channels"],
            "current_exposure_value": round(_current_value, 2),
            "current_exposure_percent_of_holdings": round(_current_pct, 2) if _current_pct is not None else None,
            "proposed_exposure_value": round(_proposed_value, 2),
            "proposed_exposure_percent_of_holdings": round(_proposed_pct, 2) if _proposed_pct is not None else None,
            "change_in_exposure_value": round(_proposed_value - _current_value, 2),
            "change_in_exposure_percentage_points": round(_proposed_pct - _current_pct, 2) if _proposed_pct is not None and _current_pct is not None else None,
            "current_unmapped_or_etf_value": round(_current_unmapped, 2),
            "proposed_unmapped_or_etf_value": round(_proposed_unmapped, 2),
            "current_exposed_holdings": _current_rows,
            "proposed_exposed_holdings": _proposed_rows,
            "trigger_evidence": _evidence,
            "status_reason": _status_reason,
            "confidence": "LOW — SECTOR-BASED EXPOSURE PROXY; NOT A LOSS FORECAST",
            "advisory_only": True,
        })
        if _status == "SIGNAL_DETECTED" and (_current_value > 0 or _proposed_value > 0):
            assessment["recommendations"].append({
                "Priority": "REVIEW",
                "Recommendation": (
                    f"Review portfolio and proposed-transaction exposure to "
                    f"the {_definition['scenario'].lower()} scenario."
                ),
                "Evidence": _status_reason + " " + "; ".join(
                    item.get("evidence", "") for item in _evidence if item.get("evidence")
                ),
                "Scenario": _scenario_id,
                "Current Exposure Value": round(_current_value, 2),
                "Proposed Exposure Value": round(_proposed_value, 2),
                "Exposure Change Value": round(_proposed_value - _current_value, 2),
                "Governance": "ADVISORY ONLY — NO AUTOMATIC DECISION CHANGE",
            })
    assessment["data_quality"]["macro_stress_scenarios_built"] = bool(assessment["macro_stress_scenarios"])
    assessment["data_quality"]["macro_stress_scenarios_with_exposure"] = sum(
        bool(item.get("current_exposure_value") or item.get("proposed_exposure_value"))
        for item in assessment["macro_stress_scenarios"]
    )

    # --------------------------------------------------------
    # EXPLICIT UNASSESSED RISKS
    # --------------------------------------------------------

    if not assessment["data_quality"]["sector_country_classification_available"]:
        assessment["limitations"].append(
            "Sector and country classifications are incomplete or unavailable; "
            "concentration coverage is limited."
        )

    if not transaction_rows:
        assessment["limitations"].append(
            "No proposed transactions were supplied; transaction-specific "
            "risk reviews could not be performed."
        )

    assessment["limitations"].append(
        "Proposed sector and country exposures are estimates derived from the "
        "current holdings and proposed transaction amounts. They are not live-price "
        "post-trade valuations and must be validated against the final trade plan."
    )
    assessment["limitations"].append(
        "The portfolio-value denominator is supplied by the upstream portfolio summary. "
        "Any cash balance embedded in that summary is not assigned to a security sector; "
        "external cash allocated in proposed transactions is added to the proposed denominator."
    )

    assessment["limitations"].append(
        "Correlated investment themes, including AI infrastructure and "
        "semiconductors, remain unassessed without explicit theme mappings."
    )

    assessment["limitations"].append(
        "Macro risk is assessed only through the cache-only proxy screen when "
        "enough current observations are available; this is not a full macro model. "
        "Historical pre-purchase macro warnings remain unassessed without purchase "
        "dates and point-in-time macro snapshots."
    )

    # --------------------------------------------------------
    # FINANCIAL STATEMENT EVIDENCE INVENTORY
    #
    # Availability, periods and provenance only.
    # No resilience ratios or risk thresholds are inferred.
    # --------------------------------------------------------

    def _financial_period_map(statement_rows):
        period_rows = {}
        invalid_period_rows = 0

        if not isinstance(statement_rows, list):
            return {}, invalid_period_rows, []

        for statement_row in statement_rows:
            if not isinstance(statement_row, dict):
                invalid_period_rows += 1
                continue

            period_value = statement_row.get("period_end")
            period_text = (
                str(period_value).strip()
                if period_value is not None
                else ""
            )
            if period_text.upper() in {
                "", "UNKNOWN", "N/A", "NA", "NONE", "NULL", "NAN"
            }:
                period_text = ""

            period_date = pd.to_datetime(
                period_text,
                format="%Y-%m-%d",
                errors="coerce",
            )

            if pd.isna(period_date):
                invalid_period_rows += 1
                continue

            period_end = period_date.strftime("%Y-%m-%d")

            period_rows.setdefault(
                period_end, []
            ).append(statement_row)

        duplicate_periods = sorted(
            period_end
            for period_end, period_records in period_rows.items()
            if len(period_records) > 1
        )

        duplicate_period_set = set(duplicate_periods)

        # Exclude all records for duplicated periods.
        period_map = {
            period_end: period_records[0]
            for period_end, period_records in period_rows.items()
            if period_end not in duplicate_period_set
        }

        return (
            period_map,
            invalid_period_rows,
            duplicate_periods,
        )

    statement_mapping = (
        financial_statements_by_ticker
        if isinstance(financial_statements_by_ticker, dict)
        else {}
    )

    statement_records_with_data = 0

    statement_definitions = {
        "balance_sheet": "Balance Sheet",
        "income_statement": "Income Statement",
        "cash_flow": "Cash Flow",
    }

    for statement_ticker, statement_record in sorted(
        statement_mapping.items()
    ):

        if not isinstance(statement_record, dict):
            statement_record = {}

        annual_statements = statement_record.get(
            "Annual",
            {}
        )

        if not isinstance(annual_statements, dict):
            annual_statements = {}

        statement_periods = {}
        statement_row_counts = {}
        statement_period_validation = {}
        statement_period_maps = {}

        available_statement_count = 0

        for statement_key, statement_label in (
            statement_definitions.items()
        ):

            statement_rows = annual_statements.get(
                statement_key,
                []
            )

            if not isinstance(statement_rows, list):
                statement_rows = []

            if statement_rows:
                available_statement_count += 1

            statement_row_counts[statement_label] = len(
                statement_rows
            )

            (
                period_map,
                invalid_period_rows,
                duplicate_periods,
            ) = _financial_period_map(statement_rows)

            statement_period_maps[statement_key] = period_map

            statement_periods[statement_label] = sorted(
                period_map.keys(),
                reverse=True,
            )

            statement_period_validation[statement_label] = {
                "Invalid Period Rows": invalid_period_rows,
                "Duplicate Period Count": len(duplicate_periods),
                "Duplicate Periods": duplicate_periods,
                "Usable Period Count": len(period_map),
            }

        statement_period_sets = [
            set(statement_period_maps[key])
            for key in statement_definitions
        ]

        common_periods = (
            set.intersection(*statement_period_sets)
            if len(statement_period_sets) == 3
            else set()
        )

        all_periods_aligned = (
            len(statement_period_sets) == 3
            and all(statement_period_sets)
            and all(
                period_set == statement_period_sets[0]
                for period_set in statement_period_sets[1:]
            )
        )

        has_period_quality_issues = any(
            item["Invalid Period Rows"] > 0
            or item["Duplicate Period Count"] > 0
            for item in statement_period_validation.values()
        )

        if all_periods_aligned and not has_period_quality_issues:
            period_alignment_status = "ALIGNED"
        elif common_periods:
            period_alignment_status = (
                "PARTIAL — PERIOD COVERAGE OR DATA QUALITY ISSUES"
            )
        else:
            period_alignment_status = (
                "UNAVAILABLE — NO COMMON VALID PERIOD"
            )

        evidence_status = (
            "AVAILABLE"
            if available_statement_count == 3
            else "PARTIAL"
            if available_statement_count > 0
            else "UNAVAILABLE"
        )

        if available_statement_count > 0:
            statement_records_with_data += 1

        assessment["financial_resilience_evidence"].append({
            "Ticker": str(statement_ticker).strip().upper(),
            "Evidence Status": evidence_status,
            "Source": statement_record.get("Source"),
            "Retrieved At": statement_record.get("Retrieved At"),
            "Statement Periods": statement_periods,
            "Statement Row Counts": statement_row_counts,
            "Statement Period Validation": statement_period_validation,
            "Common Valid Periods": sorted(
                common_periods,
                reverse=True,
            ),
            "Common Valid Period Count": len(common_periods),
            "Period Alignment Status": period_alignment_status,
            "Ingestion Period Validation": statement_record.get(
                "Statement Period Validation",
                {},
            ),
            "Available Statement Types": available_statement_count,
            "Errors": statement_record.get("Errors", []),
            "Assessment Scope": (
                "Annual statement evidence inventory only; "
                "financial-resilience metrics have not yet been calculated."
            ),
            "Advisory Only": True,
        })

    assessment["data_quality"][
        "financial_statements_received"
    ] = len(statement_mapping)

    assessment["data_quality"][
        "financial_statements_with_data"
    ] = statement_records_with_data

    assessment["data_quality"][
        "financial_statements_unavailable"
    ] = (
        len(statement_mapping)
        - statement_records_with_data
    )

    assessment["data_quality"][
        "financial_statement_evidence_available"
    ] = statement_records_with_data > 0

    assessment["limitations"].append(
        "Financial statement inventory records source availability, "
        "periods and provenance. Separate SHADOW metrics are provided "
        "for eligible operating companies only; specialist and "
        "unverified business types remain unassessed. No validated "
        "risk thresholds or composite resilience score are applied."
    )


    # --------------------------------------------------------
    # SHADOW FINANCIAL RESILIENCE METRICS
    #
    # Exact fiscal-period joins across the three annual statements.
    # Operating-company framework only.
    # Descriptive metrics; no composite score or production impact.
    # --------------------------------------------------------

    import math

    assessment.setdefault("financial_resilience_metrics", [])

    _financial_classification_rows = {}

    for _source_row in list(rows) + list(intelligence_rows):
        if not isinstance(_source_row, dict):
            continue

        _source_ticker = clean_ticker(
            _source_row.get(
                "Ticker",
                _source_row.get("ticker", "")
            )
        )

        if _source_ticker:
            _financial_classification_rows.setdefault(
                _source_ticker, []
            ).append(_source_row)

    def _financial_text(value):
        value = str(value or "").strip()
        if value.upper() in {
            "", "UNKNOWN", "N/A", "NA", "NONE", "NULL", "NAN"
        }:
            return ""
        return value

    def _financial_number(record, *field_names):
        if not isinstance(record, dict):
            return None

        for field_name in field_names:
            if field_name not in record:
                continue

            value = record.get(field_name)

            if value is None or isinstance(value, bool):
                continue

            try:
                number = float(value)
            except (TypeError, ValueError, OverflowError):
                continue

            if math.isfinite(number):
                return number

        return None

    def _financial_business_classification(ticker, statement_record):
        _metadata = metadata_by_ticker.get(ticker, {})
        if not isinstance(_metadata, dict):
            _metadata = {}

        _sector = _financial_text(_metadata.get("sector"))
        _industry = _financial_text(_metadata.get("industry"))
        _company_name = _financial_text(
            statement_record.get("Name")
            if isinstance(statement_record, dict)
            else ""
        )

        for _source_row in _financial_classification_rows.get(
            ticker, []
        ):
            if not _sector:
                _sector = _financial_text(
                    _source_row.get(
                        "Sector",
                        _source_row.get("sector")
                    )
                )

            if not _industry:
                _industry = _financial_text(
                    _source_row.get(
                        "Industry",
                        _source_row.get("industry")
                    )
                )

            if not _company_name:
                _company_name = _financial_text(
                    _source_row.get(
                        "Company Name",
                        _source_row.get(
                            "Name",
                            _source_row.get("Security Name", "")
                        )
                    )
                )

        _sector_upper = _sector.upper()
        _industry_upper = _industry.upper()
        _name_upper = _company_name.upper()
        _classification_text = (
            _industry_upper + " " + _name_upper
        )

        if any(term in _classification_text for term in (
            "BANK",
            "BANKING",
            "SAVINGS INSTITUTION",
        )):
            _business_class = "BANK"

        elif any(term in _classification_text for term in (
            "REAL ESTATE INVESTMENT TRUST",
            "REIT",
        )):
            _business_class = "REIT"

        elif any(term in _classification_text for term in (
            "MASTER LIMITED PARTNERSHIP",
            "LIMITED PARTNERSHIP",
            "MLP",
        )):
            _business_class = "MLP / PARTNERSHIP"

        elif any(term in _classification_text for term in (
            "MIDSTREAM",
            "PIPELINE",
            "PIPELINES",
            "GAS TRANSMISSION",
            "OIL AND GAS STORAGE",
            "OIL & GAS STORAGE",
            "OIL AND GAS TRANSPORTATION",
            "OIL & GAS TRANSPORTATION",
        )):
            _business_class = "MIDSTREAM SPECIALIST"

        elif any(term in _classification_text for term in (
            "MARINE SHIPPING",
            "TANKER",
            "LNG SHIPPING",
            "LNG TRANSPORTATION",
        )):
            _business_class = "SHIPPING SPECIALIST"

        elif any(term in _sector_upper for term in (
            "FINANCIAL SERVICES",
            "FINANCIALS",
        )):
            _business_class = "FINANCIAL NON-BANK"

        elif "REAL ESTATE" in _sector_upper:
            _business_class = "REAL ESTATE SPECIALIST"

        elif not _sector or not _industry:
            _business_class = "BUSINESS TYPE UNVERIFIED"

        else:
            _business_class = "OPERATING COMPANY"

        _classification_evidence = (
            f"Sector={_sector or 'UNAVAILABLE'}; "
            f"Industry={_industry or 'UNAVAILABLE'}; "
            f"Name={_company_name or 'UNAVAILABLE'}"
        )

        return _business_class, _classification_evidence

    _specialist_business_classes = {
        "BANK",
        "FINANCIAL NON-BANK",
        "REIT",
        "MLP / PARTNERSHIP",
        "MIDSTREAM SPECIALIST",
        "SHIPPING SPECIALIST",
        "REAL ESTATE SPECIALIST",
    }

    _financial_period_count = 0
    _financial_ticker_count = 0
    _financial_operating_tickers = set()
    _financial_excluded_tickers = set()
    _financial_unverified_tickers = set()

    for _statement_ticker, _statement_record in sorted(
        statement_mapping.items()
    ):
        _ticker = clean_ticker(_statement_ticker)

        if not _ticker or not isinstance(_statement_record, dict):
            continue

        _annual = _statement_record.get("Annual", {})
        if not isinstance(_annual, dict):
            continue

        (
            _balance_rows,
            _balance_sheet_invalid_period_rows,
            _balance_sheet_duplicate_periods,
        ) = _financial_period_map(
            _annual.get("balance_sheet", [])
        )
        (
            _income_rows,
            _income_statement_invalid_period_rows,
            _income_statement_duplicate_periods,
        ) = _financial_period_map(
            _annual.get("income_statement", [])
        )
        (
            _cash_flow_rows,
            _cash_flow_invalid_period_rows,
            _cash_flow_duplicate_periods,
        ) = _financial_period_map(
            _annual.get("cash_flow", [])
        )

        # Never join different fiscal periods.
        _common_periods = sorted(
            set(_balance_rows)
            & set(_income_rows)
            & set(_cash_flow_rows),
            reverse=True,
        )

        _business_class, _classification_evidence = (
            _financial_business_classification(
                _ticker,
                _statement_record,
            )
        )

        if _business_class == "OPERATING COMPANY":
            _financial_operating_tickers.add(_ticker)
        elif _business_class == "BUSINESS TYPE UNVERIFIED":
            _financial_unverified_tickers.add(_ticker)
        else:
            _financial_excluded_tickers.add(_ticker)

        if _business_class != "OPERATING COMPANY":
            continue

        for _period in _common_periods:
            _balance = _balance_rows[_period]
            _income = _income_rows[_period]
            _cash_flow = _cash_flow_rows[_period]

            # Use total revenue where supplied; Revenue is the
            # alternative provider label. Do not substitute
            # Operating Revenue.
            _revenue = _financial_number(
                _income,
                "Total Revenue",
                "Revenue",
            )

            _revenue_field = (
                "Total Revenue"
                if _financial_number(_income, "Total Revenue") is not None
                else "Revenue"
                if _financial_number(_income, "Revenue") is not None
                else None
            )

            _fcf = _financial_number(
                _cash_flow,
                "Free Cash Flow",
            )

            # Reported Net Debt only. Missing is not treated as zero,
            # and no cash-based replacement is derived.
            _reported_net_debt = _financial_number(
                _balance,
                "Net Debt",
            )

            _ebitda = _financial_number(
                _income,
                "EBITDA",
            )

            _ebit = _financial_number(
                _income,
                "EBIT",
            )

            _interest_expense = _financial_number(
                _income,
                "Interest Expense",
            )

            _interest_income = _financial_number(
                _income,
                "Interest Income",
            )

            # Total Debt is reported as supplied. No attempt is made
            # to reconstruct it from current debt, long-term debt
            # or lease components.
            _total_debt = _financial_number(
                _balance,
                "Total Debt",
            )

            _fcf_margin = None
            if _fcf is not None and _revenue is not None and _revenue > 0:
                _fcf_margin = (_fcf / _revenue) * 100.0

            if _fcf is None or _revenue is None:
                _fcf_status = "NOT AVAILABLE — REQUIRED INPUT MISSING"
            elif _revenue <= 0:
                _fcf_status = "NOT MEANINGFUL — NON-POSITIVE REVENUE"
            else:
                _fcf_status = "AVAILABLE"

            _net_debt_ebitda = None
            if _reported_net_debt is None or _ebitda is None:
                _leverage_status = (
                    "NOT AVAILABLE — REPORTED INPUT MISSING"
                )
            elif _ebitda <= 0:
                _leverage_status = (
                    "NOT MEANINGFUL — NON-POSITIVE EBITDA"
                )
            else:
                _net_debt_ebitda = _reported_net_debt / _ebitda
                _leverage_status = "AVAILABLE"

            _gross_interest_coverage = None
            _interest_expense_revenue_pct = None

            if _ebit is None or _interest_expense is None:
                _interest_status = (
                    "NOT AVAILABLE — EBIT OR INTEREST EXPENSE MISSING"
                )
            elif _ebit <= 0:
                _interest_status = "NOT MEANINGFUL — NON-POSITIVE EBIT"
            elif _interest_expense <= 0:
                _interest_status = (
                    "NOT MEANINGFUL — NO POSITIVE GROSS INTEREST EXPENSE"
                )
            else:
                _gross_interest_coverage = _ebit / _interest_expense

                if _revenue is not None and _revenue > 0:
                    _interest_expense_revenue_pct = (
                        _interest_expense / _revenue
                    ) * 100.0

                if (
                    _interest_income is not None
                    and _interest_income >= _interest_expense
                ):
                    _interest_status = (
                        "AVAILABLE — NET INTEREST INCOME; "
                        "GROSS COVERAGE IS DESCRIPTIVE"
                    )
                else:
                    _interest_status = (
                        "AVAILABLE — GROSS COVERAGE; "
                        "REVIEW INTEREST EXPENSE MATERIALITY"
                    )

            _net_interest_income = None
            if (
                _interest_income is not None
                and _interest_expense is not None
            ):
                _net_interest_income = (
                    _interest_income - _interest_expense
                )

            _available_metric_count = sum(
                status == "AVAILABLE"
                or status.startswith("AVAILABLE —")
                for status in (
                    _fcf_status,
                    _leverage_status,
                    _interest_status,
                )
            )

            if _available_metric_count == 3:
                _overall_metric_status = "ASSESSED"
            elif _available_metric_count > 0:
                _overall_metric_status = "PARTIAL"
            else:
                _overall_metric_status = "NO USABLE METRICS"

            assessment["financial_resilience_metrics"].append({
                "Ticker": _ticker,
                "Period End": _period,
                "Business Classification": _business_class,
                "Business Classification Evidence": (
                    _classification_evidence
                ),
                "Revenue Field": _revenue_field,
                "Revenue": _revenue,
                "Free Cash Flow": _fcf,
                "FCF Margin %": _fcf_margin,
                "FCF Margin Status": _fcf_status,
                "Reported Net Debt": _reported_net_debt,
                "EBITDA": _ebitda,
                "Reported Net Debt / EBITDA (x)": _net_debt_ebitda,
                "Net Debt / EBITDA Status": _leverage_status,
                "Reported Total Debt": _total_debt,
                "EBIT": _ebit,
                "Interest Expense": _interest_expense,
                "Interest Income": _interest_income,
                "Net Interest Income (Income - Expense)": (
                    _net_interest_income
                ),
                "Interest Expense / Revenue %": (
                    _interest_expense_revenue_pct
                ),
                "Gross EBIT / Interest Expense (x)": (
                    _gross_interest_coverage
                ),
                "Interest Coverage Status": _interest_status,
                "Balance Sheet Invalid Period Rows": (
                    _balance_sheet_invalid_period_rows
                ),
                "Balance Sheet Duplicate Period Count": len(
                    _balance_sheet_duplicate_periods
                ),
                "Balance Sheet Duplicate Periods": (
                    _balance_sheet_duplicate_periods
                ),
                "Income Statement Invalid Period Rows": (
                    _income_statement_invalid_period_rows
                ),
                "Income Statement Duplicate Period Count": len(
                    _income_statement_duplicate_periods
                ),
                "Income Statement Duplicate Periods": (
                    _income_statement_duplicate_periods
                ),
                "Cash Flow Invalid Period Rows": (
                    _cash_flow_invalid_period_rows
                ),
                "Cash Flow Duplicate Period Count": len(
                    _cash_flow_duplicate_periods
                ),
                "Cash Flow Duplicate Periods": (
                    _cash_flow_duplicate_periods
                ),
                "Statement Period Data Quality Status": (
                    "ISSUES DETECTED"
                    if (
                        _balance_sheet_invalid_period_rows
                        or _balance_sheet_duplicate_periods
                        or _income_statement_invalid_period_rows
                        or _income_statement_duplicate_periods
                        or _cash_flow_invalid_period_rows
                        or _cash_flow_duplicate_periods
                    )
                    else "CLEAN"
                ),
                "Financial Metric Status": _overall_metric_status,
                "Advisory Only": True,
            })

            _financial_period_count += 1

    _financial_ticker_count = len({
        item["Ticker"]
        for item in assessment["financial_resilience_metrics"]
    })

    assessment["data_quality"][
        "financial_metric_operating_companies"
    ] = len(_financial_operating_tickers)

    assessment["data_quality"][
        "financial_metric_tickers_reported"
    ] = _financial_ticker_count

    assessment["data_quality"][
        "financial_metric_periods_reported"
    ] = _financial_period_count

    assessment["data_quality"][
        "financial_specialist_businesses_excluded"
    ] = len(_financial_excluded_tickers)

    assessment["data_quality"][
        "financial_business_types_unverified"
    ] = len(_financial_unverified_tickers)

    assessment["limitations"].append(
        "Financial resilience ratios are descriptive SHADOW measures "
        "for businesses classified as operating companies. Banks, "
        "financial non-banks, REITs, partnerships, midstream, shipping "
        "and real-estate specialists are excluded; unverified business "
        "types are not assessed."
    )

    assessment["limitations"].append(
        "Reported Net Debt is used without deriving a replacement. "
        "Reported Total Debt is displayed without reconstructing it "
        "from debt and lease components. Negative FCF margins and "
        "negative reported Net Debt are retained."
    )

    assessment["limitations"].append(
        "Gross EBIT / Interest Expense is shown with Interest Income "
        "and Net Interest Income. Gross coverage is descriptive and "
        "is not independently interpreted as debt-servicing strength."
    )

    assessment["limitations"].append(
        "Financial statement amounts remain in issuer reporting "
        "currency. No FX conversion, composite resilience score, "
        "production scoring or portfolio decision change is made."
    )

    return assessment

# ============================================================
# HOLD CHALLENGE / FUNDING HELPERS
# ============================================================

def get_hold_reduction_percent(
    source_score,
    destination_score,
    source_value=0.0,
    improves_diversification=False
):
    """
    Determine the maximum percentage of a HOLD position that may
    be recycled into a specific stronger governed destination.

    GOVERNANCE
    ----------

    HOLD remains the default.

    A HOLD position may be challenged only when:

        1. The source position is sufficiently weak.
        2. The destination has a material quality advantage.
        3. The proposed release is economically meaningful.
        4. The reduction remains proportionate.

    A HOLD is never automatically converted into a full SELL.
    """

    source_score = safe_float(source_score)
    destination_score = safe_float(destination_score)
    source_value = safe_float(source_value)

    advantage = (
        destination_score
        - source_score
    )

    # ========================================================
    # MATERIAL QUALITY ADVANTAGE
    # ========================================================

    if advantage < MIN_REALLOCATION_SCORE_ADVANTAGE:
        return 0.0

    # ========================================================
    # STRONG HOLD PROTECTION
    # ========================================================

    if source_score >= 70.0:
        return 0.0

    # ========================================================
    # DETERMINE PERMITTED REDUCTION
    # ========================================================

    permitted_percent = 0.0

    # --------------------------------------------------------
    # Moderate HOLD
    # --------------------------------------------------------

    if source_score >= 60.0:

        if advantage < 20.0:
            return 0.0

        permitted_percent = min(
            MAX_OPPORTUNITY_REDUCTION_PERCENT,
            15.0
        )

    # --------------------------------------------------------
    # Reasonable HOLD
    # --------------------------------------------------------

    elif source_score >= 50.0:

        if advantage < 20.0:
            return 0.0

        if improves_diversification:

            permitted_percent = min(
                MAX_OPPORTUNITY_REDUCTION_PERCENT,
                20.0
            )

        else:

            permitted_percent = min(
                MAX_OPPORTUNITY_REDUCTION_PERCENT,
                15.0
            )

    # --------------------------------------------------------
    # Weak HOLD
    # --------------------------------------------------------

    else:

        if advantage >= 25.0:

            if improves_diversification:

                permitted_percent = min(
                    MAX_OPPORTUNITY_REDUCTION_PERCENT,
                    25.0
                )

            else:

                permitted_percent = min(
                    MAX_OPPORTUNITY_REDUCTION_PERCENT,
                    20.0
                )

        elif advantage >= 20.0:

            permitted_percent = min(
                MAX_OPPORTUNITY_REDUCTION_PERCENT,
                15.0
            )

        else:
            return 0.0

    # ========================================================
    # MINIMUM MEANINGFUL RELEASE
    # ========================================================

    proposed_release = (
        source_value
        * permitted_percent
        / 100.0
    )

    if (
        source_value > 0
        and proposed_release
        < MIN_HOLD_CHALLENGE_RELEASE_VALUE
    ):
        return 0.0

    return round(
        permitted_percent,
        2
    )

def evaluate_hold_replacement(
    source_position,
    destinations,
    sector_exposure_percent
):
    """
    Evaluate whether a HOLD position should release capital for a
    specific governed replacement destination.

    GOVERNANCE PRINCIPLES
    ---------------------

    HOLD is the default portfolio decision.

    A lower Investment Score does not, by itself, justify reducing a
    HOLD position.

    Capital may only be released from a HOLD when there is an
    exceptional opportunity-cost case involving a specific governed
    destination.

    The replacement must demonstrate both:

    1. A substantial quality advantage, and
    2. A genuine portfolio benefit, preferably diversification or
       concentration reduction.

    This prevents unnecessary turnover and protects long-term
    compounding positions.

    ETFs are protected by is_hold_funding_eligible() before this
    function is called.

    Returns
    -------

    {
        "eligible": bool,
        "destination": dict or None,
        "reduction_percent": float,
        "reason": str
    }
    """

    # ========================================================
    # GOVERNANCE THRESHOLDS
    # ========================================================

    # A HOLD is protected unless the replacement opportunity is
    # materially exceptional.

    STRONG_HOLD_PROTECTION_SCORE = 65.0

    # Minimum absolute quality required for a replacement.
    MIN_DESTINATION_SCORE = 80.0

    # Minimum advantage required even when diversification improves.
    MIN_DIVERSIFYING_SCORE_ADVANTAGE = 35.0

    # Much higher threshold when there is no diversification benefit.
    MIN_EXCEPTIONAL_SCORE_ADVANTAGE = 45.0

    # Source sector must be meaningfully concentrated before
    # diversification alone can justify recycling a HOLD.
    MIN_SOURCE_SECTOR_CONCENTRATION = 30.0

    # The destination sector must provide a meaningful exposure
    # improvement.
    MIN_SECTOR_EXPOSURE_ADVANTAGE = 10.0

    # HOLD recycling should be conservative.
    MAX_HOLD_REDUCTION_PERCENT = 15.0

    # Avoid generating economically meaningless funding movements.
    MIN_HOLD_RELEASE_VALUE = 1.0

    # ========================================================
    # SOURCE POSITION
    # ========================================================

    source_score = safe_float(
        source_position.get(
            "Investment Score",
            0
        )
    )

    source_value = safe_float(
        source_position.get(
            "Current Value",
            0
        )
    )

    source_sector = str(
        source_position.get(
            "Sector",
            ""
        )
    ).strip()

    source_ticker = clean_ticker(
        source_position.get(
            "Ticker",
            ""
        )
    )

    if not source_ticker:

        return {
            "eligible": False,
            "destination": None,
            "reduction_percent": 0.0,
            "reason": (
                "HOLD replacement evaluation requires "
                "a valid source ticker"
            )
        }

    if source_value < MIN_HOLD_RELEASE_VALUE:

        return {
            "eligible": False,
            "destination": None,
            "reduction_percent": 0.0,
            "reason": (
                "HOLD position is too small to provide "
                "meaningful replacement capital"
            )
        }

    # ========================================================
    # PROTECT STRONG HOLDS
    # ========================================================

    if source_score >= STRONG_HOLD_PROTECTION_SCORE:

        return {
            "eligible": False,
            "destination": None,
            "reduction_percent": 0.0,
            "reason": (
                "HOLD position is sufficiently strong "
                "to remain protected"
            )
        }

    # ========================================================
    # SOURCE CONCENTRATION
    # ========================================================

    source_sector_exposure = safe_float(
        sector_exposure_percent.get(
            source_sector,
            0
        )
    )

    source_sector_concentrated = (
        source_sector_exposure
        >= MIN_SOURCE_SECTOR_CONCENTRATION
    )

    # ========================================================
    # EVALUATE GOVERNED DESTINATIONS
    # ========================================================

    best_candidate = None
    best_candidate_rank = None

    best_improves_diversification = False
    best_score_advantage = 0.0
    best_reduction_percent = 0.0
    best_destination_sector_exposure = 0.0

    for destination in destinations:

        destination_ticker = clean_ticker(
            destination.get(
                "Ticker",
                ""
            )
        )

        # ----------------------------------------------------
        # Never recycle a position into itself.
        # ----------------------------------------------------

        if (
            not destination_ticker
            or destination_ticker == source_ticker
        ):
            continue

        destination_score = safe_float(
            destination.get(
                "Investment Score",
                0
            )
        )

        destination_sector = str(
            destination.get(
                "Sector",
                ""
            )
        ).strip()

        destination_weight = safe_float(
            destination.get(
                "Allocation Weight",
                destination.get(
                    "Destination Priority",
                    0
                )
            )
        )

        score_advantage = (
            destination_score
            - source_score
        )

        # ====================================================
        # REPLACEMENT MUST BE HIGH QUALITY
        # ====================================================

        if destination_score < MIN_DESTINATION_SCORE:
            continue

        # ====================================================
        # SECTOR COMPARISON
        # ====================================================

        destination_sector_exposure = safe_float(
            sector_exposure_percent.get(
                destination_sector,
                0
            )
        )

        same_sector = (
            bool(source_sector)
            and bool(destination_sector)
            and source_sector.upper()
            == destination_sector.upper()
        )

        improves_diversification = False

        if not same_sector:

            if (
                source_sector_concentrated
                and source_sector_exposure
                >= (
                    destination_sector_exposure
                    + MIN_SECTOR_EXPOSURE_ADVANTAGE
                )
            ):

                improves_diversification = True

        # ====================================================
        # SAME-SECTOR PROTECTION
        # ====================================================

        # Do not churn a HOLD into another ticker in the same
        # sector. A score difference alone is not enough.

        if same_sector:
            continue

        # ====================================================
        # DESTINATION CONCENTRATION PROTECTION
        # ====================================================

        # Do not recycle capital into an already concentrated
        # sector.

        if destination_sector_exposure >= 40.0:
            continue

        # ====================================================
        # EXCEPTIONAL REPLACEMENT TEST
        # ====================================================

        if improves_diversification:

            if (
                score_advantage
                < MIN_DIVERSIFYING_SCORE_ADVANTAGE
            ):
                continue

        else:

            # Without diversification benefit, the replacement
            # must be exceptional.

            if (
                score_advantage
                < MIN_EXCEPTIONAL_SCORE_ADVANTAGE
            ):
                continue

        # ====================================================
        # DETERMINE CONSERVATIVE REDUCTION
        # ====================================================

        if improves_diversification:

            reduction_percent = 15.0

        else:

            reduction_percent = 10.0

        reduction_percent = min(
            reduction_percent,
            MAX_HOLD_REDUCTION_PERCENT
        )

        proposed_release_value = (
            source_value
            * reduction_percent
            / 100.0
        )

        if proposed_release_value < MIN_HOLD_RELEASE_VALUE:
            continue

        # ====================================================
        # RANK CANDIDATES
        #
        # Prefer:
        #
        # 1. Diversification improvement
        # 2. Higher score advantage
        # 3. Stronger allocation weight
        # ====================================================

        candidate_rank = (
            1 if improves_diversification else 0,
            score_advantage,
            destination_weight
        )

        if (
            best_candidate is None
            or candidate_rank > best_candidate_rank
        ):

            best_candidate = destination
            best_candidate_rank = candidate_rank

            best_improves_diversification = (
                improves_diversification
            )

            best_score_advantage = (
                score_advantage
            )

            best_reduction_percent = (
                reduction_percent
            )

            best_destination_sector_exposure = (
                destination_sector_exposure
            )

    # ========================================================
    # NO JUSTIFIED REPLACEMENT
    # ========================================================

    if best_candidate is None:

        return {
            "eligible": False,
            "destination": None,
            "reduction_percent": 0.0,
            "reason": (
                "HOLD retained because no exceptional "
                "portfolio-improving replacement was identified"
            )
        }

    # ========================================================
    # BUILD EXPLANATION
    # ========================================================

    destination_ticker = clean_ticker(
        best_candidate.get(
            "Ticker",
            ""
        )
    )

    if best_improves_diversification:

        reason = (
            f"HOLD position partially challenged by "
            f"{destination_ticker}: "
            f"{best_score_advantage:.1f}-point quality "
            f"advantage and meaningful diversification "
            f"improvement from "
            f"{source_sector_exposure:.1f}% to a sector "
            f"currently at "
            f"{best_destination_sector_exposure:.1f}% exposure"
        )

    else:

        reason = (
            f"HOLD position partially challenged only because "
            f"{destination_ticker} demonstrates an exceptional "
            f"{best_score_advantage:.1f}-point quality advantage"
        )

    return {

        "eligible": True,

        "destination": best_candidate,

        "reduction_percent": round(
            best_reduction_percent,
            2
        ),

        "reason": reason
    }
# ============================================================
# MAIN ENGINE
# ============================================================

def generate_portfolio_reallocation(
    final_portfolio_decisions,
    portfolio_value,
    min_reallocation_trade_value=1.0,
    market_intelligence=None,
    financial_statements_by_ticker=None,
):
    """
    Generate governed portfolio capital reallocation.

    GOVERNANCE PRINCIPLES
    ---------------------

    1. Explicit SELL decisions release capital.

    2. Explicit REDUCE decisions release the governed
       percentage of capital.

    3. HOLD remains the default.

    4. A HOLD may only release capital when
       evaluate_hold_replacement() identifies a specific,
       materially superior governed destination.

    5. HOLD funding is destination-specific and cannot
       subsequently be redirected elsewhere.

    6. ETFs are protected from automatic opportunity-based
       recycling through is_hold_funding_eligible().

    7. Assessment cash is discretionary and may support
       eligible destinations.

    8. SELL and REDUCE proceeds are discretionary capital.

    9. Destination allocation is calculated before funding
       transactions are generated.

    10. Position capacity and minimum meaningful trade
        values are respected.

    Returns
    -------

    {
        "reallocation": pandas.DataFrame,
        "summary": dict
    }
    """

    # ========================================================
    # NORMALISE INPUT
    # ========================================================

    if final_portfolio_decisions is None:

        return {
            "reallocation": pd.DataFrame(),
            "summary": {
                "Assessment Cash": 0.0,
                "Released From Holdings": 0.0,
                "Total Released": 0.0,
                "Total Reallocated": 0.0,
                "Unallocated Capital": 0.0,
                "Reconciliation Variance": 0.0,
                "Reconciliation Status": "NOT_RUN",
"Planned Destination Allocation": 0.0,
                "Actual Destination Allocation": 0.0,
                "Destination Allocation Variance": 0.0,
                "Destination Allocation Reconciliation": "NOT_RUN",
                "Exposure Denominator": 0.0,
                "Funding Sources": 0,
                "Destinations": 0
            },
            "market_risk_assessment": _build_market_risk_assessment(
                final_portfolio_decisions=final_portfolio_decisions,
                portfolio_value=portfolio_value,
                market_intelligence=market_intelligence,
                financial_statements_by_ticker=financial_statements_by_ticker,
            ),
        }

    if isinstance(
        final_portfolio_decisions,
        pd.DataFrame
    ):

        decisions_df = final_portfolio_decisions.copy()

    else:

        decisions_df = pd.DataFrame(
            final_portfolio_decisions
        )

    if decisions_df.empty:

        return {
            "reallocation": pd.DataFrame(),
            "summary": {
                "Assessment Cash": 0.0,
                "Released From Holdings": 0.0,
                "Total Released": 0.0,
                "Total Reallocated": 0.0,
                "Unallocated Capital": 0.0,
                "Reconciliation Variance": 0.0,
                "Reconciliation Status": "NOT_RUN",
"Planned Destination Allocation": 0.0,
                "Actual Destination Allocation": 0.0,
                "Destination Allocation Variance": 0.0,
                "Destination Allocation Reconciliation": "NOT_RUN",
                "Exposure Denominator": 0.0,
                "Funding Sources": 0,
                "Destinations": 0
            },
            "market_risk_assessment": _build_market_risk_assessment(
                final_portfolio_decisions=final_portfolio_decisions,
                portfolio_value=portfolio_value,
                market_intelligence=market_intelligence,
                financial_statements_by_ticker=financial_statements_by_ticker,
            ),
        }

    portfolio_value = safe_float(
        portfolio_value
    )

    # ========================================================
    # NORMALISE DECISIONS
    # ========================================================

    decisions = normalise_final_decisions(
        decisions_df
    )

    if decisions is None:
        decisions = []

    elif isinstance(decisions, pd.DataFrame):
        decisions = decisions.to_dict("records")

    if not decisions:
        return {
            "reallocation": pd.DataFrame(),
            "summary": {
                "Assessment Cash": 0.0,
                "Released From Holdings": 0.0,
                "Total Released": 0.0,
                "Total Reallocated": 0.0,
                "Unallocated Capital": 0.0,
                "Reconciliation Variance": 0.0,
                "Reconciliation Status": "NOT_RUN",
"Planned Destination Allocation": 0.0,
                "Actual Destination Allocation": 0.0,
                "Destination Allocation Variance": 0.0,
                "Destination Allocation Reconciliation": "NOT_RUN",
                "Exposure Denominator": 0.0,
                "Funding Sources": 0,
                "Destinations": 0
            },
            "market_risk_assessment": _build_market_risk_assessment(
                final_portfolio_decisions=final_portfolio_decisions,
                portfolio_value=portfolio_value,
                market_intelligence=market_intelligence,
                financial_statements_by_ticker=financial_statements_by_ticker,
            ),
        }
    # ========================================================
    # VALIDATE OWNED-POSITION UNIQUENESS
    # ========================================================

    # The reallocation engine uses one row per security for exposure,
    # funding and position-capacity calculations. Duplicate owned rows
    # make those calculations ambiguous, so fail closed rather than
    # silently double-counting or choosing one row.
    owned_rows_by_ticker = {}
    for row in decisions:
        ticker = clean_ticker(row.get("Ticker", ""))
        current_value = safe_float(
            row.get("Current Value", row.get("Market Value", 0))
        )
        owned = bool(row.get("Owned", current_value > 0))
        if ticker and ticker != "CASH" and owned and current_value > 0:
            owned_rows_by_ticker.setdefault(ticker, []).append(row)

    duplicate_owned_tickers = sorted(
        ticker
        for ticker, ticker_rows in owned_rows_by_ticker.items()
        if len(ticker_rows) > 1
    )

    if duplicate_owned_tickers:
        validation_summary = {
            "Assessment Cash": 0.0,
            "Released From Holdings": 0.0,
            "Total Released": 0.0,
            "Total Reallocated": 0.0,
            "Unallocated Capital": 0.0,
            "Reconciliation Variance": 0.0,
            "Reconciliation Status": "BLOCKED_DUPLICATE_OWNED_TICKERS",
            "Duplicate Owned Tickers": duplicate_owned_tickers,
            "Funding Sources": 0,
            "Destinations": 0,
        }
        return {
            "reallocation": pd.DataFrame(),
            "summary": validation_summary,
            "market_risk_assessment": _build_market_risk_assessment(
                final_portfolio_decisions=final_portfolio_decisions,
                portfolio_value=portfolio_value,
                market_intelligence=market_intelligence,
                financial_statements_by_ticker=financial_statements_by_ticker,
            ),
        }

    # ========================================================
    # BUILD CURRENT POSITIONS
    # ========================================================

    current_positions = []

    for row in decisions:

        ticker = clean_ticker(
            row.get(
                "Ticker",
                ""
            )
        )

        if not ticker:

            continue

        current_value = safe_float(
            row.get(
                "Current Value",
                row.get(
                    "Market Value",
                    0
                )
            )
        )

        owned = bool(
            row.get(
                "Owned",
                current_value > 0
            )
        )

        if not owned:

            continue

        final_decision = normalise_action(
            row.get(
                "Final Decision",
                row.get(
                    "Action",
                    ""
                )
            )
        )

        sector = str(
            row.get(
                "Sector",
                ""
            )
        ).strip()

        asset_type = str(
            row.get(
                "Asset Type",
                "STOCK"
            )
        ).strip().upper()

        score = safe_float(
            row.get(
                "Investment Score",
                0
            )
        )

        current_allocation_percent = 0.0

        if portfolio_value > 0:

            current_allocation_percent = (
                current_value
                / portfolio_value
                * 100.0
            )

        current_positions.append(
            {
                "Ticker": ticker,
                "Name": row.get(
                    "Name",
                    ticker
                ),
                "Current Value": current_value,
                "Current Quantity": safe_float(
                    row.get(
                        "Current Quantity",
                        row.get(
                            "Quantity",
                            0
                        )
                    )
                ),
                "Current Allocation %": round(
                    current_allocation_percent,
                    2
                ),
                "Sector": sector,
                "Asset Type": asset_type,
                "Country": str(
                    row.get(
                        "Country",
                        row.get(
                            "country",
                            ""
                        )
                    )
                ).strip(),
                "Final Decision": final_decision,
                "Investment Score": score,
                "Owned": True,
                "Funding Priority": get_funding_priority(
                    final_decision,
                    score,
                    True
                )
            }
        )

    # ========================================================
    # CALCULATE SECTOR EXPOSURE
    #
    # Sector/country percentages use the same owned-position population
    # as their numerators. portfolio_value remains the denominator for
    # position sizing and portfolio-level capacity limits.
    # ========================================================

    sector_values = {}

    for position in current_positions:

        sector = str(
            position.get(
                "Sector",
                ""
            ) or ""
        ).strip()

        current_value = safe_float(
            position.get(
                "Current Value",
                0
            )
        )

        sector_values[sector] = (
            sector_values.get(
                sector,
                0.0
            )
            + current_value
        )

    # Use the same owned-position population for the exposure denominator
    # and numerator. Keep portfolio_value for overall position-sizing rules.
    exposure_portfolio_value = round(
        sum(
            safe_float(position.get("Current Value", 0))
            for position in current_positions
            if safe_float(position.get("Current Value", 0)) > 0
        ),
        2,
    )

    sector_exposure_percent = {}

    if exposure_portfolio_value > 0:

        for sector, value in sector_values.items():

            sector_exposure_percent[sector] = round(
                value
                / exposure_portfolio_value
                * 100.0,
                2
            )

    # ========================================================
    # CALCULATE COUNTRY EXPOSURE
    #
    # Diagnostic only at this stage.
    # Do not use this as an additional allocation penalty yet.
    # ========================================================

    country_values = {}

    for position in current_positions:

        country = str(
            position.get(
                "Country",
                ""
            )
        ).strip()

        if not country:
            continue

        current_value = safe_float(
            position.get(
                "Current Value",
                0
            )
        )

        country_values[country] = (
            country_values.get(
                country,
                0.0
            )
            + current_value
        )

    country_exposure_percent = {}

    if exposure_portfolio_value > 0:

        for country, value in country_values.items():

            country_exposure_percent[country] = round(
                value
                / exposure_portfolio_value
                * 100.0,
                2
            )
    # ========================================================
    # BUILD DESTINATIONS
    # ========================================================

    destinations = []

    for row in decisions:

        ticker = clean_ticker(
            row.get(
                "Ticker",
                ""
            )
        )

        if not ticker:

            continue

        final_decision = normalise_action(
            row.get(
                "Final Decision",
                row.get(
                    "Action",
                    ""
                )
            )
        )

        # ----------------------------------------------------
        # Only genuine governed additions are destinations.
        # ----------------------------------------------------

        if final_decision not in (
            "BUY MORE",
            "BUY NEW"
        ):

            continue

        score = safe_float(
            row.get(
                "Investment Score",
                0
            )
        )

        if score < MIN_DESTINATION_SCORE:
            continue



        raw_risk_score = row.get(
            "Risk Score",
            row.get("risk_score", None)
        )

        risk_score = safe_float(raw_risk_score)

        # Zero is treated as unavailable because this pipeline may
        # use zero as its default when no risk score was supplied.
        risk_score_available = (
            raw_risk_score is not None
            and not pd.isna(raw_risk_score)
            and risk_score > 0
        )

        current_value = safe_float(
            row.get(
                "Current Value",
                row.get(
                    "Market Value",
                    0
                )
            )
        )

        owned = bool(
            row.get(
                "Owned",
                current_value > 0
            )
        )

        sector = str(
            row.get(
                "Sector",
                ""
            )
        ).strip()

        asset_type = str(
            row.get(
                "Asset Type",
                "STOCK"
            )
        ).strip().upper()

        destination_priority = get_destination_priority(
            final_decision,
            score,
            owned
        )

        position_capacity = get_position_capacity(
            current_value,
            portfolio_value
        )

        destinations.append(
            {
                "Ticker": ticker,
                "Name": row.get(
                    "Name",
                    ticker
                ),
                "Action": "ADD",
                "Investment Score": score,
                "Risk Score": risk_score,
                "Risk Score Available": risk_score_available,
                "Risk Score Status": (
                    "AVAILABLE"
                    if risk_score_available
                    else "UNKNOWN / NOT SCORED"
                ),
                "Destination Priority": (
                    destination_priority
                ),
                "Current Value": current_value,
                "Position Capacity": position_capacity,
                "Owned": owned,
                "Final Decision": final_decision,
                "Sector": sector,
                "Asset Type": asset_type,
                "Country": str(
                    row.get(
                        "Country",
                        row.get(
                            "country",
                            ""
                        )
                    )
                ).strip(),

                # ----------------------------------------------------
                # Preserve factual security metadata for the
                # deterministic structural-risk assessment.
                # ----------------------------------------------------
                "Structural Risk Metadata": {
                    "Country": row.get(
                        "Country",
                        row.get(
                            "country",
                            ""
                        )
                    ),
                    "Exchange": row.get(
                        "Exchange",
                        row.get(
                            "exchange",
                            ""
                        )
                    ),
                    "Quote Type": row.get(
                        "Quote Type",
                        row.get(
                            "quoteType",
                            ""
                        )
                    ),
                    "Name": row.get(
                        "Name",
                        ticker
                    )
                }
            }
        )

    destinations = sorted(
        destinations,
        key=lambda x: (
            -safe_float(
                x.get(
                    "Destination Priority",
                    0
                )
            ),
            -safe_float(
                x.get(
                    "Investment Score",
                    0
                )
            ),
            x.get(
                "Ticker",
                ""
            )
        )
    )

    # ========================================================
    # APPLY DESTINATION ALLOCATION WEIGHTS
    # ========================================================

    # ========================================================
    # APPLY DESTINATION ALLOCATION WEIGHTS
    # ========================================================

    eligible_destinations = []

    for destination in destinations:

        sector = destination.get(
            "Sector",
            ""
        )

        sector_key = str(sector or "").strip()

        sector_exposure_raw = sector_exposure_percent.get(
            sector_key
        )

        sector_exposure = (
            safe_float(sector_exposure_raw)
            if sector_exposure_raw is not None
            else None
        )

        country = str(
            destination.get(
                "Country",
                ""
            )
        ).strip()

        country_exposure = safe_float(
            country_exposure_percent.get(
                country,
                0
            )
        )

        country_present = bool(
            country
            and country in country_exposure_percent
        )

        if not country:
            portfolio_fit = "UNKNOWN"
        elif not country_present:
            portfolio_fit = "NEW COUNTRY"
        elif country_exposure >= 50.0:
            portfolio_fit = "HIGH COUNTRY CONCENTRATION"
        elif country_exposure >= 30.0:
            portfolio_fit = "MEANINGFUL COUNTRY CONCENTRATION"
        else:
            portfolio_fit = "DIVERSIFIED COUNTRY EXPOSURE"

        current_position_percent = 0.0

        if portfolio_value > 0:

            current_position_percent = (
                safe_float(
                    destination.get(
                        "Current Value",
                        0
                    )
                )
                / portfolio_value
                * 100.0
            )

        decision_multiplier = 1.0
        sector_multiplier = 1.0
        position_multiplier = 1.0
        risk_multiplier = 1.0

        risk_score = safe_float(
            destination.get("Risk Score", 0)
        )

        risk_score_available = bool(
            destination.get("Risk Score Available", False)
        )

        if risk_score_available:
            if risk_score >= 10.0:
                risk_multiplier = 1.0
            else:
                risk_multiplier = 0.70

        structural_risk = assess_structural_risk(
            destination.get(
                "Structural Risk Metadata",
                {}
            )
        )

        structural_risk_multiplier = safe_float(
            structural_risk.get(
                "Structural Risk Multiplier",
                1.0
            )
        )

        if current_position_percent >= 10.0:
            position_multiplier = 0.75

        # ----------------------------------------------------
        # Sector concentration is an allocation-capacity
        # constraint, not a destination-ranking penalty.
        # ----------------------------------------------------

        if (
            sector_exposure is not None
            and sector_exposure >= 40.0
        ):
            sector_multiplier = 0.65

        allocation_weight = (
            safe_float(
                destination.get(
                    "Destination Priority",
                    0
                )
            )
            * decision_multiplier
            * position_multiplier
            * risk_multiplier
            * structural_risk_multiplier
        )

        # ----------------------------------------------------
        # Calculate Allocation Capacity BEFORE eligibility.
        #
        # Position Capacity is the absolute position limit.
        # Sector concentration can reduce how much of that
        # capacity may be used in this reallocation cycle.
        # ----------------------------------------------------

        position_capacity = safe_float(
            destination.get(
                "Position Capacity",
                0
            )
        )

        allocation_capacity = round(
            position_capacity
            * sector_multiplier,
            2
        )

        destination_copy = destination.copy()

        destination_copy[
            "Allocation Weight"
        ] = round(
            allocation_weight,
            2
        )

        destination_copy["Sector Exposure %"] = (
            round(sector_exposure, 2)
            if sector_exposure is not None
            else None
        )

        destination_copy[
            "Country"
        ] = country

        destination_copy[
            "Country Exposure %"
        ] = round(
            country_exposure,
            2
        )

        destination_copy[
            "Portfolio Fit"
        ] = portfolio_fit

        destination_copy[
            "Current Position %"
        ] = round(
            current_position_percent,
            2
        )

        destination_copy[
            "Decision Multiplier"
        ] = decision_multiplier

        destination_copy[
            "Sector Multiplier"
        ] = sector_multiplier

        destination_copy[
            "Position Multiplier"
        ] = position_multiplier

        destination_copy[
            "Allocation Capacity"
        ] = allocation_capacity

        destination_copy[
            "Structural Risk"
        ] = structural_risk.get(
            "Structural Risk",
            "LOW"
        )

        destination_copy[
            "Structural Risk Multiplier"
        ] = structural_risk_multiplier

        destination_copy[
            "Structural Risk Reason"
        ] = structural_risk.get(
            "Structural Risk Reason",
            ""
        )

        # ----------------------------------------------------
        # Only destinations with meaningful usable capacity
        # enter the governed deployment population.
        # ----------------------------------------------------

        if (
            allocation_capacity
            >= min_reallocation_trade_value
        ):

            eligible_destinations.append(
                destination_copy
            )

    eligible_destination_lookup = {
        clean_ticker(
            destination.get(
                "Ticker",
                ""
            )
        ): destination
        for destination
        in eligible_destinations
    }

    # ========================================================
    # BUILD FUNDING CANDIDATES
    # ========================================================

    funding_candidates = []

    # --------------------------------------------------------
    # Assessment cash
    # --------------------------------------------------------

    if ASSESSMENT_CASH_CONTRIBUTION > 0:

        funding_candidates.append(
            {
                "Ticker": "ASSESSMENT CASH",
                "Name": (
                    "Assessment Cash Contribution"
                ),
                "Current Value": round(
                    ASSESSMENT_CASH_CONTRIBUTION,
                    2
                ),
                "Current Quantity": 0.0,
                "Current Allocation %": 0.0,
                "Sector": "Cash",
                "Asset Type": "CASH",
                "Final Decision": "CASH",
                "Investment Score": 0.0,
                "Funding Priority": 400.0,
                "Owned": False,
                "Funding Reason": (
                    "Assessment cash contribution"
                ),
                "Permitted Release %": 100.0,
                "Authorised Destination": ""
            }
        )

    # --------------------------------------------------------
    # Existing portfolio cash
    # --------------------------------------------------------

    actual_cash_balance = load_actual_cash_balance()

    if actual_cash_balance > 0:
        funding_candidates.append(
            {
                "Ticker": "CASH",
                "Name": "Existing Portfolio Cash",
                "Current Value": actual_cash_balance,
                "Current Quantity": 0.0,
                "Current Allocation %": 0.0,
                "Sector": "Cash",
                "Asset Type": "CASH",
                "Final Decision": "EXISTING CASH",
                "Investment Score": 0.0,
                "Funding Priority": 390.0,
                "Owned": False,
                "Funding Reason": "Existing cash balance from holdings_raw.csv",
                "Permitted Release %": 100.0,
                "Authorised Destination": "",
            }
        )

    # --------------------------------------------------------
    # Existing holdings
    # --------------------------------------------------------

    for position in current_positions:

        decision = normalise_action(
            position.get(
                "Final Decision",
                ""
            )
        )

        permitted_percent = 0.0
        funding_reason = ""
        authorised_destination = ""

        # ----------------------------------------------------
        # Explicit SELL
        # ----------------------------------------------------

        if decision == "SELL":

            permitted_percent = 100.0

            funding_reason = (
                "Explicit SELL decision"
            )

        # ----------------------------------------------------
        # Explicit REDUCE
        # ----------------------------------------------------

        elif decision.startswith("REDUCE"):

            if "100%" in decision:

                permitted_percent = 100.0

            elif "75%" in decision:

                permitted_percent = 75.0

            elif "50%" in decision:

                permitted_percent = 50.0

            else:

                permitted_percent = 25.0

            funding_reason = (
                "Explicit REDUCE decision"
            )

        # ----------------------------------------------------
        # HOLD
        #
        # Must have a specific justified replacement.
        # ----------------------------------------------------

        elif (
            decision == "HOLD"
            and is_hold_funding_eligible(
                position
            )
            and eligible_destinations
        ):

            replacement = evaluate_hold_replacement(
                position,
                eligible_destinations,
                sector_exposure_percent
            )

            if replacement.get(
                "eligible",
                False
            ):

                replacement_destination = (
                    replacement.get(
                        "destination"
                    )
                )

                replacement_ticker = clean_ticker(
                    replacement_destination.get(
                        "Ticker",
                        ""
                    )
                    if replacement_destination
                    else ""
                )

                reduction_percent = safe_float(
                    replacement.get(
                        "reduction_percent",
                        0
                    )
                )

                if (
                    replacement_ticker
                    and replacement_ticker
                    in eligible_destination_lookup
                    and reduction_percent > 0
                ):

                    permitted_percent = (
                        reduction_percent
                    )

                    authorised_destination = (
                        replacement_ticker
                    )

                    funding_reason = (
                        replacement.get(
                            "reason",
                            "HOLD challenged by specific "
                            "governed replacement"
                        )
                    )

        if permitted_percent <= 0:

            continue

        candidate = position.copy()

        candidate[
            "Permitted Release %"
        ] = round(
            permitted_percent,
            2
        )

        candidate[
            "Funding Reason"
        ] = funding_reason

        candidate[
            "Authorised Destination"
        ] = authorised_destination

        # Explicit governance ranks above HOLD challenges.

        if decision == "SELL":

            candidate[
                "Funding Priority"
            ] = (
                300.0
                + safe_float(
                    position.get(
                        "Funding Priority",
                        0
                    )
                ) % 100.0
            )

        elif decision.startswith("REDUCE"):

            candidate[
                "Funding Priority"
            ] = (
                200.0
                + safe_float(
                    position.get(
                        "Funding Priority",
                        0
                    )
                ) % 100.0
            )

        else:

            candidate[
                "Funding Priority"
            ] = (
                100.0
                + safe_float(
                    position.get(
                        "Funding Priority",
                        0
                    )
                ) % 100.0
            )

        funding_candidates.append(
            candidate
        )

    funding_candidates = sorted(
        funding_candidates,
        key=lambda x: (
            -safe_float(
                x.get(
                    "Funding Priority",
                    0
                )
            ),
            x.get(
                "Ticker",
                ""
            )
        )
    )

    # ========================================================
    # DEBUG OUTPUT
    # ========================================================

    print(
        "\nPORTFOLIO RECALIBRATION DESTINATIONS"
    )

    print(
        pd.DataFrame(
            destinations
        ).to_string(
            index=False
        )
        if destinations
        else "No eligible Final Portfolio Decision "
        "destinations."
    )

    print(
        "\nPORTFOLIO RECALIBRATION FUNDING CANDIDATES"
    )

    print(
        pd.DataFrame(
            funding_candidates
        ).to_string(
            index=False
        )
        if funding_candidates
        else "No eligible funding candidates."
    )

    print(
        "\nPORTFOLIO REALLOCATION ALLOCATION WEIGHTS"
    )

    print(
        pd.DataFrame(
            eligible_destinations
        ).to_string(
            index=False
        )

        if eligible_destinations
        else "No eligible destinations."
    )

    # ========================================================
    # AUTHORISE FUNDING CAPITAL
    # ========================================================

    remaining_funding = {}
    funding_metadata = {}

    assessment_cash = 0.0
    existing_cash = 0.0
    released_from_holdings = 0.0

    for candidate in funding_candidates:

        ticker = candidate.get(
            "Ticker",
            ""
        )

        source_value = safe_float(
            candidate.get(
                "Current Value",
                0
            )
        )

        source_decision = normalise_action(
            candidate.get(
                "Final Decision",
                ""
            )
        )

        permitted_percent = safe_float(
            candidate.get(
                "Permitted Release %",
                0
            )
        )

        if source_decision in {"CASH", "EXISTING CASH"}:

            permitted_release = source_value

        else:

            permitted_release = (
                source_value
                * permitted_percent
                / 100.0
            )

        # Reconcile on the same rounded source amounts that are
        # stored in remaining_funding and shown in the funding audit.
        # Accumulating before rounding can create a false penny of
        # unallocated capital in the summary.
        permitted_release = round(
            permitted_release,
            2
        )

        if permitted_release <= 0:

            continue

        if source_decision == "CASH":

            assessment_cash += permitted_release

        elif source_decision == "EXISTING CASH":

            existing_cash += permitted_release

        else:

            released_from_holdings += permitted_release

        remaining_funding[ticker] = (
            permitted_release
        )

        funding_metadata[ticker] = (
            candidate.copy()
        )

    total_available_capital = round(
        assessment_cash
        + existing_cash
        + released_from_holdings,
        2
    )

    # ========================================================
    # SELECT MEANINGFUL DEPLOYMENT DESTINATIONS
    # ========================================================

    deployment_destinations = (
        select_deployment_destinations(
            eligible_destinations=eligible_destinations,
            total_available_capital=total_available_capital
        )
    )


    print(
    "\nPORTFOLIO MEANINGFUL DEPLOYMENT DESTINATIONS"
    )

    print(
        pd.DataFrame(
            deployment_destinations
        ).to_string(
            index=False
        )
        if deployment_destinations
        else "No meaningful deployment destinations."
    )

    # ========================================================
    # ALLOCATE CAPITAL ACROSS DESTINATIONS
    #
    # THIS MUST HAPPEN BEFORE TRANSACTIONS ARE BUILT.
    #
    # destination_allocations is intentionally created here.
    # ========================================================

    destination_allocations = {}

    remaining_capital = total_available_capital

    max_destination_allocation = round(
        total_available_capital
        * MAX_DESTINATION_SHARE_OF_REALLOCATION,
        2
    )

    # ========================================================
    # ALLOCATE CAPITAL ACROSS DESTINATIONS
    #
    # Allocation Weight determines ranking.
    #
    # Allocation Capacity determines how much capital can
    # actually be deployed to each destination.
    # ========================================================

    if (
        deployment_destinations
        and total_available_capital > 0
    ):

        total_weight = sum(
            safe_float(
                destination.get(
                    "Allocation Weight",
                    0
                )
            )
            for destination in deployment_destinations
        )

        # ----------------------------------------------------
        # FIRST PASS
        #
        # Allocate proportionally according to governed
        # destination weights, subject to Allocation Capacity.
        # ----------------------------------------------------

        for destination in deployment_destinations:

            ticker = clean_ticker(
                destination.get(
                    "Ticker",
                    ""
                )
            )

            if not ticker:
                continue

            weight = safe_float(
                destination.get(
                    "Allocation Weight",
                    0
                )
            )

            capacity = safe_float(
                destination.get(
                    "Allocation Capacity",
                    0
                )
            )

            if total_weight <= 0:

                proposed_allocation = 0.0

            else:

                proposed_allocation = (
                    total_available_capital
                    * weight
                    / total_weight
                )

            allocation = min(
                proposed_allocation,
                capacity,
                max_destination_allocation
            )

            allocation = round(
                allocation,
                2
            )

            if (
                allocation
                >= min_reallocation_trade_value
            ):

                destination_allocations[ticker] = (
                    allocation
                )

                remaining_capital = round(
                    max(
                        0.0,
                        remaining_capital
                        - allocation
                    ),
                    2
                )

            else:

                destination_allocations[ticker] = 0.0

        remaining_capital = round(
            max(
                0.0,
                remaining_capital
            ),
            2
        )

        # ----------------------------------------------------
        # SECOND PASS
        #
        # Redistribute capital left over because some
        # destinations reached Allocation Capacity.
        # ----------------------------------------------------

        while (
            remaining_capital
            >= min_reallocation_trade_value
        ):

            destinations_with_capacity = []

            for destination in deployment_destinations:

                ticker = clean_ticker(
                    destination.get(
                        "Ticker",
                        ""
                    )
                )

                capacity = safe_float(
                    destination.get(
                        "Allocation Capacity",
                        0
                    )
                )

                already_allocated = safe_float(
                    destination_allocations.get(
                        ticker,
                        0
                    )
                )

                remaining_capacity = max(
                    0.0,
                    capacity
                    - already_allocated
                )

                if (
                    remaining_capacity
                    >= min_reallocation_trade_value
                ):

                    destinations_with_capacity.append(
                        destination
                    )

            if not destinations_with_capacity:
                break

            remaining_weight = sum(
                safe_float(
                    destination.get(
                        "Allocation Weight",
                        0
                    )
                )
                for destination
                in destinations_with_capacity
            )

            if remaining_weight <= 0:
                break

            capital_before_pass = remaining_capital

            for destination in destinations_with_capacity:

                if (
                    remaining_capital
                    < min_reallocation_trade_value
                ):
                    break

                ticker = clean_ticker(
                    destination.get(
                        "Ticker",
                        ""
                    )
                )

                weight = safe_float(
                    destination.get(
                        "Allocation Weight",
                        0
                    )
                )

                capacity = safe_float(
                    destination.get(
                        "Allocation Capacity",
                        0
                    )
                )

                already_allocated = safe_float(
                    destination_allocations.get(
                        ticker,
                        0
                    )
                )

                remaining_capacity = max(
                    0.0,
                    capacity
                    - already_allocated
                )

                proportional_share = (
                    capital_before_pass
                    * weight
                    / remaining_weight
                )

                remaining_destination_cap = max(
                    0.0,
                    max_destination_allocation
                    - already_allocated
                )

                additional_allocation = min(
                    proportional_share,
                    remaining_capacity,
                    remaining_destination_cap,
                    remaining_capital
                )

                additional_allocation = round(
                    additional_allocation,
                    2
                )

                if (
                    additional_allocation
                    < min_reallocation_trade_value
                ):
                    continue

                destination_allocations[ticker] = round(
                    already_allocated
                    + additional_allocation,
                    2
                )

                remaining_capital = round(
                    max(
                        0.0,
                        remaining_capital
                        - additional_allocation
                    ),
                    2
                )

            if remaining_capital >= capital_before_pass:
                break

    # ========================================================
    # BUILD REALLOCATION TRANSACTIONS
    #
    # HOLD funding is restricted to its specifically
    # authorised replacement destination.
    # ========================================================

    transactions = []

    remaining_destination_need = {
        ticker: round(
            amount,
            2
        )
        for ticker, amount
        in destination_allocations.items()
        if (
            amount
            >= min_reallocation_trade_value
        )
    }

    # ========================================================
    # FIRST PASS
    #
    # Use destination-specific HOLD funding first.
    # ========================================================

    for source_ticker in list(
        remaining_funding.keys()
    ):

        source_available = safe_float(
            remaining_funding.get(
                source_ticker,
                0
            )
        )

        if source_available <= 0:

            continue

        source_metadata = funding_metadata.get(
            source_ticker,
            {}
        )

        source_action = normalise_action(
            source_metadata.get(
                "Final Decision",
                ""
            )
        )

        authorised_destination = clean_ticker(
            source_metadata.get(
                "Authorised Destination",
                ""
            )
        )

        # Only HOLD funding is destination restricted.

        if (
            source_action != "HOLD"
            or not authorised_destination
        ):

            continue

        destination_need = safe_float(
            remaining_destination_need.get(
                authorised_destination,
                0
            )
        )

        if destination_need <= 0:

            continue

        destination = eligible_destination_lookup.get(
            authorised_destination,
            {}
        )

        if not destination:

            continue

        allocation = min(
            source_available,
            destination_need
        )

        allocation = round(
            allocation,
            2
        )

        if allocation <= 0:

            continue

        transactions.append(
            {
                "Source Ticker": source_ticker,
                "Source Action": "HOLD",
                "Funding Reason": source_metadata.get(
                    "Funding Reason",
                    ""
                ),
                "Authorised Destination": (
                    authorised_destination
                ),
                "Destination Ticker": (
                    authorised_destination
                ),
                "Destination Action": destination.get(
                    "Action",
                    ""
                ),
                "Destination Final Decision": (
                    destination.get(
                        "Final Decision",
                        ""
                    )
                ),
                "Investment Score": round(
                    safe_float(
                        destination.get(
                            "Investment Score",
                            0
                        )
                    ),
                    2
                ),
                "Destination Priority": round(
                    safe_float(
                        destination.get(
                            "Destination Priority",
                            0
                        )
                    ),
                    2
                ),
                "Sector": destination.get(
                    "Sector",
                    ""
                ),
                "Country": destination.get(
                    "Country",
                    destination.get("country", "")
                ),
                "Asset Type": destination.get(
                    "Asset Type",
                    ""
                ),
                "Released Capital": allocation,
                "Reallocated Capital": allocation,
                "Structural Risk": destination.get(
                    "Structural Risk",
                    "LOW"
                ),

                "Structural Risk Multiplier": destination.get(
                    "Structural Risk Multiplier",
                    1.0
                ),

                "Structural Risk Reason": destination.get(
                    "Structural Risk Reason",
                    ""
                ),
            }
        )

        remaining_funding[source_ticker] = round(
            source_available
            - allocation,
            2
        )

        remaining_destination_need[
            authorised_destination
        ] = round(
            max(
                0.0,
                destination_need
                - allocation
            ),
            2
        )

    # ========================================================
    # SECOND PASS
    #
    # CASH / SELL / REDUCE funding supports remaining
    # destinations according to funding priority.
    # ========================================================

    for destination in deployment_destinations:

        destination_ticker = clean_ticker(
            destination.get(
                "Ticker",
                ""
            )
        )

        destination_need = safe_float(
            remaining_destination_need.get(
                destination_ticker,
                0
            )
        )

        if destination_need <= 0:

            continue

        for source_ticker in list(
            remaining_funding.keys()
        ):

            if destination_need <= 0:

                break

            source_available = safe_float(
                remaining_funding.get(
                    source_ticker,
                    0
                )
            )

            if source_available <= 0:

                continue

            source_metadata = funding_metadata.get(
                source_ticker,
                {}
            )

            source_action = normalise_action(
                source_metadata.get(
                    "Final Decision",
                    ""
                )
            )

            authorised_destination = clean_ticker(
                source_metadata.get(
                    "Authorised Destination",
                    ""
                )
            )

            # HOLD capital must never leak into another
            # destination.

            if (
                source_action == "HOLD"
                and authorised_destination
            ):

                continue

            allocation = min(
                source_available,
                destination_need
            )

            allocation = round(
                allocation,
                2
            )

            if allocation <= 0:

                continue

            if source_action == "CASH":

                source_action_label = (
                    "CONTRIBUTE CASH"
                )

            else:

                source_action_label = source_action

            transactions.append(
                {
                    "Source Ticker": source_ticker,
                    "Source Action": source_action_label,
                    "Funding Reason": source_metadata.get(
                        "Funding Reason",
                        ""
                    ),
                    "Authorised Destination": "",
                    "Destination Ticker": (
                        destination_ticker
                    ),
                    "Destination Action": destination.get(
                        "Action",
                        ""
                    ),
                    "Destination Final Decision": (
                        destination.get(
                            "Final Decision",
                            ""
                        )
                    ),
                    "Investment Score": round(
                        safe_float(
                            destination.get(
                                "Investment Score",
                                0
                            )
                        ),
                        2
                    ),
                    "Destination Priority": round(
                        safe_float(
                            destination.get(
                                "Destination Priority",
                                0
                            )
                        ),
                        2
                    ),
                    "Sector": destination.get(
                        "Sector",
                        ""
                    ),
                    "Country": destination.get(
                        "Country",
                        destination.get("country", "")
                    ),
                    "Asset Type": destination.get(
                        "Asset Type",
                        ""
                    ),
                    "Allocation Weight": round(
                        safe_float(
                            destination.get(
                                "Allocation Weight",
                                0
                            )
                        ),
                        2
                    ),
                    "Structural Risk": destination.get(
                        "Structural Risk",
                        "LOW"
                    ),
                    "Structural Risk Multiplier": safe_float(
                        destination.get(
                            "Structural Risk Multiplier",
                            1.0
                        )
                    ),
                    "Structural Risk Reason": destination.get(
                        "Structural Risk Reason",
                        ""
                    ),
                    "Released Capital": allocation,
                    "Reallocated Capital": allocation
                }
            )

            remaining_funding[source_ticker] = round(
                source_available
                - allocation,
                2
            )

            destination_need = round(
                destination_need
                - allocation,
                2
            )

            remaining_destination_need[
                destination_ticker
            ] = max(
                0.0,
                destination_need
            )

    # ========================================================
    # CALCULATE SUMMARY
    # ========================================================

    # Advisory check: compare planned destination allocations
    # with the transactions actually generated. Differences
    # require review; they do not change allocation behaviour.
    planned_destination_allocation = round(
        sum(
            safe_float(amount)
            for amount in destination_allocations.values()
            if safe_float(amount) >= min_reallocation_trade_value
        ),
        2
    )

    actual_destination_allocation = round(
        sum(
            safe_float(
                transaction.get("Reallocated Capital", 0)
            )
            for transaction in transactions
            if transaction.get("Destination Ticker", "")
        ),
        2
    )

    destination_allocation_variance = round(
        planned_destination_allocation
        - actual_destination_allocation,
        2
    )

    if abs(destination_allocation_variance) <= 0.01:

        destination_allocation_variance_reason = (
            "Planned destination allocations match generated transactions."
        )

    elif destination_allocation_variance > 0:

        destination_allocation_variance_reason = (
            f"Planned destination allocations exceed generated "
            f"transactions by £{destination_allocation_variance:.2f}."
        )

    else:

        destination_allocation_variance_reason = (
            f"Generated destination transactions exceed planned "
            f"allocations by £{abs(destination_allocation_variance):.2f}."
        )


    destination_allocation_status = (
        "PASS"
        if abs(destination_allocation_variance) <= 0.01
        else "REVIEW"
    )

    total_reallocated = round(
        sum(
            safe_float(
                transaction.get(
                    "Reallocated Capital",
                    0
                )
            )
            for transaction
            in transactions
        ),
        2
    )

    # Funding candidate values are authorised release capacity. Only amounts
    # represented by generated transactions are proposed as released capital.
    # Any unused balance remains capacity, not unallocated cash.
    total_authorised_funding_capacity = total_available_capital

    total_released = round(
        sum(
            safe_float(transaction.get("Released Capital", 0))
            for transaction in transactions
        ),
        2,
    )

    actual_assessment_cash_used = round(
        sum(
            safe_float(transaction.get("Released Capital", 0))
            for transaction in transactions
            if clean_ticker(transaction.get("Source Ticker", "")) == "ASSESSMENT CASH"
        ),
        2,
    )

    actual_existing_cash_used = round(
        sum(
            safe_float(transaction.get("Released Capital", 0))
            for transaction in transactions
            if (
                clean_ticker(transaction.get("Source Ticker", "")) == "CASH"
                and normalise_action(transaction.get("Source Action", "")) == "EXISTING CASH"
            )
        ),
        2,
    )

    actual_released_from_holdings = round(
        sum(
            safe_float(transaction.get("Released Capital", 0))
            for transaction in transactions
            if clean_ticker(transaction.get("Source Ticker", ""))
            not in {"ASSESSMENT CASH", "CASH"}
        ),
        2,
    )

    unused_authorised_funding_by_source = []
    for source_ticker, remaining_amount in sorted(remaining_funding.items()):
        remaining_amount = safe_float(remaining_amount)
        if remaining_amount <= 0:
            continue

        source_metadata = funding_metadata.get(source_ticker, {})
        unused_authorised_funding_by_source.append({
            "Source Ticker": source_ticker,
            "Unused Authorised Funding": round(remaining_amount, 2),
            "Source Decision": normalise_action(
                source_metadata.get("Final Decision", "")
            ),
            "Authorised Destination": clean_ticker(
                source_metadata.get("Authorised Destination", "")
            ),
            "Funding Reason": source_metadata.get("Funding Reason", ""),
        })

    unused_authorised_funding_capacity = round(
        sum(
            safe_float(amount)
            for amount in remaining_funding.values()
        ),
        2,
    )

    unused_destination_restricted_funding = round(
        sum(
            safe_float(amount)
            for source_ticker, amount in remaining_funding.items()
            if (
                normalise_action(
                    funding_metadata.get(source_ticker, {}).get("Final Decision", "")
                ) == "HOLD"
                and clean_ticker(
                    funding_metadata.get(source_ticker, {}).get("Authorised Destination", "")
                )
            )
        ),
        2,
    )

    if abs(destination_allocation_variance) <= 0.01:

        destination_allocation_variance_reason = (
            "Planned destination allocations match the generated transactions."
        )

    elif destination_allocation_variance > 0:

        destination_allocation_variance_reason = (
            f"Planned destination allocations exceed generated transactions "
            f"by £{destination_allocation_variance:.2f}."
        )

    else:

        destination_allocation_variance_reason = (
            f"Generated destination transactions exceed planned allocations "
            f"by £{abs(destination_allocation_variance):.2f}."
        )

    if unused_destination_restricted_funding > 0.01:

        destination_allocation_variance_reason += (
            f" £{unused_destination_restricted_funding:.2f} of unused HOLD "
            "funding remains restricted to its authorised replacement "
            "destination and cannot be redirected to other destinations."
        )

    reconciliation_variance = round(
        total_released - total_reallocated,
        2,
    )

    unallocated_capital = round(
        max(0.0, reconciliation_variance),
        2,
    )

    reconciliation_tolerance = 0.01
    if reconciliation_variance < -reconciliation_tolerance:
        reconciliation_status = "OVERALLOCATED"
    elif reconciliation_variance > reconciliation_tolerance:
        reconciliation_status = "UNDERALLOCATED"
    else:
        reconciliation_status = "PASS"

    funding_sources = len(
        {
            transaction.get(
                "Source Ticker",
                ""
            )
            for transaction
            in transactions
            if transaction.get(
                "Source Ticker",
                ""
            )
        }
    )

    destination_count = len(
        {
            transaction.get(
                "Destination Ticker",
                ""
            )
            for transaction
            in transactions
            if transaction.get(
                "Destination Ticker",
                ""
            )
        }
    )

    summary = {
        "Assessment Cash": round(
            assessment_cash,
            2
        ),
        "Assessment Cash Used": actual_assessment_cash_used,
        "Existing Portfolio Cash": round(
            existing_cash,
            2
        ),
        "Existing Portfolio Cash Used": actual_existing_cash_used,
        "Released From Holdings": actual_released_from_holdings,
        "Authorised Release Capacity From Holdings": round(
            released_from_holdings,
            2
        ),
        "Total Authorised Funding Capacity": total_authorised_funding_capacity,
        "Total Released": total_released,
        "Total Reallocated": total_reallocated,
        "Unused Authorised Funding Capacity": unused_authorised_funding_capacity,
        "Unused Authorised Funding By Source": unused_authorised_funding_by_source,
        "Unused Destination-Restricted Funding": unused_destination_restricted_funding,
        "Actual Destination Allocation": (
            actual_destination_allocation
        ),
        "Planned Destination Allocation": (
            planned_destination_allocation
        ),
        "Destination Allocation Variance": (
            destination_allocation_variance
        ),
        "Destination Allocation Reconciliation": (
            destination_allocation_status
        ),
        "Destination Allocation Variance Reason": (
            destination_allocation_variance_reason
        ),
        "Unallocated Capital": unallocated_capital,
        "Reconciliation Variance": reconciliation_variance,
        "Reconciliation Status": reconciliation_status,
        "Exposure Denominator": exposure_portfolio_value,
        "Funding Sources": funding_sources,
        "Destinations": destination_count
    }

    reallocation_df = pd.DataFrame(
        transactions
    )

    # ========================================================
    # DEBUG OUTPUT
    # ========================================================

    print(
        "\nPORTFOLIO REALLOCATION DETAIL"
    )

    print(
        reallocation_df.to_string(
            index=False
        )
        if not reallocation_df.empty
        else "No portfolio reallocation required."
    )

    print(
        "\nPORTFOLIO REALLOCATION SUMMARY"
    )

    print(
        summary
    )

    reallocation_audit = build_reallocation_audit(
        destinations=destinations,
        eligible_destinations=eligible_destinations,
        deployment_destinations=deployment_destinations,
        destination_allocations=destination_allocations,
        funding_candidates=funding_candidates,
        reallocation_df=reallocation_df,
        summary=summary,
        min_destination_score=MIN_DESTINATION_SCORE,
        min_trade_value=min_reallocation_trade_value,
        max_destination_share=MAX_DESTINATION_SHARE_OF_REALLOCATION,
        max_destination_count=MAX_REALLOCATION_DESTINATIONS,
    )

    # ========================================================
    # SHADOW MARKET AND PORTFOLIO RISK ASSESSMENT
    # ========================================================

    market_risk_assessment = _build_market_risk_assessment(
        final_portfolio_decisions,
        portfolio_value,
        market_intelligence=market_intelligence,
        financial_statements_by_ticker=financial_statements_by_ticker,
        reallocation=reallocation_df,
    )

    # --------------------------------------------------------
    # SHADOW MACRO-ALLOCATION SENSITIVITY
    # Diagnostic only: never changes weights or transactions.
    # --------------------------------------------------------
    macro_assessment = market_risk_assessment.get(
        "macro_risk_assessment", {}
    )
    macro_news = market_risk_assessment.get(
        "macro_news_assessment", {}
    )

    macro_theme_names = (
        "INTEREST_RATES",
        "INFLATION",
        "AI_BORROWING_AND_CREDIT",
        "MARKET_DOWNTURN",
        "TRADE_AND_GEOPOLITICS",
    )

    structured_theme_evidence = (
        market_risk_assessment.get("macro_theme_evidence", [])
    )
    # Headline matches are review signals, not validated risk evidence.
    macro_category_by_theme = {
        "INTEREST_RATES": {"CENTRAL_BANK_AND_RATES"},
        "INFLATION": {"INFLATION"},
        "AI_BORROWING_AND_CREDIT": {"CREDIT_AND_FINANCIAL_STABILITY"},
        "MARKET_DOWNTURN": {"GROWTH_AND_EMPLOYMENT"},
        "TRADE_AND_GEOPOLITICS": {"TRADE_AND_GEOPOLITICS"},
    }

    other_macro_categories = {
        "TRADE_AND_GEOPOLITICS",
        "ENERGY_AND_COMMODITIES",
    }

    theme_evidence_by_name = {
        str(item.get("theme", "")).strip().upper(): item
        for item in structured_theme_evidence
        if isinstance(item, dict) and item.get("theme")
    }

    available_themes = {
        theme
        for theme, item in theme_evidence_by_name.items()
        if item.get("status") in {
            "MEASURED_PROXY_AVAILABLE",
            "MEASURED_DIRECT_AVAILABLE",
        }
        and item.get("source")
        and item.get("observed_at")
        and item.get("observation")
    }


    macro_items = macro_news.get("items", [])
    headline_signals = {}

    for theme, categories in macro_category_by_theme.items():
        matches = []
        for item in macro_items:
            if not isinstance(item, dict):
                continue

            # Match against the current item's headline, never a prior item.
            headline = str(item.get("Headline", ""))
            headline_lower = headline.casefold()

            found_categories = {
                part.strip().upper()
                for part in str(item.get("Category", "")).split(";")
            }

            category_match = bool(
                categories.intersection(found_categories)
            )

            # Trade/geopolitics headlines can be recognised directly
            # from their text even if the source category is inconsistent.
            headline_match = (
                theme == "TRADE_AND_GEOPOLITICS"
                and any(
                    term in headline_lower
                    for term in (
                        "sanction", "tariff", "trade war",
                        "export control", "geopolitic",
                        "invasion", "blockade",
                        "shipping disruption",
                        "supply chain disruption",
                        "supply-chain disruption",
                        "military conflict",
                    )
                )
            )

            if not category_match and not headline_match:
                continue


            # Require both an AI/data-centre reference and a financing
            # reference. Generic capex or borrowing headlines do not count.
            if theme == "AI_BORROWING_AND_CREDIT":
                ai_or_datacentre_terms = (
                    "artificial intelligence",
                    " ai ",
                    "data center",
                    "data centre",
                    "gpu",
                )
                financing_terms = (
                    "borrowing",
                    "debt financing",
                    "capex",
                    "capital expenditure",
                    "financing",
                    "debt",
                    "credit",
                )

                has_ai_or_datacentre_reference = any(
                    term in headline_lower
                    for term in ai_or_datacentre_terms
                )
                has_financing_reference = any(
                    term in headline_lower
                    for term in financing_terms
                )

                if not (
                    has_ai_or_datacentre_reference
                    and has_financing_reference
                ):
                    continue


            # Require explicit downturn language rather than general
            # growth or employment news.
            if theme == "MARKET_DOWNTURN" and not any(
                term in headline_lower
                for term in (
                    "recession", "economic contraction", "market downturn",
                    "market selloff", "market sell-off", "bear market",
                    "economic slowdown",
                )
            ):
                continue

            matches.append({
                "Headline": headline,
                "Published Date": item.get("Published Date"),
                "Source": item.get("Source"),
                "Related Tickers": item.get("Related Tickers", []),
            })

        headline_signals[theme] = {
            "status": (
                "HEADLINE SIGNAL FOUND"
                if matches else "NO HEADLINE SIGNAL FOUND"
            ),
            "matched_headlines": matches,
            "validated_evidence_available": theme in available_themes,
            "advisory_only": True,
        }

    other_macro_headline_signals = [
        {
            "Category": item.get("Category"),
            "Headline": item.get("Headline"),
            "Related Tickers": item.get("Related Tickers", []),
            "Published Date": item.get("Published Date"),
            "Source": item.get("Source"),
            "Status": "UNVALIDATED REVIEW SIGNAL",
            "Advisory Only": True,
        }
        for item in macro_items
        if isinstance(item, dict)
        and other_macro_categories.intersection(
            part.strip().upper()
            for part in str(item.get("Category", "")).split(";")
        )
        and not any(
            categories.intersection(
                part.strip().upper()
                for part in str(item.get("Category", "")).split(";")
            )
            for categories in macro_category_by_theme.values()
        )
    ]

    baseline_by_ticker = {}
    if not reallocation_df.empty:
        for _, transaction in reallocation_df.iterrows():
            ticker = clean_ticker(
                transaction.get("Destination Ticker", "")
            )
            if ticker:
                baseline_by_ticker[ticker] = round(
                    baseline_by_ticker.get(ticker, 0.0)
                    + safe_float(
                        transaction.get("Reallocated Capital", 0)
                    ),
                    2,
                )

    shadow_sensitivity_rows = []
    for destination in deployment_destinations:
        ticker = clean_ticker(destination.get("Ticker", ""))
        if not ticker:
            continue

        shadow_sensitivity_rows.append({
            "Ticker": ticker,
            "Sector": destination.get("Sector", ""),
            "Industry": destination.get("Industry", ""),
            "Baseline Allocation": baseline_by_ticker.get(ticker, 0.0),
            "Macro Themes Assessed": ", ".join(
                theme for theme in macro_theme_names
                if theme in available_themes
            ) or "NONE",
            "Evidence Status": (
                "STRUCTURED THEME EVIDENCE AVAILABLE"
                if available_themes
                else "INSUFFICIENT STRUCTURED THEME EVIDENCE"
            ),
            "Counterfactual Allocation": None,
            "Allocation Difference": None,
            "Adjustment Applied": False,
            "Reason": (
                "No calibrated, evidence-backed macro adjustment is "
                "authorised; baseline allocation retained."
            ),
            "Advisory Only": True,
        })

    market_risk_assessment["shadow_allocation_sensitivity"] = {
        "mode": "SHADOW",
        "advisory_only": True,
        "production_allocation_changed": False,
        "macro_theme_evidence_available": sorted(available_themes),
        "headline_signals_by_theme": headline_signals,
        "other_macro_headline_signals": other_macro_headline_signals,
        "required_themes": list(macro_theme_names),
        "unassessed_themes": [
            theme for theme in macro_theme_names
            if theme not in available_themes
        ],
        "destinations": shadow_sensitivity_rows,
        "limitations": [
            "Counterfactual allocations remain unset until theme evidence, "
            "exposure mapping and adjustment magnitudes are validated.",
            "A headline keyword match alone is not sufficient evidence "
            "to reduce a destination allocation.",
        ],
    }

    print("\\nSHADOW MACRO-ALLOCATION SENSITIVITY")

    print(
        pd.DataFrame(shadow_sensitivity_rows).to_string(index=False)
        if shadow_sensitivity_rows
        else "No proposed destinations available for sensitivity review."
    )

    print("\nSHADOW MARKET AND PORTFOLIO RISK ASSESSMENT")

    print("\nEXPOSURE RECONCILIATION CHECKS (ADVISORY ONLY)")
    validation_rows = market_risk_assessment.get("exposure_validation", [])
    if validation_rows:
        print(
            pd.DataFrame(validation_rows)[
                ["check", "status", "observed", "expected", "detail"]
            ].to_string(index=False)
        )
    else:
        print("No exposure reconciliation checks returned.")


    print("\nEXPOSURE DENOMINATOR BASIS")

    denominator_rows = []
    for measure, details in market_risk_assessment.get(
        "exposure_denominators", {}
    ).items():
        denominator_rows.append({
            "Measure": measure,
            "Denominator Value": details.get("value"),
            "Basis": details.get("basis"),
            "Description": details.get("description"),
        })

    if denominator_rows:
        print(pd.DataFrame(denominator_rows).to_string(index=False))
    else:
        print("Exposure denominator definitions unavailable.")


    print("\nCURRENT PORTFOLIO EXPOSURE COVERAGE")
    coverage_rows = [
        item
        for item in market_risk_assessment.get("classification_coverage", [])
        if item.get("portfolio_state") == "CURRENT"
    ]
    if coverage_rows:
        print(pd.DataFrame(coverage_rows).to_string(index=False))
    else:
        print("No current exposure coverage records returned.")

    print("\nKNOWN ETF HOLDINGS — LOOK-THROUGH STATUS")
    etf_rows = market_risk_assessment.get("known_etf_holdings", [])
    if etf_rows:
        print(pd.DataFrame(etf_rows).to_string(index=False))
    else:
        print("No ETF holdings identified.")
    print("Mode:", market_risk_assessment["mode"])
    print("Macro Risk Status:", market_risk_assessment["macro_risk_status"])
    print(
        "Market Stress Status:",
        market_risk_assessment.get("market_stress_status", "UNASSESSED"),
    )

    macro_assessment = market_risk_assessment.get("macro_risk_assessment", {})
    macro_news = market_risk_assessment.get("macro_news_assessment", {})
    print("\nMACRO NEWS RISK WARNINGS")
    print("Status:", macro_news.get("status", "UNASSESSED"))
    print("As of:", macro_news.get("as_of"))
    print("Summary:", macro_news.get("summary", "No macro news assessment returned."))
    macro_news_items = macro_news.get("items", [])
    if macro_news_items:
        print(pd.DataFrame(macro_news_items).to_string(index=False))
    else:
        print("No macro-news warning rows available.")
    for limitation in macro_news.get("limitations", []):
        print("Limitation:", limitation)

    print("\nMACRO RISK PROXY ASSESSMENT")
    print("Status:", macro_assessment.get("status", "UNASSESSED"))
    print(
        "Oldest observation date (legacy as_of):",
        macro_assessment.get("as_of"),
    )
    print(
        "Latest observation date:",
        macro_assessment.get("latest_observation_date"),
    )
    print(
        "Observation date coverage:",
        macro_assessment.get("oldest_observation_date"),
        "to",
        macro_assessment.get("latest_observation_date"),
    )
    print("Summary:", macro_assessment.get("summary", "No macro assessment returned."))
    macro_rows = macro_assessment.get("indicators", [])
    if macro_rows:
        print(pd.DataFrame(macro_rows).to_string(index=False))
    print("Historical pre-trade status:", macro_assessment.get("historical_pre_trade_status", "NOT_ASSESSED"))
    print("Historical pre-trade limitation:", macro_assessment.get("historical_pre_trade_reason", "Not available."))

    breadth_assessment = market_risk_assessment.get(
        "market_breadth_assessment", {}
    )
    print("\nMARKET BREADTH ASSESSMENT")
    print("Status:", breadth_assessment.get("status", "UNASSESSED"))
    print(
        "Reason:",
        breadth_assessment.get(
            "reason",
            "Constituent-level breadth data is not available.",
        ),
    )

    for section, title in (
        ("market_stress_indicators", "BROAD-MARKET STRESS INDICATORS"),
        ("market_breadth_indicators", "MARKET BREADTH INDICATORS — CONSTITUENT LEVEL"),
        ("market_sector_breadth", "SECTOR BREADTH AND EQUAL-WEIGHTED ROTATION"),
        ("market_leadership_indicators", "MARKET LEADERSHIP / RELATIVE STRENGTH"),
        ("macro_stress_scenarios", "MACRO STRESS SCENARIO ASSESSMENT"),
        ("candidate_macro_reviews", "CANDIDATE MACRO SENSITIVITY REVIEWS"),
        ("holding_market_sensitivity", "HOLDING MARKET SENSITIVITY"),
        ("correlated_holding_clusters", "CORRELATED HOLDING PAIRS"),
        ("common_theme_exposure", "SECTOR / INDUSTRY EXPOSURE AND OVERLAP"),
        ("explicit_investment_theme_assessment", "EXPLICIT INVESTMENT THEMES — ASSESSMENT STATUS"),
        ("holding_market_sensitivity_unavailable", "HOLDING PRICE DATA GAPS"),
        ("portfolio_concentration", "PORTFOLIO CONCENTRATION"),
        ("company_risk_flags", "COMPANY RISK FLAGS"),
        ("transaction_risk_reviews", "TRANSACTION RISK REVIEWS"),
        ("recommendations", "RISK RECOMMENDATIONS"),
        ("limitations", "RISK ASSESSMENT LIMITATIONS"),
    ):
        print(f"\n{title}")

        items = market_risk_assessment.get(section, [])

        if items:
            print(pd.DataFrame(items).to_string(index=False))
        else:
            print("None reported.")

    print("\nRISK ASSESSMENT DATA QUALITY")
    print(
        pd.DataFrame([
            {
                "Check": check,
                "Available": available,
            }
            for check, available
            in market_risk_assessment["data_quality"].items()
        ]).to_string(index=False)
    )

    # ========================================================
    # RETURN
    # ========================================================

    return {
        "reallocation": reallocation_df,
        "summary": summary,
        "audit": reallocation_audit,
        "market_risk_assessment": market_risk_assessment,
    }