"""
Read-only out-of-sample calibration test for the STRONG BUY rule.

Tests whether increasing the STRONG BUY Technical Score threshold
from the current production value of 75 to 85 or 90 produces an
improvement that generalises to later, unseen observations.

Full production STRONG BUY rule:

    Investment Score >= 80
    Technical Score >= candidate threshold
    Quality Score >= 60
    Price > SMA200
    RSI between 40 and 75 inclusive

This script does NOT modify:
    - production code
    - SQLite data
    - recommendations
    - audit records

It is a read-only analytical test.
"""

from pathlib import Path
import sqlite3

import numpy as np
import pandas as pd


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DB_PATH = (
    PROJECT_ROOT
    / "data"
    / "portfolio_manager.db"
)


# ============================================================
# PRODUCTION STRONG BUY RULE
# ============================================================

CURRENT_TECHNICAL_THRESHOLD = 75.0

CANDIDATE_TECHNICAL_THRESHOLDS = [
    75.0,
    85.0,
    90.0,
]

INVESTMENT_THRESHOLD = 80.0
QUALITY_THRESHOLD = 60.0

RSI_MIN = 40.0
RSI_MAX = 75.0


# ============================================================
# TEMPORAL SPLIT
# ============================================================

CALIBRATION_FRACTION = 0.70


# ============================================================
# OUTCOME HORIZONS
# ============================================================

HORIZONS = [5, 10, 20]


# ============================================================
# HELPERS
# ============================================================

def require_columns(df, required_columns):
    missing = sorted(
        set(required_columns)
        - set(df.columns)
    )

    if missing:
        raise RuntimeError(
            "Missing required columns:\n"
            + "\n".join(
                f"  - {column}"
                for column in missing
            )
            + "\n\nAvailable columns:\n"
            + ", ".join(
                sorted(df.columns)
            )
        )


def outcome_statistics(df):
    if df.empty:
        return {
            "N": 0,
            "Mean %": np.nan,
            "Median %": np.nan,
            "Positive %": np.nan,
        }

    returns = pd.to_numeric(
        df["return_percent"],
        errors="coerce",
    ).dropna()

    if returns.empty:
        return {
            "N": 0,
            "Mean %": np.nan,
            "Median %": np.nan,
            "Positive %": np.nan,
        }

    return {
        "N": int(len(returns)),
        "Mean %": float(returns.mean()),
        "Median %": float(returns.median()),
        "Positive %": float(
            (returns > 0).mean() * 100
        ),
    }


def format_stats(stats):
    return {
        "N": stats["N"],
        "Mean %": (
            round(stats["Mean %"], 3)
            if pd.notna(stats["Mean %"])
            else np.nan
        ),
        "Median %": (
            round(stats["Median %"], 3)
            if pd.notna(stats["Median %"])
            else np.nan
        ),
        "Positive %": (
            round(stats["Positive %"], 2)
            if pd.notna(stats["Positive %"])
            else np.nan
        ),
    }


# ============================================================
# LOAD DATABASE
# ============================================================

def load_database_data():
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database not found:\n{DB_PATH}"
        )

    conn = sqlite3.connect(DB_PATH)

    try:
        query = """
            SELECT
                re.recommendation_id,
                re.ticker,
                re.days_after,
                re.return_percent,

                ev.capture_date,
                ev.investment_score,
                ev.technical_score,
                ev.quality_score,
                ev.entry_price,
                ev.sma200,
                ev.rsi,
                ev.signal,
                ev.entry_quality

            FROM recommendation_evaluations re

            JOIN recommendation_evidence ev
                ON ev.recommendation_id =
                   re.recommendation_id

            WHERE re.return_percent IS NOT NULL
              AND re.days_after IN (5, 10, 20)
        """

        return pd.read_sql_query(
            query,
            conn,
        )

    finally:
        conn.close()


# ============================================================
# PREPARE DATA
# ============================================================

