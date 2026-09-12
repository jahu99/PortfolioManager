"""
Portfolio Reallocation Engine

Purpose
-------

Perform whole-portfolio capital reallocation downstream from the
Final Portfolio Decision layer.

The Final Portfolio Decision answers:

    "What is the appropriate decision for this asset individually?"

The Portfolio Reallocation Engine answers:

    "Given the entire portfolio, where should capital be allocated
    to maximise portfolio growth subject to diversification and
    governance constraints?"

Core principles
---------------

- Review the entire portfolio, not only explicit REDUCE / SELL decisions.

- HOLD does not mean permanently untouchable.

- A HOLD position may become a funding candidate when a materially
  stronger opportunity exists elsewhere.

- Explicit SELL decisions remain strong funding candidates.

- Explicit REDUCE decisions remain preferred funding candidates.

- Strong BUY NEW and BUY MORE opportunities compete for capital.

- Existing holdings compete with new opportunities.

- Capital should move only when the destination represents a
  meaningful improvement over the source.

- Avoid unnecessary turnover.

- Preserve diversification.

- Respect maximum position sizing.

- CASH is not an investment candidate.

- The engine produces recommendations and a proposed reallocation plan.
  It does not execute trades.
"""

import os

import pandas as pd


from config.investment_config import (
    MAX_POSITION_PERCENT
)

# ============================================================
# CONFIGURATION
# ============================================================

HOLDINGS_FILE = "portfolio/holdings_raw.csv"


# Minimum portfolio movement required before recommending a trade.
MIN_REALLOCATION_VALUE = 5.00


# HOLD positions below this score become potential funding candidates
# if stronger opportunities exist.
WEAK_HOLD_SCORE = 60.0


# HOLD positions below this score are stronger funding candidates.
VERY_WEAK_HOLD_SCORE = 45.0


# Strong opportunities eligible to receive capital.
MIN_DESTINATION_SCORE = 75.0


# Maximum percentage of a portfolio position that can be reduced
# by this engine in a single run unless the upstream final decision
# explicitly says SELL.
MAX_OPPORTUNITY_REDUCTION_PERCENT = 50.0


# Cash added to the portfolio at each assessment.
# This mirrors the discretionary cash contribution used by the
# original capital allocation process.
ASSESSMENT_CASH_CONTRIBUTION = 15.0


# Minimum score advantage required before a HOLD position may be
# challenged as a source of capital for a materially stronger
# governed destination.
MIN_REALLOCATION_SCORE_ADVANTAGE = 10.0

# ============================================================
# REALLOCATION GOVERNANCE
# ============================================================

# Normal minimum transaction size.
MIN_REALLOCATION_VALUE = 5.00

# Cash added by the investor at each assessment.
ASSESSMENT_CASH_CONTRIBUTION = 15.00


# ------------------------------------------------------------
# HOLD CHALLENGE GOVERNANCE
# ------------------------------------------------------------

# HOLD positions are not automatically funding sources.
#
# A HOLD may only be challenged when it is genuinely weak and
# there is a materially stronger governed destination.

HOLD_CHALLENGE_MAX_SCORE = 55.0

# The destination must be materially stronger than the HOLD
# position before capital can be reallocated.

HOLD_CHALLENGE_MIN_SCORE_IMPROVEMENT = 15.0

# Maximum proportion released from a challenged HOLD.

HOLD_CHALLENGE_RELEASE_PCT = 25.0


# ------------------------------------------------------------
# CORE ASSET PROTECTION
# ------------------------------------------------------------

# Broad/core ETFs should not automatically be sold merely
# because an individual stock has a higher Investment Score.

PROTECT_ETF_HOLDINGS = True


# ------------------------------------------------------------
# DESTINATION CONCENTRATION GOVERNANCE
# ------------------------------------------------------------

# Prevent recalibration from pouring all available capital into
# the first-ranked destination.

MAX_DESTINATION_SHARE_OF_REALLOCATION = 0.35


# ============================================================
# DESTINATION ALLOCATION
# ============================================================

MAX_REALLOCATION_DESTINATIONS = 5

MIN_REALLOCATION_TRADE_VALUE = 2.00

# ============================================================
# HOLD CHALLENGE GOVERNANCE
# ============================================================

# HOLD is the default portfolio decision.
# Automatic capital recycling from HOLD positions is deliberately
# restrictive and must never behave like implicit SELL governance.

HOLD_CHALLENGE_MAX_SCORE = 50.0

# A destination must be materially superior before a weak HOLD can
# be challenged for capital recycling.
MIN_HOLD_CHALLENGE_SCORE_ADVANTAGE = 25.0

# Maximum automatic recycling from a HOLD position.
MAX_WEAK_HOLD_REDUCTION_PERCENT = 10.0
MAX_VERY_WEAK_HOLD_REDUCTION_PERCENT = 15.0

# Avoid creating trivial portfolio churn.
MIN_HOLD_CHALLENGE_RELEASE_VALUE = 3.00

MIN_MEANINGFUL_DEPLOYMENT_VALUE = 7.5

# ============================================================
# HELPERS
# ============================================================

def safe_float(value, default=0.0):

    try:

        if value is None:
            return default

        if isinstance(value, (list, tuple)):
            return default

        if hasattr(value, "iloc"):

            if len(value) == 0:
                return default

            value = value.iloc[0]

        if pd.isna(value):
            return default

        return float(value)

    except Exception:

        return default


def clean_ticker(value):

    if value is None:
        return ""

    return str(value).strip().upper()


def normalise_action(value):

    if value is None:
        return "HOLD"

    return str(value).strip().upper()


def get_score(row):

    """
    Return the allocation-relevant score.

    Final Portfolio Decisions currently expose Investment Score
    for reporting compatibility.

    For ETFs this may represent the ETF allocation score.
    """

    return safe_float(

        row.get(

            "Investment Score",

            row.get(

                "investment_score",

                row.get(

                    "ETF Score",

                    row.get(

                        "etf_score",

                        0

                    )

                )

            )

        )

    )


def load_actual_holdings():

    """
    Load actual portfolio holdings.

    Quantity > 0 means owned.
    """

    if not os.path.exists(HOLDINGS_FILE):

        print(
            f"WARNING: {HOLDINGS_FILE} not found."
        )

        return pd.DataFrame()

    try:

        holdings = pd.read_csv(
            HOLDINGS_FILE
        )

    except Exception as e:

        print(
            f"Unable to read holdings file: {e}"
        )

        return pd.DataFrame()

    required_columns = [

        "Ticker",

        "Quantity",

        "Market Value"

    ]

    missing = [

        column

        for column in required_columns

        if column not in holdings.columns

    ]

    if missing:

        print(
            f"Holdings file missing columns: {missing}"
        )

        return pd.DataFrame()

    holdings = holdings.copy()

    holdings["Ticker"] = (

        holdings["Ticker"]

        .astype(str)

        .str.strip()

        .str.upper()

    )

    holdings["Quantity"] = pd.to_numeric(

        holdings["Quantity"],

        errors="coerce"

    ).fillna(0)

    holdings["Market Value"] = pd.to_numeric(

        holdings["Market Value"],

        errors="coerce"

    ).fillna(0)

    holdings = holdings.loc[
        holdings["Ticker"] != "CASH"
    ]

    holdings = holdings.loc[
        holdings["Quantity"] > 0
    ]

    return holdings


