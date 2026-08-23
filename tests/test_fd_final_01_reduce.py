
"""
Regression tests for FD-FINAL-01.

FD-FINAL-01:
    A justified REDUCE proposal must not be incorrectly overridden to HOLD.

These tests exercise the established public compatibility API:

    analysis.final_portfolio_decision.calculate_final_portfolio_decision

The tests deliberately do not import or test the internal reconciler
directly.

The public final-decision API exposes reconciliation through the flattened
result field:

    result["Reconciled Decision"]

rather than requiring an internal nested:

    result["reconciliation"]

object.

The tests therefore validate the public API contract rather than coupling
the regression suite to internal implementation details.
"""

from __future__ import annotations

from analysis.final_portfolio_decision import (
    calculate_final_portfolio_decision,
)


# ============================================================================
# TEST DATA HELPERS
# ============================================================================

def make_candidate(
    ticker: str,
    *,
    owned: bool = True,
    investment_score: float = 39.0,
    sector: str = "Healthcare",
) -> dict:
    """Build the minimum candidate structure required by the final API."""

    return {
        "ticker": ticker,
        "asset_type": "STOCK",
        "ownership": {
            "owned": owned,
            "sector": sector,
        },
        "analysis": {
            "investment_score": investment_score,
        },
    }


def make_reduce_decision(
    *,
    score: float = 39.0,
    evidence_score: float = 67.41,
    evidence_strength: str = "STRONG",
    decision_support: str = "SUPPORTED",
    confidence: float = 68.74,
) -> dict:
    """Build a justified REDUCE 25% proposal."""

    return {
        "Ticker": "",
        "Proposed Action": "REDUCE 25%",
        "Action": "REDUCE 25%",
        "Reason": (
            "Weak investment score and negative signal justify "
            "reducing the position."
        ),
        "Investment Score": score,
        "Evidence Score": evidence_score,
        "Evidence Strength": evidence_strength,
        "Decision Support": decision_support,
        "Confidence": confidence,
    }


def make_sell_decision() -> dict:
    """Build a justified SELL proposal."""

    return {
        "Ticker": "",
        "Proposed Action": "SELL",
        "Action": "SELL",
        "Reason": "Strong evidence justifies exiting the position.",
        "Investment Score": 19.0,
        "Evidence Score": 95.0,
        "Evidence Strength": "VERY STRONG",
        "Decision Support": "SUPPORTED",
        "Confidence": 90.0,
    }


def make_hold_decision() -> dict:
    """Build a HOLD proposal."""

    return {
        "Ticker": "",
        "Proposed Action": "HOLD",
        "Action": "HOLD",
        "Reason": "Evidence does not justify a portfolio action.",
        "Investment Score": 50.0,
        "Evidence Score": 40.0,
        "Evidence Strength": "WEAK",
        "Decision Support": "NOT SUPPORTED",
        "Confidence": 45.0,
    }


def make_accept_review() -> dict:
    """Build an independent LLM ACCEPT review."""

    return {
        "LLM Assessment": "ACCEPT",
        "LLM Decision": "ACCEPT",
        "Review Decision": "ACCEPT",
        "LLM Confidence": 85.0,
        "Confidence": 85.0,
        "Challenge": False,
        "Reason": (
            "The proposed portfolio action is supported "
            "by the available evidence."
        ),
        "LLM Reason": (
            "The proposed portfolio action is supported "
            "by the available evidence."
        ),
    }


def make_reduce_reconciliation() -> dict:
    """
    Build reconciler output representing an approved REDUCE.

    The reconciler operates on the generic REDUCE action.

    The final-decision layer is responsible for preserving the original
    REDUCE percentage in the final decision.
    """

    return {
        "Reconciled Action": "REDUCE",
        "reconciled_action": "REDUCE",
        "Final Decision": "REDUCE",
        "Reconciliation Status": "APPROVED",
        "Governance Reasons": [
            "REDUCE proposal supported by strong evidence.",
            "Independent LLM review accepted the proposal.",
        ],
        "Governance Reason": (
            "REDUCE proposal supported by strong evidence."
        ),
        "Decision Support": "SUPPORTED",
        "Evidence Strength": "STRONG",
        "Evidence Score": 67.41,
        "LLM Review": "ACCEPT",
        "LLM Confidence": 85.0,
    }


