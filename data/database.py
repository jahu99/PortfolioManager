"""
Recommendation database management.

Responsibilities:
    - Store daily stock recommendations.
    - Retrieve open recommendations.
    - Store forward performance evaluations.
    - Prevent duplicate evaluations.
    - Calculate recommendation-adjusted returns.
    - Calculate recommendation success.
    - Mark recommendations as evaluated after 5D evaluation.
    - Maintain backward compatibility with the existing database.

Database:
    data/portfolio_manager.db
"""

import sqlite3
import os
import json
import pandas as pd
from datetime import datetime

from data.market_calendar import get_last_trading_day


# =====================================================
# DATABASE
# =====================================================

DATABASE_PATH = os.path.join(
    os.path.dirname(__file__),
    "portfolio_manager.db"
)


# =====================================================
# CONNECTION
# =====================================================

def get_connection():

    return sqlite3.connect(
        DATABASE_PATH
    )


# =====================================================
# INITIALISE DATABASE
# =====================================================

def initialise_database():

    conn = get_connection()
    cursor = conn.cursor()

    # -------------------------------------------------
    # Recommendations table
    # -------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS recommendations
        (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            date TEXT NOT NULL,

            ticker TEXT NOT NULL,

            signal TEXT,

            investment_score INTEGER,

            technical_score INTEGER,

            quality_score INTEGER,

            growth_score INTEGER,

            price REAL,

            confidence TEXT,

            confidence_score REAL,

            confidence_reasons TEXT,

            evaluated INTEGER DEFAULT 0
        )
        """
    )

    # -------------------------------------------------
    # Recommendation evidence snapshot table
    #
    # Stores the evidence available when a recommendation was
    # created. Kept separate from recommendations for backwards
    # compatibility with all existing consumers.
    # -------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS recommendation_evidence
        (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recommendation_id INTEGER NOT NULL,
            ticker TEXT,
            capture_date TEXT,
            signal TEXT,
            investment_score REAL,
            technical_score REAL,
            quality_score REAL,
            growth_score REAL,
            confidence_score REAL,
            entry_price REAL,
            rsi REAL,
            sma50 REAL,
            sma200 REAL,
            return_3m REAL,
            trend TEXT,
            trend_score REAL,
            momentum_score REAL,
            volume_score REAL,
            risk_score REAL,
            revenue_growth REAL,
            profit_margin REAL,
            return_on_equity REAL,
            debt_to_equity REAL,
            sector TEXT,
            industry TEXT,
            technical_reasons TEXT,
            technical_risks TEXT,
            recommendation_reasons TEXT,
            recommendation_risks TEXT,
            ai_decision TEXT,
            ai_conviction TEXT,
            ai_conviction_score REAL,
            ai_action TEXT,
            ai_investment_thesis TEXT,
            ai_risks TEXT,
            FOREIGN KEY(recommendation_id) REFERENCES recommendations(id),
            UNIQUE(recommendation_id)
        )
        """
    )

    # -------------------------------------------------
    # Recommendation evaluations table
    # -------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS recommendation_evaluations
        (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            recommendation_id INTEGER,

            ticker TEXT,

            signal TEXT,

            evaluation_date TEXT,

            days_after INTEGER,

            price REAL,

            return_percent REAL,

            recommendation_return_percent REAL,

            recommendation_success INTEGER,

            outcome TEXT,

            investment_score INTEGER,

            technical_score INTEGER,

            quality_score INTEGER,

            growth_score INTEGER,

            confidence_score REAL,

            FOREIGN KEY(
                recommendation_id
            )
            REFERENCES recommendations(id),

            UNIQUE(
                recommendation_id,
                days_after
            )
        )
        """
    )

    # =================================================
    # DATABASE MIGRATIONS
    # =================================================

    # -------------------------------------------------
    # Check recommendations columns
    # -------------------------------------------------

    cursor.execute(
        "PRAGMA table_info(recommendations)"
    )

    recommendation_columns = {
        row[1]
        for row in cursor.fetchall()
    }

    # -------------------------------------------------
    # Add missing recommendation columns
    # -------------------------------------------------

    missing_recommendation_columns = {

        "growth_score":
            "INTEGER",

        "confidence":
            "TEXT",

        "confidence_score":
            "REAL",

        "confidence_reasons":
            "TEXT",

        "evaluated":
            "INTEGER DEFAULT 0"

    }

    for column, data_type in (
        missing_recommendation_columns.items()
    ):

        if column not in recommendation_columns:

            cursor.execute(
                f"""
                ALTER TABLE recommendations
                ADD COLUMN {column} {data_type}
                """
            )

    # -------------------------------------------------
    # Check evaluation columns
    # -------------------------------------------------

    cursor.execute(
        "PRAGMA table_info(recommendation_evaluations)"
    )

    evaluation_columns = {
        row[1]
        for row in cursor.fetchall()
    }

    # -------------------------------------------------
    # Add missing evaluation columns
    # -------------------------------------------------

    missing_evaluation_columns = {

        "ticker":
            "TEXT",

        "signal":
            "TEXT",

        "investment_score":
            "INTEGER",

        "technical_score":
            "INTEGER",

        "quality_score":
            "INTEGER",

        "growth_score":
            "INTEGER",

        "confidence_score":
            "REAL",

        "recommendation_return_percent":
            "REAL",

        "recommendation_success":
            "INTEGER"

    }

    for column, data_type in (
        missing_evaluation_columns.items()
    ):

        if column not in evaluation_columns:

            cursor.execute(
                f"""
                ALTER TABLE recommendation_evaluations
                ADD COLUMN {column} {data_type}
                """
            )

    # -------------------------------------------------
    # Commit migrations
    # -------------------------------------------------

    conn.commit()
    conn.close()

    print(
        "Database initialised"
    )


# =====================================================
# SAVE RECOMMENDATIONS
# =====================================================

# =====================================================
# SAVE RECOMMENDATIONS
# =====================================================

def save_recommendations(
    stock_results
):
    """
    Save the daily stock recommendations.

    Existing behaviour
    ------------------
    Only one recommendation set is saved per trading day.
    Existing recommendation rows are never duplicated.

    Recommendation evidence
    ------------------------
    Each recommendation also has an immutable evidence snapshot
    stored in:

        recommendation_evidence

    For an existing daily recommendation run, the function will
    backfill a missing evidence snapshot without creating a new
    recommendation row.

    This keeps the existing recommendations table and downstream
    logic backwards compatible.
    """

    if not stock_results:
        return

    conn = get_connection()
    cursor = conn.cursor()

    try:

        # -------------------------------------------------
        # Determine trading date
        # -------------------------------------------------

        today = get_last_trading_day(
            "SPY",
            datetime.today().strftime(
                "%Y-%m-%d"
            )
        )

        # -------------------------------------------------
        # Determine whether today's recommendations already
        # exist.
        # -------------------------------------------------

        cursor.execute(
            """
            SELECT
                id,
                ticker

            FROM recommendations

            WHERE date = ?
            """,
            (
                today,
            )
        )

        existing_rows = cursor.fetchall()

        existing_recommendations = {

            str(
                row[1]
            ).strip().upper():

                row[0]

            for row in existing_rows

            if row[1]
        }

        if existing_recommendations:

            print(
                "Recommendations already saved for today"
            )

        # -------------------------------------------------
        # Counters
        # -------------------------------------------------

        saved = 0
        evidence_saved = 0

        # -------------------------------------------------
        # Process each stock result
        # -------------------------------------------------

        for stock in stock_results:

            ticker = str(
                stock.get(
                    "Ticker",
                    ""
                )
            ).strip().upper()

            if not ticker:
                continue

            # =================================================
            # EXISTING RECOMMENDATION
            # =================================================

            if ticker in existing_recommendations:

                recommendation_id = (
                    existing_recommendations[
                        ticker
                    ]
                )

                # ---------------------------------------------
                # Check whether evidence snapshot already exists
                # ---------------------------------------------

                cursor.execute(
                    """
                    SELECT COUNT(*)

                    FROM recommendation_evidence

                    WHERE recommendation_id = ?
                    """,
                    (
                        recommendation_id,
                    )
                )

                evidence_exists = (
                    cursor.fetchone()[0] > 0
                )

                if evidence_exists:

                    continue

                # ---------------------------------------------
                # Backfill missing evidence snapshot
                # ---------------------------------------------

                cursor.execute(
                    """
                    INSERT OR IGNORE INTO recommendation_evidence
                    (
                        recommendation_id,
                        ticker,
                        capture_date,

                        signal,

                        investment_score,
                        technical_score,
                        quality_score,
                        growth_score,
                        confidence_score,

                        entry_price,
                        rsi,
                        sma50,
                        sma200,
                        return_3m,

                        trend,
                        trend_score,
                        momentum_score,
                        volume_score,
                        risk_score,

                        revenue_growth,
                        profit_margin,
                        return_on_equity,
                        debt_to_equity,

                        sector,
                        industry,

                        technical_reasons,
                        technical_risks,
                        recommendation_reasons,
                        recommendation_risks,

                        ai_decision,
                        ai_conviction,
                        ai_conviction_score,
                        ai_action,
                        ai_investment_thesis,
                        ai_risks
                    )

                    VALUES (
                        ?, ?, ?,
                        ?,
                        ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?,
                        ?, ?, ?, ?,
                        ?, ?,
                        ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?
                    )
                    """,
                    (
                        recommendation_id,

                        ticker,

                        today,

                        stock.get(
                            "Signal",
                            ""
                        ),

                        stock.get(
                            "Investment Score",
                            0
                        ),

                        stock.get(
                            "Technical Score",
                            0
                        ),

                        stock.get(
                            "Quality Score",
                            0
                        ),

                        stock.get(
                            "Growth Score",
                            0
                        ),

                        stock.get(
                            "Confidence Score",
                            0
                        ),

                        stock.get(
                            "Price",
                            0
                        ),

                        stock.get(
                            "RSI",
                            0
                        ),

                        stock.get(
                            "SMA50",
                            0
                        ),

                        stock.get(
                            "SMA200",
                            0
                        ),

                        stock.get(
                            "Return_3m",
                            0
                        ),

                        stock.get(
                            "Trend",
                            ""
                        ),

                        stock.get(
                            "Trend Score",
                            0
                        ),

                        stock.get(
                            "Momentum Score",
                            0
                        ),

                        stock.get(
                            "Volume Score",
                            0
                        ),

                        stock.get(
                            "Risk Score",
                            0
                        ),

                        stock.get(
                            "Revenue Growth",
                            0
                        ),

                        stock.get(
                            "Profit Margin",
                            0
                        ),

                        stock.get(
                            "Return on Equity",
                            0
                        ),

                        stock.get(
                            "Debt to Equity",
                            0
                        ),

                        stock.get(
                            "Sector",
                            ""
                        ),

                        stock.get(
                            "Industry",
                            ""
                        ),

                        json.dumps(
                            stock.get(
                                "Technical Reasons",
                                []
                            ),
                            default=str
                        ),

                        json.dumps(
                            stock.get(
                                "Technical Risks",
                                []
                            ),
                            default=str
                        ),

                        json.dumps(
                            stock.get(
                                "Recommendation Reasons",
                                []
                            ),
                            default=str
                        ),

                        json.dumps(
                            stock.get(
                                "Recommendation Risks",
                                []
                            ),
                            default=str
                        ),

                        stock.get(
                            "AI Decision",
                            ""
                        ),

                        stock.get(
                            "AI Conviction",
                            ""
                        ),

                        stock.get(
                            "AI Conviction Score",
                            0
                        ),

                        json.dumps(
                            stock.get(
                                "AI Action",
                                []
                            ),
                            default=str
                        ),

                        json.dumps(
                            stock.get(
                                "AI Investment Thesis",
                                []
                            ),
                            default=str
                        ),

                        json.dumps(
                            stock.get(
                                "AI Risks",
                                []
                            ),
                            default=str
                        ),
                    )
                )

                if cursor.rowcount > 0:

                    evidence_saved += 1

                continue

            # =================================================
            # NEW RECOMMENDATION
            # =================================================

            cursor.execute(
                """
                INSERT INTO recommendations
                (
                    date,
                    ticker,
                    signal,
                    investment_score,
                    technical_score,
                    quality_score,
                    growth_score,
                    price,
                    confidence,
                    confidence_score,
                    confidence_reasons,
                    evaluated
                )

                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0
                )
                """,
                (

                    today,

                    ticker,

                    stock.get(
                        "Signal",
                        ""
                    ),

                    stock.get(
                        "Investment Score",
                        0
                    ),

                    stock.get(
                        "Technical Score",
                        0
                    ),

                    stock.get(
                        "Quality Score",
                        0
                    ),

                    stock.get(
                        "Growth Score",
                        0
                    ),

                    stock.get(
                        "Price",
                        0
                    ),

                    stock.get(
                        "Confidence",
                        ""
                    ),

                    stock.get(
                        "Confidence Score",
                        0
                    ),

                    str(
                        stock.get(
                            "Confidence Reasons",
                            []
                        )
                    )

                )
            )

            recommendation_id = (
                cursor.lastrowid
            )

            # ---------------------------------------------
            # Save immutable evidence snapshot
            # ---------------------------------------------

            cursor.execute(
                """
                INSERT INTO recommendation_evidence
                (
                    recommendation_id,
                    ticker,
                    capture_date,

                    signal,

                    investment_score,
                    technical_score,
                    quality_score,
                    growth_score,
                    confidence_score,

                    entry_price,
                    rsi,
                    sma50,
                    sma200,
                    return_3m,

                    trend,
                    trend_score,
                    momentum_score,
                    volume_score,
                    risk_score,

                    revenue_growth,
                    profit_margin,
                    return_on_equity,
                    debt_to_equity,

                    sector,
                    industry,

                    technical_reasons,
                    technical_risks,
                    recommendation_reasons,
                    recommendation_risks,

                    ai_decision,
                    ai_conviction,
                    ai_conviction_score,
                    ai_action,
                    ai_investment_thesis,
                    ai_risks
                )

                VALUES (
                    ?, ?, ?,
                    ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?
                )
                """,
                (

                    recommendation_id,

                    ticker,

                    today,

                    stock.get(
                        "Signal",
                        ""
                    ),

                    stock.get(
                        "Investment Score",
                        0
                    ),

                    stock.get(
                        "Technical Score",
                        0
                    ),

                    stock.get(
                        "Quality Score",
                        0
                    ),

                    stock.get(
                        "Growth Score",
                        0
                    ),

                    stock.get(
                        "Confidence Score",
                        0
                    ),

                    stock.get(
                        "Price",
                        0
                    ),

                    stock.get(
                        "RSI",
                        0
                    ),

                    stock.get(
                        "SMA50",
                        0
                    ),

                    stock.get(
                        "SMA200",
                        0
                    ),

                    stock.get(
                        "Return_3m",
                        0
                    ),

                    stock.get(
                        "Trend",
                        ""
                    ),

                    stock.get(
                        "Trend Score",
                        0
                    ),

                    stock.get(
                        "Momentum Score",
                        0
                    ),

                    stock.get(
                        "Volume Score",
                        0
                    ),

                    stock.get(
                        "Risk Score",
                        0
                    ),

                    stock.get(
                        "Revenue Growth",
                        0
                    ),

                    stock.get(
                        "Profit Margin",
                        0
                    ),

                    stock.get(
                        "Return on Equity",
                        0
                    ),

                    stock.get(
                        "Debt to Equity",
                        0
                    ),

                    stock.get(
                        "Sector",
                        ""
                    ),

                    stock.get(
                        "Industry",
                        ""
                    ),

                    json.dumps(
                        stock.get(
                            "Technical Reasons",
                            []
                        ),
                        default=str
                    ),

                    json.dumps(
                        stock.get(
                            "Technical Risks",
                            []
                        ),
                        default=str
                    ),

                    json.dumps(
                        stock.get(
                            "Recommendation Reasons",
                            []
                        ),
                        default=str
                    ),

                    json.dumps(
                        stock.get(
                            "Recommendation Risks",
                            []
                        ),
                        default=str
                    ),

                    stock.get(
                        "AI Decision",
                        ""
                    ),

                    stock.get(
                        "AI Conviction",
                        ""
                    ),

                    stock.get(
                        "AI Conviction Score",
                        0
                    ),

                    json.dumps(
                        stock.get(
                            "AI Action",
                            []
                        ),
                        default=str
                    ),

                    json.dumps(
                        stock.get(
                            "AI Investment Thesis",
                            []
                        ),
                        default=str
                    ),

                    json.dumps(
                        stock.get(
                            "AI Risks",
                            []
                        ),
                        default=str
                    ),
                )
            )

            saved += 1
            evidence_saved += 1

        # -------------------------------------------------
        # Commit recommendation/evidence changes together
        # -------------------------------------------------

        conn.commit()

        print(
            f"Saved {saved} new recommendations"
        )

        print(
            f"Saved {evidence_saved} recommendation evidence snapshots"
        )

    except Exception:

        conn.rollback()
        raise

    finally:

        conn.close()

# =====================================================
# GET RECOMMENDATION EVIDENCE
# =====================================================

def get_recommendation_evidence(recommendation_id):
    """
    Return the immutable evidence snapshot for a recommendation.

    Returns None for historical recommendations created before
    recommendation_evidence was introduced.
    """

    conn = get_connection()

    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT *
            FROM recommendation_evidence
            WHERE recommendation_id = ?
            """,
            (recommendation_id,)
        )

        row = cursor.fetchone()

        if row is None:
            return None

        columns = [
            description[0]
            for description in cursor.description
        ]

        result = dict(zip(columns, row))

        json_fields = [
            "technical_reasons",
            "technical_risks",
            "recommendation_reasons",
            "recommendation_risks",
            "ai_action",
            "ai_investment_thesis",
            "ai_risks",
        ]

        for field in json_fields:
            value = result.get(field)
            if not value:
                result[field] = []
                continue
            try:
                result[field] = json.loads(value)
            except Exception:
                result[field] = [value]

        return result

    finally:
        conn.close()


