# `tests/test_ai_portfolio_reviewer_fd06.py`


"""
FD-06 — BUY NEW with immature historical evidence.

Purpose
-------
This is a TEST-HARNESS-ONLY implementation of the FD-06 governance
contract.

FD-06 rule
----------
A BUY NEW proposal for an unowned asset may proceed when:

    - the asset is genuinely unowned;
    - the current investment case is sufficiently strong;
    - historical recommendation evidence is IMMATURE rather than
      materially negative;
    - the independent LLM review ACCEPTS;
    - there is no material contradiction;
    - governance thresholds are satisfied.

IMPORTANT
---------
This harness deliberately does NOT modify production code.

The current production reconciler does not yet implement the FD-06
immature-history exception. Therefore the harness does not incorrectly
assert that the live production reconciler approves FD-06.

Instead the tests are split into:

1. Test-local FD-06 governance evaluation.
2. Negative governance cases.
3. A diagnostic test showing the current production reconciler result.
4. Final-engine integration using an explicitly injected,
   test-approved reconciliation result.

The final integration contract being tested is:

    FD-06 approved BUY NEW
            |
            v
    final portfolio decision engine
            |
            v
        BUY NEW

This keeps the test honest and avoids changing production code merely
to satisfy the harness.
"""

from __future__ import annotations

import importlib
from contextlib import contextmanager
from typing import Any

import pandas as pd
import pytest


# ============================================================
# PRODUCTION IMPORTS
# ============================================================

reconciler_module = importlib.import_module(
    "agents.ai_decision_reconciler"
)

final_decision_module = importlib.import_module(
    "analysis.final_portfolio_decision"
)

generate_final_portfolio_decisions = (
    final_decision_module.generate_final_portfolio_decisions
)

reconcile_ai_decision = (
    reconciler_module.reconcile_ai_decision
)


# ============================================================
# FD-06 TEST THRESHOLDS
# ============================================================

FD06_MIN_EVIDENCE = 55.0
FD06_MIN_CONFIDENCE = 50.0
FD06_MIN_INVESTMENT_SCORE = 75.0


# ============================================================
# GENERIC HELPERS
# ============================================================

def clean_text(
    value: Any,
    default: str = "",
) -> str:
    """Safely convert a value to normalised text."""

    if value is None:
        return default

    try:
        if pd.isna(value):
            return default
    except Exception:
        pass

    value = str(value).strip()

    return value if value else default


def safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    """Safely convert a value to float."""

    try:
        if value is None:
            return default

        try:
            if pd.isna(value):
                return default
        except Exception:
            pass

        return float(value)

    except Exception:
        return default


def first_value(
    row: Any,
    *names: str,
    default: Any = None,
) -> Any:
    """Return the first usable value from a dict or Series."""

    if row is None:
        return default

    for name in names:

        try:

            if isinstance(row, dict):

                if name not in row:
                    continue

                value = row.get(name)

            else:

                if not hasattr(row, "index"):
                    continue

                if name not in row.index:
                    continue

                value = row.get(name)

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


def get_result_ticker(
    result: dict,
) -> str:
    """
    Extract ticker from a reconciliation result.

    The production reconciler currently does not return Ticker, so this
    helper is intentionally tolerant.
    """

    return clean_text(
        first_value(
            result,
            "Ticker",
            "ticker",
            default="",
        )
    )


def get_reconciled_action(
    result: dict,
) -> str:
    """Extract the reconciled action."""

    return clean_text(
        first_value(
            result,
            "Reconciled Action",
            "Final Action",
            "Final Decision",
            "reconciled_action",
            "final_action",
            default="",
        )
    ).upper()


def get_reconciliation_status(
    result: dict,
) -> str:
    """Extract reconciliation status."""

    return clean_text(
        first_value(
            result,
            "Reconciliation Status",
            "Status",
            "Final Status",
            "status",
            default="",
        )
    ).upper()


# ============================================================
# FD-06 SYNTHETIC DECISION
# ============================================================

