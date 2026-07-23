SECTOR_MAP = {

    "AAPL": "Technology",
    "MSFT": "Technology",
    "NVDA": "Technology",
    "GOOGL": "Communication Services",
    "META": "Communication Services",
    "AMZN": "Consumer Discretionary",

    "JPM": "Financials",
    "BAC": "Financials",
    "GS": "Financials",

    "LLY": "Healthcare",
    "JNJ": "Healthcare",
    "UNH": "Healthcare",

    "XOM": "Energy",
    "CVX": "Energy",

    "NEE": "Utilities",

    "PG": "Consumer Staples",
    "KO": "Consumer Staples",

    "CAT": "Industrials",
    "GE": "Industrials"

}


def get_sector(ticker):

    return SECTOR_MAP.get(
        ticker,
        "Unknown"
    )