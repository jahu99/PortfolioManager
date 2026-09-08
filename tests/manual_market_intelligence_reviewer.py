"""
Manual Market & Event Intelligence Reviewer Test

Purpose
-------
Verify that Market & Event Intelligence:

1. Reaches the AI Portfolio Reviewer.
2. Appears in the generated prompt.
3. Can materially influence the LLM review when appropriate.

This is a manual smoke test and does not modify portfolio data,
deterministic scores, evidence scores or governance configuration.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


# ============================================================
# Project path
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from agents.ai_portfolio_reviewer import (
    build_review_prompt,
    review_ai_decision,
)


# ============================================================
# Test candidate
# ============================================================

candidate = {
    "Ticker": "TEST",
    "Name": "Market Intelligence Test Company",
    "Asset Type": "STOCK",
    "Held?": True,
    "Sector": "Technology",

    "Proposed Action": "BUY MORE",

    "analysis": {
        "investment_score": 82.0,
        "technical_score": 78.0,
        "quality_score": 80.0,
        "growth_score": 85.0,
        "risk_score": 55.0,
        "signal": "BUY",
        "rsi": 62.0,
    },

    "rules": {
        "confidence": 82.0,
        "reason": (
            "Strong investment and growth characteristics with "
            "supportive technical evidence."
        ),
    },

    "market_intelligence": {
        "Ticker": "TEST",

        "earnings_context": (
            "Company issued guidance materially below analyst expectations."
        ),

        "news_context": (
            "Recent company announcement indicates a significant "
            "increase in expected operating costs."
        ),

        "market_context": (
            "Sector conditions remain broadly supportive."
        ),

        "sentiment": "NEGATIVE",

        "material_event": True,

        "event_risk": (
            "Negative guidance may materially weaken the near-term "
            "investment case."
        ),
    },
}


# ============================================================
# Portfolio context
# ============================================================

portfolio = {
    "portfolio": {
        "total_market_value": 1000.0,
        "cash": 50.0,
        "largest_position_pct": 15.0,
        "largest_position_ticker": "NVDA",
        "stock_count": 10,
        "etf_count": 3,
        "sector_count": 5,
    }
}


# ============================================================
# Deterministic decision
# ============================================================

decision = {
    "Proposed Action": "BUY MORE",
    "Confidence": 82.0,
    "Reason": (
        "Strong investment and growth characteristics with "
        "supportive technical evidence."
    ),
    "Evidence Assessment": {
        "Evidence Score": 80.0,
        "Evidence Strength": "STRONG",
        "Evidence Support": "SUPPORTIVE",
    },
}


# ============================================================
# Prompt inspection
# ============================================================

def check_prompt(prompt: str) -> None:
    """
    Verify that Market & Event Intelligence reached the prompt.
    """

    print("\n============================================================")
    print("MARKET INTELLIGENCE PROMPT CHECK")
    print("============================================================")

    required_text = [
        "MARKET & EVENT INTELLIGENCE",
        "guidance materially below analyst expectations",
        "significant increase in expected operating costs",
        "Negative guidance may materially weaken",
    ]

    all_found = True

    for text in required_text:

        found = text in prompt

        status = "FOUND" if found else "MISSING"

        print(f"{status}: {text}")

        if not found:
            all_found = False

    if not all_found:

        raise AssertionError(
            "Market intelligence did not fully reach the LLM prompt."
        )

    print("\nPROMPT CHECK: PASSED")


# ============================================================
# Main test
# ============================================================

def main() -> None:

    print("\n============================================================")
    print("MARKET & EVENT INTELLIGENCE REVIEWER TEST")
    print("============================================================")

    # --------------------------------------------------------
    # Step 1: Build prompt
    # --------------------------------------------------------

    print("\nSTEP 1: Building review prompt...")

    prompt = build_review_prompt(
        candidate=candidate,
        portfolio=portfolio,
        decision=decision,
    )

    # --------------------------------------------------------
    # Step 2: Verify intelligence reached prompt
    # --------------------------------------------------------

    check_prompt(prompt)

    # --------------------------------------------------------
    # Step 3: Show intelligence payload
    # --------------------------------------------------------

    print("\n============================================================")
    print("MARKET INTELLIGENCE PAYLOAD")
    print("============================================================")

    print(
        json.dumps(
            candidate["market_intelligence"],
            indent=2,
        )
    )

    # --------------------------------------------------------
    # Step 4: Run reviewer
    # --------------------------------------------------------

    print("\n============================================================")
    print("RUNNING OLLAMA REVIEW")
    print("============================================================")

    review = review_ai_decision(
        candidate=candidate,
        portfolio=portfolio,
        decision=decision,
    )

    # --------------------------------------------------------
    # Step 5: Show result
    # --------------------------------------------------------

    print("\n============================================================")
    print("LLM REVIEW RESULT")
    print("============================================================")

    print(
        json.dumps(
            review,
            indent=2,
            default=str,
        )
    )

    # --------------------------------------------------------
    # Step 6: Interpretation
    # --------------------------------------------------------

    review_decision = str(
        review.get(
            "Review Decision",
            review.get(
                "LLM Decision",
                review.get(
                    "LLM Assessment",
                    "",
                ),
            ),
        )
    ).upper()

    reason = str(
        review.get(
            "Reason",
            review.get(
                "LLM Reason",
                "",
            ),
        )
    )

  
    print("\n============================================================")
    print("MARKET INTELLIGENCE BEHAVIOUR CHECK")
    print("============================================================")

    print(f"Review Decision: {review_decision}")
    print(f"Reason: {reason}")

    print(
        "\nExpected behaviour:"
    )

    print(
        "- The deterministic proposal is BUY MORE."
    )

    print(
        "- Market intelligence contains materially negative "
        "guidance and increased cost risk."
    )

    print(
        "- The reviewer should explicitly consider this context."
    )

    print(
        "- A CHALLENGE or REJECT may therefore be reasonable, "
        "depending on the model's assessment."
    )

    print(
        "\nIMPORTANT:"
    )

    print(
        "The test does not require a specific review decision."
    )

    print(
        "The key requirement is that the reviewer reason reflects "
        "the supplied Market & Event Intelligence when it is "
        "material to the proposed action."
    )


if __name__ == "__main__":
    main()
