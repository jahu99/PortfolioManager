"""
Governance Audit Harness
========================

Purpose
-------
Exercise the production audit persistence path for governed portfolio
decisions where governance and/or the independent AI review causes a
recommendation to be retained, changed, or rejected.

This is an integration-style test harness rather than a unit test.

It deliberately uses controlled decision-chain data so that we can test
the audit database independently of the live portfolio calculation,
market data, and LLM.

The harness:

1. Creates an audit run.
2. Creates several controlled decision scenarios.
3. Persists each scenario using the real record_decision_audit() function.
4. Queries audit_decisions and audit_reasons.
5. Verifies that governance changes and their reasons were recorded.
6. Leaves the records in portfolio_manager.db so they can be inspected
   manually with sqlite3.

Run from the project root:

    python tests/test_governance_audit_harness.py

The test intentionally writes to:

    data/portfolio_manager.db
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from typing import Any


# ============================================================
# PROJECT PATH
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# PRODUCTION AUDIT FUNCTION
# ============================================================

from analysis.audit import record_decision_audit


# ============================================================
# DATABASE
# ============================================================

DATABASE_PATH = (
    PROJECT_ROOT
    / "data"
    / "portfolio_manager.db"
)


# ============================================================
# ASSERTION HELPERS
# ============================================================


def assert_equal(
    actual: Any,
    expected: Any,
    message: str,
) -> None:
    """Raise a useful assertion error."""
    if actual != expected:
        raise AssertionError(
            f"{message}\n"
            f"Expected: {expected!r}\n"
            f"Actual:   {actual!r}"
        )


def assert_true(
    condition: bool,
    message: str,
) -> None:
    """Raise a useful assertion error."""
    if not condition:
        raise AssertionError(message)


# ============================================================
# DATABASE HELPERS
# ============================================================


def create_audit_run(conn):
    """
    Create a test audit run using the actual audit_runs schema.

    The audit_runs table requires a unique run_id, run_date,
    environment, status and created_at.
    """
    from datetime import datetime, timezone
    from uuid import uuid4

    now = datetime.now(timezone.utc).isoformat()
    run_id = f"governance-audit-test-{uuid4().hex}"

    cursor = conn.execute(
        """
        INSERT INTO audit_runs (
            run_id,
            run_date,
            environment,
            code_version,
            status,
            total_decisions,
            changed_decisions,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            now,
            "pre-production",
            "test_governance_audit_harness",
            "RUNNING",
            0,
            0,
            now,
        ),
    )

    conn.commit()

    return int(cursor.lastrowid)

def complete_audit_run(
    conn: sqlite3.Connection,
    audit_run_id: int,
) -> None:
    """
    Mark the audit run as completed where the current schema supports it.
    """

    columns = conn.execute(
        "PRAGMA table_info(audit_runs)"
    ).fetchall()

    column_names = {
        str(row[1])
        for row in columns
    }

    updates: dict[str, Any] = {}

    if "status" in column_names:
        updates["status"] = "COMPLETED"

    if not updates:
        return

    assignments = ", ".join(
        f"{column} = ?"
        for column in updates
    )

    conn.execute(
        f"""
        UPDATE audit_runs
        SET {assignments}
        WHERE id = ?
        """,
        (
            *updates.values(),
            audit_run_id,
        ),
    )

    conn.commit()


# ============================================================
# CONTROLLED DECISION SCENARIOS
# ============================================================


