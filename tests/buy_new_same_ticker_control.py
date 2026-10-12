"""
BUY NEW — SAME-TICKER CONTROL TEST

A6 READ-ONLY INVESTIGATION

Question:
    When the same ticker was evaluated multiple times, did BUY NEW
    produce worse subsequent 5D outcomes than non-BUY-NEW decisions
    for that same company?

Purpose:
    Distinguish between:
        A) BUY NEW selecting the wrong companies
        B) BUY NEW selecting companies at the wrong time
        C) ticker concentration / repeated selection effects

This test:
    - uses governed audit decisions as the source of final actions
    - reconstructs legacy recommendation lineage deterministically
    - preserves audit-decision observations
    - uses mature 5D outcomes
    - compares BUY NEW against non-BUY-NEW observations
      within the same ticker
    - does NOT modify production logic
    - does NOT change thresholds, weights, or governance

No production changes are made.
"""

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd


# ============================================================
# CONFIGURATION
# ============================================================

DB_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "portfolio_manager.db"
)

BUY_NEW_ACTION = "BUY NEW"


# ============================================================
# HELPERS
# ============================================================

def normalise_datetime(series):
    """
    Normalise mixed-format timestamps.

    Supports:
        YYYY-MM-DD
        YYYY-MM-DDTHH:MM:SS+00:00
        YYYY-MM-DDTHH:MM:SS.ssssss+00:00
    """
    return (
        pd.to_datetime(
            series,
            errors="coerce",
            format="mixed",
            utc=True,
        )
        .dt.tz_localize(None)
    )


def print_section(title):
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


# ============================================================
# LOAD AUDIT DECISIONS
# ============================================================

def load_audit_decisions(conn):
    audit = pd.read_sql_query(
        """
        SELECT
            ad.id AS audit_decision_id,
            ad.audit_run_id,
            ad.recommendation_id,
            ad.ticker,
            ad.final_action,
            ar.run_date AS audit_date
        FROM audit_decisions ad
        JOIN audit_runs ar
            ON ar.id = ad.audit_run_id
        WHERE ar.status = 'COMPLETED'
        """,
        conn,
    )

    audit["audit_date"] = normalise_datetime(
        audit["audit_date"]
    )

    return audit


# ============================================================
# LOAD RECOMMENDATIONS
# ============================================================

def load_recommendations(conn):
    recs = pd.read_sql_query(
        """
        SELECT
            id AS recommendation_id,
            date AS recommendation_date,
            ticker
        FROM recommendations
        """,
        conn,
    )

    recs["recommendation_date"] = normalise_datetime(
        recs["recommendation_date"]
    )

    # Rows without a recommendation date cannot participate
    # in deterministic temporal lineage reconstruction.
    recs = recs[
        recs["recommendation_date"].notna()
    ].copy()

    return recs


# ============================================================
# LOAD EVALUATIONS
# ============================================================

def load_evaluations(conn):
    evaluations = pd.read_sql_query(
        """
        SELECT
            recommendation_id,
            evaluation_date,
            days_after,
            return_percent,
            outcome
        FROM recommendation_evaluations
        WHERE days_after = 5
        """,
        conn,
    )

    evaluations["evaluation_date"] = normalise_datetime(
        evaluations["evaluation_date"]
    )

    return evaluations


# ============================================================
# LOAD EVIDENCE
# ============================================================

def load_evidence(conn):
    evidence = pd.read_sql_query(
        """
        SELECT
            recommendation_id,
            ticker AS evidence_ticker,
            capture_date,
            signal,
            investment_score,
            technical_score,
            quality_score,
            growth_score,
            confidence_score,
            entry_price,
            rsi,
            extension_sma50_pct,
            extension_sma200_pct,
            revenue_growth,
            profit_margin,
            return_on_equity,
            debt_to_equity,
            entry_quality
        FROM recommendation_evidence
        """,
        conn,
    )

    evidence["capture_date"] = normalise_datetime(
        evidence["capture_date"]
    )

    return evidence


# ============================================================
# BUILD LINEAGE
# ============================================================

