# Zipline Blueprint 四方评审 Prompt

> 分别发给 Claude / GPT / Gemini / Grok
> 日期：2026-04-04
> 目的：验证蓝图提取流水线在第二个项目上的表现

---

## 提示词

```
你是一位资深量化系统架构师 + AI 知识工程专家。

我们正在验证一套"蓝图提取流水线"——从开源项目源码中自动提取架构蓝图。此前已用 freqtrade 验证过（V3 四方评审平均 91 分源码忠实度）。现在用第二个项目 zipline-reloaded 验证流水线的可复用性。

这份蓝图是用同一套流水线从 zipline-reloaded（stefan-jansen/zipline-reloaded）源码中提取的。流水线步骤：
1. Clone 仓库
2. Claude Code 子代理读源码提取架构骨架（含文件路径+行号）
3. 自动 grep 验证（14 项领域检查 + 15 项 evidence 行号验证，全部通过）
4. 基于验证结果组装 Blueprint YAML

请评审这份蓝图的质量，以及流水线在不同项目上的适应性。

## 蓝图（完整）

```yaml
id: finance-bp-002
name: 事件驱动回测系统（zipline Pipeline 模式）
version: "1.0.0"

source:
  projects: [stefan-jansen/zipline-reloaded]
  extraction_method: semi_auto
  confidence: 0.90
  evidence:
    entry_point: zipline/__main__.py:468
    run_algorithm: zipline/utils/run_algo.py:304
    trading_algorithm: zipline/algorithm.py:142-605
    event_loop: zipline/gens/tradesimulation.py:99
    clock: zipline/gens/sim_engine.pyx:25-73
    every_bar: zipline/gens/tradesimulation.py:107-168
    slippage_abstractmethod: zipline/finance/slippage.py:121
    commission_abstractmethod: zipline/finance/commission.py:47
    bar_data: zipline/_protocol.pyx:116
    order_model: zipline/finance/order.py:44
    position_model: zipline/finance/position.py:44
    pipeline_engine: zipline/pipeline/engine.py:80
    asset_model: zipline/assets/_assets.pyx:44
    splits_handling: zipline/gens/tradesimulation.py:174
    trading_controls: zipline/finance/controls.py

applicability:
  domain: finance
  task_type: quantitative_backtesting
  description: >
    事件驱动回测系统。用户定义 initialize/handle_data 两个函数，
    系统按 bar-by-bar 事件循环驱动回测。
    独有 Pipeline API 支持声明式跨截面因子计算。
    内置 corporate actions 处理（splits/dividends），适合股票市场。
  prerequisites: [数据需通过 bundles 系统摄入, Python 3.10+, Cython 编译依赖]
  not_suitable_for:
    - 加密货币（无内置交易所支持）
    - 实盘交易（纯回测框架，无实盘模式）
    - 高频策略（逐 bar Python 调用开销大）
    - 快速参数扫描（无内置 Hyperopt）

execution_paradigm:
  backtest: event_driven_bar_by_bar  # 时钟产出(dt,action)事件，逐bar处理
  # 无 dry_run 和 live — 纯回测框架

# ── 5 个阶段 ──

