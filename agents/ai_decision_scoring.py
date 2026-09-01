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
    recommendation_intelligence.py
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
- 60-day historical learning is preferred when available.
- 10-day and 5-day learning provide fallback evidence.
- Learning-adjusted scores are supporting evidence only.
- Existing holdings receive additional protection.
- Concentration and portfolio risk can weaken BUY decisions.
- REDUCE / SELL require stronger evidence than HOLD.
- Missing evidence reduces confidence appropriately.
- Missing historical learning evidence is NOT negative evidence.
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

# Preferred recommendation-learning horizon.
#
# The learning engine may expose several horizons. The scoring
# layer prefers the longer 60-day evidence because it is more
# relevant to the project's long-term portfolio-management
# objective.
PREFERRED_LEARNING_HORIZON = "60D"

LEARNING_HORIZON_ORDER = (
    "60D",
    "10D",
    "5D",
)

LEARNING_HORIZON_MIN_OBSERVATIONS = {
    "60D": 30,
    "10D": 30,
    "5D": 30,
}


# ============================================================
# Generic helpers
# ============================================================

def safe_float(
    value,
    default=0.0,
):
    """Safely convert a value to float."""

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
    """Safely normalise a text value."""

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
    """Keep a score inside a defined range."""

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
    # Direct lookup.
    # --------------------------------------------------------

    for key in keys:

        if key in context:

            value = context.get(
                key
            )

            if value is not None:
                return value

    # --------------------------------------------------------
    # Structured context lookup.
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
        "learning",
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


