# Finance Blueprint Library — 扩展路线图 (EXTRACTION_ROADMAP)

> **文档用途**：指导 Doramagic 金融蓝图库从 59 个蓝图扩展至 ~90 个蓝图的系统性计划
> **方法论**：用户需求图谱 → 覆盖度差距分析 → GitHub 候选搜索 → 优先级排序
> **生成日期**：2026-04-14
> **输入文档**：
> - `docs/research/finance-user-need-taxonomy.md` — 7+4 类用户旅程需求分类
> - `docs/research/finance-gap-analysis.md` — 59 蓝图覆盖度矩阵
> - `docs/research/finance-github-candidates-core.md` — 核心缺口 GitHub 候选
> - `docs/research/finance-github-candidates-regional.md` — 中国/美国/全球区域候选

---

## 1. 概述 (Overview)

### 为什么需要这份路线图

Doramagic 当前金融蓝图库包含 **59 个蓝图**（finance-bp-001 ~ finance-bp-059），但覆盖严重偏向**量化交易与组合构建**（TRD 侧），在银行合规、信贷风控、财富管理、保险精算等领域存在结构性空白。

**现状**：
- 量化策略蓝图 16 个（EXCELLENT），组合构建蓝图 6 个（EXCELLENT）——过饱和
- 监管合规蓝图 3 个（THIN），保险精算 0 个（ABSENT），贷款支付 2 个（THIN）——严重不足
- 事件驱动回测框架有 5 个高度同质蓝图（bp-002/005/038/042/043），Multi-Agent LLM 分析有 3 个几乎相同定位的蓝图（bp-045/051/054）

**目标**：
- 通过补充 **30 个新蓝图**，将总数提升至 **~89 个**
- 消除所有 ABSENT 类别，将所有 THIN 类别提升至 ADEQUATE 以上
- 形成"前台交易 + 中台风控 + 后台合规"的完整知识链条
- 平衡中国/美国/全球三大市场的覆盖度

---

## 2. 用户需求图谱摘要 (User Need Taxonomy Summary)

### 7+4 类用户旅程

**核心 7 类**（零售 + 机构投资旅程）：

| # | 类别 | 核心问题 | 子需求数 |
|---|------|---------|---------|
| 1 | 发现机会 (Opportunity Discovery) | 在海量标的中找到值得关注的机会 | 7（NL选股、形态识别、资金流向、行业轮动、事件驱动、宏观传导、多资产扫描） |
| 2 | 分析决策 (Analysis & Decision) | 对选定标的做深度研判 | 7（基本面、研报摘要、宏观解读、异动解释、回测、因子归因、另类数据） |
| 3 | 构建组合 (Portfolio Construction) | 科学组建投资组合 | 5（资产配置、组合优化、基金筛选、智能再平衡、ESG整合） |
| 4 | 执行交易 (Trade Execution) | 以最低成本完成买卖 | 4（交易成本、执行算法、期权策略、期货对冲） |
| 5 | 监控管理 (Monitoring & Management) | 持续跟踪风险与状态 | 5（持仓监控、风险评估、分组管理、业绩归因、压力测试） |
| 6 | 合规报告 (Compliance & Reporting) | 满足监管与披露义务 | 5（监管报告、AML/KYC、信息披露、资本计算、IFRS 9） |
| 7 | 知识学习 (Knowledge & Learning) | 系统提升金融认知 | 4（百科、投教、量化入门、CFA/FRM） |

**延伸 4 类**（超出零售投资视角）：

| # | 类别 | 核心问题 | 子需求数 |
|---|------|---------|---------|
| 8 | 信用与风险管理 | 企业/零售信贷、精算、流动性 | 5 |
| 9 | 财富管理与规划 | 智能投顾、退休、税务、遗产 | 4 |
| 10 | 机构运营与基础设施 | 结算、资金管理、NL2SQL、Multi-Agent | 4 |
| 11 | 另类数据与信号工程 | 卫星、社交情绪、供应链、爬虫 | 4 |

### 关键洞察

