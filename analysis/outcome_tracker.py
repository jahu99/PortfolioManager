import yfinance as yf
import pandas as pd
from datetime import datetime


# -------------------------------------------------
# Get current market price
# -------------------------------------------------

def get_current_price(ticker):

    try:

        data = yf.download(
            ticker,
            period="5d",
            progress=False,
            auto_adjust=True
        )


        if data.empty:
            return None


        # Handle yfinance MultiIndex
        if isinstance(
            data.columns,
            pd.MultiIndex
        ):

            data.columns = (
                data.columns
                .get_level_values(0)
            )


        price = data["Close"].iloc[-1]


        # Handle pandas Series return
        if isinstance(
            price,
            pd.Series
        ):

            price = price.iloc[0]


        return float(price)


    except Exception as e:

        print(
            f"CURRENT PRICE ERROR {ticker}: {e}"
        )

        return None



# -------------------------------------------------
# Calculate recommendation evaluations
# -------------------------------------------------

def calculate_evaluations(recommendations):

    print(
        "OUTCOME EVALUATION START"
    )

    if (
        recommendations is None
        or recommendations.empty
    ):
        return pd.DataFrame()


    evaluations = []


    for _, row in recommendations.iterrows():

        try:

            recommendation_id = row["id"]

            ticker = row["ticker"]

            start_price = float(
                row["price"]
            )

            recommendation_date = row["date"]


            current_price = get_current_price(
                ticker
            )


            if current_price is None:
                continue


            return_pct = round(
                (
                    (
                        current_price
                        -
                        start_price
                    )
                    /
                    start_price
                )
                *
                100,
                2
            )


            rec_date = datetime.strptime(
                recommendation_date,
                "%Y-%m-%d"
            )


            days_after = (
                datetime.today()
                -
                rec_date
            ).days



            if return_pct >= 5:

                outcome = "SUCCESS"


            elif return_pct <= -5:

                outcome = "FAILED"


            else:

                outcome = "FLAT"



            print(
                "DEBUG EVALUATION:",
                ticker,
                start_price,
                current_price,
                return_pct
            )



            evaluations.append(
                {

                    # Database fields
                    "recommendation_id":
                        recommendation_id,

                    "evaluation_date":
                        datetime.today()
                        .strftime("%Y-%m-%d"),

                    "days_after":
                        days_after,

                    "price":
                        current_price,

                    "return_percent":
                        return_pct,

                    "outcome":
                        outcome,


                    # Learning fields
                    "Ticker":
                        ticker,

                    "Signal":
                        row.get(
                            "signal",
                            ""
                        ),

                    "Investment Score":
                        row.get(
                            "investment_score",
                            0
                        ),

                    "Technical Score":
                        row.get(
                            "technical_score",
                            0
                        ),

                    "Quality Score":
                        row.get(
                            "quality_score",
                            0
                        )

                }
            )


        except Exception as e:

            print(
                f"EVALUATION ERROR {row.get('ticker')}: {e}"
            )


    if not evaluations:

        return pd.DataFrame()


    df = pd.DataFrame(
        evaluations
    )


    print(
        "EVALUATIONS CREATED:",
        len(df)
    )


    return df