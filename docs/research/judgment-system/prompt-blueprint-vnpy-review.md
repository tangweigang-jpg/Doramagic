# vnpy Blueprint 四方评审 Prompt

> 分别发给 Claude / GPT / Gemini / Grok
> 日期：2026-04-04
> 目的：验证蓝图提取流水线在第三个项目上的表现，并汇总三项目对比

---

## 提示词

```
你是一位资深量化系统架构师 + AI 知识工程专家。

这是一套"蓝图提取流水线"的第三次验证。此前已成功提取：
- freqtrade（向量化，加密货币）— V3 四方评审平均源码忠实度 91
- zipline-reloaded（事件驱动，美股）— 四方评审平均源码忠实度 88.5

现在用第三个项目 vnpy（插件化事件驱动，中国市场）验证流水线。

这次提取严格按 SOP 执行了完整 5 步：
1. Clone
2a. 粗提取（子代理读源码）
2b. 关键声明验证（第二个子代理逐行验证 10 条声明，9✅ 1⚠️）
3. 自动验证（14 项领域检查 + 11 项 evidence 行号验证全通过）
4. 组装蓝图

特别说明：从 zipline 评审中学到教训（"唯二 @abstractmethod" 错误），这次对 vnpy 做了 @abstractmethod 完整扫描，确认共 25 个分布在 6 个文件。

## 蓝图（完整）

```yaml
id: finance-bp-003
name: 插件化事件驱动交易框架（vnpy 模式）
version: "1.0.0"

source:
  projects: [vnpy/vnpy]  # 中国量化交易框架 v4.3.0
  extraction_method: semi_auto
  confidence: 0.90
  evidence:
    event_engine: vnpy/event/engine.py:48-78
    main_engine: vnpy/trader/engine.py:51
    gateway_abstract: vnpy/trader/gateway.py:160-255
    data_models: vnpy/trader/object.py:17-178
    alpha_strategy: vnpy/alpha/strategy/template.py:43-53
    backtesting: vnpy/alpha/strategy/backtesting.py:579-673
    cross_order_before_on_bars: vnpy/alpha/strategy/backtesting.py:614-615
    database_abstract: vnpy/trader/database.py:52-128
    dynamic_loading: vnpy/trader/datafeed.py:54-58
    optimize: vnpy/trader/optimize.py
    rpc: vnpy/rpc/

applicability:
  domain: finance
  task_type: quantitative_trading_framework
  description: >
    插件化事件驱动交易框架。核心仓库只提供抽象接口（EventEngine +
    BaseGateway + BaseDatabase + 策略模板），所有实际实现（CTP网关、
    CTA策略、数据库后端）通过 pip 包动态加载。
    面向中国市场（期货/股票），内置涨跌停板检测。
  prerequisites: [Python 3.10+, 安装对应网关包, 安装策略应用包]
  not_suitable_for:
    - 纯回测研究（框架偏重实盘）
    - 不需要事件驱动的简单策略
    - 需要 Pipeline 声明式因子计算

execution_paradigm:
  live: event_driven_queue         # EventEngine Queue + handler 分发
  backtest: bar_by_bar_simulation  # 逐 K 线 cross_order → on_bars

# ── 5 个阶段 ──

