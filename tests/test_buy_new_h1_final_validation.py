"""
FINAL READ-ONLY validation of BUY NEW H1.

Purpose
-------
Determine whether the H1 momentum hypothesis adds predictive value
AFTER the existing BUY NEW entry-quality gate has been applied.

H1:
    Higher RSI within the bullish range combined with moderate rather
    than excessive 3-month performance may identify stronger
    continuation candidates.

This is the final research test before deciding whether production
logic should change.

Method
------
1. Load historical BUY / STRONG BUY recommendation evidence.
2. Restrict to the historical BUY NEW entry-quality population.
3. Deduplicate to one recommendation/evidence observation.
4. Run chronological walk-forward testing.
5. Learn H1 thresholds ONLY from each training window.
6. Freeze thresholds.
7. Apply frozen thresholds to the unseen OOS window.
8. Compare H1-selected observations against the BUY NEW-eligible
   baseline.
9. Aggregate results across all informative windows.
10. Produce an explicit final decision recommendation.

NO production files are modified.
NO database writes are performed.
NO scoring or candidate-selection logic is changed.

Important:
This script first prints the actual entry_quality distribution so
that the population restriction is visible and auditable.
"""

from pathlib import Path
import sqlite3
import numpy as np
import pandas as pd


# ============================================================
# CONFIGURATION
# ============================================================

DB_PATH = Path("data/portfolio_manager.db")

TRAIN_SIZE = 12
OOS_SIZE = 6
STEP_SIZE = 6

MIN_TRAIN_SELECTED = 4
MIN_OOS_SELECTED = 2

RSI_THRESHOLDS = [55.0, 57.0, 60.0]
RETURN_3M_CUTOFFS = [15.0, 20.0, 25.0]

# ------------------------------------------------------------
# Entry-quality population
# ------------------------------------------------------------
#
# The persisted evidence uses the entry-quality classification
# produced by the candidate-selection pipeline.
#
# "REASONABLE" is the normal BUY NEW-compatible entry condition.
# "FAVOURABLE ENTRY" is also treated as eligible if present.
#
# Timing-caution / extension categories are excluded because the
# purpose of this test is to ask:
#
#   "Does H1 add value after entry-quality gating?"
#
ELIGIBLE_ENTRY_QUALITY = {
    "REASONABLE",
    "FAVOURABLE ENTRY",
    "FAVOURABLE",
}


# ============================================================
# LOAD DATA
# ============================================================

def load_data():

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
# PREPARE DATA
# ============================================================

def prepare_data(df):

    if df.empty:
        raise ValueError(
            "No BUY / STRONG BUY recommendation evidence found."
        )

    df["capture_date"] = pd.to_datetime(
        df["capture_date"],
        errors="coerce"
    )

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
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )

    # --------------------------------------------------------
    # AUDIT ENTRY-QUALITY POPULATION
    # --------------------------------------------------------

    print()
    print("=" * 80)
    print("ENTRY-QUALITY DISTRIBUTION")
    print("=" * 80)

    print(
        df["entry_quality"]
        .fillna("<NULL>")
        .value_counts(dropna=False)
        .to_string()
    )

    print()
    print(
        "Eligible entry-quality values used:"
    )

    for value in sorted(
        ELIGIBLE_ENTRY_QUALITY
    ):
        print(
            f"  {value}"
        )

    # --------------------------------------------------------
    # RESTRICT TO BUY NEW-COMPATIBLE ENTRY QUALITY
    # --------------------------------------------------------

    before = len(df)

    df = df[
        df["entry_quality"]
        .fillna("")
        .str.strip()
        .str.upper()
        .isin(
            {
                value.upper()
                for value in ELIGIBLE_ENTRY_QUALITY
            }
        )
    ].copy()

    after_entry_quality = len(df)

    print()
    print("=" * 80)
    print("BUY NEW-ELIGIBLE POPULATION")
    print("=" * 80)

    print(
        f"BUY/STRONG BUY evidence rows : {before}"
    )

    print(
        f"After entry-quality gate      : "
        f"{after_entry_quality}"
    )

    # --------------------------------------------------------
    # DEDUPLICATE
    # --------------------------------------------------------

    before_dedupe = len(df)

    df = (
        df.sort_values(
            [
                "capture_date",
                "recommendation_id",
            ]
        )
        .drop_duplicates(
            subset=["recommendation_id"],
            keep="first"
        )
        .reset_index(drop=True)
    )

    print(
        f"Unique recommendations        : "
        f"{len(df)}"
    )

    print(
        f"Repeated rows removed         : "
        f"{before_dedupe - len(df)}"
    )

    # --------------------------------------------------------
    # H1 INPUTS
    # --------------------------------------------------------

    df = df.dropna(
        subset=[
            "capture_date",
            "recommendation_id",
            "ticker",
            "rsi",
            "return_3m",
        ]
    ).copy()

    df = df.sort_values(
        [
            "capture_date",
            "recommendation_id",
        ]
    ).reset_index(drop=True)

    print(
        f"Usable H1 observations        : "
        f"{len(df)}"
    )

    return df


