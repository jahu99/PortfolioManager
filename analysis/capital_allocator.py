"""
Capital Allocation Engine

Purpose
-------
Manage portfolio capital allocation using:

    1. Actual portfolio ownership from holdings_raw.csv
    2. Portfolio reduction decisions
    3. Scanner investment opportunities

Core principles
---------------
- Actual ownership is determined by holdings_raw.csv.
- Quantity > 0 means the asset is owned.
- CASH is never an investment candidate.
- ETFs are valid investment assets.
- BUY MORE and BUY NEW compete on Investment Score.
- There is NO artificial BUY MORE-first rule.
- Capital is allocated to the highest-ranked opportunities.
- Capital released from reductions is calculated from:
      Market Value × Reduction %
- Small/economically insignificant reductions are suppressed.
- HOLD is preferred unless there is a meaningful reason to act.
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

# Minimum investment score for a BUY candidate.
MIN_BUY_SCORE = 75


# ============================================================
# Helpers
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


def get_reduction_percentage(action):

    """
    Convert reduction action into percentage of existing
    position to release.

    REDUCE 25% -> 0.25
    REDUCE 50% -> 0.50
    REDUCE 75% -> 0.75
    SELL       -> 1.00
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
                "quantity": ...,
                "market_value": ...,
                "name": ...
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
        c for c in required
        if c not in holdings.columns
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

        ownership[ticker] = {
            "owned":
                safe_float(
                    row["Quantity"]
                ) > 0,

            "quantity":
                safe_float(
                    row["Quantity"]
                ),

            "market_value":
                safe_float(
                    row["Market Value"]
                ),

            "name":
                row.get(
                    "Name",
                    ""
                ),
        }

    return ownership


def get_investment_score(row):

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


def get_price(row):

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


# ============================================================
# Main allocator
# ============================================================

