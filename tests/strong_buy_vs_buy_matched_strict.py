"""
STRICT 1:1 STRONG BUY vs BUY matched forensic analysis.

READ-ONLY — NO PRODUCTION CHANGES.

Purpose
-------
Test whether STRONG BUY has incremental 5D outcome value after
matching against genuinely comparable BUY observations.

Matching:
    - same Entry Quality
    - nearest score profile
    - WITHOUT replacement
    - maximum match-distance caliper

No causal inference is claimed.

This script:
    - reads SQLite only
    - does not modify the database
    - does not modify production code
    - does not create output files
    - does not change thresholds or governance
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd


DB_PATH = Path("data/portfolio_manager.db")
HORIZON = 5

MATCH_FEATURES = [
    "investment_score",
    "evidence_score",
    "confidence_score",
    "technical_score",
    "quality_score",
    "growth_score",
]

# Deliberately conservative.
# We can relax this later if too few matches survive.
MAX_MATCH_DISTANCE = 2.0


def print_header(title):
    print()
    print("=" * 76)
    print(title)
    print("=" * 76)


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
        WHERE original_signal IN ('BUY', 'STRONG BUY')
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
    recommendations = recommendations.copy()

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

    for column in MATCH_FEATURES:
        decisions[column] = pd.to_numeric(
            decisions[column],
            errors="coerce",
        )

    decisions["return_5d"] = pd.to_numeric(
        decisions["return_5d"],
        errors="coerce",
    )

    decisions["entry_quality"] = (
        decisions["entry_quality"]
        .fillna("UNKNOWN")
        .astype(str)
        .str.strip()
        .str.upper()
    )

    decisions["decision_date"] = pd.to_datetime(
        decisions["created_at"],
        errors="coerce",
        utc=True,
    )

    # Matching requires complete score vectors.
    decisions = decisions[
        decisions["return_5d"].notna()
        & decisions[MATCH_FEATURES]
        .notna()
        .all(axis=1)
    ].copy()

    return decisions


def standardise(frame):

    frame = frame.copy()

    for column in MATCH_FEATURES:

        mean = frame[column].mean()
        std = frame[column].std()

        if pd.isna(std) or std == 0:
            frame[f"z_{column}"] = 0.0
        else:
            frame[f"z_{column}"] = (
                frame[column] - mean
            ) / std

    return frame


def distance(row_a, row_b):

    values = []

    for column in MATCH_FEATURES:

        values.append(
            (
                row_a[f"z_{column}"]
                - row_b[f"z_{column}"]
            ) ** 2
        )

    return float(
        np.sqrt(
            np.sum(values)
        )
    )


def match_without_replacement(frame):

    frame = standardise(frame)

    strong = frame[
        frame["original_signal"] == "STRONG BUY"
    ].copy()

    buy = frame[
        frame["original_signal"] == "BUY"
    ].copy()

    matches = []

    # Process strongest/most constrained STRONG BUY
    # observations first.
    #
    # This prevents easy observations consuming controls
    # needed by harder observations.

    strong = strong.sort_values(
        [
            "entry_quality",
            "decision_date",
            "audit_decision_id",
        ]
    )

    used_buy_ids = set()

    for _, strong_row in strong.iterrows():

        controls = buy[
            (
                buy["entry_quality"]
                == strong_row["entry_quality"]
            )
            & (
                ~buy["audit_decision_id"].isin(
                    used_buy_ids
                )
            )
        ].copy()

        if controls.empty:
            continue

        distances = []

        for _, buy_row in controls.iterrows():

            d = distance(
                strong_row,
                buy_row,
            )

            distances.append(
                (
                    d,
                    buy_row[
                        "audit_decision_id"
                    ],
                )
            )

        distances.sort(
            key=lambda x: x[0]
        )

        best_distance, best_id = (
            distances[0]
        )

        if best_distance > MAX_MATCH_DISTANCE:
            continue

        control = controls[
            controls["audit_decision_id"]
            == best_id
        ].iloc[0]

        used_buy_ids.add(
            best_id
        )

        matches.append(
            {
                "strong_buy_audit_decision_id":
                    strong_row[
                        "audit_decision_id"
                    ],
                "strong_buy_ticker":
                    strong_row["ticker"],
                "entry_quality":
                    strong_row[
                        "entry_quality"
                    ],
                "strong_buy_return_5d":
                    strong_row["return_5d"],
                "buy_audit_decision_id":
                    control[
                        "audit_decision_id"
                    ],
                "buy_ticker":
                    control["ticker"],
                "buy_return_5d":
                    control["return_5d"],
                "match_distance":
                    best_distance,
            }
        )

    return pd.DataFrame(matches)


def print_population(frame):

    print_header(
        "1. MATCHING POPULATION"
    )

    result = (
        frame.groupby(
            [
                "entry_quality",
                "original_signal",
            ],
            dropna=False,
        )
        .agg(
            n=("return_5d", "count"),
        )
        .reset_index()
    )

    print(result.to_string(index=False))


def print_matched_results(matches):

    print_header(
        "2. STRICT 1:1 MATCHED RESULTS"
    )

    if matches.empty:
        print(
            "No matches survived the caliper."
        )
        return

    matches = matches.copy()

    matches["incremental_5d"] = (
        matches["strong_buy_return_5d"]
        - matches["buy_return_5d"]
    )

    print(
        "Matched observations:",
        len(matches),
    )

    print(
        "STRONG BUY mean 5D:",
        f"{matches['strong_buy_return_5d'].mean():.4f}%",
    )

    print(
        "BUY control mean 5D:",
        f"{matches['buy_return_5d'].mean():.4f}%",
    )

    print(
        "Incremental mean 5D:",
        f"{matches['incremental_5d'].mean():.4f}%",
    )

    print()

    print(
        "STRONG BUY median 5D:",
        f"{matches['strong_buy_return_5d'].median():.4f}%",
    )

    print(
        "BUY control median 5D:",
        f"{matches['buy_return_5d'].median():.4f}%",
    )

    print(
        "Incremental median 5D:",
        f"{matches['incremental_5d'].median():.4f}%",
    )

    print()

    print(
        "STRONG BUY beats BUY:",
        f"{(matches['incremental_5d'] > 0).mean() * 100:.2f}%",
    )

    print(
        "STRONG BUY loses to BUY:",
        f"{(matches['incremental_5d'] < 0).mean() * 100:.2f}%",
    )

    print()

    print(
        "Mean match distance:",
        f"{matches['match_distance'].mean():.4f}",
    )

    print(
        "Median match distance:",
        f"{matches['match_distance'].median():.4f}",
    )

    print(
        "Maximum match distance:",
        f"{matches['match_distance'].max():.4f}",
    )


def print_by_entry_quality(matches):

    print_header(
        "3. STRICT MATCHES BY ENTRY QUALITY"
    )

    if matches.empty:
        print("No matches.")
        return

    matches = matches.copy()

    matches["incremental_5d"] = (
        matches["strong_buy_return_5d"]
        - matches["buy_return_5d"]
    )

    result = (
        matches.groupby(
            "entry_quality",
            dropna=False,
        )
        .agg(
            n=("incremental_5d", "count"),
            strong_buy_mean_5d=(
                "strong_buy_return_5d",
                "mean",
            ),
            buy_mean_5d=(
                "buy_return_5d",
                "mean",
            ),
            incremental_mean_5d=(
                "incremental_5d",
                "mean",
            ),
            incremental_median_5d=(
                "incremental_5d",
                "median",
            ),
            strong_buy_beats_buy=(
                "incremental_5d",
                lambda s: (
                    s > 0
                ).mean() * 100,
            ),
        )
        .reset_index()
    )

    print(result.to_string(index=False))


def print_unmatched(frame, matches):

    print_header(
        "4. MATCHING COVERAGE"
    )

    strong_count = (
        frame[
            frame["original_signal"]
            == "STRONG BUY"
        ]
        .shape[0]
    )

    matched_count = (
        matches[
            "strong_buy_audit_decision_id"
        ]
        .nunique()
        if not matches.empty
        else 0
    )

    print(
        f"STRONG BUY observations: "
        f"{strong_count}"
    )

    print(
        f"Matched STRONG BUY observations: "
        f"{matched_count}"
    )

    print(
        f"Unmatched STRONG BUY observations: "
        f"{strong_count - matched_count}"
    )

    if strong_count:
        print(
            "Match coverage:",
            f"{matched_count / strong_count * 100:.2f}%",
        )


def print_winner_loser(frame):

    print_header(
        "5. STRONG BUY WINNERS vs LOSERS"
    )

    strong = frame[
        frame["original_signal"]
        == "STRONG BUY"
    ].copy()

    strong["outcome"] = np.where(
        strong["return_5d"] > 0,
        "WINNER",
        "LOSER",
    )

    result = (
        strong.groupby(
            "outcome",
            dropna=False,
        )
        .agg(
            n=("return_5d", "count"),
            mean_5d=("return_5d", "mean"),
            median_5d=("return_5d", "median"),
            investment_score=(
                "investment_score",
                "mean",
            ),
            evidence_score=(
                "evidence_score",
                "mean",
            ),
            confidence_score=(
                "confidence_score",
                "mean",
            ),
            technical_score=(
                "technical_score",
                "mean",
            ),
            quality_score=(
                "quality_score",
                "mean",
            ),
            growth_score=(
                "growth_score",
                "mean",
            ),
        )
        .reset_index()
    )

    print(result.to_string(index=False))


def main():

    print()
    print("=" * 76)
    print("STRICT STRONG BUY vs BUY MATCHED FORENSICS")
    print("=" * 76)
    print()
    print(
        "READ-ONLY — NO PRODUCTION CHANGES"
    )

    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database not found: {DB_PATH}"
        )

    conn = sqlite3.connect(
        DB_PATH
    )

    try:

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

    finally:
        conn.close()

    print(
        f"\nBUY / STRONG BUY decisions with "
        f"mature {HORIZON}D outcome and complete "
        f"matching scores: {len(frame)}"
    )

    print_population(frame)

    matches = match_without_replacement(
        frame
    )

    print_matched_results(
        matches
    )

    print_by_entry_quality(
        matches
    )

    print_unmatched(
        frame,
        matches,
    )

    print_winner_loser(
        frame
    )

    print()
    print("=" * 76)
    print("END — READ-ONLY ANALYSIS")
    print("=" * 76)
    print()


if __name__ == "__main__":
    main()