- **iWencai 对标**：分类 1-5 覆盖了 iWencai/同花顺用户的核心旅程（选股→分析→组合→交易→监控），当前蓝图在此领域覆盖较好但缺少 NL-to-filter 和事件驱动机会发现
- **全球用户扩展**：分类 6/8/9/10 是中国用户之外的全球金融机构刚需，当前几乎零覆盖
- **产品哲学约束**：分类 7（知识学习）与"不教用户做事，给他工具"的产品灵魂有冲突，不建议作为独立蓝图扩展方向

---

## 3. 现有 59 项目覆盖度矩阵 (Coverage Matrix)

### 3.1 覆盖评级矩阵

| # | 需求类别 | 覆盖评级 | 相关蓝图数 | 主要缺口 | 填补优先级 |
|---|---------|---------|-----------|---------|-----------|
| 1 | Opportunity Discovery 机会发现 | GOOD | 7 | NL查询、板块追踪、事件驱动 | P1 |
| 2 | Analysis & Decision 分析决策 | GOOD | 7 | 研报生成、技术分析体系 | P1 |
| 3 | Quantitative Strategy 量化策略 | **EXCELLENT** | 16 | 统计套利、期权策略（冗余>缺口） | P2 |
| 4 | Portfolio Construction 组合构建 | **EXCELLENT** | 6 | 智能再平衡、因子风险模型 | P2 |
| 5 | Trade Execution 交易执行 | GOOD | 6 | 国内券商API、OMS | P1 |
| 6 | Monitoring & Management 监控管理 | ADEQUATE | 5 | 实时风险预警、Brinson归因 | P1 |
| 7 | Credit Risk 信用风险 | ADEQUATE | 3 | IFRS 9/CECL、PD/LGD/EAD | P1 |
| 8 | Market Risk 市场风险 | GOOD | 7 | FRTB、历史模拟VaR | P1 |
| 9 | Regulatory & Compliance 监管合规 | **THIN** | 3 | AML/KYC、监管报告、A股合规 | **P0** |
| 10 | Wealth Management 财富管理 | **THIN** | 3 | Robo-Advisor、退休规划 | P1 |
| 11 | Insurance/Actuarial 保险精算 | **ABSENT** | 0 | 全领域缺失 | P0 |
| 12 | Treasury/ALM 资金管理 | **THIN** | 2 | 流动性、IRRBB、FX对冲 | P1 |
| 13 | Fixed Income Deep 固收深度 | ADEQUATE | 5 | MBS/ABS、中国债市 | P2 |
| 14 | Lending/Payments 贷款支付 | **THIN** | 2 | LOS、反欺诈、BNPL | P1 |
| 15 | Alternative Data 另类数据 | ADEQUATE | 5 | 财报NLP、社交情绪 | P2 |
| 16 | Macro & Multi-Asset 宏观多资产 | ADEQUATE | 7 | 经济指标仪表板、大宗商品 | P2 |
| 17 | AI/LLM Finance AI金融应用 | GOOD | 8 | NL-to-filter、RAG知识库 | P1 |
| 18 | Knowledge & Education 知识教育 | **THIN** | 0 | 与产品哲学冲突，不建议扩展 | — |

### 3.2 冗余热点

| 冗余领域 | 涉及蓝图 | 建议处理 |
|---------|---------|---------|
| 事件驱动回测（5个） | bp-002(zipline), bp-005(rqalpha), bp-038(hikyuu), bp-042(backtrader), bp-043(LEAN) | 通过 `relations` 字段明确差异化（市场/性能/架构风格），避免用户选择困难 |
| Multi-Agent LLM（3个） | bp-045(TradingAgents), bp-051(FinRobot), bp-054(TradingAgents-CN) | 审视差异化定位，确保 `known_use_cases` 清晰区分 |
| 绩效分析（3个） | bp-014(QuantStats), bp-015(pyfolio), bp-030(empyrical) | bp-030 是底层统计函数，bp-014/015 是上层报告，存在合理分层 |
| 衍生品定价（2个） | bp-013(QuantLib), bp-019(FinancePy) | 保留：QuantLib=机构级C++绑定，FinancePy=纯Python易用性优先 |

---

## 4. 推荐补充项目列表 (Recommended New Projects)

### P0 — 必须补充（关键结构性缺口，最高用户价值）

