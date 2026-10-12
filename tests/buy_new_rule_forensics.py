"""
BUY NEW Rule Forensics
======================

READ-ONLY forensic analysis of historical BUY NEW decisions.

Purpose
-------
Investigate which characteristics distinguish successful and unsuccessful
BUY NEW decisions using realised 5D outcomes.

This script:
- reads the portfolio manager SQLite database;
- reconstructs legacy recommendation lineage where recommendation_id
  is missing from audit_decisions;
- attaches realised 5D recommendation outcomes;
- attaches persisted recommendation evidence;
- analyses BUY NEW performance across the persisted decision inputs;
- compares winners vs losers;
- does NOT modify production code, the database, recommendations,
  thresholds, governance, or learning.

Evidence Score is deliberately excluded because it is not persisted as a
column in recommendation_evidence.
"""

from __future__ import annotations

import sqlite3

import numpy as np
import pandas as pd


DB_PATH = "data/portfolio_manager.db"
HORIZON = 5


# ============================================================
# DATE / LINEAGE HELPERS
# ============================================================

def normalise_day(value):
    """Convert a date/datetime-like value into YYYY-MM-DD."""
    if value is None:
        return None

    try:
        timestamp = pd.to_datetime(
            value,
            errors="coerce",
        )

        if pd.isna(timestamp):
            return None

        return timestamp.strftime("%Y-%m-%d")

    except Exception:
        return None


def load_audit_decisions(conn):
    """Load all audit decisions involving BUY NEW."""
    return pd.read_sql_query(
        """
        SELECT
            id AS audit_decision_id,
            audit_run_id,
            ticker,
            original_action,
            proposed_action,
            reconciled_action,
            final_action,
            recommendation_id,
            created_at
        FROM audit_decisions
        WHERE proposed_action = 'BUY NEW'
           OR reconciled_action = 'BUY NEW'
           OR final_action = 'BUY NEW'
        """,
        conn,
    )


def load_recommendations(conn):
    """Load recommendation lineage fields."""
    recommendations = pd.read_sql_query(
        """
        SELECT
            id AS recommendation_id,
            ticker,
            date AS recommendation_day,
            signal,
            investment_score,
            technical_score,
            quality_score,
            growth_score,
            confidence_score
        FROM recommendations
        WHERE ticker IS NOT NULL
        """,
        conn,
    )

    recommendations["recommendation_day"] = (
        pd.to_datetime(
            recommendations["recommendation_day"],
            errors="coerce",
        )
        .dt.strftime("%Y-%m-%d")
    )

    recommendations["ticker"] = (
        recommendations["ticker"]
        .fillna("")
        .astype(str)
        .str.upper()
    )

    return recommendations


def reconstruct_lineage(decisions, recommendations):
    """
    Reconstruct recommendation lineage for audit decisions that do not
    contain a recommendation_id.
    """
    decisions = decisions.copy()

    recommendations_by_ticker = {
        ticker: group.sort_values(
            ["recommendation_day", "recommendation_id"]
        )
        for ticker, group
        in recommendations.groupby("ticker")
    }

    lineage = []

    for _, decision in decisions.iterrows():

        if pd.notna(decision["recommendation_id"]):
            lineage.append(
                decision["recommendation_id"]
            )
            continue

        ticker = str(
            decision["ticker"]
        ).upper()

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


# ============================================================
# OUTCOME / EVIDENCE LOADING
# ============================================================

def load_5d_evaluations(conn):
    """Load realised 5D recommendation outcomes."""
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


def attach_outcomes(decisions, evaluations):
    """Attach the first realised 5D outcome to each lineage."""
    decisions = decisions.copy()

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

    evaluations = evaluations.rename(
        columns={
            "recommendation_id":
                "lineage_recommendation_id",
            "return_percent":
                "return_5d",
            "outcome":
                "outcome_5d",
        }
    )

    return decisions.merge(
        evaluations[
            [
                "lineage_recommendation_id",
                "return_5d",
                "outcome_5d",
            ]
        ],
        on="lineage_recommendation_id",
        how="left",
    )


