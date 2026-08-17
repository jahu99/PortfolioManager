# Stock Momentum Agent — Call Chain & Redundancy Audit

**Baseline:** `66e1023` — `Cache Llama AI analyst responses`  
**Baseline tag:** `stable-baseline-66e1023`  
**Scope:** Architecture mapping and redundancy assessment only.  
**Important:** **No production files are to be removed, renamed, rewritten, or behaviourally changed as part of this audit.**

---

## 1. Executive architectural view

The current intended production flow is:

```text
Market / Universe Data
        |
        v
Technical Analysis / Stock Scoring
        |
        +--> Quality Score
        |
        +--> Growth Score
        |
        v
Investment Score
        |
        v
Stock Signal
        |
        v
Recommendation / Stock Intelligence
        |
        v
Portfolio Analysis
        |
        v
Portfolio Enrichment
        |
        v
Portfolio Action / Decision Context
        |
        v
Capital Allocation
        |
        v
Final Portfolio Decision
        |
        v
Reporting
```

The key architectural rule established in the current baseline is:

```text
Signal = stock-level intelligence
Action = portfolio-level decision
```

Therefore:

- `Signal=BUY` does **not** necessarily mean `Action=BUY`.
- `Signal=SELL` may become `Action=REDUCE`.
- An attractive stock may remain `HOLD` when the portfolio already has sufficient exposure.
- Capital Allocation is intended to be the authoritative source of transaction allocation/action information.
- Final Portfolio Decision is intended to consolidate that result into the final report-ready decision record.

This distinction must be preserved during future refactoring.

---

## 2. Current pipeline evidence

The existing pipeline harness explicitly describes the production sequence as:

```text
Synthetic Market Data
    ↓
Technical Score
    ↓
Quality Score
    ↓
Growth Score
    ↓
Investment Score
    ↓
Stock Signal
    ↓
Recommendation
    ↓
Portfolio Analysis
    ↓
Portfolio Enrichment
    ↓
Portfolio Action
    ↓
Capital Allocation
    ↓
Final Portfolio Decision
```

The harness imports these production functions:

- `analysis.scorer.score_stock`
- `analysis.quality.score_quality`
- `analysis.growth.score_growth`
- `analysis.investment_score.calculate_investment_score`
- `analysis.recommendations.generate_recommendation`
- `analysis.portfolio_analysis.analyse_portfolio`
- `analysis.portfolio_enrichment.enrich_portfolio_holdings`
- `analysis.capital_allocator.generate_capital_allocation`
- `analysis.final_portfolio_decision.generate_final_portfolio_decisions`

This is strong evidence for the intended core dependency chain.

---

## 3. Portfolio pipeline boundary

The current pipeline evidence shows the portfolio stage doing three distinct things:

### 3.1 Portfolio analysis

```text
build_portfolio()
    ↓
analyse_portfolio(portfolio, stock_results)
```

### 3.2 Portfolio enrichment

```text
analyse_portfolio(...)
    ↓
enrich_portfolio_holdings(...)
    ↓
PORTFOLIO_SUMMARY
```

### 3.3 Portfolio action boundary

```text
stock_results
    ↓
build_portfolio_decisions(...)
    ↓
PORTFOLIO_DECISIONS
```

This is an important architectural boundary because the project currently contains several modules that appear capable of producing portfolio-level decisions.

---

## 4. Capital Allocation

The current baseline evidence shows:

```text
PORTFOLIO_SUMMARY
       +
PORTFOLIO_DECISIONS
       +
STOCK_RESULTS / opportunities
       |
       v
generate_capital_allocation(...)
       |
       v
CAPITAL_ALLOCATION
```

The Capital Allocation engine's documented principles include:

- protect existing holdings unless an explicit reduction decision exists;
- prefer HOLD unless there is a meaningful reason to act;
- allocate released capital to stronger opportunities;
- BUY NEW and BUY MORE compete on conviction;
- do not create trades simply to consume available cash;
- use Investment Score for stocks;
- use ETF Score for ETFs.

Therefore Capital Allocation is currently a **high-value architectural component** and should not be treated as redundant merely because other modules also contain allocation/decision logic.

---

## 5. Final Portfolio Decision

The intended role of `analysis/final_portfolio_decision.py` is consolidation.

The module documentation states that it:

- consolidates portfolio analysis, AI analysis, portfolio management and capital allocation;
- treats Capital Allocation as authoritative for transaction actions;
- does not independently decide whether a security should be bought, increased, reduced or sold;
- defaults existing holdings absent from Capital Allocation to HOLD;
- adds BUY NEW opportunities from Capital Allocation;
- uses AI and portfolio analysis as context rather than transaction authority;
- avoids unnecessary turnover.

The intended flow is therefore:

```text
Portfolio Intelligence
        ↓
Capital Allocation
        ↓
Final Portfolio Decision
        ↓
Excel Report
```

This should be treated as the current architectural target.

---

# 6. Candidate redundancy map

