#!/bin/bash

set -u

echo "=============================================="
echo " AI Decision Reconciler - Advisory LLM Smoke Test"
echo "=============================================="
echo

python - <<'PY'
from agents.ai_decision_reconciler import reconcile_decision


def check(name, condition, detail=""):
    if condition:
        print(f"PASS  {name}")
    else:
        print(f"FAIL  {name}")
        if detail:
            print(f"      {detail}")
        raise SystemExit(1)


def run_case(name, decision, review, expected_action):
    print(f"\n--- {name} ---")

    result = reconcile_decision(
        decision=decision,
        review=review,
    )

    action = result.get("Reconciled Action")

    print(f"Deterministic Action : {result.get('Deterministic Action')}")
    print(f"Proposed Action      : {result.get('Proposed Action')}")
    print(f"LLM Review           : {result.get('LLM Review')}")
    print(f"LLM Confidence       : {result.get('LLM Confidence')}")
    print(f"Reconciled Action    : {action}")
    print(f"Automatic Approval   : {result.get('Automatic Approval')}")
    print(f"Failed Checks        : {result.get('Failed Checks')}")

    check(
        f"{name}: final action",
        action == expected_action,
        f"Expected {expected_action}, got {action}",
    )

    return result


# ============================================================
# 1. Strong BUY MORE + LLM ACCEPT
# ============================================================

decision = {
    "Final Decision": "BUY MORE",
    "Proposed Action": "BUY MORE",
    "Evidence Score": 78.0,
    "Evidence Strength": "STRONG",
    "Decision Support": "SUPPORTED",
    "Confidence": 74.0,
    "Existing Holding": True,
    "Asset Type": "STOCK",
    "Investment Score": 86.0,
    "Signal": "STRONG BUY",
}

review = {
    "Review Decision": "ACCEPT",
    "LLM Confidence": 82.0,
    "Challenge": False,
    "Reviewer Status": "LLM REVIEW COMPLETE",
}

result = run_case(
    "Strong BUY MORE + LLM ACCEPT",
    decision,
    review,
    "BUY MORE",
)

check(
    "LLM review retained for audit",
    result.get("LLM Review") == "ACCEPT",
)

# ============================================================
# 2. Strong BUY MORE + LLM CHALLENGE
# ============================================================

review = {
    "Review Decision": "CHALLENGE",
    "LLM Confidence": 85.0,
    "Challenge": True,
    "Reviewer Status": "LLM REVIEW COMPLETE",
}

result = run_case(
    "Strong BUY MORE + LLM CHALLENGE",
    decision,
    review,
    "BUY MORE",
)

check(
    "LLM challenge does NOT override deterministic action",
    result.get("Reconciled Action") == "BUY MORE",
)

# ============================================================
# 3. Strong BUY MORE + LLM REJECT
# ============================================================

review = {
    "Review Decision": "REJECT",
    "LLM Confidence": 90.0,
    "Challenge": True,
    "Reviewer Status": "LLM REVIEW COMPLETE",
}

result = run_case(
    "Strong BUY MORE + LLM REJECT",
    decision,
    review,
    "BUY MORE",
)

check(
    "LLM reject does NOT override deterministic action",
    result.get("Reconciled Action") == "BUY MORE",
)

# ============================================================
# 4. Weak deterministic proposal + LLM ACCEPT
# ============================================================

weak_decision = {
    "Final Decision": "BUY MORE",
    "Proposed Action": "BUY MORE",
    "Evidence Score": 45.0,
    "Evidence Strength": "WEAK",
    "Decision Support": "NOT SUPPORTED",
    "Confidence": 45.0,
    "Existing Holding": True,
    "Asset Type": "STOCK",
    "Investment Score": 55.0,
    "Signal": "HOLD",
}

review = {
    "Review Decision": "ACCEPT",
    "LLM Confidence": 95.0,
    "Challenge": False,
    "Reviewer Status": "LLM REVIEW COMPLETE",
}

result = run_case(
    "Weak deterministic proposal + LLM ACCEPT",
    weak_decision,
    review,
    "HOLD",
)

check(
    "LLM ACCEPT does NOT rescue weak deterministic proposal",
    result.get("Reconciled Action") == "HOLD",
)

# ============================================================
# 5. Failed deterministic threshold must expose actual/threshold
# ============================================================

reduce_decision = {
    "Final Decision": "SELL",
    "Proposed Action": "SELL",
    "Evidence Score": 65.0,
    "Evidence Strength": "STRONG",
    "Decision Support": "SUPPORTED",
    "Confidence": 72.0,
    "Existing Holding": True,
    "Asset Type": "STOCK",
    "Investment Score": 25.0,
    "Signal": "SELL",
}

review = {
    "Review Decision": "ACCEPT",
    "LLM Confidence": 95.0,
    "Challenge": False,
    "Reviewer Status": "LLM REVIEW COMPLETE",
}

result = run_case(
    "SELL with insufficient deterministic evidence",
    reduce_decision,
    review,
    "HOLD",
)

failed_checks = result.get("Failed Checks", [])

check(
    "Failed checks are retained",
    bool(failed_checks),
    "Expected at least one failed check.",
)

# Look for actual/threshold diagnostic values.
has_values = any(
    isinstance(check_item, dict)
    and "actual_value" in check_item
    and "threshold_value" in check_item
    for check_item in failed_checks
)

check(
    "Failed checks contain actual_value and threshold_value",
    has_values,
    f"Failed checks: {failed_checks}",
)

# ============================================================
# 6. Missing LLM review must not become LLM authority
# ============================================================

result = run_case(
    "Strong deterministic action with missing LLM review",
    decision,
    {},
    "BUY MORE",
)

check(
    "Missing LLM review does not alter deterministic action",
    result.get("Reconciled Action") == "BUY MORE",
)

print()
print("==============================================")
print(" ALL RECONCILER SMOKE TESTS PASSED")
print("==============================================")
PY
