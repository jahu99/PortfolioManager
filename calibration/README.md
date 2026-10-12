# BUY NEW Calibration V1

Offline research only. Nothing in this package is imported by `main.py`.

V1 uses persisted `recommendations` + `recommendation_evidence` as the point-in-time SMA observation. This avoids applying today's fundamentals/valuation to historical dates. It then measures realised forward performance for S&P 500 / Nasdaq-100 winners.

Known limitations:
- current constituent lists are used by default; historical index membership is not reconstructed yet;
- historical fundamentals/valuation are used only when they were persisted in the evidence layer;
- candidate rank/top-3 lineage is only reported where persisted audit data establishes it;
- no production DB rows, thresholds, weights, learning data, portfolio state, or decisions are modified.

Run from repository root:

```bash
python -m calibration.buy_new_calibration --start-date 2026-08-01 --end-date 2026-09-25 --universe BOTH --top-n 10 --forward-days 28
```
