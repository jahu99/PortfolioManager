"""
Universe Manager

Provides a unified investment universe.

Currently supports:
- S&P 500

Future:
- Nasdaq 100
- Dow Jones 30
- FTSE 100
- ETFs
- Custom watchlists
"""


from data.universe import get_sp500_universe



# -------------------------------------------------
# Market loaders
# -------------------------------------------------

def load_sp500():

    return get_sp500_universe()



def load_nasdaq100():

    """
    Placeholder for Nasdaq 100 integration
    """

    return []



def load_dow30():

    """
    Placeholder for Dow Jones integration
    """

    return []



def load_ftse100():

    """
    Placeholder for FTSE 100 integration
    """

    return []



def load_etfs():

    """
    Placeholder for ETF universe
    """

    return []



# -------------------------------------------------
# Main universe function
# -------------------------------------------------

def get_universe(
    markets=None
):

    """
    Returns combined investment universe.

    Example:

    get_universe(
        [
            "sp500",
            "nasdaq100"
        ]
    )

    """

    if markets is None:

        markets = [
            "sp500"
        ]


    universe = []


    loaders = {

        "sp500":
            load_sp500,

        "nasdaq100":
            load_nasdaq100,

        "dow30":
            load_dow30,

        "ftse100":
            load_ftse100,

        "etfs":
            load_etfs

    }



    for market in markets:


        if market not in loaders:

            print(
                f"Unknown market ignored: {market}"
            )

            continue


        print(
            f"Loading universe: {market}"
        )


        tickers = loaders[market]()


        universe.extend(
            tickers
        )


    # Remove duplicates

    # Remove duplicates while preserving order

    universe = list(
        dict.fromkeys(universe)
    )


    universe.sort()
    


    print(
        f"TOTAL UNIVERSE SIZE: {len(universe)}"
    )


    return universe