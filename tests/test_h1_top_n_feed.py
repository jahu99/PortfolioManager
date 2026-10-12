"""
Read-only diagnostic: H1 impact on the top-N candidate feed.

Compares:

Baseline:
    Investment Score
    -> Technical Score
    -> Quality Score
    -> Growth Score
    -> Confidence Score

Experimental:
    Investment Score
    -> H1
    -> Technical Score
    -> Quality Score
    -> Growth Score
    -> Confidence Score

H1 is therefore tested only as a secondary tie-break within the
existing Investment Score ranking.

No production logic is changed.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DB_PATH = (
    PROJECT_ROOT
    / "data"
    / "portfolio_manager.db"
)

TOP_N = [5, 10, 20, 30]

H1_RULES = {
    "RSI>=55_3M<=15": (55.0, 15.0),
    "RSI>=55_3M<=20": (55.0, 20.0),
    "RSI>=55_3M<=25": (55.0, 25.0),
}

ENTRY_QUALITY_ALLOWED = {
    "FAVOURABLE",
    "FAVOURABLE ENTRY",
    "REASONABLE",
}


def load_data() -> pd.DataFrame:

    query = """
        SELECT
            re.recommendation_id,
            re.capture_date,
            re.ticker,
            re.signal,

            re.investment_score,
            re.technical_score,
            re.quality_score,
            re.growth_score,
            re.confidence_score,

            re.rsi,
            re.return_3m,

            re.return_5d_pct,
            re.return_10d_pct,
            re.return_20d_pct,

            re.entry_quality

        FROM recommendation_evidence re

        INNER JOIN recommendations r
            ON r.id = re.recommendation_id

        WHERE
            UPPER(COALESCE(re.signal, ''))
                IN ('BUY', 'STRONG BUY')
    """

    with sqlite3.connect(DB_PATH) as connection:
        df = pd.read_sql_query(
            query,
            connection,
        )

    numeric = [
        "investment_score",
        "technical_score",
        "quality_score",
        "growth_score",
        "confidence_score",
        "rsi",
        "return_3m",
        "return_5d_pct",
        "return_10d_pct",
        "return_20d_pct",
    ]

    for column in numeric:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

    df["capture_date"] = pd.to_datetime(
        df["capture_date"],
        errors="coerce",
    )

    df["entry_quality_clean"] = (
        df["entry_quality"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
    )

    df = df[
        df["entry_quality_clean"].isin(
            ENTRY_QUALITY_ALLOWED
        )
    ].copy()

    # Immutable recommendation-level lineage.
    df = (
        df
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
        .reset_index(drop=True)
    )

    df = df.dropna(
        subset=[
            "investment_score",
            "technical_score",
            "quality_score",
            "growth_score",
            "confidence_score",
            "rsi",
            "return_3m",
        ]
    ).copy()

    return df


def add_h1(
    df: pd.DataFrame,
    rsi_threshold: float,
    return_3m_max: float,
) -> pd.DataFrame:

    result = df.copy()

    result["H1"] = (
        (result["rsi"] >= rsi_threshold)
        &
        (result["return_3m"] <= return_3m_max)
    )

    return result


def rank_baseline(
    df: pd.DataFrame,
) -> pd.DataFrame:

    return (
        df
        .sort_values(
            [
                "investment_score",
                "technical_score",
                "quality_score",
                "growth_score",
                "confidence_score",
                "ticker",
                "recommendation_id",
            ],
            ascending=False,
        )
        .reset_index(drop=True)
    )


def rank_h1(
    df: pd.DataFrame,
) -> pd.DataFrame:

    return (
        df
        .sort_values(
            [
                "investment_score",
                "H1",
                "technical_score",
                "quality_score",
                "growth_score",
                "confidence_score",
                "ticker",
                "recommendation_id",
            ],
            ascending=False,
        )
        .reset_index(drop=True)
    )


def calculate_metrics(
    df: pd.DataFrame,
) -> dict:

    metrics = {}

    for horizon in [
        "return_5d_pct",
        "return_10d_pct",
        "return_20d_pct",
    ]:

        values = df[horizon].dropna()

        if values.empty:
            metrics[horizon] = {
                "n": 0,
                "mean": np.nan,
                "positive": np.nan,
            }
            continue

        metrics[horizon] = {
            "n": len(values),
            "mean": values.mean(),
            "positive": (
                (values > 0).mean() * 100
            ),
        }

    return metrics


def print_comparison(
    baseline: pd.DataFrame,
    experimental: pd.DataFrame,
    rule_name: str,
) -> None:

    print()
    print("=" * 100)
    print(f"H1 TOP-N FEED TEST: {rule_name}")
    print("=" * 100)

    for n in TOP_N:

        base_top = baseline.head(n)
        h1_top = experimental.head(n)

        print()
        print(f"TOP {n}")
        print("-" * 100)

        base_metrics = calculate_metrics(
            base_top
        )

        h1_metrics = calculate_metrics(
            h1_top
        )

        print(
            f"  Baseline H1 count: "
            f"{int(base_top['H1'].sum())}/{n}"
        )

        print(
            f"  Experimental H1 count: "
            f"{int(h1_top['H1'].sum())}/{n}"
        )

        for horizon in [
            "return_5d_pct",
            "return_10d_pct",
            "return_20d_pct",
        ]:

            base = base_metrics[horizon]
            exp = h1_metrics[horizon]

            if base["n"] == 0 or exp["n"] == 0:
                continue

            delta = (
                exp["mean"]
                - base["mean"]
            )

            positive_delta = (
                exp["positive"]
                - base["positive"]
            )

            print(
                f"  {horizon}: "
                f"baseline "
                f"{base['mean']:+.3f}% "
                f"({base['positive']:.1f}% positive) "
                f"| H1 "
                f"{exp['mean']:+.3f}% "
                f"({exp['positive']:.1f}% positive) "
                f"| delta "
                f"{delta:+.3f}pp "
                f"| positive delta "
                f"{positive_delta:+.1f}pp"
            )


def print_rank_changes(
    baseline: pd.DataFrame,
    experimental: pd.DataFrame,
) -> None:

    print()
    print("=" * 100)
    print("TOP-20 RANK CHANGES")
    print("=" * 100)

    base_rank = {
        row.recommendation_id: index + 1
        for index, row
        in baseline.head(20).iterrows()
    }

    exp_rank = {
        row.recommendation_id: index + 1
        for index, row
        in experimental.head(20).iterrows()
    }

    ids = set(base_rank) | set(exp_rank)

    rows = []

    for recommendation_id in ids:

        base = base_rank.get(
            recommendation_id
        )

        exp = exp_rank.get(
            recommendation_id
        )

        row = (
            experimental[
                experimental[
                    "recommendation_id"
                ]
                == recommendation_id
            ]
            .iloc[0]
        )

        rows.append(
            {
                "ticker": row["ticker"],
                "investment_score": row[
                    "investment_score"
                ],
                "H1": bool(row["H1"]),
                "baseline_rank": base,
                "H1_rank": exp,
            }
        )

    result = pd.DataFrame(rows)

    if result.empty:
        return

    result["rank_change"] = (
        result["baseline_rank"].fillna(999)
        -
        result["H1_rank"].fillna(999)
    )

    result = result.sort_values(
        "rank_change",
        ascending=False,
    )

    print(
        result.to_string(
            index=False
        )
    )


def main() -> None:

    print()
    print("=" * 100)
    print("H1 IMPACT ON TOP-N CANDIDATE FEED")
    print("=" * 100)

    print()
    print(
        f"Database: {DB_PATH}"
    )

    df = load_data()

    print()
    print(
        f"Unique usable recommendation snapshots: "
        f"{len(df)}"
    )

    print(
        f"Unique tickers: "
        f"{df['ticker'].nunique()}"
    )

    print(
        f"Date range: "
        f"{df['capture_date'].min().date()} "
        f"→ "
        f"{df['capture_date'].max().date()}"
    )

    if df.empty:
        raise RuntimeError(
            "No usable recommendation observations."
        )

    for rule_name, rule in H1_RULES.items():

        rsi_threshold, return_3m_max = rule

        test_df = add_h1(
            df,
            rsi_threshold,
            return_3m_max,
        )

        baseline = rank_baseline(
            test_df
        )

        experimental = rank_h1(
            test_df
        )

        print_comparison(
            baseline,
            experimental,
            rule_name,
        )

        print_rank_changes(
            baseline,
            experimental,
        )

    print()
    print("=" * 100)
    print("ASSESSMENT")
    print("=" * 100)

    print()
    print(
        "READ-ONLY diagnostic only."
    )

    print(
        "No production scoring or ranking logic "
        "has been changed."
    )

    print()
    print(
        "The experimental ranking keeps Investment Score "
        "as the primary ranking key and uses H1 only "
        "as a secondary tie-break."
    )

    print()
    print(
        "This test is intended to determine whether that "
        "small ranking change improves the actual top-N feed."
    )

    print()


if __name__ == "__main__":
    main()
