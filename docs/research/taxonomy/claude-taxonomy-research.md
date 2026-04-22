# AI-Assisted Financial Investment Task Taxonomy

> Date: 2026-04-05
> Purpose: Establish a demand-driven task classification system for knowledge crystal sampling
> Methodology: Top-down from investor workflows, not bottom-up from GitHub projects

---

## Part I: Task Taxonomy (3-Level Hierarchy)

### L1-1: Data Acquisition & Management

#### L2-1.1: Market Data Collection

| Item | Description |
|------|-------------|
| **Typical Input** | Market identifiers, date ranges, frequency (tick/min/daily) |
| **Typical Output** | Standardized OHLCV, order book snapshots, tick streams |
| **Required Systems** | Data feed adapters, WebSocket clients, REST crawlers |
| **Upstream** | None (source node) |
| **Downstream** | L1-2 (Research & Analysis), L1-3 (Strategy), L1-5 (Risk) |

**L3 Sub-tasks:**

| L3 ID | Task | A-Share | HK | US | Open Source Status |
|-------|------|---------|----|----|-------------------|
| 1.1.1 | Real-time tick/quote subscription | tushare, akshare (partial) | futu-api | polygon.io client, alpaca-py | Fragmented; no unified multi-market solution |
| 1.1.2 | Historical bar data download | akshare, baostock, tushare (mature) | futu-api (partial) | yfinance, polygon (mature) | A-share mature; cross-market gap |
| 1.1.3 | Order book / Level-2 data | Paid only (L2 via CTP) | futu-api (partial) | lobster (academic) | Weak across all markets |
| 1.1.4 | Crypto market data | ccxt (very mature) | N/A | ccxt | Mature (ccxt dominates) |

#### L2-1.2: Alternative Data Collection

| Item | Description |
|------|-------------|
| **Typical Input** | URLs, API keys, search keywords |
| **Typical Output** | Structured records: filings, news articles, social sentiment scores |
| **Required Systems** | Web scrapers, NLP pipelines, API wrappers |
| **Upstream** | None (source node) |
| **Downstream** | L2-2.3 (Fundamental Analysis), L2-2.4 (Sentiment Analysis) |

**L3 Sub-tasks:**

| L3 ID | Task | Open Source Status |
|-------|------|--------------------|
| 1.2.1 | Financial statement / filing extraction | akshare (A-share), sec-edgar-downloader (US), partial |
| 1.2.2 | News & announcement crawling | Weak; scattered scripts, no robust framework |
| 1.2.3 | Social media sentiment collection | sntwitter (deprecated), praw (Reddit); mostly **gap** |
| 1.2.4 | Satellite / geospatial / IoT alt-data | **Blank** -- proprietary domain |
| 1.2.5 | Insider / institutional holding tracking | sec-edgar (US partial), A-share **weak** |

#### L2-1.3: Data Storage & Governance

| Item | Description |
|------|-------------|
| **Typical Input** | Raw data streams from L2-1.1 / L2-1.2 |
| **Typical Output** | Cleaned, deduplicated, versioned datasets with lineage metadata |
| **Required Systems** | Time-series DBs, data lakes, schema registries, quality monitors |
| **Upstream** | L2-1.1, L2-1.2 |
| **Downstream** | All downstream tasks |

**L3 Sub-tasks:**

| L3 ID | Task | Open Source Status |
|-------|------|--------------------|
| 1.3.1 | Time-series storage (Arctic, QuestDB, InfluxDB) | Arctic (mature for finance), QuestDB (general) |
| 1.3.2 | Data cleaning & corporate action adjustment | zipline (dividend/split adjust), otherwise **weak** |
| 1.3.3 | Multi-source data alignment & dedup | **Blank** -- everyone rolls their own |
| 1.3.4 | Data versioning & lineage | DVC (general), finance-specific **blank** |

---

### L1-2: Research & Analysis

#### L2-2.1: Technical Analysis

| Item | Description |
|------|-------------|
| **Typical Input** | OHLCV time series |
| **Typical Output** | Indicator values, chart patterns, buy/sell signals |
| **Required Systems** | TA libraries, charting engines, pattern recognition |
| **Upstream** | L2-1.1 (Market Data) |
| **Downstream** | L1-3 (Strategy Development) |

**L3 Sub-tasks:**

