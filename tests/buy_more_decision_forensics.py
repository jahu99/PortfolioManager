"""
Non-production BUY MORE decision forensics.

READ-ONLY.

This analysis investigates two separate questions:

1. BUY MORE selection:
   What distinguishes accepted BUY MORE decisions from BUY MORE
   proposals that were rejected by governance?

2. Incremental value:
   When the agent actually chooses BUY MORE, how does the realised
   outcome compare with a comparable genuine HOLD decision?

Population definitions
----------------------

BUY MORE accepted:
    proposed_action = BUY MORE
    final_action    = BUY MORE

BUY MORE rejected:
    proposed_action = BUY MORE
    final_action    = HOLD

GENUINE HOLD:
    proposed_action = HOLD
    final_action    = HOLD

The rejected BUY MORE population is NOT used as the counterfactual
HOLD population.

The incremental-value analysis therefore compares accepted BUY MORE
against genuine HOLD decisions.

Historical audit decisions without recommendation_id are linked to
the latest recommendation for the same ticker on or before the audit
date, consistent with the existing forensic lineage approach.

No production code, database rows, reports, or persistent analysis
outputs are modified.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd


DB_PATH = Path("data/portfolio_manager.db")

HORIZON = 5

EXCLUDED_TICKERS = {
    "TESTBUYMORE",
}

EXCLUDED_ASSET_TYPES = {
    "ETF",
}

MATCH_COLUMNS = [
    "investment_score",
    "evidence_score",
    "confidence_score",
    "technical_score",
    "quality_score",
    "growth_score",
]

# Require the same underlying signal.
# Maximum standardised Euclidean distance across available scores.
MAX_MATCH_DISTANCE = 2.5


def safe_float(value):
    try:
        if value is None or pd.isna(value):
            return np.nan
        return float(value)
    except (TypeError, ValueError):
        return np.nan


def normalise_day(value):
    try:
        return pd.to_datetime(
            value,
            utc=True,
        ).date()
    except Exception:
        return None


def format_pct(value):
    if pd.isna(value):
        return "n/a"
    return f"{value:.2f}%"


def print_outcome_summary(label, frame):
    print(f"\n{label}")
    print("-" * len(label))

    if frame.empty:
        print("No data.")
        return

    print(f"Decisions:   {len(frame)}")
    print(
        f"Mean 5D:     "
        f"{format_pct(frame['return_5d'].mean())}"
    )
    print(
        f"Median 5D:   "
        f"{format_pct(frame['return_5d'].median())}"
    )
    print(
        f"Positive 5D: "
        f"{frame['return_5d'].gt(0).mean() * 100:.2f}%"
    )


def load_audit_decisions(conn):
    return pd.read_sql_query(
        """
        SELECT
            id AS audit_decision_id,
            audit_run_id,
            ticker,
            asset_type,
            created_at,
            original_action,
            proposed_action,
            reconciled_action,
            final_action,
            action_changed,
            original_signal,
            investment_score,
            technical_score,
            quality_score,
            growth_score,
            confidence_score,
            evidence_score,
            original_allocation_pct,
            final_allocation_pct,
            recommendation_id
        FROM audit_decisions
        WHERE final_action IN ('BUY MORE', 'HOLD')
           OR proposed_action = 'BUY MORE'
        ORDER BY created_at, id
        """,
        conn,
    )


def load_recommendations(conn):
    frame = pd.read_sql_query(
        """
        SELECT
            id AS recommendation_id,
            date AS recommendation_date,
            ticker,
            signal,
            price AS recommendation_price
        FROM recommendations
        ORDER BY ticker, date, id
        """,
        conn,
    )

    frame["recommendation_day"] = (
        pd.to_datetime(
            frame["recommendation_date"],
            errors="coerce",
            utc=True,
        ).dt.date
    )

    return frame[
        frame["recommendation_day"].notna()
    ].copy()


def reconstruct_lineage(decisions, recommendations):
    decisions = decisions.copy()

    recommendations_by_ticker = {
        ticker: group.sort_values(
            ["recommendation_day", "recommendation_id"]
        )
        for ticker, group
        in recommendations.groupby("ticker")
    }

    lineage = []

    for _, decision in decisions.iterrows():

        if pd.notna(decision["recommendation_id"]):
            lineage.append(
                decision["recommendation_id"]
            )
            continue

        ticker = decision["ticker"]
        candidates = recommendations_by_ticker.get(
            ticker
        )

        if candidates is None:
            lineage.append(np.nan)
            continue

        audit_day = normalise_day(
            decision["created_at"]
        )

        if audit_day is None:
            lineage.append(np.nan)
            continue

        candidates = candidates[
            candidates["recommendation_day"] <= audit_day
        ]

        if candidates.empty:
            lineage.append(np.nan)
            continue

        lineage.append(
            candidates.iloc[-1]["recommendation_id"]
        )

    decisions["lineage_recommendation_id"] = lineage

    return decisions


def load_5d_evaluations(conn):
    return pd.read_sql_query(
        """
        SELECT
            recommendation_id,
            evaluation_date,
            days_after,
            return_percent,
            outcome
        FROM recommendation_evaluations
        WHERE days_after = ?
          AND return_percent IS NOT NULL
        """,
        conn,
        params=(HORIZON,),
    )


def attach_outcomes(decisions, evaluations):
    decisions = decisions.copy()

    evaluations = (
        evaluations
        .sort_values(
            [
                "recommendation_id",
                "evaluation_date",
            ]
        )
        .drop_duplicates(
            subset=["recommendation_id"],
            keep="first",
        )
    )

    evaluations = evaluations.rename(
        columns={
            "recommendation_id":
                "lineage_recommendation_id",
            "return_percent":
                "return_5d",
            "outcome":
                "outcome_5d",
        }
    )

    return decisions.merge(
        evaluations[
            [
                "lineage_recommendation_id",
                "return_5d",
                "outcome_5d",
            ]
        ],
        on="lineage_recommendation_id",
        how="left",
    )


def clean_population(decisions):
    frame = decisions.copy()

    frame["ticker"] = (
        frame["ticker"]
        .fillna("")
        .astype(str)
        .str.upper()
        .str.strip()
    )

    frame["asset_type"] = (
        frame["asset_type"]
        .fillna("")
        .astype(str)
        .str.upper()
        .str.strip()
    )

    raw_count = len(frame)

    frame = frame[
        ~frame["ticker"].isin(
            EXCLUDED_TICKERS
        )
    ]

    frame = frame[
        ~frame["asset_type"].isin(
            EXCLUDED_ASSET_TYPES
        )
    ]

    frame = frame[
        frame["return_5d"].notna()
    ].copy()

    print("\nPOPULATION")
    print("----------")
    print(
        f"Raw relevant audit decisions: "
        f"{raw_count}"
    )
    print(
        f"With realised 5D outcome: "
        f"{len(frame)}"
    )

    return frame


def classify_populations(decisions):
    frame = decisions.copy()

    accepted = frame[
        (frame["proposed_action"] == "BUY MORE")
        & (frame["final_action"] == "BUY MORE")
    ].copy()

    rejected = frame[
        (frame["proposed_action"] == "BUY MORE")
        & (frame["final_action"] == "HOLD")
    ].copy()

    genuine_hold = frame[
        (frame["proposed_action"] == "HOLD")
        & (frame["final_action"] == "HOLD")
    ].copy()

    print("\nDECISION POPULATIONS")
    print("--------------------")
    print(
        f"Accepted BUY MORE: "
        f"{len(accepted)}"
    )
    print(
        f"Rejected BUY MORE → HOLD: "
        f"{len(rejected)}"
    )
    print(
        f"Genuine HOLD: "
        f"{len(genuine_hold)}"
    )

    return accepted, rejected, genuine_hold


def signal_analysis(accepted, rejected):
    print("\n" + "=" * 72)
    print("BUY MORE SELECTION — SIGNAL")
    print("=" * 72)

    rows = []

    for label, frame in (
        ("BUY MORE", accepted),
        ("REJECTED", rejected),
    ):
        grouped = (
            frame
            .groupby(
                "original_signal",
                dropna=False,
            )
            .agg(
                decisions=("ticker", "size"),
                mean_5d=("return_5d", "mean"),
                median_5d=("return_5d", "median"),
                positive_5d=(
                    "return_5d",
                    lambda s: s.gt(0).mean() * 100,
                ),
            )
            .reset_index()
        )

        grouped.insert(0, "population", label)
        rows.append(grouped)

    if rows:
        print(
            pd.concat(
                rows,
                ignore_index=True,
            ).to_string(index=False)
        )


def score_comparison(accepted, rejected):
    print("\n" + "=" * 72)
    print("BUY MORE SELECTION — SCORE COMPARISON")
    print("=" * 72)

    rows = []

    for column in MATCH_COLUMNS:
        accepted_values = pd.to_numeric(
            accepted[column],
            errors="coerce",
        )

        rejected_values = pd.to_numeric(
            rejected[column],
            errors="coerce",
        )

        rows.append(
            {
                "score": column,
                "buy_more_n":
                    accepted_values.notna().sum(),
                "buy_more_mean":
                    accepted_values.mean(),
                "buy_more_median":
                    accepted_values.median(),
                "rejected_n":
                    rejected_values.notna().sum(),
                "rejected_mean":
                    rejected_values.mean(),
                "rejected_median":
                    rejected_values.median(),
            }
        )

    print(
        pd.DataFrame(rows).to_string(
            index=False
        )
    )


def correlation_analysis(frame):
    print("\n" + "=" * 72)
    print("BUY MORE — SCORE × 5D RETURN")
    print("=" * 72)

    rows = []

    for column in MATCH_COLUMNS:
        x = pd.to_numeric(
            frame[column],
            errors="coerce",
        )
        y = frame["return_5d"]

        mask = x.notna() & y.notna()

        if mask.sum() < 3:
            correlation = np.nan
        else:
            correlation = x[mask].corr(
                y[mask]
            )

        rows.append(
            {
                "score": column,
                "n": int(mask.sum()),
                "correlation": correlation,
            }
        )

    print(
        pd.DataFrame(rows).to_string(
            index=False
        )
    )


def standardise_for_matching(
    accepted,
    genuine_hold,
):
    combined = pd.concat(
        [
            accepted.assign(
                _population="BUY MORE"
            ),
            genuine_hold.assign(
                _population="HOLD"
            ),
        ],
        ignore_index=True,
    )

    for column in MATCH_COLUMNS:

        values = pd.to_numeric(
            combined[column],
            errors="coerce",
        )

        median = values.median()
        std = values.std()

        if pd.isna(std) or std == 0:
            std = 1.0

        combined[
            f"{column}_z"
        ] = (
            values - median
        ) / std

    return (
        combined[
            combined["_population"] == "BUY MORE"
        ].copy(),
        combined[
            combined["_population"] == "HOLD"
        ].copy(),
    )


def calculate_distance(
    treated,
    control,
):
    squared_distance = 0.0
    usable_features = 0

    for column in MATCH_COLUMNS:

        a = treated[
            f"{column}_z"
        ]
        b = control[
            f"{column}_z"
        ]

        if pd.isna(a) or pd.isna(b):
            continue

        squared_distance += (
            a - b
        ) ** 2

        usable_features += 1

    if usable_features == 0:
        return np.nan

    return float(
        np.sqrt(squared_distance)
    )


def one_to_one_matching(
    accepted,
    genuine_hold,
):
    """
    Greedy one-to-one matching.

    Each accepted BUY MORE can receive at most one
    genuine HOLD control, and each HOLD can be used
    at most once.

    Same original signal is required.
    """

    treated, controls = (
        standardise_for_matching(
            accepted,
            genuine_hold,
        )
    )

    if treated.empty or controls.empty:
        return pd.DataFrame()

    candidate_pairs = []

    for treated_index, treated_row in (
        treated.iterrows()
    ):

        same_signal = controls[
            controls["original_signal"]
            == treated_row["original_signal"]
        ]

        for control_index, control_row in (
            same_signal.iterrows()
        ):

            distance = calculate_distance(
                treated_row,
                control_row,
            )

            if pd.isna(distance):
                continue

            if distance > MAX_MATCH_DISTANCE:
                continue

            candidate_pairs.append(
                {
                    "distance": distance,
                    "treated_index":
                        treated_index,
                    "control_index":
                        control_index,
                }
            )

    if not candidate_pairs:
        return pd.DataFrame()

    candidate_pairs.sort(
        key=lambda row: row["distance"]
    )

    used_treated = set()
    used_controls = set()
    matches = []

    for pair in candidate_pairs:

        treated_index = pair[
            "treated_index"
        ]
        control_index = pair[
            "control_index"
        ]

        if treated_index in used_treated:
            continue

        if control_index in used_controls:
            continue

        treated_row = treated.loc[
            treated_index
        ]
        control_row = controls.loc[
            control_index
        ]

        matches.append(
            {
                "buy_more_audit_id":
                    treated_row[
                        "audit_decision_id"
                    ],
                "buy_more_ticker":
                    treated_row["ticker"],
                "buy_more_signal":
                    treated_row[
                        "original_signal"
                    ],
                "buy_more_return":
                    treated_row["return_5d"],
                "hold_audit_id":
                    control_row[
                        "audit_decision_id"
                    ],
                "hold_ticker":
                    control_row["ticker"],
                "hold_signal":
                    control_row[
                        "original_signal"
                    ],
                "hold_return":
                    control_row["return_5d"],
                "distance":
                    pair["distance"],
            }
        )

        used_treated.add(
            treated_index
        )
        used_controls.add(
            control_index
        )

    return pd.DataFrame(matches)


def matched_analysis(matches):
    print("\n" + "=" * 72)
    print("ACCEPTED BUY MORE VS GENUINE HOLD")
    print("=" * 72)

    if matches.empty:
        print("No matched observations.")
        return

    frame = matches.copy()

    frame["incremental_return"] = (
        frame["buy_more_return"]
        - frame["hold_return"]
    )

    print(
        f"Matched pairs: "
        f"{len(frame)}"
    )

    print(
        f"BUY MORE mean 5D: "
        f"{format_pct(frame['buy_more_return'].mean())}"
    )

    print(
        f"HOLD mean 5D:     "
        f"{format_pct(frame['hold_return'].mean())}"
    )

    print(
        f"Incremental mean: "
        f"{format_pct(frame['incremental_return'].mean())}"
    )

    print(
        f"Incremental median: "
        f"{format_pct(frame['incremental_return'].median())}"
    )

    print(
        f"BUY MORE beat HOLD: "
        f"{frame['incremental_return'].gt(0).mean() * 100:.2f}%"
    )

    print("\nBY SIGNAL")
    print("---------")

    grouped = (
        frame
        .groupby("buy_more_signal")
        .agg(
            matches=("incremental_return", "size"),
            buy_more_mean=(
                "buy_more_return",
                "mean",
            ),
            hold_mean=(
                "hold_return",
                "mean",
            ),
            incremental_mean=(
                "incremental_return",
                "mean",
            ),
            incremental_median=(
                "incremental_return",
                "median",
            ),
            buy_more_beats_hold=(
                "incremental_return",
                lambda s:
                    s.gt(0).mean() * 100,
            ),
        )
        .reset_index()
    )

    print(
        grouped.to_string(
            index=False
        )
    )

    for threshold in (
        1.0,
        1.5,
        2.0,
    ):
        close = frame[
            frame["distance"] <= threshold
        ]

        print(
            f"\nMATCH DISTANCE <= {threshold}"
        )

        if close.empty:
            print("No matches.")
            continue

        print(
            f"Pairs: {len(close)}"
        )
        print(
            "Incremental mean: "
            f"{format_pct(close['incremental_return'].mean())}"
        )
        print(
            "Incremental median: "
            f"{format_pct(close['incremental_return'].median())}"
        )
        print(
            "BUY MORE beat HOLD: "
            f"{close['incremental_return'].gt(0).mean() * 100:.2f}%"
        )


def rejection_analysis(
    rejected,
    conn,
):
    print("\n" + "=" * 72)
    print("WHY BUY MORE BECAME HOLD")
    print("=" * 72)

    if rejected.empty:
        print("No rejected BUY MORE decisions.")
        return

    ids = rejected[
        "audit_decision_id"
    ].tolist()

    placeholders = ",".join(
        "?" for _ in ids
    )

    reasons = pd.read_sql_query(
        f"""
        SELECT
            audit_decision_id,
            reason_code
        FROM audit_reasons
        WHERE audit_decision_id IN (
            {placeholders}
        )
        """,
        conn,
        params=ids,
    )

    ignored = {
        "GOVERNANCE_REASON",
        "ACTION_CHANGED",
        "MARKET_INTELLIGENCE_SNAPSHOT",
        "GOVERNANCE_FLAG_DETERMINISTIC_GOVERNANCE_AUTHORITATIVE",
        "GOVERNANCE_FLAG_BUY_MORE_GOVERNANCE_REQUIREMENTS_NOT_MET",
        "GOVERNANCE_FLAG_LLM_CHALLENGE_ADVISORY_ONLY",
        "GOVERNANCE_FLAG_LLM_ADVISORY_ACCEPT",
        "GOVERNANCE_FLAG_LLM_ADVISORY_CHALLENGE",
        "GOVERNANCE_FLAG_LOW_LLM_CONFIDENCE_ADVISORY_ONLY",
    }

    reasons = reasons[
        ~reasons["reason_code"].isin(
            ignored
        )
    ]

    grouped = (
        reasons
        .groupby("reason_code")
        .size()
        .sort_values(
            ascending=False
        )
    )

    if grouped.empty:
        print(
            "No substantive governance "
            "reason codes found."
        )
    else:
        print(
            grouped.to_string()
        )


def main():

    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database not found: {DB_PATH}"
        )

    print("=" * 72)
    print("BUY MORE DECISION FORENSICS — CORRECTED")
    print("=" * 72)
    print("READ-ONLY — NO PRODUCTION CHANGES")

    with sqlite3.connect(DB_PATH) as conn:

        decisions = load_audit_decisions(
            conn
        )

        recommendations = (
            load_recommendations(conn)
        )

        evaluations = (
            load_5d_evaluations(conn)
        )

        print(
            f"\nRaw relevant audit decisions: "
            f"{len(decisions)}"
        )

        decisions = reconstruct_lineage(
            decisions,
            recommendations,
        )

        direct_lineage = (
            decisions[
                "recommendation_id"
            ].notna()
        )

        reconstructed_lineage = (
            decisions[
                "recommendation_id"
            ].isna()
            & decisions[
                "lineage_recommendation_id"
            ].notna()
        )

        print(
            f"Direct lineage: "
            f"{direct_lineage.sum()}"
        )

        print(
            f"Reconstructed legacy lineage: "
            f"{reconstructed_lineage.sum()}"
        )

        decisions = attach_outcomes(
            decisions,
            evaluations,
        )

        decisions = clean_population(
            decisions
        )

        accepted, rejected, genuine_hold = (
            classify_populations(
                decisions
            )
        )

        print_outcome_summary(
            "ACCEPTED BUY MORE",
            accepted,
        )

        print_outcome_summary(
            "REJECTED BUY MORE → HOLD",
            rejected,
        )

        print_outcome_summary(
            "GENUINE HOLD",
            genuine_hold,
        )

        signal_analysis(
            accepted,
            rejected,
        )

        score_comparison(
            accepted,
            rejected,
        )

        correlation_analysis(
            accepted
        )

        rejection_analysis(
            rejected,
            conn,
        )

        matches = one_to_one_matching(
            accepted,
            genuine_hold,
        )

        matched_analysis(
            matches
        )


if __name__ == "__main__":
    main()
