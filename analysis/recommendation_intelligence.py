
"""
Recommendation Intelligence

Purpose
-------
Combines current stock recommendations with historical learning evidence.

This module sits between the recommendation-learning engine and the reporting
and governed decision layers.

It enriches each current stock recommendation with:

- Historical performance of its current signal
- Historical performance of its Investment Score bucket
- Component-score learning evidence
- Evidence maturity
- Learning adjustment
- Learning-adjusted Investment Score
- Recommendation strength
- Preferred learning horizon
- Preferred-horizon observations
- Preferred-horizon win rate
- Preferred-horizon average return
- Preferred-horizon reliability
- Intelligence notes

Design Principles
-----------------
1. The raw Investment Score is NEVER modified.
2. Historical learning is supporting evidence, not a replacement for the
   underlying scoring model.
3. Stock-specific signal evidence is more relevant than broad score-bucket
   evidence and therefore receives greater weight when available.
4. Score-bucket evidence provides a stabilising fallback and cross-sectional
   calibration signal.
5. Observation count determines evidence maturity/reliability. It does NOT
   directly increase the size of the learning adjustment.
6. Learning adjustments are deliberately bounded to avoid allowing historical
   learning to manufacture conviction.
7. The preferred learning horizon is the highest mature horizon available:
   60D -> 10D -> 5D.
8. Missing or immature 60D evidence is NOT invented or substituted with fake
   60D values. The next mature horizon is used.
9. The module remains compatible with the existing Recommendation Learning
   and Excel reporting pipeline.
"""

from __future__ import annotations

import pandas as pd


# ============================================================================
# CONFIGURATION
# ============================================================================

MIN_RELIABLE_OBSERVATIONS = 20

MIN_SCORE = 0.0
MAX_SCORE = 100.0

# Learning adjustment governance.
LEARNING_RETURN_MULTIPLIER = 3.0

MAX_LEARNING_ADJUSTMENT = 10.0
MIN_LEARNING_ADJUSTMENT = -10.0

# When both signal and score-bucket evidence are available, stock-specific
# signal evidence receives the larger weight.
SIGNAL_EVIDENCE_WEIGHT = 0.60
SCORE_BUCKET_EVIDENCE_WEIGHT = 0.40

# Evidence confidence reaches full strength once the sample reaches this
# observation count.
FULL_EVIDENCE_OBSERVATIONS = 100

# Minimum confidence floor for statistically valid evidence.
MIN_VALID_EVIDENCE_CONFIDENCE = 0.50


# ============================================================================
# BASIC HELPERS
# ============================================================================

def _safe_number(value, default=0.0):
    """Safely convert a value to float."""
    try:
        if value is None:
            return default

        if pd.isna(value):
            return default

        return float(value)

    except (TypeError, ValueError):
        return default


def _clamp_score(value):
    """Clamp a score to the governed 0-100 range."""
    value = _safe_number(value)

    return max(
        MIN_SCORE,
        min(
            MAX_SCORE,
            value,
        ),
    )


def _clamp_adjustment(value):
    """Clamp a learning adjustment to the governed +/-10 range."""
    value = _safe_number(value)

    return max(
        MIN_LEARNING_ADJUSTMENT,
        min(
            MAX_LEARNING_ADJUSTMENT,
            value,
        ),
    )


def _normalise_text(value):
    """Normalise text values for reliable comparisons."""
    if value is None:
        return ""

    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass

    return str(value).strip().upper()


