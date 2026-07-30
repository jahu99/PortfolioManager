import pandas as pd


def generate_growth_plan(
    portfolio_summary,
    stock_results,
    portfolio_health=None,
    portfolio_value=None
):

     

    if portfolio_summary is None:
        portfolio_summary = pd.DataFrame()


    if portfolio_health is None:
        portfolio_health = {}
    
    growth_plan = []


    if portfolio_summary is None:
        portfolio_summary = pd.DataFrame()


    if portfolio_summary.empty:
        return pd.DataFrame()


    results_lookup = {
        r["Ticker"]: r
        for r in stock_results
    }

    if portfolio_value is None:

        if (
            portfolio_summary is not None
            and not portfolio_summary.empty
            and "Current Value" in portfolio_summary.columns
        ):
            portfolio_value = portfolio_summary["Current Value"].sum()

        else:
            portfolio_value = 0


    for _, holding in portfolio_summary.iterrows():

        ticker = holding["Ticker"]


        stock = results_lookup.get(
            ticker,
            {}
        )


        investment_score = stock.get(
            "Investment Score",
            0
        )


        quality_score = stock.get(
            "Quality Score",
            0
        )


        current_value = holding.get(
            "Current Value",
            0
        )


        allocation = holding.get(
            "Allocation %",
            0
        )


        action = "HOLD"


        stage = "Starter Position"


        reason = []


        # -----------------------------
        # Position sizing
        # -----------------------------

        if current_value < 500:

            stage = "Starter Position"


        elif current_value < 2000:

            stage = "Building Position"


        elif current_value < 10000:

            stage = "Core Holding"


        else:

            stage = "Conviction Holding"



        # -----------------------------
        # Growth decision
        # -----------------------------


        if investment_score >= 85:

            action = "ADD"

            reason.append(
                "High conviction investment score"
            )


        elif investment_score >= 70:

            action = "ACCUMULATE"

            reason.append(
                "Suitable for gradual position building"
            )


        elif investment_score < 50:

            action = "REDUCE"

            reason.append(
                "Weak investment fundamentals"
            )



        # -----------------------------
        # Risk controls
        # -----------------------------


        if allocation >= 30:

            action = "REVIEW"

            reason.append(
                "Position size exceeds portfolio target"
            )


        if quality_score < 50:

            reason.append(
                "Business quality below target"
            )



        growth_plan.append(
            {

                "Ticker": ticker,

                "Current Value":
                    current_value,

                "Allocation %":
                    allocation,

                "Growth Stage":
                    stage,

                "Recommended Action":
                    action,

                "Investment Score":
                    investment_score,

                "Quality Score":
                    quality_score,

                "Reason":
                    "; ".join(reason)

            }
        )


    return pd.DataFrame(
        growth_plan
    )