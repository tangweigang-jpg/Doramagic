# GPT 方案：Judgment 元数据技术设计

## 核心主张

**"判断（Judgment）"是对的，但单独作为最小单位还差半步。**

最稳的设计不是"判断 = 最小单位"，而是：

> **最小存储单位 = Claim（命题）**
> **最小编译单位 = Judgment（带动作的判定）**

建议：
1. 对外与编译接口继续使用 `Judgment`
2. 内部底层允许三类原子对象：`fact`、`evidence`、`judgment`

## 1. Schema 设计

```typescript
type Layer = "knowledge" | "resource" | "experience";
type JudgmentMode = "must" | "must_not" | "should" | "should_not" | "prefer" | "avoid";
type Severity = "critical" | "high" | "medium" | "low";
type ConfidenceLevel = "very_high" | "high" | "medium" | "low" | "speculative";
type ConsensusLevel = "universal" | "strong_consensus" | "mixed" | "contested" | "local_only";
type LifecycleStatus = "draft" | "active" | "deprecated" | "superseded" | "invalidated";
type CrystalSection = "world_model" | "constraints" | "resource_profile" | "architecture_patterns" | "validation_protocol" | "evidence" | "warnings" | "degradation";
type RelationType = "supports" | "contradicts" | "depends_on" | "generated_by" | "generates" | "specializes" | "generalizes" | "same_rule_different_evidence" | "overrides" | "requires_resource" | "invalid_if";

interface Judgment {
  id: string;
  type: "judgment";
  title: string;
  canonical_statement: string;

  when: {
    natural_language: string;
    clauses: ConditionClause[];
  };

  decision: {
    mode: JudgmentMode;
    action: string;
    target?: string;
  };

  otherwise: Consequence[];

  provenance: {
    layer: Layer;
    authored_by: "human" | "ai_compiler" | "hybrid";
    derived_from?: string[];
    source_method?: "theory" | "resource_inspection" | "cross_project_synthesis" | "incident_learning" | "community_consensus";
  };

  confidence: {
    score: number;
    level: ConfidenceLevel;
    consensus: ConsensusLevel;
    supporting_project_count?: number;
    contradicting_project_count?: number;
    validated_in_production?: boolean;
    validation_count?: number;
  };

  applicability: {
    domains: string[];
    markets?: string[];
    instruments?: string[];
    task_types?: string[];
    frequencies?: string[];
    tech_stack?: string[];
    data_sources?: string[];
    environments?: string[];
    condition_clauses?: ConditionClause[];
    excluded_clauses?: ConditionClause[];
  };

  evidence_refs: EvidenceRef[];
  relations: RelationRef[];

  compilation: {
    severity: Severity;
    priority_score: number;
    default_include: boolean;
    crystal_sections: CrystalSection[];
    emit_as_warning?: boolean;
    emit_as_hard_constraint?: boolean;
    emit_as_validator?: boolean;
    query_tags: string[];
    user_visible_summary: string;
    machine_checkable?: boolean;
    validator_template?: string;
    degradation_action?: string;
  };

  version: {
    judgment_version: string;
    introduced_at: string;
    last_reviewed_at?: string;
    valid_from?: string;
    valid_until?: string;
    status: LifecycleStatus;
    supersedes?: string[];
    superseded_by?: string;
    review_after_days?: number;
    stale_after_days?: number;
  };

  domain_tags: string[];
  resource_tags: string[];
  pattern_tags: string[];
  failure_tags: string[];

  examples?: {
    positive?: string[];
    negative?: string[];
  };
}
```

## 2. 关联关系设计

10 类关系：supports, contradicts, depends_on, generated_by, generates, specializes, generalizes, same_rule_different_evidence, overrides, invalid_if

### 关键模式

**模式A：资源生成约束** — 资源选择 → generates → 约束判断
**模式B：同一约束的双重证据** — 理论 + 经验通过 same_rule_different_evidence 关联

## 3. 适用范围设计

两层结构：
1. **显式维度**：domains, markets, task_types, frequencies, data_sources, tech_stack
2. **条件子句**：field + operator + value 的布尔组合

## 4. 版本与时效性

生命周期：draft → active → deprecated → superseded → invalidated

时效性策略：
- resource 层：90天复审
- experience 层：180天复审
- knowledge 层：长周期复审

## 5. 查询效率设计

编译排序公式：
```
compile_score = priority_score * 0.35 + severity_weight * 0.25 + confidence.score * 0.20 + relation_centrality * 0.10 + freshness_score * 0.10
```

## 6. 最终建议

存储层采用三种原子对象（fact, evidence, judgment），编译层以 judgment 为核心编译单位，输出层按晶体 section 组装。
