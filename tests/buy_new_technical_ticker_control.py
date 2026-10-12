"""
BUY NEW Technical Score — Ticker-Controlled Investigation

Purpose
-------
Read-only A6 investigation.

Tests whether the apparent improvement from increasing the BUY NEW
Technical Score threshold from >=75 to >=85 is visible across multiple
tickers, rather than being driven by ticker concentration.

This script:
    1. Loads BUY NEW audit decisions.
    2. Reconstructs legacy recommendation lineage where required.
    3. Joins recommendation evidence.
    4. Joins mature 5D outcomes.
    5. Uses the same strict chronological OOS population as the previous
       robustness investigation.
    6. Compares Technical Score >=75 versus >=85 within each ticker.
    7. Reports per-ticker:
           - sample size
           - baseline >=75 mean
           - >=85 mean
           - delta
           - positive-rate change
           - coverage
    8. Summarises how many tickers show improvement.
    9. Makes NO production changes.

This is descriptive evidence only.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DB_PATH = PROJECT_ROOT / "data" / "portfolio_manager.db"

ACTION = "BUY NEW"

BASELINE_THRESHOLD = 75
TEST_THRESHOLD = 85

HORIZON_DAYS = 5


# ============================================================
# HELPERS
# ============================================================


def normalise_day(value):
    if value is None:
        return None

    try:
        timestamp = pd.to_datetime(value, errors="coerce")

        if pd.isna(timestamp):
            return None

        return timestamp.strftime("%Y-%m-%d")

    except Exception:
        return None


def load_recommendations(conn):
    recommendations = pd.read_sql_query(
        """
        SELECT
            id AS recommendation_id,
            ticker,
            date AS recommendation_day
        FROM recommendations
        WHERE ticker IS NOT NULL
        """,
        conn,
    )

    recommendations["recommendation_day"] = (
        pd.to_datetime(
            recommendations["recommendation_day"],
            errors="coerce",
        ).dt.strftime("%Y-%m-%d")
    )

    return recommendations


def load_audit_decisions(conn):
    decisions = pd.read_sql_query(
        """
        SELECT
            id AS audit_decision_id,
            audit_run_id,
            recommendation_id,
            ticker,
            created_at,
            original_action,
            proposed_action,
            reconciled_action,
            final_action
        FROM audit_decisions
        WHERE final_action = ?
        """,
        conn,
        params=(ACTION,),
    )

    return decisions


def reconstruct_lineage(decisions, recommendations):
    decisions = decisions.copy()

    recommendations_by_ticker = {
        ticker: group.sort_values(
            ["recommendation_day", "recommendation_id"]
        )
        for ticker, group in recommendations.groupby("ticker")
    }

    lineage = []

    for _, decision in decisions.iterrows():

        if pd.notna(decision["recommendation_id"]):
            lineage.append(
                decision["recommendation_id"]
            )
            continue

        ticker = decision["ticker"]

        candidates = recommendations_by_ticker.get(
            ticker
        )

        if candidates is None:
            lineage.append(np.nan)
            continue

        audit_day = normalise_day(
            decision["created_at"]
        )

        if audit_day is None:
            lineage.append(np.nan)
            continue

        candidates = candidates[
            candidates["recommendation_day"] <= audit_day
        ]

        if candidates.empty:
            lineage.append(np.nan)
            continue

        lineage.append(
            candidates.iloc[-1]["recommendation_id"]
        )

    decisions["lineage_recommendation_id"] = lineage

    return decisions


def load_evidence(conn):
    return pd.read_sql_query(
        """
        SELECT
            recommendation_id,
            ticker AS evidence_ticker,
            capture_date,
            technical_score,
            entry_quality,
            extension_sma50_pct,
            extension_sma200_pct
        FROM recommendation_evidence
        WHERE technical_score IS NOT NULL
        """,
        conn,
    )


def load_evaluations(conn):
    return pd.read_sql_query(
        """
        SELECT
            recommendation_id,
            evaluation_date,
            days_after,
            return_percent,
            outcome
        FROM recommendation_evaluations
        WHERE days_after = ?
          AND return_percent IS NOT NULL
        """,
        conn,
        params=(HORIZON_DAYS,),
    )


def calculate_stats(df):
    if df.empty:
        return {
            "n": 0,
            "mean": np.nan,
            "median": np.nan,
            "positive_pct": np.nan,
        }

    return {
        "n": len(df),
        "mean": df["return_percent"].mean(),
        "median": df["return_percent"].median(),
        "positive_pct": (
            df["return_percent"] > 0
        ).mean()
        * 100,
    }


# ============================================================
# MAIN
# ============================================================


def main():

    print()
    print("=" * 78)
    print()
    print("BUY NEW TECHNICAL SCORE — TICKER-CONTROLLED INVESTIGATION")
    print()
    print("=" * 78)
    print()
    print("READ-ONLY — NO PRODUCTION CHANGES")
    print()

    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database not found: {DB_PATH}"
        )

    conn = sqlite3.connect(DB_PATH)

    try:

        # ----------------------------------------------------
        # LOAD SOURCE DATA
        # ----------------------------------------------------

        recommendations = load_recommendations(
            conn
        )

        decisions = load_audit_decisions(
            conn
        )

        evidence = load_evidence(
            conn
        )

        evaluations = load_evaluations(
            conn
        )

        # ----------------------------------------------------
        # LINEAGE
        # ----------------------------------------------------

        decisions = reconstruct_lineage(
            decisions,
            recommendations,
        )

        print("=" * 78)
        print()
        print("BUY NEW LINEAGE")
        print()
        print("-" * 78)

        print(
            f"Raw BUY NEW decisions: "
            f"{len(decisions)}"
        )

        print(
            "Direct lineage: "
            f"{decisions['recommendation_id'].notna().sum()}"
        )

        print(
            "Reconstructed legacy lineage: "
            f"{(
                decisions["recommendation_id"].isna()
                & decisions[
                    "lineage_recommendation_id"
                ].notna()
            ).sum()}"
        )

        print(
            "Unresolved lineage: "
            f"{decisions['lineage_recommendation_id'].isna().sum()}"
        )

        # ----------------------------------------------------
        # NORMALISE EVIDENCE
        # ----------------------------------------------------

        evidence["capture_date"] = (
            pd.to_datetime(
                evidence["capture_date"],
                errors="coerce",
            ).dt.strftime("%Y-%m-%d")
        )

        # ----------------------------------------------------
        # JOIN EVIDENCE
        # ----------------------------------------------------

        merged = decisions.merge(
            evidence,
            left_on="lineage_recommendation_id",
            right_on="recommendation_id",
            how="inner",
            suffixes=("", "_evidence"),
        )

        # ----------------------------------------------------
        # JOIN 5D OUTCOMES
        # ----------------------------------------------------

        merged = merged.merge(
            evaluations,
            left_on="lineage_recommendation_id",
            right_on="recommendation_id",
            how="inner",
            suffixes=("", "_evaluation"),
        )

        merged["capture_date"] = (
            pd.to_datetime(
                merged["capture_date"],
                errors="coerce",
            )
        )

        merged["return_percent"] = pd.to_numeric(
            merged["return_percent"],
            errors="coerce",
        )

        merged["technical_score"] = pd.to_numeric(
            merged["technical_score"],
            errors="coerce",
        )

        merged = merged[
            merged["return_percent"].notna()
            & merged["technical_score"].notna()
            & merged["capture_date"].notna()
        ].copy()

        # ----------------------------------------------------
        # MATURE POPULATION
        # ----------------------------------------------------

        print()
        print("=" * 78)
        print()
        print("MATURE 5D POPULATION")
        print()
        print("-" * 78)

        print(
            f"Mature observations: {len(merged)}"
        )

        if merged.empty:
            print()
            print(
                "No mature observations available."
            )
            return

        # ----------------------------------------------------
        # STRICT DATE SPLIT
        #
        # Same split as previous robustness test:
        #
        # Calibration:
        #   2026-08-27 -> 2026-09-04
        #
        # OOS:
        #   2026-09-08 -> 2026-09-11
        #
        # We deliberately retain the same OOS population so
        # this investigation is directly comparable with the
        # previous robustness result.
        # ----------------------------------------------------

        oos_start = pd.Timestamp(
            "2026-09-08"
        )

        oos = merged[
            merged["capture_date"] >= oos_start
        ].copy()

        calibration = merged[
            merged["capture_date"] < oos_start
        ].copy()

        print()
        print("=" * 78)
        print()
        print("STRICT DATE SPLIT")
        print()
        print("=" * 78)

        print(
            "Calibration: "
            f"{calibration['capture_date'].min().date()}"
            " -> "
            f"{calibration['capture_date'].max().date()}"
            f" | n={len(calibration)}"
        )

        print(
            "OOS: "
            f"{oos['capture_date'].min().date()}"
            " -> "
            f"{oos['capture_date'].max().date()}"
            f" | n={len(oos)}"
        )

        print(
            f"OOS start date: "
            f"{oos_start.date()}"
        )

        # ----------------------------------------------------
        # OVERALL OOS BASELINE
        # ----------------------------------------------------

        baseline = oos[
            oos["technical_score"]
            >= BASELINE_THRESHOLD
        ]

        threshold = oos[
            oos["technical_score"]
            >= TEST_THRESHOLD
        ]

        baseline_stats = calculate_stats(
            baseline
        )

        threshold_stats = calculate_stats(
            threshold
        )

        print()
        print("=" * 78)
        print()
        print("OVERALL OOS RESULT")
        print()
        print("-" * 78)

        print(
            f"Baseline >= {BASELINE_THRESHOLD}: "
            f"n={baseline_stats['n']} "
            f"mean={baseline_stats['mean']:.3f}% "
            f"median={baseline_stats['median']:.3f}% "
            f"positive={baseline_stats['positive_pct']:.2f}%"
        )

        print(
            f"Threshold >= {TEST_THRESHOLD}: "
            f"n={threshold_stats['n']} "
            f"mean={threshold_stats['mean']:.3f}% "
            f"median={threshold_stats['median']:.3f}% "
            f"positive={threshold_stats['positive_pct']:.2f}%"
        )

        if (
            baseline_stats["n"] > 0
            and threshold_stats["n"] > 0
        ):
            print(
                f"Mean delta: "
                f"{(
                    threshold_stats["mean"]
                    - baseline_stats["mean"]
                ):+.3f}pp"
            )

        # ----------------------------------------------------
        # PER-TICKER ANALYSIS
        # ----------------------------------------------------

        print()
        print("=" * 78)
        print()
        print("PER-TICKER OOS COMPARISON")
        print()
        print("-" * 78)

        rows = []

        for ticker, ticker_df in (
            oos.groupby("evidence_ticker")
        ):

            baseline_ticker = ticker_df[
                ticker_df["technical_score"]
                >= BASELINE_THRESHOLD
            ]

            threshold_ticker = ticker_df[
                ticker_df["technical_score"]
                >= TEST_THRESHOLD
            ]

            baseline_stats_ticker = (
                calculate_stats(
                    baseline_ticker
                )
            )

            threshold_stats_ticker = (
                calculate_stats(
                    threshold_ticker
                )
            )

            baseline_n = (
                baseline_stats_ticker["n"]
            )

            threshold_n = (
                threshold_stats_ticker["n"]
            )

            if (
                baseline_n > 0
                and threshold_n > 0
            ):
                mean_delta = (
                    threshold_stats_ticker["mean"]
                    - baseline_stats_ticker["mean"]
                )

                median_delta = (
                    threshold_stats_ticker["median"]
                    - baseline_stats_ticker["median"]
                )

                positive_delta = (
                    threshold_stats_ticker[
                        "positive_pct"
                    ]
                    - baseline_stats_ticker[
                        "positive_pct"
                    ]
                )

                coverage = (
                    threshold_n
                    / baseline_n
                    * 100
                )

            else:
                mean_delta = np.nan
                median_delta = np.nan
                positive_delta = np.nan

                coverage = (
                    threshold_n
                    / baseline_n
                    * 100
                    if baseline_n > 0
                    else np.nan
                )

            rows.append(
                {
                    "ticker": ticker,
                    "baseline_n": baseline_n,
                    "baseline_mean": (
                        baseline_stats_ticker["mean"]
                    ),
                    "baseline_median": (
                        baseline_stats_ticker["median"]
                    ),
                    "baseline_positive_pct": (
                        baseline_stats_ticker[
                            "positive_pct"
                        ]
                    ),
                    "threshold_n": threshold_n,
                    "threshold_mean": (
                        threshold_stats_ticker["mean"]
                    ),
                    "threshold_median": (
                        threshold_stats_ticker["median"]
                    ),
                    "threshold_positive_pct": (
                        threshold_stats_ticker[
                            "positive_pct"
                        ]
                    ),
                    "mean_delta": mean_delta,
                    "median_delta": median_delta,
                    "positive_delta": positive_delta,
                    "coverage": coverage,
                }
            )

        ticker_results = pd.DataFrame(
            rows
        )

        ticker_results = ticker_results.sort_values(
            "baseline_n",
            ascending=False,
        )

        display_columns = [
            "ticker",
            "baseline_n",
            "baseline_mean",
            "threshold_n",
            "threshold_mean",
            "mean_delta",
            "positive_delta",
            "coverage",
        ]

        print(
            ticker_results[
                display_columns
            ].to_string(
                index=False,
                formatters={
                    "baseline_mean": (
                        lambda x:
                        f"{x:.3f}%"
                        if pd.notna(x)
                        else "nan"
                    ),
                    "threshold_mean": (
                        lambda x:
                        f"{x:.3f}%"
                        if pd.notna(x)
                        else "nan"
                    ),
                    "mean_delta": (
                        lambda x:
                        f"{x:+.3f}pp"
                        if pd.notna(x)
                        else "nan"
                    ),
                    "positive_delta": (
                        lambda x:
                        f"{x:+.2f}pp"
                        if pd.notna(x)
                        else "nan"
                    ),
                    "coverage": (
                        lambda x:
                        f"{x:.1f}%"
                        if pd.notna(x)
                        else "nan"
                    ),
                },
            )
        )

        # ----------------------------------------------------
        # TICKER-LEVEL ROBUSTNESS SUMMARY
        # ----------------------------------------------------

        valid = ticker_results[
            ticker_results["threshold_n"] > 0
        ].copy()

        improved_mean = valid[
            valid["mean_delta"] > 0
        ]

        improved_median = valid[
            valid["median_delta"] > 0
        ]

        improved_positive = valid[
            valid["positive_delta"] > 0
        ]

        worsened_mean = valid[
            valid["mean_delta"] < 0
        ]

        unchanged_mean = valid[
            valid["mean_delta"] == 0
        ]

        print()
        print("=" * 78)
        print()
        print("TICKER-LEVEL ROBUSTNESS SUMMARY")
        print()
        print("-" * 78)

        print(
            f"Tickers with usable >=85 data: "
            f"{len(valid)}"
        )

        print(
            f"Tickers with improved mean: "
            f"{len(improved_mean)}"
        )

        print(
            f"Tickers with improved median: "
            f"{len(improved_median)}"
        )

        print(
            f"Tickers with improved positive rate: "
            f"{len(improved_positive)}"
        )

        print(
            f"Tickers with worsened mean: "
            f"{len(worsened_mean)}"
        )

        print(
            f"Tickers with unchanged mean: "
            f"{len(unchanged_mean)}"
        )

        if len(valid) > 0:

            print(
                f"Mean ticker-level delta: "
                f"{valid['mean_delta'].mean():+.3f}pp"
            )

            print(
                f"Median ticker-level delta: "
                f"{valid['mean_delta'].median():+.3f}pp"
            )

        # ----------------------------------------------------
        # WEIGHTED VS UNWEIGHTED EFFECT
        # ----------------------------------------------------

        print()
        print("=" * 78)
        print()
        print("WEIGHTED VS TICKER-BALANCED EFFECT")
        print()
        print("-" * 78)

        if not valid.empty:

            weighted_delta = (
                threshold_stats["mean"]
                - baseline_stats["mean"]
            )

            unweighted_delta = (
                valid["mean_delta"].mean()
            )

            print(
                "Observation-weighted OOS mean delta: "
                f"{weighted_delta:+.3f}pp"
            )

            print(
                "Ticker-weighted mean delta: "
                f"{unweighted_delta:+.3f}pp"
            )

            print(
                "Difference between weighted and "
                "ticker-balanced effect: "
                f"{(
                    weighted_delta
                    - unweighted_delta
                ):+.3f}pp"
            )

        # ----------------------------------------------------
        # LARGE-TICKER ROBUSTNESS
        # ----------------------------------------------------

        print()
        print("=" * 78)
        print()
        print("LARGE-TICKER ROBUSTNESS")
        print()
        print("-" * 78)

        for minimum_n in [5, 10, 15, 20]:

            subset = valid[
                valid["baseline_n"]
                >= minimum_n
            ]

            if subset.empty:
                continue

            improved = subset[
                subset["mean_delta"] > 0
            ]

            print(
                f"Tickers with baseline n >= {minimum_n}: "
                f"{len(subset)} | "
                f"improved mean: "
                f"{len(improved)}/{len(subset)} | "
                f"mean ticker delta: "
                f"{subset['mean_delta'].mean():+.3f}pp"
            )

        # ----------------------------------------------------
        # ASND EXCLUSION
        # ----------------------------------------------------

        print()
        print("=" * 78)
        print()
        print("ASND-EXCLUDED TICKER-CONTROLLED RESULT")
        print()
        print("-" * 78)

        no_asnd = oos[
            oos["evidence_ticker"] != "ASND"
        ].copy()

        rows_no_asnd = []

        for ticker, ticker_df in (
            no_asnd.groupby("evidence_ticker")
        ):

            baseline_ticker = ticker_df[
                ticker_df["technical_score"]
                >= BASELINE_THRESHOLD
            ]

            threshold_ticker = ticker_df[
                ticker_df["technical_score"]
                >= TEST_THRESHOLD
            ]

            baseline_stats_ticker = (
                calculate_stats(
                    baseline_ticker
                )
            )

            threshold_stats_ticker = (
                calculate_stats(
                    threshold_ticker
                )
            )

            if (
                baseline_stats_ticker["n"] > 0
                and threshold_stats_ticker["n"] > 0
            ):

                rows_no_asnd.append(
                    {
                        "ticker": ticker,
                        "baseline_n": (
                            baseline_stats_ticker["n"]
                        ),
                        "threshold_n": (
                            threshold_stats_ticker["n"]
                        ),
                        "mean_delta": (
                            threshold_stats_ticker["mean"]
                            - baseline_stats_ticker["mean"]
                        ),
                        "positive_delta": (
                            threshold_stats_ticker[
                                "positive_pct"
                            ]
                            - baseline_stats_ticker[
                                "positive_pct"
                            ]
                        ),
                    }
                )

        no_asnd_results = pd.DataFrame(
            rows_no_asnd
        )

        if no_asnd_results.empty:

            print(
                "No sufficient ASND-excluded "
                "ticker data."
            )

        else:

            print(
                no_asnd_results.to_string(
                    index=False,
                    formatters={
                        "mean_delta": (
                            lambda x:
                            f"{x:+.3f}pp"
                        ),
                        "positive_delta": (
                            lambda x:
                            f"{x:+.2f}pp"
                        ),
                    },
                )
            )

            print()

            print(
                "ASND-excluded ticker mean delta: "
                f"{no_asnd_results['mean_delta'].mean():+.3f}pp"
            )

            print(
                "ASND-excluded tickers improved: "
                f"{(
                    no_asnd_results['mean_delta'] > 0
                ).sum()}"
                f"/{len(no_asnd_results)}"
            )

        # ----------------------------------------------------
        # FINAL INTERPRETATION SUPPORT
        # ----------------------------------------------------

        print()
        print("=" * 78)
        print()
        print("INVESTIGATION SUMMARY")
        print()
        print("=" * 78)

        print()

        print(
            "This investigation is read-only."
        )

        print(
            "It does not change BUY NEW thresholds "
            "or production decision logic."
        )

        print()

        print(
            "The key question is whether the >=85 "
            "Technical Score effect is visible "
            "across multiple independent tickers."
        )

        print()

        if not valid.empty:

            proportion_improved = (
                len(improved_mean)
                / len(valid)
                * 100
            )

            print(
                f"Mean improvement appears in "
                f"{len(improved_mean)}/{len(valid)} "
                f"tickers "
                f"({proportion_improved:.1f}%)."
            )

        if not no_asnd_results.empty:

            print(
                "The ASND-excluded result should be "
                "treated as the key robustness check."
            )

        print()

        print(
            "No production changes were made."
        )

        print()

    finally:
        conn.close()


if __name__ == "__main__":
    main()
