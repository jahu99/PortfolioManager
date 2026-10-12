"""
Read-only STRONG BUY technical-threshold calibration test.

Purpose
-------
Evaluate candidate Technical Score thresholds for the STRONG BUY rule
without changing production code.

Current production rule:
    Investment Score >= 80
    Technical Score >= 75
    Quality Score >= 60
    Price > SMA200
    RSI between 40 and 75 inclusive

Candidate Technical Score thresholds:
    75, 80, 85, 87.5, 90, 92.5

The test evaluates mature 5D recommendation outcomes and compares each
candidate threshold with the current production baseline.

IMPORTANT:
    This script is READ-ONLY.
    It does not modify SQLite, recommendations, audit data, or production
    decision logic.
"""

from pathlib import Path
import sqlite3
import sys

import pandas as pd


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "portfolio_manager.db"


# ============================================================
# PRODUCTION STRONG BUY RULE
# ============================================================

INVESTMENT_THRESHOLD = 80.0
QUALITY_THRESHOLD = 60.0
PRICE_ABOVE_SMA200 = True
RSI_MIN = 40.0
RSI_MAX = 75.0

TECHNICAL_THRESHOLDS = [
    75.0,
    80.0,
    85.0,
    87.5,
    90.0,
    92.5,
]


# ============================================================
# HELPERS
# ============================================================

def require_columns(df, required):
    missing = sorted(set(required) - set(df.columns))

    if missing:
        raise RuntimeError(
            "Missing required columns: "
            + ", ".join(missing)
            + "\nAvailable columns:\n"
            + ", ".join(sorted(df.columns))
        )


def safe_float(series):
    return pd.to_numeric(series, errors="coerce")


def outcome_summary(df):
    if df.empty:
        return {
            "N": 0,
            "Mean 5D %": None,
            "Median 5D %": None,
            "Positive 5D %": None,
        }

    returns = pd.to_numeric(
        df["return_percent"],
        errors="coerce",
    ).dropna()

    if returns.empty:
        return {
            "N": 0,
            "Mean 5D %": None,
            "Median 5D %": None,
            "Positive 5D %": None,
        }

    return {
        "N": int(len(returns)),
        "Mean 5D %": round(float(returns.mean()), 3),
        "Median 5D %": round(float(returns.median()), 3),
        "Positive 5D %": round(
            float((returns > 0).mean() * 100),
            2,
        ),
    }


# ============================================================
# LOAD MATURE RECOMMENDATION EVIDENCE
# ============================================================

def load_data():
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database not found: {DB_PATH}"
        )

    conn = sqlite3.connect(DB_PATH)

    try:
        query = """
            SELECT
                re.recommendation_id,
                re.ticker,
                re.days_after,
                re.return_percent,

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
                ON ev.recommendation_id = re.recommendation_id

            WHERE re.days_after = 5
              AND re.return_percent IS NOT NULL
        """

        df = pd.read_sql_query(
            query,
            conn,
        )

    finally:
        conn.close()

    return df


# ============================================================
# PREPARE DATA
# ============================================================

def prepare_data(df):
    required = [
        "recommendation_id",
        "ticker",
        "days_after",
        "return_percent",
        "investment_score",
        "technical_score",
        "quality_score",
        "entry_price",
        "sma200",
        "rsi",
    ]

    require_columns(df, required)

    numeric_columns = [
        "return_percent",
        "investment_score",
        "technical_score",
        "quality_score",
        "entry_price",
        "sma200",
        "rsi",
    ]

    for column in numeric_columns:
        df[column] = safe_float(df[column])

    # --------------------------------------------------------
    # Remove rows that cannot be evaluated against the
    # production STRONG BUY rule.
    # --------------------------------------------------------

    before = len(df)

    df = df.dropna(
        subset=[
            "investment_score",
            "technical_score",
            "quality_score",
            "entry_price",
            "sma200",
            "rsi",
            "return_percent",
        ]
    ).copy()

    removed = before - len(df)

    # --------------------------------------------------------
    # Reconstruct the FULL production STRONG BUY rule.
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
# CALIBRATION
# ============================================================

def evaluate_thresholds(df):
    rows = []

    baseline = None

    for threshold in TECHNICAL_THRESHOLDS:

        technical_pass = (
            df["technical_score"]
            >= threshold
        )

        selected = df[
            df["investment_pass"]
            & technical_pass
            & df["quality_pass"]
            & df["trend_pass"]
            & df["rsi_pass"]
        ].copy()

        summary = outcome_summary(selected)

        row = {
            "Technical Threshold": threshold,
            **summary,
        }

        rows.append(row)

        if threshold == 75.0:
            baseline = summary

    result = pd.DataFrame(rows)

    if baseline is not None:

        result["Mean Δ vs 75D"] = (
            result["Mean 5D %"]
            - baseline["Mean 5D %"]
        ).round(3)

        result["Median Δ vs 75D"] = (
            result["Median 5D %"]
            - baseline["Median 5D %"]
        ).round(3)

        result["Positive Δ vs 75D"] = (
            result["Positive 5D %"]
            - baseline["Positive 5D %"]
        ).round(2)

        result["Coverage Δ vs 75"] = (
            result["N"]
            - baseline["N"]
        )

    return result


# ============================================================
# TECHNICAL SCORE DISTRIBUTION
# ============================================================

