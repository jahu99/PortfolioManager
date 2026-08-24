"""
AI Decision Explanation

Purpose
-------
Create a structured, human-readable explanation of the governed
portfolio decision.

This module sits between the evidence/review stages and the final
portfolio decision output.

Architecture
------------
    Analytical Engines
            |
            v
    AI Decision Context
            |
            v
    AI Decision Scoring
            |
            v
    AI Decision Layer
            |
            v
    AI Decision Reconciliation
            |
            v
    AI Decision Explanation
            |
            v
    Final Portfolio Decision

Important
---------
This module does NOT make or change the portfolio decision.

It explains the decision already produced by the governed
decision process.

The deterministic portfolio decision remains authoritative.

The LLM reviewer is treated as independent review evidence.
It cannot silently override the deterministic decision.

Design principles
-----------------
- HOLD remains the default.
- Explanations must reflect the actual decision.
- Explanations must distinguish BUY NEW from BUY MORE.
- Existing holdings must be explicitly recognised.
- REDUCE / SELL decisions require clear justification.
- LLM disagreement must be visible.
- Missing evidence must be disclosed.
- Governance constraints must be disclosed.
- No evidence may be invented.
- No capital allocation is performed here.
- No trade execution is performed here.
"""

from __future__ import annotations

from typing import Any


# ============================================================
# Configuration
# ============================================================

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


def _clean_text(
    value: Any,
    default: str = "",
) -> str:
    """Safely convert a value to normalised text."""

    if value is None:
        return default

    try:

        text = str(value).strip()

    except Exception:

        return default

    return text


def _upper(
    value: Any,
    default: str = "",
) -> str:
    """Return normalised uppercase text."""

    return _clean_text(
        value,
        default=default,
    ).upper()


def _as_bool(
    value: Any,
    default: bool = False,
) -> bool:
    """Safely convert common boolean representations."""

    if isinstance(
        value,
        bool,
    ):
        return value

    if value is None:
        return default

    text = _upper(
        value
    )

    if text in {
        "TRUE",
        "YES",
        "Y",
        "1",
        "OWNED",
        "EXISTING",
    }:
        return True

    if text in {
        "FALSE",
        "NO",
        "N",
        "0",
        "NOT OWNED",
        "NEW",
    }:
        return False

    return default


def _as_list(
    value: Any,
) -> list:
    """Safely convert a value into a list."""

    if value is None:
        return []

    if isinstance(
        value,
        list,
    ):
        return value

    if isinstance(
        value,
        tuple,
    ):
        return list(value)

    return [value]


def _first_available(
    *values: Any,
    default: Any = None,
) -> Any:
    """Return the first non-empty value."""

    for value in values:

        if value is None:
            continue

        if isinstance(
            value,
            str,
        ) and not value.strip():
            continue

        return value

    return default


# ============================================================
# Context extraction
# ============================================================

def _get_candidate(
    candidate: dict,
) -> dict:
    """Return a safe candidate dictionary."""

    if not isinstance(
        candidate,
        dict,
    ):
        return {}

    return candidate


def _get_analysis(
    candidate: dict,
) -> dict:
    """Return the analysis section."""

    analysis = candidate.get(
        "analysis",
        {},
    )

    if not isinstance(
        analysis,
        dict,
    ):
        return {}

    return analysis


def _get_ownership(
    candidate: dict,
) -> dict:
    """Return the ownership section."""

    ownership = candidate.get(
        "ownership",
        {},
    )

    if not isinstance(
        ownership,
        dict,
    ):
        return {}

    return ownership


def _get_rules(
    candidate: dict,
    decision: dict,
) -> dict:
    """
    Return the rules-based decision section.

    Supports both the candidate context and the final decision
    structure.
    """

    rules = candidate.get(
        "rules_based_decision",
        {},
    )

    if isinstance(
        rules,
        dict,
    ) and rules:

        return rules

    rules = decision.get(
        "rules_based_decision",
        {},
    )

    if isinstance(
        rules,
        dict,
    ):
        return rules

    return {}


