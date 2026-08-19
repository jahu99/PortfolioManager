# analysis/weight_optimizer.py
"""
Calibrates the relative weights of the underlying stock scoring
components using historical recommendation outcomes.

Architecture:

    Technical Score ─┐
    Quality Score ───┼──> Optimised Weights
    Growth Score ────┘
                         │
                         ▼
                  Investment Score
                         │
                         ▼
                Signal / Decision

IMPORTANT:

    Investment Score is the OUTPUT of the scoring model.

    It is NOT a component used to calculate its own weight.

    The optimiser therefore operates only on:

        - technical_score
        - quality_score
        - growth_score

    Governance is applied by weight_controller.py before
    production weights are persisted.
"""

import pandas as pd

from data.database import get_connection
from analysis.weight_controller import save_weights


# =====================================================
# Default strategic weights
# =====================================================

DEFAULT_WEIGHTS = {

    "technical_score": 50.0,

    "quality_score": 20.0,

    "growth_score": 30.0

}


# =====================================================
# Learning data
# =====================================================

def load_learning_data():
    """
    Load historical recommendation outcomes used to
    calibrate the component weights.

    Investment Score is deliberately excluded as an
    independent weighting component.
    """

    conn = get_connection()

    try:

        query = """
        SELECT
            technical_score,
            quality_score,
            growth_score,
            return_percent,
            outcome

        FROM recommendation_evaluations

        WHERE return_percent IS NOT NULL
        """

        df = pd.read_sql_query(
            query,
            conn
        )

    finally:

        conn.close()

    numeric_columns = [

        "technical_score",

        "quality_score",

        "growth_score",

        "return_percent"

    ]

    for col in numeric_columns:

        if col not in df.columns:

            df[col] = 0

        df[col] = pd.to_numeric(
            df[col],
            errors="coerce"
        ).fillna(0)

    return df


# =====================================================
# Analyse component performance
# =====================================================

def analyse_components(df):
    """
    Measure the historical relationship between each
    underlying scoring component and subsequent return.

    Only Technical, Quality and Growth are analysed.

    Investment Score is intentionally excluded because
    it is the composite output of these components.
    """

    print(
        "\nCOMPONENT PERFORMANCE ANALYSIS"
    )

    components = [

        "technical_score",

        "quality_score",

        "growth_score"

    ]

    results = []

    for component in components:

        correlation = (
            df[component]
            .corr(
                df["return_percent"]
            )
        )

        if pd.isna(correlation):

            correlation = 0

        results.append({

            "Component":
                component,

            "Correlation":
                round(
                    correlation,
                    3
                )

        })

    return pd.DataFrame(
        results
    )


# =====================================================
# Calculate optimised weights
# =====================================================

def calculate_weights(
    component_results
):
    """
    Convert historical component correlations into
    candidate strategic weights.

    Positive correlations contribute to the weighting.

    Negative or neutral correlations receive no positive
    contribution, but governance ensures every component
    retains a minimum strategic weight.

    The resulting weights are normalised to 100%.

    These are RAW optimiser weights. They are subsequently
    passed to weight_controller.py for governance.
    """

    print(
        "\nCALCULATING OPTIMAL WEIGHTS"
    )

    MIN_WEIGHTS = {

        "technical_score": 35.0,

        "quality_score": 15.0,

        "growth_score": 10.0

    }

    MAX_WEIGHTS = {

        "technical_score": 60.0,

        "quality_score": 35.0,

        "growth_score": 30.0

    }

    correlations = {}

    for _, row in component_results.iterrows():

        component = row["Component"]

        correlation = max(
            float(
                row["Correlation"]
            ),
            0
        )

        correlations[
            component
        ] = correlation

    total = sum(
        correlations.values()
    )

    # -------------------------------------------------
    # No useful historical signal
    # -------------------------------------------------

    if total == 0:

        return DEFAULT_WEIGHTS.copy()

    weights = {}

    for component, correlation in correlations.items():

        weight = (
            correlation
            /
            total
        ) * 100

        # Apply optimiser-level minimum

        weight = max(
            weight,
            MIN_WEIGHTS[component]
        )

        # Apply optimiser-level maximum

        weight = min(
            weight,
            MAX_WEIGHTS[component]
        )

        weights[component] = round(
            weight,
            1
        )

    # -------------------------------------------------
    # Normalise to 100%
    # -------------------------------------------------

    total_weight = sum(
        weights.values()
    )

    if total_weight == 0:

        return DEFAULT_WEIGHTS.copy()

    for key in weights:

        weights[key] = round(

            weights[key]
            /
            total_weight
            *
            100,

            1

        )

    # -------------------------------------------------
    # Correct rounding drift
    # -------------------------------------------------

    difference = round(
        100.0
        -
        sum(weights.values()),
        1
    )

    if difference != 0:

        weights["technical_score"] = round(

            weights["technical_score"]
            +
            difference,

            1

        )

    return weights


