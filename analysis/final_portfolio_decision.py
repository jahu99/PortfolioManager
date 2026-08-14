"""
Final Portfolio Decision Engine

Purpose
-------
Consolidates the outputs of the portfolio analysis, AI analysis,
portfolio management and capital allocation engines into one
authoritative, report-ready decision table.

Architecture
------------
Capital Allocation is the authoritative source for transaction actions.

This module does NOT independently decide whether a security should
be bought, increased, reduced or sold.

The flow is:

    Analysis
        ↓
    Portfolio Intelligence
        ↓
    Capital Allocator
        ↓
    Final Portfolio Decisions
        ↓
    Excel Report

Rules
-----
- Capital Allocation determines the final action.
- Existing holdings absent from Capital Allocation default to HOLD.
- New BUY NEW opportunities are added from Capital Allocation.
- AI and portfolio analysis provide context, not transaction authority.
- ETFs and unscored assets are handled without treating a missing score
  as a negative investment score.
- No unnecessary portfolio turnover is introduced.
"""

import pandas as pd


# ============================================================
# HELPERS
# ============================================================

def safe_float(value, default=0.0):
    """Safely convert a value to float."""

    try:
        if value is None:
            return default

        if pd.isna(value):
            return default

        return float(value)

    except Exception:
        return default


def safe_text(value, default=""):
    """Safely convert a value to stripped text."""

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

    return value


def safe_dataframe(data):
    """Convert supported input data into a DataFrame."""

    if data is None:
        return pd.DataFrame()

    if isinstance(data, pd.DataFrame):
        return data.copy()

    try:
        return pd.DataFrame(data)

    except Exception:
        return pd.DataFrame()


def normalise_tickers(df):
    """Normalise ticker symbols to uppercase."""

    if not df.empty and "Ticker" in df.columns:

        df["Ticker"] = (
            df["Ticker"]
            .astype(str)
            .str.strip()
            .str.upper()
        )

    return df


def is_valid_score(value):
    """
    Determine whether an actual investment score exists.

    A score of zero is treated as unavailable rather than as a
    genuinely poor score. This is important for ETFs and other
    assets that do not use the stock scoring model.
    """

    try:

        if value is None:
            return False

        if pd.isna(value):
            return False

        return float(value) > 0

    except Exception:
        return False


def normalise_capital_action(action):
    """
    Normalise Capital Allocator action names.

    The Capital Allocator remains the authoritative source.
    """

    action = safe_text(action).upper()

    if action.startswith("REDUCE"):
        return action

    if action == "SELL":
        return "SELL"

    if action in {
        "BUY NEW",
        "BUY MORE",
        "BUY",
        "HOLD",
        "WATCH",
        "REVIEW",
    }:
        return action

    return "HOLD"


# ============================================================
# ACTION PRIORITY
# ============================================================

ACTION_PRIORITY = {
    "SELL": 1,
    "REDUCE": 2,
    "BUY MORE": 3,
    "BUY NEW": 4,
    "BUY": 5,
    "WATCH": 6,
    "REVIEW": 7,
    "HOLD": 8,
}


# ============================================================
# REVIEW TRIGGERS
# ============================================================

def build_review_triggers(
    asset_type,
    investment_score_available,
):
    """Build appropriate review triggers for the security."""

    asset_type = safe_text(
        asset_type
    ).upper()

    if (
        asset_type == "ETF"
        or not investment_score_available
    ):

        return [
            "Underlying/index exposure changes materially",
            "Investment case deteriorates",
            "Portfolio allocation becomes excessive",
            "Asset no longer supports portfolio objectives",
        ]

    return [
        "Investment score falls below 45",
        "Trend breaks below 200 DMA",
        "Quality score deteriorates materially",
        "Growth score deteriorates materially",
        "Signal becomes STRONG SELL",
    ]


# ============================================================
# RISKS
# ============================================================

