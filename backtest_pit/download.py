"""Download a longer price history for the backtest (needs network access to Yahoo).

    python -m backtest_pit.download --tickers-file data/sp500.csv --start 2012-01-01 --out data/pit_prices
    python -m backtest_pit.download --tickers SPY IWDA.L --start 2012-01-01 --out data/pit_prices

Resumable: re-running skips tickers already saved. Include a benchmark ticker
(e.g. SPY) so ``--benchmark SPY`` works in the run step.
"""
from __future__ import annotations

import argparse

import pandas as pd

from .data import download_yfinance


def _tickers_from_file(path: str, column: str | None) -> list:
    df = pd.read_csv(path)
    col = column or next((c for c in df.columns if c.lower() in ("ticker", "symbol")), df.columns[0])
    return [str(t).strip().upper().replace(".", "-") for t in df[col].dropna().unique()]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tickers", nargs="*", default=[])
    ap.add_argument("--tickers-file")
    ap.add_argument("--column")
    ap.add_argument("--start", required=True)
    ap.add_argument("--end")
    ap.add_argument("--out", required=True)
    ap.add_argument("--batch-size", type=int, default=50)
    ap.add_argument("--pause", type=float, default=1.0)
    ap.add_argument("--overwrite", action="store_true")
    a = ap.parse_args(argv)
    tickers = list(a.tickers)
    if a.tickers_file:
        tickers += _tickers_from_file(a.tickers_file, a.column)
    tickers = sorted(set(tickers))
    n = download_yfinance(tickers, a.start, a.out, a.end, a.batch_size, a.pause, a.overwrite)
    print(f"saved {n} of {len(tickers)} requested tickers to {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
