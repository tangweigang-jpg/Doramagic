# Blueprint + Constraint Schema 完整设计

> 版本：v0.1 (Draft for Review)
> 日期：2026-04-04
> 状态：待 GPT 技术评审

---

## 一、Blueprint Schema（蓝图）

### 设计原则

1. 语言无关：不包含可运行代码，用伪代码示例说明
2. 结构化：每个字段有明确类型，可被编译引擎程序化处理
3. 一个蓝图对应一种解法：同一任务可有多个蓝图

### 数据模型

```yaml
Blueprint:
  # ── 标识 ──
  id: string                    # 格式: {domain}-bp-{number}，如 "finance-bp-001"
  name: string                  # 人类可读名称，如 "事件驱动量化回测系统"
  version: string               # 语义化版本号，如 "1.0.0"
  
  # ── 来源 ──
  source:
    projects: list[string]      # 提炼自哪些项目，如 ["freqtrade/freqtrade", "stefan-jansen/zipline-reloaded"]
    extraction_method: enum     # manual / semi_auto / auto
    confidence: float           # 0.0-1.0，蓝图本身的可信度
  
  # ── 适用性 ──
  applicability:
    domain: string              # 所属领域，如 "finance"
    task_type: string           # 任务类型，如 "quantitative_backtesting"
    description: string         # 一句话描述解法特征，如 "事件驱动+策略插件+单交易所，适合中低频个人量化"
    prerequisites: list[string] # 使用此蓝图的前提条件，如 ["需要历史行情数据源", "Python 3.10+"]
    not_suitable_for: list[string]  # 明确不适用的场景，如 ["高频交易(< 1s)", "多交易所套利"]

  # ── 核心：阶段定义 ──
  stages: list[Stage]
  
  # ── 核心：数据流 ──
  data_flow: list[DataFlowEdge]
  
  # ── 核心：全局约定 ──
  global_contracts: list[string]  # 跨阶段的架构约定，如 ["所有金额使用 Decimal 类型", "所有时间戳 tz-aware UTC"]

  # ── 元数据 ──
  created_at: string
  updated_at: string
  tags: list[string]            # 检索标签，如 ["event-driven", "backtest", "single-exchange"]
```

### Stage（阶段）

```yaml
Stage:
  id: string                    # 阶段标识，如 "data_ingestion"
  name: string                  # 人类可读，如 "数据采集"
  order: int                    # 执行顺序（允许并行阶段共享同一 order 值）
  
  # ── 职责 ──
  responsibility: string        # 一句话说清职责，如 "获取和缓存行情数据，不做分析"
  
  # ── 接口契约 ──
  interface:
    inputs: list[DataContract]  # 输入契约
    outputs: list[DataContract] # 输出契约
    required_methods: list[MethodSignature]  # 必须实现的方法

  # ── 可替换点 ──
  replaceable_points: list[ReplaceablePoint]
  
  # ── 伪代码示例 ──
  pseudocode_example: string    # 说明这个阶段"长什么样"的伪代码（非可运行代码）
  
  # ── 关键设计决策 ──
  design_decisions: list[string]  # 如 ["本地缓存层必须存在", "策略是插件模式，用户自定义"]
```

### DataContract（数据契约）

```yaml
DataContract:
  name: string                  # 如 "ohlcv_dataframe"
  description: string           # 如 "带有 tz-aware datetime 索引的 OHLCV 数据"
  schema_hint: string           # 结构提示（语言无关），如 "columns: [open, high, low, close, volume], index: datetime(tz=UTC)"
  constraints: list[string]     # 数据级约束，如 ["不允许缺失值", "时间必须连续"]
```

### MethodSignature（方法签名）

```yaml
MethodSignature:
  name: string                  # 如 "fetch_ohlcv"
  description: string           # 如 "获取指定标的的 OHLCV 历史数据"
  parameters: list[string]      # 如 ["symbol: 标的代码", "timeframe: 时间周期", "start/end: 时间范围"]
  returns: string               # 如 "OHLCV DataFrame（符合 DataContract.ohlcv_dataframe）"
  notes: string | null          # 补充说明
```

### ReplaceablePoint（可替换点）

```yaml
ReplaceablePoint:
  name: string                  # 如 "market_data_provider"
  description: string           # 如 "行情数据来源，可替换为不同供应商"
  options: list[ResourceOption] # 可选资源
  default: string               # 默认推荐，如 "yfinance"
  selection_criteria: string    # 选择依据，如 "根据数据频率需求和预算选择"
```

### ResourceOption（资源选项）

```yaml
ResourceOption:
  name: string                  # 如 "yfinance"
  traits: list[string]          # 特征标签，如 ["free", "eod_only", "no_api_key", "rate_limited"]
  fit_for: list[string]         # 适合场景，如 ["原型验证", "日线级回测研究"]
  not_fit_for: list[string]     # 不适合场景，如 ["实时交易", "高频策略"]
```