# ============================================================
# DECISION NORMALISATION
# ============================================================

def normalise_final_decisions(final_portfolio_decisions):

    """
    Convert final decisions into a DataFrame.
    """

    if final_portfolio_decisions is None:

        return pd.DataFrame()

    if isinstance(
        final_portfolio_decisions,
        pd.DataFrame
    ):

        decisions = (
            final_portfolio_decisions.copy()
        )

    elif isinstance(
        final_portfolio_decisions,
        list
    ):

        decisions = pd.DataFrame(
            final_portfolio_decisions
        )

    else:

        return pd.DataFrame()

    if decisions.empty:

        return decisions

    if "Ticker" not in decisions.columns:

        return pd.DataFrame()

    decisions["Ticker"] = (

        decisions["Ticker"]

        .astype(str)

        .str.strip()

        .str.upper()

    )

    if "Final Decision" not in decisions.columns:

        if "Action" in decisions.columns:

            decisions["Final Decision"] = (
                decisions["Action"]
            )

        elif "Proposed Action" in decisions.columns:

            decisions["Final Decision"] = (
                decisions["Proposed Action"]
            )

        else:

            decisions["Final Decision"] = "HOLD"

    decisions["Final Decision"] = (

        decisions["Final Decision"]

        .fillna("HOLD")

        .astype(str)

        .str.strip()

        .str.upper()

    )

    return decisions


# ============================================================
# FUNDING PRIORITY
# ============================================================

def get_funding_priority(
    final_decision,
    score,
    market_value
):
    """
    Calculate how attractive an existing position is as a
    source of capital.

    Higher values mean stronger funding candidates.

    Priority hierarchy is structurally enforced:

    1. SELL
    2. REDUCE
    3. Weak HOLD

    Investment quality and position size rank candidates
    within their governance category but cannot cause a lower
    governance category to outrank a higher one.
    """

    final_decision = normalise_action(
        final_decision
    )

    score = safe_float(
        score
    )

    market_value = safe_float(
        market_value
    )

    # ====================================================
    # GOVERNANCE PRIORITY BANDS
    #
    # These bands deliberately do not overlap.
    # ====================================================

    if final_decision == "SELL":

        base_priority = 300.0

    elif final_decision.startswith(
        "REDUCE"
    ):

        base_priority = 200.0

    else:

        base_priority = 100.0

    # ====================================================
    # RELATIVE INVESTMENT QUALITY
    #
    # Used only to rank positions within their governance
    # category.
    # ====================================================

    quality_priority = 0.0

    if score < VERY_WEAK_HOLD_SCORE:

        quality_priority = 50.0

    elif score < WEAK_HOLD_SCORE:

        quality_priority = 30.0

    elif score < 75.0:

        quality_priority = 15.0

    elif score < 85.0:

        quality_priority = 5.0

    # ====================================================
    # POSITION SIZE
    #
    # Used only as a secondary ranking factor.
    # ====================================================

    size_priority = min(
        market_value / 10.0,
        20.0
    )

    return round(
        base_priority
        + quality_priority
        + size_priority,
        2
    )

def get_position_capacity(
    current_value,
    total_portfolio_value
):

    """
    Calculate how much additional capital can be allocated
    to a position before reaching MAX_POSITION_PERCENT.
    """

    current_value = safe_float(
        current_value
    )

    total_portfolio_value = safe_float(
        total_portfolio_value
    )

    if total_portfolio_value <= 0:

        return 0.0

    maximum_position_value = (

        total_portfolio_value

        *

        safe_float(
            MAX_POSITION_PERCENT
        )

        /

        100

    )

    capacity = (

        maximum_position_value

        -

        current_value

    )

    return round(

        max(
            0.0,
            capacity
        ),

        2

    )


def select_deployment_destinations(
    eligible_destinations,
    total_available_capital,
    meaningful_deployment_value=MIN_MEANINGFUL_DEPLOYMENT_VALUE
):
    """
    Select the number of destinations that can receive
    meaningful capital deployment.

    Capital is concentrated into the highest-priority governed
    destinations when available capital is limited.
    """

    if not eligible_destinations:
        return []

    ranked_destinations = sorted(
        eligible_destinations,
        key=lambda destination: (
            -safe_float(
                destination.get(
                    "Allocation Weight",
                    0
                )
            ),
            -safe_float(
                destination.get(
                    "Investment Score",
                    0
                )
            ),
            clean_ticker(
                destination.get(
                    "Ticker",
                    ""
                )
            )
        )
    )

    meaningful_deployment_value = max(
        1.0,
        safe_float(
            meaningful_deployment_value
        )
    )

    destination_count = max(
        1,
        int(
            total_available_capital
            // meaningful_deployment_value
        )
    )

    destination_count = min(
        destination_count,
        len(ranked_destinations)
    )

    return ranked_destinations[
        :destination_count
    ]


# ============================================================
# DESTINATION PRIORITY
# ============================================================

# ============================================================
# DESTINATION PRIORITY
# ============================================================

def get_destination_priority(
    final_decision,
    score,
    owned
):
    """
    Calculate attractiveness as a destination for capital.

    Portfolio recalibration does not make investment decisions.

    Only authoritative Final Portfolio Decisions of BUY MORE
    and BUY NEW are eligible destinations.

    HOLD positions are protected and remain unchanged.
    SELL and REDUCE positions are funding sources.
    """

    final_decision = normalise_action(
        final_decision
    )

    score = safe_float(
        score
    )

    if final_decision in {
        "BUY MORE",
        "BUY NEW"
    }:
        return score

    return 0.0

# ============================================================
# HOLD CHALLENGE / FUNDING HELPERS
# ============================================================

