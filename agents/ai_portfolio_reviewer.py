"""
AI Portfolio Reviewer

Purpose
-------
Use a local Ollama model to independently review a deterministic
portfolio decision produced by the governed AI Decision Layer.

This module is deliberately optimised for short, structured governance
reviews. It does not calculate investment scores. It reviews whether the supplied evidence supports the
proposed portfolio action.

Design principles
-----------------
- Deterministic analytical outputs remain authoritative.
- HOLD is the default portfolio state.
- Missing evidence is not the same as contradictory evidence.
- A lower component score is not, by itself, a contradiction.
- The reviewer must assess the proposed action, not invent a new thesis.
- BUY NEW, BUY MORE, REDUCE and SELL receive proposal-specific scrutiny.
- The output is intentionally small JSON to reduce local inference cost.
- Provider/model selection remains configurable via environment variables.

Environment variables
---------------------
OLLAMA_URL
    Default: http://localhost:11434/api/chat

OLLAMA_MODEL
    Default: qwen2.5:1.5b

OLLAMA_TIMEOUT
    Default: 120 seconds. This is a failure ceiling, not a performance
    setting; prompt/model reduction is used to improve inference speed.

OLLAMA_NUM_PREDICT
    Default: 120

OLLAMA_KEEP_ALIVE
    Default: 5m
"""

from __future__ import annotations

import json
import os

import hashlib
from pathlib import Path

from typing import Any

import requests

from google import genai

from config.llm_config import (
    LLM_PROVIDER,
    LLM_CACHE_ENABLED,
    LLM_CACHE_PATH,
    GEMINI_MODEL,
)



# ============================================================
# Configuration
# ============================================================

OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    "http://localhost:11434/api/chat",
)

OLLAMA_MODEL = os.getenv(
    "OLLAMA_MODEL",
    "qwen2.5:1.5b"
)

try:
    OLLAMA_TIMEOUT = int(
        os.getenv(
            "OLLAMA_TIMEOUT",
            "120",
        )
    )
except (TypeError, ValueError):
    OLLAMA_TIMEOUT = 120

try:
    OLLAMA_NUM_PREDICT = int(
        os.getenv(
            "OLLAMA_NUM_PREDICT",
            "120",
        )
    )
except (TypeError, ValueError):
    OLLAMA_NUM_PREDICT = 120

OLLAMA_KEEP_ALIVE = os.getenv(
    "OLLAMA_KEEP_ALIVE",
    "5m",
)

VALID_REVIEW_DECISIONS = {
    "ACCEPT",
    "CHALLENGE",
    "REJECT",
}


# ============================================================
# Utility functions
# ============================================================

