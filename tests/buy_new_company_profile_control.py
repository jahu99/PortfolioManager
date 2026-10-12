#!/usr/bin/env python3
"""
A6 — BUY NEW Company Profile Control Test

READ-ONLY INVESTIGATION.

Purpose
-------
Determine whether BUY NEW is selecting the right type of companies by
comparing the realised 5D performance and company characteristics of:

    1. BUY NEW decisions
    2. Non-BUY-NEW governed decisions

The test is deliberately diagnostic only.

It does NOT:
    - change production logic
    - change thresholds
    - change scores
    - change learning
    - change governance
    - write to the database
    - write production files

Lineage
-------
Direct lineage:
    audit_decisions.recommendation_id is populated.

Legacy lineage:
    recommendation_id is missing, so the latest recommendation for the
    same ticker on or before the audit decision date is selected.

Important:
    This implementation deliberately does NOT use pd.merge_asof().
    Historical data contains null dates, and merge_asof() is unnecessarily
    fragile for this lineage reconstruction.
"""

from pathlib import Path
import sqlite3

import numpy as np
import pandas as pd


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DB_PATH = (
    PROJECT_ROOT
    / "data"
    / "portfolio_manager.db"
)


# ============================================================
# GENERAL HELPERS
# ============================================================

def normalise_datetime(series):
    """
    Normalise mixed-format timestamps to timezone-naive UTC datetimes.

    The database contains both:
        YYYY-MM-DD
        YYYY-MM-DDTHH:MM:SS+00:00
        YYYY-MM-DDTHH:MM:SS.ssssss+00:00

    format="mixed" is required so pandas does not reject valid
    values simply because the column contains multiple formats.
    """
    return (
        pd.to_datetime(
            series,
            errors="coerce",
            format="mixed",
            utc=True,
        )
        .dt.tz_localize(None)
    )

def load_table(conn, sql):
    """
    Execute SQL and return a DataFrame.
    """
    return pd.read_sql_query(
        sql,
        conn,
    )


def numeric_series(df, column):
    """
    Return a numeric Series or an all-NaN Series if the column
    does not exist.
    """
    if column not in df.columns:
        return pd.Series(
            np.nan,
            index=df.index,
            dtype=float,
        )

    return pd.to_numeric(
        df[column],
        errors="coerce",
    )


def coalesce_columns(
    df,
    target_column,
    candidate_columns,
):
    """
    Populate target_column using the first non-null value from
    candidate_columns.

    This is used because recommendation/evidence joins can create
    suffixed columns.
    """

    result = None

    for column in candidate_columns:

        if column not in df.columns:
            continue

        series = df[column]

        if result is None:
            result = series.copy()
        else:
            result = result.combine_first(
                series
            )

    if result is None:
        df[target_column] = np.nan
    else:
        df[target_column] = result

    return df


# ============================================================
# DATABASE LOADERS
# ============================================================

def load_recommendations(conn):
    """
    Load recommendation-level information.
    """

    return load_table(
        conn,
        """
        SELECT
            id AS recommendation_id,
            date AS recommendation_date,
            ticker,
            signal,
            investment_score,
            technical_score,
            quality_score,
            growth_score,
            confidence_score
        FROM recommendations
        """,
    )


def load_evidence(conn):
    """
    Load recommendation evidence.
    """

    return load_table(
        conn,
        """
        SELECT
            recommendation_id,
            ticker AS evidence_ticker,
            capture_date,

            signal AS evidence_signal,

            investment_score
                AS evidence_investment_score,

            technical_score
                AS evidence_technical_score,

            quality_score
                AS evidence_quality_score,

            growth_score
                AS evidence_growth_score,

            confidence_score
                AS evidence_confidence_score,

            entry_price,
            rsi,
            extension_sma50_pct,
            extension_sma200_pct,

            revenue_growth,
            profit_margin,
            return_on_equity,
            debt_to_equity,

            entry_quality

        FROM recommendation_evidence
        """,
    )


def load_evaluations(conn):
    """
    Load mature 5D recommendation outcomes.
    """

    return load_table(
        conn,
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
    )


def load_audit_decisions(conn):
    """
    Load governed audit decisions.

    audit_decisions is the source of truth for final governed action.
    """

    return load_table(
        conn,
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
    )


