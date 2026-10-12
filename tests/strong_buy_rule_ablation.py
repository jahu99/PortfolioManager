"""
STRONG BUY Rule Ablation / Near-Miss Forensics

READ-ONLY ANALYSIS
NO PRODUCTION CHANGES

Purpose:
    Test whether each individual component of the production
    STRONG BUY rule adds useful separation in realised 5D outcomes.

Production STRONG BUY rule:

    Investment Score >= 80
    Technical Score >= 75
    Quality Score >= 60
    Price > SMA200
    RSI between 40 and 75

For each rule component, this analysis identifies BUY observations
that satisfy the other four conditions but fail that one condition.

It also identifies observations that fail exactly one condition.

Data source:
    SQLite audit_decisions
    recommendation_evidence
    recommendation_evaluations

No production modules are imported or modified.
"""

from pathlib import Path
import sqlite3
import pandas as pd
import numpy as np


DB_PATH = Path("data/portfolio_manager.db")

RULES = {
    "investment": "investment_score >= 80",
    "technical": "technical_score >= 75",
    "quality": "quality_score >= 60",
    "trend": "entry_price > sma200",
    "rsi": "rsi BETWEEN 40 AND 75",
}


def load_data():
    conn = sqlite3.connect(DB_PATH)

    audit = pd.read_sql_query(
        """
        SELECT
            ad.id AS audit_decision_id,
            ad.audit_run_id,
            ad.ticker,
            ad.original_action,
            ad.proposed_action,
            ad.reconciled_action,
            ad.final_action,
            ad.recommendation_id,
            ar.run_date AS audit_date
        FROM audit_decisions ad
        JOIN audit_runs ar
            ON ar.id = ad.audit_run_id
        WHERE ad.original_action IN (
            'BUY MORE',
            'BUY NEW'
        )
        """,
        conn,
    )

    evidence = pd.read_sql_query(
        """
        SELECT
            recommendation_id,
            ticker,
            capture_date,
            signal,
            investment_score,
            technical_score,
            quality_score,
            growth_score,
            confidence_score,
            entry_price,
            rsi,
            sma200,
            extension_sma200_pct,
            entry_quality
        FROM recommendation_evidence
        """,
        conn,
    )

    evaluations = pd.read_sql_query(
        """
        SELECT
            recommendation_id,
            ticker,
            days_after,
            return_percent
        FROM recommendation_evaluations
        WHERE days_after = 5
          AND return_percent IS NOT NULL
        """,
        conn,
    )

    conn.close()

    return audit, evidence, evaluations

def reconstruct_lineage(audit, evidence, evaluations):
    """
    Reconstruct recommendation lineage.

    Prefer direct recommendation_id lineage.

    For legacy audit rows without recommendation_id, use the most
    recent evidence record for the same ticker captured on or before
    the audit date.
    """

    audit = audit.copy()

    audit["audit_date"] = pd.to_datetime(
        audit["audit_date"],
        errors="coerce",
        utc=True,
    )

    evidence = evidence.copy()

    evidence["capture_date"] = pd.to_datetime(
        evidence["capture_date"],
        errors="coerce",
        utc=True,
    )

    # ------------------------------------------------------------
    # Direct recommendation lineage
    # ------------------------------------------------------------

    direct = audit[
        audit["recommendation_id"].notna()
    ].copy()

    direct = direct.merge(
        evidence,
        on="recommendation_id",
        how="left",
        suffixes=("", "_evidence"),
    )

    direct = direct.merge(
        evaluations,
        on=[
            "recommendation_id",
            "ticker",
        ],
        how="left",
        suffixes=("", "_evaluation"),
    )

    # ------------------------------------------------------------
    # Legacy lineage
    # ------------------------------------------------------------

    legacy = audit[
        audit["recommendation_id"].isna()
    ].copy()

    legacy_matches = []

    if not legacy.empty:

        legacy = legacy[
            legacy["audit_date"].notna()
        ].copy()

        evidence_legacy = evidence[
            evidence["capture_date"].notna()
        ].copy()

        for ticker, legacy_group in legacy.groupby(
            "ticker",
            sort=False,
        ):

            evidence_group = evidence_legacy[
                evidence_legacy["ticker"] == ticker
            ].copy()

            if evidence_group.empty:
                continue

            legacy_group = legacy_group.sort_values(
                "audit_date"
            ).copy()

            evidence_group = evidence_group.sort_values(
                "capture_date"
            ).copy()

            matched = pd.merge_asof(
                legacy_group,
                evidence_group,
                left_on="audit_date",
                right_on="capture_date",
                direction="backward",
                suffixes=(
                    "",
                    "_evidence",
                ),
            )

            legacy_matches.append(
                matched
            )

    if legacy_matches:

        legacy = pd.concat(
            legacy_matches,
            ignore_index=True,
        )

        # The audit row has a null recommendation_id.
        # merge_asof therefore retains the evidence recommendation_id
        # as recommendation_id_evidence.
        #
        # Use that evidence ID as the reconstructed lineage ID so the
        # realised evaluation can be recovered below.

        if "recommendation_id_evidence" in legacy.columns:

            legacy["recommendation_id"] = (
                legacy[
                    "recommendation_id_evidence"
                ]
            )

        legacy = legacy.merge(
            evaluations,
            on=[
                "recommendation_id",
                "ticker",
            ],
            how="left",
            suffixes=(
                "",
                "_evaluation",
            ),
        )

    else:

        legacy = pd.DataFrame(
            columns=direct.columns
        )

    # ------------------------------------------------------------
    # Combine direct and reconstructed lineage
    # ------------------------------------------------------------

    result = pd.concat(
        [
            direct,
            legacy,
        ],
        ignore_index=True,
    )

    return result

