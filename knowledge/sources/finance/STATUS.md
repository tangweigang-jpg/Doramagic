# knowledge/sources/finance — 项目进展日志

> 最后更新：2026-04-18 08:20:49  
> 有效项目：**73**（Wave 1-3 48 项 + Wave 4 6 项 + Wave 5/6 19 项）  
> 已验收：**73**  ·  PASS **56**  ·  WARN **17**  ·  FAIL **0**

## 蓝图提取 + 验收状态表

| # | BP ID | 目录 | BDs | UCs | Stages | Verdict | 备注 |
|---|-------|------|-----|-----|--------|---------|------|
| 1 | `finance-bp-004` | `finance-bp-004--daily_stock_analysis` | 139 | — | 9 | ✅ PASS | BDs 健康，9 阶段，evidence 接地正常（N/A 占比 14%，采样 1/3） |
| 2 | `finance-bp-009` | `finance-bp-009--zvt` | 164 | — | 6 | ✅ PASS | BDs 丰富，6 阶段，evidence 接地正常（N/A 占比 14%，采样 1/3） |
| 3 | `finance-bp-020` | `finance-bp-020--gs-quant` | 96 | — | 10 | ✅ PASS | BDs 充足，10 阶段，evidence 接地正常（N/A 占比 18%，采样 1/3） |
| 4 | `finance-bp-050` | `finance-bp-050--skorecard` | 81 | — | 9 | ✅ PASS | v1 蓝图 BDs 81 条，evidence 全部有效，9 阶段，质量通过 |
| 5 | `finance-bp-060` | `finance-bp-060--AMLSim` | 101 | — | 12 | ✅ PASS | BDs 101 条，12 阶段，evidence 接地正常（N/A 占比 19%，采样 1/3） |
| 6 | `finance-bp-061` | `finance-bp-061--FinRL` | 138 | — | 10 | ✅ PASS | BDs 充足，10 阶段，evidence 接地正常（N/A 占比 14%，采样 1/3） |
| 7 | `placeholder` | `finance-bp-062--ifrs9` | 115 | — | 9 | ✅ PASS | placeholder bug 已修复（commit e41a30f） |
| 8 | `finance-bp-063` | `finance-bp-063--chainladder-python` | 118 | — | 11 | ✅ PASS | BDs 118 条，11 阶段，evidence 接地正常（N/A 占比 16%，采样 1/3） |
| 9 | `finance-bp-064` | `finance-bp-064--insurance_python` | 133 | — | 14 | ✅ PASS | BDs 健康(133条)，evidence 接地正常，各 stage 完整 |
| 10 | `finance-bp-065` | `finance-bp-065--pyliferisk` | 104 | — | 8 | ✅ PASS | BDs 健康(104条)，evidence 接地正常，mortality/commutation/premiu… |
| 11 | `finance-bp-066` | `finance-bp-066--wealthbot` | 106 | — | 5 | ⚠️ WARN | v10 重跑 blueprint.v2.yaml，106 BDs/5 stages，evidence 24% |
| 12 | `finance-bp-067` | `finance-bp-067--firesale_stresstest` | 120 | — | 10 | ✅ PASS | BDs 健康(120条)，evidence 接地正常，火售传染模型各阶段完整 |
| 13 | `finance-bp-068` | `finance-bp-068--xalpha` | 148 | — | 8 | ✅ PASS | BDs 丰富(148条)，evidence 接地正常，xalpha中国基金管理各阶段完整 |
| 14 | `finance-bp-069` | `finance-bp-069--tqsdk-python` | 146 | — | 12 | ✅ PASS | BDs 丰富(146条)，evidence 接地正常，天勤量化交易SDK各阶段完整 |
| 15 | `finance-bp-070` | `finance-bp-070--edgartools` | 111 | — | 9 | ✅ PASS | BDs 健康(111条)，evidence 接地正常，SEC EDGAR数据提取各阶段完整 |
| 16 | `finance-bp-071` | `finance-bp-071--opensanctions` | 120 | — | 11 | ✅ PASS | BDs 健康(120条)，evidence 接地正常，制裁名单聚合各阶段完整 |
| 17 | `finance-bp-072` | `finance-bp-072--lending` | 128 | — | 11 | ✅ PASS | BDs 健康(128条)，11个阶段，evidence接地正常，3样本仅末尾1条N/A |
| 18 | `finance-bp-073` | `finance-bp-073--ledger` | 99 | — | 10 | ✅ PASS | BDs 99条健康，10阶段，evidence样本2/3接地，整体通过 |
| 19 | `finance-bp-074` | `finance-bp-074--FinRobot` | 128 | — | 13 | ✅ PASS | BDs 128条，13阶段，evidence样本2/3有效，结构健全 |
| 20 | `finance-bp-076` | `finance-bp-076--AbsBox` | 119 | — | 8 | ✅ PASS | BDs 119条，8阶段，evidence样本2/3接地，内容正常 |
| 21 | `finance-bp-077` | `finance-bp-077--Open_Source_Economic_Model` | 112 | — | 12 | ✅ PASS | BDs 112条，12阶段，evidence样本2/3有效，OSEM蓝图通过 |
| 22 | `finance-bp-078` | `finance-bp-078--fava_investor` | 75 | — | 6 | ⚠️ WARN | BDs处于警告区间(75条)，evidence接地良好，6阶段正常 |
| 23 | `placeholder` | `finance-bp-079--akshare` | 123 | — | 10 | ✅ PASS | placeholder bug 已修复（commit e41a30f） |
| 24 | `finance-bp-080` | `finance-bp-080--FinDKG` | 87 | — | 10 | ✅ PASS | BDs 87条，10阶段，evidence样本2/3接地，结构健全 |
| 25 | `finance-bp-081` | `finance-bp-081--vnpy` | 114 | — | 12 | ✅ PASS | 114条BD，12个阶段，evidence全部非空，quality_gate通过，id匹配目录 |
| 26 | `finance-bp-082` | `finance-bp-082--stock-screener` | 139 | — | 12 | ✅ PASS | 139条BD，12个阶段，evidence全部非空，N/A仅用于INTERACTION型BD，quality_… |
| 27 | `finance-bp-083` | `finance-bp-083--Economic-Dashboard` | 122 | — | 12 | ✅ PASS | 122条BD，12个阶段，evidence全部非空，quality_gate通过，id匹配目录 |
| 28 | `finance-bp-084` | `finance-bp-084--eastmoney` | 156 | — | 12 | ✅ PASS | 156条BD，12个阶段，evidence全部非空，quality_gate通过（3版本历史），id匹配目录 |
| 29 | `finance-bp-085` | `finance-bp-085--freqtrade` | 173 | — | 8 | ✅ PASS | 173条BD，8个阶段，evidence全部非空，quality_gate通过，id匹配目录 |
| 30 | `finance-bp-086` | `finance-bp-086--backtrader` | 177 | — | 7 | ✅ PASS | 177条BD，7个阶段，evidence全部非空，quality_gate通过，id匹配目录 |
| 31 | `finance-bp-087` | `finance-bp-087--qlib` | 168 | — | 11 | ✅ PASS | 168条BD，11个阶段，evidence全部非空，quality_gate通过，id匹配目录 |
| 32 | `finance-bp-088` | `finance-bp-088--zipline-reloaded` | 120 | — | 8 | ✅ PASS | 120条BD，8个阶段，evidence全部非空，quality_gate通过，id匹配目录 |
| 33 | `finance-bp-089` | `finance-bp-089--rqalpha` | 165 | — | 6 | ✅ PASS | BDs 165条，stages 6个，evidence 接地正常，quality_gate 通过 |
| 34 | `finance-bp-090` | `finance-bp-090--QUANTAXIS` | 114 | — | 7 | ✅ PASS | BDs 114条，stages 7个，evidence 接地正常，quality_gate 通过 |
| 35 | `finance-bp-091` | `finance-bp-091--czsc` | 157 | — | 6 | ✅ PASS | BDs 157条，stages 6个，evidence 接地正常，quality_gate 通过 |
| 36 | `finance-bp-092` | `finance-bp-092--vectorbt` | 139 | — | 7 | ✅ PASS | BDs 139条，stages 7个，evidence 接地正常，quality_gate 通过 |
| 37 | `finance-bp-093` | `finance-bp-093--PyPortfolioOpt` | 123 | — | 7 | ✅ PASS | BDs 123条，stages 7个，evidence 接地正常，quality_gate 通过 |
| 38 | `finance-bp-094` | `finance-bp-094--easytrader` | 144 | — | 5 | ✅ PASS | BDs 144条，stages 5个，evidence 接地正常，quality_gate 通过 |
| 39 | `finance-bp-095` | `finance-bp-095--rotki` | 164 | — | 8 | ✅ PASS | BDs 164条，stages 8个，evidence 接地正常，quality_gate 通过 |
| 40 | `finance-bp-096` | `finance-bp-096--hummingbot` | 144 | — | 8 | ✅ PASS | BDs 144条，stages 8个，evidence 接地正常，quality_gate 通过 |
| 41 | `finance-bp-097` | `finance-bp-097--OpenBB` | 160 | — | 7 | ✅ PASS | BDs健康，evidence接地正常，7个阶段结构完整 |
| 42 | `finance-bp-098` | `finance-bp-098--nautilus_trader` | 130 | — | 8 | ✅ PASS | BDs健康，evidence接地正常，8个阶段结构完整 |
| 43 | `finance-bp-099` | `finance-bp-099--TradingAgents-CN` | 141 | — | 9 | ✅ PASS | BDs健康，evidence接地正常，9个阶段结构完整 |
| 44 | `finance-bp-100` | `finance-bp-100--LEAN` | 139 | — | 7 | ✅ PASS | BDs健康，evidence接地正常，7个阶段结构完整 |
| 45 | `finance-bp-101` | `finance-bp-101--FinancePy` | 121 | — | 8 | ✅ PASS | BDs健康，evidence接地正常，8个阶段结构完整 |
| 46 | `placeholder` | `finance-bp-102--Darts` | 189 | — | 15 | ✅ PASS | placeholder bug 已修复（commit e41a30f） |
| 47 | `finance-bp-103` | `finance-bp-103--ArcticDB` | 153 | — | 9 | ✅ PASS | BDs健康，evidence接地正常，9个阶段结构完整 |
| 48 | `finance-bp-104` | `finance-bp-104--Engine` | 78 | — | 7 | ⚠️ WARN | BDs数量偏少（78条），处于WARN区间，其余指标正常 |
| 49 | `finance-bp-105` | `finance-bp-105--open-climate-investing` | 116 | 9 | 7 | ✅ PASS | ESG/碳因子蓝图首次覆盖，BD 116条健康，evidence接地良好，quality_gate全通过 |
| 50 | `finance-bp-106` | `finance-bp-106--pyfolio-reloaded` | 138 | 7 | 8 | ✅ PASS | 绩效归因子域，BD 138条丰富，evidence覆盖广泛，quality_gate全通过 |
| 51 | `finance-bp-107` | `finance-bp-107--empyrical-reloaded` | 111 | 3 | 6 | ⚠️ WARN | BD健康，evidence字段有值但验证失败率高；UC全为文档类 |
| 52 | `finance-bp-108` | `finance-bp-108--finmarketpy` | 77 | 4 | 6 | ⚠️ WARN | 宏观多资产/FX回测子域，BD数量偏低但达标，evidence接地正常 |
| 53 | `finance-bp-109` | `finance-bp-109--ta-lib-python` | 104 | 1 | 6 | ⚠️ WARN | BD充足但近半数无代码证据，evidence 质量偏低 |
| 54 | `finance-bp-110` | `finance-bp-110--cryptofeed` | 98 | 40 | 8 | ✅ PASS | 加密行情聚合子域，UC 40条异常充沛，BD 98条健康，evidence接地正常 |
| 55 | `finance-bp-111` | `finance-bp-111--ccxt` | 137 | 100 | 6 | ✅ PASS | BD/UC均健康，evidence接地正常，覆盖率0.877，最大项目表现优异 |
| 56 | `finance-bp-112` | `finance-bp-112--openLGD` | 91 | 1 | 5 | ⚠️ WARN | BD充足，但UC完全缺失真实信用风险场景 |
| 57 | `finance-bp-114` | `finance-bp-114--edgar-crawler` | 92 | 1 | 4 | ⚠️ WARN | BD达标，evidence有值但失效率较高 |
| 58 | `finance-bp-115` | `finance-bp-115--mlfinlab` | 124 | 1 | 12 | ⚠️ WARN | 金融ML子域（AFML方法论），BD 124条/stages 12条充沛但UC严重不足 |
| 59 | `finance-bp-116` | `finance-bp-116--FinRL-Meta` | 171 | 9 | 6 | ✅ PASS | 重跑 blueprint.v2.yaml：BDs 43→171，stages 8→6，蓝图验证 8 PASS/… |
| 60 | `finance-bp-117` | `finance-bp-117--Riskfolio-Lib` | 162 | 0 | 7 | ⚠️ WARN | 风险平价子域，BD 162条为本批最丰富，但UC未按标准格式提取 |
| 61 | `finance-bp-118` | `finance-bp-118--FinanceToolkit` | 175 | 13 | 10 | ⚠️ WARN | BD/UC数量优秀，但超半数evidence引用失效（FN_NOT_FOUND） |
| 62 | `finance-bp-119` | `finance-bp-119--transitionMatrix` | 134 | 22 | 6 | ⚠️ WARN | BD/UC数量良好，但绝大多数evidence引用验证失败 |
| 63 | `finance-bp-120` | `finance-bp-120--alphalens-reloaded` | 127 | 6 | 4 | ✅ PASS | BD充足，evidence覆盖0.88，UC含真实因子研究场景，整体健康 |
| 64 | `finance-bp-121` | `finance-bp-121--machine-learning-for-trading` | 142 | 0 | 7 | ⚠️ WARN | BD数量优秀，evidence接地率0.917，但UC完全缺失 |
| 65 | `finance-bp-122` | `finance-bp-122--ta-python` | 129 | 2 | 5 | ⚠️ WARN | BDs健康(129条)，evidence接地正常，UC数量异常偏低 |
| 66 | `finance-bp-123` | `finance-bp-123--QuantLib-SWIG` | 137 | 35 | 5 | ✅ PASS | BDs健康(137条)，evidence接地正常，UC丰富(35条) |
| 67 | `finance-bp-124` | `finance-bp-124--arch` | 100 | 9 | 7 | ✅ PASS | BDs健康(100条)，evidence接地正常，各项指标达标 |
| 68 | `finance-bp-125` | `finance-bp-125--bt` | 102 | 20 | 6 | ✅ PASS | BDs健康(102条)，evidence接地正常，UC充足(20条) |
| 69 | `finance-bp-126` | `finance-bp-126--lifelines` | 131 | 19 | 6 | ✅ PASS | 重跑 blueprint.v2.yaml：stages 0→6，BDs 57→131，蓝图验证 8 PASS/… |
| 70 | `finance-bp-127` | `finance-bp-127--py_vollib` | 116 | 1 | 5 | ⚠️ WARN | BDs健康(116条)，evidence接地正常，UC数量异常(仅1条) |
| 71 | `finance-bp-128` | `finance-bp-128--yfinance` | 58 | 12 | 9 | ⚠️ WARN | BDs偏低(58条)但超过50条门槛，其余指标正常 |
| 72 | `finance-bp-129` | `finance-bp-129--beancount` | 116 | 2 | 6 | ⚠️ WARN | BDs健康(116条)，evidence接地正常，UC数量异常偏低 |
| 73 | `finance-bp-130` | `finance-bp-130--tensortrade` | 133 | 19 | 5 | ✅ PASS | BDs健康(133条)，evidence接地正常，UC充足(19条) |

