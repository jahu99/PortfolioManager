"""
Non-production BUY MORE regime analysis.

READ-ONLY.

Purpose
-------
Investigate whether BUY MORE performance depends on:

    - original signal
    - Investment Score
    - Evidence Score
    - Confidence Score
    - Technical Score
    - Quality Score
    - Growth Score
    - interactions between signal and scores
    - temporal stability

This analysis does NOT change:
    - production code
    - governance
    - thresholds
    - database contents
    - reports

Population
----------
Accepted BUY MORE:
    proposed_action = BUY MORE
    final_action    = BUY MORE

Rejected BUY MORE:
    proposed_action = BUY MORE
    final_action    = HOLD

Genuine HOLD:
    proposed_action = HOLD
    final_action    = HOLD

Rejected BUY MORE decisions are used to understand the selection /
governance boundary.

Genuine HOLD decisions are used only for the separate comparison
against accepted BUY MORE.

Historical audit decisions without recommendation_id are linked to
the latest recommendation for the same ticker on or before the
audit date, consistent with the existing forensic lineage approach.

Important:
----------
The results are exploratory evidence, not causal estimates.
No production change should be made from this script alone.
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

SCORES = [
    "investment_score",
    "evidence_score",
    "confidence_score",
    "technical_score",
    "quality_score",
    "growth_score",
]

MIN_GROUP_SIZE = 8


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


def load_audit_decisions(conn):
    return pd.read_sql_query(
        """
        SELECT
            id AS audit_decision_id,
            audit_run_id,
            ticker,
            asset_type,
            created_at,
            proposed_action,
            final_action,
            original_signal,
            investment_score,
            technical_score,
            quality_score,
            growth_score,
            confidence_score,
            evidence_score,
            recommendation_id
        FROM audit_decisions
        WHERE proposed_action IN ('BUY MORE', 'HOLD')
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
            ticker
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


def reconstruct_lineage(
    decisions,
    recommendations,
):
    decisions = decisions.copy()

    by_ticker = {
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

        candidates = by_ticker.get(
            decision["ticker"]
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
            candidates["recommendation_day"]
            <= audit_day
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
            return_percent
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
        }
    )

    return decisions.merge(
        evaluations[
            [
                "lineage_recommendation_id",
                "return_5d",
            ]
        ],
        on="lineage_recommendation_id",
        how="left",
    )


def clean_population(frame):
    frame = frame.copy()

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

    for column in SCORES:
        frame[column] = pd.to_numeric(
            frame[column],
            errors="coerce",
        )

    frame["decision_date"] = pd.to_datetime(
        frame["created_at"],
        errors="coerce",
        utc=True,
    )

    return frame


def split_populations(frame):
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

    return accepted, rejected, genuine_hold


def summary(label, frame):
    print(f"\n{label}")
    print("-" * len(label))

    if frame.empty:
        print("No data.")
        return

    print(f"N:          {len(frame)}")
    print(
        f"Mean 5D:    "
        f"{format_pct(frame['return_5d'].mean())}"
    )
    print(
        f"Median 5D:  "
        f"{format_pct(frame['return_5d'].median())}"
    )
    print(
        f"Positive:   "
        f"{frame['return_5d'].gt(0).mean() * 100:.2f}%"
    )


def signal_regime_analysis(
    accepted,
    rejected,
):
    print("\n" + "=" * 72)
    print("1. SIGNAL REGIME ANALYSIS")
    print("=" * 72)

    rows = []

    for label, frame in (
        ("ACCEPTED BUY MORE", accepted),
        ("REJECTED BUY MORE", rejected),
    ):

        grouped = (
            frame
            .groupby(
                "original_signal",
                dropna=False,
            )
            .agg(
                n=("ticker", "size"),
                mean_5d=("return_5d", "mean"),
                median_5d=(
                    "return_5d",
                    "median",
                ),
                positive_5d=(
                    "return_5d",
                    lambda s:
                        s.gt(0).mean() * 100,
                ),
            )
            .reset_index()
        )

        grouped.insert(
            0,
            "population",
            label,
        )

        rows.append(grouped)

    print(
        pd.concat(
            rows,
            ignore_index=True,
        ).to_string(index=False)
    )


