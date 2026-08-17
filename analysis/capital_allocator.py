"""
Capital Allocation Engine

Purpose
-------
Manage portfolio capital allocation using:

    1. Actual portfolio ownership from holdings_raw.csv
    2. Explicit portfolio reduction decisions
    3. Stock investment opportunities
    4. ETF opportunities using ETF Score

Core principles
---------------
- Actual ownership is determined by holdings_raw.csv.
- Quantity > 0 means the asset is owned.
- CASH is never an investment candidate.
- ETFs are valid investment assets.
- BUY MORE and BUY NEW compete on allocation conviction.
- There is NO artificial BUY MORE-first rule.
- Stocks are ranked using Investment Score.
- ETFs are ranked using ETF Score.
- Stock Investment Score and ETF Score remain analytically separate.
- Higher conviction opportunities receive proportionally more capital.
- Capital released from reductions is calculated from:
      Market Value × Reduction %
- Small/economically insignificant reductions are suppressed.
- HOLD is preferred unless there is a meaningful reason to act.
- Existing holdings are protected unless an explicit reduction
  decision has been generated.
- Released capital can be recycled into higher-ranked opportunities.
- The allocator does not create trades simply to use available cash.

Important ETF design
--------------------
ETFs deliberately do NOT receive:

    - Stock Momentum Score
    - Stock Quality Score
    - Stock Investment Score
    - Stock RSI scoring
    - Stock fundamental analysis

Instead, ETF opportunities use:

    ETF Score

as their allocation-ranking score.

Internally this is called:

    Allocation Score

because the allocator needs one common ranking mechanism while
preserving the distinction between stock and ETF analytical models.

Reporting compatibility
------------------------
The existing Capital Allocation worksheet structure is preserved.

The existing:

    Investment Score

column remains in the output for compatibility with the report.

For ETFs, that column contains the ETF Score used for allocation.
The separate analytical ETF fields remain available upstream and
in the wider portfolio analysis.
"""

import os
import pandas as pd

from config.investment_config import (
    DISCRETIONARY_SPEND_LIMIT,
    MAX_NEW_BUYS,
    MAX_BUY_MORE,
)


# ============================================================
# Configuration
# ============================================================

HOLDINGS_FILE = "portfolio/holdings_raw.csv"

# Do not create a trade simply to release a trivial amount.
MIN_REDUCTION_VALUE = 5.00

# Minimum score required to become a buy candidate.
#
# For STOCKS:
#     Investment Score >= MIN_BUY_SCORE
#
# For ETFs:
#     ETF Score >= MIN_BUY_SCORE
#
# The score scales are both 0-100, but they remain separate
# analytical measures.
MIN_BUY_SCORE = 75

# Minimum conviction weight for a selected candidate.
MIN_CONVICTION_WEIGHT = 1.0




# ============================================================
# Helpers
# ============================================================

def safe_float(value, default=0.0):
    """
    Safely convert a value to float.

    Handles:
        - None
        - NaN
        - pandas Series
        - lists / tuples
        - invalid strings
    """

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
    """
    Normalise a ticker symbol.
    """

    if value is None:
        return ""

    return str(value).strip().upper()


def normalise_action(value):
    """
    Normalise an action such as BUY MORE, REDUCE 25%, etc.
    """

    if value is None:
        return "HOLD"

    return str(value).strip().upper()


def get_reduction_percentage(action):
    """
    Convert reduction action into percentage of existing
    position to release.

    Examples
    --------
    REDUCE 25% -> 0.25
    REDUCE 50% -> 0.50
    REDUCE 75% -> 0.75
    SELL       -> 1.00

    A bare REDUCE defaults to 25%.
    """

    action = normalise_action(action)

    if "25" in action:
        return 0.25

    if "50" in action:
        return 0.50

    if "75" in action:
        return 0.75

    if action in (
        "SELL",
        "SELL 100%",
        "REDUCE 100%",
        "REDUCE / SELL",
    ):
        return 1.00

    if action == "REDUCE":
        return 0.25

    return 0.0


# ============================================================
# ACTUAL HOLDINGS
# ============================================================

