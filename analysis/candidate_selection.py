"""
candidate_selection.py

Production BUY NEW Candidate Selection Layer.

Purpose
-------

Creates a deterministic shortlist of the strongest new investment
opportunities before BUY NEW governance is applied.

Architecture
------------

Investment Universe
        ↓
Investment Ranking
        ↓
Candidate Selection
        ↓
Entry Quality Assessment
        ↓
BUY NEW Governance
        ↓
Portfolio Decision

Important Design Principles
---------------------------

This module:

    - DOES rank investment opportunities
    - DOES identify the strongest candidates
    - DOES preserve ties at the selection boundary
    - DOES consider Entry Quality for candidate classification
    - DOES NOT modify Investment Score
    - DOES NOT modify technical scoring
    - DOES NOT modify quality scoring
    - DOES NOT modify growth scoring
    - DOES NOT perform capital allocation
    - DOES NOT override portfolio governance
    - DOES NOT make final BUY/SELL decisions

The Portfolio Decision Engine remains authoritative for final actions.

Candidate selection answers:

    "Which opportunities deserve serious portfolio consideration?"

Governance answers:

    "Which of those opportunities are currently permitted to become BUY NEW?"

This separation prevents governance rules from accidentally becoming
the investment ranking engine.
"""

import pandas as pd


# ============================================================
# CONFIGURATION
# ============================================================

DEFAULT_TOP_CANDIDATES = 10

MAX_BUY_NEW_DECISIONS = 3

# ============================================================
# BUY NEW H1 CONTINUATION FILTER
# ============================================================

# Validated separately using walk-forward OOS testing.
#
# H1 is deliberately NOT part of Investment Score.
# It is a BUY NEW decision-layer feature used to prioritise
# otherwise eligible candidates.
#
# These values must be the frozen thresholds selected by the
# final BUY NEW H1 validation.
H1_RSI_THRESHOLD = 55.0
H1_RETURN_3M_MAX = 25.0


# ============================================================
# HELPERS
# ============================================================

def safe_float(value, default=0.0):
    """
    Safely convert a value to float.
    """

    try:
        if pd.isna(value):
            return default

        return float(value)

    except Exception:
        return default


def normalise_text(value):
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

    return str(value).strip().upper()


def is_not_held(value):
    """
    Determine whether a Held? value represents a non-held position.
    """

    value = normalise_text(value)

    return value in (
        "NO",
        "FALSE",
        "0",
        "",
    )


# ============================================================
# OPPORTUNITY UNIVERSE
# ============================================================

