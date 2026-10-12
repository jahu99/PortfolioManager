"""
Forensic BUY NEW factor contribution analysis.

READ-ONLY.
NO PRODUCTION CHANGES.

Observation unit:
    One unique recommendation_evidence row per BUY NEW recommendation_id.

Source of truth:
    audit_decisions.final_action = 'BUY NEW'
    joined to recommendation_evidence via recommendation_id

Purpose:
    Investigate which historical candidate characteristics are associated
    with realised BUY NEW forward performance.

This is an investigation only.
It does NOT change scoring, thresholds, weights, governance, or production logic.
"""

import sqlite3
import statistics
import math

DB = "data/portfolio_manager.db"


FACTORS = [
    "investment_score",
    "technical_score",
    "quality_score",
    "growth_score",
    "confidence_score",
    "revenue_growth",
    "profit_margin",
    "return_on_equity",
    "debt_to_equity",
    "rsi",
    "return_3m",
    "extension_sma50_pct",
    "extension_sma200_pct",
]


def correlation(xs, ys):
    pairs = [
        (float(x), float(y))
        for x, y in zip(xs, ys)
        if x is not None and y is not None
        and math.isfinite(float(x))
        and math.isfinite(float(y))
    ]

    if len(pairs) < 3:
        return None

    x = [p[0] for p in pairs]
    y = [p[1] for p in pairs]

    mx = statistics.mean(x)
    my = statistics.mean(y)

    numerator = sum(
        (a - mx) * (b - my)
        for a, b in pairs
    )

    denominator_x = math.sqrt(
        sum((a - mx) ** 2 for a in x)
    )

    denominator_y = math.sqrt(
        sum((b - my) ** 2 for b in y)
    )

    if denominator_x == 0 or denominator_y == 0:
        return None

    return numerator / (denominator_x * denominator_y)


def percentile(values, p):
    values = sorted(values)

    if not values:
        return None

    if len(values) == 1:
        return values[0]

    k = (len(values) - 1) * p
    f = math.floor(k)
    c = math.ceil(k)

    if f == c:
        return values[int(k)]

    return values[f] + (values[c] - values[f]) * (k - f)


conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=" * 100)
print("BUY NEW FACTOR CONTRIBUTION / SELECTION ANALYSIS")
print("READ-ONLY — NO PRODUCTION CHANGES")
print("=" * 100)

# ---------------------------------------------------------------------
# Unique BUY NEW evidence population
# ---------------------------------------------------------------------

cur.execute("""
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
        re.revenue_growth,
        re.profit_margin,
        re.return_on_equity,
        re.debt_to_equity,
        re.rsi,
        re.return_3m,
        re.extension_sma50_pct,
        re.extension_sma200_pct,
        re.entry_quality,
        re.return_5d_pct,
        re.return_10d_pct,
        re.return_20d_pct,
        re.sector,
        re.industry
    FROM audit_decisions ad
    JOIN recommendation_evidence re
      ON re.recommendation_id = ad.recommendation_id
    WHERE ad.final_action = 'BUY NEW'
      AND ad.recommendation_id IS NOT NULL
    GROUP BY ad.recommendation_id
    ORDER BY re.capture_date, ad.recommendation_id
""")

rows = cur.fetchall()

print()
print(f"Unique BUY NEW observations: {len(rows)}")

tickers = sorted(set(r["ticker"] for r in rows))

print(f"Unique BUY NEW tickers:      {len(tickers)}")
print(f"Tickers:                     {', '.join(tickers)}")

# ---------------------------------------------------------------------
# Realised performance
# ---------------------------------------------------------------------

for horizon in ["return_5d_pct", "return_10d_pct", "return_20d_pct"]:

    values = [
        float(r[horizon])
        for r in rows
        if r[horizon] is not None
    ]

    print()
    print(f"{horizon.upper()}")
    print("-" * 60)

    if not values:
        print("No observations.")
        continue

    positive = sum(v > 0 for v in values)

    print(f"n:             {len(values)}")
    print(f"Mean:          {statistics.mean(values):.3f}%")
    print(f"Median:        {statistics.median(values):.3f}%")
    print(f"Positive:      {positive}/{len(values)} "
          f"({positive / len(values) * 100:.2f}%)")

# ---------------------------------------------------------------------
# Factor correlations against 5D return
# ---------------------------------------------------------------------

print()
print("=" * 100)
print("FACTOR CORRELATIONS WITH 5D RETURN")
print("=" * 100)

correlations = []