def build_lineage(audit, recs):
    """
    Resolve governed audit decisions to recommendations.

    Direct lineage:
        audit_decisions.recommendation_id

    Legacy lineage:
        latest recommendation for the same ticker
        on or before the audit date.

    Rows with no defensible lineage remain unresolved.
    """

    audit = audit.copy()

    direct = audit[
        audit["recommendation_id"].notna()
    ].copy()

    direct["lineage_type"] = "DIRECT"

    legacy = audit[
        audit["recommendation_id"].isna()
    ].copy()

    legacy = legacy[
        legacy["audit_date"].notna()
    ].copy()

    # Only recommendations with valid dates can be used.
    recs_valid = recs[
        recs["recommendation_date"].notna()
    ].copy()

    # Deterministic per-ticker lookup.
    recs_by_ticker = {
        ticker: group.sort_values(
            "recommendation_date"
        )
        for ticker, group
        in recs_valid.groupby("ticker")
    }

    resolved_rows = []

    for row in legacy.itertuples(index=False):

        ticker = row.ticker
        audit_date = row.audit_date

        ticker_recs = recs_by_ticker.get(ticker)

        if ticker_recs is None:
            continue

        eligible = ticker_recs[
            ticker_recs["recommendation_date"]
            <= audit_date
        ]

        if eligible.empty:
            continue

        match = eligible.iloc[-1]

        resolved_rows.append(
            {
                "audit_decision_id": row.audit_decision_id,
                "audit_run_id": row.audit_run_id,
                "recommendation_id": match[
                    "recommendation_id"
                ],
                "ticker": row.ticker,
                "final_action": row.final_action,
                "audit_date": row.audit_date,
                "recommendation_date": match[
                    "recommendation_date"
                ],
                "lineage_type": "RECONSTRUCTED",
            }
        )

    reconstructed = pd.DataFrame(
        resolved_rows
    )

    if reconstructed.empty:
        reconstructed = pd.DataFrame(
            columns=[
                "audit_decision_id",
                "audit_run_id",
                "recommendation_id",
                "ticker",
                "final_action",
                "audit_date",
                "recommendation_date",
                "lineage_type",
            ]
        )

    # Add recommendation dates to direct lineage.
    direct = direct.merge(
        recs_valid[
            [
                "recommendation_id",
                "recommendation_date",
            ]
        ],
        on="recommendation_id",
        how="left",
    )

    columns = [
        "audit_decision_id",
        "audit_run_id",
        "recommendation_id",
        "ticker",
        "final_action",
        "audit_date",
        "recommendation_date",
        "lineage_type",
    ]

    direct = direct[columns]

    lineage = pd.concat(
        [
            direct,
            reconstructed,
        ],
        ignore_index=True,
    )

    lineage = lineage.drop_duplicates(
        subset=["audit_decision_id"],
        keep="first",
    )

    lineage = lineage.sort_values(
        [
            "ticker",
            "audit_date",
            "audit_decision_id",
        ]
    ).reset_index(drop=True)

    return lineage


# ============================================================
# BUILD MATURE GOVERNED POPULATION
# ============================================================

def build_mature_population(
    lineage,
    evaluations,
    evidence,
):
    population = lineage.merge(
        evaluations,
        on="recommendation_id",
        how="inner",
    )

    population = population[
        population["days_after"] == 5
    ].copy()

    population = population.merge(
        evidence,
        on="recommendation_id",
        how="left",
        suffixes=("", "_evidence"),
    )

    # Coalesce evidence ticker where required.
    if "evidence_ticker" in population.columns:
        population["ticker"] = (
            population["ticker"]
            .fillna(
                population["evidence_ticker"]
            )
        )

    return population


# ============================================================
# BASIC PERFORMANCE
# ============================================================

def performance(df, label):
    print_section(label)

    if df.empty:
        print("No observations.")
        return None

    returns = pd.to_numeric(
        df["return_percent"],
        errors="coerce",
    ).dropna()

    if returns.empty:
        print("No valid 5D returns.")
        return None

    result = {
        "n": len(returns),
        "mean": returns.mean(),
        "median": returns.median(),
        "positive_rate": (
            returns.gt(0).mean() * 100
        ),
    }

    print(f"n: {result['n']}")
    print(
        f"Mean 5D return: "
        f"{result['mean']:.3f}%"
    )
    print(
        f"Median 5D return: "
        f"{result['median']:.3f}%"
    )
    print(
        f"Positive rate: "
        f"{result['positive_rate']:.3f}%"
    )

    return result


