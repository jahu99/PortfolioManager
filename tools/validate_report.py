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



# =====================================
# LOAD WORKBOOK
# =====================================

try:

    workbook = pd.ExcelFile(
        report_file
    )

    sheets = workbook.sheet_names


except Exception as e:

    raise Exception(
        f"Unable to read workbook: {e}"
    )



print()
print("SHEETS")
print("----------------")


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
# LOAD DATAFRAMES
# =====================================

required_non_empty = [

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
    "Recommendation Intelligence"

]


dataframes = {}



print()
print("CONTENT")
print("----------------")



for sheet in required_non_empty:

    try:

        df = pd.read_excel(
            report_file,
            sheet_name=sheet
        )


        dataframes[sheet] = df


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
# COLUMN VALIDATION
# =====================================

print()
print("COLUMNS")
print("----------------")



required_columns = {


    "Stock Rankings": [

        "Ticker",
        "Investment Score",
        "Quality Score",
        "Signal"

    ],


    "Portfolio": [

        "Ticker",
        "Shares",
        "Current Value",
        "Allocation %"

    ],


    "Portfolio Actions": [

        "Action",
        "Ticker"

    ],


    "Portfolio Optimisation": [

        "Sector"

    ],


    "Rebalance Recommendations": [

        "Action",
        "Ticker"

    ],


    "Sector Analysis": [

        "Sector"

    ],


    "Portfolio Health": [

        "Health Score",
        "Rating"

    ],


    "Final Portfolio Decisions": [

        "Ticker",
        "Final Action",
        "Conviction"

    ],


    "Investment Decisions": [

        "Ticker",
        "Action"

    ],


    "Trade Plan": [

        "Ticker",
        "Action"

    ],


    "Recommendation Intelligence": [

        "Ticker"

    ]

}



for sheet, columns in required_columns.items():


    df = dataframes.get(
        sheet
    )


    if df is None:

        continue



    missing = [

        c for c in columns

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
# PORTFOLIO QUALITY
# =====================================

print()
print("PORTFOLIO")
print("----------------")



portfolio = dataframes.get(
    "Portfolio"
)



if portfolio is not None and not portfolio.empty:


    if portfolio["Ticker"].duplicated().any():

        print(
            "✗ Duplicate portfolio tickers"
        )

        issues.append(
            "Duplicate portfolio tickers"
        )

    else:

        print(
            "✓ Portfolio no duplicate tickers"
        )



    total = portfolio[
        "Current Value"
    ].sum()


    allocation = portfolio[
        "Allocation %"
    ].sum()



    print(
        f"Portfolio value: {round(total,2)}"
    )


    print(
        f"Portfolio allocation: {round(allocation,2)}%"
    )



    if abs(allocation - 100) <= 1:

        print(
            "✓ Allocation check"
        )

    else:

        print(
            "✗ Allocation check failed"
        )

        issues.append(
            "Portfolio allocation invalid"
        )



# =====================================
# STOCK RANKINGS QUALITY
# =====================================

print()
print("STOCK RANKINGS")
print("----------------")



rankings = dataframes.get(
    "Stock Rankings"
)



if rankings is not None and not rankings.empty:


    if rankings[
        "Ticker"
    ].duplicated().any():

        print(
            "✗ Duplicate ranked tickers"
        )

        issues.append(
            "Duplicate ranked tickers"
        )


    else:

        print(
            "✓ No duplicate ranked tickers"
        )



    if "Investment Score" in rankings.columns:

        if rankings[
            "Investment Score"
        ].between(
            0,
            100
        ).all():

            print(
                "✓ Investment Score between 0-100"
            )

        else:

            print(
                "✗ Investment Score invalid"
            )

            issues.append(
                "Investment Score invalid"
            )



    if "Quality Score" in rankings.columns:

        if rankings[
            "Quality Score"
        ].between(
            0,
            100
        ).all():

            print(
                "✓ Quality Score between 0-100"
            )

        else:

            print(
                "✗ Quality Score invalid"
            )

            issues.append(
                "Quality Score invalid"
            )



    if "Signal" in rankings.columns:

        print(
            "✓ Valid stock signals"
        )



# =====================================
# FINAL RESULT
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