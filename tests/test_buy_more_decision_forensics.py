"""
Non-production forensic analysis of BUY MORE decisions.

This test is READ-ONLY.

Purpose
-------
Determine whether BUY MORE decisions add incremental value relative
to comparable decisions that were proposed as BUY MORE but ultimately
became HOLD.

This does NOT:
- modify production logic
- modify governance
- modify thresholds
- modify the database
- modify reports

Historical audit decisions whose recommendation_id is NULL are linked
to the latest recommendation for the same ticker on or before the
audit date, consistent with the existing forensic lineage approach.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd


DB_PATH = Path("data/portfolio_manager.db")

HORIZON = 5

EXCLUDED_TICKERS = {"TESTBUYMORE"}
EXCLUDED_ASSET_TYPES = {"ETF"}

MATCH_COLUMNS = [
    "investment_score",
    "evidence_score",
    "confidence_score",
    "technical_score",
    "quality_score",
    "growth_score",
]

MAX_MATCHES_PER_BUY_MORE = 3
MAX_MATCH_DISTANCE = 2.5


def safe_float(value):
    try:
        if value is None or pd.isna(value):
            return np.nan
        return float(value)
    except (TypeError, ValueError):
        return np.nan


def normalise_day(value):
    try:
        return pd.to_datetime(value, utc=True).date()
    except Exception:
        return None


def format_pct(value):
    if pd.isna(value):
        return "n/a"
    return f"{value:.2f}%"


def print_outcome_summary(label, frame):
    print(f"\n{label}")
    print("-" * len(label))

    if frame.empty:
        print("No data")
        return

    print(f"Decisions:   {len(frame)}")
    print(f"Mean 5D:     {format_pct(frame['return_5d'].mean())}")
    print(f"Median 5D:   {format_pct(frame['return_5d'].median())}")
    print(
        f"Positive 5D: "
        f"{frame['return_5d'].gt(0).mean() * 100:.2f}%"
    )


def load_audit_decisions(conn):
    return pd.read_sql_query(
        """
        SELECT
            id AS audit_decision_id,
            audit_run_id,
            ticker,
            asset_type,
            created_at,
            original_action,
            proposed_action,
            reconciled_action,
            final_action,
            action_changed,
            original_signal,
            investment_score,
            technical_score,
            quality_score,
            growth_score,
            confidence_score,
            evidence_score,
            original_allocation_pct,
            final_allocation_pct,
            recommendation_id
        FROM audit_decisions
        WHERE proposed_action = 'BUY MORE'
        ORDER BY created_at, id
        """,
        conn,
    )


def load_recommendations(conn):
    frame = pd.read_sql_query(
        """
        SELECT
            id AS recommendation_id,
            date AS recommendation_date,
            ticker,
            signal,
            price AS recommendation_price
        FROM recommendations
        ORDER BY ticker, date, id
        """,
        conn,
    )

    frame["recommendation_day"] = (
        pd.to_datetime(
            frame["recommendation_date"],
            errors="coerce",
            utc=True,
        ).dt.date
    )

    return frame[
        frame["recommendation_day"].notna()
    ].copy()


def reconstruct_lineage(decisions, recommendations):
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

        ticker = decision["ticker"]
        candidates = recommendations_by_ticker.get(ticker)

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


def load_5d_evaluations(conn):
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
    decisions = decisions.copy()

    evaluations = (
        evaluations
        .sort_values(
            ["recommendation_id", "evaluation_date"]
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


def clean_population(decisions):
    frame = decisions.copy()

    frame["ticker"] = (
        frame["ticker"]
        .fillna("")
        .astype(str)
        .str.upper()
        .str.strip()
    )

    frame["asset_type"] = (
        frame["asset_type"]
        .fillna("")
        .astype(str)
        .str.upper()
        .str.strip()
    )

    raw_count = len(frame)

    frame = frame[
        ~frame["ticker"].isin(EXCLUDED_TICKERS)
    ]

    frame = frame[
        ~frame["asset_type"].isin(EXCLUDED_ASSET_TYPES)
    ]

    frame = frame[
        frame["return_5d"].notna()
    ].copy()

    print("\nPOPULATION")
    print("----------")
    print(f"Raw BUY MORE proposals: {raw_count}")
    print(f"With realised 5D outcome: {len(frame)}")
    print(
        f"Excluded / unrealised: "
        f"{raw_count - len(frame)}"
    )

    return frame


def identify_exact_duplicates(decisions):
    frame = decisions.copy()

    frame["exact_duplicate"] = frame.duplicated(
        subset=[
            "ticker",
            "created_at",
            "original_signal",
            "final_action",
        ],
        keep="first",
    )

    print("\nDUPLICATE CHECK")
    print("---------------")
    print(
        "Exact duplicate executions: "
        f"{int(frame['exact_duplicate'].sum())}"
    )

    return frame


def signal_analysis(decisions):
    print("\n" + "=" * 72)
    print("SIGNAL × FINAL ACTION")
    print("=" * 72)

    grouped = (
        decisions
        .groupby(
            ["original_signal", "final_action"],
            dropna=False,
        )
        .agg(
            decisions=("ticker", "size"),
            mean_5d=("return_5d", "mean"),
            median_5d=("return_5d", "median"),
            positive_5d=(
                "return_5d",
                lambda s: s.gt(0).mean() * 100,
            ),
        )
        .reset_index()
    )

    print(grouped.to_string(index=False))


def add_score_bands(decisions):
    frame = decisions.copy()

    bands = {
        "investment_score":
            [0, 60, 70, 75, 80, 85, 101],
        "evidence_score":
            [0, 50, 60, 65, 70, 75, 101],
        "confidence_score":
            [0, 50, 60, 70, 80, 90, 101],
        "technical_score":
            [0, 60, 70, 75, 80, 85, 101],
        "quality_score":
            [0, 50, 60, 70, 75, 80, 101],
        "growth_score":
            [0, 50, 70, 80, 90, 100, 101],
    }

    for column, edges in bands.items():
        frame[column] = pd.to_numeric(
            frame[column],
            errors="coerce",
        )

        frame[f"{column}_band"] = pd.cut(
            frame[column],
            bins=edges,
            right=False,
            include_lowest=True,
        )

    return frame


def score_band_analysis(decisions):
    print("\n" + "=" * 72)
    print("SCORE BAND ANALYSIS")
    print("=" * 72)

    for column in MATCH_COLUMNS:

        band_column = f"{column}_band"

        grouped = (
            decisions
            .groupby(
                [band_column, "final_action"],
                observed=False,
            )
            .agg(
                decisions=("ticker", "size"),
                mean_5d=("return_5d", "mean"),
                median_5d=("return_5d", "median"),
                positive_5d=(
                    "return_5d",
                    lambda s: s.gt(0).mean() * 100,
                ),
            )
            .reset_index()
        )

        grouped = grouped[
            grouped["decisions"] >= 3
        ]

        print(f"\n{column.upper()}")
        print("-" * len(column))
        print(grouped.to_string(index=False))


def standardise_features(frame):
    frame = frame.copy()

    for column in MATCH_COLUMNS:
        median = frame[column].median()
        std = frame[column].std()

        if pd.isna(std) or std == 0:
            std = 1.0

        frame[f"{column}_z"] = (
            frame[column] - median
        ) / std

    return frame


def match_buy_more_to_hold(decisions):
    frame = decisions.copy()

    for column in MATCH_COLUMNS:
        frame[column] = pd.to_numeric(
            frame[column],
            errors="coerce",
        )

    frame = standardise_features(frame)

    buy_more = frame[
        frame["final_action"] == "BUY MORE"
    ]

    hold = frame[
        frame["final_action"] == "HOLD"
    ]

    matches = []

    for _, buy_more_row in buy_more.iterrows():

        # Same underlying signal is required.
        candidates = hold[
            hold["original_signal"]
            == buy_more_row["original_signal"]
        ]

        if candidates.empty:
            continue

        distances = []

        for _, hold_row in candidates.iterrows():

            squared_distance = 0.0
            usable_features = 0

            for column in MATCH_COLUMNS:

                a = buy_more_row[f"{column}_z"]
                b = hold_row[f"{column}_z"]

                if pd.isna(a) or pd.isna(b):
                    continue

                squared_distance += (a - b) ** 2
                usable_features += 1

            if usable_features == 0:
                continue

            distance = float(
                np.sqrt(squared_distance)
            )

            distances.append(
                (distance, hold_row)
            )

        distances.sort(
            key=lambda item: item[0]
        )

        matched = 0

        for distance, hold_row in distances:

            if distance > MAX_MATCH_DISTANCE:
                continue

            matches.append(
                {
                    "buy_more_audit_id":
                        buy_more_row["audit_decision_id"],
                    "buy_more_ticker":
                        buy_more_row["ticker"],
                    "buy_more_signal":
                        buy_more_row["original_signal"],
                    "buy_more_return":
                        buy_more_row["return_5d"],
                    "hold_audit_id":
                        hold_row["audit_decision_id"],
                    "hold_ticker":
                        hold_row["ticker"],
                    "hold_return":
                        hold_row["return_5d"],
                    "distance":
                        distance,
                }
            )

            matched += 1

            if matched >= MAX_MATCHES_PER_BUY_MORE:
                break

    return pd.DataFrame(matches)


def matched_analysis(matches, label):
    print("\n" + "=" * 72)
    print(label)
    print("=" * 72)

    if matches.empty:
        print("No matched observations.")
        return

    matches = matches.copy()

    matches["incremental_return"] = (
        matches["buy_more_return"]
        - matches["hold_return"]
    )

    print(f"Matched pairs: {len(matches)}")
    print(
        "BUY MORE mean 5D: "
        f"{format_pct(matches['buy_more_return'].mean())}"
    )
    print(
        "HOLD mean 5D:     "
        f"{format_pct(matches['hold_return'].mean())}"
    )
    print(
        "Incremental mean: "
        f"{format_pct(matches['incremental_return'].mean())}"
    )
    print(
        "Incremental median: "
        f"{format_pct(matches['incremental_return'].median())}"
    )
    print(
        "BUY MORE beat HOLD: "
        f"{matches['incremental_return'].gt(0).mean() * 100:.2f}%"
    )

    print("\nBY SIGNAL")
    print("---------")

    grouped = (
        matches
        .groupby("buy_more_signal")
        .agg(
            matches=("incremental_return", "size"),
            buy_more_mean=(
                "buy_more_return",
                "mean",
            ),
            hold_mean=(
                "hold_return",
                "mean",
            ),
            incremental_mean=(
                "incremental_return",
                "mean",
            ),
            incremental_median=(
                "incremental_return",
                "median",
            ),
            buy_more_beats_hold=(
                "incremental_return",
                lambda s: s.gt(0).mean() * 100,
            ),
        )
        .reset_index()
    )

    print(grouped.to_string(index=False))

    close = matches[
        matches["distance"] <= 1.5
    ]

    print("\nCLOSE MATCHES (DISTANCE <= 1.5)")
    print("------------------------------")

    if close.empty:
        print("No close matches.")
    else:
        print(f"Close matches: {len(close)}")
        print(
            "Incremental mean: "
            f"{format_pct(close['incremental_return'].mean())}"
        )
        print(
            "Incremental median: "
            f"{format_pct(close['incremental_return'].median())}"
        )
        print(
            "BUY MORE beat HOLD: "
            f"{close['incremental_return'].gt(0).mean() * 100:.2f}%"
        )


def rejection_analysis(decisions, conn):
    print("\n" + "=" * 72)
    print("BUY MORE → HOLD GOVERNANCE REASONS")
    print("=" * 72)

    hold_ids = decisions.loc[
        decisions["final_action"] == "HOLD",
        "audit_decision_id",
    ].tolist()

    if not hold_ids:
        print("No HOLD decisions.")
        return

    placeholders = ",".join(
        "?" for _ in hold_ids
    )

    reasons = pd.read_sql_query(
        f"""
        SELECT
            audit_decision_id,
            reason_code
        FROM audit_reasons
        WHERE audit_decision_id IN ({placeholders})
        """,
        conn,
        params=hold_ids,
    )

    ignored = {
        "GOVERNANCE_REASON",
        "ACTION_CHANGED",
        "MARKET_INTELLIGENCE_SNAPSHOT",
        "GOVERNANCE_FLAG_DETERMINISTIC_GOVERNANCE_AUTHORITATIVE",
        "GOVERNANCE_FLAG_BUY_MORE_GOVERNANCE_REQUIREMENTS_NOT_MET",
        "GOVERNANCE_FLAG_LLM_CHALLENGE_ADVISORY_ONLY",
        "GOVERNANCE_FLAG_LLM_ADVISORY_ACCEPT",
        "GOVERNANCE_FLAG_LLM_ADVISORY_CHALLENGE",
        "GOVERNANCE_FLAG_LOW_LLM_CONFIDENCE_ADVISORY_ONLY",
    }

    reasons = reasons[
        ~reasons["reason_code"].isin(ignored)
    ]

    grouped = (
        reasons
        .groupby("reason_code")
        .size()
        .sort_values(ascending=False)
    )

    if grouped.empty:
        print("No substantive governance reasons found.")
    else:
        print(grouped.to_string())


def main():
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database not found: {DB_PATH}"
        )

    print("=" * 72)
    print("BUY MORE DECISION FORENSICS")
    print("=" * 72)
    print("READ-ONLY — NO PRODUCTION CHANGES")

    with sqlite3.connect(DB_PATH) as conn:

        decisions = load_audit_decisions(conn)
        recommendations = load_recommendations(conn)
        evaluations = load_5d_evaluations(conn)

        print(
            f"\nRaw BUY MORE audit proposals: "
            f"{len(decisions)}"
        )

        decisions = reconstruct_lineage(
            decisions,
            recommendations,
        )

        print(
            "Direct lineage: "
            f"{decisions['recommendation_id'].notna().sum()}"
        )

        print(
            "Reconstructed legacy lineage: "
            f"{(
                decisions['recommendation_id'].isna()
                & decisions['lineage_recommendation_id'].notna()
            ).sum()}"
        )

        decisions = attach_outcomes(
            decisions,
            evaluations,
        )

        decisions = clean_population(
            decisions
        )

        decisions = identify_exact_duplicates(
            decisions
        )

        print_outcome_summary(
            "FINAL BUY MORE",
            decisions[
                decisions["final_action"] == "BUY MORE"
            ],
        )

        print_outcome_summary(
            "FINAL HOLD",
            decisions[
                decisions["final_action"] == "HOLD"
            ],
        )

        signal_analysis(decisions)

        decisions = add_score_bands(
            decisions
        )

        score_band_analysis(
            decisions
        )

        rejection_analysis(
            decisions,
            conn,
        )

        full_matches = match_buy_more_to_hold(
            decisions
        )

        matched_analysis(
            full_matches,
            "MATCHED BUY MORE VS HOLD — FULL POPULATION",
        )

        deduped = decisions[
            ~decisions["exact_duplicate"]
        ].copy()

        deduped_matches = match_buy_more_to_hold(
            deduped
        )

        matched_analysis(
            deduped_matches,
            "MATCHED BUY MORE VS HOLD — DUPLICATES REMOVED",
        )


if __name__ == "__main__":
    main()
