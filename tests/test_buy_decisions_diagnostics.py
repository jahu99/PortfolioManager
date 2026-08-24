
"""
BUY / BUY MORE Decision Diagnostic
==================================

Purpose
-------
Run the existing production pipeline and inspect BUY NEW and BUY MORE
candidates after the complete governed decision chain.

This is a diagnostic script only.

It does NOT:
    - change production thresholds
    - change scoring weights
    - alter recommendation learning
    - alter portfolio holdings
    - allocate capital
    - execute trades
    - modify production modules

The diagnostic temporarily intercepts the production call to:

    generate_final_portfolio_decisions()

so that the exact inputs already constructed by main.py can be captured.

The diagnostic then explains, for every BUY NEW / BUY MORE candidate:

    1. Proposed action
    2. Final action
    3. Evidence score
    4. Deterministic confidence
    5. Investment score
    6. Signal
    7. Current allocation
    8. Historical learning evidence
    9. LLM review
    10. LLM confidence
    11. Reconciliation status
    12. Governance reasons
    13. Individual BUY MORE qualification gates
    14. Individual BUY NEW qualification gates
    15. Which gates failed
    16. Which gates appear to be the principal reason for downgrade

IMPORTANT
---------
The diagnostic does NOT replace production governance logic.

Where production fields already expose the actual governance result,
those fields are treated as authoritative.

Diagnostic gate checks are used only to explain the production result.

BUY MORE thresholds are read directly from the production reconciler.
They are NOT duplicated as hard-coded diagnostic values.

The actual existing_holding value supplied to the production reconciler
is captured during the diagnostic run so that the BUY MORE holding gate
can be reported accurately.
"""

from __future__ import annotations

import inspect
import sys
import traceback
from pathlib import Path
from typing import Any

import pandas as pd


# ============================================================================
# PROJECT PATH
# ============================================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================================
# PRODUCTION IMPORTS
# ============================================================================

import main as production_main

from analysis.final_portfolio_decision import (
    generate_final_portfolio_decisions as real_final_decisions,
)

import agents.ai_decision_reconciler as reconciler


# ============================================================================
# OPTIONAL PRODUCTION CONSTANTS
# ============================================================================

try:
    import analysis.final_portfolio_decision as final_decision_module
except Exception:
    final_decision_module = None


def production_constant(
    name: str,
    default: Any = None,
) -> Any:
    """
    Read a production constant without modifying it.
    """

    if final_decision_module is None:
        return default

    return getattr(
        final_decision_module,
        name,
        default,
    )


MIN_DETERMINISTIC_CONFIDENCE = production_constant(
    "MIN_DETERMINISTIC_CONFIDENCE"
)

STRONG_DETERMINISTIC_CONFIDENCE = production_constant(
    "STRONG_DETERMINISTIC_CONFIDENCE"
)

MIN_EVIDENCE_SCORE = production_constant(
    "MIN_EVIDENCE_SCORE"
)

STRONG_EVIDENCE_SCORE = production_constant(
    "STRONG_EVIDENCE_SCORE"
)

SELL_EVIDENCE_SCORE = production_constant(
    "SELL_EVIDENCE_SCORE"
)

MIN_LLM_CONFIDENCE = production_constant(
    "MIN_LLM_CONFIDENCE"
)

STRONG_LLM_CONFIDENCE = production_constant(
    "STRONG_LLM_CONFIDENCE"
)

BUY_NEW_IMMATURE_MIN_EVIDENCE = production_constant(
    "BUY_NEW_IMMATURE_MIN_EVIDENCE"
)

BUY_NEW_IMMATURE_MIN_INVESTMENT_SCORE = production_constant(
    "BUY_NEW_IMMATURE_MIN_INVESTMENT_SCORE"
)

BUY_NEW_IMMATURE_MIN_SCORE_BUCKET_WIN_RATE = production_constant(
    "BUY_NEW_IMMATURE_MIN_SCORE_BUCKET_WIN_RATE"
)

BUY_NEW_IMMATURE_MIN_SCORE_BUCKET_OBSERVATIONS = production_constant(
    "BUY_NEW_IMMATURE_MIN_SCORE_BUCKET_OBSERVATIONS"
)

BUY_NEW_STARTER_ALLOCATION_CAP = production_constant(
    "BUY_NEW_STARTER_ALLOCATION_CAP"
)

REDUCE_CHALLENGE_MIN_EVIDENCE = production_constant(
    "REDUCE_CHALLENGE_MIN_EVIDENCE"
)

REDUCE_CHALLENGE_MIN_CONFIDENCE = production_constant(
    "REDUCE_CHALLENGE_MIN_CONFIDENCE"
)

REDUCE_CHALLENGE_MAX_INVESTMENT_SCORE = production_constant(
    "REDUCE_CHALLENGE_MAX_INVESTMENT_SCORE"
)


# ============================================================================
# BUY MORE PRODUCTION THRESHOLDS
# ============================================================================
#
# IMPORTANT:
# These are read directly from agents.ai_decision_reconciler.
#
# The diagnostic therefore cannot silently drift away from production
# governance when the production thresholds are changed.
# ============================================================================

BUY_MORE_MIN_EVIDENCE = getattr(
    reconciler,
    "BUY_MORE_MIN_EVIDENCE",
    None,
)

BUY_MORE_MIN_CONFIDENCE = getattr(
    reconciler,
    "BUY_MORE_MIN_CONFIDENCE",
    None,
)

BUY_MORE_MIN_INVESTMENT_SCORE = getattr(
    reconciler,
    "BUY_MORE_MIN_INVESTMENT_SCORE",
    None,
)

BUY_MORE_MAX_ALLOCATION_PERCENT = getattr(
    reconciler,
    "BUY_MORE_MAX_ALLOCATION_PERCENT",
    None,
)

BUY_MORE_MIN_LLM_CONFIDENCE = getattr(
    reconciler,
    "BUY_MORE_MIN_LLM_CONFIDENCE",
    None,
)

BUY_MORE_SUPPORTING_SIGNALS = getattr(
    reconciler,
    "BUY_MORE_SUPPORTING_SIGNALS",
    {
        "BUY",
        "STRONG BUY",
    },
)


# ============================================================================
# GLOBAL CAPTURE STATE
# ============================================================================

captured_inputs: dict[str, Any] = {}

captured_result: Any = None

captured_buy_more_holding_state: dict[str, bool] = {}


# ============================================================================
# GENERIC HELPERS
# ============================================================================

def safe_text(
    value: Any,
    default: str = "",
) -> str:
    """
    Safely convert a value to clean text.
    """

    if value is None:
        return default

    try:
        if pd.isna(value):
            return default
    except Exception:
        pass

    try:
        text = str(value).strip()
    except Exception:
        return default

    return text if text else default


def safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    """
    Safely convert a scalar value to float.

    Arrays, dictionaries, lists and other non-scalar values are ignored.
    """

    try:
        if value is None:
            return default

        if isinstance(
            value,
            (
                list,
                tuple,
                set,
                dict,
            ),
        ):
            return default

        if pd.isna(value):
            return default

        return float(value)

    except (
        TypeError,
        ValueError,
    ):
        return default


