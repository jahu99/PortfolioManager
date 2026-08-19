"""
AI Portfolio Reviewer

Purpose
-------
Use a local Llama model to independently review a deterministic
portfolio decision produced by the governed AI Decision Layer.

Architecture
------------
    Analytical Engines
            |
            v
    Rules-Based Proposal
            |
            v
    AI Decision Context
            |
            v
    AI Decision Layer
            |
            v
    AI Portfolio Reviewer (Llama)
            |
            v
    Reviewed Decision
            |
            v
    AI Decision Reconciler

The LLM is a REVIEW layer.

It does NOT:
    - calculate investment scores
    - replace analytical engines
    - invent market data
    - change ownership facts
    - allocate capital
    - execute trades
    - silently replace the deterministic decision

It DOES:
    - independently assess the deterministic proposal
    - assess the supplied supporting evidence
    - identify genuine contradictions
    - identify material evidence gaps
    - assess portfolio fit
    - distinguish BUY NEW from BUY MORE
    - provide an independent review opinion

Important design principle
--------------------------
The deterministic engine remains authoritative for:

    Technical Score
    Quality Score
    Growth Score
    Investment Score
    Signal
    Ownership
    Portfolio constraints

The LLM reviews whether the supplied evidence supports the
deterministic proposal.

Missing secondary evidence should reduce confidence, but should
NOT automatically create a CHALLENGE when the evidence that is
available is internally consistent.

A genuine contradiction should normally result in CHALLENGE.

Current provider
----------------
Ollama running locally.

Default model
-------------
llama3.2:3b

Environment variables
---------------------
OLLAMA_URL
    Default: http://localhost:11434/api/chat

OLLAMA_MODEL
    Default: llama3.2:3b

OLLAMA_TIMEOUT
    Default: 120 seconds
"""

from __future__ import annotations

import json
import os
from typing import Any

import requests


# ============================================================
# Configuration
# ============================================================

OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    "http://localhost:11434/api/chat",
)

OLLAMA_MODEL = os.getenv(
    "OLLAMA_MODEL",
    "llama3.2:3b",
)

try:

    OLLAMA_TIMEOUT = int(
        os.getenv(
            "OLLAMA_TIMEOUT",
            "120",
        )
    )

except (
    TypeError,
    ValueError,
):

    OLLAMA_TIMEOUT = 120


VALID_REVIEW_DECISIONS = {
    "ACCEPT",
    "CHALLENGE",
    "REJECT",
}


# ============================================================
# Utility Functions
# ============================================================

def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    """
    Safely convert a value to float.
    """

    try:

        if value is None:
            return default

        return float(value)

    except (
        TypeError,
        ValueError,
    ):

        return default


def _safe_confidence(
    value: Any,
) -> float:
    """
    Return confidence bounded between 0 and 100.
    """

    confidence = _safe_float(
        value,
        default=0.0,
    )

    return round(
        max(
            0.0,
            min(
                100.0,
                confidence,
            ),
        ),
        2,
    )


def _clean_text(
    value: Any,
) -> str:
    """
    Convert arbitrary values into compact text.
    """

    if value is None:
        return ""

    return str(
        value
    ).strip()


def _safe_json(
    value: Any,
) -> str:
    """
    Safely serialise data for the LLM prompt.
    """

    return json.dumps(
        value,
        indent=2,
        default=str,
    )


def _normalise_list(
    value: Any,
) -> list[str]:
    """
    Convert an arbitrary value into a clean string list.
    """

    if value is None:
        return []

    if isinstance(
        value,
        list,
    ):

        return [
            _clean_text(item)
            for item in value
            if _clean_text(item)
        ]

    text = _clean_text(
        value
    )

    if not text:
        return []

    return [text]


def _first_value(
    data: dict,
    *keys: str,
    default: Any = None,
) -> Any:
    """
    Return the first non-empty value from a dictionary.
    """

    if not isinstance(
        data,
        dict,
    ):
        return default

    for key in keys:

        value = data.get(
            key
        )

        if value is None:
            continue

        if isinstance(
            value,
            str,
        ) and not value.strip():
            continue

        return value

    return default


# ============================================================
# Compact Candidate Context
# ============================================================