def build_risks(
    portfolio_risk,
    signal,
    quality_score,
    growth_score,
    investment_score_available,
):
    """Build portfolio and security-level risk factors."""

    risks = []

    if portfolio_risk == "HIGH":
        risks.append(
            "Portfolio risk is currently high"
        )

    if signal in {
        "SELL",
        "STRONG SELL",
    }:
        risks.append(
            "Technical signal is bearish"
        )

    if (
        investment_score_available
        and quality_score > 0
        and quality_score < 50
    ):
        risks.append(
            "Quality score is weak"
        )

    if (
        investment_score_available
        and growth_score > 0
        and growth_score < 40
    ):
        risks.append(
            "Growth score is weak"
        )

    return risks


# ============================================================
# ACTION DESCRIPTION
# ============================================================

def build_capital_action_description(action):
    """Create a human-readable description of the capital action."""

    if action == "BUY NEW":

        return (
            "Allocate new capital to this opportunity"
        )

    if action == "BUY MORE":

        return (
            "Increase the existing allocation"
        )

    if action.startswith("REDUCE"):

        return (
            "Release capital and reallocate to stronger "
            "risk-adjusted opportunities"
        )

    if action == "SELL":

        return (
            "Exit the position and redeploy released capital"
        )

    return (
        "Maintain existing allocation"
    )


# ============================================================
# ACTIONS
# ============================================================

def build_actions(action):
    """Create implementation actions for the final decision."""

    if action == "BUY NEW":

        return [
            "Implement the allocated new position "
            "within the approved capital limit"
        ]

    if action == "BUY MORE":

        return [
            "Increase the position according to the "
            "capital allocation plan"
        ]

    if action.startswith("REDUCE"):

        return [
            "Review and execute the specified reduction"
        ]

    if action == "SELL":

        return [
            "Review and execute the planned exit"
        ]

    return [
        "Continue monitoring without unnecessary turnover"
    ]


# ============================================================
# CONFIDENCE
# ============================================================

def calculate_confidence(
    action,
    investment_score,
    investment_score_available,
    ai_conviction="",
    ai_holding_conviction="",
):
    """
    Calculate presentation confidence.

    This does NOT alter the Capital Allocator action.
    """

    if action in {
        "SELL",
    } or action.startswith("REDUCE"):

        return "HIGH"

    if action in {
        "BUY NEW",
        "BUY MORE",
    }:

        if (
            investment_score_available
            and investment_score >= 85
        ):
            return "HIGH"

        if ai_conviction in {
            "HIGH",
            "VERY HIGH",
        }:
            return "HIGH"

        if ai_holding_conviction in {
            "HIGH",
            "VERY HIGH",
        }:
            return "HIGH"

    return "MEDIUM"


# ============================================================
# EXISTING HOLDING DECISION
# ============================================================

