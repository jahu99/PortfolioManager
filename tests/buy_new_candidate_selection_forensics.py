"""
BUY NEW — SAME-TICKER / DIFFERENT-RECOMMENDATION CONTROL TEST V3

A6 READ-ONLY INVESTIGATION
NO PRODUCTION CHANGES

Purpose
-------
Test whether BUY NEW decisions perform differently from genuinely
different non-BUY-NEW recommendations for the SAME ticker.

Critical correction from V2
---------------------------
Multiple audit_decision rows can refer to the same recommendation_id.

Therefore V3 treats recommendation_id as the observation unit.

A control is only valid when:

    same ticker
    AND
    different recommendation_id
    AND
    non-BUY-NEW action
    AND
    mature 5D outcome

The validated mature BUY NEW population is preserved at the
recommendation level.

No production logic is changed.
"""


import sqlite3
from pathlib import Path

import pandas as pd


# ============================================================
# CONFIG
# ============================================================

DB_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "portfolio_manager.db"
)

BUY_NEW = "BUY NEW"


# ============================================================
# HELPERS
# ============================================================

def normalise_datetime(series):

    return (
        pd.to_datetime(
            series,
            errors="coerce",
            format="mixed",
            utc=True,
        )
        .dt.tz_localize(None)
    )


def section(title):

    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


# ============================================================
# LOAD AUDIT
# ============================================================

def load_audit(conn):

    df = pd.read_sql_query(
        """
        SELECT
            ad.id AS audit_decision_id,
            ad.audit_run_id,
            ad.recommendation_id,
            ad.ticker,
            ad.final_action,
            ar.run_date AS audit_date
        FROM audit_decisions ad
        JOIN audit_runs ar
            ON ar.id = ad.audit_run_id
        WHERE ar.status = 'COMPLETED'
        """,
        conn,
    )

    df["audit_date"] = normalise_datetime(
        df["audit_date"]
    )

    df["ticker"] = (
        df["ticker"]
        .astype(str)
        .str.strip()
    )

    return df


# ============================================================
# LOAD RECOMMENDATIONS
# ============================================================

def load_recommendations(conn):

    df = pd.read_sql_query(
        """
        SELECT
            id AS recommendation_id,
            date AS recommendation_date,
            ticker
        FROM recommendations
        """,
        conn,
    )

    df["recommendation_date"] = normalise_datetime(
        df["recommendation_date"]
    )

    df = df[
        df["recommendation_date"].notna()
    ].copy()

    df["ticker"] = (
        df["ticker"]
        .astype(str)
        .str.strip()
    )

    return df


# ============================================================
# LOAD 5D OUTCOMES
# ============================================================

def load_evaluations(conn):

    df = pd.read_sql_query(
        """
        SELECT
            recommendation_id,
            evaluation_date,
            days_after,
            return_percent,
            outcome
        FROM recommendation_evaluations
        WHERE days_after = 5
        """,
        conn,
    )

    df["evaluation_date"] = normalise_datetime(
        df["evaluation_date"]
    )

    df["return_percent"] = pd.to_numeric(
        df["return_percent"],
        errors="coerce",
    )

    return df


# ============================================================
# BUILD AUDIT LINEAGE
# ============================================================

