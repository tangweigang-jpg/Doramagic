# Gate-1 Coverage-Density Classification — bp-009 domain injection v1

**Classified**: 2026-04-19
**Pool**: 10 domain constraints + 10 domain packages
**Classifier**: sonnet, reading project LATEST.jsonl (147 constraints) + SL registry (12 SL) + stack (10 pkgs)

## Summary

- SPARSE: 9 (保留)
- STRENGTHEN: 3 (保留作补强)
- DILUTE: 3 (drop from injection)
- Drop rate: 3/20 = 15%

**Note on stage mapping quality**: Six of the ten domain rules reference stages not present in bp-009's pipeline (`performance_analysis`, `returns_analysis`, `backtesting`, `signal_generation`, `portfolio_simulation`). The project's pipeline is `data_collection → data_storage → factor_computation → target_selection → trading_execution → visualization`. Stage mismatch does not change the coverage-density verdict — it is recorded here as a mapping-quality signal for future domain-rule curation.

---

## Per-Constraint Classification

| new id | original id | classification | project rule overlap | rationale |
|---|---|---|---|---|
| finance-C-9001 | finance-C-026 | SPARSE | none — stage `performance_analysis` absent in project; C-061 and SL-02/C-099/C-151 cover *signal execution timing*, not forward-return computation for factor evaluation | No project constraint mandates `shift(-period)` for return alignment in a factor-analysis context. Distinct behavioral dimension — keep. |
| finance-C-9002 | finance-C-017 | DILUTE | **SL-02** (fatal): `due_timestamp = happen_timestamp + level.to_second()` — enforces next-bar execution at the hardcoded signal scheduling layer; **finance-C-099** (high, trading_execution): "Calculate due_timestamp as happen_timestamp plus the interval level duration" | SL-02 is a fatal spec lock imposing next-bar delay at the ZVT API level, which is strictly stronger than the domain rule's generic "introduce 1-period lag through rolling/shift." The project's mechanism is ZVT-native and already enforced architecturally. Domain rule adds nothing and introduces imprecise framing that could conflict with ZVT's timestamp arithmetic. DILUTE. |
| finance-C-9003 | finance-C-075 | STRENGTHEN | **finance-C-052** (high, factor_computation): "initialize acc_window parameter to at least maximum rolling window size" — governs state retention during *incremental* compute, not initial data loading | C-052 addresses how much history the accumulator retains between runs; C-9003 addresses ensuring the initial dataset fed to backtesting has enough pre-run candles to prime all indicators. These are complementary concerns at different lifecycle points. Domain rule is more specific on the initial loading side. STRENGTHEN. |
| finance-C-9004 | finance-C-006 | SPARSE | No project constraint mandates explicit fallback/retry when `fetch_market` returns `None`. finance-C-019 (medium) says "must_not guarantee data completeness" — this is a disclaimer, not a fallback implementation rule. finance-C-004 and finance-C-007 cover recorder method contracts, not None-return handling. | No project constraint enacts a None-check + fallback mechanism for data fetches. SPARSE — keep injection. |
| finance-C-9005 | finance-C-091 | SPARSE | No project constraint covers annualization using `sqrt(252)` or `APPROX_BDAYS_PER_YEAR`. Project pipeline has no `returns_analysis` stage. The Sharpe/volatility scaling dimension is entirely absent from the 147 project constraints. | Pure addition — no overlap found. SPARSE. |
| finance-C-9006 | finance-C-065 | STRENGTHEN | **finance-C-052** (high): acknowledges NaN production for first `max(window)` periods and mandates acc_window ≥ max rolling window; **finance-C-056** (high): `keep_window >= acc_window` for sufficient rolling history | C-052/056 are upstream preventive rules (set the window correctly). The domain rule adds a downstream handling requirement: explicitly zero/mark-as-NaN the initial `vol_periods` rows in the output. Different point of enforcement; the domain rule hardens behavior the project rules leave implicit. STRENGTHEN. |
| finance-C-9007 | finance-C-204 | SPARSE | No project constraint covers temporal TRAIN/VALID/TEST splitting. finance-C-204 does not appear in LATEST.jsonl (was drawn from a different blueprint). The project's ML dimension (sgd, classification) is mentioned in intent_keywords but has zero constraint coverage in LATEST.jsonl. | Entirely uncovered dimension in the project. SPARSE. |
| finance-C-9008 | finance-C-053 | DILUTE | **SL-05** (fatal): "TradingSignal MUST have EXACTLY ONE of: position_pct, order_money, order_amount — XOR enforcement"; **finance-C-102** (fatal, trading_execution): "Trigger assert False to prevent silent signal processing failures"; **finance-C-125** (high): "TradingSignal MUST have valid kdata (close price not None) at happen_timestamp" | The project enforces position-state validity at the signal contract level (SL-05 XOR + C-102 assert) and at the kdata-validity check (C-125). The domain rule's "validate position is finite during each order processing" is a weaker, more generic check than the project's typed-contract + hard-assert + kdata-gating combination. Project version is more precise and modality is stronger (fatal SL). DILUTE. |
| finance-C-9009 | finance-C-057 | DILUTE | **finance-C-100** (high, trading_execution): "Divide total position_pct by number of target entities" — ensures order_amount is structurally positive via proportional allocation; **finance-C-102** (fatal): assert False on missing order spec; **SL-05** (fatal): XOR enforcement on order fields | The domain rule "validate order size is greater than zero" is subsumed by the project's structural guarantees: C-100 computes a positive fraction, SL-05 ensures exactly one order-spec field is set, C-102 hard-asserts on spec absence. A domain-level "size > 0" check adds no new constraint above these — the action is already strictly covered. DILUTE. |
| finance-C-9010 | finance-C-130 | STRENGTHEN | **finance-C-133** (medium, `should`): "Kdata timestamps SHOULD align with trading calendar"; **finance-C-070** (medium, factor_computation): "call fill_gap before computing to verify continuous timestamps for rolling windows" | The project rules are weaker on two dimensions: (1) C-133 uses `should` vs. domain rule's `must`; (2) both project rules apply at factor_computation stage, while domain rule targets the data ingestion → filtering edge (earlier and more upstream). Domain rule upgrades enforcement modality from SHOULD to MUST and moves the check earlier in the pipeline. STRENGTHEN. |

