# Human Review Checklist — finance-bp-009--zvt

- **Sources**: `scored_constraints.jsonl` (60 scored), `scored_resources.yaml` (40 scored)
- **Targets**: Top-15 constraints + Top-10 resources
- **Action**: Reply in chat with drop-indices, format:
  `drop constraints: 2,7,9; drop resources: 3`
- **Score legend**: a=alignment · act=actionability · nr=non_redundancy · roi=token_roi · c=confidence · total=weighted

---
## Constraints — Top 15 of 47 passed (target: 15)

**Review each row. Reply in chat with comma-separated indices to DROP. Default: keep all.**

| # | ID | Score | One-line reason (sonnet) |
|---|---|---|---|
| 1 | `finance-C-026` | **0.89** | shift(-period) for forward-return alignment is directly applicable to ZVT factor computation and prevents critical look-ahead bias. |
| 2 | `finance-C-076` | **0.89** | Entry-signal price timing at current open (not future candle) is a critical look-ahead prevention rule for ZVT backtesting. |
| 3 | `finance-C-008` | **0.88** | Incremental data collection from last stored date is a core ZVT data pipeline pattern for Chinese market data. |
| 4 | `finance-C-059` | **0.88** | Preserving pandas Series index in TA function wrappers directly applies to ZVT's technical indicator pipeline using pandas. |
| 5 | `finance-C-247` | **0.88** | Order direction sign convention (+/-) is a critical contract for ZVT's position management and backtesting accuracy. |
| 6 | `finance-C-017` | **0.88** | 1-period inherent lag for indicator signals is a fundamental anti-look-ahead rule applicable to all ZVT technical signals. |
| 7 | `finance-C-075` | **0.88** | Startup candle warmup >= max indicator lookback is a critical rule for ZVT's MACD/MA/Bollinger indicator initialization. |
| 8 | `finance-C-006` | **0.88** | None-return fallback for external data fetch is critical for ZVT's robustness against network/API failures from Chinese data sources. |
| 9 | `finance-C-091` | **0.86** | Annualizing volatility with sqrt(252) trading days is directly applicable to ZVT performance reporting and Sharpe calculation. |
| 10 | `finance-C-065` | **0.86** | NaN warmup period handling in rolling calculations is a concrete, frequent bug pattern in ZVT's pandas-based indicator pipeline. |
| 11 | `finance-C-204` | **0.86** | Temporal data splitting for ML training is essential for ZVT's prediction pipeline to prevent look-ahead bias. |
| 12 | `finance-C-258` | **0.86** | DEMA formula correctness is directly relevant to ZVT's moving average indicator implementation. |
| 13 | `finance-C-053` | **0.86** | Position finiteness validation during order execution is a concrete guard for ZVT's trading execution pipeline. |
| 14 | `finance-C-057` | **0.86** | Positive order size validation before trade record creation is a concrete guard for ZVT's order execution pipeline. |
| 15 | `finance-C-130` | **0.86** | Chronological OHLCV order in data ingestion is fundamental to ZVT's data pipeline and prevents look-ahead bias. |

### Details

**#1 `finance-C-026`** — total **0.89** · domain_rule · fatal

- **when**: When computing forward returns from price data
- **action**: use shift(-period) to correctly align future prices with current factor values
- **consequence**: Using shift(period) instead of shift(-period) introduces look-ahead bias, causing future information to be used in historical analysis and producing backtests that cannot be replicated in live trading
- **sonnet score**: a=0.90 act=0.95 nr=0.80 roi=0.90 c=0.90
- **rationale**: shift(-period) for forward-return alignment is directly applicable to ZVT factor computation and prevents critical look-ahead bias.

**#2 `finance-C-076`** — total **0.89** · domain_rule · fatal

- **when**: When simulating entry signals in backtesting
- **action**: Process entry signals at current candle open price, not future candles
- **consequence**: Entry signals using future price data create look-ahead bias, causing backtest results to be unrealistically profitable
- **sonnet score**: a=0.90 act=0.95 nr=0.80 roi=0.90 c=0.90
- **rationale**: Entry-signal price timing at current open (not future candle) is a critical look-ahead prevention rule for ZVT backtesting.

**#3 `finance-C-008`** — total **0.88** · domain_rule · high