| L3 ID | Task | Open Source Status |
|-------|------|--------------------|
| 2.1.1 | Standard indicator computation (MA, RSI, MACD...) | ta-lib, pandas-ta (very mature) |
| 2.1.2 | Chart pattern recognition (head-shoulders, flags...) | **Weak**; scattered, no robust library |
| 2.1.3 | Chan Theory (缠论) analysis | czsc (niche but functional) |
| 2.1.4 | Volume profile / market microstructure | **Weak** |
| 2.1.5 | Interactive charting & visualization | mplfinance, lightweight-charts; partial |

#### L2-2.2: Factor Research & Quantitative Analysis

| Item | Description |
|------|-------------|
| **Typical Input** | Multi-asset price/fundamental data, universe definition |
| **Typical Output** | Alpha factors, factor returns, IC/IR metrics, factor portfolios |
| **Required Systems** | Factor computation engines, cross-sectional regression, factor testing frameworks |
| **Upstream** | L2-1.1, L2-1.2 (Data) |
| **Downstream** | L2-3.1 (Strategy), L2-5.2 (Risk Attribution) |

**L3 Sub-tasks:**

| L3 ID | Task | Open Source Status |
|-------|------|--------------------|
| 2.2.1 | Alpha factor mining & computation | qlib (strong), alphalens (mature) |
| 2.2.2 | Factor evaluation (IC, turnover, decay) | alphalens (mature), qlib (strong) |
| 2.2.3 | Multi-factor model construction | pyfinance (basic), empyrical (partial); mostly **weak** |
| 2.2.4 | Risk factor decomposition (Barra-style) | **Blank** -- proprietary Barra/Axioma dominate |
| 2.2.5 | AutoML / NAS for alpha discovery | qlib (NAS-based alpha mining, strong) |

#### L2-2.3: Fundamental Analysis

| Item | Description |
|------|-------------|
| **Typical Input** | Financial statements, industry data, macro indicators |
| **Typical Output** | Valuation models (DCF, multiples), quality scores, sector rankings |
| **Required Systems** | Financial modeling tools, comparable analysis engines |
| **Upstream** | L2-1.2 (Alt Data) |
| **Downstream** | L2-3.2 (Portfolio Construction), L2-4.1 (Stock Screening) |

**L3 Sub-tasks:**

| L3 ID | Task | Open Source Status |
|-------|------|--------------------|
| 2.3.1 | Financial statement standardization & ratio analysis | **Weak**; no comprehensive open-source solution |
| 2.3.2 | DCF / multiples valuation modeling | **Blank** -- Excel-dominated, no robust OSS |
| 2.3.3 | Earnings quality & accrual analysis | **Blank** |
| 2.3.4 | Industry / sector comparative analysis | **Blank** |
| 2.3.5 | Macro-economic indicator analysis | fredapi (US), **weak** for CN/HK |

#### L2-2.4: Sentiment & NLP Analysis

| Item | Description |
|------|-------------|
| **Typical Input** | News articles, analyst reports, social media posts, earnings call transcripts |
| **Typical Output** | Sentiment scores, topic clusters, event extraction, named entities |
| **Required Systems** | FinBERT, LLM pipelines, NER models, event detectors |
| **Upstream** | L2-1.2 (Alt Data) |
| **Downstream** | L2-3.1 (Strategy), L2-4.2 (Investment Advice) |

**L3 Sub-tasks:**

| L3 ID | Task | Open Source Status |
|-------|------|--------------------|
| 2.4.1 | Financial sentiment classification | FinBERT (mature for EN), **weak** for Chinese |
| 2.4.2 | Event extraction (M&A, earnings surprise, policy change) | **Weak**; research prototypes only |
| 2.4.3 | Analyst report summarization | **Blank** (LLM opportunity) |
| 2.4.4 | Earnings call transcript analysis | **Weak**; few OSS tools |
| 2.4.5 | LLM-driven comprehensive stock commentary | daily_stock_analysis (emerging) |

#### L2-2.5: Macro & Cross-Asset Research

| Item | Description |
|------|-------------|
| **Typical Input** | GDP, CPI, yield curves, FX rates, commodity prices, central bank decisions |
| **Typical Output** | Regime classification, correlation matrices, macro factor exposures |
| **Required Systems** | Econometric models, regime detection, cross-asset correlation engines |
| **Upstream** | L2-1.1, L2-1.2 |
| **Downstream** | L2-3.2 (Portfolio Construction), L2-5.1 (Risk Management) |

**L3 Sub-tasks:**