| # | Blueprint ID | 项目名 | GitHub URL | Stars | 填补需求 | 市场 |
|---|-------------|-------|-----------|-------|---------|------|
| 1 | finance-bp-060 | AMLSim 反洗钱模拟 | https://github.com/IBM/AMLSim | ~304 | 监管合规：AML交易模拟与模式检测 | Global |
| 2 | finance-bp-061 | OpenSanctions 制裁名单 | https://github.com/opensanctions/opensanctions | ~703 | 监管合规：制裁/PEP筛查与实体匹配 | Global |
| 3 | finance-bp-062 | IFRS 9 预期信用损失 | https://github.com/naenumtou/ifrs9 | ~70 | 信用风险：IFRS 9三阶段ECL计算（PD/LGD/EAD/Staging） | Global |
| 4 | finance-bp-063 | chainladder 精算准备金 | https://github.com/casact/chainladder-python | ~200 | 保险精算：P&C准备金（Chain Ladder/BF/Mack随机） | Global |
| 5 | finance-bp-064 | insurance_python Solvency II | https://github.com/open-source-modelling/insurance_python | ~100 | 保险精算：Solvency II SCR计算（Smith-Wilson曲线） | EU |
| 6 | finance-bp-065 | pyliferisk 寿险精算 | https://github.com/franciscogarate/pyliferisk | ~119 | 保险精算：死亡率表、寿险定价、年金计算 | Global |
| 7 | finance-bp-066 | wealthbot 智能投顾 | https://github.com/wealthbot-io/wealthbot | ~675 | 财富管理：Robo-Advisor全流程（风险测评→配置→再平衡→TLH） | US |
| 8 | finance-bp-067 | firesale_stresstest 银行压力测试 | https://github.com/ox-inet-resilience/firesale_stresstest | ~50 | 监管合规：系统性银行压力测试（EBA数据+传染模型） | EU/Global |
| 9 | finance-bp-068 | xalpha 公募基金管理 | https://github.com/refraction-ray/xalpha | ~2,300 | 财富管理：中国公募基金NAV追踪、回测、定投策略 | China |
| 10 | finance-bp-069 | tqsdk 中国商品期货 | https://github.com/shinnytech/tqsdk-python | ~4,000 | 交易执行：中国期货CTA策略框架（三大交易所全品种） | China |
| 11 | finance-bp-070 | edgartools SEC文件解析 | https://github.com/dgunning/edgartools | ~1,900 | 另类数据：SEC EDGAR结构化解析（10-K/10-Q/XBRL/MCP） | US |

**P0 小计**：11 个蓝图

### P1 — 高优先级（重要市场覆盖，强业务驱动）

| # | Blueprint ID | 项目名 | GitHub URL | Stars | 填补需求 | 市场 |
|---|-------------|-------|-----------|-------|---------|------|
| 12 | finance-bp-071 | frappe/lending 贷款管理 | https://github.com/frappe/lending | ~264 | 贷款支付：贷款全生命周期（发放→还款→催收） | Global |
| 13 | finance-bp-072 | formancehq/ledger 金融账本 | https://github.com/formancehq/ledger | ~1,100 | 贷款支付：双重记账账本引擎（Numscript DSL） | Global |
| 14 | finance-bp-073 | FinRobot AI研报生成 | https://github.com/AI4Finance-Foundation/FinRobot | ~4,800 | AI金融：Multi-Agent研究报告自动生成 | Global |
| 15 | finance-bp-074 | stock-screener NL选股 | https://github.com/xang1234/stock-screener | ~50 | AI金融：NL-to-filter自然语言选股（80+筛选条件） | Global |
| 16 | finance-bp-075 | ORE XVA引擎 | https://github.com/OpenSourceRisk/Engine | ~658 | 市场风险：CVA/DVA/FVA/SIMM交对手信用风险估值调整 | Global |
| 17 | finance-bp-076 | AbsBox MBS/ABS现金流 | https://github.com/yellowbean/AbsBox | ~56 | 固收深度：结构化产品waterfall建模（分层/触发/提前还款） | Global |
| 18 | finance-bp-077 | Open_Source_Economic_Model 资产负债管理 | https://github.com/open-source-modelling/Open_Source_Economic_Model | ~40 | 资金管理：ALM经济情景生成（ESG）+资产负债建模 | Global |
| 19 | finance-bp-078 | FinancePy FX衍生品 | https://github.com/domokane/FinancePy | ~2,600 | 资金管理：FX期权/远期/掉期定价与Delta对冲 | Global |
| 20 | finance-bp-079 | fava_investor 税损收割 | https://github.com/redstreet/fava_investor | ~300 | 财富管理：Tax-Loss Harvesting（Wash Sale检测） | US |
| 21 | finance-bp-080 | akshare 北向资金模块 | https://github.com/akfamily/akshare | ~18,100 | 机会发现：沪深港通北向资金+A股债券数据管道 | China |
| 22 | finance-bp-081 | FinDKG 金融知识图谱 | https://github.com/xiaohui-victor-li/FinDKG | ~200 | AI金融：动态金融知识图谱（LLM+KG+时序预测） | Global |
| 23 | finance-bp-082 | Economic-Dashboard 宏观仪表板 | https://github.com/moshesham/Economic-Dashboard | ~100 | 宏观多资产：60+经济指标实时接入+多国对比Dashboard | Global |
| 24 | finance-bp-083 | eastmoney A股情绪平台 | https://github.com/Austin-Patrician/eastmoney | ~300 | 另类数据：A股市场AI情绪分析（LLM盘前盘后报告） | China |
| 25 | finance-bp-084 | vnpy CTA策略引擎 | https://github.com/vnpy/vnpy | ~25,000 | 交易执行：国内最广泛使用的CTA量化平台（CTP接口） | China |

