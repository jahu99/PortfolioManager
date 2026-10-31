"""
Portfolio Reallocation Audit

Purpose
-------
Provide an explainable, read-only audit of the Portfolio Reallocation
Engine's existing decisions.

This module MUST NOT:
- change portfolio decisions
- change destination eligibility
- change allocation weights
- change capital allocations
- change funding priorities
- recalculate investment scores
- introduce new governance

It only explains the outputs already produced by
analysis.portfolio_recalibration.

The audit distinguishes:

1. Destination candidates considered by the engine.
2. Destinations that passed governance.
3. Destinations selected for meaningful deployment.
4. Destinations that actually received capital.
5. Funding sources that actually supplied capital.
6. Capital that remained unallocated.

All explanations are based on values already calculated by the
Portfolio Reallocation Engine.
"""

import pandas as pd


def _safe_float(value, default=0.0):
    """Safely convert a value to float."""
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


def _clean_ticker(value):
    """Normalise a ticker for audit matching."""
    if value is None:
        return ""

    return str(value).strip().upper()


def _normalise_action(value):
    """Normalise a decision/action."""
    if value is None:
        return ""

    return str(value).strip().upper()


def build_reallocation_audit(
    destinations,
    eligible_destinations,
    deployment_destinations,
    destination_allocations,
    funding_candidates,
    reallocation_df,
    summary,
    min_destination_score,
    min_trade_value,
    max_destination_share,
    max_destination_count,
):
    """
    Build a read-only audit of the Portfolio Reallocation result.

    Parameters
    ----------
    destinations:
        All candidate destinations considered by the engine before
        allocation eligibility filtering.

    eligible_destinations:
        Destinations that passed the engine's allocation-capacity
        eligibility test.

    deployment_destinations:
        Destinations selected for meaningful deployment.

    destination_allocations:
        Final capital allocation calculated by the engine.

    funding_candidates:
        Funding sources actually authorised by the engine.

    reallocation_df:
        Final transaction DataFrame produced by the engine.

    summary:
        Existing engine summary.

    Governance parameters are supplied by the caller so this module
    does not maintain a second copy of production configuration.

    Returns
    -------
    dict
        {
            "destination_audit": DataFrame,
            "funding_audit": DataFrame,
            "summary": dict
        }

    This function is deliberately side-effect free.
    """



    destinations = destinations or []
    eligible_destinations = eligible_destinations or []
    deployment_destinations = deployment_destinations or []
    funding_candidates = funding_candidates or []

    destination_allocations = (
        destination_allocations or {}
    )

    if reallocation_df is None:
        reallocation_df = pd.DataFrame()

    if summary is None:
        summary = {}

    # ============================================================
    # ACTUAL TRANSACTION TOTALS
    # ============================================================
    # Audit actual generated transactions separately from the
    # engine's planned destination allocations and funding limits.

    actual_destination_allocations = {}
    actual_source_releases = {}

    if not reallocation_df.empty:
        for _, transaction in reallocation_df.iterrows():
            amount_value = transaction.get(
                "Reallocated Capital",
                None
            )

            if amount_value is None or pd.isna(amount_value):
                amount_value = transaction.get(
                    "Released Capital",
                    0
                )

            amount = _safe_float(amount_value)

            if amount <= 0:
                continue

            destination_ticker = _clean_ticker(
                transaction.get("Destination Ticker", "")
            )
            source_ticker = _clean_ticker(
                transaction.get("Source Ticker", "")
            )

            if destination_ticker:
                actual_destination_allocations[
                    destination_ticker
                ] = (
                    actual_destination_allocations.get(
                        destination_ticker, 0.0
                    ) + amount
                )

            if source_ticker:
                actual_source_releases[source_ticker] = (
                    actual_source_releases.get(
                        source_ticker, 0.0
                    ) + amount
                )

    actual_destination_allocations = {
        ticker: round(amount, 2)
        for ticker, amount in actual_destination_allocations.items()
    }
    actual_source_releases = {
        ticker: round(amount, 2)
        for ticker, amount in actual_source_releases.items()
    }

    # ============================================================
    # LOOKUPS
    # ============================================================

    eligible_lookup = {
        _clean_ticker(
            destination.get("Ticker", "")
        ): destination
        for destination in eligible_destinations
    }

    deployment_lookup = {
        _clean_ticker(
            destination.get("Ticker", "")
        ): destination
        for destination in deployment_destinations
    }

    funding_lookup = {
        _clean_ticker(
            candidate.get("Ticker", "")
        ): candidate
        for candidate in funding_candidates
    }

    # ============================================================
    # DESTINATION AUDIT
    # ============================================================

    destination_rows = []

    for destination in destinations:

        ticker = _clean_ticker(
            destination.get("Ticker", "")
        )

        if not ticker:
            continue

        audit_destination = eligible_lookup.get(
            ticker,
            destination
        )
                
        score = _safe_float(
            destination.get(
                "Investment Score",
                0
            )
        )

        final_decision = _normalise_action(
            destination.get(
                "Final Decision",
                ""
            )
        )

        position_capacity = _safe_float(
            audit_destination.get(
                "Position Capacity",
                0
            )
        )

        allocation_capacity = _safe_float(
            audit_destination.get(
                "Allocation Capacity",
                0
            )
        )

        allocation_weight = _safe_float(
            audit_destination.get(
                "Allocation Weight",
                0
            )
        )

        sector_exposure_raw = audit_destination.get(
            "Sector Exposure %",
            destination.get(
                "Sector Exposure %",
                None
            )
        )

        sector_exposure = None

        if sector_exposure_raw is not None:
            try:
                if not pd.isna(sector_exposure_raw):
                    sector_exposure = float(
                        sector_exposure_raw
                    )
            except (TypeError, ValueError):
                sector_exposure = None

        structural_risk = audit_destination.get(
            "Structural Risk",
            destination.get(
                "Structural Risk",
                "LOW"
            )
        )

        structural_risk_multiplier = _safe_float(
            audit_destination.get(
                "Structural Risk Multiplier",
                destination.get(
                    "Structural Risk Multiplier",
                    1.0
                )
            ),
            1.0
        )

        planned_allocation = _safe_float(
            destination_allocations.get(
                ticker,
                0
            )
        )

        allocation = actual_destination_allocations.get(
            ticker,
            0.0
        )

        is_eligible = (
            ticker in eligible_lookup
        )

        is_selected = (
            ticker in deployment_lookup
        )

        # --------------------------------------------------------
        # Determine the actual stage reached by the destination.
        # --------------------------------------------------------

        if score < min_destination_score:

            status = "EXCLUDED"

            reason = (
                f"Investment Score {score:.1f} is below "
                f"minimum destination score "
                f"{min_destination_score:.1f}"
            )

        elif not is_eligible:

            status = "EXCLUDED"

            reason = (
                f"Allocation Capacity £{allocation_capacity:.2f} "
                f"is below the minimum trade value of "
                f"£{min_trade_value:.2f}"
            )

        elif not is_selected:

            status = "NOT SELECTED"

            reason = (
                "Passed destination eligibility but was outside "
                "the meaningful deployment set"
            )

        elif allocation <= 0:

            status = "NO ALLOCATION"

            reason = (
                "Selected for deployment but no capital was "
                "ultimately allocated"
            )

        elif allocation < min_trade_value:

            status = "NO ALLOCATION"

            reason = (
                f"Calculated allocation £{allocation:.2f} is below "
                f"the minimum trade value of "
                f"£{min_trade_value:.2f}"
            )

        else:

            status = "ALLOCATED"

            reason = (
                "Passed destination governance and received "
                "capital"
            )

        # --------------------------------------------------------
        # Allocation constraint explanation.
        # --------------------------------------------------------

        constraint_reason = ""

        if allocation > 0:

            max_destination_allocation = (
                _safe_float(
                    summary.get(
                        "Total Released",
                        0
                    )
                )
                * _safe_float(
                    max_destination_share,
                    0.35
                )
            )

            if (
                max_destination_allocation > 0
                and allocation
                >= round(
                    max_destination_allocation,
                    2
                )
            ):
                constraint_reason = (
                    f"Allocation subject to maximum destination "
                    f"share of "
                    f"{max_destination_share * 100:.0f}%"
                )

        if not constraint_reason and allocation_capacity > 0:

            if allocation >= allocation_capacity:

                constraint_reason = (
                    "Allocation constrained by position/sector "
                    "capacity"
                )

        destination_rows.append(
            {
                "Ticker": ticker,
                "Name": destination.get(
                    "Name",
                    ticker
                ),
                "Final Decision": final_decision,
                "Investment Score": round(
                    score,
                    2
                ),
                "Risk Score": destination.get(
                    "Risk Score"
                ),
                "Risk Score Available": bool(
                    destination.get(
                        "Risk Score Available",
                        False
                    )
                ),
                "Risk Score Status": destination.get(
                    "Risk Score Status",
                    "UNKNOWN / NOT SCORED"
                ),
                "Sector": destination.get(
                    "Sector",
                    ""
                ),
                "Sector Exposure %": (
                    round(sector_exposure, 2)
                    if sector_exposure is not None
                    else None
                ),
                "Position Capacity": round(
                    position_capacity,
                    2
                ),
                "Allocation Capacity": round(
                    allocation_capacity,
                    2
                ),
                "Allocation Weight": round(
                    allocation_weight,
                    2
                ),
                "Structural Risk": structural_risk,
                "Structural Risk Multiplier": round(
                    structural_risk_multiplier,
                    2
                ),
                "Selected For Deployment": is_selected,
                "Planned Allocation": round(
                    planned_allocation,
                    2
                ),
                "Allocated Capital": round(
                    allocation,
                    2
                ),
                "Status": status,
                "Reason": reason,
                "Constraint": constraint_reason,
            }
        )

    destination_audit = pd.DataFrame(
        destination_rows
    )

    if not destination_audit.empty:

        destination_audit = (
            destination_audit.sort_values(
                by=[
                    "Status",
                    "Investment Score",
                    "Ticker"
                ],
                ascending=[
                    True,
                    False,
                    True
                ]
            )
            .reset_index(drop=True)
        )

    # ============================================================
    # FUNDING AUDIT
    # ============================================================

    funding_rows = []

    for ticker, candidate in funding_lookup.items():

        source_action = _normalise_action(
            candidate.get(
                "Final Decision",
                ""
            )
        )

        current_value = _safe_float(
            candidate.get(
                "Current Value",
                0
            )
        )

        permitted_release_percent = _safe_float(
            candidate.get(
                "Permitted Release %",
                0
            )
        )

        permitted_release_capital = _safe_float(
            current_value
            * permitted_release_percent
            / 100.0
        )

        if source_action == "CASH":
            permitted_release_capital = current_value

        # This is the amount evidenced by generated transactions,
        # not the maximum amount the source was permitted to release.
        released_capital = actual_source_releases.get(
            ticker,
            0.0
        )

        funding_rows.append(
            {
                "Source Ticker": ticker,
                "Source Action": (
                    "CONTRIBUTE CASH"
                    if source_action == "CASH"
                    else source_action
                ),
                "Current Value": round(
                    current_value,
                    2
                ),
                "Permitted Release %": round(
                    permitted_release_percent,
                    2
                ),
                "Permitted Release Capital": round(
                    permitted_release_capital,
                    2
                ),
                "Released Capital": round(
                    released_capital,
                    2
                ),
                "Funding Status": (
                    "ACTUALLY FUNDED"
                    if released_capital > 0
                    else "NO ACTUAL RELEASE"
                ),
                "Funding Priority": round(
                    _safe_float(
                        candidate.get(
                            "Funding Priority",
                            0
                        )
                    ),
                    2
                ),
                "Authorised Destination": (
                    candidate.get(
                        "Authorised Destination",
                        ""
                    )
                ),
                "Funding Reason": candidate.get(
                    "Funding Reason",
                    ""
                ),
            }
        )

    funding_audit = pd.DataFrame(
        funding_rows
    )

    if not funding_audit.empty:

        funding_audit = (
            funding_audit.sort_values(
                by=[
                    "Funding Priority",
                    "Source Ticker"
                ],
                ascending=[
                    False,
                    True
                ]
            )
            .reset_index(drop=True)
        )

    # ============================================================
    # TRANSACTION SUMMARY
    # ============================================================

    transaction_count = 0

    if not reallocation_df.empty:
        transaction_count = len(
            reallocation_df
        )

    allocated_destination_count = sum(
        amount >= min_trade_value
        for amount in actual_destination_allocations.values()
    )

    excluded_destination_count = 0

    if not destination_audit.empty:

        excluded_destination_count = int(
            (
                destination_audit["Status"]
                == "EXCLUDED"
            ).sum()
        )

    not_selected_count = 0

    if not destination_audit.empty:

        not_selected_count = int(
            (
                destination_audit["Status"]
                == "NOT SELECTED"
            ).sum()
        )

    no_allocation_count = 0

    if not destination_audit.empty:

        no_allocation_count = int(
            destination_audit["Status"]
            .isin(
                [
                    "NO ALLOCATION"
                ]
            ).sum()
        )

    audit_summary = {
        "Total Released": round(
            _safe_float(
                summary.get(
                    "Total Released",
                    0
                )
            ),
            2
        ),
        "Total Reallocated": round(
            _safe_float(
                summary.get(
                    "Total Reallocated",
                    0
                )
            ),
            2
        ),
        "Unallocated Capital": round(
            _safe_float(
                summary.get(
                    "Unallocated Capital",
                    0
                )
            ),
            2
        ),
        "Reconciliation Variance": round(
            _safe_float(
                summary.get(
                    "Reconciliation Variance",
                    0
                )
            ),
            2
        ),
        "Reconciliation Status": str(
            summary.get(
                "Reconciliation Status",
                "UNAVAILABLE"
            ) or "UNAVAILABLE"
        ),
        "Exposure Denominator": round(
            _safe_float(
                summary.get(
                    "Exposure Denominator",
                    0
                )
            ),
            2
        ),
        "Funding Sources": sum(
            amount > 0
            for amount in actual_source_releases.values()
        ),
        "Funding Candidates": len(
            funding_rows
        ),
        "Destination Candidates": len(
            destination_rows
        ),
        "Eligible Destinations": len(
            eligible_destinations
        ),
        "Selected Destinations": len(
            deployment_destinations
        ),
        "Allocated Destinations": (
            allocated_destination_count
        ),
        "Excluded Destinations": (
            excluded_destination_count
        ),
        "Not Selected Destinations": (
            not_selected_count
        ),
        "No Allocation Destinations": (
            no_allocation_count
        ),
        "Transactions": transaction_count,
        "Maximum Destinations": (
            max_destination_count
        ),
        "Maximum Destination Share": (
            max_destination_share
        ),
        "Minimum Destination Score": (
            min_destination_score
        ),
        "Minimum Trade Value": (
            min_trade_value
        ),
    }

    return {
        "destination_audit": destination_audit,
        "funding_audit": funding_audit,
        "summary": audit_summary,
    }