def build_existing_holding_decision(
    row,
    allocation_row,
    portfolio_risk,
):
    """
    Build the final decision for an existing portfolio holding.

    Capital Allocation remains authoritative.
    """

    ticker = safe_text(
        row.get("Ticker", "")
    )

    # --------------------------------------------------------
    # Scores
    # --------------------------------------------------------

    investment_raw = row.get(
        "Investment Score",
        row.get(
            "Investment Score_Decision",
            None,
        ),
    )

    quality_raw = row.get(
        "Quality Score",
        row.get(
            "Quality Score_Decision",
            None,
        ),
    )

    growth_raw = row.get(
        "Growth Score",
        row.get(
            "Growth Score_Decision",
            None,
        ),
    )

    investment_score = safe_float(
        investment_raw
    )

    quality_score = safe_float(
        quality_raw
    )

    growth_score = safe_float(
        growth_raw
    )

    investment_score_available = is_valid_score(
        investment_raw
    )

    # --------------------------------------------------------
    # Signal
    # --------------------------------------------------------

    signal = safe_text(
        row.get(
            "Signal",
            row.get(
                "Signal_Decision",
                "",
            ),
        )
    ).upper()

    # --------------------------------------------------------
    # Existing portfolio decision
    # --------------------------------------------------------

    existing_reason = safe_text(
        row.get(
            "Reason",
            "",
        )
    )

    # --------------------------------------------------------
    # AI
    # --------------------------------------------------------

    ai_decision = safe_text(
        row.get(
            "AI Decision",
            "",
        )
    ).upper()

    ai_conviction = safe_text(
        row.get(
            "AI Conviction",
            "",
        )
    ).upper()

    ai_holding_decision = safe_text(
        row.get(
            "AI Holding Decision",
            "",
        )
    ).upper()

    ai_holding_conviction = safe_text(
        row.get(
            "AI Holding Conviction",
            "",
        )
    ).upper()

    # --------------------------------------------------------
    # Capital Allocation
    # --------------------------------------------------------

    if allocation_row is not None:

        final_action = normalise_capital_action(
            allocation_row.get(
                "Action",
                allocation_row.get(
                    "Capital Allocation Action",
                    "HOLD",
                ),
            )
        )

        allocation_reason = safe_text(
            allocation_row.get(
                "Reason",
                "",
            )
        )

        allocation_amount = safe_float(
            allocation_row.get(
                "Amount",
                allocation_row.get(
                    "Buy Value",
                    0,
                ),
            )
        )

        released_capital = safe_float(
            allocation_row.get(
                "Released Capital",
                0,
            )
        )

        buy_value = safe_float(
            allocation_row.get(
                "Buy Value",
                0,
            )
        )

        buy_quantity = safe_float(
            allocation_row.get(
                "Buy Quantity",
                0,
            )
        )

        reduction_percent = safe_float(
            allocation_row.get(
                "Reduction %",
                0,
            )
        )

        reduction_quantity = safe_float(
            allocation_row.get(
                "Reduction Quantity",
                0,
            )
        )

        funding_source = safe_text(
            allocation_row.get(
                "Funding Source",
                "",
            )
        )

        investment_rank = safe_float(
            allocation_row.get(
                "Investment Rank",
                0,
            )
        )

        reduction_rank = safe_float(
            allocation_row.get(
                "Reduction Rank",
                0,
            )
        )

    else:

        # Existing holdings that Capital Allocation has not
        # selected remain HOLD.

        final_action = "HOLD"

        allocation_reason = ""

        allocation_amount = 0.0
        released_capital = 0.0
        buy_value = 0.0
        buy_quantity = 0.0
        reduction_percent = 0.0
        reduction_quantity = 0.0

        funding_source = ""

        investment_rank = 0.0
        reduction_rank = 0.0

    # --------------------------------------------------------
    # Reason
    # --------------------------------------------------------

    if allocation_reason:

        final_reason = allocation_reason

    elif final_action == "BUY NEW":

        final_reason = (
            "Capital allocation identifies this as a "
            "new portfolio opportunity"
        )

    elif final_action == "BUY MORE":

        final_reason = (
            "Capital allocation identifies this as an "
            "existing holding suitable for additional capital"
        )

    elif final_action.startswith("REDUCE"):

        final_reason = (
            "Capital allocation recommends reducing "
            "the existing position"
        )

    elif final_action == "SELL":

        final_reason = (
            "Capital allocation recommends exiting "
            "the existing position"
        )

    elif existing_reason:

        final_reason = existing_reason

    elif ai_holding_decision == "HOLD":

        final_reason = (
            "Existing holding retained; no capital "
            "reallocation currently required"
        )

    elif not investment_score_available:

        final_reason = (
            "Existing holding retained because "
            "investment analysis is unavailable"
        )

    else:

        final_reason = (
            "Existing holding retained; no sufficiently "
            "strong capital allocation change is required"
        )

    # --------------------------------------------------------
    # Confidence
    # --------------------------------------------------------

    confidence = calculate_confidence(
        action=final_action,
        investment_score=investment_score,
        investment_score_available=investment_score_available,
        ai_conviction=ai_conviction,
        ai_holding_conviction=ai_holding_conviction,
    )

    # --------------------------------------------------------
    # Review triggers
    # --------------------------------------------------------

    asset_type = safe_text(
        row.get(
            "Asset Type",
            "",
        )
    ).upper()

    review_triggers = build_review_triggers(
        asset_type,
        investment_score_available,
    )

    # --------------------------------------------------------
    # Risks
    # --------------------------------------------------------

    risks = build_risks(
        portfolio_risk=portfolio_risk,
        signal=signal,
        quality_score=quality_score,
        growth_score=growth_score,
        investment_score_available=investment_score_available,
    )

    # --------------------------------------------------------
    # Actions
    # --------------------------------------------------------

    actions = build_actions(
        final_action
    )

    # --------------------------------------------------------
    # Result
    # --------------------------------------------------------

    return {

        "Ticker": ticker,

        "Final Action":
            final_action,

        "Final Reason":
            final_reason,

        "Investment Score":
            investment_score,

        "Quality Score":
            quality_score,

        "Growth Score":
            growth_score,

        "Signal":
            signal,

        "AI Decision":
            ai_decision,

        "AI Conviction":
            ai_conviction,

        "AI Holding Decision":
            ai_holding_decision,

        "AI Holding Conviction":
            ai_holding_conviction,

        "Portfolio Risk":
            portfolio_risk,

        "Confidence":
            confidence,

        "Capital Allocation Action":
            build_capital_action_description(
                final_action
            ),

        "Allocation Amount":
            allocation_amount,

        "Buy Quantity":
            buy_quantity,

        "Buy Value":
            buy_value,

        "Reduction %":
            reduction_percent,

        "Reduction Quantity":
            reduction_quantity,

        "Released Capital":
            released_capital,

        "Funding Source":
            funding_source,

        "Investment Rank":
            investment_rank,

        "Reduction Rank":
            reduction_rank,

        "Review Triggers":
            review_triggers,

        "Risks":
            risks,

        "Actions":
            actions,

        "Sector":
            safe_text(
                row.get(
                    "Sector",
                    "Unknown",
                ),
                "Unknown",
            ),

    }