## 本轮（Wave 5+6）亮点

- **ccxt（bp-111，1334 py 文件最大项目）**：UC 100 条、BDs 137、PASS ✅
- **QuantLib-SWIG（bp-123）**：UC 35 条、BDs 137、衍生品/固收黄金标准 PASS ✅
- **tensortrade（bp-130）**：UC 19 条、BDs 133、RL 三件套完整 PASS ✅
- **bp-116 FinRL-Meta**：rate-limit 批次导致首轮 BDs 仅 43，重跑后 BDs 171 ✨
- **bp-126 lifelines**：首轮 assemble 损坏 stages=0，重跑后 stages 6 + BDs 131 ✨

## 不合格项目

### ❌ FAIL

_无_ 🎉

### ⚠️ WARN

- **finance-bp-066--wealthbot** — v10 重跑 blueprint.v2.yaml，106 BDs/5 stages，evidence 24%
- **finance-bp-078--fava_investor** — BDs处于警告区间(75条)，evidence接地良好，6阶段正常
- **finance-bp-104--Engine** — BDs数量偏少（78条），处于WARN区间，其余指标正常
- **finance-bp-107--empyrical-reloaded** — BD健康，evidence字段有值但验证失败率高；UC全为文档类
- **finance-bp-108--finmarketpy** — 宏观多资产/FX回测子域，BD数量偏低但达标，evidence接地正常
- **finance-bp-109--ta-lib-python** — BD充足但近半数无代码证据，evidence 质量偏低
- **finance-bp-112--openLGD** — BD充足，但UC完全缺失真实信用风险场景
- **finance-bp-114--edgar-crawler** — BD达标，evidence有值但失效率较高
- **finance-bp-115--mlfinlab** — 金融ML子域（AFML方法论），BD 124条/stages 12条充沛但UC严重不足
- **finance-bp-117--Riskfolio-Lib** — 风险平价子域，BD 162条为本批最丰富，但UC未按标准格式提取
- **finance-bp-118--FinanceToolkit** — BD/UC数量优秀，但超半数evidence引用失效（FN_NOT_FOUND）
- **finance-bp-119--transitionMatrix** — BD/UC数量良好，但绝大多数evidence引用验证失败
- **finance-bp-121--machine-learning-for-trading** — BD数量优秀，evidence接地率0.917，但UC完全缺失
- **finance-bp-122--ta-python** — BDs健康(129条)，evidence接地正常，UC数量异常偏低
- **finance-bp-127--py_vollib** — BDs健康(116条)，evidence接地正常，UC数量异常(仅1条)
- **finance-bp-128--yfinance** — BDs偏低(58条)但超过50条门槛，其余指标正常
- **finance-bp-129--beancount** — BDs健康(116条)，evidence接地正常，UC数量异常偏低