def generate_capital_allocation(
    portfolio_summary,
    opportunities=None,
    portfolio_decisions=None
):

    if portfolio_summary is None:
        portfolio_summary = pd.DataFrame()

    if opportunities is None:
        opportunities = pd.DataFrame()

    # ========================================================
    # NORMALISE PORTFOLIO DECISIONS
    #
    # generate_portfolio_decisions() returns a DataFrame.
    # The capital allocator internally expects a list of
    # dictionaries.
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

    # --------------------------------------------------------
    # Actual ownership
    # --------------------------------------------------------

    ownership = load_actual_holdings()

    allocations = []

    # ========================================================
    # REDUCTIONS
    # ========================================================

    reduction_candidates = []

    if portfolio_decisions:

        for row in portfolio_decisions:

            ticker = clean_ticker(
                row.get(
                    "Ticker",
                    ""
                )
            )

            if not ticker:
                continue

            # CASH is never reduced by the investment allocator.
            if ticker == "CASH":
                continue

            # ETFs are HOLD-only until we have a dedicated
            # ETF investment model.
            if is_etf(ticker, row):
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

            # ------------------------------------------------
            # Verify actual ownership
            # ------------------------------------------------

            holding = ownership.get(
                ticker
            )

            if not holding:
                continue

            if not holding["owned"]:
                continue

            quantity = safe_float(
                holding["quantity"]
            )

            market_value = safe_float(
                holding["market_value"]
            )

            if quantity <= 0:
                continue

            # ------------------------------------------------
            # Calculate actual released capital
            # ------------------------------------------------

            release_amount = round(
                market_value
                *
                reduction_percentage,
                2
            )

            # ------------------------------------------------
            # Ignore economically insignificant reductions
            # ------------------------------------------------

            if (
                release_amount
                <
                MIN_REDUCTION_VALUE
            ):

                continue

            reduction_candidates.append(
                {
                    "Ticker":
                        ticker,

                    "Action":
                        (
                            "SELL"
                            if reduction_percentage >= 1
                            else
                            f"REDUCE "
                            f"{int(reduction_percentage * 100)}%"
                        ),

                    "Existing Holding":
                        "Yes",

                    "Asset Type":
                        "ETF"
                        if (
                            ticker in {
                                "IWDA",
                                "VUAA",
                                "SEC0",
                            }
                        )
                        else "STOCK",

                    "Price":
                        get_price(row)
                        if get_price(row) > 0
                        else (
                            round(
                                market_value / quantity,
                                2
                            )
                            if quantity > 0 and market_value > 0
                            else 0
                        ),

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

                    "Investment Score":
                        get_investment_score(
                            row
                        ),
                }
            )

    # --------------------------------------------------------
    # Rank reductions by weakest investment score first.
    # --------------------------------------------------------

    reduction_candidates = sorted(
        reduction_candidates,
        key=lambda x: (
            x["Investment Score"],
            -x["Market Value"]
        )
    )

    for rank, item in enumerate(
        reduction_candidates,
        start=1
    ):

        item["Reduction Rank"] = rank
        item["Investment Rank"] = 0

        allocations.append(
            item
        )

    # ========================================================
    # CAPITAL RELEASE
    # ========================================================

    released_capital = round(
        sum(
            x["Released Capital"]
            for x in reduction_candidates
        ),
        2
    )

    # Explicit numeric conversion preserves the existing
    # configuration interface while avoiding unexpected
    # zero/default behaviour.
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
    # IMPORTANT:
    # BUY MORE and BUY NEW are deliberately combined.
    #
    # Ownership is determined from holdings_raw.csv.
    # Investment Score determines priority.
    # ========================================================

    buy_candidates = {}

    if not opportunities.empty:

        for _, row in opportunities.iterrows():

            ticker = clean_ticker(
                row.get(
                    "Ticker",
                    ""
                )
            )

            if not ticker:
                continue

            # CASH cannot be bought.
            if ticker == "CASH":
                continue

            score = get_investment_score(
                row
            )

            if score < MIN_BUY_SCORE:
                continue

            holding = ownership.get(
                ticker
            )

            owned = bool(
                holding
                and
                holding["owned"]
                and
                holding["quantity"] > 0
            )

            if owned:

                action = "BUY MORE"
                existing_holding = "Yes"

                quantity = safe_float(
                    holding["quantity"]
                )

                market_value = safe_float(
                    holding["market_value"]
                )

            else:

                action = "BUY NEW"
                existing_holding = "No"

                quantity = 0.0
                market_value = 0.0

            # ------------------------------------------------
            # Keep highest-scoring occurrence of each ticker.
            # ------------------------------------------------

            candidate = {

                "Ticker":
                    ticker,

                "Action":
                    action,

                "Existing Holding":
                    existing_holding,

                "Asset Type":
                    "ETF"
                    if (
                        ticker in {
                            "IWDA",
                            "VUAA",
                            "SEC0",
                        }
                    )
                    else "STOCK",

                "Price":
                    get_price(row),

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

                "Investment Score":
                    score,
            }

            if (
                ticker not in buy_candidates
                or
                score
                >
                buy_candidates[ticker][
                    "Investment Score"
                ]
            ):

                buy_candidates[ticker] = candidate

    # ========================================================
    # Remove BUY candidates that are simultaneously being
    # completely sold.
    # ========================================================

    sold_tickers = {
        x["Ticker"]
        for x in reduction_candidates
        if x["Reduction %"] >= 100
    }

    buy_candidates = {
        ticker: candidate
        for ticker, candidate
        in buy_candidates.items()
        if ticker not in sold_tickers
    }

    # ========================================================
    # RANK ALL BUY OPPORTUNITIES TOGETHER
    # ========================================================

    buy_candidates = sorted(
        buy_candidates.values(),
        key=lambda x: (
            -x["Investment Score"],
            x["Ticker"]
        )
    )

    # --------------------------------------------------------
    # Apply maximum counts by category.
    #
    # We first rank ALL opportunities.
    # We then permit the configured maximum number of
    # BUY MORE and BUY NEW positions.
    #
    # There is still NO category priority.
    # --------------------------------------------------------

    selected_candidates = []

    buy_more_count = 0
    buy_new_count = 0

    for candidate in buy_candidates:

        if (
            candidate["Action"]
            ==
            "BUY MORE"
        ):

            if buy_more_count >= MAX_BUY_MORE:
                continue

            buy_more_count += 1

        else:

            if buy_new_count >= MAX_NEW_BUYS:
                continue

            buy_new_count += 1

        selected_candidates.append(
            candidate
        )

    # ========================================================
    # Re-rank after configured limits
    # ========================================================

    selected_candidates = sorted(
        selected_candidates,
        key=lambda x: (
            -x["Investment Score"],
            x["Ticker"]
        )
    )

    # ========================================================
    # ALLOCATE CAPITAL
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

        # ----------------------------------------------------
        # Equal allocation among selected candidates for now.
        #
        # The ranking determines who gets capital.
        # We can later introduce conviction-weighted
        # allocation without changing ownership logic.
        # ----------------------------------------------------

        positions_remaining = (
            len(selected_candidates)
            -
            rank
            +
            1
        )

        allocation = round(
            remaining
            /
            positions_remaining,
            2
        )

        if allocation <= 0:
            continue

        price = safe_float(
            candidate["Price"]
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

        # Protect against rounding causing us to overspend.
        buy_value = min(
            buy_value,
            remaining
        )

        allocation = buy_value

        candidate["Buy Quantity"] = (
            buy_quantity
        )

        candidate["Buy Value"] = (
            buy_value
        )

        candidate["Amount"] = (
            buy_value
        )

        candidate["Investment Rank"] = (
            rank
        )

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
    # HOLD POSITIONS
    # ========================================================

    if (
        portfolio_summary is not None
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

            # Don't duplicate a holding already represented
            # by a reduction or buy.
            if any(
                x["Ticker"] == ticker
                for x in allocations
            ):
                continue

            allocations.append(
                {
                    "Ticker":
                        ticker,

                    "Action":
                        "HOLD",

                    "Existing Holding":
                        "Yes",

                    "Asset Type":
                        row.get(
                            "Type",
                            "STOCK"
                        ),

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
                                0
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
                        "Maintain existing position",

                    "Reduction Rank":
                        0,

                    "Investment Rank":
                        0,

                    "Investment Score":
                        safe_float(
                            row.get(
                                "Investment Score",
                                0
                            )
                        ),
                }
            )

    # ========================================================
    # DATAFRAME
    # ========================================================

    allocation_df = pd.DataFrame(
        allocations
    )

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
                allocation_df[column] = 0

        allocation_df = allocation_df[
            columns
        ]

        # Numeric fields
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

            allocation_df[column] = pd.to_numeric(
                allocation_df[column],
                errors="coerce"
            ).fillna(0)

    # ========================================================
    # SUMMARY
    #
    # IMPORTANT:
    # The summary is deliberately calculated from the FINAL
    # allocation dataframe.
    #
    # This keeps the summary and the Capital Allocation
    # worksheet completely consistent.
    # ========================================================

    # --------------------------------------------------------
    # Discretionary capital
    # --------------------------------------------------------

    discretionary_capital = round(
        safe_float(
            DISCRETIONARY_SPEND_LIMIT
        ),
        2
    )

    # --------------------------------------------------------
    # Capital released from actual reduction/sell actions
    # --------------------------------------------------------

    reduction_mask = (
        allocation_df["Action"]
        .astype(str)
        .str.startswith("REDUCE")
        |
        allocation_df["Action"].isin(
            ["SELL"]
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

    # --------------------------------------------------------
    # Total available capital
    # --------------------------------------------------------

    total_available_capital = round(
        discretionary_capital
        +
        released_capital,
        2
    )

    # --------------------------------------------------------
    # Capital actually allocated to BUY NEW / BUY MORE
    # --------------------------------------------------------

    buy_mask = allocation_df["Action"].isin(
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

    # --------------------------------------------------------
    # Remaining capital
    # --------------------------------------------------------

    remaining = round(
        total_available_capital
        -
        capital_allocated,
        2
    )

    # Protect against tiny floating-point residuals.
    if abs(remaining) < 0.01:
        remaining = 0.00

    # Never report negative remaining capital.
    remaining = max(
        0.00,
        remaining
    )

    # ========================================================
    # COUNTS
    # ========================================================

    buy_new_count = int(
        (
            allocation_df["Action"]
            ==
            "BUY NEW"
        ).sum()
    )

    buy_more_count = int(
        (
            allocation_df["Action"]
            ==
            "BUY MORE"
        ).sum()
    )

    reduce_sell_count = int(
        allocation_df["Action"].isin(
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
            allocation_df["Action"]
            ==
            "HOLD"
        ).sum()
    )

    reduction_count = reduce_sell_count

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
                    "Reduction Actions",

                "Amount":
                    reduction_count,
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
    # IMPORTANT:
    # Keep these exact dictionary keys because downstream
    # reports/excel_report.py expects them.
    # ========================================================

    return {
        "Capital Allocation":
            allocation_df,

        "Capital Summary":
            summary,
    }

def is_etf(ticker, row=None):
    """
    Determine whether an asset is an ETF.

    This is deliberately conservative. We only classify assets
    as ETFs when we have explicit evidence.

    Known portfolio ETFs:
        IWDA
        VUAA
        SEC0

    We also recognise explicit ETF/Exchange Traded Fund asset
    type information when supplied by the upstream data.
    """

    ticker = clean_ticker(ticker)

    known_etfs = {
        "IWDA",
        "VUAA",
        "SEC0",
    }

    if ticker in known_etfs:
        return True

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
            "EXCHANGE TRADED FUND",
            "EXCHANGE-TRADED FUND",
        }:
            return True

    return False