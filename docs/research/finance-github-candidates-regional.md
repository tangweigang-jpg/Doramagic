# Finance GitHub Candidates — Regional & Global

**Created**: 2026-04-14  
**Purpose**: GitHub open-source candidates to complement Doramagic's finance blueprint library, covering China-specific, US-specific, and Global gaps.  
**Search scope**: Stars ≥ 200 preferred (China projects relaxed), Python/JS preferred, real code not API wrappers.

---

## Summary Table

| Gap | Market | Best Candidate | Stars (approx) | Priority |
|-----|--------|---------------|----------------|----------|
| 公募基金分析 | China | refraction-ray/xalpha | 2.3k | P0 |
| 北向资金/沪深港通 | China | akfamily/akshare (bond_china + northbound APIs) | 18k | P0 |
| A股情绪/舆情 | China | wangys96/Bayesian-Stock-Market-Sentiment | ~100 | P1 |
| 中国债券市场 | China | akfamily/akshare (bond module) | 18k | P1 |
| A股财务报表分析 | China | markson14/FinancialReportAnalysis | ~200 | P1 |
| 期货/商品 CTA | China | shinnytech/tqsdk-python | 4k | P0 |
| SEC Edgar分析 | US | dgunning/edgartools | 1.9k | P0 |
| Options Flow | US | hongtao510/SmartMoneyTracker | low | P2 |
| 401k/IRA退休规划 | US | mdlacasse/Owl | ~14 | P2 |
| Tax-Loss Harvesting | US | redstreet/fava_investor | ~300 | P1 |
| US银行监管 | US | (no strong OSS candidate found) | — | P2 |
| FX Trading/Hedging | Global | domokane/FinancePy | 2.6k | P1 |
| Commodity CTRM | Global | je-suis-tm/quant-trading | ~2k | P2 |
| Carbon Credit/ETS | Global | datasets/eu-emissions-trading-system | ~200 | P2 |
| Alternative Data | Global | sallamy2580/python-web-scrapping | low | P2 |
| 宏观经济Dashboard | Global | MajesticKhan/Nowcasting-Python | low | P1 |
| Financial Knowledge Graph | Global | xiaohui-victor-li/FinDKG | ~200 | P1 |

---

## Gap 1: 公募基金分析系统 (Market: China)

Priority: P0

### Candidate 1: refraction-ray/xalpha

- URL: https://github.com/refraction-ray/xalpha
- Stars: ~2,300
- Language: Python
- Description: 基金投资管理回测引擎。支持天天基金等数据源，NAV净值抓取、持仓管理、收益回测、定投策略模拟、数据可视化。
- Why it fits: 覆盖公募基金核心业务流——NAV追踪、回测、定投分析——与"天天基金/蛋卷基金"功能高度对齐。代码质量高，有 pip 包，文档完整。
- Last active: 2023（stable，维护中）

### Candidate 2: piginzoo/fund_analysis

- URL: https://github.com/piginzoo/fund_analysis
- Stars: ~500
- Language: Python
- Description: 中国公募基金爬虫 + 分析工具，覆盖数据爬取（天天基金）、基金经理评估、风格分析。
- Why it fits: 明确包含基金经理评估和风格分析，是 xalpha 的功能补充，更侧重研究视角。
- Last active: 2022（stable）

### Candidate 3: SunshowerC/fund-strategy

- URL: https://github.com/SunshowerC/fund-strategy
- Stars: ~2,000
- Language: JavaScript/TypeScript
- Description: 基金投资策略分析与回测工具，前端可视化强。
- Why it fits: 提供策略层视角（定投、网格、价值平均等），适合作为 xalpha 的策略层补充蓝图。
- Last active: 2022（stable）

---

## Gap 2: 北向资金/沪深港通分析 (Market: China)

Priority: P0

### Candidate 1: akfamily/akshare

- URL: https://github.com/akfamily/akshare
- Stars: ~18,100
- Language: Python
- Description: 开源财经数据接口库，覆盖A股、港股、美股、期货、期权、基金、债券、外汇、数字货币。内置北向资金（沪深港通）接口、QFII数据、外资动向分析。
- Why it fits: 这是中国金融数据领域最权威的开源库，北向资金是其核心数据模块之一，包含实时和历史流入数据。星数最高，生态最成熟。
- Last active: 2026（actively maintained）

