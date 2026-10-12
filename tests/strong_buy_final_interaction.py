"""
Final read-only STRONG BUY interaction analysis.

Tests the combined relationship between:
    - Technical Score
    - Entry Quality
    - Growth Score

The purpose is to identify whether STRONG BUY weakness is concentrated
in particular combinations of technical strength, entry quality and growth.

No production logic is changed.
"""

import sqlite3
import pandas as pd


DB_PATH = "data/portfolio_manager.db"


def load_data():

    conn = sqlite3.connect(DB_PATH)

    query = """
    SELECT
        re.recommendation_id,
        re.ticker,
        re.days_after,
        re.return_percent,

        re.growth_score,
        re.investment_score,
        re.technical_score,
        re.confidence_score,

        ev.entry_quality

    FROM recommendation_evaluations re

    LEFT JOIN recommendation_evidence ev
        ON ev.recommendation_id = re.recommendation_id

    WHERE re.days_after = 5
      AND re.return_percent IS NOT NULL

      AND re.growth_score IS NOT NULL
      AND re.investment_score IS NOT NULL
      AND re.technical_score IS NOT NULL
      AND re.confidence_score IS NOT NULL

      AND ev.entry_quality IS NOT NULL
    """

    df = pd.read_sql_query(query, conn)

    conn.close()

    return df


def apply_strong_buy_rule(df):

    df = df.copy()

    df["strong_buy"] = (
        (df["investment_score"] >= 80)
        & (df["technical_score"] >= 75)
    )

    return df


def add_bands(df):

    df = df.copy()

    df["technical_band"] = pd.cut(
        df["technical_score"],
        bins=[
            -float("inf"),
            84,
            89,
            float("inf"),
        ],
        labels=[
            "<85",
            "85-89",
            "90+",
        ],
    )

    df["growth_band"] = pd.cut(
        df["growth_score"],
        bins=[
            -float("inf"),
            79,
            84,
            89,
            94,
            float("inf"),
        ],
        labels=[
            "<80",
            "80-84",
            "85-89",
            "90-94",
            "95+",
        ],
    )

    return df


def entry_quality_normalised(df):

    df = df.copy()

    df["entry_quality"] = (
        df["entry_quality"]
        .fillna("UNKNOWN")
        .astype(str)
        .str.strip()
        .str.upper()
    )

    return df


def print_baseline(sb):

    print()
    print("=" * 90)
    print("FINAL STRONG BUY INTERACTION ANALYSIS")
    print("=" * 90)

    print()

    print(
        "Mature STRONG BUY observations:",
        len(sb),
    )

    print(
        "Mean 5D return:",
        round(sb["return_percent"].mean(), 3),
    )

    print(
        "Median 5D return:",
        round(sb["return_percent"].median(), 3),
    )

    print(
        "Positive 5D:",
        round(
            sb["return_percent"].gt(0).mean() * 100,
            2,
        ),
    )


def technical_entry_quality(sb):

    print()
    print("=" * 90)
    print("TECHNICAL SCORE × ENTRY QUALITY")
    print("=" * 90)

    print()

    result = (
        sb.groupby(
            [
                "technical_band",
                "entry_quality",
            ],
            observed=False,
        )
        .agg(
            count=("return_percent", "size"),
            mean_growth=(
                "growth_score",
                "mean",
            ),
            mean_investment=(
                "investment_score",
                "mean",
            ),
            mean_return=(
                "return_percent",
                "mean",
            ),
            median_return=(
                "return_percent",
                "median",
            ),
            positive_pct=(
                "return_percent",
                lambda x:
                x.gt(0).mean() * 100,
            ),
        )
        .reset_index()
    )

    print(result.to_string(index=False))


def technical_growth(sb):

    print()
    print("=" * 90)
    print("TECHNICAL SCORE × GROWTH SCORE")
    print("=" * 90)

    print()

    result = (
        sb.groupby(
            [
                "technical_band",
                "growth_band",
            ],
            observed=False,
        )
        .agg(
            count=("return_percent", "size"),
            mean_entry_quality=(
                "entry_quality",
                lambda x: (
                    x.eq("REASONABLE").mean()
                    * 100
                ),
            ),
            mean_return=(
                "return_percent",
                "mean",
            ),
            median_return=(
                "return_percent",
                "median",
            ),
            positive_pct=(
                "return_percent",
                lambda x:
                x.gt(0).mean() * 100,
            ),
        )
        .reset_index()
    )

    print(result.to_string(index=False))


def growth_entry_quality(sb):

    print()
    print("=" * 90)
    print("GROWTH SCORE × ENTRY QUALITY")
    print("=" * 90)

    print()

    result = (
        sb.groupby(
            [
                "growth_band",
                "entry_quality",
            ],
            observed=False,
        )
        .agg(
            count=("return_percent", "size"),
            mean_technical=(
                "technical_score",
                "mean",
            ),
            mean_investment=(
                "investment_score",
                "mean",
            ),
            mean_return=(
                "return_percent",
                "mean",
            ),
            median_return=(
                "return_percent",
                "median",
            ),
            positive_pct=(
                "return_percent",
                lambda x:
                x.gt(0).mean() * 100,
            ),
        )
        .reset_index()
    )

    print(result.to_string(index=False))


