# 约束质量评审提示词（第二轮）

> 请将此���示词发送给 Claude / GPT / Gemini，对约束样本进行独立质量评审。
> 这是第二轮抽样，与第一轮不同的 5 条约束。

---

## 背景

我们正在构建一个 AI 知识锻造系统（Doramagic），从开源项目中系统性提取专家知识。知识架构是 **Blueprint（蓝图）+ Constraint（约束）** 两层模型：

- **蓝图**：描述一个系统的架构结构（阶段、数据���、接口）
- **约束**：挂在蓝图上的规则和限制——"按这张蓝图建造时，哪些坑不能踩"

我们从 freqtrade��开源量化交易框架）的源码中提取了 165 条约束。第一轮评审（5 条样本）平均分 4.64/5，三方评审一致认为质量达到"可启动种子晶体编译"水平，但指出了三个改进方向：
1. when 条件视角混淆（运行时 vs 编码时）
2. 元数据分层不稳（constraint_kind / confidence / source_type）
3. 后果量化偏弱

本轮为第二轮独立抽样，检验问题是否系统性存在。

## 蓝图概要（finance-bp-001：freqtrade 向量化量化回测系统）

```
stages:
  [1] data_pipeline:        获取/缓存/校验 OHLCV 数据
  [2] strategy_engine:      用户策略逻辑（继承 IStrategy）
  [3] trade_loop:           信号执行 + 内嵌风控（shift(1) 延迟）
  [4] evaluation_reporting: 交易记录 → 绩效指标
edges:
  pairlist_to_data → data_to_strategy → strategy_to_trade → trade_to_eval
```

---

## 待评审的 5 条约束样本

### 样本 1: finance-C-108（operational_lesson / data_pipeline）

```
当: 数据加载后 DataFrame 为空时
必须: 记录 WARNING 日志并提示用户执行 'freqtrade download-data' 下载数据
否则: 空 DataFrame 传入策略将导致指标计算异常或策略无信号，用户无日志提示则无法定位问题
严重度: medium | 可信度: 0.94 (code_analysis)
证据: freqtrade/data/history/datahandlers/idatahandler.py:414-420 — if pairdf.empty: logger.warning('No history for...Use freqtrade download-data')
machine_checkable: True | promote_to_acceptance: False
挂载: stage=['data_pipeline']
```

### 样本 2: finance-C-102（architecture_guardrail / data_pipeline）

```
当: DataProvider.__cached_pairs 属性命名时
必须: 使用双下划线前缀(__cached_pairs)触发 Python name mangling，禁止策略代码直接访问缓存
否则: 策略直接修改缓存将绕过 copy() 保护和 anti-lookahead 机制，导致数据污染和未来数据泄露
严重度: high | 可信度: 0.94 (code_analysis)
证据: freqtrade/data/dataprovider.py:51 — self.__cached_pairs; dataprovider.py:88-89 — _set_cached_df 注释: 'Using private method as this should never be used by a user'
machine_checkable: False | promote_to_acceptance: False
挂载: stage=['data_pipeline']
```

### 样本 3: finance-C-054（domain_rule / trade_loop）

```
当: 自定义出场价（custom_exit_price）返回的价格
必须: 将自定义出场价钳制在 K 线范围内——做多取 max(close_rate, row[LOW_IDX])，做空取 min(close_rate, row[HIGH_IDX])
否则: 不钳制会产生低于 LOW（做多）或高于 HIGH（做空）的出场价，回测收益失真
严重度: high | 可信度: 0.96 (code_analysis)
证据: backtesting.py:854-857 — if trade.is_short: close_rate = min(close_rate, row[HIGH_IDX]) else: close_rate = max(close_rate, row[LOW_IDX])
machine_checkable: True | promote_to_acceptance: False
挂载: stage=['trade_loop']
```

### 样本 4: finance-C-158（architecture_guardrail / global）

```
当: User writes a strategy using populate_indicators()
必须: Only use populate_indicators as the @abstractmethod (mandatory override). populate_entry_trend and populate_exit_trend are non-abstract with defaults delegating to deprecated buy/sell methods.
否则: Failing to implement populate_indicators raises TypeError at class instantiation; incorrectly assuming entry/exit methods are abstract leads to silent no-op strategies that never generate signals
严重度: high | 可信度: 0.98 (code_analysis)
证据: interface.py:228-273 — only populate_indicators has @abstractmethod; populate_entry_trend:247 delegates to populate_buy_trend; populate_exit_trend:266 delegates to populate_sell_trend
machine_checkable: True | promote_to_acceptance: True
挂载: global
```

### 样本 5: finance-C-048（architecture_guardrail / trade_loop）

```
当: 回测结束后仍有未平仓交易
必须: 以最后一根 K 线的 open 价强制平仓（FORCE_EXIT），并设置 exit_reason = 'force_exit'
否则: 不处理未平仓交易会导致资金统计不完整，回测最终余额与交易记录不一致
严重度: high | 可信度: 0.97 (code_analysis)
证据: backtesting.py:1228-1250 — handle_left_open 方法以 exit_row[OPEN_IDX] 价格和 ExitType.FORCE_EXIT 强制平仓
machine_checkable: True | promote_to_acceptance: False
挂载: stage=['trade_loop']
```

---

## 评审要求

请对每条约束从以下 6 个维度打分（1-5 分），并给出总体评价：

### 评审维度

| 维度 | 1 分 | 3 分 | 5 分 |
|------|------|------|------|
| **正确性** | 规则描述有事实错误 | 基本正确但有模糊之处 | 完全准确，与源码行为一致 |
| **原子性** | 包含多个独立规则 | 可拆但勉强可接受 | 严格一条一规则 |
| **可执行性** | action 模糊不可操作 | 方向明确但缺细节 | 读完就知道怎么做 |
| **后果量化** | 后果描述空泛 | 有方向但不具体 | 量化或有具体失败现象 |
| **证据质量** | 无证据或编造 | 有方向但定位模糊 | 精确到文件:行号 |
| **元数据准确性** | kind/severity/scope 明显错误 | 基本合理 | 所有元数据精准匹配 |

### 输出格式

```
## 样本 N: finance-C-XXX

| 维度 | 分数 | 说明 |
|------|------|------|
| 正确性 | X/5 | ... |
| 原子性 | X/5 | ... |
| 可执行性 | X/5 | ... |
| 后果量化 | X/5 | ... |
| 证据质量 | X/5 | ... |
| 元数据准确性 | X/5 | ... |
| **平均** | X.X/5 | |

评语: ...
```

### 额外问题

在评审完 5 条样本后，请回答：

1. **与第一轮对比**：本轮样本是否出现了第一���指出的同类问题（when 视角混淆、元数据分层、后果量化）？如果出现，严重程度是上升、持平还是下降？
2. **整体质量判断**：基于两轮共 10 条样本，这批约束库是否达到"可用于种子晶体编译"的水平？
3. **新发现的问题**：本轮是否发现了第一轮未提及的新问题？

请用中文回答。
