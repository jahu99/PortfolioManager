"""
Calibration V2 - scoring architecture test.

Purpose
-------
Test a cleaner Technical / Quality / Growth architecture against the
point-in-time data captured by recommendation_evidence.

IMPORTANT
---------
Do NOT use current Yahoo Finance fundamentals to calculate historical
August scores. Doing so would introduce look-ahead bias.

Current Yahoo fundamentals are therefore used only for a separate
availability/inventory diagnostic.

This module is calibration-only and must never be imported by production.
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DB_PATH = PROJECT_ROOT / "data" / "portfolio_manager.db"

OUTPUT_DIR = PROJECT_ROOT / "calibration" / "output"

MIN_BUY_SCORE = 75


# ============================================================
# POINT-IN-TIME PRODUCTION INPUTS
# ============================================================

# These are the fields that were actually captured by the production
# system at the time of the August recommendation.
#
# Do NOT substitute current Yahoo values for these fields.

REQUIRED_FIELDS = [
    "recommendation_id",
    "ticker",
    "capture_date",
    "signal",
    "investment_score",
    "technical_score",
    "quality_score",
    "growth_score",
    "rsi",
    "sma50",
    "sma200",
    "return_3m",
    "trend_score",
    "momentum_score",
    "volume_score",
    "risk_score",
    "revenue_growth",
    "profit_margin",
    "return_on_equity",
    "debt_to_equity",
]


# ============================================================
# CANDIDATE YAHOO FIELDS
#
# These are NOT used in the historical V2 score because they were
# not captured point-in-time in August.
# ============================================================

YAHOO_FIELDS = {
    "revenueGrowth": "Growth",
    "earningsGrowth": "Growth",
    "earningsQuarterlyGrowth": "Growth",
    "revenueQuarterlyGrowth": "Growth",
    "grossMargins": "Quality",
    "operatingMargins": "Quality",
    "profitMargins": "Quality",
    "returnOnEquity": "Quality",
    "returnOnAssets": "Quality",
    "debtToEquity": "Quality",
    "currentRatio": "Quality",
    "quickRatio": "Quality",
    "freeCashflow": "Quality",
    "operatingCashflow": "Quality",
    "totalDebt": "Quality",
    "totalCash": "Quality",
    "trailingPE": "Valuation",
    "forwardPE": "Valuation",
    "pegRatio": "Valuation",
    "priceToSalesTrailing12Months": "Valuation",
    "enterpriseToEbitda": "Valuation",
}


# ============================================================
# LOAD POINT-IN-TIME EVIDENCE
# ============================================================

def load_evidence(
    start_date: str,
    end_date: str,
) -> pd.DataFrame:

    query = """
        SELECT
            recommendation_id,
            ticker,
            capture_date,
            signal,
            investment_score,
            technical_score,
            quality_score,
            growth_score,
            rsi,
            sma50,
            sma200,
            return_3m,
            trend_score,
            momentum_score,
            volume_score,
            risk_score,
            revenue_growth,
            profit_margin,
            return_on_equity,
            debt_to_equity
        FROM recommendation_evidence
        WHERE capture_date >= ?
          AND capture_date <= ?
        ORDER BY capture_date, ticker
    """

    with sqlite3.connect(DB_PATH) as connection:

        df = pd.read_sql_query(
            query,
            connection,
            params=(start_date, end_date),
        )

    if df.empty:
        raise RuntimeError(
            f"No recommendation evidence found between "
            f"{start_date} and {end_date}."
        )

    missing = [
        field
        for field in REQUIRED_FIELDS
        if field not in df.columns
    ]

    if missing:
        raise RuntimeError(
            "Missing required evidence fields: "
            + ", ".join(missing)
        )

    return df


# ============================================================
# NUMERIC CONVERSION
# ============================================================

def convert_numeric_fields(
    df: pd.DataFrame,
) -> pd.DataFrame:

    result = df.copy()

    non_numeric = {
        "recommendation_id",
        "ticker",
        "capture_date",
        "signal",
    }

    for column in result.columns:

        if column in non_numeric:
            continue

        result[column] = pd.to_numeric(
            result[column],
            errors="coerce",
        )

    return result


# ============================================================
# NORMALISATION HELPERS
# ============================================================

def clamp(
    value: float,
    minimum: float = 0.0,
    maximum: float = 100.0,
) -> float:

    if pd.isna(value):
        return np.nan

    return max(
        minimum,
        min(maximum, float(value)),
    )


def percentile_score(
    series: pd.Series,
) -> pd.Series:

    """
    Convert a numeric series into a 0-100 cross-sectional percentile.

    Higher raw values receive higher scores.

    Missing values remain missing.
    """

    numeric = pd.to_numeric(
        series,
        errors="coerce",
    )

    valid = numeric.notna()

    result = pd.Series(
        np.nan,
        index=series.index,
        dtype=float,
    )

    if valid.sum() == 1:

        result.loc[valid] = 50.0

        return result

    if valid.sum() > 1:

        result.loc[valid] = (
            numeric.loc[valid]
            .rank(
                method="average",
                pct=True,
            )
            * 100.0
        )

    return result


def inverse_percentile_score(
    series: pd.Series,
) -> pd.Series:

    """
    Convert a numeric series into a 0-100 score where lower raw values
    are better.

    Used for Debt / Equity.
    """

    score = percentile_score(
        series
    )

    return 100.0 - score


# ============================================================
# TECHNICAL V2
# ============================================================

# ============================================================
# TECHNICAL V2
# ============================================================

# ============================================================
# TECHNICAL V2
# ============================================================

def calculate_technical_v2(
    df: pd.DataFrame,
) -> pd.Series:

    """
    Technical V2 diagnostic.

    For this calibration test, retain the production Technical
    Score as the Technical domain.

    The purpose of this iteration is NOT to redesign Technical.
    It is to isolate whether the Quality/Growth architecture is
    suppressing strong candidates.

    Production Technical Score is already on a 0-100 scale.
    """

    technical = pd.to_numeric(
        df["technical_score"],
        errors="coerce",
    )

    return technical.round(1)
# ============================================================
# QUALITY V2
# ============================================================

# ============================================================
# QUALITY V2
# ============================================================

def calculate_quality_v2(
    df: pd.DataFrame,
) -> pd.Series:

    """
    Quality V2 diagnostic.

    Quality is deliberately restricted to characteristics of
    business/financial quality:

        - Profit Margin
        - Return on Equity
        - Debt to Equity

    Growth is deliberately excluded.

    Each metric is converted to a cross-sectional percentile
    within the August calibration observations.

    Debt to Equity is inverse-scored because lower leverage
    represents stronger balance-sheet quality.

    This is a calibration diagnostic only.
    """

    margin = percentile_score(
        df["profit_margin"]
    )

    roe = percentile_score(
        df["return_on_equity"]
    )

    debt = inverse_percentile_score(
        df["debt_to_equity"]
    )

    components = pd.concat(
        [
            margin.rename("margin"),
            roe.rename("roe"),
            debt.rename("debt"),
        ],
        axis=1,
    )

    quality = components.mean(
        axis=1,
        skipna=True,
    )

    quality = quality.where(
        components.notna().sum(axis=1) > 0
    )

    return quality.round(1)
# ============================================================
# GROWTH V2
# ============================================================

# ============================================================
# GROWTH V2
# ============================================================

def calculate_growth_v2(
    df: pd.DataFrame,
) -> pd.Series:

    """
    Growth V2 diagnostic.

    Growth is deliberately restricted to:

        - Revenue Growth

    Margin, ROE and Debt/Equity are excluded because they belong
    to Quality in this diagnostic architecture.

    Revenue Growth is converted to a cross-sectional percentile
    within the August calibration observations.

    This is a calibration diagnostic only.
    """

    growth = percentile_score(
        df["revenue_growth"]
    )

    return growth.round(1)

# ============================================================
# INVESTMENT SCORE V2
# ============================================================

def calculate_investment_v2(
    technical: pd.Series,
    quality: pd.Series,
    growth: pd.Series,
) -> pd.Series:

    """
    V2 Investment Score.

    Equal domain weighting is used deliberately as a TEST ARCHITECTURE.

    This is NOT a proposed production weighting.

        Technical = 1/3
        Quality   = 1/3
        Growth    = 1/3
    """

    components = pd.concat(
        [
            technical.rename("technical"),
            quality.rename("quality"),
            growth.rename("growth"),
        ],
        axis=1,
    )

    score = components.mean(
        axis=1,
        skipna=True,
    )

    score = score.where(
        components.notna().sum(axis=1) == 3
    )

    return score.round(1)


# ============================================================
# V2 RESULT TABLE
# ============================================================

def build_v2_results(
    df: pd.DataFrame,
) -> pd.DataFrame:

    result = df.copy()

    result["Technical V2"] = (
        calculate_technical_v2(result)
    )

    result["Quality V2"] = (
        calculate_quality_v2(result)
    )

    result["Growth V2"] = (
        calculate_growth_v2(result)
    )

    result["Investment Score V2"] = (
        calculate_investment_v2(
            result["Technical V2"],
            result["Quality V2"],
            result["Growth V2"],
        )
    )

    result["V2 Meets 75"] = (
        result["Investment Score V2"]
        >= MIN_BUY_SCORE
    )

    return result


# ============================================================
# V2 SUMMARY
# ============================================================

def build_v2_summary(
    result: pd.DataFrame,
) -> pd.DataFrame:

    total = len(result)

    meets_75 = int(
        result["V2 Meets 75"].sum()
    )

    return pd.DataFrame(
        [
            {
                "Observations": total,
                "V2 Mean Technical": round(
                    result["Technical V2"].mean(),
                    2,
                ),
                "V2 Mean Quality": round(
                    result["Quality V2"].mean(),
                    2,
                ),
                "V2 Mean Growth": round(
                    result["Growth V2"].mean(),
                    2,
                ),
                "V2 Mean Investment Score": round(
                    result["Investment Score V2"].mean(),
                    2,
                ),
                "V2 Meets 75": meets_75,
                "V2 Meets 75 %": round(
                    meets_75 / total * 100,
                    2,
                )
                if total
                else 0,
            }
        ]
    )


# ============================================================
# SCORE BAND ANALYSIS
# ============================================================

def build_score_band_analysis(
    result: pd.DataFrame,
) -> pd.DataFrame:

    working = result.copy()

    working["V2 Score Band"] = pd.cut(
        working["Investment Score V2"],
        bins=[
            -np.inf,
            49.999,
            59.999,
            69.999,
            74.999,
            np.inf,
        ],
        labels=[
            "<50",
            "50-59",
            "60-69",
            "70-74",
            "75+",
        ],
    )

    grouped = (
        working
        .groupby(
            "V2 Score Band",
            observed=False,
        )
        .agg(
            Observations=(
                "Investment Score V2",
                "count",
            ),
            Average_Technical=(
                "Technical V2",
                "mean",
            ),
            Average_Quality=(
                "Quality V2",
                "mean",
            ),
            Average_Growth=(
                "Growth V2",
                "mean",
            ),
            Average_Investment_Score=(
                "Investment Score V2",
                "mean",
            ),
        )
        .reset_index()
    )

    for column in [
        "Average_Technical",
        "Average_Quality",
        "Average_Growth",
        "Average_Investment_Score",
    ]:

        grouped[column] = grouped[column].round(
            2
        )

    return grouped


# ============================================================
# WINNER CHECK
# ============================================================

def build_known_winner_check(
    result: pd.DataFrame,
) -> pd.DataFrame:

    """
    Check the known August winner examples that we have already
    identified during calibration.

    This is deliberately limited to the known examples rather than
    attempting to infer winners from current Yahoo data.
    """

    known_winners = {
        "PLTR",
        "ARM",
        "ABNB",
        "SNDK",
        "LITE",
        "VRTX",
        "AAPL",
        "CRWD",
    }

    winners = result[
        result["ticker"]
        .astype(str)
        .str.upper()
        .isin(known_winners)
    ].copy()

    if winners.empty:
        return pd.DataFrame(
            columns=[
                "Ticker",
                "Existing Investment Score",
                "Technical V2",
                "Quality V2",
                "Growth V2",
                "Investment Score V2",
                "V2 Meets 75",
            ]
        )

    # One row per ticker, using the highest V2 score observed
    # during the selected period.

    winners["ticker"] = (
        winners["ticker"]
        .astype(str)
        .str.upper()
    )

    winners = (
        winners
        .sort_values(
            [
                "ticker",
                "Investment Score V2",
            ],
            ascending=[
                True,
                False,
            ],
        )
        .drop_duplicates(
            subset=["ticker"]
        )
    )

    return winners[
        [
            "ticker",
            "investment_score",
            "Technical V2",
            "Quality V2",
            "Growth V2",
            "Investment Score V2",
            "V2 Meets 75",
        ]
    ].rename(
        columns={
            "ticker": "Ticker",
            "investment_score": (
                "Existing Investment Score"
            ),
        }
    )


# ============================================================
# YAHOO AVAILABILITY TEST
# ============================================================

def retrieve_current_yahoo_fields(
    tickers: list[str],
) -> pd.DataFrame:

    """
    Retrieve current Yahoo values ONLY for availability diagnostics.

    These values must never be merged into historical August scores.
    """

    rows = []

    total = len(tickers)

    print()
    print(
        "Retrieving CURRENT Yahoo fields for "
        f"{total} tickers for availability diagnostics..."
    )

    for number, ticker in enumerate(
        tickers,
        start=1,
    ):

        print(
            f"[{number}/{total}] {ticker}"
        )

        try:
            info = yf.Ticker(ticker).info

        except Exception as exc:

            print(
                f"  Yahoo retrieval failed: {exc}"
            )

            info = {}

        row = {
            "ticker": ticker,
        }

        for field in YAHOO_FIELDS:
            row[field] = info.get(field)

        rows.append(row)

    return pd.DataFrame(rows)


def build_yahoo_inventory(
    yahoo_df: pd.DataFrame,
) -> pd.DataFrame:

    if yahoo_df.empty:
        return pd.DataFrame()

    total = len(yahoo_df)

    rows = []

    for field, role in YAHOO_FIELDS.items():

        available = int(
            yahoo_df[field].notna().sum()
        )

        rows.append(
            {
                "Field": field,
                "Role": role,
                "Available Tickers": available,
                "Total Tickers": total,
                "Availability %": round(
                    available / total * 100,
                    1,
                ),
            }
        )

    return (
        pd.DataFrame(rows)
        .sort_values(
            "Availability %",
            ascending=False,
        )
    )


# ============================================================
# CORRELATION ANALYSIS
# ============================================================

def build_correlation_analysis(
    df: pd.DataFrame,
    fields: list[str],
) -> pd.DataFrame:

    usable = []

    for field in fields:

        if field not in df.columns:
            continue

        numeric = pd.to_numeric(
            df[field],
            errors="coerce",
        )

        if numeric.notna().sum() >= 2:

            usable.append(field)

    rows = []

    for index, field_a in enumerate(usable):

        for field_b in usable[index + 1:]:

            pair = df[
                [field_a, field_b]
            ].apply(
                pd.to_numeric,
                errors="coerce",
            ).dropna()

            if len(pair) < 2:
                continue

            correlation = pair[
                field_a
            ].corr(
                pair[field_b]
            )

            if pd.isna(correlation):
                continue

            rows.append(
                {
                    "Field A": field_a,
                    "Field B": field_b,
                    "Observations": len(pair),
                    "Pearson Correlation": round(
                        float(correlation),
                        4,
                    ),
                    "Abs Correlation": round(
                        abs(float(correlation)),
                        4,
                    ),
                }
            )

    if not rows:
        return pd.DataFrame()

    return (
        pd.DataFrame(rows)
        .sort_values(
            "Abs Correlation",
            ascending=False,
        )
        .reset_index(drop=True)
    )


# ============================================================
# REALISED PERFORMANCE COMPARISON
# ============================================================

def build_realised_performance_comparison(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compare Production Investment Score with V2 Investment Score
    against matured 5D and 10D realised outcomes.

    Calibration diagnostic only.

    This does NOT:
        - change production scoring
        - change thresholds
        - change weights
        - change recommendations
        - modify the database
    """

    working = df.copy()

    # --------------------------------------------------------
    # LOAD MATURED REALISED OUTCOMES
    #
    # The August observations are point-in-time recommendation
    # evidence. Realised outcomes are loaded separately from
    # recommendation_evaluations and matched by recommendation_id.
    #
    # Current Yahoo data is deliberately NOT used here.
    # --------------------------------------------------------

    database_path = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "portfolio_manager.db"
    )

    if "recommendation_id" not in working.columns:
        print(
            "WARNING: recommendation_id missing from "
            "point-in-time evidence."
        )
        return pd.DataFrame()

    try:
        conn = sqlite3.connect(database_path)

        evaluations = pd.read_sql_query(
            """
            SELECT
                recommendation_id,
                days_after,
                return_percent
            FROM recommendation_evaluations
            WHERE days_after IN (5, 10)
            """,
            conn,
        )

        conn.close()

    except Exception as exc:
        print(
            "WARNING: Unable to load matured outcomes: "
            f"{exc}"
        )
        return pd.DataFrame()

    if evaluations.empty:
        print(
            "WARNING: No matured 5D/10D outcomes found."
        )
        return pd.DataFrame()

    # --------------------------------------------------------
    # Convert the matured outcomes into one row per
    # recommendation_id with separate 5D and 10D returns.
    # --------------------------------------------------------

    evaluations["recommendation_id"] = pd.to_numeric(
        evaluations["recommendation_id"],
        errors="coerce",
    )

    evaluations["return_percent"] = pd.to_numeric(
        evaluations["return_percent"],
        errors="coerce",
    )

    outcome_table = (
        evaluations
        .pivot_table(
            index="recommendation_id",
            columns="days_after",
            values="return_percent",
            aggfunc="first",
        )
        .reset_index()
        .rename(
            columns={
                5: "return_5d",
                10: "return_10d",
            }
        )
    )

    working["recommendation_id"] = pd.to_numeric(
        working["recommendation_id"],
        errors="coerce",
    )

    working = working.merge(
        outcome_table,
        how="left",
        on="recommendation_id",
    )

    return_5d_col = "return_5d"
    return_10d_col = "return_10d"

    print()
    print("=" * 78)
    print("REALISED PERFORMANCE COMPARISON")
    print("=" * 78)

    print(
        f"5D matured observations: "
        f"{working[return_5d_col].notna().sum()}"
    )

    print(
        f"10D matured observations: "
        f"{working[return_10d_col].notna().sum()}"
    )

    if (
        working[return_5d_col].notna().sum() == 0
        and working[return_10d_col].notna().sum() == 0
    ):
        print(
            "WARNING: No matured 5D/10D outcomes matched "
            "to the August recommendation evidence."
        )
        return pd.DataFrame()


    # --------------------------------------------------------
    # Score bands
    # --------------------------------------------------------

    def score_band(score):

        if pd.isna(score):
            return "Missing"

        if score < 50:
            return "<50"

        if score < 60:
            return "50-59"

        if score < 70:
            return "60-69"

        if score < 75:
            return "70-74"

        return "75+"

    rows = []

    score_definitions = [
        (
            "Production Investment Score",
            "investment_score",
        ),
        (
            "V2 Investment Score",
            "Investment Score V2",
        ),
    ]

    for score_name, score_column in score_definitions:

        if score_column not in working.columns:
            continue

        score_values = pd.to_numeric(
            working[score_column],
            errors="coerce",
        )

        # ----------------------------------------------------
        # Overall performance
        # ----------------------------------------------------

        for horizon, return_column in [
            ("5D", return_5d_col),
            ("10D", return_10d_col),
        ]:

            if return_column is None:
                continue

            returns = pd.to_numeric(
                working[return_column],
                errors="coerce",
            )

            valid = pd.DataFrame({
                "score": score_values,
                "return": returns,
            }).dropna()

            if valid.empty:
                continue

            rows.append({
                "Score Model": score_name,
                "Score Band": "ALL",
                "Horizon": horizon,
                "Observations": len(valid),
                "Average Return %": round(
                    valid["return"].mean(),
                    3,
                ),
                "Median Return %": round(
                    valid["return"].median(),
                    3,
                ),
                "Positive Return %": round(
                    valid["return"].gt(0).mean() * 100,
                    2,
                ),
                "Score vs Return Correlation": round(
                    valid["score"].corr(
                        valid["return"]
                    ),
                    3,
                )
                if len(valid) >= 3
                else None,
            })

            # ------------------------------------------------
            # Score-band performance
            # ------------------------------------------------

            valid = valid.copy()

            valid["Score Band"] = (
                valid["score"]
                .apply(score_band)
            )

            for band in [
                "<50",
                "50-59",
                "60-69",
                "70-74",
                "75+",
            ]:

                band_df = valid[
                    valid["Score Band"] == band
                ]

                if band_df.empty:
                    continue

                rows.append({
                    "Score Model": score_name,
                    "Score Band": band,
                    "Horizon": horizon,
                    "Observations": len(band_df),
                    "Average Return %": round(
                        band_df["return"].mean(),
                        3,
                    ),
                    "Median Return %": round(
                        band_df["return"].median(),
                        3,
                    ),
                    "Positive Return %": round(
                        band_df["return"].gt(0).mean() * 100,
                        2,
                    ),
                    "Score vs Return Correlation": round(
                        band_df["score"].corr(
                            band_df["return"]
                        ),
                        3,
                    )
                    if len(band_df) >= 3
                    else None,
                })

    result = pd.DataFrame(rows)

    if result.empty:
        print(
            "No matured performance observations available."
        )
        return result

    print()
    print(
        result.to_string(
            index=False
        )
    )

    return result