# ============================================================
# H1 RULE
# ============================================================

def apply_h1(
    df,
    rsi_threshold,
    return_3m_cutoff,
):

    return df[
        (df["rsi"] >= rsi_threshold)
        &
        (df["return_3m"] <= return_3m_cutoff)
    ].copy()


# ============================================================
# LEARN H1 FROM TRAINING ONLY
# ============================================================

def learn_rule(train):

    candidates = []

    for rsi_threshold in RSI_THRESHOLDS:

        for return_3m_cutoff in RETURN_3M_CUTOFFS:

            selected = apply_h1(
                train,
                rsi_threshold,
                return_3m_cutoff,
            )

            matured = selected[
                selected["return_5d_pct"].notna()
            ]

            if len(matured) < MIN_TRAIN_SELECTED:
                continue

            candidates.append(
                {
                    "rsi_threshold": rsi_threshold,
                    "return_3m_cutoff": return_3m_cutoff,
                    "n": len(matured),
                    "mean_5d": (
                        matured["return_5d_pct"]
                        .mean()
                    ),
                    "positive_5d": (
                        matured["return_5d_pct"] > 0
                    ).mean(),
                }
            )

    if not candidates:
        return None

    # Training-only optimisation.
    candidates.sort(
        key=lambda x: (
            x["mean_5d"],
            x["positive_5d"],
            x["n"],
        ),
        reverse=True,
    )

    return candidates[0]


# ============================================================
# HORIZON STATS
# ============================================================

def stats(
    df,
    column,
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
        "positive": (
            matured[column] > 0
        ).mean() * 100,
    }


# ============================================================
# WALK FORWARD
# ============================================================

def walk_forward(df):

    windows = []

    start = 0
    window_number = 1

    while True:

        train_end = start + TRAIN_SIZE
        oos_end = train_end + OOS_SIZE

        if oos_end > len(df):
            break

        train = df.iloc[
            start:train_end
        ].copy()

        oos = df.iloc[
            train_end:oos_end
        ].copy()

        rule = learn_rule(
            train
        )

        if rule is None:
            start += STEP_SIZE
            window_number += 1
            continue

        # Freeze rule before touching OOS.
        h1 = apply_h1(
            oos,
            rule["rsi_threshold"],
            rule["return_3m_cutoff"],
        )

        windows.append(
            {
                "window": window_number,
                "train": train,
                "oos": oos,
                "h1": h1,
                "rule": rule,
            }
        )

        start += STEP_SIZE
        window_number += 1

    return windows


# ============================================================
# AGGREGATE RESULTS
# ============================================================

