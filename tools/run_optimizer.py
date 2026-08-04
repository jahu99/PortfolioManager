import sys
import os


# Add project root to Python path
PROJECT_ROOT = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

sys.path.insert(
    0,
    PROJECT_ROOT
)


from analysis.weight_optimizer import run_weight_optimizer



if __name__ == "__main__":

    results = run_weight_optimizer()


    print("\n===== OPTIMISER RESULTS =====")


    print(
        "\nRecommended Weights:"
    )

    print(
        results[
            "Recommended Weights"
        ]
    )


    print(
        "\nComponent Performance:"
    )

    print(
        results[
            "Component Performance"
        ]
    )


    print(
        "\nWeight Actions:"
    )

    print(
        results[
            "Weight Actions"
        ]
    )