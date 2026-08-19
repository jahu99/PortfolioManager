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

    Includes:

        - every existing investment holding
        - every non-owned BUY NEW opportunity

    Excludes CASH and the non-owned market universe.
    """

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

    # --------------------------------------------------------
    # Remove CASH from every source.
    # --------------------------------------------------------

    for dataframe_name, dataframe in (
        ("holdings", holdings),
        ("decisions", decisions),
        ("capital", capital),
    ):

        if (
            not dataframe.empty
            and
            "Ticker" in dataframe.columns
        ):

            dataframe.drop(
                dataframe[
                    dataframe[
                        "Ticker"
                    ].astype(str)
                    .str.strip()
                    .str.upper()
                    == "CASH"
                ].index,
                inplace=True,
            )

    # --------------------------------------------------------
    # Existing holdings are authoritative from holdings_raw.csv
    # as represented by portfolio_summary.
    # --------------------------------------------------------

    holding_lookup = {}

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

            if not ticker:
                continue

            if get_quantity(
                record
            ) > 0:

                holding_lookup[
                    ticker
                ] = record

    # --------------------------------------------------------
    # Capital Allocation is authoritative for the transaction
    # proposal.
    # --------------------------------------------------------

    capital_lookup = build_capital_lookup(
        capital_allocation
    )

    population = {}

    print(
        "HOLDING LOOKUP TICKERS:",
        sorted(
            holding_lookup.keys()
        )
    )

    # --------------------------------------------------------
    # First add every existing holding.
    # --------------------------------------------------------

    for ticker, holding in holding_lookup.items():

        base = dict(
            holding
        )

        allocation_row = capital_lookup.get(
            ticker
        )

        if allocation_row:

            for key, value in allocation_row.items():

                if (
                    key not in base
                    or
                    pd.isna(
                        base.get(
                            key
                        )
                    )
                ):

                    base[
                        key
                    ] = value

        # Existing holdings are allowed through regardless of
        # whether Capital Allocation selected an action.
        population[
            ticker
        ] = base

    # --------------------------------------------------------
    # Add ONLY non-owned BUY NEW proposals.
    # --------------------------------------------------------

    for ticker, allocation_row in capital_lookup.items():

        if ticker in holding_lookup:
            continue

        action = get_capital_action(
            allocation_row
        )

        if action != "BUY NEW":
            continue

        base = dict(
            allocation_row
        )

        base[
            "Existing Holding"
        ] = False

        population[
            ticker
        ] = base

        print(
            "ELIGIBLE POPULATION TICKERS:",
            sorted(
                population.keys()
            )
        )

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

    asset_type = get_asset_type(
        base_row
    )

    proposed_action = get_capital_action(
        base_row
    )

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

        "analysis": {

            "investment_score":
                safe_float(
                    row_value(
                        base_row,
                        "Investment Score",
                        "investment_score",
                        default=0,
                    )
                ),

            "quality_score":
                safe_float(
                    row_value(
                        base_row,
                        "Quality Score",
                        "quality_score",
                        default=0,
                    )
                ),

            "growth_score":
                safe_float(
                    row_value(
                        base_row,
                        "Growth Score",
                        "growth_score",
                        default=0,
                    )
                ),

            "signal":
                upper_text(
                    row_value(
                        base_row,
                        "Signal",
                        "signal",
                        "Momentum Signal",
                        default="",
                    )
                ),

            "risk_score":
                safe_float(
                    row_value(
                        base_row,
                        "Risk Score",
                        "risk_score",
                        default=0,
                    )
                ),
        },

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
    Run the complete agreed AI decision chain.

    Context
        ↓
    Scoring via Decision Layer
        ↓
    Decision Layer
        ↓
    Explanation
        ↓
    Llama Review
        ↓
    Reconciliation

    Historical recommendation intelligence is passed through
    from the existing recommendation-intelligence engine.

    The immutable recommendation evidence snapshot is loaded
    by build_ai_decision_context() using the Recommendation ID.
    """

    ticker = get_ticker(
        base_row
    )

    # --------------------------------------------------------
    # Identify the exact recommendation used to create the
    # evidence snapshot.
    # --------------------------------------------------------

    recommendation_id = get_latest_recommendation_id(
        ticker=ticker,
        recommendation_date=base_row.get(
            "Date",
            base_row.get(
                "date",
                None
            )
        )
    )

    # --------------------------------------------------------
    # Build current candidate input.
    #
    # This contains the authoritative current portfolio
    # ownership and rules-based proposal.
    # --------------------------------------------------------

    candidate_input = build_chain_candidate(
        base_row=base_row,
        portfolio_summary=portfolio_summary,
    )

    # --------------------------------------------------------
    # Historical recommendation intelligence
    #
    # IMPORTANT:
    #
    # recommendation_intelligence is normally a DataFrame
    # generated by recommendation_intelligence.py.
    #
    # The AI Decision Context Builder already knows how to:
    #
    #     DataFrame
    #         ↓
    #     ticker lookup
    #         ↓
    #     matching intelligence record
    #
    # Therefore we pass the complete existing object through.
    #
    # If no intelligence was supplied at all, retain the
    # existing backwards-compatible fallback.
    # --------------------------------------------------------

    intelligence_input = (
        recommendation_intelligence
        if recommendation_intelligence is not None
        else [
            build_intelligence_record(
                base_row
            )
        ]
    )

    # --------------------------------------------------------
    # AI Decision Context
    # --------------------------------------------------------

    context = build_ai_decision_context(
        portfolio=portfolio_summary,

        candidate_decisions=[
            {
                "Ticker":
                    ticker,

                # ------------------------------------------------
                # Recommendation ID allows the context builder
                # to retrieve the immutable recommendation
                # evidence snapshot.
                # ------------------------------------------------

                "Recommendation ID":
                    recommendation_id,

                "Asset Type":
                    candidate_input[
                        "asset_type"
                    ],

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

                "Investment Score":
                    candidate_input[
                        "analysis"
                    ][
                        "investment_score"
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

                "Risk Score":
                    candidate_input[
                        "analysis"
                    ][
                        "risk_score"
                    ],
            }
        ],

        # --------------------------------------------------------
        # IMPORTANT:
        #
        # Pass the existing intelligence DataFrame through.
        #
        # build_ai_decision_context() is responsible for turning
        # it into the correct ticker-specific intelligence record.
        # --------------------------------------------------------

        recommendation_intelligence=
            intelligence_input,

        capital_allocation=
            capital_allocation,
    )

    # --------------------------------------------------------
    # Validate context.
    # --------------------------------------------------------

    candidates = context.get(
        "candidates",
        [],
    )

    if not candidates:

        raise ValueError(
            f"AI Decision Context produced no candidate for {ticker}"
        )

    candidate = candidates[0]

    # --------------------------------------------------------
    # Preserve authoritative current-state fields.
    #
    # IMPORTANT:
    #
    # Do NOT overwrite candidate["analysis"].
    #
    # build_ai_decision_context() has already enriched analysis
    # using the immutable recommendation_evidence snapshot.
    #
    # Do NOT overwrite candidate["recommendation_intelligence"].
    #
    # The context builder has already selected the matching
    # ticker's historical intelligence record.
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # DO NOT DO THIS:
    #
    # candidate["analysis"] = candidate_input["analysis"]
    #
    # It would discard the recommendation evidence snapshot.
    #
    # Also do not overwrite:
    #
    # candidate["recommendation_intelligence"]
    #
    # because build_ai_decision_context() has already enriched
    # it from the supplied intelligence data.
    # --------------------------------------------------------

    # --------------------------------------------------------
    # AI Decision Layer
    #
    # This calls ai_decision_scoring.py internally.
    # --------------------------------------------------------

    print(
        f"CALLING AI DECISION LAYER: {ticker}"
    )

    deterministic = generate_ai_decision(
        portfolio=context,
        candidate=candidate,
    )

    if not isinstance(
        deterministic,
        dict,
    ):

        raise ValueError(
            f"AI Decision Layer returned invalid output for {ticker}"
        )

    print(
        f"AI DECISION LAYER COMPLETE: {ticker}"
    )

    # --------------------------------------------------------
    # Explanation before LLM review.
    # --------------------------------------------------------

    explanation = explain_ai_decision(
        candidate=candidate,
        decision=deterministic,
        review={},
    )

    if not isinstance(
        explanation,
        dict,
    ):

        explanation = {}

    # --------------------------------------------------------
    # AI Portfolio Reviewer / Llama
    # --------------------------------------------------------

    print(
        f"CALLING LLM REVIEWER: {ticker}"
    )

    try:

        llm_review = review_ai_decision(
            candidate=candidate,
            portfolio=context,
            decision=deterministic,
        )

    except Exception as exc:

        llm_review = {
            "Ticker":
                ticker,

            "LLM Assessment":
                "CHALLENGE",

            "LLM Confidence":
                0.0,

            "LLM Reason":
                (
                    "Production reviewer error: "
                    f"{exc}"
                ),

            "LLM Key Points":
                [],

            "LLM Evidence Gaps":
                [
                    "Production reviewer exception"
                ],

            "Reviewer Status":
                "LLM REVIEW ERROR",
        }

    if not isinstance(
        llm_review,
        dict,
    ):

        llm_review = {
            "Ticker":
                ticker,

            "LLM Assessment":
                "CHALLENGE",

            "LLM Confidence":
                0.0,

            "LLM Reason":
                "Invalid LLM reviewer output.",

            "LLM Key Points":
                [],

            "LLM Evidence Gaps":
                [
                    "Invalid LLM reviewer output"
                ],

            "Reviewer Status":
                "LLM REVIEW ERROR",
        }

    print(
        f"LLM REVIEWER RETURNED: {ticker} | "
        f"{llm_review.get('Reviewer Status', 'UNKNOWN')} | "
        f"{llm_review.get('LLM Assessment', 'UNKNOWN')} | "
        f"{llm_review.get('LLM Confidence', 0)}"
    )

    # --------------------------------------------------------
    # Explanation with the actual LLM review.
    # --------------------------------------------------------

    explanation = explain_ai_decision(
        candidate=candidate,
        decision=deterministic,
        review=llm_review,
    )

    if not isinstance(
        explanation,
        dict,
    ):

        explanation = {}

    # --------------------------------------------------------
    # AI Decision Reconciler
    #
    # IMPORTANT:
    # The local reconciler contract is:
    #
    #     reconcile_ai_decision(
    #         decision=...,
    #         review=...,
    #     )
    # --------------------------------------------------------

    print(
        f"CALLING RECONCILER: {ticker}"
    )

    try:

        reconciliation = reconcile_ai_decision(
            decision=deterministic,
            review=llm_review,
        )

    except Exception as exc:

        reconciliation = {
            "Reconciled Action":
                "HOLD",

            "Status":
                "RECONCILIATION ERROR",

            "Reason":
                (
                    "AI decision reconciliation failed: "
                    f"{exc}"
                ),

            "Governance Flags":
                [
                    "RECONCILIATION ERROR"
                ],

            "Automatic Approval":
                False,
        }

    if not isinstance(
        reconciliation,
        dict,
    ):

        reconciliation = {
            "Reconciled Action":
                "HOLD",

            "Status":
                "RECONCILIATION ERROR",

            "Reason":
                "Invalid reconciliation output.",

            "Governance Flags":
                [
                    "RECONCILIATION ERROR"
                ],

            "Automatic Approval":
                False,
        }

    print(
        f"RECONCILER RETURNED: {ticker} | "
        f"{reconciliation.get('Reconciled Action', 'HOLD')} | "
        f"{reconciliation.get('Reconciliation Status', 'UNKNOWN')}"
    )

    # --------------------------------------------------------
    # Return complete governed chain.
    # --------------------------------------------------------

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
            llm_review,

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
) -> dict:
    """
    Convert the full AI decision chain into the
    Final Portfolio Decisions report contract.

    Important
    ---------
    The original proposed action is preserved exactly, including
    reduction percentages such as REDUCE 25%.

    Governance comparisons use a normalised action:

        REDUCE 25% -> REDUCE

    This keeps governance logic separate from capital-allocation
    sizing.
    """

    result = dict(
        base_row
    )

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

    ticker = get_ticker(
        base_row
    )

    # ========================================================
    # Original deterministic proposal
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

    # Preserve REDUCE percentage variants exactly.
    #
    # Example:
    #     REDUCE 25%
    #     REDUCE 50%
    #
    # The governance engine works with REDUCE, while the original
    # proposal remains available for reporting/capital allocation.
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
    # Reconciliation
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
    # Final action
    #
    # Governance comparisons use the NORMALISED proposal.
    # This is critical for:
    #
    #     REDUCE 25%
    #         vs
    #     REDUCE
    #
    # ========================================================

    if normalised_proposed_action == "HOLD":

        final_action = "HOLD"

    elif (
        reconciled_action
        ==
        normalised_proposed_action
    ):

        final_action = (
            normalised_proposed_action
        )

    elif (
        normalised_proposed_action
        ==
        "BUY NEW"
        and
        not is_owned(
            base_row
        )
    ):

        final_action = "NO ACTION"

    else:

        final_action = "HOLD"

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
    # ========================================================

    # --------------------------------------------------------
    # Compare governed actions, not sizing variants.
    #
    # REDUCE 25%, REDUCE 50%, etc. are all the same governance
    # action: REDUCE.
    # --------------------------------------------------------

    decision_changed = (
        final_action
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

    elif final_action == "REDUCE":

        final_reason = (
            f"{ticker} is approved for REDUCE after passing "
            "the governed AI decision chain."
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
    # ========================================================

    result.update({

        # ----------------------------------------------------
        # Core identity
        # ----------------------------------------------------

        "Ticker":
            ticker,

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
            candidate.get(
                "ownership",
                {},
            ).get(
                "owned",
                decision.get(
                    "Existing Holding",
                    False,
                ),
            ),

        "Investment Score":
            candidate.get(
                "analysis",
                {},
            ).get(
                "investment_score",
                decision.get(
                    "Investment Score",
                    0,
                ),
            ),

        "Sector":
            candidate.get(
                "ownership",
                {},
            ).get(
                "sector",
                "Unknown",
            ),

        "Final Action":
            decision.get(
                "Proposed Action",
                decision.get(
                    "Action",
                    "HOLD",
                ),
            ),

        "Original Reason":
            decision.get(
                "Reason",
                "",
            ),
    }

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
    # Run the complete AI chain per candidate.
    # --------------------------------------------------------

    for base_row in population:

        ticker = get_ticker(
            base_row
        )

        if not ticker:
            continue

        if ticker == "CASH":
            continue

        # ----------------------------------------------------
        # Explicit production population protection.
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
                ].astype(str)
                .str.strip()
                .str.upper()
                == ticker
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

        # Existing holding: allowed regardless of proposal.
        #
        # Non-owned: only BUY NEW is allowed.
        if (
            not owned
            and
            proposed_action != "BUY NEW"
        ):

            continue

        # ----------------------------------------------------
        # Run complete chain.
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
            )

        except Exception as exc:

            # ------------------------------------------------
            # A pipeline error can never create a transaction.
            # ------------------------------------------------

            result = dict(
                base_row
            )

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
        "Quality Score",
        "Growth Score",
        "Signal",
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