def build_component_performance_analysis(evidence):
    """
    Analyse realised 5D performance against the underlying historical
    fundamental inputs used by the production scoring model.

    Diagnostic only.

    Uses:
        recommendation_id
            -> recommendation_evidence
            -> recommendation_evaluations

    This function does not modify production scoring.
    """

    print()
    print("=" * 78)
    print("COMPONENT-LEVEL REALISED PERFORMANCE ANALYSIS")
    print("=" * 78)

    if evidence is None or evidence.empty:
        print("No evidence available.")
        return pd.DataFrame(), pd.DataFrame()

    if "recommendation_id" not in evidence.columns:
        print("ERROR: recommendation_id not present in evidence.")
        return pd.DataFrame(), pd.DataFrame()

    # ------------------------------------------------------------------
    # LOAD AUTHORITATIVE 5D OUTCOMES
    # ------------------------------------------------------------------

    conn = sqlite3.connect(DB_PATH)

    outcomes = pd.read_sql_query(
        """
        SELECT
            recommendation_id,
            evaluation_date,
            return_percent AS return_5d
        FROM recommendation_evaluations
        WHERE days_after = 5
        """,
        conn
    )

    # ------------------------------------------------------------------
    # LOAD POINT-IN-TIME FUNDAMENTAL EVIDENCE
    # ------------------------------------------------------------------

    historical_evidence = pd.read_sql_query(
        """
        SELECT
            recommendation_id,
            ticker,
            capture_date,
            revenue_growth,
            profit_margin,
            return_on_equity,
            debt_to_equity,
            investment_score,
            technical_score,
            quality_score,
            growth_score
        FROM recommendation_evidence
        """,
        conn
    )

    conn.close()

    print(
        f"Historical evidence rows loaded: "
        f"{len(historical_evidence)}"
    )

    print(
        f"5D outcome rows loaded: "
        f"{len(outcomes)}"
    )

    if historical_evidence.empty:
        print("No recommendation_evidence rows found.")
        return pd.DataFrame(), pd.DataFrame()

    # ------------------------------------------------------------------
    # NORMALISE IDS
    # ------------------------------------------------------------------

    evidence = evidence.copy()
    historical_evidence = historical_evidence.copy()
    outcomes = outcomes.copy()

    evidence["recommendation_id"] = pd.to_numeric(
        evidence["recommendation_id"],
        errors="coerce"
    )

    historical_evidence["recommendation_id"] = pd.to_numeric(
        historical_evidence["recommendation_id"],
        errors="coerce"
    )

    outcomes["recommendation_id"] = pd.to_numeric(
        outcomes["recommendation_id"],
        errors="coerce"
    )

    # ------------------------------------------------------------------
    # START WITH THE ACTUAL AUGUST POPULATION
    #
    # Do not assume recommendation_date exists in load_evidence().
    # We only need recommendation_id and the stored production scores.
    # ------------------------------------------------------------------

    population_columns = [
        "recommendation_id",
        "ticker",
        "investment_score",
        "technical_score",
        "quality_score",
        "growth_score",
    ]

    missing_population_columns = [
        column
        for column in population_columns
        if column not in evidence.columns
    ]

    if missing_population_columns:
        print(
            "ERROR: Missing population columns:",
            missing_population_columns
        )
        return pd.DataFrame(), pd.DataFrame()

    component_data = evidence[
        population_columns
    ].copy()

    # ------------------------------------------------------------------
    # JOIN POINT-IN-TIME FUNDAMENTALS
    # ------------------------------------------------------------------

    component_data = component_data.merge(
        historical_evidence[
            [
                "recommendation_id",
                "capture_date",
                "revenue_growth",
                "profit_margin",
                "return_on_equity",
                "debt_to_equity",
            ]
        ],
        on="recommendation_id",
        how="left",
        suffixes=("", "_historical")
    )

    # ------------------------------------------------------------------
    # JOIN AUTHORITATIVE 5D OUTCOME
    # ------------------------------------------------------------------

    component_data = component_data.merge(
        outcomes[
            [
                "recommendation_id",
                "evaluation_date",
                "return_5d",
            ]
        ],
        on="recommendation_id",
        how="left"
    )

    # ------------------------------------------------------------------
    # NORMALISE NUMERIC VALUES
    # ------------------------------------------------------------------

    numeric_columns = [
        "investment_score",
        "technical_score",
        "quality_score",
        "growth_score",
        "revenue_growth",
        "profit_margin",
        "return_on_equity",
        "debt_to_equity",
        "return_5d",
    ]

    for column in numeric_columns:
        if column in component_data.columns:
            component_data[column] = pd.to_numeric(
                component_data[column],
                errors="coerce"
            )

    # ------------------------------------------------------------------
    # USE ONLY MATURED 5D OBSERVATIONS
    # ------------------------------------------------------------------

    matured = component_data[
        component_data["return_5d"].notna()
    ].copy()

    print()
    print(
        f"Matured 5D observations: {len(matured)}"
    )

    if matured.empty:
        print("No matured 5D observations available.")
        return pd.DataFrame(), pd.DataFrame()

    # ------------------------------------------------------------------
    # COMPONENTS TO TEST
    # ------------------------------------------------------------------

    components = {
        "Revenue Growth": "revenue_growth",
        "Profit Margin": "profit_margin",
        "Return on Equity": "return_on_equity",
        "Debt to Equity": "debt_to_equity",
        "Production Quality Score": "quality_score",
        "Production Growth Score": "growth_score",
        "Production Technical Score": "technical_score",
        "Production Investment Score": "investment_score",
    }

    # ------------------------------------------------------------------
    # COMPONENT SUMMARY
    # ------------------------------------------------------------------

    summary_rows = []

    for component_name, column in components.items():

        series = matured[
            [column, "return_5d"]
        ].dropna()

        if series.empty:
            print(
                f"WARNING: {component_name} "
                f"has no usable historical observations."
            )
            continue

        correlation = series[column].corr(
            series["return_5d"]
        )

        summary_rows.append(
            {
                "Component": component_name,
                "Source Column": column,
                "Observations": len(series),
                "Coverage %": round(
                    len(series) / len(matured) * 100,
                    2
                ),
                "Mean Input": round(
                    series[column].mean(),
                    4
                ),
                "Median Input": round(
                    series[column].median(),
                    4
                ),
                "Min Input": round(
                    series[column].min(),
                    4
                ),
                "Max Input": round(
                    series[column].max(),
                    4
                ),
                "Average 5D Return %": round(
                    series["return_5d"].mean(),
                    3
                ),
                "Median 5D Return %": round(
                    series["return_5d"].median(),
                    3
                ),
                "Positive 5D %": round(
                    (series["return_5d"] > 0).mean() * 100,
                    2
                ),
                "Correlation to 5D Return": round(
                    correlation,
                    3
                ),
            }
        )

    component_summary = pd.DataFrame(
        summary_rows
    )

    # ------------------------------------------------------------------
    # QUARTILE PERFORMANCE
    # ------------------------------------------------------------------

    quartile_rows = []

    for component_name, column in components.items():

        series = matured[
            [column, "return_5d"]
        ].dropna().copy()

        if len(series) < 8:
            continue

        try:
            series["_Quartile"] = pd.qcut(
                series[column],
                q=4,
                labels=[
                    "Q1 - Lowest",
                    "Q2",
                    "Q3",
                    "Q4 - Highest",
                ],
                duplicates="drop"
            )
        except ValueError:
            continue

        for quartile, group in series.groupby(
            "_Quartile",
            observed=True
        ):

            if group.empty:
                continue

            quartile_rows.append(
                {
                    "Component": component_name,
                    "Source Column": column,
                    "Quartile": str(quartile),
                    "Observations": len(group),
                    "Mean Input": round(
                        group[column].mean(),
                        4
                    ),
                    "Average 5D Return %": round(
                        group["return_5d"].mean(),
                        3
                    ),
                    "Median 5D Return %": round(
                        group["return_5d"].median(),
                        3
                    ),
                    "Positive 5D %": round(
                        (group["return_5d"] > 0).mean() * 100,
                        2
                    ),
                }
            )

    component_quartiles = pd.DataFrame(
        quartile_rows
    )

    # ------------------------------------------------------------------
    # DISPLAY RESULTS
    # ------------------------------------------------------------------

    print()
    print("COMPONENT SUMMARY")
    print("-" * 78)

    if component_summary.empty:
        print("No component results available.")
    else:
        print(
            component_summary.to_string(
                index=False
            )
        )

    print()
    print("COMPONENT QUARTILE PERFORMANCE")
    print("-" * 78)

    if component_quartiles.empty:
        print("No quartile results available.")
    else:
        print(
            component_quartiles.to_string(
                index=False
            )
        )

    # ------------------------------------------------------------------
    # RETURN
    # ------------------------------------------------------------------

    return (
        component_summary,
        component_quartiles,
    )
