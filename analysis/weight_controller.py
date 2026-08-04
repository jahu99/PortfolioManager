# analysis/weight_controller.py

import json
import os


WEIGHT_FILE = "data/optimised_weights.json"


# =====================================================
# Default strategic weights
# =====================================================

DEFAULT_WEIGHTS = {

    "technical_score": 50.0,

    "quality_score": 20.0,

    "growth_score": 10.0,

    "investment_score": 20.0

}



# =====================================================
# Governance rules
# =====================================================

MIN_WEIGHTS = {

    "technical_score": 35.0,

    "quality_score": 15.0,

    "growth_score": 10.0,

    "investment_score": 15.0

}



MAX_WEIGHTS = {

    "technical_score": 55.0,

    "quality_score": 30.0,

    "growth_score": 25.0,

    "investment_score": 30.0

}



VALID_KEYS = set(

    DEFAULT_WEIGHTS.keys()

)



# =====================================================
# Load weights
# =====================================================

def get_weights():


    if not os.path.exists(
        WEIGHT_FILE
    ):

        return DEFAULT_WEIGHTS.copy()



    try:

        with open(
            WEIGHT_FILE,
            "r"
        ) as f:

            weights = json.load(f)



        if validate_weights(weights):

            return weights



    except Exception:

        pass



    return DEFAULT_WEIGHTS.copy()



# =====================================================
# Validate weights
# =====================================================

def validate_weights(weights):


    if not isinstance(
        weights,
        dict
    ):

        return False



    # Check keys

    if set(weights.keys()) != VALID_KEYS:

        print(
            "Invalid weight keys:",
            weights.keys()
        )

        return False



    # Check numeric

    for key, value in weights.items():


        try:

            float(value)

        except Exception:

            print(
                "Invalid weight value:",
                key,
                value
            )

            return False



    # Check total

    total = round(

        sum(

            float(v)

            for v in weights.values()

        ),

        2

    )



    if total != 100.0:


        print(

            "Weights do not equal 100:",
            total

        )


        return False



    # Check boundaries

    for key, value in weights.items():


        value = float(value)



        if value < MIN_WEIGHTS[key]:

            print(

                f"{key} below minimum: {value}"

            )

            return False



        if value > MAX_WEIGHTS[key]:

            print(

                f"{key} above maximum: {value}"

            )

            return False



    return True




# =====================================================
# Normalise weights
# =====================================================

def normalise_weights(weights):


    cleaned = {}



    for key in VALID_KEYS:


        cleaned[key] = float(

            weights.get(

                key,

                DEFAULT_WEIGHTS[key]

            )

        )



    total = sum(

        cleaned.values()

    )



    if total == 0:

        return DEFAULT_WEIGHTS.copy()



    for key in cleaned:


        cleaned[key] = round(

            cleaned[key]

            /

            total

            *

            100,

            1

        )



    return cleaned




# =====================================================
# Save weights
# =====================================================

def save_weights(weights):


    os.makedirs(

        "data",

        exist_ok=True

    )


    print(
        "\nRAW WEIGHTS RECEIVED:"
    )

    print(weights)



    # -------------------------------------------------
    # Ensure only valid keys
    # -------------------------------------------------

    cleaned = {}


    for key in VALID_KEYS:

        cleaned[key] = float(

            weights.get(

                key,

                DEFAULT_WEIGHTS[key]

            )

        )



    # -------------------------------------------------
    # Apply minimum constraints
    # -------------------------------------------------

    for key in cleaned:


        if cleaned[key] < MIN_WEIGHTS[key]:

            cleaned[key] = MIN_WEIGHTS[key]



    # -------------------------------------------------
    # Apply maximum constraints
    # -------------------------------------------------

    for key in cleaned:


        if cleaned[key] > MAX_WEIGHTS[key]:

            cleaned[key] = MAX_WEIGHTS[key]



    # -------------------------------------------------
    # Normalise to 100%
    # -------------------------------------------------

    total = sum(

        cleaned.values()

    )



    for key in cleaned:


        cleaned[key] = round(

            cleaned[key]

            /

            total

            *

            100,

            1

        )



    print(

        "\nGOVERNED WEIGHTS:"
    )

    print(cleaned)



    # -------------------------------------------------
    # Final safety check
    # -------------------------------------------------

    if round(sum(cleaned.values()),1) != 100.0:

        raise ValueError(

            "Weight normalisation failed"

        )



    with open(

        WEIGHT_FILE,

        "w"

    ) as f:


        json.dump(

            cleaned,

            f,

            indent=4

        )



    print(

        "\nWEIGHTS SAVED:",
        WEIGHT_FILE

    )


    return cleaned

# =====================================================
# Weight summary
# =====================================================

def get_weight_summary():


    weights = get_weights()



    return {


        "Weights":

            weights,


        "Total":

            round(

                sum(

                    weights.values()

                ),

                1

            )

    }

def govern_weights(weights):
    """
    Applies portfolio governance rules to optimiser output.

    Ensures:
    - all required components exist
    - weights total 100%
    - minimum diversification
    - technical score cannot dominate
    """

    MIN_WEIGHTS = {

        "technical_score": 40,
        "quality_score": 15,
        "growth_score": 10,
        "investment_score": 15

    }


    MAX_WEIGHTS = {

        "technical_score": 60,
        "quality_score": 30,
        "growth_score": 30,
        "investment_score": 30

    }


    governed = {}


    for component, value in weights.items():

        value = float(value)

        value = max(
            value,
            MIN_WEIGHTS.get(
                component,
                5
            )
        )

        value = min(
            value,
            MAX_WEIGHTS.get(
                component,
                50
            )
        )

        governed[component] = value



    # ensure missing components exist

    for component, value in MIN_WEIGHTS.items():

        if component not in governed:

            governed[component] = value



    # normalise to 100

    total = sum(
        governed.values()
    )


    for component in governed:

        governed[component] = round(

            (
                governed[component]
                /
                total
            )
            *
            100,

            1

        )


    return governed