def _find_column(df, possible_names):
    """
    Find the first matching column from a list of possible names.

    Matching is case-insensitive and whitespace-insensitive.
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


# ============================================================================
# EVIDENCE CONFIDENCE
# ============================================================================

def _evidence_confidence(observations):
    """
    Convert an observation count into evidence confidence.

    Observation count is used only to determine how much trust to place in
    historical evidence.

    It does NOT increase the learning adjustment by itself.

    Governance:
        <20 observations  -> 0.00
        20 observations   -> 0.50
        100+ observations -> 1.00
    """
    observations = _safe_number(
        observations,
        default=0.0,
    )

    if observations < MIN_RELIABLE_OBSERVATIONS:
        return 0.0

    if observations >= FULL_EVIDENCE_OBSERVATIONS:
        return 1.0

    progress = (
        observations - MIN_RELIABLE_OBSERVATIONS
    ) / (
        FULL_EVIDENCE_OBSERVATIONS
        - MIN_RELIABLE_OBSERVATIONS
    )

    return (
        MIN_VALID_EVIDENCE_CONFIDENCE
        + (
            progress
            * (
                1.0
                - MIN_VALID_EVIDENCE_CONFIDENCE
            )
        )
    )


# ============================================================================
# RELIABILITY HELPERS
# ============================================================================

def _derive_reliability(observations):
    """
    Derive a reliability status from observation count.

    This is deliberately conservative.

    Returns
    -------
    str
        VALID
        INSUFFICIENT DATA
        NO DATA
    """
    observations = _safe_number(
        observations,
        default=0.0,
    )

    if observations >= MIN_RELIABLE_OBSERVATIONS:
        return "VALID"

    if observations > 0:
        return "INSUFFICIENT DATA"

    return "NO DATA"


def _normalise_reliability(
    reliability,
    observations,
):
    """
    Normalise an upstream reliability value.

    If upstream reliability is missing, derive it from observations.

    This prevents blank reliability values from leaking into the downstream
    decision-scoring layer.
    """
    normalised = _normalise_text(
        reliability
    )

    if normalised in {
        "",
        "NAN",
        "NONE",
        "NULL",
        "UNKNOWN",
    }:
        return _derive_reliability(
            observations
        )

    return normalised


# ============================================================================
# SIGNAL EVIDENCE
# ============================================================================

def _get_signal_evidence(
    signal,
    signal_performance,
):
    """
    Return historical evidence for the supplied recommendation signal.

    Reliability is taken from upstream learning output where available.
    Otherwise it is derived from observation count.
    """
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

    target_signal = _normalise_text(signal)

    matching = signal_performance[
        signal_performance[signal_column]
        .astype(str)
        .str.strip()
        .str.upper()
        == target_signal
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
                row[observations_column],
            )
        )

    if average_return_column is not None:
        evidence["average_return"] = _safe_number(
            row[average_return_column],
        )

    if win_rate_column is not None:
        evidence["win_rate"] = _safe_number(
            row[win_rate_column],
        )

    if reliability_column is not None:
        evidence["reliability"] = (
            _normalise_reliability(
                row[reliability_column],
                evidence["observations"],
            )
        )
    else:
        evidence["reliability"] = (
            _derive_reliability(
                evidence["observations"]
            )
        )

    return evidence


# ============================================================================
# SCORE BUCKETS
# ============================================================================

def _get_score_bucket(score):
    """
    Convert an Investment Score into the standard learning bucket.

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
    """Return historical evidence for the Investment Score bucket."""
    evidence = {
        "observations": 0,
        "average_return": 0.0,
        "win_rate": 0.0,
        "reliability": "NO DATA",
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

    bucket = _get_score_bucket(score)

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

    reliability_column = _find_column(
        score_bucket_performance,
        [
            "Reliability",
        ],
    )

    matching = pd.DataFrame()

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
            & (maximums >= score)
        ]

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
            == bucket.upper()
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
        evidence["observations"] = int(
            _safe_number(
                row[observations_column],
            )
        )

    if average_return_column is not None:
        evidence["average_return"] = _safe_number(
            row[average_return_column],
        )

    if win_rate_column is not None:
        evidence["win_rate"] = _safe_number(
            row[win_rate_column],
        )

    if reliability_column is not None:
        evidence["reliability"] = (
            _normalise_reliability(
                row[reliability_column],
                evidence["observations"],
            )
        )
    else:
        evidence["reliability"] = (
            _derive_reliability(
                evidence["observations"]
            )
        )

    return evidence


# ============================================================================
# COMPONENT EVIDENCE
# ============================================================================

def _get_component_evidence(
    component_score_performance,
):
    """Convert component learning data into a compact representation."""
    if (
        component_score_performance is None
        or component_score_performance.empty
    ):
        return "Unavailable"

    try:
        records = component_score_performance.to_dict(
            "records"
        )

        return str(records)

    except Exception:
        return "Unavailable"


# ============================================================================
# RECOMMENDATION STRENGTH
# ============================================================================

def _get_recommendation_strength(score):
    """Determine descriptive recommendation strength."""
    score = _safe_number(score)

    if score >= 80:
        return "Strong"

    if score >= 65:
        return "Moderate"

    return "Weak"


# ============================================================================
# CONFIDENCE
# ============================================================================