def _get_horizon_mapping(
    context,
    horizon,
):
    """
    Retrieve a nested historical-learning mapping for a horizon.

    Public interface compatibility
    -------------------------------
    Consumers may supply horizons as either integers or strings:

        5
        "5"
        "5D"
        "5-day"
        "5_day"

        10
        "10"
        "10D"
        "10-day"
        "10_day"

        60
        "60"
        "60D"
        "60-day"
        "60_day"

    All supported representations are normalised to the canonical
    internal form:

        5  -> "5D"
        10 -> "10D"
        60 -> "60D"

    The normalisation is performed here so that all horizon-specific
    getters retain their existing public interface.
    """

    if not isinstance(
        context,
        dict,
    ):
        return {}

    # ------------------------------------------------------------
    # Normalise the horizon argument.
    # ------------------------------------------------------------

    horizon_text = str(
        horizon
    ).strip().upper()

    horizon_mapping = {
        "5": "5D",
        "5D": "5D",
        "5-DAY": "5D",
        "5_DAY": "5D",
        "5 DAYS": "5D",
        "5-DAYS": "5D",

        "10": "10D",
        "10D": "10D",
        "10-DAY": "10D",
        "10_DAY": "10D",
        "10 DAYS": "10D",
        "10-DAYS": "10D",

        "60": "60D",
        "60D": "60D",
        "60-DAY": "60D",
        "60_DAY": "60D",
        "60 DAYS": "60D",
        "60-DAYS": "60D",
    }

    canonical_horizon = horizon_mapping.get(
        horizon_text
    )

    if canonical_horizon is None:
        return {}

    # ------------------------------------------------------------
    # Supported nested naming conventions.
    # ------------------------------------------------------------

    aliases = {
        "60D": (
            "60D",
            "60d",
            "60-day",
            "60_day",
            "historical_60d",
            "historical_60_day",
            "historical_60-day",
            "learning_60d",
            "learning_60_day",
        ),

        "10D": (
            "10D",
            "10d",
            "10-day",
            "10_day",
            "historical_10d",
            "historical_10_day",
            "historical_10-day",
            "learning_10d",
            "learning_10_day",
        ),

        "5D": (
            "5D",
            "5d",
            "5-day",
            "5_day",
            "historical_5d",
            "historical_5_day",
            "historical_5-day",
            "learning_5d",
            "learning_5_day",
        ),
    }

    candidates = aliases.get(
        canonical_horizon,
        (),
    )

    # ------------------------------------------------------------
    # Search supported containers.
    # ------------------------------------------------------------

    containers = [
        context,

        context.get(
            "historical"
        ),

        context.get(
            "learning"
        ),

        context.get(
            "recommendation_intelligence"
        ),

        context.get(
            "recommendation_learning"
        ),
    ]

    # ------------------------------------------------------------
    # Find the first matching nested mapping.
    # ------------------------------------------------------------

    for container in containers:

        if not isinstance(
            container,
            dict,
        ):
            continue

        for candidate in candidates:

            value = container.get(
                candidate
            )

            if isinstance(
                value,
                dict,
            ):
                return value

    return {}

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
    Retrieve or derive the learning-adjusted investment score.

    Interface remains unchanged: accepts a single decision context.

    Priority
    --------
    1. Use an explicitly supplied upstream Learning Adjusted Score
       when available.
    2. Otherwise derive it from the raw Investment Score plus the
       Recommendation Intelligence learning adjustment.

    The raw Investment Score is never modified.

    The derived score is bounded to 0-100.
    """

    investment_score = get_investment_score(
        context
    )

    # ------------------------------------------------------------
    # 1. Preserve an explicitly supplied upstream value.
    #
    # This maintains compatibility with the Recommendation
    # Intelligence pipeline when it has already calculated the
    # learning-adjusted score.
    # ------------------------------------------------------------

    value = get_value(
        context,
        "Learning Adjusted Score",
        "learning_adjusted_score",
        default=None,
    )

    if value is not None:
        numeric_value = safe_float(
            value,
            default=None,
        )

        if numeric_value is not None:
            return clamp(
                numeric_value,
                0.0,
                100.0,
            )

    # ------------------------------------------------------------
    # 2. No upstream adjusted score was supplied.
    #
    # Derive it from:
    #
    #     Investment Score + Learning Adjustment
    #
    # Learning adjustment is supporting evidence only. The raw
    # Investment Score itself remains unchanged.
    # ------------------------------------------------------------

    learning_adjustment = get_learning_adjustment(
        context
    )

    return clamp(
        investment_score + learning_adjustment,
        0.0,
        100.0,
    )

def get_learning_adjustment(
    context,
):
    """
    Retrieve or derive the recommendation-learning adjustment.

    Public interface remains compatible with both integer and string
    horizon representations.

    Priority
    --------
    1. Preserve an explicitly supplied upstream Learning Adjustment.
    2. Otherwise derive the adjustment from the preferred mature
       historical-learning horizon.

    Historical learning is supporting evidence only.
    The raw Investment Score is never modified.

    Adjustment model
    ----------------
        average_return × 3.0 × evidence_confidence

    Evidence confidence:
        <20 observations  -> 0.00
        20 observations   -> 0.50
        100+ observations -> 1.00

    The result is bounded to +/-10.
    """

    # --------------------------------------------------------
    # 1. Preserve an explicitly supplied upstream adjustment.
    # --------------------------------------------------------

    existing = get_value(
        context,
        "Learning Adjustment",
        "learning_adjustment",
        default=None,
    )

    if existing is not None:

        numeric_existing = safe_float(
            existing,
            default=None,
        )

        if numeric_existing is not None:

            return clamp(
                numeric_existing,
                -10.0,
                10.0,
            )

    # --------------------------------------------------------
    # 2. Determine the preferred learning horizon.
    #
    # Prefer 60D, then 10D, then 5D when mature.
    # --------------------------------------------------------

    preferred_horizon = get_value(
        context,
        "Preferred Learning Horizon",
        "preferred_learning_horizon",
        "Historical Learning Horizon",
        "historical_learning_horizon",
        default=None,
    )

    horizon = None

    if preferred_horizon is not None:

        horizon_text = clean_text(
            preferred_horizon
        )

        if horizon_text in {
            "60",
            "60D",
            "60 DAY",
            "60 DAYS",
            "60-DAY",
            "60_DAY",
        }:

            horizon = 60

        elif horizon_text in {
            "10",
            "10D",
            "10 DAY",
            "10 DAYS",
            "10-DAY",
            "10_DAY",
        }:

            horizon = 10

        elif horizon_text in {
            "5",
            "5D",
            "5 DAY",
            "5 DAYS",
            "5-DAY",
            "5_DAY",
        }:

            horizon = 5

    # --------------------------------------------------------
    # 3. If no explicit horizon exists, select the highest
    #    mature available horizon.
    # --------------------------------------------------------

    if horizon is None:

        for candidate in (
            60,
            10,
            5,
        ):

            observations = get_horizon_observations(
                context,
                candidate,
            )

            reliability = clean_text(
                get_horizon_reliability(
                    context,
                    candidate,
                )
            )

            if (
                observations >= 20
                and
                reliability == "VALID"
            ):

                horizon = candidate
                break

    # --------------------------------------------------------
    # 4. No mature evidence = no adjustment.
    # --------------------------------------------------------

    if horizon is None:

        return 0.0

    observations = get_horizon_observations(
        context,
        horizon,
    )

    reliability = clean_text(
        get_horizon_reliability(
            context,
            horizon,
        )
    )

    average_return = get_horizon_average_return(
        context,
        horizon,
    )

    # --------------------------------------------------------
    # 5. Require mature evidence.
    # --------------------------------------------------------

    if observations < 20:
        return 0.0

    if reliability != "VALID":
        return 0.0

    # --------------------------------------------------------
    # 6. Calculate evidence confidence.
    #
    # 20 observations = 0.50
    # 100 observations = 1.00
    # --------------------------------------------------------

    evidence_confidence = min(
        1.0,
        max(
            0.0,
            (
                observations - 20.0
            ) / 80.0 * 0.5
            + 0.5,
        ),
    )

    # --------------------------------------------------------
    # 7. Calculate learning adjustment.
    # --------------------------------------------------------

    adjustment = (
        average_return
        * 3.0
        * evidence_confidence
    )

    return clamp(
        adjustment,
        -10.0,
        10.0,
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


# ============================================================
# Generic historical signal access
# ============================================================

def get_signal_reliability(
    context,
):
    """
    Retrieve historical signal reliability.

    This remains the generic/fallback historical reliability field.
    """

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
            "Win Rate %",
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
            "Average Return %",
            default=0,
        )
    )

def _normalise_horizon(horizon):
    """
    Normalise supported learning-horizon inputs.

    Public consumers may supply either:
        5
        10
        60

    or:
        "5"
        "5D"
        "5 DAY"
        "5 DAYS"
        "10"
        "10D"
        "10 DAY"
        "10 DAYS"
        "60"
        "60D"
        "60 DAY"
        "60 DAYS"

    The canonical internal representation is:
        "5D"
        "10D"
        "60D"

    This preserves the existing consumer interface while ensuring all
    horizon accessors use identical matching behaviour.
    """

    if horizon is None:
        return None

    # Numeric input.
    try:
        numeric = float(horizon)

        if numeric == 5:
            return "5D"

        if numeric == 10:
            return "10D"

        if numeric == 60:
            return "60D"

    except (TypeError, ValueError):
        pass

    text = clean_text(
        horizon
    )

    mapping = {
        "5": "5D",
        "5D": "5D",
        "5 DAY": "5D",
        "5 DAYS": "5D",

        "10": "10D",
        "10D": "10D",
        "10 DAY": "10D",
        "10 DAYS": "10D",

        "60": "60D",
        "60D": "60D",
        "60 DAY": "60D",
        "60 DAYS": "60D",
    }

    return mapping.get(
        text
    )


# ============================================================
# Horizon-specific historical learning
# ============================================================

def get_horizon_observations(
    context,
    horizon,
):
    """Retrieve historical observations for a specific horizon."""

    nested = _get_horizon_mapping(
        context,
        horizon,
    )

    value = get_value(
        nested,
        "Observations",
        "Historical Signal Observations",
        "Signal Observations",
        "observations",
        "sample_size",
        "count",
        default=None,
    )

    if value is not None:
        return safe_float(
            value
        )

    # Flat aliases.
    aliases = {
        "60D": (
            "Historical 60-Day Signal Observations",
            "Historical 60D Signal Observations",
            "Signal 60-Day Observations",
            "signal_60d_observations",
            "historical_60d_observations",
            "historical_60_day_observations",
        ),
        "10D": (
            "Historical 10-Day Signal Observations",
            "Historical 10D Signal Observations",
            "Signal 10-Day Observations",
            "signal_10d_observations",
            "historical_10d_observations",
            "historical_10_day_observations",
        ),
        "5D": (
            "Historical 5-Day Signal Observations",
            "Historical 5D Signal Observations",
            "Signal 5-Day Observations",
            "signal_5d_observations",
            "historical_5d_observations",
            "historical_5_day_observations",
        ),
    }

    return safe_float(
        get_value(
            context,
            *aliases.get(
                horizon,
                (),
            ),
            default=0,
        )
    )


def get_horizon_win_rate(
    context,
    horizon,
):
    """Retrieve historical win rate for a specific horizon."""

    nested = _get_horizon_mapping(
        context,
        horizon,
    )

    value = get_value(
        nested,
        "Win Rate %",
        "Win Rate",
        "Historical Signal Win Rate %",
        "historical_signal_win_rate",
        "win_rate",
        default=None,
    )

    if value is not None:
        return safe_float(
            value
        )

    aliases = {
        "60D": (
            "Historical 60-Day Signal Win Rate %",
            "Historical 60D Signal Win Rate %",
            "Signal 60-Day Win Rate %",
            "signal_60d_win_rate",
            "historical_60d_win_rate",
            "historical_60_day_win_rate",
        ),
        "10D": (
            "Historical 10-Day Signal Win Rate %",
            "Historical 10D Signal Win Rate %",
            "Signal 10-Day Win Rate %",
            "signal_10d_win_rate",
            "historical_10d_win_rate",
            "historical_10_day_win_rate",
        ),
        "5D": (
            "Historical 5-Day Signal Win Rate %",
            "Historical 5D Signal Win Rate %",
            "Signal 5-Day Win Rate %",
            "signal_5d_win_rate",
            "historical_5d_win_rate",
            "historical_5_day_win_rate",
        ),
    }

    return safe_float(
        get_value(
            context,
            *aliases.get(
                horizon,
                (),
            ),
            default=0,
        )
    )


def get_horizon_average_return(
    context,
    horizon,
):
    """Retrieve historical average return for a specific horizon."""

    nested = _get_horizon_mapping(
        context,
        horizon,
    )

    value = get_value(
        nested,
        "Average Return %",
        "Average Return",
        "Historical Signal Average Return %",
        "historical_signal_average_return",
        "average_return",
        "return",
        default=None,
    )

    if value is not None:
        return safe_float(
            value
        )

    aliases = {
        "60D": (
            "Historical 60-Day Signal Average Return %",
            "Historical 60D Signal Average Return %",
            "Signal 60-Day Average Return %",
            "signal_60d_average_return",
            "historical_60d_average_return",
            "historical_60_day_average_return",
        ),
        "10D": (
            "Historical 10-Day Signal Average Return %",
            "Historical 10D Signal Average Return %",
            "Signal 10-Day Average Return %",
            "signal_10d_average_return",
            "historical_10d_average_return",
            "historical_10_day_average_return",
        ),
        "5D": (
            "Historical 5-Day Signal Average Return %",
            "Historical 5D Signal Average Return %",
            "Signal 5-Day Average Return %",
            "signal_5d_average_return",
            "historical_5d_average_return",
            "historical_5_day_average_return",
        ),
    }

    return safe_float(
        get_value(
            context,
            *aliases.get(
                horizon,
                (),
            ),
            default=0,
        )
    )


def get_horizon_reliability(
    context,
    horizon,
):
    """
    Retrieve historical reliability for a specific learning horizon.

    Interface compatibility
    -----------------------
    Accepts either integer or string horizons:

        5
        "5"
        "5D"
        "5-day"
        "5_day"

        10
        "10"
        "10D"
        "10-day"
        "10_day"

        60
        "60"
        "60D"
        "60-day"
        "60_day"

    The horizon is normalised by _get_horizon_mapping(), so callers using
    either the legacy integer interface or the newer D-suffixed interface
    receive the same result.
    """

    # ------------------------------------------------------------
    # Retrieve the nested horizon mapping.
    # ------------------------------------------------------------

    nested = _get_horizon_mapping(
        context,
        horizon,
    )

    # ------------------------------------------------------------
    # Read reliability from the nested learning record.
    # ------------------------------------------------------------

    value = get_value(
        nested,
        "Reliability",
        "Signal Reliability",
        "Historical Signal Reliability",
        "historical_signal_reliability",
        "historical_reliability",
        "reliability",
        default=None,
    )

    if value is not None:
        text = clean_text(
            value
        )

        if text:
            return text

    # ------------------------------------------------------------
    # Normalise the requested horizon.
    #
    # This preserves the public integer/string interface even when
    # the supplied context uses flat fields rather than nested data.
    # ------------------------------------------------------------

    horizon_text = str(
        horizon
    ).strip().upper()

    horizon_mapping = {
        "5": "5D",
        "5D": "5D",
        "5-DAY": "5D",
        "5_DAY": "5D",

        "10": "10D",
        "10D": "10D",
        "10-DAY": "10D",
        "10_DAY": "10D",

        "60": "60D",
        "60D": "60D",
        "60-DAY": "60D",
        "60_DAY": "60D",
    }

    canonical_horizon = horizon_mapping.get(
        horizon_text
    )

    # ------------------------------------------------------------
    # Flat-field aliases.
    # ------------------------------------------------------------

    aliases = {
        "60D": (
            "Historical 60-Day Signal Reliability",
            "Historical 60D Signal Reliability",
            "Signal 60-Day Reliability",
            "historical_60d_reliability",
            "historical_60_day_reliability",
            "signal_60d_reliability",
            "signal_60_day_reliability",
        ),

        "10D": (
            "Historical 10-Day Signal Reliability",
            "Historical 10D Signal Reliability",
            "Signal 10-Day Reliability",
            "historical_10d_reliability",
            "historical_10_day_reliability",
            "signal_10d_reliability",
            "signal_10_day_reliability",
        ),

        "5D": (
            "Historical 5-Day Signal Reliability",
            "Historical 5D Signal Reliability",
            "Signal 5-Day Reliability",
            "historical_5d_reliability",
            "historical_5_day_reliability",
            "signal_5d_reliability",
            "signal_5_day_reliability",
        ),
    }

    if canonical_horizon is not None:

        value = get_value(
            context,
            *aliases.get(
                canonical_horizon,
                (),
            ),
            default=None,
        )

        if value is not None:
            text = clean_text(
                value
            )

            if text:
                return text

    # ------------------------------------------------------------
    # Final fallback.
    #
    # Do not fabricate reliability. An empty value means that the
    # upstream learning layer did not provide one.
    # ------------------------------------------------------------

    return ""

def get_preferred_learning_horizon(
    context,
):
    """
    Select the preferred available historical learning horizon.

    Preference:
        60D -> 10D -> 5D

    A horizon is considered usable when it has at least one
    observation. Mature evidence is preferred automatically when
    available.

    This prevents the scoring layer from inventing negative
    evidence merely because a preferred horizon is unavailable.
    """

    for horizon in LEARNING_HORIZON_ORDER:

        observations = get_horizon_observations(
            context,
            horizon,
        )

        if observations > 0:

            return horizon

    # --------------------------------------------------------
    # If horizon-specific fields are absent, use the legacy
    # generic historical signal fields.
    # --------------------------------------------------------

    if get_signal_observations(
        context
    ) > 0:

        return "LEGACY"

    return "NONE"


def get_preferred_learning_observations(
    context,
):
    """Retrieve observations from the selected learning horizon."""

    horizon = get_preferred_learning_horizon(
        context
    )

    if horizon == "LEGACY":

        return get_signal_observations(
            context
        )

    if horizon == "NONE":

        return 0.0

    return get_horizon_observations(
        context,
        horizon,
    )


def get_preferred_learning_win_rate(
    context,
):
    """Retrieve win rate from the selected learning horizon."""

    horizon = get_preferred_learning_horizon(
        context
    )

    if horizon == "LEGACY":

        return get_signal_win_rate(
            context
        )

    if horizon == "NONE":

        return 0.0

    return get_horizon_win_rate(
        context,
        horizon,
    )


def get_preferred_learning_average_return(
    context,
):
    """Retrieve average return from the selected learning horizon."""

    horizon = get_preferred_learning_horizon(
        context
    )

    if horizon == "LEGACY":

        return get_signal_average_return(
            context
        )

    if horizon == "NONE":

        return 0.0

    return get_horizon_average_return(
        context,
        horizon,
    )


def get_preferred_learning_reliability(
    context,
):
    """Retrieve reliability from the selected learning horizon."""

    horizon = get_preferred_learning_horizon(
        context
    )

    if horizon == "LEGACY":

        return get_signal_reliability(
            context
        )

    if horizon == "NONE":

        return ""

    return get_horizon_reliability(
        context,
        horizon,
    )


# ============================================================
# Score bucket evidence
# ============================================================

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


# ============================================================
# Portfolio / decision context
# ============================================================

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
    """Retrieve portfolio concentration."""

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
    """Convert the existing investment score into evidence strength."""

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

    Learning evidence is selected using the preferred historical
    horizon supplied by the AI Decision Context.

    Preference order
    ----------------
    1. Mature 60-day evidence
    2. Mature 10-day evidence
    3. Mature 5-day evidence
    4. Largest available immature sample

    Historical learning is supporting evidence only. It does not
    replace the underlying Investment Score.

    Important
    ---------
    Missing or immature historical evidence is NOT treated as
    negative evidence.

    Therefore:

        0 observations
        or
        INSUFFICIENT DATA
        or
        IMMATURE

    produces neutral learning evidence rather than a penalty.

    Public interface
    ----------------
    The function signature is deliberately unchanged because it is
    consumed by calculate_buy_evidence(), calculate_reduction_evidence()
    and the wider AI decision-scoring chain.
    """

    # --------------------------------------------------------
    # Preferred learning horizon
    # --------------------------------------------------------

    preferred_horizon = clean_text(
        get_preferred_learning_horizon(
            context
        )
    )

    preferred_observations = (
        get_preferred_learning_observations(
            context
        )
    )

    preferred_win_rate = (
        get_preferred_learning_win_rate(
            context
        )
    )

    preferred_average_return = (
        get_preferred_learning_average_return(
            context
        )
    )

    preferred_reliability = (
        get_preferred_learning_reliability(
            context
        )
    )

    # --------------------------------------------------------
    # If the context already identified a preferred horizon,
    # use it.
    # --------------------------------------------------------

    observations = preferred_observations
    win_rate = preferred_win_rate
    average_return = preferred_average_return
    reliability = preferred_reliability

    # --------------------------------------------------------
    # Defensive fallback.
    #
    # This protects compatibility with older contexts that do
    # not yet contain preferred-learning fields.
    # --------------------------------------------------------

    if observations <= 0:

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
    # No historical evidence.
    #
    # IMPORTANT:
    # Missing learning is neutral, not negative.
    # --------------------------------------------------------

    if observations <= 0:

        return 50.0

    # --------------------------------------------------------
    # Sample-size assessment.
    #
    # 0-29:
    #     immature
    #
    # 30-99:
    #     valid
    #
    # 100+:
    #     strong
    # --------------------------------------------------------

    if (
        observations
        >=
        STRONG_RELIABILITY_OBSERVATIONS
    ):

        sample_score = 100.0
        immature_history = False

    elif (
        observations
        >=
        MIN_RELIABILITY_OBSERVATIONS
    ):

        sample_score = 70.0
        immature_history = False

    else:

        sample_score = 50.0
        immature_history = True

    # --------------------------------------------------------
    # Reliability classification.
    #
    # Explicit immature / insufficient classifications always
    # remain neutral regardless of the observed return.
    # --------------------------------------------------------

    reliability = clean_text(
        reliability,
        default="",
    )

    if reliability in {
        "INSUFFICIENT DATA",
        "NO DATA",
        "IMMATURE",
        "INSUFFICIENT",
    }:

        immature_history = True

    # --------------------------------------------------------
    # Win-rate evidence.
    #
    # Immature samples do not receive positive or negative
    # interpretation from their observed win rate.
    # --------------------------------------------------------

    if immature_history:

        win_score = 50.0

    elif win_rate >= 60.0:

        win_score = 100.0

    elif win_rate >= 55.0:

        win_score = 80.0

    elif win_rate >= 50.0:

        win_score = 60.0

    elif win_rate > 0.0:

        win_score = 35.0

    else:

        win_score = 50.0

    # --------------------------------------------------------
    # Average-return evidence.
    #
    # Again, immature samples are neutral.
    # --------------------------------------------------------

    if immature_history:

        return_score = 50.0

    elif average_return >= 5.0:

        return_score = 100.0

    elif average_return > 0.0:

        return_score = 70.0

    elif average_return == 0.0:

        return_score = 50.0

    else:

        return_score = 20.0

    # --------------------------------------------------------
    # Reliability contribution.
    #
    # Valid mature evidence receives a modest bonus.
    # Insufficient/immature evidence receives NO penalty.
    # --------------------------------------------------------

    reliability_bonus = 0.0

    if reliability == "VALID":

        reliability_bonus = 5.0

    elif reliability in {
        "STRONG",
        "RELIABLE",
        "HIGH",
    }:

        reliability_bonus = 10.0

    elif reliability in {
        "INSUFFICIENT DATA",
        "NO DATA",
        "IMMATURE",
        "INSUFFICIENT",
        "",
    }:

        reliability_bonus = 0.0

    # --------------------------------------------------------
    # Final learning evidence.
    #
    # This remains deliberately bounded.
    #
    # Learning contributes evidence; it does not become the
    # investment score.
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

    if observations < MIN_RELIABILITY_OBSERVATIONS:

        win_score = 50.0

        return_score = 50.0

    else:

        if win_rate >= 60:

            win_score = 100.0

        elif win_rate >= 55:

            win_score = 80.0

        elif win_rate >= 50:

            win_score = 60.0

        elif win_rate > 0:

            win_score = 35.0

        else:

            win_score = 0.0

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
    """Assess whether the proposed action fits the portfolio."""

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
    """Assess whether portfolio risk supports the proposed action."""

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
    """Calculate the evidence score for the proposed action."""

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
    """Determine whether the evidence supports the proposed action."""

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
# Evidence completeness
# ============================================================

