import pandas as pd


# ============================================================
# Helpers
# ============================================================

def safe_float(value, default=0.0):

    try:

        if value is None:
            return default

        if pd.isna(value):
            return default

        return float(value)

    except Exception:

        return default


def clean_ticker(value):

    if value is None:
        return ""

    if pd.isna(value):
        return ""

    return str(value).strip().upper()


def normalise_text(value, default=""):

    if value is None:
        return default

    if pd.isna(value):
        return default

    value = str(value).strip()

    if not value:
        return default

    return value.upper()


def get_value(row, *columns, default=None):

    for column in columns:

        if column in row.index:

            value = row.get(column)

            if value is not None:

                try:

                    if not pd.isna(value):
                        return value

                except Exception:

                    return value

    return default


# ============================================================
# EXISTING HOLDING DECISION
# ============================================================

def evaluate_existing_holding(holding):

    ticker = clean_ticker(
        holding.get(
            "Ticker",
            ""
        )
    )

    score = safe_float(
        get_value(
            holding,
            "Investment Score",
            "Momentum Score",
            "Score",
            default=0
        )
    )

    quality_score = safe_float(
        get_value(
            holding,
            "Quality Score",
            default=0
        )
    )

    growth_score = safe_float(
        get_value(
            holding,
            "Growth Score",
            default=0
        )
    )

    signal = normalise_text(
        get_value(
            holding,
            "Signal",
            "Momentum Signal",
            default=""
        )
    )

    allocation = safe_float(
        get_value(
            holding,
            "Allocation %",
            default=0
        )
    )

    sector = get_value(
        holding,
        "Sector",
        default="Unknown"
    )

    # --------------------------------------------------------
    # Default position
    #
    # Existing holdings are protected.
    # A stock does NOT get reduced simply because it has
    # fallen below the BUY threshold.
    # --------------------------------------------------------

    action = "HOLD"

    reasons = []

    # --------------------------------------------------------
    # Strong holding
    # --------------------------------------------------------

    if score >= 85:

        reasons.append(
            "High investment score supports continued ownership"
        )

    # --------------------------------------------------------
    # Reasonable holding
    # --------------------------------------------------------

    elif score >= 60:

        reasons.append(
            "Investment score remains sufficient to retain the position"
        )

    # --------------------------------------------------------
    # Weak holding
    #
    # Weak score alone does NOT trigger a reduction.
    # --------------------------------------------------------

    else:

        reasons.append(
            "Low investment score requires monitoring"
        )

        weak_quality = (
            quality_score > 0
            and
            quality_score < 50
        )

        weak_growth = (
            growth_score > 0
            and
            growth_score < 40
        )

        bearish_signal = signal in {
            "SELL",
            "STRONG SELL"
        }

        # ----------------------------------------------------
        # Only recommend REDUCE when multiple independent
        # deterioration signals are present.
        # ----------------------------------------------------

        if (
            weak_quality
            and
            weak_growth
            and
            bearish_signal
        ):

            action = "REDUCE"

            reasons = [
                "Low investment score",
                "Weak quality",
                "Weak growth",
                "Bearish technical signal"
            ]

        else:

            action = "HOLD"

            reasons.append(
                "Insufficient evidence to justify reducing an existing holding"
            )

    # --------------------------------------------------------
    # Concentration
    #
    # Concentration is a reason for review, not automatically
    # a sell instruction.
    # --------------------------------------------------------

    if allocation > 40:

        if action == "HOLD":

            action = "REVIEW"

        reasons.append(
            "High portfolio concentration"
        )

    elif allocation > 25:

        reasons.append(
            "Large position but not sufficiently concentrated to require reduction"
        )

    # --------------------------------------------------------
    # Deduplicate reasons
    # --------------------------------------------------------

    reasons = list(
        dict.fromkeys(
            reasons
        )
    )

    return {
        "Action":
            action,

        "Ticker":
            ticker,

        "Sector":
            sector,

        "Investment Score":
            score,

        "Quality Score":
            quality_score,

        "Growth Score":
            growth_score,

        "Signal":
            signal,

        "Allocation %":
            allocation,

        "Reason":
            "; ".join(
                reasons
            )
    }


# ============================================================
# REBALANCE DECISION NORMALISATION
# ============================================================

def normalise_rebalance_decision(item):

    ticker = clean_ticker(
        item.get(
            "Ticker",
            ""
        )
    )

    if not ticker:
        return None

    action = normalise_text(
        item.get(
            "Action",
            "HOLD"
        ),
        "HOLD"
    )

    sector = item.get(
        "Sector",
        "Unknown"
    )

    investment_score = safe_float(
        item.get(
            "Investment Score",
            0
        )
    )

    allocation = safe_float(
        item.get(
            "Allocation %",
            0
        )
    )

    quality_score = safe_float(
        item.get(
            "Quality Score",
            0
        )
    )

    growth_score = safe_float(
        item.get(
            "Growth Score",
            0
        )
    )

    signal = normalise_text(
        item.get(
            "Signal",
            ""
        )
    )

    reason = item.get(
        "Reason",
        ""
    )

    if reason is None:

        reason = ""

    return {
        "Action":
            action,

        "Ticker":
            ticker,

        "Sector":
            sector,

        "Investment Score":
            investment_score,

        "Quality Score":
            quality_score,

        "Growth Score":
            growth_score,

        "Signal":
            signal,

        "Allocation %":
            allocation,

        "Reason":
            str(reason)
    }


