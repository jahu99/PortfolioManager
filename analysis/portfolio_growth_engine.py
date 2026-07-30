import pandas as pd


def generate_growth_plan(
    results,
    portfolio_value,
    current_holdings=None,
    risk_profile="balanced"
):
    """
    Generates an AI portfolio growth plan.

    Purpose:
    Convert stock intelligence into wealth-building actions.

    Inputs:
        results:
            Stock analysis results from scanner

        portfolio_value:
            Current investable portfolio value

        current_holdings:
            Existing portfolio holdings

        risk_profile:
            conservative / balanced / aggressive

    Output:
        DataFrame containing growth recommendations
    """


    if results is None or len(results) == 0:
        return pd.DataFrame()


    if current_holdings is None:
        current_holdings = []


    holdings = set()

    for holding in current_holdings:

        if isinstance(holding, dict):

            holdings.add(
                holding.get("Ticker")
            )



    recommendations = []


    # ---------------------------------
    # Growth stages
    # ---------------------------------

    if portfolio_value < 10000:

        stage = "Foundation"

        starter_allocation = 0.02


    elif portfolio_value < 50000:

        stage = "Growth"

        starter_allocation = 0.03


    elif portfolio_value < 250000:

        stage = "Expansion"

        starter_allocation = 0.04


    else:

        stage = "Compounding"

        starter_allocation = 0.05



    # ---------------------------------
    # Risk profile adjustment
    # ---------------------------------

    if risk_profile == "conservative":

        max_position = 0.05

    elif risk_profile == "aggressive":

        max_position = 0.10

    else:

        max_position = 0.075



    # ---------------------------------
    # Select candidates
    # ---------------------------------

    candidates = []


    for stock in results:


        ticker = stock.get(
            "Ticker"
        )


        if ticker in holdings:
            continue



        investment_score = stock.get(
            "Investment Score",
            0
        )


        quality_score = stock.get(
            "Quality Score",
            0
        )


        signal = stock.get(
            "Signal",
            ""
        )


        if investment_score < 75:
            continue


        if signal not in [
            "BUY",
            "STRONG BUY"
        ]:
            continue


        candidates.append(stock)



    candidates = sorted(
        candidates,
        key=lambda x:
            x.get(
                "Investment Score",
                0
            ),
        reverse=True
    )



    # ---------------------------------
    # Create recommendations
    # ---------------------------------

    rank = 1


    for stock in candidates[:20]:


        investment_score = stock.get(
            "Investment Score",
            0
        )


        quality_score = stock.get(
            "Quality Score",
            0
        )


        # confidence calculation

        if (
            investment_score >= 85
            and quality_score >= 70
        ):

            confidence = "High"


        elif investment_score >= 75:

            confidence = "Medium"


        else:

            confidence = "Low"



        allocation_percent = min(
            starter_allocation,
            max_position
        )


        allocation_value = (
            portfolio_value *
            allocation_percent
        )



        recommendations.append(

            {

                "Priority":
                    rank,


                "Ticker":
                    stock.get(
                        "Ticker"
                    ),


                "Sector":
                    stock.get(
                        "Sector",
                        ""
                    ),


                "Growth Stage":
                    stage,


                "Action":
                    "START POSITION",


                "Investment Score":
                    investment_score,


                "Quality Score":
                    quality_score,


                "Confidence":
                    confidence,


                "Allocation %":
                    round(
                        allocation_percent * 100,
                        2
                    ),


                "Suggested Investment":
                    round(
                        allocation_value,
                        2
                    ),


                "Scaling Rule":
                    (
                        "Increase position if "
                        "score remains above 85 "
                        "and trend remains positive"
                    ),


                "Exit Rule":
                    (
                        "Reduce if investment score "
                        "falls below 60 or trend breaks"
                    )

            }

        )


        rank += 1



    return pd.DataFrame(
        recommendations
    )



# --------------------------------------------------
# Position scaling engine
# --------------------------------------------------


def evaluate_position_scaling(
    holding
):
    """
    Determines whether an existing position
    should increase, hold or reduce.
    """


    score = holding.get(
        "Investment Score",
        0
    )


    quality = holding.get(
        "Quality Score",
        0
    )


    allocation = holding.get(
        "Allocation %",
        0
    )



    if (
        score >= 85
        and quality >= 70
        and allocation < 10
    ):

        return {

            "Action":
                "INCREASE",

            "Reason":
                "High conviction underweight position"

        }



    if allocation > 25:

        return {

            "Action":
                "REDUCE",

            "Reason":
                "Position concentration exceeds target"

        }



    if score < 60:

        return {

            "Action":
                "REDUCE",

            "Reason":
                "Investment quality deteriorating"

        }



    return {

        "Action":
            "HOLD",

        "Reason":
            "Position remains within strategy"

    }