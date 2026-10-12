from pathlib import Path
import sqlite3
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "portfolio_manager.db"
OUTPUT_DIR = PROJECT_ROOT / "calibration" / "output"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_data():
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database not found: {DB_PATH}"
        )

    conn = sqlite3.connect(DB_PATH)

    # =========================================================
    # AUDIT DECISIONS
    # =========================================================
    #
    # audit_date comes from audit_runs.run_date.
    # recommendation_id is audit_decisions.recommendation_id.
    # =========================================================

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
            ad.growth_score
        FROM audit_decisions ad
        INNER JOIN audit_runs ar
            ON ar.id = ad.audit_run_id
        WHERE ar.status = 'COMPLETED'
          AND UPPER(TRIM(ad.final_action)) = 'HOLD'
          AND UPPER(TRIM(ad.asset_type)) = 'STOCK'
          AND ad.recommendation_id IS NOT NULL
        ORDER BY
            ar.run_date,
            ad.id
        """,
        conn,
    )

    # =========================================================
    # RECOMMENDATIONS
    # =========================================================
    #
    # Actual schema:
    #   id
    #   date
    #   ticker
    #   signal
    # =========================================================

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

    # =========================================================
    # POINT-IN-TIME RECOMMENDATION EVIDENCE
    # =========================================================

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

    # =========================================================
    # 5D REALISED OUTCOMES
    # =========================================================

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

    return (
        audit,
        recommendations,
        evidence,
        evaluations,
    )

def build_population(
    audit,
    recommendations,
    evidence,
    evaluations,
):
    # ---------------------------------------------------------
    # One audit record per recommendation.
    # Prefer the latest audit snapshot.
    # ---------------------------------------------------------

    audit["audit_date"] = pd.to_datetime(
        audit["audit_date"],
        errors="coerce",
    )

    audit = (
        audit
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

    # ---------------------------------------------------------
    # Join recommendation metadata.
    # ---------------------------------------------------------

    df = audit.merge(
        recommendations[
            [
                "recommendation_id",
                "recommendation_date",
                "signal",
            ]
        ],
        on="recommendation_id",
        how="left",
        suffixes=("", "_recommendation"),
    )

    # ---------------------------------------------------------
    # Join point-in-time evidence.
    #
    # Evidence is preferable to current market data because
    # this investigation must remain point-in-time.
    # ---------------------------------------------------------

    evidence["capture_date"] = pd.to_datetime(
        evidence["capture_date"],
        errors="coerce",
    )

    evidence = (
        evidence
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
    )

    evidence_columns = [
        "recommendation_id",
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
    ]

    evidence_columns = [
        column
        for column in evidence_columns
        if column in evidence.columns
    ]

    evidence_subset = evidence[
        evidence_columns
    ].copy()

    evidence_subset = evidence_subset.rename(
        columns={
            "signal": "evidence_signal",
            "investment_score": "evidence_investment_score",
            "technical_score": "evidence_technical_score",
            "quality_score": "evidence_quality_score",
            "growth_score": "evidence_growth_score",
        }
    )

    df = df.merge(
        evidence_subset,
        on="recommendation_id",
        how="left",
    )

    # ---------------------------------------------------------
    # Join 5D outcome.
    # ---------------------------------------------------------

    evaluations = (
        evaluations
        .sort_values(
            "recommendation_id"
        )
        .drop_duplicates(
            subset=["recommendation_id"],
            keep="last",
        )
    )

    df = df.merge(
        evaluations[
            [
                "recommendation_id",
                "return_percent",
            ]
        ],
        on="recommendation_id",
        how="left",
    )

    # ---------------------------------------------------------
    # Use persisted audit scores as the action-layer values.
    # ---------------------------------------------------------

    for column in [
        "investment_score",
        "technical_score",
        "quality_score",
        "growth_score",
        "return_percent",
    ]:
        if column in df.columns:
            df[column] = pd.to_numeric(
                df[column],
                errors="coerce",
            )

    # ---------------------------------------------------------
    # Target population:
    #
    # Investment Score 70-74
    # Quality Score 25-49
    # ---------------------------------------------------------

    population = df[
        df["investment_score"].between(70, 74)
        & df["quality_score"].between(25, 49)
    ].copy()

    return population


def classify_candidate_action(row):
    """
    Diagnostic only.

    This does NOT reproduce or modify production logic.

    It applies the candidate safeguard:
        Investment Score 70-74
        AND Quality 25-49
        -> REDUCE 25%

    Everything else is left as HOLD.
    """

    if (
        70 <= row["investment_score"] <= 74
        and
        25 <= row["quality_score"] <= 49
    ):
        return "CANDIDATE REDUCE 25%"

    return "HOLD"


def main():
    print("=" * 78)
    print("QUALITY SAFEGUARD INVESTIGATION")
    print("=" * 78)
    print()
    print("READ-ONLY")
    print("No production files or database records will be changed.")
    print()

    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database not found: {DB_PATH}"
        )

    (
        audit,
        recommendations,
        evidence,
        evaluations,
    ) = load_data()

    population = build_population(
        audit,
        recommendations,
        evidence,
        evaluations,
    )

    if population.empty:
        print(
            "No matching 70-74 / Quality 25-49 "
            "HOLD decisions were found."
        )
        return

    # ---------------------------------------------------------
    # Candidate action
    # ---------------------------------------------------------

    population["candidate_action"] = population.apply(
        classify_candidate_action,
        axis=1,
    )

    # ---------------------------------------------------------
    # Outcome statistics
    # ---------------------------------------------------------

    matured = population[
        population["return_percent"].notna()
    ].copy()

    print(
        f"Target HOLD decisions: "
        f"{len(population)}"
    )

    print(
        f"Matured 5D outcomes: "
        f"{len(matured)}"
    )

    if not matured.empty:
        returns = matured["return_percent"]

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

    # ---------------------------------------------------------
    # Score distributions
    # ---------------------------------------------------------

    print()
    print("=" * 78)
    print("SCORE DISTRIBUTION")
    print("=" * 78)

    for column in [
        "investment_score",
        "technical_score",
        "quality_score",
        "growth_score",
    ]:
        if column not in population.columns:
            continue

        series = population[column].dropna()

        if series.empty:
            continue

        print()
        print(column)

        print(
            f"  Min:    {series.min():.1f}"
        )
        print(
            f"  Median: {series.median():.1f}"
        )
        print(
            f"  Mean:   {series.mean():.1f}"
        )
        print(
            f"  Max:    {series.max():.1f}"
        )

    # ---------------------------------------------------------
    # Signal distribution
    # ---------------------------------------------------------

    print()
    print("=" * 78)
    print("SIGNAL DISTRIBUTION")
    print("=" * 78)

    signal_column = "signal"

    if signal_column in population.columns:
        print(
            population[
                signal_column
            ].value_counts(
                dropna=False
            ).to_string()
        )

    # ---------------------------------------------------------
    # Candidate action
    # ---------------------------------------------------------

    print()
    print("=" * 78)
    print("CANDIDATE ACTION")
    print("=" * 78)

    print(
        population[
            "candidate_action"
        ].value_counts(
            dropna=False
        ).to_string()
    )

    # ---------------------------------------------------------
    # Outcome by candidate action
    # ---------------------------------------------------------

    if not matured.empty:
        print()
        print("=" * 78)
        print("OUTCOME BY CANDIDATE ACTION")
        print("=" * 78)

        summary = (
            matured
            .groupby(
                "candidate_action",
                observed=False,
            )["return_percent"]
            .agg(
                Decisions="count",
                Average_5D_Return="mean",
                Median_5D_Return="median",
                Positive_5D=lambda x: (
                    x.gt(0).mean() * 100
                ),
                Negative_5D=lambda x: (
                    x.lt(0).mean() * 100
                ),
            )
            .reset_index()
        )

        summary["Average_5D_Return"] = (
            summary["Average_5D_Return"]
            .round(3)
        )

        summary["Median_5D_Return"] = (
            summary["Median_5D_Return"]
            .round(3)
        )

        summary["Positive_5D"] = (
            summary["Positive_5D"]
            .round(2)
        )

        summary["Negative_5D"] = (
            summary["Negative_5D"]
            .round(2)
        )

        print(
            summary.to_string(
                index=False
            )
        )

    # ---------------------------------------------------------
    # Detailed historical population
    # ---------------------------------------------------------

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
        "final_action",
        "candidate_action",
    ]

    available = [
        column
        for column in columns
        if column in population.columns
    ]

    detail = (
        population[
            available
        ]
        .sort_values(
            "return_percent",
            ascending=True,
            na_position="last",
        )
        .reset_index(drop=True)
    )

    output_file = (
        OUTPUT_DIR
        / "quality_safeguard_70_74_25_49.csv"
    )

    detail.to_csv(
        output_file,
        index=False,
    )

    print()
    print("=" * 78)
    print("HISTORICAL CASES")
    print("=" * 78)

    print(
        detail.to_string(
            index=False
        )
    )

    print()
    print("=" * 78)
    print("OUTPUT")
    print("=" * 78)

    print(output_file)

    print()
    print(
        "Investigation complete."
    )
    print(
        "No production files or database records were changed."
    )


if __name__ == "__main__":
    main()
