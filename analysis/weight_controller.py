
"""
Weight Controller
=================

Purpose
-------
Provides the governed production scoring weights used by the
Investment Score engine and adaptive weight optimiser.

Architecture
------------
The scoring model has three strategic components:

    Technical Score
    Quality Score
    Growth Score

These weights:

    - must total 100%
    - are constrained by minimum and maximum governance limits
    - may be adjusted by the adaptive weight optimiser
    - are persisted to data/scoring_weights.json

The Investment Score itself is NOT a weighted component.

Governance
----------
The controller is deliberately conservative.

Optimiser output is never written directly to production.

Instead:

    Optimiser Proposal
            ↓
       Normalisation
            ↓
      Governance Bounds
            ↓
      Exact 100% Total
            ↓
         Validation
            ↓
       Persisted Weights

This ensures that the adaptive optimiser cannot introduce
invalid or excessively aggressive scoring weights.

Current production defaults:

    Technical = 50%
    Quality   = 20%
    Growth    = 30%

Governance boundaries:

    Technical = 35% - 60%
    Quality   = 15% - 30%
    Growth    = 10% - 35%
"""

import json
import os


# ============================================================
# CONFIGURATION
# ============================================================

WEIGHT_FILE = (
    "data/scoring_weights.json"
)


# ------------------------------------------------------------
# Valid scoring components
# ------------------------------------------------------------

VALID_KEYS = {
    "technical_score",
    "quality_score",
    "growth_score",
}


# ------------------------------------------------------------
# Default production weights
# ------------------------------------------------------------

DEFAULT_WEIGHTS = {

    "technical_score": 50.0,

    "quality_score": 20.0,

    "growth_score": 30.0,
}


# ------------------------------------------------------------
# Governance boundaries
# ------------------------------------------------------------

MIN_WEIGHTS = {

    "technical_score": 35.0,

    "quality_score": 15.0,

    "growth_score": 10.0,
}


MAX_WEIGHTS = {

    "technical_score": 60.0,

    "quality_score": 30.0,

    "growth_score": 35.0,
}


# ============================================================
# HELPERS
# ============================================================

def safe_float(
    value,
    default=0.0,
):
    """
    Safely convert a value to float.

    Invalid values return the supplied default.
    """

    try:

        return float(value)

    except Exception:

        return default


# ============================================================
# VALIDATION
# ============================================================

def validate_weights(weights):
    """
    Validate a complete set of production scoring weights.

    Validation requirements
    -----------------------
    1. Input must be a dictionary.
    2. Exactly the three expected scoring components must exist.
    3. All values must be numeric.
    4. Total must equal 100%.
    5. Every component must remain within governance limits.

    Returns
    -------
    bool
        True when the weights are valid.
    """

    if not isinstance(
        weights,
        dict,
    ):

        print(
            "Invalid weights object:",
            type(weights),
        )

        return False


    # --------------------------------------------------------
    # Check keys
    # --------------------------------------------------------

    if set(weights.keys()) != VALID_KEYS:

        print(
            "Invalid weight keys:",
            weights.keys(),
        )

        print(
            "Expected keys:",
            VALID_KEYS,
        )

        return False


    # --------------------------------------------------------
    # Check numeric values
    # --------------------------------------------------------

    for key, value in weights.items():

        try:

            float(value)

        except Exception:

            print(
                "Invalid weight value:",
                key,
                value,
            )

            return False


    # --------------------------------------------------------
    # Check total
    # --------------------------------------------------------

    total = round(
        sum(
            float(value)
            for value in weights.values()
        ),
        2,
    )

    if total != 100.0:

        print(
            "Weights do not equal 100:",
            total,
        )

        return False


    # --------------------------------------------------------
    # Check governance boundaries
    # --------------------------------------------------------

    for key, value in weights.items():

        value = float(value)


        if value < MIN_WEIGHTS[key]:

            print(
                f"{key} below minimum: "
                f"{value} < {MIN_WEIGHTS[key]}"
            )

            return False


        if value > MAX_WEIGHTS[key]:

            print(
                f"{key} above maximum: "
                f"{value} > {MAX_WEIGHTS[key]}"
            )

            return False


    return True


# ============================================================
# NORMALISE WEIGHTS
# ============================================================

def normalise_weights(weights):
    """
    Normalise arbitrary weight values so that they total 100%.

    Missing components receive zero before normalisation.

    This function does not apply governance limits.
    """

    cleaned = {}


    for key in VALID_KEYS:

        cleaned[key] = safe_float(
            weights.get(
                key,
                0.0,
            )
        )


    total = sum(
        cleaned.values()
    )


    if total <= 0:

        return DEFAULT_WEIGHTS.copy()


    for key in cleaned:

        cleaned[key] = (
            cleaned[key]
            /
            total
            *
            100.0
        )


    return cleaned


# ============================================================
# GOVERNANCE ENGINE
# ============================================================

