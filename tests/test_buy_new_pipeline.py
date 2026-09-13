"""
BUY NEW Production Pipeline Diagnostic.

This diagnostic is read-only.

It traces the authoritative BUY NEW candidate shortlist through:

    Candidate Ranking Snapshot
            ↓
    Portfolio Decisions Snapshot
            ↓
    Final Portfolio Decisions Snapshot

The diagnostic does not modify production decisions.

"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(
    __file__
).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )


from pathlib import Path

import pandas as pd

from analysis.candidate_selection import (
    select_buy_new_candidates,
)


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(
    __file__
).resolve().parent.parent

DATA_DIRECTORY = (
    PROJECT_ROOT / "data"
)

CANDIDATE_SNAPSHOT_FILE = (
    DATA_DIRECTORY
    / "candidate_ranking_snapshot.csv"
)

PORTFOLIO_SNAPSHOT_FILE = (
    DATA_DIRECTORY
    / "candidate_ranking_portfolio_snapshot.csv"
)

PORTFOLIO_DECISIONS_SNAPSHOT_FILE = (
    DATA_DIRECTORY
    / "portfolio_decisions_snapshot.csv"
)

FINAL_PORTFOLIO_DECISIONS_SNAPSHOT_FILE = (
    DATA_DIRECTORY
    / "final_portfolio_decisions_snapshot.csv"
)


# ============================================================
# DISPLAY
# ============================================================

SEPARATOR = "=" * 100


# ============================================================
# HELPERS
# ============================================================

def clean_ticker(
    value,
):

    if pd.isna(
        value
    ):

        return ""

    return str(
        value
    ).strip().upper()


def load_csv(
    path,
    description,
):

    if not path.exists():

        raise FileNotFoundError(

            f"{description} not found:\n"

            f"{path}\n\n"

            "Run python main.py first to create "
            "fresh production snapshots."

        )

    return pd.read_csv(
        path
    )


def get_value(
    row,
    column,
    default="",
):

    if column not in row.index:

        return default

    value = row.get(
        column
    )

    if pd.isna(
        value
    ):

        return default

    return value


def build_lookup(
    df,
):

    if df is None:

        return {}

    if df.empty:

        return {}

    if "Ticker" not in df.columns:

        return {}

    lookup = {}

    for _, row in df.iterrows():

        ticker = clean_ticker(
            row.get(
                "Ticker",
                ""
            )
        )

        if not ticker:

            continue

        lookup[ticker] = (
            row.to_dict()
        )

    return lookup


# ============================================================
# ENTRY QUALITY
# ============================================================

def get_entry_quality(
    row,
):

    for column in (

        "Entry Timing Status",

        "Entry Quality",

        "Candidate Status",

    ):

        if column in row.index:

            value = get_value(
                row,
                column,
                ""
            )

            if value:

                return value

    return "UNKNOWN"


# ============================================================
# DIAGNOSTIC
# ============================================================

def run_buy_new_pipeline_diagnostic():

    print()
    print(
        SEPARATOR
    )
    print(
        "BUY NEW PRODUCTION PIPELINE DIAGNOSTIC"
    )
    print(
        SEPARATOR
    )

    # --------------------------------------------------------
    # Load production snapshots
    # --------------------------------------------------------

    results = load_csv(

        CANDIDATE_SNAPSHOT_FILE,

        "Candidate ranking snapshot",

    )

    portfolio_summary = load_csv(

        PORTFOLIO_SNAPSHOT_FILE,

        "Portfolio snapshot",

    )

    portfolio_decisions = load_csv(

        PORTFOLIO_DECISIONS_SNAPSHOT_FILE,

        "Portfolio decisions snapshot",

    )

    final_portfolio_decisions = load_csv(

        FINAL_PORTFOLIO_DECISIONS_SNAPSHOT_FILE,

        "Final portfolio decisions snapshot",

    )

    # --------------------------------------------------------
    # Recreate authoritative candidate shortlist
    # --------------------------------------------------------

    candidates = (
        select_buy_new_candidates(
            results
        )
    )

    if candidates is None:

        candidates = pd.DataFrame()

    if candidates.empty:

        print()
        print(
            "No BUY NEW candidates were produced."
        )

        return

    candidates = candidates.copy()

    # --------------------------------------------------------
    # Ensure tickers are normalised
    # --------------------------------------------------------

    candidates["Ticker"] = (
        candidates["Ticker"]
        .apply(
            clean_ticker
        )
    )

    # --------------------------------------------------------
    # Investment rank
    # --------------------------------------------------------

    if "Investment Rank" not in candidates.columns:

        if "Investment Score" in candidates.columns:

            candidates[
                "Investment Score"
            ] = pd.to_numeric(

                candidates[
                    "Investment Score"
                ],

                errors="coerce",

            )

            candidates = (
                candidates
                .sort_values(

                    "Investment Score",

                    ascending=False,

                )
                .reset_index(
                    drop=True
                )
            )

        candidates.insert(

            0,

            "Investment Rank",

            range(
                1,
                len(candidates) + 1
            ),

        )

    # --------------------------------------------------------
    # Build production lookups
    # --------------------------------------------------------

    portfolio_lookup = (
        build_lookup(
            portfolio_decisions
        )
    )

    final_lookup = (
        build_lookup(
            final_portfolio_decisions
        )
    )

    # ========================================================
    # AUTHORITATIVE CANDIDATES
    # ========================================================

    print()
    print(
        SEPARATOR
    )
    print(
        "1. AUTHORITATIVE TOP BUY NEW CANDIDATES"
    )
    print(
        SEPARATOR
    )
    print()

    display_rows = []

    for _, row in candidates.iterrows():

        display_rows.append({

            "Investment Rank":

                get_value(
                    row,
                    "Investment Rank",
                    ""
                ),

            "Ticker":

                get_value(
                    row,
                    "Ticker",
                    ""
                ),

            "Name":

                get_value(
                    row,
                    "Name",
                    ""
                ),

            "Sector":

                get_value(
                    row,
                    "Sector",
                    ""
                ),

            "Investment Score":

                get_value(
                    row,
                    "Investment Score",
                    ""
                ),

            "Signal":

                get_value(
                    row,
                    "Signal",
                    ""
                ),

            "Entry Quality":

                get_entry_quality(
                    row
                ),

        })

    display_candidates = pd.DataFrame(
        display_rows
    )

    print(
        display_candidates.to_string(
            index=False
        )
    )

    # ========================================================
    # PIPELINE TRACE
    # ========================================================

    print()
    print(
        SEPARATOR
    )
    print(
        "2. COMPLETE PRODUCTION PIPELINE TRACE"
    )
    print(
        SEPARATOR
    )
    print()

    trace_rows = []

    reached_portfolio = 0

    portfolio_buy_new = 0

    reached_final = 0

    final_buy_new = 0

    final_changed = 0

    lost_before_portfolio = 0

    lost_before_final = 0

    for _, row in candidates.iterrows():

        ticker = clean_ticker(
            get_value(
                row,
                "Ticker",
                ""
            )
        )

        investment_rank = get_value(
            row,
            "Investment Rank",
            ""
        )

        investment_score = get_value(
            row,
            "Investment Score",
            ""
        )

        signal = get_value(
            row,
            "Signal",
            ""
        )

        entry_quality = get_entry_quality(
            row
        )

        portfolio_record = (
            portfolio_lookup.get(
                ticker
            )
        )

        final_record = (
            final_lookup.get(
                ticker
            )
        )

        in_portfolio = (
            portfolio_record
            is not None
        )

        in_final = (
            final_record
            is not None
        )

        portfolio_action = ""

        proposed_action = ""

        reconciled_decision = ""

        final_decision = ""

        decision_status = ""

        final_reason = ""

        if in_portfolio:

            reached_portfolio += 1

            portfolio_action = (
                portfolio_record.get(
                    "Action",
                    ""
                )
            )

            if (
                str(
                    portfolio_action
                ).strip().upper()
                ==
                "BUY NEW"
            ):

                portfolio_buy_new += 1

        else:

            lost_before_portfolio += 1

        if in_final:

            reached_final += 1

            proposed_action = (
                final_record.get(
                    "Proposed Action",
                    ""
                )
            )

            reconciled_decision = (
                final_record.get(
                    "Reconciled Decision",
                    ""
                )
            )

            final_decision = (
                final_record.get(
                    "Final Decision",
                    ""
                )
            )

            decision_status = (
                final_record.get(
                    "Decision Status",
                    ""
                )
            )

            final_reason = (
                final_record.get(
                    "Final Reason",
                    ""
                )
            )

            if (
                str(
                    final_decision
                ).strip().upper()
                ==
                "BUY NEW"
            ):

                final_buy_new += 1

            if (

                str(
                    portfolio_action
                ).strip().upper()

                !=

                str(
                    final_decision
                ).strip().upper()

            ):

                final_changed += 1

        elif in_portfolio:

            lost_before_final += 1

        # ----------------------------------------------------
        # Pipeline status
        # ----------------------------------------------------

        if not in_portfolio:

            pipeline_status = (
                "LOST BEFORE PORTFOLIO DECISIONS"
            )

        elif not in_final:

            pipeline_status = (
                "LOST BEFORE FINAL PORTFOLIO DECISIONS"
            )

        elif (
            str(
                portfolio_action
            ).strip().upper()

            ==

            str(
                final_decision
            ).strip().upper()

        ):

            pipeline_status = (
                "FINAL DECISION CONFIRMED"
            )

        else:

            pipeline_status = (
                "ACTION CHANGED IN FINAL GOVERNANCE"
            )

        trace_rows.append({

            "Investment Rank":

                investment_rank,

            "Ticker":

                ticker,

            "Investment Score":

                investment_score,

            "Signal":

                signal,

            "Entry Quality":

                entry_quality,

            "Portfolio Action":

                portfolio_action,

            "Proposed Action":

                proposed_action,

            "Reconciled Decision":

                reconciled_decision,

            "Final Decision":

                final_decision,

            "Decision Status":

                decision_status,

            "Pipeline Status":

                pipeline_status,

        })

    trace_df = pd.DataFrame(
        trace_rows
    )

    print(
        trace_df.to_string(
            index=False
        )
    )

    # ========================================================
    # FINAL GOVERNANCE CHANGES
    # ========================================================

    changed_df = trace_df[

        trace_df[
            "Pipeline Status"
        ]

        ==

        "ACTION CHANGED IN FINAL GOVERNANCE"

    ].copy()

    print()
    print(
        SEPARATOR
    )
    print(
        "3. BUY NEW GOVERNANCE OVERRIDES"
    )
    print(
        SEPARATOR
    )
    print()

    if changed_df.empty:

        print(
            "No candidate actions were changed "
            "by the final governance layer."
        )

    else:

        print(

            changed_df[

                [

                    "Investment Rank",

                    "Ticker",

                    "Investment Score",

                    "Portfolio Action",

                    "Proposed Action",

                    "Reconciled Decision",

                    "Final Decision",

                    "Decision Status",

                ]

            ].to_string(
                index=False
            )

        )

    # ========================================================
    # SUMMARY
    # ========================================================

    print()
    print(
        SEPARATOR
    )
    print(
        "PIPELINE SUMMARY"
    )
    print(
        SEPARATOR
    )
    print()

    print(
        f"Top BUY NEW candidates tested: "
        f"{len(candidates)}"
    )

    print(
        f"Reached Portfolio Decisions: "
        f"{reached_portfolio}"
    )

    print(
        f"BUY NEW decisions produced: "
        f"{portfolio_buy_new}"
    )

    print(
        f"Reached Final Portfolio Decisions: "
        f"{reached_final}"
    )

    print(
        f"Final BUY NEW decisions retained: "
        f"{final_buy_new}"
    )

    print(
        f"Actions changed by final governance: "
        f"{final_changed}"
    )

    print(
        f"Lost before Portfolio Decisions: "
        f"{lost_before_portfolio}"
    )

    print(
        f"Lost before Final Portfolio Decisions: "
        f"{lost_before_final}"
    )

    print()
    print(
        "This diagnostic identifies where top "
        "BUY NEW candidates disappear or change "
        "through the production pipeline."
    )

    print()
    print(
        "IMPORTANT: This diagnostic does not "
        "modify production decisions."
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    run_buy_new_pipeline_diagnostic()