def _safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert a value to float."""
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_confidence(value: Any) -> float:
    """Return confidence bounded between 0 and 100."""
    confidence = _safe_float(value, 0.0)
    return round(max(1.0, min(100.0, confidence)), 2)


def _clean_text(value: Any) -> str:
    """Convert arbitrary values into stripped text."""
    if value is None:
        return ""
    return str(value).strip()


def _normalise_list(value: Any) -> list[str]:
    """Convert an arbitrary value into a clean string list."""
    if value is None:
        return []

    if isinstance(value, list):
        return [
            _clean_text(item)
            for item in value
            if _clean_text(item)
        ]

    text = _clean_text(value)
    return [text] if text else []


def _first_value(
    data: dict,
    *keys: str,
    default: Any = None,
) -> Any:
    """Return the first non-empty dictionary value."""
    if not isinstance(data, dict):
        return default

    for key in keys:
        value = data.get(key)
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value

    return default


def _safe_json(value: Any) -> str:
    """Compact JSON serialisation for prompt construction."""
    return json.dumps(
        value,
        separators=(",", ":"),
        default=str,
    )


# ============================================================
# Compact evidence extraction
# ============================================================


def _build_compact_candidate(candidate: dict) -> dict:
    """
    Build the governed candidate evidence supplied to the LLM reviewer.

    The reviewer must receive the actual evidence produced by the deterministic
    decision layer, not synthetic defaults.

    Design rules:

    - Preserve the canonical proposed action when supplied.
    - Structured ownership is authoritative for held status.
    - Structured candidate decision is authoritative for proposed action.
    - Support both flattened and nested candidate structures.
    - Preserve genuine absence as None/omitted.
    - Never convert missing technical evidence into fake values.
    - ETFs receive ETF evidence only.
    - Stocks receive stock evidence only.
    - Historical/learning evidence is preserved when available.
    """

    if not isinstance(candidate, dict):
        candidate = {}

    # ------------------------------------------------------------
    # Nested sections
    # ------------------------------------------------------------

    analysis = candidate.get("analysis", {})
    if not isinstance(analysis, dict):
        analysis = {}

    intelligence = candidate.get(
        "recommendation_intelligence",
        candidate.get("intelligence", {}),
    )
    if not isinstance(intelligence, dict):
        intelligence = {}

    rules = candidate.get("rules", {})
    if not isinstance(rules, dict):
        rules = {}

    ownership = candidate.get("ownership", {})
    if not isinstance(ownership, dict):
        ownership = {}

    decision = candidate.get("decision", {})
    if not isinstance(decision, dict):
        decision = {}

    # ------------------------------------------------------------
    # Asset type
    # ------------------------------------------------------------

    asset_type = _clean_text(
        _first_value(
            candidate,
            "Asset Type",
            "asset_type",
            default=_first_value(
                analysis,
                "asset_type",
                "Asset Type",
                default=_first_value(
                    candidate,
                    "asset",
                    "Asset",
                    default="STOCK",
                ),
            ),
        )
    ).upper()

    if asset_type not in {"STOCK", "ETF"}:
        asset_type = "STOCK"

    # ------------------------------------------------------------
    # Basic identity
    # ------------------------------------------------------------

    ticker = _clean_text(
        _first_value(
            ownership,
            "Ticker",
            "ticker",
            default=_first_value(
                candidate,
                "Ticker",
                "ticker",
                default="",
            ),
        )
    )

    name = _clean_text(
        _first_value(
            ownership,
            "Name",
            "name",
            default=_first_value(
                candidate,
                "Name",
                "name",
                default="",
            ),
        )
    )

    # ------------------------------------------------------------
    # Ownership
    #
    # Structured ownership is authoritative. Flattened candidate
    # fields may be stale from an earlier pipeline stage.
    # ------------------------------------------------------------

    held_value = _first_value(
        ownership,
        "Held?",
        "held",
        "is_held",
        default=_first_value(
            candidate,
            "Held?",
            "held",
            "is_held",
            default=False,
        ),
    )

    if isinstance(held_value, str):
        held = held_value.strip().lower() in {
            "true",
            "yes",
            "1",
        }
    else:
        held = bool(held_value)

    sector = _clean_text(
        _first_value(
            ownership,
            "Sector",
            "sector",
            default=_first_value(
                candidate,
                "Sector",
                "sector",
                default="",
            ),
        )
    )

    compact = {
        "ticker": ticker,
        "name": name,
        "asset_type": asset_type,
        "held": held,
        "sector": sector,
    }

    # ------------------------------------------------------------
    # Proposed action
    #
    # Structured candidate decision is authoritative over flattened
    # candidate fields, which may contain stale values.
    # ------------------------------------------------------------

    proposed_action = _first_value(
        decision,
        "Proposed Action",
        "proposed_action",
        "Action",
        "action",
        default=_first_value(
            candidate,
            "Proposed Action",
            "proposed_action",
            "Action",
            "action",
            default="HOLD",
        ),
    )

    compact["proposed_action"] = (
        _clean_text(proposed_action).upper() or "HOLD"
    )

    # ------------------------------------------------------------
    # ETF evidence
    # ------------------------------------------------------------

    if asset_type == "ETF":

        etf_score = _first_value(
            analysis,
            "etf_score",
            "ETF Score",
            default=_first_value(
                candidate,
                "ETF Score",
                "etf_score",
                default=None,
            ),
        )

        etf_signal = _first_value(
            analysis,
            "etf_signal",
            "ETF Signal",
            default=_first_value(
                candidate,
                "ETF Signal",
                "etf_signal",
                default=None,
            ),
        )

        if etf_score is not None:
            compact["etf_score"] = _safe_float(etf_score)

        if etf_signal is not None:
            compact["etf_signal"] = _clean_text(etf_signal)

    # ------------------------------------------------------------
    # Stock evidence
    # ------------------------------------------------------------

    else:

        stock_fields = {
            "investment_score": (
                "investment_score",
                "Investment Score",
            ),
            "technical_score": (
                "technical_score",
                "Technical Score",
            ),
            "quality_score": (
                "quality_score",
                "Quality Score",
            ),
            "growth_score": (
                "growth_score",
                "Growth Score",
            ),
            "risk_score": (
                "risk_score",
                "Risk Score",
            ),
        }

        for output_key, source_keys in stock_fields.items():

            value = _first_value(
                analysis,
                *source_keys,
                default=_first_value(
                    candidate,
                    *source_keys,
                    default=None,
                ),
            )

            if value is not None:
                compact[output_key] = _safe_float(value)

        # --------------------------------------------------------
        # Signal
        # --------------------------------------------------------

        signal = _first_value(
            analysis,
            "signal",
            "Signal",
            "Momentum Signal",
            default=_first_value(
                candidate,
                "signal",
                "Signal",
                "Momentum Signal",
                default=None,
            ),
        )

        if signal is not None:
            compact["signal"] = _clean_text(signal).upper()

        # --------------------------------------------------------
        # Price / technical evidence
        # --------------------------------------------------------

        technical_fields = {
            "current_price": (
                "current_price",
                "Current Price",
                "price",
                "Price",
            ),
            "ma50": (
                "ma50",
                "MA50",
                "SMA50",
            ),
            "ma200": (
                "ma200",
                "MA200",
                "SMA200",
            ),
            "rsi": (
                "rsi",
                "RSI",
            ),
            "return_3m_pct": (
                "return_3m_pct",
                "Return 3M %",
                "3M Return %",
            ),
        }

        for output_key, source_keys in technical_fields.items():

            value = _first_value(
                analysis,
                *source_keys,
                default=_first_value(
                    candidate,
                    *source_keys,
                    default=None,
                ),
            )

            if value is not None:
                compact[output_key] = _safe_float(value)

    # ------------------------------------------------------------
    # Historical / learning evidence
    # ------------------------------------------------------------

    historical = _first_value(
        intelligence,
        "historical_evidence",
        "Historical Evidence",
        "learning",
        "Learning",
        default=_first_value(
            analysis,
            "historical_evidence",
            "Historical Evidence",
            "learning",
            "Learning",
            default=_first_value(
                candidate,
                "historical_evidence",
                "Historical Evidence",
                "learning",
                "Learning",
                default={},
            ),
        ),
    )

    if isinstance(historical, dict) and historical:

        compact_historical = {}

        historical_fields = {
            "observations": (
                "observations",
                "Observations",
            ),
            "win_rate_pct": (
                "win_rate_pct",
                "Win Rate %",
                "win_rate",
            ),
            "average_return_pct": (
                "average_return_pct",
                "Average Return %",
                "average_return",
            ),
            "reliability": (
                "reliability",
                "Reliability",
            ),
            "score_bucket_observations": (
                "score_bucket_observations",
                "Score Bucket Observations",
            ),
            "score_bucket_win_rate_pct": (
                "score_bucket_win_rate_pct",
                "Score Bucket Win Rate %",
            ),
            "learning_adjusted_score": (
                "learning_adjusted_score",
                "Learning Adjusted Score",
            ),
        }

        for output_key, source_keys in historical_fields.items():

            value = _first_value(
                historical,
                *source_keys,
                default=None,
            )

            if value is not None:

                if output_key == "reliability":
                    compact_historical[output_key] = _clean_text(value).upper()
                else:
                    compact_historical[output_key] = _safe_float(value)

        if compact_historical:
            compact["historical_evidence"] = compact_historical

    # ------------------------------------------------------------
    # Deterministic confidence
    #
    # Structured decision confidence is authoritative.
    # Do not emit a synthetic 0.0 where no genuine value exists.
    # ------------------------------------------------------------

    deterministic_confidence = _first_value(
        decision,
        "Deterministic Confidence",
        "deterministic_confidence",
        "Confidence",
        "confidence",
        default=_first_value(
            candidate,
            "Deterministic Confidence",
            "deterministic_confidence",
            "Confidence",
            "confidence",
            default=None,
        ),
    )

    if deterministic_confidence is not None:
        compact["deterministic_confidence"] = _safe_float(
            deterministic_confidence
        )

    # ------------------------------------------------------------
    # Decision reason
    # ------------------------------------------------------------

    decision_reason = _clean_text(
        _first_value(
            decision,
            "Reason",
            "reason",
            "Decision Reason",
            "decision_reason",
            default=_first_value(
                candidate,
                "Reason",
                "reason",
                "Decision Reason",
                "decision_reason",
                default="",
            ),
        )
    )

    if decision_reason:
        compact["decision_reason"] = decision_reason

    # ------------------------------------------------------------
    # Technical reasons / risks
    # ------------------------------------------------------------

    technical_reasons = _first_value(
        analysis,
        "technical_reasons",
        "Technical Reasons",
        default=_first_value(
            candidate,
            "technical_reasons",
            "Technical Reasons",
            default=None,
        ),
    )

    if isinstance(technical_reasons, list) and technical_reasons:
        compact["technical_reasons"] = technical_reasons

    technical_risks = _first_value(
        analysis,
        "technical_risks",
        "Technical Risks",
        default=_first_value(
            candidate,
            "technical_risks",
            "Technical Risks",
            default=None,
        ),
    )

    if isinstance(technical_risks, list) and technical_risks:
        compact["technical_risks"] = technical_risks

    recommendation_risks = _first_value(
        intelligence,
        "recommendation_risks",
        "Recommendation Risks",
        default=_first_value(
            candidate,
            "recommendation_risks",
            "Recommendation Risks",
            default=None,
        ),
    )

    if isinstance(recommendation_risks, list) and recommendation_risks:
        compact["recommendation_risks"] = recommendation_risks

    # ------------------------------------------------------------
    # Market intelligence
    # ------------------------------------------------------------

    market_intelligence = candidate.get(
        "market_intelligence",
        {},
    )

    if not isinstance(market_intelligence, dict):
        market_intelligence = {}

    compact["market_intelligence"] = market_intelligence

    return compact

# ============================================================
# Compact portfolio context
# ============================================================

def _build_compact_portfolio(portfolio: dict) -> dict:
    """Extract portfolio facts material to the proposed action."""
    if not isinstance(portfolio, dict):
        portfolio = {}

    summary = portfolio.get("portfolio", portfolio)
    if not isinstance(summary, dict):
        summary = {}

    return {
        "total_market_value": _safe_float(
            summary.get("total_market_value", 0.0)
        ),
        "cash": _safe_float(
            summary.get("cash", 0.0)
        ),
        "largest_position_pct": _safe_float(
            summary.get("largest_position_pct", 0.0)
        ),
        "largest_position_ticker": _clean_text(
            summary.get("largest_position_ticker", "")
        ),
        "stock_count": int(
            _safe_float(summary.get("stock_count", 0))
        ),
        "etf_count": int(
            _safe_float(summary.get("etf_count", 0))
        ),
        "sector_count": int(
            _safe_float(summary.get("sector_count", 0))
        ),
    }


# ============================================================
# Compact deterministic decision
# ============================================================

def _build_compact_decision(decision: dict) -> dict:
    """Extract the deterministic decision fields."""

    if not isinstance(decision, dict):
        decision = {}

    evidence = decision.get("Evidence Assessment", {})

    if not isinstance(evidence, dict):
        evidence = {}

    proposed_action = _clean_text(
        _first_value(
            decision,
            "Proposed Action",
            default="HOLD",
        )
    ).upper() or "HOLD"

    decision_support = _clean_text(
        _first_value(
            decision,
            "Decision Support",
            default=_first_value(
                evidence,
                "Decision Support",
                default="UNKNOWN",
            ),
        )
    ).upper() or "UNKNOWN"

    # ------------------------------------------------------------
    # Explain the deterministic meaning of Decision Support.
    #
    # This prevents an LLM from interpreting CONDITIONAL as an
    # instruction to prefer HOLD. The proposed action remains the
    # deterministic portfolio action unless governance says otherwise.
    # ------------------------------------------------------------

    if decision_support == "SUPPORTED":

        decision_support_interpretation = (
            "The deterministic evidence supports the proposed action."
        )

    elif decision_support == "CONDITIONAL":

        decision_support_interpretation = (
            "The proposed action passed deterministic governance, but "
            "the supporting evidence contains caveats or uncertainty that "
            "should be independently reviewed. CONDITIONAL does not mean "
            "that HOLD is preferred and does not, by itself, contradict "
            "the proposed action."
        )

    elif decision_support == "UNSUPPORTED":

        decision_support_interpretation = (
            "The deterministic evidence does not adequately support the "
            "proposed action."
        )

    else:

        decision_support_interpretation = (
            "The deterministic decision support classification is unknown."
        )

    return {

        "proposed_action": proposed_action,

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

        "evidence_strength": _clean_text(
            _first_value(
                decision,
                "Evidence Strength",
                default=_first_value(
                    evidence,
                    "Evidence Strength",
                    default="UNKNOWN",
                ),
            )
        ).upper() or "UNKNOWN",

        "decision_support": decision_support,

        "decision_support_interpretation": (
            decision_support_interpretation
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
            decision.get("Reason", "")
        ),

    }

# ============================================================
# Review prompt
# ============================================================

def build_review_prompt(
    candidate: dict,
    portfolio: dict,
    decision: dict,
) -> str:
    """
    Build a compact, action-aware governance prompt.

    The reviewer is asked one question:

        Is there a material reason to disagree with the
        deterministic portfolio proposal?

    It must not invent a new stock thesis or treat normal score
    component differences as contradictions.
    """

    c = _build_compact_candidate(candidate)
    p = _build_compact_portfolio(portfolio)
    d = _build_compact_decision(decision)
    action = d["proposed_action"]

    if c["asset_type"] == "ETF":
        asset_guidance = (
            "This is an ETF. Evaluate ONLY ETF Score, ETF Signal, "
            "portfolio fit, evidence quality and supplied historical evidence. "
            "Stock-only fields are not applicable unless explicitly supplied. "
            "Never infer a value for an omitted field and never treat a stock field as zero."
        )
    else:
        asset_guidance = (
            "This is a STOCK. Evaluate ONLY the stock metrics and portfolio evidence "
            "explicitly present in the supplied evidence. Investment Score, Technical "
            "Score, Quality Score, Growth Score, Signal, risk, current price, moving "
            "averages and RSI may only be referenced if their corresponding values are "
            "actually supplied. Never infer, reconstruct or assume an omitted field. "
        )

    if action == "BUY NEW":
        action_guidance = (
            "Assess whether the supplied evidence collectively justifies opening a new position. "
            "Immature historical evidence lowers certainty but is not negative evidence."
        )
    elif action == "BUY MORE":
        action_guidance = (
            "Assess the INCREMENTAL case for adding capital to the EXISTING position. "
            "Do not simply assess whether the security is attractive. Determine whether "
            "the supplied evidence supports increasing the existing position rather than "
            "leaving it unchanged. "
            "Before choosing ACCEPT, CHALLENGE or REJECT, explicitly weigh the evidence "
            "supporting BUY MORE against the evidence opposing BUY MORE. "
            "Consider the relationships between the supplied metrics rather than treating "
            "individual scores in isolation. Where supplied, consider Investment Score, "
            "Technical Score, Quality Score, Growth Score, Signal, risk, current price, "
            "MA50, MA200, RSI, historical signal performance, score-bucket learning and "
            "other explicitly supplied investment evidence. "
            "Distinguish three questions: (1) is the security attractive, (2) is the "
            "existing position suitable for additional capital, and (3) is BUY MORE "
            "better supported than HOLDING the existing position unchanged. "
            "A security can be attractive without BUY MORE being justified. "
            "Conversely, BUY MORE can be justified without perfect evidence. "
            "Do not treat missing or incomplete evidence as negative evidence. "
            "Do not invent missing information. "
            "ACCEPT means the supplied evidence supports the incremental BUY MORE proposal. "
            "CHALLENGE means the evidence is insufficient, uncertain or mixed to establish "
            "that adding capital is preferable to leaving the position unchanged. "
            "REJECT means the supplied evidence contains a specific, substantive reason "
            "why additional capital should NOT be added. "
            "Do not use REJECT merely because evidence is incomplete, immature, uncertain "
            "or insufficient. "
            "The reason must identify the actual evidence balance and must not merely say "
            "'insufficient grounds' without explaining what evidence supports or opposes "
            "the proposed action. "
            "Assess only investment evidence, signal evidence, evidence quality, historical "
            "evidence and any explicitly supplied portfolio-governance evidence that is not "
            "based on allocation, position size or capital sizing. "
        )

    elif action in {"REDUCE", "SELL"}:
        action_guidance = (
            "Assess whether the supplied evidence gives a sufficiently strong reason to reduce or "
            "exit the existing position. Distinguish material contradiction from incomplete evidence."
        )
    else:
        action_guidance = (
            "For HOLD, ACCEPT is the normal outcome unless supplied evidence contains a material "
            "contradiction or portfolio concern requiring change."
        )

    return f"""You are an independent portfolio governance reviewer.

