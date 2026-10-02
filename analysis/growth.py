def score_growth(fundamentals):

    """
    Score growth independently of business quality.

    Growth measures:
        - Revenue Growth
        - Earnings Growth

    Missing metrics are excluded and the remaining weights
    are renormalised.

    Profit Margin, ROE and Debt deliberately do not belong
    in Growth. They are scored by score_quality().
    """

    scores = {}
    reasons = []
    risks = []

    # =========================================================
    # REVENUE GROWTH — 60%
    # =========================================================

    revenue_growth = fundamentals.get(
        "Revenue Growth"
    )

    if revenue_growth is not None:

        if revenue_growth >= 0.20:

            scores["revenue"] = 100

            reasons.append(
                "Exceptional revenue growth"
            )

        elif revenue_growth >= 0.15:

            scores["revenue"] = 80

            reasons.append(
                "Strong revenue growth"
            )

        elif revenue_growth >= 0.05:

            scores["revenue"] = 50

            reasons.append(
                "Positive revenue growth"
            )

        elif revenue_growth > 0:

            scores["revenue"] = 20

        else:

            scores["revenue"] = 0

            risks.append(
                "Weak revenue growth"
            )

    # =========================================================
    # EARNINGS GROWTH — 40%
    # =========================================================

    earnings_growth = fundamentals.get(
        "Earnings Growth"
    )

    if earnings_growth is not None:

        if earnings_growth >= 0.30:

            scores["earnings"] = 100

            reasons.append(
                "Exceptional earnings growth"
            )

        elif earnings_growth >= 0.10:

            scores["earnings"] = 75

            reasons.append(
                "Strong earnings growth"
            )

        elif earnings_growth > 0:

            scores["earnings"] = 40

            reasons.append(
                "Positive earnings growth"
            )

        else:

            scores["earnings"] = 0

            risks.append(
                "Weak earnings growth"
            )

    # =========================================================
    # WEIGHTED SCORE
    # =========================================================

    weights = {
        "revenue": 60,
        "earnings": 40,
    }

    available_weight = sum(
        weights[name]
        for name in scores
    )

    if available_weight == 0:

        return {
            "Growth Score": 0,
            "Growth Reasons": reasons,
            "Growth Risks": risks,
        }

    score = sum(
        scores[name] * weights[name]
        for name in scores
    ) / available_weight

    score = min(
        score,
        100
    )

    return {
        "Growth Score": round(score),
        "Growth Reasons": reasons,
        "Growth Risks": risks,
    }