def _build_compact_candidate(
    candidate: dict,
) -> dict:
    """
    Build a compact but materially complete evidence package.

    The previous reviewer context was too sparse. It included
    Investment Score, Quality Score and Growth Score but omitted
    much of the evidence behind those scores.

    This version exposes the most important technical,
    fundamental, timing and historical evidence already produced
    by upstream modules.

    No new evidence is calculated here.
    """

    if not isinstance(
        candidate,
        dict,
    ):
        candidate = {}

    analysis = candidate.get(
        "analysis",
        {},
    )

    if not isinstance(
        analysis,
        dict,
    ):
        analysis = {}

    ownership = candidate.get(
        "ownership",
        {},
    )

    if not isinstance(
        ownership,
        dict,
    ):
        ownership = {}

    rules = candidate.get(
        "rules_based_decision",
        {},
    )

    if not isinstance(
        rules,
        dict,
    ):
        rules = {}

    intelligence = candidate.get(
        "recommendation_intelligence",
        {},
    )

    if not isinstance(
        intelligence,
        dict,
    ):
        intelligence = {}

    ai_decision = candidate.get(
        "ai_decision",
        candidate.get(
            "AI Decision Object",
            {},
        ),
    )

    if not isinstance(
        ai_decision,
        dict,
    ):
        ai_decision = {}

    # --------------------------------------------------------
    # Identity / proposal
    # --------------------------------------------------------

    ticker = _first_value(
        candidate,
        "ticker",
        "Ticker",
        default="",
    )

    asset_type = _first_value(
        candidate,
        "asset_type",
        "Asset Type",
        "Type",
        default="STOCK",
    )

    proposed_action = _first_value(
        rules,
        "action",
        default=_first_value(
            candidate,
            "Proposed Action",
            "Action",
            default="HOLD",
        ),
    )

    # --------------------------------------------------------
    # Core scoring
    # --------------------------------------------------------

    investment_score = _first_value(
        analysis,
        "investment_score",
        default=_first_value(
            candidate,
            "Investment Score",
            "investment_score",
            default=0.0,
        ),
    )

    technical_score = _first_value(
        analysis,
        "technical_score",
        default=_first_value(
            candidate,
            "Technical Score",
            "technical_score",
            default=0.0,
        ),
    )

    quality_score = _first_value(
        analysis,
        "quality_score",
        default=_first_value(
            candidate,
            "Quality Score",
            "quality_score",
            default=0.0,
        ),
    )

    growth_score = _first_value(
        analysis,
        "growth_score",
        default=_first_value(
            candidate,
            "Growth Score",
            "growth_score",
            default=0.0,
        ),
    )

    signal = _first_value(
        analysis,
        "signal",
        default=_first_value(
            candidate,
            "Signal",
            "Momentum Signal",
            "signal",
            default="",
        ),
    )

    # --------------------------------------------------------
    # Technical / timing evidence
    # --------------------------------------------------------

    current_price = _first_value(
        analysis,
        "price",
        "current_price",
        default=_first_value(
            candidate,
            "Price",
            "Current Price",
            default=0.0,
        ),
    )

    ma50 = _first_value(
        analysis,
        "ma50",
        default=_first_value(
            candidate,
            "MA50",
            "SMA50",
            default=0.0,
        ),
    )

    ma200 = _first_value(
        analysis,
        "ma200",
        default=_first_value(
            candidate,
            "MA200",
            "SMA200",
            default=0.0,
        ),
    )

    rsi = _first_value(
        analysis,
        "rsi",
        default=_first_value(
            candidate,
            "RSI",
            default=50.0,
        ),
    )

    return_3m = _first_value(
        analysis,
        "return_3m",
        default=_first_value(
            candidate,
            "Return_3m",
            "3M Return %",
            "6M Return %",
            default=0.0,
        ),
    )

    trend = _first_value(
        analysis,
        "trend",
        default=_first_value(
            candidate,
            "Trend",
            default="",
        ),
    )

    trend_score = _first_value(
        analysis,
        "trend_score",
        default=_first_value(
            candidate,
            "Trend Score",
            default=0.0,
        ),
    )

    momentum_score = _first_value(
        analysis,
        "momentum_score",
        default=_first_value(
            candidate,
            "Momentum Score",
            default=0.0,
        ),
    )

    volume_score = _first_value(
        analysis,
        "volume_score",
        default=_first_value(
            candidate,
            "Volume Score",
            default=0.0,
        ),
    )

    risk_score = _first_value(
        analysis,
        "risk_score",
        default=_first_value(
            candidate,
            "Risk Score",
            default=0.0,
        ),
    )

    technical_reasons = _first_value(
        analysis,
        "technical_reasons",
        "Technical Reasons",
        default=_first_value(
            candidate,
            "Technical Reasons",
            default=[],
        ),
    )

    technical_risks = _first_value(
        analysis,
        "technical_risks",
        "Technical Risks",
        default=_first_value(
            candidate,
            "Technical Risks",
            default=[],
        ),
    )

    # --------------------------------------------------------
    # Fundamental evidence
    # --------------------------------------------------------

    revenue_growth = _first_value(
        analysis,
        "revenue_growth",
        default=_first_value(
            candidate,
            "Revenue Growth",
            default=0.0,
        ),
    )

    profit_margin = _first_value(
        analysis,
        "profit_margin",
        default=_first_value(
            candidate,
            "Profit Margin",
            default=0.0,
        ),
    )

    roe = _first_value(
        analysis,
        "return_on_equity",
        "roe",
        default=_first_value(
            candidate,
            "Return on Equity",
            "ROE",
            default=0.0,
        ),
    )

    debt_to_equity = _first_value(
        analysis,
        "debt_to_equity",
        "debt",
        default=_first_value(
            candidate,
            "Debt to Equity",
            "Debt / Equity",
            default=0.0,
        ),
    )

    sector = _first_value(
        analysis,
        "sector",
        default=_first_value(
            candidate,
            "Sector",
            default="Unknown",
        ),
    )

    industry = _first_value(
        analysis,
        "industry",
        default=_first_value(
            candidate,
            "Industry",
            default="Unknown",
        ),
    )

    recommendation_reasons = _first_value(
        candidate,
        "Recommendation Reasons",
        "recommendation_reasons",
        default=[],
    )

    recommendation_risks = _first_value(
        candidate,
        "Recommendation Risks",
        "recommendation_risks",
        default=[],
    )

    # --------------------------------------------------------
    # Historical / learning evidence
    # --------------------------------------------------------

    historical_observations = _first_value(
        intelligence,
        "historical_signal_observations",
        default=_first_value(
            candidate,
            "Historical Signal Observations",
            default=0,
        ),
    )

    historical_win_rate = _first_value(
        intelligence,
        "historical_signal_win_rate_pct",
        default=_first_value(
            candidate,
            "Historical Signal Win Rate %",
            default=0.0,
        ),
    )

    historical_average_return = _first_value(
        intelligence,
        "historical_signal_average_return_pct",
        default=_first_value(
            candidate,
            "Historical Signal Average Return %",
            default=0.0,
        ),
    )

    historical_reliability = _first_value(
        intelligence,
        "historical_signal_reliability",
        default=_first_value(
            candidate,
            "Historical Signal Reliability",
            default="",
        ),
    )

    learning_adjusted_score = _first_value(
        intelligence,
        "learning_adjusted_score",
        default=_first_value(
            candidate,
            "Learning Adjusted Score",
            default=0.0,
        ),
    )

    confidence_score = _first_value(
        analysis,
        "confidence_score",
        default=_first_value(
            candidate,
            "Confidence Score",
            "confidence_score",
            default=0.0,
        ),
    )

    # --------------------------------------------------------
    # Deterministic AI assessment
    # --------------------------------------------------------

    ai_conviction = _first_value(
        ai_decision,
        "Conviction",
        default=_first_value(
            candidate,
            "AI Conviction",
            default="",
        ),
    )

    ai_conviction_score = _first_value(
        ai_decision,
        "Conviction Score",
        default=_first_value(
            candidate,
            "AI Conviction Score",
            default=0.0,
        ),
    )

    ai_action = _first_value(
        ai_decision,
        "Recommended Action",
        default=_first_value(
            candidate,
            "AI Action",
            default=[],
        ),
    )

    ai_thesis = _first_value(
        candidate,
        "AI Investment Thesis",
        "Investment Thesis",
        default=[],
    )

    ai_risks = _first_value(
        candidate,
        "AI Risks",
        "Risks",
        default=[],
    )

    return {
        "ticker": ticker,
        "asset_type": asset_type,
        "proposed_action": proposed_action,

        # Core scoring
        "investment_score": _safe_float(
            investment_score
        ),
        "technical_score": _safe_float(
            technical_score
        ),
        "quality_score": _safe_float(
            quality_score
        ),
        "growth_score": _safe_float(
            growth_score
        ),
        "signal": signal,

        # Technical / timing
        "current_price": _safe_float(
            current_price
        ),
        "ma50": _safe_float(
            ma50
        ),
        "ma200": _safe_float(
            ma200
        ),
        "rsi": _safe_float(
            rsi
        ),
        "return_3m_pct": _safe_float(
            return_3m
        ),
        "trend": trend,
        "trend_score": _safe_float(
            trend_score
        ),
        "momentum_score": _safe_float(
            momentum_score
        ),
        "volume_score": _safe_float(
            volume_score
        ),
        "risk_score": _safe_float(
            risk_score
        ),
        "technical_reasons": _normalise_list(
            technical_reasons
        ),
        "technical_risks": _normalise_list(
            technical_risks
        ),

        # Fundamental
        "revenue_growth": _safe_float(
            revenue_growth
        ),
        "profit_margin": _safe_float(
            profit_margin
        ),
        "return_on_equity": _safe_float(
            roe
        ),
        "debt_to_equity": _safe_float(
            debt_to_equity
        ),
        "sector": sector,
        "industry": industry,
        "recommendation_reasons": _normalise_list(
            recommendation_reasons
        ),
        "recommendation_risks": _normalise_list(
            recommendation_risks
        ),

        # Ownership / portfolio
        "existing_holding": bool(
            ownership.get(
                "owned",
                False,
            )
        ),
        "allocation_pct": _safe_float(
            ownership.get(
                "allocation_pct",
                0.0,
            )
        ),
        "quantity": _safe_float(
            ownership.get(
                "quantity",
                0.0,
            )
        ),

        # Learning
        "historical_observations": int(
            _safe_float(
                historical_observations
            )
        ),
        "historical_win_rate_pct": _safe_float(
            historical_win_rate
        ),
        "historical_average_return_pct": _safe_float(
            historical_average_return
        ),
        "historical_reliability": historical_reliability,
        "learning_adjusted_score": _safe_float(
            learning_adjusted_score
        ),
        "confidence_score": _safe_float(
            confidence_score
        ),

        # Deterministic AI assessment
        "ai_conviction": ai_conviction,
        "ai_conviction_score": _safe_float(
            ai_conviction_score
        ),
        "ai_action": _normalise_list(
            ai_action
        ),
        "ai_investment_thesis": _normalise_list(
            ai_thesis
        ),
        "ai_risks": _normalise_list(
            ai_risks
        ),
    }


