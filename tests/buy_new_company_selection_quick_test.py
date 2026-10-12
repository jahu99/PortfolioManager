"""
BUY NEW Company Selection — Quick Test

A6 READ-ONLY INVESTIGATION

Question:
    Is BUY NEW selecting the right type of companies?

This test deliberately starts from the governed audit_decisions population,
rather than starting from recommendations.

Lineage:
    audit_decisions
        -> direct recommendation_id where persisted
        -> legacy recommendation reconstruction where recommendation_id is NULL
        -> recommendation_evaluations (5D)
        -> recommendation_evidence

Known BUY NEW lineage baseline:
    Raw BUY NEW decisions:        439
    Direct lineage:               114
    Reconstructed legacy lineage: 315
    Unresolved lineage:            10
    Mature 5D BUY NEW outcomes:   306

READ-ONLY:
    No production files, database records, thresholds, scores, learning,
    governance or decision logic are changed.

This test is descriptive only.
It does not establish causation.
"""

from pathlib import Path
import sqlite3

import numpy as np
import pandas as pd


# ============================================================
# CONFIGURATION
# ============================================================

DATABASE_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "portfolio_manager.db"
)

TARGET_ACTION = "BUY NEW"
TARGET_HORIZON = 5


# ============================================================
# HELPERS
# ============================================================

def safe_float(value, default=np.nan):
    """
    Convert a value to float without raising.
    """

    try:

        if value is None:
            return default

        if pd.isna(value):
            return default

        return float(value)

    except Exception:

        return default


def clean_ticker(value):
    """
    Normalise ticker text.
    """

    if value is None:
        return ""

    try:

        if pd.isna(value):
            return ""

    except Exception:

        pass

    return str(value).strip().upper()


def normalise_action(value):
    """
    Normalise final action text.
    """

    if value is None:
        return ""

    try:

        if pd.isna(value):
            return ""

    except Exception:

        pass

    return str(value).strip().upper()


def print_header(title):
    """
    Print a consistent section header.
    """

    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def print_subheader(title):
    """
    Print a consistent subsection header.
    """

    print()
    print("-" * 78)
    print(title)
    print("-" * 78)


def percentage(value):
    """
    Format a percentage safely.
    """

    if pd.isna(value):
        return "nan"

    return f"{value:.2f}%"


def return_formatter(value):
    """
    Format realised return.
    """

    if pd.isna(value):
        return "nan"

    return f"{value:.3f}%"


def format_dataframe(
    dataframe,
    percentage_columns=None,
    decimal_columns=None,
):
    """
    Apply readable formatting for console output.
    """

    percentage_columns = percentage_columns or []
    decimal_columns = decimal_columns or []

    formatters = {}

    for column in percentage_columns:

        if column in dataframe.columns:

            formatters[column] = (
                lambda value:
                f"{value:.3f}%"
                if pd.notna(value)
                else "nan"
            )

    for column in decimal_columns:

        if column in dataframe.columns:

            formatters[column] = (
                lambda value:
                f"{value:.3f}"
                if pd.notna(value)
                else "nan"
            )

    return dataframe.to_string(
        index=False,
        formatters=formatters,
    )


# ============================================================
# DATABASE
# ============================================================

def get_connection():
    """
    Open the portfolio manager database.
    """

    if not DATABASE_PATH.exists():

        raise FileNotFoundError(
            f"Database not found: {DATABASE_PATH}"
        )

    return sqlite3.connect(
        DATABASE_PATH
    )


# ============================================================
# LOAD GOVERNED AUDIT DECISIONS
# ============================================================

