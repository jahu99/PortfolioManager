"""
A6 — HOLD Performance Investigation

READ-ONLY DIAGNOSTIC
--------------------
Investigates historical FINAL HOLD decisions using:
    audit_decisions.final_action
    recommendations / recommendation_id
    recommendation_evidence (point-in-time evidence)
    recommendation_evaluations (realised 5D outcome)

This module:
    - does NOT change production logic
    - does NOT change thresholds
    - does NOT change weights
    - does NOT write to the database

Outputs:
    calibration/output/hold_score_bands.csv
    calibration/output/hold_technical_bands.csv
    calibration/output/hold_signal_bands.csv
    calibration/output/hold_good_bad_outcomes.csv
    calibration/output/hold_current_boundary_summary.csv
"""

from pathlib import Path
import sqlite3

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "portfolio_manager.db"
OUTPUT_DIR = PROJECT_ROOT / "calibration" / "output"


def load_data():
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database not found: {DB_PATH}"
        )

    conn = sqlite3.connect(DB_PATH)

    audit = pd.read_sql_query(
        """
        SELECT
            ad.id AS audit_decision_id,
            ad.audit_run_id,
            ar.run_date AS audit_date,
            ad.recommendation_id,
            ad.ticker,
            ad.asset_type,
            ad.final_action,
            ad.proposed_action,
            ad.original_signal,
            ad.investment_score,
            ad.technical_score,
            ad.quality_score,
            ad.growth_score,
            ad.confidence_score,
            ad.evidence_score
        FROM audit_decisions ad
        INNER JOIN audit_runs ar
            ON ar.id = ad.audit_run_id
        WHERE ar.status = 'COMPLETED'
          AND UPPER(TRIM(ad.final_action)) = 'HOLD'
          AND UPPER(TRIM(ad.asset_type)) = 'STOCK'
        ORDER BY ar.run_date, ad.id
        """,
        conn,
    )

    recommendations = pd.read_sql_query(
        """
        SELECT
            id AS recommendation_id,
            date AS recommendation_date,
            ticker,
            signal
        FROM recommendations
        WHERE ticker IS NOT NULL
        """,
        conn,
    )

    evidence = pd.read_sql_query(
        """
        SELECT
            recommendation_id,
            capture_date,
            ticker,
            signal,
            investment_score,
            technical_score,
            quality_score,
            growth_score,
            entry_price,
            rsi,
            sma50,
            sma200,
            return_3m,
            trend,
            trend_score,
            momentum_score,
            volume_score,
            risk_score,
            revenue_growth,
            profit_margin,
            return_on_equity,
            debt_to_equity
        FROM recommendation_evidence
        """,
        conn,
    )

    evaluations = pd.read_sql_query(
        """
        SELECT
            recommendation_id,
            days_after,
            evaluation_date,
            return_percent,
            outcome
        FROM recommendation_evaluations
        WHERE days_after = 5
        """,
        conn,
    )

    conn.close()

    return audit, recommendations, evidence, evaluations


