
"""
portfolio_decision_engine.py

Purpose
-------
Converts portfolio analysis and investment opportunities into
portfolio-level actions.

Asset classes are deliberately handled separately.

STOCK:
    Uses Investment Score, Quality Score, Growth Score and
    Momentum Signal.

ETF:
    Uses the authoritative ETF decision engine in
    etf_decisions.py.

CASH:
    No investment decision.

Portfolio philosophy
--------------------
Existing positions are protected by default.

The engine should HOLD unless there is sufficiently strong
evidence to change the position.

For existing STOCK holdings, reductions have explicit severity:

    HOLD
    REDUCE 25%
    REDUCE 50%
    REDUCE 75%
    SELL

SELL represents a 100% reduction.

There is deliberately no REDUCE 100% action and no arbitrary
percentage such as REDUCE 70%.

The portfolio decision engine determines the reduction severity.

Capital allocation is handled separately by capital_allocator.py.
The capital allocator executes the action it receives and must not
invent the reduction severity.

ETF decisions are NOT recreated here.

ETF decision logic is owned exclusively by:

    analysis/etf_decisions.py

This module only wires the authoritative ETF decision into the
portfolio-level decision pipeline.
"""

import pandas as pd

from analysis.etf_decisions import decide_etf


# ============================================================
# ACTION CONSTANTS
# ============================================================

HOLD_ACTION = "HOLD"

REDUCE_25_ACTION = "REDUCE 25%"
REDUCE_50_ACTION = "REDUCE 50%"
REDUCE_75_ACTION = "REDUCE 75%"
SELL_ACTION = "SELL"

REDUCTION_ACTIONS = {
    REDUCE_25_ACTION,
    REDUCE_50_ACTION,
    REDUCE_75_ACTION,
    SELL_ACTION,
}


# ============================================================
# HELPERS
# ============================================================

def safe_float(value, default=0.0):
    """
    Safely convert a value to float.

    Invalid, missing or NaN values return the supplied default.
    """

    try:

        if value is None:
            return default

        if pd.isna(value):
            return default

        return float(value)

    except Exception:

        return default


def normalise_text(value, default="UNKNOWN"):
    """
    Safely convert a value to normalised uppercase text.
    """

    if value is None:
        return default

    try:

        if pd.isna(value):
            return default

    except Exception:
        pass

    value = str(value).strip()

    if not value:
        return default

    return value.upper()


def get_value(row, *keys, default=None):
    """
    Return the first valid value found under the supplied keys.
    """

    for key in keys:

        try:
            value = row.get(
                key,
                None
            )
        except Exception:
            value = None

        if value is None:
            continue

        try:

            if pd.isna(value):
                continue

        except Exception:
            pass

        if isinstance(
            value,
            str
        ) and not value.strip():

            continue

        return value

    return default


def clean_ticker(value):
    """
    Normalise a ticker symbol.
    """

    if value is None:
        return ""

    try:

        if pd.isna(value):
            return ""

    except Exception:
        pass

    return str(
        value
    ).strip().upper()


# ============================================================
# STOCK BUY APPROVAL
# ============================================================

def approve_buy(
    investment_score,
    conviction,
    allocation,
    portfolio_risk,
    sector_allocation
):
    """
    Determine whether a new STOCK position is sufficiently
    attractive to receive a BUY NEW action.

    Conviction is informational and is not used as an
    independent governance veto because it is derived from
    underlying deterministic investment evidence.
    """

    investment_score = safe_float(
        investment_score
    )

    allocation = safe_float(
        allocation
    )

    sector_allocation = safe_float(
        sector_allocation
    )

    portfolio_risk = normalise_text(
        portfolio_risk
    )

    if investment_score < 75:
        return False

    if allocation >= 10:
        return False

    if portfolio_risk == "HIGH":
        return False

    if sector_allocation >= 30:
        return False

    return True
# ============================================================
# STOCK REDUCTION SEVERITY
# ============================================================

