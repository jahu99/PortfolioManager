"""
STRONG BUY rule forensic analysis.

READ-ONLY — NO PRODUCTION CHANGES.

Investigates the realised 5D performance of the actual STRONG BUY
rule components:

    Investment Score >= 80
    Technical Score >= 75
    Quality Score >= 60
    Price > SMA200
    RSI 40-75

The analysis examines:
    - RSI bands
    - distance above SMA200
    - Investment Score bands
    - Technical Score bands
    - Quality Score bands
    - Entry Quality
    - Evidence Score
    - Confidence
    - Growth Score
    - selected interactions

Uses recommendation_evidence as the authoritative analytical
snapshot and recommendation_evaluations for realised 5D outcome.

No database writes.
No production changes.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd


DB_PATH = Path("data/portfolio_manager.db")


def header(title: str) -> None:
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def load_data(conn: sqlite3.Connection) -> pd.DataFrame:

    query = """
        SELECT
            re.id AS evidence_id,
            re.recommendation_id,
            re.ticker,
            re.capture_date,

            re.signal,
            re.investment_score,
            re.technical_score,
            re.quality_score,
            re.growth_score,
            re.confidence_score,

            re.entry_price,
            re.rsi,
            re.sma50,
            re.sma200,

            re.trend,
            re.trend_score,
            re.momentum_score,
            re.volume_score,
            re.risk_score,

            re.extension_sma50_pct,
            re.extension_sma200_pct,

            re.entry_quality,
            re.entry_quality_mode,

            ev.return_percent AS return_5d

        FROM recommendation_evidence re

        JOIN recommendation_evaluations ev
          ON ev.recommendation_id = re.recommendation_id
         AND ev.days_after = 5

        WHERE re.signal IN ('BUY', 'STRONG BUY')
          AND ev.return_percent IS NOT NULL

        ORDER BY
            re.capture_date,
            re.recommendation_id
    """

    return pd.read_sql_query(query, conn)


def numeric_columns(df: pd.DataFrame) -> pd.DataFrame:

    columns = [
        "investment_score",
        "technical_score",
        "quality_score",
        "growth_score",
        "confidence_score",
        "entry_price",
        "rsi",
        "sma50",
        "sma200",
        "trend_score",
        "momentum_score",
        "volume_score",
        "risk_score",
        "extension_sma50_pct",
        "extension_sma200_pct",
        "return_5d",
    ]

    for column in columns:
        if column in df.columns:
            df[column] = pd.to_numeric(
                df[column],
                errors="coerce",
            )

    df["entry_quality"] = (
        df["entry_quality"]
        .fillna("UNKNOWN")
        .astype(str)
        .str.strip()
        .str.upper()
    )

    return df


def add_derived_fields(df: pd.DataFrame) -> pd.DataFrame:

    df = df.copy()

    # Actual price distance above SMA200.
    #
    # Use the persisted extension field where available.
    # Otherwise reconstruct it from entry price / SMA200.
    df["sma200_distance_pct"] = (
        df["extension_sma200_pct"]
    )

    missing = (
        df["sma200_distance_pct"].isna()
        & df["entry_price"].notna()
        & df["sma200"].notna()
        & (df["sma200"] != 0)
    )

    df.loc[missing, "sma200_distance_pct"] = (
        (
            df.loc[missing, "entry_price"]
            / df.loc[missing, "sma200"]
        ) - 1
    ) * 100

    # RSI bands.
    df["rsi_band"] = pd.cut(
        df["rsi"],
        bins=[-np.inf, 40, 50, 60, 70, 75, np.inf],
        labels=[
            "<40",
            "40-50",
            "50-60",
            "60-70",
            "70-75",
            ">75",
        ],
        right=False,
    )

    # SMA200 distance bands.
    df["sma200_band"] = pd.cut(
        df["sma200_distance_pct"],
        bins=[
            -np.inf,
            0,
            5,
            10,
            15,
            20,
            np.inf,
        ],
        labels=[
            "<=0%",
            "0-5%",
            "5-10%",
            "10-15%",
            "15-20%",
            "20%+",
        ],
        right=False,
    )

    # Score bands.
    df["investment_band"] = pd.cut(
        df["investment_score"],
        bins=[-np.inf, 80, 85, 90, np.inf],
        labels=[
            "<80",
            "80-84",
            "85-89",
            "90+",
        ],
        right=False,
    )

    df["technical_band"] = pd.cut(
        df["technical_score"],
        bins=[-np.inf, 75, 80, 85, np.inf],
        labels=[
            "<75",
            "75-79",
            "80-84",
            "85+",
        ],
        right=False,
    )

    df["quality_band"] = pd.cut(
        df["quality_score"],
        bins=[-np.inf, 60, 70, 80, np.inf],
        labels=[
            "<60",
            "60-69",
            "70-79",
            "80+",
        ],
        right=False,
    )

    df["evidence_band"] = pd.cut(
        df["confidence_score"],
        bins=[-np.inf, 60, 65, 70, 80, 90, np.inf],
        labels=[
            "<60",
            "60-64",
            "65-69",
            "70-79",
            "80-89",
            "90+",
        ],
        right=False,
    )

    df["confidence_band"] = pd.cut(
        df["confidence_score"],
        bins=[-np.inf, 60, 70, 80, 90, np.inf],
        labels=[
            "<60",
            "60-69",
            "70-79",
            "80-89",
            "90+",
        ],
        right=False,
    )

    df["growth_band"] = pd.cut(
        df["growth_score"],
        bins=[-np.inf, 80, 90, 95, np.inf],
        labels=[
            "<80",
            "80-89",
            "90-94",
            "95+",
        ],
        right=False,
    )

    return df


def summary(
    df: pd.DataFrame,
    column: str,
) -> pd.DataFrame:

    result = (
        df.groupby(
            column,
            dropna=False,
            observed=False,
        )
        .agg(
            n=("return_5d", "count"),
            mean_5d=("return_5d", "mean"),
            median_5d=("return_5d", "median"),
            positive_pct=(
                "return_5d",
                lambda x: (x > 0).mean() * 100,
            ),
        )
        .reset_index()
    )

    return result


def print_section(
    df: pd.DataFrame,
    title: str,
    column: str,
) -> None:

    header(title)

    result = summary(
        df,
        column,
    )

    print(
        result.to_string(
            index=False,
            float_format=lambda x: f"{x:.3f}",
        )
    )


def print_baseline(df: pd.DataFrame) -> None:

    header("1. STRONG BUY BASELINE")

    print(
        f"STRONG BUY observations with mature 5D outcome: "
        f"{len(df)}"
    )

    if df.empty:
        return

    print(
        f"Mean 5D return: "
        f"{df['return_5d'].mean():.3f}%"
    )

    print(
        f"Median 5D return: "
        f"{df['return_5d'].median():.3f}%"
    )

    print(
        f"Positive 5D outcomes: "
        f"{(df['return_5d'] > 0).mean() * 100:.2f}%"
    )

    print()

    for column in [
        "investment_score",
        "technical_score",
        "quality_score",
        "growth_score",
        "confidence_score",
        "extension_sma200_pct",
        "rsi",
    ]:

        if column in df.columns:

            print(
                f"{column}: "
                f"{df[column].mean():.3f}"
            )


def print_coverage(df: pd.DataFrame) -> None:

    header("2. DATA COVERAGE")

    columns = [
        "rsi",
        "entry_price",
        "sma200",
        "extension_sma200_pct",
        "investment_score",
        "technical_score",
        "quality_score",
        "growth_score",
        "confidence_score",
        "entry_quality",
    ]

    rows = []

    for column in columns:

        available = df[column].notna().sum()

        rows.append(
            {
                "field": column,
                "available": available,
                "missing": len(df) - available,
                "coverage_pct": (
                    available / len(df) * 100
                    if len(df)
                    else 0
                ),
            }
        )

    print(
        pd.DataFrame(rows).to_string(
            index=False,
            float_format=lambda x: f"{x:.2f}",
        )
    )


def print_interaction(
    df: pd.DataFrame,
    title: str,
    columns: list[str],
) -> None:

    header(title)

    working = df.dropna(
        subset=columns + ["return_5d"]
    ).copy()

    if working.empty:
        print("No observations.")
        return

    result = (
        working.groupby(
            columns,
            dropna=False,
            observed=False,
        )
        .agg(
            n=("return_5d", "count"),
            mean_5d=("return_5d", "mean"),
            median_5d=("return_5d", "median"),
            positive_pct=(
                "return_5d",
                lambda x: (x > 0).mean() * 100,
            ),
        )
        .reset_index()
    )

    print(
        result.to_string(
            index=False,
            float_format=lambda x: f"{x:.3f}",
        )
    )


def print_signal_rule(df: pd.DataFrame) -> None:

    header("3. ACTUAL STRONG BUY RULE COVERAGE")

    print(
        "The production STRONG BUY rule is:"
    )

    print(
        "Investment Score >= 80"
    )
    print(
        "Technical Score >= 75"
    )
    print(
        "Quality Score >= 60"
    )
    print(
        "Price > SMA200"
    )
    print(
        "RSI between 40 and 75"
    )

    print()

    tests = {
        "Investment >= 80":
            df["investment_score"] >= 80,

        "Technical >= 75":
            df["technical_score"] >= 75,

        "Quality >= 60":
            df["quality_score"] >= 60,

        "Price > SMA200":
            (
                df["entry_price"].notna()
                & df["sma200"].notna()
                & (
                    df["entry_price"]
                    > df["sma200"]
                )
            ),

        "RSI 40-75":
            (
                df["rsi"].notna()
                & df["rsi"].between(
                    40,
                    75,
                    inclusive="both",
                )
            ),
    }

    rows = []

    for name, condition in tests.items():

        available = condition.notna().sum()

        passed = condition.sum()

        rows.append(
            {
                "rule_component": name,
                "passed": passed,
                "available": available,
                "pass_pct": (
                    passed / available * 100
                    if available
                    else 0
                ),
            }
        )

    print(
        pd.DataFrame(rows).to_string(
            index=False,
            float_format=lambda x: f"{x:.2f}",
        )
    )


def print_strong_buy_winners_losers(
    df: pd.DataFrame,
) -> None:

    header(
        "12. STRONG BUY WINNERS vs LOSERS"
    )

    working = df.copy()

    working["outcome"] = np.where(
        working["return_5d"] > 0,
        "WINNER",
        "LOSER",
    )

    result = (
        working.groupby(
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
            confidence_score=(
                "confidence_score",
                "mean",
            ),
            evidence_score=(
                "evidence_score",
                "mean",
            )
            if "evidence_score" in working.columns
            else ("confidence_score", "mean"),
            rsi=("rsi", "mean"),
            sma200_distance_pct=(
                "sma200_distance_pct",
                "mean",
            ),
        )
        .reset_index()
    )

    print(
        result.to_string(
            index=False,
            float_format=lambda x: f"{x:.3f}",
        )
    )


def main() -> None:

    print()
    print("=" * 78)
    print("STRONG BUY RULE FORENSICS")
    print("=" * 78)
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
        df = load_data(conn)
    finally:
        conn.close()

    df = numeric_columns(df)

    df = add_derived_fields(df)

    # We specifically want STRONG BUY here.
    strong_buy = df[
        df["signal"]
        == "STRONG BUY"
    ].copy()

    print_baseline(
        strong_buy
    )

    print_coverage(
        strong_buy
    )

    print_signal_rule(
        strong_buy
    )

    print_section(
        strong_buy,
        "4. RSI BANDS",
        "rsi_band",
    )

    print_section(
        strong_buy,
        "5. DISTANCE ABOVE SMA200",
        "sma200_band",
    )

    print_section(
        strong_buy,
        "6. INVESTMENT SCORE",
        "investment_band",
    )

    print_section(
        strong_buy,
        "7. TECHNICAL SCORE",
        "technical_band",
    )

    print_section(
        strong_buy,
        "8. QUALITY SCORE",
        "quality_band",
    )

    print_section(
        strong_buy,
        "9. ENTRY QUALITY",
        "entry_quality",
    )

    print_section(
        strong_buy,
        "10. CONFIDENCE",
        "confidence_band",
    )

    print_section(
        strong_buy,
        "11. GROWTH SCORE",
        "growth_band",
    )

    print_strong_buy_winners_losers(
        strong_buy
    )

    print_interaction(
        strong_buy,
        "13. RSI × SMA200 DISTANCE",
        [
            "rsi_band",
            "sma200_band",
        ],
    )

    print_interaction(
        strong_buy,
        "14. INVESTMENT × RSI",
        [
            "investment_band",
            "rsi_band",
        ],
    )

    print_interaction(
        strong_buy,
        "15. INVESTMENT × ENTRY QUALITY",
        [
            "investment_band",
            "entry_quality",
        ],
    )

    print_interaction(
        strong_buy,
        "16. EVIDENCE × CONFIDENCE",
        [
            "evidence_band",
            "confidence_band",
        ],
    )

    print_interaction(
        strong_buy,
        "17. GROWTH × ENTRY QUALITY",
        [
            "growth_band",
            "entry_quality",
        ],
    )

    print()
    print("=" * 78)
    print("END — READ-ONLY ANALYSIS")
    print("=" * 78)
    print()


if __name__ == "__main__":
    main()