def prepare_data(df):
    required_columns = [
        "recommendation_id",
        "ticker",
        "days_after",
        "return_percent",
        "capture_date",
        "investment_score",
        "technical_score",
        "quality_score",
        "entry_price",
        "sma200",
        "rsi",
    ]

    require_columns(
        df,
        required_columns,
    )

    numeric_columns = [
        "days_after",
        "return_percent",
        "investment_score",
        "technical_score",
        "quality_score",
        "entry_price",
        "sma200",
        "rsi",
    ]

    for column in numeric_columns:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

    df["capture_date"] = pd.to_datetime(
        df["capture_date"],
        errors="coerce",
    )

    before = len(df)

    df = df.dropna(
        subset=[
            "recommendation_id",
            "ticker",
            "capture_date",
            "days_after",
            "return_percent",
            "investment_score",
            "technical_score",
            "quality_score",
            "entry_price",
            "sma200",
            "rsi",
        ]
    ).copy()

    removed = before - len(df)

    # --------------------------------------------------------
    # FULL production STRONG BUY conditions
    # --------------------------------------------------------

    df["investment_pass"] = (
        df["investment_score"]
        >= INVESTMENT_THRESHOLD
    )

    df["quality_pass"] = (
        df["quality_score"]
        >= QUALITY_THRESHOLD
    )

    df["trend_pass"] = (
        df["entry_price"]
        > df["sma200"]
    )

    df["rsi_pass"] = (
        (df["rsi"] >= RSI_MIN)
        & (df["rsi"] <= RSI_MAX)
    )

    return df, removed


# ============================================================
# STRONG BUY MASK
# ============================================================

def strong_buy_mask(
    df,
    technical_threshold,
):
    """
    Reconstruct the full production STRONG BUY rule
    using the supplied Technical Score threshold.
    """

    return (
        df["investment_pass"]
        & (
            df["technical_score"]
            >= technical_threshold
        )
        & df["quality_pass"]
        & df["trend_pass"]
        & df["rsi_pass"]
    )


# ============================================================
# CHRONOLOGICAL SPLIT
# ============================================================

def chronological_split(df):
    dates = (
        df["capture_date"]
        .dropna()
        .sort_values()
        .unique()
    )

    if len(dates) < 2:
        raise RuntimeError(
            "Not enough distinct capture dates "
            "for chronological validation."
        )

    split_index = int(
        len(dates)
        * CALIBRATION_FRACTION
    )

    split_index = max(
        1,
        min(
            split_index,
            len(dates) - 1,
        ),
    )

    calibration_end = dates[
        split_index - 1
    ]

    validation_start = dates[
        split_index
    ]

    calibration = df[
        df["capture_date"]
        <= calibration_end
    ].copy()

    validation = df[
        df["capture_date"]
        >= validation_start
    ].copy()

    return (
        calibration,
        validation,
        calibration_end,
        validation_start,
    )


# ============================================================
# EVALUATE THRESHOLD
# ============================================================

def evaluate_threshold(
    df,
    technical_threshold,
):
    mask = strong_buy_mask(
        df,
        technical_threshold,
    )

    return df[
        mask
    ].copy()


# ============================================================
# CALIBRATION PERIOD
# ============================================================

def calibration_analysis(
    calibration_df,
    horizon,
):
    horizon_df = calibration_df[
        calibration_df["days_after"]
        == horizon
    ].copy()

    rows = []

    for threshold in CANDIDATE_TECHNICAL_THRESHOLDS:

        selected = evaluate_threshold(
            horizon_df,
            threshold,
        )

        stats = outcome_statistics(
            selected
        )

        rows.append(
            {
                "Technical Threshold": threshold,
                **format_stats(stats),
            }
        )

    return pd.DataFrame(rows)


# ============================================================
# OUT-OF-SAMPLE VALIDATION
# ============================================================

