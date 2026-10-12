"""
Read-only walk-forward OOS test for BUY NEW technical hypothesis H1.

H1:
Within BUY NEW candidates, short-term momentum quality may be more
predictive of subsequent performance than aggregate Technical Score.

Specifically:
- higher RSI within the bullish range may be favourable;
- moderate 3-month performance may outperform already-extended 3-month momentum;
- the combination of higher RSI + moderate 3M performance may identify
  stronger near-term continuation candidates.

This script:
1. Uses recommendation_evidence as the historical evidence source.
2. Uses final BUY NEW decisions from audit_decisions to define the
   BUY NEW population.
3. Collapses repeated audit rows to one observation per recommendation.
4. Orders observations chronologically.
5. Splits observations into chronological training and OOS periods.
6. Learns candidate RSI / Return_3m thresholds ONLY from training data.
7. Freezes those thresholds.
8. Applies the frozen H1 rule to the OOS period.
9. Compares H1-selected observations with the full BUY NEW baseline.
10. Reports 5D, 10D and 20D performance where matured.
11. Makes NO production changes.

Important:
- This is deliberately conservative.
- No thresholds are learned from OOS observations.
- No production scoring, recommendation, candidate selection or database
  logic is modified.
"""

from pathlib import Path
import sqlite3
import pandas as pd
import numpy as np


# ============================================================
# CONFIGURATION
# ============================================================

DB_PATH = Path("data/portfolio_manager.db")

# Chronological training proportion.
TRAIN_RATIO = 0.70

# Minimum observations required in each training bucket before a
# threshold is considered usable.
MIN_TRAIN_BUCKET = 3

# Candidate threshold grids.
#
# These are deliberately coarse. We do NOT want to overfit the
# very small current BUY NEW sample.
RSI_THRESHOLDS = [55.0, 57.0, 60.0]
RETURN_3M_CUTOFFS = [15.0, 20.0, 25.0]

# H1 operational form:
#
# RSI >= learned threshold
# AND
# Return_3m <= learned cutoff
#
# This represents:
# "higher RSI within the bullish range + moderate rather than excessive
# 3-month performance."
#
# The rule is only learned from training observations.


# ============================================================
# DATABASE
# ============================================================

def load_buy_new_evidence():
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database not found: {DB_PATH}"
        )

    conn = sqlite3.connect(DB_PATH)

    query = """
        SELECT
            ad.recommendation_id,
            ad.ticker,
            ad.created_at AS audit_created_at,
            ad.final_action,

            re.capture_date,
            re.signal,
            re.investment_score,
            re.technical_score,
            re.quality_score,
            re.growth_score,
            re.ai_conviction_score,

            re.rsi,
            re.return_3m,
            re.return_5d_pct,
            re.return_10d_pct,
            re.return_20d_pct,

            re.entry_quality,
            re.entry_quality_mode

        FROM audit_decisions ad

        INNER JOIN recommendation_evidence re
            ON ad.recommendation_id = re.recommendation_id

        WHERE ad.final_action = 'BUY NEW'

        ORDER BY
            re.capture_date ASC,
            ad.recommendation_id ASC
    """

    df = pd.read_sql_query(query, conn)

    conn.close()

    return df


# ============================================================
# CLEAN / DEDUPLICATE
# ============================================================

