"""
Market & Event Intelligence shadow-mode analysis.

This module determines which portfolio candidates should receive
external intelligence assessment and normalises that intelligence
for reporting and later AI review.

It does NOT alter deterministic portfolio decisions.
"""

import pandas as pd

from data.market_intelligence import (
    collect_market_intelligence,
)

from analysis.security_classifier import classify_security


TARGET_ACTIONS = {
    "BUY NEW"
}


def _normalise_action(value):

    if value is None:
        return ""

    return str(value).upper().strip()


def _safe_value(
    row,
    *keys,
    default=None
):
    for key in keys:

        if key in row:

            value = row.get(key)

            if (
                value is not None
                and str(value).strip() != ""
            ):
                return value

    return default


def build_market_intelligence_universe(
    holdings,
    portfolio_decisions
):
    """
    Build the Market & Event Intelligence assessment universe.

    Includes:

    1. All current STOCK holdings
    2. BUY NEW STOCK candidates

    Excludes:

    - Cash balances
    - ETFs

    BUY MORE does not need separate handling because a valid
    BUY MORE recommendation must already be a current holding.

    The purpose is visibility and shadow-mode assessment only.
    """

    records = []

    # ========================================================
    # PORTFOLIO DECISION LOOKUP
    #
    # Enrich existing holdings with their authoritative
    # portfolio action and Investment Score.
    # ========================================================

    decision_lookup = {}

    if portfolio_decisions is not None:

        if isinstance(portfolio_decisions, list):
            decisions_df = pd.DataFrame(portfolio_decisions)
        else:
            decisions_df = portfolio_decisions.copy()

        if not decisions_df.empty:

            for _, decision_row in decisions_df.iterrows():

                decision_ticker = _safe_value(
                    decision_row,
                    "Ticker",
                    "ticker",
                    default=""
                )

                if not decision_ticker:
                    continue

                decision_ticker = str(
                    decision_ticker
                ).upper().strip()

                decision_lookup[decision_ticker] = {

                    "Current Portfolio Action": _normalise_action(
                        _safe_value(
                            decision_row,
                            "Final Decision",
                            "Final Action",
                            "Action",
                            "action",
                            default=""
                        )
                    ),

                    "Investment Score": _safe_value(
                        decision_row,
                        "Investment Score",
                        "investment_score",
                        default=None
                    ),

                }

    # ========================================================
    # CURRENT PORTFOLIO HOLDINGS
    # ========================================================

    if holdings is not None:

        if isinstance(
            holdings,
            list
        ):
            holdings_df = pd.DataFrame(
                holdings
            )

        else:
            holdings_df = holdings.copy()

        if not holdings_df.empty:

            for _, row in holdings_df.iterrows():

                ticker = _safe_value(
                    row,
                    "Ticker",
                    "ticker",
                    default=""
                )

                if not ticker:
                    continue

                ticker = str(
                    ticker
                ).upper().strip()

                # ------------------------------------------------
                # EXCLUDE CASH
                # ------------------------------------------------

                security_type = classify_security(
                    ticker,
                    _safe_value(
                        row,
                        "Name",
                        "name",
                        default=""
                    )
                )

                if security_type in {"CASH", "ETF"}:
                    continue

                decision_context = decision_lookup.get(
                    ticker,
                    {}
                )

                records.append(

                    {

                        "Ticker": ticker,

                        "Name": _safe_value(
                            row,
                            "Name",
                            "name",
                            default=""
                        ),

                        "Current Portfolio Action": decision_context.get(
                            "Current Portfolio Action",
                            ""
                        ),

                        "Existing Holding": "Yes",

                        "Investment Score": decision_context.get(
                            "Investment Score",
                            None
                        ),

                        "Allocation %": _safe_value(
                            row,
                            "Allocation %",
                            "allocation",
                            default=0
                        ),

                    }

                )

    # ========================================================
    # PORTFOLIO DECISIONS
    #
    # ADD BUY NEW STOCK CANDIDATES ONLY
    # ========================================================

    if portfolio_decisions is not None:

        if isinstance(
            portfolio_decisions,
            list
        ):
            decisions = pd.DataFrame(
                portfolio_decisions
            )

        else:
            decisions = portfolio_decisions.copy()

        if not decisions.empty:

            for _, row in decisions.iterrows():

                ticker = _safe_value(
                    row,
                    "Ticker",
                    "ticker",
                    default=""
                )

                if not ticker:
                    continue

                ticker = str(
                    ticker
                ).upper().strip()

                action = _normalise_action(
                    _safe_value(
                        row,
                        "Action",
                        "action",
                        default=""
                    )
                )

                # Only BUY NEW candidates are added here.
                if action != "BUY NEW":
                    continue

                # ------------------------------------------------
                # EXCLUDE ETFs
                # ------------------------------------------------

                security_type = classify_security(
                    ticker,
                    _safe_value(
                        row,
                        "Name",
                        "name",
                        default=""
                    )
                )

                if security_type == "ETF":
                    continue

                records.append(
                    {
                        "Ticker": ticker,

                        "Name": _safe_value(
                            row,
                            "Name",
                            "name",
                            default=""
                        ),

                        "Current Portfolio Action": action,

                        "Existing Holding": "No",

                        "Investment Score": _safe_value(
                            row,
                            "Investment Score",
                            "investment_score",
                            default=None
                        ),

                        "Allocation %": _safe_value(
                            row,
                            "Allocation %",
                            "allocation",
                            default=0
                        ),
                    }
                )

    # ========================================================
    # NO ASSESSMENT UNIVERSE
    # ========================================================

    if not records:
        return pd.DataFrame()

    universe = pd.DataFrame(
        records
    )

    # ========================================================
    # DEDUPLICATE
    #
    # HOLDINGS TAKE PRECEDENCE OVER BUY NEW RECORDS
    # ========================================================

    universe = universe.drop_duplicates(
        subset=["Ticker"],
        keep="first"
    )

    return universe

