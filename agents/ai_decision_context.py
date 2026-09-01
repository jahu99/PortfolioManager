"""
AI Decision Context Builder

Purpose
-------
Build the structured, portfolio-aware context supplied to the governed
AI Decision Layer.

Architecture
------------

    Existing analytical engines
            |
            v
    Rules-based decisions
            |
            v
    Recommendation Intelligence
            |
            v
    AI Decision Context
            |
            v
    AI Decision Scoring
            |
            v
    AI Decision Layer
            |
            v
    AI Decision Explanation
            |
            v
    Portfolio / Capital Allocation

This module is a DATA CONTRACT.

It does not:

    - calculate investment scores
    - recalculate technical indicators
    - make BUY / HOLD / REDUCE / SELL decisions
    - allocate capital
    - change scoring weights
    - execute trades

It collects and normalises evidence produced by the existing engines
so that the AI decision layer can assess the proposed decision.

Important design principles
---------------------------
1. Existing analytical engines remain authoritative.
2. Existing rules-based decisions remain explicit inputs.
3. Historical recommendation intelligence remains explicit evidence.
4. Stocks and ETFs remain separate asset classes.
5. Existing holdings are explicitly identified.
6. Portfolio concentration is exposed as evidence.
7. Available capital and released capital are exposed as evidence.
8. Missing evidence is represented as missing evidence.
9. No evidence is invented.
10. The AI layer is responsible for the final governed decision.
11. HOLD remains the default downstream decision.
12. The context must be serialisable and independent of pandas objects.
13. Recommendation evidence snapshots are preferred when available.
14. Historical/legacy candidates fall back to their existing fields.
"""

from __future__ import annotations

from typing import Any

import math

import pandas as pd

from data.database import (
    get_recommendation_evidence,
)


# ============================================================
# Constants
# ============================================================

VALID_ASSET_TYPES = {
    "STOCK",
    "ETF",
}

VALID_ACTIONS = {
    "BUY NEW",
    "BUY MORE",
    "HOLD",
    "REDUCE",
    "REDUCE 25%",
    "REDUCE 50%",
    "REDUCE 75%",
    "REDUCE 100%",
    "SELL",
    "REVIEW",
}


# ============================================================
# Generic helpers
# ============================================================

def safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    """
    Safely convert a scalar value to float.

    Prevents pandas Series/DataFrames, lists and invalid values from
    leaking into the AI decision context.
    """

    try:

        if value is None:
            return default

        if isinstance(
            value,
            bool,
        ):

            return float(value)

        if isinstance(
            value,
            (list, tuple, set, dict),
        ):

            return default

        if isinstance(
            value,
            pd.Series,
        ):

            if value.empty:
                return default

            value = value.iloc[0]

        if isinstance(
            value,
            pd.DataFrame,
        ):

            if value.empty:
                return default

            value = value.iloc[0, 0]

        value = float(value)

        if not math.isfinite(value):
            return default

        return value

    except (
        TypeError,
        ValueError,
    ):

        return default


def clean_text(
    value: Any,
    default: str = "",
) -> str:
    """
    Safely convert a value to clean text.
    """

    if value is None:
        return default

    try:

        if pd.isna(value):
            return default

    except Exception:
        pass

    try:

        value = str(
            value
        ).strip()

    except Exception:

        return default

    if not value:
        return default

    return value



# ============================================================
# Semantic / Ontology Layer
# ============================================================
#
# Purpose:
#
# Convert raw decision evidence into explicit, deterministic
# semantic relationships before the context is supplied to
# the LLM reviewer.
#
# This layer:
#
#   - DOES NOT change deterministic decisions
#   - DOES NOT change proposed actions
#   - DOES NOT calculate new market data
#   - DOES NOT invent missing evidence
#   - DOES NOT make the final portfolio decision
#
# It explains what existing fields mean and how they relate.
#
# The LLM should reason FROM these relationships rather than
# having to infer the application's data model itself.
# ============================================================


SEMANTIC_ACTION_ORDER = {
    "BUY NEW": 1,
    "BUY MORE": 1,
    "HOLD": 0,
    "REDUCE": -1,
    "REDUCE 25%": -1,
    "REDUCE 50%": -1,
    "REDUCE 75%": -1,
    "REDUCE 100%": -1,
    "SELL": -1,
}


def _normalise_action(value):
    """
    Return a canonical action string.

    Missing or invalid values remain None rather than being
    converted into a synthetic action.
    """

    value = clean_text(value, default="")

    if not value:
        return None

    value = value.upper().strip()

    if value in VALID_ACTIONS:
        return value

    return None


def _semantic_number(value):
    """
    Convert a value to a finite float for semantic interpretation.

    Missing or invalid values return None.

    This deliberately preserves absence of evidence.
    """

    return safe_float(value, default=None)


def _action_direction(action):
    """
    Return the semantic direction of an action.

    BUY NEW / BUY MORE -> BUY
    HOLD -> HOLD
    REDUCE / SELL -> REDUCE
    """

    action = _normalise_action(action)

    if action is None:
        return None

    if action in {"BUY NEW", "BUY MORE"}:
        return "BUY"

    if action == "HOLD":
        return "HOLD"

    if action in {
        "REDUCE",
        "REDUCE 25%",
        "REDUCE 50%",
        "REDUCE 75%",
        "REDUCE 100%",
        "SELL",
    }:
        return "REDUCE"

    return None


def _compare_action_values(left, right):
    """
    Compare two action-like values semantically.

    Returns:
        CONSISTENT
        POTENTIAL_CONFLICT
        INDETERMINATE
    """

    left = _action_direction(left)
    right = _action_direction(right)

    if left is None or right is None:
        return "INDETERMINATE"

    if left == right:
        return "CONSISTENT"

    return "POTENTIAL_CONFLICT"


def _interpret_rsi(rsi):
    """
    Interpret RSI using established technical-analysis bands.

    Returns None when RSI is unavailable.
    """

    rsi = _semantic_number(rsi)

    if rsi is None:
        return None

    if rsi < 30:
        return "OVERSOLD"

    if rsi < 50:
        return "WEAK_MOMENTUM"

    if rsi <= 70:
        return "POSITIVE_MOMENTUM"

    return "OVERBOUGHT"


def _interpret_price_vs_moving_averages(
    current_price,
    ma50,
    ma200,
):
    """
    Interpret the relationship between current price and
    medium/long-term moving averages.

    No inference is made when the relevant evidence is missing.
    """

    current_price = _semantic_number(current_price)
    ma50 = _semantic_number(ma50)
    ma200 = _semantic_number(ma200)

    relationships = []

    if current_price is not None and ma50 is not None:

        if current_price > ma50:
            relationships.append(
                "PRICE_ABOVE_MA50"
            )
        elif current_price < ma50:
            relationships.append(
                "PRICE_BELOW_MA50"
            )
        else:
            relationships.append(
                "PRICE_AT_MA50"
            )

    if current_price is not None and ma200 is not None:

        if current_price > ma200:
            relationships.append(
                "PRICE_ABOVE_MA200"
            )
        elif current_price < ma200:
            relationships.append(
                "PRICE_BELOW_MA200"
            )
        else:
            relationships.append(
                "PRICE_AT_MA200"
            )

    if (
        "PRICE_BELOW_MA50" in relationships
        and "PRICE_BELOW_MA200" in relationships
    ):
        trend_state = "WEAK_TREND"

    elif (
        "PRICE_ABOVE_MA50" in relationships
        and "PRICE_ABOVE_MA200" in relationships
    ):
        trend_state = "STRONG_TREND"

    else:
        trend_state = "MIXED_TREND"

    if not relationships:
        trend_state = None

    return {
        "relationships": relationships,
        "trend_state": trend_state,
    }


