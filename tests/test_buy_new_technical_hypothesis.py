"""
BUY NEW Technical Hypothesis Investigation
===========================================

READ-ONLY INVESTIGATION — NO PRODUCTION CHANGES.

Hypothesis:
    For BUY NEW decisions, short-term momentum quality — particularly
    RSI within the bullish range combined with moderate rather than
    excessive 3-month performance — may be more predictive of near-term
    outcome than aggregate Technical Score.

Uses:
    audit_decisions
        -> recommendation_evidence

Important:
    audit_decisions contains repeated audit processing of the same
    underlying recommendation. Therefore this test deduplicates to one
    row per recommendation_id before calculating statistics.
"""

import math
import os
import sqlite3
from statistics import mean, median


# ============================================================
# CONFIGURATION
# ============================================================

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "portfolio_manager.db",
)

MATURITY_DAYS = 5


# ============================================================
# HELPERS
# ============================================================

def pearson(x_values, y_values):
    pairs = [
        (float(x), float(y))
        for x, y in zip(x_values, y_values)
        if x is not None
        and y is not None
        and math.isfinite(float(x))
        and math.isfinite(float(y))
    ]

    if len(pairs) < 3:
        return None

    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]

    x_mean = mean(xs)
    y_mean = mean(ys)

    numerator = sum(
        (x - x_mean) * (y - y_mean)
        for x, y in pairs
    )

    x_denominator = math.sqrt(
        sum((x - x_mean) ** 2 for x in xs)
    )

    y_denominator = math.sqrt(
        sum((y - y_mean) ** 2 for y in ys)
    )

    if x_denominator == 0 or y_denominator == 0:
        return None

    return numerator / (
        x_denominator * y_denominator
    )


def fmt(value, digits=3):
    if value is None:
        return "N/A"

    return f"{value:.{digits}f}"


def pct(value):
    if value is None:
        return "N/A"

    return f"{value:.2f}%"


def group_stats(rows, label):
    returns_5d = [
        float(r["return_5d_pct"])
        for r in rows
        if r["return_5d_pct"] is not None
    ]

    returns_10d = [
        float(r["return_10d_pct"])
        for r in rows
        if r["return_10d_pct"] is not None
    ]

    returns_20d = [
        float(r["return_20d_pct"])
        for r in rows
        if r["return_20d_pct"] is not None
    ]

    positive = [
        r
        for r in rows
        if r["return_5d_pct"] is not None
        and float(r["return_5d_pct"]) > 0
    ]

    print(f"\n{label}")
    print("-" * len(label))
    print(f"n:             {len(rows)}")

    if returns_5d:
        print(
            f"5D mean:       {pct(mean(returns_5d))}"
        )
        print(
            f"5D median:     {pct(median(returns_5d))}"
        )
        print(
            f"5D positive:   {len(positive) / len(returns_5d) * 100:.2f}%"
        )
    else:
        print("5D mean:       N/A")
        print("5D median:     N/A")
        print("5D positive:   N/A")

    if returns_10d:
        print(
            f"10D mean:      {pct(mean(returns_10d))}"
        )
    else:
        print("10D mean:      N/A")

    if returns_20d:
        print(
            f"20D mean:      {pct(mean(returns_20d))}"
        )
    else:
        print("20D mean:      N/A")


def median_split(rows, field, label):
    values = [
        float(r[field])
        for r in rows
        if r[field] is not None
    ]

    if not values:
        return

    threshold = median(values)

    low = [
        r for r in rows
        if r[field] is not None
        and float(r[field]) < threshold
    ]

    high = [
        r for r in rows
        if r[field] is not None
        and float(r[field]) >= threshold
    ]

    print(f"\n{label}")
    print(
        f"Median split: {threshold:.3f}"
    )

    group_stats(low, "LOW")
    group_stats(high, "HIGH")


# ============================================================
# LOAD AUTHORITATIVE BUY NEW EVIDENCE
# ============================================================

print()
print("=" * 72)
print("BUY NEW TECHNICAL HYPOTHESIS INVESTIGATION")
print("=" * 72)
print()
print("READ-ONLY — NO PRODUCTION CHANGES")
print(f"Database: {DB_PATH}")
print()

if not os.path.exists(DB_PATH):
    raise SystemExit(
        f"ERROR: Database not found:\n{DB_PATH}"
    )


conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

