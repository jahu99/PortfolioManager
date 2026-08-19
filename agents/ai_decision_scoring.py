"""
AI Decision Scoring

Purpose
-------
Score the quality of the evidence supporting a proposed portfolio decision.

This module is part of the governed AI portfolio decision layer.

Architecture
------------
    Existing analysis engines
            |
            v
    ai_decision_context.py
            |
            v
    ai_decision_scoring.py
            |
            v
    ai_decision_layer.py
            |
            v
    ai_decision_explanation.py
            |
            v
    ai_portfolio_reviewer.py
            |
            v
    ai_decision_reconciler.py
            |
            v
    Final Portfolio Decision

Important
---------
This module does NOT make the final portfolio decision.

It evaluates the evidence available to support a decision.

The final governed decision remains the responsibility of the
downstream decision layers.

Existing project engines remain authoritative for:

    decision_engine.py
    portfolio_decision_engine.py
    capital_allocator.py
    recommendation_intelligence.py

Design principles
-----------------
- HOLD remains the natural baseline.
- Strong decisions require stronger evidence.
- Historical recommendation reliability is supporting evidence.
- Learning-adjusted scores are supporting evidence only.
- Existing holdings receive additional protection.
- Concentration and portfolio risk can weaken BUY decisions.
- REDUCE / SELL require stronger evidence than HOLD.
- Missing evidence reduces confidence appropriately.
- Missing historical learning evidence should not automatically
  make a HOLD or justified REDUCE decision low confidence.
- BUY NEW and BUY MORE are assessed on the same core evidence scale,
  with BUY MORE receiving additional portfolio scrutiny.
- This module does not allocate capital.
- This module does not change core analytical scoring weights.
- This module does not execute trades.
"""

from __future__ import annotations

import math


# ============================================================
# Configuration
# ============================================================

MIN_RELIABILITY_OBSERVATIONS = 30

STRONG_RELIABILITY_OBSERVATIONS = 100

HIGH_CONCENTRATION = 25.0
VERY_HIGH_CONCENTRATION = 40.0

STRONG_SCORE = 85.0
GOOD_SCORE = 70.0
WEAK_SCORE = 55.0
VERY_WEAK_SCORE = 40.0

BUY_EVIDENCE_THRESHOLD = 60.0
STRONG_BUY_EVIDENCE_THRESHOLD = 75.0

REDUCE_EVIDENCE_THRESHOLD = 65.0
SELL_EVIDENCE_THRESHOLD = 75.0


# ============================================================
# Generic helpers
# ============================================================

def safe_float(
    value,
    default=0.0,
):
    """
    Safely convert a value to float.
    """

    try:

        if value is None:
            return default

        if isinstance(
            value,
            (list, tuple, dict),
        ):
            return default

        if isinstance(
            value,
            bool,
        ):
            return float(value)

        value = float(value)

        if not math.isfinite(value):
            return default

        return value

    except (
        TypeError,
        ValueError,
    ):

        return default


def clean_text(
    value,
    default="",
):
    """
    Safely normalise a text value.
    """

    if value is None:
        return default

    try:

        text = str(
            value
        ).strip()

    except Exception:

        return default

    if not text:
        return default

    return text.upper()


def clamp(
    value,
    minimum=0.0,
    maximum=100.0,
):
    """
    Keep a score inside a defined range.
    """

    value = safe_float(
        value
    )

    return max(
        minimum,
        min(
            maximum,
            value,
        ),
    )


def get_value(
    context,
    *keys,
    default=None,
):
    """
    Retrieve the first available value from a decision context.

    Supports both flat scoring contexts and structured AI decision
    candidate schemas.
    """

    if not isinstance(
        context,
        dict,
    ):
        return default

    # --------------------------------------------------------
    # Direct lookup
    # --------------------------------------------------------

    for key in keys:

        if key in context:

            value = context.get(
                key
            )

            if value is not None:
                return value

    # --------------------------------------------------------
    # Structured context lookup
    # --------------------------------------------------------

    nested_keys = [
        "ownership",
        "analysis",
        "rules_based_decision",
        "recommendation_intelligence",
        "capital",
        "portfolio",
        "risk",
        "historical",
        "current",
        "evidence",
        "stock",
        "holding",
        "recommendation",
    ]

    for nested_key in nested_keys:

        nested = context.get(
            nested_key
        )

        if not isinstance(
            nested,
            dict,
        ):
            continue

        for key in keys:

            if key in nested:

                value = nested.get(
                    key
                )

                if value is not None:
                    return value

            snake_key = (
                key
                .strip()
                .lower()
                .replace(
                    " ",
                    "_",
                )
                .replace(
                    "%",
                    "pct",
                )
            )

            if snake_key in nested:

                value = nested.get(
                    snake_key
                )

                if value is not None:
                    return value

    return default