def _semantic_field_relationship(
    field_a,
    value_a,
    field_b,
    value_b,
):
    """
    Describe the semantic relationship between two action fields.

    This is deliberately explicit so the LLM cannot interpret
    identical values as contradictory.
    """

    action_a = _normalise_action(value_a)
    action_b = _normalise_action(value_b)

    if action_a is None or action_b is None:
        return {
            "field_a": field_a,
            "value_a": action_a,
            "field_b": field_b,
            "value_b": action_b,
            "relationship": "INDETERMINATE",
            "meaning": (
                "One or both action values are unavailable."
            ),
        }

    relationship = _compare_action_values(
        action_a,
        action_b,
    )

    if relationship == "CONSISTENT":

        meaning = (
            f"{field_a} ({action_a}) and "
            f"{field_b} ({action_b}) are semantically "
            f"consistent. They do not represent a conflict."
        )

    else:

        meaning = (
            f"{field_a} ({action_a}) and "
            f"{field_b} ({action_b}) point in different "
            f"portfolio-action directions and therefore "
            f"represent a potential conflict requiring review."
        )

    return {
        "field_a": field_a,
        "value_a": action_a,
        "field_b": field_b,
        "value_b": action_b,
        "relationship": relationship,
        "meaning": meaning,
    }


def build_semantic_evidence(
    *,
    asset_type=None,
    current_price=None,
    rsi=None,
    ma50=None,
    ma200=None,
    etf_signal=None,
    signal=None,
    deterministic_action=None,
    proposed_action=None,
):
    """
    Build deterministic semantic/ontology evidence.

    This function translates existing evidence into explicit
    relationships for the AI reviewer.

    It does not alter any decision.

    Returns
    -------
    dict
        JSON-serialisable semantic evidence.
    """

    asset_type = clean_text(
        asset_type,
        default="",
    ).upper()

    if asset_type not in VALID_ASSET_TYPES:
        asset_type = None

    current_price = _semantic_number(
        current_price
    )
    rsi = _semantic_number(rsi)
    ma50 = _semantic_number(ma50)
    ma200 = _semantic_number(ma200)

    deterministic_action = _normalise_action(
        deterministic_action
    )

    proposed_action = _normalise_action(
        proposed_action
    )

    etf_signal = _normalise_action(
        etf_signal
    )

    signal = _normalise_action(
        signal
    )

    semantic = {
        "ontology_version": "1.0",
        "asset_type": asset_type,
        "metric_semantics": {},
        "relationships": [],
        "action_semantics": {},
        "conflicts": [],
        "missing_evidence": [],
    }

    # --------------------------------------------------------
    # Metric semantics
    # --------------------------------------------------------

    if rsi is not None:

        semantic["metric_semantics"]["rsi"] = {
            "value": rsi,
            "category": "MOMENTUM",
            "interpretation": _interpret_rsi(rsi),
        }

    else:

        semantic["missing_evidence"].append(
            "RSI_UNAVAILABLE"
        )

    price_ma = _interpret_price_vs_moving_averages(
        current_price=current_price,
        ma50=ma50,
        ma200=ma200,
    )

    if price_ma["relationships"]:

        semantic["metric_semantics"][
            "price_vs_moving_averages"
        ] = price_ma

        semantic["relationships"].extend(
            price_ma["relationships"]
        )

    else:

        semantic["missing_evidence"].append(
            "MOVING_AVERAGE_RELATIONSHIP_UNAVAILABLE"
        )

    # --------------------------------------------------------
    # Action semantics
    # --------------------------------------------------------

    if deterministic_action is not None:

        semantic["action_semantics"][
            "deterministic_action"
        ] = {
            "value": deterministic_action,
            "direction": _action_direction(
                deterministic_action
            ),
            "meaning": (
                "Rules-based portfolio decision."
            ),
        }

    if proposed_action is not None:

        semantic["action_semantics"][
            "proposed_action"
        ] = {
            "value": proposed_action,
            "direction": _action_direction(
                proposed_action
            ),
            "meaning": (
                "Candidate portfolio action being reviewed."
            ),
        }

    # --------------------------------------------------------
    # ETF signal
    # --------------------------------------------------------

    if asset_type == "ETF":

        if etf_signal is not None:

            semantic["action_semantics"][
                "etf_signal"
            ] = {
                "value": etf_signal,
                "direction": _action_direction(
                    etf_signal
                ),
                "meaning": (
                    "ETF-specific market/trend signal. "
                    "It is evidence, not itself the final "
                    "portfolio decision."
                ),
            }

        else:

            semantic["missing_evidence"].append(
                "ETF_SIGNAL_UNAVAILABLE"
            )

    # --------------------------------------------------------
    # Stock signal
    # --------------------------------------------------------

    if asset_type == "STOCK":

        if signal is not None:

            semantic["action_semantics"][
                "stock_signal"
            ] = {
                "value": signal,
                "direction": _action_direction(
                    signal
                ),
                "meaning": (
                    "Stock technical signal. "
                    "It is evidence, not itself the final "
                    "portfolio decision."
                ),
            }

        else:

            semantic["missing_evidence"].append(
                "STOCK_SIGNAL_UNAVAILABLE"
            )

    # --------------------------------------------------------
    # Deterministic decision vs proposed action
    # --------------------------------------------------------

    relationship = _semantic_field_relationship(
        "DETERMINISTIC DECISION",
        deterministic_action,
        "PROPOSED ACTION",
        proposed_action,
    )

    semantic["relationships"].append(
        relationship
    )

    if (
        relationship["relationship"]
        == "POTENTIAL_CONFLICT"
    ):

        semantic["conflicts"].append(
            "DETERMINISTIC_DECISION_PROPOSED_ACTION_CONFLICT"
        )

    # --------------------------------------------------------
    # ETF signal vs deterministic decision
    #
    # IMPORTANT:
    #
    # Equal values are explicitly CONSISTENT.
    # --------------------------------------------------------

    if asset_type == "ETF":

        relationship = _semantic_field_relationship(
            "ETF SIGNAL",
            etf_signal,
            "DETERMINISTIC DECISION",
            deterministic_action,
        )

        semantic["relationships"].append(
            relationship
        )

        if (
            relationship["relationship"]
            == "POTENTIAL_CONFLICT"
        ):

            semantic["conflicts"].append(
                "ETF_SIGNAL_DETERMINISTIC_DECISION_CONFLICT"
            )

        # ETF signal vs proposed action

        relationship = _semantic_field_relationship(
            "ETF SIGNAL",
            etf_signal,
            "PROPOSED ACTION",
            proposed_action,
        )

        semantic["relationships"].append(
            relationship
        )

        if (
            relationship["relationship"]
            == "POTENTIAL_CONFLICT"
        ):

            semantic["conflicts"].append(
                "ETF_SIGNAL_PROPOSED_ACTION_CONFLICT"
            )

    # --------------------------------------------------------
    # Stock signal vs deterministic decision
    # --------------------------------------------------------

    if asset_type == "STOCK":

        relationship = _semantic_field_relationship(
            "STOCK SIGNAL",
            signal,
            "DETERMINISTIC DECISION",
            deterministic_action,
        )

        semantic["relationships"].append(
            relationship
        )

        if (
            relationship["relationship"]
            == "POTENTIAL_CONFLICT"
        ):

            semantic["conflicts"].append(
                "STOCK_SIGNAL_DETERMINISTIC_DECISION_CONFLICT"
            )

    # --------------------------------------------------------
    # Technical trend vs action
    #
    # IMPORTANT:
    #
    # Weak trend does NOT automatically contradict HOLD.
    # It is primarily relevant when the proposed action
    # increases exposure.
    # --------------------------------------------------------

    trend_state = price_ma["trend_state"]

    if trend_state is not None:

        proposed_direction = _action_direction(
            proposed_action
        )

        if (
            trend_state == "WEAK_TREND"
            and proposed_direction == "BUY"
        ):

            semantic["relationships"].append({
                "field_a": "PRICE/TREND EVIDENCE",
                "value_a": trend_state,
                "field_b": "PROPOSED ACTION",
                "value_b": proposed_action,
                "relationship": "POTENTIAL_CONFLICT",
                "meaning": (
                    "Price is below both MA50 and MA200 "
                    "while the proposed action increases "
                    "exposure. This is a potential technical "
                    "conflict requiring review."
                ),
            })

            semantic["conflicts"].append(
                "WEAK_TREND_VS_BUY_ACTION"
            )

        elif (
            trend_state == "WEAK_TREND"
            and proposed_direction == "HOLD"
        ):

            semantic["relationships"].append({
                "field_a": "PRICE/TREND EVIDENCE",
                "value_a": trend_state,
                "field_b": "PROPOSED ACTION",
                "value_b": proposed_action,
                "relationship": "CONSISTENT",
                "meaning": (
                    "Weak technical trend is compatible "
                    "with maintaining an existing position. "
                    "Weak trend alone is not a contradiction "
                    "of HOLD."
                ),
            })

    # --------------------------------------------------------
    # RSI vs action
    # --------------------------------------------------------

    rsi_state = _interpret_rsi(rsi)
    proposed_direction = _action_direction(
        proposed_action
    )

    if rsi_state is not None:

        if (
            rsi_state == "OVERBOUGHT"
            and proposed_direction == "BUY"
        ):

            semantic["relationships"].append({
                "field_a": "RSI",
                "value_a": rsi_state,
                "field_b": "PROPOSED ACTION",
                "value_b": proposed_action,
                "relationship": "POTENTIAL_CONFLICT",
                "meaning": (
                    "RSI is overbought while the proposed "
                    "action increases exposure."
                ),
            })

            semantic["conflicts"].append(
                "OVERBOUGHT_RSI_VS_BUY_ACTION"
            )

        elif (
            rsi_state == "OVERSOLD"
            and proposed_direction == "REDUCE"
        ):

            semantic["relationships"].append({
                "field_a": "RSI",
                "value_a": rsi_state,
                "field_b": "PROPOSED ACTION",
                "value_b": proposed_action,
                "relationship": "POTENTIAL_CONFLICT",
                "meaning": (
                    "RSI is oversold while the proposed "
                    "action reduces exposure. RSI alone "
                    "does not determine the decision, but "
                    "the relationship warrants review."
                ),
            })

            semantic["conflicts"].append(
                "OVERSOLD_RSI_VS_REDUCE_ACTION"
            )

    # --------------------------------------------------------
    # Overall semantic status
    # --------------------------------------------------------

    if semantic["conflicts"]:

        semantic["overall_status"] = (
            "POTENTIAL_CONFLICT"
        )

    elif semantic["missing_evidence"]:

        semantic["overall_status"] = (
            "EVIDENCE_INCOMPLETE"
        )

    else:

        semantic["overall_status"] = (
            "CONSISTENT"
        )

    return semantic