def govern_weights(weights):
    """
    Convert optimiser output into valid governed weights.

    The algorithm guarantees:

        MIN <= weight <= MAX

    and:

        Technical + Quality + Growth = 100

    The optimiser cannot therefore push any individual component
    outside its approved governance boundary.

    Strategy
    --------
    1. Normalise the optimiser proposal.
    2. Clamp each component to its governance boundaries.
    3. Redistribute any remaining difference across components
       that still have available capacity.
    4. Round to one decimal place.
    5. Correct any rounding drift while respecting boundaries.
    6. Fall back to defaults if a valid solution cannot be created.
    """

    # --------------------------------------------------------
    # Validate input type
    # --------------------------------------------------------

    if not isinstance(
        weights,
        dict,
    ):

        print(
            "Invalid optimiser weights. "
            "Using defaults."
        )

        return DEFAULT_WEIGHTS.copy()


    # --------------------------------------------------------
    # Normalise optimiser output
    # --------------------------------------------------------

    proposed = normalise_weights(
        weights
    )


    # --------------------------------------------------------
    # Initial governance clamp
    # --------------------------------------------------------

    governed = {}


    for key in VALID_KEYS:

        value = proposed.get(
            key,
            DEFAULT_WEIGHTS[key],
        )

        value = max(
            MIN_WEIGHTS[key],
            min(
                value,
                MAX_WEIGHTS[key],
            ),
        )

        governed[key] = value


    # --------------------------------------------------------
    # Redistribute difference
    # --------------------------------------------------------

    def redistribute_difference(
        values,
        difference,
    ):
        """
        Redistribute a weight difference without violating
        governance boundaries.

        Positive difference:
            Increase components with available headroom.

        Negative difference:
            Decrease components with available room above minimum.
        """

        remaining = difference


        # ----------------------------------------------------
        # Positive difference
        # ----------------------------------------------------

        if remaining > 0:

            while remaining > 0.00001:

                candidates = [
                    key
                    for key in VALID_KEYS
                    if values[key]
                    <
                    MAX_WEIGHTS[key]
                    - 0.00001
                ]


                if not candidates:

                    break


                capacity = {
                    key:
                        MAX_WEIGHTS[key]
                        -
                        values[key]
                    for key in candidates
                }


                total_capacity = sum(
                    capacity.values()
                )


                if total_capacity <= 0:

                    break


                for key in candidates:

                    share = (
                        remaining
                        *
                        capacity[key]
                        /
                        total_capacity
                    )

                    addition = min(
                        share,
                        capacity[key],
                    )

                    values[key] += addition

                new_total = sum(
                    values.values()
                )

                remaining = (
                    100.0
                    -
                    new_total
                )


        # ----------------------------------------------------
        # Negative difference
        # ----------------------------------------------------

        elif remaining < 0:

            while remaining < -0.00001:

                candidates = [
                    key
                    for key in VALID_KEYS
                    if values[key]
                    >
                    MIN_WEIGHTS[key]
                    + 0.00001
                ]


                if not candidates:

                    break


                capacity = {
                    key:
                        values[key]
                        -
                        MIN_WEIGHTS[key]
                    for key in candidates
                }


                total_capacity = sum(
                    capacity.values()
                )


                if total_capacity <= 0:

                    break


                reduction_needed = (
                    -remaining
                )


                for key in candidates:

                    share = (
                        reduction_needed
                        *
                        capacity[key]
                        /
                        total_capacity
                    )

                    reduction = min(
                        share,
                        capacity[key],
                    )

                    values[key] -= reduction


                new_total = sum(
                    values.values()
                )

                remaining = (
                    100.0
                    -
                    new_total
                )


        return values


    # --------------------------------------------------------
    # First redistribution
    # --------------------------------------------------------

    difference = (
        100.0
        -
        sum(
            governed.values()
        )
    )


    governed = redistribute_difference(
        governed,
        difference,
    )


    # --------------------------------------------------------
    # Round to one decimal place
    # --------------------------------------------------------

    for key in governed:

        governed[key] = round(
            governed[key],
            1,
        )


    # --------------------------------------------------------
    # Correct rounding drift
    # --------------------------------------------------------

    total = round(
        sum(
            governed.values()
        ),
        1,
    )


    difference = round(
        100.0
        -
        total,
        1,
    )


    if difference != 0:

        # ----------------------------------------------------
        # Try to apply rounding correction to a component
        # that can safely absorb it.
        # ----------------------------------------------------

        correction_applied = False


        for key in (
            "technical_score",
            "quality_score",
            "growth_score",
        ):

            proposed_value = round(
                governed[key]
                +
                difference,
                1,
            )


            if (
                proposed_value
                >= MIN_WEIGHTS[key]
                and
                proposed_value
                <= MAX_WEIGHTS[key]
            ):

                governed[key] = (
                    proposed_value
                )

                correction_applied = True

                break


        # ----------------------------------------------------
        # If no single component can absorb the rounding
        # difference, use the redistribution engine again.
        # ----------------------------------------------------

        if not correction_applied:

            governed = redistribute_difference(
                governed,
                difference,
            )


            for key in governed:

                governed[key] = round(
                    governed[key],
                    1,
                )


    # --------------------------------------------------------
    # Final total correction
    # --------------------------------------------------------

    total = round(
        sum(
            governed.values()
        ),
        2,
    )


    if total != 100.0:

        difference = round(
            100.0
            -
            total,
            2,
        )


        # Find a component with enough room.
        for key in VALID_KEYS:

            candidate = round(
                governed[key]
                +
                difference,
                1,
            )


            if (
                candidate
                >= MIN_WEIGHTS[key]
                and
                candidate
                <= MAX_WEIGHTS[key]
            ):

                governed[key] = (
                    candidate
                )

                break


    # --------------------------------------------------------
    # Final validation
    # --------------------------------------------------------

    if not validate_weights(
        governed
    ):

        print(
            "\nWARNING: Optimiser proposal could not "
            "be converted into a valid governed weight set."
        )

        print(
            "Proposed:",
            proposed,
        )

        print(
            "Governed:",
            governed,
        )

        print(
            "Minimums:",
            MIN_WEIGHTS,
        )

        print(
            "Maximums:",
            MAX_WEIGHTS,
        )

        print(
            "Total:",
            sum(
                governed.values()
            ),
        )

        print(
            "Falling back to DEFAULT_WEIGHTS."
        )

        return DEFAULT_WEIGHTS.copy()


    return governed


