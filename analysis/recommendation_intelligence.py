"""
Recommendation Intelligence

Purpose
-------
Combines current stock recommendations with historical learning evidence.

This module sits between the recommendation-learning engine and the reporting
layer. It enriches each current stock recommendation with:

- Historical performance of its current signal
- Historical performance of its investment-score bucket
- Component-score learning evidence
- Learning adjustment
- Learning-adjusted investment score
- Recommendation strength
- Confidence
- Intelligence notes

The output is a DataFrame designed for the Recommendation Intelligence
worksheet in the daily report.
"""

import pandas as pd


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_number(value, default=0.0):
    """
    Convert a value to a numeric type safely.
    """
    try:
        if pd.isna(value):
            return default

        return float(value)

    except (TypeError, ValueError):
        return default


def _normalise_text(value):
    """
    Normalise text values for reliable matching.
    """
    if value is None:
        return ""

    if pd.isna(value):
        return ""

    return str(value).strip().upper()


def _find_column(df, possible_names):
    """
    Find the first matching column from a list of possible names.

    This makes the intelligence layer tolerant of small naming differences
    between learning modules.
    """
    if df is None or df.empty:
        return None

    normalised = {
        str(column).strip().lower(): column
        for column in df.columns
    }

    for name in possible_names:

        key = str(name).strip().lower()

        if key in normalised:
            return normalised[key]

    return None


def _get_signal_evidence(
    signal,
    signal_performance,
):
    """
    Return historical evidence for the supplied signal.

    Reliability is derived from the observation count when the
    upstream dataset does not explicitly provide a Reliability
    column. This keeps Recommendation Intelligence aligned with
    recommendation_learning.py.
    """

    MIN_RELIABLE_OBSERVATIONS = 20

    evidence = {
        "observations": 0,
        "average_return": 0.0,
        "win_rate": 0.0,
        "reliability": "NO DATA",
    }

    if (
        signal_performance is None
        or signal_performance.empty
    ):
        return evidence

    signal_column = _find_column(
        signal_performance,
        [
            "Signal",
            "signal",
        ],
    )

    if signal_column is None:
        return evidence

    matching = signal_performance[
        signal_performance[
            signal_column
        ]
        .astype(str)
        .str.strip()
        .str.upper()
        ==
        _normalise_text(signal)
    ]

    if matching.empty:
        return evidence

    row = matching.iloc[0]

    observations_column = _find_column(
        matching,
        [
            "Recommendations",
            "Observations",
            "Evaluations",
            "Count",
            "Sample Size",
        ],
    )

    average_return_column = _find_column(
        matching,
        [
            "Average Return %",
            "Average_Return_Percent",
            "Average Return",
            "Mean Return %",
        ],
    )

    win_rate_column = _find_column(
        matching,
        [
            "Win Rate %",
            "Win_Rate_Percent",
            "Win Rate",
        ],
    )

    reliability_column = _find_column(
        matching,
        [
            "Reliability",
            "Signal Reliability",
        ],
    )

    if observations_column is not None:

        evidence["observations"] = int(
            _safe_number(
                row[
                    observations_column
                ]
            )
        )

    if average_return_column is not None:

        evidence["average_return"] = _safe_number(
            row[
                average_return_column
            ]
        )

    if win_rate_column is not None:

        evidence["win_rate"] = _safe_number(
            row[
                win_rate_column
            ]
        )

    # --------------------------------------------------------
    # Prefer explicit upstream reliability.
    # Otherwise derive it from observation count.
    # --------------------------------------------------------

    if reliability_column is not None:

        reliability = row[
            reliability_column
        ]

        if not pd.isna(
            reliability
        ):

            evidence[
                "reliability"
            ] = str(
                reliability
            ).strip().upper()

    if (
        evidence["reliability"]
        in {
            "NO DATA",
            "",
        }
    ):

        if evidence[
            "observations"
        ] >= MIN_RELIABLE_OBSERVATIONS:

            evidence[
                "reliability"
            ] = "VALID"

        elif evidence[
            "observations"
        ] > 0:

            evidence[
                "reliability"
            ] = "INSUFFICIENT DATA"

        else:

            evidence[
                "reliability"
            ] = "NO DATA"

    return evidence