def get_new_stock_opportunities(

    df,

    portfolio_summary=None,

):

    """

    Return the investable universe of new STOCK opportunities.

    A new opportunity is defined authoritatively as a STOCK that
    is present in the scan universe but is not currently held in
    the portfolio.

    Filters:

        - Non-held securities only

        - STOCK assets only, where Asset Type is available

        - Valid Investment Score required

    This function deliberately does NOT apply:

        - BUY NEW governance

        - Entry Quality filtering

        - Portfolio allocation

        - Sector allocation

        - LLM review

    """

    if df is None or df.empty:

        return pd.DataFrame()

    candidates = df.copy()

    # --------------------------------------------------------
    # TICKER
    # --------------------------------------------------------

    if "Ticker" not in candidates.columns:

        return pd.DataFrame()

    candidates["Ticker"] = (

        candidates["Ticker"]

        .apply(normalise_text)

    )

    candidates = candidates[

        candidates["Ticker"] != ""

    ].copy()

    # --------------------------------------------------------
    # EXISTING PORTFOLIO HOLDINGS
    #
    # portfolio_summary is authoritative for determining
    # whether a security is already held.
    # --------------------------------------------------------

    held_tickers = set()

    if (

        portfolio_summary is not None

        and isinstance(

            portfolio_summary,

            pd.DataFrame,

        )

        and not portfolio_summary.empty

        and "Ticker" in portfolio_summary.columns

    ):

        held_tickers = set(

            portfolio_summary["Ticker"]

            .apply(normalise_text)

        )

        held_tickers.discard("")

    # --------------------------------------------------------
    # FALLBACK HELD STATUS
    #
    # Retained for compatibility where the scan universe
    # already contains Held? information.
    # --------------------------------------------------------

    if held_tickers:

        candidates = candidates[

            ~candidates["Ticker"].isin(

                held_tickers

            )

        ].copy()

    elif "Held?" in candidates.columns:

        candidates = candidates[

            candidates["Held?"].apply(

                is_not_held

            )

        ].copy()

    # --------------------------------------------------------
    # ASSET TYPE
    # --------------------------------------------------------

    asset_type_column = None

    for column in (

        "Asset Type",

        "Type",

    ):

        if column in candidates.columns:

            asset_type_column = column

            break

    if asset_type_column:

        candidates = candidates[

            candidates[

                asset_type_column

            ]

            .apply(normalise_text)

            .eq("STOCK")

        ].copy()

    # --------------------------------------------------------
    # INVESTMENT SCORE
    # --------------------------------------------------------

    if "Investment Score" not in candidates.columns:

        return pd.DataFrame()

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
    # ONE AUTHORITATIVE RECORD PER TICKER
    # --------------------------------------------------------

    candidates = (

        candidates

        .sort_values(

            "Investment Score",

            ascending=False,

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

def get_buy_candidates(df):
    """
    Return candidates with BUY or STRONG BUY signals.

    Signal filtering happens after the new-stock universe is created.

    This does NOT apply governance.
    """

    if df is None or df.empty:
        return pd.DataFrame()

    candidates = df.copy()

    if "Signal" not in candidates.columns:
        return candidates

    candidates = candidates[
        candidates["Signal"]
        .apply(normalise_text)
        .isin(
            (
                "BUY",
                "STRONG BUY",
            )
        )
    ].copy()

    return candidates


# ============================================================
# AUTHORITATIVE INVESTMENT RANKING
# ============================================================

def rank_investment_candidates(df):
    """
    Rank candidates using the authoritative investment hierarchy.

    Primary ranking:

        1. Investment Score
        2. Technical Score
        3. Quality Score
        4. Growth Score
        5. Confidence Score

    This ranking intentionally does NOT use Entry Quality.

    Entry Quality answers:

        "Is now a good time to enter?"

    Investment Ranking answers:

        "How attractive is this investment opportunity?"

    These are deliberately separate concepts.
    """

    if df is None or df.empty:
        return pd.DataFrame()

    candidates = df.copy()

    # --------------------------------------------------------
    # H1 BUY NEW TIE-BREAKER
    #
    # H1 is deliberately NOT part of Investment Score.
    #
    # Investment Score remains the primary ranking factor.
    # H1 is used only to break ties between candidates with
    # the same Investment Score.
    #
    # H1:
    #   RSI >= 55
    #   Return 3M <= 25%
    #
    # This was selected as the current human-reviewed
    # calibration from the read-only historical/OOS tests.
    #
    # H1 must not:
    #   - override Investment Score
    #   - act as a hard eligibility gate
    #   - override HOLD/governance decisions
    # --------------------------------------------------------

    if (
        "RSI" in candidates.columns
        and "Return_3m" in candidates.columns
    ):
        candidates["H1"] = (
            pd.to_numeric(
                candidates["RSI"],
                errors="coerce",
            ).ge(55.0)
            &
            pd.to_numeric(
                candidates["Return_3m"],
                errors="coerce",
            ).le(25.0)
        )
    else:
        candidates["H1"] = False

    ranking_columns = [
        "Investment Score",
        "H1",
        "Technical Score",
        "Quality Score",
        "Growth Score",
        "Confidence Score",
    ]

    available_columns = []

    for column in ranking_columns:
        if column == "H1":
            available_columns.append(column)
            continue

        if column in candidates.columns:
            candidates[column] = pd.to_numeric(
                candidates[column],
                errors="coerce",
            ).fillna(0)

            available_columns.append(column)

    if not available_columns:
        return pd.DataFrame()

    candidates = candidates.sort_values(
        by=available_columns,
        ascending=[
            False,
            False,
            False,
            False,
            False,
            False,
        ][:len(available_columns)],
    ).copy()
    # --------------------------------------------------------
    # INVESTMENT SCORE TIER
    #
    # Candidates with the same Investment Score share the same
    # tier. This prevents arbitrary separation of equal scores.
    # --------------------------------------------------------

    candidates["Investment Score Tier"] = (
        candidates["Investment Score"]
        .rank(
            method="dense",
            ascending=False,
        )
        .astype(int)
    )

    # --------------------------------------------------------
    # UNIQUE INVESTMENT RANK
    #
    # Used only to preserve deterministic ordering.
    # --------------------------------------------------------

    candidates.insert(
        0,
        "Investment Rank",
        range(
            1,
            len(candidates) + 1,
        ),
    )

    return candidates


# ============================================================
# TOP CANDIDATE SELECTION
# ============================================================

def select_top_candidates(
    ranked_candidates,
    top_n=DEFAULT_TOP_CANDIDATES,
):
    """
    Select the strongest investment candidates.

    Important:

    The selection boundary preserves Investment Score ties.

    Example:

        top_n = 10

        Rank 10 Investment Score = 78

    Every candidate with Investment Score = 78 is included.

    This prevents arbitrary exclusion of equivalent
    Investment Score candidates.
    """

    if ranked_candidates is None or ranked_candidates.empty:
        return pd.DataFrame()

    candidates = ranked_candidates.copy()

    if "Investment Score" not in candidates.columns:
        return candidates.head(top_n).copy()

    if len(candidates) <= top_n:
        return candidates

    boundary_score = safe_float(
        candidates.iloc[top_n - 1]["Investment Score"]
    )

    selected = candidates[
        candidates["Investment Score"].apply(
            lambda value: safe_float(value) >= boundary_score
        )
    ].copy()

    return selected


# ============================================================
# ENTRY QUALITY CLASSIFICATION
# ============================================================

def classify_entry_quality(candidate):
    """
    Classify entry timing.

    Entry Quality is deliberately separate from investment quality.

    Returns:

        FAVOURABLE ENTRY
        TIMING CAUTION
        HIGH TIMING RISK
        UNKNOWN

    This function does NOT reject the investment.

    It classifies timing only.
    """

    entry_quality = normalise_text(
        candidate.get(
            "Entry Quality",
            "",
        )
    )

    if entry_quality in (
        "REASONABLE",
        "ATTRACTIVE",
        "FAVOURABLE",
        "GOOD",
    ):
        return "FAVOURABLE ENTRY"

    if entry_quality in (
        "HIGHLY EXTENDED",
        "EXTREME",
        "VERY EXTENDED",
    ):
        return "HIGH TIMING RISK"

    if entry_quality in (
        "MODERATELY EXTENDED",
        "EXTENDED",
        "CAUTION",
    ):
        return "TIMING CAUTION"

    return "UNKNOWN"

# ============================================================
# BUY NEW H1 CONTINUATION ASSESSMENT
# ============================================================

def classify_buy_new_h1(candidate):
    """
    Classify short-term continuation quality for an otherwise
    BUY NEW-eligible candidate.

    H1 is deliberately separate from Investment Score and
    Entry Quality.

    H1 asks:

        "Does this candidate have the short-term momentum
         characteristics associated with stronger subsequent
         BUY NEW performance?"

    It does NOT determine whether the underlying investment
    is attractive and does NOT override governance.

    Returns
    -------
    str
        "H1 STRONG"
        "H1 NEUTRAL"
        "H1 DATA INSUFFICIENT"
    """

    if candidate is None:
        return "H1 DATA INSUFFICIENT"

    rsi = pd.to_numeric(
        candidate.get("RSI"),
        errors="coerce",
    )

    return_3m = pd.to_numeric(
        candidate.get(
            "Return_3m",
            candidate.get("Return 3M"),
        ),
        errors="coerce",
    )

    # --------------------------------------------------------
    # Missing evidence
    # --------------------------------------------------------

    if pd.isna(rsi) or pd.isna(return_3m):
        return "H1 DATA INSUFFICIENT"

    # --------------------------------------------------------
    # Validated H1 continuation profile
    # --------------------------------------------------------

    if (
        rsi >= H1_RSI_THRESHOLD
        and return_3m <= H1_RETURN_3M_MAX
    ):
        return "H1 STRONG"

    return "H1 NEUTRAL"



# ============================================================
# CANDIDATE REVIEW
# ============================================================

def build_candidate_review(
    selected_candidates,
):
    """
    Add entry timing, BUY NEW eligibility and H1 continuation
    assessment to selected investment candidates.

    Concepts deliberately remain separate:

        Investment Rank
            Which opportunities are the strongest investments?

        Entry Timing Status
            Is the current entry technically suitable?

        H1 Continuation
            Does the candidate have the validated short-term
            momentum characteristics associated with stronger
            subsequent BUY NEW performance?

        BUY NEW Priority Rank
            Which eligible candidates should receive priority?

    H1 does NOT:

        - change Investment Score
        - change Investment Rank
        - change Technical Score
        - change Entry Quality
        - make an otherwise ineligible candidate eligible
        - override governance
        - override HOLD protection
    """

    if (
        selected_candidates is None
        or selected_candidates.empty
    ):
        return pd.DataFrame()

    candidates = selected_candidates.copy()

    timing_statuses = []
    candidate_statuses = []
    buy_new_eligible = []
    h1_statuses = []

    for _, row in candidates.iterrows():

        timing_status = classify_entry_quality(
            row
        )

        h1_status = classify_buy_new_h1(
            row
        )

        timing_statuses.append(
            timing_status
        )

        h1_statuses.append(
            h1_status
        )

        # ----------------------------------------------------
        # Existing entry classification
        #
        # H1 does NOT alter this gate.
        # ----------------------------------------------------

        if timing_status == "FAVOURABLE ENTRY":

            candidate_statuses.append(
                "STRONG CANDIDATE"
            )

            buy_new_eligible.append(
                True
            )

        elif timing_status == "TIMING CAUTION":

            candidate_statuses.append(
                "STRONG INVESTMENT - TIMING CAUTION"
            )

            buy_new_eligible.append(
                False
            )

        elif timing_status == "HIGH TIMING RISK":

            candidate_statuses.append(
                "STRONG INVESTMENT - WAIT FOR ENTRY"
            )

            buy_new_eligible.append(
                False
            )

        else:

            candidate_statuses.append(
                "CANDIDATE - ENTRY QUALITY UNKNOWN"
            )

            buy_new_eligible.append(
                False
            )

    # --------------------------------------------------------
    # Persist entry assessment
    # --------------------------------------------------------

    candidates["Entry Timing Status"] = (
        timing_statuses
    )

    candidates["Candidate Status"] = (
        candidate_statuses
    )

    candidates["BUY NEW Eligible"] = (
        buy_new_eligible
    )

    # --------------------------------------------------------
    # Persist H1 assessment
    # --------------------------------------------------------

    candidates["BUY NEW H1 Status"] = (
        h1_statuses
    )

    # --------------------------------------------------------
    # BUY NEW PRIORITY RANK
    #
    # Existing Investment Rank remains authoritative for
    # investment attractiveness.
    #
    # H1 is used only to prioritise candidates that have
    # already passed the BUY NEW eligibility gate.
    #
    # Priority:
    #
    #   1. H1 STRONG
    #   2. H1 NEUTRAL
    #   3. H1 DATA INSUFFICIENT
    #
    # Within each H1 group:
    #
    #   Investment Rank
    #
    # Therefore H1 cannot rescue a weak investment candidate;
    # it only differentiates otherwise eligible candidates.
    # --------------------------------------------------------

    candidates["BUY NEW Priority Rank"] = pd.NA

    eligible_mask = (
        candidates["BUY NEW Eligible"]
        .fillna(False)
        .astype(bool)
    )

    eligible_candidates = (
        candidates.loc[
            eligible_mask
        ]
        .copy()
    )

    if not eligible_candidates.empty:

        h1_priority = {
            "H1 STRONG": 0,
            "H1 NEUTRAL": 1,
            "H1 DATA INSUFFICIENT": 2,
        }

        eligible_candidates["_H1 Priority"] = (
            eligible_candidates[
                "BUY NEW H1 Status"
            ]
            .map(
                h1_priority
            )
            .fillna(2)
        )

        # ----------------------------------------------------
        # Investment Rank remains the tie-breaker.
        # ----------------------------------------------------

        if "Investment Rank" in eligible_candidates.columns:

            eligible_candidates = (
                eligible_candidates
                .sort_values(
                    by=[
                        "_H1 Priority",
                        "Investment Rank",
                    ],
                    ascending=[
                        True,
                        True,
                    ],
                    na_position="last",
                )
                .copy()
            )

        else:

            # Fallback ordering if Investment Rank is absent.
            sort_columns = [
                "_H1 Priority",
            ]

            ascending = [
                True,
            ]

            for column in (
                "Investment Score",
                "Technical Score",
                "Quality Score",
                "Growth Score",
                "Confidence Score",
            ):

                if column in eligible_candidates.columns:

                    sort_columns.append(
                        column
                    )

                    ascending.append(
                        False
                    )

            eligible_candidates = (
                eligible_candidates
                .sort_values(
                    by=sort_columns,
                    ascending=ascending,
                    na_position="last",
                )
                .copy()
            )

        eligible_candidates[
            "BUY NEW Priority Rank"
        ] = range(
            1,
            len(eligible_candidates) + 1,
        )

        candidates.loc[
            eligible_candidates.index,
            "BUY NEW Priority Rank",
        ] = (
            eligible_candidates[
                "BUY NEW Priority Rank"
            ]
        )

    return candidates
# ============================================================
# COMPLETE CANDIDATE PIPELINE
# ============================================================

# ============================================================
# COMPLETE CANDIDATE PIPELINE
# ============================================================

def select_buy_new_candidates(

    df,

    top_n=MAX_BUY_NEW_DECISIONS,

):

    """

    Execute the complete BUY NEW candidate selection pipeline.

    Pipeline

    --------

    New Stock Universe

            ↓

    BUY / STRONG BUY Filter

            ↓

    Investment Ranking

            ↓

    Entry Quality Classification

            ↓

    BUY NEW Eligibility

            ↓

    BUY NEW Priority Ranking

            ↓

    Top BUY NEW Candidate Selection

    IMPORTANT

    ---------

    Investment Rank answers:

        Which opportunities are the strongest investments?

    BUY NEW Priority Rank answers:

        Which strong investments are suitable to buy now?

    Entry timing does NOT alter Investment Rank.

    Returns

    -------

    pd.DataFrame

        Prioritised BUY NEW candidate shortlist.

    """

    # --------------------------------------------------------
    # NEW OPPORTUNITY UNIVERSE
    # --------------------------------------------------------

    new_opportunities = (

        get_new_stock_opportunities(

            df

        )

    )

    if (

        new_opportunities is None

        or new_opportunities.empty

    ):

        return pd.DataFrame()

    # --------------------------------------------------------
    # BUY / STRONG BUY FILTER
    # --------------------------------------------------------

    buy_candidates = (

        get_buy_candidates(

            new_opportunities

        )

    )

    if (

        buy_candidates is None

        or buy_candidates.empty

    ):

        return pd.DataFrame()

    # --------------------------------------------------------
    # INVESTMENT RANKING
    #
    # This is deliberately independent of entry timing.
    # --------------------------------------------------------

    ranked_candidates = (

        rank_investment_candidates(

            buy_candidates

        )

    )

    if (

        ranked_candidates is None

        or ranked_candidates.empty

    ):

        return pd.DataFrame()

    # --------------------------------------------------------
    # ENTRY QUALITY + BUY NEW ELIGIBILITY
    #
    # Investment Rank is preserved.
    #
    # BUY NEW Priority Rank is calculated separately.
    # --------------------------------------------------------

    reviewed_candidates = (

        build_candidate_review(

            ranked_candidates

        )

    )

    if (

        reviewed_candidates is None

        or reviewed_candidates.empty

    ):

        return pd.DataFrame()

    # --------------------------------------------------------
    # BUY NEW ELIGIBLE UNIVERSE
    #
    # Only candidates suitable for entry NOW can compete
    # for the limited BUY NEW slots.
    # --------------------------------------------------------

    if "BUY NEW Eligible" not in reviewed_candidates.columns:

        return pd.DataFrame()

    buy_new_candidates = (

        reviewed_candidates[

            reviewed_candidates[

                "BUY NEW Eligible"

            ]

            .fillna(False)

            .astype(bool)

        ]

        .copy()

    )

    if buy_new_candidates.empty:

        return pd.DataFrame()

    # --------------------------------------------------------
    # BUY NEW PRIORITY ORDER
    # --------------------------------------------------------

    if (

        "BUY NEW Priority Rank"

        in buy_new_candidates.columns

    ):

        buy_new_candidates = (

            buy_new_candidates

            .sort_values(

                by="BUY NEW Priority Rank",

                ascending=True,

                na_position="last",

            )

            .copy()

        )

    elif "Investment Rank" in buy_new_candidates.columns:

        # Defensive fallback.

        buy_new_candidates = (

            buy_new_candidates

            .sort_values(

                by="Investment Rank",

                ascending=True,

                na_position="last",

            )

            .copy()

        )

    # --------------------------------------------------------
    # TOP BUY NEW CANDIDATES
    #
    # This is the shortlist used downstream.
    #
    # The top_n limit applies to the best candidates
    # that are actually suitable for entry now.
    # --------------------------------------------------------

    if (

        top_n is not None

        and top_n > 0

    ):

        buy_new_candidates = (

            buy_new_candidates

            .head(

                top_n

            )

            .copy()

        )

    return buy_new_candidates

# ============================================================
# CANDIDATE LOOKUP
# ============================================================

def build_candidate_lookup(
    candidates,
):
    """
    Build a ticker-keyed lookup for the selected candidate set.

    This allows the Portfolio Decision Engine to determine:

        Is this ticker part of the current serious BUY NEW
        candidate shortlist?

    Important:

    This function does not determine whether BUY NEW is approved.

    Governance remains responsible for that decision.
    """

    if candidates is None or candidates.empty:
        return {}

    if "Ticker" not in candidates.columns:
        return {}

    lookup = {}

    for _, row in candidates.iterrows():

        ticker = normalise_text(
            row.get(
                "Ticker",
                "",
            )
        )

        if not ticker:
            continue

        lookup[ticker] = row.to_dict()

    return lookup