def build_buy_more_governance_scenario() -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
]:
    """
    BUY MORE -> HOLD because dedicated BUY MORE governance fails.

    This represents an existing holding where the recommendation is
    BUY MORE but governance prevents the capital allocation change.
    """

    base_row = {
        "Ticker": "NVDA",
        "Asset Type": "Stock",
        "Original Action": "BUY MORE",
        "Proposed Action": "BUY MORE",
        "Signal": "BUY",
        "Investment Score": 78,
        "Technical Score": 68,
        "Quality Score": 80,
        "Growth Score": 78,
        "Confidence Score": 62,
        "Evidence Score": 72,
        "Allocation %": 4.0,
        "Maximum Allocation %": 5.0,
    }

    chain = {
        "deterministic": {
            "Evidence Assessment": {
                "Evidence Score": 72,
                "Decision Support": "SUPPORTED",
                "Historical Signal Reliability": "RELIABLE",
                "Historical Signal Observations": 50,
            },
            "Confidence": 62,
            "Proposed Action": "BUY MORE",
        },
        "explanation": {},
        "review": {
            "Review Decision": "ACCEPT",
            "LLM Confidence": 78,
            "Challenge": False,
            "LLM Reason": (
                "The proposal is reasonable but the "
                "governance constraints remain applicable."
            ),
        },
        "reconciliation": {
            "Status": "CHALLENGE",
            "Reconciled Action": "HOLD",

            "Governance Flags": [
                "BUY MORE GOVERNANCE REQUIREMENTS NOT MET",
                "Deterministic confidence too low",
            ],

            "Governance Reasons": [
                (
                    "BUY MORE did not satisfy one or more "
                    "of the dedicated governance requirements."
                ),
                (
                    "BUY MORE was not approved because "
                    "deterministic confidence was too low."
                ),
            ],

            "Governance Failed Checks": [
                {
                    "check_def": (
                        "_buy_more_is_strong_enough_for_automatic_approval"
                    ),
                    "check_code": (
                        "BUY_MORE_DETERMINISTIC_CONFIDENCE_LOW"
                    ),
                    "reason": (
                        "BUY MORE was not approved because deterministic "
                        "confidence was too low."
                    ),
                    "actual_value": 62.0,
                    "threshold_value": 70.0,
                    "unit": "percent",
                    "source_layer": "reconciliation",
                },
            ],
        },
    }

    final_result = {
        "Ticker": "NVDA",
        "Asset Type": "Stock",
        "Original Action": "BUY MORE",
        "Proposed Action": "BUY MORE",
        "Reconciled Action": "HOLD",
        "Final Action": "HOLD",
        "Signal": "BUY",
        "Investment Score": 78,
        "Technical Score": 68,
        "Quality Score": 80,
        "Growth Score": 78,
        "Confidence Score": 62,
        "Evidence Score": 72,
        "Allocation %": 4.0,
        "Final Allocation %": 0.0,
        "Decision Stage": "FINAL_PORTFOLIO_DECISION",
        "Source Module": (
            "tests/test_governance_audit_harness.py"
        ),
    }

    return (
        base_row,
        chain,
        final_result,
    )

def build_buy_more_allocation_blocked_scenario() -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
]:
    """
    BUY MORE -> HOLD because the proposed additional allocation
    exceeds the permitted BUY MORE allocation.

    This represents the "don't buy more" outcome: the existing
    holding is retained, but no additional capital is allocated.
    """

    base_row = {
        "Ticker": "TESTBUYMORE",
        "Asset Type": "Stock",
        "Original Action": "BUY MORE",
        "Proposed Action": "BUY MORE",
        "Signal": "BUY",
        "Investment Score": 88,
        "Technical Score": 82,
        "Quality Score": 84,
        "Growth Score": 86,
        "Confidence Score": 82,
        "Evidence Score": 80,
        "Allocation %": 4.5,
        "Maximum Allocation %": 5.0,
    }

    chain = {
        "deterministic": {
            "Evidence Assessment": {
                "Evidence Score": 80,
                "Decision Support": "SUPPORTED",
                "Historical Signal Reliability": "RELIABLE",
                "Historical Signal Observations": 100,
            },
            "Confidence": 82,
            "Proposed Action": "BUY MORE",
        },
        "explanation": {},
        "review": {
            "Review Decision": "ACCEPT",
            "LLM Confidence": 85,
            "Challenge": False,
            "LLM Reason": (
                "The underlying investment case is strong, "
                "but the existing position is already too large "
                "for additional allocation."
            ),
        },
        "reconciliation": {
            "Status": "CHALLENGE",
            "Reconciled Action": "HOLD",
            "Governance Flags": [
                "BUY MORE GOVERNANCE REQUIREMENTS NOT MET",
                "Proposed allocation exceeds maximum permitted "
                "BUY MORE allocation",
            ],
            "Governance Reasons": [
                (
                    "BUY MORE did not satisfy one or more "
                    "of the dedicated governance requirements."
                ),
                (
                    "BUY MORE was not approved because the "
                    "proposed allocation exceeds the maximum "
                    "permitted BUY MORE allocation."
                ),
            ],
        },
    }

    final_result = {
        "Ticker": "TESTBUYMORE",
        "Asset Type": "Stock",
        "Original Action": "BUY MORE",
        "Proposed Action": "BUY MORE",
        "Reconciled Action": "HOLD",
        "Final Action": "HOLD",
        "Signal": "BUY",
        "Investment Score": 88,
        "Technical Score": 82,
        "Quality Score": 84,
        "Growth Score": 86,
        "Confidence Score": 82,
        "Evidence Score": 80,
        "Allocation %": 4.5,
        "Final Allocation %": 4.5,
        "Decision Stage": "FINAL_PORTFOLIO_DECISION",
        "Source Module": (
            "tests/test_governance_audit_harness.py"
        ),
    }

    return (
        base_row,
        chain,
        final_result,
    )