def normalise_text(
    value: Any,
    default: str = "",
) -> str:
    """
    Normalise text while preserving its human-readable form.
    """

    return clean_text(
        value,
        default,
    )


def clean_ticker(
    value: Any,
) -> str:
    """
    Normalise ticker symbols.
    """

    value = clean_text(
        value,
        "",
    )

    return value.upper()


def normalise_action(
    value: Any,
) -> str:
    """
    Normalise a portfolio action.
    """

    return clean_text(
        value,
        "HOLD",
    ).upper()


def clean_value(
    value: Any,
) -> Any:
    """
    Convert arbitrary values into serialisable Python values.
    """

    if value is None:
        return None

    if isinstance(
        value,
        bool,
    ):

        return value

    if isinstance(
        value,
        (str, int, float),
    ):

        try:

            if isinstance(
                value,
                float,
            ) and not math.isfinite(value):

                return None

        except Exception:
            pass

        return value

    if isinstance(
        value,
        pd.Timestamp,
    ):

        return value.isoformat()

    if isinstance(
        value,
        pd.Series,
    ):

        if value.empty:
            return None

        return clean_value(
            value.iloc[0]
        )

    if isinstance(
        value,
        pd.DataFrame,
    ):

        return None

    if isinstance(
        value,
        (list, tuple, set),
    ):

        return [
            clean_value(item)
            for item in value
        ]

    if isinstance(
        value,
        dict,
    ):

        return {
            str(key): clean_value(item)
            for key, item in value.items()
        }

    try:

        if pd.isna(value):
            return None

    except Exception:
        pass

    return str(value)


def clean_record(
    record: dict,
) -> dict:
    """
    Convert a dictionary into a fully serialisable dictionary.
    """

    if not isinstance(
        record,
        dict,
    ):

        return {}

    return {
        str(key): clean_value(value)
        for key, value in record.items()
    }


def get_value(
    row: Any,
    *columns: str,
    default: Any = None,
) -> Any:
    """
    Return the first available value from a dictionary or pandas Series.
    """

    if row is None:
        return default

    for column in columns:

        try:

            if isinstance(
                row,
                dict,
            ):

                if column not in row:
                    continue

                value = row.get(
                    column
                )

            else:

                if not hasattr(
                    row,
                    "index",
                ):
                    continue

                if column not in row.index:
                    continue

                value = row.get(
                    column
                )

            if value is None:
                continue

            try:

                if pd.isna(value):
                    continue

            except Exception:
                pass

            return value

        except Exception:
            continue

    return default


def dataframe_records(
    dataframe: Any,
) -> list[dict]:
    """
    Convert a DataFrame to clean Python dictionaries.
    """

    if not isinstance(
        dataframe,
        pd.DataFrame,
    ):

        return []

    if dataframe.empty:
        return []

    records = dataframe.to_dict(
        orient="records"
    )

    return [
        clean_record(record)
        for record in records
        if isinstance(
            record,
            dict,
        )
    ]


def normalise_records(
    data: Any,
) -> list[dict]:
    """
    Normalise DataFrame, list or dictionary input into records.
    """

    if data is None:
        return []

    if isinstance(
        data,
        pd.DataFrame,
    ):

        return dataframe_records(
            data
        )

    if isinstance(
        data,
        dict,
    ):

        return [
            clean_record(data)
        ]

    if isinstance(
        data,
        (list, tuple),
    ):

        return [
            clean_record(item)
            for item in data
            if isinstance(
                item,
                dict,
            )
        ]

    return []


# ============================================================
# Asset classification
# ============================================================

def get_asset_type(
    row: Any,
    default: str = "STOCK",
) -> str:
    """
    Determine whether an asset is a STOCK or ETF.

    Existing upstream classification is preferred.

    This function does not attempt to discover or classify ETFs from
    external data. It only consumes existing classification fields.
    """

    value = get_value(
        row,
        "Asset Type",
        "Asset_Type",
        "Type",
        "Security Type",
        "security_type",
        default=default,
    )

    asset_type = clean_text(
        value,
        default,
    ).upper()

    if asset_type in {
        "EQUITY",
        "SHARE",
        "SHARES",
        "STOCK",
    }:

        return "STOCK"

    if asset_type in {
        "ETF",
        "EXCHANGE TRADED FUND",
        "EXCHANGE-TRADED FUND",
    }:

        return "ETF"

    if asset_type in VALID_ASSET_TYPES:
        return asset_type

    return default


# ============================================================
# Portfolio holdings lookup
# ============================================================

def build_holdings_lookup(
    portfolio: Any,
) -> dict[str, dict]:
    """
    Build a ticker-based ownership lookup.

    Positive quantity means the asset is owned.

    Cash is retained in the lookup but marked as cash.
    """

    records = normalise_records(
        portfolio
    )

    lookup = {}

    for row in records:

        ticker = clean_ticker(
            get_value(
                row,
                "Ticker",
                "ticker",
                "Symbol",
                "symbol",
                default="",
            )
        )

        if not ticker:
            continue

        quantity = safe_float(
            get_value(
                row,
                "Quantity",
                "quantity",
                "Shares",
                "shares",
                default=0,
            )
        )

        market_value = safe_float(
            get_value(
                row,
                "Market Value",
                "market_value",
                "Current Value",
                "Current Value £",
                "Value",
                default=0,
            )
        )

        allocation = safe_float(
            get_value(
                row,
                "Allocation %",
                "allocation_pct",
                "Allocation",
                "Portfolio %",
                default=0,
            )
        )

        sector = clean_text(
            get_value(
                row,
                "Sector",
                "sector",
                default="Unknown",
            ),
            "Unknown",
        )

        asset_type = get_asset_type(
            row
        )

        is_cash = (
            ticker == "CASH"
            or
            "cash" in ticker.lower()
        )

        lookup[ticker] = {

            "owned":
                quantity > 0,

            "quantity":
                quantity,

            "market_value":
                market_value,

            "allocation_pct":
                allocation,

            "sector":
                sector,

            "asset_type":
                asset_type,

            "is_cash":
                is_cash,
        }

    return lookup


