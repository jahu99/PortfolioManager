"""
FD-FINAL-02 — Final Portfolio Decision Population Tests

Purpose
-------
Validate the population gate used by the Final Portfolio Decision Engine.

FD-02 verifies that the Final Portfolio Decisions population contains:

    1. Every genuinely owned investment holding.
    2. Every non-owned BUY NEW opportunity approved by Capital Allocation.

It must exclude:

    - CASH
    - non-owned HOLD
    - non-owned BUY MORE
    - non-owned REDUCE
    - non-owned SELL
    - arbitrary market-universe rows

Important
---------
These tests deliberately test ONLY population construction.

They do NOT test:

    - AI decision scoring
    - LLM review
    - AI reconciliation
    - final action mapping
    - capital allocation calculations
    - position sizing
    - trade execution

The function under test is:

    build_eligible_population()

from:

    analysis.final_portfolio_decision
"""

from __future__ import annotations

import pandas as pd

from analysis.final_portfolio_decision import (
    build_eligible_population,
)


# ============================================================
# TEST HELPERS
# ============================================================

def tickers(rows):
    """Return sorted tickers from population records."""

    return sorted(
        row["Ticker"]
        for row in rows
        if row.get("Ticker")
    )


def find_row(rows, ticker):
    """Find a population row by ticker."""

    for row in rows:
        if row.get("Ticker") == ticker:
            return row

    return None


# ============================================================
# FD-02-01
# ============================================================

def test_fd_02_existing_holdings_are_included():
    """
    FD-02-01

    Every genuinely owned investment holding must be included
    in the Final Portfolio Decision population.

    Ownership is determined by positive Quantity.
    """

    portfolio_summary = pd.DataFrame(
        [
            {
                "Ticker": "NVDA",
                "Quantity": 50,
                "Market Value": 7200,
                "Asset Type": "STOCK",
            },
            {
                "Ticker": "MSFT",
                "Quantity": 40,
                "Market Value": 16000,
                "Asset Type": "STOCK",
            },
            {
                "Ticker": "IWDA",
                "Quantity": 10,
                "Market Value": 4500,
                "Asset Type": "ETF",
            },
        ]
    )

    portfolio_decisions = pd.DataFrame()

    capital_allocation = pd.DataFrame(
        [
            {
                "Ticker": "NVDA",
                "Action": "HOLD",
            },
            {
                "Ticker": "MSFT",
                "Action": "HOLD",
            },
            {
                "Ticker": "IWDA",
                "Action": "HOLD",
            },
        ]
    )

    population = build_eligible_population(
        portfolio_summary=portfolio_summary,
        portfolio_decisions=portfolio_decisions,
        capital_allocation=capital_allocation,
    )

    assert tickers(population) == [
        "IWDA",
        "MSFT",
        "NVDA",
    ]


# ============================================================
# FD-02-02
# ============================================================

def test_fd_02_non_owned_buy_new_is_included():
    """
    FD-02-02

    A non-owned security must be included when Capital Allocation
    explicitly proposes BUY NEW.
    """

    portfolio_summary = pd.DataFrame(
        [
            {
                "Ticker": "NVDA",
                "Quantity": 50,
                "Market Value": 7200,
                "Asset Type": "STOCK",
            },
        ]
    )

    portfolio_decisions = pd.DataFrame(
        [
            {
                "Ticker": "DLO",
                "Proposed Action": "BUY NEW",
                "Investment Score": 82,
            },
        ]
    )

    capital_allocation = pd.DataFrame(
        [
            {
                "Ticker": "DLO",
                "Action": "BUY NEW",
                "Investment Score": 82,
            },
        ]
    )

    population = build_eligible_population(
        portfolio_summary=portfolio_summary,
        portfolio_decisions=portfolio_decisions,
        capital_allocation=capital_allocation,
    )

    assert tickers(population) == [
        "DLO",
        "NVDA",
    ]

    dlo = find_row(
        population,
        "DLO",
    )

    assert dlo is not None
    assert dlo["Existing Holding"] is False


# ============================================================
# FD-02-03
# ============================================================

