import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from analysis.portfolio_decision_engine import (
    determine_reduction_action,
    HOLD_ACTION,
    REDUCE_25_ACTION,
    REDUCE_75_ACTION,
    SELL_ACTION,
)

def run_test(investment_score, quality_score, growth_score, signal, expected):
    action, reason = determine_reduction_action(
        investment_score=investment_score,
        quality_score=quality_score,
        growth_score=growth_score,
        signal=signal,
    )

    result = "PASS" if action == expected else "FAIL"

    print(
        f"{result}: "
        f"Investment={investment_score}, "
        f"Quality={quality_score}, "
        f"Growth={growth_score}, "
        f"Signal={signal} "
        f"→ {action}"
    )

    if action != expected:
        print(f"    Reason: {reason}")

    return action == expected


def main():

    print("=" * 70)
    print("QUALITY SAFEGUARD REGRESSION TEST")
    print("=" * 70)
    print()
    print("READ-ONLY")
    print("No production files or database records will be changed.")
    print()

    tests = [

        # --------------------------------------------------------
        # SAFEGUARD SHOULD FIRE
        # --------------------------------------------------------

        (
            70,
            25,
            75,
            "BUY",
            REDUCE_25_ACTION,
        ),

        (
            71,
            35,
            75,
            "BUY",
            REDUCE_25_ACTION,
        ),

        (
            72,
            46,
            75,
            "BUY",
            REDUCE_25_ACTION,
        ),

        (
            74,
            49,
            70,
            "BUY",
            REDUCE_25_ACTION,
        ),

        # --------------------------------------------------------
        # BOUNDARY: QUALITY BELOW 25
        # --------------------------------------------------------
        # Must NOT be caught by this safeguard.

        (
            70,
            24,
            75,
            "BUY",
            HOLD_ACTION,
        ),

        # --------------------------------------------------------
        # BOUNDARY: QUALITY = 50
        # --------------------------------------------------------
        # Must NOT be caught by this safeguard.

        (
            74,
            50,
            75,
            "BUY",
            HOLD_ACTION,
        ),

        # --------------------------------------------------------
        # BOUNDARY: INVESTMENT SCORE BELOW 70
        # --------------------------------------------------------

        (
            69,
            40,
            75,
            "BUY",
            HOLD_ACTION,
        ),

        # --------------------------------------------------------
        # BOUNDARY: INVESTMENT SCORE = 75
        # --------------------------------------------------------

        (
            75,
            40,
            75,
            "BUY",
            HOLD_ACTION,
        ),

        # --------------------------------------------------------
        # STRONGER EXISTING REDUCTION LOGIC
        # --------------------------------------------------------
        # The safeguard must not override existing severe
        # reduction rules.

        (
            20,
            20,
            20,
            "SELL",
            SELL_ACTION,
        ),
    ]

    passed = 0
    failed = 0

    for test in tests:

        if run_test(*test):
            passed += 1
        else:
            failed += 1

    print()
    print("=" * 70)
    print("RESULT")
    print("=" * 70)
    print()
    print(f"Tests:  {len(tests)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print()

    if failed == 0:
        print("ALL TESTS PASSED")
    else:
        print("TEST FAILURE")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