def score_distribution_comparison(
    accepted,
    rejected,
):
    print("\n" + "=" * 72)
    print("2. SCORE DISTRIBUTION — ACCEPTED VS REJECTED")
    print("=" * 72)

    rows = []

    for score in SCORES:

        a = accepted[score].dropna()
        r = rejected[score].dropna()

        rows.append(
            {
                "score": score,
                "accepted_n": len(a),
                "accepted_mean": a.mean(),
                "accepted_median": a.median(),
                "accepted_min": a.min(),
                "accepted_max": a.max(),
                "rejected_n": len(r),
                "rejected_mean": r.mean(),
                "rejected_median": r.median(),
                "rejected_min": r.min(),
                "rejected_max": r.max(),
                "mean_difference":
                    a.mean() - r.mean(),
            }
        )

    print(
        pd.DataFrame(rows).to_string(
            index=False
        )
    )


def make_score_bands(
    frame,
    score,
):
    frame = frame.copy()

    values = frame[score]

    # Use quantiles from the BUY MORE population
    # itself, rather than arbitrary production thresholds.
    try:
        quantiles = values.quantile(
            [0, 0.25, 0.50, 0.75, 1.0]
        ).drop_duplicates()

        if len(quantiles) < 3:
            return frame, None

        labels = [
            "Q1",
            "Q2",
            "Q3",
            "Q4",
        ]

        labels = labels[
            : len(quantiles) - 1
        ]

        frame[
            f"{score}_quartile"
        ] = pd.cut(
            values,
            bins=quantiles,
            labels=labels,
            include_lowest=True,
            duplicates="drop",
        )

        return frame, f"{score}_quartile"

    except ValueError:
        return frame, None


def score_regime_analysis(
    accepted,
):
    print("\n" + "=" * 72)
    print("3. SCORE QUARTILES WITHIN ACCEPTED BUY MORE")
    print("=" * 72)

    for score in SCORES:

        frame, band_column = make_score_bands(
            accepted,
            score,
        )

        if band_column is None:
            continue

        grouped = (
            frame
            .groupby(
                band_column,
                observed=False,
            )
            .agg(
                n=("ticker", "size"),
                mean_score=(score, "mean"),
                mean_5d=("return_5d", "mean"),
                median_5d=(
                    "return_5d",
                    "median",
                ),
                positive_5d=(
                    "return_5d",
                    lambda s:
                        s.gt(0).mean() * 100,
                ),
            )
            .reset_index()
        )

        grouped = grouped[
            grouped["n"] >= MIN_GROUP_SIZE
        ]

        print(f"\n{score.upper()}")
        print("-" * len(score))
        print(
            grouped.to_string(
                index=False
            )
        )


def interaction_analysis(
    accepted,
):
    print("\n" + "=" * 72)
    print("4. SIGNAL × SCORE INTERACTIONS")
    print("=" * 72)

    for score in SCORES:

        frame, band_column = make_score_bands(
            accepted,
            score,
        )

        if band_column is None:
            continue

        grouped = (
            frame
            .groupby(
                [
                    "original_signal",
                    band_column,
                ],
                observed=False,
            )
            .agg(
                n=("ticker", "size"),
                mean_score=(score, "mean"),
                mean_5d=("return_5d", "mean"),
                median_5d=(
                    "return_5d",
                    "median",
                ),
                positive_5d=(
                    "return_5d",
                    lambda s:
                        s.gt(0).mean() * 100,
                ),
            )
            .reset_index()
        )

        grouped = grouped[
            grouped["n"] >= MIN_GROUP_SIZE
        ]

        print(f"\n{score.upper()}")
        print("-" * len(score))
        print(
            grouped.to_string(
                index=False
            )
        )


