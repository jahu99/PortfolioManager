#!/usr/bin/env python3

"""
Stock Momentum Agent
LLM Provider Behaviour Test

Compares Ollama and Gemini across three governance scenarios.

Scenarios:

1. BUY MORE with strong quantitative evidence and no adverse context
   Expected behaviour: generally ACCEPT.

2. BUY MORE with strong quantitative evidence but materially negative
   Market & Event Intelligence.
   Expected behaviour: CHALLENGE or REJECT is reasonable, but the
   reasoning must explicitly consider the market intelligence.

3. HOLD with neutral/noisy market intelligence.
   Expected behaviour: generally ACCEPT. HOLD is the portfolio default
   unless there is a strong, action-specific reason to challenge it.

This script is standalone and does NOT modify production code.

Run:

    source .venv/bin/activate
    python tests/manual_llm_provider_ab_test.py
"""

import json
import os
import sys
from pathlib import Path


# ============================================================
# PROJECT PATH
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# IMPORTS
# ============================================================

from google import genai

from agents.ai_portfolio_reviewer import call_ollama


# ============================================================
# CONFIGURATION
# ============================================================

GEMINI_MODEL = "gemini-3.6-flash"

VALID_DECISIONS = {
    "ACCEPT",
    "CHALLENGE",
    "REJECT",
}


# ============================================================
# COMMON PORTFOLIO
# ============================================================

PORTFOLIO = {
    "total_market_value": 482.81,
    "cash": 2.81,
    "largest_position_pct": 17.92,
    "largest_position_ticker": "NVDA",
    "stock_count": 22,
    "etf_count": 3,
    "sector_count": 6,
}


# ============================================================
# SCENARIOS
# ============================================================

SCENARIOS = [

    # ========================================================
    # SCENARIO 1
    # ========================================================

    {
        "name": "STRONG BUY MORE — NO ADVERSE CONTEXT",

        "expected": (
            "The reviewer should generally ACCEPT the BUY MORE "
            "proposal because the quantitative evidence is strong "
            "and there is no materially negative contextual evidence."
        ),

        "candidate": {
            "ticker": "TEST1",
            "name": "Test Growth Company",
            "asset_type": "STOCK",

            "ownership": {
                "existing_holding": True,
                "allocation_pct": 3.5,
            },

            "analysis": {
                "investment_score": 91.0,
                "technical_score": 88.0,
                "quality_score": 87.0,
                "growth_score": 92.0,
                "risk_score": 30.0,
                "signal": "BUY",
            },

            "recommendation_intelligence": {
                "historical_observations": 50,
                "win_rate": 68.0,
            },

            "market_intelligence": {
                "Source": "TEST MARKET INTELLIGENCE",
                "Analyst Recommendation": "BUY",
                "Analyst Target Upside %": 22.0,
                "Earnings Status": "POSITIVE",
                "Next Earnings Date": "2026-10-15",
                "News Count": 2,
                "News Headlines": [
                    "Company reports stronger than expected demand.",
                    "Management reaffirms full-year guidance.",
                ],
            },
        },

        "decision": {
            "proposed_action": "BUY MORE",
            "evidence_score": 85.0,
            "evidence_strength": "STRONG",
            "decision_support": "SUPPORTED",
            "confidence": 88.0,
            "reason": (
                "BUY MORE is supported by a strong Investment Score, "
                "positive technical and growth characteristics, "
                "and favourable historical performance."
            ),
        },

        "preferred_decisions": {"ACCEPT"},
        "require_market_context": False,
    },


    # ========================================================
    # SCENARIO 2
    # ========================================================

    {
        "name": "BUY MORE — NEGATIVE MARKET CONTEXT",

        "expected": (
            "The reviewer should explicitly consider materially "
            "negative earnings guidance, weaker demand and increased "
            "operating costs. CHALLENGE or REJECT may be reasonable."
        ),

        "candidate": {
            "ticker": "TEST2",
            "name": "Test Company",
            "asset_type": "STOCK",

            "ownership": {
                "existing_holding": True,
                "allocation_pct": 3.5,
            },

            "analysis": {
                "investment_score": 88.0,
                "technical_score": 84.0,
                "quality_score": 82.0,
                "growth_score": 90.0,
                "risk_score": 35.0,
                "signal": "BUY",
            },

            "recommendation_intelligence": {
                "historical_observations": 25,
                "win_rate": 64.0,
            },

            "market_intelligence": {
                "Source": "TEST MARKET INTELLIGENCE",
                "Analyst Recommendation": "BUY",
                "Analyst Target Upside %": 18.0,
                "Earnings Status": "NEGATIVE GUIDANCE",
                "Next Earnings Date": "2026-10-15",
                "News Count": 2,
                "News Headlines": [
                    (
                        "Company reduces earnings guidance "
                        "because of weaker demand."
                    ),
                    (
                        "Operating costs increased significantly "
                        "during the latest quarter."
                    ),
                ],
            },
        },

        "decision": {
            "proposed_action": "BUY MORE",
            "evidence_score": 78.0,
            "evidence_strength": "STRONG",
            "decision_support": "SUPPORTED",
            "confidence": 82.0,
            "reason": (
                "BUY MORE is supported by a strong Investment Score, "
                "positive technical and growth characteristics, "
                "and favourable historical recommendation performance."
            ),
        },

        "preferred_decisions": {
            "CHALLENGE",
            "REJECT",
        },

        "require_market_context": True,
    },


    # ========================================================
    # SCENARIO 3
    # ========================================================

    {
        "name": "HOLD — NOISY BUT NON-MATERIAL NEWS",

        "expected": (
            "The reviewer should generally ACCEPT HOLD. The supplied "
            "news is informational but does not materially contradict "
            "the deterministic portfolio action."
        ),

        "candidate": {
            "ticker": "TEST3",
            "name": "Established Company",
            "asset_type": "STOCK",

            "ownership": {
                "existing_holding": True,
                "allocation_pct": 4.0,
            },

            "analysis": {
                "investment_score": 58.0,
                "technical_score": 55.0,
                "quality_score": 72.0,
                "growth_score": 60.0,
                "risk_score": 45.0,
                "signal": "HOLD",
            },

            "recommendation_intelligence": {
                "historical_observations": 120,
                "win_rate": 54.0,
            },

            "market_intelligence": {
                "Source": "TEST MARKET INTELLIGENCE",
                "Analyst Recommendation": "HOLD",
                "Analyst Target Upside %": 4.0,
                "Earnings Status": "NEUTRAL",
                "Next Earnings Date": "2026-11-01",
                "News Count": 2,
                "News Headlines": [
                    (
                        "Company announces a minor management "
                        "reorganisation."
                    ),
                    (
                        "Industry commentary discusses general "
                        "competitive pressures."
                    ),
                ],
            },
        },

        "decision": {
            "proposed_action": "HOLD",
            "evidence_score": 68.0,
            "evidence_strength": "MODERATE",
            "decision_support": "SUPPORTED",
            "confidence": 70.0,
            "reason": (
                "HOLD remains the default portfolio action because "
                "there is no sufficiently strong evidence supporting "
                "an increase, reduction or sale."
            ),
        },

        "preferred_decisions": {"ACCEPT"},
        "require_market_context": False,
    },
]