**P1 小计**：14 个蓝图

### P2 — 中优先级（深化现有领域或覆盖长尾需求）

| # | Blueprint ID | 项目名 | GitHub URL | Stars | 填补需求 | 市场 |
|---|-------------|-------|-----------|-------|---------|------|
| 26 | finance-bp-085 | openLGD 违约损失率建模 | https://github.com/open-risk/openLGD | ~85 | 信用风险：LGD统计估计（联邦学习/传统方法） | Global |
| 27 | finance-bp-086 | open-climate-investing 气候因子 | https://github.com/opentaps/open-climate-investing | ~48 | 宏观多资产：BMG碳风险因子+气候对齐组合优化 | Global |
| 28 | finance-bp-087 | sa-ccr-python SA-CCR监管资本 | https://github.com/sa-ccr/sa-ccr-python | ~30 | 监管合规：Basel III标准化交对手信用风险计算 | Global |
| 29 | finance-bp-088 | MarksonFinancialReport A股财报分析 | https://github.com/markson14/FinancialReportAnalysis | ~200 | 分析决策：A股CSRC报表解析+关键财务指标计算 | China |
| 30 | finance-bp-089 | edgar-crawler SEC NLP管道 | https://github.com/lefterisloukas/edgar-crawler | ~382 | 另类数据：SEC Filing文本提取+NLP数据集构建（WWW 2025） | US |

**P2 小计**：5 个蓝图

---

### 4.1 项目详细说明

#### P0 项目详细

**finance-bp-060 — AMLSim 反洗钱模拟**
- 来源：IBM Research
- 架构模式：账户模拟 → 交易生成 → 洗钱模式注入（layering/structuring/fan-out）→ 告警标注
- 蓝图价值：唯一严肃建模洗钱交易网络拓扑的开源项目，4阶段数据管线设计清晰可提取
- 提取难度：中（Python+Java混合，聚焦Python部分）

**finance-bp-061 — OpenSanctions 制裁名单筛查**
- 来源：开源社区（703 stars，活跃维护）
- 架构模式：多源爬取 → 数据归一化 → 去重 → 实体链接 → API服务（yente匹配引擎）
- 蓝图价值：覆盖OFAC/UN/EU/UK等制裁名单，实体匹配架构是KYC系统核心组件
- 提取难度：低（纯Python，文档完善）

**finance-bp-062 — IFRS 9 预期信用损失**
- 来源：naenumtou/ifrs9（Jupyter Notebooks，~70 stars）
- 架构模式：PD建模(生存分析) → LGD建模 → EAD建模 → 三阶段分类(SICR判断) → ECL计算 → 宏观情景加权
- 蓝图价值：最完整的纯Python IFRS 9实现，Stage 1/2/3逻辑显式建模，各组件独立可提取
- 提取难度：低（Notebook格式，逻辑清晰）
- 复合蓝图候选：可结合 Daniel11OSSE/ifrs9-ecl-modeling（情景分析）和 open-risk/openLGD（LGD深度）

