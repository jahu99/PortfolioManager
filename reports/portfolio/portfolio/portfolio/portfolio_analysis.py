def analyse_portfolio(
        holdings,
        market_results
    ):

    results = []

    prices = {
        item["Ticker"]: item["Price"]
        for item in market_results
    }

    total_value = 0

    for _, holding in holdings.iterrows():

        ticker = holding["Ticker"]

        if ticker in prices:

            value = (
                holding["Shares"]
                *
                prices[ticker]
            )

            total_value += value

            results.append(
                {
                    "Ticker": ticker,
                    "Value": value
                }
            )

    for item in results:

        item["Allocation %"] = round(
            item["Value"]
            /
            total_value
            *
            100,
            2
        )

    return results