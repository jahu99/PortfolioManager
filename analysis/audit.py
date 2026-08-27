"""
Decision Audit Management
=========================

Purpose
-------
Provides the audit orchestration layer for the Stock Momentum Agent.

This module records the transition from the original recommendation through
the portfolio decision and reconciliation stages to the final action.

The audit layer is observational only:

    - It does NOT change portfolio decisions.
    - It does NOT override the reconciler.
    - It records every material reason for an action change.
    - It stores each execution as a separate audit run.
    - It preserves multiple reasons for the same decision.

Database
--------
Uses:

    data/portfolio_manager.db

Tables:

    audit_runs
    audit_decisions
    audit_reasons

Design principles
-----------------
1. One audit run represents one execution of the portfolio decision process.
2. One audit decision represents one ticker/security within that run.
3. One audit reason represents one reason associated with a decision.
4. Multiple reasons are always preserved.
5. Audit failures must not silently alter investment decisions.
6. The audit layer tolerates slightly different dictionary contracts while
   the decision engine is still being stabilised.
"""

from __future__ import annotations

import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable


# ============================================================
# DATABASE
# ============================================================

DATABASE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "data",
    "portfolio_manager.db",
)


# ============================================================
# CONSTANTS
# ============================================================

VALID_ENVIRONMENTS = {
    "pre-production",
    "production",
}

RUNNING = "RUNNING"
COMPLETED = "COMPLETED"
FAILED = "FAILED"

VALID_RUN_STATUSES = {
    RUNNING,
    COMPLETED,
    FAILED,
}

DEFAULT_FINAL_ACTION = "HOLD"


# ============================================================
# GENERAL HELPERS
# ============================================================

