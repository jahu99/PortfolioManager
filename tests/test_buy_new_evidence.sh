#!/bin/bash

# ============================================================
# BUY NEW Evidence Comparison Test
# ============================================================
#
# Purpose:
#   Compare the CURRENT BUY evidence calculation with the
#   proposed BUY NEW calculation without changing production
#   code, the database, or any report files.
#
# Run from the project root:
#
#   ./tests/test_buy_new_evidence.sh
#
# ============================================================

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

echo
echo "============================================================"
echo " BUY NEW Evidence Comparison Test"
echo "============================================================"
echo
echo "Project: $PROJECT_ROOT"
echo

# ------------------------------------------------------------
# Activate virtual environment if present
# ------------------------------------------------------------

if [ -f "$PROJECT_ROOT/.venv/bin/activate" ]; then
    source "$PROJECT_ROOT/.venv/bin/activate"
elif [ -f "$PROJECT_ROOT/venv/bin/activate" ]; then
    source "$PROJECT_ROOT/venv/bin/activate"
fi

# ------------------------------------------------------------
# Run the diagnostic in Python.
#
# IMPORTANT:
# This does NOT modify ai_decision_scoring.py.
# ------------------------------------------------------------

python - <<'PY'

import sys
from pathlib import Path

PROJECT_ROOT = Path.cwd()

print("Python:", sys.executable)
print()

# ============================================================
# Imports
# ============================================================

from agents import ai_decision_scoring as scoring


# ============================================================
# Proposed BUY NEW calculation
# ============================================================

def proposed_buy_new_evidence(context):
    """
    Proposed BUY NEW evidence calculation.

    This mirrors the proposed production change but exists
    only inside this test script.
    """

    investment_quality = scoring.clamp(
        scoring.get_learning_adjusted_score(
            context
        )
    )

    portfolio_fit = scoring.score_portfolio_fit(
        context
    )

    risk_fit = scoring.score_risk_fit(
        context
    )

    portfolio_adjustment = (
        portfolio_fit - 70.0
    )

    risk_adjustment = (
        risk_fit - 50.0
    )

    score = (
        investment_quality
        +
        portfolio_adjustment
        +
        risk_adjustment
    )

    return scoring.clamp(
        score
    )


# ============================================================
# Current calculation
# ============================================================

def current_buy_evidence(context):
    """
    Current production BUY evidence calculation.

    This deliberately calls the existing production function.
    """

    return scoring.calculate_buy_new_evidence(
        context
    )


# ============================================================
# Helper
# ============================================================

def get_value(context, *names, default=None):
    """
    Safely retrieve a value using the scoring module's
    existing value resolver.
    """

    for name in names:
        try:
            value = scoring.get_value(
                context,
                name,
                default=None,
            )

            if value is not None:
                return value

        except Exception:
            pass

    return default


