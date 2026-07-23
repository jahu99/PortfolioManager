import pandas as pd
import os



def get_targets():

    path = os.path.join(
        os.path.dirname(__file__),
        "targets.csv"
    )


    return pd.read_csv(path)