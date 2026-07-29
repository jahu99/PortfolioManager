import pandas as pd
import traceback


from analysis import recommendations
from data.universe import get_sp500_universe
from data.market_data import get_stock_data
from data.fundamentals import get_fundamentals


from data.database import (
    initialise_database,
    save_recommendations,
    save_recommendation_evaluations,
    save_outcomes
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



from analysis import recommendations
from data.universe import get_sp500_universe
from data.market_data import get_stock_data
from data.fundamentals import get_fundamentals


from data.database import (
    initialise_database,
    save_recommendations,
    save_recommendation_evaluations,
    save_outcomes
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


from data.database_queries import (
    get_open_recommendations,
    get_recommendation_history,
    get_performance_summary,
    get_signal_performance,
    get_horizon_performance,
    get_score_performance,
    get_signal_horizon_performance,
    get_score_horizon_performance,
    get_score_bucket_performance,
    get_component_score_performance
)

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

def main():

    print("MAIN STARTED")


    # ---------------------------------
    # Initialise database
    # ---------------------------------

    initialise_database()


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

            save_outcomes(
                evaluations
            )

            print(
                f"Saved {len(evaluations)} outcomes"
            )

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

    universe = get_sp500_universe()


    print(
        f"Scanning {len(universe)} stocks"
    )



    results = []



    # ---------------------------------
    # Scan stocks
    # ---------------------------------

    for ticker in universe:


        try:


            print(
                f"Scanning {ticker}"
            )


            df = get_stock_data(
                ticker
            )


            if df.empty:

                continue



            df = add_indicators(
                df
            )


            if df.empty:

                continue



            technical_score, technical_reasons = score_stock(
                df
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




            investment_score = round(

                (technical_score * 0.45)

                +

                (quality_score * 0.30)

                +

                (growth_score * 0.25)

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
                    "Technical Score": technical_score,
                    "Quality Score": quality_score,
                    "Growth Score": growth_score,
                    "Confidence Score": recommendation["Confidence Score"]
                }
            )

            print(
                f"{ticker} AI DECISION: {ai_decision}"
            )

            ai_analysis = generate_ai_analysis(
                    ticker,
                    investment_score,
                    technical_score,
                    quality_score,
                    growth_score,
                    ai_decision,
                    recommendation["Reasons"],
                    recommendation["Risks"]
                )

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
    holdings = []
    portfolio_decisions = None



    try:


        holdings = get_portfolio()



        portfolio_summary = analyse_portfolio(
            holdings,
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



    except Exception as e:


        print(
            f"Portfolio analysis skipped: {e}"
        )

    # ---------------------------------
    # AI Portfolio Intelligence
    # ---------------------------------
    try:
        portfolio_ai_review = generate_portfolio_review(
            holdings,
            results
        )

        print("\nAI PORTFOLIO REVIEW")

        for review in portfolio_ai_review:
            print(review)
    except Exception as e:
        print(
            f"AI Portfolio Intelligence skipped: {e}"
        )
    # ---------------------------------
    # Alerts
    # ---------------------------------

    alerts = generate_alerts(
        portfolio_summary,
        results
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

    recommendation_history = get_recommendation_history()
    
    factor_performance = (
        calculate_factor_performance(
            recommendation_history
        )
    )

    

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
    portfolio_ai_review
)



    print(
        "\nReport complete"
    )








    print(
        "\nReport complete"
    )



if __name__ == "__main__":

    main()