def prepare_data(df):
    if df.empty:
        raise ValueError(
            "No BUY NEW evidence rows were found."
        )

    # Convert dates.
    df["capture_date"] = pd.to_datetime(
        df["capture_date"],
        errors="coerce"
    )

    # Numeric fields.
    numeric_columns = [
        "investment_score",
        "technical_score",
        "quality_score",
        "growth_score",
        "ai_conviction_score",
        "rsi",
        "return_3m",
        "return_5d_pct",
        "return_10d_pct",
        "return_20d_pct",
    ]

    for column in numeric_columns:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )

    # The same recommendation can appear multiple times in audit_decisions.
    #
    # We need one underlying recommendation/evidence observation, otherwise
    # repeated audit processing would artificially increase its weight.
    #
    # recommendation_evidence is expected to be one immutable snapshot per
    # recommendation.
    dedupe_columns = ["recommendation_id"]

    before = len(df)

    df = (
        df.sort_values(
            ["capture_date", "recommendation_id"]
        )
        .drop_duplicates(
            subset=dedupe_columns,
            keep="first"
        )
        .reset_index(drop=True)
    )

    after = len(df)

    print()
    print("=" * 80)
    print("BUY NEW DATASET")
    print("=" * 80)
    print(f"Raw joined audit rows       : {before}")
    print(f"Unique recommendations      : {after}")
    print(
        f"Removed repeated audit rows : {before - after}"
    )

    # Require the fields needed for H1.
    required = [
        "capture_date",
        "recommendation_id",
        "ticker",
        "rsi",
        "return_3m",
    ]

    missing = [
        column
        for column in required
        if column not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Missing required columns: {missing}"
        )

    # Keep observations where H1 inputs exist.
    df = df.dropna(
        subset=[
            "capture_date",
            "rsi",
            "return_3m",
        ]
    ).reset_index(drop=True)

    print(f"Usable H1 observations       : {len(df)}")

    if len(df) < 10:
        print()
        print(
            "WARNING: Very small BUY NEW sample. "
            "Any OOS result is exploratory only."
        )

    return df


# ============================================================
# TRAIN / OOS SPLIT
# ============================================================

def split_train_oos(df):
    df = df.sort_values(
        ["capture_date", "recommendation_id"]
    ).reset_index(drop=True)

    split_index = int(
        np.floor(len(df) * TRAIN_RATIO)
    )

    # Ensure neither side is empty.
    split_index = max(
        1,
        min(split_index, len(df) - 1)
    )

    train = df.iloc[:split_index].copy()
    oos = df.iloc[split_index:].copy()

    return train, oos


# ============================================================
# TRAINING THRESHOLD SELECTION
# ============================================================

def evaluate_rule(df, rsi_threshold, return_3m_cutoff):
    selected = df[
        (df["rsi"] >= rsi_threshold)
        &
        (df["return_3m"] <= return_3m_cutoff)
    ].copy()

    return selected


def score_training_rule(train, rsi_threshold, return_3m_cutoff):
    selected = evaluate_rule(
        train,
        rsi_threshold,
        return_3m_cutoff
    )

    if len(selected) < MIN_TRAIN_BUCKET:
        return None

    # Primary training objective:
    # mean 5D return.
    #
    # 10D / 20D are secondary diagnostics only.
    if selected["return_5d_pct"].notna().sum() < MIN_TRAIN_BUCKET:
        return None

    mean_5d = selected["return_5d_pct"].mean()

    if pd.isna(mean_5d):
        return None

    positive_5d = (
        selected["return_5d_pct"] > 0
    ).mean()

    return {
        "rsi_threshold": rsi_threshold,
        "return_3m_cutoff": return_3m_cutoff,
        "n": len(selected),
        "mean_5d": mean_5d,
        "positive_5d": positive_5d,
    }


def learn_h1_rule(train):
    candidates = []

    for rsi_threshold in RSI_THRESHOLDS:
        for return_3m_cutoff in RETURN_3M_CUTOFFS:

            result = score_training_rule(
                train,
                rsi_threshold,
                return_3m_cutoff
            )

            if result is not None:
                candidates.append(result)

    if not candidates:
        raise ValueError(
            "Insufficient training observations to learn "
            "an H1 threshold combination."
        )

    # Rank by training 5D performance.
    #
    # This ranking is performed ONLY on the training set.
    # The selected thresholds are then frozen before OOS evaluation.
    candidates = sorted(
        candidates,
        key=lambda x: (
            x["mean_5d"],
            x["positive_5d"],
            x["n"],
        ),
        reverse=True
    )

    best = candidates[0]

    print()
    print("=" * 80)
    print("TRAINING — H1 THRESHOLD SEARCH")
    print("=" * 80)

    print(
        f"Training observations       : {len(train)}"
    )

    print(
        f"Candidate rules evaluated   : {len(candidates)}"
    )

    print()
    print(
        "Top training candidates:"
    )

    for candidate in candidates[:10]:
        print(
            f"  RSI >= {candidate['rsi_threshold']:>4.1f} "
            f"AND 3M <= {candidate['return_3m_cutoff']:>4.1f}%"
            f" | n={candidate['n']:>2}"
            f" | 5D mean={candidate['mean_5d']:>7.3f}%"
            f" | 5D positive={candidate['positive_5d'] * 100:>6.2f}%"
        )

    print()
    print(
        "FROZEN OOS RULE:"
    )
    print(
        f"  RSI >= {best['rsi_threshold']:.1f}"
    )
    print(
        f"  Return_3m <= {best['return_3m_cutoff']:.1f}%"
    )

    return best