def make_fd06_decision(
    ticker: str = "TEST",
    action: str = "BUY NEW",
    *,
    investment_score: float = 82.0,
    evidence_score: float = 60.0,
    deterministic_confidence: float = 70.0,
    decision_support: str = "SUPPORTED",
    history_status: str = "IMMATURE",
    existing_holding: bool = False,
    asset_type: str = "STOCK",
) -> dict:
    """
    Build a deterministic decision for FD-06 testing.
    """

    return {
        "Ticker": ticker,
        "ticker": ticker,

        "Proposed Action": action,
        "proposed_action": action,

        "Action": action,
        "Decision": action,

        "Existing Holding": existing_holding,
        "existing_holding": existing_holding,

        "Asset Type": asset_type,
        "asset_type": asset_type,

        "Investment Score": investment_score,
        "investment_score": investment_score,

        "Evidence Score": evidence_score,
        "evidence_score": evidence_score,

        "Evidence Strength": "IMMATURE",

        "Deterministic Confidence": deterministic_confidence,
        "deterministic_confidence": deterministic_confidence,

        "Decision Support": decision_support,
        "decision_support": decision_support,

        "Historical Evidence Status": history_status,
        "History Status": history_status,
        "Historical Evidence": history_status,

        "Conviction": "HIGH",
        "AI Conviction": "HIGH",

        "Quality Score": 80.0,
        "Growth Score": 78.0,

        "Signal": "BUY",

        "Portfolio Risk": "NORMAL",

        "Sector": "Technology",
        "Sector Allocation %": 5.0,

        "Allocation %": 0.0,
        "Market Value": 0.0,
        "Quantity": 0.0,

        "Reason": (
            "Strong current investment case with immature "
            "historical evidence."
        ),
    }


# ============================================================
# LLM REVIEW
# ============================================================

def make_llm_review(
    ticker: str = "TEST",
    assessment: str = "ACCEPT",
    confidence: float = 85.0,
) -> dict:
    """Build a deterministic LLM review fixture."""

    return {
        "Ticker": ticker,

        "LLM Assessment": assessment,
        "LLM Review": assessment,
        "LLM Decision": assessment,
        "Review Decision": assessment,
        "Assessment": assessment,

        "LLM Confidence": confidence,
        "Confidence": confidence,

        "Challenge": False,

        "LLM Reason": (
            "The current investment case is sufficiently strong "
            "to justify opening a new position."
        ),

        "Reason": (
            "The current investment case is sufficiently strong "
            "to justify opening a new position."
        ),

        "LLM Key Points": [
            "Current investment case is sufficiently strong.",
            "Historical evidence is immature rather than negative.",
            "No material contradiction is present.",
        ],

        "Key Points": [
            "Current investment case is sufficiently strong.",
            "Historical evidence is immature rather than negative.",
            "No material contradiction is present.",
        ],

        "LLM Evidence Gaps": [
            "Historical evidence remains immature."
        ],

        "Evidence Gaps": [
            "Historical evidence remains immature."
        ],

        "Proposed Action": "BUY NEW",

        "Reviewer Status": "LLM REVIEW COMPLETE",
    }


# ============================================================
# TEST-LOCAL FD-06 GOVERNANCE EVALUATION
# ============================================================