def _get_intelligence(
    candidate: dict,
) -> dict:
    """Return recommendation-intelligence evidence."""

    intelligence = candidate.get(
        "recommendation_intelligence",
        {},
    )

    if not isinstance(
        intelligence,
        dict,
    ):
        return {}

    return intelligence


def _get_evidence(
    decision: dict,
) -> dict:
    """Return the evidence assessment."""

    evidence = decision.get(
        "Evidence Assessment",
        {},
    )

    if not isinstance(
        evidence,
        dict,
    ):
        return {}

    return evidence


# ============================================================
# Core field extraction
# ============================================================

def get_ticker(
    candidate: dict,
    decision: dict,
) -> str:
    """Return ticker."""

    return _upper(
        _first_available(
            candidate.get("ticker"),
            candidate.get("Ticker"),
            decision.get("Ticker"),
            default="",
        )
    )


def get_asset_type(
    candidate: dict,
    decision: dict,
) -> str:
    """Return STOCK or ETF."""

    value = _first_available(
        candidate.get("asset_type"),
        candidate.get("Asset Type"),
        decision.get("Asset Type"),
        default="STOCK",
    )

    asset_type = _upper(
        value,
        default="STOCK",
    )

    if asset_type == "EQUITY":
        return "STOCK"

    if asset_type not in {
        "STOCK",
        "ETF",
    }:
        return "STOCK"

    return asset_type


def get_action(
    candidate: dict,
    decision: dict,
) -> str:
    """
    Return the authoritative portfolio action.

    The final decision is preferred where available.
    """

    evidence = _get_evidence(
        decision
    )

    rules = _get_rules(
        candidate,
        decision,
    )

    action = _first_available(
        decision.get("Final Decision"),
        decision.get("Decision"),
        decision.get("Proposed Action"),
        rules.get("action"),
        evidence.get("Action"),
        candidate.get("Proposed Action"),
        default="HOLD",
    )

    action = _upper(
        action,
        default="HOLD",
    )

    if action not in VALID_ACTIONS:
        return "HOLD"

    return action


def get_existing_holding(
    candidate: dict,
) -> bool:
    """Return whether the asset is already owned."""

    ownership = _get_ownership(
        candidate
    )

    return _as_bool(
        _first_available(
            ownership.get("owned"),
            candidate.get("Existing Holding"),
            candidate.get("existing_holding"),
            default=False,
        )
    )


def get_allocation_pct(
    candidate: dict,
) -> float:
    """Return current portfolio allocation."""

    ownership = _get_ownership(
        candidate
    )

    return _safe_float(
        _first_available(
            ownership.get("allocation_pct"),
            candidate.get("Allocation %"),
            candidate.get("allocation_pct"),
            default=0.0,
        )
    )


def get_quantity(
    candidate: dict,
) -> float:
    """Return current holding quantity."""

    ownership = _get_ownership(
        candidate
    )

    return _safe_float(
        ownership.get(
            "quantity",
            0.0,
        )
    )


def get_investment_score(
    candidate: dict,
    decision: dict,
) -> float:
    """Return the core investment score."""

    analysis = _get_analysis(
        candidate
    )

    evidence = _get_evidence(
        decision
    )

    return _safe_float(
        _first_available(
            analysis.get("investment_score"),
            evidence.get("Investment Score"),
            candidate.get("Investment Score"),
            default=0.0,
        )
    )


def get_signal(
    candidate: dict,
    decision: dict,
) -> str:
    """Return current recommendation signal."""

    analysis = _get_analysis(
        candidate
    )

    evidence = _get_evidence(
        decision
    )

    return _upper(
        _first_available(
            analysis.get("signal"),
            evidence.get("Signal"),
            candidate.get("Signal"),
            default="",
        )
    )