def build_buy_new_weak_evidence_scenario() -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
]:
    """
    BUY NEW -> HOLD because deterministic evidence is insufficient.

    This represents a non-owned candidate where the proposal is BUY NEW,
    but weak deterministic evidence prevents an automatic portfolio
    change even though the independent LLM review accepts the proposal.
    """

    base_row = {
        "Ticker": "TESTBUY",
        "Asset Type": "Stock",
        "Original Action": "BUY NEW",
        "Proposed Action": "BUY NEW",
        "Signal": "BUY",
        "Investment Score": 88,
        "Technical Score": 76,
        "Quality Score": 82,
        "Growth Score": 80,
        "Confidence Score": 55,
        "Evidence Score": 50,
        "Allocation %": 1.0,
        "Maximum Allocation %": 2.0,
    }

    chain = {
        "deterministic": {
            "Evidence Assessment": {
                "Evidence Score": 50,
                "Decision Support": "NOT SUPPORTED",
                "Historical Signal Reliability": (
                    "INSUFFICIENT DATA"
                ),
                "Historical Signal Observations": 5,
            },
            "Confidence": 55,
            "Proposed Action": "BUY NEW",
        },
        "explanation": {},
        "review": {
            "Review Decision": "ACCEPT",
            "LLM Confidence": 82,
            "Challenge": False,
            "LLM Reason": (
                "The investment case is attractive, "
                "but historical evidence remains immature."
            ),
        },
        "reconciliation": {
            "Status": "CHALLENGE",
            "Reconciled Action": "HOLD",
            "Governance Flags": [
                "WEAK DETERMINISTIC EVIDENCE",
                "LLM ACCEPTS WEAK PROPOSAL",
            ],
            "Governance Reasons": [
                (
                    "Deterministic evidence is insufficient "
                    "to support automatic portfolio change."
                ),
                (
                    "LLM agreement cannot compensate for "
                    "insufficient deterministic evidence."
                ),
                (
                    "The deterministic proposal was not approved "
                    "because deterministic confidence was below "
                    "the minimum confidence threshold."
                ),
            ],
        },
    }

    final_result = {
        "Ticker": "TESTBUY",
        "Asset Type": "Stock",
        "Original Action": "BUY NEW",
        "Proposed Action": "BUY NEW",
        "Reconciled Action": "HOLD",
        "Final Action": "HOLD",
        "Signal": "BUY",
        "Investment Score": 88,
        "Technical Score": 76,
        "Quality Score": 82,
        "Growth Score": 80,
        "Confidence Score": 55,
        "Evidence Score": 50,
        "Allocation %": 1.0,
        "Final Allocation %": 0.0,
        "Decision Stage": "FINAL_PORTFOLIO_DECISION",
        "Source Module": (
            "tests/test_governance_audit_harness.py"
        ),
    }

    return (
        base_row,
        chain,
        final_result,
    )


