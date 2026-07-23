import pandas as pd


def generate_portfolio_recommendations(
    holdings,
    stock_results
):

    holdings_df = (
        holdings
        if isinstance(holdings, pd.DataFrame)
        else pd.DataFrame(holdings)
    )


    stocks_df = (
        stock_results
        if isinstance(stock_results, pd.DataFrame)
        else pd.DataFrame(stock_results)
    )


    recommendations = []


    # ---------------------------------
    # Calculate portfolio value
    # ---------------------------------

    portfolio_value = 0


    for _, holding in holdings_df.iterrows():

        ticker = holding["Ticker"]

        match = stocks_df[
            stocks_df["Ticker"] == ticker
        ]


        if not match.empty:

            price = float(
                match.iloc[0]["Price"]
            )

            portfolio_value += (
                float(holding["Shares"])
                *
                price
            )



    # ---------------------------------
    # Analyse holdings
    # ---------------------------------

    for _, holding in holdings_df.iterrows():

        ticker = holding["Ticker"]


        match = stocks_df[
            stocks_df["Ticker"] == ticker
        ]


        if match.empty:

            continue


        stock = match.iloc[0]


        price = float(stock["Price"])


        value = (
            float(holding["Shares"])
            *
            price
        )


        allocation = (
            value
            /
            portfolio_value
            *
            100
        )


        score = float(
            stock["Investment Score"]
        )


        signal = stock["Signal"]



        # ---------------------------------
        # Decision logic
        # ---------------------------------

        # Exceptional holdings
        if (
            score >= 85
            and allocation < 25
        ):

            action = "HOLD"

            reason = (
                "High conviction holding; "
                "maintain position"
            )


        # Strong holdings but large position
        elif (
            score >= 80
            and allocation >= 25
        ):

            action = "REVIEW"

            reason = (
                "Strong holding but "
                "portfolio concentration is high"
            )


        # Weak position in portfolio
        elif (
            score < 70
            and allocation > 15
        ):

            action = "REDUCE"

            reason = (
                "Large allocation with "
                "weaker investment score"
            )


        elif score < 60:

            action = "SELL"

            reason = (
                "Investment score has deteriorated"
            )


        elif score >= 75:

            action = "HOLD"

            reason = (
                "Quality holding with positive outlook"
            )


        else:

            action = "REVIEW"

            reason = (
                "Monitor investment performance"
            )



        recommendations.append(
            {
                "Ticker": ticker,

                "Action": action,

                "Signal": signal,

                "Investment Score": score,

                "Portfolio Weight %": round(
                    allocation,
                    2
                ),

                "Current Value": round(
                    value,
                    2
                ),

                "Reason": reason
            }
        )



    return pd.DataFrame(
        recommendations
    )