**finance-bp-063 — chainladder 精算准备金**
- 来源：Casualty Actuarial Society（CAS官方维护，~200 stars）
- 架构模式：损失发展三角形 → 尾部因子选择 → IBNR估计 → 不确定性量化（Mack/ODP）
- 蓝图价值：P&C精算准备金的权威Python库，API仿pandas/scikit-learn，是非寿险准备金的核心蓝图
- 提取难度：低（文档完善，CAS背书）

**finance-bp-064 — insurance_python Solvency II**
- 来源：Open Source Modelling（~100 stars）
- 架构模式：无风险利率曲线(Smith-Wilson外推) → 负债贴现 → SCR计算 → 自有资金 → 偿付比率
- 蓝图价值：唯一实现EIOPA强制的Smith-Wilson曲线外推方法的Python库，Solvency II监管架构完整可提取
- 提取难度：中（数学密集）

**finance-bp-065 — pyliferisk 寿险精算**
- 来源：franciscogarate（~119 stars）
- 架构模式：死亡率表 → 寿险精算符号 → 年金/保险精算计算 → 准备金
- 蓝图价值：寿险定价的独立蓝图，与P&C准备金（bp-063）形成互补
- 提取难度：低（纯Python无依赖）

**finance-bp-066 — wealthbot 智能投顾**
- 来源：wealthbot-io（~675 stars，Symfony/PHP但架构可提取）
- 架构模式：客户入职 → 风险测评 → 模型组合分配 → 自动再平衡（账户级+家庭级）→ Tax-Loss Harvesting → 绩效报告
- 蓝图价值：最完整的开源Robo-Advisor，多组件架构（RIA门户→客户入职→风险画像→模型分配→再平衡→报告）是财富管理工作流的参考蓝图
- 提取难度：中（PHP语言但REST API架构清晰，架构层面完全可提取）

**finance-bp-067 — firesale_stresstest 银行压力测试**
- 来源：Oxford INET（~50 stars，学术级）
- 架构模式：初始资产负债表 → 冲击传播 → 流动性螺旋 → 资本耗尽
- 蓝图价值：唯一使用真实EBA压力测试数据的Python项目，银行级资本压力测试架构可提取
- 提取难度：中（学术代码，需理解Cont-Schaanning 2017模型）
- 复合蓝图候选：可结合 Open_Source_Economic_Model（情景生成）

**finance-bp-068 — xalpha 公募基金管理**
- 来源：refraction-ray（~2,300 stars）
- 架构模式：基金NAV抓取 → 持仓管理 → 收益回测 → 定投策略模拟 → 可视化
- 蓝图价值：覆盖中国公募基金核心业务流，与"天天基金/蛋卷基金"功能对齐
- 提取难度：低（代码清晰，有pip包，文档完整）
- 注：bp-025 已有 xalpha 蓝图，此处需确认是否已充分覆盖或需升级

**finance-bp-069 — tqsdk 中国商品期货**
- 来源：天勤量化（~4,000 stars）
- 架构模式：行情订阅(三大交易所) → K线/Tick数据 → 策略信号 → 委托管理 → 实盘/回测
- 蓝图价值：中国商品期货量化的事实标准SDK，原生CTA策略支持，比vnpy更轻量聚焦
- 提取难度：中（需理解异步模型）

**finance-bp-070 — edgartools SEC文件解析**
- 来源：dgunning（~1,900 stars，very active）
- 架构模式：SEC EDGAR API → 文件下载 → HTML/XBRL解析 → 结构化Python对象 → 财务数据提取
- 蓝图价值：最完整的EDGAR开源工具，Filing→结构化对象（非原始HTML），已支持Claude MCP
- 提取难度：低（文档完善，Python原生）

#### P1 项目详细

**finance-bp-071 — frappe/lending 贷款管理**
- 贷款全生命周期：申请 → 审批 → 放款 → 还款计划 → 催收 → 结清
- 基于ERPNext的生产代码，NBFC和金融机构实际使用

**finance-bp-072 — formancehq/ledger 金融账本**
- 可编程双重记账账本：Numscript事务语言 → 原子记账引擎 → 不可变账本日志 → OLAP副本
- 支付、数字资产、贷款管理的基础设施层