def utc_now() -> str:
    """Return the current UTC timestamp as an ISO-formatted string."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def create_run_id() -> str:
    """Create a unique audit run identifier."""
    return uuid.uuid4().hex


def safe_text(
    value: Any,
    default: str = "",
) -> str:
    """Safely convert a value to stripped text."""
    if value is None:
        return default

    try:
        text = str(value).strip()
    except Exception:
        return default

    return text if text else default


def safe_float(
    value: Any,
    default: float | None = None,
) -> float | None:
    """Safely convert a value to float."""
    if value is None:
        return default

    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(
    value: Any,
    default: int = 0,
) -> int:
    """Safely convert a value to integer."""
    if value is None:
        return default

    if isinstance(value, bool):
        return int(value)

    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def safe_bool(
    value: Any,
    default: bool = False,
) -> bool:
    """Safely convert common boolean representations."""
    if value is None:
        return default

    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return bool(value)

    text = safe_text(value).upper()

    if text in {"TRUE", "YES", "Y", "1"}:
        return True

    if text in {"FALSE", "NO", "N", "0"}:
        return False

    return default


def first_value(
    *values: Any,
    default: Any = None,
) -> Any:
    """
    Return the first non-empty value.

    This allows the audit layer to tolerate minor differences in dictionary
    contracts while the decision engine is being stabilised.
    """
    for value in values:
        if value is None:
            continue

        if isinstance(value, str) and not value.strip():
            continue

        return value

    return default


def get_value(
    row: dict[str, Any],
    *keys: str,
    default: Any = None,
) -> Any:
    """Return the first available value from a dictionary."""
    if not isinstance(row, dict):
        return default

    return first_value(
        *(row.get(key) for key in keys),
        default=default,
    )


def normalise_action(
    value: Any,
    default: str = DEFAULT_FINAL_ACTION,
) -> str:
    """
    Normalise an action for audit comparison.

    REDUCE 25%, REDUCE 50%, REDUCE 75% and REDUCE 100% are all treated
    as the same action category for action-change detection.
    """
    action = safe_text(value, default).upper()

    if action.startswith("REDUCE"):
        return "REDUCE"

    return action


def actions_differ(
    original_action: Any,
    final_action: Any,
) -> bool:
    """Return True when the effective action category changed."""
    return (
        normalise_action(original_action)
        != normalise_action(final_action)
    )


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_connection() -> sqlite3.Connection:
    """Open a connection to the portfolio manager database."""
    return sqlite3.connect(DATABASE_PATH)


# ============================================================
# AUDIT RUN MANAGEMENT
# ============================================================

def start_audit_run(
    environment: str,
    code_version: str | None = None,
) -> dict[str, Any]:
    """
    Start a new audit run.

    Returns
    -------
    dict
        Contains the database ID, run ID, environment, code version
        and initial status.
    """
    environment = safe_text(environment).lower()

    if environment not in VALID_ENVIRONMENTS:
        raise ValueError(
            "environment must be 'pre-production' or 'production'"
        )

    run_id = create_run_id()
    created_at = utc_now()
    run_date = created_at

    conn = get_connection()

    try:
        cursor = conn.cursor()

        cursor.execute(
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
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                run_date,
                environment,
                code_version,
                RUNNING,
                0,
                0,
                created_at,
            ),
        )

        audit_run_id = cursor.lastrowid

        conn.commit()

        return {
            "id": audit_run_id,
            "run_id": run_id,
            "environment": environment,
            "code_version": code_version,
            "status": RUNNING,
        }

    finally:
        conn.close()


def get_audit_run_counts(
    audit_run_id: int,
) -> tuple[int, int]:
    """
    Return authoritative decision counts for an audit run.

    Counts are derived from the persisted audit_decisions rows so that
    audit_runs reflects the SQLite audit data rather than a separate
    in-memory counter in the decision engine.
    """
    conn = get_connection()

    try:
        row = conn.execute(
            """
            SELECT
                COUNT(*) AS total_decisions,
                COALESCE(
                    SUM(action_changed),
                    0
                ) AS changed_decisions
            FROM audit_decisions
            WHERE audit_run_id = ?
            """,
            (audit_run_id,),
        ).fetchone()

        return (
            safe_int(row[0] if row else 0),
            safe_int(row[1] if row else 0),
        )

    finally:
        conn.close()


def complete_audit_run(
    audit_run_id: int,
    total_decisions: int,
    changed_decisions: int,
) -> None:
    """Mark an audit run as successfully completed."""
    conn = get_connection()

    try:
        conn.execute(
            """
            UPDATE audit_runs
            SET
                status = ?,
                total_decisions = ?,
                changed_decisions = ?
            WHERE id = ?
            """,
            (
                COMPLETED,
                safe_int(total_decisions),
                safe_int(changed_decisions),
                audit_run_id,
            ),
        )

        conn.commit()

    finally:
        conn.close()


def fail_audit_run(
    audit_run_id: int,
) -> None:
    """Mark an audit run as failed."""
    conn = get_connection()

    try:
        conn.execute(
            """
            UPDATE audit_runs
            SET status = ?
            WHERE id = ?
            """,
            (
                FAILED,
                audit_run_id,
            ),
        )

        conn.commit()

    finally:
        conn.close()


# ============================================================
# REASON NORMALISATION
# ============================================================

def normalise_reason(
    reason: Any,
    default_source_layer: str = "",
) -> dict[str, Any]:
    """
    Convert a supplied reason into the audit_reasons schema.

    Both structured dictionaries and simple strings are supported.
    """
    if isinstance(reason, dict):
        return {
            "reason_code": safe_text(
                first_value(
                    reason.get("reason_code"),
                    reason.get("code"),
                    default="DECISION_CHANGE",
                ),
                "DECISION_CHANGE",
            ),
            "reason_category": safe_text(
                first_value(
                    reason.get("reason_category"),
                    reason.get("category"),
                    default="GOVERNANCE",
                ),
                "GOVERNANCE",
            ),
            "reason_description": safe_text(
                first_value(
                    reason.get("reason_description"),
                    reason.get("description"),
                    reason.get("reason"),
                    default="",
                )
            ),
            "actual_value": safe_text(
                first_value(
                    reason.get("actual_value"),
                    reason.get("actual"),
                    default="",
                )
            ),
            "threshold_value": safe_text(
                first_value(
                    reason.get("threshold_value"),
                    reason.get("threshold"),
                    default="",
                )
            ),
            "unit": safe_text(
                reason.get("unit")
            ),
            "severity": safe_text(
                reason.get("severity"),
                "MATERIAL",
            ).upper(),
            "source_layer": safe_text(
                first_value(
                    reason.get("source_layer"),
                    reason.get("layer"),
                    default=default_source_layer,
                )
            ),
        }

    return {
        "reason_code": "DECISION_CHANGE",
        "reason_category": "GOVERNANCE",
        "reason_description": safe_text(reason),
        "actual_value": "",
        "threshold_value": "",
        "unit": "",
        "severity": "MATERIAL",
        "source_layer": default_source_layer,
    }


def _add_reason(
    reasons: list[dict[str, Any]],
    *,
    reason_code: str,
    reason_category: str,
    reason_description: str,
    actual_value: Any = None,
    threshold_value: Any = None,
    unit: str = "",
    severity: str = "MATERIAL",
    source_layer: str = "",
) -> None:
    """Append one normalised audit reason."""
    reasons.append(
        normalise_reason(
            {
                "reason_code": reason_code,
                "reason_category": reason_category,
                "reason_description": reason_description,
                "actual_value": actual_value,
                "threshold_value": threshold_value,
                "unit": unit,
                "severity": severity,
                "source_layer": source_layer,
            },
            default_source_layer=source_layer,
        )
    )


# ============================================================
# GENERIC REASON EXTRACTION
# ============================================================

def extract_reasons(
    decision: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Extract all reasons directly exposed by a decision dictionary.

    This supports the simpler audit API and is also useful when callers
    already provide structured audit reasons.
    """
    if not isinstance(decision, dict):
        return []

    candidates: list[tuple[Any, str]] = []

    explicit_reasons = first_value(
        decision.get("audit_reasons"),
        decision.get("Audit Reasons"),
        decision.get("reasons"),
        decision.get("Reasons"),
        default=[],
    )

    if isinstance(explicit_reasons, (list, tuple)):
        for reason in explicit_reasons:
            candidates.append((reason, "AUDIT"))
    elif explicit_reasons:
        candidates.append((explicit_reasons, "AUDIT"))

    governance_flags = first_value(
        decision.get("Governance Flags"),
        decision.get("governance_flags"),
        decision.get("Governance Reasons"),
        decision.get("governance_reasons"),
        default=[],
    )

    if isinstance(governance_flags, (list, tuple)):
        for reason in governance_flags:
            candidates.append((reason, "GOVERNANCE"))
    elif governance_flags:
        candidates.append((governance_flags, "GOVERNANCE"))

    reconciliation = first_value(
        decision.get("reconciliation"),
        decision.get("Reconciliation"),
        default={},
    )

    if isinstance(reconciliation, dict):

        reconciliation_reasons = first_value(
            reconciliation.get("Reasons"),
            reconciliation.get("reasons"),
            reconciliation.get("Governance Reasons"),
            reconciliation.get("Governance Flags"),
            default=[],
        )

        if isinstance(reconciliation_reasons, (list, tuple)):
            for reason in reconciliation_reasons:
                candidates.append(
                    (reason, "RECONCILIATION")
                )
        elif reconciliation_reasons:
            candidates.append(
                (
                    reconciliation_reasons,
                    "RECONCILIATION",
                )
            )

        reconciliation_reason = first_value(
            reconciliation.get("Reason"),
            reconciliation.get("Reconciliation Reason"),
            reconciliation.get("reconciliation_reason"),
            default="",
        )

        if reconciliation_reason:
            candidates.append(
                (
                    reconciliation_reason,
                    "RECONCILIATION",
                )
            )

    results: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    for reason, source_layer in candidates:
        normalised = normalise_reason(
            reason,
            default_source_layer=source_layer,
        )

        key = (
            normalised["reason_code"],
            normalised["reason_description"],
            normalised["source_layer"],
        )

        if key in seen:
            continue

        seen.add(key)
        results.append(normalised)

    return results


