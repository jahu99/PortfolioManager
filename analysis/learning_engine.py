def evaluate_recommendation_outcome(
    entry_price,
    exit_price,
    signal
):

    if entry_price == 0:
        return {
            "Return": 0,
            "Outcome": "UNKNOWN"
        }


    return_percent = (
        (exit_price - entry_price)
        /
        entry_price
    ) * 100


    if signal in [
        "BUY",
        "STRONG BUY"
    ]:

        if return_percent > 5:

            outcome = "SUCCESS"

        elif return_percent < -5:

            outcome = "FAILURE"

        else:

            outcome = "NEUTRAL"


    else:

        outcome = "NOT_TESTED"


    return {

        "Return": round(
            return_percent,
            2
        ),

        "Outcome":
            outcome

    }