def build_reduce_survives_scenario() -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
]:
    """
    REDUCE 50% -> REDUCE 50%.

    Governance permits the reduction because the deterministic evidence
    is sufficiently strong and the investment case is weak.
    """

    base_row = {
        "Ticker": "TESTREDUCE",
        "Asset Type": "Stock",
        "Original Action": "REDUCE 50%",
        "Proposed Action": "REDUCE 50%",
        "Signal": "SELL",
        "Investment Score": 32,
        "Technical Score": 35,
        "Quality Score": 55,
        "Growth Score": 48,
        "Confidence Score": 76,
        "Evidence Score": 78,
        "Allocation %": 6.0,
        "Maximum Allocation %": 10.0,
    }

    chain = {
        "deterministic": {
            "Evidence Assessment": {
                "Evidence Score": 78,
                "Decision Support": "SUPPORTED",
                "Historical Signal Reliability": "RELIABLE",
                "Historical Signal Observations": 80,
            },
            "Confidence": 76,
            "Proposed Action": "REDUCE",
        },
        "explanation": {},
        "review": {
            "Review Decision": "ACCEPT",
            "LLM Confidence": 82,
            "Challenge": False,
            "LLM Reason": (
                "The weak investment case supports reducing "
                "the existing holding."
            ),
        },
        "reconciliation": {
            "Status": "ACCEPT",
            "Reconciled Action": "REDUCE",
            "Governance Flags": [
                "JUSTIFIED REDUCE",
            ],
            "Governance Reasons": [
                (
                    "REDUCE is supported by sufficient deterministic "
                    "evidence and an adequately weak investment case "
                    "for the existing holding."
                ),
                (
                    "Investment Score is sufficiently weak to "
                    "justify reducing exposure."
                ),
                (
                    "The underlying analytical signal is bearish."
                ),
                (
                    "The independent LLM review accepts the "
                    "REDUCE proposal."
                ),
            ],
        },
    }

    final_result = {
        "Ticker": "TESTREDUCE",
        "Asset Type": "Stock",
        "Original Action": "REDUCE 50%",
        "Proposed Action": "REDUCE",
        "Reconciled Action": "REDUCE 50%",
        "Final Action": "REDUCE 50%",
        "Signal": "SELL",
        "Investment Score": 32,
        "Technical Score": 35,
        "Quality Score": 55,
        "Growth Score": 48,
        "Confidence Score": 76,
        "Evidence Score": 78,
        "Allocation %": 6.0,
        "Final Allocation %": 3.0,
        "Decision Stage": "FINAL_PORTFOLIO_DECISION",
        "Source Module": (
            "tests/test_governance_audit_harness.py"
        ),
    }

    return (
        base_row,
        chain,
        final_result,
    )