def three_way_interaction(sb):

    print()
    print("=" * 90)
    print(
        "THREE-WAY INTERACTION: "
        "TECHNICAL × ENTRY QUALITY × GROWTH"
    )
    print("=" * 90)

    print()

    result = (
        sb.groupby(
            [
                "technical_band",
                "entry_quality",
                "growth_band",
            ],
            observed=False,
        )
        .agg(
            count=("return_percent", "size"),
            mean_investment=(
                "investment_score",
                "mean",
            ),
            mean_return=(
                "return_percent",
                "mean",
            ),
            median_return=(
                "return_percent",
                "median",
            ),
            positive_pct=(
                "return_percent",
                lambda x:
                x.gt(0).mean() * 100,
            ),
        )
        .reset_index()
    )

    # Only display combinations with
    # enough observations to be meaningful.
    result = result[
        result["count"] >= 3
    ].copy()

    result = result.sort_values(
        [
            "mean_return",
            "count",
        ],
        ascending=[
            True,
            False,
        ],
    )

    print(result.to_string(index=False))


def strongest_and_weakest_regimes(sb):

    print()
    print("=" * 90)
    print("STRONGEST / WEAKEST STRONG BUY REGIMES")
    print("=" * 90)

    print()

    result = (
        sb.groupby(
            [
                "technical_band",
                "entry_quality",
                "growth_band",
            ],
            observed=False,
        )
        .agg(
            count=("return_percent", "size"),
            mean_return=(
                "return_percent",
                "mean",
            ),
            median_return=(
                "return_percent",
                "median",
            ),
            positive_pct=(
                "return_percent",
                lambda x:
                x.gt(0).mean() * 100,
            ),
        )
        .reset_index()
    )

    result = result[
        result["count"] >= 3
    ].copy()

    print()
    print("LOWEST RETURN REGIMES")
    print()

    print(
        result.sort_values(
            "mean_return",
            ascending=True,
        )
        .head(10)
        .to_string(index=False)
    )

    print()
    print("HIGHEST RETURN REGIMES")
    print()

    print(
        result.sort_values(
            "mean_return",
            ascending=False,
        )
        .head(10)
        .to_string(index=False)
    )


def technical_breakpoint(sb):

    print()
    print("=" * 90)
    print("TECHNICAL SCORE BREAKPOINT WITHIN ENTRY QUALITY")
    print("=" * 90)

    print()

    result = (
        sb.groupby(
            [
                "entry_quality",
                "technical_band",
            ],
            observed=False,
        )
        .agg(
            count=("return_percent", "size"),
            mean_return=(
                "return_percent",
                "mean",
            ),
            positive_pct=(
                "return_percent",
                lambda x:
                x.gt(0).mean() * 100,
            ),
        )
        .reset_index()
    )

    print(result.to_string(index=False))


def growth_breakpoint(sb):

    print()
    print("=" * 90)
    print("GROWTH SCORE BREAKPOINT WITHIN TECHNICAL BAND")
    print("=" * 90)

    print()

    result = (
        sb.groupby(
            [
                "technical_band",
                "growth_band",
            ],
            observed=False,
        )
        .agg(
            count=("return_percent", "size"),
            mean_return=(
                "return_percent",
                "mean",
            ),
            positive_pct=(
                "return_percent",
                lambda x:
                x.gt(0).mean() * 100,
            ),
        )
        .reset_index()
    )

    print(result.to_string(index=False))


def winner_loser_profile(sb):

    print()
    print("=" * 90)
    print("STRONG BUY WINNERS VS LOSERS")
    print("=" * 90)

    print()

    winners = sb[
        sb["return_percent"] > 0
    ]

    losers = sb[
        sb["return_percent"] <= 0
    ]

    rows = []

    for name, group in [
        ("WINNERS", winners),
        ("LOSERS", losers),
    ]:

        rows.append(
            {
                "group": name,
                "count": len(group),
                "mean_return": group[
                    "return_percent"
                ].mean(),
                "technical": group[
                    "technical_score"
                ].mean(),
                "growth": group[
                    "growth_score"
                ].mean(),
                "investment": group[
                    "investment_score"
                ].mean(),
                "confidence": group[
                    "confidence_score"
                ].mean(),
                "reasonable_entry_pct": (
                    group["entry_quality"]
                    .eq("REASONABLE")
                    .mean()
                    * 100
                ),
                "moderately_extended_pct": (
                    group["entry_quality"]
                    .eq("MODERATELY EXTENDED")
                    .mean()
                    * 100
                ),
                "extended_pct": (
                    group["entry_quality"]
                    .eq("EXTENDED")
                    .mean()
                    * 100
                ),
                "highly_extended_pct": (
                    group["entry_quality"]
                    .eq("HIGHLY EXTENDED")
                    .mean()
                    * 100
                ),
            }
        )

    print(
        pd.DataFrame(rows).to_string(
            index=False
        )
    )


def main():

    df = load_data()

    print(
        "Complete mature 5D observations:",
        len(df),
    )

    df = apply_strong_buy_rule(df)
    df = add_bands(df)
    df = entry_quality_normalised(df)

    sb = df[
        df["strong_buy"]
    ].copy()

    print_baseline(sb)

    technical_entry_quality(sb)

    technical_growth(sb)

    growth_entry_quality(sb)

    three_way_interaction(sb)

    strongest_and_weakest_regimes(sb)

    technical_breakpoint(sb)

    growth_breakpoint(sb)

    winner_loser_profile(sb)

    print()
    print(
        "No production logic changed."
    )


if __name__ == "__main__":
    main()
