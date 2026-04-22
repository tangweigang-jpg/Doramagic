# Judgment Schema 四方合成（Claude × GPT × Gemini × Grok）

---

## 一、共识信号（ALIGNED）— 四方一致

### A1. 核心三元组不可动摇
四方均保留了 `when/action/consequence` 三元组作为 Judgment 的内容核心。无人提出替代结构。

### A2. 三层归属（layer）
所有方案都包含 `knowledge | resource | experience` 三层标签，且用法一致。

### A3. 关联关系是一等公民
四方均把关系建模为判断的核心组成部分（非可选附件），且都包含至少这三种关系：
- **generates**（资源 → 约束）
- **conflicts / contradicts**（互斥）
- **depends_on / requires**（前置依赖）

### A4. 严重度分级
四方均区分"致命/高/中/低"，编译器依此排序和裁剪。

### A5. 晶体分区映射
四方均设计了"判断 → 晶体 section"的映射字段（`crystal_section` / `target_sections`），编译器按此分组输出。

### A6. 适用范围需要结构化
四方都拒绝了"纯文本描述适用范围"，都设计了可查询的结构化 scope。

---

## 二、分歧信号（DIVERGENT）及裁决

### D1. 最小单位是否只有 Judgment？

| 立场 | 持有者 |
|------|--------|
| Judgment 是唯一原子，够用 | Claude, Grok, Gemini |
| 底层应分 fact/evidence/judgment 三种 | GPT |

**裁决：Judgment 为唯一原子。** 理由：
1. GPT 说的 fact（"yfinance 延迟 15 分钟"）和 evidence（"上线三天 PnL 偏差 0.8%"）不是独立的知识单元——它们只有在被"当…时，禁止…，否则…"的判断句式引用时才有编译价值。
2. 独立存储 fact/evidence 会增加存储层复杂度，但编译器最终消费的还是 Judgment。
3. **但采纳 GPT 的核心洞察**：Judgment 必须保留 `evidence_refs` 和 `derived_from` 槽位，让 fact 和 evidence 作为判断的**溯源材料**而非独立实体。

### D2. 关系类型数量

| 方案 | 关系类型数 |
|------|-----------|
| Gemini | 4 (generates, conflicts_with, reinforces, subsumes) |
| Claude | 5 (+supersedes) |
| Grok | 4 (depends_on, generates, equivalent_to, conflicts_with) |
| GPT | 11 (含 specializes, generalizes, overrides, invalid_if 等) |

**裁决：6 种关系。** GPT 的 11 种过度工程化，Gemini 的 4 种缺少关键的 `depends_on`。最终保留：

1. **generates** — 资源选择 → 生成约束
2. **depends_on** — 前置依赖
3. **conflicts** — 互斥，编译器需裁决
4. **strengthens** — 同一约束的多重证据（Claude 的 strengthens = Grok 的 equivalent_to = GPT 的 same_rule_different_evidence）
5. **supersedes** — 版本迭代替代
6. **subsumes** — 大原则包含子规则（Gemini 独特贡献）

其中 GPT 的 `specializes/generalizes` 被 `subsumes` 单向边覆盖；`overrides` 被 `supersedes` + `scope` 覆盖；`invalid_if` 被 `conflicts` + `scope.context_requires` 覆盖。

### D3. 适用范围的表达方式

| 方案 | 设计 |
|------|------|
| Claude | scope 三级枚举 (universal/domain/context) + context_requires 字符串数组 |
| GPT | 显式维度（domains, markets, tech_stack...）+ condition_clauses 布尔表达式 |
| Grok | global 布尔 + conditions 条件数组 |
| Gemini | domain_tags + context_deps + resource_deps + is_cross_domain 布尔 |

