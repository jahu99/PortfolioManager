import pandas as pd
from pathlib import Path


# =====================================
# CONFIG
# =====================================

REPORT_DIR = Path("reports")

issues = []


# =====================================
# FIND LATEST REPORT
# =====================================

reports = sorted(
    REPORT_DIR.glob(
        "daily_report_*.xlsx"
    )
)

if not reports:
    raise FileNotFoundError(
        "No daily report found"
    )

report_file = reports[-1]


print()
print("======================")
print("REPORT AUDIT")
print("======================")
print(report_file)



# =====================================
# EXPECTED SHEETS
# =====================================

expected_sheets = [

    "Executive Summary",
    "How To Use",
    "Stock Rankings",
    "Portfolio",
    "Portfolio Actions",
    "Portfolio Optimisation",
    "Rebalance Recommendations",
    "Sector Analysis",
    "Portfolio Health",
    "Final Portfolio Decisions",
    "Investment Decisions",
    "Trade Plan",
    "Portfolio Growth Plan",
    "AI Portfolio Review",
    "AI Portfolio Manager",
    "Recommendation Learning Summary",
    "Learning 5D Summary",
    "Learning 10D Summary",
    "Recommendation Intelligence",
    "Alerts"

]


print()
print("SHEETS")
print("----------------")


workbook = pd.ExcelFile(
    report_file
)

sheets = workbook.sheet_names


for sheet in expected_sheets:

    if sheet in sheets:

        print(
            f"✓ {sheet}"
        )

    else:

        print(
            f"✗ FAIL: {sheet} missing"
        )

        issues.append(
            f"{sheet} missing"
        )



# =====================================
# LOAD SHEETS
# =====================================

dataframes = {}


print()
print("CONTENT")
print("----------------")


for sheet in expected_sheets:

    if sheet not in sheets:
        continue


    try:

        df = pd.read_excel(
            report_file,
            sheet_name=sheet
        )


        dataframes[sheet] = df


        # Recommendation Intelligence
        # is a formatted report, not raw table

        if sheet == "Recommendation Intelligence":

            text = df.astype(
                str
            ).to_string()


            if (
                "Signal Performance" in text
                or
                "Recommendation Intelligence Report" in text
            ):

                print(
                    "✓ Recommendation Intelligence contains report sections"
                )

            else:

                print(
                    "✗ FAIL: Recommendation Intelligence malformed"
                )

                issues.append(
                    "Recommendation Intelligence malformed"
                )


            continue



        if len(df) > 0:

            print(
                f"✓ {sheet}: {len(df)} rows"
            )

        else:

            print(
                f"✗ FAIL: {sheet} empty"
            )

            issues.append(
                f"{sheet} empty"
            )


    except Exception as e:

        print(
            f"✗ FAIL: {sheet} read error {e}"
        )

        issues.append(
            f"{sheet} unreadable"
        )



# =====================================
# COLUMN CHECKS
# =====================================

print()
print("COLUMNS")
print("----------------")


column_rules = {


    "Stock Rankings":
    [
        "Ticker",
        "Investment Score",
        "Quality Score",
        "Signal"
    ],


    "Portfolio":
    [
        "Ticker",
        "Shares",
        "Current Value",
        "Allocation %"
    ],


    "Portfolio Actions":
    [
        "Action",
        "Ticker"
    ],


    "Portfolio Optimisation":
    [
        "Sector"
    ],


    "Rebalance Recommendations":
    [
        "Ticker",
        "Action"
    ],


    "Sector Analysis":
    [
        "Sector"
    ],


    "Portfolio Health":
    [
        "Health Score"
    ],


    "Final Portfolio Decisions":
    [
        "Ticker",
        "Final Action"
    ],


    "Investment Decisions":
    [
        "Ticker",
        "Action"
    ],


    "Trade Plan":
    [
        "Ticker",
        "Action"
    ]

}



for sheet, required in column_rules.items():


    df = dataframes.get(
        sheet
    )


    if df is None:
        continue


    missing = [
        c for c in required
        if c not in df.columns
    ]


    if missing:

        print(
            f"✗ {sheet} missing {missing}"
        )

        issues.append(
            f"{sheet} missing columns {missing}"
        )

    else:

        print(
            f"✓ {sheet}"
        )



# =====================================
# DATA QUALITY
# =====================================

print()
print("DATA QUALITY")
print("----------------")


# Portfolio checks

portfolio = dataframes.get(
    "Portfolio"
)


if portfolio is not None and not portfolio.empty:


    if "Ticker" in portfolio.columns:

        duplicates = (
            portfolio["Ticker"]
            .duplicated()
            .any()
        )


        if duplicates:

            print(
                "✗ Portfolio duplicate tickers"
            )

            issues.append(
                "Portfolio duplicate tickers"
            )

        else:

            print(
                "✓ Portfolio no duplicate tickers"
            )


    if "Allocation %" in portfolio.columns:

        allocation = (
            portfolio["Allocation %"]
            .sum()
        )


        print(
            f"Portfolio allocation: {allocation:.2f}%"
        )


        if abs(allocation - 100) <= 0.2:

            print(
                "✓ Allocation check"
            )

        else:

            print(
                "✗ Allocation incorrect"
            )

            issues.append(
                "Portfolio allocation incorrect"
            )



# Generic ticker duplicate checks

ticker_checks = [

    "Stock Rankings",
    "Investment Decisions",
    "Final Portfolio Decisions"

]


for sheet in ticker_checks:


    df = dataframes.get(
        sheet
    )


    if (
        df is not None
        and
        "Ticker" in df.columns
    ):


        if df["Ticker"].duplicated().any():

            print(
                f"✗ {sheet} duplicate tickers"
            )

            issues.append(
                f"{sheet} duplicate tickers"
            )

        else:

            print(
                f"✓ {sheet} no duplicate tickers"
            )



# =====================================
# RESULT
# =====================================

print()

print("======================")

if issues:

    print(
        f"RESULT: FAIL ({len(issues)} issues)"
    )

    print()

    for issue in issues:

        print(
            "-",
            issue
        )


else:

    print(
        "RESULT: PASS"
    )


print("======================")