Review the deterministic proposed action using ONLY the supplied CANDIDATE,

PORTFOLIO, DETERMINISTIC DECISION and MARKET & EVENT INTELLIGENCE evidence.

Do not generate a new recommendation. Review the proposed ACTION exactly as
given.

Your task is analytical, not merely a test of whether the action is proven.

FIRST analyse the evidence:

1. Identify the strongest evidence SUPPORTING the proposed action.
2. Identify the strongest evidence AGAINST the proposed action.
3. Identify the most important decision risk or limitation.
4. Decide whether the overall evidence supports, is insufficient for, or
   materially contradicts the proposed action.

Use relationships between supplied metrics rather than interpreting one metric
in isolation.

For STOCKS, where supplied, consider Investment Score, Technical Score,
Quality Score, Growth Score, Signal, Risk Score, current price, MA50, MA200,
RSI, historical signal performance, score-bucket learning and other supplied
investment evidence.

For ETFs, use only the ETF-specific evidence actually supplied.

Never invent, reconstruct or assume a missing field.

MARKET & EVENT INTELLIGENCE:

Market & Event Intelligence is contextual shadow-mode evidence supplied to
provide current market, company or event context.

It does NOT replace, modify or override deterministic scores, signals,
evidence scoring, historical learning or portfolio governance.