def get_learning_adjusted_score(
    candidate: dict,
    decision: dict,
) -> float:
    """Return learning-adjusted score."""

    intelligence = _get_intelligence(
        candidate
    )

    evidence = _get_evidence(
        decision
    )

    return _safe_float(
        _first_available(
            intelligence.get(
                "learning_adjusted_score"
            ),
            evidence.get(
                "Learning Adjusted Score"
            ),
            candidate.get(
                "Learning Adjusted Score"
            ),
            default=0.0,
        )
    )

def get_historical_observations(
    candidate: dict,
    decision: dict,
) -> float:
    """Return historical signal observations."""

    intelligence = _get_intelligence(
        candidate
    )

    evidence = _get_evidence(
        decision
    )

    return _safe_float(
        _first_available(
            intelligence.get(
                "historical_signal_observations"
            ),
            evidence.get(
                "Historical Signal Observations"
            ),
            default=0.0,
        )
    )


def get_historical_win_rate(
    candidate: dict,
    decision: dict,
) -> float:
    """Return historical signal win rate."""

    intelligence = _get_intelligence(
        candidate
    )

    evidence = _get_evidence(
        decision
    )

    return _safe_float(
        _first_available(
            intelligence.get(
                "historical_signal_win_rate_pct"
            ),
            evidence.get(
                "Historical Signal Win Rate %"
            ),
            default=0.0,
        )
    )


def get_historical_return(
    candidate: dict,
    decision: dict,
) -> float:
    """Return historical average return."""

    intelligence = _get_intelligence(
        candidate
    )

    evidence = _get_evidence(
        decision
    )

    return _safe_float(
        _first_available(
            intelligence.get(
                "historical_signal_average_return_pct"
            ),
            evidence.get(
                "Historical Signal Average Return %"
            ),
            default=0.0,
        )
    )


def get_reliability(
    candidate: dict,
    decision: dict,
) -> str:
    """Return historical reliability status."""

    intelligence = _get_intelligence(
        candidate
    )

    evidence = _get_evidence(
        decision
    )

    return _upper(
        _first_available(
            intelligence.get(
                "historical_signal_reliability"
            ),
            evidence.get(
                "Historical Signal Reliability"
            ),
            default="",
        )
    )


def get_evidence_score(
    decision: dict,
) -> float:
    """Return evidence score."""

    evidence = _get_evidence(
        decision
    )

    return _safe_float(
        _first_available(
            decision.get("Evidence Score"),
            evidence.get("Evidence Score"),
            default=0.0,
        )
    )


def get_evidence_strength(
    decision: dict,
) -> str:
    """Return evidence strength."""

    evidence = _get_evidence(
        decision
    )

    return _upper(
        _first_available(
            decision.get("Evidence Strength"),
            evidence.get("Evidence Strength"),
            default="UNKNOWN",
        )
    )


def get_decision_support(
    decision: dict,
) -> str:
    """Return deterministic decision support status."""

    evidence = _get_evidence(
        decision
    )

    return _upper(
        _first_available(
            decision.get("Decision Support"),
            evidence.get("Decision Support"),
            default="UNKNOWN",
        )
    )


def get_confidence(
    decision: dict,
) -> float:
    """Return deterministic decision confidence."""

    evidence = _get_evidence(
        decision
    )

    value = _first_available(
        decision.get("Confidence"),
        evidence.get("Confidence"),
        default=0.0,
    )

    return max(
        0.0,
        min(
            100.0,
            _safe_float(value),
        ),
    )


# ============================================================
# LLM review extraction
# ============================================================

def get_llm_review(
    review: dict | None,
) -> dict:
    """Return a safe LLM review dictionary."""

    if not isinstance(
        review,
        dict,
    ):
        return {}

    return review


