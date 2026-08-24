
"""
AI Decision Reconciler

Purpose
-------
Reconcile the deterministic portfolio decision with the independent
AI Portfolio Reviewer assessment.

This module is a governance / reconciliation layer. It does not
create investment decisions independently.

Architecture
------------
    Analytical Engines
            |
            v
    Rules-Based Proposal
            |
            v
    AI Decision Context
            |
            v
    AI Decision Scoring
            |
            v
    AI Portfolio Reviewer
            |
            v
    AI Decision Reconciler
            |
            v
    Final Portfolio Decision

Important
---------
The deterministic decision remains authoritative.

The LLM reviewer can:
    - support the deterministic proposal
    - challenge the proposal
    - identify evidence gaps
    - identify contradictory evidence

The LLM cannot silently override the deterministic decision.

Design principles
-----------------
- HOLD remains the default.
- Deterministic decisions remain authoritative.
- LLM approval alone is never sufficient for a portfolio change.
- An LLM challenge triggers additional scrutiny.
- An LLM rejection prevents automatic approval.
- Strong decisions require strong evidence.
- SELL requires stronger evidence than REDUCE.
- Existing holdings receive additional protection.
- BUY MORE is more conservative than BUY NEW.
- BUY MORE requires a strong current investment case and
  strict LLM agreement.
- A justified REDUCE may proceed despite an LLM challenge when
  deterministic evidence is sufficiently strong.
- BUY NEW may proceed when the current investment case is strong
  but historical recommendation evidence is immature rather than
  materially negative.
- Missing LLM review never becomes approval.
- LLM failure results in a conservative outcome.
- Insufficient historical data is not treated as negative evidence.
- This module does not allocate capital.
- This module does not execute trades.
- This module does not change investment scoring weights.
- The final portfolio decision remains the responsibility of
  the downstream final decision gate.

Historical Horizon
------------------
The current learning engine provides short-term historical
evidence. The governance model is designed so that future
60-day evidence can become the preferred historical evidence
without changing the overall governance structure.

Importantly:

    INSUFFICIENT DATA != NEGATIVE EVIDENCE
"""

from __future__ import annotations

from typing import Any


# ============================================================
# Configuration
# ============================================================

MIN_DETERMINISTIC_CONFIDENCE = 70.0
STRONG_DETERMINISTIC_CONFIDENCE = 80.0

MIN_EVIDENCE_SCORE = 60.0
STRONG_EVIDENCE_SCORE = 75.0
SELL_EVIDENCE_SCORE = 80.0

MIN_LLM_CONFIDENCE = 60.0
STRONG_LLM_CONFIDENCE = 75.0


# ============================================================
# BUY NEW governance
# ============================================================

BUY_NEW_IMMATURE_MIN_EVIDENCE = 55.0
BUY_NEW_IMMATURE_MIN_CONFIDENCE = 50.0
BUY_NEW_IMMATURE_MIN_INVESTMENT_SCORE = 75.0


# ============================================================
# BUY MORE governance
#
# BUY MORE is deliberately stricter than BUY NEW because the
# asset is already held and increasing the position increases
# portfolio concentration.
# ============================================================

BUY_MORE_MIN_EVIDENCE = 70.0
BUY_MORE_MIN_CONFIDENCE = 70.0
BUY_MORE_MIN_INVESTMENT_SCORE = 80.0
BUY_MORE_MIN_LLM_CONFIDENCE = 75.0
BUY_MORE_MAX_ALLOCATION_PERCENT = 5.0

BUY_MORE_SUPPORTING_SIGNALS = {
    "BUY",
    "STRONG BUY",
}


# ============================================================
# REDUCE governance
# ============================================================

REDUCE_CHALLENGE_MIN_EVIDENCE = 65.0
REDUCE_CHALLENGE_MIN_CONFIDENCE = 65.0
REDUCE_CHALLENGE_MAX_INVESTMENT_SCORE = 40.0

REDUCE_SUPPORTING_SIGNALS = {
    "SELL",
    "STRONG SELL",
}


VALID_ACTIONS = {
    "BUY NEW",
    "BUY MORE",
    "HOLD",
    "REDUCE",
    "SELL",
}

VALID_REVIEW_DECISIONS = {
    "ACCEPT",
    "CHALLENGE",
    "REJECT",
}


# ============================================================
# Generic helpers
# ============================================================

def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    """Safely convert a value to float."""

    try:
        if value is None:
            return default

        return float(value)

    except (
        TypeError,
        ValueError,
    ):
        return default


def _clamp(
    value: Any,
    minimum: float = 0.0,
    maximum: float = 100.0,
) -> float:
    """Clamp a numeric value to a defined range."""

    value = _safe_float(value)

    return max(
        minimum,
        min(
            maximum,
            value,
        ),
    )


def _clean_text(
    value: Any,
    default: str = "",
) -> str:
    """Safely normalise text."""

    if value is None:
        return default

    try:
        text = str(value).strip()

    except Exception:
        return default

    return (
        text.upper()
        if text
        else default
    )


def _get(
    mapping: Any,
    *keys: str,
    default: Any = None,
) -> Any:
    """Return the first available non-null value from a dictionary."""

    if not isinstance(
        mapping,
        dict,
    ):
        return default

    for key in keys:

        if key not in mapping:
            continue

        value = mapping.get(key)

        if value is not None:
            return value

    return default


def _normalise_action(
    value: Any,
) -> str:
    """
    Normalise a portfolio action.

    REDUCE percentage variants are normalised to REDUCE.
    """

    action = _clean_text(
        value,
        default="HOLD",
    )

    if action.startswith("REDUCE"):
        return "REDUCE"

    if action in VALID_ACTIONS:
        return action

    return "HOLD"


# ============================================================
# Deterministic decision extraction
# ============================================================

def get_deterministic_action(
    decision: dict,
) -> str:
    """Extract the deterministic final action."""

    action = _get(
        decision,
        "Final Decision",
        "final_decision",
        "Proposed Action",
        "proposed_action",
        "Action",
        "action",
        default="HOLD",
    )

    return _normalise_action(action)


def get_proposed_action(
    decision: dict,
) -> str:
    """Extract the original deterministic proposed action."""

    action = _get(
        decision,
        "Proposed Action",
        "proposed_action",
        "Action",
        "action",
        default="HOLD",
    )

    return _normalise_action(action)