Use it only where a specific supplied contextual fact materially supports,
weakens or contradicts the proposed action.

Missing Market & Event Intelligence is neutral. Do not treat its absence as
negative evidence.

Do not invent current events, news, earnings information, sentiment or market
conditions that are not explicitly supplied.

Contextual intelligence may strengthen confidence in an action, identify a
material risk, or provide a specific action-relevant contradiction. It must
not be used to invent a new investment thesis or recommendation.

IMPORTANT REVIEW CLASSIFICATION:

ACCEPT:
The supplied evidence is directionally supportive of the proposed action and
there is no material contradiction.

CHALLENGE:
The evidence is mixed, incomplete, uncertain or insufficient to establish the
proposed action, but there is no specific substantive evidence showing that
the action itself is wrong.

REJECT:
The supplied evidence contains specific, substantive, action-specific
evidence showing that the proposed action should NOT be taken.

Lack of evidence is NOT evidence against the action.

Do NOT use REJECT merely because:
- confidence is not high;
- evidence is incomplete;
- historical evidence is immature;
- one component score is weak;
- the action is not conclusively proven;
- you would prefer another action.

Before REJECT, identify the concrete supplied fact, metric, signal or other
permitted evidence that contradicts the proposed action. If you cannot
identify one, use CHALLENGE instead.

For BUY MORE specifically, answer these three questions:

1. Is the security attractive based on the supplied evidence?
2. Does the supplied evidence support adding capital to the existing position?
3. Is BUY MORE sufficiently supported relative to simply leaving the position
   unchanged?

A security can be attractive without BUY MORE being justified.
Conversely, BUY MORE does not require perfect evidence.


BUY MORE DECISION GATE:

For BUY MORE, distinguish clearly between:

- WEAK OR INSUFFICIENT SUPPORT: use CHALLENGE.
- MIXED OR AMBIGUOUS EVIDENCE: use CHALLENGE.
- AFFIRMATIVE CONTRADICTORY EVIDENCE: use REJECT.

A low, moderate or borderline Investment Score, Technical Score,
Quality Score, Growth Score, Risk Score, Evidence Score or historical
learning result is NOT by itself evidence that BUY MORE should NOT occur.

A BUY or neutral signal is not automatically evidence against BUY MORE.

REJECT requires affirmative contradictory evidence such as an explicitly
supplied SELL or STRONG SELL signal, a clearly adverse supplied metric
relationship, or another concrete supplied fact showing that additional
capital should not be added.

If the evidence merely fails to make the BUY MORE case strongly enough,
return CHALLENGE.

For BUY NEW, assess whether the supplied evidence supports opening the new
position. Immature historical evidence reduces certainty but is not itself
negative evidence.

For HOLD, ACCEPT is appropriate when the supplied evidence supports continuing
to hold and contains no material contradiction.

For REDUCE or SELL, assess whether the supplied evidence supports reducing or
exiting. REJECT requires substantive evidence that the position should instead
be retained.

ALLOCATION AND POSITION SIZING ARE COMPLETELY OUT OF SCOPE.

Ignore any:
- current allocation percentage;
- target allocation;
- position size;
- portfolio weight;
- concentration caused by position size;
- allocation limit;
- proposed trade allocation;
- capital amount;
- relative size of the existing position.

Do not mention these in the reason.

The deterministic engine remains authoritative for supplied scores, signals,
ownership and portfolio constraints.

The reviewer is advisory only. Do not alter or reinterpret the deterministic
action.

ACTION: {action}

{asset_guidance}

{action_guidance}

CANDIDATE
{_safe_json(c)}

PORTFOLIO
{_safe_json(p)}

DETERMINISTIC DECISION
{_safe_json(d)}

MARKET & EVENT INTELLIGENCE
{_safe_json(c.get("market_intelligence", {}))}


Return ONLY valid JSON with exactly these four fields:

{{
  "review_decision": "ACCEPT|CHALLENGE|REJECT",
  "confidence": 1,
  "challenge": false,
  "reason": "One or two concise sentences based only on supplied evidence."
}}

Rules for the JSON:

