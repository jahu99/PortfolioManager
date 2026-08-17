# analysis/investment_score.py
"""
Calculates the overall Investment Score for a stock.

Architecture:

    Technical Score ─┐
    Quality Score ───┼──> Weighted Composite
    Growth Score ────┘
                          │
                          ▼
                   Investment Score
                          │
                          ▼
                     Signal Engine
                          │
                          ▼
                 Portfolio Decision


IMPORTANT ARCHITECTURE:

Investment Score is the OUTPUT of the scoring model.

It is NOT an input component and therefore must never have
its own strategic weighting.

The only strategic weights are:

    - technical_score
    - quality_score
    - growth_score

Weights are loaded from analysis.weight_controller.

The weight optimiser may change these weights over time
based on historical recommendation outcomes, subject to
governance constraints.


CURRENT DESIGN:

Investment Score is deliberately deterministic.

The calculation is:

    Investment Score =
        Technical Score × Technical Weight
      + Quality Score   × Quality Weight
      + Growth Score    × Growth Weight


FUTURE AI AUGMENTATION:

Future versions may introduce AI-derived assessments such as:

    - recommendation confidence
    - historical recommendation reliability
    - market regime assessment
    - company-specific risk assessment
    - qualitative catalysts and risks
    - valuation/context assessment

These should preferably be introduced in the downstream
Portfolio Decision Engine rather than allowing AI to
arbitrarily alter the core Investment Score.

This keeps the Investment Score:

    - explainable
    - reproducible
    - statistically calibratable
    - independent of portfolio context

The Portfolio Decision Engine can subsequently combine
Investment Score, Signal, AI assessment, portfolio exposure,
risk, concentration, sector allocation and available capital
to determine:

    BUY
    BUY MORE
    HOLD
    REDUCE
    SELL
"""


from analysis.weight_controller import get_weights


# =====================================================
# Helpers
# =====================================================

def safe_float(value):
    """
    Safely convert a value to float.

    Invalid or missing values return 0.0.
    """

    try:

        return float(value)

    except Exception:

        return 0.0


def clamp(
    value,
    minimum=0.0,
    maximum=100.0
):
    """
    Constrain a numeric value to a defined range.
    """

    return max(
        min(
            value,
            maximum
        ),
        minimum
    )


# =====================================================
# Investment Score Engine
# =====================================================

def calculate_investment_score(
    technical_score,
    quality_score,
    growth_score
):
    """
    Calculate the overall Investment Score.

    Parameters
    ----------
    technical_score : float
        Technical market strength, 0-100.

    quality_score : float
        Underlying business quality, 0-100.

    growth_score : float
        Growth characteristics, 0-100.

    Returns
    -------
    float
        Investment Score constrained to 0-100.


    Calculation
    -----------

        Investment Score =
            Technical × Technical Weight
          + Quality   × Quality Weight
          + Growth    × Growth Weight

    Investment Score is therefore a composite output.

    It has no independent weighting of its own.
    """

    # -------------------------------------------------
    # Normalise component inputs
    # -------------------------------------------------

    technical_score = clamp(
        safe_float(
            technical_score
        )
    )

    quality_score = clamp(
        safe_float(
            quality_score
        )
    )

    growth_score = clamp(
        safe_float(
            growth_score
        )
    )


    # -------------------------------------------------
    # Load current governed production weights
    # -------------------------------------------------
    #
    # The weight controller is responsible for ensuring
    # that the production weights are valid and governed.
    #
    # The optimiser may change these values over time.
    #

    weights = get_weights()


    technical_weight = safe_float(
        weights.get(
            "technical_score",
            50.0
        )
    )

    quality_weight = safe_float(
        weights.get(
            "quality_score",
            20.0
        )
    )

    growth_weight = safe_float(
        weights.get(
            "growth_score",
            30.0
        )
    )


    # -------------------------------------------------
    # Safety normalisation
    # -------------------------------------------------
    #
    # Normally the weight controller guarantees that
    # these weights total 100%.
    #
    # Normalising here protects the scoring engine from
    # a malformed configuration.
    #

    total_weight = (
        technical_weight
        +
        quality_weight
        +
        growth_weight
    )


    if total_weight <= 0:

        technical_weight = 50.0
        quality_weight = 20.0
        growth_weight = 30.0

        total_weight = 100.0


    technical_weight /= total_weight

    quality_weight /= total_weight

    growth_weight /= total_weight


    # -------------------------------------------------
    # Calculate base Investment Score
    # -------------------------------------------------
    #
    # This is intentionally the complete production
    # Investment Score calculation.
    #
    # Investment Score is NOT used as an input.
    #

    investment_score = (

        technical_score
        *
        technical_weight

        +

        quality_score
        *
        quality_weight

        +

        growth_score
        *
        growth_weight

    )


    # -------------------------------------------------
    # Final safety constraint
    # -------------------------------------------------

    investment_score = clamp(
        investment_score
    )


    return round(
        investment_score,
        1
    )


# =====================================================
# Future AI augmentation
# =====================================================
#
# DO NOT add AI adjustments directly into the calculation
# above without establishing explicit governance.
#
# Potential future inputs include:
#
#     - AI confidence
#     - recommendation reliability
#     - market regime
#     - qualitative company assessment
#     - company-specific risk
#     - catalysts
#     - valuation context
#
# The preferred architecture is for these factors to feed
# the Portfolio Decision Engine rather than silently changing
# the underlying Investment Score.
#
# Example future architecture:
#
#     Investment Score
#            +
#     Signal
#            +
#     AI Assessment
#            +
#     Portfolio Risk
#            +
#     Position Size
#            +
#     Sector Exposure
#            +
#     Available Capital
#            │
#            ▼
#     Portfolio Decision
#
#              BUY
#              BUY MORE
#              HOLD
#              REDUCE
#              SELL
#
# This keeps the core score stable while allowing the
# decision layer to become progressively more intelligent.