def get_evidence_score(
    decision: dict,
) -> float:
    """Extract the deterministic evidence score."""

    evidence = decision.get(
        "Evidence Assessment",
        {},
    )

    value = _get(
        decision,
        "Evidence Score",
        "evidence_score",
        default=None,
    )

    if value is None:
        value = _get(
            evidence,
            "Evidence Score",
            "evidence_score",
            default=0.0,
        )

    return _clamp(value)


def get_evidence_strength(
    decision: dict,
) -> str:
    """Extract deterministic evidence strength."""

    evidence = decision.get(
        "Evidence Assessment",
        {},
    )

    value = _get(
        decision,
        "Evidence Strength",
        "evidence_strength",
        default=None,
    )

    if value is None:
        value = _get(
            evidence,
            "Evidence Strength",
            "evidence_strength",
            default="",
        )

    return _clean_text(value)


def get_decision_support(
    decision: dict,
) -> str:
    """Extract deterministic decision support classification."""

    evidence = decision.get(
        "Evidence Assessment",
        {},
    )

    value = _get(
        decision,
        "Decision Support",
        "decision_support",
        default=None,
    )

    if value is None:
        value = _get(
            evidence,
            "Decision Support",
            "decision_support",
            default="",
        )

    return _clean_text(value)


def get_deterministic_confidence(
    decision: dict,
) -> float:
    """Extract deterministic decision confidence."""

    evidence = decision.get(
        "Evidence Assessment",
        {},
    )

    value = _get(
        decision,
        "Deterministic Confidence",
        "deterministic_confidence",
        "Confidence",
        "confidence",
        default=None,
    )

    if value is None:
        value = _get(
            evidence,
            "Deterministic Confidence",
            "deterministic_confidence",
            "Confidence",
            "confidence",
            default=0.0,
        )

    return _clamp(value)

def get_investment_score(
    decision: dict,
) -> float:
    """Extract the existing investment score."""

    evidence = decision.get(
        "Evidence Assessment",
        {},
    )

    value = _get(
        decision,
        "Investment Score",
        "investment_score",
        default=None,
    )

    if value is None:
        value = _get(
            evidence,
            "Investment Score",
            "investment_score",
            default=0.0,
        )

    return _clamp(value)


def get_signal(
    decision: dict,
) -> str:
    """Extract the existing analytical signal."""

    evidence = decision.get(
        "Evidence Assessment",
        {},
    )

    value = _get(
        decision,
        "Signal",
        "signal",
        "Momentum Signal",
        "momentum_signal",
        default=None,
    )

    if value is None:
        value = _get(
            evidence,
            "Signal",
            "signal",
            "Momentum Signal",
            "momentum_signal",
            default="",
        )

    return _clean_text(value)


def get_allocation_percent(
    decision: dict,
) -> float | None:
    """
    Extract portfolio allocation percentage.

    Allocation is consumed evidence from the upstream portfolio
    allocation layer. The reconciler does not calculate it.

    Returns
    -------
    float | None
        None when allocation is unavailable.
    """

    value = _get(
        decision,
        "Allocation %",
        "allocation_percent",
        "Allocation Percent",
        "allocation",
        default=None,
    )

    if value is None:
        return None

    try:
        return float(value)

    except (
        TypeError,
        ValueError,
    ):
        return None


# ============================================================
# Historical evidence helpers
# ============================================================

def get_historical_reliability(
    decision: dict,
) -> str:
    """Extract historical recommendation reliability."""

    evidence = decision.get(
        "Evidence Assessment",
        {},
    )

    value = _get(
        decision,
        "Historical Signal Reliability",
        "historical_signal_reliability",
        default=None,
    )

    if value is None:
        value = _get(
            evidence,
            "Historical Signal Reliability",
            "historical_signal_reliability",
            default="",
        )

    return _clean_text(value)


def get_historical_observations(
    decision: dict,
) -> float:
    """Extract historical recommendation observations."""

    evidence = decision.get(
        "Evidence Assessment",
        {},
    )

    value = _get(
        decision,
        "Historical Signal Observations",
        "historical_signal_observations",
        default=None,
    )

    if value is None:
        value = _get(
            evidence,
            "Historical Signal Observations",
            "historical_signal_observations",
            default=0,
        )

    return _safe_float(value)


def history_is_immature(
    decision: dict,
) -> bool:
    """
    Determine whether historical evidence is immature.

    INSUFFICIENT DATA is treated as evidence immaturity,
    not as negative evidence.
    """

    reliability = get_historical_reliability(
        decision
    )

    observations = get_historical_observations(
        decision
    )

    if reliability in {
        "",
        "NO DATA",
        "INSUFFICIENT DATA",
    }:
        return True

    if observations < 10:
        return True

    return False


# ============================================================
# LLM review helpers
# ============================================================

def get_llm_review(
    review: dict,
) -> str:
    """Extract the LLM review classification."""

    value = _get(
        review,
        "Review Decision",
        "review_decision",
        "LLM Decision",
        "LLM Assessment",
        default="CHALLENGE",
    )

    value = _clean_text(
        value,
        default="CHALLENGE",
    )

    if value not in VALID_REVIEW_DECISIONS:
        return "CHALLENGE"

    return value


def get_llm_confidence(
    review: dict,
) -> float:
    """Extract LLM confidence."""

    value = _get(
        review,
        "LLM Confidence",
        "llm_confidence",
        "Confidence",
        "confidence",
        default=0.0,
    )

    return _clamp(value)


def get_llm_challenge(
    review: dict,
) -> bool:
    """Extract explicit LLM challenge status."""

    value = _get(
        review,
        "Challenge",
        "challenge",
        default=None,
    )

    if value is None:
        return (
            get_llm_review(review)
            != "ACCEPT"
        )

    if isinstance(
        value,
        str,
    ):
        return (
            value.strip().lower()
            in {
                "true",
                "yes",
                "1",
                "challenge",
            }
        )

    return bool(value)


