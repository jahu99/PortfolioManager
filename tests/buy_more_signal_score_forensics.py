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

    return decisions, recommendations, evaluations


def reconstruct_lineage(
    decisions,
    recommendations,
    evaluations,
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

    for column in SCORES:
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


def section_signal_regime(frame):
    print_header(1, "BUY VS STRONG BUY — FULL REGIME")

    result = (
        frame
        .groupby(
            "original_signal",
            dropna=False,
        )
        .agg(
            n=("ticker", "size"),
            mean_5d=("return_5d", "mean"),
            median_5d=("return_5d", "median"),
            positive_5d=(
                "return_5d",
                lambda s: s.gt(0).mean() * 100,
            ),
            mean_investment=(
                "investment_score",
                "mean",
            ),
            mean_evidence=(
                "evidence_score",
                "mean",
            ),
            mean_confidence=(
                "confidence_score",
                "mean",
            ),
            mean_technical=(
                "technical_score",
                "mean",
            ),
            mean_quality=(
                "quality_score",
                "mean",
            ),
            mean_growth=(
                "growth_score",
                "mean",
            ),
        )
        .reset_index()
    )

    print(result.to_string(index=False))


def actual_score_analysis(
    frame,
    score,
):
    result = (
        frame
        .groupby(
            score,
            dropna=False,
        )
        .agg(
            n=("ticker", "size"),
            mean_5d=("return_5d", "mean"),
            median_5d=("return_5d", "median"),
            positive_5d=(
                "return_5d",
                lambda s: s.gt(0).mean() * 100,
            ),
        )
        .reset_index()
    )

    result = result[
        result["n"] >= MIN_GROUP_SIZE
    ]

    return result


def section_actual_scores(frame):
    print_header(2, "ACTUAL SCORE VALUES")

    for score in SCORES:

        print(f"\n{score.upper()}")
        print("-" * len(score))

        result = actual_score_analysis(
            frame,
            score,
        )

        print(
            result.to_string(
                index=False
            )
        )


def section_investment_by_signal(frame):
    print_header(
        3,
        "SIGNAL × ACTUAL INVESTMENT SCORE",
    )

    result = (
        frame
        .groupby(
            [
                "original_signal",
                "investment_score",
            ],
            dropna=False,
        )
        .agg(
            n=("ticker", "size"),
            mean_5d=("return_5d", "mean"),
            median_5d=("return_5d", "median"),
            positive_5d=(
                "return_5d",
                lambda s: s.gt(0).mean() * 100,
            ),
        )
        .reset_index()
    )

    result = result[
        result["n"] >= MIN_GROUP_SIZE
    ]

    print(
        result.to_string(index=False)
    )


def band(value, score_name):
    """
    Use practical analytical bands where the score distribution
    contains many repeated integer values.

    These are analytical bands, not production thresholds.
    """

    if score_name == "investment_score":
        return pd.cut(
            [value],
            bins=[-np.inf, 75, 77, 79, np.inf],
            labels=[
                "<=75",
                "76-77",
                "78-79",
                "80+",
            ],
        )[0]

    if score_name == "confidence_score":
        return pd.cut(
            [value],
            bins=[-np.inf, 75, 80, 85, 90, np.inf],
            labels=[
                "<=75",
                "76-80",
                "81-85",
                "86-90",
                "91+",
            ],
        )[0]

    if score_name == "evidence_score":
        return pd.cut(
            [value],
            bins=[-np.inf, 65, 70, 75, np.inf],
            labels=[
                "<=65",
                "66-70",
                "71-75",
                "76+",
            ],
        )[0]

    if score_name == "technical_score":
        return pd.cut(
            [value],
            bins=[-np.inf, 70, 75, 80, np.inf],
            labels=[
                "<=70",
                "71-75",
                "76-80",
                "81+",
            ],
        )[0]

    if score_name == "quality_score":
        return pd.cut(
            [value],
            bins=[-np.inf, 60, 65, 70, 75, np.inf],
            labels=[
                "<=60",
                "61-65",
                "66-70",
                "71-75",
                "76+",
            ],
        )[0]

    if score_name == "growth_score":
        return pd.cut(
            [value],
            bins=[-np.inf, 80, 85, 90, 95, np.inf],
            labels=[
                "<=80",
                "81-85",
                "86-90",
                "91-95",
                "96+",
            ],
        )[0]

    return "UNKNOWN"

def section_signal_score_bands(frame):
    print_header(
        4,
        "SIGNAL × SCORE BANDS",
    )

    for score in SCORES:

        temp = frame.copy()

        temp["_band"] = temp[score].apply(
            lambda value: band(value, score)
        )

        result = (
            temp
            .groupby(
                [
                    "original_signal",
                    "_band",
                ],
                observed=False,
                dropna=False,
            )
            .agg(
                n=("ticker", "size"),
                mean_5d=("return_5d", "mean"),
                median_5d=(
                    "return_5d",
                    "median",
                ),
                positive_5d=(
                    "return_5d",
                    lambda s:
                        s.gt(0).mean() * 100,
                ),
            )
            .reset_index()
        )

        result = result[
            result["n"] >= MIN_GROUP_SIZE
        ]

        print(f"\n{score.upper()}")
        print("-" * len(score))

        print(
            result.to_string(
                index=False
            )
        )


def section_strong_buy_profile(frame):
    print_header(
        5,
        "STRONG BUY PROFILE VS BUY PROFILE",
    )

    buy = frame[
        frame["original_signal"] == "BUY"
    ]

    strong = frame[
        frame["original_signal"]
        == "STRONG BUY"
    ]

    rows = []

    for score in SCORES:

        rows.append(
            {
                "score": score,
                "BUY_mean":
                    buy[score].mean(),
                "STRONG_BUY_mean":
                    strong[score].mean(),
                "difference":
                    strong[score].mean()
                    - buy[score].mean(),
            }
        )

    result = pd.DataFrame(rows)

    print(
        result.to_string(
            index=False
        )
    )

    print("\nSTRONG BUY RETURN DISTRIBUTION")

    print(
        strong[
            "return_5d"
        ].describe().to_string()
    )

    print("\nBUY RETURN DISTRIBUTION")

    print(
        buy[
            "return_5d"
        ].describe().to_string()
    )


def section_quality_deep_dive(frame):
    print_header(
        6,
        "QUALITY SCORE DEEP DIVE",
    )

    result = (
        frame
        .groupby(
            [
                "original_signal",
                "quality_score",
            ],
            dropna=False,
        )
        .agg(
            n=("ticker", "size"),
            mean_5d=("return_5d", "mean"),
            median_5d=(
                "return_5d",
                "median",
            ),
            positive_5d=(
                "return_5d",
                lambda s:
                    s.gt(0).mean() * 100,
            ),
            mean_growth=(
                "growth_score",
                "mean",
            ),
            mean_technical=(
                "technical_score",
                "mean",
            ),
            mean_investment=(
                "investment_score",
                "mean",
            ),
        )
        .reset_index()
    )

    result = result[
        result["n"] >= MIN_GROUP_SIZE
    ]

    print(
        result.to_string(
            index=False
        )
    )


def section_temporal(frame):
    print_header(
        7,
        "TEMPORAL STABILITY",
    )

    frame = frame.sort_values(
        "decision_date"
    )

    if len(frame) < 40:
        print(
            "Insufficient data."
        )
        return

    midpoint = len(frame) // 2

    periods = {
        "EARLY":
            frame.iloc[:midpoint],
        "LATE":
            frame.iloc[midpoint:],
    }

    rows = []

    for period_name, period in periods.items():

        for signal in [
            "BUY",
            "STRONG BUY",
        ]:

            subset = period[
                period["original_signal"]
                == signal
            ]

            if subset.empty:
                continue

            rows.append(
                {
                    "period":
                        period_name,
                    "signal":
                        signal,
                    "n":
                        len(subset),
                    "start":
                        subset[
                            "decision_date"
                        ].min(),
                    "end":
                        subset[
                            "decision_date"
                        ].max(),
                    "mean_5d":
                        subset[
                            "return_5d"
                        ].mean(),
                    "median_5d":
                        subset[
                            "return_5d"
                        ].median(),
                    "positive_5d":
                        subset[
                            "return_5d"
                        ].gt(0).mean()
                        * 100,
                }
            )

    print(
        pd.DataFrame(rows).to_string(
            index=False
        )
    )


def section_accepted_rejected(frame):
    print_header(
        8,
        "ACCEPTED VS REJECTED — SAME SIGNAL",
    )

    result = (
        frame
        .groupby(
            [
                "original_signal",
                "final_action",
            ],
            dropna=False,
        )
        .agg(
            n=("ticker", "size"),
            mean_5d=("return_5d", "mean"),
            median_5d=(
                "return_5d",
                "median",
            ),
            positive_5d=(
                "return_5d",
                lambda s:
                    s.gt(0).mean() * 100,
            ),
            investment=(
                "investment_score",
                "mean",
            ),
            evidence=(
                "evidence_score",
                "mean",
            ),
            confidence=(
                "confidence_score",
                "mean",
            ),
            technical=(
                "technical_score",
                "mean",
            ),
            quality=(
                "quality_score",
                "mean",
            ),
            growth=(
                "growth_score",
                "mean",
            ),
        )
        .reset_index()
    )

    print(
        result.to_string(index=False)
    )


def main():

    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database not found: {DB_PATH}"
        )

    print("=" * 76)
    print(
        "BUY MORE SIGNAL / SCORE FORENSICS"
    )
    print("=" * 76)
    print(
        "READ-ONLY — NO PRODUCTION CHANGES"
    )

    with sqlite3.connect(DB_PATH) as conn:

        decisions, recommendations, evaluations = (
            load_data(conn)
        )

        frame = reconstruct_lineage(
            decisions,
            recommendations,
            evaluations,
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
        f"Rejected BUY MORE → HOLD: "
        f"{len(rejected)}"
    )

    section_signal_regime(accepted)

    section_actual_scores(accepted)

    section_investment_by_signal(
        accepted
    )

    section_signal_score_bands(
        accepted
    )

    section_strong_buy_profile(
        accepted
    )

    section_quality_deep_dive(
        accepted
    )

    section_temporal(
        accepted
    )

    section_accepted_rejected(
        frame
    )


if __name__ == "__main__":
    main()