# ============================================================
# LINEAGE
# ============================================================

def build_buy_new_lineage(
    audit_decisions,
    recommendations,
):
    """
    Reconstruct BUY NEW lineage.

    Direct:
        audit_decisions.recommendation_id exists.

    Legacy:
        recommendation_id is missing.

        For legacy decisions we select the latest recommendation for
        the same ticker whose recommendation date is on or before
        the audit date.

    No merge_asof() is used.
    """

    audit = audit_decisions.copy()

    recs = recommendations.copy()

    # --------------------------------------------------------
    # NORMALISE DATES
    # --------------------------------------------------------

    audit["audit_date"] = normalise_datetime(
        audit["audit_date"]
    )

    recs["recommendation_date"] = normalise_datetime(
        recs["recommendation_date"]
    )

    recs = recs[
        recs["recommendation_date"].notna()
    ].copy()

    # --------------------------------------------------------
    # NORMALISE TICKERS
    # --------------------------------------------------------

    audit["ticker"] = (
        audit["ticker"]
        .astype("string")
        .str.strip()
        .str.upper()
    )

    recs["ticker"] = (
        recs["ticker"]
        .astype("string")
        .str.strip()
        .str.upper()
    )

    # --------------------------------------------------------
    # DIRECT LINEAGE
    # --------------------------------------------------------

    direct = audit[
        audit["recommendation_id"].notna()
    ].copy()

    direct["lineage_type"] = "DIRECT"

    direct["lineage_recommendation_id"] = (
        direct["recommendation_id"]
    )

    direct["lineage_recommendation_date"] = pd.NaT

    # --------------------------------------------------------
    # LEGACY LINEAGE
    # --------------------------------------------------------

    legacy = audit[
        audit["recommendation_id"].isna()
    ].copy()

    legacy["lineage_type"] = "LEGACY"

    legacy["lineage_recommendation_id"] = pd.NA

    legacy["lineage_recommendation_date"] = pd.NaT

    # --------------------------------------------------------
    # ELIGIBLE RECOMMENDATIONS
    # --------------------------------------------------------

    eligible = recs[
        recs["ticker"].notna()
        & recs["recommendation_date"].notna()
        & recs["recommendation_id"].notna()
    ].copy()

    eligible["recommendation_id"] = pd.to_numeric(
        eligible["recommendation_id"],
        errors="coerce",
    )

    eligible = eligible[
        eligible["recommendation_id"].notna()
    ].copy()

    eligible = eligible.sort_values(
        [
            "ticker",
            "recommendation_date",
            "recommendation_id",
        ]
    )

    # --------------------------------------------------------
    # BUILD TICKER LOOKUP
    # --------------------------------------------------------

    recommendation_groups = {}

    for ticker, group in eligible.groupby(
        "ticker",
        sort=False,
    ):
        recommendation_groups[ticker] = (
            group.reset_index(drop=True)
        )

    # --------------------------------------------------------
    # RESOLVE LEGACY ROWS
    # --------------------------------------------------------

    resolved_rows = []

    unresolved_rows = []

    for _, row in legacy.iterrows():

        ticker = row["ticker"]

        audit_date = row["audit_date"]

        # Missing ticker/date cannot be resolved.
        if pd.isna(ticker):
            unresolved_rows.append(row)
            continue

        if pd.isna(audit_date):
            unresolved_rows.append(row)
            continue

        if ticker not in recommendation_groups:
            unresolved_rows.append(row)
            continue

        candidates = recommendation_groups[
            ticker
        ]

        candidates = candidates[
            candidates["recommendation_date"]
            <= audit_date
        ]

        if candidates.empty:
            unresolved_rows.append(row)
            continue

        # Because candidates are sorted chronologically,
        # the final row is the latest eligible recommendation.
        matched = candidates.iloc[-1]

        resolved_row = row.copy()

        resolved_row[
            "lineage_recommendation_id"
        ] = matched[
            "recommendation_id"
        ]

        resolved_row[
            "lineage_recommendation_date"
        ] = matched[
            "recommendation_date"
        ]

        resolved_rows.append(
            resolved_row
        )

    # --------------------------------------------------------
    # DATAFRAMES
    # --------------------------------------------------------

    if resolved_rows:

        legacy_resolved = pd.DataFrame(
            resolved_rows
        )

    else:

        legacy_resolved = (
            legacy.iloc[0:0].copy()
        )

    if unresolved_rows:

        unresolved = pd.DataFrame(
            unresolved_rows
        )

    else:

        unresolved = (
            legacy.iloc[0:0].copy()
        )

    # --------------------------------------------------------
    # COMBINE DIRECT + LEGACY
    # --------------------------------------------------------

    lineage_parts = []

    if not direct.empty:
        lineage_parts.append(
            direct
        )

    if not legacy_resolved.empty:
        lineage_parts.append(
            legacy_resolved
        )

    if lineage_parts:

        lineage = pd.concat(
            lineage_parts,
            ignore_index=True,
            sort=False,
        )

    else:

        lineage = audit.iloc[0:0].copy()

    return (
        lineage,
        unresolved,
    )