def validation_analysis(
    validation_df,
    horizon,
):
    horizon_df = validation_df[
        validation_df["days_after"]
        == horizon
    ].copy()

    rows = []

    baseline = evaluate_threshold(
        horizon_df,
        CURRENT_TECHNICAL_THRESHOLD,
    )

    baseline_stats = outcome_statistics(
        baseline
    )

    for threshold in CANDIDATE_TECHNICAL_THRESHOLDS:

        selected = evaluate_threshold(
            horizon_df,
            threshold,
        )

        stats = outcome_statistics(
            selected
        )

        if (
            baseline_stats["N"] > 0
            and stats["N"] > 0
        ):
            mean_delta = (
                stats["Mean %"]
                - baseline_stats["Mean %"]
            )

            median_delta = (
                stats["Median %"]
                - baseline_stats["Median %"]
            )

            positive_delta = (
                stats["Positive %"]
                - baseline_stats["Positive %"]
            )

        else:
            mean_delta = np.nan
            median_delta = np.nan
            positive_delta = np.nan

        rows.append(
            {
                "Technical Threshold": threshold,
                "N": stats["N"],
                "Mean %": (
                    round(stats["Mean %"], 3)
                    if pd.notna(stats["Mean %"])
                    else np.nan
                ),
                "Median %": (
                    round(stats["Median %"], 3)
                    if pd.notna(stats["Median %"])
                    else np.nan
                ),
                "Positive %": (
                    round(stats["Positive %"], 2)
                    if pd.notna(stats["Positive %"])
                    else np.nan
                ),
                "Mean Δ vs 75": (
                    round(mean_delta, 3)
                    if pd.notna(mean_delta)
                    else np.nan
                ),
                "Median Δ vs 75": (
                    round(median_delta, 3)
                    if pd.notna(median_delta)
                    else np.nan
                ),
                "Positive Δ vs 75": (
                    round(positive_delta, 2)
                    if pd.notna(positive_delta)
                    else np.nan
                ),
                "Coverage Δ vs 75": (
                    stats["N"]
                    - baseline_stats["N"]
                ),
            }
        )

    return pd.DataFrame(rows)


# ============================================================
# TECHNICAL SCORE BANDS
# ============================================================

def technical_band_analysis(
    validation_df,
    horizon,
):
    horizon_df = validation_df[
        validation_df["days_after"]
        == horizon
    ].copy()

    eligible = horizon_df[
        horizon_df["investment_pass"]
        & horizon_df["quality_pass"]
        & horizon_df["trend_pass"]
        & horizon_df["rsi_pass"]
    ].copy()

    if eligible.empty:
        return pd.DataFrame()

    eligible["Technical Band"] = pd.cut(
        eligible["technical_score"],
        bins=[
            float("-inf"),
            74.999999,
            79.999999,
            84.999999,
            89.999999,
            float("inf"),
        ],
        labels=[
            "<75",
            "75-79",
            "80-84",
            "85-89",
            "90+",
        ],
    )

    rows = []

    for band, group in eligible.groupby(
        "Technical Band",
        observed=False,
    ):
        stats = outcome_statistics(
            group
        )

        rows.append(
            {
                "Technical Band": str(band),
                **format_stats(stats),
            }
        )

    return pd.DataFrame(rows)


# ============================================================
# 90 VS 75
# ============================================================