def load_recommendation_evidence(conn):
    """
    Load persisted recommendation evidence.

    NOTE:
    recommendation_evidence does NOT contain a standalone evidence_score
    column. Therefore evidence_score is deliberately not queried or
    reconstructed here.
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

            return_5d_pct,
            return_10d_pct,
            return_20d_pct,

            entry_quality,
            entry_quality_mode,

            trend_score,
            momentum_score,
            volume_score,
            risk_score,

            revenue_growth,
            profit_margin,
            return_on_equity,
            debt_to_equity,

            sector,
            industry

        FROM recommendation_evidence
        """,
        conn,
    )


def attach_evidence(decisions, evidence):
    """Attach persisted recommendation evidence to reconstructed lineage."""
    decisions = decisions.copy()
    evidence = evidence.copy()

    evidence = evidence.sort_values(
        [
            "recommendation_id",
            "capture_date",
        ]
    )

    evidence = evidence.drop_duplicates(
        subset=["recommendation_id"],
        keep="first",
    )

    evidence = evidence.rename(
        columns={
            "recommendation_id":
                "lineage_recommendation_id"
        }
    )

    evidence_columns = [
        "lineage_recommendation_id",
        "ticker",
        "capture_date",

        "signal",

        "investment_score",
        "technical_score",
        "quality_score",
        "growth_score",
        "confidence_score",

        "entry_price",

        "rsi",
        "sma50",
        "sma200",

        "extension_sma50_pct",
        "extension_sma200_pct",

        "return_5d_pct",
        "return_10d_pct",
        "return_20d_pct",

        "entry_quality",
        "entry_quality_mode",

        "trend_score",
        "momentum_score",
        "volume_score",
        "risk_score",

        "revenue_growth",
        "profit_margin",
        "return_on_equity",
        "debt_to_equity",

        "sector",
        "industry",
    ]

    available_columns = [
        column
        for column in evidence_columns
        if column in evidence.columns
    ]

    return decisions.merge(
        evidence[available_columns],
        on="lineage_recommendation_id",
        how="left",
        suffixes=("", "_evidence"),
    )


# ============================================================
# POPULATION CLEANING
# ============================================================

def clean_population(decisions):
    """Keep the genuine BUY NEW population and normalise fields."""
    frame = decisions.copy()

    frame["ticker"] = (
        frame["ticker"]
        .fillna("")
        .astype(str)
        .str.upper()
    )

    if "ticker_evidence" in frame.columns:
        frame["ticker"] = (
            frame["ticker"]
            .replace("", np.nan)
            .combine_first(
                frame["ticker_evidence"]
            )
            .fillna("")
            .astype(str)
            .str.upper()
        )

    frame = frame[
        frame["final_action"] == "BUY NEW"
    ].copy()

    frame = frame[
        frame["lineage_recommendation_id"].notna()
    ].copy()

    numeric_columns = [
        "return_5d",

        "investment_score",
        "technical_score",
        "quality_score",
        "growth_score",
        "confidence_score",

        "extension_sma50_pct",
        "extension_sma200_pct",

        "rsi",
        "sma50",
        "sma200",
        "entry_price",

        "candidate_rank",
        "priority_rank",

        "trend_score",
        "momentum_score",
        "volume_score",
        "risk_score",

        "revenue_growth",
        "profit_margin",
        "return_on_equity",
        "debt_to_equity",
    ]

    for column in numeric_columns:
        if column in frame.columns:
            frame[column] = pd.to_numeric(
                frame[column],
                errors="coerce",
            )

    if "entry_quality" in frame.columns:
        frame["entry_quality"] = (
            frame["entry_quality"]
            .fillna("UNKNOWN")
            .astype(str)
            .str.upper()
            .str.strip()
        )
    else:
        frame["entry_quality"] = "UNKNOWN"

    if "signal" in frame.columns:
        frame["signal"] = (
            frame["signal"]
            .fillna("UNKNOWN")
            .astype(str)
            .str.upper()
            .str.strip()
        )
    else:
        frame["signal"] = "UNKNOWN"

    return frame


# ============================================================
# SUMMARY HELPERS
# ============================================================