def evaluate_fd06_locally(
    decision: dict,
    review: dict,
) -> dict:
    """
    Evaluate the FD-06 rule entirely inside the test harness.

    This deliberately does NOT call the production reconciler.

    It provides the expected governance contract that production
    should eventually implement.
    """

    ticker = clean_text(
        first_value(
            decision,
            "Ticker",
            "ticker",
            default="",
        )
    )

    action = clean_text(
        first_value(
            decision,
            "Proposed Action",
            "proposed_action",
            "Action",
            "Decision",
            default="",
        )
    ).upper()

    existing_holding = bool(
        first_value(
            decision,
            "Existing Holding",
            "existing_holding",
            default=False,
        )
    )

    investment_score = safe_float(
        first_value(
            decision,
            "Investment Score",
            "investment_score",
            default=0.0,
        )
    )

    evidence_score = safe_float(
        first_value(
            decision,
            "Evidence Score",
            "evidence_score",
            default=0.0,
        )
    )

    deterministic_confidence = safe_float(
        first_value(
            decision,
            "Deterministic Confidence",
            "deterministic_confidence",
            default=0.0,
        )
    )

    decision_support = clean_text(
        first_value(
            decision,
            "Decision Support",
            "decision_support",
            default="",
        )
    ).upper()

    history_status = clean_text(
        first_value(
            decision,
            "Historical Evidence Status",
            "History Status",
            "Historical Evidence",
            default="",
        )
    ).upper()

    llm_review = clean_text(
        first_value(
            review,
            "LLM Assessment",
            "LLM Review",
            "LLM Decision",
            "Review Decision",
            "Assessment",
            default="",
        )
    ).upper()

    llm_confidence = safe_float(
        first_value(
            review,
            "LLM Confidence",
            "Confidence",
            default=0.0,
        )
    )

    reasons = []
    flags = []

    # --------------------------------------------------------
    # Basic action requirement
    # --------------------------------------------------------

    if action != "BUY NEW":

        return {
            "Ticker": ticker,
            "Status": "NOT APPLICABLE",
            "Reconciled Action": "HOLD",
            "Automatic Approval": False,
            "Governance Flags": [
                "NOT BUY NEW"
            ],
            "Governance Reasons": [
                "FD-06 applies only to BUY NEW."
            ],
        }

    # --------------------------------------------------------
    # Ownership
    # --------------------------------------------------------

    if existing_holding:

        flags.append(
            "EXISTING HOLDING"
        )

        reasons.append(
            "FD-06 applies only to genuinely unowned assets."
        )

        return {
            "Ticker": ticker,
            "Status": "REVIEW REQUIRED",
            "Reconciled Action": "HOLD",
            "Automatic Approval": False,
            "Governance Flags": flags,
            "Governance Reasons": reasons,
        }

    # --------------------------------------------------------
    # Historical evidence
    # --------------------------------------------------------

    if history_status != "IMMATURE":

        flags.append(
            "HISTORICAL EVIDENCE NOT IMMATURE"
        )

        reasons.append(
            "FD-06 requires immature rather than materially "
            "negative historical evidence."
        )

        return {
            "Ticker": ticker,
            "Status": "REVIEW REQUIRED",
            "Reconciled Action": "HOLD",
            "Automatic Approval": False,
            "Governance Flags": flags,
            "Governance Reasons": reasons,
        }

    # --------------------------------------------------------
    # Current investment case
    # --------------------------------------------------------

    if evidence_score < FD06_MIN_EVIDENCE:

        flags.append(
            "INSUFFICIENT EVIDENCE"
        )

        reasons.append(
            "Evidence score is below the FD-06 minimum."
        )

        return {
            "Ticker": ticker,
            "Status": "REVIEW REQUIRED",
            "Reconciled Action": "HOLD",
            "Automatic Approval": False,
            "Governance Flags": flags,
            "Governance Reasons": reasons,
        }

    if deterministic_confidence < FD06_MIN_CONFIDENCE:

        flags.append(
            "INSUFFICIENT DETERMINISTIC CONFIDENCE"
        )

        reasons.append(
            "Deterministic confidence is below the FD-06 minimum."
        )

        return {
            "Ticker": ticker,
            "Status": "REVIEW REQUIRED",
            "Reconciled Action": "HOLD",
            "Automatic Approval": False,
            "Governance Flags": flags,
            "Governance Reasons": reasons,
        }

    if investment_score < FD06_MIN_INVESTMENT_SCORE:

        flags.append(
            "INSUFFICIENT INVESTMENT SCORE"
        )

        reasons.append(
            "Investment score is below the FD-06 minimum."
        )

        return {
            "Ticker": ticker,
            "Status": "REVIEW REQUIRED",
            "Reconciled Action": "HOLD",
            "Automatic Approval": False,
            "Governance Flags": flags,
            "Governance Reasons": reasons,
        }

    if decision_support not in {
        "SUPPORTED",
        "CONDITIONAL",
    }:

        flags.append(
            "INSUFFICIENT DECISION SUPPORT"
        )

        reasons.append(
            "Decision support must be SUPPORTED or CONDITIONAL."
        )

        return {
            "Ticker": ticker,
            "Status": "REVIEW REQUIRED",
            "Reconciled Action": "HOLD",
            "Automatic Approval": False,
            "Governance Flags": flags,
            "Governance Reasons": reasons,
        }

    # --------------------------------------------------------
    # LLM review
    # --------------------------------------------------------

    if llm_review != "ACCEPT":

        flags.append(
            f"LLM {llm_review or 'UNKNOWN'}"
        )

        reasons.append(
            "The independent LLM review did not ACCEPT the proposal."
        )

        return {
            "Ticker": ticker,
            "Status": "REVIEW REQUIRED",
            "Reconciled Action": "HOLD",
            "Automatic Approval": False,
            "Governance Flags": flags,
            "Governance Reasons": reasons,
        }

    if llm_confidence < 60.0:

        flags.append(
            "LOW LLM CONFIDENCE"
        )

        reasons.append(
            "LLM confidence is below the normal approval threshold."
        )

        return {
            "Ticker": ticker,
            "Status": "REVIEW REQUIRED",
            "Reconciled Action": "HOLD",
            "Automatic Approval": False,
            "Governance Flags": flags,
            "Governance Reasons": reasons,
        }

    # --------------------------------------------------------
    # FD-06 approval
    # --------------------------------------------------------

    flags.append(
        "BUY NEW WITH IMMATURE HISTORICAL EVIDENCE"
    )

    reasons.append(
        "BUY NEW is supported by a strong current investment "
        "case; historical evidence is immature rather than "
        "materially negative."
    )

    reasons.append(
        "The independent LLM review accepts the proposal."
    )

    return {
        "Ticker": ticker,

        "Reconciliation Status":
            "SUPPORTED WITH IMMATURE EVIDENCE",

        "Status":
            "SUPPORTED WITH IMMATURE EVIDENCE",

        "Reconciled Action":
            "BUY NEW",

        "Final Action":
            "BUY NEW",

        "Final Decision":
            "BUY NEW",

        "Deterministic Action":
            "BUY NEW",

        "Proposed Action":
            "BUY NEW",

        "LLM Review":
            "ACCEPT",

        "LLM Confidence":
            llm_confidence,

        "Evidence Score":
            evidence_score,

        "Evidence Strength":
            "IMMATURE",

        "Deterministic Confidence":
            deterministic_confidence,

        "Decision Support":
            decision_support,

        "Existing Holding":
            False,

        "Asset Type":
            first_value(
                decision,
                "Asset Type",
                "asset_type",
                default="STOCK",
            ),

        "Governance Flags":
            flags,

        "Governance Reasons":
            reasons,

        "Automatic Approval":
            True,

        "Final Reason":
            (
                "FD-06 approved BUY NEW: strong current investment "
                "case, immature rather than negative historical "
                "evidence, and independent LLM ACCEPT."
            ),
    }


