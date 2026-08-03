import yfinance as yf
import pandas as pd


ETF_TICKERS = {
    "IWDA",
    "VUAA",
    "SEC0"
}


def classify_security(ticker, name=""):

    ticker = str(ticker).upper()
    name = str(name).upper()

    if ticker == "CASH":
        return "CASH"

    if ticker in ETF_TICKERS:
        return "ETF"

    if "ETF" in name:
        return "ETF"

    if "ISHARES" in name:
        return "ETF"

    if "VANGUARD" in name:
        return "ETF"

    return "STOCK"



def get_close_series(data):

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
    # Stock metadata lookup
    # ---------------------------------

    stock_lookup = {}


    if stock_results:

        for stock in stock_results:

            ticker = stock.get(
                "Ticker"
            )


            stock_lookup[ticker] = {

                "Score":
                    stock.get("Score"),

                "Signal":
                    stock.get("Signal"),

                "Quality Score":
                    stock.get(
                        "Quality Score"
                    ),

                "Investment Score":
                    stock.get(
                        "Investment Score"
                    ),

                "Sector":
                    stock.get(
                        "Sector",
                        "Unknown"
                    ),

                "Industry":
                    stock.get(
                        "Industry",
                        "Unknown"
                    )

            }



    # ---------------------------------
    # Validate normalised portfolio
    # ---------------------------------

    required = [

        "Ticker",
        "Name",
        "Shares",
        "Current Value"

    ]


    missing = [

        c for c in required
        if c not in holdings.columns

    ]


    if missing:

        raise ValueError(
            f"Missing portfolio columns: {missing}"
        )



    holdings = holdings.copy()



    holdings["Shares"] = pd.to_numeric(
        holdings["Shares"],
        errors="coerce"
    )


    holdings["Current Value"] = pd.to_numeric(
        holdings["Current Value"],
        errors="coerce"
    )



    holdings["Ticker"] = (
        holdings["Ticker"]
        .astype(str)
        .str.upper()
        .str.strip()
    )



    holdings = holdings.dropna(
        subset=[
            "Ticker",
            "Current Value"
        ]
    )



    holdings = holdings[
        holdings["Ticker"] != "TOTAL"
    ]



    total_value = holdings[
        "Current Value"
    ].sum()



    if total_value <= 0:

        raise ValueError(
            "Portfolio value invalid"
        )



    # ---------------------------------
    # Analyse holdings
    # ---------------------------------

    for _, row in holdings.iterrows():


        ticker = row["Ticker"]

        name = row["Name"]

        shares = row["Shares"]

        current_value = float(
            row["Current Value"]
        )


        security_type = classify_security(
            ticker,
            name
        )


        metadata = stock_lookup.get(
            ticker,
            {}
        )



        base = {

            "Ticker":
                ticker,

            "Name":
                name,

            "Type":
                security_type,

            "Shares":
                shares,

            "Current Value":
                current_value,

            "Allocation %":
                round(
                    current_value /
                    total_value *
                    100,
                    2
                )

        }



        # -----------------------------
        # Cash
        # -----------------------------

        if security_type == "CASH":

            results.append({

                **base,

                "Sector":
                    "Cash",

                "Industry":
                    "Cash",

                "Trend":
                    "Cash"

            })

            continue



        # -----------------------------
        # ETFs
        # -----------------------------

        if security_type == "ETF":

            results.append({

                **base,

                "Sector":
                    "ETF",

                "Industry":
                    "Fund",

                "Trend":
                    "Passive"

            })

            continue



        # -----------------------------
        # Stocks
        # -----------------------------

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



            results.append({

                **base,


                "Current Price":
                    current_price,

                "MA50":
                    ma50,

                "MA200":
                    ma200,

                "Trend":
                    trend,


                "Sector":
                    metadata.get(
                        "Sector",
                        "Unknown"
                    ),


                "Industry":
                    metadata.get(
                        "Industry",
                        "Unknown"
                    ),


                "Momentum Score":
                    metadata.get(
                        "Score"
                    ),


                "Momentum Signal":
                    metadata.get(
                        "Signal"
                    ),


                "Quality Score":
                    metadata.get(
                        "Quality Score"
                    ),


                "Investment Score":
                    metadata.get(
                        "Investment Score"
                    )

            })



        except Exception as e:

            print(
                f"Portfolio error {ticker}: {e}"
            )



    df = pd.DataFrame(
        results
    )


    if df.empty:

        return df



    # ---------------------------------
    # Sector analysis
    # ---------------------------------

    sector_totals = (

        df.groupby(
            "Sector"
        )["Current Value"]
        .sum()

    )



    df["Sector Allocation %"] = (

        df["Sector"]
        .map(
            sector_totals /
            total_value *
            100
        )
        .round(2)

    )



    df["Sector Risk"] = (

        df["Sector Allocation %"]
        .apply(

            lambda x:

            "High"
            if x > 40

            else

            "Medium"
            if x > 25

            else

            "Low"

        )

    )



    return df