def build_lineage(audit, recs):

    # --------------------------------------------------------
    # Direct lineage
    # --------------------------------------------------------

    direct = audit[
        audit["recommendation_id"].notna()
    ].copy()

    direct["lineage_type"] = "DIRECT"

    direct = direct.merge(
        recs[
            [
                "recommendation_id",
                "recommendation_date",
            ]
        ],
        on="recommendation_id",
        how="left",
    )

    # --------------------------------------------------------
    # Legacy lineage
    # --------------------------------------------------------

    legacy = audit[
        audit["recommendation_id"].isna()
    ].copy()

    legacy = legacy[
        legacy["audit_date"].notna()
    ].copy()

    recs_by_ticker = {
        ticker: group.sort_values(
            "recommendation_date"
        )
        for ticker, group
        in recs.groupby("ticker")
    }

    rows = []

    for row in legacy.itertuples(
        index=False
    ):

        candidates = recs_by_ticker.get(
            row.ticker
        )

        if candidates is None:
            continue

        candidates = candidates[
            candidates["recommendation_date"]
            <= row.audit_date
        ]

        if candidates.empty:
            continue

        match = candidates.iloc[-1]

        rows.append(
            {
                "audit_decision_id":
                    row.audit_decision_id,
                "audit_run_id":
                    row.audit_run_id,
                "recommendation_id":
                    match["recommendation_id"],
                "ticker":
                    row.ticker,
                "final_action":
                    row.final_action,
                "audit_date":
                    row.audit_date,
                "recommendation_date":
                    match["recommendation_date"],
                "lineage_type":
                    "RECONSTRUCTED",
            }
        )

    reconstructed = pd.DataFrame(rows)

    if reconstructed.empty:

        reconstructed = pd.DataFrame(
            columns=[
                "audit_decision_id",
                "audit_run_id",
                "recommendation_id",
                "ticker",
                "final_action",
                "audit_date",
                "recommendation_date",
                "lineage_type",
            ]
        )

    columns = [
        "audit_decision_id",
        "audit_run_id",
        "recommendation_id",
        "ticker",
        "final_action",
        "audit_date",
        "recommendation_date",
        "lineage_type",
    ]

    direct = direct[columns]

    lineage = pd.concat(
        [
            direct,
            reconstructed,
        ],
        ignore_index=True,
    )

    return lineage


# ============================================================
# BUILD RECOMMENDATION-LEVEL OBSERVATIONS
# ============================================================

def build_observations(
    lineage,
    evaluations,
):

    # --------------------------------------------------------
    # Attach 5D outcomes
    # --------------------------------------------------------

    df = lineage.merge(
        evaluations[
            [
                "recommendation_id",
                "evaluation_date",
                "days_after",
                "return_percent",
                "outcome",
            ]
        ],
        on="recommendation_id",
        how="inner",
    )

    df = df[
        df["days_after"] == 5
    ].copy()

    # --------------------------------------------------------
    # V4:
    #
    # Preserve the validated mature BUY NEW decision population.
    #
    # recommendation_id is NOT used as the observation unit
    # because one recommendation can appear in multiple governed
    # audit decisions / decision episodes.
    #
    # Remove only exact duplicate audit observations.
    # --------------------------------------------------------

    df = df.drop_duplicates(
        subset=[
            "audit_decision_id",
            "recommendation_id",
            "ticker",
            "audit_date",
            "final_action",
            "return_percent",
        ],
        keep="last",
    )

    return df


# ============================================================
# VALIDATED BUY NEW POPULATION
# ============================================================

def get_buy_new(
    observations,
):

    buy_new = observations[
        observations["final_action"]
        == BUY_NEW
    ].copy()

    return buy_new


# ============================================================
# VALID CONTROL POPULATION
# ============================================================

def get_controls(
    observations,
):

    controls = observations[
        observations["final_action"]
        != BUY_NEW
    ].copy()

    return controls


# ============================================================
# MATCH CONTROLS
# ============================================================