**finance-bp-073 — FinRobot AI研报生成**
- Multi-Agent研报管线：数据Agent → 分析Agent → 写作Agent → 事实核查Agent → 格式化Agent
- Brain(LLM推理) + Perception(数据摄入) + Action(报告生成)三层架构

**finance-bp-074 — stock-screener NL选股**
- NL-to-filter管线：用户查询 → LLM意图提取 → 筛选参数映射 → 选股执行 → 结果排序
- 80+基本面/技术筛选条件，6个LLM提供商

**finance-bp-075 — ORE XVA引擎**
- XVA计算架构：交易表示 → 市场情景生成 → 暴露模拟 → 净额/抵押品 → XVA聚合
- 基于QuantLib的机构级实现，覆盖CVA/DVA/FVA/SIMM/SA-CCR

**finance-bp-076 — AbsBox MBS/ABS现金流**
- Waterfall建模：资产池现金流 → 顺序/比例分配 → 覆盖测试 → 触发器 → 分层还款
- 唯一有Python接口的开源ABS/MBS现金流引擎

**finance-bp-077 — Open_Source_Economic_Model 资产负债管理**
- ALM蓝图：资产负债表映射 → 缺口分析 → 利率情景生成 → NII/EVE敏感性 → 资本影响
- 经济情景生成器（ESG）是压力测试和ALM的关键基础设施

**finance-bp-078 — FinancePy FX衍生品**
- 注：bp-019已有FinancePy蓝图，此蓝图聚焦FX模块（FX期权/远期/XCS/Delta对冲）
- 企业FX对冲框架的核心，60+示例notebook，EDHEC教授维护

**finance-bp-079 — fava_investor 税损收割**
- TLH管线：持仓扫描 → 损失阈值判断 → Wash Sale Rule检测 → 替代证券匹配 → 收割建议
- 基于Beancount双重记账，算法逻辑清晰

**finance-bp-080 — akshare 北向资金模块**
- 注：聚焦akshare的北向资金+债券子模块（非整个akshare库）
- 北向资金实时/历史数据 + 中国债券信息网收益率曲线

**finance-bp-081 — FinDKG 金融知识图谱**
- 架构：~40万篇WSJ新闻 → LLM知识提取(ICKG) → 动态知识图谱 → 时序链接预测(KGTransformer)
- ACM ICAIF 2024发表，15种关系类型，12种实体类型

**finance-bp-082 — Economic-Dashboard 宏观仪表板**
- 60+经济指标实时接入（FRED/Yahoo Finance），多国对比分析，可视化Dashboard

**finance-bp-083 — eastmoney A股情绪平台**
- A股智能金融分析：基金分析+股票监控+商品追踪+市场情绪分析+LLM报告生成

**finance-bp-084 — vnpy CTA策略引擎**
- 注：聚焦 vnpy 的 cta_strategy 子模块
- CTA策略生命周期：信号生成 → 订单管理 → 风控 → 执行，CTP接口全品种

---

## 5. 补充后预期覆盖度 (Post-Expansion Coverage)

### 5.1 覆盖度变化矩阵