# ============================================================
# GOVERNED DECISION REASON COLLECTION
# ============================================================

def _collect_audit_reasons(
    base_row: dict[str, Any],
    chain: dict[str, Any],
    final_result: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Collect every material reason contributing to a governed decision.

    The audit layer is observational. It does not create or alter
    governance rules. It records governance outcomes, governance
    reasons, and failed governance checks already exposed by the
    reconciler.

    In particular, successful REDUCE challenge exceptions must still
    generate an audit reason even though they have no failed checks.
    """

    reasons: list[dict[str, Any]] = []

    if not isinstance(base_row, dict):
        base_row = {}

    if not isinstance(chain, dict):
        chain = {}

    if not isinstance(final_result, dict):
        final_result = {}

    reconciliation = chain.get("reconciliation", {})
    if not isinstance(reconciliation, dict):
        reconciliation = {}

    deterministic = chain.get("deterministic", {})
    if not isinstance(deterministic, dict):
        deterministic = {}

    review = chain.get("review", {})
    if not isinstance(review, dict):
        review = {}

    # --------------------------------------------------------
    # Helpers
    # --------------------------------------------------------

    def numeric_value(*values: Any) -> float | None:
        for value in values:
            if value is None:
                continue

            if isinstance(value, str):
                value = value.strip()
                if not value:
                    continue

            try:
                return float(value)
            except (TypeError, ValueError):
                continue

        return None

    def add_reason_once(
        reason_code: str,
        reason_category: str,
        reason_description: str,
        *,
        actual_value: Any = None,
        threshold_value: Any = None,
        unit: str = "",
        source_layer: str = "audit",
        severity: str = "MATERIAL",
    ) -> None:
        if not reason_description:
            return

        reason_code = safe_text(
            reason_code,
            "AUDIT_REASON",
        )

        reason_category = safe_text(
            reason_category,
            "governance",
        )

        reason_description = safe_text(
            reason_description,
        )

        for existing in reasons:
            if (
                existing.get("reason_code")
                == reason_code
                and existing.get("reason_description")
                == reason_description
            ):
                return

        reasons.append(
            {
                "reason_code": reason_code,
                "reason_category": reason_category,
                "reason_description": reason_description,
                "actual_value": actual_value,
                "threshold_value": threshold_value,
                "unit": safe_text(unit),
                "source_layer": safe_text(
                    source_layer,
                    "audit",
                ),
                "severity": safe_text(
                    severity,
                    "MATERIAL",
                ).upper(),
            }
        )

    # --------------------------------------------------------
    # Extract governance information from reconciliation.
    #
    # The reconciler is the source of truth. The audit layer
    # records what it produced; it does not re-run governance.
    # --------------------------------------------------------

    governance_reason_code = first_value(
        final_result.get("Governance Reason Code"),
        final_result.get("governance_reason_code"),
        reconciliation.get("Governance Reason Code"),
        reconciliation.get("governance_reason_code"),
        default=None,
    )

    governance_reason = first_value(
        final_result.get("Governance Reason"),
        final_result.get("governance_reason"),
        reconciliation.get("Governance Reason"),
        reconciliation.get("governance_reason"),
        default=None,
    )

    governance_flags = first_value(
        final_result.get("Governance Flags"),
        final_result.get("governance_flags"),
        reconciliation.get("Governance Flags"),
        reconciliation.get("governance_flags"),
        default=[],
    )

    governance_reasons = first_value(
        final_result.get("Governance Reasons"),
        final_result.get("governance_reasons"),
        reconciliation.get("Governance Reasons"),
        reconciliation.get("governance_reasons"),
        default=[],
    )

    failed_checks = first_value(
        final_result.get("Governance Failed Checks")
        if final_result.get("Governance Failed Checks")
        else None,
        final_result.get("governance_failed_checks")
        if final_result.get("governance_failed_checks")
        else None,
        final_result.get("Failed Checks")
        if final_result.get("Failed Checks")
        else None,
        final_result.get("failed_checks")
        if final_result.get("failed_checks")
        else None,
        reconciliation.get("Governance Failed Checks")
        if reconciliation.get("Governance Failed Checks")
        else None,
        reconciliation.get("governance_failed_checks")
        if reconciliation.get("governance_failed_checks")
        else None,
        reconciliation.get("Failed Checks")
        if reconciliation.get("Failed Checks")
        else None,
        reconciliation.get("failed_checks")
        if reconciliation.get("failed_checks")
        else None,
        default=[],
    )

    if not isinstance(governance_flags, list):
        governance_flags = (
            [governance_flags]
            if governance_flags
            else []
        )

    if not isinstance(governance_reasons, list):
        governance_reasons = (
            [governance_reasons]
            if governance_reasons
            else []
        )

    if not isinstance(failed_checks, list):
        failed_checks = []

    # --------------------------------------------------------
    # Persist the governance outcome.
    #
    # This is critical for successful REDUCE challenge
    # exceptions because they legitimately have no failed
    # checks.
    # --------------------------------------------------------

    if governance_reason_code:
        add_reason_once(
            reason_code=safe_text(
                governance_reason_code,
                "GOVERNANCE_OUTCOME",
            ),
            reason_category="governance",
            reason_description=safe_text(
                governance_reason,
                "Governed reconciliation outcome.",
            ),
            source_layer="reconciliation",
            severity="MATERIAL",
        )

    # --------------------------------------------------------
    # Persist governance flags.
    # --------------------------------------------------------

    for flag in governance_flags:
        flag_text = safe_text(flag)

        if not flag_text:
            continue

        flag_code = (
            "GOVERNANCE_FLAG_"
            + flag_text.upper()
            .replace(" ", "_")
            .replace("-", "_")
        )

        add_reason_once(
            reason_code=flag_code,
            reason_category="governance",
            reason_description=flag_text,
            source_layer="reconciliation",
            severity="INFO",
        )

    # --------------------------------------------------------
    # Persist explanatory governance reasons.
    # --------------------------------------------------------

    for governance_reason_text in governance_reasons:
        reason_text = safe_text(
            governance_reason_text
        )

        if not reason_text:
            continue

        add_reason_once(
            reason_code="GOVERNANCE_REASON",
            reason_category="governance",
            reason_description=reason_text,
            source_layer="reconciliation",
            severity="MATERIAL",
        )

    # --------------------------------------------------------
    # Persist individual failed governance checks.
    #
    # These are produced by the governed reconciler.
    # --------------------------------------------------------

    for failed_check in failed_checks:

        if not isinstance(
            failed_check,
            dict,
        ):
            continue

        check_code = safe_text(
            first_value(
                failed_check.get("check_code"),
                failed_check.get("reason_code"),
                failed_check.get("code"),
                default="GOVERNANCE_CHECK_FAILED",
            ),
            "GOVERNANCE_CHECK_FAILED",
        )

        check_reason = safe_text(
            first_value(
                failed_check.get("reason"),
                failed_check.get("reason_description"),
                failed_check.get("description"),
                default="Governance check failed.",
            ),
            "Governance check failed.",
        )

        actual_value = first_value(
            failed_check.get("actual_value"),
            failed_check.get("actual"),
            default=None,
        )

        threshold_value = first_value(
            failed_check.get("threshold_value"),
            failed_check.get("threshold"),
            default=None,
        )

        unit = safe_text(
            failed_check.get("unit"),
            "",
        )

        source_layer = safe_text(
            failed_check.get("source_layer"),
            "reconciliation",
        )

        # ----------------------------------------------------
        # Make quantitative governance failures explicit.
        #
        # The persisted audit reason should show both the
        # actual value and the threshold that was evaluated.
        # This makes marginal decisions immediately visible
        # in the audit report without changing the audit
        # schema or governance logic.
        # ----------------------------------------------------
        quantitative_reason = check_reason

        if (
            actual_value is not None
            and threshold_value is not None
        ):
            code_upper = check_code.upper()

            if "INVESTMENT_SCORE" in code_upper:
                quantitative_reason = (
                    f"Investment score of {actual_value} "
                    f"below threshold of {threshold_value}."
                )

            elif "CONFIDENCE" in code_upper:
                quantitative_reason = (
                    f"Confidence score of {actual_value} "
                    f"below threshold of {threshold_value}."
                )

            elif (
                "EVIDENCE" in code_upper
                and "WEAK" in code_upper
            ):
                quantitative_reason = (
                    f"Evidence score of {actual_value} "
                    f"below threshold of {threshold_value}."
                )

            elif (
                "EVIDENCE" in code_upper
                and "BELOW" in code_upper
            ):
                quantitative_reason = (
                    f"Evidence score of {actual_value} "
                    f"below threshold of {threshold_value}."
                )

            elif unit:
                quantitative_reason = (
                    f"{check_reason} "
                    f"(actual: {actual_value} {unit}; "
                    f"threshold: {threshold_value} {unit})."
                )

            else:
                quantitative_reason = (
                    f"{check_reason} "
                    f"(actual: {actual_value}; "
                    f"threshold: {threshold_value})."
                )

        add_reason_once(
            reason_code=check_code,
            reason_category="governance",
            reason_description=quantitative_reason,
            actual_value=actual_value,
            threshold_value=threshold_value,
            unit=unit,
            source_layer=source_layer,
            severity="MATERIAL",
        )

    # --------------------------------------------------------
    # Existing deterministic/review audit reasons
    # --------------------------------------------------------

    original_action = safe_text(
        first_value(
            final_result.get("Original Action"),
            base_row.get("Original Action"),
            base_row.get("Action"),
            base_row.get("Decision"),
        ),
        "HOLD",
    )

    proposed_action = safe_text(
        first_value(
            final_result.get("Proposed Action"),
            base_row.get("Proposed Action"),
        ),
        "HOLD",
    )

    reconciled_action = safe_text(
        first_value(
            final_result.get("Reconciled Action"),
            reconciliation.get("Reconciled Action"),
        ),
        "HOLD",
    )

    final_action = safe_text(
        first_value(
            final_result.get("Final Action"),
            final_result.get("Final Decision"),
        ),
        "HOLD",
    )

    # --------------------------------------------------------
    # Action change itself.
    # --------------------------------------------------------

    if actions_differ(
        original_action,
        final_action,
    ):
        add_reason_once(
            reason_code="ACTION_CHANGED",
            reason_category="governance",
            reason_description=(
                f"Final action changed from "
                f"{original_action} to {final_action}."
            ),
            actual_value=final_action,
            threshold_value=original_action,
            unit="action",
            source_layer="reconciliation",
            severity="MATERIAL",
        )

    # --------------------------------------------------------
    # REDUCE-specific fallback.
    #
    # If a REDUCE governance result exists but the reconciler
    # did not expose a governance reason code, retain the
    # reconciliation status as an audit reason rather than
    # silently producing no audit row.
    # --------------------------------------------------------

    if (
        (
            original_action == "REDUCE"
            or proposed_action == "REDUCE"
            or reconciled_action == "REDUCE"
            or final_action == "REDUCE"
        )
        and not governance_reason_code
        and not failed_checks
        and reconciliation
    ):
        reconciliation_status = safe_text(
            first_value(
                reconciliation.get("Status"),
                reconciliation.get("Decision Status"),
                default="",
            )
        )

        if reconciliation_status:
            add_reason_once(
                reason_code="REDUCE_RECONCILIATION",
                reason_category="governance",
                reason_description=(
                    f"REDUCE reconciliation completed with "
                    f"status '{reconciliation_status}'."
                ),
                actual_value=reconciliation_status,
                threshold_value=None,
                unit="status",
                source_layer="reconciliation",
                severity="MATERIAL",
            )

    return reasons



# ============================================================
# GOVERNED DECISION AUDIT
# ============================================================

def record_decision_audit(
    conn: sqlite3.Connection,
    audit_run_id: int,
    base_row: dict[str, Any],
    chain: dict[str, Any],
    final_result: dict[str, Any],
) -> int:
    """
    Record one governed portfolio decision.

    Parameters
    ----------
    conn:
        Open SQLite connection.

    audit_run_id:
        ID of the audit_runs record.

    base_row:
        Original decision input.

    chain:
        Complete deterministic / review / reconciliation chain.

    final_result:
        Final result returned by the portfolio decision layer.

    Returns
    -------
    int
        Newly created audit_decisions.id.
    """
    if not isinstance(base_row, dict):
        base_row = {}

    if not isinstance(chain, dict):
        chain = {}

    if not isinstance(final_result, dict):
        final_result = {}

    reconciliation = chain.get(
        "reconciliation",
        {},
    )

    if not isinstance(reconciliation, dict):
        reconciliation = {}

    ticker = safe_text(
        first_value(
            final_result.get("Ticker"),
            base_row.get("Ticker"),
        ),
        "UNKNOWN",
    )

    asset_type = safe_text(
        first_value(
            final_result.get("Asset Type"),
            base_row.get("Asset Type"),
        )
    )

    original_action = safe_text(
        first_value(
            final_result.get("Original Action"),
            base_row.get("Original Action"),
            base_row.get("Action"),
            base_row.get("Decision"),
        ),
        "HOLD",
    )

    proposed_action = safe_text(
        first_value(
            final_result.get("Proposed Action"),
            base_row.get("Proposed Action"),
        ),
        "HOLD",
    )

    reconciled_action = safe_text(
        first_value(
            final_result.get("Reconciled Action"),
            reconciliation.get("Reconciled Action"),
        ),
        "HOLD",
    )

    final_action = safe_text(
        first_value(
            final_result.get("Final Action"),
            final_result.get("Final Decision"),
        ),
        "HOLD",
    )

    action_changed = int(
        actions_differ(
            original_action,
            final_action,
        )
    )

    original_signal = safe_text(
        first_value(
            final_result.get("Signal"),
            base_row.get("Signal"),
            final_result.get("Original Signal"),
            base_row.get("Original Signal"),
        )
    )

    investment_score = safe_float(
        first_value(
            final_result.get("Investment Score"),
            base_row.get("Investment Score"),
        )
    )

    technical_score = safe_float(
        first_value(
            final_result.get("Technical Score"),
            base_row.get("Technical Score"),
        )
    )

    quality_score = safe_float(
        first_value(
            final_result.get("Quality Score"),
            base_row.get("Quality Score"),
        )
    )

    growth_score = safe_float(
        first_value(
            final_result.get("Growth Score"),
            base_row.get("Growth Score"),
        )
    )

    confidence_score = safe_float(
        first_value(
            final_result.get("Confidence Score"),
            base_row.get("Confidence Score"),
        )
    )

    evidence_score = safe_float(
        first_value(
            final_result.get("Evidence Score"),
            base_row.get("Evidence Score"),
        )
    )

    original_allocation = safe_float(
        first_value(
            final_result.get("Original Allocation %"),
            final_result.get("Allocation %"),
            base_row.get("Original Allocation %"),
            base_row.get("Allocation %"),
        )
    )

    final_allocation = safe_float(
        first_value(
            final_result.get("Final Allocation %"),
            final_result.get("Allocation %"),
            base_row.get("Final Allocation %"),
            base_row.get("Allocation %"),
        )
    )

    reconciliation_status = safe_text(
        first_value(
            final_result.get("Reconciliation Status"),
            final_result.get("Decision Status"),
            reconciliation.get("Status"),
            reconciliation.get("Decision Status"),
        )
    )

    decision_stage = safe_text(
        final_result.get(
            "Decision Stage",
            "FINAL_PORTFOLIO_DECISION",
        ),
        "FINAL_PORTFOLIO_DECISION",
    )

    source_module = safe_text(
        final_result.get(
            "Source Module",
            "analysis.final_portfolio_decision",
        ),
        "analysis.final_portfolio_decision",
    )

    created_at = utc_now()

    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO audit_decisions
        (
            audit_run_id,
            ticker,
            asset_type,
            original_action,
            proposed_action,
            reconciled_action,
            final_action,
            action_changed,
            original_signal,
            investment_score,
            technical_score,
            quality_score,
            growth_score,
            confidence_score,
            evidence_score,
            original_allocation_pct,
            final_allocation_pct,
            reconciliation_status,
            decision_stage,
            source_module,
            created_at
        )
        VALUES
        (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        (
            audit_run_id,
            ticker,
            asset_type,
            original_action,
            proposed_action,
            reconciled_action,
            final_action,
            action_changed,
            original_signal,
            investment_score,
            technical_score,
            quality_score,
            growth_score,
            confidence_score,
            evidence_score,
            original_allocation,
            final_allocation,
            reconciliation_status,
            decision_stage,
            source_module,
            created_at,
        ),
    )

    audit_decision_id = int(cursor.lastrowid)

    reasons = _collect_audit_reasons(
        base_row=base_row,
        chain=chain,
        final_result=final_result,
    )

    for reason in reasons:
        severity = safe_text(
            reason.get("severity"),
            "MATERIAL",
        ).upper()

        if severity not in {
            "INFO",
            "WARNING",
            "MATERIAL",
        }:
            severity = "MATERIAL"

        cursor.execute(
            """
            INSERT INTO audit_reasons
            (
                audit_decision_id,
                reason_code,
                reason_category,
                reason_description,
                actual_value,
                threshold_value,
                unit,
                severity,
                source_layer,
                created_at
            )
            VALUES
            (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                audit_decision_id,
                reason["reason_code"],
                reason["reason_category"],
                reason["reason_description"],
                reason["actual_value"],
                reason["threshold_value"],
                reason["unit"],
                severity,
                reason["source_layer"],
                created_at,
            ),
        )

    # Commit the complete decision audit atomically:
    # audit_decisions row plus all associated audit_reasons.
    conn.commit()

    return audit_decision_id


