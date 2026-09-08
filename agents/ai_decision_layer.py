
"""
AI Decision Layer

Purpose
-------
Apply governed portfolio-level decision logic to the evidence produced
by the AI Decision Context and AI Decision Scoring layers.

Architecture
------------

    Existing analytical engines
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
    Portfolio decision / capital allocation


This module is the GOVERNANCE layer.

It does NOT:

    - recalculate investment scores
    - replace existing analytical engines
    - allocate capital
    - execute trades
    - invent missing evidence
    - automatically favour BUY MORE over BUY NEW

It DOES:

    - assess proposed rules-based actions
    - apply portfolio-aware governance
    - preserve authoritative ownership information
    - require stronger evidence for BUY / REDUCE / SELL
    - preserve HOLD as the default
    - prevent inappropriate concentration
    - distinguish BUY NEW from BUY MORE
    - preserve the underlying evidence assessment
    - expose simple production/test interfaces

Important architecture
----------------------
The structured AI Decision Context is authoritative for:

    candidate["rules_based_decision"]["action"]

and:

    candidate["ownership"]["owned"]

The AI scoring layer assesses the evidence supporting the proposed
action. It must not silently redefine the original rules-based
proposal.

Primary interface
-----------------

    generate_ai_decision(
        portfolio=...,
        candidate=...,
    )

Complete-context interface
--------------------------

    generate_ai_decisions(
        context
    )
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from agents.ai_decision_scoring import score_ai_decision


# ============================================================
# Constants
# ============================================================

VALID_ASSET_TYPES = {
    "STOCK",
    "ETF",
}

VALID_ACTIONS = {
    "BUY NEW",
    "BUY MORE",
    "HOLD",
    "REDUCE",
    "SELL",
    "REVIEW",
    "REDUCE 25%",
    "REDUCE 50%",
    "REDUCE 75%",
    "REDUCE 100%",
}

BUY_ACTIONS = {
    "BUY NEW",
    "BUY MORE",
}

REDUCTION_ACTIONS = {
    "REDUCE",
    "REDUCE 25%",
    "REDUCE 50%",
    "REDUCE 75%",
    "REDUCE 100%",
}


# ============================================================
# Generic helpers
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
            (list, tuple, dict, set),
        ):
            return default

        if isinstance(
            value,
            pd.Series,
        ):
            if value.empty:
                return default

            value = value.iloc[0]

        if isinstance(
            value,
            pd.DataFrame,
        ):
            if value.empty:
                return default

            value = value.iloc[0, 0]

        if pd.isna(value):
            return default

        return float(value)

    except (
        TypeError,
        ValueError,
    ):
        return default


def normalise_text(
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
        result = str(value).strip()
    except Exception:
        return default

    return result if result else default


def normalise_action(
    value: Any,
) -> str:
    """Convert an action to the canonical action vocabulary."""

    return normalise_text(
        value,
        "HOLD",
    ).upper()


def clean_ticker(
    value: Any,
) -> str:
    """Normalise a ticker symbol."""

    if value is None:
        return ""

    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass

    return str(value).strip().upper()


def get_value(
    source: Any,
    *names: str,
    default: Any = None,
) -> Any:
    """
    Retrieve the first available value from a dictionary, Series,
    or ordinary object.
    """

    if source is None:
        return default

    for name in names:
        try:
            if isinstance(
                source,
                dict,
            ):
                if name in source:
                    value = source[name]
                else:
                    continue

            elif isinstance(
                source,
                pd.Series,
            ):
                if name in source.index:
                    value = source[name]
                else:
                    continue

            else:
                if hasattr(
                    source,
                    name,
                ):
                    value = getattr(
                        source,
                        name,
                    )
                else:
                    continue

            if value is None:
                continue

            try:
                if pd.isna(value):
                    continue
            except Exception:
                pass

            return value

        except Exception:
            continue

    return default


def clean_value(
    value: Any,
) -> Any:
    """Convert values into ordinary serialisable Python values."""

    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except Exception:
        pass

    if isinstance(
        value,
        (str, int, float, bool),
    ):
        return value

    if isinstance(
        value,
        (list, tuple),
    ):
        return [
            clean_value(item)
            for item in value
        ]

    if isinstance(
        value,
        dict,
    ):
        return {
            str(key): clean_value(item)
            for key, item in value.items()
        }

    if isinstance(
        value,
        pd.Series,
    ):
        return {
            str(key): clean_value(item)
            for key, item in value.to_dict().items()
        }

    return str(value)


def clean_dict(
    value: Any,
) -> dict:
    """Return a clean ordinary dictionary."""

    if isinstance(
        value,
        dict,
    ):
        return {
            str(key): clean_value(item)
            for key, item in value.items()
        }

    if isinstance(
        value,
        pd.Series,
    ):
        return {
            str(key): clean_value(item)
            for key, item in value.to_dict().items()
        }

    return {}


# ============================================================
# Portfolio extraction
# ============================================================

def _portfolio_value(
    portfolio: Any,
    *names: str,
    default: Any = None,
) -> Any:
    """Retrieve a portfolio-level value."""

    if portfolio is None:
        return default

    value = get_value(
        portfolio,
        *names,
        default=None,
    )

    if value is not None:
        return value

    nested = get_value(
        portfolio,
        "portfolio",
        default=None,
    )

    if isinstance(
        nested,
        dict,
    ):
        value = get_value(
            nested,
            *names,
            default=None,
        )

        if value is not None:
            return value

    return default


def _portfolio_allocation(
    portfolio: Any,
    candidate: Any,
) -> float:
    """
    Determine the candidate's portfolio allocation percentage.

    Allocation is deliberately resolved from the most authoritative
    source available.

    Priority:

        1. Structured candidate ownership
        2. Candidate-level allocation
        3. Portfolio holdings
        4. Zero fallback
    """

    ticker = clean_ticker(
        get_value(
            candidate,
            "Ticker",
            "ticker",
            "Symbol",
            "symbol",
            default="",
        )
    )

    # --------------------------------------------------------
    # Structured ownership context
    # --------------------------------------------------------

    if isinstance(
        candidate,
        dict,
    ):
        ownership = candidate.get(
            "ownership",
            {},
        )

        if isinstance(
            ownership,
            dict,
        ):
            if "allocation_pct" in ownership:

                allocation = safe_float(
                    ownership.get(
                        "allocation_pct",
                        0,
                    )
                )

                print(
                    f"ALLOCATION TRACE: {ticker} | "
                    f"SOURCE=structured ownership | "
                    f"allocation_pct={allocation}"
                )

                return allocation

    # --------------------------------------------------------
    # Candidate-level allocation
    # --------------------------------------------------------

    candidate_value = get_value(
        candidate,
        "Allocation %",
        "Portfolio Allocation %",
        "allocation_pct",
        "allocation_percent",
        "allocation",
        "Position %",
        "Position Weight %",
        default=None,
    )

    if candidate_value is not None:

        allocation = safe_float(
            candidate_value
        )

        print(
            f"ALLOCATION TRACE: {ticker} | "
            f"SOURCE=candidate | "
            f"raw={candidate_value!r} | "
            f"allocation={allocation}"
        )

        return allocation

    # --------------------------------------------------------
    # Portfolio holdings
    # --------------------------------------------------------

    holdings = get_value(
        portfolio,
        "holdings",
        default=None,
    )

    if isinstance(
        holdings,
        list,
    ):
        for holding in holdings:

            holding_ticker = clean_ticker(
                get_value(
                    holding,
                    "Ticker",
                    "ticker",
                    "Symbol",
                    "symbol",
                    default="",
                )
            )

            if holding_ticker == ticker:

                allocation = safe_float(
                    get_value(
                        holding,
                        "Allocation %",
                        "Portfolio Allocation %",
                        "allocation_pct",
                        "allocation_percent",
                        "Allocation",
                        default=0,
                    )
                )

                print(
                    f"ALLOCATION TRACE: {ticker} | "
                    f"SOURCE=portfolio holdings list | "
                    f"allocation={allocation}"
                )

                return allocation

    if isinstance(
        holdings,
        dict,
    ):
        holding = holdings.get(
            ticker,
            {},
        )

        if isinstance(
            holding,
            dict,
        ):

            allocation = safe_float(
                get_value(
                    holding,
                    "Allocation %",
                    "Portfolio Allocation %",
                    "allocation_pct",
                    "allocation_percent",
                    "Allocation",
                    default=0,
                )
            )

            print(
                f"ALLOCATION TRACE: {ticker} | "
                f"SOURCE=portfolio holdings dict | "
                f"allocation={allocation}"
            )

            return allocation

    print(
        f"ALLOCATION TRACE: {ticker} | "
        f"SOURCE=NONE | allocation=0.0"
    )

    return 0.0


def _existing_holding(
    portfolio: Any,
    candidate: Any,
) -> bool:
    """
    Determine whether the candidate is currently held.

    Structured candidate ownership is authoritative when present.
    """

    # --------------------------------------------------------
    # Structured AI Decision Context
    # --------------------------------------------------------

    if isinstance(
        candidate,
        dict,
    ):
        ownership = candidate.get(
            "ownership",
            {},
        )

        if isinstance(
            ownership,
            dict,
        ) and "owned" in ownership:

            return bool(
                ownership["owned"]
            )

    # --------------------------------------------------------
    # Legacy flattened candidate
    # --------------------------------------------------------

    explicit = get_value(
        candidate,
        "Existing Holding",
        "existing_holding",
        "owned",
        "Owned",
        default=None,
    )

    if explicit is not None:

        if isinstance(
            explicit,
            str,
        ):
            return explicit.strip().lower() in {
                "true",
                "yes",
                "1",
                "owned",
            }

        return bool(explicit)

    quantity = get_value(
        candidate,
        "Quantity",
        "quantity",
        "Shares",
        "shares",
        default=None,
    )

    if quantity is not None:
        return safe_float(
            quantity
        ) > 0

    ticker = clean_ticker(
        get_value(
            candidate,
            "Ticker",
            "ticker",
            "Symbol",
            "symbol",
            default="",
        )
    )

    holdings = get_value(
        portfolio,
        "holdings",
        default=None,
    )

    if isinstance(
        holdings,
        list,
    ):

        for holding in holdings:

            holding_ticker = clean_ticker(
                get_value(
                    holding,
                    "Ticker",
                    "ticker",
                    "Symbol",
                    "symbol",
                    default="",
                )
            )

            if holding_ticker != ticker:
                continue

            quantity = safe_float(
                get_value(
                    holding,
                    "Quantity",
                    "quantity",
                    "Shares",
                    "shares",
                    default=0,
                )
            )

            return quantity > 0

    if isinstance(
        holdings,
        dict,
    ):

        holding = holdings.get(
            ticker
        )

        if isinstance(
            holding,
            dict,
        ):

            quantity = safe_float(
                get_value(
                    holding,
                    "Quantity",
                    "quantity",
                    "Shares",
                    "shares",
                    default=0,
                )
            )

            if quantity != 0:
                return quantity > 0

            owned = get_value(
                holding,
                "owned",
                "Owned",
                default=None,
            )

            if owned is not None:
                return bool(owned)

    return False


# ============================================================
# Candidate normalisation
# ============================================================

def _normalise_candidate(
    candidate: Any,
    portfolio: Any,
) -> dict:
    """
    Convert structured or legacy candidate data into the flattened
    representation expected by the AI Decision Scoring layer.

    The structured AI Decision Context is authoritative for:

        rules_based_decision.action
        ownership.owned
        ownership.quantity
        ownership.market_value
        ownership.allocation_pct
        analysis.*
        recommendation_intelligence.*

    Legacy flattened dictionaries remain supported.

    Allocation is deliberately exposed under BOTH:

        "Allocation %"
        "Portfolio Allocation %"

    This prevents the allocation value being lost at an interface
    boundary between context, scoring and reconciliation.
    """

    # ========================================================
    # Convert input
    # ========================================================

    if isinstance(
        candidate,
        pd.Series,
    ):

        candidate = candidate.to_dict()

    elif not isinstance(
        candidate,
        dict,
    ):

        candidate = {}

    candidate = clean_dict(
        candidate
    )

    # ========================================================
    # Structured sections
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

    rules_based = candidate.get(
        "rules_based_decision",
        {},
    )

    if not isinstance(
        rules_based,
        dict,
    ):
        rules_based = {}

    intelligence = candidate.get(
        "recommendation_intelligence",
        {},
    )

    if not isinstance(
        intelligence,
        dict,
    ):
        intelligence = {}

    # ========================================================
    # Ticker
    # ========================================================

    ticker = clean_ticker(
        candidate.get(
            "ticker",
            candidate.get(
                "Ticker",
                candidate.get(
                    "symbol",
                    candidate.get(
                        "Symbol",
                        "",
                    ),
                ),
            ),
        )
    )

    # ========================================================
    # Asset type
    # ========================================================

    asset_type = normalise_text(
        candidate.get(
            "asset_type",
            candidate.get(
                "Asset Type",
                candidate.get(
                    "type",
                    candidate.get(
                        "Type",
                        "STOCK",
                    ),
                ),
            ),
        ),
        "STOCK",
    ).upper()

    if asset_type == "EQUITY":
        asset_type = "STOCK"

    if asset_type not in VALID_ASSET_TYPES:
        asset_type = "STOCK"

    # ========================================================
    # AUTHORITATIVE RULES-BASED ACTION
    # ========================================================

    if "action" in rules_based:

        proposed_action = normalise_action(
            rules_based["action"]
        )

    else:

        proposed_action = normalise_action(
            get_value(
                candidate,
                "Action",
                "action",
                "Proposed Action",
                "proposed_action",
                "Recommendation",
                "recommendation",
                default="HOLD",
            )
        )

    # ========================================================
    # AUTHORITATIVE OWNERSHIP
    # ========================================================

    if "owned" in ownership:

        existing_holding = bool(
            ownership["owned"]
        )

    else:

        existing_holding = _existing_holding(
            portfolio,
            candidate,
        )

    # ========================================================
    # Quantity
    # ========================================================

    if "quantity" in ownership:

        quantity = safe_float(
            ownership.get(
                "quantity",
                0,
            )
        )

    else:

        quantity = safe_float(
            get_value(
                candidate,
                "Quantity",
                "quantity",
                "Shares",
                "shares",
                default=0,
            )
        )

    # ========================================================
    # Market value
    # ========================================================

    if "market_value" in ownership:

        market_value = safe_float(
            ownership.get(
                "market_value",
                0,
            )
        )

    else:

        market_value = safe_float(
            get_value(
                candidate,
                "Market Value",
                "market_value",
                "Current Value",
                "current_value",
                default=0,
            )
        )

    # ========================================================
    # Allocation
    # ========================================================

    if "allocation_pct" in ownership:

        allocation = safe_float(
            ownership.get(
                "allocation_pct",
                0,
            )
        )

        allocation_source = (
            "structured ownership"
        )

    else:

        allocation = _portfolio_allocation(
            portfolio,
            candidate,
        )

        allocation_source = (
            "portfolio/candidate fallback"
        )

    print(
        f"ALLOCATION TRACE: {ticker} | "
        f"SOURCE={allocation_source} | "
        f"NORMALISED Allocation %={allocation}"
    )

    # ========================================================
    # Analysis
    # ========================================================

    investment_score = safe_float(
        analysis.get(
            "investment_score",
            get_value(
                candidate,
                "Investment Score",
                "investment_score",
                "Score",
                "score",
                default=0,
            ),
        )
    )

    etf_score = safe_float(
        analysis.get(
            "etf_score",
            get_value(
                candidate,
                "ETF Score",
                "etf_score",
                default=0,
            ),
        )
    )

    quality_score = safe_float(
        analysis.get(
            "quality_score",
            get_value(
                candidate,
                "Quality Score",
                "quality_score",
                default=0,
            ),
        )
    )

    growth_score = safe_float(
        analysis.get(
            "growth_score",
            get_value(
                candidate,
                "Growth Score",
                "growth_score",
                default=0,
            ),
        )
    )

    signal = normalise_text(
        analysis.get(
            "signal",
            get_value(
                candidate,
                "Signal",
                "signal",
                "Momentum Signal",
                "momentum_signal",
                default="",
            ),
        )
    )

    # ========================================================
    # Confidence
    # ========================================================

    rules_confidence = rules_based.get(
        "confidence",
        intelligence.get(
            "confidence",
            get_value(
                candidate,
                "Confidence",
                "confidence",
                "Recommendation Confidence",
                "recommendation_confidence",
                default="",
            ),
        ),
    )

    # ========================================================
    # Historical intelligence
    # ========================================================

    historical_observations = safe_float(
        intelligence.get(
            "historical_signal_observations",
            get_value(
                candidate,
                "Historical Signal Observations",
                "historical_signal_observations",
                default=0,
            ),
        )
    )

    historical_win_rate = safe_float(
        intelligence.get(
            "historical_signal_win_rate_pct",
            get_value(
                candidate,
                "Historical Signal Win Rate %",
                "historical_signal_win_rate_pct",
                "historical_win_rate_pct",
                default=0,
            ),
        )
    )

    historical_return = safe_float(
        intelligence.get(
            "historical_signal_average_return_pct",
            get_value(
                candidate,
                "Historical Signal Average Return %",
                "historical_signal_average_return_pct",
                "historical_average_return_pct",
                default=0,
            ),
        )
    )

    historical_reliability = normalise_text(
        intelligence.get(
            "historical_signal_reliability",
            get_value(
                candidate,
                "Historical Signal Reliability",
                "historical_signal_reliability",
                default="INSUFFICIENT DATA",
            ),
        ),
        "INSUFFICIENT DATA",
    )

    learning_adjustment = safe_float(
        intelligence.get(
            "learning_adjustment",
            get_value(
                candidate,
                "Learning Adjustment",
                "learning_adjustment",
                default=0,
            ),
        )
    )

    learning_adjusted_score = intelligence.get(
        "learning_adjusted_score",
        get_value(
            candidate,
            "Learning Adjusted Score",
            "learning_adjusted_score",
            default=None,
        ),
    )

    if learning_adjusted_score is not None:

        learning_adjusted_score = safe_float(
            learning_adjusted_score
        )

    score_bucket = intelligence.get(
        "score_bucket",
        get_value(
            candidate,
            "Score Bucket",
            "score_bucket",
            default=None,
        ),
    )

    score_bucket_observations = safe_float(
        intelligence.get(
            "score_bucket_observations",
            get_value(
                candidate,
                "Score Bucket Observations",
                "score_bucket_observations",
                default=0,
            ),
        )
    )

    score_bucket_win_rate = safe_float(
        intelligence.get(
            "score_bucket_win_rate_pct",
            get_value(
                candidate,
                "Score Bucket Win Rate %",
                "score_bucket_win_rate_pct",
                default=0,
            ),
        )
    )

    score_bucket_return = safe_float(
        intelligence.get(
            "score_bucket_average_return_pct",
            get_value(
                candidate,
                "Score Bucket Average Return %",
                "score_bucket_average_return_pct",
                default=0,
            ),
        )
    )

    # ========================================================
    # Portfolio evidence
    # ========================================================

    largest_position_pct = safe_float(
        _portfolio_value(
            portfolio,
            "Largest Position %",
            "largest_position_pct",
            default=0,
        )
    )

    largest_position_ticker = clean_ticker(
        _portfolio_value(
            portfolio,
            "Largest Position Ticker",
            "largest_position_ticker",
            default="",
        )
    )

    risk_score = safe_float(
        get_value(
            candidate,
            "Risk Score",
            "risk_score",
            default=_portfolio_value(
                portfolio,
                "Risk Score",
                "risk_score",
                default=0,
            ),
        )
    )

    semantic_evidence = candidate.get(
        "semantic_evidence",
        {},
    )

    if not isinstance(
        semantic_evidence,
        dict,
    ):
        semantic_evidence = {}

    # ========================================================
    # Flattened scoring context
    # ========================================================

    result = {
        "Ticker":
            ticker,

        "Asset Type":
            asset_type,

        "Action":
            proposed_action,

        "semantic_evidence":
            semantic_evidence,

        "Signal":
            signal,

        "Investment Score":
            investment_score,

        "ETF Score":
            etf_score,

        "Quality Score":
            quality_score,

        "Growth Score":
            growth_score,

        "Confidence":
            rules_confidence,

        "Existing Holding":
            existing_holding,

        "Quantity":
            quantity,

        "Market Value":
            market_value,

        # ----------------------------------------------------
        # IMPORTANT:
        # Keep BOTH allocation names.
        # ----------------------------------------------------

        "Allocation %":
            allocation,

        "Portfolio Allocation %":
            allocation,

        "allocation_pct":
            allocation,

        "allocation_percent":
            allocation,

        "Historical Signal Observations":
            int(historical_observations),

        "Historical Signal Win Rate %":
            historical_win_rate,

        "Historical Signal Average Return %":
            historical_return,

        "Historical Signal Reliability":
            historical_reliability,

        "Learning Adjustment":
            learning_adjustment,

        "Learning Adjusted Score":
            learning_adjusted_score,

        "Score Bucket":
            score_bucket,

        "Score Bucket Observations":
            int(score_bucket_observations),

        "Score Bucket Win Rate %":
            score_bucket_win_rate,

        "Score Bucket Average Return %":
            score_bucket_return,

        "Largest Position %":
            largest_position_pct,

        "Largest Position Ticker":
            largest_position_ticker,

        "Risk Score":
            risk_score,
    }

    print(
        f"ALLOCATION TRACE: {ticker} | "
        f"CONTEXT Allocation %={result.get('Allocation %')} | "
        f"CONTEXT Portfolio Allocation %="
        f"{result.get('Portfolio Allocation %')} | "
        f"CONTEXT allocation_percent="
        f"{result.get('allocation_percent')}"
    )

    return result


# ============================================================
# Scoring
# ============================================================

def _score_candidate(
    candidate: dict,
    portfolio: Any,
) -> dict:
    """
    Pass the normalised candidate to the existing AI scoring layer.

    The normalised candidate is authoritative for portfolio context,
    particularly:
        - Quantity
        - Allocation %
        - Portfolio Allocation %
        - Existing Holding
        - Investment Score
        - Signal
        - Proposed Action
        - Semantic Evidence

    The scoring layer calculates evidence and confidence but must not
    overwrite or lose the authoritative portfolio context.
    """

    # ------------------------------------------------------------
    # Normalise the candidate first.
    # ------------------------------------------------------------

    scoring_context = _normalise_candidate(
        candidate,
        portfolio,
    )

    ticker = clean_ticker(
        scoring_context.get(
            "Ticker",
            "",
        )
    )

    # ------------------------------------------------------------
    # Capture authoritative portfolio context BEFORE scoring.
    #
    # These values must survive the scoring-layer boundary even if
    # score_ai_decision() returns a reduced dictionary.
    # ------------------------------------------------------------

    authoritative_allocation = safe_float(
        scoring_context.get(
            "Allocation %",
            scoring_context.get(
                "Portfolio Allocation %",
                scoring_context.get(
                    "allocation_pct",
                    0.0,
                ),
            ),
        ),
        0.0,
    )

    authoritative_quantity = scoring_context.get(
        "Quantity",
        0,
    )

    authoritative_owned = bool(
        scoring_context.get(
            "Existing Holding",
            False,
        )
    )

    authoritative_investment_score = safe_float(
        scoring_context.get(
            "Investment Score",
            0.0,
        ),
        0.0,
    )

    authoritative_signal = normalise_text(
        scoring_context.get(
            "Signal",
            "",
        ),
        "",
    )

    authoritative_action = normalise_action(
        scoring_context.get(
            "Action",
            "HOLD",
        )
    )

    authoritative_asset_type = normalise_text(
        scoring_context.get(
            "Asset Type",
            "STOCK",
        ),
        "STOCK",
    ).upper()

    # ------------------------------------------------------------
    # Capture authoritative semantic evidence BEFORE scoring.
    #
    # Semantic evidence is a governance/consistency signal. It is
    # deliberately kept separate from the numeric evidence score.
    # ------------------------------------------------------------

    authoritative_semantic_evidence = scoring_context.get(
        "semantic_evidence",
        {},
    )

    if not isinstance(
        authoritative_semantic_evidence,
        dict,
    ):
        authoritative_semantic_evidence = {}

    print(
        f"ALLOCATION TRACE: {ticker} | "
        f"BEFORE SCORING | "
        f"Allocation %={authoritative_allocation} | "
        f"Quantity={authoritative_quantity} | "
        f"Owned={authoritative_owned}"
    )

    # ------------------------------------------------------------
    # Run the existing deterministic scoring layer.
    # ------------------------------------------------------------

    try:
        result = score_ai_decision(
            scoring_context
        )

    except Exception as exc:
        print(
            f"AI DECISION TRACE: {ticker} | "
            f"SCORING ERROR={exc}"
        )

        return {
            "Ticker": ticker,
            "Action": authoritative_action,
            "Proposed Action": authoritative_action,
            "Deterministic Action": authoritative_action,
            "Deterministic Confidence": 0.0,
            "Confidence": 0.0,
            "Evidence Score": 0.0,
            "Evidence Strength": "VERY WEAK",
            "Decision Support": "NOT SUPPORTED",

            # Preserve authoritative portfolio context.
            "Quantity": authoritative_quantity,
            "Allocation %": authoritative_allocation,
            "Portfolio Allocation %": authoritative_allocation,
            "allocation_pct": authoritative_allocation,
            "allocation_percent": authoritative_allocation,
            "Existing Holding": authoritative_owned,
            "Investment Score": authoritative_investment_score,
            "Signal": authoritative_signal,
            "Asset Type": authoritative_asset_type,

            # Preserve semantic evidence even when scoring fails.
            "semantic_evidence": authoritative_semantic_evidence,

            "_scoring_error": str(exc),
        }

    if not isinstance(
        result,
        dict,
    ):
        result = {}

    # ------------------------------------------------------------
    # Start with the scoring result so all scoring evidence is
    # preserved.
    # ------------------------------------------------------------

    decision = dict(
        result
    )

    # ------------------------------------------------------------
    # Canonical scoring fields.
    # ------------------------------------------------------------

    proposed_action = normalise_action(
        result.get(
            "Proposed Action",
            result.get(
                "proposed_action",
                result.get(
                    "Action",
                    result.get(
                        "action",
                        authoritative_action,
                    ),
                ),
            ),
        )
    )

    deterministic_action = normalise_action(
        result.get(
            "Deterministic Action",
            result.get(
                "deterministic_action",
                proposed_action,
            ),
        )
    )

    deterministic_confidence = safe_float(
        result.get(
            "Deterministic Confidence",
            result.get(
                "deterministic_confidence",
                result.get(
                    "Confidence",
                    result.get(
                        "confidence",
                        0.0,
                    ),
                ),
            ),
        ),
        0.0,
    )

    evidence_score = safe_float(
        result.get(
            "Evidence Score",
            result.get(
                "evidence_score",
                0.0,
            ),
        ),
        0.0,
    )

    evidence_strength = normalise_text(
        result.get(
            "Evidence Strength",
            result.get(
                "evidence_strength",
                "VERY WEAK",
            ),
        ),
        "VERY WEAK",
    ).upper()

    decision_support = normalise_text(
        result.get(
            "Decision Support",
            result.get(
                "decision_support",
                "NOT SUPPORTED",
            ),
        ),
        "NOT SUPPORTED",
    ).upper()

    # ------------------------------------------------------------
    # Write the canonical reconciler contract.
    #
    # IMPORTANT:
    # Portfolio context below deliberately comes from the
    # pre-scoring authoritative context, NOT from `result`.
    # ------------------------------------------------------------

    decision["Ticker"] = ticker
    decision["Action"] = proposed_action
    decision["Proposed Action"] = proposed_action
    decision["Deterministic Action"] = deterministic_action
    decision["Deterministic Confidence"] = (
        deterministic_confidence
    )
    decision["Confidence"] = (
        deterministic_confidence
    )
    decision["Evidence Score"] = evidence_score
    decision["Evidence Strength"] = (
        evidence_strength
    )
    decision["Decision Support"] = (
        decision_support
    )

    # ------------------------------------------------------------
    # AUTHORITATIVE PORTFOLIO CONTEXT
    #
    # Do not take these values from the scoring result.
    # ------------------------------------------------------------

    decision["Quantity"] = authoritative_quantity
    decision["Allocation %"] = (
        authoritative_allocation
    )
    decision["Portfolio Allocation %"] = (
        authoritative_allocation
    )
    decision["allocation_pct"] = (
        authoritative_allocation
    )
    decision["allocation_percent"] = (
        authoritative_allocation
    )
    decision["Existing Holding"] = (
        authoritative_owned
    )
    decision["Investment Score"] = (
        authoritative_investment_score
    )
    decision["Signal"] = (
        authoritative_signal
    )
    decision["Asset Type"] = (
        authoritative_asset_type
    )

    # ------------------------------------------------------------
    # Preserve semantic evidence from the authoritative context.
    #
    # Semantic evidence is a governance/consistency signal. It is
    # deliberately preserved separately from the numeric evidence
    # score and is NOT folded into the evidence weighting.
    # ------------------------------------------------------------

    decision["semantic_evidence"] = (
        authoritative_semantic_evidence
    )

    # ------------------------------------------------------------
    # Preserve historical intelligence from the normalised
    # context rather than allowing the scoring boundary to lose it.
    # ------------------------------------------------------------

    for field in (
        "Historical Signal Reliability",
        "Historical Signal Observations",
        "Historical Signal Win Rate %",
        "Historical Signal Average Return %",
        "Learning Adjustment",
        "Learning Adjusted Score",
        "Score Bucket",
        "Score Bucket Observations",
        "Score Bucket Win Rate %",
        "Score Bucket Average Return %",
        "Largest Position %",
        "Largest Position Ticker",
        "Risk Score",
    ):
        if field in scoring_context:
            decision[field] = scoring_context[field]

    # ------------------------------------------------------------
    # Preserve scoring errors if the scoring layer returned one.
    # ------------------------------------------------------------

    if "_scoring_error" in result:
        decision["_scoring_error"] = result[
            "_scoring_error"
        ]

    # ------------------------------------------------------------
    # Final trace.
    # ------------------------------------------------------------

    print(
        f"ALLOCATION TRACE: {ticker} | "
        f"AFTER SCORING | "
        f"Allocation %={decision['Allocation %']} | "
        f"Portfolio Allocation %="
        f"{decision['Portfolio Allocation %']} | "
        f"Quantity={decision['Quantity']} | "
        f"Owned={decision['Existing Holding']} | "
        f"Investment Score="
        f"{decision['Investment Score']} | "
        f"Action={decision['Action']}"
    )

    return decision
# ============================================================
# Governance
# ============================================================

def _govern_buy(
    proposed_action: str,
    evidence_score: float,
    decision_support: str,
    existing_holding: bool,
    allocation: float,
) -> tuple[str, list[str]]:
    """
    Govern BUY NEW and BUY MORE.

    BUY MORE does not automatically outrank BUY NEW.
    """

    if decision_support == "NOT SUPPORTED":

        return (
            "HOLD",
            [
                "Buy evidence is insufficient",
            ],
        )

    if evidence_score < 60:

        return (
            "HOLD",
            [
                "Evidence score is below the minimum buy threshold",
            ],
        )

    if (
        proposed_action == "BUY MORE"
        and existing_holding
        and allocation >= 40
    ):

        return (
            "HOLD",
            [
                "Existing position is highly concentrated",
            ],
        )

    if (
        proposed_action == "BUY MORE"
        and existing_holding
        and allocation >= 25
        and evidence_score < 75
    ):

        return (
            "HOLD",
            [
                "Existing position is already large and evidence "
                "is not strong enough to justify increasing it",
            ],
        )

    if decision_support == "CONDITIONAL":

        return (
            
            proposed_action,
            [
                "Buy evidence is conditional and contains caveats, "
                "but deterministic governance requirements for the "
                "proposed action have been satisfied",
            ],
        )

    return (
        proposed_action,
        [
            "Evidence sufficiently supports the proposed buy action",
        ],
    )


def _govern_reduction(
    evidence_score: float,
    evidence_strength: str,
    decision_support: str,
    existing_holding: bool,
) -> tuple[str, list[str]]:
    """Govern REDUCE actions."""

    if not existing_holding:

        return (
            "HOLD",
            [
                "Cannot reduce an asset that is not currently held",
            ],
        )

    if decision_support == "NOT SUPPORTED":

        return (
            "HOLD",
            [
                "Reduction evidence is insufficient",
            ],
        )

    if evidence_score < 65:

        return (
            "HOLD",
            [
                "Reduction requires stronger evidence than HOLD",
            ],
        )

    if evidence_strength not in {
        "STRONG",
        "VERY STRONG",
    }:

        return (
            "HOLD",
            [
                "Reduction requires strong or very strong evidence",
            ],
        )

    return (
        "REDUCE",
        [
            "Multiple evidence sources support reducing the existing position",
        ],
    )


def _govern_sell(
    evidence_score: float,
    evidence_strength: str,
    decision_support: str,
    existing_holding: bool,
) -> tuple[str, list[str]]:
    """Govern SELL."""

    if not existing_holding:

        return (
            "HOLD",
            [
                "Cannot sell an asset that is not currently held",
            ],
        )

    if decision_support == "NOT SUPPORTED":

        return (
            "HOLD",
            [
                "Sell evidence is insufficient",
            ],
        )

    if evidence_score < 75:

        return (
            "HOLD",
            [
                "SELL requires very strong evidence",
            ],
        )

    if evidence_strength != "VERY STRONG":

        return (
            "HOLD",
            [
                "SELL requires very strong evidence",
            ],
        )

    return (
        "SELL",
        [
            "Very strong evidence supports exiting the position",
        ],
    )


# ============================================================
# Single decision
# ============================================================

def generate_ai_decision(
    portfolio: Any = None,
    candidate: Any = None,
    context: dict | None = None,
    candidate_context: dict | None = None,
    portfolio_context: dict | None = None,
    **kwargs: Any,
) -> dict:
    """
    Generate one governed AI portfolio decision.

    Supports both:

        generate_ai_decision(
            portfolio=portfolio,
            candidate=candidate,
        )

    and:

        generate_ai_decision(
            candidate_context=candidate,
            portfolio_context=context,
        )
    """

    # ========================================================
    # Resolve complete context
    # ========================================================

    if context is None:

        context = kwargs.get(
            "ai_context"
        )

    if context is not None:

        if not isinstance(
            context,
            dict,
        ):

            return _invalid_decision(
                reason="Invalid AI decision context"
            )

        candidates = context.get(
            "candidates",
            [],
        )

        if candidate is None:

            if candidate_context is not None:
                candidate = candidate_context

            elif candidates:
                candidate = candidates[0]

        if portfolio is None:
            portfolio = context

        if portfolio_context is not None:
            portfolio = portfolio_context

    # ========================================================
    # Resolve aliases
    # ========================================================

    if candidate is None:
        candidate = kwargs.get("decision")

    if candidate is None:
        candidate = kwargs.get("recommendation")

    if candidate is None:
        candidate = candidate_context

    if portfolio is None:
        portfolio = portfolio_context

    if portfolio is None:
        portfolio = kwargs.get("portfolio_data")

    if candidate is None:
        candidate = {}

    # ========================================================
    # Normalise
    # ========================================================

    normalised_candidate = _normalise_candidate(
        candidate,
        portfolio,
    )

    if not normalised_candidate.get(
        "Ticker"
    ):

        return _invalid_decision(
            reason="Candidate has no ticker"
        )

    ticker = normalised_candidate[
        "Ticker"
    ]

    print(
        f"AI DECISION TRACE: {ticker} | "
        f"PROPOSED ACTION="
        f"{normalised_candidate.get('Action')} | "
        f"OWNED="
        f"{normalised_candidate.get('Existing Holding')} | "
        f"ALLOCATION="
        f"{normalised_candidate.get('Allocation %')}"
    )

    # ========================================================
    # Score evidence
    # ========================================================

    evidence = _score_candidate(
        candidate=normalised_candidate,
        portfolio=portfolio,
    )

    scoring_error = evidence.get(
        "_scoring_error"
    )

    if scoring_error:

        return {
            "Ticker":
                ticker,

            "Final Decision":
                "HOLD",

            "Proposed Action":
                normalised_candidate["Action"],

            "Asset Type":
                normalised_candidate["Asset Type"],

            "Existing Holding":
                normalised_candidate["Existing Holding"],

            "Evidence Score":
                0.0,

            "Evidence Strength":
                "VERY WEAK",

            "Decision Support":
                "NOT SUPPORTED",

            "Confidence":
                0.0,

            "Portfolio Allocation %":
                normalised_candidate["Allocation %"],

            "Allocation %":
                normalised_candidate["Allocation %"],

            "Governance Reasons":
                [
                    f"AI decision scoring failed: {scoring_error}",
                ],

            "Reason":
                f"AI decision scoring failed: {scoring_error}",

            "Decision Status":
                "SCORING ERROR",

            "Evidence Assessment":
                evidence,
        }

    # ========================================================
    # Extract scored evidence
    # ========================================================

    proposed_action = normalise_action(
        normalised_candidate.get(
            "Action",
            "HOLD",
        )
    )

    evidence_score = safe_float(
        evidence.get(
            "Evidence Score",
            0,
        )
    )

    evidence_strength = normalise_text(
        evidence.get(
            "Evidence Strength",
            "VERY WEAK",
        ),
        "VERY WEAK",
    ).upper()

    decision_support = normalise_text(
        evidence.get(
            "Decision Support",
            "NOT SUPPORTED",
        ),
        "NOT SUPPORTED",
    ).upper()

    confidence = safe_float(
        evidence.get(
            "Confidence",
            0,
        )
    )

    # --------------------------------------------------------
    # Ownership is authoritative from candidate context.
    # --------------------------------------------------------

    existing_holding = bool(
        normalised_candidate.get(
            "Existing Holding",
            False,
        )
    )

    allocation = safe_float(
        normalised_candidate.get(
            "Allocation %",
            0,
        )
    )

    asset_type = normalise_text(
        normalised_candidate.get(
            "Asset Type",
            "STOCK",
        ),
        "STOCK",
    ).upper()

    # ========================================================
    # Governance
    # ========================================================

    final_decision = "HOLD"

    governance_reasons = []

    # --------------------------------------------------------
    # HOLD
    # --------------------------------------------------------

    if proposed_action == "HOLD":

        final_decision = "HOLD"

        governance_reasons.append(
            "HOLD remains the default portfolio action"
        )

    # --------------------------------------------------------
    # BUY NEW / BUY MORE
    # --------------------------------------------------------

    elif proposed_action in BUY_ACTIONS:

        (
            final_decision,
            reasons,
        ) = _govern_buy(
            proposed_action=proposed_action,
            evidence_score=evidence_score,
            decision_support=decision_support,
            existing_holding=existing_holding,
            allocation=allocation,
        )

        governance_reasons.extend(
            reasons
        )

    # --------------------------------------------------------
    # REDUCE
    # --------------------------------------------------------

    elif proposed_action == "REDUCE":

        (
            final_decision,
            reasons,
        ) = _govern_reduction(
            evidence_score=evidence_score,
            evidence_strength=evidence_strength,
            decision_support=decision_support,
            existing_holding=existing_holding,
        )

        governance_reasons.extend(
            reasons
        )

    # --------------------------------------------------------
    # Percentage reductions
    # --------------------------------------------------------

    elif proposed_action in {
        "REDUCE 25%",
        "REDUCE 50%",
        "REDUCE 75%",
        "REDUCE 100%",
    }:

        reduction_decision, reasons = _govern_reduction(
            evidence_score=evidence_score,
            evidence_strength=evidence_strength,
            decision_support=decision_support,
            existing_holding=existing_holding,
        )

        if reduction_decision == "REDUCE":
            final_decision = proposed_action
        else:
            final_decision = "HOLD"

        governance_reasons.extend(
            reasons
        )

    # --------------------------------------------------------
    # SELL
    # --------------------------------------------------------

    elif proposed_action == "SELL":

        (
            final_decision,
            reasons,
        ) = _govern_sell(
            evidence_score=evidence_score,
            evidence_strength=evidence_strength,
            decision_support=decision_support,
            existing_holding=existing_holding,
        )

        governance_reasons.extend(
            reasons
        )

    # --------------------------------------------------------
    # REVIEW
    # --------------------------------------------------------

    elif proposed_action == "REVIEW":

        final_decision = "HOLD"

        governance_reasons.append(
            "Rules-based engine requested review; REVIEW does not "
            "become a trade without stronger evidence"
        )

    # --------------------------------------------------------
    # Unknown action
    # --------------------------------------------------------

    else:

        final_decision = "HOLD"

        governance_reasons.append(
            "Unknown proposed action converted to HOLD"
        )

    # ========================================================
    # Final confidence
    # ========================================================

    if final_decision == proposed_action:

        final_confidence = confidence

    else:

        final_confidence = min(
            confidence,
            85.0,
        )

    # ========================================================
    # Final result
    # ========================================================

    final_result = {
        "Ticker":
            ticker,

        "Final Decision":
            final_decision,

        "Proposed Action":
            proposed_action,

        "Asset Type":
            asset_type,

        "Existing Holding":
            existing_holding,

        "Evidence Score":
            round(
                evidence_score,
                2,
            ),

        "Evidence Strength":
            evidence_strength,

        "Decision Support":
            decision_support,

        "Confidence":
            round(
                final_confidence,
                2,
            ),

        "Portfolio Allocation %":
            round(
                allocation,
                2,
            ),

        # ----------------------------------------------------
        # Preserve both allocation names at final boundary.
        # ----------------------------------------------------

        "Allocation %":
            round(
                allocation,
                2,
            ),

        "Governance Reasons":
            governance_reasons,

        "Reason":
            "; ".join(
                governance_reasons
            ),

        "Decision Status":
            "FINAL AI DECISION",

        "Evidence Assessment":
            evidence,
    }

    print(
        f"AI DECISION TRACE: {ticker} | "
        f"FINAL={final_decision} | "
        f"PROPOSED={proposed_action} | "
        f"ALLOCATION={final_result.get('Allocation %')} | "
        f"OWNED={existing_holding} | "
        f"EVIDENCE={evidence_score} | "
        f"CONFIDENCE={final_confidence}"
    )

    return final_result


# ============================================================
# Complete portfolio decision
# ============================================================

def generate_ai_decisions(
    context: dict,
) -> list[dict]:
    """
    Generate final AI decisions for every candidate in a complete
    AI Decision Context.
    """

    if not isinstance(
        context,
        dict,
    ):

        return []

    candidates = context.get(
        "candidates",
        [],
    )

    if not isinstance(
        candidates,
        list,
    ):

        return []

    results = []

    for candidate in candidates:

        results.append(
            generate_ai_decision(
                portfolio=context,
                candidate=candidate,
            )
        )

    return results


# ============================================================
# Single candidate from complete context
# ============================================================

def generate_ai_decision_from_context(
    context: dict,
    ticker: str,
) -> dict:
    """
    Generate one decision from a complete AI Decision Context.
    """

    if not isinstance(
        context,
        dict,
    ):

        return _invalid_decision(
            reason="Invalid AI decision context"
        )

    target = clean_ticker(
        ticker
    )

    for candidate in context.get(
        "candidates",
        [],
    ):

        candidate_ticker = clean_ticker(
            get_value(
                candidate,
                "Ticker",
                "ticker",
                "Symbol",
                "symbol",
                default="",
            )
        )

        if candidate_ticker == target:

            return generate_ai_decision(
                portfolio=context,
                candidate=candidate,
            )

    return {
        "Ticker":
            target,

        "Final Decision":
            "HOLD",

        "Proposed Action":
            "HOLD",

        "Decision Support":
            "NOT SUPPORTED",

        "Evidence Score":
            0.0,

        "Confidence":
            0.0,

        "Decision Status":
            "TICKER NOT FOUND",

        "Reason":
            f"No AI decision candidate found for {target}",
    }


# ============================================================
# Invalid decision helper
# ============================================================

def _invalid_decision(
    reason: str,
) -> dict:
    """Return a safe HOLD decision for invalid input."""

    return {
        "Ticker": "",

        "Final Decision":
            "HOLD",

        "Proposed Action":
            "HOLD",

        "Decision Support":
            "NOT SUPPORTED",

        "Evidence Score":
            0.0,

        "Evidence Strength":
            "VERY WEAK",

        "Confidence":
            0.0,

        "Decision Status":
            "INVALID INPUT",

        "Reason":
            reason,

        "Governance Reasons":
            [
                reason,
            ],
    }


# ============================================================
# Module test
# ============================================================

if __name__ == "__main__":

    print(
        "AI Decision Layer"
    )

    print(
        "Module loaded successfully."
    )

    print(
        "Primary interface:"
    )

    print(
        "    generate_ai_decision("
    )

    print(
        "        portfolio=portfolio,"
    )

    print(
        "        candidate=candidate,"
    )

    print(
        "    )"
    )

    print(
        "Complete portfolio interface:"
    )

    print(
        "    generate_ai_decisions(context)"
    )
