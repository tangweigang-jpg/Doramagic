# Blueprint V3 四方评审 Prompt

> 分别发给 Claude / GPT / Gemini / Grok
> 日期：2026-04-04
> 目的：评估 V3 是否修正了 V2 的所有错误，以及流水线改进是否有效

---

## 提示词

```
你是一位资深量化系统架构师 + AI 知识工程专家。

这是一份从 freqtrade 源码中提取的架构蓝图的**第三版（V3）**。V2 曾被四方评审发现 3 项事实性错误：
1. 信号执行时机搞反（写成"同根 K 线执行"，实际源码 shift(1) 延迟一根）
2. DataFrame 结构错误（写成 DatetimeIndex，实际 date 是普通列）
3. 抽象方法数量错误（写成三个，实际只有 populate_indicators 一个）

V3 通过改进提取流水线（新增 10 项 grep 自动验证）修正了这些错误。请评审 V3 是否真正修复了问题，以及是否引入了新问题。

## V3 蓝图（完整）

```yaml
id: finance-bp-001
name: 量化回测系统（向量化策略回测）
version: "3.0.0"

source:
  projects: [freqtrade/freqtrade]
  extraction_method: semi_auto
  confidence: 0.92
  evidence:
    entry_point: freqtrade/main.py:31-52
    core_orchestrator: freqtrade/freqtradebot.py:247-301
    strategy_interface: freqtrade/strategy/interface.py:67-272
    backtest_engine: freqtrade/optimize/backtesting.py:504-1742
    trade_model: freqtrade/persistence/trade_model.py:381+
    signal_shift: freqtrade/optimize/backtesting.py:504-512
    dataframe_structure: freqtrade/data/converter/converter.py:46
    abstractmethod: freqtrade/strategy/interface.py:227

applicability:
  domain: finance
  task_type: quantitative_backtesting
  description: >
    向量化策略回测系统。用户继承策略基类定义指标和信号，
    系统负责数据管理、回测模拟、风控执行、绩效评估。
    同一套策略代码可在回测/dry-run/实盘运行，但执行语义有显著差异。
  prerequisites: [历史行情数据源, Python 3.10+]
  not_suitable_for:
    - 高频交易（< 1秒）
    - 纯基本面因子研究
    - 逐笔订单簿仿真
    - T+1 市场（如 A 股）需额外适配

execution_paradigm:
  backtest: batch_pipeline
  dry_run: polling_event_loop
  live: polling_event_loop

# ── 4 个阶段 + 可选扩展 ──

