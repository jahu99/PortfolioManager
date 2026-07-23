import pandas as pd
import os
from datetime import datetime



def create_executive_summary(
    writer,
    portfolio,
    stocks,
    health,
    decisions,
    sectors
):

    rows = []


    rows.append(
        [
            "STOCK MOMENTUM AGENT - EXECUTIVE SUMMARY"
        ]
    )


    rows.append(
        [
            "Generated",
            datetime.now().strftime(
                "%d %B %Y %H:%M"
            )
        ]
    )


    rows.append([])


    # -------------------------------
    # Portfolio Health
    # -------------------------------

    rows.append(
        [
            "PORTFOLIO HEALTH"
        ]
    )


    if not health.empty:

        health_row = health.iloc[0]


        rows.append(
            [
                "Health Score",
                health_row.get(
                    "Health Score",
                    ""
                )
            ]
        )


        rows.append(
            [
                "Rating",
                health_row.get(
                    "Rating",
                    ""
                )
            ]
        )


        risks = health_row.get(
            "Risks",
            ""
        )


        rows.append(
            [
                "Risks",
                risks
            ]
        )


    else:

        rows.append(
            [
                "No portfolio health data"
            ]
        )


    rows.append([])


    # -------------------------------
    # Top Opportunities
    # -------------------------------

    rows.append(
        [
            "TOP STOCK OPPORTUNITIES"
        ]
    )


    rows.append(
        [
            "Ticker",
            "Signal",
            "Investment Score"
        ]
    )


    if not stocks.empty:


        top = stocks.sort_values(
            by="Investment Score",
            ascending=False
        ).head(10)


        for _, row in top.iterrows():


            rows.append(
                [
                    row.get(
                        "Ticker",
                        ""
                    ),

                    row.get(
                        "Signal",
                        ""
                    ),

                    row.get(
                        "Investment Score",
                        ""
                    )
                ]
            )


    rows.append([])


    # -------------------------------
    # Investment Decisions
    # -------------------------------

    rows.append(
        [
            "PORTFOLIO ACTIONS"
        ]
    )


    rows.append(
        [
            "Action",
            "Ticker",
            "Reason"
        ]
    )


    if not decisions.empty:


        for _, row in decisions.head(10).iterrows():


            rows.append(
                [
                    row.get(
                        "Action",
                        ""
                    ),

                    row.get(
                        "Ticker",
                        ""
                    ),

                    row.get(
                        "Reason",
                        ""
                    )
                ]
            )


    rows.append([])


    # -------------------------------
    # Sector Positioning
    # -------------------------------

    rows.append(
        [
            "SECTOR POSITIONING"
        ]
    )


    if not sectors.empty:


        rows.append(
            [
                "Sector",
                "Current %",
                "Target %",
                "Action"
            ]
        )


        for _, row in sectors.iterrows():


            rows.append(
                [
                    row.get(
                        "Sector",
                        ""
                    ),

                    row.get(
                        "Current %",
                        ""
                    ),

                    row.get(
                        "Target %",
                        ""
                    ),

                    row.get(
                        "Action",
                        ""
                    )
                ]
            )


    pd.DataFrame(
        rows
    ).to_excel(
        writer,
        sheet_name="Executive Summary",
        index=False,
        header=False
    )



def create_user_guide(writer):


    guide = [

        [
            "STOCK MOMENTUM AGENT - USER GUIDE"
        ],

        [],

        [
            "DAILY WORKFLOW"
        ],

        [
            "Step 1",
            "Run python main.py"
        ],

        [
            "Step 2",
            "Review Executive Summary tab"
        ],

        [
            "Step 3",
            "Review Investment Decisions"
        ],

        [
            "Step 4",
            "Review Trade Plan recommendations"
        ],

        [],

        [
            "UNDERSTANDING SCORES"
        ],

        [
            "Investment Score",
            "Overall stock attractiveness"
        ],

        [
            "Technical Score",
            "Trend, momentum, RSI, MACD and volume"
        ],

        [
            "Quality Score",
            "Business fundamentals and financial strength"
        ],

        [],

        [
            "SIGNALS"
        ],

        [
            "STRONG BUY",
            "High conviction opportunity"
        ],

        [
            "BUY",
            "Potential investment candidate"
        ],

        [
            "WATCH",
            "Monitor for improvement"
        ],

        [
            "HOLD",
            "Maintain current position"
        ],

        [
            "SELL",
            "Review position"
        ]

    ]


    pd.DataFrame(
        guide
    ).to_excel(
        writer,
        sheet_name="How To Use",
        index=False,
        header=False
    )



