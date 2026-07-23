import yfinance as yf
import pandas as pd



def get_close_series(data):

    """
    Handles yfinance returning either:
    - normal Series
    - DataFrame with multi-level columns
    """

    close = data["Close"]

    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]

    return close



def analyse_portfolio(
    holdings,
    stock_results=None
):

    results = []


    # ---------------------------------
    # Create stock lookup
    # ---------------------------------

    stock_lookup = {}


    if stock_results:

        for stock in stock_results:

            stock_lookup[
                stock["Ticker"]
            ] = {

                "Score": stock.get(
                    "Score"
                ),

                "Signal": stock.get(
                    "Signal"
                ),

                "Quality Score": stock.get(
                    "Quality Score"
                ),

                "Investment Score": stock.get(
                    "Investment Score"
                ),

                "Sector": stock.get(
                    "Sector",
                    "Unknown"
                ),

                "Industry": stock.get(
                    "Industry",
                    "Unknown"
                )

            }



    # ---------------------------------
    # First pass - calculate values
    # ---------------------------------

    total_value = 0

    temp_results = []



    for _, stock in holdings.iterrows():

        ticker = stock["Ticker"]

        shares = float(
            stock["Shares"]
        )

        average_cost = float(
            stock["AverageCost"]
        )



        try:

            print(
                f"Analysing portfolio holding: {ticker}"
            )


            data = yf.download(
                ticker,
                period="1y",
                progress=False,
                auto_adjust=False
            )


            if data.empty:
                continue



            close = get_close_series(
                data
            ).dropna()



            if len(close) < 50:
                continue



            current_price = float(
                close.iloc[-1]
            )


            current_value = (
                shares *
                current_price
            )


            invested_value = (
                shares *
                average_cost
            )


            gain_loss = (
                current_value -
                invested_value
            )


            return_pct = (
                gain_loss /
                invested_value
            ) * 100



            ma50 = float(
                close.tail(50).mean()
            )


            ma200 = float(
                close.tail(200).mean()
            )



            if (
                current_price > ma50
                and current_price > ma200
            ):

                trend = "Positive"


            elif current_price < ma200:

                trend = "Negative"


            else:

                trend = "Neutral"



            metadata = stock_lookup.get(
                ticker,
                {}
            )



            temp_results.append(
                {

                    "Ticker": ticker,

                    "Shares": shares,

                    "Average Cost": average_cost,

                    "Current Price": current_price,

                    "Invested Value": invested_value,

                    "Current Value": current_value,

                    "Gain/Loss": gain_loss,

                    "Return %": return_pct,

                    "MA50": ma50,

                    "MA200": ma200,

                    "Trend": trend,


                    "Sector": metadata.get(
                        "Sector",
                        "Unknown"
                    ),


                    "Industry": metadata.get(
                        "Industry",
                        "Unknown"
                    )

                }
            )


            total_value += current_value



        except Exception as e:

            print(
                f"Portfolio error {ticker}: {e}"
            )



    # ---------------------------------
    # Second pass - portfolio metrics
    # ---------------------------------

    for item in temp_results:


        allocation = (
            item["Current Value"]
            /
            total_value
        ) * 100



        ticker = item["Ticker"]


        metadata = stock_lookup.get(
            ticker,
            {}
        )



        results.append(
            {

                **item,


                "Allocation %": round(
                    allocation,
                    2
                ),


                "Momentum Score": metadata.get(
                    "Score"
                ),


                "Momentum Signal": metadata.get(
                    "Signal"
                ),


                "Quality Score": metadata.get(
                    "Quality Score"
                ),


                "Investment Score": metadata.get(
                    "Investment Score"
                )

            }
        )



    return pd.DataFrame(results)