# ============================================================
# Portfolio context
# ============================================================

def build_portfolio_context(
    portfolio: Any = None,
    portfolio_summary: Any = None,
    sector_analysis: Any = None,
    capital_allocation: Any = None,
    capital_summary: Any = None,
) -> dict:
    """
    Build portfolio-level context.

    No portfolio judgement is made here.
    """

    if portfolio is None:
        portfolio = portfolio_summary

    records = normalise_records(
        portfolio
    )

    holdings = []

    total_market_value = 0.0
    cash = 0.0

    stock_count = 0
    etf_count = 0

    largest_position_pct = 0.0
    largest_position_ticker = ""

    for row in records:

        ticker = clean_ticker(
            get_value(
                row,
                "Ticker",
                "ticker",
                "Symbol",
                default="",
            )
        )

        if not ticker:
            continue

        quantity = safe_float(
            get_value(
                row,
                "Quantity",
                "quantity",
                "Shares",
                "shares",
                default=0,
            )
        )

        market_value = safe_float(
            get_value(
                row,
                "Market Value",
                "market_value",
                "Current Value",
                "Value",
                default=0,
            )
        )

        allocation = safe_float(
            get_value(
                row,
                "Allocation %",
                "allocation_pct",
                "Allocation",
                "Portfolio %",
                default=0,
            )
        )

        sector = clean_text(
            get_value(
                row,
                "Sector",
                "sector",
                default="Unknown",
            ),
            "Unknown",
        )

        asset_type = get_asset_type(
            row
        )

        is_cash = (
            ticker == "CASH"
            or
            "cash" in ticker.lower()
        )

        holding = {
            "ticker":
                ticker,

            "asset_type":
                asset_type,

            "quantity":
                quantity,

            "market_value":
                market_value,

            "allocation_pct":
                allocation,

            "sector":
                sector,

            "is_cash":
                is_cash,
        }

        holdings.append(
            holding
        )

        if is_cash:

            cash += market_value

            continue

        total_market_value += market_value

        if asset_type == "ETF":

            etf_count += 1

        else:

            stock_count += 1

        if allocation > largest_position_pct:

            largest_position_pct = allocation

            largest_position_ticker = ticker

    sectors = normalise_records(
        sector_analysis
    )

    # --------------------------------------------------------
    # Capital
    # --------------------------------------------------------

    capital = {
        "discretionary_spend_limit": 0.0,
        "capital_released_from_sales": 0.0,
        "total_available_capital": 0.0,
        "capital_allocated": 0.0,
        "remaining_capital": 0.0,
    }

    capital_records = normalise_records(
        capital_summary
    )

    for row in capital_records:

        metric = clean_text(
            get_value(
                row,
                "Metric",
                "metric",
                "Name",
                default="",
            )
        ).lower()

        amount = safe_float(
            get_value(
                row,
                "Amount",
                "amount",
                "Value",
                default=0,
            )
        )

        if "discretionary" in metric:

            capital[
                "discretionary_spend_limit"
            ] = amount

        elif (
            "released" in metric
            and
            "capital" in metric
        ):

            capital[
                "capital_released_from_sales"
            ] = amount

        elif "total available" in metric:

            capital[
                "total_available_capital"
            ] = amount

        elif "allocated" in metric:

            capital[
                "capital_allocated"
            ] = amount

        elif "remaining" in metric:

            capital[
                "remaining_capital"
            ] = amount

    if isinstance(
        capital_summary,
        dict,
    ):

        for key, value in capital_summary.items():

            normalised_key = str(
                key
            ).strip().lower()

            if (
                "discretionary"
                in normalised_key
            ):

                capital[
                    "discretionary_spend_limit"
                ] = safe_float(value)

            elif (
                "released"
                in normalised_key
            ):

                capital[
                    "capital_released_from_sales"
                ] = safe_float(value)

            elif (
                "total_available"
                in normalised_key
                or
                "total available"
                in normalised_key
            ):

                capital[
                    "total_available_capital"
                ] = safe_float(value)

            elif "allocated" in normalised_key:

                capital[
                    "capital_allocated"
                ] = safe_float(value)

            elif "remaining" in normalised_key:

                capital[
                    "remaining_capital"
                ] = safe_float(value)

    allocation_records = normalise_records(
        capital_allocation
    )

    portfolio = {
        "total_positions":
            len(
                [
                    item
                    for item in holdings
                    if not item["is_cash"]
                ]
            ),

        "total_market_value":
            total_market_value,

        "cash":
            cash,

        "largest_position_pct":
            largest_position_pct,

        "largest_position_ticker":
            largest_position_ticker,

        "stock_count":
            stock_count,

        "etf_count":
            etf_count,

        "sector_count":
            len(sectors),
    }

    return {

        "portfolio":
            portfolio,

        "holdings":
            holdings,

        "sectors":
            sectors,

        "capital":
            capital,

        "capital_allocation":
            allocation_records,
    }


# ============================================================
# Recommendation intelligence
# ============================================================

def build_intelligence_lookup(
    recommendation_intelligence: Any,
) -> dict[str, dict]:
    """
    Build ticker lookup for recommendation intelligence.
    """

    records = normalise_records(
        recommendation_intelligence
    )

    lookup = {}

    for record in records:

        ticker = clean_ticker(
            get_value(
                record,
                "Ticker",
                "ticker",
                "Symbol",
                default="",
            )
        )

        if ticker:

            lookup[ticker] = record

    return lookup