# ============================================================
# BUILD MATURE POPULATION
# ============================================================

def build_population(
    lineage,
    recommendations,
    evidence,
    evaluations,
):
    """
    Join governed audit lineage to recommendation evidence and
    mature 5D outcomes.
    """

    population = lineage.copy()

    # Only lineage that actually resolved to a recommendation.
    population = population[
        population[
            "lineage_recommendation_id"
        ].notna()
    ].copy()

    # --------------------------------------------------------
    # NORMALISE IDS
    # --------------------------------------------------------

    population[
        "lineage_recommendation_id"
    ] = pd.to_numeric(
        population[
            "lineage_recommendation_id"
        ],
        errors="coerce",
    )

    recommendations = recommendations.copy()

    recommendations[
        "recommendation_id"
    ] = pd.to_numeric(
        recommendations[
            "recommendation_id"
        ],
        errors="coerce",
    )

    evidence = evidence.copy()

    evidence[
        "recommendation_id"
    ] = pd.to_numeric(
        evidence[
            "recommendation_id"
        ],
        errors="coerce",
    )

    evaluations = evaluations.copy()

    evaluations[
        "recommendation_id"
    ] = pd.to_numeric(
        evaluations[
            "recommendation_id"
        ],
        errors="coerce",
    )

    # --------------------------------------------------------
    # RECOMMENDATION JOIN
    # --------------------------------------------------------

    population = population.merge(
        recommendations,
        left_on="lineage_recommendation_id",
        right_on="recommendation_id",
        how="left",
        suffixes=(
            "",
            "_recommendation",
        ),
    )

    # --------------------------------------------------------
    # EVIDENCE JOIN
    # --------------------------------------------------------

    population = population.merge(
        evidence,
        left_on="lineage_recommendation_id",
        right_on="recommendation_id",
        how="left",
        suffixes=(
            "",
            "_evidence",
        ),
    )

    # --------------------------------------------------------
    # 5D OUTCOME JOIN
    # --------------------------------------------------------

    population = population.merge(
        evaluations,
        left_on="lineage_recommendation_id",
        right_on="recommendation_id",
        how="inner",
        suffixes=(
            "",
            "_evaluation",
        ),
    )

    # --------------------------------------------------------
    # SCORE COALESCING
    # --------------------------------------------------------

    population = coalesce_columns(
        population,
        "investment_score_final",
        [
            "evidence_investment_score",
            "investment_score",
            "investment_score_recommendation",
        ],
    )

    population = coalesce_columns(
        population,
        "technical_score_final",
        [
            "evidence_technical_score",
            "technical_score",
            "technical_score_recommendation",
        ],
    )

    population = coalesce_columns(
        population,
        "quality_score_final",
        [
            "evidence_quality_score",
            "quality_score",
            "quality_score_recommendation",
        ],
    )

    population = coalesce_columns(
        population,
        "growth_score_final",
        [
            "evidence_growth_score",
            "growth_score",
            "growth_score_recommendation",
        ],
    )

    population = coalesce_columns(
        population,
        "confidence_score_final",
        [
            "evidence_confidence_score",
            "confidence_score",
            "confidence_score_recommendation",
        ],
    )

    # --------------------------------------------------------
    # OTHER EVIDENCE FIELDS
    # --------------------------------------------------------

    population = coalesce_columns(
        population,
        "rsi_final",
        [
            "rsi",
            "rsi_evidence",
        ],
    )

    population = coalesce_columns(
        population,
        "extension_sma50_final",
        [
            "extension_sma50_pct",
            "extension_sma50_pct_evidence",
        ],
    )

    population = coalesce_columns(
        population,
        "extension_sma200_final",
        [
            "extension_sma200_pct",
            "extension_sma200_pct_evidence",
        ],
    )

    population = coalesce_columns(
        population,
        "revenue_growth_final",
        [
            "revenue_growth",
            "revenue_growth_evidence",
        ],
    )

    population = coalesce_columns(
        population,
        "profit_margin_final",
        [
            "profit_margin",
            "profit_margin_evidence",
        ],
    )

    population = coalesce_columns(
        population,
        "roe_final",
        [
            "return_on_equity",
            "return_on_equity_evidence",
        ],
    )

    population = coalesce_columns(
        population,
        "debt_to_equity_final",
        [
            "debt_to_equity",
            "debt_to_equity_evidence",
        ],
    )

    population = coalesce_columns(
        population,
        "entry_quality_final",
        [
            "entry_quality",
            "entry_quality_evidence",
        ],
    )

    population = coalesce_columns(
        population,
        "signal_final",
        [
            "evidence_signal",
            "signal",
            "signal_recommendation",
        ],
    )

    # --------------------------------------------------------
    # BUY NEW FLAG
    # --------------------------------------------------------

    population[
        "is_buy_new"
    ] = (
        population[
            "final_action"
        ]
        .astype("string")
        .str.upper()
        .eq("BUY NEW")
    )

    return population


