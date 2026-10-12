"""
BUY MORE signal / score forensic analysis.

READ-ONLY — NO PRODUCTION CHANGES.

Purpose
-------
Investigate the strongest BUY MORE findings from the regime analysis:

1. BUY vs STRONG BUY
2. Actual Investment Score values
3. Actual Confidence Score values
4. Quality Score behaviour
5. Signal × Investment Score
6. Signal × Technical / Quality / Growth
7. STRONG BUY forensic characteristics
8. Temporal stability

This script:
    - reads SQLite only
    - does not modify the database
    - does not modify production code
    - does not create report/output files
    - does not change thresholds or governance

Historical outcomes are observational 5D stock returns.
They are not causal estimates.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd


DB_PATH = Path("data/portfolio_manager.db")
HORIZON = 5

SCORES = [
    "investment_score",
    "evidence_score",
    "confidence_score",
    "technical_score",
    "quality_score",
    "growth_score",
]

MIN_GROUP_SIZE = 8


def fmt(value):
    if pd.isna(value):
        return "n/a"
    return f"{value:.2f}%"


def load_data(conn):

    decisions = pd.read_sql_query(
        """
        SELECT
            id AS audit_decision_id,
            audit_run_id,
            ticker,
            asset_type,
            created_at,
            proposed_action,
            final_action,
            original_signal,
            investment_score,
            technical_score,
            quality_score,
            growth_score,
            confidence_score,
            evidence_score,
            recommendation_id
        FROM audit_decisions
        WHERE proposed_action = 'BUY MORE'
        ORDER BY created_at, id
        """,
        conn,
    )

    recommendations = pd.read_sql_query(
        """
        SELECT
            id AS recommendation_id,
            date AS recommendation_date,
            ticker
        FROM recommendations
        ORDER BY ticker, date, id
        """,
        conn,
    )

    evaluations = pd.read_sql_query(
        """
        SELECT
            recommendation_id,
            evaluation_date,
            return_percent
        FROM recommendation_evaluations
        WHERE days_after = ?
          AND return_percent IS NOT NULL
        ORDER BY recommendation_id, evaluation_date
        """,
        conn,
        params=(HORIZON,),
    )

    evidence = pd.read_sql_query(
        """
        SELECT
            recommendation_id AS lineage_recommendation_id,
            ticker AS evidence_ticker,
            capture_date,
            entry_quality,
            entry_quality_mode,
            extension_sma50_pct,
            extension_sma200_pct,
            return_5d_pct AS evidence_return_5d,
            return_10d_pct,
            return_20d_pct
        FROM recommendation_evidence
        """,
        conn,
    )

    return (
        decisions,
        recommendations,
        evaluations,
        evidence,
    )


def reconstruct_lineage(
    decisions,
    recommendations,
    evaluations,
    evidence,
):
    decisions = decisions.copy()

    recommendations["recommendation_day"] = (
        pd.to_datetime(
            recommendations["recommendation_date"],
            errors="coerce",
            utc=True,
        ).dt.date
    )

    lookup = {
        ticker: group.sort_values(
            ["recommendation_day", "recommendation_id"]
        )
        for ticker, group
        in recommendations.groupby("ticker")
    }

    lineage = []

    for _, row in decisions.iterrows():

        direct_id = row["recommendation_id"]

        if pd.notna(direct_id):
            lineage.append(direct_id)
            continue

        candidates = lookup.get(row["ticker"])

        if candidates is None:
            lineage.append(np.nan)
            continue

        audit_date = pd.to_datetime(
            row["created_at"],
            errors="coerce",
            utc=True,
        )

        if pd.isna(audit_date):
            lineage.append(np.nan)
            continue

        valid = candidates[
            candidates["recommendation_day"]
            <= audit_date.date()
        ]

        if valid.empty:
            lineage.append(np.nan)
            continue

        lineage.append(
            valid.iloc[-1]["recommendation_id"]
        )

    decisions[
        "lineage_recommendation_id"
    ] = lineage

    evaluations = (
        evaluations
        .drop_duplicates(
            subset=["recommendation_id"],
            keep="first",
        )
        .rename(
            columns={
                "recommendation_id":
                    "lineage_recommendation_id",
                "return_percent":
                    "return_5d",
            }
        )
    )

    decisions = decisions.merge(
        evaluations[
            [
                "lineage_recommendation_id",
                "return_5d",
            ]
        ],
        on="lineage_recommendation_id",
        how="left",
    )

    evidence = (
        evidence
        .drop_duplicates(
            subset=["lineage_recommendation_id"],
            keep="first",
        )
    )

    decisions = decisions.merge(
        evidence[
            [
                "lineage_recommendation_id",
                "entry_quality",
                "entry_quality_mode",
                "extension_sma50_pct",
                "extension_sma200_pct",
                "evidence_return_5d",
                "return_10d_pct",
                "return_20d_pct",
            ]
        ],
        on="lineage_recommendation_id",
        how="left",
    )

    for column in SCORES:
        decisions[column] = pd.to_numeric(
            decisions[column],
            errors="coerce",
        )

    for column in [
        "extension_sma50_pct",
        "extension_sma200_pct",
        "evidence_return_5d",
        "return_10d_pct",
        "return_20d_pct",
    ]:
        decisions[column] = pd.to_numeric(
            decisions[column],
            errors="coerce",
        )

    decisions["decision_date"] = pd.to_datetime(
        decisions["created_at"],
        errors="coerce",
        utc=True,
    )

    return decisions[
        decisions["return_5d"].notna()
    ].copy()


def split(frame):
    accepted = frame[
        frame["final_action"] == "BUY MORE"
    ].copy()

    rejected = frame[
        frame["final_action"] == "HOLD"
    ].copy()

    return accepted, rejected


def print_header(number, title):
    print("\n" + "=" * 76)
    print(f"{number}. {title}")
    print("=" * 76)




def clean_analysis_data(frame):
    frame = frame.copy()

    numeric_columns = [
        "investment_score",
        "evidence_score",
        "confidence_score",
        "technical_score",
        "quality_score",
        "growth_score",
        "sma50_extension",
        "sma200_extension",
        "return_5d",
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
            .str.strip()
            .str.upper()
        )
    else:
        frame["entry_quality"] = "UNKNOWN"

    return frame


def print_header(title):
    print()
    print("=" * 76)
    print(title)
    print("=" * 76)


def grouped_outcome(frame, group_columns):
    return (
        frame.groupby(group_columns, dropna=False)
        .agg(
            n=("return_5d", "count"),
            mean_5d=("return_5d", "mean"),
            median_5d=("return_5d", "median"),
            positive_5d=(
                "return_5d",
                lambda s: (s > 0).mean() * 100,
            ),
        )
        .reset_index()
    )


def print_grouped(frame, group_columns, title):
    print_header(title)

    result = grouped_outcome(
        frame,
        group_columns,
    )

    if result.empty:
        print("No data.")
        return

    print(result.to_string(index=False))


def score_band(value):
    if pd.isna(value):
        return "UNKNOWN"

    if value < 50:
        return "<50"
    if value < 60:
        return "50-59"
    if value < 70:
        return "60-69"
    if value < 80:
        return "70-79"
    if value < 90:
        return "80-89"

    return "90+"


def add_score_bands(frame):
    frame = frame.copy()

    mappings = {
        "investment_score": "investment_band",
        "evidence_score": "evidence_band",
        "confidence_score": "confidence_band",
        "technical_score": "technical_band",
        "quality_score": "quality_band",
        "growth_score": "growth_band",
    }

    for source, target in mappings.items():
        frame[target] = frame[source].apply(score_band)

    return frame


def print_baseline(frame):
    print_header("1. STRONG BUY VS BUY — BASELINE")

    result = (
        frame.groupby("original_signal", dropna=False)
        .agg(
            n=("return_5d", "count"),
            mean_5d=("return_5d", "mean"),
            median_5d=("return_5d", "median"),
            positive_5d=(
                "return_5d",
                lambda s: (s > 0).mean() * 100,
            ),
            investment_score=("investment_score", "mean"),
            evidence_score=("evidence_score", "mean"),
            confidence_score=("confidence_score", "mean"),
            technical_score=("technical_score", "mean"),
            quality_score=("quality_score", "mean"),
            growth_score=("growth_score", "mean"),
        )
        .reset_index()
    )

    print(result.to_string(index=False))


def print_score_analysis(
    frame,
    score_band_column,
    title,
):
    print_grouped(
        frame,
        [
            "original_signal",
            score_band_column,
        ],
        title,
    )


def print_entry_quality_score_interaction(
    frame,
    score_band_column,
    title,
):
    print_grouped(
        frame,
        [
            "original_signal",
            "entry_quality",
            score_band_column,
        ],
        title,
    )


def print_entry_quality_baseline(frame):
    print_grouped(
        frame,
        [
            "original_signal",
            "entry_quality",
        ],
        "8. ENTRY QUALITY × SIGNAL",
    )


def print_strong_buy_winners_losers(frame):

    print_header("STRONG BUY — FINE-GRAINED WINNER VS LOSER FORENSICS")

    strong = frame[
        frame["original_signal"] == "STRONG BUY"
    ].copy()

    if strong.empty:
        print("No STRONG BUY observations.")
        return

    strong["outcome"] = strong["return_5d"].apply(
        lambda x: "WINNER" if x > 0 else "LOSER"
    )

    print(
        strong.groupby("outcome")
        .agg(
            n=("return_5d", "count"),
            mean_5d=("return_5d", "mean"),
            median_5d=("return_5d", "median"),
            investment_score=("investment_score", "mean"),
            evidence_score=("evidence_score", "mean"),
            confidence_score=("confidence_score", "mean"),
            technical_score=("technical_score", "mean"),
            quality_score=("quality_score", "mean"),
            growth_score=("growth_score", "mean"),
        )
        .round(3)
        .to_string()
    )

    def fine_band(value):
        if pd.isna(value):
            return "UNKNOWN"
        lower = int(value // 2) * 2
        return f"{lower}-{lower + 1}"

    for column, label in [
        ("investment_score", "INVESTMENT SCORE"),
        ("evidence_score", "EVIDENCE SCORE"),
        ("confidence_score", "CONFIDENCE SCORE"),
        ("technical_score", "TECHNICAL SCORE"),
        ("quality_score", "QUALITY SCORE"),
        ("growth_score", "GROWTH SCORE"),
    ]:

        print_header(f"STRONG BUY — {label} FINE BANDS")

        strong[f"{column}_fine_band"] = strong[column].apply(
            fine_band
        )

        result = (
            strong.groupby(
                ["outcome", f"{column}_fine_band"]
            )
            .agg(
                n=("return_5d", "count"),
                mean_5d=("return_5d", "mean"),
                median_5d=("return_5d", "median"),
                positive_5d=(
                    "return_5d",
                    lambda x: (x > 0).mean() * 100,
                ),
            )
            .reset_index()
        )

        print(
            result.round(3).to_string(index=False)
        )

    print_header("STRONG BUY — ENTRY QUALITY × WINNER/LOSER")

    print(
        strong.groupby(
            ["entry_quality", "outcome"]
        )
        .agg(
            n=("return_5d", "count"),
            mean_5d=("return_5d", "mean"),
            median_5d=("return_5d", "median"),
            positive_5d=(
                "return_5d",
                lambda x: (x > 0).mean() * 100,
            ),
            investment_score=("investment_score", "mean"),
            evidence_score=("evidence_score", "mean"),
            confidence_score=("confidence_score", "mean"),
            technical_score=("technical_score", "mean"),
            quality_score=("quality_score", "mean"),
            growth_score=("growth_score", "mean"),
        )
        .round(3)
        .to_string()
    )

    print_header("STRONG BUY — SCORE INTERACTIONS")

    strong["evidence_band"] = pd.cut(
        strong["evidence_score"],
        bins=[-float("inf"), 59, 64, 69, 74, 79, float("inf")],
        labels=["<60", "60-64", "65-69", "70-74", "75-79", "80+"],
    )

    strong["confidence_band"] = pd.cut(
        strong["confidence_score"],
        bins=[-float("inf"), 69, 79, 89, float("inf")],
        labels=["<70", "70-79", "80-89", "90+"],
    )

    strong["entry_signal"] = strong["entry_quality"].fillna(
        "UNKNOWN"
    )

    result = (
        strong.groupby(
            [
                "entry_signal",
                "evidence_band",
                "confidence_band",
                "outcome",
            ],
            observed=True,
        )
        .agg(
            n=("return_5d", "count"),
            mean_5d=("return_5d", "mean"),
            positive_5d=(
                "return_5d",
                lambda x: (x > 0).mean() * 100,
            ),
        )
        .reset_index()
    )

    print(
        result.round(3).to_string(index=False)
    )

    print_header("STRONG BUY — TEMPORAL STABILITY")

    if "period" in strong.columns:

        result = (
            strong.groupby(
                ["period", "entry_quality"]
            )
            .agg(
                n=("return_5d", "count"),
                mean_5d=("return_5d", "mean"),
                median_5d=("return_5d", "median"),
                positive_5d=(
                    "return_5d",
                    lambda x: (x > 0).mean() * 100,
                ),
            )
            .reset_index()
        )

        print(
            result.round(3).to_string(index=False)
        )
    else:
        print(
            "Temporal period field unavailable."
        )

def print_temporal_stability(frame):
    if "period" not in frame.columns:
        return

    print_grouped(
        frame,
        [
            "period",
            "original_signal",
        ],
        "14. TEMPORAL STABILITY",
    )


def print_missing_telemetry(frame):
    print_header("15. TELEMETRY COVERAGE")

    total = len(frame)

    print(
        f"BUY / STRONG BUY decisions with mature 5D outcome: "
        f"{total}"
    )

    telemetry = [
        "investment_score",
        "evidence_score",
        "confidence_score",
        "technical_score",
        "quality_score",
        "growth_score",
        "entry_quality",
        "sma50_extension",
        "sma200_extension",
    ]

    for column in telemetry:
        if column not in frame.columns:
            continue

        populated = frame[column].notna().sum()

        if total:
            percentage = populated / total * 100
        else:
            percentage = 0

        print(
            f"{column}: "
            f"{populated} "
            f"({percentage:.2f}%)"
        )


def main():
    with sqlite3.connect(DB_PATH) as conn:
        decisions, recommendations, evaluations, evidence = (
            load_data(conn)
        )

        frame = reconstruct_lineage(
            decisions,
            recommendations,
            evaluations,
            evidence,
        )

    frame = clean_analysis_data(frame)

    mature = frame[
        frame["return_5d"].notna()
    ].copy()

    buy_more = mature[
        mature["proposed_action"] == "BUY MORE"
    ].copy()

    print_header("BUY MORE STRONG BUY FORENSICS")

    print("READ-ONLY — NO PRODUCTION CHANGES")
    print()

    print(
        f"BUY MORE decisions with mature 5D outcome: "
        f"{len(buy_more)}"
    )

    accepted = buy_more[
        buy_more["final_action"] == "BUY MORE"
    ]

    rejected = buy_more[
        buy_more["final_action"] == "HOLD"
    ]

    print(f"Accepted BUY MORE: {len(accepted)}")
    print(f"Rejected BUY MORE → HOLD: {len(rejected)}")

    analysis = mature[
        mature["original_signal"].isin(
            ["BUY", "STRONG BUY"]
        )
    ].copy()

    analysis = add_score_bands(analysis)

    print_baseline(analysis)

    print_score_analysis(
        analysis,
        "investment_band",
        "2. INVESTMENT SCORE × SIGNAL",
    )

    print_score_analysis(
        analysis,
        "evidence_band",
        "3. EVIDENCE SCORE × SIGNAL",
    )

    print_score_analysis(
        analysis,
        "confidence_band",
        "4. CONFIDENCE SCORE × SIGNAL",
    )

    print_score_analysis(
        analysis,
        "technical_band",
        "5. TECHNICAL SCORE × SIGNAL",
    )

    print_score_analysis(
        analysis,
        "quality_band",
        "6. QUALITY SCORE × SIGNAL",
    )

    print_score_analysis(
        analysis,
        "growth_band",
        "7. GROWTH SCORE × SIGNAL",
    )

    print_entry_quality_baseline(
        analysis
    )

    print_entry_quality_score_interaction(
        analysis,
        "evidence_band",
        "9. ENTRY QUALITY × EVIDENCE × SIGNAL",
    )

    print_entry_quality_score_interaction(
        analysis,
        "growth_band",
        "10. ENTRY QUALITY × GROWTH × SIGNAL",
    )

    print_entry_quality_score_interaction(
        analysis,
        "confidence_band",
        "11. ENTRY QUALITY × CONFIDENCE × SIGNAL",
    )

    print_entry_quality_score_interaction(
        analysis,
        "investment_band",
        "12. ENTRY QUALITY × INVESTMENT SCORE × SIGNAL",
    )

    print_strong_buy_winners_losers(
        analysis
    )

    print_temporal_stability(
        analysis
    )

    print_missing_telemetry(
        analysis
    )


if __name__ == "__main__":
    main()
