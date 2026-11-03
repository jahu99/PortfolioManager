# Point-in-time backtest (`backtest_pit`)

Answers one question honestly: **does a factor rank stocks by what they go on to earn, using only information
available at the time?** It replaces `backtest.py`, which picks today's top-ranked stocks and tests them over the
past (look-ahead bias).

## Run it

```bash
pip install pandas numpy scipy          # plus `ta` only if you want the live-scorer parity test
python -m unittest tests.test_pit_backtest -v     # 25 tests; one needs `pip install ta` to run

# 1. smoke test on the price cache already in the repo (about 2 years)
python -m backtest_pit.run --prices-dir data/cache/prices --format pickle

# 2. the real test: download a longer history, then evaluate 1, 3, 6 and 12 month horizons
python -m backtest_pit.download --tickers-file data/sp500.csv --tickers SPY --start 2012-01-01 --out data/pit_prices
python -m backtest_pit.run --prices-dir data/pit_prices --format csv --horizons 21 63 126 252 --benchmark SPY
```

Outputs go to `reports/pit_backtest/`: `report.md` (read this), `factor_summary.csv`, `per_date_*.csv`,
`portfolio_*.csv`.

## Inspecting what a portfolio actually held

Each `portfolio_<factor>.csv` has a `holdings` column (the 20 tickers chosen each month). To see which names drive
a result, and whether they are recent index additions (a sign of look-ahead through today's membership):

```bash
python - <<'EOF'
import pandas as pd, collections
d = pd.read_csv("reports/pit_backtest/portfolio_mom_12_1.csv", index_col=0, parse_dates=True)
early = d[d.index < "2019-01-01"]
print("most frequent holdings before 2019:")
print(collections.Counter(t for h in early.holdings for t in h.split(";")).most_common(25))
EOF
```

## What it does

* **Causal factors, all dates at once.** Only backward-looking rolling/shift/ewm operations. A test corrupts every
  price after a cut-off and asserts nothing at or before it changes; it was verified to catch a planted peek-ahead,
  a centred rolling window and a full-sample z-score.
* **Execution lag.** Signal at close `t`, trade at close `t+1`, total-return (dividend-adjusted) prices.
* **Causal eligibility.** Price >= 5 and 20-day median dollar volume >= 1m, computed from data up to `t`.
* **Rank IC and quintile spreads** per month-end, with moving-block bootstrap intervals and a Bonferroni-adjusted
  interval for the number of factor x horizon tests. Intervals are withheld below 12 independent periods.
* **A `random` factor** as a noise gauge, alongside `technical_score` (a vectorised copy of
  `analysis/scorer.py`), `mom_12_1` and `mom_6_1`.
* **Top-N portfolio** with rank hysteresis (`--exit-rank`), random tie-breaking (the live allocator breaks ties
  alphabetically), per-trade costs and turnover, compared with the raw equal-weight universe.

## Exit and benchmark conventions

* **Exits.** `exits.py` separates a gap (series resumes: last price carried forward) from a terminal exit (series
  ends for good). `--delist-return -0.3` applies a haircut to terminal exits; `--exit-grace-days` (default 5) treats a
  series ending just before the panel end as data lag. The report counts both kinds, and warns if over 2% of tickers
  "end early", which means a stale or ragged download rather than real delistings.
* **Benchmarks.** Portfolio excess is shown against the equal-weight universe (like-for-like) and against `--benchmark`
  (e.g. SPY). The gap between those two mixes survivorship and equal- versus cap-weighting, so it is not model edge.
* **Intervals.** Portfolio excess uses a 3-month block bootstrap and a Bonferroni-adjusted interval.

## What it cannot tell you (yet)

1. **Survivorship bias.** The universe is whatever tickers you load: names that exist today. Failed companies are
   missing, which flatters long-only results. Fix: historical index or exchange membership including delisted names.
2. **Quality and growth scores are untested.** They come from Yahoo's snapshot of today's fundamentals, so scoring
   the past with them would leak the future. Fix: point-in-time fundamentals from SEC filings keyed by filing date.
   Until then, only price/volume factors can be validated, and the combined `Investment Score` cannot.
3. **Sample length.** The cached prices cover about two years. That supports 1 and 3 month horizons only roughly;
   12-month horizons need the longer download.
4. `download.py` needs network access to Yahoo and was not exercised in the sandbox this was written in.
5. The `technical_score` parity test against the live `analysis.scorer` is skipped unless `ta` is installed. Run it.

## Adding a factor

Write `(PricePanel, seed) -> DataFrame (date x ticker)` using only backward-looking operations and add it to
`FACTORS` in `factors.py`. The look-ahead test picks it up automatically.

## Decision rule

A factor goes into the live score only if the adjusted IC interval excludes zero, IC is positive in most dates, the
top-N portfolio beats the universe after costs with an interval that excludes zero, and the result holds in each
half of the sample. If the `random` row ever looks significant, distrust everything else in that run.