def extract_intelligence(
    ticker: str,
    intelligence_lookup: dict[str, dict],
) -> dict:
    """
    Extract historical recommendation intelligence for one ticker.

    Historical learning is exposed at both:
        - generic signal level
        - 5-day horizon
        - 10-day horizon
        - 60-day horizon

    60-day evidence is preferred when sufficiently mature.
    Missing or immature historical evidence is not treated as
    negative evidence.

    This function transports and normalises learning evidence.
    It does not make investment decisions or change scoring weights.
    """

    record = intelligence_lookup.get(ticker)

    if not record:
        return {
            "available": False,

            "historical_signal_observations": 0,
            "historical_signal_average_return_pct": 0.0,
            "historical_signal_win_rate_pct": 0.0,
            "historical_signal_reliability": "INSUFFICIENT DATA",

            "historical_5_day": {
                "observations": 0,
                "average_return_pct": 0.0,
                "win_rate_pct": 0.0,
                "reliability": "INSUFFICIENT DATA",
            },

            "historical_10_day": {
                "observations": 0,
                "average_return_pct": 0.0,
                "win_rate_pct": 0.0,
                "reliability": "INSUFFICIENT DATA",
            },

            "historical_60_day": {
                "observations": 0,
                "average_return_pct": 0.0,
                "win_rate_pct": 0.0,
                "reliability": "INSUFFICIENT DATA",
            },

            "preferred_learning_horizon": None,
            "preferred_learning_observations": 0,
            "preferred_learning_average_return_pct": 0.0,
            "preferred_learning_win_rate_pct": 0.0,
            "preferred_learning_reliability": "INSUFFICIENT DATA",

            "learning_adjustment": 0.0,
            "learning_adjusted_score": None,

            "recommendation_strength": "",
            "score_bucket": "",
            "score_bucket_observations": 0,
            "score_bucket_average_return_pct": 0.0,
            "score_bucket_win_rate_pct": 0.0,
            "confidence": "",
        }

    def extract_horizon(horizon: str) -> dict:
        """
        Extract one learning horizon.

        Supports both nested dictionaries and flat fields so that
        the context layer remains compatible with the existing
        recommendation-intelligence output.
        """

        horizon_lower = horizon.lower()

        nested = get_value(
            record,
            f"historical_{horizon_lower}_day",
            f"historical_{horizon_lower}",
            f"Historical {horizon} Day",
            f"Historical {horizon}-Day",
            default=None,
        )

        if not isinstance(nested, dict):
            nested = {}

        observations = safe_float(
            get_value(
                nested,
                "observations",
                "Observations",
                "Historical Observations",
                default=0,
            )
        )

        average_return = safe_float(
            get_value(
                nested,
                "average_return_pct",
                "Average Return %",
                "Historical Average Return %",
                default=0,
            )
        )

        win_rate = safe_float(
            get_value(
                nested,
                "win_rate_pct",
                "Win Rate %",
                "Historical Win Rate %",
                default=0,
            )
        )

        reliability = clean_text(
            get_value(
                nested,
                "reliability",
                "Reliability",
                "Historical Reliability",
                default="",
            )
        )

        # Flat-field fallback.
        if observations <= 0:
            observations = safe_float(
                get_value(
                    record,
                    f"Historical {horizon} Day Observations",
                    f"Historical {horizon}-Day Observations",
                    f"Historical {horizon}_day_observations",
                    f"historical_{horizon_lower}_day_observations",
                    default=0,
                )
            )

        if average_return == 0.0:
            average_return = safe_float(
                get_value(
                    record,
                    f"Historical {horizon} Day Average Return %",
                    f"Historical {horizon}-Day Average Return %",
                    f"Historical {horizon}_day_average_return_pct",
                    default=0,
                )
            )

        if win_rate == 0.0:
            win_rate = safe_float(
                get_value(
                    record,
                    f"Historical {horizon} Day Win Rate %",
                    f"Historical {horizon}-Day Win Rate %",
                    f"Historical {horizon}_day_win_rate_pct",
                    default=0,
                )
            )

        if not reliability:
            reliability = clean_text(
                get_value(
                    record,
                    f"Historical {horizon} Day Reliability",
                    f"Historical {horizon}-Day Reliability",
                    f"Historical {horizon}_day_reliability",
                    default="",
                )
            )

        if not reliability:
            if observations <= 0:
                reliability = "INSUFFICIENT DATA"
            elif observations < 30:
                reliability = "IMMATURE"
            else:
                reliability = "VALID"

        return {
            "observations": int(observations),
            "average_return_pct": average_return,
            "win_rate_pct": win_rate,
            "reliability": reliability,
        }

    # --------------------------------------------------------
    # Extract all learning horizons.
    # --------------------------------------------------------

    historical_5_day = extract_horizon("5")
    historical_10_day = extract_horizon("10")
    historical_60_day = extract_horizon("60")

    # --------------------------------------------------------
    # Prefer mature 60-day evidence.
    #
    # If 60-day is not mature, fall back to 10-day and then
    # 5-day.
    # --------------------------------------------------------

    preferred_horizon = None
    preferred_data = None

    for horizon, data in (
        ("60-day", historical_60_day),
        ("10-day", historical_10_day),
        ("5-day", historical_5_day),
    ):
        if data["observations"] >= 30:
            preferred_horizon = horizon
            preferred_data = data
            break

    # --------------------------------------------------------
    # If no horizon is mature, retain the largest available
    # sample as immature supporting evidence.
    # --------------------------------------------------------

    if preferred_data is None:
        available_horizons = [
            ("60-day", historical_60_day),
            ("10-day", historical_10_day),
            ("5-day", historical_5_day),
        ]

        available_horizons.sort(
            key=lambda item: item[1]["observations"],
            reverse=True,
        )

        if available_horizons:
            candidate_horizon, candidate_data = available_horizons[0]

            if candidate_data["observations"] > 0:
                preferred_horizon = candidate_horizon
                preferred_data = candidate_data

    if preferred_data is None:
        preferred_learning_observations = 0
        preferred_learning_average_return_pct = 0.0
        preferred_learning_win_rate_pct = 0.0
        preferred_learning_reliability = "INSUFFICIENT DATA"
    else:
        preferred_learning_observations = (
            preferred_data["observations"]
        )

        preferred_learning_average_return_pct = (
            preferred_data["average_return_pct"]
        )

        preferred_learning_win_rate_pct = (
            preferred_data["win_rate_pct"]
        )

        preferred_learning_reliability = (
            preferred_data["reliability"]
        )

    # --------------------------------------------------------
    # Existing generic learning fields.
    # --------------------------------------------------------

    learning_adjusted = get_value(
        record,
        "Learning Adjusted Score",
        "learning_adjusted_score",
        default=None,
    )

    return {
        "available": True,

        "historical_signal_observations": int(
            safe_float(
                get_value(
                    record,
                    "Historical Signal Observations",
                    "Signal Observations",
                    default=0,
                )
            )
        ),

        "historical_signal_average_return_pct": safe_float(
            get_value(
                record,
                "Historical Signal Average Return %",
                "Signal Average Return %",
                default=0,
            )
        ),

        "historical_signal_win_rate_pct": safe_float(
            get_value(
                record,
                "Historical Signal Win Rate %",
                "Signal Win Rate %",
                default=0,
            )
        ),

        "historical_signal_reliability": clean_text(
            get_value(
                record,
                "Historical Signal Reliability",
                "Signal Reliability",
                default="INSUFFICIENT DATA",
            ),
            "INSUFFICIENT DATA",
        ),

        # Horizon-specific learning.
        "historical_5_day": historical_5_day,
        "historical_10_day": historical_10_day,
        "historical_60_day": historical_60_day,

        # Preferred learning evidence.
        "preferred_learning_horizon": preferred_horizon,
        "preferred_learning_observations": (
            preferred_learning_observations
        ),
        "preferred_learning_average_return_pct": (
            preferred_learning_average_return_pct
        ),
        "preferred_learning_win_rate_pct": (
            preferred_learning_win_rate_pct
        ),
        "preferred_learning_reliability": (
            preferred_learning_reliability
        ),

        # Existing learning adjustment.
        "learning_adjustment": safe_float(
            get_value(
                record,
                "Learning Adjustment",
                "learning_adjustment",
                default=0,
            )
        ),

        "learning_adjusted_score": (
            safe_float(learning_adjusted)
            if learning_adjusted is not None
            else None
        ),

        "recommendation_strength": clean_text(
            get_value(
                record,
                "Recommendation Strength",
                "recommendation_strength",
                default="",
            )
        ),

        "score_bucket": clean_text(
            get_value(
                record,
                "Score Bucket",
                "score_bucket",
                default="",
            )
        ),

        "score_bucket_observations": int(
            safe_float(
                get_value(
                    record,
                    "Score Bucket Observations",
                    "Bucket Observations",
                    default=0,
                )
            )
        ),

        "score_bucket_average_return_pct": safe_float(
            get_value(
                record,
                "Score Bucket Average Return %",
                "Bucket Average Return %",
                default=0,
            )
        ),

        "score_bucket_win_rate_pct": safe_float(
            get_value(
                record,
                "Score Bucket Win Rate %",
                "Bucket Win Rate %",
                default=0,
            )
        ),

        "confidence": clean_text(
            get_value(
                record,
                "Confidence",
                "confidence",
                default="",
            )
        ),
    }

# ============================================================
# Recommendation evidence snapshot
# ============================================================

