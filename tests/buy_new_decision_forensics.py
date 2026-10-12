# tests/buy_new_decision_forensics.py

"""
BUY NEW decision forensics.

READ-ONLY.
No production changes.

Purpose:
    Establish the historical BUY NEW population, reconstruct
    legacy recommendation lineage, attach realised 5D outcomes,
    and report the usable mature population.

This is an A6 calibration investigation only.
"""

from pathlib import Path

import sqlite3

import numpy as np
import pandas as pd


DB_PATH = Path(
    "data/portfolio_manager.db"
)

HORIZON = 5


def normalise_day(value):
    if value is None:
        return None

    try:
        timestamp = pd.to_datetime(
            value,
            errors="coerce",
        )

        if pd.isna(timestamp):
            return None

        return timestamp.strftime("%Y-%m-%d")

    except Exception:
        return None 

def load_audit_decisions(conn):

    return pd.read_sql_query(
        """
        SELECT
            id,
            audit_run_id,
            created_at,
            ticker,
            original_action,
            proposed_action,
            reconciled_action,
            final_action,
            recommendation_id
        FROM audit_decisions
        WHERE final_action = 'BUY NEW'
        """,
        conn,
    )


def load_recommendations(conn):

    recommendations = pd.read_sql_query(
        """
        SELECT
            id AS recommendation_id,
            ticker,
            date AS recommendation_day
        FROM recommendations
        WHERE ticker IS NOT NULL
        """,
        conn,
    )

    recommendations["recommendation_day"] = (
        pd.to_datetime(
            recommendations["recommendation_day"],
            errors="coerce",
        ).dt.strftime("%Y-%m-%d")
    )

    return recommendations

def reconstruct_lineage(
    decisions,
    recommendations,
):

    decisions = decisions.copy()

    recommendations_by_ticker = {
        ticker: group.sort_values(
            [
                "recommendation_day",
                "recommendation_id",
            ]
        )
        for ticker, group
        in recommendations.groupby("ticker")
    }

    lineage = []

    for _, decision in decisions.iterrows():

        if pd.notna(
            decision["recommendation_id"]
        ):
            lineage.append(
                decision["recommendation_id"]
            )
            continue

        ticker = decision["ticker"]

        candidates = (
            recommendations_by_ticker.get(
                ticker
            )
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
            candidates[
                "recommendation_day"
            ] <= audit_day
        ]

        if candidates.empty:
            lineage.append(np.nan)
            continue

        lineage.append(
            candidates.iloc[-1][
                "recommendation_id"
            ]
        )

    decisions[
        "lineage_recommendation_id"
    ] = lineage

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


def attach_outcomes(
    decisions,
    evaluations,
):

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
            subset=[
                "recommendation_id"
            ],
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
    )

    frame = frame[
        frame["ticker"] != ""
    ].copy()

    return frame


def print_summary(decisions):

    direct = (
        decisions[
            "recommendation_id"
        ].notna()
    )

    reconstructed = (
        decisions[
            "recommendation_id"
        ].isna()
        & decisions[
            "lineage_recommendation_id"
        ].notna()
    )

    unresolved = (
        decisions[
            "lineage_recommendation_id"
        ].isna()
    )

    realised = (
        decisions[
            "return_5d"
        ].notna()
    )

    print()
    print("=" * 72)
    print(
        "BUY NEW DECISION FORENSICS"
    )
    print("=" * 72)
    print(
        "READ-ONLY — NO PRODUCTION CHANGES"
    )

    print()
    print("LINEAGE")
    print("-" * 72)

    print(
        f"Raw BUY NEW decisions:       "
        f"{len(decisions)}"
    )

    print(
        f"Direct lineage:               "
        f"{direct.sum()}"
    )

    print(
        f"Reconstructed legacy lineage: "
        f"{reconstructed.sum()}"
    )

    print(
        f"Unresolved lineage:           "
        f"{unresolved.sum()}"
    )

    print()
    print("5D OUTCOMES")
    print("-" * 72)

    print(
        f"With realised 5D outcome:     "
        f"{realised.sum()}"
    )

    print(
        f"Without realised 5D outcome:  "
        f"{(~realised).sum()}"
    )

    if realised.any():

        realised_returns = (
            decisions.loc[
                realised,
                "return_5d",
            ]
        )

        print(
            f"Mean 5D return:              "
            f"{realised_returns.mean():+.3f}%"
        )

        print(
            f"Median 5D return:            "
            f"{realised_returns.median():+.3f}%"
        )

        print(
            f"Positive 5D outcomes:        "
            f"{(
                realised_returns > 0
            ).mean() * 100:.2f}%"
        )

    print()
    print("LINEAGE × OUTCOME")
    print("-" * 72)

    for label, mask in [
        (
            "Direct",
            direct,
        ),
        (
            "Reconstructed",
            reconstructed,
        ),
        (
            "Unresolved",
            unresolved,
        ),
    ]:

        subset = decisions[
            mask
        ]

        realised_subset = subset[
            subset[
                "return_5d"
            ].notna()
        ]

        if realised_subset.empty:

            print(
                f"{label:15} "
                f"population={len(subset):4} "
                f"mature=0"
            )

            continue

        returns = (
            realised_subset[
                "return_5d"
            ]
        )

        print(
            f"{label:15} "
            f"population={len(subset):4} "
            f"mature={len(returns):4} "
            f"mean={returns.mean():+.3f}% "
            f"median={returns.median():+.3f}% "
            f"positive={(returns > 0).mean() * 100:.2f}%"
        )

    print()
    print("BUY NEW BY TICKER")
    print("-" * 72)

    ticker_summary = (
        decisions[
            decisions[
                "return_5d"
            ].notna()
        ]
        .groupby("ticker")[
            "return_5d"
        ]
        .agg(
            count="count",
            mean="mean",
            median="median",
        )
        .sort_values(
            "count",
            ascending=False,
        )
    )

    if ticker_summary.empty:

        print(
            "No mature BUY NEW outcomes."
        )

    else:

        print(
            ticker_summary.to_string(
                float_format=lambda x:
                    f"{x:+.3f}"
            )
        )

    print()
    print("=" * 72)


def main():

    if not DB_PATH.exists():

        raise FileNotFoundError(
            f"Database not found: "
            f"{DB_PATH}"
        )

    with sqlite3.connect(
        DB_PATH
    ) as conn:

        decisions = (
            load_audit_decisions(
                conn
            )
        )

        recommendations = (
            load_recommendations(
                conn
            )
        )

        evaluations = (
            load_5d_evaluations(
                conn
            )
        )

        decisions = (
            reconstruct_lineage(
                decisions,
                recommendations,
            )
        )

        decisions = (
            attach_outcomes(
                decisions,
                evaluations,
            )
        )

        decisions = (
            clean_population(
                decisions
            )
        )

        print_summary(
            decisions
        )


if __name__ == "__main__":
    main()
