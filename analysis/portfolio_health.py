import pandas as pd



def calculate_portfolio_health(
    portfolio_summary,
    sector_summary
):

    if (
        portfolio_summary is None
        or portfolio_summary.empty
    ):
        return {

            "Health Score": 0,

            "Rating": "Unknown",

            "Strengths": [],

            "Risks": []

        }



    score = 100

    strengths = []

    risks = []



    # ---------------------------------
    # Quality
    # ---------------------------------

    if "Quality Score" in portfolio_summary.columns:

        avg_quality = (
            portfolio_summary["Quality Score"]
            .mean()
        )


        if avg_quality >= 85:

            strengths.append(
                "High quality holdings"
            )


        elif avg_quality < 70:

            score -= 10

            risks.append(
                "Portfolio quality below target"
            )



    # ---------------------------------
    # Momentum
    # ---------------------------------

    if "Momentum Score" in portfolio_summary.columns:

        avg_momentum = (
            portfolio_summary["Momentum Score"]
            .mean()
        )


        if avg_momentum >= 80:

            strengths.append(
                "Strong market momentum"
            )


        elif avg_momentum < 60:

            score -= 10

            risks.append(
                "Weak momentum across holdings"
            )



    # ---------------------------------
    # Sector concentration
    # ---------------------------------

    if (
        sector_summary is not None
        and not sector_summary.empty
    ):


        for _, row in sector_summary.iterrows():

            allocation = row.get(
                "Current %",
                0
            )


            sector = row.get(
                "Sector",
                "Unknown"
            )


            if allocation > 40:

                score -= 15

                risks.append(
                    f"{sector} concentration risk"
                )


            elif allocation > 25:

                score -= 5

                risks.append(
                    f"{sector} overweight"
                )



    # ---------------------------------
    # Score limits
    # ---------------------------------

    if score < 0:
        score = 0


    if score >= 85:

        rating = "Excellent"


    elif score >= 70:

        rating = "Good"


    elif score >= 50:

        rating = "Needs Improvement"


    else:

        rating = "Poor"



    return {

        "Health Score": score,

        "Rating": rating,

        "Strengths": strengths,

        "Risks": risks

    }