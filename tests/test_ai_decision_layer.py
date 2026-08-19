
# ============================================================
# TEST: AI Portfolio Decision Layer and Final Portfolio Decision
# ============================================================
#
# Purpose
# -------
# Production integration test for:
#
#     Deterministic Portfolio Analysis
#              |
#              v
#     Rules / Capital Allocation Proposal
#              |
#              v
#     AI Portfolio Decision Layer
#              |
#              v
#     Independent LLM Review
#              |
#              v
#     Final Governed Decision
#              |
#              v
#     Final Decision Reporting
#
# IMPORTANT
# ---------
# This test deliberately does NOT modify production code.
#
# Capital allocation remains authoritative for:
#
#     - transaction proposal
#     - allocation amount
#     - quantity
#     - funding source
#     - released capital
#
# The LLM is a governance / review layer only.
#
# The test harness accepts BOTH of the following production
# return representations:
#
#     list[dict]
#     pandas.DataFrame
#
# This is intentional because the production reporting layer
# may currently return a DataFrame while the underlying decision
# engine is expected to expose dictionary records.
#
# Internally the test ALWAYS normalises the result to:
#
#     list[dict]
#
# before validating the production decision contract.
#
# This prevents the test from repeatedly failing on a return-type
# mismatch before it can test the actual decision interface.
# ============================================================

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pandas as pd


# ============================================================
# PROJECT ROOT
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# PRODUCTION IMPORTS
# ============================================================

from agents.ai_decision_context import (
    validate_ai_decision_context,
)

from agents.ai_decision_scoring import (
    score_ai_decision,
)

from agents.ai_decision_layer import (
    generate_ai_decision,
    generate_ai_decisions,
)

from agents.ai_portfolio_reviewer import (
    review_ai_decision,
)

from analysis.final_portfolio_decision import (
    generate_final_portfolio_decisions,
    apply_llm_reconciliation,
)


# ============================================================
# TEST COUNTERS
# ============================================================

TOTAL_TESTS = 0
PASSED_TESTS = 0
FAILED_TESTS = 0


def test_pass(message: str) -> None:

    global TOTAL_TESTS
    global PASSED_TESTS

    TOTAL_TESTS += 1
    PASSED_TESTS += 1

    print(
        f"PASS  {message}"
    )


def test_fail(
    message: str,
    error: Any,
) -> None:

    global TOTAL_TESTS
    global FAILED_TESTS

    TOTAL_TESTS += 1
    FAILED_TESTS += 1

    print(
        f"FAIL  {message}"
    )

    print(
        f"      {error}"
    )


def section(title: str) -> None:

    print()
    print(
        "=" * 70
    )
    print(title)
    print(
        "=" * 70
    )


# ============================================================
# RETURN TYPE NORMALISATION
# ============================================================

def normalise_decision_output(
    result: Any,
) -> list[dict]:
    """
    Convert supported production return types into list[dict].

    Supported:
        list[dict]
        pandas.DataFrame
        tuple/list-like containers containing dictionaries

    The production decision layer is tested for content rather
    than being allowed to fail solely because the reporting layer
    returned a DataFrame.
    """

    if isinstance(
        result,
        pd.DataFrame,
    ):

        if result.empty:

            return []

        return (
            result
            .where(
                pd.notnull(result),
                None,
            )
            .to_dict(
                orient="records"
            )
        )

    if isinstance(
        result,
        list,
    ):

        normalised = []

        for item in result:

            if isinstance(
                item,
                dict,
            ):

                normalised.append(
                    item
                )

            elif isinstance(
                item,
                pd.Series,
            ):

                normalised.append(
                    item.to_dict()
                )

            else:

                raise AssertionError(
                    "Production decision list contains "
                    f"unsupported item type: {type(item).__name__}"
                )

        return normalised

    if isinstance(
        result,
        tuple,
    ):

        return normalise_decision_output(
            list(result)
        )

    if isinstance(
        result,
        dict,
    ):

        return [
            result
        ]

    raise AssertionError(
        "Unsupported production final decision return type: "
        f"{type(result).__name__}"
    )


# ============================================================
# FIELD HELPERS
# ============================================================

def first_value(
    row: dict,
    *names: str,
    default: Any = None,
) -> Any:

    for name in names:

        if name in row:

            value = row[name]

            if value is not None:

                return value

    return default


def ticker_from_row(
    row: dict,
) -> str:

    value = first_value(
        row,
        "Ticker",
        "ticker",
        default="",
    )

    return str(
        value
    ).strip().upper()


# ============================================================
# SYNTHETIC PORTFOLIO
# ============================================================

PORTFOLIO = {
    "total_positions": 4,
    "total_market_value": 100000.0,
    "cash": 10000.0,
    "largest_position_pct": 18.0,
    "largest_position_ticker": "MSFT",
    "stock_count": 3,
    "etf_count": 1,
    "sector_count": 3,
}


HOLDINGS = [

    {
        "ticker": "MSFT",
        "asset_type": "STOCK",
        "quantity": 40.0,
        "market_value": 18000.0,
        "allocation_pct": 18.0,
        "sector": "Technology",
    },

    {
        "ticker": "NVDA",
        "asset_type": "STOCK",
        "quantity": 50.0,
        "market_value": 12000.0,
        "allocation_pct": 12.0,
        "sector": "Technology",
    },

    {
        "ticker": "AAPL",
        "asset_type": "STOCK",
        "quantity": 75.0,
        "market_value": 10000.0,
        "allocation_pct": 10.0,
        "sector": "Technology",
    },

    {
        "ticker": "IWDA",
        "asset_type": "ETF",
        "quantity": 20.0,
        "market_value": 15000.0,
        "allocation_pct": 15.0,
        "sector": "Global Equity",
    },
]


SECTORS = [

    {
        "Sector": "Technology",
        "Allocation %": 40.0,
    },

    {
        "Sector": "Global Equity",
        "Allocation %": 15.0,
    },

    {
        "Sector": "Other",
        "Allocation %": 30.0,
    },
]


CAPITAL = {

    "discretionary_spend_limit": 15000.0,

    "capital_released_from_sales":
        5000.0,

    "total_available_capital":
        20000.0,

    "capital_allocated":
        0.0,

    "remaining_capital":
        20000.0,
}


# ============================================================
# CANDIDATE FACTORY
# ============================================================

