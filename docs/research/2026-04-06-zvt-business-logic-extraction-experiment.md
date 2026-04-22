# zvt 业务逻辑提取实验报告

**日期**: 2026-04-06
**项目**: zvtvz/zvt
**目标**: 搞清楚 zvt"业务逻辑"是什么、长什么样，为 Doramagic 第三层知识体系奠基

---

## 1. 项目概览（README 提取）

### zvt 声称自己能做什么

根据 README，zvt 定位为一个**股票市场分析与量化交易平台**，面向 A 股/美股/港股市场，核心能力包括：

#### 业务用例

| # | 业务用例 | 描述 |
|---|---------|------|
| 1 | **股票分析与回测** | 分析历史价格形态、评估财务指标、模拟交易执行以评估策略表现 |
| 2 | **量化研究** | 录入数据、计算技术因子、生成交易信号，使用二维索引模型同时处理多标的 |
| 3 | **机构持仓追踪** | 跟踪机构增仓>5%时买入、减仓>50%时卖出的策略 |
| 4 | **多数据源整合** | 接入东方财富、聚宽、新浪、QMT，实现数据源稳定切换 |
| 5 | **技术指标计算** | MACD、均线、布林带等技术指标因子化计算 |
| 6 | **基本面选股** | 按 ROE、ROTA、机构持仓比等财务指标筛选股票 |
| 7 | **动态股票池管理** | 基于 Tag 标签的动态股票池管理 |
| 8 | **策略可视化** | 交互式仪表盘展示回测结果与策略表现 |
| 9 | **实盘/REST API** | 提供 REST API 和独立 UI 支持实时行情处理 |

#### 典型工作流

```
数据录入 → 增量更新 → 技术因子计算 → 多标的因子评分 → 自动信号生成 → 表现可视化
```

---

## 2. 蓝图已有内容 vs 缺失内容

### 蓝图（finance-bp-009）已覆盖的内容

蓝图 `finance-bp-009` 完整描述了 zvt 的**框架架构层**，共 8 个阶段：

| 阶段 | 内容 | 蓝图质量 |
|------|------|---------|
| schema_layer | Schema 驱动数据模型，76 个 declarative_base | 详细，含 pseudocode |
| infrastructure_layer | 存储后端 ABC + Recorder 元类自动注册 | 详细 |
| recorder_layer | 数据录入层，5 种数据源 | 详细，含继承链 |
| data_reader | DataReader + MultiIndex DataFrame | 详细 |
| factor_engine | Transformer + Accumulator 双层计算管线 | 详细，含 pseudocode |
| target_selector | 多因子合并 AND/OR 选股 | 详细，含 pseudocode |
| trader_engine | 回测/实盘主循环，T+1 执行延迟 | 详细，含 pseudocode |
| sim_account | 模拟账户，滑点/手续费 0.1% | 详细 |

**蓝图的定位**：描述"这个框架是怎么运作的"——数据如何流动、组件如何连接、接口是什么。

### 蓝图明确缺失的内容（业务逻辑层）

蓝图描述了管道，但**没有描述管道里跑什么**：

#### 2.1 具体因子的业务定义

蓝图里写了"MaTransformer 用于均线计算"，但没有回答：
- `GoldCrossFactor` 的黄金交叉具体是怎么判断的？`keep_window=10` 的含义是什么？
- `GoodCompanyFactor` 用哪 8 个财务指标？各自的阈值是什么？
- `ZenFactor`（缠论）的中枢判断规则是什么？`zhongshu_range=0.4` 代表什么？

#### 2.2 完整策略的端到端逻辑

蓝图描述了 `Trader.run()` 是什么，但没有描述：
- MACD 日线交易策略：选股范围、入场条件、出场条件
- 机构追踪策略（follow_ii）：触发阈值、持仓周期
- MA 均线交叉策略：短期窗口=5、长期窗口=10 的具体含义

#### 2.3 参数化决策（业务知识）

- 默认止盈 +300%、止损 -30% 的合理性来自哪里？
- 仓位三档（0.2/0.5/1.0）的业务含义
- `GoodCompanyFactor` 默认 `window=1095d`（3 年）的业务依据