**裁决：Claude 的三级枚举 + GPT 的显式维度混合。** 理由：
1. Claude 的 `universal/domain/context` 三级在**概念上**最清晰，一颗判断的适用范围只有三种可能，这是第一性原理。
2. 但 Claude 的 `context_requires` 字符串数组太松散，编译器无法高效查询。
3. 采纳 GPT 的结构化维度作为 `context_requires` 的实现方式，但不暴露为顶层字段（保持概念简洁）。

### D4. 版本管理复杂度

| 方案 | 设计 |
|------|------|
| Claude | freshness 三级 + 简单审查周期 |
| GPT | 完整生命周期状态机 (draft → active → deprecated → superseded → invalidated) |
| Grok | SemVer + expires_at + Merkle Root |
| Gemini | valid_from/valid_until + target_versions |

**裁决：GPT 的生命周期状态机 + Claude 的 freshness 三级 + Gemini 的 target_versions。** 理由：
1. 生命周期状态机对编译器至关重要——编译器必须知道一颗判断是"草稿"还是"已被替代"。
2. freshness 三级是 Claude 的独特贡献，它告诉编译器"这颗判断多久会过期"，这是时效性的**本质属性**而非**管理状态**。
3. Gemini 的 `target_versions` 对资源层判断不可或缺（如 "pandas < 2.0" 时才成立）。
4. Grok 的 Merkle Root 是工程锦上添花，不进核心 Schema。

### D5. action 的枚举值

| 方案 | action 值 |
|------|----------|
| Claude | 隐含在 claim 自然语言中 |
| Grok | must, prohibit, should, should_not, recommend |
| GPT | must, must_not, should, should_not, prefer, avoid |
| Gemini | must, must_not, should, should_not |

**裁决：4 值枚举 `must | must_not | should | should_not`。** 理由：
1. Grok 的 `recommend` 和 GPT 的 `prefer/avoid` 语义模糊，不符合"判断"的断言性质。一颗判断要么是规则，要么不该写成判断。
2. Gemini 的 4 值最干净。

---

## 三、独特贡献（UNIQUE）— 各方精华

### U1. Gemini：内容哈希（hash）
`hash` 字段用于检测知识库更新——同一 ID 的判断内容是否被修改过。简单但关键，采纳。

### U2. Gemini：边描述给编译器 LLM 看
`DirectedEdge.description` 字段：给编译器大模型的因果解释。不是给人看的文档，是给 LLM 的上下文。精妙，采纳。

### U3. GPT：consequence 的结构化
`otherwise` 不只是一段文字，而是 `{ kind, description, measurable_impact }`。kind 枚举（bug/performance/compliance/safety/financial_loss/false_claim）让编译器能按后果类型分类和聚合。采纳 kind + description，measurable_impact 合入 description。

### U4. GPT：正负示例（examples）
`examples: { positive?, negative? }` — 给编译器和种子晶体的具体代码示例。对 LLM 消费极有价值。采纳为可选字段。

### U5. GPT：编译排序公式
`compile_score = priority * 0.35 + severity * 0.25 + confidence * 0.20 + centrality * 0.10 + freshness * 0.10`。这不属于 Schema 本身，但对编译引擎设计有参考价值，记录但不入 Schema。

### U6. GPT：degradation_action
当资源不足时的降级动作（如 `downgrade_to_eod_research_only`）。这是编译引擎的指令，属于 `compilation` 字段。采纳。

### U7. Grok：full_sentence 自动生成
`core.full_sentence`：从三元组自动拼接完整句子，供 LLM 直接提示。实用，但应由编译器运行时生成而非存储。不入 Schema。

### U8. Gemini：target_versions 资源版本约束
`temporality.target_versions: Record<string, string>`：如 `{"pandas": "<2.0.0"}`。对资源层判断至关重要。采纳。

### U9. Claude：source 的知识来源分级
`S1_single_project | S2_cross_project | S3_community | S4_reasoning`：描述判断的知识来源层级，与 confidence 是不同维度。来源越广泛，判断越可靠。采纳。