def get_llm_decision(
    review: dict,
) -> str:
    """Return LLM review decision."""

    value = _first_available(
        review.get("LLM Assessment"),
        review.get("LLM Decision"),
        review.get("Review Decision"),
        default="CHALLENGE",
    )

    value = _upper(
        value,
        default="CHALLENGE",
    )

    if value not in VALID_REVIEW_DECISIONS:
        return "CHALLENGE"

    return value


def get_llm_confidence(
    review: dict,
) -> float:
    """Return LLM confidence."""

    value = _safe_float(
        _first_available(
            review.get("LLM Confidence"),
            review.get("Confidence"),
            default=0.0,
        )
    )

    return max(
        0.0,
        min(
            100.0,
            value,
        ),
    )


def get_llm_reason(
    review: dict,
) -> str:
    """Return LLM review reason."""

    return _clean_text(
        _first_available(
            review.get("LLM Reason"),
            review.get("Reason"),
            default="",
        )
    )


def get_llm_challenge(
    review: dict,
) -> bool:
    """Return whether the LLM explicitly challenged."""

    return _as_bool(
        review.get(
            "Challenge",
            False,
        )
    )


def get_llm_key_points(
    review: dict,
) -> list[str]:
    """Return LLM key points."""

    values = _as_list(
        review.get(
            "Key Points",
            [],
        )
    )

    return [
        _clean_text(value)
        for value in values
        if _clean_text(value)
    ]


def get_llm_evidence_gaps(
    review: dict,
) -> list[str]:
    """Return LLM evidence gaps."""

    values = _as_list(
        review.get(
            "Evidence Gaps",
            [],
        )
    )

    return [
        _clean_text(value)
        for value in values
        if _clean_text(value)
    ]


# ============================================================
# Governance interpretation
# ============================================================

def build_governance_reasons(
    candidate: dict,
    decision: dict,
    review: dict,
) -> list[str]:
    """
    Build explicit governance reasons.

    These are derived from supplied evidence and existing
    decision outputs only.
    """

    reasons: list[str] = []

    action = get_action(
        candidate,
        decision,
    )

    existing = get_existing_holding(
        candidate
    )

    allocation = get_allocation_pct(
        candidate
    )

    evidence_score = get_evidence_score(
        decision
    )

    support = get_decision_support(
        decision
    )

    llm_decision = get_llm_decision(
        review
    )

    observations = get_historical_observations(
        candidate,
        decision,
    )

    # --------------------------------------------------------
    # HOLD baseline
    # --------------------------------------------------------

    if action == "HOLD":

        reasons.append(
            "HOLD remains the default portfolio action "
            "unless stronger evidence supports change."
        )

    # --------------------------------------------------------
    # Existing holding
    # --------------------------------------------------------

    if existing:

        reasons.append(
            f"Existing holding is protected from unnecessary "
            f"turnover at approximately {allocation:.2f}% allocation."
        )

    # --------------------------------------------------------
    # BUY NEW
    # --------------------------------------------------------

    if action == "BUY NEW":

        reasons.append(
            "BUY NEW requires evidence that justifies opening "
            "a new portfolio position."
        )

    # --------------------------------------------------------
    # BUY MORE
    # --------------------------------------------------------

    if action == "BUY MORE":

        reasons.append(
            "BUY MORE requires stronger portfolio justification "
            "because the position already exists."
        )

    # --------------------------------------------------------
    # REDUCE / SELL
    # --------------------------------------------------------

    if action in {
        "REDUCE",
        "SELL",
    }:

        reasons.append(
            f"{action} requires stronger evidence than maintaining "
            "the existing position."
        )

    # --------------------------------------------------------
    # Historical evidence
    # --------------------------------------------------------

    if observations <= 0:

        reasons.append(
            "Historical recommendation evidence is unavailable."
        )

    else:

        reasons.append(
            f"Historical evidence is based on "
            f"{int(observations)} observations."
        )

    # --------------------------------------------------------
    # Evidence support
    # --------------------------------------------------------

    if support == "SUPPORTED":

        reasons.append(
            f"Deterministic evidence supports the proposed "
            f"{action} action with an evidence score of "
            f"{evidence_score:.2f}."
        )

    elif support == "CONDITIONAL":

        reasons.append(
            f"The proposed {action} action is only conditionally "
            f"supported by the available evidence."
        )

    else:

        reasons.append(
            f"The available evidence does not strongly support "
            f"the proposed {action} action."
        )

    # --------------------------------------------------------
    # LLM review
    # --------------------------------------------------------

    if llm_decision == "ACCEPT":

        reasons.append(
            "Independent LLM review accepts the deterministic proposal."
        )

    elif llm_decision == "CHALLENGE":

        reasons.append(
            "Independent LLM review challenges or questions "
            "the deterministic proposal."
        )

    elif llm_decision == "REJECT":

        reasons.append(
            "Independent LLM review rejects the deterministic proposal."
        )

    return reasons