### DataFlowEdge（数据流边）

```yaml
DataFlowEdge:
  from_stage: string            # 如 "data_ingestion"
  to_stage: string              # 如 "feature_engineering"
  data: string                  # 传递的数据契约名，如 "ohlcv_dataframe"
  condition: string | null      # 条件流转（null = 无条件），如 "当 signal_count > 0 时"
```

---

## 二、Constraint Schema（约束）

### 与旧 Judgment 的变更总结

| 变更类型 | 字段 | 说明 |
|---------|------|------|
| **删除** | `layer` | 不再按来源分层 |
| **删除** | `compilation.crystal_section` | 编译时自动派生 |
| **删除** | `compilation.emit_as_hard_constraint` | 被 severity + applies_to 替代 |
| **删除** | `compilation.machine_checkable` | 低使用率，简化 |
| **删除** | `compilation.validator_template` | 低使用率，简化 |
| **删除** | `compilation.degradation_action` | 移入蓝图的 stage.design_decisions |
| **新增** | `applies_to` | 约束附着到蓝图的哪个位置 |
| **修改** | `id` 格式 | `{domain}-{K/R/E}-{num}` → `{domain}-C-{num}` |
| **修改** | `confidence.source` | `SourceLevel(S1-S4)` → `SourceType` 枚举 |
| **简化** | `scope.context_requires` | 去掉 markets/environments/target_versions |
| **保留** | core / scope.level / scope.domains / severity / freshness / relations / version / examples / notes | 不变 |

### 完整数据模型

```yaml
Constraint:
  # ── 标识 ──
  id: string                    # 格式: {domain}-C-{number}，如 "finance-C-001"
  hash: string                  # 内容指纹（自动计算，含 core + applies_to + scope）

  # ── 核心三元组（不变） ──
  core:
    when: string                # 触发条件（min 5 字符）
    modality: enum              # must / must_not / should / should_not
    action: string              # 具体行为（min 5 字符）
    consequence:
      kind: enum                # bug / performance / financial_loss / data_corruption / service_disruption / operational_failure / compliance / safety / false_claim
      description: string       # 后果描述（min 10 字符）

  # ── 附着点（新增） ──
  applies_to:
    target: string              # 蓝图阶段 ID（如 "data_ingestion"）或 "global"
    blueprint_id: string | null # 关联的蓝图 ID（null = 通用约束，适用于所有含该阶段的蓝图）

  # ── 适用范围 ──
  scope:
    level: enum                 # universal / domain / context
    domains: list[string]       # 领域标签（min 1）
    context_requires:           # 可选，仅 level=context 时必填
      resources: list[string]   # 如 ["yfinance", "pandas"]
      task_types: list[string]  # 如 ["backtesting", "live_trading"]
      tech_stack: list[string]  # 如 ["python", "asyncio"]

  # ── 可信度 ──
  confidence:
    source_type: enum           # code_analysis / community_issue / official_doc / api_changelog / cross_project / expert_reasoning
    score: float                # 0.0 - 1.0
    consensus: enum             # universal / strong / mixed / contested
    verified_by: list[string]   # 验证者
    evidence_refs: list[EvidenceRef]
      # type: source_code / issue / pull_request / discussion / benchmark / paper / doc / user_feedback
      # source: string
      # locator: string | null
      # summary: string

  # ── 严重度与新鲜度 ──
  severity: enum                # fatal / high / medium / low
  freshness: enum               # stable / semi_stable / volatile

  # ── 关系（不变） ──
  relations: list[Relation]
    # type: generates / depends_on / conflicts / strengthens / supersedes / subsumes
    # target_id: string
    # description: string

  # ── 生命周期（不变） ──
  version:
    status: enum                # draft / active / deprecated / superseded / invalidated
    created_at: string
    updated_at: string
    review_after_days: int | null
    superseded_by: string | null
    schema_version: string      # "2.0"（区别于旧版 "1.0"）

  # ── 可选 ──
  examples:
    positive: list[string]
    negative: list[string]
  notes: string | null
  tags: list[string]            # 检索标签
```

### Hash 计算规则

```
hash = sha256(json_dumps({
    "core": core,
    "applies_to": applies_to,
    "scope": scope
}, sort_keys=True))[:16]
```

包含 `applies_to`，因为同一规则挂在不同阶段应被视为不同约束。

---

## 三、Seed Crystal 编译规则

### 输入

```
编译输入：
  - 1 个 Blueprint
  - N 条 Constraint（通过 applies_to.blueprint_id 关联，或 blueprint_id=null 的通用约束）
  - 用户意图描述（task_description）
```

### 编译流程