def numeric(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


# ============================================================
# Candidate discovery
# ============================================================
#
# We deliberately use the existing final portfolio decisions
# snapshot so the test is based on real pipeline output rather
# than invented candidate data.
# ============================================================

import pandas as pd

snapshot_candidates = [
    PROJECT_ROOT / "data" / "final_portfolio_decisions_snapshot.csv",
]

snapshot = None

for path in snapshot_candidates:
    if path.exists() and path.stat().st_size > 0:
        try:
            snapshot = pd.read_csv(path)
            print("Using snapshot:")
            print(" ", path)
            print()
            break
        except Exception as exc:
            print(f"Could not read {path}: {exc}")

if snapshot is None:
    raise SystemExit(
        "ERROR: Could not find a usable "
        "data/final_portfolio_decisions_snapshot.csv"
    )


# ============================================================
# Find BUY NEW candidates
# ============================================================

action_column = None

for column in [
    "Proposed Action",
    "Action",
    "proposed_action",
    "action",
]:
    if column in snapshot.columns:
        action_column = column
        break

if action_column is None:
    raise SystemExit(
        "ERROR: Could not find an action column in the "
        "final portfolio decisions snapshot."
    )


buy_new = snapshot[
    snapshot[action_column]
    .astype(str)
    .str.strip()
    .str.upper()
    == "BUY NEW"
].copy()


# ============================================================
# Prefer the three candidates we are investigating.
# ============================================================

preferred = ["CBC", "ASND", "TRMK"]

preferred_buy_new = buy_new[
    buy_new.get(
        "Ticker",
        pd.Series(index=buy_new.index, dtype=str),
    )
    .astype(str)
    .str.upper()
    .isin(preferred)
]

if not preferred_buy_new.empty:
    candidates = preferred_buy_new
else:
    candidates = buy_new.head(10)


if candidates.empty:
    raise SystemExit(
        "ERROR: No BUY NEW candidates found in the snapshot."
    )


# ============================================================
# Build contexts
# ============================================================
#
# The snapshot contains the actual values produced by the
# pipeline. We construct the minimum scoring context needed
# by ai_decision_scoring.py.
#
# We do not write anything back to the project.
# ============================================================

def build_context(row):

    context = {}

    for column in snapshot.columns:

        value = row[column]

        if pd.isna(value):
            value = None

        context[column] = value

        # Also provide common lowercase aliases.
        context[
            column.lower()
            .replace(" ", "_")
            .replace("%", "pct")
        ] = value

    # Explicit canonical values used by the scoring module.

    ticker = get_value(
        context,
        "Ticker",
        "ticker",
        default="",
    )

    investment_score = get_value(
        context,
        "Investment Score",
        "investment_score",
        default=0,
    )

    action = get_value(
        context,
        "Proposed Action",
        "Action",
        "proposed_action",
        "action",
        default="BUY NEW",
    )

    context["Ticker"] = ticker
    context["ticker"] = ticker

    context["Action"] = action
    context["action"] = action

    context["Proposed Action"] = action
    context["proposed_action"] = action

    context["Investment Score"] = numeric(
        investment_score
    )

    context["investment_score"] = numeric(
        investment_score
    )

    return context


# ============================================================
# Run comparison
# ============================================================

print(
    "------------------------------------------------------------"
)
print("Results")
print(
    "------------------------------------------------------------"
)
print()

results = []

for _, row in candidates.iterrows():

    ticker = str(
        row.get("Ticker", "")
    ).strip().upper()

    context = build_context(row)

    print(f"Testing {ticker}")
    print("-" * 60)

    try:
        investment_score = scoring.get_investment_score(
            context
        )

        learning_adjusted_score = (
            scoring.get_learning_adjusted_score(
                context
            )
        )

        learning_adjustment = (
            scoring.get_learning_adjustment(
                context
            )
        )

        observations = (
            scoring.get_preferred_learning_observations(
                context
            )
        )

        learning_evidence = (
            scoring.score_learning_evidence(
                context
            )
        )

        bucket_evidence = (
            scoring.score_score_bucket_evidence(
                context
            )
        )

        portfolio_fit = (
            scoring.score_portfolio_fit(
                context
            )
        )

        risk_fit = (
            scoring.score_risk_fit(
                context
            )
        )

        current = current_buy_evidence(
            context
        )

        proposed = proposed_buy_new_evidence(
            context
        )

        difference = proposed - current

        print(
            f"Investment Score:          {investment_score:.2f}"
        )

        print(
            f"Learning Adjusted Score:   "
            f"{learning_adjusted_score:.2f}"
        )

        print(
            f"Learning Adjustment:       "
            f"{learning_adjustment:.2f}"
        )

        print(
            f"Historical Observations:   "
            f"{observations}"
        )

        print(
            f"Learning Evidence:         "
            f"{learning_evidence:.2f}"
        )

        print(
            f"Score Bucket Evidence:     "
            f"{bucket_evidence:.2f}"
        )

        print(
            f"Portfolio Fit:              "
            f"{portfolio_fit:.2f}"
        )

        print(
            f"Risk Fit:                   "
            f"{risk_fit:.2f}"
        )

        print()

        print(
            f"CURRENT Evidence:          "
            f"{current:.2f}"
        )

        print(
            f"PROPOSED BUY NEW Evidence: "
            f"{proposed:.2f}"
        )

        print(
            f"Difference:                 "
            f"{difference:+.2f}"
        )

        results.append(
            {
                "Ticker": ticker,
                "Investment Score": investment_score,
                "Learning Adjusted Score": learning_adjusted_score,
                "Learning Adjustment": learning_adjustment,
                "Historical Observations": observations,
                "Learning Evidence": learning_evidence,
                "Score Bucket Evidence": bucket_evidence,
                "Portfolio Fit": portfolio_fit,
                "Risk Fit": risk_fit,
                "Current Evidence": current,
                "Proposed BUY NEW Evidence": proposed,
                "Difference": difference,
            }
        )

    except Exception as exc:

        print(
            f"ERROR testing {ticker}: {exc}"
        )

    print()


# ============================================================
# Summary
# ============================================================

if results:

    result_df = pd.DataFrame(results)

    print(
        "============================================================"
    )
    print("SUMMARY")
    print(
        "============================================================"
    )
    print()

    display_columns = [
        "Ticker",
        "Investment Score",
        "Learning Adjusted Score",
        "Historical Observations",
        "Learning Adjustment",
        "Portfolio Fit",
        "Risk Fit",
        "Current Evidence",
        "Proposed BUY NEW Evidence",
        "Difference",
    ]

    print(
        result_df[
            display_columns
        ].to_string(
            index=False,
            float_format=lambda x: f"{x:.2f}",
        )
    )

    print()

    print(
        "No production files were changed."
    )

    print(
        "No database records were changed."
    )

    print(
        "No report files were changed."
    )

else:

    raise SystemExit(
        "ERROR: No candidates were successfully tested."
    )

PY

echo
echo "============================================================"
echo " Test complete"
echo "============================================================"
echo
