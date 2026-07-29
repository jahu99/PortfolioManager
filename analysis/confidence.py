def calculate_confidence(
    investment_score,
    technical_score,
    quality_score,
    growth_score,
    risks=None,
    signal_performance=None,
    score_bucket_performance=None
):

    confidence = 50
    reasons = []

    risks = risks or []


    # --------------------------------
    # Investment score strength
    # --------------------------------

    if investment_score >= 80:

        confidence += 15

        reasons.append(
            "High investment score"
        )

    elif investment_score >= 70:

        confidence += 8

        reasons.append(
            "Good investment score"
        )



    # --------------------------------
    # Technical strength
    # --------------------------------

    if technical_score >= 80:

        confidence += 10

        reasons.append(
            "Strong technical setup"
        )

    elif technical_score >= 70:

        confidence += 5



    # --------------------------------
    # Quality strength
    # --------------------------------

    if quality_score >= 80:

        confidence += 10

        reasons.append(
            "High quality company"
        )

    elif quality_score >= 65:

        confidence += 5



    # --------------------------------
    # Growth strength
    # --------------------------------

    if growth_score >= 80:

        confidence += 10

        reasons.append(
            "Strong growth profile"
        )

    elif growth_score >= 65:

        confidence += 5



    # --------------------------------
    # Risk adjustment
    # --------------------------------

    confidence -= (
        len(risks) * 5
    )


    if risks:

        reasons.append(
            f"{len(risks)} risk factors identified"
        )



    # --------------------------------
    # Historical performance
    # --------------------------------

    if (
        score_bucket_performance is not None
        and not score_bucket_performance.empty
    ):

        bucket = get_score_bucket(
            investment_score
        )


        match = score_bucket_performance[
            score_bucket_performance["Score Bucket"]
            == bucket
        ]


        if not match.empty:

            win_rate = float(
                match.iloc[0]["Win_Rate_Percent"]
            )


            confidence += (
                win_rate - 50
            ) * 0.25


            reasons.append(
                f"Historical {bucket} win rate {win_rate}%"
            )



    confidence = max(
        0,
        min(
            100,
            confidence
        )
    )


    return {

        "Confidence":
            round(confidence,1),

        "Confidence Reasons":
            reasons

    }



def get_score_bucket(score):

    if score >= 90:
        return "90+"

    elif score >= 80:
        return "80-89"

    elif score >= 70:
        return "70-79"

    elif score >= 60:
        return "60-69"

    else:
        return "<60"