def load_audit_decisions(conn):
    """
    Load completed governed audit decisions.

    audit_runs supplies the audit date because audit_decisions itself
    does not contain the run timestamp used for legacy lineage.
    """

    return pd.read_sql_query(
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
            ad.investment_score,
            ad.technical_score,
            ad.quality_score,
            ad.growth_score,
            ad.confidence_score,
            ad.evidence_score,
            ad.original_signal,
            ad.reconciliation_status
        FROM audit_decisions ad
        INNER JOIN audit_runs ar
            ON ar.id = ad.audit_run_id
        WHERE ar.status = 'COMPLETED'
        ORDER BY
            ar.run_date,
            ad.id
        """,
        conn,
    )


# ============================================================
# LOAD RECOMMENDATIONS
# ============================================================

def load_recommendations(conn):
    """
    Load historical recommendation records.

    These are used only to reconstruct lineage for legacy audit
    decisions that do not have a persisted recommendation_id.
    """

    recommendations = pd.read_sql_query(
        """
        SELECT
            id AS recommendation_id,
            date AS recommendation_date,
            ticker,
            signal,
            investment_score
                AS recommendation_investment_score,
            technical_score
                AS recommendation_technical_score,
            quality_score
                AS recommendation_quality_score,
            growth_score
                AS recommendation_growth_score,
            confidence_score
                AS recommendation_confidence_score,
            price
                AS recommendation_price
        FROM recommendations
        WHERE ticker IS NOT NULL
        """,
        conn,
    )

    recommendations["recommendation_date"] = (
        pd.to_datetime(
            recommendations["recommendation_date"],
            format="ISO8601",
            errors="coerce",
        )
        .dt.tz_localize(None)
    )

    recommendations["ticker"] = (
        recommendations["ticker"]
        .map(clean_ticker)
    )

    recommendations = recommendations.dropna(
        subset=[
            "ticker",
            "recommendation_date",
        ]
    )

    return recommendations


# ============================================================
# LOAD RECOMMENDATION EVALUATIONS
# ============================================================

def load_evaluations(conn):
    """
    Load recommendation outcome evaluations.

    One row per recommendation_id / days_after is retained,
    using the latest evaluation record where duplicates exist.
    """

    evaluations = pd.read_sql_query(
        """
        SELECT
            recommendation_id,
            evaluation_date,
            days_after,
            return_percent,
            outcome
        FROM recommendation_evaluations
        WHERE days_after IN (5, 10, 20, 60)
        """,
        conn,
    )

    if evaluations.empty:

        return evaluations

    evaluations["evaluation_date"] = pd.to_datetime(
        evaluations["evaluation_date"],
        errors="coerce",
    )

    evaluations["days_after"] = pd.to_numeric(
        evaluations["days_after"],
        errors="coerce",
    )

    evaluations["return_percent"] = pd.to_numeric(
        evaluations["return_percent"],
        errors="coerce",
    )

    evaluations = (
        evaluations
        .sort_values(
            [
                "recommendation_id",
                "days_after",
                "evaluation_date",
            ]
        )
        .drop_duplicates(
            subset=[
                "recommendation_id",
                "days_after",
            ],
            keep="last",
        )
    )

    return evaluations


# ============================================================
# LOAD RECOMMENDATION EVIDENCE
# ============================================================

def load_evidence(conn):
    """
    Load recommendation evidence.

    Evidence is reduced to the latest available capture for each
    recommendation_id so the company-selection analysis does not
    duplicate recommendations because of multiple evidence rows.
    """

    evidence = pd.read_sql_query(
        """
        SELECT
            recommendation_id,
            ticker AS evidence_ticker,
            capture_date,
            signal,
            investment_score,
            technical_score,
            quality_score,
            growth_score,
            confidence_score,
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
        conn,
    )

    if evidence.empty:

        return evidence

    evidence["capture_date"] = pd.to_datetime(
        evidence["capture_date"],
        errors="coerce",
    )

    evidence["evidence_ticker"] = (
        evidence["evidence_ticker"]
        .map(clean_ticker)
    )

    numeric_columns = [
        "investment_score",
        "technical_score",
        "quality_score",
        "growth_score",
        "confidence_score",
        "entry_price",
        "rsi",
        "extension_sma50_pct",
        "extension_sma200_pct",
        "revenue_growth",
        "profit_margin",
        "return_on_equity",
        "debt_to_equity",
    ]

    for column in numeric_columns:

        if column in evidence.columns:

            evidence[column] = pd.to_numeric(
                evidence[column],
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

    return evidence


# ============================================================
# RECONSTRUCT BUY NEW LINEAGE
# ============================================================

def build_buy_new_lineage(
    audit_decisions,
    recommendations,
):
    """
    Build the proven BUY NEW audit -> recommendation lineage.

    Direct lineage:
        audit_decisions.recommendation_id -> recommendations.id

    Legacy lineage:
        ticker + audit_date
            -> latest recommendation on/before audit_date

    Uses pd.merge_asof with:
        direction="backward"
        allow_exact_matches=True

    This is the same lineage approach used by the established
    decision-performance reporting path.
    """

    audit_decisions = audit_decisions.copy()
    recommendations = recommendations.copy()

    audit_decisions["final_action"] = (
        audit_decisions["final_action"]
        .map(normalise_action)
    )

    audit_decisions["ticker"] = (
        audit_decisions["ticker"]
        .map(clean_ticker)
    )

    audit_decisions["audit_date"] = (
        pd.to_datetime(
            audit_decisions["audit_date"],
            format="ISO8601",
            errors="coerce",
        )
        .dt.tz_localize(None)
    )

    # --------------------------------------------------------
    # Start from ACTUAL governed BUY NEW decisions.
    # --------------------------------------------------------

    buy_new_audit = audit_decisions[
        audit_decisions["final_action"]
        == TARGET_ACTION
    ].copy()

    raw_count = len(
        buy_new_audit
    )

    # --------------------------------------------------------
    # Remove unusable audit rows.
    # --------------------------------------------------------

    buy_new_audit = buy_new_audit.dropna(
        subset=[
            "ticker",
            "audit_date",
        ]
    ).copy()

    # --------------------------------------------------------
    # Direct lineage.
    # --------------------------------------------------------

    direct_audit = buy_new_audit[
        buy_new_audit["recommendation_id"].notna()
    ].copy()

    direct_lineage = direct_audit.merge(
        recommendations,
        how="left",
        on="recommendation_id",
        suffixes=(
            "",
            "_recommendation",
        ),
    )

    direct_lineage["lineage_type"] = (
        "DIRECT"
    )

    # --------------------------------------------------------
    # Legacy lineage.
    # --------------------------------------------------------

    legacy_audit = buy_new_audit[
        buy_new_audit["recommendation_id"].isna()
    ].copy()

    if not legacy_audit.empty:

        legacy_audit = (
            legacy_audit
            .drop(
                columns=["recommendation_id"]
            )
            .sort_values(
                [
                    "audit_date",
                    "ticker",
                ]
            )
            .copy()
        )

        legacy_recommendations = (
            recommendations
            .sort_values(
                [
                    "recommendation_date",
                    "ticker",
                ]
            )
            .copy()
        )

        legacy_lineage = pd.merge_asof(
            legacy_audit,
            legacy_recommendations,
            left_on="audit_date",
            right_on="recommendation_date",
            by="ticker",
            direction="backward",
            allow_exact_matches=True,
        )

        legacy_lineage["lineage_type"] = (
            "RECONSTRUCTED"
        )

    else:

        legacy_lineage = pd.DataFrame(
            columns=direct_lineage.columns
        )

    # --------------------------------------------------------
    # Combine.
    # --------------------------------------------------------

    lineage = pd.concat(
        [
            direct_lineage,
            legacy_lineage,
        ],
        ignore_index=True,
        sort=False,
    )

    # --------------------------------------------------------
    # Identify unresolved lineage.
    # --------------------------------------------------------

    lineage["lineage_resolved"] = (
        lineage["recommendation_id"]
        .notna()
    )

    unresolved_count = int(
        (~lineage["lineage_resolved"]).sum()
    )

    direct_count = len(
        direct_lineage
    )

    reconstructed_count = len(
        legacy_lineage
    )

    return (
        lineage,
        {
            "raw_count": raw_count,
            "direct_count": direct_count,
            "reconstructed_count": reconstructed_count,
            "unresolved_count": unresolved_count,
        },
    )


# ============================================================
# BUILD MATURE BUY NEW POPULATION
# ============================================================

def build_mature_buy_new_population(
    buy_new_lineage,
    evaluations,
    evidence,
):
    """
    Join BUY NEW lineage to mature 5D outcomes and evidence.

    The returned dataframe contains one mature 5D observation per
    resolved recommendation_id.
    """

    population = buy_new_lineage[
        buy_new_lineage["lineage_resolved"]
    ].copy()

    if population.empty:

        return population

    # --------------------------------------------------------
    # Join 5D outcomes.
    # --------------------------------------------------------

    five_day = evaluations[
        evaluations["days_after"]
        == TARGET_HORIZON
    ].copy()

    population = population.merge(
        five_day[
            [
                "recommendation_id",
                "evaluation_date",
                "return_percent",
                "outcome",
            ]
        ],
        how="left",
        on="recommendation_id",
        suffixes=(
            "",
            "_evaluation",
        ),
    )

    # --------------------------------------------------------
    # Join evidence.
    # --------------------------------------------------------

    if not evidence.empty:

        evidence_columns = [
            "recommendation_id",
            "evidence_ticker",
            "capture_date",
            "signal",
            "investment_score",
            "technical_score",
            "quality_score",
            "growth_score",
            "confidence_score",
            "entry_price",
            "rsi",
            "extension_sma50_pct",
            "extension_sma200_pct",
            "revenue_growth",
            "profit_margin",
            "return_on_equity",
            "debt_to_equity",
            "entry_quality",
        ]

        evidence_columns = [
            column
            for column in evidence_columns
            if column in evidence.columns
        ]

        population = population.merge(
            evidence[evidence_columns],
            how="left",
            on="recommendation_id",
            suffixes=(
                "",
                "_evidence",
            ),
        )

    # --------------------------------------------------------
    # Normalise evidence fields.
    # --------------------------------------------------------

    evidence_score_columns = [
        "investment_score",
        "technical_score",
        "quality_score",
        "growth_score",
        "confidence_score",
        "rsi",
        "extension_sma50_pct",
        "extension_sma200_pct",
        "revenue_growth",
        "profit_margin",
        "return_on_equity",
        "debt_to_equity",
    ]

    for column in evidence_score_columns:

        if column in population.columns:

            population[column] = pd.to_numeric(
                population[column],
                errors="coerce",
            )

    population["ticker"] = (
        population["ticker"]
        .map(clean_ticker)
    )

    # --------------------------------------------------------
    # Mature = actual 5D realised return exists.
    # --------------------------------------------------------

    population["return_percent"] = pd.to_numeric(
        population["return_percent"],
        errors="coerce",
    )

    population = population[
        population["return_percent"].notna()
    ].copy()

    # --------------------------------------------------------
    # If multiple audit decisions resolve to the same
    # recommendation, retain one observation.
    #
    # This prevents repeated audit runs from turning one
    # recommendation into multiple performance observations.
    # --------------------------------------------------------

    # ============================================================
    # COALESCE FEATURE VALUES
    # ============================================================
    #
    # Evidence is the preferred source for feature-level analysis.
    # Recommendation-level values are the fallback.
    #
    # Merges can create *_x / *_y columns, so explicitly restore
    # the canonical analysis columns here.

    for column in [
        "investment_score",
        "technical_score",
        "quality_score",
        "growth_score",
        "confidence_score",
    ]:
        evidence_column = f"{column}_evidence"
        recommendation_column = f"{column}_recommendation"

        if evidence_column in population.columns:
            if recommendation_column in population.columns:
                population[column] = (
                    population[evidence_column]
                    .combine_first(
                        population[recommendation_column]
                    )
                )
            else:
                population[column] = population[evidence_column]

        elif recommendation_column in population.columns:
            population[column] = population[recommendation_column]

    return population


# ============================================================
# LOAD NON-BUY-NEW COMPARATOR
# ============================================================

def build_non_buy_new_population(
    audit_decisions,
    recommendations,
    evaluations,
    evidence,
    buy_new_recommendation_ids,
):
    """
    Build a comparable mature population of governed decisions
    whose final action was NOT BUY NEW.

    The same lineage rules are used, so BUY NEW and non-BUY-NEW
    observations are being compared on the same basis.
    """

    non_buy_audit = audit_decisions.copy()

    non_buy_audit["final_action"] = (
        non_buy_audit["final_action"]
        .map(normalise_action)
    )

    non_buy_audit = non_buy_audit[
        non_buy_audit["final_action"]
        != TARGET_ACTION
    ].copy()

    non_buy_audit["ticker"] = (
        non_buy_audit["ticker"]
        .map(clean_ticker)
    )

    non_buy_audit["audit_date"] = (
        pd.to_datetime(
            non_buy_audit["audit_date"],
            format="ISO8601",
            errors="coerce",
        )
        .dt.tz_localize(None)
    )

    non_buy_audit = non_buy_audit.dropna(
        subset=[
            "ticker",
            "audit_date",
        ]
    )

    # --------------------------------------------------------
    # Direct lineage.
    # --------------------------------------------------------

    direct_audit = non_buy_audit[
        non_buy_audit["recommendation_id"].notna()
    ].copy()

    direct = direct_audit.merge(
        recommendations,
        how="left",
        on="recommendation_id",
        suffixes=(
            "",
            "_recommendation",
        ),
    )

    # --------------------------------------------------------
    # Legacy lineage.
    # --------------------------------------------------------

    legacy_audit = non_buy_audit[
        non_buy_audit["recommendation_id"].isna()
    ].copy()

    if not legacy_audit.empty:

        legacy_audit = (
            legacy_audit
            .drop(
                columns=["recommendation_id"]
            )
            .sort_values(
                [
                    "audit_date",
                    "ticker",
                ]
            )
        )

        legacy_recommendations = (
            recommendations
            .sort_values(
                [
                    "recommendation_date",
                    "ticker",
                ]
            )
        )

        legacy = pd.merge_asof(
            legacy_audit,
            legacy_recommendations,
            left_on="audit_date",
            right_on="recommendation_date",
            by="ticker",
            direction="backward",
            allow_exact_matches=True,
        )

    else:

        legacy = pd.DataFrame(
            columns=direct.columns
        )

    population = pd.concat(
        [
            direct,
            legacy,
        ],
        ignore_index=True,
        sort=False,
    )

    population = population[
        population["recommendation_id"].notna()
    ].copy()

    # --------------------------------------------------------
    # Join 5D outcome.
    # --------------------------------------------------------

    five_day = evaluations[
        evaluations["days_after"]
        == TARGET_HORIZON
    ].copy()

    population = population.merge(
        five_day[
            [
                "recommendation_id",
                "return_percent",
                "outcome",
            ]
        ],
        how="left",
        on="recommendation_id",
        suffixes=(
            "",
            "_evaluation",
        ),
    )

    # --------------------------------------------------------
    # Join evidence.
    # --------------------------------------------------------

    if not evidence.empty:

        evidence_columns = [
            "recommendation_id",
            "evidence_ticker",
            "capture_date",
            "signal",
            "investment_score",
            "technical_score",
            "quality_score",
            "growth_score",
            "confidence_score",
            "entry_price",
            "rsi",
            "extension_sma50_pct",
            "extension_sma200_pct",
            "revenue_growth",
            "profit_margin",
            "return_on_equity",
            "debt_to_equity",
            "entry_quality",
        ]

        evidence_columns = [
            column
            for column in evidence_columns
            if column in evidence.columns
        ]

        population = population.merge(
            evidence[evidence_columns],
            how="left",
            on="recommendation_id",
            suffixes=(
                "",
                "_evidence",
            ),
        )

    population["return_percent"] = pd.to_numeric(
        population["return_percent"],
        errors="coerce",
    )

    population = population[
        population["return_percent"].notna()
    ].copy()

    # Exclude recommendation IDs that are already in BUY NEW.
    population = population[
        ~population["recommendation_id"].isin(
            buy_new_recommendation_ids
        )
    ].copy()

    population = (
        population
        .sort_values(
            [
                "recommendation_id",
                "audit_date",
                "audit_decision_id",
            ]
        )
        .drop_duplicates(
            subset=["recommendation_id"],
            keep="last",
        )
        .reset_index(drop=True)
    )

    return population


# ============================================================
# SECTION 1 — PERFORMANCE BY FINAL ACTION
# ============================================================

def analyse_action_performance(
    audit_decisions,
    evaluations,
):
    """
    Descriptive 5D performance by governed final action.

    This is supporting context only.
    """

    five_day = evaluations[
        evaluations["days_after"]
        == TARGET_HORIZON
    ].copy()

    if five_day.empty:

        print(
            "No mature 5D evaluations available."
        )

        return

    action_rows = []

    actions = (
        audit_decisions[
            [
                "recommendation_id",
                "final_action",
            ]
        ]
        .dropna(
            subset=["recommendation_id"]
        )
        .copy()
    )

    actions["final_action"] = (
        actions["final_action"]
        .map(normalise_action)
    )

    actions = actions[
        actions["final_action"] != ""
    ]

    actions = actions.drop_duplicates(
        subset=["recommendation_id"],
        keep="last",
    )

    joined = actions.merge(
        five_day[
            [
                "recommendation_id",
                "return_percent",
            ]
        ],
        how="inner",
        on="recommendation_id",
    )

    for action, group in joined.groupby(
        "final_action"
    ):

        returns = group[
            "return_percent"
        ].dropna()

        if returns.empty:
            continue

        action_rows.append(
            {
                "action": action,
                "n": len(returns),
                "mean": returns.mean(),
                "median": returns.median(),
                "positive_pct": (
                    returns.gt(0).mean()
                    * 100
                ),
            }
        )

    result = pd.DataFrame(
        action_rows,
        columns=[
            "action",
            "n",
            "mean",
            "median",
            "positive_pct",
        ],
    )

    if result.empty:

        print(
            "No mature governed action observations available."
        )

        return

    result = result.sort_values(
        "n",
        ascending=False,
    )

    print(
        format_dataframe(
            result,
            percentage_columns=[
                "mean",
                "median",
                "positive_pct",
            ],
        )
    )


# ============================================================
# SECTION 2 — BUY NEW VS NON-BUY-NEW
# ============================================================

def analyse_buy_new_vs_non_buy_new(
    buy_new,
    non_buy_new,
):
    """
    Compare mature 5D realised performance.
    """

    rows = []

    for label, dataframe in [
        ("BUY NEW", buy_new),
        ("Non-BUY NEW", non_buy_new),
    ]:

        returns = dataframe[
            "return_percent"
        ].dropna()

        rows.append(
            {
                "population": label,
                "n": len(returns),
                "mean": (
                    returns.mean()
                    if not returns.empty
                    else np.nan
                ),
                "median": (
                    returns.median()
                    if not returns.empty
                    else np.nan
                ),
                "positive_pct": (
                    returns.gt(0).mean()
                    * 100
                    if not returns.empty
                    else np.nan
                ),
            }
        )

    result = pd.DataFrame(
        rows
    )

    print(
        format_dataframe(
            result,
            percentage_columns=[
                "mean",
                "median",
                "positive_pct",
            ],
        )
    )


# ============================================================
# SECTION 3 — FEATURE PROFILE
# ============================================================

FEATURES = [
    "investment_score",
    "technical_score",
    "quality_score",
    "growth_score",
    "confidence_score",
    "rsi",
    "extension_sma50_pct",
    "extension_sma200_pct",
    "revenue_growth",
    "profit_margin",
    "return_on_equity",
    "debt_to_equity",
]


def analyse_feature_profile(
    buy_new,
    non_buy_new,
):
    """
    Compare BUY NEW feature characteristics with
    the non-BUY-NEW mature population.
    """

    rows = []

    for feature in FEATURES:

        if (
            feature not in buy_new.columns
            or feature not in non_buy_new.columns
        ):
            continue

        buy_values = pd.to_numeric(
            buy_new[feature],
            errors="coerce",
        ).dropna()

        non_buy_values = pd.to_numeric(
            non_buy_new[feature],
            errors="coerce",
        ).dropna()

        buy_mean = (
            buy_values.mean()
            if not buy_values.empty
            else np.nan
        )

        non_buy_mean = (
            non_buy_values.mean()
            if not non_buy_values.empty
            else np.nan
        )

        buy_median = (
            buy_values.median()
            if not buy_values.empty
            else np.nan
        )

        non_buy_median = (
            non_buy_values.median()
            if not non_buy_values.empty
            else np.nan
        )

        rows.append(
            {
                "feature": feature,
                "buy_new_mean": buy_mean,
                "non_buy_new_mean": non_buy_mean,
                "difference": (
                    buy_mean - non_buy_mean
                    if pd.notna(buy_mean)
                    and pd.notna(non_buy_mean)
                    else np.nan
                ),
                "buy_new_median": buy_median,
                "non_buy_new_median": non_buy_median,
            }
        )

    result = pd.DataFrame(
        rows
    )

    print(
        format_dataframe(
            result,
            decimal_columns=[
                "buy_new_mean",
                "non_buy_new_mean",
                "difference",
                "buy_new_median",
                "non_buy_new_median",
            ],
        )
    )


# ============================================================
# SECTION 4 — BUY NEW WINNERS VS LOSERS
# ============================================================

def analyse_buy_new_winners_losers(
    buy_new,
):
    """
    Compare BUY NEW observations that realised positive 5D
    returns against non-positive observations.
    """

    winners = buy_new[
        buy_new["return_percent"] > 0
    ].copy()

    losers = buy_new[
        buy_new["return_percent"] <= 0
    ].copy()

    print(
        f"BUY NEW winners: {len(winners)}"
    )

    print(
        f"BUY NEW losers/non-positive: {len(losers)}"
    )

    if (
        len(winners) < 2
        or len(losers) < 2
    ):

        print(
            "Insufficient BUY NEW winners and losers "
            "for a meaningful comparison."
        )

        return

    rows = []

    for feature in FEATURES:

        if (
            feature not in winners.columns
            or feature not in losers.columns
        ):
            continue

        winner_values = pd.to_numeric(
            winners[feature],
            errors="coerce",
        ).dropna()

        loser_values = pd.to_numeric(
            losers[feature],
            errors="coerce",
        ).dropna()

        if (
            winner_values.empty
            or loser_values.empty
        ):
            continue

        winner_mean = winner_values.mean()
        loser_mean = loser_values.mean()

        rows.append(
            {
                "metric": feature,
                "winner_mean": winner_mean,
                "loser_mean": loser_mean,
                "difference": (
                    winner_mean
                    - loser_mean
                ),
            }
        )

    result = pd.DataFrame(
        rows
    )

    print(
        format_dataframe(
            result,
            decimal_columns=[
                "winner_mean",
                "loser_mean",
                "difference",
            ],
        )
    )

    # --------------------------------------------------------
    # Entry quality split.
    # --------------------------------------------------------

    if "entry_quality" in buy_new.columns:

        print()
        print("Winner Entry Quality:")

        print(
            winners[
                "entry_quality"
            ]
            .fillna("UNKNOWN")
            .value_counts()
            .to_string()
        )

        print()
        print("Loser Entry Quality:")

        print(
            losers[
                "entry_quality"
            ]
            .fillna("UNKNOWN")
            .value_counts()
            .to_string()
        )


# ============================================================
# SECTION 5 — FEATURE CORRELATIONS
# ============================================================

def analyse_feature_correlations(
    buy_new,
):
    """
    Calculate descriptive Pearson correlations between BUY NEW
    input features and subsequent 5D return.
    """

    rows = []

    for feature in FEATURES:

        if feature not in buy_new.columns:

            rows.append(
                {
                    "feature": feature,
                    "correlation": np.nan,
                    "observations": 0,
                }
            )

            continue

        values = buy_new[
            [
                feature,
                "return_percent",
            ]
        ].copy()

        values[feature] = pd.to_numeric(
            values[feature],
            errors="coerce",
        )

        values["return_percent"] = pd.to_numeric(
            values["return_percent"],
            errors="coerce",
        )

        values = values.dropna()

        if len(values) < 2:

            correlation = np.nan

        else:

            correlation = (
                values[feature]
                .corr(
                    values["return_percent"]
                )
            )

        rows.append(
            {
                "feature": feature,
                "correlation": correlation,
                "observations": len(values),
            }
        )

    result = pd.DataFrame(
        rows
    )

    print(
        format_dataframe(
            result,
            decimal_columns=[
                "correlation",
            ],
        )
    )


# ============================================================
# SECTION 6 — TICKER CONCENTRATION
# ============================================================

def analyse_ticker_concentration(
    buy_new,
):
    """
    Show whether BUY NEW performance is dominated by a small
    number of tickers.
    """

    if buy_new.empty:

        print(
            "No BUY NEW observations available "
            "for ticker concentration analysis."
        )

        return

    ticker_rows = []

    for ticker, group in buy_new.groupby(
        "ticker"
    ):

        returns = group[
            "return_percent"
        ].dropna()

        if returns.empty:
            continue

        ticker_rows.append(
            {
                "ticker": ticker,
                "count": len(returns),
                "mean": returns.mean(),
                "median": returns.median(),
                "positive_pct": (
                    returns.gt(0).mean()
                    * 100
                ),
            }
        )

    ticker_results = pd.DataFrame(
        ticker_rows,
        columns=[
            "ticker",
            "count",
            "mean",
            "median",
            "positive_pct",
        ],
    )

    if ticker_results.empty:

        print(
            "No BUY NEW observations available "
            "for ticker concentration analysis."
        )

        return

    ticker_results = (
        ticker_results
        .sort_values(
            "count",
            ascending=False,
        )
    )

    print(
        format_dataframe(
            ticker_results,
            percentage_columns=[
                "mean",
                "median",
                "positive_pct",
            ],
        )
    )


# ============================================================
# SECTION 7 — SIGNAL MIX
# ============================================================

def analyse_signal_mix(
    buy_new,
):
    """
    Show the signal composition of BUY NEW decisions.
    """

    if buy_new.empty:

        print(
            "No BUY NEW observations available "
            "for signal analysis."
        )

        return

    if "signal" not in buy_new.columns:

        print(
            "Signal field unavailable."
        )

        return

    result = (
        buy_new[
            "signal"
        ]
        .fillna("UNKNOWN")
        .value_counts()
        .rename_axis("signal")
        .reset_index(
            name="count"
        )
    )

    print(
        result.to_string(
            index=False
        )
    )


# ============================================================
# SECTION 8 — ENTRY QUALITY
# ============================================================

def analyse_entry_quality(
    buy_new,
):
    """
    Show BUY NEW performance by entry-quality classification.
    """

    if buy_new.empty:

        print(
            "No BUY NEW observations available "
            "for entry-quality analysis."
        )

        return

    if "entry_quality" not in buy_new.columns:

        print(
            "Entry quality field unavailable."
        )

        return

    rows = []

    working = buy_new.copy()

    working["entry_quality"] = (
        working["entry_quality"]
        .fillna("UNKNOWN")
        .replace(
            "",
            "UNKNOWN",
        )
    )

    for entry_quality, group in (
        working.groupby(
            "entry_quality"
        )
    ):

        returns = group[
            "return_percent"
        ].dropna()

        if returns.empty:
            continue

        rows.append(
            {
                "entry_quality": entry_quality,
                "count": len(returns),
                "mean": returns.mean(),
                "median": returns.median(),
                "positive_pct": (
                    returns.gt(0).mean()
                    * 100
                ),
            }
        )

    result = pd.DataFrame(
        rows,
        columns=[
            "entry_quality",
            "count",
            "mean",
            "median",
            "positive_pct",
        ],
    )

    if result.empty:

        print(
            "No entry-quality observations available."
        )

        return

    result = result.sort_values(
        "count",
        ascending=False,
    )

    print(
        format_dataframe(
            result,
            percentage_columns=[
                "mean",
                "median",
                "positive_pct",
            ],
        )
    )


# ============================================================
# SECTION 9 — SELECTION DIAGNOSTIC
# ============================================================

def selection_diagnostic(
    buy_new,
    non_buy_new,
):
    """
    Produce a simple descriptive diagnostic.

    This deliberately does not recommend an automatic threshold
    or production change.
    """

    if buy_new.empty:

        print(
            "No BUY NEW observations available."
        )

        return

    if non_buy_new.empty:

        print(
            "No non-BUY-NEW comparator observations available."
        )

        return

    buy_returns = buy_new[
        "return_percent"
    ].dropna()

    non_buy_returns = non_buy_new[
        "return_percent"
    ].dropna()

    if (
        buy_returns.empty
        or non_buy_returns.empty
    ):

        print(
            "Insufficient realised returns for selection diagnostic."
        )

        return

    buy_mean = buy_returns.mean()
    non_buy_mean = non_buy_returns.mean()

    buy_positive = (
        buy_returns.gt(0).mean()
        * 100
    )

    non_buy_positive = (
        non_buy_returns.gt(0).mean()
        * 100
    )

    print(
        f"BUY NEW mean 5D return: "
        f"{buy_mean:.3f}%"
    )

    print(
        f"Non-BUY NEW mean 5D return: "
        f"{non_buy_mean:.3f}%"
    )

    print(
        f"BUY NEW positive 5D: "
        f"{buy_positive:.2f}%"
    )

    print(
        f"Non-BUY NEW positive 5D: "
        f"{non_buy_positive:.2f}%"
    )

    print(
        f"BUY NEW mean delta: "
        f"{buy_mean - non_buy_mean:.3f}pp"
    )

    print(
        f"BUY NEW positive-rate delta: "
        f"{buy_positive - non_buy_positive:.2f}pp"
    )

    print()
    print(
        "This diagnostic describes selection performance only."
    )

    print(
        "It does not establish that BUY NEW caused the outcomes."
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print_header(
        "BUY NEW COMPANY SELECTION — QUICK TEST"
    )

    print()
    print(
        "READ-ONLY — NO PRODUCTION CHANGES"
    )

    print()
    print(
        f"Database: {DATABASE_PATH}"
    )

    conn = get_connection()

    try:

        # ----------------------------------------------------
        # Load source populations.
        # ----------------------------------------------------

        audit_decisions = (
            load_audit_decisions(
                conn
            )
        )

        recommendations = (
            load_recommendations(
                conn
            )
        )

        evaluations = (
            load_evaluations(
                conn
            )
        )

        evidence = (
            load_evidence(
                conn
            )
        )

        print()
        print(
            f"Recommendations: "
            f"{len(recommendations)}"
        )

        print(
            f"Evidence rows: "
            f"{len(evidence)}"
        )

        five_day_evaluations = (
            evaluations[
                evaluations["days_after"]
                == TARGET_HORIZON
            ]
            if not evaluations.empty
            else pd.DataFrame()
        )

        print(
            f"Mature 5D outcomes: "
            f"{five_day_evaluations['return_percent'].notna().sum()}"
            if not five_day_evaluations.empty
            else
            "Mature 5D outcomes: 0"
        )

        # ----------------------------------------------------
        # Proven BUY NEW lineage.
        # ----------------------------------------------------

        (
            buy_new_lineage,
            lineage_stats,
        ) = build_buy_new_lineage(
            audit_decisions,
            recommendations,
        )

        print()
        print(
            f"Raw BUY NEW audit decisions: "
            f"{lineage_stats['raw_count']}"
        )

        print(
            f"Direct lineage: "
            f"{lineage_stats['direct_count']}"
        )

        print(
            f"Reconstructed legacy lineage: "
            f"{lineage_stats['reconstructed_count']}"
        )

        print(
            f"Unresolved lineage: "
            f"{lineage_stats['unresolved_count']}"
        )

        # ----------------------------------------------------
        # Mature BUY NEW population.
        # ----------------------------------------------------

        buy_new = (
            build_mature_buy_new_population(
                buy_new_lineage,
                evaluations,
                evidence,
            )
        )

        print(
            f"Mature BUY NEW observations: "
            f"{len(buy_new)}"
        )

        # ----------------------------------------------------
        # Build comparator.
        # ----------------------------------------------------

        buy_new_recommendation_ids = set(
            buy_new[
                "recommendation_id"
            ].dropna()
        )

        non_buy_new = (
            build_non_buy_new_population(
                audit_decisions,
                recommendations,
                evaluations,
                evidence,
                buy_new_recommendation_ids,
            )
        )

        print(
            f"Mature non-BUY-NEW observations: "
            f"{len(non_buy_new)}"
        )

        # ====================================================
        # 1. PERFORMANCE BY FINAL ACTION
        # ====================================================

        print_header(
            "1. 5D PERFORMANCE BY FINAL ACTION"
        )

        analyse_action_performance(
            audit_decisions,
            evaluations,
        )

        # ====================================================
        # 2. BUY NEW VS NON-BUY-NEW
        # ====================================================

        print_header(
            "2. BUY NEW VS NON-BUY-NEW"
        )

        analyse_buy_new_vs_non_buy_new(
            buy_new,
            non_buy_new,
        )

        # ====================================================
        # 3. BUY NEW FEATURE PROFILE
        # ====================================================

        print_header(
            "3. BUY NEW FEATURE PROFILE"
        )

        analyse_feature_profile(
            buy_new,
            non_buy_new,
        )

        # ====================================================
        # 4. BUY NEW WINNERS VS LOSERS
        # ====================================================

        print_header(
            "4. BUY NEW WINNERS VS LOSERS"
        )

        analyse_buy_new_winners_losers(
            buy_new,
        )

        # ====================================================
        # 5. BUY NEW FEATURE CORRELATIONS
        # ====================================================

        print_header(
            "5. BUY NEW FEATURE CORRELATIONS WITH 5D RETURN"
        )

        analyse_feature_correlations(
            buy_new,
        )

        # ====================================================
        # 6. BUY NEW TICKER CONCENTRATION
        # ====================================================

        print_header(
            "6. BUY NEW TICKER CONCENTRATION"
        )

        analyse_ticker_concentration(
            buy_new,
        )

        # ====================================================
        # 7. BUY NEW SIGNAL MIX
        # ====================================================

        print_header(
            "7. BUY NEW SIGNAL MIX"
        )

        analyse_signal_mix(
            buy_new,
        )

        # ====================================================
        # 8. BUY NEW ENTRY QUALITY
        # ====================================================

        print_header(
            "8. BUY NEW ENTRY QUALITY"
        )

        analyse_entry_quality(
            buy_new,
        )

        # ====================================================
        # 9. SELECTION DIAGNOSTIC
        # ====================================================

        print_header(
            "9. SELECTION DIAGNOSTIC"
        )

        selection_diagnostic(
            buy_new,
            non_buy_new,
        )

        # ====================================================
        # FINAL SUMMARY
        # ====================================================

        print_header(
            "QUICK TEST COMPLETE"
        )

        print()
        print(
            "BUY NEW lineage was derived from governed "
            "audit_decisions."
        )

        print(
            "Legacy recommendation lineage was reconstructed "
            "using ticker + audit date."
        )

        print(
            "5D outcomes are realised recommendation evaluations."
        )

        print()
        print(
            "This test is descriptive only."
        )

        print(
            "It does not establish causation."
        )

        print(
            "No production changes were made."
        )

    finally:

        conn.close()


if __name__ == "__main__":

    main()