- **when**: When incrementing stock day data in MongoDB
- **action**: query the last stored date from database and only fetch data after that date
- **consequence**: Re-downloading existing data causes duplicate entries and incorrect backtest results due to overlapping timestamps
- **sonnet score**: a=0.90 act=0.90 nr=0.80 roi=0.85 c=0.90
- **rationale**: Incremental data collection from last stored date is a core ZVT data pipeline pattern for Chinese market data.

**#4 `finance-C-059`** — total **0.88** · domain_rule · fatal

- **when**: When implementing SMA or other TA-Lib functions to accept pandas Series input
- **action**: Return pandas.Series with the same index preserved from the input Series
- **consequence**: Breaking pandas index preservation causes downstream code to lose temporal alignment, leading to incorrect backtest results and misaligned signal generation
- **sonnet score**: a=0.90 act=0.90 nr=0.80 roi=0.85 c=0.90
- **rationale**: Preserving pandas Series index in TA function wrappers directly applies to ZVT's technical indicator pipeline using pandas.

**#5 `finance-C-247`** — total **0.88** · domain_rule · fatal

- **when**: When implementing order direction logic in backtesting
- **action**: Use positive order amounts for buy (long) positions and negative amounts for sell (short) positions — maintain consistent sign convention throughout order processing and position calculation
- **consequence**: Inverting the order sign convention causes buy orders to be interpreted as sells and vice versa, resulting in completely opposite trading behavior with catastrophic losses in backtest and live trading
- **sonnet score**: a=0.90 act=0.90 nr=0.80 roi=0.85 c=0.90
- **rationale**: Order direction sign convention (+/-) is a critical contract for ZVT's position management and backtesting accuracy.

**#6 `finance-C-017`** — total **0.88** · domain_rule · fatal

- **when**: When implementing indicator-based signal generation
- **action**: introduce inherent 1-period lag through rolling window or shift operations
- **consequence**: Signals generated without lag will exhibit look-ahead bias, causing live trading returns to fall far below backtested results because the strategy would have traded on information not yet available
- **sonnet score**: a=0.90 act=0.90 nr=0.80 roi=0.85 c=0.90
- **rationale**: 1-period inherent lag for indicator signals is a fundamental anti-look-ahead rule applicable to all ZVT technical signals.

**#7 `finance-C-075`** — total **0.88** · domain_rule · fatal

- **when**: When preparing historical data for backtesting
- **action**: Verify startup candle count equals or exceeds longest indicator lookback period
- **consequence**: Insufficient startup candles cause indicators to reference future data, introducing look-ahead bias that inflates backtest performance
- **sonnet score**: a=0.90 act=0.90 nr=0.80 roi=0.85 c=0.90
- **rationale**: Startup candle warmup >= max indicator lookback is a critical rule for ZVT's MACD/MA/Bollinger indicator initialization.

**#8 `finance-C-006`** — total **0.88** · operational_lesson · high

- **when**: When fetching market data from external data sources
- **action**: Implement fallback mechanism when data fetch returns None
- **consequence**: Network failures, API errors, or missing credentials cause fetch_market to return None; without fallback, the entire backtest fails without generating any results
- **sonnet score**: a=0.90 act=0.90 nr=0.80 roi=0.85 c=0.90
- **rationale**: None-return fallback for external data fetch is critical for ZVT's robustness against network/API failures from Chinese data sources.

**#9 `finance-C-091`** — total **0.86** · domain_rule · high

- **when**: When computing rolling volatility and Sharpe ratio
- **action**: annualize volatility using sqrt(APPROX_BDAYS_PER_YEAR) where APPROX_BDAYS_PER_YEAR equals 252
- **consequence**: Annualized volatility and Sharpe ratio will be incorrectly scaled if using calendar days instead of trading days
- **sonnet score**: a=0.85 act=0.90 nr=0.80 roi=0.85 c=0.90
- **rationale**: Annualizing volatility with sqrt(252) trading days is directly applicable to ZVT performance reporting and Sharpe calculation.

**#10 `finance-C-065`** — total **0.86** · domain_rule · high

- **when**: When implementing volatility targeting with rolling window periods
- **action**: account for NaN values in the first N periods before the rolling window completes
- **consequence**: Volatility-adjusted leverage will be NaN for the initial periods equal to the rolling window (vol_periods), causing backtest P&L series to contain NaN values for warmup periods and potentially causing downstream calculation errors in portfolio aggregation
- **sonnet score**: a=0.85 act=0.90 nr=0.80 roi=0.85 c=0.90
- **rationale**: NaN warmup period handling in rolling calculations is a concrete, frequent bug pattern in ZVT's pandas-based indicator pipeline.