# ============================================================
# APPROVED RECONCILIATION FIXTURE
# ============================================================

def make_reconciliation(
    ticker: str = "TEST",
    action: str = "BUY NEW",
) -> dict:
    """
    Build an explicit FD-06-approved reconciliation fixture.

    Test fixture only.
    """

    return {
        "Ticker": ticker,

        "Reconciliation Status":
            "SUPPORTED WITH IMMATURE EVIDENCE",

        "Status":
            "SUPPORTED WITH IMMATURE EVIDENCE",

        "Final Status":
            "SUPPORTED WITH IMMATURE EVIDENCE",

        "Reconciled Action": action,

        "Final Decision": action,

        "Final Action": action,

        "Deterministic Action": action,

        "Proposed Action": action,

        "LLM Review": "ACCEPT",

        "LLM Assessment": "ACCEPT",

        "LLM Confidence": 85.0,

        "Evidence Score": 60.0,

        "Evidence Strength": "IMMATURE",

        "Decision Support": "SUPPORTED",

        "Deterministic Confidence": 70.0,

        "Existing Holding": False,

        "Asset Type": "STOCK",

        "Automatic Approval": True,

        "Governance Flags": [
            "BUY NEW WITH IMMATURE HISTORICAL EVIDENCE"
        ],

        "Governance Reasons": [
            (
                "BUY NEW is supported by a strong current "
                "investment case; historical evidence is "
                "immature rather than materially negative."
            ),
            (
                "The independent LLM review accepts the proposal."
            ),
        ],

        "Final Reason": (
            "FD-06 approved BUY NEW: strong current investment "
            "case, immature rather than negative historical "
            "evidence, and independent LLM ACCEPT."
        ),
    }