# ============================================================
# SIMPLE DECISION AUDIT COMPATIBILITY API
# ============================================================

def record_audit_decision(
    audit_run_id: int,
    decision: dict[str, Any],
) -> int:
    """
    Record a simple decision dictionary.

    This compatibility wrapper preserves the original audit API while
    using the same database-writing implementation as the governed path.
    """
    if not isinstance(decision, dict):
        raise TypeError("decision must be a dictionary")

    base_row = dict(decision)

    reconciliation = first_value(
        decision.get("reconciliation"),
        decision.get("Reconciliation"),
        default={},
    )

    if not isinstance(reconciliation, dict):
        reconciliation = {}

    chain = {
        "reconciliation": reconciliation,
    }

    final_result = dict(decision)

    conn = get_connection()

    try:
        audit_decision_id = record_decision_audit(
            conn=conn,
            audit_run_id=audit_run_id,
            base_row=base_row,
            chain=chain,
            final_result=final_result,
        )

        conn.commit()

        return audit_decision_id

    finally:
        conn.close()


# ============================================================
# BATCH RECORDING
# ============================================================

def record_audit_decisions(
    audit_run_id: int,
    decisions: Iterable[dict[str, Any]],
) -> dict[str, int]:
    """
    Record a collection of decisions.

    Returns
    -------
    dict
        {
            "total_decisions": ...,
            "changed_decisions": ...
        }
    """
    total = 0
    changed = 0

    for decision in decisions:
        record_audit_decision(
            audit_run_id,
            decision,
        )

        total += 1

        original_action = safe_text(
            first_value(
                decision.get("Original Action"),
                decision.get("original_action"),
                decision.get("Original Recommendation"),
                decision.get("original_recommendation"),
            ),
            "HOLD",
        )

        final_action = safe_text(
            first_value(
                decision.get("Final Action"),
                decision.get("final_action"),
                decision.get("Final Decision"),
                decision.get("final_decision"),
            ),
            "HOLD",
        )

        if actions_differ(
            original_action,
            final_action,
        ):
            changed += 1

    return {
        "total_decisions": total,
        "changed_decisions": changed,
    }