# ============================================================
# SAME-TICKER CONTROL
# ============================================================

def build_same_ticker_controls(
    buy_new,
    non_buy_new,
):
    """
    For every BUY NEW observation, identify non-BUY-NEW
    observations for the same ticker.

    The primary comparison is the nearest prior non-BUY-NEW
    observation for the same ticker.

    This asks:

        When this company was evaluated previously,
        how did the non-BUY-NEW decision perform compared
        with the BUY NEW decision?

    We also retain the nearest subsequent non-BUY-NEW
    observation where available.
    """

    controls = []

    non_by_ticker = {
        ticker: group.sort_values(
            "recommendation_date"
        )
        for ticker, group
        in non_buy_new.groupby("ticker")
    }

    for buy_row in buy_new.itertuples(
        index=False
    ):

        ticker = buy_row.ticker

        candidates = non_by_ticker.get(
            ticker
        )

        if candidates is None or candidates.empty:
            continue

        buy_date = buy_row.recommendation_date

        prior = candidates[
            candidates["recommendation_date"]
            < buy_date
        ]

        subsequent = candidates[
            candidates["recommendation_date"]
            > buy_date
        ]

        prior_row = (
            prior.iloc[-1]
            if not prior.empty
            else None
        )

        subsequent_row = (
            subsequent.iloc[0]
            if not subsequent.empty
            else None
        )

        base = {
            "buy_audit_decision_id":
                buy_row.audit_decision_id,
            "buy_recommendation_id":
                buy_row.recommendation_id,
            "ticker": ticker,
            "buy_date": buy_date,
            "buy_return":
                buy_row.return_percent,
        }

        if prior_row is not None:
            controls.append(
                {
                    **base,
                    "control_type": "PRIOR",
                    "control_audit_decision_id":
                        prior_row.audit_decision_id,
                    "control_recommendation_id":
                        prior_row.recommendation_id,
                    "control_date":
                        prior_row.recommendation_date,
                    "control_action":
                        prior_row.final_action,
                    "control_return":
                        prior_row.return_percent,
                    "return_delta":
                        (
                            buy_row.return_percent
                            - prior_row.return_percent
                        ),
                    "days_between":
                        (
                            buy_date
                            - prior_row.recommendation_date
                        ).days,
                }
            )

        if subsequent_row is not None:
            controls.append(
                {
                    **base,
                    "control_type": "SUBSEQUENT",
                    "control_audit_decision_id":
                        subsequent_row.audit_decision_id,
                    "control_recommendation_id":
                        subsequent_row.recommendation_id,
                    "control_date":
                        subsequent_row.recommendation_date,
                    "control_action":
                        subsequent_row.final_action,
                    "control_return":
                        subsequent_row.return_percent,
                    "return_delta":
                        (
                            buy_row.return_percent
                            - subsequent_row.return_percent
                        ),
                    "days_between":
                        (
                            subsequent_row.recommendation_date
                            - buy_date
                        ).days,
                }
            )

    return pd.DataFrame(controls)


# ============================================================
# TICKER-LEVEL ANALYSIS
# ============================================================

def ticker_analysis(
    buy_new,
    controls,
):
    print_section(
        "SAME-TICKER CONTROL BY TICKER"
    )

    if controls.empty:
        print("No same-ticker controls available.")
        return

    rows = []

    for ticker, group in controls.groupby(
        "ticker"
    ):

        prior = group[
            group["control_type"] == "PRIOR"
        ]

        if prior.empty:
            continue

        buy_mean = pd.to_numeric(
            prior["buy_return"],
            errors="coerce",
        ).mean()

        control_mean = pd.to_numeric(
            prior["control_return"],
            errors="coerce",
        ).mean()

        delta = buy_mean - control_mean

        rows.append(
            {
                "ticker": ticker,
                "n_controls": len(prior),
                "buy_new_mean_5d":
                    buy_mean,
                "control_mean_5d":
                    control_mean,
                "delta_buy_minus_control":
                    delta,
            }
        )

    if not rows:
        print("No prior same-ticker controls.")
        return

    result = pd.DataFrame(rows)

    result = result.sort_values(
        "delta_buy_minus_control"
    )

    print(
        result.to_string(
            index=False,
            formatters={
                "buy_new_mean_5d":
                    lambda x: f"{x:.3f}",
                "control_mean_5d":
                    lambda x: f"{x:.3f}",
                "delta_buy_minus_control":
                    lambda x: f"{x:.3f}",
            },
        )
    )


