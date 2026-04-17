# knowledge/sources/finance — 项目进展日志

> 最后更新：2026-04-17 23:09:57  
> 有效项目：**54**（Wave 1-3 原 48 项 + Wave 4 新增 6 项）  
> 已验收：**54**  ·  PASS **48**  ·  WARN **6**  ·  FAIL **0**

## 蓝图提取 + 验收状态表

| # | BP ID | 目录 | BDs | UCs | Stages | SOP | Agent | QG | Extracted | Verdict | 备注 |
|---|-------|------|-----|-----|--------|-----|-------|----|-----------|---------|------|
| 1 | `finance-bp-004` | `finance-bp-004--daily_stock_analysis` | 139 | — | 9 | 3.6 | v6 | ✅ | 2026-04-16 | ✅ PASS | BDs 健康，9 阶段，evidence 接地正常（N/A 占比 14%，采样 1/3） |
| 2 | `finance-bp-009` | `finance-bp-009--zvt` | 164 | — | 6 | — | — | — |  | ✅ PASS | BDs 丰富，6 阶段，evidence 接地正常（N/A 占比 14%，采样 1/3） |
| 3 | `finance-bp-020` | `finance-bp-020--gs-quant` | 96 | — | 10 | 3.6 | v6 | ✅ | 2026-04-16 | ✅ PASS | BDs 充足，10 阶段，evidence 接地正常（N/A 占比 18%，采样 1/3） |
| 4 | `finance-bp-050` | `finance-bp-050--skorecard` | 81 | — | 9 | 3.2 | v5.2 | — | 2026-04-11 | ✅ PASS | v1 蓝图 BDs 81 条，evidence 全部有效，9 阶段，质量通过 |
| 5 | `finance-bp-060` | `finance-bp-060--AMLSim` | 101 | — | 12 | 3.4 | v6 | ✅ | 2026-04-14 | ✅ PASS | BDs 101 条，12 阶段，evidence 接地正常（N/A 占比 19%，采样 1/3） |
| 6 | `finance-bp-061` | `finance-bp-061--FinRL` | 138 | — | 10 | 3.6 | v6 | ✅ | 2026-04-14 | ✅ PASS | BDs 充足，10 阶段，evidence 接地正常（N/A 占比 14%，采样 1/3） |
| 7 | `finance-bp-062` | `finance-bp-062--ifrs9` | 115 | — | 9 | 3.6 | v6 | ✅ | 2026-04-14 | ✅ PASS | placeholder bug 已修复：从 assemble_raw.txt 恢复 id/name/… |
| 8 | `finance-bp-063` | `finance-bp-063--chainladder-python` | 118 | — | 11 | 3.6 | v6 | ✅ | 2026-04-14 | ✅ PASS | BDs 118 条，11 阶段，evidence 接地正常（N/A 占比 16%，采样 1/3） |
| 9 | `finance-bp-064` | `finance-bp-064--insurance_python` | 133 | — | 14 | 3.6 | v6 | ✅ | 2026-04-14 | ✅ PASS | BDs 健康(133条)，evidence 接地正常，各 stage 完整 |
| 10 | `finance-bp-065` | `finance-bp-065--pyliferisk` | 104 | — | 8 | 3.6 | v6 | ✅ | 2026-04-14 | ✅ PASS | BDs 健康(104条)，evidence 接地正常，mortality/commutation/p… |
| 11 | `finance-bp-066` | `finance-bp-066--wealthbot` | 106 | — | 5 | 3.6 | v6 | ✅ | 2026-04-14 | ⚠️ WARN | v10 重跑完成（blueprint.v2.yaml，106 BDs/5 stages），evide… |
| 12 | `finance-bp-067` | `finance-bp-067--firesale_stresstest` | 120 | — | 10 | 3.6 | v6 | ✅ | 2026-04-14 | ✅ PASS | BDs 健康(120条)，evidence 接地正常，火售传染模型各阶段完整 |
| 13 | `finance-bp-068` | `finance-bp-068--xalpha` | 148 | — | 8 | 3.6 | v6 | ✅ | 2026-04-17 | ✅ PASS | BDs 丰富(148条)，evidence 接地正常，xalpha中国基金管理各阶段完整 |
| 14 | `finance-bp-069` | `finance-bp-069--tqsdk-python` | 146 | — | 12 | 3.6 | v6 | ✅ | 2026-04-14 | ✅ PASS | BDs 丰富(146条)，evidence 接地正常，天勤量化交易SDK各阶段完整 |
| 15 | `finance-bp-070` | `finance-bp-070--edgartools` | 111 | — | 9 | 3.6 | v6 | ✅ | 2026-04-15 | ✅ PASS | BDs 健康(111条)，evidence 接地正常，SEC EDGAR数据提取各阶段完整 |
| 16 | `finance-bp-071` | `finance-bp-071--opensanctions` | 120 | — | 11 | 3.6 | v6 | ✅ | 2026-04-14 | ✅ PASS | BDs 健康(120条)，evidence 接地正常，制裁名单聚合各阶段完整 |
| 17 | `finance-bp-072` | `finance-bp-072--lending` | 128 | — | 11 | 3.6 | v6 | ✅ | 2026-04-15 | ✅ PASS | BDs 健康(128条)，11个阶段，evidence接地正常，3样本仅末尾1条N/A |
| 18 | `finance-bp-073` | `finance-bp-073--ledger` | 99 | — | 10 | 3.6 | v6 | ✅ | 2026-04-15 | ✅ PASS | BDs 99条健康，10阶段，evidence样本2/3接地，整体通过 |
| 19 | `finance-bp-074` | `finance-bp-074--FinRobot` | 128 | — | 13 | 3.6 | v6 | ✅ | 2026-04-15 | ✅ PASS | BDs 128条，13阶段，evidence样本2/3有效，结构健全 |
| 20 | `finance-bp-076` | `finance-bp-076--AbsBox` | 119 | — | 8 | 3.6 | v6 | ✅ | 2026-04-15 | ✅ PASS | BDs 119条，8阶段，evidence样本2/3接地，内容正常 |
| 21 | `finance-bp-077` | `finance-bp-077--Open_Source_Economic_Model` | 112 | — | 12 | 3.6 | v6 | ✅ | 2026-04-15 | ✅ PASS | BDs 112条，12阶段，evidence样本2/3有效，OSEM蓝图通过 |
| 22 | `finance-bp-078` | `finance-bp-078--fava_investor` | 75 | — | 6 | 3.6 | v6 | ✅ | 2026-04-15 | ⚠️ WARN | BDs处于警告区间(75条)，evidence接地良好，6阶段正常 |
| 23 | `finance-bp-079` | `finance-bp-079--akshare` | 123 | — | 10 | 3.6 | v6 | ❌ | 2026-04-15 | ✅ PASS | placeholder bug 已修复：从 assemble_raw.txt 恢复 id/name/… |
| 24 | `finance-bp-080` | `finance-bp-080--FinDKG` | 87 | — | 10 | 3.6 | v6 | ✅ | 2026-04-15 | ✅ PASS | BDs 87条，10阶段，evidence样本2/3接地，结构健全 |
| 25 | `finance-bp-081` | `finance-bp-081--vnpy` | 114 | — | 12 | 3.6 | v6 | ✅ | 2026-04-15 | ✅ PASS | 114条BD，12个阶段，evidence全部非空，quality_gate通过，id匹配目录 |
| 26 | `finance-bp-082` | `finance-bp-082--stock-screener` | 139 | — | 12 | 3.6 | v6 | ✅ | 2026-04-15 | ✅ PASS | 139条BD，12个阶段，evidence全部非空，N/A仅用于INTERACTION型BD，qua… |
| 27 | `finance-bp-083` | `finance-bp-083--Economic-Dashboard` | 122 | — | 12 | 3.6 | v6 | ✅ | 2026-04-15 | ✅ PASS | 122条BD，12个阶段，evidence全部非空，quality_gate通过，id匹配目录 |
| 28 | `finance-bp-084` | `finance-bp-084--eastmoney` | 156 | — | 12 | 3.6 | v6 | ✅ | 2026-04-15 | ✅ PASS | 156条BD，12个阶段，evidence全部非空，quality_gate通过（3版本历史），id… |
| 29 | `finance-bp-085` | `finance-bp-085--freqtrade` | 173 | — | 8 | 3.6 | v6 | ✅ | 2026-04-17 | ✅ PASS | 173条BD，8个阶段，evidence全部非空，quality_gate通过，id匹配目录 |
| 30 | `finance-bp-086` | `finance-bp-086--backtrader` | 177 | — | 7 | 3.6 | v6 | ✅ | 2026-04-16 | ✅ PASS | 177条BD，7个阶段，evidence全部非空，quality_gate通过，id匹配目录 |
| 31 | `finance-bp-087` | `finance-bp-087--qlib` | 168 | — | 11 | 3.6 | v6 | ✅ | 2026-04-16 | ✅ PASS | 168条BD，11个阶段，evidence全部非空，quality_gate通过，id匹配目录 |
| 32 | `finance-bp-088` | `finance-bp-088--zipline-reloaded` | 120 | — | 8 | 3.6 | v6 | ✅ | 2026-04-16 | ✅ PASS | 120条BD，8个阶段，evidence全部非空，quality_gate通过，id匹配目录 |
| 33 | `finance-bp-089` | `finance-bp-089--rqalpha` | 165 | — | 6 | 3.6 | v6 | ✅ | 2026-04-16 | ✅ PASS | BDs 165条，stages 6个，evidence 接地正常，quality_gate 通过 |
| 34 | `finance-bp-090` | `finance-bp-090--QUANTAXIS` | 114 | — | 7 | 3.6 | v6 | ✅ | 2026-04-16 | ✅ PASS | BDs 114条，stages 7个，evidence 接地正常，quality_gate 通过 |
| 35 | `finance-bp-091` | `finance-bp-091--czsc` | 157 | — | 6 | 3.6 | v6 | ✅ | 2026-04-16 | ✅ PASS | BDs 157条，stages 6个，evidence 接地正常，quality_gate 通过 |
| 36 | `finance-bp-092` | `finance-bp-092--vectorbt` | 139 | — | 7 | 3.6 | v6 | ✅ | 2026-04-16 | ✅ PASS | BDs 139条，stages 7个，evidence 接地正常，quality_gate 通过 |
| 37 | `finance-bp-093` | `finance-bp-093--PyPortfolioOpt` | 123 | — | 7 | 3.6 | v6 | ✅ | 2026-04-16 | ✅ PASS | BDs 123条，stages 7个，evidence 接地正常，quality_gate 通过 |
| 38 | `finance-bp-094` | `finance-bp-094--easytrader` | 144 | — | 5 | 3.6 | v6 | ✅ | 2026-04-17 | ✅ PASS | BDs 144条，stages 5个，evidence 接地正常，quality_gate 通过 |
| 39 | `finance-bp-095` | `finance-bp-095--rotki` | 164 | — | 8 | 3.6 | v6 | ✅ | 2026-04-17 | ✅ PASS | BDs 164条，stages 8个，evidence 接地正常，quality_gate 通过 |
| 40 | `finance-bp-096` | `finance-bp-096--hummingbot` | 144 | — | 8 | 3.6 | v6 | ✅ | 2026-04-17 | ✅ PASS | BDs 144条，stages 8个，evidence 接地正常，quality_gate 通过 |
| 41 | `finance-bp-097` | `finance-bp-097--OpenBB` | 160 | — | 7 | 3.6 | v6 | ✅ | 2026-04-17 | ✅ PASS | BDs健康，evidence接地正常，7个阶段结构完整 |
| 42 | `finance-bp-098` | `finance-bp-098--nautilus_trader` | 130 | — | 8 | 3.6 | v6 | ✅ | 2026-04-17 | ✅ PASS | BDs健康，evidence接地正常，8个阶段结构完整 |
| 43 | `finance-bp-099` | `finance-bp-099--TradingAgents-CN` | 141 | — | 9 | 3.6 | v6 | ✅ | 2026-04-17 | ✅ PASS | BDs健康，evidence接地正常，9个阶段结构完整 |
| 44 | `finance-bp-100` | `finance-bp-100--LEAN` | 139 | — | 7 | 3.6 | v6 | ✅ | 2026-04-17 | ✅ PASS | BDs健康，evidence接地正常，7个阶段结构完整 |
| 45 | `finance-bp-101` | `finance-bp-101--FinancePy` | 121 | — | 8 | 3.6 | v6 | ✅ | 2026-04-17 | ✅ PASS | BDs健康，evidence接地正常，8个阶段结构完整 |
| 46 | `finance-bp-102` | `finance-bp-102--Darts` | 189 | — | 15 | 3.6 | v6 | ❌ | 2026-04-17 | ✅ PASS | placeholder bug 已修复：从截断 JSON 恢复 id/name/15 stages，… |
| 47 | `finance-bp-103` | `finance-bp-103--ArcticDB` | 153 | — | 9 | 3.6 | v6 | ✅ | 2026-04-17 | ✅ PASS | BDs健康，evidence接地正常，9个阶段结构完整 |
| 48 | `finance-bp-104` | `finance-bp-104--Engine` | 78 | — | 7 | 3.6 | v6 | ✅ | 2026-04-17 | ⚠️ WARN | BDs数量偏少（78条），处于WARN区间，其余指标正常 |
| 49 | `finance-bp-105` | `finance-bp-105--open-climate-investing` | 116 | 9 | 7 | 3.6 | v10 | ✅ | 2026-04-17 | ✅ PASS | ESG/碳因子蓝图首次覆盖，BD 116条健康，evidence接地良好，quality_gate全… |
| 50 | `finance-bp-106` | `finance-bp-106--pyfolio-reloaded` | 138 | 7 | 8 | 3.6 | v10 | ✅ | 2026-04-17 | ✅ PASS | 绩效归因子域，BD 138条丰富，evidence覆盖广泛，quality_gate全通过 |
| 51 | `finance-bp-108` | `finance-bp-108--finmarketpy` | 77 | 4 | 6 | 3.6 | v10 | ✅ | 2026-04-17 | ⚠️ WARN | 宏观多资产/FX回测子域，BD数量偏低但达标，evidence接地正常 |
| 52 | `finance-bp-110` | `finance-bp-110--cryptofeed` | 98 | 40 | 8 | 3.6 | v10 | ✅ | 2026-04-17 | ✅ PASS | 加密行情聚合子域，UC 40条异常充沛，BD 98条健康，evidence接地正常 |
| 53 | `finance-bp-115` | `finance-bp-115--mlfinlab` | 124 | 1 | 12 | 3.6 | v10 | ✅ | 2026-04-17 | ⚠️ WARN | 金融ML子域（AFML方法论），BD 124条/stages 12条充沛但UC严重不足 |
| 54 | `finance-bp-117` | `finance-bp-117--Riskfolio-Lib` | 162 | 0 | 7 | 3.6 | v10 | ✅ | 2026-04-17 | ⚠️ WARN | 风险平价子域，BD 162条为本批最丰富，但UC未按标准格式提取 |

