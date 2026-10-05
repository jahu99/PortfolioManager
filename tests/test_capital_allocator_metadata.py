import pandas as pd

from analysis.capital_allocator import generate_capital_allocation
from data.fundamentals import get_fundamentals


# ============================================================
# REAL MELI FUNDAMENTALS
# ============================================================

fundamentals = get_fundamentals("MELI")

print("\n--- MELI FUNDAMENTALS CACHE ---")
print({
    "Name": fundamentals.get("Name"),
    "Sector": fundamentals.get("Sector"),
    "Country": fundamentals.get("Country"),
    "Exchange": fundamentals.get("Exchange"),
    "Quote Type": fundamentals.get("Quote Type"),
})


# ============================================================
# RESULTS-STYLE METADATA SOURCE
# This mirrors the fields main.py puts into results.
# ============================================================

metadata_source = pd.DataFrame([
    {
        "Ticker": "MELI",
        "Name": fundamentals.get("Name"),
        "Sector": fundamentals.get("Sector"),
        "Country": fundamentals.get("Country"),
        "Exchange": fundamentals.get("Exchange"),
        "Quote Type": fundamentals.get("Quote Type"),
    }
])


print("\n--- METADATA SOURCE ---")
print(metadata_source.to_string(index=False))


# ============================================================
# EXISTING HOLDING
# ============================================================

portfolio = pd.DataFrame([
    {
        "Ticker": "MELI",
        "Sector": "Consumer Cyclical",
        "Current Value": 10000,
        "Investment Score": 26,
    }
])


# ============================================================
# FORCE A REDUCE ACTION
# ============================================================

portfolio_decisions = pd.DataFrame([
    {
        "Ticker": "MELI",
        "Action": "REDUCE 75%",
        "Investment Score": 26,
    }
])


# ============================================================
# RUN ALLOCATOR
# ============================================================

result = generate_capital_allocation(
    portfolio_summary=portfolio,
    opportunities=pd.DataFrame(),
    portfolio_decisions=portfolio_decisions,
    metadata_source=metadata_source,
)


allocation = result["Capital Allocation"]


# ============================================================
# DISPLAY RESULT
# ============================================================

print("\n--- CAPITAL ALLOCATION RESULT ---")

if allocation.empty:
    print("Allocation is EMPTY")
else:
    print(allocation.to_string(index=False))


# ============================================================
# FIND MELI
# ============================================================

m = allocation[
    allocation["Ticker"].astype(str).str.upper() == "MELI"
]


assert not m.empty, "MELI allocation row was not generated"


row = m.iloc[0]


print("\n--- MELI OUTPUT METADATA ---")
print({
    "Name": row.get("Name"),
    "Sector": row.get("Sector"),
    "Country": row.get("Country"),
    "Exchange": row.get("Exchange"),
    "Quote Type": row.get("Quote Type"),
    "Sector Allocation %": row.get("Sector Allocation %"),
})


# ============================================================
# METADATA ASSERTIONS
# ============================================================

assert row.get("Name") == fundamentals.get("Name"), (
    f"Name mismatch: {row.get('Name')!r}"
)

assert row.get("Country") == fundamentals.get("Country"), (
    f"Country mismatch: {row.get('Country')!r}"
)

assert row.get("Exchange") == fundamentals.get("Exchange"), (
    f"Exchange mismatch: {row.get('Exchange')!r}"
)

assert row.get("Quote Type") == fundamentals.get("Quote Type"), (
    f"Quote Type mismatch: {row.get('Quote Type')!r}"
)


print("\nMETADATA PATH: PASS")
