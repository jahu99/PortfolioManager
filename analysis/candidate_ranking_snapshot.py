"""
Candidate Ranking Snapshot

Purpose
-------

Persists a read-only snapshot of the live investment scan and the
current portfolio summary.

The snapshot exists solely to support offline diagnostics of the
BUY NEW candidate selection pipeline.

It does NOT modify:

    - Investment Score
    - Technical Score
    - Quality Score
    - Growth Score
    - Signals
    - Recommendations
    - Portfolio decisions
    - Final decisions
    - Capital allocation
    - Governance
    - Learning

Architecture
------------

Live Scan Results
        +
Portfolio Summary
        ↓
Diagnostic Snapshot
        ↓
tests/test_candidate_ranking.py

The snapshot allows the candidate-ranking diagnostic to analyse the
exact live scan universe without importing or executing main.py.

Files
-----

The latest snapshot is written to:

    data/candidate_ranking_snapshot.csv

The portfolio snapshot is written to:

    data/candidate_ranking_portfolio_snapshot.csv

"""

from pathlib import Path

import pandas as pd


# ============================================================
# CONFIGURATION
# ============================================================

DATA_DIRECTORY = Path("data")

CANDIDATE_SNAPSHOT_FILE = (
    DATA_DIRECTORY
    / "candidate_ranking_snapshot.csv"
)

PORTFOLIO_SNAPSHOT_FILE = (
    DATA_DIRECTORY
    / "candidate_ranking_portfolio_snapshot.csv"
)

PORTFOLIO_DECISIONS_SNAPSHOT_FILE = (
    DATA_DIRECTORY /
    "portfolio_decisions_snapshot.csv"
)

FINAL_PORTFOLIO_DECISIONS_SNAPSHOT_FILE = (
    DATA_DIRECTORY /
    "final_portfolio_decisions_snapshot.csv"
)

# ============================================================
# HELPERS
# ============================================================

def save_candidate_ranking_snapshot(
    results,
    portfolio_summary,
):
    """
    Save the live scan universe and portfolio summary for
    offline candidate-ranking diagnostics.

    Parameters
    ----------

    results:
        Iterable of stock analysis dictionaries or a DataFrame.

    portfolio_summary:
        Current portfolio summary DataFrame or compatible object.

    Returns
    -------

    tuple

        (
            candidate_snapshot_path,
            portfolio_snapshot_path
        )

    """

    # --------------------------------------------------------
    # Ensure data directory exists
    # --------------------------------------------------------

    DATA_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    # --------------------------------------------------------
    # RESULTS
    # --------------------------------------------------------

    if results is None:

        results_df = pd.DataFrame()

    elif isinstance(
        results,
        pd.DataFrame,
    ):

        results_df = results.copy()

    else:

        results_df = pd.DataFrame(
            results
        )

    # --------------------------------------------------------
    # PORTFOLIO
    # --------------------------------------------------------

    if portfolio_summary is None:

        portfolio_df = pd.DataFrame()

    elif isinstance(
        portfolio_summary,
        pd.DataFrame,
    ):

        portfolio_df = portfolio_summary.copy()

    else:

        portfolio_df = pd.DataFrame(
            portfolio_summary
        )

    # --------------------------------------------------------
    # Save scan snapshot
    # --------------------------------------------------------

    results_df.to_csv(
        CANDIDATE_SNAPSHOT_FILE,
        index=False,
    )

    # --------------------------------------------------------
    # Save portfolio snapshot
    # --------------------------------------------------------

    portfolio_df.to_csv(
        PORTFOLIO_SNAPSHOT_FILE,
        index=False,
    )

    print()

    print(
        "CANDIDATE RANKING SNAPSHOT SAVED"
    )

    print(
        f"Candidates: "
        f"{len(results_df)}"
    )

    print(
        f"Portfolio rows: "
        f"{len(portfolio_df)}"
    )

    print(
        f"Candidate snapshot: "
        f"{CANDIDATE_SNAPSHOT_FILE}"
    )

    print(
        f"Portfolio snapshot: "
        f"{PORTFOLIO_SNAPSHOT_FILE}"
    )

    return (

        CANDIDATE_SNAPSHOT_FILE,

        PORTFOLIO_SNAPSHOT_FILE,

    )

# ============================================================

# BUY NEW PIPELINE SNAPSHOT

# ============================================================

def save_buy_new_pipeline_snapshot(

    portfolio_decisions,

    final_portfolio_decisions,

):

    """

    Save the actual production decision outputs used by the
    BUY NEW pipeline diagnostic.

    This captures:

        portfolio_decisions

        final_portfolio_decisions

    The diagnostic must inspect the real production outputs
    rather than attempting to recreate the final decision
    pipeline synthetically.

    """

    DATA_DIRECTORY.mkdir(

        parents=True,

        exist_ok=True,

    )

    # --------------------------------------------------------

    # PORTFOLIO DECISIONS

    # --------------------------------------------------------

    if portfolio_decisions is None:

        portfolio_decisions_df = pd.DataFrame()

    elif isinstance(

        portfolio_decisions,

        pd.DataFrame,

    ):

        portfolio_decisions_df = (

            portfolio_decisions.copy()

        )

    else:

        portfolio_decisions_df = pd.DataFrame(

            portfolio_decisions

        )

    portfolio_decisions_df.to_csv(

        PORTFOLIO_DECISIONS_SNAPSHOT_FILE,

        index=False,

    )

    # --------------------------------------------------------

    # FINAL PORTFOLIO DECISIONS

    # --------------------------------------------------------

    if final_portfolio_decisions is None:

        final_portfolio_decisions_df = pd.DataFrame()

    elif isinstance(

        final_portfolio_decisions,

        pd.DataFrame,

    ):

        final_portfolio_decisions_df = (

            final_portfolio_decisions.copy()

        )

    else:

        final_portfolio_decisions_df = pd.DataFrame(

            final_portfolio_decisions

        )

    final_portfolio_decisions_df.to_csv(

        FINAL_PORTFOLIO_DECISIONS_SNAPSHOT_FILE,

        index=False,

    )

    print()

    print(

        "BUY NEW PIPELINE SNAPSHOTS SAVED"

    )

    print(

        f"Portfolio decisions: "

        f"{PORTFOLIO_DECISIONS_SNAPSHOT_FILE}"

    )

    print(

        f"Final portfolio decisions: "

        f"{FINAL_PORTFOLIO_DECISIONS_SNAPSHOT_FILE}"

    )

    return (

        PORTFOLIO_DECISIONS_SNAPSHOT_FILE,

        FINAL_PORTFOLIO_DECISIONS_SNAPSHOT_FILE,

    )