# ============================================================
# Evidence summary
# ============================================================

def build_evidence_summary(
    candidate: dict,
    decision: dict,
) -> list[str]:
    """
    Build concise evidence statements.

    Every statement is derived from supplied data.
    """

    evidence: list[str] = []

    investment_score = get_investment_score(
        candidate,
        decision,
    )

    signal = get_signal(
        candidate,
        decision,
    )

    learning_score = get_learning_adjusted_score(
        candidate,
        decision,
    )

    observations = get_historical_observations(
        candidate,
        decision,
    )

    win_rate = get_historical_win_rate(
        candidate,
        decision,
    )

    average_return = get_historical_return(
        candidate,
        decision,
    )

    reliability = get_reliability(
        candidate,
        decision,
    )

    if investment_score > 0:

        evidence.append(
            f"Investment Score: {investment_score:.2f}."
        )

    if signal:

        evidence.append(
            f"Current signal: {signal}."
        )

    if learning_score > 0:

        evidence.append(
            f"Learning-adjusted score: {learning_score:.2f}."
        )

    if observations > 0:

        evidence.append(
            f"Historical signal evidence: "
            f"{int(observations)} observations, "
            f"{win_rate:.2f}% win rate, "
            f"{average_return:.2f}% average return."
        )

    if reliability:

        evidence.append(
            f"Historical reliability: {reliability}."
        )

    if not evidence:

        evidence.append(
            "No material analytical evidence was available "
            "for explanation."
        )

    return evidence


# ============================================================
# Review interpretation
# ============================================================

def build_review_summary(
    review: dict,
) -> list[str]:
    """Build a concise summary of the independent LLM review."""

    if not review:

        return [
            "No independent LLM review was available."
        ]

    llm_decision = get_llm_decision(
        review
    )

    confidence = get_llm_confidence(
        review
    )

    reason = get_llm_reason(
        review
    )

    summary = [
        f"LLM review: {llm_decision} "
        f"with {confidence:.2f}% confidence."
    ]

    if reason:

        summary.append(
            f"LLM reviewer reason: {reason}"
        )

    return summary


# ============================================================
# Final explanation
# ============================================================