# ============================================================
# LINEAGE SUMMARY
# ============================================================

def print_lineage_summary(
    lineage,
    unresolved,
):
    """
    Print lineage statistics specifically for BUY NEW.
    """

    raw_buy_new = lineage[
        lineage[
            "final_action"
        ]
        .astype("string")
        .str.upper()
        .eq("BUY NEW")
    ].copy()

    direct_count = (
        raw_buy_new[
            "lineage_type"
        ]
        .eq("DIRECT")
        .sum()
    )

    legacy_count = (
        raw_buy_new[
            "lineage_type"
        ]
        .eq("LEGACY")
        .sum()
    )

    print(
        f"Raw BUY NEW audit decisions: "
        f"{len(raw_buy_new)}"
    )

    print(
        f"Direct lineage: "
        f"{direct_count}"
    )

    print(
        f"Reconstructed legacy lineage: "
        f"{legacy_count}"
    )

    print(
        f"Unresolved lineage: "
        f"{len(unresolved)}"
    )


# ============================================================
# GROUP SUMMARY
# ============================================================

def print_group_summary(
    title,
    population,
):
    """
    Print realised 5D performance.
    """

    print()
    print("=" * 78)
    print(title)
    print("=" * 78)

    if population.empty:

        print(
            "No observations."
        )

        return

    returns = pd.to_numeric(
        population[
            "return_percent"
        ],
        errors="coerce",
    ).dropna()

    if returns.empty:

        print(
            "No realised returns."
        )

        return

    print(
        f"n: {len(returns)}"
    )

    print(
        f"Mean 5D return: "
        f"{returns.mean():.3f}%"
    )

    print(
        f"Median 5D return: "
        f"{returns.median():.3f}%"
    )

    print(
        f"Positive rate: "
        f"{(returns > 0).mean() * 100:.3f}%"
    )


# ============================================================
# COMPANY PROFILE
# ============================================================