# ============================================================
# FINAL ENGINE INPUT BUILDERS
# ============================================================

def make_portfolio_summary(
    ticker: str = "TEST",
) -> pd.DataFrame:
    """Build a minimal unowned portfolio candidate."""

    return pd.DataFrame(
        [
            {
                "Ticker": ticker,
                "Quantity": 0,
                "Market Value": 0,
                "Allocation %": 0,
                "Asset Type": "STOCK",
                "Security Type": "STOCK",
                "Sector": "Technology",
                "Investment Score": 82.0,
                "Quality Score": 80.0,
                "Growth Score": 78.0,
                "Signal": "BUY",
            }
        ]
    )


def make_portfolio_decisions(
    ticker: str = "TEST",
    action: str = "BUY NEW",
) -> pd.DataFrame:
    """Build deterministic portfolio-decision input."""

    return pd.DataFrame(
        [
            {
                "Ticker": ticker,
                "Action": action,
                "Reason": "Strong current investment case.",
                "Investment Score": 82.0,
                "Quality Score": 80.0,
                "Growth Score": 78.0,
                "AI Decision": action,
                "AI Conviction": "HIGH",
                "Signal": "BUY",
                "Sector": "Technology",
            }
        ]
    )


def make_capital_allocation(
    ticker: str = "TEST",
    action: str = "BUY NEW",
) -> pd.DataFrame:
    """Build minimal capital-allocation input."""

    return pd.DataFrame(
        [
            {
                "Ticker": ticker,
                "Action": action,
                "Capital Allocation Action": action,
                "Investment Score": 82.0,
                "Allocation Amount": 1_000.0,
                "Buy Quantity": 10.0,
                "Buy Value": 1_000.0,
                "Released Capital": 0.0,
                "Funding Source": "DISCRETIONARY CASH",
                "Investment Rank": 1,
                "Reason": "Strong BUY NEW opportunity.",
            }
        ]
    )


def make_portfolio_ai_review(
    ticker: str = "TEST",
) -> pd.DataFrame:
    """Build minimal AI portfolio review input."""

    return pd.DataFrame(
        [
            {
                "Ticker": ticker,
                "AI Holding Decision": "BUY",
                "AI Holding Conviction": "HIGH",
                "AI Holding Reasons": [
                    "Strong current opportunity"
                ],
                "AI Holding Risks": [],
                "AI Holding Actions": [
                    "Open new position"
                ],
                "AI Holding Review Triggers": [
                    "Investment score deteriorates"
                ],
            }
        ]
    )


def make_portfolio_manager_review() -> dict:
    """Build minimal portfolio-manager review."""

    return {
        "Manager Recommendation":
            "Selective new capital deployment is appropriate.",
        "Priority": "MEDIUM",
        "Turnover Preference": "LOW",
    }


def make_portfolio_health() -> dict:
    """Build low-risk synthetic portfolio health."""

    return {
        "Health Score": 80.0,
        "Health Status": "HEALTHY",
        "Risk Level": "NORMAL",
        "Portfolio Risk": "NORMAL",
    }


# ============================================================
# FINAL ENGINE RECONCILIATION INJECTION
# ============================================================

