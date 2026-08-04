"""
Capital Allocation Engine

Purpose:

- Manage portfolio capital allocation
- Use discretionary spend limit
- Reinvest released capital
- Decide:

    BUY NEW
    BUY MORE
    HOLD
    REDUCE
    SELL

Interface preserved for:
main.py
excel_report.py

"""

import pandas as pd


from config.investment_config import (
    DISCRETIONARY_SPEND_LIMIT,
    MAX_NEW_BUYS,
    MAX_BUY_MORE,
    MIN_NEW_BUY_SCORE,
    MIN_BUY_MORE_SCORE,
    MIN_ALLOCATION_AMOUNT
)



# =====================================================
# Helpers
# =====================================================

def safe_float(value, default=0.0):

    try:

        if value is None:
            return default

        return float(value)

    except Exception:

        return default



def safe_text(value, default=""):

    if value is None:
        return default

    return str(value)



# =====================================================
# Capital Allocation Engine
# =====================================================

def generate_capital_allocation(
    portfolio_summary,
    opportunities=None,
    portfolio_decisions=None
):


    if portfolio_summary is None:
        portfolio_summary = pd.DataFrame()


    if opportunities is None:
        opportunities = pd.DataFrame()


    if portfolio_decisions is None:
        portfolio_decisions = pd.DataFrame()



    allocations = []



    # =================================================
    # Existing portfolio values
    # =================================================

    portfolio_values = {}

    existing_tickers = set()



    if (
        isinstance(
            portfolio_summary,
            pd.DataFrame
        )
        and
        not portfolio_summary.empty
    ):


        if "Ticker" in portfolio_summary.columns:


            for _, holding in portfolio_summary.iterrows():


                ticker = safe_text(
                    holding.get(
                        "Ticker",
                        ""
                    )
                ).upper()


                if ticker:


                    existing_tickers.add(
                        ticker
                    )


                    portfolio_values[ticker] = safe_float(
                        holding.get(
                            "Current Value",
                            0
                        )
                    )



    # =================================================
    # Calculate released capital
    # =================================================

    released_capital = 0



    if not portfolio_decisions.empty:


        for _, row in portfolio_decisions.iterrows():


            ticker = safe_text(
                row.get(
                    "Ticker",
                    ""
                )
            ).upper()



            # Cash is not a trade

            if ticker == "CASH":

                continue



            action = safe_text(
                row.get(
                    "Action",
                    "HOLD"
                )
            ).upper()



            current_value = portfolio_values.get(
                ticker,
                0
            )



            if action in [
                "REDUCE",
                "SELL"
            ]:


                release_amount = round(

                    current_value * 0.25,

                    2

                )


                released_capital += release_amount



                allocations.append(

                    {

                        "Ticker":
                            ticker,

                        "Action":
                            action,

                        "Existing Holding":
                            "Yes",

                        "Amount":
                            -release_amount,

                        "Funding Source":
                            "Released Capital",

                        "Reason":
                            row.get(
                                "Reason",
                                "Weak holding reduced"
                            )

                    }

                )



    # =================================================
    # Available capital
    # =================================================

    total_available_capital = round(

        DISCRETIONARY_SPEND_LIMIT

        +

        released_capital,

        2

    )



    # =================================================
    # BUY MORE candidates
    # =================================================

    buy_more_candidates = []



    if not portfolio_decisions.empty:


        for _, row in portfolio_decisions.iterrows():


            ticker = safe_text(
                row.get(
                    "Ticker",
                    ""
                )
            ).upper()



            action = safe_text(
                row.get(
                    "Action",
                    ""
                )
            ).upper()



            score = safe_float(
                row.get(
                    "Investment Score",
                    0
                )
            )



            if (

                ticker

                and

                action in [
                    "BUY",
                    "BUY MORE",
                    "ADD"
                ]

                and

                score >= MIN_BUY_MORE_SCORE

                and

                ticker in existing_tickers

            ):


                buy_more_candidates.append(

                    {

                        "Ticker":
                            ticker,

                        "Score":
                            score,

                        "Existing Holding":
                            "Yes",

                        "Reason":
                            "Increase existing high conviction holding"

                    }

                )



    buy_more_candidates = sorted(

        buy_more_candidates,

        key=lambda x:
            x["Score"],

        reverse=True

    )[:MAX_BUY_MORE]

        # =================================================
    # BUY NEW candidates
    # =================================================

    buy_new_candidates = []


    if not opportunities.empty:


        for _, row in opportunities.iterrows():


            ticker = safe_text(
                row.get(
                    "Ticker",
                    ""
                )
            ).upper()



            score = safe_float(
                row.get(
                    "Investment Score",
                    0
                )
            )



            # IMPORTANT:
            # Do not buy new stocks already held

            if (

                ticker

                and

                ticker not in existing_tickers

                and

                score >= MIN_NEW_BUY_SCORE

            ):


                buy_new_candidates.append(

                    {

                        "Ticker":
                            ticker,

                        "Score":
                            score,

                        "Existing Holding":
                            "No",

                        "Reason":
                            "High conviction opportunity"

                    }

                )



    buy_new_candidates = sorted(

        buy_new_candidates,

        key=lambda x:
            x["Score"],

        reverse=True

    )[:MAX_NEW_BUYS]



    # =================================================
    # Allocate capital
    #
    # Split equally across:
    #
    # BUY MORE
    # BUY NEW
    #
    # =================================================

    buy_candidates = (

        buy_more_candidates

        +

        buy_new_candidates

    )


    if buy_candidates:


        allocation_amount = round(

            total_available_capital

            /

            len(
                buy_candidates
            ),

            2

        )


    else:

        allocation_amount = 0



    capital_allocated = 0



    for candidate in buy_candidates:


        amount = min(

            allocation_amount,

            total_available_capital - capital_allocated

        )


        if amount < MIN_ALLOCATION_AMOUNT:

            continue



        action = (

            "BUY MORE"

            if candidate["Existing Holding"] == "Yes"

            else

            "BUY NEW"

        )


        allocations.append(

            {

                "Ticker":
                    candidate["Ticker"],

                "Action":
                    action,

                "Existing Holding":
                    candidate["Existing Holding"],

                "Amount":
                    round(
                        amount,
                        2
                    ),

                "Funding Source":
                    "Discretionary Spend + Released Capital",

                "Reason":
                    candidate["Reason"]

            }

        )


        capital_allocated += amount



    # =================================================
    # HOLD positions
    # =================================================

    if not portfolio_decisions.empty:


        for _, row in portfolio_decisions.iterrows():


            ticker = safe_text(
                row.get(
                    "Ticker",
                    ""
                )
            ).upper()



            action = safe_text(
                row.get(
                    "Action",
                    ""
                )
            ).upper()



            if (

                action == "HOLD"

                and

                ticker != "CASH"

            ):


                allocations.append(

                    {

                        "Ticker":
                            ticker,

                        "Action":
                            "HOLD",

                        "Existing Holding":
                            "Yes",

                        "Amount":
                            0,

                        "Funding Source":
                            "",

                        "Reason":
                            row.get(
                                "Reason",
                                "Maintain position"
                            )

                    }

                )



    # =================================================
    # AVOID non-held opportunities
    # =================================================

    if not opportunities.empty:


        for _, row in opportunities.iterrows():


            ticker = safe_text(
                row.get(
                    "Ticker",
                    ""
                )
            ).upper()



            score = safe_float(
                row.get(
                    "Investment Score",
                    0
                )
            )



            if (

                ticker

                and

                ticker not in existing_tickers

                and

                score < MIN_NEW_BUY_SCORE

            ):


                allocations.append(

                    {

                        "Ticker":
                            ticker,

                        "Action":
                            "AVOID",

                        "Existing Holding":
                            "No",

                        "Amount":
                            0,

                        "Funding Source":
                            "",

                        "Reason":
                            "Low conviction"

                    }

                )



    # =================================================
    # Create allocation dataframe
    # =================================================

    allocation_df = pd.DataFrame(
        allocations
    )



    if not allocation_df.empty:


        allocation_df = allocation_df[

            [
                "Ticker",
                "Action",
                "Existing Holding",
                "Amount",
                "Funding Source",
                "Reason"
            ]

        ]



    # =================================================
    # Capital Summary
    # =================================================

    summary = pd.DataFrame(

        [

            {

                "Metric":
                    "Discretionary Spend Limit",

                "Amount":
                    DISCRETIONARY_SPEND_LIMIT

            },

            {

                "Metric":
                    "Capital Released From Sales",

                "Amount":
                    round(
                        released_capital,
                        2
                    )

            },

            {

                "Metric":
                    "Total Available Capital",

                "Amount":
                    round(
                        total_available_capital,
                        2
                    )

            },

            {

                "Metric":
                    "Capital Allocated",

                "Amount":
                    round(
                        capital_allocated,
                        2
                    )

            },

            {

                "Metric":
                    "Remaining Capital",

                "Amount":
                    round(
                        total_available_capital
                        -
                        capital_allocated,

                        2

                    )

            },

            {

                "Metric":
                    "BUY NEW Count",

                "Amount":
                    len(

                        allocation_df[

                            allocation_df["Action"]

                            ==

                            "BUY NEW"

                        ]

                    )

            },

            {

                "Metric":
                    "BUY MORE Count",

                "Amount":
                    len(

                        allocation_df[

                            allocation_df["Action"]

                            ==

                            "BUY MORE"

                        ]

                    )

            },

            {

                "Metric":
                    "REDUCE / SELL Count",

                "Amount":
                    len(

                        allocation_df[

                            allocation_df["Action"]

                            .isin(
                                [
                                    "REDUCE",
                                    "SELL"
                                ]
                            )

                        ]

                    )

            }

        ]

    )



    return {

        "Capital Allocation":
            allocation_df,

        "Capital Summary":
            summary

    }