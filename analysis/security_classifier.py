ETF_TICKERS = {

    "IWDA",
    "VUAA",
    "SEC0"

}


def classify_security(ticker, name=""):

    ticker = ticker.upper()

    name = name.upper()


    if ticker in ETF_TICKERS:
        return "ETF"


    if "ETF" in name:
        return "ETF"


    if "ISHARES" in name:
        return "ETF"


    if "VANGUARD" in name:
        return "ETF"


    return "STOCK"