# ============================================================
# CONTROL SUMMARY
# ============================================================

def control_summary(controls):
    print_section(
        "SAME-TICKER CONTROL SUMMARY"
    )

    if controls.empty:
        print("No same-ticker controls available.")
        return

    prior = controls[
        controls["control_type"] == "PRIOR"
    ].copy()

    subsequent = controls[
        controls["control_type"] == "SUBSEQUENT"
    ].copy()

    if not prior.empty:

        buy_returns = pd.to_numeric(
            prior["buy_return"],
            errors="coerce",
        )

        control_returns = pd.to_numeric(
            prior["control_return"],
            errors="coerce",
        )

        delta = pd.to_numeric(
            prior["return_delta"],
            errors="coerce",
        )

        valid = (
            buy_returns.notna()
            & control_returns.notna()
        )

        print(
            "PRIOR SAME-TICKER CONTROL"
        )
        print(
            f"BUY NEW observations: "
            f"{valid.sum()}"
        )
        print(
            f"BUY NEW mean 5D: "
            f"{buy_returns[valid].mean():.3f}%"
        )
        print(
            f"Prior control mean 5D: "
            f"{control_returns[valid].mean():.3f}%"
        )
        print(
            f"Mean delta "
            f"(BUY NEW - control): "
            f"{delta[valid].mean():.3f}pp"
        )
        print(
            f"BUY NEW better than control: "
            f"{(delta[valid] > 0).mean() * 100:.3f}%"
        )
        print(
            f"BUY NEW worse than control: "
            f"{(delta[valid] < 0).mean() * 100:.3f}%"
        )

    if not subsequent.empty:

        buy_returns = pd.to_numeric(
            subsequent["buy_return"],
            errors="coerce",
        )

        control_returns = pd.to_numeric(
            subsequent["control_return"],
            errors="coerce",
        )

        delta = pd.to_numeric(
            subsequent["return_delta"],
            errors="coerce",
        )

        valid = (
            buy_returns.notna()
            & control_returns.notna()
        )

        print()
        print(
            "SUBSEQUENT SAME-TICKER CONTROL"
        )
        print(
            f"BUY NEW observations: "
            f"{valid.sum()}"
        )
        print(
            f"BUY NEW mean 5D: "
            f"{buy_returns[valid].mean():.3f}%"
        )
        print(
            f"Subsequent control mean 5D: "
            f"{control_returns[valid].mean():.3f}%"
        )
        print(
            f"Mean delta "
            f"(BUY NEW - control): "
            f"{delta[valid].mean():.3f}pp"
        )
        print(
            f"BUY NEW better than control: "
            f"{(delta[valid] > 0).mean() * 100:.3f}%"
        )
        print(
            f"BUY NEW worse than control: "
            f"{(delta[valid] < 0).mean() * 100:.3f}%"
        )


# ============================================================
# MATCH DISTANCE
# ============================================================

