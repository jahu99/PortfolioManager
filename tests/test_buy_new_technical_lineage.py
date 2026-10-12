"""
BUY NEW TECHNICAL COMPONENT LINEAGE INVESTIGATION

READ-ONLY — NO PRODUCTION CHANGES

Purpose:
    Verify whether the technical component fields stored in
    recommendation_evidence are internally consistent with the
    stored Technical Score and the production scoring rules.

This test does NOT modify production code, database records, scores,
thresholds, or recommendations.
"""

from pathlib import Path
import sqlite3
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = REPO_ROOT / "data" / "portfolio_manager.db"


def main():
    print("=" * 72)
    print("BUY NEW TECHNICAL COMPONENT LINEAGE INVESTIGATION")
    print("=" * 72)
    print()
    print("READ-ONLY — NO PRODUCTION CHANGES")
    print(f"Database: {DB_PATH}")
    print()

    if not DB_PATH.exists():
        print("ERROR: Database not found.")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """
        SELECT DISTINCT
            r.id AS recommendation_id,
            r.ticker,
            r.date,
            r.signal,
            r.technical_score,
            e.technical_score AS evidence_technical_score,
            e.rsi,
            e.return_3m,
            e.trend_score,
            e.momentum_score,
            e.volume_score,
            e.risk_score
        FROM audit_decisions a
        JOIN recommendations r
            ON r.id = a.recommendation_id
        JOIN recommendation_evidence e
            ON e.recommendation_id = r.id
        WHERE a.final_action = 'BUY NEW'
        ORDER BY r.id
        """
    ).fetchall()

    print(f"Unique BUY NEW recommendation rows: {len(rows)}")
    print()

    if not rows:
        print("No BUY NEW rows found.")
        conn.close()
        return

    print("=" * 72)
    print("STORED COMPONENTS")
    print("=" * 72)
    print()

    for row in rows:
        print(
            f"{row['recommendation_id']:>6} "
            f"{row['ticker']:<6} "
            f"Tech={row['technical_score']!s:<5} "
            f"EvidenceTech={row['evidence_technical_score']!s:<5} "
            f"RSI={row['rsi']!s:<6} "
            f"3M={row['return_3m']!s:<7} "
            f"Trend={row['trend_score']!s:<5} "
            f"Mom={row['momentum_score']!s:<5} "
            f"Vol={row['volume_score']!s:<5} "
            f"Risk={row['risk_score']!s:<5}"
        )

    print()
    print("=" * 72)
    print("COMPONENT TOTAL CHECK")
    print("=" * 72)
    print()

    mismatches = []

    for row in rows:
        components = [
            row["trend_score"],
            row["momentum_score"],
            row["volume_score"],
            row["risk_score"],
        ]

        if all(value is not None for value in components):
            component_total = sum(float(value) for value in components)

            technical_score = (
                float(row["evidence_technical_score"])
                if row["evidence_technical_score"] is not None
                else None
            )

            if technical_score is not None:
                difference = component_total - technical_score

                print(
                    f"{row['ticker']:<6} "
                    f"components={component_total:>6.1f} "
                    f"technical={technical_score:>6.1f} "
                    f"difference={difference:>7.1f}"
                )

                if abs(difference) > 0.1:
                    mismatches.append(
                        (
                            row["recommendation_id"],
                            row["ticker"],
                            component_total,
                            technical_score,
                            difference,
                        )
                    )

    print()
    print("=" * 72)
    print("LINEAGE ASSESSMENT")
    print("=" * 72)
    print()

    print(f"Rows with component/Technical Score mismatch: {len(mismatches)}")
    print()

    if mismatches:
        print(
            "RESULT: COMPONENT LINEAGE IS NOT INTERNALLY CONSISTENT."
        )
        print()
        print(
            "The stored component scores cannot currently be treated "
            "as the decomposition of the stored Technical Score."
        )
        print()
        print("Examples:")
        for item in mismatches[:10]:
            rec_id, ticker, component_total, technical, difference = item
            print(
                f"  recommendation={rec_id} "
                f"ticker={ticker} "
                f"components={component_total:.1f} "
                f"technical={technical:.1f} "
                f"difference={difference:.1f}"
            )
    else:
        print(
            "RESULT: COMPONENT TOTALS MATCH THE STORED TECHNICAL SCORE."
        )
        print()
        print(
            "The stored technical component fields appear internally "
            "consistent for this BUY NEW sample."
        )

    print()
    print("=" * 72)
    print("END — READ-ONLY / NO PRODUCTION CHANGES")
    print("=" * 72)

    conn.close()


if __name__ == "__main__":
    main()
