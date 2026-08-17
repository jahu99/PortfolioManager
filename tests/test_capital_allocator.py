"""
test_capital_allocator.py

Purpose
-------
Basic regression test for the current capital allocator.

The allocator now returns:

    {
        "Capital Allocation": allocation_df,
        "Capital Summary": summary
    }

This harness therefore validates the current allocator contract
rather than the obsolete BUY / REDUCE / AVOID return structure.
"""

import pandas as pd

from analysis.capital_allocator import (
    generate_capital_allocation
)


# ============================================================
# TEST PORTFOLIO
# ============================================================

portfolio = pd.DataFrame([

    {
        "Ticker": "NVDA",
        "Sector": "Technology",
        "Current Value": 50000,
        "Investment Score": 90
    },

    {
        "Ticker": "MSFT",
        "Sector": "Technology",
        "Current Value": 5000,
        "Investment Score": 80
    },

    {
        "Ticker": "AAPL",
        "Sector": "Technology",
        "Current Value": 3000,
        "Investment Score": 75
    }
])


# ============================================================
# TEST OPPORTUNITIES
# ============================================================

opportunities = pd.DataFrame([

    {
        "Ticker": "CARE",
        "Sector": "Financial Services",
        "Investment Score": 100,
        "Quality Score": 67,
        "Signal": "STRONG BUY",
        "Confidence": "High",
        "Price": 20
    },

    {
        "Ticker": "DXCM",
        "Sector": "Healthcare",
        "Investment Score": 95,
        "Quality Score": 46,
        "Signal": "BUY",
        "Confidence": "Medium",
        "Price": 50
    }
])


# ============================================================
# TEST
# ============================================================

result = generate_capital_allocation(

    portfolio_summary=portfolio,

    opportunities=opportunities,

    portfolio_decisions=[]
)


# ============================================================
# VALIDATE RETURN STRUCTURE
# ============================================================

assert isinstance(
    result,
    dict
), "Allocator should return a dictionary"


assert "Capital Allocation" in result, (
    "Missing 'Capital Allocation' in allocator result"
)


assert "Capital Summary" in result, (
    "Missing 'Capital Summary' in allocator result"
)


allocation = result[
    "Capital Allocation"
]

summary = result[
    "Capital Summary"
]


assert isinstance(
    allocation,
    pd.DataFrame
), "Capital Allocation should be a DataFrame"


assert isinstance(
    summary,
    pd.DataFrame
), "Capital Summary should be a DataFrame"


# ============================================================
# DISPLAY ALLOCATION
# ============================================================

print(
    "\n--- CAPITAL ALLOCATION TEST ---"
)

print(
    "\nAllocation:"
)

if allocation.empty:

    print(
        "No allocations generated."
    )

else:

    print(
        allocation.to_string(
            index=False
        )
    )


# ============================================================
# DISPLAY SUMMARY
# ============================================================

print(
    "\nCapital Summary:"
)

if summary.empty:

    print(
        "No summary generated."
    )

else:

    print(
        summary.to_string(
            index=False
        )
    )


# ============================================================
# BASIC ASSERTIONS
# ============================================================

expected_allocation_columns = [

    "Ticker",
    "Action",
    "Existing Holding",
    "Asset Type",
    "Price",
    "Quantity",
    "Reduction %",
    "Reduction Quantity",
    "Market Value",
    "Released Capital",
    "Buy Quantity",
    "Buy Value",
    "Amount",
    "Funding Source",
    "Reason",
    "Investment Score",
    "Reduction Rank",
    "Investment Rank"
]


for column in expected_allocation_columns:

    assert column in allocation.columns, (
        f"Missing allocation column: {column}"
    )


print(
    "\nAllocation structure: PASS"
)


# ============================================================
# SUMMARY VALIDATION
# ============================================================

expected_summary_columns = [
    "Metric",
    "Amount"
]



for column in expected_summary_columns:

    assert column in summary.columns, (
        f"Missing summary column: {column}"
    )


print(
    "Summary structure: PASS"
)


print(
    "\n======================================================================"
)

print(
    "CAPITAL ALLOCATOR TEST PASSED"
)

print(
    "======================================================================"
)