# ============================================================
# NEW CAPITAL ALLOCATION OPPORTUNITY
# ============================================================

def build_new_opportunity(
    allocation_row,
    portfolio_risk,
):
    """
    Create a final decision record for a new opportunity that
    is not already present in portfolio_summary.
    """

    ticker = safe_text(
        allocation_row.get(
            "Ticker",
            "",
        )
    )

    action = normalise_capital_action(
        allocation_row.get(
            "Action",
            allocation_row.get(
                "Capital Allocation Action",
                "HOLD",
            ),
        )
    )

    investment_score = safe_float(
        allocation_row.get(
            "Investment Score",
            0,
        )
    )

    quality_score = safe_float(
        allocation_row.get(
            "Quality Score",
            0,
        )
    )

    growth_score = safe_float(
        allocation_row.get(
            "Growth Score",
            0,
        )
    )

    signal = safe_text(
        allocation_row.get(
            "Signal",
            "",
        )
    ).upper()

    ai_decision = safe_text(
        allocation_row.get(
            "AI Decision",
            "",
        )
    ).upper()

    ai_conviction = safe_text(
        allocation_row.get(
            "AI Conviction",
            "",
        )
    ).upper()

    reason = safe_text(
        allocation_row.get(
            "Reason",
            "",
        )
    )

    buy_quantity = safe_float(
        allocation_row.get(
            "Buy Quantity",
            0,
        )
    )

    buy_value = safe_float(
        allocation_row.get(
            "Buy Value",
            allocation_row.get(
                "Amount",
                0,
            ),
        )
    )

    funding_source = safe_text(
        allocation_row.get(
            "Funding Source",
            "Available Capital",
        ),
        "Available Capital",
    )

    investment_rank = safe_float(
        allocation_row.get(
            "Investment Rank",
            0,
        )
    )

    # --------------------------------------------------------
    # Reason
    # --------------------------------------------------------

    if reason:

        final_reason = reason

    elif action == "BUY NEW":

        final_reason = (
            "Capital allocation identifies a new "
            "portfolio opportunity"
        )

    else:

        final_reason = (
            "Capital allocation identifies an opportunity "
            "for additional investment"
        )

    # --------------------------------------------------------
    # Confidence
    # --------------------------------------------------------

    confidence = calculate_confidence(
        action=action,
        investment_score=investment_score,
        investment_score_available=is_valid_score(
            investment_score
        ),
        ai_conviction=ai_conviction,
    )

    # --------------------------------------------------------
    # Review triggers
    # --------------------------------------------------------

    review_triggers = [
        "Investment score falls below 75",
        "Technical trend deteriorates",
        "Portfolio risk increases materially",
    ]

    # --------------------------------------------------------
    # Result
    # --------------------------------------------------------

    return {

        "Ticker":
            ticker,

        "Final Action":
            action,

        "Final Reason":
            final_reason,

        "Investment Score":
            investment_score,

        "Quality Score":
            quality_score,

        "Growth Score":
            growth_score,

        "Signal":
            signal,

        "AI Decision":
            ai_decision,

        "AI Conviction":
            ai_conviction,

        "AI Holding Decision":
            "",

        "AI Holding Conviction":
            "",

        "Portfolio Risk":
            portfolio_risk,

        "Confidence":
            confidence,

        "Capital Allocation Action":
            build_capital_action_description(
                action
            ),

        "Allocation Amount":
            buy_value,

        "Buy Quantity":
            buy_quantity,

        "Buy Value":
            buy_value,

        "Reduction %":
            0.0,

        "Reduction Quantity":
            0.0,

        "Released Capital":
            0.0,

        "Funding Source":
            funding_source,

        "Investment Rank":
            investment_rank,

        "Reduction Rank":
            0.0,

        "Review Triggers":
            review_triggers,

        "Risks":
            [],

        "Actions":
            build_actions(
                action
            ),

        "Sector":
            safe_text(
                allocation_row.get(
                    "Sector",
                    "Unknown",
                ),
                "Unknown",
            ),

    }


