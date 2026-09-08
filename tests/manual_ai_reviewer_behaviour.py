from __future__ import annotations

import json
import os
import time
from typing import Any

from agents.ai_portfolio_reviewer import _normalise_llm_response

import requests


OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    "http://localhost:11434/api/chat",
)

OLLAMA_MODEL = os.getenv(
    "OLLAMA_MODEL",
    "qwen2.5:1.5b",
)

TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "120"))


# ============================================================
# Controlled gold-standard test cases
# ============================================================

TEST_CASES = [
    {
        "name": "STRONG BUY MORE",
        "expected": "ACCEPT",
        "evidence": {
            "asset_type": "STOCK",
            "proposed_action": "BUY MORE",
            "investment_score": 88,
            "technical_score": 90,
            "quality_score": 86,
            "growth_score": 89,
            "risk_score": 78,
            "signal": "STRONG BUY",
            "current_price": 120.0,
            "ma50": 112.0,
            "ma200": 98.0,
            "rsi": 62.0,
            "evidence_score": 82.0,
            "evidence_strength": "STRONG",
            "deterministic_confidence": 85.0,
            "historical_signal_win_rate": 75.0,
            "historical_average_return_pct": 12.0,
        },
    },
    {
        "name": "WEAK BUY MORE",
        "expected": "CHALLENGE",
        "evidence": {
            "asset_type": "STOCK",
            "proposed_action": "BUY MORE",
            "investment_score": 72,
            "technical_score": 76,
            "quality_score": 70,
            "growth_score": 74,
            "risk_score": 55,
            "signal": "BUY",
            "current_price": 120.0,
            "ma50": 118.0,
            "ma200": 115.0,
            "rsi": 55.0,
            "evidence_score": 55.0,
            "evidence_strength": "WEAK",
            "deterministic_confidence": 60.0,
            "historical_signal_win_rate": None,
            "historical_average_return_pct": None,
        },
    },
    {
        "name": "CLEAR CONTRADICTION",
        "expected": "REJECT",
        "evidence": {
            "asset_type": "STOCK",
            "proposed_action": "BUY MORE",
            "investment_score": 35,
            "technical_score": 25,
            "quality_score": 42,
            "growth_score": 30,
            "risk_score": 20,
            "signal": "SELL",
            "current_price": 80.0,
            "ma50": 92.0,
            "ma200": 105.0,
            "rsi": 34.0,
            "evidence_score": 30.0,
            "evidence_strength": "WEAK",
            "deterministic_confidence": 80.0,
            "historical_signal_win_rate": 28.0,
            "historical_average_return_pct": -14.0,
        },
    },
]


# ============================================================
# Prompt A
# ============================================================

PROMPT_A = """
You are an independent portfolio governance reviewer.

Review ONLY the supplied evidence.

The proposed action is authoritative. You are reviewing that action,
not generating a different recommendation.

For BUY MORE, evaluate whether the evidence supports adding capital
to the existing position rather than leaving it unchanged.

ACCEPT:
The supplied evidence supports the proposed action and there is no
material contradiction.

CHALLENGE:
The evidence is insufficient, uncertain or mixed to establish that
the proposed action is justified, but there is no specific substantive
evidence that the proposed action itself is wrong.

REJECT:
The supplied evidence contains specific, substantive, action-specific
evidence showing that the proposed action should NOT be taken.

IMPORTANT:
Lack of supporting evidence is NOT evidence against the action.

For BUY MORE:
- Strong evidence supporting the investment case can justify ACCEPT.
- Weak or incomplete evidence normally means CHALLENGE.
- Concrete bearish evidence directly inconsistent with adding capital
  can justify REJECT.

Return ONLY JSON:

{
  "review_decision": "ACCEPT | CHALLENGE | REJECT",
  "confidence": 1-100,
  "challenge": true | false,
  "reason": "one or two concise evidence-based sentences"
}

The challenge field MUST be true only for CHALLENGE.
"""


# ============================================================
# Prompt B
# ============================================================

PROMPT_B = """
Review this portfolio action using ONLY the supplied evidence.

ACTION: BUY MORE

ACCEPT = evidence supports BUY MORE and there is no contradiction.

CHALLENGE = evidence is insufficient, mixed or uncertain, but there
is no concrete evidence that BUY MORE is wrong.

REJECT = there is concrete, substantive evidence that BUY MORE should
NOT be taken.

CRITICAL:
Insufficient evidence -> CHALLENGE.
Lack of evidence -> CHALLENGE.
Low confidence alone -> CHALLENGE.
A different preferred action alone -> CHALLENGE.

REJECT requires affirmative evidence against BUY MORE.

Return ONLY JSON:

{
  "review_decision": "ACCEPT | CHALLENGE | REJECT",
  "confidence": 1-100,
  "challenge": true | false,
  "reason": "one or two concise evidence-based sentences"
}
"""


# ============================================================
# Ollama
# ============================================================