stages:

  - id: data_layer
    name: 数据层（Bundles + DataPortal）
    order: 1
    responsibility: >
      通过 data bundles 摄入数据，通过 DataPortal 统一访问。
      内置 corporate actions（splits/dividends 自动调整）。
      底层 Bcolz 列式存储。
    interface:
      outputs:
        - name: bar_data
          description: >
            BarData 对象（Cython），用户在 handle_data 中接收。
            不是 DataFrame，而是按 bar 查询的接口：
            current(assets,fields) / history(assets,fields,bar_count,freq)
            fields: open/high/low/close/volume/price/last_traded
            价格自动复权。
    replaceable_points:
      - "data_bundle: csvdir(默认/本地CSV) / quandl(美股) / custom_bundle(自定义)"
      - "trading_calendar: XNYS(默认/美股) / custom(通过 exchange_calendars 扩展)"
    design_decisions:
      - "DataPortal 是数据统一入口（data_portal.py:89）"
      - "数据自动复权——BarData 返回已 adjusted 价格"
      - "Bcolz 列式存储"
      - "data bundles 标准化摄入/加载/清理"
      - "交易日历驱动所有日期操作"

  - id: user_strategy
    name: 用户策略
    order: 2
    responsibility: >
      用户定义四个生命周期函数。函数式接口（非 class 继承）。
      通过 ZiplineAPI 上下文访问下单/Pipeline/调度能力。
    interface:
      required_methods:
        - "initialize(context) — 模拟开始调用一次。非抽象，namespace.get()查找 [algorithm.py:419]"
        - "handle_data(context, data) — 每bar调用。非抽象，默认noop [algorithm.py:443]"
        - "before_trading_start(context, data) — 每天开盘前。可选 [algorithm.py:426]"
        - "analyze(context, perf) — 回测结束后。可选 [algorithm.py:447]"
        - "注意：四个函数均无 @abstractmethod，通过 namespace 动态查找或参数传入"
      outputs:
        - "Orders — 通过 order()/order_target_percent() 等 6 种 API 产生"
    design_decisions:
      - "函数式接口——用户定义独立函数，不继承基类"
      - "四个生命周期函数均无 @abstractmethod"
      - "6 种下单 API: order/order_value/order_percent/order_target/order_target_value/order_target_percent"
      - "schedule_function 支持定时调度"

  - id: event_loop
    name: 事件驱动交易循环
    order: 3
    responsibility: >
      MinuteSimulationClock 产出(dt,action)事件流，
      AlgorithmSimulator.transform() 按事件分发。
      每 bar: 先撮合上一 bar 订单，再调用 handle_data。
      内嵌 slippage/commission 模型和 trading controls。
    key_behaviors:
      - behavior: "T+1 订单延迟"
        description: "every_bar()先撮合旧单(blotter.get_transactions)再执行handle_data"
        evidence: "tradesimulation.py:107-168"
      - behavior: "5 种事件: BAR/SESSION_START/SESSION_END/MINUTE_END/BEFORE_TRADING_START_BAR"
        evidence: "sim_engine.pyx:25"
      - behavior: "Splits 在 SESSION_START 自动处理"
        evidence: "tradesimulation.py:174"
      - behavior: "SlippageModel.process_order() 是 @abstractmethod"
        evidence: "slippage.py:121"
      - behavior: "CommissionModel.calculate() 是 @abstractmethod"
        evidence: "commission.py:47"
      - behavior: "Trading controls: MaxOrderSize/MaxOrderCount/MaxPositionSize/LongOnly/MaxLeverage"
        evidence: "controls.py"
    replaceable_points:
      - "slippage: FixedBasisPointsSlippage(默认/股票) / VolumeShareSlippage / NoSlippage"
      - "commission: PerShare(默认/$0.001) / PerContract($0.85/期货) / PerTrade"

  - id: pipeline_api
    name: Pipeline API（声明式因子计算，zipline 独创）
    order: 2  # 与 user_strategy 同 order
    responsibility: >
      声明式跨截面数据处理：Factor/Filter/Classifier → 依赖图 → 拓扑排序 → 批量计算。
      支持动态选股和多因子排名。
    interface:
      required_methods:
        - "attach_pipeline(pipe, name) — initialize 中注册 [algorithm.py:302]"
        - "pipeline_output(name) — before_trading_start 中获取结果"
      outputs:
        - "DataFrame(index=[date,asset], columns=用户定义的因子列)"
    design_decisions:
      - "声明式——用户描述'算什么'，引擎决定'怎么算'"
      - "基于 Term 依赖图拓扑排序（pipeline/engine.py:80）"
      - "三类表达式: Factor(数值)/Filter(布尔)/Classifier(分类)"
      - "内置 20+ 因子: SMA, VWAP, RSI, MACD, BollingerBands, Returns..."

  - id: evaluation
    name: 绩效评估
    order: 4
    responsibility: MetricsTracker 逐 bar 聚合指标，TradingAlgorithm.run() 返回 daily_stats DataFrame。
    interface:
      outputs:
        - "pd.DataFrame(portfolio_value, returns, pnl, alpha, beta, sharpe, sortino, max_drawdown, positions, transactions)"

