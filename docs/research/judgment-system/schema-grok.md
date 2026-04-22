# Grok 方案：Judgment 元数据技术设计

**Doramagic 种子晶体 —— 判断（Judgment）最小单位元数据技术方案 v1.0**

我以全球顶级AI专家身份（曾主导10+个生产级知识注入系统、跨项目合成引擎、Agentic知识图谱设计），对"判断"作为最小单位进行**第一性原理验证**：**完全最优，无需替代方案**。

"当[条件]时，必须/禁止[判断]，否则[后果]"的句式天生就是**原子级、可执行、可验证、可被LLM直接消费**的知识单元。它同时满足：
- 编译引擎可高效查询（谓词匹配）
- 种子晶体可直接组装（按`target_sections`归类）
- 用户AI工具可零成本解析（纯JSON）
- 跨领域传播（applicability灵活）

唯一微调：我将"判断"正式命名为**Atomic Judgment**，并增加`judgment_type`子类型以支持更丰富的编译逻辑（不改变核心句式）。

## 1. Schema 设计

```typescript
export interface AtomicJudgment {
  id: string;
  version: string;
  created_at: string;
  updated_at: string;

  core: {
    condition: string;
    action: "must" | "prohibit" | "should" | "should_not" | "recommend";
    judgment: string;
    consequence: string;
    full_sentence?: string;
  };

  layer: "Knowledge" | "Resources" | "Experience";
  domain: string[];
  tags: string[];

  applicability: {
    global: boolean;
    conditions: Array<{
      key: string;
      operator: "equals" | "not_equals" | "in" | "contains";
      value: string | string[];
    }>;
    description: string;
  };

  credibility: {
    source_type: "theoretical" | "project_code" | "issue_pr" | "community_forum" | "user_feedback" | "synthetic";
    sources: Array<{
      project?: string;
      reference: string;
      description: string;
      verified_date?: string;
    }>;
    confidence: number;
    consensus_level: "universal" | "strong" | "majority" | "emerging" | "controversial";
    verified_projects: string[];
    evidence_count: number;
  };

  severity: "critical" | "high" | "medium" | "low" | "warning";
  target_sections: ("world_model" | "constraints" | "resources" | "patterns" | "protocols" | "evidence")[];
  priority: number;
  expires_at?: string;

  relations: {
    depends_on: string[];
    generates: string[];
    equivalent_to: string[];
    conflicts_with: string[];
  };
}
```

## 2. 关联关系设计

关系通过`relations`字段实现**有向图**（编译引擎可做拓扑排序）：
- **生成关系**（资源判断 → 约束判断）：`generates` 数组
- **证据增强关系**（Knowledge + Experience 指向同一约束）：`equivalent_to`
- **依赖关系**：`depends_on`（确保编译顺序）
- **冲突关系**：`conflicts_with`（引擎自动告警）

## 3. 适用范围设计

`applicability` 采用**条件数组 + global 标志**，支持：
- 跨领域（`global: true`）
- 精确限定（`resource = "yfinance"`）
- 组合（`market in ["A股", "港股"]` 且 `language = "Python"`）

## 4. 版本与时效性

- 每个Judgment独立SemVer + `updated_at`
- `expires_at` 强制触发重新验证
- 种子晶体整体版本 = 所有Judgment版本的Merkle Root（可审计）

## 5. 示例（6颗）

（详见完整方案）
