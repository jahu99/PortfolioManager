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

---

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

---

# 19. PROTECTED COMPLETED EPIC — GOVERNANCE AUDIT

## 19.1 Protection rule

**The governance audit implementation is a completed, working baseline and must be treated as protected functionality.**

When editing files for any future Stock Momentum Agent epic:

* **Do not modify, refactor, replace, simplify, or overwrite audit functionality as part of unrelated work.**
* Preserve the existing audit reconciliation behaviour.
* Preserve the existing audit persistence behaviour.
* Preserve the existing SQLite audit schema.
* Preserve the meaning of existing audit fields, reason codes, governance flags and persisted values.
* Preserve the existing audit interfaces unless an explicit audit change is required.
* Do not move audit responsibilities into another module merely for convenience.
* Do not replace persisted audit data with transient in-memory structures.
* Do not delete, reset, truncate, or overwrite historical audit records as part of normal development.
* Do not alter the audit implementation simply because another epic exposes a more convenient way to obtain or display the same information.
* Treat the existing governance audit harness and its passing behaviour as regression requirements for future changes.

If a future epic genuinely requires an audit change, that change must be explicitly identified as an **audit-impacting change** before implementation. It must be isolated from unrelated changes and the existing audit behaviour must be regression-tested afterwards.

### Golden rule

> **If a future change does not require changing audit, do not change audit.**

If a future change appears to require modifying audit, first determine whether the same requirement can be satisfied by changing the consuming component instead.

---

## 19.2 Audit architectural purpose

The audit system provides a persistent, inspectable and execution-specific record of governed portfolio decisions.

Its purpose is to answer, after the Python process has finished:

* What decision was made?
* What was the original action?
* What action was proposed?
* What action did governance reconcile?
* What was the final action?
* Did the action change?
* What scores and evidence supported the decision?
* Which governance checks failed?
* What thresholds were involved?
* What did the independent AI review say?
* Why was the final action accepted, challenged, rejected or changed?
* Which specific execution/run produced the record?

The audit trail is therefore part of the **decision-control architecture**, not merely a reporting feature.

---

## 19.3 Authoritative source of truth

SQLite is the **authoritative source of truth for decision audit data**.

The persisted relationship is:

```text
audit_runs
    │
    │ audit_run_id
    ▼
audit_decisions
    │
    │ audit_decision_id
    ▼
audit_reasons
```

The existing audit schema should not be changed merely to support reporting.

Historical audit records represent completed executions and should remain available for inspection.

New executions create new audit runs rather than overwriting previous runs.

---

## 19.4 Audit tables

### `audit_runs`

Identifies a specific execution:

```text
id
run_id
run_date
environment
code_version
status
total_decisions
changed_decisions
created_at
```

`audit_run_id` is the database primary identifier used to associate all decisions belonging to that execution.

### `audit_decisions`

Stores the decision-level audit record:

```text
id
audit_run_id
ticker
asset_type
original_action
proposed_action
reconciled_action
final_action
action_changed
original_signal
investment_score
technical_score
quality_score
growth_score
confidence_score
evidence_score
original_allocation_pct
final_allocation_pct
reconciliation_status
decision_stage
source_module
created_at
```

The record must retain the progression through the decision pipeline rather than only storing the final answer.

### `audit_reasons`

Stores the detailed persisted reasons associated with an audit decision:

```text
id
audit_decision_id
reason_code
reason_category
reason_description
actual_value
threshold_value
unit
severity
source_layer
created_at
```

`actual_value` and `threshold_value` are important. When a governance check fails, the audit should capture the **actual value and the threshold that it failed against**, rather than only recording a generic flag.

For example:

```text
reason_code:
BUY_MORE_DETERMINISTIC_CONFIDENCE_LOW

reason_description:
Confidence score of 62.0 below threshold of 70.0.

actual_value:
62.0

threshold_value:
70.0

unit:
percent

source_layer:
reconciliation
```

This makes the audit explainable and allows the database to answer exactly which governance requirement failed.

---

## 19.5 Audit production interfaces

The audit implementation exposes a small set of important responsibilities/interfaces.

### Database connection

The audit module owns the database connection mechanism:

```text
get_connection()
```

It opens the configured portfolio manager SQLite database.

### Audit run lifecycle

```text
start_audit_run(
    environment,
    code_version=None,
)
```

Creates a new `audit_runs` record and returns the database audit run ID and run metadata.

```text
complete_audit_run(
    audit_run_id,
    total_decisions,
    changed_decisions,
)
```

Marks an audit run as completed.

```text
fail_audit_run(
    audit_run_id,
)
```

Marks an audit run as failed.

### Decision persistence

The governed decision path records an individual decision through the production audit writer:

```text
record_decision_audit(
    conn,
    audit_run_id,
    base_row,
    chain,
    final_result,
)
```

This is the important production persistence boundary.