def candidate_comparison(
    validation_df,
    horizon,
):
    horizon_df = validation_df[
        validation_df["days_after"]
        == horizon
    ].copy()

    baseline = evaluate_threshold(
        horizon_df,
        CURRENT_TECHNICAL_THRESHOLD,
    )

    candidate = evaluate_threshold(
        horizon_df,
        90.0,
    )

    baseline_stats = outcome_statistics(
        baseline
    )

    candidate_stats = outcome_statistics(
        candidate
    )

    if (
        baseline_stats["N"] > 0
        and candidate_stats["N"] > 0
    ):
        mean_delta = (
            candidate_stats["Mean %"]
            - baseline_stats["Mean %"]
        )

        median_delta = (
            candidate_stats["Median %"]
            - baseline_stats["Median %"]
        )

        positive_delta = (
            candidate_stats["Positive %"]
            - baseline_stats["Positive %"]
        )

    else:
        mean_delta = np.nan
        median_delta = np.nan
        positive_delta = np.nan

    return {
        "Horizon": horizon,
        "Baseline N": baseline_stats["N"],
        "Candidate N": candidate_stats["N"],
        "Coverage Δ": (
            candidate_stats["N"]
            - baseline_stats["N"]
        ),
        "Baseline Mean %": baseline_stats[
            "Mean %"
        ],
        "Candidate Mean %": candidate_stats[
            "Mean %"
        ],
        "Mean Δ": mean_delta,
        "Baseline Median %": baseline_stats[
            "Median %"
        ],
        "Candidate Median %": candidate_stats[
            "Median %"
        ],
        "Median Δ": median_delta,
        "Baseline Positive %": baseline_stats[
            "Positive %"
        ],
        "Candidate Positive %": candidate_stats[
            "Positive %"
        ],
        "Positive Δ": positive_delta,
    }


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 78)
    print("STRONG BUY TECHNICAL THRESHOLD")
    print("OUT-OF-SAMPLE CALIBRATION TEST")
    print("=" * 78)
    print()

    print("READ-ONLY TEST")
    print(
        f"Database: {DB_PATH}"
    )
    print()

    print("FULL STRONG BUY rule:")
    print(
        f"  Investment Score >= "
        f"{INVESTMENT_THRESHOLD}"
    )
    print(
        "  Technical Score >= candidate threshold"
    )
    print(
        f"  Quality Score >= "
        f"{QUALITY_THRESHOLD}"
    )
    print(
        "  Price > SMA200"
    )
    print(
        f"  RSI between "
        f"{RSI_MIN} and {RSI_MAX}"
    )
    print()

    print("Candidate thresholds:")

    for threshold in CANDIDATE_TECHNICAL_THRESHOLDS:
        print(
            f"  {threshold:g}"
            + (
                "  <- CURRENT"
                if threshold
                == CURRENT_TECHNICAL_THRESHOLD
                else "  <- CANDIDATE"
            )
        )

    print()

    # --------------------------------------------------------
    # LOAD DATA
    # --------------------------------------------------------

    df = load_database_data()

    print(
        f"Raw mature outcome rows: "
        f"{len(df):,}"
    )

    df, removed = prepare_data(
        df
    )

    print(
        f"Usable outcome rows: "
        f"{len(df):,}"
    )

    print(
        f"Excluded due to missing required fields: "
        f"{removed:,}"
    )

    if df.empty:
        raise RuntimeError(
            "No usable observations remain."
        )

    # --------------------------------------------------------
    # DATE RANGE
    # --------------------------------------------------------

    print()
    print("-" * 78)
    print("DATA RANGE")
    print("-" * 78)
    print()

    print(
        f"First capture date: "
        f"{df['capture_date'].min().date()}"
    )

    print(
        f"Last capture date:  "
        f"{df['capture_date'].max().date()}"
    )

    print(
        f"Distinct capture dates: "
        f"{df['capture_date'].nunique():,}"
    )

    # --------------------------------------------------------
    # CHRONOLOGICAL SPLIT
    # --------------------------------------------------------

    (
        calibration_df,
        validation_df,
        calibration_end,
        validation_start,
    ) = chronological_split(
        df
    )

    print()
    print("-" * 78)
    print("CHRONOLOGICAL SPLIT")
    print("-" * 78)
    print()

    print("Calibration period:")
    print(
        f"  {calibration_df['capture_date'].min().date()}"
        f" -> "
        f"{calibration_df['capture_date'].max().date()}"
    )

    print(
        f"  Rows: {len(calibration_df):,}"
    )

    print()

    print("Out-of-sample validation period:")
    print(
        f"  {validation_df['capture_date'].min().date()}"
        f" -> "
        f"{validation_df['capture_date'].max().date()}"
    )

    print(
        f"  Rows: {len(validation_df):,}"
    )

    # --------------------------------------------------------
    # CALIBRATION RESULTS
    # --------------------------------------------------------

    print()
    print("=" * 78)
    print("CALIBRATION PERIOD")
    print("=" * 78)

    for horizon in HORIZONS:

        result = calibration_analysis(
            calibration_df,
            horizon,
        )

        print()
        print(
            f"{horizon}D:"
        )
        print()

        if result.empty:
            print(
                "No observations."
            )
        else:
            print(
                result.to_string(
                    index=False
                )
            )

    # --------------------------------------------------------
    # OUT-OF-SAMPLE RESULTS
    # --------------------------------------------------------

    print()
    print("=" * 78)
    print("OUT-OF-SAMPLE VALIDATION")
    print("=" * 78)

    for horizon in HORIZONS:

        result = validation_analysis(
            validation_df,
            horizon,
        )

        print()
        print(
            f"{horizon}D:"
        )
        print()

        if result.empty:
            print(
                "No observations."
            )
        else:
            print(
                result.to_string(
                    index=False
                )
            )

    # --------------------------------------------------------
    # TECHNICAL BANDS
    # --------------------------------------------------------

    print()
    print("=" * 78)
    print("OUT-OF-SAMPLE TECHNICAL SCORE BANDS")
    print("=" * 78)

    for horizon in HORIZONS:

        result = technical_band_analysis(
            validation_df,
            horizon,
        )

        if result.empty:
            continue

        print()
        print(
            f"{horizon}D:"
        )
        print()

        print(
            result.to_string(
                index=False
            )
        )

    # --------------------------------------------------------
    # EXPLICIT 90 VS 75
    # --------------------------------------------------------

    print()
    print("=" * 78)
    print("CANDIDATE 90 VS CURRENT 75")
    print("=" * 78)

    comparison_rows = []

    for horizon in HORIZONS:

        comparison_rows.append(
            candidate_comparison(
                validation_df,
                horizon,
            )
        )

    comparison = pd.DataFrame(
        comparison_rows
    )

    display = comparison.copy()

    for column in [
        "Baseline Mean %",
        "Candidate Mean %",
        "Mean Δ",
        "Baseline Median %",
        "Candidate Median %",
        "Median Δ",
        "Baseline Positive %",
        "Candidate Positive %",
        "Positive Δ",
    ]:
        display[column] = display[
            column
        ].round(3)

    print()
    print(
        display.to_string(
            index=False
        )
    )

    # --------------------------------------------------------
    # COVERAGE IMPACT
    # --------------------------------------------------------

    print()
    print("=" * 78)
    print("COVERAGE IMPACT OF TECHNICAL >= 90")
    print("=" * 78)

    for horizon in HORIZONS:

        horizon_df = validation_df[
            validation_df["days_after"]
            == horizon
        ].copy()

        if horizon_df.empty:
            continue

        baseline = evaluate_threshold(
            horizon_df,
            75.0,
        )

        candidate = evaluate_threshold(
            horizon_df,
            90.0,
        )

        baseline_n = len(
            baseline
        )

        candidate_n = len(
            candidate
        )

        if baseline_n:
            retained = (
                candidate_n
                / baseline_n
                * 100
            )
        else:
            retained = np.nan

        print()
        print(
            f"{horizon}D:"
        )
        print(
            f"  Current 75: "
            f"{baseline_n}"
        )
        print(
            f"  Candidate 90: "
            f"{candidate_n}"
        )

        if pd.notna(retained):
            print(
                f"  Retained: "
                f"{retained:.2f}%"
            )

    # --------------------------------------------------------
    # FINAL MESSAGE
    # --------------------------------------------------------

    print()
    print("=" * 78)
    print("TEST COMPLETE")
    print("=" * 78)
    print()

    print(
        "This test is READ-ONLY."
    )

    print(
        "No production STRONG BUY rule has been changed."
    )

    print(
        "The candidate threshold must be assessed using "
        "out-of-sample performance, sample size, coverage "
        "and consistency across horizons."
    )

    print(
        "The result is observational evidence and does not "
        "establish causality."
    )

    print()


if __name__ == "__main__":
    main()
