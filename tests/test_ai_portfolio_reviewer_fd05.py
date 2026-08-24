"""
FD-05 — AI Portfolio Reviewer Governance Calibration Tests

Purpose
-------
Verify that the AI Portfolio Reviewer does not systematically reject
legitimate portfolio changes simply because evidence is not perfect.

FD-05 policy:

    Strong + coherent evidence
        -> ACCEPT

    Missing secondary evidence
        -> reduce confidence, not automatically CHALLENGE

    Material contradiction
        -> CHALLENGE

    Clearly unsupported proposal
        -> REJECT

    HOLD with mixed/weak evidence
        -> ACCEPT

The tests mock Ollama so they are deterministic and do not require
a running Llama model.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


# ============================================================
# Load production reviewer
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

MODULE_PATH = (
    PROJECT_ROOT
    / "agents"
    / "ai_portfolio_reviewer.py"
)

spec = importlib.util.spec_from_file_location(
    "ai_portfolio_reviewer_fd05",
    MODULE_PATH,
)

reviewer = importlib.util.module_from_spec(spec)

assert spec.loader is not None

spec.loader.exec_module(reviewer)


# ============================================================
# Test fixtures
# ============================================================

def make_candidate(
    action: str,
    score: float = 80,
    allocation: float = 2.0,
    owned: bool = True,
) -> dict:
    """
    Build a representative candidate containing coherent evidence.
    """

    return {
        "ticker": "TEST",
        "asset_type": "STOCK",

        "analysis": {
            "investment_score": score,
            "technical_score": 85,
            "quality_score": 82,
            "growth_score": 84,
            "signal": "BUY",

            "price": 100,
            "ma50": 95,
            "ma200": 85,
            "rsi": 62,

            "return_3m": 15,

            "trend": "Strong upward trend",
            "trend_score": 90,
            "momentum_score": 88,
            "volume_score": 82,
            "risk_score": 75,

            "technical_reasons": [
                "Above 50 DMA",
                "Above 200 DMA",
                "Positive momentum",
                "Strong volume confirmation",
            ],

            "technical_risks": [],

            "revenue_growth": 20,
            "profit_margin": 25,
            "return_on_equity": 22,
            "debt_to_equity": 0.4,

            "sector": "Technology",
            "industry": "Software",

            "confidence_score": 85,
        },

        "ownership": {
            "owned": owned,
            "allocation_pct": allocation,
            "quantity": 10,
        },

        "rules_based_decision": {
            "action": action,
        },

        "recommendation_intelligence": {
            "historical_signal_observations": 50,
            "historical_signal_win_rate_pct": 68,
            "historical_signal_average_return_pct": 9,
            "historical_signal_reliability": "STRONG",
            "learning_adjusted_score": score,
        },

        "ai_decision": {
            "Conviction": "HIGH",
            "Conviction Score": 85,
            "Recommended Action": [action],
        },

        "Recommendation Reasons": [
            "Strong technical trend",
            "Strong growth",
            "Strong quality",
        ],

        "Recommendation Risks": [],

        "AI Investment Thesis": [
            "Strong underlying investment case",
        ],

        "AI Risks": [],
    }


def make_portfolio(
    allocation: float = 2.0,
) -> dict:
    """
    Build a representative portfolio context.
    """

    return {
        "portfolio": {
            "total_market_value": 100000,
            "cash": 10000,
            "largest_position_pct": allocation,
            "largest_position_ticker": "TEST",
            "stock_count": 20,
            "etf_count": 3,
            "sector_count": 8,
        }
    }


def make_decision(
    action: str,
) -> dict:
    """
    Build a representative deterministic decision.
    """

    return {
        "Final Decision": action,
        "Proposed Action": action,
        "Evidence Score": 85,
        "Evidence Strength": "STRONG",
        "Decision Support": "SUPPORTED",
        "Confidence": 85,
        "Reason": "Strong and coherent supplied evidence.",
        "Governance Reasons": [],
    }


def mock_ollama_response(
    review_decision: str,
    confidence: int,
    challenge: bool,
    reason: str,
    key_points: list[str] | None = None,
    evidence_gaps: list[str] | None = None,
) -> dict:
    """
    Return a deterministic fake Ollama response.
    """

    return {
        "review_decision": review_decision,
        "confidence": confidence,
        "challenge": challenge,
        "reason": reason,
        "key_points": key_points or [],
        "evidence_gaps": evidence_gaps or [],
    }


# ============================================================
# FD-05.1
# Strong BUY should be ACCEPTED
# ============================================================

def test_strong_buy_is_accepted(monkeypatch):
    """
    A strong BUY with coherent supporting evidence should not be
    rejected merely because the position is currently held.
    """

    candidate = make_candidate(
        action="BUY",
        score=85,
        allocation=2.0,
        owned=True,
    )

    portfolio = make_portfolio(
        allocation=2.0,
    )

    decision = make_decision(
        action="BUY",
    )

    monkeypatch.setattr(
        reviewer,
        "call_ollama",
        lambda prompt: mock_ollama_response(
            review_decision="ACCEPT",
            confidence=88,
            challenge=False,
            reason="Strong and coherent evidence supports BUY.",
            key_points=[
                "Strong technical trend",
                "Strong quality and growth",
                "No material contradiction",
            ],
        ),
    )

    result = reviewer.review_ai_decision(
        candidate,
        portfolio,
        decision,
    )

    assert result["LLM Assessment"] == "ACCEPT"
    assert result["Challenge"] is False
    assert result["LLM Confidence"] == 88


# ============================================================
# FD-05.2
# Strong BUY MORE should be ACCEPTED
# ============================================================

def test_strong_buy_more_is_accepted(monkeypatch):
    """
    BUY MORE should be capable of surviving governance when the
    existing allocation is small and the supplied evidence is strong.
    """

    candidate = make_candidate(
        action="BUY MORE",
        score=82,
        allocation=2.5,
        owned=True,
    )

    portfolio = make_portfolio(
        allocation=2.5,
    )

    decision = make_decision(
        action="BUY MORE",
    )

    monkeypatch.setattr(
        reviewer,
        "call_ollama",
        lambda prompt: mock_ollama_response(
            review_decision="ACCEPT",
            confidence=84,
            challenge=False,
            reason="Strong evidence supports increasing the existing position.",
            key_points=[
                "Strong technical evidence",
                "Strong growth and quality",
                "Current allocation is modest",
            ],
        ),
    )

    result = reviewer.review_ai_decision(
        candidate,
        portfolio,
        decision,
    )

    assert result["LLM Assessment"] == "ACCEPT"
    assert result["Challenge"] is False
    assert result["LLM Confidence"] == 84


# ============================================================
# FD-05.3
# BUY MORE should be challenged when concentration is excessive
# ============================================================

def test_buy_more_is_challenged_for_excessive_concentration(
    monkeypatch,
):
    """
    Strong stock evidence does not automatically justify BUY MORE
    when the existing portfolio allocation is already excessive.
    """

    candidate = make_candidate(
        action="BUY MORE",
        score=88,
        allocation=18.0,
        owned=True,
    )

    portfolio = make_portfolio(
        allocation=18.0,
    )

    decision = make_decision(
        action="BUY MORE",
    )

    monkeypatch.setattr(
        reviewer,
        "call_ollama",
        lambda prompt: mock_ollama_response(
            review_decision="CHALLENGE",
            confidence=91,
            challenge=True,
            reason=(
                "The investment case is strong but the existing "
                "allocation creates a material concentration concern."
            ),
            key_points=[
                "Strong investment evidence",
                "Existing allocation is excessive",
            ],
        ),
    )

    result = reviewer.review_ai_decision(
        candidate,
        portfolio,
        decision,
    )

    assert result["LLM Assessment"] == "CHALLENGE"
    assert result["Challenge"] is True
    assert result["LLM Confidence"] == 91


# ============================================================
# FD-05.4
# Strong REDUCE should be ACCEPTED
# ============================================================

def test_strong_reduce_is_accepted(monkeypatch):
    """
    A strong negative case should be capable of producing REDUCE
    rather than being automatically protected by the existing HOLD.
    """

    candidate = make_candidate(
        action="REDUCE",
        score=25,
        allocation=6.0,
        owned=True,
    )

    candidate["analysis"]["technical_score"] = 15
    candidate["analysis"]["trend_score"] = 10
    candidate["analysis"]["momentum_score"] = 12
    candidate["analysis"]["signal"] = "SELL"

    candidate["analysis"]["technical_reasons"] = [
        "Below 50 DMA",
        "Below 200 DMA",
        "Negative momentum",
    ]

    candidate["analysis"]["technical_risks"] = [
        "Persistent downtrend",
        "Weak momentum",
    ]

    portfolio = make_portfolio(
        allocation=6.0,
    )

    decision = make_decision(
        action="REDUCE",
    )

    monkeypatch.setattr(
        reviewer,
        "call_ollama",
        lambda prompt: mock_ollama_response(
            review_decision="ACCEPT",
            confidence=90,
            challenge=False,
            reason="Strong negative evidence supports REDUCE.",
            key_points=[
                "Strong negative technical trend",
                "SELL signal",
                "Existing position is material",
            ],
        ),
    )

    result = reviewer.review_ai_decision(
        candidate,
        portfolio,
        decision,
    )

    assert result["LLM Assessment"] == "ACCEPT"
    assert result["Challenge"] is False
    assert result["LLM Confidence"] == 90


# ============================================================
# FD-05.5
# Strong SELL should be ACCEPTED
# ============================================================

def test_strong_sell_is_accepted(monkeypatch):
    """
    A very strong negative case should be capable of surviving
    governance as SELL.
    """

    candidate = make_candidate(
        action="SELL",
        score=15,
        allocation=4.0,
        owned=True,
    )

    candidate["analysis"]["technical_score"] = 5
    candidate["analysis"]["trend_score"] = 5
    candidate["analysis"]["momentum_score"] = 5
    candidate["analysis"]["risk_score"] = 15
    candidate["analysis"]["signal"] = "SELL"

    candidate["analysis"]["technical_reasons"] = []

    candidate["analysis"]["technical_risks"] = [
        "Severe downtrend",
        "Below 200 DMA",
        "Weak momentum",
    ]

    portfolio = make_portfolio(
        allocation=4.0,
    )

    decision = make_decision(
        action="SELL",
    )

    monkeypatch.setattr(
        reviewer,
        "call_ollama",
        lambda prompt: mock_ollama_response(
            review_decision="ACCEPT",
            confidence=94,
            challenge=False,
            reason="Very strong negative evidence supports SELL.",
            key_points=[
                "Severe negative technical evidence",
                "SELL signal",
                "No supplied evidence contradicts exit",
            ],
        ),
    )

    result = reviewer.review_ai_decision(
        candidate,
        portfolio,
        decision,
    )

    assert result["LLM Assessment"] == "ACCEPT"
    assert result["Challenge"] is False
    assert result["LLM Confidence"] == 94


# ============================================================
# FD-05.6
# HOLD with mixed evidence should remain ACCEPT
# ============================================================

def test_hold_with_mixed_evidence_is_accepted(monkeypatch):
    """
    HOLD is the default action when the supplied evidence does not
    establish a sufficiently strong reason to change the position.
    """

    candidate = make_candidate(
        action="HOLD",
        score=55,
        allocation=5.0,
        owned=True,
    )

    candidate["analysis"]["technical_score"] = 50
    candidate["analysis"]["quality_score"] = 60
    candidate["analysis"]["growth_score"] = 55
    candidate["analysis"]["signal"] = "HOLD"

    portfolio = make_portfolio(
        allocation=5.0,
    )

    decision = make_decision(
        action="HOLD",
    )

    monkeypatch.setattr(
        reviewer,
        "call_ollama",
        lambda prompt: mock_ollama_response(
            review_decision="ACCEPT",
            confidence=68,
            challenge=False,
            reason="Mixed evidence supports maintaining HOLD.",
            key_points=[
                "No material contradiction",
                "No strong change case",
            ],
        ),
    )

    result = reviewer.review_ai_decision(
        candidate,
        portfolio,
        decision,
    )

    assert result["LLM Assessment"] == "ACCEPT"
    assert result["Challenge"] is False
    assert result["LLM Confidence"] == 68


# ============================================================
# FD-05.7
# Missing secondary evidence should reduce confidence,
# not automatically create CHALLENGE
# ============================================================

def test_missing_secondary_evidence_does_not_automatically_challenge(
    monkeypatch,
):
    """
    Missing secondary evidence should reduce confidence rather than
    automatically overturning a coherent proposal.
    """

    candidate = make_candidate(
        action="BUY NEW",
        score=86,
        allocation=0.0,
        owned=False,
    )

    candidate["analysis"]["revenue_growth"] = 0.0
    candidate["analysis"]["profit_margin"] = 0.0
    candidate["analysis"]["return_on_equity"] = 0.0
    candidate["analysis"]["debt_to_equity"] = 0.0

    portfolio = make_portfolio(
        allocation=0.0,
    )

    decision = make_decision(
        action="BUY NEW",
    )

    monkeypatch.setattr(
        reviewer,
        "call_ollama",
        lambda prompt: mock_ollama_response(
            review_decision="ACCEPT",
            confidence=67,
            challenge=False,
            reason=(
                "Core supplied evidence supports BUY NEW, "
                "although secondary fundamental evidence is incomplete."
            ),
            key_points=[
                "Strong technical evidence",
                "Strong investment score",
            ],
            evidence_gaps=[
                "Fundamental metrics unavailable",
            ],
        ),
    )

    result = reviewer.review_ai_decision(
        candidate,
        portfolio,
        decision,
    )

    assert result["LLM Assessment"] == "ACCEPT"
    assert result["Challenge"] is False

    assert result["LLM Confidence"] < 85

    assert (
        "Fundamental metrics unavailable"
        in result["Evidence Gaps"]
    )


# ============================================================
# FD-05.8
# Contradictory evidence should CHALLENGE
# ============================================================

def test_material_contradiction_is_challenged(monkeypatch):
    """
    A genuine contradiction between the supplied evidence and the
    proposed action should result in CHALLENGE.
    """

    candidate = make_candidate(
        action="BUY",
        score=82,
        allocation=2.0,
        owned=True,
    )

    candidate["analysis"]["technical_score"] = 20
    candidate["analysis"]["signal"] = "SELL"
    candidate["analysis"]["trend"] = "Strong downward trend"

    candidate["analysis"]["technical_risks"] = [
        "Below 200 DMA",
        "Persistent downtrend",
    ]

    portfolio = make_portfolio(
        allocation=2.0,
    )

    decision = make_decision(
        action="BUY",
    )

    monkeypatch.setattr(
        reviewer,
        "call_ollama",
        lambda prompt: mock_ollama_response(
            review_decision="CHALLENGE",
            confidence=95,
            challenge=True,
            reason=(
                "The supplied technical evidence materially "
                "contradicts the BUY proposal."
            ),
            key_points=[
                "Technical score is weak",
                "SELL signal conflicts with BUY",
            ],
        ),
    )

    result = reviewer.review_ai_decision(
        candidate,
        portfolio,
        decision,
    )

    assert result["LLM Assessment"] == "CHALLENGE"
    assert result["Challenge"] is True
    assert result["LLM Confidence"] == 95


# ============================================================
# FD-05.9
# Clearly unsupported BUY should REJECT
# ============================================================

def test_unsupported_buy_is_rejected(monkeypatch):
    """
    A proposal with genuinely weak evidence should be rejectable.
    """

    candidate = make_candidate(
        action="BUY",
        score=35,
        allocation=2.0,
        owned=True,
    )

    candidate["analysis"]["technical_score"] = 20
    candidate["analysis"]["quality_score"] = 35
    candidate["analysis"]["growth_score"] = 30
    candidate["analysis"]["signal"] = "SELL"

    portfolio = make_portfolio(
        allocation=2.0,
    )

    decision = make_decision(
        action="BUY",
    )

    monkeypatch.setattr(
        reviewer,
        "call_ollama",
        lambda prompt: mock_ollama_response(
            review_decision="REJECT",
            confidence=92,
            challenge=False,
            reason=(
                "The supplied evidence does not support the BUY proposal."
            ),
            key_points=[
                "Weak technical evidence",
                "SELL signal",
                "Weak supporting scores",
            ],
        ),
    )

    result = reviewer.review_ai_decision(
        candidate,
        portfolio,
        decision,
    )

    assert result["LLM Assessment"] == "REJECT"
    assert result["Challenge"] is False
    assert result["LLM Confidence"] == 92


# ============================================================
# FD-05.10
# Reviewer output remains normalised
# ============================================================

def test_review_output_has_required_governance_fields(
    monkeypatch,
):
    """
    Ensure the reviewer contract remains stable for the downstream
    reconciliation layer.
    """

    candidate = make_candidate(
        action="BUY",
        score=85,
        allocation=2.0,
        owned=True,
    )

    portfolio = make_portfolio(
        allocation=2.0,
    )

    decision = make_decision(
        action="BUY",
    )

    monkeypatch.setattr(
        reviewer,
        "call_ollama",
        lambda prompt: mock_ollama_response(
            review_decision="ACCEPT",
            confidence=87,
            challenge=False,
            reason="Evidence supports proposal.",
            key_points=[
                "Coherent evidence",
            ],
        ),
    )

    result = reviewer.review_ai_decision(
        candidate,
        portfolio,
        decision,
    )

    required_fields = {
        "Ticker",
        "LLM Assessment",
        "LLM Confidence",
        "LLM Reason",
        "LLM Decision",
        "Review Decision",
        "Confidence",
        "Challenge",
        "Reason",
        "Key Points",
        "Evidence Gaps",
        "Proposed Action",
        "Reviewer Status",
    }

    assert required_fields.issubset(
        result.keys()
    )

    assert result["Reviewer Status"] == (
        "LLM REVIEW COMPLETE"
    )


# ============================================================
# Test runner
# ============================================================

if __name__ == "__main__":

    import pytest

    raise SystemExit(
        pytest.main(
            [
                __file__,
                "-q",
            ]
        )
    )