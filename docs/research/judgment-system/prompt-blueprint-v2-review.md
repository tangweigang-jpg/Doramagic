# Blueprint v2 四方评审 Prompt

> 分别发给 Claude / GPT / Gemini / Grok
> 日期：2026-04-04

---

## 提示词

```
你是一位资深量化系统架构师 + AI 知识工程专家。请评审以下从开源项目源码中提取的"架构蓝图"。

## 背景

我们在构建一个叫 Doramagic 的系统——从开源项目的实际源码中提取架构知识，编译成"种子晶体"（AI 可消费的知识配方）。用户把晶体交给自己的 AI 工具（Claude Code / Cursor / ChatGPT 等），AI 按配方构建个性化 skill。

种子晶体 = 蓝图（架构结构） + 约束（规则和限制） + 验收标准 + 上下文获取指令

以下是我们从 freqtrade（GitHub 22K+ stars 的量化交易框架）源码中提取的第一份蓝图。提取方法是：克隆仓库 → 读核心入口和调用链 → 提炼阶段划分、接口契约、数据流、设计决策。

## 待评审的蓝图

```yaml
id: finance-bp-001
name: 量化回测系统（向量化策略回测）
version: "1.0.0"

source:
  projects:
    - freqtrade/freqtrade
  extraction_method: semi_auto
  confidence: 0.9
  evidence:
    entry_point: freqtrade/main.py:31-62
    core_orchestrator: freqtrade/freqtradebot.py:79-301
    strategy_interface: freqtrade/strategy/interface.py
    backtest_engine: freqtrade/optimize/backtesting.py
    trade_model: freqtrade/persistence/trade_model.py:381+

applicability:
  domain: finance
  task_type: quantitative_backtesting
  description: >
    向量化策略回测系统。用户通过继承策略基类定义指标和信号，
    系统负责数据管理、回测模拟、风控执行、绩效评估。
    同一套策略代码可在回测/模拟盘(dry-run)/实盘三种模式下运行。
  prerequisites:
    - 历史行情数据源（至少日线级别）
    - Python 3.10+
  not_suitable_for:
    - 高频交易（< 1 秒级别，需要订单簿仿真）
    - 纯基本面因子研究（无交易执行需求）
    - 需要逐笔撮合的精确滑点模拟

execution_paradigm: pipeline

# ── 5 个阶段 ──

