"""
Behavioural tests for the AI Portfolio Reviewer.

These tests verify how the reviewer handles strong, weak and contradictory
deterministic proposals without depending on a live Ollama model.
"""

from __future__ import annotations

from pathlib import Path
import importlib.util
from unittest.mock import patch


REVIEWER_PATH = (
    Path(__file__).resolve().parents[1]
    / "agents"
    / "ai_portfolio_reviewer.py"
)

spec = importlib.util.spec_from_file_location(
    "ai_portfolio_reviewer",
    REVIEWER_PATH,
)

reviewer = importlib.util.module_from_spec(spec)
assert spec is not None
assert spec.loader is not None
spec.loader.exec_module(reviewer)


def _stock_candidate(
    *,
    action: str = "BUY MORE",
    allocation: float = 2.0,
    investment_score: float = 90.0,
    signal: str = "BUY",
):
    return {
        "ticker": "TEST",
        "asset_type": "STOCK",
        "signal": signal,
        "ownership": {
            "owned": True,
            "allocation_pct": allocation,
        },
        "analysis": {
            "investment_score": investment_score,
            "technical_score": 85,
            "quality_score": 90,
            "growth_score": 90,
            "signal": signal,
            "risk_score": 20,
        },
        "rules_based_decision": {
            "action": action,
            "confidence": 85,
            "reason": "Deterministic proposal.",
        },
        "recommendation_intelligence": {
            "historical_signal_observations": 50,
            "historical_signal_win_rate_pct": 75,
            "historical_signal_average_return_pct": 12,
            "historical_signal_reliability": "HIGH",
            "score_bucket_observations": 50,
            "score_bucket_win_rate_pct": 75,
            "learning_adjusted_score": 90,
        },
    }


def _portfolio():
    return {
        "portfolio": {
            "total_market_value": 100000,
            "cash": 10000,
            "largest_position_pct": 12,
            "largest_position_ticker": "NVDA",
            "stock_count": 20,
            "etf_count": 3,
            "sector_count": 8,
        }
    }


def _decision(
    *,
    action: str = "BUY MORE",
    evidence_score: float = 80,
    confidence: float = 85,
):
    return {
        "Proposed Action": action,
        "Evidence Score": evidence_score,
        "Evidence Strength": "STRONG",
        "Decision Support": "SUPPORTED",
        "Confidence": confidence,
        "Reason": "Deterministic proposal.",
    }


def test_strong_buy_more_response_is_accepted():
    candidate = _stock_candidate()
    portfolio = _portfolio()
    decision = _decision()

    response = {
        "review_decision": "ACCEPT",
        "confidence": 90,
        "challenge": False,
        "reason": (
            "The strong Investment Score, BUY signal and low allocation "
            "support incremental capital."
        ),
    }

    with patch.object(
        reviewer,
        "call_ollama",
        return_value=response,
    ):
        result = reviewer.review_ai_decision(
            candidate,
            portfolio,
            decision,
        )

    assert result["LLM Assessment"] == "ACCEPT"
    assert result["LLM Review"] == "ACCEPT"
    assert result["LLM Confidence"] == 90


def test_weak_buy_more_response_can_be_challenged():
    candidate = _stock_candidate(
        allocation=9.0,
        investment_score=68,
        signal="HOLD",
    )
    portfolio = _portfolio()
    decision = _decision(
        evidence_score=55,
        confidence=58,
    )

    response = {
        "review_decision": "CHALLENGE",
        "confidence": 88,
        "challenge": True,
        "reason": (
            "The existing allocation is already meaningful and the supplied "
            "score and HOLD signal do not establish a strong incremental "
            "case for BUY MORE versus HOLD."
        ),
    }

    with patch.object(
        reviewer,
        "call_ollama",
        return_value=response,
    ):
        result = reviewer.review_ai_decision(
            candidate,
            portfolio,
            decision,
        )

    assert result["LLM Assessment"] == "CHALLENGE"
    assert result["LLM Review"] == "CHALLENGE"
    assert result["LLM Confidence"] == 88


def test_clear_contradiction_can_be_rejected():
    candidate = _stock_candidate(
        allocation=10.0,
        investment_score=25,
        signal="SELL",
    )
    portfolio = _portfolio()
    decision = _decision(
        action="BUY MORE",
        evidence_score=30,
        confidence=35,
    )

    response = {
        "review_decision": "REJECT",
        "confidence": 95,
        "challenge": True,
        "reason": (
            "The supplied Investment Score and SELL signal materially "
            "contradict the proposed action."
        ),
    }

    with patch.object(
        reviewer,
        "call_ollama",
        return_value=response,
    ):
        result = reviewer.review_ai_decision(
            candidate,
            portfolio,
            decision,
        )

    assert result["LLM Assessment"] == "REJECT"
    assert result["LLM Review"] == "REJECT"
    assert result["LLM Confidence"] == 95
