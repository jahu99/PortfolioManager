"""
Test ETF Score and ETF Signal through the real AI decision context builder.

This isolates the production boundary between run_governed_chain()
candidate construction and generate_ai_decision().
"""

import os
import sys

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from analysis.final_portfolio_decision import (
    build_ai_decision_context,
)


def main():

    candidate_decisions = [
        {
            "Ticker": "IWDA.L",
            "Recommendation ID": None,
            "Asset Type": "ETF",

            "Action": "HOLD",
            "Reason": "ETF test",
            "Confidence": 80,

            "Existing Holding": True,
            "Quantity": 1.0,
            "Allocation %": 10.0,
            "Sector": "ETF",

            "Investment Score": 0.0,
            "ETF Score": 82.5,
            "Quality Score": 0.0,
            "Growth Score": 0.0,
            "Signal": "",
            "ETF Signal": "BUY",
            "Risk Score": 0.0,
        }
    ]

    portfolio = {
        "holdings": [],
    }

    context = build_ai_decision_context(
        portfolio=portfolio,
        candidate_decisions=candidate_decisions,
        recommendation_intelligence=[],
        capital_allocation=None,
    )

    candidates = context.get("candidates", [])

    assert candidates, (
        "FAIL: build_ai_decision_context() "
        "returned no candidates"
    )

    candidate = candidates[0]
    analysis = candidate.get("analysis", {})

    etf_score = analysis.get("etf_score")
    etf_signal = analysis.get("etf_signal")

    assert etf_score == 82.5, (
        f"FAIL: ETF Score lost or changed: "
        f"{etf_score!r}"
    )

    assert etf_signal == "BUY", (
        f"FAIL: ETF Signal lost or changed: "
        f"{etf_signal!r}"
    )

    print(
        "PASS: ETF Score and ETF Signal survive "
        "build_ai_decision_context()."
    )


if __name__ == "__main__":
    main()