for factor in FACTORS:

    xs = []
    ys = []

    for r in rows:
        if r["return_5d_pct"] is None:
            continue

        value = r[factor]

        if value is None:
            continue

        try:
            value = float(value)
            ret = float(r["return_5d_pct"])
        except (TypeError, ValueError):
            continue

        if not math.isfinite(value) or not math.isfinite(ret):
            continue

        xs.append(value)
        ys.append(ret)

    corr = correlation(xs, ys)

    correlations.append(
        (factor, len(xs), corr)
    )

for factor, n, corr in sorted(
    correlations,
    key=lambda x: abs(x[2]) if x[2] is not None else -1,
    reverse=True,
):
    if corr is None:
        print(f"{factor:<25} n={n:<3} correlation=NA")
    else:
        print(
            f"{factor:<25} "
            f"n={n:<3} "
            f"correlation={corr:+.3f}"
        )

# ---------------------------------------------------------------------
# High vs low factor split
# ---------------------------------------------------------------------

print()
print("=" * 100)
print("HIGH-vs-LOW FACTOR REALISED PERFORMANCE")
print("=" * 100)

for factor in FACTORS:

    observations = []

    for r in rows:
        value = r[factor]
        ret = r["return_5d_pct"]

        if value is None or ret is None:
            continue

        try:
            value = float(value)
            ret = float(ret)
        except (TypeError, ValueError):
            continue

        if not math.isfinite(value) or not math.isfinite(ret):
            continue

        observations.append((value, ret))

    if len(observations) < 6:
        continue

    values = [x[0] for x in observations]

    median_value = statistics.median(values)

    low = [
        ret
        for value, ret in observations
        if value <= median_value
    ]

    high = [
        ret
        for value, ret in observations
        if value > median_value
    ]

    if not low or not high:
        continue

    print()
    print(f"{factor}")
    print(f"  Median split: {median_value:.4f}")
    print(
        f"  Low  n={len(low):<2} "
        f"mean={statistics.mean(low):+.3f}% "
        f"positive={sum(x > 0 for x in low) / len(low) * 100:.1f}%"
    )
    print(
        f"  High n={len(high):<2} "
        f"mean={statistics.mean(high):+.3f}% "
        f"positive={sum(x > 0 for x in high) / len(high) * 100:.1f}%"
    )
    print(
        f"  High-minus-low mean delta: "
        f"{statistics.mean(high) - statistics.mean(low):+.3f}pp"
    )

# ---------------------------------------------------------------------
# Current BUY NEW score profile
# ---------------------------------------------------------------------

print()
print("=" * 100)
print("CURRENT BUY NEW PROFILE")
print("=" * 100)

for factor in FACTORS:

    values = []

    for r in rows:
        value = r[factor]

        if value is None:
            continue

        try:
            value = float(value)
        except (TypeError, ValueError):
            continue

        if math.isfinite(value):
            values.append(value)

    if not values:
        continue

    print(
        f"{factor:<25} "
        f"mean={statistics.mean(values):.3f} "
        f"median={statistics.median(values):.3f} "
        f"p25={percentile(values, 0.25):.3f} "
        f"p75={percentile(values, 0.75):.3f}"
    )

# ---------------------------------------------------------------------
# Individual observations
# ---------------------------------------------------------------------

print()
print("=" * 100)
print("INDIVIDUAL BUY NEW OBSERVATIONS")
print("=" * 100)

print(
    f"{'ID':>6} "
    f"{'Ticker':<7} "
    f"{'Date':<12} "
    f"{'Inv':>5} "
    f"{'Tech':>5} "
    f"{'Qual':>5} "
    f"{'Grow':>5} "
    f"{'Conf':>6} "
    f"{'5D':>8} "
    f"{'Entry':<22}"
)

print("-" * 100)

for r in rows:

    print(
        f"{r['recommendation_id']:>6} "
        f"{r['ticker']:<7} "
        f"{str(r['capture_date']):<12} "
        f"{float(r['investment_score']):>5.1f} "
        f"{float(r['technical_score']):>5.1f} "
        f"{float(r['quality_score']):>5.1f} "
        f"{float(r['growth_score']):>5.1f} "
        f"{float(r['confidence_score']):>6.1f} "
        f"{float(r['return_5d_pct']):>8.2f} "
        f"{str(r['entry_quality']):<22}"
    )

print()
print("=" * 100)
print("INTERPRETATION GUARDRAIL")
print("=" * 100)
print(
    "This is a forensic investigation of the current BUY NEW cohort."
)
print(
    "The sample is small and recent. Correlations and median splits "
    "are investigation signals, not evidence for automatic calibration."
)
print(
    "NO production thresholds, weights, scores, governance rules, "
    "or candidate-selection rules are changed by this script."
)

conn.close()
