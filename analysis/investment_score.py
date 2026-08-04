from analysis.weight_controller import get_weights
from analysis.adaptive_learning import get_adaptive_adjustments


# =====================================================
# Helpers
# =====================================================

def safe_float(value):

    try:

        return float(value)

    except Exception:

        return 0.0



def clamp(
    value,
    minimum=0,
    maximum=100
):

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

    growth_score,

    confidence_score=0,

    signal="",

    score_bucket="",

    sector=""

):

    """
    Calculates final investment conviction score.

    Inputs:

    technical_score
        Technical market strength

    quality_score
        Business quality

    growth_score
        Growth characteristics

    confidence_score
        AI confidence 0-100

    signal
        BUY / WATCH / SELL

    score_bucket
        Low / Medium / Good / High

    sector
        Sector classification


    Returns:

    Final Investment Score 0-100

    """



    # -------------------------------------------------
    # Normalise inputs
    # -------------------------------------------------

    technical_score = safe_float(
        technical_score
    )


    quality_score = safe_float(
        quality_score
    )


    growth_score = safe_float(
        growth_score
    )


    confidence_score = safe_float(
        confidence_score
    )



    # -------------------------------------------------
    # Load adaptive weights
    # -------------------------------------------------

    weights = get_weights()



    technical_weight = weights.get(

        "technical_score",

        50

    )


    quality_weight = weights.get(

        "quality_score",

        30

    )


    growth_weight = weights.get(

        "growth_score",

        20

    )



    # -------------------------------------------------
    # Base investment score
    # -------------------------------------------------

    score = (

        technical_score
        *
        technical_weight
        /
        100


        +

        quality_score
        *
        quality_weight
        /
        100


        +

        growth_score
        *
        growth_weight
        /
        100

    )



    # -------------------------------------------------
    # Confidence adjustment
    # -------------------------------------------------

    if confidence_score > 0:


        confidence_multiplier = (

            0.85

            +

            (
                confidence_score
                /
                100
                *
                0.15
            )

        )


        score *= confidence_multiplier



    # -------------------------------------------------
    # Adaptive learning adjustment
    # -------------------------------------------------

    try:


        adjustments = get_adaptive_adjustments()



        learning_adjustment = adjustments.get(

            (

                signal,

                score_bucket,

                sector

            ),

            0

        )


        score += learning_adjustment



    except Exception as e:


        print(

            "Adaptive learning adjustment skipped:",

            e

        )



    # -------------------------------------------------
    # Final score
    # -------------------------------------------------

    score = clamp(

        score

    )


    return round(

        score,

        1

    )



# =====================================================
# Diagnostic Test
# =====================================================

def test_investment_score():


    score = calculate_investment_score(

        technical_score=85,

        quality_score=70,

        growth_score=80,

        confidence_score=90,

        signal="BUY",

        score_bucket="High",

        sector="Technology"

    )


    print(

        "Investment Score:",

        score

    )


    print(

        "Weights:",

        get_weights()

    )



if __name__ == "__main__":

    test_investment_score()