from analysis.ai_engine import generate_ai_response


def generate_ai_analysis(
    ticker,
    investment_score,
    technical_score,
    quality_score,
    growth_score,
    ai_decision,
    reasons=None,
    risks=None,
    intelligence=None
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
    # Decision
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
    # Historical intelligence
    # -----------------------------

    historical_context = ""

    if intelligence:

        historical_context = f"""

Historical recommendation intelligence:

Signal performance:
{intelligence.get("Historical Signal Evidence","Unavailable")}

Score bucket performance:
{intelligence.get("Score Bucket Evidence","Unavailable")}

Component performance:
{intelligence.get("Component Evidence","Unavailable")}

Use this historical evidence when assessing confidence.
"""



    # -----------------------------
    # LLM prompt
    # -----------------------------

    llm_prompt = f"""

You are an equity research analyst.

Analyse this investment opportunity.

Ticker:
{ticker}

Current scores:

Investment Score:
{investment_score}

Technical Score:
{technical_score}

Quality Score:
{quality_score}

Growth Score:
{growth_score}

Current AI Decision:
{decision}


Bull factors:

{thesis}


Risks:

{bear_case}


{historical_context}


Provide:

1. Investment thesis
2. Key risks
3. Investor action
4. Review triggers
5. Confidence assessment

Keep the response concise and investor focused.

"""


    llm_response = generate_ai_response(
        llm_prompt
    )


    # fallback if Llama unavailable

    if not llm_response:

        llm_response = f"""

{ticker} is rated {decision}.

Investment thesis:
{", ".join(thesis)}

Risks:
{", ".join(bear_case)}

Action:
{", ".join(actions)}

"""


    return {

        "Ticker": ticker,

        "Investment View": llm_response,

        "Bull Case": thesis,

        "Bear Case": bear_case,

        "Investor Action": actions,

        "Review Triggers": triggers,

        "LLM Analysis": llm_response

    }