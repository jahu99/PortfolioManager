from __future__ import annotations

"""
FD-001 — Final Portfolio Decision Integrity Tests

Purpose
-------
Verify that the final portfolio decision engine preserves governed
BUY MORE decisions for existing positions such as PLTR and BBVA.

IMPORTANT
---------
This test harness does NOT assume that the final output dataframe
contains an "Existing Holding" column.

Ownership is established from the portfolio input fixture using:

    Quantity > 0
    Market Value > 0
    Allocation % > 0

The final decision output is tested only through columns actually
returned by generate_final_portfolio_decisions().

This file is a TEST HARNESS correction only.
No production code is changed by this test.
"""

import importlib
from typing import Any

import pandas as pd
import pytest


# ============================================================
# PRODUCTION IMPORT
# ============================================================

final_decision_module = importlib.import_module(
    "analysis.final_portfolio_decision"
)

generate_final_portfolio_decisions = (
    final_decision_module.generate_final_portfolio_decisions
)


# ============================================================
# GENERIC HELPERS
# ============================================================

def clean_text(
    value: Any,
    default: str = "",
) -> str:
    """Safely convert a value to normalised text."""

    if value is None:
        return default

    try:
        if pd.isna(value):
            return default
    except Exception:
        pass

    value = str(value).strip()

    return value if value else default


# ============================================================
# PORTFOLIO SUMMARY FIXTURE
# ============================================================

def make_portfolio_summary(
    ticker: str,
    allocation: float,
) -> pd.DataFrame:
    """
    Create an existing holding.

    Ownership is represented by positive quantity, positive market
    value and positive portfolio allocation.
    """

    sector = (
        "Technology"
        if ticker == "PLTR"
        else "Financial Services"
    )

    investment_score = (
        78.0
        if ticker == "PLTR"
        else 67.0
    )

    signal = (
        "BUY"
        if ticker == "PLTR"
        else "WATCH"
    )

    return pd.DataFrame(
        [
            {
                "Ticker": ticker,
                "Quantity": 100.0,
                "Market Value": 10_000.0,
                "Allocation %": allocation,
                "Asset Type": "STOCK",
                "Security Type": "STOCK",
                "Sector": sector,
                "Investment Score": investment_score,
                "Quality Score": 80.0,
                "Growth Score": 78.0,
                "Signal": signal,
            }
        ]
    )


# ============================================================
# PORTFOLIO DECISION FIXTURE
# ============================================================

def make_portfolio_decision(
    ticker: str,
) -> pd.DataFrame:
    """
    Create the proposed portfolio decision.

    Ownership is deliberately NOT represented by an
    "Existing Holding" field.

    The portfolio summary is the source of truth for ownership.
    """

    if ticker == "PLTR":

        action = "BUY MORE"
        investment_score = 78.0
        signal = "BUY"
        sector = "Technology"

    elif ticker == "BBVA":

        action = "BUY MORE"
        investment_score = 67.0
        signal = "WATCH"
        sector = "Financial Services"

    else:

        raise ValueError(
            f"Unsupported FD-001 ticker: {ticker}"
        )

    return pd.DataFrame(
        [
            {
                "Ticker": ticker,
                "Action": action,
                "Proposed Action": action,
                "Reason": (
                    "Strong current investment case."
                ),
                "Investment Score": investment_score,
                "Quality Score": 80.0,
                "Growth Score": 78.0,
                "AI Decision": action,
                "AI Conviction": "HIGH",
                "Signal": signal,
                "Sector": sector,
            }
        ]
    )


# ============================================================
# CAPITAL ALLOCATION FIXTURE
# ============================================================

def make_capital_allocation(
    ticker: str,
) -> pd.DataFrame:
    """Create the capital-allocation proposal."""

    if ticker == "PLTR":

        buy_value = 2.24
        investment_score = 78.0

    elif ticker == "BBVA":

        buy_value = 1.50
        investment_score = 67.0

    else:

        raise ValueError(
            f"Unsupported FD-001 ticker: {ticker}"
        )

    return pd.DataFrame(
        [
            {
                "Ticker": ticker,
                "Action": "BUY MORE",
                "Capital Allocation Action": "BUY MORE",
                "Investment Score": investment_score,
                "Allocation Amount": buy_value,
                "Buy Quantity": 1.0,
                "Buy Value": buy_value,
                "Released Capital": 0.0,
                "Funding Source": "DISCRETIONARY CASH",
                "Investment Rank": 1,
                "Reduction Rank": None,
                "Reason": (
                    "Strong BUY MORE opportunity."
                ),
            }
        ]
    )