def _get_confidence(stock):
    """Retrieve the existing confidence value from a stock result."""
    confidence = stock.get(
        "Confidence",
        "Unknown",
    )

    if confidence is None:
        return "Unknown"

    try:
        if pd.isna(confidence):
            return "Unknown"
    except (TypeError, ValueError):
        pass

    return str(confidence)


# ============================================================================
# LEARNING ADJUSTMENT
# ============================================================================

def _calculate_return_adjustment(
    average_return,
    observations,
):
    """
    Convert historical average return into a bounded learning adjustment.

    Observation count determines confidence, not adjustment magnitude.
    """
    average_return = _safe_number(
        average_return,
    )

    observations = _safe_number(
        observations,
    )

    confidence = _evidence_confidence(
        observations
    )

    if confidence <= 0:
        return 0.0

    raw_adjustment = (
        average_return
        * LEARNING_RETURN_MULTIPLIER
    )

    adjusted = (
        raw_adjustment
        * confidence
    )

    return _clamp_adjustment(
        adjusted
    )


def _calculate_learning_adjustment(
    signal_evidence,
    score_evidence,
):
    """
    Calculate the final learning adjustment.

    Mature signal evidence is weighted 60%.
    Mature score-bucket evidence is weighted 40%.

    If only one source is mature, that source is used.
    """
    signal_observations = _safe_number(
        signal_evidence.get(
            "observations",
            0,
        )
    )

    bucket_observations = _safe_number(
        score_evidence.get(
            "observations",
            0,
        )
    )

    signal_confidence = _evidence_confidence(
        signal_observations
    )

    bucket_confidence = _evidence_confidence(
        bucket_observations
    )

    signal_return = _safe_number(
        signal_evidence.get(
            "average_return",
            0,
        )
    )

    bucket_return = _safe_number(
        score_evidence.get(
            "average_return",
            0,
        )
    )

    if (
        signal_confidence > 0
        and bucket_confidence > 0
    ):
        weighted_return = (
            signal_return
            * SIGNAL_EVIDENCE_WEIGHT
            * signal_confidence
            +
            bucket_return
            * SCORE_BUCKET_EVIDENCE_WEIGHT
            * bucket_confidence
        )

        combined_confidence = (
            SIGNAL_EVIDENCE_WEIGHT
            * signal_confidence
            +
            SCORE_BUCKET_EVIDENCE_WEIGHT
            * bucket_confidence
        )

        if combined_confidence <= 0:
            return 0.0

        raw_adjustment = (
            weighted_return
            * LEARNING_RETURN_MULTIPLIER
        )

        return _clamp_adjustment(
            raw_adjustment
            * combined_confidence
        )

    if signal_confidence > 0:
        return _calculate_return_adjustment(
            signal_return,
            signal_observations,
        )

    if bucket_confidence > 0:
        return _calculate_return_adjustment(
            bucket_return,
            bucket_observations,
        )

    return 0.0


# ============================================================================
# LEARNING ADJUSTED SCORE
# ============================================================================

def _calculate_learning_adjusted_score(
    investment_score,
    learning_adjustment,
):
    """Calculate the derived learning-adjusted score."""
    investment_score = _safe_number(
        investment_score,
    )

    learning_adjustment = _safe_number(
        learning_adjustment,
    )

    return _clamp_score(
        investment_score
        + learning_adjustment
    )


# ============================================================================
# HORIZON EVIDENCE
# ============================================================================

def _get_horizon_row(
    horizon_performance,
    horizon,
):
    """
    Return the row for a specific learning horizon.

    Supports numeric values such as:
        5
        10
        60

    and textual values such as:
        5D
        10D
        60D
        5 DAY
        10 DAY
        60 DAY
    """
    if (
        horizon_performance is None
        or horizon_performance.empty
    ):
        return None

    horizon_column = _find_column(
        horizon_performance,
        [
            "Horizon",
            "Learning Horizon",
            "Horizon Days",
            "Horizon_Days",
        ],
    )

    if horizon_column is None:
        return None

    target = int(horizon)

    values = horizon_performance[
        horizon_column
    ]

    numeric_values = pd.to_numeric(
        values,
        errors="coerce",
    )

    matches = horizon_performance[
        numeric_values == target
    ]

    if not matches.empty:
        return matches.iloc[0]

    target_texts = {
        f"{target}D",
        f"{target} D",
        f"{target}DAY",
        f"{target} DAY",
        f"{target}-DAY",
        f"{target}-DAY RETURN",
        str(target),
    }

    normalised_values = (
        values
        .astype(str)
        .str.strip()
        .str.upper()
    )

    matches = horizon_performance[
        normalised_values.isin(
            target_texts
        )
    ]

    if matches.empty:
        return None

    return matches.iloc[0]