def get_recommendation_evidence_snapshot(
    candidate: Any,
) -> dict:
    """
    Load the immutable evidence snapshot associated with a
    recommendation when a recommendation ID is available.

    Backward compatibility
    -----------------------
    Older candidate records may not contain a recommendation ID
    and older recommendations may not have an evidence snapshot.

    In either case this function returns an empty dictionary and
    the existing candidate fields remain authoritative.

    This function performs no scoring or decision logic.
    """

    recommendation_id = get_value(
        candidate,
        "Recommendation ID",
        "recommendation_id",
        "RecommendationID",
        "recommendationId",
        "id",
        default=None,
    )

    if recommendation_id is None:

        return {}

    try:

        return get_recommendation_evidence(
            int(
                recommendation_id
            )
        ) or {}

    except (
        TypeError,
        ValueError,
        Exception,
    ):

        return {}


def merge_evidence_value(
    candidate: Any,
    evidence: dict,
    *candidate_keys: str,
    evidence_key: str,
    default: Any = None,
) -> Any:
    """
    Return the recommendation snapshot value when available,
    otherwise fall back to the existing candidate value.

    The database snapshot is preferred because it represents the
    evidence available when the recommendation was generated.
    """

    if (
        evidence
        and
        evidence.get(
            evidence_key
        ) is not None
    ):

        return evidence.get(
            evidence_key
        )

    return get_value(
        candidate,
        *candidate_keys,
        default=default,
    )


# ============================================================
# Candidate context
# ============================================================