#### 2.4 数据→信号→决策的完整语义链

蓝图只说"filter_result 是 bool 型"，但没有说：
- `True` 意味着"明天早盘开仓做多"
- `False` 意味着"持有或空仓不操作"
- 信号 T+1 执行延迟的**业务含义**（避免未来函数/look-ahead bias）

---

## 3. 因子模块详细分析

### 3.1 MACD 因子（技术指标类）

**文件**: `src/zvt/factors/macd/macd_factor.py`

#### 因子族

| 因子类 | 计算内容 | 输出信号 |
|--------|---------|---------|
| `GoldCrossFactor` | MACD 金叉（DIFF 上穿 DEA） | filter_result: True/False |
| `BullFactor` | MACD DIFF > 0 且 MACD 柱 > 0 | filter_result: True/False |
| `KeepBullFactor` | 持续 10 个周期内都是 BullFactor | filter_result: True/False |
| `LiveOrDeadFactor` | 从长期死叉转金叉的特征 | filter_result: True/False |

**输入**: 日线/周线 K 线价格数据（由 MacdTransformer 计算 DIFF/DEA/MACD 柱）

**可配置参数**:
- `keep_window = 10`：KeepBullFactor 的持续窗口
- `pattern = [-5, 1]`：LiveOrDeadFactor 的死叉/金叉计数阈值

**业务问题**: 当前是否出现 MACD 技术性买入信号？信号是否足够持续？

---

### 3.2 基本面因子（GoodCompanyFactor）

**文件**: `src/zvt/factors/fundamental/finance_factor.py`

**计算逻辑**:

```
对每个标的，在 window=1095d（3年）滚动窗口内：
1. 检查 ROE >= 2%
2. 检查营业收入增长 > 0
3. 检查净利润增长 > 0
4. 检查经营现金流/净利润 >= 合理阈值
5. 检查流动比率
6. 检查资产负债率
7. 检查应收账款占流动资产比例 <= 30%
8. 其他质量维度...

→ 统计满足条件的数量 >= count（默认=8）
→ 输出 filter_result: True/False
```

**输入**: 财务报表数据（资产负债表、利润表、现金流量表）

**可配置参数**:
- `window = '1095d'`：评估窗口（默认 3 年）
- `count = 8`：最少需满足的指标数
- `col_period_threshold`：年报 vs 季报的期望调整

**业务问题**: 这家公司在过去 3 年内是否持续展现财务健康？

---

### 3.3 缠论因子（ZenFactor）

**文件**: `src/zvt/factors/zen/zen_factor.py`

**计算逻辑**（缠论中枢分析）:

系统追踪**中枢（Zhongshu）** — 价格在某区间内反复震荡的区域，用于判断趋势结构。

| 概念 | 含义 | 参数 |
|------|------|------|
| `ZhongshuRange` | 中枢区间大小（small<=0.4, big>0.4） | range 阈值 |
| `ZhongshuLevel` | 中枢级别（bar 数量分三档） | - |
| `ZhongshuDistance` | 相邻中枢间距（big_up/big_down/small_up/small_down） | - |

**因子**:
- `TrendingFactor`：识别低波动预启动区（good_state = 近期中枢小范围 + 中等级别）
- `ShakingFactor`：识别"窄幅震荡"入场机会（change<=0.5, level>=2, interval>=120 bars，价格在中枢边界附近）

**输出**: filter_result: True/False（是否满足缠论入场条件）

**业务问题**: 按缠论，现在是否处于低风险的潜在突破前夕？

---

## 4. Examples 详细分析

### 4.1 MACD 日线交易策略（macd_day_trader.py）

**业务场景**: 基于 MACD 日线金叉的 A 股自动交易策略

**完整流程**:

```
输入:
  - 股票范围: 全 A 股（或指定 entity_ids）
  - 时间范围: 2019-01-01 ~ 2020-01-01
  - 数据源: JoinQuant
  - 周期: 日线（LEVEL_1DAY）

处理:
  1. GoldCrossFactor 计算所有标的的 MACD 金叉信号
     → 回看窗口: 50 根 K 线
  2. TargetSelector 筛选 filter_result == True 的标的
  3. Trader 主循环: T 周期产生信号，T+1 周期开盘执行
  4. 仓位控制: 空仓买 2 成，持仓 <= 10 买 5 成，> 10 买满

输出:
  - AccountStats（账户资产曲线）
  - Position（持仓记录）
  - Order（订单记录）
  → 持久化到 SQLite，可通过 UI 可视化
```