def print_section(title):
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def print_group_summary(
    frame,
    group_column,
    minimum_observations=1,
):
    """Print grouped 5D performance."""
    if group_column not in frame.columns:
        return

    grouped = (
        frame[
            frame["return_5d"].notna()
        ]
        .groupby(group_column)["return_5d"]
        .agg(
            count="count",
            mean="mean",
            median="median",
        )
    )

    grouped = grouped[
        grouped["count"] >= minimum_observations
    ]

    if grouped.empty:
        print("No observations.")
        return

    print(
        grouped.to_string(
            float_format=lambda value:
                f"{value:.3f}"
        )
    )


def print_numeric_band_summary(
    frame,
    column,
    bins,
    labels,
):
    """Print 5D performance by numeric bands."""
    if column not in frame.columns:
        return

    subset = frame[
        frame["return_5d"].notna()
        & frame[column].notna()
    ].copy()

    if subset.empty:
        print("No observations.")
        return

    subset["band"] = pd.cut(
        subset[column],
        bins=bins,
        labels=labels,
        include_lowest=True,
        right=False,
    )

    grouped = (
        subset
        .groupby(
            "band",
            observed=False,
        )["return_5d"]
        .agg(
            count="count",
            mean="mean",
            median="median",
        )
    )

    grouped["positive_pct"] = (
        subset
        .groupby(
            "band",
            observed=False,
        )["return_5d"]
        .apply(
            lambda values:
                (
                    values > 0
                ).mean() * 100
        )
    )

    grouped = grouped[
        grouped["count"] > 0
    ]

    print(
        grouped.to_string(
            float_format=lambda value:
                f"{value:.3f}"
        )
    )


# ============================================================
# WINNER / LOSER ANALYSIS
# ============================================================

def print_winner_loser_analysis(frame):
    """Compare characteristics of positive and negative outcomes."""
    matured = frame[
        frame["return_5d"].notna()
    ].copy()

    if matured.empty:
        print("No mature observations.")
        return

    winners = matured[
        matured["return_5d"] > 0
    ]

    losers = matured[
        matured["return_5d"] <= 0
    ]

    print_section(
        "BUY NEW WINNERS VS LOSERS"
    )

    print(
        f"Winners: {len(winners)}"
    )

    print(
        f"Losers:  {len(losers)}"
    )

    numeric_columns = [
        "investment_score",
        "confidence_score",
        "technical_score",
        "quality_score",
        "growth_score",
        "rsi",
        "extension_sma50_pct",
        "extension_sma200_pct",
        "candidate_rank",
        "priority_rank",
        "trend_score",
        "momentum_score",
        "volume_score",
        "risk_score",
        "revenue_growth",
        "profit_margin",
        "return_on_equity",
        "debt_to_equity",
    ]

    rows = []

    for column in numeric_columns:

        if column not in matured.columns:
            continue

        winner_mean = winners[column].mean()
        loser_mean = losers[column].mean()

        rows.append(
            {
                "metric": column,
                "winner_mean": winner_mean,
                "loser_mean": loser_mean,
                "difference": (
                    winner_mean
                    - loser_mean
                ),
            }
        )

    if rows:
        comparison = pd.DataFrame(rows)

        print(
            comparison.to_string(
                index=False,
                float_format=lambda value:
                    f"{value:.3f}"
            )
        )

    print()
    print("Winner Entry Quality:")

    print(
        winners[
            "entry_quality"
        ]
        .value_counts()
        .to_string()
    )

    print()
    print("Loser Entry Quality:")

    print(
        losers[
            "entry_quality"
        ]
        .value_counts()
        .to_string()
    )


# ============================================================
# CURRENT BUY NEW INPUT ANALYSIS
# ============================================================