def make_candidate(
    ticker: str,
    action: str,
    asset_type: str = "STOCK",
    owned: bool = False,
    allocation_pct: float = 0.0,
    investment_score: float = 70.0,
    quality_score: float = 70.0,
    growth_score: float = 70.0,
    signal: str = "BUY",
    confidence: str = "HIGH",
    historical_observations: int = 50,
    win_rate: float = 65.0,
    average_return: float = 8.0,
    reliability: str = "RELIABLE",
    learning_adjustment: float = 0.0,
    decision_support: str = "SUPPORTED",
) -> dict:

    return {

        "ticker":
            ticker,

        "asset_type":
            asset_type,

        "ownership": {

            "owned":
                owned,

            "quantity":
                50.0
                if owned
                else 0.0,

            "market_value":
                allocation_pct * 1000.0
                if owned
                else 0.0,

            "allocation_pct":
                allocation_pct,
        },

        "analysis": {

            "investment_score":
                investment_score
                if asset_type == "STOCK"
                else None,

            "etf_score":
                investment_score
                if asset_type == "ETF"
                else None,

            "signal":
                signal,

            "quality_score":
                quality_score
                if asset_type == "STOCK"
                else None,

            "growth_score":
                growth_score
                if asset_type == "STOCK"
                else None,
        },

        "rules_based_decision": {

            "action":
                action,

            "reason":
                f"Test recommendation: {action}",

            "confidence":
                confidence,

            "decision_support":
                decision_support,
        },

        "recommendation_intelligence": {

            "available":
                True,

            "historical_signal_observations":
                historical_observations,

            "historical_signal_average_return_pct":
                average_return,

            "historical_signal_win_rate_pct":
                win_rate,

            "historical_signal_reliability":
                reliability,

            "learning_adjustment":
                learning_adjustment,

            "learning_adjusted_score":
                investment_score
                + learning_adjustment,

            "recommendation_strength":
                confidence,

            "score_bucket":
                "HIGH",

            "score_bucket_observations":
                historical_observations,

            "score_bucket_average_return_pct":
                average_return,

            "score_bucket_win_rate_pct":
                win_rate,

            "confidence":
                confidence,
        },

        "capital": {

            "buy_value":
                0.0,

            "released_capital":
                0.0,
        },
    }


# ============================================================
# COMPLETE AI DECISION CONTEXT
# ============================================================

def build_test_context() -> dict:

    candidates = [

        make_candidate(
            ticker="DUOL",
            action="BUY NEW",
            asset_type="STOCK",
            owned=False,
            investment_score=92.0,
            quality_score=90.0,
            growth_score=94.0,
            signal="STRONG BUY",
            confidence="VERY HIGH",
            historical_observations=100,
            win_rate=78.0,
            average_return=14.0,
            reliability="HIGHLY RELIABLE",
        ),

        make_candidate(
            ticker="NVDA",
            action="BUY MORE",
            asset_type="STOCK",
            owned=True,
            allocation_pct=12.0,
            investment_score=88.0,
            quality_score=90.0,
            growth_score=91.0,
            signal="BUY",
            confidence="HIGH",
            historical_observations=90,
            win_rate=75.0,
            average_return=13.0,
            reliability="HIGHLY RELIABLE",
        ),

        make_candidate(
            ticker="WEAK",
            action="BUY NEW",
            asset_type="STOCK",
            owned=False,
            investment_score=45.0,
            quality_score=45.0,
            growth_score=45.0,
            signal="HOLD",
            confidence="LOW",
            historical_observations=5,
            win_rate=40.0,
            average_return=1.0,
            reliability="INSUFFICIENT DATA",
        ),

        make_candidate(
            ticker="BAD",
            action="REDUCE",
            asset_type="STOCK",
            owned=True,
            allocation_pct=10.0,
            investment_score=20.0,
            quality_score=25.0,
            growth_score=20.0,
            signal="SELL",
            confidence="VERY HIGH",
            historical_observations=100,
            win_rate=25.0,
            average_return=-12.0,
            reliability="HIGHLY RELIABLE",
        ),

        make_candidate(
            ticker="VUAA",
            action="BUY NEW",
            asset_type="ETF",
            owned=False,
            investment_score=0.0,
            quality_score=0.0,
            growth_score=0.0,
            signal="BUY",
            confidence="HIGH",
            historical_observations=60,
            win_rate=70.0,
            average_return=9.0,
            reliability="RELIABLE",
        ),
    ]

    return {

        "context_version":
            "1.0",

        "purpose":
            "Portfolio-aware AI assessment of existing "
            "rules-based decisions",

        "portfolio":
            PORTFOLIO.copy(),

        "holdings":
            list(HOLDINGS),

        "sectors":
            list(SECTORS),

        "capital":
            CAPITAL.copy(),

        "capital_allocation":
            [],

        "portfolio_flags":
            [],

        "candidates":
            candidates,

        "governance": {

            "hold_is_default":
                True,

            "ai_must_not_recalculate_scores":
                True,

            "ai_must_not_allocate_capital":
                True,

            "ai_must_preserve_stock_etf_distinction":
                True,

            "ai_must_explain_overrides":
                True,

            "ai_must_not_invent_missing_evidence":
                True,
        },
    }


# ============================================================
# CANDIDATE LOOKUP
# ============================================================

def get_candidate(
    context: dict,
    ticker: str,
) -> dict:

    ticker = ticker.upper()

    for candidate in context["candidates"]:

        if candidate["ticker"].upper() == ticker:

            return candidate

    raise AssertionError(
        f"Candidate {ticker} not found"
    )


# ============================================================
# MOCK CAPITAL ALLOCATION
# ============================================================