The following are **candidates for investigation only**. They are not deletion recommendations.

| Component | Apparent responsibility | Initial status | Why investigate |
|---|---|---|---|
| `analysis.decision_engine.py` | Portfolio/decision logic | REDUNDANCY CANDIDATE | Another decision boundary exists in `final_portfolio_decision.py` |
| `analysis.portfolio_decision_engine.py` | Portfolio decision generation | REDUNDANCY CANDIDATE | Appears to overlap with `decision_engine.py` and final decision logic |
| `analysis.portfolio_decision.py` | Portfolio decision logic | REDUNDANCY CANDIDATE | Another portfolio decision implementation |
| `analysis.final_portfolio_decision.py` | Final consolidation | ACTIVE / AUTHORITATIVE CANDIDATE | Intended final transaction decision boundary |
| `analysis.capital_allocator.py` | Capital allocation | ACTIVE / AUTHORITATIVE | Current allocation engine |
| `analysis.capital_allocator_backup_662.py` | Older allocation implementation | BACKUP / LEGACY CANDIDATE | Filename and implementation indicate historical copy |
| `analysis.portfolio_manager.py` | Portfolio management | INVESTIGATE | May overlap with final decision / AI management |
| `analysis.portfolio_ai.py` | AI portfolio assessment | SUPPORTING / INVESTIGATE | May provide context rather than transaction authority |
| `analysis.stock_analyser.py` | Stock-level analysis | INVESTIGATE | Potential overlap with scorer/recommendation modules |
| `analysis.recommendations.py` | Stock recommendations | CORE / INVESTIGATE | Appears to sit upstream of portfolio decisions |
| `analysis.recommendation_intelligence.py` | Recommendation intelligence | SUPPORTING | Likely learning/measurement rather than live decision authority |
| `analysis.recommendation_learning.py` | Recommendation learning | SUPPORTING | Historical/adaptive learning |
| `analysis.adaptive_learning.py` | Adaptive learning | SUPPORTING / INVESTIGATE | Potential overlap with recommendation learning |
| `analysis/rebalance.py` | Rebalance recommendations | LEGACY / SECONDARY CANDIDATE | Appears to generate actions outside Capital Allocation |
| `analysis/trade_sizing.py` | Trade sizing | LEGACY / SECONDARY CANDIDATE | Potential overlap with Capital Allocation |
| `analysis/weight_optimizer.py` | Weight optimisation | SUPPORTING / INVESTIGATE | Potential overlap with portfolio optimiser |
| `analysis/portfolio_optimizer.py` | Portfolio optimisation | SUPPORTING / INVESTIGATE | Potential overlap with weight optimiser/rebalance |
| `analysis/portfolio_growth_engine.py` | Long-term portfolio growth | SUPPORTING | Separate strategic planning responsibility |
| `reports/excel_report.py` | Report rendering | ACTIVE | Output layer; not part of decision authority |

### Important

The above table is a **structural assessment**, not a deletion list.

A module must not be removed merely because its filename looks redundant.

---

# 7. Specific redundancy clusters

## 7.1 Decision engines — highest priority

Potential cluster:

```text
decision_engine.py
        |
portfolio_decision_engine.py
        |
portfolio_decision.py
        |
final_portfolio_decision.py
```

This is the most important redundancy cluster to understand.

The architectural question is:

> Which module actually owns the portfolio decision, and which modules are merely legacy/supporting implementations?

The current intended answer appears to be:

```text
Portfolio analysis / intelligence
        ↓
Capital Allocation
        ↓
Final Portfolio Decision
```

The other decision modules should therefore be traced to determine whether they are:

- called in production;
- called only by tests;
- used by learning/reporting;
- historical;
- or genuinely competing decision engines.

---

## 7.2 Capital allocation cluster

Potential cluster:

```text
capital_allocator.py
capital_allocator_backup_662.py
rebalance.py
trade_sizing.py
weight_optimizer.py
portfolio_optimizer.py
```

The key question is not whether these modules contain similar concepts.

The key question is:

> Which one is on the production path that determines actual allocation?

Current evidence strongly points to:

```text
analysis.capital_allocator.generate_capital_allocation
```

The others should be mapped by actual import/call references before any future consolidation.

---

## 7.3 Portfolio management / AI cluster

Potential cluster:

```text
portfolio_manager.py
portfolio_ai.py
ai_engine.py
decision_engine.py
final_portfolio_decision.py
```

These need to be separated by responsibility:

```text
AI analysis
    ≠
portfolio management context
    ≠
transaction authority
```

The final decision module should consume context rather than allow multiple managers to independently issue competing transactions.

---

## 7.4 Learning cluster

Potential cluster:

```text
recommendation_intelligence.py
recommendation_learning.py
adaptive_learning.py
recommendation_evaluator.py
learning_calibration.py
score_calibration.py
model_validation.py
```

These should initially be treated as **measurement/learning infrastructure**, not part of the core transaction decision chain, unless runtime tracing proves otherwise.

---

# 8. Vulture assessment