# ============================================================
# STAGE 2 — CANDIDATE SCORING ARCHITECTURES
# ============================================================

def build_stage2_model_results(
    evidence: pd.DataFrame,
) -> pd.DataFrame:
    """
    Stage 2 calibration test.

    Compare candidate Investment Score architectures against the
    same August point-in-time evidence.

    Models
    ------

    Production Baseline
        Uses the stored production Investment Score.

    Model A — Clean / Equal
        Technical = production Technical Score
        Quality   = percentile(Margin, ROE, inverse Debt/Equity)
        Growth    = percentile(Revenue Growth)

        Weights:
            Technical 33.33%
            Quality   33.33%
            Growth    33.33%

    Model B — Clean / Production Weights
        Same clean Quality/Growth architecture as Model A.

        Weights:
            Technical 60.0%
            Quality   21.3%
            Growth    18.7%

    Model C — Existing Components / Balanced Weights
        Uses the stored production Technical, Quality and Growth
        component scores.

        Weights:
            Technical 50%
            Quality   25%
            Growth    25%

    This function is diagnostic only.

    It does NOT:
        - modify production scoring
        - modify scoring_weights.json
        - modify MIN_BUY_SCORE
        - modify recommendations
        - modify the database
        - modify governance
    """

    result = evidence.copy()

    # --------------------------------------------------------
    # CLEAN COMPONENTS
    # --------------------------------------------------------

    clean_technical = calculate_technical_v2(
        result
    )

    clean_quality = calculate_quality_v2(
        result
    )

    clean_growth = calculate_growth_v2(
        result
    )

    # Store the clean domains for inspection.
    result["Stage2 Technical"] = clean_technical
    result["Stage2 Clean Quality"] = clean_quality
    result["Stage2 Clean Growth"] = clean_growth

    # --------------------------------------------------------
    # MODEL A — CLEAN / EQUAL
    # --------------------------------------------------------

    clean_equal_components = pd.concat(
        [
            clean_technical.rename("technical"),
            clean_quality.rename("quality"),
            clean_growth.rename("growth"),
        ],
        axis=1,
    )

    result["Model A Investment Score"] = (
        clean_equal_components.mean(
            axis=1,
            skipna=False,
        )
        .round(1)
    )

    # --------------------------------------------------------
    # MODEL B — CLEAN / PRODUCTION WEIGHTS
    # --------------------------------------------------------

    clean_production_components = pd.concat(
        [
            clean_technical.rename("technical"),
            clean_quality.rename("quality"),
            clean_growth.rename("growth"),
        ],
        axis=1,
    )

    result["Model B Investment Score"] = (
        (
            clean_production_components["technical"] * 0.600
            + clean_production_components["quality"] * 0.213
            + clean_production_components["growth"] * 0.187
        )
        .round(1)
    )

    # --------------------------------------------------------
    # MODEL C — EXISTING COMPONENTS / BALANCED WEIGHTS
    # --------------------------------------------------------

    production_components = pd.concat(
        [
            pd.to_numeric(
                result["technical_score"],
                errors="coerce",
            ).rename("technical"),

            pd.to_numeric(
                result["quality_score"],
                errors="coerce",
            ).rename("quality"),

            pd.to_numeric(
                result["growth_score"],
                errors="coerce",
            ).rename("growth"),
        ],
        axis=1,
    )

    result["Model C Investment Score"] = (
        (
            production_components["technical"] * 0.50
            + production_components["quality"] * 0.25
            + production_components["growth"] * 0.25
        )
        .round(1)
    )

    # --------------------------------------------------------
    # THRESHOLD FLAGS
    # --------------------------------------------------------

    result["Production Meets 75"] = (
        pd.to_numeric(
            result["investment_score"],
            errors="coerce",
        )
        >= MIN_BUY_SCORE
    )

    result["Model A Meets 75"] = (
        result["Model A Investment Score"]
        >= MIN_BUY_SCORE
    )

    result["Model B Meets 75"] = (
        result["Model B Investment Score"]
        >= MIN_BUY_SCORE
    )

    result["Model C Meets 75"] = (
        result["Model C Investment Score"]
        >= MIN_BUY_SCORE
    )

    return result


def build_stage2_performance_analysis(
    result: pd.DataFrame,
) -> pd.DataFrame:
    """
    Compare Stage 2 candidate Investment Score models against
    authoritative realised 5D outcomes.

    All models use exactly the same August observations and the
    same recommendation_evaluations 5D outcomes.

    Diagnostic only.
    """

    working = result.copy()

    # --------------------------------------------------------
    # LOAD AUTHORITATIVE 5D OUTCOMES
    # --------------------------------------------------------

    if "recommendation_id" not in working.columns:
        return pd.DataFrame()

    conn = sqlite3.connect(DB_PATH)

    outcomes = pd.read_sql_query(
        """
        SELECT
            recommendation_id,
            return_percent AS return_5d
        FROM recommendation_evaluations
        WHERE days_after = 5
        """,
        conn,
    )

    conn.close()

    outcomes["recommendation_id"] = pd.to_numeric(
        outcomes["recommendation_id"],
        errors="coerce",
    )

    outcomes["return_5d"] = pd.to_numeric(
        outcomes["return_5d"],
        errors="coerce",
    )

    working["recommendation_id"] = pd.to_numeric(
        working["recommendation_id"],
        errors="coerce",
    )

    working = working.merge(
        outcomes[
            [
                "recommendation_id",
                "return_5d",
            ]
        ],
        on="recommendation_id",
        how="left",
    )

    matured = working[
        working["return_5d"].notna()
    ].copy()

    print()
    print("=" * 78)
    print("STAGE 2 — CANDIDATE MODEL PERFORMANCE")
    print("=" * 78)
    print(
        f"Matured 5D observations: {len(matured)}"
    )

    if matured.empty:
        return pd.DataFrame()

    models = {
        "Production Baseline": "investment_score",
        "Model A — Clean / Equal": "Model A Investment Score",
        "Model B — Clean / Production Weights": (
            "Model B Investment Score"
        ),
        "Model C — Existing Components / Balanced": (
            "Model C Investment Score"
        ),
    }

    rows = []

    # --------------------------------------------------------
    # OVERALL MODEL PERFORMANCE
    # --------------------------------------------------------

    for model_name, score_column in models.items():

        valid = matured[
            [
                score_column,
                "return_5d",
            ]
        ].dropna()

        if valid.empty:
            continue

        rows.append(
            {
                "Model": model_name,
                "Score Band": "ALL",
                "Observations": len(valid),
                "Mean Score": round(
                    valid[score_column].mean(),
                    2,
                ),
                "Meets 75": int(
                    (
                        valid[score_column]
                        >= MIN_BUY_SCORE
                    ).sum()
                ),
                "Meets 75 %": round(
                    (
                        valid[score_column]
                        >= MIN_BUY_SCORE
                    ).mean() * 100,
                    2,
                ),
                "Average 5D Return %": round(
                    valid["return_5d"].mean(),
                    3,
                ),
                "Median 5D Return %": round(
                    valid["return_5d"].median(),
                    3,
                ),
                "Positive 5D %": round(
                    valid["return_5d"].gt(0).mean()
                    * 100,
                    2,
                ),
                "Score / Return Correlation": round(
                    valid[score_column].corr(
                        valid["return_5d"]
                    ),
                    3,
                ),
            }
        )

        # ----------------------------------------------------
        # SCORE-BAND PERFORMANCE
        # ----------------------------------------------------

        valid = valid.copy()

        valid["_band"] = pd.cut(
            valid[score_column],
            bins=[
                -np.inf,
                49.999,
                59.999,
                69.999,
                74.999,
                np.inf,
            ],
            labels=[
                "<50",
                "50-59",
                "60-69",
                "70-74",
                "75+",
            ],
        )

        for band in [
            "<50",
            "50-59",
            "60-69",
            "70-74",
            "75+",
        ]:

            band_df = valid[
                valid["_band"] == band
            ]

            if band_df.empty:
                continue

            rows.append(
                {
                    "Model": model_name,
                    "Score Band": band,
                    "Observations": len(band_df),
                    "Mean Score": round(
                        band_df[score_column].mean(),
                        2,
                    ),
                    "Meets 75": int(
                        (
                            band_df[score_column]
                            >= MIN_BUY_SCORE
                        ).sum()
                    ),
                    "Meets 75 %": round(
                        (
                            band_df[score_column]
                            >= MIN_BUY_SCORE
                        ).mean() * 100,
                        2,
                    ),
                    "Average 5D Return %": round(
                        band_df["return_5d"].mean(),
                        3,
                    ),
                    "Median 5D Return %": round(
                        band_df["return_5d"].median(),
                        3,
                    ),
                    "Positive 5D %": round(
                        band_df["return_5d"].gt(0).mean()
                        * 100,
                        2,
                    ),
                    "Score / Return Correlation": round(
                        band_df[score_column].corr(
                            band_df["return_5d"]
                        ),
                        3,
                    )
                    if len(band_df) >= 3
                    else None,
                }
            )

    performance = pd.DataFrame(rows)

    print()
    print(
        performance.to_string(
            index=False
        )
    )

    return performance


def build_stage2_threshold_movement(
    result: pd.DataFrame,
) -> pd.DataFrame:
    """
    Identify observations whose threshold status changes under
    each candidate model.

    This is particularly important because the existing BUY
    threshold of 75 is deliberately being held constant.

    The function does not decide whether any change is desirable.
    """

    working = result.copy()

    production_score = pd.to_numeric(
        working["investment_score"],
        errors="coerce",
    )

    working["Production Status"] = np.where(
        production_score >= MIN_BUY_SCORE,
        "75+",
        "<75",
    )

    models = {
        "Model A — Clean / Equal": (
            "Model A Investment Score"
        ),
        "Model B — Clean / Production Weights": (
            "Model B Investment Score"
        ),
        "Model C — Existing Components / Balanced": (
            "Model C Investment Score"
        ),
    }

    rows = []

    for model_name, score_column in models.items():

        model_score = pd.to_numeric(
            working[score_column],
            errors="coerce",
        )

        model_status = np.where(
            model_score >= MIN_BUY_SCORE,
            "75+",
            "<75",
        )

        changed = (
            working["Production Status"]
            != model_status
        )

        rows.append(
            {
                "Model": model_name,
                "Observations": len(working),
                "Production 75+": int(
                    (
                        production_score
                        >= MIN_BUY_SCORE
                    ).sum()
                ),
                "Model 75+": int(
                    (
                        model_score
                        >= MIN_BUY_SCORE
                    ).sum()
                ),
                "Moved Below 75 to 75+": int(
                    (
                        (working["Production Status"] == "<75")
                        & (model_status == "75+")
                    ).sum()
                ),
                "Moved 75+ to Below 75": int(
                    (
                        (working["Production Status"] == "75+")
                        & (model_status == "<75")
                    ).sum()
                ),
                "Threshold Status Changed": int(
                    changed.sum()
                ),
            }
        )

    return pd.DataFrame(rows)


def build_stage2_known_winner_analysis(
    result: pd.DataFrame,
) -> pd.DataFrame:
    """
    Show how the candidate models treat the known August winners.

    The test uses the same known winner set already established
    during Stage 1.

    One row per ticker, using the highest candidate score observed
    during the August period.
    """

    known_winners = {
        "PLTR",
        "ARM",
        "ABNB",
        "SNDK",
        "LITE",
        "VRTX",
        "AAPL",
        "CRWD",
    }

    working = result.copy()

    working["ticker"] = (
        working["ticker"]
        .astype(str)
        .str.upper()
    )

    working = working[
        working["ticker"].isin(
            known_winners
        )
    ].copy()

    if working.empty:
        return pd.DataFrame()

    working = (
        working
        .sort_values(
            [
                "ticker",
                "investment_score",
            ],
            ascending=[
                True,
                False,
            ],
        )
        .drop_duplicates(
            subset=["ticker"]
        )
    )

    output = working[
        [
            "ticker",
            "investment_score",
            "Model A Investment Score",
            "Model B Investment Score",
            "Model C Investment Score",
            "Production Meets 75",
            "Model A Meets 75",
            "Model B Meets 75",
            "Model C Meets 75",
        ]
    ].copy()

    return output.rename(
        columns={
            "ticker": "Ticker",
            "investment_score": (
                "Production Investment Score"
            ),
        }
    )


def run_stage2_calibration(
    evidence: pd.DataFrame,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
]:
    """
    Execute the complete Stage 2 diagnostic.

    Returns:
        result
        performance
        threshold_movement
        known_winners
    """

    result = build_stage2_model_results(
        evidence
    )

    performance = (
        build_stage2_performance_analysis(
            result
        )
    )

    threshold_movement = (
        build_stage2_threshold_movement(
            result
        )
    )

    known_winners = (
        build_stage2_known_winner_analysis(
            result
        )
    )

    return (
        result,
        performance,
        threshold_movement,
        known_winners,
    )
# ============================================================
# FINAL DIAGNOSTIC — SUB-75 FAILURE-CASE ANALYSIS
# ============================================================