# ============================================================
# DECISION PRIORITY
# ============================================================

def get_action_priority(action):

    action = normalise_text(
        action,
        "HOLD"
    )

    priorities = {

        "SELL": 1,

        "REDUCE": 1,

        "REDUCE 75%": 1,

        "REDUCE 50%": 1,

        "REDUCE 25%": 1,

        "REVIEW": 2,

        "BUY NEW": 3,

        "BUY MORE": 3,

        "BUY": 3,

        "ADD": 3,

        "WATCH": 4,

        "HOLD": 5,

        "HOLD / ADD": 5
    }

    return priorities.get(
        action,
        99
    )


# ============================================================
# MAIN DECISION ENGINE
# ============================================================

def generate_decisions(
    portfolio_summary,
    stock_results,
    rebalance_recommendations
):

    decisions = []

    # ========================================================
    # EXISTING HOLDINGS
    # ========================================================

    if (
        isinstance(
            portfolio_summary,
            pd.DataFrame
        )
        and
        not portfolio_summary.empty
    ):

        for _, holding in portfolio_summary.iterrows():

            decision = evaluate_existing_holding(
                holding
            )

            ticker = decision.get(
                "Ticker",
                ""
            )

            if not ticker:
                continue

            decisions.append(
                decision
            )

    # ========================================================
    # REBALANCE RECOMMENDATIONS
    # ========================================================

    if (
        isinstance(
            rebalance_recommendations,
            pd.DataFrame
        )
        and
        not rebalance_recommendations.empty
    ):

        for _, item in rebalance_recommendations.iterrows():

            decision = normalise_rebalance_decision(
                item
            )

            if decision is None:
                continue

            decisions.append(
                decision
            )

    # ========================================================
    # RESULT DATAFRAME
    # ========================================================

    if not decisions:

        return pd.DataFrame(
            columns=[
                "Action",
                "Ticker",
                "Sector",
                "Investment Score",
                "Quality Score",
                "Growth Score",
                "Signal",
                "Allocation %",
                "Reason"
            ]
        )

    result = pd.DataFrame(
        decisions
    )

    # ========================================================
    # CLEAN TICKERS
    # ========================================================

    if "Ticker" in result.columns:

        result["Ticker"] = (
            result["Ticker"]
            .apply(clean_ticker)
        )

        result = result[
            result["Ticker"] != ""
        ]

    # ========================================================
    # NORMALISE ACTIONS
    # ========================================================

    if "Action" in result.columns:

        result["Action"] = (
            result["Action"]
            .apply(
                lambda x:
                    normalise_text(
                        x,
                        "HOLD"
                    )
            )
        )

    # ========================================================
    # NUMERIC NORMALISATION
    # ========================================================

    numeric_columns = [
        "Investment Score",
        "Quality Score",
        "Growth Score",
        "Allocation %"
    ]

    for column in numeric_columns:

        if column in result.columns:

            result[column] = pd.to_numeric(
                result[column],
                errors="coerce"
            ).fillna(0)

    # ========================================================
    # CONSOLIDATE DUPLICATE TICKERS
    #
    # If multiple parts of the system produce a decision for
    # the same ticker, the strongest action takes precedence.
    #
    # SELL / REDUCE
    #     ↓
    # REVIEW
    #     ↓
    # BUY
    #     ↓
    # WATCH
    #     ↓
    # HOLD
    # ========================================================

    result["Decision Priority"] = (
        result["Action"]
        .apply(
            get_action_priority
        )
    )

    result = (
        result
        .sort_values(
            [
                "Ticker",
                "Decision Priority"
            ],
            ascending=[
                True,
                True
            ]
        )
        .drop_duplicates(
            subset=[
                "Ticker"
            ],
            keep="first"
        )
    )

    # ========================================================
    # FINAL RANKING
    # ========================================================

    result["Priority"] = (
        result["Action"]
        .apply(
            get_action_priority
        )
    )

    result = (
        result
        .sort_values(
            [
                "Priority",
                "Investment Score",
                "Ticker"
            ],
            ascending=[
                True,
                False,
                True
            ]
        )
    )

    # ========================================================
    # REMOVE INTERNAL COLUMNS
    # ========================================================

    result = result.drop(
        columns=[
            "Priority",
            "Decision Priority"
        ],
        errors="ignore"
    )

    # ========================================================
    # STANDARD COLUMN ORDER
    # ========================================================

    columns = [
        "Action",
        "Ticker",
        "Sector",
        "Investment Score",
        "Quality Score",
        "Growth Score",
        "Signal",
        "Allocation %",
        "Reason"
    ]

    existing_columns = [
        column
        for column in columns
        if column in result.columns
    ]

    remaining_columns = [
        column
        for column in result.columns
        if column not in existing_columns
    ]

    result = result[
        existing_columns
        +
        remaining_columns
    ]

    # ========================================================
    # RESET INDEX
    # ========================================================

    result = result.reset_index(
        drop=True
    )

    return result