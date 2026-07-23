from data.universe import get_sp500_universe
from data.market_data import get_stock_data
from data.fundamentals import get_fundamentals

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



def main():

    print("MAIN STARTED")


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



            investment_score = round(
                (technical_score * 0.6)
                +
                (quality_score * 0.4)
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
                technical_reasons,
                quality_reasons
            )



            latest = df.iloc[-1]



            results.append(
                {

                    "Ticker": ticker,

                    "Signal": signal,

                    "Score": technical_score,

                    "Quality Score": quality_score,

                    "Investment Score": investment_score,

                    "Confidence":
                        recommendation["Confidence"],


                    "Price": round(
                        float(latest["Close"]),
                        2
                    ),


                    "RSI": round(
                        float(latest["RSI"]),
                        1
                    ),


                    "SMA50": round(
                        float(latest["SMA50"]),
                        2
                    ),


                    "SMA200": round(
                        float(latest["SMA200"]),
                        2
                    ),


                    "3M Return %": round(
                        float(latest["Return_3m"]) * 100,
                        2
                    ),


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


                    "Recommendation Reasons":
                        recommendation["Reasons"],


                    "Recommendation Risks":
                        recommendation["Risks"]

                }
            )



        except Exception as e:

            print(
                f"Error processing {ticker}: {e}"
            )



    # ---------------------------------
    # Rank stocks
    # ---------------------------------

    results = sorted(
        results,
        key=lambda x: x["Investment Score"],
        reverse=True
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
    # Alerts
    # ---------------------------------

    alerts = generate_alerts(
        portfolio_summary,
        results
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
        trade_plan
    )



    print(
        "\nReport complete"
    )



if __name__ == "__main__":

    main()