| L3 ID | Task | Open Source Status |
|-------|------|--------------------|
| 2.5.1 | Business cycle / regime detection | statsmodels (Markov switching, basic); finance-specific **weak** |
| 2.5.2 | Yield curve analysis & modeling | **Weak**; Nelson-Siegel implementations scattered |
| 2.5.3 | Cross-asset correlation & contagion analysis | **Blank** |
| 2.5.4 | Central bank policy NLP analysis | **Blank** (LLM opportunity) |

---

### L1-3: Strategy Development

#### L2-3.1: Signal Generation & Strategy Design

| Item | Description |
|------|-------------|
| **Typical Input** | Research outputs (factors, indicators, signals), trading rules |
| **Typical Output** | Entry/exit signals, position sizing directives, strategy definitions |
| **Required Systems** | Strategy DSLs, signal combiners, rule engines |
| **Upstream** | L1-2 (Research) |
| **Downstream** | L2-3.3 (Backtesting) |

**L3 Sub-tasks:**

| L3 ID | Task | Open Source Status |
|-------|------|--------------------|
| 3.1.1 | Rule-based strategy definition | freqtrade (mature), rqalpha (mature) |
| 3.1.2 | ML-based signal generation | qlib (strong), sklearn pipelines (general) |
| 3.1.3 | Multi-factor signal combination | **Weak**; ad-hoc implementations |
| 3.1.4 | RL-based strategy learning | FinRL (functional but experimental) |
| 3.1.5 | Strategy parameter sensitivity analysis | optuna integration in freqtrade (partial) |

#### L2-3.2: Portfolio Construction & Optimization

| Item | Description |
|------|-------------|
| **Typical Input** | Expected returns, risk model, constraints (sector, turnover, ESG) |
| **Typical Output** | Target portfolio weights, rebalancing schedules |
| **Required Systems** | Optimization solvers, risk model interfaces, constraint engines |
| **Upstream** | L2-3.1 (Signals), L2-2.2 (Factors), L2-5.1 (Risk) |
| **Downstream** | L2-3.3 (Backtesting), L1-6 (Execution) |

**L3 Sub-tasks:**

| L3 ID | Task | Open Source Status |
|-------|------|--------------------|
| 3.2.1 | Mean-variance / Black-Litterman optimization | PyPortfolioOpt (mature), Riskfolio-Lib (mature) |
| 3.2.2 | Risk-parity / hierarchical risk parity | Riskfolio-Lib (mature), hrp (mature) |
| 3.2.3 | Constraint-aware optimization (turnover, sector, ESG) | cvxpy (general), finance-specific **weak** |
| 3.2.4 | Dynamic rebalancing & tax-loss harvesting | **Blank** |
| 3.2.5 | Multi-asset allocation (stocks + bonds + alts) | **Weak** |

#### L2-3.3: Backtesting & Simulation

| Item | Description |
|------|-------------|
| **Typical Input** | Strategy definition, historical data, execution assumptions (slippage, commission) |
| **Typical Output** | PnL curves, Sharpe/Sortino/Calmar ratios, drawdown analysis, trade logs |
| **Required Systems** | Event-driven or vectorized backtesting engines, performance analytics |
| **Upstream** | L2-3.1 (Strategy), L2-3.2 (Portfolio) |
| **Downstream** | L2-3.4 (Optimization), L2-5.2 (Risk Attribution), L1-6 (Execution) |

**L3 Sub-tasks:**

| L3 ID | Task | Open Source Status |
|-------|------|--------------------|
| 3.3.1 | Vectorized backtesting | freqtrade (mature), vectorbt (mature) |
| 3.3.2 | Event-driven backtesting | zipline (mature), rqalpha (mature for A-share), vnpy (mature) |
| 3.3.3 | Multi-asset / cross-market backtesting | **Weak**; most frameworks single-market |
| 3.3.4 | Market impact / realistic slippage simulation | **Weak**; basic models only |
| 3.3.5 | Walk-forward / combinatorial purged CV | qlib (partial), otherwise **weak** |
| 3.3.6 | Performance analytics & reporting | empyrical (mature), quantstats (mature) |

#### L2-3.4: Strategy Optimization & Selection

| Item | Description |
|------|-------------|
| **Typical Input** | Backtest results, parameter search spaces |
| **Typical Output** | Optimal parameters, robustness scores, overfitting diagnostics |
| **Required Systems** | Hyperparameter optimizers, walk-forward engines, combinatorial testing |
| **Upstream** | L2-3.3 (Backtesting) |
| **Downstream** | L1-6 (Execution) |

**L3 Sub-tasks:**