def _extract_horizon_evidence(
    row,
):
    """
    Extract standardised evidence from a horizon row.

    Returns
    -------
    dict
        observations
        win_rate
        average_return
        reliability
    """
    evidence = {
        "observations": 0,
        "win_rate": 0.0,
        "average_return": 0.0,
        "reliability": "NO DATA",
    }

    if row is None:
        return evidence

    # A Series does not have the same column discovery interface as a
    # DataFrame, so inspect its index directly.
    columns = {
        str(column).strip().lower(): column
        for column in row.index
    }

    def find_value(possible_names):
        for name in possible_names:
            key = str(name).strip().lower()

            if key in columns:
                return row[columns[key]]

        return None

    observations_value = find_value(
        [
            "Recommendations",
            "Observations",
            "Evaluations",
            "Count",
            "Sample Size",
            "Historical Signal Observations",
        ]
    )

    win_rate_value = find_value(
        [
            "Win Rate %",
            "Win_Rate_Percent",
            "Win Rate",
            "Historical Win Rate %",
        ]
    )

    average_return_value = find_value(
        [
            "Average Return %",
            "Average_Return_Percent",
            "Average Return",
            "Mean Return %",
            "Historical Average Return %",
        ]
    )

    reliability_value = find_value(
        [
            "Reliability",
            "Historical Signal Reliability",
            "Historical Reliability",
        ]
    )

    evidence["observations"] = int(
        _safe_number(
            observations_value,
            default=0,
        )
    )

    evidence["win_rate"] = _safe_number(
        win_rate_value,
        default=0.0,
    )

    evidence["average_return"] = _safe_number(
        average_return_value,
        default=0.0,
    )

    evidence["reliability"] = (
        _normalise_reliability(
            reliability_value,
            evidence["observations"],
        )
    )

    return evidence


def _get_preferred_learning_evidence(
    horizon_performance,
):
    """
    Return the highest mature learning horizon.

    Preference:
        60D -> 10D -> 5D

    A horizon is mature when it has at least
    MIN_RELIABLE_OBSERVATIONS observations.

    Upstream reliability is respected where supplied, but missing reliability
    is derived from observations.

    No 60D data is invented when 60D is unavailable.
    """
    empty = {
        "horizon": None,
        "observations": 0,
        "win_rate": 0.0,
        "average_return": 0.0,
        "reliability": "NO DATA",
    }

    if (
        horizon_performance is None
        or horizon_performance.empty
    ):
        return empty

    for horizon in (
        60,
        10,
        5,
    ):
        row = _get_horizon_row(
            horizon_performance,
            horizon,
        )

        if row is None:
            continue

        evidence = _extract_horizon_evidence(
            row
        )

        if (
            evidence["observations"]
            >= MIN_RELIABLE_OBSERVATIONS
            and evidence["reliability"]
            == "VALID"
        ):
            return {
                "horizon": horizon,
                **evidence,
            }

    return empty


def _get_preferred_learning_horizon(
    horizon_performance,
):
    """
    Backward-compatible helper returning only the preferred horizon.

    Preference:
        60D -> 10D -> 5D
    """
    evidence = _get_preferred_learning_evidence(
        horizon_performance
    )

    return evidence["horizon"]


# ============================================================================
# MAIN FUNCTION
# ============================================================================