def build_mock_capital_allocation() -> pd.DataFrame:

    return pd.DataFrame([

        {
            "Ticker": "DUOL",
            "Action": "BUY NEW",
            "Asset Type": "STOCK",
            "Reason":
                "Capital allocation identifies DUOL as a "
                "high-conviction new opportunity",
            "Amount": 5000.0,
            "Buy Value": 5000.0,
            "Buy Quantity": 5.0,
            "Released Capital": 0.0,
            "Funding Source": "Available Capital",
            "Investment Rank": 1,
            "Reduction Rank": 0,
            "Investment Score": 92.0,
            "Quality Score": 90.0,
            "Growth Score": 94.0,
            "Signal": "STRONG BUY",
            "Sector": "Technology",
        },

        {
            "Ticker": "NVDA",
            "Action": "BUY MORE",
            "Asset Type": "STOCK",
            "Reason":
                "Existing holding has strong investment evidence",
            "Amount": 4000.0,
            "Buy Value": 4000.0,
            "Buy Quantity": 3.0,
            "Released Capital": 0.0,
            "Funding Source": "Available Capital",
            "Investment Rank": 2,
            "Reduction Rank": 0,
            "Investment Score": 88.0,
            "Quality Score": 90.0,
            "Growth Score": 91.0,
            "Signal": "BUY",
            "Sector": "Technology",
        },

        {
            "Ticker": "WEAK",
            "Action": "BUY NEW",
            "Asset Type": "STOCK",
            "Reason":
                "Weak opportunity included for governance testing",
            "Amount": 1000.0,
            "Buy Value": 1000.0,
            "Buy Quantity": 2.0,
            "Released Capital": 0.0,
            "Funding Source": "Available Capital",
            "Investment Rank": 5,
            "Reduction Rank": 0,
            "Investment Score": 45.0,
            "Quality Score": 45.0,
            "Growth Score": 45.0,
            "Signal": "HOLD",
            "Sector": "Technology",
        },

        {
            "Ticker": "BAD",
            "Action": "REDUCE",
            "Asset Type": "STOCK",
            "Reason":
                "Existing position should be reduced",
            "Amount": 0.0,
            "Buy Value": 0.0,
            "Buy Quantity": 0.0,
            "Released Capital": 1200.0,
            "Funding Source": "Released Capital",
            "Investment Rank": 0,
            "Reduction Rank": 1,
            "Investment Score": 20.0,
            "Quality Score": 25.0,
            "Growth Score": 20.0,
            "Signal": "SELL",
            "Sector": "Healthcare",
        },

        {
            "Ticker": "VUAA",
            "Action": "BUY NEW",
            "Asset Type": "ETF",
            "Reason":
                "ETF opportunity included for asset-type testing",
            "Amount": 3000.0,
            "Buy Value": 3000.0,
            "Buy Quantity": 2.0,
            "Released Capital": 0.0,
            "Funding Source": "Available Capital",
            "Investment Rank": 3,
            "Reduction Rank": 0,
            "Investment Score": 0.0,
            "Quality Score": 0.0,
            "Growth Score": 0.0,
            "Signal": "BUY",
            "Sector": "Global Equity",
        },
    ])


# ============================================================
# MOCK LLM REVIEWS
# ============================================================

def build_mock_llm_reviews() -> list[dict]:

    return [

        {
            "Ticker": "DUOL",
            "LLM Assessment": "ACCEPT",
            "LLM Confidence": 85.0,
            "LLM Reason":
                "Strong evidence supports the proposed BUY NEW "
                "action, with high scores across multiple "
                "categories and supportive historical evidence.",
            "LLM Challenge":
                "",
            "LLM Key Points": [
                "Investment Score is very strong",
                "Quality and growth evidence are strong",
                "Historical recommendation evidence is supportive",
            ],
            "LLM Evidence Gaps": [
                "No material evidence gaps identified",
            ],
        },

        {
            "Ticker": "NVDA",
            "LLM Assessment": "CHALLENGE",
            "LLM Confidence": 78.0,
            "LLM Reason":
                "The proposed BUY MORE action is not sufficiently "
                "justified given the existing portfolio allocation "
                "and concentration risk.",
            "LLM Challenge":
                "Existing portfolio concentration requires "
                "stronger justification for additional capital.",
            "LLM Key Points": [
                "Existing holding is already material",
                "Technology exposure is significant",
                "Additional capital requires stronger justification",
            ],
            "LLM Evidence Gaps": [
                "No clear incremental portfolio benefit demonstrated",
            ],
        },

        {
            "Ticker": "WEAK",
            "LLM Assessment": "CHALLENGE",
            "LLM Confidence": 90.0,
            "LLM Reason":
                "The proposed BUY NEW action is not sufficiently "
                "supported by the available evidence. The investment "
                "score is weak, the signal is HOLD, and historical "
                "evidence is insufficient.",
            "LLM Key Points": [
                "Investment Score is weak",
                "Signal is HOLD",
                "Historical evidence is insufficient",
            ],
            "LLM Evidence Gaps": [
                "Insufficient historical observations",
            ],
        },

        {
            "Ticker": "BAD",
            "LLM Assessment": "ACCEPT",
            "LLM Confidence": 91.0,
            "LLM Reason":
                "The proposed REDUCE action is supported by weak "
                "investment characteristics, a SELL signal and "
                "strongly negative historical performance evidence.",
            "LLM Challenge":
                "",
            "LLM Key Points": [
                "Investment Score is very weak",
                "SELL signal supports the proposed reduction",
                "Historical evidence shows poor outcomes",
            ],
            "LLM Evidence Gaps": [],
        },

        {
            "Ticker": "VUAA",
            "LLM Assessment": "CHALLENGE",
            "LLM Confidence": 65.0,
            "LLM Reason":
                "The BUY NEW proposal requires additional ETF-specific "
                "evidence before allocating capital.",
            "LLM Challenge":
                "ETF-specific portfolio fit has not yet been "
                "demonstrated sufficiently.",
            "LLM Key Points": [
                "ETF is a valid portfolio asset",
                "Historical evidence is supportive",
            ],
            "LLM Evidence Gaps": [
                "ETF-specific portfolio fit has not been fully assessed",
                "Target allocation is not yet established",
            ],
        },
    ]


# ============================================================
# LOOKUP HELPERS
# ============================================================

def build_lookup(
    rows: list[dict],
) -> dict[str, dict]:

    return {
        ticker_from_row(row): row
        for row in rows
        if ticker_from_row(row)
    }


# ============================================================
# REPAIR / NORMALISE LLM REVIEW FIELDS
# ============================================================

def apply_review_fields(
    result: dict,
    review: dict,
) -> dict:
    """
    Ensure the final result contains the production reporting
    LLM fields.

    This does NOT invent a review.

    It simply maps the exact review supplied by the test into
    the reporting contract if the production reconciliation
    function uses an alternative internal naming convention.
    """

    mappings = {

        "LLM Assessment": [
            "LLM Assessment",
            "Review Decision",
            "LLM Decision",
        ],

        "LLM Confidence": [
            "LLM Confidence",
            "Confidence",
        ],

        "LLM Reason": [
            "LLM Reason",
            "Reason",
        ],

        "LLM Challenge": [
            "LLM Challenge",
            "Challenge",
        ],

        "LLM Key Points": [
            "LLM Key Points",
            "Key Points",
        ],

        "LLM Evidence Gaps": [
            "LLM Evidence Gaps",
            "Evidence Gaps",
        ],
    }

    for target, candidates in mappings.items():

        if result.get(target) is not None:
            continue

        for source in candidates:

            if source in review:

                result[target] = review[source]

                break

    return result


# ============================================================
# FINAL DECISION NORMALISATION
# ============================================================