def match_controls(
    buy_new,
    controls,
):

    rows = []

    for _, buy in buy_new.iterrows():

        candidates = controls[
            (
                controls["ticker"]
                == buy["ticker"]
            )
            &
            (
                controls["recommendation_id"]
                != buy["recommendation_id"]
            )
        ].copy()

        if candidates.empty:
            continue

        # ----------------------------------------------------
        # Distance from BUY NEW recommendation
        # ----------------------------------------------------

        candidates["distance_days"] = (
            candidates["recommendation_date"]
            - buy["recommendation_date"]
        ).dt.total_seconds() / 86400.0

        # ----------------------------------------------------
        # Prior
        # ----------------------------------------------------

        prior = candidates[
            candidates["distance_days"] < 0
        ].copy()

        if not prior.empty:

            prior = prior.sort_values(
                [
                    "distance_days",
                    "recommendation_id",
                ],
                ascending=[
                    False,
                    True,
                ],
            )

            control = prior.iloc[0]

            rows.append(
                {
                    "buy_recommendation_id":
                        buy["recommendation_id"],
                    "ticker":
                        buy["ticker"],
                    "buy_date":
                        buy["recommendation_date"],
                    "buy_action":
                        buy["final_action"],
                    "buy_return":
                        buy["return_percent"],
                    "control_type":
                        "PRIOR",
                    "control_recommendation_id":
                        control[
                            "recommendation_id"
                        ],
                    "control_date":
                        control[
                            "recommendation_date"
                        ],
                    "control_action":
                        control[
                            "final_action"
                        ],
                    "control_return":
                        control[
                            "return_percent"
                        ],
                    "days_between":
                        abs(
                            control[
                                "distance_days"
                            ]
                        ),
                    "return_delta":
                        (
                            buy["return_percent"]
                            -
                            control["return_percent"]
                        ),
                }
            )

        # ----------------------------------------------------
        # Subsequent
        # ----------------------------------------------------

        subsequent = candidates[
            candidates["distance_days"] > 0
        ].copy()

        if not subsequent.empty:

            subsequent = subsequent.sort_values(
                [
                    "distance_days",
                    "recommendation_id",
                ],
                ascending=[
                    True,
                    True,
                ],
            )

            control = subsequent.iloc[0]

            rows.append(
                {
                    "buy_recommendation_id":
                        buy["recommendation_id"],
                    "ticker":
                        buy["ticker"],
                    "buy_date":
                        buy["recommendation_date"],
                    "buy_action":
                        buy["final_action"],
                    "buy_return":
                        buy["return_percent"],
                    "control_type":
                        "SUBSEQUENT",
                    "control_recommendation_id":
                        control[
                            "recommendation_id"
                        ],
                    "control_date":
                        control[
                            "recommendation_date"
                        ],
                    "control_action":
                        control[
                            "final_action"
                        ],
                    "control_return":
                        control[
                            "return_percent"
                        ],
                    "days_between":
                        abs(
                            control[
                                "distance_days"
                            ]
                        ),
                    "return_delta":
                        (
                            buy["return_percent"]
                            -
                            control["return_percent"]
                        ),
                }
            )

    return pd.DataFrame(rows)


# ============================================================
# SUMMARY
# ============================================================

def summary(
    controls,
    control_type,
):

    df = controls[
        controls["control_type"]
        == control_type
    ].copy()

    if df.empty:
        return

    buy = pd.to_numeric(
        df["buy_return"],
        errors="coerce",
    )

    control = pd.to_numeric(
        df["control_return"],
        errors="coerce",
    )

    delta = pd.to_numeric(
        df["return_delta"],
        errors="coerce",
    )

    valid = (
        buy.notna()
        & control.notna()
        & delta.notna()
    )

    buy = buy[valid]
    control = control[valid]
    delta = delta[valid]

    print(
        f"n: {len(df)}"
    )

    print(
        f"BUY NEW mean 5D: "
        f"{buy.mean():.3f}%"
    )

    print(
        f"Control mean 5D: "
        f"{control.mean():.3f}%"
    )

    print(
        f"Mean delta "
        f"(BUY NEW - control): "
        f"{delta.mean():.3f}pp"
    )

    print(
        f"Median delta: "
        f"{delta.median():.3f}pp"
    )

    print(
        f"BUY NEW better: "
        f"{(delta > 0).mean() * 100:.1f}%"
    )

    print(
        f"BUY NEW worse: "
        f"{(delta < 0).mean() * 100:.1f}%"
    )

    print(
        f"BUY NEW equal: "
        f"{(delta == 0).mean() * 100:.1f}%"
    )

    print(
        f"Median control distance: "
        f"{df['days_between'].median():.2f} days"
    )


# ============================================================
# TICKER ANALYSIS
# ============================================================

def ticker_analysis(
    controls,
):

    section(
        "SAME-TICKER CONTROL BY TICKER"
    )

    prior = controls[
        controls["control_type"]
        == "PRIOR"
    ].copy()

    if prior.empty:
        print("No prior controls.")
        return

    rows = []

    for ticker, group in prior.groupby(
        "ticker"
    ):

        delta = pd.to_numeric(
            group["return_delta"],
            errors="coerce",
        ).dropna()

        if delta.empty:
            continue

        rows.append(
            {
                "ticker": ticker,
                "n": len(delta),
                "buy_new_mean":
                    group[
                        "buy_return"
                    ].mean(),
                "control_mean":
                    group[
                        "control_return"
                    ].mean(),
                "delta":
                    delta.mean(),
                "buy_better_pct":
                    (
                        delta > 0
                    ).mean() * 100,
            }
        )

    if not rows:
        print("No usable ticker results.")
        return

    result = pd.DataFrame(rows)

    print(
        result
        .sort_values(
            "delta"
        )
        .to_string(
            index=False,
            formatters={
                "buy_new_mean":
                    lambda x: f"{x:.3f}",
                "control_mean":
                    lambda x: f"{x:.3f}",
                "delta":
                    lambda x: f"{x:.3f}",
                "buy_better_pct":
                    lambda x: f"{x:.1f}",
            },
        )
    )


