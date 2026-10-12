"""Benchmark universes and realised forward performance. Research-only."""
from __future__ import annotations
import pandas as pd
import yfinance as yf
import requests


def _ticker(value: str) -> str:
    return str(value).strip().upper().replace('.', '-')


def load_universe(name: str) -> list[str]:
    name = name.upper()
    if name == 'SP500': return load_sp500_constituents()
    if name == 'NASDAQ100': return load_nasdaq100_constituents()
    if name == 'BOTH': return sorted(set(load_sp500_constituents()) | set(load_nasdaq100_constituents()))
    raise ValueError('Universe must be SP500, NASDAQ100, or BOTH.')


def load_historical_closes(
    tickers: list[str],
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> pd.DataFrame:
    """
    Download historical closing prices for the calibration universe once.

    This is research-only. It does not call any AI/LLM functionality.
    """

    data = yf.download(
        tickers,
        start=start_date.strftime("%Y-%m-%d"),
        end=(end_date + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
        auto_adjust=False,
        progress=False,
        group_by="column",
    )

    if data.empty:
        raise RuntimeError("No historical price data returned.")

    close = data["Close"]

    if isinstance(close, pd.Series):
        close = close.to_frame()

    close.index = pd.to_datetime(
        close.index
    ).tz_localize(None)

    close.columns = [
        _ticker(column)
        for column in close.columns
    ]

    return close.apply(
        pd.to_numeric,
        errors="coerce"
    )


def realised_forward_return(
    closes: pd.DataFrame,
    ticker: str,
    t0: pd.Timestamp,
    forward_days: int,
) -> float | None:
    """
    Calculate realised forward return from already-loaded prices.
    """

    ticker = _ticker(ticker)

    if ticker not in closes.columns:
        return None

    t0 = pd.Timestamp(t0).normalize()
    target = t0 + pd.Timedelta(days=forward_days)

    series = closes[ticker].dropna()

    before = series[series.index <= t0]
    after = series[series.index >= target]

    if before.empty or after.empty:
        return None

    entry_price = float(before.iloc[-1])
    exit_price = float(after.iloc[0])

    if entry_price <= 0:
        return None

    return (
        (exit_price / entry_price) - 1.0
    ) * 100.0


def rank_forward_winners(
    tickers,
    closes: pd.DataFrame,
    t0: pd.Timestamp,
    forward_days: int,
    top_n: int,
) -> pd.DataFrame:

    rows = []

    for ticker in tickers:

        ret = realised_forward_return(
            closes,
            ticker,
            t0,
            forward_days,
        )

        if ret is not None:

            rows.append(
                {
                    "Evaluation Date": t0.date().isoformat(),
                    "Ticker": ticker,
                    "Forward Return %": ret,
                }
            )

    if not rows:
        return pd.DataFrame()

    result = (
        pd.DataFrame(rows)
        .sort_values(
            ["Forward Return %", "Ticker"],
            ascending=[False, True],
        )
        .reset_index(drop=True)
    )

    result["Forward Rank"] = result.index + 1

    result["Benchmark Top N"] = (
        result["Forward Rank"] <= top_n
    )

    return result.head(top_n)

def _read_html_tables(url):
    """
    Download an HTML page using a browser-style request and then
    pass the response content to pandas.

    Wikipedia may reject pandas' default HTTP request with HTTP 403.
    """

    import requests
    from io import StringIO

    response = requests.get(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 "
                "(Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/140.0 Safari/537.36"
            )
        },
        timeout=30,
    )

    response.raise_for_status()

    return pd.read_html(
        StringIO(response.text)
    )


def load_sp500_constituents():
    """
    Load the current S&P 500 constituent list.

    This is benchmark-universe data only. It does not modify
    the production Stock Momentum Agent universe.
    """

    tables = _read_html_tables(
        "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    )

    table = tables[0]

    symbols = (
        table["Symbol"]
        .dropna()
        .astype(str)
        .str.strip()
    )

    return sorted(
        {
            symbol
            .replace(".", "-")
            .upper()
            for symbol in symbols
        }
    )


def load_nasdaq100_constituents():
    """
    Load current Nasdaq-100 constituents from Nasdaq's official API.
    """

    url = "https://api.nasdaq.com/api/quote/list-type/nasdaq100"

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.nasdaq.com",
        "Referer": "https://www.nasdaq.com/",
    }

    response = requests.get(
        url,
        headers=headers,
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()

    rows = (
        data
        .get("data", {})
        .get("data", {})
        .get("rows", [])
    )

    tickers = []

    for row in rows:

        symbol = row.get("symbol")

        if symbol:
            tickers.append(symbol.upper().strip())

    tickers = sorted(set(tickers))

    if len(tickers) < 90:
        raise RuntimeError(
            f"Nasdaq-100 loader returned only {len(tickers)} constituents."
        )

    return tickers