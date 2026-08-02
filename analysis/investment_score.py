from analysis.weight_controller import get_weights


# =====================================================
# Investment Score Engine
# =====================================================


def calculate_investment_score(
    technical_score,
    quality_score,
    growth_score,
    confidence_score=0
):
    """
    Calculates adaptive investment score.

    Uses weights produced by
    weight_optimizer.py

    Falls back to defaults through
    weight_controller.py
    """


    weights = get_weights()


    investment_weight = weights.get(
        "investment_score",
        0
    )


    technical_weight = weights.get(
        "technical_score",
        50
    )


    quality_weight = weights.get(
        "quality_score",
        20
    )


    growth_weight = weights.get(
        "growth_score",
        10
    )



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



    # Confidence adjustment
    # avoids low confidence scores dominating

    if confidence_score:

        score = (

            score
            *
            (
                0.8
                +
                (
                    confidence_score
                    /
                    500
                )
            )

        )



    return round(
        max(
            min(
                score,
                100
            ),
            0
        ),
        1
    )



# =====================================================
# Diagnostic Test
# =====================================================


def test_investment_score():

    score = calculate_investment_score(

        technical_score=80,

        quality_score=70,

        growth_score=60,

        confidence_score=75

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