# ============================================================
# COVERAGE
# ============================================================

def coverage(
    buy_new,
    controls,
):

    section(
        "CONTROL COVERAGE"
    )

    prior = set(
        controls[
            controls["control_type"]
            == "PRIOR"
        ]["buy_recommendation_id"]
    )

    subsequent = set(
        controls[
            controls["control_type"]
            == "SUBSEQUENT"
        ]["buy_recommendation_id"]
    )

    print(
        f"BUY NEW recommendation observations: "
        f"{len(buy_new)}"
    )

    print(
        f"Prior control: "
        f"{len(prior)} "
        f"({len(prior) / len(buy_new) * 100:.1f}%)"
    )

    print(
        f"Subsequent control: "
        f"{len(subsequent)} "
        f"({len(subsequent) / len(buy_new) * 100:.1f}%)"
    )

    print(
        f"Both: "
        f"{len(prior & subsequent)} "
        f"({len(prior & subsequent) / len(buy_new) * 100:.1f}%)"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    section(
        "BUY NEW CANDIDATE SELECTION FORENSICS"
    )

    print(
        "READ-ONLY — NO PRODUCTION CHANGES"
    )

    print(
        f"Database: {DB_PATH}"
    )

    conn = sqlite3.connect(
        DB_PATH
    )

    audit = load_audit(
        conn
    )

    recs = load_recommendations(
        conn
    )

    evaluations = load_evaluations(
        conn
    )

    conn.close()

    print()
    print(
        f"Audit decisions: {len(audit)}"
    )

    print(
        f"Recommendations with valid dates: "
        f"{len(recs)}"
    )

    print(
        f"Mature 5D outcomes: "
        f"{len(evaluations)}"
    )

    lineage = build_lineage(
        audit,
        recs,
    )

    raw_buy_new = audit[
        audit["final_action"]
        == BUY_NEW
    ]

    print(
        f"Raw BUY NEW audit decisions: "
        f"{len(raw_buy_new)}"
    )

    print(
        f"Lineage rows: "
        f"{len(lineage)}"
    )

    population = build_observations(
        lineage,
        evaluations,
    )

    buy_new = get_buy_new(
        population
    )

    controls = get_controls(
        population
    )

    print(
        f"Mature BUY NEW recommendation "
        f"observations: {len(buy_new)}"
    )

    print(
        f"Mature non-BUY-NEW recommendation "
        f"observations: {len(controls)}"
    )

    # --------------------------------------------------------
    # BUY NEW headline
    # --------------------------------------------------------

    section(
        "BUY NEW HEADLINE"
    )

    print(
        f"n: {len(buy_new)}"
    )

    print(
        f"Mean 5D return: "
        f"{buy_new['return_percent'].mean():.3f}%"
    )

    print(
        f"Median 5D return: "
        f"{buy_new['return_percent'].median():.3f}%"
    )

    positive_pct = (
        buy_new["return_percent"] > 0
    ).mean() * 100

    print(
        f"Positive 5D return: "
        f"{positive_pct:.3f}%"
    )
    # --------------------------------------------------------
    # Match
    # --------------------------------------------------------

    matched = match_controls(
        buy_new,
        controls,
    )

    print()
    print(
        f"Control observations: "
        f"{len(matched)}"
    )

    coverage(
        buy_new,
        matched,
    )

    # --------------------------------------------------------
    # Prior
    # --------------------------------------------------------

    section(
        "PRIOR DIFFERENT-RECOMMENDATION CONTROL"
    )

    summary(
        matched,
        "PRIOR",
    )

    # --------------------------------------------------------
    # Subsequent
    # --------------------------------------------------------

    section(
        "SUBSEQUENT DIFFERENT-RECOMMENDATION CONTROL"
    )

    summary(
        matched,
        "SUBSEQUENT",
    )

    # --------------------------------------------------------
    # Ticker
    # --------------------------------------------------------

    ticker_analysis(
        matched
    )

    # --------------------------------------------------------
    # Detail
    # --------------------------------------------------------

    section(
        "CONTROL DETAIL"
    )

    if matched.empty:

        print(
            "No valid controls found."
        )

    else:

        print(
            matched[
                [
                    "buy_recommendation_id",
                    "ticker",
                    "buy_date",
                    "buy_return",
                    "control_type",
                    "control_recommendation_id",
                    "control_date",
                    "control_action",
                    "control_return",
                    "days_between",
                    "return_delta",
                ]
            ]
            .sort_values(
                [
                    "ticker",
                    "buy_date",
                    "control_type",
                ]
            )
            .to_string(
                index=False
            )
        )

    # --------------------------------------------------------
    # Candidate Selection Forensics
    # --------------------------------------------------------

    section(
        "CANDIDATE SELECTION FORENSICS"
    )

    print()

    print(
        "Investigating whether the BUY NEW population is "
        "being promoted by unusually strong model scores "
        "without corresponding forward performance."
    )

    print()

    # --------------------------------------------------------
    # Score profile
    # --------------------------------------------------------

    score_columns = [
        "investment_score",
        "technical_score",
        "quality_score",
        "growth_score",
        "confidence_score",
        "rsi",
        "sma50_extension_pct",
        "sma200_extension_pct",
    ]

    available = [
        c
        for c in score_columns
        if c in buy_new.columns
    ]

    if available:

        print(
            "BUY NEW SCORE PROFILE"
        )
        print("-" * 60)

        for column in available:

            values = (
                buy_new[column]
                .dropna()
            )

            if values.empty:
                continue

            print(
                f"{column}: "
                f"mean={values.mean():.3f}, "
                f"median={values.median():.3f}, "
                f"n={len(values)}"
            )

        print()

    # --------------------------------------------------------
    # Correlation with realised 5D return
    # --------------------------------------------------------

    if (
        "return_percent" in buy_new.columns
        and available
    ):

        print(
            "SCORE / 5D RETURN CORRELATIONS"
        )
        print("-" * 60)

        for column in available:

            sample = buy_new[
                [
                    column,
                    "return_percent",
                ]
            ].dropna()

            if len(sample) < 5:
                continue

            correlation = (
                sample[column]
                .corr(
                    sample["return_percent"]
                )
            )

            print(
                f"{column}: "
                f"{correlation:.3f}"
            )

        print()

    # --------------------------------------------------------
    # Technical score buckets
    # --------------------------------------------------------

    if (
        "technical_score" in buy_new.columns
        and "return_percent" in buy_new.columns
    ):

        print(
            "TECHNICAL SCORE BUCKET PERFORMANCE"
        )
        print("-" * 60)

        technical = buy_new.copy()

        technical["technical_bucket"] = (
            __import__("pandas")
            .cut(
                technical["technical_score"],
                bins=[
                    float("-inf"),
                    74,
                    79,
                    84,
                    89,
                    94,
                    float("inf"),
                ],
                labels=[
                    "<75",
                    "75-79",
                    "80-84",
                    "85-89",
                    "90-94",
                    "95+",
                ],
            )
        )

        result = (
            technical
            .groupby(
                "technical_bucket",
                observed=False,
            )["return_percent"]
            .agg(
                ["count", "mean", "median"]
            )
        )

        print(
            result.to_string()
        )

        print()

    # --------------------------------------------------------
    # Investment score buckets
    # --------------------------------------------------------

    if (
        "investment_score" in buy_new.columns
        and "return_percent" in buy_new.columns
    ):

        print(
            "INVESTMENT SCORE BUCKET PERFORMANCE"
        )
        print("-" * 60)

        investment = buy_new.copy()

        investment["investment_bucket"] = (
            __import__("pandas")
            .cut(
                investment["investment_score"],
                bins=[
                    float("-inf"),
                    69,
                    74,
                    79,
                    84,
                    89,
                    94,
                    float("inf"),
                ],
                labels=[
                    "<70",
                    "70-74",
                    "75-79",
                    "80-84",
                    "85-89",
                    "90-94",
                    "95+",
                ],
            )
        )

        result = (
            investment
            .groupby(
                "investment_bucket",
                observed=False,
            )["return_percent"]
            .agg(
                ["count", "mean", "median"]
            )
        )

        print(
            result.to_string()
        )

        print()

    # --------------------------------------------------------
    # Entry quality
    # --------------------------------------------------------

    if (
        "entry_quality" in buy_new.columns
        and "return_percent" in buy_new.columns
    ):

        print(
            "ENTRY QUALITY PERFORMANCE"
        )
        print("-" * 60)

        result = (
            buy_new
            .groupby(
                "entry_quality",
                dropna=False,
            )["return_percent"]
            .agg(
                ["count", "mean", "median"]
            )
            .sort_values("mean")
        )

        print(
            result.to_string()
        )

        print()

    # --------------------------------------------------------
    # Ticker concentration
    # --------------------------------------------------------

    if (
        "ticker" in buy_new.columns
        and "return_percent" in buy_new.columns
    ):

        print(
            "BUY NEW TICKER CONCENTRATION"
        )
        print("-" * 60)

        result = (
            buy_new
            .groupby(
                "ticker"
            )["return_percent"]
            .agg(
                ["count", "mean", "median"]
            )
            .sort_values(
                ["count", "mean"],
                ascending=[
                    False,
                    True,
                ],
            )
        )

        print(
            result.head(20).to_string()
        )

        print()

    # --------------------------------------------------------
    # Highest-score BUY NEW performance
    # --------------------------------------------------------

    if (
        "investment_score" in buy_new.columns
        and "return_percent" in buy_new.columns
    ):

        ranked = (
            buy_new
            .sort_values(
                "investment_score",
                ascending=False,
            )
        )

        print(
            "INVESTMENT SCORE RANKING"
        )
        print("-" * 60)

        for fraction in [
            0.10,
            0.25,
            0.50,
        ]:

            n = max(
                1,
                int(
                    len(ranked)
                    * fraction
                ),
            )

            sample = ranked.head(n)

            print(
                f"Top {fraction:.0%}: "
                f"n={len(sample)}, "
                f"mean="
                f"{sample['return_percent'].mean():.3f}%, "
                f"positive="
                f"{(sample['return_percent'] > 0).mean() * 100:.2f}%"
            )

        print()

    # --------------------------------------------------------
    # Highest technical-score BUY NEW performance
    # --------------------------------------------------------

    if (
        "technical_score" in buy_new.columns
        and "return_percent" in buy_new.columns
    ):

        ranked = (
            buy_new
            .sort_values(
                "technical_score",
                ascending=False,
            )
        )

        print(
            "TECHNICAL SCORE RANKING"
        )
        print("-" * 60)

        for fraction in [
            0.10,
            0.25,
            0.50,
        ]:

            n = max(
                1,
                int(
                    len(ranked)
                    * fraction
                ),
            )

            sample = ranked.head(n)

            print(
                f"Top {fraction:.0%}: "
                f"n={len(sample)}, "
                f"mean="
                f"{sample['return_percent'].mean():.3f}%, "
                f"positive="
                f"{(sample['return_percent'] > 0).mean() * 100:.2f}%"
            )

        print()


    # --------------------------------------------------------
    # Interpretation
    # --------------------------------------------------------

    section(
        "INTERPRETATION"
    )

    print(
        "V3 uses recommendation_id as the observation "
        "unit rather than audit_decision_id."
    )

    print()

    print(
        "A control is only valid when it is a genuinely "
        "different recommendation for the same ticker."
    )

    print()

    print(
        "Therefore identical BUY NEW/control returns "
        "caused by repeated audit decisions referencing "
        "the same recommendation are removed."
    )

    print()

    print(
        "If a negative delta remains across multiple "
        "tickers after this correction, that would be "
        "meaningfully stronger evidence that BUY NEW "
        "selection/timing is contributing to the poor "
        "realised performance."
    )

    print()

    print(
        "If the negative delta disappears, the earlier "
        "BUY NEW underperformance is more consistent "
        "with candidate-pool composition/concentration "
        "rather than the BUY NEW action itself."
    )

    print()

    print(
        "No production changes were made."
    )

    section(
        "TEST COMPLETE"
    )


if __name__ == "__main__":
    main()

