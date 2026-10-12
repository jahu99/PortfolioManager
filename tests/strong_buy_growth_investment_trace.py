"""
Read-only forensic analysis of the relationship between
Growth Score, Investment Score and STRONG BUY outcomes.

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
    """

    df = pd.read_sql_query(query, conn)

    conn.close()

    return df


def add_strong_buy_rule(df):

    df = df.copy()

    df["strong_buy"] = (
        (df["investment_score"] >= 80)
        & (df["technical_score"] >= 75)
    )

    return df


def correlation_analysis(df):

    print()
    print("=" * 90)
    print("GROWTH SCORE → INVESTMENT SCORE RELATIONSHIP")
    print("=" * 90)

    print()

    print(
        "Growth / Investment correlation:",
        round(
            df["growth_score"].corr(
                df["investment_score"]
            ),
            3,
        ),
    )

    print()

    print("Growth Score summary:")
    print(
        df["growth_score"].describe()
    )

    print()

    print("Investment Score summary:")
    print(
        df["investment_score"].describe()
    )


def investment_by_growth(df):

    print()
    print("=" * 90)
    print("INVESTMENT SCORE BY GROWTH SCORE BAND")
    print("=" * 90)

    print()

    bins = [
        -float("inf"),
        79,
        84,
        89,
        94,
        float("inf"),
    ]

    labels = [
        "<80",
        "80-84",
        "85-89",
        "90-94",
        "95+",
    ]

    df["growth_band"] = pd.cut(
        df["growth_score"],
        bins=bins,
        labels=labels,
    )

    summary = (
        df.groupby(
            "growth_band",
            observed=False,
        )
        .agg(
            count=("investment_score", "size"),
            mean_investment=(
                "investment_score",
                "mean",
            ),
            median_investment=(
                "investment_score",
                "median",
            ),
            mean_return=(
                "return_percent",
                "mean",
            ),
            positive_pct=(
                "return_percent",
                lambda x: (
                    x.gt(0).mean() * 100
                ),
            ),
        )
    )

    print(summary)


def growth_within_investment_band(df):

    print()
    print("=" * 90)
    print("GROWTH SCORE WITHIN INVESTMENT SCORE BANDS")
    print("=" * 90)

    print()

    bins = [
        -float("inf"),
        79,
        84,
        89,
        94,
        float("inf"),
    ]

    labels = [
        "<80",
        "80-84",
        "85-89",
        "90-94",
        "95+",
    ]

    df["investment_band"] = pd.cut(
        df["investment_score"],
        bins=bins,
        labels=labels,
    )

    summary = (
        df.groupby(
            "investment_band",
            observed=False,
        )
        .agg(
            count=("growth_score", "size"),
            mean_growth=(
                "growth_score",
                "mean",
            ),
            median_growth=(
                "growth_score",
                "median",
            ),
            mean_return=(
                "return_percent",
                "mean",
            ),
            positive_pct=(
                "return_percent",
                lambda x: (
                    x.gt(0).mean() * 100
                ),
            ),
        )
    )

    print(summary)


def strong_buy_growth_distribution(df):

    print()
    print("=" * 90)
    print("STRONG BUY GROWTH / INVESTMENT DISTRIBUTION")
    print("=" * 90)

    print()

    sb = df[df["strong_buy"]].copy()

    print(
        "STRONG BUY observations:",
        len(sb),
    )

    print()

    print(
        "Growth Score:",
        "mean=",
        round(sb["growth_score"].mean(), 3),
        "median=",
        round(sb["growth_score"].median(), 3),
        "min=",
        round(sb["growth_score"].min(), 3),
        "max=",
        round(sb["growth_score"].max(), 3),
    )

    print(
        "Investment Score:",
        "mean=",
        round(sb["investment_score"].mean(), 3),
        "median=",
        round(sb["investment_score"].median(), 3),
        "min=",
        round(sb["investment_score"].min(), 3),
        "max=",
        round(sb["investment_score"].max(), 3),
    )

    print()

    print("STRONG BUY Growth Score bands:")

    print(
        sb.groupby(
            "growth_band",
            observed=False,
        )
        .agg(
            count=("return_percent", "size"),
            mean_investment=(
                "investment_score",
                "mean",
            ),
            mean_technical=(
                "technical_score",
                "mean",
            ),
            mean_return=(
                "return_percent",
                "mean",
            ),
            positive_pct=(
                "return_percent",
                lambda x: (
                    x.gt(0).mean() * 100
                ),
            ),
        )
    )