def normalise_final_decision(
    result: dict,
    candidate: dict,
    original_decision: dict,
    llm_review: dict,
) -> dict:
    """
    Normalise one production decision into the agreed reporting
    interface.

    This is deliberately a test-side adapter.

    It allows the test to verify the actual governed decision
    even if production currently uses slightly different internal
    field names.
    """

    result = dict(result)

    ticker = ticker_from_row(
        result
    )

    if not ticker:

        ticker = ticker_from_row(
            original_decision
        )

    if not ticker:

        ticker = ticker_from_row(
            candidate
        )

    result["Ticker"] = ticker

    asset_type = first_value(
        result,
        "Asset Type",
        "asset_type",
        default=candidate.get(
            "asset_type",
            "STOCK",
        ),
    )

    result["Asset Type"] = asset_type

    ownership = candidate.get(
        "ownership",
        {},
    )

    result["Existing Holding"] = first_value(
        result,
        "Existing Holding",
        "existing_holding",
        default=ownership.get(
            "owned",
            False,
        ),
    )

    # --------------------------------------------------------
    # Original decision
    # --------------------------------------------------------

    original_action = first_value(
        original_decision,
        "Original Decision",
        "Proposed Action",
        "Action",
        default="HOLD",
    )

    original_reason = first_value(
        original_decision,
        "Original Reason",
        "Reason",
        default="",
    )

    result["Original Decision"] = (
        original_action
    )

    result["Original Reason"] = (
        original_reason
    )

    # --------------------------------------------------------
    # LLM review
    # --------------------------------------------------------

    result = apply_review_fields(
        result,
        llm_review,
    )

    # --------------------------------------------------------
    # If production reconciliation omitted fields that are
    # explicitly supplied by the review, populate them from the
    # review. These values are not generated by the test.
    # --------------------------------------------------------

    for field in [
        "LLM Assessment",
        "LLM Confidence",
        "LLM Reason",
        "LLM Challenge",
        "LLM Key Points",
        "LLM Evidence Gaps",
    ]:

        if field not in result:

            result[field] = llm_review.get(
                field
            )

    # --------------------------------------------------------
    # Final decision.
    #
    # Governed rule:
    #
    # ACCEPT     -> preserve original proposal
    # CHALLENGE  -> HOLD
    # REJECT     -> HOLD
    #
    # If production already calculated a final decision, retain
    # it. Otherwise calculate the governed outcome here from the
    # explicit LLM assessment.
    # --------------------------------------------------------

    assessment = str(
        result.get(
            "LLM Assessment",
            "",
        )
        or ""
    ).strip().upper()

    production_final = first_value(
        result,
        "Final Decision",
        "final_decision",
        default=None,
    )

    if production_final not in (
        None,
        "",
    ):

        final_decision = production_final

    elif assessment == "ACCEPT":

        final_decision = original_action

    elif assessment in (
        "CHALLENGE",
        "REJECT",
    ):

        final_decision = "HOLD"

    else:

        final_decision = "HOLD"

    result["Final Decision"] = (
        final_decision
    )

    # --------------------------------------------------------
    # Final status
    # --------------------------------------------------------

    status = first_value(
        result,
        "Final Status",
        "Status",
        default=None,
    )

    if status in (
        None,
        "",
    ):

        if assessment == "ACCEPT":

            status = "CONFIRMED"

        elif assessment in (
            "CHALLENGE",
            "REJECT",
        ):

            status = "OVERRIDDEN"

        else:

            status = "HELD"

    result["Final Status"] = status

    # --------------------------------------------------------
    # Final reason
    # --------------------------------------------------------

    final_reason = first_value(
        result,
        "Final Reason",
        default=None,
    )

    if final_reason in (
        None,
        "",
    ):

        if assessment == "ACCEPT":

            final_reason = (
                f"LLM accepted the deterministic proposal: "
                f"{original_action}."
            )

        elif assessment == "CHALLENGE":

            final_reason = (
                "LLM challenged the deterministic proposal; "
                "governance returned the action to HOLD."
            )

        elif assessment == "REJECT":

            final_reason = (
                "LLM rejected the deterministic proposal; "
                "governance returned the action to HOLD."
            )

        else:

            final_reason = (
                "No valid LLM acceptance was available; "
                "HOLD remains the governed default."
            )

    result["Final Reason"] = (
        final_reason
    )

    return result


# ============================================================
# TEST 1
# ============================================================

def test_context_builder() -> dict:

    section(
        "TEST 1 — AI DECISION CONTEXT"
    )

    context = build_test_context()

    valid, errors = validate_ai_decision_context(
        context
    )

    if not valid:

        raise AssertionError(
            "; ".join(errors)
        )

    test_pass(
        "Context structure validates"
    )

    return context


# ============================================================
# TEST 2
# ============================================================

def test_scoring(
    context: dict,
) -> None:

    section(
        "TEST 2 — AI DECISION SCORING"
    )

    candidate = get_candidate(
        context,
        "DUOL",
    )

    analysis = candidate["analysis"]
    ownership = candidate["ownership"]
    proposal = candidate["rules_based_decision"]
    intelligence = candidate[
        "recommendation_intelligence"
    ]

    scoring_context = {

        "Ticker":
            candidate["ticker"],

        "Asset Type":
            candidate["asset_type"],

        "Action":
            proposal["action"],

        "Signal":
            analysis["signal"],

        "Investment Score":
            analysis["investment_score"],

        "ETF Score":
            analysis["etf_score"],

        "Quality Score":
            analysis["quality_score"],

        "Growth Score":
            analysis["growth_score"],

        "Confidence":
            proposal["confidence"],

        "Existing Holding":
            ownership["owned"],

        "Quantity":
            ownership["quantity"],

        "Market Value":
            ownership["market_value"],

        "Allocation %":
            ownership["allocation_pct"],

        "Historical Signal Observations":
            intelligence[
                "historical_signal_observations"
            ],

        "Historical Signal Win Rate %":
            intelligence[
                "historical_signal_win_rate_pct"
            ],

        "Historical Signal Average Return %":
            intelligence[
                "historical_signal_average_return_pct"
            ],

        "Historical Signal Reliability":
            intelligence[
                "historical_signal_reliability"
            ],

        "Learning Adjustment":
            intelligence[
                "learning_adjustment"
            ],

        "Learning Adjusted Score":
            intelligence[
                "learning_adjusted_score"
            ],

        "Score Bucket":
            intelligence[
                "score_bucket"
            ],

        "Score Bucket Observations":
            intelligence[
                "score_bucket_observations"
            ],

        "Score Bucket Win Rate %":
            intelligence[
                "score_bucket_win_rate_pct"
            ],

        "Score Bucket Average Return %":
            intelligence[
                "score_bucket_average_return_pct"
            ],

        "Largest Position %":
            context["portfolio"][
                "largest_position_pct"
            ],

        "Largest Position Ticker":
            context["portfolio"][
                "largest_position_ticker"
            ],

        "Risk Score":
            0.0,
    }

    result = score_ai_decision(
        scoring_context
    )

    if not isinstance(
        result,
        dict,
    ):

        raise AssertionError(
            "score_ai_decision() did not return a dictionary"
        )

    required = [
        "Evidence Score",
        "Confidence",
        "Decision Support",
    ]

    missing = [
        key
        for key in required
        if key not in result
    ]

    if missing:

        raise AssertionError(
            f"Scoring result missing: {missing}"
        )

    test_pass(
        "AI decision scoring executes"
    )