---

## Per-Resource Classification

| pkg name | classification | project overlap | rationale |
|---|---|---|---|
| exchange-calendars | SPARSE | not in stack | Project uses `arrow` for date arithmetic; no trading-calendar library present. Pure addition for calendar-aware scheduling. |
| scikit-learn | SPARSE | not in stack | No ML-specific constraint or package in project stack. Covers the ML dimension noted in intent_keywords but absent from constraints. |
| empyrical-reloaded | SPARSE | not in stack | No performance-metrics library in stack. Covers returns/Sharpe/drawdown computation entirely absent from project. |
| pyfolio-reloaded | SPARSE | not in stack | Portfolio tearsheet analysis not present in any project constraint or stack package. Pure addition. |
| beautifulsoup4 | SPARSE | not in stack | Project uses `requests` for HTTP; no HTML parser. Complementary (not displacing). |
| lightgbm | SPARSE | not in stack | No gradient-boosting library in stack. Adds capability not covered by any project tool. |
| scipy | SPARSE | not in stack | No scientific computing library in stack beyond numpy/pandas. Complement, not displacement. |
| statsmodels | SPARSE | not in stack | No econometrics/stats library in stack. Pure addition for time-series modeling. |
| lxml | SPARSE | not in stack | Complement to beautifulsoup4; no XML/HTML parser in stack. |
| numba | SPARSE | not in stack | No JIT/performance library in stack. Pure addition for numeric acceleration. |

**Confidence caveat**: The project fingerprint's `stack` field lists 10 packages, which likely represents the top declared dependencies, not the full transitive environment. It is possible that some of these packages (e.g., scipy, numba) are present as transitive dependencies of numpy/pandas in the actual runtime. This does not change the SPARSE classification — a transitive dependency without a declared project constraint still represents a dimension without explicit coverage — but consumers of this classification should verify against the full `requirements.txt` or `pyproject.toml` before asserting zero overlap.

---

## Drops Recommended

**Domain constraints to drop (DILUTE)**:
- `finance-C-9002` (orig: finance-C-017) — 1-period signal lag, superseded by SL-02 fatal lock + C-099
- `finance-C-9008` (orig: finance-C-053) — position isfinite, superseded by SL-05 + C-102 assert + C-125
- `finance-C-9009` (orig: finance-C-057) — order size > 0, superseded by C-100 proportional allocation + SL-05 + C-102

**Domain packages to drop (DILUTE)**: none

---

## Keeps (SPARSE + STRENGTHEN)

**Constraints**:
- `finance-C-9001` — SPARSE: `shift(-period)` forward return alignment (performance_analysis, not covered)
- `finance-C-9003` — STRENGTHEN: startup candle count ≥ lookback (complements C-052 at load time)
- `finance-C-9004` — SPARSE: fetch-returns-None fallback (no project retry/fallback rule found)
- `finance-C-9005` — SPARSE: sqrt(252) Sharpe annualization (entirely absent from project)
- `finance-C-9006` — STRENGTHEN: NaN first vol_periods rows (complements C-052/C-056 with explicit downstream handling)
- `finance-C-9007` — SPARSE: temporal TRAIN/VALID/TEST split (ML dimension not covered)
- `finance-C-9010` — STRENGTHEN: chronological OHLCV order at ingestion (upgrades C-133 SHOULD→MUST, enforces earlier)

**Packages**: all 10 kept (exchange-calendars, scikit-learn, empyrical-reloaded, pyfolio-reloaded, beautifulsoup4, lightgbm, scipy, statsmodels, lxml, numba)