def load_actual_holdings():
    """
    Load actual ownership from holdings_raw.csv.

    Quantity > 0 means owned.

    Returns
    -------
    dict

        {
            "NVDA": {
                "owned": True,
                "quantity": 50,
                "market_value": 10000,
                "name": "NVIDIA"
            }
        }
    """

    if not os.path.exists(HOLDINGS_FILE):

        print(
            f"WARNING: {HOLDINGS_FILE} not found."
        )

        return {}

    try:

        holdings = pd.read_csv(
            HOLDINGS_FILE
        )

    except Exception as e:

        print(
            "Unable to read holdings file:",
            e
        )

        return {}

    required = [
        "Ticker",
        "Quantity",
        "Market Value",
    ]

    missing = [
        column
        for column in required
        if column not in holdings.columns
    ]

    if missing:

        print(
            "Holdings file missing columns:",
            missing
        )

        return {}

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

    ownership = {}

    for _, row in holdings.iterrows():

        ticker = clean_ticker(
            row["Ticker"]
        )

        if not ticker:
            continue

        quantity = safe_float(
            row["Quantity"]
        )

        market_value = safe_float(
            row["Market Value"]
        )

        ownership[ticker] = {

            "owned":
                quantity > 0,

            "quantity":
                quantity,

            "market_value":
                market_value,

            "name":
                row.get(
                    "Name",
                    ""
                ),
        }

    return ownership


# ============================================================
# ASSET TYPE
# ============================================================




def get_asset_type(ticker, row=None):
    """
    Return the asset classification supplied by upstream analysis.

    Defaults to STOCK if no valid classification is available.
    """

    if row is not None:

        asset_type = str(
            row.get(
                "Asset Type",
                row.get(
                    "Type",
                    ""
                )
            )
        ).strip().upper()

        if asset_type in {
            "ETF",
            "STOCK",
        }:
            return asset_type

        if asset_type == "EQUITY":
            return "STOCK"

    return "STOCK"

# ============================================================
# SCORE HELPERS
# ============================================================

def get_investment_score(row):
    """
    Return the STOCK Investment Score.

    This function deliberately does NOT fall back to ETF Score.

    It exists for stock-specific scoring and for backwards
    compatibility with existing callers.
    """

    return safe_float(
        row.get(
            "Investment Score",
            row.get(
                "investment_score",
                row.get(
                    "Score",
                    0
                )
            )
        )
    )


def get_etf_score(row):
    """
    Return the ETF-specific score.

    ETF Score is intentionally kept separate from stock
    Investment Score.
    """

    return safe_float(
        row.get(
            "ETF Score",
            row.get(
                "etf_score",
                0
            )
        )
    )


def get_allocation_score(row, ticker=None):
    """
    Return the score used by the capital allocator.

    STOCK
        Allocation Score = Investment Score

    ETF
        Allocation Score = ETF Score

    This is the key separation between analytical models.

    The allocator can therefore rank stocks and ETFs together
    without pretending they were scored using the same model.
    """

    if ticker is None:

        ticker = row.get(
            "Ticker",
            ""
        )

    asset_type = get_asset_type(
        ticker,
        row
    )

    if asset_type == "ETF":

        return get_etf_score(
            row
        )

    return get_investment_score(
        row
    )


def get_price(row):
    """
    Extract a usable price from an opportunity/decision row.
    """

    return safe_float(
        row.get(
            "Price",
            row.get(
                "Current Price",
                0
            )
        )
    )


def get_reason(row, default):
    """
    Extract a human-readable reason.
    """

    reason = row.get(
        "Reason",
        default
    )

    if reason is None:
        return default

    if isinstance(reason, list):

        return "; ".join(
            str(x)
            for x in reason
        )

    return str(reason)


def get_conviction_weight(score):
    """
    Convert allocation score into capital-allocation weight.

    Scores at the BUY threshold receive the minimum weight.

    Example:

        Score 76 -> weight 1
        Score 78 -> weight 3
        Score 85 -> weight 10
        Score 90 -> weight 15
        Score 94 -> weight 19

    Higher score therefore produces a larger allocation.

    The same weighting mechanism is used for:

        STOCK Investment Score
        ETF Score

    but the underlying scores remain analytically separate.
    """

    score = safe_float(
        score
    )

    excess_score = (
        score
        -
        MIN_BUY_SCORE
    )

    return max(
        MIN_CONVICTION_WEIGHT,
        excess_score
    )