### U10. GPT：machine_checkable + validator_template
判断是否可以被代码自动验证，以及对应的验证器模板。这是从"被动知识"到"主动检查"的桥梁。采纳为可选字段。

---

## 四、最终合成 Schema

```typescript
// ═══════════════════════════════════════════════
// Doramagic Judgment Schema v1.0 — 四方合成最终版
// ═══════════════════════════════════════════════

// ── 枚举定义 ──

type Layer = "knowledge" | "resource" | "experience";

type Modality = "must" | "must_not" | "should" | "should_not";

type Severity = "fatal" | "high" | "medium" | "low";

type Scope = "universal" | "domain" | "context";

type Freshness = "stable" | "semi_stable" | "volatile";
//  stable:      3年+ 不变（数学原理、物理规律）
//  semi_stable: 6-18月（框架最佳实践、API 用法）
//  volatile:    <6月（费用结构、限频策略）

type LifecycleStatus = "draft" | "active" | "deprecated" | "superseded" | "invalidated";

type ConsequenceKind =
  | "bug"
  | "performance"
  | "compliance"
  | "safety"
  | "financial_loss"
  | "false_claim"
  | "operational_failure";

type SourceLevel =
  | "S1_single_project"
  | "S2_cross_project"
  | "S3_community"
  | "S4_reasoning";

type ConsensusLevel = "universal" | "strong" | "mixed" | "contested";

type CrystalSection =
  | "world_model"
  | "constraints"
  | "resource_profile"
  | "architecture"
  | "protocols"
  | "evidence";

type RelationType =
  | "generates"      // 本判断成立 → 产生目标判断
  | "depends_on"     // 本判断成立依赖目标判断
  | "conflicts"      // 与目标判断互斥
  | "strengthens"    // 为目标判断提供额外证据
  | "supersedes"     // 替代目标判断（版本迭代）
  | "subsumes";      // 本判断是目标判断的上位规则

// ── 核心接口 ──

interface Judgment {
  // 基础标识
  id: string;                         // 格式: "{domain}-{layer_initial}-{seq}"
  hash: string;                       // 内容哈希，检测知识库更新

  // ═══ 核心三元组 ═══
  core: {
    when: string;                     // 触发条件（同时是向量检索的主力字段）
    modality: Modality;               // 必须/禁止/应当/不应当
    action: string;                   // 具体行为
    consequence: {
      kind: ConsequenceKind;          // 后果类型
      description: string;            // 后果描述（含可量化影响）
    };
  };

  // ═══ 本体归属 ═══
  layer: Layer;                       // 三层归属

  // ═══ 适用范围 ═══
  scope: {
    level: Scope;                     // universal / domain / context
    domains: string[];                // 适用领域，如 ["finance", "quant"]
    context_requires?: {              // level=context 时的结构化条件
      resources?: string[];           // 如 ["yfinance", "pandas"]
      markets?: string[];             // 如 ["us_equity", "cn_a_share"]
      task_types?: string[];          // 如 ["backtest", "live_trading"]
      tech_stack?: string[];          // 如 ["python", "duckdb"]
      environments?: string[];        // 如 ["local", "server", "realtime"]
      target_versions?: Record<string, string>;  // 如 {"pandas": "<2.0.0"}
    };
  };

  // ═══ 可信度 ═══
  confidence: {
    source: SourceLevel;              // 知识来源层级
    score: number;                    // 0.0-1.0
    consensus: ConsensusLevel;        // 共识度
    verified_by?: string[];           // 验证过的项目/社区
    evidence_refs?: EvidenceRef[];    // 溯源材料
  };

  // ═══ 编译指导 ═══
  compilation: {
    severity: Severity;               // 编译排序权重
    crystal_section: CrystalSection;  // 在晶体中的位置
    freshness: Freshness;             // 时效性本质属性
    freshness_note?: string;          // 如 "美股2024年从T+2改T+1"
    emit_as_hard_constraint?: boolean;  // 是否作为硬约束注入
    machine_checkable?: boolean;      // 是否可代码自动验证
    validator_template?: string;      // 验证器模板 ID
    degradation_action?: string;      // 资源不足时的降级指令
    query_tags: string[];             // 搜索加速标签
  };

  // ═══ 关联关系 ═══
  relations: Relation[];

  // ═══ 版本管理 ═══
  version: {
    status: LifecycleStatus;
    created_at: string;               // ISO8601
    updated_at: string;
    review_after_days?: number;       // 自动审查周期
    superseded_by?: string;           // 被哪个判断替代
  };

  // ═══ 可选扩展 ═══
  examples?: {
    positive?: string[];              // 正确做法示例
    negative?: string[];              // 错误做法示例
  };
  notes?: string;
}

interface Relation {
  type: RelationType;
  target_id: string;
  description: string;                // 给编译器 LLM 的因果解释
}

interface EvidenceRef {
  type: "source_code" | "issue" | "pull_request" | "discussion"
      | "benchmark" | "paper" | "doc" | "user_feedback";
  source: string;                     // 项目或来源名
  locator?: string;                   // URL 或具体引用
  summary: string;                    // 一句话摘要
}
```

