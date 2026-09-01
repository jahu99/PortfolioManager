"""
FD-05 tests for asset-specific reviewer evidence and semantic guardrails.
"""
from __future__ import annotations
from pathlib import Path
import importlib.util



REVIEWER_PATH = Path(__file__).resolve().parents[1] / "agents" / "ai_portfolio_reviewer.py"

spec = importlib.util.spec_from_file_location(
    "ai_portfolio_reviewer",
    REVIEWER_PATH,
)



import importlib.util
from pathlib import Path
from unittest.mock import patch


reviewer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reviewer)

assert spec is not None
assert spec.loader is not None

def _etf_case():
    candidate = {
        "ticker": "IWDA.L",
        "asset_type": "ETF",
        "ownership": {"owned": True, "allocation_pct": 10.11},
        "analysis": {
            "etf_score": 100,
            "etf_signal": "BUY",
            "investment_score": 0,
            "technical_score": 0,
            "quality_score": 0,
            "growth_score": 0,
        },
        "rules_based_decision": {"action": "HOLD", "confidence": 70},
        "recommendation_intelligence": {
            "historical_signal_observations": 1,
            "score_bucket_observations": 0,
        },
    }
    portfolio = {"portfolio": {"largest_position_pct": 15.92}}
    decision = {"Proposed Action": "HOLD", "Evidence Score": 69.61, "Confidence": 62.9}
    return candidate, portfolio, decision


def test_etf_payload_contains_only_etf_metrics():
    candidate, portfolio, decision = _etf_case()
    payload = reviewer.build_review_payload(candidate, portfolio, decision)
    compact = payload["candidate"]

    assert compact["asset_type"] == "ETF"
    assert compact["etf_score"] == 100
    assert compact["etf_signal"] == "BUY"
    assert "investment_score" not in compact
    assert "technical_score" not in compact
    assert "quality_score" not in compact
    assert "growth_score" not in compact
    assert "current_price" not in compact
    assert "ma50" not in compact
    assert "ma200" not in compact
    assert "rsi" not in compact


def test_etf_semantic_guard_rejects_stock_metric_in_reason():
    candidate, _, _ = _etf_case()
    response = {
        "review_decision": "REJECT",
        "confidence": 90,
        "challenge": True,
        "reason": "The investment score is zero, so HOLD is not supported.",
    }

    try:
        reviewer._validate_review_semantics(response, candidate)
    except ValueError as exc:
        assert "non-applicable stock metric" in str(exc)
    else:
        raise AssertionError("Expected ETF semantic guard to reject stock metric")


def test_etf_semantic_failure_is_retried_and_valid_second_response_is_used():
    candidate, portfolio, decision = _etf_case()
    invalid = {
        "review_decision": "REJECT",
        "confidence": 90,
        "challenge": True,
        "reason": "The ETF investment score of 0 contradicts the proposal.",
    }
    valid = {
        "review_decision": "ACCEPT",
        "confidence": 82,
        "challenge": False,
        "reason": "The ETF Score of 100 and BUY signal support the existing position, while the current allocation is already meaningful.",
    }

    with patch.object(reviewer, "call_ollama", side_effect=[invalid, valid]) as mock_call:
        result = reviewer.review_ai_decision(candidate, portfolio, decision)

    assert mock_call.call_count == 2
    assert result["LLM Assessment"] == "ACCEPT"
    assert result["LLM Confidence"] == 82
    assert result["Reviewer Status"] == "LLM REVIEW RETRIED"


def test_etf_semantic_failure_twice_becomes_unavailable():
    candidate, portfolio, decision = _etf_case()
    invalid = {
        "review_decision": "REJECT",
        "confidence": 90,
        "challenge": True,
        "reason": "The technical score is below the investment score.",
    }

    with patch.object(reviewer, "call_ollama", side_effect=[invalid, invalid]) as mock_call:
        result = reviewer.review_ai_decision(candidate, portfolio, decision)

    assert mock_call.call_count == 2
    assert result["LLM Assessment"] == "UNAVAILABLE"
    assert result["LLM Confidence"] == 0.0
    assert result["Reviewer Status"] == "LLM REVIEW FAILED"
    assert "failed JSON validation after retry" in result["LLM Reason"]
