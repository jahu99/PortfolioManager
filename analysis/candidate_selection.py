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
Investment Score Eligibility
        ↓
BUY / STRONG BUY Filter
        ↓
Business Attractiveness Ranking
        ↓
Entry Quality Assessment
        ↓
BUY NEW Priority Ranking
        ↓
BUY NEW Governance
        ↓
Portfolio Decision

Important Design Principles
---------------------------

This module:

    - DOES identify the strongest new investment opportunities
    - DOES use Investment Score as an eligibility gate
    - DOES rank business attractiveness separately from entry timing
    - DOES preserve Investment Rank for audit/reporting
    - DOES consider Entry Quality for BUY NEW eligibility
    - DOES consider Technical Score as a secondary entry/timing factor
    - DOES use H1 as a secondary tie-breaker
    - DOES NOT modify Investment Score
    - DOES NOT modify technical scoring
    - DOES NOT modify quality scoring
    - DOES NOT modify growth scoring
    - DOES NOT perform capital allocation
    - DOES NOT override portfolio governance
    - DOES NOT make final BUY/SELL decisions

Investment Score answers:

    "Is this opportunity strong enough to enter the BUY NEW
     candidate universe?"

Business Score answers:

    "Among eligible opportunities, how attractive is the
     underlying business based on Growth and Quality?"

Technical Score answers:

    "Among comparable business opportunities, which currently
     has stronger entry/market characteristics?"

H1 answers:

    "Among otherwise comparable candidates, which has the
     stronger validated short-term continuation profile?"

The Portfolio Decision Engine remains authoritative for final actions.

Candidate selection answers:

    "Which opportunities deserve serious portfolio consideration?"

Governance answers:

    "Which of those opportunities are currently permitted to become BUY NEW?"

