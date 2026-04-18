# I help you build quant strategies on A-share with ZVT — from data fetch to backtest, one flow

> **Authoritative reference**: `seed.yaml` (finance-bp-009-v5.2) — this file is a derived summary and MUST NOT be relied upon for behavioral decisions. Always re-read seed.yaml.

## 1. What This Skill Does

I help you build quant strategies on A-share with ZVT — from data fetch to backtest, one flow. Just tell me what you want; I'll write the code, you don't have to dig docs. (Heads up: ZVT natively supports A-share, HK, and crypto. US stocks — stockus_nasdaq_AAPL — are half-baked; don't bother for serious work.)

I help you build quant strategies on A-share with ZVT — from data fetch to backtest, one flow.

### Capability Catalog (5 groups, 31 use cases)

#### 📊 Data Collection (8 UCs)

_Fetch market / fundamental / alternative data from various providers_

| UC-ID  | Name                               | Short Description                                                                                                                          | Triggers                                              |
| ------ | ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------- |
| UC-101 | Actor Data Recorder                | Collects institutional investor holdings and top 10 free float shareholders on a weekly schedule for tracking major player positions       | institutional investor, top holders, actor data       |
| UC-102 | Financial Statement Recorder       | Collects fundamental financial data including balance sheets, income statements, and cash flow statements from eastmoney on a weekly basis | financial statements, balance sheet, income statement |
| UC-103 | Index Data Recorder                | Collects index metadata, index compositions (SZ1000, SZ2000, growth, value indices), and daily index price data                            | index data, index composition, SZ1000                 |
| UC-104 | Joinquant Fund Data Recorder       | Collects fund information, fund holdings (which stocks funds own), and individual stock valuations from Joinquant provider                 | fund holdings, fund data, stock valuation             |
| UC-105 | Joinquant Stock Kdata Recorder     | Collects A-share stock list and post-adjustment (hfq) daily price data from Joinquant after market close                                   | stock kdata, price data, hfq                          |
| UC-106 | Stock News and Limit Up Recorder   | Records stock news headlines and limit-up (涨停) tracking information for each normal stocks on weekdays                                     | stock news, limit up, 涨停                              |
| UC-107 | Sina Block and Money Flow Recorder | Collects block (concept/industry sector) classifications and sector-level money flow data from Sina                                        | block, concept, sector                                |
| UC-108 | Dragon and Tiger Data Recorder     | Records dragon and tiger list data (top gaining/losing stocks by trading volume) and tracks top-performing brokerages                      | dragon tiger, 龙虎榜, top traders                        |

#### 🧮 Factor & Stock Selection (3 UCs)

_Compute technical/fundamental factors and select target stocks_

| UC-ID  | Name                              | Short Description                                                                                                                              | Triggers                                            |
| ------ | --------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------- |
| UC-109 | Bollinger Bands Technical Factor  | Implements Bollinger Bands indicator with upper/lower bands and bandwidth/percentage bands for volatility-based trading signals                | bollinger bands, volatility, bandwidth              |
| UC-110 | Good Company Fundamental Selector | Screens for quality companies using criteria: high ROE, strong cash flow, high dividends, low receivables, low capital expenditure, and growth | fundamental screening, good company, quality stocks |
| UC-114 | SGD Machine Learning Prediction   | Uses Stochastic Gradient Descent classifiers and regressors to predict stock behavior patterns and price movements                             | machine learning, SGD, prediction                   |

#### 📈 Strategy Backtest & Live Trading (7 UCs)

_Simulate, validate and execute trading strategies_

| UC-ID  | Name                                   | Short Description                                                                                                      | Triggers                                                       |
| ------ | -------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------- |
| UC-111 | Bull and Up Technical Factor           | Combines MACD indicator with moving average cross signals to identify bull market uptrends                             | MACD, bull market, moving average                              |
| UC-125 | Dragon Tiger Follower Trader           | Executes trades following institutional-only dragon and tiger list entries with filtering for institutional专用 seats    | follow institutional, dragon tiger trader, institutional seats |
| UC-126 | Institutional Investor Follower Trader | Follows institutional investor activities by tracking raised funds and executing based on significant position changes | follow institutional, raised fund, institutional tracking      |
| UC-127 | Multi-Level Bull Run Trader            | Combines weekly MACD (BullFactor) with gold cross factors across multiple timeframes using top fund holdings           | multi timeframe, bull run, weekly MACD                         |
| UC-128 | Moving Average Crossover Trader        | Executes trades based on moving average crossovers using configurable windows (5,10) or BullFactor MACD signals        | MA crossover, moving average, gold cross                       |
| UC-129 | MACD Gold Cross Day Trader             | Day-level trading strategy using MACD gold cross signals with profit control (stop loss/take profit) overrides         | MACD, gold cross, day trader                                   |
| UC-130 | MACD Multi-Timeframe Trader            | Combines weekly and daily MACD gold cross signals for more robust trading decisions across multiple timeframes         | MACD, multi timeframe, weekly daily                            |

#### 📋 Research & Reports (12 UCs)

_Generate insights, analysis reports, and portfolio reviews_

| UC-ID  | Name                              | Short Description                                                                                                             | Triggers                                             |
| ------ | --------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------- |
| UC-112 | Cross-Asset Comparison Intent     | Compares different markets and assets: China vs US stocks, US yields vs stocks, commodities vs stocks, metals comparisons     | compare markets, cross-asset, China US comparison    |
| UC-115 | Stock Tag Query Utilities         | Provides utilities to query stocks by tags, find stocks without tags, and get delisted stock lists for data management        | stock tags, query by tag, tagged stocks              |
| UC-116 | Report Utilities Framework        | Provides reusable reporting utilities including email notifications, stock grouping by topic/tag, and performance statistics  | reporting, email notification, stock grouping        |
| UC-117 | Bull Stock Report                 | Generates weekly reports identifying bull market stocks using the BullAndUpFactor with turnover and volume filters            | bull stocks, weekly report, uptrend                  |
| UC-118 | Core Company Fundamental Report   | Generates weekly fundamental stock selection reports using the FundamentalSelector for core quality companies                 | core company, fundamental report, quality stocks     |
| UC-119 | Top Performance Stocks Report     | Identifies and reports top-performing stocks by market cap, short-term, and long-term performance categories                  | top stocks, best performers, top gainers             |
| UC-120 | Volume Breakout Stocks Report     | Reports stocks breaking out with volume surge through half-year or full-year moving averages, separated by market cap         | volume breakout, 放量突破, year MA breakout              |
| UC-121 | Dragon and Tiger Analysis         | Analyzes dragon and tiger list data to identify big trading players and their historical success rates over various intervals | dragon tiger, big players, seat analysis             |
| UC-122 | Top Dragon Tiger Players Research | Tracks top-performing monthly stocks and analyzes which trading seats (brokerages) appear in their dragon tiger lists         | top stocks, dragon tiger, player tracking            |
| UC-123 | Monthly Top Stocks Tags Analysis  | Analyzes monthly top 30 performers to understand market cap distribution and tag patterns among high-performing stocks        | monthly top, market cap, stock tags                  |
| UC-124 | Tag and Concept Utilities         | Provides utilities for mapping stocks to industry sectors, concept tags, and analyzing limit-up reasons by topic              | industry tag, concept mapping, sector classification |
| UC-131 | Hot Topics Analysis Utilities     | Provides utilities for counting hot words in text, grouping stocks by topic/hot keywords, and analyzing market themes         | hot words, topic detection, keyword analysis         |

#### 🔧 Tools & Extensions (1 UCs)

_Custom extension examples and utility helpers_

| UC-ID  | Name                     | Short Description                                                                                                   | Triggers                                  |
| ------ | ------------------------ | ------------------------------------------------------------------------------------------------------------------- | ----------------------------------------- |
| UC-113 | Schema Migration Example | Demonstrates how to extend ZVT schema with custom user tables using SQLAlchemy declarative base and Pydantic models | schema extension, custom table, migration |

### Quick Start

- **Find stocks in MACD bullish state** → routes to `UC-111`
- **Pick fundamentally strong companies (ROE >= 2%)** → routes to `UC-110`
- **Collect dragon-tiger board data** → routes to `UC-108`

Tell me which one you want to try.

Ask me 'what else can you do?' to see all 31 capabilities.

## 2. Execution Protocol

**Install trigger**: When seed.yaml is submitted without explicit execution intent (e.g. file upload, skill registration command)

**Execute trigger**: When user intent matches intent_router.uc_entries[].positive_terms AND user uses action verb (run/execute/跑/执行/backtest/fetch/collect)

**On execute, the agent MUST**:

1. Reload seed.yaml (do not rely on SKILL.md or cached summaries)
2. Run preconditions[] in declared order; halt on first fatal failure with on_fail message to user
3. Enter context_state_machine.CA1_MEMORY_CHECKED state
4. Evaluate evidence_quality.enforcement_rules[]; fire triggers that match declared state
5. Translate user_facing_fields to user locale per locale_contract

## 3. Preconditions (4 checks)

| ID    | Description                                                     | Check                                                                                                                                                                                               | On Fail                                                                                                                                     | Severity |
| ----- | --------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- | -------- |
| PC-01 | zvt package installed and importable                            | `python3 -c 'import zvt; print(zvt.__version__)'`                                                                                                                                                   | Run: python3 -m pip install zvt  then re-run: python3 -m zvt.init_dirs to initialize data directories                                       | fatal    |
| PC-02 | K-data exists for target entities (required before backtesting) | `python3 -c "from zvt.api.kdata import get_kdata; df = get_kdata(entity_ids=['stock_sh_600000'], limit=1); assert df is not None and len(df) > 0, 'No kdata found'"`                                | Run recorder first: python3 -m zvt.recorders.em.em_stock_kdata_recorder --entity_ids stock_sh_600000  (replace with your target entity IDs) | fatal    |
| PC-03 | ZVT data directory initialized (~/.zvt or ZVT_HOME)             | `python3 -c "import os; from pathlib import Path; zvt_home = Path(os.environ.get('ZVT_HOME', Path.home() / '.zvt')); assert zvt_home.exists(), f'ZVT home not found: {zvt_home}'"`                  | Run: python3 -m zvt.init_dirs                                                                                                               | fatal    |
| PC-04 | SQLite write permission for ZVT data directory                  | `python3 -c "import os, tempfile; from pathlib import Path; zvt_home = Path(os.environ.get('ZVT_HOME', Path.home() / '.zvt')); test_f = zvt_home / '.write_test'; test_f.touch(); test_f.unlink()"` | Check directory permissions: chmod u+w ~/.zvt  or set ZVT_HOME environment variable to a writable location                                  | warn     |

## 4. Evidence Quality Declaration

- verify_ratio: 44.3%
- audit fail total: 36

**Active enforcement rules**:

- **EQ-01**: When `declared.evidence_verify_ratio < 0.5` → MUST `MUST invoke traceback lookup for all cited BD-IDs in output before emitting business code — read LATEST.yaml sections for each BD referenced` (violation: `EQ-01-V`)
- **EQ-02**: When `declared.audit_fail_total > 20` → MUST `MUST prepend user_disclosure_template (translated to user locale) to first user-facing response` (violation: `EQ-02-V`)

## 5. Semantic Locks (Violation = Fatal)

| SL-ID | Locked Value                                                                | Source BDs     |
| ----- | --------------------------------------------------------------------------- | -------------- |
| SL-01 | sell() called before buy() in each Trader.run() iteration                   | BD-018         |
| SL-02 | due_timestamp = happen_timestamp + level.to_second()                        | BD-014, BD-025 |
| SL-03 | stock_sh_600000 | stockhk_hk_0700 | stockus_nasdaq_AAPL                     | n/a            |
| SL-04 | df.index.names == ['entity_id', 'timestamp']                                | n/a            |
| SL-05 | XOR enforcement in trading/__init__.py:68                                   | n/a            |
| SL-06 | factor.py:475 order_type_flag mapping                                       | n/a            |
| SL-07 | compute_result(): transform at :403 before accumulator at :409              | n/a            |
| SL-08 | factors/algorithm.py:30 macd(slow=26, fast=12, n=9)                         | BD-036         |
| SL-09 | sim_account.py:25 SimAccountService default costs                           | BD-029         |
| SL-10 | sim_account.available_long filters by trading_t                             | n/a            |
| SL-11 | contract/recorder.py:71 Meta; register_schema decorator                     | n/a            |
| SL-12 | result_df.columns.intersection({'filter_result', 'score_result'}) non-empty | n/a            |

## 6. Output Validator Assertions

Each assertion has a business_meaning; purely structural checks are forbidden:

- **OV-01** — all(p in inspect.getsource(zvt.factors.algorithm.macd) for p in ['slow=26', 'fast=12', 'n=9'])
  - Meaning: Standard MACD parameters are a semantic lock; drift makes results incomparable with industry-standard indicators and non-reproducible.
  - Sources: SL-08, BD-036
- **OV-02** — result.get('total_trades', 0) > 0 or result.get('explicit_zero_trade_ack') is True
  - Meaning: A backtest with zero trades is not a valid result; either data is missing or the strategy never triggered. Structural non-emptiness check is insufficient — we need business confirmation.
  - Sources: SL-01, finance-C-073
- **OV-03** — result.get('annual_return') is None or abs(float(result['annual_return'])) <= 5.0
  - Meaning: Annual returns exceeding 500% are physically implausible for A-share strategies; indicates look-ahead bias or corrupt data.
- **OV-04** — result.get('holding_change_pct') is None or abs(float(result['holding_change_pct'])) <= 1.0
  - Meaning: Holding change percentage cannot exceed 100%; violation indicates position accounting error.
  - Sources: BD-029
- **OV-05** — result.get('max_drawdown') is None or abs(float(result['max_drawdown'])) <= 1.0
  - Meaning: Maximum drawdown cannot exceed 100% without leverage; violation indicates calculation error or look-ahead bias.
- **OV-06** — not (hasattr(result, 'trade_log') and result.trade_log and any(result.trade_log[i].action == 'sell' and i+1 < len(result.trade_log) and result.trade_log[i+1].action == 'buy' and result.trade_log[i].timestamp == result.trade_log[i+1].timestamp for i in range(len(result.trade_log)-1)))
  - Meaning: SL-01 requires sell() before buy() in each cycle; violation means available_long was not updated before buying, risking duplicate positions.
  - Sources: SL-01

## 7. Hard Gates (Acceptance)

| G-ID | Check                                                                                 | On Fail                                                                                                              |
| ---- | ------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| G1   | {workspace}/result.csv exists AND file size > 0                                       | Strategy did not produce output; check run_backtest() return value and enforce_validation() call                     |
| G2   | {workspace}/result.csv.validation_passed marker file exists                           | Validation did not complete; review validate.py output and fix assertion failures                                    |
| G3   | Main script contains literal: from validate import enforce_validation                 | Validation chain stripped; re-add the import in the DO NOT MODIFY block                                              |
| G4   | Main script contains literal: # === DO NOT MODIFY BELOW THIS LINE ===                 | Validation fence removed; regenerate DO NOT MODIFY tail block                                                        |
| G5   | result.csv has at least 1 row: pandas.read_csv(result_csv).shape[0] >= 1              | Empty result; check if trade_log is non-empty and factors generated signals. Confirm PC-02 (k-data exists) passed.   |
| G6   | If MACD strategy: source contains 'slow=26' AND 'fast=12' AND 'n=9' in algorithm call | MACD params drifted from SL-08 lock; restore standard (12, 26, 9)                                                    |
| G7   | For data pipeline tasks: result.csv columns include 'entity_id' and 'timestamp'       | Missing required columns; check Mixin.query_data return schema and DataFrame MultiIndex reset_index() before writing |
| G8   | OV-03 passes: abs(annual_return) <= 5.0 (500%)                                        | Physical plausibility check failed; investigate look-ahead bias or data corruption in input kdata                    |

## 8. Skill Crystallization

After all Hard Gates pass, agent MUST emit `.skill` to `{workspace}/../skills/{slug}.skill`. Captured fields: name, intent_keywords, entry_point_script, validate_script, fatal_constraints, spec_locks, preconditions, human_summary_translated.

**Action**: After G1-G8 PASS, write .skill YAML file at {workspace}/../skills/fin-bp-009-uc_101.skill then notify user in user's locale: 'Skill saved as fin-bp-009-uc_101.skill — say backtest or zvt next time to invoke directly.'

**Violation signal**: All hard gates passed but no .skill file exists at expected path
---
*Generated from finance-bp-009-v5.2 by crystal_skill_readme_emitter.py. Regenerate whenever seed.yaml changes.*
