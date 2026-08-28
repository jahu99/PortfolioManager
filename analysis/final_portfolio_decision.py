"""
Final Portfolio Decision Engine

Purpose
-------
Produce the final governed portfolio decision from the outputs of the
portfolio analysis and the agreed AI decision chain.

Architecture
------------

    Existing Analytical Engines
                |
                v
    Rules-Based Portfolio Proposal
                |
                v
    AI Decision Context
                |
                v
    AI Decision Scoring
                |
                v
    AI Decision Layer
                |
                v
    AI Decision Explanation
                |
                v
    AI Portfolio Reviewer / Llama
                |
                v
    AI Decision Reconciler
                |
                v
    FINAL PORTFOLIO DECISION
                |
                v
    Capital Allocation / Reporting

Important
---------
This module is the final governed decision gate.

It does NOT:

    - recalculate investment scores
    - recalculate technical indicators
    - change scoring weights
    - allocate capital
    - determine position sizing
    - execute trades

It DOES:

    - review all existing holdings
    - review genuine BUY NEW candidates
    - execute the complete AI decision chain
    - enforce ownership consistency
    - preserve HOLD as the default
    - prevent unavailable LLM review from approving trades
    - respect reconciler output
    - preserve capital-allocation sizing information
    - exclude CASH from the final decision population

Population
----------
Final Portfolio Decisions contains:

    - every existing investment holding
    - every non-owned BUY NEW proposal

It excludes:

    - CASH
    - non-owned HOLD
    - non-owned BUY MORE
    - non-owned REDUCE
    - non-owned SELL

Compatibility
-------------
The module preserves the public interfaces used by main.py and
the existing AI decision test harness.
"""

from __future__ import annotations

from typing import Any

import pandas as pd


# ============================================================
# AGREED AI DECISION CHAIN
# ============================================================

from agents.ai_decision_context import (
    build_ai_decision_context,
)

from agents.ai_decision_layer import (
    generate_ai_decision,
)

from agents.ai_decision_explanation import (
    explain_ai_decision,
)

from agents.ai_portfolio_reviewer import (
    review_ai_decision,
)

from agents.ai_decision_reconciler import (
    reconcile_ai_decision,
)

from data.database import (
    get_latest_recommendation_id,
)

from analysis.audit import (
    get_connection,
    start_audit_run,
    record_decision_audit,
    get_audit_run_counts,
    complete_audit_run,
    fail_audit_run,
)


# ============================================================
# CONSTANTS
# ============================================================

VALID_ACTIONS = {
    "BUY NEW",
    "BUY MORE",
    "HOLD",
    "REDUCE",
    "SELL",
    "WATCH",
    "REVIEW",
}

VALID_ASSET_TYPES = {
    "STOCK",
    "ETF",
}


# ============================================================
# GENERIC HELPERS
# ============================================================

def safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    """Safely convert a scalar value to float."""

    try:

        if value is None:
            return default

        if isinstance(
            value,
            bool,
        ):
            return float(value)

        if pd.isna(value):
            return default

        return float(value)

    except (
        TypeError,
        ValueError,
    ):

        return default


def safe_text(
    value: Any,
    default: str = "",
) -> str:
    """Safely convert a value to stripped text."""

    if value is None:
        return default

    try:

        if pd.isna(value):
            return default

    except Exception:
        pass

    try:

        text = str(
            value
        ).strip()

    except Exception:

        return default

    return (
        text
        if text
        else default
    )


def upper_text(
    value: Any,
    default: str = "",
) -> str:
    """Safely normalise text to uppercase."""

    return safe_text(
        value,
        default,
    ).upper()


def safe_bool(
    value: Any,
    default: bool = False,
) -> bool:
    """Safely convert common boolean representations."""

    if isinstance(
        value,
        bool,
    ):
        return value

    if value is None:
        return default

    text = upper_text(
        value
    )

    if text in {
        "TRUE",
        "YES",
        "Y",
        "1",
        "OWNED",
        "EXISTING",
    }:
        return True

    if text in {
        "FALSE",
        "NO",
        "N",
        "0",
        "NEW",
        "NOT OWNED",
    }:
        return False

    return default


def safe_list(
    value: Any,
) -> list:
    """Safely convert a value to a list."""

    if value is None:
        return []

    if isinstance(
        value,
        list,
    ):
        return value

    if isinstance(
        value,
        tuple,
    ):
        return list(
            value
        )

    return [
        value
    ]


def first_value(
    *values: Any,
    default: Any = None,
) -> Any:
    """Return the first usable value."""

    for value in values:

        if value is None:
            continue

        try:

            if pd.isna(value):
                continue

        except Exception:
            pass

        if (
            isinstance(
                value,
                str,
            )
            and
            not value.strip()
        ):
            continue

        return value

    return default


def safe_dataframe(
    value: Any,
) -> pd.DataFrame:
    """Convert supported input to a DataFrame."""

    if value is None:
        return pd.DataFrame()

    if isinstance(
        value,
        pd.DataFrame,
    ):
        return value.copy()

    if isinstance(
        value,
        pd.Series,
    ):
        return pd.DataFrame(
            [
                value.to_dict()
            ]
        )

    if isinstance(
        value,
        dict,
    ):
        return pd.DataFrame(
            [value]
        )

    try:

        return pd.DataFrame(
            value
        )

    except Exception:

        return pd.DataFrame()


