
"""
AEM.L AI Decision Reconciler Regression Tests

Purpose
-------
Protect the governance behaviour for REDUCE decisions, particularly
the justified REDUCE exception when the independent LLM challenges
the deterministic proposal.

These tests are intentionally focused on the reconciliation layer.
They do not test capital allocation or the downstream final decision
gate.
"""

from agents.ai_decision_reconciler import reconcile_ai_decision


def make_decision(
    *,
    investment_score=39.0,
    evidence_score=67.41,
    confidence=68.74,
    decision_support="SUPPORTED",
    signal="SELL",
    existing_holding=True,
):
    """Create a deterministic AEM.L-style REDUCE decision."""

    return {
        "Ticker": "AEM.L",
        "Final Decision": "REDUCE 25%",
        "Proposed Action": "REDUCE 25%",
        "Action": "REDUCE 25%",
        "Investment Score": investment_score,
        "Evidence Score": evidence_score,
        "Evidence Strength": "STRONG",
        "Decision Support": decision_support,
        "Confidence": confidence,
        "Existing Holding": existing_holding,
        "Asset Type": "STOCK",
        "Signal": signal,
    }


def test_buy_more_deterministic_confidence_field_is_respected():
    """
    Regression test for the deterministic-confidence field-name bug.

    The reconciler must read the explicit "Deterministic Confidence"
    field when evaluating BUY MORE governance.

    A fully qualified BUY MORE must therefore be automatically
    approved rather than incorrectly downgraded to HOLD.
    """

    decision = {
        "Ticker": "TGTX",
        "Final Decision": "BUY MORE",
        "Proposed Action": "BUY MORE",
        "Action": "BUY MORE",
        "Existing Holding": True,
        "Investment Score": 88.0,
        "Evidence Score": 70.0,
        "Deterministic Confidence": 85.0,
        "Evidence Strength": "STRONG",
        "Decision Support": "SUPPORTED",
        "Signal": "STRONG BUY",
        "Allocation %": 0.0,
        "Asset Type": "STOCK",
    }

    review = {
        "Review Decision": "ACCEPT",
        "LLM Decision": "ACCEPT",
        "LLM Assessment": "ACCEPT",
        "LLM Confidence": 85.0,
        "Challenge": False,
        "Reviewer Status": "LLM REVIEW COMPLETE",
    }

    result = reconcile_ai_decision(
        decision=decision,
        review=review,
    )

    assert result["Deterministic Confidence"] == 85.0
    assert result["Reconciled Action"] == "BUY MORE"
    assert result["Reconciliation Status"] == "SUPPORTED"
    assert result["Automatic Approval"] is True
    assert result["Governance Reason Code"] == "QUALIFIED_BUY_MORE"


def make_review(
    *,
    decision="ACCEPT",
    confidence=85.0,
    challenge=False,
):
    """Create an independent LLM review."""

    return {
        "Review Decision": decision,
        "LLM Decision": decision,
        "LLM Assessment": decision,
        "LLM Confidence": confidence,
        "Challenge": challenge,
        "Reviewer Status": "LLM REVIEW COMPLETE",
    }


def test_aeml_reduce_llm_accept_is_supported():
    """
    A justified REDUCE with LLM ACCEPT should be automatically
    approved.
    """

    result = reconcile_ai_decision(
        decision=make_decision(),
        review=make_review(
            decision="ACCEPT",
            challenge=False,
        ),
    )

    assert result["Reconciled Action"] == "REDUCE"
    assert result["Reconciliation Status"] == "SUPPORTED"
    assert result["Automatic Approval"] is True


def test_aeml_reduce_llm_challenge_strong_exception_is_supported():
    """
    A justified REDUCE should survive an LLM challenge when the
    dedicated strong-reduction criteria are satisfied.

    This is the regression test for the bug fixed in the reconciler.
    """

    result = reconcile_ai_decision(
        decision=make_decision(
            investment_score=39.0,
            evidence_score=67.41,
            confidence=68.74,
            decision_support="SUPPORTED",
            signal="SELL",
            existing_holding=True,
        ),
        review=make_review(
            decision="CHALLENGE",
            confidence=85.0,
            challenge=True,
        ),
    )

    assert result["Reconciled Action"] == "REDUCE"
    assert (
        result["Reconciliation Status"]
        == "SUPPORTED WITH CHALLENGE"
    )
    assert result["Automatic Approval"] is True