# =====================================================
# GET OPEN RECOMMENDATIONS
# =====================================================

def get_open_recommendations():

    """
    Return recommendations that have not yet completed
    their primary 5-day evaluation.
    """

    conn = get_connection()

    query = """
        SELECT
            id,
            date,
            ticker,
            signal,
            investment_score,
            technical_score,
            quality_score,
            growth_score,
            price,
            confidence,
            confidence_score,
            confidence_reasons

        FROM recommendations

        WHERE evaluated = 0

        ORDER BY date ASC
    """

    df = pd.read_sql_query(
        query,
        conn
    )

    conn.close()

    return df


# =====================================================
# SAVE RECOMMENDATION EVALUATIONS
# =====================================================

def save_recommendation_evaluations(
    evaluations
):

    """
    Save forward recommendation evaluations.

    Each recommendation can have one evaluation per
    horizon, such as:

        5D
        10D

    The original stock return is retained in:

        return_percent

    A recommendation-adjusted return is calculated in:

        recommendation_return_percent

    Direction handling:

        BUY
        STRONG BUY
        HOLD
        WATCH

            adjusted return = raw stock return

        SELL
        STRONG SELL

            adjusted return = negative raw stock return

    This means:

        BUY +5% stock return
            = +5% recommendation return

        BUY -5% stock return
            = -5% recommendation return

        SELL -5% stock return
            = +5% recommendation return

        SELL +5% stock return
            = -5% recommendation return

    recommendation_success is:

        1 = recommendation direction was correct
        0 = recommendation direction was incorrect

    The recommendations.evaluated flag is set to 1 when
    the 5-day evaluation has been successfully saved.

    10-day evaluations are retained as additional
    learning data and do not change the evaluated flag.
    """

    if evaluations is None:
        return

    if evaluations.empty:
        return

    conn = get_connection()
    cursor = conn.cursor()

    saved = 0

    for _, row in evaluations.iterrows():

        # ---------------------------------------------
        # Recommendation ID
        # ---------------------------------------------

        recommendation_id = row[
            "recommendation_id"
        ]

        # ---------------------------------------------
        # Evaluation horizon
        # ---------------------------------------------

        days_after = int(
            row[
                "days_after"
            ]
        )

        # ---------------------------------------------
        # Prevent duplicate evaluations
        # ---------------------------------------------

        cursor.execute(
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
        )

        exists = cursor.fetchone()[0]

        if exists:

            continue

        # ---------------------------------------------
        # Basic fields
        # ---------------------------------------------

        ticker = row.get(
            "ticker",
            ""
        )

        signal = row.get(
            "Signal",
            row.get(
                "signal",
                ""
            )
        )

        evaluation_date = row.get(
            "evaluation_date"
        )

        if pd.notna(
            evaluation_date
        ):
            evaluation_date = (
                pd.Timestamp(
                    evaluation_date
                )
                .strftime("%Y-%m-%d")
            )
        else:
            evaluation_date = None

        price = row.get(
            "evaluation_price",
            row.get(
                "price",
                0
            )
        )

        outcome = row[
            "outcome"
        ]

        # ---------------------------------------------
        # Raw stock return
        # ---------------------------------------------

        raw_return = row[
            "return_percent"
        ]

        try:

            raw_return = float(
                raw_return
            )

        except (
            TypeError,
            ValueError
        ):

            raw_return = 0.0

        # ---------------------------------------------
        # Normalise signal
        # ---------------------------------------------

        signal_upper = str(
            signal
        ).strip().upper()

        # ---------------------------------------------
        # Recommendation-adjusted return
        # ---------------------------------------------

        if signal_upper in (
            "SELL",
            "STRONG SELL"
        ):

            recommendation_return = (
                -raw_return
            )

        else:

            recommendation_return = (
                raw_return
            )

        # ---------------------------------------------
        # Recommendation success
        # ---------------------------------------------

        recommendation_success = int(
            recommendation_return > 0
        )

        # ---------------------------------------------
        # Insert evaluation
        # ---------------------------------------------

        cursor.execute(
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
                recommendation_return_percent,
                recommendation_success,
                outcome,
                investment_score,
                technical_score,
                quality_score,
                growth_score,
                confidence_score
            )

            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?
            )
            """,
            (

                recommendation_id,

                ticker,

                signal,

                evaluation_date,

                days_after,

                price,

                raw_return,

                recommendation_return,

                recommendation_success,

                outcome,

                row.get(
                    "Investment Score",
                    row.get(
                        "investment_score",
                        0
                    )
                ),

                row.get(
                    "Technical Score",
                    row.get(
                        "technical_score",
                        0
                    )
                ),

                row.get(
                    "Quality Score",
                    row.get(
                        "quality_score",
                        0
                    )
                ),

                row.get(
                    "Growth Score",
                    row.get(
                        "growth_score",
                        0
                    )
                ),

                row.get(
                    "Confidence Score",
                    row.get(
                        "confidence_score",
                        0
                    )
                )

            )
        )

        # ---------------------------------------------
        # Mark recommendation evaluated
        #
        # 5D is the primary evaluation horizon.
        #
        # 10D remains additional learning data.
        # ---------------------------------------------

        if days_after == 5:

            cursor.execute(
                """
                UPDATE recommendations

                SET evaluated = 1

                WHERE id = ?
                """,
                (
                    recommendation_id,
                )
            )

        saved += 1

    # ---------------------------------------------
    # Commit transaction
    # ---------------------------------------------

    conn.commit()
    conn.close()

    print(
        f"Saved {saved} evaluations"
    )


# =====================================================
# BACKFILL RECOMMENDATION-ADJUSTED RETURNS
# =====================================================

def backfill_recommendation_returns():

    """
    Populate recommendation-adjusted returns for
    historical evaluations.

    This is required when upgrading an existing database
    that already contains recommendation evaluations.

    Existing raw return_percent values are never changed.
    """

    conn = get_connection()
    cursor = conn.cursor()

    # -------------------------------------------------
    # Check whether columns exist
    # -------------------------------------------------

    cursor.execute(
        "PRAGMA table_info(recommendation_evaluations)"
    )

    columns = {
        row[1]
        for row in cursor.fetchall()
    }

    if (
        "recommendation_return_percent"
        not in columns
    ):

        cursor.execute(
            """
            ALTER TABLE recommendation_evaluations
            ADD COLUMN recommendation_return_percent REAL
            """
        )

    if (
        "recommendation_success"
        not in columns
    ):

        cursor.execute(
            """
            ALTER TABLE recommendation_evaluations
            ADD COLUMN recommendation_success INTEGER
            """
        )

    # -------------------------------------------------
    # Backfill historical evaluations
    # -------------------------------------------------

    cursor.execute(
        """
        UPDATE recommendation_evaluations

        SET

            recommendation_return_percent =

                CASE

                    WHEN UPPER(
                        TRIM(signal)
                    ) IN (
                        'SELL',
                        'STRONG SELL'
                    )

                    THEN -return_percent

                    ELSE return_percent

                END,

            recommendation_success =

                CASE

                    WHEN

                        CASE

                            WHEN UPPER(
                                TRIM(signal)
                            ) IN (
                                'SELL',
                                'STRONG SELL'
                            )

                            THEN -return_percent

                            ELSE return_percent

                        END > 0

                    THEN 1

                    ELSE 0

                END

        WHERE recommendation_return_percent IS NULL
        """
    )

    updated = cursor.rowcount

    conn.commit()
    conn.close()

    print(
        f"Backfilled {updated} historical evaluations"
    )


# =====================================================
# EVALUATION HISTORY
# =====================================================

def get_evaluation_history():

    """
    Return the complete recommendation evaluation
    history.

    Includes both raw stock returns and
    recommendation-adjusted returns.
    """

    conn = get_connection()

    df = pd.read_sql_query(
        """
        SELECT
            *
        FROM recommendation_evaluations
        ORDER BY evaluation_date DESC
        """,
        conn
    )

    conn.close()

    return df

# =====================================================
# GET LATEST RECOMMENDATION ID
# =====================================================

def get_latest_recommendation_id(
    ticker,
    recommendation_date=None,
):
    """
    Return the recommendation ID for the latest saved
    recommendation for a ticker.

    When recommendation_date is supplied, restrict the lookup
    to that date.

    Returns None when no matching recommendation exists.
    """

    conn = get_connection()

    try:

        cursor = conn.cursor()

        ticker = str(
            ticker
        ).strip().upper()

        if recommendation_date:

            cursor.execute(
                """
                SELECT id
                FROM recommendations
                WHERE UPPER(TRIM(ticker)) = ?
                AND date = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (
                    ticker,
                    recommendation_date,
                )
            )

        else:

            cursor.execute(
                """
                SELECT id
                FROM recommendations
                WHERE UPPER(TRIM(ticker)) = ?
                ORDER BY date DESC, id DESC
                LIMIT 1
                """,
                (
                    ticker,
                )
            )

        row = cursor.fetchone()

        if row is None:
            return None

        return row[0]

    finally:

        conn.close()