def generate_recommendation_intelligence(
    results,
    signal_performance,
    score_bucket_performance,
    component_score_performance,
    horizon_performance=None,
):
    """
    Generate the Recommendation Intelligence DataFrame.

    Existing function signature is preserved.

    Parameters
    ----------
    results:
        Current stock recommendation results.

    signal_performance:
        Historical performance grouped by recommendation signal.

    score_bucket_performance:
        Historical performance grouped by Investment Score bucket.

    component_score_performance:
        Historical performance associated with score components.

    horizon_performance:
        Historical performance by learning horizon.

    Returns
    -------
    pandas.DataFrame
        Recommendation Intelligence dataset.
    """
    print(
        "RECOMMENDATION INTELLIGENCE START"
    )

    preferred_learning = (
        _get_preferred_learning_evidence(
            horizon_performance
        )
    )

    preferred_horizon = (
        preferred_learning["horizon"]
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

    component_evidence = (
        _get_component_evidence(
            component_score_performance
        )
    )

    for stock in results:

        if not isinstance(stock, dict):
            continue

        ticker = stock.get(
            "Ticker",
            "UNKNOWN",
        )

        signal = stock.get(
            "Signal",
            "UNKNOWN",
        )

        score = _safe_number(
            stock.get(
                "Investment Score",
                stock.get(
                    "Score",
                    0,
                ),
            )
        )

        base_strength = (
            _get_recommendation_strength(
                score
            )
        )

        confidence = _get_confidence(
            stock
        )

        # --------------------------------------------------------------------
        # Historical signal evidence.
        # --------------------------------------------------------------------

        signal_evidence = (
            _get_signal_evidence(
                signal,
                signal_performance,
            )
        )

        # --------------------------------------------------------------------
        # Historical score-bucket evidence.
        # --------------------------------------------------------------------

        score_bucket = _get_score_bucket(
            score
        )

        score_evidence = (
            _get_score_bucket_evidence(
                score,
                score_bucket_performance,
            )
        )

        # --------------------------------------------------------------------
        # Learning adjustment.
        # --------------------------------------------------------------------

        learning_adjustment = (
            _calculate_learning_adjustment(
                signal_evidence,
                score_evidence,
            )
        )

        learning_adjusted_score = (
            _calculate_learning_adjusted_score(
                score,
                learning_adjustment,
            )
        )

        recommendation_strength = (
            _get_recommendation_strength(
                learning_adjusted_score
            )
        )

        signal_observations = _safe_number(
            signal_evidence.get(
                "observations",
                0,
            )
        )

        bucket_observations = _safe_number(
            score_evidence.get(
                "observations",
                0,
            )
        )

        signal_confidence = (
            _evidence_confidence(
                signal_observations
            )
        )

        bucket_confidence = (
            _evidence_confidence(
                bucket_observations
            )
        )

        # --------------------------------------------------------------------
        # Intelligence notes.
        # --------------------------------------------------------------------

        notes = []

        if signal_observations > 0:
            notes.append(
                "Historical signal data available"
            )
        else:
            notes.append(
                "Limited historical signal data"
            )

        if bucket_observations > 0:
            notes.append(
                "Historical score bucket data available"
            )
        else:
            notes.append(
                "Limited historical score bucket data"
            )

        if abs(learning_adjustment) > 0.01:
            notes.append(
                "Learning adjustment applied: "
                f"{learning_adjustment:+.2f}"
            )
        else:
            notes.append(
                "No learning adjustment applied"
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

        if (
            bucket_observations
            >= MIN_RELIABLE_OBSERVATIONS
        ):
            notes.append(
                "Score bucket evidence is statistically valid"
            )

        if (
            signal_confidence > 0
            and bucket_confidence > 0
        ):
            notes.append(
                "Learning combines signal and score-bucket evidence"
            )

        elif signal_confidence > 0:
            notes.append(
                "Learning primarily uses signal evidence"
            )

        elif bucket_confidence > 0:
            notes.append(
                "Learning primarily uses score-bucket evidence"
            )

        else:
            notes.append(
                "Insufficient historical evidence for learning adjustment"
            )

        # --------------------------------------------------------------------
        # Preferred learning horizon notes.
        # --------------------------------------------------------------------

        if preferred_horizon is not None:
            notes.append(
                f"{preferred_horizon}-day learning horizon is mature"
            )

        else:
            notes.append(
                "No mature learning horizon available"
            )

        # --------------------------------------------------------------------
        # Construct output row.
        #
        # The preferred-horizon fields are deliberately explicit so downstream
        # consumers do not have to reconstruct the selected horizon.
        # --------------------------------------------------------------------

        row = {
            "Ticker":
                ticker,

            "Signal":
                signal,

            # Raw Investment Score remains unchanged.
            "Investment Score":
                score,

            "Base Recommendation Strength":
                base_strength,

            # ---------------------------------------------------------------
            # Historical signal evidence.
            # ---------------------------------------------------------------

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

            # ---------------------------------------------------------------
            # Learning adjustment / derived score.
            # ---------------------------------------------------------------

            "Learning Adjustment":
                learning_adjustment,

            "Learning Adjusted Score":
                learning_adjusted_score,

            "Recommendation Strength":
                recommendation_strength,

            # ---------------------------------------------------------------
            # Score bucket evidence.
            # ---------------------------------------------------------------

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

            "Score Bucket Reliability":
                score_evidence[
                    "reliability"
                ],

            # ---------------------------------------------------------------
            # Existing confidence.
            # ---------------------------------------------------------------

            "Confidence":
                confidence,

            # ---------------------------------------------------------------
            # Evidence payloads.
            # ---------------------------------------------------------------

            "Historical Signal Evidence":
                (
                    str(signal_evidence)
                    if signal_observations > 0
                    else "Unavailable"
                ),

            "Score Bucket Evidence":
                (
                    str(score_evidence)
                    if bucket_observations > 0
                    else "Unavailable"
                ),

            "Component Evidence":
                component_evidence,

            # ---------------------------------------------------------------
            # Preferred learning horizon.
            #
            # These fields are the key new downstream interface.
            # ---------------------------------------------------------------

            "Preferred Learning Horizon":
                preferred_learning[
                    "horizon"
                ],

            "Preferred Learning Observations":
                preferred_learning[
                    "observations"
                ],

            "Preferred Learning Win Rate":
                preferred_learning[
                    "win_rate"
                ],

            "Preferred Learning Average Return %":
                preferred_learning[
                    "average_return"
                ],

            "Preferred Learning Reliability":
                preferred_learning[
                    "reliability"
                ],

            "Learning Horizon Status":
                (
                    f"{preferred_horizon} DAY MATURE"
                    if preferred_horizon is not None
                    else "IMMATURE"
                ),

            # ---------------------------------------------------------------
            # General intelligence notes.
            # ---------------------------------------------------------------

            "Intelligence Notes":
                "; ".join(notes),
        }

        intelligence.append(
            row
        )

    # =========================================================================
    # CREATE DATAFRAME
    # =========================================================================

    df = pd.DataFrame(
        intelligence
    )

    print(
        "FINAL INTELLIGENCE DATAFRAME SIZE: "
        f"{df.shape}"
    )

    if not df.empty:

        diagnostic_columns = [
            "Ticker",
            "Signal",
            "Investment Score",
            "Historical Signal Observations",
            "Historical Signal Average Return %",
            "Historical Signal Win Rate %",
            "Historical Signal Reliability",
            "Learning Adjustment",
            "Learning Adjusted Score",
            "Recommendation Strength",
            "Score Bucket",
            "Score Bucket Observations",
            "Score Bucket Average Return %",
            "Score Bucket Win Rate %",
            "Score Bucket Reliability",
            "Preferred Learning Horizon",
            "Preferred Learning Observations",
            "Preferred Learning Win Rate",
            "Preferred Learning Average Return %",
            "Preferred Learning Reliability",
        ]

        available_columns = [
            column
            for column in diagnostic_columns
            if column in df.columns
        ]

        print(
            df[
                available_columns
            ].head(10)
        )

        print(
            "\nPREFERRED LEARNING EVIDENCE:"
        )

        print(
            "Horizon:",
            preferred_learning[
                "horizon"
            ],
        )

        print(
            "Observations:",
            preferred_learning[
                "observations"
            ],
        )

        print(
            "Win rate:",
            preferred_learning[
                "win_rate"
            ],
        )

        print(
            "Average return:",
            preferred_learning[
                "average_return"
            ],
        )

        print(
            "Reliability:",
            preferred_learning[
                "reliability"
            ],
        )

        print(
            "\nLEARNING ADJUSTMENT DISTRIBUTION:"
        )

        print(
            df[
                "Learning Adjustment"
            ]
            .round(2)
            .value_counts()
            .sort_index()
            .to_string()
        )

        print(
            "\nLEARNING ADJUSTMENT RANGE:",
            round(
                _safe_number(
                    df[
                        "Learning Adjustment"
                    ].min()
                ),
                2,
            ),
            "to",
            round(
                _safe_number(
                    df[
                        "Learning Adjustment"
                    ].max()
                ),
                2,
            ),
        )

    print(
        "RECOMMENDATION INTELLIGENCE COMPLETE"
    )

    return df


# ============================================================================
# END
# ============================================================================