### Candidate 2: 1nchaos/adata

- URL: https://github.com/1nchaos/adata
- Stars: ~2,100
- Language: Python
- Description: 免费开源A股量化交易数据库，多数据源融合，包含北向资金实时与历史流入数据、QFII持仓数据。
- Why it fits: adata 是 akshare 的竞品，专注A股，数据源更聚焦，代理切换更稳健，适合对比提取蓝图。
- Last active: 2025（active）

---

## Gap 3: A股情绪分析/舆情监控 (Market: China)

Priority: P1

### Candidate 1: wangys96/Bayesian-Stock-Market-Sentiment

- URL: https://github.com/wangys96/Bayesian-Stock-Market-Sentiment
- Stars: ~100
- Language: Python
- Description: A股舆情分析网站，含爬虫（雪球/东方财富）、贝叶斯文本分类、TF-IDF、Django后端、数据可视化。
- Why it fits: 完整的中国股市舆情分析系统，明确针对A股中文社媒（雪球、东方财富），涵盖爬虫+NLP+展示全链路。星数低但功能完整，是此类中文情绪分析的标杆案例。
- Last active: 2021（stable，功能完整可提取蓝图）

### Candidate 2: Austin-Patrician/eastmoney

- URL: https://github.com/Austin-Patrician/eastmoney
- Stars: ~300
- Language: Python
- Description: VibeAlpha Terminal，专注A股市场的智能金融分析平台，集成基金分析、股票监控、商品追踪和市场情绪分析，通过LLM自动生成盘前/盘后分析报告。
- Why it fits: 代表最新的AI+A股情绪分析实践，整合多维情绪指标，含LLM决策层，体现当前技术前沿。
- Last active: 2025（active）

### Candidate 3: algosenses/Stock_Market_Sentiment_Analysis

- URL: https://github.com/algosenses/Stock_Market_Sentiment_Analysis
- Stars: ~200
- Language: Python
- Description: 股市情感分析，专注A股市场文本情感挖掘，涵盖词典方法和机器学习方法。
- Why it fits: 方法论更系统，适合提取情绪分析的算法蓝图（词典法 vs ML法对比）。
- Last active: 2022（stable）

---

## Gap 4: 中国债券市场分析 (Market: China)

Priority: P1

**注**：专门针对中国银行间债券/信用债的独立OSS项目极少。最佳策略是提取 akshare 的债券模块作为蓝图。

### Candidate 1: akfamily/akshare (bond module)

- URL: https://github.com/akfamily/akshare/blob/main/akshare/bond/bond_china_money.py
- Stars: ~18,100 (主库)
- Language: Python
- Description: AKShare的债券子模块，覆盖中国国债收益率曲线（中债信息网）、企业债、可转债、银行间债券市场数据。`bond_china_yield()` 函数直接对接中国债券信息网官方数据。
- Why it fits: 这是获取中国债券市场数据最直接的开源路径，覆盖银行间市场、信用债、利率债。蓝图价值在于数据管道设计和收益率曲线构建方法。
- Last active: 2026（actively maintained）

### Candidate 2: domokane/FinancePy (bond + credit modules)

- URL: https://github.com/domokane/FinancePy
- Stars: ~2,600
- Language: Python
- Description: 全面的金融衍生品定价库，覆盖固定收益、FX、信用衍生品，含债券定价、收益率曲线拟合、信用违约互换（CDS）定价。
- Why it fits: 提供中国信用债分析所需的底层定价引擎（YTM计算、久期、凸性、信用利差），与中国市场数据对接可完成完整分析链路。
- Last active: 2024（active）

---

## Gap 5: A股财务报表分析 (Market: China)

Priority: P1

### Candidate 1: markson14/FinancialReportAnalysis

