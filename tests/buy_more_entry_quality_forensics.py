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



def clean_entry_quality(frame):

    frame = frame.copy()

    frame["entry_quality"] = (
        frame["entry_quality"]
        .fillna("UNKNOWN")
        .astype(str)
        .str.strip()
        .str.upper()
    )

    for column in [
        "extension_sma50_pct",
        "extension_sma200_pct",
        "return_10d_pct",
        "return_20d_pct",
    ]:
        frame[column] = pd.to_numeric(
            frame[column],
            errors="coerce",
        )

    return frame


def summary(frame, group_columns):

    result = (
        frame
        .groupby(
            group_columns,
            dropna=False,
        )
        .agg(
            n=("return_5d", "size"),
            mean_5d=("return_5d", "mean"),
            median_5d=("return_5d", "median"),
            positive_5d=(
                "return_5d",
                lambda x: (x > 0).mean() * 100,
            ),
            mean_sma50_extension=(
                "extension_sma50_pct",
                "mean",
            ),
            mean_sma200_extension=(
                "extension_sma200_pct",
                "mean",
            ),
        )
        .reset_index()
    )

    return result[
        result["n"] >= MIN_GROUP_SIZE
    ].sort_values(
        group_columns
    )


def print_entry_quality_distribution(frame):

    print_header(
        1,
        "ENTRY QUALITY DISTRIBUTION",
    )

    result = (
        frame
        .groupby(
            ["original_signal", "entry_quality"],
            dropna=False,
        )
        .agg(
            n=("return_5d", "size"),
            mean_5d=("return_5d", "mean"),
            median_5d=("return_5d", "median"),
            positive_5d=(
                "return_5d",
                lambda x: (x > 0).mean() * 100,
            ),
        )
        .reset_index()
    )

    result = result[result["n"] >= MIN_GROUP_SIZE]

    print(result.to_string(index=False))


def print_entry_quality_outcomes(frame):

    print_header(
        2,
        "5D OUTCOME BY ENTRY QUALITY",
    )

    result = summary(
        frame,
        ["entry_quality"],
    )

    print(result.to_string(index=False))


def print_signal_entry_quality(frame):

    print_header(
        3,
        "SIGNAL × ENTRY QUALITY",
    )

    result = summary(
        frame,
        [
            "original_signal",
            "entry_quality",
        ],
    )

    print(result.to_string(index=False))


def extension_band(value):

    if pd.isna(value):
        return "UNKNOWN"

    if value < 0:
        return "<0%"

    if value < 5:
        return "0-5%"

    if value < 10:
        return "5-10%"

    if value < 15:
        return "10-15%"

    if value < 20:
        return "15-20%"

    return "20%+"


def add_extension_bands(frame):

    frame = frame.copy()

    frame["sma50_extension_band"] = (
        frame["extension_sma50_pct"]
        .apply(extension_band)
    )

    frame["sma200_extension_band"] = (
        frame["extension_sma200_pct"]
        .apply(extension_band)
    )

    return frame


def print_sma50(frame):

    print_header(
        4,
        "SMA50 EXTENSION × SIGNAL",
    )

    result = summary(
        frame,
        [
            "original_signal",
            "sma50_extension_band",
        ],
    )

    print(result.to_string(index=False))


def print_sma200(frame):

    print_header(
        5,
        "SMA200 EXTENSION × SIGNAL",
    )

    result = summary(
        frame,
        [
            "original_signal",
            "sma200_extension_band",
        ],
    )

    print(result.to_string(index=False))


def print_entry_quality_extensions(frame):

    print_header(
        6,
        "ENTRY QUALITY × EXTENSION",
    )

    result = (
        frame
        .groupby(
            [
                "original_signal",
                "entry_quality",
            ],
            dropna=False,
        )
        .agg(
            n=("return_5d", "size"),
            mean_5d=("return_5d", "mean"),
            median_5d=("return_5d", "median"),
            positive_5d=(
                "return_5d",
                lambda x: (x > 0).mean() * 100,
            ),
            sma50_extension=(
                "extension_sma50_pct",
                "mean",
            ),
            sma200_extension=(
                "extension_sma200_pct",
                "mean",
            ),
        )
        .reset_index()
    )

    result = result[result["n"] >= MIN_GROUP_SIZE]

    print(result.to_string(index=False))