# ============================================================
# PROMPT
# ============================================================

def build_prompt(
    portfolio,
    candidate,
    decision,
):

    return f"""
You are an independent portfolio decision reviewer.

Your role is ADVISORY ONLY.

You are reviewing a deterministic portfolio proposal.

The deterministic decision engine remains authoritative.

Your task is NOT to invent a different portfolio action.

Your task is to determine whether the proposed action is supported
or materially challenged by the supplied evidence.

IMPORTANT GOVERNANCE PRINCIPLES:

1. Use ONLY evidence supplied below.

2. Do NOT invent prices, RSI values, moving averages,
   technical indicators or other facts.

3. Review the SPECIFIC proposed action.

   For example:

   - BUY MORE is not the same as BUY.
   - BUY NEW is not the same as BUY MORE.
   - HOLD should not be challenged merely because the stock
     has positive or negative characteristics.

4. HOLD is the default portfolio action.

   A HOLD decision should only be challenged when there is
   clear, material, action-specific evidence that retaining
   the position unchanged is inappropriate.

5. Market & Event Intelligence is contextual evidence.

   If it contains information materially relevant to the
   proposed action, explicitly consider that information.

6. Do NOT manufacture a challenge merely to appear analytical.

7. Do NOT reject an action simply because the evidence does
   not prove that another action is necessary.

PORTFOLIO

{json.dumps(portfolio, indent=2, default=str)}

CANDIDATE

{json.dumps(candidate, indent=2, default=str)}

DETERMINISTIC DECISION

{json.dumps(decision, indent=2, default=str)}

MARKET & EVENT INTELLIGENCE

{json.dumps(
    candidate.get("market_intelligence", {}),
    indent=2,
    default=str,
)}

Return ONLY one valid JSON object.

The response MUST contain EXACTLY these fields:

{{
    "review_decision": "ACCEPT | CHALLENGE | REJECT",
    "confidence": 0,
    "challenge": false,
    "reason": "Short action-specific evidence-based explanation"
}}

Decision definitions:

ACCEPT:
The supplied evidence supports the proposed action.

CHALLENGE:
There is material uncertainty, contradiction or contextual
evidence that should cause the deterministic proposal to be
questioned.

REJECT:
The supplied evidence materially contradicts the proposed action.

Rules:

- review_decision must be ACCEPT, CHALLENGE or REJECT.
- confidence must be a number between 0 and 100.
- challenge must be true or false.
- reason must be non-empty.
- reason must refer to the specific proposed action.
- No markdown.
- No code fences.
- No text before or after the JSON object.
""".strip()