# ============================================================
# PERFORMANCE
# ============================================================

def performance_summary(df, label):
    print()
    print(f"--- {label} ---")

    if df.empty:
        print("No observations.")
        return

    print(
        f"Observations : {len(df)}"
    )

    for horizon in [
        "return_5d_pct",
        "return_10d_pct",
        "return_20d_pct",
    ]:

        horizon_label = horizon.replace(
            "return_", ""
        ).replace(
            "_pct", ""
        ).upper()

        matured = df[
            df[horizon].notna()
        ]

        if matured.empty:
            print(
                f"{horizon_label:>3} : no matured observations"
            )
            continue

        mean_return = matured[horizon].mean()
        median_return = matured[horizon].median()
        positive_rate = (
            matured[horizon] > 0
        ).mean() * 100

        print(
            f"{horizon_label:>3} : "
            f"n={len(matured):>2} "
            f"mean={mean_return:>7.3f}% "
            f"median={median_return:>7.3f}% "
            f"positive={positive_rate:>6.2f}%"
        )


def compare_oos(oos, selected):
    print()
    print("=" * 80)
    print("OOS COMPARISON")
    print("=" * 80)

    performance_summary(
        oos,
        "OOS BUY NEW BASELINE"
    )

    performance_summary(
        selected,
        "OOS H1 SELECTED"
    )

    print()
    print("--- OOS H1 DELTA VS BASELINE ---")

    for horizon in [
        "return_5d_pct",
        "return_10d_pct",
        "return_20d_pct",
    ]:

        baseline = oos[
            oos[horizon].notna()
        ]

        h1 = selected[
            selected[horizon].notna()
        ]

        horizon_label = horizon.replace(
            "return_", ""
        ).replace(
            "_pct", ""
        ).upper()

        if baseline.empty or h1.empty:
            print(
                f"{horizon_label:>3} : insufficient matured data"
            )
            continue

        baseline_mean = baseline[horizon].mean()
        h1_mean = h1[horizon].mean()

        baseline_positive = (
            baseline[horizon] > 0
        ).mean() * 100

        h1_positive = (
            h1[horizon] > 0
        ).mean() * 100

        print(
            f"{horizon_label:>3} : "
            f"mean delta="
            f"{h1_mean - baseline_mean:>7.3f}pp "
            f"| positive-rate delta="
            f"{h1_positive - baseline_positive:>7.2f}pp "
            f"| H1 n={len(h1):>2} "
            f"| baseline n={len(baseline):>2}"
        )


# ============================================================
# OOS DETAIL
# ============================================================

def print_oos_detail(oos, selected, rule):
    selected_ids = set(
        selected["recommendation_id"]
    )

    detail = oos[
        [
            "capture_date",
            "recommendation_id",
            "ticker",
            "rsi",
            "return_3m",
            "technical_score",
            "investment_score",
            "return_5d_pct",
            "return_10d_pct",
            "return_20d_pct",
        ]
    ].copy()

    detail["H1_Selected"] = (
        detail["recommendation_id"]
        .isin(selected_ids)
    )

    detail = detail.sort_values(
        [
            "capture_date",
            "recommendation_id",
        ]
    )

    print()
    print("=" * 80)
    print("OOS OBSERVATIONS")
    print("=" * 80)

    print(
        f"Frozen rule: RSI >= {rule['rsi_threshold']:.1f} "
        f"AND Return_3m <= {rule['return_3m_cutoff']:.1f}%"
    )

    print()

    print(
        detail.to_string(
            index=False,
            formatters={
                "rsi": lambda x: f"{x:.1f}",
                "return_3m": lambda x: f"{x:.2f}",
                "technical_score": lambda x: f"{x:.1f}",
                "investment_score": lambda x: f"{x:.1f}",
                "return_5d_pct": lambda x: (
                    f"{x:.2f}" if pd.notna(x) else "-"
                ),
                "return_10d_pct": lambda x: (
                    f"{x:.2f}" if pd.notna(x) else "-"
                ),
                "return_20d_pct": lambda x: (
                    f"{x:.2f}" if pd.notna(x) else "-"
                ),
            }
        )
    )