- review_decision must be exactly ACCEPT, CHALLENGE or REJECT.
- challenge must be true only for CHALLENGE.
- confidence must be an integer from 1 to 100.
- confidence reflects confidence in the REVIEW DECISION, not confidence in
  the underlying investment.
- reason must cite actual supplied evidence.
- Do not say merely "insufficient evidence"; explain what evidence is present
  and why it leads to the review decision.
- For BUY MORE, explicitly address whether the supplied evidence supports
  adding capital versus leaving the existing position unchanged.
- Do not use allocation, position size or capital sizing as evidence.
- Do not invent missing information.
"""


# ============================================================
# Ollama interface
# ============================================================

def _call_ollama_once(prompt: str) -> dict:
    """Send one review request to Ollama and parse its JSON response.

    This function deliberately performs no retry. Retry policy belongs in
    ``review_ai_decision`` so provider failures and malformed model output
    can be governed differently.
    """

    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a disciplined portfolio governance reviewer. "
                    "Use only supplied evidence. Return JSON only."
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
            "num_predict": OLLAMA_NUM_PREDICT,
        },
        "keep_alive": OLLAMA_KEEP_ALIVE,
    }

    response = requests.post(
        OLLAMA_URL,
        json=payload,
        timeout=OLLAMA_TIMEOUT,
    )
    response.raise_for_status()

    response_payload = response.json()
    message = response_payload.get("message", {})
    content = message.get("content", "")

    if not content:
        raise ValueError("Ollama returned an empty response")

    try:
        result = json.loads(content.strip())
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Ollama returned malformed JSON: {exc}"
        ) from exc

    if not isinstance(result, dict):
        raise ValueError("Ollama response was not a JSON object")



    return result


def _validate_llm_response(
    response: dict,
) -> None:
    """Validate the minimum reviewer response contract.

    A syntactically valid JSON object is not necessarily a valid reviewer
    response. The governance layer therefore validates the fields required
    to make the response an auditable review before normalisation.
    """

    if not isinstance(response, dict):
        raise ValueError("LLM response was not a JSON object")

    required = {
        "review_decision",
        "confidence",
        "challenge",
        "reason",
    }

    missing = sorted(
        key for key in required
        if key not in response
    )

    if missing:
        raise ValueError(
            "LLM response missing required fields: "
            + ", ".join(missing)
        )

    review_decision = _clean_text(
        response.get("review_decision")
    ).upper()

    if review_decision not in VALID_REVIEW_DECISIONS:
        raise ValueError(
            "LLM response contains invalid review_decision: "
            f"{review_decision!r}"
        )

    confidence = _safe_float(
        response.get("confidence"),
        default=float("nan"),
    )

    if not 1.0 <= confidence <= 100.0:
        raise ValueError(
            "LLM response confidence must be between 0 and 100"
        )

    challenge = response.get("challenge")

    if isinstance(challenge, str):
        if challenge.strip().lower() not in {
            "true",
            "false",
            "yes",
            "no",
            "1",
            "0",
        }:
            raise ValueError(
                "LLM response contains invalid challenge value"
            )
    elif not isinstance(challenge, bool):
        raise ValueError(
            "LLM response challenge must be boolean"
        )

    if not _clean_text(response.get("reason")):
        raise ValueError(
            "LLM response reason must not be empty"
        )




# ============================================================
# LLM PROVIDER AND RESPONSE CACHE
# ============================================================

def _get_cache_path() -> Path:
    """Return the configured LLM response cache path."""

    return Path(LLM_CACHE_PATH)


def _load_llm_cache() -> dict:
    """Load the LLM response cache safely."""

    cache_path = _get_cache_path()

    if not cache_path.exists():
        return {}

    try:

        with cache_path.open(
            "r",
            encoding="utf-8",
        ) as handle:

            data = json.load(handle)

        return data if isinstance(data, dict) else {}

    except Exception as exc:

        print(
            f"LLM cache read failed: {exc}"
        )

        return {}


def _save_llm_cache(cache: dict) -> None:
    """Persist the LLM response cache safely."""

    cache_path = _get_cache_path()

    try:

        cache_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with cache_path.open(
            "w",
            encoding="utf-8",
        ) as handle:

            json.dump(
                cache,
                handle,
                indent=2,
                default=str,
            )

    except Exception as exc:

        print(
            f"LLM cache write failed: {exc}"
        )


def _get_cache_key(prompt: str) -> str:
    """Create a stable cache key for provider/model/prompt."""

    provider = _clean_text(
        LLM_PROVIDER
    ).lower()

    if provider == "gemini":

        model = _clean_text(
            GEMINI_MODEL
        )

    elif provider == "ollama":

        model = _clean_text(
            OLLAMA_MODEL
        )

    else:

        model = ""

    cache_input = json.dumps(
        {
            "provider": provider,
            "model": model,
            "prompt": prompt,
        },
        sort_keys=True,
    )

    return hashlib.sha256(
        cache_input.encode("utf-8")
    ).hexdigest()


def _call_gemini_once(prompt: str) -> dict:
    """Send one portfolio review request to Gemini."""

    api_key = os.getenv(
        "GEMINI_API_KEY",
        "",
    ).strip()

    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY environment variable is not configured"
        )

    client = genai.Client(
        api_key=api_key
    )

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config={
            "response_mime_type": "application/json",
            "temperature": 0,
        },
    )

    content = _clean_text(
        getattr(
            response,
            "text",
            "",
        )
    )

    if not content:
        raise ValueError(
            "Gemini returned an empty response"
        )

    try:
        result = json.loads(
            content.strip()
        )

    except json.JSONDecodeError as exc:

        raise ValueError(
            "Gemini returned malformed JSON: "
            f"{exc}. Raw response: {content[:500]!r}"
        ) from exc

    if not isinstance(result, dict):

        raise ValueError(
            "Gemini response was not a JSON object"
        )

    return result

def call_llm(prompt: str) -> dict:
    """Call the configured LLM provider with optional response caching."""

    provider = _clean_text(
        LLM_PROVIDER
    ).lower()

    if provider not in {
        "gemini",
        "ollama",
    }:

        raise ValueError(
            "Invalid LLM_PROVIDER configuration: "
            f"{LLM_PROVIDER!r}. "
            "Valid values are 'gemini' or 'ollama'."
        )

    cache_key = _get_cache_key(
        prompt
    )

    if LLM_CACHE_ENABLED:

        cache = _load_llm_cache()

        cached = cache.get(
            cache_key
        )

        if isinstance(
            cached,
            dict,
        ):

            response = cached.get(
                "response"
            )

            if isinstance(
                response,
                dict,
            ):

                print(
                    f"LLM CACHE HIT: {provider.upper()}"
                )

                return response

    print(
        f"CALLING LLM PROVIDER: {provider.upper()}"
    )

    if provider == "gemini":

        result = _call_gemini_once(
            prompt
        )

    else:

        result = _call_ollama_once(
            prompt
        )

    _validate_llm_response(
        result
    )

    if LLM_CACHE_ENABLED:

        cache = _load_llm_cache()

        cache[cache_key] = {
            "provider": provider,
            "model": (
                GEMINI_MODEL
                if provider == "gemini"
                else OLLAMA_MODEL
            ),
            "response": result,
        }

        _save_llm_cache(
            cache
        )

        print(
            f"LLM CACHE SAVED: {provider.upper()}"
        )

    return result




def call_ollama(prompt: str) -> dict:
    """Send a review request to Ollama and validate the response contract.

    Public compatibility wrapper retained for existing callers and tests.
    Retry behaviour is implemented by ``review_ai_decision``.
    """

    result = _call_ollama_once(prompt)
    _validate_llm_response(result)
    return result


def _validate_review_semantics(
    response: dict,
    candidate: dict,
) -> None:
    """Reject semantic hallucinations in LLM review reasons.

    The reviewer may only refer to evidence actually supplied in the
    candidate payload. This is especially important because the LLM can
    otherwise introduce plausible-sounding metrics that were not provided.
    """

    if not isinstance(response, dict):
        raise ValueError("LLM response was not a JSON object")

    if not isinstance(candidate, dict):
        raise ValueError("Candidate was not a JSON object")

    reason = _clean_text(response.get("reason", "")).lower()

    asset_type = _clean_text(
        _first_value(
            candidate,
            "asset_type",
            "Asset Type",
            default="STOCK",
        )
    ).upper()

    analysis = candidate.get("analysis", {})
    if not isinstance(analysis, dict):
        analysis = {}

    ownership = candidate.get("ownership", {})
    if not isinstance(ownership, dict):
        ownership = {}

    intelligence = candidate.get(
        "recommendation_intelligence",
        {},
    )
    if not isinstance(intelligence, dict):
        intelligence = {}

    # ------------------------------------------------------------
    # ETF semantic guard
    # ------------------------------------------------------------

    if asset_type == "ETF":
        forbidden = (
            "investment score",
            "technical score",
            "quality score",
            "growth score",
            "rsi",
            "moving average",
            "sma50",
            "sma200",
            "current price",
        )

        found = [
            term
            for term in forbidden
            if term in reason
        ]

        if found:
            raise ValueError(
                "ETF review reason referenced non-applicable "
                "or unsupported metric(s): "
                + ", ".join(found)
            )

        return

    # ------------------------------------------------------------
    # Stock evidence guard
    # ------------------------------------------------------------

    supplied_fields = set()

    for key, value in analysis.items():
        if value is not None and value != "":
            supplied_fields.add(key.lower())

    for key, value in ownership.items():
        if value is not None and value != "":
            supplied_fields.add(key.lower())

    for key, value in intelligence.items():
        if value is not None and value != "":
            supplied_fields.add(key.lower())

    # Candidate-level fields can also be valid evidence.
    for key, value in candidate.items():
        if value is not None and value != "":
            supplied_fields.add(key.lower())

    # Metrics/claims that require explicit evidence.
    evidence_requirements = {
        "current price": {
            "current_price",
            "price",
            "close",
        },
        "moving average": {
            "ma50",
            "ma200",
            "sma50",
            "sma200",
            "moving_average",
        },
        "sma50": {
            "sma50",
            "ma50",
        },
        "sma200": {
            "sma200",
            "ma200",
        },
        "rsi": {
            "rsi",
        },
    }

    unsupported = []

    for phrase, required_fields in evidence_requirements.items():
        if phrase in reason:
            if not supplied_fields.intersection(required_fields):
                unsupported.append(phrase)

    if unsupported:
        raise ValueError(
            "Review reason referenced unsupported evidence: "
            + ", ".join(unsupported)
        )


def _build_retry_prompt(
    original_prompt: str,
    failure: Exception,
) -> str:
    """Build a short corrective prompt after malformed/invalid output."""

    return f"""