# ============================================================
# Compact Portfolio Context
# ============================================================

def _build_compact_portfolio(
    portfolio: dict,
) -> dict:
    """
    Extract portfolio facts relevant to review.
    """

    if not isinstance(
        portfolio,
        dict,
    ):
        portfolio = {}

    portfolio_summary = portfolio.get(
        "portfolio",
        portfolio,
    )

    if not isinstance(
        portfolio_summary,
        dict,
    ):
        portfolio_summary = {}

    return {
        "total_market_value": _safe_float(
            portfolio_summary.get(
                "total_market_value",
                0.0,
            )
        ),

        "cash": _safe_float(
            portfolio_summary.get(
                "cash",
                0.0,
            )
        ),

        "largest_position_pct": _safe_float(
            portfolio_summary.get(
                "largest_position_pct",
                0.0,
            )
        ),

        "largest_position_ticker": _clean_text(
            portfolio_summary.get(
                "largest_position_ticker",
                "",
            )
        ),

        "stock_count": int(
            _safe_float(
                portfolio_summary.get(
                    "stock_count",
                    0,
                )
            )
        ),

        "etf_count": int(
            _safe_float(
                portfolio_summary.get(
                    "etf_count",
                    0,
                )
            )
        ),

        "sector_count": int(
            _safe_float(
                portfolio_summary.get(
                    "sector_count",
                    0,
                )
            )
        ),
    }


