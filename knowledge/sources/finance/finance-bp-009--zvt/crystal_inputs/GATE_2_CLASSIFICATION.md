# Gate-2 Action Substitution Risk — bp-009 v2 kept set

**Classified**: 2026-04-19
**Pool**: 7 constraints + 10 packages (post-Gate-1)

## Summary
- SAFE_KEEP: 6 constraints + 10 packages
- ACTION_SUBSTITUTION_RISK: 1 (drop)

## Per-Constraint Analysis

| new id | original id | project overlap (same trigger) | project action depth | domain action | verdict |
|---|---|---|---|---|---|
| finance-C-9001 | finance-C-026 | finance-C-061 ("use .shift() properly to avoid look-ahead bias") | C-061 states the principle; C-9001 *sharpens* it with explicit sign convention: `shift(-period)` vs `shift(period)` — orthogonal specificity | "use shift(-period) to correctly align future prices" | SAFE_KEEP |
| finance-C-9002 | finance-C-075 | finance-C-052 ("initialize acc_window to at least max rolling window") — different stage (Accumulator init, not startup candles for backtesting) | C-052 operates on Factor Accumulator state, not on raw historical data warmup period before indicators stabilize. No same-trigger project rule exists for startup candle count. | "verify startup candle count ≥ longest indicator lookback" | SAFE_KEEP |
| finance-C-9003 | finance-C-006 | finance-C-024 ("handle HTTP errors and JSON parsing exceptions"), finance-C-013 ("use sleeping_time intervals to avoid overwhelming external APIs") | Project requires: (1) classify exception types (HTTP vs JSON parse), (2) avoid crash with data gaps, (3) rate-limit via sleeping_time between attempts — a multi-step recovery protocol | "implement fallback mechanism when data fetch returns None" | ACTION_SUBSTITUTION_RISK |
| finance-C-9004 | finance-C-091 | None — project has zero constraints on volatility/Sharpe annualization | No project rule addresses rolling volatility computation or the sqrt(252) scaling convention. Pure additive domain knowledge. | "annualize volatility using sqrt(APPROX_BDAYS_PER_YEAR=252)" | SAFE_KEEP |
| finance-C-9005 | finance-C-065 | finance-C-052 (acc_window init for Accumulator) — different layer | C-052 is about Accumulator state initialization, not about explicitly zeroing out vol_periods NaN values in rolling leverage series. Different implementation context; no substitution path. | "account for NaN values in first N periods before rolling window completes" | SAFE_KEEP |
| finance-C-9006 | finance-C-204 | None — ZVT bp-009 has no ML training pipeline constraints | bp-009 is a data recorder + factor + backtest engine. No project constraint governs TRAIN/VALID/TEST temporal splitting. Additive domain rule from ML context. | "split data temporally into TRAIN/VALID/TEST using date range boundaries" | SAFE_KEEP |
| finance-C-9007 | finance-C-130 | finance-C-070 ("call fill_gap before computing"), finance-C-133 ("SHOULD align with trading calendar, no gaps") | C-070/C-133 prescribe *mechanisms* (fill_gap call, calendar alignment). C-9007 states the upstream *invariant* at ingestion. Host will not read "maintain chronological order with no gaps" and skip fill_gap — fill_gap is the remedy, not the antecedent. Complementary. | "maintain chronological order with no temporal gaps in OHLCV bar timestamps" | SAFE_KEEP |

## Per-Resource Analysis

| pkg | substitution risk? | reasoning |
|---|---|---|
| exchange-calendars | No | Adds trading calendar lookup; no project logic implements a custom calendar. Additive. |
| scikit-learn | No | Used for ML model training. bp-009 has no self-implemented ML to displace. |
| empyrical-reloaded | No | Performance metrics library. No project-level performance math to replace. |
| pyfolio-reloaded | No | Portfolio analytics reporting tool. No project tearsheet logic. |
| beautifulsoup4 | No | HTML/XML parsing. No project implements its own parser logic. |
| lightgbm | No | Gradient boosting library. No project model implementation displaced. |
| scipy | No | Scientific computing, orthogonal to project logic. |
| statsmodels | No | Statistical modeling, additive to project scope. |
| lxml | No | XML/HTML parsing backend for bs4. No project-level parser logic. |
| numba | No | JIT acceleration. No project implements custom accelerated computation. |

All 10 packages are additive tool dependencies. None replaces or renders obsolete any self-implemented project logic.

## Drop list (ACTION_SUBSTITUTION_RISK)

**Constraints to drop**: `finance-C-9003`
**Packages to drop**: (none)

## Evidence for each drop

### finance-C-9003 (original: finance-C-006)

**Domain rule when/action:**
- when: "When fetching market data from external data sources"
- action: "Implement fallback mechanism when data fetch returns None"
- evidence source: `finmarketpy_examples/tradingmodelfxtrend_example.py:139` — explicit `None` check with CSV fallback
- severity: high | constraint_kind: operational_lesson

**Project rules covering the same trigger (same when: external data fetch):**

1. **finance-C-024** (severity: high, constraint_kind: operational_lesson)
   - when: "When calling external API endpoints"
   - action: "handle HTTP errors and JSON parsing exceptions appropriately"
   - consequence: "Unhandled exceptions will crash the recording process, leaving entities unprocessed and creating data gaps in the database"
   - evidence: `em_api.py:43,208` catch Exception; `wb_api.py:81-90` raise ValueError for parsing errors

2. **finance-C-013** (severity: high, constraint_kind: resource_boundary)
   - when: "When running recorder in continuous mode"
   - action: "use specified sleeping_time intervals to avoid overwhelming external APIs"
   - consequence: "Excessive API call frequency may trigger rate limiting or IP blocking by external providers, causing data collection to fail entirely"
   - evidence: `recorder.py:136-144` implements sleep() between recording cycles

**Why host substitution occurs:**

The domain rule (C-9003) frames the entire problem as "check if fetch returns None → apply fallback." A host reading this rule can satisfy itself by writing:

```python
result = fetch_market(...)
if result is None:
    return []  # fallback: return empty list
```

This passes the domain rule's stated test (`if.*None` grep check per `validation_threshold`), yet:

- It **bypasses finance-C-024**: the crash-prevention requirement demands *classifying* the exception (HTTP error vs JSON parse failure vs credentials failure) and handling each appropriately — not silently swallowing all failure modes into a single `None` branch.
- It **bypasses finance-C-013**: the rate-limit avoidance requirement demands `sleeping_time` intervals between API attempts in continuous mode — silent `return []` leaves the recorder looping immediately to the next entity without back-off.

The v2 treatment regression on T3 confirms this exactly: treatment r1 "silently returns `[]`" satisfied the domain None-fallback semantics while bypassing the project's retry + classified error handling, producing worse outcomes than the baseline which implemented the full multi-step recovery.

**Substitution test (true subset check):**
- Domain action: `{check None → fallback}` — one guard, one recovery branch
- Project action (C-024 + C-013): `{classify exception type → handle HTTP separately from parse → avoid crash/data gap → sleep before retry cycle}` — multi-step recovery pipeline

Domain action ⊂ project action. C-9003 is a strict subset of the behavior C-024 + C-013 require. **Drop confirmed.**