The previous reviewer response failed the required JSON contract.

Failure:
{_clean_text(failure)}

Retry the SAME portfolio review using ONLY the evidence already supplied.
Do not change the proposed action yourself.
Do not add market data or unsupported facts.

Return ONLY one valid JSON object with EXACTLY these fields:

{{
  "review_decision": "ACCEPT",
  "confidence": 85,
  "challenge": false,
  "reason": "Short evidence-based explanation"
}}

- confidence must be a number from 1 to 100.

Rules:
- review_decision must be ACCEPT, CHALLENGE or REJECT.
- confidence must be a number from 0 to 100.
- challenge must be true or false.
- reason must be non-empty.
- No markdown.
- No code fences.
- No text before or after the JSON object.

ORIGINAL REVIEW CONTEXT

{original_prompt}
""".strip()


# Backwards-compatible alias for code/tests that may reference the old helper.
_call_ollama = _call_ollama_once


# ============================================================
# Response normalisation
# ============================================================

def _normalise_llm_response(

    llm_response: dict,

    candidate: dict,

    decision: dict,

) -> dict:

    """

    Convert raw model JSON to the stable reviewer contract.

    Ollama is subject to an additional semantic translation layer because

    the local model has demonstrated that it can use REJECT to express

    uncertainty or insufficient evidence.

    Other providers are trusted to return the reviewer contract directly.

    The final portfolio decision remains the responsibility of the

    deterministic governance / reconciliation layer.

    """

    if not isinstance(llm_response, dict):

        llm_response = {}

    # ------------------------------------------------------------

    # Extract and validate the raw LLM response

    # ------------------------------------------------------------

    review_decision = _clean_text(

        llm_response.get(

            "review_decision",

            "CHALLENGE",

        )

    ).upper()

    if review_decision not in VALID_REVIEW_DECISIONS:

        review_decision = "CHALLENGE"

    confidence = _safe_confidence(

        llm_response.get("confidence", 0.0)

    )

    challenge = llm_response.get(

        "challenge",

        review_decision != "ACCEPT",

    )

    if isinstance(challenge, str):

        challenge = challenge.strip().lower() in {

            "true",

            "yes",

            "1",

        }

    else:

        challenge = bool(challenge)

    reason = _clean_text(

        llm_response.get("reason", "")

    )

    if not reason:

        reason = "LLM review returned no detailed reason."

        confidence = min(confidence, 50.0)

    # ------------------------------------------------------------

    # Determine the proposed action

    # ------------------------------------------------------------

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

    proposed_action = _clean_text(

        proposed_action

    ).upper()

    # ------------------------------------------------------------

    # Provider-specific semantic translation
    #
    # Ollama requires a compatibility layer because it can incorrectly
    # use REJECT where the underlying reason expresses uncertainty or
    # insufficient evidence.
    #
    # Other providers are trusted to return ACCEPT / CHALLENGE / REJECT
    # directly and are not reinterpreted here.
    # ------------------------------------------------------------

    provider = _clean_text(

        LLM_PROVIDER

    ).lower()

    if provider == "ollama":

        # --------------------------------------------------------

        # Deterministic semantic classification
        #
        # The local model may return an incorrect REJECT when the
        # reason itself describes uncertainty or insufficient evidence.
        # Python owns the final interpretation of that distinction
        # for Ollama compatibility.
        # --------------------------------------------------------

        reason_lower = reason.lower()

        insufficient_evidence_phrases = (

            "insufficient evidence",

            "evidence is insufficient",

            "insufficient grounds",

            "insufficient information",

            "not enough evidence",

            "not enough information",

            "does not provide sufficient grounds",

            "does not provide enough evidence",

            "does not establish",

            "cannot establish",

            "unable to establish",

            "cannot determine",

            "unable to determine",

            "not sufficiently supported",

            "not sufficiently justified",

            "insufficiently supported",

            "evidence is mixed",

            "evidence is uncertain",

            "evidence is ambiguous",

            "evidence is incomplete",

            "mixed evidence",

            "uncertain evidence",

            "ambiguous evidence",

        )

        clearly_insufficient = any(

            phrase in reason_lower

            for phrase in insufficient_evidence_phrases

        )

        # Explicit affirmative contradiction is qualitatively
        # different from simply having a weak or incomplete
        # investment case.

        contradiction_phrases = (

            "contradicts the proposed action",

            "contradicts the action",

            "contradicts buy more",

            "contradict the proposed action",

            "contradictory to the proposed action",

            "against the proposed action",

            "against buy more",

            "should not be added",

            "should not add capital",

            "should not add additional capital",

            "additional capital should not",

            "additional capital should not be added",

            "adding capital should not",

            "adding capital is inappropriate",

            "adding capital is not appropriate",

            "buy more is inappropriate",

            "buy more is not appropriate",

            "buy more is wrong",

            "buy more is incorrect",

            "buy more should not",

            "proposed action is wrong",

            "proposed action itself is wrong",

            "position should instead be retained",

            "position should be retained",

            "should instead hold",

            "should be held instead",

        )

        explicit_contradiction = any(

            phrase in reason_lower

            for phrase in contradiction_phrases

        )

        # --------------------------------------------------------

        # BUY MORE semantic gate
        #
        # Deterministic evidence thresholds prevent Ollama from
        # turning objectively weak BUY MORE evidence into ACCEPT.
        #
        # REJECT requires affirmative contradictory evidence.
        # Weak/insufficient evidence means CHALLENGE.
        # --------------------------------------------------------

        if proposed_action == "BUY MORE":

            candidate_signal = _clean_text(

                _first_value(

                    candidate,

                    "signal",

                    "Signal",

                    "Momentum Signal",

                    default="",

                )

            ).upper()

            evidence_score = _safe_float(

                _first_value(

                    decision,

                    "Evidence Score",

                    default=_first_value(

                        candidate,

                        "evidence_score",

                        "Evidence Score",

                        default=0.0,

                    ),

                )

            )

            deterministic_confidence = _safe_float(

                _first_value(

                    candidate,

                    "deterministic_confidence",

                    "Deterministic Confidence",

                    "confidence",

                    "Confidence",

                    default=_first_value(

                        decision,

                        "Confidence",

                        default=0.0,

                    ),

                )

            )

            evidence_strength = _clean_text(

                _first_value(

                    candidate,

                    "evidence_strength",

                    "Evidence Strength",

                    default=_first_value(

                        decision,

                        "Evidence Strength",

                        default="",

                    ),

                )

            ).upper()

            signal_contradiction = candidate_signal in {

                "SELL",

                "STRONG SELL",

            }

            weak_deterministic_evidence = (

                evidence_score < 60.0

                or deterministic_confidence < 70.0

                or evidence_strength == "WEAK"

            )

            if signal_contradiction:

                review_decision = "REJECT"

                challenge = False

            elif weak_deterministic_evidence:

                review_decision = "CHALLENGE"

                challenge = True

            elif clearly_insufficient:

                review_decision = "CHALLENGE"

                challenge = True

            elif (

                review_decision == "REJECT"

                and not explicit_contradiction

            ):

                review_decision = "CHALLENGE"

                challenge = True

            elif explicit_contradiction:

                review_decision = "REJECT"

                challenge = False

        # --------------------------------------------------------

        # Generic insufficiency handling
        #
        # For Ollama, insufficient evidence is CHALLENGE,
        # not REJECT.
        # --------------------------------------------------------

        elif (

            review_decision == "REJECT"

            and clearly_insufficient

            and not explicit_contradiction

        ):

            review_decision = "CHALLENGE"

            challenge = True

    # ------------------------------------------------------------

    # Keep challenge flag consistent with the final review decision.
    #
    # This does not reinterpret the provider's decision. It only keeps
    # the stable output contract internally consistent.
    # ------------------------------------------------------------

    if review_decision == "ACCEPT":

        challenge = False

    elif review_decision == "CHALLENGE":

        challenge = True

    elif review_decision == "REJECT":

        challenge = False

    # ------------------------------------------------------------

    # Ticker

    # ------------------------------------------------------------

    ticker = _clean_text(

        _first_value(

            candidate,

            "ticker",

            "Ticker",

            default="",

        )

    )

    # ------------------------------------------------------------

    # Stable reviewer contract

    # ------------------------------------------------------------

    return {

        "Ticker": ticker,

        "LLM Assessment": review_decision,

        "LLM Confidence": confidence,

        "LLM Reason": reason,

        "LLM Decision": review_decision,

        "Review Decision": review_decision,

        "Review Confidence": confidence,

        "Review Challenge": challenge,

        "Review Reason": reason,

    }


# ============================================================
# Public reviewer interface
# ============================================================

def _review_failure(
    ticker: str,
    decision: dict,
    message: str,
    status: str,
) -> dict:
    """Return a governed non-opinion result for reviewer failure."""

    proposed_action = _first_value(
        decision,
        "Proposed Action",
        default="HOLD",
    )

    return {
        "Ticker": ticker,
        "LLM Assessment": "UNAVAILABLE",
        "LLM Confidence": 0.0,
        "LLM Reason": message,
        "LLM Decision": "UNAVAILABLE",
        "Review Decision": "UNAVAILABLE",
        "Confidence": 0.0,
        "Challenge": False,
        "Reason": message,
        "Key Points": [],
        "LLM Key Points": [],
        "Evidence Gaps": ["LLM reviewer failure"],
        "LLM Evidence Gaps": ["LLM reviewer failure"],
        "Proposed Action": proposed_action,
        "Reviewer Status": status,
    }


def review_ai_decision(
    candidate: dict,
    portfolio: dict,
    decision: dict,
) -> dict:
    """Review one deterministic decision with Ollama.

    Malformed/invalid model output receives one corrective retry. Provider
    failures such as timeouts are not retried here because they are not JSON
    reliability failures. If the retry also fails, the reviewer returns a
    governed UNAVAILABLE result rather than an investment opinion.

    The public contract is unchanged so the reconciler and final-decision
    engine do not need to know which model is used.
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

        try:

            print(f"\n===== LLM PROMPT: {ticker} =====\n{prompt}\n===== END LLM PROMPT =====\n")

            llm_response = call_llm(prompt)

            print(
                f"RAW LLM RESPONSE: {ticker} | "
                f"{json.dumps(llm_response, ensure_ascii=False)}"
            )

            _validate_review_semantics(llm_response, candidate)
            review_status = "LLM REVIEW COMPLETE"

        except (ValueError, json.JSONDecodeError) as first_failure:
            print(
                f"LLM REVIEW RETRY: {ticker} | "
                f"{first_failure}"
            )

            retry_prompt = _build_retry_prompt(
                original_prompt=prompt,
                failure=first_failure,
            )

            try:
                llm_response = call_llm(retry_prompt)
                _validate_review_semantics(llm_response, candidate)
                review_status = "LLM REVIEW RETRIED"

            except (ValueError, json.JSONDecodeError) as second_failure:
                message = (
                    "LLM reviewer failed JSON validation after retry: "
                    f"{second_failure}"
                )

                print(
                    f"LLM REVIEW FAILED: {ticker} | {message}"
                )

                return _review_failure(
                    ticker=ticker,
                    decision=decision,
                    message=message,
                    status="LLM REVIEW FAILED",
                )

        review = _normalise_llm_response(
            llm_response=llm_response,
            candidate=candidate,
            decision=decision,
        )

        # The normalised governance decision is canonical.
        # Do not allow a raw model field to contradict the
        # validated/normalised review outcome.
        llm_review = str(
            review.get(
                "Review Decision",
                review.get(
                    "LLM Decision",
                    review.get(
                        "LLM Assessment",
                        "CHALLENGE",
                    ),
                ),
            )
        ).strip().upper()


        review["LLM Review"] = llm_review
        review["Reviewer Status"] = review_status
        print(
            f"LLM REVIEW COMPLETE: {ticker} | "
            f"{review.get('LLM Assessment', 'UNKNOWN')} | "
            f"{review.get('LLM Confidence', 0)} | "
            f"{review.get('LLM Reason', '')} | "
            f"{review_status}"
        )

        return review

    except requests.exceptions.Timeout as exc:
        message = (
            f"LLM reviewer timed out after {OLLAMA_TIMEOUT}s: {exc}"
        )
        print(
            f"LLM REVIEW TIMEOUT: {ticker} | {message}"
        )

        return _review_failure(
            ticker=ticker,
            decision=decision,
            message=message,
            status="LLM UNAVAILABLE",
        )

    except requests.exceptions.RequestException as exc:
        message = (
            f"LLM provider request failed: {exc}"
        )
        print(
            f"LLM REVIEW ERROR: {ticker} | {message}"
        )

        return _review_failure(
            ticker=ticker,
            decision=decision,
            message=message,
            status="LLM UNAVAILABLE",
        )

    except Exception as exc:
        message = (
            f"Production reviewer error: {exc}"
        )
        print(
            f"LLM REVIEW ERROR: {ticker} | {message}"
        )

        return _review_failure(
            ticker=ticker,
            decision=decision,
            message=message,
            status="LLM REVIEW ERROR",
        )