def review_indicates_material_contradiction(
    review: dict,
) -> bool:
    """
    Detect substantive contradiction in the independent review.

    Missing or insufficient data alone does not count as a
    material contradiction.
    """

    if not isinstance(
        review,
        dict,
    ):
        return False

    text_parts: list[str] = []

    for key in (
        "LLM Reason",
        "Reason",
        "LLM Evidence Gaps",
        "Evidence Gaps",
        "LLM Key Points",
        "Key Points",
    ):

        value = review.get(key)

        if isinstance(
            value,
            list,
        ):

            text_parts.extend(
                str(item)
                for item in value
            )

        elif value is not None:

            text_parts.append(
                str(value)
            )

    text = " ".join(
        text_parts
    ).upper()

    contradiction_terms = (
        "CONTRADICTORY",
        "CONTRADICTION",
        "CONFLICTING EVIDENCE",
        "MATERIAL RISK",
        "MATERIAL NEGATIVE",
        "UNSUPPORTED",
        "NOT SUPPORTED",
    )

    return any(
        term in text
        for term in contradiction_terms
    )


# ============================================================
# Context extraction
# ============================================================

def get_existing_holding(
    decision: dict,
    review: dict | None = None,
) -> bool:
    """
    Determine whether the candidate is an existing portfolio holding.

    Ownership is determined from Quantity whenever a valid quantity is
    available. A positive quantity means the asset is owned.

    This prevents a stale or incorrect "Existing Holding" boolean in the
    decision/review context from overriding the authoritative portfolio
    quantity.

    Fallback order:
        1. Quantity from decision
        2. Quantity from review
        3. Existing Holding / Owned flag from decision
        4. Existing Holding / Owned flag from review
        5. False
    """

    # --------------------------------------------------------
    # Quantity is the authoritative ownership signal.
    # --------------------------------------------------------

    quantity = _get(
        decision,
        "Quantity",
        "quantity",
        default=None,
    )

    if quantity is not None:
        try:
            return float(quantity) > 0
        except (TypeError, ValueError):
            pass

    # --------------------------------------------------------
    # Fall back to quantity supplied by the review.
    # --------------------------------------------------------

    if review:
        quantity = _get(
            review,
            "Quantity",
            "quantity",
            default=None,
        )

        if quantity is not None:
            try:
                return float(quantity) > 0
            except (TypeError, ValueError):
                pass

    # --------------------------------------------------------
    # Legacy / fallback ownership flag from the decision.
    # --------------------------------------------------------

    value = _get(
        decision,
        "Existing Holding",
        "existing_holding",
        "Owned",
        "owned",
        default=None,
    )

    if value is not None:
        if isinstance(value, bool):
            return value

        return _clean_text(value) in {
            "TRUE",
            "YES",
            "OWNED",
            "EXISTING",
        }

    # --------------------------------------------------------
    # Final fallback: ownership flag from the review.
    # --------------------------------------------------------

    if review:
        value = _get(
            review,
            "Existing Holding",
            "existing_holding",
            "Owned",
            "owned",
            default=None,
        )

        if value is not None:
            if isinstance(value, bool):
                return value

            return _clean_text(value) in {
                "TRUE",
                "YES",
                "OWNED",
                "EXISTING",
            }

    return False



def get_asset_type(
    decision: dict,
    review: dict | None = None,
) -> str:
    """Determine whether the candidate is a STOCK or ETF."""

    value = _get(
        decision,
        "Asset Type",
        "asset_type",
        default=None,
    )

    if value is None and review:
        value = _get(
            review,
            "Asset Type",
            "asset_type",
            default="STOCK",
        )

    value = _clean_text(
        value,
        default="STOCK",
    )

    if value == "EQUITY":
        return "STOCK"

    if value not in {
        "STOCK",
        "ETF",
    }:
        return "STOCK"

    return value


# ============================================================
# BUY NEW governance
# ============================================================

def buy_new_is_strong_enough_to_survive_immature_history(
    decision: dict,
    review: dict,
) -> bool:
    """
    Determine whether BUY NEW may proceed despite immature
    historical evidence.

    Requirements
    ------------
    - BUY NEW proposal
    - LLM ACCEPT
    - No material contradiction
    - Immature historical evidence
    - Evidence score >= configured minimum
    - Deterministic confidence >= configured minimum
    - Decision support is SUPPORTED or CONDITIONAL
    - Investment score >= configured minimum
    """

    if get_proposed_action(decision) != "BUY NEW":
        return False

    if get_llm_review(review) != "ACCEPT":
        return False

    if review_indicates_material_contradiction(review):
        return False

    if not history_is_immature(decision):
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

    if evidence_score < BUY_NEW_IMMATURE_MIN_EVIDENCE:
        return False

    if confidence < BUY_NEW_IMMATURE_MIN_CONFIDENCE:
        return False

    if support not in {
        "SUPPORTED",
        "CONDITIONAL",
    }:
        return False

    if investment_score < BUY_NEW_IMMATURE_MIN_INVESTMENT_SCORE:
        return False

    return True


# ============================================================
# BUY MORE governance
# ============================================================

def _buy_more_is_strong_enough_for_automatic_approval(
    decision: dict,
    review: dict,
    existing_holding: bool,
) -> bool:
    """
    Determine whether BUY MORE satisfies the dedicated
    BUY MORE governance requirements.

    BUY MORE is intentionally stricter than BUY NEW because
    the asset is already held and increasing the position
    increases portfolio concentration.

    Requirements
    ------------
    - Existing holding
    - Evidence Score >= 70
    - Deterministic Confidence >= 70
    - Investment Score >= 80
    - Signal is BUY or STRONG BUY
    - LLM review is ACCEPT
    - LLM Confidence >= 75
    - No material contradiction
    - Allocation <= 2%

    Allocation is consumed evidence from the upstream portfolio
    decision / capital-allocation layer.
    """

    if not existing_holding:
        return False

    if get_proposed_action(decision) != "BUY MORE":
        return False

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

    llm_review = get_llm_review(
        review
    )

    llm_confidence = get_llm_confidence(
        review
    )

    allocation = get_allocation_percent(
        decision
    )

    if evidence_score < BUY_MORE_MIN_EVIDENCE:
        return False

    if deterministic_confidence < BUY_MORE_MIN_CONFIDENCE:
        return False

    if investment_score < BUY_MORE_MIN_INVESTMENT_SCORE:
        return False

    if signal not in BUY_MORE_SUPPORTING_SIGNALS:
        return False

    if llm_review != "ACCEPT":
        return False

    if llm_confidence < BUY_MORE_MIN_LLM_CONFIDENCE:
        return False

    if review_indicates_material_contradiction(review):
        return False

    # Missing allocation is deliberately conservative.
    if allocation is None:
        return False

    if allocation < 0:
        return False

    if allocation > BUY_MORE_MAX_ALLOCATION_PERCENT:
        return False

    return True


