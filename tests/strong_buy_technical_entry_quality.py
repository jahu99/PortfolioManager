"""
STRONG BUY Growth Score Formula / Component Trace

READ-ONLY FORENSIC TEST.

Purpose
-------
Trace the relationship between the persisted fundamental inputs and
the resulting Growth Score within the mature STRONG BUY population.

This test does NOT change production logic.

It deliberately does not assume that the Growth Score is a simple
average of the persisted fundamentals. Instead it:

1. Loads the mature STRONG BUY population.
2. Examines the persisted Growth Score and fundamental inputs.
3. Identifies the production growth-component fields available in
   recommendation_evidence.
4. Tests whether Growth Score appears to be monotonic with each
   underlying fundamental.
5. Compares high/low component populations.
6. Tests whether the persisted fundamentals can explain the
   Growth Score ordering.
7. Prints the Growth Reasons / Growth Risks distributions where
   available in the persisted evidence.
8. Performs a consistency check between the Growth Score and the
   component inputs.

IMPORTANT
---------
This is forensic analysis only.

No thresholds, weights, production functions, database rows,
recommendations, signals, or governance rules are changed.
"""

import ast
import json
import sqlite3

import numpy as np
import pandas as pd


DB_PATH = "data/portfolio_manager.db"


# ============================================================
# LOAD DATA
# ============================================================