## 不合格项目

### ❌ FAIL（需重跑）

_无_ 🎉

### ⚠️ WARN（可用但有瑕疵）

- **finance-bp-066--wealthbot** — v10 重跑完成（blueprint.v2.yaml，106 BDs/5 stages），evidence 从 7% → 24%，仍偏弱
- **finance-bp-078--fava_investor** — BDs处于警告区间(75条)，evidence接地良好，6阶段正常
- **finance-bp-104--Engine** — BDs数量偏少（78条），处于WARN区间，其余指标正常
- **finance-bp-108--finmarketpy** — 宏观多资产/FX回测子域，BD数量偏低但达标，evidence接地正常
- **finance-bp-115--mlfinlab** — 金融ML子域（AFML方法论），BD 124条/stages 12条充沛但UC严重不足
- **finance-bp-117--Riskfolio-Lib** — 风险平价子域，BD 162条为本批最丰富，但UC未按标准格式提取

## Wave 4 子域覆盖成果

- **ESG/碳因子**（ABSENT → ADEQUATE）：bp-105 open-climate-investing
- **绩效归因**（ABSENT → ADEQUATE）：bp-106 pyfolio-reloaded
- **宏观多资产/FX**（THIN → ADEQUATE）：bp-108 finmarketpy
- **加密行情**（THIN → GOOD）：bp-110 cryptofeed（UC 40 条异常充沛）
- **金融 ML**（THIN → ADEQUATE）：bp-115 mlfinlab
- **风险平价**（THIN → ADEQUATE）：bp-117 Riskfolio-Lib（BD 162 条本批最多）