def debug_buy_more_governance(
    decision: dict,
    review: dict,
) -> None:
    """
    Print the individual BUY MORE governance checks.

    This is diagnostic only. It does not change any decision.
    It allows the main program output to show exactly why a
    BUY MORE proposal was either qualified or moved to HOLD.
    """

    existing_holding = get_existing_holding(
        decision,
        review,
    )

    proposed_action = get_proposed_action(
        decision
    )

    if proposed_action != "BUY MORE":
        return

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

    llm_review = get_llm_review(
        review
    )

    llm_confidence = get_llm_confidence(
        review
    )

    allocation = get_allocation_percent(
        decision
    )

    contradiction = (
        review_indicates_material_contradiction(
            review
        )
    )

    checks = {
        "Existing Holding":
            existing_holding,

        "Evidence >= 70":
            evidence_score >= BUY_MORE_MIN_EVIDENCE,

        "Confidence >= 70":
            deterministic_confidence
            >= BUY_MORE_MIN_CONFIDENCE,

        "Investment Score >= 80":
            investment_score
            >= BUY_MORE_MIN_INVESTMENT_SCORE,

        "Signal BUY/STRONG BUY":
            signal in BUY_MORE_SUPPORTING_SIGNALS,

        "LLM ACCEPT":
            llm_review == "ACCEPT",

        "LLM Confidence >= 75":
            llm_confidence
            >= BUY_MORE_MIN_LLM_CONFIDENCE,

        "No Material Contradiction":
            not contradiction,

        "Allocation <= 2%":
            (
                allocation is not None
                and
                0 <= allocation
                <= BUY_MORE_MAX_ALLOCATION_PERCENT
            ),
    }

    print()
    print("=" * 72)
    print("BUY MORE GOVERNANCE DEBUG")
    print("=" * 72)

    print(
        f"Proposed Action        : {proposed_action}"
    )

    print(
        f"Existing Holding       : {existing_holding}"
    )

    print(
        f"Evidence Score         : {evidence_score:.2f}"
    )

    print(
        f"Deterministic Conf.    : {deterministic_confidence:.2f}"
    )

    print(
        f"Investment Score       : {investment_score:.2f}"
    )

    print(
        f"Signal                 : {signal}"
    )

    print(
        f"LLM Review             : {llm_review}"
    )

    print(
        f"LLM Confidence         : {llm_confidence:.2f}"
    )

    print(
        f"Allocation %           : "
        f"{allocation:.2f}%"
        if allocation is not None
        else "Allocation %           : MISSING"
    )

    print(
        f"Material Contradiction : {contradiction}"
    )

    print("-" * 72)

    for check_name, passed in checks.items():

        print(
            f"{'PASS' if passed else 'FAIL':4} | "
            f"{check_name}"
        )

    all_pass = all(checks.values())

    print("-" * 72)

    print(
        "BUY MORE RESULT        : "
        f"{'QUALIFIED BUY MORE' if all_pass else 'HOLD'}"
    )

    print("=" * 72)


# ============================================================
# REDUCE governance
# ============================================================

