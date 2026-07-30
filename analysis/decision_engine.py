import pandas as pd



def generate_decisions(
    portfolio_summary,
    stock_results,
    rebalance_recommendations
):

    decisions = []



    # ---------------------------------
    # Review existing holdings
    # ---------------------------------

    if (
        portfolio_summary is not None
        and not portfolio_summary.empty
    ):


        for _, holding in portfolio_summary.iterrows():

            ticker = holding.get(
                "Ticker",
                ""
            )


            if pd.isna(ticker):

                ticker = ""



            score = holding.get(
                "Momentum Score",
                holding.get(
                    "Investment Score",
                    0
                )
            )


            signal = holding.get(
                "Momentum Signal",
                holding.get(
                    "Signal",
                    ""
                )
            )


            allocation = holding.get(
                "Allocation %",
                0
            )


            sector = holding.get(
                "Sector",
                "Unknown"
            )



            action = "HOLD"

            reasons = []



            # Weak signal

            if signal in [
                "SELL",
                "STRONG SELL"
            ]:

                action = "REVIEW"

                reasons.append(
                    "Weak technical signal"
                )



            # Low score

            if (
                score is not None
                and not pd.isna(score)
                and float(score) < 60
            ):

                action = "REVIEW"

                reasons.append(
                    "Low momentum score"
                )



            # Concentration

            if (
                allocation is not None
                and not pd.isna(allocation)
                and float(allocation) > 40
            ):

                action = "REVIEW"

                reasons.append(
                    "High portfolio concentration"
                )



            # Positive exception

            if not reasons:

                if allocation > 25:

                    reasons.append(
                        "Large position but high conviction"
                    )

                else:

                    reasons.append(
                        "Holding meets current criteria"
                    )



            decisions.append(
                {

                    "Action":
                        action,

                    "Ticker":
                        ticker,

                    "Sector":
                        sector,

                    "Investment Score":
                        score,

                    "Allocation %":
                        allocation,

                    "Reason":
                        "; ".join(
                            reasons
                        )

                }
            )



    # ---------------------------------
    # Add rebalance opportunities
    # ---------------------------------

    if (
        rebalance_recommendations is not None
        and not rebalance_recommendations.empty
    ):


        print(
            "\nREBALANCE INPUT TO DECISION ENGINE"
        )

        print(
            rebalance_recommendations.to_string()
        )



        for _, item in rebalance_recommendations.iterrows():


            ticker = item.get(
                "Ticker",
                ""
            )


            # Handle missing values

            if (
                ticker is None
                or pd.isna(ticker)
                or str(ticker).strip() == ""
            ):

                print(
                    "Skipping rebalance recommendation with blank ticker"
                )

                continue



            decisions.append(
                {

                    "Action":
                        item.get(
                            "Action",
                            ""
                        ),

                    "Ticker":
                        ticker,

                    "Sector":
                        item.get(
                            "Sector",
                            ""
                        ),

                    "Investment Score":
                        item.get(
                            "Investment Score",
                            None
                        ),

                    "Allocation %":
                        item.get(
                            "Allocation %",
                            None
                        ),

                    "Reason":
                        item.get(
                            "Reason",
                            ""
                        )

                }
            )



    # ---------------------------------
    # Create dataframe
    # ---------------------------------

    result = pd.DataFrame(
        decisions
    )



    if result.empty:

        return result


    # ---------------------------------
    # Remove invalid and duplicate tickers
    # ---------------------------------

    if "Ticker" in result.columns:

        # Remove blanks
        result = result[
            result["Ticker"].notna()
        ]

        result = result[
            result["Ticker"] != ""
        ]


        # Consolidate duplicate decisions
        # Most important action wins

        action_priority = {

            "REDUCE": 1,
            "SELL": 1,
            "REVIEW": 2,
            "ADD": 3,
            "BUY": 3,
            "HOLD": 4,
            "HOLD / ADD": 5

        }


        result["Decision Priority"] = (
            result["Action"]
            .map(action_priority)
            .fillna(99)
        )


        result = (
            result
            .sort_values(
                [
                    "Ticker",
                    "Decision Priority"
                ]
            )
            .drop_duplicates(
                subset=["Ticker"],
                keep="first"
            )
        )
    


    # ---------------------------------
    # Rank decisions
    # ---------------------------------

    action_order = {

        "REDUCE": 1,

        "SELL": 1,

        "REVIEW": 2,

        "ADD": 3,

        "HOLD": 4

    }



    result["Priority"] = (
        result["Action"]
        .map(action_order)
        .fillna(5)
    )



    result = result.sort_values(
        by=[
            "Priority",
            "Ticker"
        ]
    )

    result = result.drop(
        columns=[
            "Priority"
        ]
    )



    return result