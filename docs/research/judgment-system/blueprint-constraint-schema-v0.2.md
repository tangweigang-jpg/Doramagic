# Blueprint + Constraint Schema v0.2

> 基于 v0.1 + GPT/Gemini/Grok 三方技术评审修订
> 日期：2026-04-04
> 状态：定稿（可进入代码实现）

---

## 一、Blueprint Schema

```yaml
Blueprint:
  # ── 标识 ──
  id: string                        # {domain}-bp-{number}
  name: string                      # 人类可读名称
  version: string                   # 语义化版本号

  # ── 来源 ──
  source:
    projects: list[string]          # 提炼自哪些项目
    extraction_method: enum         # manual / semi_auto / auto
    confidence: float               # 0.0-1.0

  # ── 适用性 ──
  applicability:
    domain: string
    task_type: string
    description: string             # 一句话描述解法特征
    prerequisites: list[string]     # 使用前提
    not_suitable_for: list[string]  # 明确不适用场景

  # ── 执行范式（v0.2 新增） ──
  execution_paradigm: enum          # pipeline / event_driven / state_machine
                                    # pipeline: A→B→C 线性或 DAG
                                    # event_driven: while-loop + 异步回调
                                    # state_machine: 状态转移驱动

  # ── 核心：阶段定义 ──
  stages: list[Stage]

  # ── 核心：数据流 ──
  data_flow: list[DataFlowEdge]

  # ── 核心：全局约定 ──
  global_contracts: list[string]    # 跨阶段架构约定

  # ── 蓝图间关系（v0.2 新增） ──
  relations: list[BlueprintRelation]

  # ── 元数据 ──
  created_at: string
  updated_at: string
  tags: list[string]
```

### Stage（阶段）

```yaml
Stage:
  id: string                        # 如 "data_ingestion"
  name: string                      # 如 "数据采集"
  order: int                        # 执行顺序（并行阶段可共享 order 值）

  # ── 职责 ──
  responsibility: string            # 一句话职责

  # ── 接口契约 ──
  interface:
    inputs: list[DataContract]
    outputs: list[DataContract]
    required_methods: list[MethodSignature]

  # ── 可替换点 ──
  replaceable_points: list[ReplaceablePoint]

  # ── 伪代码示例 ──
  pseudocode_example: string

  # ── 关键设计决策 ──
  design_decisions: list[string]

  # ── 阶段验收提示（v0.2 新增） ──
  acceptance_hints: list[string]    # 如 ["输出 DataFrame 必须有 tz-aware 索引", "无缺失值"]
```

### DataFlowEdge（数据流边）

```yaml
DataFlowEdge:
  id: string                        # 如 "data_to_feature"（v0.2 新增 id）
  from_stage: string
  to_stage: string
  data: string                      # DataContract name
  edge_type: enum                   # data_flow / control_gate / feedback_loop（v0.2 新增）
  required: bool                    # true=必须 false=可选（v0.2 新增）
  condition: string | null
```

### BlueprintRelation（蓝图间关系，v0.2 新增）

```yaml
BlueprintRelation:
  type: enum                        # specializes / generalizes / alternative_to / supersedes
  target_blueprint_id: string
  rationale: string                 # 一句话说明关系
```

### DataContract / MethodSignature / ReplaceablePoint / ResourceOption

与 v0.1 相同，不再重复。

---

## 二、Constraint Schema