stages:

  - id: data_pipeline
    name: 数据管道
    order: 1
    responsibility: >
      获取、缓存、校验 OHLCV 行情数据，提供统一的数据访问接口。不做任何分析计算。
    interface:
      inputs:
        - name: pair_config
          description: 交易对配置
          schema_hint: "{pairs: list[str], timeframe: str, timerange: str}"
      outputs:
        - name: ohlcv_dataframe
          description: 标准化 OHLCV DataFrame
          schema_hint: "DataFrame(columns=[open,high,low,close,volume], index=DatetimeIndex(tz=UTC))"
          constraints:
            - 时间索引 tz-aware UTC、升序、无缺失
      required_methods:
        - name: refresh
          description: 刷新交易对 K 线数据
          notes: "源码: DataProvider.refresh()"
        - name: get_pair_dataframe
          description: 获取 OHLCV 数据
          notes: "源码: DataProvider.get_pair_dataframe()"
        - name: get_analyzed_dataframe
          description: 获取经策略处理后的 DataFrame
          notes: "源码: DataProvider.get_analyzed_dataframe()"
    replaceable_points:
      - name: data_storage_format
        description: 本地存储格式
        options: [feather(默认/快速), json(可读/慢), parquet(压缩/跨系统)]
        selection_criteria: "源码: IDataHandler 抽象 → 三种实现"
      - name: market_data_source
        description: 行情数据来源
        options: [ccxt(加密货币/100+交易所), yfinance(股票/免费), akshare(A股)]
    design_decisions:
      - "DataProvider 是数据统一入口——策略只通过 dp 获取数据，不直接调 exchange"
      - "内存缓存 + 本地文件持久化双层架构"
      - "数据格式通过 IDataHandler 抽象解耦"
      - "辅助时间周期(informative_pairs)与主时间周期一起刷新"

  - id: strategy_engine
    name: 策略引擎
    order: 2
    responsibility: >
      用户定义的策略逻辑。继承 IStrategy 基类实现三个抽象方法。纯计算，无副作用。
    interface:
      inputs:
        - name: ohlcv_dataframe
          description: OHLCV DataFrame + metadata({pair: str})
      outputs:
        - name: signal_dataframe
          description: "DataFrame(原有列 + indicator列 + enter_long:0|1 + exit_long:0|1 + enter_short:0|1 + exit_short:0|1 + enter_tag + exit_tag)"
          constraints:
            - 信号列 int 0|1
            - 禁止使用未来数据
      required_methods:
        - name: populate_indicators(dataframe, metadata) -> DataFrame
          notes: "源码: IStrategy 抽象方法。接收完整 DF 一次性计算。INTERFACE_VERSION=3"
        - name: populate_entry_trend(dataframe, metadata) -> DataFrame
          notes: "源码: 设 enter_long=1 做多信号，enter_short=1 做空信号"
        - name: populate_exit_trend(dataframe, metadata) -> DataFrame
          notes: "源码: 设 exit_long=1 / exit_short=1"
      # 可选回调: bot_loop_start, confirm_trade_entry, confirm_trade_exit,
      #          custom_stoploss, custom_exit, adjust_trade_position
    design_decisions:
      - "策略是插件模式——用户继承 IStrategy 实现三个抽象方法"
      - "信号是 DataFrame 列标记（0/1 int）——向量化计算"
      - "startup_candle_count 机制确保指标预热"
      - "enter_tag/exit_tag 支持信号归因"
      - "process_only_new_candles=True 时只在新 K 线到来时重算"

  - id: trade_execution
    name: 回测与交易执行
    order: 3
    responsibility: >
      根据信号执行交易。回测模式逐 K 线模拟，实盘模式通过 exchange API 下单。
      维护账户状态（持仓、资金、订单）。
    interface:
      inputs:
        - name: signal_dataframe
      outputs:
        - name: trade_list
          description: "list[Trade] — 含 30+ 字段: id, pair, is_short, leverage, open_rate, close_rate, close_profit, fee_open, fee_close, stop_loss, exit_reason, enter_tag, orders:list[Order]..."
    design_decisions:
      - "回测用 DataFrame→list[tuple] 转换加速遍历（backtesting.py line 1704）"
      - "实盘主循环: 刷新数据→分析信号→先出场→再入场（freqtradebot.py process()）"
      - "Trade 和 Order 分离——一个 Trade 可有多个 Order（DCA/部分成交）"
      - "fee 从交易所获取实际费率最差情况"
      - "回测中订单在同根 K 线的 open 价执行（freqtrade 特有）"
      - "dry_run 使用模拟钱包，只调只读 API"

  - id: risk_management
    name: 风险管理
    order: 3  # 与 trade_execution 同 order：嵌入交易循环
    responsibility: >
      止损、追踪止损、仓位控制、交易对锁定。嵌入交易主循环实时执行。
      风控有覆盖策略信号的权限。
    interface:
      inputs:
        - name: "trade(current_rate, stop_loss, max_rate)"
        - name: "strategy_config(stoploss, trailing_stop, minimal_roi)"
      outputs:
        - name: "exit_decision(stop_loss | trailing_stop_loss | roi | none)"
    design_decisions:
      - "风控参数定义在策略类中，不是独立配置文件"
      - "追踪止损只上移不下移——adjust_stop_loss() 中 new_loss > trade.stop_loss"
      - "止损可在交易所端执行(stoploss_on_exchange)"
      - "custom_stoploss 回调允许动态止损"
      - "Protections 机制可锁定交易对——连续亏损后冷却"

  - id: evaluation_reporting
    name: 绩效评估与报告
    order: 4
    responsibility: 从交易记录计算绩效指标并生成报告。
    interface:
      inputs:
        - name: "trade_list + config"
      outputs:
        - name: "backtest_stats(total_trades, profit_factor, max_drawdown, sharpe, sortino, calmar, per_pair_stats, daily_stats)"

# ── 数据流 ──