This separation prevents Investment Score, technical timing or H1
from becoming the sole ranking mechanism for long-term BUY NEW
opportunity selection.
"""

import pandas as pd


# ============================================================
# CONFIGURATION
# ============================================================

DEFAULT_TOP_CANDIDATES = 10

MAX_BUY_NEW_DECISIONS = 3

# Investment Score remains the existing production BUY threshold.
#
# This is an eligibility gate for BUY NEW candidate selection.
# It does NOT change the underlying Investment Score calculation.
MIN_BUY_NEW_INVESTMENT_SCORE = 75.0


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

        - Investment Score >= production BUY threshold

    Investment Score is used here as an eligibility gate rather
    than as the final BUY NEW ranking mechanism.

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
    # BUY NEW INVESTMENT SCORE ELIGIBILITY
    #
    # The existing production BUY threshold of 75 is retained.
    #
    # This is an eligibility gate only.
    #
    # It deliberately does NOT determine the final BUY NEW
    # priority order.
    # --------------------------------------------------------

    candidates = candidates[

        candidates["Investment Score"]

        .ge(

            MIN_BUY_NEW_INVESTMENT_SCORE

        )

    ].copy()

    if candidates.empty:

        return pd.DataFrame()

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
    Preserve the authoritative Investment Score ranking for
    reporting and audit purposes while also calculating a
    transparent Business Score.

    Investment Rank remains based on:

        1. Investment Score
        2. H1
        3. Technical Score
        4. Quality Score
        5. Growth Score
        6. Confidence Score

    Important:

    Investment Rank is NOT the final BUY NEW priority order.

    Business Score is calculated as:

        50% Growth Score
        50% Quality Score

    This does not modify either underlying score or the
    Investment Score.

    The Business Score exists specifically so BUY NEW candidate
    selection can distinguish underlying business attractiveness
    from short-term entry/timing characteristics.

    Entry Quality is deliberately not used here.
    """

    if df is None or df.empty:
        return pd.DataFrame()

    candidates = df.copy()

    # --------------------------------------------------------
    # H1 BUY NEW TIE-BREAKER
    #
    # H1 is deliberately NOT part of Investment Score.
    #
    # Investment Score remains the primary ranking factor for
    # Investment Rank.
    #
    # H1 is used only to break ties between candidates with
    # the same Investment Score.
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

    # --------------------------------------------------------
    # NORMALISE INVESTMENT RANKING INPUTS
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # INVESTMENT RANK
    #
    # This remains the authoritative investment ranking and is
    # retained for reporting/audit.
    # --------------------------------------------------------

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
    # BUSINESS SCORE
    #
    # Business Score is deliberately separate from Investment
    # Score.
    #
    # It represents the underlying business opportunity using
    # Growth and Quality equally.
    #
    # This is the same transparent 50/50 Business Score used
    # in the completed diagnostic analysis.
    #
    # It does NOT alter production Growth, Quality or Investment
    # scores.
    # --------------------------------------------------------

    if "Growth Score" in candidates.columns:

        growth_score = pd.to_numeric(

            candidates["Growth Score"],

            errors="coerce",

        ).fillna(0.0)

    else:

        growth_score = pd.Series(

            0.0,

            index=candidates.index,

        )

    if "Quality Score" in candidates.columns:

        quality_score = pd.to_numeric(

            candidates["Quality Score"],

            errors="coerce",

        ).fillna(0.0)

    else:

        quality_score = pd.Series(

            0.0,

            index=candidates.index,

        )

    candidates["Business Score"] = (

        growth_score + quality_score

    ) / 2.0

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
    # Used to preserve deterministic ordering and for audit/reporting.
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

    NOTE:

    This function remains available for compatibility and
    reporting purposes. The production BUY NEW pipeline now
    evaluates the complete Investment Score >= 75 universe
    before applying Business Score and entry-priority ranking.
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

            lambda value:

                safe_float(value) >= boundary_score

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
            The authoritative Investment Score ranking.

        Business Score
            Underlying Growth + Quality attractiveness.

        Entry Timing Status
            Is the current entry technically suitable?

        Technical Score
            Secondary ordering factor reflecting entry/market
            characteristics.

        H1 Continuation
            Validated short-term continuation profile.

        BUY NEW Priority Rank
            Final ordering of candidates eligible to compete
            for the limited BUY NEW slots.

    BUY NEW priority is:

        1. Business Score
        2. Technical Score
        3. H1 Priority
        4. Investment Rank

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
        # Entry Quality remains the hard BUY NEW timing gate.
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
    # BUSINESS SCORE SAFETY
    #
    # Business Score should normally already exist because
    # rank_investment_candidates() creates it.
    #
    # Retain a safe fallback so this function remains robust
    # if called independently.
    # --------------------------------------------------------

    if "Business Score" not in candidates.columns:

        if "Growth Score" in candidates.columns:

            growth_score = pd.to_numeric(

                candidates["Growth Score"],

                errors="coerce",

            ).fillna(0.0)

        else:

            growth_score = pd.Series(

                0.0,

                index=candidates.index,

            )

        if "Quality Score" in candidates.columns:

            quality_score = pd.to_numeric(

                candidates["Quality Score"],

                errors="coerce",

            ).fillna(0.0)

        else:

            quality_score = pd.Series(

                0.0,

                index=candidates.index,

            )

        candidates["Business Score"] = (

            growth_score + quality_score

        ) / 2.0

    # --------------------------------------------------------
    # BUY NEW PRIORITY RANK
    #
    # Investment Rank remains available as the authoritative
    # investment ranking.
    #
    # However, the completed diagnostic showed that using
    # Investment Rank as the primary BUY NEW ordering caused
    # selected BUY NEW candidates to underperform the broader
    # eligible opportunity universe.
    #
    # BUY NEW therefore separates:
    #
    #   Investment Score
    #       Eligibility gate
    #
    #   Business Score
    #       Primary opportunity ranking
    #
    #   Technical Score
    #       Secondary entry/timing ordering
    #
    #   H1
    #       Secondary continuation tie-breaker
    #
    #   Investment Rank
    #       Final deterministic tie-breaker
    #
    # This prevents short-term Technical/Investment Score
    # strength from dominating the selection of underlying
    # business opportunities.
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
        # Normalise priority columns.
        # ----------------------------------------------------

        eligible_candidates["Business Score"] = pd.to_numeric(

            eligible_candidates["Business Score"],

            errors="coerce",

        ).fillna(0.0)

        if "Technical Score" in eligible_candidates.columns:

            eligible_candidates["Technical Score"] = pd.to_numeric(

                eligible_candidates["Technical Score"],

                errors="coerce",

            )

        else:

            eligible_candidates["Technical Score"] = 0.0

        # ----------------------------------------------------
        # FINAL BUY NEW PRIORITY ORDER
        #
        # 1. Business Score
        # 2. Technical Score
        # 3. H1 Priority
        # 4. Investment Rank
        # ----------------------------------------------------

        sort_columns = [

            "Business Score",

            "Technical Score",

            "_H1 Priority",

        ]

        ascending = [

            False,

            False,

            True,

        ]

        if "Investment Rank" in eligible_candidates.columns:

            sort_columns.append(

                "Investment Rank"

            )

            ascending.append(

                True

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

    portfolio_summary=None,

    top_n=MAX_BUY_NEW_DECISIONS,

):

    """
    Execute the complete BUY NEW candidate selection pipeline.

    Pipeline
    --------

    New Stock Universe

            ↓

    Investment Score >= 75 Eligibility

            ↓

    Ownership Filter

            ↓

    BUY / STRONG BUY Filter

            ↓

    Investment Ranking

            ↓

    Business Score Ranking

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

        Which opportunities have the strongest composite
        Investment Scores?

    Business Score answers:

        Which eligible opportunities have the strongest
        underlying Growth + Quality profile?

    BUY NEW Priority Rank answers:

        Which eligible business opportunities should receive
        priority for the limited BUY NEW slots?

    Entry timing remains a gate.

    Technical Score is a secondary ordering factor.

    H1 is a secondary continuation tie-breaker.

    The Investment Score threshold remains 75.

    Existing holdings are excluded from the BUY NEW candidate
    pool and continue through the existing-holding decision
    path as BUY MORE / HOLD / REDUCE / SELL.

    Returns
    -------

    pd.DataFrame

        Prioritised BUY NEW candidate shortlist containing
        genuinely unowned positions.
    """

    # --------------------------------------------------------
    # NEW OPPORTUNITY UNIVERSE
    #
    # get_new_stock_opportunities() already enforces:
    #
    #     Investment Score >= 75
    #
    # This is deliberately an eligibility gate rather than
    # a top-N Investment Score selection.
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
    # OWNERSHIP FILTER
    #
    # BUY NEW candidates must be genuinely unowned positions.
    #
    # Existing holdings are handled by the existing-holding
    # decision path as BUY MORE / HOLD / REDUCE / SELL.
    #
    # Ownership is taken from portfolio_summary, which is the
    # authoritative current portfolio state.
    # --------------------------------------------------------

    if (

        portfolio_summary is not None

        and not portfolio_summary.empty

        and "Ticker" in portfolio_summary.columns

        and "Ticker" in new_opportunities.columns

    ):

        owned_tickers = set(

            portfolio_summary[

                "Ticker"

            ]

            .dropna()

            .astype(str)

            .str.strip()

            .str.upper()

        )

        new_opportunities = (

            new_opportunities[

                ~new_opportunities[

                    "Ticker"

                ]

                .astype(str)

                .str.strip()

                .str.upper()

                .isin(

                    owned_tickers

                )

            ]

            .copy()

        )

    if new_opportunities.empty:

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
    # Investment Rank is retained for audit/reporting.
    #
    # Business Score is calculated here.
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
    # The complete eligible Investment Score >= 75 universe
    # is reviewed here.
    #
    # We deliberately do NOT call select_top_candidates()
    # before Entry Quality / Business ranking because that
    # would reintroduce Investment Score as the primary
    # BUY NEW selection mechanism.
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
    #
    # build_candidate_review() has already calculated the
    # authoritative BUY NEW Priority Rank.
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
    # The top_n limit applies only after:
    #
    #     Investment Score eligibility
    #     Ownership exclusion
    #     BUY signal filtering
    #     Entry Quality eligibility
    #     Business Score ranking
    #     Technical Score ordering
    #     H1 ordering
    #
    # Up to three genuinely new BUY NEW candidates are
    # selected by default.
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