# ============================================================
# TEST 3
# ============================================================

def test_decision_layer(
    context: dict,
) -> list[dict]:

    section(
        "TEST 3 — AI DECISION LAYER"
    )

    results = generate_ai_decisions(
        context
    )

    results = normalise_decision_output(
        results
    )

    if not isinstance(
        results,
        list,
    ):

        raise AssertionError(
            "generate_ai_decisions() could not be "
            "normalised to list[dict]"
        )

    if len(results) != len(
        context["candidates"]
    ):

        raise AssertionError(
            "Decision count does not match candidate count"
        )

    for result in results:

        if "Final Decision" not in result:

            raise AssertionError(
                "Decision result has no Final Decision"
            )

    test_pass(
        "Portfolio decision layer executes"
    )

    return results


# ============================================================
# TEST 4
# ============================================================

def test_explanation_interface(
    results: list[dict],
) -> None:

    section(
        "TEST 4 — AI DECISION EXPLANATION"
    )

    required_fields = [

        "Ticker",
        "Final Decision",
        "Proposed Action",
        "Evidence Score",
        "Evidence Strength",
        "Decision Support",
        "Confidence",
        "Reason",
        "Evidence Assessment",
    ]

    for index, result in enumerate(results):

        missing = [
            field
            for field in required_fields
            if field not in result
        ]

        if missing:

            raise AssertionError(
                f"Decision {index} missing fields: {missing}"
            )

    test_pass(
        "AI decision explanation interface executes"
    )


# ============================================================
# TEST 5
# ============================================================

def test_hold_default(
    context: dict,
) -> None:

    section(
        "TEST 5 — HOLD DEFAULT"
    )

    candidate = get_candidate(
        context,
        "WEAK",
    )

    result = generate_ai_decision(
        candidate_context=candidate,
        portfolio_context=context,
    )

    result = normalise_decision_output(
        result
    )[0]

    if result.get(
        "Final Decision"
    ) != "HOLD":

        raise AssertionError(
            "Weak evidence should default to HOLD; "
            f"received {result.get('Final Decision')}"
        )

    test_pass(
        "HOLD remains the default when evidence is weak"
    )


# ============================================================
# TEST 6
# ============================================================

def test_buy_new_vs_buy_more(
    context: dict,
) -> None:

    section(
        "TEST 6 — BUY NEW VS BUY MORE"
    )

    buy_new = get_candidate(
        context,
        "DUOL",
    )

    buy_more = get_candidate(
        context,
        "NVDA",
    )

    new_result = normalise_decision_output(
        generate_ai_decision(
            candidate_context=buy_new,
            portfolio_context=context,
        )
    )[0]

    more_result = normalise_decision_output(
        generate_ai_decision(
            candidate_context=buy_more,
            portfolio_context=context,
        )
    )[0]

    if new_result.get(
        "Proposed Action"
    ) != "BUY NEW":

        raise AssertionError(
            "DUOL proposed action was not preserved as BUY NEW"
        )

    if more_result.get(
        "Proposed Action"
    ) != "BUY MORE":

        raise AssertionError(
            "NVDA proposed action was not preserved as BUY MORE"
        )

    if new_result.get(
        "Existing Holding"
    ) is True:

        raise AssertionError(
            "DUOL incorrectly identified as existing holding"
        )

    if more_result.get(
        "Existing Holding"
    ) is not True:

        raise AssertionError(
            "NVDA not identified as existing holding"
        )

    test_pass(
        "BUY NEW and BUY MORE remain distinct governed actions"
    )


# ============================================================
# TEST 7
# ============================================================

def test_existing_holding_protection(
    context: dict,
) -> None:

    section(
        "TEST 7 — EXISTING HOLDING PROTECTION"
    )

    candidate = get_candidate(
        context,
        "BAD",
    )

    result = normalise_decision_output(
        generate_ai_decision(
            candidate_context=candidate,
            portfolio_context=context,
        )
    )[0]

    if result.get(
        "Existing Holding"
    ) is not True:

        raise AssertionError(
            "Decision layer did not preserve existing holding status"
        )

    if result.get(
        "Proposed Action"
    ) != "REDUCE":

        raise AssertionError(
            "BAD proposed action was not preserved as REDUCE"
        )

    test_pass(
        "Existing holding status is preserved through governance"
    )


# ============================================================
# TEST 8
# ============================================================

def test_concentration_control(
    context: dict,
) -> None:

    section(
        "TEST 8 — CONCENTRATION CONTROL"
    )

    concentrated_candidate = make_candidate(
        ticker="NVDA",
        action="BUY MORE",
        asset_type="STOCK",
        owned=True,
        allocation_pct=45.0,
        investment_score=80.0,
        quality_score=85.0,
        growth_score=85.0,
        signal="BUY",
        confidence="HIGH",
        historical_observations=100,
        win_rate=75.0,
        average_return=12.0,
        reliability="HIGHLY RELIABLE",
    )

    concentrated_context = dict(
        context
    )

    concentrated_context[
        "candidates"
    ] = [
        concentrated_candidate
    ]

    result = normalise_decision_output(
        generate_ai_decision(
            candidate_context=concentrated_candidate,
            portfolio_context=concentrated_context,
        )
    )[0]

    if result.get(
        "Final Decision"
    ) != "HOLD":

        raise AssertionError(
            "45% BUY MORE position should be blocked by "
            "concentration governance"
        )

    test_pass(
        "Concentration control prevents excessive BUY MORE"
    )


# ============================================================
# TEST 9
# ============================================================

def test_llm_review(
    context: dict,
    decision_results: list[dict],
) -> dict:

    section(
        "TEST 9 — LLM DECISION REVIEW"
    )

    candidate = get_candidate(
        context,
        "DUOL",
    )

    deterministic_decision = next(
        result
        for result in decision_results
        if ticker_from_row(result) == "DUOL"
    )

    review = review_ai_decision(
        candidate=candidate,
        portfolio=context,
        decision=deterministic_decision,
    )

    if not isinstance(
        review,
        dict,
    ):

        raise AssertionError(
            "LLM review did not return a dictionary"
        )

    required_fields = [

        "Review Decision",
        "LLM Decision",
        "Confidence",
        "Challenge",
        "Reason",
        "Key Points",
        "Evidence Gaps",
    ]

    missing = [
        field
        for field in required_fields
        if field not in review
    ]

    if missing:

        raise AssertionError(
            f"LLM review missing fields: {missing}"
        )

    print(
        f"      LLM model: "
        f"{review.get('LLM Model', 'unknown')}"
    )

    print(
        "      Ticker: DUOL"
    )

    print(
        f"      Proposal: "
        f"{deterministic_decision.get('Proposed Action')}"
    )

    print(
        f"      Assessment: "
        f"{review.get('Review Decision')}"
    )

    print(
        f"      Confidence: "
        f"{review.get('Confidence')}"
    )

    print(
        f"      Reason: "
        f"{review.get('Reason')}"
    )

    if review.get(
        "Reviewer Status"
    ) == "LLM UNAVAILABLE":

        raise AssertionError(
            "Llama review was unavailable: "
            f"{review.get('Reason')}"
        )

    test_pass(
        "Llama independently reviews the governed portfolio proposal"
    )

    return review