def build_sell_aligned_scenario() -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
]:
    """
    SELL -> SELL.

    This confirms that an aligned deterministic/LLM decision is also
    auditable and is not treated as an unexplained overwrite.
    """

    base_row = {
        "Ticker": "TESTSELL",
        "Asset Type": "Stock",
        "Original Action": "SELL",
        "Proposed Action": "SELL",
        "Signal": "STRONG SELL",
        "Investment Score": 18,
        "Technical Score": 25,
        "Quality Score": 35,
        "Growth Score": 30,
        "Confidence Score": 86,
        "Evidence Score": 85,
        "Allocation %": 4.0,
        "Maximum Allocation %": 10.0,
    }

    chain = {
        "deterministic": {
            "Evidence Assessment": {
                "Evidence Score": 85,
                "Decision Support": "SUPPORTED",
                "Historical Signal Reliability": "RELIABLE",
                "Historical Signal Observations": 100,
            },
            "Confidence": 86,
            "Proposed Action": "SELL",
        },
        "explanation": {},
        "review": {
            "Review Decision": "ACCEPT",
            "LLM Confidence": 88,
            "Challenge": False,
            "LLM Reason": (
                "The independent review supports the "
                "deterministic proposal."
            ),
        },
        "reconciliation": {
            "Status": "ACCEPT",
            "Reconciled Action": "SELL",
            "Governance Flags": [],
            "Governance Reasons": [
                (
                    "The independent LLM review supports "
                    "the deterministic proposal."
                ),
                (
                    "Deterministic evidence and independent "
                    "LLM review are aligned."
                ),
                "LLM review has strong confidence.",
            ],
        },
    }

    final_result = {
        "Ticker": "TESTSELL",
        "Asset Type": "Stock",
        "Original Action": "SELL",
        "Proposed Action": "SELL",
        "Reconciled Action": "SELL",
        "Final Action": "SELL",
        "Signal": "STRONG SELL",
        "Investment Score": 18,
        "Technical Score": 25,
        "Quality Score": 35,
        "Growth Score": 30,
        "Confidence Score": 86,
        "Evidence Score": 85,
        "Allocation %": 4.0,
        "Final Allocation %": 0.0,
        "Decision Stage": "FINAL_PORTFOLIO_DECISION",
        "Source Module": (
            "tests/test_governance_audit_harness.py"
        ),
    }

    return (
        base_row,
        chain,
        final_result,
    )


def build_hold_scenario() -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
]:
    """
    HOLD -> HOLD.

    Confirms that ordinary HOLD decisions are persisted as well.
    """

    base_row = {
        "Ticker": "TESTHOLD",
        "Asset Type": "Stock",
        "Original Action": "HOLD",
        "Proposed Action": "HOLD",
        "Signal": "HOLD",
        "Investment Score": 55,
        "Technical Score": 58,
        "Quality Score": 60,
        "Growth Score": 55,
        "Confidence Score": 72,
        "Evidence Score": 70,
        "Allocation %": 3.0,
        "Maximum Allocation %": 5.0,
    }

    chain = {
        "deterministic": {
            "Evidence Assessment": {
                "Evidence Score": 70,
                "Decision Support": "SUPPORTED",
                "Historical Signal Reliability": "RELIABLE",
                "Historical Signal Observations": 40,
            },
            "Confidence": 72,
            "Proposed Action": "HOLD",
        },
        "explanation": {},
        "review": {
            "Review Decision": "ACCEPT",
            "LLM Confidence": 75,
            "Challenge": False,
            "LLM Reason": (
                "The independent LLM review supports "
                "the deterministic HOLD."
            ),
        },
        "reconciliation": {
            "Status": "ACCEPT",
            "Reconciled Action": "HOLD",
            "Governance Flags": [],
            "Governance Reasons": [
                (
                    "The independent LLM review supports "
                    "the deterministic HOLD."
                ),
            ],
        },
    }

    final_result = {
        "Ticker": "TESTHOLD",
        "Asset Type": "Stock",
        "Original Action": "HOLD",
        "Proposed Action": "HOLD",
        "Reconciled Action": "HOLD",
        "Final Action": "HOLD",
        "Signal": "HOLD",
        "Investment Score": 55,
        "Technical Score": 58,
        "Quality Score": 60,
        "Growth Score": 55,
        "Confidence Score": 72,
        "Evidence Score": 70,
        "Allocation %": 3.0,
        "Final Allocation %": 3.0,
        "Decision Stage": "FINAL_PORTFOLIO_DECISION",
        "Source Module": (
            "tests/test_governance_audit_harness.py"
        ),
    }

    return (
        base_row,
        chain,
        final_result,
    )


# ============================================================
# SCENARIO DEFINITIONS
# ============================================================


