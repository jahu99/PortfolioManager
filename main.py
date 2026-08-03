import pandas as pd
import traceback


from analysis import recommendations
from analysis import recommendation_learning


from data.market_data import get_stock_data
from data.fundamentals import get_fundamentals

from data.database import (
    initialise_database,
    get_open_recommendations,
    save_recommendations,
    save_recommendation_evaluations,
)


from data.database_queries import (
    get_recommendation_history,
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


from analysis.indicators import add_indicators
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

from analysis.ai_analyst import generate_ai_analysis

from analysis.portfolio_ai import (
    generate_portfolio_review
)

from analysis.portfolio_decision_engine import generate_portfolio_decisions

from analysis.portfolio_manager import generate_portfolio_manager_review

from agents.orchestrator import run_ai_agents

from analysis.portfolio_growth_engine import (
    generate_growth_plan
)

from analysis.portfolio_context import evaluate_portfolio_context



from analysis.final_portfolio_decision import (
    generate_final_portfolio_decisions

)

from analysis.portfolio_manager_rules import (
    apply_portfolio_manager_rules
)




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

def main():

    print("MAIN STARTED")

    AI_ANALYSIS_LIMIT = 3
    ai_analysis_count = 0


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

    recommendations_to_evaluate = get_open_recommendations()

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
                f"Evaluation records created: {len(evaluations)}"
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

    portfolio_tickers = holdings["Ticker"].tolist()

    print(
        f"Portfolio holdings loaded: {portfolio_tickers}"
    )
    

    print(
    f"Scanning universe: {len(tickers)} stocks"
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
                col for col in required_columns
                if col not in df.columns
            ]


            if missing_columns:

                print(
                    f"{ticker} skipped - missing indicators:",
                    missing_columns
                )

                continue



            try:
                score_result = candidate["Score Result"]

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



            quality_score, quality_reasons = score_quality(
                fundamentals
            )

            print("Passed quality")

            growth_results = score_growth(
                fundamentals
            )

            print("Passed growth")


            growth_score = growth_results["Growth Score"]

            growth_reasons = growth_results["Growth Reasons"]

            growth_risks = growth_results["Growth Risks"]




            raw_investment_score = (

                (technical_score * TECHNICAL_WEIGHT)

                +

                (quality_score * QUALITY_WEIGHT)

                +

                (growth_score * GROWTH_WEIGHT)

            )


            investment_score = round(
                raw_investment_score * 1.15
            )


            # cap score
            investment_score = min(
                investment_score,
                100
            )


            signal = generate_signal(
                investment_score,
                quality_score,
                technical_score,
                df
            )


            recommendation = generate_recommendation(
                ticker,
                signal,
                investment_score,
                technical_score,
                quality_score,
                growth_score,
                technical_reasons,
                quality_reasons,
                signal_performance,
                score_bucket_performance
            )

            print("Passed recommendation")

            latest = df.iloc[-1]

            print(
                f"ADDING {ticker}: Investment {investment_score}, Quality {quality_score}"
            )

            ai_decision = generate_ai_decision(
                {
                    "Investment Score": investment_score,

                    "Confidence Score":
                        recommendation.get(
                            "Confidence Score",
                            0
                        ),

                    "Technical Score": technical_score,
                    "Trend Score": trend_score,
                    "Momentum Score": momentum_score,
                    "Volume Score": volume_score,
                    "Risk Score": risk_score,
                    "Quality Score": quality_score,
                    "Growth Score": growth_score,
                }
            )

            print(
                f"{ticker} AI DECISION: {ai_decision}"
            )

            ai_analysis = None

            ai_recommendation = generate_ai_recommendation(
                {
                    "Ticker": ticker,
                    "Signal": signal,
                    "Investment Score": investment_score,
                    "Technical Score": technical_score,
                    "Quality Score": quality_score,
                    "Growth Score": growth_score,
                    "Confidence Score": recommendation["Confidence Score"],
                    "RSI": float(latest["RSI"]),
                    "Revenue Growth": fundamentals.get("Revenue Growth", 0),
                    "Return on Equity": fundamentals.get("Return on Equity", 0),
                    "Debt to Equity": fundamentals.get("Debt to Equity", 0),
                    "Sector": fundamentals.get("Sector", "Unknown")
                }
            )

            print("About to append")

            results.append(
                {
                    "Ticker": ticker,
                    "Signal": signal,

                    # Core Scores
                    "Score": technical_score,
                    "Technical Score": technical_score,
                    "Quality Score": quality_score,
                    "Investment Score": investment_score,
                    "Growth Score": growth_score,

                    # Confidence Engine
                    "Confidence": recommendation["Confidence"],
                    "Confidence Score": recommendation.get("Confidence Score", 0),
                    "Confidence Reasons": recommendation.get("Confidence Reasons", []),

                    # Price / Technical Data
                    "Price": round(float(latest["Close"]), 2),
                    "RSI": round(float(latest["RSI"]), 1),
                    "SMA50": round(float(latest["SMA50"]), 2),
                    "SMA200": round(float(latest["SMA200"]), 2),
                    "3M Return %": round(float(latest["Return_3m"]) * 100, 2),

                    # Fundamentals
                    "Revenue Growth": fundamentals.get("Revenue Growth", 0),
                    "Profit Margin": fundamentals.get("Profit Margin", 0),
                    "Return on Equity": fundamentals.get("Return on Equity", 0),
                    "Debt to Equity": fundamentals.get("Debt to Equity", 0),
                    "Sector": fundamentals.get("Sector", "Unknown"),
                    "Industry": fundamentals.get("Industry", "Unknown"),

                    # Recommendation Engine
                    "Recommendation Reasons": recommendation["Reasons"],
                    "Recommendation Risks": recommendation["Risks"],

                    # Growth Engine
                    "Growth Reasons": growth_reasons,
                    "Growth Risks": growth_risks,


                    # ---------------------------------
                    # AI Analyst Layer
                    # ---------------------------------

                    "AI Summary":
                        ai_recommendation["Summary"],

                    "AI Investment Thesis":
                        ai_recommendation["Investment Thesis"],

                    "AI Strengths":
                        ai_recommendation["Strengths"],

                    "AI Risks":
                        ai_recommendation["Risks"],

                    "AI Catalysts":
                        ai_recommendation["Catalysts"],

                    "AI Holding Period":
                        ai_recommendation["Holding Period"],

                    "AI Investor Type":
                        ai_recommendation["Investor Type"],

                    "AI Probability":
                        ai_recommendation["Probability"],


                    # ---------------------------------
                    # AI Decision Layer
                    # ---------------------------------

                    "AI Decision":
                        ai_decision["Decision"],

                    "AI Decision Object":
                        ai_decision,

                    "AI Conviction":
                        ai_decision["Conviction"],

                    "AI Conviction Score":
                        ai_decision["Conviction Score"],

                    "AI Decision Thesis":
                        ai_decision["Investment Thesis"],

                    "AI Decision Risks":
                        "; ".join(ai_decision["Risks"])
                        if ai_decision["Risks"]
                        else "No material risks identified",

                    "AI Action":
                        ai_decision["Recommended Action"],

                    "AI Review Triggers":
                        ai_decision["Review Triggers"]
                }
            )

            print(
                f"RESULTS COUNT NOW: {len(results)}"
            )



        except Exception as e:


            print(f"\nERROR processing {ticker}")

            traceback.print_exc()


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
    # AI Analyst Review - Top Candidates
    # ---------------------------------

    for stock in results[:AI_ANALYSIS_LIMIT]:

        try:

            print(
                "OLLAMA ANALYST RUN:",
                stock["Ticker"]
            )

            ai_analysis = generate_ai_analysis(
                stock["Ticker"],
                stock["Investment Score"],
                stock["Technical Score"],
                stock["Quality Score"],
                stock["Growth Score"],
                stock["AI Decision Object"],
                stock["Recommendation Reasons"],
                stock["Recommendation Risks"]
            )

            stock["AI Analysis"] = ai_analysis


        except Exception as e:

            print(
                f"AI Analyst failed for {stock['Ticker']}: {e}"
            )

            stock["AI Analysis"] = None

    # ---------------------------------
    # Save recommendation history
    # ---------------------------------

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



    try:

        
        portfolio_summary = analyse_portfolio(
            holdings,
            results
        )

        


        portfolio_summary = enrich_portfolio_holdings(
            portfolio_summary,
            results
        )

        portfolio_actions = generate_portfolio_recommendations(
            holdings,
            results
        )



        sector_summary = analyse_sectors(
            portfolio_summary
        )



        targets = get_targets()



        portfolio_optimisation = optimise_portfolio(
            sector_summary,
            targets
        )



        rebalance_recommendations = (
            generate_rebalance_recommendations(
                portfolio_summary,
                portfolio_optimisation,
                results
            )
        )



        portfolio_health = calculate_portfolio_health(
            portfolio_summary,
            sector_summary
        )

        test_context = evaluate_portfolio_context(
            results[0],
            portfolio_summary,
            sector_summary,
            portfolio_health
        )

        print("\nPORTFOLIO CONTEXT TEST")
        print(test_context)

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

        portfolio_decisions = generate_portfolio_decisions(
            holdings,
            pd.DataFrame(results)
        )

        print(
            "\nPORTFOLIO DECISIONS"
        )

        for decision in portfolio_decisions[:10]:
            print(decision)



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
            portfolio_value=portfolio_summary["Current Value"].sum(),
            current_holdings=portfolio_summary.to_dict("records")
        )


        print("\nPORTFOLIO GROWTH PLAN")

        print(growth_plan.head(10))

        print("ABOUT TO CREATE MANAGER REVIEW")

        portfolio_manager_review = generate_portfolio_manager_review(
            portfolio_summary,
            sector_summary,
            decisions,
            trade_plan,
            portfolio_health
        )



        print("MANAGER REVIEW CREATED")

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
        
        portfolio_ai_review = generate_portfolio_review(
            portfolio_summary,
            results
        )

        print("\nAI PORTFOLIO REVIEW")

        for review in portfolio_ai_review:
            print(review)
    except Exception as e:
        print(
            f"AI Portfolio Intelligence skipped: {e}"
        )

        portfolio_ai_review = []

    # ---------------------------------
    # Final Portfolio Decisions
    # ---------------------------------

    print("\nDEBUG DECISIONS INPUT")
    print(decisions)


    print("\nDUPLICATE TICKERS")

    if decisions is not None and not decisions.empty:

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

    final_portfolio_decisions = generate_final_portfolio_decisions(
        portfolio_summary,
        decisions,
        portfolio_ai_review,
        portfolio_manager_review,
        portfolio_health
    )

    final_portfolio_decisions = apply_portfolio_manager_rules(
        final_portfolio_decisions,
        portfolio_health
    )


    print(
        "\nFINAL PORTFOLIO DECISIONS"
    )

    print(
        final_portfolio_decisions
    )
    
    # ---------------------------------
    # Alerts
    # ---------------------------------

    alerts = generate_alerts(
        portfolio_summary,
        results
    )


    recommendation_history = get_learning_history()

    recommendation_learning = (
        calculate_recommendation_learning(
            recommendation_history
        )
    )

    print(
        "\nRECOMMENDATION LEARNING"
    )

    if isinstance(recommendation_learning, dict):

        for key, value in recommendation_learning.items():

            print(
                f"{key}: {value}"
            )

    else:

        print(
            recommendation_learning
        )

    signal_performance = (
    recommendation_learning.get(
        "Signal Performance",
        pd.DataFrame()
        )
    )

    score_bucket_performance = (
        recommendation_learning.get(
            "Score Bucket Performance",
            pd.DataFrame()
        )
    )

    component_score_performance = (
        recommendation_learning.get(
            "Component Score Performance",
            pd.DataFrame()
        )
    )

    # ---------------------------------
    # Recommendation Intelligence
    # ---------------------------------

    try:

        recommendation_intelligence = (
            generate_recommendation_intelligence(
                results,
                signal_performance,
                score_bucket_performance,
                component_score_performance
            )
        )


    except Exception as e:

        print(
            f"Recommendation Intelligence skipped: {e}"
        )

    
    
    
    factor_performance = (
        calculate_factor_performance(
            recommendation_history
        )
    )

    print("\n===== REPORT INPUT CHECK =====")

    print("Results:", len(results))

    print("Portfolio Summary:",
        type(portfolio_summary),
        getattr(portfolio_summary, "shape", None))

    print("Sector Summary:",
        type(sector_summary),
        getattr(sector_summary, "shape", None))

    print("Portfolio Actions:",
        type(portfolio_actions),
        getattr(portfolio_actions, "shape", None))

    print("Portfolio Optimisation:",
        type(portfolio_optimisation),
        getattr(portfolio_optimisation, "shape", None))

    print("Rebalance:",
        type(rebalance_recommendations),
        getattr(rebalance_recommendations, "shape", None))

    print("Portfolio Health:",
        portfolio_health)

    print("Decisions:",
        type(decisions))

    print("Trade Plan:",
        type(trade_plan))

    print("AI Review:",
        type(portfolio_ai_review))

    print("Manager Review:",
        type(portfolio_manager_review))
    

    # ---------------------------------
    # Portfolio Growth Plan Safety
    # ---------------------------------

    if "growth_plan" not in locals():

        growth_plan = pd.DataFrame()


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








    print(
        "\nReport complete"
    )



if __name__ == "__main__":

    main()