# ============================================================
# Compact Deterministic Decision
# ============================================================

def _build_compact_decision(
    decision: dict,
) -> dict:
    """
    Extract the deterministic decision fields.
    """

    if not isinstance(
        decision,
        dict,
    ):
        decision = {}

    evidence = decision.get(
        "Evidence Assessment",
        {},
    )

    if not isinstance(
        evidence,
        dict,
    ):
        evidence = {}

    return {
        "final_decision": _first_value(
            decision,
            "Final Decision",
            default="HOLD",
        ),

        "proposed_action": _first_value(
            decision,
            "Proposed Action",
            default=_first_value(
                evidence,
                "Action",
                default="HOLD",
            ),
        ),

        "evidence_score": _safe_float(
            _first_value(
                decision,
                "Evidence Score",
                default=_first_value(
                    evidence,
                    "Evidence Score",
                    default=0.0,
                ),
            )
        ),

        "evidence_strength": _first_value(
            decision,
            "Evidence Strength",
            default=_first_value(
                evidence,
                "Evidence Strength",
                default="UNKNOWN",
            ),
        ),

        "decision_support": _first_value(
            decision,
            "Decision Support",
            default=_first_value(
                evidence,
                "Decision Support",
                default="UNKNOWN",
            ),
        ),

        "confidence": _safe_float(
            _first_value(
                decision,
                "Confidence",
                default=_first_value(
                    evidence,
                    "Confidence",
                    default=0.0,
                ),
            )
        ),

        "reason": _clean_text(
            _first_value(
                decision,
                "Reason",
                default="",
            )
        ),

        "governance_reasons": _normalise_list(
            _first_value(
                decision,
                "Governance Reasons",
                default=[],
            )
        ),
    }