# ============================================================
# LOAD CURRENT WEIGHTS
# ============================================================

def get_weights():
    """
    Load the current governed production weights.

    If the persisted file is missing or invalid, return the
    governed default weights.
    """

    try:

        if os.path.exists(
            WEIGHT_FILE
        ):

            with open(
                WEIGHT_FILE,
                "r",
            ) as f:

                weights = json.load(
                    f
                )


            if validate_weights(
                weights
            ):

                return weights


    except Exception as e:

        print(
            "Unable to load scoring weights:",
            e,
        )


    return DEFAULT_WEIGHTS.copy()


# ============================================================
# SAVE WEIGHTS
# ============================================================

def save_weights(weights):
    """
    Govern, validate and persist optimiser weights.

    Invalid optimiser proposals are never written directly
    to production.
    """

    os.makedirs(
        "data",
        exist_ok=True,
    )


    print(
        "\nRAW WEIGHTS RECEIVED:"
    )

    print(
        weights
    )


    # --------------------------------------------------------
    # Govern optimiser output
    # --------------------------------------------------------

    cleaned = govern_weights(
        weights
    )


    print(
        "\nGOVERNED WEIGHTS:"
    )

    print(
        cleaned
    )


    # --------------------------------------------------------
    # Final safety check
    # --------------------------------------------------------

    if not validate_weights(
        cleaned
    ):

        print(
            "\n!!! GOVERNED WEIGHTS FAILED VALIDATION !!!"
        )

        print(
            "RAW WEIGHTS:",
            weights,
        )

        print(
            "GOVERNED WEIGHTS:",
            cleaned,
        )

        print(
            "MIN WEIGHTS:",
            MIN_WEIGHTS,
        )

        print(
            "MAX WEIGHTS:",
            MAX_WEIGHTS,
        )

        print(
            "TOTAL WEIGHT:",
            sum(
                float(value)
                for value in cleaned.values()
            ),
        )

        raise ValueError(
            "Governed weights failed validation"
        )


    # --------------------------------------------------------
    # Persist
    # --------------------------------------------------------

    with open(
        WEIGHT_FILE,
        "w",
    ) as f:

        json.dump(
            cleaned,
            f,
            indent=4,
        )


    print(
        "\nWEIGHTS SAVED:",
        WEIGHT_FILE,
    )


    return cleaned


# ============================================================
# WEIGHT SUMMARY
# ============================================================

def get_weight_summary():
    """
    Return the current production weights plus governance
    boundaries for reporting/debugging.
    """

    weights = get_weights()


    return {

        "Technical Weight":
            weights[
                "technical_score"
            ],

        "Quality Weight":
            weights[
                "quality_score"
            ],

        "Growth Weight":
            weights[
                "growth_score"
            ],

        "Technical Minimum":
            MIN_WEIGHTS[
                "technical_score"
            ],

        "Technical Maximum":
            MAX_WEIGHTS[
                "technical_score"
            ],

        "Quality Minimum":
            MIN_WEIGHTS[
                "quality_score"
            ],

        "Quality Maximum":
            MAX_WEIGHTS[
                "quality_score"
            ],

        "Growth Minimum":
            MIN_WEIGHTS[
                "growth_score"
            ],

        "Growth Maximum":
            MAX_WEIGHTS[
                "growth_score"
            ],

    }