# ============================================================
# Evidence extraction
# ============================================================

def get_investment_score(
    context,
):
    """Retrieve the core investment score."""

    return safe_float(
        get_value(
            context,
            "Investment Score",
            "investment_score",
            "Score",
            "score",
            default=0,
        )
    )


def get_learning_adjusted_score(
    context,
):
    """
    Retrieve the learning-adjusted score.

    If unavailable, fall back to the core investment score.

    The learning-adjusted score is supporting evidence only.
    """

    investment_score = get_investment_score(
        context
    )

    value = get_value(
        context,
        "Learning Adjusted Score",
        "learning_adjusted_score",
        default=None,
    )

    if value is None:
        return investment_score

    return clamp(
        safe_float(
            value,
            investment_score,
        )
    )


def get_learning_adjustment(
    context,
):
    """Retrieve the recommendation-learning adjustment."""

    return safe_float(
        get_value(
            context,
            "Learning Adjustment",
            "learning_adjustment",
            default=0,
        )
    )


def get_signal(
    context,
):
    """Retrieve the current recommendation signal."""

    return clean_text(
        get_value(
            context,
            "Signal",
            "Momentum Signal",
            "signal",
            default="",
        )
    )


def get_confidence(
    context,
):
    """
    Retrieve an existing upstream confidence where available.

    This is not the same as the decision-confidence calculated
    by this module.
    """

    value = get_value(
        context,
        "Confidence",
        "confidence",
        default=None,
    )

    if value is None:
        return None

    numeric = safe_float(
        value,
        default=-1,
    )

    if numeric >= 0:

        if numeric <= 1:

            return clamp(
                numeric * 100
            )

        return clamp(
            numeric
        )

    text = clean_text(
        value
    )

    mapping = {
        "VERY HIGH": 90,
        "HIGH": 80,
        "STRONG": 80,
        "MEDIUM": 60,
        "MODERATE": 60,
        "LOW": 35,
        "WEAK": 35,
        "VERY LOW": 20,
    }

    return mapping.get(
        text
    )


def get_signal_reliability(
    context,
):
    """Retrieve historical signal reliability."""

    return clean_text(
        get_value(
            context,
            "Historical Signal Reliability",
            "Signal Reliability",
            "historical_signal_reliability",
            "signal_reliability",
            "Reliability",
            default="",
        )
    )


def get_signal_observations(
    context,
):
    """Retrieve historical signal observations."""

    return safe_float(
        get_value(
            context,
            "Historical Signal Observations",
            "Signal Observations",
            "historical_signal_observations",
            "signal_observations",
            "Observations",
            default=0,
        )
    )


def get_signal_win_rate(
    context,
):
    """Retrieve historical signal win rate."""

    return safe_float(
        get_value(
            context,
            "Historical Signal Win Rate %",
            "Signal Win Rate %",
            "historical_signal_win_rate",
            "signal_win_rate",
            default=0,
        )
    )


def get_signal_average_return(
    context,
):
    """Retrieve historical signal average return."""

    return safe_float(
        get_value(
            context,
            "Historical Signal Average Return %",
            "Signal Average Return %",
            "historical_signal_average_return",
            "signal_average_return",
            default=0,
        )
    )


def get_score_bucket_observations(
    context,
):
    """Retrieve historical score-bucket observations."""

    return safe_float(
        get_value(
            context,
            "Score Bucket Observations",
            "score_bucket_observations",
            default=0,
        )
    )


def get_score_bucket_win_rate(
    context,
):
    """Retrieve historical score-bucket win rate."""

    return safe_float(
        get_value(
            context,
            "Score Bucket Win Rate %",
            "score_bucket_win_rate",
            default=0,
        )
    )


