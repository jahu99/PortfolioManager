
"""
BUY / BUY MORE Decision Diagnostic

Purpose
-------
Run the existing production pipeline and inspect only BUY NEW and
BUY MORE candidates after the complete governed decision chain.

This is a diagnostic test only.

It does not:
    - change production thresholds
    - change scoring weights
    - alter learning
    - alter portfolio holdings
    - allocate capital
    - execute trades

The test temporarily intercepts the production call to
generate_final_portfolio_decisions() so that the exact inputs already
created by main.py are captured.

Recommendation Intelligence evidence is read directly from the
production Recommendation Intelligence input captured at the final
decision boundary. This prevents upstream learning evidence from
being lost when the final decision dataframe does not expose every
Recommendation Intelligence field.
"""

from __future__ import annotations

import pandas as pd

import main as production_main

from analysis.final_portfolio_decision import (
    generate_final_portfolio_decisions as real_final_decisions,
)


# ============================================================
# Helpers
# ============================================================

def safe_text(
    value,
    default="",
):
    """Safely convert a value to clean text."""

    if value is None:
        return default

    try:
        if pd.isna(value):
            return default
    except Exception:
        pass

    try:
        text = str(value).strip()
    except Exception:
        return default

    return text if text else default


def safe_float(
    value,
    default=0.0,
):
    """Safely convert a scalar value to float."""

    try:
        if value is None:
            return default

        if isinstance(
            value,
            (list, tuple, set, dict),
        ):
            return default

        if pd.isna(value):
            return default

        return float(value)

    except (
        TypeError,
        ValueError,
    ):
        return default


def get_first(
    row,
    *names,
    default=None,
):
    """Return the first usable value from a pandas Series."""

    for name in names:
        if name not in row.index:
            continue

        value = row[name]

        if value is None:
            continue

        try:
            if pd.isna(value):
                continue
        except Exception:
            pass

        return value

    return default


def normalise_ticker(value):
    """Normalise a ticker symbol for comparison."""

    return safe_text(
        value,
        "",
    ).upper()


def build_intelligence_lookup(
    recommendation_intelligence,
):
    """
    Build a ticker-indexed lookup from the Recommendation Intelligence
    dataframe captured from the production pipeline.
    """

    if not isinstance(
        recommendation_intelligence,
        pd.DataFrame,
    ):
        return {}

    if recommendation_intelligence.empty:
        return {}

    if "Ticker" not in recommendation_intelligence.columns:
        return {}

    lookup = {}

    for _, row in recommendation_intelligence.iterrows():

        ticker = normalise_ticker(
            row.get(
                "Ticker",
                "",
            )
        )

        if not ticker:
            continue

        lookup[ticker] = row.to_dict()

    return lookup


# ============================================================
# Diagnostic categorisation
# ============================================================

def classify_result(row):
    """
    Identify the principal reason a BUY NEW / BUY MORE proposal
    was not approved.
    """

    final_decision = safe_text(
        get_first(
            row,
            "Final Decision",
            "final_decision",
            default="",
        )
    ).upper()

    reconciliation_status = safe_text(
        get_first(
            row,
            "Reconciliation",
            "Reconciliation Status",
            "reconciliation_status",
            default="",
        )
    ).upper()

    decision_status = safe_text(
        get_first(
            row,
            "Decision Status",
            "decision_status",
            default="",
        )
    ).upper()

    llm_review = safe_text(
        get_first(
            row,
            "LLM Review",
            "LLM Assessment",
            "llm_review",
            default="",
        )
    ).upper()

    evidence_support = safe_text(
        get_first(
            row,
            "Evidence Support",
            "Decision Support",
            "Decision_Support",
            default="",
        )
    ).upper()

    evidence_score = safe_float(
        get_first(
            row,
            "Evidence Score",
            "evidence_score",
            default=0,
        )
    )

    reason = safe_text(
        get_first(
            row,
            "Reconciliation Reason",
            "Reason",
            default="",
        )
    )

    # --------------------------------------------------------
    # Approved
    # --------------------------------------------------------

    if final_decision in {
        "BUY NEW",
        "BUY MORE",
    }:
        return "APPROVED", reason

    # --------------------------------------------------------
    # LLM challenge / review
    # --------------------------------------------------------

    if (
        llm_review in {
            "CHALLENGE",
            "REJECT",
        }
        or
        reconciliation_status in {
            "REVIEW REQUIRED",
            "CHALLENGE",
        }
    ):
        return "LLM / GOVERNANCE REVIEW", reason

    # --------------------------------------------------------
    # Weak deterministic evidence
    # --------------------------------------------------------

    if (
        evidence_support == "NOT SUPPORTED"
        or
        evidence_score < 60
    ):
        return "WEAK DETERMINISTIC EVIDENCE", reason

    # --------------------------------------------------------
    # Final fallback
    # --------------------------------------------------------

    if decision_status:
        return decision_status, reason

    return "OTHER", reason


