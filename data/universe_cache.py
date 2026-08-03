import json
import os
from datetime import datetime, timedelta


CACHE_FILE = "data/cache/universe_cache.json"


def save_universe(tickers):

    os.makedirs(
        "data/cache",
        exist_ok=True
    )

    data = {
        "date": datetime.today().strftime("%Y-%m-%d"),
        "tickers": tickers
    }

    with open(
        CACHE_FILE,
        "w"
    ) as f:

        json.dump(
            data,
            f
        )


def load_universe():

    if not os.path.exists(CACHE_FILE):
        return None


    with open(
        CACHE_FILE,
        "r"
    ) as f:

        data = json.load(f)


    cache_date = datetime.strptime(
        data["date"],
        "%Y-%m-%d"
    )


    # refresh monthly
    if datetime.today() - cache_date > timedelta(days=30):
        return None


    return data["tickers"]