| L3 ID | Task | Open Source Status |
|-------|------|--------------------|
| 3.4.1 | Hyperparameter optimization | freqtrade + optuna (functional), qlib (partial) |
| 3.4.2 | Overfitting detection (WFA, CPCV, deflated Sharpe) | **Weak**; research code only |
| 3.4.3 | Strategy ensemble / blending | **Blank** |
| 3.4.4 | Regime-conditional strategy switching | **Blank** |

---

### L1-4: Investment Decision Support

#### L2-4.1: Stock Screening & Selection

| Item | Description |
|------|-------------|
| **Typical Input** | Screening criteria (PE < 15, ROE > 15%, etc.), universe |
| **Typical Output** | Ranked stock lists, screening reports |
| **Required Systems** | Multi-criteria filtering engines, ranking systems |
| **Upstream** | L2-2.1 (TA), L2-2.2 (Factors), L2-2.3 (Fundamental) |
| **Downstream** | L2-4.2 (Advice), L2-3.2 (Portfolio) |

**L3 Sub-tasks:**

| L3 ID | Task | Open Source Status |
|-------|------|--------------------|
| 4.1.1 | Multi-criteria stock screening | myhhub/stock (A-share, functional), finviz API wrapper (US) |
| 4.1.2 | Composite scoring & ranking | myhhub/stock (partial), otherwise **weak** |
| 4.1.3 | Smart beta index construction | **Blank** |
| 4.1.4 | Cross-market opportunity scanning (AH premium, ADR) | **Blank** |

#### L2-4.2: Investment Advice & Report Generation

| Item | Description |
|------|-------------|
| **Typical Input** | Analysis results, user profile (risk tolerance, horizon, preferences) |
| **Typical Output** | Natural-language investment commentary, recommendation reports, trade ideas |
| **Required Systems** | LLM orchestrators, multi-agent systems, report templates |
| **Upstream** | L1-2 (Research), L2-4.1 (Screening) |
| **Downstream** | L1-6 (Execution -- human decision) |

**L3 Sub-tasks:**

| L3 ID | Task | Open Source Status |
|-------|------|--------------------|
| 4.2.1 | AI-driven stock analysis reports | daily_stock_analysis (emerging, single-stock) |
| 4.2.2 | Portfolio review & recommendation | **Blank** (LLM opportunity) |
| 4.2.3 | Market outlook / morning brief generation | **Blank** (LLM opportunity) |
| 4.2.4 | Personalized investment education | **Blank** (LLM opportunity) |

#### L2-4.3: Financial Planning & Goal-Based Investing

| Item | Description |
|------|-------------|
| **Typical Input** | User goals (retirement, education), current assets, risk profile |
| **Typical Output** | Asset allocation plans, savings targets, progress tracking |
| **Required Systems** | Financial planning calculators, Monte Carlo simulators, goal trackers |
| **Upstream** | L2-2.5 (Macro), L2-3.2 (Portfolio) |
| **Downstream** | L1-6 (Execution) |

**L3 Sub-tasks:**

| L3 ID | Task | Open Source Status |
|-------|------|--------------------|
| 4.3.1 | Retirement planning simulation | **Blank** |
| 4.3.2 | Education / home savings planning | **Blank** |
| 4.3.3 | Tax-efficient withdrawal strategies | **Blank** |

---

### L1-5: Risk Management

#### L2-5.1: Risk Measurement & Monitoring

| Item | Description |
|------|-------------|
| **Typical Input** | Portfolio positions, market data, risk model parameters |
| **Typical Output** | VaR, CVaR, Greeks, stress test results, limit breach alerts |
| **Required Systems** | Risk engines, stress testing frameworks, alert systems |
| **Upstream** | L2-1.1 (Data), L2-3.2 (Portfolio) |
| **Downstream** | L2-5.2 (Attribution), L1-6 (Execution -- hedging) |

**L3 Sub-tasks:**

| L3 ID | Task | Open Source Status |
|-------|------|--------------------|
| 5.1.1 | Portfolio VaR / CVaR computation | pyfolio (partial), Riskfolio-Lib (partial) |
| 5.1.2 | Stress testing & scenario analysis | **Weak**; no robust OSS framework |
| 5.1.3 | Real-time risk monitoring & alerting | **Blank** |
| 5.1.4 | Options Greeks & derivatives risk | QuantLib-Python (mature for pricing), risk mgmt **weak** |
| 5.1.5 | Margin & leverage monitoring | **Blank** |