- URL: https://github.com/markson14/FinancialReportAnalysis
- Stars: ~200
- Language: Python
- Description: 中国A股市场分析脚本，使用AKShare获取实时和历史股票数据，计算关键财务指标（ROE、P/E、P/B等），支持多维度财务健康评估。
- Why it fits: 明确针对A股CSRC报表格式，与wind/choice风格的财务分析对齐，提供三张报表解析+财务指标计算的完整蓝图。
- Last active: 2024（active）

### Candidate 2: MiaLi0521/financial-report-analysis

- URL: https://github.com/MiaLi0521/financial-report-analysis
- Stars: ~150
- Language: Python
- Description: A股上市公司财务报告分析，包含资产负债表、利润表、现金流量表的解析和关键指标提取。
- Why it fits: 专注A股上市公司财务报告的结构化解析，补充了 markson14 版本的报表解析深度。
- Last active: 2022（stable）

### Candidate 3: liangdabiao/easy_investment_Agent_crewai

- URL: https://github.com/liangdabiao/easy_investment_Agent_crewai
- Stars: ~300
- Language: Python
- Description: 基于AKShare和CrewAI的A股智能分析平台，多Agent协作提供专业投资分析，覆盖实时行情、财务数据、资金流向、市场情绪。
- Why it fits: 代表A股财务分析的AI-native实践，展示如何用多Agent架构整合CSRC财务数据，是"现代风格"蓝图候选。
- Last active: 2025（active）

---

## Gap 6: 期货/商品 CTA 策略 (Market: China)

Priority: P0

### Candidate 1: shinnytech/tqsdk-python

- URL: https://github.com/shinnytech/tqsdk-python
- Stars: ~4,000
- Language: Python
- Description: 天勤量化开发包，专注中国期货量化。支持上期所/大商所/郑商所全品种，提供实时行情+历史K线+实盘交易+回测，单线程异步模型，原生支持CTA策略。
- Why it fits: 这是中国商品期货量化的事实标准SDK，完整覆盖上期所/大商所/郑商所三大交易所，CTA策略框架完整。比vnpy更轻量，专注期货垂直场景。
- Last active: 2025（active）

### Candidate 2: vnpy/vnpy

- URL: https://github.com/vnpy/vnpy
- Stars: ~25,000+
- Language: Python
- Description: 基于Python的开源量化交易平台，内置CTA策略引擎（cta_strategy），支持全国期货品种通过CTP接口交易，是国内私募基金、期货公司最广泛使用的量化平台。
- Why it fits: 国内使用最广的CTA量化框架，有完整的策略生命周期管理（信号生成→订单管理→风控→执行），蓝图价值极高。星数排GitHub量化框架前三。
- Last active: 2025（active）

### Candidate 3: yutiansut/QUANTAXIS

- URL: https://github.com/yutiansut/QUANTAXIS
- Stars: ~8,000
- Language: Python
- Description: 支持任务调度、分布式部署的股票/期货/期权数据/回测/模拟/交易/可视化全栈量化解决方案。
- Why it fits: 提供CTA策略的分布式架构视角，补充 tqsdk 和 vnpy 在分布式调度层的蓝图。
- Last active: 2022（stable，成熟归档）

---

## Gap 7: SEC Edgar Filing Analysis (Market: US)

Priority: P0

### Candidate 1: dgunning/edgartools

- URL: https://github.com/dgunning/edgartools
- Stars: ~1,900
- Language: Python
- Description: Python library to access and analyze SEC EDGAR filings as structured Python objects. Parses 10-K, 10-Q, 8-K, 13-F, proxy statements, XBRL financial data. Built-in MCP server for LLM integration. No API keys required.
- Why it fits: 最完整的EDGAR开源工具，将SEC filings转化为结构化Python对象（不是原始HTML/XML），有XBRL解析、财务报表提取，且已支持Claude MCP，与Doramagic生态天然契合。
- Last active: 2025（very active）

### Candidate 2: lefterisloukas/edgar-crawler