# ============================================================
# MAIN ENGINE
# ============================================================

def generate_final_portfolio_decisions(
    portfolio_summary,
    portfolio_decisions,
    portfolio_ai_review,
    portfolio_manager_review,
    portfolio_health,
    capital_allocation,
):
    """
    Consolidate all portfolio intelligence into the definitive
    portfolio decision table.

    Capital Allocation is the sole authority for transaction action.
    """

    # --------------------------------------------------------
    # Normalise inputs
    # --------------------------------------------------------

    portfolio_summary = normalise_tickers(
        safe_dataframe(
            portfolio_summary
        )
    )

    portfolio_decisions = normalise_tickers(
        safe_dataframe(
            portfolio_decisions
        )
    )

    portfolio_ai_review = normalise_tickers(
        safe_dataframe(
            portfolio_ai_review
        )
    )

    capital_allocation = normalise_tickers(
        safe_dataframe(
            capital_allocation
        )
    )

    if isinstance(
        portfolio_health,
        dict,
    ):
        health = portfolio_health
    else:
        health = {}

    portfolio_risk = safe_text(
        health.get(
            "Risk Level",
            "NORMAL",
        ),
        "NORMAL",
    ).upper()

    # --------------------------------------------------------
    # Start with portfolio holdings
    # --------------------------------------------------------

    final = portfolio_summary.copy()

    # --------------------------------------------------------
    # Merge portfolio decisions
    # --------------------------------------------------------

    if (
        not portfolio_decisions.empty
        and "Ticker" in portfolio_decisions.columns
    ):

        decision_columns = [
            "Ticker",
            "Action",
            "Reason",
            "Investment Score",
            "Quality Score",
            "Growth Score",
            "AI Decision",
            "AI Conviction",
            "Signal",
            "Sector",
        ]

        decision_columns = [
            column
            for column in decision_columns
            if column in portfolio_decisions.columns
        ]

        if len(decision_columns) > 1:

            decision_data = (
                portfolio_decisions[
                    decision_columns
                ]
                .drop_duplicates(
                    subset=["Ticker"],
                    keep="first",
                )
            )

            final = final.merge(
                decision_data,
                on="Ticker",
                how="left",
                suffixes=(
                    "",
                    "_Decision",
                ),
            )

    # --------------------------------------------------------
    # Merge AI portfolio review
    # --------------------------------------------------------

    if (
        not portfolio_ai_review.empty
        and "Ticker" in portfolio_ai_review.columns
    ):

        ai_columns = [
            "Ticker",
            "AI Holding Decision",
            "AI Holding Conviction",
            "AI Holding Reasons",
            "AI Holding Risks",
            "AI Holding Actions",
            "AI Holding Review Triggers",
        ]

        ai_columns = [
            column
            for column in ai_columns
            if column in portfolio_ai_review.columns
        ]

        if len(ai_columns) > 1:

            ai_data = (
                portfolio_ai_review[
                    ai_columns
                ]
                .drop_duplicates(
                    subset=["Ticker"],
                    keep="first",
                )
            )

            final = final.merge(
                ai_data,
                on="Ticker",
                how="left",
                suffixes=(
                    "",
                    "_AI",
                ),
            )

    # --------------------------------------------------------
    # Build Capital Allocation lookup
    # --------------------------------------------------------

    allocation_lookup = {}

    if (
        not capital_allocation.empty
        and "Ticker" in capital_allocation.columns
    ):

        allocation_data = (
            capital_allocation
            .drop_duplicates(
                subset=["Ticker"],
                keep="first",
            )
        )

        for _, allocation_row in allocation_data.iterrows():

            ticker = safe_text(
                allocation_row.get(
                    "Ticker",
                    "",
                )
            )

            if ticker:
                allocation_lookup[ticker] = allocation_row

    # --------------------------------------------------------
    # Existing portfolio holdings
    # --------------------------------------------------------

    decisions = []

    for _, row in final.iterrows():

        ticker = safe_text(
            row.get(
                "Ticker",
                "",
            )
        )

        if not ticker:
            continue

        allocation_row = allocation_lookup.get(
            ticker
        )

        decision = build_existing_holding_decision(
            row=row,
            allocation_row=allocation_row,
            portfolio_risk=portfolio_risk,
        )

        decisions.append(
            decision
        )

    # --------------------------------------------------------
    # Add new Capital Allocation opportunities
    # --------------------------------------------------------

    existing_tickers = {
        decision["Ticker"]
        for decision in decisions
    }

    for ticker, allocation_row in allocation_lookup.items():

        if ticker in existing_tickers:
            continue

        allocation_action = normalise_capital_action(
            allocation_row.get(
                "Action",
                allocation_row.get(
                    "Capital Allocation Action",
                    "HOLD",
                ),
            )
        )

        if allocation_action not in {
            "BUY NEW",
            "BUY",
            "BUY MORE",
        }:
            continue

        decision = build_new_opportunity(
            allocation_row=allocation_row,
            portfolio_risk=portfolio_risk,
        )

        decisions.append(
            decision
        )

    # --------------------------------------------------------
    # Create result
    # --------------------------------------------------------

    result = pd.DataFrame(
        decisions
    )

    if result.empty:
        return result

    # --------------------------------------------------------
    # Ensure consistent column order
    # --------------------------------------------------------

    preferred_columns = [

        "Ticker",
        "Final Action",
        "Final Reason",

        "Investment Score",
        "Quality Score",
        "Growth Score",
        "Signal",

        "Confidence",
        "Portfolio Risk",

        "Capital Allocation Action",
        "Allocation Amount",

        "Buy Quantity",
        "Buy Value",

        "Reduction %",
        "Reduction Quantity",
        "Released Capital",

        "Funding Source",

        "Investment Rank",
        "Reduction Rank",

        "AI Decision",
        "AI Conviction",
        "AI Holding Decision",
        "AI Holding Conviction",

        "Review Triggers",
        "Risks",
        "Actions",

        "Sector",
    ]

    existing_columns = [
        column
        for column in preferred_columns
        if column in result.columns
    ]

    remaining_columns = [
        column
        for column in result.columns
        if column not in existing_columns
    ]

    result = result[
        existing_columns + remaining_columns
    ]

    # --------------------------------------------------------
    # Deduplicate
    # --------------------------------------------------------

    result["Priority"] = (
        result["Final Action"]
        .map(ACTION_PRIORITY)
        .fillna(99)
    )

    result = (
        result
        .sort_values(
            [
                "Ticker",
                "Priority",
            ]
        )
        .drop_duplicates(
            subset=["Ticker"],
            keep="first",
        )
        .drop(
            columns=["Priority"]
        )
        .reset_index(
            drop=True
        )
    )

    return result