def print_controlled_signal_comparison(frame):

    print_header(
        7,
        "STRONG BUY VS BUY — WITHIN ENTRY QUALITY",
    )

    result = (
        frame
        .groupby(
            [
                "entry_quality",
                "original_signal",
            ],
            dropna=False,
        )
        .agg(
            n=("return_5d", "size"),
            mean_5d=("return_5d", "mean"),
            median_5d=("return_5d", "median"),
            positive_5d=(
                "return_5d",
                lambda x: (x > 0).mean() * 100,
            ),
            sma50_extension=(
                "extension_sma50_pct",
                "mean",
            ),
            sma200_extension=(
                "extension_sma200_pct",
                "mean",
            ),
        )
        .reset_index()
    )

    result = result[result["n"] >= MIN_GROUP_SIZE]

    print(result.to_string(index=False))

    print(
        "\nInterpretation aid:"
    )
    print(
        "If STRONG BUY remains materially below BUY "
        "within the same Entry Quality category, "
        "Entry Quality does not fully explain the "
        "STRONG BUY problem."
    )
    print(
        "If the difference largely disappears within "
        "Entry Quality categories, entry timing becomes "
        "a stronger candidate mechanism."
    )


def print_rejected_comparison(frame):

    print_header(
        8,
        "ACCEPTED VS REJECTED — ENTRY QUALITY",
    )

    result = (
        frame
        .groupby(
            [
                "original_signal",
                "final_action",
                "entry_quality",
            ],
            dropna=False,
        )
        .agg(
            n=("return_5d", "size"),
            mean_5d=("return_5d", "mean"),
            median_5d=("return_5d", "median"),
            positive_5d=(
                "return_5d",
                lambda x: (x > 0).mean() * 100,
            ),
            sma50_extension=(
                "extension_sma50_pct",
                "mean",
            ),
            sma200_extension=(
                "extension_sma200_pct",
                "mean",
            ),
        )
        .reset_index()
    )

    result = result[result["n"] >= MIN_GROUP_SIZE]

    print(result.to_string(index=False))


def print_temporal_entry_quality(frame):

    print_header(
        9,
        "TEMPORAL STABILITY — ENTRY QUALITY",
    )

    working = frame.copy()

    midpoint = working["decision_date"].median()

    working["period"] = np.where(
        working["decision_date"] <= midpoint,
        "EARLY",
        "LATE",
    )

    result = (
        working
        .groupby(
            [
                "period",
                "original_signal",
                "entry_quality",
            ],
            dropna=False,
        )
        .agg(
            n=("return_5d", "size"),
            mean_5d=("return_5d", "mean"),
            median_5d=("return_5d", "median"),
            positive_5d=(
                "return_5d",
                lambda x: (x > 0).mean() * 100,
            ),
        )
        .reset_index()
    )

    result = result[result["n"] >= MIN_GROUP_SIZE]

    print(result.to_string(index=False))


def print_missing_telemetry(frame):

    print_header(
        10,
        "ENTRY QUALITY TELEMETRY COVERAGE",
    )

    total = len(frame)

    with_entry = (
        frame["entry_quality"]
        .notna()
        .sum()
    )

    with_sma50 = (
        frame["extension_sma50_pct"]
        .notna()
        .sum()
    )

    with_sma200 = (
        frame["extension_sma200_pct"]
        .notna()
        .sum()
    )

    print(
        f"BUY MORE decisions with 5D outcome: {total}"
    )

    print(
        f"Entry Quality populated: "
        f"{with_entry} "
        f"({with_entry / total * 100:.2f}%)"
    )

    print(
        f"SMA50 extension populated: "
        f"{with_sma50} "
        f"({with_sma50 / total * 100:.2f}%)"
    )

    print(
        f"SMA200 extension populated: "
        f"{with_sma200} "
        f"({with_sma200 / total * 100:.2f}%)"
    )


def main():

    print("=" * 76)
    print("BUY MORE ENTRY QUALITY FORENSICS")
    print("=" * 76)
    print("READ-ONLY — NO PRODUCTION CHANGES")

    with sqlite3.connect(DB_PATH) as conn:

        (
            decisions,
            recommendations,
            evaluations,
            evidence,
        ) = load_data(conn)

        frame = reconstruct_lineage(
            decisions,
            recommendations,
            evaluations,
            evidence,
        )

    print(
        f"\nBUY MORE decisions with "
        f"mature 5D outcome: {len(frame)}"
    )

    accepted, rejected = split(frame)

    print(
        f"Accepted BUY MORE: {len(accepted)}"
    )

    print(
        f"Rejected BUY MORE → HOLD: {len(rejected)}"
    )

    frame = clean_entry_quality(frame)
    frame = add_extension_bands(frame)

    print_missing_telemetry(frame)

    print_entry_quality_distribution(frame)

    print_entry_quality_outcomes(frame)

    print_signal_entry_quality(frame)

    print_sma50(frame)

    print_sma200(frame)

    print_entry_quality_extensions(frame)

    print_controlled_signal_comparison(frame)

    print_rejected_comparison(frame)

    print_temporal_entry_quality(frame)


if __name__ == "__main__":
    main()