- URL: https://github.com/lefterisloukas/edgar-crawler
- Stars: ~382
- Language: Python
- Description: Open-source toolkit to download SEC EDGAR reports and extract textual data from specific item sections (10-K, 10-Q, 8-K) into structured JSON. Presented at WWW 2025.
- Why it fits: 专注NLP数据集构建，将filing文本按Item结构化提取为JSON，是AI/ML下游任务的最佳数据管道设计蓝图。学术认可度高（WWW 2025）。
- Last active: 2024-10（active）

### Candidate 3: alphanome-ai/sec-parser

- URL: https://github.com/alphanome-ai/sec-parser
- Stars: ~400
- Language: Python
- Description: Parse SEC EDGAR HTML documents into a semantic tree of elements corresponding to the visual structure. Designed for AI/ML/LLM pre-processing.
- Why it fits: 填补了"结构感知解析"的空白，将HTML转化为语义树而非平文本，对LLM上下文窗口利用更高效。适合提取解析架构蓝图。
- Last active: 2024（active）

---

## Gap 8: Options Flow Analysis (Market: US)

Priority: P2

**注**: 此领域OSS项目质量普遍偏低，大多是对Unusual Whales等付费数据源的封装。真正的"unusual options activity detection"逻辑较难在OSS中找到高质量实现。

### Candidate 1: hongtao510/SmartMoneyTracker

- URL: https://github.com/hongtao510/SmartMoneyTracker
- Stars: ~50
- Language: Python
- Description: 追踪机构投资者"聪明钱"动向，基于Donoho (2003)研究方法实时检测异常期权成交量。
- Why it fits: 有明确的学术方法论来源（Steve Donoho的内幕交易早期检测研究），检测逻辑基于成交量异常+持仓比例分析，是少有的有理论支撑的OSS实现。
- Last active: 2022（stable）

### Candidate 2: Andrew-Reis-SMU-2022/Options_Based_Trading

- URL: https://github.com/Andrew-Reis-SMU-2022/Options_Based_Trading
- Stars: ~30
- Language: Python
- Description: 基于成交量加权平均分析unusual OTM options activity，可生成日报/周报。
- Why it fits: 实现了unusual options activity检测的核心逻辑（OTM期权成交量异常判断），代码简洁可参考架构。
- Last active: 2022（stable）

**推荐策略**: 此Gap星数均偏低，建议降级为P2，蓝图价值有限。可考虑结合FinancePy的Greeks计算模块（domokane/FinancePy）单独编写约束。

---

## Gap 9: 401k/IRA Retirement Planning (Market: US)

Priority: P2

### Candidate 1: mdlacasse/Owl

- URL: https://github.com/mdlacasse/Owl
- Stars: ~14
- Language: Python
- Description: Retirement planner using mixed-integer linear programming (SciPy) to optimize withdrawals, Roth conversions, contributions across 401k/IRA/taxable accounts. Streamlit frontend hosted at owlplanner.streamlit.app.
- Why it fits: 功能最完整的退休规划OSS，明确支持401k/IRA/Roth账户类型，LP优化算法专业，有可用的Web UI。星数低但质量高，是此领域最接近"正确解"的实现。
- Last active: 2024（active）

### Candidate 2: willauld/fplan

- URL: https://github.com/willauld/fplan
- Stars: ~200
- Language: Go
- Description: Retirement planning financial calculator using linear programming to maximize minimum annual spending, accounting for Social Security, federal taxes, and IRA withdrawals.
- Why it fits: LP方法更成熟，考虑了Social Security和联邦税，提供跨账户最优提款策略，蓝图价值在于多账户税务优化的算法设计。
- Last active: 2023（stable）

---

## Gap 10: Tax-Loss Harvesting (Market: US)

Priority: P1

### Candidate 1: redstreet/fava_investor

- URL: https://github.com/redstreet/fava_investor
- Stars: ~300
- Language: Python
- Description: Comprehensive investment analysis for Beancount/Fava (plain-text accounting). Modules include: tax-loss harvester (wash sale detection), asset allocation by class/account, cash drag analysis.
- Why it fits: 税损收割实现最完整——包含 wash sale rule 检测、损失阈值设置、多账户扫描，且基于 beancount 的 double-entry 数据结构，算法逻辑清晰可提取。
- Last active: 2024（active）

### Candidate 2: danguetta/rebalancer

