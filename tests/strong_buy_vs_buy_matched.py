"""
STRONG BUY vs BUY matched forensic analysis.

READ-ONLY — NO PRODUCTION CHANGES.

Purpose
-------
Determine whether STRONG BUY itself provides useful incremental
5D outcome information after controlling for comparable BUY
observations.

Matching is observational, not causal.

The analysis:
    1. Loads all BUY / STRONG BUY audit decisions.
    2. Reconstructs recommendation lineage using the existing
       audit-date / ticker lineage approach.
    3. Joins realised 5D outcomes.
    4. Joins persisted Entry Quality evidence.
    5. Compares STRONG BUY against BUY within the same
       Entry Quality.
    6. Performs nearest-neighbour matching on the available
       score dimensions.
    7. Reports STRONG BUY vs matched BUY outcomes.

This script:
    - reads SQLite only
    - does not modify the database
    - does not modify production code
    - does not create output files
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

MATCH_FEATURES = [
    "investment_score",
    "evidence_score",
    "confidence_score",
    "technical_score",
    "quality_score",
    "growth_score",
]

MIN_GROUP_SIZE = 8


# ============================================================
# HELPERS
# ============================================================

def print_header(title):
    print()
    print("=" * 76)
    print(title)
    print("=" * 76)


def fmt(value):
    if pd.isna(value):
        return "n/a"
    return f"{value:.2f}"


# ============================================================
# LOAD DATA
# ============================================================

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


# ============================================================
# RECONSTRUCT LINEAGE
# ============================================================

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

    # --------------------------------------------------------
    # 5D OUTCOME
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # ENTRY QUALITY EVIDENCE
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # NUMERIC NORMALISATION
    # --------------------------------------------------------

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

    decisions["entry_quality"] = (
        decisions["entry_quality"]
        .fillna("UNKNOWN")
        .astype(str)
        .str.strip()
        .str.upper()
    )

    return decisions[
        decisions["return_5d"].notna()
    ].copy()


# ============================================================
# BASIC GROUPED OUTCOME
# ============================================================

def grouped_outcome(frame, group_columns):
    return (
        frame.groupby(
            group_columns,
            dropna=False,
        )
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


# ============================================================
# BASELINE
# ============================================================

def print_baseline(frame):

    print_header(
        "1. ALL BUY vs STRONG BUY — BASELINE"
    )

    result = (
        frame.groupby(
            "original_signal",
            dropna=False,
        )
        .agg(
            n=("return_5d", "count"),
            mean_5d=("return_5d", "mean"),
            median_5d=("return_5d", "median"),
            positive_5d=(
                "return_5d",
                lambda s: (s > 0).mean() * 100,
            ),
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


# ============================================================
# ENTRY QUALITY COMPARISON
# ============================================================

def print_entry_quality(frame):

    print_header(
        "2. ENTRY QUALITY × SIGNAL"
    )

    result = grouped_outcome(
        frame,
        [
            "original_signal",
            "entry_quality",
        ],
    )

    result = result[
        result["n"] >= MIN_GROUP_SIZE
    ]

    print(result.to_string(index=False))


# ============================================================
# ENTRY QUALITY COUNTS
# ============================================================

def print_entry_quality_counts(frame):

    print_header(
        "3. ENTRY QUALITY COUNTS"
    )

    result = (
        frame.groupby(
            [
                "entry_quality",
                "original_signal",
            ],
            dropna=False,
        )
        .size()
        .reset_index(name="n")
    )

    print(result.to_string(index=False))


# ============================================================
# SCORE DISTANCE
# ============================================================

def standardise_features(frame, columns):

    result = frame.copy()

    for column in columns:

        values = pd.to_numeric(
            result[column],
            errors="coerce",
        )

        mean = values.mean()
        std = values.std()

        if pd.isna(std) or std == 0:
            result[
                f"__z_{column}"
            ] = 0.0
        else:
            result[
                f"__z_{column}"
            ] = (
                values - mean
            ) / std

    return result


# ============================================================
# MATCH STRONG BUY → BUY
# ============================================================

def build_matches(frame):

    strong_buy = frame[
        frame["original_signal"] == "STRONG BUY"
    ].copy()

    buy = frame[
        frame["original_signal"] == "BUY"
    ].copy()

    matches = []

    if strong_buy.empty or buy.empty:
        return pd.DataFrame()

    # --------------------------------------------------------
    # Standardise scores using the complete population.
    # --------------------------------------------------------

    combined = pd.concat(
        [
            strong_buy,
            buy,
        ],
        ignore_index=True,
    )

    combined = standardise_features(
        combined,
        MATCH_FEATURES,
    )

    strong_buy = combined[
        combined["original_signal"] == "STRONG BUY"
    ].copy()

    buy = combined[
        combined["original_signal"] == "BUY"
    ].copy()

    # --------------------------------------------------------
    # Match within Entry Quality.
    #
    # This deliberately excludes UNKNOWN from the primary
    # matched analysis because there is no comparable
    # STRONG BUY UNKNOWN population.
    # --------------------------------------------------------

    usable_entry_quality = [
        "REASONABLE",
        "MODERATELY EXTENDED",
        "EXTENDED",
        "HIGHLY EXTENDED",
    ]

    strong_buy = strong_buy[
        strong_buy["entry_quality"].isin(
            usable_entry_quality
        )
    ].copy()

    buy = buy[
        buy["entry_quality"].isin(
            usable_entry_quality
        )
    ].copy()

    if strong_buy.empty or buy.empty:
        return pd.DataFrame()

    # --------------------------------------------------------
    # Nearest-neighbour matching WITH replacement.
    #
    # Each STRONG BUY gets the closest BUY observation
    # within the same Entry Quality bucket.
    #
    # Matching is observational and not causal.
    # --------------------------------------------------------

    z_columns = [
        f"__z_{column}"
        for column in MATCH_FEATURES
    ]

    for _, strong_row in strong_buy.iterrows():

        controls = buy[
            buy["entry_quality"]
            == strong_row["entry_quality"]
        ].copy()

        if controls.empty:
            continue

        distances = (
            (
                controls[z_columns]
                - strong_row[z_columns].values
            ) ** 2
        ).sum(axis=1)

        nearest_index = distances.idxmin()
        control = controls.loc[
            nearest_index
        ]

        matches.append(
            {
                "strong_buy_audit_decision_id":
                    strong_row[
                        "audit_decision_id"
                    ],
                "strong_buy_ticker":
                    strong_row["ticker"],
                "strong_buy_entry_quality":
                    strong_row["entry_quality"],
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
                    float(
                        np.sqrt(
                            distances.loc[
                                nearest_index
                            ]
                        )
                    ),
            }
        )

    return pd.DataFrame(matches)


# ============================================================
# MATCHED RESULTS
# ============================================================

def print_matched_results(matches):

    print_header(
        "4. MATCHED STRONG BUY vs BUY"
    )

    if matches.empty:
        print("No matched observations.")
        return

    strong_mean = (
        matches["strong_buy_return_5d"].mean()
    )

    buy_mean = (
        matches["buy_return_5d"].mean()
    )

    strong_median = (
        matches["strong_buy_return_5d"].median()
    )

    buy_median = (
        matches["buy_return_5d"].median()
    )

    incremental = (
        matches["strong_buy_return_5d"]
        - matches["buy_return_5d"]
    )

    print(
        f"Matched STRONG BUY observations: "
        f"{len(matches)}"
    )

    print()

    print(
        f"STRONG BUY mean 5D: "
        f"{strong_mean:.4f}%"
    )

    print(
        f"Matched BUY mean 5D: "
        f"{buy_mean:.4f}%"
    )

    print(
        f"Incremental mean 5D: "
        f"{incremental.mean():.4f}%"
    )

    print()

    print(
        f"STRONG BUY median 5D: "
        f"{strong_median:.4f}%"
    )

    print(
        f"Matched BUY median 5D: "
        f"{buy_median:.4f}%"
    )

    print(
        f"Incremental median 5D: "
        f"{incremental.median():.4f}%"
    )

    print()

    print(
        f"STRONG BUY beat BUY: "
        f"{(incremental > 0).mean() * 100:.2f}%"
    )

    print(
        f"STRONG BUY tied BUY: "
        f"{(incremental == 0).mean() * 100:.2f}%"
    )

    print(
        f"STRONG BUY lost to BUY: "
        f"{(incremental < 0).mean() * 100:.2f}%"
    )

    print()

    print(
        "Mean match distance: "
        f"{matches['match_distance'].mean():.4f}"
    )

    print(
        "Median match distance: "
        f"{matches['match_distance'].median():.4f}"
    )


# ============================================================
# MATCHED RESULTS BY ENTRY QUALITY
# ============================================================

def print_matched_entry_quality(matches):

    print_header(
        "5. MATCHED RESULTS BY ENTRY QUALITY"
    )

    if matches.empty:
        print("No matched observations.")
        return

    matches = matches.copy()

    matches["incremental_5d"] = (
        matches["strong_buy_return_5d"]
        - matches["buy_return_5d"]
    )

    result = (
        matches.groupby(
            "strong_buy_entry_quality",
            dropna=False,
        )
        .agg(
            n=("incremental_5d", "count"),
            strong_buy_mean_5d=(
                "strong_buy_return_5d",
                "mean",
            ),
            matched_buy_mean_5d=(
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
                lambda s: (s > 0).mean() * 100,
            ),
        )
        .reset_index()
    )

    print(result.to_string(index=False))


# ============================================================
# MATCH QUALITY
# ============================================================

def print_match_quality(matches):

    print_header(
        "6. MATCH QUALITY"
    )

    if matches.empty:
        print("No matched observations.")
        return

    result = (
        matches.groupby(
            "strong_buy_entry_quality",
            dropna=False,
        )
        .agg(
            n=("match_distance", "count"),
            mean_distance=(
                "match_distance",
                "mean",
            ),
            median_distance=(
                "match_distance",
                "median",
            ),
            max_distance=(
                "match_distance",
                "max",
            ),
        )
        .reset_index()
    )

    print(result.to_string(index=False))


# ============================================================
# STRONG BUY WINNERS / LOSERS
# ============================================================

def print_winners_losers(frame):

    print_header(
        "7. STRONG BUY WINNERS vs LOSERS"
    )

    strong_buy = frame[
        frame["original_signal"] == "STRONG BUY"
    ].copy()

    if strong_buy.empty:
        print("No STRONG BUY observations.")
        return

    strong_buy["outcome"] = np.where(
        strong_buy["return_5d"] > 0,
        "WINNER",
        "LOSER",
    )

    result = (
        strong_buy.groupby(
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


# ============================================================
# TELEMETRY COVERAGE
# ============================================================

def print_coverage(frame):

    print_header(
        "8. TELEMETRY COVERAGE"
    )

    print(
        "BUY / STRONG BUY decisions with mature "
        f"{HORIZON}D outcome: {len(frame)}"
    )

    for column in [
        "investment_score",
        "evidence_score",
        "confidence_score",
        "technical_score",
        "quality_score",
        "growth_score",
        "entry_quality",
    ]:

        if column not in frame.columns:
            continue

        count = (
            frame[column]
            .notna()
            .sum()
        )

        pct = (
            count / len(frame) * 100
            if len(frame)
            else 0
        )

        print(
            f"{column}: "
            f"{count} "
            f"({pct:.2f}%)"
        )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 76)
    print("STRONG BUY vs BUY MATCHED FORENSICS")
    print("=" * 76)
    print()
    print(
        "READ-ONLY — NO PRODUCTION CHANGES"
    )
    print()

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
        f"BUY / STRONG BUY audit decisions "
        f"with mature {HORIZON}D outcome: "
        f"{len(frame)}"
    )

    print_baseline(frame)

    print_entry_quality(frame)

    print_entry_quality_counts(frame)

    matches = build_matches(frame)

    print_matched_results(matches)

    print_matched_entry_quality(matches)

    print_match_quality(matches)

    print_winners_losers(frame)

    print_coverage(frame)

    print()
    print("=" * 76)
    print("END — READ-ONLY ANALYSIS")
    print("=" * 76)
    print()


if __name__ == "__main__":
    main()
