"""
BUY NEW Technical Threshold OOS Calibration

READ-ONLY — NO PRODUCTION CHANGES

Purpose:
    Test whether increasing the BUY NEW minimum Technical Score
    improves realised 5D / 10D performance out-of-sample.

Method:
    1. Load historical BUY NEW audit decisions.
    2. Reconstruct legacy recommendation lineage where required.
    3. Attach persisted recommendation evidence.
    4. Attach realised recommendation outcomes.
    5. Split observations chronologically 70/30.
    6. Test candidate Technical Score thresholds.
    7. Compare each threshold with the current baseline.
    8. Report calibration and OOS results.

This script does NOT modify the decision engine, database,
thresholds, learning data, or governance.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd


# ============================================================
# CONFIGURATION
# ============================================================

DB_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "portfolio_manager.db"
)

HORIZONS = (5, 10)

# Candidate thresholds to investigate.
TECHNICAL_THRESHOLDS = (75.0, 80.0, 85.0, 90.0, 95.0)

CALIBRATION_SHARE = 0.70


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


def load_buy_new_decisions(conn):
    """
    Load BUY NEW audit decisions.

    Proposed action is used because the Technical Score gate
    operates before later reconciliation/final-decision layers.
    """

    return pd.read_sql_query(
        """
        SELECT
            id AS audit_decision_id,
            audit_run_id,
            ticker,
            created_at,
            recommendation_id,
            proposed_action,
            reconciled_action,
            final_action
        FROM audit_decisions
        WHERE UPPER(TRIM(proposed_action)) = 'BUY NEW'
        """,
        conn,
    )


def load_recommendations(conn):
    """
    Load recommendation lineage source.

    The recommendations table uses `date`, not capture_date.
    """

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


def reconstruct_lineage(
    decisions,
    recommendations,
):
    """
    Reconstruct recommendation lineage for audit decisions
    where recommendation_id was not persisted directly.

    This is the same proven approach used by the BUY MORE
    decision forensics.
    """

    decisions = decisions.copy()

    recommendations_by_ticker = {
        ticker: group.sort_values(
            [
                "recommendation_day",
                "recommendation_id",
            ]
        )
        for ticker, group
        in recommendations.groupby("ticker")
    }

    lineage = []

    for _, decision in decisions.iterrows():

        # Direct lineage already exists.
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


def load_recommendation_evidence(conn):
    """
    Load persisted recommendation evidence.

    Evidence schema is based on the actual recommendation_evidence
    table rather than assuming an evidence_score column exists.
    """

    return pd.read_sql_query(
        """
        SELECT
            recommendation_id,
            ticker,
            capture_date,

            signal,

            investment_score,
            technical_score,
            quality_score,
            growth_score,
            confidence_score,

            entry_price,
            rsi,
            sma50,
            sma200,

            extension_sma50_pct,
            extension_sma200_pct,

            entry_quality,
            entry_quality_mode

        FROM recommendation_evidence

        WHERE recommendation_id IS NOT NULL
        """,
        conn,
    )


def load_evaluations(
    conn,
    horizon,
):
    """
    Load realised recommendation outcomes for one horizon.
    """

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
        params=(horizon,),
    )


def attach_evidence(
    decisions,
    evidence,
):
    """
    Attach persisted recommendation evidence to audit decisions.
    """

    decisions = decisions.copy()

    evidence = evidence.copy()

    evidence = (
        evidence
        .sort_values(
            [
                "recommendation_id",
                "capture_date",
            ]
        )
        .drop_duplicates(
            subset=["recommendation_id"],
            keep="last",
        )
    )

    evidence = evidence.rename(
        columns={
            column: f"evidence_{column}"
            for column in evidence.columns
            if column != "recommendation_id"
        }
    )

    return decisions.merge(
        evidence,
        left_on="lineage_recommendation_id",
        right_on="recommendation_id",
        how="left",
    )


def attach_outcomes(
    decisions,
    evaluations,
    horizon,
):
    """
    Attach realised outcome to reconstructed recommendation lineage.
    """

    decisions = decisions.copy()

    evaluations = evaluations.copy()

    evaluations = (
        evaluations
        .sort_values(
            [
                "recommendation_id",
                "evaluation_date",
            ]
        )
        .drop_duplicates(
            subset=["recommendation_id"],
            keep="first",
        )
    )

    return decisions.merge(
        evaluations[
            [
                "recommendation_id",
                "return_percent",
                "outcome",
            ]
        ],
        left_on="lineage_recommendation_id",
        right_on="recommendation_id",
        how="left",
        suffixes=("", "_evaluation"),
    )


def prepare_population(
    decisions,
    evidence,
):
    """
    Build the BUY NEW calibration population.
    """

    decisions = reconstruct_lineage(
        decisions,
        recommendations=evidence["recommendations"],
    )

    decisions = attach_evidence(
        decisions,
        evidence=evidence["evidence"],
    )

    decisions["technical_score"] = pd.to_numeric(
        decisions["evidence_technical_score"],
        errors="coerce",
    )

    decisions["capture_date"] = pd.to_datetime(
        decisions["evidence_capture_date"],
        errors="coerce",
    )

    return decisions


def calculate_metrics(
    population,
):
    """
    Calculate basic realised-return metrics.
    """

    population = population[
        population["return_percent"].notna()
    ].copy()

    if population.empty:
        return {
            "n": 0,
            "mean": np.nan,
            "median": np.nan,
            "positive_pct": np.nan,
        }

    returns = population["return_percent"]

    return {
        "n": len(population),
        "mean": returns.mean(),
        "median": returns.median(),
        "positive_pct": (
            returns.gt(0).mean() * 100
        ),
    }


def print_metrics(
    label,
    metrics,
):
    print(
        f"{label:<20}"
        f" n={metrics['n']:>4}"
        f" mean={metrics['mean']:>8.3f}%"
        f" median={metrics['median']:>8.3f}%"
        f" positive={metrics['positive_pct']:>6.2f}%"
    )


def evaluate_threshold(
    population,
    threshold,
):
    """
    Apply a candidate Technical Score threshold.
    """

    return population[
        population["technical_score"] >= threshold
    ].copy()


def chronological_split(
    population,
):
    """
    70/30 chronological split using recommendation capture date.
    """

    population = population[
        population["capture_date"].notna()
    ].copy()

    population = population.sort_values(
        [
            "capture_date",
            "lineage_recommendation_id",
        ]
    )

    if population.empty:
        return population.copy(), population.copy()

    split_index = int(
        len(population) * CALIBRATION_SHARE
    )

    split_index = max(
        1,
        min(
            split_index,
            len(population) - 1,
        ),
    )

    calibration = population.iloc[
        :split_index
    ].copy()

    oos = population.iloc[
        split_index:
    ].copy()

    return calibration, oos


def print_threshold_table(
    population,
    horizon,
    label,
):
    print()
    print(label)
    print("-" * 72)

    print(
        f"{'Threshold':<12}"
        f"{'n':>6}"
        f"{'Mean':>12}"
        f"{'Median':>12}"
        f"{'Positive':>12}"
    )

    for threshold in TECHNICAL_THRESHOLDS:

        candidate = evaluate_threshold(
            population,
            threshold,
        )

        metrics = calculate_metrics(
            candidate
        )

        print(
            f"{threshold:<12.0f}"
            f"{metrics['n']:>6}"
            f"{metrics['mean']:>11.3f}%"
            f"{metrics['median']:>11.3f}%"
            f"{metrics['positive_pct']:>11.2f}%"
        )


def print_oos_delta(
    population,
):
    """
    Compare candidate thresholds against the baseline 75 threshold.
    """

    baseline = evaluate_threshold(
        population,
        75,
    )

    baseline_metrics = calculate_metrics(
        baseline
    )

    print()
    print(
        "OOS DELTA VS CURRENT 75 THRESHOLD"
    )
    print("-" * 72)

    for threshold in TECHNICAL_THRESHOLDS:

        candidate = evaluate_threshold(
            population,
            threshold,
        )

        metrics = calculate_metrics(
            candidate
        )

        if (
            metrics["n"] == 0
            or baseline_metrics["n"] == 0
        ):
            continue

        mean_delta = (
            metrics["mean"]
            - baseline_metrics["mean"]
        )

        median_delta = (
            metrics["median"]
            - baseline_metrics["median"]
        )

        positive_delta = (
            metrics["positive_pct"]
            - baseline_metrics["positive_pct"]
        )

        coverage = (
            metrics["n"]
            / baseline_metrics["n"]
            * 100
        )

        print(
            f"Threshold {threshold:>5.0f}"
            f" | n={metrics['n']:>3}"
            f" | coverage={coverage:>6.1f}%"
            f" | mean Δ={mean_delta:>7.3f}pp"
            f" | median Δ={median_delta:>7.3f}pp"
            f" | positive Δ={positive_delta:>7.2f}pp"
        )


def print_ticker_concentration(
    population,
):
    """
    Show whether the OOS result is dominated by individual tickers.
    """

    print()
    print(
        "OOS TICKER CONCENTRATION"
    )
    print("-" * 72)

    ticker_summary = (
        population
        .groupby("evidence_ticker")[
            "return_percent"
        ]
        .agg(
            count="count",
            mean="mean",
            median="median",
        )
        .sort_values(
            "count",
            ascending=False,
        )
    )

    print(
        ticker_summary.head(15).to_string()
    )


# ============================================================
# MAIN
# ============================================================


def main():

    print("=" * 72)
    print("BUY NEW TECHNICAL THRESHOLD OOS CALIBRATION")
    print("=" * 72)
    print()
    print("READ-ONLY — NO PRODUCTION CHANGES")
    print()

    conn = sqlite3.connect(
        DB_PATH
    )

    try:

        # ----------------------------------------------------
        # LOAD SOURCE DATA
        # ----------------------------------------------------

        decisions = load_buy_new_decisions(
            conn
        )

        recommendations = load_recommendations(
            conn
        )

        evidence = load_recommendation_evidence(
            conn
        )

        print(
            f"Raw BUY NEW audit decisions: "
            f"{len(decisions)}"
        )

        # ----------------------------------------------------
        # RECONSTRUCT LINEAGE
        # ----------------------------------------------------

        decisions = reconstruct_lineage(
            decisions,
            recommendations,
        )

        direct = decisions[
            decisions["recommendation_id"].notna()
        ]

        reconstructed = decisions[
            decisions["recommendation_id"].isna()
            & decisions[
                "lineage_recommendation_id"
            ].notna()
        ]

        unresolved = decisions[
            decisions[
                "lineage_recommendation_id"
            ].isna()
        ]

        print(
            f"Direct lineage: "
            f"{len(direct)}"
        )

        print(
            f"Reconstructed legacy lineage: "
            f"{len(reconstructed)}"
        )

        print(
            f"Unresolved lineage: "
            f"{len(unresolved)}"
        )

        # ----------------------------------------------------
        # ATTACH EVIDENCE
        # ----------------------------------------------------

        decisions = attach_evidence(
            decisions,
            evidence,
        )

        decisions["technical_score"] = pd.to_numeric(
            decisions["evidence_technical_score"],
            errors="coerce",
        )

        decisions["capture_date"] = pd.to_datetime(
            decisions["evidence_capture_date"],
            errors="coerce",
        )

        # ----------------------------------------------------
        # VALID POPULATION
        # ----------------------------------------------------

        population = decisions[
            decisions["lineage_recommendation_id"].notna()
            & decisions["technical_score"].notna()
            & decisions["capture_date"].notna()
        ].copy()

        print()
        print("=" * 72)
        print("POPULATION")
        print("=" * 72)

        print(
            f"BUY NEW observations with evidence: "
            f"{len(population)}"
        )

        # ----------------------------------------------------
        # HORIZONS
        # ----------------------------------------------------

        for horizon in HORIZONS:

            print()
            print("=" * 72)
            print(
                f"{horizon}D HORIZON"
            )
            print("=" * 72)

            evaluations = load_evaluations(
                conn,
                horizon,
            )

            horizon_population = attach_outcomes(
                population,
                evaluations,
                horizon,
            )

            horizon_population = (
                horizon_population[
                    horizon_population[
                        "return_percent"
                    ].notna()
                ]
                .copy()
            )

            print(
                f"Mature observations: "
                f"{len(horizon_population)}"
            )

            if horizon_population.empty:
                print(
                    "No mature observations."
                )
                continue

            # ------------------------------------------------
            # CHRONOLOGICAL SPLIT
            # ------------------------------------------------

            calibration, oos = chronological_split(
                horizon_population
            )

            print()
            print(
                "CHRONOLOGICAL SPLIT"
            )
            print("-" * 72)

            print(
                f"Calibration: "
                f"{calibration['capture_date'].min().date()}"
                f" -> "
                f"{calibration['capture_date'].max().date()}"
                f" | n={len(calibration)}"
            )

            print(
                f"OOS validation: "
                f"{oos['capture_date'].min().date()}"
                f" -> "
                f"{oos['capture_date'].max().date()}"
                f" | n={len(oos)}"
            )

            # ------------------------------------------------
            # CURRENT BASELINE
            # ------------------------------------------------

            print()
            print(
                "CURRENT BASELINE"
            )
            print("-" * 72)

            baseline = evaluate_threshold(
                horizon_population,
                75,
            )

            print_metrics(
                "All BUY NEW >=75",
                calculate_metrics(
                    baseline
                ),
            )

            print()
            print(
                "CALIBRATION"
            )
            print("-" * 72)

            print_threshold_table(
                calibration,
                horizon,
                "Calibration threshold results",
            )

            print()
            print(
                "OOS VALIDATION"
            )
            print("-" * 72)

            print_threshold_table(
                oos,
                horizon,
                "OOS threshold results",
            )

            # ------------------------------------------------
            # OOS DELTA
            # ------------------------------------------------

            print_oos_delta(
                oos
            )

            # ------------------------------------------------
            # TICKER CONCENTRATION
            # ------------------------------------------------

            print_ticker_concentration(
                oos
            )

            # ------------------------------------------------
            # HIGH-TECHNICAL CANDIDATE
            # ------------------------------------------------

            print()
            print(
                "OOS CANDIDATE SUMMARY"
            )
            print("-" * 72)

            for threshold in (
                85.0,
                90.0,
                95.0,
            ):

                candidate = evaluate_threshold(
                    oos,
                    threshold,
                )

                metrics = calculate_metrics(
                    candidate
                )

                print_metrics(
                    f"Technical >= {threshold:.0f}",
                    metrics,
                )

        print()
        print("=" * 72)
        print("CALIBRATION TEST COMPLETE")
        print("=" * 72)
        print()
        print(
            "No production changes were made."
        )
        print(
            "Results are descriptive and read-only."
        )
        print(
            "A threshold should only be considered for"
            " production after OOS evidence is sufficiently"
            " mature and robust to ticker concentration."
        )

    finally:
        conn.close()


if __name__ == "__main__":
    main()