# ============================================================
# AI PORTFOLIO REVIEW FIXTURE
# ============================================================

def make_portfolio_ai_review(
    ticker: str,
) -> pd.DataFrame:
    """Create the AI holding review."""

    return pd.DataFrame(
        [
            {
                "Ticker": ticker,
                "AI Holding Decision": "BUY",
                "AI Holding Conviction": "HIGH",
                "AI Holding Reasons": [
                    "Strong current opportunity"
                ],
                "AI Holding Risks": [],
                "AI Holding Actions": [
                    "Increase existing position"
                ],
                "AI Holding Review Triggers": [
                    "Investment score deteriorates"
                ],
            }
        ]
    )


# ============================================================
# PORTFOLIO MANAGER REVIEW
# ============================================================

def make_portfolio_manager_review() -> dict:
    """Create a minimal portfolio-manager review."""

    return {
        "Manager Recommendation": (
            "Selective additional capital deployment "
            "is appropriate."
        ),
        "Priority": "MEDIUM",
        "Turnover Preference": "LOW",
    }


# ============================================================
# PORTFOLIO HEALTH
# ============================================================

def make_portfolio_health() -> dict:
    """Create a low-risk synthetic portfolio-health result."""

    return {
        "Health Score": 80.0,
        "Health Status": "HEALTHY",
        "Risk Level": "NORMAL",
        "Portfolio Risk": "NORMAL",
    }


# ============================================================
# LLM REVIEW
# ============================================================

def make_llm_review(
    ticker: str,
) -> dict:
    """Create a deterministic independent LLM review."""

    return {
        "Ticker": ticker,
        "LLM Assessment": "ACCEPT",
        "LLM Review": "ACCEPT",
        "LLM Decision": "ACCEPT",
        "Review Decision": "ACCEPT",
        "Assessment": "ACCEPT",
        "LLM Confidence": 85.0,
        "Confidence": 85.0,
        "Challenge": False,
        "LLM Reason": (
            "The current investment case supports "
            "additional capital deployment."
        ),
        "Reason": (
            "The current investment case supports "
            "additional capital deployment."
        ),
        "LLM Key Points": [
            "Investment case remains strong.",
            "Existing position has capacity for additional capital.",
            "No material contradiction is present.",
        ],
        "Key Points": [
            "Investment case remains strong.",
            "Existing position has capacity for additional capital.",
            "No material contradiction is present.",
        ],
        "LLM Evidence Gaps": [],
        "Evidence Gaps": [],
        "Proposed Action": "BUY MORE",
        "Reviewer Status": "LLM REVIEW COMPLETE",
    }


# ============================================================
# RECONCILIATION FIXTURE
# ============================================================

def make_reconciliation(
    ticker: str,
) -> dict:
    """
    Create a governed BUY MORE reconciliation fixture.

    This represents an already-approved reconciliation boundary.
    It is not a test of the production reconciler.
    """

    return {
        "Ticker": ticker,
        "Status": "SUPPORTED",
        "Final Status": "SUPPORTED",
        "Reconciled Action": "BUY MORE",
        "Final Decision": "BUY MORE",
        "Final Action": "BUY MORE",
        "Deterministic Action": "BUY MORE",
        "Proposed Action": "BUY MORE",
        "LLM Review": "ACCEPT",
        "LLM Assessment": "ACCEPT",
        "LLM Confidence": 85.0,
        "Evidence Score": 74.2,
        "Evidence Strength": "STRONG",
        "Decision Support": "SUPPORTED",
        "Confidence": 71.0,
        "Automatic Approval": True,
        "automatic_approval": True,
        "Governance Flags": [],
        "Reasons": [
            (
                "BUY MORE is supported by the current "
                "investment case."
            ),
        ],
        "Final Reason": (
            "BUY MORE passed the governed decision "
            "and reconciliation checks."
        ),
    }


# ============================================================
# FINAL ENGINE CALL
# ============================================================

