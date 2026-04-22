# Schema 技术评审 Prompt

> 发给 GPT-4o 做技术挑战
> 日期：2026-04-04

---

## 提示词

```
你是一位资深系统架构师，擅长知识工程和 AI 系统设计。请对以下两个数据模型做技术评审。

## 背景

我们在构建一个"种子晶体"系统——从开源项目中提取专家知识，编译成 AI 可消费的知识配方。用户把晶体交给自己的 AI 工具，AI 按配方构建个性化 skill。

经过四方模型（Claude/GPT/Gemini/Grok）的架构评审，我们确定了"蓝图 + 约束"两层知识架构：
- **蓝图（Blueprint）**：系统的架构结构（阶段划分、接口契约、数据流、可替换点）
- **约束（Constraint）**：规则和限制（挂在蓝图的特定阶段或全局）

以下是两个 schema 的完整设计。请从技术角度挑战它们。

---

## Blueprint Schema

```yaml
Blueprint:
  id: string                    # {domain}-bp-{number}
  name: string                  
  version: string               
  
  source:
    projects: list[string]      # 提炼自哪些项目
    extraction_method: enum     # manual / semi_auto / auto
    confidence: float           # 0.0-1.0
  
  applicability:
    domain: string              
    task_type: string           
    description: string         # 一句话描述解法特征
    prerequisites: list[string] 
    not_suitable_for: list[string]

  stages: list[Stage]           # 核心阶段定义
  data_flow: list[DataFlowEdge] # 阶段间数据流
  global_contracts: list[string] # 跨阶段架构约定

  created_at: string
  updated_at: string
  tags: list[string]

Stage:
  id: string                    # 如 "data_ingestion"
  name: string                  
  order: int                    # 允许并行阶段共享 order 值
  responsibility: string        # 一句话职责
  
  interface:
    inputs: list[DataContract]
    outputs: list[DataContract]
    required_methods: list[MethodSignature]

  replaceable_points: list[ReplaceablePoint]
  pseudocode_example: string    # 非可运行代码
  design_decisions: list[string]

DataContract:
  name: string
  description: string
  schema_hint: string           # 语言无关的结构描述
  constraints: list[string]

MethodSignature:
  name: string
  description: string
  parameters: list[string]      # "参数名: 含义" 格式
  returns: string
  notes: string | null

ReplaceablePoint:
  name: string
  description: string
  options: list[ResourceOption]
  default: string
  selection_criteria: string

ResourceOption:
  name: string
  traits: list[string]          # 如 ["free", "eod_only"]
  fit_for: list[string]
  not_fit_for: list[string]

DataFlowEdge:
  from_stage: string
  to_stage: string
  data: string                  # DataContract name
  condition: string | null
```

## Constraint Schema

```yaml
Constraint:
  id: string                    # {domain}-C-{number}
  hash: string                  # sha256(core + applies_to + scope)[:16]

  core:
    when: string                # min 5 chars
    modality: enum              # must / must_not / should / should_not
    action: string              # min 5 chars
    consequence:
      kind: enum                # bug / performance / financial_loss / data_corruption / service_disruption / operational_failure / compliance / safety / false_claim
      description: string       # min 10 chars

  applies_to:
    target: string              # 蓝图阶段 ID 或 "global"
    blueprint_id: string | null # null = 通用约束

  scope:
    level: enum                 # universal / domain / context
    domains: list[string]
    context_requires:           # 可选
      resources: list[string]
      task_types: list[string]
      tech_stack: list[string]

  confidence:
    source_type: enum           # code_analysis / community_issue / official_doc / api_changelog / cross_project / expert_reasoning
    score: float                # 0.0-1.0
    consensus: enum             # universal / strong / mixed / contested
    verified_by: list[string]
    evidence_refs: list
      # type / source / locator / summary

  severity: enum                # fatal / high / medium / low
  freshness: enum               # stable / semi_stable / volatile
  relations: list[Relation]
  version: { status, created_at, updated_at, schema_version: "2.0" }
  tags: list[string]
```

## 编译规则

种子晶体 = Blueprint + 关联 Constraints 编译而成，四段输出：

1. **context_acquisition**：从蓝图 replaceable_points + 约束 context_requires 自动生成
2. **架构蓝图**：渲染 Blueprint 的 stages + data_flow + interfaces
3. **约束表**：按 global / 各阶段分组，severity 降序
4. **验收标准**：severity=fatal 自动提升 + 跨阶段 when 碰撞提升

存储：蓝图用 YAML（数量少、需人工编辑），约束用 JSONL（数量大、自动采集）。

---

## 请评审以下方面

### A. Schema 完整性
1. Blueprint schema 是否有遗漏的关键字段？
2. Constraint schema 去掉 `layer` 字段后，是否丢失了有用信息？
3. `applies_to` 的设计是否足够表达约束和蓝图的关联关系？有没有边界情况处理不了？

### B. 编译可行性
4. 从 Blueprint + Constraints 编译到种子晶体四段结构，这个映射是否有歧义或遗漏？
5. "severity=fatal → 验收标准"这个自动提升规则是否合理？会不会漏掉非 fatal 但应该验收的项？
6. 约束按 applies_to.target 分组挂载到蓝图阶段——如果一条约束跨两个阶段怎么办？

### C. 实践可行性
7. Blueprint 用 YAML、Constraint 用 JSONL，两种格式混用会有什么问题？
8. ReplaceablePoint + ResourceOption 这个设计，在实际采集中能稳定提取吗？
9. hash 计算包含 applies_to——如果同一规则后来被重新挂载到不同阶段，hash 变了，去重会失效。这是 feature 还是 bug？

### D. 扩展性
10. 如果未来蓝图数量从 20 增长到 500，这个 schema 会遇到什么瓶颈？
11. 如果未来需要"蓝图选择器"（根据用户意图自动选蓝图），schema 需要改什么？
12. 如果你认为这个设计有根本性缺陷，请直接指出。

## 要求
- 用具体的例子说明问题（以"股票投资分析工具"为场景）
- 区分"设计缺陷"和"实现难点"
- 如果整体方向正确但有局部需要调整，给出具体的修改建议
```