def safe_bool(
    value: Any,
    default: bool = False,
) -> bool:
    """
    Safely convert common values to bool.
    """

    if isinstance(value, bool):
        return value

    text = safe_text(
        value
    ).upper()

    if text in {
        "TRUE",
        "YES",
        "Y",
        "1",
        "HELD",
        "OWNED",
    }:
        return True

    if text in {
        "FALSE",
        "NO",
        "N",
        "0",
        "NOT HELD",
        "NOT OWNED",
    }:
        return False

    return default


def get_first(
    row: Any,
    *names: str,
    default: Any = None,
) -> Any:
    """
    Return the first usable value from a pandas Series or mapping.
    """

    if row is None:
        return default

    for name in names:

        try:
            if isinstance(row, pd.Series):

                if name not in row.index:
                    continue

                value = row[name]

            elif isinstance(row, dict):

                if name not in row:
                    continue

                value = row[name]

            else:
                continue

        except Exception:
            continue

        if value is None:
            continue

        try:
            if pd.isna(value):
                continue
        except Exception:
            pass

        return value

    return default


def normalise_ticker(
    value: Any,
) -> str:
    """
    Normalise a ticker symbol for comparison.
    """

    return safe_text(
        value
    ).upper()


def normalise_records(
    value: Any,
) -> list[dict]:
    """
    Convert common DataFrame/list/dict structures into records.
    """

    if value is None:
        return []

    if isinstance(
        value,
        pd.DataFrame,
    ):
        return value.to_dict(
            "records"
        )

    if isinstance(
        value,
        pd.Series,
    ):
        return [
            value.to_dict()
        ]

    if isinstance(
        value,
        dict,
    ):
        return [
            value
        ]

    if isinstance(
        value,
        list,
    ):

        records = []

        for item in value:

            if isinstance(
                item,
                dict,
            ):
                records.append(
                    item
                )

            elif isinstance(
                item,
                pd.Series,
            ):
                records.append(
                    item.to_dict()
                )

        return records

    return []


def dataframe_or_empty(
    value: Any,
) -> pd.DataFrame:
    """
    Convert an arbitrary result to a DataFrame safely.
    """

    if isinstance(
        value,
        pd.DataFrame,
    ):
        return value.copy()

    if value is None:
        return pd.DataFrame()

    try:
        return pd.DataFrame(
            value
        )
    except Exception:
        return pd.DataFrame()


# ============================================================================
# RECOMMENDATION INTELLIGENCE LOOKUP
# ============================================================================

def build_intelligence_lookup(
    recommendation_intelligence: Any,
) -> dict[str, dict]:
    """
    Build a ticker lookup from Recommendation Intelligence.
    """

    records = normalise_records(
        recommendation_intelligence
    )

    lookup: dict[str, dict] = {}

    for record in records:

        ticker = normalise_ticker(
            get_first(
                record,
                "Ticker",
                "ticker",
                "Symbol",
                default="",
            )
        )

        if ticker:
            lookup[ticker] = record

    return lookup


# ============================================================================
# PRODUCTION RECONCILER INTERCEPTOR
# ============================================================================
#
# This is the important addition.
#
# The production reconciler receives existing_holding as an explicit
# argument. The diagnostic captures that exact value instead of attempting
# to reconstruct it later from the final DataFrame.
#
# We wrap the production function itself during the diagnostic run.
# ============================================================================

_original_reconcile = (
    reconciler.reconcile_decision
    if hasattr(
        reconciler,
        "reconcile_decision",
    )
    else None
)


def intercepted_reconcile_decision(
    *args: Any,
    **kwargs: Any,
) -> Any:
    """
    Capture the actual existing_holding value supplied to production
    reconciliation, then delegate immediately to the real reconciler.

    This function deliberately does not change any production input.
    """

    result = _original_reconcile(
        *args,
        **kwargs,
    )

    decision = (
        kwargs.get(
            "decision"
        )
        if "decision" in kwargs
        else (
            args[0]
            if len(args) > 0
            else {}
        )
    )

    existing_holding = (
        kwargs.get(
            "existing_holding"
        )
        if "existing_holding" in kwargs
        else (
            args[2]
            if len(args) > 2
            else None
        )
    )

    ticker = normalise_ticker(
        get_first(
            decision,
            "Ticker",
            "ticker",
            "Symbol",
            default="",
        )
    )

    if ticker:

        captured_buy_more_holding_state[
            ticker
        ] = safe_bool(
            existing_holding
        )

    return result


# ============================================================================
# PRODUCTION FINAL DECISION INTERCEPTOR
# ============================================================================

def intercepted_final_decisions(
    *args: Any,
    **kwargs: Any,
) -> Any:
    """
    Intercept the production final-decision call.

    The wrapper accepts both positional and keyword invocation so that
    the diagnostic remains compatible with the current main.py call style.

    The exact production inputs are captured before immediately delegating
    to the real production implementation.
    """

    global captured_result

    captured_inputs.clear()

    parameter_order = [
        "portfolio_summary",
        "portfolio_decisions",
        "portfolio_ai_review",
        "portfolio_manager_review",
        "portfolio_health",
        "capital_allocation",
        "recommendation_intelligence",
    ]

    call_kwargs = dict(
        kwargs
    )

    for index, value in enumerate(
        args
    ):

        if index >= len(
            parameter_order
        ):
            break

        call_kwargs[
            parameter_order[index]
        ] = value

    captured_inputs.update(
        call_kwargs
    )

    captured_result = real_final_decisions(
        **call_kwargs
    )

    return captured_result


# ============================================================================
# VALUE EXTRACTION
# ============================================================================

