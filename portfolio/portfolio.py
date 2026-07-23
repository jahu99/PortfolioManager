import pandas as pd
import os


def get_portfolio():

    file_path = os.path.join(
        os.path.dirname(__file__),
        "holdings.csv"
    )

    portfolio = pd.read_csv(file_path)

    return portfolio