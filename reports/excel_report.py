import pandas as pd
import os
from datetime import datetime
from openpyxl import load_workbook


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
    score_performance=None,
    score_bucket_performance=None,
    component_score_performance=None,
    signal_horizon_performance=None,
    recommendation_intelligence=None,
    portfolio_ai_review=None,
    portfolio_manager_review=None, 
    growth_plan=None,
    final_portfolio_decisions=None,
    recommendation_learning=None
):

    print("STARTING REPORT CREATION")

    # --------------------------------
    # Safety handling
    # --------------------------------

    if results is None:
        results = []


    dataframes = {

        "portfolio_summary": portfolio_summary,
        "alerts": alerts,
        "sector_summary": sector_summary,
        "portfolio_actions": portfolio_actions,
        "portfolio_optimisation": portfolio_optimisation,
        "rebalance_recommendations": rebalance_recommendations,
        "decisions": decisions,
        "trade_plan": trade_plan,

        "performance_summary": performance_summary,
        "signal_performance": signal_performance,
        "horizon_performance": horizon_performance,
        "score_performance": score_performance,
        "score_bucket_performance": score_bucket_performance,
        "component_score_performance": component_score_performance,
        "signal_horizon_performance": signal_horizon_performance,

        "recommendation_intelligence": recommendation_intelligence,
        "portfolio_ai_review": portfolio_ai_review,
        "portfolio_manager_review": portfolio_manager_review,
        "final_portfolio_decisions": final_portfolio_decisions,
        "recommendation_learning": recommendation_learning


    }


    for key, value in dataframes.items():

        if value is None:
            dataframes[key] = pd.DataFrame()



    portfolio_summary = dataframes["portfolio_summary"]
    alerts = dataframes["alerts"]
    sector_summary = dataframes["sector_summary"]
    portfolio_actions = dataframes["portfolio_actions"]
    portfolio_optimisation = dataframes["portfolio_optimisation"]
    rebalance_recommendations = dataframes["rebalance_recommendations"]
    decisions = dataframes["decisions"]
    trade_plan = dataframes["trade_plan"]

    performance_summary = dataframes["performance_summary"]
    final_portfolio_decisions = dataframes["final_portfolio_decisions"]

    signal_performance = dataframes["signal_performance"]
    horizon_performance = dataframes["horizon_performance"]
    score_performance = dataframes["score_performance"]
    score_bucket_performance = dataframes["score_bucket_performance"]
    component_score_performance = dataframes["component_score_performance"]
    signal_horizon_performance = dataframes["signal_horizon_performance"]
    
    recommendation_intelligence = dataframes["recommendation_intelligence"]
    portfolio_ai_review = dataframes["portfolio_ai_review"]


    print(
        "RECOMMENDATION INTELLIGENCE SHAPE:",
        recommendation_intelligence.shape
    )

    print(
        "ALERTS SHAPE:",
        alerts.shape
    )



    # --------------------------------
    # Filename
    # --------------------------------

    report_path = (
        "/Users/jameshulin/Documents/"
        "stock-momentum-agent/reports/"
    )


    os.makedirs(
        report_path,
        exist_ok=True
    )


    filename = os.path.join(
        report_path,
        f"daily_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    )



    print("CREATING REPORT")

    print(
        "Stocks:",
        len(results)
    )

    print(
        "Portfolio:",
        len(portfolio_summary)
    )

    print(
        "Alerts:",
        len(alerts)
    )



    with pd.ExcelWriter(
        filename,
        engine="openpyxl"
    ) as writer:


        # =================================
        # Executive Summary
        # =================================

        print(
            "Creating Executive Summary"
        )


        summary_rows = [

            [
                "STOCK MOMENTUM AGENT - EXECUTIVE SUMMARY"
            ],

            [
                "Generated",
                datetime.now().strftime(
                    "%d %B %Y %H:%M"
                )
            ],

            [],

            [
                "PORTFOLIO OVERVIEW"
            ],

            [
                "Metric",
                "Value"
            ],

            [
                "Stocks Scanned",
                len(results)
            ],

            [
                "Portfolio Holdings",
                len(portfolio_summary)
            ],

            [
                "Alerts",
                len(alerts)
            ],

            [],

            [
                "PORTFOLIO HEALTH"
            ]

        ]


        # -------------------------------
        # Portfolio Health
        # -------------------------------

        if isinstance(portfolio_health, dict):

            summary_rows.extend([

                [
                    "Health Score",
                    portfolio_health.get(
                        "Health Score",
                        ""
                    )
                ],

                [
                    "Rating",
                    portfolio_health.get(
                        "Rating",
                        ""
                    )
                ]

            ])


        # -------------------------------
        # Portfolio Manager Intelligence
        # -------------------------------

        if isinstance(
            portfolio_manager_review,
            dict
        ):

            summary_rows.extend([

                [],

                [
                    "AI PORTFOLIO MANAGER VIEW"
                ],

                [
                    "Market View",
                    portfolio_manager_review.get(
                        "Market View",
                        ""
                    )
                ],

                [
                    "Portfolio Status",
                    portfolio_manager_review.get(
                        "Portfolio Status",
                        ""
                    )
                ],

                [
                    "AI Summary",
                    portfolio_manager_review.get(
                        "AI Summary",
                        ""
                    )
                ]

            ])


            summary_rows.append([])


            summary_rows.append(
                [
                    "KEY STRENGTHS"
                ]
            )


            for item in portfolio_manager_review.get(
                "Key Strengths",
                []
            ):

                summary_rows.append(
                    [
                        item
                    ]
                )


            summary_rows.append([])


            summary_rows.append(
                [
                    "KEY RISKS"
                ]
            )


            for item in portfolio_manager_review.get(
                "Key Risks",
                []
            ):

                summary_rows.append(
                    [
                        item
                    ]
                )


            summary_rows.append([])


            summary_rows.append(
                [
                    "PRIORITY ACTIONS"
                ]
            )


            for item in portfolio_manager_review.get(
                "Priority Actions",
                []
            ):

                summary_rows.append(
                    [
                        item
                    ]
                )


        # -------------------------------
        # Top Opportunities
        # -------------------------------

        summary_rows.extend([

            [],

            [
                "TOP OPPORTUNITIES"
            ],

            [
                "Ticker",
                "Signal",
                "Investment Score"
            ]

        ])


        if len(results) > 0:

            opportunities = (
                pd.DataFrame(results)
                .sort_values(
                    "Investment Score",
                    ascending=False
                )
                .head(5)
            )


            for _, stock in opportunities.iterrows():

                summary_rows.append(
                    [

                        stock.get(
                            "Ticker",
                            ""
                        ),

                        stock.get(
                            "Signal",
                            ""
                        ),

                        stock.get(
                            "Investment Score",
                            ""
                        )

                    ]
                )



        pd.DataFrame(
            summary_rows
        ).to_excel(
            writer,
            sheet_name="Executive Summary",
            index=False,
            header=False
        )


        # =================================
        # How To Use
        # =================================

        print(
            "Creating How To Use"
        )


        pd.DataFrame(
            {
                "Instructions":[

                    "Executive Summary provides portfolio overview",

                    "Stock Rankings shows investment opportunities",

                    "Portfolio Actions shows recommended changes",

                    "Recommendation Intelligence measures historical recommendation quality"

                ]
            }

        ).to_excel(
            writer,
            sheet_name="How To Use",
            index=False
        )

        # =================================
        # Main Data Tabs
        # =================================


        print(
            "Creating Stock Rankings"
        )


        pd.DataFrame(
            results
        ).to_excel(
            writer,
            sheet_name="Stock Rankings",
            index=False
        )



        print(
            "Creating Portfolio"
        )


        portfolio_summary.to_excel(
            writer,
            sheet_name="Portfolio",
            index=False
        )



        print(
            "Creating Portfolio Actions"
        )


        portfolio_actions.to_excel(
            writer,
            sheet_name="Portfolio Actions",
            index=False
        )



        print(
            "Creating Portfolio Optimisation"
        )


        portfolio_optimisation.to_excel(
            writer,
            sheet_name="Portfolio Optimisation",
            index=False
        )



        print(
            "Creating Rebalance Recommendations"
        )


        rebalance_recommendations.to_excel(
            writer,
            sheet_name="Rebalance Recommendations",
            index=False
        )



        print(
            "Creating Sector Analysis"
        )


        sector_summary.to_excel(
            writer,
            sheet_name="Sector Analysis",
            index=False
        )



        print(
            "Creating Portfolio Health"
        )


        pd.DataFrame(
            [portfolio_health]
        ).to_excel(
            writer,
            sheet_name="Portfolio Health",
            index=False
        )


        print(
            "Creating Final Portfolio Decisions"
        )


        final_portfolio_decisions.to_excel(
            writer,
            sheet_name="Final Portfolio Decisions",
            index=False
        )


        print(
            "Creating Investment Decisions"
        )



        decisions.to_excel(
            writer,
            sheet_name="Investment Decisions",
            index=False
        )



        print(
            "Creating Trade Plan"
        )


        trade_plan.to_excel(
            writer,
            sheet_name="Trade Plan",
            index=False
        )

        print("Creating Portfolio Growth Plan")

        growth_plan_df = pd.DataFrame(growth_plan)

        growth_plan_df.to_excel(
            writer,
            sheet_name="Portfolio Growth Plan",
            index=False
        )

        print(
            "Creating AI Portfolio Review"
        )

        print(
            "AI REVIEW TYPE:",
        type(portfolio_ai_review)
        )

        print(
            "AI REVIEW VALUE:",
            portfolio_ai_review
        )
        

        print(
            "Creating AI Portfolio Review"
        )



        if isinstance(
            portfolio_ai_review,
            list
        ):

            portfolio_ai_review = pd.DataFrame(
                portfolio_ai_review
            )


        if not portfolio_ai_review.empty:

            portfolio_ai_review.to_excel(
                writer,
                sheet_name="AI Portfolio Review",
                index=False
            )

        else:

            pd.DataFrame(
                {
                    "Status": [
                        "No AI portfolio review available"
                    ]
                }

            ).to_excel(
                writer,
                sheet_name="AI Portfolio Review",
                index=False
            )

        print(
            "Creating AI Portfolio Manager"
        )


        if isinstance(
            portfolio_manager_review,
            dict
        ):

            pd.DataFrame(
                [
                    portfolio_manager_review
                ]

            ).to_excel(
                writer,
                sheet_name="AI Portfolio Manager",
                index=False
            )

        else:

            pd.DataFrame(
                {
                    "Status": [
                        "No portfolio manager review available"
                    ]
                }

            ).to_excel(
                writer,
                sheet_name="AI Portfolio Manager",
                index=False
            )
            

        # =================================
        # Recommendation Performance
        # =================================


        print(
            "Creating Recommendation Performance"
        )

        # =================================
        # Recommendation Learning
        # =================================

        print(
            "Creating Recommendation Learning"
        )


        if isinstance(
            recommendation_learning,
            dict
        ):

            learning_df = pd.DataFrame(
                [
                    recommendation_learning
                ]
            )

        else:

            learning_df = pd.DataFrame(
                {
                    "Status":
                    [
                        "No recommendation learning available"
                    ]
                }
            )


        learning_df.to_excel(
            writer,
            sheet_name="Recommendation Learning",
            index=False
        )


        performance_summary.to_excel(
            writer,
            sheet_name="Recommendation Performance",
            index=False
        )



        # =================================
        # Recommendation Intelligence
        # =================================


        print(
            "Creating Recommendation Intelligence"
        )


        intelligence_sheet = (
            "Recommendation Intelligence"
        )


        # Force sheet creation even if some sections are empty

        pd.DataFrame(
            {
                "Status": [
                    "Recommendation Intelligence Report"
                ]
            }

        ).to_excel(
            writer,
            sheet_name=intelligence_sheet,
            index=False
        )



        row = 2



        intelligence_sections = [

            (
                "Signal Performance",
                signal_performance
            ),

            (
                "Horizon Performance",
                horizon_performance
            ),

            (
                "Recommendation Intelligence",
                recommendation_intelligence
            ),

            (
                "Score Performance",
                score_performance
            ),

            (
                "Score Bucket Performance",
                score_bucket_performance
            ),

            (
                "Component Score Performance",
                component_score_performance
            ),

            (
                "Signal Horizon Performance",
                signal_horizon_performance
            )

        ]



        for title, dataframe in intelligence_sections:


            if dataframe is None:
                continue


            if dataframe.empty:
                continue



            pd.DataFrame(
                [
                    [
                        title
                    ]
                ]

            ).to_excel(
                writer,
                sheet_name=intelligence_sheet,
                startrow=row,
                index=False,
                header=False
            )


            row += 1



            dataframe.to_excel(
                writer,
                sheet_name=intelligence_sheet,
                startrow=row,
                index=False
            )


            row += len(dataframe) + 4

        # =================================
        # Alerts
        # =================================


        print(
            "ALERTS SHAPE:",
            alerts.shape
        )


        print(
            "ALERTS EMPTY:",
            alerts.empty
        )


        print(
            "Creating Alerts"
        )


        alerts.to_excel(
            writer,
            sheet_name="Alerts",
            index=False
        )



    # =================================
    # Workbook verification
    # =================================

    print(
        "Report created:",
        filename
    )


    # Verify sheets actually exist

    try:

        from openpyxl import load_workbook


        workbook = load_workbook(
            filename,
            read_only=True
        )


        print(
            "FINAL WORKBOOK SHEETS:",
            workbook.sheetnames
        )


        workbook.close()


    except Exception as e:

        print(
            "Workbook verification failed:",
            e
        )



    return filename

