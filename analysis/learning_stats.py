import pandas as pd


def calculate_learning_stats(
    history
):

    if history.empty:

        return {}


    stats = {}


    stats["Total Recommendations"] = len(history)


    stats["Success Rate"] = round(

        (
            history["Outcome"]
            ==
            "SUCCESS"
        ).mean()

        * 100,

        1
    )


    stats["Average Return"] = round(

        history["Return"]

        .mean(),

        2
    )


    return stats