def get_score_bucket_return(
    context,
):
    """Retrieve historical score-bucket average return."""

    return safe_float(
        get_value(
            context,
            "Score Bucket Average Return %",
            "score_bucket_average_return",
            default=0,
        )
    )


def get_action(
    context,
):
    """Retrieve the proposed/current action."""

    return clean_text(
        get_value(
            context,
            "Action",
            "Proposed Action",
            "proposed_action",
            "Decision",
            "decision",
            default="HOLD",
        ),
        default="HOLD",
    )


def get_asset_type(
    context,
):
    """Retrieve asset type."""

    asset_type = clean_text(
        get_value(
            context,
            "Asset Type",
            "asset_type",
            "Type",
            default="STOCK",
        ),
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


def get_existing_holding(
    context,
):
    """Determine whether the asset is currently held."""

    value = get_value(
        context,
        "Existing Holding",
        "existing_holding",
        "Owned",
        "owned",
        default=False,
    )

    if isinstance(
        value,
        bool,
    ):
        return value

    text = clean_text(
        value
    )

    return text in {
        "YES",
        "TRUE",
        "OWNED",
        "EXISTING",
    }


def get_allocation(
    context,
):
    """Retrieve current portfolio allocation percentage."""

    return safe_float(
        get_value(
            context,
            "Allocation %",
            "Allocation",
            "allocation_pct",
            "allocation",
            default=0,
        )
    )


def get_sector_allocation(
    context,
):
    """
    Retrieve sector allocation.

    Supports either a direct percentage or nested sector exposure.
    """

    direct = get_value(
        context,
        "Sector Allocation %",
        "Sector Allocation",
        "sector_allocation",
        default=None,
    )

    if direct is not None:

        return safe_float(
            direct
        )

    sector = get_value(
        context,
        "Sector",
        "sector",
        default=None,
    )

    sector_exposure = get_value(
        context,
        "Sector Exposure",
        "sector_exposure",
        default=None,
    )

    if (
        isinstance(
            sector_exposure,
            dict,
        )
        and
        sector
    ):

        return safe_float(
            sector_exposure.get(
                sector,
                0,
            )
        )

    return 0.0


def get_concentration(
    context,
):
    """
    Retrieve portfolio concentration.

    Current position allocation is the primary measure.
    """

    explicit = get_value(
        context,
        "Concentration %",
        "concentration_pct",
        "Concentration",
        "concentration",
        default=None,
    )

    if explicit is not None:

        return safe_float(
            explicit
        )

    return get_allocation(
        context
    )


def get_risk_score(
    context,
):
    """
    Retrieve an existing portfolio/asset risk score.

    Higher score means greater risk.

    This is deliberately not recreated here.
    """

    return clamp(
        safe_float(
            get_value(
                context,
                "Risk Score",
                "risk_score",
                "Portfolio Risk Score",
                "portfolio_risk_score",
                default=0,
            )
        )
    )


# ============================================================
# Individual evidence scores
# ============================================================

def score_investment_quality(
    context,
):
    """
    Convert the existing investment score into evidence strength.
    """

    score = get_investment_score(
        context
    )

    if score >= STRONG_SCORE:
        return 100.0

    if score >= GOOD_SCORE:
        return 80.0

    if score >= WEAK_SCORE:
        return 55.0

    if score >= VERY_WEAK_SCORE:
        return 30.0

    return 10.0



def score_learning_evidence(
    context,
):
    """
    Assess whether recommendation learning provides useful
    supporting evidence.

    Historical learning is supporting evidence rather than a
    replacement for the underlying analytical score.

    Important
    ---------
    Immature historical evidence is NOT treated as negative
    evidence.

    For example:

        2 observations
        -6.79% average return
        INSUFFICIENT DATA

    should be interpreted as:

        "There is not enough evidence yet to know whether this
         signal is reliable."

    It should NOT be interpreted as:

        "The signal is demonstrably poor."

    Mature historical evidence is allowed to influence the
    evidence score according to its observed win rate and
    average return.
    """

    observations = get_signal_observations(
        context
    )

    win_rate = get_signal_win_rate(
        context
    )

    average_return = get_signal_average_return(
        context
    )

    reliability = get_signal_reliability(
        context
    )

    # --------------------------------------------------------
    # No historical observations.
    # --------------------------------------------------------

    if observations <= 0:

        return 0.0

    # --------------------------------------------------------
    # Sample-size assessment.
    #
    # < 30 observations = immature evidence.
    # 30-99             = valid evidence.
    # 100+              = strong evidence.
    # --------------------------------------------------------

    if observations >= STRONG_RELIABILITY_OBSERVATIONS:

        sample_score = 100.0
        immature_history = False

    elif observations >= MIN_RELIABILITY_OBSERVATIONS:

        sample_score = 70.0
        immature_history = False

    else:

        sample_score = 35.0
        immature_history = True

    # --------------------------------------------------------
    # Win-rate evidence.
    #
    # During the immature phase, avoid interpreting the observed
    # win rate as statistically established.
    # --------------------------------------------------------

    if immature_history:

        win_score = 50.0

    elif win_rate >= 60:

        win_score = 100.0

    elif win_rate >= 55:

        win_score = 80.0

    elif win_rate >= 50:

        win_score = 60.0

    elif win_rate > 0:

        win_score = 35.0

    else:

        win_score = 0.0

    # --------------------------------------------------------
    # Return evidence.
    #
    # During the immature phase, the observed return is treated
    # as neutral rather than negative because the sample is too
    # small to establish reliability.
    # --------------------------------------------------------

    if immature_history:

        return_score = 50.0

    else:

        if average_return >= 5:

            return_score = 100.0

        elif average_return > 0:

            return_score = 70.0

        elif average_return == 0:

            return_score = 50.0

        else:

            return_score = 20.0

    # --------------------------------------------------------
    # Reliability classification.
    # --------------------------------------------------------

    reliability_bonus = 0.0

    if reliability == "VALID":

        reliability_bonus = 10.0

    elif reliability == "INVALID":

        reliability_bonus = -10.0

    elif reliability == "INSUFFICIENT DATA":

        # Insufficient data is not negative evidence.
        reliability_bonus = 0.0

    # --------------------------------------------------------
    # Final learning evidence score.
    # --------------------------------------------------------

    evidence = (
        sample_score * 0.35
        +
        win_score * 0.35
        +
        return_score * 0.20
        +
        50.0 * 0.10
        +
        reliability_bonus
    )

    return clamp(
        evidence
    )




def score_score_bucket_evidence(
    context,
):
    """Assess historical evidence for the current score bucket."""

    observations = get_score_bucket_observations(
        context
    )

    win_rate = get_score_bucket_win_rate(
        context
    )

    average_return = get_score_bucket_return(
        context
    )

    if observations <= 0:

        return 0.0

    if observations >= STRONG_RELIABILITY_OBSERVATIONS:

        sample_score = 100.0

    elif observations >= MIN_RELIABILITY_OBSERVATIONS:

        sample_score = 70.0

    else:

        sample_score = 35.0

    if win_rate >= 60:

        win_score = 100.0

    elif win_rate >= 55:

        win_score = 80.0

    elif win_rate >= 50:

        win_score = 60.0

    else:

        win_score = 30.0

    if average_return >= 5:

        return_score = 100.0

    elif average_return > 0:

        return_score = 70.0

    elif average_return == 0:

        return_score = 50.0

    else:

        return_score = 20.0

    return clamp(
        sample_score * 0.35
        +
        win_score * 0.35
        +
        return_score * 0.30
    )


def score_portfolio_fit(
    context,
):
    """
    Assess whether the proposed action fits the portfolio.
    """

    action = get_action(
        context
    )

    existing = get_existing_holding(
        context
    )

    allocation = get_allocation(
        context
    )

    sector_allocation = get_sector_allocation(
        context
    )

    concentration = get_concentration(
        context
    )

    score = 70.0

    if (
        action == "BUY MORE"
        and
        existing
    ):

        if concentration >= VERY_HIGH_CONCENTRATION:

            score -= 40

        elif concentration >= HIGH_CONCENTRATION:

            score -= 20

        elif allocation >= 10:

            score -= 10

    if action == "BUY NEW":

        if sector_allocation >= 30:

            score -= 25

        elif sector_allocation >= 20:

            score -= 10

    if action in {
        "REDUCE",
        "SELL",
    }:

        if concentration >= VERY_HIGH_CONCENTRATION:

            score += 25

        elif concentration >= HIGH_CONCENTRATION:

            score += 15

    return clamp(
        score
    )


def score_risk_fit(
    context,
):
    """
    Assess whether portfolio risk supports the proposed action.
    """

    action = get_action(
        context
    )

    risk = get_risk_score(
        context
    )

    if risk <= 0:

        return 50.0

    if action in {
        "BUY NEW",
        "BUY MORE",
    }:

        if risk >= 80:
            return 20.0

        if risk >= 60:
            return 40.0

        if risk >= 40:
            return 65.0

        return 80.0

    if action in {
        "REDUCE",
        "SELL",
    }:

        if risk >= 80:
            return 90.0

        if risk >= 60:
            return 75.0

        if risk >= 40:
            return 55.0

        return 40.0

    return 60.0


def score_learning_adjustment(
    context,
):
    """
    Assess the learning adjustment.

    This does not automatically change the investment score.
    """

    adjustment = get_learning_adjustment(
        context
    )

    if adjustment >= 10:
        return 85.0

    if adjustment >= 5:
        return 70.0

    if adjustment > 0:
        return 60.0

    if adjustment == 0:
        return 50.0

    if adjustment > -5:
        return 40.0

    if adjustment > -10:
        return 25.0

    return 10.0


# ============================================================
# Decision-specific evidence
# ============================================================

def calculate_buy_evidence(
    context,
):
    """Calculate evidence supporting BUY NEW / BUY MORE."""

    investment_quality = score_investment_quality(
        context
    )

    learning_evidence = score_learning_evidence(
        context
    )

    bucket_evidence = score_score_bucket_evidence(
        context
    )

    portfolio_fit = score_portfolio_fit(
        context
    )

    risk_fit = score_risk_fit(
        context
    )

    learning_adjustment = score_learning_adjustment(
        context
    )

    score = (
        investment_quality * 0.35
        +
        learning_evidence * 0.15
        +
        bucket_evidence * 0.10
        +
        portfolio_fit * 0.20
        +
        risk_fit * 0.10
        +
        learning_adjustment * 0.10
    )

    return clamp(
        score
    )


def calculate_hold_evidence(
    context,
):
    """Calculate evidence supporting HOLD."""

    buy_evidence = calculate_buy_evidence(
        context
    )

    action = get_action(
        context
    )

    existing = get_existing_holding(
        context
    )

    concentration = get_concentration(
        context
    )

    score = 100.0 - buy_evidence

    if existing:

        score += 10.0

    if (
        action == "BUY MORE"
        and
        concentration >= HIGH_CONCENTRATION
    ):

        score += 10.0

    return clamp(
        score
    )


def calculate_reduction_evidence(
    context,
):
    """Calculate evidence supporting REDUCE."""

    investment_score = get_investment_score(
        context
    )

    risk_fit = score_risk_fit(
        context
    )

    portfolio_fit = score_portfolio_fit(
        context
    )

    learning_evidence = score_learning_evidence(
        context
    )

    if investment_score < VERY_WEAK_SCORE:

        weakness = 100.0

    elif investment_score < WEAK_SCORE:

        weakness = 80.0

    elif investment_score < GOOD_SCORE:

        weakness = 50.0

    else:

        weakness = 20.0

    score = (
        weakness * 0.40
        +
        portfolio_fit * 0.25
        +
        risk_fit * 0.20
        +
        learning_evidence * 0.15
    )

    return clamp(
        score
    )


def calculate_sell_evidence(
    context,
):
    """Calculate evidence supporting SELL."""

    reduction_evidence = calculate_reduction_evidence(
        context
    )

    investment_score = get_investment_score(
        context
    )

    signal = get_signal(
        context
    )

    score = reduction_evidence

    if signal == "STRONG SELL":

        score += 15

    elif signal == "SELL":

        score += 8

    if investment_score < VERY_WEAK_SCORE:

        score += 10

    return clamp(
        score
    )


# ============================================================
# Overall evidence assessment
# ============================================================

def calculate_evidence_score(
    context,
):
    """
    Calculate the evidence score for the proposed action.
    """

    action = get_action(
        context
    )

    if action in {
        "BUY NEW",
        "BUY MORE",
    }:

        return calculate_buy_evidence(
            context
        )

    if action == "REDUCE":

        return calculate_reduction_evidence(
            context
        )

    if action == "SELL":

        return calculate_sell_evidence(
            context
        )

    return calculate_hold_evidence(
        context
    )


def determine_evidence_strength(
    evidence_score,
):
    """Convert numeric evidence into strength classification."""

    evidence_score = safe_float(
        evidence_score
    )

    if evidence_score >= 80:
        return "VERY STRONG"

    if evidence_score >= 65:
        return "STRONG"

    if evidence_score >= 50:
        return "MODERATE"

    if evidence_score >= 35:
        return "WEAK"

    return "VERY WEAK"


def determine_decision_support(
    context,
    evidence_score,
):
    """
    Determine whether the evidence supports the proposed action.

    This does not replace the final governed decision layer.
    """

    action = get_action(
        context
    )

    evidence_score = safe_float(
        evidence_score
    )

    if action in {
        "BUY NEW",
        "BUY MORE",
    }:

        if evidence_score >= STRONG_BUY_EVIDENCE_THRESHOLD:
            return "SUPPORTED"

        if evidence_score >= BUY_EVIDENCE_THRESHOLD:
            return "CONDITIONAL"

        return "NOT SUPPORTED"

    if action == "REDUCE":

        if evidence_score >= REDUCE_EVIDENCE_THRESHOLD:
            return "SUPPORTED"

        if evidence_score >= 50:
            return "CONDITIONAL"

        return "NOT SUPPORTED"

    if action == "SELL":

        if evidence_score >= SELL_EVIDENCE_THRESHOLD:
            return "SUPPORTED"

        if evidence_score >= 60:
            return "CONDITIONAL"

        return "NOT SUPPORTED"

    if evidence_score >= 50:
        return "SUPPORTED"

    return "CONDITIONAL"


# ============================================================
# NEW CONFIDENCE MODEL
# ============================================================

def _score_evidence_completeness(
    context,
):
    """
    Measure completeness of the evidence relevant to the proposed
    action.

    This is deliberately NOT treated as decision confidence by
    itself.

    Historical learning receives less influence for HOLD and
    justified REDUCE decisions because those decisions can be
    valid from current portfolio / analytical evidence alone.
    """

    action = get_action(
        context
    )

    components = []

    # --------------------------------------------------------
    # Core investment evidence
    # --------------------------------------------------------

    investment_score = get_investment_score(
        context
    )

    if investment_score > 0:

        components.append(
            25.0
        )

    # --------------------------------------------------------
    # Current signal
    # --------------------------------------------------------

    signal = get_signal(
        context
    )

    if signal:

        components.append(
            15.0
        )

    # --------------------------------------------------------
    # Portfolio context
    # --------------------------------------------------------

    allocation = get_allocation(
        context
    )

    sector_allocation = get_sector_allocation(
        context
    )

    if (
        allocation > 0
        or
        get_existing_holding(
            context
        )
    ):

        components.append(
            10.0
        )

    if (
        sector_allocation > 0
    ):

        components.append(
            5.0
        )

    # --------------------------------------------------------
    # Risk evidence
    # --------------------------------------------------------

    if get_risk_score(
        context
    ) > 0:

        components.append(
            15.0
        )

    # --------------------------------------------------------
    # Historical evidence.
    #
    # It is more important for BUY decisions than for HOLD.
    # --------------------------------------------------------

    observations = get_signal_observations(
        context
    )

    bucket_observations = (
        get_score_bucket_observations(
            context
        )
    )

    if observations >= MIN_RELIABILITY_OBSERVATIONS:

        components.append(
            15.0
        )

    elif observations > 0:

        components.append(
            8.0
        )

    elif action in {
        "BUY NEW",
        "BUY MORE",
    }:

        # Missing historical evidence matters more for a new
        # capital deployment decision.
        components.append(
            0.0
        )

    else:

        # Lack of historical evidence does not destroy confidence
        # in a HOLD or justified reduction.
        components.append(
            5.0
        )

    if bucket_observations >= MIN_RELIABILITY_OBSERVATIONS:

        components.append(
            10.0
        )

    elif bucket_observations > 0:

        components.append(
            5.0
        )

    elif action in {
        "HOLD",
        "REDUCE",
    }:

        components.append(
            5.0
        )

    completeness = sum(
        components
    )

    return clamp(
        completeness,
        0.0,
        100.0,
    )


def calculate_confidence(
    context,
    evidence_score=None,
    decision_support=None,
):
    """
    Calculate confidence in the proposed action.

    This is the key distinction from the previous implementation.

    Previous behaviour:
        Confidence primarily represented evidence completeness.

    New behaviour:
        Confidence represents how strongly the supplied evidence
        supports the proposed action, with evidence completeness
        acting as a secondary modifier.

    The model deliberately avoids making historical learning
    availability a prerequisite for confidence in HOLD or a
    strongly justified REDUCE.
    """

    if evidence_score is None:

        evidence_score = calculate_evidence_score(
            context
        )

    evidence_score = clamp(
        evidence_score
    )

    if decision_support is None:

        decision_support = determine_decision_support(
            context,
            evidence_score,
        )

    action = get_action(
        context
    )

    completeness = _score_evidence_completeness(
        context
    )

    # --------------------------------------------------------
    # Evidence score carries the largest weight.
    # --------------------------------------------------------

    confidence = (
        evidence_score * 0.70
        +
        completeness * 0.30
    )

    # --------------------------------------------------------
    # Decision-support adjustment.
    # --------------------------------------------------------

    if decision_support == "SUPPORTED":

        confidence += 5.0

    elif decision_support == "CONDITIONAL":

        confidence -= 5.0

    elif decision_support == "NOT SUPPORTED":

        confidence -= 15.0

    # --------------------------------------------------------
    # Action-specific safeguards.
    # --------------------------------------------------------

    if action in {
        "BUY NEW",
        "BUY MORE",
    }:

        observations = get_signal_observations(
            context
        )

        # Missing historical evidence should materially reduce
        # confidence for new capital deployment.
        if observations <= 0:

            confidence -= 10.0

    if action == "BUY MORE":

        concentration = get_concentration(
            context
        )

        if concentration >= HIGH_CONCENTRATION:

            confidence -= 10.0

    if action == "REDUCE":

        investment_score = get_investment_score(
            context
        )

        signal = get_signal(
            context
        )

        # Strong current bearish evidence should increase
        # confidence in risk reduction even without historical
        # learning evidence.
        if (
            investment_score <= 40
            or
            signal in {
                "SELL",
                "STRONG SELL",
            }
        ):

            confidence += 5.0

    if action == "SELL":

        signal = get_signal(
            context
        )

        if signal in {
            "SELL",
            "STRONG SELL",
        }:

            confidence += 5.0

        else:

            confidence -= 10.0

    # --------------------------------------------------------
    # Existing upstream confidence can be used as a secondary
    # reference, not as the primary score.
    # --------------------------------------------------------

    upstream_confidence = get_confidence(
        context
    )

    if upstream_confidence is not None:

        confidence = (
            confidence * 0.85
            +
            upstream_confidence * 0.15
        )

    return round(
        clamp(
            confidence
        ),
        2,
    )


# ============================================================
# Main scoring function
# ============================================================

def score_ai_decision(
    context,
):
    """
    Score the evidence surrounding a proposed AI portfolio decision.

    Returns evidence, confidence and decision-support information.

    This remains an evidence-assessment layer only.
    """

    if not isinstance(
        context,
        dict,
    ):

        return {
            "Evidence Score": 0.0,
            "Evidence Strength": "VERY WEAK",
            "Decision Support": "NOT SUPPORTED",
            "Confidence": 0.0,
            "Decision Confidence": 0.0,
            "Evidence Confidence": 0.0,
            "Data Quality": "INVALID",
            "Action": "HOLD",
            "Reason": "Invalid decision context",
            "Final Decision": None,
            "Decision Layer Status":
                "EVIDENCE ASSESSMENT ONLY",
        }

    action = get_action(
        context
    )

    investment_score = get_investment_score(
        context
    )

    learning_adjusted_score = (
        get_learning_adjusted_score(
            context
        )
    )

    evidence_score = calculate_evidence_score(
        context
    )

    evidence_strength = determine_evidence_strength(
        evidence_score
    )

    decision_support = determine_decision_support(
        context,
        evidence_score,
    )

    decision_confidence = calculate_confidence(
        context,
        evidence_score=evidence_score,
        decision_support=decision_support,
    )

    evidence_confidence = round(
        _score_evidence_completeness(
            context
        ),
        2,
    )

    # --------------------------------------------------------
    # Data quality
    #
    # This remains separate from decision confidence.
    # --------------------------------------------------------

    data_quality_items = []

    if investment_score > 0:

        data_quality_items.append(
            "Investment Score"
        )

    if get_signal_observations(
        context
    ) > 0:

        data_quality_items.append(
            "Historical Signal Evidence"
        )

    if get_score_bucket_observations(
        context
    ) > 0:

        data_quality_items.append(
            "Score Bucket Evidence"
        )

    if get_existing_holding(
        context
    ):

        data_quality_items.append(
            "Portfolio Holding"
        )

    if get_signal(
        context
    ):

        data_quality_items.append(
            "Current Signal"
        )

    if get_risk_score(
        context
    ) > 0:

        data_quality_items.append(
            "Risk Evidence"
        )

    if len(
        data_quality_items
    ) >= 5:

        data_quality = "HIGH"

    elif len(
        data_quality_items
    ) >= 3:

        data_quality = "MEDIUM"

    elif len(
        data_quality_items
    ) >= 1:

        data_quality = "LOW"

    else:

        data_quality = "INSUFFICIENT"

    return {

        "Action":
            action,

        "Asset Type":
            get_asset_type(
                context
            ),

        "Existing Holding":
            get_existing_holding(
                context
            ),

        "Investment Score":
            investment_score,

        "Learning Adjusted Score":
            learning_adjusted_score,

        "Learning Adjustment":
            get_learning_adjustment(
                context
            ),

        "Historical Signal Observations":
            get_signal_observations(
                context
            ),

        "Historical Signal Win Rate %":
            get_signal_win_rate(
                context
            ),

        "Historical Signal Average Return %":
            get_signal_average_return(
                context
            ),

        "Historical Signal Reliability":
            get_signal_reliability(
                context
            ),

        "Score Bucket Observations":
            get_score_bucket_observations(
                context
            ),

        "Score Bucket Win Rate %":
            get_score_bucket_win_rate(
                context
            ),

        "Score Bucket Average Return %":
            get_score_bucket_return(
                context
            ),

        "Portfolio Allocation %":
            get_allocation(
                context
            ),

        "Sector Allocation %":
            get_sector_allocation(
                context
            ),

        "Risk Score":
            get_risk_score(
                context
            ),

        "Investment Quality Evidence":
            round(
                score_investment_quality(
                    context
                ),
                2,
            ),

        "Historical Learning Evidence":
            round(
                score_learning_evidence(
                    context
                ),
                2,
            ),

        "Score Bucket Evidence":
            round(
                score_score_bucket_evidence(
                    context
                ),
                2,
            ),

        "Portfolio Fit Evidence":
            round(
                score_portfolio_fit(
                    context
                ),
                2,
            ),

        "Risk Fit Evidence":
            round(
                score_risk_fit(
                    context
                ),
                2,
            ),

        "Learning Adjustment Evidence":
            round(
                score_learning_adjustment(
                    context
                ),
                2,
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

        # ----------------------------------------------------
        # NEW SEMANTICS
        # ----------------------------------------------------

        "Confidence":
            decision_confidence,

        "Decision Confidence":
            decision_confidence,

        "Evidence Confidence":
            evidence_confidence,

        "Data Quality":
            data_quality,

        # ----------------------------------------------------
        # This layer never owns the final portfolio action.
        # ----------------------------------------------------

        "Final Decision":
            None,

        "Decision Layer Status":
            "EVIDENCE ASSESSMENT ONLY",
    }


# ============================================================
# Batch scoring
# ============================================================

def score_ai_decisions(
    contexts,
):
    """
    Score multiple decision contexts.
    """

    if contexts is None:

        return []

    if not isinstance(
        contexts,
        list,
    ):

        contexts = [
            contexts
        ]

    results = []

    for context in contexts:

        results.append(
            score_ai_decision(
                context
            )
        )

    return results


# ============================================================
# PUBLIC COMPATIBILITY API
# ============================================================

def calculate_ai_decision_score(
    context,
):
    """
    Public compatibility entry point.

    This is a wrapper around score_ai_decision().
    """

    return score_ai_decision(
        context
    )


# ============================================================
# Module test
# ============================================================

if __name__ == "__main__":

    print(
        "AI Decision Scoring"
    )

    print(
        "Module loaded successfully."
    )