| # | 需求类别 | 当前评级 | 新增蓝图 | 预期评级 | 变化 |
|---|---------|---------|---------|---------|------|
| 1 | Opportunity Discovery | GOOD | bp-074(NL选股), bp-080(北向资金) | **EXCELLENT** | +2 |
| 2 | Analysis & Decision | GOOD | bp-073(FinRobot研报), bp-088(A股财报) | **EXCELLENT** | +2 |
| 3 | Quantitative Strategy | EXCELLENT | — | EXCELLENT | 0（已饱和） |
| 4 | Portfolio Construction | EXCELLENT | — | EXCELLENT | 0（已饱和） |
| 5 | Trade Execution | GOOD | bp-069(tqsdk), bp-084(vnpy CTA) | **EXCELLENT** | +2 |
| 6 | Monitoring & Management | ADEQUATE | bp-082(宏观Dashboard) | GOOD | +1 |
| 7 | Credit Risk | ADEQUATE | bp-062(IFRS 9), bp-085(openLGD) | **GOOD** | +2 |
| 8 | Market Risk | GOOD | bp-075(ORE XVA), bp-087(SA-CCR) | **EXCELLENT** | +2 |
| 9 | Regulatory & Compliance | **THIN** | bp-060(AML), bp-061(制裁), bp-067(压力测试), bp-087(SA-CCR) | **GOOD** | +4 |
| 10 | Wealth Management | **THIN** | bp-066(Robo-Advisor), bp-068(公募基金), bp-079(TLH) | **GOOD** | +3 |
| 11 | Insurance/Actuarial | **ABSENT** | bp-063(准备金), bp-064(Solvency II), bp-065(寿险) | **ADEQUATE** | +3 |
| 12 | Treasury/ALM | **THIN** | bp-077(ALM/ESG), bp-078(FX衍生品) | **ADEQUATE** | +2 |
| 13 | Fixed Income Deep | ADEQUATE | bp-076(MBS/ABS) | GOOD | +1 |
| 14 | Lending/Payments | **THIN** | bp-071(贷款), bp-072(账本) | **ADEQUATE** | +2 |
| 15 | Alternative Data | ADEQUATE | bp-070(SEC EDGAR), bp-083(A股情绪), bp-089(edgar-crawler) | **GOOD** | +3 |
| 16 | Macro & Multi-Asset | ADEQUATE | bp-082(经济Dashboard), bp-086(气候因子) | GOOD | +2 |
| 17 | AI/LLM Finance | GOOD | bp-073(FinRobot), bp-074(NL选股), bp-081(FinDKG) | **EXCELLENT** | +3 |
| 18 | Knowledge & Education | THIN | — | THIN | 0（产品哲学约束） |

### 5.2 关键指标

| 指标 | 当前（59蓝图） | 目标（89蓝图） |
|------|-------------|-------------|
| 总蓝图数 | 59 | **89**（+30） |
| ABSENT 类别数 | 1 | **0** |
| THIN 类别数 | 5 | **1**（仅Knowledge & Education，属有意不扩展） |
| ADEQUATE+ 类别占比 | 11/18 (61%) | **17/18 (94%)** |
| EXCELLENT 类别数 | 2 | **6** |
| 中国市场专项蓝图 | ~12 | **~18**（+6） |
| 美国市场专项蓝图 | ~5 | **~9**（+4） |

### 5.3 市场覆盖改善

| 市场 | 新增蓝图 | 关键填补 |
|------|---------|---------|
| China | bp-068(公募基金), bp-069(tqsdk), bp-080(北向资金), bp-083(A股情绪), bp-084(vnpy), bp-088(A股财报) | 公募基金、CTA期货、北向资金、情绪分析、财报分析 |
| US | bp-070(EDGAR), bp-079(TLH), bp-089(edgar-crawler) | SEC文件解析、税损收割 |
| EU | bp-064(Solvency II), bp-067(EBA压力测试) | 欧盟保险监管、银行压力测试 |
| Global | 其余 19 个 | 合规、风控、基础设施等通用能力 |

---

## 6. 执行建议 (Execution Notes)

### 6.1 提取顺序建议

**第一批（立即启动，预计 2-3 周）**：提取难度低 + P0优先级

| 序号 | Blueprint | 提取难度 | 理由 |
|------|----------|---------|------|
| 1 | bp-063 chainladder 精算准备金 | 低 | CAS官方维护，Python，文档完善，自包含 |
| 2 | bp-062 IFRS 9 ECL | 低 | Notebook格式，逻辑清晰，模块独立 |
| 3 | bp-070 edgartools SEC解析 | 低 | 文档完善，Python原生，2025活跃 |
| 4 | bp-068 xalpha 公募基金 | 低 | 代码清晰，有pip包（需确认与bp-025的关系） |
| 5 | bp-061 OpenSanctions 制裁筛查 | 低 | 纯Python，架构清晰 |

**第二批（第一批完成后，预计 2-3 周）**：P0剩余 + P1高价值

| 序号 | Blueprint | 提取难度 | 理由 |
|------|----------|---------|------|
| 6 | bp-073 FinRobot AI研报 | 中 | 高stars(4800)，Multi-Agent架构明确 |
| 7 | bp-069 tqsdk 期货CTA | 中 | 需理解异步模型，但中国期货标准 |
| 8 | bp-066 wealthbot Robo-Advisor | 中 | PHP但架构可提取，覆盖关键空白 |
| 9 | bp-071 frappe/lending 贷款 | 中 | 生产级代码，业务逻辑与框架分离 |
| 10 | bp-074 stock-screener NL选股 | 低 | NL-to-filter管线简洁 |