---

## 五、3 颗标杆判断（最终 Schema 格式）

### J1: 知识层 — float 精度禁令（跨领域）

```yaml
id: "finance-K-001"
hash: "a3f7c2..."

core:
  when: "进行金融计算（价格、资金、盈亏、费用累加）"
  modality: must_not
  action: "使用原生 float 类型作为真值存储"
  consequence:
    kind: financial_loss
    description: "IEEE 754 浮点误差累积，长期 PnL 偏差超 0.01%，审计无法通过"

layer: knowledge

scope:
  level: universal
  domains: ["finance", "healthcare", "engineering"]

confidence:
  source: S2_cross_project
  score: 0.98
  consensus: universal
  verified_by: ["freqtrade", "zipline", "vnpy"]
  evidence_refs:
    - type: issue
      source: freqtrade
      locator: "github.com/freqtrade/freqtrade/issues/2345"
      summary: "上线三天 PnL 累计偏差 0.8%"

compilation:
  severity: fatal
  crystal_section: constraints
  freshness: stable
  emit_as_hard_constraint: true
  machine_checkable: true
  validator_template: "validator.no_float_monetary_paths"
  query_tags: ["precision", "float", "decimal", "money", "pnl"]

relations:
  - type: strengthens
    target_id: "finance-E-012"
    description: "理论精度约束与实盘偏差案例互为双重证据"
  - type: subsumes
    target_id: "finance-K-042"
    description: "通用 float 禁令包含金融账本子场景"

version:
  status: active
  created_at: "2026-04-03"
  updated_at: "2026-04-03"
```

### J2: 资源层 — yfinance 实时交易禁令

```yaml
id: "finance-R-001"
hash: "b8d1e5..."

core:
  when: "需要实时交易决策且数据源为 yfinance"
  modality: must_not
  action: "依赖 yfinance 作为执行信号的数据源"
  consequence:
    kind: operational_failure
    description: "15-20 分钟数据延迟 + 无 SLA + 格式随时变更，信号决策全部失效"

layer: resource

scope:
  level: context
  domains: ["finance"]
  context_requires:
    resources: ["yfinance"]
    task_types: ["live_trading", "signal_generation"]

confidence:
  source: S2_cross_project
  score: 0.95
  consensus: strong
  verified_by: ["freqtrade", "zipline"]

compilation:
  severity: fatal
  crystal_section: resource_profile
  freshness: semi_stable
  freshness_note: "yfinance API 可能随 Yahoo 政策变动而变化"
  emit_as_hard_constraint: true
  degradation_action: "downgrade_to_eod_research_only"
  query_tags: ["yfinance", "realtime", "latency", "data_source"]

relations:
  - type: generates
    target_id: "finance-R-002"
    description: "选择 yfinance → 产品能力必须降级为 EOD 研究工具"

version:
  status: active
  created_at: "2026-04-03"
  updated_at: "2026-04-03"
  review_after_days: 90
```