def call_final_engine(
    ticker: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Execute the final portfolio decision engine.

    Returns:
        result
        portfolio_summary

    Ownership is returned separately so the harness can validate
    the ownership condition without assuming an output column.
    """

    allocation = (
        2.98
        if ticker == "PLTR"
        else 1.62
    )

    portfolio_summary = make_portfolio_summary(
        ticker=ticker,
        allocation=allocation,
    )

    portfolio_decisions = make_portfolio_decision(
        ticker=ticker,
    )

    capital_allocation = make_capital_allocation(
        ticker=ticker,
    )

    portfolio_ai_review = make_portfolio_ai_review(
        ticker=ticker,
    )

    portfolio_manager_review = (
        make_portfolio_manager_review()
    )

    portfolio_health = make_portfolio_health()

    llm_review = make_llm_review(
        ticker=ticker,
    )

    llm_reviews = [
        llm_review
    ]

    reconciliation = make_reconciliation(
        ticker=ticker,
    )

    # Keep the fixture internally valid.
    assert reconciliation["Final Action"] == "BUY MORE"

    result = generate_final_portfolio_decisions(
        portfolio_summary=portfolio_summary,
        portfolio_decisions=portfolio_decisions,
        portfolio_ai_review=portfolio_ai_review,
        portfolio_manager_review=portfolio_manager_review,
        portfolio_health=portfolio_health,
        capital_allocation=capital_allocation,
        llm_reviews=llm_reviews,
    )

    return result, portfolio_summary


# ============================================================
# OWNERSHIP ASSERTION
# ============================================================

def assert_existing_position(
    portfolio_summary: pd.DataFrame,
    ticker: str,
) -> None:
    """
    Verify that the test input genuinely represents an
    existing holding.

    This replaces every dependency on an "Existing Holding"
    column in the final result.
    """

    holding = portfolio_summary.loc[
        portfolio_summary["Ticker"].astype(str).str.upper()
        == ticker.upper()
    ]

    assert not holding.empty, (
        f"{ticker} must exist in the portfolio summary"
    )

    row = holding.iloc[0]

    quantity = float(
        row["Quantity"]
    )

    market_value = float(
        row["Market Value"]
    )

    allocation = float(
        row["Allocation %"]
    )

    assert quantity > 0, (
        f"{ticker} must have positive quantity"
    )

    assert market_value > 0, (
        f"{ticker} must have positive market value"
    )

    assert allocation > 0, (
        f"{ticker} must have positive portfolio allocation"
    )


# ============================================================
# FINAL ACTION ASSERTION
# ============================================================

def assert_final_buy_more(
    result: pd.DataFrame,
    ticker: str,
) -> None:
    """Assert that the final decision remains BUY MORE."""

    assert not result.empty, (
        f"Final decision result is empty for {ticker}"
    )

    assert "Ticker" in result.columns, (
        "Final decision output must contain Ticker"
    )

    row = result.loc[
        result["Ticker"].astype(str).str.upper()
        == ticker.upper()
    ]

    assert not row.empty, (
        f"{ticker} missing from final decision output"
    )

    final_row = row.iloc[0]

    assert "Final Action" in result.columns, (
        "Final decision output must contain Final Action"
    )

    final_action = clean_text(
        final_row["Final Action"]
    ).upper()

    assert final_action == "BUY MORE", (
        f"{ticker}: expected BUY MORE, "
        f"received {final_action!r}\n\n"
        f"Result:\n{result}"
    )


# ============================================================
# FD-001 — PLTR
# ============================================================

def test_fd001_pltr():
    """
    FD-001 — PLTR BUY MORE integrity.

    PLTR is an existing holding with a low portfolio allocation
    and a strong investment score.

    Expected flow:

        existing position
            +
        BUY MORE proposal
            ↓
        final decision engine
            ↓
        BUY MORE
    """

    result, portfolio_summary = call_final_engine(
        ticker="PLTR",
    )

    assert_existing_position(
        portfolio_summary=portfolio_summary,
        ticker="PLTR",
    )

    assert_final_buy_more(
        result=result,
        ticker="PLTR",
    )


# ============================================================
# FD-001 — BBVA
# ============================================================

def test_fd001_bbva():
    """
    FD-001 — BBVA BUY MORE integrity.

    BBVA is an existing holding with a low portfolio allocation.

    Expected flow:

        existing position
            +
        BUY MORE proposal
            ↓
        final decision engine
            ↓
        BUY MORE
    """

    result, portfolio_summary = call_final_engine(
        ticker="BBVA",
    )

    assert_existing_position(
        portfolio_summary=portfolio_summary,
        ticker="BBVA",
    )

    assert_final_buy_more(
        result=result,
        ticker="BBVA",
    )


# ============================================================
# HARNESS REGRESSION TEST
# ============================================================

def test_fd001_harness_does_not_require_existing_holding_output():
    """
    Harness regression test.

    The final decision dataframe is not required to expose an
    "Existing Holding" column.

    Ownership is validated from portfolio_summary instead.
    """

    result, portfolio_summary = call_final_engine(
        ticker="PLTR",
    )

    assert_existing_position(
        portfolio_summary=portfolio_summary,
        ticker="PLTR",
    )

    assert_final_buy_more(
        result=result,
        ticker="PLTR",
    )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    pytest.main(
        [
            __file__,
            "-v",
            "-s",
        ]
    )