stages:

  - id: data_pipeline
    name: 数据管道
    order: 1
    responsibility: 获取、缓存、校验 OHLCV 数据。前置依赖 PairListManager。
    interface:
      inputs:
        - name: pair_whitelist
          description: PairListManager 责任链过滤后的交易对列表
        - name: timeframe_config
          description: "{timeframe: str, informative_pairs: list}"
      outputs:
        - name: ohlcv_dataframe
          description: >
            DataFrame(columns=["date","open","high","low","close","volume"])
            date 是普通列（非索引），datetime64[ns, UTC]，升序，无缺失
          evidence: "converter.py:46 df['date']=...; converter.py:82 groupby(as_index=False)"
      required_methods:
        - "refresh(pairlist, informative_pairs) — DataProvider.refresh()"
        - "get_pair_dataframe(pair, timeframe)"
        - "get_analyzed_dataframe(pair, timeframe)"
    replaceable_points:
      - "data_storage_format: feather(默认) / json / parquet — IDataHandler 抽象"
      - "market_data_source: ccxt(默认/加密) / yfinance(股票) / akshare(A股)"
      - "pairlist_manager: StaticPairList / VolumePairList — 责任链模式"
    design_decisions:
      - "DataProvider 是数据统一入口，策略不直接调 exchange"
      - "内存缓存(__cached_pairs) + 本地文件(IDataHandler) 双层"
      - "PairListManager 责任链在 data_pipeline 之前运行"

  - id: strategy_engine
    name: 策略引擎
    order: 2
    responsibility: 用户继承 IStrategy，必须实现 populate_indicators（唯一抽象方法）。
    interface:
      inputs:
        - name: ohlcv_dataframe
          description: "DataFrame + metadata({pair: str})"
      outputs:
        - name: signal_dataframe
          description: "原有列 + indicators + enter_long:0|1 + exit_long:0|1 + enter_short:0|1 + exit_short:0|1 + enter_tag + exit_tag"
    required_methods:
      - "populate_indicators(df, metadata) → DataFrame 【@abstractmethod — 唯一抽象方法，interface.py:227】"
      - "populate_entry_trend(df, metadata) → DataFrame 【非抽象，默认委派旧方法，interface.py:246】"
      - "populate_exit_trend(df, metadata) → DataFrame 【非抽象，默认委派旧方法，interface.py:265】"
      - "14+ 可选回调: bot_loop_start, confirm_trade_entry/exit, custom_stoploss, custom_exit, adjust_trade_position, feature_engineering_*(FreqAI)..."
    design_decisions:
      - "只有 populate_indicators 有 @abstractmethod（grep 验证：interface.py:227 唯一一处）"
      - "策略插件模式，信号是 DataFrame 列标记(0/1 int)"
      - "stoploss 和 timeframe 无默认值，必须显式设置"
      - "FreqAI 延迟加载，未启用时 DummyClass（interface.py:208）"

  - id: trade_loop
    name: 交易循环（含风控）
    order: 3
    responsibility: >
      执行交易 + 内嵌风控。回测：信号 shift(1) 后在下一根 K 线 open 价执行。
      实盘：polling loop，先出场再入场。风控嵌入循环，非独立阶段。
    interface:
      outputs:
        - name: trade_list
          description: "list[LocalTrade] — 40+ 字段，含 orders:list[Order], exit_reason, enter_tag"
    key_behaviors:
      - behavior: "回测信号延迟执行"
        description: "信号列 shift(1)：candle N 信号 → candle N+1 open 价执行"
        evidence: "backtesting.py:504-512 — .shift(1) + 注释 'To avoid using data from future'"
      - behavior: "实盘主循环顺序"
        description: "刷新→分析→管订单→先出场→调仓→再入场→RPC"
        evidence: "freqtradebot.py:255-301"
      - behavior: "费率取最坏情况"
        description: "配置优先，否则取 exchange taker/maker 最高费率"
        evidence: "backtesting.py:241-254 set_fee()"
      - behavior: "追踪止损方向"
        description: "做多只上移（higher_stop and not is_short），做空只下移（lower_stop and is_short）"
        evidence: "trade_model.py:866-867"
      - behavior: "Protections 交易对锁定"
        description: "连续亏损后自动冷却锁定交易对"
        evidence: "plugins/protectionmanager.py"
    replaceable_points:
      - "execution_mode: backtest_engine / dry_run / live_exchange"

  - id: evaluation_reporting
    name: 绩效评估与报告
    order: 4
    responsibility: 从交易记录计算绩效指标（Sharpe/Sortino/Calmar/drawdown/per-pair）。
    evidence: "optimize/optimize_reports.py"

optional_extensions:
  - id: hyperopt
    name: 参数优化
    description: "Optuna + joblib 并行，每次迭代调用 Backtesting.backtest()"
    evidence: "optimize/hyperopt/"
  - id: freqai
    name: 机器学习集成
    description: "延迟加载 ML 子系统，通过 feature_engineering_* 回调集成"
    evidence: "freqai/ + strategy/interface.py:179-186"
  - id: rpc_system
    name: 远程控制与通知
    description: "RPCManager Facade → Telegram/REST/Webhook/Discord"
    evidence: "rpc/ + freqtradebot.py:122,300"

data_flow:
  - {from: "(PairListManager)", to: data_pipeline, data: pair_whitelist, type: data_flow}
  - {from: data_pipeline, to: strategy_engine, data: ohlcv_dataframe, type: data_flow}
  - {from: strategy_engine, to: trade_loop, data: signal_dataframe, type: data_flow, note: "回测模式信号经 shift(1)"}
  - {from: trade_loop, to: evaluation_reporting, data: trade_list, type: data_flow}

