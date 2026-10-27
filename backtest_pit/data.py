"""Price loading for the point-in-time backtest.

Three ways to get a PricePanel:

* ``load_pickle_dir``  - the repo's existing ``data/cache/prices/*.pkl`` files.
  Pickle can execute code on load, so a strict allow-list loader is used: it
  refuses any global that is not one of the plain pandas/numpy reconstruction
  functions found in those files.
* ``load_csv_dir``     - ``*.csv.gz`` files (Date, Close, Adj Close, Volume),
  which is what ``download_yfinance`` writes. Preferred for long histories.
* ``assemble_panel``   - from an in-memory ``{ticker: DataFrame}`` mapping.
"""
from __future__ import annotations

import glob
import os
import pickle
import time
from dataclasses import dataclass

import numpy as np
import pandas as pd

# Exact set of globals found in the repo's cached price pickles (found by
# scanning them with a stub loader that executes nothing).
_PICKLE_ALLOWLIST = frozenset(
    {
        ("builtins", "slice"),
        ("numpy._core.multiarray", "_reconstruct"),
        ("numpy._core.numeric", "_frombuffer"),
        ("numpy", "dtype"),
        ("numpy", "ndarray"),
        ("pandas", "DataFrame"),
        ("pandas", "DatetimeIndex"),
        ("pandas", "Index"),
        ("pandas", "StringDtype"),
        ("pandas._libs.arrays", "__pyx_unpickle_NDArrayBacked"),
        ("pandas._libs.internals", "_unpickle_block"),
        ("pandas.arrays", "DatetimeArray"),
        ("pandas.arrays", "StringArray"),
        ("pandas.core.indexes.base", "_new_Index"),
        ("pandas.core.indexes.datetimes", "_new_DatetimeIndex"),
        ("pandas.core.internals.managers", "BlockManager"),
    }
)


class _StrictUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        if (module, name) not in _PICKLE_ALLOWLIST:
            raise pickle.UnpicklingError(
                f"Refusing to load pickle: global {module}.{name} is not allow-listed"
            )
        return super().find_class(module, name)


def read_price_pickle(path: str) -> pd.DataFrame:
    with open(path, "rb") as fh:
        return _StrictUnpickler(fh).load()


@dataclass
class PricePanel:
    """Aligned (date x ticker) panels. All three share the same index/columns."""

    close: pd.DataFrame      # split-adjusted, NOT dividend-adjusted (what the live scorer uses)
    adj_close: pd.DataFrame  # total-return series, used for forward returns
    volume: pd.DataFrame

    def __post_init__(self):
        if not (self.close.index.equals(self.adj_close.index) and self.close.index.equals(self.volume.index)):
            raise ValueError("panels must share the same date index")
        if not (self.close.columns.equals(self.adj_close.columns) and self.close.columns.equals(self.volume.columns)):
            raise ValueError("panels must share the same ticker columns")

    @property
    def index(self) -> pd.DatetimeIndex:
        return self.close.index

    @property
    def tickers(self) -> list:
        return list(self.close.columns)

    def subset(self, tickers) -> "PricePanel":
        cols = [t for t in tickers if t in self.close.columns]
        return PricePanel(self.close[cols], self.adj_close[cols], self.volume[cols])


def _clean_frame(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    idx = pd.to_datetime(df.index)
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_localize(None)
    df.index = idx.normalize()
    df = df[~df.index.duplicated(keep="last")].sort_index()
    return df


def assemble_panel(frames: dict, min_rows: int = 0) -> PricePanel:
    """Build a PricePanel from ``{ticker: DataFrame[Close, (Adj Close), Volume]}``."""
    close, adj, vol = {}, {}, {}
    for ticker, raw in frames.items():
        if raw is None or len(raw) == 0 or "Close" not in raw.columns or "Volume" not in raw.columns:
            continue
        df = _clean_frame(raw)
        if df["Close"].notna().sum() < min_rows:
            continue
        close[ticker] = df["Close"].astype(float)
        adj[ticker] = (df["Adj Close"] if "Adj Close" in df.columns else df["Close"]).astype(float)
        vol[ticker] = df["Volume"].astype(float)
    if not close:
        raise ValueError("no usable price frames")
    c = pd.concat(close, axis=1).sort_index()
    a = pd.concat(adj, axis=1).reindex(c.index)
    v = pd.concat(vol, axis=1).reindex(c.index)
    c, a = c.where(c > 0), a.where(a > 0)
    v = v.where(v >= 0)
    keep = c.index[c.notna().any(axis=1)]
    return PricePanel(c.loc[keep], a.loc[keep], v.loc[keep])


def load_pickle_dir(path: str, tickers=None, max_tickers=None, min_rows: int = 210) -> PricePanel:
    files = sorted(glob.glob(os.path.join(path, "*.pkl")))
    if tickers is not None:
        wanted = {t.upper() for t in tickers}
        files = [f for f in files if os.path.basename(f)[:-4].upper() in wanted]
    if max_tickers:
        files = files[:max_tickers]
    frames = {os.path.basename(f)[:-4]: read_price_pickle(f) for f in files}
    return assemble_panel(frames, min_rows=min_rows)


def save_csv(frame: pd.DataFrame, path: str) -> None:
    out = frame[[c for c in ("Close", "Adj Close", "Volume") if c in frame.columns]].copy()
    out.index.name = "Date"
    out.to_csv(path, compression="gzip")


def load_csv_dir(path: str, tickers=None, max_tickers=None, min_rows: int = 210) -> PricePanel:
    files = sorted(glob.glob(os.path.join(path, "*.csv.gz")))
    if tickers is not None:
        wanted = {t.upper() for t in tickers}
        files = [f for f in files if os.path.basename(f)[:-7].upper() in wanted]
    if max_tickers:
        files = files[:max_tickers]
    frames = {
        os.path.basename(f)[:-7]: pd.read_csv(f, parse_dates=["Date"], index_col="Date") for f in files
    }
    return assemble_panel(frames, min_rows=min_rows)


def _extract_ticker(data: pd.DataFrame, ticker: str, batch_len: int):
    if isinstance(data.columns, pd.MultiIndex):
        if ticker in data.columns.get_level_values(0):
            return data[ticker]
        if ticker in data.columns.get_level_values(1):
            return data.xs(ticker, axis=1, level=1)
        return None
    return data if batch_len == 1 else None


def download_yfinance(tickers, start: str, out_dir: str, end: str | None = None,
                      batch_size: int = 50, pause: float = 1.0, overwrite: bool = False) -> int:
    """Download daily bars (unadjusted Close + Adj Close + Volume) to ``out_dir/<TICKER>.csv.gz``.

    Resumable: existing files are skipped unless ``overwrite``. Needs network
    access to Yahoo and the ``yfinance`` package (imported lazily).
    """
    import yfinance as yf  # noqa: WPS433 - lazy on purpose

    os.makedirs(out_dir, exist_ok=True)
    path_for = lambda t: os.path.join(out_dir, f"{t}.csv.gz")  # noqa: E731
    todo = [t for t in tickers if overwrite or not os.path.exists(path_for(t))]
    saved = 0
    for i in range(0, len(todo), batch_size):
        batch = todo[i:i + batch_size]
        data = yf.download(batch, start=start, end=end, auto_adjust=False,
                           group_by="ticker", progress=False, threads=True)
        for t in batch:
            df = _extract_ticker(data, t, len(batch))
            if df is None:
                continue
            df = df.dropna(how="all")
            if df.empty or "Close" not in df.columns:
                continue
            save_csv(df, path_for(t))
            saved += 1
        time.sleep(pause)
    return saved
