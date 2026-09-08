# tests/manual_market_intelligence_ab_test.py

import json
import sys
from pathlib import Path


# ============================================================
# Ensure project root is importable when running:
#
# python tests/manual_market_intelligence_ab_test.py
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from agents.ai_portfolio_reviewer import (
    review_ai_decision,
    build_review_prompt,
)


# ============================================================
# Helpers
# ============================================================

def print_section(title: str):
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72 + "\n")


def print_json(value):
    print(json.dumps(value, indent=2, default=str))


def summarise_result(result: dict) -> dict:
    if not isinstance(result, dict):
        return {
            "review_decision": None,
            "llm_review": None,
            "llm_assessment": None,
            "confidence": None,
            "reason": None,
        }

    return {
        "review_decision": result.get("Review Decision"),
        "llm_review": result.get("LLM Review"),
        "llm_assessment": result.get("LLM Assessment"),
        "confidence": result.get("LLM Confidence"),
        "reason": result.get("LLM Reason"),
    }


# ============================================================
# Test portfolio
# ============================================================

portfolio = {
    "portfolio": {
        "total_market_value": 1000.0,
        "cash": 100.0,
        "largest_position_pct": 20.0,
        "largest_position_ticker": "NVDA",
        "stock_count": 10,
        "etf_count": 3,
        "sector_count": 5,
    }
}


# ============================================================
# Deterministic decision
#
# BUY MORE is deliberately supported by the deterministic
# evidence so that the contextual evidence has something
# meaningful to challenge.
# ============================================================

decision = {
    "Proposed Action": "BUY MORE",
    "Confidence": 85.0,
    "Reason": (
        "Strong investment, technical, quality and growth evidence "
        "supports adding capital to the existing position."
    ),
}


# ============================================================
# Candidate A — BASELINE
#
# No Market & Event Intelligence.
# ============================================================

baseline_candidate = {
    "Ticker": "TEST",
    "Name": "Test Company",
    "Asset Type": "STOCK",
    "Held?": True,
    "Sector": "Technology",

    "Proposed Action": "BUY MORE",

    "Investment Score": 92.0,
    "Technical Score": 88.0,
    "Quality Score": 90.0,
    "Growth Score": 94.0,
    "Risk Score": 25.0,

    "Signal": "BUY",

    "Current Price": 110.0,
    "MA50": 105.0,
    "MA200": 95.0,
    "RSI": 60.0,

    "Confidence": 85.0,

    "Technical Reasons": [
        "Price is above MA50.",
        "Price is above MA200.",
        "Strong positive momentum.",
    ],

    "Technical Risks": [],

    "Recommendation Risks": [],

    "market_intelligence": None,
}


# ============================================================
# Candidate B — CONTEXTUAL
#
# Same deterministic evidence as A, but with materially
# negative Market & Event Intelligence.
#
# IMPORTANT:
# The distinctive phrases below are deliberately explicit so
# we can determine whether the model actually considered them.
# ============================================================

contextual_candidate = dict(baseline_candidate)

contextual_candidate["market_intelligence"] = {
    "Ticker": "TEST",

    "Earnings Context": (
        "LATEST_GUIDANCE_ALERT: Management materially reduced "
        "forward earnings guidance."
    ),

    "Company News": [
        (
            "LATEST_GUIDANCE_ALERT: Management reduced forward "
            "earnings guidance."
        ),
        (
            "COST_PRESSURE_ALERT: Management reported materially "
            "increasing operating costs and margin pressure."
        ),
    ],

    "Guidance": (
        "LATEST_GUIDANCE_ALERT: Forward earnings guidance was "
        "materially reduced."
    ),

    "Risk Context": [
        (
            "COST_PRESSURE_ALERT: Operating costs are increasing "
            "and margin pressure is expected."
        ),
    ],

    "Sentiment": "NEGATIVE",

    "Summary": (
        "LATEST_GUIDANCE_ALERT and COST_PRESSURE_ALERT represent "
        "material near-term risks to the investment case."
    ),

    "Source": "MANUAL A/B TEST",
    "Timestamp": "2026-09-06",
}


# ============================================================
# 1. PROMPT INSPECTION
#
# First prove that the contextual intelligence is physically
# present in the prompt supplied to the LLM.
# ============================================================

print_section("A — PROMPT DELIVERY CHECK")

baseline_prompt = build_review_prompt(
    candidate=baseline_candidate,
    portfolio=portfolio,
    decision=decision,
)

