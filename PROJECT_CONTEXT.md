# Stock Momentum Agent — Project Context

## 1. Purpose

The Stock Momentum Agent is a Python-based portfolio analysis and decision system.

Its purpose is to:

* analyse stocks and ETFs;
* assess momentum, technical strength, quality and growth;
* calculate investment/recommendation scores;
* analyse the existing portfolio;
* produce portfolio-aware BUY / BUY MORE / HOLD / REDUCE / SELL decisions;
* allocate available and released capital;
* provide explainable, governed decisions rather than frequent trading.

The system is intended primarily for **long-term portfolio management**, not short-term trading.

---

## 2. Core Portfolio Philosophy

These principles are fundamental and should not be changed casually:

1. **HOLD is the default.**
2. Do not trade simply because a model produces a BUY or SELL signal.
3. Avoid unnecessary portfolio turnover.
4. Protect strong/core holdings unless there is a material reason to reduce them.
5. BUY NEW and BUY MORE compete based on the quality/opportunity of the investment, rather than automatically prioritising one over the other.
6. Released capital from justified reductions/sells should be recycled into the strongest available opportunities.
7. Decisions must be explainable, with reasons and confidence/evidence.
8. Portfolio context matters: position size, concentration, sector exposure, available cash and existing holdings must influence the final decision.
9. The system should favour **meaningful portfolio actions** rather than small trades that have little practical value.

---

## 3. High-Level Production Pipeline

The intended production flow is:

```text
Market Universe
    ↓
Universe Filtering
    ↓
Market Scan
    ↓
Stock / ETF Analysis
    ↓
Portfolio Analysis
    ↓
Recommendation / Investment Scoring
    ↓
Portfolio Decision Engine
    ↓
Final Portfolio Decision
    ↓
Capital Allocation
    ↓
Portfolio / Excel Reporting
```

The important boundary is that portfolio decisions must flow through the governed decision layer before capital is allocated.

Capital allocation must not silently erase an upstream REDUCE or SELL decision.

---

## 4. Stocks vs ETFs vs Cash

### Stocks

Stocks use the stock analytical model, including:

* technical/trend analysis;
* momentum;
* quality;
* growth;
* Investment Score;
* stock recommendation/signal.

### ETFs

ETFs are treated separately from stocks.

They should not be forced through the stock Investment Score model.

ETFs use ETF-specific assessment/scoring and can have their own BUY / HOLD / REDUCE logic.

Examples of ETFs encountered in the portfolio include:

* IWDA.L
* VUAA.L
* AEMD.L where applicable to the project's ETF classification logic
* SEC0.DE

Ticker classification must therefore be reliable, particularly for European UCITS ETFs.

### Cash

Cash is not an investment candidate and must never receive BUY / BUY MORE / SELL investment actions.

---

## 5. Portfolio Ownership

Actual ownership is determined from:

```text
portfolio/holdings_raw.csv
```

Positive quantity means the asset is owned.

Zero/non-existent quantity means it is not owned.

Ownership determines:

* BUY NEW vs BUY MORE;
* whether a reduction/sell applies to an existing position.

The capital allocator should not infer ownership from opportunity data alone.

---

## 6. Final Portfolio Decision Layer

The governed final portfolio decision layer combines:

* proposed action;
* investment/ETF score;
* technical evidence;
* quality;
* growth;
* recommendation signal;
* current allocation;
* portfolio constraints;
* evidence/reliability;
* AI review;
* reconciliation/governance rules.

The final decision should be explainable and should preserve valid upstream decisions.

### Critical handoff rule

An explicit upstream:

```text
REDUCE 25%
REDUCE 50%
REDUCE 75%
SELL
```

must not subsequently become HOLD merely because a downstream component has insufficient information or defaults to HOLD.

Similarly, an explicit downstream governed reduction must not be overwritten by an upstream HOLD.

The decision pipeline must reconcile these actions deliberately.

---

## 7. Reduction / Sell Rules

The reduction framework is:

```text
REDUCE 25% → release 25% of position
REDUCE 50% → release 50% of position
REDUCE 75% → release 75% of position
SELL       → release 100% of position
```

The allocator must never invent a reduction percentage for a bare REDUCE action.

### Minimum meaningful reduction rule

A reduction that would release less than the configured minimum meaningful reduction value is not useful as a partial trade.

Therefore:

```text
REDUCE X%
    ↓
released value below minimum meaningful reduction value?
    ↓
YES
    ↓
SELL / 100% reduction
```

It must **not** become HOLD.

This rule was identified and regression-tested using the real `CA.PA` position.

### CA.PA regression

Carrefour (`CA.PA`) is an existing stock holding.

The required behaviour is:

```text
CA.PA
Investment Score = 18
Signal = SELL
Proposed Action = SELL
Final Decision = SELL
Reduction = 100%
Released Capital = £3.47
```

The previous defect caused an explicit reduction/sell decision to become HOLD. That behaviour is now treated as a regression condition.

---

## 8. Capital Allocation

The production capital allocator is:

```text
analysis.capital_allocator.generate_capital_allocation()
```

It receives:

* portfolio summary;
* opportunities;
* portfolio decisions.

BUY NEW and BUY MORE candidates are placed into a common opportunity pool.

Priority is based on allocation opportunity/conviction:

```text
Stock → Investment Score
ETF   → ETF Score
```

A higher-scoring BUY NEW can therefore outrank a lower-scoring BUY MORE.