- URL: https://github.com/danguetta/rebalancer
- Stars: ~150
- Language: Python
- Description: Portfolio rebalancer with tax-loss harvesting using eTrade API. Combines rebalancing and TLH in a single optimization pass.
- Why it fits: 将TLH与再平衡合并在一次优化中，是更工程化的实现，提供了"同时做TLH+rebalancing"的蓝图模式。
- Last active: 2022（stable）

---

## Gap 11: US Bank Regulatory (Dodd-Frank/CCAR/DFAST) (Market: US)

Priority: P2

**注**: 经过搜索，此领域几乎没有达到Stars ≥ 200且功能完整的开源Python实现。主要原因：CCAR/DFAST是监管强制测试，银行倾向于内部实现或购买商业解决方案（Moody's Analytics、SAS等），不对外开源。

### Candidate 1: KhalilBelghouat/StressTestingLoanPortfolio

- URL: https://github.com/KhalilBelghouat/StressTestingLoanPortfolio
- Stars: ~50
- Language: Python
- Description: 基于经济情景的贷款组合压力测试，Python实现。
- Why it fits: 是此领域唯一有实质代码的Python OSS，虽然不是完整CCAR框架，但覆盖了压力测试的核心逻辑（情景生成→信用损失计算）。

**推荐**: 此Gap建议降级为P2或放弃单独蓝图，考虑将CCAR/DFAST作为约束条目并入银行风险管理蓝图。

---

## Gap 12: FX Trading / Hedging Framework (Market: Global)

Priority: P1

### Candidate 1: domokane/FinancePy

- URL: https://github.com/domokane/FinancePy
- Stars: ~2,600
- Language: Python
- Description: 全面的金融衍生品定价库，覆盖FX期权、FX远期、外汇掉期、交叉货币互换（XCS），含Black-Scholes/Garman-Kohlhagen定价、Delta/Vega等Greeks计算。
- Why it fits: 企业FX对冲框架的核心是衍生品定价（FX Forward、FX Option）和风险敞口计算（Delta hedging），FinancePy提供了这一切且文档含60+示例notebook。由EDHEC商学院教授维护，学术+实务双重认可。
- Last active: 2024（active）

### Candidate 2: DarkThyme/RL-Driven-FX-Options-Trading-and-Hedging-Strategies

- URL: https://github.com/DarkThyme/RL-Driven-FX-Options-Trading-and-Hedging-Strategies
- Stars: ~100
- Language: Python
- Description: 强化学习（Deep Q-Learning）驱动的FX期权交易与对冲策略仿真，含协整套利、动量指标、蒙特卡洛对冲、Greeks管理。
- Why it fits: 代表FX对冲的AI-native实现视角，Delta对冲+蒙特卡洛+RL三种方法对比，提供现代FX对冲蓝图的方法论广度。
- Last active: 2024（active）

---

## Gap 13: Commodity Trading / CTRM (Market: Global)

Priority: P2

**注**: 完整的CTRM（Commodity Trade and Risk Management）系统——含实物交割、物流、合规、会计科目联动——几乎没有开源实现。商业系统（Openlink/TRIPLE POINT/Brady）才有完整CTRM。开源项目只覆盖量化/策略层。

### Candidate 1: je-suis-tm/quant-trading

- URL: https://github.com/je-suis-tm/quant-trading
- Stars: ~2,000
- Language: Python
- Description: Python量化交易策略集合，含 Commodity Trading Advisor (CTA)、VIX Calculator、蒙特卡洛、Oil Money项目（原油价格与货币相关性分析）。
- Why it fits: 最接近CTRM中"交易策略"层的OSS实现，Oil Money子项目专门研究大宗商品与汇率联动，CTA实现包含商品期货信号生成逻辑。
- Last active: 2022（stable）

### Candidate 2: tradingeconomics/tradingeconomics-python

- URL: https://github.com/tradingeconomics/tradingeconomics-python
- Stars: ~200
- Language: Python
- Description: Trading Economics Python SDK，提供商品价格、宏观数据、经济日历的实时和历史数据接口。
- Why it fits: CTRM系统的数据层——商品价格、库存数据、宏观驱动因素——都可通过此库获取，是构建大宗商品分析管道的数据基础。
- Last active: 2023（stable）

