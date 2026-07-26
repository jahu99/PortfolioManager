import pandas as pd


def calculate_confidence(
    score,
    signal_performance=None,
    score_bucket_performance=None
):

    confidence = 50
    reasons = []


    # -----------------------------
    # Score confidence
    # -----------------------------

    if score_bucket_performance is not None and not score_bucket_performance.empty:

        bucket = get_score_bucket(score)


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
            ) * 0.5


            reasons.append(
                f"Historical {bucket} win rate {win_rate}%"
            )



    # -----------------------------
    # Signal confidence
    # -----------------------------

    if signal_performance is not None and not signal_performance.empty:


        signal_match = signal_performance[
            signal_performance["Signal"]
            == "BUY"
        ]


        if not signal_match.empty:


            win_rate = float(
                signal_match.iloc[0]["Win_Rate_Percent"]
            )


            confidence += (
                win_rate - 50
            ) * 0.25


            reasons.append(
                f"BUY signal history {win_rate}%"
            )



    confidence = max(
        0,
        min(
            100,
            confidence
        )
    )


    return {
        "Confidence": round(
            confidence,
            1
        ),

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