def prepare(audit, recommendations, evidence, evaluations):
    audit["audit_date"] = pd.to_datetime(
        audit["audit_date"],
        errors="coerce",
        format="ISO8601",
    ).dt.tz_localize(None)

    recommendations["recommendation_date"] = pd.to_datetime(
        recommendations["recommendation_date"],
        errors="coerce",
        format="ISO8601",
    ).dt.tz_localize(None)

    evidence["capture_date"] = pd.to_datetime(
        evidence["capture_date"],
        errors="coerce",
        format="ISO8601",
    ).dt.tz_localize(None)

    evaluations["evaluation_date"] = pd.to_datetime(
        evaluations["evaluation_date"],
        errors="coerce",
        format="ISO8601",
    ).dt.tz_localize(None)

    # Persisted recommendation_id is authoritative.
    audit = audit[
        audit["recommendation_id"].notna()
    ].copy()

    audit["recommendation_id"] = pd.to_numeric(
        audit["recommendation_id"],
        errors="coerce",
    )

    recommendations["recommendation_id"] = pd.to_numeric(
        recommendations["recommendation_id"],
        errors="coerce",
    )

    evidence["recommendation_id"] = pd.to_numeric(
        evidence["recommendation_id"],
        errors="coerce",
    )

    evaluations["recommendation_id"] = pd.to_numeric(
        evaluations["recommendation_id"],
        errors="coerce",
    )

    # Keep the recommendation record attached to the audited decision.
    working = audit.merge(
        recommendations,
        how="left",
        on="recommendation_id",
        suffixes=("", "_recommendation"),
    )

    # Point-in-time evidence.
    working = working.merge(
        evidence,
        how="left",
        on="recommendation_id",
        suffixes=("", "_evidence"),
    )

    # Realised 5D outcome.
    evaluations = (
        evaluations
        .sort_values(
            [
                "recommendation_id",
                "evaluation_date",
            ]
        )
        .drop_duplicates(
            subset=["recommendation_id"],
            keep="last",
        )
    )

    working = working.merge(
        evaluations[
            [
                "recommendation_id",
                "return_percent",
                "outcome",
            ]
        ],
        how="left",
        on="recommendation_id",
    )

    # Prefer immutable point-in-time evidence for the analysis fields.
    for field in [
        "investment_score",
        "technical_score",
        "quality_score",
        "growth_score",
    ]:
        evidence_field = f"{field}_evidence"

        if evidence_field in working.columns:
            working[field] = pd.to_numeric(
                working[evidence_field],
                errors="coerce",
            ).combine_first(
                pd.to_numeric(
                    working[field],
                    errors="coerce",
                )
            )

    working["rsi"] = pd.to_numeric(
        working["rsi"],
        errors="coerce",
    )
    working["sma50"] = pd.to_numeric(
        working["sma50"],
        errors="coerce",
    )
    working["sma200"] = pd.to_numeric(
        working["sma200"],
        errors="coerce",
    )
    working["entry_price"] = pd.to_numeric(
        working["entry_price"],
        errors="coerce",
    )
    working["return_3m"] = pd.to_numeric(
        working["return_3m"],
        errors="coerce",
    )
    working["return_percent"] = pd.to_numeric(
        working["return_percent"],
        errors="coerce",
    )

    # Only matured 5D observations are performance evidence.
    working["matured_5d"] = working["return_percent"].notna()

    return working


def add_score_band(series):
    return pd.cut(
        pd.to_numeric(series, errors="coerce"),
        bins=[
            -np.inf,
            49.999,
            59.999,
            69.999,
            74.999,
            79.999,
            89.999,
            np.inf,
        ],
        labels=[
            "<50",
            "50-59",
            "60-69",
            "70-74",
            "75-79",
            "80-89",
            "90+",
        ],
        right=True,
    )


def summarise(df, group_column, order=None):
    matured = df[
        df["return_percent"].notna()
    ].copy()

    grouping_columns = (
        group_column
        if isinstance(group_column, list)
        else [group_column]
    )

    grouped = matured.groupby(
        grouping_columns,
        observed=False,
        dropna=False,
    )

    rows = []

    for key, group in grouped:
        returns = group["return_percent"]

        if not isinstance(key, tuple):
            key = (key,)

        row = {
            column: value
            for column, value in zip(
                grouping_columns,
                key,
            )
        }

        # Count the full decision population for
        # this exact bucket, not just matured outcomes.
        population_grouped = df.groupby(
            grouping_columns,
            observed=False,
            dropna=False,
        )

        try:
            population = population_grouped.get_group(
                key
            )
            decisions = len(population)
        except KeyError:
            decisions = 0

        row.update(
            {
                "Decisions": decisions,
                "5D Outcomes": len(group),
                "5D Coverage %": round(
                    len(group)
                    / decisions
                    * 100,
                    2,
                )
                if decisions
                else None,
                "Average 5D Return %": round(
                    returns.mean(),
                    3,
                ),
                "Median 5D Return %": round(
                    returns.median(),
                    3,
                ),
                "Positive 5D %": round(
                    returns.gt(0).mean() * 100,
                    2,
                ),
                "Negative 5D %": round(
                    returns.lt(0).mean() * 100,
                    2,
                ),
            }
        )

        rows.append(row)

    result = pd.DataFrame(rows)

    if (
        order is not None
        and not result.empty
        and len(grouping_columns) == 1
    ):
        column = grouping_columns[0]

        result[column] = pd.Categorical(
            result[column],
            categories=order,
            ordered=True,
        )

        result = result.sort_values(
            column
        )

    return result.reset_index(drop=True)