def is_hold_funding_eligible(position):
    """
    Determine whether a HOLD position is structurally eligible
    for a portfolio-level capital recycling challenge.

    HOLD remains the default portfolio decision.

    ETFs are protected automatically because they may represent
    core, diversification, or strategic portfolio exposure.

    Individual stocks may proceed to the stricter evidence test,
    but eligibility alone does not authorise capital recycling.
    """

    final_decision = normalise_action(
        position.get(
            "Final Decision",
            "HOLD"
        )
    )

    asset_type = str(
        position.get(
            "Asset Type",
            ""
        )
    ).strip().upper()

    # This helper applies only to HOLD positions.
    if final_decision != "HOLD":
        return False

    # ETFs are protected from automatic opportunity-based
    # capital recycling.
    if asset_type == "ETF":
        return False

    # Unknown asset types are protected by default.
    if asset_type != "STOCK":
        return False

    return True



# ============================================================
# HOLD CHALLENGE / FUNDING HELPERS
# ============================================================

def get_hold_reduction_percent(
    source_score,
    destination_score,
    source_value=0.0,
    improves_diversification=False
):
    """
    Determine the maximum percentage of a HOLD position that may
    be recycled into a specific stronger governed destination.

    GOVERNANCE
    ----------

    HOLD remains the default.

    A HOLD position may be challenged only when:

        1. The source position is sufficiently weak.
        2. The destination has a material quality advantage.
        3. The proposed release is economically meaningful.
        4. The reduction remains proportionate.

    A HOLD is never automatically converted into a full SELL.
    """

    source_score = safe_float(source_score)
    destination_score = safe_float(destination_score)
    source_value = safe_float(source_value)

    advantage = (
        destination_score
        - source_score
    )

    # ========================================================
    # MATERIAL QUALITY ADVANTAGE
    # ========================================================

    if advantage < MIN_REALLOCATION_SCORE_ADVANTAGE:
        return 0.0

    # ========================================================
    # STRONG HOLD PROTECTION
    # ========================================================

    if source_score >= 70.0:
        return 0.0

    # ========================================================
    # DETERMINE PERMITTED REDUCTION
    # ========================================================

    permitted_percent = 0.0

    # --------------------------------------------------------
    # Moderate HOLD
    # --------------------------------------------------------

    if source_score >= 60.0:

        if advantage < 20.0:
            return 0.0

        permitted_percent = min(
            MAX_OPPORTUNITY_REDUCTION_PERCENT,
            15.0
        )

    # --------------------------------------------------------
    # Reasonable HOLD
    # --------------------------------------------------------

    elif source_score >= 50.0:

        if advantage < 20.0:
            return 0.0

        if improves_diversification:

            permitted_percent = min(
                MAX_OPPORTUNITY_REDUCTION_PERCENT,
                20.0
            )

        else:

            permitted_percent = min(
                MAX_OPPORTUNITY_REDUCTION_PERCENT,
                15.0
            )

    # --------------------------------------------------------
    # Weak HOLD
    # --------------------------------------------------------

    else:

        if advantage >= 25.0:

            if improves_diversification:

                permitted_percent = min(
                    MAX_OPPORTUNITY_REDUCTION_PERCENT,
                    25.0
                )

            else:

                permitted_percent = min(
                    MAX_OPPORTUNITY_REDUCTION_PERCENT,
                    20.0
                )

        elif advantage >= 20.0:

            permitted_percent = min(
                MAX_OPPORTUNITY_REDUCTION_PERCENT,
                15.0
            )

        else:
            return 0.0

    # ========================================================
    # MINIMUM MEANINGFUL RELEASE
    # ========================================================

    proposed_release = (
        source_value
        * permitted_percent
        / 100.0
    )

    if (
        source_value > 0
        and proposed_release
        < MIN_HOLD_CHALLENGE_RELEASE_VALUE
    ):
        return 0.0

    return round(
        permitted_percent,
        2
    )