def numeric_columns(df):
    columns = [
        "investment_score",
        "technical_score",
        "quality_score",
        "growth_score",
        "confidence_score",
        "entry_price",
        "rsi",
        "sma200",
        "extension_sma200_pct",
        "return_percent",
    ]

    for col in columns:
        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col],
                errors="coerce",
            )

    return df


def add_rule_flags(df):
    df = df.copy()

    df["rule_investment"] = (
        df["investment_score"] >= 80
    )

    df["rule_technical"] = (
        df["technical_score"] >= 75
    )

    df["rule_quality"] = (
        df["quality_score"] >= 60
    )

    df["rule_trend"] = (
        df["entry_price"] > df["sma200"]
    )

    df["rule_rsi"] = (
        df["rsi"].between(40, 75)
    )

    rule_columns = [
        "rule_investment",
        "rule_technical",
        "rule_quality",
        "rule_trend",
        "rule_rsi",
    ]

    df["rules_passed"] = df[
        rule_columns
    ].sum(axis=1)

    df["rules_failed"] = (
        5 - df["rules_passed"]
    )

    return df


def summary(df, label):
    if df.empty:
        return {
            "group": label,
            "n": 0,
            "mean_5d": np.nan,
            "median_5d": np.nan,
            "positive_pct": np.nan,
        }

    returns = df["return_percent"].dropna()

    return {
        "group": label,
        "n": len(returns),
        "mean_5d": returns.mean(),
        "median_5d": returns.median(),
        "positive_pct": (
            (returns > 0).mean() * 100
        ),
    }


def print_separator(title):
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)
    print()

