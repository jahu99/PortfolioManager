import traceback

from data.market_data import get_stock_data
from data.fundamentals import get_fundamentals

from analysis.indicators import add_indicators
from analysis.scorer import score_stock
from analysis.quality import score_quality
from analysis.growth import score_growth
from analysis.signals import generate_signal
from analysis.recommendations import generate_recommendation

from analysis.ai_recommendation import generate_ai_recommendation
from analysis.ai_decision_engine import generate_ai_decision

from analysis.score_calibration import get_calibrated_weights



def analyse_stock(ticker):
    """
    Complete stock analysis pipeline.

    Used by:
    - Market scanner
    - Portfolio enrichment
    - AI portfolio manager

    Returns:
        dict containing complete stock intelligence
    """

    try:

        ticker = str(ticker).upper().strip()

        print(
            f"ANALYSING STOCK: {ticker}"
        )


        # ---------------------------------
        # Market data
        # ---------------------------------

        df = get_stock_data(
            ticker
        )


        if df is None or df.empty:

            print(
                f"No data for {ticker}"
            )

            return None



        df = add_indicators(
            df
        )



        latest = df.iloc[-1]



        # ---------------------------------
        # Technical score
        # ---------------------------------

        score_result = score_stock(
            df
        )


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



        # ---------------------------------
        # Fundamentals
        # ---------------------------------

        fundamentals = get_fundamentals(
            ticker
        )



        quality_score, quality_reasons = score_quality(
            fundamentals
        )



        growth_results = score_growth(
            fundamentals
        )


        growth_score = growth_results.get(
            "Growth Score",
            0
        )


        growth_reasons = growth_results.get(
            "Growth Reasons",
            []
        )


        growth_risks = growth_results.get(
            "Growth Risks",
            []
        )



        # ---------------------------------
        # Investment score
        # ---------------------------------

        weights = get_calibrated_weights()


        investment_score = round(

            technical_score
            *
            weights["Technical Weight"]

            +

            quality_score
            *
            weights["Quality Weight"]

            +

            growth_score
            *
            weights["Growth Weight"]

        )



        investment_score = min(
            investment_score,
            100
        )



        # ---------------------------------
        # Signal
        # ---------------------------------

        signal = generate_signal(
            investment_score,
            quality_score,
            technical_score,
            df
        )



        # ---------------------------------
        # Recommendation
        # ---------------------------------

        recommendation = generate_recommendation(
            ticker,
            signal,
            investment_score,
            technical_score,
            quality_score,
            growth_score,
            technical_reasons,
            quality_reasons,
            None,
            None
        )



        # ---------------------------------
        # AI decision
        # ---------------------------------

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
                    growth_score

            }

        )



        # ---------------------------------
        # AI recommendation
        # ---------------------------------

        ai_recommendation = generate_ai_recommendation(

            {

                "Ticker": ticker,

                "Signal": signal,

                "Investment Score":
                    investment_score,

                "Technical Score":
                    technical_score,

                "Quality Score":
                    quality_score,

                "Growth Score":
                    growth_score,

                "Confidence Score":
                    recommendation.get(
                        "Confidence Score",
                        0
                    ),

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



        # ---------------------------------
        # Final intelligence object
        # ---------------------------------

        result = {


            "Ticker":
                ticker,


            "Signal":
                signal,


            "Score":
                technical_score,


            "Technical Score":
                technical_score,


            "Quality Score":
                quality_score,


            "Growth Score":
                growth_score,


            "Investment Score":
                investment_score,



            "Confidence":
                recommendation.get(
                    "Confidence",
                    "Unknown"
                ),


            "Confidence Score":
                recommendation.get(
                    "Confidence Score",
                    0
                ),



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
                        latest["Return_3m"]
                    )
                    *
                    100,
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
                recommendation.get(
                    "Reasons",
                    []
                ),


            "Recommendation Risks":
                recommendation.get(
                    "Risks",
                    []
                ),



            "Growth Reasons":
                growth_reasons,


            "Growth Risks":
                growth_risks,



            "AI Decision":
                ai_decision.get(
                    "Decision",
                    "REVIEW"
                ),


            "AI Decision Object":
                ai_decision,


            "AI Conviction":
                ai_decision.get(
                    "Conviction",
                    "Unknown"
                ),


            "AI Conviction Score":
                ai_decision.get(
                    "Conviction Score",
                    0
                ),



            "AI Summary":
                ai_recommendation.get(
                    "Summary",
                    ""
                ),


            "AI Investment Thesis":
                ai_recommendation.get(
                    "Investment Thesis",
                    []
                ),


            "AI Strengths":
                ai_recommendation.get(
                    "Strengths",
                    []
                ),


            "AI Risks":
                ai_recommendation.get(
                    "Risks",
                    []
                ),


            "AI Action":
                ai_decision.get(
                    "Recommended Action",
                    []
                ),


            "AI Review Triggers":
                ai_decision.get(
                    "Review Triggers",
                    []
                )

        }



        return result



    except Exception as e:


        print(
            f"STOCK ANALYSIS FAILED {ticker}: {e}"
        )

        traceback.print_exc()

        return None