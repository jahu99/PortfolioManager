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
    AVOID

Interface intentionally unchanged.
"""


import pandas as pd


from config.investment_config import (
    DISCRETIONARY_SPEND_LIMIT,
    MAX_POSITION_PERCENT
)



# =====================================================
# Helpers
# =====================================================

def safe_float(value, default=0.0):

    try:

        if pd.isna(value):
            return default

        return float(value)

    except Exception:

        return default



def normalise_ticker(value):

    return str(value).upper().strip()



def get_existing_holdings(portfolio_summary):

    """
    Returns set of existing portfolio tickers
    """

    if (
        isinstance(portfolio_summary, pd.DataFrame)
        and
        "Ticker" in portfolio_summary.columns
    ):

        return set(

            portfolio_summary["Ticker"]
            .astype(str)
            .str.upper()
            .tolist()

        )


    return set()



def get_current_value(
    ticker,
    portfolio_summary
):

    """
    Find holding value from portfolio summary
    """

    if (
        not isinstance(
            portfolio_summary,
            pd.DataFrame
        )
        or
        portfolio_summary.empty
    ):

        return 0



    if "Ticker" not in portfolio_summary.columns:

        return 0



    rows = portfolio_summary[
        portfolio_summary["Ticker"]
        .astype(str)
        .str.upper()
        ==
        ticker
    ]



    if rows.empty:

        return 0



    return safe_float(

        rows.iloc[0]
        .get(
            "Current Value",
            0
        )

    )



# =====================================================
# Main Engine
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



    # Allow list input from existing pipeline

    if isinstance(
        opportunities,
        list
    ):

        opportunities = pd.DataFrame(
            opportunities
        )



    if isinstance(
        portfolio_decisions,
        list
    ):

        portfolio_decisions = pd.DataFrame(
            portfolio_decisions
        )



    allocations = []



    existing_holdings = get_existing_holdings(
        portfolio_summary
    )



    released_capital = 0



    # =================================================
    # Existing portfolio decisions
    # =================================================


    if not portfolio_decisions.empty:


        for _, row in portfolio_decisions.iterrows():


            ticker = normalise_ticker(
                row.get(
                    "Ticker",
                    ""
                )
            )


            if not ticker:

                continue



            action = str(
                row.get(
                    "Action",
                    "HOLD"
                )
            ).upper()



            current_value = get_current_value(
                ticker,
                portfolio_summary
            )



            # Existing weak holdings

            if (
                action in [
                    "REDUCE",
                    "SELL"
                ]
                or
                (
                    ticker in existing_holdings
                    and
                    safe_float(
                        row.get(
                            "Investment Score",
                            100
                        )
                    )
                    < 60
                )
            ):


                reduce_amount = round(
                    current_value * 0.25,
                    2
                )


                released_capital += reduce_amount



                allocations.append(

                    {

                        "Ticker":
                            ticker,

                        "Action":
                            "SELL"
                            if action == "SELL"
                            else
                            "REDUCE",

                        "Existing Holding":
                            "Yes",

                        "Amount":
                            reduce_amount,

                        "Funding Source":
                            "Released Capital",

                        "Reason":
                            row.get(
                                "Reason",
                                "Weakening investment profile"
                            )

                    }

                )

                continue

                # =================================================
    # HOLD / BUY MORE existing holdings
    # =================================================

    buy_candidates = []


    if not portfolio_decisions.empty:

        for _, row in portfolio_decisions.iterrows():

            ticker = normalise_ticker(
                row.get(
                    "Ticker",
                    ""
                )
            )


            if not ticker:
                continue


            action = str(
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


            # Existing holdings only

            if ticker in existing_holdings:


                if action in [
                    "BUY",
                    "ADD",
                    "BUY MORE"
                ]:

                    buy_candidates.append(

                        {

                            "Ticker":
                                ticker,

                            "Action":
                                "BUY MORE",

                            "Existing Holding":
                                "Yes",

                            "Score":
                                score,

                            "Reason":
                                "Increase existing high conviction holding"

                        }

                    )


                elif action == "HOLD":


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
    # New opportunity candidates
    # =================================================


    if not opportunities.empty:


        for _, row in opportunities.iterrows():


            ticker = normalise_ticker(
                row.get(
                    "Ticker",
                    ""
                )
            )


            if not ticker:

                continue



            score = safe_float(
                row.get(
                    "Investment Score",
                    0
                )
            )



            # Existing holdings never become BUY NEW

            if ticker in existing_holdings:

                continue



            if score >= 75:


                buy_candidates.append(

                    {

                        "Ticker":
                            ticker,

                        "Action":
                            "BUY NEW",

                        "Existing Holding":
                            "No",

                        "Score":
                            score,

                        "Reason":
                            "High conviction opportunity"

                    }

                )


            else:


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
                            "Low conviction opportunity"

                    }

                )



    # =================================================
    # Allocate available capital
    # =================================================


    available_capital = (

        DISCRETIONARY_SPEND_LIMIT

        +

        released_capital

    )


    buy_candidates = sorted(

        buy_candidates,

        key=lambda x: x["Score"],

        reverse=True

    )



    # Maximum number of positions to fund

    max_new_allocations = min(

        len(buy_candidates),

        10

    )



    selected = buy_candidates[
        :max_new_allocations
    ]



    if selected:


        total_score = sum(

            x["Score"]

            for x in selected

        )


        for candidate in selected:


            allocation = round(

                available_capital

                *

                (
                    candidate["Score"]

                    /

                    total_score

                ),

                2

            )


            allocations.append(

                {

                    "Ticker":
                        candidate["Ticker"],

                    "Action":
                        candidate["Action"],

                    "Existing Holding":
                        candidate["Existing Holding"],

                    "Amount":
                        allocation,

                    "Funding Source":
                        "Discretionary Spend + Released Capital",

                    "Reason":
                        candidate["Reason"]

                }

            )



    # =================================================
    # Create Allocation dataframe
    # =================================================


    allocation_df = pd.DataFrame(
        allocations
    )



    if allocation_df.empty:


        allocation_df = pd.DataFrame(

            columns=[

                "Ticker",
                "Action",
                "Existing Holding",
                "Amount",
                "Funding Source",
                "Reason"

            ]

        )



    # =================================================
    # Capital Summary
    # =================================================


    allocated = allocation_df[

        allocation_df["Action"]

        .isin(
            [
                "BUY NEW",
                "BUY MORE"
            ]
        )

    ]["Amount"].sum()



    summary = pd.DataFrame(

        [

            {

                "Metric":
                    "Discretionary Spend Limit",

                "Value":
                    DISCRETIONARY_SPEND_LIMIT

            },

            {

                "Metric":
                    "Capital Released From Sales",

                "Value":
                    round(
                        released_capital,
                        2
                    )

            },

            {

                "Metric":
                    "Total Available Capital",

                "Value":
                    round(
                        available_capital,
                        2
                    )

            },

            {

                "Metric":
                    "Capital Allocated",

                "Value":
                    round(
                        allocated,
                        2
                    )

            },

            {

                "Metric":
                    "Remaining Capital",

                "Value":
                    round(

                        available_capital

                        -

                        allocated,

                        2

                    )

            },

            {

                "Metric":
                    "BUY NEW Count",

                "Value":
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

                "Value":
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

                "Value":
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