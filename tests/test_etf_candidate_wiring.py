"""
Test ETF candidate wiring into the final portfolio decision engine.

Purpose
-------
Verify that ETF Score and ETF Signal survive the construction of the
candidate/base row that is passed into build_final_result().

This test deliberately stops before the full portfolio pipeline so that
we can identify whether ETF data is being lost before or during final
result construction.
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
    
from analysis.final_portfolio_decision import build_final_result


def assert_equal(actual, expected, label):
    if actual != expected:
        raise AssertionError(
            f"{label}: expected {expected!r}, got {actual!r}"
        )


def main():
    print()
    print("=== ETF CANDIDATE WIRING TEST ===")
    print()

    candidate = {
        "ticker": "IWDA.L",
        "asset_type": "ETF",
        "Ticker": "IWDA.L",
        "Asset Type": "ETF",
        "ETF Score": 82.5,
        "ETF Signal": "BUY",
        "Investment Score": 0,
        "Signal": "",
        "Proposed Action": "HOLD",
        "Sector": "ETF",
    }

    decision = {
        "Ticker": "IWDA.L",
        "Asset Type": "ETF",
        "ETF Score": 82.5,
        "ETF Signal": "BUY",
        "Investment Score": 0,
        "Signal": "",
        "Proposed Action": "HOLD",
    }

    chain = {
        "deterministic": decision,
        "explanation": {},
        "review": {
            "LLM Assessment": "ACCEPT",
            "LLM Confidence": 85,
            "LLM Reason": "ETF evidence supports the decision.",
            "Reviewer Status": "LLM REVIEW COMPLETE",
        },
        "reconciliation": {
            "Reconciled Decision": "HOLD",
            "Reconciliation": "SUPPORTED",
            "Reconciliation Reason": "ETF evidence supports HOLD.",
        },
    }

    result = build_final_result(
        base_row={
            "Ticker": "IWDA.L",
            "Asset Type": "ETF",
            "Existing Holding": True,
            "Quantity": 1,
            "Market Value": 100,
            "Allocation %": 10,
            "Investment Score": 0,
            "ETF Score": candidate["ETF Score"],
            "ETF Signal": candidate["ETF Signal"],
            "Signal": "",
            "Sector": "ETF",
            "Proposed Action": "HOLD",
        },
        chain=chain,
    )

    print("Ticker:", result.get("Ticker"))
    print("Asset Type:", result.get("Asset Type"))
    print("Investment Score:", result.get("Investment Score"))
    print("ETF Score:", result.get("ETF Score"))
    print("Signal:", repr(result.get("Signal")))
    print("ETF Signal:", repr(result.get("ETF Signal")))
    print()

    assert_equal(result.get("Asset Type"), "ETF", "Asset Type")
    assert_equal(result.get("Investment Score"), 0.0, "Investment Score")
    assert_equal(result.get("ETF Score"), 82.5, "ETF Score")
    assert_equal(result.get("Signal"), "", "Signal")
    assert_equal(result.get("ETF Signal"), "BUY", "ETF Signal")

    print("PASS: ETF Score and ETF Signal survive candidate -> final-result wiring.")


if __name__ == "__main__":
    main()