def build_failure_case_analysis(
    calibration_evidence: pd.DataFrame,
    holdout_evidence: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Final A6 diagnostic.

    Identify observations that:
        1. had a production Investment Score below 75
        2. subsequently produced a positive / strong 5D outcome

    The analysis is deliberately systematic rather than based on
    named stocks or selected examples.

    Outcome thresholds:
        >0%
        >=5%
        >=10%

    For each failed sub-75 observation, determine which production
    component contributed the largest negative score drag relative
    to a neutral component value of 75.

    Production weights:
        Technical = 60.0%
        Quality   = 21.3%
        Growth    = 18.7%

    This is diagnostic only.

    It does NOT:
        - modify production scoring
        - modify scoring_weights.json
        - modify MIN_BUY_SCORE
        - modify recommendations
        - modify the database
        - modify governance
    """

    print()
    print("=" * 78)
    print("FINAL A6 DIAGNOSTIC — SUB-75 FAILURE-CASE ANALYSIS")
    print("=" * 78)

    # --------------------------------------------------------
    # COMBINE AUGUST CALIBRATION AND SEPTEMBER HOLDOUT
    # --------------------------------------------------------

    august = calibration_evidence.copy()
    september = holdout_evidence.copy()

    august["Analysis Period"] = "August Calibration"
    september["Analysis Period"] = "September Holdout"

    population = pd.concat(
        [
            august,
            september,
        ],
        ignore_index=True,
    )

    if population.empty:
        print("No evidence available.")
        return pd.DataFrame(), pd.DataFrame()

    # --------------------------------------------------------
    # NORMALISE IDS
    # --------------------------------------------------------

    population["recommendation_id"] = pd.to_numeric(
        population["recommendation_id"],
        errors="coerce",
    )

    # --------------------------------------------------------
    # LOAD AUTHORITATIVE 5D OUTCOMES
    # --------------------------------------------------------

    try:
        conn = sqlite3.connect(DB_PATH)

        outcomes = pd.read_sql_query(
            """
            SELECT
                recommendation_id,
                evaluation_date,
                return_percent AS return_5d
            FROM recommendation_evaluations
            WHERE days_after = 5
            """,
            conn,
        )

        conn.close()

    except Exception as exc:

        print(
            "WARNING: Unable to load 5D outcomes: "
            f"{exc}"
        )

        return pd.DataFrame(), pd.DataFrame()

    if outcomes.empty:
        print("No 5D outcomes available.")
        return pd.DataFrame(), pd.DataFrame()

    outcomes["recommendation_id"] = pd.to_numeric(
        outcomes["recommendation_id"],
        errors="coerce",
    )

    outcomes["return_5d"] = pd.to_numeric(
        outcomes["return_5d"],
        errors="coerce",
    )

    # --------------------------------------------------------
    # JOIN REALISED OUTCOMES
    # --------------------------------------------------------

    population = population.merge(
        outcomes[
            [
                "recommendation_id",
                "evaluation_date",
                "return_5d",
            ]
        ],
        on="recommendation_id",
        how="left",
    )

    # --------------------------------------------------------
    # NORMALISE PRODUCTION SCORE COMPONENTS
    # --------------------------------------------------------

    score_columns = [
        "investment_score",
        "technical_score",
        "quality_score",
        "growth_score",
    ]

    for column in score_columns:

        population[column] = pd.to_numeric(
            population[column],
            errors="coerce",
        )

    population["return_5d"] = pd.to_numeric(
        population["return_5d"],
        errors="coerce",
    )

    # --------------------------------------------------------
    # ONLY MATURED SUB-75 OBSERVATIONS
    # --------------------------------------------------------

    failed = population[
        (
            population["investment_score"]
            < MIN_BUY_SCORE
        )
        & population["return_5d"].notna()
    ].copy()

    print(
        f"Total matured sub-75 observations: "
        f"{len(failed)}"
    )

    if failed.empty:
        print("No matured sub-75 observations found.")
        return pd.DataFrame(), pd.DataFrame()

    # --------------------------------------------------------
    # SCORE BANDS
    # --------------------------------------------------------

    failed["Production Score Band"] = pd.cut(
        failed["investment_score"],
        bins=[
            -np.inf,
            49.999,
            59.999,
            69.999,
            74.999,
        ],
        labels=[
            "<50",
            "50-59",
            "60-69",
            "70-74",
        ],
    )

    # --------------------------------------------------------
    # COMPONENT SCORE DRAG
    #
    # A component at 75 contributes zero drag.
    #
    # Example:
    # Quality = 40
    # Quality weight = 21.3%
    #
    # Drag = (40 - 75) * 0.213
    #      = -7.455 Investment Score points
    #
    # The most negative component is the largest suppressor.
    # --------------------------------------------------------

    weights = {
        "Technical": 0.600,
        "Quality": 0.213,
        "Growth": 0.187,
    }

    component_columns = {
        "Technical": "technical_score",
        "Quality": "quality_score",
        "Growth": "growth_score",
    }

    for component_name, column in component_columns.items():

        failed[
            f"{component_name} Neutral Drag"
        ] = (
            failed[column] - 75.0
        ) * weights[component_name]

    drag_columns = [
        "Technical Neutral Drag",
        "Quality Neutral Drag",
        "Growth Neutral Drag",
    ]

    failed["Dominant Suppressor"] = (
        failed[drag_columns]
        .idxmin(axis=1)
        .str.replace(
            " Neutral Drag",
            "",
            regex=False,
        )
    )

    failed["Largest Component Drag"] = (
        failed[drag_columns]
        .min(axis=1)
    )

    # --------------------------------------------------------
    # HOW FAR BELOW 75?
    # --------------------------------------------------------

    failed["Score Gap to 75"] = (
        MIN_BUY_SCORE
        - failed["investment_score"]
    )

    # --------------------------------------------------------
    # COUNTERFACTUAL COMPONENT TEST
    #
    # What would the Investment Score become if one component
    # were raised to 75 while all other production components
    # remained unchanged?
    #
    # This tells us whether a single component was sufficient
    # to explain the threshold miss.
    # --------------------------------------------------------

    for component_name, column in component_columns.items():

        weight = weights[component_name]

        failed[
            f"Score if {component_name}=75"
        ] = (
            failed["investment_score"]
            + (
                75.0
                - failed[column]
            ) * weight
        )

    # --------------------------------------------------------
    # OUTCOME FLAGS
    # --------------------------------------------------------

    failed["Positive >0%"] = (
        failed["return_5d"] > 0
    )

    failed["Strong >=5%"] = (
        failed["return_5d"] >= 5
    )

    failed["Very Strong >=10%"] = (
        failed["return_5d"] >= 10
    )

    # --------------------------------------------------------
    # DETAILED FAILURE-CASE OUTPUT
    # --------------------------------------------------------

    detail_columns = [
        "Analysis Period",
        "capture_date",
        "ticker",
        "recommendation_id",
        "investment_score",
        "technical_score",
        "quality_score",
        "growth_score",
        "return_5d",
        "Production Score Band",
        "Score Gap to 75",
        "Technical Neutral Drag",
        "Quality Neutral Drag",
        "Growth Neutral Drag",
        "Dominant Suppressor",
        "Largest Component Drag",
        "Score if Technical=75",
        "Score if Quality=75",
        "Score if Growth=75",
        "Positive >0%",
        "Strong >=5%",
        "Very Strong >=10%",
    ]

    detail = failed[
        detail_columns
    ].copy()

    # --------------------------------------------------------
    # SUMMARY BY PERIOD / SCORE BAND / OUTCOME LEVEL
    # --------------------------------------------------------

    summary_rows = []

    outcome_definitions = [
        (
            "Positive >0%",
            failed["return_5d"] > 0,
        ),
        (
            "Strong >=5%",
            failed["return_5d"] >= 5,
        ),
        (
            "Very Strong >=10%",
            failed["return_5d"] >= 10,
        ),
    ]

    for outcome_name, outcome_mask in outcome_definitions:

        cohort = failed[
            outcome_mask
        ].copy()

        if cohort.empty:
            continue

        for period in [
            "August Calibration",
            "September Holdout",
        ]:

            period_cohort = cohort[
                cohort["Analysis Period"]
                == period
            ].copy()

            if period_cohort.empty:
                continue

            for score_band in [
                "<50",
                "50-59",
                "60-69",
                "70-74",
            ]:

                band_cohort = period_cohort[
                    period_cohort[
                        "Production Score Band"
                    ] == score_band
                ].copy()

                if band_cohort.empty:
                    continue

                suppressor_counts = (
                    band_cohort[
                        "Dominant Suppressor"
                    ]
                    .value_counts()
                )

                dominant_suppressor = (
                    suppressor_counts
                    .index[0]
                    if not suppressor_counts.empty
                    else None
                )

                dominant_suppressor_pct = (
                    suppressor_counts.iloc[0]
                    / len(band_cohort)
                    * 100
                    if not suppressor_counts.empty
                    else None
                )

                summary_rows.append(
                    {
                        "Outcome Level": outcome_name,
                        "Analysis Period": period,
                        "Production Score Band": score_band,
                        "Observations": len(
                            band_cohort
                        ),
                        "Average Production Score": round(
                            band_cohort[
                                "investment_score"
                            ].mean(),
                            2,
                        ),
                        "Average 5D Return %": round(
                            band_cohort[
                                "return_5d"
                            ].mean(),
                            3,
                        ),
                        "Median 5D Return %": round(
                            band_cohort[
                                "return_5d"
                            ].median(),
                            3,
                        ),
                        "Average Technical": round(
                            band_cohort[
                                "technical_score"
                            ].mean(),
                            2,
                        ),
                        "Average Quality": round(
                            band_cohort[
                                "quality_score"
                            ].mean(),
                            2,
                        ),
                        "Average Growth": round(
                            band_cohort[
                                "growth_score"
                            ].mean(),
                            2,
                        ),
                        "Dominant Suppressor": (
                            dominant_suppressor
                        ),
                        "Dominant Suppressor %": round(
                            dominant_suppressor_pct,
                            2,
                        )
                        if dominant_suppressor_pct
                        is not None
                        else None,
                        "Avg Technical Drag": round(
                            band_cohort[
                                "Technical Neutral Drag"
                            ].mean(),
                            3,
                        ),
                        "Avg Quality Drag": round(
                            band_cohort[
                                "Quality Neutral Drag"
                            ].mean(),
                            3,
                        ),
                        "Avg Growth Drag": round(
                            band_cohort[
                                "Growth Neutral Drag"
                            ].mean(),
                            3,
                        ),
                        "Would Quality=75 Reach 75 %": round(
                            (
                                band_cohort[
                                    "Score if Quality=75"
                                ]
                                >= MIN_BUY_SCORE
                            ).mean()
                            * 100,
                            2,
                        ),
                        "Would Growth=75 Reach 75 %": round(
                            (
                                band_cohort[
                                    "Score if Growth=75"
                                ]
                                >= MIN_BUY_SCORE
                            ).mean()
                            * 100,
                            2,
                        ),
                        "Would Technical=75 Reach 75 %": round(
                            (
                                band_cohort[
                                    "Score if Technical=75"
                                ]
                                >= MIN_BUY_SCORE
                            ).mean()
                            * 100,
                            2,
                        ),
                    }
                )

    summary = pd.DataFrame(
        summary_rows
    )

    # --------------------------------------------------------
    # OVERALL FAILURE-CASE SUMMARY
    # --------------------------------------------------------

    overall_rows = []

    for outcome_name, outcome_mask in outcome_definitions:

        cohort = failed[
            outcome_mask
        ].copy()

        if cohort.empty:
            continue

        suppressor_counts = (
            cohort[
                "Dominant Suppressor"
            ]
            .value_counts()
        )

        overall_rows.append(
            {
                "Outcome Level": outcome_name,
                "Analysis Period": "ALL",
                "Observations": len(cohort),
                "Average Production Score": round(
                    cohort[
                        "investment_score"
                    ].mean(),
                    2,
                ),
                "Average 5D Return %": round(
                    cohort[
                        "return_5d"
                    ].mean(),
                    3,
                ),
                "Median 5D Return %": round(
                    cohort[
                        "return_5d"
                    ].median(),
                    3,
                ),
                "Average Technical": round(
                    cohort[
                        "technical_score"
                    ].mean(),
                    2,
                ),
                "Average Quality": round(
                    cohort[
                        "quality_score"
                    ].mean(),
                    2,
                ),
                "Average Growth": round(
                    cohort[
                        "growth_score"
                    ].mean(),
                    2,
                ),
                "Technical Dominant %": round(
                    (
                        cohort[
                            "Dominant Suppressor"
                        ]
                        == "Technical"
                    ).mean()
                    * 100,
                    2,
                ),
                "Quality Dominant %": round(
                    (
                        cohort[
                            "Dominant Suppressor"
                        ]
                        == "Quality"
                    ).mean()
                    * 100,
                    2,
                ),
                "Growth Dominant %": round(
                    (
                        cohort[
                            "Dominant Suppressor"
                        ]
                        == "Growth"
                    ).mean()
                    * 100,
                    2,
                ),
                "Would Quality=75 Reach 75 %": round(
                    (
                        cohort[
                            "Score if Quality=75"
                        ]
                        >= MIN_BUY_SCORE
                    ).mean()
                    * 100,
                    2,
                ),
                "Would Growth=75 Reach 75 %": round(
                    (
                        cohort[
                            "Score if Growth=75"
                        ]
                        >= MIN_BUY_SCORE
                    ).mean()
                    * 100,
                    2,
                ),
                "Would Technical=75 Reach 75 %": round(
                    (
                        cohort[
                            "Score if Technical=75"
                        ]
                        >= MIN_BUY_SCORE
                    ).mean()
                    * 100,
                    2,
                ),
            }
        )

    overall = pd.DataFrame(
        overall_rows
    )

    # --------------------------------------------------------
    # DISPLAY
    # --------------------------------------------------------

    print()
    print(
        "MATURED SUB-75 FAILURE-CASE SUMMARY"
    )
    print("-" * 78)

    if overall.empty:
        print(
            "No qualifying failure cases found."
        )
    else:
        print(
            overall.to_string(
                index=False
            )
        )

    print()
    print(
        "FAILURE-CASE ANALYSIS BY PERIOD / SCORE BAND"
    )
    print("-" * 78)

    if summary.empty:
        print(
            "No cohort-level failure-case results found."
        )
    else:
        print(
            summary.to_string(
                index=False
            )
        )

    # --------------------------------------------------------
    # MOST IMPORTANT OBSERVATIONS
    # --------------------------------------------------------

    print()
    print(
        "FINAL DIAGNOSTIC — STRONG SUB-75 OBSERVATIONS"
    )
    print("-" * 78)

    strong = failed[
        failed["return_5d"] >= 5
    ].copy()

    if strong.empty:

        print(
            "No matured sub-75 observations achieved "
            "a 5D return of >=5%."
        )

    else:

        print(
            f"Strong sub-75 observations (>=5%): "
            f"{len(strong)}"
        )

        print(
            "Dominant suppressor distribution:"
        )

        print(
            strong[
                "Dominant Suppressor"
            ]
            .value_counts(
                normalize=True
            )
            .mul(100)
            .round(2)
            .to_string()
        )

        print()

        print(
            "Average component scores:"
        )

        print(
            strong[
                [
                    "technical_score",
                    "quality_score",
                    "growth_score",
                ]
            ]
            .mean()
            .round(2)
            .to_string()
        )

        print()

        print(
            "Average component score drag versus neutral 75:"
        )

        print(
            strong[
                [
                    "Technical Neutral Drag",
                    "Quality Neutral Drag",
                    "Growth Neutral Drag",
                ]
            ]
            .mean()
            .round(3)
            .to_string()
        )

    return (
        detail,
        summary,
    )

# ============================================================
# FINAL QUALITY COMPONENT DIAGNOSTIC
# ============================================================

def build_quality_component_diagnostic(
    calibration_evidence: pd.DataFrame,
    holdout_evidence: pd.DataFrame,
) -> pd.DataFrame:
    """
    Final component-level Quality diagnostic.

    Reconstruct the ACTUAL production Quality scoring rules
    using only point-in-time recommendation evidence.

    This is diagnostic only.

    It does NOT modify:
        - production scoring
        - scoring_weights.json
        - MIN_BUY_SCORE
        - recommendations
        - database
        - governance
    """

    print()
    print("=" * 78)
    print("FINAL A6 DIAGNOSTIC — PRODUCTION QUALITY COMPONENT CONTRIBUTIONS")
    print("=" * 78)

    # --------------------------------------------------------
    # COMBINE CALIBRATION + HOLDOUT
    # --------------------------------------------------------

    august = calibration_evidence.copy()
    september = holdout_evidence.copy()

    august["Analysis Period"] = "August Calibration"
    september["Analysis Period"] = "September Holdout"

    population = pd.concat(
        [
            august,
            september,
        ],
        ignore_index=True,
    )

    if population.empty:
        print("No evidence available.")
        return pd.DataFrame()

    # --------------------------------------------------------
    # NORMALISE NUMERIC INPUTS
    # --------------------------------------------------------

    numeric_fields = [
        "recommendation_id",
        "investment_score",
        "quality_score",
        "technical_score",
        "growth_score",
        "revenue_growth",
        "profit_margin",
        "return_on_equity",
        "debt_to_equity",
    ]

    for column in numeric_fields:
        if column in population.columns:
            population[column] = pd.to_numeric(
                population[column],
                errors="coerce",
            )

    # --------------------------------------------------------
    # LOAD AUTHORITATIVE 5D OUTCOMES
    # --------------------------------------------------------

    try:

        conn = sqlite3.connect(DB_PATH)

        outcomes = pd.read_sql_query(
            """
            SELECT
                recommendation_id,
                return_percent AS return_5d
            FROM recommendation_evaluations
            WHERE days_after = 5
            """,
            conn,
        )

        conn.close()

    except Exception as exc:

        print(
            "WARNING: Unable to load 5D outcomes: "
            f"{exc}"
        )

        return pd.DataFrame()

    if outcomes.empty:
        print("No 5D outcomes available.")
        return pd.DataFrame()

    outcomes["recommendation_id"] = pd.to_numeric(
        outcomes["recommendation_id"],
        errors="coerce",
    )

    outcomes["return_5d"] = pd.to_numeric(
        outcomes["return_5d"],
        errors="coerce",
    )

    # --------------------------------------------------------
    # JOIN OUTCOMES
    # --------------------------------------------------------

    population = population.merge(
        outcomes[
            [
                "recommendation_id",
                "return_5d",
            ]
        ],
        on="recommendation_id",
        how="left",
    )

    # --------------------------------------------------------
    # RECONSTRUCT PRODUCTION QUALITY POINTS
    #
    # These rules intentionally mirror analysis/quality.py.
    #
    # Missing point-in-time fields remain missing/zero exactly
    # as they effectively behave in the production scorer.
    # --------------------------------------------------------

    revenue_growth = population["revenue_growth"]

    population["Quality Revenue Growth Points"] = np.select(
        [
            revenue_growth > 0.50,
            revenue_growth > 0.20,
            revenue_growth > 0.05,
        ],
        [
            25.0,
            20.0,
            10.0,
        ],
        default=0.0,
    )

    # Earnings Growth is not present in recommendation_evidence.
    # Therefore it cannot be retrospectively reconstructed without
    # introducing non-point-in-time data.
    population["Quality Earnings Growth Points"] = 0.0

    margin = population["profit_margin"]

    population["Quality Profit Margin Points"] = np.select(
        [
            margin > 0.40,
            margin > 0.20,
            margin > 0.10,
        ],
        [
            20.0,
            15.0,
            8.0,
        ],
        default=0.0,
    )

    roe = population["return_on_equity"]

    population["Quality ROE Points"] = np.select(
        [
            roe > 1.0,
            roe > 0.30,
            roe > 0.15,
            roe > 0,
        ],
        [
            20.0,
            18.0,
            12.0,
            5.0,
        ],
        default=0.0,
    )

    debt = population["debt_to_equity"]

    population["Quality Debt Points"] = np.select(
        [
            debt < 50,
            debt < 150,
        ],
        [
            10.0,
            5.0,
        ],
        default=0.0,
    )

    # The production FCF block currently awards points only inside
    # the "if free_cash_flow is None" branch, after assigning 0.
    # Consequently it contributes zero in production.
    population["Quality Free Cash Flow Points"] = 0.0

    # --------------------------------------------------------
    # RECONSTRUCT QUALITY TOTAL
    # --------------------------------------------------------

    quality_point_columns = [
        "Quality Revenue Growth Points",
        "Quality Earnings Growth Points",
        "Quality Profit Margin Points",
        "Quality ROE Points",
        "Quality Debt Points",
        "Quality Free Cash Flow Points",
    ]

    population["Reconstructed Quality Score"] = (
        population[quality_point_columns]
        .sum(axis=1)
        .clip(upper=100)
        .round(1)
    )

    population["Stored Quality Score"] = (
        population["quality_score"]
    )

    population["Quality Reconstruction Difference"] = (
        population["Stored Quality Score"]
        - population["Reconstructed Quality Score"]
    )

    # --------------------------------------------------------
    # ONLY MATURED SUB-75 OBSERVATIONS
    # --------------------------------------------------------

    failed = population[
        (
            population["investment_score"]
            < MIN_BUY_SCORE
        )
        & population["return_5d"].notna()
    ].copy()

    print(
        f"Matured sub-75 observations analysed: "
        f"{len(failed)}"
    )

    if failed.empty:
        print("No matured sub-75 observations found.")
        return pd.DataFrame()

    # --------------------------------------------------------
    # OUTCOME FLAGS
    # --------------------------------------------------------

    failed["Positive >0%"] = (
        failed["return_5d"] > 0
    )

    failed["Strong >=5%"] = (
        failed["return_5d"] >= 5
    )

    failed["Very Strong >=10%"] = (
        failed["return_5d"] >= 10
    )

    # --------------------------------------------------------
    # SCORE BANDS
    # --------------------------------------------------------

    failed["Production Score Band"] = pd.cut(
        failed["investment_score"],
        bins=[
            -np.inf,
            49.999,
            59.999,
            69.999,
            74.999,
        ],
        labels=[
            "<50",
            "50-59",
            "60-69",
            "70-74",
        ],
    )

    # --------------------------------------------------------
    # DISPLAY COMPONENT DIAGNOSTIC
    # --------------------------------------------------------

    print()
    print("SUB-75 QUALITY COMPONENT CONTRIBUTIONS")
    print("-" * 78)

    component_display = (
        failed[
            [
                "Quality Revenue Growth Points",
                "Quality Earnings Growth Points",
                "Quality Profit Margin Points",
                "Quality ROE Points",
                "Quality Debt Points",
                "Quality Free Cash Flow Points",
                "Stored Quality Score",
            ]
        ]
        .mean()
        .round(2)
    )

    print(
        component_display.to_string()
    )

    # --------------------------------------------------------
    # STRONG SUB-75 DIAGNOSTIC
    # --------------------------------------------------------

    strong = failed[
        failed["Strong >=5%"]
    ].copy()

    print()
    print("STRONG SUB-75 (>=5%) QUALITY COMPONENT CONTRIBUTIONS")
    print("-" * 78)

    if strong.empty:

        print(
            "No strong sub-75 observations."
        )

    else:

        print(
            f"Observations: {len(strong)}"
        )

        print()

        strong_components = (
            strong[
                [
                    "Quality Revenue Growth Points",
                    "Quality Earnings Growth Points",
                    "Quality Profit Margin Points",
                    "Quality ROE Points",
                    "Quality Debt Points",
                    "Quality Free Cash Flow Points",
                    "Stored Quality Score",
                ]
            ]
            .mean()
            .round(2)
        )

        print(
            strong_components.to_string()
        )

        print()

        print(
            "Average strong-sub-75 fundamentals:"
        )

        print(
            strong[
                [
                    "revenue_growth",
                    "profit_margin",
                    "return_on_equity",
                    "debt_to_equity",
                ]
            ]
            .mean()
            .round(4)
            .to_string()
        )

    # --------------------------------------------------------
    # VERY STRONG SUB-75 DIAGNOSTIC
    # --------------------------------------------------------

    very_strong = failed[
        failed["Very Strong >=10%"]
    ].copy()

    print()
    print("VERY STRONG SUB-75 (>=10%) QUALITY COMPONENT CONTRIBUTIONS")
    print("-" * 78)

    if very_strong.empty:

        print(
            "No very strong sub-75 observations."
        )

    else:

        print(
            f"Observations: {len(very_strong)}"
        )

        print()

        very_strong_components = (
            very_strong[
                [
                    "Quality Revenue Growth Points",
                    "Quality Earnings Growth Points",
                    "Quality Profit Margin Points",
                    "Quality ROE Points",
                    "Quality Debt Points",
                    "Quality Free Cash Flow Points",
                    "Stored Quality Score",
                ]
            ]
            .mean()
            .round(2)
        )

        print(
            very_strong_components.to_string()
        )

    # --------------------------------------------------------
    # PERIOD / SCORE-BAND SUMMARY
    # --------------------------------------------------------

    summary_rows = []

    for outcome_name, outcome_mask in [
        (
            "Positive >0%",
            failed["return_5d"] > 0,
        ),
        (
            "Strong >=5%",
            failed["return_5d"] >= 5,
        ),
        (
            "Very Strong >=10%",
            failed["return_5d"] >= 10,
        ),
    ]:

        cohort = failed[
            outcome_mask
        ].copy()

        if cohort.empty:
            continue

        for period in [
            "August Calibration",
            "September Holdout",
        ]:

            period_cohort = cohort[
                cohort["Analysis Period"]
                == period
            ].copy()

            if period_cohort.empty:
                continue

            for score_band in [
                "<50",
                "50-59",
                "60-69",
                "70-74",
            ]:

                band = period_cohort[
                    period_cohort["Production Score Band"]
                    == score_band
                ].copy()

                if band.empty:
                    continue

                summary_rows.append(
                    {
                        "Outcome Level": outcome_name,
                        "Analysis Period": period,
                        "Production Score Band": score_band,
                        "Observations": len(band),
                        "Avg Investment Score": round(
                            band["investment_score"].mean(),
                            2,
                        ),
                        "Avg Quality Score": round(
                            band["quality_score"].mean(),
                            2,
                        ),
                        "Avg Revenue Growth Points": round(
                            band[
                                "Quality Revenue Growth Points"
                            ].mean(),
                            2,
                        ),
                        "Avg Earnings Growth Points": round(
                            band[
                                "Quality Earnings Growth Points"
                            ].mean(),
                            2,
                        ),
                        "Avg Margin Points": round(
                            band[
                                "Quality Profit Margin Points"
                            ].mean(),
                            2,
                        ),
                        "Avg ROE Points": round(
                            band[
                                "Quality ROE Points"
                            ].mean(),
                            2,
                        ),
                        "Avg Debt Points": round(
                            band[
                                "Quality Debt Points"
                            ].mean(),
                            2,
                        ),
                        "Avg FCF Points": round(
                            band[
                                "Quality Free Cash Flow Points"
                            ].mean(),
                            2,
                        ),
                        "Avg 5D Return %": round(
                            band["return_5d"].mean(),
                            3,
                        ),
                        "Positive 5D %": round(
                            band["return_5d"].gt(0).mean()
                            * 100,
                            2,
                        ),
                    }
                )

    summary = pd.DataFrame(
        summary_rows
    )

    print()
    print("QUALITY COMPONENT SUMMARY BY PERIOD / SCORE BAND")
    print("-" * 78)

    if summary.empty:
        print("No cohort results found.")
    else:
        print(
            summary.to_string(
                index=False
            )
        )

    # --------------------------------------------------------
    # SAVE DETAILED OUTPUT
    # --------------------------------------------------------

    detail_columns = [
        "Analysis Period",
        "capture_date",
        "ticker",
        "recommendation_id",
        "investment_score",
        "technical_score",
        "quality_score",
        "growth_score",
        "return_5d",
        "Production Score Band",
        "revenue_growth",
        "profit_margin",
        "return_on_equity",
        "debt_to_equity",
        "Quality Revenue Growth Points",
        "Quality Earnings Growth Points",
        "Quality Profit Margin Points",
        "Quality ROE Points",
        "Quality Debt Points",
        "Quality Free Cash Flow Points",
        "Reconstructed Quality Score",
        "Stored Quality Score",
        "Quality Reconstruction Difference",
        "Positive >0%",
        "Strong >=5%",
        "Very Strong >=10%",
    ]

    detail = failed[
        detail_columns
    ].copy()

    detail.to_csv(
        OUTPUT_DIR
        / "final_quality_component_diagnostic.csv",
        index=False,
    )

    summary.to_csv(
        OUTPUT_DIR
        / "final_quality_component_summary.csv",
        index=False,
    )

    print()
    print(
        "Saved:"
    )
    print(
        OUTPUT_DIR
        / "final_quality_component_diagnostic.csv"
    )
    print(
        OUTPUT_DIR
        / "final_quality_component_summary.csv"
    )

    return detail

# ============================================================
# FINAL A6 TEST — QUALITY ARCHITECTURE
# ============================================================

def build_final_quality_architecture_test(
    calibration_evidence: pd.DataFrame,
    holdout_evidence: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    FINAL A6 TEST.

    Tests only targeted Quality architecture changes.

    Production Technical:
        unchanged

    Production Growth:
        unchanged

    Investment weights:
        Technical = 60.0%
        Quality   = 21.3%
        Growth    = 18.7%

    Investment threshold:
        75

    Variants:

    1. Production Baseline
       Existing production Quality score.

    2. Final Quality A — De-duplicated Absolute
       Removes Revenue Growth from Quality.
       Quality consists only of:
           - Profit Margin
           - ROE
           - Debt

       Revenue Growth remains exclusively in Growth.

       Each of the three dimensions is given an equal
       one-third contribution to a 100-point Quality score.

    3. Final Quality B — De-duplicated Percentile
       Same three Quality dimensions:
           - Profit Margin
           - ROE
           - Debt

       Each dimension is converted to a percentile using
       the August calibration population.

       September uses the frozen August reference.

    This is diagnostic only.

    It does NOT modify:
        - production scoring
        - scoring_weights.json
        - MIN_BUY_SCORE
        - recommendations
        - database
        - governance
    """

    print()
    print("=" * 78)
    print("FINAL A6 TEST — TARGETED QUALITY ARCHITECTURES")
    print("=" * 78)

    august = calibration_evidence.copy()
    september = holdout_evidence.copy()

    august["Analysis Period"] = "August Calibration"
    september["Analysis Period"] = "September Holdout"

    if august.empty or september.empty:
        print("ERROR: Both August calibration and September holdout are required.")
        return pd.DataFrame(), pd.DataFrame()

    population = pd.concat(
        [august, september],
        ignore_index=True,
    )

    numeric_fields = [
        "recommendation_id",
        "investment_score",
        "technical_score",
        "quality_score",
        "growth_score",
        "revenue_growth",
        "profit_margin",
        "return_on_equity",
        "debt_to_equity",
    ]

    for column in numeric_fields:
        if column in population.columns:
            population[column] = pd.to_numeric(
                population[column],
                errors="coerce",
            )

    # --------------------------------------------------------
    # AUTHORITATIVE 5D OUTCOMES
    # --------------------------------------------------------

    try:
        conn = sqlite3.connect(DB_PATH)

        outcomes = pd.read_sql_query(
            """
            SELECT
                recommendation_id,
                return_percent AS return_5d
            FROM recommendation_evaluations
            WHERE days_after = 5
            """,
            conn,
        )

        conn.close()

    except Exception as exc:
        print(
            "WARNING: Unable to load 5D outcomes: "
            f"{exc}"
        )
        return pd.DataFrame(), pd.DataFrame()

    if outcomes.empty:
        print("No 5D outcomes available.")
        return pd.DataFrame(), pd.DataFrame()

    outcomes["recommendation_id"] = pd.to_numeric(
        outcomes["recommendation_id"],
        errors="coerce",
    )

    outcomes["return_5d"] = pd.to_numeric(
        outcomes["return_5d"],
        errors="coerce",
    )

    population = population.merge(
        outcomes[
            [
                "recommendation_id",
                "return_5d",
            ]
        ],
        on="recommendation_id",
        how="left",
    )

    # ========================================================
    # 1. PRODUCTION BASELINE
    # ========================================================

    population["Production Quality"] = pd.to_numeric(
        population["quality_score"],
        errors="coerce",
    )

    population["Production Investment"] = pd.to_numeric(
        population["investment_score"],
        errors="coerce",
    )

    # ========================================================
    # 2. FINAL QUALITY A
    #
    # DE-DUPLICATED ABSOLUTE QUALITY
    #
    # Revenue Growth is deliberately removed from Quality.
    # Revenue Growth remains in the existing Growth component.
    #
    # Quality dimensions:
    #     Profit Margin
    #     ROE
    #     Debt
    #
    # Each receives one third of the 100-point Quality score.
    # ========================================================

    margin = population["profit_margin"]
    roe = population["return_on_equity"]
    debt = population["debt_to_equity"]

    # --------------------------------------------------------
    # Margin: production thresholds retained
    #
    # 0–10%       = 0
    # 10–20%      = 8
    # 20–40%      = 15
    # >40%        = 20
    #
    # Rescaled from 20 possible points to 33.33.
    # --------------------------------------------------------

    margin_points = np.select(
        [
            margin > 0.40,
            margin > 0.20,
            margin > 0.10,
        ],
        [
            33.333333,
            25.0,
            13.333333,
        ],
        default=0.0,
    )

    # --------------------------------------------------------
    # ROE: production thresholds retained
    #
    # >100%       = 20
    # >30%        = 18
    # >15%        = 12
    # >0%         = 5
    #
    # Rescaled from 20 possible points to 33.33.
    # --------------------------------------------------------

    roe_points = np.select(
        [
            roe > 1.0,
            roe > 0.30,
            roe > 0.15,
            roe > 0,
        ],
        [
            33.333333,
            30.0,
            20.0,
            8.333333,
        ],
        default=0.0,
    )

    # --------------------------------------------------------
    # Debt: lower is better
    #
    # <50         = 33.33
    # <150        = 16.67
    # >=150       = 0
    #
    # Rescaled from 10 possible points to 33.33.
    # --------------------------------------------------------

    debt_points = np.select(
        [
            debt < 50,
            debt < 150,
        ],
        [
            33.333333,
            16.666667,
        ],
        default=0.0,
    )

    population["Final Quality A"] = pd.Series(
        margin_points
        + roe_points
        + debt_points,
        index=population.index,
    ).clip(
        upper=100
    ).round(1)
    
    # ========================================================
    # 3. FINAL QUALITY B
    #
    # DE-DUPLICATED PERCENTILE QUALITY
    #
    # August is the calibration population.
    # September is scored against the frozen August
    # distributions.
    #
    # Higher margin = better
    # Higher ROE    = better
    # Lower debt   = better
    # ========================================================

    calibration_margin = pd.to_numeric(
        august["profit_margin"],
        errors="coerce",
    )

    calibration_roe = pd.to_numeric(
        august["return_on_equity"],
        errors="coerce",
    )

    calibration_debt = pd.to_numeric(
        august["debt_to_equity"],
        errors="coerce",
    )

    margin_percentile = percentile_score_against_reference(
        population["profit_margin"],
        calibration_margin,
    )

    roe_percentile = percentile_score_against_reference(
        population["return_on_equity"],
        calibration_roe,
    )

    debt_percentile = (
        100.0
        - percentile_score_against_reference(
            population["debt_to_equity"],
            calibration_debt,
        )
    )

    percentile_components = pd.concat(
        [
            margin_percentile.rename("margin"),
            roe_percentile.rename("roe"),
            debt_percentile.rename("debt"),
        ],
        axis=1,
    )

    population["Final Quality B"] = (
        percentile_components.mean(
            axis=1,
            skipna=True,
        )
        .where(
            percentile_components.notna().sum(axis=1) > 0
        )
        .round(1)
    )

    # ========================================================
    # INVESTMENT SCORE
    #
    # IMPORTANT:
    # Technical, Growth and weights are unchanged.
    # ========================================================

    technical = pd.to_numeric(
        population["technical_score"],
        errors="coerce",
    )

    growth = pd.to_numeric(
        population["growth_score"],
        errors="coerce",
    )

    population["Final Investment A"] = (
        technical * 0.600
        + population["Final Quality A"] * 0.213
        + growth * 0.187
    ).round(1)

    population["Final Investment B"] = (
        technical * 0.600
        + population["Final Quality B"] * 0.213
        + growth * 0.187
    ).round(1)

    # ========================================================
    # THRESHOLD FLAGS
    # ========================================================

    population["Production Meets 75"] = (
        population["Production Investment"] >= MIN_BUY_SCORE
    )

    population["Final A Meets 75"] = (
        population["Final Investment A"] >= MIN_BUY_SCORE
    )

    population["Final B Meets 75"] = (
        population["Final Investment B"] >= MIN_BUY_SCORE
    )

    # ========================================================
    # SCORE BANDS
    # ========================================================

    population["Production Score Band"] = pd.cut(
        population["Production Investment"],
        bins=[
            -np.inf,
            49.999,
            59.999,
            69.999,
            74.999,
            np.inf,
        ],
        labels=[
            "<50",
            "50-59",
            "60-69",
            "70-74",
            "75+",
        ],
    )

    # ========================================================
    # THRESHOLD MOVEMENT
    # ========================================================

    movement_rows = []

    for model_name, model_column, meets_column in [
        (
            "Final Quality A — De-duplicated Absolute",
            "Final Investment A",
            "Final A Meets 75",
        ),
        (
            "Final Quality B — De-duplicated Percentile",
            "Final Investment B",
            "Final B Meets 75",
        ),
    ]:

        production_meets = population["Production Meets 75"]
        model_meets = population[meets_column]

        movement_rows.append(
            {
                "Model": model_name,
                "Observations": len(population),
                "Production 75+": int(
                    production_meets.sum()
                ),
                "Model 75+": int(
                    model_meets.sum()
                ),
                "Moved Below 75 to 75+": int(
                    (
                        (~production_meets)
                        & model_meets
                    ).sum()
                ),
                "Moved 75+ to Below 75": int(
                    (
                        production_meets
                        & (~model_meets)
                    ).sum()
                ),
                "Threshold Status Changed": int(
                    (
                        production_meets
                        != model_meets
                    ).sum()
                ),
            }
        )

    threshold_movement = pd.DataFrame(
        movement_rows
    )

    # ========================================================
    # PERFORMANCE ANALYSIS
    # ========================================================

    performance_rows = []

    model_definitions = [
        (
            "Production Baseline",
            "Production Investment",
        ),
        (
            "Final Quality A — De-duplicated Absolute",
            "Final Investment A",
        ),
        (
            "Final Quality B — De-duplicated Percentile",
            "Final Investment B",
        ),
    ]

    for model_name, score_column in model_definitions:

        for population_name, population_mask in [
            (
                "ALL",
                population["return_5d"].notna(),
            ),
            (
                "75+",
                (
                    population[score_column] >= MIN_BUY_SCORE
                )
                & population["return_5d"].notna(),
            ),
            (
                "Promoted <75 to 75+",
                (
                    population["Production Investment"]
                    < MIN_BUY_SCORE
                )
                & (
                    population[score_column]
                    >= MIN_BUY_SCORE
                )
                & population["return_5d"].notna(),
            ),
        ]:

            cohort = population[
                population_mask
            ].copy()

            if cohort.empty:
                continue

            returns = cohort["return_5d"]

            performance_rows.append(
                {
                    "Model": model_name,
                    "Population": population_name,
                    "Observations": len(cohort),
                    "75+ Observations": int(
                        (
                            cohort[score_column]
                            >= MIN_BUY_SCORE
                        ).sum()
                    ),
                    "75+ %": round(
                        (
                            cohort[score_column]
                            >= MIN_BUY_SCORE
                        ).mean()
                        * 100,
                        2,
                    ),
                    "Average 5D Return %": round(
                        returns.mean(),
                        3,
                    ),
                    "Median 5D Return %": round(
                        returns.median(),
                        3,
                    ),
                    "Positive 5D %": round(
                        returns.gt(0).mean()
                        * 100,
                        2,
                    ),
                    "Strong >=5% %": round(
                        returns.ge(5).mean()
                        * 100,
                        2,
                    ),
                    "Very Strong >=10% %": round(
                        returns.ge(10).mean()
                        * 100,
                        2,
                    ),
                    "Score / Return Correlation": round(
                        cohort[
                            [
                                score_column,
                                "return_5d",
                            ]
                        ].corr().iloc[0, 1],
                        3,
                    ),
                }
            )

    performance = pd.DataFrame(
        performance_rows
    )

    # ========================================================
    # PROMOTED OBSERVATION ANALYSIS
    # ========================================================

    promoted_rows = []

    for model_name, score_column in [
        (
            "Final Quality A — De-duplicated Absolute",
            "Final Investment A",
        ),
        (
            "Final Quality B — De-duplicated Percentile",
            "Final Investment B",
        ),
    ]:

        promoted = population[
            (
                population["Production Investment"]
                < MIN_BUY_SCORE
            )
            & (
                population[score_column]
                >= MIN_BUY_SCORE
            )
            & population["return_5d"].notna()
        ].copy()

        if promoted.empty:
            continue

        returns = promoted["return_5d"]

        promoted_rows.append(
            {
                "Model": model_name,
                "Promoted": len(promoted),
                "Matured Promoted": len(promoted),
                "Average 5D Return %": round(
                    returns.mean(),
                    3,
                ),
                "Median 5D Return %": round(
                    returns.median(),
                    3,
                ),
                "Positive 5D %": round(
                    returns.gt(0).mean()
                    * 100,
                    2,
                ),
                "Strong >=5% %": round(
                    returns.ge(5).mean()
                    * 100,
                    2,
                ),
                "Very Strong >=10% %": round(
                    returns.ge(10).mean()
                    * 100,
                    2,
                ),
            }
        )

    promoted_performance = pd.DataFrame(
        promoted_rows
    )

    # ========================================================
    # SCORE DISTRIBUTION
    # ========================================================

    distribution_rows = []

    for model_name, quality_column, investment_column in [
        (
            "Production Baseline",
            "Production Quality",
            "Production Investment",
        ),
        (
            "Final Quality A — De-duplicated Absolute",
            "Final Quality A",
            "Final Investment A",
        ),
        (
            "Final Quality B — De-duplicated Percentile",
            "Final Quality B",
            "Final Investment B",
        ),
    ]:

        matured = population[
            population["return_5d"].notna()
        ].copy()

        distribution_rows.append(
            {
                "Model": model_name,
                "Observations": len(matured),
                "Mean Quality": round(
                    matured[quality_column].mean(),
                    2,
                ),
                "Mean Investment": round(
                    matured[investment_column].mean(),
                    2,
                ),
                "75+ Count": int(
                    (
                        matured[investment_column]
                        >= MIN_BUY_SCORE
                    ).sum()
                ),
                "75+ %": round(
                    (
                        matured[investment_column]
                        >= MIN_BUY_SCORE
                    ).mean()
                    * 100,
                    2,
                ),
                "Mean Technical": round(
                    technical.loc[matured.index].mean(),
                    2,
                ),
                "Mean Growth": round(
                    growth.loc[matured.index].mean(),
                    2,
                ),
            }
        )

    distribution = pd.DataFrame(
        distribution_rows
    )

    # ========================================================
    # PRINT RESULTS
    # ========================================================

    print()
    print("FINAL QUALITY ARCHITECTURES")
    print("-" * 78)

    print(
        population[
            [
                "Analysis Period",
                "Production Quality",
                "Final Quality A",
                "Final Quality B",
            ]
        ]
        .groupby("Analysis Period")
        .mean()
        .round(2)
        .to_string()
    )

    print()
    print("FINAL QUALITY SCORE DISTRIBUTION")
    print("-" * 78)
    print(
        distribution.to_string(
            index=False
        )
    )

    print()
    print("FINAL QUALITY THRESHOLD MOVEMENT")
    print("-" * 78)
    print(
        threshold_movement.to_string(
            index=False
        )
    )

    print()
    print("FINAL QUALITY PERFORMANCE")
    print("-" * 78)
    print(
        performance.to_string(
            index=False
        )
    )

    print()
    print("PROMOTED <75 → 75+ PERFORMANCE")
    print("-" * 78)

    if promoted_performance.empty:
        print("No promoted observations.")

    else:
        print(
            promoted_performance.to_string(
                index=False
            )
        )

    # ========================================================
    # SAVE OUTPUTS
    # ========================================================

    detail_columns = [
        "Analysis Period",
        "capture_date",
        "ticker",
        "recommendation_id",
        "Production Investment",
        "Production Quality",
        "technical_score",
        "growth_score",
        "Final Quality A",
        "Final Quality B",
        "Final Investment A",
        "Final Investment B",
        "Production Meets 75",
        "Final A Meets 75",
        "Final B Meets 75",
        "return_5d",
        "Production Score Band",
        "revenue_growth",
        "profit_margin",
        "return_on_equity",
        "debt_to_equity",
    ]

    detail = population[
        detail_columns
    ].copy()

    detail.to_csv(
        OUTPUT_DIR
        / "final_quality_architecture_detail.csv",
        index=False,
    )

    performance.to_csv(
        OUTPUT_DIR
        / "final_quality_architecture_performance.csv",
        index=False,
    )

    threshold_movement.to_csv(
        OUTPUT_DIR
        / "final_quality_architecture_threshold_movement.csv",
        index=False,
    )

    promoted_performance.to_csv(
        OUTPUT_DIR
        / "final_quality_architecture_promoted_performance.csv",
        index=False,
    )

    distribution.to_csv(
        OUTPUT_DIR
        / "final_quality_architecture_distribution.csv",
        index=False,
    )

    print()
    print("Saved:")
    print(
        OUTPUT_DIR
        / "final_quality_architecture_detail.csv"
    )
    print(
        OUTPUT_DIR
        / "final_quality_architecture_performance.csv"
    )
    print(
        OUTPUT_DIR
        / "final_quality_architecture_threshold_movement.csv"
    )
    print(
        OUTPUT_DIR
        / "final_quality_architecture_promoted_performance.csv"
    )
    print(
        OUTPUT_DIR
        / "final_quality_architecture_distribution.csv"
    )

    return detail, performance


# ============================================================
# STAGE 3 — FROZEN CALIBRATION NORMALISATION
# ============================================================

def percentile_score_against_reference(
    series: pd.Series,
    reference: pd.Series,
) -> pd.Series:
    """
    Convert a holdout series to percentile scores using a frozen
    calibration-period reference distribution.

    The holdout observations are NOT used to establish the
    percentile distribution.

    This is deliberately separate from percentile_score(), which
    remains unchanged for Stage 2.
    """

    numeric = pd.to_numeric(
        series,
        errors="coerce",
    )

    reference_numeric = pd.to_numeric(
        reference,
        errors="coerce",
    ).dropna()

    result = pd.Series(
        np.nan,
        index=series.index,
        dtype=float,
    )

    if reference_numeric.empty:
        return result

    sorted_reference = np.sort(
        reference_numeric.to_numpy()
    )

    valid = numeric.notna()

    if not valid.any():
        return result

    values = numeric.loc[valid].to_numpy()

    ranks = np.searchsorted(
        sorted_reference,
        values,
        side="right",
    )

    result.loc[valid] = (
        ranks / len(sorted_reference)
    ) * 100.0

    return result


def calculate_stage3_clean_components(
    calibration: pd.DataFrame,
    holdout: pd.DataFrame,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    Calculate frozen Stage 3 Quality and Growth components.

    Calibration-period distributions are used as the reference.

    Holdout observations never influence their own percentile
    normalisation.
    """

    # --------------------------------------------------------
    # TECHNICAL
    # --------------------------------------------------------

    technical = pd.to_numeric(
        holdout["technical_score"],
        errors="coerce",
    ).round(1)

    # --------------------------------------------------------
    # CALIBRATION REFERENCES
    # --------------------------------------------------------

    calibration_margin = pd.to_numeric(
        calibration["profit_margin"],
        errors="coerce",
    )

    calibration_roe = pd.to_numeric(
        calibration["return_on_equity"],
        errors="coerce",
    )

    calibration_debt = pd.to_numeric(
        calibration["debt_to_equity"],
        errors="coerce",
    )

    calibration_revenue = pd.to_numeric(
        calibration["revenue_growth"],
        errors="coerce",
    )

    # --------------------------------------------------------
    # HOLDOUT QUALITY
    # --------------------------------------------------------

    margin = percentile_score_against_reference(
        holdout["profit_margin"],
        calibration_margin,
    )

    roe = percentile_score_against_reference(
        holdout["return_on_equity"],
        calibration_roe,
    )

    debt = (
        100.0
        - percentile_score_against_reference(
            holdout["debt_to_equity"],
            calibration_debt,
        )
    )

    quality_components = pd.concat(
        [
            margin.rename("margin"),
            roe.rename("roe"),
            debt.rename("debt"),
        ],
        axis=1,
    )

    quality = quality_components.mean(
        axis=1,
        skipna=True,
    )

    quality = quality.where(
        quality_components.notna().sum(axis=1) > 0
    )

    # --------------------------------------------------------
    # HOLDOUT GROWTH
    # --------------------------------------------------------

    growth = percentile_score_against_reference(
        holdout["revenue_growth"],
        calibration_revenue,
    )

    return (
        technical,
        quality.round(1),
        growth.round(1),
    )


def build_stage3_frozen_model_results(
    calibration: pd.DataFrame,
    holdout: pd.DataFrame,
) -> pd.DataFrame:
    """
    Apply the frozen Stage 2 candidate architectures to the
    September holdout.

    The August calibration population defines all percentile
    reference distributions.

    No September observation is used to recalibrate the scores.
    """

    result = holdout.copy()

    (
        clean_technical,
        clean_quality,
        clean_growth,
    ) = calculate_stage3_clean_components(
        calibration,
        holdout,
    )

    result["Stage3 Technical"] = clean_technical
    result["Stage3 Clean Quality"] = clean_quality
    result["Stage3 Clean Growth"] = clean_growth

    # --------------------------------------------------------
    # MODEL A — CLEAN / EQUAL
    # --------------------------------------------------------

    result["Model A Investment Score"] = (
        pd.concat(
            [
                clean_technical.rename("technical"),
                clean_quality.rename("quality"),
                clean_growth.rename("growth"),
            ],
            axis=1,
        )
        .mean(
            axis=1,
            skipna=False,
        )
        .round(1)
    )

    # --------------------------------------------------------
    # MODEL B — CLEAN / PRODUCTION WEIGHTS
    # --------------------------------------------------------

    result["Model B Investment Score"] = (
        clean_technical * 0.600
        + clean_quality * 0.213
        + clean_growth * 0.187
    ).round(1)

    # --------------------------------------------------------
    # MODEL C — EXISTING COMPONENTS / BALANCED
    # --------------------------------------------------------

    production_components = pd.concat(
        [
            pd.to_numeric(
                result["technical_score"],
                errors="coerce",
            ).rename("technical"),

            pd.to_numeric(
                result["quality_score"],
                errors="coerce",
            ).rename("quality"),

            pd.to_numeric(
                result["growth_score"],
                errors="coerce",
            ).rename("growth"),
        ],
        axis=1,
    )

    result["Model C Investment Score"] = (
        production_components["technical"] * 0.50
        + production_components["quality"] * 0.25
        + production_components["growth"] * 0.25
    ).round(1)

    # --------------------------------------------------------
    # THRESHOLD FLAGS
    # --------------------------------------------------------

    result["Production Meets 75"] = (
        pd.to_numeric(
            result["investment_score"],
            errors="coerce",
        )
        >= MIN_BUY_SCORE
    )

    result["Model A Meets 75"] = (
        result["Model A Investment Score"]
        >= MIN_BUY_SCORE
    )

    result["Model B Meets 75"] = (
        result["Model B Investment Score"]
        >= MIN_BUY_SCORE
    )

    result["Model C Meets 75"] = (
        result["Model C Investment Score"]
        >= MIN_BUY_SCORE
    )

    return result

# ============================================================
# STAGE 3 — OUT-OF-SAMPLE ROBUSTNESS
# ============================================================

def build_stage3_holdout_performance(
    result: pd.DataFrame,
) -> pd.DataFrame:
    """
    Evaluate the frozen Stage 2 candidate architectures on a
    separate historical holdout period.

    The holdout observations are not used to select or tune the
    candidate architecture. They are used only to measure whether
    the Stage 2 findings generalise.

    Models:
        Production Baseline
        Model A — Clean / Equal
        Model B — Clean / Production Weights
        Model C — Existing Components / Balanced

    The production BUY threshold remains fixed at 75.

    Diagnostic only.

    This function does NOT:
        - change production scoring
        - change scoring weights
        - change MIN_BUY_SCORE
        - change recommendations
        - modify the database
    """

    working = result.copy()

    if "recommendation_id" not in working.columns:
        return pd.DataFrame()

    # --------------------------------------------------------
    # LOAD AUTHORITATIVE 5D OUTCOMES
    # --------------------------------------------------------

    conn = sqlite3.connect(DB_PATH)

    outcomes = pd.read_sql_query(
        """
        SELECT
            recommendation_id,
            return_percent AS return_5d
        FROM recommendation_evaluations
        WHERE days_after = 5
        """,
        conn,
    )

    conn.close()

    outcomes["recommendation_id"] = pd.to_numeric(
        outcomes["recommendation_id"],
        errors="coerce",
    )

    outcomes["return_5d"] = pd.to_numeric(
        outcomes["return_5d"],
        errors="coerce",
    )

    working["recommendation_id"] = pd.to_numeric(
        working["recommendation_id"],
        errors="coerce",
    )

    working = working.merge(
        outcomes[
            [
                "recommendation_id",
                "return_5d",
            ]
        ],
        on="recommendation_id",
        how="left",
    )

    matured = working[
        working["return_5d"].notna()
    ].copy()

    if matured.empty:
        return pd.DataFrame()

    models = {
        "Production Baseline": "investment_score",
        "Model A — Clean / Equal": (
            "Model A Investment Score"
        ),
        "Model B — Clean / Production Weights": (
            "Model B Investment Score"
        ),
        "Model C — Existing Components / Balanced": (
            "Model C Investment Score"
        ),
    }

    rows = []

    # --------------------------------------------------------
    # OVERALL HOLDOUT PERFORMANCE
    # --------------------------------------------------------

    for model_name, score_column in models.items():

        valid = matured[
            [
                score_column,
                "return_5d",
            ]
        ].dropna()

        if valid.empty:
            continue

        rows.append(
            {
                "Model": model_name,
                "Population": "ALL",
                "Observations": len(valid),
                "75+ Observations": int(
                    (
                        valid[score_column]
                        >= MIN_BUY_SCORE
                    ).sum()
                ),
                "75+ %": round(
                    (
                        valid[score_column]
                        >= MIN_BUY_SCORE
                    ).mean() * 100,
                    2,
                ),
                "Average 5D Return %": round(
                    valid["return_5d"].mean(),
                    3,
                ),
                "Median 5D Return %": round(
                    valid["return_5d"].median(),
                    3,
                ),
                "Positive 5D %": round(
                    valid["return_5d"].gt(0).mean()
                    * 100,
                    2,
                ),
                "Score / Return Correlation": round(
                    valid[score_column].corr(
                        valid["return_5d"]
                    ),
                    3,
                ),
            }
        )

        # ----------------------------------------------------
        # 75+ HOLDOUT PERFORMANCE
        # ----------------------------------------------------

        above_75 = valid[
            valid[score_column] >= MIN_BUY_SCORE
        ]

        if not above_75.empty:

            rows.append(
                {
                    "Model": model_name,
                    "Population": "75+",
                    "Observations": len(above_75),
                    "75+ Observations": len(above_75),
                    "75+ %": 100.0,
                    "Average 5D Return %": round(
                        above_75["return_5d"].mean(),
                        3,
                    ),
                    "Median 5D Return %": round(
                        above_75["return_5d"].median(),
                        3,
                    ),
                    "Positive 5D %": round(
                        above_75["return_5d"].gt(0).mean()
                        * 100,
                        2,
                    ),
                    "Score / Return Correlation": round(
                        above_75[score_column].corr(
                            above_75["return_5d"]
                        ),
                        3,
                    )
                    if len(above_75) >= 3
                    else None,
                }
            )

    performance = pd.DataFrame(rows)

    print()
    print("=" * 78)
    print("STAGE 3 — OUT-OF-SAMPLE HOLDOUT PERFORMANCE")
    print("=" * 78)
    print(
        f"Matured 5D holdout observations: "
        f"{len(matured)}"
    )

    print()
    print(
        performance.to_string(
            index=False
        )
    )

    return performance


def build_stage3_threshold_movement(
    result: pd.DataFrame,
) -> pd.DataFrame:
    """
    Measure threshold movement on the out-of-sample holdout.

    The 75 threshold is deliberately frozen.

    This identifies:
        - observations newly promoted to 75+
        - observations demoted from 75+
        - total threshold changes

    Diagnostic only.
    """

    working = result.copy()

    production_score = pd.to_numeric(
        working["investment_score"],
        errors="coerce",
    )

    working["Production Status"] = np.where(
        production_score >= MIN_BUY_SCORE,
        "75+",
        "<75",
    )

    models = {
        "Model A — Clean / Equal": (
            "Model A Investment Score"
        ),
        "Model B — Clean / Production Weights": (
            "Model B Investment Score"
        ),
        "Model C — Existing Components / Balanced": (
            "Model C Investment Score"
        ),
    }

    rows = []

    for model_name, score_column in models.items():

        model_score = pd.to_numeric(
            working[score_column],
            errors="coerce",
        )

        model_status = np.where(
            model_score >= MIN_BUY_SCORE,
            "75+",
            "<75",
        )

        promoted = (
            (working["Production Status"] == "<75")
            & (model_status == "75+")
        )

        demoted = (
            (working["Production Status"] == "75+")
            & (model_status == "<75")
        )

        rows.append(
            {
                "Model": model_name,
                "Observations": len(working),
                "Production 75+": int(
                    (
                        production_score
                        >= MIN_BUY_SCORE
                    ).sum()
                ),
                "Model 75+": int(
                    (
                        model_score
                        >= MIN_BUY_SCORE
                    ).sum()
                ),
                "Moved Below 75 to 75+": int(
                    promoted.sum()
                ),
                "Moved 75+ to Below 75": int(
                    demoted.sum()
                ),
                "Threshold Status Changed": int(
                    (promoted | demoted).sum()
                ),
            }
        )

    movement = pd.DataFrame(rows)

    print()
    print("=" * 78)
    print("STAGE 3 — OUT-OF-SAMPLE THRESHOLD MOVEMENT")
    print("=" * 78)

    print(
        movement.to_string(
            index=False
        )
    )

    return movement


def build_stage3_promoted_observation_performance(
    result: pd.DataFrame,
) -> pd.DataFrame:
    """
    Measure realised 5D performance specifically for observations
    promoted from below 75 to 75+ by each candidate model.

    This is the key test of whether the additional threshold
    coverage represents useful candidates rather than merely
    score inflation.
    """

    working = result.copy()

    conn = sqlite3.connect(DB_PATH)

    outcomes = pd.read_sql_query(
        """
        SELECT
            recommendation_id,
            return_percent AS return_5d
        FROM recommendation_evaluations
        WHERE days_after = 5
        """,
        conn,
    )

    conn.close()

    outcomes["recommendation_id"] = pd.to_numeric(
        outcomes["recommendation_id"],
        errors="coerce",
    )

    outcomes["return_5d"] = pd.to_numeric(
        outcomes["return_5d"],
        errors="coerce",
    )

    working["recommendation_id"] = pd.to_numeric(
        working["recommendation_id"],
        errors="coerce",
    )

    working = working.merge(
        outcomes[
            [
                "recommendation_id",
                "return_5d",
            ]
        ],
        on="recommendation_id",
        how="left",
    )

    production_score = pd.to_numeric(
        working["investment_score"],
        errors="coerce",
    )

    working["Production Status"] = np.where(
        production_score >= MIN_BUY_SCORE,
        "75+",
        "<75",
    )

    models = {
        "Model A — Clean / Equal": (
            "Model A Investment Score"
        ),
        "Model B — Clean / Production Weights": (
            "Model B Investment Score"
        ),
        "Model C — Existing Components / Balanced": (
            "Model C Investment Score"
        ),
    }

    rows = []

    for model_name, score_column in models.items():

        model_score = pd.to_numeric(
            working[score_column],
            errors="coerce",
        )

        promoted = working[
            (working["Production Status"] == "<75")
            & (model_score >= MIN_BUY_SCORE)
        ].copy()

        matured = promoted[
            promoted["return_5d"].notna()
        ]

        if matured.empty:
            rows.append(
                {
                    "Model": model_name,
                    "Promoted Observations": len(promoted),
                    "Matured Promoted": 0,
                    "Average 5D Return %": None,
                    "Median 5D Return %": None,
                    "Positive 5D %": None,
                }
            )
            continue

        rows.append(
            {
                "Model": model_name,
                "Promoted Observations": len(promoted),
                "Matured Promoted": len(matured),
                "Average 5D Return %": round(
                    matured["return_5d"].mean(),
                    3,
                ),
                "Median 5D Return %": round(
                    matured["return_5d"].median(),
                    3,
                ),
                "Positive 5D %": round(
                    matured["return_5d"].gt(0).mean()
                    * 100,
                    2,
                ),
            }
        )

    promoted_performance = pd.DataFrame(rows)

    print()
    print("=" * 78)
    print("STAGE 3 — PROMOTED OBSERVATION PERFORMANCE")
    print("=" * 78)

    print(
        promoted_performance.to_string(
            index=False
        )
    )

    return promoted_performance


def run_stage3_holdout(
    calibration_evidence: pd.DataFrame,
    holdout_evidence: pd.DataFrame,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
]:
    """
    Execute Stage 3 out-of-sample robustness testing.

    August is the calibration/reference period.

    September is the independent holdout.

    The candidate architectures and 75 threshold are frozen.
    Percentile normalisation is also frozen using August data.
    """

    result = build_stage3_frozen_model_results(
        calibration_evidence,
        holdout_evidence,
    )

    performance = build_stage3_holdout_performance(
        result
    )

    threshold_movement = build_stage3_threshold_movement(
        result
    )

    promoted_performance = (
        build_stage3_promoted_observation_performance(
            result
        )
    )

    return (
        result,
        performance,
        threshold_movement,
        promoted_performance,
    )

# ============================================================
# MAIN
# ============================================================

def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "Test V2 Technical / Quality / Growth "
            "scoring architecture."
        )
    )

    parser.add_argument(
        "--start-date",
        required=True,
    )

    parser.add_argument(
        "--end-date",
        required=True,
    )

    parser.add_argument(
        "--holdout-start-date",
        required=False,
        default=None,
    )

    parser.add_argument(
        "--holdout-end-date",
        required=False,
        default=None,
    )

    args = parser.parse_args()

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # --------------------------------------------------------
    # LOAD POINT-IN-TIME AUGUST EVIDENCE
    # --------------------------------------------------------

    evidence = load_evidence(
        args.start_date,
        args.end_date,
    )

    evidence = convert_numeric_fields(
        evidence
    )

    print()
    print(
        f"Loaded {len(evidence)} "
        "point-in-time recommendation observations."
    )

    # --------------------------------------------------------
    # BUILD V2 HISTORICAL SCORE
    # --------------------------------------------------------

    result = build_v2_results(
        evidence
    )

    # --------------------------------------------------------
    # STAGE 2 — CANDIDATE SCORING ARCHITECTURES
    # --------------------------------------------------------

    (
        stage2_result,
        stage2_performance,
        stage2_threshold_movement,
        stage2_known_winners,
    ) = run_stage2_calibration(
        evidence
    )

    # --------------------------------------------------------
    # STAGE 3 — OUT-OF-SAMPLE HOLDOUT
    # --------------------------------------------------------

    stage3_result = pd.DataFrame()
    stage3_performance = pd.DataFrame()
    stage3_threshold_movement = pd.DataFrame()
    stage3_promoted_performance = pd.DataFrame()

    if (
        args.holdout_start_date
        and args.holdout_end_date
    ):

        print()
        print("=" * 78)
        print("STAGE 3 — LOADING OUT-OF-SAMPLE HOLDOUT")
        print("=" * 78)

        holdout_evidence = load_evidence(
            args.holdout_start_date,
            args.holdout_end_date,
        )

        holdout_evidence = convert_numeric_fields(
            holdout_evidence
        )

        print(
            f"Loaded {len(holdout_evidence)} "
            "point-in-time holdout observations."
        )

        (
            stage3_result,
            stage3_performance,
            stage3_threshold_movement,
            stage3_promoted_performance,
        ) = run_stage3_holdout(
            evidence,
            holdout_evidence,
        )

    # --------------------------------------------------------
    # FINAL A6 — FAILURE-CASE ANALYSIS
    # --------------------------------------------------------

    (
        failure_case_detail,
        failure_case_summary,
    ) = build_failure_case_analysis(
        evidence,
        holdout_evidence
        if (
            args.holdout_start_date
            and args.holdout_end_date
        )
        else pd.DataFrame(),
    )

    # --------------------------------------------------------
    # FINAL QUALITY COMPONENT DIAGNOSTIC
    # --------------------------------------------------------

    quality_component_diagnostic = (
        build_quality_component_diagnostic(
            evidence,
            holdout_evidence
            if (
                args.holdout_start_date
                and args.holdout_end_date
            )
            else pd.DataFrame(),
        )
    )

    # --------------------------------------------------------
    # FINAL QUALITY ARCHITECTURE TEST
    # --------------------------------------------------------

    (
        final_quality_detail,
        final_quality_performance,
    ) = build_final_quality_architecture_test(
        evidence,
        holdout_evidence
        if (
            args.holdout_start_date
            and args.holdout_end_date
        )
        else pd.DataFrame(),
    )

    # --------------------------------------------------------
    # REALISED PERFORMANCE COMPARISON
    # --------------------------------------------------------

    realised_performance = (
        build_realised_performance_comparison(
            result
        )
    )

    component_performance = (
        build_component_performance_analysis(evidence)
    )

    summary = build_v2_summary(
        result
    )

    bands = build_score_band_analysis(
        result
    )

    winners = build_known_winner_check(
        result
    )

    # --------------------------------------------------------
    # PRODUCTION INPUT CORRELATIONS
    # --------------------------------------------------------

    production_fields = [
        "rsi",
        "sma50",
        "sma200",
        "return_3m",
        "trend_score",
        "momentum_score",
        "volume_score",
        "risk_score",
        "profit_margin",
        "return_on_equity",
        "debt_to_equity",
        "revenue_growth",
    ]

    production_correlations = (
        build_correlation_analysis(
            evidence,
            production_fields,
        )
    )

    # --------------------------------------------------------
    # CURRENT YAHOO AVAILABILITY
    # --------------------------------------------------------

    tickers = sorted(
        evidence["ticker"]
        .dropna()
        .astype(str)
        .str.upper()
        .unique()
        .tolist()
    )

    yahoo_df = retrieve_current_yahoo_fields(
        tickers
    )

    yahoo_inventory = build_yahoo_inventory(
        yahoo_df
    )

    yahoo_correlations = (
        build_correlation_analysis(
            yahoo_df,
            list(YAHOO_FIELDS.keys()),
        )
    )

    # --------------------------------------------------------
    # SAVE OUTPUT
    # --------------------------------------------------------

    result.to_csv(
        OUTPUT_DIR
        / "fundamental_v2_observations.csv",
        index=False,
    )

    failure_case_detail.to_csv(
        OUTPUT_DIR
        / "final_failure_case_detail.csv",
        index=False,
    )

    failure_case_summary.to_csv(
        OUTPUT_DIR
        / "final_failure_case_summary.csv",
        index=False,
    )

    realised_performance.to_csv(
        OUTPUT_DIR
        / "fundamental_v2_realised_performance.csv",
        index=False,
    )

    stage2_result.to_csv(
        OUTPUT_DIR
        / "stage2_candidate_model_observations.csv",
        index=False,
    )

    stage2_performance.to_csv(
        OUTPUT_DIR
        / "stage2_candidate_model_performance.csv",
        index=False,
    )

    stage2_threshold_movement.to_csv(
        OUTPUT_DIR
        / "stage2_threshold_movement.csv",
        index=False,
    )

    stage2_known_winners.to_csv(
        OUTPUT_DIR
        / "stage2_known_winners.csv",
        index=False,
    )

    if not stage3_result.empty:

        stage3_result.to_csv(
            OUTPUT_DIR
            / "stage3_holdout_observations.csv",
            index=False,
        )

        stage3_performance.to_csv(
            OUTPUT_DIR
            / "stage3_holdout_performance.csv",
            index=False,
        )

        stage3_threshold_movement.to_csv(
            OUTPUT_DIR
            / "stage3_threshold_movement.csv",
            index=False,
        )

        stage3_promoted_performance.to_csv(
            OUTPUT_DIR
            / "stage3_promoted_performance.csv",
            index=False,
        )

    if component_performance:
        (
            component_summary,
            component_bands,
        ) = component_performance

        component_summary.to_csv(
            OUTPUT_DIR
            / "fundamental_component_performance.csv",
            index=False,
        )

        component_bands.to_csv(
            OUTPUT_DIR
            / "fundamental_component_quartiles.csv",
            index=False,
        )

    summary.to_csv(
        OUTPUT_DIR
        / "fundamental_v2_summary.csv",
        index=False,
    )

    bands.to_csv(
        OUTPUT_DIR
        / "fundamental_v2_score_bands.csv",
        index=False,
    )

    winners.to_csv(
        OUTPUT_DIR
        / "fundamental_v2_known_winners.csv",
        index=False,
    )

    production_correlations.to_csv(
        OUTPUT_DIR
        / "fundamental_v2_production_correlations.csv",
        index=False,
    )

    yahoo_inventory.to_csv(
        OUTPUT_DIR
        / "fundamental_v2_yahoo_availability.csv",
        index=False,
    )

    yahoo_correlations.to_csv(
        OUTPUT_DIR
        / "fundamental_v2_yahoo_correlations.csv",
        index=False,
    )

    # --------------------------------------------------------
    # PRINT RESULTS
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("V2 SUMMARY")
    print("=" * 70)

    print(
        summary.to_string(
            index=False
        )
    )

    print()
    print("=" * 70)
    print("V2 SCORE BANDS")
    print("=" * 70)

    print(
        bands.to_string(
            index=False
        )
    )

    print()
    print("=" * 70)
    print("KNOWN AUGUST WINNERS")
    print("=" * 70)

    if winners.empty:

        print(
            "No known winner tickers found."
        )

    else:

        print(
            winners.to_string(
                index=False
            )
        )

    print()
    print("=" * 70)
    print("TOP PRODUCTION INPUT CORRELATIONS")
    print("=" * 70)

    print(
        production_correlations.head(20).to_string(
            index=False
        )
    )

    print()
    print("=" * 70)
    print("CURRENT YAHOO FIELD AVAILABILITY")
    print("=" * 70)

    print(
        yahoo_inventory.to_string(
            index=False
        )
    )

    print()
    print("=" * 70)
    print("TOP CURRENT YAHOO FIELD CORRELATIONS")
    print("=" * 70)

    print(
        yahoo_correlations.head(20).to_string(
            index=False
        )
    )

    print()
    print("=" * 70)
    print("STAGE 2 — THRESHOLD MOVEMENT")
    print("=" * 70)

    print(
        stage2_threshold_movement.to_string(
            index=False
        )
    )

    print()
    print("=" * 70)
    print("STAGE 2 — KNOWN AUGUST WINNERS")
    print("=" * 70)

    if stage2_known_winners.empty:
        print(
            "No known winner tickers found."
        )
    else:
        print(
            stage2_known_winners.to_string(
                index=False
            )
        )

    print()
    print("=" * 70)
    print("STAGE 2 COMPLETE")
    print("=" * 70)

    print(
        "No production scoring, weights, thresholds, "
        "recommendations or database records were modified."
    )


    print()
    if not stage3_result.empty:

        print()
        print("=" * 70)
        print("STAGE 3 COMPLETE")
        print("=" * 70)

        print(
            "Stage 3 used a separate historical holdout period."
        )

        print(
            "The Stage 2 candidate architectures, "
            "75 threshold and production weights were frozen."
        )

        print(
            "No production scoring, weights, thresholds, "
            "recommendations or database records were modified."
        )

    print(
        "V2 calibration complete."
    )

    print(
        "Historical V2 scoring used only point-in-time "
        "recommendation evidence."
    )

    print(
        "Current Yahoo values were used only for "
        "availability/correlation diagnostics."
    )


if __name__ == "__main__":
    main()