
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

The engine should HOLD unless there is a sufficiently strong
reason to BUY, BUY MORE or REDUCE.

ETF decisions are NOT recreated here.

ETF decision logic is owned exclusively by:

    analysis/etf_decisions.py

This module only wires the authoritative ETF decision into the
portfolio-level decision pipeline.

Capital allocation is handled separately by capital_allocator.py.
"""

import pandas as pd

from analysis.etf_decisions import decide_etf


# ============================================================
# HELPERS
# ============================================================

def safe_float(value, default=0.0):

    try:

        if value is None:
            return default

        if pd.isna(value):
            return default

        return float(value)

    except Exception:

        return default


def normalise_text(value, default="UNKNOWN"):

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

    investment_score = safe_float(
        investment_score
    )

    allocation = safe_float(
        allocation
    )

    sector_allocation = safe_float(
        sector_allocation
    )

    conviction = normalise_text(
        conviction
    )

    portfolio_risk = normalise_text(
        portfolio_risk
    )

    if investment_score < 75:
        return False

    if conviction not in (
        "HIGH",
        "VERY HIGH"
    ):
        return False

    if allocation >= 10:
        return False

    if portfolio_risk == "HIGH":
        return False

    if sector_allocation >= 30:
        return False

    return True


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
    Evaluate an existing stock holding.

    HOLD is the default for moderate or ambiguous situations.

    REDUCE is triggered when there is sufficiently strong evidence
    that the existing position no longer deserves its current
    allocation.

    The decision deliberately uses multiple levels of evidence:

        1. Very low Investment Score + bearish signal
        2. Low Investment Score + materially weak fundamentals
           + bearish signal
        3. Extremely weak Investment Score regardless of signal

    This prevents unnecessary turnover while ensuring that clearly
    deteriorating holdings are not incorrectly retained as HOLD.
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

    # ========================================================
    # STRONG HOLD
    # ========================================================

    if investment_score >= 85:

        return (
            "HOLD",
            "High investment score supports retaining the existing position"
        )

    # ========================================================
    # GOOD / MODERATE HOLD
    # ========================================================

    if investment_score >= 70:

        return (
            "HOLD",
            "Moderate-to-strong investment score with no sufficiently "
            "strong reason to change the existing position"
        )

    # ========================================================
    # CLEAR REDUCTION
    #
    # Very low score + bearish signal is sufficient evidence.
    #
    # This is the key rule that protects against retaining clearly
    # deteriorating positions such as CA.PA.
    # ========================================================

    if (
        investment_score < 30
        and
        signal in {
            "SELL",
            "STRONG SELL",
        }
    ):

        return (
            "REDUCE",
            "Very low investment score combined with a bearish "
            "signal indicates that the existing position should "
            "be reduced"
        )

    # ========================================================
    # EXTREMELY WEAK FUNDAMENTALS
    #
    # Even if the technical signal has not yet become SELL,
    # exceptionally weak fundamentals justify reducing exposure.
    # ========================================================

    if (
        investment_score < 30
        and
        quality_score < 30
        and
        growth_score < 30
    ):

        return (
            "REDUCE",
            "Very low investment score combined with materially "
            "weak quality and growth"
        )

    # ========================================================
    # LOW SCORE + WEAK FUNDAMENTALS + BEARISH SIGNAL
    # ========================================================

    if (
        investment_score < 45
        and
        quality_score < 50
        and
        growth_score < 40
        and
        signal in {
            "SELL",
            "STRONG SELL",
        }
    ):

        return (
            "REDUCE",
            "Low investment score combined with weak quality, "
            "weak growth and bearish signal"
        )

    # ========================================================
    # MODERATE SCORE
    #
    # Below the BUY threshold does NOT automatically mean sell.
    # This preserves the portfolio's HOLD-by-default behaviour.
    # ========================================================

    if investment_score >= 45:

        return (
            "HOLD",
            "Below buy threshold but not weak enough to justify "
            "a reduction in the existing position"
        )

    # ========================================================
    # LOW SCORE BUT INSUFFICIENT EVIDENCE
    # ========================================================

    return (
        "HOLD",
        "Low investment score but insufficient evidence to justify "
        "reducing the existing position"
    )


# ============================================================
# PORTFOLIO DECISION ENGINE
# ============================================================

def generate_portfolio_decisions(
    portfolio_summary,
    opportunities=None
):

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
            #
            # ETF decisioning is delegated entirely to
            # analysis.etf_decisions.decide_etf().
            #
            # No ETF rules are duplicated here.
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
    #
    # ETF opportunities are deliberately NOT processed here.
    #
    # The current ETF requirement is to assess existing ETF
    # holdings only: BUY MORE / HOLD / REDUCE / SELL.
    #
    # Stock opportunities continue to use the existing stock
    # BUY NEW logic.
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
            # Do not create BUY NEW ETF decisions here.
            # ETF decisioning is currently limited to existing
            # ETF holdings.
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
                    "Strong investment score, conviction "
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
    # ========================================================

    if not result.empty:

        action_priority = {

            "REDUCE": 1,
            "SELL": 1,
            "BUY MORE": 2,
            "BUY NEW": 3,
            "WATCH": 4,
            "HOLD": 5
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
    # ========================================================

    action_order = {

        "REDUCE": 1,
        "SELL": 1,
        "BUY MORE": 2,
        "BUY NEW": 3,
        "WATCH": 4,
        "HOLD": 5
    }

    if not result.empty:

        result["_Priority"] = (
            result["Action"]
            .map(action_order)
            .fillna(6)
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

