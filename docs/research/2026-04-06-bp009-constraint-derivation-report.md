# bp-009 业务约束派生报告

**派生时间**: 2026-04-06  
**派生规范**: 约束 SOP v1.3 Step 2.4  
**蓝图**: finance-bp-009（模块化量化框架 zvt Schema 驱动 + 向量化模式）  
**输出文件**: `knowledge/constraints/drafts/finance-bp-009-derived-v1.3.json`

---

## 一、总计派生数量

**共派生 22 条约束**（SOP 预估 25~31 条，本次实际因去重略低）

---

## 二、按 business_decision type 分布

| type | 原始条数 | 派生约束数 | 备注 |
|------|---------|----------|------|
| RC（监管规则） | 4 条 | 3 条 | T+1 持仓约束已由 C-432/C-442 覆盖，跳过；A 股印花税 1 条，涨跌停 missing 双联 2 条 |
| B（业务决策，选择性） | 5 条（可选范围） | 4 条 | 先卖后买（C-433 已覆盖跳过）；信号延迟（C-432 已覆盖跳过）；filter_result 三值逻辑、rich_mode 双层默认值、fill_gap 停牌场景各 1 条 |
| BA（业务假设） | 6 条（可选范围） | 5 条 | sell_cost 旧费率、buy_cost 偏估、滑点固定值、收盘价估值各 1 条，仓位控制（C-434 已覆盖跳过），止损止盈（C-435 已覆盖跳过） |
| missing（已知缺陷，双联） | 7 条 gap | 14 条 | 涨跌停(2) + 停牌(2) + ST(2) + 除权除息(2) + 成分股历史时点(2) + 新股次新股(2) + 执行可行性(2) |
| DK（领域知识） | 2 条 | 0 条 | 不影响交易合法性/可执行性，跳过 |
| T / T+B / T+BA | 5 条 | 0 条 | 纯技术选择，跳过 |

---

## 三、按 constraint_kind 分布

| constraint_kind | 数量 | 占比 |
|----------------|------|------|
| claim_boundary | 7 条 | 32% |
| domain_rule | 7 条 | 32% |
| operational_lesson | 8 条 | 36% |
| architecture_guardrail | 0 条 | — |
| resource_boundary | 0 条 | — |

---

## 四、与现有 56 条约束的去重情况

### 跳过（已覆盖）

| 跳过原因 | 现有约束 | 蓝图条目 |
|---------|---------|---------|
| T+1 持仓约束已覆盖 | C-432（fatal）、C-442（high） | T+1 持仓约束（RC）+ 主循环信号延迟（B） |
| 先卖后买已覆盖 | C-433（high） | 先卖后买（B） |
| 仓位控制三档已覆盖 | C-434（medium） | 仓位控制三档（BA） |
| 止损止盈阈值已覆盖 | C-435（medium） | 止损 -30% + 止盈 +300%（BA） |

### 部分覆盖但新约束补充了不同角度

| 现有约束 | 新约束补充 |
|---------|-----------|
| C-426（filter_result 格式要求 bool/score） | 新增 NaN 三值逻辑 AND 传播行为的约束 |
| C-439（资金扣减公式） | 新增 sell_cost 旧费率失真和 buy_cost 成本偏估约束 |
| C-440（rich_mode=False 异常处理） | 新增双层默认值相反陷阱的约束 |

---

## 五、每条约束一行摘要

### RC 类派生（3 条）

| # | ID草稿 | severity | constraint_kind | 一行摘要 |
|---|--------|---------|----------------|---------|
| 1 | — | high | domain_rule | 实现 A 股卖出成本时，印花税必须使用 0.05%（2023-08-28 新税率），不用旧税率 |
| 2 | — | fatal | claim_boundary | 禁止假设 zvt 已处理涨跌停——涨停买单会被视为全额成交 |
| 3 | — | fatal | domain_rule | 实现 A 股回测时必须在下单前过滤涨停股（不发买单）和跌停股（不发卖单） |

### B 类派生（4 条）

| # | ID草稿 | severity | constraint_kind | 一行摘要 |
|---|--------|---------|----------------|---------|
| 4 | — | high | domain_rule | filter_result 为三值逻辑，NaN 表示无意见而非 False，AND 合并时必须明确处理 NaN 传播 |
| 5 | — | high | domain_rule | 实例化 Trader 时必须显式传 rich_mode=False，不能依赖 SimAccountService 的 True 默认值 |
| 6 | — | high | operational_lesson | fill_gap() 填充停牌期间应添加停牌标记，不能直接继承上一期信号 |
| 7 | — | high | claim_boundary | 禁止假设 zvt 已处理停牌状态——停牌期间 fill_gap 会继续传递买入信号 |