def build_candidate_context(
    candidate: Any,
    intelligence_lookup: dict[str, dict] | None = None,
    portfolio_holdings: dict[str, dict] | None = None,
) -> dict | None:
    """
    Build the AI context for one candidate.

    The existing rules-based action is preserved exactly as an input.

    No new decision is made here.

    Recommendation evidence
    ------------------------
    When a recommendation ID is available, the immutable evidence
    snapshot saved at recommendation creation time is loaded and
    used as the preferred source for analytical evidence.

    Existing candidate fields remain the fallback so historical
    recommendations and legacy callers continue to work.
    """

    if candidate is None:
        return None

    if intelligence_lookup is None:
        intelligence_lookup = {}

    if portfolio_holdings is None:
        portfolio_holdings = {}

    ticker = clean_ticker(
        get_value(
            candidate,
            "Ticker",
            "ticker",
            "Symbol",
            default="",
        )
    )

    if not ticker:
        return None

    # --------------------------------------------------------
    # Immutable recommendation evidence
    # --------------------------------------------------------

    evidence_snapshot = get_recommendation_evidence_snapshot(
        candidate
    )

    evidence_available = bool(
        evidence_snapshot
    )

    recommendation_id = get_value(
        candidate,
        "Recommendation ID",
        "recommendation_id",
        "RecommendationID",
        "recommendationId",
        "id",
        default=None,
    )

    asset_type = get_asset_type(
        candidate
    )

    holding = portfolio_holdings.get(
        ticker,
        {},
    )

    owned = bool(
        holding.get(
            "owned",
            False,
        )
    )

    if holding:
        quantity = safe_float(
            holding.get(
                "quantity",
                0,
            )
        )

        market_value = safe_float(
            holding.get(
                "market_value",
                0,
            )
        )

        allocation_pct = safe_float(
            holding.get(
                "allocation_pct",
                0,
            )
        )

        sector = clean_text(
            holding.get(
                "sector",
                "Unknown",
            ),
            "Unknown",
        )

        owned = quantity > 0

    else:
        quantity = safe_float(
            get_value(
                candidate,
                "Quantity",
                "quantity",
                "Shares",
                default=0,
            )
        )

        market_value = safe_float(
            get_value(
                candidate,
                "Market Value",
                "market_value",
                "Current Value",
                default=0,
            )
        )

        allocation_pct = safe_float(
            get_value(
                candidate,
                "Allocation %",
                "allocation_pct",
                "Allocation",
                default=0,
            )
        )

        sector = clean_text(
            merge_evidence_value(
                candidate,
                evidence_snapshot,
                "Sector",
                "sector",
                evidence_key="sector",
                default="Unknown",
            ),
            "Unknown",
        )

        owned = quantity > 0

    # --------------------------------------------------------
    # Core scoring
    # --------------------------------------------------------

    investment_score = safe_float(
        merge_evidence_value(
            candidate,
            evidence_snapshot,
            "Investment Score",
            "investment_score",
            "Score",
            "score",
            evidence_key="investment_score",
            default=0,
        )
    )

    etf_score_value = get_value(
        candidate,
        "ETF Score",
        "etf_score",
        default=None,
    )

    etf_score = (
        safe_float(
            etf_score_value
        )
        if etf_score_value is not None
        else None
    )

    # FIX: Preserve ETF Signal through the AI context boundary.
    etf_signal = clean_text(
        get_value(
            candidate,
            "ETF Signal",
            "etf_signal",
            default="",
        )
    )

    signal = clean_text(
        merge_evidence_value(
            candidate,
            evidence_snapshot,
            "Signal",
            "Momentum Signal",
            "signal",
            evidence_key="signal",
            default="",
        )
    )



    # --------------------------------------------------------
    # Rules-based proposal
    # --------------------------------------------------------

    rules_action = normalise_action(
        get_value(
            candidate,
            "Action",
            "action",
            "Proposed Action",
            "proposed_action",
            default="HOLD",
        )
    )

    proposed_action = normalise_action(
        get_value(
            candidate,
            "Proposed Action",
            "proposed_action",
            default=rules_action,
        )
    )

    # --------------------------------------------------------
    # Analytical evidence
    # --------------------------------------------------------

    technical_score = safe_float(
        merge_evidence_value(
            candidate,
            evidence_snapshot,
            "Technical Score",
            "technical_score",
            evidence_key="technical_score",
            default=0,
        )
    )

    quality_score = safe_float(
        merge_evidence_value(
            candidate,
            evidence_snapshot,
            "Quality Score",
            "quality_score",
            evidence_key="quality_score",
            default=0,
        )
    )

    growth_score = safe_float(
        merge_evidence_value(
            candidate,
            evidence_snapshot,
            "Growth Score",
            "growth_score",
            evidence_key="growth_score",
            default=0,
        )
    )

    confidence_score = safe_float(
        merge_evidence_value(
            candidate,
            evidence_snapshot,
            "Confidence Score",
            "confidence_score",
            evidence_key="confidence_score",
            default=0,
        )
    )

    current_price = safe_float(
        merge_evidence_value(
            candidate,
            evidence_snapshot,
            "Price",
            "Current Price",
            "Entry Price",
            "entry_price",
            evidence_key="entry_price",
            default=0,
        )
    )

    rsi = safe_float(
        merge_evidence_value(
            candidate,
            evidence_snapshot,
            "RSI",
            "rsi",
            evidence_key="rsi",
            default=None,
        )
    )

    sma50 = safe_float(
        merge_evidence_value(
            candidate,
            evidence_snapshot,
            "SMA50",
            "MA50",
            "ma50",
            evidence_key="sma50",
            default=None,
        )
    )

    sma200 = safe_float(
        merge_evidence_value(
            candidate,
            evidence_snapshot,
            "SMA200",
            "MA200",
            "ma200",
            evidence_key="sma200",
            default=None,
        )
    )

    return_3m = safe_float(
        merge_evidence_value(
            candidate,
            evidence_snapshot,
            "Return_3m",
            "Return 3m",
            "Return 3M",
            "3M Return %",
            evidence_key="return_3m",
            default=0,
        )
    )

    trend = clean_text(
        merge_evidence_value(
            candidate,
            evidence_snapshot,
            "Trend",
            "trend",
            evidence_key="trend",
            default="",
        )
    )

    trend_score = safe_float(
        merge_evidence_value(
            candidate,
            evidence_snapshot,
            "Trend Score",
            "trend_score",
            evidence_key="trend_score",
            default=0,
        )
    )

    momentum_score = safe_float(
        merge_evidence_value(
            candidate,
            evidence_snapshot,
            "Momentum Score",
            "momentum_score",
            evidence_key="momentum_score",
            default=0,
        )
    )

    volume_score = safe_float(
        merge_evidence_value(
            candidate,
            evidence_snapshot,
            "Volume Score",
            "volume_score",
            evidence_key="volume_score",
            default=0,
        )
    )

    risk_score = safe_float(
        merge_evidence_value(
            candidate,
            evidence_snapshot,
            "Risk Score",
            "risk_score",
            evidence_key="risk_score",
            default=0,
        )
    )

    # --------------------------------------------------------
    # Fundamental evidence
    # --------------------------------------------------------

    revenue_growth = safe_float(
        merge_evidence_value(
            candidate,
            evidence_snapshot,
            "Revenue Growth",
            "revenue_growth",
            evidence_key="revenue_growth",
            default=0,
        )
    )

    profit_margin = safe_float(
        merge_evidence_value(
            candidate,
            evidence_snapshot,
            "Profit Margin",
            "profit_margin",
            evidence_key="profit_margin",
            default=0,
        )
    )

    return_on_equity = safe_float(
        merge_evidence_value(
            candidate,
            evidence_snapshot,
            "Return on Equity",
            "ROE",
            "return_on_equity",
            evidence_key="return_on_equity",
            default=0,
        )
    )

    debt_to_equity = safe_float(
        merge_evidence_value(
            candidate,
            evidence_snapshot,
            "Debt to Equity",
            "Debt / Equity",
            "debt_to_equity",
            evidence_key="debt_to_equity",
            default=0,
        )
    )

    sector = clean_text(
        merge_evidence_value(
            candidate,
            evidence_snapshot,
            "Sector",
            "sector",
            evidence_key="sector",
            default=sector,
        ),
        "Unknown",
    )

    industry = clean_text(
        merge_evidence_value(
            candidate,
            evidence_snapshot,
            "Industry",
            "industry",
            evidence_key="industry",
            default="Unknown",
        ),
        "Unknown",
    )

    # --------------------------------------------------------
    # Reasons / risks
    # --------------------------------------------------------

    technical_reasons = merge_evidence_value(
        candidate,
        evidence_snapshot,
        "Technical Reasons",
        "technical_reasons",
        evidence_key="technical_reasons",
        default=[],
    )

    technical_risks = merge_evidence_value(
        candidate,
        evidence_snapshot,
        "Technical Risks",
        "technical_risks",
        evidence_key="technical_risks",
        default=[],
    )

    recommendation_reasons = merge_evidence_value(
        candidate,
        evidence_snapshot,
        "Recommendation Reasons",
        "recommendation_reasons",
        evidence_key="recommendation_reasons",
        default=[],
    )

    recommendation_risks = merge_evidence_value(
        candidate,
        evidence_snapshot,
        "Recommendation Risks",
        "recommendation_risks",
        evidence_key="recommendation_risks",
        default=[],
    )

    # --------------------------------------------------------
    # Deterministic AI assessment
    # --------------------------------------------------------

    ai_decision = merge_evidence_value(
        candidate,
        evidence_snapshot,
        "AI Decision",
        "ai_decision",
        evidence_key="ai_decision",
        default="",
    )

    ai_conviction = merge_evidence_value(
        candidate,
        evidence_snapshot,
        "AI Conviction",
        "ai_conviction",
        evidence_key="ai_conviction",
        default="",
    )

    ai_conviction_score = safe_float(
        merge_evidence_value(
            candidate,
            evidence_snapshot,
            "AI Conviction Score",
            "ai_conviction_score",
            evidence_key="ai_conviction_score",
            default=0,
        )
    )

    ai_action = merge_evidence_value(
        candidate,
        evidence_snapshot,
        "AI Action",
        "ai_action",
        evidence_key="ai_action",
        default=[],
    )

    ai_investment_thesis = merge_evidence_value(
        candidate,
        evidence_snapshot,
        "AI Investment Thesis",
        "Investment Thesis",
        "ai_investment_thesis",
        evidence_key="ai_investment_thesis",
        default=[],
    )

    ai_risks = merge_evidence_value(
        candidate,
        evidence_snapshot,
        "AI Risks",
        "ai_risks",
        evidence_key="ai_risks",
        default=[],
    )

    # --------------------------------------------------------
    # Historical recommendation intelligence
    # --------------------------------------------------------

    intelligence = extract_intelligence(
        ticker,
        intelligence_lookup,
    )


    # --------------------------------------------------------
    # Semantic / ontology evidence
    # --------------------------------------------------------
    #
    # IMPORTANT:
    # This must be built only after all analytical evidence
    # and action fields have been resolved.
    #
    # The semantic layer does NOT make or change a decision.
    # It translates the existing evidence into explicit
    # relationships for the LLM reviewer.
    # --------------------------------------------------------

    proposed_action = normalise_action(
        get_value(
            candidate,
            "Proposed Action",
            "proposed_action",
            default=rules_action,
        )
    )

    semantic_evidence = build_semantic_evidence(
        asset_type=asset_type,
        current_price=current_price,
        rsi=rsi,
        ma50=sma50,
        ma200=sma200,
        etf_signal=etf_signal,
        signal=signal,
        deterministic_action=rules_action,
        proposed_action=proposed_action,
    )


    return {
        "ticker":
            ticker,

        "recommendation_id":
            recommendation_id,

        "recommendation_evidence": {
            "available":
                evidence_available,

            "capture_date":
                (
                    evidence_snapshot.get(
                        "capture_date"
                    )
                    if evidence_snapshot
                    else None
                ),
        },

        "asset_type":
            asset_type,

        "ownership": {
            "owned":
                owned,

            "quantity":
                quantity,

            "market_value":
                market_value,

            "allocation_pct":
                allocation_pct,
        },

        "analysis": {
            "investment_score":
                (
                    investment_score
                    if asset_type == "STOCK"
                    else None
                ),

            "etf_score":
                (
                    etf_score
                    if asset_type == "ETF"
                    else None
                ),

            # FIX: Preserve ETF Signal in returned AI context.
            "etf_signal":
                etf_signal,

            "signal":
                signal,

            "technical_score":
                (
                    technical_score
                    if asset_type == "STOCK"
                    else None
                ),

            "quality_score":
                (
                    quality_score
                    if asset_type == "STOCK"
                    else None
                ),

            "growth_score":
                (
                    growth_score
                    if asset_type == "STOCK"
                    else None
                ),

            "confidence_score":
                confidence_score,

            "current_price":
                current_price,

            "rsi":
                rsi,

            "ma50":
                sma50,

            "ma200":
                sma200,

            "return_3m":
                return_3m,

            "trend":
                trend,

            "trend_score":
                trend_score,

            "momentum_score":
                momentum_score,

            "volume_score":
                volume_score,

            "risk_score":
                risk_score,

            "revenue_growth":
                revenue_growth,

            "profit_margin":
                profit_margin,

            "return_on_equity":
                return_on_equity,

            "debt_to_equity":
                debt_to_equity,

            "sector":
                sector,

            "industry":
                industry,

            "technical_reasons":
                technical_reasons,

            "technical_risks":
                technical_risks,

            "recommendation_reasons":
                recommendation_reasons,

            "recommendation_risks":
                recommendation_risks,

            "ai_decision":
                ai_decision,

            "ai_conviction":
                ai_conviction,

            "ai_conviction_score":
                ai_conviction_score,

            "ai_action":
                ai_action,

            "ai_investment_thesis":
                ai_investment_thesis,

            "ai_risks":
                ai_risks,
        },

        "rules_based_decision": {
            "action":
                rules_action,
        },

        # ----------------------------------------------------
        # Explicit semantic / ontology interpretation
        # ----------------------------------------------------
        #
        # This is explanatory evidence for the LLM reviewer.
        # It is not a decision and must not override the
        # deterministic decision.
        # ----------------------------------------------------
        "semantic_evidence":
            semantic_evidence,

        "recommendation_intelligence":
            intelligence,
    }


# ============================================================
# Portfolio flags
# ============================================================