## 已知异常（结构层面）

- **`finance-bp-009--zvt/`** — 使用 v3~v17 老命名（无 `blueprint.v1.yaml`），验收时读 `blueprint.v17.yaml`
- **`finance-bp-066--wealthbot/`** — PHP 项目，v10 重跑后 evidence 接地率仍偏弱（agent indexer 主要面向 Python）
- **`finance-bp-115--mlfinlab/`** — UC=1 是 **upstream 限制**：mlfinlab 已转商业化，GitHub 只留 public-facing 空壳 repo（README 明确说明仅用于提 issue），无 examples/notebooks/ipynb/tests；UC discovery patterns 已覆盖标准目录，但 repo 本身无可提取内容；蓝图主体（124 BDs / 12 stages）质量良好，保留 WARN 状态

## bp_assemble placeholder bug 修复记录

**Bug**：v10 agent `bp_assemble` 阶段在 L2 JSON 残缺/L3 fallback 失败时写入 placeholder。

**本次修复**：
- 数据侧：bp-062/079/102 从 `assemble_raw.txt` 恢复（commit e41a30f）
- 代码侧：`blueprint_phases.py`（L3 三层降级 + 截断 JSON 抽取器）+ `executor.py`（placeholder 嵌入真实 id + _assemble_failed 标记）

