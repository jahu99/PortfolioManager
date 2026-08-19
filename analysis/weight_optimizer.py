# analysis/weight_optimizer.py
"""
Investment Score Weight Calibration / Research Engine

Purpose
-------
Evaluate alternative Technical / Quality / Growth weighting schemes
using historical recommendation outcomes.

IMPORTANT
---------
This module is RESEARCH ONLY.

It does NOT:
    - modify production scoring weights
    - call save_weights()
    - write data/scoring_weights.json
    - automatically change Investment Score behaviour

The production Investment Score therefore remains unchanged until
a weighting has been deliberately reviewed and approved.

Research architecture
---------------------

    Historical Recommendation Outcomes
                    |
                    v
        Candidate Weight Configurations
                    |
                    v
          Reconstructed Investment Score
                    |
                    v
        Historical / Out-of-Sample Testing
                    |
                    v
        Threshold + Horizon Analysis
                    |
                    v
             Calibration Report

Why this replaces the previous optimiser
-----------------------------------------
The previous implementation converted simple component/return
correlations directly into production weights.

That approach is not sufficiently robust because:

    - correlation is not a multivariate optimisation method
    - component interactions are ignored
    - horizons are mixed
    - the historical sample is relatively small
    - missing component values can distort calibration
    - production weights could be changed automatically

This module instead directly tests candidate weight combinations
against historical outcomes.

Important data-quality rule
---------------------------
A missing Technical, Quality or Growth score is NOT treated as zero.

Zero is a legitimate score.

Missing means the observation cannot reliably be used for calibration.

Important validation rule
-------------------------
5-day and 10-day evaluations for the same recommendation must remain
together in the same train/test partition.

The split is therefore performed at recommendation_id level using
evaluation_date.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from data.database import get_connection

from analysis.weight_controller import (
    get_weights,
)


# ============================================================
# Research baseline
# ============================================================

BASELINE_WEIGHTS = {
    "technical_score": 50.0,
    "quality_score": 25.0,
    "growth_score": 25.0,
}


# ============================================================
# Candidate research weight sets
# ============================================================
#
# These are deliberately conservative research candidates.
#
# They are NOT production weights.
#
# All candidates total 100%.
#

CANDIDATE_WEIGHT_SETS = {

    "Baseline 50/25/25": {
        "technical_score": 50.0,
        "quality_score": 25.0,
        "growth_score": 25.0,
    },

    "Balanced 45/30/25": {
        "technical_score": 45.0,
        "quality_score": 30.0,
        "growth_score": 25.0,
    },

    "Balanced Growth 45/25/30": {
        "technical_score": 45.0,
        "quality_score": 25.0,
        "growth_score": 30.0,
    },

    "Balanced 40/30/30": {
        "technical_score": 40.0,
        "quality_score": 30.0,
        "growth_score": 30.0,
    },

    "Growth 40/25/35": {
        "technical_score": 40.0,
        "quality_score": 25.0,
        "growth_score": 35.0,
    },

    "Technical 55/25/20": {
        "technical_score": 55.0,
        "quality_score": 25.0,
        "growth_score": 20.0,
    },

    "Technical 50/30/20": {
        "technical_score": 50.0,
        "quality_score": 30.0,
        "growth_score": 20.0,
    },
}


# ============================================================
# Calibration configuration
# ============================================================

TRAINING_FRACTION = 0.70

SCORE_THRESHOLDS = [
    65,
    70,
    75,
    80,
    85,
]


# ============================================================
# Helpers
# ============================================================

def safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    """
    Safely convert a value to float.
    """

    try:

        if value is None:
            return default

        return float(value)

    except (TypeError, ValueError):

        return default


def validate_weights(
    weights: dict[str, float],
) -> bool:
    """
    Validate a research weight set.

    Requirements
    ------------
    - exactly three components
    - numeric values
    - values between 0 and 100
    - total equals 100%
    """

    required_keys = {
        "technical_score",
        "quality_score",
        "growth_score",
    }

    if not isinstance(
        weights,
        dict,
    ):

        return False

    if set(weights.keys()) != required_keys:

        return False

    values = []

    for value in weights.values():

        try:

            numeric_value = float(value)

        except (
            TypeError,
            ValueError,
        ):

            return False

        if (
            numeric_value < 0
            or
            numeric_value > 100
        ):

            return False

        values.append(
            numeric_value
        )

    return (
        round(
            sum(values),
            2,
        )
        == 100.0
    )


def calculate_reconstructed_score(
    dataframe: pd.DataFrame,
    weights: dict[str, float],
) -> pd.Series:
    """
    Recalculate Investment Score using a candidate weighting.

    Investment Score =
        Technical × Technical Weight
      + Quality   × Quality Weight
      + Growth    × Growth Weight
    """

    technical = pd.to_numeric(
        dataframe[
            "technical_score"
        ],
        errors="coerce",
    ).clip(
        lower=0,
        upper=100,
    )

    quality = pd.to_numeric(
        dataframe[
            "quality_score"
        ],
        errors="coerce",
    ).clip(
        lower=0,
        upper=100,
    )

    growth = pd.to_numeric(
        dataframe[
            "growth_score"
        ],
        errors="coerce",
    ).clip(
        lower=0,
        upper=100,
    )

    return (
        technical
        *
        safe_float(
            weights[
                "technical_score"
            ]
        )
        /
        100.0
        +
        quality
        *
        safe_float(
            weights[
                "quality_score"
            ]
        )
        /
        100.0
        +
        growth
        *
        safe_float(
            weights[
                "growth_score"
            ]
        )
        /
        100.0
    )


# ============================================================
# Learning data
# ============================================================

def load_learning_data() -> pd.DataFrame:
    """
    Load historical recommendation outcomes for calibration.

    Missing component scores are excluded rather than treated as zero.

    recommendation_id and evaluation_date are retained so the
    calibration can split complete recommendations chronologically.
    """

    print(
        "WEIGHT CALIBRATION ENGINE START"
    )

    conn = get_connection()

    try:

        query = """
        SELECT
            id,
            recommendation_id,
            ticker,
            signal,
            evaluation_date,
            days_after,
            technical_score,
            quality_score,
            growth_score,
            return_percent,
            outcome,
            investment_score,
            confidence_score
        FROM recommendation_evaluations
        WHERE return_percent IS NOT NULL
        ORDER BY evaluation_date, recommendation_id, days_after
        """

        dataframe = pd.read_sql_query(
            query,
            conn,
        )

    finally:

        conn.close()

    if dataframe.empty:

        print(
            "No historical recommendation data available."
        )

        return dataframe

    # --------------------------------------------------------
    # Convert numeric fields.
    # --------------------------------------------------------

    numeric_columns = [
        "id",
        "recommendation_id",
        "technical_score",
        "quality_score",
        "growth_score",
        "return_percent",
        "days_after",
        "investment_score",
        "confidence_score",
    ]

    for column in numeric_columns:

        if column not in dataframe.columns:

            dataframe[
                column
            ] = pd.NA

        dataframe[
            column
        ] = pd.to_numeric(
            dataframe[
                column
            ],
            errors="coerce",
        )

    # --------------------------------------------------------
    # Parse evaluation date.
    # --------------------------------------------------------

    dataframe[
        "evaluation_date"
    ] = pd.to_datetime(
        dataframe[
            "evaluation_date"
        ],
        errors="coerce",
    )

    # --------------------------------------------------------
    # Complete-data requirement.
    # --------------------------------------------------------

    required_columns = [
        "recommendation_id",
        "evaluation_date",
        "technical_score",
        "quality_score",
        "growth_score",
        "return_percent",
    ]

    before_count = len(
        dataframe
    )

    dataframe = dataframe.dropna(
        subset=required_columns
    ).copy()

    after_count = len(
        dataframe
    )

    print(
        "Calibration observations with complete "
        "component data:",
        f"{after_count} / {before_count}",
    )

    excluded_count = (
        before_count
        -
        after_count
    )

    if excluded_count > 0:

        print(
            "Excluded observations with missing "
            "calibration data:",
            excluded_count,
        )

    # --------------------------------------------------------
    # Score validation.
    # --------------------------------------------------------

    dataframe = dataframe[
        dataframe[
            "technical_score"
        ].between(
            0,
            100,
        )
        &
        dataframe[
            "quality_score"
        ].between(
            0,
            100,
        )
        &
        dataframe[
            "growth_score"
        ].between(
            0,
            100,
        )
    ].copy()

    # --------------------------------------------------------
    # Chronological ordering.
    # --------------------------------------------------------

    dataframe.sort_values(
        [
            "evaluation_date",
            "recommendation_id",
            "days_after",
        ],
        inplace=True,
    )

    dataframe.reset_index(
        drop=True,
        inplace=True,
    )

    print(
        "Usable calibration records:",
        len(dataframe),
    )

    print(
        "Unique recommendations:",
        dataframe[
            "recommendation_id"
        ].nunique(),
    )

    print(
        "Evaluation date range:",
        dataframe[
            "evaluation_date"
        ].min(),
        "to",
        dataframe[
            "evaluation_date"
        ].max(),
    )

    return dataframe


# ============================================================
# Candidate validation
# ============================================================

def validate_candidate_weight_sets():
    """
    Return only valid research weight configurations.
    """

    valid_sets = {}

    for name, weights in CANDIDATE_WEIGHT_SETS.items():

        if validate_weights(
            weights
        ):

            valid_sets[
                name
            ] = weights

        else:

            print(
                "Ignoring invalid research weight set:",
                name,
                weights,
            )

    return valid_sets


# ============================================================
# Performance metrics
# ============================================================

def calculate_metrics(
    dataframe: pd.DataFrame,
) -> dict[str, float]:
    """
    Calculate return and win-rate metrics.
    """

    if dataframe.empty:

        return {
            "Observations": 0,
            "Average Return %": 0.0,
            "Median Return %": 0.0,
            "Win Rate %": 0.0,
            "Best Return %": 0.0,
            "Worst Return %": 0.0,
        }

    returns = pd.to_numeric(
        dataframe[
            "return_percent"
        ],
        errors="coerce",
    ).dropna()

    if returns.empty:

        return {
            "Observations": 0,
            "Average Return %": 0.0,
            "Median Return %": 0.0,
            "Win Rate %": 0.0,
            "Best Return %": 0.0,
            "Worst Return %": 0.0,
        }

    return {

        "Observations":
            int(
                len(returns)
            ),

        "Average Return %":
            round(
                float(
                    returns.mean()
                ),
                3,
            ),

        "Median Return %":
            round(
                float(
                    returns.median()
                ),
                3,
            ),

        "Win Rate %":
            round(
                float(
                    (
                        returns > 0
                    ).mean()
                    *
                    100.0
                ),
                2,
            ),

        "Best Return %":
            round(
                float(
                    returns.max()
                ),
                3,
            ),

        "Worst Return %":
            round(
                float(
                    returns.min()
                ),
                3,
            ),
    }


# ============================================================
# Recommendation-level train/test split
# ============================================================

def assign_train_test_samples(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """
    Assign IN SAMPLE / OUT OF SAMPLE at recommendation level.

    All evaluations belonging to one recommendation remain in
    the same sample.

    This prevents 5-day and 10-day evaluations of the same
    recommendation being split across training and validation.
    """

    working = dataframe.copy()

    recommendation_dates = (
        working[
            [
                "recommendation_id",
                "evaluation_date",
            ]
        ]
        .drop_duplicates(
            subset=[
                "recommendation_id",
            ]
        )
        .sort_values(
            "evaluation_date",
        )
        .reset_index(
            drop=True,
        )
    )

    recommendation_count = len(
        recommendation_dates
    )

    if recommendation_count < 2:

        working[
            "Sample"
        ] = "IN SAMPLE"

        return working

    split_index = int(
        recommendation_count
        *
        TRAINING_FRACTION
    )

    split_index = max(
        1,
        split_index,
    )

    split_index = min(
        recommendation_count - 1,
        split_index,
    )

    training_ids = set(
        recommendation_dates.iloc[
            :split_index
        ][
            "recommendation_id"
        ].tolist()
    )

    validation_ids = set(
        recommendation_dates.iloc[
            split_index:
        ][
            "recommendation_id"
        ].tolist()
    )

    working[
        "Sample"
    ] = "OUT OF SAMPLE"

    working.loc[
        working[
            "recommendation_id"
        ].isin(
            training_ids
        ),
        "Sample"
    ] = "IN SAMPLE"

    # Defensive assertion.
    #
    # Every recommendation should belong to exactly one
    # partition.

    assigned_ids = (
        training_ids
        |
        validation_ids
    )

    if len(
        assigned_ids
    ) != recommendation_count:

        raise RuntimeError(
            "Recommendation-level train/test split failed."
        )

    return working


# ============================================================
# Evaluate one weighting
# ============================================================

def evaluate_weight_set(
    dataframe: pd.DataFrame,
    weight_name: str,
    weights: dict[str, float],
) -> pd.DataFrame:
    """
    Evaluate one candidate weighting across score thresholds
    and time horizons.

    This does not create production decisions.
    """

    if dataframe.empty:

        return pd.DataFrame()

    working = dataframe.copy()

    # --------------------------------------------------------
    # Reconstruct Investment Score.
    # --------------------------------------------------------

    working[
        "Calibrated Investment Score"
    ] = calculate_reconstructed_score(
        working,
        weights,
    )

    # --------------------------------------------------------
    # Assign time-aware samples.
    # --------------------------------------------------------

    working = assign_train_test_samples(
        working
    )

    rows = []

    # --------------------------------------------------------
    # Evaluate thresholds.
    # --------------------------------------------------------

    for threshold in SCORE_THRESHOLDS:

        selected = working[
            working[
                "Calibrated Investment Score"
            ]
            >= threshold
        ].copy()

        if selected.empty:

            continue

        # ----------------------------------------------------
        # Overall / training / validation.
        # ----------------------------------------------------

        for sample_name in (
            "ALL",
            "IN SAMPLE",
            "OUT OF SAMPLE",
        ):

            if sample_name == "ALL":

                sample_df = selected

            else:

                sample_df = selected[
                    selected[
                        "Sample"
                    ]
                    ==
                    sample_name
                ]

            if sample_df.empty:

                continue

            metrics = calculate_metrics(
                sample_df
            )

            rows.append({

                "Weight Set":
                    weight_name,

                "Technical %":
                    weights[
                        "technical_score"
                    ],

                "Quality %":
                    weights[
                        "quality_score"
                    ],

                "Growth %":
                    weights[
                        "growth_score"
                    ],

                "Threshold":
                    threshold,

                "Sample":
                    sample_name,

                "Horizon":
                    "ALL",

                "Observations":
                    metrics[
                        "Observations"
                    ],

                "Average Return %":
                    metrics[
                        "Average Return %"
                    ],

                "Median Return %":
                    metrics[
                        "Median Return %"
                    ],

                "Win Rate %":
                    metrics[
                        "Win Rate %"
                    ],

                "Best Return %":
                    metrics[
                        "Best Return %"
                    ],

                "Worst Return %":
                    metrics[
                        "Worst Return %"
                    ],
            })

        # ----------------------------------------------------
        # Horizon-specific out-of-sample performance.
        # ----------------------------------------------------

        horizons = (
            sorted(
                selected[
                    "days_after"
                ]
                .dropna()
                .unique()
                .tolist()
            )
        )

        for horizon in horizons:

            horizon_df = selected[
                selected[
                    "days_after"
                ]
                ==
                horizon
            ].copy()

            if horizon_df.empty:

                continue

            horizon_oos = horizon_df[
                horizon_df[
                    "Sample"
                ]
                ==
                "OUT OF SAMPLE"
            ].copy()

            if horizon_oos.empty:

                continue

            metrics = calculate_metrics(
                horizon_oos
            )

            rows.append({

                "Weight Set":
                    weight_name,

                "Technical %":
                    weights[
                        "technical_score"
                    ],

                "Quality %":
                    weights[
                        "quality_score"
                    ],

                "Growth %":
                    weights[
                        "growth_score"
                    ],

                "Threshold":
                    threshold,

                "Sample":
                    "OUT OF SAMPLE",

                "Horizon":
                    str(
                        int(
                            horizon
                        )
                    ),

                "Observations":
                    metrics[
                        "Observations"
                    ],

                "Average Return %":
                    metrics[
                        "Average Return %"
                    ],

                "Median Return %":
                    metrics[
                        "Median Return %"
                    ],

                "Win Rate %":
                    metrics[
                        "Win Rate %"
                    ],

                "Best Return %":
                    metrics[
                        "Best Return %"
                    ],

                "Worst Return %":
                    metrics[
                        "Worst Return %"
                    ],
            })

    return pd.DataFrame(
        rows
    )


# ============================================================
# Compare weight sets
# ============================================================

def compare_weight_sets(
    dataframe: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Evaluate all research weight configurations.

    Returns
    -------
    summary_df
        Primary out-of-sample comparison.

    detail_df
        Full threshold / horizon results.

    The primary comparison deliberately reports all thresholds
    rather than assuming 75 is the correct BUY threshold.
    """

    valid_sets = (
        validate_candidate_weight_sets()
    )

    all_results = []

    for name, weights in valid_sets.items():

        print(
            "\nTESTING WEIGHT SET:",
            name,
            weights,
        )

        result = evaluate_weight_set(
            dataframe,
            name,
            weights,
        )

        if not result.empty:

            all_results.append(
                result
            )

    if not all_results:

        return (
            pd.DataFrame(),
            pd.DataFrame(),
        )

    detail_df = pd.concat(
        all_results,
        ignore_index=True,
    )

    # --------------------------------------------------------
    # Primary research view:
    #
    # OUT OF SAMPLE
    # Horizon-specific results
    # All tested thresholds
    # --------------------------------------------------------

    summary_df = detail_df[
        (
            detail_df[
                "Sample"
            ]
            ==
            "OUT OF SAMPLE"
        )
        &
        (
            detail_df[
                "Horizon"
            ]
            !=
            "ALL"
        )
    ].copy()

    if summary_df.empty:

        return (
            summary_df,
            detail_df,
        )

    summary_columns = [
        "Weight Set",
        "Technical %",
        "Quality %",
        "Growth %",
        "Threshold",
        "Horizon",
        "Observations",
        "Average Return %",
        "Median Return %",
        "Win Rate %",
        "Best Return %",
        "Worst Return %",
    ]

    summary_df = summary_df[
        [
            column
            for column in summary_columns
            if column in summary_df.columns
        ]
    ].copy()

    # --------------------------------------------------------
    # Sort by threshold, horizon and then performance.
    # --------------------------------------------------------

    summary_df.sort_values(
        [
            "Threshold",
            "Horizon",
            "Average Return %",
            "Win Rate %",
        ],
        ascending=[
            True,
            True,
            False,
            False,
        ],
        inplace=True,
    )

    summary_df.reset_index(
        drop=True,
        inplace=True,
    )

    return (
        summary_df,
        detail_df,
    )


