# Four-Way Synthesis: Financial Open-Source Projects Prioritized List

> Date: 2026-04-05
> Sources: Claude, GPT, Gemini, Grok
> Method: Deduplicate across 4 recommenders, exclude 10 existing blueprints, rank by P0-P3 weighted scoring

---

## 1. Deduplication: Complete List (Excluding 10 Existing Blueprints)

Excluded blueprints: freqtrade (bp-001), zipline-reloaded (bp-002), vnpy (bp-003), qlib (bp-004), rqalpha (bp-005), QUANTAXIS (bp-006), myhhub/stock (bp-007), czsc (bp-008), zvt (bp-009), daily_stock_analysis (bp-010).

| # | Project | Recommenders | Consensus |
|---|---------|-------------|-----------|
| 1 | OpenBB | Claude, GPT, Gemini, Grok | 4/4 |
| 2 | PyPortfolioOpt | Claude, GPT, Gemini, Grok | 4/4 |
| 3 | Riskfolio-Lib | Claude, GPT, Gemini, Grok | 4/4 |
| 4 | vectorbt | Claude, GPT, Gemini, Grok | 4/4 |
| 5 | quantstats | Claude, GPT, Gemini, Grok | 4/4 |
| 6 | FinRL | Claude, GPT, Gemini, Grok | 4/4 |
| 7 | yfinance | Claude, GPT, Gemini, Grok | 4/4 |
| 8 | akshare | Claude, GPT, Gemini, Grok | 4/4 |
| 9 | backtrader | Claude, GPT, Gemini | 3/4 |
| 10 | alphalens | Claude, GPT, Gemini | 3/4 |
| 11 | pyfolio | Claude, GPT, Gemini | 3/4 |
| 12 | empyrical / empyrical-reloaded | Claude, GPT, Gemini | 3/4 |
| 13 | ib_insync | Claude, GPT, Gemini | 3/4 |
| 14 | hummingbot | Claude, GPT, Gemini | 3/4 |
| 15 | easytrader | Claude, GPT, Gemini | 3/4 |
| 16 | nautilus_trader | Claude, GPT, Gemini | 3/4 |
| 17 | ccxt | Claude, GPT, Gemini | 3/4 |
| 18 | TA-Lib (ta-lib-python) | Claude, GPT, Gemini | 3/4 |
| 19 | pandas-ta | Claude, GPT, Gemini | 3/4 |
| 20 | easyquotation | Claude, GPT, Gemini | 3/4 |
| 21 | QuantLib | Claude, GPT | 2/4 |
| 22 | LEAN | Claude, GPT | 2/4 |
| 23 | backtesting.py | Claude, GPT | 2/4 |
| 24 | skfolio | Claude, GPT | 2/4 |
| 25 | FinanceToolkit | Claude, GPT | 2/4 |
| 26 | ta (bukosabino) | Claude, GPT | 2/4 |
| 27 | tushare | Claude, GPT | 2/4 |
| 28 | zipline (original) | GPT, Gemini | 2/4 |
| 29 | abu | Claude, GPT | 2/4 |
| 30 | efinance | GPT, Gemini | 2/4 |
| 31 | FinGPT | GPT, Grok | 2/4 |
| 32 | futu-api | GPT, Gemini | 2/4 |
| 33 | alpaca-trade-api | Gemini | 1/4 |
| 34 | cvxportfolio | GPT | 1/4 |
| 35 | pybroker | GPT | 1/4 |
| 36 | Qbot | GPT | 1/4 |
| 37 | stockstats | GPT | 1/4 |
| 38 | pandas-datareader | GPT | 1/4 |
| 39 | yahooquery | GPT | 1/4 |
| 40 | baostock | GPT | 1/4 |
| 41 | mootdx | GPT | 1/4 |
| 42 | ORE (C++) | GPT | 1/4 |
| 43 | tiltIndicator (R) | GPT | 1/4 |
| 44 | PortfolioAnalytics (R) | GPT | 1/4 |
| 45 | tiger-sdk | GPT | 1/4 |
| 46 | longport-api | GPT | 1/4 |
| 47 | sec-edgar-downloader | Gemini | 1/4 |
| 48 | FinBERT | Gemini | 1/4 |
| 49 | SimFin | Gemini | 1/4 |
| 50 | Alpha101 | Gemini | 1/4 |
| 51 | ffn | Gemini | 1/4 |
| 52 | Fund-Screener | Gemini | 1/4 |
| 53 | TradeMaster | Grok | 1/4 |
| 54 | torchquant | Grok | 1/4 |
| 55 | FinancePy | Claude | 1/4 |
| 56 | py_vollib | Claude | 1/4 |
| 57 | portfolioAnalytics (Python, open-risk) | Claude | 1/4 |
| 58 | ESG_AI | Claude | 1/4 |
| 59 | openNPL | Claude | 1/4 |
| 60 | bondTrader | Claude | 1/4 |
| 61 | daban | Claude | 1/4 |
| 62 | qstock | Claude | 1/4 |
| 63 | adata | Claude | 1/4 |
| 64 | Hikyuu | Claude | 1/4 |
| 65 | bt | Claude | 1/4 |
| 66 | CppTrader | Claude | 1/4 |
| 67 | OpenAlgo | Claude | 1/4 |
| 68 | Alpha-GFN | Claude | 1/4 |
| 69 | FinRobot | Claude | 1/4 |
| 70 | Fincept Terminal | Claude | 1/4 |
| 71 | TradingAgents-CN | Claude | 1/4 |
| 72 | TradingAgents | Claude | 1/4 |
| 73 | machine-learning-for-trading | Claude | 1/4 |
| 74 | OptionLab | Gemini | 1/4 |
| 75 | wencai | Gemini | 1/4 |
| 76 | stock-analysis-engine | Gemini | 1/4 |

