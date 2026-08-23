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

        # HARD ALLOCATION LIMIT
        # =================================================
        #
        # The authoritative maximum allocation is supplied
        # by portfolio_context.py as:
        #
        #     "Maximum Allocation %"
        #
        # Do not use a separate hard-coded portfolio limit
        # here.
        #

        allocation = row.get(

            "Allocation %",

            None

        )

        maximum_allocation = row.get(

            "Maximum Allocation %",

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


        try:

            maximum_allocation = float(

                maximum_allocation

            )

        except (

            TypeError,

            ValueError

        ):

            maximum_allocation = None


        #

        # A genuine hard allocation breach must never

        # remain as an unexplained HOLD.

        #

        if (

            allocation is not None

            and

            maximum_allocation is not None

            and

            allocation > maximum_allocation

        ):

            breach_reason = (

                f"Position allocation of "

                f"{allocation:.2f}% exceeds the hard "

                f"maximum allocation of "

                f"{maximum_allocation:.2f}%."

            )


            #

            # Existing REDUCE / SELL decisions are

            # retained by the rule above. This branch is

            # defensive in case the action handling changes

            # in future.

            #

            if current_action in (

                "REDUCE",

                "SELL",

                "STRONG SELL"

            ):

                final_decisions.loc[

                    idx,

                    "Manager Reason"

                ] = (

                    breach_reason

                    + " Corrective action remains required."

                )

                continue


            #

            # An existing position above its hard maximum

            # requires corrective action.

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

                    breach_reason

                    + " Corrective REDUCE action required."

                )

                continue


            #

            # Additional capital cannot be deployed into

            # a position that already exceeds its maximum.

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

                    breach_reason

                    + " Additional allocation is blocked."

                )

                continue


            #

            # BUY NEW should not normally have an existing

            # allocation, but if allocation data indicates

            # a breach, block the new allocation.

            #

            if current_action == "BUY NEW":

                final_decisions.loc[

                    idx,

                    "Final Action"

                ] = "HOLD"

                final_decisions.loc[

                    idx,

                    "Manager Reason"

                ] = (

                    breach_reason

                    + " New capital allocation is blocked."

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