"""Explicit exit-price assumptions for names whose prices stop.

A forward return needs an exit price. When a name has no price on the exit date
there are two very different situations, and silently forward-filling both is
how backtests flatter themselves:

* **Gap** - the series resumes later (a halt, a missing Yahoo bar). The last
  price is carried forward. Harmless when short; flagged so you can count it.
* **Terminal** - the series ends for good before the end of the panel (delisting,
  bankruptcy, takeover, ticker change). The last price is the best case. A
  ``delist_return`` is applied on top of it: 0.0 keeps the last price (optimistic
  for failures, fair for takeovers); e.g. -0.30 is a common stress assumption.

``grace_days``: a series that ends within this many rows of the panel end is
treated as not delisted yet (recent data lag), not as terminal.

With a survivors-only universe terminal events should be about zero; this
matters once delisted names are included, and the counts tell you whether it
does.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

OBSERVED, GAP, TERMINAL = 0, 1, 2


@dataclass
class ExitPrices:
    price: pd.DataFrame             # exit price to use on each date (forward-filled, haircut after termination)
    flags: pd.DataFrame             # OBSERVED / GAP / TERMINAL per date and ticker
    terminated_names: list = field(default_factory=list)


@dataclass(frozen=True)
class ExitModel:
    delist_return: float = 0.0
    grace_days: int = 5

    def build(self, adj: pd.DataFrame) -> ExitPrices:
        valid = adj.notna().to_numpy()
        n = valid.shape[0]
        any_valid = valid.any(axis=0)
        last_pos = np.where(any_valid, n - 1 - np.argmax(valid[::-1], axis=0), -1)
        ends_early = any_valid & (last_pos < n - 1 - self.grace_days)
        rows = np.arange(n)[:, None]
        terminated = (rows > last_pos[None, :]) & ends_early[None, :]

        price = adj.ffill()
        gap = adj.isna().to_numpy() & ~terminated & price.notna().to_numpy()
        if self.delist_return != 0.0:
            term_df = pd.DataFrame(terminated, index=adj.index, columns=adj.columns)
            price = price.where(~term_df, price * (1.0 + self.delist_return))

        flags = np.zeros(adj.shape, dtype=np.int8)
        flags[gap] = GAP
        flags[terminated] = TERMINAL
        return ExitPrices(price, pd.DataFrame(flags, index=adj.index, columns=adj.columns),
                          list(adj.columns[ends_early]))


def exit_event_summary(adj: pd.DataFrame, exits: ExitPrices, positions: np.ndarray, horizon: int,
                       lag: int = 1) -> dict:
    """How many forward-return observations rely on a gap fill or a terminal exit."""
    entry = positions + lag
    ex = entry + horizon
    ok = ex < len(adj)
    if not ok.any():
        return {"horizon_days": horizon, "observations": 0, "gap_filled": 0, "terminal": 0}
    entry_valid = adj.iloc[entry[ok]].notna().to_numpy()
    f = exits.flags.iloc[ex[ok]].to_numpy()
    return {"horizon_days": horizon, "observations": int(entry_valid.sum()),
            "gap_filled": int(((f == GAP) & entry_valid).sum()),
            "terminal": int(((f == TERMINAL) & entry_valid).sum())}