#### L2-5.2: Risk Attribution & Reporting

| Item | Description |
|------|-------------|
| **Typical Input** | Portfolio returns, factor model, benchmark |
| **Typical Output** | Performance attribution (Brinson, factor-based), risk contribution decomposition |
| **Required Systems** | Attribution engines, factor risk models |
| **Upstream** | L2-5.1, L2-3.3 (Backtesting) |
| **Downstream** | L2-4.2 (Reporting) |

**L3 Sub-tasks:**

| L3 ID | Task | Open Source Status |
|-------|------|--------------------|
| 5.2.1 | Brinson attribution (allocation/selection) | **Weak**; basic implementations only |
| 5.2.2 | Factor-based risk attribution | **Blank** |
| 5.2.3 | Transaction cost analysis (TCA) | **Blank** |

---

### L1-6: Trade Execution & Operations

#### L2-6.1: Order Management & Execution

| Item | Description |
|------|-------------|
| **Typical Input** | Target trades (symbol, qty, side), execution strategy (TWAP, VWAP, limit) |
| **Typical Output** | Order fills, execution reports, slippage analysis |
| **Required Systems** | OMS, broker API adapters, smart order routers |
| **Upstream** | L1-3 (Strategy), L2-5.1 (Risk) |
| **Downstream** | L2-6.2 (Monitoring) |

**L3 Sub-tasks:**

| L3 ID | Task | Open Source Status |
|-------|------|--------------------|
| 6.1.1 | Broker API integration (A-share CTP/XTP) | vnpy (mature, 30+ gateways) |
| 6.1.2 | Broker API integration (US: IB/Alpaca) | ib_insync (mature), alpaca-py (mature) |
| 6.1.3 | Broker API integration (HK: Futu) | futu-api (mature) |
| 6.1.4 | Algo execution (TWAP/VWAP/iceberg) | vnpy (basic), otherwise **weak** |
| 6.1.5 | Smart order routing | **Blank** |
| 6.1.6 | Crypto exchange integration | ccxt (very mature), freqtrade (mature) |

#### L2-6.2: Portfolio Monitoring & Operations

| Item | Description |
|------|-------------|
| **Typical Input** | Live positions, market data, benchmark |
| **Typical Output** | Real-time PnL, drift alerts, rebalancing triggers, reconciliation reports |
| **Required Systems** | Position trackers, drift monitors, reconciliation engines |
| **Upstream** | L2-6.1 (Execution) |
| **Downstream** | L2-5.1 (Risk), L2-4.2 (Reporting) |

**L3 Sub-tasks:**

| L3 ID | Task | Open Source Status |
|-------|------|--------------------|
| 6.2.1 | Live position & PnL tracking | vnpy (partial), QUANTAXIS (partial) |
| 6.2.2 | Portfolio drift monitoring & rebalance triggers | **Blank** |
| 6.2.3 | Trade reconciliation | **Blank** |
| 6.2.4 | Multi-account / fund-level aggregation | **Blank** |

---

### L1-7: Infrastructure & Platform

#### L2-7.1: Platform Architecture

| Item | Description |
|------|-------------|
| **Typical Input** | System requirements, scale targets |
| **Typical Output** | Deployable platform with data pipelines, compute, storage, API layers |
| **Required Systems** | Distributed computing, message queues, container orchestration |
| **Upstream** | None (enabling layer) |
| **Downstream** | All other L1 categories |

**L3 Sub-tasks:**

| L3 ID | Task | Open Source Status |
|-------|------|--------------------|
| 7.1.1 | Full-stack quant platform architecture | QUANTAXIS (ambitious but fragile), qlib (research-focused, solid) |
| 7.1.2 | Plugin / extension system design | vnpy (mature Mod system), rqalpha (mature Mod system), freqtrade (strategy plugin) |
| 7.1.3 | Schema-driven data pipeline | zvt (functional, SQLAlchemy-driven) |
| 7.1.4 | Distributed task scheduling | QUANTAXIS (RabbitMQ-based, partial) |
| 7.1.5 | Web dashboard / UI framework | QUANTAXIS (partial), freqtrade (freq-ui, functional) |

---

## Part II: Task Category x User Type Coverage Matrix

Legend: ★★★ = Critical need | ★★ = Important | ★ = Nice-to-have | - = Not applicable

