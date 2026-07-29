import pandas as pd


def calculate_portfolio_health(
    portfolio_summary,
    sector_summary
):

    health_score = 100

    strengths = []
    risks = []


    # ---------------------------------
    # Validate inputs
    # ---------------------------------

    if portfolio_summary is None or portfolio_summary.empty:

        return {
            "Health Score": 0,
            "Rating": "Unknown",
            "Strengths": [],
            "Risks": [
                "Portfolio data unavailable"
            ]
        }


    if sector_summary is None or sector_summary.empty:

        return {
            "Health Score": 50,
            "Rating": "Needs Attention",
            "Strengths": [],
            "Risks": [
                "Sector analysis unavailable"
            ]
        }


    # ---------------------------------
    # Portfolio size / diversification
    # ---------------------------------

    holding_count = len(
        portfolio_summary
    )


    if holding_count >= 10:

        health_score += 5

        strengths.append(
            "Good number of portfolio holdings"
        )


    elif holding_count <= 5:

        health_score -= 5

        risks.append(
            "Portfolio has limited number of holdings"
        )


    # ---------------------------------
    # Single stock concentration
    # ---------------------------------

    if "Allocation %" in portfolio_summary.columns:


        for _, holding in portfolio_summary.iterrows():

            ticker = holding.get(
                "Ticker",
                "Unknown"
            )

            allocation = float(
                holding.get(
                    "Allocation %",
                    0
                )
            )


            if allocation >= 40:

                health_score -= 15

                risks.append(
                    f"{ticker} represents excessive portfolio concentration"
                )


            elif allocation >= 20:

                health_score -= 5

                risks.append(
                    f"{ticker} has high portfolio weighting"
                )


            elif allocation <= 5:

                risks.append(
                    f"{ticker} position may have limited impact"
                )


    # ---------------------------------
    # Sector concentration
    # ---------------------------------

    if (
        "Sector" in sector_summary.columns
        and
        "Allocation %" in sector_summary.columns
    ):


        for _, sector in sector_summary.iterrows():

            sector_name = sector.get(
                "Sector",
                "Unknown"
            )

            sector_allocation = float(
                sector.get(
                    "Allocation %",
                    0
                )
            )


            if sector_allocation >= 80:

                health_score -= 15

                risks.append(
                    f"Severe {sector_name} sector concentration risk"
                )


            elif sector_allocation >= 60:

                health_score -= 10

                risks.append(
                    f"{sector_name} sector concentration risk"
                )


            elif sector_allocation <= 20:

                strengths.append(
                    f"{sector_name} sector exposure controlled"
                )


    # ---------------------------------
    # Portfolio quality
    # ---------------------------------

    if "Investment Score" in portfolio_summary.columns:


        average_score = portfolio_summary[
            "Investment Score"
        ].mean()


        if average_score >= 75:

            health_score += 10

            strengths.append(
                "Strong average investment quality"
            )


        elif average_score < 60:

            health_score -= 10

            risks.append(
                "Portfolio quality below target"
            )


    # ---------------------------------
    # Quality score
    # ---------------------------------

    if "Quality Score" in portfolio_summary.columns:


        average_quality = portfolio_summary[
            "Quality Score"
        ].mean()


        if average_quality >= 70:

            health_score += 5

            strengths.append(
                "Strong business quality"
            )


        elif average_quality < 50:

            health_score -= 5

            risks.append(
                "Average business quality below preferred level"
            )


    # ---------------------------------
    # Clamp score
    # ---------------------------------

    health_score = max(
        0,
        min(
            100,
            round(health_score)
        )
    )


    # ---------------------------------
    # Rating
    # ---------------------------------

    if health_score >= 80:

        rating = "Excellent"


    elif health_score >= 65:

        rating = "Healthy"


    elif health_score >= 45:

        rating = "Needs Attention"


    else:

        rating = "Poor"


    return {

        "Health Score": health_score,

        "Rating": rating,

        "Strengths": list(
            dict.fromkeys(strengths)
        ),

        "Risks": list(
            dict.fromkeys(risks)
        )
    }