## Important limitation

This audit document was created from the available project evidence in the conversation/file context. The actual local Git working tree at:

```text
/Users/jameshulin/Documents/stock-momentum-agent
```

is not mounted into this execution environment.

Therefore I have **not fabricated a Vulture result**.

The Vulture assessment must be run against the actual checkout of:

```text
stable-baseline-66e1023
66e1023
```

with no working-tree modifications.

Run:

```bash
cd /Users/jameshulin/Documents/stock-momentum-agent

python -m vulture     .     --exclude-dir=.venv     --exclude-dir=.git     --exclude-dir=__pycache__     --exclude="*_backup.py"     --exclude="main_backup_before_epic15.py"
```

If Vulture is not installed:

```bash
pip install vulture
```

Then capture the result:

```bash
python -m vulture     .     --exclude-dir=.venv     --exclude-dir=.git     --exclude-dir=__pycache__     --exclude="*_backup.py"     --exclude="main_backup_before_epic15.py"     > reports/vulture_audit.txt
```

### Do not delete based on Vulture alone

Vulture identifies potentially unused Python objects. It does **not** prove that an object is architecturally redundant.

For every Vulture finding we need to classify it as:

1. **Production reachable**
2. **Test reachable**
3. **Dynamically referenced**
4. **CLI/tool entry point**
5. **Intentionally public API**
6. **Legacy**
7. **Actually dead**

Only category 7 becomes a serious deletion candidate.

---

# 9. Recommended combined redundancy matrix

The eventual authoritative matrix should look like this:

| Module | Imported by production | Called at runtime | Referenced by tests | Vulture finding | Architectural role | Candidate status |
|---|---:|---:|---:|---|---|---|
| `final_portfolio_decision.py` | ? | ? | ? | ? | Final decision consolidation | KEEP |
| `capital_allocator.py` | ? | ? | ? | ? | Capital allocation | KEEP |
| `decision_engine.py` | ? | ? | ? | ? | Decision logic | INVESTIGATE |
| `portfolio_decision_engine.py` | ? | ? | ? | ? | Decision logic | INVESTIGATE |
| `portfolio_decision.py` | ? | ? | ? | ? | Decision logic | INVESTIGATE |
| `capital_allocator_backup_662.py` | ? | ? | ? | ? | Historical allocation | INVESTIGATE |
| `portfolio_manager.py` | ? | ? | ? | ? | Portfolio management | INVESTIGATE |
| `portfolio_ai.py` | ? | ? | ? | ? | AI portfolio context | INVESTIGATE |
| `rebalance.py` | ? | ? | ? | ? | Rebalancing | INVESTIGATE |
| `trade_sizing.py` | ? | ? | ? | ? | Trade sizing | INVESTIGATE |

The missing columns should be populated from the actual checkout, not inferred.

---

# 10. Architectural rules going forward

These should be treated as guardrails during future epics.

### Rule 1 — One transaction authority

There should ultimately be one authoritative transaction decision path.

Current target:

```text
Capital Allocation
        ↓
Final Portfolio Decision
```

### Rule 2 — Signal is not Action

Stock-level signal generation must remain distinct from portfolio-level action.

### Rule 3 — Portfolio context precedes allocation

Allocation must consider:

- existing ownership;
- current portfolio weights;
- portfolio risk;
- conviction;
- sector exposure;
- released capital;
- available discretionary capital.

### Rule 4 — Final decision does not independently compete with Capital Allocation

Final Portfolio Decision should consolidate and explain the allocation result rather than create a competing allocation decision.

### Rule 5 — Reporting is downstream

`excel_report.py` should consume established outputs.

It should not become a second decision engine.

### Rule 6 — Learning is downstream/supporting unless explicitly promoted

Learning and recommendation evaluation should inform future model behaviour, but should not silently introduce a competing live transaction path.

### Rule 7 — Refactor only after the dependency map is known

No module should be removed because it "looks redundant".

---

# 11. Immediate next technical action

The next action is **not a code change**.

Run the Vulture audit on the stable checkout and combine it with an import/call graph.

The desired end product is:

```text
CALL CHAIN
+
IMPORT GRAPH
+
VULTURE FINDINGS
+
TEST REFERENCES
+
ARCHITECTURAL ROLE
=
REDUNDANCY MAP
```

Only after that map exists should we create a separate **Redundancy Reduction Epic**.

---

## 12. Current conclusion

The project has grown organically enough that filename-level reasoning is no longer reliable.

The biggest architectural risk is not the number of files itself. It is **multiple modules having overlapping authority over the same conceptual decision**.

The highest-priority cluster to resolve architecturally is therefore:

```text
decision_engine
portfolio_decision_engine
portfolio_decision
capital_allocator
final_portfolio_decision
```

The objective is not to simplify the code for its own sake.

The objective is to make the runtime architecture explicit so that future changes have a known place to belong — and so that we can remove genuine redundancy without accidentally changing behaviour that currently works.

**No production code should be changed as part of this audit.**