def determine_reduction_action(
    investment_score,
    quality_score,
    growth_score,
    signal
):
    """
    Determine the severity of a STOCK reduction.

    Returns
    -------
    tuple
        (action, reason)

    Actions
    -------
    HOLD
    REDUCE 25%
    REDUCE 50%
    REDUCE 75%
    SELL

    SELL represents a 100% reduction.

    Design principles
    -----------------
    1. HOLD remains the default.
    2. Investment Score is important but is not used alone.
    3. Quality, Growth and Momentum Signal provide corroborating
       evidence.
    4. Stronger deterioration produces a larger reduction.
    5. A bearish signal without sufficient underlying evidence does
       not automatically cause a large reduction.
    6. SELL is reserved for exceptionally strong deterioration.
    """

    investment_score = safe_float(
        investment_score
    )

    quality_score = safe_float(
        quality_score
    )

    growth_score = safe_float(
        growth_score
    )

    signal = normalise_text(
        signal
    )

    bearish_signal = signal in {
        "SELL",
        "STRONG SELL",
    }

    strong_bearish_signal = (
        signal == "STRONG SELL"
    )

    # ========================================================
    # SELL / 100% REDUCTION
    #
    # Reserved for exceptionally strong evidence.
    #
    # This requires either:
    #
    #   - extremely low Investment Score + STRONG SELL
    #
    # or:
    #
    #   - extremely weak Investment Score combined with
    #     extremely weak Quality and Growth.
    # ========================================================

    if (
        investment_score < 20
        and
        strong_bearish_signal
    ):

        return (
            SELL_ACTION,
            "Extremely low investment score combined with a "
            "STRONG SELL signal indicates that the position "
            "should be exited completely"
        )

    if (
        investment_score < 25
        and
        bearish_signal
        and
        quality_score < 30
        and
        growth_score < 30
    ):

        return (
            SELL_ACTION,
            "Extremely weak investment score, quality and growth "
            "combined with a bearish signal justify a complete exit"
        )

    if (
        investment_score < 20
        and
        quality_score < 25
        and
        growth_score < 25
    ):

        return (
            SELL_ACTION,
            "Exceptionally weak investment, quality and growth "
            "scores justify a complete exit"
        )

    # ========================================================
    # REDUCE 75%
    #
    # Severe deterioration.
    # ========================================================

    if (
        investment_score < 30
        and
        strong_bearish_signal
    ):

        return (
            REDUCE_75_ACTION,
            "Very low investment score combined with a STRONG "
            "SELL signal indicates severe deterioration"
        )

    if (
        investment_score < 30
        and
        bearish_signal
        and
        (
            quality_score < 40
            or
            growth_score < 35
        )
    ):

        return (
            REDUCE_75_ACTION,
            "Very low investment score, bearish signal and "
            "material weakness in quality or growth indicate "
            "severe deterioration"
        )

    if (
        investment_score < 30
        and
        quality_score < 30
        and
        growth_score < 30
    ):

        return (
            REDUCE_75_ACTION,
            "Very low investment score combined with extremely "
            "weak quality and growth indicates severe deterioration"
        )

    # ========================================================
    # REDUCE 50%
    #
    # Clear deterioration.
    # ========================================================

    if (
        investment_score < 45
        and
        bearish_signal
        and
        quality_score < 50
        and
        growth_score < 40
    ):

        return (
            REDUCE_50_ACTION,
            "Low investment score combined with weak quality, "
            "weak growth and a bearish signal indicates clear "
            "deterioration"
        )

    if (
        investment_score < 40
        and
        bearish_signal
    ):

        return (
            REDUCE_50_ACTION,
            "Low investment score combined with a bearish signal "
            "indicates clear deterioration"
        )

    if (
        investment_score < 35
        and
        (
            quality_score < 40
            or
            growth_score < 35
        )
        and
        bearish_signal
    ):

        return (
            REDUCE_50_ACTION,
            "Low investment score, weak fundamentals and a bearish "
            "signal justify a substantial reduction"
        )

    # ========================================================
    # REDUCE 25%
    #
    # Mild but credible deterioration.
    #
    # This is deliberately the lowest reduction severity.
    # ========================================================

    if (
        investment_score < 45
        and
        bearish_signal
    ):

        return (
            REDUCE_25_ACTION,
            "Investment score has weakened and the bearish signal "
            "provides sufficient evidence for a modest reduction"
        )

    if (
        investment_score < 40
        and
        (
            quality_score < 50
            or
            growth_score < 45
        )
    ):

        return (
            REDUCE_25_ACTION,
            "Low investment score combined with weakening "
            "fundamentals supports a modest reduction"
        )

    # ========================================================
    # HOLD
    #
    # Insufficient evidence for a reduction.
    # ========================================================

    if investment_score >= 70:

        return (
            HOLD_ACTION,
            "Investment score remains sufficiently strong to "
            "retain the existing position"
        )

    if investment_score >= 45:

        return (
            HOLD_ACTION,
            "Investment score is below the buy threshold but "
            "there is insufficient evidence to reduce the position"
        )

    return (
        HOLD_ACTION,
        "Investment score is weak but the available evidence "
        "is insufficient to justify a portfolio reduction"
    )


