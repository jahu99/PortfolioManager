#!/usr/bin/env python3

import sqlite3
import statistics
from pathlib import Path


DB_PATH = Path("data/portfolio_manager.db")


def pct(value):
    return f"{value:.2f}%" if value is not None else "N/A"


def median(values):
    return statistics.median(values) if values else None

def numeric_entry_quality(value):
    """Convert Entry Quality to float; return None when unavailable."""
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip().upper()

    # Handle common textual representations if present.
    if text in {"", "N/A", "NA", "NONE", "NULL", "UNKNOWN"}:
        return None

    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def main():
    print("=" * 90)
    print("ENTRY QUALITY — BUY NEW CALIBRATION TEST")
    print("=" * 90)
    print(f"Database: {DB_PATH}")
    print()

    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        # ------------------------------------------------------------------
        # 1. Inspect relevant schema
        # ------------------------------------------------------------------
        print("SCHEMA")
        print("-" * 90)

        for table in [
            "audit_decisions",
            "recommendation_evidence",
            "recommendation_evaluations",
        ]:
            columns = conn.execute(
                f"PRAGMA table_info({table})"
            ).fetchall()

            print(f"{table}:")
            print("  " + ", ".join(row["name"] for row in columns))
            print()

        # ------------------------------------------------------------------
        # 2. Find BUY NEW recommendations through audit_decisions
        # ------------------------------------------------------------------
        print("BUY NEW DATA")
        print("-" * 90)

        buy_new_ids = conn.execute(
            """
            SELECT DISTINCT recommendation_id
            FROM audit_decisions
            WHERE recommendation_id IS NOT NULL
              AND (
                    UPPER(TRIM(original_action)) = 'BUY NEW'
                 OR UPPER(TRIM(proposed_action)) = 'BUY NEW'
                 OR UPPER(TRIM(reconciled_action)) = 'BUY NEW'
                 OR UPPER(TRIM(final_action)) = 'BUY NEW'
              )
            """
        ).fetchall()

        recommendation_ids = [
            row["recommendation_id"]
            for row in buy_new_ids
        ]

        print(f"BUY NEW recommendation IDs: {len(recommendation_ids)}")

        if not recommendation_ids:
            print()
            print("No BUY NEW recommendations found in audit_decisions.")
            return

        # ------------------------------------------------------------------
        # 3. Get Entry Quality from recommendation_evidence
        # ------------------------------------------------------------------
        placeholders = ",".join("?" * len(recommendation_ids))

        evidence_rows = conn.execute(
            f"""
            SELECT
                recommendation_id,
                ticker,
                capture_date,
                entry_quality,
                entry_quality_mode,
                investment_score,
                technical_score,
                quality_score,
                growth_score,
                confidence_score,
                valuation,
                valuation_mode
            FROM recommendation_evidence
            WHERE recommendation_id IN ({placeholders})
              AND entry_quality IS NOT NULL
            ORDER BY recommendation_id, capture_date DESC
            """,
            recommendation_ids,
        ).fetchall()

        # Keep the latest evidence row for each recommendation.
        evidence_by_id = {}

        for row in evidence_rows:
            rid = row["recommendation_id"]

            if rid not in evidence_by_id:
                evidence_by_id[rid] = row

        print(f"BUY NEW recommendations with Entry Quality: {len(evidence_by_id)}")

        # ------------------------------------------------------------------
        # 4. Get matured 5D outcomes
        # ------------------------------------------------------------------
        evaluation_rows = conn.execute(
            f"""
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
            """,
            recommendation_ids,
        ).fetchall()

        # One independent 5D outcome per recommendation.
        outcome_by_id = {}

        for row in evaluation_rows:
            rid = row["recommendation_id"]

            if rid not in outcome_by_id:
                outcome_by_id[rid] = row

        print(f"BUY NEW recommendations with matured 5D outcome: {len(outcome_by_id)}")

        # ------------------------------------------------------------------
        # 5. Join Entry Quality + independent 5D outcome
        # ------------------------------------------------------------------
        observations = []

        for rid, evidence in evidence_by_id.items():
            outcome = outcome_by_id.get(rid)

            if outcome is None:
                continue

            observations.append(
                {
                    "recommendation_id": rid,
                    "ticker": evidence["ticker"],
                    "capture_date": evidence["capture_date"],
                   "entry_quality": (
                        str(evidence["entry_quality"]).strip().upper()
                        if evidence["entry_quality"] is not None
                        else "UNKNOWN"
                    ),
                    "entry_quality_mode": evidence["entry_quality_mode"],
                    "investment_score": evidence["investment_score"],
                    "confidence_score": evidence["confidence_score"],
                    "valuation": evidence["valuation"],
                    "valuation_mode": evidence["valuation_mode"],
                    "return_5d": float(outcome["return_percent"]),
                }
            )

        print(f"Independent matured observations: {len(observations)}")
        print()

        if not observations:
            print("No usable independent BUY NEW + Entry Quality + 5D observations.")
            return

        # ------------------------------------------------------------------
        # 6. Overall Entry Quality relationship
        # ------------------------------------------------------------------
        print("OVERALL RESULT")
        print("-" * 90)

        returns = [x["return_5d"] for x in observations]

        print(f"Observations:       {len(observations)}")
        print(f"Average 5D return:  {pct(sum(returns) / len(returns))}")
        print(f"Median 5D return:   {pct(median(returns))}")
        print(
            f"Positive 5D:        "
            f"{sum(r > 0 for r in returns) / len(returns) * 100:.2f}%"
        )

        # ------------------------------------------------------------------
        # 7. Entry Quality bands
        # ------------------------------------------------------------------
        print()
        print("ENTRY QUALITY BANDS")
        print("-" * 90)

        bands = [
            ("< 50", lambda x: x < 50),
            ("50–59", lambda x: 50 <= x < 60),
            ("60–69", lambda x: 60 <= x < 70),
            ("70–79", lambda x: 70 <= x < 80),
            ("80–89", lambda x: 80 <= x < 90),
            ("90+", lambda x: x >= 90),
        ]

        print(
            f"{'Band':<10}"
            f"{'N':>8}"
            f"{'Avg 5D':>12}"
            f"{'Median':>12}"
            f"{'Positive':>12}"
        )

        print("-" * 54)

        for name, condition in bands:
            rows = [
                x for x in observations
                if condition(x["entry_quality"])
            ]

            if not rows:
                continue

            band_returns = [x["return_5d"] for x in rows]

            print(
                f"{name:<10}"
                f"{len(rows):>8}"
                f"{sum(band_returns) / len(band_returns):>11.2f}%"
                f"{median(band_returns):>11.2f}%"
                f"{sum(r > 0 for r in band_returns) / len(band_returns) * 100:>11.2f}%"
            )

        # ------------------------------------------------------------------
        # 8. High vs low Entry Quality
        # ------------------------------------------------------------------
        print()
        print("HIGH vs LOW ENTRY QUALITY")
        print("-" * 90)

        low = [
            x for x in observations
            if x["entry_quality"] < 70
        ]

        high = [
            x for x in observations
            if x["entry_quality"] >= 70
        ]

        def print_group(name, rows):
            if not rows:
                print(f"{name:<20} N=0")
                return

            rs = [x["return_5d"] for x in rows]

            print(
                f"{name:<20}"
                f"N={len(rows):>4}  "
                f"Avg={sum(rs) / len(rs):>7.2f}%  "
                f"Median={median(rs):>7.2f}%  "
                f"Positive={sum(r > 0 for r in rs) / len(rs) * 100:>6.2f}%"
            )

        print_group("Entry Quality <70", low)
        print_group("Entry Quality >=70", high)

        if low and high:
            low_avg = sum(x["return_5d"] for x in low) / len(low)
            high_avg = sum(x["return_5d"] for x in high) / len(high)

            print()
            print(
                f"Average-return advantage of >=70: "
                f"{high_avg - low_avg:+.2f} percentage points"
            )

        # ------------------------------------------------------------------
        # 9. Show individual observations
        # ------------------------------------------------------------------
        print()
        print("INDIVIDUAL OBSERVATIONS")
        print("-" * 90)

        print(
            f"{'Ticker':<8}"
            f"{'Entry Q':>10}"
            f"{'Inv':>8}"
            f"{'Confidence':>12}"
            f"{'Valuation':>15}"
            f"{'5D Return':>12}"
        )

        print("-" * 70)

        for x in sorted(
            observations,
            key=lambda y: y["entry_quality"],
            reverse=True,
        ):
            print(
                f"{str(x['ticker']):<8}"
                f"{x['entry_quality']:>10.1f}"
                f"{str(x['investment_score'] or ''):>8}"
                f"{str(x['confidence_score'] or ''):>12}"
                f"{str(x['valuation'] or ''):>15}"
                f"{x['return_5d']:>11.2f}%"
            )

        # ------------------------------------------------------------------
        # 10. Interpretation
        # ------------------------------------------------------------------
        print()
        print("=" * 90)
        print("CALIBRATION INTERPRETATION")
        print("=" * 90)

        if len(observations) < 20:
            print(
                "WARNING: Sample is small. Treat any Entry Quality relationship "
                "as indicative, not production-calibration evidence."
            )

        if low and high:
            difference = high_avg - low_avg

            if difference > 1.0:
                print(
                    "Entry Quality shows a potentially useful positive relationship "
                    "with realised BUY NEW performance."
                )
            elif difference < -1.0:
                print(
                    "Entry Quality is behaving counter-intuitively in this cohort: "
                    "higher Entry Quality has worse realised performance."
                )
            else:
                print(
                    "Entry Quality does not show a strong separation between "
                    "higher- and lower-quality entries."
                )

        print()
        print(
            "IMPORTANT: This test is observational. It does not justify changing "
            "BUY NEW thresholds by itself."
        )
        print(
            "A production calibration change should also test temporal stability, "
            "independent recommendations, and whether Entry Quality adds information "
            "beyond Investment Score, Evidence Score, Confidence and valuation."
        )

    finally:
        conn.close()


if __name__ == "__main__":
    main()