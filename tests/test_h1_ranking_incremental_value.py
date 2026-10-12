"""
Read-only diagnostic: H1 incremental value within Investment Score ranking.

Purpose
-------
Determine whether H1 adds useful discrimination AFTER the existing
Investment Score ranking, rather than replacing or overriding it.

This test:
    1. Reads recommendation_evidence from portfolio_manager.db.
    2. Restricts to BUY / STRONG BUY recommendations.
    3. Restricts to usable Entry Quality observations.
    4. Deduplicates to one row per recommendation_id.
    5. Creates Investment Score bands.
    6. Applies three H1 candidate rules:
         - RSI >= 55 and Return 3M <= 15
         - RSI >= 55 and Return 3M <= 20
         - RSI >= 55 and Return 3M <= 25
    7. Compares H1 vs non-H1 returns within Investment Score bands.
    8. Tests whether H1 improves the ranking inside each band.
    9. Produces no production changes.

This is diagnostic evidence only.
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


# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

H1_RULES = {
    "RSI>=55_3M<=15": {
        "rsi": 55.0,
        "return_3m": 15.0,
    },
    "RSI>=55_3M<=20": {
        "rsi": 55.0,
        "return_3m": 20.0,
    },
    "RSI>=55_3M<=25": {
        "rsi": 55.0,
        "return_3m": 25.0,
    },
}


ENTRY_QUALITY_ALLOWED = {
    "FAVOURABLE",
    "FAVOURABLE ENTRY",
    "REASONABLE",
}


# ---------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------

def load_evidence() -> pd.DataFrame:
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database not found: {DB_PATH}"
        )

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
            re.sma50,
            re.sma200,

            re.extension_sma50_pct,
            re.extension_sma200_pct,

            re.return_5d_pct,
            re.return_10d_pct,
            re.return_20d_pct,

            re.entry_quality,
            re.entry_quality_mode

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

    if df.empty:
        raise RuntimeError(
            "No BUY / STRONG BUY recommendation evidence found."
        )

    return df


# ---------------------------------------------------------------------
# Cleaning / lineage
# ---------------------------------------------------------------------

def prepare_data(df: pd.DataFrame) -> pd.DataFrame:

    numeric_columns = [
        "investment_score",
        "technical_score",
        "quality_score",
        "growth_score",
        "confidence_score",
        "evidence_score",
        "rsi",
        "return_3m",
        "sma50",
        "sma200",
        "extension_sma50_pct",
        "extension_sma200_pct",
        "return_5d_pct",
        "return_10d_pct",
        "return_20d_pct",
    ]

    for column in numeric_columns:
        if column in df.columns:
            df[column] = pd.to_numeric(
                df[column],
                errors="coerce",
            )

    df["capture_date"] = pd.to_datetime(
        df["capture_date"],
        errors="coerce",
    )

    # Keep only Entry Quality observations that are eligible
    # for BUY NEW consideration.
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

    # One immutable evidence snapshot per recommendation.
    #
    # recommendation_id is the correct lineage key. This prevents
    # repeated audit processing from artificially increasing sample size.
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

    # We need Investment Score and H1 inputs.
    df = df.dropna(
        subset=[
            "investment_score",
            "rsi",
            "return_3m",
        ]
    ).copy()

    # Outcomes are allowed to be missing at individual horizons.
    return df


# ---------------------------------------------------------------------
# Investment Score bands
# ---------------------------------------------------------------------

def add_score_bands(
    df: pd.DataFrame,
) -> pd.DataFrame:

    bins = [
        -np.inf,
        69.999,
        74.999,
        79.999,
        84.999,
        np.inf,
    ]

    labels = [
        "<70",
        "70-74.9",
        "75-79.9",
        "80-84.9",
        "85+",
    ]

    df["investment_band"] = pd.cut(
        df["investment_score"],
        bins=bins,
        labels=labels,
        right=True,
    )

    return df


# ---------------------------------------------------------------------
# H1
# ---------------------------------------------------------------------

def add_h1_flags(
    df: pd.DataFrame,
) -> pd.DataFrame:

    for name, rule in H1_RULES.items():
        df[name] = (
            (df["rsi"] >= rule["rsi"])
            &
            (df["return_3m"] <= rule["return_3m"])
        )

    return df


# ---------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------

def horizon_stats(
    df: pd.DataFrame,
    flag_column: str,
    horizon: str,
) -> dict:

    subset = df[
        df[horizon].notna()
    ].copy()

    if subset.empty:
        return {
            "n": 0,
            "mean": np.nan,
            "median": np.nan,
            "positive_pct": np.nan,
        }

    h1 = subset[
        subset[flag_column]
    ][horizon]

    non_h1 = subset[
        ~subset[flag_column]
    ][horizon]

    return {
        "n": len(h1),
        "mean": h1.mean()
        if not h1.empty
        else np.nan,
        "median": h1.median()
        if not h1.empty
        else np.nan,
        "positive_pct": (
            (h1 > 0).mean() * 100
            if not h1.empty
            else np.nan
        ),
        "non_h1_n": len(non_h1),
        "non_h1_mean": (
            non_h1.mean()
            if not non_h1.empty
            else np.nan
        ),
        "non_h1_positive_pct": (
            (non_h1 > 0).mean() * 100
            if not non_h1.empty
            else np.nan
        ),
        "delta": (
            h1.mean() - non_h1.mean()
            if not h1.empty and not non_h1.empty
            else np.nan
        ),
    }


def print_stats(
    df: pd.DataFrame,
    flag_column: str,
    label: str,
) -> None:

    print()
    print("-" * 100)
    print(label)
    print("-" * 100)

    for horizon in [
        "return_5d_pct",
        "return_10d_pct",
        "return_20d_pct",
    ]:

        stats = horizon_stats(
            df,
            flag_column,
            horizon,
        )

        print()
        print(horizon)

        print(
            f"  H1 n:              {stats['n']}"
        )

        if stats["n"] > 0:
            print(
                f"  H1 mean:           "
                f"{stats['mean']:.3f}%"
            )
            print(
                f"  H1 median:         "
                f"{stats['median']:.3f}%"
            )
            print(
                f"  H1 positive:       "
                f"{stats['positive_pct']:.2f}%"
            )

        print(
            f"  Non-H1 n:          "
            f"{stats['non_h1_n']}"
        )

        if stats["non_h1_n"] > 0:
            print(
                f"  Non-H1 mean:       "
                f"{stats['non_h1_mean']:.3f}%"
            )
            print(
                f"  Non-H1 positive:   "
                f"{stats['non_h1_positive_pct']:.2f}%"
            )

        if pd.notna(stats["delta"]):
            print(
                f"  H1 delta:          "
                f"{stats['delta']:+.3f}pp"
            )


# ---------------------------------------------------------------------
# Within-band analysis
# ---------------------------------------------------------------------

def print_band_analysis(
    df: pd.DataFrame,
    flag_column: str,
) -> None:

    print()
    print(
        "INVESTMENT SCORE BAND ANALYSIS"
    )
    print("=" * 100)

    horizons = [
        "return_5d_pct",
        "return_10d_pct",
        "return_20d_pct",
    ]

    for band in df["investment_band"].cat.categories:

        band_df = df[
            df["investment_band"] == band
        ].copy()

        if band_df.empty:
            continue

        print()
        print(
            f"Investment Score band: {band}"
        )

        print(
            f"  Total observations: "
            f"{len(band_df)}"
        )

        h1_count = int(
            band_df[flag_column].sum()
        )

        print(
            f"  H1 observations:     "
            f"{h1_count}"
        )

        for horizon in horizons:

            usable = band_df[
                band_df[horizon].notna()
            ]

            if usable.empty:
                continue

            h1 = usable[
                usable[flag_column]
            ][horizon]

            non_h1 = usable[
                ~usable[flag_column]
            ][horizon]

            if h1.empty or non_h1.empty:
                continue

            delta = (
                h1.mean()
                - non_h1.mean()
            )

            print(
                f"  {horizon}: "
                f"H1 {h1.mean():+.3f}% "
                f"vs non-H1 "
                f"{non_h1.mean():+.3f}% "
                f"→ {delta:+.3f}pp"
            )


# ---------------------------------------------------------------------
# Ranking experiment
# ---------------------------------------------------------------------

def print_ranking_experiment(
    df: pd.DataFrame,
    flag_column: str,
) -> None:

    print()
    print(
        "RANKING EXPERIMENT"
    )
    print("=" * 100)

    # Existing production-style ordering:
    # Investment Score first, H1 ignored.
    baseline = (
        df
        .sort_values(
            [
                "investment_score",
                "technical_score",
                "quality_score",
                "growth_score",
                "confidence_score",
            ],
            ascending=False,
        )
        .reset_index(drop=True)
    )

    # Experimental ordering:
    # Investment Score remains primary.
    # H1 becomes a secondary priority only.
    h1_ranked = (
        df
        .sort_values(
            [
                "investment_score",
                flag_column,
                "technical_score",
                "quality_score",
                "growth_score",
                "confidence_score",
            ],
            ascending=False,
        )
        .reset_index(drop=True)
    )

    print()
    print(
        "Top 20: existing ranking"
    )

    print(
        baseline[
            [
                "ticker",
                "investment_score",
                "rsi",
                "return_3m",
                flag_column,
            ]
        ]
        .head(20)
        .to_string(index=False)
    )

    print()
    print(
        "Top 20: experimental H1 tie-break ranking"
    )

    print(
        h1_ranked[
            [
                "ticker",
                "investment_score",
                "rsi",
                "return_3m",
                flag_column,
            ]
        ]
        .head(20)
        .to_string(index=False)
    )


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def main() -> None:

    print()
    print("=" * 100)
    print(
        "H1 INCREMENTAL VALUE WITHIN INVESTMENT SCORE RANKING"
    )
    print("=" * 100)

    print()
    print(
        f"Database: {DB_PATH}"
    )

    raw = load_evidence()

    print()
    print(
        f"Raw BUY / STRONG BUY evidence rows: "
        f"{len(raw)}"
    )

    df = prepare_data(raw)

    print(
        f"Unique usable recommendation snapshots: "
        f"{len(df)}"
    )

    if df.empty:
        raise RuntimeError(
            "No usable recommendation evidence "
            "remains after cleaning."
        )

    print(
        f"Date range: "
        f"{df['capture_date'].min().date()} "
        f"→ "
        f"{df['capture_date'].max().date()}"
    )

    print()
    print(
        "Ticker count: "
        f"{df['ticker'].nunique()}"
    )

    df = add_score_bands(df)
    df = add_h1_flags(df)

    print()
    print(
        "H1 coverage"
    )
    print("-" * 100)

    for name in H1_RULES:

        count = int(
            df[name].sum()
        )

        pct = (
            count / len(df) * 100
        )

        print(
            f"  {name:<22} "
            f"{count:>4}/{len(df)} "
            f"({pct:>6.2f}%)"
        )

    # -------------------------------------------------------------
    # Overall H1 comparison
    # -------------------------------------------------------------

    for name in H1_RULES:

        print_stats(
            df,
            name,
            f"OVERALL: {name}",
        )

    # -------------------------------------------------------------
    # Investment Score band analysis
    # -------------------------------------------------------------

    for name in H1_RULES:

        print()
        print(
            "=" * 100
        )
        print(
            f"WITHIN-SCORE-BAND TEST: {name}"
        )
        print(
            "=" * 100
        )

        print_band_analysis(
            df,
            name,
        )

    # -------------------------------------------------------------
    # Ranking experiment
    # -------------------------------------------------------------

    for name in H1_RULES:

        print()
        print(
            "=" * 100
        )
        print(
            f"RANKING EXPERIMENT: {name}"
        )
        print(
            "=" * 100
        )

        print_ranking_experiment(
            df,
            name,
        )

    # -------------------------------------------------------------
    # Final interpretation
    # -------------------------------------------------------------

    print()
    print("=" * 100)
    print(
        "ASSESSMENT"
    )
    print("=" * 100)

    print()
    print(
        "This is a READ-ONLY diagnostic."
    )

    print(
        "No production scoring, ranking, BUY NEW, "
        "governance or HOLD logic has been changed."
    )

    print()
    print(
        "The key question is whether H1 provides "
        "incremental value within existing Investment "
        "Score bands."
    )

    print()
    print(
        "If H1 only helps when Investment Scores are "
        "similar, the appropriate production role may "
        "be a secondary/tie-break priority rather than "
        "a new primary ranking factor."
    )

    print()
    print(
        "No production threshold is selected by this test."
    )

    print()


if __name__ == "__main__":
    main()