def create_report(
    stock_results,
    portfolio_results,
    alerts,
    sector_results,
    portfolio_actions=None,
    portfolio_optimisation=None,
    rebalance_recommendations=None,
    portfolio_health=None,
    decisions=None,
    trade_plan=None,
    performance_summary=None
):
        # ---------------------------------
    # File location
    # ---------------------------------

    report_folder = os.path.dirname(__file__)


    filename = (
        f"daily_report_"
        f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    )


    filepath = os.path.join(
        report_folder,
        filename
    )


    # ---------------------------------
    # Convert inputs
    # ---------------------------------

    stocks = (
    stock_results
    if isinstance(
        stock_results,
        pd.DataFrame
    )
    else pd.DataFrame(
        stock_results
    )
)


    portfolio = (
        portfolio_results
        if isinstance(
            portfolio_results,
            pd.DataFrame
        )
        else pd.DataFrame(
            portfolio_results
        )
    )


    sectors = (
        sector_results
        if isinstance(
            sector_results,
            pd.DataFrame
        )
        else pd.DataFrame(
            sector_results
        )
    )

       

    alerts_df = (
        alerts
        if isinstance(
            alerts,
            pd.DataFrame
        )
        else pd.DataFrame(
            alerts
        )
    )


    actions = (
        portfolio_actions
        if isinstance(
            portfolio_actions,
            pd.DataFrame
        )
        else pd.DataFrame(
            portfolio_actions
        )
    )


    optimisation = (
        portfolio_optimisation
        if isinstance(
            portfolio_optimisation,
            pd.DataFrame
        )
        else pd.DataFrame(
            portfolio_optimisation
        )
    )


    rebalance = (
        rebalance_recommendations
        if isinstance(
            rebalance_recommendations,
            pd.DataFrame
        )
        else pd.DataFrame(
            rebalance_recommendations
        )
    )


    if portfolio_health is None:

        health = pd.DataFrame()

    else:

        health = pd.DataFrame(
            [
                portfolio_health
            ]
        )


    decisions_df = (
        decisions
        if isinstance(
            decisions,
            pd.DataFrame
        )
        else pd.DataFrame(
            decisions
        )
    )



    trade_plan_df = (
        trade_plan
        if isinstance(
            trade_plan,
            pd.DataFrame
        )
        else pd.DataFrame(
            trade_plan
        )
    )

    performance_df = (
        performance_summary
        if isinstance(
            performance_summary,
            pd.DataFrame
        )
        else pd.DataFrame(
            performance_summary
        )
    )
       


    print(
        "CREATING REPORT:"
    )


    print(
        "Stocks:",
        len(stocks)
    )


    print(
        "Portfolio:",
        len(portfolio)
    )


    print(
        "Sectors:",
        len(sectors)
    )


    print(
        "Alerts:",
        len(alerts_df)
    )



    with pd.ExcelWriter(
        filepath,
        engine="openpyxl"
    ) as writer:



        # ---------------------------------
        # Executive Summary
        # ---------------------------------

        print(
            "Creating Executive Summary tab"
        )


        create_executive_summary(
            writer,
            portfolio,
            stocks,
            health,
            decisions_df,
            optimisation
        )



        # ---------------------------------
        # How To Use
        # ---------------------------------

        print(
            "Creating How To Use tab"
        )


        create_user_guide(
            writer
        )



        # ---------------------------------
        # Stock Rankings
        # ---------------------------------

        print(
            "Creating Stock Rankings tab"
        )


        if stocks.empty:

            pd.DataFrame(
                {
                    "Message":
                    [
                        "No stock results"
                    ]
                }
            ).to_excel(
                writer,
                sheet_name="Stock Rankings",
                index=False
            )

        else:

            stocks.sort_values(
                by="Investment Score",
                ascending=False
            ).to_excel(
                writer,
                sheet_name="Stock Rankings",
                index=False
            )



        # ---------------------------------
        # Portfolio
        # ---------------------------------

        print(
            "Creating Portfolio tab"
        )


        if portfolio.empty:

            pd.DataFrame(
                {
                    "Message":
                    [
                        "No portfolio data"
                    ]
                }
            ).to_excel(
                writer,
                sheet_name="Portfolio",
                index=False
            )

        else:

            portfolio.to_excel(
                writer,
                sheet_name="Portfolio",
                index=False
            )



        # ---------------------------------
        # Portfolio Actions
        # ---------------------------------

        print(
            "Creating Portfolio Actions tab"
        )


        if actions.empty:

            pd.DataFrame(
                {
                    "Message":
                    [
                        "No portfolio actions"
                    ]
                }
            ).to_excel(
                writer,
                sheet_name="Portfolio Actions",
                index=False
            )

        else:

            actions.to_excel(
                writer,
                sheet_name="Portfolio Actions",
                index=False
            )

                    # ---------------------------------
        # Portfolio Optimisation
        # ---------------------------------

        print(
            "Creating Portfolio Optimisation tab"
        )


        if optimisation.empty:

            pd.DataFrame(
                {
                    "Message":
                    [
                        "No optimisation data"
                    ]
                }
            ).to_excel(
                writer,
                sheet_name="Portfolio Optimisation",
                index=False
            )

        else:

            optimisation.to_excel(
                writer,
                sheet_name="Portfolio Optimisation",
                index=False
            )



        # ---------------------------------
        # Rebalance Recommendations
        # ---------------------------------

        print(
            "Creating Rebalance Recommendations tab"
        )


        if rebalance.empty:

            pd.DataFrame(
                {
                    "Message":
                    [
                        "No rebalance recommendations"
                    ]
                }
            ).to_excel(
                writer,
                sheet_name="Rebalance Recommendations",
                index=False
            )

        else:

            rebalance.to_excel(
                writer,
                sheet_name="Rebalance Recommendations",
                index=False
            )



        # ---------------------------------
        # Sector Analysis
        # ---------------------------------

        print(
            "Creating Sector Analysis tab"
        )


        if sectors.empty:

            pd.DataFrame(
                {
                    "Message":
                    [
                        "No sector data"
                    ]
                }
            ).to_excel(
                writer,
                sheet_name="Sector Analysis",
                index=False
            )

        else:

            sectors.to_excel(
                writer,
                sheet_name="Sector Analysis",
                index=False
            )



        # ---------------------------------
        # Portfolio Health
        # ---------------------------------

        print(
            "Creating Portfolio Health tab"
        )


        if health.empty:

            pd.DataFrame(
                {
                    "Message":
                    [
                        "No portfolio health data"
                    ]
                }
            ).to_excel(
                writer,
                sheet_name="Portfolio Health",
                index=False
            )

        else:

            health.to_excel(
                writer,
                sheet_name="Portfolio Health",
                index=False
            )



        # ---------------------------------
        # Investment Decisions
        # ---------------------------------

        print(
            "Creating Investment Decisions tab"
        )


        if decisions_df.empty:

            pd.DataFrame(
                {
                    "Message":
                    [
                        "No investment decisions"
                    ]
                }
            ).to_excel(
                writer,
                sheet_name="Investment Decisions",
                index=False
            )

        else:

            decisions_df.to_excel(
                writer,
                sheet_name="Investment Decisions",
                index=False
            )



        # ---------------------------------
        # Trade Plan
        # ---------------------------------

        print(
            "Creating Trade Plan tab"
        )


        if trade_plan_df.empty:

            pd.DataFrame(
                {
                    "Message":
                    [
                        "No trade plan"
                    ]
                }
            ).to_excel(
                writer,
                sheet_name="Trade Plan",
                index=False
            )

        else:

            trade_plan_df.to_excel(
                writer,
                sheet_name="Trade Plan",
                index=False
            )


        # ---------------------------------
        # Recommendation Performance
        # ---------------------------------

        print(
            "Creating Recommendation Performance tab"
        )


        if performance_df.empty:

            pd.DataFrame(
                {
                    "Message":
                    [
                        "No recommendation performance data"
                    ]
                }
            ).to_excel(
                writer,
                sheet_name="Recommendation Performance",
                index=False
            )

        else:

            performance_df.to_excel(
                writer,
                sheet_name="Recommendation Performance",
                index=False
            )
        # ---------------------------------
        # Alerts
        # ---------------------------------

        print(
            "Creating Alerts tab"
        )


        if alerts_df.empty:

            pd.DataFrame(
                {
                    "Message":
                    [
                        "No alerts generated"
                    ]
                }
            ).to_excel(
                writer,
                sheet_name="Alerts",
                index=False
            )

        else:

            alerts_df.to_excel(
                writer,
                sheet_name="Alerts",
                index=False
            )



    print(
        f"\nReport created: {filepath}"
    )


    return filepath