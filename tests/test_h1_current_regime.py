"""
Read-only current-regime validation of H1 for BUY NEW candidate selection.

Purpose
-------
Test whether the H1 concept:

    RSI >= threshold
    AND Return_3m <= threshold

would have identified the strongest recent stocks in the S&P 500
and Nasdaq-100 during the current 4 Sep -> 18 Sep 2026 regime.

IMPORTANT
---------
This is a diagnostic experiment only.

It does NOT:
- change production thresholds
- change Technical Score
- change Investment Score
- change BUY/BUY MORE/HOLD/SELL governance
- change candidate_selection.py
- write to the audit database
- write to recommendation_evidence
- modify learning weights

Look-ahead protection
---------------------
The eventual winners are identified using performance through 18 Sep.

H1 is evaluated ONLY using information available at the
4 Sep 2026 close.

The subsequent 5D/10D/20D returns are measured independently.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from pathlib import Path


# ============================================================
# PATHS / TEST PARAMETERS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = PROJECT_ROOT / "data"
CACHE_DIR = DATA_DIR / "cache"

START_DATE = pd.Timestamp("2026-09-04")
END_DATE = pd.Timestamp("2026-09-18")

RSI_THRESHOLD = 55.0
RETURN_3M_THRESHOLDS = (15.0, 20.0, 25.0)

TOP_N = 5

HORIZONS = {
    "5D": 5,
    "10D": 10,
    "20D": 20,
}


# ============================================================
# UNIVERSE DISCOVERY
# ============================================================

def find_universe_file(candidates: list[str]) -> Path | None:
    for filename in candidates:
        path = DATA_DIR / filename

        if path.exists():
            return path

    return None


def load_ticker_column(path: Path) -> list[str]:
    df = pd.read_csv(path)

    possible_columns = [
        "Ticker",
        "ticker",
        "Symbol",
        "symbol",
        "Ticker Symbol",
        "ticker_symbol",
    ]

    ticker_column = next(
        (
            column
            for column in possible_columns
            if column in df.columns
        ),
        None,
    )

    if ticker_column is None:
        raise ValueError(
            f"Could not find a ticker column in {path}. "
            f"Columns found: {list(df.columns)}"
        )

    tickers = (
        df[ticker_column]
        .dropna()
        .astype(str)
        .str.strip()
        .tolist()
    )

    return sorted(set(tickers))


def load_sp500_universe() -> list[str]:
    path = find_universe_file(
        [
            "sp500.csv",
            "s&p500.csv",
            "s_and_p500.csv",
            "snp500.csv",
            "sp500_universe.csv",
        ]
    )

    if path is None:
        raise FileNotFoundError(
            "Could not locate the S&P 500 universe CSV in data/."
        )

    return load_ticker_column(path)


def load_nasdaq100_universe() -> list[str]:
    path = find_universe_file(
        [
            "nasdaq.csv",
            "nasdaq100_universe.csv",
            "ndx.csv",
            "ndx100.csv",
        ]
    )

    if path is None:
        raise FileNotFoundError(
            "Could not locate the Nasdaq-100 universe CSV in data/."
        )

    return load_ticker_column(path)


# ============================================================
# PRICE CACHE
# ============================================================

def normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()

    rename_map = {}

    for column in result.columns:
        normalised = str(column).strip().lower()

        if normalised in {
            "date",
            "datetime",
            "timestamp",
        }:
            rename_map[column] = "Date"

        elif normalised in {
            "close",
            "adj close",
            "adjusted close",
        }:
            rename_map[column] = "Close"

    return result.rename(columns=rename_map)


def load_price_history(ticker: str) -> pd.DataFrame | None:
    """
    Load historical prices through the production market-data loader.

    Normalises yfinance-style MultiIndex / duplicated columns so that
    the H1 diagnostic always receives a simple Date + Close dataframe.
    """

    try:
        from data.market_data import get_stock_data
    except ImportError as exc:
        raise ImportError(
            "Could not import data.market_data.get_stock_data()"
        ) from exc

    try:
        df = get_stock_data(ticker)
    except Exception as exc:
        print(
            f"\n  WARNING: could not load {ticker}: {exc}"
        )
        return None

    if df is None or df.empty:
        return None

    result = df.copy()

    # ---------------------------------------------------------
    # Normalise the index
    # ---------------------------------------------------------

    if isinstance(result.index, pd.DatetimeIndex):
        result = result.reset_index()

    # ---------------------------------------------------------
    # Normalise MultiIndex columns
    # ---------------------------------------------------------

    if isinstance(result.columns, pd.MultiIndex):
        flattened = []

        for column in result.columns:
            parts = [
                str(part)
                for part in column
                if str(part).lower() != "nan"
            ]

            flattened.append("_".join(parts))

        result.columns = flattened

    # ---------------------------------------------------------
    # Locate Date column
    # ---------------------------------------------------------

    date_column = next(
        (
            column
            for column in result.columns
            if str(column).lower()
            in {
                "date",
                "datetime",
                "timestamp",
            }
        ),
        None,
    )

    if date_column is None:
        # Handle common flattened yfinance names such as
        # "Date_A".
        date_candidates = [
            column
            for column in result.columns
            if str(column).lower().startswith("date")
        ]

        if not date_candidates:
            return None

        date_column = date_candidates[0]

    if date_column != "Date":
        result = result.rename(
            columns={
                date_column: "Date"
            }
        )

    # ---------------------------------------------------------
    # Locate Close column
    # ---------------------------------------------------------

    close_candidates = [
        column
        for column in result.columns
        if str(column).lower() == "close"
        or str(column).lower().startswith("close_")
        or str(column).lower().endswith("_close")
    ]

    if not close_candidates:
        return None

    close_column = close_candidates[0]

    if close_column != "Close":
        result = result.rename(
            columns={
                close_column: "Close"
            }
        )

    # ---------------------------------------------------------
    # Make absolutely sure Close is one-dimensional
    # ---------------------------------------------------------

    close = result["Close"]

    if isinstance(close, pd.DataFrame):
        # This can happen if duplicate Close columns survived
        # normalisation. Take the first actual price column.
        close = close.iloc[:, 0]

    result["Close"] = pd.to_numeric(
        close,
        errors="coerce",
    )

    # ---------------------------------------------------------
    # Normalise dates and clean rows
    # ---------------------------------------------------------

    result["Date"] = pd.to_datetime(
        result["Date"],
        errors="coerce",
    )

    # Remove timezone if present.
    if (
        isinstance(result["Date"].dtype, pd.DatetimeTZDtype)
    ):
        result["Date"] = (
            result["Date"]
            .dt.tz_localize(None)
        )

    result = (
        result[
            [
                "Date",
                "Close",
            ]
        ]
        .dropna(
            subset=[
                "Date",
                "Close",
            ]
        )
        .sort_values("Date")
        .drop_duplicates(
            subset=["Date"],
            keep="last",
        )
        .reset_index(drop=True)
    )

    if result.empty:
        return None

    return result
# ============================================================
# INDICATORS
# ============================================================

def calculate_rsi(
    close: pd.Series,
    period: int = 14,
) -> pd.Series:
    delta = close.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    average_gain = gain.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period,
    ).mean()

    average_loss = loss.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period,
    ).mean()

    rs = (
        average_gain
        / average_loss.replace(0, np.nan)
    )

    rsi = 100 - (
        100 / (1 + rs)
    )

    rsi = rsi.where(
        average_loss != 0,
        100.0,
    )

    return rsi


def calculate_return_3m(
    close: pd.Series,
    trading_days: int = 63,
) -> pd.Series:
    return (
        close
        .pct_change(trading_days)
        .mul(100)
    )


def build_indicators(
    price_history: pd.DataFrame,
) -> pd.DataFrame:
    df = price_history.copy()

    df["RSI"] = calculate_rsi(
        df["Close"]
    )

    df["Return_3m"] = calculate_return_3m(
        df["Close"]
    )

    return df


# ============================================================
# START-DATE SNAPSHOT
# ============================================================

def get_start_snapshot(
    ticker: str,
    price_history: pd.DataFrame,
) -> dict | None:

    df = build_indicators(
        price_history
    )

    # CRITICAL:
    # H1 inputs can only use information available
    # on or before 4 Sep 2026.
    df = df[
        df["Date"] <= START_DATE
    ].copy()

    if df.empty:
        return None

    row = df.iloc[-1]

    if row["Date"].normalize() != START_DATE:
        return None

    if pd.isna(row["RSI"]):
        return None

    if pd.isna(row["Return_3m"]):
        return None

    return {
        "Ticker": ticker,
        "Start Close": float(
            row["Close"]
        ),
        "RSI": float(
            row["RSI"]
        ),
        "Return_3m": float(
            row["Return_3m"]
        ),
    }


# ============================================================
# FORWARD RETURNS
# ============================================================

def get_forward_returns(
    price_history: pd.DataFrame,
) -> dict[str, float | None]:

    df = (
        price_history
        .sort_values("Date")
        .reset_index(drop=True)
    )

    start_positions = df.index[
        df["Date"] == START_DATE
    ]

    if len(start_positions) == 0:
        return {
            horizon: None
            for horizon in HORIZONS
        }

    start_position = int(
        start_positions[0]
    )

    start_close = float(
        df.loc[
            start_position,
            "Close",
        ]
    )

    results = {}

    for horizon, days in HORIZONS.items():

        target_position = (
            start_position + days
        )

        if target_position >= len(df):
            results[horizon] = None
            continue

        target_date = df.loc[
            target_position,
            "Date",
        ]

        if target_date > END_DATE:
            results[horizon] = None
            continue

        target_close = float(
            df.loc[
                target_position,
                "Close",
            ]
        )

        results[horizon] = (
            (
                target_close
                / start_close
            ) - 1
        ) * 100

    return results


# ============================================================
# TWO-WEEK PERFORMANCE
# ============================================================

def calculate_period_return(
    price_history: pd.DataFrame,
) -> float | None:

    df = (
        price_history
        .sort_values("Date")
    )

    start = df[
        df["Date"] == START_DATE
    ]

    end = df[
        df["Date"] == END_DATE
    ]

    if start.empty or end.empty:
        return None

    start_close = float(
        start.iloc[-1]["Close"]
    )

    end_close = float(
        end.iloc[-1]["Close"]
    )

    if start_close <= 0:
        return None

    return (
        (
            end_close
            / start_close
        ) - 1
    ) * 100


# ============================================================
# BUILD UNIVERSE
# ============================================================

def build_universe_observations(
    tickers: list[str],
    universe_name: str,
) -> pd.DataFrame:

    rows = []

    print()
    print(
        f"Loading {universe_name}: "
        f"{len(tickers)} tickers"
    )

    for number, ticker in enumerate(
        tickers,
        start=1,
    ):

        print(
            f"\r  {number}/{len(tickers)} "
            f"{ticker:<12}",
            end="",
            flush=True,
        )

        price_history = load_price_history(
            ticker
        )

        if price_history is None:
            continue

        snapshot = get_start_snapshot(
            ticker,
            price_history,
        )

        if snapshot is None:
            continue

        two_week_return = (
            calculate_period_return(
                price_history
            )
        )

        if two_week_return is None:
            continue

        forward_returns = (
            get_forward_returns(
                price_history
            )
        )

        snapshot.update(
            {
                "Universe": universe_name,
                "Two Week Return": (
                    two_week_return
                ),
                **forward_returns,
            }
        )

        rows.append(snapshot)

    print()

    return pd.DataFrame(rows)


# ============================================================
# H1
# ============================================================

def apply_h1(
    df: pd.DataFrame,
) -> pd.DataFrame:

    result = df.copy()

    for return_3m_max in (
        RETURN_3M_THRESHOLDS
    ):

        column = (
            f"H1 RSI>=55 "
            f"3M<={return_3m_max:g}"
        )

        result[column] = (
            result["RSI"].ge(
                RSI_THRESHOLD
            )
            & result["Return_3m"].le(
                return_3m_max
            )
        )

    return result


# ============================================================
# REPORTING
# ============================================================

def select_top_five(
    df: pd.DataFrame,
) -> pd.DataFrame:

    return (
        df
        .sort_values(
            "Two Week Return",
            ascending=False,
        )
        .head(TOP_N)
        .copy()
    )


def print_top_five(
    df: pd.DataFrame,
) -> None:

    universe = (
        df["Universe"].iloc[0]
    )

    print()
    print("=" * 100)
    print(
        f"TOP {TOP_N} — {universe}"
    )
    print("=" * 100)

    columns = [
        "Ticker",
        "Two Week Return",
        "RSI",
        "Return_3m",
        "H1 RSI>=55 3M<=15",
        "H1 RSI>=55 3M<=20",
        "H1 RSI>=55 3M<=25",
        "5D",
        "10D",
        "20D",
    ]

    display = df[
        columns
    ].copy()

    for column in [
        "Two Week Return",
        "RSI",
        "Return_3m",
        "5D",
        "10D",
        "20D",
    ]:
        display[column] = (
            display[column]
            .map(
                lambda value:
                (
                    f"{value:.2f}"
                    if pd.notna(value)
                    else "NA"
                )
            )
        )

    print(
        display.to_string(
            index=False
        )
    )


def print_top_five_h1_results(
    top_five: pd.DataFrame,
) -> None:

    print()
    print("=" * 100)
    print("EVENTUAL TOP-FIVE H1 TEST")
    print("=" * 100)

    for _, row in top_five.iterrows():

        print()
        print(
            f"{row['Universe']} — "
            f"{row['Ticker']}"
        )

        print(
            f"  4 Sep RSI: "
            f"{row['RSI']:.2f}"
        )

        print(
            f"  4 Sep Return 3M: "
            f"{row['Return_3m']:.2f}%"
        )

        print(
            f"  4 Sep -> 18 Sep: "
            f"{row['Two Week Return']:.2f}%"
        )

        for threshold in (
            RETURN_3M_THRESHOLDS
        ):

            column = (
                f"H1 RSI>=55 "
                f"3M<={threshold:g}"
            )

            result = (
                "PASS"
                if bool(row[column])
                else "FAIL"
            )

            print(
                f"  {column}: "
                f"{result}"
            )

        for horizon in HORIZONS:

            value = row[horizon]

            if pd.isna(value):
                print(
                    f"  {horizon}: NA"
                )
            else:
                print(
                    f"  {horizon}: "
                    f"{value:.2f}%"
                )


def performance_summary(
    df: pd.DataFrame,
    selection_column: str | None = None,
) -> dict:

    if selection_column is None:
        selected = df
    else:
        selected = df[
            df[selection_column]
        ]

    result = {
        "N": len(selected)
    }

    for horizon in HORIZONS:

        values = pd.to_numeric(
            selected[horizon],
            errors="coerce",
        ).dropna()

        if values.empty:

            result[
                f"{horizon}_mean"
            ] = None

            result[
                f"{horizon}_median"
            ] = None

            result[
                f"{horizon}_positive"
            ] = None

            continue

        result[
            f"{horizon}_mean"
        ] = values.mean()

        result[
            f"{horizon}_median"
        ] = values.median()

        result[
            f"{horizon}_positive"
        ] = (
            values.gt(0).mean()
            * 100
        )

    return result


def print_performance_comparison(
    df: pd.DataFrame,
    universe_name: str,
) -> None:

    print()
    print("=" * 100)
    print(
        f"PERFORMANCE — {universe_name}"
    )
    print("=" * 100)

    baseline = performance_summary(
        df
    )

    print()
    print(
        "BASELINE"
    )

    for horizon in HORIZONS:

        mean = baseline[
            f"{horizon}_mean"
        ]

        median = baseline[
            f"{horizon}_median"
        ]

        positive = baseline[
            f"{horizon}_positive"
        ]

        if mean is None:
            continue

        print(
            f"  {horizon}: "
            f"mean={mean:.3f}% "
            f"median={median:.3f}% "
            f"positive={positive:.2f}% "
            f"n={baseline['N']}"
        )

    for threshold in (
        RETURN_3M_THRESHOLDS
    ):

        column = (
            f"H1 RSI>=55 "
            f"3M<={threshold:g}"
        )

        selected = performance_summary(
            df,
            column,
        )

        print()
        print(column)

        for horizon in HORIZONS:

            mean = selected[
                f"{horizon}_mean"
            ]

            if mean is None:
                print(
                    f"  {horizon}: "
                    f"no observations"
                )
                continue

            median = selected[
                f"{horizon}_median"
            ]

            positive = selected[
                f"{horizon}_positive"
            ]

            delta = (
                mean
                - baseline[
                    f"{horizon}_mean"
                ]
            )

            print(
                f"  {horizon}: "
                f"mean={mean:.3f}% "
                f"median={median:.3f}% "
                f"positive={positive:.2f}% "
                f"n={selected['N']} "
                f"delta={delta:+.3f}pp"
            )


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    print()
    print("=" * 100)
    print("H1 CURRENT-REGIME VALIDATION")
    print("=" * 100)

    print(
        f"Information date: "
        f"{START_DATE.date()}"
    )

    print(
        f"Performance window: "
        f"{START_DATE.date()} -> "
        f"{END_DATE.date()}"
    )

    print()
    print(
        "H1 uses information available "
        "ONLY at the 4 Sep close."
    )

    print(
        "The 4 Sep -> 18 Sep return is used "
        "ONLY to identify the eventual winners."
    )

    print()
    print(
        "NO PRODUCTION CHANGES WILL BE MADE."
    )

    # --------------------------------------------------------
    # Universes
    # --------------------------------------------------------

    sp500 = load_sp500_universe()
    nasdaq100 = load_nasdaq100_universe()

    print()
    print(
        f"S&P 500 universe: "
        f"{len(sp500)}"
    )

    print(
        f"Nasdaq-100 universe: "
        f"{len(nasdaq100)}"
    )

    # --------------------------------------------------------
    # Observations
    # --------------------------------------------------------

    sp500_df = build_universe_observations(
        sp500,
        "S&P 500",
    )

    nasdaq100_df = build_universe_observations(
        nasdaq100,
        "Nasdaq-100",
    )

    if sp500_df.empty:
        raise RuntimeError(
            "No S&P 500 observations were built."
        )

    if nasdaq100_df.empty:
        raise RuntimeError(
            "No Nasdaq-100 observations were built."
        )

    # --------------------------------------------------------
    # H1
    # --------------------------------------------------------

    sp500_df = apply_h1(
        sp500_df
    )

    nasdaq100_df = apply_h1(
        nasdaq100_df
    )

    # --------------------------------------------------------
    # Eventual top five
    # --------------------------------------------------------

    sp500_top5 = select_top_five(
        sp500_df
    )

    nasdaq100_top5 = select_top_five(
        nasdaq100_df
    )

    print_top_five(
        sp500_top5
    )

    print_top_five(
        nasdaq100_top5
    )

    # --------------------------------------------------------
    # H1 result for eventual winners
    # --------------------------------------------------------

    combined_top10 = pd.concat(
        [
            sp500_top5,
            nasdaq100_top5,
        ],
        ignore_index=True,
    )

    print_top_five_h1_results(
        combined_top10
    )

    # --------------------------------------------------------
    # Population performance
    # --------------------------------------------------------

    print_performance_comparison(
        sp500_df,
        "S&P 500",
    )

    print_performance_comparison(
        nasdaq100_df,
        "Nasdaq-100",
    )

    # --------------------------------------------------------
    # Combined population
    # --------------------------------------------------------

    combined = pd.concat(
        [
            sp500_df,
            nasdaq100_df,
        ],
        ignore_index=True,
    )

    print_performance_comparison(
        combined,
        "Combined S&P 500 + Nasdaq-100",
    )

    # --------------------------------------------------------
    # Final summary
    # --------------------------------------------------------

    print()
    print("=" * 100)
    print("EVENTUAL TOP-FIVE H1 COVERAGE")
    print("=" * 100)

    for top_five in [
        sp500_top5,
        nasdaq100_top5,
    ]:

        universe = (
            top_five[
                "Universe"
            ].iloc[0]
        )

        print()
        print(universe)

        for threshold in (
            RETURN_3M_THRESHOLDS
        ):

            column = (
                f"H1 RSI>=55 "
                f"3M<={threshold:g}"
            )

            passed = int(
                top_five[column].sum()
            )

            print(
                f"  {column}: "
                f"{passed}/{TOP_N}"
            )

    print()
    print("=" * 100)
    print("ASSESSMENT")
    print("=" * 100)

    print(
        "This is a current-regime diagnostic only."
    )

    print(
        "It does not select a production H1 threshold."
    )

    print(
        "It does not change Technical Score."
    )

    print(
        "It does not change Investment Score."
    )

    print(
        "It does not change BUY NEW production logic."
    )

    print(
        "It does not override HOLD protection "
        "or governance."
    )


if __name__ == "__main__":
    main()