def normalise_tickers(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """Normalise ticker symbols."""

    if (
        not dataframe.empty
        and
        "Ticker" in dataframe.columns
    ):

        dataframe[
            "Ticker"
        ] = (
            dataframe[
                "Ticker"
            ]
            .astype(str)
            .str.strip()
            .str.upper()
        )

    return dataframe


def row_value(
    row: dict,
    *names: str,
    default: Any = None,
) -> Any:
    """Retrieve a value from a dictionary using multiple aliases."""

    if not isinstance(
        row,
        dict,
    ):
        return default

    for name in names:

        if name in row:

            value = row.get(
                name
            )

            if value is not None:

                try:

                    if not pd.isna(value):
                        return value

                except Exception:

                    return value

    normalised = {
        str(key)
        .strip()
        .lower()
        .replace(
            "_",
            " ",
        ):
        value

        for key, value
        in row.items()
    }

    for name in names:

        key = (
            str(name)
            .strip()
            .lower()
            .replace(
                "_",
                " ",
            )
        )

        if key in normalised:

            value = normalised[
                key
            ]

            if value is not None:

                return value

    return default


# ============================================================
# RECORD HELPERS
# ============================================================

def get_ticker(
    row: dict,
) -> str:
    """Get ticker."""

    return upper_text(
        row_value(
            row,
            "Ticker",
            "ticker",
            "Symbol",
            "symbol",
            default="",
        )
    )


def get_asset_type(
    row: dict,
) -> str:
    """Get asset type."""

    value = upper_text(
        row_value(
            row,
            "Asset Type",
            "asset_type",
            "Type",
            "type",
            default="STOCK",
        ),
        "STOCK",
    )

    if value in {
        "EQUITY",
        "SHARE",
        "SHARES",
    }:
        return "STOCK"

    if value == "ETF":
        return "ETF"

    return "STOCK"


def get_quantity(
    row: dict,
) -> float:
    """Get holding quantity."""

    return safe_float(
        row_value(
            row,
            "Quantity",
            "quantity",
            "Qty",
            "qty",
            "Shares",
            "shares",
            default=0,
        )
    )


def is_owned(
    row: dict,
) -> bool:
    """Determine whether the security is currently held."""

    quantity = get_quantity(
        row
    )

    if quantity > 0:
        return True

    return safe_bool(
        row_value(
            row,
            "Existing Holding",
            "existing_holding",
            "Owned",
            "owned",
            default=False,
        )
    )


def get_action(
    row: dict,
) -> str:
    """Get the upstream proposed action."""

    action = upper_text(
        row_value(
            row,
            "Proposed Action",
            "proposed_action",
            "Action",
            "action",
            "Decision",
            "decision",
            "Recommendation",
            "recommendation",
            default="HOLD",
        ),
        "HOLD",
    )

    if action.startswith(
        "REDUCE"
    ):
        return action

    if action in VALID_ACTIONS:
        return action

    return "HOLD"


def get_market_value(
    row: dict,
) -> float:
    """Get market value."""

    return safe_float(
        row_value(
            row,
            "Market Value",
            "market_value",
            "Current Value",
            "Value",
            default=0,
        )
    )


def get_allocation_pct(
    row: dict,
) -> float:
    """Get portfolio allocation percentage."""

    return safe_float(
        row_value(
            row,
            "Allocation %",
            "allocation_pct",
            "Portfolio Allocation %",
            "Portfolio %",
            default=0,
        )
    )


# ============================================================
# CAPITAL ALLOCATION HELPERS
# ============================================================

def get_capital_allocation_dataframe(
    capital_allocation: Any,
) -> pd.DataFrame:
    """
    Extract the Capital Allocation dataframe.

    Supports the dictionary structure returned by the capital
    allocation engine.
    """

    if isinstance(
        capital_allocation,
        dict,
    ):

        value = capital_allocation.get(
            "Capital Allocation"
        )

        if isinstance(
            value,
            pd.DataFrame,
        ):

            return value.copy()

        if value is not None:

            return safe_dataframe(
                value
            )

    return safe_dataframe(
        capital_allocation
    )


def build_capital_lookup(
    capital_allocation: Any,
) -> dict[str, dict]:
    """Create ticker-indexed capital allocation lookup."""

    dataframe = normalise_tickers(
        get_capital_allocation_dataframe(
            capital_allocation
        )
    )

    lookup = {}

    if dataframe.empty:
        return lookup

    for _, row in dataframe.iterrows():

        record = row.to_dict()

        ticker = get_ticker(
            record
        )

        if ticker:
            lookup[
                ticker
            ] = record

    return lookup


def get_capital_action(
    row: dict,
) -> str:
    """Get the Capital Allocator proposal."""

    action = upper_text(
        row_value(
            row,
            "Action",
            "Capital Allocation Action",
            "Proposed Action",
            default="HOLD",
        ),
        "HOLD",
    )

    if action.startswith(
        "REDUCE"
    ):
        return action

    if action in {
        "BUY NEW",
        "BUY MORE",
        "BUY",
        "SELL",
        "HOLD",
        "WATCH",
        "REVIEW",
    }:
        return action

    return "HOLD"


# ============================================================
# PORTFOLIO POPULATION
# ============================================================

def build_eligible_population(
    portfolio_summary: Any,
    portfolio_decisions: Any,
    capital_allocation: Any,
) -> list[dict]:
    """
    Build the exact Final Portfolio Decisions population.

    FD-02 — Population Governance
    ------------------------------

    The final population contains ONLY:

        1. Every currently owned investment holding.
        2. Every non-owned BUY NEW opportunity from Capital Allocation.

    Explicit exclusions:

        - CASH
        - non-owned HOLD
        - non-owned BUY MORE
        - non-owned REDUCE
        - non-owned SELL
        - non-owned WATCH
        - non-owned REVIEW

    Ownership is authoritative from portfolio_summary.

    Capital Allocation is authoritative for NEW BUY proposals.

    CASH is excluded at source and again immediately before the
    population is returned.

    This routine does not run the AI decision chain.
    It only establishes the population that the final decision
    engine is permitted to review.
    """

    # ============================================================
    # NORMALISE INPUT DATA
    # ============================================================

    holdings = normalise_tickers(
        safe_dataframe(
            portfolio_summary
        )
    )

    decisions = normalise_tickers(
        safe_dataframe(
            portfolio_decisions
        )
    )

    capital = normalise_tickers(
        get_capital_allocation_dataframe(
            capital_allocation
        )
    )

    # ============================================================
    # CASH EXCLUSION
    #
    # CASH must never enter the Final Portfolio Decisions
    # population, regardless of which upstream source contains it.
    #
    # Do this before constructing any lookup dictionaries.
    # ============================================================

    def remove_cash(
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:

        if dataframe.empty:
            return dataframe

        if "Ticker" not in dataframe.columns:
            return dataframe

        ticker_series = (
            dataframe[
                "Ticker"
            ]
            .astype(str)
            .str.strip()
            .str.upper()
        )

        return dataframe[
            ticker_series != "CASH"
        ].copy()

    holdings = remove_cash(
        holdings
    )

    decisions = remove_cash(
        decisions
    )

    capital = remove_cash(
        capital
    )

    # ============================================================
    # EXISTING HOLDINGS
    #
    # portfolio_summary is authoritative for ownership.
    #
    # Positive Quantity means the security is currently held.
    #
    # Do not use Capital Allocation to determine whether something
    # is owned.
    # ============================================================

    holding_lookup: dict[str, dict] = {}

    if (
        not holdings.empty
        and
        "Ticker" in holdings.columns
    ):

        for _, row in holdings.iterrows():

            record = row.to_dict()

            ticker = get_ticker(
                record
            )

            # Defensive CASH protection.
            if not ticker or ticker == "CASH":
                continue

            quantity = get_quantity(
                record
            )

            if quantity > 0:

                holding_lookup[
                    ticker
                ] = record

    # ============================================================
    # CAPITAL ALLOCATION LOOKUP
    # ============================================================

    capital_lookup = {}

    if (
        not capital.empty
        and
        "Ticker" in capital.columns
    ):

        for _, row in capital.iterrows():

            record = row.to_dict()

            ticker = get_ticker(
                record
            )

            # Defensive CASH protection.
            if not ticker or ticker == "CASH":
                continue

            capital_lookup[
                ticker
            ] = record

    # ============================================================
    # BUILD POPULATION
    # ============================================================

    population: dict[str, dict] = {}

    # ============================================================
    # 1. ADD EVERY EXISTING HOLDING
    #
    # Existing holdings are always eligible for final portfolio
    # review, regardless of whether Capital Allocation currently
    # proposes HOLD, BUY MORE, REDUCE or SELL.
    # ============================================================

    for ticker, holding in holding_lookup.items():

        # Absolute final CASH safety check.
        if ticker == "CASH":
            continue

        base = dict(
            holding
        )

        allocation_row = capital_lookup.get(
            ticker
        )

        # Merge Capital Allocation fields without allowing the
        # allocation row to overwrite authoritative holding data.
        if allocation_row:

            for key, value in allocation_row.items():

                if key not in base:

                    base[
                        key
                    ] = value

                else:

                    try:

                        if pd.isna(
                            base[
                                key
                            ]
                        ):

                            base[
                                key
                            ] = value

                    except Exception:

                        pass

        # Ownership is explicit and authoritative.
        base[
            "Existing Holding"
        ] = True

        base[
            "Owned"
        ] = True

        base[
            "Quantity"
        ] = get_quantity(
            holding
        )

        population[
            ticker
        ] = base

    # ============================================================
    # 2. ADD ONLY NON-OWNED BUY NEW OPPORTUNITIES
    #
    # Capital Allocation determines whether a new candidate is
    # eligible.
    #
    # IMPORTANT:
    #
    # Only the exact action "BUY NEW" qualifies.
    #
    # Do not use startswith("BUY"), because BUY MORE is not a
    # valid non-owned population candidate.
    # ============================================================

    for ticker, allocation_row in capital_lookup.items():

        # Existing holdings were already added above.
        if ticker in holding_lookup:
            continue

        # Absolute CASH protection.
        if ticker == "CASH":
            continue

        action = get_capital_action(
            allocation_row
        )

        # Only genuine BUY NEW candidates enter the population.
        if action != "BUY NEW":
            continue

        base = dict(
            allocation_row
        )

        base[
            "Existing Holding"
        ] = False

        base[
            "Owned"
        ] = False

        base[
            "Quantity"
        ] = 0.0

        population[
            ticker
        ] = base

    # ============================================================
    # FINAL SAFETY FILTER
    #
    # Even though CASH has already been removed at source, apply
    # one final filter immediately before returning.
    #
    # This is deliberate defence-in-depth for FD-02.
    # ============================================================

    population = {
        ticker: record
        for ticker, record in population.items()
        if ticker
        and ticker != "CASH"
        and get_ticker(record) != "CASH"
    }

    # ============================================================
    # DIAGNOSTICS
    # ============================================================

    print(
        "HOLDING LOOKUP TICKERS:",
        sorted(
            holding_lookup.keys()
        )
    )

    print(
        "ELIGIBLE POPULATION TICKERS:",
        sorted(
            population.keys()
        )
    )

    # ============================================================
    # RETURN
    # ============================================================

    return list(
        population.values()
    )

# ============================================================
# CANDIDATE CONTEXT
# ============================================================

def build_chain_candidate(
    base_row: dict,
    portfolio_summary: Any,
) -> dict:
    """
    Build the candidate passed into ai_decision_context.py.

    Portfolio holdings are authoritative for ownership.

    Stock analysis uses:
        Investment Score
        Quality Score
        Growth Score
        Momentum Signal

    ETF analysis uses:
        ETF Score
        ETF Signal

    ETFs are deliberately excluded from stock-specific scoring.
    """

    ticker = get_ticker(
        base_row
    )

    summary = normalise_tickers(
        safe_dataframe(
            portfolio_summary
        )
    )

    holding_row = {}

    if (
        not summary.empty
        and
        "Ticker" in summary.columns
    ):

        matches = summary[
            summary[
                "Ticker"
            ]
            .astype(str)
            .str.strip()
            .str.upper()
            == ticker
        ]

        if not matches.empty:

            holding_row = (
                matches.iloc[0]
                .to_dict()
            )

    # =========================================================
    # OWNERSHIP
    # =========================================================

    owned = (
        get_quantity(
            holding_row
        ) > 0
        if holding_row
        else False
    )

    quantity = (
        get_quantity(
            holding_row
        )
        if holding_row
        else 0.0
    )

    allocation_pct = (
        get_allocation_pct(
            holding_row
        )
        if holding_row
        else get_allocation_pct(
            base_row
        )
    )

    # =========================================================
    # ASSET TYPE
    # =========================================================

    asset_type = get_asset_type(
        base_row
    )

    print(
        "FINAL DECISION INPUT:",
        ticker,
        "| Asset Type =", asset_type,
        "| Action =", base_row.get("Action"),
        "| Capital Allocation Action =",
        base_row.get("Capital Allocation Action"),
        "| Proposed Action =",
        base_row.get("Proposed Action"),
        "| Final Action =",
        base_row.get("Final Action"),
    )

    # =========================================================
    # PROPOSED ACTION
    # =========================================================

    proposed_action = get_capital_action(
        base_row
    )

    # =========================================================
    # ANALYSIS
    #
    # IMPORTANT:
    #
    # STOCK:
    #     Investment Score + Momentum Signal
    #
    # ETF:
    #     ETF Score + ETF Signal
    #
    # An ETF must never inherit a zero Investment Score and
    # then have that zero interpreted as a weak stock signal.
    # =========================================================

    if asset_type == "ETF":

        investment_score = 0.0

        etf_score = safe_float(
            first_value(
                row_value(
                    base_row,
                    "ETF Score",
                    "etf_score",
                    default=None,
                ),
                row_value(
                    holding_row,
                    "ETF Score",
                    "etf_score",
                    default=None,
                ),
                0,
            )
        )

        quality_score = 0.0

        growth_score = 0.0

        # ETFs must never inherit the stock Momentum Signal.
        signal = ""

        etf_signal = upper_text(
            first_value(
                row_value(
                    base_row,
                    "ETF Signal",
                    "etf_signal",
                    default=None,
                ),
                row_value(
                    holding_row,
                    "ETF Signal",
                    "etf_signal",
                    default=None,
                ),
                "HOLD",
            ),
            "HOLD",
        )

        risk_score = 0.0
    else:

        investment_score = safe_float(
            row_value(
                base_row,
                "Investment Score",
                "investment_score",
                "Score",
                default=0,
            )
        )

        etf_score = 0.0

        quality_score = safe_float(
            row_value(
                base_row,
                "Quality Score",
                "quality_score",
                default=0,
            )
        )

        growth_score = safe_float(
            row_value(
                base_row,
                "Growth Score",
                "growth_score",
                default=0,
            )
        )

        signal = upper_text(
            row_value(
                base_row,
                "Signal",
                "signal",
                "Momentum Signal",
                default="",
            )
        )

        etf_signal = ""

        risk_score = safe_float(
            row_value(
                base_row,
                "Risk Score",
                "risk_score",
                default=0,
            )
        )

    # =========================================================
    # RETURN CHAIN CANDIDATE
    # =========================================================

    return {

        "ticker":
            ticker,

        "asset_type":
            asset_type,

        "ownership": {

            "owned":
                owned,

            "quantity":
                quantity,

            "market_value":
                get_market_value(
                    holding_row
                    if holding_row
                    else base_row
                ),

            "allocation_pct":
                allocation_pct,

            "sector":
                safe_text(
                    row_value(
                        base_row,
                        "Sector",
                        "sector",
                        default="Unknown",
                    ),
                    "Unknown",
                ),
        },

        # =====================================================
        # ANALYSIS
        # =====================================================

        "analysis": {

            "investment_score":
                investment_score,

            "etf_score":
                etf_score,

            "quality_score":
                quality_score,

            "growth_score":
                growth_score,

            "signal":
                signal,

            "etf_signal":
                etf_signal,

            "risk_score":
                risk_score,
        },

        # =====================================================
        # RULES-BASED DECISION
        # =====================================================

        "rules_based_decision": {

            "action":
                proposed_action,

            "reason":
                safe_text(
                    row_value(
                        base_row,
                        "Reason",
                        "Original Reason",
                        "Final Reason",
                        default="",
                    )
                ),

            "confidence":
                row_value(
                    base_row,
                    "Confidence",
                    "Deterministic Confidence",
                    default="",
                ),
        },

        # =====================================================
        # RECOMMENDATION INTELLIGENCE
        # =====================================================

        "recommendation_intelligence": {

            "historical_signal_observations":
                safe_float(
                    row_value(
                        base_row,
                        "Historical Signal Observations",
                        default=0,
                    )
                ),

            "historical_signal_win_rate_pct":
                safe_float(
                    row_value(
                        base_row,
                        "Historical Signal Win Rate %",
                        default=0,
                    )
                ),

            "historical_signal_average_return_pct":
                safe_float(
                    row_value(
                        base_row,
                        "Historical Signal Average Return %",
                        default=0,
                    )
                ),

            "historical_signal_reliability":
                safe_text(
                    row_value(
                        base_row,
                        "Historical Signal Reliability",
                        default="",
                    )
                ),

            "learning_adjustment":
                safe_float(
                    row_value(
                        base_row,
                        "Learning Adjustment",
                        default=0,
                    )
                ),

            "learning_adjusted_score":
                safe_float(
                    row_value(
                        base_row,
                        "Learning Adjusted Score",
                        "Investment Score",
                        default=0,
                    )
                ),

            "score_bucket_observations":
                safe_float(
                    row_value(
                        base_row,
                        "Score Bucket Observations",
                        default=0,
                    )
                ),

            "score_bucket_win_rate_pct":
                safe_float(
                    row_value(
                        base_row,
                        "Score Bucket Win Rate %",
                        default=0,
                    )
                ),

            "score_bucket_average_return_pct":
                safe_float(
                    row_value(
                        base_row,
                        "Score Bucket Average Return %",
                        default=0,
                    )
                ),
        },
    }

def build_intelligence_record(
    base_row: dict,
) -> dict:
    """Build Recommendation Intelligence input."""

    return {
        "Ticker":
            get_ticker(
                base_row
            ),

        "Historical Signal Observations":
            row_value(
                base_row,
                "Historical Signal Observations",
                default=0,
            ),

        "Historical Signal Win Rate %":
            row_value(
                base_row,
                "Historical Signal Win Rate %",
                default=0,
            ),

        "Historical Signal Average Return %":
            row_value(
                base_row,
                "Historical Signal Average Return %",
                default=0,
            ),

        "Historical Signal Reliability":
            row_value(
                base_row,
                "Historical Signal Reliability",
                default="",
            ),

        "Learning Adjustment":
            row_value(
                base_row,
                "Learning Adjustment",
                default=0,
            ),

        "Learning Adjusted Score":
            row_value(
                base_row,
                "Learning Adjusted Score",
                "Investment Score",
                default=0,
            ),

        "Score Bucket Observations":
            row_value(
                base_row,
                "Score Bucket Observations",
                default=0,
            ),

        "Score Bucket Win Rate %":
            row_value(
                base_row,
                "Score Bucket Win Rate %",
                default=0,
            ),

        "Score Bucket Average Return %":
            row_value(
                base_row,
                "Score Bucket Average Return %",
                default=0,
            ),
    }


# ============================================================
# AI DECISION CHAIN
# ============================================================

# ============================================================
# AI DECISION CHAIN
# ============================================================

def run_governed_chain(
    portfolio_summary: Any,
    base_row: dict,
    capital_allocation: Any = None,
    recommendation_intelligence: Any = None,
) -> dict:
    """
    Run the complete governed AI decision chain for one candidate.

    FD-02 — Final Portfolio Decision Governance
    --------------------------------------------

    Chain:

        Current Candidate Context
                ↓
        AI Decision Context
                ↓
        Deterministic Decision Layer
                ↓
        Decision Explanation
                ↓
        LLM Review
                ↓
        Reconciliation
                ↓
        Final Governed Decision

    Asset-specific analysis:

        STOCK
            Investment Score
            Quality Score
            Growth Score
            Signal
            Risk Score

        ETF
            ETF Score
            ETF Signal

    ETFs must never inherit stock-specific scoring or signals.

    Historical recommendation intelligence is passed through to
    build_ai_decision_context(), which is responsible for selecting
    the ticker-specific historical intelligence record.

    The immutable recommendation evidence snapshot is also loaded
    by build_ai_decision_context() using Recommendation ID.

    Important:
        candidate["analysis"] returned by the context builder must
        not be overwritten after context construction because the
        context builder may enrich it with immutable recommendation
        evidence.
    """

    ticker = get_ticker(
        base_row
    )

    # ============================================================
    # RECOMMENDATION ID
    # ============================================================

    recommendation_id = get_latest_recommendation_id(
        ticker=ticker,
        recommendation_date=base_row.get(
            "Date",
            base_row.get(
                "date",
                None,
            ),
        ),
    )

    # ============================================================
    # BUILD CURRENT CANDIDATE INPUT
    #
    # build_chain_candidate() establishes:
    #
    #   - authoritative ownership
    #   - asset type
    #   - stock analysis
    #   - ETF analysis
    #   - rules-based proposed action
    #
    # For ETFs:
    #
    #   investment_score = 0
    #   signal = ""
    #   ETF Score = actual ETF score
    #   ETF Signal = actual ETF signal
    # ============================================================

    candidate_input = build_chain_candidate(
        base_row=base_row,
        portfolio_summary=portfolio_summary,
    )

    # ============================================================
    # HISTORICAL RECOMMENDATION INTELLIGENCE
    #
    # Pass the complete existing intelligence object through.
    #
    # build_ai_decision_context() is responsible for converting
    # this into the ticker-specific intelligence record.
    #
    # If none was supplied, retain the backwards-compatible
    # fallback behaviour.
    # ============================================================

    intelligence_input = (
        recommendation_intelligence
        if recommendation_intelligence is not None
        else [
            build_intelligence_record(
                base_row
            )
        ]
    )

    # ============================================================
    # CANDIDATE DECISION INPUT
    #
    # IMPORTANT:
    #
    # ETF Score was previously missing from this boundary.
    #
    # That meant build_chain_candidate() could correctly calculate
    # an ETF Score, but the score could be lost when constructing
    # candidate_decisions for build_ai_decision_context().
    #
    # Explicitly pass both ETF Score and ETF Signal.
    # ============================================================

    candidate_decisions = [
        {
            # ----------------------------------------------------
            # Core identity
            # ----------------------------------------------------

            "Ticker":
                ticker,

            "Recommendation ID":
                recommendation_id,

            "Asset Type":
                candidate_input[
                    "asset_type"
                ],

            # ----------------------------------------------------
            # Rules-based decision
            # ----------------------------------------------------

            "Action":
                candidate_input[
                    "rules_based_decision"
                ][
                    "action"
                ],

            "Reason":
                candidate_input[
                    "rules_based_decision"
                ][
                    "reason"
                ],

            "Confidence":
                candidate_input[
                    "rules_based_decision"
                ][
                    "confidence"
                ],

            # ----------------------------------------------------
            # Portfolio ownership
            # ----------------------------------------------------

            "Existing Holding":
                candidate_input[
                    "ownership"
                ][
                    "owned"
                ],

            "Quantity":
                candidate_input[
                    "ownership"
                ][
                    "quantity"
                ],

            "Allocation %":
                candidate_input[
                    "ownership"
                ][
                    "allocation_pct"
                ],

            "Sector":
                candidate_input[
                    "ownership"
                ][
                    "sector"
                ],

            # ----------------------------------------------------
            # Asset-specific analysis
            #
            # STOCK:
            #   Investment Score
            #   Quality Score
            #   Growth Score
            #   Signal
            #   Risk Score
            #
            # ETF:
            #   ETF Score
            #   ETF Signal
            #
            # ETF fields are explicitly passed so ETF analysis
            # cannot be lost between the candidate builder and
            # AI decision context.
            # ----------------------------------------------------

            "Investment Score":
                candidate_input[
                    "analysis"
                ][
                    "investment_score"
                ],

            "ETF Score":
                candidate_input[
                    "analysis"
                ][
                    "etf_score"
                ],

            "Quality Score":
                candidate_input[
                    "analysis"
                ][
                    "quality_score"
                ],

            "Growth Score":
                candidate_input[
                    "analysis"
                ][
                    "growth_score"
                ],

            "Signal":
                candidate_input[
                    "analysis"
                ][
                    "signal"
                ],

            "ETF Signal":
                candidate_input[
                    "analysis"
                ][
                    "etf_signal"
                ],

            "Risk Score":
                candidate_input[
                    "analysis"
                ][
                    "risk_score"
                ],
        }
    ]

    # ============================================================
    # AI DECISION CONTEXT
    # ============================================================

    context = build_ai_decision_context(
        portfolio=portfolio_summary,
        candidate_decisions=candidate_decisions,
        recommendation_intelligence=
            intelligence_input,
        capital_allocation=
            capital_allocation,
    )

    # ============================================================
    # VALIDATE CONTEXT
    # ============================================================

    candidates = context.get(
        "candidates",
        [],
    )

    if not candidates:
        raise ValueError(
            f"AI Decision Context produced no candidate for {ticker}"
        )

    candidate = candidates[0]

    # ============================================================
    # PRESERVE AUTHORITATIVE CURRENT-STATE FIELDS
    #
    # Do NOT overwrite candidate["analysis"].
    #
    # build_ai_decision_context() may have enriched the analysis
    # using the immutable recommendation evidence snapshot.
    #
    # Do NOT overwrite candidate["recommendation_intelligence"].
    #
    # The context builder has already selected the matching
    # ticker-specific historical intelligence record.
    # ============================================================

    candidate[
        "ownership"
    ] = candidate_input[
        "ownership"
    ]

    candidate[
        "asset_type"
    ] = candidate_input[
        "asset_type"
    ]

    candidate[
        "rules_based_decision"
    ] = candidate_input[
        "rules_based_decision"
    ]

    # ============================================================
    # AI DECISION LAYER
    #
    # This calls ai_decision_scoring.py internally.
    # ============================================================

    print(
        f"CALLING AI DECISION LAYER: {ticker}"
    )

    deterministic = generate_ai_decision(
        portfolio=context,
        candidate=candidate,
    )

    # ============================================================
    # DECISION EXPLANATION
    # ============================================================

    explanation = explain_ai_decision(
        portfolio=context,
        candidate=candidate,
        decision=deterministic,
    )

    # ============================================================
    # LLM REVIEW
    # ============================================================

    
    review = review_ai_decision(
        portfolio=context,
        candidate=candidate,
        decision=deterministic,
    )

  
    # ============================================================
    # RECONCILIATION
    # ============================================================

    reconciliation = reconcile_ai_decision(
        decision=deterministic,
        review=review,
    )

    print(
        f"RECONCILIATION DETAIL: {ticker} | "
        f"Status={reconciliation.get('Reconciliation Status')} | "
        f"Deterministic={reconciliation.get('Deterministic Action')} | "
        f"Proposed={reconciliation.get('Proposed Action')} | "
        f"Reconciled={reconciliation.get('Reconciled Action')} | "
        f"Evidence={reconciliation.get('Evidence Score')} | "
        f"Deterministic Confidence={reconciliation.get('Deterministic Confidence')} | "
        f"LLM Review={reconciliation.get('LLM Review')} | "
        f"LLM Confidence={reconciliation.get('LLM Confidence')} | "
        f"Existing Holding={reconciliation.get('Existing Holding')} | "
        f"Flags={reconciliation.get('Governance Flags')} | "
        f"Reason Code={reconciliation.get('Governance Reason Code')} | "
        f"Reasons={reconciliation.get('Governance Reasons')} | "
        f"Reason={reconciliation.get('Governance Reason')}"
    )

    # ============================================================
    # RETURN COMPLETE GOVERNED CHAIN
    #
    # Keep the individual stages intact so build_final_result()
    # can consume the established result contract.
    # ============================================================

    return {
        "context":
            context,

        "candidate":
            candidate,

        "deterministic":
            deterministic,

        "explanation":
            explanation,

        "review":
            review,

        "reconciliation":
            reconciliation,
    }


# ============================================================
# FINAL RESULT MAPPING
# ============================================================

def get_reconciled_action(
    reconciliation: dict,
) -> str:
    """
    Extract the local reconciler's authoritative action.

    Actual local contract:

        Reconciled Action

    Compatibility fallbacks are retained.
    """

    if not isinstance(
        reconciliation,
        dict,
    ):
        return "HOLD"

    action = first_value(
        reconciliation.get(
            "Reconciled Action"
        ),
        reconciliation.get(
            "reconciled_action"
        ),
        reconciliation.get(
            "Final Decision"
        ),
        default="HOLD",
    )

    action = upper_text(
        action,
        "HOLD",
    )

    if action.startswith(
        "REDUCE"
    ):
        return action

    if action in VALID_ACTIONS:
        return action

    return "HOLD"


def get_reconciliation_status(
    reconciliation: dict,
) -> str:
    """Extract reconciler status."""

    return safe_text(
        first_value(
            reconciliation.get(
                "Status"
            ),
            reconciliation.get(
                "Decision Status"
            ),
            reconciliation.get(
                "Reconciliation Status"
            ),
            default="",
        )
    )


def get_reconciliation_reason(
    reconciliation: dict,
) -> str:
    """Extract reconciler reason."""

    return safe_text(
        first_value(
            reconciliation.get(
                "Reason"
            ),
            reconciliation.get(
                "Reconciliation Reason"
            ),
            default="",
        )
    )


def get_governance_flags(
    reconciliation: dict,
) -> list:
    """Extract governance flags."""

    value = first_value(
        reconciliation.get(
            "Governance Flags"
        ),
        reconciliation.get(
            "Governance Reasons"
        ),
        default=[],
    )

    values = safe_list(
        value
    )

    return [
        safe_text(
            item
        )
        for item in values
        if safe_text(
            item
        )
    ]


def build_final_result(
    base_row: dict,
    chain: dict,
    ticker_horizon_learning=None,
) -> dict:
    """
    Convert the full AI decision chain into the
    Final Portfolio Decisions report contract.

    FD-FINAL-01
    -----------
    Preserve REDUCE percentage variants in the final decision.

    Governance operates on the normalised action:

        REDUCE 25% -> REDUCE
        REDUCE 50% -> REDUCE
        REDUCE 75% -> REDUCE
        REDUCE 100% -> REDUCE

    The reconciler also operates on the normalised action.

    Therefore:

        Proposed Action: REDUCE 25%
        Reconciled Action: REDUCE
        --------------------------
        Final Decision: REDUCE 25%

    Ticker Horizon Learning
    -----------------------
    Ticker / horizon learning is REPORTING ONLY.

    It must NOT modify:

        - Proposed Action
        - Reconciled Decision
        - Final Decision
        - Confidence
        - Evidence Score
        - Investment Score
        - Governance
        - Capital Allocation
        - Audit

    Learning commentary uses the longest mature horizon available:

        60D -> 10D -> 5D

    A horizon is considered mature when it contains at least
    MIN_LEARNING_OBSERVATIONS recommendations.

    When no mature horizon exists, the 5D result is reported as
    "Insufficient data".

    Score relationship
    ------------------
    When available, the commentary also reports the relationship
    between the current Investment Score and the historical
    score-bucket win rate.

    This is informational only.

    Audit
    -----
    This function does NOT create, update or otherwise modify:

        audit_runs
        audit_decisions
        audit_reasons

    Audit remains observational and is handled by the production
    audit layer in generate_final_portfolio_decisions().
    """

    result = dict(
        base_row
    )

    # ========================================================
    # CHAIN STAGES
    # ========================================================

    deterministic = chain.get(
        "deterministic",
        {},
    )

    explanation = chain.get(
        "explanation",
        {},
    )

    review = chain.get(
        "review",
        {},
    )

    reconciliation = chain.get(
        "reconciliation",
        {},
    )

    if not isinstance(
        deterministic,
        dict,
    ):
        deterministic = {}

    if not isinstance(
        explanation,
        dict,
    ):
        explanation = {}

    if not isinstance(
        review,
        dict,
    ):
        review = {}

    if not isinstance(
        reconciliation,
        dict,
    ):
        reconciliation = {}

    evidence = deterministic.get(
        "Evidence Assessment",
        {},
    )

    if not isinstance(
        evidence,
        dict,
    ):
        evidence = {}

    # ========================================================
    # CANDIDATE CONTEXT
    #
    # The production AI chain stores the authoritative candidate
    # under chain["candidate"].
    #
    # Compatibility callers may not provide that nested candidate,
    # so fall back to base_row.
    # ========================================================

    candidate = chain.get(
        "candidate",
        base_row,
    )

    if not isinstance(
        candidate,
        dict,
    ):
        candidate = base_row

    if not isinstance(
        candidate,
        dict,
    ):
        candidate = {}

    ownership = candidate.get(
        "ownership",
        {},
    )

    if not isinstance(
        ownership,
        dict,
    ):
        ownership = {}

    analysis = candidate.get(
        "analysis",
        {},
    )

    if not isinstance(
        analysis,
        dict,
    ):
        analysis = {}

    ticker = get_ticker(
        base_row
    )

    # ========================================================
    # ASSET TYPE
    #
    # ETFs use ETF Score / ETF Signal.
    # Stocks use Investment Score / Signal.
    #
    # Do not allow stock scoring information to leak into ETFs.
    # ========================================================

    asset_type = get_asset_type(
        base_row
    )

    if asset_type == "ETF":

        etf_score = safe_float(
            first_value(
                base_row.get(
                    "ETF Score"
                ),
                base_row.get(
                    "etf_score"
                ),
                0,
            )
        )

        etf_signal = upper_text(
            first_value(
                base_row.get(
                    "ETF Signal"
                ),
                base_row.get(
                    "etf_signal"
                ),
                default="HOLD",
            ),
            "HOLD",
        )

        signal = ""

        investment_score = 0.0

    else:

        etf_score = 0.0

        etf_signal = ""

        investment_score = safe_float(
            first_value(
                base_row.get(
                    "Investment Score"
                ),
                analysis.get(
                    "investment_score"
                ),
                deterministic.get(
                    "Investment Score"
                ),
                0,
            )
        )

        signal = upper_text(
            first_value(
                base_row.get(
                    "Signal"
                ),
                base_row.get(
                    "signal"
                ),
                analysis.get(
                    "signal"
                ),
                default="HOLD",
            ),
            "HOLD",
        )

    # ========================================================
    # ORIGINAL PROPOSED ACTION
    #
    # Preserve REDUCE percentage variants exactly.
    # ========================================================

    proposed_action = upper_text(
        first_value(
            base_row.get(
                "Proposed Action"
            ),
            base_row.get(
                "Final Action"
            ),
            base_row.get(
                "Capital Allocation Action"
            ),
            base_row.get(
                "Action"
            ),
            deterministic.get(
                "Proposed Action"
            ),
            deterministic.get(
                "Action"
            ),
            default="HOLD",
        ),
        "HOLD",
    )

    # ========================================================
    # NORMALISED PROPOSED ACTION
    #
    # Governance compares the action category, not reduction size.
    # ========================================================

    normalised_proposed_action = (
        proposed_action
    )

    if normalised_proposed_action.startswith(
        "REDUCE"
    ):

        normalised_proposed_action = "REDUCE"

    elif normalised_proposed_action not in {
        "BUY NEW",
        "BUY MORE",
        "HOLD",
        "REDUCE",
        "SELL",
    }:

        normalised_proposed_action = "HOLD"

    # ========================================================
    # RECONCILIATION
    # ========================================================

    reconciled_action = get_reconciled_action(
        reconciliation
    )

    reconciliation_status = (
        get_reconciliation_status(
            reconciliation
        )
    )

    reconciliation_reason = (
        get_reconciliation_reason(
            reconciliation
        )
    )

    governance_flags = (
        get_governance_flags(
            reconciliation
        )
    )

    # ========================================================
    # NORMALISED RECONCILED ACTION
    # ========================================================

    normalised_reconciled_action = (
        reconciled_action
    )

    if normalised_reconciled_action.startswith(
        "REDUCE"
    ):

        normalised_reconciled_action = "REDUCE"

    elif normalised_reconciled_action not in {
        "BUY NEW",
        "BUY MORE",
        "HOLD",
        "REDUCE",
        "SELL",
    }:

        normalised_reconciled_action = "HOLD"

    # ========================================================
    # FINAL ACTION
    #
    # Preserve REDUCE percentage whenever governance supports
    # the REDUCE action.
    # ========================================================

    if normalised_proposed_action == "HOLD":

        final_action = "HOLD"

    elif (
        normalised_reconciled_action
        ==
        normalised_proposed_action
    ):

        if normalised_proposed_action == "REDUCE":

            final_action = proposed_action

        else:

            final_action = (
                normalised_proposed_action
            )

    else:

        # Governance did not support the proposal.
        #
        # Conservative portfolio result.
        final_action = "HOLD"

    # ========================================================
    # LLM REVIEW
    # ========================================================

    llm_assessment = upper_text(
        first_value(
            review.get(
                "LLM Assessment"
            ),
            review.get(
                "Review Decision"
            ),
            review.get(
                "LLM Decision"
            ),
            default="CHALLENGE",
        ),
        "CHALLENGE",
    )

    llm_confidence = safe_float(
        first_value(
            review.get(
                "LLM Confidence"
            ),
            review.get(
                "Confidence"
            ),
            default=0,
        )
    )

    llm_reason = safe_text(
        first_value(
            review.get(
                "LLM Reason"
            ),
            review.get(
                "Reason"
            ),
            default="",
        )
    )

    reviewer_status = upper_text(
        review.get(
            "Reviewer Status",
            "",
        )
    )

    # ========================================================
    # DETERMINISTIC EVIDENCE
    # ========================================================

    evidence_score = safe_float(
        first_value(
            deterministic.get(
                "Evidence Score"
            ),
            evidence.get(
                "Evidence Score"
            ),
            default=0,
        )
    )

    evidence_strength = safe_text(
        first_value(
            deterministic.get(
                "Evidence Strength"
            ),
            evidence.get(
                "Evidence Strength"
            ),
            default="UNKNOWN",
        ),
        "UNKNOWN",
    )

    decision_support = upper_text(
        first_value(
            deterministic.get(
                "Decision Support"
            ),
            evidence.get(
                "Decision Support"
            ),
            default="UNKNOWN",
        ),
        "UNKNOWN",
    )

    deterministic_confidence = safe_float(
        first_value(
            deterministic.get(
                "Confidence"
            ),
            deterministic.get(
                "Decision Confidence"
            ),
            evidence.get(
                "Confidence"
            ),
            default=0,
        )
    )

    learning_adjusted_score = safe_float(
        first_value(
            deterministic.get(
                "Learning Adjusted Score"
            ),
            evidence.get(
                "Learning Adjusted Score"
            ),
            base_row.get(
                "Learning Adjusted Score"
            ),
            default=0,
        )
    )

    # ========================================================
    # HISTORICAL SIGNAL EVIDENCE
    #
    # These are the existing historical evidence fields used by
    # the governed decision layer.
    #
    # Do NOT replace these with ticker-horizon commentary.
    # ========================================================

    historical_observations = safe_float(
        first_value(
            deterministic.get(
                "Historical Signal Observations"
            ),
            evidence.get(
                "Historical Signal Observations"
            ),
            base_row.get(
                "Historical Signal Observations"
            ),
            default=0,
        )
    )

    historical_win_rate = safe_float(
        first_value(
            deterministic.get(
                "Historical Signal Win Rate %"
            ),
            evidence.get(
                "Historical Signal Win Rate %"
            ),
            base_row.get(
                "Historical Signal Win Rate %"
            ),
            default=0,
        )
    )

    historical_return = safe_float(
        first_value(
            deterministic.get(
                "Historical Signal Average Return %"
            ),
            evidence.get(
                "Historical Signal Average Return %"
            ),
            base_row.get(
                "Historical Signal Average Return %"
            ),
            default=0,
        )
    )

    historical_reliability = safe_text(
        first_value(
            deterministic.get(
                "Historical Signal Reliability"
            ),
            evidence.get(
                "Historical Signal Reliability"
            ),
            base_row.get(
                "Historical Signal Reliability"
            ),
            default="",
        )
    )

    
    # --------------------------------------------------------
    # Ticker Horizon Learning
    #
    # At this point build_final_result() receives the learning
    # dictionary for THIS ticker only.
    #
    # Expected structure:
    #
    #     {
    #         5:  {...},
    #         10: {...},
    #         60: {...}
    #     }
    #
    # The complete ticker lookup has already been resolved by
    # generate_final_portfolio_decisions().
    #
    # Do NOT attempt to look up the ticker again here.
    # --------------------------------------------------------
    learning_records = (
        ticker_horizon_learning
        if isinstance(
            ticker_horizon_learning,
            dict,
        )
        else {}
    )
    
    # --------------------------------------------------------
    # Learning maturity threshold.
    #
    # Prefer the existing project constant when available.
    # --------------------------------------------------------

    min_learning_observations = safe_float(
        globals().get(
            "MIN_LEARNING_OBSERVATIONS",
            20,
        )
    )

    if min_learning_observations <= 0:

        min_learning_observations = 20.0

    # --------------------------------------------------------
    # Helper to extract numeric learning fields.
    #
    # Supports the established learning schema and common
    # compatibility field names.
    # --------------------------------------------------------

    def learning_numeric(
        record,
        *names,
    ):
        if not isinstance(
            record,
            dict,
        ):
            return None

        for name in names:

            if name not in record:
                continue

            value = record.get(
                name
            )

            if value is None:
                continue

            try:

                numeric = float(
                    value
                )

                if pd.isna(
                    numeric
                ):
                    continue

                return numeric

            except (
                TypeError,
                ValueError,
            ):

                continue

        return None

    # --------------------------------------------------------
    # Locate horizon records.
    #
    # Horizon keys may be integers, strings such as "5D", or
    # strings such as "5".
    # --------------------------------------------------------

    def get_horizon_record(
        horizon,
    ):
        if not learning_records:
            return None

        possible_keys = [
            horizon,
            str(horizon),
            f"{horizon}D",
            f"{horizon}d",
        ]

        for key in possible_keys:

            record = learning_records.get(
                key
            )

            if isinstance(
                record,
                dict,
            ):

                return record

        # Compatibility with records represented as a list.
        if isinstance(
            learning_records,
            list,
        ):

            for record in learning_records:

                if not isinstance(
                    record,
                    dict,
                ):
                    continue

                record_horizon = learning_numeric(
                    record,
                    "Horizon",
                    "horizon",
                )

                if (
                    record_horizon is not None
                    and
                    int(record_horizon) == horizon
                ):

                    return record

        return None

    # --------------------------------------------------------
    # Select longest mature horizon.
    # --------------------------------------------------------

    selected_horizon = None
    selected_record = None

    for horizon_number in (
        60,
        10,
        5,
    ):

        record = get_horizon_record(
            horizon_number
        )

        if not isinstance(
            record,
            dict,
        ):
            continue

        observations = learning_numeric(
            record,
            "Recommendations",
            "Recommendation Count",
            "Observations",
            "Observation Count",
            "Outcome Count",
            "outcome_count",
            "observations",
            "observation_count",
        )

        if (
            observations is not None
            and
            observations >=
            min_learning_observations
        ):

            selected_horizon = (
                horizon_number
            )

            selected_record = record

            break

    # ========================================================
    # Build ticker-horizon commentary.
    # ========================================================

    ticker_horizon_learning_commentary = ""

    if selected_record is None:

        five_day_record = (
            get_horizon_record(
                5
            )
        )

        five_day_observations = (
            learning_numeric(
                five_day_record,
                "Recommendations",
                "Recommendation Count",
                "Observations",
                "Observation Count",
                "Outcome Count",
                "outcome_count",
                "observations",
                "observation_count",
            )
        )

        if five_day_observations is None:

            observation_text = (
                "recommendation count is unknown"
            )

        else:

            if (
                float(
                    five_day_observations
                ).is_integer()
            ):

                observation_text = (
                    f"{int(five_day_observations)} "
                    "recommendations"
                )

            else:

                observation_text = (
                    f"{five_day_observations:g} "
                    "recommendations"
                )

        ticker_horizon_learning_commentary = (
            "5D: Insufficient data "
            f"({observation_text}; "
            f"{int(min_learning_observations)} required)"
        )

        # ----------------------------------------------------
        # Even when horizon learning is immature, expose the
        # current score relationship when score-bucket evidence
        # is available.
        # ----------------------------------------------------

        score_bucket_observations = learning_numeric(
            base_row,
            "Score Bucket Observations",
            "score_bucket_observations",
        )

        score_bucket_win_rate = learning_numeric(
            base_row,
            "Score Bucket Win Rate %",
            "Score Bucket Win Rate",
            "score_bucket_win_rate_pct",
        )

        if (
            score_bucket_observations is not None
            and
            score_bucket_observations > 0
            and
            score_bucket_win_rate is not None
        ):

            ticker_horizon_learning_commentary += (
                f"; current score {investment_score:.1f} "
                f"has {score_bucket_win_rate:.1f}% "
                "historical win rate in its score bucket"
            )

        else:

            ticker_horizon_learning_commentary += (
                f"; current score {investment_score:.1f} "
                "has no mature score-bucket win-rate evidence"
            )

    else:

        recommendations = learning_numeric(
            selected_record,
            "Recommendations",
            "Recommendation Count",
            "Observations",
            "Observation Count",
            "Outcome Count",
            "outcome_count",
            "observations",
            "observation_count",
        )

        average_return = learning_numeric(
            selected_record,
            "Average Return %",
            "Average Return",
            "average_return",
            "average_return_pct",
        )

        median_return = learning_numeric(
            selected_record,
            "Median Return %",
            "Median Return",
            "median_return",
            "median_return_pct",
        )

        win_rate = learning_numeric(
            selected_record,
            "Win Rate %",
            "Win Rate",
            "win_rate",
            "win_rate_pct",
        )

        reliability = safe_text(
            first_value(
                selected_record.get(
                    "Reliability"
                ),
                selected_record.get(
                    "reliability"
                ),
                default="",
            )
        )

        learning_proposed_action = safe_text(
            first_value(
                selected_record.get(
                    "Initial Action"
                ),
                selected_record.get(
                    "Proposed Action"
                ),
                selected_record.get(
                    "Action"
                ),
                proposed_action,
            )
        )

        # ----------------------------------------------------
        # Determine the historical outcome relationship.
        #
        # A positive average return means the recommendation
        # generally preceded an increase in price.
        #
        # A negative average return means it generally preceded
        # a decrease in price.
        # ----------------------------------------------------

        if average_return is not None:

            if average_return > 0:

                relationship = (
                    "historically positive"
                )

            elif average_return < 0:

                relationship = (
                    "historically negative"
                )

            else:

                relationship = (
                    "historically neutral"
                )

        else:

            relationship = (
                "historical outcome unavailable"
            )

        # ----------------------------------------------------
        # Outcome text.
        # ----------------------------------------------------

        if average_return is not None:

            outcome_text = (
                f"average outcome "
                f"{average_return:+.2f}%"
            )

        elif median_return is not None:

            outcome_text = (
                f"median outcome "
                f"{median_return:+.2f}%"
            )

        else:

            outcome_text = (
                "outcome unavailable"
            )

        # ----------------------------------------------------
        # Recommendation count text.
        # ----------------------------------------------------

        if recommendations is None:

            recommendation_text = (
                "recommendation count unknown"
            )

        elif recommendations.is_integer():

            recommendation_text = (
                f"{int(recommendations)} "
                "recommendations"
            )

        else:

            recommendation_text = (
                f"{recommendations:g} "
                "recommendations"
            )

        ticker_horizon_learning_commentary = (
            f"{selected_horizon}D: "
            f"{relationship} "
            f"{learning_proposed_action} — "
            f"{outcome_text} "
            f"({recommendation_text})"
        )

        # ----------------------------------------------------
        # Win-rate metric.
        #
        # Example:
        #
        #     win rate 72.5%
        #
        # This is the percentage of historical recommendations
        # that met the learning system's definition of a win.
        # ----------------------------------------------------

        if win_rate is not None:

            ticker_horizon_learning_commentary += (
                f"; win rate "
                f"{win_rate:.1f}%"
            )

        # ----------------------------------------------------
        # Reliability.
        # ----------------------------------------------------

        if reliability:

            ticker_horizon_learning_commentary += (
                f"; reliability "
                f"{reliability}"
            )

        # ----------------------------------------------------
        # Median outcome.
        # ----------------------------------------------------

        if median_return is not None:

            ticker_horizon_learning_commentary += (
                f"; median outcome "
                f"{median_return:+.2f}%"
            )

        # ----------------------------------------------------
        # Current score relationship.
        #
        # This explicitly connects today's Investment Score
        # with the historical performance of the score bucket.
        #
        # It is INFORMATIONAL ONLY.
        # ----------------------------------------------------

        score_bucket_observations = learning_numeric(
            base_row,
            "Score Bucket Observations",
            "score_bucket_observations",
        )

        score_bucket_win_rate = learning_numeric(
            base_row,
            "Score Bucket Win Rate %",
            "Score Bucket Win Rate",
            "score_bucket_win_rate_pct",
        )

        score_bucket_average_return = learning_numeric(
            base_row,
            "Score Bucket Average Return %",
            "Score Bucket Average Return",
            "score_bucket_average_return_pct",
        )

        if (
            score_bucket_observations is not None
            and
            score_bucket_observations > 0
            and
            score_bucket_win_rate is not None
        ):

            score_relationship = (
                f"; current score "
                f"{investment_score:.1f} "
                f"maps to a "
                f"{score_bucket_win_rate:.1f}% "
                "historical win rate in its score bucket"
            )

            if score_bucket_average_return is not None:

                score_relationship += (
                    f" with average return "
                    f"{score_bucket_average_return:+.2f}%"
                )

            ticker_horizon_learning_commentary += (
                score_relationship
            )

        else:

            ticker_horizon_learning_commentary += (
                f"; current score "
                f"{investment_score:.1f} "
                "has no mature score-bucket evidence"
            )

    # ========================================================
    # DECISION STATUS
    #
    # Compare governed action categories.
    #
    # REDUCE 25%, REDUCE 50%, REDUCE 75%, REDUCE 100%
    # all compare as REDUCE.
    # ========================================================

    final_action_for_governance = (
        "REDUCE"
        if str(
            final_action
        ).upper().startswith(
            "REDUCE"
        )
        else final_action
    )

    decision_changed = (
        final_action_for_governance
        !=
        normalised_proposed_action
    )

    if final_action == "NO ACTION":

        decision_status = (
            "GOVERNANCE OVERRIDE TO NO ACTION"
        )

    elif decision_changed:

        decision_status = (
            "GOVERNANCE OVERRIDE"
        )

    else:

        decision_status = (
            "FINAL DECISION CONFIRMED"
        )

    # ========================================================
    # FINAL REASON
    # ========================================================

    if final_action == "NO ACTION":

        final_reason = (
            f"{ticker} is not currently held and the proposed "
            "BUY NEW action did not pass the governed decision "
            "process. No position should be established."
        )

    elif final_action == "HOLD":

        if reconciliation_reason:

            final_reason = (
                reconciliation_reason
            )

        elif (
            normalised_proposed_action
            !=
            "HOLD"
        ):

            final_reason = (
                f"{ticker} remains HOLD because the proposed "
                f"{proposed_action} action did not survive the "
                "complete governed AI decision chain."
            )

        else:

            final_reason = (
                f"{ticker} remains HOLD because there is no "
                "sufficiently strong reason to change the portfolio."
            )

    elif final_action_for_governance == "REDUCE":

        final_reason = (
            f"{ticker} is approved for {final_action} after "
            "passing the governed AI decision chain."
        )

    elif final_action == "SELL":

        final_reason = (
            f"{ticker} is approved for SELL after passing "
            "the governed AI decision chain."
        )

    elif final_action == "BUY MORE":

        final_reason = (
            f"{ticker} is approved for BUY MORE after passing "
            "the governed AI decision chain."
        )

    elif final_action == "BUY NEW":

        final_reason = (
            f"{ticker} is approved for BUY NEW after passing "
            "the governed AI decision chain."
        )

    else:

        final_reason = (
            f"{ticker} remains HOLD because the proposed action "
            "did not pass the governed decision process."
        )

    # ========================================================
    # OPTIONAL EXPLANATION
    # ========================================================

    explanation_text = safe_text(
        first_value(
            explanation.get(
                "Summary"
            ),
            explanation.get(
                "Decision Explanation"
            ),
            explanation.get(
                "Explanation"
            ),
            default="",
        )
    )

    if explanation_text:

        if final_action in {
            "HOLD",
            "NO ACTION",
        }:

            if final_action == "HOLD":

                final_reason = (
                    explanation_text
                )

    # ========================================================
    # FINAL RESULT CONTRACT
    #
    # IMPORTANT:
    #
    # Learning commentary is inserted here only as a reporting
    # field.
    #
    # Nothing from ticker_horizon_learning is used to determine
    # final_action.
    #
    # Nothing here writes to the audit database.
    # ========================================================

    result.update({

        # ----------------------------------------------------
        # Core identity
        # ----------------------------------------------------

        "Ticker":
            ticker,

        "Asset Type":
            asset_type,

        "Investment Score":
            round(
                investment_score,
                2,
            ),

        "ETF Score":
            round(
                etf_score,
                2,
            ),

        "Signal":
            signal,

        "ETF Signal":
            etf_signal,

        # ----------------------------------------------------
        # Governance action fields
        # ----------------------------------------------------

        "Original Action":
            proposed_action,

        "Proposed Action":
            proposed_action,

        "Original Decision":
            proposed_action,

        "Reconciled Decision":
            reconciled_action,

        "Final Decision":
            final_action,

        "Final Action":
            final_action,

        "Action":
            final_action,

        # ----------------------------------------------------
        # State / governance
        # ----------------------------------------------------

        "Decision Changed":
            decision_changed,

        "Decision Status":
            decision_status,

        "Reconciliation Status":
            reconciliation_status,

        "Reconciliation Reason":
            reconciliation_reason,

        "Governance Reasons":
            governance_flags,

        # ----------------------------------------------------
        # Deterministic evidence
        # ----------------------------------------------------

        "Evidence Score":
            round(
                evidence_score,
                2,
            ),

        "Evidence Strength":
            evidence_strength,

        "Decision Support":
            decision_support,

        "Deterministic Confidence":
            round(
                deterministic_confidence,
                2,
            ),

        "Confidence":
            round(
                deterministic_confidence,
                2,
            ),

        # ----------------------------------------------------
        # Historical evidence
        # ----------------------------------------------------

        "Historical Signal Observations":
            int(
                historical_observations
            ),

        "Historical Signal Win Rate %":
            round(
                historical_win_rate,
                2,
            ),

        "Historical Signal Average Return %":
            round(
                historical_return,
                2,
            ),

        "Historical Signal Reliability":
            historical_reliability,

        "Learning Adjusted Score":
            round(
                learning_adjusted_score,
                2,
            ),

        # ----------------------------------------------------
        # Ticker / horizon learning
        #
        # REPORTING ONLY.
        # ----------------------------------------------------

        "Ticker Horizon Learning Commentary":
            ticker_horizon_learning_commentary,

        # ----------------------------------------------------
        # LLM review
        # ----------------------------------------------------

        "LLM Assessment":
            llm_assessment,

        "LLM Review Decision":
            llm_assessment,

        "LLM Review Valid":
            (
                reviewer_status
                ==
                "LLM REVIEW COMPLETE"
            ),

        "LLM Confidence":
            round(
                llm_confidence,
                2,
            ),

        "LLM Review Confidence":
            round(
                llm_confidence,
                2,
            ),

        "LLM Reason":
            llm_reason,

        "LLM Review Reason":
            llm_reason,

        "LLM Key Points":
            review.get(
                "LLM Key Points",
                review.get(
                    "Key Points",
                    [],
                ),
            ),

        "LLM Evidence Gaps":
            review.get(
                "LLM Evidence Gaps",
                review.get(
                    "Evidence Gaps",
                    [],
                ),
            ),

        # ----------------------------------------------------
        # Final result
        # ----------------------------------------------------

        "Final Reason":
            final_reason,

        "Explanation":
            final_reason,

        # ----------------------------------------------------
        # Authority / execution
        #
        # This function does not execute trades or allocate
        # capital. Those remain downstream responsibilities.
        # ----------------------------------------------------

        "Decision Authority":
            "GOVERNED AI DECISION LAYER",

        "Capital Allocation":
            "NOT PERFORMED",

        "Trade Execution":
            "NOT PERFORMED",
    })

    return result


    def _learning_value(
        record: dict,
        *names,
    ):
        if not isinstance(
            record,
            dict,
        ):
            return None

        for name in names:

            if name not in record:
                continue

            value = record.get(
                name
            )

            if value is None:
                continue

            try:
                if pd.isna(
                    value
                ):
                    continue
            except Exception:
                pass

            return value

        return None

    def _learning_numeric(
        record: dict,
        *names,
    ):
        value = _learning_value(
            record,
            *names,
        )

        if value is None:
            return None

        try:

            if isinstance(
                value,
                bool,
            ):
                return float(
                    int(value)
                )

            return float(
                value
            )

        except (
            TypeError,
            ValueError,
        ):

            return None

    # --------------------------------------------------------
    # Build a clean horizon lookup.
    #
    # Defensive support for:
    #
    #     {5: {...}, 10: {...}, 60: {...}}
    #
    # and:
    #
    #     {"5": {...}, "10": {...}, "60": {...}}
    #
    # and:
    #
    #     {"5D": {...}, "10D": {...}, "60D": {...}}
    # --------------------------------------------------------

    horizon_records = {}

    for raw_horizon, record in (
        ticker_horizon_learning.items()
    ):

        if not isinstance(
            record,
            dict,
        ):
            continue

        try:

            horizon_number = int(
                float(
                    raw_horizon
                )
            )

        except (
            TypeError,
            ValueError,
        ):

            horizon_text = (
                safe_text(
                    raw_horizon
                ).upper()
            )

            if horizon_text.startswith(
                "5D"
            ):
                horizon_number = 5

            elif horizon_text.startswith(
                "10D"
            ):
                horizon_number = 10

            elif horizon_text.startswith(
                "60D"
            ):
                horizon_number = 60

            else:
                horizon_number = None

        if horizon_number not in {
            5,
            10,
            60,
        }:
            continue

        horizon_records[
            horizon_number
        ] = record

    # --------------------------------------------------------
    # Select longest mature horizon.
    #
    # The agreed reporting hierarchy is:
    #
    #     60D -> 10D -> 5D
    #
    # A horizon is mature with >= 20 recommendations.
    # --------------------------------------------------------

    MIN_LEARNING_OBSERVATIONS = 20

    selected_horizon = None
    selected_record = None

    for horizon_number in (
        60,
        10,
        5,
    ):

        record = horizon_records.get(
            horizon_number
        )

        if not isinstance(
            record,
            dict,
        ):
            continue

        recommendations = _learning_numeric(
            record,
            "Recommendations",
            "Recommendation Count",
            "Observations",
            "Observation Count",
            "Outcome Count",
            "outcome_count",
            "observations",
            "observation_count",
        )

        if (
            recommendations is not None
            and
            recommendations
            >=
            MIN_LEARNING_OBSERVATIONS
        ):

            selected_horizon = (
                horizon_number
            )

            selected_record = record

            break

    # --------------------------------------------------------
    # If no horizon is mature, the terminal reporting state is
    # the 5D horizon.
    #
    # This is intentionally conservative and transparent.
    # --------------------------------------------------------

    ticker_horizon_learning_commentary = ""

    # --------------------------------------------------------
    # Current recommendation context.
    #
    # Reporting only. These values do NOT influence the
    # portfolio decision or governance.
    # --------------------------------------------------------

    current_investment_score = _learning_numeric(
        base_row,
        "Investment Score",
        "investment_score",
        "Score",
    )

    current_signal = upper_text(
        first_value(
            base_row.get("Signal"),
            base_row.get("signal"),
            default="",
        ),
        "",
    )

    if selected_record is None:

        five_day_record = (
            horizon_records.get(
                5
            )
        )

        five_day_observations = None

        if isinstance(
            five_day_record,
            dict,
        ):

            five_day_observations = (
                _learning_numeric(
                    five_day_record,
                    "Recommendations",
                    "Recommendation Count",
                    "Observations",
                    "Observation Count",
                    "Outcome Count",
                    "outcome_count",
                    "observations",
                    "observation_count",
                )
            )

            if five_day_observations is None:

                ticker_horizon_learning_commentary = (
                    "5D: Insufficient data "
                    "(recommendation count is unknown; "
                    "20 required)"
                )

            else:

                ticker_horizon_learning_commentary = (
                    "5D: Insufficient data "
                    f"({int(five_day_observations)} "
                    "recommendations; 20 required)"
                )

        # ----------------------------------------------------
        # Even when the historical sample is immature, show
        # the current score and signal so the user can see
        # the relationship between today's recommendation
        # and the available historical learning.
        #
        # Reporting only.
        # ----------------------------------------------------

        if current_investment_score is not None:

            ticker_horizon_learning_commentary += (
                f"; current Investment Score "
                f"{current_investment_score:.0f}"
            )

        if current_signal:

            ticker_horizon_learning_commentary += (
                f"; current Signal "
                f"{current_signal}"
            )
    else:

        recommendations = _learning_numeric(
            selected_record,
            "Recommendations",
            "Recommendation Count",
            "Observations",
            "Observation Count",
            "Outcome Count",
            "outcome_count",
            "observations",
            "observation_count",
        )

        average_return = _learning_numeric(
            selected_record,
            "Average Return %",
            "Average Return",
            "average_return",
            "Mean Return",
        )

        median_return = _learning_numeric(
            selected_record,
            "Median Return %",
            "Median Return",
            "median_return",
        )

        win_rate = _learning_numeric(
            selected_record,
            "Win Rate %",
            "Win Rate",
            "win_rate",
        )

        reliability = safe_text(
            _learning_value(
                selected_record,
                "Reliability",
                "Learning Reliability",
                "learning_reliability",
                "Signal Reliability",
            ),
            "",
        ).upper()

        # ----------------------------------------------------
        # Determine relationship between historical outcomes
        # and the original recommendation.
        #
        # The learning record itself does not contain a
        # separate "Learning Direction" field.
        #
        # Therefore:
        #
        #   positive average return -> supports
        #   negative average return -> contradicts
        #   zero / unavailable       -> historical result
        #
        # This is reporting language only.
        # ----------------------------------------------------

        if average_return is not None:

            if average_return > 0:

                relationship = "Supports"

            elif average_return < 0:

                relationship = "Contradicts"

            else:

                relationship = "Neutral"

        else:

            relationship = "Historical"

        # ----------------------------------------------------
        # Use the original proposal as the recommendation
        # being evaluated.
        #
        # This is deliberately NOT the final governed action.
        # ----------------------------------------------------

        learning_proposed_action = (
            proposed_action
        )

        if learning_proposed_action == "HOLD":

            learning_proposed_action = "HOLD"

        # ----------------------------------------------------
        # Average outcome text.
        # ----------------------------------------------------

        if average_return is None:

            outcome_text = (
                "average outcome unavailable"
            )

        else:

            outcome_text = (
                f"average outcome "
                f"{average_return:+.2f}%"
            )

        # ----------------------------------------------------
        # Observation text.
        # ----------------------------------------------------

        if recommendations is None:

            recommendation_text = (
                "recommendations unknown"
            )

        elif recommendations.is_integer():

            recommendation_text = (
                f"{int(recommendations)} "
                "recommendations"
            )

        else:

            recommendation_text = (
                f"{recommendations:g} "
                "recommendations"
            )

        # ----------------------------------------------------
        # Primary commentary.
        # ----------------------------------------------------

        ticker_horizon_learning_commentary = (
            f"{selected_horizon}D: "
            f"{relationship} initial "
            f"{learning_proposed_action} — "
            f"{outcome_text} "
            f"({recommendation_text})"
        )

        # ----------------------------------------------------
        # Optional win-rate information.
        # ----------------------------------------------------

        if win_rate is not None:

            ticker_horizon_learning_commentary += (
                f"; win rate "
                f"{win_rate:.1f}%"
            )

        # ----------------------------------------------------
        # Current score relationship.
        #
        # The current score is displayed alongside historical
        # ticker/horizon learning but does not modify it.
        # ----------------------------------------------------

        if current_investment_score is not None:

            ticker_horizon_learning_commentary += (
                f"; current Investment Score "
                f"{current_investment_score:.0f}"
            )

        if current_signal:

            ticker_horizon_learning_commentary += (
                f"; current Signal "
                f"{current_signal}"
            )

        # ----------------------------------------------------
        # Optional reliability information.
        # ----------------------------------------------------

        if reliability:

            ticker_horizon_learning_commentary += (
                f"; reliability "
                f"{reliability}"
            )

        # ----------------------------------------------------
        # Optional median return information.
        # ----------------------------------------------------

        if median_return is not None:

            ticker_horizon_learning_commentary += (
                f"; median outcome "
                f"{median_return:+.2f}%"
            )

        # ----------------------------------------------------
        # Show the next immature horizon's observation count.
        #
        # This gives useful visibility without making the
        # commentary excessively verbose.
        # ----------------------------------------------------

        next_horizon = None

        if selected_horizon == 60:

            next_horizon = None

        elif selected_horizon == 10:

            next_horizon = 60

        elif selected_horizon == 5:

            next_horizon = 10

        if next_horizon is not None:

            next_record = horizon_records.get(
                next_horizon
            )

            if isinstance(
                next_record,
                dict,
            ):

                next_observations = (
                    _learning_numeric(
                        next_record,
                        "Recommendations",
                        "Recommendation Count",
                        "Observations",
                        "Observation Count",
                        "Outcome Count",
                        "outcome_count",
                        "observations",
                        "observation_count",
                    )
                )

                if next_observations is not None:

                    if next_observations.is_integer():

                        next_count_text = (
                            str(
                                int(
                                    next_observations
                                )
                            )
                        )

                    else:

                        next_count_text = (
                            f"{next_observations:g}"
                        )

                    ticker_horizon_learning_commentary += (
                        f"; {next_horizon}D: "
                        f"{next_count_text} observations"
                    )

    # ========================================================
    # DECISION STATUS
    #
    # Compare governed actions, not sizing variants.
    #
    # REDUCE 25%, REDUCE 50%, etc. are all the same governance
    # action: REDUCE.
    # ========================================================

    final_action_for_governance = (
        "REDUCE"
        if str(
            final_action
        ).upper().startswith(
            "REDUCE"
        )
        else final_action
    )

    decision_changed = (
        final_action_for_governance
        !=
        normalised_proposed_action
    )

    if decision_changed:

        decision_status = (
            "GOVERNANCE OVERRIDE"
        )

    else:

        decision_status = (
            "FINAL AI DECISION"
        )

    # ========================================================
    # FINAL REASON
    # ========================================================

    if final_action == "HOLD":

        if reconciliation_reason:

            final_reason = (
                reconciliation_reason
            )

        elif (
            normalised_proposed_action
            !=
            "HOLD"
        ):

            final_reason = (
                f"{ticker} remains HOLD because the proposed "
                f"{proposed_action} action did not survive the "
                "complete governed AI decision chain."
            )

        else:

            final_reason = (
                f"{ticker} remains HOLD because there is no "
                "sufficiently strong reason to change the portfolio."
            )

    elif final_action_for_governance == "REDUCE":

        final_reason = (
            f"{ticker} is approved for {final_action} after "
            "passing the governed AI decision chain."
        )

    elif final_action == "SELL":

        final_reason = (
            f"{ticker} is approved for SELL after passing "
            "the governed AI decision chain."
        )

    elif final_action == "BUY MORE":

        final_reason = (
            f"{ticker} is approved for BUY MORE after passing "
            "the governed AI decision chain."
        )

    elif final_action == "BUY NEW":

        final_reason = (
            f"{ticker} is approved for BUY NEW after passing "
            "the governed AI decision chain."
        )

    else:

        final_reason = (
            f"{ticker} remains HOLD because the proposed action "
            "did not pass the governed decision process."
        )

    # ========================================================
    # OPTIONAL EXPLANATION
    # ========================================================

    explanation_text = safe_text(
        first_value(
            explanation.get(
                "Summary"
            ),
            explanation.get(
                "Decision Explanation"
            ),
            explanation.get(
                "Explanation"
            ),
            default="",
        )
    )

    if explanation_text:

        if final_action == "HOLD":

            final_reason = (
                explanation_text
            )

    # ========================================================
    # BUILD FINAL RESULT
    #
    # The existing report contract is retained.
    #
    # The ticker horizon learning commentary is added as a
    # reporting field only.
    # ========================================================

    result.update({

        # ----------------------------------------------------
        # Core identity
        # ----------------------------------------------------

        "Ticker":
            ticker,

        "Asset Type":
            asset_type,

        "Investment Score":
            0.0
            if asset_type == "ETF"
            else safe_float(
                base_row.get(
                    "Investment Score",
                    0,
                )
            ),

        "ETF Score":
            round(
                etf_score,
                2,
            ),

        "Signal":
            signal,

        "ETF Signal":
            etf_signal,

        # ----------------------------------------------------
        # Governance action fields
        # ----------------------------------------------------

        "Original Action":
            proposed_action,

        "Proposed Action":
            proposed_action,

        "Original Decision":
            proposed_action,

        "Reconciled Decision":
            reconciled_action,

        "Final Decision":
            final_action,

        "Final Action":
            final_action,

        "Action":
            final_action,

        # ----------------------------------------------------
        # State / governance
        # ----------------------------------------------------

        "Decision Changed":
            decision_changed,

        "Decision Status":
            decision_status,

        "Reconciliation Status":
            reconciliation_status,

        "Reconciliation Reason":
            reconciliation_reason,

        "Governance Reasons":
            governance_flags,

        # ----------------------------------------------------
        # Deterministic evidence
        # ----------------------------------------------------

        "Evidence Score":
            round(
                evidence_score,
                2,
            ),

        "Evidence Strength":
            evidence_strength,

        "Decision Support":
            decision_support,

        "Deterministic Confidence":
            round(
                deterministic_confidence,
                2,
            ),

        "Confidence":
            round(
                deterministic_confidence,
                2,
            ),

        # ----------------------------------------------------
        # Historical evidence
        # ----------------------------------------------------

        "Historical Signal Observations":
            int(
                historical_observations
            ),

        "Historical Signal Win Rate %":
            round(
                historical_win_rate,
                2,
            ),

        "Historical Signal Average Return %":
            round(
                historical_return,
                2,
            ),

        "Historical Signal Reliability":
            historical_reliability,

        "Learning Adjusted Score":
            round(
                learning_adjusted_score,
                2,
            ),

        # ----------------------------------------------------
        # Ticker / horizon learning
        #
        # REPORTING ONLY.
        #
        # This field has no connection to final_action.
        # ----------------------------------------------------

        "Ticker Horizon Learning Commentary":
            ticker_horizon_learning_commentary,

        # ----------------------------------------------------
        # LLM review
        # ----------------------------------------------------

        "LLM Assessment":
            llm_assessment,

        "LLM Review Decision":
            llm_assessment,

        "LLM Review Valid":
            (
                reviewer_status
                ==
                "LLM REVIEW COMPLETE"
            ),

        "LLM Confidence":
            round(
                llm_confidence,
                2,
            ),

        "LLM Review Confidence":
            round(
                llm_confidence,
                2,
            ),

        "LLM Reason":
            llm_reason,

        "LLM Review Reason":
            llm_reason,

        "LLM Key Points":
            review.get(
                "LLM Key Points",
                review.get(
                    "Key Points",
                    [],
                ),
            ),

        "LLM Evidence Gaps":
            review.get(
                "LLM Evidence Gaps",
                review.get(
                    "Evidence Gaps",
                    [],
                ),
            ),

        # ----------------------------------------------------
        # Final result
        # ----------------------------------------------------

        "Final Reason":
            final_reason,

        "Explanation":
            final_reason,

        # ----------------------------------------------------
        # Authority / execution
        # ----------------------------------------------------

        "Decision Authority":
            "GOVERNED AI DECISION LAYER",

        "Capital Allocation":
            "NOT PERFORMED",

        "Trade Execution":
            "NOT PERFORMED",
    })

    return result


    # --------------------------------------------------------
    # Support both common naming conventions used by the
    # learning layer.
    # --------------------------------------------------------

    def _learning_value(*names):
        for name in names:
            if name in ticker_horizon_learning:
                return ticker_horizon_learning.get(
                    name
                )
        return None

    def _learning_numeric(*names):
        raw_value = _learning_value(
            *names
        )

        if raw_value is None:
            return None

        try:
            if isinstance(
                raw_value,
                bool,
            ):
                return float(
                    int(raw_value)
                )

            return float(
                raw_value
            )

        except (
            TypeError,
            ValueError,
        ):
            return None

    # --------------------------------------------------------
    # Resolve observations.
    # --------------------------------------------------------

    learning_observations = _learning_numeric(
        "Observations",
        "Observation Count",
        "Outcome Count",
        "outcome_count",
        "observations",
        "observation_count",
    )

    # --------------------------------------------------------
    # Resolve horizon.
    #
    # This function is specifically concerned with the 5d
    # recommendation horizon. If the supplied learning record
    # explicitly identifies another horizon, it is not used.
    # --------------------------------------------------------

    learning_horizon = _learning_value(
        "Horizon",
        "horizon",
        "Days",
        "days_after",
    )

    try:

        learning_horizon = int(
            float(
                learning_horizon
            )
        )

    except (
        TypeError,
        ValueError,
    ):

        learning_horizon = 5

    # --------------------------------------------------------
    # Resolve the learning recommendation / direction.
    # --------------------------------------------------------

    learning_recommendation = safe_text(
        _learning_value(
            "Recommendation",
            "Learning Recommendation",
            "Recommended Action",
            "Learning Direction",
            "Outcome",
            "outcome",
        ),
        "",
    )

    learning_recommendation_upper = (
        learning_recommendation.upper()
    )

    # --------------------------------------------------------
    # Resolve whether the 5d learning explicitly supports
    # BUY MORE.
    #
    # Prefer explicit boolean fields when supplied.
    # Otherwise interpret the learning recommendation text.
    # --------------------------------------------------------

    supports_buy_more = _learning_value(
        "Supports BUY MORE",
        "Supports Buy More",
        "supports_buy_more",
        "buy_more_supported",
        "Buy More Supported",
    )

    if isinstance(
        supports_buy_more,
        str,
    ):

        supports_buy_more_normalised = (
            supports_buy_more.strip().upper()
        )

        if supports_buy_more_normalised in {
            "TRUE",
            "YES",
            "Y",
            "1",
            "SUPPORTED",
        }:

            supports_buy_more = True

        elif supports_buy_more_normalised in {
            "FALSE",
            "NO",
            "N",
            "0",
            "NOT SUPPORTED",
            "UNSUPPORTED",
        }:

            supports_buy_more = False

        else:

            supports_buy_more = None

    elif isinstance(
        supports_buy_more,
        (int, float),
    ):

        supports_buy_more = bool(
            supports_buy_more
        )

    elif not isinstance(
        supports_buy_more,
        bool,
    ):

        supports_buy_more = None

    # --------------------------------------------------------
    # If there is no explicit boolean, infer only from the
    # learning recommendation itself.
    #
    # This remains informational and never changes the action.
    # --------------------------------------------------------

    if supports_buy_more is None:

        if learning_recommendation_upper in {
            "BUY MORE",
            "BUY_MORE",
            "SUPPORTS BUY MORE",
            "BUY MORE SUPPORTED",
            "POSITIVE",
            "POSITIVE BUY MORE",
        }:

            supports_buy_more = True

        elif (
            "BUY MORE"
            in learning_recommendation_upper
            and
            any(
                phrase in learning_recommendation_upper
                for phrase in {
                    "SUPPORT",
                    "FAVOUR",
                    "FAVOR",
                    "POSITIVE",
                    "YES",
                }
            )
        ):

            supports_buy_more = True

        elif learning_recommendation_upper:

            supports_buy_more = False

    # --------------------------------------------------------
    # Minimum mature observation threshold.
    #
    # We require 20 observations before describing the 5d
    # learning as sufficient information.
    # --------------------------------------------------------

    MIN_5D_OBSERVATIONS = 20

    if (
        learning_horizon != 5
        or
        learning_observations is None
        or
        learning_observations
        <
        MIN_5D_OBSERVATIONS
    ):

        five_day_recommendation_horizon = (
            "Not enough information to produce "
            "5d recommendation"
        )

    elif supports_buy_more is True:

        five_day_recommendation_horizon = (
            "5d recommendation horizon "
            "supports BUY MORE"
        )

    else:

        five_day_recommendation_horizon = (
            "5d recommendation horizon "
            "does not support BUY MORE"
        )

    # ========================================================
    # LLM review fields
    # ========================================================

    llm_assessment = upper_text(
        first_value(
            review.get(
                "LLM Assessment"
            ),
            review.get(
                "Review Decision"
            ),
            review.get(
                "LLM Decision"
            ),
            default="CHALLENGE",
        ),
        "CHALLENGE",
    )

    llm_confidence = safe_float(
        first_value(
            review.get(
                "LLM Confidence"
            ),
            review.get(
                "Confidence"
            ),
            default=0,
        )
    )

    llm_reason = safe_text(
        first_value(
            review.get(
                "LLM Reason"
            ),
            review.get(
                "Reason"
            ),
            default="",
        )
    )

    reviewer_status = upper_text(
        review.get(
            "Reviewer Status",
            "",
        )
    )

    # ========================================================
    # Deterministic evidence
    # ========================================================

    evidence_score = safe_float(
        first_value(
            deterministic.get(
                "Evidence Score"
            ),
            evidence.get(
                "Evidence Score"
            ),
            default=0,
        )
    )

    evidence_strength = safe_text(
        first_value(
            deterministic.get(
                "Evidence Strength"
            ),
            evidence.get(
                "Evidence Strength"
            ),
            default="UNKNOWN",
        ),
        "UNKNOWN",
    )

    decision_support = upper_text(
        first_value(
            deterministic.get(
                "Decision Support"
            ),
            evidence.get(
                "Decision Support"
            ),
            default="UNKNOWN",
        ),
        "UNKNOWN",
    )

    deterministic_confidence = safe_float(
        first_value(
            deterministic.get(
                "Confidence"
            ),
            deterministic.get(
                "Decision Confidence"
            ),
            evidence.get(
                "Confidence"
            ),
            default=0,
        )
    )

    learning_adjusted_score = safe_float(
        first_value(
            deterministic.get(
                "Learning Adjusted Score"
            ),
            evidence.get(
                "Learning Adjusted Score"
            ),
            base_row.get(
                "Learning Adjusted Score"
            ),
            default=0,
        )
    )

    # ========================================================
    # Historical evidence
    # ========================================================

    historical_observations = safe_float(
        first_value(
            deterministic.get(
                "Historical Signal Observations"
            ),
            evidence.get(
                "Historical Signal Observations"
            ),
            base_row.get(
                "Historical Signal Observations"
            ),
            default=0,
        )
    )

    historical_win_rate = safe_float(
        first_value(
            deterministic.get(
                "Historical Signal Win Rate %"
            ),
            evidence.get(
                "Historical Signal Win Rate %"
            ),
            base_row.get(
                "Historical Signal Win Rate %"
            ),
            default=0,
        )
    )

    historical_return = safe_float(
        first_value(
            deterministic.get(
                "Historical Signal Average Return %"
            ),
            evidence.get(
                "Historical Signal Average Return %"
            ),
            base_row.get(
                "Historical Signal Average Return %"
            ),
            default=0,
        )
    )

    historical_reliability = safe_text(
        first_value(
            deterministic.get(
                "Historical Signal Reliability"
            ),
            evidence.get(
                "Historical Signal Reliability"
            ),
            base_row.get(
                "Historical Signal Reliability"
            ),
            default="",
        )
    )

    # ========================================================
    # Decision status
    #
    # Compare governed actions, not sizing variants.
    #
    # REDUCE 25%, REDUCE 50%, etc. are all the same governance
    # action: REDUCE.
    # ========================================================

    final_action_for_governance = (
        "REDUCE"
        if str(
            final_action
        ).upper().startswith(
            "REDUCE"
        )
        else final_action
    )

    decision_changed = (
        final_action_for_governance
        !=
        normalised_proposed_action
    )

    if final_action == "NO ACTION":

        decision_status = (
            "GOVERNANCE OVERRIDE TO NO ACTION"
        )

    elif decision_changed:

        decision_status = (
            "GOVERNANCE OVERRIDE"
        )

    else:

        decision_status = (
            "FINAL DECISION CONFIRMED"
        )

    # ========================================================
    # Final reason
    # ========================================================

    if final_action == "NO ACTION":

        final_reason = (
            f"{ticker} is not currently held and the proposed "
            "BUY NEW action did not pass the governed decision "
            "process. No position should be established."
        )

    elif final_action == "HOLD":

        if reconciliation_reason:

            final_reason = (
                reconciliation_reason
            )

        elif (
            normalised_proposed_action
            !=
            "HOLD"
        ):

            final_reason = (
                f"{ticker} remains HOLD because the proposed "
                f"{proposed_action} action did not survive the "
                "complete governed AI decision chain."
            )

        else:

            final_reason = (
                f"{ticker} remains HOLD because there is no "
                "sufficiently strong reason to change the portfolio."
            )

    elif final_action_for_governance == "REDUCE":

        final_reason = (
            f"{ticker} is approved for {final_action} after "
            "passing the governed AI decision chain."
        )

    elif final_action == "SELL":

        final_reason = (
            f"{ticker} is approved for SELL after passing "
            "the governed AI decision chain."
        )

    elif final_action == "BUY MORE":

        final_reason = (
            f"{ticker} is approved for BUY MORE after passing "
            "the governed AI decision chain."
        )

    elif final_action == "BUY NEW":

        final_reason = (
            f"{ticker} is approved for BUY NEW after passing "
            "the governed AI decision chain."
        )

    else:

        final_reason = (
            f"{ticker} remains HOLD because the proposed action "
            "did not pass the governed decision process."
        )

    # ========================================================
    # Optional explanation
    # ========================================================

    explanation_text = safe_text(
        first_value(
            explanation.get(
                "Summary"
            ),
            explanation.get(
                "Decision Explanation"
            ),
            explanation.get(
                "Explanation"
            ),
            default="",
        )
    )

    # Use the generated explanation only when it is appropriate.
    if explanation_text:

        if final_action in {
            "HOLD",
            "NO ACTION",
        }:

            final_reason = (
                explanation_text
                if final_action == "HOLD"
                else final_reason
            )

    # ========================================================
    # Build final result
    #
    # IMPORTANT:
    # Existing report fields are preserved.
    #
    # The only new reporting field is:
    #
    #     "5d Recommendation Horizon"
    #
    # It is informational only.
    #
    # Audit fields and audit behaviour are not modified here.
    # ========================================================

    result.update({

        # ----------------------------------------------------
        # Core identity
        # ----------------------------------------------------

        "Ticker":
            ticker,

        "Asset Type":
            asset_type,

        "Investment Score":
            0.0
            if asset_type == "ETF"
            else safe_float(
                base_row.get(
                    "Investment Score",
                    0,
                )
            ),

        "ETF Score":
            round(
                etf_score,
                2,
            ),

        "Signal":
            signal,

        "ETF Signal":
            etf_signal,

        # ----------------------------------------------------
        # Governance action fields
        # ----------------------------------------------------

        "Proposed Action":
            proposed_action,

        "Original Decision":
            proposed_action,

        "Reconciled Decision":
            reconciled_action,

        "Final Decision":
            final_action,

        "Final Action":
            final_action,

        "Action":
            final_action,

        # ----------------------------------------------------
        # State / governance
        # ----------------------------------------------------

        "Decision Changed":
            decision_changed,

        "Decision Status":
            decision_status,

        "Reconciliation Status":
            reconciliation_status,

        "Reconciliation Reason":
            reconciliation_reason,

        "Governance Reasons":
            governance_flags,

        # ----------------------------------------------------
        # Deterministic evidence
        # ----------------------------------------------------

        "Evidence Score":
            round(
                evidence_score,
                2,
            ),

        "Evidence Strength":
            evidence_strength,

        "Decision Support":
            decision_support,

        "Deterministic Confidence":
            round(
                deterministic_confidence,
                2,
            ),

        "Confidence":
            round(
                deterministic_confidence,
                2,
            ),

        # ----------------------------------------------------
        # Historical evidence
        # ----------------------------------------------------

        "Historical Signal Observations":
            int(
                historical_observations
            ),

        "Historical Signal Win Rate %":
            round(
                historical_win_rate,
                2,
            ),

        "Historical Signal Average Return %":
            round(
                historical_return,
                2,
            ),

        "Historical Signal Reliability":
            historical_reliability,

        "Learning Adjusted Score":
            round(
                learning_adjusted_score,
                2,
            ),

        # ----------------------------------------------------
        # 5d recommendation horizon learning
        #
        # INFORMATIONAL ONLY.
        # ----------------------------------------------------

        "5d Recommendation Horizon":
            five_day_recommendation_horizon,

        # ----------------------------------------------------
        # LLM review
        # ----------------------------------------------------

        "LLM Assessment":
            llm_assessment,

        "LLM Review Decision":
            llm_assessment,

        "LLM Review Valid":
            (
                reviewer_status
                ==
                "LLM REVIEW COMPLETE"
            ),

        "LLM Confidence":
            round(
                llm_confidence,
                2,
            ),

        "LLM Review Confidence":
            round(
                llm_confidence,
                2,
            ),

        "LLM Reason":
            llm_reason,

        "LLM Review Reason":
            llm_reason,

        "LLM Key Points":
            review.get(
                "LLM Key Points",
                review.get(
                    "Key Points",
                    [],
                ),
            ),

        "LLM Evidence Gaps":
            review.get(
                "LLM Evidence Gaps",
                review.get(
                    "Evidence Gaps",
                    [],
                ),
            ),

        # ----------------------------------------------------
        # Final result
        # ----------------------------------------------------

        "Final Reason":
            final_reason,

        "Explanation":
            final_reason,

        # ----------------------------------------------------
        # Authority / execution
        # ----------------------------------------------------

        "Decision Authority":
            "GOVERNED AI DECISION LAYER",

        "Capital Allocation":
            "NOT PERFORMED",

        "Trade Execution":
            "NOT PERFORMED",
    })

    return result
# ============================================================
# SINGLE DECISION COMPATIBILITY API
# ============================================================

def calculate_final_portfolio_decision(
    candidate: dict | None = None,
    portfolio: dict | None = None,
    decision: dict | None = None,
    review: dict | None = None,
    explanation: dict | None = None,
    reconciled_decision: dict | None = None,
    **kwargs: Any,
) -> dict:
    """
    Compatibility interface used by the AI Decision test harness.

    This function does not invoke the entire pipeline. It maps
    already-produced chain outputs into one final decision.

    IMPORTANT
    ---------
    The original Proposed Action is preserved, including reduction
    sizing such as:

        REDUCE 25%
        REDUCE 50%
        REDUCE 75%
        REDUCE 100%

    The downstream build_final_result() function normalises REDUCE
    variants to REDUCE for governance comparison while preserving
    the original percentage for the final reported action.
    """

    candidate = (
        candidate
        if isinstance(
            candidate,
            dict,
        )
        else {}
    )

    portfolio = (
        portfolio
        if isinstance(
            portfolio,
            dict,
        )
        else {}
    )

    decision = (
        decision
        if isinstance(
            decision,
            dict,
        )
        else {}
    )

    review = (
        review
        if isinstance(
            review,
            dict,
        )
        else {}
    )

    explanation = (
        explanation
        if isinstance(
            explanation,
            dict,
        )
        else {}
    )

    reconciled_decision = (
        reconciled_decision
        if isinstance(
            reconciled_decision,
            dict,
        )
        else {}
    )

    # ========================================================
    # Candidate ownership / analysis information
    # ========================================================

    ownership = candidate.get(
        "ownership",
        {},
    )

    if not isinstance(
        ownership,
        dict,
    ):
        ownership = {}

    analysis = candidate.get(
        "analysis",
        {},
    )

    if not isinstance(
        analysis,
        dict,
    ):
        analysis = {}

    # ========================================================
    # PRESERVE THE ORIGINAL PROPOSED ACTION
    #
    # This is important for REDUCE 25% / 50% / 75% / 100%.
    #
    # Prefer the original proposal before falling back to the
    # AI decision layer's generic Action field.
    # ========================================================

    proposed_action = upper_text(
        first_value(
            decision.get(
                "Proposed Action"
            ),

            candidate.get(
                "Proposed Action"
            ),

            candidate.get(
                "proposed_action"
            ),

            candidate.get(
                "Capital Allocation Action"
            ),

            candidate.get(
                "capital_allocation_action"
            ),

            decision.get(
                "Action"
            ),

            default="HOLD",
        ),
        "HOLD",
    )

    # ========================================================
    # Build the base row consumed by build_final_result().
    #
    # DO NOT populate "Final Action" here.
    #
    # build_final_result() is responsible for determining the
    # final governed action. This prevents the compatibility
    # layer from accidentally replacing REDUCE 50% with REDUCE.
    # ========================================================

    candidate_row = {
        "Ticker":
            candidate.get(
                "ticker",
                candidate.get(
                    "Ticker",
                    decision.get(
                        "Ticker",
                        "",
                    ),
                ),
            ),

        "Asset Type":
            candidate.get(
                "asset_type",
                candidate.get(
                    "Asset Type",
                    decision.get(
                        "Asset Type",
                        "STOCK",
                    ),
                ),
            ),

        "Existing Holding":
            ownership.get(
                "owned",
                decision.get(
                    "Existing Holding",
                    False,
                ),
            ),

        "Quantity":
            ownership.get(
                "quantity",
                decision.get(
                    "Quantity",
                    0,
                ),
            ),

        "Market Value":
            ownership.get(
                "market_value",
                decision.get(
                    "Market Value",
                    0,
                ),
            ),

        "Allocation %":
            ownership.get(
                "allocation_pct",
                decision.get(
                    "Allocation %",
                    0,
                ),
            ),

        "Investment Score":
            analysis.get(
                "investment_score",
                decision.get(
                    "Investment Score",
                    0,
                ),
            ),

        "Sector":
            ownership.get(
                "sector",
                candidate.get(
                    "Sector",
                    "Unknown",
                ),
            ),

        # ----------------------------------------------------
        # THIS is the important field.
        #
        # It retains:
        #
        #     REDUCE 25%
        #     REDUCE 50%
        #     REDUCE 75%
        #     REDUCE 100%
        #
        # rather than replacing them with generic REDUCE.
        # ----------------------------------------------------

        "Proposed Action":
            proposed_action,

        "Original Reason":
            first_value(
                decision.get(
                    "Reason"
                ),
                candidate.get(
                    "Reason"
                ),
                default="",
            ),
    }

    # ========================================================
    # Final governed result
    # ========================================================

    return build_final_result(
        base_row=candidate_row,

        chain={
            "deterministic":
                decision,

            "explanation":
                explanation,

            "review":
                review,

            "reconciliation":
                reconciled_decision,
        },
    )

def final_portfolio_decision(
    candidate: dict | None = None,
    portfolio: dict | None = None,
    decision: dict | None = None,
    review: dict | None = None,
    explanation: dict | None = None,
    context: dict | None = None,
    ai_decision: dict | None = None,
    llm_review: dict | None = None,
    reconciled_decision: dict | None = None,
    **kwargs: Any,
) -> dict:
    """Compatibility alias."""

    if candidate is None:

        if isinstance(
            context,
            dict,
        ):

            candidates = context.get(
                "candidates",
                [],
            )

            if (
                isinstance(
                    candidates,
                    list,
                )
                and
                candidates
            ):

                candidate = candidates[0]

    if decision is None:
        decision = ai_decision

    if review is None:
        review = llm_review

    if portfolio is None:
        portfolio = context

    return calculate_final_portfolio_decision(
        candidate=candidate,
        portfolio=portfolio,
        decision=decision,
        review=review,
        explanation=explanation,
        reconciled_decision=reconciled_decision,
    )


def build_ticker_horizon_learning_commentary(
    learning_row,
    current_investment_score=None,
    current_signal=None,
) -> str:
    """
    Build informational ticker-level learning commentary.

    Learning is deliberately reporting-only.

    It must NOT modify:
        - proposed action
        - reconciled action
        - final action
        - confidence
        - evidence
        - investment score
        - governance
        - capital allocation
        - audit

    Horizon maturity:
        5d -> 10d -> 60d

    A mature later horizon supersedes an earlier mature horizon
    for the primary commentary.

    The commentary reports:

        1. Ticker-specific historical win rate.
        2. Number of historical recommendations.
        3. Whether the ticker-specific sample is mature.
        4. Current Investment Score.
        5. Current Signal.

    The current Investment Score is contextual only. It does not
    alter the score or any portfolio decision.

    Win Rate interpretation:

        Win Rate % represents the percentage of historical
        recommendations at that horizon that produced a positive
        outcome according to the recommendation-learning layer.

    This helper is reporting-only and has no decision authority.
    """

    if not isinstance(learning_row, dict):
        return "5D: Insufficient data"

    def value(*names):
        for name in names:
            if name in learning_row:
                return learning_row.get(name)
        return None

    def numeric(*names):
        raw = value(*names)

        if raw is None:
            return None

        try:
            return float(raw)
        except (
            TypeError,
            ValueError,
        ):
            return None

    # ============================================================
    # CURRENT DECISION CONTEXT
    #
    # These values are informational only.
    # ============================================================

    score = None

    if current_investment_score is not None:
        try:
            score = float(
                current_investment_score
            )
        except (
            TypeError,
            ValueError,
        ):
            score = None

    signal = ""

    if current_signal is not None:
        signal = str(
            current_signal
        ).strip().upper()

    # ============================================================
    # LEARNING DATA
    # ============================================================

    horizon_raw = value(
        "Horizon",
        "horizon",
        "Days",
        "days_after",
    )

    observations = numeric(
        "Recommendations",
        "Observations",
        "Observation Count",
        "Outcome Count",
        "Count",
        "outcome_count",
    )

    win_rate = numeric(
        "Win Rate %",
        "Win Rate",
        "win_rate",
        "win_rate_pct",
    )

    average_return = numeric(
        "Average Return %",
        "Average Return",
        "average_return",
        "Mean Return",
    )

    reliability = value(
        "Reliability",
        "reliability",
    )

    # ============================================================
    # HORIZON
    # ============================================================

    horizon_text = (
        str(horizon_raw).strip().lower()
        if horizon_raw is not None
        else ""
    )

    if "60" in horizon_text:
        horizon = 60

    elif "10" in horizon_text:
        horizon = 10

    elif "5" in horizon_text:
        horizon = 5

    else:
        horizon = None

    # ============================================================
    # MATURITY
    #
    # These are reporting thresholds only.
    # ============================================================

    MIN_OBSERVATIONS = {
        5: 20,
        10: 20,
        60: 20,
    }

    # ============================================================
    # NO HORIZON
    # ============================================================

    if horizon is None:

        commentary = []

        if score is not None:
            commentary.append(
                f"Current Investment Score: "
                f"{score:.0f}"
            )

        if signal:
            commentary.append(
                f"Current Signal: {signal}"
            )

        if not commentary:
            return "5D: Insufficient data"

        return " | ".join(
            commentary
        )

    # ============================================================
    # OBSERVATION COUNT
    # ============================================================

    if observations is None:

        count_text = "unknown"

    elif observations.is_integer():

        count_text = str(
            int(observations)
        )

    else:

        count_text = str(
            observations
        )

    minimum_required = MIN_OBSERVATIONS[
        horizon
    ]

    # ============================================================
    # BASE LEARNING COMMENTARY
    # ============================================================

    prefix = f"{horizon}D"

    if observations is None or observations < minimum_required:

        commentary = (
            f"{prefix}: Insufficient data "
            f"({count_text} recommendations; "
            f"{minimum_required} required)"
        )

    else:

        # --------------------------------------------------------
        # Mature ticker-specific learning.
        # --------------------------------------------------------

        if win_rate is None:

            commentary = (
                f"{prefix}: Mature sample "
                f"({count_text} recommendations); "
                f"win rate unavailable"
            )

        else:

            commentary = (
                f"{prefix}: {win_rate:.1f}% win rate "
                f"({count_text} recommendations) "
                f"— mature sample"
            )

        # --------------------------------------------------------
        # Include average return when available.
        # --------------------------------------------------------

        if average_return is not None:

            commentary += (
                f"; average return "
                f"{average_return:.2f}%"
            )

        # --------------------------------------------------------
        # Include reliability when available.
        # --------------------------------------------------------

        if (
            reliability is not None
            and str(reliability).strip()
            and str(reliability).strip().lower()
            != "nan"
        ):

            commentary += (
                f"; reliability "
                f"{str(reliability).strip()}"
            )

    # ============================================================
    # CURRENT INVESTMENT SCORE
    #
    # This is deliberately descriptive only.
    # ============================================================

    if score is not None:

        commentary += (
            f". Current Investment Score: "
            f"{score:.0f}"
        )

    # ============================================================
    # CURRENT SIGNAL
    #
    # Also descriptive only.
    # ============================================================

    if signal:

        commentary += (
            f". Current Signal: {signal}"
        )

    # ============================================================
    # EXPLICIT GOVERNANCE BOUNDARY
    #
    # Keep this short in the report. Learning is not decision
    # authority.
    # ============================================================

    commentary += (
        ". Learning is informational only"
    )

    return commentary
    def value(*names):
        for name in names:
            if name in learning_row:
                return learning_row.get(name)
        return None

    def numeric(*names):
        raw = value(*names)

        if raw is None:
            return None

        try:
            return float(raw)
        except (
            TypeError,
            ValueError,
        ):
            return None

    # ------------------------------------------------------------
    # Resolve horizon-specific observations.
    #
    # The ticker-horizon learning output may expose horizon
    # information using the exact column names produced by the
    # learning layer. Keep this helper tolerant of common naming
    # variants without changing the underlying learning data.
    # ------------------------------------------------------------

    horizon_raw = value(
        "Horizon",
        "horizon",
        "Days",
        "days_after",
    )

    observations = numeric(
        "Observations",
        "Observation Count",
        "Outcome Count",
        "Count",
        "outcome_count",
    )

    win_rate = numeric(
        "Win Rate",
        "win_rate",
    )

    average_return = numeric(
        "Average Return",
        "average_return",
        "Mean Return",
    )

    average_score_change = numeric(
        "Average Score Change",
        "average_score_change",
        "Score Change",
        "score_change",
    )

    learning_direction = value(
        "Learning Direction",
        "learning_direction",
        "Outcome",
        "outcome",
    )

    # ------------------------------------------------------------
    # Determine horizon.
    # ------------------------------------------------------------

    horizon_text = (
        str(horizon_raw).strip().lower()
        if horizon_raw is not None
        else ""
    )

    if "60" in horizon_text:
        horizon = 60
    elif "10" in horizon_text:
        horizon = 10
    elif "5" in horizon_text:
        horizon = 5
    else:
        horizon = None

    # ------------------------------------------------------------
    # Minimum maturity thresholds.
    #
    # These are deliberately reporting thresholds only.
    # They do NOT participate in portfolio decision governance.
    # ------------------------------------------------------------

    MIN_OBSERVATIONS = {
        5: 20,
        10: 20,
        60: 20,
    }

    # ------------------------------------------------------------
    # If the learning output is not horizon-specific, return a
    # conservative informational message rather than attempting
    # to infer a decision.
    # ------------------------------------------------------------

    if horizon is None:
        if observations is None:
            return "5d: insufficient data"

        return (
            f"learning observations: "
            f"{int(observations) if observations.is_integer() else observations}"
        )

    # ------------------------------------------------------------
    # Determine whether this horizon is mature.
    # ------------------------------------------------------------

    minimum_required = MIN_OBSERVATIONS[horizon]

    if (
        observations is None
        or observations < minimum_required
    ):
        count_text = (
            "unknown"
            if observations is None
            else (
                str(int(observations))
                if observations.is_integer()
                else str(observations)
            )
        )

        return (
            f"{horizon}d: insufficient data "
            f"(outcome count is {count_text})"
        )

    # ------------------------------------------------------------
    # Mature horizon.
    #
    # Later mature horizons supersede earlier mature horizons.
    # Because this function receives the selected ticker/horizon
    # record, the learning layer remains responsible for supplying
    # the appropriate horizon record.
    # ------------------------------------------------------------

    parts = [
        f"{horizon}d learning"
    ]

    if learning_direction not in (
        None,
        "",
        "nan",
    ):
        parts.append(
            str(learning_direction).strip()
        )

    if average_score_change is not None:
        sign = "+" if average_score_change > 0 else ""

        parts.append(
            f"score change {sign}"
            f"{average_score_change:.1f}"
        )

    elif average_return is not None:
        sign = "+" if average_return > 0 else ""

        parts.append(
            f"average return {sign}"
            f"{average_return:.1f}%"
        )

    elif win_rate is not None:
        parts.append(
            f"win rate {win_rate:.1f}%"
        )

    parts.append(
        f"(outcome count is "
        f"{int(observations) if observations.is_integer() else observations})"
    )

    return " — ".join(parts)


# ============================================================
# PRODUCTION ENTRY POINT
# ============================================================

# ============================================================
# PRODUCTION ENTRY POINT
# ============================================================

def generate_final_portfolio_decisions(
    portfolio_summary,
    portfolio_decisions,
    portfolio_ai_review,
    portfolio_manager_review,
    portfolio_health,
    capital_allocation,
    recommendation_intelligence=None,
    learning_ticker_horizon_performance=None,
    **kwargs,
):
    """
    Generate the production Final Portfolio Decisions table.

    IMPORTANT
    ---------
    portfolio_decisions provides the existing rules-based proposal.

    Existing holdings come ONLY from portfolio_summary.

    New candidates come ONLY from Capital Allocation and only when
    Capital Allocation proposes BUY NEW.

    Every eligible row then executes the complete AI chain.

    Learning
    --------
    Ticker/horizon learning is attached to each candidate before the
    governed AI chain executes. Learning is informational only and
    must not directly alter deterministic scoring, reconciliation,
    governance, or the final action.

    Audit
    -----
    A single audit_run is created for the complete production
    decision population. Each successfully processed decision is
    recorded against that audit_run_id.

    The audit layer is observational only and must never alter the
    decision produced by the governed AI chain.
    """

    population = build_eligible_population(
        portfolio_summary=portfolio_summary,
        portfolio_decisions=portfolio_decisions,
        capital_allocation=capital_allocation,
    )

    if not population:

        print(
            "FINAL PORTFOLIO DECISION POPULATION: 0"
        )

        return pd.DataFrame()

    # --------------------------------------------------------
    # Preserve existing portfolio health.
    # --------------------------------------------------------

    health = (
        portfolio_health
        if isinstance(
            portfolio_health,
            dict,
        )
        else {}
    )

    portfolio_risk = safe_text(
        health.get(
            "Risk Level",
            "NORMAL",
        ),
        "NORMAL",
    ).upper()

    results = []

    # --------------------------------------------------------
    # Build ticker/horizon learning lookup.
    #
    # Structure:
    #
    # {
    #     "NVDA": {
    #         5:  {...},
    #         10: {...},
    #         60: {...},
    #     },
    #     ...
    # }
    #
    # Learning is attached to the candidate and passed through
    # the existing governed chain.
    # --------------------------------------------------------

    ticker_horizon_lookup = {}

    

    if (
        isinstance(
            learning_ticker_horizon_performance,
            pd.DataFrame,
        )
        and not learning_ticker_horizon_performance.empty
    ):

        for _, row in learning_ticker_horizon_performance.iterrows():

            ticker = safe_text(
                row.get("Ticker"),
                "",
            ).upper()

            if not ticker:
                continue

            horizon = row.get(
                "Horizon",
                row.get(
                    "Days",
                    None,
                ),
            )

            try:
                horizon = int(
                    float(
                        horizon
                    )
                )
            except (
                TypeError,
                ValueError,
            ):
                continue

            if horizon not in {
                5,
                10,
                60,
            }:
                continue

            ticker_horizon_lookup.setdefault(
                ticker,
                {}
            )[horizon] = row.to_dict()
    # --------------------------------------------------------
    # Start ONE audit run for the complete production decision
    # population.
    #
    # SQLite is the source of truth for audit data.
    # --------------------------------------------------------

    audit_run = start_audit_run(
        environment="pre-production",
        code_version="final_portfolio_decision",
    )

    audit_run_id = int(
        audit_run["id"]
    )

    audit_conn = get_connection()

    # --------------------------------------------------------
    # Run the complete AI chain per candidate.
    # --------------------------------------------------------

    for base_row in population:

        ticker = get_ticker(
            base_row
        )

        if not ticker:
            continue

        if ticker.upper() == "CASH":
            continue

        # ----------------------------------------------------
        # Copy the candidate before attaching additional
        # context so the original population object is not
        # modified unexpectedly.
        # ----------------------------------------------------

        base_row = dict(
            base_row
        )

        # ----------------------------------------------------
        # Attach portfolio risk explicitly.
        #
        # This does not change the decision. It ensures the
        # final result can expose the portfolio health context.
        # ----------------------------------------------------

        base_row[
            "Portfolio Risk"
        ] = portfolio_risk

        # ----------------------------------------------------
        # Attach ticker-specific horizon learning.
        #
        # Learning is informational only.
        #
        # It must NOT directly modify:
        #     - Investment Score
        #     - Evidence Score
        #     - Confidence
        #     - Governance
        #     - Reconciliation
        #     - Final Decision
        #     - Capital Allocation
        # ----------------------------------------------------

        ticker_learning = ticker_horizon_lookup.get(
            ticker.upper(),
            {},
        )

        if not isinstance(
            ticker_learning,
            dict,
        ):
            ticker_learning = {}

        base_row[
            "learning_ticker_horizon_performance"
        ] = ticker_learning

        # ----------------------------------------------------
        # Explicit production population protection.
        #
        # Existing holdings are determined ONLY from
        # portfolio_summary.
        #
        # Non-owned assets are eligible ONLY when Capital
        # Allocation explicitly proposes BUY NEW.
        # ----------------------------------------------------

        owned = False

        summary = normalise_tickers(
            safe_dataframe(
                portfolio_summary
            )
        )

        if (
            not summary.empty
            and
            "Ticker" in summary.columns
        ):

            matches = summary[
                summary[
                    "Ticker"
                ]
                .astype(str)
                .str.strip()
                .str.upper()
                ==
                ticker.upper()
            ]

            if not matches.empty:

                holding_record = (
                    matches.iloc[0].to_dict()
                )

                owned = is_owned(
                    holding_record
                )

        proposed_action = get_capital_action(
            base_row
        )

        # Existing holding:
        #     allowed regardless of proposal.
        #
        # Non-owned:
        #     only BUY NEW is allowed.
        if (
            not owned
            and
            proposed_action != "BUY NEW"
        ):

            continue

        # ----------------------------------------------------
        # Run complete governed AI chain.
        # ----------------------------------------------------

        try:

            chain = run_governed_chain(
                portfolio_summary=portfolio_summary,
                base_row=base_row,
                capital_allocation=capital_allocation,
                recommendation_intelligence=(
                    recommendation_intelligence
                ),
            )

            result = build_final_result(

                base_row=base_row,

                chain=chain,

                ticker_horizon_learning=(
                    ticker_learning
                ),

            )

            # ------------------------------------------------
            # Ensure portfolio risk remains available in the
            # final report even if the chain does not return it.
            # ------------------------------------------------

            if not result.get(
                "Portfolio Risk"
            ):

                result[
                    "Portfolio Risk"
                ] = portfolio_risk

            # ------------------------------------------------
            # Record the exact governed decision chain.
            #
            # Audit capture is observational only.
            # It does not modify result or influence the
            # decision.
            # ------------------------------------------------

            try:

                print(
                    f"AUDIT CAPTURE: {ticker} | "
                    f"Proposed={result.get('Proposed Action')} | "
                    f"Final={result.get('Final Action')}"
                )

                record_decision_audit(
                    conn=audit_conn,
                    audit_run_id=audit_run_id,
                    base_row=base_row,
                    chain=chain,
                    final_result=result,
                )

            except Exception as audit_exc:

                print(
                    f"WARNING: Audit capture failed for "
                    f"{ticker}: {audit_exc}"
                )

        except Exception as exc:

            # ------------------------------------------------
            # A pipeline error can never create a transaction.
            #
            # The candidate remains in the output as HOLD so
            # that the failure is visible rather than silently
            # disappearing from the production decision table.
            # ------------------------------------------------

            result = dict(
                base_row
            )

            result[
                "Ticker"
            ] = ticker

            result[
                "Portfolio Risk"
            ] = portfolio_risk

            result[
                "Proposed Action"
            ] = proposed_action

            result[
                "Original Decision"
            ] = proposed_action

            result[
                "Final Decision"
            ] = "HOLD"

            result[
                "Final Action"
            ] = "HOLD"

            result[
                "Action"
            ] = "HOLD"

            result[
                "Decision Changed"
            ] = (
                proposed_action
                !=
                "HOLD"
            )

            result[
                "Decision Status"
            ] = "AI CHAIN ERROR"

            result[
                "Evidence Score"
            ] = 0.0

            result[
                "Evidence Strength"
            ] = "VERY WEAK"

            result[
                "Decision Support"
            ] = "NOT SUPPORTED"

            result[
                "Deterministic Confidence"
            ] = 0.0

            result[
                "Confidence"
            ] = 0.0

            result[
                "LLM Assessment"
            ] = "CHALLENGE"

            result[
                "LLM Review Valid"
            ] = False

            result[
                "LLM Confidence"
            ] = 0.0

            result[
                "LLM Reason"
            ] = (
                "AI decision chain error: "
                f"{exc}"
            )

            result[
                "LLM Review Reason"
            ] = result[
                "LLM Reason"
            ]

            result[
                "LLM Key Points"
            ] = []

            result[
                "LLM Evidence Gaps"
            ] = [
                "AI decision chain error"
            ]

            result[
                "Reconciled Decision"
            ] = "HOLD"

            result[
                "Reconciliation Status"
            ] = "AI CHAIN ERROR"

            result[
                "Reconciliation Reason"
            ] = str(
                exc
            )

            result[
                "Governance Reasons"
            ] = [
                (
                    "AI decision chain error: "
                    f"{exc}"
                )
            ]

            result[
                "Final Reason"
            ] = (
                f"{ticker} remains HOLD because "
                f"the governed AI chain failed: {exc}"
            )

            result[
                "Explanation"
            ] = result[
                "Final Reason"
            ]

            result[
                "Decision Authority"
            ] = (
                "GOVERNED AI DECISION LAYER"
            )

            result[
                "Capital Allocation"
            ] = "NOT PERFORMED"

            result[
                "Trade Execution"
            ] = "NOT PERFORMED"

        results.append(
            result
        )

    # --------------------------------------------------------
    # Build dataframe.
    # --------------------------------------------------------

    result_df = pd.DataFrame(
        results
    )

    if result_df.empty:

        print(
            "FINAL PORTFOLIO DECISION POPULATION: 0"
        )

        # Close the audit connection even when no rows survived.
        try:
            audit_conn.close()
        except Exception:
            pass

        try:

            complete_audit_run(
                audit_run_id=audit_run_id,
                total_decisions=0,
                changed_decisions=0,
            )

        except Exception as audit_exc:

            print(
                f"WARNING: Audit run completion failed: "
                f"{audit_exc}"
            )

        result_df.attrs[
            "audit_run_id"
        ] = audit_run_id

        return result_df

    # --------------------------------------------------------
    # CASH safety filter.
    # --------------------------------------------------------

    if "Ticker" in result_df.columns:

        result_df[
            "Ticker"
        ] = (
            result_df[
                "Ticker"
            ]
            .astype(str)
            .str.strip()
            .str.upper()
        )

        result_df = result_df[
            result_df[
                "Ticker"
            ]
            != "CASH"
        ]

    # --------------------------------------------------------
    # One row per ticker.
    # --------------------------------------------------------

    result_df = (
        result_df
        .drop_duplicates(
            subset=[
                "Ticker"
            ],
            keep="last",
        )
        .reset_index(
            drop=True
        )
    )

    # --------------------------------------------------------
    # Report column order.
    # --------------------------------------------------------

    preferred_columns = [
        "Ticker",
        "Asset Type",
        "Existing Holding",
        "Sector",
        "Investment Score",
        "ETF Score",
        "Quality Score",
        "Growth Score",
        "Signal",
        "ETF Signal",
        "Portfolio Risk",
        "Portfolio Allocation %",
        "Proposed Action",
        "Original Decision",
        "Original Reason",
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
        "Evidence Score",
        "Evidence Strength",
        "Decision Support",
        "Deterministic Confidence",
        "Confidence",
        "LLM Assessment",
        "LLM Review Valid",
        "LLM Confidence",
        "LLM Reason",
        "LLM Key Points",
        "LLM Evidence Gaps",
        "Reconciled Decision",
        "Reconciliation Status",
        "Reconciliation Reason",
        "Final Decision",
        "Final Reason",
        "Final Action",
        "Decision Changed",
        "Decision Status",
        "Governance Reasons",
        "Review Triggers",
        "Risks",
        "Actions",
        "Learning Adjusted Score",
        "Ticker Horizon Learning Commentary",
        "Decision Authority",
        "Capital Allocation",
        "Trade Execution",
        "Explanation",
    ]

    columns = [
        column
        for column in preferred_columns
        if column in result_df.columns
    ]

    columns += [
        column
        for column in result_df.columns
        if column not in columns
    ]

    result_df = result_df[
        columns
    ]

    # --------------------------------------------------------
    # Diagnostics.
    # --------------------------------------------------------

    existing_count = int(
        result_df[
            "Existing Holding"
        ]
        .map(
            safe_bool
        )
        .sum()
    )

    buy_new_count = int(
        (
            result_df[
                "Proposed Action"
            ]
            .astype(str)
            .str.upper()
            ==
            "BUY NEW"
        ).sum()
    )

    final_counts = (
        result_df[
            "Final Decision"
        ]
        .value_counts()
        .to_dict()
    )

    print()
    print(
        "FINAL PORTFOLIO DECISION POPULATION"
    )

    print(
        f"Existing holdings reviewed: "
        f"{existing_count}"
    )

    print(
        f"BUY NEW proposals reviewed: "
        f"{buy_new_count}"
    )

    print(
        f"Total final decisions: "
        f"{len(result_df)}"
    )

    print(
        "Final action counts:",
        final_counts,
    )

    # --------------------------------------------------------
    # Complete the audit run after the full decision population
    # has been processed.
    #
    # record_decision_audit() uses the shared audit connection.
    # Close it before complete_audit_run(), which opens its own
    # connection, to avoid SQLite database-lock contention.
    # --------------------------------------------------------

    try:

        audit_conn.close()

    except Exception as audit_close_exc:

        print(
            f"WARNING: Audit connection close failed: "
            f"{audit_close_exc}"
        )

    try:

        audited_total_decisions, audited_changed_decisions = (
            get_audit_run_counts(
                audit_run_id
            )
        )

        complete_audit_run(
            audit_run_id=audit_run_id,
            total_decisions=audited_total_decisions,
            changed_decisions=audited_changed_decisions,
        )

    except Exception as audit_exc:

        print(
            f"WARNING: Audit run completion failed: "
            f"{audit_exc}"
        )

    # --------------------------------------------------------
    # Propagate the audit run ID to the report layer.
    #
    # The Excel reporting layer can use this exact ID to retrieve
    # the audit records associated with this production execution.
    # --------------------------------------------------------

    result_df.attrs[
        "audit_run_id"
    ] = audit_run_id

    return result_df

# ============================================================
# TEST-HARNESS BATCH INTERFACE
# ============================================================

def calculate_final_portfolio_decisions(
    candidates=None,
    portfolios=None,
    decisions=None,
    reviews=None,
    explanations=None,
):
    """
    Compatibility batch interface for the AI decision test harness.

    This function maps already-produced chain outputs; it does not
    invoke Llama itself.
    """

    candidates = (
        candidates
        if isinstance(
            candidates,
            list,
        )
        else []
    )

    portfolios = (
        portfolios
        if isinstance(
            portfolios,
            list,
        )
        else []
    )

    decisions = (
        decisions
        if isinstance(
            decisions,
            list,
        )
        else []
    )

    reviews = (
        reviews
        if isinstance(
            reviews,
            list,
        )
        else []
    )

    explanations = (
        explanations
        if isinstance(
            explanations,
            list,
        )
        else []
    )

    count = max(
        len(candidates),
        len(portfolios),
        len(decisions),
        len(reviews),
        len(explanations),
    )

    results = []

    for index in range(
        count
    ):

        results.append(
            calculate_final_portfolio_decision(
                candidate=(
                    candidates[
                        index
                    ]
                    if index
                    <
                    len(
                        candidates
                    )
                    else {}
                ),
                portfolio=(
                    portfolios[
                        index
                    ]
                    if index
                    <
                    len(
                        portfolios
                    )
                    else {}
                ),
                decision=(
                    decisions[
                        index
                    ]
                    if index
                    <
                    len(
                        decisions
                    )
                    else {}
                ),
                review=(
                    reviews[
                        index
                    ]
                    if index
                    <
                    len(
                        reviews
                    )
                    else {}
                ),
                explanation=(
                    explanations[
                        index
                    ]
                    if index
                    <
                    len(
                        explanations
                    )
                    else {}
                ),
            )
        )

    return results


# ============================================================
# COMPATIBILITY BATCH ALIAS
# ============================================================

def calculate_final_portfolio_decision_batch(
    *args: Any,
    **kwargs: Any,
):
    """Compatibility alias for the batch test harness."""

    return calculate_final_portfolio_decisions(
        *args,
        **kwargs,
    )


# ============================================================
# MODULE TEST
# ============================================================

if __name__ == "__main__":

    print(
        "Final Portfolio Decision Engine"
    )

    print(
        "Architecture:"
    )

    print(
        "  Context"
    )

    print(
        "    -> Scoring"
    )

    print(
        "    -> Decision Layer"
    )

    print(
        "    -> Explanation"
    )

    print(
        "    -> LLM Reviewer"
    )

    print(
        "    -> Reconciliation"
    )

    print(
        "    -> Final Portfolio Decision"
    )

    print(
        "Module loaded successfully."
    )