def print_feature_profile(
    buy_new,
    non_buy_new,
):
    """
    Compare the BUY NEW company profile with the non-BUY-NEW
    population.
    """

    print()
    print("=" * 78)
    print("BUY NEW COMPANY PROFILE")
    print("=" * 78)

    features = [
        (
            "Investment Score",
            "investment_score_final",
        ),
        (
            "Technical Score",
            "technical_score_final",
        ),
        (
            "Quality Score",
            "quality_score_final",
        ),
        (
            "Growth Score",
            "growth_score_final",
        ),
        (
            "Confidence Score",
            "confidence_score_final",
        ),
        (
            "RSI",
            "rsi_final",
        ),
        (
            "SMA50 Extension",
            "extension_sma50_final",
        ),
        (
            "SMA200 Extension",
            "extension_sma200_final",
        ),
        (
            "Revenue Growth",
            "revenue_growth_final",
        ),
        (
            "Profit Margin",
            "profit_margin_final",
        ),
        (
            "ROE",
            "roe_final",
        ),
        (
            "Debt / Equity",
            "debt_to_equity_final",
        ),
    ]

    for label, column in features:

        buy_values = numeric_series(
            buy_new,
            column,
        ).dropna()

        non_values = numeric_series(
            non_buy_new,
            column,
        ).dropna()

        if (
            buy_values.empty
            or non_values.empty
        ):
            continue

        diff = (
            buy_values.mean()
            - non_values.mean()
        )

        print(
            f"{label}: "
            f"BUY NEW={buy_values.mean():.3f} "
            f"vs NON={non_values.mean():.3f} "
            f"diff={diff:+.3f}"
        )


# ============================================================
# WINNERS VS LOSERS
# ============================================================

def print_winners_vs_losers(
    buy_new,
):
    """
    Compare BUY NEW winners with BUY NEW non-winners.
    """

    print()
    print("=" * 78)
    print("BUY NEW WINNERS VS LOSERS")
    print("=" * 78)

    returns = pd.to_numeric(
        buy_new[
            "return_percent"
        ],
        errors="coerce",
    )

    winners = buy_new[
        returns > 0
    ].copy()

    losers = buy_new[
        returns <= 0
    ].copy()

    print(
        f"Winners: {len(winners)}"
    )

    print(
        f"Losers/non-positive: "
        f"{len(losers)}"
    )

    if (
        winners.empty
        or losers.empty
    ):
        return

    features = [
        (
            "Investment Score",
            "investment_score_final",
        ),
        (
            "Technical Score",
            "technical_score_final",
        ),
        (
            "Quality Score",
            "quality_score_final",
        ),
        (
            "Growth Score",
            "growth_score_final",
        ),
        (
            "Confidence Score",
            "confidence_score_final",
        ),
        (
            "RSI",
            "rsi_final",
        ),
        (
            "SMA50 Extension",
            "extension_sma50_final",
        ),
        (
            "SMA200 Extension",
            "extension_sma200_final",
        ),
        (
            "Revenue Growth",
            "revenue_growth_final",
        ),
        (
            "Profit Margin",
            "profit_margin_final",
        ),
        (
            "ROE",
            "roe_final",
        ),
        (
            "Debt / Equity",
            "debt_to_equity_final",
        ),
    ]

    for label, column in features:

        winner_values = numeric_series(
            winners,
            column,
        ).dropna()

        loser_values = numeric_series(
            losers,
            column,
        ).dropna()

        if (
            winner_values.empty
            or loser_values.empty
        ):
            continue

        diff = (
            winner_values.mean()
            - loser_values.mean()
        )

        print(
            f"{label}: "
            f"WIN={winner_values.mean():.3f} "
            f"LOSS={loser_values.mean():.3f} "
            f"diff={diff:+.3f}"
        )

    if (
        "entry_quality_final"
        in buy_new.columns
    ):

        print()
        print(
            "Winner Entry Quality:"
        )

        print(
            winners[
                "entry_quality_final"
            ]
            .value_counts(
                dropna=False
            )
            .to_string()
        )

        print()
        print(
            "Loser Entry Quality:"
        )

        print(
            losers[
                "entry_quality_final"
            ]
            .value_counts(
                dropna=False
            )
            .to_string()
        )


# ============================================================
# CORRELATIONS
# ============================================================