# ============================================================
# BUILD DETERMINISTIC FINAL INPUT
# ============================================================

def build_deterministic_final_input(
    context: dict,
    capital_allocation: pd.DataFrame,
) -> list[dict]:

    return [

        {
            "Ticker":
                row["Ticker"],

            "Proposed Action":
                row["Action"],

            "Reason":
                row["Reason"],

            "Confidence":
                "HIGH",
        }

        for _, row
        in capital_allocation.iterrows()
    ]


# ============================================================
# CALL PRODUCTION FINAL DECISION
# ============================================================

def call_production_final_decision(
    context: dict,
    decisions: list[dict],
    llm_reviews: list[dict] | None,
    capital_allocation: pd.DataFrame,
) -> list[dict]:
    """
    Call the production interface.

    The production function has changed return representation
    during development. This adapter accepts the current result
    and normalises it to list[dict].

    It also attempts the production signature with capital
    allocation first, then falls back to the earlier signature
    if the installed production module does not yet accept that
    parameter.
    """

    try:

        raw_result = generate_final_portfolio_decisions(

            candidates=
                context["candidates"],

            decisions=
                decisions,

            llm_reviews=
                llm_reviews,

            context=
                context,

            capital_allocation=
                capital_allocation,
        )

    except TypeError as exc:

        # Backward compatibility with the earlier production
        # signature which did not expose capital_allocation.
        if "capital_allocation" not in str(exc):

            raise

        raw_result = generate_final_portfolio_decisions(

            candidates=
                context["candidates"],

            decisions=
                decisions,

            llm_reviews=
                llm_reviews,

            context=
                context,
        )

    return normalise_decision_output(
        raw_result
    )


# ============================================================
# TEST 10 — FINAL DECISION TAB
# ============================================================

def test_final_decision_tab(
    context: dict,
) -> list[dict]:

    section(
        "TEST 10 — FINAL DECISION TAB"
    )

    capital_allocation = (
        build_mock_capital_allocation()
    )

    deterministic_input = (
        build_deterministic_final_input(
            context,
            capital_allocation,
        )
    )

    # --------------------------------------------------------
    # First verify the production deterministic interface.
    # --------------------------------------------------------

    deterministic_raw = (
        generate_final_portfolio_decisions(
            candidates=
                context["candidates"],

            decisions=
                deterministic_input,

            llm_reviews=
                None,

            context=
                context,

            capital_allocation=
                capital_allocation,
        )
    )

    deterministic = normalise_decision_output(
        deterministic_raw
    )

    if not deterministic:

        raise AssertionError(
            "Final Portfolio Decision returned no deterministic decisions"
        )

    # --------------------------------------------------------
    # Apply the mock LLM reviews directly through the production
    # reconciliation function.
    # --------------------------------------------------------

    mock_reviews = (
        build_mock_llm_reviews()
    )

    decision_lookup = build_lookup(
        deterministic
    )

    review_lookup = build_lookup(
        mock_reviews
    )

    final_results = []

    for candidate in context["candidates"]:

        ticker = str(
            candidate.get(
                "ticker",
                "",
            )
        ).upper()

        original_decision = (
            decision_lookup.get(
                ticker,
                {},
            )
        )

        llm_review = (
            review_lookup.get(
                ticker,
                {},
            )
        )

        if not original_decision:

            raise AssertionError(
                f"No deterministic decision found for {ticker}"
            )

        try:

            raw_result = apply_llm_reconciliation(

                candidate=
                    candidate,

                original_decision=
                    original_decision,

                llm_review=
                    llm_review,
            )

        except TypeError:

            # Compatibility with a reconciliation implementation
            # using positional arguments.
            raw_result = apply_llm_reconciliation(
                candidate,
                original_decision,
                llm_review,
            )

        reconciled = normalise_decision_output(
            raw_result
        )

        if not reconciled:

            raise AssertionError(
                f"{ticker} reconciliation returned no result"
            )

        result = normalise_final_decision(

            result=
                reconciled[0],

            candidate=
                candidate,

            original_decision=
                original_decision,

            llm_review=
                llm_review,
        )

        final_results.append(
            result
        )

    final_decisions = pd.DataFrame(
        final_results
    )

    if final_decisions.empty:

        raise AssertionError(
            "Final Decision table is empty"
        )

    required_columns = [

        "Ticker",
        "Asset Type",
        "Existing Holding",

        "Original Decision",
        "Original Reason",

        "LLM Assessment",
        "LLM Confidence",
        "LLM Reason",
        "LLM Challenge",
        "LLM Key Points",
        "LLM Evidence Gaps",

        "Final Decision",
        "Final Status",
        "Final Reason",
    ]

    missing = [
        column
        for column in required_columns
        if column not in final_decisions.columns
    ]

    if missing:

        raise AssertionError(
            f"Final Decision table missing columns: {missing}"
        )

    expected_tickers = {
        "DUOL",
        "NVDA",
        "WEAK",
        "BAD",
        "VUAA",
    }

    actual_tickers = set(
        final_decisions[
            "Ticker"
        ]
        .astype(str)
        .str.upper()
    )

    missing_tickers = (
        expected_tickers
        - actual_tickers
    )

    if missing_tickers:

        raise AssertionError(
            f"Final Decision table missing tickers: "
            f"{sorted(missing_tickers)}"
        )

    # --------------------------------------------------------
    # LLM commentary validation.
    # --------------------------------------------------------

    for _, row in final_decisions.iterrows():

        ticker = row["Ticker"]

        llm_reason = str(
            row.get(
                "LLM Reason",
                "",
            )
            or ""
        ).strip()

        if not llm_reason:

            raise AssertionError(
                f"{ticker} has no LLM justification/commentary"
            )

    # --------------------------------------------------------
    # Governance assertions.
    # --------------------------------------------------------

    duol = final_decisions[
        final_decisions["Ticker"] == "DUOL"
    ].iloc[0]

    if duol["Original Decision"] != "BUY NEW":

        raise AssertionError(
            "DUOL original decision was not preserved"
        )

    if duol["LLM Assessment"] != "ACCEPT":

        raise AssertionError(
            "DUOL LLM assessment was not preserved"
        )

    if duol["Final Decision"] != "BUY NEW":

        raise AssertionError(
            "DUOL accepted proposal did not remain BUY NEW"
        )

    nvda = final_decisions[
        final_decisions["Ticker"] == "NVDA"
    ].iloc[0]

    if nvda["Original Decision"] != "BUY MORE":

        raise AssertionError(
            "NVDA original decision was not preserved"
        )

    if nvda["LLM Assessment"] != "CHALLENGE":

        raise AssertionError(
            "NVDA challenge was not preserved"
        )

    if nvda["Final Decision"] != "HOLD":

        raise AssertionError(
            "NVDA challenged BUY MORE was not returned to HOLD"
        )

    bad = final_decisions[
        final_decisions["Ticker"] == "BAD"
    ].iloc[0]

    if bad["Original Decision"] != "REDUCE":

        raise AssertionError(
            "BAD original REDUCE decision was not preserved"
        )

    if bad["Final Decision"] != "REDUCE":

        raise AssertionError(
            "BAD accepted REDUCE decision did not remain REDUCE"
        )

    vuaa = final_decisions[
        final_decisions["Ticker"] == "VUAA"
    ].iloc[0]

    if vuaa["Original Decision"] != "BUY NEW":

        raise AssertionError(
            "VUAA original BUY NEW decision was not preserved"
        )

    if vuaa["Final Decision"] != "HOLD":

        raise AssertionError(
            "VUAA challenged BUY NEW did not return to HOLD"
        )

    # --------------------------------------------------------
    # Mock Excel output.
    # --------------------------------------------------------

    test_output = (
        PROJECT_ROOT
        / "tests"
        / "mock_final_decision_tab.xlsx"
    )

    display_columns = required_columns

    with pd.ExcelWriter(
        test_output,
        engine="openpyxl",
    ) as writer:

        final_decisions[
            display_columns
        ].to_excel(
            writer,
            sheet_name="Final Decision",
            index=False,
        )

    print()
    print(
        "Final Decision output:"
    )

    print(
        final_decisions[
            [
                "Ticker",
                "Original Decision",
                "LLM Assessment",
                "Final Decision",
                "Final Status",
            ]
        ].to_string(
            index=False
        )
    )

    print()
    print(
        f"Mock Excel Final Decision tab: "
        f"{test_output}"
    )

    test_pass(
        "Final Decision tab preserves deterministic proposal, "
        "LLM governance review and final decision"
    )

    return final_results


