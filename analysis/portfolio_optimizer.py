import pandas as pd



def optimise_portfolio(
    portfolio_summary,
    targets
):


    if portfolio_summary is None or portfolio_summary.empty:

        return pd.DataFrame()



    if targets is None or targets.empty:

        return pd.DataFrame()



    recommendations = []



    # ---------------------------------
    # Compare actual vs target
    # ---------------------------------

    for _, target in targets.iterrows():


        sector = target["Sector"]

        target_pct = float(
            target["Target %"]
        )


        current = portfolio_summary[
            portfolio_summary["Sector"] == sector
        ]



        if current.empty:

            actual_pct = 0

        else:

            actual_pct = float(
                current.iloc[0]["Allocation %"]
            )



        difference = (
            actual_pct
            -
            target_pct
        )



        if difference > 10:

            action = "REDUCE"

            reason = (
                f"{sector} is "
                f"{round(difference,1)}% "
                "above target"
            )


        elif difference < -10:

            action = "ADD"

            reason = (
                f"{sector} is "
                f"{round(abs(difference),1)}% "
                "below target"
            )


        else:

            action = "HOLD"

            reason = (
                "Within target range"
            )



        recommendations.append(
            {

                "Sector": sector,

                "Current %": round(
                    actual_pct,
                    2
                ),

                "Target %": target_pct,

                "Difference %": round(
                    difference,
                    2
                ),

                "Action": action,

                "Reason": reason

            }
        )



    return pd.DataFrame(
        recommendations
    )