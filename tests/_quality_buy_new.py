#!/usr/bin/env python3

"""
A6 — ENTRY QUALITY BUY NEW CALIBRATION TEST

READ-ONLY analysis.
No production BUY NEW logic is modified.

Purpose:
    Trace:
        audit_decisions
            -> recommendation_evidence
            -> recommendation_evaluations (5D)

    and determine whether Entry Quality provides useful information
    about realised BUY NEW performance beyond the existing decision scores.
"""

import sqlite3
import statistics
from pathlib import Path
from collections import Counter


DB_PATH = Path("data/portfolio_manager.db")


def pct(value):
    return f"{value:.2f}%" if value is not None else "N/A"


def median(values):
    return statistics.median(values) if values else None


def numeric_value(value):
    """Convert a database value to float; return None when unavailable."""
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip().upper()

    if text in {"", "N/A", "NA", "NONE", "NULL", "UNKNOWN"}:
        return None

    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def correlation(x_values, y_values):
    """Pearson correlation for paired numeric values."""
    pairs = [
        (x, y)
        for x, y in zip(x_values, y_values)
        if x is not None and y is not None
    ]

    if len(pairs) < 2:
        return None

    xs = [x for x, _ in pairs]
    ys = [y for _, y in pairs]

    mean_x = statistics.mean(xs)
    mean_y = statistics.mean(ys)

    numerator = sum(
        (x - mean_x) * (y - mean_y)
        for x, y in pairs
    )

    denominator_x = sum((x - mean_x) ** 2 for x in xs)
    denominator_y = sum((y - mean_y) ** 2 for y in ys)

    denominator = (denominator_x * denominator_y) ** 0.5

    if denominator == 0:
        return None

    return numerator / denominator


def performance(rows):
    if not rows:
        return None, None, None

    returns = [x["return_5d"] for x in rows]

    return (
        sum(returns) / len(returns),
        median(returns),
        sum(r > 0 for r in returns) / len(returns) * 100,
    )


def print_group(name, rows):
    if not rows:
        print(f"{name:<24} N=0")
        return None

    avg, med, positive = performance(rows)

    print(
        f"{name:<24}"
        f"N={len(rows):>4}  "
        f"Avg={avg:>8.2f}%  "
        f"Median={med:>8.2f}%  "
        f"Positive={positive:>7.2f}%"
    )

    return avg