def _score_evidence_completeness(
    context,
):
    """
    Measure completeness of the evidence relevant to the proposed
    action.

    Historical learning is more important for BUY decisions than
    for HOLD or REDUCE.

    The selected learning horizon is explicitly exposed through
    the scoring result.
    """

    action = get_action(
        context
    )

    components = []

    # --------------------------------------------------------
    # Core investment evidence.
    # --------------------------------------------------------

    if get_investment_score(
        context
    ) > 0:

        components.append(
            25.0
        )

    # --------------------------------------------------------
    # Current signal.
    # --------------------------------------------------------

    if get_signal(
        context
    ):

        components.append(
            15.0
        )

    # --------------------------------------------------------
    # Portfolio context.
    # --------------------------------------------------------

    if (
        get_allocation(
            context
        ) > 0
        or
        get_existing_holding(
            context
        )
    ):

        components.append(
            10.0
        )

    if get_sector_allocation(
        context
    ) > 0:

        components.append(
            5.0
        )

    # --------------------------------------------------------
    # Risk evidence.
    # --------------------------------------------------------

    if get_risk_score(
        context
    ) > 0:

        components.append(
            15.0
        )

    # --------------------------------------------------------
    # Historical learning.
    #
    # Mature 60D evidence receives the strongest completeness
    # contribution.
    # --------------------------------------------------------

    horizon = get_preferred_learning_horizon(
        context
    )

    observations = get_preferred_learning_observations(
        context
    )

    if horizon == "60D":

        if observations >= STRONG_RELIABILITY_OBSERVATIONS:

            components.append(
                20.0
            )

        elif observations >= MIN_RELIABILITY_OBSERVATIONS:

            components.append(
                15.0
            )

        elif observations > 0:

            components.append(
                8.0
            )

    elif horizon in {
        "10D",
        "5D",
    }:

        if observations >= MIN_RELIABILITY_OBSERVATIONS:

            components.append(
                12.0
            )

        elif observations > 0:

            components.append(
                8.0
            )

    elif horizon == "LEGACY":

        if observations >= MIN_RELIABILITY_OBSERVATIONS:

            components.append(
                12.0
            )

        elif observations > 0:

            components.append(
                8.0
            )

    elif action in {
        "HOLD",
        "REDUCE",
    }:

        # Missing historical evidence does not destroy confidence
        # in HOLD or a justified reduction.
        components.append(
            5.0
        )

    # --------------------------------------------------------
    # Score-bucket evidence.
    # --------------------------------------------------------

    bucket_observations = (
        get_score_bucket_observations(
            context
        )
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

    return clamp(
        sum(
            components
        ),
        0.0,
        100.0,
    )


# ============================================================
# Confidence model
# ============================================================

def calculate_confidence(
    context,
    evidence_score=None,
    decision_support=None,
):
    """
    Calculate confidence in the proposed action.

    Evidence score carries the largest weight.

    Historical learning contributes through both the evidence
    score and completeness, but missing learning does not become
    negative evidence.
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
    # BUY safeguards.
    # --------------------------------------------------------

    if action in {
        "BUY NEW",
        "BUY MORE",
    }:

        observations = get_preferred_learning_observations(
            context
        )

        if observations <= 0:

            confidence -= 10.0

    # --------------------------------------------------------
    # BUY MORE concentration safeguard.
    # --------------------------------------------------------

    if action == "BUY MORE":

        concentration = get_concentration(
            context
        )

        if concentration >= HIGH_CONCENTRATION:

            confidence -= 10.0

    # --------------------------------------------------------
    # REDUCE safeguard.
    # --------------------------------------------------------

    if action == "REDUCE":

        investment_score = get_investment_score(
            context
        )

        signal = get_signal(
            context
        )

        if (
            investment_score <= 40
            or
            signal in {
                "SELL",
                "STRONG SELL",
            }
        ):

            confidence += 5.0

    # --------------------------------------------------------
    # SELL safeguard.
    # --------------------------------------------------------

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
    # Existing upstream confidence is secondary.
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

    learning_horizon = (
        get_preferred_learning_horizon(
            context
        )
    )

    learning_observations = (
        get_preferred_learning_observations(
            context
        )
    )

    learning_win_rate = (
        get_preferred_learning_win_rate(
            context
        )
    )

    learning_average_return = (
        get_preferred_learning_average_return(
            context
        )
    )

    learning_reliability = (
        get_preferred_learning_reliability(
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
    # Data quality.
    # --------------------------------------------------------

    data_quality_items = []

    if investment_score > 0:

        data_quality_items.append(
            "Investment Score"
        )

    if learning_observations > 0:

        data_quality_items.append(
            "Historical Learning Evidence"
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

        "Signal":
            get_signal(
                context
            ),

        "Learning Adjusted Score":
            learning_adjusted_score,

        "Learning Adjustment":
            get_learning_adjustment(
                context
            ),

        # ----------------------------------------------------
        # Preferred historical learning evidence.
        # ----------------------------------------------------

        "Historical Learning Horizon":
            learning_horizon,

        "Historical Signal Observations":
            learning_observations,

        "Historical Signal Win Rate %":
            learning_win_rate,

        "Historical Signal Average Return %":
            learning_average_return,

        "Historical Signal Reliability":get_signal_reliability(context),


        # ----------------------------------------------------
        # Explicit horizon fields.
        #
        # These make the selected learning evidence visible to
        # downstream explanation/reviewer layers.
        # ----------------------------------------------------

        "Historical 60-Day Observations":
            get_horizon_observations(
                context,
                "60D",
            ),

        "Historical 60-Day Win Rate %":
            get_horizon_win_rate(
                context,
                "60D",
            ),

        "Historical 60-Day Average Return %":
            get_horizon_average_return(
                context,
                "60D",
            ),

        "Historical 60-Day Reliability":
            get_horizon_reliability(
                context,
                60,
            ),

        "Historical 10-Day Observations":
            get_horizon_observations(
                context,
                "10D",
            ),

        "Historical 10-Day Win Rate %":
            get_horizon_win_rate(
                context,
                "10D",
            ),

        "Historical 10-Day Average Return %":
            get_horizon_average_return(
                context,
                "10D",
            ),

        "Historical 10-Day Reliability":
            get_horizon_reliability(
                context,
                10,
            ),


        "Historical 5-Day Observations":
            get_horizon_observations(
                context,
                "5D",
            ),

        "Historical 5-Day Win Rate %":
            get_horizon_win_rate(
                context,
                "5D",
            ),

        "Historical 5-Day Average Return %":
            get_horizon_average_return(
                context,
                "5D",
            ),

        "Historical 5-Day Reliability":
            get_horizon_reliability(
                context,
                5,
            ),

        # ----------------------------------------------------
        # Score-bucket evidence.
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # Portfolio evidence.
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # Component evidence scores.
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # Final evidence assessment.
        # ----------------------------------------------------

        "Evidence Score":
            round(
                evidence_score,
                2,
            ),

        "Evidence Strength":
            evidence_strength,

        "Decision Support":
            decision_support,

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
    """Score multiple decision contexts."""

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
# Public compatibility API
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