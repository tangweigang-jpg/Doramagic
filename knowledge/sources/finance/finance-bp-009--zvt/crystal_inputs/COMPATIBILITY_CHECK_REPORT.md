# Domain Injection Compatibility Check — bp-009 pruned treatment

**Checked**: 2026-04-19T10:30:00+08:00
**Subjects**: 11 domain constraints (after Level-1 drops of C-9002/9003/9004/9012 → renumbered; current IDs: C-9001..C-9011)
**References**: 147 project constraints (LATEST.jsonl) + 12 spec_locks (SL-01..SL-12, from finance-bp-009-v5.3.seed.yaml)
**Overall verdict**: CONDITIONAL CLEAN — 1 blocker (finance-C-9002), 8 stage-rebinding warnings, 1 watch

---

## Per-Candidate Findings

| # | New ID | Original ID | Source BP | Status | Finding |
|---|---|---|---|---|---|
| 1 | finance-C-9001 | finance-C-026 | finance-bp-120 | WATCH (stage) | `performance_analysis` stage doesn't exist in ZVT; principle is sound but needs scope rebinding |
| 2 | finance-C-9002 | finance-C-247 | finance-bp-088 | **BLOCKER** | Signed-amount sign convention directly conflicts with SL-05 + SL-06 + ZVT TradingSignal model |
| 3 | finance-C-9003 | finance-C-017 | finance-bp-108 | WATCH (stage + overlap) | `signal_generation` stage non-existent; principle is sound but overlaps with SL-02 in ways that cause confusion |
| 4 | finance-C-9004 | finance-C-075 | finance-bp-085 | WATCH (stage + terminology) | `backtesting` stage non-existent; "startup candles" is freqtrade/backtrader idiom — ZVT uses `acc_window` |
| 5 | finance-C-9005 | finance-C-006 | finance-bp-108 | CLEAN | `data_collection` stage exists; principle is general and adds defensive coverage |
| 6 | finance-C-9006 | finance-C-091 | finance-bp-106 | WATCH (stage) | `returns_analysis` stage non-existent; annualization rule is finance-universal but has no ZVT hook |
| 7 | finance-C-9007 | finance-C-065 | finance-bp-108 | WATCH (stage) | `backtesting` stage non-existent; NaN warmup principle maps to ZVT's acc_window but uses finmarketpy terminology |
| 8 | finance-C-9008 | finance-C-204 | finance-bp-081 | WATCH | `target_scope=global`, no stage issue; but ZVT has no ML pipeline — this is dead code for bp-009 |
| 9 | finance-C-9009 | finance-C-053 | finance-bp-092 | WATCH (stage) | `portfolio_simulation` stage non-existent; analogous to ZVT's `sim_account` but no direct binding |
| 10 | finance-C-9010 | finance-C-057 | finance-bp-092 | WATCH (stage) | `portfolio_simulation` stage non-existent; same source-BP issue as C-9009 |
| 11 | finance-C-9011 | finance-C-130 | finance-bp-086 | WATCH (stage + edge) | edge `data_ingestion->data_filtering` non-existent in ZVT; overlaps with finance-C-070 and finance-C-133 |

---

## Detailed Conflict Analysis

### BLOCKER: finance-C-9002

**Domain rule**:
- when: "When implementing order direction logic in backtesting"
- action: "Use positive order amounts for buy (long) positions and **negative amounts for sell (short) positions** — maintain consistent sign convention throughout order processing and position calculation"

**Conflicts with**:
1. **SL-05**: `TradingSignal MUST have EXACTLY ONE of: position_pct, order_money, order_amount` (XOR enforcement at `trading/__init__.py:68`). SL-05 carries no sign semantics on these fields — they are treated as unsigned magnitudes.
2. **SL-06**: `filter_result column semantics: True=BUY, False=SELL, None/NaN=NO ACTION` (locked at `factor.py:475`). In ZVT, trade direction is encoded in `filter_result`, NOT in the sign of `order_amount`.
3. **finance-C-100**: "Divide total `position_pct` by number of target entities" — this assumes `position_pct` is always a positive fraction; negative values would produce inverted sizing.
4. **finance-C-090** / **finance-C-123**: Both specify that `order_amount` is one of the valid sizing fields in `TradingSignal` without any sign convention — treated as absolute quantity.

**Conflict type**: direct — C-9002's "negative for sell" prescription is architecturally incompatible with ZVT's direction-via-filter_result model.