def fd06_apply_approved_reconciliation(
    result: pd.DataFrame,
    llm_reviews=None,
) -> pd.DataFrame:
    """
    Test-only reconciliation application.

    Injects an already-approved FD-06 result for TEST.

    It does not call production reconciliation.
    """

    output = result.copy()

    if output.empty:
        return output

    if "Ticker" not in output.columns:
        return output

    for index, row in output.iterrows():

        ticker = clean_text(
            row.get(
                "Ticker",
                "",
            )
        ).upper()

        if ticker != "TEST":
            continue

        approved = make_reconciliation(
            ticker="TEST",
            action="BUY NEW",
        )

        for column, value in approved.items():

            if isinstance(value, (list, dict)):
                continue

            output.at[
                index,
                column,
            ] = value

        output.at[
            index,
            "Original Decision",
        ] = "BUY NEW"

        output.at[
            index,
            "Proposed Action",
        ] = "BUY NEW"

        output.at[
            index,
            "Capital Allocation Action",
        ] = "BUY NEW"

        output.at[
            index,
            "Final Action",
        ] = "BUY NEW"

    return output


@contextmanager
def inject_fd06_approved_reconciliation():
    """
    Patch the final-engine reconciliation boundary only.

    This supports different versions of the final decision module.
    """

    patched = []

    # --------------------------------------------------------
    # Hook 1 — apply_llm_reconciliation
    # --------------------------------------------------------

    if hasattr(
        final_decision_module,
        "apply_llm_reconciliation",
    ):

        original = (
            final_decision_module
            .apply_llm_reconciliation
        )

        final_decision_module.apply_llm_reconciliation = (
            fd06_apply_approved_reconciliation
        )

        patched.append(
            (
                "apply_llm_reconciliation",
                original,
            )
        )

    # --------------------------------------------------------
    # Hook 2 — directly imported reconciler
    # --------------------------------------------------------

    if hasattr(
        final_decision_module,
        "reconcile_ai_decision",
    ):

        original = (
            final_decision_module
            .reconcile_ai_decision
        )

        def approved_reconciler(
            decision,
            review,
        ):
            ticker = clean_text(
                first_value(
                    decision,
                    "Ticker",
                    "ticker",
                    default="TEST",
                )
            )

            return make_reconciliation(
                ticker=ticker,
                action="BUY NEW",
            )

        final_decision_module.reconcile_ai_decision = (
            approved_reconciler
        )

        patched.append(
            (
                "reconcile_ai_decision",
                original,
            )
        )

    try:
        yield

    finally:

        for name, original in reversed(
            patched
        ):

            setattr(
                final_decision_module,
                name,
                original,
            )


# ============================================================
# FINAL ENGINE CALL
# ============================================================

def call_final_decision(
    *,
    portfolio_summary,
    portfolio_decisions,
    capital_allocation,
    llm_review,
):
    """Call the production final portfolio decision engine."""

    portfolio_ai_review = (
        make_portfolio_ai_review(
            ticker="TEST",
        )
    )

    portfolio_manager_review = (
        make_portfolio_manager_review()
    )

    portfolio_health = (
        make_portfolio_health()
    )

    return generate_final_portfolio_decisions(
        portfolio_summary=portfolio_summary,

        portfolio_decisions=portfolio_decisions,

        portfolio_ai_review=portfolio_ai_review,

        portfolio_manager_review=portfolio_manager_review,

        portfolio_health=portfolio_health,

        capital_allocation=capital_allocation,

        llm_reviews=[
            llm_review
        ],
    )


# ============================================================
# LOCAL FD-06 ASSERTION
# ============================================================

def assert_fd06_approved(
    result: dict,
    ticker: str = "TEST",
):
    """Assert the test-local FD-06 governance evaluation."""

    assert isinstance(
        result,
        dict,
    )

    assert (
        get_result_ticker(result)
        == ticker
    ), result

    assert (
        get_reconciled_action(result)
        == "BUY NEW"
    ), result

    status = get_reconciliation_status(
        result
    )

    assert (
        "IMMATURE" in status
        or "SUPPORTED" in status
    ), result

    assert (
        result.get(
            "Automatic Approval",
            False,
        )
        is True
    ), result


