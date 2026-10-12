#!/usr/bin/env python3

import sqlite3
import statistics
from pathlib import Path


DB_PATH = Path("data/portfolio_manager.db")


def percentile(values, p):
    """Simple percentile calculation."""
    if not values:
        return None

    values = sorted(values)

    k = (len(values) - 1) * p
    f = int(k)
    c = min(f + 1, len(values))

    if f == c:
        return values[f]

    return values[f] + (values[c] - values[f]) * (k - f)


def fmt(value, decimals=2):
    if value is None:
        return "N/A"
    return f"{value:.{decimals}f}"


def main():

    print("=" * 88)
    print("ENTRY QUALITY — BUY NEW CALIBRATION TEST")
    print("=" * 88)
    print(f"Database: {DB_PATH}")
    print()

    if not DB_PATH.exists():
        print(f"ERROR: Database not found: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # -------------------------------------------------------------------------
    # STEP 1 — Identify independent BUY NEW recommendations
    # -------------------------------------------------------------------------

    print("STEP 1 — IDENTIFYING BUY NEW RECOMMENDATIONS")
    print("=" * 88)

    buy_new_sql = """
        SELECT
            ad.recommendation_id,
            ad.ticker,
            ad.created_at,
            ad.final_action,
            ad.proposed_action,
            ad.original_action
        FROM audit_decisions ad
        WHERE ad.recommendation_id IS NOT NULL
          AND (
                UPPER(ad.final_action) = 'BUY NEW'
                OR UPPER(ad.proposed_action) = 'BUY NEW'
                OR UPPER(ad.original_action) = 'BUY NEW'
              )
        ORDER BY ad.created_at
    """

    rows = conn.execute(buy_new_sql).fetchall()

    # Deduplicate recommendation IDs.
    buy_new = {}

    for row in rows:
        rid = row["recommendation_id"]

        if rid not in buy_new:
            buy_new[rid] = row

    print(f"Raw BUY NEW audit rows:       {len(rows):,}")
    print(f"Independent recommendation IDs: {len(buy_new):,}")
    print()

    if not buy_new:
        print("No BUY NEW recommendations found.")
        conn.close()
        return

    # -------------------------------------------------------------------------
    # STEP 2 — Join Entry Quality from recommendation_evidence
    # -------------------------------------------------------------------------

    print("STEP 2 — JOINING ENTRY QUALITY")
    print("=" * 88)

    placeholders = ",".join("?" for _ in buy_new)

    evidence_sql = f"""
        SELECT
            recommendation_id,
            ticker,
            capture_date,
            entry_quality,
            entry_quality_mode,
            investment_score,
            signal,
            valuation,
            valuation_mode
        FROM recommendation_evidence
        WHERE recommendation_id IN ({placeholders})
          AND entry_quality IS NOT NULL
        ORDER BY recommendation_id, capture_date
    """

    evidence_rows = conn.execute(
        evidence_sql,
        list(buy_new.keys())
    ).fetchall()

    # One evidence observation per recommendation:
    # use the earliest evidence capture for the recommendation.
    evidence_by_id = {}

    for row in evidence_rows:
        rid = row["recommendation_id"]

        if rid not in evidence_by_id:
            evidence_by_id[rid] = row

    print(f"BUY NEW IDs with Entry Quality: {len(evidence_by_id):,}")
    print(
        f"BUY NEW IDs without Entry Quality: "
        f"{len(buy_new) - len(evidence_by_id):,}"
    )
    print()

    # -------------------------------------------------------------------------
    # STEP 3 — Join matured 5D outcomes
    # -------------------------------------------------------------------------

    print("STEP 3 — JOINING 5D REALISED OUTCOMES")
    print("=" * 88)

    evaluations_sql = f"""
        SELECT
            recommendation_id,
            ticker,
            evaluation_date,
            days_after,
            return_percent,
            outcome
        FROM recommendation_evaluations
        WHERE recommendation_id IN ({placeholders})
          AND days_after = 5
          AND return_percent IS NOT NULL
        ORDER BY recommendation_id, evaluation_date
    """

    evaluation_rows = conn.execute(
        evaluations_sql,
        list(buy_new.keys())
    ).fetchall()

    # One 5D observation per recommendation.
    evaluation_by_id = {}

    for row in evaluation_rows:
        rid = row["recommendation_id"]

        if rid not in evaluation_by_id:
            evaluation_by_id[rid] = row

    print(f"Matured 5D BUY NEW IDs: {len(evaluation_by_id):,}")
    print()

    # -------------------------------------------------------------------------
    # STEP 4 — Build independent calibration dataset
    # -------------------------------------------------------------------------

    observations = []

    for rid, bn in buy_new.items():

        evidence = evidence_by_id.get(rid)
        evaluation = evaluation_by_id.get(rid)

        if evidence is None or evaluation is None:
            continue

        try:
            entry_quality = float(evidence["entry_quality"])
            realised_return = float(evaluation["return_percent"])
        except (TypeError, ValueError):
            continue

        observations.append(
            {
                "recommendation_id": rid,
                "ticker": bn["ticker"],
                "created_at": bn["created_at"],
                "entry_quality": entry_quality,
                "entry_quality_mode": evidence["entry_quality_mode"],
                "investment_score": evidence["investment_score"],
                "valuation": evidence["valuation"],
                "realised_return": realised_return,
            }
        )

    print("=" * 88)
    print("INDEPENDENT MATURED BUY NEW DATASET")
    print("=" * 88)

    print(f"Independent matured observations: {len(observations):,}")

    if not observations:
        print()
        print("No usable matured BUY NEW observations found.")
        print()
        print("Diagnostic counts:")
        print(f"  BUY NEW IDs:                 {len(buy_new):,}")
        print(f"  With Entry Quality:          {len(evidence_by_id):,}")
        print(f"  With 5D evaluation:          {len(evaluation_by_id):,}")
        conn.close()
        return

    returns = [x["realised_return"] for x in observations]

    print(f"Average 5D return:             {fmt(statistics.mean(returns))}%")
    print(f"Median 5D return:              {fmt(statistics.median(returns))}%")
    print(
        f"Positive 5D outcomes:          "
        f"{sum(r > 0 for r in returns) / len(returns) * 100:.2f}%"
    )
    print()

    # -------------------------------------------------------------------------
    # STEP 5 — Entry Quality distribution
    # -------------------------------------------------------------------------

    print("=" * 88)
    print("ENTRY QUALITY DISTRIBUTION")
    print("=" * 88)

    entry_values = [x["entry_quality"] for x in observations]

    print(f"Minimum:                        {fmt(min(entry_values))}")
    print(f"25th percentile:               {fmt(percentile(entry_values, 0.25))}")
    print(f"Median:                        {fmt(percentile(entry_values, 0.50))}")
    print(f"75th percentile:               {fmt(percentile(entry_values, 0.75))}")
    print(f"Maximum:                        {fmt(max(entry_values))}")
    print()

    # -------------------------------------------------------------------------
    # STEP 6 — Bucket Entry Quality
    # -------------------------------------------------------------------------

    buckets = [
        ("0–59", lambda x: x < 60),
        ("60–69", lambda x: 60 <= x < 70),
        ("70–79", lambda x: 70 <= x < 80),
        ("80–89", lambda x: 80 <= x < 90),
        ("90–100", lambda x: x >= 90),
    ]

    print("=" * 88)
    print("BUY NEW PERFORMANCE BY ENTRY QUALITY")
    print("=" * 88)

    print(
        f"{'Entry Quality':<16}"
        f"{'N':>7}"
        f"{'Avg 5D':>14}"
        f"{'Median 5D':>14}"
        f"{'Positive':>14}"
    )
    print("-" * 88)

    bucket_results = []

    for label, condition in buckets:

        bucket = [
            x for x in observations
            if condition(x["entry_quality"])
        ]

        if not bucket:
            print(
                f"{label:<16}"
                f"{0:>7}"
                f"{'N/A':>14}"
                f"{'N/A':>14}"
                f"{'N/A':>14}"
            )
            continue

        bucket_returns = [
            x["realised_return"]
            for x in bucket
        ]

        avg_return = statistics.mean(bucket_returns)
        median_return = statistics.median(bucket_returns)
        positive_rate = (
            sum(r > 0 for r in bucket_returns)
            / len(bucket_returns)
            * 100
        )

        bucket_results.append(
            {
                "label": label,
                "n": len(bucket),
                "avg": avg_return,
                "median": median_return,
                "positive": positive_rate,
            }
        )

        print(
            f"{label:<16}"
            f"{len(bucket):>7}"
            f"{avg_return:>13.2f}%"
            f"{median_return:>13.2f}%"
            f"{positive_rate:>13.2f}%"
        )

    # -------------------------------------------------------------------------
    # STEP 7 — High vs lower Entry Quality
    # -------------------------------------------------------------------------

    print()
    print("=" * 88)
    print("HIGH ENTRY QUALITY TEST")
    print("=" * 88)

    high = [
        x for x in observations
        if x["entry_quality"] >= 80
    ]

    lower = [
        x for x in observations
        if x["entry_quality"] < 80
    ]

    def print_group(label, group):

        if not group:
            print(f"{label:<25} N=0")
            return None

        rs = [x["realised_return"] for x in group]

        avg = statistics.mean(rs)
        median = statistics.median(rs)
        positive = sum(r > 0 for r in rs) / len(rs) * 100

        print(
            f"{label:<25}"
            f"N={len(group):>4}  "
            f"Avg={avg:>7.2f}%  "
            f"Median={median:>7.2f}%  "
            f"Positive={positive:>6.2f}%"
        )

        return avg

    high_avg = print_group("Entry Quality >= 80", high)
    lower_avg = print_group("Entry Quality < 80", lower)

    if high_avg is not None and lower_avg is not None:
        print()
        print(
            f"Average-return advantage of >=80: "
            f"{high_avg - lower_avg:+.2f} percentage points"
        )

    # -------------------------------------------------------------------------
    # STEP 8 — Correlation
    # -------------------------------------------------------------------------

    print()
    print("=" * 88)
    print("ENTRY QUALITY / REALISED RETURN RELATIONSHIP")
    print("=" * 88)

    if len(observations) >= 3:

        xs = [x["entry_quality"] for x in observations]
        ys = [x["realised_return"] for x in observations]

        x_mean = statistics.mean(xs)
        y_mean = statistics.mean(ys)

        numerator = sum(
            (x - x_mean) * (y - y_mean)
            for x, y in zip(xs, ys)
        )

        denominator = (
            sum((x - x_mean) ** 2 for x in xs)
            * sum((y - y_mean) ** 2 for y in ys)
        ) ** 0.5

        correlation = (
            numerator / denominator
            if denominator
            else None
        )

        print(
            f"Pearson correlation: "
            f"{fmt(correlation, 3) if correlation is not None else 'N/A'}"
        )

    # -------------------------------------------------------------------------
    # STEP 9 — Individual observations
    # -------------------------------------------------------------------------

    print()
    print("=" * 88)
    print("INDIVIDUAL INDEPENDENT OBSERVATIONS")
    print("=" * 88)

    print(
        f"{'Ticker':<10}"
        f"{'EntryQ':>9}"
        f"{'InvScore':>10}"
        f"{'Valuation':>15}"
        f"{'5D Return':>13}"
    )
    print("-" * 88)

    for x in sorted(
        observations,
        key=lambda r: r["entry_quality"],
        reverse=True
    ):
        print(
            f"{str(x['ticker']):<10}"
            f"{x['entry_quality']:>9.1f}"
            f"{float(x['investment_score']):>10.1f}"
            f"{str(x['valuation'] or ''):>15}"
            f"{x['realised_return']:>12.2f}%"
        )

    # -------------------------------------------------------------------------
    # CONCLUSION
    # -------------------------------------------------------------------------

    print()
    print("=" * 88)
    print("CALIBRATION INTERPRETATION")
    print("=" * 88)

    print(
        """
This test is descriptive, not a production-rule recommendation.

Evidence for Entry Quality as a useful BUY NEW discriminator would be
stronger if:

  1. Higher Entry Quality buckets show consistently better realised returns.
  2. Positive-rate improves as Entry Quality increases.
  3. Entry Quality >=80 materially outperforms Entry Quality <80.
  4. The relationship is not driven by only one or two observations.
  5. The relationship remains visible in an independent/out-of-sample cohort.
  6. Any improvement remains after considering Investment Score and valuation.

A non-monotonic result means Entry Quality should NOT automatically become
a hard BUY NEW eligibility threshold.
"""
    )

    conn.close()


if __name__ == "__main__":
    main()