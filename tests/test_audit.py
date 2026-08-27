
"""
Epic 1 — Audit Layer Test Harness

Purpose
-------
Validates the audit persistence layer without running the full
portfolio decision pipeline.

The test deliberately creates a BUY MORE -> HOLD change with
multiple governance reasons so we can verify that:

    audit_runs
        -> one run

    audit_decisions
        -> one decision

    audit_reasons
        -> multiple reasons for the same decision

Database
--------
data/portfolio_manager.db
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path


# ============================================================
# PROJECT PATH
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from analysis.audit import record_decision_audit


DATABASE_PATH = (
    PROJECT_ROOT
    / "data"
    / "portfolio_manager.db"
)


# ============================================================
# ASSERTION HELPERS
# ============================================================

def assert_equal(actual, expected, message):
    """Raise a useful assertion error."""
    if actual != expected:
        raise AssertionError(
            f"{message}\n"
            f"Expected: {expected!r}\n"
            f"Actual:   {actual!r}"
        )


def assert_true(condition, message):
    """Assert that a condition is true."""
    if not condition:
        raise AssertionError(message)


# ============================================================
# DATABASE HELPERS
# ============================================================

def create_test_run(conn):
    """Create a pre-production audit run."""

    conn.execute(
        """
        INSERT INTO audit_runs
        (
            run_id,
            run_date,
            environment,
            code_version,
            status,
            total_decisions,
            changed_decisions,
            created_at
        )
        VALUES
        (
            ?,
            datetime('now'),
            'pre-production',
            ?,
            'RUNNING',
            0,
            0,
            datetime('now')
        )
        """,
        (
            "TEST-AUDIT-EPIC1",
            "TEST",
        ),
    )

    return conn.execute(
        """
        SELECT id
        FROM audit_runs
        WHERE run_id = ?
        """,
        (
            "TEST-AUDIT-EPIC1",
        ),
    ).fetchone()[0]


def cleanup_test_data(conn):
    """Remove records created by this harness."""
    run = conn.execute(
        """
        SELECT id
        FROM audit_runs
        WHERE run_id = ?
        """,
        (
            "TEST-AUDIT-EPIC1",
        ),
    ).fetchone()

    if not run:
        return

    audit_run_id = run[0]

    conn.execute(
        """
        DELETE FROM audit_reasons
        WHERE audit_decision_id IN
        (
            SELECT id
            FROM audit_decisions
            WHERE audit_run_id = ?
        )
        """,
        (
            audit_run_id,
        ),
    )

    conn.execute(
        """
        DELETE FROM audit_decisions
        WHERE audit_run_id = ?
        """,
        (
            audit_run_id,
        ),
    )

    conn.execute(
        """
        DELETE FROM audit_runs
        WHERE id = ?
        """,
        (
            audit_run_id,
        ),
    )

    conn.commit()


# ============================================================
# TEST DATA
# ============================================================

def build_test_case():
    """
    Create a deliberately controlled BUY MORE -> HOLD case.

    Two independent reasons are supplied:

        1. Allocation exceeds maximum allocation.
        2. Technical score is below required threshold.

    The audit must retain BOTH.
    """

    base_row = {
        "Ticker": "TEST",
        "Asset Type": "Stock",

        "Original Action": "BUY MORE",
        "Proposed Action": "BUY MORE",

        "Signal": "BUY",

        "Investment Score": 82,
        "Technical Score": 55,
        "Quality Score": 78,
        "Growth Score": 74,
        "Confidence Score": 68,

        "Allocation %": 6.0,
        "Maximum Allocation %": 5.0,

        "Minimum Technical Score": 70,
    }

    chain = {
        "deterministic": {
            "Evidence Assessment": {
                "Evidence Score": 72,
            }
        },

        "explanation": {},

        "review": {},

        "reconciliation": {
            "Status": "CHALLENGE",

            "Reconciled Action": "HOLD",

            "Governance Flags": [
                "Maximum allocation exceeded",
                "Technical score too low",
            ],

            "Governance Reasons": [
                "Maximum allocation of 5% exceeded.",
                "Technical score is below the required threshold.",
            ],
        },
    }

    final_result = {
        "Ticker": "TEST",
        "Asset Type": "Stock",

        "Original Action": "BUY MORE",
        "Proposed Action": "BUY MORE",
        "Reconciled Action": "HOLD",
        "Final Action": "HOLD",

        "Signal": "BUY",

        "Investment Score": 82,
        "Technical Score": 55,
        "Quality Score": 78,
        "Growth Score": 74,
        "Confidence Score": 68,
        "Evidence Score": 72,

        "Allocation %": 6.0,
        "Final Allocation %": 0.0,

        "Decision Stage": "FINAL_PORTFOLIO_DECISION",
        "Source Module": "TEST",
    }

    return (
        base_row,
        chain,
        final_result,
    )


# ============================================================
# MAIN TEST
# ============================================================

def main():
    print()
    print("=" * 70)
    print("EPIC 1 — AUDIT TEST HARNESS")
    print("=" * 70)
    print()
    print(
        f"Database: {DATABASE_PATH}"
    )
    print()

    if not DATABASE_PATH.exists():
        raise FileNotFoundError(
            f"Database not found: {DATABASE_PATH}"
        )

    conn = sqlite3.connect(
        DATABASE_PATH
    )

    try:
        # ----------------------------------------------------
        # Clean any previous test run
        # ----------------------------------------------------

        cleanup_test_data(
            conn
        )

        # ----------------------------------------------------
        # Create audit run
        # ----------------------------------------------------

        audit_run_id = create_test_run(
            conn
        )

        print(
            f"Created audit run: {audit_run_id}"
        )

        # ----------------------------------------------------
        # Build controlled test case
        # ----------------------------------------------------

        (
            base_row,
            chain,
            final_result,
        ) = build_test_case()

        # ----------------------------------------------------
        # Record decision
        # ----------------------------------------------------

        audit_decision_id = record_decision_audit(
            conn=conn,
            audit_run_id=audit_run_id,
            base_row=base_row,
            chain=chain,
            final_result=final_result,
        )

        conn.commit()

        print(
            f"Created audit decision: "
            f"{audit_decision_id}"
        )

        # ----------------------------------------------------
        # Verify decision
        # ----------------------------------------------------

        decision = conn.execute(
            """
            SELECT
                ticker,
                original_action,
                proposed_action,
                reconciled_action,
                final_action,
                action_changed
            FROM audit_decisions
            WHERE id = ?
            """,
            (
                audit_decision_id,
            ),
        ).fetchone()

        assert_true(
            decision is not None,
            "Audit decision was not persisted.",
        )

        (
            ticker,
            original_action,
            proposed_action,
            reconciled_action,
            final_action,
            action_changed,
        ) = decision

        assert_equal(
            ticker,
            "TEST",
            "Ticker incorrect.",
        )

        assert_equal(
            original_action,
            "BUY MORE",
            "Original action incorrect.",
        )

        assert_equal(
            proposed_action,
            "BUY MORE",
            "Proposed action incorrect.",
        )

        assert_equal(
            reconciled_action,
            "HOLD",
            "Reconciled action incorrect.",
        )

        assert_equal(
            final_action,
            "HOLD",
            "Final action incorrect.",
        )

        assert_equal(
            action_changed,
            1,
            "Action should have been recorded as changed.",
        )

        print(
            "✓ Decision record verified"
        )

        # ----------------------------------------------------
        # Verify ALL reasons
        # ----------------------------------------------------

        reasons = conn.execute(
            """
            SELECT
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
            (
                audit_decision_id,
            ),
        ).fetchall()

        print()
        print(
            f"Audit reasons captured: {len(reasons)}"
        )

        for reason in reasons:
            print(
                f"  - {reason[0]}: {reason[2]}"
            )

        # We expect at least two independent reasons.
        assert_true(
            len(reasons) >= 2,
            (
                "Expected multiple audit reasons, "
                f"but only {len(reasons)} were recorded."
            ),
        )

        reason_codes = {
            reason[0]
            for reason in reasons
        }

        assert_true(
            "ALLOCATION_CONSTRAINT" in reason_codes,
            (
                "Allocation constraint reason "
                "was not captured."
            ),
        )

        assert_true(
            (
                "TECHNICAL_SCORE_LOW" in reason_codes
                or "TECHNICAL_CONSTRAINT" in reason_codes
            ),
            (
                "Technical constraint reason "
                "was not captured."
            ),
        )

        print(
            "✓ Multiple reasons verified"
        )

        # ----------------------------------------------------
        # Verify run counts
        # ----------------------------------------------------

        conn.execute(
            """
            UPDATE audit_runs
            SET
                total_decisions = (
                    SELECT COUNT(*)
                    FROM audit_decisions
                    WHERE audit_run_id = ?
                ),
                changed_decisions = (
                    SELECT COUNT(*)
                    FROM audit_decisions
                    WHERE audit_run_id = ?
                    AND action_changed = 1
                ),
                status = 'COMPLETED'
            WHERE id = ?
            """,
            (
                audit_run_id,
                audit_run_id,
                audit_run_id,
            ),
        )

        conn.commit()

        run = conn.execute(
            """
            SELECT
                status,
                total_decisions,
                changed_decisions
            FROM audit_runs
            WHERE id = ?
            """,
            (
                audit_run_id,
            ),
        ).fetchone()

        assert_true(
            run is not None,
            "Audit run was not found.",
        )

        status, total, changed = run

        assert_equal(
            status,
            "COMPLETED",
            "Audit run did not complete.",
        )

        assert_equal(
            total,
            1,
            "Audit run should contain one decision.",
        )

        assert_equal(
            changed,
            1,
            "Audit run should contain one changed decision.",
        )

        print(
            "✓ Audit run counts verified"
        )

        # ----------------------------------------------------
        # Success
        # ----------------------------------------------------

        print()
        print("=" * 70)
        print("AUDIT TEST PASSED")
        print("=" * 70)
        print()
        print(
            "BUY MORE -> HOLD was recorded correctly."
        )
        print(
            f"Reasons captured: {len(reasons)}"
        )
        print(
            "The audit successfully retains multiple reasons "
            "for one decision change."
        )
        print()

    finally:
        # ----------------------------------------------------
        # Keep the database clean.
        #
        # The harness validates persistence but removes its
        # TEST record afterwards so it cannot pollute real
        # audit history.
        # ----------------------------------------------------

        cleanup_test_data(
            conn
        )

        conn.close()


if __name__ == "__main__":
    main()
