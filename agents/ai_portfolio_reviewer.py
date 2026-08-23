"""
AI Portfolio Reviewer

Purpose
-------
Use a local Ollama model to independently review a deterministic
portfolio decision produced by the governed AI Decision Layer.

This module is deliberately optimised for short, structured governance
reviews. It does not calculate investment scores or make portfolio
allocations. It reviews whether the supplied evidence supports the
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
from typing import Any

import requests


# ============================================================
# Configuration
# ============================================================

OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    "http" + chr(58) + chr(47) + chr(47) + "localhost" + chr(58) + "11434" + chr(47) + "api" + chr(47) + "chat",
)
OLLAMA_MODEL = os.getenv(
    "OLLAMA_MODEL",
    "qwen2.5:1.5b",
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
    return round(max(0.0, min(100.0, confidence)), 2)


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
    Build the minimum evidence package needed for a meaningful review.

    The reviewer still receives:
        - proposed action
        - investment / technical / quality / growth scores
        - signal and timing data
        - risk and portfolio exposure
        - sector / industry
        - historical observations and reliability
        - learning-adjusted score
        - deterministic confidence
        - relevant reasons / risks

    No new evidence is calculated here.
    """

    if not isinstance(candidate, dict):
        candidate = {}

    analysis = candidate.get("analysis", {})
    ownership = candidate.get("ownership", {})
    rules = candidate.get("rules_based_decision", {})
    intelligence = candidate.get("recommendation_intelligence", {})

    if not isinstance(analysis, dict):
        analysis = {}
    if not isinstance(ownership, dict):
        ownership = {}
    if not isinstance(rules, dict):
        rules = {}
    if not isinstance(intelligence, dict):
        intelligence = {}

    action = _first_value(
        rules,
        "action",
        default=_first_value(
            candidate,
            "Proposed Action",
            "Action",
            default="HOLD",
        ),
    )

    compact = {
        "ticker": _first_value(
            candidate,
            "ticker",
            "Ticker",
            default="",
        ),
        "asset_type": _first_value(
            candidate,
            "asset_type",
            "Asset Type",
            default="STOCK",
        ),
        "proposed_action": action,

        "investment_score": _safe_float(
            _first_value(
                analysis,
                "investment_score",
                default=_first_value(
                    candidate,
                    "Investment Score",
                    default=0.0,
                ),
            )
        ),
        "technical_score": _safe_float(
            _first_value(
                analysis,
                "technical_score",
                default=_first_value(
                    candidate,
                    "Technical Score",
                    default=0.0,
                ),
            )
        ),
        "quality_score": _safe_float(
            _first_value(
                analysis,
                "quality_score",
                default=_first_value(
                    candidate,
                    "Quality Score",
                    default=0.0,
                ),
            )
        ),
        "growth_score": _safe_float(
            _first_value(
                analysis,
                "growth_score",
                default=_first_value(
                    candidate,
                    "Growth Score",
                    default=0.0,
                ),
            )
        ),
        "signal": _first_value(
            analysis,
            "signal",
            default=_first_value(
                candidate,
                "Signal",
                "Momentum Signal",
                default="",
            ),
        ),

        "current_price": _safe_float(
            _first_value(
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
        ),
        "ma50": _safe_float(
            _first_value(
                analysis,
                "ma50",
                default=_first_value(
                    candidate,
                    "MA50",
                    "SMA50",
                    default=0.0,
                ),
            )
        ),
        "ma200": _safe_float(
            _first_value(
                analysis,
                "ma200",
                default=_first_value(
                    candidate,
                    "MA200",
                    "SMA200",
                    default=0.0,
                ),
            )
        ),
        "rsi": _safe_float(
            _first_value(
                analysis,
                "rsi",
                default=_first_value(
                    candidate,
                    "RSI",
                    default=50.0,
                ),
            )
        ),
        "return_3m_pct": _safe_float(
            _first_value(
                analysis,
                "return_3m",
                default=_first_value(
                    candidate,
                    "Return_3m",
                    "3M Return %",
                    default=0.0,
                ),
            )
        ),
        "risk_score": _safe_float(
            _first_value(
                analysis,
                "risk_score",
                default=_first_value(
                    candidate,
                    "Risk Score",
                    default=0.0,
                ),
            )
        ),

        "sector": _first_value(
            analysis,
            "sector",
            default=_first_value(
                candidate,
                "Sector",
                default="Unknown",
            ),
        ),
        "industry": _first_value(
            analysis,
            "industry",
            default=_first_value(
                candidate,
                "Industry",
                default="Unknown",
            ),
        ),

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

        "historical_observations": int(
            _safe_float(
                _first_value(
                    intelligence,
                    "historical_signal_observations",
                    default=_first_value(
                        candidate,
                        "Historical Signal Observations",
                        default=0,
                    ),
                )
            )
        ),
        "historical_win_rate_pct": _safe_float(
            _first_value(
                intelligence,
                "historical_signal_win_rate_pct",
                default=_first_value(
                    candidate,
                    "Historical Signal Win Rate %",
                    default=0.0,
                ),
            )
        ),
        "historical_average_return_pct": _safe_float(
            _first_value(
                intelligence,
                "historical_signal_average_return_pct",
                default=_first_value(
                    candidate,
                    "Historical Signal Average Return %",
                    default=0.0,
                ),
            )
        ),
        "historical_reliability": _first_value(
            intelligence,
            "historical_signal_reliability",
            default=_first_value(
                candidate,
                "Historical Signal Reliability",
                default="",
            ),
        ),
        "learning_adjusted_score": _safe_float(
            _first_value(
                intelligence,
                "learning_adjusted_score",
                default=_first_value(
                    candidate,
                    "Learning Adjusted Score",
                    default=0.0,
                ),
            )
        ),
        "score_bucket_observations": int(
            _safe_float(
                _first_value(
                    intelligence,
                    "score_bucket_observations",
                    default=_first_value(
                        candidate,
                        "Score Bucket Observations",
                        default=0,
                    ),
                )
            )
        ),
        "score_bucket_win_rate_pct": _safe_float(
            _first_value(
                intelligence,
                "score_bucket_win_rate_pct",
                default=_first_value(
                    candidate,
                    "Score Bucket Win Rate %",
                    default=0.0,
                ),
            )
        ),

        "deterministic_confidence": _safe_float(
            _first_value(
                rules,
                "confidence",
                default=_first_value(
                    candidate,
                    "Confidence",
                    default=0.0,
                ),
            )
        ),
        "decision_reason": _first_value(
            rules,
            "reason",
            default=_first_value(
                candidate,
                "Reason",
                "Original Reason",
                "Final Reason",
                default="",
            ),
        ),
        "technical_reasons": _normalise_list(
            _first_value(
                analysis,
                "technical_reasons",
                default=_first_value(
                    candidate,
                    "Technical Reasons",
                    default=[],
                ),
            )
        ),
        "technical_risks": _normalise_list(
            _first_value(
                analysis,
                "technical_risks",
                default=_first_value(
                    candidate,
                    "Technical Risks",
                    default=[],
                ),
            )
        ),
        "recommendation_risks": _normalise_list(
            _first_value(
                candidate,
                "Recommendation Risks",
                "recommendation_risks",
                default=[],
            )
        ),
    }

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

    return {
        "proposed_action": _first_value(
            decision,
            "Proposed Action",
            default="HOLD",
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
    action = str(c["proposed_action"]).upper()

    if action == "BUY NEW":
        action_guidance = (
            "Assess whether the supplied technical, quality, growth, "
            "signal and historical evidence collectively justify opening "
            "a new position. Immature historical evidence lowers certainty "
            "but does not by itself invalidate a strong current case."
        )
    elif action == "BUY MORE":
        action_guidance = (
            "Assess the INCREMENTAL case for adding capital to an existing position, "
            "not merely whether the stock is attractive. Compare BUY MORE directly with "
            "simply continuing to HOLD the existing position. Consider current allocation, "
            "position concentration, sector exposure, evidence quality, signal consistency, "
            "historical reliability and whether the supplied evidence justifies the additional "
            "capital relative to other available portfolio uses. A small existing position "
            "provides capacity for additional investment, but does not by itself justify BUY MORE."
        )
    elif action in {"REDUCE", "SELL"}:
        action_guidance = (
            "Assess whether the supplied evidence gives a sufficiently strong "
            "reason to reduce or exit the existing position. Distinguish a real "
            "contradiction from merely incomplete secondary evidence."
        )
    else:
        action_guidance = (
            "For HOLD, accept when the supplied evidence supports maintaining "
            "the position. Do not search for reasons to reject a HOLD without a "
            "material contradiction or portfolio concern."
        )

    return f"""You are an independent governance reviewer for a portfolio decision.

Review ONLY the supplied evidence. Do not invent market data, valuation,
news, catalysts, earnings, or other facts.

The deterministic engine remains authoritative for all supplied scores,
signals, ownership facts and portfolio constraints. Your job is to decide
whether there is a MATERIAL reason to disagree with its proposed action.

ACTION: {action}

{action_guidance}

CRITICAL REVIEW RULES
1. A lower Technical Score than Investment Score is NOT itself a contradiction.
2. Different Technical, Quality and Growth scores are normal because Investment
   Score is a composite.
3. Price below a moving average is bearish technical evidence; it is NOT by
   itself evidence of overvaluation.
4. Missing secondary evidence should normally LOWER CONFIDENCE, not create a
   CHALLENGE or REJECT.
5. Immature historical evidence is not negative evidence.
6. CHALLENGE only when supplied evidence materially conflicts with the proposal,
   exposes a material portfolio/governance issue, or leaves an essential gap.
7. REJECT is reserved for a proposal that is clearly inconsistent with the
   supplied evidence. Do not use REJECT merely because the case is imperfect.
8. For HOLD, ACCEPT is the normal outcome unless there is a material reason
   that the portfolio should change.
9. For BUY MORE, evaluate the incremental portfolio case: why add capital rather than simply HOLD.
10. For BUY MORE, a low existing allocation provides capacity for additional investment, but does not by itself justify BUY MORE. The supplied evidence must still establish a sufficiently strong incremental case versus HOLD.
11. If a material input such as current price, sector, portfolio exposure or historical evidence is unavailable, explicitly identify that limitation and reduce confidence rather than infer the missing information.
12. Do not challenge a BUY MORE merely because one component score is lower than another; explain the actual portfolio or evidence issue.
13. Do not recalculate the Investment Score or invent a different decision.

CANDIDATE
{_safe_json(c)}

PORTFOLIO
{_safe_json(p)}

DETERMINISTIC DECISION
{_safe_json(d)}

Return ONLY valid JSON using exactly this structure:
{{"review_decision":"ACCEPT","confidence":85,"challenge":false,"reason":"Short evidence-based explanation"}}

The reason must explain the ACCEPT / CHALLENGE / REJECT decision in one or two
sentences. For BUY MORE, explicitly state whether the incremental capital is justified
versus HOLD and cite the portfolio allocation, concentration, portfolio fit, evidence
quality or historical evidence that drove the conclusion. If a material input is missing,
state that limitation and lower confidence rather than infer the missing fact. Do not use a
component-score comparison as the sole reason. Keep the response concise.
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

    if not 0.0 <= confidence <= 100.0:
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


def call_ollama(prompt: str) -> dict:
    """Send a review request to Ollama and validate the response contract.

    Public compatibility wrapper retained for existing callers and tests.
    Retry behaviour is implemented by ``review_ai_decision``.
    """

    result = _call_ollama_once(prompt)
    _validate_llm_response(result)
    return result


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
    """Convert raw model JSON to the stable reviewer contract."""

    if not isinstance(llm_response, dict):
        llm_response = {}

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

    if challenge and review_decision == "ACCEPT":
        review_decision = "CHALLENGE"

    if not reason:
        reason = "LLM review returned no detailed reason."
        confidence = min(confidence, 50.0)

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

    return {
        "Ticker": ticker,
        "LLM Assessment": review_decision,
        "LLM Confidence": confidence,
        "LLM Reason": reason,
        "LLM Decision": review_decision,
        "Review Decision": review_decision,
        "Confidence": confidence,
        "Challenge": challenge,
        "Reason": reason,
        "Key Points": key_points,
        "LLM Key Points": key_points,
        "Evidence Gaps": evidence_gaps,
        "LLM Evidence Gaps": evidence_gaps,
        "Proposed Action": proposed_action,
        "Reviewer Status": "LLM REVIEW COMPLETE",
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
            llm_response = call_ollama(prompt)
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
                llm_response = call_ollama(retry_prompt)
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

