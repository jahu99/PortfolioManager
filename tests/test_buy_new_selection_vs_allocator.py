"""
Diagnostic:

Trace BUY NEW candidates through the actual production snapshot lineage.

This test is READ-ONLY.

It does not:
    - run main.py
    - run the capital allocator
    - modify production code
    - modify portfolio decisions
    - write audit records
    - modify the database

Production lineage:

    Portfolio Decisions
            ↓
    Final Portfolio Decisions
            ↓
    Compare BUY NEW population

The purpose is to establish exactly which BUY NEW decisions survive
into Final Portfolio Decisions and specifically trace CLBK.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


# ============================================================
# PROJECT ROOT
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# FILES
# ============================================================

PORTFOLIO_DECISIONS_FILE = (
    PROJECT_ROOT
    / "data"
    / "portfolio_decisions_snapshot.csv"
)

FINAL_DECISIONS_FILE = (
    PROJECT_ROOT
    / "data"
    / "final_portfolio_decisions_snapshot.csv"
)


# ============================================================
# HELPERS
# ============================================================

def section(title: str) -> None:
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)


def clean_ticker(value) -> str:
    if value is None:
        return ""

    if pd.isna(value):
        return ""

    return str(value).strip().upper()


def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"Snapshot not found: {path}"
        )

    df = pd.read_csv(path)

    if df.empty:
        raise ValueError(
            f"Snapshot is empty: {path}"
        )

    return df


def normalise_tickers(
    df: pd.DataFrame,
) -> pd.DataFrame:

    df = df.copy()

    if "Ticker" not in df.columns:
        raise ValueError(
            "Snapshot does not contain a Ticker column."
        )

    df["_Ticker"] = (
        df["Ticker"]
        .map(clean_ticker)
    )

    return df


def buy_new_rows(
    df: pd.DataFrame,
    action_column: str,
) -> pd.DataFrame:

    if action_column not in df.columns:
        return pd.DataFrame()

    mask = (
        df[action_column]
        .astype(str)
        .str.strip()
        .str.upper()
        .eq("BUY NEW")
    )

    return df.loc[mask].copy()


def display_columns(
    df: pd.DataFrame,
) -> list[str]:

    preferred = [
        "Ticker",
        "Name",
        "Action",
        "Proposed Action",
        "Original Decision",
        "Final Decision",
        "Final Action",
        "Decision Status",
        "Reconciliation Status",
        "Investment Score",
        "Quality Score",
        "Growth Score",
        "Technical Score",
        "Confidence Score",
        "Evidence Score",
        "Entry Quality",
        "Buy Quantity",
        "Buy Value",
        "Capital Allocation",
        "Trade Execution",
        "Reason",
        "Final Reason",
        "Explanation",
    ]

    return [
        column
        for column in preferred
        if column in df.columns
    ]


def print_rows(
    title: str,
    df: pd.DataFrame,
) -> None:

    section(title)

    if df is None or df.empty:
        print("NONE")
        return

    columns = display_columns(df)

    if columns:
        print(
            df[columns]
            .to_string(index=False)
        )
    else:
        print(
            df.to_string(index=False)
        )


# ============================================================
# MAIN
# ============================================================

def main() -> int:

    section(
        "BUY NEW PRODUCTION SNAPSHOT TRACE"
    )

    print(
        "This diagnostic uses the persisted production outputs."
    )

    print(
        "It does not run main.py or generate new decisions."
    )

    print(
        f"\nPortfolio Decisions snapshot:"
        f"\n  {PORTFOLIO_DECISIONS_FILE}"
    )

    print(
        f"\nFinal Portfolio Decisions snapshot:"
        f"\n  {FINAL_DECISIONS_FILE}"
    )


    # ========================================================
    # 1. LOAD PRODUCTION SNAPSHOTS
    # ========================================================

    try:
        portfolio_decisions = load_csv(
            PORTFOLIO_DECISIONS_FILE
        )

        final_decisions = load_csv(
            FINAL_DECISIONS_FILE
        )

    except Exception as exc:

        print()
        print(
            f"ERROR loading snapshots: {exc}"
        )

        return 1


    portfolio_decisions = normalise_tickers(
        portfolio_decisions
    )

    final_decisions = normalise_tickers(
        final_decisions
    )


    # ========================================================
    # 2. PORTFOLIO DECISIONS BUY NEW
    # ========================================================

    portfolio_buy_new = buy_new_rows(
        portfolio_decisions,
        "Action",
    )

    print_rows(
        "PORTFOLIO DECISIONS — BUY NEW",
        portfolio_buy_new,
    )


    # ========================================================
    # 3. FINAL DECISION BUY NEW POPULATION
    # ========================================================

    # Final Portfolio Decisions has several action fields.
    #
    # "Proposed Action" is the most useful field for determining
    # whether the candidate entered the final decision population.
    #
    # Final Action / Final Decision are shown separately because
    # governance may subsequently alter the action.

    final_buy_new = buy_new_rows(
        final_decisions,
        "Proposed Action",
    )

    print_rows(
        "FINAL PORTFOLIO DECISIONS — PROPOSED BUY NEW",
        final_buy_new,
    )


    # ========================================================
    # 4. POPULATION COMPARISON
    # ========================================================

    portfolio_tickers = set(
        portfolio_buy_new["_Ticker"]
        .dropna()
    )

    final_tickers = set(
        final_buy_new["_Ticker"]
        .dropna()
    )

    only_portfolio_decisions = (
        portfolio_tickers
        - final_tickers
    )

    only_final_decisions = (
        final_tickers
        - portfolio_tickers
    )

    common_tickers = (
        portfolio_tickers
        &
        final_tickers
    )


    section(
        "BUY NEW POPULATION COMPARISON"
    )

    print(
        "Portfolio Decisions BUY NEW:",
        len(portfolio_tickers),
    )

    print(
        "Final Portfolio Decisions proposed BUY NEW:",
        len(final_tickers),
    )

    print(
        "Common:",
        len(common_tickers),
    )

    print()
    print(
        "BUY NEW present in Portfolio Decisions"
        " but absent from Final Portfolio Decisions:"
    )

    print(
        sorted(
            only_portfolio_decisions
        )
        or "NONE"
    )

    print()
    print(
        "BUY NEW present in Final Portfolio Decisions"
        " but absent from Portfolio Decisions:"
    )

    print(
        sorted(
            only_final_decisions
        )
        or "NONE"
    )


    # ========================================================
    # 5. CLBK TRACE
    # ========================================================

    section(
        "CLBK TRACE"
    )

    clbk_portfolio = portfolio_decisions.loc[
        portfolio_decisions["_Ticker"].eq("CLBK")
    ].copy()

    clbk_final = final_decisions.loc[
        final_decisions["_Ticker"].eq("CLBK")
    ].copy()


    print()
    print(
        "Portfolio Decisions snapshot:"
    )

    if clbk_portfolio.empty:
        print(
            "CLBK NOT PRESENT"
        )
    else:
        print_rows(
            "CLBK — PORTFOLIO DECISIONS",
            clbk_portfolio,
        )


    print()
    print(
        "Final Portfolio Decisions snapshot:"
    )

    if clbk_final.empty:
        print(
            "CLBK NOT PRESENT"
        )
    else:
        print_rows(
            "CLBK — FINAL PORTFOLIO DECISIONS",
            clbk_final,
        )


    # ========================================================
    # 6. CLBK INTERPRETATION
    # ========================================================

    section(
        "CLBK DIAGNOSTIC RESULT"
    )

    clbk_portfolio_action = ""

    if not clbk_portfolio.empty:
        clbk_portfolio_action = (
            str(
                clbk_portfolio.iloc[0].get(
                    "Action",
                    "",
                )
            )
            .strip()
            .upper()
        )

    clbk_final_proposed_action = ""

    if not clbk_final.empty:
        clbk_final_proposed_action = (
            str(
                clbk_final.iloc[0].get(
                    "Proposed Action",
                    "",
                )
            )
            .strip()
            .upper()
        )

    if (
        clbk_portfolio_action
        ==
        "BUY NEW"
        and
        clbk_final_proposed_action
        ==
        "BUY NEW"
    ):

        print(
            "CLBK SURVIVES:"
        )

        print(
            "Portfolio Decisions → Final Portfolio Decisions"
            " population is intact for CLBK."
        )

    elif (
        clbk_portfolio_action
        ==
        "BUY NEW"
        and
        clbk_final.empty
    ):

        print(
            "CLBK DROPPED:"
        )

        print(
            "CLBK is BUY NEW in Portfolio Decisions"
            " but has no Final Portfolio Decisions row."
        )

        print(
            "This indicates a population/eligibility issue"
            " between those layers."
        )

    elif (
        clbk_portfolio_action
        ==
        "BUY NEW"
        and
        clbk_final_proposed_action
        !=
        "BUY NEW"
    ):

        print(
            "CLBK PRESENT BUT ACTION CHANGED:"
        )

        print(
            "CLBK entered Final Portfolio Decisions,"
            " but Proposed Action is no longer BUY NEW."
        )

    elif clbk_portfolio.empty:

        print(
            "CLBK NOT IN PORTFOLIO DECISIONS:"
        )

        print(
            "The problem occurs before the Final Portfolio"
            " Decisions population."
        )

    else:

        print(
            "CLBK exists, but is not BUY NEW"
            " in Portfolio Decisions."
        )


    # ========================================================
    # 7. READ-ONLY GUARANTEE
    # ========================================================

    section(
        "READ-ONLY CHECK"
    )

    print(
        "PASS: No production pipeline was executed."
    )

    print(
        "PASS: No capital allocation was generated."
    )

    print(
        "PASS: No portfolio decisions were generated."
    )

    print(
        "PASS: No audit records were written."
    )

    print(
        "PASS: No production files were modified."
    )


    return 0


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    raise SystemExit(
        main()
    )