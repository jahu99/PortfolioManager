import pandas as pd
import os
from datetime import datetime



def create_report(
    results,
    portfolio_summary,
    alerts,
    sector_summary,
    portfolio_actions,
    portfolio_optimisation,
    rebalance_recommendations,
    portfolio_health,
    decisions,
    trade_plan,
    performance_summary=None,
    signal_performance=None,
    horizon_performance=None,
    score_performance=None
):


    # -------------------------------
    # Safety handling
    # -------------------------------

    if results is None:
        results = []

    if portfolio_summary is None:
        portfolio_summary = pd.DataFrame()

    if alerts is None:
        alerts = pd.DataFrame()

    if sector_summary is None:
        sector_summary = pd.DataFrame()

    if portfolio_actions is None:
        portfolio_actions = pd.DataFrame()

    if portfolio_optimisation is None:
        portfolio_optimisation = pd.DataFrame()

    if rebalance_recommendations is None:
        rebalance_recommendations = pd.DataFrame()

    if decisions is None:
        decisions = pd.DataFrame()

    if trade_plan is None:
        trade_plan = pd.DataFrame()

    if performance_summary is None:
        performance_summary = pd.DataFrame()

    if signal_performance is None:
        signal_performance = pd.DataFrame()

    if horizon_performance is None:
        horizon_performance = pd.DataFrame()

    if score_performance is None:
        score_performance = pd.DataFrame()



    # -------------------------------
    # Create filename
    # -------------------------------

    report_path = (
        "/Users/jameshulin/Documents/"
        "stock-momentum-agent/reports/"
    )


    filename = os.path.join(
        report_path,
        f"daily_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    )


    print("CREATING REPORT:")
    print(f"Stocks: {len(results)}")
    print(f"Portfolio: {len(portfolio_summary)}")
    print(f"Sectors: {len(sector_summary)}")
    print(f"Alerts: {len(alerts)}")



    with pd.ExcelWriter(
        filename,
        engine="openpyxl"
    ) as writer:



        # -------------------------------
        # Executive Summary
        # -------------------------------

        print(
            "Creating Executive Summary tab"
        )


        pd.DataFrame(
            {
                "Metric": [
                    "Stocks Scanned",
                    "Portfolio Holdings",
                    "Alerts"
                ],

                "Value": [
                    len(results),
                    len(portfolio_summary),
                    len(alerts)
                ]
            }

        ).to_excel(
            writer,
            sheet_name="Executive Summary",
            index=False
        )



        # -------------------------------
        # How To Use
        # -------------------------------

        print(
            "Creating How To Use tab"
        )


        pd.DataFrame(
            {
                "Instructions": [

                    "Stock Rankings shows opportunities",

                    "Portfolio shows holdings",

                    "Investment Decisions shows recommended actions",

                    "Recommendation Performance shows historical accuracy"

                ]
            }

        ).to_excel(
            writer,
            sheet_name="How To Use",
            index=False
        )



        # -------------------------------
        # Main Data Tabs
        # -------------------------------

        print("Creating Stock Rankings tab")

        pd.DataFrame(results).to_excel(
            writer,
            sheet_name="Stock Rankings",
            index=False
        )


        print("Creating Portfolio tab")

        portfolio_summary.to_excel(
            writer,
            sheet_name="Portfolio",
            index=False
        )


        print("Creating Portfolio Actions tab")

        portfolio_actions.to_excel(
            writer,
            sheet_name="Portfolio Actions",
            index=False
        )


        print("Creating Portfolio Optimisation tab")

        portfolio_optimisation.to_excel(
            writer,
            sheet_name="Portfolio Optimisation",
            index=False
        )


        print("Creating Rebalance Recommendations tab")

        rebalance_recommendations.to_excel(
            writer,
            sheet_name="Rebalance Recommendations",
            index=False
        )


        print("Creating Sector Analysis tab")

        sector_summary.to_excel(
            writer,
            sheet_name="Sector Analysis",
            index=False
        )



        print("Creating Portfolio Health tab")

        pd.DataFrame(
            [portfolio_health]
        ).to_excel(
            writer,
            sheet_name="Portfolio Health",
            index=False
        )



        print("Creating Investment Decisions tab")

        decisions.to_excel(
            writer,
            sheet_name="Investment Decisions",
            index=False
        )



        print("Creating Trade Plan tab")

        trade_plan.to_excel(
            writer,
            sheet_name="Trade Plan",
            index=False
        )



        # -------------------------------
        # Performance
        # -------------------------------

        print(
            "Creating Recommendation Performance tab"
        )


        performance_summary.to_excel(
            writer,
            sheet_name="Recommendation Performance",
            index=False
        )



        # -------------------------------
        # Intelligence
        # -------------------------------

        print(
            "Creating Recommendation Intelligence tab"
        )


        row = 0


        intelligence = [
            (
                "Signal Performance",
                signal_performance
            ),

            (
                "Horizon Performance",
                horizon_performance
            ),

            (
                "Score Performance",
                score_performance
            )
        ]



        for title, dataframe in intelligence:


            if dataframe.empty:

                continue


            pd.DataFrame(
                [title]
            ).to_excel(
                writer,
                sheet_name="Recommendation Intelligence",
                startrow=row,
                index=False,
                header=False
            )


            row += 1


            dataframe.to_excel(
                writer,
                sheet_name="Recommendation Intelligence",
                startrow=row,
                index=False
            )


            row += len(dataframe) + 3



        # -------------------------------
        # Alerts
        # -------------------------------

        print(
            "Creating Alerts tab"
        )


        alerts.to_excel(
            writer,
            sheet_name="Alerts",
            index=False
        )



    print(
        f"\nReport created: {filename}"
    )


    return filename