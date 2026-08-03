import os
import json
import requests
from datetime import datetime, timedelta

CACHE_FILE = "data/cache/nasdaq_universe.json"

# -------------------------------------------------
# Cache handling
# -------------------------------------------------

def load_universe_cache():

    if not os.path.exists(CACHE_FILE):
        return None

    try:

        with open(CACHE_FILE, "r") as f:
            data = json.load(f)

        cache_date = datetime.strptime(
            data["date"],
            "%Y-%m-%d"
        )

        if datetime.today() - cache_date > timedelta(days=30):

            print("Universe cache expired")

            return None

        print(
            f"Using cached NASDAQ universe: {len(data['tickers'])} stocks"
        )

        return data["tickers"]

    except Exception as e:

        print(f"Universe cache error: {e}")

        return None


def save_universe_cache(tickers):

    os.makedirs(
        "data/cache",
        exist_ok=True
    )

    with open(CACHE_FILE, "w") as f:

        json.dump(
            {
                "date":
                    datetime.today().strftime("%Y-%m-%d"),
                "source":
                    "NASDAQ",
                "tickers":
                    tickers
            },
            f,
            indent=4
        )

    print(
        f"NASDAQ universe cached: {len(tickers)} stocks"
    )


# -------------------------------------------------
# Instrument cleanup
# -------------------------------------------------

EXCLUDED_SUFFIXES = (
    "W",      # Warrants
    "WS",
    "WT",
    "U",      # Units
    "R",      # Rights
    "RT",
    "P"       # Preferred shares
)


def is_common_stock(ticker):

    ticker = ticker.upper().strip()

    if len(ticker) == 0:
        return False

    # Remove obvious non-equity suffixes
    if ticker.endswith(EXCLUDED_SUFFIXES):
        return False

    # Ignore symbols containing punctuation
    if any(ch in ticker for ch in ".-^/"):
        return False

    return True


# -------------------------------------------------
# NASDAQ loader
# -------------------------------------------------

def load_nasdaq_universe():

    print("Loading NASDAQ universe...")

    url = (
        "https://api.nasdaq.com/api/screener/stocks"
        "?tableonly=true"
        "&limit=5000"
    )

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.nasdaq.com",
        "Referer": "https://www.nasdaq.com/"
    }

    try:

        response = requests.get(
            url,
            headers=headers,
            timeout=30
        )

        print(
            "NASDAQ STATUS:",
            response.status_code
        )

        data = response.json()

        rows = []

        if "data" in data:

            if isinstance(data["data"], dict):

                rows = (
                    data["data"]
                    .get("table", {})
                    .get("rows", [])
                )

        tickers = []

        for row in rows:

            symbol = row.get("symbol")

            if not symbol:
                continue

            symbol = symbol.upper().strip()

            if not symbol.isalpha():
                continue

            if len(symbol) > 5:
                continue

            if not is_common_stock(symbol):
                continue

            tickers.append(symbol)

        tickers = sorted(
            list(set(tickers))
        )

        print(
            f"NASDAQ common stock universe: {len(tickers)} stocks"
        )

        return tickers

    except Exception as e:

        print(f"NASDAQ loader failed: {e}")

        return []


# -------------------------------------------------
# Public interface
# -------------------------------------------------

def get_market_universe():

    """
    Returns cleaned investable NASDAQ universe.

    Cached for 30 days.
    """

    cached = load_universe_cache()

    if cached:
        return cached

    tickers = load_nasdaq_universe()

    if tickers:
        save_universe_cache(tickers)

    return tickers