---

## Gap 14: Carbon Credit / Emissions Trading (Market: Global)

Priority: P2

### Candidate 1: datasets/eu-emissions-trading-system

- URL: https://github.com/datasets/eu-emissions-trading-system
- Stars: ~200
- Language: Python/CSV
- Description: EU ETS（欧盟碳排放交易体系）数据集，来源EUTL（EU Transaction Log），包含各国、各行业、各年度的排放量与配额数据。
- Why it fits: 这是EU ETS分析的标准数据基础，数据规范完整，是构建碳市场分析蓝图的数据层入口。Python处理脚本可直接参考。
- Last active: 2024（active，跟随官方数据更新）

### Candidate 2: dw-data/eu-ets

- URL: https://github.com/dw-data/eu-ets
- Stars: ~50
- Language: Python
- Description: DW（德意志之声）数据新闻团队的EU ETS分析项目，含完整的碳价分析、配额价格趋势可视化。
- Why it fits: 提供新闻数据团队视角的碳市场分析蓝图，展示如何从宏观叙事角度构建碳交易分析工作流。
- Last active: 2021（stable）

**注**: 自愿碳市场（VCM）分析的OSS项目极少，建议此Gap聚焦EU ETS合规市场，暂不覆盖VCM。

---

## Gap 15: Alternative Data Pipeline (Market: Global)

Priority: P2

### Candidate 1: sallamy2580/python-web-scrapping

- URL: https://github.com/sallamy2580/python-web-scrapping
- Stars: ~150
- Language: Python
- Description: 详细的金融数据爬虫教程集合，涵盖：Reddit WallStreetBets、CME（期权+期货）、美国财政部、CFTC、LME、MacroTrends、SHFE，以及替代数据源（Tomtom交通、BBC/路透/彭博新闻）。
- Why it fits: 覆盖最广泛的另类数据源类型，从传统金融数据到另类数据（交通、新闻情绪）都有爬虫实现，是Alternative Data Pipeline的多源采集蓝图。
- Last active: 2022（stable）

### Candidate 2: DemonDamon/FinnewsHunter

- URL: https://github.com/DemonDamon/FinnewsHunter
- Stars: ~100
- Language: Python
- Description: Multi-agent金融情报平台，基于AgenticX，支持实时新闻分析、情绪融合、Alpha因子挖掘。
- Why it fits: 代表最新的AI-native另类数据处理实践，multi-agent架构处理非结构化金融情报，体现当前技术前沿，适合提取现代另类数据管道设计蓝图。
- Last active: 2025（active）

---

## Gap 16: Macroeconomic Dashboard (Market: Global)

Priority: P1

### Candidate 1: MajesticKhan/Nowcasting-Python

- URL: https://github.com/MajesticKhan/Nowcasting-Python
- Stars: ~80
- Language: Python
- Description: 将FRBNY（纽约联储）MATLAB版Nowcasting框架移植为Python，实现动态因子模型（DFM），可基于高频数据对GDP增速进行实时预测。
- Why it fits: 基于权威机构（纽约联储）的nowcasting方法论，动态因子模型是宏观经济实时跟踪的标准工具，代码完整可运行。
- Last active: 2021（stable，方法论稳定）

### Candidate 2: genekindberg/DFM-Nowcaster

- URL: https://github.com/genekindberg/DFM-Nowcaster
- Stars: ~50
- Language: Python
- Description: Python实现的动态因子模型（DFM），用多个高频序列nowcast季度GDP，含Kalman滤波、EM算法估计。
- Why it fits: 纯Python实现（无MATLAB依赖），更易于生产化，提供DFM nowcasting的工程化蓝图。
- Last active: 2022（stable）

### Candidate 3: moshesham/Economic-Dashboard