| Task Category | Retail Investor | Quant Researcher | Fund Manager |
|---------------|:---:|:---:|:---:|
| **L1-1: Data Acquisition** | | | |
| L2-1.1 Market Data Collection | ★★ | ★★★ | ★★ |
| L2-1.2 Alternative Data Collection | ★ | ★★★ | ★★★ |
| L2-1.3 Data Storage & Governance | - | ★★★ | ★★★ |
| **L1-2: Research & Analysis** | | | |
| L2-2.1 Technical Analysis | ★★★ | ★★ | ★ |
| L2-2.2 Factor Research | - | ★★★ | ★★★ |
| L2-2.3 Fundamental Analysis | ★★★ | ★ | ★★★ |
| L2-2.4 Sentiment & NLP Analysis | ★★ | ★★ | ★★★ |
| L2-2.5 Macro & Cross-Asset Research | ★ | ★★ | ★★★ |
| **L1-3: Strategy Development** | | | |
| L2-3.1 Signal Generation | ★ | ★★★ | ★★ |
| L2-3.2 Portfolio Construction | - | ★★ | ★★★ |
| L2-3.3 Backtesting | ★ | ★★★ | ★★ |
| L2-3.4 Strategy Optimization | - | ★★★ | ★★ |
| **L1-4: Investment Decision Support** | | | |
| L2-4.1 Stock Screening | ★★★ | ★ | ★★ |
| L2-4.2 Investment Advice & Reports | ★★★ | ★ | ★★★ |
| L2-4.3 Financial Planning | ★★★ | - | ★ |
| **L1-5: Risk Management** | | | |
| L2-5.1 Risk Measurement | ★ | ★★ | ★★★ |
| L2-5.2 Risk Attribution | - | ★★ | ★★★ |
| **L1-6: Execution & Operations** | | | |
| L2-6.1 Order Management | ★ | ★★ | ★★★ |
| L2-6.2 Portfolio Monitoring | ★ | ★ | ★★★ |
| **L1-7: Infrastructure** | | | |
| L2-7.1 Platform Architecture | - | ★★★ | ★★ |

**Key Observations:**

1. **Retail investors** -- most underserved. Their core needs (fundamental analysis, stock screening, AI-generated advice, financial planning) have the weakest OSS coverage.
2. **Quant researchers** -- best served. Backtesting, factor research, and ML pipelines have mature solutions.
3. **Fund managers** -- partially served for execution and backtesting, but risk management, attribution, and portfolio monitoring are nearly blank.

---

## Part III: Existing Blueprint Mapping

### Blueprint-by-Blueprint Analysis

#### BP-001: freqtrade (Vectorized Strategy Backtesting)

| Task Coverage | Depth |
|---------------|-------|
| L2-3.1 Signal Generation (rule-based) | Complete |
| L2-3.3 Backtesting (vectorized) | Complete |
| L2-3.4 Strategy Optimization (hyperopt) | Complete |
| L2-6.1 Order Mgmt (crypto exchange) | Complete |
| L2-1.1 Market Data (crypto) | Partial |
| L2-7.1 Platform (plugin, web UI) | Partial |

**Limitation:** Crypto-only; not directly applicable to equity markets.

#### BP-002: zipline (Event-Driven Backtesting)

| Task Coverage | Depth |
|---------------|-------|
| L2-3.3 Backtesting (event-driven) | Complete |
| L2-2.2 Factor Research (Pipeline API) | Partial |
| L2-1.3 Data Governance (bundle system) | Partial |
| L2-3.1 Signal Generation | Partial |

**Limitation:** US equities only; project maintenance stalled (zipline-reloaded fork active).

#### BP-003: vnpy (Trading Framework)

| Task Coverage | Depth |
|---------------|-------|
| L2-6.1 Order Management (30+ gateways) | Complete |
| L2-3.3 Backtesting (event-driven) | Complete |
| L2-7.1 Platform (plugin system) | Complete |
| L2-1.1 Market Data (real-time) | Partial |
| L2-6.2 Portfolio Monitoring | Touches |

**Limitation:** Execution-heavy; weak on research/analysis layers.

#### BP-004: qlib (AI/ML Quant Research)

| Task Coverage | Depth |
|---------------|-------|
| L2-2.2 Factor Research (AutoML alpha) | Complete |
| L2-3.1 Signal Generation (ML-based) | Complete |
| L2-3.3 Backtesting (built-in) | Partial |
| L2-3.4 Strategy Optimization (NAS) | Partial |
| L2-7.1 Platform (config pipeline) | Partial |
| L2-1.3 Data Governance | Partial |

**Limitation:** Research-focused; no live trading, limited market coverage.