def build_decision_explanation(
    candidate: dict,
    decision: dict,
    review: dict | None = None,
) -> dict:
    """
    Build the structured explanation for a governed decision.

    This function does not alter the decision.
    """

    candidate = _get_candidate(
        candidate
    )

    if not isinstance(
        decision,
        dict,
    ):
        decision = {}

    review = get_llm_review(
        review
    )

    ticker = get_ticker(
        candidate,
        decision,
    )

    asset_type = get_asset_type(
        candidate,
        decision,
    )

    action = get_action(
        candidate,
        decision,
    )

    existing = get_existing_holding(
        candidate
    )

    allocation = get_allocation_pct(
        candidate
    )

    quantity = get_quantity(
        candidate
    )

    evidence_score = get_evidence_score(
        decision
    )

    evidence_strength = get_evidence_strength(
        decision
    )

    decision_support = get_decision_support(
        decision
    )

    confidence = get_confidence(
        decision
    )

    llm_decision = get_llm_decision(
        review
    )

    llm_confidence = get_llm_confidence(
        review
    )

    llm_reason = get_llm_reason(
        review
    )

    llm_challenge = get_llm_challenge(
        review
    )

    key_points = get_llm_key_points(
        review
    )

    evidence_gaps = get_llm_evidence_gaps(
        review
    )

    governance_reasons = build_governance_reasons(
        candidate,
        decision,
        review,
    )

    evidence_summary = build_evidence_summary(
        candidate,
        decision,
    )

    review_summary = build_review_summary(
        review
    )

    # --------------------------------------------------------
    # Determine whether the deterministic and LLM views agree.
    #
    # The LLM review is advisory. Agreement does not make the
    # LLM authoritative.
    # --------------------------------------------------------

    if llm_decision == "ACCEPT":

        review_alignment = "ALIGNED"

    elif llm_decision in {
        "CHALLENGE",
        "REJECT",
    }:

        review_alignment = "NOT ALIGNED"

    else:

        review_alignment = "UNKNOWN"

    # --------------------------------------------------------
    # Explanation headline
    # --------------------------------------------------------

    if action == "BUY NEW":

        headline = (
            f"{ticker}: BUY NEW is supported only where the "
            "available evidence justifies opening a new position."
        )

    elif action == "BUY MORE":

        headline = (
            f"{ticker}: BUY MORE is supported only where the "
            "opportunity outweighs the additional concentration "
            "created by increasing an existing position."
        )

    elif action == "REDUCE":

        headline = (
            f"{ticker}: REDUCE is supported where evidence "
            "justifies lowering the existing portfolio exposure."
        )

    elif action == "SELL":

        headline = (
            f"{ticker}: SELL requires sufficiently strong evidence "
            "that continuing to hold the position is no longer "
            "justified."
        )

    else:

        headline = (
            f"{ticker}: HOLD remains the baseline because the "
            "evidence does not provide a sufficiently strong "
            "reason to change the position."
        )

    # --------------------------------------------------------
    # Explicit missing evidence handling
    # --------------------------------------------------------

    if not evidence_gaps:

        observations = get_historical_observations(
            candidate,
            decision,
        )

        if observations <= 0:

            evidence_gaps.append(
                "No historical signal observations are available."
            )

    return {
        "Ticker":
            ticker,

        "Asset Type":
            asset_type,

        "Final Decision":
            action,

        "Headline":
            headline,

        "Existing Holding":
            existing,

        "Current Allocation %":
            round(
                allocation,
                2,
            ),

        "Current Quantity":
            round(
                quantity,
                6,
            ),

        "Evidence Score":
            round(
                evidence_score,
                2,
            ),

        "Evidence Strength":
            evidence_strength,

        "Decision Support":
            decision_support,

        "Deterministic Confidence":
            round(
                confidence,
                2,
            ),

        "Evidence Summary":
            evidence_summary,

        "Governance Reasons":
            governance_reasons,

        "LLM Review Decision":
            llm_decision,

        "LLM Review Confidence":
            round(
                llm_confidence,
                2,
            ),

        "LLM Review Alignment":
            review_alignment,

        "LLM Challenge":
            llm_challenge,

        "LLM Review Reason":
            llm_reason,

        "LLM Key Points":
            key_points,

        "Evidence Gaps":
            evidence_gaps,

        "LLM Review Summary":
            review_summary,

        "Decision Explanation":
            headline,

        # ----------------------------------------------------
        # Explicit governance statement.
        # ----------------------------------------------------

        "Authority":
            "DETERMINISTIC GOVERNED DECISION LAYER",

        "LLM Role":
            "INDEPENDENT REVIEW ONLY",

        "Capital Allocation":
            "NOT PERFORMED BY THIS MODULE",

        "Trade Execution":
            "NOT PERFORMED BY THIS MODULE",

    }


