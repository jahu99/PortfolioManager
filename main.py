import pandas as pd
import traceback

from data.fundamentals import get_fundamentals

from data.database import (
    initialise_database,
    get_open_recommendations,
    save_recommendations,
    save_recommendation_evaluations,
    get_evaluation_history,
)


from data.database_queries import (
    get_performance_summary,
    get_signal_performance,
    get_horizon_performance,
    get_score_performance,
    get_signal_horizon_performance,
    get_score_horizon_performance,
    get_score_bucket_performance,
    get_component_score_performance,
    get_learning_history
)


from analysis.scorer import score_stock
from analysis.quality import score_quality
from analysis.signals import generate_signal
from analysis.recommendations import generate_recommendation


from analysis.rebalance import generate_rebalance_recommendations
from analysis.portfolio_health import calculate_portfolio_health
from analysis.decision_engine import generate_decisions
from analysis.trade_sizing import generate_trade_plan


from analysis.portfolio_recommendations import (
    generate_portfolio_recommendations
)


from analysis.portfolio_analysis import analyse_portfolio
from analysis.sector_analysis import analyse_sectors
from analysis.portfolio_optimizer import optimise_portfolio
from analysis.alerts import generate_alerts


from portfolio.portfolio import get_portfolio
from portfolio.targets import get_targets


from reports.excel_report import create_report


from analysis.outcome_tracker import calculate_evaluations


from analysis.growth import score_growth

from analysis.recommendation_intelligence import (
    generate_recommendation_intelligence
)

from analysis.factor_performance import (
    calculate_factor_performance
)

from analysis.ai_recommendation import (
    generate_ai_recommendation
)

from analysis.ai_decision_engine import (
    generate_ai_decision
)


from analysis.portfolio_ai import (
    generate_portfolio_review
)

from analysis.portfolio_decision_engine import (
    generate_portfolio_decisions
)

from analysis.portfolio_manager import (
    generate_portfolio_manager_review
)

from agents.orchestrator import run_ai_agents

from analysis.portfolio_growth_engine import (
    generate_growth_plan
)

from analysis.portfolio_context import evaluate_portfolio_context

from analysis.recommendation_learning import (
    calculate_recommendation_learning
)

from analysis.score_calibration import get_calibrated_weights

from analysis.portfolio_enrichment import (
    enrich_portfolio_holdings
)

from data.universe import get_market_universe

from analysis.universe_filter import filter_investable_universe

from analysis.scanner import run_market_scan

from analysis.capital_allocator import (
    generate_capital_allocation
)

from analysis.stock_analyser import analyse_stock

from analysis.weight_optimizer import run_weight_optimizer

from analysis.investment_score import (
    calculate_investment_score
)

from analysis.final_portfolio_decision import (
    generate_final_portfolio_decisions,
)

from analysis.entry_quality import assess_entry_quality

from analysis.market_intelligence import (
    assess_market_intelligence,
)

from analysis.portfolio_recalibration import (
    generate_portfolio_reallocation
)

from analysis.candidate_ranking_snapshot import (

    save_candidate_ranking_snapshot,

    save_buy_new_pipeline_snapshot,

)

from analysis.candidate_selection import (
    select_buy_new_candidates,
)

from analysis.valuation import (
    assess_valuation,
    summarise_valuation,
    valuation_diagnostics,
    valuation_threshold_diagnostics,
    valuation_evidence_diagnostics,
)