# ============================================================
# Weight configuration summary
# ============================================================

def create_weight_summary() -> pd.DataFrame:
    """
    Create a simple table of research configurations.
    """

    rows = []

    for name, weights in (
        validate_candidate_weight_sets()
        .items()
    ):

        rows.append({

            "Weight Set":
                name,

            "Technical %":
                weights[
                    "technical_score"
                ],

            "Quality %":
                weights[
                    "quality_score"
                ],

            "Growth %":
                weights[
                    "growth_score"
                ],
        })

    return pd.DataFrame(
        rows
    )


# ============================================================
# Main calibration entry point
# ============================================================

def run_weight_optimizer():
    """
    Run the research calibration.

    IMPORTANT
    ---------
    This function does NOT alter production weights.

    Returns
    -------
    dict

        Learning Records
        Unique Recommendations
        Baseline Weights
        Weight Configurations
        Calibration Summary
        Calibration Detail
    """

    print(
        "WEIGHT CALIBRATION START"
    )

    dataframe = load_learning_data()

    record_count = len(
        dataframe
    )

    recommendation_count = 0

    if (
        not dataframe.empty
        and
        "recommendation_id" in dataframe.columns
    ):

        recommendation_count = (
            dataframe[
                "recommendation_id"
            ]
            .nunique()
        )

    print(
        "Learning records:",
        record_count,
    )

    print(
        "Unique recommendations:",
        recommendation_count,
    )

    if dataframe.empty:

        return {

            "Learning Records":
                0,

            "Unique Recommendations":
                0,

            "Baseline Weights":
                BASELINE_WEIGHTS.copy(),

            "Weight Configurations":
                create_weight_summary(),

            "Calibration Summary":
                pd.DataFrame(),

            "Calibration Detail":
                pd.DataFrame(),
        }

    summary_df, detail_df = (
        compare_weight_sets(
            dataframe
        )
    )

    print(
        "\nBASELINE RESEARCH WEIGHTS:",
        BASELINE_WEIGHTS,
    )

    print(
        "\nWEIGHT CONFIGURATIONS:"
    )

    print(
        create_weight_summary().to_string(
            index=False
        )
    )

    print(
        "\nCALIBRATION SUMMARY:"
    )

    if summary_df.empty:

        print(
            "No out-of-sample horizon results available."
        )

    else:

        print(
            summary_df.to_string(
                index=False
            )
        )

    print(
        "\nWEIGHT CALIBRATION COMPLETE"
    )

        # --------------------------------------------------------
    # Production compatibility
    #
    # Calibration is research-only.
    # Do NOT automatically persist a new weight set.
    #
    # "Recommended Weights" is retained because main.py
    # expects this established interface.
    # It represents the current governed production weights.
    # --------------------------------------------------------

    current_production_weights = get_weights()

    return {

        "Learning Records":
            record_count,

        "Unique Recommendations":
            recommendation_count,

        "Baseline Weights":
            BASELINE_WEIGHTS.copy(),

        "Weight Configurations":
            create_weight_summary(),

        "Calibration Summary":
            summary_df,

        "Calibration Detail":
            detail_df,

        "Recommended Weights":
            current_production_weights,
    }


# ============================================================
# Standalone execution
# ============================================================

if __name__ == "__main__":

    result = run_weight_optimizer()

    print(
        "\n=== BASELINE ==="
    )

    print(
        result[
            "Baseline Weights"
        ]
    )

    print(
        "\n=== CONFIGURATIONS ==="
    )

    configurations = result[
        "Weight Configurations"
    ]

    if (
        isinstance(
            configurations,
            pd.DataFrame,
        )
        and
        not configurations.empty
    ):

        print(
            configurations.to_string(
                index=False
            )
        )

    print(
        "\n=== CALIBRATION SUMMARY ==="
    )

    summary = result[
        "Calibration Summary"
    ]

    if (
        isinstance(
            summary,
            pd.DataFrame,
        )
        and
        not summary.empty
    ):

        print(
            summary.to_string(
                index=False
            )
        )

    else:

        print(
            "No calibration results available."
        )