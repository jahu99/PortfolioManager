import pandas as pd


# ---------------------------------
# Helpers
# ---------------------------------

def safe_float(value):

    try:
        return float(value)

    except:

        return 0.0



def safe_dataframe(data):

    if data is None:
        return pd.DataFrame()


    if isinstance(data, pd.DataFrame):

        return data.copy()


    try:

        return pd.DataFrame(data)

    except:

        return pd.DataFrame()



def normalise_tickers(df):

    if (
        not df.empty
        and
        "Ticker" in df.columns
    ):

        df["Ticker"] = (
            df["Ticker"]
            .astype(str)
            .str.upper()
        )

    return df



# ---------------------------------
# Action priority
# ---------------------------------

ACTION_PRIORITY = {

    "SELL": 1,
    "REDUCE": 2,
    "BUY MORE": 3,
    "BUY": 4,
    "REVIEW": 5,
    "HOLD": 6

}



# ---------------------------------
# Main engine
# ---------------------------------

def generate_final_portfolio_decisions(
    portfolio_summary,
    portfolio_decisions,
    portfolio_ai_review,
    portfolio_manager_review,
    portfolio_health
):


    portfolio_summary = normalise_tickers(
        safe_dataframe(portfolio_summary)
    )


    portfolio_decisions = normalise_tickers(
        safe_dataframe(portfolio_decisions)
    )


    portfolio_ai_review = normalise_tickers(
        safe_dataframe(portfolio_ai_review)
    )



    portfolio_health = (
        portfolio_health
        if isinstance(
            portfolio_health,
            dict
        )
        else {}
    )



    # ---------------------------------
    # Portfolio risk
    # ---------------------------------

    portfolio_risk = portfolio_health.get(
        "Risk Level",
        "NORMAL"
    )



    # ---------------------------------
    # Start from holdings
    # ---------------------------------

    final = portfolio_summary.copy()



    # ---------------------------------
    # Add decisions
    # ---------------------------------

    if not portfolio_decisions.empty:


        cols = [

            c for c in [

                "Ticker",
                "Action",
                "Reason",
                "Investment Score",
                "AI Decision",
                "AI Conviction",
                "Signal"

            ]

            if c in portfolio_decisions.columns

        ]


        final = final.merge(

            portfolio_decisions[
                cols
            ],

            on="Ticker",

            how="left"

        )



    # ---------------------------------
    # Add AI review
    # ---------------------------------

    if not portfolio_ai_review.empty:


        cols = [

            c for c in [

                "Ticker",
                "AI Holding Decision",
                "AI Holding Conviction"

            ]

            if c in portfolio_ai_review.columns

        ]


        if len(cols) > 1:


            final = final.merge(

                portfolio_ai_review[
                    cols
                ],

                on="Ticker",

                how="left"

            )



    decisions = []



    # ---------------------------------
    # Existing holdings decisions
    # ---------------------------------

    for _, row in final.iterrows():


        ticker = row.get(
            "Ticker",
            ""
        )


        score = safe_float(
            row.get(
                "Investment Score",
                0
            )
        )


        action = row.get(
            "Action",
            ""
        )


        reason = row.get(
            "Reason",
            ""
        )


        ai = row.get(
            "AI Decision",
            ""
        )


        conviction = row.get(
            "AI Conviction",
            ""
        )



        if not action:


            if score < 45:

                action = "REDUCE"

                reason = (
                    "Investment score deterioration"
                )


            else:

                action = "HOLD"

                reason = (
                    "Holding remains appropriate"
                )



        decisions.append(

            {

                "Ticker": ticker,

                "Final Action": action,

                "Final Reason": reason,

                "Investment Score": score,

                "Signal":
                    row.get(
                        "Signal",
                        ""
                    ),

                "AI Decision": ai,

                "AI Conviction":
                    conviction,

                "Sector":
                    row.get(
                        "Sector",
                        "Unknown"
                    )

            }

        )



    result = pd.DataFrame(
        decisions
    )



    # ---------------------------------
    # Deduplicate
    # ---------------------------------

    if not result.empty:


        result["Priority"] = (
            result["Final Action"]
            .map(ACTION_PRIORITY)
            .fillna(99)
        )


        result = (

            result
            .sort_values(
                [
                    "Ticker",
                    "Priority"
                ]
            )
            .drop_duplicates(
                "Ticker",
                keep="first"
            )

        )



        result = result.drop(
            columns=[
                "Priority"
            ]
        )



    print(
        "FINAL PORTFOLIO DECISIONS CREATED:",
        result.shape
    )


    return result.reset_index(
        drop=True
    )