def load_data():
    conn = sqlite3.connect(DB_PATH)

    evidence = pd.read_sql_query(
        """
        SELECT
            recommendation_id,
            ticker,
            capture_date,
            signal,
            growth_score,
            revenue_growth,
            profit_margin,
            return_on_equity,
            debt_to_equity,
            technical_score,
            quality_score,
            investment_score,
            confidence_score,
            entry_price,
            rsi,
            sma200,
            entry_quality,
            recommendation_reasons,
            recommendation_risks,
            technical_reasons,
            technical_risks
        FROM recommendation_evidence
        WHERE signal = 'STRONG BUY'
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

    return evidence, evaluations


# ============================================================
# PREPARE DATA
# ============================================================

def prepare_data(
    evidence,
    evaluations,
):
    df = evidence.merge(
        evaluations,
        on=[
            "recommendation_id",
            "ticker",
        ],
        how="inner",
    )

    numeric_columns = [
        "growth_score",
        "revenue_growth",
        "profit_margin",
        "return_on_equity",
        "debt_to_equity",
        "technical_score",
        "quality_score",
        "investment_score",
        "confidence_score",
        "entry_price",
        "rsi",
        "sma200",
        "return_percent",
    ]

    for column in numeric_columns:
        if column in df.columns:
            df[column] = pd.to_numeric(
                df[column],
                errors="coerce",
            )

    required = [
        "growth_score",
        "revenue_growth",
        "profit_margin",
        "return_on_equity",
        "debt_to_equity",
        "return_percent",
    ]

    df = df.dropna(
        subset=required
    ).copy()

    return df


# ============================================================
# SAFE PARSING HELPERS
# ============================================================

def parse_list(value):
    """
    Convert persisted list-like evidence into a Python list.

    Handles:
        - actual lists
        - JSON strings
        - Python repr strings
        - empty values
    """

    if value is None:
        return []

    if isinstance(
        value,
        list,
    ):
        return value

    text = str(value).strip()

    if not text:
        return []

    try:
        parsed = json.loads(text)

        if isinstance(
            parsed,
            list,
        ):
            return parsed

    except Exception:
        pass

    try:
        parsed = ast.literal_eval(text)

        if isinstance(
            parsed,
            list,
        ):
            return parsed

    except Exception:
        pass

    return [text]


# ============================================================
# BASIC POPULATION
# ============================================================

def print_population(df):
    print()
    print(
        "STRONG BUY GROWTH SCORE FORMULA TRACE"
    )
    print(
        "=" * 90
    )

    print()
    print(
        f"Total mature STRONG BUY observations: "
        f"{len(df)}"
    )

    print()
    print(
        f"Growth Score mean: "
        f"{df['growth_score'].mean():.3f}"
    )

    print(
        f"Growth Score median: "
        f"{df['growth_score'].median():.3f}"
    )

    print(
        f"Growth Score min: "
        f"{df['growth_score'].min():.3f}"
    )

    print(
        f"Growth Score max: "
        f"{df['growth_score'].max():.3f}"
    )


# ============================================================
# COMPONENT SUMMARY
# ============================================================

def component_summary(df):
    print()
    print(
        "RAW FUNDAMENTAL INPUT SUMMARY"
    )
    print(
        "=" * 90
    )

    components = [
        "revenue_growth",
        "profit_margin",
        "return_on_equity",
        "debt_to_equity",
    ]

    print()
    print(
        f"{'Component':<24}"
        f"{'Mean':>14}"
        f"{'Median':>14}"
        f"{'Min':>14}"
        f"{'Max':>14}"
    )

    print(
        "-" * 90
    )

    for component in components:

        series = df[
            component
        ].dropna()

        print(
            f"{component:<24}"
            f"{series.mean():>14.3f}"
            f"{series.median():>14.3f}"
            f"{series.min():>14.3f}"
            f"{series.max():>14.3f}"
        )


# ============================================================
# COMPONENT / GROWTH SCORE CORRELATION
# ============================================================

def component_growth_correlations(df):
    print()
    print(
        "COMPONENT vs GROWTH SCORE"
    )
    print(
        "=" * 90
    )

    components = [
        "revenue_growth",
        "profit_margin",
        "return_on_equity",
        "debt_to_equity",
    ]

    rows = []

    print()
    print(
        f"{'Component':<24}"
        f"{'N':>8}"
        f"{'Correlation':>16}"
        f"{'Direction':>16}"
    )

    print(
        "-" * 70
    )

    for component in components:

        subset = df[
            [
                component,
                "growth_score",
            ]
        ].dropna()

        correlation = subset[
            component
        ].corr(
            subset["growth_score"]
        )

        direction = (
            "POSITIVE"
            if correlation > 0
            else "NEGATIVE"
            if correlation < 0
            else "FLAT"
        )

        rows.append(
            {
                "component": component,
                "n": len(subset),
                "correlation": correlation,
                "direction": direction,
            }
        )

        print(
            f"{component:<24}"
            f"{len(subset):>8}"
            f"{correlation:>15.3f}"
            f"{direction:>16}"
        )

    return pd.DataFrame(rows)


# ============================================================
# GROWTH SCORE ORDERING TEST
# ============================================================

def growth_score_ordering_test(df):
    print()
    print(
        "GROWTH SCORE ORDERING TEST"
    )
    print(
        "=" * 90
    )

    """
    Divide the population into quartiles by Growth Score and
    inspect the underlying fundamentals.

    If the production Growth Score is meaningfully driven by a
    component, we should normally see some corresponding
    separation in that component across score quartiles.
    """

    df = df.copy()

    try:
        df["growth_quartile"] = pd.qcut(
            df["growth_score"],
            q=4,
            duplicates="drop",
        )
    except Exception as exc:
        print(
            "Unable to construct Growth Score quartiles:",
            exc,
        )
        return pd.DataFrame()

    components = [
        "revenue_growth",
        "profit_margin",
        "return_on_equity",
        "debt_to_equity",
    ]

    grouped = (
        df.groupby(
            "growth_quartile",
            observed=True,
        )[components]
        .mean()
    )

    print()
    print(
        grouped.to_string()
    )

    return grouped


# ============================================================
# EXTREME SCORE COMPARISON
# ============================================================

def extreme_score_comparison(df):
    print()
    print(
        "EXTREME GROWTH SCORE COMPARISON"
    )
    print(
        "=" * 90
    )

    low = df[
        df["growth_score"] <= 80
    ].copy()

    high = df[
        df["growth_score"] >= 95
    ].copy()

    print()
    print(
        f"Growth Score <=80: N={len(low)}"
    )

    print(
        f"Growth Score >=95: N={len(high)}"
    )

    if (
        low.empty
        or high.empty
    ):
        print(
            "Insufficient observations for extreme comparison."
        )
        return pd.DataFrame()

    components = [
        "revenue_growth",
        "profit_margin",
        "return_on_equity",
        "debt_to_equity",
    ]

    rows = []

    print()
    print(
        f"{'Component':<24}"
        f"{'<=80':>14}"
        f"{'>=95':>14}"
        f"{'Difference':>16}"
    )

    print(
        "-" * 75
    )

    for component in components:

        low_mean = (
            low[component]
            .dropna()
            .mean()
        )

        high_mean = (
            high[component]
            .dropna()
            .mean()
        )

        difference = (
            high_mean
            - low_mean
        )

        rows.append(
            {
                "component": component,
                "score_80_or_less": low_mean,
                "score_95_plus": high_mean,
                "difference": difference,
            }
        )

        print(
            f"{component:<24}"
            f"{low_mean:>13.3f}"
            f"{high_mean:>13.3f}"
            f"{difference:>15.3f}"
        )

    return pd.DataFrame(rows)


# ============================================================
# MONOTONICITY TEST
# ============================================================

def monotonicity_test(df):
    print()
    print(
        "COMPONENT MONOTONICITY TEST"
    )
    print(
        "=" * 90
    )

    print(
        "Tests whether higher raw component values correspond"
    )
    print(
        "to higher Growth Scores within the STRONG BUY population."
    )

    components = [
        "revenue_growth",
        "profit_margin",
        "return_on_equity",
        "debt_to_equity",
    ]

    rows = []

    for component in components:

        subset = df[
            [
                component,
                "growth_score",
            ]
        ].dropna()

        correlation = subset[
            component
        ].corr(
            subset["growth_score"]
        )

        rows.append(
            {
                "component": component,
                "correlation": correlation,
                "monotonic_direction": (
                    "HIGHER RAW VALUE → HIGHER SCORE"
                    if correlation > 0
                    else "HIGHER RAW VALUE → LOWER SCORE"
                    if correlation < 0
                    else "NO CLEAR RELATIONSHIP"
                ),
            }
        )

    result = pd.DataFrame(
        rows
    )

    print()
    print(
        result.to_string(
            index=False
        )
    )

    return result


# ============================================================
# REASON / RISK DISTRIBUTION
# ============================================================

def analyse_persisted_reasons(df):
    print()
    print(
        "PERSISTED GROWTH-RELATED EVIDENCE"
    )
    print(
        "=" * 90
    )

    reason_columns = [
        "recommendation_reasons",
        "recommendation_risks",
        "technical_reasons",
        "technical_risks",
    ]

    for column in reason_columns:

        if column not in df.columns:
            continue

        counts = {}

        for value in df[column]:

            for item in parse_list(value):

                text = str(
                    item
                ).strip()

                if not text:
                    continue

                counts[text] = (
                    counts.get(
                        text,
                        0,
                    )
                    + 1
                )

        if not counts:
            continue

        print()
        print(
            column.upper()
        )
        print(
            "-" * 70
        )

        for text, count in sorted(
            counts.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:20]:

            print(
                f"{count:>4}  {text}"
            )


# ============================================================
# GROWTH SCORE / 5D PERFORMANCE
# ============================================================

def growth_score_performance(df):
    print()
    print(
        "GROWTH SCORE vs REALISED 5D RETURN"
    )
    print(
        "=" * 90
    )

    correlation = df[
        "growth_score"
    ].corr(
        df["return_percent"]
    )

    print()
    print(
        f"Correlation: {correlation:.3f}"
    )

    bands = [
        (
            "<80",
            df["growth_score"] < 80,
        ),
        (
            "80-89",
            (
                (df["growth_score"] >= 80)
                & (df["growth_score"] < 90)
            ),
        ),
        (
            "90-94",
            (
                (df["growth_score"] >= 90)
                & (df["growth_score"] < 95)
            ),
        ),
        (
            "95+",
            df["growth_score"] >= 95,
        ),
    ]

    print()
    print(
        f"{'Band':<12}"
        f"{'N':>8}"
        f"{'Mean 5D':>14}"
        f"{'Median 5D':>16}"
        f"{'Positive %':>14}"
    )

    print(
        "-" * 70
    )

    rows = []

    for label, mask in bands:

        subset = df[
            mask
        ]

        if subset.empty:
            continue

        mean_return = subset[
            "return_percent"
        ].mean()

        median_return = subset[
            "return_percent"
        ].median()

        positive = (
            subset[
                "return_percent"
            ] > 0
        ).mean() * 100

        rows.append(
            {
                "band": label,
                "n": len(subset),
                "mean_5d": mean_return,
                "median_5d": median_return,
                "positive_percent": positive,
            }
        )

        print(
            f"{label:<12}"
            f"{len(subset):>8}"
            f"{mean_return:>13.3f}"
            f"{median_return:>15.3f}"
            f"{positive:>13.2f}%"
        )

    return pd.DataFrame(
        rows
    )


# ============================================================
# MAIN
# ============================================================

def main():

    evidence, evaluations = (
        load_data()
    )

    df = prepare_data(
        evidence,
        evaluations,
    )

    print_population(
        df
    )

    component_summary(
        df
    )

    correlation_results = (
        component_growth_correlations(
            df
        )
    )

    quartile_results = (
        growth_score_ordering_test(
            df
        )
    )

    extreme_results = (
        extreme_score_comparison(
            df
        )
    )

    monotonicity_results = (
        monotonicity_test(
            df
        )
    )

    analyse_persisted_reasons(
        df
    )

    performance_results = (
        growth_score_performance(
            df
        )
    )

    print()
    print(
        "SUMMARY DATAFRAMES"
    )
    print(
        "=" * 90
    )

    print()
    print(
        "COMPONENT / GROWTH SCORE CORRELATIONS"
    )

    print(
        correlation_results.to_string(
            index=False
        )
    )

    print()
    print(
        "GROWTH SCORE QUARTILE COMPONENTS"
    )

    print(
        quartile_results.to_string()
    )

    print()
    print(
        "EXTREME SCORE COMPONENT COMPARISON"
    )

    print(
        extreme_results.to_string(
            index=False
        )
    )

    print()
    print(
        "MONOTONICITY RESULTS"
    )

    print(
        monotonicity_results.to_string(
            index=False
        )
    )

    print()
    print(
        "GROWTH SCORE PERFORMANCE"
    )

    print(
        performance_results.to_string(
            index=False
        )
    )

    print()
    print(
        "No production logic changed."
    )


if __name__ == "__main__":
    main()