# ============================================================
# JSON EXTRACTION
# ============================================================

def extract_json(response):

    if isinstance(response, dict):
        return response

    if not isinstance(response, str):
        raise ValueError(
            f"Response was not text or dict: {type(response)}"
        )

    text = response.strip()

    try:
        return json.loads(text)

    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1 or end <= start:
        raise ValueError(
            "No JSON object found in response"
        )

    return json.loads(
        text[start:end + 1]
    )


# ============================================================
# RESPONSE VALIDATION
# ============================================================

def validate_response(response):

    if not isinstance(response, dict):
        raise ValueError(
            "Response is not a JSON object"
        )

    required = {
        "review_decision",
        "confidence",
        "challenge",
        "reason",
    }

    missing = required - set(response.keys())

    if missing:
        raise ValueError(
            f"Missing required fields: {sorted(missing)}"
        )

    review_decision = str(
        response["review_decision"]
    ).strip().upper()

    if review_decision not in VALID_DECISIONS:
        raise ValueError(
            f"Invalid review decision: {review_decision}"
        )

    confidence = float(
        response["confidence"]
    )

    if not 0 <= confidence <= 100:
        raise ValueError(
            f"Invalid confidence: {confidence}"
        )

    challenge = response["challenge"]

    if not isinstance(challenge, bool):
        raise ValueError(
            "Challenge must be boolean"
        )

    reason = str(
        response["reason"]
    ).strip()

    if not reason:
        raise ValueError(
            "Reason is empty"
        )

    return {
        "review_decision": review_decision,
        "confidence": confidence,
        "challenge": challenge,
        "reason": reason,
    }


# ============================================================
# ACTION-SPECIFIC REASON CHECK
# ============================================================

def check_action_specificity(
    reason,
    proposed_action,
):

    reason_upper = reason.upper()
    action_upper = proposed_action.upper()

    # Exact action appears.

    if action_upper in reason_upper:
        return True

    # HOLD can reasonably be described as retaining or keeping.

    if action_upper == "HOLD":

        hold_terms = [
            "HOLD",
            "RETAIN",
            "RETAINING",
            "UNCHANGED",
            "KEEP",
            "KEEPING",
        ]

        return any(
            term in reason_upper
            for term in hold_terms
        )

    return False


# ============================================================
# MARKET INTELLIGENCE CHECK
# ============================================================

def check_market_intelligence_usage(
    reason,
):

    reason_lower = reason.lower()

    keywords = [
        "guidance",
        "earnings",
        "operating cost",
        "cost pressure",
        "weaker demand",
        "market context",
        "near-term risk",
        "negative",
        "demand",
    ]

    found = [
        keyword
        for keyword in keywords
        if keyword in reason_lower
    ]

    return {
        "references_market_intelligence": bool(found),
        "matched_terms": found,
    }


# ============================================================
# SEMANTIC CONSISTENCY CHECK
# ============================================================

def check_semantic_consistency(
    result,
):

    decision = result["review_decision"]
    challenge = result["challenge"]

    if decision == "ACCEPT" and challenge:
        return False

    if decision == "CHALLENGE" and not challenge:
        return False

    return True


# ============================================================
# OLLAMA
# ============================================================

def run_ollama(prompt):

    raw = call_ollama(prompt)

    parsed = extract_json(raw)

    return validate_response(parsed)


# ============================================================
# GEMINI
# ============================================================

def run_gemini(prompt):

    api_key = os.getenv(
        "GEMINI_API_KEY"
    )

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set"
        )

    client = genai.Client(
        api_key=api_key
    )

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
    )

    raw = response.text

    parsed = extract_json(raw)

    return validate_response(parsed)


# ============================================================
# PROVIDER TEST
# ============================================================

def run_provider(
    provider_name,
    provider_function,
    scenario,
):

    print("\n" + "-" * 72)
    print(
        f"{provider_name}: {scenario['name']}"
    )
    print("-" * 72)

    prompt = build_prompt(
        portfolio=PORTFOLIO,
        candidate=scenario["candidate"],
        decision=scenario["decision"],
    )

    try:

        result = provider_function(prompt)

        action_specific = (
            check_action_specificity(
                result["reason"],
                scenario["decision"][
                    "proposed_action"
                ],
            )
        )

        market_check = (
            check_market_intelligence_usage(
                result["reason"]
            )
        )

        semantic_consistency = (
            check_semantic_consistency(result)
        )

        preferred = (
            result["review_decision"]
            in scenario["preferred_decisions"]
        )

        result["action_specific"] = (
            action_specific
        )

        result["semantic_consistency"] = (
            semantic_consistency
        )

        result.update(market_check)

        result["preferred_decision"] = (
            preferred
        )

        return result

    except Exception as exc:

        return {
            "error": str(exc),
        }


