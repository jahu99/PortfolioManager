import pandas as pd

from analysis.capital_allocator import generate_capital_allocation


def test_buy_new_only_allows_reasonable_entry_quality(monkeypatch):
    opportunities = pd.DataFrame(
        [
            {
                "Ticker": "REASONABLE1",
                "Name": "Reasonable Entry",
                "Asset": "STOCK",
                "Investment Score": 95.0,
                "Price": 100.0,
                "Entry Quality": "REASONABLE",
                "Entry Quality Mode": "SHADOW",
            },
            {
                "Ticker": "MODERATE1",
                "Name": "Moderately Extended",
                "Asset": "STOCK",
                "Investment Score": 94.0,
                "Price": 100.0,
                "Entry Quality": "MODERATELY EXTENDED",
                "Entry Quality Mode": "SHADOW",
            },
            {
                "Ticker": "EXTENDED1",
                "Name": "Extended",
                "Asset": "STOCK",
                "Investment Score": 93.0,
                "Price": 100.0,
                "Entry Quality": "EXTENDED",
                "Entry Quality Mode": "SHADOW",
            },
            {
                "Ticker": "HIGHLY_EXTENDED1",
                "Name": "Highly Extended",
                "Asset": "STOCK",
                "Investment Score": 92.0,
                "Price": 100.0,
                "Entry Quality": "HIGHLY EXTENDED",
                "Entry Quality Mode": "SHADOW",
            },
        ]
    )

    # Ensure none of the synthetic tickers are treated as existing holdings.
    monkeypatch.setattr(
        "analysis.capital_allocator.load_actual_holdings",
        lambda: {},
    )

    result = generate_capital_allocation(
        portfolio_summary=pd.DataFrame(),
        opportunities=opportunities,
        portfolio_decisions=[],
    )

    allocation = result["Capital Allocation"]

    buy_new = allocation[
        allocation["Action"] == "BUY NEW"
    ]

    selected_tickers = set(
        buy_new["Ticker"]
    )

    assert "REASONABLE1" in selected_tickers

    assert "MODERATE1" not in selected_tickers
    assert "EXTENDED1" not in selected_tickers
    assert "HIGHLY_EXTENDED1" not in selected_tickers