def assess_market_intelligence(
    holdings,
    portfolio_decisions,
    force_refresh=False
):
    """
    Collect Market & Event Intelligence for:

    - all current portfolio holdings
    - BUY NEW candidates

    This is shadow-mode intelligence only and does not alter
    deterministic portfolio decisions.
    """

    universe = (
        build_market_intelligence_universe(
            holdings,
            portfolio_decisions
        )
    )

    if universe.empty:

        return pd.DataFrame()

    intelligence_records = []

    for _, row in universe.iterrows():

        ticker = row["Ticker"]

        company_name = row.get(
            "Name",
            None
        )

        try:

            intelligence = (

                collect_market_intelligence(

                    ticker,

                    company_name=company_name,

                    force_refresh=force_refresh

                )
            )

            record = row.to_dict()

            # Preserve portfolio identity fields.
            # External intelligence must not overwrite
            # the portfolio's authoritative name/type.

            intelligence.pop(
                "Name",
                None
            )

            record.update(
                intelligence
            )

            intelligence_records.append(
                record
            )

        except Exception as exc:

            print(
                f"Market intelligence failed "
                f"for {ticker}: {exc}"
            )

            record = row.to_dict()

            record.update(
                {
                    "Source": "UNAVAILABLE",

                    "Analyst Recommendation":
                        "UNKNOWN",

                    "Analyst Mean Score":
                        None,

                    "Analyst Target Mean":
                        None,

                    "Analyst Target High":
                        None,

                    "Analyst Target Low":
                        None,

                    "Current Price":
                        None,

                    "Analyst Target Upside %":
                        None,


                    "Next Earnings Date":
                        None,

                    "Earnings Status":
                        "UNKNOWN",

                    "News Count":
                        0,

                    "News Headlines":
                        [],
                }
            )

            intelligence_records.append(
                record
            )

    if not intelligence_records:

        return pd.DataFrame()

    return pd.DataFrame(
        intelligence_records
    )
