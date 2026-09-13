"""
BUY NEW Candidate Ranking Diagnostic

Purpose
-------

Provides a transparent, read-only diagnostic of the BUY NEW
candidate selection pipeline.

This module answers the following questions:

    1. What are the highest-ranked investment opportunities?

    2. Which opportunities are genuinely new opportunities,
       rather than existing portfolio holdings?

    3. Which candidates have BUY or STRONG BUY signals?

    4. What are the authoritative Investment Score rankings?

    5. Where are the score ties?

    6. Which candidates fall inside the Top 10 investment
       ranking?

    7. What is the Entry Quality of those candidates?

    8. Which candidates satisfy BUY NEW governance?

    9. Where does each candidate get eliminated?

Important
---------

This diagnostic does NOT modify:

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
Candidate Snapshot Files
        ↓
This Diagnostic
        ↓

Investment Ranking
        ↓
New Opportunity Identification
        ↓
BUY / STRONG BUY Filter
        ↓
Authoritative Investment Ranking
        ↓
Top 10 Candidates
        ↓
Entry Quality Review
        ↓
BUY NEW Governance Review
        ↓
Diagnostic Outcome

Ranking Principle
-----------------

Investment Score is the authoritative ranking metric.

Investment Score is already the governed composite of:

    Technical Score
    Quality Score
    Growth Score

Therefore:

    Technical Score

    Quality Score

    Growth Score

are NOT used as secondary ranking tie-breakers.

Candidates with equal Investment Scores remain in the same
ranking tier.

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


TOP_CANDIDATE_COUNT = 10


# ============================================================
# DISPLAY HELPERS
# ============================================================

def print_section(
    title,
):
    """
    Print a standard diagnostic section heading.
    """

    print()

    print(
        "=" * 80
    )

    print(
        title
    )

    print(
        "=" * 80
    )


def print_dataframe(
    dataframe,
    columns=None,
):
    """
    Print a DataFrame safely.

    Parameters
    ----------

    dataframe:
        DataFrame to display.

    columns:
        Optional preferred columns.

    """

    if dataframe is None or dataframe.empty:

        print(
            "No candidates found."
        )

        return

    display_df = dataframe.copy()

    if columns:

        available_columns = [

            column

            for column in columns

            if column in display_df.columns

        ]

        if available_columns:

            display_df = display_df[
                available_columns
            ]

    print(

        display_df.to_string(

            index=False

        )

    )


# ============================================================
# VALUE HELPERS
# ============================================================

def safe_float(
    value,
    default=0.0,
):
    """
    Safely convert a value to float.
    """

    try:

        if pd.isna(value):

            return default

        return float(value)

    except Exception:

        return default


def normalise_text(
    value,
):
    """
    Normalise text for comparison.
    """

    if value is None:

        return ""

    try:

        if pd.isna(value):

            return ""

    except Exception:

        pass

    return str(
        value
    ).strip().upper()


def clean_ticker(
    value,
):
    """
    Normalise a ticker symbol.
    """

    return normalise_text(
        value
    )

def classify_buy_new_candidate(row):
    """
    Classify BUY NEW candidates by investment quality, governance
    eligibility and entry timing.

    This is diagnostic-only and does not modify production decisions.
    """

    governance_eligible = bool(
        row.get("BUY NEW Governance Eligible", False)
    )

    investment_score = row.get("Investment Score")
    signal = str(row.get("Signal", "")).strip().upper()
    entry_quality = str(
        row.get("Entry Quality", "")
    ).strip().upper()

    # ------------------------------------------------------------
    # 1. Governance failure
    # ------------------------------------------------------------

    if not governance_eligible:

        return (
            "NOT ELIGIBLE",
            "BUY NEW governance requirements not satisfied",
        )

    # ------------------------------------------------------------
    # 2. Insufficient investment quality
    # ------------------------------------------------------------

    if investment_score is None or investment_score < 75:

        return (
            "WATCH",
            "Investment quality below actionable BUY NEW threshold",
        )

    # ------------------------------------------------------------
    # 3. Signal validation
    # ------------------------------------------------------------

    if signal not in {"BUY", "STRONG BUY"}:

        return (
            "WATCH",
            "Investment signal is not sufficiently positive for BUY NEW",
        )

    # ------------------------------------------------------------
    # 4. Entry timing classification
    # ------------------------------------------------------------

    if entry_quality == "REASONABLE":

        return (
            "BUY NEW NOW",
            "Strong investment opportunity with favourable entry timing",
        )

    if entry_quality in {
        "MODERATELY EXTENDED",
        "EXTENDED",
    }:

        return (
            "BUY NEW - TIMING CAUTION",
            "Strong investment opportunity but entry is extended",
        )

    if entry_quality == "HIGHLY EXTENDED":

        return (
            "WATCH FOR BETTER ENTRY",
            "Investment opportunity is attractive but current entry timing carries high risk",
        )

    # ------------------------------------------------------------
    # Conservative fallback
    # ------------------------------------------------------------

    return (
        "WATCH",
        "Entry quality could not be classified with sufficient confidence",
    )

# ============================================================
# LOAD SNAPSHOTS
# ============================================================

def load_snapshots():
    """
    Load the latest candidate and portfolio snapshots.

    Returns
    -------

    tuple

        (
            candidates_df,
            portfolio_df
        )

    """

    # --------------------------------------------------------
    # Candidate snapshot
    # --------------------------------------------------------

    if not CANDIDATE_SNAPSHOT_FILE.exists():

        raise FileNotFoundError(

            "Candidate ranking snapshot not found:\n"

            f"{CANDIDATE_SNAPSHOT_FILE}\n\n"

            "Run main.py first to generate the diagnostic "
            "snapshot."

        )

    candidates_df = pd.read_csv(

        CANDIDATE_SNAPSHOT_FILE

    )

    # --------------------------------------------------------
    # Portfolio snapshot
    # --------------------------------------------------------

    if PORTFOLIO_SNAPSHOT_FILE.exists():

        portfolio_df = pd.read_csv(

            PORTFOLIO_SNAPSHOT_FILE

        )

    else:

        print(

            "WARNING: Portfolio snapshot not found."

        )

        portfolio_df = pd.DataFrame()

    return (

        candidates_df,

        portfolio_df,

    )


# ============================================================
# EXISTING HOLDINGS
# ============================================================

def get_existing_tickers(
    portfolio_df,
):
    """
    Return the set of current portfolio tickers.

    Uses the same conceptual architecture as the production
    portfolio decision engine.

    """

    if (

        portfolio_df is None

        or portfolio_df.empty

        or "Ticker" not in portfolio_df.columns

    ):

        return set()

    tickers = portfolio_df[
        "Ticker"
    ].apply(
        clean_ticker
    )

    tickers = tickers[
        tickers != ""
    ]

    return set(
        tickers
    )


# ============================================================
# PREPARE CANDIDATE UNIVERSE
# ============================================================

def prepare_candidate_universe(
    candidates_df,
    portfolio_df,
):
    """
    Prepare the full new-opportunity candidate universe.

    This stage:

        - normalises tickers
        - removes invalid tickers
        - removes existing holdings
        - removes duplicate tickers
        - preserves the full scan universe

    It deliberately does NOT yet filter:

        - Signal
        - Entry Quality
        - Governance
        - Portfolio risk
        - Sector allocation
        - LLM review

    """

    if candidates_df is None or candidates_df.empty:

        return pd.DataFrame()

    candidates = candidates_df.copy()

    # --------------------------------------------------------
    # Ticker required
    # --------------------------------------------------------

    if "Ticker" not in candidates.columns:

        raise ValueError(

            "Candidate snapshot does not contain a Ticker column."

        )

    candidates["Ticker"] = candidates[
        "Ticker"
    ].apply(
        clean_ticker
    )

    candidates = candidates[
        candidates["Ticker"] != ""
    ].copy()

    # --------------------------------------------------------
    # Investment Score numeric
    # --------------------------------------------------------

    if "Investment Score" not in candidates.columns:

        raise ValueError(

            "Candidate snapshot does not contain Investment Score."

        )

    candidates["Investment Score"] = pd.to_numeric(

        candidates["Investment Score"],

        errors="coerce",

    )

    candidates = candidates.dropna(

        subset=[

            "Investment Score",

        ]

    ).copy()

    # --------------------------------------------------------
    # Existing holdings
    # --------------------------------------------------------

    existing_tickers = get_existing_tickers(

        portfolio_df

    )

    candidates["Already Held"] = candidates[
        "Ticker"
    ].isin(
        existing_tickers
    )

    candidates = candidates[
        ~candidates["Already Held"]
    ].copy()

    # --------------------------------------------------------
    # One authoritative record per ticker
    #
    # Keep highest Investment Score.
    # --------------------------------------------------------

    candidates = (

        candidates

        .sort_values(

            by=[

                "Investment Score",

            ],

            ascending=[

                False,

            ],

        )

        .drop_duplicates(

            subset=[

                "Ticker",

            ],

            keep="first",

        )

        .copy()

    )

    return candidates


# ============================================================
# BUY SIGNAL UNIVERSE
# ============================================================

def get_buy_signal_candidates(
    candidates,
):
    """
    Return non-held candidates with BUY or STRONG BUY signals.

    """

    if candidates is None or candidates.empty:

        return pd.DataFrame()

    if "Signal" not in candidates.columns:

        print(

            "WARNING: Signal column missing."

        )

        return candidates.copy()

    result = candidates.copy()

    result["_Signal"] = result[
        "Signal"
    ].apply(
        normalise_text
    )

    result = result[

        result["_Signal"].isin(

            [

                "BUY",

                "STRONG BUY",

            ]

        )

    ].copy()

    result = result.drop(

        columns=[

            "_Signal",

        ]

    )

    return result


# ============================================================
# AUTHORITATIVE INVESTMENT RANKING
# ============================================================

def rank_candidates(
    candidates,
):
    """
    Rank candidates using Investment Score ONLY.

    Important:

    Investment Score is the authoritative ranking model.

    No secondary ranking formula is introduced.

    Equal Investment Scores remain in the same score tier.

    """

    if candidates is None or candidates.empty:

        return pd.DataFrame()

    ranked = candidates.copy()

    ranked = ranked.sort_values(

        by=[

            "Investment Score",

        ],

        ascending=[

            False,

        ],

    ).copy()

    # --------------------------------------------------------
    # Position rank
    # --------------------------------------------------------

    ranked.insert(

        0,

        "Investment Rank",

        range(

            1,

            len(ranked) + 1,

        ),

    )

    # --------------------------------------------------------
    # Score tier
    #
    # Candidates with the same Investment Score share
    # the same tier.
    # --------------------------------------------------------

    ranked["Investment Score Tier"] = (

        ranked["Investment Score"]

        .rank(

            method="dense",

            ascending=False,

        )

        .astype(int)

    )

    return ranked


# ============================================================
# TOP CANDIDATES
# ============================================================

def get_top_candidates(
    ranked_candidates,
    top_n=TOP_CANDIDATE_COUNT,
):
    """
    Return the Top N ranked candidates.

    Ranking is based only on Investment Score.

    Note:

    If the cutoff occurs inside a tied Investment Score tier,
    the complete tier is included.

    This avoids arbitrarily excluding candidates that have the
    same authoritative Investment Score.

    """

    if (

        ranked_candidates is None

        or ranked_candidates.empty

    ):

        return pd.DataFrame()

    ranked = ranked_candidates.copy()

    if len(ranked) <= top_n:

        return ranked

    # --------------------------------------------------------
    # Score at nominal cutoff
    # --------------------------------------------------------

    cutoff_score = ranked.iloc[
        top_n - 1
    ][
        "Investment Score"
    ]

    # --------------------------------------------------------
    # Include complete score tier
    # --------------------------------------------------------

    top_candidates = ranked[

        ranked["Investment Score"]

        >= cutoff_score

    ].copy()

    return top_candidates


# ============================================================
# ENTRY QUALITY DIAGNOSTIC
# ============================================================

def add_entry_quality_outcome(
    candidates,
):
    """
    Add a diagnostic interpretation of Entry Quality.

    Entry Quality remains diagnostic only.

    It does not alter Investment Rank.

    """

    if candidates is None or candidates.empty:

        return pd.DataFrame()

    result = candidates.copy()

    if "Entry Quality" not in result.columns:

        result["Entry Quality"] = "UNKNOWN"

    result["_Entry Quality"] = result[
        "Entry Quality"
    ].apply(
        normalise_text
    )

    def classify_entry_quality(
        value,
    ):

        if value == "REASONABLE":

            return "FAVOURABLE ENTRY"

        if value in (

            "MODERATELY EXTENDED",

            "EXTENDED",

        ):

            return "TIMING CAUTION"

        if value == "HIGHLY EXTENDED":

            return "HIGH TIMING RISK"

        return "ENTRY QUALITY UNKNOWN"

    result["Entry Quality Outcome"] = (

        result["_Entry Quality"]

        .apply(

            classify_entry_quality

        )

    )

    result = result.drop(

        columns=[

            "_Entry Quality",

        ]

    )

    return result


# ============================================================
# BUY NEW GOVERNANCE DIAGNOSTIC
# ============================================================

def add_buy_new_governance_diagnostic(
    candidates,
    portfolio_df,
):
    """
    Apply a transparent diagnostic approximation of the current
    BUY NEW approval rules.

    This does NOT alter production decisions.

    Current production approval rules:

        Investment Score >= 75

        Conviction must be:

            HIGH
            VERY HIGH

        Allocation < 10

        Portfolio Risk != HIGH

        Sector Allocation < 30

    The diagnostic evaluates these conditions where the relevant
    fields are available.

    """

    if candidates is None or candidates.empty:

        return pd.DataFrame()

    result = candidates.copy()

    # --------------------------------------------------------
    # Investment Score
    # --------------------------------------------------------

    result["Governance Investment Score"] = (

        result["Investment Score"]

        .apply(

            safe_float

        )

        >= 75

    )

    # --------------------------------------------------------
    # Conviction
    # --------------------------------------------------------

    
    # --------------------------------------------------------
    # Allocation
    #
    # New candidates normally have no current allocation.
    # --------------------------------------------------------

    allocation_column = None

    for column in (

        "Allocation %",

        "Allocation",

        "Portfolio Allocation %",

    ):

        if column in result.columns:

            allocation_column = column

            break

    if allocation_column:

        result["Governance Allocation"] = (

            result[allocation_column]

            .apply(

                safe_float

            )

            < 10

        )

    else:

        result["Governance Allocation"] = True

    # --------------------------------------------------------
    # Portfolio Risk
    # --------------------------------------------------------

    risk_column = None

    for column in (

        "Portfolio Risk",

        "Risk",

    ):

        if column in result.columns:

            risk_column = column

            break

    if risk_column:

        result["Governance Portfolio Risk"] = (

            result[risk_column]

            .apply(

                normalise_text

            )

            != "HIGH"

        )

    else:

        # Not available in scan universe.
        #
        # Diagnostic should not pretend this was evaluated.

        result["Governance Portfolio Risk"] = True

    # --------------------------------------------------------
    # Sector Allocation
    # --------------------------------------------------------

    sector_allocation_column = None

    for column in (

        "Sector Allocation %",

        "Sector Allocation",

    ):

        if column in result.columns:

            sector_allocation_column = column

            break

    if sector_allocation_column:

        result["Governance Sector Allocation"] = (

            result[sector_allocation_column]

            .apply(

                safe_float

            )

            < 30

        )

    else:

        # Portfolio-level information is not necessarily
        # available in the scan snapshot.

        result["Governance Sector Allocation"] = True

    # --------------------------------------------------------
    # Final diagnostic result
    # --------------------------------------------------------

    governance_columns = [

        "Governance Investment Score",

        "Governance Allocation",

        "Governance Portfolio Risk",

        "Governance Sector Allocation",

    ]

    result["BUY NEW Governance Eligible"] = (

        result[governance_columns]

        .all(

            axis=1

        )

    )

    # --------------------------------------------------------
    # Diagnostic reason
    # --------------------------------------------------------

    def build_governance_reason(
        row,
    ):

        failures = []

        if not row[
            "Governance Investment Score"
        ]:

            failures.append(

                "Investment Score below 75"

            )
        
        if not row[
            "Governance Allocation"
        ]:

            failures.append(

                "Allocation limit"

            )

        if not row[
            "Governance Portfolio Risk"
        ]:

            failures.append(

                "Portfolio risk HIGH"

            )

        if not row[
            "Governance Sector Allocation"
        ]:

            failures.append(

                "Sector allocation limit"

            )

        if not failures:

            return (

                "Meets available BUY NEW governance checks"

            )

        return "; ".join(

            failures

        )

    result["BUY NEW Governance Reason"] = (

        result.apply(

            build_governance_reason,

            axis=1,

        )

    )

    return result


# ============================================================
# PIPELINE OUTCOME
# ============================================================

def add_diagnostic_outcome(
    candidates,
):
    """
    Add the final diagnostic outcome.

    The BUY NEW Candidate Decision is the authoritative
    diagnostic classification.

    This remains diagnostic-only and does not modify
    production decisions.
    """

    if candidates is None or candidates.empty:

        return pd.DataFrame()

    result = candidates.copy()

    result["Diagnostic Outcome"] = result.apply(

        lambda row: row.get(
            "BUY NEW Candidate Decision",
            "WATCH",
        ),

        axis=1,

    )

    return result

# ============================================================
# MAIN DIAGNOSTIC
# ============================================================

def run_candidate_ranking_diagnostic():
    """
    Run the complete BUY NEW candidate-ranking diagnostic.

    """

    print_section(

        "BUY NEW CANDIDATE RANKING DIAGNOSTIC"

    )

    # --------------------------------------------------------
    # Load snapshots
    # --------------------------------------------------------

    candidates_df, portfolio_df = (

        load_snapshots()

    )

    print(

        f"Live scan records: "

        f"{len(candidates_df)}"

    )

    print(

        f"Portfolio records: "

        f"{len(portfolio_df)}"

    )

    # --------------------------------------------------------
    # Prepare new opportunity universe
    # --------------------------------------------------------

    candidate_universe = (

        prepare_candidate_universe(

            candidates_df,

            portfolio_df,

        )

    )

    print_section(

        "1. NEW INVESTMENT OPPORTUNITY UNIVERSE"

    )

    print(

        f"Non-held opportunities: "

        f"{len(candidate_universe)}"

    )

    # --------------------------------------------------------
    # BUY signal candidates
    # --------------------------------------------------------

    buy_candidates = (

        get_buy_signal_candidates(

            candidate_universe

        )

    )

    print_section(

        "2. BUY / STRONG BUY CANDIDATES"

    )

    print(

        f"BUY / STRONG BUY opportunities: "

        f"{len(buy_candidates)}"

    )

    # --------------------------------------------------------
    # Authoritative ranking
    # --------------------------------------------------------

    ranked_candidates = (

        rank_candidates(

            buy_candidates

        )

    )

    print_section(

        "3. AUTHORITATIVE INVESTMENT RANKING"

    )

    print_dataframe(

        ranked_candidates,

        columns=[

            "Investment Rank",

            "Investment Score Tier",

            "Ticker",

            "Sector",

            "Investment Score",

            "Signal",

            "Entry Quality",

            "BUY NEW Governance Eligible",

            "BUY NEW Candidate Decision",

            "BUY NEW Candidate Reason",

        ],
    )

    # --------------------------------------------------------
    # Top candidates
    # --------------------------------------------------------

    top_candidates = (

        get_top_candidates(

            ranked_candidates,

            TOP_CANDIDATE_COUNT,

        )

    )

    print_section(

        "4. TOP INVESTMENT CANDIDATES"

    )

    print(

        f"Nominal Top N: "

        f"{TOP_CANDIDATE_COUNT}"

    )

    print(

        f"Candidates included after ties: "

        f"{len(top_candidates)}"

    )

    print_dataframe(

        top_candidates,

        columns=[

            "Investment Rank",

            "Investment Score Tier",

            "Ticker",

            "Name",

            "Sector",

            "Signal",

            "Investment Score",

            "Technical Score",

            "Quality Score",

            "Growth Score",

            "Confidence Score",

        ],

    )

    # --------------------------------------------------------
    # Entry Quality
    # --------------------------------------------------------

    entry_quality_candidates = (

        add_entry_quality_outcome(

            top_candidates

        )

    )

    print_section(

        "5. ENTRY QUALITY REVIEW"

    )

    print_dataframe(

        entry_quality_candidates,

        columns=[

            "Investment Rank",

            "Ticker",

            "Investment Score",

            "Signal",

            "Entry Quality",

            "Entry Quality Outcome",

            "Extension SMA50 %",

            "Extension SMA200 %",

            "Return 5D %",

            "Return 10D %",

            "Return 20D %",

        ],

    )

    # --------------------------------------------------------
    # Governance
    # --------------------------------------------------------

    governance_candidates = (

        add_buy_new_governance_diagnostic(

            entry_quality_candidates,

            portfolio_df,

        )

    )

    print_section(

        "6. BUY NEW GOVERNANCE REVIEW"

    )

    print_dataframe(

        governance_candidates,

        columns=[

            "Investment Rank",

            "Ticker",

            "Investment Score",

            "Entry Quality",

            "Governance Investment Score",

            "Governance Conviction",

            "Governance Allocation",

            "Governance Portfolio Risk",

            "Governance Sector Allocation",

            "BUY NEW Governance Eligible",

            "BUY NEW Governance Reason",

        ],

    )

    # ------------------------------------------------------------
    # BUY NEW candidate decision classification
    # ------------------------------------------------------------

    candidate_classification = governance_candidates.apply(
        classify_buy_new_candidate,
        axis=1,
    )

    governance_candidates[
        "BUY NEW Candidate Decision"
    ] = candidate_classification.apply(lambda x: x[0])

    governance_candidates[
        "BUY NEW Candidate Reason"
    ] = candidate_classification.apply(lambda x: x[1])

    # --------------------------------------------------------
    # Final diagnostic outcome
    # --------------------------------------------------------

    final_candidates = (

        add_diagnostic_outcome(

            governance_candidates

        )

    )

    print_section(

        "7. FINAL DIAGNOSTIC OUTCOME"

    )

    print_dataframe(

        final_candidates,

        columns=[

            "Investment Rank",

            "Investment Score Tier",

            "Ticker",

            "Sector",

            "Investment Score",

            "Signal",

            "Entry Quality",

            "BUY NEW Governance Eligible",

            "Diagnostic Outcome",

        ],

    )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print_section(

        "DIAGNOSTIC SUMMARY"

    )

    print(

        f"Live scan universe: "

        f"{len(candidates_df)}"

    )

    print(

        f"New opportunities: "

        f"{len(candidate_universe)}"

    )

    print(

        f"BUY / STRONG BUY candidates: "

        f"{len(buy_candidates)}"

    )

    print(

        f"Top ranked candidates reviewed: "

        f"{len(top_candidates)}"

    )

    governance_approved = (

        final_candidates[

            final_candidates[

                "BUY NEW Governance Eligible"

            ]

        ]

        if not final_candidates.empty

        else pd.DataFrame()

    )

    print(

        f"BUY NEW governance eligible: "

        f"{len(governance_approved)}"

    )

    print()

    print(

        "IMPORTANT: This diagnostic does not modify "

        "production decisions."

    )

    return final_candidates


# ============================================================
# SCRIPT ENTRY POINT
# ============================================================

if __name__ == "__main__":

    run_candidate_ranking_diagnostic()