**#11 `finance-C-204`** — total **0.86** · domain_rule · high

- **when**: When preparing datasets for machine learning model training and validation
- **action**: Split data temporally into TRAIN, VALID, TEST segments using date range boundaries — verify each TRAIN timestamps precede VALID, which precedes TEST
- **consequence**: Random or incorrect temporal splitting introduces look-ahead bias where future information leaks into training data, causing backtest results to significantly overestimate live trading performance
- **sonnet score**: a=0.85 act=0.90 nr=0.80 roi=0.85 c=0.90
- **rationale**: Temporal data splitting for ML training is essential for ZVT's prediction pipeline to prevent look-ahead bias.

**#12 `finance-C-258`** — total **0.86** · domain_rule · high

- **when**: When implementing Double Exponential Moving Average (DEMA) indicator
- **action**: Calculate DEMA using the formula: DEMA = 2*EMA(period) - EMA(EMA(period), period). This specific coefficient structure achieves approximately half the lag of standard EMA. Do not simplify or re-derive the formula.
- **consequence**: Incorrect DEMA formula variations produce different lag characteristics that alter signal timing. Short-term strategies relying on DEMA crossovers will generate signals at different prices, causing backtest results to diverge from expected short-term trading behavior.
- **sonnet score**: a=0.85 act=0.90 nr=0.85 roi=0.85 c=0.85
- **rationale**: DEMA formula correctness is directly relevant to ZVT's moving average indicator implementation.

**#13 `finance-C-053`** — total **0.86** · domain_rule · fatal

- **when**: When validating position state during order execution
- **action**: validate position is finite during each order processing
- **consequence**: Infinite or NaN positions cause arithmetic failures in size calculations and corrupt trade PnL records
- **sonnet score**: a=0.85 act=0.90 nr=0.80 roi=0.85 c=0.90
- **rationale**: Position finiteness validation during order execution is a concrete guard for ZVT's trading execution pipeline.

**#14 `finance-C-057`** — total **0.86** · domain_rule · fatal

- **when**: When processing order records to build trade records
- **action**: validate order size is greater than zero before creating trade records
- **consequence**: Zero or negative order sizes in trade generation produce invalid trade records with corrupted size fields and incorrect PnL calculations
- **sonnet score**: a=0.85 act=0.90 nr=0.80 roi=0.85 c=0.90
- **rationale**: Positive order size validation before trade record creation is a concrete guard for ZVT's order execution pipeline.

**#15 `finance-C-130`** — total **0.86** · domain_rule · fatal

- **when**: When implementing data ingestion to data filtering data flow
- **action**: Maintain chronological order with no temporal gaps in OHLCV bar timestamps
- **consequence**: Backtest equity curve exhibits look-ahead bias when non-chronological data causes indicator values to reference future prices, leading to live trading returns that fall far below backtested results
- **sonnet score**: a=0.90 act=0.90 nr=0.75 roi=0.85 c=0.90
- **rationale**: Chronological OHLCV order in data ingestion is fundamental to ZVT's data pipeline and prevents look-ahead bias.

---

## Resources — Top 10 of 13 passed (target: 10)

| # | Name | Score | Reason (sonnet) |
|---|---|---|---|
| 1 | `exchange-calendars` | **0.89** | Trading calendar for Chinese/global exchanges; critical for data_collection and backtesting. |
| 2 | `scikit-learn` | **0.88** | Directly supports bp-009 ML intent (classification, regression, SGD, prediction); not declared. |
| 3 | `empyrical-reloaded` | **0.85** | Financial returns and risk metrics (Sharpe, drawdown) directly useful for backtesting scene. |
| 4 | `pyfolio-reloaded` | **0.84** | Portfolio performance tearsheet directly applicable to bp-009 backtesting/reporting scenes. |
| 5 | `beautifulsoup4` | **0.83** | HTML parsing essential for stock news and financial data scraping in data_collection scene. |
| 6 | `lightgbm` | **0.80** | Gradient boosting for factor-based stock prediction; directly supports ML intent keywords. |
| 7 | `scipy` | **0.79** | Statistical functions useful for factor computation and signal analysis; not in declared stack. |
| 8 | `statsmodels` | **0.78** | Time-series regression and statistical tests directly applicable for factor computation. |
| 9 | `lxml` | **0.78** | Fast XML/HTML parser for financial data scraping; complements beautifulsoup4 in data_collection. |
| 10 | `numba` | **0.73** | JIT acceleration for factor loops over large Chinese stock datasets; not in stack. |