stages:

  - id: event_engine
    name: 事件引擎（vnpy 核心骨架）
    order: 1
    responsibility: 单线程 Queue 消费 + handler 分发。所有模块间通信通过事件解耦。
    interface:
      required_methods:
        - "register(type, handler) — 注册事件 handler [engine.py:80]"
        - "put(event) — 放入队列 [engine.py:93]"
        - "_process(event) — typed handler + general handler 两级分发 [engine.py:66-78]"
    design_decisions:
      - "单线程 Queue 消费（engine.py:48-63）"
      - "typed handler + general handler 两级分发"
      - "timer 线程定时产出 EVENT_TIMER"
      - "所有模块通过事件解耦——Gateway/Strategy/Engine 不直接调用彼此"

  - id: data_models
    name: 数据模型（全 @dataclass）
    order: 1
    responsibility: 标准化数据结构，全部 @dataclass。
    interface:
      outputs:
        - description: |
            TickData: symbol, exchange, datetime, 5档买卖, last_price, limit_up/limit_down [object.py:29]
            BarData: symbol, exchange, datetime, interval, OHLC, volume [object.py:87]
            OrderData: symbol, exchange, orderid, type, direction, offset, price, volume, status [object.py:111]
            TradeData: symbol, exchange, orderid, tradeid, direction, offset, price, volume [object.py:153]
            PositionData: symbol, exchange, direction, volume, frozen, pnl, yd_volume [object.py:178]
    design_decisions:
      - "全 @dataclass（轻量、类型安全）"
      - "BaseData 含 gateway_name——标识数据来源"
      - "TickData 有 5 档买卖盘 + 涨跌停价——中国市场特有"
      - "OrderData.offset 区分开仓/平仓——期货市场必需"

  - id: gateway_layer
    name: 网关抽象层（7 个 @abstractmethod）
    order: 2
    responsibility: BaseGateway 定义 7 个抽象方法，实际网关全部外部 pip 包。
    interface:
      required_methods:
        - "connect(setting) 【@abstractmethod gateway.py:160】"
        - "close() 【@abstractmethod gateway.py:182】"
        - "subscribe(req) 【@abstractmethod gateway.py:189】"
        - "send_order(req) -> str 【@abstractmethod gateway.py:196】"
        - "cancel_order(req) 【@abstractmethod gateway.py:214】"
        - "query_account() 【@abstractmethod gateway.py:248】"
        - "query_position() 【@abstractmethod gateway.py:255】"
    replaceable_points:
      - "vnpy_ctp（中国期货/默认）/ vnpy_ib（全球）/ vnpy_binance（加密货币）"
    design_decisions:
      - "网关是纯外部包——核心只定义 7 个抽象方法"
      - "send_quote/cancel_quote 非抽象（有默认空实现）——仅期权询价需要"

  - id: strategy_engine
    name: 策略引擎（3 个 @abstractmethod）
    order: 3
    responsibility: 用户继承 AlphaStrategy 实现 on_init/on_bars/on_trade。CTA 模板在外部包。
    interface:
      required_methods:
        - "on_init() 【@abstractmethod template.py:43】"
        - "on_bars(bars: dict[str, BarData]) 【@abstractmethod template.py:48】"
        - "on_trade(trade: TradeData) 【@abstractmethod template.py:53】"
      trading_api: "buy/sell/short/cover（区分开仓/平仓——期货特有）"
    replaceable_points:
      - "AlphaStrategy（多标的/内置）/ CtaTemplate（单标的/外部 vnpy_ctastrategy）"
    design_decisions:
      - "用 ABCMeta 而非继承 ABC（效果相同）"
      - "买卖 API 区分开仓/平仓（中国期货需要）"

  - id: backtest_engine
    name: 回测引擎（一根延迟 + 涨跌停）
    order: 4
    responsibility: 逐 K 线回测。cross_order 在 on_bars 之前保证延迟。内置涨跌停检测。
    key_behaviors:
      - behavior: "一根 K 线延迟"
        description: "cross_order() 在 on_bars() 之前执行"
        evidence: "backtesting.py:614-615"
      - behavior: "撮合: low/high 判断 + open 最优价"
        description: "多单 order.price >= low, 空单 order.price <= high, 成交价取 min/max(委托价, open)"
        evidence: "backtesting.py:624-673"
      - behavior: "涨跌停板检测"
        description: "涨停封板多单不成交，跌停封板空单不成交"
        evidence: "backtesting.py:642-654"

optional_extensions:
  - {id: optimize, name: 参数优化, evidence: "trader/optimize.py"}
  - {id: alpha_model, name: "Alpha ML 模型(2 @abstractmethod: fit/predict)", evidence: "alpha/model/template.py:12-19"}
  - {id: rpc, name: RPC 远程调用, evidence: "vnpy/rpc/"}
  - {id: database, name: "数据库后端(8 @abstractmethod)", evidence: "trader/database.py:52-128"}
  - {id: chart, name: "K线图表(4 @abstractmethod)", evidence: "chart/item.py:44-67"}

data_flow:
  - {from: gateway_layer, to: event_engine, data: "Event(TICK/ORDER/TRADE)", type: data_flow}
  - {from: event_engine, to: strategy_engine, data: "handler 分发", type: data_flow}
  - {from: strategy_engine, to: gateway_layer, data: "OrderRequest", type: data_flow}
  - {from: data_models, to: backtest_engine, data: "list[BarData]", type: data_flow, condition: "回测模式"}

global_contracts:
  - {contract: "所有模块通过 EventEngine 解耦", evidence: "event/engine.py:48-78"}
  - {contract: "回测一根延迟: cross_order 在 on_bars 前", evidence: "backtesting.py:614-615", note: "与 zipline 类似（执行顺序），与 freqtrade 不同（shift(1))"}
  - {contract: "数据模型全 @dataclass", evidence: "trader/object.py:17-178"}
  - {contract: "网关/策略/数据库通过外部 pip 包动态加载", evidence: "trader/datafeed.py:54"}
  - {contract: "内置涨跌停板检测", evidence: "backtesting.py:642-654"}
  - {contract: "25 个 @abstractmethod 分布在 6 个文件", evidence: "gateway(7)+engine(1)+database(8)+alpha/strategy(3)+alpha/model(2)+chart(4)"}