def test_fd_02_non_owned_non_buy_new_is_excluded():
    """
    FD-02-03

    Non-owned securities must NOT enter the final population
    unless Capital Allocation proposes BUY NEW.

    This specifically protects against accidentally including:

        HOLD
        BUY MORE
        REDUCE
        SELL
    """

    portfolio_summary = pd.DataFrame(
        [
            {
                "Ticker": "NVDA",
                "Quantity": 50,
                "Market Value": 7200,
                "Asset Type": "STOCK",
            },
        ]
    )

    portfolio_decisions = pd.DataFrame()

    capital_allocation = pd.DataFrame(
        [
            {
                "Ticker": "HOLD1",
                "Action": "HOLD",
            },
            {
                "Ticker": "MORE1",
                "Action": "BUY MORE",
            },
            {
                "Ticker": "REDUCE1",
                "Action": "REDUCE 25%",
            },
            {
                "Ticker": "SELL1",
                "Action": "SELL",
            },
            {
                "Ticker": "BUY1",
                "Action": "BUY NEW",
            },
        ]
    )

    population = build_eligible_population(
        portfolio_summary=portfolio_summary,
        portfolio_decisions=portfolio_decisions,
        capital_allocation=capital_allocation,
    )

    assert tickers(population) == [
        "BUY1",
        "NVDA",
    ]

    assert "HOLD1" not in tickers(population)
    assert "MORE1" not in tickers(population)
    assert "REDUCE1" not in tickers(population)
    assert "SELL1" not in tickers(population)


# ============================================================
# FD-02-04
# ============================================================

def test_fd_02_cash_is_excluded():
    """
    FD-02-04

    CASH must never appear in Final Portfolio Decisions,
    regardless of where it appears in the source data.
    """

    portfolio_summary = pd.DataFrame(
        [
            {
                "Ticker": "NVDA",
                "Quantity": 50,
                "Market Value": 7200,
                "Asset Type": "STOCK",
            },
            {
                "Ticker": "CASH",
                "Quantity": 1,
                "Market Value": 5000,
                "Asset Type": "CASH",
            },
        ]
    )

    portfolio_decisions = pd.DataFrame(
        [
            {
                "Ticker": "CASH",
                "Proposed Action": "HOLD",
            },
            {
                "Ticker": "DLO",
                "Proposed Action": "BUY NEW",
            },
        ]
    )

    capital_allocation = pd.DataFrame(
        [
            {
                "Ticker": "CASH",
                "Action": "BUY NEW",
            },
            {
                "Ticker": "DLO",
                "Action": "BUY NEW",
            },
        ]
    )

    population = build_eligible_population(
        portfolio_summary=portfolio_summary,
        portfolio_decisions=portfolio_decisions,
        capital_allocation=capital_allocation,
    )

    population_tickers = tickers(
        population
    )

    assert "CASH" not in population_tickers
    assert "DLO" in population_tickers
    assert "NVDA" in population_tickers


# ============================================================
# FD-02-05
# ============================================================

def test_fd_02_existing_holding_is_included_even_if_capital_allocator_says_hold():
    """
    FD-02-05

    Existing holdings must remain in the final population even
    when Capital Allocation proposes HOLD.

    Capital Allocation determines the transaction proposal.

    It does NOT determine whether an existing holding is eligible
    for final portfolio review.
    """

    portfolio_summary = pd.DataFrame(
        [
            {
                "Ticker": "NVDA",
                "Quantity": 50,
                "Market Value": 7200,
                "Asset Type": "STOCK",
            },
            {
                "Ticker": "MSFT",
                "Quantity": 40,
                "Market Value": 16000,
                "Asset Type": "STOCK",
            },
        ]
    )

    portfolio_decisions = pd.DataFrame(
        [
            {
                "Ticker": "NVDA",
                "Proposed Action": "HOLD",
            },
            {
                "Ticker": "MSFT",
                "Proposed Action": "HOLD",
            },
        ]
    )

    capital_allocation = pd.DataFrame(
        [
            {
                "Ticker": "NVDA",
                "Action": "HOLD",
            },
            {
                "Ticker": "MSFT",
                "Action": "HOLD",
            },
        ]
    )

    population = build_eligible_population(
        portfolio_summary=portfolio_summary,
        portfolio_decisions=portfolio_decisions,
        capital_allocation=capital_allocation,
    )

    assert tickers(population) == [
        "MSFT",
        "NVDA",
    ]


# ============================================================
# FD-02-06
# ============================================================