query = """
SELECT
    ad.recommendation_id,

    re.ticker,
    re.capture_date,
    re.signal,

    re.investment_score,
    re.technical_score,
    re.quality_score,
    re.growth_score,
    re.confidence_score,

    re.rsi,
    re.return_3m,

    re.trend_score,
    re.momentum_score,
    re.volume_score,
    re.risk_score,

    re.extension_sma50_pct,
    re.extension_sma200_pct,

    re.return_5d_pct,
    re.return_10d_pct,
    re.return_20d_pct,

    re.entry_quality,
    re.entry_quality_mode

FROM audit_decisions ad

JOIN recommendation_evidence re
    ON re.recommendation_id = ad.recommendation_id

WHERE ad.final_action = 'BUY NEW'

  AND ad.recommendation_id IS NOT NULL

ORDER BY
    re.capture_date,
    ad.recommendation_id
"""

rows = conn.execute(query).fetchall()
conn.close()


# ============================================================
# DEDUPLICATE REPEATED AUDIT PROCESSING
# ============================================================

unique = {}

for row in rows:
    recommendation_id = row["recommendation_id"]

    if recommendation_id not in unique:
        unique[recommendation_id] = row

rows = list(unique.values())


print(f"BUY NEW audit rows:             {len(rows)}")
print(
    f"Unique recommendations:         {len(rows)}"
)

mature = [
    r for r in rows
    if r["return_5d_pct"] is not None
]

print(
    f"Unique recommendations with 5D: {len(mature)}"
)

if len(mature) < 5:
    raise SystemExit(
        "ERROR: Too few mature BUY NEW observations."
    )


# ============================================================
# BASIC PROFILE
# ============================================================

print()
print("=" * 72)
print("BUY NEW PROFILE")
print("=" * 72)

for field in [
    "investment_score",
    "technical_score",
    "quality_score",
    "growth_score",
    "confidence_score",
    "rsi",
    "return_3m",
    "trend_score",
    "momentum_score",
    "volume_score",
    "risk_score",
    "extension_sma50_pct",
    "extension_sma200_pct",
]:
    values = [
        float(r[field])
        for r in mature
        if r[field] is not None
    ]

    if not values:
        continue

    print(
        f"{field:25s}"
        f" n={len(values):2d}"
        f" mean={mean(values):8.3f}"
        f" median={median(values):8.3f}"
    )


# ============================================================
# COMPONENT CORRELATIONS
# ============================================================

print()
print("=" * 72)
print("COMPONENT CORRELATIONS WITH 5D RETURN")
print("=" * 72)

for field in [
    "rsi",
    "return_3m",
    "trend_score",
    "momentum_score",
    "volume_score",
    "risk_score",
    "technical_score",
    "investment_score",
    "confidence_score",
    "extension_sma50_pct",
    "extension_sma200_pct",
    "quality_score",
    "growth_score",
]:
    x = []
    y = []

    for r in mature:
        if (
            r[field] is not None
            and r["return_5d_pct"] is not None
        ):
            x.append(float(r[field]))
            y.append(float(r["return_5d_pct"]))

    print(
        f"{field:25s}"
        f" r={fmt(pearson(x, y), 3)}"
    )


# ============================================================
# 10D / 20D CORRELATIONS
# ============================================================

print()
print("=" * 72)
print("RSI / 3M RETURN CORRELATIONS BY HORIZON")
print("=" * 72)

for horizon in [
    "return_5d_pct",
    "return_10d_pct",
    "return_20d_pct",
]:
    print()
    print(horizon)

    for field in [
        "rsi",
        "return_3m",
        "technical_score",
    ]:
        x = []
        y = []

        for r in rows:
            if (
                r[field] is not None
                and r[horizon] is not None
            ):
                x.append(float(r[field]))
                y.append(float(r[horizon]))

        print(
            f"  {field:20s}"
            f" r={fmt(pearson(x, y), 3)}"
        )


# ============================================================
# MEDIAN SPLITS
# ============================================================

print()
print("=" * 72)
print("MEDIAN SPLIT ANALYSIS")
print("=" * 72)

median_split(
    mature,
    "rsi",
    "RSI"
)

median_split(
    mature,
    "return_3m",
    "3-MONTH RETURN"
)

median_split(
    mature,
    "technical_score",
    "TECHNICAL SCORE"
)


