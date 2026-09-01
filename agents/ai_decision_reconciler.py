
"""
AI Decision Reconciler
======================

Purpose
-------
Apply deterministic governance to a portfolio decision while retaining
the independent LLM review as advisory/audit information only.

IMPORTANT ARCHITECTURAL RULE
----------------------------
The deterministic decision and deterministic governance rules are
authoritative.

The LLM review is NOT authoritative.

Therefore:

    LLM ACCEPT      -> advisory only
    LLM CHALLENGE   -> advisory only
    LLM REJECT      -> advisory only
    LLM unavailable -> advisory information only
    LLM confidence  -> advisory information only

None of the above may change:

    - Reconciled Action
    - Automatic Approval
    - deterministic governance outcome

The purpose of this module is therefore to determine whether the
deterministic proposal is sufficiently governed to proceed.

The final portfolio decision layer may subsequently apply portfolio-level
allocation, position-sizing and other portfolio-aware rules.

Design principles
-----------------
1. Deterministic governance is the source of authority.
2. The LLM reviewer is an independent advisory signal.
3. LLM output is retained for auditability.
4. LLM output must never override deterministic governance.
5. Missing LLM review must not block an otherwise valid deterministic
   decision.
6. Weak deterministic evidence must still block automatic approval.
7. BUY MORE receives dedicated existing-holding governance.
8. BUY NEW with immature historical evidence may use its explicit
   deterministic exception.
9. REDUCE and SELL receive stronger deterministic evidence requirements.
10. HOLD remains the safe default when deterministic governance fails.
11. This module does not perform portfolio allocation.
12. Asset type is consumed from the supplied decision data. This module
    does not hard-code individual securities as stocks or ETFs.
"""

from __future__ import annotations

from typing import Any


# ============================================================
# Constants
# ============================================================

VALID_ACTIONS = {
    "BUY NEW",
    "BUY MORE",
    "HOLD",
    "REDUCE",
    "SELL",
}

VALID_ASSET_TYPES = {
    "STOCK",
    "ETF",
    "CASH",
}

VALID_REVIEW_DECISIONS = {
    "ACCEPT",
    "CHALLENGE",
    "REJECT",
}

# ------------------------------------------------------------
# General deterministic governance thresholds
# ------------------------------------------------------------

MIN_DETERMINISTIC_CONFIDENCE = 65.0
STRONG_DETERMINISTIC_CONFIDENCE = 80.0

MIN_EVIDENCE_SCORE = 60.0
STRONG_EVIDENCE_SCORE = 75.0
SELL_EVIDENCE_SCORE = 75.0

# ------------------------------------------------------------
# LLM thresholds
#
# These remain available for compatibility/audit reporting.
#
# THEY ARE NOT APPROVAL GATES.
# ------------------------------------------------------------

MIN_LLM_CONFIDENCE = 60.0
STRONG_LLM_CONFIDENCE = 75.0

# ------------------------------------------------------------
# BUY MORE governance
#
# These are deterministic requirements.
# ------------------------------------------------------------

BUY_MORE_MIN_EVIDENCE = 65.0
BUY_MORE_MIN_CONFIDENCE = 65.0
BUY_MORE_MIN_INVESTMENT_SCORE = 75.0
BUY_MORE_MAX_ALLOCATION_PERCENT = 20.0

BUY_MORE_SUPPORTING_SIGNALS = {
    "BUY",
    "STRONG BUY",
}

# ------------------------------------------------------------
# BUY NEW immature-history exception
# ------------------------------------------------------------

BUY_NEW_IMMATURE_MIN_EVIDENCE = 65.0
BUY_NEW_IMMATURE_MIN_INVESTMENT_SCORE = 85.0
BUY_NEW_IMMATURE_MIN_SCORE_BUCKET_WIN_RATE = 60.0
BUY_NEW_IMMATURE_MIN_SCORE_BUCKET_OBSERVATIONS = 20

# ------------------------------------------------------------
# REDUCE challenge / strength compatibility constants
#
# These remain deterministic. The word "challenge" refers to the
# historical governance path and does NOT mean that an LLM challenge
# can change the action.
# ------------------------------------------------------------

REDUCE_CHALLENGE_MIN_EVIDENCE = 65.0
REDUCE_CHALLENGE_MIN_CONFIDENCE = 65.0
REDUCE_CHALLENGE_MAX_INVESTMENT_SCORE = 40.0

REDUCE_SUPPORTING_SIGNALS = {
    "SELL",
    "STRONG SELL",
}

# ============================================================
# General helpers
# ============================================================