def make_sell_reconciliation() -> dict:
    """Build reconciler output representing an approved SELL."""

    return {
        "Reconciled Action": "SELL",
        "reconciled_action": "SELL",
        "Final Decision": "SELL",
        "Reconciliation Status": "APPROVED",
        "Governance Reasons": [
            "SELL proposal supported by strong evidence.",
        ],
        "Governance Reason": (
            "SELL proposal supported by strong evidence."
        ),
    }


def make_hold_reconciliation() -> dict:
    """Build reconciler output representing an explicit HOLD."""

    return {
        "Reconciled Action": "HOLD",
        "reconciled_action": "HOLD",
        "Final Decision": "HOLD",
        "Reconciliation Status": "APPROVED",
        "Governance Reasons": [
            "Evidence does not justify a change to the existing position."
        ],
        "Governance Reason": (
            "Evidence does not justify a change to the existing position."
        ),
    }


# ============================================================================
# TEST EXECUTION HELPER
# ============================================================================

def run_final_decision(
    ticker: str,
    decision: dict,
    *,
    reconciliation: dict,
    investment_score: float = 39.0,
) -> dict:
    """
    Execute the established final-decision compatibility API.

    The reconciliation argument represents the output of the upstream
    reconciliation stage. It is passed into the public final-decision API,
    but the tests intentionally validate the flattened public result rather
    than requiring the internal reconciliation dictionary to be returned.
    """

    candidate = make_candidate(
        ticker,
        investment_score=investment_score,
    )

    decision = {
        **decision,
        "Ticker": ticker,
    }

    return calculate_final_portfolio_decision(
        candidate=candidate,
        portfolio={},
        decision=decision,
        review=make_accept_review(),
        explanation={},
        reconciled_decision=reconciliation,
    )


# ============================================================================
# FD-FINAL-01 REGRESSION TESTS
# ============================================================================

def test_fd_final_01_aemd_reduce_25_remains_reduce():
    """
    AEMD.L:

        Proposed Action   = REDUCE 25%
        Evidence          = STRONG / SUPPORTED
        LLM Review        = ACCEPT
        Reconciled Action = REDUCE

    Required:

        Final Decision     = REDUCE 25%
        Reconciled Decision = REDUCE
    """

    result = run_final_decision(
        "AEMD.L",
        make_reduce_decision(),
        reconciliation=make_reduce_reconciliation(),
    )

    assert result["Final Decision"] == "REDUCE 25%"
    assert result["Reconciled Decision"] == "REDUCE"


def test_fd_final_01_apld_reduce_25_remains_reduce():
    """
    APLD:

        Proposed Action   = REDUCE 25%
        Evidence          = STRONG / SUPPORTED
        LLM Review        = ACCEPT
        Reconciled Action = REDUCE

    Required:

        Final Decision     = REDUCE 25%
        Reconciled Decision = REDUCE
    """

    result = run_final_decision(
        "APLD",
        make_reduce_decision(),
        reconciliation=make_reduce_reconciliation(),
    )

    assert result["Final Decision"] == "REDUCE 25%"
    assert result["Reconciled Decision"] == "REDUCE"


def test_fd_final_01_justified_sell_still_works():
    """
    FD-FINAL-01 must not break an existing justified SELL path.
    """

    result = run_final_decision(
        "TESTSELL",
        make_sell_decision(),
        reconciliation=make_sell_reconciliation(),
        investment_score=19.0,
    )

    assert result["Final Decision"] == "SELL"
    assert result["Reconciled Decision"] == "SELL"


def test_fd_final_01_weak_reduce_remains_hold():
    """
    A weak REDUCE proposal must not automatically become a reduction.

    This preserves the HOLD-default philosophy.

    In this scenario the reconciliation layer explicitly returns HOLD,
    therefore the final decision must also remain HOLD.
    """

    weak_reduce = make_reduce_decision(
        score=55.0,
        evidence_score=35.0,
        evidence_strength="WEAK",
        decision_support="NOT SUPPORTED",
        confidence=42.0,
    )

    result = run_final_decision(
        "WEAKREDUCE",
        weak_reduce,
        reconciliation=make_hold_reconciliation(),
        investment_score=55.0,
    )

    assert result["Final Decision"] == "HOLD"
    assert result["Reconciled Decision"] == "HOLD"


def test_fd_final_01_hold_remains_hold():
    """A genuine HOLD must remain HOLD."""

    result = run_final_decision(
        "TESTHOLD",
        make_hold_decision(),
        reconciliation=make_hold_reconciliation(),
        investment_score=50.0,
    )

    assert result["Final Decision"] == "HOLD"
    assert result["Reconciled Decision"] == "HOLD"