**可运行性**: 完整可运行（有 `if __name__ == "__main__"` 入口），依赖 zvt 安装 + JoinQuant 账号

**组件使用**: `GoldCrossFactor` + `StockTrader` + `IntervalLevel.LEVEL_1DAY`

---

### 4.2 机构追踪策略（follow_ii_trader.py）

**业务场景**: 跟踪机构投资者持仓变化的 A 股择时策略

**完整流程**:

```
输入:
  - 标的: 股票代码 "600519"（贵州茅台）
  - 时间范围: 2002-01-01 ~ 2021-01-01
  - 数据源: 东方财富（em）

处理:
  on_time(timestamp) 回调中:
  1. 查询最近一期财报数据
  2. 从 StockActorSummary 获取机构投资者持仓变化
  3. 筛选条件:
     - 买入信号: change_ratio > 5%（增仓超 5%）
     - 卖出信号: change_ratio < -50%（减仓超 50%）
  4. 按信号生成 open_long / open_short 列表

输出:
  - 交易记录（持久化到数据库）
  - 账户表现（AccountStats）
```

**可运行性**: 完整可运行（19 年回测范围）

**组件使用**: `StockActorSummary` + `Stock1dKdata` + `StockTrader.on_time()` 回调

**关键洞察**: 这个例子演示了如何绕过 Factor 体系，直接在 `on_time` 回调里手写信号逻辑——适合非标准化信号。

---

### 4.3 基本面选股器（fundamental_selector.py）

**业务场景**: 多因子基本面选股，筛选"核心资产"

**完整流程**:

```
输入:
  - 时间范围: 2015-01-01 ~ 2019-06-30
  - 数据源: 东方财富（em）
  - 快照时间点: 2019-06-30

处理:
  Factor 1（GoodCompanyFactor）:
    → 高 ROE + 高现金流 + 低财务杠杆 + 有增长
  Factor 2（GoodCompanyFactor，不同 data_schema）:
    → 应收账款 <= 流动资产的 30%（低应收款质量标准）

  两个 Factor 通过 AND 合并（SelectMode.condition_and）:
    → 同时满足两个质量维度才入选

输出:
  → get_targets() 返回快照日期的入选股票代码列表
```

**可运行性**: 基本完整（缺少 `if __name__ == "__main__"`，但逻辑完整），需补充调用入口

**组件使用**: `GoodCompanyFactor` + `TargetSelector` + `BalanceSheet` + `SelectMode.condition_and`

---

## 5. 核心发现：业务逻辑的定义与分类

### A. 业务逻辑的定义

从 zvt 项目来看，"业务逻辑"是介于框架架构（蓝图）和用户自定义代码之间的**中间层知识**。它回答的不是"组件怎么工作"，而是**"用这些组件能构建什么有意义的投资决策流程"**。

业务逻辑 = **领域语义 + 参数决策 + 完整流程**

### B. 业务逻辑的三类知识

#### 类型 1：因子语义（Factor Semantics）

单个因子的**业务含义**：这个指标在经济/投资上代表什么？

| 特征 | 例子 |
|------|------|
| 有具体的投资假设 | "MACD 金叉意味着短期动能转向上涨" |
| 有数值边界及含义 | "ROE >= 2% 才视为有效盈利" |
| 有参数的业务理由 | "3 年滚动窗口覆盖完整经济周期" |

示例：`GoldCrossFactor`、`GoodCompanyFactor`、`TrendingFactor`

#### 类型 2：策略流程（Strategy Workflow）

从信号到交易的**完整可执行流程**：什么条件入场、什么条件出场、如何管理仓位。

| 特征 | 例子 |
|------|------|
| 有明确的进出场条件 | "金叉买入，死叉卖出" |
| 有风险控制参数 | "止损 -30%，止盈 +300%" |
| 有时间和范围界定 | "日线级别，全 A 股范围" |
| 端到端可运行 | `macd_day_trader.py` 有 `__main__` 入口 |

