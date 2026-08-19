"""
Recommendation Learning

Purpose
-------
Analyse completed recommendation outcomes and produce statistical
learning evidence for the stock recommendation engine.

Learning milestones
-------------------
The governed learning horizons are:

    - 5 trading days
    - 10 trading days
    - 60 trading days

Only completed evaluations are treated as learning observations.

Architecture
------------

    recommendations
            |
            v
    outcome_tracker.py
            |
            v
    recommendation_evaluations
            |
            v
    recommendation_learning.py
            |
            v
    recommendation_intelligence.py
            |
            v
    AI Decision Context
            |
            v
    Governed AI Portfolio Decision

Important
---------
- This module learns from completed recommendation evaluations.
- It does not invent results for future milestones.
- Missing 60-day history is treated as immature evidence.
- Historical learning does not automatically rewrite core scoring weights.
- Learning evidence is supporting evidence for downstream decision layers.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# ============================================================
# CONFIGURATION
# ============================================================

MIN_RELIABLE_OBSERVATIONS = 20

SIGNALS = [
    "BUY",
    "STRONG BUY",
    "HOLD",
    "SELL",
    "STRONG SELL",
    "WATCH",
]


SCORE_BUCKETS = [
    ("<40", 0, 39),
    ("40-54", 40, 54),
    ("55-69", 55, 69),
    ("70-84", 70, 84),
    ("85-100", 85, 100),
]


COMPONENTS = [
    ("Technical Score", "technical_score"),
    ("Quality Score", "quality_score"),
    ("Growth Score", "growth_score"),
    ("Confidence Score", "confidence_score"),
    ("Investment Score", "investment_score"),
]


LEARNING_HORIZONS = (
    5,
    10,
    60,
)


# ============================================================
# BASIC HELPERS
# ============================================================

def safe_numeric(series):
    """Convert values to numeric, coercing invalid values to NaN."""

    return pd.to_numeric(
        series,
        errors="coerce",
    )


def reliability_label(count):
    """
    Classify the reliability of a dataset based on observation count.
    """

    count = int(
        safe_numeric(
            count
        )
    )

    if count >= MIN_RELIABLE_OBSERVATIONS:
        return "VALID"

    if count > 0:
        return "INSUFFICIENT DATA"

    return "NO DATA"


def safe_mean(series):
    """Return a rounded mean or zero when no observations exist."""

    values = pd.Series(
        series
    ).dropna()

    if values.empty:
        return 0.0

    return round(
        float(
            values.mean()
        ),
        2,
    )


def safe_median(series):
    """Return a rounded median or zero when no observations exist."""

    values = pd.Series(
        series
    ).dropna()

    if values.empty:
        return 0.0

    return round(
        float(
            values.median()
        ),
        2,
    )


def calculate_win_rate(values):
    """
    Calculate positive-directional-return win rate.

    A recommendation is considered successful for learning purposes
    when its directional return is greater than zero.
    """

    values = pd.Series(
        values
    ).dropna()

    if values.empty:
        return 0.0

    return round(
        float(
            (
                values > 0
            ).mean()
            * 100
        ),
        2,
    )


def safe_correlation(
    df,
    x,
    y,
):
    """Safely calculate correlation between two numeric columns."""

    if x not in df.columns:
        return 0.0

    if y not in df.columns:
        return 0.0

    temp = df[
        [
            x,
            y,
        ]
    ].copy()

    temp[x] = safe_numeric(
        temp[x]
    )

    temp[y] = safe_numeric(
        temp[y]
    )

    temp = temp.dropna()

    if len(temp) < 5:
        return 0.0

    if temp[x].nunique() <= 1:
        return 0.0

    if temp[y].nunique() <= 1:
        return 0.0

    correlation = temp[x].corr(
        temp[y]
    )

    if pd.isna(
        correlation
    ):
        return 0.0

    return round(
        float(
            correlation
        ),
        3,
    )


# ============================================================
# DIRECTION-AWARE RETURN
# ============================================================

def calculate_directional_return(
    signal,
    stock_return,
):
    """
    Convert the underlying stock return into the return relevant
    to the recommendation.

    BUY / STRONG BUY
        Stock +10% -> recommendation +10%

    SELL / STRONG SELL
        Stock +10% -> recommendation -10%

    HOLD / WATCH
        Underlying stock return is retained.

    The important point is that a SELL recommendation followed by
    a rising stock is a LOSS, not a WIN.
    """

    if pd.isna(
        stock_return
    ):
        return np.nan

    signal = str(
        signal
    ).strip().upper()

    stock_return = float(
        stock_return
    )

    if signal in (
        "SELL",
        "STRONG SELL",
    ):
        return -stock_return

    return stock_return


# ============================================================
# SUCCESS / FAILURE
# ============================================================

def calculate_success(
    signal,
    directional_return,
):
    """
    Return:

        1   successful recommendation
        0   unsuccessful recommendation
        NaN insufficient information
    """

    if pd.isna(
        directional_return
    ):
        return np.nan

    return (
        1
        if float(
            directional_return
        ) > 0
        else 0
    )


# ============================================================
# LEARNING DATA SOURCE
# ============================================================

def get_completed_evaluation_history():
    """
    Load the completed recommendation evaluation history.

    This is the preferred source of truth for recommendation learning.

    The raw recommendations table contains recommendations that may
    not yet have realised outcomes. The recommendation_evaluations
    table contains only completed milestone evaluations.
    """

    from data.database import (
        get_evaluation_history,
    )

    history = get_evaluation_history()

    if history is None:
        return pd.DataFrame()

    if not isinstance(
        history,
        pd.DataFrame,
    ):
        history = pd.DataFrame(
            history
        )

    return history


# ============================================================
# NORMALISE HISTORY
# ============================================================

def prepare_learning_data(
    history,
):
    """
    Normalise completed recommendation evaluation history.

    The expected primary input is recommendation_evaluations.

    Important
    ---------
    Learning is performed only on rows containing a realised
    return. Future/uncompleted milestones therefore do not enter
    the statistical learning calculations.
    """

    if history is None:
        return pd.DataFrame()

    if not isinstance(
        history,
        pd.DataFrame,
    ):

        history = pd.DataFrame(
            history
        )

    if history.empty:
        return pd.DataFrame()

    df = history.copy()

    # --------------------------------------------------------
    # Normalise column names
    # --------------------------------------------------------

    df.columns = [
        str(
            column
        ).strip()
        for column in df.columns
    ]

    # --------------------------------------------------------
    # Map database / reporting names to internal names
    # --------------------------------------------------------

    aliases = {

        "Ticker":
            "ticker",

        "ticker":
            "ticker",

        "Recommendation Date":
            "recommendation_date",

        "Date":
            "recommendation_date",

        "date":
            "recommendation_date",

        "Signal":
            "signal",

        "signal":
            "signal",

        "Investment Score":
            "investment_score",

        "investment_score":
            "investment_score",

        "Technical Score":
            "technical_score",

        "technical_score":
            "technical_score",

        "Quality Score":
            "quality_score",

        "quality_score":
            "quality_score",

        "Growth Score":
            "growth_score",

        "growth_score":
            "growth_score",

        "Confidence":
            "confidence",

        "confidence":
            "confidence",

        "Confidence Score":
            "confidence_score",

        "confidence_score":
            "confidence_score",

        "Evaluation Date":
            "evaluation_date",

        "evaluation_date":
            "evaluation_date",

        "Days After":
            "days_after",

        "days_after":
            "days_after",

        "Evaluation Price":
            "evaluation_price",

        "Price":
            "evaluation_price",

        "price":
            "evaluation_price",

        "Evaluation Price £":
            "evaluation_price",

        "Return %":
            "return_percent",

        "Return Percent":
            "return_percent",

        "return_percent":
            "return_percent",

        "Recommendation Return %":
            "recommendation_return_percent",

        "recommendation_return_percent":
            "recommendation_return_percent",

        "Recommendation Success":
            "recommendation_success",

        "recommendation_success":
            "recommendation_success",

        "Outcome":
            "outcome",

        "outcome":
            "outcome",
    }

    for source, target in aliases.items():

        if (
            source in df.columns
            and target not in df.columns
        ):

            df[target] = df[
                source
            ]

    # --------------------------------------------------------
    # Numeric columns
    # --------------------------------------------------------

    numeric_columns = [

        "investment_score",
        "technical_score",
        "quality_score",
        "growth_score",
        "confidence_score",
        "return_percent",
        "recommendation_return_percent",
        "recommendation_success",
        "days_after",
        "evaluation_price",
    ]

    for column in numeric_columns:

        if column in df.columns:

            df[column] = safe_numeric(
                df[column]
            )

    # --------------------------------------------------------
    # Signal
    # --------------------------------------------------------

    if "signal" in df.columns:

        df[
            "signal"
        ] = (
            df[
                "signal"
            ]
            .astype(str)
            .str.strip()
            .str.upper()
        )

    else:

        df[
            "signal"
        ] = "UNKNOWN"

    # --------------------------------------------------------
    # Required learning fields
    # --------------------------------------------------------

    if "return_percent" not in df.columns:

        df[
            "return_percent"
        ] = np.nan

    if "days_after" not in df.columns:

        df[
            "days_after"
        ] = np.nan

    if "investment_score" not in df.columns:

        df[
            "investment_score"
        ] = np.nan

    # --------------------------------------------------------
    # Restrict to governed learning horizons
    # --------------------------------------------------------

    valid_horizons = set(
        LEARNING_HORIZONS
    )

    df = df[
        df[
            "days_after"
        ].isin(
            valid_horizons
        )
        |
        df[
            "days_after"
        ].isna()
    ].copy()

    # --------------------------------------------------------
    # Directional return
    #
    # Prefer the persisted recommendation-adjusted return when
    # available because recommendation_evaluations already stores
    # the correctly direction-adjusted value.
    #
    # Otherwise calculate it from signal + raw return.
    # --------------------------------------------------------

    if (
        "recommendation_return_percent"
        in df.columns
    ):

        persisted_directional_return = safe_numeric(
            df[
                "recommendation_return_percent"
            ]
        )

    else:

        persisted_directional_return = (
            pd.Series(
                np.nan,
                index=df.index,
                dtype=float,
            )
        )

    calculated_directional_return = pd.Series(
        [
            calculate_directional_return(
                signal,
                stock_return,
            )
            for signal, stock_return
            in zip(
                df[
                    "signal"
                ],
                df[
                    "return_percent"
                ],
            )
        ],
        index=df.index,
        dtype=float,
    )

    df[
        "directional_return"
    ] = (
        persisted_directional_return
        .where(
            persisted_directional_return.notna(),
            calculated_directional_return,
        )
    )

    # --------------------------------------------------------
    # Learning success
    # --------------------------------------------------------

    if (
        "recommendation_success"
        in df.columns
    ):

        persisted_success = safe_numeric(
            df[
                "recommendation_success"
            ]
        )

    else:

        persisted_success = pd.Series(
            np.nan,
            index=df.index,
            dtype=float,
        )

    calculated_success = pd.Series(
        [
            calculate_success(
                signal,
                directional_return,
            )
            for signal, directional_return
            in zip(
                df[
                    "signal"
                ],
                df[
                    "directional_return"
                ],
            )
        ],
        index=df.index,
        dtype=float,
    )

    df[
        "learning_success"
    ] = (
        persisted_success
        .where(
            persisted_success.notna(),
            calculated_success,
        )
    )

    # --------------------------------------------------------
    # Ensure historical date fields are usable
    # --------------------------------------------------------

    if "recommendation_date" in df.columns:

        df[
            "recommendation_date"
        ] = pd.to_datetime(
            df[
                "recommendation_date"
            ],
            errors="coerce",
        )

    if "evaluation_date" in df.columns:

        df[
            "evaluation_date"
        ] = pd.to_datetime(
            df[
                "evaluation_date"
            ],
            errors="coerce",
        )

    # --------------------------------------------------------
    # Final learning population
    #
    # Rows without realised directional return are not usable
    # observations and are therefore excluded from statistical
    # learning.
    # --------------------------------------------------------

    df = df[
        df[
            "directional_return"
        ].notna()
    ].copy()

    return df.reset_index(
        drop=True
    )


# ============================================================
# OVERALL PERFORMANCE
# ============================================================

def calculate_overall_performance(
    df,
):
    """Calculate overall recommendation performance."""

    if df is None or df.empty:

        return {
            "Observations":
                0,

            "Average Return %":
                0,

            "Median Return %":
                0,

            "Win Rate %":
                0,

            "Reliability":
                "NO DATA",
        }

    returns = (
        df[
            "directional_return"
        ]
        .dropna()
    )

    count = len(
        returns
    )

    return {

        "Observations":
            count,

        "Average Return %":
            safe_mean(
                returns
            ),

        "Median Return %":
            safe_median(
                returns
            ),

        "Win Rate %":
            calculate_win_rate(
                returns
            ),

        "Reliability":
            reliability_label(
                count
            ),
    }


# ============================================================
# HORIZON PERFORMANCE
# ============================================================

def calculate_horizon_performance(
    df,
):
    """
    Calculate learning performance for:

        5 trading days
        10 trading days
        60 trading days

    A milestone with no completed observations is classified as
    IMMATURE when the available dataset has not yet reached that
    horizon.

    It is never treated as negative evidence.
    """

    columns = [
        "Horizon",
        "Recommendations",
        "Average Return %",
        "Median Return %",
        "Win Rate %",
        "Reliability",
        "Milestone Status",
    ]

    if (
        df is None
        or df.empty
        or "days_after" not in df.columns
    ):

        working = pd.DataFrame()

    else:

        working = df.dropna(
            subset=[
                "days_after"
            ]
        ).copy()

        working[
            "days_after"
        ] = safe_numeric(
            working[
                "days_after"
            ]
        )

    max_available_horizon = 0

    if not working.empty:

        valid_horizons = (
            working[
                "days_after"
            ]
            .dropna()
            .astype(int)
            .tolist()
        )

        if valid_horizons:

            max_available_horizon = max(
                valid_horizons
            )

    rows = []

    for horizon in LEARNING_HORIZONS:

        if working.empty:

            group = pd.DataFrame()

        else:

            group = working[
                working[
                    "days_after"
                ]
                ==
                horizon
            ]

        returns = (
            group[
                "directional_return"
            ]
            .dropna()
            if not group.empty
            else pd.Series(
                dtype=float
            )
        )

        count = len(
            returns
        )

        if count > 0:

            reliability = (
                reliability_label(
                    count
                )
            )

            milestone_status = (
                "MATURE"
                if count >= MIN_RELIABLE_OBSERVATIONS
                else "IMMATURE"
            )

        elif max_available_horizon < horizon:

            reliability = "IMMATURE"
            milestone_status = "IMMATURE"

        else:

            reliability = "NO DATA"
            milestone_status = "NO DATA"

        rows.append(
            {
                "Horizon":
                    horizon,

                "Recommendations":
                    count,

                "Average Return %":
                    safe_mean(
                        returns
                    ),

                "Median Return %":
                    safe_median(
                        returns
                    ),

                "Win Rate %":
                    calculate_win_rate(
                        returns
                    ),

                "Reliability":
                    reliability,

                "Milestone Status":
                    milestone_status,
            }
        )

    return pd.DataFrame(
        rows,
        columns=columns,
    )


# ============================================================
# SIGNAL PERFORMANCE
# ============================================================

def calculate_signal_performance(
    df,
):
    """Calculate performance grouped by recommendation signal."""

    columns = [
        "Signal",
        "Recommendations",
        "Average Return %",
        "Median Return %",
        "Win Rate %",
        "Reliability",
    ]

    if df is None or df.empty:

        return pd.DataFrame(
            columns=columns
        )

    rows = []

    for signal in SIGNALS:

        group = df[
            df[
                "signal"
            ]
            ==
            signal
        ]

        returns = (
            group[
                "directional_return"
            ]
            .dropna()
        )

        count = len(
            returns
        )

        rows.append(
            {
                "Signal":
                    signal,

                "Recommendations":
                    count,

                "Average Return %":
                    safe_mean(
                        returns
                    ),

                "Median Return %":
                    safe_median(
                        returns
                    ),

                "Win Rate %":
                    calculate_win_rate(
                        returns
                    ),

                "Reliability":
                    reliability_label(
                        count
                    ),
            }
        )

    return (
        pd.DataFrame(
            rows
        )
        .sort_values(
            "Average Return %",
            ascending=False,
        )
        .reset_index(
            drop=True
        )
    )


# ============================================================
# SIGNAL RELIABILITY
# ============================================================

def calculate_signal_reliability(
    df,
):
    """Calculate signal reliability statistics."""

    if df is None or df.empty:

        return pd.DataFrame()

    rows = []

    for signal in SIGNALS:

        group = df[
            df[
                "signal"
            ]
            ==
            signal
        ]

        returns = (
            group[
                "directional_return"
            ]
            .dropna()
        )

        count = len(
            returns
        )

        rows.append(
            {
                "Signal":
                    signal,

                "Observations":
                    count,

                "Average Return %":
                    safe_mean(
                        returns
                    ),

                "Win Rate %":
                    calculate_win_rate(
                        returns
                    ),

                "Reliability":
                    reliability_label(
                        count
                    ),
            }
        )

    return (
        pd.DataFrame(
            rows
        )
        .sort_values(
            "Average Return %",
            ascending=False,
        )
        .reset_index(
            drop=True
        )
    )


# ============================================================
# SCORE BUCKET
# ============================================================

def get_score_bucket(
    score,
):
    """Map an investment/component score to its learning bucket."""

    if pd.isna(
        score
    ):
        return None

    score = float(
        score
    )

    if score < 40:
        return "<40"

    if score < 55:
        return "40-54"

    if score < 70:
        return "55-69"

    if score < 85:
        return "70-84"

    return "85-100"


# ============================================================
# SCORE BUCKET PERFORMANCE
# ============================================================

def calculate_score_bucket_performance(
    df,
):
    """Calculate realised performance by investment-score bucket."""

    columns = [
        "Score Bucket",
        "Minimum Score",
        "Maximum Score",
        "Observations",
        "Average Return %",
        "Median Return %",
        "Win Rate %",
        "Reliability",
    ]

    if (
        df is None
        or df.empty
        or "investment_score" not in df.columns
    ):

        return pd.DataFrame(
            columns=columns
        )

    temp = df.copy()

    temp[
        "investment_score"
    ] = safe_numeric(
        temp[
            "investment_score"
        ]
    )

    temp[
        "Score Bucket"
    ] = (
        temp[
            "investment_score"
        ]
        .apply(
            get_score_bucket
        )
    )

    rows = []

    for bucket, minimum, maximum in SCORE_BUCKETS:

        group = temp[
            temp[
                "Score Bucket"
            ]
            ==
            bucket
        ]

        returns = (
            group[
                "directional_return"
            ]
            .dropna()
        )

        count = len(
            returns
        )

        rows.append(
            {
                "Score Bucket":
                    bucket,

                "Minimum Score":
                    minimum,

                "Maximum Score":
                    maximum,

                "Observations":
                    count,

                "Average Return %":
                    safe_mean(
                        returns
                    ),

                "Median Return %":
                    safe_median(
                        returns
                    ),

                "Win Rate %":
                    calculate_win_rate(
                        returns
                    ),

                "Reliability":
                    reliability_label(
                        count
                    ),
            }
        )

    return pd.DataFrame(
        rows,
        columns=columns,
    )


# ============================================================
# COMPONENT SCORE PERFORMANCE
# ============================================================

def calculate_component_score_performance(
    df,
):
    """Calculate realised performance for component score buckets."""

    columns = [
        "Component",
        "Component Score Bucket",
        "Minimum Score",
        "Maximum Score",
        "Observations",
        "Average Return %",
        "Win Rate %",
        "Reliability",
    ]

    if df is None or df.empty:

        return pd.DataFrame(
            columns=columns
        )

    rows = []

    for component_name, column in COMPONENTS:

        if column not in df.columns:
            continue

        temp = df.copy()

        temp[
            "Score Bucket"
        ] = (
            safe_numeric(
                temp[
                    column
                ]
            )
            .apply(
                get_score_bucket
            )
        )

        for bucket, minimum, maximum in SCORE_BUCKETS:

            group = temp[
                temp[
                    "Score Bucket"
                ]
                ==
                bucket
            ]

            returns = (
                group[
                    "directional_return"
                ]
                .dropna()
            )

            count = len(
                returns
            )

            rows.append(
                {
                    "Component":
                        component_name,

                    "Component Score Bucket":
                        bucket,

                    "Minimum Score":
                        minimum,

                    "Maximum Score":
                        maximum,

                    "Observations":
                        count,

                    "Average Return %":
                        safe_mean(
                            returns
                        ),

                    "Win Rate %":
                        calculate_win_rate(
                            returns
                        ),

                    "Reliability":
                        reliability_label(
                            count
                        ),
                }
            )

    return pd.DataFrame(
        rows,
        columns=columns,
    )


# ============================================================
# CONFIDENCE PERFORMANCE
# ============================================================

def get_confidence_bucket(
    score,
):
    """Map confidence score into a standard learning bucket."""

    if pd.isna(
        score
    ):
        return None

    score = float(
        score
    )

    if score < 40:
        return "0-39"

    if score < 60:
        return "40-59"

    if score < 80:
        return "60-79"

    if score < 90:
        return "80-89"

    return "90-100"


def calculate_confidence_performance(
    df,
):
    """Calculate realised performance by confidence-score bucket."""

    columns = [
        "Confidence Bucket",
        "Minimum Score",
        "Observations",
        "Average Return %",
        "Median Return %",
        "Win Rate %",
        "Reliability",
    ]

    if (
        df is None
        or df.empty
        or "confidence_score" not in df.columns
    ):

        return pd.DataFrame(
            columns=columns
        )

    temp = df.copy()

    temp[
        "Confidence Bucket"
    ] = (
        safe_numeric(
            temp[
                "confidence_score"
            ]
        )
        .apply(
            get_confidence_bucket
        )
    )

    buckets = [
        ("0-39", 0),
        ("40-59", 40),
        ("60-79", 60),
        ("80-89", 80),
        ("90-100", 90),
    ]

    rows = []

    for bucket, minimum in buckets:

        group = temp[
            temp[
                "Confidence Bucket"
            ]
            ==
            bucket
        ]

        returns = (
            group[
                "directional_return"
            ]
            .dropna()
        )

        count = len(
            returns
        )

        rows.append(
            {
                "Confidence Bucket":
                    bucket,

                "Minimum Score":
                    minimum,

                "Observations":
                    count,

                "Average Return %":
                    safe_mean(
                        returns
                    ),

                "Median Return %":
                    safe_median(
                        returns
                    ),

                "Win Rate %":
                    calculate_win_rate(
                        returns
                    ),

                "Reliability":
                    reliability_label(
                        count
                    ),
            }
        )

    return pd.DataFrame(
        rows,
        columns=columns,
    )


# ============================================================
# SIGNAL + HORIZON
# ============================================================

def calculate_signal_horizon_performance(
    df,
):
    """Calculate signal performance separately for each learning horizon."""

    if df is None or df.empty:

        return pd.DataFrame()

    rows = []

    for signal in SIGNALS:

        signal_df = df[
            df[
                "signal"
            ]
            ==
            signal
        ]

        horizons = sorted(
            set(
                safe_numeric(
                    signal_df[
                        "days_after"
                    ]
                )
                .dropna()
                .astype(int)
                .tolist()
            )
            & set(
                LEARNING_HORIZONS
            )
        )

        for horizon in horizons:

            group = signal_df[
                safe_numeric(
                    signal_df[
                        "days_after"
                    ]
                )
                ==
                horizon
            ]

            returns = (
                group[
                    "directional_return"
                ]
                .dropna()
            )

            count = len(
                returns
            )

            rows.append(
                {
                    "Signal":
                        signal,

                    "Days After":
                        horizon,

                    "Recommendations":
                        count,

                    "Average Return %":
                        safe_mean(
                            returns
                        ),

                    "Win Rate %":
                        calculate_win_rate(
                            returns
                        ),

                    "Reliability":
                        reliability_label(
                            count
                        ),
                }
            )

    return pd.DataFrame(
        rows
    )


# ============================================================
# SCORE + HORIZON
# ============================================================

def calculate_score_horizon_performance(
    df,
):
    """Calculate score-bucket performance separately by horizon."""

    if df is None or df.empty:

        return pd.DataFrame()

    temp = df.copy()

    temp[
        "investment_score"
    ] = safe_numeric(
        temp[
            "investment_score"
        ]
    )

    temp[
        "Score Bucket"
    ] = (
        temp[
            "investment_score"
        ]
        .apply(
            get_score_bucket
        )
    )

    rows = []

    for bucket, minimum, maximum in SCORE_BUCKETS:

        bucket_df = temp[
            temp[
                "Score Bucket"
            ]
            ==
            bucket
        ]

        horizons = sorted(
            set(
                safe_numeric(
                    bucket_df[
                        "days_after"
                    ]
                )
                .dropna()
                .astype(int)
                .tolist()
            )
            & set(
                LEARNING_HORIZONS
            )
        )

        for horizon in horizons:

            group = bucket_df[
                safe_numeric(
                    bucket_df[
                        "days_after"
                    ]
                )
                ==
                horizon
            ]

            returns = (
                group[
                    "directional_return"
                ]
                .dropna()
            )

            count = len(
                returns
            )

            rows.append(
                {
                    "Score Bucket":
                        bucket,

                    "Days After":
                        horizon,

                    "Observations":
                        count,

                    "Average Return %":
                        safe_mean(
                            returns
                        ),

                    "Win Rate %":
                        calculate_win_rate(
                            returns
                        ),

                    "Reliability":
                        reliability_label(
                            count
                        ),
                }
            )

    return pd.DataFrame(
        rows
    )


# ============================================================
# CORRELATION ANALYSIS
# ============================================================

def calculate_score_correlations(
    df,
):
    """Calculate score correlation with directional return by horizon."""

    if df is None or df.empty:

        return pd.DataFrame()

    rows = []

    horizons = sorted(
        set(
            safe_numeric(
                df[
                    "days_after"
                ]
            )
            .dropna()
            .astype(int)
            .tolist()
        )
        & set(
            LEARNING_HORIZONS
        )
    )

    for horizon in horizons:

        horizon_df = df[
            safe_numeric(
                df[
                    "days_after"
                ]
            )
            ==
            horizon
        ]

        for component_name, column in COMPONENTS:

            if column not in horizon_df.columns:
                continue

            valid = horizon_df[
                [
                    column,
                    "directional_return",
                ]
            ].dropna()

            if len(
                valid
            ) < 20:

                correlation = None

            else:

                correlation = safe_correlation(
                    horizon_df,
                    column,
                    "directional_return",
                )

            rows.append(
                {
                    "Days After":
                        horizon,

                    "Component":
                        column,

                    "Correlation":
                        correlation,

                    "Observations":
                        len(valid),

                    "Reliability":
                        reliability_label(
                            len(valid)
                        ),
                }
            )

    return pd.DataFrame(
        rows
    )


# ============================================================
# COMPONENT CORRELATION SUMMARY
# ============================================================

def calculate_component_correlations(
    df,
):
    """Calculate overall component correlation with directional return."""

    if df is None or df.empty:

        return pd.DataFrame()

    rows = []

    for component_name, column in COMPONENTS:

        if column not in df.columns:
            continue

        valid = df[
            [
                column,
                "directional_return",
            ]
        ].dropna()

        correlation = safe_correlation(
            df,
            column,
            "directional_return",
        )

        rows.append(
            {
                "Component":
                    column,

                "Correlation":
                    correlation,

                "Observations":
                    len(valid),

                "Reliability":
                    reliability_label(
                        len(valid)
                    ),
            }
        )

    return pd.DataFrame(
        rows
    )


# ============================================================
# DIAGNOSTIC OUTPUT
# ============================================================

def run_diagnostic(
    history=None,
    print_output=True,
):
    """
    Run a recommendation-learning diagnostic.

    When no history is supplied, completed recommendation evaluations
    are loaded directly from recommendation_evaluations.
    """

    if history is None:

        history = (
            get_completed_evaluation_history()
        )

    df = prepare_learning_data(
        history
    )

    if df.empty:

        if print_output:

            print(
                "\nNo completed recommendation learning data available.\n"
            )

        return {}

    horizon = (
        calculate_horizon_performance(
            df
        )
    )

    score = (
        calculate_score_bucket_performance(
            df
        )
    )

    signal = (
        calculate_signal_horizon_performance(
            df
        )
    )

    technical = (
        calculate_component_bucket(
            df,
            "technical_score",
            "Technical Bucket",
        )
    )

    quality = (
        calculate_component_bucket(
            df,
            "quality_score",
            "Quality Bucket",
        )
    )

    growth = (
        calculate_component_bucket(
            df,
            "growth_score",
            "Growth Bucket",
        )
    )

    confidence = (
        calculate_confidence_performance(
            df
        )
    )

    correlations = (
        calculate_score_correlations(
            df
        )
    )

    if print_output:

        print(
            "=" * 90
        )

        print(
            "RECOMMENDATION LEARNING DIAGNOSTIC"
        )

        print(
            "=" * 90
        )

        print(
            f"\nTotal completed evaluations: "
            f"{len(df):,}"
        )

        print(
            "\n" + "=" * 90
        )

        print(
            "1. PERFORMANCE BY HORIZON"
        )

        print(
            "=" * 90
        )

        print(
            horizon.to_string(
                index=False
            )
        )

        print(
            "\n" + "=" * 90
        )

        print(
            "2. PERFORMANCE BY INVESTMENT SCORE"
        )

        print(
            "=" * 90
        )

        print(
            score.to_string(
                index=False
            )
        )

        print(
            "\n" + "=" * 90
        )

        print(
            "3. PERFORMANCE BY SIGNAL"
        )

        print(
            "=" * 90
        )

        print(
            calculate_signal_performance(
                df
            ).to_string(
                index=False
            )
        )

        print(
            "\n" + "=" * 90
        )

        print(
            "4. PERFORMANCE BY TECHNICAL SCORE"
        )

        print(
            "=" * 90
        )

        print(
            technical.to_string(
                index=False
            )
        )

        print(
            "\n" + "=" * 90
        )

        print(
            "5. PERFORMANCE BY QUALITY SCORE"
        )

        print(
            "=" * 90
        )

        print(
            quality.to_string(
                index=False
            )
        )

        print(
            "\n" + "=" * 90
        )

        print(
            "6. PERFORMANCE BY GROWTH SCORE"
        )

        print(
            "=" * 90
        )

        print(
            growth.to_string(
                index=False
            )
        )

        print(
            "\n" + "=" * 90
        )

        print(
            "7. PERFORMANCE BY CONFIDENCE SCORE"
        )

        print(
            "=" * 90
        )

        print(
            confidence.to_string(
                index=False
            )
        )

        print(
            "\n" + "=" * 90
        )

        print(
            "8. SCORE CORRELATION WITH DIRECTIONAL RETURN"
        )

        print(
            "=" * 90
        )

        if correlations.empty:

            print(
                "No horizon correlation data available."
            )

        else:

            for horizon_value in sorted(
                correlations[
                    "Days After"
                ]
                .dropna()
                .unique()
            ):

                print(
                    f"\n{int(horizon_value)}D:"
                )

                temp = correlations[
                    correlations[
                        "Days After"
                    ]
                    ==
                    horizon_value
                ]

                for _, row in temp.iterrows():

                    if pd.isna(
                        row[
                            "Correlation"
                        ]
                    ):

                        print(
                            f"  {row['Component']}: "
                            f"insufficient data"
                        )

                    else:

                        print(
                            f"  {row['Component']}: "
                            f"{row['Correlation']:.3f} "
                            f"({int(row['Observations']):,} observations)"
                        )

        print(
            "\n" + "=" * 90
        )

        print(
            "9. SIGNAL RANKING"
        )

        print(
            "=" * 90
        )

        print(
            signal.to_string(
                index=False
            )
        )

        print(
            "\n" + "=" * 90
        )

        print(
            "10. LEARNING SUMMARY"
        )

        print(
            "=" * 90
        )

        for _, row in horizon.iterrows():

            print(
                f"\n{int(row['Horizon'])}D observations: "
                f"{int(row['Recommendations']):,}"
            )

            print(
                f"{int(row['Horizon'])}D average "
                f"directional return: "
                f"{row['Average Return %']:.2f}%"
            )

            print(
                f"{int(row['Horizon'])}D win rate: "
                f"{row['Win Rate %']:.1f}%"
            )

            print(
                f"{int(row['Horizon'])}D status: "
                f"{row['Milestone Status']}"
            )

        print(
            "\nDIAGNOSTIC COMPLETE"
        )

    return {

        "data":
            df,

        "Overall":
            calculate_overall_performance(
                df
            ),

        "Horizon Learning":
            horizon,

        "Signal Performance":
            calculate_signal_performance(
                df
            ),

        "Signal Reliability":
            calculate_signal_reliability(
                df
            ),

        "Score Bucket Performance":
            score,

        "Score Horizon Performance":
            calculate_score_horizon_performance(
                df
            ),

        "Signal Horizon Performance":
            calculate_signal_horizon_performance(
                df
            ),

        "Component Score Performance":
            calculate_component_score_performance(
                df
            ),

        "Confidence Performance":
            confidence,

        "Technical Performance":
            technical,

        "Quality Performance":
            quality,

        "Growth Performance":
            growth,

        "Score Correlations":
            correlations,

        "Component Correlations":
            calculate_component_correlations(
                df
            ),
    }


# ============================================================
# GENERIC COMPONENT BUCKET ANALYSIS
# ============================================================

def calculate_component_bucket(
    df,
    column,
    bucket_column_name,
):
    """Calculate performance by a generic score-component bucket."""

    if (
        df is None
        or df.empty
        or column not in df.columns
    ):

        return pd.DataFrame()

    temp = df.copy()

    temp[
        bucket_column_name
    ] = (
        safe_numeric(
            temp[
                column
            ]
        )
        .apply(
            get_component_bucket
        )
    )

    bucket_order = [
        "<40",
        "40-54",
        "55-69",
        "70-84",
        "85-100",
    ]

    rows = []

    for bucket in bucket_order:

        group = temp[
            temp[
                bucket_column_name
            ]
            ==
            bucket
        ]

        returns = (
            group[
                "directional_return"
            ]
            .dropna()
        )

        count = len(
            returns
        )

        rows.append(
            {
                bucket_column_name:
                    bucket,

                "Observations":
                    count,

                "Average Return %":
                    safe_mean(
                        returns
                    ),

                "Median Return %":
                    safe_median(
                        returns
                    ),

                "Win Rate %":
                    calculate_win_rate(
                        returns
                    ),

                "Reliability":
                    reliability_label(
                        count
                    ),
            }
        )

    return pd.DataFrame(
        rows
    )


def get_component_bucket(
    score,
):
    """Map a component score into the standard score bucket."""

    if pd.isna(
        score
    ):
        return None

    score = float(
        score
    )

    if score < 40:
        return "<40"

    if score < 55:
        return "40-54"

    if score < 70:
        return "55-69"

    if score < 85:
        return "70-84"

    return "85-100"


# ============================================================
# MAIN LEARNING FUNCTION
# ============================================================

def calculate_recommendation_learning(
    history=None,
):
    """
    Main production interface used by main.py.

    Parameters
    ----------
    history:
        Optional completed evaluation history.

        When omitted, recommendation_evaluations is loaded directly.

        Passing an explicit DataFrame remains supported for compatibility.

    Returns
    -------
    dict
        Complete recommendation learning model.
    """

    if history is None:

        history = (
            get_completed_evaluation_history()
        )

    print(
        "\nRECOMMENDATION LEARNING INPUT:",
        len(history)
        if history is not None
        else 0,
    )

    df = prepare_learning_data(
        history
    )

    if df.empty:

        print(
            "RECOMMENDATION LEARNING: NO COMPLETED EVALUATIONS"
        )

        return {

            "Overall": {
                "Observations": 0,
                "Average Return %": 0,
                "Median Return %": 0,
                "Win Rate %": 0,
                "Reliability": "NO DATA",
            },

            "Horizon Learning":
                pd.DataFrame(),

            "Signal Performance":
                pd.DataFrame(),

            "Signal Reliability":
                pd.DataFrame(),

            "Score Bucket Performance":
                pd.DataFrame(),

            "Score Horizon Performance":
                pd.DataFrame(),

            "Signal Horizon Performance":
                pd.DataFrame(),

            "Component Score Performance":
                pd.DataFrame(),

            "Confidence Performance":
                pd.DataFrame(),

            "Technical Performance":
                pd.DataFrame(),

            "Quality Performance":
                pd.DataFrame(),

            "Growth Performance":
                pd.DataFrame(),

            "Score Correlations":
                pd.DataFrame(),

            "Component Correlations":
                pd.DataFrame(),
        }

    print(
        "RECOMMENDATION LEARNING PREPARED:",
        len(df),
    )

    if "signal" in df.columns:

        print(
            "SIGNAL COUNTS:"
        )

        print(
            df[
                "signal"
            ].value_counts()
        )

    if "days_after" in df.columns:

        print(
            "DAYS AFTER COUNTS:"
        )

        print(
            df[
                "days_after"
            ].value_counts()
            .sort_index()
        )

    # --------------------------------------------------------
    # Calculate all learning outputs
    # --------------------------------------------------------

    overall = (
        calculate_overall_performance(
            df
        )
    )

    horizon_learning = (
        calculate_horizon_performance(
            df
        )
    )

    signal_performance = (
        calculate_signal_performance(
            df
        )
    )

    signal_reliability = (
        calculate_signal_reliability(
            df
        )
    )

    score_bucket_performance = (
        calculate_score_bucket_performance(
            df
        )
    )

    score_horizon_performance = (
        calculate_score_horizon_performance(
            df
        )
    )

    signal_horizon_performance = (
        calculate_signal_horizon_performance(
            df
        )
    )

    component_score_performance = (
        calculate_component_score_performance(
            df
        )
    )

    confidence_performance = (
        calculate_confidence_performance(
            df
        )
    )

    technical_performance = (
        calculate_component_bucket(
            df,
            "technical_score",
            "Technical Bucket",
        )
    )

    quality_performance = (
        calculate_component_bucket(
            df,
            "quality_score",
            "Quality Bucket",
        )
    )

    growth_performance = (
        calculate_component_bucket(
            df,
            "growth_score",
            "Growth Bucket",
        )
    )

    score_correlations = (
        calculate_score_correlations(
            df
        )
    )

    component_correlations = (
        calculate_component_correlations(
            df
        )
    )

    # --------------------------------------------------------
    # Diagnostic console output
    # --------------------------------------------------------

    print(
        "Overall:",
        overall,
    )

    print(
        "Horizon Learning:",
        horizon_learning,
    )

    print(
        "Signal Performance:",
        signal_performance,
    )

    print(
        "Signal Reliability:",
        signal_reliability,
    )

    print(
        "Score Bucket Performance:",
        score_bucket_performance,
    )

    print(
        "Score Horizon Performance:",
        score_horizon_performance,
    )

    print(
        "Signal Horizon Performance:",
        signal_horizon_performance,
    )

    print(
        "Component Score Performance:",
        component_score_performance,
    )

    print(
        "Confidence Performance:",
        confidence_performance,
    )

    return {

        "Overall":
            overall,

        "Horizon Learning":
            horizon_learning,

        "Signal Performance":
            signal_performance,

        "Signal Reliability":
            signal_reliability,

        "Score Bucket Performance":
            score_bucket_performance,

        "Score Horizon Performance":
            score_horizon_performance,

        "Signal Horizon Performance":
            signal_horizon_performance,

        "Component Score Performance":
            component_score_performance,

        "Confidence Performance":
            confidence_performance,

        "Technical Performance":
            technical_performance,

        "Quality Performance":
            quality_performance,

        "Growth Performance":
            growth_performance,

        "Score Correlations":
            score_correlations,

        "Component Correlations":
            component_correlations,
    }


# ============================================================
# LEARNING MILESTONE STATUS
# ============================================================

def get_learning_milestone_status(
    horizon_performance,
):
    """
    Summarise the current maturity of the governed learning milestones.

    Returns one record for each of:

        5
        10
        60

    Also identifies the highest mature milestone.
    """

    horizons = list(
        LEARNING_HORIZONS
    )

    records = []

    highest_mature_horizon = None

    if (
        horizon_performance is None
        or horizon_performance.empty
    ):

        horizon_lookup = {}

    else:

        horizon_lookup = {}

        for _, row in horizon_performance.iterrows():

            try:

                horizon = int(
                    row[
                        "Horizon"
                    ]
                )

            except (
                TypeError,
                ValueError,
            ):

                continue

            horizon_lookup[
                horizon
            ] = row.to_dict()

    for horizon in horizons:

        row = horizon_lookup.get(
            horizon,
            {},
        )

        observations = int(
            safe_numeric(
                row.get(
                    "Recommendations",
                    0,
                )
            )
        )

        reliability = str(
            row.get(
                "Reliability",
                "IMMATURE",
            )
        ).strip().upper()

        status = str(
            row.get(
                "Milestone Status",
                "IMMATURE",
            )
        ).strip().upper()

        if (
            reliability == "VALID"
            and
            observations >= MIN_RELIABLE_OBSERVATIONS
        ):

            highest_mature_horizon = max(
                highest_mature_horizon or 0,
                horizon,
            )

        records.append(
            {
                "Horizon":
                    horizon,

                "Observations":
                    observations,

                "Reliability":
                    reliability,

                "Status":
                    status,

                "Average Return %":
                    safe_numeric(
                        row.get(
                            "Average Return %",
                            0,
                        )
                    ),

                "Median Return %":
                    safe_numeric(
                        row.get(
                            "Median Return %",
                            0,
                        )
                    ),

                "Win Rate %":
                    safe_numeric(
                        row.get(
                            "Win Rate %",
                            0,
                        )
                    ),
            }
        )

    return {

        "milestones":
            records,

        "highest_mature_horizon":
            highest_mature_horizon,
    }


# ============================================================
# STANDALONE EXECUTION
# ============================================================

if __name__ == "__main__":

    history = (
        get_completed_evaluation_history()
    )

    print(
        "\nLoaded completed evaluation history:",
        len(history),
    )

    run_diagnostic(
        history
    )