# ============================================================
# Captured production call
# ============================================================

captured_inputs = {}
captured_result = None


def intercepted_final_decisions(
    *,
    portfolio_summary,
    portfolio_decisions,
    portfolio_ai_review,
    portfolio_manager_review,
    portfolio_health,
    capital_allocation,
    recommendation_intelligence=None,
    **kwargs,
):
    """
    Intercept the production call, capture its exact inputs,
    then delegate immediately to the real implementation.
    """

    global captured_result

    captured_inputs.clear()

    captured_inputs.update(
        {
            "portfolio_summary": portfolio_summary,
            "portfolio_decisions": portfolio_decisions,
            "portfolio_ai_review": portfolio_ai_review,
            "portfolio_manager_review": portfolio_manager_review,
            "portfolio_health": portfolio_health,
            "capital_allocation": capital_allocation,
            "recommendation_intelligence": (
                recommendation_intelligence
            ),
        }
    )

    captured_result = real_final_decisions(
        portfolio_summary=portfolio_summary,
        portfolio_decisions=portfolio_decisions,
        portfolio_ai_review=portfolio_ai_review,
        portfolio_manager_review=portfolio_manager_review,
        portfolio_health=portfolio_health,
        capital_allocation=capital_allocation,
        recommendation_intelligence=(
            recommendation_intelligence
        ),
        **kwargs,
    )

    return captured_result


# ============================================================
# Main diagnostic
# ============================================================