# =====================================================
# Generate actions
# =====================================================

def generate_actions(
    component_results
):
    """
    Generate a human-readable explanation of how
    historical performance affects each component.
    """

    actions = []

    for _, row in component_results.iterrows():

        correlation = float(
            row["Correlation"]
        )

        if correlation > 0:

            action = (
                "Increase weighting"
            )

            reason = (
                "Positive historical return correlation"
            )

        else:

            action = (
                "Maintain or reduce"
            )

            reason = (
                "Negative or neutral historical "
                "return correlation"
            )

        actions.append({

            "Component":
                row["Component"],

            "Correlation":
                row["Correlation"],

            "Action":
                action,

            "Reason":
                reason

        })

    return pd.DataFrame(
        actions
    )


# =====================================================
# Main optimiser
# =====================================================

def run_weight_optimizer():
    """
    Run the historical component-weight calibration.

    Returns:

        Component Performance
            Historical component correlations.

        Raw Weights
            Weights produced by the optimiser before
            production governance.

        Recommended Weights
            Governed production weights.

        Weight Actions
            Human-readable explanation of the
            historical evidence.
    """

    print(
        "WEIGHT OPTIMISER START"
    )

    df = load_learning_data()

    print(
        f"Learning records: {len(df)}"
    )

    # -------------------------------------------------
    # No learning data
    # -------------------------------------------------

    if df.empty:

        return {

            "Component Performance":
                pd.DataFrame(),

            "Raw Weights":
                DEFAULT_WEIGHTS.copy(),

            "Recommended Weights":
                DEFAULT_WEIGHTS.copy(),

            "Weight Actions":
                pd.DataFrame()

        }

    # -------------------------------------------------
    # Analyse components
    # -------------------------------------------------

    component_results = (
        analyse_components(df)
    )

    print(
        "\nCOMPONENT PERFORMANCE"
    )

    print(
        component_results
    )

    # -------------------------------------------------
    # Generate raw optimiser weights
    # -------------------------------------------------

    raw_weights = calculate_weights(
        component_results
    )

    print(
        "\nRAW OPTIMISER WEIGHTS"
    )

    print(
        raw_weights
    )

    # -------------------------------------------------
    # Apply governance and persist production weights
    # -------------------------------------------------
    #
    # save_weights() is the single governance and
    # persistence boundary.
    #
    # It:
    #
    #   1. receives raw optimiser weights
    #   2. applies governance
    #   3. validates the result
    #   4. saves data/optimised_weights.json
    #   5. returns the governed weights
    #

    governed_weights = save_weights(
        raw_weights
    )

    print(
        "\nGOVERNED WEIGHTS"
    )

    print(
        governed_weights
    )

    # -------------------------------------------------
    # Generate explanation
    # -------------------------------------------------

    actions = generate_actions(
        component_results
    )

    print(
        "\nWEIGHT ACTIONS"
    )

    print(
        actions
    )

    print(
        "\nWEIGHT OPTIMISER COMPLETE"
    )

    return {

        "Component Performance":
            component_results,

        # Research output only

        "Raw Weights":
            raw_weights,

        # Production output

        "Recommended Weights":
            governed_weights,

        "Weight Actions":
            actions

    }