- URL: https://github.com/moshesham/Economic-Dashboard
- Stars: ~100
- Language: Python
- Description: 综合经济智能平台，实时接入60+经济指标（来自FRED和Yahoo Finance），支持多国对比分析。
- Why it fits: 直接对应"Multi-country macro indicator tracking"需求，覆盖FRED数据接入+可视化Dashboard的完整实现。
- Last active: 2024（active）

---

## Gap 17: Financial Knowledge Graph (Market: Global)

Priority: P1

### Candidate 1: xiaohui-victor-li/FinDKG

- URL: https://github.com/xiaohui-victor-li/FinDKG
- Stars: ~200
- Language: Python
- Description: Financial Dynamic Knowledge Graph，基于~40万篇WSJ金融新闻（1999-2023）构建的动态知识图谱。包含ICKG（LLM-based知识图谱生成器，基于Vicuna-7B微调）和KGTransformer（时序链接预测模型）。定义了15种关系类型和12种实体类型。发表于ACM ICAIF 2024。
- Why it fits: 学术级别的金融知识图谱实现，包含公司关系建模、供应链映射、事件图谱，完整覆盖Gap描述的三个维度。LLM+KG的架构代表技术前沿，有论文背书。
- Last active: 2024（active）

### Candidate 2: KevinFasusi/supplychainpy

- URL: https://github.com/KevinFasusi/supplychainpy
- Stars: ~350
- Language: Python
- Description: 供应链分析、建模与仿真Python库，覆盖库存管理、需求预测、供应链网络分析。
- Why it fits: 覆盖知识图谱中"供应链映射"的分析层，提供供应链量化分析的完整工具箱，可作为金融知识图谱供应链维度的分析后端。
- Last active: 2022（stable）

---

## Blueprint Extraction Recommendations

### Tier 1: 立即提取（质量高、紧迫性高）

| 项目 | 蓝图类型 | 提取难度 |
|------|---------|---------|
| dgunning/edgartools | SEC文件解析全栈架构 | 低（文档完善） |
| refraction-ray/xalpha | 公募基金投资管理引擎 | 低（代码清晰） |
| shinnytech/tqsdk-python | 中国商品期货CTA框架 | 中（需理解异步模型） |
| vnpy/vnpy (cta_strategy module) | CTA策略生命周期管理 | 中（代码量大，聚焦子模块） |
| akfamily/akshare (northbound + bond) | 北向资金+债券数据管道 | 低（接口文档完善） |

### Tier 2: 次优先（有价值但可延后）

| 项目 | 蓝图类型 | 提取难度 |
|------|---------|---------|
| domokane/FinancePy | FX+固收衍生品定价框架 | 高（数学密集） |
| xiaohui-victor-li/FinDKG | 金融动态知识图谱 | 高（LLM微调+GNN） |
| lefterisloukas/edgar-crawler | SEC NLP数据集构建管道 | 低 |
| redstreet/fava_investor | 税损收割+资产配置框架 | 中 |
| moshesham/Economic-Dashboard | 宏观经济多指标Dashboard | 低 |

### Tier 3: 参考或跳过

| 项目 | 建议 | 原因 |
|------|------|------|
| KhalilBelghouat/StressTestingLoanPortfolio | 跳过 | 功能不完整，无法支撑CCAR蓝图 |
| mdlacasse/Owl | 参考约束 | 14星，质量高但受众窄 |
| hongtao510/SmartMoneyTracker | 跳过 | Stars太低，方法论借鉴价值有限 |
| datasets/eu-emissions-trading-system | 数据源参考 | 数据集而非代码库 |

---

## Notes on Search Quality

1. **中国债券市场**: 独立的中国银行间债券OSS几乎没有，最佳路径是从akshare债券模块提取蓝图。
2. **CCAR/DFAST**: 银行监管压测无有效OSS，建议将此需求转化为约束条目而非独立蓝图。
3. **CTRM系统**: 完整CTRM商业秘密，OSS只能覆盖策略层，不含实物交割生命周期。
4. **Carbon/VCM**: 欧盟ETS有数据集，自愿碳市场几乎没有OSS实现。
5. **北向资金**: akshare已是事实标准，无需另寻专属项目。

---

*Research conducted: 2026-04-14 | Sources: GitHub WebSearch*