def call_ollama(
    prompt: str,
    evidence: dict[str, Any],
) -> tuple[dict[str, Any], float]:

    full_prompt = (
        prompt
        + "\n\nSUPPLIED EVIDENCE:\n"
        + json.dumps(evidence, indent=2)
    )

    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a disciplined portfolio governance reviewer. "
                    "Return JSON only."
                ),
            },
            {
                "role": "user",
                "content": full_prompt,
            },
        ],
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0,
            "num_predict": 200,
        },
    }

    started = time.perf_counter()

    response = requests.post(
        OLLAMA_URL,
        json=payload,
        timeout=TIMEOUT,
    )

    elapsed = time.perf_counter() - started

    response.raise_for_status()

    content = response.json().get("message", {}).get("content", "")

    if not content:
        raise ValueError("Ollama returned an empty response")

    return json.loads(content.strip()), elapsed


# ============================================================
# Production governance classification
#
# This deliberately mirrors the semantic rule now implemented
# in agents/ai_portfolio_reviewer.py:
#
#   insufficient / weak / mixed -> CHALLENGE
#   affirmative contradiction    -> REJECT
#   otherwise                     -> retain LLM classification
#
# The purpose of this section is to make the distinction between
# RAW LLM behaviour and GOVERNED production behaviour explicit.
# ============================================================

def production_governance_classification(
    raw_response: dict[str, Any],
    evidence: dict[str, Any],
) -> str:
    """Use the real production reviewer semantic governance."""

    decision = {
        "Proposed Action": evidence.get("proposed_action", "HOLD"),
    }

    candidate = dict(evidence)

    governed = _normalise_llm_response(
        llm_response=raw_response,
        candidate=candidate,
        decision=decision,
    )

    return str(
        governed.get("Review Decision")
        or governed.get("LLM Assessment")
        or "CHALLENGE"
    ).strip().upper()


# ============================================================
# Main
# ============================================================

print("=" * 80)
print("CONTROLLED LLM REVIEWER BEHAVIOUR TEST")
print("=" * 80)
print()
print(f"Model: {OLLAMA_MODEL}")
print(f"URL  : {OLLAMA_URL}")
print()
print("Expected gold-standard outcomes:")
print("  STRONG BUY MORE     -> ACCEPT")
print("  WEAK BUY MORE       -> CHALLENGE")
print("  CLEAR CONTRADICTION -> REJECT")
print()
print("=" * 80)
print("RAW LLM BEHAVIOUR")
print("=" * 80)

raw_results = {}

for prompt_name, prompt in (
    ("A = GOVERNANCE ANALYTICAL PROMPT", PROMPT_A),
    ("B = MINIMAL ANALYTICAL PROMPT", PROMPT_B),
):

    print()
    print(prompt_name)
    print("-" * 80)

    raw_results[prompt_name] = {}

    for case in TEST_CASES:

        response, elapsed = call_ollama(
            prompt,
            case["evidence"],
        )

        decision = str(
            response.get("review_decision", "UNKNOWN")
        ).upper()

        raw_results[prompt_name][case["name"]] = {
            "response": response,
            "time": elapsed,
            "decision": decision,
        }

        print()
        print(case["name"])
        print(f"Expected : {case['expected']}")
        print(f"Raw LLM : {decision}")
        print(f"Confidence: {response.get('confidence')}")
        print(f"Time     : {elapsed:.2f}s")
        print(f"Reason   : {response.get('reason', '')}")


print()
print("=" * 80)
print("PRODUCTION GOVERNANCE CLASSIFICATION")
print("=" * 80)
print()
print("The raw LLM classification is NOT authoritative.")
print("Python applies the deterministic semantic governance rule.")
print()

all_passed = True

for prompt_name, cases in raw_results.items():

    print(prompt_name)
    print("-" * 80)

    for case in TEST_CASES:

        name = case["name"]
        expected = case["expected"]

        raw_response = cases[name]["response"]

        governed = production_governance_classification(
            raw_response,
            case["evidence"],
        )

        passed = governed == expected

        if not passed:
            all_passed = False

        print()
        print(name)
        print(f"Expected              : {expected}")
        print(
            f"Raw LLM classification: "
            f"{cases[name]['decision']}"
        )
        print(
            f"Governed classification: "
            f"{governed}"
        )
        print(
            "RESULT                : "
            + ("PASS" if passed else "FAIL")
        )

        if not passed:
            print(
                f"  !! EXPECTED {expected}, GOT {governed}"
            )

    print()


print("=" * 80)
print("FINAL RESULT")
print("=" * 80)

if all_passed:
    print()
    print("PASS: All three gold-standard cases are correctly")
    print("classified after deterministic governance.")
else:
    print()
    print("FAIL: One or more cases were not correctly classified.")
    print("Inspect the raw LLM output and governed classification above.")

print()
print("IMPORTANT:")
print("Raw LLM behaviour measures model quality.")
print("Governed classification measures production safety.")
print("The deterministic governance layer remains authoritative.")
print()
print("=" * 80)