def technical_distribution(df):
    selected = df[
        df["investment_pass"]
        & df["quality_pass"]
        & df["trend_pass"]
        & df["rsi_pass"]
    ].copy()

    bands = pd.cut(
        selected["technical_score"],
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

    selected["Technical Band"] = bands

    rows = []

    for band, group in selected.groupby(
        "Technical Band",
        observed=False,
    ):
        summary = outcome_summary(group)

        rows.append(
            {
                "Technical Band": str(band),
                **summary,
            }
        )

    return pd.DataFrame(rows)


# ============================================================
# INTERACTION WITH ENTRY QUALITY
# ============================================================

def entry_quality_interaction(df):
    if "entry_quality" not in df.columns:
        return pd.DataFrame()

    selected = df[
        df["investment_pass"]
        & df["quality_pass"]
        & df["trend_pass"]
        & df["rsi_pass"]
    ].copy()

    selected["Technical Band"] = pd.cut(
        selected["technical_score"],
        bins=[
            float("-inf"),
            84.999999,
            89.999999,
            float("inf"),
        ],
        labels=[
            "<85",
            "85-89",
            "90+",
        ],
    )

    rows = []

    for (
        technical_band,
        entry_quality,
    ), group in selected.groupby(
        [
            "Technical Band",
            "entry_quality",
        ],
        observed=False,
        dropna=False,
    ):
        summary = outcome_summary(group)

        if summary["N"] < 3:
            continue

        rows.append(
            {
                "Technical Band": str(
                    technical_band
                ),
                "Entry Quality": (
                    str(entry_quality)
                    if pd.notna(entry_quality)
                    else "UNKNOWN"
                ),
                **summary,
            }
        )

    return pd.DataFrame(rows)


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 72)
    print("STRONG BUY TECHNICAL THRESHOLD CALIBRATION")
    print("=" * 72)
    print()
    print("READ-ONLY TEST")
    print(f"Database: {DB_PATH}")
    print()

    print("Production STRONG BUY rule:")
    print(
        f"  Investment Score >= "
        f"{INVESTMENT_THRESHOLD}"
    )
    print(
        f"  Technical Score >= "
        f"{TECHNICAL_THRESHOLDS[0]}"
    )
    print(
        f"  Quality Score >= "
        f"{QUALITY_THRESHOLD}"
    )
    print("  Price > SMA200")
    print(
        f"  RSI between "
        f"{RSI_MIN} and {RSI_MAX}"
    )
    print()

    df = load_data()

    print(
        f"Raw mature 5D recommendation outcomes: "
        f"{len(df):,}"
    )

    df, removed = prepare_data(df)

    print(
        f"Usable observations after required-field "
        f"filter: {len(df):,}"
    )

    print(
        f"Excluded because required fields were "
        f"missing: {removed:,}"
    )
    print()

    # --------------------------------------------------------
    # Evaluate candidate thresholds
    # --------------------------------------------------------

    results = evaluate_thresholds(df)

    print()
    print("-" * 72)
    print("CANDIDATE TECHNICAL THRESHOLDS")
    print("-" * 72)
    print()

    print(
        results.to_string(
            index=False
        )
    )

    # --------------------------------------------------------
    # Distribution
    # --------------------------------------------------------

    distribution = technical_distribution(df)

    print()
    print("-" * 72)
    print("TECHNICAL SCORE DISTRIBUTION")
    print("-" * 72)
    print()

    print(
        distribution.to_string(
            index=False
        )
    )

    # --------------------------------------------------------
    # Entry Quality interaction
    # --------------------------------------------------------

    interaction = entry_quality_interaction(df)

    if not interaction.empty:

        print()
        print("-" * 72)
        print(
            "TECHNICAL SCORE × ENTRY QUALITY"
        )
        print("-" * 72)
        print()

        print(
            interaction.to_string(
                index=False
            )
        )

    # --------------------------------------------------------
    # Explicit baseline
    # --------------------------------------------------------

    baseline = results[
        results["Technical Threshold"] == 75.0
    ]

    if not baseline.empty:

        baseline = baseline.iloc[0]

        print()
        print("-" * 72)
        print("CURRENT PRODUCTION BASELINE")
        print("-" * 72)
        print()

        print(
            f"N:              {baseline['N']}"
        )
        print(
            f"Mean 5D:        "
            f"{baseline['Mean 5D %']:.3f}%"
        )
        print(
            f"Median 5D:      "
            f"{baseline['Median 5D %']:.3f}%"
        )
        print(
            f"Positive 5D:    "
            f"{baseline['Positive 5D %']:.2f}%"
        )

    # --------------------------------------------------------
    # Important warning
    # --------------------------------------------------------

    print()
    print("=" * 72)
    print("INTERPRETATION")
    print("=" * 72)
    print()
    print(
        "This test does NOT change the production "
        "STRONG BUY rule."
    )
    print()
    print(
        "A higher threshold should only be considered "
        "for A6 calibration if the improvement is "
        "material and sufficiently supported by "
        "mature observations."
    )
    print()
    print(
        "In particular, do not select a threshold "
        "solely because it has the highest historical "
        "5D return. Check sample size, coverage, "
        "median return, positive rate, and the "
        "85-89 / 90+ population sizes."
    )
    print()
    print(
        "The next decision should be based on the "
        "observed calibration evidence, not on this "
        "script making an automatic production change."
    )
    print()
    print("=" * 72)
    print()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print()
        print("TEST FAILED")
        print()
        print(str(exc))
        print()
        raise
