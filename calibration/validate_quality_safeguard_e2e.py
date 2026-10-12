import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from analysis.portfolio_decision_engine import (
    determine_reduction_action,
    HOLD_ACTION,
    REDUCE_25_ACTION,
)


INPUT_FILE = (
    PROJECT_ROOT
    / "calibration"
    / "output"
    / "quality_safeguard_70_74_25_49.csv"
)


def main():

    print("=" * 70)
    print("QUALITY SAFEGUARD HISTORICAL VALIDATION")
    print("=" * 70)
    print()
    print("READ-ONLY")
    print("No production files or database records will be changed.")
    print()

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Historical cohort file not found:\n{INPUT_FILE}"
        )

    df = pd.read_csv(INPUT_FILE)

    print(f"Historical cases loaded: {len(df)}")
    print()

    passed = 0
    failed = 0

    for _, row in df.iterrows():

        action, reason = determine_reduction_action(
            investment_score=row["investment_score"],
            quality_score=row["quality_score"],
            growth_score=row["growth_score"],
            signal=row["signal"],
        )

        expected = REDUCE_25_ACTION

        ticker = row["ticker"]

        if action == expected:
            passed += 1
            result = "PASS"
        else:
            failed += 1
            result = "FAIL"

        print(
            f"{result}: "
            f"{ticker} | "
            f"Investment={row['investment_score']:.0f} | "
            f"Quality={row['quality_score']:.0f} | "
            f"Growth={row['growth_score']:.0f} | "
            f"Signal={row['signal']} | "
            f"Historical={row['final_action']} | "
            f"New={action}"
        )

        if action != expected:
            print(f"    Reason: {reason}")

    print()
    print("=" * 70)
    print("RESULT")
    print("=" * 70)
    print()
    print(f"Historical cases: {len(df)}")
    print(f"Passed:           {passed}")
    print(f"Failed:           {failed}")
    print()

    if failed == 0:
        print("ALL HISTORICAL CASES PASS")
        print()
        print(
            "All historical cases identified by the Quality safeguard "
            "now produce REDUCE 25%."
        )
    else:
        print("HISTORICAL VALIDATION FAILED")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