def extract_decision_fields(
    row: Any,
) -> dict[str, Any]:
    """
    Extract the principal fields needed for governance diagnostics.
    """

    ticker = normalise_ticker(
        get_first(
            row,
            "Ticker",
            "ticker",
            default="",
        )
    )

    production_holding = (
        captured_buy_more_holding_state.get(
            ticker
        )
    )

    dataframe_holding = safe_bool(
        get_first(
            row,
            "Held?",
            "Existing Holding",
            "Existing_Holding",
            default=False,
        )
    )

    return {
        "ticker": ticker,

        "proposal": safe_text(
            get_first(
                row,
                "Proposed Action",
                "Proposed_Action",
                "Action",
                default="",
            )
        ),

        "final_decision": safe_text(
            get_first(
                row,
                "Final Decision",
                "Final Action",
                "Reconciled Decision",
                "final_decision",
                default="",
            )
        ),

        "held": (
            production_holding
            if production_holding is not None
            else dataframe_holding
        ),

        "production_existing_holding": (
            production_holding
        ),

        "allocation": safe_float(
            get_first(
                row,
                "Current Allocation %",
                "Portfolio Allocation %",
                "Allocation %",
                "allocation_pct",
                "allocation_percent",
                default=0,
            )
        ),

        "investment_score": safe_float(
            get_first(
                row,
                "Investment Score",
                "investment_score",
                default=0,
            )
        ),

        "learning_adjusted_score": safe_float(
            get_first(
                row,
                "Learning Adjusted Score",
                "learning_adjusted_score",
                default=0,
            )
        ),

        "signal": safe_text(
            get_first(
                row,
                "Signal",
                "Momentum Signal",
                "signal",
                default="",
            )
        ).upper(),

        "evidence_score": safe_float(
            get_first(
                row,
                "Evidence Score",
                "evidence_score",
                default=0,
            )
        ),

        "evidence_strength": safe_text(
            get_first(
                row,
                "Evidence Strength",
                "evidence_strength",
                default="",
            )
        ).upper(),

        "evidence_support": safe_text(
            get_first(
                row,
                "Evidence Support",
                "Decision Support",
                "Decision_Support",
                "evidence_support",
                default="",
            )
        ).upper(),

        "confidence": safe_float(
            get_first(
                row,
                "Confidence",
                "Decision Confidence",
                "Deterministic Confidence",
                "confidence",
                default=0,
            )
        ),

        "llm_review": safe_text(
            get_first(
                row,
                "LLM Review",
                "LLM Assessment",
                "LLM Review Decision",
                "llm_review",
                default="",
            )
        ).upper(),

        "llm_confidence": safe_float(
            get_first(
                row,
                "LLM Confidence",
                "llm_confidence",
                default=0,
            )
        ),

        "reconciliation": safe_text(
            get_first(
                row,
                "Reconciliation",
                "Reconciliation Status",
                "reconciliation_status",
                default="",
            )
        ).upper(),

        "decision_status": safe_text(
            get_first(
                row,
                "Decision Status",
                "decision_status",
                default="",
            )
        ).upper(),

        "governance_reasons": safe_text(
            get_first(
                row,
                "Governance Reasons",
                "Governance Reason",
                "governance_reasons",
                default="",
            )
        ),

        "review_triggers": safe_text(
            get_first(
                row,
                "Review Triggers",
                "review_triggers",
                default="",
            )
        ),

        "final_reason": safe_text(
            get_first(
                row,
                "Final Reason",
                "Final Action Reason",
                "Reconciliation Reason",
                "Reason",
                default="",
            )
        ),

        "decision_changed": safe_text(
            get_first(
                row,
                "Decision Changed",
                "decision_changed",
                default="",
            )
        ),

        "capital_allocation": safe_text(
            get_first(
                row,
                "Capital Allocation",
                "capital_allocation",
                default="",
            )
        ),
    }


# ============================================================================
# GOVERNANCE TEXT EXTRACTION
# ============================================================================

def combined_governance_text(
    fields: dict[str, Any],
) -> str:
    """
    Combine all available governance/review text.
    """

    parts = [
        fields.get(
            "governance_reasons",
            "",
        ),
        fields.get(
            "review_triggers",
            "",
        ),
        fields.get(
            "final_reason",
            "",
        ),
    ]

    return " ".join(
        safe_text(
            part
        )
        for part in parts
    ).upper()


def has_material_contradiction(
    fields: dict[str, Any],
) -> bool:
    """
    Detect explicit material contradiction language.

    This is diagnostic only.

    Missing data by itself is NOT treated as contradiction.
    """

    text = combined_governance_text(
        fields
    )

    contradiction_terms = {
        "CONTRADICTORY",
        "CONTRADICTION",
        "CONFLICTING EVIDENCE",
        "MATERIAL NEGATIVE",
        "MATERIAL RISK",
        "UNSUPPORTED",
        "NOT SUPPORTED",
    }

    return any(
        term in text
        for term in contradiction_terms
    )


# ============================================================================
# LEARNING EVIDENCE
# ============================================================================

def learning_fields(
    ticker: str,
    intelligence_lookup: dict[str, dict],
) -> dict[str, Any]:
    """
    Extract Recommendation Intelligence fields for one ticker.
    """

    intelligence = intelligence_lookup.get(
        ticker,
        {},
    )

    return {
        "learning_observations": safe_float(
            get_first(
                intelligence,
                "Historical Signal Observations",
                "Learning Observations",
                "observations",
                default=0,
            )
        ),

        "learning_reliability": safe_text(
            get_first(
                intelligence,
                "Historical Signal Reliability",
                "Learning Reliability",
                "reliability",
                default="",
            )
        ).upper(),

        "learning_average_return": safe_float(
            get_first(
                intelligence,
                "Historical Signal Average Return %",
                "Learning Avg Return %",
                "average_return_pct",
                default=0,
            )
        ),

        "score_bucket": safe_text(
            get_first(
                intelligence,
                "Score Bucket",
                "score_bucket",
                default="",
            )
        ),

        "score_bucket_observations": safe_float(
            get_first(
                intelligence,
                "Score Bucket Observations",
                "score_bucket_observations",
                default=0,
            )
        ),

        "score_bucket_win_rate": safe_float(
            get_first(
                intelligence,
                "Score Bucket Win Rate %",
                "score_bucket_win_rate",
                default=0,
            )
        ),

        "score_bucket_average_return": safe_float(
            get_first(
                intelligence,
                "Score Bucket Average Return %",
                "score_bucket_average_return",
                default=0,
            )
        ),

        "preferred_horizon": safe_float(
            get_first(
                intelligence,
                "Preferred Learning Horizon",
                "preferred_learning_horizon",
                default=0,
            )
        ),

        "preferred_horizon_status": safe_text(
            get_first(
                intelligence,
                "Learning Horizon Status",
                "Preferred Learning Reliability",
                "preferred_learning_reliability",
                default="",
            )
        ).upper(),

        "learning_adjustment": safe_float(
            get_first(
                intelligence,
                "Learning Adjustment",
                "learning_adjustment",
                default=0,
            )
        ),
    }


# ============================================================================
# PRODUCTION-ALIGNED BUY MORE GATE DIAGNOSTICS
# ============================================================================