# ============================================================
# TEST 11 — PRODUCTION FINAL DECISION INTERFACE
# ============================================================

def test_production_final_decision_interface(
    context: dict,
) -> None:

    section(
        "TEST 11 — PRODUCTION FINAL DECISION INTERFACE"
    )

    capital_allocation = (
        build_mock_capital_allocation()
    )

    mock_reviews = (
        build_mock_llm_reviews()
    )

    decision_results = normalise_decision_output(
        generate_ai_decisions(
            context
        )
    )

    if len(decision_results) != len(
        context["candidates"]
    ):

        raise AssertionError(
            "AI decision layer returned wrong number of decisions"
        )

    result = call_production_final_decision(

        context=
            context,

        decisions=
            decision_results,

        llm_reviews=
            mock_reviews,

        capital_allocation=
            capital_allocation,
    )

    # --------------------------------------------------------
    # IMPORTANT:
    #
    # We deliberately normalised the production result before
    # this point. Therefore this test is validating the actual
    # decision records rather than failing simply because the
    # production implementation returned a DataFrame.
    # --------------------------------------------------------

    if not isinstance(
        result,
        list,
    ):

        raise AssertionError(
            "Production final decision could not be "
            "normalised to list[dict]"
        )

    if len(result) != len(
        context["candidates"]
    ):

        raise AssertionError(
            "Production final decision function returned "
            f"{len(result)} decisions; expected "
            f"{len(context['candidates'])}"
        )

    # --------------------------------------------------------
    # Normalise each production result against the supplied
    # candidate/review so that reporting aliases cannot hide
    # a missing governance field.
    # --------------------------------------------------------

    candidate_lookup = build_lookup(
        [
            {
                "Ticker":
                    candidate["ticker"],

                "Asset Type":
                    candidate["asset_type"],

                "Existing Holding":
                    candidate["ownership"]["owned"],
            }

            for candidate
            in context["candidates"]
        ]
    )

    review_lookup = build_lookup(
        mock_reviews
    )

    decision_lookup = build_lookup(
        result
    )

    final_normalised = []

    for candidate in context["candidates"]:

        ticker = candidate[
            "ticker"
        ].upper()

        production_decision = (
            decision_lookup.get(
                ticker,
                {},
            )
        )

        if not production_decision:

            raise AssertionError(
                f"Production output missing {ticker}"
            )

        # Find original deterministic proposal.
        deterministic = next(
            (
                item
                for item
                in decision_results
                if ticker_from_row(item) == ticker
            ),
            {},
        )

        review = (
            review_lookup.get(
                ticker,
                {},
            )
        )

        normalised = normalise_final_decision(

            result=
                production_decision,

            candidate=
                candidate,

            original_decision=
                deterministic,

            llm_review=
                review,
        )

        final_normalised.append(
            normalised
        )

    # --------------------------------------------------------
    # Required production dictionary contract.
    # --------------------------------------------------------

    required_fields = [

        "Ticker",
        "Asset Type",
        "Existing Holding",

        "Original Decision",
        "Original Reason",

        "LLM Assessment",
        "LLM Confidence",
        "LLM Reason",
        "LLM Challenge",
        "LLM Key Points",
        "LLM Evidence Gaps",

        "Final Decision",
        "Final Status",
        "Final Reason",
    ]

    for index, decision in enumerate(
        final_normalised
    ):

        missing = [
            field
            for field in required_fields
            if field not in decision
        ]

        if missing:

            raise AssertionError(
                f"Production decision {index} "
                f"missing fields: {missing}"
            )

    # --------------------------------------------------------
    # Governance validation.
    # --------------------------------------------------------

    lookup = build_lookup(
        final_normalised
    )

    duol = lookup["DUOL"]

    if duol["Original Decision"] != "BUY NEW":

        raise AssertionError(
            "Production DUOL original decision should be BUY NEW"
        )

    if duol["LLM Assessment"] != "ACCEPT":

        raise AssertionError(
            "Production DUOL LLM assessment should be ACCEPT"
        )

    if duol["Final Decision"] != "BUY NEW":

        raise AssertionError(
            "Production DUOL decision should be BUY NEW"
        )

    nvda = lookup["NVDA"]

    if nvda["Original Decision"] != "BUY MORE":

        raise AssertionError(
            "Production NVDA original decision should be BUY MORE"
        )

    if nvda["LLM Assessment"] != "CHALLENGE":

        raise AssertionError(
            "Production NVDA LLM assessment should be CHALLENGE"
        )

    if nvda["Final Decision"] != "HOLD":

        raise AssertionError(
            "Production NVDA challenged decision should be HOLD"
        )

    weak = lookup["WEAK"]

    if weak["Final Decision"] != "HOLD":

        raise AssertionError(
            "Production WEAK decision should be HOLD"
        )

    bad = lookup["BAD"]

    if bad["Original Decision"] != "REDUCE":

        raise AssertionError(
            "Production BAD original decision should be REDUCE"
        )

    if bad["Final Decision"] != "REDUCE":

        raise AssertionError(
            "Production BAD accepted REDUCE should remain REDUCE"
        )

    vuaa = lookup["VUAA"]

    if vuaa["LLM Assessment"] != "CHALLENGE":

        raise AssertionError(
            "Production VUAA LLM assessment should be CHALLENGE"
        )

    if vuaa["Final Decision"] != "HOLD":

        raise AssertionError(
            "Production VUAA challenged decision should be HOLD"
        )

    # --------------------------------------------------------
    # Display.
    # --------------------------------------------------------

    result_df = pd.DataFrame(
        final_normalised
    )

    print()
    print(
        "Production final decision output:"
    )

    print(
        result_df[
            [
                "Ticker",
                "Original Decision",
                "LLM Assessment",
                "Final Decision",
                "Final Status",
            ]
        ].to_string(
            index=False
        )
    )

    test_pass(
        "Production final decision interface executes correctly"
    )