def build_score_analysis(df):
    working = df.copy()
    working["Score Band"] = add_score_band(
        working["investment_score"]
    )

    order = [
        "<50",
        "50-59",
        "60-69",
        "70-74",
        "75-79",
        "80-89",
        "90+",
    ]

    return summarise(
        working,
        "Score Band",
        order,
    )


def build_technical_analysis(df):
    working = df.copy()

    technical = pd.to_numeric(
        working["technical_score"],
        errors="coerce",
    )

    working["Technical Band"] = pd.cut(
        technical,
        bins=[
            -np.inf,
            24.999,
            49.999,
            74.999,
            np.inf,
        ],
        labels=[
            "<25",
            "25-49",
            "50-74",
            "75+",
        ],
    )

    return summarise(
        working,
        "Technical Band",
        [
            "<25",
            "25-49",
            "50-74",
            "75+",
        ],
    )


def build_signal_analysis(df):
    working = df.copy()

    signal = (
        working["signal"]
        .fillna(
            working["original_signal"]
        )
        .astype(str)
        .str.upper()
        .str.strip()
    )

    working["Signal"] = signal.replace(
        {
            "": "UNKNOWN",
            "NAN": "UNKNOWN",
            "NONE": "UNKNOWN",
        }
    )

    return summarise(
        working,
        "Signal",
    )


def build_technical_state_analysis(df):
    working = df.copy()

    working["Above MA50"] = (
        working["entry_price"]
        > working["sma50"]
    )

    working["Above MA200"] = (
        working["entry_price"]
        > working["sma200"]
    )

    working["Technical State"] = np.select(
        [
            working["Above MA50"]
            & working["Above MA200"],

            (~working["Above MA50"])
            & working["Above MA200"],

            working["Above MA50"]
            & (~working["Above MA200"]),

            (~working["Above MA50"])
            & (~working["Above MA200"]),
        ],
        [
            "Above MA50 + MA200",
            "Below MA50 / Above MA200",
            "Above MA50 / Below MA200",
            "Below MA50 + MA200",
        ],
        default="Unknown",
    )

    return summarise(
        working,
        "Technical State",
        [
            "Above MA50 + MA200",
            "Below MA50 / Above MA200",
            "Above MA50 / Below MA200",
            "Below MA50 + MA200",
            "Unknown",
        ],
    )

def filter_score_70_74(df):
    """
    Restrict analysis to FINAL HOLD decisions with
    Investment Score 70-74.

    This is a read-only diagnostic population.
    """

    score = pd.to_numeric(
        df["investment_score"],
        errors="coerce",
    )

    return df[
        (score >= 70)
        & (score < 75)
    ].copy()


def add_quality_band(series):
    return pd.cut(
        pd.to_numeric(series, errors="coerce"),
        bins=[
            -np.inf,
            24.999,
            49.999,
            74.999,
            np.inf,
        ],
        labels=[
            "<25",
            "25-49",
            "50-74",
            "75+",
        ],
    )


def add_growth_band(series):
    return pd.cut(
        pd.to_numeric(series, errors="coerce"),
        bins=[
            -np.inf,
            24.999,
            49.999,
            74.999,
            np.inf,
        ],
        labels=[
            "<25",
            "25-49",
            "50-74",
            "75+",
        ],
    )


def build_70_74_signal_analysis(df):
    working = filter_score_70_74(df)

    signal = (
        working["signal"]
        .fillna(
            working["original_signal"]
        )
        .astype(str)
        .str.upper()
        .str.strip()
    )

    working["Signal"] = signal.replace(
        {
            "": "UNKNOWN",
            "NAN": "UNKNOWN",
            "NONE": "UNKNOWN",
        }
    )

    return summarise(
        working,
        "Signal",
    )


