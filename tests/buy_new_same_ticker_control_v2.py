"""
BUY NEW — SAME-TICKER CONTROL TEST V2

A6 READ-ONLY INVESTIGATION
NO PRODUCTION CHANGES

Question:
    When the same ticker was evaluated by the governed decision
    system, did BUY NEW produce a different subsequent 5D outcome
    from a non-BUY-NEW decision for that same ticker?

This version is deliberately anchored to the validated BUY NEW
population:

    - 234 raw BUY NEW audit decisions
    - 114 direct lineage
    - 120 reconstructed legacy lineage
    - 111 mature BUY NEW observations

The test then:

    1. Rebuilds governed audit lineage.
    2. Identifies the validated mature BUY NEW population.
    3. Finds DISTINCT non-BUY-NEW audit decisions for the same ticker.
    4. Matches each BUY NEW observation to the closest valid
       same-ticker control.
    5. Prevents the BUY NEW decision itself from being reused
       as its own control.
    6. Deduplicates repeated recommendation/evaluation records.
    7. Reports prior and subsequent controls separately.
    8. Reports ticker-level results.
    9. Reports coverage so we know how much of BUY NEW is actually
       being tested.

This is an investigation only.

It does NOT:
    - change thresholds
    - change scores
    - change weights
    - change governance
    - change portfolio decisions
    - modify the database
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

BUY_NEW = "BUY NEW"


# ============================================================
# HELPERS
# ============================================================

def normalise_datetime(series):
    return (
        pd.to_datetime(
            series,
            errors="coerce",
            format="mixed",
            utc=True,
        )
        .dt.tz_localize(None)
    )


def section(title):
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


# ============================================================
# LOAD AUDIT DECISIONS
# ============================================================

def load_audit(conn):

    df = pd.read_sql_query(
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

    df["audit_date"] = normalise_datetime(
        df["audit_date"]
    )

    df["ticker"] = (
        df["ticker"]
        .astype(str)
        .str.strip()
    )

    return df


# ============================================================
# LOAD RECOMMENDATIONS
# ============================================================

def load_recommendations(conn):

    df = pd.read_sql_query(
        """
        SELECT
            id AS recommendation_id,
            date AS recommendation_date,
            ticker
        FROM recommendations
        """,
        conn,
    )

    df["recommendation_date"] = normalise_datetime(
        df["recommendation_date"]
    )

    df = df[
        df["recommendation_date"].notna()
    ].copy()

    df["ticker"] = (
        df["ticker"]
        .astype(str)
        .str.strip()
    )

    return df


# ============================================================
# LOAD 5D EVALUATIONS
# ============================================================

def load_evaluations(conn):

    df = pd.read_sql_query(
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

    df["evaluation_date"] = normalise_datetime(
        df["evaluation_date"]
    )

    df["return_percent"] = pd.to_numeric(
        df["return_percent"],
        errors="coerce",
    )

    return df


# ============================================================
# BUILD VALIDATED LINEAGE
# ============================================================

def build_lineage(audit, recs):

    direct = audit[
        audit["recommendation_id"].notna()
    ].copy()

    direct["lineage_type"] = "DIRECT"

    direct = direct.merge(
        recs[
            [
                "recommendation_id",
                "recommendation_date",
            ]
        ],
        on="recommendation_id",
        how="left",
    )

    legacy = audit[
        audit["recommendation_id"].isna()
    ].copy()

    legacy = legacy[
        legacy["audit_date"].notna()
    ].copy()

    recs_by_ticker = {
        ticker: group.sort_values(
            "recommendation_date"
        )
        for ticker, group
        in recs.groupby("ticker")
    }

    rows = []

    for row in legacy.itertuples(
        index=False
    ):

        candidates = recs_by_ticker.get(
            row.ticker
        )

        if candidates is None:
            continue

        candidates = candidates[
            candidates["recommendation_date"]
            <= row.audit_date
        ]

        if candidates.empty:
            continue

        match = candidates.iloc[-1]

        rows.append(
            {
                "audit_decision_id":
                    row.audit_decision_id,
                "audit_run_id":
                    row.audit_run_id,
                "recommendation_id":
                    match["recommendation_id"],
                "ticker":
                    row.ticker,
                "final_action":
                    row.final_action,
                "audit_date":
                    row.audit_date,
                "recommendation_date":
                    match["recommendation_date"],
                "lineage_type":
                    "RECONSTRUCTED",
            }
        )

    reconstructed = pd.DataFrame(rows)

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

def build_population(
    lineage,
    evaluations,
):

    population = lineage.merge(
        evaluations[
            [
                "recommendation_id",
                "evaluation_date",
                "days_after",
                "return_percent",
                "outcome",
            ]
        ],
        on="recommendation_id",
        how="inner",
    )

    population = population[
        population["days_after"] == 5
    ].copy()

    # Critical:
    # one governed audit decision should appear once.
    population = population.drop_duplicates(
        subset=["audit_decision_id"],
        keep="first",
    )

    return population


# ============================================================
# IDENTIFY VALIDATED BUY NEW POPULATION
# ============================================================

def get_buy_new_population(population):

    buy_new = population[
        population["final_action"] == BUY_NEW
    ].copy()

    # Critical:
    # Keep the validated BUY NEW population intact.
    # Do not deduplicate by recommendation_id because multiple
    # governed decisions can legitimately reference the same
    # recommendation.
    buy_new = buy_new.drop_duplicates(
        subset=["audit_decision_id"],
        keep="first",
    )

    return buy_new


# ============================================================
# BUILD CONTROL CANDIDATES
# ============================================================

def get_control_candidates(
    population,
    buy_row,
):
    """
    Return distinct non-BUY-NEW governed observations
    for the same ticker.

    Exclude:
        - the BUY NEW audit decision itself
        - BUY NEW actions
        - exact duplicate audit observations
    """

    candidates = population[
        (
            population["ticker"]
            == buy_row["ticker"]
        )
        & (
            population["final_action"]
            != BUY_NEW
        )
        & (
            population["audit_decision_id"]
            != buy_row["audit_decision_id"]
        )
    ].copy()

    candidates = candidates.drop_duplicates(
        subset=["audit_decision_id"],
        keep="first",
    )

    return candidates


# ============================================================
# FIND CONTROLS
# ============================================================

def find_controls(
    buy_new,
    population,
):

    rows = []

    for _, buy in buy_new.iterrows():

        candidates = get_control_candidates(
            population,
            buy,
        )

        if candidates.empty:
            continue

        buy_date = buy["audit_date"]

        candidates["distance_days"] = (
            candidates["audit_date"]
            - buy_date
        ).dt.total_seconds() / 86400.0

        prior = candidates[
            candidates["distance_days"] < 0
        ].copy()

        subsequent = candidates[
            candidates["distance_days"] > 0
        ].copy()

        # ----------------------------------------------------
        # PRIOR CONTROL
        # ----------------------------------------------------

        if not prior.empty:

            # Closest prior governed decision.
            prior = prior.sort_values(
                [
                    "distance_days",
                    "audit_decision_id",
                ],
                ascending=[
                    False,
                    True,
                ],
            )

            control = prior.iloc[0]

            rows.append(
                {
                    "buy_audit_decision_id":
                        buy["audit_decision_id"],
                    "buy_recommendation_id":
                        buy["recommendation_id"],
                    "ticker":
                        buy["ticker"],
                    "buy_date":
                        buy_date,
                    "buy_return":
                        buy["return_percent"],
                    "control_type":
                        "PRIOR",
                    "control_audit_decision_id":
                        control[
                            "audit_decision_id"
                        ],
                    "control_recommendation_id":
                        control[
                            "recommendation_id"
                        ],
                    "control_date":
                        control["audit_date"],
                    "control_action":
                        control["final_action"],
                    "control_return":
                        control["return_percent"],
                    "days_between":
                        abs(
                            control[
                                "distance_days"
                            ]
                        ),
                    "return_delta":
                        (
                            buy["return_percent"]
                            - control["return_percent"]
                        ),
                }
            )

        # ----------------------------------------------------
        # SUBSEQUENT CONTROL
        # ----------------------------------------------------

        if not subsequent.empty:

            # Closest subsequent governed decision.
            subsequent = subsequent.sort_values(
                [
                    "distance_days",
                    "audit_decision_id",
                ],
                ascending=[
                    True,
                    True,
                ],
            )

            control = subsequent.iloc[0]

            rows.append(
                {
                    "buy_audit_decision_id":
                        buy["audit_decision_id"],
                    "buy_recommendation_id":
                        buy["recommendation_id"],
                    "ticker":
                        buy["ticker"],
                    "buy_date":
                        buy_date,
                    "buy_return":
                        buy["return_percent"],
                    "control_type":
                        "SUBSEQUENT",
                    "control_audit_decision_id":
                        control[
                            "audit_decision_id"
                        ],
                    "control_recommendation_id":
                        control[
                            "recommendation_id"
                        ],
                    "control_date":
                        control["audit_date"],
                    "control_action":
                        control["final_action"],
                    "control_return":
                        control["return_percent"],
                    "days_between":
                        abs(
                            control[
                                "distance_days"
                            ]
                        ),
                    "return_delta":
                        (
                            buy["return_percent"]
                            - control["return_percent"]
                        ),
                }
            )

    return pd.DataFrame(rows)


# ============================================================
# SUMMARY
# ============================================================

def summarise_controls(
    controls,
    control_type,
):

    df = controls[
        controls["control_type"]
        == control_type
    ].copy()

    if df.empty:
        return None

    buy = pd.to_numeric(
        df["buy_return"],
        errors="coerce",
    )

    control = pd.to_numeric(
        df["control_return"],
        errors="coerce",
    )

    delta = pd.to_numeric(
        df["return_delta"],
        errors="coerce",
    )

    valid = (
        buy.notna()
        & control.notna()
        & delta.notna()
    )

    if not valid.any():
        return None

    return {
        "n": int(valid.sum()),
        "buy_mean": buy[valid].mean(),
        "control_mean": control[valid].mean(),
        "delta_mean": delta[valid].mean(),
        "buy_better_pct":
            (delta[valid] > 0).mean() * 100,
        "buy_worse_pct":
            (delta[valid] < 0).mean() * 100,
        "median_days":
            df.loc[
                valid,
                "days_between",
            ].median(),
    }


# ============================================================
# TICKER ANALYSIS
# ============================================================

def ticker_analysis(
    controls,
):

    section(
        "SAME-TICKER CONTROL BY TICKER"
    )

    prior = controls[
        controls["control_type"]
        == "PRIOR"
    ].copy()

    if prior.empty:
        print("No prior controls available.")
        return

    rows = []

    for ticker, group in prior.groupby(
        "ticker"
    ):

        buy = pd.to_numeric(
            group["buy_return"],
            errors="coerce",
        )

        control = pd.to_numeric(
            group["control_return"],
            errors="coerce",
        )

        delta = pd.to_numeric(
            group["return_delta"],
            errors="coerce",
        )

        valid = (
            buy.notna()
            & control.notna()
            & delta.notna()
        )

        if not valid.any():
            continue

        rows.append(
            {
                "ticker": ticker,
                "n": int(valid.sum()),
                "buy_new_mean":
                    buy[valid].mean(),
                "control_mean":
                    control[valid].mean(),
                "delta":
                    delta[valid].mean(),
                "buy_better_pct":
                    (
                        delta[valid] > 0
                    ).mean() * 100,
            }
        )

    if not rows:
        print("No usable ticker results.")
        return

    result = pd.DataFrame(rows)

    result = result.sort_values(
        "delta"
    )

    print(
        result.to_string(
            index=False,
            formatters={
                "buy_new_mean":
                    lambda x: f"{x:.3f}",
                "control_mean":
                    lambda x: f"{x:.3f}",
                "delta":
                    lambda x: f"{x:.3f}",
                "buy_better_pct":
                    lambda x: f"{x:.1f}",
            },
        )
    )


# ============================================================
# COVERAGE
# ============================================================

def coverage_summary(
    buy_new,
    controls,
):

    section(
        "BUY NEW CONTROL COVERAGE"
    )

    prior_ids = set(
        controls[
            controls["control_type"]
            == "PRIOR"
        ]["buy_audit_decision_id"]
    )

    subsequent_ids = set(
        controls[
            controls["control_type"]
            == "SUBSEQUENT"
        ]["buy_audit_decision_id"]
    )

    both_ids = (
        prior_ids
        & subsequent_ids
    )

    print(
        f"Validated BUY NEW observations: "
        f"{len(buy_new)}"
    )

    print(
        f"With prior control: "
        f"{len(prior_ids)} "
        f"({len(prior_ids) / len(buy_new) * 100:.1f}%)"
    )

    print(
        f"With subsequent control: "
        f"{len(subsequent_ids)} "
        f"({len(subsequent_ids) / len(buy_new) * 100:.1f}%)"
    )

    print(
        f"With both controls: "
        f"{len(both_ids)} "
        f"({len(both_ids) / len(buy_new) * 100:.1f}%)"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 78)
    print(
        "BUY NEW — SAME-TICKER CONTROL TEST V2"
    )
    print("=" * 78)
    print(
        "READ-ONLY — NO PRODUCTION CHANGES"
    )
    print(f"Database: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)

    audit = load_audit(conn)
    recs = load_recommendations(conn)
    evaluations = load_evaluations(conn)

    conn.close()

    print()
    print(
        f"Audit decisions: {len(audit)}"
    )
    print(
        f"Recommendations with valid dates: "
        f"{len(recs)}"
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
        audit["final_action"] == BUY_NEW
    ]

    direct = (
        lineage["lineage_type"]
        == "DIRECT"
    ).sum()

    reconstructed = (
        lineage["lineage_type"]
        == "RECONSTRUCTED"
    ).sum()

    unresolved = (
        len(audit)
        - len(lineage)
    )

    print()
    print(
        f"Raw BUY NEW audit decisions: "
        f"{len(raw_buy_new)}"
    )
    print(
        f"Direct lineage: {direct}"
    )
    print(
        f"Reconstructed legacy lineage: "
        f"{reconstructed}"
    )
    print(
        f"Unresolved lineage: {unresolved}"
    )

    population = build_population(
        lineage,
        evaluations,
    )

    buy_new = get_buy_new_population(
        population
    )

    non_buy_new = population[
        population["final_action"] != BUY_NEW
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

    # --------------------------------------------------------
    # Sanity check: validated BUY NEW population
    # --------------------------------------------------------

    section(
        "VALIDATED BUY NEW POPULATION"
    )

    if not buy_new.empty:
        print(
            buy_new[
                [
                    "audit_decision_id",
                    "recommendation_id",
                    "ticker",
                    "audit_date",
                    "recommendation_date",
                    "return_percent",
                ]
            ]
            .sort_values(
                [
                    "ticker",
                    "audit_date",
                ]
            )
            .head(20)
            .to_string(index=False)
        )

    # --------------------------------------------------------
    # Build controls
    # --------------------------------------------------------

    controls = find_controls(
        buy_new,
        population,
    )

    print()
    print(
        f"Same-ticker control observations: "
        f"{len(controls)}"
    )

    # --------------------------------------------------------
    # Coverage
    # --------------------------------------------------------

    coverage_summary(
        buy_new,
        controls,
    )

    # --------------------------------------------------------
    # Prior controls
    # --------------------------------------------------------

    section(
        "PRIOR SAME-TICKER CONTROL"
    )

    prior = summarise_controls(
        controls,
        "PRIOR",
    )

    if prior is None:
        print("No usable prior controls.")
    else:
        print(
            f"n: {prior['n']}"
        )
        print(
            f"BUY NEW mean 5D: "
            f"{prior['buy_mean']:.3f}%"
        )
        print(
            f"Control mean 5D: "
            f"{prior['control_mean']:.3f}%"
        )
        print(
            f"Mean delta "
            f"(BUY NEW - control): "
            f"{prior['delta_mean']:.3f}pp"
        )
        print(
            f"BUY NEW better: "
            f"{prior['buy_better_pct']:.1f}%"
        )
        print(
            f"BUY NEW worse: "
            f"{prior['buy_worse_pct']:.1f}%"
        )
        print(
            f"Median control distance: "
            f"{prior['median_days']:.1f} days"
        )

    # --------------------------------------------------------
    # Subsequent controls
    # --------------------------------------------------------

    section(
        "SUBSEQUENT SAME-TICKER CONTROL"
    )

    subsequent = summarise_controls(
        controls,
        "SUBSEQUENT",
    )

    if subsequent is None:
        print("No usable subsequent controls.")
    else:
        print(
            f"n: {subsequent['n']}"
        )
        print(
            f"BUY NEW mean 5D: "
            f"{subsequent['buy_mean']:.3f}%"
        )
        print(
            f"Control mean 5D: "
            f"{subsequent['control_mean']:.3f}%"
        )
        print(
            f"Mean delta "
            f"(BUY NEW - control): "
            f"{subsequent['delta_mean']:.3f}pp"
        )
        print(
            f"BUY NEW better: "
            f"{subsequent['buy_better_pct']:.1f}%"
        )
        print(
            f"BUY NEW worse: "
            f"{subsequent['buy_worse_pct']:.1f}%"
        )
        print(
            f"Median control distance: "
            f"{subsequent['median_days']:.1f} days"
        )

    # --------------------------------------------------------
    # Ticker analysis
    # --------------------------------------------------------

    ticker_analysis(
        controls
    )

    # --------------------------------------------------------
    # Control detail
    # --------------------------------------------------------

    section(
        "CONTROL DETAIL"
    )

    if controls.empty:
        print("No control observations.")
    else:
        print(
            controls[
                [
                    "buy_audit_decision_id",
                    "ticker",
                    "buy_date",
                    "buy_return",
                    "control_type",
                    "control_audit_decision_id",
                    "control_date",
                    "control_action",
                    "control_return",
                    "days_between",
                    "return_delta",
                ]
            ]
            .sort_values(
                [
                    "ticker",
                    "buy_date",
                    "control_type",
                ]
            )
            .to_string(index=False)
        )

    # --------------------------------------------------------
    # Interpretation
    # --------------------------------------------------------

    section(
        "INTERPRETATION"
    )

    print(
        "This test is read-only."
    )
    print()
    print(
        "The validated BUY NEW population is "
        "kept fixed at the mature governed "
        "observations identified by the A6 lineage."
    )
    print()
    print(
        "The control is a DISTINCT governed "
        "non-BUY-NEW audit decision for the "
        "same ticker."
    )
    print()
    print(
        "A persistent negative BUY NEW-minus-control "
        "delta across multiple tickers would provide "
        "stronger evidence that the BUY NEW decision "
        "itself is selecting poor timing/entry points."
    )
    print()
    print(
        "If the delta disappears when controlled "
        "within ticker, the problem is more likely "
        "the composition/concentration of the BUY NEW "
        "candidate pool."
    )
    print()
    print(
        "No production thresholds, weights, scores, "
        "governance or portfolio decisions are changed."
    )

    print()
    print("=" * 78)
    print("CONTROL TEST V2 COMPLETE")
    print("=" * 78)
    print(
        "NO PRODUCTION CHANGES WERE MADE."
    )


if __name__ == "__main__":
    main()