### J3: 经验层 — dry-run 72 小时协议

```yaml
id: "finance-E-001"
hash: "c4a9f3..."

core:
  when: "量化策略首次部署到实盘之前"
  modality: must
  action: "在 dry-run / paper-trading 模式下运行至少 72 小时（含一个完整周末）"
  consequence:
    kind: operational_failure
    description: "跳过 dry-run 的项目首周出现致命 bug 概率极高——调度异常、时区错误、数据缺口、订单重复（freqtrade 社区 300+ 案例）"

layer: experience

scope:
  level: domain
  domains: ["finance", "quant"]

confidence:
  source: S3_community
  score: 0.92
  consensus: strong
  verified_by: ["freqtrade"]
  evidence_refs:
    - type: user_feedback
      source: freqtrade
      summary: "社区 300+ 案例验证 dry-run 可拦截首周致命 bug"

compilation:
  severity: high
  crystal_section: protocols
  freshness: stable
  query_tags: ["dry_run", "paper_trading", "launch", "deployment"]

relations:
  - type: strengthens
    target_id: "finance-R-001"
    description: "dry-run 经验进一步验证了不可靠数据源在实盘中的风险"

version:
  status: active
  created_at: "2026-04-03"
  updated_at: "2026-04-03"
```

---

## 六、编译引擎查询流程（推荐）

```
用户意图输入
    │
    ▼
Step 1: 向量召回
    对 core.when 做语义匹配 + query_tags 关键词匹配
    同时加载 scope.level = universal 的判断
    │
    ▼
Step 2: 范围过滤
    scope.level = domain → 检查 domains 匹配
    scope.level = context → 检查 context_requires 各维度匹配
    version.status = active（排除 draft/deprecated/invalidated）
    │
    ▼
Step 3: 关系展开
    沿 generates / depends_on 拉入关联判断
    检测 conflicts 并标记冲突对
    合并 strengthens 证据链
    │
    ▼
Step 4: 编译排序
    severity (fatal > high > medium > low)
    × confidence.score
    × relation centrality
    │
    ▼
Step 5: 晶体组装
    按 compilation.crystal_section 分组
    emit_as_hard_constraint → 写入晶体约束区头部
    degradation_action → 写入降级策略区
```

---

## 七、设计决策记录

| # | 决策 | 采纳来源 | 拒绝方案 | 理由 |
|---|------|---------|---------|------|
| 1 | Judgment 为唯一原子 | Claude/Grok/Gemini | GPT 的 fact/evidence/judgment 三种 | 编译器只消费 Judgment，fact/evidence 通过 evidence_refs 溯源 |
| 2 | 6 种关系类型 | 四方融合 | GPT 的 11 种 | 6 种覆盖所有语义，多余的可由 scope + 已有关系组合表达 |
| 3 | scope 三级 + 结构化 context | Claude 概念 + GPT 实现 | Grok 的纯条件数组 | 三级在概念上最清晰，结构化维度让编译器可查询 |
| 4 | 4 值 modality | Gemini | GPT 的 prefer/avoid | 判断必须是断言，不是建议 |
| 5 | 生命周期状态机 | GPT | — | 编译器必须知道判断是否可用 |
| 6 | freshness 三级 | Claude | — | 时效性的本质属性，与状态机互补 |
| 7 | target_versions | Gemini | — | 资源层判断的版本约束不可或缺 |
| 8 | consequence 结构化 | GPT | 纯字符串 | kind 枚举让编译器可按后果类型聚合 |
| 9 | hash 字段 | Gemini | — | 低成本检测内容变更 |
| 10 | Relation.description | Gemini | — | 给编译器 LLM 的因果上下文 |
