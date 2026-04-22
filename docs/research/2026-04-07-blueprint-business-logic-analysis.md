# 蓝图业务逻辑提取分析

日期: 2026-04-07
目的: 分析"业务逻辑"在不同金融子领域中的表现形式，支撑 SOP v3.0 中 M 类分类的引入

## 核心发现

"业务逻辑"不是一种东西。不同子领域的业务逻辑性质根本不同：

| 子领域 | 业务逻辑的本质 | 典型例子 | 原 T/B/BA/DK/RC 能覆盖？ |
|--------|--------------|---------|------------------------|
| 交易与执行 | 状态迁移 + 决策规则 | 先卖后买、止损-30%、T+1延迟执行 | 能（B/BA/RC） |
| 定价与估值 | 数学模型选择 + 数值假设 | Heston vs BS、蒙特卡洛路径数、波动率曲面插值 | 不能 |
| 风险与配置 | 概率假设 + 优化约束 | VaR 99%、Ledoit-Wolf 收缩、再平衡触发 | 部分（BA 能覆盖假设） |
| 信用与银行 | 监管公式 + 评分方法论 | PD logistic regression、WoE 分箱、Basel III | 不能（RC 只覆盖监管事实） |
| AI/LLM金融 | 训练范式 + 数据隔离 | RL reward 设计、train/test 切分、多 Agent 共识 | 不能 |

## 决策：引入 M 类

M (Mathematical/Model Choice) — 基于数学推导或统计假设的方法选择。

判断准则："这是基于数学/统计理论的选择吗？换了模型/方法，结果精度或含义会变吗？"

### M 与其他类型的边界

| 场景 | 分类 | 理由 |
|------|------|------|
| 选 Black-Scholes 定价 | M | 数学模型选择 |
| 选 SQLite 存储 | T | 技术选择，不影响业务结果 |
| 止损阈值 -30% | B/BA | 业务决策 + 假设 |
| T+1 交割制度 | RC | 监管强制 |
| Ledoit-Wolf 协方差收缩 | M | 统计方法选择 |
| A 股换手率作为一等字段 | DK | 市场特有的领域知识 |
| 蒙特卡洛 10 万路径 | M/QT | 数值方法选择 + 定量约束 |

### 三方评审对 M 类的共识

- Grok: 建议增加 ML (Mathematical Logic) + SM (Stochastic/Model-Driven Logic) 两类
- Gemini: 建议增加 M (Mathematical & Statistical Model) 一类
- GPT: 建议两层分类（逻辑性质 × 业务场景），其中逻辑性质包含 numerical_method 和 economic_semantics

SOP v3.0 采纳 Gemini 方案（增加一类 M），兼顾简洁性和覆盖度。