def _get_score_bucket(
    score,
):
    """
    Convert an investment score into the standard learning bucket.

    Must remain aligned with analysis.recommendation_learning.py.

    Buckets:

        <40
        40-54
        55-69
        70-84
        85-100
    """

    score = _safe_number(
        score,
        default=-1,
    )

    if score < 0:
        return None

    if score < 40:
        return "<40"

    if score < 55:
        return "40-54"

    if score < 70:
        return "55-69"

    if score < 85:
        return "70-84"

    return "85-100"

def _get_score_bucket_evidence(
    score,
    score_bucket_performance,
):
    """
    Return historical evidence for the investment-score bucket.

    Numeric range matching is preferred because it keeps this
    module compatible with the authoritative bucket definitions
    produced by recommendation_learning.py.
    """

    evidence = {
        "observations": 0,
        "average_return": 0.0,
        "win_rate": 0.0,
    }

    if (
        score_bucket_performance is None
        or score_bucket_performance.empty
    ):
        return evidence

    score = _safe_number(
        score,
        default=-1,
    )

    if score < 0:
        return evidence

    bucket = _get_score_bucket(
        score
    )

    minimum_column = _find_column(
        score_bucket_performance,
        [
            "Minimum Score",
            "Minimum_Score",
            "Min Score",
            "Min_Score",
        ],
    )

    maximum_column = _find_column(
        score_bucket_performance,
        [
            "Maximum Score",
            "Maximum_Score",
            "Max Score",
            "Max_Score",
        ],
    )

    bucket_column = _find_column(
        score_bucket_performance,
        [
            "Score Bucket",
            "Score_Bucket",
            "Bucket",
        ],
    )

    matching = pd.DataFrame()

    # --------------------------------------------------------
    # Preferred: numeric bucket range.
    # --------------------------------------------------------

    if (
        minimum_column is not None
        and maximum_column is not None
    ):

        minimums = pd.to_numeric(
            score_bucket_performance[
                minimum_column
            ],
            errors="coerce",
        )

        maximums = pd.to_numeric(
            score_bucket_performance[
                maximum_column
            ],
            errors="coerce",
        )

        matching = score_bucket_performance[
            (minimums <= score)
            &
            (maximums >= score)
        ]

    # --------------------------------------------------------
    # Fallback: exact bucket label.
    # --------------------------------------------------------

    if (
        matching.empty
        and bucket_column is not None
        and bucket is not None
    ):

        matching = score_bucket_performance[
            score_bucket_performance[
                bucket_column
            ]
            .astype(str)
            .str.strip()
            .str.upper()
            ==
            bucket.upper()
        ]

    if matching.empty:
        return evidence

    row = matching.iloc[0]

    observations_column = _find_column(
        matching,
        [
            "Observations",
            "Recommendations",
            "Evaluations",
            "Count",
            "Sample Size",
        ],
    )

    average_return_column = _find_column(
        matching,
        [
            "Average Return %",
            "Average_Return_Percent",
            "Average Return",
            "Mean Return %",
        ],
    )

    win_rate_column = _find_column(
        matching,
        [
            "Win Rate %",
            "Win_Rate_Percent",
            "Win Rate",
        ],
    )

    if observations_column is not None:

        evidence[
            "observations"
        ] = int(
            _safe_number(
                row[
                    observations_column
                ]
            )
        )

    if average_return_column is not None:

        evidence[
            "average_return"
        ] = _safe_number(
            row[
                average_return_column
            ]
        )

    if win_rate_column is not None:

        evidence[
            "win_rate"
        ] = _safe_number(
            row[
                win_rate_column
            ]
        )

    return evidence

def _get_component_evidence(
    component_score_performance
):
    """
    Convert component learning data into a compact representation.

    Component evidence is currently retained as supporting intelligence.
    It is not yet used to alter the recommendation score.
    """

    if (
        component_score_performance is None
        or component_score_performance.empty
    ):
        return "Unavailable"

    return str(
        component_score_performance.to_dict(
            "records"
        )
    )


def _get_base_recommendation_strength(score):
    """
    Determine the base recommendation strength from the raw investment score.
    """

    score = _safe_number(score)

    if score >= 80:
        return "Strong"

    if score >= 65:
        return "Moderate"

    return "Weak"


def _get_confidence(stock):
    """
    Retrieve the existing confidence value from the stock result.
    """

    confidence = stock.get(
        "Confidence",
        "Unknown"
    )

    if confidence is None:
        return "Unknown"

    if pd.isna(confidence):
        return "Unknown"

    return str(confidence)