def _clean_text(
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


def _normalise_text(
    value: Any,
    default: str = "",
) -> str:
    """Safely normalise text to uppercase."""
    text = _clean_text(value, default)
    return text.upper() if text else default


def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    """Safely convert a value to float."""
    if value is None:
        return default

    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(
    value: Any,
    default: int = 0,
) -> int:
    """Safely convert a value to integer."""
    if value is None:
        return default

    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _clamp(
    value: Any,
    minimum: float = 0.0,
    maximum: float = 100.0,
) -> float:
    """Convert to float and clamp to a range."""
    number = _safe_float(value, minimum)
    return round(
        max(
            minimum,
            min(
                maximum,
                number,
            ),
        ),
        2,
    )


def _safe_bool(
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

    text = _normalise_text(value)

    if text in {
        "TRUE",
        "YES",
        "Y",
        "1",
    }:
        return True

    if text in {
        "FALSE",
        "NO",
        "N",
        "0",
    }:
        return False

    return default


def _get(
    data: dict[str, Any],
    *keys: str,
    default: Any = None,
) -> Any:
    """Return the first non-empty value for the supplied keys."""
    if not isinstance(data, dict):
        return default

    for key in keys:
        value = data.get(key)

        if value is None:
            continue

        if isinstance(value, str) and not value.strip():
            continue

        return value

    return default


def _normalise_action(
    value: Any,
) -> str:
    """
    Normalise a portfolio action.

    REDUCE 25%, REDUCE 50%, REDUCE 75% and REDUCE 100% all normalise
    to REDUCE for governance-category comparisons.
    """
    action = _normalise_text(
        value,
        "HOLD",
    )

    if action.startswith("REDUCE"):
        return "REDUCE"

    if action in VALID_ACTIONS:
        return action

    return "HOLD"


def _action_with_percentage(
    value: Any,
) -> str:
    """Return the original action text while normalising whitespace."""
    action = _clean_text(
        value,
        "HOLD",
    ).upper()

    if action.startswith("REDUCE"):
        return action

    if action in VALID_ACTIONS:
        return action

    return "HOLD"


# ============================================================
# Decision field extraction
# ============================================================


def get_proposed_action(
    decision: dict[str, Any],
) -> str:
    """Extract and normalise the deterministic proposed action."""
    value = _get(
        decision,
        "Proposed Action",
        "proposed_action",
        "Action",
        "action",
        "Final Decision",
        "final_decision",
        default="HOLD",
    )

    return _action_with_percentage(value)


def get_evidence_score(
    decision: dict[str, Any],
) -> float:
    """Extract deterministic evidence score."""
    evidence = _get(
        decision,
        "Evidence Assessment",
        "evidence_assessment",
        default={},
    )

    if not isinstance(evidence, dict):
        evidence = {}

    return _safe_float(
        _get(
            decision,
            "Evidence Score",
            "evidence_score",
            default=_get(
                evidence,
                "Evidence Score",
                "evidence_score",
                default=0.0,
            ),
        )
    )


def get_evidence_strength(
    decision: dict[str, Any],
) -> str:
    """Extract deterministic evidence strength."""
    evidence = _get(
        decision,
        "Evidence Assessment",
        "evidence_assessment",
        default={},
    )

    if not isinstance(evidence, dict):
        evidence = {}

    return _normalise_text(
        _get(
            decision,
            "Evidence Strength",
            "evidence_strength",
            default=_get(
                evidence,
                "Evidence Strength",
                "evidence_strength",
                default="UNKNOWN",
            ),
        ),
        "UNKNOWN",
    )


def get_deterministic_confidence(
    decision: dict[str, Any],
) -> float:
    """Extract deterministic confidence."""
    evidence = _get(
        decision,
        "Evidence Assessment",
        "evidence_assessment",
        default={},
    )

    if not isinstance(evidence, dict):
        evidence = {}

    return _clamp(
        _get(
            decision,
            "Confidence",
            "Deterministic Confidence",
            "deterministic_confidence",
            default=_get(
                evidence,
                "Confidence",
                "confidence",
                default=0.0,
            ),
        )
    )


def get_decision_support(
    decision: dict[str, Any],
) -> str:
    """Extract deterministic decision support classification."""
    evidence = _get(
        decision,
        "Evidence Assessment",
        "evidence_assessment",
        default={},
    )

    if not isinstance(evidence, dict):
        evidence = {}

    return _normalise_text(
        _get(
            decision,
            "Decision Support",
            "decision_support",
            default=_get(
                evidence,
                "Decision Support",
                "decision_support",
                default="UNKNOWN",
            ),
        ),
        "UNKNOWN",
    )


def get_investment_score(
    decision: dict[str, Any],
) -> float:
    """Extract investment score."""
    return _safe_float(
        _get(
            decision,
            "Investment Score",
            "investment_score",
            default=0.0,
        )
    )


def get_signal(
    decision: dict[str, Any],
) -> str:
    """Extract the deterministic technical signal."""

    evidence = _get(
        decision,
        "Evidence Assessment",
        "evidence_assessment",
        default={},
    )

    if not isinstance(evidence, dict):
        evidence = {}

    analysis = _get(
        decision,
        "Analysis",
        "analysis",
        default={},
    )

    if not isinstance(analysis, dict):
        analysis = {}

    return _normalise_text(
        _get(
            decision,
            # Preferred production/top-level locations
            "Signal",
            "signal",
            "Momentum Signal",
            "momentum_signal",

            # Nested evidence locations
            default=_get(
                evidence,
                "Signal",
                "signal",
                "Momentum Signal",
                "momentum_signal",

                # Nested analysis locations
                default=_get(
                    analysis,
                    "Signal",
                    "signal",
                    "Momentum Signal",
                    "momentum_signal",
                    default="",
                ),
            ),
        )
    )

def get_existing_holding(
    decision: dict[str, Any],
) -> bool:
    """Extract existing-holding status."""
    ownership = _get(
        decision,
        "Ownership",
        "ownership",
        default={},
    )

    if isinstance(ownership, dict):
        owned = _get(
            ownership,
            "owned",
            "Existing Holding",
            "existing_holding",
            default=None,
        )

        if owned is not None:
            return _safe_bool(
                owned,
                False,
            )

    return _safe_bool(
        _get(
            decision,
            "Existing Holding",
            "existing_holding",
            "Held?",
            "held",
            default=False,
        ),
        False,
    )


def get_allocation_percent(
    decision: dict[str, Any],
) -> float:
    """Extract current portfolio allocation percentage."""
    ownership = _get(
        decision,
        "Ownership",
        "ownership",
        default={},
    )

    if isinstance(ownership, dict):
        value = _get(
            ownership,
            "allocation_pct",
            "Allocation %",
            "Current Allocation %",
            "current_allocation_pct",
            default=None,
        )

        if value is not None:
            return _safe_float(value)

    return _safe_float(
        _get(
            decision,
            "Allocation %",
            "allocation_pct",
            "Current Allocation %",
            "current_allocation_pct",
            default=0.0,
        )
    )


def get_asset_type(
    decision: dict[str, Any],
) -> str:
    """
    Extract authoritative asset type supplied by the decision layer.

    This function deliberately does not infer asset type from ticker
    names. In particular, individual security names are never used to
    classify STOCK versus ETF.
    """
    asset_type = _normalise_text(
        _get(
            decision,
            "Asset Type",
            "asset_type",
            "Asset_Type",
            default="STOCK",
        ),
        "STOCK",
    )

    if asset_type == "EQUITY":
        asset_type = "STOCK"

    if asset_type in VALID_ASSET_TYPES:
        return asset_type

    return "STOCK"


def get_reason(
    decision: dict[str, Any],
) -> str:
    """Extract the deterministic decision reason."""
    return _clean_text(
        _get(
            decision,
            "Reason",
            "reason",
            "Decision Reason",
            "decision_reason",
            "Final Reason",
            "final_reason",
            default="",
        )
    )


def get_historical_observations(
    decision: dict[str, Any],
) -> int:
    """Extract historical signal observations."""
    intelligence = _get(
        decision,
        "Recommendation Intelligence",
        "recommendation_intelligence",
        default={},
    )

    if not isinstance(intelligence, dict):
        intelligence = {}

    return _safe_int(
        _get(
            decision,
            "Historical Signal Observations",
            "historical_signal_observations",
            default=_get(
                intelligence,
                "historical_signal_observations",
                "Historical Signal Observations",
                default=0,
            ),
        )
    )


def get_score_bucket_observations(
    decision: dict[str, Any],
) -> int:
    """Extract score-bucket observation count."""
    intelligence = _get(
        decision,
        "Recommendation Intelligence",
        "recommendation_intelligence",
        default={},
    )

    if not isinstance(intelligence, dict):
        intelligence = {}

    return _safe_int(
        _get(
            decision,
            "Score Bucket Observations",
            "score_bucket_observations",
            default=_get(
                intelligence,
                "score_bucket_observations",
                "Score Bucket Observations",
                default=0,
            ),
        )
    )


def get_score_bucket_win_rate(
    decision: dict[str, Any],
) -> float:
    """Extract score-bucket win rate."""
    intelligence = _get(
        decision,
        "Recommendation Intelligence",
        "recommendation_intelligence",
        default={},
    )

    if not isinstance(intelligence, dict):
        intelligence = {}

    return _safe_float(
        _get(
            decision,
            "Score Bucket Win Rate %",
            "score_bucket_win_rate_pct",
            default=_get(
                intelligence,
                "score_bucket_win_rate_pct",
                "Score Bucket Win Rate %",
                default=0.0,
            ),
        )
    )


# ============================================================
# LLM extraction
#
# These helpers remain deliberately available because the review
# is still retained as advisory/audit information.
#
# NONE of these values are used as deterministic approval gates.
# ============================================================


def get_llm_review(
    review: dict[str, Any],
) -> str:
    """Extract the advisory LLM review decision."""
    return _normalise_text(
        _get(
            review,
            "Review Decision",
            "review_decision",
            "LLM Review",
            "llm_review",
            "LLM Assessment",
            "llm_assessment",
            default="",
        )
    )


def get_llm_confidence(
    review: dict[str, Any],
) -> float:
    """Extract advisory LLM confidence."""
    return _clamp(
        _get(
            review,
            "LLM Confidence",
            "llm_confidence",
            "Confidence",
            "confidence",
            default=0.0,
        )
    )


def get_llm_challenge(
    review: dict[str, Any],
) -> bool:
    """Extract advisory LLM challenge status."""
    explicit = _get(
        review,
        "Challenge",
        "challenge",
        default=None,
    )

    if explicit is not None:
        return _safe_bool(
            explicit,
            False,
        )

    return get_llm_review(review) == "CHALLENGE"


def get_llm_reason(
    review: dict[str, Any],
) -> str:
    """Extract advisory LLM reasoning."""
    return _clean_text(
        _get(
            review,
            "Reason",
            "reason",
            "LLM Reason",
            "llm_reason",
            default="",
        )
    )


def review_indicates_material_contradiction(
    review: dict[str, Any],
) -> bool:
    """
    Detect whether the advisory LLM review describes a material concern.

    IMPORTANT:
        This function is informational only.

    It MUST NOT be used to alter the deterministic action.
    """
    if not isinstance(review, dict):
        return False

    if get_llm_challenge(review):
        return True

    text = _normalise_text(
        " ".join(
            [
                _clean_text(
                    review.get("Reason")
                ),
                _clean_text(
                    review.get("LLM Reason")
                ),
                _clean_text(
                    review.get("reason")
                ),
            ]
        )
    )

    contradiction_terms = (
        "CONTRADICTORY",
        "CONTRADICTION",
        "CONFLICTING EVIDENCE",
        "MATERIAL RISK",
        "MATERIAL NEGATIVE",
        "UNSUPPORTED",
        "NOT SUPPORTED",
        "ESSENTIAL GAP",
    )

    return any(
        term in text
        for term in contradiction_terms
    )


# ============================================================
# Historical evidence helpers
# ============================================================


def history_is_immature(
    decision: dict[str, Any],
) -> bool:
    """
    Determine whether historical evidence is immature.

    Immature history means there is insufficient historical evidence
    to treat the learning layer as mature evidence.

    It is NOT itself negative evidence.
    """
    observations = get_historical_observations(
        decision
    )

    bucket_observations = get_score_bucket_observations(
        decision
    )

    return (
        observations
        < BUY_NEW_IMMATURE_MIN_SCORE_BUCKET_OBSERVATIONS
        or
        bucket_observations
        < BUY_NEW_IMMATURE_MIN_SCORE_BUCKET_OBSERVATIONS
    )


def buy_new_is_strong_enough_to_survive_immature_history(
    decision: dict[str, Any],
    review: dict[str, Any] | None = None,
) -> bool:
    """
    Determine whether BUY NEW qualifies for the deterministic
    immature-history exception.

    NOTE:
        ``review`` is accepted for API compatibility only.

        The LLM review is intentionally NOT inspected here.

    Requirements
    ------------
    - BUY NEW proposal
    - immature historical evidence
    - evidence score >= 65
    - deterministic confidence >= 70
    - decision support is SUPPORTED or CONDITIONAL
    - investment score >= 85
    - score bucket has >= 20 observations
    - score bucket win rate >= 60%
    """
    del review

    if (
        _normalise_action(
            get_proposed_action(decision)
        )
        != "BUY NEW"
    ):
        return False

    if not history_is_immature(
        decision
    ):
        return False

    evidence_score = get_evidence_score(
        decision
    )

    confidence = get_deterministic_confidence(
        decision
    )

    support = get_decision_support(
        decision
    )

    investment_score = get_investment_score(
        decision
    )

    bucket_observations = get_score_bucket_observations(
        decision
    )

    bucket_win_rate = get_score_bucket_win_rate(
        decision
    )

    if evidence_score < BUY_NEW_IMMATURE_MIN_EVIDENCE:
        return False

    if confidence < MIN_DETERMINISTIC_CONFIDENCE:
        return False

    if support not in {
        "SUPPORTED",
        "CONDITIONAL",
    }:
        return False

    if investment_score < BUY_NEW_IMMATURE_MIN_INVESTMENT_SCORE:
        return False

    if (
        bucket_observations
        < BUY_NEW_IMMATURE_MIN_SCORE_BUCKET_OBSERVATIONS
    ):
        return False

    if (
        bucket_win_rate
        < BUY_NEW_IMMATURE_MIN_SCORE_BUCKET_WIN_RATE
    ):
        return False

    return True


# ============================================================
# Deterministic governance helpers
# ============================================================


def _is_high_impact_action(
    action: str,
) -> bool:
    """Return True for actions requiring enhanced scrutiny."""
    return _normalise_action(action) in {
        "BUY MORE",
        "REDUCE",
        "SELL",
    }


def _requires_strong_evidence(
    action: str,
) -> bool:
    """
    Return True where strong deterministic evidence is required.

    BUY NEW has a lower general evidence requirement because it has
    the explicit immature-history exception.
    """
    return _normalise_action(action) in {
        "BUY MORE",
        "REDUCE",
        "SELL",
    }


def _deterministic_action_is_weak(
    decision: dict[str, Any],
) -> bool:
    """
    Determine whether the deterministic proposal lacks the minimum
    evidence required for automatic approval.

    This is entirely deterministic.
    """
    evidence_score = get_evidence_score(
        decision
    )

    confidence = get_deterministic_confidence(
        decision
    )

    support = get_decision_support(
        decision
    )

    if evidence_score < MIN_EVIDENCE_SCORE:
        return True

    if confidence < MIN_DETERMINISTIC_CONFIDENCE:
        return True

    if support == "NOT SUPPORTED":
        return True

    return False


def _reduce_is_strong_enough_to_survive_challenge(
    decision: dict[str, Any],
    existing_holding: bool,
) -> bool:
    """
    Determine whether a deterministic REDUCE proposal is strong enough
    to remain a REDUCE action.

    This function has no dependency on LLM output.

    The name is retained for compatibility with existing tests and
    callers. "Challenge" here refers to the historical governance
    concept, not an LLM override.
    """
    if not existing_holding:
        return False

    evidence_score = get_evidence_score(
        decision
    )

    deterministic_confidence = get_deterministic_confidence(
        decision
    )

    decision_support = get_decision_support(
        decision
    )

    investment_score = get_investment_score(
        decision
    )

    signal = get_signal(
        decision
    )

    if evidence_score < REDUCE_CHALLENGE_MIN_EVIDENCE:
        return False

    if (
        deterministic_confidence
        < REDUCE_CHALLENGE_MIN_CONFIDENCE
    ):
        return False

    if decision_support != "SUPPORTED":
        return False

    weak_investment_case = (
        investment_score
        <= REDUCE_CHALLENGE_MAX_INVESTMENT_SCORE
    )

    bearish_signal = (
        signal
        in REDUCE_SUPPORTING_SIGNALS
    )

    return (
        weak_investment_case
        or
        bearish_signal
    )


def _record_failed_check(
    failed_checks: list[dict[str, Any]],
    *,
    check_def: str,
    check_code: str,
    reason: str,
    actual_value: Any,
    threshold_value: Any,
    unit: str,
) -> None:
    """Record one deterministic governance failure."""
    failed_checks.append(
        {
            "check_def": check_def,
            "check_code": check_code,
            "reason": reason,
            "actual_value": actual_value,
            "threshold_value": threshold_value,
            "unit": unit,
            "source_layer": "reconciliation",
        }
    )


# ============================================================
# BUY MORE deterministic governance
# ============================================================


def _evaluate_buy_more_governance(
    decision: dict[str, Any],
    *,
    existing_holding: bool,
) -> tuple[
    bool,
    list[str],
    list[str],
    list[dict[str, Any]],
]:
    """
    Evaluate BUY MORE using deterministic rules only.

    Returns
    -------
    qualified, flags, reasons, failed_checks
    """
    flags: list[str] = []
    reasons: list[str] = []
    failed_checks: list[dict[str, Any]] = []

    allocation_pct = get_allocation_percent(
        decision
    )

    evidence_score = get_evidence_score(
        decision
    )

    deterministic_confidence = (
        get_deterministic_confidence(
            decision
        )
    )

    investment_score = get_investment_score(
        decision
    )

    signal = get_signal(
        decision
    )

    if not existing_holding:
        flags.append(
            "BUY MORE REQUIRES EXISTING HOLDING"
        )

        reasons.append(
            "BUY MORE requires an existing holding."
        )

        _record_failed_check(
            failed_checks,
            check_def="BUY_MORE_GOVERNANCE",
            check_code=(
                "BUY_MORE_REQUIRES_EXISTING_HOLDING"
            ),
            reason=(
                "BUY MORE REQUIRES EXISTING HOLDING"
            ),
            actual_value=existing_holding,
            threshold_value=True,
            unit="boolean",
        )

    if allocation_pct > BUY_MORE_MAX_ALLOCATION_PERCENT:
        flags.append(
            "BUY MORE ALLOCATION ABOVE LIMIT"
        )

        reasons.append(
            f"Current allocation of {allocation_pct:.2f}% "
            f"exceeds the maximum permitted allocation of "
            f"{BUY_MORE_MAX_ALLOCATION_PERCENT:.2f}%."
        )

        _record_failed_check(
            failed_checks,
            check_def="BUY_MORE_GOVERNANCE",
            check_code=(
                "BUY_MORE_ALLOCATION_ABOVE_LIMIT"
            ),
            reason=(
                "BUY MORE allocation exceeds the maximum permitted "
                "portfolio allocation."
            ),
            actual_value=allocation_pct,
            threshold_value=BUY_MORE_MAX_ALLOCATION_PERCENT,
            unit="percent",
        )

    if evidence_score < BUY_MORE_MIN_EVIDENCE:
        flags.append(
            "BUY MORE EVIDENCE BELOW THRESHOLD"
        )

        reasons.append(
            f"Evidence score of {evidence_score:.2f} is below "
            f"the BUY MORE minimum of "
            f"{BUY_MORE_MIN_EVIDENCE:.2f}."
        )

        _record_failed_check(
            failed_checks,
            check_def="BUY_MORE_GOVERNANCE",
            check_code=(
                "BUY_MORE_EVIDENCE_BELOW_THRESHOLD"
            ),
            reason=(
                "BUY MORE EVIDENCE BELOW THRESHOLD"
            ),
            actual_value=evidence_score,
            threshold_value=BUY_MORE_MIN_EVIDENCE,
            unit="score",
        )

    if (
        deterministic_confidence
        < BUY_MORE_MIN_CONFIDENCE
    ):
        flags.append(
            "BUY MORE CONFIDENCE BELOW THRESHOLD"
        )

        reasons.append(
            f"Deterministic confidence of "
            f"{deterministic_confidence:.2f} is below "
            f"the BUY MORE minimum of "
            f"{BUY_MORE_MIN_CONFIDENCE:.2f}."
        )

        _record_failed_check(
            failed_checks,
            check_def="BUY_MORE_GOVERNANCE",
            check_code=(
                "BUY_MORE_CONFIDENCE_BELOW_THRESHOLD"
            ),
            reason=(
                "BUY MORE CONFIDENCE BELOW THRESHOLD"
            ),
            actual_value=deterministic_confidence,
            threshold_value=BUY_MORE_MIN_CONFIDENCE,
            unit="percent",
        )

    if investment_score < BUY_MORE_MIN_INVESTMENT_SCORE:
        flags.append(
            "BUY MORE INVESTMENT SCORE BELOW THRESHOLD"
        )

        reasons.append(
            f"Investment score of {investment_score:.2f} "
            f"is below the BUY MORE minimum of "
            f"{BUY_MORE_MIN_INVESTMENT_SCORE:.2f}."
        )

        _record_failed_check(
            failed_checks,
            check_def="BUY_MORE_GOVERNANCE",
            check_code=(
                "BUY_MORE_INVESTMENT_SCORE_BELOW_THRESHOLD"
            ),
            reason=(
                "BUY MORE INVESTMENT SCORE BELOW THRESHOLD"
            ),
            actual_value=investment_score,
            threshold_value=BUY_MORE_MIN_INVESTMENT_SCORE,
            unit="score",
        )

    if signal not in BUY_MORE_SUPPORTING_SIGNALS:
        flags.append(
            "BUY MORE SIGNAL NOT SUPPORTIVE"
        )

        reasons.append(
            f"Signal '{signal or 'UNKNOWN'}' is not a "
            "BUY or STRONG BUY signal."
        )

        _record_failed_check(
            failed_checks,
            check_def="BUY_MORE_GOVERNANCE",
            check_code=(
                "BUY_MORE_SIGNAL_NOT_SUPPORTIVE"
            ),
            reason=(
                "BUY MORE SIGNAL NOT SUPPORTIVE"
            ),
            actual_value=signal,
            threshold_value="BUY / STRONG BUY",
            unit="signal",
        )

    qualified = not failed_checks

    return (
        qualified,
        flags,
        reasons,
        failed_checks,
    )


# ============================================================
# Result construction
# ============================================================


def _build_result(
    *,
    status: str,
    reconciled_action: str,
    deterministic_action: str,
    proposed_action: str,
    llm_review: str,
    llm_confidence: float,
    evidence_score: float,
    evidence_strength: str,
    deterministic_confidence: float,
    decision_support: str,
    existing_holding: bool,
    asset_type: str,
    governance_flags: list[str],
    reasons: list[str],
    automatic_approval: bool,
    failed_checks: list[dict[str, Any]] | None = None,
    governance_reason_code: str = "",
    governance_reason: str = "",
    llm_reason: str = "",
    llm_challenge: bool = False,
) -> dict[str, Any]:
    """
    Build the stable reconciliation result.

    Reconciled Action is determined by deterministic governance.

    LLM fields are retained for audit/advisory purposes only.
    """
    if failed_checks is None:
        failed_checks = []

    return {
        "Reconciliation Status":
            status,

        "Reconciled Action":
            reconciled_action,

        "Deterministic Action":
            deterministic_action,

        "Proposed Action":
            proposed_action,

        "LLM Review":
            llm_review,

        "LLM Confidence":
            llm_confidence,

        "LLM Challenge":
            llm_challenge,

        "LLM Reason":
            llm_reason,

        "Evidence Score":
            evidence_score,

        "Evidence Strength":
            evidence_strength,

        "Deterministic Confidence":
            deterministic_confidence,

        "Decision Support":
            decision_support,

        "Existing Holding":
            existing_holding,

        "Asset Type":
            asset_type,

        "Governance Flags":
            governance_flags,

        "Governance Reasons":
            reasons,

        "Governance Failed Checks":
            failed_checks,

        "Governance Failed Check Count":
            len(failed_checks),

        "Failed Checks":
            failed_checks,

        "Failed Check Count":
            len(failed_checks),

        "Governance Reason Code":
            governance_reason_code,

        "Governance Reason":
            governance_reason,

        "Automatic Approval":
            automatic_approval,

        # Explicit architecture marker.
        "Decision Authority":
            "DETERMINISTIC GOVERNANCE",

        "LLM Role":
            "ADVISORY ONLY",

        "Final Decision":
            None,

        "Decision Layer Status":
            "RECONCILIATION ONLY",
    }


# ============================================================
# Main reconciliation
# ============================================================


def reconcile_decision(
    decision: dict,
    review: dict,
) -> dict:
    """
    Reconcile one deterministic decision with one advisory LLM review.

    IMPORTANT
    ---------
    The LLM review does not participate in determining the final action.

    The deterministic proposal is evaluated against deterministic
    governance rules.

    The resulting action is therefore a function of the deterministic
    decision only:

        Reconciled Action = f(deterministic decision)

    and NOT:

        Reconciled Action = f(deterministic decision, LLM review)

    The LLM review is copied into the result for auditability.
    """

    if not isinstance(
        decision,
        dict,
    ):
        decision = {}

    if not isinstance(
        review,
        dict,
    ):
        review = {}

    # --------------------------------------------------------
    # Extract deterministic fields.
    # --------------------------------------------------------

    proposed_action = get_proposed_action(
        decision
    )

    deterministic_action = _normalise_action(
        proposed_action
    )

    evidence_score = get_evidence_score(
        decision
    )

    evidence_strength = get_evidence_strength(
        decision
    )

    deterministic_confidence = (
        get_deterministic_confidence(
            decision
        )
    )

    decision_support = get_decision_support(
        decision
    )

    existing_holding = get_existing_holding(
        decision
    )

    asset_type = get_asset_type(
        decision
    )

    investment_score = get_investment_score(
        decision
    )

    signal = get_signal(
        decision
    )

    # --------------------------------------------------------
    # Extract LLM fields.
    #
    # These are advisory only.
    # --------------------------------------------------------

    llm_review = get_llm_review(
        review
    )

    llm_confidence = get_llm_confidence(
        review
    )

    llm_challenge = get_llm_challenge(
        review
    )

    llm_reason = get_llm_reason(
        review
    )

    governance_flags: list[str] = []
    reasons: list[str] = []
    failed_checks: list[dict[str, Any]] = []

    # --------------------------------------------------------
    # Explicitly record the architecture.
    # --------------------------------------------------------

    governance_flags.append(
        "DETERMINISTIC GOVERNANCE AUTHORITATIVE"
    )

    reasons.append(
        "The portfolio action is determined by deterministic "
        "governance. The independent LLM review is advisory only."
    )

    # --------------------------------------------------------
    # Record advisory LLM information.
    #
    # None of these conditions changes the action.
    # --------------------------------------------------------

    if not llm_review:
        governance_flags.append(
            "LLM REVIEW UNAVAILABLE"
        )

        reasons.append(
            "Independent LLM review is unavailable; this does not "
            "affect deterministic governance."
        )

    elif llm_review == "ACCEPT":
        governance_flags.append(
            "LLM ADVISORY ACCEPT"
        )

        reasons.append(
            "The independent LLM review supports the deterministic "
            "proposal as an advisory signal only."
        )

    elif llm_review == "CHALLENGE":
        governance_flags.append(
            "LLM ADVISORY CHALLENGE"
        )

        reasons.append(
            "The independent LLM review challenges the deterministic "
            "proposal; the challenge is retained for audit purposes "
            "and does not override deterministic governance."
        )

    elif llm_review == "REJECT":
        governance_flags.append(
            "LLM ADVISORY REJECT"
        )

        reasons.append(
            "The independent LLM review rejects the deterministic "
            "proposal; the rejection is retained for audit purposes "
            "and does not override deterministic governance."
        )

    else:
        governance_flags.append(
            "LLM ADVISORY RESULT UNKNOWN"
        )

        reasons.append(
            f"The LLM returned an unrecognised advisory review value "
            f"'{llm_review}'. It has no effect on deterministic "
            f"governance."
        )

    if llm_challenge:
        governance_flags.append(
            "LLM CHALLENGE ADVISORY ONLY"
        )

    if llm_confidence < MIN_LLM_CONFIDENCE:
        governance_flags.append(
            "LOW LLM CONFIDENCE ADVISORY ONLY"
        )

    # --------------------------------------------------------
    # HOLD
    #
    # HOLD is deterministic and does not require LLM approval.
    # --------------------------------------------------------

    if deterministic_action == "HOLD":
        reasons.append(
            "The deterministic proposal is HOLD. No LLM approval "
            "is required to retain the HOLD action."
        )

        return _build_result(
            status="SUPPORTED",
            reconciled_action="HOLD",
            deterministic_action=deterministic_action,
            proposed_action=proposed_action,
            llm_review=llm_review,
            llm_confidence=llm_confidence,
            llm_reason=llm_reason,
            llm_challenge=llm_challenge,
            evidence_score=evidence_score,
            evidence_strength=evidence_strength,
            deterministic_confidence=deterministic_confidence,
            decision_support=decision_support,
            existing_holding=existing_holding,
            asset_type=asset_type,
            governance_flags=governance_flags,
            reasons=reasons,
            automatic_approval=True,
            failed_checks=[],
            governance_reason_code=(
                "DETERMINISTIC_HOLD"
            ),
            governance_reason=(
                "HOLD is the deterministic portfolio action and "
                "requires no LLM approval."
            ),
        )

    # --------------------------------------------------------
    # Asset-specific defensive rule.
    #
    # Cash should not be given a transactional stock action by this
    # reconciliation layer.
    # --------------------------------------------------------

    if asset_type == "CASH":
        governance_flags.append(
            "CASH ACTION NOT PERMITTED"
        )

        reasons.append(
            "CASH is not eligible for stock/ETF BUY, BUY MORE, "
            "REDUCE or SELL governance."
        )

        _record_failed_check(
            failed_checks,
            check_def="reconcile_decision",
            check_code="CASH_ACTION_NOT_PERMITTED",
            reason=(
                "Cash cannot be processed as a stock/ETF transaction."
            ),
            actual_value=proposed_action,
            threshold_value="HOLD",
            unit="action",
        )

        return _build_result(
            status="REVIEW REQUIRED",
            reconciled_action="HOLD",
            deterministic_action=deterministic_action,
            proposed_action=proposed_action,
            llm_review=llm_review,
            llm_confidence=llm_confidence,
            llm_reason=llm_reason,
            llm_challenge=llm_challenge,
            evidence_score=evidence_score,
            evidence_strength=evidence_strength,
            deterministic_confidence=deterministic_confidence,
            decision_support=decision_support,
            existing_holding=existing_holding,
            asset_type=asset_type,
            governance_flags=governance_flags,
            reasons=reasons,
            automatic_approval=False,
            failed_checks=failed_checks,
            governance_reason_code=(
                "CASH_ACTION_NOT_PERMITTED"
            ),
            governance_reason=(
                "Cash cannot receive a stock/ETF transaction action."
            ),
        )

    # --------------------------------------------------------
    # BUY MORE
    #
    # Every check is deterministic.
    #
    # NO LLM REVIEW CHECK.
    # NO LLM CONFIDENCE CHECK.
    # NO LLM CONTRADICTION CHECK.
    # --------------------------------------------------------

    if deterministic_action == "BUY MORE":
        (
            buy_more_qualified,
            buy_more_flags,
            buy_more_reasons,
            buy_more_failed_checks,
        ) = _evaluate_buy_more_governance(
            decision,
            existing_holding=existing_holding,
        )

        governance_flags.extend(
            buy_more_flags
        )

        reasons.extend(
            buy_more_reasons
        )

        failed_checks.extend(
            buy_more_failed_checks
        )

        if buy_more_qualified:
            governance_flags.append(
                "BUY MORE GOVERNANCE PASSED"
            )

            reasons.append(
                "BUY MORE satisfies all deterministic existing-holding, "
                "allocation, evidence, confidence, investment-score and "
                "signal requirements."
            )

            return _build_result(
                status="SUPPORTED",
                reconciled_action="BUY MORE",
                deterministic_action=deterministic_action,
                proposed_action=proposed_action,
                llm_review=llm_review,
                llm_confidence=llm_confidence,
                llm_reason=llm_reason,
                llm_challenge=llm_challenge,
                evidence_score=evidence_score,
                evidence_strength=evidence_strength,
                deterministic_confidence=deterministic_confidence,
                decision_support=decision_support,
                existing_holding=existing_holding,
                asset_type=asset_type,
                governance_flags=governance_flags,
                reasons=reasons,
                automatic_approval=True,
                failed_checks=[],
                governance_reason_code=(
                    "BUY_MORE_DETERMINISTIC_GOVERNANCE_PASSED"
                ),
                governance_reason=(
                    "BUY MORE was automatically approved because all "
                    "deterministic BUY MORE governance requirements passed."
                ),
            )

        governance_flags.append(
            "BUY MORE GOVERNANCE REQUIREMENTS NOT MET"
        )

        reasons.append(
            "BUY MORE did not satisfy the complete deterministic "
            "governance requirements."
        )

        return _build_result(
            status="REVIEW REQUIRED",
            reconciled_action="HOLD",
            deterministic_action=deterministic_action,
            proposed_action=proposed_action,
            llm_review=llm_review,
            llm_confidence=llm_confidence,
            llm_reason=llm_reason,
            llm_challenge=llm_challenge,
            evidence_score=evidence_score,
            evidence_strength=evidence_strength,
            deterministic_confidence=deterministic_confidence,
            decision_support=decision_support,
            existing_holding=existing_holding,
            asset_type=asset_type,
            governance_flags=governance_flags,
            reasons=reasons,
            automatic_approval=False,
            failed_checks=failed_checks,
            governance_reason_code=(
                "BUY_MORE_DETERMINISTIC_GOVERNANCE_FAILED"
            ),
            governance_reason=(
                "BUY MORE was not automatically approved because "
                "one or more deterministic BUY MORE governance "
                "requirements failed."
            ),
        )

    # --------------------------------------------------------
    # BUY NEW immature-history exception.
    #
    # This is entirely deterministic.
    # --------------------------------------------------------

    buy_new_immature_history_override = (
        buy_new_is_strong_enough_to_survive_immature_history(
            decision=decision,
            review=review,
        )
    )

    if (
        deterministic_action == "BUY NEW"
        and
        buy_new_immature_history_override
    ):
        governance_flags.append(
            "BUY NEW WITH IMMATURE HISTORICAL EVIDENCE"
        )

        reasons.append(
            "BUY NEW qualifies for the deterministic immature-history "
            "exception because the current investment case is strong "
            "enough despite immature historical evidence."
        )

        return _build_result(
            status="SUPPORTED WITH IMMATURE EVIDENCE",
            reconciled_action="BUY NEW",
            deterministic_action=deterministic_action,
            proposed_action=proposed_action,
            llm_review=llm_review,
            llm_confidence=llm_confidence,
            llm_reason=llm_reason,
            llm_challenge=llm_challenge,
            evidence_score=evidence_score,
            evidence_strength=evidence_strength,
            deterministic_confidence=deterministic_confidence,
            decision_support=decision_support,
            existing_holding=existing_holding,
            asset_type=asset_type,
            governance_flags=governance_flags,
            reasons=reasons,
            automatic_approval=True,
            failed_checks=[],
            governance_reason_code=(
                "BUY_NEW_IMMATURE_HISTORY"
            ),
            governance_reason=(
                "BUY NEW approved under the deterministic immature-history "
                "exception. LLM review is advisory only."
            ),
        )

    # --------------------------------------------------------
    # General deterministic minimum gate.
    #
    # This is the normal gate for BUY NEW / REDUCE / SELL.
    # --------------------------------------------------------

    weak_deterministic = _deterministic_action_is_weak(
        decision
    )

    if weak_deterministic:
        governance_flags.append(
            "WEAK DETERMINISTIC EVIDENCE"
        )

        reasons.append(
            "Deterministic evidence is insufficient to support "
            "automatic portfolio change."
        )

        if evidence_score < MIN_EVIDENCE_SCORE:
            _record_failed_check(
                failed_checks,
                check_def="reconcile_decision",
                check_code=(
                    "WEAK_DETERMINISTIC_EVIDENCE"
                ),
                reason=(
                    "Deterministic evidence is below the minimum "
                    "evidence threshold."
                ),
                actual_value=evidence_score,
                threshold_value=MIN_EVIDENCE_SCORE,
                unit="score",
            )

        if (
            deterministic_confidence
            < MIN_DETERMINISTIC_CONFIDENCE
        ):
            _record_failed_check(
                failed_checks,
                check_def="reconcile_decision",
                check_code=(
                    "WEAK_DETERMINISTIC_CONFIDENCE"
                ),
                reason=(
                    "Deterministic confidence is below the minimum "
                    "confidence threshold."
                ),
                actual_value=deterministic_confidence,
                threshold_value=MIN_DETERMINISTIC_CONFIDENCE,
                unit="percent",
            )

        if decision_support == "NOT SUPPORTED":
            _record_failed_check(
                failed_checks,
                check_def="reconcile_decision",
                check_code=(
                    "DETERMINISTIC_DECISION_NOT_SUPPORTED"
                ),
                reason=(
                    "The deterministic decision support classification "
                    "is NOT SUPPORTED."
                ),
                actual_value=decision_support,
                threshold_value="SUPPORTED",
                unit="decision support",
            )

        return _build_result(
            status="REVIEW REQUIRED",
            reconciled_action="HOLD",
            deterministic_action=deterministic_action,
            proposed_action=proposed_action,
            llm_review=llm_review,
            llm_confidence=llm_confidence,
            llm_reason=llm_reason,
            llm_challenge=llm_challenge,
            evidence_score=evidence_score,
            evidence_strength=evidence_strength,
            deterministic_confidence=deterministic_confidence,
            decision_support=decision_support,
            existing_holding=existing_holding,
            asset_type=asset_type,
            governance_flags=governance_flags,
            reasons=reasons,
            automatic_approval=False,
            failed_checks=failed_checks,
            governance_reason_code=(
                "DETERMINISTIC_MINIMUM_GATE_FAILED"
            ),
            governance_reason=(
                "The deterministic proposal did not satisfy the "
                "minimum evidence, confidence and decision-support "
                "requirements."
            ),
        )

    # --------------------------------------------------------
    # Strong evidence gate for high-impact deterministic actions.
    #
    # Again, this is entirely deterministic.
    # --------------------------------------------------------

    if (
        _requires_strong_evidence(
            deterministic_action
        )
        and
        evidence_score < STRONG_EVIDENCE_SCORE
    ):
        governance_flags.append(
            "STRONG EVIDENCE REQUIRED"
        )

        reasons.append(
            f"{deterministic_action} requires deterministic evidence "
            f"of at least {STRONG_EVIDENCE_SCORE:.2f}."
        )

        _record_failed_check(
            failed_checks,
            check_def="reconcile_decision",
            check_code=(
                "DETERMINISTIC_EVIDENCE_THRESHOLD"
            ),
            reason=(
                "Strong deterministic evidence is required for this action."
            ),
            actual_value=evidence_score,
            threshold_value=STRONG_EVIDENCE_SCORE,
            unit="score",
        )

        return _build_result(
            status="REVIEW REQUIRED",
            reconciled_action="HOLD",
            deterministic_action=deterministic_action,
            proposed_action=proposed_action,
            llm_review=llm_review,
            llm_confidence=llm_confidence,
            llm_reason=llm_reason,
            llm_challenge=llm_challenge,
            evidence_score=evidence_score,
            evidence_strength=evidence_strength,
            deterministic_confidence=deterministic_confidence,
            decision_support=decision_support,
            existing_holding=existing_holding,
            asset_type=asset_type,
            governance_flags=governance_flags,
            reasons=reasons,
            automatic_approval=False,
            failed_checks=failed_checks,
            governance_reason_code=(
                "DETERMINISTIC_EVIDENCE_THRESHOLD"
            ),
            governance_reason=(
                f"{deterministic_action} was not automatically approved "
                f"because deterministic evidence of {evidence_score:.2f} "
                f"is below the required strong-evidence threshold of "
                f"{STRONG_EVIDENCE_SCORE:.2f}."
            ),
        )

    # --------------------------------------------------------
    # SELL requires the strongest deterministic evidence.
    # --------------------------------------------------------

    if (
        deterministic_action == "SELL"
        and
        evidence_score < SELL_EVIDENCE_SCORE
    ):
        governance_flags.append(
            "SELL EVIDENCE BELOW THRESHOLD"
        )

        reasons.append(
            f"SELL requires deterministic evidence of at least "
            f"{SELL_EVIDENCE_SCORE:.2f}."
        )

        _record_failed_check(
            failed_checks,
            check_def="reconcile_decision",
            check_code=(
                "SELL_EVIDENCE_BELOW_THRESHOLD"
            ),
            reason=(
                "SELL requires stronger deterministic evidence."
            ),
            actual_value=evidence_score,
            threshold_value=SELL_EVIDENCE_SCORE,
            unit="score",
        )

        return _build_result(
            status="REVIEW REQUIRED",
            reconciled_action="HOLD",
            deterministic_action=deterministic_action,
            proposed_action=proposed_action,
            llm_review=llm_review,
            llm_confidence=llm_confidence,
            llm_reason=llm_reason,
            llm_challenge=llm_challenge,
            evidence_score=evidence_score,
            evidence_strength=evidence_strength,
            deterministic_confidence=deterministic_confidence,
            decision_support=decision_support,
            existing_holding=existing_holding,
            asset_type=asset_type,
            governance_flags=governance_flags,
            reasons=reasons,
            automatic_approval=False,
            failed_checks=failed_checks,
            governance_reason_code=(
                "SELL_EVIDENCE_THRESHOLD"
            ),
            governance_reason=(
                "SELL was not approved because deterministic evidence "
                "is below the required SELL threshold."
            ),
        )

    # --------------------------------------------------------
    # REDUCE.
    #
    # A REDUCE is allowed when the deterministic proposal itself
    # is sufficiently governed.
    #
    # The LLM cannot veto it.
    # --------------------------------------------------------

    if deterministic_action == "REDUCE":
        if not existing_holding:
            governance_flags.append(
                "REDUCE REQUIRES EXISTING HOLDING"
            )

            reasons.append(
                "REDUCE requires an existing holding."
            )

            _record_failed_check(
                failed_checks,
                check_def="reconcile_decision",
                check_code=(
                    "REDUCE_REQUIRES_EXISTING_HOLDING"
                ),
                reason=(
                    "REDUCE requires an existing holding."
                ),
                actual_value=existing_holding,
                threshold_value=True,
                unit="boolean",
            )

            return _build_result(
                status="REVIEW REQUIRED",
                reconciled_action="HOLD",
                deterministic_action=deterministic_action,
                proposed_action=proposed_action,
                llm_review=llm_review,
                llm_confidence=llm_confidence,
                llm_reason=llm_reason,
                llm_challenge=llm_challenge,
                evidence_score=evidence_score,
                evidence_strength=evidence_strength,
                deterministic_confidence=deterministic_confidence,
                decision_support=decision_support,
                existing_holding=existing_holding,
                asset_type=asset_type,
                governance_flags=governance_flags,
                reasons=reasons,
                automatic_approval=False,
                failed_checks=failed_checks,
                governance_reason_code=(
                    "REDUCE_REQUIRES_EXISTING_HOLDING"
                ),
                governance_reason=(
                    "REDUCE was not approved because the asset is "
                    "not an existing holding."
                ),
            )

        # ----------------------------------------------------
        # Deterministic REDUCE governance has passed the general
        # minimum and strong-evidence gates above.
        # ----------------------------------------------------

        governance_flags.append(
            "REDUCE DETERMINISTIC GOVERNANCE PASSED"
        )

        reasons.append(
            "REDUCE satisfies the deterministic governance requirements."
        )

        return _build_result(
            status="SUPPORTED",
            reconciled_action=proposed_action,
            deterministic_action=deterministic_action,
            proposed_action=proposed_action,
            llm_review=llm_review,
            llm_confidence=llm_confidence,
            llm_reason=llm_reason,
            llm_challenge=llm_challenge,
            evidence_score=evidence_score,
            evidence_strength=evidence_strength,
            deterministic_confidence=deterministic_confidence,
            decision_support=decision_support,
            existing_holding=existing_holding,
            asset_type=asset_type,
            governance_flags=governance_flags,
            reasons=reasons,
            automatic_approval=True,
            failed_checks=[],
            governance_reason_code=(
                "REDUCE_DETERMINISTIC_GOVERNANCE_PASSED"
            ),
            governance_reason=(
                "REDUCE was approved by deterministic governance. "
                "Any LLM challenge or rejection is advisory only."
            ),
        )


    # --------------------------------------------------------
    # SELL.
    #
    # SELL is equivalent to REDUCE 100%.
    #
    # All SELL governance is deterministic. The LLM cannot
    # veto or downgrade a fully governed SELL.
    #
    # The general minimum gate, strong-evidence gate and
    # SELL-specific evidence gate above have already passed
    # before execution reaches this block.
    # --------------------------------------------------------

    if deterministic_action == "SELL":
        if not existing_holding:
            governance_flags.append(
                "SELL REQUIRES EXISTING HOLDING"
            )
            reasons.append(
                "SELL requires an existing holding."
            )

            _record_failed_check(
                failed_checks,
                check_def="reconcile_decision",
                check_code=(
                    "SELL_REQUIRES_EXISTING_HOLDING"
                ),
                reason=(
                    "SELL requires an existing holding."
                ),
                actual_value=existing_holding,
                threshold_value=True,
                unit="boolean",
            )

            return _build_result(
                status="REVIEW REQUIRED",
                reconciled_action="HOLD",
                deterministic_action=deterministic_action,
                proposed_action=proposed_action,
                llm_review=llm_review,
                llm_confidence=llm_confidence,
                llm_reason=llm_reason,
                llm_challenge=llm_challenge,
                evidence_score=evidence_score,
                evidence_strength=evidence_strength,
                deterministic_confidence=deterministic_confidence,
                decision_support=decision_support,
                existing_holding=existing_holding,
                asset_type=asset_type,
                governance_flags=governance_flags,
                reasons=reasons,
                automatic_approval=False,
                failed_checks=failed_checks,
                governance_reason_code=(
                    "SELL_REQUIRES_EXISTING_HOLDING"
                ),
                governance_reason=(
                    "SELL was not approved because the asset is "
                    "not an existing holding."
                ),
            )

        # ----------------------------------------------------
        # Deterministic SELL governance has passed all gates
        # above, including the SELL-specific evidence threshold.
        #
        # SELL represents a 100% reduction of the holding.
        # ----------------------------------------------------

        governance_flags.append(
            "SELL DETERMINISTIC GOVERNANCE PASSED"
        )

        reasons.append(
            "SELL satisfies the deterministic governance "
            "requirements and represents a 100% reduction "
            "of the existing holding."
        )

        return _build_result(
            status="SUPPORTED",
            reconciled_action="SELL",
            deterministic_action=deterministic_action,
            proposed_action=proposed_action,
            llm_review=llm_review,
            llm_confidence=llm_confidence,
            llm_reason=llm_reason,
            llm_challenge=llm_challenge,
            evidence_score=evidence_score,
            evidence_strength=evidence_strength,
            deterministic_confidence=deterministic_confidence,
            decision_support=decision_support,
            existing_holding=existing_holding,
            asset_type=asset_type,
            governance_flags=governance_flags,
            reasons=reasons,
            automatic_approval=True,
            failed_checks=[],
            governance_reason_code=(
                "SELL_DETERMINISTIC_GOVERNANCE_PASSED"
            ),
            governance_reason=(
                "SELL was approved by deterministic governance. "
                "SELL represents a 100% reduction of the holding. "
                "Any LLM challenge or rejection is advisory only."
            ),
        )

    # --------------------------------------------------------
    # BUY NEW.
    #
    # General deterministic governance has passed.
    # --------------------------------------------------------



    if deterministic_action == "BUY NEW":
        if existing_holding:
            governance_flags.append(
                "BUY NEW WITH EXISTING HOLDING"
            )

            reasons.append(
                "The deterministic action is BUY NEW even though "
                "the asset is already marked as held."
            )

        governance_flags.append(
            "BUY NEW DETERMINISTIC GOVERNANCE PASSED"
        )

        reasons.append(
            "BUY NEW satisfies the deterministic governance requirements."
        )

        return _build_result(
            status="SUPPORTED",
            reconciled_action="BUY NEW",
            deterministic_action=deterministic_action,
            proposed_action=proposed_action,
            llm_review=llm_review,
            llm_confidence=llm_confidence,
            llm_reason=llm_reason,
            llm_challenge=llm_challenge,
            evidence_score=evidence_score,
            evidence_strength=evidence_strength,
            deterministic_confidence=deterministic_confidence,
            decision_support=decision_support,
            existing_holding=existing_holding,
            asset_type=asset_type,
            governance_flags=governance_flags,
            reasons=reasons,
            automatic_approval=True,
            failed_checks=[],
            governance_reason_code=(
                "BUY_NEW_DETERMINISTIC_GOVERNANCE_PASSED"
            ),
            governance_reason=(
                "BUY NEW was approved by deterministic governance. "
                "The LLM review is advisory only."
            ),
        )

    # --------------------------------------------------------
    # Defensive fallback.
    # --------------------------------------------------------

    governance_flags.append(
        "UNRESOLVED RECONCILIATION"
    )

    reasons.append(
        "The deterministic proposal could not be reconciled "
        "with sufficient governance certainty."
    )

    _record_failed_check(
        failed_checks,
        check_def="reconcile_decision",
        check_code="UNRESOLVED_RECONCILIATION",
        reason=(
            "No deterministic governance path produced sufficient "
            "certainty for automatic approval."
        ),
        actual_value=proposed_action,
        threshold_value="VALID DETERMINISTIC ACTION",
        unit="action",
    )

    return _build_result(
        status="REVIEW REQUIRED",
        reconciled_action="HOLD",
        deterministic_action=deterministic_action,
        proposed_action=proposed_action,
        llm_review=llm_review,
        llm_confidence=llm_confidence,
        llm_reason=llm_reason,
        llm_challenge=llm_challenge,
        evidence_score=evidence_score,
        evidence_strength=evidence_strength,
        deterministic_confidence=deterministic_confidence,
        decision_support=decision_support,
        existing_holding=existing_holding,
        asset_type=asset_type,
        governance_flags=governance_flags,
        reasons=reasons,
        automatic_approval=False,
        failed_checks=failed_checks,
        governance_reason_code=(
            "UNRESOLVED_RECONCILIATION"
        ),
        governance_reason=(
            "The deterministic proposal reached the defensive "
            "fallback because no valid deterministic governance "
            "path was available."
        ),
    )


# ============================================================
# Public compatibility API
# ============================================================


def reconcile_ai_decision(
    decision: dict,
    review: dict,
) -> dict:
    """
    Public compatibility entry point.

    The LLM review is accepted because existing callers provide it,
    but it is advisory only and cannot determine the action.
    """
    return reconcile_decision(
        decision=decision,
        review=review,
    )


def reconcile_review(
    decision: dict,
    review: dict,
) -> dict:
    """Compatibility alias for reconcile_decision()."""
    return reconcile_decision(
        decision=decision,
        review=review,
    )


# ============================================================
# Batch reconciliation
# ============================================================


def reconcile_ai_decisions(
    decisions: list[dict] | None,
    reviews: list[dict] | None,
) -> list[dict]:
    """
    Reconcile multiple deterministic decisions.

    Reviews are matched by position and retained as advisory information.

    Missing reviews do not block deterministic reconciliation.
    """
    if not decisions:
        return []

    if not isinstance(
        decisions,
        list,
    ):
        decisions = [
            decisions
        ]

    if not isinstance(
        reviews,
        list,
    ):
        reviews = []

    results: list[dict] = []

    for index, decision in enumerate(
        decisions
    ):
        review = (
            reviews[index]
            if index < len(reviews)
            else {}
        )

        results.append(
            reconcile_decision(
                decision=decision,
                review=review,
            )
        )

    return results


# ============================================================
# Module tests
# ============================================================


if __name__ == "__main__":

    print(
        "AI Decision Reconciler"
    )

    print(
        "Module loaded successfully."
    )

    # --------------------------------------------------------
    # TEST 1: Strong deterministic REDUCE with LLM ACCEPT.
    # --------------------------------------------------------

    reduce_decision = {
        "Final Decision":
            "REDUCE 25%",

        "Proposed Action":
            "REDUCE 25%",

        "Evidence Score":
            82.5,

        "Evidence Strength":
            "VERY STRONG",

        "Decision Support":
            "SUPPORTED",

        "Confidence":
            72.61,

        "Existing Holding":
            True,

        "Asset Type":
            "STOCK",

        "Investment Score":
            25.0,

        "Signal":
            "SELL",
    }

    reduce_review = {
        "Review Decision":
            "ACCEPT",

        "LLM Confidence":
            85.0,

        "Challenge":
            False,

        "Reviewer Status":
            "LLM REVIEW COMPLETE",
    }

    result = reconcile_decision(
        decision=reduce_decision,
        review=reduce_review,
    )

    print()
    print(
        "TEST 1: REDUCE 25%"
    )

    print(
        "Reconciled Action:",
        result["Reconciled Action"],
    )

    print(
        "Status:",
        result["Reconciliation Status"],
    )

    print(
        "Automatic Approval:",
        result["Automatic Approval"],
    )

    print(
        "Decision Authority:",
        result["Decision Authority"],
    )

    # --------------------------------------------------------
    # TEST 2: Qualified BUY MORE with LLM ACCEPT.
    # --------------------------------------------------------

    buy_more_decision = {
        "Final Decision":
            "BUY MORE",

        "Proposed Action":
            "BUY MORE",

        "Evidence Score":
            78.0,

        "Evidence Strength":
            "STRONG",

        "Decision Support":
            "SUPPORTED",

        "Confidence":
            74.0,

        "Existing Holding":
            True,

        "Asset Type":
            "STOCK",

        "Investment Score":
            86.0,

        "Signal":
            "STRONG BUY",

        "Allocation %":
            1.5,
    }

    buy_more_review = {
        "Review Decision":
            "ACCEPT",

        "LLM Confidence":
            82.0,

        "Challenge":
            False,

        "Reviewer Status":
            "LLM REVIEW COMPLETE",
    }

    result = reconcile_decision(
        decision=buy_more_decision,
        review=buy_more_review,
    )

    print()
    print(
        "TEST 2: QUALIFIED BUY MORE"
    )

    print(
        "Reconciled Action:",
        result["Reconciled Action"],
    )

    print(
        "Status:",
        result["Reconciliation Status"],
    )

    print(
        "Automatic Approval:",
        result["Automatic Approval"],
    )

    # --------------------------------------------------------
    # TEST 3: BUY MORE fails deterministic allocation.
    # --------------------------------------------------------

    buy_more_high_allocation = dict(
        buy_more_decision
    )

    buy_more_high_allocation[
        "Allocation %"
    ] = 2.5

    result = reconcile_decision(
        decision=buy_more_high_allocation,
        review=buy_more_review,
    )

    print()
    print(
        "TEST 3: BUY MORE HIGH ALLOCATION"
    )

    print(
        "Reconciled Action:",
        result["Reconciled Action"],
    )

    print(
        "Status:",
        result["Reconciliation Status"],
    )

    print(
        "Automatic Approval:",
        result["Automatic Approval"],
    )

    # --------------------------------------------------------
    # TEST 4: LLM REJECT MUST NOT change a qualified
    # deterministic BUY MORE.
    # --------------------------------------------------------

    reject_review = {
        "Review Decision":
            "REJECT",

        "LLM Confidence":
            95.0,

        "Challenge":
            True,

        "Reviewer Status":
            "LLM REVIEW COMPLETE",
    }

    result = reconcile_decision(
        decision=buy_more_decision,
        review=reject_review,
    )

    print()
    print(
        "TEST 4: QUALIFIED BUY MORE + LLM REJECT"
    )

    print(
        "Reconciled Action:",
        result["Reconciled Action"],
    )

    print(
        "Status:",
        result["Reconciliation Status"],
    )

    print(
        "Automatic Approval:",
        result["Automatic Approval"],
    )

    # --------------------------------------------------------
    # TEST 5: LLM CHALLENGE must not change a qualified
    # deterministic REDUCE.
    # --------------------------------------------------------

    challenge_review = {
        "Review Decision":
            "CHALLENGE",

        "LLM Confidence":
            95.0,

        "Challenge":
            True,

        "Reviewer Status":
            "LLM REVIEW COMPLETE",
    }

    result = reconcile_decision(
        decision=reduce_decision,
        review=challenge_review,
    )

    print()
    print(
        "TEST 5: QUALIFIED REDUCE + LLM CHALLENGE"
    )

    print(
        "Reconciled Action:",
        result["Reconciled Action"],
    )

    print(
        "Status:",
        result["Reconciliation Status"],
    )

    print(
        "Automatic Approval:",
        result["Automatic Approval"],
    )

    # --------------------------------------------------------
    # TEST 6: Missing LLM review must not block qualified
    # deterministic REDUCE.
    # --------------------------------------------------------

    result = reconcile_decision(
        decision=reduce_decision,
        review={},
    )

    print()
    print(
        "TEST 6: QUALIFIED REDUCE + NO LLM REVIEW"
    )

    print(
        "Reconciled Action:",
        result["Reconciled Action"],
    )

    print(
        "Status:",
        result["Reconciliation Status"],
    )

    print(
        "Automatic Approval:",
        result["Automatic Approval"],
    )
