"""
Historical candidate-population walk-forward OOS test for BUY NEW H1.

H1:
Within the historical BUY NEW candidate population, short-term momentum
quality may be more predictive of subsequent performance than aggregate
Technical Score.

Specifically:
    - higher RSI within the bullish range may be favourable;
    - moderate 3-month performance may be preferable to already-extended
      3-month momentum;
    - the combination of higher RSI + moderate Return_3m may identify
      stronger near-term continuation candidates.

This test deliberately moves upstream from FINAL BUY NEW decisions.

Population:
    Historical BUY / STRONG BUY recommendation candidates with immutable
    recommendation_evidence and matured realised returns.

It does NOT require the candidate to have ultimately become BUY NEW.

Method:
    1. Load the historical BUY / STRONG BUY candidate population.
    2. Deduplicate to one immutable recommendation/evidence observation.
    3. Require matured 5D/10D/20D outcomes.
    4. Run chronological walk-forward windows.
    5. Learn H1 thresholds ONLY from each training window.
    6. Freeze the thresholds.
    7. Apply the frozen rule to the immediately following OOS window.
    8. Compare H1-selected candidates with the complete candidate baseline.
    9. Repeat across multiple windows.
   10. Report aggregate OOS performance.

No production changes are made.
No database writes are made.
No scoring, weighting, candidate-selection or governance logic is changed.
"""

from pathlib import Path
import sqlite3
import numpy as np
import pandas as pd


# ============================================================
# CONFIGURATION
# ============================================================

DB_PATH = Path("data/portfolio_manager.db")

# Minimum training observations required before learning a rule.
MIN_TRAIN_OBSERVATIONS = 12

# Minimum observations selected by a candidate rule in training.
MIN_TRAIN_SELECTED = 4

# Minimum OOS observations selected by H1 before treating an individual
# OOS window as informative.
MIN_OOS_SELECTED = 2

# Candidate thresholds.
#
# Kept deliberately coarse to reduce overfitting.
RSI_THRESHOLDS = [55.0, 57.0, 60.0]

RETURN_3M_CUTOFFS = [15.0, 20.0, 25.0]

# Walk-forward window sizes.
#
# We use chronological blocks rather than random train/test splits.
TRAIN_SIZE = 12
OOS_SIZE = 6
STEP_SIZE = 6


# ============================================================
# DATABASE LOAD
# ============================================================

def load_candidate_population():
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database not found: {DB_PATH}"
        )

    conn = sqlite3.connect(DB_PATH)

    query = """
        SELECT
            r.id AS recommendation_id,
            r.date AS recommendation_date,
            r.ticker,
            r.signal,
            r.investment_score,
            r.technical_score,
            r.quality_score,
            r.growth_score,
            r.confidence_score,

            re.capture_date,
            re.rsi,
            re.return_3m,
            re.return_5d_pct,
            re.return_10d_pct,
            re.return_20d_pct,
            re.entry_quality,
            re.entry_quality_mode

        FROM recommendations r

        INNER JOIN recommendation_evidence re
            ON r.id = re.recommendation_id

        WHERE UPPER(TRIM(r.signal)) IN (
            'BUY',
            'STRONG BUY'
        )

        ORDER BY
            re.capture_date ASC,
            r.id ASC
    """

    df = pd.read_sql_query(
        query,
        conn
    )

    conn.close()

    return df


# ============================================================
# PREPARE / DEDUPLICATE
# ============================================================