**第三批（中期，按需安排）**：P1剩余 + P2

| 序号 | Blueprint | 提取难度 | 理由 |
|------|----------|---------|------|
| 11-15 | bp-075(ORE), bp-076(AbsBox), bp-077(ESG ALM), bp-078(FX), bp-084(vnpy) | 中-高 | 数学密集或代码量大 |
| 16-25 | 其余P1 | 中 | 按业务需求排序 |
| 26-30 | P2全部 | 中 | 深化已有领域 |

### 6.2 复合蓝图建议（2-3个项目合并提取）

以下缺口无法由单一项目完整覆盖，建议合并多个项目提取为一个蓝图：

| 蓝图 | 组成项目 | 合并理由 |
|------|---------|---------|
| bp-062 IFRS 9 ECL | naenumtou/ifrs9（主） + Daniel11OSSE/ifrs9-ecl-modeling（情景分析） + open-risk/openLGD（LGD深度） | IFRS 9需要PD+LGD+EAD+Staging+情景全覆盖，单一项目不够完整 |
| bp-060 AMLSim | IBM/AMLSim（数据模拟） + opensanctions（数据层）— 注：checkmarble/marble(Go)仅作架构参考 | AML全栈需要模拟+筛查+监控三层 |
| bp-067 压力测试 | firesale_stresstest（传染模型） + Open_Source_Economic_Model（情景生成） | 压力测试需要情景生成+资本推演两层 |

### 6.3 已知挑战与替代方案

| 缺口领域 | 挑战 | 建议替代方案 |
|---------|------|------------|
| CCAR/DFAST（美国银行压测） | 无生产级OSS实现，银行倾向内部/商业方案 | 使用 bp-067 覆盖通用压力测试架构，CCAR规则作为约束条目补充 |
| US银行监管(Dodd-Frank) | OSS几乎空白 | 将CCAR/DFAST规则编入约束层，不做独立蓝图 |
| CTRM大宗商品全流程 | 实物交割+物流+合规+会计联动无OSS | 仅覆盖策略层（已有bp-069/084），实物层作为约束 |
| 自愿碳市场(VCM) | 几乎没有OSS实现 | bp-086聚焦EU ETS合规市场，暂不覆盖VCM |
| Options Flow（异常期权成交） | OSS质量普遍偏低（<50 stars） | 降为P2，结合FinancePy的Greeks模块编写约束 |
| 401k/IRA退休规划 | 最佳项目仅14 stars | 纳入bp-066 Robo-Advisor蓝图的退休子模块，不做独立蓝图 |
| 中国银行间债券 | 无独立OSS，akshare债券模块最佳 | 纳入bp-080 akshare蓝图的债券子模块 |

### 6.4 与现有蓝图的关系注意

| 新蓝图 | 可能重叠的现有蓝图 | 处理建议 |
|--------|-----------------|---------|
| bp-068 xalpha 公募基金 | bp-025 xalpha 中国基金管理 | **需确认**：bp-025若已覆盖完整，则不新增；若仅覆盖基础功能，bp-068可升级覆盖范围 |
| bp-078 FinancePy FX | bp-019 FinancePy | bp-078 聚焦FX子模块，通过 `relations: specializes` 关联 bp-019 |
| bp-084 vnpy CTA | bp-006 QUANTAXIS | 定位不同：vnpy偏CTP实盘+CTA策略引擎，QUANTAXIS偏全栈分布式，通过 `relations: alternative_to` 关联 |
| bp-073 FinRobot 研报 | bp-051 FinRobot AI Agent | **需确认**：bp-051已有FinRobot蓝图，bp-073应聚焦研报生成管线（specializes） |

---

*生成时间：2026-04-14*
*方法：用户需求分类体系 → 59蓝图覆盖度矩阵 → GitHub候选搜索（core + regional） → 优先级排序 → 路线图编译*
*输入文档：finance-user-need-taxonomy.md, finance-gap-analysis.md, finance-github-candidates-core.md, finance-github-candidates-regional.md*