## 事件日志

- **2026-04-17 23:20** — bp-115 mlfinlab UC 调查：确认 repo 是商业化后的 public-facing 空壳，UC=1 为 upstream 限制而非 agent 缺陷，接受 WARN 状态
- **2026-04-17 23:09** — Wave 4 验收完成：**3 PASS / 3 WARN**（bp-105/106/110 PASS，bp-108/115/117 WARN）
- 2026-04-17 23:03 — Wave 4 批次完成（6 项全 WARN 以上，0 FAIL，2h25min）
- 2026-04-17 20:38 — Wave 4 批次启动（open-climate-investing / pyfolio-reloaded / finmarketpy / cryptofeed / mlfinlab / Riskfolio-Lib）
- 2026-04-17 20:25 — bp-066 wealthbot v10 重跑完成（evidence 7%→24%，仍 WARN）
- 2026-04-17 20:20 — bp-062/079/102 placeholder bug 修复
- 2026-04-17 20:10 — 全量蓝图验收完成（6 sonnet 子代理并行）：42 PASS / 2 WARN / 4 FAIL
- 2026-04-17 19:48 — `finance-bp-068 xalpha` 首次提取完成（148 BDs）
- 2026-04-17 19:07 — v10 wave3 resume 批次完成（bp-097~104）
- 2026-04-17 15:07 — wave3 resume 启动（停电中断恢复）