**Evidence**:
- SL-06 locked_value: `factor.py:475 order_type_flag mapping` (True=BUY, False=SELL)
- SL-05 locked_value: `XOR enforcement in trading/__init__.py:68` (no sign check)
- finance-C-100 action: "Divide total position_pct by number of target entities" (unsigned arithmetic)
- Source blueprint for C-9002 is `finance-bp-088`, which implements a different backtesting engine where signed order amounts are the direction mechanism — incompatible model with ZVT.

**Severity**: blocker

**Recommendation**: **DROP finance-C-9002**. A skill agent internalizing this rule will either (a) attempt to set `order_amount` negative for sells, breaking `sim_account` accounting, or (b) face irreconcilable conflict with SL-06 and silently pick one. There is no safe "accept-with-note" path.

---

### WATCH: finance-C-9001 — Stage scope overreach

**Domain rule**:
- when: "When computing forward returns from price data"
- action: "use shift(-period) to correctly align future prices with current factor values"

**Stage in constraint**: `performance_analysis` — **does not exist in ZVT pipeline** (ZVT stages: `data_collection`, `data_storage`, `factor_computation`, `target_selection`, `trading_execution`, `visualization`, `cross_cutting_concerns`).

**Evidence from source**: Codebase ref is `alphalens-reloaded` (a factor analysis library — `finance-bp-120`), not ZVT. ZVT's performance analysis is done via `SimAccountService`, which produces `AccountStats`, not alphalens-style forward returns.

**Conflict type**: scope overreach

**Severity**: watch

**Recommendation**: The forward-return shift(-period) principle is finance-universal and correct. However, it only applies if a user is using alphalens on top of ZVT. Rewrite `applies_to.stage_ids` to `factor_computation` or `cross_cutting_concerns`, and add `context_requires: alphalens_workflow` to prevent blanket injection.

---

### WATCH: finance-C-9003 — Stage mismatch + potential confusion with SL-02

**Domain rule**:
- when: "When implementing indicator-based signal generation"
- action: "introduce inherent 1-period lag through rolling window or shift operations"

**Stage in constraint**: `signal_generation` — **does not exist in ZVT pipeline**.

**Overlap with SL-02**: SL-02 locks "next-bar execution" (`due_timestamp = happen_timestamp + level.to_second()`), which already guarantees that signals from any timestamp are executed at the next bar. A skill reading both C-9003 AND SL-02 may add an extra `.shift(1)` on top of the indicator, creating a **double-lag**: one in the indicator (per C-9003), one in execution (per SL-02). This would produce consistently late signals in backtests.

**Evidence**: C-9003 cites `finmarketpy` source (`techindicator.py:92`) — a different backtesting framework from ZVT. In finmarketpy, there is no SL-02-equivalent next-bar enforcement, so the indicator-level shift is the primary lag defense. ZVT has already solved this at the execution layer.

**Conflict type**: semantic overlap causing confusion

**Severity**: watch (not blocker — in isolation, ensuring indicator lag is harmless; the risk is additive misapplication with SL-02)

**Recommendation**: Accept-with-note. Add note: "In ZVT, SL-02 guarantees next-bar execution at the framework level. This rule's value is restricted to indicator purity (e.g., no current-bar close in rolling mean at time t). Do NOT add an additional .shift(1) on top of the indicator if SL-02 is already enforced."

---

### WATCH: finance-C-9004 — Stage mismatch + foreign terminology

**Domain rule**:
- when: "When preparing historical data for backtesting"
- action: "Verify startup candle count equals or exceeds longest indicator lookback period"

**Stage in constraint**: `backtesting` — **does not exist in ZVT pipeline**.

**Terminology mismatch**: "startup candles" is terminology from freqtrade/backtrader ecosystems. ZVT's equivalent mechanism is `acc_window` in `Accumulator` subclasses. ZVT's project constraints already address this:
- finance-C-052: "initialize acc_window parameter to at least the maximum rolling window size"
- finance-C-056: "set keep_window >= acc_window to verify accumulator has sufficient history"
- finance-C-069 and finance-C-130 also address accumulator window requirements.

**Conflict type**: semantic overlap (same concern, different vocabulary) + scope overreach

**Severity**: watch

**Recommendation**: Accept-with-note or rewrite. If kept, translate to ZVT vocabulary: "When configuring Accumulator subclasses, set acc_window >= longest indicator lookback period." Map to `factor_computation` stage. Note that finance-C-052/056/069/130 already cover the ZVT-specific enforcement.

---

### CLEAN: finance-C-9005

**Domain rule**:
- when: "When fetching market data from external data sources"
- action: "Implement fallback mechanism when data fetch returns None"

**Stage**: `data_collection` — **exists in ZVT pipeline**.

**Cross-check**: No project constraint directly conflicts. finance-C-024 covers HTTP error handling. finance-C-019 says "do NOT guarantee data completeness" (claim_boundary), complementary. None prescribes a specific fallback behavior that conflicts.

