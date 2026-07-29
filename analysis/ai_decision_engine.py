def generate_ai_decision(stock):

    decision = "HOLD"
    conviction = "Low"

    conviction_score = 50

    thesis = []
    risks = []
    actions = []
    triggers = []


    investment_score = stock.get(
        "Investment Score",
        0
    )

    confidence_score = stock.get(
        "Confidence Score",
        0
    )

    technical_score = stock.get(
        "Technical Score",
        0
    )

    quality_score = stock.get(
        "Quality Score",
        0
    )

    growth_score = stock.get(
        "Growth Score",
        0
    )


    # -----------------------------
    # Decision logic
    # -----------------------------

    if (
        investment_score >= 80
        and confidence_score >= 70
    ):

        decision = "BUY"

        actions.append(
            "Build position gradually"
        )


    elif investment_score >= 65:

        decision = "WATCH"

        actions.append(
            "Monitor for better entry"
        )


    else:

        decision = "AVOID"

        actions.append(
            "Do not initiate position"
        )


    # -----------------------------
    # Conviction scoring
    # -----------------------------

    conviction_score = round(

        (investment_score * 0.35)

        +

        (confidence_score * 0.35)

        +

        (quality_score * 0.15)

        +

        (growth_score * 0.15)

    )


    if conviction_score >= 80:

        conviction = "High"

    elif conviction_score >= 60:

        conviction = "Medium"

    else:

        conviction = "Low"


    # -----------------------------
    # Investment thesis
    # -----------------------------

    if technical_score >= 70:

        thesis.append(
            "Strong technical trend"
        )


    if quality_score >= 70:

        thesis.append(
            "Strong business quality"
        )


    if growth_score >= 70:

        thesis.append(
            "Strong growth profile"
        )


    # -----------------------------
    # Risk identification
    # -----------------------------

    if technical_score < 50:

        risks.append(
            "Weak technical momentum"
        )


    if quality_score < 50:

        risks.append(
            "Below preferred quality threshold"
        )


    if growth_score < 50:

        risks.append(
            "Growth profile requires monitoring"
        )


    # -----------------------------
    # Review triggers
    # -----------------------------

    triggers.append(
        "Review if investment score falls below 60"
    )

    triggers.append(
        "Review if trend breaks"
    )


    return {

        "Decision": decision,

        "Conviction": conviction,

        "Conviction Score": conviction_score,

        "Investment Thesis": thesis,

        "Risks": risks,

        "Recommended Action": actions,

        "Review Triggers": triggers

    }