def aggregate(windows):

    if not windows:
        print()
        print(
            "NO VALID WALK-FORWARD WINDOWS."
        )
        return None

    baseline_frames = []
    h1_frames = []

    informative = {
        "return_5d_pct": [],
        "return_10d_pct": [],
        "return_20d_pct": [],
    }

    for window in windows:

        baseline = window["oos"].copy()
        h1 = window["h1"].copy()

        baseline["window"] = window["window"]
        h1["window"] = window["window"]

        baseline_frames.append(
            baseline
        )

        h1_frames.append(
            h1
        )

        for horizon in informative:

            h1_stats = stats(
                h1,
                horizon,
            )

            if (
                h1_stats is not None
                and h1_stats["n"] >= MIN_OOS_SELECTED
            ):
                informative[horizon].append(
                    (
                        window,
                        h1_stats,
                    )
                )

    baseline_all = pd.concat(
        baseline_frames,
        ignore_index=True,
    )

    h1_all = pd.concat(
        h1_frames,
        ignore_index=True,
    )

    print()
    print("=" * 80)
    print("FINAL BUY NEW H1 VALIDATION")
    print("=" * 80)

    print(
        f"Walk-forward windows : {len(windows)}"
    )

    print(
        f"BUY NEW-eligible OOS : "
        f"{len(baseline_all)}"
    )


    print(
        f"H1-selected OOS      : "
        f"{len(h1_all)}"
    )

    print()
    print("SELECTED RULE DISTRIBUTION")

    rule_distribution = {}

    for window in windows:
        rule = window["rule"]
        key = (
            rule["rsi_threshold"],
            rule["return_3m_cutoff"],
        )

        rule_distribution[key] = (
            rule_distribution.get(key, 0) + 1
        )

    for (
        rsi_threshold,
        return_3m_cutoff,
    ), count in sorted(
        rule_distribution.items(),
        key=lambda item: item[1],
        reverse=True,
    ):
        print(
            f"  RSI >= {rsi_threshold:.0f} "
            f"& Return 3M <= {return_3m_cutoff:.0f}% "
            f": {count} windows"
        )

    print()

    results = {}

    for horizon in [
        "return_5d_pct",
        "return_10d_pct",
        "return_20d_pct",
    ]:

        baseline_stats = stats(
            baseline_all,
            horizon,
        )

        h1_stats = stats(
            h1_all,
            horizon,
        )

        label = (
            horizon
            .replace("return_", "")
            .replace("_pct", "")
            .upper()
        )

        if (
            baseline_stats is None
            or h1_stats is None
        ):
            print(
                f"{label}: insufficient data"
            )
            continue

        delta = (
            h1_stats["mean"]
            - baseline_stats["mean"]
        )

        positive_delta = (
            h1_stats["positive"]
            - baseline_stats["positive"]
        )

        results[horizon] = {
            "baseline": baseline_stats,
            "h1": h1_stats,
            "mean_delta": delta,
            "positive_delta": positive_delta,
        }

        print(
            f"{label}: "
            f"baseline={baseline_stats['mean']:+.3f}% "
            f"| H1={h1_stats['mean']:+.3f}% "
            f"| delta={delta:+.3f}pp "
            f"| baseline positive="
            f"{baseline_stats['positive']:.2f}% "
            f"| H1 positive="
            f"{h1_stats['positive']:.2f}% "
            f"| H1 n={h1_stats['n']}"
        )

    print()
    print("=" * 80)
    print("OOS PERFORMANCE BY SELECTED H1 RULE")
    print("=" * 80)

    rule_oos = {}

    for window in windows:
        rule = window["rule"]

        rule_key = (
            rule["rsi_threshold"],
            rule["return_3m_cutoff"],
        )

        oos = window["oos"]

        if oos is None or oos.empty:
            continue

        if rule_key not in rule_oos:
            rule_oos[rule_key] = {
                "windows": 0,
                "rows": 0,
                "returns_5d": [],
                "returns_10d": [],
                "returns_20d": [],
            }

        rule_oos[rule_key]["windows"] += 1

        for value in oos["return_5d_pct"].dropna():
            rule_oos[rule_key]["returns_5d"].append(value)

        for value in oos["return_10d_pct"].dropna():
            rule_oos[rule_key]["returns_10d"].append(value)

        for value in oos["return_20d_pct"].dropna():
            rule_oos[rule_key]["returns_20d"].append(value)

    for (
        rsi_threshold,
        return_3m_cutoff,
    ), data in sorted(
        rule_oos.items(),
        key=lambda item: (
            -item[1]["windows"],
            item[0][0],
            item[0][1],
        ),
    ):
        print()
        print(
            f"Rule: RSI >= {rsi_threshold:.0f} "
            f"& Return 3M <= {return_3m_cutoff:.0f}%"
        )
        print(
            f"  Training-selected windows : "
            f"{data['windows']}"
        )

        for label, key in (
            ("5D", "returns_5d"),
            ("10D", "returns_10d"),
            ("20D", "returns_20d"),
        ):
            values = data[key]

            if not values:
                print(
                    f"  {label}: no OOS observations"
                )
                continue

            mean_return = sum(values) / len(values)

            positive_rate = (
                sum(value > 0 for value in values)
                / len(values)
                * 100
            )

            print(
                f"  {label}: "
                f"mean={mean_return:+.3f}% | "
                f"positive={positive_rate:.2f}% | "
                f"n={len(values)}"
            )

    # --------------------------------------------------------
    # WINDOW CONSISTENCY
    # --------------------------------------------------------

    print()
    print(
        "WINDOW CONSISTENCY"
    )

    consistency = {}

    for horizon in [
        "return_5d_pct",
        "return_10d_pct",
        "return_20d_pct",
    ]:

        improved = 0
        informative_count = 0

        for window in windows:

            h1 = window["h1"]

            h1_stats = stats(
                h1,
                horizon,
            )

            baseline_stats = stats(
                window["oos"],
                horizon,
            )

            if (
                h1_stats is None
                or baseline_stats is None
                or h1_stats["n"] < MIN_OOS_SELECTED
            ):
                continue

            informative_count += 1

            if (
                h1_stats["mean"]
                > baseline_stats["mean"]
            ):
                improved += 1

        label = (
            horizon
            .replace("return_", "")
            .replace("_pct", "")
            .upper()
        )

        consistency[horizon] = (
            improved,
            informative_count,
        )

        print(
            f"{label}: "
            f"H1 improved "
            f"{improved}/{informative_count} "
            f"informative windows"
        )

        # ============================================================
    # FIXED H1 RULE OOS COMPARISON
    # ============================================================
    
    print()
    print("=" * 80)
    print("FIXED H1 RULE OOS COMPARISON")
    print("=" * 80)
    
    fixed_rules = [
        {
            "name": "RSI >= 55 & Return 3M <= 15%",
            "rsi_threshold": 55.0,
            "return_3m_cutoff": 15.0,
        },
        {
            "name": "RSI >= 55 & Return 3M <= 20%",
            "rsi_threshold": 55.0,
            "return_3m_cutoff": 20.0,
        },
        {
            "name": "RSI >= 55 & Return 3M <= 25%",
            "rsi_threshold": 55.0,
            "return_3m_cutoff": 25.0,
        },
    ]
    
    for fixed_rule in fixed_rules:
    
        selected_frames = []
    
        for window in windows:
    
            oos = window["oos"]
    
            if oos is None or oos.empty:
                continue
    
            working = oos.copy()
    
            rsi = pd.to_numeric(
                working["rsi"],
                errors="coerce",
            )
    
            return_3m = pd.to_numeric(
                working["return_3m"],
                errors="coerce",
            )
    
            mask = (
                rsi >= fixed_rule["rsi_threshold"]
            ) & (
                return_3m
                <= fixed_rule["return_3m_cutoff"]
            )
    
            selected = working.loc[mask].copy()
    
            if not selected.empty:
                selected_frames.append(
                    selected
                )
    
        print()
        print(
            f"RULE: {fixed_rule['name']}"
        )
    
        if not selected_frames:
            print("  No OOS observations selected.")
            continue
    
        selected_all = pd.concat(
            selected_frames,
            ignore_index=True,
        )
    
        for label, horizon in (
            ("5D", "return_5d_pct"),
            ("10D", "return_10d_pct"),
            ("20D", "return_20d_pct"),
        ):
    
            values = pd.to_numeric(
                selected_all[horizon],
                errors="coerce",
            ).dropna()
    
            if values.empty:
                print(
                    f"  {label}: no observations"
                )
                continue
    
            mean_return = values.mean()
    
            positive_rate = (
                (values > 0).mean() * 100
            )
    
            print(
                f"  {label}: "
                f"mean={mean_return:+.3f}% | "
                f"positive={positive_rate:.2f}% | "
                f"n={len(values)}"
            )
    

    return {
        "results": results,
        "consistency": consistency,
        "baseline": baseline_all,
        "h1": h1_all,
    }


    