### Details

**#1 `exchange-calendars`** — total **0.89**

- **version_range**: latest
- **used_by** (2 BPs): bp-004, bp-088
- **description**: (no description)
- **sonnet score**: a=0.90 act=0.85 nr=0.95 roi=0.85 c=0.90
- **rationale**: Trading calendar for Chinese/global exchanges; critical for data_collection and backtesting.

**#2 `scikit-learn`** — total **0.88**

- **version_range**: >1.4.2
- **used_by** (14 BPs): bp-050, bp-062, bp-063, bp-083, bp-093, bp-102, bp-106, bp-108
- **description**: (no description)
- **sonnet score**: a=0.85 act=0.90 nr=0.95 roi=0.80 c=0.95
- **rationale**: Directly supports bp-009 ML intent (classification, regression, SGD, prediction); not declared.

**#3 `empyrical-reloaded`** — total **0.85**

- **version_range**: latest
- **used_by** (3 BPs): bp-106, bp-120, bp-121
- **description**: (no description)
- **sonnet score**: a=0.85 act=0.80 nr=0.95 roi=0.80 c=0.85
- **rationale**: Financial returns and risk metrics (Sharpe, drawdown) directly useful for backtesting scene.

**#4 `pyfolio-reloaded`** — total **0.84**

- **version_range**: >=0.9
- **used_by** (3 BPs): bp-061, bp-120, bp-121
- **description**: (no description)
- **sonnet score**: a=0.85 act=0.80 nr=0.90 roi=0.80 c=0.85
- **rationale**: Portfolio performance tearsheet directly applicable to bp-009 backtesting/reporting scenes.

**#5 `beautifulsoup4`** — total **0.83**

- **version_range**: ==4.8.2
- **used_by** (5 BPs): bp-068, bp-070, bp-079, bp-114, bp-128
- **description**: (no description)
- **sonnet score**: a=0.80 act=0.80 nr=0.95 roi=0.80 c=0.90
- **rationale**: HTML parsing essential for stock news and financial data scraping in data_collection scene.

**#6 `lightgbm`** — total **0.80**

- **version_range**: latest
- **used_by** (2 BPs): bp-083, bp-087
- **description**: (no description)
- **sonnet score**: a=0.80 act=0.75 nr=0.90 roi=0.75 c=0.85
- **rationale**: Gradient boosting for factor-based stock prediction; directly supports ML intent keywords.

**#7 `scipy`** — total **0.79**

- **version_range**: >=1.3.0
- **used_by** (21 BPs): bp-020, bp-050, bp-062, bp-064, bp-068, bp-069, bp-088, bp-092
- **description**: (no description)
- **sonnet score**: a=0.75 act=0.80 nr=0.90 roi=0.75 c=0.85
- **rationale**: Statistical functions useful for factor computation and signal analysis; not in declared stack.

**#8 `statsmodels`** — total **0.78**

- **version_range**: >=0.14.0
- **used_by** (7 BPs): bp-062, bp-088, bp-102, bp-115, bp-117, bp-119, bp-120
- **description**: (no description)
- **sonnet score**: a=0.75 act=0.75 nr=0.92 roi=0.70 c=0.85
- **rationale**: Time-series regression and statistical tests directly applicable for factor computation.

**#9 `lxml`** — total **0.78**

- **version_range**: ==4.9.1
- **used_by** (5 BPs): bp-068, bp-070, bp-071, bp-079, bp-114
- **description**: (no description)
- **sonnet score**: a=0.75 act=0.75 nr=0.95 roi=0.75 c=0.85
- **rationale**: Fast XML/HTML parser for financial data scraping; complements beautifulsoup4 in data_collection.

**#10 `numba`** — total **0.73**

- **version_range**: >0.54
- **used_by** (6 BPs): bp-063, bp-092, bp-101, bp-108, bp-115, bp-127
- **description**: (no description)
- **sonnet score**: a=0.70 act=0.65 nr=0.95 roi=0.60 c=0.80
- **rationale**: JIT acceleration for factor loops over large Chinese stock datasets; not in stack.
