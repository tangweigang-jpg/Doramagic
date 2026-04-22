# 多模型调研综合报告：开源竞品分析 + 子代理拆分决策

> 日期：2026-04-12
> 研究方法：Grok、Gemini、GPT（Codex）、Claude Opus 四模型独立调研 + 交叉验证
> 输入资料：Blueprint Extraction SOP v3.2、Constraint Collection SOP v2.2、Doramagic 现有代码库
> 研究问题：
>   1. GitHub 上是否存在可直接实现这两个 SOP 的开源项目？
>   2. 蓝图提取和约束提取是否应该拆分为独立子代理？
>   3. 仅聚焦蓝图提取，是否有接近的开源项目？

---

## 0. 执行摘要

**四个模型的核心结论高度一致**：

1. **没有任何开源项目能直接替代 Doramagic 的两个 SOP**。Doramagic 的金融领域知识工程流水线（业务决策六类分类 + 审计清单 + 约束派生）在开源界属于原创/领先水平。
2. **应该拆分为两个独立子代理**。四个模型一致支持拆分，且均指出需要一个轻量协调层。
3. **存在大量高价值 building blocks 可复用**，但核心差异化层（M/BA/RC 分类、金融审计清单、missing gap 双联约束）必须自研。

**Doramagic 的真正护城河不是"代码分析"，而是"金融业务语义理解 + 结构化知识锻造"。**

---

## 1. 开源竞品全景分析

### 1.1 四模型推荐项目汇总（去重合并）

按**被推荐次数**和**匹配度**排序：

| 项目 | Grok | Gemini | GPT | Codex | 推荐次数 | 最佳用途 |
|------|:----:|:------:|:---:|:-----:|:--------:|---------|
| **ArchGuard / co-mate** | - | - | ✅ | - | 1 | 蓝图展示层 + 架构治理 + DSL 表达 |
| **Joern / Fraunhofer CPG** | - | - | ✅ | - | 1 | 底层代码图 + 语义引擎（调用链/数据流） |
| **CodeBoarding** | - | ✅ | - | - | 1 | 静态分析 + LLM 混合架构提取（最接近 SOP Step 2a） |
| **DeepWiki-Open** | - | - | - | ✅ | 1 | 仓库转 Wiki/文档（通用蓝图生成器参考） |
| **OpenDeepWiki** | - | - | - | ✅ | 1 | 代码知识库平台（UI/MCP/知识库参考） |
| **RepoAgent** | - | ✅ | - | ✅ | 2 | AST 分析 + 仓库级文档生成 + 增量更新 |
| **Autodoc** | - | ✅ | ✅ | - | 2 | LLM 驱动的 repo 文档生成 |
| **Semgrep** | - | ✅ | ✅ | ✅ | 3 | 约束验证执行层（machine_checkable） |
| **ast-grep** | ✅ | ✅ | ✅ | ✅ | 4 | AST 结构搜索 + 候选点发现 |
| **tree-sitter** | - | ✅ | ✅ | ✅ | 3 | 多语言 AST 解析底座 |
| **Repomix / Gitingest** | - | ✅ | - | ✅ | 2 | 仓库打包为 LLM 上下文 |
| **Instructor / Outlines** | - | ✅ | - | ✅ | 2 | LLM 结构化输出 + Pydantic 校验 |
| **LangGraph** | ✅ | ✅ | - | - | 2 | 多步 Agent 流水线编排 |
| **Promptfoo + LiteLLM** | - | ✅ | - | - | 1 | 多模型评审 |
| **CodeQL** | - | - | ✅ | ✅ | 2 | 语义查询 + 约束可验证化 |
| **neo4j-labs/llm-graph-builder** | ✅ | - | - | - | 1 | 非结构化内容转 KG |
| **Zep/graphiti** | ✅ | - | - | - | 1 | 时序知识图谱（约束图替代方案） |
| **Google/langextract** | ✅ | - | - | - | 1 | 结构化提取 + source grounding |
| **OPA/Conftest** | - | - | - | ✅ | 1 | YAML/JSONL 质量门禁 |
| **n8n workflow** | - | ✅ | - | - | 1 | evidence-based 架构蓝图生成（Claude 驱动） |
| **Azure agent-architecture-review** | ✅ | ✅ | - | - | 2 | Agentic 架构评审 + 交互图 |
| **Zoekt / OpenGrok** | - | - | ✅ | ✅ | 2 | 大仓库检索 |
| **ctags** | - | - | ✅ | ✅ | 2 | 符号索引 |
| **aider repo-map** | - | - | - | ✅ | 1 | Tree-sitter 仓库结构地图 |

### 1.2 按 SOP 步骤的能力映射

#### Blueprint Extraction SOP v3.2