```yaml
Constraint:
  # ── 标识 ──
  id: string                        # {domain}-C-{number}
  hash: string                      # sha256(core + scope)[:16]
                                    # 【v0.2 修正】不再包含 applies_to

  # ── 核心三元组（不变） ──
  core:
    when: string                    # min 5 chars
    modality: enum                  # must / must_not / should / should_not
    action: string                  # min 5 chars
    consequence:
      kind: enum                    # bug / performance / financial_loss / data_corruption /
                                    # service_disruption / operational_failure / compliance /
                                    # safety / false_claim
      description: string           # min 10 chars

  # ── 约束性质（v0.2 新增） ──
  constraint_kind: enum             # domain_rule: 领域客观规则（如"必须用 Decimal"）
                                    # resource_boundary: 工具能力边界（如"yfinance 延迟 15 分钟"）
                                    # operational_lesson: 运维/社区经验（如"dry-run 72 小时"）
                                    # architecture_guardrail: 架构护栏（如"风控在执行之后"）
                                    # claim_boundary: 能力声明边界（如"不能宣称实时交易"）

  # ── 附着点（v0.2 修正：支持多目标） ──
  applies_to:
    target_scope: enum              # global / stage / edge
    stage_ids: list[string]         # 适用的阶段 ID 列表（target_scope=stage 时必填）
    edge_ids: list[string]          # 适用的数据流边 ID 列表（target_scope=edge 时必填）
    blueprint_ids: list[string] | null  # 关联蓝图（null = 通用约束）

  # ── 适用范围 ──
  scope:
    level: enum                     # universal / domain / context
    domains: list[string]
    context_requires:               # 可选
      resources: list[string]
      task_types: list[string]
      tech_stack: list[string]

  # ── 可信度 ──
  confidence:
    source_type: enum               # code_analysis / community_issue / official_doc /
                                    # api_changelog / cross_project / expert_reasoning
    score: float                    # 0.0-1.0
    consensus: enum                 # universal / strong / mixed / contested
    verified_by: list[string]
    evidence_refs: list[EvidenceRef]

  # ── 编译提示（v0.2 新增） ──
  machine_checkable: bool           # 是否可自动化验证
  promote_to_acceptance: bool       # 显式标记是否提升为验收标准（覆盖自动派生）

  # ── 严重度与新鲜度 ──
  severity: enum                    # fatal / high / medium / low
  freshness: enum                   # stable / semi_stable / volatile

  # ── 关系 ──
  relations: list[Relation]

  # ── 生命周期 ──
  version:
    status: enum                    # draft / active / deprecated / superseded / invalidated
    created_at: string
    updated_at: string
    review_after_days: int | null
    superseded_by: string | null
    schema_version: string          # "2.0"

  # ── 可选 ──
  examples:
    positive: list[string]
    negative: list[string]
  notes: string | null
  tags: list[string]
```

---

## 三、编译规则（v0.2 修订）

### 约束收集

```
Step 1: 收集关联约束
  - blueprint_ids 包含当前蓝图 ID
  - blueprint_ids = null 且 stage_ids 在蓝图 stages 中存在
  - blueprint_ids = null 且 target_scope = "global" 且 domains 匹配
```

### 验收标准派生规则（v0.2 修订）

```
进入验收标准的条件（满足任一即可）：
  1. promote_to_acceptance = true（显式标记，最高优先级）
  2. severity = fatal
  3. machine_checkable = true 且 severity >= high
  4. consequence.kind in {false_claim, financial_loss, data_corruption, compliance, safety}
  5. target_scope = "edge"（跨阶段约束天然是验收项）
```

### 约束冲突裁决规则（v0.2 新增）

```
优先级从高到低：
  1. blueprint-specific（blueprint_ids 非空）> generic（blueprint_ids = null）
  2. must / must_not > should / should_not
  3. severity 高 > severity 低
  4. confidence.score 高 > confidence.score 低
  5. version.updated_at 新 > 旧
```

### 输出：种子晶体结构（v2，2026-04-04 修订）

> v2 基于首次端到端验证 + 四方研究（Grok/Gemini/GPT/Claude）优化。
> 核心变更：execution_directive 前置、FATAL ≤15 条高注意力位置、约束按阶段交织、验收嵌入工作流。
> 设计文档：`docs/designs/2026-04-04-crystal-v2-design.md`