data_flow:
  - {from: data_layer, to: user_strategy, data: "BarData(current/history)", type: data_flow}
  - {from: user_strategy, to: event_loop, data: "Orders", type: data_flow, note: "T+1延迟"}
  - {from: pipeline_api, to: user_strategy, data: "pipeline DataFrame", type: data_flow, required: false}
  - {from: event_loop, to: evaluation, data: "daily_perfs", type: data_flow}

global_contracts:
  - contract: "T+1 订单延迟：Bar T 下单 → Bar T+1 撮合"
    evidence: "tradesimulation.py:107-168"
    note: "通过执行顺序保证，无 shift（与 freqtrade 不同）"
  - contract: "价格自动复权"
    evidence: "data_portal.py AdjustmentReader"
  - contract: "Splits/Dividends 在 SESSION_START 自动处理"
    evidence: "tradesimulation.py:174"
  - contract: "SlippageModel.process_order() 和 CommissionModel.calculate() 是唯二 @abstractmethod"
    evidence: "slippage.py:121 + commission.py:47"
  - contract: "用户函数不是 @abstractmethod（namespace 动态查找）"
    evidence: "algorithm.py:362-374"
```

## 评审要求

### Part 1：源码忠实度

1. 如果你熟悉 zipline 源码，蓝图中的阶段划分是否与真实模块边界一致？
2. "T+1 订单延迟通过执行顺序保证，无需 shift"这条描述是否准确？这与 freqtrade 的 shift(1) 机制有什么本质区别？
3. "用户四个生命周期函数均无 @abstractmethod，通过 namespace 动态查找"——是否正确？
4. "SlippageModel.process_order() 和 CommissionModel.calculate() 是唯二的 @abstractmethod"——是否正确？是否有遗漏的 @abstractmethod？
5. Pipeline API 的描述是否准确反映了 zipline 的实际实现？

### Part 2：与 freqtrade 蓝图的架构对比

6. 两份蓝图（freqtrade bp-001 vs zipline bp-002）体现了同一任务（量化回测）的两种不同解法。它们的关键差异被正确捕捉了吗？遗漏了什么？
7. 两个项目的防前瞻偏差机制不同（freqtrade 用 shift(1)，zipline 用执行顺序）。蓝图是否清晰地表达了这个区别？
8. 如果一个用户说"帮我做一个股票投资分析工具"，这两份蓝图中应该推荐哪个？蓝图中的 applicability 描述是否足以支撑这个选择？

### Part 3：流水线可复用性

9. 这是用同一套流水线提取的第二个项目。从 freqtrade 到 zipline，流水线展示了哪些适应能力？有什么不足？
10. 自动验证脚本在 zipline 上的 14 项领域检查中有 7 项报 ⚠️ warning（signal_shift/fee/stoploss/data_format/hyperopt/ml/rpc）。这些 warning 是合理的（zipline 确实没有这些特性）还是说明验证规则需要调整？
11. 从工程角度，你怎么评价"同一套验证规则应用于架构完全不同的两个项目"这种做法？

### Part 4：评分与改进

12. 给这份蓝图打分：

| 维度 | 得分(0-100) | 理由 |
|------|------------|------|
| 源码忠实度 | ? | |
| AI 消费品质量 | ? | |
| 架构抽象质量 | ? | |

13. 这份蓝图最需要改进的 3 点是什么？
14. 如果这份蓝图交给宿主 AI（Claude Code / Cursor），AI 能否基于它构建出一个可用的 zipline 策略？还差什么？

## 输出格式

按 Part 1-4 结构回答，每题给出具体判断。Part 4 评分用表格。
```

---

## 使用说明

1. 分别发给 Claude、GPT-4o、Gemini 2.5 Pro、Grok
2. 回复保存到：
   - `docs/research/judgment-system/blueprint-zipline-review-claude.md`
   - `docs/research/judgment-system/blueprint-zipline-review-gpt.md`
   - `docs/research/judgment-system/blueprint-zipline-review-gemini.md`
   - `docs/research/judgment-system/blueprint-zipline-review-grok.md`
3. 重点关注 Part 2（与 freqtrade 对比）和 Part 3（流水线可复用性）
