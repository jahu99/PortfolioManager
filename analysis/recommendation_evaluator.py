import pandas as pd
import yfinance as yf

from datetime import datetime

from data.database import get_connection


# ==========================================
# Evaluation checkpoints
# ==========================================

EVALUATION_PERIODS = [
    5,
    10,
    30
]


# ==========================================
# Price helpers
# ==========================================

def get_price_after_days(
    ticker,
    start_date,
    days
):

    try:

        start_date = pd.to_datetime(start_date)


        data = yf.download(
            ticker,
            start=(
                start_date
                -
                pd.Timedelta(days=10)
            ),
            end=(
                start_date
                +
                pd.Timedelta(days=90)
            ),
            progress=False,
            auto_adjust=False
        )


        if data.empty:
            return None


        close = data["Close"]


        if isinstance(close, pd.DataFrame):

            close = close.iloc[:, 0]


        close = (
            close
            .dropna()
            .sort_index()
        )


        entry_dates = (
            close.index[
                close.index <= start_date
            ]
        )


        if len(entry_dates) == 0:

            return None


        entry_date = entry_dates[-1]


        future_prices = close[
            close.index > entry_date
        ]


        if len(future_prices) < days:

            return None


        return float(
            future_prices.iloc[days-1]
        )


    except Exception as e:

        print(
            f"Historical price error {ticker}: {e}"
        )

        return None



# ==========================================
# Outcome
# ==========================================

def calculate_outcome(
    return_percent
):

    if return_percent >= 2:

        return "SUCCESS"


    elif return_percent <= -2:

        return "FAILED"


    return "FLAT"



# ==========================================
# Duplicate check
# ==========================================

def evaluation_exists(
    conn,
    recommendation_id,
    days_after
):

    result = conn.execute(
        """
        SELECT COUNT(*)
        FROM recommendation_evaluations

        WHERE recommendation_id = ?
        AND days_after = ?

        """,
        (
            recommendation_id,
            days_after
        )
    ).fetchone()


    return result[0] > 0



# ==========================================
# Main evaluator
# ==========================================

def evaluate_recommendations():

    print(
        "RECOMMENDATION EVALUATION START"
    )


    conn = get_connection()



    recommendations = pd.read_sql_query(
        """
        SELECT

            id,
            ticker,
            signal,
            date,
            price,

            investment_score,
            technical_score,
            quality_score,
            growth_score,
            confidence_score

        FROM recommendations

        WHERE evaluated = 0

        ORDER BY date ASC

        """,
        conn
    )



    if recommendations.empty:

        print(
            "NO OPEN RECOMMENDATIONS"
        )

        conn.close()

        return



    print(
        "OPEN RECOMMENDATIONS:",
        len(recommendations)
    )



    for _, recommendation in recommendations.iterrows():


        recommendation_id = recommendation["id"]

        ticker = recommendation["ticker"]

        signal = recommendation["signal"]

        entry_price = recommendation["price"]

        recommendation_date = recommendation["date"]



        print(
            f"Evaluating {ticker}"
        )



        print(
            "DEBUG EVALUATOR:",
            ticker,
            recommendation.get("investment_score"),
            recommendation.get("technical_score"),
            recommendation.get("quality_score"),
            recommendation.get("growth_score"),
            recommendation.get("confidence_score")
        )



        all_complete = True



        elapsed_days = (

            datetime.today()
            -
            pd.to_datetime(
                recommendation_date
            )

        ).days



        for days_after in EVALUATION_PERIODS:


            if elapsed_days < days_after:

                all_complete = False

                continue



            if evaluation_exists(
                conn,
                recommendation_id,
                days_after
            ):

                continue



            evaluation_price = get_price_after_days(
                ticker,
                recommendation_date,
                days_after
            )



            if evaluation_price is None:

                print(
                    f"{ticker}: price unavailable for {days_after} days"
                )

                all_complete = False

                continue



            return_percent = (

                (
                    evaluation_price
                    -
                    entry_price
                )
                /
                entry_price

            ) * 100



            outcome = calculate_outcome(
                return_percent
            )



            print(
                f"DEBUG EVALUATION {ticker} "
                f"{days_after} days "
                f"{return_percent:.2f}% "
                f"{outcome}"
            )

            print(
                "INSERT VALUES:",
                recommendation["ticker"],
                recommendation["growth_score"],
                recommendation["confidence_score"]
            )



            conn.execute(
                """
                INSERT INTO recommendation_evaluations
                (

                    recommendation_id,

                    ticker,

                    signal,

                    evaluation_date,

                    days_after,

                    price,

                    return_percent,

                    outcome,

                    investment_score,

                    technical_score,

                    quality_score,

                    growth_score,

                    confidence_score

                )

                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)

                """,

                (

                    recommendation_id,

                    ticker,

                    signal,

                    datetime.today()
                    .strftime(
                        "%Y-%m-%d"
                    ),

                    days_after,

                    evaluation_price,

                    round(
                        return_percent,
                        2
                    ),

                    outcome,

                    recommendation.get(
                        "investment_score",
                        0
                    ),

                    recommendation.get(
                        "technical_score",
                        0
                    ),

                    recommendation.get(
                        "quality_score",
                        0
                    ),

                    recommendation.get(
                        "growth_score",
                        0
                    ),

                    recommendation.get(
                        "confidence_score",
                        0
                    )

                )

            )



        if all_complete:

            conn.execute(
                """
                UPDATE recommendations

                SET evaluated = 1

                WHERE id = ?

                """,

                (
                    recommendation_id,
                )

            )



    conn.commit()

    conn.close()



    print(
        "RECOMMENDATION EVALUATION COMPLETE"
    )