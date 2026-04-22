# 约束质量评审提示词

> 请将此提示词发送给 Claude / GPT / Gemini，对约束样本进行独立质量评审。

---

## 背景

我们正在构建一个 AI 知识锻造系统（Doramagic），从开源项目中系统性提取专家知识。知识架构是 **Blueprint（蓝图）+ Constraint（约束）** 两层模型：

- **蓝图**：描述一个系统的架构结构（阶段、数据流、接口）
- **约束**：挂在蓝图上的规则和限制——"按这张蓝图建造时，哪些坑不能踩"

我们刚完成了 freqtrade（开源量化交易框架）的约束采集，从源码中提取了 165 条约束。现在需要评审约束的质量。

## 约束的核心结构

每条约束是一个三元组：**当[条件]时，必须/禁止[行为]，否则[后果]**

完整字段包括：
- `core.when`: 触发条件
- `core.modality`: must / must_not / should / should_not
- `core.action`: 具体行为
- `core.consequence`: 违反后果（kind + description）
- `constraint_kind`: domain_rule / resource_boundary / operational_lesson / architecture_guardrail / claim_boundary
- `applies_to`: 挂载点（global / stage / edge + 具体 ID）
- `confidence`: 可信度（source_type + score + evidence_refs）
- `severity`: fatal / high / medium / low
- `machine_checkable`: 是否可自动化验证
- `promote_to_acceptance`: 是否提升为验收标准

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

### 样本 1: finance-C-164（claim_boundary / global）

```
当: 向用户说明系统能力边界时
必须不: 声称系统支持纯基本面因子研究（无需交易执行）。系统设计为交易执行管线（data→strategy→trade→evaluate），纯因子研究不在其范围内。
否则: 用户尝试纯因子研究时会发现系统的交易中心架构（强制止损、ROI、订单执行）增加了不必要的复杂性
严重度: medium | 可信度: 0.94 (expert_reasoning)
证据: 蓝图 applicability.not_suitable_for[1]: 'pure fundamental factor research'
```

### 样本 2: finance-C-029（architecture_guardrail / strategy_engine）

```
当: advise_entry 被框架调用时
必须不: 在策略子类中重写 advise_entry / advise_exit / advise_indicators 方法
否则: 这三个方法是框架内部编排方法（advise_indicators 负责 @informative 合并 + 调用 populate_indicators），重写会绕过框架的信息合并和校验逻辑
严重度: high | 可信度: 0.9 (code_analysis)
证据: freqtrade/strategy/interface.py:1795-1798 注释 'This method should not be overridden'
```

### 样本 3: finance-C-007（domain_rule / strategy_engine）

```
当: 策略计算指标或信号时
必须不: 使用未来数据（如 shift(-N)、全局 min/max/mean、未经 shift 的 rolling 窗口包含未来行）
否则: 引入 look-ahead bias，回测结果虚高，实盘时策略表现大幅下降，造成资金亏损
严重度: fatal | 可信度: 0.95 (expert_reasoning)
证据: interface.py:229 populate_indicators 接收完整 DF；蓝图 acceptance_hints 明确禁止
promote_to_acceptance: true
```

### 样本 4: finance-C-071（architecture_guardrail / trade_loop）

```
当: 回测中对同一 Trade 重复提交相同参数的订单（price + side + amount 完全一致）
必须: 跳过重复订单，保留已存在的订单
否则: 重复下单会导致双倍仓位或双倍出场，回测结果失真
严重度: medium | 可信度: 0.94 (code_analysis)
证据: backtesting.py:1309-1326 handle_similar_order
machine_checkable: true
```

### 样本 5: finance-C-063（domain_rule / trade_loop）

```
当: 止损价经过精度处理
必须: 做多时向上取整（ROUND_UP），做空时向下取整（ROUND_DOWN）
否则: 做多向下取整会使止损触发更容易（提前止损），做空向上取整同理，导致非预期亏损
严重度: medium | 可信度: 0.95 (code_analysis)
证据: trade_model.py:839-844 price_to_precision(new_loss, ..., rounding_mode=ROUND_DOWN if self.is_short else ROUND_UP)
machine_checkable: true
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

---
```

### 额外问题

在评审完 5 条样本后，请回答：

1. **整体质量判断**：这批约束的质量是否达到"可用于种子晶体编译"的水平？（是/否/需改进）
2. **最大风险**：你看到的最大质量风险是什么？
3. **改进建议**：如果只能改一件事来提升约束质量，你会改什么？

请用中文回答。