def main():

    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database not found: {DB_PATH}"
        )

    audit, evidence, evaluations = load_data()

    # ------------------------------------------------------------
    # Build the forensic population directly from the immutable
    # recommendation evidence snapshot.
    #
    # recommendation_evidence.signal contains the actual
    # recommendation signal (BUY / STRONG BUY).
    #
    # audit_decisions.original_action contains the portfolio action
    # and must not be used to identify BUY or STRONG BUY signals.
    # ------------------------------------------------------------

    df = evidence.merge(
        evaluations,
        on=[
            "recommendation_id",
            "ticker",
        ],
        how="inner",
    ).copy()

    df = numeric_columns(df)

    # ------------------------------------------------------------
    # Keep only mature observations with complete rule inputs.
    # ------------------------------------------------------------

    required = [
        "investment_score",
        "technical_score",
        "quality_score",
        "entry_price",
        "sma200",
        "rsi",
        "return_percent",
    ]

    df = df.dropna(
        subset=required
    ).copy()

    df = add_rule_flags(df)

    # ------------------------------------------------------------
    # Actual STRONG BUY population
    # ------------------------------------------------------------

    strong_buy = df[
        (
            df["rule_investment"]
            & df["rule_technical"]
            & df["rule_quality"]
            & df["rule_trend"]
            & df["rule_rsi"]
        )
    ].copy()

    # ------------------------------------------------------------
    # BUY control population
    # ------------------------------------------------------------

    buy = df[
        df["signal"]
        .astype(str)
        .str.upper()
        .eq("BUY")
    ].copy()

    print_separator(
        "STRONG BUY RULE ABLATION / NEAR-MISS FORENSICS"
    )

    print(
        "READ-ONLY — NO PRODUCTION CHANGES"
    )

    print()

    print(
        f"Complete mature 5D observations: {len(df)}"
    )

    print(
        f"STRONG BUY observations: {len(strong_buy)}"
    )

    print(
        f"BUY observations: {len(buy)}"
    )

    # ------------------------------------------------------------
    # Baseline
    # ------------------------------------------------------------

    print_separator(
        "1. BASELINE"
    )

    baseline = pd.DataFrame(
        [
            summary(
                strong_buy,
                "STRONG BUY",
            ),
            summary(
                buy,
                "BUY",
            ),
        ]
    )

    print(
        baseline.to_string(
            index=False,
            float_format=lambda x: f"{x:.3f}",
        )
    )

    # ------------------------------------------------------------
    # Component ablation
    # ------------------------------------------------------------

    print_separator(
        "2. COMPONENT NEAR-MISS ANALYSIS"
    )

    results = []

    component_map = {
        "investment": "rule_investment",
        "technical": "rule_technical",
        "quality": "rule_quality",
        "trend": "rule_trend",
        "rsi": "rule_rsi",
    }

    for component, column in component_map.items():

        other_columns = [
            c
            for name, c in component_map.items()
            if name != component
        ]

        # BUY observations which satisfy every other
        # STRONG BUY condition but fail this condition.
        near_miss = buy[
            (~buy[column])
            & buy[other_columns].all(axis=1)
        ].copy()

        result = summary(
            near_miss,
            f"BUY near-miss: {component}",
        )

        results.append(result)

    component_results = pd.DataFrame(
        results
    )

    print(
        component_results.to_string(
            index=False,
            float_format=lambda x: f"{x:.3f}",
        )
    )

    # ------------------------------------------------------------
    # Exactly one failed condition
    # ------------------------------------------------------------

    print_separator(
        "3. EXACTLY ONE FAILED STRONG BUY CONDITION"
    )

    exactly_one = buy[
        buy["rules_failed"] == 1
    ].copy()

    print(
        f"BUY observations failing exactly one condition: "
        f"{len(exactly_one)}"
    )

    if not exactly_one.empty:

        rows = []

        for component, column in component_map.items():

            failed = exactly_one[
                ~exactly_one[column]
            ].copy()

            if not failed.empty:
                rows.append(
                    summary(
                        failed,
                        f"Fails only: {component}",
                    )
                )

        exactly_one_results = pd.DataFrame(
            rows
        )

        print()

        print(
            exactly_one_results.to_string(
                index=False,
                float_format=lambda x: f"{x:.3f}",
            )
        )

    else:
        print(
            "No observations."
        )

    # ------------------------------------------------------------
    # STRONG BUY versus near-misses
    # ------------------------------------------------------------

    print_separator(
        "4. STRONG BUY VS NEAR-MISS DELTAS"
    )

    strong_summary = summary(
        strong_buy,
        "STRONG BUY",
    )

    comparison_rows = []

    for component, column in component_map.items():

        other_columns = [
            c
            for name, c in component_map.items()
            if name != component
        ]

        near_miss = buy[
            (~buy[column])
            & buy[other_columns].all(axis=1)
        ].copy()

        near_summary = summary(
            near_miss,
            f"Near-miss: {component}",
        )

        if (
            strong_summary["n"] > 0
            and near_summary["n"] > 0
        ):
            comparison_rows.append(
                {
                    "failed_condition": component,
                    "strong_buy_n": strong_summary["n"],
                    "near_miss_n": near_summary["n"],
                    "strong_buy_mean_5d":
                        strong_summary["mean_5d"],
                    "near_miss_mean_5d":
                        near_summary["mean_5d"],
                    "incremental_mean":
                        (
                            strong_summary["mean_5d"]
                            - near_summary["mean_5d"]
                        ),
                    "strong_buy_positive_pct":
                        strong_summary["positive_pct"],
                    "near_miss_positive_pct":
                        near_summary["positive_pct"],
                }
            )

    if comparison_rows:

        comparison = pd.DataFrame(
            comparison_rows
        )

        print(
            comparison.to_string(
                index=False,
                float_format=lambda x: f"{x:.3f}",
            )
        )

    else:
        print(
            "No component comparisons available."
        )

    # ------------------------------------------------------------
    # Exact STRONG BUY rule verification
    # ------------------------------------------------------------

    print_separator(
        "5. STRONG BUY RULE VERIFICATION"
    )

    verification = pd.DataFrame(
        [
            {
                "condition": "Investment >= 80",
                "passed": int(
                    strong_buy["rule_investment"].sum()
                ),
                "total": len(strong_buy),
            },
            {
                "condition": "Technical >= 75",
                "passed": int(
                    strong_buy["rule_technical"].sum()
                ),
                "total": len(strong_buy),
            },
            {
                "condition": "Quality >= 60",
                "passed": int(
                    strong_buy["rule_quality"].sum()
                ),
                "total": len(strong_buy),
            },
            {
                "condition": "Price > SMA200",
                "passed": int(
                    strong_buy["rule_trend"].sum()
                ),
                "total": len(strong_buy),
            },
            {
                "condition": "RSI 40-75",
                "passed": int(
                    strong_buy["rule_rsi"].sum()
                ),
                "total": len(strong_buy),
            },
        ]
    )

    verification["pass_pct"] = (
        verification["passed"]
        / verification["total"]
        * 100
    ).replace(
        [np.inf, -np.inf],
        np.nan,
    )

    print(
        verification.to_string(
            index=False,
            float_format=lambda x: f"{x:.3f}",
        )
    )

    # ------------------------------------------------------------
    # STRONG BUY outcome distribution
    # ------------------------------------------------------------

    print_separator(
        "6. STRONG BUY WINNERS VS LOSERS"
    )

    strong_buy["outcome"] = np.where(
        strong_buy["return_percent"] > 0,
        "WINNER",
        "LOSER",
    )

    winner_loser = (
        strong_buy
        .groupby("outcome")
        .agg(
            n=("return_percent", "size"),
            mean_5d=("return_percent", "mean"),
            median_5d=("return_percent", "median"),
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
            rsi=("rsi", "mean"),
            entry_price=("entry_price", "mean"),
            sma200=("sma200", "mean"),
            extension_sma200_pct=(
                "extension_sma200_pct",
                "mean",
            ),
        )
        .reset_index()
    )

    print(
        winner_loser.to_string(
            index=False,
            float_format=lambda x: f"{x:.3f}",
        )
    )

    # ------------------------------------------------------------
    # Component failure counts in BUY population
    # ------------------------------------------------------------

    print_separator(
        "7. BUY POPULATION — CONDITION FAILURE COUNTS"
    )

    failure_rows = []

    for component, column in component_map.items():

        failed = buy[
            ~buy[column]
        ]

        failure_rows.append(
            {
                "condition": component,
                "BUY observations failing":
                    len(failed),
                "BUY observations passing":
                    int(
                        buy[column].sum()
                    ),
            }
        )

    failures = pd.DataFrame(
        failure_rows
    )

    print(
        failures.to_string(
            index=False
        )
    )

    # ------------------------------------------------------------
    # Conclusion guidance
    # ------------------------------------------------------------

    print_separator(
        "8. INTERPRETATION GUIDE"
    )

    print(
        "This test is descriptive, not causal."
    )

    print(
        "A component should only be considered for calibration"
    )

    print(
        "if its near-miss comparison has sufficient sample size,"
    )

    print(
        "a meaningful and persistent outcome difference, and"
    )

    print(
        "the result survives further out-of-sample validation."
    )

    print()

    print(
        "Do NOT change the STRONG BUY production rule from this"
    )

    print(
        "test alone."
    )

    print_separator(
        "END — READ-ONLY ANALYSIS"
    )




if __name__ == "__main__":
    main()