def strong_buy_growth_vs_investment(df):

    print()
    print("=" * 90)
    print("STRONG BUY GROWTH SCORE vs INVESTMENT SCORE")
    print("=" * 90)

    print()

    sb = df[df["strong_buy"]].copy()

    print(
        "Correlation:",
        round(
            sb["growth_score"].corr(
                sb["investment_score"]
            ),
            3,
        ),
    )

    print()

    print(
        "Growth Score vs realised 5D:",
        round(
            sb["growth_score"].corr(
                sb["return_percent"]
            ),
            3,
        ),
    )

    print(
        "Investment Score vs realised 5D:",
        round(
            sb["investment_score"].corr(
                sb["return_percent"]
            ),
            3,
        ),
    )

    print()

    print("STRONG BUY observations by exact Growth Score:")

    print(
        sb.groupby("growth_score")
        .agg(
            count=("return_percent", "size"),
            mean_investment=(
                "investment_score",
                "mean",
            ),
            mean_technical=(
                "technical_score",
                "mean",
            ),
            mean_return=(
                "return_percent",
                "mean",
            ),
            positive_pct=(
                "return_percent",
                lambda x: (
                    x.gt(0).mean() * 100
                ),
            ),
        )
        .sort_index()
    )


def residual_growth_analysis(df):

    print()
    print("=" * 90)
    print("RESIDUAL GROWTH ANALYSIS")
    print("=" * 90)

    print()

    # Estimate the linear relationship between
    # Growth Score and Investment Score.
    #
    # The residual asks:
    #
    # "Is this stock's Growth Score unusually
    # high or low relative to its Investment Score?"

    model = pd.DataFrame(
        {
            "growth": df["growth_score"],
            "investment": df["investment_score"],
        }
    ).dropna()

    slope = (
        model["growth"].cov(
            model["investment"]
        )
        / model["investment"].var()
    )

    intercept = (
        model["growth"].mean()
        - slope * model["investment"].mean()
    )

    df = df.copy()

    df["expected_growth_from_investment"] = (
        intercept
        + slope * df["investment_score"]
    )

    df["growth_residual"] = (
        df["growth_score"]
        - df["expected_growth_from_investment"]
    )

    sb = df[df["strong_buy"]].copy()

    print(
        "Growth residual correlation with 5D return:",
        round(
            sb["growth_residual"].corr(
                sb["return_percent"]
            ),
            3,
        ),
    )

    print()

    bins = [
        -float("inf"),
        -10,
        -5,
        5,
        10,
        float("inf"),
    ]

    labels = [
        "<-10",
        "-10 to -5",
        "-5 to +5",
        "+5 to +10",
        ">+10",
    ]

    sb["growth_residual_band"] = pd.cut(
        sb["growth_residual"],
        bins=bins,
        labels=labels,
    )

    print(
        sb.groupby(
            "growth_residual_band",
            observed=False,
        )
        .agg(
            count=("return_percent", "size"),
            mean_growth_residual=(
                "growth_residual",
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
                lambda x: (
                    x.gt(0).mean() * 100
                ),
            ),
        )
    )


def main():

    df = load_data()

    print()
    print(
        "Total mature 5D observations:",
        len(df),
    )

    df = add_strong_buy_rule(df)

    correlation_analysis(df)

    investment_by_growth(df)

    growth_within_investment_band(df)

    strong_buy_growth_distribution(df)

    strong_buy_growth_vs_investment(df)

    residual_growth_analysis(df)

    print()
    print(
        "No production logic changed."
    )


if __name__ == "__main__":
    main()