SCENARIOS = [
    (
        "BUY MORE governance override",
        build_buy_more_governance_scenario,
        "NVDA",
        "BUY MORE",
        "HOLD",
        True,
    ),
    (
        "BUY NEW weak deterministic evidence",
        build_buy_new_weak_evidence_scenario,
        "TESTBUY",
        "BUY NEW",
        "HOLD",
        True,
    ),
    (
        "REDUCE justified by governance",
        build_reduce_survives_scenario,
        "TESTREDUCE",
        "REDUCE 50%",
        "REDUCE 50%",
        False,
    ),
    (
        "SELL deterministic and AI aligned",
        build_sell_aligned_scenario,
        "TESTSELL",
        "SELL",
        "SELL",
        False,
    ),
    (
        "HOLD deterministic and AI aligned",
        build_hold_scenario,
        "TESTHOLD",
        "HOLD",
        "HOLD",
        False,
    ),
    (
        "BUY MORE governance override - confidence too low",
        build_buy_more_governance_scenario,
        "NVDA",
        "BUY MORE",
        "HOLD",
        True,
    ),
    (
        "BUY MORE governance override - allocation too high",
        build_buy_more_allocation_blocked_scenario,
        "TESTBUYMORE",
        "BUY MORE",
        "HOLD",
        True,
    ),
]


# ============================================================
# AUDIT QUERY HELPERS
# ============================================================


def get_decision(
    conn: sqlite3.Connection,
    audit_decision_id: int,
) -> sqlite3.Row:
    """Return one persisted audit decision."""

    row = conn.execute(
        """
        SELECT
            id,
            audit_run_id,
            ticker,
            original_action,
            proposed_action,
            reconciled_action,
            final_action,
            action_changed,
            reconciliation_status
        FROM audit_decisions
        WHERE id = ?
        """,
        (audit_decision_id,),
    ).fetchone()

    if row is None:
        raise AssertionError(
            f"Audit decision {audit_decision_id} "
            "was not persisted."
        )

    return row


def get_reasons(
    conn: sqlite3.Connection,
    audit_decision_id: int,
) -> list[sqlite3.Row]:
    """Return all persisted audit reasons for one decision."""

    return conn.execute(
        """
        SELECT
            id,
            reason_code,
            reason_category,
            reason_description,
            actual_value,
            threshold_value,
            unit,
            severity,
            source_layer
        FROM audit_reasons
        WHERE audit_decision_id = ?
        ORDER BY id
        """,
        (audit_decision_id,),
    ).fetchall()


# ============================================================
# SCENARIO EXECUTION
# ============================================================


def run_scenario(
    conn: sqlite3.Connection,
    audit_run_id: int,
    name: str,
    builder,
    expected_ticker: str,
    expected_original: str,
    expected_final: str,
    expected_change: bool,
) -> int:
    """Persist and verify one controlled governance scenario."""

    print()
    print("-" * 70)
    print(name)
    print("-" * 70)

    base_row, chain, final_result = builder()

    audit_decision_id = record_decision_audit(
        conn=conn,
        audit_run_id=audit_run_id,
        base_row=base_row,
        chain=chain,
        final_result=final_result,
    )

    conn.commit()

    decision = get_decision(
        conn,
        audit_decision_id,
    )

    assert_equal(
        decision["ticker"],
        expected_ticker,
        "Persisted ticker is incorrect.",
    )

    assert_equal(
        decision["original_action"],
        expected_original,
        "Persisted original action is incorrect.",
    )

    assert_equal(
        decision["final_action"],
        expected_final,
        "Persisted final action is incorrect.",
    )

    assert_equal(
        bool(decision["action_changed"]),
        expected_change,
        "Persisted action_changed flag is incorrect.",
    )

    reasons = get_reasons(
        conn,
        audit_decision_id,
    )

    print(
        f"Audit decision ID: {audit_decision_id}"
    )

    print(
        f"Decision: "
        f"{decision['original_action']} -> "
        f"{decision['final_action']}"
    )

    print(
        f"Audit reasons captured: {len(reasons)}"
    )

    for reason in reasons:
        print(
            f"  - {reason['reason_code']}: "
            f"{reason['reason_description']}"
        )

    assert_true(
        len(reasons) > 0,
        (
            f"No audit reasons were recorded for "
            f"{expected_ticker}."
        ),
    )

    if expected_change:
        governance_reasons = [
            reason
            for reason in reasons
            if (
                str(reason["reason_category"])
                .upper()
                == "GOVERNANCE"
            )
            or (
                str(reason["reason_code"])
                .upper()
                in {
                    "GOVERNANCE_CONSTRAINT",
                    "DECISION_CHANGE",
                    "RECONCILIATION_REASON",
                    "EVIDENCE_SCORE_LOW",
                    "LLM_REVIEW",
                }
            )
        ]

        assert_true(
            len(governance_reasons) > 0,
            (
                f"{expected_ticker} changed from "
                f"{expected_original} to {expected_final}, "
                "but no governance-related audit reason "
                "was persisted."
            ),
        )

    print("PASS")

    return audit_decision_id


