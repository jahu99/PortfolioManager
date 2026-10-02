def score_quality(fundamentals):

    """
    Score business quality independently of growth.

    Quality measures:
        - Profit Margin       35%
        - Return on Equity    30%
        - Debt / Equity       20%
        - Free Cash Flow      15%

    Missing metrics are excluded and the remaining weights
    are renormalised.

    Revenue Growth and Earnings Growth deliberately do not
    belong in Quality. They are scored by score_growth().
    """

    scores = {}
    reasons = []

    # =========================================================
    # PROFIT MARGIN — 35%
    # =========================================================

    margin = fundamentals.get(
        "Profit Margin"
    )

    if margin is not None:

        if margin > 0.40:

            scores["margin"] = 100

            reasons.append(
                "Exceptional profit margin"
            )

        elif margin > 0.20:

            scores["margin"] = 75

            reasons.append(
                "High profit margin"
            )

        elif margin > 0.10:

            scores["margin"] = 40

            reasons.append(
                "Healthy profit margin"
            )

        elif margin > 0:

            scores["margin"] = 20

        else:

            scores["margin"] = 0

    # =========================================================
    # RETURN ON EQUITY — 30%
    # =========================================================

    roe = fundamentals.get(
        "Return on Equity"
    )

    if roe is not None:

        if roe > 1:

            scores["roe"] = 100

            reasons.append(
                "Exceptional ROE"
            )

        elif roe > 0.30:

            scores["roe"] = 90

            reasons.append(
                "Excellent ROE"
            )

        elif roe > 0.15:

            scores["roe"] = 60

            reasons.append(
                "Strong ROE"
            )

        elif roe > 0:

            scores["roe"] = 25

        else:

            scores["roe"] = 0

    # =========================================================
    # DEBT / EQUITY — 20%
    # =========================================================

    debt = fundamentals.get(
        "Debt to Equity"
    )

    if debt is not None:

        if debt < 50:

            scores["debt"] = 100

            reasons.append(
                "Low debt"
            )

        elif debt < 150:

            scores["debt"] = 50

            reasons.append(
                "Moderate debt"
            )

        else:

            scores["debt"] = 0

    # =========================================================
    # FREE CASH FLOW — 15%
    # =========================================================

    free_cash_flow = fundamentals.get(
        "Free Cash Flow"
    )

    if free_cash_flow is not None:

        if free_cash_flow > 0:

            scores["fcf"] = 100

            reasons.append(
                "Positive free cash flow"
            )

        else:

            scores["fcf"] = 0

    # =========================================================
    # WEIGHTED SCORE
    # =========================================================

    weights = {
        "margin": 35,
        "roe": 30,
        "debt": 20,
        "fcf": 15,
    }

    available_weight = sum(
        weights[name]
        for name in scores
    )

    if available_weight == 0:

        return 0, reasons

    score = sum(
        scores[name] * weights[name]
        for name in scores
    ) / available_weight

    score = min(
        score,
        100
    )

    return round(score), reasons