示例：`macd_day_trader`、`follow_ii_trader`、`ma_trader`

#### 类型 3：选股逻辑（Screening Logic）

从全市场到投资候选集的**系统性筛选规则**：用什么标准缩小范围、多个标准如何组合。

| 特征 | 例子 |
|------|------|
| 有多维度标准组合 | "高 ROE AND 低应收款 AND 有增长" |
| 有合并逻辑 | "AND/OR 逻辑组合" |
| 有结果快照 | "在某时间点的入选名单" |

示例：`fundamental_selector`、`ZenFactor` 组合选股

---

## 6. 业务逻辑卡片示例

### 卡片 1：MACD 日线金叉策略

```
名称: MACD 日线金叉交易策略

业务问题: 如何通过 MACD 技术指标识别 A 股日线级别的趋势转折买入点，并自动化执行交易？

输入:
  - 标的范围: A 股全市场（可缩窄至特定代码）
  - 时间范围: 用户指定（示例: 2019-01-01 ~ 2020-01-01）
  - 数据周期: 日线（LEVEL_1DAY）
  - 数据源: JoinQuant 或 东方财富
  - 计算窗口: 50 根 K 线（回看期）

输出:
  - 账户资产曲线（AccountStats）
  - 逐笔持仓记录（Position）
  - 订单明细（Order）
  - 策略可视化报告（可选）

核心步骤:
  1. 数据准备: 从数据源加载日线 OHLCV 数据
  2. 信号计算: MacdTransformer 计算每个标的的 DIFF/DEA/MACD 柱
  3. 金叉检测: GoldCrossFactor 判断 DIFF 上穿 DEA（filter_result=True）
  4. 选股: TargetSelector 汇总所有 filter_result=True 的标的
  5. 信号延迟: T 周期产生信号，T+1 周期开盘执行（避免未来函数）
  6. 仓位分配: 按选中标的数量均分，空仓 20%/持仓<=10 个 50%/持仓>10 个 100%
  7. 先卖后买: 先平持有死叉标的，再买入新金叉标的
  8. 风控: 止盈 +300%，止损 -30%

参数（可配置）:
  - lookback_window: 50（回看计算窗口，影响 MACD 初始化质量）
  - profit_threshold: (3, -0.3)（止盈倍数, 止损比例）
  - level: LEVEL_1DAY（可改为 LEVEL_1WEEK 等）
  - start/end_timestamp: 回测/实盘时间范围

验证标准:
  - 信号一致性: 金叉后价格在 5-10 日内有上涨概率 > 50%
  - 无未来函数: T 周期收盘价产生信号，T+1 周期才成交
  - 账户记录完整: AccountStats 每周期都有更新
  - 先卖后买: Order 日志中卖单时间戳 <= 买单时间戳

依赖的框架能力:
  - MacdTransformer: EWM 计算 MACD 三元组
  - GoldCrossFactor: 继承 Factor，实现 filter_result 输出
  - TargetSelector: 合并多因子 filter，生成 open_long 列表
  - StockTrader.run(): 主循环，管理 T+1 延迟和仓位控制
  - SimAccountService: 资金/持仓/盈亏核算
  - Stock1dKdata Schema: 日线 K 线数据存储和读取
```

---

### 卡片 2：多因子基本面选股