def print_correlations(
    buy_new,
):
    """
    Calculate feature correlations with realised 5D return
    within BUY NEW only.

    These are diagnostic signals, not causal conclusions.
    """

    print()
    print("=" * 78)
    print(
        "BUY NEW FEATURE CORRELATIONS "
        "WITH 5D RETURN"
    )
    print("=" * 78)

    features = [
        (
            "Investment Score",
            "investment_score_final",
        ),
        (
            "Technical Score",
            "technical_score_final",
        ),
        (
            "Quality Score",
            "quality_score_final",
        ),
        (
            "Growth Score",
            "growth_score_final",
        ),
        (
            "Confidence Score",
            "confidence_score_final",
        ),
        (
            "RSI",
            "rsi_final",
        ),
        (
            "SMA50 Extension",
            "extension_sma50_final",
        ),
        (
            "SMA200 Extension",
            "extension_sma200_final",
        ),
        (
            "Revenue Growth",
            "revenue_growth_final",
        ),
        (
            "Profit Margin",
            "profit_margin_final",
        ),
        (
            "ROE",
            "roe_final",
        ),
        (
            "Debt / Equity",
            "debt_to_equity_final",
        ),
    ]

    returns = pd.to_numeric(
        buy_new[
            "return_percent"
        ],
        errors="coerce",
    )

    for label, column in features:

        values = numeric_series(
            buy_new,
            column,
        )

        mask = (
            values.notna()
            & returns.notna()
        )

        if mask.sum() < 3:
            continue

        correlation = (
            values[mask]
            .corr(
                returns[mask]
            )
        )

        print(
            f"{label}: "
            f"{correlation:+.3f} "
            f"(n={mask.sum()})"
        )


# ============================================================
# TICKER CONCENTRATION
# ============================================================

def print_ticker_concentration(
    buy_new,
):
    """
    Show whether BUY NEW performance is concentrated in a small
    number of tickers.
    """

    print()
    print("=" * 78)
    print(
        "BUY NEW TICKER CONCENTRATION"
    )
    print("=" * 78)

    if buy_new.empty:
        return

    returns = pd.to_numeric(
        buy_new[
            "return_percent"
        ],
        errors="coerce",
    )

    working = buy_new.copy()

    working[
        "return_percent"
    ] = returns

    summary = (
        working
        .groupby(
            "ticker",
            dropna=False,
        )
        .agg(
            n=(
                "return_percent",
                "count",
            ),
            mean_5d=(
                "return_percent",
                "mean",
            ),
            positive_rate=(
                "return_percent",
                lambda x:
                (x > 0).mean() * 100,
            ),
        )
        .sort_values(
            [
                "n",
                "mean_5d",
            ],
            ascending=[
                False,
                True,
            ],
        )
    )

    print(
        summary.to_string()
    )


# ============================================================
# SIGNAL MIX
# ============================================================

def print_signal_mix(
    buy_new,
):
    """
    Show BUY NEW signal composition.
    """

    print()
    print("=" * 78)
    print(
        "BUY NEW SIGNAL MIX"
    )
    print("=" * 78)

    if (
        "signal_final"
        not in buy_new.columns
    ):
        return

    print(
        buy_new[
            "signal_final"
        ]
        .value_counts(
            dropna=False
        )
        .to_string()
    )


# ============================================================
# ENTRY QUALITY
# ============================================================

def print_entry_quality(
    buy_new,
):
    """
    Compare realised performance by entry-quality classification.
    """

    print()
    print("=" * 78)
    print(
        "BUY NEW ENTRY QUALITY"
    )
    print("=" * 78)

    if (
        "entry_quality_final"
        not in buy_new.columns
    ):
        return

    working = buy_new.copy()

    working[
        "return_percent"
    ] = pd.to_numeric(
        working[
            "return_percent"
        ],
        errors="coerce",
    )

    summary = (
        working
        .groupby(
            "entry_quality_final",
            dropna=False,
        )
        .agg(
            n=(
                "return_percent",
                "count",
            ),
            mean_5d=(
                "return_percent",
                "mean",
            ),
            positive_rate=(
                "return_percent",
                lambda x:
                (x > 0).mean() * 100,
            ),
        )
        .sort_values(
            "n",
            ascending=False,
        )
    )

    print(
        summary.to_string()
    )


# ============================================================
# SELECTION DIAGNOSTIC
# ============================================================