```
Step 1: 约束收集
  - 直接关联：applies_to.blueprint_id == 当前蓝图 ID
  - 通用关联：applies_to.blueprint_id == null 且 applies_to.target 在蓝图的 stages 中存在
  - 领域关联：scope.domains 包含蓝图的 domain 且 applies_to.target == "global"
  
Step 2: 约束分组
  - 全局约束组：applies_to.target == "global"
  - 各阶段约束组：按 applies_to.target 分组

Step 3: 验收标准提取
  从所有约束中提取进入验收标准的：
  - severity == fatal → 自动提升为验收项
  - 跨阶段碰撞：同一 when 出现在两个不同阶段的约束中 → 提升为验收项

Step 4: 渲染四段晶体
```

### 输出：种子晶体四段结构

```markdown
# 种子晶体：{domain} — {task_description}

> 蓝图来源：{blueprint.source.projects}
> 约束数量：{constraint_count} 条（全局 {global_count} + 阶段 {stage_count}）
> 编译时间：{compiled_at}

---

## context_acquisition

（自动生成，基于蓝图的 replaceable_points + 约束的 scope.context_requires）

> 宿主 AI 在执行前必须获取以下用户上下文：
> 1. 用户的技术栈和语言偏好
> 2. 可用的数据源（决定 {replaceable_point} 选择）
> 3. ...

---

## 一、架构蓝图

（渲染自 Blueprint，语言无关）

### 系统概述
{blueprint.applicability.description}

### 阶段划分

| 阶段 | 职责 | 输入 | 输出 |
|------|------|------|------|

（逐 stage 渲染）

### 数据流
{data_flow 渲染为文本 DAG}

### 各阶段详情

#### 1. {stage.name}

**职责**：{stage.responsibility}

**接口契约**：
- 输入：{inputs}
- 输出：{outputs}
- 必须实现：{required_methods}

**可替换资源**：
- {replaceable_point.name}：{options 列表}（默认：{default}）

**伪代码示例**：
{stage.pseudocode_example}

**关键设计决策**：
- {design_decisions}

---

## 二、约束（违反必出 bug）

### 全局约束

| # | 约束 | 严重度 | 证据 |
|---|------|--------|------|
（severity desc 排序的 global 约束）

### 阶段约束

#### {stage.name} 阶段

| # | 约束 | 严重度 | 证据 |
|---|------|--------|------|
（该阶段的约束，severity desc 排序）

---

## 三、验收标准

一个合格的 skill 必须通过以下检验：

1. {fatal 约束自动提升}
2. {跨阶段碰撞约束}
3. ...

---

*生成自 Doramagic 知识引擎 | 蓝图版本: {blueprint.version}*
```

---

## 四、存储格式

### Blueprint 存储

```
knowledge/
├── blueprints/
│   ├── finance/
│   │   ├── finance-bp-001.yaml    # 事件驱动量化回测
│   │   ├── finance-bp-002.yaml    # 向量化因子研究
│   │   └── _index.yaml            # 领域蓝图索引
│   ├── ai_tooling/
│   │   ├── ai_tooling-bp-001.yaml # 多 Agent 编排
│   │   └── _index.yaml
│   └── _global_index.yaml         # 全局索引
```

蓝图用 YAML 存储（结构化、人类可读、方便编辑），不用 JSONL（蓝图数量少、单个体积大、需要频繁人工编辑）。

### Constraint 存储

```
knowledge/
├── constraints/
│   ├── domains/
│   │   ├── finance.jsonl          # 金融领域约束
│   │   └── ai_tooling.jsonl       # AI 工具领域约束
│   ├── universal.jsonl            # 跨领域通用约束
│   └── _relations.jsonl           # 关系索引
```

约束继续用 JSONL 存储（数量大、批量追加、自动化采集）。

---

## 五、迁移计划（旧 Judgment → 新 Constraint）

### 字段映射

```
旧 Judgment                  → 新 Constraint
─────────────────────────────────────────────
id: "finance-K-001"          → id: "finance-C-001"（重新编号）
layer: "knowledge"           → （删除）
core: {...}                  → core: {...}（不变）
scope: {...}                 → scope: {...}（简化 context_requires）
confidence.source: "S1_..."  → confidence.source_type: "code_analysis"
compilation.severity         → severity（提升为顶级字段）
compilation.freshness        → freshness（提升为顶级字段）
compilation.crystal_section  → （删除，编译时自动派生）
compilation.query_tags       → tags（提升为顶级字段）
（无）                       → applies_to: { target: "global", blueprint_id: null }
```

### source 映射规则

```
旧 SourceLevel              → 新 SourceType
S1_single_project           → code_analysis（如果来自代码）或 official_doc（如果来自文档）
S2_cross_project            → cross_project
S3_community                → community_issue
S4_reasoning                → expert_reasoning
```

### applies_to 默认值

现有 judgment 迁移时，applies_to 默认为 `{ target: "global", blueprint_id: null }`。蓝图建立后再手动或半自动关联。
