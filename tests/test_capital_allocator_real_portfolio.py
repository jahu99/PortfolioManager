import pandas as pd
from pathlib import Path

from portfolio.portfolio import get_portfolio
from analysis.portfolio_analysis import analyse_portfolio
from analysis.capital_allocator import generate_capital_allocation


print("\n================================")
print("REAL PORTFOLIO CAPITAL ALLOCATION")
print("================================")


# =================================
# Load real holdings
# =================================

holdings = get_portfolio()


print("\nHOLDINGS")
print(holdings)


# =================================
# Load latest report stock rankings
# =================================

reports = sorted(
    Path("reports").glob(
        "daily_report_*.xlsx"
    )
)


if not reports:

    raise FileNotFoundError(
        "No daily report found in reports directory"
    )


latest_report = reports[-1]


print("\nUSING REPORT")
print(latest_report)


rankings = pd.read_excel(
    latest_report,
    sheet_name="Stock Rankings"
)


print("\nRANKINGS")
print(
    rankings.head()
)


# =================================
# Build portfolio summary
# =================================

portfolio_summary = analyse_portfolio(
    holdings,
    rankings.to_dict(
        "records"
    )
)


print("\nPORTFOLIO SUMMARY")

print(
    portfolio_summary[
        [
            "Ticker",
            "Sector",
            "Current Value"
        ]
    ]
)



# =================================
# Build sector optimisation input
# =================================

sector_summary = (

    portfolio_summary
    .groupby(
        "Sector"
    )["Current Value"]