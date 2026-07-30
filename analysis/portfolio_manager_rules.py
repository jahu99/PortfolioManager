def apply_portfolio_manager_rules(
    final_decisions,
    portfolio_health
):

    for idx,row in final_decisions.iterrows():

        ticker = row["Ticker"]

        score = row.get(
            "Investment Score",
            0
        )

        allocation = row.get(
            "Allocation %",
            0
        )


        # Overweight rule

        if allocation and allocation > 25:

            final_decisions.loc[
                idx,
                "Final Action"
            ] = "REDUCE"

            final_decisions.loc[
                idx,
                "Manager Reason"
            ] = (
                "Position exceeds portfolio allocation limit"
            )


        # Weak investment score

        elif score < 55:

            final_decisions.loc[
                idx,
                "Final Action"
            ] = "REDUCE"

            final_decisions.loc[
                idx,
                "Manager Reason"
            ] = (
                "Investment score below portfolio threshold"
            )


        else:

            final_decisions.loc[
                idx,
                "Manager Reason"
            ] = (
                "Holding remains appropriate"
            )


    return final_decisions