## 事件日志

- **2026-04-18 08:50** — evidence verifier 两处修复后重跑 bp-118/bp-119（commit 900af46）；bp-119 invalid 83.6%→0.8%（verifier fix），bp-118 57.7%→18.9%（basename fallback + LLM 重跑）
- **2026-04-18 08:20** — Wave 5+6 验收 + 2 项重跑完成：**56 PASS / 17 WARN / 0 FAIL**
- 2026-04-18 08:19 — bp-116 FinRL-Meta 重跑完成（BDs 43→171，PASS）
- 2026-04-18 08:14 — bp-126 lifelines 重跑完成（stages 0→6，PASS）
- 2026-04-18 06:51 — Wave 5+6 批次完成（19 项，7h21min，含 MiniMax 限流期 glm-5 failover）
- 2026-04-17 23:29 — Wave 5+6 合并批次启动（含 ccxt 1334 文件压轴）
- 2026-04-17 23:20 — bp-115 mlfinlab UC=1 判为 upstream 限制
- 2026-04-17 23:03 — Wave 4 批次完成（6 项）
- 2026-04-17 20:20 — bp-062/079/102 placeholder bug 修复
- 2026-04-17 19:48 — bp-068 xalpha 补提取
- 2026-04-17 19:07 — v10 wave3 resume 批次完成