def pairwise_interactions(
    accepted,
):
    print("\n" + "=" * 72)
    print("5. TWO-SCORE INTERACTIONS")
    print("=" * 72)

    selected_pairs = [
        (
            "investment_score",
            "evidence_score",
        ),
        (
            "investment_score",
            "confidence_score",
        ),
        (
            "evidence_score",
            "confidence_score",
        ),
        (
            "technical_score",
            "evidence_score",
        ),
        (
            "quality_score",
            "growth_score",
        ),
        (
            "technical_score",
            "growth_score",
        ),
    ]

    for first, second in selected_pairs:

        frame = accepted.copy()

        frame, first_band = (
            make_score_bands(
                frame,
                first,
            )
        )

        frame, second_band = (
            make_score_bands(
                frame,
                second,
            )
        )

        if (
            first_band is None
            or second_band is None
        ):
            continue

        grouped = (
            frame
            .groupby(
                [
                    first_band,
                    second_band,
                ],
                observed=False,
            )
            .agg(
                n=("ticker", "size"),
                mean_5d=(
                    "return_5d",
                    "mean",
                ),
                median_5d=(
                    "return_5d",
                    "median",
                ),
                positive_5d=(
                    "return_5d",
                    lambda s:
                        s.gt(0).mean() * 100,
                ),
            )
            .reset_index()
        )

        grouped = grouped[
            grouped["n"] >= MIN_GROUP_SIZE
        ]

        print(
            f"\n{first.upper()} × "
            f"{second.upper()}"
        )
        print("-" * (
            len(first)
            + len(second)
            + 3
        ))

        print(
            grouped.to_string(
                index=False
            )
        )


def temporal_stability(
    accepted,
):
    print("\n" + "=" * 72)
    print("6. TEMPORAL STABILITY")
    print("=" * 72)

    frame = accepted.copy()

    frame = frame[
        frame["decision_date"].notna()
    ].sort_values(
        "decision_date"
    )

    if len(frame) < 20:
        print(
            "Insufficient observations "
            "for temporal split."
        )
        return

    midpoint = len(frame) // 2

    early = frame.iloc[
        :midpoint
    ]

    late = frame.iloc[
        midpoint:
    ]

    rows = []

    for label, period in (
        ("EARLY", early),
        ("LATE", late),
    ):
        rows.append(
            {
                "period": label,
                "n": len(period),
                "start":
                    period[
                        "decision_date"
                    ].min(),
                "end":
                    period[
                        "decision_date"
                    ].max(),
                "mean_5d":
                    period[
                        "return_5d"
                    ].mean(),
                "median_5d":
                    period[
                        "return_5d"
                    ].median(),
                "positive_5d":
                    period[
                        "return_5d"
                    ].gt(0).mean()
                    * 100,
            }
        )

    print(
        pd.DataFrame(rows).to_string(
            index=False
        )
    )

    print("\nBY SIGNAL")
    print("---------")

    rows = []

    for period_name, period in (
        ("EARLY", early),
        ("LATE", late),
    ):

        grouped = (
            period
            .groupby(
                "original_signal",
                dropna=False,
            )
            .agg(
                n=("ticker", "size"),
                mean_5d=(
                    "return_5d",
                    "mean",
                ),
                median_5d=(
                    "return_5d",
                    "median",
                ),
                positive_5d=(
                    "return_5d",
                    lambda s:
                        s.gt(0).mean() * 100,
                ),
            )
            .reset_index()
        )

        grouped.insert(
            0,
            "period",
            period_name,
        )

        rows.append(grouped)

    print(
        pd.concat(
            rows,
            ignore_index=True,
        ).to_string(index=False)
    )