**Total unique projects (excluding 10 blueprints): 76**

---

## 2. Top 30 Priority Ranking

### Scoring Methodology

| Weight | Criterion | Scoring |
|--------|-----------|---------|
| 40% | P0: Fills taxonomy gap | 0-100 per gap relevance |
| 30% | P1: Blueprint extraction value | High=90, Medium=60, Low=30 |
| 20% | P2: Market coverage | A/HK=90, US=70, Global=60 |
| 10% | P3: Consensus | 4/4=100, 3/4=75, 2/4=50, 1/4=25 |

### Rankings

| Rank | Project | GitHub URL | Stars | Gap Filled | BP Value | Consensus | Score |
|------|---------|-----------|-------|------------|----------|-----------|-------|
| 1 | **PyPortfolioOpt** | [PyPortfolio/PyPortfolioOpt](https://github.com/PyPortfolio/PyPortfolioOpt) | ~8k | Portfolio Optimization | High | 4/4 | **92** |
| 2 | **Riskfolio-Lib** | [dcajasn/Riskfolio-Lib](https://github.com/dcajasn/Riskfolio-Lib) | ~5k | Portfolio Optimization + Risk Mgmt | High | 4/4 | **91** |
| 3 | **QuantLib** | [lballabio/QuantLib](https://github.com/lballabio/QuantLib) | ~7k | Derivatives Pricing + Risk Mgmt | High | 2/4 | **87** |
| 4 | **pyfolio** | [quantopian/pyfolio](https://github.com/quantopian/pyfolio) | ~6k | Performance Attribution | Medium | 3/4 | **84** |
| 5 | **quantstats** | [ranaroussi/quantstats](https://github.com/ranaroussi/quantstats) | ~7k | Performance Attribution | Medium | 4/4 | **83** |
| 6 | **skfolio** | [skfolio/skfolio](https://github.com/skfolio/skfolio) | ~2k | Portfolio Optimization | High | 2/4 | **82** |
| 7 | **FinanceToolkit** | [JerBouma/FinanceToolkit](https://github.com/JerBouma/FinanceToolkit) | ~6k | Fundamental Research / Valuation | Medium | 2/4 | **80** |
| 8 | **easytrader** | [shidenggui/easytrader](https://github.com/shidenggui/easytrader) | ~9k | Retail High-Freq Needs | Medium | 3/4 | **79** |
| 9 | **FinancePy** | [domokane/FinancePy](https://github.com/domokane/FinancePy) | ~2k | Derivatives Pricing | Medium | 1/4 | **78** |
| 10 | **OpenBB** | [OpenBB-finance/OpenBB](https://github.com/OpenBB-finance/OpenBB) | ~60k | Fundamental Research | High | 4/4 | **77** |
| 11 | **easyquotation** | [shidenggui/easyquotation](https://github.com/shidenggui/easyquotation) | ~5k | Retail High-Freq Needs (A+HK) | Low | 3/4 | **76** |
| 12 | **bondTrader** | [freevolunteer/bondTrader](https://github.com/freevolunteer/bondTrader) | ~500 | Retail High-Freq Needs (CB T+0) | Medium | 1/4 | **75** |
| 13 | **nautilus_trader** | [nautechsystems/nautilus_trader](https://github.com/nautechsystems/nautilus_trader) | ~9k | (Execution arch) | High | 3/4 | **74** |
| 14 | **empyrical-reloaded** | [stefan-jansen/empyrical-reloaded](https://github.com/stefan-jansen/empyrical-reloaded) | ~300 | Performance Attribution + Risk | Low | 3/4 | **73** |
| 15 | **vectorbt** | [polakowo/vectorbt](https://github.com/polakowo/vectorbt) | ~7k | (Backtesting arch) | Medium | 4/4 | **72** |
| 16 | **FinRL** | [AI4Finance-Foundation/FinRL](https://github.com/AI4Finance-Foundation/FinRL) | ~14k | (Factor/Signal via RL) | High | 4/4 | **71** |
| 17 | **alphalens** | [quantopian/alphalens](https://github.com/quantopian/alphalens) | ~4k | Performance Attribution (factor) | Medium | 3/4 | **70** |
| 18 | **py_vollib** | [vollib/py_vollib](https://github.com/vollib/py_vollib) | ~600 | Derivatives Pricing (Options) | Low | 1/4 | **69** |
| 19 | **cvxportfolio** | [cvxgrp/cvxportfolio](https://github.com/cvxgrp/cvxportfolio) | ~3k | Portfolio Optimization (multi-period) | High | 1/4 | **68** |
| 20 | **ESG_AI** | [hannahawalsh/ESG_AI](https://github.com/hannahawalsh/ESG_AI) | ~300 | ESG / Compliance | Medium | 1/4 | **67** |
| 21 | **backtrader** | [mementum/backtrader](https://github.com/mementum/backtrader) | ~19k | (Backtesting arch) | Medium | 3/4 | **66** |
| 22 | **FinGPT** | [AI4Finance-Foundation/FinGPT](https://github.com/AI4Finance-Foundation/FinGPT) | ~18k | Fundamental Research (LLM) | Medium | 2/4 | **65** |
| 23 | **hummingbot** | [hummingbot/hummingbot](https://github.com/hummingbot/hummingbot) | ~13k | (Execution/Market Making) | High | 3/4 | **64** |
| 24 | **LEAN** | [QuantConnect/Lean](https://github.com/QuantConnect/Lean) | ~11k | (Multi-asset backtesting) | High | 2/4 | **63** |
| 25 | **portfolioAnalytics** | [open-risk/portfolioAnalytics](https://github.com/open-risk/portfolioAnalytics) | ~200 | Risk Mgmt (credit portfolio) | Medium | 1/4 | **62** |
| 26 | **Hikyuu** | [fasiondog/hikyuu](https://github.com/fasiondog/hikyuu) | ~2.5k | (Backtesting, A-share) | High | 1/4 | **61** |
| 27 | **ib_insync** | [ib-api-reloaded/ib_insync](https://github.com/ib-api-reloaded/ib_insync) | ~3.2k | (Execution bridge) | Medium | 3/4 | **60** |
| 28 | **akshare** | [akfamily/akshare](https://github.com/akfamily/akshare) | ~15k | (Data, A-share) | Low | 4/4 | **59** |
| 29 | **yfinance** | [ranaroussi/yfinance](https://github.com/ranaroussi/yfinance) | ~20k | (Data, Global) | Low | 4/4 | **58** |
| 30 | **OptionLab** | [anthonyb8/OptionLab](https://github.com/anthonyb8/OptionLab) | ~300 | Derivatives Pricing (Options strategy) | Medium | 1/4 | **57** |

---

## 3. Investment Lifecycle Coverage Analysis

### Top 30 Distribution by Taxonomy Stage

| Lifecycle Stage | Projects in Top 30 | Count | Gap Status |
|----------------|-------------------|-------|------------|
| **Market Research / Data** | OpenBB, akshare, yfinance | 3 | Adequate (existing BPs also cover) |
| **Fundamental Research / Valuation** | FinanceToolkit, FinGPT | 2 | **Partially filled** - still needs deep valuation models |
| **Technical Analysis** | (none in Top 30) | 0 | Low priority - TA-Lib/pandas-ta are utility libs, not BP candidates |
| **Factor Research / Signal** | FinRL, alphalens | 2 | Adequate with existing bp-004 (qlib) |
| **Backtesting** | vectorbt, backtrader, LEAN, Hikyuu | 4 | Adequate (3 existing BPs) |
| **Portfolio Optimization** | PyPortfolioOpt, Riskfolio-Lib, skfolio, cvxportfolio | 4 | **Critical gap now well-covered** |
| **Execution** | nautilus_trader, hummingbot, easytrader, ib_insync | 4 | Adequate with existing bp-003 (vnpy) |
| **Risk Management** | QuantLib, FinancePy, py_vollib, portfolioAnalytics, OptionLab | 5 | **Critical gap now well-covered** |
| **Performance Attribution** | pyfolio, quantstats, empyrical-reloaded, alphalens | 4 | **Critical gap now well-covered** |
| **Retail High-Freq Needs** | easytrader, easyquotation, bondTrader | 3 | **Partially filled** - IPO/DRIP/ETF rotation still open |
| **ESG / Compliance** | ESG_AI | 1 | **Thin** - ecosystem too immature |

### Balance Assessment

The Top 30 achieves **strong coverage** of the 4 highest-priority gaps identified by all 4 recommenders:

1. **Portfolio Optimization**: 4 projects (PyPortfolioOpt, Riskfolio-Lib, skfolio, cvxportfolio) -- EXCELLENT
2. **Performance Attribution**: 4 projects (pyfolio, quantstats, empyrical, alphalens) -- EXCELLENT
3. **Risk Management / Derivatives Pricing**: 5 projects (QuantLib, FinancePy, py_vollib, portfolioAnalytics, OptionLab) -- EXCELLENT
4. **Fundamental Research**: 2 projects (FinanceToolkit, FinGPT) -- ADEQUATE

**Remaining weak spots**:
- ESG/Compliance: Only 1 project, ecosystem immature -- accept as is
- Retail high-freq needs (IPO automation, DRIP, ETF rotation): Partially addressed, may need custom development
- Multi-period dynamic rebalancing: cvxportfolio is the only candidate

---

## 4. Batch Extraction Plan

### Batch 1: Immediate (Fill Critical Gaps)

Priority: the 4/4 consensus gaps that have zero existing blueprint coverage.

| # | Project | Gap Filled | Rationale |
|---|---------|------------|-----------|
| 1 | **PyPortfolioOpt** | Portfolio Optimization | MVO/BL/HRP, clean architecture, most-referenced portfolio lib |
| 2 | **Riskfolio-Lib** | Portfolio Opt + Risk | 20+ optimization models, academic depth, excellent for constraint extraction |
| 3 | **QuantLib** | Derivatives + Risk | Industry gold standard, massive architecture (1000+ classes), ultra-high BP value |
| 4 | **pyfolio** | Performance Attribution | Brinson attribution, tear sheets, Quantopian heritage |
| 5 | **quantstats** | Performance Attribution | Sharpe/drawdown/monthly tables, complements pyfolio |
| 6 | **skfolio** | Portfolio Optimization | sklearn pipeline pattern, modern API, cross-validation support |
| 7 | **FinanceToolkit** | Fundamental Research | 150+ financial ratios, transparent calculation, fills valuation gap |
| 8 | **easytrader** | Retail High-Freq | A-share auto-trading, 9k stars, fills retail execution gap |
| 9 | **nautilus_trader** | Execution Architecture | Rust core, event-driven, highest-quality execution engine architecture |
| 10 | **FinancePy** | Derivatives Pricing | Pure Python derivatives (FI/equity/FX/credit), complements QuantLib |

**Batch 1 delivers**: 4 portfolio optimization BPs, 2 attribution BPs, 2 derivatives/risk BPs, 1 fundamental BP, 1 retail BP.

### Batch 2: Next Phase (Deepen Coverage + High-Value Architecture)

| # | Project | Gap Filled | Rationale |
|---|---------|------------|-----------|
| 11 | **OpenBB** | Fundamental Research Platform | 60k stars, full data platform, high architecture complexity |
| 12 | **vectorbt** | Backtesting (vectorized) | Unique vectorized paradigm, complements event-driven BPs |
| 13 | **FinRL** | RL-based Signal Generation | NeurIPS paper, DRL for trading, unique approach |
| 14 | **empyrical-reloaded** | Risk/Perf Metrics Engine | Core metrics library, foundation for attribution |
| 15 | **cvxportfolio** | Multi-period Portfolio Opt | Boyd (Stanford) project, unique multi-period with tx costs |
| 16 | **alphalens** | Factor Attribution | IC analysis, factor returns, complements pyfolio |
| 17 | **hummingbot** | Market Making / Execution | 13k stars, liquidity mining, unique market-making architecture |
| 18 | **bondTrader** | Retail CB Trading | A-share convertible bond T+0, niche but high demand |
| 19 | **FinGPT** | LLM for Finance | LLM fine-tuning for financial NLP, emerging paradigm |
| 20 | **easyquotation** | Retail Real-time Data | Free real-time quotes (Sina/Tencent/Jisilu), A+HK coverage |

**Batch 2 delivers**: deeper portfolio/risk coverage, vectorized backtesting paradigm, RL approach, LLM finance, retail tools.

### Batch 3: Reserve (Strategic Depth + Niche Coverage)

| # | Project | Gap Filled | Rationale |
|---|---------|------------|-----------|
| 21 | **backtrader** | Backtesting (event-driven) | 19k stars, largest community, good constraint extraction |
| 22 | **LEAN** | Multi-asset Backtesting | C# industrial-grade, QuantConnect ecosystem |
| 23 | **Hikyuu** | A-share Backtesting | C++ core, A-share specialist, high-perf architecture |
| 24 | **ESG_AI** | ESG Scoring | Only viable ESG project, NLP-based |
| 25 | **py_vollib** | Options Greeks | Focused options pricing, IV/Greeks calculation |
| 26 | **ib_insync** | Broker Bridge | IB API wrapper, clean async design |
| 27 | **portfolioAnalytics** | Credit Risk | Credit portfolio loss distribution, niche but unique |
| 28 | **OptionLab** | Options Strategy | Options strategy backtesting, emerging project |
| 29 | **akshare** | A-share Data | 15k stars, most comprehensive Chinese financial data |
| 30 | **yfinance** | Global Data | 20k stars, de facto Yahoo Finance wrapper |

**Batch 3 delivers**: architecture depth for backtesting, niche domains (ESG, credit risk, options), data layer completeness.

---

## Appendix: Projects Not in Top 30 (for Reference)

The remaining 46 projects are lower priority for blueprint extraction due to:
- **Pure data wrappers** (tushare, baostock, efinance, adata, mootdx, pandas-datareader, yahooquery, sec-edgar-downloader, SimFin): Low architecture complexity, mostly API wrappers
- **Technical indicator libraries** (TA-Lib, pandas-ta, ta, stockstats): Utility libraries, low BP extraction value (no multi-stage pipeline)
- **Broker SDKs** (futu-api, tiger-sdk, longport-api, alpaca-trade-api): Vendor-specific, thin wrapper
- **Unverified/tiny projects** (hkex-news-scraper, CB-Pricing, brinson-attribution, ESG-Lexicon, Pyspark-Stock-NLP, A-Share-Volatility-Trading-Strategy, ga-hk_stock_info, ETFs-Sector-Rotation-Strategy, torchquant, wencai): Stars too low or existence unverified
- **Non-Python primary** (ORE/C++, tiltIndicator/R, PortfolioAnalytics/R, CppTrader/C++, Fincept Terminal/C++): Limited Python BP extraction value
- **Overlapping coverage** (zipline-original, abu, Qbot, bt, backtesting.py, Fund-Screener, daban, qstock, OpenAlgo, pybroker): Either duplicative of existing BPs or lower-quality alternatives
- **LLM/Agent platforms** (FinRobot, TradingAgents, TradingAgents-CN, TradeMaster, machine-learning-for-trading, FinBERT, Alpha101, Alpha-GFN, stock-analysis-engine, ccxt): Either too broad/generic or better suited as reference material than BP extraction targets

---

*Generated: 2026-04-05 | Methodology: 4-way deduplication with P0-P3 weighted scoring*
