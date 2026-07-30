import pandas as pd

from data.database import get_connection



# ==========================================================
# Recommendation history
# ==========================================================

def get_recommendation_history():

    conn = get_connection()

    query = """
        SELECT *

        FROM recommendations

        ORDER BY date DESC
    """

    df = pd.read_sql_query(
        query,
        conn
    )

    conn.close()

    return df



# ==========================================================
# Overall recommendation performance
# ==========================================================

def get_performance_summary():

    conn = get_connection()

    query = """

        SELECT

            signal AS Signal,

            days_after AS Days_After,

            COUNT(id) AS Evaluations,

            ROUND(
                AVG(return_percent),
                2
            ) AS Average_Return_Percent,


            ROUND(

                SUM(
                    CASE
                        WHEN outcome = 'WIN'
                        THEN 1
                        ELSE 0
                    END
                )
                *
                100.0
                /
                COUNT(id),

                2

            ) AS Win_Rate_Percent


        FROM recommendation_evaluations


        GROUP BY

            signal,
            days_after


        ORDER BY

            days_after ASC

    """

    df = pd.read_sql_query(
        query,
        conn
    )

    conn.close()

    return df



# ==========================================================
# Performance by signal
# ==========================================================

def get_signal_performance():

    conn = get_connection()

    query = """

        SELECT

            signal AS Signal,

            COUNT(id) AS Evaluations,

            ROUND(
                AVG(return_percent),
                2
            ) AS Average_Return_Percent,


            ROUND(

                SUM(
                    CASE
                        WHEN outcome = 'WIN'
                        THEN 1
                        ELSE 0
                    END
                )
                *
                100.0
                /
                COUNT(id),

                2

            ) AS Win_Rate_Percent


        FROM recommendation_evaluations


        GROUP BY signal


        ORDER BY Average_Return_Percent DESC

    """

    df = pd.read_sql_query(
        query,
        conn
    )

    conn.close()

    return df



# ==========================================================
# Performance by evaluation period
# ==========================================================

def get_horizon_performance():

    conn = get_connection()

    query = """

        SELECT

            days_after AS Days_After,

            COUNT(id) AS Evaluations,

            ROUND(
                AVG(return_percent),
                2
            ) AS Average_Return_Percent,


            ROUND(

                SUM(
                    CASE
                        WHEN outcome = 'WIN'
                        THEN 1
                        ELSE 0
                    END
                )
                *
                100.0
                /
                COUNT(id),

                2

            ) AS Win_Rate_Percent


        FROM recommendation_evaluations


        GROUP BY days_after


        ORDER BY days_after ASC

    """

    df = pd.read_sql_query(
        query,
        conn
    )

    conn.close()

    return df



# ==========================================================
# Performance by investment score
# ==========================================================

def get_score_performance():

    conn = get_connection()

    query = """

        SELECT


            CASE

                WHEN r.investment_score >= 90
                THEN '90-100'

                WHEN r.investment_score >= 80
                THEN '80-89'

                WHEN r.investment_score >= 70
                THEN '70-79'

                ELSE '<70'

            END AS Score_Band,


            COUNT(e.id) AS Evaluations,


            ROUND(
                AVG(e.return_percent),
                2
            ) AS Average_Return_Percent,


            ROUND(

                SUM(
                    CASE
                        WHEN e.outcome='WIN'
                        THEN 1
                        ELSE 0
                    END
                )
                *
                100.0
                /
                COUNT(e.id),

                2

            ) AS Win_Rate_Percent


        FROM recommendation_evaluations e


        JOIN recommendations r

        ON e.recommendation_id = r.id


        GROUP BY Score_Band


        ORDER BY Average_Return_Percent DESC

    """

    df = pd.read_sql_query(
        query,
        conn
    )

    conn.close()

    return df



# ==========================================================
# Signal + horizon performance
# ==========================================================

def get_signal_horizon_performance():

    conn = get_connection()

    query = """

        SELECT

            r.signal AS Signal,

            e.days_after AS Days_After,

            COUNT(e.id) AS Evaluations,


            ROUND(
                AVG(e.return_percent),
                2
            ) AS Average_Return_Percent,


            ROUND(

                SUM(
                    CASE
                        WHEN e.outcome='WIN'
                        THEN 1
                        ELSE 0
                    END
                )
                *
                100.0
                /
                COUNT(e.id),

                2

            ) AS Win_Rate_Percent


        FROM recommendation_evaluations e


        JOIN recommendations r

        ON e.recommendation_id = r.id


        GROUP BY

            r.signal,
            e.days_after


        ORDER BY

            r.signal,
            e.days_after

    """

    df = pd.read_sql_query(
        query,
        conn
    )

    conn.close()

    return df