def test_reduce_llm_challenge_weak_evidence_is_blocked():
    """
    An LLM-challenged REDUCE must still be blocked when the
    dedicated reduction criteria are not satisfied.
    """

    result = reconcile_ai_decision(
        decision=make_decision(
            investment_score=55.0,
            evidence_score=64.0,
            confidence=64.0,
            decision_support="SUPPORTED",
            signal="HOLD",
            existing_holding=True,
        ),
        review=make_review(
            decision="CHALLENGE",
            confidence=85.0,
            challenge=True,
        ),
    )

    assert result["Reconciled Action"] == "HOLD"
    assert result["Reconciliation Status"] == "REVIEW REQUIRED"
    assert result["Automatic Approval"] is False


def test_reduce_llm_reject_is_blocked():
    """
    Explicit LLM rejection must prevent automatic REDUCE approval.
    """

    result = reconcile_ai_decision(
        decision=make_decision(),
        review=make_review(
            decision="REJECT",
            confidence=85.0,
            challenge=True,
        ),
    )

    assert result["Reconciled Action"] == "HOLD"
    assert result["Reconciliation Status"] == "REVIEW REQUIRED"
    assert result["Automatic Approval"] is False


def test_buy_more_llm_challenge_is_blocked():
    """
    BUY MORE remains subject to additional protection when the
    independent reviewer challenges the proposal.
    """

    decision = make_decision(
        investment_score=85.0,
        evidence_score=85.0,
        confidence=85.0,
        decision_support="SUPPORTED",
        signal="BUY",
        existing_holding=True,
    )

    decision["Final Decision"] = "BUY MORE"
    decision["Proposed Action"] = "BUY MORE"
    decision["Action"] = "BUY MORE"

    result = reconcile_ai_decision(
        decision=decision,
        review=make_review(
            decision="CHALLENGE",
            confidence=85.0,
            challenge=True,
        ),
    )

    assert result["Reconciled Action"] == "HOLD"
    assert result["Reconciliation Status"] == "REVIEW REQUIRED"
    assert result["Automatic Approval"] is False


def test_sell_with_insufficient_evidence_is_blocked():
    """
    SELL requires stronger evidence than REDUCE.
    """

    decision = make_decision(
        investment_score=20.0,
        evidence_score=75.0,
        confidence=80.0,
        decision_support="SUPPORTED",
        signal="STRONG SELL",
        existing_holding=True,
    )

    decision["Final Decision"] = "SELL"
    decision["Proposed Action"] = "SELL"
    decision["Action"] = "SELL"

    result = reconcile_ai_decision(
        decision=decision,
        review=make_review(
            decision="ACCEPT",
            confidence=85.0,
            challenge=False,
        ),
    )

    assert result["Reconciled Action"] == "HOLD"
    assert result["Reconciliation Status"] == "REVIEW REQUIRED"
    assert result["Automatic Approval"] is False


def test_hold_llm_accept_is_supported():
    """
    HOLD remains the safe default and can be supported by the
    independent reviewer.
    """

    decision = make_decision()

    decision["Final Decision"] = "HOLD"
    decision["Proposed Action"] = "HOLD"
    decision["Action"] = "HOLD"

    result = reconcile_ai_decision(
        decision=decision,
        review=make_review(
            decision="ACCEPT",
            confidence=85.0,
            challenge=False,
        ),
    )

    assert result["Reconciled Action"] == "HOLD"
    assert result["Reconciliation Status"] == "SUPPORTED"
    assert result["Automatic Approval"] is True


def test_missing_llm_review_is_conservative():
    """
    Missing LLM review must never become automatic approval for a
    non-HOLD action.
    """

    result = reconcile_ai_decision(
        decision=make_decision(),
        review={},
    )

    assert result["Reconciled Action"] == "HOLD"
    assert result["Reconciliation Status"] == "REVIEW REQUIRED"
    assert result["Automatic Approval"] is False