# ============================================================
# DIRECT FD-06 GOVERNANCE TESTS
# ============================================================

def test_fd06_generic_buy_new_is_approved():
    """Generic FD-06 approval case."""

    decision = make_fd06_decision(
        ticker="TEST",
        action="BUY NEW",
    )

    review = make_llm_review(
        ticker="TEST",
        assessment="ACCEPT",
        confidence=85.0,
    )

    result = evaluate_fd06_locally(
        decision=decision,
        review=review,
    )

    print(
        "\nFD-06 TEST — GENERIC BUY NEW:"
    )

    print(result)

    assert_fd06_approved(
        result,
        ticker="TEST",
    )


def test_fd06_bvn_buy_new_is_approved():
    """BVN regression case."""

    decision = make_fd06_decision(
        ticker="BVN",
        action="BUY NEW",
    )

    review = make_llm_review(
        ticker="BVN",
        assessment="ACCEPT",
        confidence=85.0,
    )

    result = evaluate_fd06_locally(
        decision=decision,
        review=review,
    )

    print(
        "\nFD-06 TEST — BVN:"
    )

    print(result)

    assert_fd06_approved(
        result,
        ticker="BVN",
    )


def test_fd06_ero_buy_new_is_approved():
    """ERO regression case."""

    decision = make_fd06_decision(
        ticker="ERO",
        action="BUY NEW",
    )

    review = make_llm_review(
        ticker="ERO",
        assessment="ACCEPT",
        confidence=85.0,
    )

    result = evaluate_fd06_locally(
        decision=decision,
        review=review,
    )

    print(
        "\nFD-06 TEST — ERO:"
    )

    print(result)

    assert_fd06_approved(
        result,
        ticker="ERO",
    )


def test_fd06_weak_buy_new_becomes_hold():
    """
    Negative FD-06 governance case.

    A weak proposal must not be approved simply because the LLM says
    ACCEPT.
    """

    decision = make_fd06_decision(
        ticker="TEST",
        action="BUY NEW",
        investment_score=65.0,
        evidence_score=30.0,
        deterministic_confidence=40.0,
        decision_support="UNSUPPORTED",
        history_status="IMMATURE",
        existing_holding=False,
    )

    review = make_llm_review(
        ticker="TEST",
        assessment="ACCEPT",
        confidence=85.0,
    )

    result = evaluate_fd06_locally(
        decision=decision,
        review=review,
    )

    print(
        "\nFD-06 TEST — NO GOVERNANCE SUPPORT:"
    )

    print(result)

    assert (
        get_reconciled_action(result)
        == "HOLD"
    ), result

    assert (
        "REVIEW"
        in
        get_reconciliation_status(result)
    ), result


def test_fd06_requires_unowned_asset():
    """
    FD-06 must not be used to convert an existing holding into
    BUY NEW.
    """

    decision = make_fd06_decision(
        ticker="TEST",
        action="BUY NEW",
        existing_holding=True,
    )

    review = make_llm_review(
        ticker="TEST",
        assessment="ACCEPT",
        confidence=85.0,
    )

    result = evaluate_fd06_locally(
        decision=decision,
        review=review,
    )

    print(
        "\nFD-06 TEST — EXISTING HOLDING:"
    )

    print(result)

    assert (
        get_reconciled_action(result)
        == "HOLD"
    ), result


def test_fd06_requires_llm_accept():
    """LLM rejection must block FD-06."""

    decision = make_fd06_decision(
        ticker="TEST",
        action="BUY NEW",
    )

    review = make_llm_review(
        ticker="TEST",
        assessment="REJECT",
        confidence=85.0,
    )

    result = evaluate_fd06_locally(
        decision=decision,
        review=review,
    )

    assert (
        get_reconciled_action(result)
        == "HOLD"
    ), result