# ============================================================
# MAIN
# ============================================================

def main():
    print()
    print("=" * 80)
    print("BUY NEW H1 WALK-FORWARD OOS TEST")
    print("=" * 80)

    print()
    print(
        "READ-ONLY TEST — NO PRODUCTION CHANGES"
    )

    df = load_buy_new_evidence()

    df = prepare_data(df)

    if len(df) < 10:
        print()
        print(
            "RESULT: INSUFFICIENT DATA"
        )
        print(
            "The BUY NEW evidence population is too small "
            "for a meaningful train/OOS test."
        )
        return

    train, oos = split_train_oos(df)

    print()
    print("=" * 80)
    print("CHRONOLOGICAL SPLIT")
    print("=" * 80)

    print(
        f"Training observations : {len(train)}"
    )

    print(
        f"OOS observations      : {len(oos)}"
    )

    print(
        f"Training period       : "
        f"{train['capture_date'].min().date()} "
        f"→ "
        f"{train['capture_date'].max().date()}"
    )

    print(
        f"OOS period            : "
        f"{oos['capture_date'].min().date()} "
        f"→ "
        f"{oos['capture_date'].max().date()}"
    )

    # Learn ONLY from training.
    rule = learn_h1_rule(train)

    # Apply frozen rule ONLY to OOS.
    oos_h1 = evaluate_rule(
        oos,
        rule["rsi_threshold"],
        rule["return_3m_cutoff"]
    )

    print()
    print(
        f"OOS observations selected by frozen H1 rule: "
        f"{len(oos_h1)} / {len(oos)}"
    )

    compare_oos(
        oos,
        oos_h1
    )

    print_oos_detail(
        oos,
        oos_h1,
        rule
    )

    # --------------------------------------------------------
    # FINAL INTERPRETATION
    # --------------------------------------------------------

    print()
    print("=" * 80)
    print("H1 OOS ASSESSMENT")
    print("=" * 80)

    baseline_5d = oos[
        oos["return_5d_pct"].notna()
    ]

    h1_5d = oos_h1[
        oos_h1["return_5d_pct"].notna()
    ]

    if baseline_5d.empty or h1_5d.empty:
        print(
            "INSUFFICIENT OOS EVIDENCE: "
            "no usable matured 5D comparison."
        )
        return

    baseline_mean = baseline_5d[
        "return_5d_pct"
    ].mean()

    h1_mean = h1_5d[
        "return_5d_pct"
    ].mean()

    delta = h1_mean - baseline_mean

    print(
        f"OOS 5D baseline mean : {baseline_mean:.3f}%"
    )

    print(
        f"OOS 5D H1 mean       : {h1_mean:.3f}%"
    )

    print(
        f"OOS 5D delta         : {delta:.3f}pp"
    )

    print(
        f"OOS H1 sample        : {len(h1_5d)}"
    )

    if len(h1_5d) < 5:
        print()
        print(
            "ASSESSMENT: INCONCLUSIVE"
        )
        print(
            "The OOS H1 sample is too small to support "
            "a production calibration decision."
        )

    elif delta > 0:
        print()
        print(
            "ASSESSMENT: H1 SHOWS POSITIVE OOS DIRECTION"
        )
        print(
            "This is evidence in favour of further testing, "
            "not evidence for immediate production change."
        )

    else:
        print()
        print(
            "ASSESSMENT: H1 NOT SUPPORTED OOS"
        )
        print(
            "The frozen H1 rule did not outperform the "
            "BUY NEW baseline on the OOS 5D measure."
        )

    print()
    print(
        "IMPORTANT: No production thresholds, weights, "
        "scoring logic or candidate-selection logic were changed."
    )


if __name__ == "__main__":
    main()