# ============================================================
# Batch explanation
# ============================================================

def explain_ai_decisions(
    candidates: list[dict] | None = None,
    decisions: list[dict] | None = None,
    reviews: list[dict] | None = None,
) -> list[dict]:
    """
    Build explanations for multiple portfolio decisions.

    Candidates, decisions and reviews are matched by list position.
    Missing entries are handled safely.
    """

    if not isinstance(
        candidates,
        list,
    ):
        candidates = []

    if not isinstance(
        decisions,
        list,
    ):
        decisions = []

    if not isinstance(
        reviews,
        list,
    ):
        reviews = []

    count = max(
        len(candidates),
        len(decisions),
        len(reviews),
    )

    results = []

    for index in range(
        count
    ):

        candidate = (
            candidates[index]
            if index < len(candidates)
            else {}
        )

        decision = (
            decisions[index]
            if index < len(decisions)
            else {}
        )

        review = (
            reviews[index]
            if index < len(reviews)
            else {}
        )

        results.append(
            build_decision_explanation(
                candidate=candidate,
                decision=decision,
                review=review,
            )
        )

    return results


# ============================================================
# Compatibility API
# ============================================================

def explain_ai_decision(
    candidate: dict | None = None,
    decision: dict | None = None,
    review: dict | None = None,
    candidate_context: dict | None = None,
    ai_decision: dict | None = None,
    llm_review: dict | None = None,
    **kwargs: Any,
) -> dict:
    """
    Public compatibility entry point.

    Supports both the preferred interface:

        explain_ai_decision(
            candidate=candidate,
            decision=decision,
            review=review,
        )

    and compatibility aliases used by test harnesses.
    """

    if candidate is None:

        candidate = candidate_context

    if decision is None:

        decision = ai_decision

    if review is None:

        review = llm_review

    if not isinstance(
        candidate,
        dict,
    ):
        candidate = {}

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

    return build_decision_explanation(
        candidate=candidate,
        decision=decision,
        review=review,
    )


# ============================================================
# Module test
# ============================================================

if __name__ == "__main__":

    sample_candidate = {
        "ticker": "NVDA",
        "asset_type": "STOCK",
        "analysis": {
            "signal": "BUY",
            "investment_score": 82,
        },
        "ownership": {
            "owned": True,
            "allocation_pct": 8.5,
            "quantity": 50,
        },
        "recommendation_intelligence": {
            "historical_signal_observations": 120,
            "historical_signal_win_rate_pct": 62,
            "historical_signal_average_return_pct": 7.5,
            "historical_signal_reliability": "VALID",
            "learning_adjusted_score": 84,
        },
    }

    sample_decision = {
        "Final Decision": "BUY MORE",
        "Proposed Action": "BUY MORE",
        "Evidence Score": 78,
        "Evidence Strength": "STRONG",
        "Decision Support": "SUPPORTED",
        "Confidence": 82,
        "Evidence Assessment": {
            "Investment Score": 82,
            "Evidence Score": 78,
            "Evidence Strength": "STRONG",
            "Decision Support": "SUPPORTED",
            "Confidence": 82,
        },
    }

    sample_review = {
        "Ticker": "NVDA",
        "LLM Assessment": "ACCEPT",
        "LLM Confidence": 80,
        "LLM Reason": (
            "The proposed increase is supported by strong "
            "investment and historical evidence."
        ),
        "Challenge": False,
        "Key Points": [
            "Strong investment score",
            "Positive historical evidence",
        ],
        "Evidence Gaps": [],
    }

    explanation = explain_ai_decision(
        candidate=sample_candidate,
        decision=sample_decision,
        review=sample_review,
    )

    print(
        "AI Decision Explanation"
    )

    print(
        explanation
    )