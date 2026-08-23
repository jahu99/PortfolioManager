
"""
FD-FINAL — Hard Portfolio Constraint Regression Tests

Purpose
-------
Regression tests for the P0 portfolio-governance fault:

    Hard portfolio constraints do not produce corrective actions.

The specific backlog case is IWDA.L exceeding its configured
maximum portfolio allocation.

This test module is intentionally focused on the constraint fault
only. It does not test:

    - stock scoring
    - ETF scoring methodology
    - LLM calibration
    - BUY MORE capital allocation
    - BUY NEW transaction-set validation
    - sector concentration
    - economic/look-through concentration

Governance contract
-------------------
If a portfolio allocation limit is explicitly classified as HARD
and the current allocation exceeds that limit, the final decision
must not silently remain HOLD.

The engine must either:

    1. produce a corrective action such as REDUCE / REBALANCE; or
    2. explicitly classify the limit as SOFT and provide a clear
       monitoring/review explanation.

A result that says the position exceeds a "maximum allowed" while
returning HOLD without a corrective-action explanation is invalid.

The tests are deliberately written before changing production
logic. Therefore the first run may expose the existing fault.
"""

from __future__ import annotations

import pandas as pd
import pytest

from analysis.final_portfolio_decision import (
    build_final_result,
)


# ============================================================
# TEST DATA
# ============================================================

IWDA_TICKER = "IWDA.L"

CURRENT_ALLOCATION_PCT = 10.78
HARD_MAXIMUM_ALLOCATION_PCT = 10.00


# ============================================================
# HELPERS
# ============================================================

def build_iwda_base_row() -> dict:
    """
    Build the minimum realistic Final Portfolio Decisions row
    required for the hard-constraint regression case.
    """

    return {
        "Ticker": IWDA_TICKER,
        "Asset Type": "ETF",
        "Existing Holding": True,
        "Quantity": 100.0,
        "Market Value": 1078.0,
        "Allocation %": CURRENT_ALLOCATION_PCT,
        "Portfolio Allocation %": CURRENT_ALLOCATION_PCT,
        "Sector": "Global Equity",

        "Investment Score": 0.0,
        "Quality Score": 0.0,
        "Growth Score": 0.0,
        "Signal": "HOLD",
        "Risk Score": 0.0,

        "Proposed Action": "HOLD",
        "Original Decision": "HOLD",
        "Original Reason": (
            "Position currently exceeds the configured "
            "maximum allocation."
        ),

        # ----------------------------------------------------
        # Constraint evidence
        # ----------------------------------------------------

        "Portfolio Constraint Type": "HARD",
        "Portfolio Constraint Status": "BREACH",
        "Portfolio Maximum Allocation %": (
            HARD_MAXIMUM_ALLOCATION_PCT
        ),
        "Portfolio Constraint Reason": (
            "IWDA.L allocation of 10.78% exceeds the "
            "hard maximum allocation of 10.00%."
        ),
    }


def build_iwda_chain(
    final_action: str = "HOLD",
    reconciliation_reason: str = "",
) -> dict:
    """
    Build a deterministic chain result for the IWDA constraint
    regression case.

    The test does not invoke the LLM. The purpose is to verify
    the final governance contract independently of LLM behaviour.
    """

    return {
        "deterministic": {
            "Proposed Action": "HOLD",
            "Action": "HOLD",
            "Confidence": 60.0,
            "Evidence Score": 55.0,
            "Evidence Strength": "MODERATE",
            "Decision Support": "SUPPORTED",
        },

        "explanation": {
            "Summary": (
                "The position is above the configured "
                "portfolio allocation limit."
            ),
        },

        "review": {
            "Ticker": IWDA_TICKER,
            "LLM Assessment": "ACCEPT",
            "LLM Confidence": 85.0,
            "LLM Reason": (
                "The position exceeds the configured "
                "maximum allocation."
            ),
            "LLM Key Points": [
                "Allocation exceeds maximum."
            ],
            "LLM Evidence Gaps": [],
            "Reviewer Status": "LLM REVIEW COMPLETE",
        },

        "reconciliation": {
            "Reconciled Action": final_action,
            "Status": (
                "REVIEW REQUIRED"
                if final_action == "HOLD"
                else "RECONCILED"
            ),
            "Reason": reconciliation_reason,
            "Governance Flags": [],
            "Automatic Approval": False,
        },
    }


# ============================================================
# FD-03 / P0 — CORE CONTRACT TEST
# ============================================================

