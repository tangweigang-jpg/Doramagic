# Finance 子领域必审清单研究

日期: 2026-04-07
研究方法: 4 个 Sonnet 子代理并行研究，基于 repos/ 中 59 个实际仓库的源码分析
目的: 为 SOP v3.0 的子领域必审清单提供研究基础

## 研究范围

| 子代理 | 研究子领域 | 产出条目数 |
|--------|-----------|-----------|
| #1 | 交易与执行 + 定价与估值 | 12 + 12 = 24 |
| #2 | 风险与配置 + 信用与银行 | 12 + 10 = 22 |
| #3 | 合规与ESG + 数据基础设施 + AI/LLM金融 | 8 + 8 + 8 = 24 |
| #4 | 横切关注点（8 大类） | 20 |
| **总计** | | **90 条** |

## 59 个蓝图的子领域分类

| 子领域 | 代码 | 数量 | 占比 | 代表项目 |
|--------|------|------|------|---------|
| 量化交易与回测 | TRD | 14 | 24% | freqtrade, zipline, vnpy, vectorbt, backtrader |
| AI/LLM金融 | AIL | 6 | 10% | FinRL, FinGPT, TradingAgents, Darts |
| 散户投资与基金 | TRD | 6 | 10% | easytrader, xalpha, bondTrader, Ghostfolio |
| 执行/HFT/微结构 | TRD | 6 | 10% | nautilus_trader, hftbacktest, hummingbot |
| 衍生品定价 | PRC | 5 | 8.5% | QuantLib, FinancePy, gs-quant, py_vollib |
| 绩效归因 | RSK | 4 | 7% | quantstats, pyfolio, empyrical, alphalens |
| 组合优化 | RSK | 4 | 7% | PyPortfolioOpt, Riskfolio-Lib, skfolio, cvxportfolio |
| 信用风险/银行 | CRD | 3 | 5% | skorecard, openNPL, portfolioAnalytics |
| ESG/合规 | CMP | 3 | 5% | rotki, ESG_AI, Equinox |
| 风险建模 | RSK | 2 | 3.5% | arch, Copulas |
| 基本面研究 | DAT | 2 | 3.5% | FinanceToolkit, tsfresh |
| 金融数据基础设施 | DAT | 2 | 3.5% | ArcticDB, OpenBB |
| 固收定价 | PRC | 1 | 2% | rateslib |

## SOP v3.0 采纳的精选清单

从 90 条研究成果中，SOP v3.0 精选纳入：
- 金融通用必审清单：20 条（横切关注点全量纳入）
- TRD 交易与执行：8 条（从 12 条精选）
- PRC 定价与估值：8 条（从 12 条精选）
- RSK 风险与配置：8 条（从 12 条精选）
- CRD 信用与银行：6 条（从 10 条精选）
- CMP 合规与ESG：6 条（从 8 条精选）
- DAT 数据与研究：5 条（从 8 条精选）
- AIL AI/LLM金融：6 条（从 8 条精选）
- A 股市场规则：11 条（原有保留）

## 完整研究清单（未精选的条目供未来参考）

以下列出各子领域研究中产出但未纳入 SOP v3.0 的条目（已被精选条目覆盖或优先级较低）：

### TRD 额外条目
- 模拟延迟模型（Latency Model）— HFT 专项，通用 SOP 中优先级低
- P&L 归因与会计正确性 — 已被横切关注点 #9 (PnL 守恒) 覆盖
- 时间精度与时区一致性 — 已被横切关注点 #3 (时区归一化) 覆盖
- 价格精度与合约规格 — 已被横切关注点 #20 (Tick/Lot Size) 覆盖

### PRC 额外条目
- 蒙特卡洛方差缩减 — 定价引擎专项，非通用必审
- 概率测度与计价单位 — 高度专业化，非通用必审
- 红利与资金成本处理 — 已被 TRD #5 (资金成本) 部分覆盖
- 结算惯例与 Spot Lag — 已被横切关注点 #19 (结算约定) 覆盖

### RSK 额外条目
- 多期 vs 单期优化视野 — 组合优化专项
- HRP 层次聚类的链接方法 — 高度专业化
- 最大回撤计算的时间粒度 — 已被横切关注点 #3 (收益率频率) 相关覆盖
- 因子暴露归因方法（Brinson vs 因子模型） — 绩效归因专项

### CRD 额外条目
- 抵押品评估与 LGD 回收率时间价值 — 高度专业化
- 禁止再违约/cure rate 的状态转移约束 — 信用建模专项
- 信用组合损失分布尾部数值积分精度 — Vasicek 模型专项
- 宽限期与暂停违约的时序先后顺序 — NPL 管理专项

### DAT 额外条目
- 去重策略与追加写入幂等性 — 数据库运维专项
- 特征选择的统计检验方法 — tsfresh 专项
- 时区一致性与归一化 — 已被横切关注点 #3 覆盖

### AIL 额外条目
- LoRA 微调超参数与目标模块选择 — FinGPT 专项
- LLM 微调的数据时序切割 — 已被 #1 (时间段边界) 覆盖
