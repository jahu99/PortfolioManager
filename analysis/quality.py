def score_quality(fundamentals):

    score = 0
    reasons = []


    # -----------------------------
    # Revenue Growth (25)
    # -----------------------------

    revenue_growth = fundamentals.get(
        "Revenue Growth",
        0
    )


    if revenue_growth > 0.50:
        score += 25
        reasons.append(
            "Exceptional revenue growth"
        )

    elif revenue_growth > 0.20:
        score += 20
        reasons.append(
            "Strong revenue growth"
        )

    elif revenue_growth > 0.05:
        score += 10
        reasons.append(
            "Positive revenue growth"
        )



    # -----------------------------
    # Earnings Growth (20)
    # -----------------------------

    earnings_growth = fundamentals.get(
        "Earnings Growth",
        0
    )


    if earnings_growth > 0.30:
        score += 20
        reasons.append(
            "Exceptional earnings growth"
        )

    elif earnings_growth > 0.10:
        score += 15
        reasons.append(
            "Strong earnings growth"
        )

    elif earnings_growth > 0:
        score += 8
        reasons.append(
            "Positive earnings growth"
        )



    # -----------------------------
    # Profit Margin (20)
    # -----------------------------

    margin = fundamentals.get(
        "Profit Margin",
        0
    )


    if margin > 0.40:
        score += 20
        reasons.append(
            "Exceptional margins"
        )

    elif margin > 0.20:
        score += 15
        reasons.append(
            "High profit margin"
        )

    elif margin > 0.10:
        score += 8
        reasons.append(
            "Healthy profit margin"
        )



    # -----------------------------
    # Return on Equity (20)
    # -----------------------------

    roe = fundamentals.get(
        "Return on Equity",
        0
    )


    if roe > 1:
        score += 20
        reasons.append(
            "Exceptional ROE"
        )

    elif roe > 0.30:
        score += 18
        reasons.append(
            "Excellent ROE"
        )

    elif roe > 0.15:
        score += 12
        reasons.append(
            "Strong ROE"
        )

    elif roe > 0:
        score += 5



    # -----------------------------
    # Debt (10)
    # -----------------------------

    debt = fundamentals.get(
        "Debt to Equity",
        999
    )


    if debt < 50:
        score += 10
        reasons.append(
            "Low debt"
        )

    elif debt < 150:
        score += 5
        reasons.append(
            "Moderate debt"
        )



    # -----------------------------
    # Free Cash Flow (5)
    # -----------------------------

    free_cash_flow = fundamentals.get(
        "Free Cash Flow",
        0
    )


    if free_cash_flow > 0:

        score += 5

        reasons.append(
            "Positive free cash flow"
        )



    if score > 100:
        score = 100



    return round(score), reasons