def match_distance_summary(controls):
    print_section(
        "CONTROL MATCH DISTANCE"
    )

    if controls.empty:
        print("No controls.")
        return

    for control_type in [
        "PRIOR",
        "SUBSEQUENT",
    ]:

        subset = controls[
            controls["control_type"]
            == control_type
        ]

        if subset.empty:
            continue

        days = pd.to_numeric(
            subset["days_between"],
            errors="coerce",
        ).dropna()

        print(
            f"{control_type}: "
            f"n={len(days)}, "
            f"median={days.median():.1f} days, "
            f"mean={days.mean():.1f} days"
        )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 78)
    print(
        "BUY NEW — SAME-TICKER CONTROL TEST"
    )
    print("=" * 78)
    print(
        "READ-ONLY — NO PRODUCTION CHANGES"
    )
    print(f"Database: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)

    audit = load_audit_decisions(conn)
    recs = load_recommendations(conn)
    evaluations = load_evaluations(conn)
    evidence = load_evidence(conn)

    conn.close()

    print(
        f"Audit decisions: {len(audit)}"
    )
    print(
        f"Recommendations with valid dates: "
        f"{len(recs)}"
    )
    print(
        f"Evidence rows: {len(evidence)}"
    )
    print(
        f"Mature 5D outcomes: "
        f"{len(evaluations)}"
    )

    lineage = build_lineage(
        audit,
        recs,
    )

    raw_buy_new = audit[
        audit["final_action"]
        == BUY_NEW_ACTION
    ]

    direct_count = (
        lineage["lineage_type"]
        == "DIRECT"
    ).sum()

    reconstructed_count = (
        lineage["lineage_type"]
        == "RECONSTRUCTED"
    ).sum()

    unresolved_count = (
        len(audit)
        - len(lineage)
    )

    print()
    print(
        f"Raw BUY NEW audit decisions: "
        f"{len(raw_buy_new)}"
    )
    print(
        f"Direct lineage: "
        f"{direct_count}"
    )
    print(
        f"Reconstructed legacy lineage: "
        f"{reconstructed_count}"
    )
    print(
        f"Unresolved lineage: "
        f"{unresolved_count}"
    )

    population = build_mature_population(
        lineage,
        evaluations,
        evidence,
    )

    buy_new = population[
        population["final_action"]
        == BUY_NEW_ACTION
    ].copy()

    non_buy_new = population[
        population["final_action"]
        != BUY_NEW_ACTION
    ].copy()

    print()
    print(
        f"Mature BUY NEW observations: "
        f"{len(buy_new)}"
    )
    print(
        f"Mature non-BUY-NEW observations: "
        f"{len(non_buy_new)}"
    )

    performance(
        buy_new,
        "BUY NEW PERFORMANCE",
    )

    performance(
        non_buy_new,
        "NON-BUY-NEW PERFORMANCE",
    )

    controls = build_same_ticker_controls(
        buy_new,
        non_buy_new,
    )

    print()
    print(
        f"Same-ticker control observations: "
        f"{len(controls)}"
    )

    control_summary(controls)

    match_distance_summary(controls)

    ticker_analysis(
        buy_new,
        controls,
    )

    print_section(
        "BUY NEW OBSERVATIONS WITHOUT PRIOR "
        "SAME-TICKER CONTROL"
    )

    if controls.empty:
        print("No controls.")
    else:
        prior_ids = set(
            controls[
                controls["control_type"]
                == "PRIOR"
            ]["buy_audit_decision_id"]
        )

        missing = buy_new[
            ~buy_new[
                "audit_decision_id"
            ].isin(prior_ids)
        ]

        print(
            f"BUY NEW observations without "
            f"prior same-ticker control: "
            f"{len(missing)}"
        )

        if not missing.empty:
            print(
                missing[
                    [
                        "audit_decision_id",
                        "recommendation_id",
                        "ticker",
                        "recommendation_date",
                        "return_percent",
                    ]
                ]
                .sort_values(
                    "recommendation_date"
                )
                .to_string(index=False)
            )

    print_section(
        "INTERPRETATION GUIDE"
    )

    print(
        "This is an A6 investigation only."
    )
    print()
    print(
        "If BUY NEW remains materially worse "
        "than same-ticker controls, that is "
        "stronger evidence of a BUY NEW "
        "selection/timing problem."
    )
    print()
    print(
        "If the BUY NEW disadvantage largely "
        "disappears within ticker, the broader "
        "problem is more likely the composition "
        "of the BUY NEW candidate pool or "
        "ticker concentration."
    )
    print()
    print(
        "No thresholds, weights, scores, "
        "governance or production decisions "
        "are changed by this test."
    )

    print()
    print("=" * 78)
    print("CONTROL TEST COMPLETE")
    print("=" * 78)
    print(
        "NO PRODUCTION CHANGES WERE MADE."
    )


if __name__ == "__main__":
    main()

