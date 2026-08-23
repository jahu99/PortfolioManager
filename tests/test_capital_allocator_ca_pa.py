
"""
CA.PA Capital Allocator Regression Test

Purpose
-------
Verify the critical production rule at the Final Portfolio Decision ->
Capital Allocation boundary:

    CA.PA + explicit SELL decision
        ->
    CA.PA SELL allocation

The allocator must NOT subsequently convert CA.PA to HOLD.

This test deliberately isolates capital_allocator.py from the rest of
the portfolio decision pipeline. It therefore tells us whether the fault
is inside the allocator itself.

The test does not:
- change production code;
- access live market data;
- execute trades;
- modify the real holdings CSV.
"""

from __future__ import annotations

import pandas as pd

import analysis.capital_allocator as allocator


def _ca_pa_holdings():
    """
    Minimal representation of the real CA.PA holding.

    Real portfolio data currently contains:

        CA.PA,Carrefour SA,0.25,3.47

    Therefore:

        quantity    = 0.25
        market_value = 3.47
    """

    return {
        "CA.PA": {
            "owned": True,
            "quantity": 0.25,
            "market_value": 3.47,
        }
    }


def _ca_pa_portfolio():
    """
    Minimal portfolio summary containing the existing CA.PA position.
    """

    return pd.DataFrame(
        [
            {
                "Ticker": "CA.PA",
                "Asset Type": "STOCK",
                "Shares": 0.25,
                "Quantity": 0.25,
                "Current Value": 3.47,
                "Market Value": 3.47,
                "Current Price": 13.88,
                "Price": 13.88,
                "Investment Score": 18,
            }
        ]
    )


def _ca_pa_sell_decision():
    """
    Explicit authoritative portfolio decision.

    This is the input that capital_allocator.py must preserve.
    """

    return [
        {
            "Ticker": "CA.PA",
            "Action": "SELL",
            "Price": 13.88,
            "Market Value": 3.47,
            "Reason": "Explicit CA.PA SELL decision",
            "Investment Score": 18,
        }
    ]


def test_ca_pa_sell_is_preserved_and_not_converted_to_hold(
    monkeypatch,
):
    """
    CA.PA SELL must remain SELL in the capital allocation output.

    This is the regression test for the reported fault where an explicit
    SELL decision is subsequently appearing as HOLD.
    """

    # ------------------------------------------------------------
    # Isolate the allocator from the real holdings file.
    # ------------------------------------------------------------

    monkeypatch.setattr(
        allocator,
        "load_actual_holdings",
        _ca_pa_holdings,
    )

    # ------------------------------------------------------------
    # No BUY opportunity is required for this test.
    #
    # We are testing the REDUCTIONS -> HOLD boundary.
    # ------------------------------------------------------------

    opportunities = pd.DataFrame()

    result = allocator.generate_capital_allocation(
        portfolio_summary=_ca_pa_portfolio(),
        opportunities=opportunities,
        portfolio_decisions=_ca_pa_sell_decision(),
    )

    allocation_df = result["Capital Allocation"]

    # ------------------------------------------------------------
    # CA.PA must exist in the allocation output.
    # ------------------------------------------------------------

    ca_pa_rows = allocation_df[
        allocation_df["Ticker"] == "CA.PA"
    ]

    assert not ca_pa_rows.empty, (
        "CA.PA disappeared from Capital Allocation. "
        "The explicit SELL decision was not preserved."
    )

    # ------------------------------------------------------------
    # There must be exactly one CA.PA action.
    # ------------------------------------------------------------

    assert len(ca_pa_rows) == 1, (
        "CA.PA appears more than once in Capital Allocation."
    )

    # ------------------------------------------------------------
    # CRITICAL ASSERTION:
    #
    # An explicit SELL must never become HOLD.
    # ------------------------------------------------------------

    assert ca_pa_rows.iloc[0]["Action"] == "SELL", (
        "CA.PA explicit SELL was converted to "
        f"{ca_pa_rows.iloc[0]['Action']!r}."
    )

    # ------------------------------------------------------------
    # SELL must represent the full position reduction.
    # ------------------------------------------------------------

    assert ca_pa_rows.iloc[0]["Reduction %"] == 100

    # ------------------------------------------------------------
    # Capital released must equal the actual holding value.
    # ------------------------------------------------------------

    assert round(
        float(ca_pa_rows.iloc[0]["Released Capital"]),
        2,
    ) == 3.47

    # ------------------------------------------------------------
    # A SELL must not simultaneously appear as a HOLD.
    # ------------------------------------------------------------

    assert not (
        allocation_df[
            (allocation_df["Ticker"] == "CA.PA")
            & (allocation_df["Action"] == "HOLD")
        ]
    ).any(axis=None), (
        "CA.PA has both a SELL and HOLD allocation."
    )


def test_ca_pa_reduce_25_is_preserved(
    monkeypatch,
):
    """
    Regression test for partial reduction.

    REDUCE 25% must remain REDUCE 25% and must not become HOLD.
    """

    monkeypatch.setattr(
        allocator,
        "load_actual_holdings",
        _ca_pa_holdings,
    )

    portfolio_decisions = [
        {
            "Ticker": "CA.PA",
            "Action": "REDUCE 25%",
            "Price": 13.88,
            "Market Value": 3.47,
            "Reason": "Explicit CA.PA reduction decision",
            "Investment Score": 18,
        }
    ]

    result = allocator.generate_capital_allocation(
        portfolio_summary=_ca_pa_portfolio(),
        opportunities=pd.DataFrame(),
        portfolio_decisions=portfolio_decisions,
    )

    allocation_df = result["Capital Allocation"]

    ca_pa_rows = allocation_df[
        allocation_df["Ticker"] == "CA.PA"
    ]

    assert not ca_pa_rows.empty

    assert len(ca_pa_rows) == 1

    row = ca_pa_rows.iloc[0]

    assert row["Action"] == "REDUCE 25%"

    assert row["Reduction %"] == 25

    assert round(
        float(row["Released Capital"]),
        2,
    ) == 0.87

    assert not (
        allocation_df[
            (allocation_df["Ticker"] == "CA.PA")
            & (allocation_df["Action"] == "HOLD")
        ]
    ).any(axis=None)


def test_ca_pa_sell_does_not_require_price_in_decision(
    monkeypatch,
):
    """
    The allocator should be able to calculate a SELL using the actual
    holding market value and quantity even if the decision row itself
    contains no price.

    Real CA.PA holding:

        quantity     = 0.25
        market value = 3.47

    Therefore the allocator's existing price fallback should calculate:

        3.47 / 0.25 = 13.88
    """

    monkeypatch.setattr(
        allocator,
        "load_actual_holdings",
        _ca_pa_holdings,
    )

    portfolio_decisions = [
        {
            "Ticker": "CA.PA",
            "Action": "SELL",
            "Market Value": 3.47,
            "Reason": "Explicit CA.PA SELL decision",
            "Investment Score": 18,
        }
    ]

    result = allocator.generate_capital_allocation(
        portfolio_summary=_ca_pa_portfolio(),
        opportunities=pd.DataFrame(),
        portfolio_decisions=portfolio_decisions,
    )

    allocation_df = result["Capital Allocation"]

    ca_pa_rows = allocation_df[
        allocation_df["Ticker"] == "CA.PA"
    ]

    assert not ca_pa_rows.empty

    row = ca_pa_rows.iloc[0]

    assert row["Action"] == "SELL"

    assert round(
        float(row["Price"]),
        2,
    ) == 13.88

    assert row["Reduction %"] == 100