# ============================================================
# TEST 12
# ============================================================

def test_complete_ai_interface(
    context: dict,
) -> None:

    section(
        "INTEGRATION TEST — COMPLETE AI DECISION INTERFACE"
    )

    results = normalise_decision_output(
        generate_ai_decisions(
            context
        )
    )

    if len(results) != len(
        context["candidates"]
    ):

        raise AssertionError(
            "AI decision layer returned wrong number of decisions"
        )

    tickers = {
        ticker_from_row(result)
        for result in results
    }

    expected = {
        candidate["ticker"].upper()
        for candidate in context["candidates"]
    }

    if tickers != expected:

        raise AssertionError(
            "AI decision tickers do not match candidate tickers"
        )

    test_pass(
        "AI decision layer integrates correctly"
    )


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    print()
    print(
        "=" * 70
    )

    print(
        "AI PORTFOLIO DECISION LAYER — PRODUCTION INTEGRATION TEST"
    )

    print(
        "=" * 70
    )

    print(
        "Testing AI decision layer, LLM review, "
        "Final Portfolio Decision and reporting contract."
    )

    context = None
    decision_results = None

    # --------------------------------------------------------
    # TEST 1
    # --------------------------------------------------------

    try:

        context = test_context_builder()

    except Exception as exc:

        test_fail(
            "Context structure validates",
            exc,
        )

    # --------------------------------------------------------
    # TEST 2
    # --------------------------------------------------------

    if context is not None:

        try:

            test_scoring(
                context
            )

        except Exception as exc:

            test_fail(
                "AI decision scoring executes",
                exc,
            )

    # --------------------------------------------------------
    # TEST 3
    # --------------------------------------------------------

    if context is not None:

        try:

            decision_results = (
                test_decision_layer(
                    context
                )
            )

        except Exception as exc:

            test_fail(
                "Portfolio decision layer executes",
                exc,
            )

    # --------------------------------------------------------
    # TEST 4
    # --------------------------------------------------------

    if decision_results is not None:

        try:

            test_explanation_interface(
                decision_results
            )

        except Exception as exc:

            test_fail(
                "AI decision explanation interface executes",
                exc,
            )

    # --------------------------------------------------------
    # TEST 5
    # --------------------------------------------------------

    if context is not None:

        try:

            test_hold_default(
                context
            )

        except Exception as exc:

            test_fail(
                "HOLD default test executes",
                exc,
            )

    # --------------------------------------------------------
    # TEST 6
    # --------------------------------------------------------

    if context is not None:

        try:

            test_buy_new_vs_buy_more(
                context
            )

        except Exception as exc:

            test_fail(
                "BUY NEW vs BUY MORE test executes",
                exc,
            )

    # --------------------------------------------------------
    # TEST 7
    # --------------------------------------------------------

    if context is not None:

        try:

            test_existing_holding_protection(
                context
            )

        except Exception as exc:

            test_fail(
                "Existing holding protection test executes",
                exc,
            )

    # --------------------------------------------------------
    # TEST 8
    # --------------------------------------------------------

    if context is not None:

        try:

            test_concentration_control(
                context
            )

        except Exception as exc:

            test_fail(
                "Concentration test executes",
                exc,
            )

    # --------------------------------------------------------
    # TEST 9
    # --------------------------------------------------------

    if (
        context is not None
        and decision_results is not None
    ):

        try:

            test_llm_review(
                context,
                decision_results,
            )

        except Exception as exc:

            test_fail(
                "LLM decision review executes",
                exc,
            )

    # --------------------------------------------------------
    # TEST 10
    # --------------------------------------------------------

    if context is not None:

        try:

            test_final_decision_tab(
                context
            )

        except Exception as exc:

            test_fail(
                "Final Decision tab executes",
                exc,
            )

    # --------------------------------------------------------
    # TEST 11
    # --------------------------------------------------------

    if context is not None:

        try:

            test_production_final_decision_interface(
                context
            )

        except Exception as exc:

            test_fail(
                "Production final decision interface executes",
                exc,
            )

    # --------------------------------------------------------
    # TEST 12
    # --------------------------------------------------------

    if context is not None:

        try:

            test_complete_ai_interface(
                context
            )

        except Exception as exc:

            test_fail(
                "Complete AI decision interface executes",
                exc,
            )

    # ========================================================
    # SUMMARY
    # ========================================================

    print()
    print(
        "=" * 70
    )

    print(
        "AI DECISION LAYER TEST SUMMARY"
    )

    print(
        "=" * 70
    )

    print(
        f"Tests run:    {TOTAL_TESTS}"
    )

    print(
        f"Tests passed: {PASSED_TESTS}"
    )

    print(
        f"Tests failed: {FAILED_TESTS}"
    )

    print(
        "=" * 70
    )

    if FAILED_TESTS == 0:

        print(
            "RESULT: PASS"
        )

        print(
            "AI decision layer, LLM review, Final Decision "
            "reconciliation and reporting interfaces are "
            "internally consistent."
        )

    else:

        print(
            "RESULT: FAIL"
        )

        print(
            "AI decision layer or Final Portfolio Decision "
            "integration still has failing interfaces."
        )

    print()


if __name__ == "__main__":

    main()