| SOP 步骤 | 可复用的开源项目 | 复用程度 | 自研必要性 |
|---------|----------------|---------|-----------|
| Step 0: Clone + 指纹探针 | Repomix, Gitingest, code2prompt | 高 | 低（指纹关键词匹配需自研） |
| Step 1: 索引预处理 | tree-sitter, ast-grep, ctags, aider repo-map | 高 | 低 |
| Step 2a: 架构提取 | CodeBoarding, DeepWiki, Joern/CPG, RepoAgent | 中 | 中（LLM 探索逻辑自研） |
| Step 2b: 声明验证 | langextract（source grounding） | 低 | **高（闭环验证无现成方案）** |
| Step 2c: 业务决策标注 | **无** | 无 | **极高（T/B/BA/DK/RC/M 分类完全独创）** |
| Step 2d: 用例扫描 | DeepWiki（部分） | 低 | 高 |
| Step 3: 自动验证 | Semgrep, ast-grep, CodeQL | 中 | 中 |
| Step 4: YAML 组装 | Instructor/Outlines（结构化输出） | 中 | 中 |
| Step 5: 一致性检查 | OPA/Conftest | 中 | 中 |
| Step 6: 多模型评审 | Promptfoo + LiteLLM | 高 | 低 |

#### Constraint Collection SOP v2.2

| SOP 步骤 | 可复用的开源项目 | 复用程度 | 自研必要性 |
|---------|----------------|---------|-----------|
| Step 1: 加载蓝图 | Pydantic（已有） | 高 | 低 |
| Step 2.1-2.3: 代码约束提取 | Semgrep, CodeQL, ast-grep | 中 | 高（金融语义层自研） |
| Step 2.4: 业务约束派生 | **无** | 无 | **极高（missing gap 双联约束独创）** |
| Step 2.5: 审计约束转化 | **无** | 无 | **极高（69 项金融审计清单独创）** |
| Step 3: 入库 | Instructor/Outlines + Pydantic | 高 | 低 |
| Step 4: 后处理修复 | OPA/Conftest | 中 | 中 |
| Step 5: 质量验证 | OPA/Conftest | 中 | 高（质量基线自研） |

### 1.3 复用率估算（四模型平均）

| 模型 | Blueprint 可复用 | Constraint 可复用 | 核心自研 |
|------|:---------------:|:-----------------:|:--------:|
| Grok | 60-80% | 未明确 | 20-40% |
| Gemini | 未明确 | 未明确 | L3-L6 必须自建 |
| GPT | 未明确 | 未明确 | 40-60% 必须自研 |
| Codex | 50-60% | 35-45% | 40-60% 必须自研 |
| **综合判断** | **~55%** | **~40%** | **核心 45-60% 必须自研** |

---

## 2. 子代理拆分决策分析

### 2.1 四模型一致结论

| 模型 | 是否拆分 | 架构建议 | 关键论据 |
|------|:-------:|---------|---------|
| Grok | **是** | Orchestrator + BlueprintAgent + ConstraintAgent | 认知负载正交、Prompt 爆炸、SOP 已隐含边界 |
| Gemini | **是** | Orchestrator → BlueprintAgent → 人工门 → ConstraintAgent | 数据严格依赖、认知模式不同（归纳 vs 演绎）、错误隔离 |
| GPT | **是** | BlueprintAgent + ConstraintAgent + 轻量协调层 | 任务姿态冲突（抽象 vs 穷举）、错误代价不同 |
| Codex | **是** | Blueprint 作为硬 contract，Constraint 作为下游 consumer | 文件/Schema 交接、不用自然语言记忆交接 |

**共识度：4/4，100% 一致。**

### 2.2 拆分理由交叉验证

按独立提出的次数排序：

| 拆分理由 | Grok | Gemini | GPT | Codex | 提出次数 |
|---------|:----:|:------:|:---:|:-----:|:--------:|
| 认知模式/任务本质不同 | ✅ | ✅ | ✅ | ✅ | 4 |
| 错误隔离 | ✅ | ✅ | ✅ | ✅ | 4 |
| 输出格式完全不同（YAML vs JSONL） | ✅ | ✅ | ✅ | ✅ | 4 |
| SOP 已隐含拆分边界 | ✅ | ✅ | ✅ | ✅ | 4 |
| 可独立迭代（SOP 版本号不同） | ✅ | ✅ | - | - | 2 |
| Context 窗口限制 | ✅ | ✅ | - | - | 2 |
| 严格数据依赖（不可并行） | - | ✅ | ✅ | ✅ | 3 |
| 可扩展性（新领域复用） | ✅ | - | - | - | 1 |

### 2.3 推荐架构（四模型综合）