### BA 类派生（5 条）

| # | ID草稿 | severity | constraint_kind | 一行摘要 |
|---|--------|---------|----------------|---------|
| 8 | — | high | operational_lesson | sell_cost=0.001 使用旧费率，应验证并调整为当前综合成本 0.0007~0.0012 |
| 9 | — | medium | operational_lesson | buy_cost=0.001 对机构偏高 10~30 倍，应根据实际账户类型调整 |
| 10 | — | high | operational_lesson | 固定滑点 0.1% 不适用大资金/小盘策略，应改为基于成交量的动态滑点模型 |
| 11 | — | medium | operational_lesson | 收盘价估值在跌停时虚高，应区分账面估值与可变现价值 |
| 12 | — | high | domain_rule | 停牌处理：必须在选股池筛选中排除停牌标的，并对停牌期因子信号置 NaN |

### missing 双联约束（14 条）

| # | ID草稿 | severity | constraint_kind | 一行摘要 |
|---|--------|---------|----------------|---------|
| 13 | — | high | claim_boundary | 禁止假设 zvt 已处理停牌——框架无停牌标记和禁交逻辑 |
| 14 | — | high | domain_rule | 停牌处理 remedy：TargetSelector 必须过滤停牌标的，停牌期因子信号置 NaN |
| 15 | — | high | claim_boundary | 禁止假设 zvt TargetSelector 已过滤 ST/*ST——框架 Entity 模型无 ST 字段 |
| 16 | — | high | domain_rule | ST 过滤 remedy：必须在 on_factor_targets_filtered() 中通过 name 字段显式过滤 ST 股 |
| 17 | — | fatal | claim_boundary | 禁止假设 zvt 已处理除权除息——框架未实现分红再投资和送股持仓更新 |
| 18 | — | fatal | domain_rule | 除权除息 remedy：中长期回测必须使用复权数据，显式处理持仓数量变化和现金分红入账 |
| 19 | — | high | claim_boundary | 禁止假设 zvt Entity 支持历史时点成分股查询——point-in-time 功能未经验证 |
| 20 | — | medium | operational_lesson | 成分股历史时点 remedy：使用外部数据源（AkShare/Wind）构建历史时点成分股宇宙 |
| 21 | — | medium | claim_boundary | 禁止假设 zvt 已过滤新股/次新股——list_date 字段存在但过滤逻辑需用户自行实现 |
| 22 | — | medium | operational_lesson | 新股过滤 remedy：通过 list_date 过滤上市不足 60 日标的，on_factor_targets_filtered() 中添加逻辑 |
| 23 | — | high | claim_boundary | 禁止假设 zvt SimAccount 已处理成交量限制和冲击成本——仅实现固定滑点，无成交量上限 |
| 24 | — | high | operational_lesson | 流动性 remedy：小盘/大资金策略必须添加成交量限制（不超过日成交量 5%~20%）和部分成交建模 |

> 注：编号 12 为 B 类衍生的停牌 domain_rule，同时也是 missing/停牌的 remedy 组成部分，统计时归入 B 类，不重复计入 missing 双联。

---

## 六、质量自检（SOP v1.3 提交前检查清单）

- [x] 所有 modality 值属于：must / must_not / should / should_not
- [x] 所有 constraint_kind 值属于：domain_rule / operational_lesson / claim_boundary
- [x] 所有 consequence_kind 值属于：bug / financial_loss / data_corruption / service_disruption / operational_failure / compliance
- [x] 所有 severity 值属于：fatal / high / medium / low
- [x] 所有 source_type = expert_reasoning，confidence_score = 0.7（符合 L6 规则）
- [x] 所有 consensus 值属于：strong
- [x] 所有 target_scope = stage
- [x] 所有 consequence_description ≥ 20 字且描述具体失败现象
- [x] 所有约束包含 derived_from 溯源字段（SOP v1.3 L20 要求）
- [x] 无重复派生已有 C-432/C-433/C-434/C-435/C-442 覆盖的约束

---

## 七、下一步建议

1. **入库**：运行 `scripts/ingest_constraints.py` 将 JSON 转换为 Constraint 对象，自动分配 ID
2. **关联关系**：为停牌相关约束添加 `relations: [{type: "supplements", target: "finance-C-432"}]`
3. **promote_to_acceptance 标记**：涨跌停（2条）、除权除息（2条）、ST（2条）共 6 条建议优先提升为 acceptance test
4. **freshness=volatile 约束**：印花税税率（C新1条）需要关注监管政策变化，设为 volatile