The allocator should:

* respect available discretionary capital;
* include capital released from reductions/sells;
* avoid allocating capital to CASH;
* avoid rebuying a position that has been completely sold in the same allocation cycle;
* respect maximum BUY NEW / BUY MORE safeguards;
* allocate capital according to conviction;
* avoid creating trades simply to consume available capital.

---

## 9. Evidence and AI Governance

AI is an advisory/governance layer, not a replacement for the deterministic portfolio rules.

The system should distinguish between:

* model evidence;
* evidence strength;
* AI review;
* decision confidence;
* reconciliation/governance status.

AI must not casually override a strong deterministic portfolio constraint.

Where an AI review disagrees with the proposed action, the disagreement should be visible and governed rather than silently changing the decision.

---

## 10. Recommendation Reliability

A longer-term objective is to calibrate recommendation reliability using historical outcomes.

This should:

* measure how reliable recommendations/signals have historically been;
* provide evidence to the portfolio decision layer;
* improve decision confidence.

It should **not automatically rewrite the core scoring weights** merely because historical outcomes differ.

Calibration is evidence for governance, not an uncontrolled feedback loop.

---

## 11. Portfolio Risk and Allocation

The portfolio decision layer should ultimately consider:

* current position size;
* portfolio allocation %;
* concentration;
* sector exposure;
* ETF/core-satellite exposure;
* maximum position limits;
* minimum meaningful trade size;
* available cash;
* capital released from justified reductions/sells;
* investment conviction;
* recommendation reliability;
* portfolio risk.

The objective is portfolio-aware capital management rather than isolated stock recommendations.

---

## 12. Coding / Engineering Principles

When changing the project:

* make the smallest change necessary to fix the identified defect;
* avoid unrelated refactoring;
* preserve established interfaces unless there is a clear reason to change them;
* add regression tests for important decision rules;
* keep production logic deterministic and explainable where possible;
* AI outputs must be governed;
* Python modules should have a clear top-of-file docstring/comment explaining their purpose and role;
* do not silently change business rules while fixing implementation bugs.

Tests should validate both individual functions and important production-path behaviour.

---

## 13. Current Stable Release

Current Git rollback point:

```text
v0.1.0-stable
```

Tag description:

```text
Stable release: governed portfolio decisions and capital allocation
```

Git is the authoritative source for code and release history.

The ChatGPT Project is a development/context workspace and should not be treated as the source of truth for the repository.

---

## 14. Current Key Production Modules

Important modules include:

```text
analysis/scorer.py
analysis/quality.py
analysis/growth.py
analysis/investment_score.py
analysis/recommendations.py
analysis/portfolio_analysis.py
analysis/portfolio_enrichment.py
analysis/portfolio_decision_engine.py
analysis/final_portfolio_decision.py
analysis/capital_allocator.py
analysis/portfolio_manager_rules.py

agents/ai_decision_reconciler.py
agents/ai_portfolio_reviewer.py

portfolio/portfolio.py

tests/
```

The actual Git repository remains authoritative if this context document differs from the code.

---

## 15. Current Development Priorities

### Priority 1 — Portfolio-aware capital allocation and position sizing

Continue improving allocation using:

* position size;
* portfolio percentage;
* investment score/conviction;
* sector exposure;
* ETF/core-satellite exposure;
* maximum position limits;
* minimum meaningful trade size;
* available capital;
* released capital.

### Priority 2 — Portfolio risk and recommendation reliability

Continue developing:

* historical recommendation reliability;
* evidence calibration;
* portfolio risk;
* concentration management;
* governed AI portfolio decisions.

Do not automatically rewrite the underlying scoring model as part of calibration.

### Priority 3 — ETF decision wiring

Complete and validate ETF-specific decision handling so ETFs are consistently:

* classified correctly;
* scored using ETF logic;
* governed through the final portfolio decision layer;
* handled correctly by capital allocation.

---

## 16. Important Working Rule for Future Changes

When debugging a portfolio decision defect, trace the complete handoff:

```text
Recommendation
    ↓
Portfolio Decision
    ↓
Final Portfolio Decision
    ↓
Capital Allocation
    ↓
Report
```

Do not assume the component where the incorrect output appears is necessarily the component that caused the defect.

In particular, verify that:

```text
explicit REDUCE / SELL
```

survives every downstream boundary.

When fixing a defect, first reproduce it with a focused regression harness, then make the smallest production change necessary, then rerun the focused test and the broader test suite.

---

## 17. Stable Baseline Principle

Before significant architectural changes:

1. commit the working state;
2. create an annotated Git tag;
3. verify the test suite;
4. then begin the next change.

Use Git tags as rollback points rather than relying on local `.bak` files or backup directories.

## 18. Current State / Known Issues

Current implementation status:

* Governed portfolio decision layer is implemented.
* Capital allocation is implemented and has been tested against real portfolio data.
* Stock decision flow is substantially implemented.
* ETF decision wiring is still being completed.
* Portfolio risk/reliability calibration remains future work.

Known issues / areas requiring validation:

* ETF price/quote retrieval can fail for some European UCITS tickers.
* ETF classification must remain robust for European tickers.
* Final decision reconciliation must be regression-tested whenever decision-layer logic changes.
* Capital allocation must be tested against the full production path, not just isolated allocator output.

Do not assume an item is fixed merely because the code contains an apparent implementation for it; verify through the relevant production-path test.