**Conflict type**: none

**Severity**: clean

**Note**: Evidence cites `finmarketpy` example — valid general pattern. ZVT's recorder architecture can return None on failed fetches; this rule correctly adds a defensive layer.

---

### WATCH: finance-C-9006 — Stage scope overreach

**Domain rule**:
- when: "When computing rolling volatility and Sharpe ratio"
- action: "annualize volatility using sqrt(APPROX_BDAYS_PER_YEAR) where APPROX_BDAYS_PER_YEAR equals 252"

**Stage in constraint**: `returns_analysis` — **does not exist in ZVT pipeline**.

**ZVT coverage**: ZVT has no built-in Sharpe ratio or rolling volatility stage. If a user adds performance analytics on top of ZVT output, this rule is valid. However, with a non-existent stage, a crystal compiler that passes constraints by stage intersection will not fire this rule at all.

**Conflict type**: scope overreach (no direct semantic conflict — rule is finance-universal)

**Severity**: watch

**Recommendation**: Remap `stage_ids` to `cross_cutting_concerns` (or `visualization` if used in reports). Add `context_requires: performance_analytics_workflow`. Rule content itself is uncontroversial.

---

### WATCH: finance-C-9007 — Stage mismatch

**Domain rule**:
- when: "When implementing volatility targeting with rolling window periods"
- action: "account for NaN values in the first N periods before the rolling window completes"

**Stage in constraint**: `backtesting` — **does not exist in ZVT pipeline**.

**ZVT equivalent**: ZVT's finance-C-052 handles this at the Accumulator level (`acc_window`). C-9007's principle — "set `lev_df[0:vol_periods] = np.nan`" — is implemented correctly in finmarketpy's backtestengine but translates to ZVT's Accumulator warmup handling.

**Conflict type**: scope overreach

**Severity**: watch

**Recommendation**: Remap `stage_ids` to `factor_computation`. Rewrite action to ZVT idiom: "When implementing rolling-volatility Accumulator, ensure NaN handling for initial acc_window periods." No content-level conflict.

---

### WATCH: finance-C-9008 — Dead code for bp-009

**Domain rule**:
- when: "When preparing datasets for machine learning model training and validation"
- action: "Split data temporally into TRAIN, VALID, TEST segments using date range boundaries"

**Stage**: `target_scope=global` (no stage restriction) — **passes the stage-filter test**.

**ZVT coverage**: ZVT has one ML-related use case (UC-114: SGD Machine Learning Prediction). However, the core ZVT architecture has no ML training pipeline. This constraint would only fire for a narrow UC-114 workflow. For the other 30 use cases, it is dormant.

**Conflict type**: scope overreach (latent; no direct conflict)

**Severity**: watch

**Recommendation**: Accept-with-note. Add `applies_to.context_requires: machine_learning_workflow` or `applies_to.uc_ids: [UC-114]` to prevent this rule from appearing in general backtest contexts where it causes confusion.

---

### WATCH: finance-C-9009 — Stage mismatch

**Domain rule**:
- when: "When validating position state during order execution"
- action: "validate position is finite during each order processing"

**Stage in constraint**: `portfolio_simulation` — **does not exist in ZVT pipeline**. ZVT equivalent is `trading_execution` + `SimAccountService`.

**ZVT coverage**: No project constraint explicitly requires `math.isfinite(position)` check. This rule adds defensive coverage — but with the wrong stage label, it will not bind to any ZVT execution gate if the compiler uses stage intersection.

**Source**: finance-bp-092 (not ZVT) — different simulation engine.

**Conflict type**: scope overreach

**Severity**: watch

**Recommendation**: Accept-with-note. Remap `stage_ids` to `trading_execution`. Action is valid defensive engineering even if not present in ZVT project constraints.

---

### WATCH: finance-C-9010 — Stage mismatch

**Domain rule**:
- when: "When processing order records to build trade records"
- action: "validate order size is greater than zero before creating trade records"

**Stage in constraint**: `portfolio_simulation` — **does not exist in ZVT pipeline**.

**ZVT coverage**: finance-C-090 and finance-C-102 cover TradingSignal integrity (XOR of sizing fields, assert-False on missing spec), but not explicit order_size > 0 validation. This adds a complementary guard.

**Conflict type**: scope overreach

**Severity**: watch

**Recommendation**: Accept-with-note. Remap `stage_ids` to `trading_execution`. Same source-BP issue as C-9009 (finance-bp-092). Content is additive, not conflicting.

---

### WATCH: finance-C-9011 — Stage + edge mismatch + semantic overlap