# ============================================================
# Prompt Construction
# ============================================================

def build_review_prompt(
    candidate: dict,
    portfolio: dict,
    decision: dict,
) -> str:
    """
    Build the LLM review prompt.

    Important review semantics:

        ACCEPT
            Evidence supports the deterministic proposal.

        CHALLENGE
            There is meaningful contradictory evidence, or a
            material portfolio/governance concern.

        REJECT
            The proposal is clearly inconsistent with the
            supplied evidence.

    A missing secondary field does not automatically mean
    CHALLENGE. It lowers confidence unless the missing evidence
    is material to the particular proposal.
    """

    compact_candidate = _build_compact_candidate(
        candidate
    )

    compact_portfolio = _build_compact_portfolio(
        portfolio
    )

    compact_decision = _build_compact_decision(
        decision
    )

    proposed_action = str(
        compact_candidate.get(
            "proposed_action",
            "HOLD",
        )
    ).upper()

    review_guidance = []

    if proposed_action == "BUY NEW":

        review_guidance = [
            "For BUY NEW, assess whether the supplied technical, fundamental and timing evidence is collectively strong enough to support initiating a new position.",
            "A high Investment Score alone is not proof of a BUY, but a high Investment Score supported by strong component evidence and a compatible signal is meaningful evidence.",
            "Do not invent valuation, earnings, news or market information that is not supplied.",
            "Missing secondary data should lower confidence rather than automatically create CHALLENGE.",
            "CHALLENGE when there is a material contradiction in the supplied evidence."
        ]

    elif proposed_action == "BUY MORE":

        review_guidance = [
            "For BUY MORE, assess whether increasing an existing position is justified by the supplied evidence and current portfolio exposure.",
            "Pay particular attention to current allocation, concentration and whether the technical/fundamental evidence remains supportive.",
            "A strong stock case can still be challenged when the supplied portfolio evidence shows excessive concentration.",
            "Missing secondary data should lower confidence rather than automatically create CHALLENGE.",
            "CHALLENGE when there is a material contradiction in the supplied evidence."
        ]

    elif proposed_action in {
        "REDUCE",
        "SELL",
    }:

        review_guidance = [
            "For REDUCE or SELL, require strong supplied evidence that the existing position should be reduced or exited.",
            "Do not create a challenge merely because some secondary information is unavailable."
        ]

    else:

        review_guidance = [
            "For HOLD, determine whether the supplied evidence supports maintaining the existing portfolio state.",
            "HOLD remains the default when there is no sufficiently strong reason to change."
        ]

    return f"""
You are an independent AI reviewer inside a governed investment
portfolio system.

Your role is to review the deterministic proposal using ONLY the
evidence supplied below.

You are NOT the investment scoring engine.

Do not:
- invent market data
- invent financial evidence
- invent valuation data
- invent news or catalysts
- calculate a new investment score
- change ownership facts
- allocate capital
- execute trades
- silently replace the deterministic decision

You may:
- ACCEPT the proposal
- CHALLENGE the proposal
- REJECT the proposal

IMPORTANT REVIEW PRINCIPLES

1. The Investment Score is already calculated by the deterministic
   scoring engine from Technical, Quality and Growth scores.

2. Do NOT recalculate or replace that score.

3. Review the underlying supplied evidence to determine whether it
   supports the proposal.

4. Distinguish:
   - MISSING EVIDENCE
   - CONTRADICTORY EVIDENCE

5. Missing evidence:
   - lowers confidence
   - does NOT automatically require CHALLENGE
   - should only materially affect the review when the missing
     information is essential to the proposed action.

6. Contradictory evidence:
   - normally warrants CHALLENGE
   - especially when the contradiction directly conflicts with
     the proposed action.

7. A strong deterministic BUY proposal may be ACCEPTED when the
   supplied evidence is coherent and there is no material
   contradiction.

8. HOLD remains the default when evidence does not justify a
   change.

9. BUY NEW and BUY MORE require stronger evidence than HOLD,
   but do not require certainty.

10. For BUY MORE, consider existing portfolio allocation and
    concentration.

ACTION-SPECIFIC GUIDANCE

{_safe_json(review_guidance)}

CANDIDATE EVIDENCE

{_safe_json(compact_candidate)}

PORTFOLIO EVIDENCE

{_safe_json(compact_portfolio)}

DETERMINISTIC DECISION

{_safe_json(compact_decision)}

REVIEW TASK

Determine whether the deterministic proposal is adequately
supported by the supplied evidence.

For BUY NEW and BUY MORE:
- assess technical strength
- assess timing evidence
- assess quality and growth evidence
- assess signal consistency
- assess historical evidence when present
- assess portfolio fit
- identify genuine contradictions
- identify material evidence gaps

Do not penalise the proposal simply because every possible
investment metric is not supplied.

Return ONLY valid JSON.

Required structure:

{{
  "review_decision": "ACCEPT",
  "confidence": 85,
  "challenge": false,
  "reason": "Short explanation",
  "key_points": [
    "Point one"
  ],
  "evidence_gaps": []
}}

review_decision must be exactly one of:

ACCEPT
CHALLENGE
REJECT

confidence must be an integer or number from 0 to 100.

challenge must be true or false.

reason must be concise.

key_points must contain short evidence-based observations.

evidence_gaps must contain only material missing evidence.

Do not return markdown.
Do not return commentary outside the JSON object.
"""