def main():

    print("MAIN STARTED")


    # ---------------------------------
    # Initialise database
    # ---------------------------------

    initialise_database()

    # ---------------------------------
    # Load calibrated scoring weights
    # ---------------------------------

    calibrated_weights = get_calibrated_weights()

    TECHNICAL_WEIGHT = calibrated_weights["Technical Weight"]
    QUALITY_WEIGHT = calibrated_weights["Quality Weight"]
    GROWTH_WEIGHT = calibrated_weights["Growth Weight"]

    print(
        "CALIBRATED WEIGHTS:",
        calibrated_weights
    )

    # ---------------------------------
    # Update recommendations
    # ---------------------------------

    print(
        "Updating recommendation history"
    )

    # ---------------------------------
    # Evaluate previous recommendations
    # ---------------------------------

    print(
        "Evaluating previous recommendations"
    )

    recommendations_to_evaluate = (
        get_open_recommendations()
    )

    print(
        "OPEN RECOMMENDATIONS COUNT:",
        len(recommendations_to_evaluate)
    )

    print(
        recommendations_to_evaluate.head()
    )

    if (
        recommendations_to_evaluate is not None
        and not recommendations_to_evaluate.empty
    ):

        evaluations = calculate_evaluations(
            recommendations_to_evaluate
        )

        if (
            evaluations is not None
            and not evaluations.empty
        ):

            print(
                f"Evaluation records created: "
                f"{len(evaluations)}"
            )

            save_recommendation_evaluations(
                evaluations
            )

            from data.database import get_connection

            conn = get_connection()

            cursor = conn.cursor()

            cursor.execute(
                "SELECT COUNT(*) FROM outcomes"
            )

            print(
                "OUTCOME COUNT:",
                cursor.fetchone()[0]
            )

            conn.close()

        else:

            print(
                "No evaluation milestones reached"
            )

    else:

        print(
            "No previous recommendations requiring evaluation"
        )

    # ---------------------------------
    # Load recommendation learning data
    #
    # IMPORTANT:
    #
    # These legacy database-query outputs remain in place because
    # the current recommendation engine uses them during the stock
    # scanning phase.
    #
    # The newer governed AI decision layer uses the separate
    # recommendation_learning outputs calculated later in main().
    # ---------------------------------

    performance_summary = pd.DataFrame()
    signal_performance = pd.DataFrame()
    horizon_performance = pd.DataFrame()
    score_performance = pd.DataFrame()
    signal_horizon_performance = pd.DataFrame()
    score_horizon_performance = pd.DataFrame()
    score_bucket_performance = pd.DataFrame()
    component_score_performance = pd.DataFrame()

    try:

        performance_summary = (
            get_performance_summary()
        )

        signal_performance = (
            get_signal_performance()
        )

        horizon_performance = (
            get_horizon_performance()
        )

        score_performance = (
            get_score_performance()
        )

        signal_horizon_performance = (
            get_signal_horizon_performance()
        )

        score_horizon_performance = (
            get_score_horizon_performance()
        )

        score_bucket_performance = (
            get_score_bucket_performance()
        )

        component_score_performance = (
            get_component_score_performance()
        )

        print(
            "Recommendation learning data loaded"
        )

    except Exception as e:

        print(
            f"Learning data unavailable: {e}"
        )

    # ---------------------------------
    # Load universe
    # ---------------------------------

    tickers = get_market_universe()

    tickers = filter_investable_universe(
        tickers
    )

    # ---------------------------------
    # Load portfolio holdings for AI filter
    # ---------------------------------

    holdings = get_portfolio()

    portfolio_tickers = (
        holdings["Ticker"].tolist()
    )

    print(
        f"Portfolio holdings loaded: "
        f"{portfolio_tickers}"
    )

    print(
        f"Scanning universe: "
        f"{len(tickers)} stocks"
    )

    candidates = run_market_scan(
        tickers,
        limit=200
    )

    results = []

    # ---------------------------------
    # Scan stocks
    # ---------------------------------

    for candidate in candidates:

        try:

            ticker = candidate["Ticker"]

            df = candidate["df"]

            print(
                f"Scanning {ticker}"
            )

            # ---------------------------------
            # Technical Scoring Engine
            # ---------------------------------

            required_columns = [
                "Close",
                "SMA50",
                "SMA200",
                "RSI",
                "MACD",
                "MACD_signal",
                "Return_3m",
                "Volume",
                "Volume_avg"
            ]

            missing_columns = [
                col
                for col in required_columns
                if col not in df.columns
            ]

            if missing_columns:

                print(
                    f"{ticker} skipped - missing indicators:",
                    missing_columns
                )

                continue

            try:

                score_result = (
                    candidate["Score Result"]
                )

            except Exception as e:

                print(
                    f"SCORER FAILED {ticker}: {e}"
                )

                continue

            technical_score = score_result.get(
                "Technical Score",
                0
            )

            technical_reasons = score_result.get(
                "Technical Reasons",
                []
            )

            technical_risks = score_result.get(
                "Technical Risks",
                []
            )

            trend_score = score_result.get(
                "Trend Score",
                0
            )

            momentum_score = score_result.get(
                "Momentum Score",
                0
            )

            volume_score = score_result.get(
                "Volume Score",
                0
            )

            risk_score = score_result.get(
                "Risk Score",
                0
            )

            print(
                f"{ticker} SCORE RESULT:",
                technical_score,
                technical_reasons[:3]
            )

            fundamentals = get_fundamentals(
                ticker
            )

            valuation = assess_valuation(
                fundamentals
        )

            quality_score, quality_reasons = (
                score_quality(
                    fundamentals
                )
            )

            print(
                "Passed quality"
            )

            growth_results = score_growth(
                fundamentals
            )

            print(
                "Passed growth"
            )

            growth_score = (
                growth_results["Growth Score"]
            )

            growth_reasons = (
                growth_results["Growth Reasons"]
            )

            growth_risks = (
                growth_results["Growth Risks"]
            )

            # ---------------------------------
            # Investment Score
            # ---------------------------------
            #
            # Investment Score is calculated by the
            # central investment_score module.
            #
            # Keeping this calculation in one place
            # prevents different parts of the application
            # from producing different Investment Scores.
            #
            # The scoring engine can be augmented in the
            # future with AI-derived assessment or
            # statistically calibrated inputs, but AI should
            # not directly override the core score without
            # explicit governance.
            # ---------------------------------

            investment_score = (
                calculate_investment_score(
                    technical_score,
                    quality_score,
                    growth_score
                )
            )

            investment_score = round(
                float(investment_score)
            )

            signal = generate_signal(
                investment_score,
                quality_score,
                technical_score,
                df
            )

            recommendation = (
                generate_recommendation(
                    ticker=ticker,
                    signal=signal,
                    investment_score=investment_score,
                    technical_score=technical_score,
                    quality_score=quality_score,
                    growth_score=growth_score,
                    technical_reasons=technical_reasons,
                    quality_reasons=quality_reasons,
                    signal_performance=signal_performance,
                    score_bucket_performance=(
                        score_bucket_performance
                    ),
                    security_type="STOCK"
                )
            )

            print(
                "Passed recommendation"
            )

            latest = df.iloc[-1]

            print(
                f"ADDING {ticker}: "
                f"Investment {investment_score}, "
                f"Quality {quality_score}"
            )

            ai_decision = generate_ai_decision(
                {
                    "Investment Score":
                        investment_score,

                    "Confidence Score":
                        recommendation.get(
                            "Confidence Score",
                            0
                        ),

                    "Technical Score":
                        technical_score,

                    "Trend Score":
                        trend_score,

                    "Momentum Score":
                        momentum_score,

                    "Volume Score":
                        volume_score,

                    "Risk Score":
                        risk_score,

                    "Quality Score":
                        quality_score,

                    "Growth Score":
                        growth_score,
                }
            )

            print(
                f"{ticker} AI DECISION: "
                f"{ai_decision}"
            )


            ai_recommendation = (
                generate_ai_recommendation(
                    {
                        "Ticker":
                            ticker,

                        "Signal":
                            signal,

                        "Investment Score":
                            investment_score,

                        "Technical Score":
                            technical_score,

                        "Quality Score":
                            quality_score,

                        "Growth Score":
                            growth_score,

                        "Confidence Score":
                            recommendation[
                                "Confidence Score"
                            ],

                        "RSI":
                            float(
                                latest["RSI"]
                            ),

                        "Revenue Growth":
                            fundamentals.get(
                                "Revenue Growth",
                                0
                            ),

                        "Return on Equity":
                            fundamentals.get(
                                "Return on Equity",
                                0
                            ),

                        "Debt to Equity":
                            fundamentals.get(
                                "Debt to Equity",
                                0
                            ),

                        "Sector":
                            fundamentals.get(
                                "Sector",
                                "Unknown"
                            )
                    }
                )
            )

            entry_quality = assess_entry_quality(df)

            print(
                f"ENTRY QUALITY DEBUG | {ticker} | "
                f"EQ={entry_quality.get('Entry Quality')} | "
                f"SMA50={entry_quality.get('Extension SMA50 %')} | "
                f"SMA200={entry_quality.get('Extension SMA200 %')} | "
                f"5D={entry_quality.get('Return 5D %')} | "
                f"10D={entry_quality.get('Return 10D %')} | "
                f"20D={entry_quality.get('Return 20D %')}"
            )

            print(
                "About to append"
            )

            results.append(
                {
                    "Ticker":
                        ticker,
                    "Name":
                        fundamentals.get(
                            "Name",
                            ticker
                        ),

                    "Signal":
                        signal,

                    # Core Scores
                    "Score":
                        technical_score,

                    "Technical Score":
                        technical_score,

                    "Momentum Score":
                        momentum_score,

                    "Quality Score":
                        quality_score,

                    "Investment Score":
                        investment_score,

                    "Growth Score":
                        growth_score,

                    # Confidence Engine
                    "Confidence":
                        recommendation[
                            "Confidence"
                        ],

                    "Confidence Score":
                        recommendation.get(
                            "Confidence Score",
                            0
                        ),

                    "Confidence Reasons":
                        recommendation.get(
                            "Confidence Reasons",
                            []
                        ),

                    # Price / Technical Data
                    "Price":
                        round(
                            float(
                                latest["Close"]
                            ),
                            2
                        ),

                    "RSI":
                        round(
                            float(
                                latest["RSI"]
                            ),
                            1
                        ),

                    "SMA50":
                        round(
                            float(
                                latest["SMA50"]
                            ),
                            2
                        ),

                    "SMA200":
                        round(
                            float(
                                latest["SMA200"]
                            ),
                            2
                        ),

                    "3M Return %":
                        round(
                            float(
                                latest[
                                    "Return_3m"
                                ]
                            ) * 100,
                            2
                        ),

                    # ---------------------------------
                    # BUY NEW Entry Quality — SHADOW
                    # ---------------------------------
                    "Extension SMA50 %":
                        entry_quality[
                            "Extension SMA50 %"
                        ],

                    "Extension SMA200 %":
                        entry_quality[
                            "Extension SMA200 %"
                        ],

                    "Return 5D %":
                        entry_quality[
                            "Return 5D %"
                        ],

                    "Return 10D %":
                        entry_quality[
                            "Return 10D %"
                        ],

                    "Return 20D %":
                        entry_quality[
                            "Return 20D %"
                        ],

                    "Entry Quality":
                        entry_quality[
                            "Entry Quality"
                        ],

                    "Entry Quality Mode":
                        entry_quality[
                            "Entry Quality Mode"
                        ],

                    # Fundamentals
                    "Revenue Growth":
                        fundamentals.get(
                            "Revenue Growth",
                            0
                        ),

                    "Profit Margin":
                        fundamentals.get(
                            "Profit Margin",
                            0
                        ),

                    "Return on Equity":
                        fundamentals.get(
                            "Return on Equity",
                            0
                        ),

                    "Debt to Equity":
                        fundamentals.get(
                            "Debt to Equity",
                            0
                        ),

                    # Valuation — SHADOW

                    "PE Ratio":
                        valuation.get(
                            "PE Ratio"
                        ),

                    "Forward PE":
                        valuation.get(
                            "Forward PE"
                        ),

                    "PEG Ratio":
                        valuation.get(
                            "PEG Ratio"
                        ),

                    "Price to Sales":
                        valuation.get(
                            "Price to Sales"
                        ),

                    "EV to EBITDA":
                        valuation.get(
                            "EV to EBITDA"
                        ),

                    "Free Cash Flow":
                        valuation.get(
                            "Free Cash Flow"
                        ),

                    "Valuation":
                        valuation.get(
                            "Valuation",
                            "UNKNOWN"
                        ),

                    "Valuation Mode":
                        valuation.get(
                            "Valuation Mode",
                            "SHADOW"
                        ),

                    "Sector":
                        fundamentals.get(
                            "Sector",
                            "Unknown"
                        ),
                    "Industry":
                        fundamentals.get(
                            "Industry",
                            "Unknown"
                        ),

                    # Recommendation Engine
                    "Recommendation Reasons":
                        recommendation[
                            "Reasons"
                        ],

                    "Recommendation Risks":
                        recommendation[
                            "Risks"
                        ],

                    # Growth Engine
                    "Growth Reasons":
                        growth_reasons,

                    "Growth Risks":
                        growth_risks,

                    # ---------------------------------
                    # AI Analyst Layer
                    # ---------------------------------

                    "AI Summary":
                        ai_recommendation[
                            "Summary"
                        ],

                    "AI Investment Thesis":
                        ai_recommendation[
                            "Investment Thesis"
                        ],

                    "AI Strengths":
                        ai_recommendation[
                            "Strengths"
                        ],

                    "AI Risks":
                        ai_recommendation[
                            "Risks"
                        ],

                    "AI Catalysts":
                        ai_recommendation[
                            "Catalysts"
                        ],

                    "AI Holding Period":
                        ai_recommendation[
                            "Holding Period"
                        ],

                    "AI Investor Type":
                        ai_recommendation[
                            "Investor Type"
                        ],

                    "AI Probability":
                        ai_recommendation[
                            "Probability"
                        ],

                    # ---------------------------------
                    # AI Decision Layer
                    # ---------------------------------

                    "AI Decision":
                        ai_decision[
                            "Decision"
                        ],

                    "AI Decision Object":
                        ai_decision,

                    "AI Conviction":
                        ai_decision[
                            "Conviction"
                        ],

                    "AI Conviction Score":
                        ai_decision[
                            "Conviction Score"
                        ],

                    "AI Decision Thesis":
                        ai_decision[
                            "Investment Thesis"
                        ],

                    "AI Decision Risks":
                        (
                            "; ".join(
                                ai_decision[
                                    "Risks"
                                ]
                            )
                            if ai_decision[
                                "Risks"
                            ]
                            else
                            "No material risks identified"
                        ),

                    "AI Action":
                        ai_decision[
                            "Recommended Action"
                        ],

                    "AI Review Triggers":
                        ai_decision[
                            "Review Triggers"
                        ]
                }
            )

            print(
                f"RESULTS COUNT NOW: "
                f"{len(results)}"
            )

        except Exception as e:

            print(
                f"\nERROR processing {ticker}"
            )

            traceback.print_exc()

    # ---------------------------------
    # Track already analysed stocks
    # ---------------------------------

    scanned = {
        str(r["Ticker"]).upper()
        for r in results
        if "Ticker" in r
    }

    print(
        "SCANNED STOCK COUNT:",
        len(scanned)
    )

    for ticker in portfolio_tickers:

        # CASH is a portfolio balance, not an investment candidate.
        if str(ticker).upper() == "CASH":
            continue

        if ticker not in scanned:

            try:

                print(
                    "Adding holding to scanner:",
                    ticker
                )

                holding_analysis = analyse_stock(
                    ticker
                )

                if holding_analysis:

                    results.append(
                        holding_analysis
                    )

            except Exception as e:

                print(
                    "Holding enrichment failed:",
                    ticker,
                    e
                )

    # ---------------------------------
    # Valuation Calibration — SHADOW
    # ---------------------------------

    valuation_summary = summarise_valuation(
        results
    )

    print(
        "\nVALUATION CALIBRATION — SHADOW"
    )

    print(
        f"Total analysed: "
        f"{valuation_summary['Total']}"
    )

    print(
        f"UNDERVALUED: "
        f"{valuation_summary['UNDERVALUED']}"
    )

    print(
        f"WELL VALUED: "
        f"{valuation_summary['WELL VALUED']}"
    )

    print(
        f"OVERVALUED: "
        f"{valuation_summary['OVERVALUED']}"
    )

    print(
        f"UNKNOWN: "
        f"{valuation_summary['UNKNOWN']}"
    )

    # ---------------------------------
    # Valuation Classification Detail
    # ---------------------------------

    valuation_details = valuation_diagnostics(
        results
    )

    threshold_counts = valuation_threshold_diagnostics(
        results
    )

    print(
        "\nVALUATION THRESHOLD DIAGNOSTICS — SHADOW"
    )

    for metric, count in threshold_counts.items():

        print(
            f"{metric}: {count}"
        )

    valuation_evidence = valuation_evidence_diagnostics(results)

    print("\nVALUATION EVIDENCE DIAGNOSTICS — SHADOW")

    for item in valuation_evidence:
        print(
            f"{item['Ticker']} | "
            f"Earnings={item['Earnings Expensive']} | "
            f"Growth={item['Growth Expensive']} | "
            f"Enterprise/Revenue={item['Enterprise/Revenue Expensive']}"
        )
    # ---------------------------------
    # Rank stocks
    # ---------------------------------

    print(
        f"RESULTS BEFORE SORT: {len(results)}"
    )



    results = sorted(
        results,
        key=lambda x: x["Investment Score"],
        reverse=True
    )

    print(
        f"RESULTS AFTER SORT: {len(results)}"
    )

   
    


    # ---------------------------------
    # Save recommendation history
    # ---------------------------------

    print("\nPRE-SAVE EQ DEBUG")

    for stock in results[:20]:
        print(
            f"PRE-SAVE EQ DEBUG | "
            f"{stock.get('Ticker')} | "
            f"EQ={stock.get('Entry Quality')} | "
            f"SMA50={stock.get('Extension SMA50 %')} | "
            f"SMA200={stock.get('Extension SMA200 %')}"
        )



    save_recommendations(
        results
    )

    print(
        "\nTOP STOCKS"
    )

    for stock in results[:20]:

        print(
            f"{stock['Ticker']} | "
            f"{stock['Signal']} | "
            f"Investment: {stock['Investment Score']} | "
            f"Confidence: {stock['Confidence']}"
        )

    # ---------------------------------
    # Portfolio processing
    # ---------------------------------

    portfolio_summary = None
    sector_summary = None
    portfolio_actions = None
    portfolio_optimisation = None
    rebalance_recommendations = None
    portfolio_health = None
    decisions = None
    trade_plan = None
    portfolio_ai_review = None
    portfolio_decisions = None
    portfolio_manager_review = None
    final_portfolio_decisions = None
    capital_allocation = None
    market_intelligence = pd.DataFrame()

    try:

        portfolio_summary = analyse_portfolio(
            holdings,
            results
        )

        portfolio_summary = (
            enrich_portfolio_holdings(
                portfolio_summary,
                results
            )
        )

        # ---------------------------------
        # BUY NEW CANDIDATE SELECTION
        #
        # Investment opportunity ranking is
        # performed before portfolio governance.
        # ---------------------------------
        
        buy_new_candidates = (
            select_buy_new_candidates(
                pd.DataFrame(results)
            )
        )
        
        print(
        
            f"BUY NEW CANDIDATES: "
        
            f"{len(buy_new_candidates)}"
        
        )
        

        portfolio_actions = (
            generate_portfolio_recommendations(
                holdings,
                results
            )
        )

        sector_summary = analyse_sectors(
            portfolio_summary,
            results
        )

        targets = get_targets()

        portfolio_optimisation = (
            optimise_portfolio(
                sector_summary,
                targets
            )
        )

        rebalance_recommendations = (
            generate_rebalance_recommendations(
                portfolio_summary,
                portfolio_optimisation,
                results
            )
        )

        print("\n========== SECTOR SUMMARY ==========")
        print(sector_summary.to_string(index=False))

        print("\n========== PORTFOLIO OPTIMISATION ==========")
        print(portfolio_optimisation.to_string(index=False))

        print("\n========== REBALANCE RECOMMENDATIONS ==========")
        print(rebalance_recommendations.to_string(index=False))


        portfolio_health = (
            calculate_portfolio_health(
                portfolio_summary,
                sector_summary
            )
        )

        if results:

            test_context = (
                evaluate_portfolio_context(
                    results[0],
                    portfolio_summary,
                    sector_summary,
                    portfolio_health
                )
            )

        else:

            test_context = None


        # ---------------------------------
        # Candidate Ranking Diagnostic
        #
        # Persist read-only snapshots of:
        #
        #     - live scan universe
        #     - current portfolio
        #
        # Used by:
        #
        # tests/test_candidate_ranking.py
        #
        # ---------------------------------

        save_candidate_ranking_snapshot(

            results,

            portfolio_summary,

        )

        portfolio_decisions = (

            generate_portfolio_decisions(

                portfolio_summary,

                pd.DataFrame(results)

            )

        )
    
        print(
            "\nPORTFOLIO DECISIONS"
        )

        for decision in portfolio_decisions[:10]:

            print(
                decision
            )

        # ---------------------------------
        # MARKET & EVENT INTELLIGENCE
        # Shadow mode — does not alter
        # portfolio decisions
        # ---------------------------------

        print(
            "\nMARKET & EVENT INTELLIGENCE"
        )

        market_intelligence = (
            assess_market_intelligence(
                holdings,
                portfolio_decisions,
                force_refresh=True

            )
        )

        print(
            f"Market intelligence records: "
            f"{len(market_intelligence)}"
        )

        if not market_intelligence.empty:

            print(
                market_intelligence[
                    [
                        "Ticker",
                        "Name",
                        "Current Portfolio Action",
                        "Existing Holding",
                        "Analyst Recommendation",
                        "Analyst Target Upside %",
                        "Earnings Status",
                    ]
                ].to_string(
                    index=False
                )
            )

        # Convert stock results into dataframe for capital allocator

        if isinstance(
            results,
            list
        ):

            opportunities_df = pd.DataFrame(
                results
            )

        else:

            opportunities_df = results

        capital_allocation = (
            generate_capital_allocation(
                portfolio_summary=(
                    portfolio_summary
                ),
                opportunities=(
                    opportunities_df
                ),
                portfolio_decisions=(
                    portfolio_decisions
                )
            )
        )

        try:

            ai_reviews = run_ai_agents(
                results,
                portfolio_summary,
                sector_summary,
                portfolio_health
            )

        except Exception as e:

            print(
                f"AI agents skipped: {e}"
            )

            ai_reviews = []

        decisions = generate_decisions(
            portfolio_summary,
            results,
            rebalance_recommendations
        )

        trade_plan = generate_trade_plan(
            portfolio_summary,
            portfolio_optimisation,
            results
        )

        growth_plan = generate_growth_plan(
            results,
            portfolio_value=(
                portfolio_summary[
                    "Current Value"
                ].sum()
            ),
            current_holdings=(
                portfolio_summary.to_dict(
                    "records"
                )
            )
        )

        print(
            "\nPORTFOLIO GROWTH PLAN"
        )

        print(
            growth_plan.head(10)
        )

        print(
            "ABOUT TO CREATE MANAGER REVIEW"
        )

        portfolio_manager_review = (
            generate_portfolio_manager_review(
                portfolio_summary,
                sector_summary,
                decisions,
                trade_plan,
                portfolio_health
            )
        )

        print(
            "MANAGER REVIEW CREATED"
        )

        print(
            "DEBUG MANAGER REVIEW:",
            portfolio_manager_review
        )

        print(
            "\nPORTFOLIO HEALTH"
        )

        print(
            portfolio_health
        )

        print(
            "\nINVESTMENT DECISIONS"
        )

        print(
            decisions
        )

        print(
            "\nTRADE PLAN"
        )

        print(
            trade_plan
        )

        print(
            "\nAI PORTFOLIO MANAGER REVIEW"
        )

        print(
            portfolio_manager_review
        )

    except Exception as e:

        print(
            "PORTFOLIO ANALYSIS ERROR:"
        )

        traceback.print_exc()

        portfolio_manager_review = None

    # ---------------------------------
    # AI Portfolio Intelligence
    # ---------------------------------

    try:

        portfolio_ai_review = (
            generate_portfolio_review(
                portfolio_summary,
                results
            )
        )

        print(
            "\nAI PORTFOLIO REVIEW"
        )

        for review in portfolio_ai_review:

            print(
                review
            )

    except Exception as e:

        print(
            f"AI Portfolio Intelligence skipped: {e}"
        )

        portfolio_ai_review = []

    # ---------------------------------
    # Final Portfolio Decisions
    # ---------------------------------

    print(
        "\nDEBUG DECISIONS INPUT"
    )

    print(
        decisions
    )

    print(
        "\nDUPLICATE TICKERS"
    )

    if (
        decisions is not None
        and not decisions.empty
    ):

        print(
            decisions[
                decisions.duplicated(
                    subset=["Ticker"],
                    keep=False
                )
            ]
        )

    else:

        print(
            "No portfolio decisions generated"
        )

    # ---------------------------------
    # Final Portfolio Decision
    # ---------------------------------
    #
    # This is the final governed decision layer.
    #
    # IMPORTANT:
    # - portfolio_decisions = deterministic governed proposals
    # - portfolio_ai_review = AI portfolio review
    # - portfolio_manager_review = portfolio manager review
    # - portfolio_health = portfolio risk/health context
    # - capital_allocation = capital constraint/allocation context
    #
    # The final decision engine reconciles these inputs and
    # returns the production Final Decision interface.
    # ---------------------------------

    print(
        "\nPORTFOLIO SUMMARY COLUMNS:",
        portfolio_summary.columns.tolist()
    )

    print(
        "\nPORTFOLIO SUMMARY HEAD:"
    )

    print(
        portfolio_summary.head(10).to_string()
    )

    # ---------------------------------
    # Recommendation Learning
    # ---------------------------------
    #
    # IMPORTANT:
    #
    # This is the current governed learning dataset.
    #
    # Unlike the legacy query outputs used earlier by the
    # recommendation engine, this source is built directly from
    # the persisted recommendation_evaluations table.
    #
    # This learning output is therefore the authoritative source
    # for Recommendation Intelligence and the governed AI
    # portfolio decision layer.
    # ---------------------------------

    print(
        "\nCALCULATING RECOMMENDATION LEARNING"
    )

    recommendation_history = (
        get_evaluation_history()
    )

    recommendation_learning = (
        calculate_recommendation_learning(
            recommendation_history
        )
    )

    if isinstance(
        recommendation_learning,
        dict,
    ):

        for key, value in recommendation_learning.items():

            print(
                f"{key}: {value}"
            )

    else:

        print(
            recommendation_learning
        )

    # ---------------------------------
    # Current learning outputs
    # ---------------------------------
    #
    # Keep these separate from the legacy performance variables.
    #
    # This prevents the newer governed learning data from
    # accidentally altering the existing recommendation engine.
    # ---------------------------------

    learning_signal_performance = (
        recommendation_learning.get(
            "Signal Performance",
            pd.DataFrame()
        )
    )

    learning_score_bucket_performance = (
        recommendation_learning.get(
            "Score Bucket Performance",
            pd.DataFrame()
        )
    )

    learning_component_score_performance = (
        recommendation_learning.get(
            "Component Score Performance",
            pd.DataFrame()
        )
    )

    learning_horizon_performance = (
        recommendation_learning.get(
            "Horizon Learning",
            pd.DataFrame()
        )
    )

    learning_ticker_horizon_performance = (
        recommendation_learning.get(
            "Ticker Horizon Performance",
            pd.DataFrame()
        )
    )

    print(
        "\nTICKER HORIZON LEARNING:",
        learning_ticker_horizon_performance.shape
    )

    if not learning_ticker_horizon_performance.empty:
        print(
            "TICKER HORIZON COLUMNS:",
            learning_ticker_horizon_performance.columns.tolist()
        )
        print(
            learning_ticker_horizon_performance.head(10).to_string(
                index=False
            )
        )
    else:
        print(
            "TICKER HORIZON LEARNING IS EMPTY"
        )

    # ---------------------------------
    # Recommendation Intelligence
    # ---------------------------------
    #
    # IMPORTANT:
    #
    # Recommendation Intelligence consumes the CURRENT
    # recommendation-learning outputs, not the legacy query
    # outputs used during the stock scan.
    # ---------------------------------

    recommendation_intelligence = (
        pd.DataFrame()
    )

    try:

        recommendation_intelligence = (
            generate_recommendation_intelligence(
                results,
                learning_signal_performance,
                learning_score_bucket_performance,
                learning_component_score_performance,
                learning_horizon_performance,
            )
        )

        print(
            "\nRECOMMENDATION INTELLIGENCE CREATED:",
            recommendation_intelligence.shape
        )

    except Exception as e:

        print(
            f"Recommendation Intelligence skipped: {e}"
        )
    
    # ---------------------------------
    # Final Portfolio Decisions
    # ---------------------------------

    print(
        "\nGENERATING FINAL PORTFOLIO DECISIONS"
    )

    try:

        final_portfolio_decisions = (
            generate_final_portfolio_decisions(
                portfolio_summary=portfolio_summary,
                portfolio_decisions=pd.DataFrame(
                    portfolio_decisions
                ),
                portfolio_ai_review=portfolio_ai_review,
                portfolio_manager_review=portfolio_manager_review,
                portfolio_health=portfolio_health,
                capital_allocation=capital_allocation,
                recommendation_intelligence=(
                    recommendation_intelligence
                ),
                learning_ticker_horizon_performance=(
                    learning_ticker_horizon_performance
                ),
                market_intelligence=market_intelligence,

            )
        )

        print(
            "FINAL PORTFOLIO DECISIONS GENERATED:",
            type(final_portfolio_decisions)
        )

        audit_run_id = None

        if isinstance(
            final_portfolio_decisions,
            pd.DataFrame
        ):
            audit_run_id = (
                final_portfolio_decisions.attrs.get(
                    "audit_run_id"
                )
            )

    except Exception as e:

        print(
            "FINAL PORTFOLIO DECISION ERROR:",
            e
        )

        traceback.print_exc()

        final_portfolio_decisions = []

    print(
        "\nFINAL PORTFOLIO DECISIONS"
    )

    print(
        final_portfolio_decisions
    )


    # ---------------------------------

    # BUY NEW PRODUCTION PIPELINE

    # SNAPSHOT

    #

    # Persist the actual production outputs

    # so the diagnostic can trace BUY NEW

    # candidates through the complete

    # production decision chain.

    # ---------------------------------

    save_buy_new_pipeline_snapshot(

        portfolio_decisions,

        final_portfolio_decisions,

    )


    # ---------------------------------
    # Portfolio Reallocation
    # ---------------------------------

    print(
        "\nGENERATING PORTFOLIO REALLOCATION"
    )

    try:


        portfolio_reallocation = generate_portfolio_reallocation(
            final_portfolio_decisions=final_portfolio_decisions,
            portfolio_value=portfolio_summary["Current Value"].sum()
        )

        print(
            "PORTFOLIO REALLOCATION GENERATED:",
            type(portfolio_reallocation)
        )

    except Exception as e:

        print(
            "PORTFOLIO REALLOCATION ERROR:",
            e
        )

        traceback.print_exc()

        portfolio_reallocation = pd.DataFrame()

    print(
        "\nPORTFOLIO REALLOCATION"
    )

    print(
        portfolio_reallocation
    )

    # ---------------------------------
    # Alerts
    # ---------------------------------

    alerts = generate_alerts(
        portfolio_summary,
        results
    )

    if alerts is None:

        alerts = pd.DataFrame()

    # =====================================================
    # ADAPTIVE WEIGHT OPTIMISATION
    # =====================================================

    weight_learning = (
        run_weight_optimizer()
    )

    print(
        "\nOPTIMISED SCORING WEIGHTS"
    )

    print(
        weight_learning[
            "Recommended Weights"
        ]
    )

    factor_performance = (
        calculate_factor_performance(
            recommendation_history
        )
    )

    print(
        "\n===== REPORT INPUT CHECK ====="
    )

    print(
        "Results:",
        len(results)
    )

    print(
        "Portfolio Summary:",
        type(portfolio_summary),
        getattr(
            portfolio_summary,
            "shape",
            None
        )
    )

    print(
        "Sector Summary:",
        type(sector_summary),
        getattr(
            sector_summary,
            "shape",
            None
        )
    )

    print(
        "Portfolio Actions:",
        type(portfolio_actions),
        getattr(
            portfolio_actions,
            "shape",
            None
        )
    )

    print(
        "Portfolio Optimisation:",
        type(portfolio_optimisation),
        getattr(
            portfolio_optimisation,
            "shape",
            None
        )
    )

    print(
        "Rebalance:",
        type(rebalance_recommendations),
        getattr(
            rebalance_recommendations,
            "shape",
            None
        )
    )

    print(
        "Portfolio Health:",
        portfolio_health
    )

    print(
        "Decisions:",
        type(decisions)
    )

    print(
        "Trade Plan:",
        type(trade_plan)
    )

    print(
        "AI Review:",
        type(portfolio_ai_review)
    )

    print(
        "Manager Review:",
        type(portfolio_manager_review)
    )

    print(
        "Recommendation Intelligence:",
        type(recommendation_intelligence),
        getattr(
            recommendation_intelligence,
            "shape",
            None
        )
    )

    print(
        "Recommendation Learning:",
        type(recommendation_learning)
    )

    # ---------------------------------
    # Portfolio Growth Plan Safety
    # ---------------------------------

    if "growth_plan" not in locals():

        growth_plan = pd.DataFrame()

    # ---------------------------------
    # Portfolio Reallocation Safety
    # ---------------------------------

    if "portfolio_reallocation" not in locals():

        portfolio_reallocation = {
            "reallocation": pd.DataFrame(),
            "summary": {}
        }


    # ---------------------------------
    # Excel report
    # ---------------------------------

    create_report(
        results,
        portfolio_summary,
        alerts,
        sector_summary,
        portfolio_actions,
        portfolio_optimisation,
        rebalance_recommendations,
        portfolio_health,
        capital_allocation,
        market_intelligence,
        portfolio_reallocation,
        decisions,
        trade_plan,
        performance_summary,
        signal_performance,
        horizon_performance,
        score_performance,
        score_bucket_performance,
        component_score_performance,
        signal_horizon_performance,
        recommendation_intelligence,
        portfolio_ai_review,
        portfolio_manager_review,
        growth_plan,
        final_portfolio_decisions,
        recommendation_learning
    )

    print(
        "\nReport complete"
    )


if __name__ == "__main__":
    main()