def prepare_data(df):
    if df.empty:
        raise ValueError(
            "No historical BUY / STRONG BUY candidate observations found."
        )

    # Dates.
    df["capture_date"] = pd.to_datetime(
        df["capture_date"],
        errors="coerce"
    )

    df["recommendation_date"] = pd.to_datetime(
        df["recommendation_date"],
        errors="coerce"
    )

    # Numeric fields.
    numeric_columns = [
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

    for column in numeric_columns:
        if column in df.columns:
            df[column] = pd.to_numeric(
                df[column],
                errors="coerce"
            )

    raw_rows = len(df)

    # recommendation_evidence should be immutable and one row per
    # recommendation. Protect the analysis against accidental duplicate
    # joins nevertheless.
    df = (
        df.sort_values(
            [
                "capture_date",
                "recommendation_id"
            ]
        )
        .drop_duplicates(
            subset=["recommendation_id"],
            keep="first"
        )
        .reset_index(drop=True)
    )

    unique_rows = len(df)

    print()
    print("=" * 80)
    print("HISTORICAL BUY NEW CANDIDATE POPULATION")
    print("=" * 80)

    print(
        f"Raw joined candidate rows : {raw_rows}"
    )

    print(
        f"Unique recommendations    : {unique_rows}"
    )

    print(
        f"Duplicate rows removed    : "
        f"{raw_rows - unique_rows}"
    )

    # H1 requires RSI and Return_3m.
    df = df.dropna(
        subset=[
            "capture_date",
            "recommendation_id",
            "ticker",
            "rsi",
            "return_3m",
        ]
    ).reset_index(drop=True)

    print(
        f"Usable H1 observations    : {len(df)}"
    )

    # Chronological ordering.
    df = df.sort_values(
        [
            "capture_date",
            "recommendation_id"
        ]
    ).reset_index(drop=True)

    return df


# ============================================================
# RULE
# ============================================================

def apply_h1_rule(
    df,
    rsi_threshold,
    return_3m_cutoff
):
    return df[
        (df["rsi"] >= rsi_threshold)
        &
        (df["return_3m"] <= return_3m_cutoff)
    ].copy()


# ============================================================
# TRAINING RULE SEARCH
# ============================================================

def evaluate_training_rule(
    train,
    rsi_threshold,
    return_3m_cutoff
):
    selected = apply_h1_rule(
        train,
        rsi_threshold,
        return_3m_cutoff
    )

    if len(selected) < MIN_TRAIN_SELECTED:
        return None

    matured = selected[
        selected["return_5d_pct"].notna()
    ]

    if len(matured) < MIN_TRAIN_SELECTED:
        return None

    mean_5d = matured[
        "return_5d_pct"
    ].mean()

    positive_5d = (
        matured["return_5d_pct"] > 0
    ).mean()

    return {
        "rsi_threshold": rsi_threshold,
        "return_3m_cutoff": return_3m_cutoff,
        "n": len(matured),
        "mean_5d": mean_5d,
        "positive_5d": positive_5d,
    }


def learn_rule(train):
    candidates = []

    for rsi_threshold in RSI_THRESHOLDS:
        for return_3m_cutoff in RETURN_3M_CUTOFFS:

            result = evaluate_training_rule(
                train,
                rsi_threshold,
                return_3m_cutoff
            )

            if result is not None:
                candidates.append(result)

    if not candidates:
        return None

    # Training-only optimisation.
    candidates = sorted(
        candidates,
        key=lambda x: (
            x["mean_5d"],
            x["positive_5d"],
            x["n"],
        ),
        reverse=True
    )

    return candidates[0]


# ============================================================
# PERFORMANCE
# ============================================================

def horizon_stats(
    df,
    column
):
    matured = df[
        df[column].notna()
    ]

    if matured.empty:
        return None

    return {
        "n": len(matured),
        "mean": matured[column].mean(),
        "median": matured[column].median(),
        "positive_rate": (
            matured[column] > 0
        ).mean() * 100,
    }


def compare(
    baseline,
    h1
):
    results = {}

    for horizon in [
        "return_5d_pct",
        "return_10d_pct",
        "return_20d_pct",
    ]:

        baseline_stats = horizon_stats(
            baseline,
            horizon
        )

        h1_stats = horizon_stats(
            h1,
            horizon
        )

        if baseline_stats is None:
            results[horizon] = None
            continue

        if h1_stats is None:
            results[horizon] = {
                "baseline": baseline_stats,
                "h1": None,
            }
            continue

        results[horizon] = {
            "baseline": baseline_stats,
            "h1": h1_stats,
            "mean_delta": (
                h1_stats["mean"]
                - baseline_stats["mean"]
            ),
            "positive_delta": (
                h1_stats["positive_rate"]
                - baseline_stats["positive_rate"]
            ),
        }

    return results


# ============================================================
# WALK-FORWARD
# ============================================================

def run_walk_forward(df):
    windows = []

    start = 0
    window_number = 1

    while True:

        train_start = 0
        train_end = start + TRAIN_SIZE

        oos_start = train_end
        oos_end = oos_start + OOS_SIZE

        if oos_end > len(df):
            break

        train = df.iloc[
            train_start:train_end
        ].copy()

        oos = df.iloc[
            oos_start:oos_end
        ].copy()

        if len(train) < MIN_TRAIN_OBSERVATIONS:
            break

        rule = learn_rule(train)

        if rule is None:
            print()
            print(
                f"Window {window_number}: "
                "no valid training rule."
            )

            start += STEP_SIZE
            window_number += 1
            continue

        # IMPORTANT:
        # Rule is now frozen.
        oos_h1 = apply_h1_rule(
            oos,
            rule["rsi_threshold"],
            rule["return_3m_cutoff"]
        )

        comparison = compare(
            oos,
            oos_h1
        )

        windows.append(
            {
                "window": window_number,
                "train": train,
                "oos": oos,
                "rule": rule,
                "h1": oos_h1,
                "comparison": comparison,
            }
        )

        print()
        print("=" * 80)
        print(
            f"WALK-FORWARD WINDOW {window_number}"
        )
        print("=" * 80)

        print(
            f"Training : "
            f"{train['capture_date'].min().date()} "
            f"→ "
            f"{train['capture_date'].max().date()} "
            f"(n={len(train)})"
        )

        print(
            f"OOS      : "
            f"{oos['capture_date'].min().date()} "
            f"→ "
            f"{oos['capture_date'].max().date()} "
            f"(n={len(oos)})"
        )

        print()
        print(
            "Frozen training rule:"
        )

        print(
            f"  RSI >= {rule['rsi_threshold']:.1f}"
        )

        print(
            f"  Return_3m <= "
            f"{rule['return_3m_cutoff']:.1f}%"
        )

        print()
        print(
            f"OOS H1 selected : "
            f"{len(oos_h1)} / {len(oos)}"
        )

        for horizon in [
            "return_5d_pct",
            "return_10d_pct",
            "return_20d_pct",
        ]:

            result = comparison[horizon]

            label = (
                horizon
                .replace("return_", "")
                .replace("_pct", "")
                .upper()
            )

            if (
                result is None
                or result["h1"] is None
            ):
                print(
                    f"{label:>3}: "
                    "insufficient H1 data"
                )
                continue

            print(
                f"{label:>3}: "
                f"baseline={result['baseline']['mean']:+.3f}% "
                f"H1={result['h1']['mean']:+.3f}% "
                f"delta={result['mean_delta']:+.3f}pp "
                f"H1 n={result['h1']['n']}"
            )

        start += STEP_SIZE
        window_number += 1

    return windows


# ============================================================
# AGGREGATE OOS
# ============================================================

def aggregate_oos(windows):
    if not windows:
        print()
        print(
            "NO VALID WALK-FORWARD WINDOWS"
        )
        return

    baseline_frames = []
    h1_frames = []

    rules = []

    for window in windows:

        baseline = window["oos"].copy()
        h1 = window["h1"].copy()

        baseline["window"] = window["window"]
        h1["window"] = window["window"]

        baseline_frames.append(baseline)
        h1_frames.append(h1)

        rules.append(
            {
                "window": window["window"],
                "rsi_threshold": (
                    window["rule"]["rsi_threshold"]
                ),
                "return_3m_cutoff": (
                    window["rule"]["return_3m_cutoff"]
                ),
                "oos_n": len(window["oos"]),
                "h1_n": len(h1),
            }
        )

    baseline_all = pd.concat(
        baseline_frames,
        ignore_index=True
    )

    h1_all = pd.concat(
        h1_frames,
        ignore_index=True
    )

    print()
    print("=" * 80)
    print("AGGREGATED WALK-FORWARD OOS RESULTS")
    print("=" * 80)

    print(
        f"Walk-forward windows : {len(windows)}"
    )

    print(
        f"Baseline OOS rows    : {len(baseline_all)}"
    )

    print(
        f"H1-selected OOS rows : {len(h1_all)}"
    )

    print()
    print(
        "Frozen rules by window:"
    )

    for rule in rules:
        print(
            f"  Window {rule['window']}: "
            f"RSI >= {rule['rsi_threshold']:.1f}, "
            f"3M <= {rule['return_3m_cutoff']:.1f}% "
            f"| OOS n={rule['oos_n']} "
            f"| H1 n={rule['h1_n']}"
        )

    print()
    print(
        "Aggregate performance:"
    )

    aggregate_comparison = compare(
        baseline_all,
        h1_all
    )

    for horizon in [
        "return_5d_pct",
        "return_10d_pct",
        "return_20d_pct",
    ]:

        result = aggregate_comparison[horizon]

        label = (
            horizon
            .replace("return_", "")
            .replace("_pct", "")
            .upper()
        )

        if (
            result is None
            or result["h1"] is None
        ):
            print(
                f"{label:>3}: insufficient matured H1 data"
            )
            continue

        print(
            f"{label:>3}: "
            f"baseline mean="
            f"{result['baseline']['mean']:+.3f}% "
            f"| H1 mean="
            f"{result['h1']['mean']:+.3f}% "
            f"| delta="
            f"{result['mean_delta']:+.3f}pp "
            f"| baseline positive="
            f"{result['baseline']['positive_rate']:.2f}% "
            f"| H1 positive="
            f"{result['h1']['positive_rate']:.2f}% "
            f"| H1 n="
            f"{result['h1']['n']}"
        )

    # Window-level consistency.
    print()
    print(
        "WINDOW CONSISTENCY"
    )

    for horizon in [
        "return_5d_pct",
        "return_10d_pct",
        "return_20d_pct",
    ]:

        label = (
            horizon
            .replace("return_", "")
            .replace("_pct", "")
            .upper()
        )

        improvements = 0
        informative = 0

        for window in windows:

            result = window["comparison"][horizon]

            if (
                result is None
                or result["h1"] is None
                or result["h1"]["n"] < MIN_OOS_SELECTED
            ):
                continue

            informative += 1

            if result["mean_delta"] > 0:
                improvements += 1

        if informative == 0:
            print(
                f"{label:>3}: no informative OOS windows"
            )
        else:
            print(
                f"{label:>3}: "
                f"H1 improved in "
                f"{improvements}/{informative} "
                f"informative windows"
            )

    # Final evidence classification.
    informative_windows = 0

    for window in windows:
        result = window["comparison"]["return_5d_pct"]

        if (
            result is not None
            and result["h1"] is not None
            and result["h1"]["n"] >= MIN_OOS_SELECTED
        ):
            informative_windows += 1

    print()
    print("=" * 80)
    print("H1 EVIDENCE ASSESSMENT")
    print("=" * 80)

    if informative_windows < 2:
        print(
            "INCONCLUSIVE"
        )
        print(
            "There are not enough informative OOS windows "
            "to support an H1 calibration decision."
        )

    else:
        result = aggregate_comparison[
            "return_5d_pct"
        ]

        if (
            result is not None
            and result["h1"] is not None
            and result["mean_delta"] > 0
        ):
            print(
                "POSITIVE OOS DIRECTION — FURTHER VALIDATION REQUIRED"
            )
            print(
                "H1 has shown positive aggregate OOS direction, "
                "but this remains research evidence rather than "
                "a production calibration recommendation."
            )
        else:
            print(
                "NOT SUPPORTED BY CURRENT OOS EVIDENCE"
            )
            print(
                "H1 has not demonstrated a positive aggregate "
                "OOS advantage over the historical BUY/STRONG BUY "
                "candidate baseline."
            )

    print()
    print(
        "NO PRODUCTION CHANGES WERE MADE."
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 80)
    print("BUY NEW H1 HISTORICAL CANDIDATE WALK-FORWARD TEST")
    print("=" * 80)

    print()
    print(
        "READ-ONLY — NO PRODUCTION CHANGES"
    )

    df = load_candidate_population()

    df = prepare_data(df)

    if len(df) < (
        TRAIN_SIZE + OOS_SIZE
    ):
        print()
        print(
            "INSUFFICIENT DATA"
        )
        print(
            f"Need at least "
            f"{TRAIN_SIZE + OOS_SIZE} "
            f"usable observations."
        )
        print(
            f"Found {len(df)}."
        )
        return

    print()
    print("=" * 80)
    print("CANDIDATE POPULATION")
    print("=" * 80)

    print(
        f"Date range : "
        f"{df['capture_date'].min().date()} "
        f"→ "
        f"{df['capture_date'].max().date()}"
    )

    print(
        f"Observations : {len(df)}"
    )

    print()
    print(
        "Signal distribution:"
    )

    print(
        df["signal"]
        .value_counts()
        .to_string()
    )

    windows = run_walk_forward(
        df
    )

    aggregate_oos(
        windows
    )


if __name__ == "__main__":
    main()
