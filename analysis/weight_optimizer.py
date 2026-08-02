# analysis/weight_optimizer.py

import os
import json
import pandas as pd

from data.database import get_connection


WEIGHT_FILE = "data/optimised_weights.json"


# =====================================================
# Default weights
# =====================================================

DEFAULT_WEIGHTS = {

    "technical_score": 50.0,

    "quality_score": 15.0,

    "growth_score": 15.0,

    "confidence_score": 10.0,

    "investment_score": 10.0

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

        confidence_score,

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


    # Ensure numeric

    numeric_columns = [

        "technical_score",

        "quality_score",

        "growth_score",

        "confidence_score",

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
# Component correlation analysis
# =====================================================

def analyse_components(df):

    print(
        "\nCOMPONENT PERFORMANCE ANALYSIS"
    )


    components = [

        "technical_score",

        "quality_score",

        "growth_score",

        "confidence_score",

        "investment_score"

    ]


    rows = []


    for component in components:


        correlation = df[component].corr(
            df["return_percent"]
        )


        if pd.isna(correlation):

            correlation = 0



        rows.append(

            {

                "Component": component,

                "Correlation": round(
                    correlation,
                    3
                )

            }

        )


    return pd.DataFrame(rows)



# =====================================================
# Calculate optimal weights
# =====================================================

def calculate_weights(component_results):


    print(
        "\nCALCULATING OPTIMAL WEIGHTS"
    )


    MIN_WEIGHTS = {


        "technical_score": 30,

        "quality_score": 10,

        "growth_score": 10,

        "confidence_score": 10,

        "investment_score": 10

    }


    MAX_WEIGHTS = {


        "technical_score": 60,

        "quality_score": 30,

        "growth_score": 30,

        "confidence_score": 30,

        "investment_score": 40

    }



    correlations = {}



    for _, row in component_results.iterrows():


        correlation = row["Correlation"]


        # Ignore negative predictors

        correlation = max(
            correlation,
            0
        )


        correlations[
            row["Component"]
        ] = correlation



    total = sum(
        correlations.values()
    )



    # fallback

    if total == 0:

        return DEFAULT_WEIGHTS



    weights = {}



    for component, correlation in correlations.items():


        weight = (

            correlation

            /

            total

        ) * 100



        weight = max(

            weight,

            MIN_WEIGHTS.get(
                component,
                5
            )

        )


        weight = min(

            weight,

            MAX_WEIGHTS.get(
                component,
                50
            )

        )


        weights[component] = round(
            weight,
            1
        )



    # Normalise to 100%

    total_weight = sum(
        weights.values()
    )



    for component in weights:

        weights[component] = round(

            (

                weights[component]

                /

                total_weight

            )

            * 100,

            1

        )


    return weights



# =====================================================
# Save weights
# =====================================================

def save_weights(weights):


    os.makedirs(

        "data",

        exist_ok=True

    )


    with open(

        WEIGHT_FILE,

        "w"

    ) as f:


        json.dump(

            weights,

            f,

            indent=4

        )



# =====================================================
# Generate actions
# =====================================================

def generate_actions(component_results):


    actions = []


    for _, row in component_results.iterrows():


        correlation = row["Correlation"]


        if correlation > 0:


            action = "Increase weighting"

            reason = (
                "Positive historical return correlation"
            )


        else:


            action = "Reduce weighting"

            reason = (
                "Negative historical return correlation"
            )



        actions.append(

            {

                "Component":
                    row["Component"],


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


            "Recommended Weights":
                DEFAULT_WEIGHTS,


            "Weight Actions":
                pd.DataFrame()

        }



    component_results = analyse_components(
        df
    )


    print(
        component_results
    )



    weights = calculate_weights(
        component_results
    )



    print(
        "\nOPTIMISED WEIGHTS"
    )


    print(
        weights
    )



    save_weights(
        weights
    )



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


        "Recommended Weights":
            weights,


        "Weight Actions":
            actions

    }