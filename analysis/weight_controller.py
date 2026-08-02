import json
import os


DEFAULT_WEIGHTS = {

    "investment_score": 20,
    "technical_score": 50,
    "quality_score": 20,
    "growth_score": 10

}


WEIGHT_FILE = "data/optimised_weights.json"



def get_weights():

    """
    Loads optimised scoring weights.

    Falls back to defaults.
    """


    if not os.path.exists(WEIGHT_FILE):

        return DEFAULT_WEIGHTS



    try:

        with open(
            WEIGHT_FILE,
            "r"
        ) as f:

            weights = json.load(f)


        return weights



    except Exception:

        return DEFAULT_WEIGHTS