def build_70_74_technical_state_analysis(df):
    working = filter_score_70_74(df)

    working["Above MA50"] = (
        working["entry_price"]
        > working["sma50"]
    )

    working["Above MA200"] = (
        working["entry_price"]
        > working["sma200"]
    )

    working["Technical State"] = np.select(
        [
            working["Above MA50"]
            & working["Above MA200"],

            (~working["Above MA50"])
            & working["Above MA200"],

            working["Above MA50"]
            & (~working["Above MA200"]),

            (~working["Above MA50"])
            & (~working["Above MA200"]),
        ],
        [
            "Above MA50 + MA200",
            "Below MA50 / Above MA200",
            "Above MA50 / Below MA200",
            "Below MA50 + MA200",
        ],
        default="Unknown",
    )

    return summarise(
        working,
        "Technical State",
        [
            "Above MA50 + MA200",
            "Below MA50 / Above MA200",
            "Above MA50 / Below MA200",
            "Below MA50 + MA200",
            "Unknown",
        ],
    )


def build_70_74_quality_analysis(df):
    working = filter_score_70_74(df)

    working["Quality Band"] = add_quality_band(
        working["quality_score"]
    )

    return summarise(
        working,
        "Quality Band",
        [
            "<25",
            "25-49",
            "50-74",
            "75+",
        ],
    )


def build_70_74_growth_analysis(df):
    working = filter_score_70_74(df)

    working["Growth Band"] = add_growth_band(
        working["growth_score"]
    )

    return summarise(
        working,
        "Growth Band",
        [
            "<25",
            "25-49",
            "50-74",
            "75+",
        ],
    )


def build_70_74_signal_quality_analysis(df):
    working = filter_score_70_74(df)

    signal = (
        working["signal"]
        .fillna(
            working["original_signal"]
        )
        .astype(str)
        .str.upper()
        .str.strip()
    )

    working["Signal"] = signal.replace(
        {
            "": "UNKNOWN",
            "NAN": "UNKNOWN",
            "NONE": "UNKNOWN",
        }
    )

    working["Quality Band"] = add_quality_band(
        working["quality_score"]
    )

    return summarise(
        working,
        ["Signal", "Quality Band"],
    )


def build_70_74_signal_growth_analysis(df):
    working = filter_score_70_74(df)

    signal = (
        working["signal"]
        .fillna(
            working["original_signal"]
        )
        .astype(str)
        .str.upper()
        .str.strip()
    )

    working["Signal"] = signal.replace(
        {
            "": "UNKNOWN",
            "NAN": "UNKNOWN",
            "NONE": "UNKNOWN",
        }
    )

    working["Growth Band"] = add_growth_band(
        working["growth_score"]
    )

    return summarise(
        working,
        ["Signal", "Growth Band"],
    )


def build_good_bad_outcomes(df):
    matured = df[
        df["return_percent"].notna()
    ].copy()

    columns = [
        "recommendation_id",
        "ticker",
        "audit_date",
        "recommendation_date",
        "signal",
        "investment_score",
        "technical_score",
        "quality_score",
        "growth_score",
        "rsi",
        "entry_price",
        "sma50",
        "sma200",
        "return_3m",
        "return_percent",
        "outcome",
    ]

    available = [
        c for c in columns
        if c in matured.columns
    ]

    result = matured[available].copy()

    result["Outcome Group"] = np.select(
        [
            result["return_percent"] >= 5,
            result["return_percent"] <= -5,
        ],
        [
            "Strongly Positive (>= +5%)",
            "Strongly Negative (<= -5%)",
        ],
        default="Intermediate",
    )

    return result.sort_values(
        "return_percent",
        ascending=True,
    ).reset_index(drop=True)