def build_portfolio_flags(
    portfolio: dict,
) -> list[str]:
    """
    Build observations about portfolio structure.

    These are NOT decisions.
    """

    flags = []

    largest_position = safe_float(
        portfolio.get(
            "largest_position_pct",
            0,
        )
    )

    if largest_position > 25:

        flags.append(
            "LARGE_POSITION"
        )

    if largest_position > 40:

        flags.append(
            "HIGH_CONCENTRATION"
        )

    if safe_float(
        portfolio.get(
            "etf_count",
            0,
        )
    ) > 0:

        flags.append(
            "ETF_EXPOSURE_PRESENT"
        )

    if safe_float(
        portfolio.get(
            "cash",
            0,
        )
    ) > 0:

        flags.append(
            "CASH_PRESENT"
        )

    return flags


# ============================================================
# Main context builder
# ============================================================

def build_ai_decision_context(
    portfolio: Any = None,
    candidate_decisions: Any = None,
    recommendation_intelligence: Any = None,
    sector_analysis: Any = None,
    capital_allocation: Any = None,
    capital_summary: Any = None,
    portfolio_summary: Any = None,
) -> dict:
    """
    Build the complete AI Decision Context.

    Parameters
    ----------
    portfolio:
        Preferred portfolio input.

    candidate_decisions:
        Existing rules-based decisions.

    recommendation_intelligence:
        Existing recommendation intelligence output.

    sector_analysis:
        Existing sector analysis output.

    capital_allocation:
        Existing capital allocator output.

    capital_summary:
        Existing capital allocator summary.

    portfolio_summary:
        Legacy alias for portfolio.

    Returns
    -------
    dict
        Fully serialisable AI Decision Context.
    """

    # --------------------------------------------------------
    # Backward compatibility
    # --------------------------------------------------------

    if portfolio is None:

        portfolio = portfolio_summary

    # --------------------------------------------------------
    # Existing portfolio
    # --------------------------------------------------------

    portfolio_context = build_portfolio_context(
        portfolio=portfolio,
        sector_analysis=sector_analysis,
        capital_allocation=capital_allocation,
        capital_summary=capital_summary,
    )

    # --------------------------------------------------------
    # Holdings
    # --------------------------------------------------------

    holdings_lookup = build_holdings_lookup(
        portfolio
    )

    # --------------------------------------------------------
    # Recommendation intelligence
    # --------------------------------------------------------

    intelligence_lookup = build_intelligence_lookup(
        recommendation_intelligence
    )

    # --------------------------------------------------------
    # Candidate decisions
    # --------------------------------------------------------

    candidates = normalise_records(
        candidate_decisions
    )

    candidate_contexts = []

    for candidate in candidates:

        candidate_context = build_candidate_context(
            candidate=candidate,
            intelligence_lookup=intelligence_lookup,
            portfolio_holdings=holdings_lookup,
        )

        if candidate_context is not None:

            candidate_contexts.append(
                candidate_context
            )

    # --------------------------------------------------------
    # Portfolio flags
    # --------------------------------------------------------

    portfolio_flags = build_portfolio_flags(
        portfolio_context[
            "portfolio"
        ]
    )

    # --------------------------------------------------------
    # Final context
    # --------------------------------------------------------

    context = {

        "context_version":
            "1.1",

        "purpose":
            "Portfolio-aware AI assessment of existing rules-based decisions",

        "portfolio":
            portfolio_context[
                "portfolio"
            ],

        "holdings":
            portfolio_context[
                "holdings"
            ],

        "sectors":
            portfolio_context[
                "sectors"
            ],

        "capital":
            portfolio_context[
                "capital"
            ],

        "capital_allocation":
            portfolio_context[
                "capital_allocation"
            ],

        "portfolio_flags":
            portfolio_flags,

        "candidates":
            candidate_contexts,

        "governance": {

            "hold_is_default":
                True,

            "ai_must_not_recalculate_scores":
                True,

            "ai_must_not_allocate_capital":
                True,

            "ai_must_preserve_stock_etf_distinction":
                True,

            "ai_must_explain_overrides":
                True,

            "ai_must_not_invent_missing_evidence":
                True,

            "existing_rules_based_decision_is_input":
                True,

            "historical_reliability_is_supporting_evidence":
                True,

            "recommendation_evidence_snapshot_is_preferred":
                True,

            "legacy_candidate_fields_are_valid_fallback":
                True,
        },
    }

    return clean_value(
        context
    )


# ============================================================
# Convenience helper
# ============================================================

def get_candidate_context(
    context: Any,
    ticker: str,
) -> dict | None:
    """
    Retrieve one candidate context from a completed AI context.
    """

    if not isinstance(
        context,
        dict,
    ):

        return None

    ticker = clean_ticker(
        ticker
    )

    for candidate in context.get(
        "candidates",
        [],
    ):

        if not isinstance(
            candidate,
            dict,
        ):

            continue

        if clean_ticker(
            candidate.get(
                "ticker",
                "",
            )
        ) == ticker:

            return candidate

    return None


# ============================================================
# Structural validation
# ============================================================

def validate_ai_decision_context(
    context: Any,
) -> tuple[bool, list[str]]:
    """
    Validate the structure of an AI Decision Context.

    This validates the DATA CONTRACT only.

    It does not validate whether an investment decision is correct.
    """

    errors = []

    if not isinstance(
        context,
        dict,
    ):

        return (
            False,
            [
                "Context is not a dictionary"
            ],
        )

    required_sections = [
        "context_version",
        "portfolio",
        "holdings",
        "sectors",
        "capital",
        "capital_allocation",
        "portfolio_flags",
        "candidates",
        "governance",
    ]

    for section in required_sections:

        if section not in context:

            errors.append(
                f"Missing context section: {section}"
            )

    if not isinstance(
        context.get(
            "portfolio",
            {},
        ),
        dict,
    ):

        errors.append(
            "Portfolio section must be a dictionary"
        )

    if not isinstance(
        context.get(
            "holdings",
            [],
        ),
        list,
    ):

        errors.append(
            "Holdings section must be a list"
        )

    if not isinstance(
        context.get(
            "candidates",
            [],
        ),
        list,
    ):

        errors.append(
            "Candidates section must be a list"
        )

    # --------------------------------------------------------
    # Candidate validation
    # --------------------------------------------------------

    candidates = context.get(
        "candidates",
        [],
    )

    for index, candidate in enumerate(
        candidates
    ):

        if not isinstance(
            candidate,
            dict,
        ):

            errors.append(
                f"Candidate {index} is not a dictionary"
            )

            continue

        ticker = candidate.get(
            "ticker"
        )

        if not ticker:

            errors.append(
                f"Candidate {index} has no ticker"
            )

        asset_type = candidate.get(
            "asset_type"
        )

        if asset_type not in VALID_ASSET_TYPES:

            errors.append(
                f"Candidate {index} has invalid asset type: "
                f"{asset_type}"
            )

        decision = candidate.get(
            "rules_based_decision",
            {},
        )

        if not isinstance(
            decision,
            dict,
        ):

            errors.append(
                f"Candidate {index} rules_based_decision "
                f"must be a dictionary"
            )

        else:

            action = normalise_action(
                decision.get(
                    "action",
                    "HOLD",
                )
            )

            if action not in VALID_ACTIONS:

                errors.append(
                    f"Candidate {index} has invalid action: "
                    f"{action}"
                )

        evidence = candidate.get(
            "recommendation_evidence",
            {},
        )

        if not isinstance(
            evidence,
            dict,
        ):

            errors.append(
                f"Candidate {index} recommendation_evidence "
                f"must be a dictionary"
            )

    return (
        len(errors) == 0,
        errors,
    )


# ============================================================
# Module test
# ============================================================

if __name__ == "__main__":

    print(
        "AI Decision Context Builder"
    )

    context = build_ai_decision_context()

    valid, errors = (
        validate_ai_decision_context(
            context
        )
    )

    print(
        f"Context valid: {valid}"
    )

    if errors:

        for error in errors:

            print(
                f"ERROR: {error}"
            )

    else:

        print(
            "Context structure is valid."
        )

    print(
        f"Candidates: "
        f"{len(context.get('candidates', []))}"
    )