# 蓝图升级：区分技术架构与业务决策

> 日期：2026-04-06
> 来源：v9 晶体测试 → 业务逻辑缺失发现 → zvt 提取实验 → 三方挑战评审
> 状态：待设计

---

## 1. 问题

蓝图提取 SOP v2.2 用"技术架构"视角读代码，提取了框架的组件、接口、数据流。但同一段代码中隐含的"业务决策"被当成技术实现一笔带过。

示例（bp-009 / zvt）：

| 蓝图当前写法 | 写在哪里 | 实际是什么 |
|------------|---------|----------|
| "Trader.run() 先执行卖出再执行买入" | design_decisions | **业务决策**：防止资金不足导致买入失败 |
| "T+1 执行延迟" | design_decisions | **业务规则**：A 股 T+1 交割制度 |
| "默认止损 -30%、止盈 +300%" | pseudocode_example 默认参数 | **业务假设**：风险收益不对称的经验值 |
| "turnover_rate 是一等字段" | schema 设计 | **领域知识**：换手率是 A 股核心量价指标 |
| "仓位分三档 0.2/0.5/1.0" | pseudocode_example | **业务策略**：渐进式建仓的风险控制 |

这些信息已经在蓝图里了，但没有被识别和标注为"业务决策"。

---

## 2. 根因

SOP v2.2 步骤 2a 的 8 项任务全部是技术视角：

1. 入口调用链
2. 子包识别
3. ABC/Protocol 抽象方法
4. DataFrame 数据模型
5. 主循环执行顺序
6. 风控位置
7. 辅助子系统
8. @abstractmethod 完整扫描

**没有一项要求区分"这是技术选择还是业务决策"。**

---

## 3. 升级方向

### 3.1 SOP 改进：增加业务决策审视维度

在 SOP 步骤 2a 完成后（已提取技术架构），新增步骤：

**步骤 2d：业务决策标注（新增）**

对已提取的每个 `design_decision`、`default parameter`、`schema field`，追问：

> "这是纯技术选择（换一种实现方式结果一样），还是领域业务决策（换了就改变了投资/分析行为）？"

判断准则：
- **技术选择**：用 Bcolz 还是 Parquet 存储 → 换了存储格式，投资结果不变
- **业务决策**：先卖后买 vs 先买后卖 → 换了顺序，资金管理行为改变
- **业务假设**：止损 -30% → 换了阈值，策略风险特征改变
- **领域知识**：turnover_rate 是一等字段 → 这体现了 A 股市场的领域认知

### 3.2 蓝图 Schema 改进：标注业务决策

两种可能方案（待定）：

**方案 A：在 design_decisions 中加标签**

```yaml
design_decisions:
  - text: "Trader.run() 先执行卖出再执行买入"
    type: business_decision  # technical | business_decision | domain_knowledge
    rationale: "防止资金不足导致买入失败"

  - text: "DataPortal 是数据统一入口"
    type: technical
```

**方案 B：独立段落**

```yaml
# 现有
design_decisions:
  - "DataPortal 是数据统一入口"
  - "Bcolz 列式存储"

# 新增
business_decisions:
  - decision: "先卖后买"
    rationale: "防止资金不足"
    impact: "改变执行顺序会影响资金利用率"

  - decision: "默认止损 -30%"
    rationale: "风险收益不对称经验值"
    impact: "改变阈值直接改变策略风险特征"
```

### 3.3 缺失内容新增：业务用例

蓝图中完全没有的内容（来自 examples/notebooks），需要新增字段：

```yaml
# 新增
known_use_cases:
  - name: "MACD 日线金叉交易策略"
    source: "examples/trader/macd_day_trader.py"
    business_problem: "通过 MACD 技术指标识别 A 股趋势转折买入点"
    key_parameters:
      - lookback_window: 50
      - profit_threshold: [3, -0.3]

  - name: "多因子基本面选股"
    source: "examples/factors/fundamental_selector.py"
    business_problem: "从全 A 股筛选财务健康的核心资产"
    key_parameters:
      - window: 1095d
      - count: 8
```

### 3.4 隐式业务逻辑的提取来源

三方评审一致指出需要读代码才能发现隐式业务逻辑，关键文件：

| 文件类型 | 隐藏的业务逻辑 | 提取方法 |
|---------|-------------|---------|
| 基类（trader.py, factor.py） | 默认行为、执行顺序、生命周期 | 审视每个默认值和方法顺序 |
| 模拟账户（sim_account.py） | 佣金模型、滑点、资金管理 | 审视默认参数 |
| Schema 定义 | 一等字段选择、数据组织方式 | 审视为什么是这些字段 |
| 默认参数 | 止盈止损、窗口期、阈值 | 追问"为什么是这个值" |

**核心方法：不需要重新读代码，而是用业务决策视角重新审视蓝图提取时已经读过的代码。**

---

## 4. 三方评审的其他改进建议（记录待评估）

| 建议 | 来源 | 是否与蓝图升级相关 |
|------|------|-----------------|
| 业务逻辑定义扩展（加入经济假设、决策策略、风险管理） | 三方共识 | 是，影响标注维度 |
| 粒度分 4 层（Primitive → Method → Strategy → Research） | GPT | 是，影响 known_use_cases 的粒度 |
| 区分 Correctness Validation 和 Business Validation | 三方共识 | 是，影响 acceptance_hints |
| 负面业务逻辑（框架不支持什么及为什么） | Grok/GPT | 是，可加入 not_suitable_for 的业务理由 |
| 卡片增加 assumptions / applicability / regime_sensitivity | 三方共识 | 部分相关，影响 business_decisions 的字段 |

---

## 5. 下一步

1. **确认蓝图 Schema 改进方案**（方案 A 标签 vs 方案 B 独立段落）
2. **拿 bp-009（zvt）做一次示范升级**——标注现有 design_decisions 中的业务决策
3. **更新 SOP**——新增步骤 2d（业务决策审视）
4. **评估是否仍需独立 Pattern 层**——蓝图升级后，剩余的 examples 级业务逻辑用 known_use_cases 是否够用

---

*记录文档 v1.0 | 2026-04-06 | 基于 zvt 提取实验 + Grok/Gemini/GPT 三方挑战评审*