```markdown
# 种子晶体：{blueprint.name}

## execution_directive
（告诉宿主 AI 这是执行任务，立即按流程执行，交付结果而非工具）

## [FATAL] 不可违反的约束（≤15 条）
（severity=fatal + promote_to_acceptance，按 confidence 降序取 top 15）
（放在文件前部——注意力衰减研究表明开头权重最高）

## context_acquisition
### 第一步：查阅用户记忆（历史会话、偏好、经验水平）
### 第二步：补采缺失信息（从蓝图 prerequisites 生成）
### 可替换点决策（从蓝图 replaceable_points 生成）
### 用户策略思路（从意图识别阶段传入）
### 不适用场景（从蓝图 not_suitable_for 生成）

## skill_scaffold
（预定义 skill 输出文件结构，防止 AI 自主决定）

## 架构蓝图与约束（按阶段交织组织）
### 数据流
### 全局约定
### 全局与跨阶段约束
### 阶段 N：{stage.name}
  - 职责 + 输出 + 伪代码
  - 本阶段约束（severity 降序）
  - 本阶段验收检查点（嵌入式 checklist）
...
```

**约束三层分级**：
- EMBED（≤15 条）：fatal + promote_to_acceptance → 放入 [FATAL] 段
- ON_DEMAND（其余）：按阶段分组，交织在架构蓝图中
- 验收标准嵌入每个阶段末尾（非末尾堆砌）

---

## 四、存储格式

### Blueprint

```
knowledge/blueprints/{domain}/{id}.yaml
```

YAML 格式。数量少（预计 <100），需人工编辑和 review。

### Constraint

```
knowledge/constraints/domains/{domain}.jsonl
knowledge/constraints/universal.jsonl
```

JSONL 格式。数量大，自动化采集追加。

### 一致性校验（v0.2 新增）

必须实现 CI 级脚本 `scripts/check_consistency.py`：
- 校验所有 Constraint 的 `applies_to.stage_ids` 在关联 Blueprint 的 stages 中存在
- 校验所有 `applies_to.edge_ids` 在关联 Blueprint 的 data_flow 中存在
- 校验所有 `applies_to.blueprint_ids` 指向存在的 Blueprint
- Blueprint 的 stage.id 重命名时自动提示受影响的 Constraint 数量

---

## 五、v0.1 → v0.2 变更总结

| 变更 | 来源 | 类型 |
|------|------|------|
| `applies_to.target` 从 string 改为 `stage_ids: list` + `edge_ids: list` | 全票共识 | 设计修复 |
| hash 不再包含 applies_to | 全票共识 | Bug 修复 |
| 新增 `machine_checkable` + `promote_to_acceptance` | 全票共识 | 设计修复 |
| 新增 `constraint_kind` 枚举 | GPT + Grok | 设计增强 |
| 新增 Blueprint `execution_paradigm` | Gemini | 设计增强 |
| 新增 Blueprint `relations` | GPT | 设计增强 |
| 新增 DataFlowEdge `id` + `edge_type` + `required` | GPT | 设计增强 |
| 新增 Stage `acceptance_hints` | GPT + Grok | 设计增强 |
| 新增约束冲突裁决规则 | GPT | 编译规则补全 |
| 新增验收标准五条派生规则 | 全票共识 | 编译规则修复 |
| 新增一致性校验脚本要求 | 全票共识 | 工程保障 |

---

## 六、迁移计划（旧 Judgment → 新 Constraint）

```
旧字段                      → 新字段
────────────────────────────────────────
id: "{domain}-K-001"        → id: "{domain}-C-001"
layer: "knowledge"          → constraint_kind: "domain_rule"
layer: "resource"           → constraint_kind: "resource_boundary"
layer: "experience"         → constraint_kind: "operational_lesson"
confidence.source: S1       → confidence.source_type: code_analysis 或 official_doc
confidence.source: S2       → confidence.source_type: cross_project
confidence.source: S3       → confidence.source_type: community_issue
confidence.source: S4       → confidence.source_type: expert_reasoning
compilation.severity        → severity（顶级）
compilation.freshness       → freshness（顶级）
compilation.crystal_section → （删除，编译时自动派生）
compilation.query_tags      → tags（顶级）
（无）                      → applies_to: { target_scope: "global", stage_ids: [], edge_ids: [], blueprint_ids: null }
（无）                      → constraint_kind:（由旧 layer 映射）
（无）                      → machine_checkable: false（默认，后续人工标注）
（无）                      → promote_to_acceptance: null（默认，后续人工标注）
hash: sha256(core+scope)   → hash: sha256(core+scope)（不变，v0.1 的 applies_to 已在实际代码中被修正）
```
