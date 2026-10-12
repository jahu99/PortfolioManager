import pandas as pd


SNAPSHOT = "data/candidate_ranking_snapshot.csv"


df = pd.read_csv(SNAPSHOT)


# ------------------------------------------------------------
# Restrict to BUY NEW eligible candidates from the snapshot.
#
# This test is specifically about ranking, not Entry Quality
# classification or BUY NEW governance.
# ------------------------------------------------------------

if "BUY NEW Eligible" in df.columns:

    eligible = df[
        df["BUY NEW Eligible"]
        .fillna(False)
        .astype(bool)
    ].copy()

else:

    eligible = df.copy()


# ------------------------------------------------------------
# Normalise ranking columns.
# ------------------------------------------------------------

ranking_columns = [
    "Investment Score",
    "Technical Score",
    "Quality Score",
    "Growth Score",
    "Confidence Score",
]


for column in ranking_columns:

    if column not in eligible.columns:

        eligible[column] = 0.0

    eligible[column] = pd.to_numeric(
        eligible[column],
        errors="coerce",
    ).fillna(0.0)


# ------------------------------------------------------------
# H1 priority
# ------------------------------------------------------------

if "BUY NEW H1 Status" in eligible.columns:

    h1_priority = {
        "H1 STRONG": 0,
        "H1 NEUTRAL": 1,
        "H1 DATA INSUFFICIENT": 2,
    }

    eligible["_H1 Priority"] = (
        eligible["BUY NEW H1 Status"]
        .map(h1_priority)
        .fillna(2)
    )

else:

    eligible["_H1 Priority"] = 2


# ------------------------------------------------------------
# Apply the CURRENT production BUY NEW ranking.
# ------------------------------------------------------------

sort_columns = [
    "Investment Score",
    "Technical Score",
    "Quality Score",
    "Growth Score",
    "Confidence Score",
    "_H1 Priority",
]


ascending = [
    False,
    False,
    False,
    False,
    False,
    True,
]


if "Investment Rank" in eligible.columns:

    eligible["Investment Rank"] = pd.to_numeric(
        eligible["Investment Rank"],
        errors="coerce",
    ).fillna(999999)

    sort_columns.append("Investment Rank")
    ascending.append(True)


if "Ticker" in eligible.columns:

    sort_columns.append("Ticker")
    ascending.append(True)


eligible = (
    eligible
    .sort_values(
        by=sort_columns,
        ascending=ascending,
        na_position="last",
    )
    .reset_index(drop=True)
)


# ------------------------------------------------------------
# Display top 20.
# ------------------------------------------------------------

display_columns = [
    "Ticker",
    "Investment Score",
    "Technical Score",
    "Quality Score",
    "Growth Score",
    "Confidence Score",
]


for column in [
    "Valuation",
    "Entry Quality",
    "Entry Timing Status",
    "BUY NEW H1 Status",
    "Sector",
    "Country",
]:

    if column in eligible.columns:
        display_columns.append(column)


print()
print("=" * 80)
print("REAL BUY NEW PRIORITY TEST")
print("=" * 80)

print()
print(
    f"Snapshot candidates: {len(df)}"
)

print(
    f"BUY NEW eligible candidates: {len(eligible)}"
)

print()
print("TOP 20 UNDER CURRENT RANKING:")
print()

print(
    eligible[
        display_columns
    ].head(20).to_string(index=False)
)


print()
print("=" * 80)
print("TOP 3 BUY NEW")
print("=" * 80)

top3 = eligible.head(3)

print()

print(
    top3[
        display_columns
    ].to_string(index=False)
)

print()

print(
    "TOP 3 TICKERS:",
    top3["Ticker"].tolist()
)

print()