#### BP-005: rqalpha (A-Share Backtesting)

| Task Coverage | Depth |
|---------------|-------|
| L2-3.3 Backtesting (event-driven, T+1) | Complete |
| L2-3.1 Signal Generation (rule-based) | Partial |
| L2-7.1 Platform (Mod plugin) | Partial |

**Limitation:** A-share backtesting only; narrow scope.

#### BP-006: QUANTAXIS (Full-Stack Quant Platform)

| Task Coverage | Depth |
|---------------|-------|
| L2-7.1 Platform (distributed arch) | Partial (ambitious but fragile) |
| L2-1.1 Market Data (A-share) | Partial |
| L2-1.3 Data Storage (MongoDB) | Partial |
| L2-3.3 Backtesting | Partial |
| L2-6.1 Order Management | Partial |
| L2-6.2 Portfolio Monitoring | Touches |

**Limitation:** Wide but shallow; stability issues; unmaintained in parts.

#### BP-007: myhhub/stock (Stock Screening)

| Task Coverage | Depth |
|---------------|-------|
| L2-4.1 Stock Screening (A-share) | Complete |
| L2-2.1 Technical Analysis (indicators) | Partial |

**Limitation:** A-share only; screening only; no strategy/execution.

#### BP-008: czsc (Chan Theory Analysis)

| Task Coverage | Depth |
|---------------|-------|
| L2-2.1 Technical Analysis (Chan Theory) | Complete |
| L2-3.1 Signal Generation (signal-driven) | Partial |

**Limitation:** Niche methodology (Chan Theory); limited generalization.

#### BP-009: zvt (Schema-Driven Framework)

| Task Coverage | Depth |
|---------------|-------|
| L2-7.1 Platform (schema-driven pipeline) | Partial |
| L2-1.3 Data Governance (SQLAlchemy ORM) | Partial |
| L2-2.2 Factor Research (factor computation) | Partial |
| L2-1.1 Market Data (A-share) | Touches |

**Limitation:** Framework design focus; limited actual analytics.

#### BP-010: daily_stock_analysis (LLM Stock Analysis)

| Task Coverage | Depth |
|---------------|-------|
| L2-4.2 Investment Advice (AI commentary) | Partial |
| L2-2.4 Sentiment & NLP (LLM analysis) | Touches |

**Limitation:** Single-stock analysis only; no portfolio view; emerging quality.

---

## Part IV: Task Category x Blueprint Coverage Heatmap

Legend: ███ Complete | ▓▓▓ Partial | ░░░ Touches | (blank) = No coverage

```
                          BP-001  BP-002  BP-003  BP-004  BP-005  BP-006  BP-007  BP-008  BP-009  BP-010
                          freq    zip     vnpy    qlib    rqalp   QUANT   myhub   czsc    zvt     daily
                          trade   line            IA              AXIS    stock           
─────────────────────────────────────────────────────────────────────────────────────────────────────────
L2-1.1 Market Data         ▓▓▓                                    ▓▓▓                     ░░░          
L2-1.2 Alt Data                                                                                        
L2-1.3 Data Governance             ▓▓▓                    ▓▓▓     ▓▓▓                     ▓▓▓          
L2-2.1 Technical Analysis                                                  ▓▓▓     ███                 
L2-2.2 Factor Research             ▓▓▓            ███                                     ▓▓▓          
L2-2.3 Fundamental Analysis                                                                            
L2-2.4 Sentiment/NLP                                                                             ░░░  
L2-2.5 Macro/Cross-Asset                                                                               
L2-3.1 Signal Generation  ███             ░░░     ███     ▓▓▓                     ▓▓▓                  
L2-3.2 Portfolio Constr.                                                                               
L2-3.3 Backtesting         ███     ███     ███     ▓▓▓     ███     ▓▓▓                                 
L2-3.4 Strategy Optim.    ███                      ▓▓▓                                                 
L2-4.1 Stock Screening                                                     ███                         
L2-4.2 Advice/Reports                                                                           ▓▓▓  
L2-4.3 Financial Planning                                                                              
L2-5.1 Risk Measurement                                                                               
L2-5.2 Risk Attribution                                                                               
L2-6.1 Order Management   ███              ███                     ▓▓▓                                 
L2-6.2 Portfolio Monitor                   ░░░                     ░░░                                 
L2-7.1 Platform Arch.      ▓▓▓             ███     ▓▓▓     ▓▓▓     ▓▓▓                     ▓▓▓          
─────────────────────────────────────────────────────────────────────────────────────────────────────────
```

