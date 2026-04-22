# Gemini 方案：Judgment 元数据技术设计

## 核心洞察

"判断"的经典句法在信息论上的本质是**状态机控制律（State-Machine Control Rule）**。它将模糊的领域经验压缩为带有明确**惩罚函数（Penalty Function）**的上下文干预指令。

技术文档抽象定义对标：**Production Rule（产生式规则）或 Heuristic Constraint（启发式约束）**。

## 1. Schema 设计

```typescript
type JudgmentLayer = "knowledge" | "resources" | "experience";
type Modality = "must" | "must_not" | "should" | "should_not";
type SeverityLevel = "fatal" | "high" | "medium" | "low";
type TargetCrystalSection = "world_model" | "constraints" | "resource_profile" | "architecture_paradigm" | "verification_protocol";

interface Judgment {
  id: string;
  hash: string;                    // 内容哈希，检测更新

  core: {
    condition: string;             // 触发条件（Embedding检索主力对象）
    modality: Modality;
    action: string;
    consequence: string;           // 惩罚函数（收束LLM幻觉）
  };

  scope: {
    layer: JudgmentLayer;
    domain_tags: string[];
    context_deps: string[];        // 业务流依赖
    resource_deps: string[];       // 资源依赖
    is_cross_domain: boolean;
  };

  edges: DirectedEdge[];

  temporality: {
    valid_from_date?: string;
    valid_until_date?: string;
    target_versions?: Record<string, string>;  // {"pandas": "<2.0.0"}
  };

  compilation: {
    severity: SeverityLevel;
    crystal_section: TargetCrystalSection;
    confidence_score: number;
    verifications: number;
    evidence_links: string[];
  };
}

interface DirectedEdge {
  target_id: string;
  relation_type: "generates" | "conflicts_with" | "reinforces" | "subsumes";
  description: string;             // 给编译器LLM看的因果描述
}
```

## 2. 关联关系设计

4 类关系：
- **generates**：资源选择 → 生成约束
- **conflicts_with**：经验A ↔ 异议经验B，需编译时裁决
- **reinforces**：实战经验 → 强化理论知识
- **subsumes**：大原则 → 包含子规则

## 3. 适用范围设计

通过 `scope` 结构实现：
- `domain_tags`：领域树
- `context_deps`：业务流条件
- `resource_deps`：资源存在性条件
- `is_cross_domain`：泛领域真理标志

## 4. 版本与时效性

通过 `temporality` 结构实现：
- `valid_from_date` / `valid_until_date`：时间窗口
- `target_versions`：资源版本约束

## 5. 编译引擎运转流向

1. **向量召回**：意图 vs `core.condition` 相似度匹配
2. **图谱拉平**：沿 `edges` 拉入上下游
3. **环境裁剪**：通过 `scope.resource_deps` + `temporality` 过滤
4. **组装晶体**：按 `compilation.crystal_section` Group By