```
Orchestrator（轻量编排层）
  │
  ├── Phase 1: BlueprintAgent（蓝图提取代理）
  │     ├── 内部子代理 1: 架构提取（Step 2a）
  │     ├── 内部子代理 2: 声明验证（Step 2b）
  │     ├── 内部子代理 3: 业务决策标注（Step 2c）
  │     ├── 内部子代理 4: 用例扫描（Step 2d）
  │     └── 输出: blueprint.yaml + verification artifacts
  │
  │   ← 【质量门 / 人工确认点】
  │
  ├── Phase 2: ConstraintAgent（约束提取代理）
  │     ├── 内部子代理 A-N: per-stage 约束提取（可并行）
  │     ├── 内部子代理: edges/global/claim_boundary
  │     ├── 内部子代理: 业务约束派生（Step 2.4）
  │     └── 输出: constraints.jsonl + validation_report.json
  │
  └── Phase 3: 一致性校验（轻量）
        ├── 蓝图 BD 覆盖率检查
        ├── 约束引用的 stage 存在性检查
        └── RC/M/BA 派生完整性检查
```

### 2.4 关键设计约束（四模型共识）

1. **文件/Schema 交接，不用自然语言记忆交接**（Codex 强调）
2. **Blueprint 是硬 contract**，Constraint 只能基于已验证的蓝图工件继续（全部强调）
3. **蓝图阶段必须有质量门/人工确认**，防止错误传播到约束（Gemini/GPT 强调）
4. **约束 stages 可内部并行**，蓝图→约束必须串行（全部强调）
5. **协调层必须有一致性检查**，防止两个 agent 各自正确但整体错误（GPT 强调）

---

## 3. 蓝图提取专项分析

### 3.1 最接近的开源项目（跨模型排名）

| 排名 | 项目 | 推荐模型 | 接近维度 | 关键差距 |
|------|------|---------|---------|---------|
| 1 | **CodeBoarding** | Gemini | 静态分析 + LLM 混合、Agent Tooling Interface、多语言 LSP、增量分析 | 无声明验证、无业务决策分类、无金融 checklist |
| 2 | **DeepWiki-Open** | Codex | 克隆→分析→文档→Mermaid 图→RAG | 产出是 Wiki 不是 Blueprint YAML |
| 3 | **ArchGuard** | GPT | 最接近"蓝图形态"：架构扫描、组件/包/类分析、规则治理 | 不做金融业务逻辑抽取 |
| 4 | **Joern / CPG** | GPT | 底层代码图引擎：调用链、数据流、跨语言 | 偏程序分析，不偏业务解释 |
| 5 | **RepoAgent** | Gemini, Codex | AST 分析 + 仓库级文档 + 增量更新 | 文件级文档，非架构级骨架 |
| 6 | **n8n workflow** | Gemini | evidence-based architecture blueprint + 反幻觉 | 无金融 checklist、无精细验证 |
| 7 | **co-mate** | GPT | AI 架构 copilot + DSL/规格表达 | 不是成熟抽取器 |

### 3.2 核心差距分析

**所有候选项目的共同缺失**（Doramagic 独有）：

| 能力 | 说明 | 竞品状态 |
|------|------|---------|
| T/B/BA/DK/RC/M 六类业务决策分类 | 金融领域专有的决策分类框架 | **全球独创，无任何开源实现** |
| 69 项金融审计清单 | 20 项通用 + 7 子领域各项专审 | **纯领域知识壁垒** |
| 声明验证闭环（Step 2b） | LLM 产出 → 源码逐条验证 → 修正 | **流程创新，无现成方案** |
| missing gap 双联约束 | 蓝图中未覆盖但应存在的约束自动派生 | **工程创新** |
| evidence 双锚点（file:line + function） | 每个 BD/约束必须有可追溯的源码证据 | 部分项目有 source grounding，但不如 Doramagic 严格 |
| A 股 11 项硬规则 | 涨跌停、T+1、印花税等特化规则 | **领域独有** |

### 3.3 Doramagic 与 CodeBoarding（最接近项目）逐步对比

| SOP 步骤 | Doramagic | CodeBoarding | 差距 |
|---------|-----------|-------------|------|
| Clone + 指纹 | 7 子领域关键词匹配 | 支持 local/remote | CodeBoarding 无指纹 |
| 结构索引 | AST + 依赖图 + Math 检测 | LSP-based 多语言 | CodeBoarding 更强（LSP > AST） |
| 架构提取 | LLM agentic 探索 + 工具调用 | 静态分析 + LLM | 各有优势 |
| 声明验证 | 完整闭环 | **无** | Doramagic 独有 |
| 业务决策 | 六类分类 + 金融 checklist | **无** | Doramagic 独有 |
| 用例扫描 | examples/notebooks/tutorials | **无** | Doramagic 独有 |
| YAML 组装 | 严格 schema + 一致性检查 | Markdown 输出 | Doramagic 更严格 |
| 多模型评审 | v3 harness + failover | **无** | Doramagic 独有 |

