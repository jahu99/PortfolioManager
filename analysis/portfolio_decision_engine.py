import pandas as pd


def safe_float(value, default=0.0):

    try:
        if pd.isna(value):
            return default

        return float(value)

    except Exception:

        return default



def normalise_text(value, default="UNKNOWN"):

    if value is None:
        return default

    value = str(value).strip()

    if value == "":
        return default

    return value.upper()



# =====================================================
# BUY APPROVAL
# =====================================================

def approve_buy(
    investment_score,
    conviction,
    allocation,
    portfolio_risk,
    sector_allocation
):

    if investment_score < 75:
        return False

    if conviction not in [
        "HIGH",
        "VERY HIGH"
    ]:
        return False

    if allocation >= 10:
        return False

    if portfolio_risk == "HIGH":
        return False

    if sector_allocation >= 30:
        return False

    return True



# =====================================================
# PORTFOLIO DECISION ENGINE
# =====================================================

def generate_portfolio_decisions(
    portfolio_summary,
    opportunities=None
):


    if portfolio_summary is None:

        portfolio_summary = pd.DataFrame()



    if opportunities is None:

        opportunities = pd.DataFrame()



    decisions = []



    # -------------------------------------------------
    # Create intelligence lookup
    # -------------------------------------------------

    intelligence = {}


    if isinstance(opportunities, pd.DataFrame):

        if "Ticker" in opportunities.columns:

            opportunities["Ticker"] = (
                opportunities["Ticker"]
                .astype(str)
                .str.upper()
            )


            intelligence = (
                opportunities
                .set_index("Ticker")
                .to_dict("index")
            )



    # -------------------------------------------------
    # Existing holdings
    # -------------------------------------------------

    if (
        isinstance(portfolio_summary, pd.DataFrame)
        and
        "Ticker" in portfolio_summary.columns
    ):


        portfolio_summary["Ticker"] = (

            portfolio_summary["Ticker"]
            .astype(str)
            .str.upper()

        )


        for _, row in portfolio_summary.iterrows():


            ticker = row["Ticker"]


            # Merge intelligence data if available

            stock_info = intelligence.get(
                ticker,
                {}
            )


            investment_score = safe_float(
                stock_info.get(
                    "Investment Score",
                    row.get(
                        "Investment Score",
                        0
                    )
                )
            )


            quality_score = safe_float(
                stock_info.get(
                    "Quality Score",
                    row.get(
                        "Quality Score",
                        0
                    )
                )
            )


            growth_score = safe_float(
                stock_info.get(
                    "Growth Score",
                    row.get(
                        "Growth Score",
                        0
                    )
                )
            )


            signal = stock_info.get(
                "Signal",
                row.get(
                    "Signal",
                    "UNKNOWN"
                )
            )


            conviction = normalise_text(
                stock_info.get(
                    "AI Conviction",
                    row.get(
                        "AI Conviction",
                        "MEDIUM"
                    )
                )
            )


            allocation = safe_float(
                row.get(
                    "Allocation %",
                    0
                )
            )


            sector = row.get(
                "Sector",
                "Unknown"
            )


            sector_allocation = safe_float(
                row.get(
                    "Sector Allocation %",
                    0
                )
            )


            portfolio_risk = normalise_text(
                row.get(
                    "Portfolio Risk",
                    "NORMAL"
                )
            )



            # -----------------------------
            # Decision rules
            # -----------------------------

            if investment_score >= 85:

                action = "HOLD"

                reason = (
                    "High quality holding "
                    "meeting portfolio criteria"
                )


            elif investment_score >= 70:

                action = "REVIEW"

                reason = (
                    "Moderate score - monitor performance"
                )


            elif investment_score >= 50:

                action = "REDUCE"

                reason = (
                    "Weakening investment profile"
                )


            else:

                action = "REDUCE"

                reason = (
                    "Investment score below threshold"
                )



            decisions.append(

                {

                    "Ticker": ticker,

                    "Action": action,

                    "Reason": reason,

                    "Investment Score": investment_score,

                    "Quality Score": quality_score,

                    "Growth Score": growth_score,

                    "Signal": signal,

                    "AI Conviction": conviction,

                    "Allocation %": allocation,

                    "Sector": sector,

                    "Sector Allocation %": sector_allocation,

                    "Portfolio Risk": portfolio_risk

                }

            )



    # -------------------------------------------------
    # New opportunities
    # -------------------------------------------------

    if isinstance(opportunities, pd.DataFrame):

        for _, stock in opportunities.iterrows():


            ticker = str(
                stock.get(
                    "Ticker",
                    ""
                )
            ).upper()


            if not ticker:
                continue



            if ticker in [
                d["Ticker"]
                for d in decisions
            ]:
                continue



            investment_score = safe_float(
                stock.get(
                    "Investment Score",
                    0
                )
            )


            conviction = normalise_text(
                stock.get(
                    "AI Conviction",
                    "UNKNOWN"
                )
            )


            if approve_buy(

                investment_score,

                conviction,

                0,

                "NORMAL",

                safe_float(
                    stock.get(
                        "Sector Allocation %",
                        0
                    )
                )

            ):


                decisions.append(

                    {

                        "Ticker": ticker,

                        "Action": "BUY",

                        "Reason":
                            "High conviction opportunity",

                        "Investment Score":
                            investment_score,

                        "Quality Score":
                            safe_float(
                                stock.get(
                                    "Quality Score",
                                    0
                                )
                            ),

                        "Growth Score":
                            safe_float(
                                stock.get(
                                    "Growth Score",
                                    0
                                )
                            ),

                        "Signal":
                            stock.get(
                                "Signal",
                                ""
                            ),

                        "AI Conviction":
                            conviction,

                        "Sector":
                            stock.get(
                                "Sector",
                                "Unknown"
                            )

                    }

                )



    result = pd.DataFrame(decisions)


    if not result.empty:

        result = result.drop_duplicates(
            "Ticker"
        )


    print(
        "PORTFOLIO DECISIONS CREATED:",
        result.shape
    )


    return result