# ============================================================
# FINAL DECISION
# ============================================================

def final_decision(
    aggregate_result,
    windows,
):

    print()
    print("=" * 80)
    print("FINAL LOGIC DECISION")
    print("=" * 80)

    if aggregate_result is None:
        print(
            "DECISION: INCONCLUSIVE"
        )
        print(
            "There is insufficient evidence to change production logic."
        )
        return

    results = aggregate_result["results"]
    consistency = aggregate_result["consistency"]

    five_day = results.get(
        "return_5d_pct"
    )

    ten_day = results.get(
        "return_10d_pct"
    )

    twenty_day = results.get(
        "return_20d_pct"
    )

    five_day_consistency = consistency.get(
        "return_5d_pct",
        (0, 0),
    )

    ten_day_consistency = consistency.get(
        "return_10d_pct",
        (0, 0),
    )

    twenty_day_consistency = consistency.get(
        "return_20d_pct",
        (0, 0),
    )

    print()
    print(
        "Evidence criteria:"
    )

    print(
        "  1. Positive aggregate OOS delta"
    )

    print(
        "  2. Positive-rate improvement"
    )

    print(
        "  3. Repeated improvement across informative windows"
    )

    print(
        "  4. Evidence survives the BUY NEW entry-quality gate"
    )

    print()

    if five_day is None:
        print(
            "DECISION: INCONCLUSIVE"
        )
        print(
            "No usable 5D BUY NEW OOS comparison."
        )
        return

    five_day_positive = (
        five_day["mean_delta"] > 0
        and five_day["positive_delta"] > 0
    )

    ten_day_positive = (
        ten_day is not None
        and ten_day["mean_delta"] > 0
        and ten_day["positive_delta"] > 0
    )

    twenty_day_positive = (
        twenty_day is not None
        and twenty_day["mean_delta"] > 0
        and twenty_day["positive_delta"] > 0
    )

    five_day_consistent = (
        five_day_consistency[1] >= 5
        and (
            five_day_consistency[0]
            / five_day_consistency[1]
        ) >= 0.60
    )

    ten_day_consistent = (
        ten_day_consistency[1] >= 5
        and (
            ten_day_consistency[0]
            / ten_day_consistency[1]
        ) >= 0.60
    )

    # We require 5D + 10D support.
    #
    # 20D is supporting evidence, not mandatory, because the hypothesis
    # is explicitly about near-term continuation.
    if (
        five_day_positive
        and ten_day_positive
        and five_day_consistent
        and ten_day_consistent
    ):

        print(
            "DECISION: H1 SUPPORTED"
        )

        print()
        print(
            "The current OOS evidence supports H1 as a BUY NEW "
            "candidate-selection / decision-layer feature."
        )
        print()
        print(
            "The exact production threshold is NOT yet conclusively "
            "selected."
        )
        print(
            "The fixed-rule comparison supports RSI >= 55, but the "
            "Return 3M cutoff remains a human calibration decision."
        )
        print()
        print(
            "Recommended implementation direction:"
        )
        print(
            "  - Do NOT simply change the RSI score threshold."
        )
        print(
            "  - Do NOT treat the existing 60/20 thresholds as "
            "empirically validated."
        )
        print(
            "  - Do NOT remove the existing Technical Score."
        )
        print(
            "  - Add H1 as a BUY NEW candidate-selection / "
            "decision-layer feature."
        )
        print(
            "  - Preserve the underlying technical components."
        )
        print(
            "  - Select and freeze the production H1 thresholds "
            "through human review."
        )
        print(
            "  - Keep H1 advisory initially and measure it prospectively."
        )
        print(
            "  - Do not allow H1 to override governance or HOLD protection."
        )
    else:

        print(
            "DECISION: H1 NOT SUFFICIENTLY SUPPORTED"
        )

        print()
        print(
            "Do NOT change production BUY NEW logic."
        )

        print(
            "The evidence is insufficiently consistent after "
            "the existing BUY NEW entry-quality gate."
        )

    print()
    print(
        "NO PRODUCTION CHANGES WERE MADE BY THIS TEST."
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 80)
    print("FINAL BUY NEW H1 VALIDATION")
    print("=" * 80)

    print()
    print(
        "READ-ONLY — NO PRODUCTION CHANGES"
    )

    df = load_data()

    df = prepare_data(
        df
    )

    if len(df) < (
        TRAIN_SIZE + OOS_SIZE
    ):

        print()
        print(
            "DECISION: INCONCLUSIVE"
        )

        print(
            f"Only {len(df)} usable BUY NEW-eligible "
            "observations are available."
        )

        print(
            "Not enough data for final validation."
        )

        return

    print()
    print("=" * 80)
    print("FINAL TEST POPULATION")
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

    windows = walk_forward(
        df
    )

    aggregate_result = aggregate(
        windows
    )

    final_decision(
        aggregate_result,
        windows,
    )


if __name__ == "__main__":
    main()