def evaluate_hold_replacement(
    source_position,
    destinations,
    sector_exposure_percent
):
    """
    Evaluate whether a HOLD position should release capital for a
    specific governed replacement destination.

    GOVERNANCE PRINCIPLES
    ---------------------

    HOLD is the default portfolio decision.

    A lower Investment Score does not, by itself, justify reducing a
    HOLD position.

    Capital may only be released from a HOLD when there is an
    exceptional opportunity-cost case involving a specific governed
    destination.

    The replacement must demonstrate both:

    1. A substantial quality advantage, and
    2. A genuine portfolio benefit, preferably diversification or
       concentration reduction.

    This prevents unnecessary turnover and protects long-term
    compounding positions.

    ETFs are protected by is_hold_funding_eligible() before this
    function is called.

    Returns
    -------

    {
        "eligible": bool,
        "destination": dict or None,
        "reduction_percent": float,
        "reason": str
    }
    """

    # ========================================================
    # GOVERNANCE THRESHOLDS
    # ========================================================

    # A HOLD is protected unless the replacement opportunity is
    # materially exceptional.

    STRONG_HOLD_PROTECTION_SCORE = 65.0

    # Minimum absolute quality required for a replacement.
    MIN_DESTINATION_SCORE = 80.0

    # Minimum advantage required even when diversification improves.
    MIN_DIVERSIFYING_SCORE_ADVANTAGE = 35.0

    # Much higher threshold when there is no diversification benefit.
    MIN_EXCEPTIONAL_SCORE_ADVANTAGE = 45.0

    # Source sector must be meaningfully concentrated before
    # diversification alone can justify recycling a HOLD.
    MIN_SOURCE_SECTOR_CONCENTRATION = 30.0

    # The destination sector must provide a meaningful exposure
    # improvement.
    MIN_SECTOR_EXPOSURE_ADVANTAGE = 10.0

    # HOLD recycling should be conservative.
    MAX_HOLD_REDUCTION_PERCENT = 15.0

    # Avoid generating economically meaningless funding movements.
    MIN_HOLD_RELEASE_VALUE = 1.0

    # ========================================================
    # SOURCE POSITION
    # ========================================================

    source_score = safe_float(
        source_position.get(
            "Investment Score",
            0
        )
    )

    source_value = safe_float(
        source_position.get(
            "Current Value",
            0
        )
    )

    source_sector = str(
        source_position.get(
            "Sector",
            ""
        )
    ).strip()

    source_ticker = clean_ticker(
        source_position.get(
            "Ticker",
            ""
        )
    )

    if not source_ticker:

        return {
            "eligible": False,
            "destination": None,
            "reduction_percent": 0.0,
            "reason": (
                "HOLD replacement evaluation requires "
                "a valid source ticker"
            )
        }

    if source_value < MIN_HOLD_RELEASE_VALUE:

        return {
            "eligible": False,
            "destination": None,
            "reduction_percent": 0.0,
            "reason": (
                "HOLD position is too small to provide "
                "meaningful replacement capital"
            )
        }

    # ========================================================
    # PROTECT STRONG HOLDS
    # ========================================================

    if source_score >= STRONG_HOLD_PROTECTION_SCORE:

        return {
            "eligible": False,
            "destination": None,
            "reduction_percent": 0.0,
            "reason": (
                "HOLD position is sufficiently strong "
                "to remain protected"
            )
        }

    # ========================================================
    # SOURCE CONCENTRATION
    # ========================================================

    source_sector_exposure = safe_float(
        sector_exposure_percent.get(
            source_sector,
            0
        )
    )

    source_sector_concentrated = (
        source_sector_exposure
        >= MIN_SOURCE_SECTOR_CONCENTRATION
    )

    # ========================================================
    # EVALUATE GOVERNED DESTINATIONS
    # ========================================================

    best_candidate = None
    best_candidate_rank = None

    best_improves_diversification = False
    best_score_advantage = 0.0
    best_reduction_percent = 0.0
    best_destination_sector_exposure = 0.0

    for destination in destinations:

        destination_ticker = clean_ticker(
            destination.get(
                "Ticker",
                ""
            )
        )

        # ----------------------------------------------------
        # Never recycle a position into itself.
        # ----------------------------------------------------

        if (
            not destination_ticker
            or destination_ticker == source_ticker
        ):
            continue

        destination_score = safe_float(
            destination.get(
                "Investment Score",
                0
            )
        )

        destination_sector = str(
            destination.get(
                "Sector",
                ""
            )
        ).strip()

        destination_weight = safe_float(
            destination.get(
                "Allocation Weight",
                destination.get(
                    "Destination Priority",
                    0
                )
            )
        )

        score_advantage = (
            destination_score
            - source_score
        )

        # ====================================================
        # REPLACEMENT MUST BE HIGH QUALITY
        # ====================================================

        if destination_score < MIN_DESTINATION_SCORE:
            continue

        # ====================================================
        # SECTOR COMPARISON
        # ====================================================

        destination_sector_exposure = safe_float(
            sector_exposure_percent.get(
                destination_sector,
                0
            )
        )

        same_sector = (
            bool(source_sector)
            and bool(destination_sector)
            and source_sector.upper()
            == destination_sector.upper()
        )

        improves_diversification = False

        if not same_sector:

            if (
                source_sector_concentrated
                and source_sector_exposure
                >= (
                    destination_sector_exposure
                    + MIN_SECTOR_EXPOSURE_ADVANTAGE
                )
            ):

                improves_diversification = True

        # ====================================================
        # SAME-SECTOR PROTECTION
        # ====================================================

        # Do not churn a HOLD into another ticker in the same
        # sector. A score difference alone is not enough.

        if same_sector:
            continue

        # ====================================================
        # DESTINATION CONCENTRATION PROTECTION
        # ====================================================

        # Do not recycle capital into an already concentrated
        # sector.

        if destination_sector_exposure >= 40.0:
            continue

        # ====================================================
        # EXCEPTIONAL REPLACEMENT TEST
        # ====================================================

        if improves_diversification:

            if (
                score_advantage
                < MIN_DIVERSIFYING_SCORE_ADVANTAGE
            ):
                continue

        else:

            # Without diversification benefit, the replacement
            # must be exceptional.

            if (
                score_advantage
                < MIN_EXCEPTIONAL_SCORE_ADVANTAGE
            ):
                continue

        # ====================================================
        # DETERMINE CONSERVATIVE REDUCTION
        # ====================================================

        if improves_diversification:

            reduction_percent = 15.0

        else:

            reduction_percent = 10.0

        reduction_percent = min(
            reduction_percent,
            MAX_HOLD_REDUCTION_PERCENT
        )

        proposed_release_value = (
            source_value
            * reduction_percent
            / 100.0
        )

        if proposed_release_value < MIN_HOLD_RELEASE_VALUE:
            continue

        # ====================================================
        # RANK CANDIDATES
        #
        # Prefer:
        #
        # 1. Diversification improvement
        # 2. Higher score advantage
        # 3. Stronger allocation weight
        # ====================================================

        candidate_rank = (
            1 if improves_diversification else 0,
            score_advantage,
            destination_weight
        )

        if (
            best_candidate is None
            or candidate_rank > best_candidate_rank
        ):

            best_candidate = destination
            best_candidate_rank = candidate_rank

            best_improves_diversification = (
                improves_diversification
            )

            best_score_advantage = (
                score_advantage
            )

            best_reduction_percent = (
                reduction_percent
            )

            best_destination_sector_exposure = (
                destination_sector_exposure
            )

    # ========================================================
    # NO JUSTIFIED REPLACEMENT
    # ========================================================

    if best_candidate is None:

        return {
            "eligible": False,
            "destination": None,
            "reduction_percent": 0.0,
            "reason": (
                "HOLD retained because no exceptional "
                "portfolio-improving replacement was identified"
            )
        }

    # ========================================================
    # BUILD EXPLANATION
    # ========================================================

    destination_ticker = clean_ticker(
        best_candidate.get(
            "Ticker",
            ""
        )
    )

    if best_improves_diversification:

        reason = (
            f"HOLD position partially challenged by "
            f"{destination_ticker}: "
            f"{best_score_advantage:.1f}-point quality "
            f"advantage and meaningful diversification "
            f"improvement from "
            f"{source_sector_exposure:.1f}% to a sector "
            f"currently at "
            f"{best_destination_sector_exposure:.1f}% exposure"
        )

    else:

        reason = (
            f"HOLD position partially challenged only because "
            f"{destination_ticker} demonstrates an exceptional "
            f"{best_score_advantage:.1f}-point quality advantage"
        )

    return {

        "eligible": True,

        "destination": best_candidate,

        "reduction_percent": round(
            best_reduction_percent,
            2
        ),

        "reason": reason
    }
# ============================================================
# MAIN ENGINE
# ============================================================

