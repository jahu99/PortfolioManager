"""
Test ETF data wiring into the final portfolio decision.

Purpose
-------
Verify that ETF Score and ETF Signal survive the transition from the
governed candidate/decision data into build_final_result().

This test does NOT run the full portfolio engine and does NOT call Ollama.
It isolates the exact data path that previously lost:

    ETF Score
    ETF Signal
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from analysis.final_portfolio_decision import build_final_result


def test_etf_final_result_wiring():
    """
    ETF Score and ETF Signal must appear correctly in the final result.

    Expected:
        ETF Score  = 100.0
        ETF Signal = BUY
        Investment Score = 0.0
        Signal = ""
    """

    candidate = {
        "ticker": "IWDA.L",
        "asset_type": "ETF",
        "ownership": {
            "owned": True,
            "quantity": 10,
            "market_value": 1000,
            "allocation_pct": 10.0,
            "sector": "ETF",
        },
        "analysis": {
            "investment_score": 0.0,
            "etf_score": 100.0,
            "etf_signal": "BUY",
            "signal": "",
        },
    }

    decision = {
        "Ticker": "IWDA.L",
        "Asset Type": "ETF",
        "Investment Score": 0.0,
        "ETF Score": 100.0,
        "ETF Signal": "BUY",
        "Signal": "",
        "Action": "HOLD",
        "Proposed Action": "HOLD",
        "Reason": "ETF test",
    }

    # ------------------------------------------------------------
    # This reproduces the important candidate_row hand-off.
    # ------------------------------------------------------------

    analysis = candidate["analysis"]
    ownership = candidate["ownership"]

    candidate_row = {
        "Ticker": candidate["ticker"],
        "Asset Type": candidate["asset_type"],
        "Existing Holding": ownership["owned"],
        "Quantity": ownership["quantity"],
        "Market Value": ownership["market_value"],
        "Allocation %": ownership["allocation_pct"],

        "Investment Score": analysis.get(
            "investment_score",
            decision.get("Investment Score", 0),
        ),

        "ETF Score": analysis.get(
            "etf_score",
            candidate.get(
                "ETF Score",
                decision.get("ETF Score", 0),
            ),
        ),

        "ETF Signal": analysis.get(
            "etf_signal",
            candidate.get(
                "ETF Signal",
                decision.get("ETF Signal", ""),
            ),
        ),

        "Signal": analysis.get(
            "signal",
            candidate.get(
                "Signal",
                decision.get("Signal", ""),
            ),
        ),

        "Sector": ownership["sector"],
        "Proposed Action": "HOLD",
        "Original Reason": "ETF test",
    }

    # ------------------------------------------------------------
    # Verify the hand-off BEFORE build_final_result().
    # ------------------------------------------------------------

    assert candidate_row["ETF Score"] == 100.0
    assert candidate_row["ETF Signal"] == "BUY"
    assert candidate_row["Investment Score"] == 0.0
    assert candidate_row["Signal"] == ""

    # ------------------------------------------------------------
    # Run the actual final-result builder.
    #
    # The exact chain structure is deliberately minimal because
    # this test is testing ETF field wiring, not governance.
    # ------------------------------------------------------------

    result = build_final_result(
        base_row=candidate_row,
        chain={
            "deterministic": decision,
            "explanation": {},
            "review": {
                "LLM Assessment": "ACCEPT",
                "LLM Confidence": 85,
                "LLM Reason": "ETF test",
            },
            "reconciliation": {
                "Reconciled Decision": "HOLD",
                "Reconciliation Status": "SUPPORTED",
                "Reconciliation Reason": "ETF test",
            },
            "candidate": candidate,
        },
    )

    # ------------------------------------------------------------
    # Final output assertions.
    # ------------------------------------------------------------

    print()
    print("=== ETF FINAL RESULT WIRING TEST ===")
    print("Ticker:", result.get("Ticker"))
    print("Asset Type:", result.get("Asset Type"))
    print("Investment Score:", result.get("Investment Score"))
    print("ETF Score:", result.get("ETF Score"))
    print("Signal:", repr(result.get("Signal")))
    print("ETF Signal:", repr(result.get("ETF Signal")))

    assert result["Asset Type"] == "ETF"
    assert result["Investment Score"] == 0.0
    assert result["ETF Score"] == 100.0
    assert result["Signal"] == ""
    assert result["ETF Signal"] == "BUY"

    print()
    print("PASS: ETF Score and ETF Signal survive final-result wiring.")


if __name__ == "__main__":
    test_etf_final_result_wiring()