def test_fd_02_existing_holding_is_included_even_if_capital_allocator_says_reduce():
    """
    FD-02-06

    Existing holdings must remain in the final population even
    when Capital Allocation proposes REDUCE.

    The reduction decision must be reviewed by the final
    decision engine rather than removing the holding from
    the population.
    """

    portfolio_summary = pd.DataFrame(
        [
            {
                "Ticker": "NVDA",
                "Quantity": 50,
                "Market Value": 7200,
                "Asset Type": "STOCK",
            },
            {
                "Ticker": "AAPL",
                "Quantity": 25,
                "Market Value": 5000,
                "Asset Type": "STOCK",
            },
        ]
    )

    portfolio_decisions = pd.DataFrame()

    capital_allocation = pd.DataFrame(
        [
            {
                "Ticker": "NVDA",
                "Action": "HOLD",
            },
            {
                "Ticker": "AAPL",
                "Action": "REDUCE 25%",
            },
        ]
    )

    population = build_eligible_population(
        portfolio_summary=portfolio_summary,
        portfolio_decisions=portfolio_decisions,
        capital_allocation=capital_allocation,
    )

    assert tickers(population) == [
        "AAPL",
        "NVDA",
    ]

    aapl = find_row(
        population,
        "AAPL",
    )

    assert aapl is not None
    assert aapl["Quantity"] == 25


# ============================================================
# FD-02-07
# ============================================================

def test_fd_02_existing_holding_is_authoritative_over_non_owned_buy_new_proposal():
    """
    FD-02-07

    If a security exists in the holdings portfolio with a
    positive Quantity, it is an existing holding.

    A Capital Allocation BUY NEW proposal must NOT convert it
    into a new-position population entry.

    This protects the ownership boundary.
    """

    portfolio_summary = pd.DataFrame(
        [
            {
                "Ticker": "NVDA",
                "Quantity": 50,
                "Market Value": 7200,
                "Asset Type": "STOCK",
            },
        ]
    )

    portfolio_decisions = pd.DataFrame()

    capital_allocation = pd.DataFrame(
        [
            {
                "Ticker": "NVDA",
                "Action": "BUY NEW",
                "Investment Score": 95,
            },
        ]
    )

    population = build_eligible_population(
        portfolio_summary=portfolio_summary,
        portfolio_decisions=portfolio_decisions,
        capital_allocation=capital_allocation,
    )

    assert tickers(population) == [
        "NVDA",
    ]

    nvda = find_row(
        population,
        "NVDA",
    )

    assert nvda is not None
    assert nvda["Quantity"] == 50


# ============================================================
# FD-02-08
# ============================================================

def test_fd_02_zero_quantity_is_not_an_existing_holding():
    """
    FD-02-08

    Quantity == 0 means the security is not owned.

    Therefore a zero-quantity security only enters the final
    population if Capital Allocation proposes BUY NEW.
    """

    portfolio_summary = pd.DataFrame(
        [
            {
                "Ticker": "NVDA",
                "Quantity": 50,
                "Market Value": 7200,
                "Asset Type": "STOCK",
            },
            {
                "Ticker": "DLO",
                "Quantity": 0,
                "Market Value": 0,
                "Asset Type": "STOCK",
            },
        ]
    )

    portfolio_decisions = pd.DataFrame()

    capital_allocation = pd.DataFrame(
        [
            {
                "Ticker": "DLO",
                "Action": "BUY NEW",
            },
        ]
    )

    population = build_eligible_population(
        portfolio_summary=portfolio_summary,
        portfolio_decisions=portfolio_decisions,
        capital_allocation=capital_allocation,
    )

    assert tickers(population) == [
        "DLO",
        "NVDA",
    ]

    dlo = find_row(
        population,
        "DLO",
    )

    assert dlo is not None
    assert dlo["Existing Holding"] is False


# ============================================================
# FD-02-09
# ============================================================

def test_fd_02_positive_quantity_overrides_owned_flag():
    """
    FD-02-09

    Positive Quantity is sufficient to establish ownership.

    This protects against inconsistent or missing 'Owned' /
    'Existing Holding' flags in upstream data.
    """

    portfolio_summary = pd.DataFrame(
        [
            {
                "Ticker": "NVDA",
                "Quantity": 50,
                "Existing Holding": False,
                "Owned": False,
                "Market Value": 7200,
                "Asset Type": "STOCK",
            },
        ]
    )

    portfolio_decisions = pd.DataFrame()

    capital_allocation = pd.DataFrame(
        [
            {
                "Ticker": "NVDA",
                "Action": "HOLD",
            },
        ]
    )

    population = build_eligible_population(
        portfolio_summary=portfolio_summary,
        portfolio_decisions=portfolio_decisions,
        capital_allocation=capital_allocation,
    )

    assert tickers(population) == [
        "NVDA",
    ]