def generate_portfolio_reallocation(
    final_portfolio_decisions,
    portfolio_value,
    min_reallocation_trade_value=1.0
):
    """
    Generate governed portfolio capital reallocation.

    GOVERNANCE PRINCIPLES
    ---------------------

    1. Explicit SELL decisions release capital.

    2. Explicit REDUCE decisions release the governed
       percentage of capital.

    3. HOLD remains the default.

    4. A HOLD may only release capital when
       evaluate_hold_replacement() identifies a specific,
       materially superior governed destination.

    5. HOLD funding is destination-specific and cannot
       subsequently be redirected elsewhere.

    6. ETFs are protected from automatic opportunity-based
       recycling through is_hold_funding_eligible().

    7. Assessment cash is discretionary and may support
       eligible destinations.

    8. SELL and REDUCE proceeds are discretionary capital.

    9. Destination allocation is calculated before funding
       transactions are generated.

    10. Position capacity and minimum meaningful trade
        values are respected.

    Returns
    -------

    {
        "reallocation": pandas.DataFrame,
        "summary": dict
    }
    """

    # ========================================================
    # NORMALISE INPUT
    # ========================================================

    if final_portfolio_decisions is None:

        return {
            "reallocation": pd.DataFrame(),
            "summary": {
                "Assessment Cash": 0.0,
                "Released From Holdings": 0.0,
                "Total Released": 0.0,
                "Total Reallocated": 0.0,
                "Unallocated Capital": 0.0,
                "Funding Sources": 0,
                "Destinations": 0
            }
        }

    if isinstance(
        final_portfolio_decisions,
        pd.DataFrame
    ):

        decisions_df = final_portfolio_decisions.copy()

    else:

        decisions_df = pd.DataFrame(
            final_portfolio_decisions
        )

    if decisions_df.empty:

        return {
            "reallocation": pd.DataFrame(),
            "summary": {
                "Assessment Cash": 0.0,
                "Released From Holdings": 0.0,
                "Total Released": 0.0,
                "Total Reallocated": 0.0,
                "Unallocated Capital": 0.0,
                "Funding Sources": 0,
                "Destinations": 0
            }
        }

    portfolio_value = safe_float(
        portfolio_value
    )

    # ========================================================
    # NORMALISE DECISIONS
    # ========================================================

    decisions = normalise_final_decisions(
        decisions_df
    )

    if decisions is None:
        decisions = []

    elif isinstance(decisions, pd.DataFrame):
        decisions = decisions.to_dict("records")

    if not decisions:
        return {
            "reallocation": pd.DataFrame(),
            "summary": {
                "Assessment Cash": 0.0,
                "Released From Holdings": 0.0,
                "Total Released": 0.0,
                "Total Reallocated": 0.0,
                "Unallocated Capital": 0.0,
                "Funding Sources": 0,
                "Destinations": 0
            }
        }
    # ========================================================
    # BUILD CURRENT POSITIONS
    # ========================================================

    current_positions = []

    for row in decisions:

        ticker = clean_ticker(
            row.get(
                "Ticker",
                ""
            )
        )

        if not ticker:

            continue

        current_value = safe_float(
            row.get(
                "Current Value",
                row.get(
                    "Market Value",
                    0
                )
            )
        )

        owned = bool(
            row.get(
                "Owned",
                current_value > 0
            )
        )

        if not owned:

            continue

        final_decision = normalise_action(
            row.get(
                "Final Decision",
                row.get(
                    "Action",
                    ""
                )
            )
        )

        sector = str(
            row.get(
                "Sector",
                ""
            )
        ).strip()

        asset_type = str(
            row.get(
                "Asset Type",
                "STOCK"
            )
        ).strip().upper()

        score = safe_float(
            row.get(
                "Investment Score",
                0
            )
        )

        current_allocation_percent = 0.0

        if portfolio_value > 0:

            current_allocation_percent = (
                current_value
                / portfolio_value
                * 100.0
            )

        current_positions.append(
            {
                "Ticker": ticker,
                "Name": row.get(
                    "Name",
                    ticker
                ),
                "Current Value": current_value,
                "Current Quantity": safe_float(
                    row.get(
                        "Current Quantity",
                        row.get(
                            "Quantity",
                            0
                        )
                    )
                ),
                "Current Allocation %": round(
                    current_allocation_percent,
                    2
                ),
                "Sector": sector,
                "Asset Type": asset_type,
                "Final Decision": final_decision,
                "Investment Score": score,
                "Owned": True,
                "Funding Priority": get_funding_priority(
                    final_decision,
                    score,
                    True
                )
            }
        )

    # ========================================================
    # CALCULATE SECTOR EXPOSURE
    # ========================================================

    sector_values = {}

    for position in current_positions:

        sector = position.get(
            "Sector",
            ""
        )

        current_value = safe_float(
            position.get(
                "Current Value",
                0
            )
        )

        sector_values[sector] = (
            sector_values.get(
                sector,
                0.0
            )
            + current_value
        )

    sector_exposure_percent = {}

    if portfolio_value > 0:

        for sector, value in sector_values.items():

            sector_exposure_percent[sector] = round(
                value
                / portfolio_value
                * 100.0,
                2
            )

    # ========================================================
    # BUILD DESTINATIONS
    # ========================================================

    destinations = []

    for row in decisions:

        ticker = clean_ticker(
            row.get(
                "Ticker",
                ""
            )
        )

        if not ticker:

            continue

        final_decision = normalise_action(
            row.get(
                "Final Decision",
                row.get(
                    "Action",
                    ""
                )
            )
        )

        # ----------------------------------------------------
        # Only genuine governed additions are destinations.
        # ----------------------------------------------------

        if final_decision not in (
            "BUY",
            "BUY MORE",
            "STRONG BUY",
            "ADD"
        ):

            continue

        score = safe_float(
            row.get(
                "Investment Score",
                0
            )
        )

        current_value = safe_float(
            row.get(
                "Current Value",
                row.get(
                    "Market Value",
                    0
                )
            )
        )

        owned = bool(
            row.get(
                "Owned",
                current_value > 0
            )
        )

        sector = str(
            row.get(
                "Sector",
                ""
            )
        ).strip()

        asset_type = str(
            row.get(
                "Asset Type",
                "STOCK"
            )
        ).strip().upper()

        destination_priority = get_destination_priority(
            final_decision,
            score,
            owned
        )

        position_capacity = get_position_capacity(
            current_value,
            portfolio_value
        )

        destinations.append(
            {
                "Ticker": ticker,
                "Name": row.get(
                    "Name",
                    ticker
                ),
                "Action": "ADD",
                "Investment Score": score,
                "Destination Priority": (
                    destination_priority
                ),
                "Current Value": current_value,
                "Position Capacity": position_capacity,
                "Owned": owned,
                "Final Decision": final_decision,
                "Sector": sector,
                "Asset Type": asset_type
            }
        )

    destinations = sorted(
        destinations,
        key=lambda x: (
            -safe_float(
                x.get(
                    "Destination Priority",
                    0
                )
            ),
            -safe_float(
                x.get(
                    "Investment Score",
                    0
                )
            ),
            x.get(
                "Ticker",
                ""
            )
        )
    )

    # ========================================================
    # APPLY DESTINATION ALLOCATION WEIGHTS
    # ========================================================

    eligible_destinations = []

    for destination in destinations:

        sector = destination.get(
            "Sector",
            ""
        )

        sector_exposure = safe_float(
            sector_exposure_percent.get(
                sector,
                0
            )
        )

        current_position_percent = 0.0

        if portfolio_value > 0:

            current_position_percent = (
                safe_float(
                    destination.get(
                        "Current Value",
                        0
                    )
                )
                / portfolio_value
                * 100.0
            )

        decision_multiplier = 1.0
        sector_multiplier = 1.0
        position_multiplier = 1.0

        # ----------------------------------------------------
        # Sector concentration protection.
        # ----------------------------------------------------

        if sector_exposure >= 40.0:

            sector_multiplier = 0.65

        # ----------------------------------------------------
        # Position concentration protection.
        # ----------------------------------------------------

        if current_position_percent >= 10.0:

            position_multiplier = 0.75

        allocation_weight = (
            safe_float(
                destination.get(
                    "Destination Priority",
                    0
                )
            )
            * decision_multiplier
            * sector_multiplier
            * position_multiplier
        )

        destination_copy = destination.copy()

        destination_copy[
            "Allocation Weight"
        ] = round(
            allocation_weight,
            2
        )

        destination_copy[
            "Sector Exposure %"
        ] = round(
            sector_exposure,
            2
        )

        destination_copy[
            "Current Position %"
        ] = round(
            current_position_percent,
            2
        )

        destination_copy[
            "Decision Multiplier"
        ] = decision_multiplier

        destination_copy[
            "Sector Multiplier"
        ] = sector_multiplier

        destination_copy[
            "Position Multiplier"
        ] = position_multiplier

        if (
            safe_float(
                destination_copy.get(
                    "Position Capacity",
                    0
                )
            )
            >= min_reallocation_trade_value
        ):

            eligible_destinations.append(
                destination_copy
            )

    eligible_destination_lookup = {
        clean_ticker(
            destination.get(
                "Ticker",
                ""
            )
        ): destination
        for destination
        in eligible_destinations
    }

    # ========================================================
    # BUILD FUNDING CANDIDATES
    # ========================================================

    funding_candidates = []

    # --------------------------------------------------------
    # Assessment cash
    # --------------------------------------------------------

    if ASSESSMENT_CASH_CONTRIBUTION > 0:

        funding_candidates.append(
            {
                "Ticker": "ASSESSMENT CASH",
                "Name": (
                    "Assessment Cash Contribution"
                ),
                "Current Value": round(
                    ASSESSMENT_CASH_CONTRIBUTION,
                    2
                ),
                "Current Quantity": 0.0,
                "Current Allocation %": 0.0,
                "Sector": "Cash",
                "Asset Type": "CASH",
                "Final Decision": "CASH",
                "Investment Score": 0.0,
                "Funding Priority": 400.0,
                "Owned": False,
                "Funding Reason": (
                    "Assessment cash contribution"
                ),
                "Permitted Release %": 100.0,
                "Authorised Destination": ""
            }
        )

    # --------------------------------------------------------
    # Existing holdings
    # --------------------------------------------------------

    for position in current_positions:

        decision = normalise_action(
            position.get(
                "Final Decision",
                ""
            )
        )

        permitted_percent = 0.0
        funding_reason = ""
        authorised_destination = ""

        # ----------------------------------------------------
        # Explicit SELL
        # ----------------------------------------------------

        if decision == "SELL":

            permitted_percent = 100.0

            funding_reason = (
                "Explicit SELL decision"
            )

        # ----------------------------------------------------
        # Explicit REDUCE
        # ----------------------------------------------------

        elif decision.startswith("REDUCE"):

            if "100%" in decision:

                permitted_percent = 100.0

            elif "75%" in decision:

                permitted_percent = 75.0

            elif "50%" in decision:

                permitted_percent = 50.0

            else:

                permitted_percent = 25.0

            funding_reason = (
                "Explicit REDUCE decision"
            )

        # ----------------------------------------------------
        # HOLD
        #
        # Must have a specific justified replacement.
        # ----------------------------------------------------

        elif (
            decision == "HOLD"
            and is_hold_funding_eligible(
                position
            )
            and eligible_destinations
        ):

            replacement = evaluate_hold_replacement(
                position,
                eligible_destinations,
                sector_exposure_percent
            )

            if replacement.get(
                "eligible",
                False
            ):

                replacement_destination = (
                    replacement.get(
                        "destination"
                    )
                )

                replacement_ticker = clean_ticker(
                    replacement_destination.get(
                        "Ticker",
                        ""
                    )
                    if replacement_destination
                    else ""
                )

                reduction_percent = safe_float(
                    replacement.get(
                        "reduction_percent",
                        0
                    )
                )

                if (
                    replacement_ticker
                    and replacement_ticker
                    in eligible_destination_lookup
                    and reduction_percent > 0
                ):

                    permitted_percent = (
                        reduction_percent
                    )

                    authorised_destination = (
                        replacement_ticker
                    )

                    funding_reason = (
                        replacement.get(
                            "reason",
                            "HOLD challenged by specific "
                            "governed replacement"
                        )
                    )

        if permitted_percent <= 0:

            continue

        candidate = position.copy()

        candidate[
            "Permitted Release %"
        ] = round(
            permitted_percent,
            2
        )

        candidate[
            "Funding Reason"
        ] = funding_reason

        candidate[
            "Authorised Destination"
        ] = authorised_destination

        # Explicit governance ranks above HOLD challenges.

        if decision == "SELL":

            candidate[
                "Funding Priority"
            ] = (
                300.0
                + safe_float(
                    position.get(
                        "Funding Priority",
                        0
                    )
                ) % 100.0
            )

        elif decision.startswith("REDUCE"):

            candidate[
                "Funding Priority"
            ] = (
                200.0
                + safe_float(
                    position.get(
                        "Funding Priority",
                        0
                    )
                ) % 100.0
            )

        else:

            candidate[
                "Funding Priority"
            ] = (
                100.0
                + safe_float(
                    position.get(
                        "Funding Priority",
                        0
                    )
                ) % 100.0
            )

        funding_candidates.append(
            candidate
        )

    funding_candidates = sorted(
        funding_candidates,
        key=lambda x: (
            -safe_float(
                x.get(
                    "Funding Priority",
                    0
                )
            ),
            x.get(
                "Ticker",
                ""
            )
        )
    )

    # ========================================================
    # DEBUG OUTPUT
    # ========================================================

    print(
        "\nPORTFOLIO RECALIBRATION DESTINATIONS"
    )

    print(
        pd.DataFrame(
            destinations
        ).to_string(
            index=False
        )
        if destinations
        else "No eligible Final Portfolio Decision "
        "destinations."
    )

    print(
        "\nPORTFOLIO RECALIBRATION FUNDING CANDIDATES"
    )

    print(
        pd.DataFrame(
            funding_candidates
        ).to_string(
            index=False
        )
        if funding_candidates
        else "No eligible funding candidates."
    )

    print(
        "\nPORTFOLIO REALLOCATION ALLOCATION WEIGHTS"
    )

    print(
        pd.DataFrame(
            eligible_destinations
        ).to_string(
            index=False
        )
        
        if eligible_destinations
        else "No eligible destinations."
    )

    # ========================================================
    # AUTHORISE FUNDING CAPITAL
    # ========================================================

    remaining_funding = {}
    funding_metadata = {}

    assessment_cash = 0.0
    released_from_holdings = 0.0

    for candidate in funding_candidates:

        ticker = candidate.get(
            "Ticker",
            ""
        )

        source_value = safe_float(
            candidate.get(
                "Current Value",
                0
            )
        )

        source_decision = normalise_action(
            candidate.get(
                "Final Decision",
                ""
            )
        )

        permitted_percent = safe_float(
            candidate.get(
                "Permitted Release %",
                0
            )
        )

        if source_decision == "CASH":

            permitted_release = source_value

            assessment_cash += permitted_release

        else:

            permitted_release = (
                source_value
                * permitted_percent
                / 100.0
            )

            released_from_holdings += (
                permitted_release
            )

        permitted_release = round(
            permitted_release,
            2
        )

        if permitted_release <= 0:

            continue

        remaining_funding[ticker] = (
            permitted_release
        )

        funding_metadata[ticker] = (
            candidate.copy()
        )

    total_available_capital = round(
        assessment_cash
        + released_from_holdings,
        2
    )

    # ========================================================
    # SELECT MEANINGFUL DEPLOYMENT DESTINATIONS
    # ========================================================

    deployment_destinations = (
        select_deployment_destinations(
            eligible_destinations=eligible_destinations,
            total_available_capital=total_available_capital
        )
    )


    print(
    "\nPORTFOLIO MEANINGFUL DEPLOYMENT DESTINATIONS"
    )

    print(
        pd.DataFrame(
            deployment_destinations
        ).to_string(
            index=False
        )
        if deployment_destinations
        else "No meaningful deployment destinations."
    )

    # ========================================================
    # ALLOCATE CAPITAL ACROSS DESTINATIONS
    #
    # THIS MUST HAPPEN BEFORE TRANSACTIONS ARE BUILT.
    #
    # destination_allocations is intentionally created here.
    # ========================================================

    destination_allocations = {}

    remaining_capital = total_available_capital

    if (

        deployment_destinations

        and total_available_capital > 0

    ):

        total_weight = sum(
            safe_float(
                destination.get(
                    "Allocation Weight",
                    0
                )
            )
            for destination in deployment_destinations
        )

        # ----------------------------------------------------
        # FIRST PASS
        #
        # Allocate proportionally according to governed
        # destination weights.
        # ----------------------------------------------------

        for destination in deployment_destinations:
            ticker = clean_ticker(
                destination.get(
                    "Ticker",
                    ""
                )
            )

            if not ticker:

                continue

            weight = safe_float(
                destination.get(
                    "Allocation Weight",
                    0
                )
            )

            capacity = safe_float(
                destination.get(
                    "Position Capacity",
                    0
                )
            )

            if total_weight <= 0:

                proposed_allocation = 0.0

            else:

                proposed_allocation = (
                    total_available_capital
                    * weight
                    / total_weight
                )

            allocation = min(
                proposed_allocation,
                capacity
            )

            allocation = round(
                allocation,
                2
            )

            if (
                allocation
                >= min_reallocation_trade_value
            ):

                destination_allocations[ticker] = (
                    allocation
                )

                remaining_capital -= allocation

            else:

                destination_allocations[ticker] = 0.0

        remaining_capital = round(
            max(
                0.0,
                remaining_capital
            ),
            2
        )

        # ----------------------------------------------------
        # SECOND PASS
        #
        # Redistribute capital left over because some
        # destinations reached capacity.
        # ----------------------------------------------------

        while (
            remaining_capital
            >= min_reallocation_trade_value
        ):

            destinations_with_capacity = []

            for destination in deployment_destinations:

                ticker = clean_ticker(
                    destination.get(
                        "Ticker",
                        ""
                    )
                )

                capacity = safe_float(
                    destination.get(
                        "Position Capacity",
                        0
                    )
                )

                already_allocated = safe_float(
                    destination_allocations.get(
                        ticker,
                        0
                    )
                )

                remaining_capacity = max(
                    0.0,
                    capacity
                    - already_allocated
                )

                if (
                    remaining_capacity
                    >= min_reallocation_trade_value
                ):

                    destinations_with_capacity.append(
                        destination
                    )

            if not destinations_with_capacity:

                break

            remaining_weight = sum(
                safe_float(
                    destination.get(
                        "Allocation Weight",
                        0
                    )
                )
                for destination
                in destinations_with_capacity
            )

            if remaining_weight <= 0:

                break

            capital_before_pass = remaining_capital

            for destination in destinations_with_capacity:

                if (
                    remaining_capital
                    < min_reallocation_trade_value
                ):

                    break

                ticker = clean_ticker(
                    destination.get(
                        "Ticker",
                        ""
                    )
                )

                weight = safe_float(
                    destination.get(
                        "Allocation Weight",
                        0
                    )
                )

                capacity = safe_float(
                    destination.get(
                        "Position Capacity",
                        0
                    )
                )

                already_allocated = safe_float(
                    destination_allocations.get(
                        ticker,
                        0
                    )
                )

                remaining_capacity = max(
                    0.0,
                    capacity
                    - already_allocated
                )

                proportional_share = (
                    capital_before_pass
                    * weight
                    / remaining_weight
                )

                additional_allocation = min(
                    proportional_share,
                    remaining_capacity,
                    remaining_capital
                )

                additional_allocation = round(
                    additional_allocation,
                    2
                )

                if (
                    additional_allocation
                    < min_reallocation_trade_value
                ):

                    continue

                destination_allocations[ticker] = round(
                    already_allocated
                    + additional_allocation,
                    2
                )

                remaining_capital = round(
                    max(
                        0.0,
                        remaining_capital
                        - additional_allocation
                    ),
                    2
                )

            if remaining_capital >= capital_before_pass:

                break

    # ========================================================
    # BUILD REALLOCATION TRANSACTIONS
    #
    # HOLD funding is restricted to its specifically
    # authorised replacement destination.
    # ========================================================

    transactions = []

    remaining_destination_need = {
        ticker: round(
            amount,
            2
        )
        for ticker, amount
        in destination_allocations.items()
        if (
            amount
            >= min_reallocation_trade_value
        )
    }

    # ========================================================
    # FIRST PASS
    #
    # Use destination-specific HOLD funding first.
    # ========================================================

    for source_ticker in list(
        remaining_funding.keys()
    ):

        source_available = safe_float(
            remaining_funding.get(
                source_ticker,
                0
            )
        )

        if source_available <= 0:

            continue

        source_metadata = funding_metadata.get(
            source_ticker,
            {}
        )

        source_action = normalise_action(
            source_metadata.get(
                "Final Decision",
                ""
            )
        )

        authorised_destination = clean_ticker(
            source_metadata.get(
                "Authorised Destination",
                ""
            )
        )

        # Only HOLD funding is destination restricted.

        if (
            source_action != "HOLD"
            or not authorised_destination
        ):

            continue

        destination_need = safe_float(
            remaining_destination_need.get(
                authorised_destination,
                0
            )
        )

        if destination_need <= 0:

            continue

        destination = eligible_destination_lookup.get(
            authorised_destination,
            {}
        )

        if not destination:

            continue

        allocation = min(
            source_available,
            destination_need
        )

        allocation = round(
            allocation,
            2
        )

        if allocation <= 0:

            continue

        transactions.append(
            {
                "Source Ticker": source_ticker,
                "Source Action": "HOLD",
                "Funding Reason": source_metadata.get(
                    "Funding Reason",
                    ""
                ),
                "Authorised Destination": (
                    authorised_destination
                ),
                "Destination Ticker": (
                    authorised_destination
                ),
                "Destination Action": destination.get(
                    "Action",
                    ""
                ),
                "Destination Final Decision": (
                    destination.get(
                        "Final Decision",
                        ""
                    )
                ),
                "Investment Score": round(
                    safe_float(
                        destination.get(
                            "Investment Score",
                            0
                        )
                    ),
                    2
                ),
                "Destination Priority": round(
                    safe_float(
                        destination.get(
                            "Destination Priority",
                            0
                        )
                    ),
                    2
                ),
                "Sector": destination.get(
                    "Sector",
                    ""
                ),
                "Asset Type": destination.get(
                    "Asset Type",
                    ""
                ),
                "Released Capital": allocation,
                "Reallocated Capital": allocation
            }
        )

        remaining_funding[source_ticker] = round(
            source_available
            - allocation,
            2
        )

        remaining_destination_need[
            authorised_destination
        ] = round(
            max(
                0.0,
                destination_need
                - allocation
            ),
            2
        )

    # ========================================================
    # SECOND PASS
    #
    # CASH / SELL / REDUCE funding supports remaining
    # destinations according to funding priority.
    # ========================================================

    for destination in deployment_destinations:

        destination_ticker = clean_ticker(
            destination.get(
                "Ticker",
                ""
            )
        )

        destination_need = safe_float(
            remaining_destination_need.get(
                destination_ticker,
                0
            )
        )

        if destination_need <= 0:

            continue

        for source_ticker in list(
            remaining_funding.keys()
        ):

            if destination_need <= 0:

                break

            source_available = safe_float(
                remaining_funding.get(
                    source_ticker,
                    0
                )
            )

            if source_available <= 0:

                continue

            source_metadata = funding_metadata.get(
                source_ticker,
                {}
            )

            source_action = normalise_action(
                source_metadata.get(
                    "Final Decision",
                    ""
                )
            )

            authorised_destination = clean_ticker(
                source_metadata.get(
                    "Authorised Destination",
                    ""
                )
            )

            # HOLD capital must never leak into another
            # destination.

            if (
                source_action == "HOLD"
                and authorised_destination
            ):

                continue

            allocation = min(
                source_available,
                destination_need
            )

            allocation = round(
                allocation,
                2
            )

            if allocation <= 0:

                continue

            if source_action == "CASH":

                source_action_label = (
                    "CONTRIBUTE CASH"
                )

            else:

                source_action_label = source_action

            transactions.append(
                {
                    "Source Ticker": source_ticker,
                    "Source Action": source_action_label,
                    "Funding Reason": source_metadata.get(
                        "Funding Reason",
                        ""
                    ),
                    "Authorised Destination": "",
                    "Destination Ticker": (
                        destination_ticker
                    ),
                    "Destination Action": destination.get(
                        "Action",
                        ""
                    ),
                    "Destination Final Decision": (
                        destination.get(
                            "Final Decision",
                            ""
                        )
                    ),
                    "Investment Score": round(
                        safe_float(
                            destination.get(
                                "Investment Score",
                                0
                            )
                        ),
                        2
                    ),
                    "Destination Priority": round(
                        safe_float(
                            destination.get(
                                "Destination Priority",
                                0
                            )
                        ),
                        2
                    ),
                    "Sector": destination.get(
                        "Sector",
                        ""
                    ),
                    "Asset Type": destination.get(
                        "Asset Type",
                        ""
                    ),
                    "Released Capital": allocation,
                    "Reallocated Capital": allocation
                }
            )

            remaining_funding[source_ticker] = round(
                source_available
                - allocation,
                2
            )

            destination_need = round(
                destination_need
                - allocation,
                2
            )

            remaining_destination_need[
                destination_ticker
            ] = max(
                0.0,
                destination_need
            )

    # ========================================================
    # CALCULATE SUMMARY
    # ========================================================

    total_reallocated = round(
        sum(
            safe_float(
                transaction.get(
                    "Reallocated Capital",
                    0
                )
            )
            for transaction
            in transactions
        ),
        2
    )

    total_released = round(
        assessment_cash
        + released_from_holdings,
        2
    )

    unallocated_capital = round(
        max(
            0.0,
            total_released
            - total_reallocated
        ),
        2
    )

    funding_sources = len(
        {
            transaction.get(
                "Source Ticker",
                ""
            )
            for transaction
            in transactions
            if transaction.get(
                "Source Ticker",
                ""
            )
        }
    )

    destination_count = len(
        {
            transaction.get(
                "Destination Ticker",
                ""
            )
            for transaction
            in transactions
            if transaction.get(
                "Destination Ticker",
                ""
            )
        }
    )

    summary = {
        "Assessment Cash": round(
            assessment_cash,
            2
        ),
        "Released From Holdings": round(
            released_from_holdings,
            2
        ),
        "Total Released": total_released,
        "Total Reallocated": total_reallocated,
        "Unallocated Capital": unallocated_capital,
        "Funding Sources": funding_sources,
        "Destinations": destination_count
    }

    reallocation_df = pd.DataFrame(
        transactions
    )

    # ========================================================
    # DEBUG OUTPUT
    # ========================================================

    print(
        "\nPORTFOLIO REALLOCATION DETAIL"
    )

    print(
        reallocation_df.to_string(
            index=False
        )
        if not reallocation_df.empty
        else "No portfolio reallocation required."
    )

    print(
        "\nPORTFOLIO REALLOCATION SUMMARY"
    )

    print(
        summary
    )

    # ========================================================
    # RETURN
    # ========================================================

    return {
        "reallocation": reallocation_df,
        "summary": summary
    }