# ============================================================
# SCENARIO VALIDATION
# ============================================================

def evaluate_scenario(
    scenario,
    result,
):

    if "error" in result:

        return {
            "passed": False,
            "reason": (
                f"Provider error: {result['error']}"
            ),
        }

    checks = []

    checks.append(
        result.get(
            "semantic_consistency",
            False,
        )
    )

    checks.append(
        result.get(
            "action_specific",
            False,
        )
    )

    # Scenario-specific decision expectation.

    checks.append(
        result.get(
            "preferred_decision",
            False,
        )
    )

    # Negative market context scenario requires explicit usage.

    if scenario.get(
        "require_market_context",
        False,
    ):

        checks.append(
            result.get(
                "references_market_intelligence",
                False,
            )
        )

    passed = all(checks)

    return {
        "passed": passed,
        "reason": (
            "All scenario checks passed"
            if passed
            else "One or more scenario checks failed"
        ),
    }


# ============================================================
# RESULT DISPLAY
# ============================================================

def print_result(
    provider,
    scenario,
    result,
    evaluation,
):

    print("\n" + "=" * 72)

    print(
        f"{provider} RESULT — {scenario['name']}"
    )

    print("=" * 72)

    print(
        json.dumps(
            result,
            indent=2,
        )
    )

    print("\nVALIDATION:")

    print(
        f"Expected: {scenario['expected']}"
    )

    print(
        f"Result: "
        f"{'PASS' if evaluation['passed'] else 'FAIL'}"
    )

    print(
        f"Reason: {evaluation['reason']}"
    )


# ============================================================
# SUMMARY
# ============================================================

def print_summary(results):

    print("\n" + "=" * 72)
    print("FINAL PROVIDER SUMMARY")
    print("=" * 72)

    print()

    print(
        f"{'SCENARIO':<42}"
        f"{'OLLAMA':<15}"
        f"{'GEMINI':<15}"
    )

    print("-" * 72)

    ollama_passes = 0
    gemini_passes = 0

    for scenario_name, data in results.items():

        ollama = data["ollama"]["evaluation"]
        gemini = data["gemini"]["evaluation"]

        ollama_status = (
            "PASS"
            if ollama["passed"]
            else "FAIL"
        )

        gemini_status = (
            "PASS"
            if gemini["passed"]
            else "FAIL"
        )

        if ollama["passed"]:
            ollama_passes += 1

        if gemini["passed"]:
            gemini_passes += 1

        print(
            f"{scenario_name[:40]:<42}"
            f"{ollama_status:<15}"
            f"{gemini_status:<15}"
        )

    print("\n" + "-" * 72)

    print(
        f"Ollama score: "
        f"{ollama_passes}/{len(results)}"
    )

    print(
        f"Gemini score: "
        f"{gemini_passes}/{len(results)}"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("\n" + "=" * 72)
    print("STOCK MOMENTUM AGENT")
    print("LLM PROVIDER BEHAVIOUR TEST")
    print("=" * 72)

    results = {}

    for scenario in SCENARIOS:

        print("\n" + "#" * 72)
        print(
            f"SCENARIO: {scenario['name']}"
        )
        print("#" * 72)

        # ----------------------------------------------------
        # OLLAMA
        # ----------------------------------------------------

        ollama_result = run_provider(
            provider_name="OLLAMA",
            provider_function=run_ollama,
            scenario=scenario,
        )

        ollama_evaluation = (
            evaluate_scenario(
                scenario,
                ollama_result,
            )
        )

        print_result(
            provider="OLLAMA",
            scenario=scenario,
            result=ollama_result,
            evaluation=ollama_evaluation,
        )

        # ----------------------------------------------------
        # GEMINI
        # ----------------------------------------------------

        gemini_result = run_provider(
            provider_name="GEMINI",
            provider_function=run_gemini,
            scenario=scenario,
        )

        gemini_evaluation = (
            evaluate_scenario(
                scenario,
                gemini_result,
            )
        )

        print_result(
            provider="GEMINI",
            scenario=scenario,
            result=gemini_result,
            evaluation=gemini_evaluation,
        )

        results[scenario["name"]] = {

            "ollama": {
                "result": ollama_result,
                "evaluation": ollama_evaluation,
            },

            "gemini": {
                "result": gemini_result,
                "evaluation": gemini_evaluation,
            },
        }

    print_summary(results)

    print("\n" + "=" * 72)
    print("TEST COMPLETE")
    print("=" * 72)


if __name__ == "__main__":
    main()