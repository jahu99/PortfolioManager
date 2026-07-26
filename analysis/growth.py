def score_growth(fundamentals):

    score = 0
    reasons = []
    risks = []


    revenue_growth = fundamentals.get(
        "Revenue Growth",
        0
    )

    margin = fundamentals.get(
        "Profit Margin",
        0
    )

    roe = fundamentals.get(
        "Return on Equity",
        0
    )

    debt = fundamentals.get(
        "Debt to Equity",
        0
    )


    # -------------------------
    # Revenue growth
    # -------------------------

    if revenue_growth >= 0.15:

        score += 40
        reasons.append(
            "Strong revenue growth"
        )

    elif revenue_growth >= 0.05:

        score += 25
        reasons.append(
            "Positive revenue growth"
        )

    else:

        risks.append(
            "Weak revenue growth"
        )


    # -------------------------
    # Profitability
    # -------------------------

    if margin >= 0.20:

        score += 20
        reasons.append(
            "Strong profit margin"
        )

    elif margin >= 0.10:

        score += 10

    else:

        risks.append(
            "Weak profit margin"
        )


    # -------------------------
    # Return on equity
    # -------------------------

    if roe >= 0.20:

        score += 25
        reasons.append(
            "Strong return on equity"
        )

    elif roe >= 0.10:

        score += 15


    else:

        risks.append(
            "Weak return on equity"
        )


    # -------------------------
    # Debt
    # -------------------------

    if debt <= 1:

        score += 15

    elif debt <= 2:

        score += 5

    else:

        risks.append(
            "High debt"
        )


    return {

        "Growth Score": min(
            score,
            100
        ),

        "Growth Reasons":
            reasons,

        "Growth Risks":
            risks
    }