# ============================================================
# FD-02-10
# ============================================================

def test_fd_02_population_is_deduplicated_by_ticker():
    """
    FD-02-10

    A ticker must appear only once in the eligible population.

    Existing holdings take precedence over a duplicate
    Capital Allocation BUY NEW row.
    """

    portfolio_summary = pd.DataFrame(
        [
            {
                "Ticker": "NVDA",
                "Quantity": 50,
                "Market Value": 7200,
                "Asset Type": "STOCK",
            },
        ]
    )

    portfolio_decisions = pd.DataFrame()

    capital_allocation = pd.DataFrame(
        [
            {
                "Ticker": "NVDA",
                "Action": "BUY NEW",
                "Investment Score": 95,
            },
            {
                "Ticker": "DLO",
                "Action": "BUY NEW",
                "Investment Score": 85,
            },
            {
                "Ticker": "DLO",
                "Action": "BUY NEW",
                "Investment Score": 86,
            },
        ]
    )

    population = build_eligible_population(
        portfolio_summary=portfolio_summary,
        portfolio_decisions=portfolio_decisions,
        capital_allocation=capital_allocation,
    )

    population_tickers = tickers(
        population
    )

    assert population_tickers.count(
        "NVDA"
    ) == 1

    assert population_tickers.count(
        "DLO"
    ) == 1

    assert population_tickers == [
        "DLO",
        "NVDA",
    ]


# ============================================================
# FD-02-11
# ============================================================

def test_fd_02_ticker_normalisation_is_case_insensitive():
    """
    FD-02-11

    Ticker matching must be case-insensitive and whitespace
    tolerant.
    """

    portfolio_summary = pd.DataFrame(
        [
            {
                "Ticker": " nvda ",
                "Quantity": 50,
                "Market Value": 7200,
                "Asset Type": "STOCK",
            },
        ]
    )

    portfolio_decisions = pd.DataFrame()

    capital_allocation = pd.DataFrame(
        [
            {
                "Ticker": "NVDA",
                "Action": "HOLD",
            },
            {
                "Ticker": " dlo ",
                "Action": "BUY NEW",
            },
        ]
    )

    population = build_eligible_population(
        portfolio_summary=portfolio_summary,
        portfolio_decisions=portfolio_decisions,
        capital_allocation=capital_allocation,
    )

    assert tickers(population) == [
        "DLO",
        "NVDA",
    ]


# ============================================================
# FD-02-12
# ============================================================

def test_fd_02_empty_sources_produce_empty_population():
    """
    FD-02-12

    No holdings and no BUY NEW opportunities must produce an
    empty final population.
    """

    portfolio_summary = pd.DataFrame()

    portfolio_decisions = pd.DataFrame()

    capital_allocation = pd.DataFrame()

    population = build_eligible_population(
        portfolio_summary=portfolio_summary,
        portfolio_decisions=portfolio_decisions,
        capital_allocation=capital_allocation,
    )

    assert population == []


# ============================================================
# FD-02-13
# ============================================================

def test_fd_02_portfolio_decisions_alone_do_not_create_population_entries():
    """
    FD-02-13

    portfolio_decisions is NOT authoritative for final
    population membership.

    A non-owned BUY NEW row in portfolio_decisions must not enter
    the population unless Capital Allocation also proposes
    BUY NEW.
    """

    portfolio_summary = pd.DataFrame()

    portfolio_decisions = pd.DataFrame(
        [
            {
                "Ticker": "DLO",
                "Proposed Action": "BUY NEW",
                "Investment Score": 90,
            },
        ]
    )

    capital_allocation = pd.DataFrame()

    population = build_eligible_population(
        portfolio_summary=portfolio_summary,
        portfolio_decisions=portfolio_decisions,
        capital_allocation=capital_allocation,
    )

    assert population == []


# ============================================================
# FD-02-14
# ============================================================