---

## 4. 技术建议综合

### 4.1 可立即吸收的开源能力（按优先级）

| 优先级 | 能力 | 推荐项目 | 集成方式 | 预估收益 |
|:------:|------|---------|---------|---------|
| P0 | AST 结构搜索 | ast-grep | 替代 SOP 中的 `grep -rn` | 精确度 + 速度提升 |
| P0 | LLM 结构化输出 | Instructor | BD/约束 JSON 输出层 | 减少后处理修复 |
| P1 | 多模型评审 | Promptfoo + LiteLLM | Step 6 评审自动化 | 评审效率 |
| P1 | YAML/JSONL 门禁 | OPA/Conftest | 质量门禁外置 | 规则可维护性 |
| P2 | 仓库上下文压缩 | Repomix / aider repo-map | 大仓库预处理 | token 节省 |
| P2 | 约束验证执行 | Semgrep | machine_checkable 约束 | 验证自动化 |
| P3 | 底层代码图 | Joern / CPG | 调用链 + 数据流分析 | 证据质量 |

### 4.2 不建议做的事

1. **不要 fork DeepWiki/OpenDeepWiki 当主框架** — 它们产出"人读的 Wiki"，Doramagic 产出"AI 消费的结构化 Blueprint"，方向相近但终点不同
2. **不要换 LangGraph/CrewAI 底座** — Doramagic 已有 SOPExecutor，切换底座代价大于收益
3. **不要试图从零复用通用 KG 框架** — neo4j/graphiti 适合做后端存储，但约束派生逻辑必须自研
4. **不要低估自研部分的价值** — 45-60% 的自研比例恰好说明 Doramagic 的核心竞争力所在

### 4.3 与现有 v4.1 架构的对齐

当前 v4.1 已有的能力与开源建议的对比：

| 开源建议 | Doramagic 现状 | 判断 |
|---------|--------------|------|
| tree-sitter / ast-grep 做 AST | 已有 `tools/indexer.py`（Python ast 模块） | 当前够用，多语言时再升级 |
| Instructor 做结构化输出 | 已有 Pydantic schema + `_extract_json()` 兜底 | 可考虑集成 |
| LangGraph 做编排 | 已有 SOPExecutor + Phase DAG | 不换 |
| Repomix 做上下文 | 已有 `tools/sources.py` + worker 并行 | 当前更贴合 |
| Semgrep 做验证 | 已有 `bp_auto_verify` (Python) | P2 可升级 |

---

## 5. 与 Doramagic 待讨论问题的关系

### 问题 1：蓝图/约束是否拆分？

**答案明确：拆。** 四模型 100% 一致。当前 `blueprint_phases.py` 和 `constraint_phases.py` 已经是两条独立 phase 链，下一步是把边界从"代码分离"升级为"子代理分离"：
- 独立的 agent 实例
- 独立的 context window
- 文件契约交接（blueprint.yaml 为唯一接口）
- 质量门阻断传播

### 问题 2：如何增加蓝图深度？

开源项目提供的启发：
- **CodeBoarding 的 LSP 分析**：比当前 AST 更深，可提取跨文件调用关系
- **Joern/CPG 的数据流分析**：可发现隐含的数据依赖
- **n8n workflow 的 evidence-first 机制**：每条产出必须有文件证据
- **当前 v4.1 的 30KB vs 111KB 差距**主要在 stage 详情和 use_cases，这些不是开源能解决的，是 worker prompt 深度问题

### 问题 3：约束管线 v4 式重构？

四模型均支持约束 stages 并行化：
- 约束 stages 互相独立（已有 `parallel_group` 机制）
- 拆分为独立子代理后，约束管线可以完全并行
- 预期 42 min → 4-6 min

---

## 6. 最终结论

### Doramagic 的竞争定位

```
  通用代码分析          Doramagic 位置          金融业务知识
  ←───────────────────────●──────────────────────────→

  CodeBoarding            │                    无开源竞品
  DeepWiki                │
  ArchGuard               │
  Joern/CPG               │
                          │
                    ┌─────┴─────┐
                    │ 这个区间   │
                    │ 是护城河   │
                    └───────────┘
                    业务决策分类
                    金融审计清单
                    约束派生体系
                    声明验证闭环
```

**一句话**：GitHub 上有大量"代码→结构"的工具，但没有"代码→金融业务知识"的工具。Doramagic 占据的正是这个空白地带。

---

*报告结束。基于此报告，建议进入三个架构问题的具体讨论。*