def print_buy_new_input_analysis(frame):
    """
    Descriptive analysis of persisted BUY NEW decision inputs.

    Evidence Score is intentionally excluded because it is not persisted
    in recommendation_evidence.
    """
    matured = frame[
        frame["return_5d"].notna()
    ].copy()

    if matured.empty:
        return

    print_section(
        "BUY NEW INPUT GATES"
    )

    checks = []

    if "confidence_score" in matured.columns:
        checks.append(
            (
                "Confidence >= 65",
                matured["confidence_score"] >= 65,
            )
        )

    if "investment_score" in matured.columns:
        checks.append(
            (
                "Investment >= 70",
                matured["investment_score"] >= 70,
            )
        )

    for label, mask in checks:

        selected = matured[
            mask.fillna(False)
        ]

        excluded = matured[
            ~mask.fillna(False)
        ]

        print()
        print(label)

        print(
            f"  Pass: {len(selected)}"
        )

        if not selected.empty:
            print(
                f"  Pass mean: "
                f"{selected['return_5d'].mean():+.3f}%"
            )
            print(
                f"  Pass positive: "
                f"{(
                    selected['return_5d'] > 0
                ).mean() * 100:.2f}%"
            )

        print(
            f"  Fail: {len(excluded)}"
        )

        if not excluded.empty:
            print(
                f"  Fail mean: "
                f"{excluded['return_5d'].mean():+.3f}%"
            )
            print(
                f"  Fail positive: "
                f"{(
                    excluded['return_5d'] > 0
                ).mean() * 100:.2f}%"
            )


# ============================================================
# CORRELATIONS
# ============================================================