def is_owned(
    ticker,
    ownership
):
    """
    Determine whether the portfolio actually owns the asset.
    """

    holding = ownership.get(
        clean_ticker(ticker)
    )

    if not holding:
        return False

    return bool(
        holding.get(
            "owned",
            False
        )
        and
        safe_float(
            holding.get(
                "quantity",
                0
            )
        ) > 0
    )


# ============================================================
# MAIN ALLOCATOR
# ============================================================

def generate_capital_allocation(
    portfolio_summary,
    opportunities=None,
    portfolio_decisions=None
):
    """
    Generate portfolio capital allocation.

    Parameters
    ----------
    portfolio_summary : pandas.DataFrame
        Existing portfolio positions.

    opportunities : pandas.DataFrame
        Potential BUY NEW / BUY MORE opportunities.

        STOCK opportunities should contain:
            Investment Score

        ETF opportunities should contain:
            ETF Score

    portfolio_decisions : list or pandas.DataFrame
        Explicit REDUCE / SELL / HOLD decisions.

    Returns
    -------
    dict

        {
            "Capital Allocation": allocation_df,
            "Capital Summary": summary
        }
    """

    if portfolio_summary is None:
        portfolio_summary = pd.DataFrame()

    if opportunities is None:
        opportunities = pd.DataFrame()

    # ========================================================
    # NORMALISE PORTFOLIO DECISIONS
    # ========================================================

    if portfolio_decisions is None:

        portfolio_decisions = []

    elif isinstance(
        portfolio_decisions,
        pd.DataFrame
    ):

        portfolio_decisions = (
            portfolio_decisions
            .to_dict("records")
        )

    elif not isinstance(
        portfolio_decisions,
        list
    ):

        portfolio_decisions = []

    # ========================================================
    # ACTUAL OWNERSHIP
    # ========================================================

    ownership = load_actual_holdings()

    allocations = []

    # ========================================================
    # REDUCTIONS
    # ========================================================

    reduction_candidates = []

    for row in portfolio_decisions:

        if not isinstance(
            row,
            dict
        ):
            continue

        ticker = clean_ticker(
            row.get(
                "Ticker",
                ""
            )
        )

        if not ticker:
            continue

        # CASH is never managed as an investment.
        if ticker == "CASH":
            continue

        action = normalise_action(
            row.get(
                "Action",
                "HOLD"
            )
        )

        reduction_percentage = (
            get_reduction_percentage(
                action
            )
        )

        if reduction_percentage <= 0:
            continue

        # ----------------------------------------------------
        # Verify actual ownership.
        #
        # A reduction decision against something that is not
        # actually owned must never create a trade.
        # ----------------------------------------------------

        holding = ownership.get(
            ticker
        )

        if not holding:
            continue

        if not holding.get(
            "owned",
            False
        ):
            continue

        quantity = safe_float(
            holding.get(
                "quantity",
                0
            )
        )

        market_value = safe_float(
            holding.get(
                "market_value",
                0
            )
        )

        if quantity <= 0:
            continue

        
        release_amount = round(
            market_value
            *
            reduction_percentage,
            2
        )

        # ----------------------------------------------------
        # If a reduction is economically insignificant,
        # sell the entire position instead.
        #
        # A small residual position has little portfolio value
        # and creates unnecessary complexity.
        # ----------------------------------------------------

        if release_amount < MIN_REDUCTION_VALUE:

            reduction_percentage = 1.0

            release_amount = round(
                market_value,
                2
            )

            reduction_action = "SELL"

        else:

            reduction_action = (
                "SELL"
                if reduction_percentage >= 1
                else
                f"REDUCE "
                f"{int(reduction_percentage * 100)}%"
            )

        price = get_price(
            row
        )

        if price <= 0:

            if (
                quantity > 0
                and
                market_value > 0
            ):

                price = round(
                    market_value / quantity,
                    2
                )

        if price <= 0:
            continue

        reduction_action = (
            "SELL"
            if reduction_percentage >= 1
            else
            f"REDUCE "
            f"{int(reduction_percentage * 100)}%"
        )

        allocation_score = get_allocation_score(
            row,
            ticker
        )

        reduction_candidates.append(
            {

                "Ticker":
                    ticker,

                "Action":
                    reduction_action,

                "Existing Holding":
                    "Yes",

                "Asset Type":
                    get_asset_type(
                        ticker,
                        row
                    ),

                "Price":
                    price,

                "Quantity":
                    quantity,

                "Reduction %":
                    round(
                        reduction_percentage * 100,
                        2
                    ),

                "Reduction Quantity":
                    round(
                        quantity
                        *
                        reduction_percentage,
                        6
                    ),

                "Market Value":
                    round(
                        market_value,
                        2
                    ),

                "Released Capital":
                    release_amount,

                "Buy Quantity":
                    0,

                "Buy Value":
                    0,

                "Amount":
                    -release_amount,

                "Funding Source":
                    "Released Capital",

                "Reason":
                    get_reason(
                        row,
                        "Portfolio reduction"
                    ),

                # ------------------------------------------------
                # Keep the existing report column.
                #
                # For ETFs this represents ETF Score for
                # allocation purposes.
                # ------------------------------------------------
                "Investment Score":
                    allocation_score,

                "Reduction Rank":
                    0,

                "Investment Rank":
                    0,

            }
        )

    # ========================================================
    # RANK REDUCTIONS
    #
    # Weakest allocation score first.
    # ========================================================

    reduction_candidates = sorted(
        reduction_candidates,
        key=lambda x: (
            x["Investment Score"],
            -x["Market Value"],
            x["Ticker"]
        )
    )

    for rank, item in enumerate(
        reduction_candidates,
        start=1
    ):

        item["Reduction Rank"] = rank

        allocations.append(
            item
        )

    # ========================================================
    # CAPITAL RELEASE
    # ========================================================

    released_capital = round(
        sum(
            item["Released Capital"]
            for item in reduction_candidates
        ),
        2
    )

    discretionary_capital = round(
        safe_float(
            DISCRETIONARY_SPEND_LIMIT
        ),
        2
    )

    total_available_capital = round(
        discretionary_capital
        +
        released_capital,
        2
    )

    # ========================================================
    # BUY CANDIDATES
    #
    # BUY NEW and BUY MORE are deliberately placed into the
    # same candidate pool.
    #
    # Ownership determines the action.
    #
    # Asset type determines which analytical score is used.
    #
    # Allocation Score determines priority.
    # ========================================================

    buy_candidates = {}

    if (
        isinstance(
            opportunities,
            pd.DataFrame
        )
        and
        not opportunities.empty
    ):

        for _, row in opportunities.iterrows():

            ticker = clean_ticker(
                row.get(
                    "Ticker",
                    ""
                )
            )

            if not ticker:
                continue

            # CASH is never an investment candidate.
            if ticker == "CASH":
                continue

            # ------------------------------------------------
            # Determine asset class.
            # ------------------------------------------------

            asset_type = get_asset_type(
                ticker,
                row
            )

            # ------------------------------------------------
            # Determine allocation score.
            #
            # STOCK -> Investment Score
            # ETF   -> ETF Score
            # ------------------------------------------------

            allocation_score = (
                get_allocation_score(
                    row,
                    ticker
                )
            )

            # ------------------------------------------------
            # Candidate must meet the relevant score threshold.
            # ------------------------------------------------

            if allocation_score < MIN_BUY_SCORE:
                continue

            owned = is_owned(
                ticker,
                ownership
            )

            if owned:

                action = "BUY MORE"
                existing_holding = "Yes"

                holding = ownership.get(
                    ticker,
                    {}
                )

                quantity = safe_float(
                    holding.get(
                        "quantity",
                        0
                    )
                )

                market_value = safe_float(
                    holding.get(
                        "market_value",
                        0
                    )
                )

            else:

                action = "BUY NEW"
                existing_holding = "No"

                quantity = 0.0
                market_value = 0.0

            price = get_price(
                row
            )

            # A candidate without a valid price cannot receive
            # an allocation.
            if price <= 0:
                continue

            candidate = {

                "Ticker":
                    ticker,

                "Action":
                    action,

                "Existing Holding":
                    existing_holding,

                "Asset Type":
                    asset_type,

                "Price":
                    price,

                "Quantity":
                    quantity,

                "Reduction %":
                    0,

                "Reduction Quantity":
                    0,

                "Market Value":
                    market_value,

                "Released Capital":
                    0,

                "Buy Quantity":
                    0,

                "Buy Value":
                    0,

                "Amount":
                    0,

                "Funding Source":
                    "Available Capital",

                "Reason":
                    get_reason(
                        row,
                        "High conviction opportunity"
                    ),

                "Reduction Rank":
                    0,

                "Investment Rank":
                    0,

                # ------------------------------------------------
                # Existing worksheet field.
                #
                # For stocks:
                #     Investment Score
                #
                # For ETFs:
                #     ETF Score
                #
                # The allocator uses this field as the common
                # allocation-ranking value while Asset Type
                # tells us which analytical model produced it.
                # ------------------------------------------------
                "Investment Score":
                    allocation_score,

                # Internal field used only before final output.
                "_Allocation Score":
                    allocation_score,
            }

            # ------------------------------------------------
            # Keep only the highest-scoring occurrence of each
            # ticker.
            # ------------------------------------------------

            existing_candidate = (
                buy_candidates.get(
                    ticker
                )
            )

            if (
                existing_candidate is None
                or
                allocation_score
                >
                existing_candidate[
                    "_Allocation Score"
                ]
            ):

                buy_candidates[ticker] = candidate

    # ========================================================
    # DO NOT REBUY A FULLY SOLD POSITION
    # ========================================================

    sold_tickers = {
        item["Ticker"]
        for item in reduction_candidates
        if item["Reduction %"] >= 100
    }

    buy_candidates = {
        ticker: candidate
        for ticker, candidate
        in buy_candidates.items()
        if ticker not in sold_tickers
    }

    # ========================================================
    # RANK ALL BUY OPPORTUNITIES TOGETHER
    #
    # Stocks and ETFs compete on Allocation Score.
    #
    # Stock:
    #     Allocation Score = Investment Score
    #
    # ETF:
    #     Allocation Score = ETF Score
    # ========================================================

    buy_candidates = sorted(
        buy_candidates.values(),
        key=lambda x: (
            -x["_Allocation Score"],
            x["Ticker"]
        )
    )

    # ========================================================
    # SELECT CANDIDATES
    #
    # There is NO BUY MORE-first rule.
    #
    # A BUY NEW with a higher allocation score can therefore
    # beat a BUY MORE.
    #
    # MAX_NEW_BUYS and MAX_BUY_MORE remain category safeguards.
    # ========================================================

    selected_candidates = []

    buy_more_count = 0
    buy_new_count = 0

    for candidate in buy_candidates:

        action = candidate[
            "Action"
        ]

        if action == "BUY MORE":

            if buy_more_count >= MAX_BUY_MORE:
                continue

        elif action == "BUY NEW":

            if buy_new_count >= MAX_NEW_BUYS:
                continue

        else:

            continue

        selected_candidates.append(
            candidate
        )

        if action == "BUY MORE":

            buy_more_count += 1

        else:

            buy_new_count += 1

    # ========================================================
    # FINAL RANKING
    # ========================================================

    selected_candidates = sorted(
        selected_candidates,
        key=lambda x: (
            -x["_Allocation Score"],
            x["Ticker"]
        )
    )

    # ========================================================
    # CONVICTION WEIGHTS
    # ========================================================

    total_conviction_weight = 0.0

    for candidate in selected_candidates:

        weight = get_conviction_weight(
            candidate[
                "_Allocation Score"
            ]
        )

        candidate[
            "_Conviction Weight"
        ] = weight

        total_conviction_weight += weight

    # ========================================================
    # CAPITAL ALLOCATION
    # ========================================================

    remaining = round(
        total_available_capital,
        2
    )

    capital_allocated = 0.0

    for rank, candidate in enumerate(
        selected_candidates,
        start=1
    ):

        if remaining <= 0:
            break

        if total_conviction_weight <= 0:
            continue

        allocation = round(
            total_available_capital
            *
            (
                candidate[
                    "_Conviction Weight"
                ]
                /
                total_conviction_weight
            ),
            2
        )

        allocation = min(
            allocation,
            remaining
        )

        if allocation <= 0:
            continue

        price = safe_float(
            candidate[
                "Price"
            ]
        )

        if price <= 0:
            continue

        buy_quantity = round(
            allocation / price,
            6
        )

        buy_value = round(
            buy_quantity * price,
            2
        )

        buy_value = min(
            buy_value,
            remaining
        )

        if buy_value <= 0:
            continue

        candidate[
            "Buy Quantity"
        ] = buy_quantity

        candidate[
            "Buy Value"
        ] = buy_value

        candidate[
            "Amount"
        ] = buy_value

        candidate[
            "Investment Rank"
        ] = rank

        allocations.append(
            candidate
        )

        remaining = round(
            remaining
            -
            buy_value,
            2
        )

        capital_allocated = round(
            capital_allocated
            +
            buy_value,
            2
        )

    # ========================================================
    # RESIDUAL CAPITAL
    #
    # Do not create another position simply to consume the
    # remaining cash.
    #
    # If a residual remains and there is already a selected BUY,
    # add the residual to the highest-conviction selected BUY.
    # ========================================================

    if (
        selected_candidates
        and
        remaining > 0
    ):

        valid_buy_allocations = [
            item
            for item in allocations
            if item["Action"]
            in (
                "BUY NEW",
                "BUY MORE"
            )
            and
            safe_float(
                item["Price"]
            ) > 0
        ]

        if valid_buy_allocations:

            top_candidate = sorted(
                valid_buy_allocations,
                key=lambda x: (
                    -x["_Allocation Score"],
                    x["Ticker"]
                )
            )[0]

            residual = round(
                remaining,
                2
            )

            price = safe_float(
                top_candidate[
                    "Price"
                ]
            )

            if price > 0:

                additional_quantity = round(
                    residual / price,
                    6
                )

                additional_value = round(
                    additional_quantity * price,
                    2
                )

                additional_value = min(
                    additional_value,
                    remaining
                )

                if additional_value > 0:

                    top_candidate[
                        "Buy Quantity"
                    ] = round(
                        safe_float(
                            top_candidate[
                                "Buy Quantity"
                            ]
                        )
                        +
                        additional_quantity,
                        6
                    )

                    top_candidate[
                        "Buy Value"
                    ] = round(
                        safe_float(
                            top_candidate[
                                "Buy Value"
                            ]
                        )
                        +
                        additional_value,
                        2
                    )

                    top_candidate[
                        "Amount"
                    ] = round(
                        safe_float(
                            top_candidate[
                                "Amount"
                            ]
                        )
                        +
                        additional_value,
                        2
                    )

                    capital_allocated = round(
                        capital_allocated
                        +
                        additional_value,
                        2
                    )

                    remaining = round(
                        remaining
                        -
                        additional_value,
                        2
                    )

    # ========================================================
    # REMOVE INTERNAL FIELDS
    # ========================================================

    for candidate in allocations:

        candidate.pop(
            "_Conviction Weight",
            None
        )

        candidate.pop(
            "_Allocation Score",
            None
        )

    # ========================================================
    # HOLD POSITIONS
    #
    # Every genuine holding not already represented by a
    # REDUCE, SELL, BUY MORE or BUY NEW action is retained as
    # HOLD.
    #
    # This protects existing positions from unnecessary turnover.
    # ========================================================

    if (
        isinstance(
            portfolio_summary,
            pd.DataFrame
        )
        and
        not portfolio_summary.empty
    ):

        for _, row in portfolio_summary.iterrows():

            ticker = clean_ticker(
                row.get(
                    "Ticker",
                    ""
                )
            )

            if not ticker:
                continue

            if ticker == "CASH":
                continue

            # ------------------------------------------------
            # Do not duplicate positions already represented
            # by a trade action.
            # ------------------------------------------------

            if any(
                item["Ticker"] == ticker
                for item in allocations
            ):

                continue

            asset_type = get_asset_type(
                ticker,
                row
            )

            allocation_score = (
                get_allocation_score(
                    row,
                    ticker
                )
            )

            if asset_type == "ETF":
           

                allocation_pct = safe_float(
                    row.get(
                        "Allocation %",
                        row.get(
                            "Allocation",
                            0
                        )
                    )
                )

                if allocation_pct > 10:

                    reason = (
                        f"ETF Score {allocation_score:.0f}/100 is very strong, "
                        f"but the existing ETF allocation is already "
                        f"{allocation_pct:.1f}% of the portfolio. "
                        f"HOLD to avoid increasing concentration."
                    )

                elif allocation_pct >= 2:

                    reason = (
                        f"ETF Score {allocation_score:.0f}/100 is strong, "
                        f"but the existing ETF position is already meaningful. "
                        f"HOLD rather than increase the allocation unnecessarily."
                    )

                else:

                    reason = (
                        f"ETF Score {allocation_score:.0f}/100 is strong, "
                        f"but the current position does not yet justify a "
                        f"portfolio change."
                    )

            else:

                reason = "Maintain existing position"

            allocations.append(
                {

                    "Ticker":
                        ticker,

                    "Action":
                        "HOLD",

                    "Existing Holding":
                        "Yes",

                    "Asset Type":
                        asset_type,

                    "Price":
                        safe_float(
                            row.get(
                                "Current Price",
                                row.get(
                                    "Price",
                                    0
                                )
                            )
                        ),

                    "Quantity":
                        safe_float(
                            row.get(
                                "Shares",
                                row.get(
                                    "Quantity",
                                    0
                                )
                            )
                        ),

                    "Reduction %":
                        0,

                    "Reduction Quantity":
                        0,

                    "Market Value":
                        safe_float(
                            row.get(
                                "Current Value",
                                row.get(
                                    "Market Value",
                                    0
                                )
                            )
                        ),

                    "Released Capital":
                        0,

                    "Buy Quantity":
                        0,

                    "Buy Value":
                        0,

                    "Amount":
                        0,

                    "Funding Source":
                        "",

                    "Reason":
                        reason,

                    "Reduction Rank":
                        0,

                    "Investment Rank":
                        0,

                    # ------------------------------------------------
                    # Compatibility field.
                    #
                    # STOCK:
                    #     Investment Score
                    #
                    # ETF:
                    #     ETF Score
                    # ------------------------------------------------
                    "Investment Score":
                        allocation_score,
                }
            )

    # ========================================================
    # DATAFRAME
    # ========================================================

    allocation_df = pd.DataFrame(
        allocations
    )

    # ========================================================
    # EXISTING CAPITAL ALLOCATION STRUCTURE
    #
    # DO NOT CHANGE THIS STRUCTURE.
    # ========================================================

    columns = [

        "Ticker",
        "Action",
        "Existing Holding",
        "Asset Type",
        "Price",
        "Quantity",
        "Reduction %",
        "Reduction Quantity",
        "Market Value",
        "Released Capital",
        "Buy Quantity",
        "Buy Value",
        "Amount",
        "Funding Source",
        "Reason",
        "Reduction Rank",
        "Investment Rank",
        "Investment Score",

    ]

    if allocation_df.empty:

        allocation_df = pd.DataFrame(
            columns=columns
        )

    else:

        for column in columns:

            if column not in allocation_df.columns:

                allocation_df[
                    column
                ] = 0

        allocation_df = allocation_df[
            columns
        ]

        numeric_columns = [

            "Price",
            "Quantity",
            "Reduction %",
            "Reduction Quantity",
            "Market Value",
            "Released Capital",
            "Buy Quantity",
            "Buy Value",
            "Amount",
            "Reduction Rank",
            "Investment Rank",
            "Investment Score",

        ]

        for column in numeric_columns:

            allocation_df[
                column
            ] = pd.to_numeric(
                allocation_df[
                    column
                ],
                errors="coerce"
            ).fillna(0)

    # ========================================================
    # CAPITAL SUMMARY
    #
    # Calculate everything from the final allocation dataframe.
    #
    # This ensures the summary and worksheet cannot disagree.
    # ========================================================

    discretionary_capital = round(
        safe_float(
            DISCRETIONARY_SPEND_LIMIT
        ),
        2
    )

    # ========================================================
    # RELEASED CAPITAL
    # ========================================================

    reduction_mask = (
        allocation_df[
            "Action"
        ]
        .astype(str)
        .str.startswith(
            "REDUCE"
        )
        |
        allocation_df[
            "Action"
        ].isin(
            [
                "SELL"
            ]
        )
    )

    released_capital = round(
        pd.to_numeric(
            allocation_df.loc[
                reduction_mask,
                "Released Capital"
            ],
            errors="coerce"
        )
        .fillna(0)
        .sum(),
        2
    )

    # ========================================================
    # TOTAL CAPITAL AVAILABLE
    # ========================================================

    total_available_capital = round(
        discretionary_capital
        +
        released_capital,
        2
    )

    # ========================================================
    # ACTUAL CAPITAL ALLOCATED
    # ========================================================

    buy_mask = allocation_df[
        "Action"
    ].isin(
        [
            "BUY NEW",
            "BUY MORE"
        ]
    )

    capital_allocated = round(
        pd.to_numeric(
            allocation_df.loc[
                buy_mask,
                "Buy Value"
            ],
            errors="coerce"
        )
        .fillna(0)
        .sum(),
        2
    )

    # ========================================================
    # REMAINING CAPITAL
    # ========================================================

    remaining = round(
        total_available_capital
        -
        capital_allocated,
        2
    )

    if abs(remaining) < 0.01:
        remaining = 0.00

    remaining = max(
        0.00,
        remaining
    )

    # ========================================================
    # COUNTS
    # ========================================================

    buy_new_count = int(
        (
            allocation_df[
                "Action"
            ]
            ==
            "BUY NEW"
        ).sum()
    )

    buy_more_count = int(
        (
            allocation_df[
                "Action"
            ]
            ==
            "BUY MORE"
        ).sum()
    )

    reduce_sell_count = int(
        allocation_df[
            "Action"
        ].isin(
            [
                "SELL",
                "REDUCE",
                "REDUCE 25%",
                "REDUCE 50%",
                "REDUCE 75%",
                "REDUCE 100%",
            ]
        ).sum()
    )

    hold_count = int(
        (
            allocation_df[
                "Action"
            ]
            ==
            "HOLD"
        ).sum()
    )

    total_buy_opportunities = (
        buy_new_count
        +
        buy_more_count
    )

    # ========================================================
    # CAPITAL SUMMARY DATAFRAME
    # ========================================================

    summary = pd.DataFrame(
        [

            {
                "Metric":
                    "Discretionary Spend Limit",

                "Amount":
                    discretionary_capital,
            },

            {
                "Metric":
                    "Capital Released From Sales",

                "Amount":
                    released_capital,
            },

            {
                "Metric":
                    "Total Available Capital",

                "Amount":
                    total_available_capital,
            },

            {
                "Metric":
                    "Capital Allocated",

                "Amount":
                    capital_allocated,
            },

            {
                "Metric":
                    "Remaining Capital",

                "Amount":
                    remaining,
            },

            {
                "Metric":
                    "BUY NEW Count",

                "Amount":
                    buy_new_count,
            },

            {
                "Metric":
                    "BUY MORE Count",

                "Amount":
                    buy_more_count,
            },

            {
                "Metric":
                    "REDUCE / SELL Count",

                "Amount":
                    reduce_sell_count,
            },

            {
                "Metric":
                    "HOLD Count",

                "Amount":
                    hold_count,
            },

            {
                "Metric":
                    "Total BUY Opportunities",

                "Amount":
                    total_buy_opportunities,
            },

        ]
    )

    # ========================================================
    # RETURN
    #
    # These exact keys are required by the existing report.
    # ========================================================

    return {

        "Capital Allocation":
            allocation_df,

        "Capital Summary":
            summary,

    }