def build_70_74_low_quality_cohort(df):
    """
    Extract the matured HOLD cohort with:
        - Investment Score 70-74
        - Quality Score 25-49

    This is diagnostic only. It does not modify
    production decision logic.
    """

    cohort = df[
        (df["return_percent"].notna())
        & (
            pd.to_numeric(
                df["investment_score"],
                errors="coerce",
            ).between(70, 74)
        )
        & (
            pd.to_numeric(
                df["quality_score"],
                errors="coerce",
            ).between(25, 49)
        )
    ].copy()

    # One observation per recommendation.
    cohort = (
        cohort
        .sort_values(
            [
                "recommendation_id",
                "audit_date",
            ]
        )
        .drop_duplicates(
            subset=["recommendation_id"],
            keep="last",
        )
    )

    columns = [
        "recommendation_id",
        "ticker",
        "audit_date",
        "recommendation_date",
        "signal",
        "investment_score",
        "technical_score",
        "quality_score",
        "growth_score",
        "rsi",
        "entry_price",
        "sma50",
        "sma200",
        "return_3m",
        "return_percent",
        "outcome",
    ]

    available = [
        column
        for column in columns
        if column in cohort.columns
    ]

    return (
        cohort[available]
        .sort_values(
            "return_percent",
            ascending=True,
        )
        .reset_index(drop=True)
    )


def build_boundary_summary(df):
    matured = df[
        df["return_percent"].notna()
    ].copy()

    # This is descriptive only. It identifies where HOLD decisions
    # sit relative to the eventual negative/positive outcome.
    score = pd.to_numeric(
        matured["investment_score"],
        errors="coerce",
    )
    technical = pd.to_numeric(
        matured["technical_score"],
        errors="coerce",
    )

    cases = pd.DataFrame(
        {
            "Population": [
                "All matured HOLD",
                "HOLD <= -5%",
                "HOLD <= -10%",
                "HOLD >= +5%",
                "HOLD >= +10%",
                "HOLD < 60",
                "HOLD 60-74",
                "HOLD >= 75",
                "HOLD Technical < 50",
                "HOLD Technical >= 50",
            ],
            "Observations": [
                len(matured),
                int((matured["return_percent"] <= -5).sum()),
                int((matured["return_percent"] <= -10).sum()),
                int((matured["return_percent"] >= 5).sum()),
                int((matured["return_percent"] >= 10).sum()),
                int((score < 60).sum()),
                int(((score >= 60) & (score < 75)).sum()),
                int((score >= 75).sum()),
                int((technical < 50).sum()),
                int((technical >= 50).sum()),
            ],
        }
    )

    return cases