def print_correlations(frame):
    """
    Print descriptive Pearson correlations with realised 5D return.
    """
    matured = frame[
        frame["return_5d"].notna()
    ].copy()

    numeric_columns = [
        "investment_score",
        "confidence_score",
        "technical_score",
        "quality_score",
        "growth_score",
        "rsi",
        "extension_sma50_pct",
        "extension_sma200_pct",
        "candidate_rank",
        "priority_rank",
        "trend_score",
        "momentum_score",
        "volume_score",
        "risk_score",
        "revenue_growth",
        "profit_margin",
        "return_on_equity",
        "debt_to_equity",
    ]

    rows = []

    for column in numeric_columns:

        if column not in matured.columns:
            continue

        subset = matured[
            [
                column,
                "return_5d",
            ]
        ].dropna()

        if len(subset) < 3:
            continue

        correlation = (
            subset[column]
            .corr(
                subset["return_5d"]
            )
        )

        rows.append(
            {
                "metric": column,
                "n": len(subset),
                "correlation": correlation,
            }
        )

    print_section(
        "BUY NEW INPUT CORRELATIONS WITH 5D RETURN"
    )

    if not rows:
        print("No usable correlations.")
        return

    result = pd.DataFrame(rows)

    print(
        result.to_string(
            index=False,
            float_format=lambda value:
                f"{value:.3f}"
        )
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 72)
    print("BUY NEW RULE FORENSICS")
    print("=" * 72)
    print()
    print("READ-ONLY — NO PRODUCTION CHANGES")
    print()

    conn = sqlite3.connect(
        DB_PATH
    )

    try:

        decisions = load_audit_decisions(
            conn
        )

        recommendations = load_recommendations(
            conn
        )

        evaluations = load_5d_evaluations(
            conn
        )

        evidence = load_recommendation_evidence(
            conn
        )

        # ----------------------------------------------------
        # LINEAGE
        # ----------------------------------------------------

        raw_count = len(decisions)

        direct_lineage = (
            decisions[
                "recommendation_id"
            ].notna()
        )

        print_section(
            "LINEAGE"
        )

        print(
            f"Raw BUY NEW decisions:       "
            f"{raw_count}"
        )

        print(
            f"Direct lineage:              "
            f"{direct_lineage.sum()}"
        )

        decisions = reconstruct_lineage(
            decisions,
            recommendations,
        )

        reconstructed_lineage = (
            decisions["recommendation_id"].isna()
            & decisions[
                "lineage_recommendation_id"
            ].notna()
        )

        unresolved = (
            decisions[
                "lineage_recommendation_id"
            ].isna()
        )

        print(
            f"Reconstructed legacy lineage: "
            f"{reconstructed_lineage.sum()}"
        )

        print(
            f"Unresolved lineage:           "
            f"{unresolved.sum()}"
        )

        # ----------------------------------------------------
        # OUTCOMES
        # ----------------------------------------------------

        decisions = attach_outcomes(
            decisions,
            evaluations,
        )

        # ----------------------------------------------------
        # EVIDENCE
        # ----------------------------------------------------

        decisions = attach_evidence(
            decisions,
            evidence,
        )

        # ----------------------------------------------------
        # CLEAN POPULATION
        # ----------------------------------------------------

        decisions = clean_population(
            decisions
        )

        matured = decisions[
            decisions["return_5d"].notna()
        ].copy()

        print_section(
            "5D OUTCOMES"
        )

        print(
            f"With realised 5D outcome:  "
            f"{len(matured)}"
        )

        print(
            f"Without realised 5D outcome: "
            f"{len(decisions) - len(matured)}"
        )

        if not matured.empty:

            print(
                f"Mean 5D return:            "
                f"{matured['return_5d'].mean():+.3f}%"
            )

            print(
                f"Median 5D return:          "
                f"{matured['return_5d'].median():+.3f}%"
            )

            print(
                f"Positive 5D outcomes:      "
                f"{(
                    matured['return_5d'] > 0
                ).mean() * 100:.2f}%"
            )

        # ----------------------------------------------------
        # SIGNAL
        # ----------------------------------------------------

        print_section(
            "BUY NEW BY SIGNAL"
        )

        print_group_summary(
            decisions,
            "signal",
        )

        # ----------------------------------------------------
        # ENTRY QUALITY
        # ----------------------------------------------------

        print_section(
            "BUY NEW BY ENTRY QUALITY"
        )

        print_group_summary(
            decisions,
            "entry_quality",
        )

        # ----------------------------------------------------
        # CANDIDATE RANK
        # ----------------------------------------------------

        print_section(
            "BUY NEW BY CANDIDATE RANK"
        )

        print_numeric_band_summary(
            decisions,
            "candidate_rank",
            bins=[
                0,
                2,
                4,
                6,
                11,
                np.inf,
            ],
            labels=[
                "1",
                "2-3",
                "4-5",
                "6-10",
                "10+",
            ],
        )

        # ----------------------------------------------------
        # PRIORITY RANK
        # ----------------------------------------------------

        print_section(
            "BUY NEW BY PRIORITY RANK"
        )

        print_numeric_band_summary(
            decisions,
            "priority_rank",
            bins=[
                0,
                2,
                4,
                6,
                11,
                np.inf,
            ],
            labels=[
                "1",
                "2-3",
                "4-5",
                "6-10",
                "10+",
            ],
        )

        # ----------------------------------------------------
        # INVESTMENT SCORE
        # ----------------------------------------------------

        print_section(
            "BUY NEW BY INVESTMENT SCORE"
        )

        print_numeric_band_summary(
            decisions,
            "investment_score",
            bins=[
                0,
                70,
                75,
                80,
                85,
                90,
                95,
                101,
            ],
            labels=[
                "<70",
                "70-74",
                "75-79",
                "80-84",
                "85-89",
                "90-94",
                "95+",
            ],
        )

        # ----------------------------------------------------
        # CONFIDENCE
        # ----------------------------------------------------

        print_section(
            "BUY NEW BY CONFIDENCE"
        )

        print_numeric_band_summary(
            decisions,
            "confidence_score",
            bins=[
                0,
                60,
                65,
                70,
                75,
                80,
                85,
                90,
                101,
            ],
            labels=[
                "<60",
                "60-64",
                "65-69",
                "70-74",
                "75-79",
                "80-84",
                "85-89",
                "90+",
            ],
        )

        # ----------------------------------------------------
        # TECHNICAL SCORE
        # ----------------------------------------------------

        print_section(
            "BUY NEW BY TECHNICAL SCORE"
        )

        print_numeric_band_summary(
            decisions,
            "technical_score",
            bins=[
                0,
                60,
                70,
                75,
                80,
                85,
                90,
                95,
                101,
            ],
            labels=[
                "<60",
                "60-69",
                "70-74",
                "75-79",
                "80-84",
                "85-89",
                "90-94",
                "95+",
            ],
        )

        # ----------------------------------------------------
        # QUALITY SCORE
        # ----------------------------------------------------

        print_section(
            "BUY NEW BY QUALITY SCORE"
        )

        print_numeric_band_summary(
            decisions,
            "quality_score",
            bins=[
                0,
                50,
                60,
                70,
                80,
                90,
                101,
            ],
            labels=[
                "<50",
                "50-59",
                "60-69",
                "70-79",
                "80-89",
                "90+",
            ],
        )

        # ----------------------------------------------------
        # GROWTH SCORE
        # ----------------------------------------------------

        print_section(
            "BUY NEW BY GROWTH SCORE"
        )

        print_numeric_band_summary(
            decisions,
            "growth_score",
            bins=[
                0,
                60,
                70,
                80,
                85,
                90,
                95,
                101,
            ],
            labels=[
                "<60",
                "60-69",
                "70-79",
                "80-84",
                "85-89",
                "90-94",
                "95+",
            ],
        )

        # ----------------------------------------------------
        # SMA50 EXTENSION
        # ----------------------------------------------------

        print_section(
            "BUY NEW BY SMA50 EXTENSION"
        )

        print_numeric_band_summary(
            decisions,
            "extension_sma50_pct",
            bins=[
                -np.inf,
                0,
                5,
                10,
                15,
                20,
                30,
                np.inf,
            ],
            labels=[
                "<0%",
                "0-4.9%",
                "5-9.9%",
                "10-14.9%",
                "15-19.9%",
                "20-29.9%",
                "30%+",
            ],
        )

        # ----------------------------------------------------
        # SMA200 EXTENSION
        # ----------------------------------------------------

        print_section(
            "BUY NEW BY SMA200 EXTENSION"
        )

        print_numeric_band_summary(
            decisions,
            "extension_sma200_pct",
            bins=[
                -np.inf,
                0,
                5,
                10,
                15,
                20,
                30,
                np.inf,
            ],
            labels=[
                "<0%",
                "0-4.9%",
                "5-9.9%",
                "10-14.9%",
                "15-19.9%",
                "20-29.9%",
                "30%+",
            ],
        )

        # ----------------------------------------------------
        # RSI
        # ----------------------------------------------------

        print_section(
            "BUY NEW BY RSI"
        )

        print_numeric_band_summary(
            decisions,
            "rsi",
            bins=[
                0,
                30,
                40,
                50,
                60,
                70,
                80,
                101,
            ],
            labels=[
                "<30",
                "30-39",
                "40-49",
                "50-59",
                "60-69",
                "70-79",
                "80+",
            ],
        )

        # ----------------------------------------------------
        # GOVERNANCE INPUTS
        # ----------------------------------------------------

        print_buy_new_input_analysis(
            decisions
        )

        # ----------------------------------------------------
        # WINNERS VS LOSERS
        # ----------------------------------------------------

        print_winner_loser_analysis(
            decisions
        )

        # ----------------------------------------------------
        # CORRELATIONS
        # ----------------------------------------------------

        print_correlations(
            decisions
        )

        # ----------------------------------------------------
        # TICKER CONCENTRATION
        # ----------------------------------------------------

        print_section(
            "BUY NEW BY TICKER"
        )

        print_group_summary(
            decisions,
            "ticker",
        )

        # ----------------------------------------------------
        # FINAL DIAGNOSTIC
        # ----------------------------------------------------

        print_section(
            "FORENSIC POPULATION"
        )

        print(
            f"Total BUY NEW decisions: "
            f"{len(decisions)}"
        )

        print(
            f"Mature BUY NEW decisions: "
            f"{len(matured)}"
        )

        if len(decisions) > 0:
            print(
                f"Mature coverage: "
                f"{len(matured) / len(decisions) * 100:.2f}%"
            )

        print()
        print(
            "No production changes were made."
        )

        print(
            "Results are descriptive and do not establish causality."
        )

        print(
            "Use the output to determine whether an A6 calibration "
            "candidate is justified."
        )

    finally:
        conn.close()


if __name__ == "__main__":
    main()