# ============================================================
# Prompt inspection helper
# ============================================================

def build_review_payload(
    candidate: dict,
    portfolio: dict,
    decision: dict,
) -> dict:
    """
    Return the compact payload without calling Ollama.

    Useful for benchmarking prompt size and inspecting exactly what
    the local model receives.
    """

    return {
        "candidate": _build_compact_candidate(candidate),
        "portfolio": _build_compact_portfolio(portfolio),
        "decision": _build_compact_decision(decision),
    }


# ============================================================
# Module test
# ============================================================

# ============================================================
# DXCM reviewer test case
# ============================================================

def build_dxcm_test_case() -> tuple[dict, dict, dict]:
    """Return a representative DXCM BUY MORE governance test case."""
    candidate = {
        "ticker": "DXCM",
        "asset_type": "STOCK",
        "ownership": {
            "owned": True,
            "quantity": 10.0,
            "allocation_pct": 1.49,
            "sector": "Healthcare",
        },
        "analysis": {
            "investment_score": 84.0,
            "technical_score": 90.0,
            "quality_score": 82.0,
            "growth_score": 86.0,
            "signal": "BUY",
            "risk_score": 35.0,
        },
        "recommendation_intelligence": {
            "historical_signal_observations": 80,
            "historical_signal_win_rate_pct": 68.0,
            "historical_signal_average_return_pct": 10.0,
            "historical_signal_reliability": "RELIABLE",
            "learning_adjusted_score": 84.0,
            "score_bucket_observations": 40,
            "score_bucket_win_rate_pct": 70.0,
        },
        "rules_based_decision": {
            "action": "BUY MORE",
            "reason": "Strong investment case with a small existing allocation.",
            "confidence": 78.0,
        },
    }

    portfolio = {
        "portfolio": {
            "total_market_value": 100000.0,
            "cash": 10000.0,
            "largest_position_pct": 16.97,
            "largest_position_ticker": "NVDA",
            "stock_count": 20,
            "etf_count": 3,
            "sector_count": 8,
        }
    }

    decision = {
        "Proposed Action": "BUY MORE",
        "Investment Score": 84.0,
        "Evidence Score": 74.2,
        "Evidence Strength": "MODERATE",
        "Decision Support": "CONDITIONAL",
        "Confidence": 71.02,
        "Reason": "Strong buy evidence with moderate portfolio fit.",
    }

    return candidate, portfolio, decision


def test_dxcm_prompt() -> None:
    """Print the DXCM BUY MORE governance prompt without calling Ollama."""
    candidate, portfolio, decision = build_dxcm_test_case()
    prompt = build_review_prompt(candidate, portfolio, decision)
    print("DXCM BUY MORE TEST PROMPT")
    print(prompt)
    print()
    print("DXCM TEST EXPECTATION")
    print("- Do not assume BUY MORE is correct merely because allocation is 1.49%.")
    print("- Decide whether the supplied evidence justifies BUY MORE versus HOLD.")
    print("- Explicitly identify any material missing evidence such as sector or price data.")
    print("- Do not treat component-score differences as contradictions.")


if __name__ == "__main__":
    print("AI Portfolio Reviewer")
    test_dxcm_prompt()

