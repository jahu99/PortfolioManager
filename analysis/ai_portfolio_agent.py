from analysis.ai_client import ask_ai
import json



def generate_ai_portfolio_review(
    portfolio_summary,
    portfolio_manager_review,
    trade_plan
):


    system_prompt = """

You are an experienced portfolio manager.

Analyse the provided portfolio data.

You must:
- identify portfolio strengths
- identify risks
- evaluate concentration
- review proposed trades
- provide practical recommendations

Do not invent data.
Only use information supplied.

Return concise professional investment commentary.

"""


    user_prompt = f"""

PORTFOLIO DATA:

{portfolio_summary.to_json()}


PORTFOLIO MANAGER REVIEW:

{json.dumps(
    portfolio_manager_review,
    indent=2
)}


TRADE PLAN:

{trade_plan.to_json()}


Provide:

1. Overall assessment
2. Key strengths
3. Key risks
4. Recommended actions
5. Portfolio manager summary

"""


    return ask_ai(
        system_prompt,
        user_prompt
    )