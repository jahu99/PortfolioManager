import pandas as pd


def generate_alerts(portfolio_summary, stock_results):

    alerts = []


    # -------------------------------
    # Portfolio alerts
    # -------------------------------

    if (
        portfolio_summary is not None
        and not portfolio_summary.empty
    ):


        for _, holding in portfolio_summary.iterrows():

            ticker = holding["Ticker"]

            allocation = None


            # Calculate allocation if available
            if "Current Value" in holding:

                total_value = (
                    portfolio_summary["Current Value"]
                    .sum()
                )

                allocation = (
                    holding["Current Value"]
                    /
                    total_value
                    *
                    100
                )


            if (
                allocation is not None
                and allocation > 40
            ):

                alerts.append(
                    {
                        "Type": "Concentration Risk",

                        "Ticker": ticker,

                        "Message":
                        f"{ticker} represents "
                        f"{allocation:.1f}% of portfolio"
                    }
                )



            # Price below MA200 warning

            if (
                "Current Price" in holding
                and "MA200" in holding
            ):

                if holding["Current Price"] < holding["MA200"]:

                    alerts.append(
                        {
                            "Type": "Trend Warning",

                            "Ticker": ticker,

                            "Message":
                            f"{ticker} is below "
                            "its 200 day moving average"
                        }
                    )



    # -------------------------------
    # Market opportunity alerts
    # -------------------------------

    if stock_results:


        for stock in stock_results[:20]:

            if (
                stock["Signal"] == "BUY"
                and stock["Score"] >= 80
            ):

                alerts.append(
                    {
                        "Type": "Opportunity",

                        "Ticker": stock["Ticker"],

                        "Message":
                        f"{stock['Ticker']} has a "
                        f"strong momentum score "
                        f"({stock['Score']})"
                    }
                )



    return pd.DataFrame(alerts)