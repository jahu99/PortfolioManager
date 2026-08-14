import pandas as pd


def apply_portfolio_manager_rules(
    final_decisions,
    portfolio_health
):
    """
    Apply portfolio-level risk constraints to the final
    portfolio decisions.

    IMPORTANT:
    This function is NOT a second investment decision engine.

    generate_final_portfolio_decisions() determines the
    investment decision.

    This function only applies hard portfolio-management
    constraints that may override that decision.
    """

    if final_decisions is None:
        return pd.DataFrame()

    final_decisions = final_decisions.copy()

    if final_decisions.empty:
        return final_decisions

    # -----------------------------------------------------
    # Portfolio health
    # -----------------------------------------------------

    if not isinstance(portfolio_health, dict):
        portfolio_health = {}

    portfolio_risk = str(
        portfolio_health.get(
            "Risk Level",
            "NORMAL"
        )
    ).upper()


    # -----------------------------------------------------
    # Ensure Manager Reason exists
    # -----------------------------------------------------

    if "Manager Reason" not in final_decisions.columns:

        final_decisions["Manager Reason"] = ""


    # -----------------------------------------------------
    # Apply ONLY portfolio-level overrides
    # -----------------------------------------------------

    for idx, row in final_decisions.iterrows():

        current_action = str(
            row.get(
                "Final Action",
                "HOLD"
            )
        ).upper().strip()


        ticker = str(
            row.get(
                "Ticker",
                ""
            )
        ).upper().strip()


        # =================================================
        # DO NOT OVERRIDE AN EXISTING REDUCE / SELL
        # =================================================

        if current_action in [
            "REDUCE",
            "SELL"
        ]:

            if not row.get("Manager Reason", ""):

                final_decisions.loc[
                    idx,
                    "Manager Reason"
                ] = (
                    "Final portfolio decision retained; "
                    "no portfolio-level override required"
                )

            continue


        # =================================================
        # PORTFOLIO RISK OVERRIDE
        # =================================================

        #
        # If portfolio risk is HIGH, prevent additional
        # capital deployment.
        #
        # This does NOT force existing holdings to sell.
        #

        if portfolio_risk == "HIGH":

            if current_action == "BUY MORE":

                final_decisions.loc[
                    idx,
                    "Final Action"
                ] = "HOLD"

                final_decisions.loc[
                    idx,
                    "Manager Reason"
                ] = (
                    "Additional capital allocation blocked "
                    "because portfolio risk is currently HIGH"
                )

                continue


        # =================================================
        # ALLOCATION LIMIT
        # =================================================

        allocation = row.get(
            "Allocation %",
            None
        )


        try:

            allocation = float(
                allocation
            )

        except (
            TypeError,
            ValueError
        ):

            allocation = None


        #
        # Only apply this rule when allocation data actually
        # exists.
        #

        if (
            allocation is not None
            and
            allocation > 25
        ):

            #
            # Do not force a sale of a weak position that
            # happens to be overweight. The purpose here is
            # simply to flag the portfolio constraint.
            #

            if current_action == "BUY MORE":

                final_decisions.loc[
                    idx,
                    "Final Action"
                ] = "HOLD"

                final_decisions.loc[
                    idx,
                    "Manager Reason"
                ] = (
                    "Additional allocation blocked because "
                    "position exceeds the 25% portfolio limit"
                )

                continue


            #
            # If an existing position is already HOLD, an
            # overweight position can justify REDUCE.
            #

            if current_action == "HOLD":

                final_decisions.loc[
                    idx,
                    "Final Action"
                ] = "REDUCE"

                final_decisions.loc[
                    idx,
                    "Manager Reason"
                ] = (
                    "Position exceeds the 25% portfolio "
                    "allocation limit"
                )

                continue


        # =================================================
        # DEFAULT
        # =================================================

        if not row.get(
            "Manager Reason",
            ""
        ):

            final_decisions.loc[
                idx,
                "Manager Reason"
            ] = (
                "No portfolio-level constraint requires "
                "a change to the final decision"
            )


    return final_decisions