def diagnostic_buy_more_gates(
    fields: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Explain the actual production BUY MORE qualification criteria.

    Thresholds come directly from agents.ai_decision_reconciler.

    These checks explain the production result.
    They do not replace production reconciliation.
    """

    gates: list[dict[str, Any]] = []

    existing_holding = fields[
        "production_existing_holding"
    ]

    # ------------------------------------------------------------------------
    # Existing holding
    # ------------------------------------------------------------------------

    gates.append(
        {
            "Gate": "Existing holding",
            "Value": (
                existing_holding
                if existing_holding is not None
                else "NOT CAPTURED"
            ),
            "Required": True,
            "Pass": (
                None
                if existing_holding is None
                else bool(existing_holding)
            ),
        }
    )

    # ------------------------------------------------------------------------
    # Proposed action
    # ------------------------------------------------------------------------

    gates.append(
        {
            "Gate": "Proposed action = BUY MORE",
            "Value": fields["proposal"],
            "Required": "BUY MORE",
            "Pass": (
                fields["proposal"].upper()
                == "BUY MORE"
            ),
        }
    )

    # ------------------------------------------------------------------------
    # Evidence
    # ------------------------------------------------------------------------

    gates.append(
        {
            "Gate": "Evidence >= production minimum",
            "Value": fields["evidence_score"],
            "Required": (
                BUY_MORE_MIN_EVIDENCE
                if BUY_MORE_MIN_EVIDENCE is not None
                else "NOT EXPOSED"
            ),
            "Pass": (
                None
                if BUY_MORE_MIN_EVIDENCE is None
                else (
                    fields["evidence_score"]
                    >= float(
                        BUY_MORE_MIN_EVIDENCE
                    )
                )
            ),
        }
    )

    # ------------------------------------------------------------------------
    # Deterministic confidence
    # ------------------------------------------------------------------------

    gates.append(
        {
            "Gate": "Confidence >= production minimum",
            "Value": fields["confidence"],
            "Required": (
                BUY_MORE_MIN_CONFIDENCE
                if BUY_MORE_MIN_CONFIDENCE is not None
                else "NOT EXPOSED"
            ),
            "Pass": (
                None
                if BUY_MORE_MIN_CONFIDENCE is None
                else (
                    fields["confidence"]
                    >= float(
                        BUY_MORE_MIN_CONFIDENCE
                    )
                )
            ),
        }
    )

    # ------------------------------------------------------------------------
    # Investment score
    # ------------------------------------------------------------------------

    gates.append(
        {
            "Gate": "Investment Score >= production minimum",
            "Value": fields["investment_score"],
            "Required": (
                BUY_MORE_MIN_INVESTMENT_SCORE
                if BUY_MORE_MIN_INVESTMENT_SCORE is not None
                else "NOT EXPOSED"
            ),
            "Pass": (
                None
                if BUY_MORE_MIN_INVESTMENT_SCORE is None
                else (
                    fields["investment_score"]
                    >= float(
                        BUY_MORE_MIN_INVESTMENT_SCORE
                    )
                )
            ),
        }
    )

    # ------------------------------------------------------------------------
    # Signal
    # ------------------------------------------------------------------------

    allowed_signals = {
        safe_text(
            signal
        ).upper()
        for signal in BUY_MORE_SUPPORTING_SIGNALS
    }

    gates.append(
        {
            "Gate": "Signal supports BUY MORE",
            "Value": fields["signal"],
            "Required": ", ".join(
                sorted(
                    allowed_signals
                )
            ),
            "Pass": (
                fields["signal"]
                in allowed_signals
            ),
        }
    )

    # ------------------------------------------------------------------------
    # LLM review
    # ------------------------------------------------------------------------

    gates.append(
        {
            "Gate": "LLM review = ACCEPT",
            "Value": fields["llm_review"],
            "Required": "ACCEPT",
            "Pass": (
                fields["llm_review"]
                == "ACCEPT"
            ),
        }
    )

    # ------------------------------------------------------------------------
    # LLM confidence
    # ------------------------------------------------------------------------

    gates.append(
        {
            "Gate": "LLM confidence >= production minimum",
            "Value": fields["llm_confidence"],
            "Required": (
                BUY_MORE_MIN_LLM_CONFIDENCE
                if BUY_MORE_MIN_LLM_CONFIDENCE is not None
                else "NOT EXPOSED"
            ),
            "Pass": (
                None
                if BUY_MORE_MIN_LLM_CONFIDENCE is None
                else (
                    fields["llm_confidence"]
                    >= float(
                        BUY_MORE_MIN_LLM_CONFIDENCE
                    )
                )
            ),
        }
    )

    # ------------------------------------------------------------------------
    # Contradiction
    # ------------------------------------------------------------------------

    contradiction = has_material_contradiction(
        fields
    )

    gates.append(
        {
            "Gate": "No material contradiction",
            "Value": (
                "CONTRADICTION"
                if contradiction
                else "NONE"
            ),
            "Required": "NONE",
            "Pass": not contradiction,
        }
    )

    # ------------------------------------------------------------------------
    # Allocation
    # ------------------------------------------------------------------------

    allocation = fields[
        "allocation"
    ]

    gates.append(
        {
            "Gate": "Allocation is present",
            "Value": allocation,
            "Required": "PRESENT",
            "Pass": (
                None
                if fields.get(
                    "allocation"
                ) is None
                else True
            ),
        }
    )

    gates.append(
        {
            "Gate": "Allocation >= 0",
            "Value": allocation,
            "Required": 0,
            "Pass": (
                None
                if allocation is None
                else allocation >= 0
            ),
        }
    )

    gates.append(
        {
            "Gate": "Allocation <= production maximum",
            "Value": allocation,
            "Required": (
                BUY_MORE_MAX_ALLOCATION_PERCENT
                if BUY_MORE_MAX_ALLOCATION_PERCENT is not None
                else "NOT EXPOSED"
            ),
            "Pass": (
                None
                if BUY_MORE_MAX_ALLOCATION_PERCENT is None
                else (
                    allocation
                    <= float(
                        BUY_MORE_MAX_ALLOCATION_PERCENT
                    )
                )
            ),
        }
    )

    return gates


# ============================================================================
# BUY NEW GATE DIAGNOSTICS
# ============================================================================

def diagnostic_buy_new_gates(
    fields: dict[str, Any],
    learning: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Evaluate the BUY NEW diagnostic criteria.

    The production implementation remains authoritative.

    Where a production constant is not exposed, the check is marked
    NOT EXPOSED rather than inventing a threshold.
    """

    gates: list[dict[str, Any]] = []

    gates.append(
        {
            "Gate": "Not already held",
            "Value": fields["held"],
            "Required": False,
            "Pass": not fields["held"],
        }
    )

    gates.append(
        {
            "Gate": "Evidence meets minimum",
            "Value": fields["evidence_score"],
            "Required": (
                MIN_EVIDENCE_SCORE
                if MIN_EVIDENCE_SCORE is not None
                else "NOT EXPOSED"
            ),
            "Pass": (
                None
                if MIN_EVIDENCE_SCORE is None
                else (
                    fields["evidence_score"]
                    >= float(
                        MIN_EVIDENCE_SCORE
                    )
                )
            ),
        }
    )

    gates.append(
        {
            "Gate": "Deterministic confidence meets minimum",
            "Value": fields["confidence"],
            "Required": (
                MIN_DETERMINISTIC_CONFIDENCE
                if MIN_DETERMINISTIC_CONFIDENCE is not None
                else "NOT EXPOSED"
            ),
            "Pass": (
                None
                if MIN_DETERMINISTIC_CONFIDENCE is None
                else (
                    fields["confidence"]
                    >= float(
                        MIN_DETERMINISTIC_CONFIDENCE
                    )
                )
            ),
        }
    )

    if BUY_NEW_STARTER_ALLOCATION_CAP is not None:

        gates.append(
            {
                "Gate": "Starter allocation <= configured cap",
                "Value": fields["allocation"],
                "Required": BUY_NEW_STARTER_ALLOCATION_CAP,
                "Pass": (
                    fields["allocation"]
                    <= float(
                        BUY_NEW_STARTER_ALLOCATION_CAP
                    )
                ),
            }
        )

    else:

        gates.append(
            {
                "Gate": "Starter allocation <= configured cap",
                "Value": fields["allocation"],
                "Required": "NOT EXPOSED",
                "Pass": None,
            }
        )

    if BUY_NEW_IMMATURE_MIN_EVIDENCE is not None:

        gates.append(
            {
                "Gate": "Immature-history evidence floor",
                "Value": fields["evidence_score"],
                "Required": BUY_NEW_IMMATURE_MIN_EVIDENCE,
                "Pass": (
                    fields["evidence_score"]
                    >= float(
                        BUY_NEW_IMMATURE_MIN_EVIDENCE
                    )
                ),
            }
        )

    if BUY_NEW_IMMATURE_MIN_INVESTMENT_SCORE is not None:

        gates.append(
            {
                "Gate": "Immature-history Investment Score floor",
                "Value": fields["investment_score"],
                "Required": BUY_NEW_IMMATURE_MIN_INVESTMENT_SCORE,
                "Pass": (
                    fields["investment_score"]
                    >= float(
                        BUY_NEW_IMMATURE_MIN_INVESTMENT_SCORE
                    )
                ),
            }
        )

    if (
        BUY_NEW_IMMATURE_MIN_SCORE_BUCKET_WIN_RATE
        is not None
    ):

        gates.append(
            {
                "Gate": "Immature-history score-bucket win rate",
                "Value": learning[
                    "score_bucket_win_rate"
                ],
                "Required": (
                    BUY_NEW_IMMATURE_MIN_SCORE_BUCKET_WIN_RATE
                ),
                "Pass": (
                    learning[
                        "score_bucket_win_rate"
                    ]
                    >= float(
                        BUY_NEW_IMMATURE_MIN_SCORE_BUCKET_WIN_RATE
                    )
                ),
            }
        )

    if (
        BUY_NEW_IMMATURE_MIN_SCORE_BUCKET_OBSERVATIONS
        is not None
    ):

        gates.append(
            {
                "Gate": "Immature-history score-bucket observations",
                "Value": learning[
                    "score_bucket_observations"
                ],
                "Required": (
                    BUY_NEW_IMMATURE_MIN_SCORE_BUCKET_OBSERVATIONS
                ),
                "Pass": (
                    learning[
                        "score_bucket_observations"
                    ]
                    >= float(
                        BUY_NEW_IMMATURE_MIN_SCORE_BUCKET_OBSERVATIONS
                    )
                ),
            }
        )

    gates.append(
        {
            "Gate": "No material contradiction",
            "Value": (
                "CONTRADICTION"
                if has_material_contradiction(
                    fields
                )
                else "NONE"
            ),
            "Required": "NONE",
            "Pass": not has_material_contradiction(
                fields
            ),
        }
    )

    return gates


# ============================================================================
# GATE OUTPUT
# ============================================================================

def gate_status(
    value: Any,
) -> str:
    """
    Format a gate result.
    """

    if value is True:
        return "PASS"

    if value is False:
        return "FAIL"

    return "N/A"


def print_gate_table(
    gates: list[dict[str, Any]],
) -> list[str]:
    """
    Print individual governance gates and return failed gate names.
    """

    failed_gates: list[str] = []

    for gate in gates:

        status = gate_status(
            gate["Pass"]
        )

        print(
            f"  {status:<4} "
            f"{gate['Gate']}"
        )

        print(
            f"       Value   : {gate['Value']}"
        )

        print(
            f"       Required: {gate['Required']}"
        )

        if gate["Pass"] is False:
            failed_gates.append(
                gate["Gate"]
            )

    return failed_gates


# ============================================================================
# PRINCIPAL GOVERNANCE DIAGNOSTIC
# ============================================================================

def classify_downgrade(
    fields: dict[str, Any],
    buy_more_failed: list[str],
    buy_new_failed: list[str],
) -> str:
    """
    Identify the most likely principal reason for a downgraded proposal.

    Production governance text is given priority.

    Diagnostic gates are then used to explain the result.

    This does NOT alter the production result.
    """

    final_decision = fields[
        "final_decision"
    ].upper()

    proposal = fields[
        "proposal"
    ].upper()

    if final_decision in {
        "BUY NEW",
        "BUY MORE",
    }:
        return "APPROVED"

    # ------------------------------------------------------------------------
    # Production governance reason first.
    # ------------------------------------------------------------------------

    governance_reasons = safe_text(
        fields[
            "governance_reasons"
        ]
    )

    final_reason = safe_text(
        fields[
            "final_reason"
        ]
    )

    reconciliation = safe_text(
        fields[
            "reconciliation"
        ]
    ).upper()

    llm_review = safe_text(
        fields[
            "llm_review"
        ]
    ).upper()

    text = (
        f"{governance_reasons} "
        f"{final_reason}"
    ).upper()

    # ------------------------------------------------------------------------
    # Explicit production reason.
    # ------------------------------------------------------------------------

    if governance_reasons:
        return (
            "PRODUCTION GOVERNANCE: "
            + governance_reasons
        )

    if final_reason:
        return (
            "PRODUCTION FINAL REASON: "
            + final_reason
        )

    # ------------------------------------------------------------------------
    # Reconciliation state.
    # ------------------------------------------------------------------------

    if reconciliation in {
        "REVIEW REQUIRED",
        "CHALLENGE",
        "REJECT",
    }:
        return (
            "PRODUCTION RECONCILIATION: "
            + reconciliation
        )

    if llm_review in {
        "REJECT",
        "CHALLENGE",
    }:
        return (
            "LLM "
            + llm_review
        )

    # ------------------------------------------------------------------------
    # Diagnostic gates.
    # ------------------------------------------------------------------------

    if proposal.startswith(
        "BUY MORE"
    ):

        if buy_more_failed:
            return (
                "BUY MORE DIAGNOSTIC GATE: "
                + buy_more_failed[0]
            )

    if proposal.startswith(
        "BUY NEW"
    ):

        if buy_new_failed:
            return (
                "BUY NEW DIAGNOSTIC GATE: "
                + buy_new_failed[0]
            )

    # ------------------------------------------------------------------------
    # General fallback.
    # ------------------------------------------------------------------------

    if fields[
        "evidence_score"
    ] < 60:
        return "WEAK DETERMINISTIC EVIDENCE"

    if fields[
        "confidence"
    ] < 70:
        return "LOW DETERMINISTIC CONFIDENCE"

    if (
        "CONCENTRATION"
        in text
        or "ALLOCATION"
        in text
        or "PORTFOLIO"
        in text
        or "SECTOR"
        in text
    ):
        return "PORTFOLIO / ALLOCATION GOVERNANCE"

    return "OTHER GOVERNANCE OVERRIDE"


# ============================================================================
# RUN PRODUCTION PIPELINE
# ============================================================================

def run_production_pipeline() -> Any:
    """
    Temporarily intercept main.py's final decision call and execute
    the existing production pipeline.

    The original production functions are restored in finally blocks.
    """

    global captured_buy_more_holding_state

    captured_buy_more_holding_state = {}

    original_final_function = (
        production_main.generate_final_portfolio_decisions
    )

    original_reconcile_function = (
        reconciler.reconcile_decision
        if hasattr(
            reconciler,
            "reconcile_decision",
        )
        else None
    )

    if original_reconcile_function is None:
        raise RuntimeError(
            "agents.ai_decision_reconciler does not expose "
            "reconcile_decision()."
        )

    # Update the module-level delegate used by the interceptor.
    global _original_reconcile

    _original_reconcile = (
        original_reconcile_function
    )

    production_main.generate_final_portfolio_decisions = (
        intercepted_final_decisions
    )

    reconciler.reconcile_decision = (
        intercepted_reconcile_decision
    )

    try:

        if not hasattr(
            production_main,
            "main",
        ):
            raise RuntimeError(
                "main.py does not expose main()."
            )

        print(
            "Calling production main.main()..."
        )

        return_value = production_main.main()

        # The final decision function normally populates captured_result.
        # Preserve that production result.
        return (
            captured_result
            if captured_result is not None
            else return_value
        )

    finally:

        production_main.generate_final_portfolio_decisions = (
            original_final_function
        )

        reconciler.reconcile_decision = (
            original_reconcile_function
        )

        print()
        print(
            "Production final decision and reconciler functions restored."
        )


# ============================================================================
# FINAL DECISION DATAFRAME
# ============================================================================

def get_final_dataframe() -> pd.DataFrame:
    """
    Return the captured final decision DataFrame.
    """

    result = captured_result

    if result is None:
        raise RuntimeError(
            "Production final decision returned None."
        )

    df = dataframe_or_empty(
        result
    )

    if df.empty:
        raise RuntimeError(
            "Production final decision DataFrame is empty."
        )

    return df


# ============================================================================
# DETAILED BUY DIAGNOSTIC
# ============================================================================

def diagnose_buy_candidates(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Produce detailed diagnostics for BUY NEW / BUY MORE candidates.
    """

    proposal_column = None

    for candidate in [
        "Proposed Action",
        "Proposed_Action",
        "Action",
    ]:

        if candidate in df.columns:
            proposal_column = candidate
            break

    if proposal_column is None:

        raise RuntimeError(
            "Could not find Proposed Action column."
        )

    proposals = df[
        df[
            proposal_column
        ]
        .astype(str)
        .str.upper()
        .str.startswith(
            (
                "BUY NEW",
                "BUY MORE",
            )
        )
    ].copy()

    print()
    print("=" * 110)
    print(
        f"BUY CANDIDATES FOUND: {len(proposals)}"
    )
    print("=" * 110)

    if proposals.empty:

        print(
            "No BUY NEW / BUY MORE proposals found."
        )

        return pd.DataFrame()

    recommendation_intelligence = captured_inputs.get(
        "recommendation_intelligence"
    )

    intelligence_lookup = build_intelligence_lookup(
        recommendation_intelligence
    )

    diagnostic_rows: list[dict[str, Any]] = []

    for _, row in proposals.iterrows():

        fields = extract_decision_fields(
            row
        )

        ticker = fields[
            "ticker"
        ]

        learning = learning_fields(
            ticker,
            intelligence_lookup,
        )

        buy_more_gates = []

        buy_new_gates = []

        if fields[
            "proposal"
        ].upper().startswith(
            "BUY MORE"
        ):

            buy_more_gates = diagnostic_buy_more_gates(
                fields
            )

        if fields[
            "proposal"
        ].upper().startswith(
            "BUY NEW"
        ):

            buy_new_gates = diagnostic_buy_new_gates(
                fields,
                learning,
            )

        buy_more_failed = [
            gate["Gate"]
            for gate in buy_more_gates
            if gate["Pass"] is False
        ]

        buy_new_failed = [
            gate["Gate"]
            for gate in buy_new_gates
            if gate["Pass"] is False
        ]

        classification = classify_downgrade(
            fields,
            buy_more_failed,
            buy_new_failed,
        )

        diagnostic_rows.append(
            {
                "Ticker": ticker,
                "Proposal": fields[
                    "proposal"
                ],
                "Held": fields[
                    "held"
                ],
                "Production Existing Holding": fields[
                    "production_existing_holding"
                ],
                "Allocation %": fields[
                    "allocation"
                ],
                "Investment Score": fields[
                    "investment_score"
                ],
                "Learning Adjusted Score": fields[
                    "learning_adjusted_score"
                ],
                "Signal": fields[
                    "signal"
                ],
                "Evidence Score": fields[
                    "evidence_score"
                ],
                "Evidence Strength": fields[
                    "evidence_strength"
                ],
                "Evidence Support": fields[
                    "evidence_support"
                ],
                "Decision Confidence": fields[
                    "confidence"
                ],
                "Learning Observations": learning[
                    "learning_observations"
                ],
                "Learning Reliability": learning[
                    "learning_reliability"
                ],
                "Learning Avg Return %": learning[
                    "learning_average_return"
                ],
                "Score Bucket": learning[
                    "score_bucket"
                ],
                "Score Bucket Observations": learning[
                    "score_bucket_observations"
                ],
                "Score Bucket Win Rate %": learning[
                    "score_bucket_win_rate"
                ],
                "Preferred Learning Horizon": learning[
                    "preferred_horizon"
                ],
                "Learning Horizon Status": learning[
                    "preferred_horizon_status"
                ],
                "Learning Adjustment": learning[
                    "learning_adjustment"
                ],
                "LLM Review": fields[
                    "llm_review"
                ],
                "LLM Confidence": fields[
                    "llm_confidence"
                ],
                "Reconciliation": fields[
                    "reconciliation"
                ],
                "Decision Status": fields[
                    "decision_status"
                ],
                "Final Decision": fields[
                    "final_decision"
                ],
                "Decision Changed": fields[
                    "decision_changed"
                ],
                "Governance Classification": classification,
                "Governance Reasons": fields[
                    "governance_reasons"
                ],
                "Final Reason": fields[
                    "final_reason"
                ],
                "BUY MORE Failed Gates": (
                    " | ".join(
                        buy_more_failed
                    )
                ),
                "BUY NEW Failed Gates": (
                    " | ".join(
                        buy_new_failed
                    )
                ),
            }
        )

    diagnostic = pd.DataFrame(
        diagnostic_rows
    )

    # ------------------------------------------------------------------------
    # Full summary table.
    # ------------------------------------------------------------------------

    print()
    print("=" * 110)
    print("BUY CANDIDATE SUMMARY")
    print("=" * 110)

    summary_columns = [
        "Ticker",
        "Proposal",
        "Held",
        "Production Existing Holding",
        "Allocation %",
        "Investment Score",
        "Learning Adjusted Score",
        "Signal",
        "Evidence Score",
        "Decision Confidence",
        "LLM Review",
        "LLM Confidence",
        "Reconciliation",
        "Final Decision",
        "Governance Classification",
        "BUY MORE Failed Gates",
        "BUY NEW Failed Gates",
    ]

    summary_columns = [
        column
        for column in summary_columns
        if column in diagnostic.columns
    ]

    print(
        diagnostic[
            summary_columns
        ].to_string(
            index=False
        )
    )

    # ------------------------------------------------------------------------
    # Individual gate diagnostics.
    # ------------------------------------------------------------------------

    print()
    print("=" * 110)
    print("INDIVIDUAL GOVERNANCE GATE DIAGNOSTICS")
    print("=" * 110)

    for _, row in proposals.iterrows():

        fields = extract_decision_fields(
            row
        )

        ticker = fields[
            "ticker"
        ]

        proposal = fields[
            "proposal"
        ].upper()

        print()
        print("-" * 110)
        print(
            f"{ticker} | {proposal} -> "
            f"{fields['final_decision'] or 'UNKNOWN'}"
        )
        print("-" * 110)

        print(
            f"  Production Existing Holding: "
            f"{fields['production_existing_holding']}"
        )

        print(
            f"  Investment Score       : "
            f"{fields['investment_score']:.2f}"
        )

        print(
            f"  Learning Adjusted Score: "
            f"{fields['learning_adjusted_score']:.2f}"
        )

        print(
            f"  Signal                 : "
            f"{fields['signal'] or 'N/A'}"
        )

        print(
            f"  Evidence Score         : "
            f"{fields['evidence_score']:.2f}"
        )

        print(
            f"  Evidence Strength      : "
            f"{fields['evidence_strength'] or 'N/A'}"
        )

        print(
            f"  Evidence Support       : "
            f"{fields['evidence_support'] or 'N/A'}"
        )

        print(
            f"  Deterministic Confidence: "
            f"{fields['confidence']:.2f}"
        )

        print(
            f"  Current Allocation     : "
            f"{fields['allocation']:.2f}%"
        )

        print(
            f"  LLM Review             : "
            f"{fields['llm_review'] or 'N/A'}"
        )

        print(
            f"  LLM Confidence        : "
            f"{fields['llm_confidence']:.2f}"
        )

        print(
            f"  Reconciliation         : "
            f"{fields['reconciliation'] or 'N/A'}"
        )

        print(
            f"  Decision Status        : "
            f"{fields['decision_status'] or 'N/A'}"
        )

        print(
            f"  Final Decision         : "
            f"{fields['final_decision'] or 'N/A'}"
        )

        print()

        if proposal.startswith(
            "BUY MORE"
        ):

            print(
                "  BUY MORE PRODUCTION-ALIGNED GOVERNANCE CHECKS"
            )

            failed_gates = print_gate_table(
                diagnostic_buy_more_gates(
                    fields
                )
            )

        elif proposal.startswith(
            "BUY NEW"
        ):

            recommendation_intelligence = captured_inputs.get(
                "recommendation_intelligence"
            )

            intelligence_lookup = build_intelligence_lookup(
                recommendation_intelligence
            )

            learning = learning_fields(
                ticker,
                intelligence_lookup,
            )

            print(
                "  BUY NEW GOVERNANCE CHECKS"
            )

            failed_gates = print_gate_table(
                diagnostic_buy_new_gates(
                    fields,
                    learning,
                )
            )

        else:

            failed_gates = []

        print()

        if failed_gates:

            print(
                "  DIAGNOSTIC FAILED GATES:"
            )

            for gate in failed_gates:

                print(
                    f"    - {gate}"
                )

        else:

            print(
                "  DIAGNOSTIC GATES: "
                "No diagnostic gate failure identified."
            )

        print()

        if fields[
            "governance_reasons"
        ]:

            print(
                "  PRODUCTION GOVERNANCE REASONS:"
            )

            print(
                f"    {fields['governance_reasons']}"
            )

        if fields[
            "final_reason"
        ]:

            print(
                "  PRODUCTION FINAL REASON:"
            )

            print(
                "    "
                f"{fields['final_reason']}"
            )

    return diagnostic


# ============================================================================
# SUMMARY
# ============================================================================

def print_summary(
    diagnostic: pd.DataFrame,
) -> None:
    """
    Print concise BUY NEW / BUY MORE summary.
    """

    print()
    print("=" * 110)
    print("BUY NEW / BUY MORE SUMMARY")
    print("=" * 110)

    if diagnostic.empty:

        print(
            "No BUY NEW / BUY MORE candidates."
        )

        return

    for proposal_type in [
        "BUY NEW",
        "BUY MORE",
    ]:

        subset = diagnostic[
            diagnostic[
                "Proposal"
            ]
            .astype(str)
            .str.upper()
            .str.startswith(
                proposal_type
            )
        ]

        if subset.empty:

            print()
            print(
                f"{proposal_type}: 0 candidates"
            )

            continue

        approved = subset[
            subset[
                "Final Decision"
            ]
            .astype(str)
            .str.upper()
            ==
            proposal_type
        ]

        downgraded = subset[
            ~(
                subset[
                    "Final Decision"
                ]
                .astype(str)
                .str.upper()
                ==
                proposal_type
            )
        ]

        challenged = subset[
            subset[
                "LLM Review"
            ]
            .astype(str)
            .str.upper()
            .isin(
                {
                    "CHALLENGE",
                    "REJECT",
                }
            )
        ]

        print()
        print(
            proposal_type
        )

        print(
            f"  Candidates           : "
            f"{len(subset)}"
        )

        print(
            f"  Approved             : "
            f"{len(approved)}"
        )

        print(
            f"  Rejected / downgraded: "
            f"{len(downgraded)}"
        )

        print(
            f"  LLM challenged       : "
            f"{len(challenged)}"
        )

        print(
            f"  Average Investment Score: "
            f"{subset['Investment Score'].mean():.2f}"
        )

        print(
            f"  Average Evidence Score: "
            f"{subset['Evidence Score'].mean():.2f}"
        )

        print(
            f"  Average Decision Confidence: "
            f"{subset['Decision Confidence'].mean():.2f}"
        )

        print()

        if not downgraded.empty:

            print(
                "  Downgrade classifications:"
            )

            counts = (
                downgraded[
                    "Governance Classification"
                ]
                .value_counts()
            )

            for classification, count in counts.items():

                print(
                    f"    {classification}: "
                    f"{count}"
                )


# ============================================================================
# KNOWN GOVERNANCE CASES
# ============================================================================

def print_known_cases(
    diagnostic: pd.DataFrame,
) -> None:
    """
    Print known governance cases for regression visibility.
    """

    print()
    print("=" * 110)
    print("KNOWN GOVERNANCE CASES")
    print("=" * 110)

    known_cases = [
        "CRDO",
        "ERO",
        "ANET",
        "PLTR",
        "GE",
    ]

    if diagnostic.empty:

        for ticker in known_cases:

            print(
                f"{ticker}: NOT PRESENT"
            )

        return

    for ticker in known_cases:

        match = diagnostic[
            diagnostic[
                "Ticker"
            ]
            .astype(str)
            .str.upper()
            ==
            ticker
        ]

        if match.empty:

            print(
                f"{ticker}: NOT PRESENT"
            )

            continue

        row = match.iloc[0]

        print(
            f"{ticker}: "
            f"{row['Proposal']} -> "
            f"{row['Final Decision']} | "
            f"{row['Governance Classification']}"
        )

        print(
            f"    Existing Holding="
            f"{row['Production Existing Holding']} | "
            f"Evidence={row['Evidence Score']:.2f} | "
            f"Confidence={row['Decision Confidence']:.2f} | "
            f"Investment={row['Investment Score']:.2f} | "
            f"LLM={row['LLM Review']} | "
            f"LLM Confidence={row['LLM Confidence']:.2f}"
        )

        if safe_text(
            row["BUY MORE Failed Gates"]
        ):

            print(
                "    BUY MORE failed gates: "
                f"{row['BUY MORE Failed Gates']}"
            )

        if safe_text(
            row["BUY NEW Failed Gates"]
        ):

            print(
                "    BUY NEW failed gates: "
                f"{row['BUY NEW Failed Gates']}"
            )


# ============================================================================
# RECOMMENDATION INTELLIGENCE VALIDATION
# ============================================================================

def print_learning_validation(
    diagnostic: pd.DataFrame,
) -> None:
    """
    Validate that Recommendation Intelligence remains available for
    the BUY candidates.
    """

    print()
    print("=" * 110)
    print("RECOMMENDATION INTELLIGENCE VALIDATION")
    print("=" * 110)

    recommendation_intelligence = captured_inputs.get(
        "recommendation_intelligence"
    )

    lookup = build_intelligence_lookup(
        recommendation_intelligence
    )

    if diagnostic.empty:

        print(
            "No BUY candidates to validate."
        )

        return

    for ticker in diagnostic[
        "Ticker"
    ].tolist():

        intelligence = lookup.get(
            ticker
        )

        if not intelligence:

            print(
                f"{ticker}: "
                "Recommendation Intelligence NOT FOUND"
            )

            continue

        learning = learning_fields(
            ticker,
            lookup,
        )

        print(
            f"{ticker}: "
            f"Signal Obs={learning['learning_observations']:.0f}, "
            f"Signal Reliability={learning['learning_reliability'] or 'N/A'}, "
            f"Score Bucket={learning['score_bucket'] or 'N/A'}, "
            f"Score Bucket Obs={learning['score_bucket_observations']:.0f}, "
            f"Score Bucket Win Rate={learning['score_bucket_win_rate']:.2f}%, "
            f"Preferred Horizon={learning['preferred_horizon']:.0f}"
        )


# ============================================================================
# PRODUCTION CONTRACT CHECK
# ============================================================================

def print_production_contract() -> None:
    """
    Confirm the production interface still exposes the expected
    final decision function and reconciler.
    """

    print()
    print("=" * 110)
    print("PRODUCTION INTERFACE CHECK")
    print("=" * 110)

    function = getattr(
        production_main,
        "generate_final_portfolio_decisions",
        None,
    )

    if function is None:

        print(
            "ERROR: production_main.generate_final_portfolio_decisions "
            "is not available."
        )

    else:

        print(
            "Production final decision function:"
        )

        print(
            f"  {function.__module__}"
            f".{function.__name__}"
        )

        try:

            print(
                "Production signature:"
            )

            print(
                f"  {inspect.signature(function)}"
            )

        except Exception as exc:

            print(
                f"  Signature unavailable: {exc}"
            )

    reconcile_function = getattr(
        reconciler,
        "reconcile_decision",
        None,
    )

    if reconcile_function is None:

        print(
            "ERROR: reconciler.reconcile_decision "
            "is not available."
        )

    else:

        print(
            "Production reconciler:"
        )

        print(
            f"  {reconcile_function.__module__}"
            f".{reconcile_function.__name__}"
        )

        try:

            print(
                "Reconciler signature:"
            )

            print(
                f"  {inspect.signature(reconcile_function)}"
            )

        except Exception as exc:

            print(
                f"  Signature unavailable: {exc}"
            )

    print()
    print(
        "Production BUY MORE thresholds:"
    )

    print(
        f"  Evidence minimum       : "
        f"{BUY_MORE_MIN_EVIDENCE}"
    )

    print(
        f"  Confidence minimum     : "
        f"{BUY_MORE_MIN_CONFIDENCE}"
    )

    print(
        f"  Investment Score minimum: "
        f"{BUY_MORE_MIN_INVESTMENT_SCORE}"
    )

    print(
        f"  LLM Confidence minimum : "
        f"{BUY_MORE_MIN_LLM_CONFIDENCE}"
    )

    print(
        f"  Maximum allocation      : "
        f"{BUY_MORE_MAX_ALLOCATION_PERCENT}"
    )

    print(
        f"  Supporting signals      : "
        f"{sorted(BUY_MORE_SUPPORTING_SIGNALS)}"
    )


# ============================================================================
# MAIN
# ============================================================================

def main() -> None:
    """
    Run the complete BUY / BUY MORE diagnostic.
    """

    print()
    print("=" * 110)
    print("BUY / BUY MORE GOVERNED DECISION DIAGNOSTIC")
    print("=" * 110)
    print()

    print(
        "Project root:"
    )

    print(
        f"  {PROJECT_ROOT}"
    )

    print()

    print_production_contract()

    # ------------------------------------------------------------------------
    # Capture the production run.
    # ------------------------------------------------------------------------

    try:

        run_production_pipeline()

    except Exception as exc:

        print()
        print(
            "=" * 110
        )
        print(
            "PRODUCTION PIPELINE ERROR"
        )
        print(
            "=" * 110
        )

        print(
            f"{type(exc).__name__}: {exc}"
        )

        traceback.print_exc()

        raise

    # ------------------------------------------------------------------------
    # Validate capture.
    # ------------------------------------------------------------------------

    print()
    print("=" * 110)
    print("CAPTURED PRODUCTION INPUTS")
    print("=" * 110)

    for key, value in captured_inputs.items():

        if isinstance(
            value,
            pd.DataFrame,
        ):

            print(
                f"{key}: DataFrame "
                f"{value.shape}"
            )

        elif isinstance(
            value,
            list,
        ):

            print(
                f"{key}: list "
                f"({len(value)} items)"
            )

        elif isinstance(
            value,
            dict,
        ):

            print(
                f"{key}: dict "
                f"({len(value)} keys)"
            )

        else:

            print(
                f"{key}: "
                f"{type(value).__name__}"
            )

    # ------------------------------------------------------------------------
    # Final decisions.
    # ------------------------------------------------------------------------

    df = get_final_dataframe()

    print()
    print(
        "Final decision DataFrame:"
    )

    print(
        f"  Rows    : {len(df)}"
    )

    print(
        f"  Columns : {len(df.columns)}"
    )

    # ------------------------------------------------------------------------
    # Diagnostic.
    # ------------------------------------------------------------------------

    diagnostic = diagnose_buy_candidates(
        df
    )

    # ------------------------------------------------------------------------
    # Summary.
    # ------------------------------------------------------------------------

    print_summary(
        diagnostic
    )

    # ------------------------------------------------------------------------
    # Known cases.
    # ------------------------------------------------------------------------

    print_known_cases(
        diagnostic
    )

    # ------------------------------------------------------------------------
    # Learning validation.
    # ------------------------------------------------------------------------

    print_learning_validation(
        diagnostic
    )

    # ------------------------------------------------------------------------
    # Completion.
    # ------------------------------------------------------------------------

    print()
    print("=" * 110)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 110)
    print()

    print(
        "Production final decision function was restored."
    )

    print(
        "Production reconciler was restored."
    )

    print(
        "No production decision thresholds or scoring logic "
        "were modified by this diagnostic."
    )

    print(
        "The individual gate results above are diagnostic "
        "explanations only; the production final decision "
        "remains authoritative."
    )


# ============================================================================
# SCRIPT ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    main()