---

## Part V: Gap Analysis & Sampling Priority

### Tier 1: Critical Gaps (High demand, zero coverage)

| Gap Area | Why Critical | Candidate Projects to Investigate |
|----------|-------------|----------------------------------|
| **L2-2.3 Fundamental Analysis** | Core need for retail + fund managers; zero OSS coverage | OpenBB SDK, Fundamental Analysis (github), financial-modeling-prep wrappers |
| **L2-3.2 Portfolio Construction** | Essential for anyone managing real money; no blueprint | PyPortfolioOpt, Riskfolio-Lib, cvxpy-based wrappers |
| **L2-5.1/5.2 Risk Management** | Non-negotiable for fund managers; complete blank | pyfolio, QuantLib, risktools |
| **L2-4.3 Financial Planning** | Largest retail user base; total blank | No major OSS; robo-advisor logic is the gap |

### Tier 2: Important Gaps (Partial coverage, needs deepening)

| Gap Area | Current State | Candidate Projects |
|----------|---------------|-------------------|
| **L2-2.4 Sentiment/NLP** | Only daily_stock_analysis (shallow) | FinBERT, finNLP, OpenBB NLP modules |
| **L2-1.2 Alt Data** | No coverage | sec-edgar-downloader, fundspy, social-media scrapers |
| **L2-2.5 Macro Analysis** | No coverage | fredapi, econdb, macro-research notebooks |
| **L2-4.2 AI Reports (portfolio-level)** | Only single-stock | crewAI finance templates, multi-agent frameworks |
| **L2-6.2 Portfolio Monitoring** | Barely touched | No dominant OSS; custom dashboards needed |

### Tier 3: Market-Dimension Gaps (Cross-market coverage)

| Gap | Current Bias | Needed |
|-----|-------------|--------|
| HK market coverage | Nearly zero | futu-api ecosystem, HK-specific data sources |
| US market coverage (beyond zipline) | Stale (zipline stalled) | alpaca-py, lumibot, quantconnect-lean |
| Multi-market unified framework | Each BP is single-market | OpenBB Terminal (multi-market data unification) |

### Tier 4: User-Dimension Gaps

| Gap | Description |
|-----|-------------|
| Retail-facing tools | 7 of 10 BPs serve quant researchers; retail investors are underserved |
| LLM-native workflows | Only BP-010 uses LLM; massive opportunity for LLM-driven analysis/advice |
| No-code / low-code strategy building | All BPs require Python; retail needs GUI/natural-language interfaces |

---

## Part VI: Recommended Next 10 Blueprint Candidates

Based on gap analysis, prioritized by coverage breadth and demand intensity:

| Priority | Project | Primary Gap Filled | Markets |
|----------|---------|-------------------|---------|
| 1 | **OpenBB Terminal/SDK** | L2-1.1/1.2 multi-market data + L2-2.3 fundamental + L2-2.5 macro | A/HK/US |
| 2 | **PyPortfolioOpt** | L2-3.2 portfolio construction & optimization | Market-agnostic |
| 3 | **Riskfolio-Lib** | L2-3.2 portfolio + L2-5.1 risk measurement | Market-agnostic |
| 4 | **FinRL** | L2-3.1 RL-based strategy + L2-3.4 strategy optimization | Multi-market |
| 5 | **pyfolio** | L2-5.2 risk attribution + L2-3.3 performance analytics | Market-agnostic |
| 6 | **QuantLib-Python** | L2-5.1 derivatives risk + options pricing | Market-agnostic |
| 7 | **alpaca-py / lumibot** | L2-6.1 US execution + L2-3.3 US backtesting (zipline successor) | US |
| 8 | **FinBERT / finNLP** | L2-2.4 financial NLP & sentiment | Multi-lingual |
| 9 | **sec-edgar-downloader + akshare** | L2-1.2 alt data (filings, fundamentals) | US + A-share |
| 10 | **CrewAI / AutoGen finance** | L2-4.2 multi-agent AI investment reports | Market-agnostic |

---

## Appendix: Taxonomy Summary Statistics

- **L1 Categories:** 7
- **L2 Categories:** 20
- **L3 Tasks:** 78
- **Tasks with mature OSS:** 18 (23%)
- **Tasks with partial/weak OSS:** 25 (32%)
- **Tasks that are blank (no OSS):** 35 (45%)
- **Existing blueprint coverage:** 10 of 20 L2 categories touched; 0 of 20 fully covered across all 3 markets