def _reduce_is_strong_enough_to_survive_challenge(
    decision: dict,
    existing_holding: bool,
) -> bool:
    """
    Determine whether REDUCE is strong enough to proceed
    despite an LLM challenge.

    Requirements
    ------------
    - Existing holding
    - Evidence >= 65
    - Deterministic confidence >= 65
    - Deterministic support
    - Either:
        * Investment Score <= 40
        * bearish SELL / STRONG SELL signal
    """

    if not existing_holding:
        return False

    evidence_score = get_evidence_score(
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

    investment_score = get_investment_score(
        decision
    )

    signal = get_signal(
        decision
    )

    if evidence_score < REDUCE_CHALLENGE_MIN_EVIDENCE:
        return False

    if deterministic_confidence < REDUCE_CHALLENGE_MIN_CONFIDENCE:
        return False

    if decision_support != "SUPPORTED":
        return False

    weak_investment_case = (
        investment_score
        <=
        REDUCE_CHALLENGE_MAX_INVESTMENT_SCORE
    )

    bearish_signal = (
        signal
        in
        REDUCE_SUPPORTING_SIGNALS
    )

    return (
        weak_investment_case
        or bearish_signal
    )


# ============================================================
# Generic governance helpers
# ============================================================

def _requires_strong_evidence(
    action: str,
) -> bool:
    """Return True where strong deterministic evidence is required."""

    return action in {
        "BUY MORE",
        "REDUCE",
        "SELL",
    }


def _deterministic_action_is_weak(
    decision: dict,
) -> bool:
    """
    Determine whether the deterministic proposal lacks sufficient
    evidence for automatic approval.

    BUY NEW with immature historical evidence may receive a
    controlled exception later.
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
    governance_reason_code: str = "",
    governance_reason: str = "",
) -> dict:
    """
    Build the standard reconciliation result.

    Final Decision deliberately remains None because this module
    is not the final portfolio decision gate.
    """

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

        "Governance Reason Code":
            governance_reason_code,

        "Governance Reason":
            governance_reason,

        "Automatic Approval":
            automatic_approval,

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
    Reconcile one deterministic decision with one LLM review.

    The deterministic proposal remains authoritative.

    The LLM provides independent governance evidence but cannot
    silently override a justified deterministic decision.

    This function does not make the final portfolio decision.
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

    proposed_action = get_proposed_action(
        decision
    )

    deterministic_action = get_deterministic_action(
        decision
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

    llm_review = get_llm_review(
        review
    )

    llm_confidence = get_llm_confidence(
        review
    )

    llm_challenge = get_llm_challenge(
        review
    )

    existing_holding = get_existing_holding(
        decision,
        review,
    )

    asset_type = get_asset_type(
        decision,
        review,
    )

    governance_flags: list[str] = []
    reasons: list[str] = []

    # --------------------------------------------------------
    # Detect unavailable LLM review.
    # --------------------------------------------------------

    reviewer_status = _clean_text(
        _get(
            review,
            "Reviewer Status",
            "reviewer_status",
            default="",
        )
    )

    llm_available = (
        bool(review)
        and
        reviewer_status
        not in {
            "LLM UNAVAILABLE",
            "LLM REVIEW ERROR",
        }
    )

    if not llm_available:

        governance_flags.append(
            "LLM REVIEW UNAVAILABLE"
        )

        reasons.append(
            "Independent LLM review is unavailable."
        )

        if proposed_action != "HOLD":
            reasons.append(
                "A non-HOLD action cannot be automatically approved without the independent review layer."
            )

        return _build_result(
            status="REVIEW REQUIRED",
            reconciled_action="HOLD",
            deterministic_action=deterministic_action,
            proposed_action=proposed_action,
            llm_review="CHALLENGE",
            llm_confidence=0.0,
            evidence_score=evidence_score,
            evidence_strength=evidence_strength,
            deterministic_confidence=deterministic_confidence,
            decision_support=decision_support,
            existing_holding=existing_holding,
            asset_type=asset_type,
            governance_flags=governance_flags,
            reasons=reasons,
            automatic_approval=False,
        )

    # --------------------------------------------------------
    # HOLD.
    # --------------------------------------------------------

    if proposed_action == "HOLD":

        if llm_review == "ACCEPT":

            reasons.append(
                "The independent LLM review supports the deterministic HOLD."
            )

            status = (
                "SUPPORTED"
                if llm_confidence >= STRONG_LLM_CONFIDENCE
                else "CONDITIONAL"
            )

        elif llm_review == "CHALLENGE":

            governance_flags.append(
                "LLM CHALLENGE"
            )

            reasons.append(
                "The independent LLM review challenges the HOLD."
            )

            status = "REVIEW REQUIRED"

        else:

            governance_flags.append(
                "LLM REJECT"
            )

            reasons.append(
                "The independent LLM review rejects the deterministic HOLD."
            )

            status = "REVIEW REQUIRED"

        return _build_result(
            status=status,
            reconciled_action="HOLD",
            deterministic_action=deterministic_action,
            proposed_action=proposed_action,
            llm_review=llm_review,
            llm_confidence=llm_confidence,
            evidence_score=evidence_score,
            evidence_strength=evidence_strength,
            deterministic_confidence=deterministic_confidence,
            decision_support=decision_support,
            existing_holding=existing_holding,
            asset_type=asset_type,
            governance_flags=governance_flags,
            reasons=reasons,
            automatic_approval=(
                status == "SUPPORTED"
            ),
        )

    # --------------------------------------------------------
    # BUY MORE dedicated governance.
    #
    # This occurs after LLM availability and HOLD handling.
    #
    # BUY MORE must satisfy the complete stronger rule set.
    # It cannot obtain approval merely by satisfying the generic
    # evidence threshold.
    # --------------------------------------------------------

    if proposed_action == "BUY MORE":


        debug_buy_more_governance(
            decision=decision,
            review=review,
        )

        if not _buy_more_is_strong_enough_for_automatic_approval(
            decision=decision,
            review=review,
            existing_holding=existing_holding,
        ):

            governance_flags.append(
                "BUY MORE GOVERNANCE REQUIREMENTS NOT MET"
            )

            reasons.append(
                "BUY MORE requires existing ownership, "
                "Evidence Score >= 70, deterministic confidence "
                ">= 70, Investment Score >= 80, a BUY or STRONG BUY "
                "signal, LLM ACCEPT with confidence >= 75, no "
                "material contradiction, and allocation <= 2%."
            )

            allocation = get_allocation_percent(
                decision
            )

            if allocation is None:

                governance_flags.append(
                    "BUY MORE ALLOCATION MISSING"
                )

                reasons.append(
                    "BUY MORE cannot be automatically approved "
                    "without an explicit portfolio allocation percentage."
                )

            elif allocation > BUY_MORE_MAX_ALLOCATION_PERCENT:

                governance_flags.append(
                    "BUY MORE ALLOCATION ABOVE LIMIT"
                )

                reasons.append(
                    f"BUY MORE allocation of {allocation:.2f}% "
                    f"exceeds the maximum permitted allocation of "
                    f"{BUY_MORE_MAX_ALLOCATION_PERCENT:.2f}%."
                )

            if not existing_holding:

                governance_flags.append(
                    "BUY MORE REQUIRES EXISTING HOLDING"
                )

                reasons.append(
                    "BUY MORE is only valid when the asset is already held."
                )

            if evidence_score < BUY_MORE_MIN_EVIDENCE:

                governance_flags.append(
                    "BUY MORE EVIDENCE BELOW THRESHOLD"
                )

            if (
                deterministic_confidence
                <
                BUY_MORE_MIN_CONFIDENCE
            ):

                governance_flags.append(
                    "BUY MORE CONFIDENCE BELOW THRESHOLD"
                )

            if (
                get_investment_score(decision)
                <
                BUY_MORE_MIN_INVESTMENT_SCORE
            ):

                governance_flags.append(
                    "BUY MORE INVESTMENT SCORE BELOW THRESHOLD"
                )

            if get_signal(decision) not in BUY_MORE_SUPPORTING_SIGNALS:

                governance_flags.append(
                    "BUY MORE SIGNAL NOT SUPPORTIVE"
                )

            if llm_review != "ACCEPT":

                governance_flags.append(
                    "BUY MORE LLM REVIEW NOT ACCEPTED"
                )

            if llm_confidence < BUY_MORE_MIN_LLM_CONFIDENCE:

                governance_flags.append(
                    "BUY MORE LLM CONFIDENCE BELOW THRESHOLD"
                )

            if review_indicates_material_contradiction(
                review
            ):

                governance_flags.append(
                    "BUY MORE MATERIAL CONTRADICTION"
                )

            return _build_result(
                status="REVIEW REQUIRED",
                reconciled_action="HOLD",
                deterministic_action=deterministic_action,
                proposed_action=proposed_action,
                llm_review=llm_review,
                llm_confidence=llm_confidence,
                evidence_score=evidence_score,
                evidence_strength=evidence_strength,
                deterministic_confidence=deterministic_confidence,
                decision_support=decision_support,
                existing_holding=existing_holding,
                asset_type=asset_type,
                governance_flags=governance_flags,
                reasons=reasons,
                automatic_approval=False,
                governance_reason_code="BUY_MORE_GOVERNANCE_THRESHOLD",
                governance_reason=(
                    "BUY MORE did not satisfy the complete "
                    "governance requirements for increasing an "
                    "existing position."
                ),
            )

        governance_flags.append(
            "QUALIFIED BUY MORE"
        )

        reasons.append(
            "BUY MORE satisfies the dedicated existing-holding governance requirements."
        )

        reasons.append(
            "The investment score, analytical signal, deterministic evidence and independent LLM review all support increasing the existing position."
        )

        return _build_result(
            status="SUPPORTED",
            reconciled_action="BUY MORE",
            deterministic_action=deterministic_action,
            proposed_action=proposed_action,
            llm_review=llm_review,
            llm_confidence=llm_confidence,
            evidence_score=evidence_score,
            evidence_strength=evidence_strength,
            deterministic_confidence=deterministic_confidence,
            decision_support=decision_support,
            existing_holding=existing_holding,
            asset_type=asset_type,
            governance_flags=governance_flags,
            reasons=reasons,
            automatic_approval=True,
            governance_reason_code="QUALIFIED_BUY_MORE",
            governance_reason=(
                "BUY MORE approved because the existing holding "
                "meets the required evidence, confidence, "
                "investment-score, signal, LLM-review and "
                "allocation thresholds."
            ),
        )

    # --------------------------------------------------------
    # BUY NEW immature-history exception.
    # --------------------------------------------------------

    buy_new_immature_history_override = (
        buy_new_is_strong_enough_to_survive_immature_history(
            decision=decision,
            review=review,
        )
    )

    # --------------------------------------------------------
    # JUSTIFIED REDUCE WITH LLM ACCEPT.
    #
    # This gate deliberately occurs before the generic weak-
    # deterministic-evidence gate.
    # --------------------------------------------------------

    if (
        proposed_action == "REDUCE"
        and
        llm_review == "ACCEPT"
        and
        _reduce_is_strong_enough_to_survive_challenge(
            decision=decision,
            existing_holding=existing_holding,
        )
    ):

        governance_flags.append(
            "JUSTIFIED REDUCE"
        )

        reasons.append(
            "REDUCE is supported by sufficient deterministic evidence and an adequately weak investment case for the existing holding."
        )

        if (
            get_investment_score(decision)
            <=
            REDUCE_CHALLENGE_MAX_INVESTMENT_SCORE
        ):

            reasons.append(
                "Investment Score is sufficiently weak to justify reducing exposure."
            )

        if (
            get_signal(decision)
            in
            REDUCE_SUPPORTING_SIGNALS
        ):

            reasons.append(
                "The underlying analytical signal is bearish."
            )

        reasons.append(
            "The independent LLM review accepts the REDUCE proposal."
        )

        return _build_result(
            status="SUPPORTED",
            reconciled_action="REDUCE",
            deterministic_action=deterministic_action,
            proposed_action=proposed_action,
            llm_review=llm_review,
            llm_confidence=llm_confidence,
            evidence_score=evidence_score,
            evidence_strength=evidence_strength,
            deterministic_confidence=deterministic_confidence,
            decision_support=decision_support,
            existing_holding=existing_holding,
            asset_type=asset_type,
            governance_flags=governance_flags,
            reasons=reasons,
            automatic_approval=True,
            governance_reason_code="JUSTIFIED_REDUCE",
            governance_reason=(
                "REDUCE approved because the existing holding has "
                "sufficient deterministic evidence, adequate "
                "confidence, and a weak investment case and/or "
                "bearish signal."
            ),
        )

    # --------------------------------------------------------
    # Weak deterministic proposal.
    # --------------------------------------------------------

    # --------------------------------------------------------
    # REDUCE + LLM CHALLENGE exception.
    #
    # A justified REDUCE is allowed to reach the dedicated
    # challenge-handling logic even when its deterministic
    # confidence is below the generic 70 threshold.
    # --------------------------------------------------------

    reduce_challenge_override = (
        proposed_action == "REDUCE"
        and
        llm_review == "CHALLENGE"
        and
        _reduce_is_strong_enough_to_survive_challenge(
            decision=decision,
            existing_holding=existing_holding,
        )
    )

    weak_deterministic = _deterministic_action_is_weak(
        decision
    )

    if (
        weak_deterministic
        and
        not buy_new_immature_history_override
        and
        not reduce_challenge_override
    ):

        governance_flags.append(
            "WEAK DETERMINISTIC EVIDENCE"
        )

        reasons.append(
            "Deterministic evidence is insufficient to support automatic portfolio change."
        )

        if llm_review == "ACCEPT":

            governance_flags.append(
                "LLM ACCEPTS WEAK PROPOSAL"
            )

            reasons.append(
                "LLM agreement cannot compensate for insufficient deterministic evidence."
            )

        elif llm_review == "CHALLENGE":

            governance_flags.append(
                "LLM CHALLENGE"
            )

            reasons.append(
                "The independent reviewer also identifies concerns."
            )

        else:

            governance_flags.append(
                "LLM REJECT"
            )

            reasons.append(
                "The independent reviewer rejects the already weak proposal."
            )

        return _build_result(
            status="REVIEW REQUIRED",
            reconciled_action="HOLD",
            deterministic_action=deterministic_action,
            proposed_action=proposed_action,
            llm_review=llm_review,
            llm_confidence=llm_confidence,
            evidence_score=evidence_score,
            evidence_strength=evidence_strength,
            deterministic_confidence=deterministic_confidence,
            decision_support=decision_support,
            existing_holding=existing_holding,
            asset_type=asset_type,
            governance_flags=governance_flags,
            reasons=reasons,
            automatic_approval=False,
        )

    # --------------------------------------------------------
    # LLM CHALLENGE.
    #
    # Normal rule:
    #     Challenge blocks BUY NEW / SELL.
    #
    # A justified REDUCE may survive a challenge.
    # BUY MORE cannot survive a challenge because the dedicated
    # BUY MORE gate requires LLM ACCEPT.
    # --------------------------------------------------------

    if (
        llm_review == "CHALLENGE"
        or
        llm_challenge
    ):

        if proposed_action == "REDUCE":

            if _reduce_is_strong_enough_to_survive_challenge(
                decision=decision,
                existing_holding=existing_holding,
            ):

                governance_flags.append(
                    "LLM CHALLENGE - REDUCE EXCEPTION"
                )

                reasons.append(
                    "LLM challenged the reduction, but strong deterministic evidence supports reducing the existing holding."
                )

                reasons.append(
                    "The reduction is supported by a sufficiently low investment score and/or bearish signal."
                )

                return _build_result(
                    status="SUPPORTED WITH CHALLENGE",
                    reconciled_action="REDUCE",
                    deterministic_action=deterministic_action,
                    proposed_action=proposed_action,
                    llm_review=llm_review,
                    llm_confidence=llm_confidence,
                    evidence_score=evidence_score,
                    evidence_strength=evidence_strength,
                    deterministic_confidence=deterministic_confidence,
                    decision_support=decision_support,
                    existing_holding=existing_holding,
                    asset_type=asset_type,
                    governance_flags=governance_flags,
                    reasons=reasons,
                    automatic_approval=True,
                    governance_reason_code="REDUCE_CHALLENGE_EXCEPTION",
                    governance_reason=(
                        "REDUCE allowed despite LLM challenge because "
                        "the existing holding satisfies the dedicated "
                        "strong-reduction criteria."
                    ),
                )

            governance_flags.append(
                "LLM CHALLENGE"
            )

            reasons.append(
                "The independent LLM review challenges the REDUCE proposal and the deterministic evidence is not strong enough to override that challenge."
            )

            return _build_result(
                status="REVIEW REQUIRED",
                reconciled_action="HOLD",
                deterministic_action=deterministic_action,
                proposed_action=proposed_action,
                llm_review=llm_review,
                llm_confidence=llm_confidence,
                evidence_score=evidence_score,
                evidence_strength=evidence_strength,
                deterministic_confidence=deterministic_confidence,
                decision_support=decision_support,
                existing_holding=existing_holding,
                asset_type=asset_type,
                governance_flags=governance_flags,
                reasons=reasons,
                automatic_approval=False,
            )

        governance_flags.append(
            "LLM CHALLENGE"
        )

        reasons.append(
            "The independent LLM review challenges the deterministic proposal."
        )

        if proposed_action == "BUY MORE":

            governance_flags.append(
                "EXISTING HOLDING PROTECTION"
            )

            reasons.append(
                "BUY MORE receives additional scrutiny because the asset is already held."
            )

        if proposed_action == "SELL":

            governance_flags.append(
                "SELL CHALLENGE"
            )

            reasons.append(
                "SELL remains subject to the strictest governance because an LLM challenge was received."
            )

        return _build_result(
            status="REVIEW REQUIRED",
            reconciled_action="HOLD",
            deterministic_action=deterministic_action,
            proposed_action=proposed_action,
            llm_review=llm_review,
            llm_confidence=llm_confidence,
            evidence_score=evidence_score,
            evidence_strength=evidence_strength,
            deterministic_confidence=deterministic_confidence,
            decision_support=decision_support,
            existing_holding=existing_holding,
            asset_type=asset_type,
            governance_flags=governance_flags,
            reasons=reasons,
            automatic_approval=False,
        )

    # --------------------------------------------------------
    # Explicit LLM rejection.
    # --------------------------------------------------------

    if llm_review == "REJECT":

        governance_flags.append(
            "LLM REJECT"
        )

        reasons.append(
            "The independent LLM review rejects the deterministic proposal."
        )

        reasons.append(
            "The proposal requires further governance review."
        )

        return _build_result(
            status="REVIEW REQUIRED",
            reconciled_action="HOLD",
            deterministic_action=deterministic_action,
            proposed_action=proposed_action,
            llm_review=llm_review,
            llm_confidence=llm_confidence,
            evidence_score=evidence_score,
            evidence_strength=evidence_strength,
            deterministic_confidence=deterministic_confidence,
            decision_support=decision_support,
            existing_holding=existing_holding,
            asset_type=asset_type,
            governance_flags=governance_flags,
            reasons=reasons,
            automatic_approval=False,
        )

    # --------------------------------------------------------
    # LLM ACCEPT.
    # --------------------------------------------------------

    if llm_review == "ACCEPT":

        reasons.append(
            "The independent LLM review supports the deterministic proposal."
        )

        if llm_confidence < MIN_LLM_CONFIDENCE:

            governance_flags.append(
                "LOW LLM CONFIDENCE"
            )

            reasons.append(
                "LLM confidence is too low to materially strengthen the proposal."
            )

            return _build_result(
                status="REVIEW REQUIRED",
                reconciled_action="HOLD",
                deterministic_action=deterministic_action,
                proposed_action=proposed_action,
                llm_review=llm_review,
                llm_confidence=llm_confidence,
                evidence_score=evidence_score,
                evidence_strength=evidence_strength,
                deterministic_confidence=deterministic_confidence,
                decision_support=decision_support,
                existing_holding=existing_holding,
                asset_type=asset_type,
                governance_flags=governance_flags,
                reasons=reasons,
                automatic_approval=False,
            )

        # ----------------------------------------------------
        # BUY NEW with immature historical evidence.
        # ----------------------------------------------------

        if buy_new_immature_history_override:

            governance_flags.append(
                "BUY NEW WITH IMMATURE HISTORICAL EVIDENCE"
            )

            reasons.append(
                "BUY NEW is supported by a strong current investment case; historical evidence is immature rather than materially negative."
            )

            reasons.append(
                "The independent LLM review accepts the proposal."
            )

            return _build_result(
                status="SUPPORTED WITH IMMATURE EVIDENCE",
                reconciled_action="BUY NEW",
                deterministic_action=deterministic_action,
                proposed_action=proposed_action,
                llm_review=llm_review,
                llm_confidence=llm_confidence,
                evidence_score=evidence_score,
                evidence_strength=evidence_strength,
                deterministic_confidence=deterministic_confidence,
                decision_support=decision_support,
                existing_holding=existing_holding,
                asset_type=asset_type,
                governance_flags=governance_flags,
                reasons=reasons,
                automatic_approval=True,
                governance_reason_code="BUY_NEW_IMMATURE_HISTORY",
                governance_reason=(
                    "BUY NEW approved because current deterministic "
                    "evidence and investment quality are sufficiently "
                    "strong while historical evidence remains immature."
                ),
            )

        # ----------------------------------------------------
        # SELL requires strongest deterministic evidence.
        # ----------------------------------------------------

        if (
            proposed_action == "SELL"
            and
            evidence_score < SELL_EVIDENCE_SCORE
        ):

            governance_flags.append(
                "SELL EVIDENCE BELOW THRESHOLD"
            )

            reasons.append(
                "SELL requires stronger deterministic evidence than the current proposal provides."
            )

            return _build_result(
                status="REVIEW REQUIRED",
                reconciled_action="HOLD",
                deterministic_action=deterministic_action,
                proposed_action=proposed_action,
                llm_review=llm_review,
                llm_confidence=llm_confidence,
                evidence_score=evidence_score,
                evidence_strength=evidence_strength,
                deterministic_confidence=deterministic_confidence,
                decision_support=decision_support,
                existing_holding=existing_holding,
                asset_type=asset_type,
                governance_flags=governance_flags,
                reasons=reasons,
                automatic_approval=False,
            )

        # ----------------------------------------------------
        # REDUCE / SELL / other high-impact actions.
        #
        # BUY MORE has already been handled by the dedicated
        # governance gate above.
        # ----------------------------------------------------

        if (
            _requires_strong_evidence(
                proposed_action
            )
            and
            evidence_score < STRONG_EVIDENCE_SCORE
        ):

            governance_flags.append(
                "STRONG EVIDENCE REQUIRED"
            )

            governance_reason_code = (
                "DETERMINISTIC_EVIDENCE_THRESHOLD"
            )

            governance_reason = (
                f"{proposed_action} was not automatically approved because "
                f"the deterministic evidence score of {evidence_score:.2f} "
                f"is below the required strong-evidence threshold of "
                f"{STRONG_EVIDENCE_SCORE:.2f}."
            )

            reasons.append(
                governance_reason
            )

            return _build_result(
                status="REVIEW REQUIRED",
                reconciled_action="HOLD",
                deterministic_action=deterministic_action,
                proposed_action=proposed_action,
                llm_review=llm_review,
                llm_confidence=llm_confidence,
                evidence_score=evidence_score,
                evidence_strength=evidence_strength,
                deterministic_confidence=deterministic_confidence,
                decision_support=decision_support,
                existing_holding=existing_holding,
                asset_type=asset_type,
                governance_flags=governance_flags,
                reasons=reasons,
                automatic_approval=False,
                governance_reason_code=governance_reason_code,
                governance_reason=governance_reason,
            )

        # ----------------------------------------------------
        # Strong deterministic + LLM agreement.
        # ----------------------------------------------------

        if (
            evidence_score >= MIN_EVIDENCE_SCORE
            and
            deterministic_confidence >= MIN_DETERMINISTIC_CONFIDENCE
        ):

            reasons.append(
                "Deterministic evidence and independent LLM review are aligned."
            )

            if llm_confidence >= STRONG_LLM_CONFIDENCE:

                reasons.append(
                    "LLM review has strong confidence."
                )

            return _build_result(
                status="SUPPORTED",
                reconciled_action=proposed_action,
                deterministic_action=deterministic_action,
                proposed_action=proposed_action,
                llm_review=llm_review,
                llm_confidence=llm_confidence,
                evidence_score=evidence_score,
                evidence_strength=evidence_strength,
                deterministic_confidence=deterministic_confidence,
                decision_support=decision_support,
                existing_holding=existing_holding,
                asset_type=asset_type,
                governance_flags=governance_flags,
                reasons=reasons,
                automatic_approval=True,
            )

    # --------------------------------------------------------
    # Defensive fallback.
    # --------------------------------------------------------

    governance_flags.append(
        "UNRESOLVED RECONCILIATION"
    )

    reasons.append(
        "The deterministic proposal could not be reconciled with sufficient confidence."
    )

    return _build_result(
        status="REVIEW REQUIRED",
        reconciled_action="HOLD",
        deterministic_action=deterministic_action,
        proposed_action=proposed_action,
        llm_review=llm_review,
        llm_confidence=llm_confidence,
        evidence_score=evidence_score,
        evidence_strength=evidence_strength,
        deterministic_confidence=deterministic_confidence,
        decision_support=decision_support,
        existing_holding=existing_holding,
        asset_type=asset_type,
        governance_flags=governance_flags,
        reasons=reasons,
        automatic_approval=False,
    )


# ============================================================
# Public compatibility API
# ============================================================

def reconcile_ai_decision(
    decision: dict,
    review: dict,
) -> dict:
    """
    Public entry point used by the production chain and
    AI decision-layer test harness.
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
    Reconcile multiple deterministic decisions and reviews.

    Missing reviews are handled conservatively.
    """

    if not decisions:
        return []

    if not isinstance(
        decisions,
        list,
    ):
        decisions = [decisions]

    if not isinstance(
        reviews,
        list,
    ):
        reviews = []

    results = []

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
    # TEST 1: REDUCE 25% with strong bearish evidence.
    # --------------------------------------------------------

    reduce_decision = {
        "Final Decision": "REDUCE 25%",
        "Proposed Action": "REDUCE 25%",
        "Evidence Score": 82.5,
        "Evidence Strength": "VERY STRONG",
        "Decision Support": "SUPPORTED",
        "Confidence": 72.61,
        "Existing Holding": True,
        "Asset Type": "STOCK",
        "Investment Score": 25.0,
        "Signal": "SELL",
    }

    reduce_review = {
        "Review Decision": "ACCEPT",
        "LLM Confidence": 85.0,
        "Challenge": False,
        "Reviewer Status": "LLM REVIEW COMPLETE",
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

    # --------------------------------------------------------
    # TEST 2: QUALIFIED BUY MORE.
    # --------------------------------------------------------

    buy_more_decision = {
        "Final Decision": "BUY MORE",
        "Proposed Action": "BUY MORE",
        "Evidence Score": 78.0,
        "Evidence Strength": "STRONG",
        "Decision Support": "SUPPORTED",
        "Confidence": 74.0,
        "Existing Holding": True,
        "Asset Type": "STOCK",
        "Investment Score": 86.0,
        "Signal": "STRONG BUY",
        "Allocation %": 1.5,
    }

    buy_more_review = {
        "Review Decision": "ACCEPT",
        "LLM Confidence": 82.0,
        "Challenge": False,
        "Reviewer Status": "LLM REVIEW COMPLETE",
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

    print(
        "Governance Reason Code:",
        result["Governance Reason Code"],
    )

    # --------------------------------------------------------
    # TEST 3: BUY MORE fails because allocation is too high.
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
        "TEST 3: BUY MORE ABOVE 2% ALLOCATION"
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
    # TEST 4: BUY MORE fails because LLM confidence is below 75.
    # --------------------------------------------------------

    buy_more_low_llm = dict(
        buy_more_decision
    )

    buy_more_low_llm_review = dict(
        buy_more_review
    )

    buy_more_low_llm_review[
        "LLM Confidence"
    ] = 70.0

    result = reconcile_decision(
        decision=buy_more_low_llm,
        review=buy_more_low_llm_review,
    )

    print()
    print(
        "TEST 4: BUY MORE LOW LLM CONFIDENCE"
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