# ============================================================
# RSI × 3M RETURN INTERACTION
# ============================================================

print()
print("=" * 72)
print("RSI × 3-MONTH RETURN INTERACTION")
print("=" * 72)

rsi_values = [
    float(r["rsi"])
    for r in mature
    if r["rsi"] is not None
]

return_3m_values = [
    float(r["return_3m"])
    for r in mature
    if r["return_3m"] is not None
]

rsi_median = median(rsi_values)
return_3m_median = median(return_3m_values)

print(
    f"RSI median:       {rsi_median:.3f}"
)

print(
    f"Return_3m median: {return_3m_median:.3f}"
)


groups = {
    "HIGH RSI + LOW 3M": [],
    "HIGH RSI + HIGH 3M": [],
    "LOW RSI + LOW 3M": [],
    "LOW RSI + HIGH 3M": [],
}

for r in mature:

    if (
        r["rsi"] is None
        or r["return_3m"] is None
    ):
        continue

    high_rsi = (
        float(r["rsi"]) >= rsi_median
    )

    high_3m = (
        float(r["return_3m"]) >= return_3m_median
    )

    if high_rsi and not high_3m:
        groups["HIGH RSI + LOW 3M"].append(r)

    elif high_rsi and high_3m:
        groups["HIGH RSI + HIGH 3M"].append(r)

    elif not high_rsi and not high_3m:
        groups["LOW RSI + LOW 3M"].append(r)

    else:
        groups["LOW RSI + HIGH 3M"].append(r)


for label, group in groups.items():
    group_stats(group, label)


# ============================================================
# RSI BANDS
# ============================================================

print()
print("=" * 72)
print("RSI BAND ANALYSIS")
print("=" * 72)

rsi_bands = {
    "<50": [],
    "50-55": [],
    "55-60": [],
    "60-65": [],
    "65-70": [],
    ">=70": [],
}

for r in mature:

    if r["rsi"] is None:
        continue

    value = float(r["rsi"])

    if value < 50:
        rsi_bands["<50"].append(r)

    elif value < 55:
        rsi_bands["50-55"].append(r)

    elif value < 60:
        rsi_bands["55-60"].append(r)

    elif value < 65:
        rsi_bands["60-65"].append(r)

    elif value < 70:
        rsi_bands["65-70"].append(r)

    else:
        rsi_bands[">=70"].append(r)


for label, group in rsi_bands.items():
    group_stats(group, f"RSI {label}")


# ============================================================
# 3M RETURN BANDS
# ============================================================

print()
print("=" * 72)
print("3-MONTH RETURN BAND ANALYSIS")
print("=" * 72)

return_bands = {
    "<=0%": [],
    "0-10%": [],
    "10-20%": [],
    "20-30%": [],
    ">=30%": [],
}

for r in mature:

    if r["return_3m"] is None:
        continue

    value = float(r["return_3m"])

    if value <= 0:
        return_bands["<=0%"].append(r)

    elif value < 10:
        return_bands["0-10%"].append(r)

    elif value < 20:
        return_bands["10-20%"].append(r)

    elif value < 30:
        return_bands["20-30%"].append(r)

    else:
        return_bands[">=30%"].append(r)


for label, group in return_bands.items():
    group_stats(group, f"3M RETURN {label}")


# ============================================================
# TECHNICAL COMPONENT COMBINATIONS
# ============================================================

print()
print("=" * 72)
print("TECHNICAL COMPONENT COMBINATIONS")
print("=" * 72)

# These are descriptive combinations rather than new scoring rules.

combinations = {
    "HIGH RSI + MODERATE 3M (10-20%)": [
        r for r in mature
        if r["rsi"] is not None
        and r["return_3m"] is not None
        and float(r["rsi"]) >= 55
        and 10 <= float(r["return_3m"]) < 20
    ],

    "HIGH RSI + 3M >20%": [
        r for r in mature
        if r["rsi"] is not None
        and r["return_3m"] is not None
        and float(r["rsi"]) >= 55
        and float(r["return_3m"]) >= 20
    ],

    "RSI <55 + 3M >20%": [
        r for r in mature
        if r["rsi"] is not None
        and r["return_3m"] is not None
        and float(r["rsi"]) < 55
        and float(r["return_3m"]) >= 20
    ],

    "RSI <55 + 3M <20%": [
        r for r in mature
        if r["rsi"] is not None
        and r["return_3m"] is not None
        and float(r["rsi"]) < 55
        and float(r["return_3m"]) < 20
    ],
}