def print_selection_diagnostic(
    buy_new,
    non_buy_new,
):
    """
    Compare realised BUY NEW performance against the non-BUY-NEW
    population.
    """

    print()
    print("=" * 78)
    print(
        "COMPANY-PROFILE DIAGNOSTIC"
    )
    print("=" * 78)

    buy_returns = pd.to_numeric(
        buy_new[
            "return_percent"
        ],
        errors="coerce",
    ).dropna()

    non_returns = pd.to_numeric(
        non_buy_new[
            "return_percent"
        ],
        errors="coerce",
    ).dropna()

    if (
        buy_returns.empty
        or non_returns.empty
    ):

        print(
            "Insufficient realised returns."
        )

        return

    buy_mean = buy_returns.mean()
    non_mean = non_returns.mean()

    buy_positive = (
        buy_returns > 0
    ).mean() * 100

    non_positive = (
        non_returns > 0
    ).mean() * 100

    mean_delta = (
        buy_mean
        - non_mean
    )

    positive_delta = (
        buy_positive
        - non_positive
    )

    print(
        f"BUY NEW mean: "
        f"{buy_mean:.3f}%"
    )

    print(
        f"NON-BUY NEW mean: "
        f"{non_mean:.3f}%"
    )

    print(
        f"Mean delta: "
        f"{mean_delta:+.3f}pp"
    )

    print(
        f"BUY NEW positive rate: "
        f"{buy_positive:.3f}%"
    )

    print(
        f"NON-BUY NEW positive rate: "
        f"{non_positive:.3f}%"
    )

    print(
        f"Positive-rate delta: "
        f"{positive_delta:+.3f}pp"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 78)
    print(
        "BUY NEW COMPANY PROFILE CONTROL TEST"
    )
    print("=" * 78)

    print(
        "READ-ONLY — NO PRODUCTION CHANGES"
    )

    print(
        f"Database: {DB_PATH}"
    )

    print()

    # --------------------------------------------------------
    # LOAD
    # --------------------------------------------------------

    conn = sqlite3.connect(
        DB_PATH
    )

    try:

        recommendations = (
            load_recommendations(
                conn
            )
        )

        evidence = (
            load_evidence(
                conn
            )
        )

        evaluations = (
            load_evaluations(
                conn
            )
        )

        audit_decisions = (
            load_audit_decisions(
                conn
            )
        )

    finally:

        conn.close()

    print(
        f"Recommendations: "
        f"{len(recommendations)}"
    )

    print(
        f"Evidence rows: "
        f"{len(evidence)}"
    )

    print(
        f"Mature 5D outcomes: "
        f"{len(evaluations)}"
    )

    # --------------------------------------------------------
    # LINEAGE
    # --------------------------------------------------------

    lineage, unresolved = (
        build_buy_new_lineage(
            audit_decisions,
            recommendations,
        )
    )

    print_lineage_summary(
        lineage,
        unresolved,
    )

    # --------------------------------------------------------
    # MATURE POPULATION
    # --------------------------------------------------------

    population = build_population(
        lineage,
        recommendations,
        evidence,
        evaluations,
    )

    buy_new = population[
        population[
            "is_buy_new"
        ]
    ].copy()

    non_buy_new = population[
        ~population[
            "is_buy_new"
        ]
    ].copy()

    print(
        f"Mature BUY NEW observations: "
        f"{len(buy_new)}"
    )

    print(
        f"Mature non-BUY-NEW observations: "
        f"{len(non_buy_new)}"
    )

    # --------------------------------------------------------
    # ANALYSIS
    # --------------------------------------------------------

    print_group_summary(
        "BUY NEW",
        buy_new,
    )

    print_group_summary(
        "NON-BUY-NEW",
        non_buy_new,
    )

    print_feature_profile(
        buy_new,
        non_buy_new,
    )

    print_winners_vs_losers(
        buy_new,
    )

    print_correlations(
        buy_new,
    )

    print_ticker_concentration(
        buy_new,
    )

    print_signal_mix(
        buy_new,
    )

    print_entry_quality(
        buy_new,
    )

    print_selection_diagnostic(
        buy_new,
        non_buy_new,
    )

    # --------------------------------------------------------
    # COMPLETE
    # --------------------------------------------------------

    print()
    print("=" * 78)
    print(
        "CONTROL TEST COMPLETE"
    )
    print("=" * 78)

    print(
        "NO PRODUCTION CHANGES WERE MADE."
    )


if __name__ == "__main__":
    main()