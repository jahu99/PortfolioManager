# ETF issuer holdings cache

The SHADOW portfolio-risk assessment reads issuer-published ETF holdings from this directory. It does not download holdings or infer constituents.

Create one UTF-8 CSV per ETF ticker:

`data/cache/etf_holdings/{TICKER}.csv`

For example: `data/cache/etf_holdings/VUAA.L.csv`.

## Required columns

| Column | Meaning |
|---|---|
| `constituent_ticker` | Underlying security ticker or stable identifier |
| `weight` | Decimal portfolio weight; 0.025 means 2.5% |
| `sector` | Issuer/source sector classification |
| `industry` | Issuer/source industry classification |
| `country` | Underlying issuer country classification |
| `as_of_date` | Holdings observation date, ISO `YYYY-MM-DD` |
| `source` | Issuer URL or exact issuer document name |
| `retrieved_at` | UTC retrieval timestamp, ISO 8601, e.g. `2026-11-03T12:00:00+00:00` |

Repeat the same `as_of_date`, `source` and `retrieved_at` on every row in a file.

## Validation and use

- The application rejects missing columns, blank or duplicate constituent identifiers, invalid weights, inconsistent metadata, future dates and stale evidence.
- Observation date and retrieval timestamp must both be no more than 45 days old.
- Constituent weights must total between 95% and 105%. Any residual is not silently assigned to a sector, country or industry.
- Weights must be decimal fractions, not percentages.
- Sector, country and industry classification coverage is assessed separately. Missing classifications remain unclassified.
- Current and proposed ETF values use the same holdings snapshot. This is a static look-through, not a forecast of future ETF composition.
- Source provenance and evidence dates are retained in the risk report.
- ETF look-through is advisory-only and cannot change production decisions, eligibility, sizing or trades.

Use issuer-published holdings files only. Do not substitute third-party estimates, ETF name-based guesses, exchange domicile or listing country for constituent exposure.