# ============================================================
# MAIN
# ============================================================


def main() -> None:
    """Run the complete governance audit harness."""

    print()
    print("=" * 70)
    print("GOVERNANCE AUDIT TEST HARNESS")
    print("=" * 70)
    print()
    print(
        f"Database: {DATABASE_PATH}"
    )

    if not DATABASE_PATH.exists():
        raise FileNotFoundError(
            f"Database not found: {DATABASE_PATH}"
        )

    conn = sqlite3.connect(
        DATABASE_PATH
    )

    conn.row_factory = sqlite3.Row

    try:
        audit_run_id = create_audit_run(
            conn
        )

        print(
            f"Created audit run: {audit_run_id}"
        )

        decision_ids: list[int] = []

        for scenario in SCENARIOS:
            (
                name,
                builder,
                ticker,
                original_action,
                final_action,
                changed,
            ) = scenario

            decision_id = run_scenario(
                conn=conn,
                audit_run_id=audit_run_id,
                name=name,
                builder=builder,
                expected_ticker=ticker,
                expected_original=original_action,
                expected_final=final_action,
                expected_change=changed,
            )

            decision_ids.append(
                decision_id
            )

        complete_audit_run(
            conn,
            audit_run_id,
        )

        print()
        print("=" * 70)
        print("DATABASE VERIFICATION")
        print("=" * 70)

        placeholders = ", ".join(
            "?"
            for _ in decision_ids
        )

        persisted = conn.execute(
            f"""
            SELECT
                id,
                ticker,
                original_action,
                proposed_action,
                reconciled_action,
                final_action,
                action_changed
            FROM audit_decisions
            WHERE id IN ({placeholders})
            ORDER BY id
            """,
            tuple(decision_ids),
        ).fetchall()

        assert_equal(
            len(persisted),
            len(decision_ids),
            "Not all audit decisions were persisted.",
        )

        reason_count = conn.execute(
            f"""
            SELECT COUNT(*)
            FROM audit_reasons
            WHERE audit_decision_id IN (
                {placeholders}
            )
            """,
            tuple(decision_ids),
        ).fetchone()[0]

        print(
            f"Audit decisions persisted: "
            f"{len(persisted)}"
        )

        print(
            f"Audit reasons persisted: "
            f"{reason_count}"
        )

        assert_true(
            reason_count > 0,
            "No audit reasons were persisted.",
        )

        print()
        print("=" * 70)
        print("GOVERNANCE AUDIT HARNESS PASSED")
        print("=" * 70)
        print()
        print(
            f"Audit run ID: {audit_run_id}"
        )
        print(
            f"Decision records: {len(persisted)}"
        )
        print(
            f"Reason records: {reason_count}"
        )
        print()
        print(
            "The records have been deliberately left in "
            "portfolio_manager.db for inspection."
        )
        print()
        print(
            "Example:"
        )
        print(
            "sqlite3 data/portfolio_manager.db"
        )
        print()
        print(
            "SELECT id, ticker, original_action, "
            "proposed_action, reconciled_action, "
            "final_action, action_changed"
        )
        print(
            "FROM audit_decisions"
        )
        print(
            f"WHERE audit_run_id = {audit_run_id}"
        )
        print(
            "ORDER BY id;"
        )

    finally:
        conn.close()


if __name__ == "__main__":
    main()