# ============================================================
# COMPLETE AUDIT RUN
# ============================================================

def audit_decision_run(
    decisions: Iterable[dict[str, Any]],
    environment: str,
    code_version: str | None = None,
) -> dict[str, Any]:
    """
    Audit a complete collection of portfolio decisions.

    Steps
    -----
    1. Start an audit run.
    2. Record every decision.
    3. Record every reason.
    4. Mark the run COMPLETED.
    5. Mark the run FAILED if an audit error occurs.

    Any audit exception is re-raised after the run is marked FAILED.
    """
    run = start_audit_run(
        environment=environment,
        code_version=code_version,
    )

    audit_run_id = int(run["id"])

    try:
        summary = record_audit_decisions(
            audit_run_id,
            decisions,
        )

        complete_audit_run(
            audit_run_id,
            summary["total_decisions"],
            summary["changed_decisions"],
        )

        return {
            **run,
            "status": COMPLETED,
            **summary,
        }

    except Exception:
        fail_audit_run(
            audit_run_id,
        )
        raise


# ============================================================
# QUERY HELPERS
# ============================================================

def get_changed_decisions(
    audit_run_id: int,
) -> list[dict[str, Any]]:
    """Return all decisions where the effective action changed."""
    conn = get_connection()

    try:
        conn.row_factory = sqlite3.Row

        rows = conn.execute(
            """
            SELECT *
            FROM audit_decisions
            WHERE audit_run_id = ?
              AND action_changed = 1
            ORDER BY ticker
            """,
            (audit_run_id,),
        ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:
        conn.close()


def get_decision_reasons(
    audit_decision_id: int,
) -> list[dict[str, Any]]:
    """Return all reasons associated with one audited decision."""
    conn = get_connection()

    try:
        conn.row_factory = sqlite3.Row

        rows = conn.execute(
            """
            SELECT *
            FROM audit_reasons
            WHERE audit_decision_id = ?
            ORDER BY id
            """,
            (audit_decision_id,),
        ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:
        conn.close()


def get_audit_reasons_for_run(
    audit_run_id: int,
) -> list[dict[str, Any]]:
    """
    Return all persisted audit reasons for one audit run.

    The audit database is the source of truth for reconciliation
    reasons. Results are returned with the associated ticker and
    final action so reporting layers do not need to reconstruct
    audit information from in-memory decision data.
    """

    conn = get_connection()

    try:

        conn.row_factory = sqlite3.Row

        rows = conn.execute(
            """
            SELECT
                ad.id AS audit_decision_id,
                ad.ticker,
                ad.final_action,
                ad.reconciled_action,
                ad.reconciliation_status,
                ar.id AS audit_reason_id,
                ar.reason_code,
                ar.reason_category,
                ar.reason_description,
                ar.actual_value,
                ar.threshold_value,
                ar.unit,
                ar.severity,
                ar.source_layer
            FROM audit_decisions ad
            LEFT JOIN audit_reasons ar
                ON ar.audit_decision_id = ad.id
            WHERE ad.audit_run_id = ?
            ORDER BY
                ad.ticker,
                ar.id
            """,
            (audit_run_id,),
        ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:

        conn.close()


# ============================================================
# SELF TEST
# ============================================================

if __name__ == "__main__":
    print("Audit module loaded successfully.")
    print(f"Database: {DATABASE_PATH}")