def main():
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    audit, recommendations, evidence, evaluations = (
        load_data()
    )

    df = prepare(
        audit,
        recommendations,
        evidence,
        evaluations,
    )

    matured = df[
        df["return_percent"].notna()
    ].copy()

    print()
    print("=" * 78)
    print("A6 — HOLD PERFORMANCE INVESTIGATION")
    print("=" * 78)
    print(
        f"Final HOLD decisions loaded: {len(df)}"
    )
    print(
        f"Matured 5D HOLD outcomes: {len(matured)}"
    )
    print(
        f"5D coverage: "
        f"{len(matured) / len(df) * 100:.2f}%"
        if len(df)
        else "5D coverage: 0.00%"
    )

    if matured.empty:
        print(
            "No matured 5D HOLD outcomes available."
        )
        return

    score_analysis = build_score_analysis(df)
    technical_analysis = build_technical_analysis(df)
    signal_analysis = build_signal_analysis(df)
    technical_state_analysis = (
        build_technical_state_analysis(df)
    )

    # --------------------------------------------------------
    # 70-74 HOLD COHORT DECOMPOSITION
    # --------------------------------------------------------

    hold_70_74_signal = (
        build_70_74_signal_analysis(df)
    )

    hold_70_74_technical_state = (
        build_70_74_technical_state_analysis(df)
    )

    hold_70_74_quality = (
        build_70_74_quality_analysis(df)
    )

    hold_70_74_growth = (
        build_70_74_growth_analysis(df)
    )

    hold_70_74_signal_quality = (
        build_70_74_signal_quality_analysis(df)
    )

    hold_70_74_signal_growth = (
        build_70_74_signal_growth_analysis(df)
    )

    good_bad = build_good_bad_outcomes(df)

    low_quality_cohort = (
    build_70_74_low_quality_cohort(df)
    )

    low_quality_cohort.to_csv(
        OUTPUT_DIR
        / "hold_70_74_quality_25_49.csv",
        index=False,
    )

    print(
        "\n70-74 HOLD / QUALITY 25-49 COHORT"
    )

    print(
        f"Unique matured recommendations: "
        f"{len(low_quality_cohort)}"
    )

    if not low_quality_cohort.empty:
        returns = low_quality_cohort[
            "return_percent"
        ]

        print(
            f"Average 5D return: "
            f"{returns.mean():.3f}%"
        )

        print(
            f"Median 5D return: "
            f"{returns.median():.3f}%"
        )

        print(
            f"Positive 5D: "
            f"{returns.gt(0).mean() * 100:.2f}%"
        )

        print(
            f"Negative 5D: "
            f"{returns.lt(0).mean() * 100:.2f}%"
        )

        print(
            f"<= -5%: "
            f"{returns.le(-5).sum()}"
        )

        print(
            f">= +5%: "
            f"{returns.ge(5).sum()}"
        )

        print(
            "\nUnique tickers:"
        )

        print(
            low_quality_cohort[
                "ticker"
            ].value_counts()
        )

        boundary = build_boundary_summary(df)

        outputs = {
            "hold_score_bands.csv": score_analysis,
            "hold_technical_bands.csv": technical_analysis,
            "hold_signal_bands.csv": signal_analysis,
            "hold_technical_states.csv": technical_state_analysis,

            "hold_70_74_signal.csv":
                hold_70_74_signal,

            "hold_70_74_technical_state.csv":
                hold_70_74_technical_state,

            "hold_70_74_quality.csv":
                hold_70_74_quality,

            "hold_70_74_growth.csv":
                hold_70_74_growth,

            "hold_70_74_signal_quality.csv":
                hold_70_74_signal_quality,

            "hold_70_74_signal_growth.csv":
                hold_70_74_signal_growth,

            "hold_good_bad_outcomes.csv": good_bad,
            "hold_boundary_summary.csv": boundary,
        }

        for filename, table in outputs.items():
            path = OUTPUT_DIR / filename
            table.to_csv(
                path,
                index=False,
            )
            print(
                f"Written: {path}"
            )

        print()
        print("HOLD BY INVESTMENT SCORE")
        print(score_analysis.to_string(index=False))

        print()
        print("HOLD BY TECHNICAL SCORE")
        print(technical_analysis.to_string(index=False))

        print()
        print("HOLD BY SIGNAL")
        print(signal_analysis.to_string(index=False))

        print()
        print("HOLD BY TECHNICAL STATE")
        print(
            technical_state_analysis.to_string(
                index=False
            )
        )

        print()
        print("HOLD BOUNDARY SUMMARY")
        print(boundary.to_string(index=False))

        print()
        print("=" * 78)
        print("70-74 HOLD COHORT DECOMPOSITION")
        print("=" * 78)

        cohort = filter_score_70_74(df)

        cohort_matured = cohort[
            cohort["return_percent"].notna()
        ]

        print(
            f"70-74 HOLD decisions: {len(cohort)}"
        )

        print(
            f"70-74 matured 5D outcomes: "
            f"{len(cohort_matured)}"
        )

        print()
        print("70-74 HOLD BY SIGNAL")
        print(
            hold_70_74_signal.to_string(
                index=False
            )
        )

        print()
        print("70-74 HOLD BY TECHNICAL STATE")
        print(
            hold_70_74_technical_state.to_string(
                index=False
            )
        )

        print()
        print("70-74 HOLD BY QUALITY")
        print(
            hold_70_74_quality.to_string(
                index=False
            )
        )

        print()
        print("70-74 HOLD BY GROWTH")
        print(
            hold_70_74_growth.to_string(
                index=False
            )
        )

        print()
        print("70-74 HOLD — SIGNAL × QUALITY")
        print(
            hold_70_74_signal_quality.to_string(
                index=False
            )
        )

        print()
        print("70-74 HOLD — SIGNAL × GROWTH")
        print(
            hold_70_74_signal_growth.to_string(
                index=False
            )
        )

        print()
        print(
            "READ-ONLY investigation complete."
        )
        print(
            "No production files or database records were changed."
        )


if __name__ == "__main__":
    main()

