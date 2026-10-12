import sqlite3

import pandas as pd


DB_PATH = "data/portfolio_manager.db"


# ============================================================
# LOAD MATURE STRONG BUY OBSERVATIONS
# ============================================================

def load_data():

    conn = sqlite3.connect(DB_PATH)

    query = """
    SELECT
        re.ticker,
        re.days_after,
        re.return_percent,

        re.growth_score,
        re.technical_score,
        re.investment_score,
        re.confidence_score,

        ev.entry_quality

    FROM recommendation_evaluations re

    LEFT JOIN recommendation_evidence ev
        ON ev.recommendation_id = re.recommendation_id

    WHERE re.days_after = 5
      AND re.return_percent IS NOT NULL

      AND re.growth_score IS NOT NULL
      AND re.technical_score IS NOT NULL
      AND re.investment_score IS NOT NULL
      AND re.confidence_score IS NOT NULL

      AND ev.entry_quality IS NOT NULL
    """

    df = pd.read_sql_query(
        query,
        conn,
    )

    conn.close()

    return df
# ============================================================
# RECONSTRUCT CURRENT STRONG BUY RULE
# ============================================================

def identify_strong_buy(df):

    df = df.copy()

    df["is_strong_buy"] = (
        (df["investment_score"] >= 80)
        & (df["technical_score"] >= 75)
    )

    return df[
        df["is_strong_buy"]
    ].copy()


# ============================================================
# GROWTH SCORE BANDS
# ============================================================

def score_band(score):

    if score < 80:
        return "<80"

    if score < 85:
        return "80-84"

    if score < 90:
        return "85-89"

    if score < 95:
        return "90-94"

    return "95+"


# ============================================================
# MATCHED GROWTH SCORE ANALYSIS
# ============================================================