contextual_prompt = build_review_prompt(
    candidate=contextual_candidate,
    portfolio=portfolio,
    decision=decision,
)

baseline_has_market_intelligence = (
    "LATEST_GUIDANCE_ALERT" in baseline_prompt
    or "COST_PRESSURE_ALERT" in baseline_prompt
)

contextual_has_guidance_alert = (
    "LATEST_GUIDANCE_ALERT" in contextual_prompt
)

contextual_has_cost_alert = (
    "COST_PRESSURE_ALERT" in contextual_prompt
)

print(
    "Baseline contains contextual intelligence:",
    baseline_has_market_intelligence,
)

print(
    "Contextual prompt contains LATEST_GUIDANCE_ALERT:",
    contextual_has_guidance_alert,
)

print(
    "Contextual prompt contains COST_PRESSURE_ALERT:",
    contextual_has_cost_alert,
)


if not contextual_has_guidance_alert or not contextual_has_cost_alert:

    print("\nFAIL: Market & Event Intelligence is NOT reaching the LLM prompt.")

    print_section("CONTEXTUAL PROMPT")

    print(contextual_prompt)

    raise SystemExit(1)


print(
    "\nPASS: Market & Event Intelligence is present in the prompt "
    "supplied to the LLM."
)


# ============================================================
# 2. RUN BASELINE REVIEW
# ============================================================

print_section("A — BASELINE REVIEW")

baseline_result = review_ai_decision(
    candidate=baseline_candidate,
    portfolio=portfolio,
    decision=decision,
)

print_json(baseline_result)


# ============================================================
# 3. RUN CONTEXTUAL REVIEW
# ============================================================

print_section("B — REVIEW WITH NEGATIVE MARKET INTELLIGENCE")

contextual_result = review_ai_decision(
    candidate=contextual_candidate,
    portfolio=portfolio,
    decision=decision,
)

print_json(contextual_result)


# ============================================================
# 4. A/B COMPARISON
# ============================================================

baseline_summary = summarise_result(baseline_result)

contextual_summary = summarise_result(contextual_result)

print_section("MARKET & EVENT INTELLIGENCE A/B COMPARISON")

print("A — BASELINE\n")

print_json(baseline_summary)

print("\nB — WITH NEGATIVE MARKET INTELLIGENCE\n")

print_json(contextual_summary)


# ============================================================
# 5. VALIDATION
#
# We distinguish two separate things:
#
# 1. DELIVERY:
#    Did the intelligence reach the prompt?
#
# 2. BEHAVIOUR:
#    Did the model's reasoning demonstrate that it considered
#    the supplied intelligence?
#
# The review decision itself does NOT have to change.
# ============================================================

print_section("VALIDATION")

contextual_reason = str(
    contextual_summary.get("reason") or ""
).lower()

contextual_decision = str(
    contextual_summary.get("review_decision") or ""
).upper()

baseline_decision = str(
    baseline_summary.get("review_decision") or ""
).upper()


market_terms = [
    "guidance",
    "earnings",
    "cost",
    "margin",
    "operating",
    "negative",
    "pressure",
    "near-term",
]


referenced_market_context = any(
    term in contextual_reason
    for term in market_terms
)


decision_changed = (
    contextual_decision != baseline_decision
)


print(
    "Baseline Review Decision:",
    baseline_decision,
)

print(
    "Contextual Review Decision:",
    contextual_decision,
)

print(
    "Contextual reason references market context:",
    referenced_market_context,
)

print(
    "Review decision changed:",
    decision_changed,
)


# ============================================================
# Final outcome
# ============================================================

if referenced_market_context:

    print(
        "\nPASS: The contextual reviewer explicitly referenced "
        "Market & Event Intelligence in its reasoning."
    )

    print(
        "\nCONCLUSION: Market & Event Intelligence was both "
        "delivered to and considered by the LLM reviewer."
    )

    raise SystemExit(0)


print(
    "\nWARNING: Market & Event Intelligence was successfully "
    "delivered to the LLM prompt, but the returned reason did "
    "not demonstrate that the model explicitly considered it."
)

print(
    "\nThis does NOT prove the data wiring is broken."
)

print(
    "The prompt delivery check above proves whether the contextual "
    "data reached the model."
)

print(
    "It indicates that the reviewer prompt/governance instructions "
    "may need strengthening to require material market intelligence "
    "to be explicitly weighed when present."
)

raise SystemExit(2)