relations:
  - {type: alternative_to, target: finance-bp-001, rationale: "vnpy=插件化事件驱动(中国市场), freqtrade=向量化交易机器人(加密货币)"}
  - {type: alternative_to, target: finance-bp-002, rationale: "vnpy=实盘交易框架(Gateway), zipline=纯回测(Pipeline API)"}
```

## 三项目对比参考

| 维度 | freqtrade (bp-001) | zipline (bp-002) | vnpy (bp-003) |
|------|-------------------|------------------|---------------|
| 范式 | 向量化 pipeline | 事件驱动 bar-by-bar | 事件驱动 Queue |
| 防前瞻 | shift(1) | 执行顺序 | 执行顺序(cross_order 在 on_bars 前) |
| 用户接口 | 类继承(1 abstractmethod) | 函数式(0 abstractmethod) | 类继承(3 abstractmethod) |
| 目标市场 | 加密货币 | 美股 | 中国期货/股票 |
| 实盘 | ✅ dry_run + live | ❌ 纯回测 | ✅ Gateway 实盘 |
| 独有特性 | Hyperopt/FreqAI/RPC | Pipeline API/Corporate Actions | EventEngine/插件架构/涨跌停 |
| @abstractmethod | 1个 | 数十个 | 25个(完整扫描) |

## 评审要求

### Part 1：源码忠实度

1. 如果你熟悉 vnpy 源码，蓝图中的阶段划分是否与真实模块边界一致？EventEngine 作为独立阶段是否合理？
2. "cross_order() 在 on_bars() 之前执行（一根延迟）"——是否准确？这与 freqtrade 的 shift(1) 和 zipline 的执行顺序有什么异同？
3. "BaseGateway 有 7 个 @abstractmethod"——是否正确？send_quote/cancel_quote 非抽象的说法对吗？
4. "数据模型全部 @dataclass"——是否正确？特别是 TickData 含涨跌停价、OrderData 含 offset（开仓/平仓）。
5. "核心仓库只提供抽象接口，实现全部外部 pip 包"这个架构描述准确吗？

### Part 2：三项目横向对比

6. 三份蓝图（freqtrade/zipline/vnpy）体现了量化回测/交易的三种不同架构。它们的关键差异被正确捕捉了吗？
7. 三种防前瞻偏差机制（shift(1) / 执行顺序 / cross_order 在 on_bars 前）的描述是否准确且相互区分清晰？
8. 如果用户分别说以下需求，应推荐哪个蓝图？蓝图的 applicability 是否支撑选择？
   - "帮我做一个 A 股量化回测系统"
   - "帮我做一个加密货币自动交易机器人"
   - "帮我做一个美股多因子选股研究工具"

### Part 3：流水线成熟度评估

9. 这是流水线第三次提取。对比三次的过程：
   - freqtrade V2 出了 3 个事实错误（shift/date列/abstractmethod），V3 通过新增 grep 验证修正
   - zipline 出了 1 个事实错误（"唯二 abstractmethod"），被四方评审捕获
   - vnpy 这次做了完整 SOP（2a+2b+3+4），声明验证 9✅1⚠️
   流水线的质量是在递进提升还是趋于稳定？还有什么系统性风险？
10. vnpy 的 14 项领域检查中有 6 项 ⚠️ warning（入口/shift/fee/stoploss/主循环/模拟盘）。这些 warning 是合理的吗？验证规则需要怎么调整？
11. 从工程方法论角度，这套"SOP + 验证脚本 + 多模型评审"的蓝图提取体系，你怎么评价？它能支撑到 50 个蓝图的规模吗？

### Part 4：评分与改进

12. 给这份蓝图打分：

| 维度 | 得分(0-100) | 理由 |
|------|------------|------|
| 源码忠实度 | ? | |
| AI 消费品质量 | ? | |
| 架构抽象质量 | ? | |

13. 这份蓝图最需要改进的 3 点是什么？
14. 三份蓝图汇总来看，蓝图提取流水线最需要改进的 3 点是什么？

## 输出格式

按 Part 1-4 结构回答，每题给出具体判断。Part 4 评分用表格。
```

---

## 使用说明

1. 分别发给 Claude、GPT-4o、Gemini 2.5 Pro、Grok
2. 回复保存到：
   - `docs/research/judgment-system/blueprint-vnpy-review-claude.md`
   - `docs/research/judgment-system/blueprint-vnpy-review-gpt.md`
   - `docs/research/judgment-system/blueprint-vnpy-review-gemini.md`
   - `docs/research/judgment-system/blueprint-vnpy-review-grok.md`
3. 重点关注 Part 2（三项目对比）和 Part 3（流水线成熟度）