# ============================================================
# STOCK EXISTING HOLDING
# ============================================================

def evaluate_existing_holding(
    investment_score,
    quality_score,
    growth_score,
    signal
):
    """
    Evaluate an existing STOCK holding.

    This is the public stock holding decision wrapper.

    Reduction severity is determined here rather than in the
    capital allocator.

    Possible actions:

        HOLD
        REDUCE 25%
        REDUCE 50%
        REDUCE 75%
        SELL

    SELL is equivalent to reducing the position by 100%.
    """

    return determine_reduction_action(
        investment_score=investment_score,
        quality_score=quality_score,
        growth_score=growth_score,
        signal=signal
    )


# ============================================================
# PORTFOLIO DECISION ENGINE
# ============================================================

def generate_portfolio_decisions(
    portfolio_summary,
    opportunities=None
):
    """
    Generate portfolio-level decisions.

    Existing holdings:
        STOCK -> stock decision engine
        ETF   -> authoritative ETF decision engine
        CASH  -> HOLD

    New opportunities:
        STOCK -> BUY NEW / WATCH / HOLD
        ETF   -> currently excluded from BUY NEW processing

    Capital allocation is deliberately not performed here.
    """

    if portfolio_summary is None:
        portfolio_summary = pd.DataFrame()

    if opportunities is None:
        opportunities = pd.DataFrame()

    if not isinstance(
        portfolio_summary,
        pd.DataFrame
    ):

        portfolio_summary = pd.DataFrame(
            portfolio_summary
        )

    if not isinstance(
        opportunities,
        pd.DataFrame
    ):

        opportunities = pd.DataFrame(
            opportunities
        )

    decisions = []

    # ========================================================
    # OPPORTUNITY LOOKUP
    # ========================================================

    intelligence = {}

    if (
        not opportunities.empty
        and
        "Ticker" in opportunities.columns
    ):

        opportunity_data = opportunities.copy()

        opportunity_data["Ticker"] = (
            opportunity_data["Ticker"]
            .apply(clean_ticker)
        )

        opportunity_data = opportunity_data[
            opportunity_data["Ticker"] != ""
        ]

        if "Investment Score" in opportunity_data.columns:

            opportunity_data["_Score"] = (
                pd.to_numeric(
                    opportunity_data[
                        "Investment Score"
                    ],
                    errors="coerce"
                )
                .fillna(0)
            )

            opportunity_data = (
                opportunity_data
                .sort_values(
                    "_Score",
                    ascending=False
                )
                .drop_duplicates(
                    subset=["Ticker"],
                    keep="first"
                )
                .drop(
                    columns=["_Score"]
                )
            )

        intelligence = (
            opportunity_data
            .set_index("Ticker")
            .to_dict("index")
        )

    # ========================================================
    # EXISTING HOLDINGS
    # ========================================================

    existing_tickers = set()

    if (
        not portfolio_summary.empty
        and
        "Ticker" in portfolio_summary.columns
    ):

        portfolio = portfolio_summary.copy()

        portfolio["Ticker"] = (
            portfolio["Ticker"]
            .apply(clean_ticker)
        )

        portfolio = portfolio[
            portfolio["Ticker"] != ""
        ]

        existing_tickers = set(
            portfolio["Ticker"]
        )

        for _, row in portfolio.iterrows():

            ticker = clean_ticker(
                row.get(
                    "Ticker",
                    ""
                )
            )

            if not ticker:
                continue

            asset_type = normalise_text(
                get_value(
                    row,
                    "Type",
                    "Asset Type",
                    default="STOCK"
                )
            )

            stock_info = intelligence.get(
                ticker,
                {}
            )

            allocation = safe_float(
                get_value(
                    row,
                    "Allocation %",
                    "Allocation",
                    "Portfolio Allocation %",
                    default=0
                )
            )

            portfolio_risk = normalise_text(
                get_value(
                    row,
                    "Portfolio Risk",
                    "Risk",
                    default="NORMAL"
                )
            )

            # =================================================
            # ETF
            # =================================================

            if asset_type == "ETF":

                etf_score = safe_float(
                    get_value(
                        row,
                        "ETF Score",
                        "etf_score",
                        default=0
                    )
                )

                etf_signal = normalise_text(
                    get_value(
                        row,
                        "ETF Signal",
                        "etf_signal",
                        default="UNKNOWN"
                    )
                )

                etf_reasons = get_value(
                    row,
                    "ETF Reasons",
                    default=""
                )

                etf_risks = get_value(
                    row,
                    "ETF Risks",
                    default=""
                )

                quantity = safe_float(
                    get_value(
                        row,
                        "Shares",
                        "Quantity",
                        default=0
                    )
                )

                market_value = safe_float(
                    get_value(
                        row,
                        "Current Value",
                        "Market Value",
                        default=0
                    )
                )

                etf_decision = decide_etf(
                    etf_analysis={
                        "ETF Score":
                            etf_score,

                        "ETF Signal":
                            etf_signal,

                        "ETF Reasons":
                            etf_reasons,

                        "ETF Risks":
                            etf_risks
                    },
                    quantity=quantity,
                    market_value=market_value,
                    portfolio_weight=allocation
                )

                decisions.append({

                    "Ticker":
                        ticker,

                    "Action":
                        etf_decision.get(
                            "ETF Decision",
                            "HOLD"
                        ),

                    "Reason":
                        etf_decision.get(
                            "ETF Decision Reason",
                            "ETF decision unavailable; "
                            "HOLD retained."
                        ),

                    "Investment Score":
                        None,

                    "ETF Score":
                        etf_decision.get(
                            "ETF Score",
                            etf_score
                        ),

                    "ETF Signal":
                        etf_decision.get(
                            "ETF Signal",
                            etf_signal
                        ),

                    "ETF Decision Confidence":
                        etf_decision.get(
                            "ETF Decision Confidence",
                            "LOW"
                        ),

                    "ETF Reduction %":
                        etf_decision.get(
                            "ETF Reduction %",
                            0
                        ),

                    "Quality Score":
                        None,

                    "Growth Score":
                        None,

                    "Signal":
                        "N/A",

                    "AI Conviction":
                        "N/A",

                    "Allocation %":
                        allocation,

                    "Sector":
                        "ETF",

                    "Sector Allocation %":
                        0,

                    "Portfolio Risk":
                        portfolio_risk,

                    "Existing Holding":
                        "Yes",

                    "Asset Type":
                        "ETF",

                    "ETF Reasons":
                        etf_reasons,

                    "ETF Risks":
                        etf_risks
                })

                continue

            # =================================================
            # CASH
            # =================================================

            if asset_type == "CASH":

                decisions.append({

                    "Ticker":
                        ticker,

                    "Action":
                        "HOLD",

                    "Reason":
                        "Maintain cash position",

                    "Investment Score":
                        None,

                    "ETF Score":
                        None,

                    "ETF Signal":
                        "N/A",

                    "ETF Decision Confidence":
                        "N/A",

                    "ETF Reduction %":
                        0,

                    "Quality Score":
                        None,

                    "Growth Score":
                        None,

                    "Signal":
                        "N/A",

                    "AI Conviction":
                        "N/A",

                    "Allocation %":
                        allocation,

                    "Sector":
                        "Cash",

                    "Sector Allocation %":
                        0,

                    "Portfolio Risk":
                        portfolio_risk,

                    "Existing Holding":
                        "Yes",

                    "Asset Type":
                        "CASH"
                })

                continue

            # =================================================
            # STOCK
            # =================================================

            investment_score = safe_float(
                get_value(
                    stock_info,
                    "Investment Score",
                    "investment_score",
                    "Score",
                    default=get_value(
                        row,
                        "Investment Score",
                        "investment_score",
                        "Score",
                        default=0
                    )
                )
            )

            quality_score = safe_float(
                get_value(
                    stock_info,
                    "Quality Score",
                    "quality_score",
                    default=get_value(
                        row,
                        "Quality Score",
                        "quality_score",
                        default=0
                    )
                )
            )

            growth_score = safe_float(
                get_value(
                    stock_info,
                    "Growth Score",
                    "growth_score",
                    default=get_value(
                        row,
                        "Growth Score",
                        "growth_score",
                        default=0
                    )
                )
            )

            signal = normalise_text(
                get_value(
                    stock_info,
                    "Signal",
                    "Momentum Signal",
                    "signal",
                    default=get_value(
                        row,
                        "Signal",
                        "Momentum Signal",
                        "signal",
                        default="UNKNOWN"
                    )
                )
            )

            conviction = normalise_text(
                get_value(
                    stock_info,
                    "AI Conviction",
                    "Conviction",
                    "Confidence",
                    default=get_value(
                        row,
                        "AI Conviction",
                        "Conviction",
                        "Confidence",
                        default="MEDIUM"
                    )
                )
            )

            sector = get_value(
                row,
                "Sector",
                default="Unknown"
            )

            sector_allocation = safe_float(
                get_value(
                    row,
                    "Sector Allocation %",
                    "Sector Allocation",
                    default=get_value(
                        stock_info,
                        "Sector Allocation %",
                        default=0
                    )
                )
            )

            action, reason = (
                evaluate_existing_holding(
                    investment_score=
                        investment_score,
                    quality_score=
                        quality_score,
                    growth_score=
                        growth_score,
                    signal=
                        signal
                )
            )

            decisions.append({

                "Ticker":
                    ticker,

                "Action":
                    action,

                "Reason":
                    reason,

                "Investment Score":
                    investment_score,

                "ETF Score":
                    None,

                "ETF Signal":
                    "N/A",

                "ETF Decision Confidence":
                    "N/A",

                "ETF Reduction %":
                    0,

                "Quality Score":
                    quality_score,

                "Growth Score":
                    growth_score,

                "Signal":
                    signal,

                "AI Conviction":
                    conviction,

                "Allocation %":
                    allocation,

                "Sector":
                    sector,

                "Sector Allocation %":
                    sector_allocation,

                "Portfolio Risk":
                    portfolio_risk,

                "Existing Holding":
                    "Yes",

                "Asset Type":
                    "STOCK"
            })

    # ========================================================
    # NEW OPPORTUNITIES
    # ========================================================

    if not opportunities.empty:

        for _, row in opportunities.iterrows():

            ticker = clean_ticker(
                row.get(
                    "Ticker",
                    ""
                )
            )

            if not ticker:
                continue

            if ticker in existing_tickers:
                continue

            asset_type = normalise_text(
                get_value(
                    row,
                    "Type",
                    "Asset Type",
                    default="STOCK"
                )
            )

            # =================================================
            # ETF OPPORTUNITIES
            #
            # ETF BUY NEW is deliberately not created here.
            # =================================================

            if asset_type == "ETF":
                continue

            allocation = safe_float(
                get_value(
                    row,
                    "Allocation %",
                    "Allocation",
                    default=0
                )
            )

            portfolio_risk = normalise_text(
                get_value(
                    row,
                    "Portfolio Risk",
                    "Risk",
                    default="NORMAL"
                )
            )

            # =================================================
            # NEW STOCK
            # =================================================

            investment_score = safe_float(
                get_value(
                    row,
                    "Investment Score",
                    "investment_score",
                    "Score",
                    default=0
                )
            )

            quality_score = safe_float(
                get_value(
                    row,
                    "Quality Score",
                    "quality_score",
                    default=0
                )
            )

            growth_score = safe_float(
                get_value(
                    row,
                    "Growth Score",
                    "growth_score",
                    default=0
                )
            )

            signal = normalise_text(
                get_value(
                    row,
                    "Signal",
                    "Momentum Signal",
                    "signal",
                    default="UNKNOWN"
                )
            )

            conviction = normalise_text(
                get_value(
                    row,
                    "AI Conviction",
                    "Conviction",
                    "Confidence",
                    default="MEDIUM"
                )
            )

            sector = get_value(
                row,
                "Sector",
                default="Unknown"
            )

            sector_allocation = safe_float(
                get_value(
                    row,
                    "Sector Allocation %",
                    "Sector Allocation",
                    default=0
                )
            )

            approved = approve_buy(
                investment_score=
                    investment_score,
                conviction=
                    conviction,
                allocation=
                    allocation,
                portfolio_risk=
                    portfolio_risk,
                sector_allocation=
                    sector_allocation
            )

            if approved:

                action = "BUY NEW"

                reason = (
                    "Strong investment score "
                    "and portfolio fit"
                )

            elif investment_score >= 65:

                action = "WATCH"

                reason = (
                    "Promising opportunity but does not "
                    "currently meet BUY criteria"
                )

            else:

                action = "HOLD"

                reason = (
                    "Opportunity does not currently meet "
                    "the required investment threshold"
                )

            decisions.append({

                "Ticker":
                    ticker,
                "Name":
                    get_value(
                        row,
                        "Name",
                        "name",
                        default=""
                    ),
                "Action":
                    action,

                "Reason":
                    reason,

                "Investment Score":
                    investment_score,

                "ETF Score":
                    None,

                "ETF Signal":
                    "N/A",

                "ETF Decision Confidence":
                    "N/A",

                "ETF Reduction %":
                    0,

                "Quality Score":
                    quality_score,

                "Growth Score":
                    growth_score,

                "Signal":
                    signal,

                "AI Conviction":
                    conviction,

                "Confidence Score":
                    safe_float(
                        get_value(
                            row,
                            "Confidence Score",
                            "confidence_score",
                            default=None
                        )
                    ),

                "Allocation %":
                    allocation,

                "Sector":
                    sector,

                "Sector Allocation %":
                    sector_allocation,

                "Portfolio Risk":
                    portfolio_risk,

                "Existing Holding":
                    "No",

                "Asset Type":
                    "STOCK"
            })

    # ========================================================
    # RETURN
    # ========================================================

    if not decisions:
        return []

    result = pd.DataFrame(
        decisions
    )

    if "Ticker" in result.columns:

        result["Ticker"] = (
            result["Ticker"]
            .apply(clean_ticker)
        )

        result = result[
            result["Ticker"] != ""
        ]

    # ========================================================
    # DUPLICATES
    #
    # More severe portfolio actions take priority.
    # ========================================================

    if not result.empty:

        action_priority = {

            SELL_ACTION: 1,
            REDUCE_75_ACTION: 2,
            REDUCE_50_ACTION: 3,
            REDUCE_25_ACTION: 4,
            "BUY MORE": 5,
            "BUY NEW": 6,
            "WATCH": 7,
            "HOLD": 8
        }

        result["_Decision Priority"] = (
            result["Action"]
            .map(action_priority)
            .fillna(99)
        )

        result = (
            result
            .sort_values(
                [
                    "Ticker",
                    "_Decision Priority"
                ]
            )
            .drop_duplicates(
                subset=["Ticker"],
                keep="first"
            )
            .drop(
                columns=[
                    "_Decision Priority"
                ]
            )
        )

    # ========================================================
    # DECISION ORDER
    #
    # Most severe reductions first.
    # ========================================================

    action_order = {

        SELL_ACTION: 1,
        REDUCE_75_ACTION: 2,
        REDUCE_50_ACTION: 3,
        REDUCE_25_ACTION: 4,
        "BUY MORE": 5,
        "BUY NEW": 6,
        "WATCH": 7,
        "HOLD": 8
    }

    if not result.empty:

        result["_Priority"] = (
            result["Action"]
            .map(action_order)
            .fillna(9)
        )

        result = (
            result
            .sort_values(
                [
                    "_Priority",
                    "Ticker"
                ]
            )
            .drop(
                columns=[
                    "_Priority"
                ]
            )
            .reset_index(
                drop=True
            )
        )

    return result