def matched_growth_analysis(df):

    print()
    print(
        "STRONG BUY MATCHED GROWTH SCORE ANALYSIS"
    )
    print(
        "=" * 90
    )

    print()
    print(
        f"Total mature STRONG BUY observations: "
        f"{len(df)}"
    )

    if len(df) < 10:
        print(
            "Insufficient observations."
        )
        return pd.DataFrame()

    df = df.copy()

    df["growth_band"] = df[
        "growth_score"
    ].apply(score_band)

    # --------------------------------------------------------
    # BASIC SCORE-BAND PERFORMANCE
    # --------------------------------------------------------

    print()
    print(
        "GROWTH SCORE BAND PERFORMANCE"
    )
    print(
        "-" * 90
    )

    band_results = (
        df.groupby(
            "growth_band",
            observed=True,
        )["return_percent"]
        .agg(
            [
                "count",
                "mean",
                "median",
            ]
        )
    )

    positive = (
        df.groupby(
            "growth_band",
            observed=True,
        )["return_percent"]
        .apply(
            lambda x: (
                x > 0
            ).mean()
            * 100
        )
    )

    band_results[
        "positive_pct"
    ] = positive

    print(
        band_results.to_string()
    )

    # --------------------------------------------------------
    # MATCH EACH HIGHER-GROWTH OBSERVATION AGAINST
    # THE CLOSEST LOWER-GROWTH OBSERVATION
    #
    # Matching controls:
    #   Technical Score
    #   Investment Score
    #   Confidence
    #   Entry Quality
    #
    # Each control can only be used once.
    # --------------------------------------------------------

    print()
    print(
        "1:1 MATCHED GROWTH SCORE ANALYSIS"
    )
    print(
        "-" * 90
    )

    work = df.reset_index(
        drop=True
    ).copy()

    work["matched"] = False

    matches = []

    # Highest Growth Score first.
    # This allows us to ask whether higher-growth
    # observations outperform nearby lower-growth
    # observations after controlling for the other
    # STRONG BUY characteristics.

    target_indices = list(
        work.sort_values(
            [
                "growth_score",
                "technical_score",
                "investment_score",
                "confidence_score",
            ],
            ascending=[
                False,
                False,
                False,
                False,
            ],
        ).index
    )

    for target_idx in target_indices:

        if work.loc[
            target_idx,
            "matched",
        ]:
            continue

        target = work.loc[
            target_idx
        ]

        candidates = work[
            (~work["matched"])
            & (work.index != target_idx)
            & (
                work["growth_score"]
                < target["growth_score"]
            )
            & (
                work["entry_quality"]
                == target["entry_quality"]
            )
            & (
                (
                    work["technical_score"]
                    - target["technical_score"]
                ).abs()
                <= 5
            )
            & (
                (
                    work["investment_score"]
                    - target["investment_score"]
                ).abs()
                <= 5
            )
            & (
                (
                    work["confidence_score"]
                    - target["confidence_score"]
                ).abs()
                <= 5
            )
        ].copy()

        if candidates.empty:
            continue

        candidates["distance"] = (
            (
                candidates[
                    "technical_score"
                ]
                - target[
                    "technical_score"
                ]
            ).abs()
            + (
                candidates[
                    "investment_score"
                ]
                - target[
                    "investment_score"
                ]
            ).abs()
            + (
                candidates[
                    "confidence_score"
                ]
                - target[
                    "confidence_score"
                ]
            ).abs()
        )

        control_idx = (
            candidates[
                "distance"
            ]
            .idxmin()
        )

        control = work.loc[
            control_idx
        ]

        work.loc[
            target_idx,
            "matched",
        ] = True

        work.loc[
            control_idx,
            "matched",
        ] = True

        matches.append(
            {
                "target_growth_score":
                    target[
                        "growth_score"
                    ],
                "control_growth_score":
                    control[
                        "growth_score"
                    ],

                "growth_difference":
                    target[
                        "growth_score"
                    ]
                    - control[
                        "growth_score"
                    ],

                "target_return":
                    target[
                        "return_percent"
                    ],

                "control_return":
                    control[
                        "return_percent"
                    ],

                "incremental_return":
                    target[
                        "return_percent"
                    ]
                    - control[
                        "return_percent"
                    ],

                "entry_quality":
                    target[
                        "entry_quality"
                    ],

                "technical_difference":
                    target[
                        "technical_score"
                    ]
                    - control[
                        "technical_score"
                    ],

                "investment_difference":
                    target[
                        "investment_score"
                    ]
                    - control[
                        "investment_score"
                    ],

                "confidence_difference":
                    target[
                        "confidence_score"
                    ]
                    - control[
                        "confidence_score"
                    ],
            }
        )

    matches_df = pd.DataFrame(
        matches
    )

    print()

    print(
        f"Matched pairs: "
        f"{len(matches_df)}"
    )

    if matches_df.empty:
        print(
            "No matched pairs found."
        )
        return matches_df

    print(
        f"Mean Growth Score difference: "
        f"{matches_df['growth_difference'].mean():.3f}"
    )

    print(
        f"Mean incremental 5D return: "
        f"{matches_df['incremental_return'].mean():.3f}%"
    )

    print(
        f"Median incremental 5D return: "
        f"{matches_df['incremental_return'].median():.3f}%"
    )

    print(
        f"Higher Growth Score beat control: "
        f"{(
            matches_df['incremental_return'] > 0
        ).mean() * 100:.2f}%"
    )

    # --------------------------------------------------------
    # GROWTH DIFFERENCE BANDS
    # --------------------------------------------------------

    print()
    print(
        "MATCHED PAIRS BY GROWTH SCORE DIFFERENCE"
    )
    print(
        "-" * 90
    )

    matches_df[
        "growth_difference_band"
    ] = pd.cut(
        matches_df[
            "growth_difference"
        ],
        bins=[
            0,
            5,
            10,
            20,
            float("inf"),
        ],
        labels=[
            "1-5",
            "6-10",
            "11-20",
            "21+",
        ],
        include_lowest=True,
    )

    difference_results = (
        matches_df.groupby(
            "growth_difference_band",
            observed=True,
        )[
            "incremental_return"
        ]
        .agg(
            [
                "count",
                "mean",
                "median",
            ]
        )
    )

    difference_positive = (
        matches_df.groupby(
            "growth_difference_band",
            observed=True,
        )[
            "incremental_return"
        ]
        .apply(
            lambda x: (
                x > 0
            ).mean()
            * 100
        )
    )

    difference_results[
        "positive_pct"
    ] = difference_positive

    print(
        difference_results.to_string()
    )

    # --------------------------------------------------------
    # CORRELATION
    # --------------------------------------------------------

    print()
    print(
        "MATCHED GROWTH DIFFERENCE vs "
        "INCREMENTAL RETURN"
    )
    print(
        "-" * 90
    )

    correlation = matches_df[
        "growth_difference"
    ].corr(
        matches_df[
            "incremental_return"
        ]
    )

    print(
        f"Correlation: "
        f"{correlation:.3f}"
    )

    return matches_df


# ============================================================
# MAIN
# ============================================================

def main():

    df = load_data()

    print(
        f"Complete mature 5D observations: "
        f"{len(df)}"
    )

    df = identify_strong_buy(
        df
    )

    matched_growth_analysis(
        df
    )

    print()
    print(
        "No production logic changed."
    )


if __name__ == "__main__":
    main()
