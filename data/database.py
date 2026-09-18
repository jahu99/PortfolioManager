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
# AUDIT DATABASE
# =====================================================

def initialise_audit_database():
    """
    Initialise the Epic 1 decision audit tables.

    Responsibilities:

        - Store audit execution/run records.
        - Store one audit decision record per security.
        - Store all reasons contributing to an action change.
        - Preserve quantitative actual/threshold values where
          available.
        - Maintain indexes used by audit reporting.

    Audit data is historical and should not be overwritten when
    decision logic is subsequently corrected.
    """

    conn = get_connection()
    cursor = conn.cursor()

    # -------------------------------------------------
    # Audit runs
    # -------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_runs
        (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            run_id TEXT NOT NULL UNIQUE,

            run_date TEXT NOT NULL,

            environment TEXT NOT NULL
                CHECK (
                    environment IN (
                        'pre-production',
                        'production'
                    )
                ),

            code_version TEXT,

            status TEXT NOT NULL DEFAULT 'RUNNING'
                CHECK (
                    status IN (
                        'RUNNING',
                        'COMPLETED',
                        'FAILED'
                    )
                ),

            total_decisions INTEGER DEFAULT 0,

            changed_decisions INTEGER DEFAULT 0,

            created_at TEXT NOT NULL
        )
        """
    )

    # -------------------------------------------------
    # Audit decisions
    # -------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_decisions
        (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            audit_run_id INTEGER NOT NULL,

            ticker TEXT NOT NULL,

            recommendation_id INTEGER,

            asset_type TEXT,

            original_action TEXT,

            proposed_action TEXT,

            reconciled_action TEXT,

            final_action TEXT NOT NULL,

            action_changed INTEGER NOT NULL DEFAULT 0
                CHECK (
                    action_changed IN (0, 1)
                ),

            original_signal TEXT,

            investment_score REAL,

            technical_score REAL,

            quality_score REAL,

            growth_score REAL,

            confidence_score REAL,

            evidence_score REAL,

            original_allocation_pct REAL,

            final_allocation_pct REAL,

            reconciliation_status TEXT,

            decision_stage TEXT,

            source_module TEXT,

            created_at TEXT NOT NULL,

            FOREIGN KEY (audit_run_id)
                REFERENCES audit_runs(id)
        )
        """
    )

    # -------------------------------------------------
    # Backward-compatible audit_decisions migration
    # -------------------------------------------------

    cursor.execute(
        "PRAGMA table_info(audit_decisions)"
    )

    audit_decision_columns = {
        row[1]
        for row in cursor.fetchall()
    }

    if "recommendation_id" not in audit_decision_columns:

        cursor.execute(
            """
            ALTER TABLE audit_decisions
            ADD COLUMN recommendation_id INTEGER
            """
        )

    # -------------------------------------------------
    # Audit reasons
    # -------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_reasons
        (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            audit_decision_id INTEGER NOT NULL,

            reason_code TEXT NOT NULL,

            reason_category TEXT NOT NULL,

            reason_description TEXT,

            actual_value TEXT,

            threshold_value TEXT,

            unit TEXT,

            severity TEXT DEFAULT 'MATERIAL'
                CHECK (
                    severity IN (
                        'INFO',
                        'WARNING',
                        'MATERIAL'
                    )
                ),

            source_layer TEXT,

            created_at TEXT NOT NULL,

            FOREIGN KEY (audit_decision_id)
                REFERENCES audit_decisions(id)
        )
        """
    )

    # -------------------------------------------------
    # Audit indexes
    # -------------------------------------------------

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_audit_runs_run_id
        ON audit_runs(run_id)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_audit_decisions_run
        ON audit_decisions(audit_run_id)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_audit_decisions_ticker
        ON audit_decisions(ticker)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_audit_decisions_changed
        ON audit_decisions(action_changed)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_audit_reasons_decision
        ON audit_reasons(audit_decision_id)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_audit_reasons_code
        ON audit_reasons(reason_code)
        """
    )

    conn.commit()
    conn.close()


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
    #
    # Entry Quality fields are SHADOW MODE telemetry only.
    # They do not influence recommendation decisions.
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

            extension_sma50_pct REAL,

            extension_sma200_pct REAL,

            return_5d_pct REAL,

            return_10d_pct REAL,

            return_20d_pct REAL,

            entry_quality TEXT,

            entry_quality_mode TEXT,

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

            FOREIGN KEY(recommendation_id)
                REFERENCES recommendations(id),

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
    # Check recommendation evidence columns
    # -------------------------------------------------

    cursor.execute(
        "PRAGMA table_info(recommendation_evidence)"
    )

    recommendation_evidence_columns = {
        row[1]
        for row in cursor.fetchall()
    }

    # -------------------------------------------------
    # Add missing recommendation evidence columns
    #
    # This makes the migration safe for:
    #
    #   1. New databases
    #   2. Existing databases
    #   3. The current database where the seven
    #      columns have already been added manually
    # -------------------------------------------------

    missing_recommendation_evidence_columns = {

        "extension_sma50_pct":
            "REAL",

        "extension_sma200_pct":
            "REAL",

        "return_5d_pct":
            "REAL",

        "return_10d_pct":
            "REAL",

        "return_20d_pct":
            "REAL",

        "entry_quality":
            "TEXT",

        "entry_quality_mode":
            "TEXT"

    }

    for column, data_type in (
        missing_recommendation_evidence_columns.items()
    ):

        if column not in recommendation_evidence_columns:

            cursor.execute(
                f"""
                ALTER TABLE recommendation_evidence
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
def backfill_entry_quality_evidence(
    cursor,
    recommendation_id,
    stock,
):
    """
    Backfill Entry Quality telemetry for an existing
    recommendation_evidence snapshot when those fields
    are missing.

    Existing populated evidence is preserved.
    """

    cursor.execute(
        """
        SELECT
            id,
            entry_quality
        FROM recommendation_evidence
        WHERE recommendation_id = ?
        """,
        (
            recommendation_id,
        )
    )

    existing_evidence = cursor.fetchone()

    if not existing_evidence:
        return None

    evidence_id, existing_entry_quality = existing_evidence

    if (
        existing_entry_quality is not None
        and str(existing_entry_quality).strip() != ""
    ):
        return False

    entry_quality = stock.get("Entry Quality")

    if entry_quality in (None, ""):
        return False

    cursor.execute(
        """
        UPDATE recommendation_evidence
        SET
            entry_quality = ?,
            entry_quality_mode = ?,
            extension_sma50_pct = ?,
            extension_sma200_pct = ?,
            return_5d_pct = ?,
            return_10d_pct = ?,
            return_20d_pct = ?
        WHERE id = ?
        """,
        (
            entry_quality,
            stock.get("Entry Quality Mode"),
            stock.get("Extension SMA50 %"),
            stock.get("Extension SMA200 %"),
            stock.get("Return 5D %"),
            stock.get("Return 10D %"),
            stock.get("Return 20D %"),
            evidence_id,
        )
    )

    return True



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

    Entry Quality
    -------------
    Entry Quality fields are persisted as SHADOW MODE telemetry.
    They do not influence BUY NEW, BUY MORE, HOLD, REDUCE or SELL
    decisions.
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
                # Existing evidence snapshot
                # ---------------------------------------------

                entry_quality_backfill = (
                    backfill_entry_quality_evidence(
                        cursor=cursor,
                        recommendation_id=recommendation_id,
                        stock=stock,
                    )
                )

                if entry_quality_backfill is True:
                    evidence_saved += 1
                    continue

                if entry_quality_backfill is False:
                    continue

                # No evidence exists.
                # Fall through to the full evidence INSERT below.

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

                        extension_sma50_pct,
                        extension_sma200_pct,
                        return_5d_pct,
                        return_10d_pct,
                        return_20d_pct,
                        entry_quality,
                        entry_quality_mode,

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

                        ?, ?, ?, ?, ?, ?, ?,

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
                            stock.get(
                                "3M Return %",
                                0
                            )
                        ),

                        stock.get(
                            "Extension SMA50 %"
                        ),

                        stock.get(
                            "Extension SMA200 %"
                        ),

                        stock.get(
                            "Return 5D %"
                        ),

                        stock.get(
                            "Return 10D %"
                        ),

                        stock.get(
                            "Return 20D %"
                        ),

                        stock.get(
                            "Entry Quality"
                        ),

                        stock.get(
                            "Entry Quality Mode"
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

                    extension_sma50_pct,
                    extension_sma200_pct,
                    return_5d_pct,
                    return_10d_pct,
                    return_20d_pct,
                    entry_quality,
                    entry_quality_mode,

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

                    ?, ?, ?, ?, ?, ?, ?,

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
                        stock.get(
                            "3M Return %",
                            0
                        )
                    ),

                    stock.get(
                        "Extension SMA50 %"
                    ),

                    stock.get(
                        "Extension SMA200 %"
                    ),

                    stock.get(
                        "Return 5D %"
                    ),

                    stock.get(
                        "Return 10D %"
                    ),

                    stock.get(
                        "Return 20D %"
                    ),

                    stock.get(
                        "Entry Quality"
                    ),

                    stock.get(
                        "Entry Quality Mode"
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

        # -------------------------------------------------
        # Epic 1: Decision audit database
        # -------------------------------------------------

        initialise_audit_database()

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

def get_recommendation_evidence(
    recommendation_id
):
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
            (
                recommendation_id,
            )
        )

        row = cursor.fetchone()

        if row is None:
            return None

        columns = [
            description[0]
            for description in cursor.description
        ]

        result = dict(
            zip(
                columns,
                row
            )
        )

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

            value = result.get(
                field
            )

            if not value:

                result[field] = []

                continue

            try:

                result[field] = json.loads(
                    value
                )

            except Exception:

                result[field] = [
                    value
                ]

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
                .strftime(
                    "%Y-%m-%d"
                )
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