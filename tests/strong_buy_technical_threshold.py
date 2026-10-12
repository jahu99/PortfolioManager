"""
STRONG BUY Technical Threshold Analysis

Read-only forensic analysis.

Tests whether increasing the STRONG BUY technical-score
threshold improves realised 5D performance.

No production decision logic is changed.
"""

import sqlite3
import pandas as pd


DB_PATH = "data/portfolio_manager.db"

TECHNICAL_THRESHOLDS = [75, 80, 85, 90]


def load_data():
    conn = sqlite3.connect(DB_PATH)

    evidence = pd.read_sql_query(
        """
        SELECT
            recommendation_id,
            ticker,
            signal,
            investment_score,
            technical_score,
            quality_score,
            growth_score,
            confidence_score,
            entry_price,
            rsi,
            sma200
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


def prepare_data(evidence, evaluations):
    df = evidence.merge(
        evaluations,
        on=["recommendation_id", "ticker"],
        how="inner",
    )

    numeric_columns = [
        "investment_score",
        "technical_score",
        "quality_score",
        "growth_score",
        "confidence_score",
        "entry_price",
        "rsi",
        "sma200",
        "return_percent",
    ]

    for column in numeric_columns:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

    df = df.dropna(
        subset=[
            "investment_score",
            "technical_score",
            "quality_score",
            "entry_price",
            "sma200",
            "rsi",
            "return_percent",
        ]
    ).copy()

    # Reconstruct the actual STRONG BUY production rule.
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

    df["strong_buy"] = (
        df["rule_investment"]
        & df["rule_technical"]
        & df["rule_quality"]
        & df["rule_trend"]
        & df["rule_rsi"]
    )

    return df


def analyse_thresholds(df):
    strong_buy = df[
        df["strong_buy"]
    ].copy()

    baseline_n = len(strong_buy)

    print()
    print("STRONG BUY TECHNICAL THRESHOLD ANALYSIS")
    print("=" * 70)

    print()
    print(
        f"Current STRONG BUY population: {baseline_n}"
    )

    print()
    print(
        f"{'Threshold':<12}"
        f"{'N':>8}"
        f"{'Coverage %':>14}"
        f"{'Mean 5D %':>14}"
        f"{'Median 5D %':>16}"
        f"{'Positive 5D %':>17}"
    )

    print("-" * 70)

    results = []

    for threshold in TECHNICAL_THRESHOLDS:
        subset = strong_buy[
            strong_buy["technical_score"]
            >= threshold
        ].copy()

        n = len(subset)

        if n == 0:
            mean_return = None
            median_return = None
            positive_rate = None
            coverage = 0.0
        else:
            mean_return = (
                subset["return_percent"]
                .mean()
            )

            median_return = (
                subset["return_percent"]
                .median()
            )

            positive_rate = (
                (
                    subset["return_percent"] > 0
                ).mean()
                * 100
            )

            coverage = (
                n / baseline_n * 100
                if baseline_n
                else 0.0
            )

        results.append(
            {
                "technical_threshold": threshold,
                "n": n,
                "coverage_percent": coverage,
                "mean_5d": mean_return,
                "median_5d": median_return,
                "positive_5d_percent": positive_rate,
            }
        )

        print(
            f"{threshold:<12}"
            f"{n:>8}"
            f"{coverage:>13.2f}%"
            f"{mean_return:>13.3f}"
            f"{median_return:>15.3f}"
            f"{positive_rate:>16.2f}%"
        )

    return strong_buy, pd.DataFrame(results)


def analyse_incremental_bands(strong_buy):
    print()
    print("INCREMENTAL TECHNICAL SCORE BANDS")
    print("=" * 70)

    bands = [
        ("75-79", 75, 80),
        ("80-84", 80, 85),
        ("85-89", 85, 90),
        ("90+", 90, None),
    ]

    print()
    print(
        f"{'Band':<12}"
        f"{'N':>8}"
        f"{'Mean 5D %':>14}"
        f"{'Median 5D %':>16}"
        f"{'Positive 5D %':>17}"
    )

    print("-" * 70)

    for label, lower, upper in bands:

        if upper is None:
            subset = strong_buy[
                strong_buy["technical_score"]
                >= lower
            ]
        else:
            subset = strong_buy[
                (
                    strong_buy["technical_score"]
                    >= lower
                )
                & (
                    strong_buy["technical_score"]
                    < upper
                )
            ]

        n = len(subset)

        if n == 0:
            print(
                f"{label:<12}"
                f"{0:>8}"
                f"{'N/A':>14}"
                f"{'N/A':>16}"
                f"{'N/A':>17}"
            )
            continue

        mean_return = (
            subset["return_percent"].mean()
        )

        median_return = (
            subset["return_percent"].median()
        )

        positive_rate = (
            (
                subset["return_percent"] > 0
            ).mean()
            * 100
        )

        print(
            f"{label:<12}"
            f"{n:>8}"
            f"{mean_return:>13.3f}"
            f"{median_return:>15.3f}"
            f"{positive_rate:>16.2f}%"
        )


def analyse_winners_vs_losers(strong_buy):
    print()
    print("WINNER VS LOSER TECHNICAL SCORE")
    print("=" * 70)

    winners = strong_buy[
        strong_buy["return_percent"] > 0
    ]

    losers = strong_buy[
        strong_buy["return_percent"] <= 0
    ]

    print()
    print(
        f"Winners: {len(winners)}"
    )
    if not winners.empty:
        print(
            "Mean technical score:",
            round(
                winners["technical_score"].mean(),
                3,
            ),
        )
        print(
            "Median technical score:",
            round(
                winners["technical_score"].median(),
                3,
            ),
        )

    print()
    print(
        f"Losers: {len(losers)}"
    )
    if not losers.empty:
        print(
            "Mean technical score:",
            round(
                losers["technical_score"].mean(),
                3,
            ),
        )
        print(
            "Median technical score:",
            round(
                losers["technical_score"].median(),
                3,
            ),
        )


def main():
    evidence, evaluations = load_data()

    df = prepare_data(
        evidence,
        evaluations,
    )

    strong_buy, results = analyse_thresholds(
        df
    )

    analyse_incremental_bands(
        strong_buy
    )

    analyse_winners_vs_losers(
        strong_buy
    )

    print()
    print("RESULTS DATAFRAME")
    print("=" * 70)
    print(results.to_string(index=False))

    print()
    print("No production logic changed.")


if __name__ == "__main__":
    main()