def test_fd_02_mixed_realistic_population():
    """
    FD-02-14

    End-to-end population boundary test using a realistic
    mixture of stocks, ETFs, reductions, holds, sells and
    new opportunities.

    Expected population:

        Existing:
            NVDA
            IWDA
            VUAA
            MSFT
            AAPL

        New:
            DLO
            DUOL
            AYA

    Excluded:
            CASH
            AEMD if not owned and REDUCE
            BBVA if not owned and BUY MORE
            XYZ if not owned and HOLD
            ABC if not owned and SELL
    """

    portfolio_summary = pd.DataFrame(
        [
            {
                "Ticker": "NVDA",
                "Quantity": 50,
                "Market Value": 7200,
                "Asset Type": "STOCK",
            },
            {
                "Ticker": "IWDA",
                "Quantity": 10,
                "Market Value": 4500,
                "Asset Type": "ETF",
            },
            {
                "Ticker": "VUAA",
                "Quantity": 5,
                "Market Value": 2200,
                "Asset Type": "ETF",
            },
            {
                "Ticker": "MSFT",
                "Quantity": 40,
                "Market Value": 16000,
                "Asset Type": "STOCK",
            },
            {
                "Ticker": "AAPL",
                "Quantity": 25,
                "Market Value": 5000,
                "Asset Type": "STOCK",
            },
            {
                "Ticker": "CASH",
                "Quantity": 1,
                "Market Value": 5900,
                "Asset Type": "CASH",
            },
        ]
    )

    portfolio_decisions = pd.DataFrame(
        [
            {
                "Ticker": "DLO",
                "Proposed Action": "BUY NEW",
                "Investment Score": 90,
            },
            {
                "Ticker": "DUOL",
                "Proposed Action": "BUY NEW",
                "Investment Score": 88,
            },
            {
                "Ticker": "AYA",
                "Proposed Action": "BUY NEW",
                "Investment Score": 86,
            },
            {
                "Ticker": "BBVA",
                "Proposed Action": "BUY MORE",
                "Investment Score": 84,
            },
            {
                "Ticker": "AEMD",
                "Proposed Action": "REDUCE 25%",
                "Investment Score": 40,
            },
            {
                "Ticker": "XYZ",
                "Proposed Action": "HOLD",
                "Investment Score": 50,
            },
            {
                "Ticker": "ABC",
                "Proposed Action": "SELL",
                "Investment Score": 20,
            },
        ]
    )

    capital_allocation = pd.DataFrame(
        [
            {
                "Ticker": "NVDA",
                "Action": "HOLD",
            },
            {
                "Ticker": "IWDA",
                "Action": "HOLD",
            },
            {
                "Ticker": "VUAA",
                "Action": "HOLD",
            },
            {
                "Ticker": "MSFT",
                "Action": "HOLD",
            },
            {
                "Ticker": "AAPL",
                "Action": "HOLD",
            },
            {
                "Ticker": "CASH",
                "Action": "HOLD",
            },
            {
                "Ticker": "DLO",
                "Action": "BUY NEW",
                "Investment Score": 90,
            },
            {
                "Ticker": "DUOL",
                "Action": "BUY NEW",
                "Investment Score": 88,
            },
            {
                "Ticker": "AYA",
                "Action": "BUY NEW",
                "Investment Score": 86,
            },
            {
                "Ticker": "BBVA",
                "Action": "BUY MORE",
                "Investment Score": 84,
            },
            {
                "Ticker": "AEMD",
                "Action": "REDUCE 25%",
                "Investment Score": 40,
            },
            {
                "Ticker": "XYZ",
                "Action": "HOLD",
                "Investment Score": 50,
            },
            {
                "Ticker": "ABC",
                "Action": "SELL",
                "Investment Score": 20,
            },
        ]
    )

    population = build_eligible_population(
        portfolio_summary=portfolio_summary,
        portfolio_decisions=portfolio_decisions,
        capital_allocation=capital_allocation,
    )

    assert tickers(population) == [
        "AAPL",
        "AYA",
        "DLO",
        "DUOL",
        "IWDA",
        "MSFT",
        "NVDA",
        "VUAA",
    ]

    assert "CASH" not in tickers(population)
    assert "AEMD" not in tickers(population)
    assert "BBVA" not in tickers(population)
    assert "XYZ" not in tickers(population)
    assert "ABC" not in tickers(population)