
"""
etf_decisions.py

Purpose
-------
Provides the ETF-specific portfolio decision engine.

This module is deliberately separate from the stock decisioning
framework. It converts ETF analysis plus the ETF's existing
portfolio position into one authoritative portfolio decision.

ETF decisions supported:
    BUY
    BUY MORE
    HOLD
    REDUCE
    SELL

Design principles
-----------------
- ETFs do NOT use stock scoring or stock recommendation logic.
- HOLD is the default unless there is sufficient evidence to
  justify a portfolio change.
- Existing meaningful ETF positions are protected from unnecessary
  turnover.
- Large ETF positions require stronger evidence before adding
  capital.
- Weak existing ETF positions can be reduced.
- Very weak ETF positions can be sold.
- Reduction percentages use the established 25/50/75/100 framework.

This module is intended to become the single ETF decision source
for:

    - Capital Allocation
    - Final Decision

Those reporting areas should consume the decision produced here
rather than recreate ETF decision rules independently.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


# ============================================================
# POSITION THRESHOLDS
# ============================================================

SMALL_POSITION_PCT = 2.0
MEANINGFUL_POSITION_PCT = 10.0


# ============================================================
# ETF SCORE THRESHOLDS
# ============================================================

VERY_STRONG_SCORE = 85
STRONG_SCORE = 75
POSITIVE_SCORE = 60
NEUTRAL_SCORE = 50
WEAK_SCORE = 35


# ============================================================
# CONFIDENCE THRESHOLDS
# ============================================================

HIGH_CONFIDENCE_SCORE = 85
MEDIUM_CONFIDENCE_SCORE = 70


# ============================================================
# SAFE CONVERSION HELPERS
# ============================================================

def _safe_float(
    value: Any,
    default: float = 0.0
) -> float:
    """
    Safely convert a value to float.
    """

    try:

        if value is None:
            return default

        return float(value)

    except (TypeError, ValueError):

        return default


# ============================================================
# POSITION CLASSIFICATION
# ============================================================

def classify_etf_position(
    portfolio_weight: float
) -> str:
    """
    Classify the current ETF portfolio position.

    Returns
    -------
    str
        NONE
        SMALL
        MEANINGFUL
        LARGE
    """

    weight = _safe_float(
        portfolio_weight
    )

    if weight <= 0:
        return "NONE"

    if weight < SMALL_POSITION_PCT:
        return "SMALL"

    if weight <= MEANINGFUL_POSITION_PCT:
        return "MEANINGFUL"

    return "LARGE"


# ============================================================
# CONFIDENCE
# ============================================================

def calculate_etf_decision_confidence(
    score: float,
    decision: str
) -> str:
    """
    Determine confidence in the ETF decision.

    Confidence is intentionally simple at this stage.

    Future versions can incorporate:

        - historical ETF recommendation reliability
        - volatility
        - trend agreement
        - data quality
        - portfolio concentration
        - market regime
    """

    score = _safe_float(score)

    if decision == "HOLD":

        if (
            score >= STRONG_SCORE
            or score < WEAK_SCORE
        ):
            return "MEDIUM"

        return "HIGH"

    if score >= HIGH_CONFIDENCE_SCORE:
        return "HIGH"

    if score >= MEDIUM_CONFIDENCE_SCORE:
        return "MEDIUM"

    return "LOW"


# ============================================================
# REDUCTION PERCENTAGE
# ============================================================

def calculate_etf_reduction(
    score: float,
    portfolio_weight: float
) -> int:
    """
    Determine the percentage of an existing ETF position
    that should be reduced.

    Returns one of:

        25
        50
        75
        100

    The framework deliberately avoids arbitrary partial
    percentages so downstream capital allocation remains
    predictable.
    """

    score = _safe_float(score)
    weight = _safe_float(portfolio_weight)

    # --------------------------------------------------------
    # Very weak ETF
    # --------------------------------------------------------

    if score < WEAK_SCORE:

        if score < 25:
            return 100

        if weight > MEANINGFUL_POSITION_PCT:
            return 75

        return 50

    # --------------------------------------------------------
    # Weak ETF
    # --------------------------------------------------------

    if score < NEUTRAL_SCORE:

        if weight > MEANINGFUL_POSITION_PCT:
            return 50

        return 25

    return 0


# ============================================================
# DECISION REASON
# ============================================================

def build_etf_decision_reason(
    decision: str,
    score: float,
    portfolio_weight: float,
    etf_analysis: Dict[str, Any]
) -> str:
    """
    Generate a concise human-readable explanation for the
    ETF portfolio decision.
    """

    score = _safe_float(score)
    weight = _safe_float(portfolio_weight)

    signal = str(
        etf_analysis.get(
            "ETF Signal",
            ""
        )
    )

    if decision == "BUY":

        return (
            f"ETF is not currently held and has a strong "
            f"ETF score of {score:.0f}/100 "
            f"with signal {signal}."
        )

    if decision == "BUY MORE":

        return (
            f"ETF is a small existing holding "
            f"({weight:.1f}% of portfolio) and has strong "
            f"ETF evidence with a score of {score:.0f}/100."
        )

    if decision == "REDUCE":

        return (
            f"ETF score of {score:.0f}/100 indicates weakening "
            f"conditions for an existing {weight:.1f}% portfolio "
            f"position."
        )

    if decision == "SELL":

        return (
            f"ETF score of {score:.0f}/100 indicates sufficiently "
            f"weak conditions to exit the existing position."
        )

    return (
        f"ETF score of {score:.0f}/100 does not provide "
        f"sufficient evidence for a portfolio change. "
        f"HOLD remains the default."
    )


# ============================================================
# ETF DECISION ENGINE
# ============================================================

def decide_etf(
    etf_analysis: Optional[Dict[str, Any]],
    quantity: float = 0.0,
    market_value: float = 0.0,
    portfolio_weight: float = 0.0
) -> Dict[str, Any]:
    """
    Produce the authoritative ETF portfolio decision.

    Parameters
    ----------
    etf_analysis:
        Dictionary returned by analyse_etf().

    quantity:
        Current number of ETF units held.

    market_value:
        Current market value of the ETF position.

    portfolio_weight:
        Current ETF allocation as a percentage of the portfolio.

    Returns
    -------
    dict
        Structured ETF decision.

    Important
    ---------
    HOLD is the default outcome.

    The engine does not automatically BUY merely because an ETF
    has a positive score.
    """

    quantity = _safe_float(
        quantity
    )

    market_value = _safe_float(
        market_value
    )

    portfolio_weight = _safe_float(
        portfolio_weight
    )

    # ========================================================
    # HANDLE MISSING ETF ANALYSIS
    # ========================================================

    if not isinstance(
        etf_analysis,
        dict
    ):

        return {
            "ETF Decision": "HOLD",
            "ETF Decision Confidence": "LOW",
            "ETF Decision Reason":
                "ETF analysis unavailable; HOLD retained "
                "because there is insufficient evidence.",
            "ETF Reduction %": 0,
            "ETF Position":
                classify_etf_position(
                    portfolio_weight
                ),
            "ETF Score": 0,
            "ETF Signal": "UNKNOWN",
        }

    # ========================================================
    # READ ETF ANALYSIS
    # ========================================================

    score = _safe_float(
        etf_analysis.get(
            "ETF Score",
            0
        )
    )

    signal = str(
        etf_analysis.get(
            "ETF Signal",
            "UNKNOWN"
        )
    ).upper().strip()

    position = classify_etf_position(
        portfolio_weight
    )

    # ========================================================
    # OWNERSHIP
    # ========================================================

    owned = (
        quantity > 0
        or market_value > 0
        or portfolio_weight > 0
    )

    # ========================================================
    # DEFAULT
    # ========================================================

    decision = "HOLD"
    reduction = 0

    # ========================================================
    # NOT CURRENTLY OWNED
    # ========================================================

    if not owned:

        # Strong ETF opportunity
        if (
            score >= STRONG_SCORE
            and signal in {
                "BUY",
                "STRONG BUY"
            }
        ):

            decision = "BUY"

        else:

            decision = "HOLD"

    # ========================================================
    # SMALL EXISTING POSITION
    # ========================================================

    elif position == "SMALL":

        # Require very strong evidence before adding capital.
        if (
            score >= VERY_STRONG_SCORE
            and signal in {
                "BUY",
                "STRONG BUY"
            }
        ):

            decision = "BUY MORE"

        elif score < NEUTRAL_SCORE:

            decision = "REDUCE"

            reduction = calculate_etf_reduction(
                score,
                portfolio_weight
            )

        else:

            decision = "HOLD"

    # ========================================================
    # MEANINGFUL EXISTING POSITION
    # ========================================================

    elif position == "MEANINGFUL":

        # ----------------------------------------------------
        # Strong ETF:
        #
        # Protect the existing position rather than repeatedly
        # adding capital simply because the trend remains strong.
        # ----------------------------------------------------

        if score >= STRONG_SCORE:

            decision = "HOLD"

        # ----------------------------------------------------
        # Weak or very weak ETF:
        #
        # A meaningful existing position should be reduced
        # when the ETF enters the weak score range.
        # ----------------------------------------------------

        elif score < NEUTRAL_SCORE:

            decision = "REDUCE"

            reduction = calculate_etf_reduction(
                score,
                portfolio_weight
            )

        else:

            decision = "HOLD"

    # ========================================================
    # LARGE EXISTING POSITION
    # ========================================================

    else:

        # ----------------------------------------------------
        # Large ETF positions require stronger evidence before
        # adding capital.
        #
        # We deliberately do NOT BUY MORE into a >10% ETF
        # position at this stage.
        # ----------------------------------------------------

        if score < NEUTRAL_SCORE:

            decision = "REDUCE"

            reduction = calculate_etf_reduction(
                score,
                portfolio_weight
            )

        else:

            decision = "HOLD"

    # ========================================================
    # ESCALATE EXTREME WEAKNESS TO SELL
    # ========================================================

    if (
        owned
        and score < 25
    ):

        decision = "SELL"
        reduction = 100

    # ========================================================
    # CONFIDENCE
    # ========================================================

    confidence = calculate_etf_decision_confidence(
        score,
        decision
    )

    # ========================================================
    # REASON
    # ========================================================

    reason = build_etf_decision_reason(
        decision=decision,
        score=score,
        portfolio_weight=portfolio_weight,
        etf_analysis=etf_analysis
    )

    # ========================================================
    # RESULT
    # ========================================================

    return {

        "ETF Decision":
            decision,

        "ETF Decision Confidence":
            confidence,

        "ETF Decision Reason":
            reason,

        "ETF Reduction %":
            reduction,

        "ETF Position":
            position,

        "ETF Score":
            score,

        "ETF Signal":
            signal,

        "Current Price":
            etf_analysis.get(
                "Current Price"
            ),

        "MA50":
            etf_analysis.get(
                "MA50"
            ),

        "MA200":
            etf_analysis.get(
                "MA200"
            ),

        "6M Return %":
            etf_analysis.get(
                "6M Return %"
            ),

        "12M Return %":
            etf_analysis.get(
                "12M Return %"
            ),

        "ETF Reasons":
            etf_analysis.get(
                "ETF Reasons"
            ),

        "ETF Risks":
            etf_analysis.get(
                "ETF Risks"
            )
    }


# ============================================================
# CONVENIENCE ALIAS
# ============================================================

def analyse_etf_decision(
    etf_analysis: Optional[Dict[str, Any]],
    quantity: float = 0.0,
    market_value: float = 0.0,
    portfolio_weight: float = 0.0
) -> Dict[str, Any]:
    """
    Backwards-compatible wrapper around decide_etf().
    """

    return decide_etf(
        etf_analysis=etf_analysis,
        quantity=quantity,
        market_value=market_value,
        portfolio_weight=portfolio_weight
    )


# ============================================================
# COMPATIBILITY ALIAS
# ============================================================

def generate_etf_decision(
    etf_analysis: Optional[Dict[str, Any]],
    quantity: float = 0.0,
    market_value: float = 0.0,
    portfolio_weight: float = 0.0
) -> Dict[str, Any]:
    """
    Compatibility wrapper for test harnesses and downstream
    modules that use the generate_etf_decision() name.

    This does not create a second decision engine.
    It delegates directly to decide_etf().
    """

    return decide_etf(
        etf_analysis=etf_analysis,
        quantity=quantity,
        market_value=market_value,
        portfolio_weight=portfolio_weight
    )

