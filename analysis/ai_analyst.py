def generate_ai_analysis(
    ticker,
    investment_score,
    technical_score,
    quality_score,
    growth_score,
    ai_decision,
    reasons=None,
    risks=None
):

    reasons = reasons or []
    risks = risks or []

    thesis = []
    bear_case = []
    actions = []
    triggers = []


    # -----------------------------
    # Bull case generation
    # -----------------------------

    if technical_score >= 75:
        thesis.append(
            "Strong technical trend with positive momentum"
        )

    if quality_score >= 70:
        thesis.append(
            "Strong business quality characteristics"
        )

    if growth_score >= 70:
        thesis.append(
            "Strong growth profile"
        )


    # -----------------------------
    # Risk generation
    # -----------------------------

    if technical_score < 60:
        bear_case.append(
            "Technical momentum weakening"
        )

    if quality_score < 50:
        bear_case.append(
            "Business quality below preferred threshold"
        )

    if growth_score < 50:
        bear_case.append(
            "Growth profile requires monitoring"
        )


    for risk in risks:
        if risk not in bear_case:
            bear_case.append(risk)



    # -----------------------------
    # Investor action
    # -----------------------------

    decision = ai_decision.get(
        "Decision",
        "WATCH"
    )


    if decision == "BUY":

        actions.append(
            "Consider initiating or maintaining position"
        )

    elif decision == "WATCH":

        actions.append(
            "Monitor for improved entry conditions"
        )

    else:

        actions.append(
            "Avoid new position until fundamentals improve"
        )


    # -----------------------------
    # Review triggers
    # -----------------------------

    triggers.extend(
        [
            "Investment score falls below 60",
            "Trend breaks below key moving averages",
            "Growth outlook deteriorates"
        ]
    )


    # -----------------------------
    # Create analyst summary
    # -----------------------------

    summary = f"""
{ticker} is currently rated {decision}.

Investment View:

The decision is supported by:
{', '.join(thesis) if thesis else 'Limited positive factors identified.'}

Key Risks:

{', '.join(bear_case) if bear_case else 'No significant risks identified.'}

Recommended Action:

{', '.join(actions)}

Review If:

{', '.join(triggers)}
"""


    return {

        "Ticker": ticker,

        "Investment View": summary,

        "Bull Case": thesis,

        "Bear Case": bear_case,

        "Investor Action": actions,

        "Review Triggers": triggers

    }