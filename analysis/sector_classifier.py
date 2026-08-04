# analysis/sector_classifier.py

"""
Central sector classification engine.

Priority:
1. Manual overrides
2. ETFs / Cash
3. Existing sector data
4. External metadata
5. Unknown
"""


# -------------------------------------------------
# Manual sector overrides
# -------------------------------------------------

SECTOR_OVERRIDES = {

    # Technology
    "NVDA": "Technology",
    "MSFT": "Technology",
    "AAPL": "Technology",
    "PLTR": "Technology",
    "ARM": "Technology",
    "IONQ": "Technology",
    "STX": "Technology",
    "APLD": "Technology",
    "VRDN": "Healthcare",


    # Communication Services
    "GOOGL": "Communication Services",


    # Consumer
    "AMZN": "Consumer Cyclical",
    "MELI": "Consumer Cyclical",


    # Industrials
    "GE": "Industrials",
    "CSX": "Industrials",
    "ETN": "Industrials",


    # Financials
    "BBVA": "Financial Services",
    "MA": "Financial Services",
    "FITB": "Financial Services",
    "NWG": "Financial Services",


    # ETFs
    "IWDA": "ETF",
    "VUAA": "ETF",
    "SEC0": "ETF",


    # Cash
    "CASH": "Cash"

}



# -------------------------------------------------
# Classifier
# -------------------------------------------------

def classify_sector(
    ticker,
    existing_sector=None
):


    if ticker is None:

        return "Unknown"



    ticker = (
        str(ticker)
        .upper()
        .strip()
    )



    # Manual override first

    if ticker in SECTOR_OVERRIDES:

        return SECTOR_OVERRIDES[ticker]



    # ETF detection

    if existing_sector:

        existing_sector = str(
            existing_sector
        ).strip()


        if existing_sector.upper() in [
            "ETF",
            "FUND"
        ]:

            return "ETF"


        if existing_sector.upper() == "CASH":

            return "Cash"



        if existing_sector not in [
            "",
            "Unknown",
            "Not Classified",
            "NOT CLASSIFIED"
        ]:

            return existing_sector



    return "Unknown"