def main():
    """Run the BUY / BUY MORE governed decision diagnostic."""

    print()
    print("=" * 100)
    print("BUY / BUY MORE GOVERNED DECISION DIAGNOSTIC")
    print("=" * 100)
    print()

    # --------------------------------------------------------
    # Intercept only the final portfolio decision call.
    # --------------------------------------------------------

    original_function = (
        production_main.generate_final_portfolio_decisions
    )

    production_main.generate_final_portfolio_decisions = (
        intercepted_final_decisions
    )

    try:
        production_main.main()

    finally:
        # Always restore production behaviour.
        production_main.generate_final_portfolio_decisions = (
            original_function
        )

    # --------------------------------------------------------
    # Validate capture.
    # --------------------------------------------------------

    required = {
        "portfolio_summary",
        "portfolio_decisions",
        "portfolio_ai_review",
        "portfolio_manager_review",
        "portfolio_health",
        "capital_allocation",
        "recommendation_intelligence",
    }

    missing = (
        required
        -
        set(captured_inputs.keys())
    )

    if missing:
        raise RuntimeError(
            "Final decision diagnostic failed to capture "
            f"production inputs: {sorted(missing)}"
        )

    if captured_result is None:
        raise RuntimeError(
            "Final portfolio decision result was not captured."
        )

    # --------------------------------------------------------
    # Recommendation Intelligence lookup.
    #
    # This is the authoritative source for learning evidence
    # used by this diagnostic.
    # --------------------------------------------------------

    recommendation_intelligence = (
        captured_inputs[
            "recommendation_intelligence"
        ]
    )

    intelligence_lookup = build_intelligence_lookup(
        recommendation_intelligence
    )

    print()
    print("=" * 100)
    print("CAPTURED RECOMMENDATION INTELLIGENCE")
    print("=" * 100)
    print()

    print(
        "Intelligence rows captured:",
        len(intelligence_lookup),
    )

    if (
        isinstance(
            recommendation_intelligence,
            pd.DataFrame,
        )
        and
        not recommendation_intelligence.empty
    ):
        preview_columns = [
            "Ticker",
            "Signal",
            "Investment Score",
            "Historical Signal Observations",
            "Historical Signal Reliability",
            "Historical Signal Average Return %",
            "Score Bucket",
            "Score Bucket Observations",
            "Score Bucket Average Return %",
            "Score Bucket Win Rate %",
            "Preferred Learning Horizon",
            "Learning Horizon Status",
        ]

        preview_columns = [
            column
            for column in preview_columns
            if column in recommendation_intelligence.columns
        ]

        if preview_columns:
            print(
                recommendation_intelligence[
                    preview_columns
                ].head(10).to_string(
                    index=False
                )
            )

    # --------------------------------------------------------
    # Normalise final decision result.
    # --------------------------------------------------------

    if isinstance(
        captured_result,
        pd.DataFrame,
    ):
        df = captured_result.copy()

    elif isinstance(
        captured_result,
        list,
    ):
        df = pd.DataFrame(
            captured_result
        )

    else:
        raise TypeError(
            "Unexpected final portfolio decision result type: "
            f"{type(captured_result)}"
        )

    if df.empty:
        print(
            "FINAL DECISION DATAFRAME IS EMPTY"
        )
        return

    # --------------------------------------------------------
    # Identify proposal column.
    # --------------------------------------------------------

    proposal_column = None

    for candidate in [
        "Proposed Action",
        "Proposed_Action",
        "Action",
    ]:
        if candidate in df.columns:
            proposal_column = candidate
            break

    if proposal_column is None:
        raise RuntimeError(
            "Could not find Proposed Action column."
        )

    # --------------------------------------------------------
    # Select BUY NEW / BUY MORE candidates.
    # --------------------------------------------------------

    proposals = (
        df[
            df[proposal_column]
            .astype(str)
            .str.upper()
            .str.startswith(
                (
                    "BUY NEW",
                    "BUY MORE",
                )
            )
        ]
        .copy()
    )

    print()
    print("=" * 100)
    print(
        f"BUY CANDIDATES FOUND: {len(proposals)}"
    )
    print("=" * 100)
    print()

    if proposals.empty:
        print(
            "No BUY NEW / BUY MORE proposals found."
        )
        return

    # --------------------------------------------------------
    # Build detailed diagnostic.
    # --------------------------------------------------------

    diagnostic_rows = []

    for _, row in proposals.iterrows():

        ticker = normalise_ticker(
            get_first(
                row,
                "Ticker",
                "ticker",
                default="UNKNOWN",
            )
        )

        proposed_action = safe_text(
            get_first(
                row,
                proposal_column,
                default="",
            )
        )

        result_class, reason = classify_result(
            row
        )

        # ----------------------------------------------------
        # Use Recommendation Intelligence directly for learning
        # evidence rather than relying on fields propagated into
        # the final decision dataframe.
        # ----------------------------------------------------

        intelligence = intelligence_lookup.get(
            ticker,
            {}
        )

        investment_score = safe_float(
            intelligence.get(
                "Investment Score",
                get_first(
                    row,
                    "Investment Score",
                    default=0,
                ),
            )
        )

        signal = safe_text(
            intelligence.get(
                "Signal",
                get_first(
                    row,
                    "Signal",
                    default="",
                ),
            )
        )

        diagnostic_rows.append(
            {
                "Ticker": ticker,

                "Proposal": proposed_action,

                "Held": get_first(
                    row,
                    "Held?",
                    "Existing Holding",
                    "Existing_Holding",
                    default="",
                ),

                "Allocation %": safe_float(
                    get_first(
                        row,
                        "Current Allocation %",
                        "Portfolio Allocation %",
                        "Allocation %",
                        default=0,
                    )
                ),

                "Investment Score": investment_score,

                "Signal": signal,

                # ------------------------------------------------
                # Historical signal learning
                # ------------------------------------------------

                "Learning Observations": safe_float(
                    intelligence.get(
                        "Historical Signal Observations",
                        0,
                    )
                ),

                "Learning Reliability": safe_text(
                    intelligence.get(
                        "Historical Signal Reliability",
                        "",
                    )
                ),

                "Learning Avg Return %": safe_float(
                    intelligence.get(
                        "Historical Signal Average Return %",
                        0,
                    )
                ),

                # ------------------------------------------------
                # Investment-score bucket learning
                # ------------------------------------------------

                "Score Bucket": safe_text(
                    intelligence.get(
                        "Score Bucket",
                        "",
                    )
                ),

                "Score Bucket Observations": safe_float(
                    intelligence.get(
                        "Score Bucket Observations",
                        0,
                    )
                ),

                "Score Bucket Average Return %": safe_float(
                    intelligence.get(
                        "Score Bucket Average Return %",
                        0,
                    )
                ),

                "Score Bucket Win Rate %": safe_float(
                    intelligence.get(
                        "Score Bucket Win Rate %",
                        0,
                    )
                ),

                # ------------------------------------------------
                # Learning adjustment
                # ------------------------------------------------

                "Learning Adjustment": safe_float(
                    intelligence.get(
                        "Learning Adjustment",
                        0,
                    )
                ),

                "Learning Adjusted Score": safe_float(
                    intelligence.get(
                        "Learning Adjusted Score",
                        investment_score,
                    )
                ),

                "Preferred Learning Horizon": (
                    intelligence.get(
                        "Preferred Learning Horizon",
                        None,
                    )
                ),

                "Learning Horizon Status": safe_text(
                    intelligence.get(
                        "Learning Horizon Status",
                        "",
                    )
                ),

                # ------------------------------------------------
                # Final decision evidence
                # ------------------------------------------------

                "Evidence Score": safe_float(
                    get_first(
                        row,
                        "Evidence Score",
                        default=0,
                    )
                ),

                "Evidence Strength": get_first(
                    row,
                    "Evidence Strength",
                    default="",
                ),

                "Evidence Support": get_first(
                    row,
                    "Evidence Support",
                    "Decision Support",
                    default="",
                ),

                "Decision Confidence": safe_float(
                    get_first(
                        row,
                        "Decision Confidence",
                        "Deterministic Confidence",
                        "Confidence",
                        default=0,
                    )
                ),

                "LLM Review": get_first(
                    row,
                    "LLM Review",
                    "LLM Assessment",
                    default="",
                ),

                "LLM Confidence": safe_float(
                    get_first(
                        row,
                        "LLM Confidence",
                        default=0,
                    )
                ),

                "Reconciliation": get_first(
                    row,
                    "Reconciliation",
                    "Reconciliation Status",
                    default="",
                ),

                "Final Decision": get_first(
                    row,
                    "Final Decision",
                    default="",
                ),

                "Decision Status": get_first(
                    row,
                    "Decision Status",
                    default="",
                ),

                "Diagnostic Classification": (
                    result_class
                ),

                "Diagnostic Reason": reason,
            }
        )

    diagnostic = pd.DataFrame(
        diagnostic_rows
    )

    # --------------------------------------------------------
    # Detailed results.
    # --------------------------------------------------------

    print(
        diagnostic.to_string(
            index=False
        )
    )

    # --------------------------------------------------------
    # BUY NEW / BUY MORE summary.
    # --------------------------------------------------------

    print()
    print("=" * 100)
    print("BUY NEW / BUY MORE SUMMARY")
    print("=" * 100)
    print()

    for proposal_type in [
        "BUY NEW",
        "BUY MORE",
    ]:

        subset = diagnostic[
            diagnostic["Proposal"]
            .astype(str)
            .str.upper()
            .str.startswith(
                proposal_type
            )
        ]

        approved = subset[
            subset["Final Decision"]
            .astype(str)
            .str.upper()
            ==
            proposal_type
        ]

        rejected = subset[
            ~(
                subset["Final Decision"]
                .astype(str)
                .str.upper()
                ==
                proposal_type
            )
        ]

        challenged = subset[
            subset["LLM Review"]
            .astype(str)
            .str.upper()
            .isin(
                [
                    "CHALLENGE",
                    "REJECT",
                ]
            )
        ]

        print(
            proposal_type
        )

        print(
            f"  Candidates: {len(subset)}"
        )

        print(
            f"  Approved: {len(approved)}"
        )

        print(
            f"  Rejected / downgraded: "
            f"{len(rejected)}"
        )

        print(
            f"  LLM challenged: "
            f"{len(challenged)}"
        )

        if not subset.empty:

            print(
                "  Average Investment Score: "
                f"{subset['Investment Score'].mean():.2f}"
            )

            print(
                "  Average Evidence Score: "
                f"{subset['Evidence Score'].mean():.2f}"
            )

            print(
                "  Average Decision Confidence: "
                f"{subset['Decision Confidence'].mean():.2f}"
            )

            print(
                "  Average Score Bucket Observations: "
                f"{subset['Score Bucket Observations'].mean():.2f}"
            )

        print()

    # --------------------------------------------------------
    # Known governance cases.
    # --------------------------------------------------------

    print("=" * 100)
    print("KNOWN GOVERNANCE CASES")
    print("=" * 100)
    print()

    for ticker in [
        "CRDO",
        "ERO",
        "ANET",
        "PLTR",
        "GE",
    ]:

        match = diagnostic[
            diagnostic["Ticker"]
            .astype(str)
            .str.upper()
            ==
            ticker
        ]

        if match.empty:

            print(
                f"{ticker}: NOT PRESENT"
            )

            continue

        row = match.iloc[0]

        print(
            f"{ticker}: "
            f"{row['Proposal']} -> "
            f"{row['Final Decision']} | "
            f"{row['Diagnostic Classification']} | "
            f"{row['Diagnostic Reason']}"
        )

    # --------------------------------------------------------
    # Recommendation Intelligence validation.
    #
    # This explicitly confirms that the five known candidates
    # receive the expected upstream evidence.
    # --------------------------------------------------------

    print()
    print("=" * 100)
    print("RECOMMENDATION INTELLIGENCE VALIDATION")
    print("=" * 100)
    print()

    for ticker in [
        "CRDO",
        "ERO",
        "ANET",
        "PLTR",
        "GE",
    ]:

        intelligence = intelligence_lookup.get(
            ticker,
            {}
        )

        if not intelligence:

            print(
                f"{ticker}: "
                "Recommendation Intelligence NOT FOUND"
            )

            continue

        print(
            f"{ticker}: "
            f"Signal Obs="
            f"{safe_float(intelligence.get('Historical Signal Observations', 0)):.0f}, "
            f"Signal Reliability="
            f"{safe_text(intelligence.get('Historical Signal Reliability', ''))}, "
            f"Score Bucket="
            f"{safe_text(intelligence.get('Score Bucket', ''))}, "
            f"Score Bucket Obs="
            f"{safe_float(intelligence.get('Score Bucket Observations', 0)):.0f}, "
            f"Score Bucket Win Rate="
            f"{safe_float(intelligence.get('Score Bucket Win Rate %', 0)):.2f}%, "
            f"Preferred Horizon="
            f"{intelligence.get('Preferred Learning Horizon', '')}"
        )

    # --------------------------------------------------------
    # Final status.
    # --------------------------------------------------------

    print()
    print("=" * 100)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 100)
    print()

    print(
        "Production final decision function was restored."
    )

    print(
        "No production decision thresholds or scoring logic "
        "were modified by this test."
    )


if __name__ == "__main__":
    main()
