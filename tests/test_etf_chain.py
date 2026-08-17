
"""
test_etf_chain.py

Purpose
-------
Standalone test harness for the isolated ETF decision chain.

This test deliberately does NOT modify or invoke the stock
decisioning framework.

It tests:

    1. ETF market-data retrieval
    2. ETF technical analysis
    3. ETF portfolio decisioning
    4. ETF recommendation generation

It also tests the portfolio-aware ETF decision branches by
running the same ETF analysis against different existing
portfolio positions.

The production ETF modules remain unchanged by this test.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yfinance as yf


# ============================================================
# MAKE PROJECT ROOT IMPORTABLE
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# ETF MODULES
# ============================================================

from analysis.etf_analysis import analyse_etf
from analysis.etf_decisions import decide_etf
from analysis.etf_recommendations import (
    generate_etf_recommendation,
)

def test_negative_decision_scenarios():
    """
    Test ETF REDUCE / SELL behaviour using synthetic ETF
    analysis.

    These tests deliberately bypass market-data analysis so that
    the decision thresholds can be tested deterministically.
    """

    print()
    print()
    print("#" * 70)
    print("NEGATIVE ETF DECISION TESTS")
    print("#" * 70)

    # ========================================================
    # WEAK ETF
    # ========================================================

    weak_analysis = {
        "Ticker": "TEST",
        "Type": "ETF",
        "ETF Score": 45,
        "ETF Signal": "HOLD",
        "Current Price": 100,
        "MA50": 105,
        "MA200": 110,
        "6M Return %": -5,
        "12M Return %": -10,
        "ETF Reasons": [
            "Price below 50-day moving average",
            "Price below 200-day moving average",
        ],
        "ETF Risks": [
            "Negative momentum",
            "Weak long-term trend",
        ],
    }

    # --------------------------------------------------------
    # Meaningful position + weak score
    # --------------------------------------------------------

    decision = decide_etf(
        etf_analysis=weak_analysis,
        quantity=10,
        market_value=1000,
        portfolio_weight=5,
    )

    print()
    print("Weak ETF / 5% position")
    print(f"Decision: {decision['ETF Decision']}")
    print(f"Reduction: {decision['ETF Reduction %']}%")

    assert decision["ETF Decision"] == "REDUCE"
    assert decision["ETF Reduction %"] == 25

    print("PASS")

    # ========================================================
    # VERY WEAK ETF
    # ========================================================

    very_weak_analysis = {
        "Ticker": "TEST",
        "Type": "ETF",
        "ETF Score": 20,
        "ETF Signal": "SELL",
        "Current Price": 100,
        "MA50": 105,
        "MA200": 120,
        "6M Return %": -15,
        "12M Return %": -25,
        "ETF Reasons": [
            "Price below 50-day moving average",
            "Price below 200-day moving average",
        ],
        "ETF Risks": [
            "Severe negative momentum",
            "Weak long-term trend",
        ],
    }

    # --------------------------------------------------------
    # Meaningful position + very weak score
    # --------------------------------------------------------

    decision = decide_etf(
        etf_analysis=very_weak_analysis,
        quantity=10,
        market_value=1000,
        portfolio_weight=5,
    )

    print()
    print("Very weak ETF / 5% position")
    print(f"Decision: {decision['ETF Decision']}")
    print(f"Reduction: {decision['ETF Reduction %']}%")

    assert decision["ETF Decision"] == "SELL"
    assert decision["ETF Reduction %"] == 100

    print("PASS")

    # ========================================================
    # VERY WEAK LARGE POSITION
    # ========================================================

    decision = decide_etf(
        etf_analysis=very_weak_analysis,
        quantity=100,
        market_value=5000,
        portfolio_weight=12,
    )

    print()
    print("Very weak ETF / 12% position")
    print(f"Decision: {decision['ETF Decision']}")
    print(f"Reduction: {decision['ETF Reduction %']}%")

    assert decision["ETF Decision"] == "SELL"
    assert decision["ETF Reduction %"] == 100

    print("PASS")

    # ========================================================
    # WEAK LARGE POSITION
    # ========================================================

    decision = decide_etf(
        etf_analysis=weak_analysis,
        quantity=100,
        market_value=5000,
        portfolio_weight=12,
    )

    print()
    print("Weak ETF / 12% position")
    print(f"Decision: {decision['ETF Decision']}")
    print(f"Reduction: {decision['ETF Reduction %']}%")

    assert decision["ETF Decision"] == "REDUCE"
    assert decision["ETF Reduction %"] == 50

    print("PASS")

    print()
    print("=" * 70)
    print("NEGATIVE ETF DECISION TESTS PASSED")
    print("=" * 70)

# ============================================================
# TEST ETF
# ============================================================

def get_etf_price_data(
    yahoo_ticker: str
):
    """
    Download approximately one year of ETF price history.
    """

    data = yf.download(
        yahoo_ticker,
        period="1y",
        interval="1d",
        auto_adjust=False,
        progress=False,
    )

    if data is None or data.empty:
        raise RuntimeError(
            f"No price data returned for {yahoo_ticker}"
        )

    # --------------------------------------------------------
    # Normalise Yahoo multi-index output where required.
    # --------------------------------------------------------

    if hasattr(data.columns, "nlevels"):

        if data.columns.nlevels > 1:

            if "Close" in data.columns.get_level_values(0):

                data = data["Close"]

                if hasattr(data, "columns"):

                    if len(data.columns) == 1:
                        data = data.iloc[:, 0]

    if hasattr(data, "columns") and "Close" in data.columns:

        data = data["Close"]

    return data.dropna()


# ============================================================
# PRINT ANALYSIS
# ============================================================

def print_analysis(
    analysis: dict
):
    """
    Print ETF analysis in a readable form.
    """

    print()
    print("--- ETF ANALYSIS ---")

    for key in [
        "Ticker",
        "Type",
        "ETF Score",
        "ETF Signal",
        "Current Price",
        "MA50",
        "MA200",
        "6M Return %",
        "12M Return %",
        "ETF Reasons",
        "ETF Risks",
    ]:

        print(
            f"{key}: {analysis.get(key)}"
        )


# ============================================================
# PRINT DECISION
# ============================================================

def print_decision(
    decision: dict
):
    """
    Print ETF portfolio decision.
    """

    print()
    print("--- ETF DECISION ---")

    for key in [
        "ETF Decision",
        "ETF Decision Confidence",
        "ETF Decision Reason",
        "ETF Reduction %",
        "ETF Position",
        "ETF Score",
        "ETF Signal",
    ]:

        print(
            f"{key}: {decision.get(key)}"
        )


# ============================================================
# PRINT RECOMMENDATION
# ============================================================

def print_recommendation(
    recommendation: dict
):
    """
    Print ETF recommendation.
    """

    print()
    print("--- ETF RECOMMENDATION ---")

    for key in [
        "ETF Recommendation",
        "ETF Recommendation Text",
        "ETF Confidence",
        "ETF Primary Reason",
        "ETF Reasons",
        "ETF Risks",
    ]:

        print(
            f"{key}: {recommendation.get(key)}"
        )


# ============================================================
# RUN COMPLETE CHAIN
# ============================================================

def run_chain(
    name: str,
    yahoo_ticker: str,
    quantity: float = 0.0,
    market_value: float = 0.0,
    portfolio_weight: float = 0.0,
):
    """
    Run the complete ETF chain for a specific portfolio position.
    """

    print()
    print("=" * 70)
    print(f"ETF: {name}")
    print(f"Yahoo ticker: {yahoo_ticker}")
    print(
        f"Portfolio position: "
        f"quantity={quantity}, "
        f"value={market_value}, "
        f"weight={portfolio_weight}%"
    )
    print("=" * 70)

    # --------------------------------------------------------
    # Market data
    # --------------------------------------------------------

    data = get_etf_price_data(
        yahoo_ticker
    )

    print(
        f"Price rows: {len(data)}"
    )

    # --------------------------------------------------------
    # ETF analysis
    # --------------------------------------------------------

    analysis = analyse_etf(
        yahoo_ticker,
        data
    )

    print_analysis(
        analysis
    )

    # --------------------------------------------------------
    # ETF portfolio decision
    # --------------------------------------------------------

    decision = decide_etf(
        etf_analysis=analysis,
        quantity=quantity,
        market_value=market_value,
        portfolio_weight=portfolio_weight,
    )

    print_decision(
        decision
    )

    # --------------------------------------------------------
    # ETF recommendation
    # --------------------------------------------------------

    recommendation = generate_etf_recommendation(
        decision
    )

    print_recommendation(
        recommendation
    )

    return {
        "analysis": analysis,
        "decision": decision,
        "recommendation": recommendation,
    }


# ============================================================
# ASSERT DECISION
# ============================================================

def assert_decision(
    label: str,
    result: dict,
    expected: str,
):
    """
    Assert that the ETF decision matches the expected result.
    """

    actual = result["decision"]["ETF Decision"]

    print()
    print(
        f"TEST: {label}"
    )

    print(
        f"Expected: {expected}"
    )

    print(
        f"Actual:   {actual}"
    )

    if actual != expected:

        raise AssertionError(
            f"{label}: expected {expected}, "
            f"got {actual}"
        )

    print("PASS")


# ============================================================
# PORTFOLIO DECISION SCENARIOS
# ============================================================

def test_portfolio_scenarios(
    name: str,
    yahoo_ticker: str,
):
    """
    Test portfolio-aware ETF decision behaviour.

    The ETF analysis is performed once and then reused against
    different portfolio positions.

    This isolates the portfolio decision logic from market-data
    retrieval.
    """

    print()
    print()
    print("#" * 70)
    print(
        f"PORTFOLIO DECISION TESTS: {name}"
    )
    print("#" * 70)

    data = get_etf_price_data(
        yahoo_ticker
    )

    analysis = analyse_etf(
        yahoo_ticker,
        data
    )

    score = float(
        analysis.get(
            "ETF Score",
            0
        )
    )

    signal = str(
        analysis.get(
            "ETF Signal",
            ""
        )
    )

    print()
    print(
        f"ETF Score: {score}"
    )

    print(
        f"ETF Signal: {signal}"
    )

    # ========================================================
    # SCENARIO 1 — NOT OWNED
    # ========================================================

    result = run_chain(
        name,
        yahoo_ticker,
        quantity=0,
        market_value=0,
        portfolio_weight=0,
    )

    # --------------------------------------------------------
    # Only assert BUY if the current ETF analysis actually
    # qualifies as a strong BUY.
    # --------------------------------------------------------

    if (
        score >= 75
        and signal in {
            "BUY",
            "STRONG BUY",
        }
    ):

        assert_decision(
            "Not owned / strong ETF",
            result,
            "BUY",
        )

    else:

        assert_decision(
            "Not owned / insufficient ETF evidence",
            result,
            "HOLD",
        )

    # ========================================================
    # SCENARIO 2 — SMALL POSITION
    # ========================================================

    result = run_chain(
        name,
        yahoo_ticker,
        quantity=1,
        market_value=100,
        portfolio_weight=1,
    )

    expected = "HOLD"

    if (
        score >= 85
        and signal in {
            "BUY",
            "STRONG BUY",
        }
    ):

        expected = "BUY MORE"

    elif score < 35:

        expected = "REDUCE"

    assert_decision(
        "Small existing position",
        result,
        expected,
    )

    # ========================================================
    # SCENARIO 3 — MEANINGFUL POSITION
    # ========================================================

    result = run_chain(
        name,
        yahoo_ticker,
        quantity=10,
        market_value=500,
        portfolio_weight=5,
    )

    expected = "HOLD"

    if score < 35:

        expected = "REDUCE"

    assert_decision(
        "Meaningful existing position",
        result,
        expected,
    )

    # ========================================================
    # SCENARIO 4 — LARGE POSITION
    # ========================================================

    result = run_chain(
        name,
        yahoo_ticker,
        quantity=20,
        market_value=1500,
        portfolio_weight=12,
    )

    expected = "HOLD"

    if score < 35:

        expected = "REDUCE"

    assert_decision(
        "Large existing position",
        result,
        expected,
    )


# ============================================================
# MAIN
# ============================================================

def main():
    """
    Run ETF chain tests.
    """

    # --------------------------------------------------------
    # Basic end-to-end ETF tests.
    #
    # All positions are deliberately unowned here.
    # --------------------------------------------------------

    etfs = [
        (
            "IWDA",
            "IWDA.L",
        ),
        (
            "VUAA",
            "VUAA.L",
        ),
        (
            "SEC0",
            "SEC0.DE",
        ),
        (
            "AEMD",
            "AEMD.L",
        ),
    ]

    for name, yahoo_ticker in etfs:

        run_chain(
            name,
            yahoo_ticker,
        )

    # --------------------------------------------------------
    # Portfolio-aware tests.
    #
    # Use IWDA because it currently has strong ETF evidence,
    # allowing us to exercise BUY / BUY MORE / HOLD behaviour.
    # --------------------------------------------------------

    test_portfolio_scenarios(
        "IWDA",
        "IWDA.L",
    )

    print()
    print("=" * 70)
    print("ALL ETF TESTS PASSED")
    print("=" * 70)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
    test_negative_decision_scenarios()