# ============================================================
# Ollama Interface
# ============================================================

def call_ollama(
    prompt: str,
) -> dict:
    """
    Send the review request to Ollama.
    """

    payload = {
        "model": OLLAMA_MODEL,

        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a disciplined portfolio reviewer. "
                    "Use only supplied evidence. "
                    "Return JSON only."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],

        "stream": False,

        "format": "json",

        "options": {
            "temperature": 0,
            "num_predict": 300,
        },

        "keep_alive": "10m",
    }

    response = requests.post(
        OLLAMA_URL,
        json=payload,
        timeout=OLLAMA_TIMEOUT,
    )

    response.raise_for_status()

    response_payload = response.json()

    message = response_payload.get(
        "message",
        {},
    )

    content = message.get(
        "content",
        "",
    )

    if not content:

        raise ValueError(
            "Ollama returned an empty response"
        )

    content = content.strip()

    result = json.loads(
        content
    )

    if not isinstance(
        result,
        dict,
    ):

        raise ValueError(
            "Ollama response was not a JSON object"
        )

    return result


# ============================================================
# Response Normalisation
# ============================================================

def _normalise_llm_response(
    llm_response: dict,
    candidate: dict,
    decision: dict,
) -> dict:
    """
    Convert raw Llama JSON into the standard reviewer interface.
    """

    if not isinstance(
        llm_response,
        dict,
    ):
        llm_response = {}

    review_decision = (
        _clean_text(
            llm_response.get(
                "review_decision",
                "CHALLENGE",
            )
        )
        .upper()
    )

    if review_decision not in VALID_REVIEW_DECISIONS:

        review_decision = "CHALLENGE"

    confidence = _safe_confidence(
        llm_response.get(
            "confidence",
            0.0,
        )
    )

    challenge = llm_response.get(
        "challenge",
        review_decision != "ACCEPT",
    )

    if isinstance(
        challenge,
        str,
    ):

        challenge = (
            challenge.strip().lower()
            in {
                "true",
                "yes",
                "1",
            }
        )

    else:

        challenge = bool(
            challenge
        )

    reason = _clean_text(
        llm_response.get(
            "reason",
            "",
        )
    )

    ticker = _clean_text(
        _first_value(
            candidate,
            "ticker",
            "Ticker",
            default="",
        )
    )

    proposed_action = _first_value(
        decision,
        "Proposed Action",
        default=_first_value(
            candidate,
            "Proposed Action",
            "Action",
            default="HOLD",
        ),
    )

    key_points = _normalise_list(
        llm_response.get(
            "key_points",
            [],
        )
    )

    evidence_gaps = _normalise_list(
        llm_response.get(
            "evidence_gaps",
            [],
        )
    )

    # --------------------------------------------------------
    # Safety normalisation
    #
    # If the model says ACCEPT but also sets challenge=true,
    # treat the explicit challenge flag as authoritative.
    # --------------------------------------------------------

    if challenge and review_decision == "ACCEPT":

        review_decision = "CHALLENGE"

    # --------------------------------------------------------
    # Conservative safety behaviour
    #
    # An empty reason is not enough to reject a proposal, but
    # incomplete model output receives reduced confidence.
    # --------------------------------------------------------

    if not reason:

        reason = (
            "LLM review returned no detailed reason."
        )

        confidence = min(
            confidence,
            50.0,
        )

    return {
        "Ticker":
            ticker,

        "LLM Assessment":
            review_decision,

        "LLM Confidence":
            confidence,

        "LLM Reason":
            reason,

        "LLM Decision":
            review_decision,

        "Review Decision":
            review_decision,

        "Confidence":
            confidence,

        "Challenge":
            challenge,

        "Reason":
            reason,

        "Key Points":
            key_points,

        "LLM Key Points":
            key_points,

        "Evidence Gaps":
            evidence_gaps,

        "LLM Evidence Gaps":
            evidence_gaps,

        "Proposed Action":
            proposed_action,

        "Reviewer Status":
            "LLM REVIEW COMPLETE",
    }


