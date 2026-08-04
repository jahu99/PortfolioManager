# analysis/weight_optimizer.py

import os
import pandas as pd

from data.database import get_connection
from analysis.weight_controller import save_weights


WEIGHT_FILE = "data/optimised_weights.json"


# =====================================================
# Default weights
# =====================================================

DEFAULT_WEIGHTS = {

    "technical_score": 50.0,

    "quality_score": 20.0,

    "growth_score": 10.0,

    "investment_score": 20.0

}



# =====================================================
# Load learning data
# =====================================================

def load_learning_data():

    conn = get_connection()


    query = """

    SELECT

        technical_score,

        quality_score,

        growth_score,

        investment_score,

        return_percent,

        outcome


    FROM recommendation_evaluations


    WHERE return_percent IS NOT NULL

    """


    df = pd.read_sql_query(
        query,
        conn
    )


    conn.close()



    numeric_columns = [

        "technical_score",

        "quality_score",

        "growth_score",

        "investment_score",

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


    print(
        "\nCOMPONENT PERFORMANCE ANALYSIS"
    )


    components = [

        "technical_score",

        "quality_score",

        "growth_score",

        "investment_score"

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



        results.append(

            {

                "Component":
                    component,

                "Correlation":
                    round(
                        correlation,
                        3
                    )

            }

        )


    return pd.DataFrame(results)




# =====================================================
# Calculate optimised weights
# =====================================================

def calculate_weights(component_results):


    print(
        "\nCALCULATING OPTIMAL WEIGHTS"
    )


    MIN_WEIGHTS = {

        "technical_score": 30,

        "quality_score": 10,

        "growth_score": 10,

        "investment_score": 10

    }



    MAX_WEIGHTS = {

        "technical_score": 60,

        "quality_score": 30,

        "growth_score": 30,

        "investment_score": 40

    }



    correlations = {}



    for _, row in component_results.iterrows():


        correlation = max(

            row["Correlation"],

            0

        )


        correlations[

            row["Component"]

        ] = correlation




    total = sum(

        correlations.values()

    )



    if total == 0:

        return DEFAULT_WEIGHTS.copy()



    weights = {}



    for component, correlation in correlations.items():


        weight = (

            correlation

            /

            total

        ) * 100



        weight = max(

            weight,

            MIN_WEIGHTS[component]

        )


        weight = min(

            weight,

            MAX_WEIGHTS[component]

        )


        weights[component] = round(

            weight,

            1

        )



    # normalise

    total_weight = sum(

        weights.values()

    )



    for key in weights:


        weights[key] = round(

            weights[key]

            /

            total_weight

            *

            100,

            1

        )



    return weights




# =====================================================
# Generate actions
# =====================================================

def generate_actions(component_results):


    actions = []



    for _, row in component_results.iterrows():


        if row["Correlation"] > 0:


            action = "Increase weighting"

            reason = (
                "Positive historical return correlation"
            )


        else:


            action = "Maintain or reduce"

            reason = (
                "Negative historical return correlation"
            )



        actions.append(

            {

                "Component":
                    row["Component"],

                "Correlation":
                    row["Correlation"],

                "Action":
                    action,

                "Reason":
                    reason

            }

        )


    return pd.DataFrame(actions)




# =====================================================
# Main optimiser
# =====================================================

# =====================================================
# Main optimiser
# =====================================================

def run_weight_optimizer():

    print(
        "WEIGHT OPTIMISER START"
    )


    df = load_learning_data()


    print(
        f"Learning records: {len(df)}"
    )


    if df.empty:

        return {

            "Component Performance":
                pd.DataFrame(),


            "Raw Weights":
                DEFAULT_WEIGHTS,


            "Recommended Weights":
                DEFAULT_WEIGHTS,


            "Weight Actions":
                pd.DataFrame()

        }



    # -------------------------------------
    # Analyse component performance
    # -------------------------------------

    component_results = analyse_components(
        df
    )


    print(
        "\nCOMPONENT PERFORMANCE"
    )


    print(
        component_results
    )



    # -------------------------------------
    # Generate raw optimiser weights
    # -------------------------------------

    raw_weights = calculate_weights(
        component_results
    )


    print(
        "\nRAW OPTIMISER WEIGHTS"
    )


    print(
        raw_weights
    )



    # -------------------------------------
    # Apply governance controller
    # -------------------------------------

    from analysis.weight_controller import (
        govern_weights,
        save_weights
    )


    governed_weights = govern_weights(
        raw_weights
    )


    print(
        "\nGOVERNED WEIGHTS"
    )


    print(
        governed_weights
    )



    # -------------------------------------
    # Persist production weights
    # -------------------------------------

    save_weights(
        governed_weights
    )


    print(
        "\nWEIGHTS SAVED"
    )



    # -------------------------------------
    # Generate explanation
    # -------------------------------------

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
        # Used by reporting layer
        "Recommended Weights":
            governed_weights,


        "Weight Actions":
            actions

    }