global_contracts:
  - contract: "回测信号延迟一根 K 线：candle N 信号 → candle N+1 open 价执行"
    evidence: "backtesting.py:504-512 shift(1)"
  - contract: "实盘中信号在下一个 process() 循环执行"
    evidence: "freqtradebot.py:275→287→297"
  - contract: "每笔 Trade 含完整 Order 链"
    evidence: "trade_model.py:399"
  - contract: "exit_reason 非空：roi/stop_loss/trailing/exit_signal/force_exit/custom_exit"
  - contract: "fee 取配置值或交易所最坏情况"
    evidence: "backtesting.py:241-254"
  - contract: "dry_run 用模拟钱包，只读 API"
    evidence: "freqtradebot.py:324,444"
  - contract: "DataFrame date 是普通列（非索引），datetime64[ns,UTC]"
    evidence: "converter.py:46,82"
```

## 评审要求

### Part 1：V2 错误修正验证（最重要）

请逐一验证 V2 的 3 项事实性错误是否在 V3 中被正确修正：

1. **信号执行时机**：V2 写"同根 K 线执行"，V3 改为"shift(1)，N+1 K 线 open 价执行"。V3 的描述是否正确？
2. **DataFrame 结构**：V2 写"index=DatetimeIndex(tz=UTC)"，V3 改为"date 是普通列"。V3 的描述是否正确？
3. **抽象方法数量**：V2 写"三个抽象方法"，V3 改为"只有 populate_indicators 是 @abstractmethod"。V3 的描述是否正确？

如果你熟悉 freqtrade 源码，请验证。如果不熟悉，请基于蓝图中引用的 evidence 行号做合理性判断。

### Part 2：V3 新引入的问题

4. V3 把 trade_execution 和 risk_management 合并为 trade_loop——这个合并是否合理？有没有丢失信息？
5. V3 新增了 optional_extensions（Hyperopt/FreqAI/RPC）——描述是否准确？是否遗漏了其他重要扩展？
6. V3 的 execution_paradigm 分成了 backtest/dry_run/live 三种模式——这个分法是否准确？
7. V3 在 not_suitable_for 中加了"T+1 市场需额外适配"——这条是否足够？还需要补充什么？

### Part 3：整体质量

8. 与 V2 相比，V3 的源码忠实度提升了多少？（给出 V2 和 V3 的分数对比）
9. V3 作为 AI 消费品，宿主 AI 读完后能否构建出专家级 skill？还差什么？
10. V3 最需要改进的 3 点是什么？

### Part 4：流水线改进评价

11. V3 声称通过"10 项 grep 自动验证"修正了 V2 的错误。你认为这种自动验证方法有效吗？还需要哪些验证？
12. 从 V2 到 V3 的改进过程（粗提取 → 自动验证 → 修正 → 组装），作为一种蓝图提取流水线，你怎么评价？

## 输出格式

### V2 错误修正验证
| 错误 | V3 修正 | 判定(✅/❌/⚠️) | 说明 |
|------|--------|---------------|------|

### V3 评分
| 维度 | V2 得分 | V3 得分 | 变化 |
|------|--------|--------|------|
| 源码忠实度 | ? | ? | +? |
| AI 消费品质量 | ? | ? | +? |
| 架构抽象质量 | ? | ? | +? |
| 缺失与改进 | ? | ? | +? |

### V3 最需要改进的 3 点
1. ...
2. ...
3. ...

### 流水线评价
（对提取流水线方法论的评价，而非蓝图本身）
```

---

## 使用说明

1. 将上面 ``` 中的提示词分别发给 Claude、GPT-4o、Gemini 2.5 Pro、Grok
2. 回复保存到：
   - `docs/research/judgment-system/blueprint-v3-review-claude.md`
   - `docs/research/judgment-system/blueprint-v3-review-gpt.md`
   - `docs/research/judgment-system/blueprint-v3-review-gemini.md`
   - `docs/research/judgment-system/blueprint-v3-review-grok.md`
3. 重点关注 Part 1（V2 错误是否真正修正）和 Part 4（流水线方法论评价）