```
名称: 高质量公司多因子基本面筛选

业务问题: 如何从全 A 股中系统性地筛选出"财务健康、持续盈利、低风险"的核心资产候选池？

输入:
  - 财务数据: ROE、营收增长率、净利润增长率、经营现金流、应收账款、流动比率、资产负债率
  - 评估窗口: 1095 天（3 年滚动）
  - 报告期类型: 年报 / 季报（会调整期望阈值）
  - 数据源: 东方财富（em）
  - 快照时间: 用户指定（示例: 2019-06-30）

输出:
  - 通过筛选的股票代码列表（快照日期的截面）
  - 可进一步输入至 Trader 作为候选池

核心步骤:
  1. 加载财务报表数据（利润表 + 资产负债表 + 现金流量表）
  2. Factor 1: GoodCompanyFactor 检验 8 项质量指标，滚动 3 年统计满足数量 >= 8
  3. Factor 2: GoodCompanyFactor（BalanceSheet schema）检验应收款占比 <= 30%
  4. 两个 Factor AND 合并（SelectMode.condition_and）
  5. get_targets(timestamp) 返回快照日满足条件的股票列表

参数（可配置）:
  - window: '1095d'（评估时间窗口，默认 3 年）
  - count: 8（最少满足的指标数量）
  - col_period_threshold: 年报/季报调整系数
  - select_mode: condition_and / condition_or（多因子合并逻辑）

验证标准:
  - 入选标的近 3 年 ROE 均值 > 2%
  - 入选标的应收款占流动资产 <= 30%
  - 快照日期正确（不引入未来财务数据）
  - 回测对比: 入选股票组合在评估窗口后 1 年的表现优于基准

依赖的框架能力:
  - GoodCompanyFactor: 继承 Factor，实现多指标评分逻辑
  - BalanceSheet / FinanceBalanceSheet Schema: 财务数据存储
  - TargetSelector.get_targets(): 截面快照接口
  - SelectMode.condition_and: AND 逻辑合并多因子
  - DataReader: 按时间范围查询财务数据
```

---

## 7. 粒度判断总结

### 粒度分类框架

| 粒度 | 描述 | 是否适合作为业务逻辑卡片 |
|------|------|----------------------|
| 太细 | 单个函数/指标计算（MACD 公式本身） | 否，属于框架原语 |
| 适中 | 完整业务流程（选股策略/交易策略） | 是，这是业务逻辑的核心粒度 |
| 太粗 | 整个平台能力描述 | 否，属于产品介绍 |

### 各文件粒度评估

| 文件 | 粒度 | 评估 | 原因 |
|------|------|------|------|
| `macd_factor.py` 中的单个类（如 GoldCrossFactor） | 太细 | 偏细，但有价值 | 只是一个指标信号，缺少完整交易流程 |
| `macd_day_trader.py` | 适中 | 最佳粒度 | 有完整输入/输出/参数/流程，端到端可执行 |
| `follow_ii_trader.py` | 适中 | 最佳粒度 | 独特策略（机构追踪），完整流程 |
| `fundamental_selector.py` | 适中 | 最佳粒度 | 完整选股流程，可组合到交易策略中 |
| `zen_factor.py` 单个类 | 太细 | 偏细 | 缺论证完整交易流程 |
| `zen_factor.py` + `zen_trader.py`（如果存在） | 适中 | 需配对 | 因子+策略配对才是完整业务逻辑 |
| zvt 整体平台描述（README 级别） | 太粗 | 太粗 | 描述平台定位，非具体流程 |

### 关键结论

**最佳业务逻辑粒度** = `examples/trader/` 和 `examples/factors/` 中的完整 example 文件

这些文件具备：
1. 明确的投资假设（为什么这个信号有效）
2. 具体的参数值（不是"可以配置"，而是"默认值是 X，理由是 Y"）
3. 端到端流程（数据→信号→交易→结果）
4. 可验证性（有 `__main__` 入口可直接跑）
5. 适当的抽象层次（不是 MACD 公式，也不是整个平台）

---

## 附录：本次实验的元发现

### 业务逻辑 vs 蓝图 vs 约束的三层关系

```
蓝图（Blueprint）:   "框架有哪些管道，管道怎么连"
                        ↓
业务逻辑（Business Logic）: "管道里跑什么，跑出来是什么意思"
                        ↓
约束（Constraint）:  "什么不能跑，哪里会出错"
```

### 提取方向建议

下一步批量提取业务逻辑时，优先覆盖 `examples/` 目录下的：
- `examples/trader/`（7 个策略，每个可出 1 张卡片）
- `examples/factors/`（4 个选股逻辑，每个可出 1 张卡片）
- `examples/reports/`（报告生成逻辑，属于"分析输出"类业务逻辑）

建议卡片字段（与本报告卡片格式一致）：
`名称 / 业务问题 / 输入 / 输出 / 核心步骤 / 参数 / 验证标准 / 依赖的框架能力`