# ==========================================================
# Score + horizon performance
# ==========================================================

def get_score_horizon_performance():

    conn = get_connection()

    query = """

        SELECT


            CASE

                WHEN r.investment_score >= 90
                THEN '90-100'

                WHEN r.investment_score >= 80
                THEN '80-89'

                WHEN r.investment_score >= 70
                THEN '70-79'

                ELSE '<70'

            END AS Score_Band,


            e.days_after AS Days_After,


            COUNT(e.id) AS Evaluations,


            ROUND(
                AVG(e.return_percent),
                2
            ) AS Average_Return_Percent,


            ROUND(

                SUM(
                    CASE
                        WHEN e.outcome='WIN'
                        THEN 1
                        ELSE 0
                    END
                )
                *
                100.0
                /
                COUNT(e.id),

                2

            ) AS Win_Rate_Percent


        FROM recommendation_evaluations e


        JOIN recommendations r

        ON e.recommendation_id = r.id


        GROUP BY

            Score_Band,
            e.days_after


        ORDER BY

            Score_Band,
            e.days_after

    """

    df = pd.read_sql_query(
        query,
        conn
    )

    conn.close()

    return df



# ==========================================================
# Score bucket performance
# ==========================================================

def get_score_bucket_performance():

    conn = get_connection()

    query = """

        SELECT

            r.investment_score,

            e.return_percent


        FROM recommendations r


        JOIN recommendation_evaluations e

        ON r.id = e.recommendation_id

    """

    df = pd.read_sql_query(
        query,
        conn
    )

    conn.close()


    if df.empty:
        return pd.DataFrame()


    def bucket(score):

        if score >= 90:
            return "90-100"

        if score >= 80:
            return "80-89"

        if score >= 70:
            return "70-79"

        if score >= 60:
            return "60-69"

        return "<60"


    df["Score Bucket"] = (
        df["investment_score"]
        .apply(bucket)
    )


    return (

        df.groupby("Score Bucket")

        .agg(

            Evaluations=(
                "return_percent",
                "count"
            ),

            Average_Return_Percent=(
                "return_percent",
                "mean"
            ),

            Win_Rate_Percent=(
                "return_percent",
                lambda x:
                (x > 0).mean()*100
            )

        )

        .reset_index()

    )



# ==========================================================
# Component score performance
# ==========================================================

def get_component_score_performance():

    conn = get_connection()

    query = """

        SELECT

            r.technical_score,

            r.quality_score,

            e.return_percent


        FROM recommendations r


        JOIN recommendation_evaluations e

        ON r.id = e.recommendation_id

    """

    df = pd.read_sql_query(
        query,
        conn
    )

    conn.close()


    if df.empty:
        return pd.DataFrame()


    output=[]


    def bucket(score):

        if score >= 90:
            return "90-100"

        if score >= 80:
            return "80-89"

        if score >= 70:
            return "70-79"

        if score >= 60:
            return "60-69"

        return "<60"


    for name,column in [

        ("Technical Score","technical_score"),

        ("Quality Score","quality_score")

    ]:


        temp=df.copy()

        temp["Score Bucket"] = (
            temp[column]
            .apply(bucket)
        )


        result=(

            temp.groupby("Score Bucket")

            .agg(

                Evaluations=(
                    "return_percent",
                    "count"
                ),

                Average_Return_Percent=(
                    "return_percent",
                    "mean"
                ),

                Win_Rate_Percent=(
                    "return_percent",
                    lambda x:
                    (x>0).mean()*100
                )

            )

            .reset_index()

        )


        result.insert(
            0,
            "Component",
            name
        )


        output.append(result)


    return pd.concat(
        output,
        ignore_index=True
    )

def get_learning_history():

    conn = get_connection()


    query = """

    SELECT

        r.id,

        r.ticker,

        r.signal AS Signal,

        r.investment_score AS "Investment Score",

        e.return_percent AS "Return %",

        e.outcome AS Outcome,

        e.days_after AS "Days After"


    FROM recommendation_evaluations e


    JOIN recommendations r

    ON e.recommendation_id = r.id


    ORDER BY e.evaluation_date DESC

    """


    df = pd.read_sql_query(
        query,
        conn
    )


    conn.close()


    return df