# ============================================================
# Public Reviewer Interface
# ============================================================

def review_ai_decision(
    candidate: dict,
    portfolio: dict,
    decision: dict,
) -> dict:
    """
    Review a deterministic portfolio decision with Llama.

    Public interface used by:

        analysis/final_portfolio_decision.py

    Returns a normalised reviewer dictionary.
    """

    ticker = _clean_text(
        _first_value(
            candidate,
            "ticker",
            "Ticker",
            default="",
        )
    )

    try:

        prompt = build_review_prompt(
            candidate=candidate,
            portfolio=portfolio,
            decision=decision,
        )

        llm_response = call_ollama(
            prompt
        )

        review = _normalise_llm_response(
            llm_response=llm_response,
            candidate=candidate,
            decision=decision,
        )

        print(
            f"LLM REVIEW COMPLETE: "
            f"{ticker} | "
            f"{review.get('LLM Assessment', 'UNKNOWN')} | "
            f"{review.get('LLM Confidence', 0)} | "
            f"{review.get('LLM Reason', '')}"
        )

        return review

    except Exception as exc:

        print(
            f"LLM REVIEW ERROR: "
            f"{ticker} | {exc}"
        )

        return {
            "Ticker":
                ticker,

            "LLM Assessment":
                "CHALLENGE",

            "LLM Confidence":
                0.0,

            "LLM Reason":
                (
                    "Production reviewer error: "
                    f"{exc}"
                ),

            "LLM Decision":
                "CHALLENGE",

            "Review Decision":
                "CHALLENGE",

            "Confidence":
                0.0,

            "Challenge":
                True,

            "Reason":
                (
                    "Production reviewer error: "
                    f"{exc}"
                ),

            "Key Points":
                [],

            "LLM Key Points":
                [],

            "Evidence Gaps":
                [
                    "Production reviewer exception"
                ],

            "Evidence Gaps":
                [
                    "Production reviewer exception"
                ],

            "Proposed Action":
                _first_value(
                    decision,
                    "Proposed Action",
                    default="HOLD",
                ),

            "Reviewer Status":
                "LLM REVIEW ERROR",
        }


# ============================================================
# Optional Prompt Inspection Helper
# ============================================================

def build_review_payload(
    candidate: dict,
    portfolio: dict,
    decision: dict,
) -> dict:
    """
    Return the exact compact payload supplied to Llama.

    Useful for debugging and test harnesses without making an
    Ollama call.
    """

    return {
        "candidate":
            _build_compact_candidate(
                candidate
            ),

        "portfolio":
            _build_compact_portfolio(
                portfolio
            ),

        "decision":
            _build_compact_decision(
                decision
            ),
    }