# ---------------------------------------------------------------------------
# Main function
# ---------------------------------------------------------------------------

def generate_recommendation_intelligence(
    results,
    signal_performance,
    score_bucket_performance,
    component_score_performance,
    horizon_performance=None,
):
    """
    Generate the Recommendation Intelligence DataFrame.

    Parameters
    ----------
    results : list
        Current stock recommendation results.

    signal_performance : pandas.DataFrame
        Historical performance grouped by recommendation signal.

    score_bucket_performance : pandas.DataFrame
        Historical performance grouped by investment-score bucket.

    component_score_performance : pandas.DataFrame
        Historical performance associated with individual score components.

    Returns
    -------
    pandas.DataFrame
        Recommendation Intelligence dataset.
    """

    print(
        "RECOMMENDATION INTELLIGENCE START"
    )

    preferred_horizon = _get_preferred_learning_horizon(
        horizon_performance
    )

    if results is None:

        print(
            "NO RESULTS PROVIDED"
        )

        return pd.DataFrame()

    print(
        f"INPUT RESULTS: {len(results)}"
    )

    if len(results) == 0:

        print(
            "NO RESULTS PROVIDED"
        )

        return pd.DataFrame()

    intelligence = []

    # -----------------------------------------------------------------------
    # Prepare component evidence once.
    # It is supporting evidence and therefore doesn't need to be recalculated
    # for every stock.
    # -----------------------------------------------------------------------

    component_evidence = _get_component_evidence(
        component_score_performance
    )

    # -----------------------------------------------------------------------
    # Process every stock
    # -----------------------------------------------------------------------

    for stock in results:

        if not isinstance(stock, dict):
            continue

        ticker = stock.get(
            "Ticker",
            "UNKNOWN"
        )

        signal = stock.get(
            "Signal",
            "UNKNOWN"
        )

        score = _safe_number(
            stock.get(
                "Investment Score",
                stock.get(
                    "Score",
                    0
                )
            )
        )

        # -------------------------------------------------------------------
        # Base recommendation
        # -------------------------------------------------------------------

        base_strength = (
            _get_base_recommendation_strength(
                score
            )
        )

        confidence = _get_confidence(
            stock
        )

        # -------------------------------------------------------------------
        # Historical signal evidence
        # -------------------------------------------------------------------

        signal_evidence = (
            _get_signal_evidence(
                signal,
                signal_performance
            )
        )

        # -------------------------------------------------------------------
        # Historical score-bucket evidence
        # -------------------------------------------------------------------

        score_bucket = _get_score_bucket(
            score
        )

        score_evidence = (
            _get_score_bucket_evidence(
                score,
                score_bucket_performance
            )
        )

        # -------------------------------------------------------------------
        # Learning adjustment
        #
        # Prefer an adjustment already calculated by the learning engine.
        # This preserves the behaviour currently working in the project.
        # -------------------------------------------------------------------

        learning_adjustment = _safe_number(
            stock.get(
                "Learning Adjustment",
                0
            )
        )

        learning_adjusted_score = (
            stock.get(
                "Learning Adjusted Score",
                score + learning_adjustment
            )
        )

        learning_adjusted_score = _safe_number(
            learning_adjusted_score,
            score + learning_adjustment
        )

        # Keep score inside the normal 0-100 range.

        learning_adjusted_score = max(
            0,
            min(
                100,
                learning_adjusted_score
            )
        )

        # -------------------------------------------------------------------
        # Recommendation strength
        #
        # Preserve the existing learning-engine value if available.
        # Otherwise derive it from the adjusted score.
        # -------------------------------------------------------------------

        recommendation_strength = stock.get(
            "Recommendation Strength",
            None
        )

        if (
            recommendation_strength is None
            or pd.isna(recommendation_strength)
        ):

            recommendation_strength = (
                _get_base_recommendation_strength(
                    learning_adjusted_score
                )
            )

        else:

            recommendation_strength = str(
                recommendation_strength
            )

        # -------------------------------------------------------------------
        # Intelligence notes
        # -------------------------------------------------------------------

        notes = []

        if signal_evidence["observations"] > 0:

            notes.append(
                "Historical signal data available"
            )

        else:

            notes.append(
                "Limited historical signal data"
            )

        if score_evidence["observations"] > 0:

            notes.append(
                "Historical score bucket data available"
            )

        else:

            notes.append(
                "Limited historical score bucket data"
            )

        if (
            learning_adjustment != 0
        ):

            notes.append(
                f"Learning adjustment applied: "
                f"{learning_adjustment:+.0f}"
            )

        if (
            signal_evidence["reliability"]
            == "VALID"
        ):

            notes.append(
                "Signal evidence is statistically valid"
            )

        elif (
            signal_evidence["reliability"]
            == "INSUFFICIENT DATA"
        ):

            notes.append(
                "Signal evidence has insufficient sample size"
            )

        # -------------------------------------------------------------------
        # Construct output row
        # -------------------------------------------------------------------

        row = {

            "Ticker":
                ticker,

            "Signal":
                signal,

            "Investment Score":
                score,

            "Base Recommendation Strength":
                base_strength,

            "Historical Signal Observations":
                signal_evidence[
                    "observations"
                ],

            "Historical Signal Average Return %":
                signal_evidence[
                    "average_return"
                ],

            "Historical Signal Win Rate %":
                signal_evidence[
                    "win_rate"
                ],

            "Historical Signal Reliability":
                signal_evidence[
                    "reliability"
                ],

            "Learning Adjustment":
                learning_adjustment,

            "Learning Adjusted Score":
                learning_adjusted_score,

            "Recommendation Strength":
                recommendation_strength,

            "Score Bucket":
                score_bucket,

            "Score Bucket Observations":
                score_evidence[
                    "observations"
                ],

            "Score Bucket Average Return %":
                score_evidence[
                    "average_return"
                ],

            "Score Bucket Win Rate %":
                score_evidence[
                    "win_rate"
                ],

            "Confidence":
                confidence,

            "Historical Signal Evidence":
                (
                    str(signal_evidence)
                    if signal_evidence["observations"] > 0
                    else "Unavailable"
                ),

            "Score Bucket Evidence":
                (
                    str(score_evidence)
                    if score_evidence["observations"] > 0
                    else "Unavailable"
                ),

            "Component Evidence":
                component_evidence,

            "Intelligence Notes":
                "; ".join(notes),

            "Preferred Learning Horizon":
                preferred_horizon,

            "Learning Horizon Status":
                (
                    f"{preferred_horizon} DAY MATURE"
                    if preferred_horizon is not None
                    else "IMMATURE"
                ),

        }

        intelligence.append(
            row
        )

    # -----------------------------------------------------------------------
    # Create DataFrame
    # -----------------------------------------------------------------------

    df = pd.DataFrame(
        intelligence
    )

    print(
        "FINAL INTELLIGENCE DATAFRAME SIZE: "
        f"{df.shape}"
    )

    if not df.empty:

        print(
            df[
                [
                    "Ticker",
                    "Signal",
                    "Investment Score",
                    "Historical Signal Observations",
                    "Historical Signal Average Return %",
                    "Historical Signal Win Rate %",
                    "Historical Signal Reliability",
                    "Learning Adjustment",
                    "Learning Adjusted Score",
                    "Score Bucket",
                    "Score Bucket Observations",
                ]
            ].head(10)
        )

    print(
        "RECOMMENDATION INTELLIGENCE COMPLETE"
    )

    return df

def _get_preferred_learning_horizon(
    horizon_performance,
):
    """
    Return the highest learning milestone with sufficiently mature data.

    Preference order:

        60
        10
        5

    A milestone is considered mature when it has at least
    MIN_RELIABLE_OBSERVATIONS observations.

    An immature 60-day milestone never displaces mature
    5-day or 10-day evidence.
    """

    if (
        horizon_performance is None
        or horizon_performance.empty
    ):
        return None

    required_columns = {
        "Horizon",
        "Recommendations",
        "Reliability",
    }

    if not required_columns.issubset(
        set(
            horizon_performance.columns
        )
    ):
        return None

    for horizon in (
        60,
        10,
        5,
    ):

        matches = horizon_performance[
            horizon_performance[
                "Horizon"
            ]
            ==
            horizon
        ]

        if matches.empty:
            continue

        row = matches.iloc[0]

        observations = _safe_number(
            row.get(
                "Recommendations",
                0,
            )
        )

        reliability = _normalise_text(
            row.get(
                "Reliability",
                "",
            )
        )

        if (
            observations >= 20
            and
            reliability == "VALID"
        ):
            return horizon

    return None