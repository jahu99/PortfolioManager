"""Point-in-time observation loader for BUY NEW calibration."""
from __future__ import annotations
from pathlib import Path
import sqlite3
import pandas as pd


def db_path() -> Path:
    return Path(__file__).resolve().parents[1] / 'data' / 'portfolio_manager.db'


def load_recommendations(path: Path | None = None) -> pd.DataFrame:
    query = '''SELECT r.id recommendation_id, r.date recommendation_date, r.ticker, r.signal,
        r.investment_score, r.technical_score, r.quality_score, r.growth_score, r.confidence_score,
        e.capture_date, e.entry_price, e.rsi, e.extension_sma50_pct, e.extension_sma200_pct,
        e.entry_quality, e.entry_quality_mode, e.ai_action, e.ai_conviction, e.ai_conviction_score
        FROM recommendations r LEFT JOIN recommendation_evidence e ON e.recommendation_id=r.id'''
    with sqlite3.connect(path or db_path()) as conn: result = pd.read_sql_query(query, conn)
    result['recommendation_date'] = pd.to_datetime(result['recommendation_date'], errors='coerce', utc=True).dt.tz_localize(None)
    result['capture_date'] = pd.to_datetime(result['capture_date'], errors='coerce', utc=True).dt.tz_localize(None)
    result['ticker'] = result['ticker'].astype(str).str.upper()
    return result


def load_audits(path: Path | None = None) -> pd.DataFrame:
    query = '''SELECT ad.id audit_decision_id, ad.recommendation_id, ad.ticker, ad.final_action,
        ar.run_date audit_date, ar.environment, ar.status
        FROM audit_decisions ad JOIN audit_runs ar ON ar.id=ad.audit_run_id
        WHERE ar.status='COMPLETED' '''
    with sqlite3.connect(path or db_path()) as conn: result = pd.read_sql_query(query, conn)
    result['audit_date'] = pd.to_datetime(result['audit_date'], errors='coerce', utc=True).dt.tz_localize(None)
    result['ticker'] = result['ticker'].astype(str).str.upper()
    return result


def latest_recommendation(
    history: pd.DataFrame,
    ticker: str,
    t0: pd.Timestamp,
):
    """
    Return the latest recommendation available on the evaluation date.

    The calibration date is treated as a calendar date, so any
    recommendation recorded during T0 is eligible. This avoids
    incorrectly excluding same-day recommendations because their
    timestamp is later than midnight.

    No look-ahead is permitted: recommendations from dates after T0
    are excluded.
    """

    evaluation_date = pd.Timestamp(t0).normalize()
    next_date = evaluation_date + pd.Timedelta(days=1)

    rows = history[
        (history["ticker"] == ticker.upper())
        & history["recommendation_date"].notna()
        & (history["recommendation_date"] < next_date)
    ].copy()

    if rows.empty:
        return None

    return (
        rows.sort_values(
            [
                "recommendation_date",
                "recommendation_id",
            ]
        )
        .iloc[-1]
    )

def latest_audit_action(
    audits: pd.DataFrame,
    ticker: str,
    t0: pd.Timestamp,
):
    """
    Return the latest completed audit action available on T0.

    Same-day audit runs are eligible. Audits after T0 are excluded.
    """

    evaluation_date = pd.Timestamp(t0).normalize()
    next_date = evaluation_date + pd.Timedelta(days=1)

    rows = audits[
        (audits["ticker"] == ticker.upper())
        & audits["audit_date"].notna()
        & (audits["audit_date"] < next_date)
    ].copy()

    if rows.empty:
        return None

    value = (
        rows.sort_values(
            [
                "audit_date",
                "audit_decision_id",
            ]
        )
        .iloc[-1]["final_action"]
    )

    return (
        None
        if pd.isna(value)
        else str(value).strip().upper()
    )