> **ID collision note**: The `_domain_provenance.original_id` for this constraint is `finance-C-130` (from finance-bp-086). The project LATEST.jsonl also has a `finance-C-130` (Accumulator acc_window constraint from bp-009 itself). These are two different constraints that happen to share the original ID — the domain renumbering to `finance-C-9011` resolves the collision. All references in this report to "finance-C-130" in the overlap section refer to the ZVT-native project constraint, not this domain rule.

**Domain rule**:
- when: "When implementing data ingestion to data filtering data flow"
- action: "Maintain chronological order with no temporal gaps in OHLCV bar timestamps"

**Edge in constraint**: `data_ingestion->data_filtering` — **neither of these stages nor this edge exists in ZVT pipeline**. ZVT flows through `data_collection -> data_storage -> factor_computation`.

**Source**: finance-bp-086 (not ZVT).

**Overlap**: Partial semantic coverage by existing project constraints:
- finance-C-070: "call fill_gap before computing to verify continuous timestamps for rolling windows" (ZVT-native, factor_computation stage)
- finance-C-133: "Kdata timestamps SHOULD align with trading calendar (no gaps for non-trading days)" (ZVT-native, data_storage→factor_computation edge)

C-9011's "no temporal gaps" requirement is addressed by fill_gap (C-070) and C-133. However, the chronological ordering requirement (not just gap-filling) is not explicitly stated in project constraints.

**Conflict type**: scope overreach + partial semantic overlap

**Severity**: watch

**Recommendation**: Accept-with-note. Remap to `target_scope: edge`, `edge_ids: ["data_collection->data_storage"]` (the nearest ZVT equivalent). Note the overlap with finance-C-070 and finance-C-133; C-9011 adds the explicit "chronological ordering" check not present in those constraints.

---

## 系统性问题汇总

### 问题一：Source Blueprint 全部非 ZVT

所有 11 条 domain constraints 均来自其他蓝图（finance-bp-081/085/086/088/092/106/108/120），未包含 finance-bp-009 本身的任何 constraint。这意味着：

1. 这些规则描述的是其他框架（finmarketpy / freqtrade / alphalens / 某 backtesting engine）的实现惯例，不是 ZVT 惯例。
2. `_domain_provenance.source_blueprint` 多条为 `"unknown"` — 来源可信度存疑。

**建议**：注入前将 `when`/`action` 中的外来术语翻译为 ZVT 等效概念（见下表）。

| 外来术语 | ZVT 等效 |
|---|---|
| startup candles | acc_window (Accumulator subclass parameter) |
| portfolio_simulation stage | trading_execution stage + SimAccountService |
| signal_generation stage | factor_computation stage |
| backtesting stage | factor_computation + trading_execution stages |
| performance_analysis stage | cross_cutting_concerns or visualization stage |
| returns_analysis stage | cross_cutting_concerns stage |
| positive/negative order amounts | filter_result True/False + unsigned TradingSignal fields |
| data_ingestion->data_filtering edge | data_collection->data_storage edge |

### 问题二：Stage ID 覆盖率

8/11 条约束引用 ZVT 不存在的 stage 或 edge。如果下游晶体编译器（crystal compiler）使用 stage intersection 过滤约束，这 8 条将在运行时被静默跳过，完全失效。

---

## Summary

| Category | Count | IDs |
|---|---|---|
| **Blocker** | 1 | finance-C-9002 |
| **Watch (stage rebinding required)** | 8 | finance-C-9001, C-9003, C-9004, C-9006, C-9007, C-9009, C-9010, C-9011 |
| **Watch (scope/context restriction needed)** | 1 | finance-C-9008 |
| **Clean** | 1 | finance-C-9005 |

### Action Items

1. **DROP finance-C-9002** — blocker, architecturally incompatible with SL-05 + SL-06 + ZVT TradingSignal model. (Brings total to 10 remaining.)

2. **Remap stage_ids** for C-9001/C-9003/C-9004/C-9006/C-9007/C-9009/C-9010/C-9011 before injection — use ZVT-native stage names. Without remapping, these rules will not bind to any ZVT execution gate.

3. **Translate terminology** for C-9003/C-9004/C-9007/C-9009/C-9010/C-9011 — replace foreign-framework idioms with ZVT-native equivalents (acc_window, filter_result, trading_execution, etc.).

4. **Add context guard** for C-9008 (`context_requires: machine_learning_workflow`) to prevent this rule from appearing in non-ML ZVT workflows.

5. **Accept-with-note** for C-9003 regarding SL-02 overlap — add inline note that C-9003 applies to indicator computation only; SL-02 covers execution lag; no extra `.shift(1)` should be added at the execution layer.