for label, group in combinations.items():
    group_stats(group, label)


# ============================================================
# INDIVIDUAL OBSERVATIONS
# ============================================================

print()
print("=" * 72)
print("UNDERLYING BUY NEW OBSERVATIONS")
print("=" * 72)

print(
    f"{'ID':>6} "
    f"{'Ticker':<7} "
    f"{'RSI':>6} "
    f"{'3M':>8} "
    f"{'Tech':>6} "
    f"{'Trend':>6} "
    f"{'Mom':>6} "
    f"{'Vol':>6} "
    f"{'Risk':>6} "
    f"{'5D':>8} "
    f"{'10D':>8} "
    f"{'20D':>8}"
)

print("-" * 90)

for r in mature:

    print(
        f"{r['recommendation_id']:>6} "
        f"{str(r['ticker']):<7} "
        f"{float(r['rsi']):>6.1f} "
        f"{float(r['return_3m']):>8.2f} "
        f"{float(r['technical_score']):>6.1f} "
        f"{float(r['trend_score']):>6.1f} "
        f"{float(r['momentum_score']):>6.1f} "
        f"{float(r['volume_score']):>6.1f} "
        f"{float(r['risk_score']):>6.1f} "
        f"{float(r['return_5d_pct']):>8.2f} "
        f"{float(r['return_10d_pct']):>8.2f}"
        if r["return_10d_pct"] is not None
        else f"{'N/A':>8}",
        end=""
    )

    if r["return_20d_pct"] is not None:
        print(
            f" {float(r['return_20d_pct']):>8.2f}"
        )
    else:
        print(f" {'N/A':>8}")


# ============================================================
# HYPOTHESIS ASSESSMENT
# ============================================================

print()
print("=" * 72)
print("HYPOTHESIS ASSESSMENT")
print("=" * 72)

rsi_5d = [
    float(r["rsi"])
    for r in mature
    if r["rsi"] is not None
    and r["return_5d_pct"] is not None
]

rsi_returns = [
    float(r["return_5d_pct"])
    for r in mature
    if r["rsi"] is not None
    and r["return_5d_pct"] is not None
]

ret3m_values = [
    float(r["return_3m"])
    for r in mature
    if r["return_3m"] is not None
    and r["return_5d_pct"] is not None
]

ret3m_returns = [
    float(r["return_5d_pct"])
    for r in mature
    if r["return_3m"] is not None
    and r["return_5d_pct"] is not None
]

technical_values = [
    float(r["technical_score"])
    for r in mature
    if r["technical_score"] is not None
    and r["return_5d_pct"] is not None
]

technical_returns = [
    float(r["return_5d_pct"])
    for r in mature
    if r["technical_score"] is not None
    and r["return_5d_pct"] is not None
]

rsi_corr = pearson(
    rsi_5d,
    rsi_returns
)

return_3m_corr = pearson(
    ret3m_values,
    ret3m_returns
)

technical_corr = pearson(
    technical_values,
    technical_returns
)

print()
print(
    f"RSI vs 5D:          {fmt(rsi_corr)}"
)

print(
    f"Return_3m vs 5D:    {fmt(return_3m_corr)}"
)

print(
    f"Technical vs 5D:    {fmt(technical_corr)}"
)

print()

if (
    rsi_corr is not None
    and return_3m_corr is not None
    and technical_corr is not None
    and rsi_corr > 0.40
    and return_3m_corr < -0.30
    and abs(technical_corr) < 0.20
):
    print(
        "INITIAL RESULT: H1 IS CONSISTENT WITH THE CURRENT SAMPLE."
    )
    print()
    print(
        "The component-level evidence is materially stronger"
    )
    print(
        "than the aggregate Technical Score relationship."
    )
    print()
    print(
        "This is NOT sufficient evidence for a production change."
    )
    print(
        "Proceed to an out-of-sample hypothesis test."
    )

else:
    print(
        "INITIAL RESULT: H1 IS NOT CLEARLY SUPPORTED."
    )
    print()
    print(
        "Do NOT change production scoring based on this evidence."
    )

print()
print("=" * 72)
print("END — READ-ONLY / NO PRODUCTION CHANGES")
print("=" * 72)