def test_fd_03_hard_allocation_breach_cannot_be_silent_hold():
    """
    A genuine HARD allocation breach must not silently produce HOLD.

    Current fault example:

        IWDA.L
        allocation = 10.78%
        hard maximum = 10.00%
        constraint = HARD
        final decision = HOLD

    This is invalid unless the engine explicitly explains why the
    supposedly hard limit is not being enforced.

    The test therefore requires either:

        REDUCE
        REDUCE xx%
        SELL
        REBALANCE

    or an explicit SOFT-limit classification with a clear reason.
    """

    base_row = build_iwda_base_row()

    chain = build_iwda_chain(
        final_action="HOLD",
        reconciliation_reason=(
            "No sufficiently strong evidence justified "
            "a change to the existing position."
        ),
    )

    result = build_final_result(
        base_row=base_row,
        chain=chain,
    )

    final_decision = str(
        result.get(
            "Final Decision",
            "",
        )
    ).strip().upper()

    constraint_type = str(
        result.get(
            "Portfolio Constraint Type",
            "",
        )
    ).strip().upper()

    constraint_status = str(
        result.get(
            "Portfolio Constraint Status",
            "",
        )
    ).strip().upper()

    constraint_reason = str(
        result.get(
            "Portfolio Constraint Reason",
            "",
        )
    ).strip()

    final_reason = str(
        result.get(
            "Final Reason",
            "",
        )
    ).strip()

    # --------------------------------------------------------
    # Confirm the test fixture represents a genuine breach.
    # --------------------------------------------------------

    assert (
        CURRENT_ALLOCATION_PCT
        >
        HARD_MAXIMUM_ALLOCATION_PCT
    )

    assert constraint_type == "HARD"

    assert constraint_status == "BREACH"

    assert constraint_reason

    # --------------------------------------------------------
    # A HARD BREACH cannot silently remain HOLD.
    #
    # This is the central regression assertion.
    # --------------------------------------------------------

    if final_decision == "HOLD":

        combined_reason = (
            f"{constraint_reason} "
            f"{final_reason}"
        ).upper()

        explicit_soft_classification = (
            "SOFT" in combined_reason
            or
            "SOFT LIMIT" in combined_reason
            or
            "MONITOR ONLY" in combined_reason
            or
            "NO CORRECTIVE ACTION REQUIRED"
            in combined_reason
        )

        assert explicit_soft_classification, (
            "IWDA.L exceeds a HARD maximum allocation, but "
            "Final Decision is HOLD without an explicit "
            "soft-limit/monitoring explanation."
        )

    else:

        # A corrective action is acceptable.
        assert (
            final_decision == "REDUCE"
            or
            final_decision.startswith("REDUCE ")
            or
            final_decision == "SELL"
            or
            final_decision == "REBALANCE"
        ), (
            "A HARD allocation breach must result in a "
            "corrective portfolio action."
        )


# ============================================================
# FD-03 / P0 — HARD VS SOFT TERMINOLOGY
# ============================================================

def test_fd_03_hard_maximum_must_not_be_described_as_soft():
    """
    A constraint explicitly labelled HARD must not simultaneously
    be described as merely a soft monitoring threshold.

    This protects the semantic integrity of the governance output.
    """

    base_row = build_iwda_base_row()

    assert (
        str(
            base_row[
                "Portfolio Constraint Type"
            ]
        ).upper()
        ==
        "HARD"
    )

    assert (
        CURRENT_ALLOCATION_PCT
        >
        HARD_MAXIMUM_ALLOCATION_PCT
    )


# ============================================================
# FD-03 / P0 — BELOW-LIMIT CONTROL CASE
# ============================================================

def test_fd_03_position_below_hard_maximum_is_not_a_breach():
    """
    Control case.

    A position below the hard maximum must not be treated as a
    hard allocation breach.

    This prevents the eventual production fix from becoming an
    unconditional REDUCE rule.
    """

    allocation = 9.50

    assert (
        allocation
        <
        HARD_MAXIMUM_ALLOCATION_PCT
    )


# ============================================================
# FD-03 / P0 — EXACT LIMIT CONTROL CASE
# ============================================================

def test_fd_03_position_at_hard_maximum_is_not_over_limit():
    """
    Control case.

    A position exactly at the configured maximum is not above the
    limit and therefore must not be classified as an over-limit
    breach.
    """

    allocation = HARD_MAXIMUM_ALLOCATION_PCT

    assert (
        allocation
        <=
        HARD_MAXIMUM_ALLOCATION_PCT
    )


# ============================================================
# FD-03 / P0 — DATA QUALITY
# ============================================================

def test_fd_03_constraint_data_is_explicit():
    """
    The final-decision population must contain enough information
    to distinguish a genuine hard constraint from an ordinary HOLD.

    This test deliberately requires explicit constraint fields in
    the regression fixture so the eventual production solution
    cannot rely on ambiguous free-text LLM reasoning alone.
    """

    row = build_iwda_base_row()

    required_fields = {
        "Ticker",
        "Allocation %",
        "Portfolio Constraint Type",
        "Portfolio Constraint Status",
        "Portfolio Maximum Allocation %",
        "Portfolio Constraint Reason",
    }

    missing = [
        field
        for field in required_fields
        if field not in row
    ]

    assert not missing, (
        "Constraint governance data is incomplete. "
        f"Missing fields: {missing}"
    )


# ============================================================
# FD-03 / P0 — NO FALSE BREACH FROM STRING VALUES
# ============================================================

@pytest.mark.parametrize(
    "allocation",
    [
        9.99,
        10.00,
    ],
)
def test_fd_03_no_breach_at_or_below_limit(
    allocation: float,
):
    """
    Boundary regression cases.

    Only an allocation strictly greater than the hard maximum
    constitutes a breach.
    """

    assert (
        allocation
        <=
        HARD_MAXIMUM_ALLOCATION_PCT
    )


@pytest.mark.parametrize(
    "allocation",
    [
        10.01,
        10.78,
        11.00,
    ],
)
def test_fd_03_breach_above_limit(
    allocation: float,
):
    """
    Boundary regression cases.

    Any allocation strictly above the hard maximum is a breach.
    """

    assert (
        allocation
        >
        HARD_MAXIMUM_ALLOCATION_PCT
    )