def compare_to_genuine_hold(
    accepted,
    genuine_hold,
):
    print("\n" + "=" * 72)
    print("7. ACCEPTED BUY MORE VS GENUINE HOLD")
    print("=" * 72)

    # We deliberately use a broader matching model than
    # the previous test. Exact one-to-one matching on all
    # six scores produced only 14 observations.
    #
    # Here we match on:
    #   - same original signal
    #   - nearest Investment + Evidence + Technical
    #
    # Confidence, Quality and Growth remain available
    # for analysis but are not hard matching constraints.

    required = [
        "investment_score",
        "evidence_score",
        "technical_score",
    ]

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

    for column in required:
        values = pd.to_numeric(
            combined[column],
            errors="coerce",
        )

        std = values.std()

        if pd.isna(std) or std == 0:
            std = 1.0

        combined[
            f"{column}_z"
        ] = (
            values - values.mean()
        ) / std

    treated = combined[
        combined["_population"] == "BUY MORE"
    ].copy()

    controls = combined[
        combined["_population"] == "HOLD"
    ].copy()

    candidate_pairs = []

    for treated_index, treated_row in (
        treated.iterrows()
    ):

        candidates = controls[
            controls["original_signal"]
            == treated_row["original_signal"]
        ]

        for control_index, control_row in (
            candidates.iterrows()
        ):

            distances = []

            for column in required:
                a = treated_row[
                    f"{column}_z"
                ]
                b = control_row[
                    f"{column}_z"
                ]

                if pd.isna(a) or pd.isna(b):
                    continue

                distances.append(
                    (a - b) ** 2
                )

            if len(distances) != len(required):
                continue

            distance = float(
                np.sqrt(
                    sum(distances)
                )
            )

            candidate_pairs.append(
                {
                    "distance": distance,
                    "treated_index":
                        treated_index,
                    "control_index":
                        control_index,
                }
            )

    candidate_pairs.sort(
        key=lambda row:
            row["distance"]
    )

    used_treated = set()
    used_controls = set()
    matches = []

    for pair in candidate_pairs:

        ti = pair["treated_index"]
        ci = pair["control_index"]

        if ti in used_treated:
            continue

        if ci in used_controls:
            continue

        treated_row = treated.loc[ti]
        control_row = controls.loc[ci]

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
                "hold_return":
                    control_row["return_5d"],
                "distance":
                    pair["distance"],
            }
        )

        used_treated.add(ti)
        used_controls.add(ci)

    matches = pd.DataFrame(matches)

    if matches.empty:
        print("No matches.")
        return

    matches["incremental_return"] = (
        matches["buy_more_return"]
        - matches["hold_return"]
    )

    print(
        f"One-to-one matched pairs: "
        f"{len(matches)}"
    )

    print(
        f"BUY MORE mean 5D: "
        f"{format_pct(matches['buy_more_return'].mean())}"
    )

    print(
        f"HOLD mean 5D:     "
        f"{format_pct(matches['hold_return'].mean())}"
    )

    print(
        f"Incremental mean: "
        f"{format_pct(matches['incremental_return'].mean())}"
    )

    print(
        f"Incremental median: "
        f"{format_pct(matches['incremental_return'].median())}"
    )

    print(
        f"BUY MORE beat HOLD: "
        f"{matches['incremental_return'].gt(0).mean() * 100:.2f}%"
    )

    print("\nMATCH QUALITY")

    for threshold in (
        1.0,
        1.5,
        2.0,
        2.5,
        3.0,
    ):

        close = matches[
            matches["distance"] <= threshold
        ]

        if close.empty:
            print(
                f"Distance <= {threshold}: "
                "0 pairs"
            )
            continue

        print(
            f"Distance <= {threshold}: "
            f"{len(close)} pairs | "
            f"incremental mean "
            f"{format_pct(close['incremental_return'].mean())} | "
            f"median "
            f"{format_pct(close['incremental_return'].median())} | "
            f"BUY MORE wins "
            f"{close['incremental_return'].gt(0).mean() * 100:.1f}%"
        )

    print("\nBY SIGNAL")

    grouped = (
        matches
        .groupby(
            "buy_more_signal",
            dropna=False,
        )
        .agg(
            pairs=("incremental_return", "size"),
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
            buy_more_wins=(
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


def main():

    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database not found: {DB_PATH}"
        )

    print("=" * 72)
    print("BUY MORE REGIME ANALYSIS")
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

        decisions = reconstruct_lineage(
            decisions,
            recommendations,
        )

        decisions = attach_outcomes(
            decisions,
            evaluations,
        )

        decisions = clean_population(
            decisions
        )

        accepted, rejected, genuine_hold = (
            split_populations(
                decisions
            )
        )

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

        summary(
            "ACCEPTED BUY MORE",
            accepted,
        )

        summary(
            "REJECTED BUY MORE → HOLD",
            rejected,
        )

        summary(
            "GENUINE HOLD",
            genuine_hold,
        )

        signal_regime_analysis(
            accepted,
            rejected,
        )

        score_distribution_comparison(
            accepted,
            rejected,
        )

        score_regime_analysis(
            accepted,
        )

        interaction_analysis(
            accepted,
        )

        pairwise_interactions(
            accepted,
        )

        temporal_stability(
            accepted,
        )

        compare_to_genuine_hold(
            accepted,
            genuine_hold,
        )


if __name__ == "__main__":
    main()
