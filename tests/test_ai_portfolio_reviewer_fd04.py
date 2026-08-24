"""
FD-04 tests for the AI Portfolio Reviewer.

Purpose
-------
Verify that malformed or invalid Ollama reviewer output is retried once,
then safely converted into a governed reviewer failure if the retry also
fails. Provider failures such as timeouts must remain distinct from malformed
JSON failures and must not be retried as if they were model opinions.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch

import requests


from pathlib import Path
import importlib.util

PROJECT_ROOT = Path(__file__).resolve().parents[1]

MODULE_PATH = (
    PROJECT_ROOT
    / "agents"
    / "ai_portfolio_reviewer.py"
)

spec = importlib.util.spec_from_file_location(
    "ai_portfolio_reviewer_fd04",
    MODULE_PATH,
)

assert spec is not None
assert spec.loader is not None
reviewer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reviewer)



def _case():
    candidate = {
        "ticker": "CA.PA",
        "asset_type": "STOCK",
        "ownership": {
            "owned": True,
            "quantity": 10,
            "allocation_pct": 0.81,
            "sector": "Consumer Defensive",
        },
        "analysis": {
            "investment_score": 18,
            "technical_score": 12,
            "quality_score": 25,
            "growth_score": 17,
            "signal": "SELL",
        },
        "rules_based_decision": {
            "action": "SELL",
        },
    }

    portfolio = {
        "portfolio": {
            "total_market_value": 100000,
            "cash": 5000,
            "largest_position_pct": 16.97,
            "largest_position_ticker": "NVDA",
            "stock_count": 21,
            "etf_count": 3,
            "sector_count": 8,
        }
    }

    decision = {
        "Proposed Action": "SELL",
        "Evidence Score": 95.44,
        "Evidence Strength": "VERY STRONG",
        "Decision Support": "SUPPORTED",
        "Confidence": 89.66,
    }

    return candidate, portfolio, decision



def _valid_response():
    return {
        "review_decision": "ACCEPT",
        "confidence": 91,
        "challenge": False,
        "reason": "The supplied evidence supports the proposed SELL action.",
    }



def test_malformed_first_response_is_retried_and_valid_second_response_is_used():
    candidate, portfolio, decision = _case()

    malformed = ValueError("Ollama returned malformed JSON")

    with patch.object(
        reviewer,
        "call_ollama",
        side_effect=[malformed, _valid_response()],
    ) as mock_call:
        result = reviewer.review_ai_decision(
            candidate,
            portfolio,
            decision,
        )

    assert mock_call.call_count == 2
    assert result["Ticker"] == "CA.PA"
    assert result["LLM Assessment"] == "ACCEPT"
    assert result["LLM Decision"] == "ACCEPT"
    assert result["LLM Confidence"] == 91
    assert result["Reviewer Status"] == "LLM REVIEW RETRIED"
    assert result["Proposed Action"] == "SELL"



def test_two_malformed_responses_become_governed_failure():
    candidate, portfolio, decision = _case()

    first = ValueError("Expecting ',' delimiter: line 32 column 27")
    second = ValueError(
        "Expecting property name enclosed in double quotes: "
        "line 29 column 27"
    )

    with patch.object(
        reviewer,
        "call_ollama",
        side_effect=[first, second],
    ) as mock_call:
        result = reviewer.review_ai_decision(
            candidate,
            portfolio,
            decision,
        )

    assert mock_call.call_count == 2
    assert result["Ticker"] == "CA.PA"
    assert result["LLM Assessment"] == "UNAVAILABLE"
    assert result["LLM Decision"] == "UNAVAILABLE"
    assert result["Review Decision"] == "UNAVAILABLE"
    assert result["LLM Confidence"] == 0.0
    assert result["Reviewer Status"] == "LLM REVIEW FAILED"
    assert result["Proposed Action"] == "SELL"
    assert result["Challenge"] is False
    assert "failed JSON validation after retry" in result["LLM Reason"]



def test_provider_timeout_is_not_retried_as_json_failure():
    candidate, portfolio, decision = _case()

    timeout = requests.exceptions.Timeout("timed out")

    with patch.object(
        reviewer,
        "call_ollama",
        side_effect=timeout,
    ) as mock_call:
        result = reviewer.review_ai_decision(
            candidate,
            portfolio,
            decision,
        )

    assert mock_call.call_count == 1
    assert result["LLM Assessment"] == "UNAVAILABLE"
    assert result["Review Decision"] == "UNAVAILABLE"
    assert result["Reviewer Status"] == "LLM UNAVAILABLE"
    assert result["LLM Confidence"] == 0.0
    assert result["Proposed Action"] == "SELL"
    assert "timed out" in result["LLM Reason"]



def test_invalid_reviewer_contract_is_retried():
    candidate, portfolio, decision = _case()

    invalid = {
        "review_decision": "MAYBE",
        "confidence": 91,
        "challenge": False,
        "reason": "Invalid decision value.",
    }

    with patch.object(
        reviewer,
        "call_ollama",
        side_effect=[ValueError("invalid review_decision"), _valid_response()],
    ) as mock_call:
        result = reviewer.review_ai_decision(
            candidate,
            portfolio,
            decision,
        )

    assert mock_call.call_count == 2
    assert result["LLM Assessment"] == "ACCEPT"
    assert result["Reviewer Status"] == "LLM REVIEW RETRIED"


if __name__ == "__main__":
    import pytest

    raise SystemExit(
        pytest.main([__file__, "-q"])
    )