It persists the decision-level information together with the associated audit reasons.

### Compatibility API

The audit module also has a compatibility interface for simple decision dictionaries:

```text
record_audit_decision(
    audit_run_id,
    decision,
)
```

This wrapper must continue to use the same underlying audit-writing implementation rather than creating a second, divergent audit persistence path.

### Batch audit

```text
record_audit_decisions(
    audit_run_id,
    decisions,
)
```

Records a collection of decisions and calculates the run-level decision/change counts.

### Complete run

```text
audit_decision_run(
    decisions,
    environment,
    code_version=None,
)
```

Provides the complete audit lifecycle:

```text
start run
    ↓
record decisions
    ↓
record reasons
    ↓
complete run
```

If an audit error occurs, the run is marked failed and the exception is re-raised.

---

## 19.6 Reason normalisation contract

Reasons can be supplied as structured dictionaries or simple strings.

The normalisation layer maps structured reasons into the persisted audit schema.

Structured reasons may contain:

```text
reason_code
reason_category
reason_description
actual_value
threshold_value
unit
severity
source_layer
```

The persisted representation must preserve these values.

Do not regress structured governance failures into generic strings.

In particular, a governance failure such as:

```text
Investment Score = 38
minimum required = 40
```

should remain capable of being persisted as:

```text
actual_value = 38
threshold_value = 40
unit = score
```

rather than only:

```text
"Investment Score too low"
```

The descriptive text is useful for humans; the actual/threshold values are required for precise auditability.

---

## 19.7 Reconciliation-to-audit boundary

The governance reconciler determines the governed outcome.

The audit layer records that outcome and the supporting governance evidence.

Conceptually:

```text
Deterministic decision
        ↓
AI review
        ↓
Governance reconciliation
        ↓
Final governed action
        ↓
Audit persistence
```

The audit layer must **not silently invent a different decision** from the reconciler.

The persisted audit record should make visible:

```text
original action
    ↓
proposed action
    ↓
reconciled action
    ↓
final action
```

including whether the action changed.

---

## 19.8 Governance failure audit contract

Whenever a governance requirement causes an action to be blocked or changed, the audit should capture:

1. a governance flag identifying the failed requirement;
2. a human-readable governance reason;
3. the actual value where applicable;
4. the threshold value where applicable;
5. the unit;
6. the source layer;
7. the final action change where applicable.

For example, a BUY MORE governance override should be capable of producing records equivalent to:

```text
GOVERNANCE_FLAG_BUY_MORE_GOVERNANCE_REQUIREMENTS_NOT_MET
GOVERNANCE_FLAG_DETERMINISTIC_CONFIDENCE_TOO_LOW
GOVERNANCE_REASON
GOVERNANCE_REASON
BUY_MORE_DETERMINISTIC_CONFIDENCE_LOW
ACTION_CHANGED
```

with the dedicated failed-check reason carrying the numerical evidence:

```text
actual_value = 62.0
threshold_value = 70.0
unit = percent
```

The same principle applies to Investment Score, allocation limits, evidence scores, confidence, and other governed thresholds.

---

## 19.9 Governance audit regression harness

The production audit path is validated by:

```text
tests/test_governance_audit_harness.py
```

The harness is an integration-style test rather than merely a unit test.

It deliberately uses controlled decision-chain data and the real production audit writer so that the audit database can be tested independently of live market data and the LLM.

The harness verifies scenarios including:

* BUY MORE governance override;
* BUY NEW with weak deterministic evidence;
* justified REDUCE;
* SELL with deterministic/AI alignment;
* HOLD with deterministic/AI alignment;
* BUY MORE blocked by low deterministic confidence;
* BUY MORE blocked by excessive allocation.

The harness verifies both:

```text
audit_decisions
```

and:

```text
audit_reasons
```

and deliberately leaves records in:

```text
data/portfolio_manager.db
```

for manual SQLite inspection.

A successful run should report:

```text
GOVERNANCE AUDIT HARNESS PASSED
```

The harness should be treated as a protected regression test for the audit implementation.

---

## 19.10 Audit data is append-oriented

Each execution should create a new audit run.

Conceptually:

```text
Run 19
    ├── decisions
    └── reasons

Run 21
    ├── decisions
    └── reasons

Run 22
    ├── decisions
    └── reasons

Next production run
    ├── decisions
    └── reasons
```

A new run must not overwrite the audit records from a previous run.

The `audit_run_id` is therefore critical to traceability.

Development/test harnesses may deliberately create additional test records, but normal production execution must create a distinct run.

---

## 19.11 Final Portfolio Decisions reporting interface

The **Final Portfolio Decisions** Excel worksheet should obtain its `Audit Reason` from persisted SQLite audit records.

It should **not** depend on an audit-reason object being passed through the production pipeline in memory.

The intended reporting flow is:

```text
Report execution
      ↓
explicit audit_run_id
      ↓
SQLite audit_runs
      ↓
audit_decisions
      ↓
audit_reasons
      ↓
reporting query / aggregation
      ↓
Final Portfolio Decisions
      ↓
Excel "Audit Reason" column
```

The report must use the **explicit `audit_run_id` associated with that report execution**.

It must not simply query the "latest audit run", because another audit execution could occur between decision processing and report generation.

A small dedicated database read function should retrieve the persisted audit reasons for the specified run.

The reporting preparation function can then match those persisted reasons to the final portfolio decision by ticker/audit decision.

### Executive presentation of reasons

The database remains the detailed audit source.

The Excel worksheet should not necessarily reproduce every individual audit reason record. Instead:

* retain all detailed reason records in SQLite;
* use meaningful `MATERIAL` reasons for the executive-facing `Audit Reason`;
* aggregate multiple related reasons into a concise explanation;
* include the final action change where applicable.

The distinction is:

```text
SQLite audit_reasons
    = detailed, authoritative audit trail

Excel Audit Reason
    = executive reporting representation of that audit trail
```

---

## 19.12 Rebuild requirements

If the audit implementation ever has to be rebuilt, the replacement must preserve the following externally observable contract:

### Persistence

* SQLite remains the authoritative audit store.
* Audit runs remain execution-specific.
* Historical runs remain inspectable.
* New runs do not overwrite prior runs.

### Relationships

```text
audit_runs.id
    ↓
audit_decisions.audit_run_id

audit_decisions.id
    ↓
audit_reasons.audit_decision_id
```

### Decision traceability

Each audited decision must retain:

```text
original_action
proposed_action
reconciled_action
final_action
action_changed
```

plus the relevant scores/evidence fields.

### Reason traceability

Each material governance reason must retain:

```text
reason_code
reason_category
reason_description
actual_value
threshold_value
unit
severity
source_layer
```

### Numerical governance evidence

Where a rule fails against a threshold, the actual and threshold values must be persisted.

The replacement must not reduce this to generic prose.

### Production interfaces

The replacement must provide equivalent responsibilities for:

```text
get_connection()
start_audit_run()
complete_audit_run()
fail_audit_run()
record_decision_audit()
record_audit_decision()
record_audit_decisions()
audit_decision_run()
normalise_reason()
```

The exact internal implementation may change only if the externally observable behaviour and data contract remain intact.

### Reporting

The Final Portfolio Decisions report must continue to use:

```text
explicit audit_run_id
```

to retrieve persisted audit reasons.

It must not rely on transient audit structures remaining in memory.

### Regression

The governance audit harness must continue to pass, including verification of both decision records and reason records.

---

## 19.13 Rules for future epic development

Before editing an existing file for a new epic, determine whether that file is part of the protected audit path.

Audit-sensitive components currently include, at minimum:

```text
analysis/audit.py
agents/ai_decision_reconciler.py
tests/test_governance_audit_harness.py
data/portfolio_manager.db
```

and any reporting code that reads the persisted audit data.

If a new epic touches one of these components:

1. identify the audit impact explicitly;
2. preserve the existing interfaces and schema unless the audit change is intentional;
3. avoid unrelated audit refactoring;
4. run the governance audit harness after the change;
5. verify persisted `actual_value` / `threshold_value` data for representative failed checks;
6. verify historical audit runs remain intact;
7. only then consider the audit-impacting change complete.

For an unrelated epic, the preferred approach is:

```text
NEW EPIC
   ↓
change only required non-audit components
   ↓
leave audit implementation untouched
   ↓
verify existing audit regression harness
```

The burden of proof is on a proposed change to demonstrate why the protected audit implementation must change.

---

## 19.14 Current audit baseline

The governance audit implementation has been exercised successfully through the production audit persistence path.

The latest known successful governance audit harness run demonstrated:

```text
Audit run ID: 22
Decision records: 7
Reason records: 33
GOVERNANCE AUDIT HARNESS PASSED
```

The test also verified that a BUY MORE deterministic-confidence failure can now persist the numerical governance evidence:

```text
BUY_MORE_DETERMINISTIC_CONFIDENCE_LOW
actual_value = 62.0
threshold_value = 70.0
unit = percent
source_layer = reconciliation
```

This is part of the protected audit baseline.

Future development should preserve this level of audit detail.

---

## 20. Architectural Principle

Avoid passing large audit structures through memory merely because they are convenient for reporting.

Persisted database tables should be preferred where data needs to be:

* traceable;
* reproducible;
* linked to a specific execution;
* available to downstream reporting;
* inspectable after the Python process has ended.

This is part of the broader architectural direction to reduce fragile in-memory data passing and increase the use of persisted data tables.

The audit system is therefore both:

```text
a governance control
+
a persistent historical record
```

and should be protected accordingly.