data_flow:
  - {from: data_pipeline, to: strategy_engine, data: ohlcv_dataframe, type: data_flow}
  - {from: strategy_engine, to: trade_execution, data: signal_dataframe, type: data_flow}
  - {from: trade_execution, to: risk_management, data: trade_state, type: feedback_loop}
  - {from: risk_management, to: trade_execution, data: exit_decision, type: control_gate}
  - {from: trade_execution, to: evaluation_reporting, data: trade_list, type: data_flow}

# ── 全局约定 ──

global_contracts:
  - "信号在当前 K 线产生，回测中在同根 K 线 open 价执行（freqtrade 特有）"
  - "实盘中信号产生后在下一个 process() 循环执行"
  - "每笔 Trade 包含完整 Order 链（支持 DCA/部分成交审计）"
  - "exit_reason 必须非空：roi / stop_loss / trailing_stop_loss / exit_signal / force_exit / custom_exit"
  - "fee 取交易所实际费率的最差情况（taker fee）"
  - "干跑模式(dry_run)使用模拟钱包，只调只读 API"
```

## 评审要求

请从以下 4 个维度评审，每个维度给出 0-100 分并说明理由。

### A. 源码忠实度（这份蓝图是否准确反映了 freqtrade 的真实架构？）

1. 阶段划分是否与 freqtrade 的实际模块边界一致？有没有漏掉重要模块？
2. 接口契约（方法名、参数、返回值）是否与源码一致？有事实性错误吗？
3. 设计决策（design_decisions）是否真实反映了源码中的选择？有编造的吗？
4. 全局约定是否与 freqtrade 实际行为一致？特别是"同根 K 线 open 价执行"这条。
5. 如果你熟悉 freqtrade 源码，请指出蓝图中任何与源码不一致的地方。

### B. 作为 AI 消费品的质量（宿主 AI 读完蓝图能否构建出专家级 skill？）

6. 接口契约是否足够明确，让 AI 知道每个阶段该实现什么？
7. 数据流是否清晰到 AI 能正确连接各阶段？
8. 可替换点的描述是否足够让 AI 根据用户上下文做选择？
9. 伪代码示例（如果有的话）对 AI 理解架构有多大帮助？
10. 有什么信息是 AI 构建 skill 时需要但蓝图没提供的？

### C. 架构抽象质量（蓝图是否在"太具体"和"太抽象"之间找到了平衡？）

11. 蓝图是否过度绑定 freqtrade 的实现细节（如特定类名）？能否适配到非 freqtrade 的量化系统？
12. 蓝图是否过于抽象，丢失了关键的架构决策？
13. 如果用户做的是 A 股日线选股（不是加密货币），这份蓝图还能用多少？需要改什么？
14. execution_paradigm 标为 pipeline，但 freqtrade 实盘是 while-loop + 定时触发。这个简化合理吗？

### D. 缺失与改进（这份蓝图还差什么？）

15. 有没有 freqtrade 的关键架构特性被遗漏了？（如 FreqAI、Hyperopt、Telegram RPC 等）
16. 蓝图中的 5 个阶段，是否需要拆分或合并？
17. 如果让你改进这份蓝图，最优先改的 3 点是什么？
18. 这份蓝图的整体质量在你见过的架构文档中处于什么水平？

## 输出格式

请按以下格式输出：

### 评分
| 维度 | 得分(0-100) | 一句话理由 |
|------|------------|-----------|

### 详细评审
（按 A/B/C/D 四个维度逐题回答）

### 最优先改进的 3 点
1. ...
2. ...
3. ...
```

---

## 使用说明

1. 将上面 ``` 中的提示词分别发给 Claude、GPT-4o、Gemini 2.5 Pro、Grok
2. 回复保存到：
   - `docs/research/judgment-system/blueprint-v2-review-claude.md`
   - `docs/research/judgment-system/blueprint-v2-review-gpt.md`
   - `docs/research/judgment-system/blueprint-v2-review-gemini.md`
   - `docs/research/judgment-system/blueprint-v2-review-grok.md`
3. 四份到齐后做综合，决定是否需要修订蓝图后再进入约束采集和编译测试