def main():
    print("=" * 100)
    print("ENTRY QUALITY — BUY NEW CALIBRATION TEST")
    print("=" * 100)
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
        print("-" * 100)

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
        print("-" * 100)

        buy_new_rows = conn.execute(
            """
            SELECT
                recommendation_id,
                id,
                created_at
            FROM audit_decisions
            WHERE recommendation_id IS NOT NULL
              AND (
                    UPPER(TRIM(original_action)) = 'BUY NEW'
                 OR UPPER(TRIM(proposed_action)) = 'BUY NEW'
                 OR UPPER(TRIM(reconciled_action)) = 'BUY NEW'
                 OR UPPER(TRIM(final_action)) = 'BUY NEW'
              )
            ORDER BY recommendation_id, created_at DESC, id DESC
            """
        ).fetchall()

        # Keep the latest BUY NEW audit decision per recommendation.
        audit_by_id = {}

        for row in buy_new_rows:
            rid = row["recommendation_id"]

            if rid not in audit_by_id:
                audit_by_id[rid] = row

        recommendation_ids = list(audit_by_id.keys())

        print(
            f"BUY NEW recommendation IDs: {len(recommendation_ids)}"
        )

        if not recommendation_ids:
            print()
            print("No BUY NEW recommendations found in audit_decisions.")
            return

        # ------------------------------------------------------------------
        # 3. Get decision-level scores from audit_decisions
        # ------------------------------------------------------------------

        placeholders = ",".join("?" * len(recommendation_ids))

        audit_score_rows = conn.execute(
            f"""
            SELECT
                id,
                recommendation_id,
                ticker,
                created_at,
                investment_score,
                confidence_score,
                evidence_score
            FROM audit_decisions
            WHERE recommendation_id IN ({placeholders})
            ORDER BY recommendation_id, created_at DESC, id DESC
            """,
            recommendation_ids,
        ).fetchall()

        latest_audit_by_id = {}

        for row in audit_score_rows:
            rid = row["recommendation_id"]

            if rid not in latest_audit_by_id:
                latest_audit_by_id[rid] = row

        print(
            "BUY NEW recommendations with decision-level scores: "
            f"{len(latest_audit_by_id)}"
        )

        # ------------------------------------------------------------------
        # 4. Get Entry Quality from recommendation_evidence
        # ------------------------------------------------------------------

        evidence_rows = conn.execute(
            f"""
            SELECT
                recommendation_id,
                ticker,
                capture_date,
                entry_quality,
                entry_quality_mode,
                investment_score,
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

        print(
            "BUY NEW recommendations with Entry Quality: "
            f"{len(evidence_by_id)}"
        )

        # ------------------------------------------------------------------
        # 5. Get matured 5D outcomes
        # ------------------------------------------------------------------

        evaluation_rows = conn.execute(
            f"""
            SELECT
                id,
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
            ORDER BY recommendation_id, evaluation_date DESC, id DESC
            """,
            recommendation_ids,
        ).fetchall()

        # Keep the latest recorded 5D evaluation per recommendation.
        outcome_by_id = {}

        for row in evaluation_rows:
            rid = row["recommendation_id"]

            if rid not in outcome_by_id:
                outcome_by_id[rid] = row

        print(
            "BUY NEW recommendations with matured 5D outcome: "
            f"{len(outcome_by_id)}"
        )

        # ------------------------------------------------------------------
        # 6. Join Entry Quality + decision scores + independent 5D outcome
        # ------------------------------------------------------------------

        # ------------------------------------------------------------------
        # 6. Join Entry Quality + matured 5D outcome
        # ------------------------------------------------------------------

        observations = []

        for rid, evidence in evidence_by_id.items():

            outcome = outcome_by_id.get(rid)

            if outcome is None:
                continue

            entry_quality = (
                str(evidence["entry_quality"]).strip().upper()
                if evidence["entry_quality"] is not None
                else None
            )

            if not entry_quality:
                continue

            # Decision-level scores are useful controls, but must not determine
            # whether an otherwise valid BUY NEW observation is included.
            audit = latest_audit_by_id.get(rid)

            observations.append(
                {
                    "recommendation_id": rid,
                    "ticker": evidence["ticker"],
                    "capture_date": evidence["capture_date"],
                    "entry_quality": entry_quality,
                    "entry_quality_mode": evidence["entry_quality_mode"],
                    "investment_score": (
                        numeric_value(audit["investment_score"])
                        if audit is not None
                        else numeric_value(evidence["investment_score"])
                    ),
                    "evidence_score": (
                        numeric_value(audit["evidence_score"])
                        if audit is not None
                        else None
                    ),
                    "confidence_score": (
                        numeric_value(audit["confidence_score"])
                        if audit is not None
                        else numeric_value(evidence["confidence_score"])
                    ),
                    "valuation": evidence["valuation"],
                    "valuation_mode": evidence["valuation_mode"],
                    "return_5d": float(outcome["return_percent"]),
                }
            )

        print(
            f"Independent matured observations: {len(observations)}"
        )
        print()

        if not observations:
            print(
                "No usable independent BUY NEW + Entry Quality + "
                "5D observations."
            )
            return

        # ------------------------------------------------------------------
        # 7. Overall result
        # ------------------------------------------------------------------

        # ------------------------------------------------------------------
        # 7. Entry Quality — categorical BUY NEW performance analysis
        # ------------------------------------------------------------------

        print("ENTRY QUALITY PERFORMANCE")
        print("-" * 100)

        entry_quality_groups = {}

        for row in observations:
            category = row["entry_quality"]

            if not category:
                continue

            entry_quality_groups.setdefault(category, []).append(row)

        print()
        print(
            f"{'Entry Quality':<30}"
            f"{'N':>6}"
            f"{'Avg 5D':>12}"
            f"{'Median 5D':>14}"
            f"{'Positive 5D':>15}"
        )
        print("-" * 100)

        for category, rows in sorted(
            entry_quality_groups.items(),
            key=lambda item: (-len(item[1]), item[0]),
        ):
            returns = [row["return_5d"] for row in rows]

            avg_return = statistics.mean(returns)
            median_return = statistics.median(returns)
            positive_rate = (
                sum(1 for value in returns if value > 0)
                / len(returns)
                * 100
            )

            print(
                f"{category:<30}"
                f"{len(rows):>6}"
                f"{avg_return:>11.2f}%"
                f"{median_return:>13.2f}%"
                f"{positive_rate:>14.1f}%"
            )

        # ------------------------------------------------------------------
        # 8. Entry Quality × Investment Score
        # ------------------------------------------------------------------

        print()
        print("ENTRY QUALITY × INVESTMENT SCORE")
        print("-" * 100)

        score_groups = {
            "70-79": lambda score: score is not None and 70 <= score < 80,
            "80-89": lambda score: score is not None and 80 <= score < 90,
            "90+": lambda score: score is not None and score >= 90,
        }

        for category, rows in sorted(
            entry_quality_groups.items(),
            key=lambda item: (-len(item[1]), item[0]),
        ):
            print()
            print(category)

            for band, condition in score_groups.items():
                group = [
                    row
                    for row in rows
                    if condition(row["investment_score"])
                ]

                if not group:
                    continue

                returns = [row["return_5d"] for row in group]

                print(
                    f"  Investment Score {band}: "
                    f"N={len(group)}, "
                    f"Avg 5D={statistics.mean(returns):.2f}%, "
                    f"Median 5D={statistics.median(returns):.2f}%, "
                    f"Positive={sum(r > 0 for r in returns) / len(returns) * 100:.1f}%"
                )

        # ------------------------------------------------------------------
        # 9. Entry Quality × Evidence / Confidence
        # ------------------------------------------------------------------

        print()
        print("ENTRY QUALITY × EVIDENCE / CONFIDENCE")
        print("-" * 100)

        for category, rows in sorted(
            entry_quality_groups.items(),
            key=lambda item: (-len(item[1]), item[0]),
        ):
            evidence_values = [
                row["evidence_score"]
                for row in rows
                if row["evidence_score"] is not None
            ]

            confidence_values = [
                row["confidence_score"]
                for row in rows
                if row["confidence_score"] is not None
            ]

            print(
                f"{category:<30}"
                f"N={len(rows):>4}  "
                f"Avg Evidence="
                f"{statistics.mean(evidence_values):.1f}"
                if evidence_values
                else
                f"{category:<30}N={len(rows):>4}  Avg Evidence=N/A",
                end="",
            )

            if confidence_values:
                print(
                    f"  Avg Confidence="
                    f"{statistics.mean(confidence_values):.1f}"
                )
            else:
                print("  Avg Confidence=N/A")

        # ------------------------------------------------------------------
        # 10. Overall BUY NEW baseline
        # ------------------------------------------------------------------

        print()
        print("OVERALL BUY NEW BASELINE")
        print("-" * 100)

        all_returns = [
            row["return_5d"]
            for row in observations
        ]

        overall_avg = statistics.mean(all_returns)
        overall_median = statistics.median(all_returns)
        overall_positive = (
            sum(value > 0 for value in all_returns)
            / len(all_returns)
            * 100
        )

        print(f"Observations:       {len(all_returns)}")
        print(f"Average 5D return:  {overall_avg:.2f}%")
        print(f"Median 5D return:   {overall_median:.2f}%")
        print(f"Positive 5D rate:   {overall_positive:.1f}%")

        # ------------------------------------------------------------------
        # 11. Interpretation
        # ------------------------------------------------------------------

        print()
        print("CALIBRATION INTERPRETATION")
        print("-" * 100)

        if len(entry_quality_groups) <= 1:
            print(
                "Entry Quality has only one observed category in the matured "
                "BUY NEW population. It cannot currently discriminate outcomes."
            )
        else:
            category_results = []

            for category, rows in entry_quality_groups.items():
                returns = [row["return_5d"] for row in rows]

                category_results.append(
                    (
                        category,
                        len(rows),
                        statistics.mean(returns),
                        statistics.median(returns),
                        sum(value > 0 for value in returns)
                        / len(returns)
                        * 100,
                    )
                )

            best_avg = max(
                category_results,
                key=lambda item: item[2],
            )

            worst_avg = min(
                category_results,
                key=lambda item: item[2],
            )

            best_positive = max(
                category_results,
                key=lambda item: item[4],
            )

            print(
                f"Best category by average 5D return: "
                f"{best_avg[0]} "
                f"({best_avg[2]:.2f}%, N={best_avg[1]})"
            )

            print(
                f"Worst category by average 5D return: "
                f"{worst_avg[0]} "
                f"({worst_avg[2]:.2f}%, N={worst_avg[1]})"
            )

            print(
                f"Best category by positive 5D rate: "
                f"{best_positive[0]} "
                f"({best_positive[4]:.1f}%, N={best_positive[1]})"
            )

            print()
            print(
                "These results describe association only. "
                "They do not justify a production BUY NEW rule by themselves."
            )
            
    finally:
        conn.close()

if __name__ == "__main__":
    main()