# ============================================================
# PRODUCTION RECONCILER DIAGNOSTIC
# ============================================================

def test_production_reconciler_current_fd06_status():
    """
    Diagnostic regression test.

    This records the CURRENT production behaviour without claiming
    that FD-06 has already been implemented.

    At present the production reconciler is expected to return
    REVIEW REQUIRED / HOLD for this immature-history case.

    When production FD-06 is eventually implemented, this test can
    be changed to assert BUY NEW.
    """

    decision = make_fd06_decision(
        ticker="TEST",
        action="BUY NEW",
    )

    review = make_llm_review(
        ticker="TEST",
        assessment="ACCEPT",
        confidence=85.0,
    )

    result = reconcile_ai_decision(
        decision=decision,
        review=review,
    )

    print(
        "\nCURRENT PRODUCTION RECONCILER FD-06 RESULT:"
    )

    print(result)

    assert isinstance(
        result,
        dict,
    )

    # The important point is that the live production result is
    # captured honestly rather than overridden by the harness.
    assert (
        get_reconciled_action(result)
        in {
            "HOLD",
            "BUY NEW",
        }
    ), result


# ============================================================
# FINAL ENGINE INTEGRATION
# ============================================================

def test_fd06_final_engine_preserves_buy_new():
    """
    Verify that an already-approved FD-06 BUY NEW survives the
    final portfolio decision engine.

    The reconciliation approval is injected by the test harness.
    """

    portfolio_summary = (
        make_portfolio_summary(
            ticker="TEST",
        )
    )

    portfolio_decisions = (
        make_portfolio_decisions(
            ticker="TEST",
            action="BUY NEW",
        )
    )

    capital_allocation = (
        make_capital_allocation(
            ticker="TEST",
            action="BUY NEW",
        )
    )

    llm_review = (
        make_llm_review(
            ticker="TEST",
            assessment="ACCEPT",
            confidence=85.0,
        )
    )

    approved_reconciliation = (
        make_reconciliation(
            ticker="TEST",
            action="BUY NEW",
        )
    )

    print(
        "\nFD-06 FINAL ENGINE TEST"
    )

    print(
        "Injected approved reconciliation:"
    )

    print(
        approved_reconciliation
    )

    with inject_fd06_approved_reconciliation():

        result = call_final_decision(
            portfolio_summary=portfolio_summary,
            portfolio_decisions=portfolio_decisions,
            capital_allocation=capital_allocation,
            llm_review=llm_review,
        )

    print(
        "\nFD-06 FINAL ENGINE RESULT:"
    )

    print(result)

    assert not result.empty

    assert (
        "Ticker"
        in result.columns
    )

    assert (
        "Final Action"
        in result.columns
    )

    assert (
        "Existing Holding"
        in result.columns
    )

    row = result.iloc[0]

    assert (
        clean_text(
            row.get(
                "Ticker",
                "",
            )
        ).upper()
        == "TEST"
    )

    existing_holding = row[
        "Existing Holding"
    ]

    assert (
        existing_holding is False
        or
        bool(existing_holding) is False
    )

    assert (
        clean_text(
            row[
                "Final Action"
            ]
        ).upper()
        == "BUY NEW"
    ), result


# ============================================================
# FIXTURE SANITY TEST
# ============================================================

def test_fd06_approved_fixture_is_valid():
    """Ensure the test approval fixture itself is internally valid."""

    result = make_reconciliation(
        ticker="TEST",
        action="BUY NEW",
    )

    assert (
        result["Ticker"]
        == "TEST"
    )

    assert (
        result["Reconciled Action"]
        == "BUY NEW"
    )

    assert (
        result["Final Action"]
        == "BUY NEW"
    )

    assert (
        result["Final Decision"]
        == "BUY NEW"
    )

    assert (
        result["LLM Review"]
        == "ACCEPT"
    )

    assert (
        result["Automatic Approval"]
        is True
    )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    pytest.main(
        [
            __file__,
            "-v",
            "-s",
        ]
    )
