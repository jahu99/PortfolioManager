"""
BUY NEW Technical OOS Robustness Test

READ-ONLY — NO PRODUCTION CHANGES

Purpose:
    Determine whether the apparent BUY NEW improvement from a higher
    Technical Score threshold survives:

        1. A strict chronological date split.
        2. Removal of ASND concentration.

Candidate thresholds:
    75, 80, 85, 90, 95

This test is descriptive only.
It does not modify production thresholds or governance.
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

HORIZON = 5

TECHNICAL_THRESHOLDS = (
    75.0,
    80.0,
    85.0,
    90.0,
    95.0,
)

CALIBRATION_SHARE = 0.70


# ============================================================
# HELPERS
# ============================================================


def normalise_day(value):
    if value is None:
        return None

    timestamp = pd.to_datetime(
        value,
        errors="coerce",
    )

    if pd.isna(timestamp):
        return None

    return timestamp.strftime("%Y-%m-%d")


def load_buy_new_decisions(conn):
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

        if pd.notna(
            decision["recommendation_id"]
        ):
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

    decisions[
        "lineage_recommendation_id"
    ] = lineage

    return decisions


def load_evidence(conn):
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
        params=(HORIZON,),
    )


def attach_evidence(
    decisions,
    evidence,
):
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
):
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


def calculate_metrics(population):
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

    returns = population[
        "return_percent"
    ]

    return {
        "n": len(population),
        "mean": returns.mean(),
        "median": returns.median(),
        "positive_pct": (
            returns.gt(0).mean() * 100
        ),
    }


def threshold_population(
    population,
    threshold,
):
    return population[
        population["technical_score"] >= threshold
    ].copy()


def print_threshold_results(
    population,
    title,
):
    print()
    print(title)
    print("-" * 78)

    print(
        f"{'Threshold':<12}"
        f"{'n':>6}"
        f"{'Mean':>12}"
        f"{'Median':>12}"
        f"{'Positive':>12}"
        f"{'Coverage':>12}"
    )

    baseline = threshold_population(
        population,
        75,
    )

    baseline_n = len(baseline)

    for threshold in TECHNICAL_THRESHOLDS:

        candidate = threshold_population(
            population,
            threshold,
        )

        metrics = calculate_metrics(
            candidate
        )

        if baseline_n:
            coverage = (
                len(candidate)
                / baseline_n
                * 100
            )
        else:
            coverage = np.nan

        print(
            f"{threshold:<12.0f}"
            f"{metrics['n']:>6}"
            f"{metrics['mean']:>11.3f}%"
            f"{metrics['median']:>11.3f}%"
            f"{metrics['positive_pct']:>11.2f}%"
            f"{coverage:>11.1f}%"
        )


def print_delta_vs_baseline(
    population,
    title,
):
    print()
    print(title)
    print("-" * 78)

    baseline = threshold_population(
        population,
        75,
    )

    baseline_metrics = calculate_metrics(
        baseline
    )

    print(
        f"Baseline >=75:"
        f" n={baseline_metrics['n']}"
        f" mean={baseline_metrics['mean']:.3f}%"
        f" median={baseline_metrics['median']:.3f}%"
        f" positive={baseline_metrics['positive_pct']:.2f}%"
    )

    for threshold in (
        85.0,
        90.0,
        95.0,
    ):

        candidate = threshold_population(
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

        print(
            f"Threshold >= {threshold:.0f}:"
            f" n={metrics['n']}"
            f" mean_delta="
            f"{metrics['mean'] - baseline_metrics['mean']:+.3f}pp"
            f" median_delta="
            f"{metrics['median'] - baseline_metrics['median']:+.3f}pp"
            f" positive_delta="
            f"{metrics['positive_pct'] - baseline_metrics['positive_pct']:+.2f}pp"
        )


def print_ticker_breakdown(
    population,
    title,
):
    print()
    print(title)
    print("-" * 78)

    summary = (
        population
        .groupby("evidence_ticker")[
            "return_percent"
        ]
        .agg(
            count="count",
            mean="mean",
            median="median",
            positive_pct=lambda x: (
                x.gt(0).mean() * 100
            ),
        )
        .sort_values(
            "count",
            ascending=False,
        )
    )

    print(
        summary.to_string(
            float_format=lambda value:
            f"{value:.3f}"
        )
    )


def print_date_distribution(
    population,
):
    print()
    print(
        "OOS DATE DISTRIBUTION"
    )
    print("-" * 78)

    dates = (
        population
        .groupby(
            population["capture_date"].dt.strftime(
                "%Y-%m-%d"
            )
        )
        .size()
    )

    print(
        dates.to_string()
    )


def strict_date_split(
    population,
):
    """
    Strict chronological split.

    Unlike the previous test, this does NOT split rows at 70%.
    It selects an actual calendar date boundary.
    """

    dates = sorted(
        population[
            "capture_date"
        ]
        .dt.normalize()
        .dropna()
        .unique()
    )

    if len(dates) < 2:
        return (
            population.copy(),
            population.iloc[0:0].copy(),
            None,
        )

    split_position = int(
        len(dates) * CALIBRATION_SHARE
    )

    split_position = max(
        1,
        min(
            split_position,
            len(dates) - 1,
        ),
    )

    calibration_end = dates[
        split_position - 1
    ]

    oos_start = dates[
        split_position
    ]

    calibration = population[
        population["capture_date"]
        .dt.normalize()
        <= calibration_end
    ].copy()

    oos = population[
        population["capture_date"]
        .dt.normalize()
        >= oos_start
    ].copy()

    return (
        calibration,
        oos,
        oos_start,
    )


def print_asnd_robustness(
    oos,
):
    """
    Compare the OOS threshold results with and without ASND.
    """

    print()
    print(
        "ASND ROBUSTNESS TEST"
    )
    print("-" * 78)

    all_oos = oos.copy()

    ex_asnd = oos[
        oos["evidence_ticker"].str.upper()
        != "ASND"
    ].copy()

    print()
    print(
        "ALL OOS TICKERS"
    )

    print_threshold_results(
        all_oos,
        "Technical thresholds — all OOS tickers",
    )

    print_delta_vs_baseline(
        all_oos,
        "Threshold deltas — all OOS tickers",
    )

    print()
    print(
        "ASND EXCLUDED"
    )

    print_threshold_results(
        ex_asnd,
        "Technical thresholds — ASND excluded",
    )

    print_delta_vs_baseline(
        ex_asnd,
        "Threshold deltas — ASND excluded",
    )

    print_ticker_breakdown(
        ex_asnd,
        "ASND-excluded ticker breakdown",
    )


# ============================================================
# MAIN
# ============================================================


def main():

    print("=" * 78)
    print(
        "BUY NEW TECHNICAL OOS ROBUSTNESS TEST"
    )
    print("=" * 78)
    print()
    print(
        "READ-ONLY — NO PRODUCTION CHANGES"
    )
    print()

    conn = sqlite3.connect(
        DB_PATH
    )

    try:

        # ----------------------------------------------------
        # LOAD
        # ----------------------------------------------------

        decisions = load_buy_new_decisions(
            conn
        )

        recommendations = load_recommendations(
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

        print(
            f"Raw BUY NEW decisions: "
            f"{len(decisions)}"
        )

        print(
            f"Direct lineage: "
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
        # EVIDENCE
        # ----------------------------------------------------

        population = attach_evidence(
            decisions,
            evidence,
        )

        population = attach_outcomes(
            population,
            evaluations,
        )

        population["technical_score"] = pd.to_numeric(
            population[
                "evidence_technical_score"
            ],
            errors="coerce",
        )

        population["capture_date"] = pd.to_datetime(
            population[
                "evidence_capture_date"
            ],
            errors="coerce",
        )

        population = population[
            population[
                "lineage_recommendation_id"
            ].notna()
            & population[
                "technical_score"
            ].notna()
            & population[
                "capture_date"
            ].notna()
            & population[
                "return_percent"
            ].notna()
        ].copy()

        print()
        print(
            "=" * 78
        )
        print(
            "MATURE 5D POPULATION"
        )
        print(
            "=" * 78
        )

        print(
            f"Mature observations: "
            f"{len(population)}"
        )

        if population.empty:
            print(
                "No mature population."
            )
            return

        print_date_distribution(
            population
        )

        # ----------------------------------------------------
        # STRICT DATE SPLIT
        # ----------------------------------------------------

        calibration, oos, oos_start = (
            strict_date_split(
                population
            )
        )

        print()
        print(
            "=" * 78
        )
        print(
            "STRICT DATE SPLIT"
        )
        print(
            "=" * 78
        )

        print(
            f"Calibration: "
            f"{calibration['capture_date'].min().date()}"
            f" -> "
            f"{calibration['capture_date'].max().date()}"
            f" | n={len(calibration)}"
        )

        print(
            f"OOS: "
            f"{oos['capture_date'].min().date()}"
            f" -> "
            f"{oos['capture_date'].max().date()}"
            f" | n={len(oos)}"
        )

        print(
            f"OOS start date: "
            f"{oos_start.date()}"
        )

        # ----------------------------------------------------
        # CALIBRATION
        # ----------------------------------------------------

        print_threshold_results(
            calibration,
            "CALIBRATION — TECHNICAL THRESHOLDS",
        )

        print_delta_vs_baseline(
            calibration,
            "CALIBRATION — DELTA VS 75",
        )

        # ----------------------------------------------------
        # OOS
        # ----------------------------------------------------

        print_threshold_results(
            oos,
            "OOS — TECHNICAL THRESHOLDS",
        )

        print_delta_vs_baseline(
            oos,
            "OOS — DELTA VS 75",
        )

        # ----------------------------------------------------
        # OOS TICKER CONCENTRATION
        # ----------------------------------------------------

        print_ticker_breakdown(
            oos,
            "OOS TICKER CONCENTRATION",
        )

        # ----------------------------------------------------
        # ASND ROBUSTNESS
        # ----------------------------------------------------

        print_asnd_robustness(
            oos
        )

        # ----------------------------------------------------
        # FINAL SUMMARY
        # ----------------------------------------------------

        print()
        print(
            "=" * 78
        )
        print(
            "ROBUSTNESS TEST COMPLETE"
        )
        print(
            "=" * 78
        )
        print()
        print(
            "No production changes were made."
        )
        print(
            "Results are descriptive and read-only."
        )

    finally:
        conn.close()


if __name__ == "__main__":
    main()
