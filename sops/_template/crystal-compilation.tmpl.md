# 晶体编译 SOP（通用模板 v3.2）

> **本文件是维护用模板，不直接执行。**
> 执行时请使用对应领域的完整 SOP（如 `finance/crystal-compilation-sop.md`）。
>
> 模板版本：基于 SOP v3.1
> 用途：新增领域时，从本模板出发 + 注入领域知识 → 生成领域 SOP
>
> 模板注入点标记格式：`<!-- DOMAIN: 说明 -->`
> 编译新领域 SOP 时，将所有注入点替换为领域特定内容。

---

## 前置依赖

执行本 SOP 前需了解以下蓝图 schema 字段：

| 字段 | 含义（跨领域语义） |
|------|------------------|
| `business_decisions` | 蓝图中标注的设计决策列表 |
| `type=T` | 技术选择——纯工程实现方案（如用 SQLite 还是 PostgreSQL） |
| `type=B` | 业务决策——影响最终产出行为的主动选择（如先卖后买、SSR vs CSR） |
| `type=BA` | 业务假设——可能不成立的隐含前提（如固定滑点 0.1%、所有用户有 Node 18+） |
| `type=DK` | 领域知识——领域事实（如 A 股换手率是核心指标、REST API 幂等性） |
| `type=RC` | 外部强制规则——法规/平台/标准强制（如印花税率、GDPR、WCAG、App Store 审核规则） |
| `type=M` | 数学/模型选择——基于数学推导或统计假设的方法选择（如 MACD 参数、BS 定价模型、WoE 公式） |
| `known_use_cases` | 蓝图中索引的典型使用场景 |
| `negative_keywords` | 用例消歧——与该用例容易混淆的其他用例的关键词 |
| `disambiguation` | 用例消歧——当用户意图可能匹配多个用例时应问的消歧问题 |
| `data_domain` | 用例依赖的数据类型 |
| `must_validate` | 每个 use case 中列出的验收要点 |
| `known_gap` | 蓝图中标注的已知缺失/风险 |
| `severity` | 约束的严重程度（fatal/critical/high/medium） |
| `validation_threshold` | 约束异常判定阈值（可选，用于产出数据质量校验） |

---

## 核心原则

**晶体 = 好的蓝图 + 好的资源 + 好的约束 + 好的 Harness**

四层缺一不可。Harness 是让知识正确发挥作用的手段，**不能替代知识本身**。
晶体的核心价值是让 AI 获得它原本没有的领域知识。

Harness 包含五个子系统：
1. **Execution Contract** — 参数锁 + 交付门禁
2. **Failure Taxonomy** — 失败分类 + 恢复动作
3. **Stage Spec** — 阶段拓扑 + 流控 + checkpoint
4. **State Semantics** — 制品状态持久化 + 恢复语义
5. **Host Adapter** — 宿主能力适配 + 工具人因工程

---

## 适用范围

| 领域 | 蓝图来源示例 | 典型任务类型 | 典型交付物 |
|------|-------------|-------------|-----------|
| 金融量化 | zvt、zipline、freqtrade | 脚本执行 | 回测脚本 + 指标 |
| Web 开发 | Next.js、Django、FastAPI | 迭代构建 | 可运行应用 |
| 数据工程 | Airflow、dbt、Dagster | 声明式配置 | 数据管线 |
| AI/ML | LangChain、LlamaIndex、DSPy | 迭代构建 | RAG/Agent 系统 |
| 移动端 | React Native、Flutter | 迭代构建 | 可编译应用 |
| DevOps | Kubernetes、Terraform | 声明式配置 | 基础设施配置 |

<!-- DOMAIN: 此处可追加本领域的典型任务类型和交付物说明 -->

---

## 输入

| 输入 | 来源 | 要求 |
|------|------|------|
| Blueprint YAML | 蓝图提取 SOP | 含 business_decisions + known_use_cases |
| Constraints JSON/JSONL | 约束采集 SOP | 含 severity、constraint_kind、stage_ids |
| Resources | 蓝图 replaceable_points | 含 options、fit_for |
| User Intent | 用户/产品经理 | 目标环境、任务类型、产出类型 |
| Target Host | 部署决策 | openclaw / claude_code / generic |
| Host Spec | `docs/research/host-specs/{host}-host-spec.md` | 宿主能力规范，不编撰 |

## 输出

| 输出 | 格式 | 用途 |
|------|------|------|
| Crystal IR | `crystal-{id}.ir.yaml` | 结构化中间表示 |
| seed.md | **单文件自包含**（产品宪法 §3.4） | 所有知识内联，用户丢一个 md 文件给 AI 即可用 |

---

## Step 0: Compilation Language Policy

### 0a. Crystal Prose Language

**Default compilation language: English.**

Crystals are consumed by AI systems worldwide. English maximizes global AI consumption reach.

**Language-neutral elements (no translation needed)**:
- YAML/JSON keys and identifiers (`stage_ids`, `constraint_kind`, `severity`, `spec_lock` param names)
- Code examples, pseudocode, API signatures
- File paths, variable names, framework-specific terms
- Evidence references (`evidence_refs` locators)

**Language-dependent elements (compile in English)**:
- Constraint prose: `core.when` / `core.action` / `core.consequence.description`
- Stage descriptions: `responsibility`, `name`, design decisions
- Blueprint descriptions: `description`, `not_suitable_for`
- Crystal directive text, context_acquisition questions
- Failure taxonomy descriptions and recovery actions
- Delivery gate descriptions

### 0b. Human Summary Locale

The `## Human Summary` section is the ONLY section using the user's locale language. Humans read this section; AI reads all other sections.

| Crystal section | Language | Audience |
|-----------------|----------|----------|
| `## Human Summary` | User's locale (default: zh) | Human |
| All other prose | English | AI |

### 0c. Source Knowledge Translation

When source knowledge (blueprints, constraints) is in a non-English language:

1. **Translate** `core.when` / `core.action` / `core.consequence.description` to English during compilation
2. **Preserve** the original text in a `_source_locale` annotation for traceability
3. **Technical accuracy > prose elegance** — domain terms must use established English equivalents
4. **Evidence preservation** — `evidence_refs` locators remain in original language (they point to source code/docs)

<!-- DOMAIN: 此处注入本领域的术语对照表（如金融：涨停=daily price limit up, 印花税=stamp duty） -->

### 0d. Crystal IR Language Metadata

Add to Crystal IR `metadata` block:

```yaml
metadata:
  compilation_language: "en"
  source_languages: ["{source_lang}"]
  human_summary_locale: "{user_locale}"
```

### 0e. Runtime Language Protocol

The crystal is compiled in English. The host AI interacts with the user in the user's language. Embed the following protocol in the crystal's `## directive` section:

```markdown
### Language Protocol

This crystal is written in English for universal AI consumption.

1. **Detect** the user's language from their first message or system locale
2. **All user-facing output** (questions, explanations, warnings, reports) MUST be in the user's detected language
3. **Intent matching**: translate user input to English semantically before matching against intent_router terms — do not require the user to speak English
4. **Code and identifiers** remain in English regardless of user language (variable names, file paths, API calls, assert statements)
5. **Domain terms**: use the user's language equivalent when explaining constraints or decisions (e.g., "look-ahead bias" → "前视偏差" for Chinese users, "先読みバイアス" for Japanese users)
```

**Design principle**: Host AI LLMs are natively multilingual — leverage this capability via protocol, do not compile multilingual crystals.

---

## Step 0.5: Compilation Intensity Preset

Select compilation intensity before starting. This determines which steps execute and at what depth.

### Presets

| Preset | When to use | Step coverage |
|--------|-------------|---------------|
| **scout** | First compilation of new blueprint, feasibility check | Steps 0-3 + 6 + 7 (IR only, no rendering) |
| **standard** | Production compilation of validated blueprints | Steps 0-9 (full pipeline) |
| **thorough** | New domain first compilation, >80 constraints, cross-project matching enabled | Steps 0-10 (full pipeline + efficacy test) |

### Preset Selection Rules

| Condition | Preset |
|-----------|--------|
| Blueprint has no prior crystal (first compilation) | **thorough** |
| Blueprint has validated crystal, incremental update only | **standard** |
| Exploratory compilation (testing new SOP version, new host) | **scout** |
| Cross-project constraint matching enabled (Step 6.6) | **thorough** (mandatory) |

Steps marked `min_preset: standard` or `min_preset: thorough` are skipped when running a lower-intensity preset.

---

## Step 0.7: Preflight Validation

Validate all inputs satisfy structural prerequisites before executing the compilation pipeline. Catch cheap errors before expensive LLM-driven steps.

### 0.7a. Input Existence Checks (deterministic, zero LLM cost)

| Check | Condition | On failure |
|-------|-----------|------------|
| Blueprint file exists | File at blueprint path is readable YAML | ABORT |
| Blueprint has `stages` | `stages` list is non-empty | ABORT |
| Blueprint has `source.projects` | Source project attribution exists | ABORT — violates traceability requirement |
| Constraint file exists | JSONL file at constraints path is readable | WARN — compile with zero constraints |
| Constraint schema version | All constraints have `schema_version >= "2.0"` | WARN — legacy constraints may have missing fields |
| Host Spec exists (if host specified) | Host spec file exists | ABORT — cannot adapt without host spec |

### 0.7b. Structural Consistency Checks (deterministic)

| Check | Condition | On failure |
|-------|-----------|------------|
| stage_id referential integrity | Every constraint `applies_to.stage_ids` entry exists in blueprint `stages` | WARN — orphan constraints dropped |
| Business decisions exist | Blueprint has `business_decisions` field | WARN — compile without spec_lock (degraded) |
| Known use cases exist | Blueprint has `known_use_cases` field | WARN — intent_router single generic entry |
| Constraint count sanity | Domain has >0 constraints matching this blueprint | WARN — knowledge-poor crystal |

### 0.7c. Cross-Project Readiness (only when thorough preset + Step 6.6 enabled)

| Check | Condition | On failure |
|-------|-----------|------------|
| Domain constraint pool loaded | Full domain JSONL loaded successfully | ABORT — cross-project requires full pool |
| Blueprint stage vocabulary extracted | Blueprint stage_ids available for matching | ABORT — no matching dimensions |
| Minimum pool size | Domain has >=100 constraints from >=3 blueprints | WARN — cross-project may not add value |

All preflight checks MUST pass (or degrade to WARN with documented rationale) before proceeding to Step 1.

---

## Step 0.8: Intelligence Judgment Protocol

本 SOP 中所有涉及"智能判断"（语义相似度、相关性打分、意图排序、LLM-as-Judge 等）的步骤必须使用本节统一执行器规范。未按本协议执行的判断步骤视为违反 SOP 并必须返工。

### 0.8a 判断类型分类

| 判断类型 | 实现方式 | 适用位置 |
|---------|---------|---------|
| **语义相似度**（boolean threshold）| LLM 一次性打分（0.0-1.0），threshold 由调用方指定 | Step 6a 聚合去重（> 0.85 合并） |
| **多维度加权打分**（连续值）| LLM 按维度独立打分 + 脚本加权求和 | Step 6.6b relevance scoring（5 维度加权 0.35/0.20/0.15/0.20/0.10） |
| **Top-k 排序**（相对比较）| LLM 对候选集一次性排序输出名次 | Step 6.5d intent_router 消歧（top-1 与 top-2 差距 < 20%） |
| **Rubric-based Judge**（结构化评判）| LLM-as-Judge + 显式 rubric + JSON 输出 | Step 1b Soft Gate |

### 0.8b 统一 Judge Prompt 模板

```prompt
你是 Doramagic 晶体编译的智能判断执行器。

## 判断类型
{type}  # similarity / weighted_scoring / ranking / rubric_judge

## 输入
{structured_input}

## 输出规范
必须输出合法 JSON，格式：
{
  "judgment": <具体值类型，见下>,
  "confidence": 0.0-1.0,
  "reasoning": "简述判断依据（≤50 字）"
}

## 值类型
- similarity       → {"score": 0.0-1.0}
- weighted_scoring → {"dimensions": {"dim_1": 0.0-1.0, ...}, "weighted_total": 0.0-1.0}
- ranking          → {"ranked_ids": ["id_1", "id_2", ...]}
- rubric_judge     → {"passed": true/false, "rubric_scores": {"dim_1": 1-5, ...}}
```

### 0.8c 复现性保障

| 规则 | 标准 |
|------|------|
| 模型 | 使用与编译主线同一 LLM（默认 Claude 4.5 或 GPT-4.5），不用宿主 AI |
| 温度 | `temperature = 0.0` |
| 种子 | 模型支持 seed 时锁定 `seed = 42` |
| 多数投票 | 同一判断重复 3 次，similarity/scoring 取中位数，ranking 取众数 |
| 缓存 | 相同输入缓存结果，避免重复调用 |

### 0.8d Soft Gate Rubric 强制字段

每条 Soft Gate 必须含以下字段，否则 Step 1b 不予接纳：

```yaml
soft_gate:
  id: "SG-{N}"
  description: "{gate 目标}"
  rubric:
    dimensions:
      - name: "{维度 1 名称}"
        scale: "1-5"
        anchors:
          1: "{1 分锚点说明}"
          3: "{3 分锚点说明}"
          5: "{5 分锚点说明}"
    passing_threshold: "所有维度均 >= 4"
  judge_prompt: "{该 gate 专用的 judge prompt，含 rubric 锚点}"
```

### 0.8e 无执行器降级

编译环境不具备 Intelligence Judgment 执行能力时（纯脚本流水线 / LLM 不可用）：
- 所有相关判断步骤降级为 WARN 级标注
- IR metadata 标注 `intelligence_judgment_deferred: true`
- 人工审查员在晶体发布前离线完成所有 deferred 判断

---

## Step 1: Execution Contract 编写

### 1a. Spec Lock 提取

**输入**：蓝图 `business_decisions` 中 type=B、type=BA 或 type=M 的条目。

**双层结构**（教训 L27）：Spec Lock 分为两层：
- **semantic_locks**：业务规则层（不可更改的业务语义），violation=FATAL
- **implementation_hints**：实现建议层（框架 API 最佳实践），violation=WARN

**可漂移参数的判断元准则**（领域无关）：

一个参数是否需要锁定，取决于以下三个条件，**满足任一即锁**：

| 元准则 | 说明 | 金融例 | Web 例 | 数据例 |
|--------|------|--------|--------|--------|
| **(a) AI 无约束时会自主选择** | AI 有自己的"默认偏好"，会偏离用户意图 | TOP_N=5→AI 改 30 | App Router→AI 用 Pages Router | materialization=view→AI 改 table |
| **(b) 不同选择导致结果不可比较** | 参数变化后产出的性质发生质变 | 动量策略→布林带策略 | SSR→CSR（SEO 完全不同） | incremental→full refresh |
| **(c) 与用户意图直接绑定** | 用户明确要求了这个值 | "A 股回测" | "TypeScript 项目" | "每日增量更新" |

<!-- DOMAIN: 此处注入本领域典型的可漂移参数列表及其锁定理由 -->

**格式**：
```yaml
- param: {参数名}
  value: {锁定值}
  violation: FATAL | WARN
  rationale: {为什么锁}
```

**规则**：
- type=RC（外部强制规则）→ 一律 `violation: FATAL`，归入 semantic_locks
- type=M（数学/模型选择）→ 默认 `violation: FATAL`，归入 semantic_locks（教训 L27）
- 框架 API 惯用法、配置最佳实践 → 归入 implementation_hints，`violation: WARN`
- 路径参数使用 `{workspace}` 占位符

### 1b. Delivery Gate 提取

**输入**：`known_use_cases[target].must_validate` + severity=fatal 约束 + validation_threshold 字段 + machine_checkable/promote_to_acceptance 字段。

**三类通用 Gate**（领域无关）：

| Gate 类别 | 说明 | 金融例 | Web 例 | 数据例 |
|-----------|------|--------|--------|--------|
| **产出存在性** | 交付物文件/服务/端点存在 | 结果文件存在 | `next build` 成功 | 所有 model 编译通过 |
| **执行正确性** | 主流程无错误完成 | 回测完成无异常 | `curl localhost:3000` 返回 200 | `dbt test` 全部通过 |
| **业务合理性** | 结果不是"表面通过实际无效" | abs(return)>1%, trades>0 | 页面有实际内容（非空白） | 输出行数>0, 无全 NULL 列 |

<!-- DOMAIN: 此处注入本领域典型 Hard Gate 示例 -->

**Hard Gate vs Soft Gate**：

| 类型 | 定义 | on_fail | 适用场景 |
|------|------|---------|---------|
| **Hard Gate** | 可程序化验证（exit code / regex / 数值比较） | RERUN / REBUILD | 构建成功、指标阈值、文件存在 |
| **Soft Gate** | 需要 AI self-check 或 LLM-as-Judge | WARN + 输出评估报告 | 架构一致性、代码质量、设计意图符合 |

每个晶体至少 3 条 Hard Gate。Soft Gate 可选但必须有明确 rubric。

**Hard Gate 补充来源**：

| 约束字段值 | 处理 |
|------------|------|
| `machine_checkable=true` 且 `severity >= high` | 自动列入 Hard Gate 候选 |
| `promote_to_acceptance=true` | 强制纳入 Hard Gate，不可省略 |
| M 类 BD 含具体参数 | 通过 grep 源码验证，纳入 Hard Gate |

**Output Validator Gate 强制结构**（任务产出含可量化数值结果时必须存在）：

任务交付物含数值结果（回测 metrics、数据管线行数、ML 训练 metrics、API 响应字段等）时，Hard Gate 必须包含以下 G1-G4 全部四条：

| Gate ID | 检查内容 | 验证方式 |
|---------|---------|---------|
| **G1** | 主结果文件存在且非空 | filesystem 检查 + size > 0 |
| **G2** | `{result_path}.validation_passed` 标记文件存在 | filesystem 检查 |
| **G3** | 主脚本含 `from validate import enforce_validation` 调用 | grep 字面字符串 |
| **G4** | 主脚本末尾含 `# === DO NOT MODIFY BELOW THIS LINE ===` 围栏 | grep 字面字符串 |

G1-G2 验证产出与验证标记同时存在；G3-G4 验证 Output Validator 调用链未被宿主 AI 移除。Validator Scaffold 渲染规则见 Step 8e。

**FATAL 阈值卡位规则**（每条进入 Hard Gate 的 validation_threshold 必须满足）：

| 卡位依据（三选一） | 例 |
|------------------|-----|
| 物理意义不可能 | 持仓比例 > 100%、abs(drawdown) > 100%、行数为负 |
| 合法历史观察上限的 5 倍以上 | 年化 abs(return) > 500% |
| 数据完整性破坏 | result 行数为 0、关键列全 NaN、unique 值 = 1 |

<!-- DOMAIN: 此处注入本领域的 FATAL 阈值卡位示例 -->

不满足上述任一依据的阈值降级为 Soft Gate 走 LLM-as-Judge，禁止进入 Hard Gate。

---

## Step 2: Failure Taxonomy 编写

### 2a. 通用失败类（8 条，领域无关）

| 失败类 | 触发条件 | 恢复动作 | 禁止动作 |
|--------|---------|---------|---------|
| `exec_rejected` | 宿主拒绝执行命令 | 重写命令为白名单格式 | 不重试相同命令 |
| `param_drift` | spec_lock 参数偏离锁定值 | 立即恢复锁定值 | 不辩解修改理由 |
| `timeout_risk` | 预估剩余工作 > 50% 时间预算 | 简化方案 | 不增加工具调用 |
| `framework_dead_end` | 框架/依赖错误重试 2 次仍失败 | 切换替代方案 | 不继续重试 |
| `mode_switch` | 产出文档/分析而非可执行交付物 | 删除文档，重新生成交付物 | 不产出参考文档 |
| `silent_drift` | 架构/方法偏离规格但未报错 | 对照 spec_lock 逐项检查 | 不假设"接近"可以 |
| `model_misuse` | 数学模型/算法被替换为不等价方法 | 恢复蓝图指定的模型/方法，不做"等效替换" | 不辩解"更好的方法" |
| `false_completion_claim` | AI 声明完成但未执行 Output Validator 调用链；或 result.csv 存在但无 validation_passed 标记文件 | 回到 Output Validator 阶段执行 enforce_validation，列出未通过的 Hard Gate | 不以"看起来对"或"显然完成"为由确认完成 |

### 2b. 领域特定失败类派生

从蓝图 `known_gap=true` + 约束 severity=fatal/critical 派生。每条必须有**具体 recovery action**。

<!-- DOMAIN: 此处注入本领域典型的领域特定失败类 -->

### 2c. Rationalization Guards 映射

**输入**：约束池中 `constraint_kind = rationalization_guard` 的条目。每条含 `guard_pattern.{excuse, rebuttal, red_flags, violation_detector}` 四字段。

**派生规则**：每条 rationalization_guard 约束派生 1 条 domain-specific failure class，补充到 Step 2b 的输出列表。

| failure class 字段 | 从 guard_pattern 派生 |
|------------------|---------------------|
| `name` | 基于 excuse 主题短语 |
| `trigger` | red_flags 全部列出 + violation_detector 描述 |
| `recovery` | rebuttal 原文 |
| `prohibited` | "禁止以 excuse 为由" + excuse 原文 |

**派生示例格式**：

```yaml
- name: premature_completion_claim
  trigger:
    - "AI 声称任务完成但缺少验证步骤"
  violation_detector: "未执行 enforce_validation 调用"
  recovery: "回到 Output Validator 步骤执行 enforce_validation"
  prohibited: "禁止以'测试冗余'或'显然正确'为由跳过验证"
```

**min_preset**：standard。scout 预设跳过本步骤。

**不去重规则**：一条 rationalization_guard 派生的 failure class 与一条 Step 2a 通用失败类（silent_drift / mode_switch / model_misuse）指向同一行为时，两条均保留。

---

## Step 3: 任务类型判断 + Stage Spec

### 3a. 任务类型判断

在设计阶段拓扑前，先判断任务类型：

| 类型 | 特征 | 典型场景 | 流控模式 |
|------|------|---------|---------|
| **A：一次性产出** | 输入确定→处理→输出确定 | 回测、报告生成、数据转换、脚手架生成 | **Pipeline** |
| **B：迭代构建** | 需要写→测→改循环 | Web 应用、移动端应用、重构、AI 系统 | **Iterative** |
| **C：声明式配置** | 产出是配置文件/DAG/规则 | dbt、Terraform、K8s、CI/CD | **Declarative** |

<!-- DOMAIN: 此处标注本领域最常见的任务类型（如量化金融通常是 A：Pipeline）-->

### 3b. 三种流控模式

**Pipeline 模式**（类型 A）：
```
setup → execute → validate → deliver
```
严格顺序，禁止回退。

**Iterative 模式**（类型 B）：
```
setup → scaffold → [loop: implement ↔ test, max_iterations=N] → deliver
```
implement↔test 允许内循环，必须声明 `max_iterations`。

**Declarative 模式**（类型 C）：
```
analyze → generate → verify → apply
```
generate 产出配置文件，verify 做 dry-run/lint，apply 提交。

### 3c. 通用规则

- 最多 4-5 个阶段
- 每阶段定义 goal / actions / exit_criterion / budget_ratio
- budget_ratio 之和 = 1.0，基于 Host Spec 的真实 timeout
- **禁止可选扩展阶段**（L3 教训）
- 时间预算从 Host Spec 读取，不编撰（L9 教训）

### 3d. Checkpoint 语义（durable execution）

每个 stage 必须声明 checkpoint 行为，使任务在中断后可恢复：

| 字段 | 说明 | 必填 |
|------|------|------|
| `checkpoint_artifact` | 本阶段完成后应持久化的制品路径 | 是 |
| `resume_condition` | 恢复时的前置检查 | 是 |
| `resume_action` | 恢复时的动作：skip / resume / rerun | 是 |

**三种 resume_action**：

| 动作 | 适用场景 |
|------|---------|
| **skip** | 该阶段产出幂等，制品存在即可跳过 |
| **resume** | 可以从中间状态继续 |
| **rerun** | 必须完全重新执行 |

<!-- DOMAIN: 此处注入本领域典型的 checkpoint 配置示例 -->

### 3e. Forced Checkpoint Injection (Iterative mode only)

> **min_preset**: standard

For Iterative mode (type B) stages with `resume_action: resume`, declare a forced checkpoint policy:

```yaml
forced_checkpoint:
  trigger: "every {N} tool calls without artifact_emission event"
  N: 10
  action: "write partial artifact to checkpoint_artifact path"
  on_empty_artifact: "emit WARN to trace + write diagnostic snapshot to .state/stall_diagnostic.json"
```

**Calibration rule**: N = 10 for `implement_test_loop` stages (expected dense tool use); N = 5 for `setup` stages (should converge fast).

---

## Step 4: State Semantics 编写

**核心命题**：关键状态必须**外化为文件制品**（artifact-backed state），使状态可持久、可恢复、可审计。

### 4a. State Slot 设计

| 字段 | 说明 |
|------|------|
| `slot_id` | 唯一标识（plan / result / evidence / manifest） |
| `path` | 文件路径模板（使用 `{workspace}` 占位符） |
| `purpose` | 该状态的职责（一句话） |
| `write_stage` | 哪个阶段写入 |
| `read_stages` | 哪些阶段读取 |
| `format` | json / yaml / markdown / csv |
| `compaction_stable` | 是否在上下文压缩后仍需可访问 |

### 4b. 四类通用 State Slot

| Slot 类型 | 职责 | compaction_stable | 适用任务类型 |
|-----------|------|-------------------|-------------|
| **Plan** | 任务分解、步骤清单、进度标记 | true | B（迭代构建）必须，A/C 可选 |
| **Working Memory** | 中间计算结果、临时发现 | false | 长时间任务推荐 |
| **Evidence** | 验证结果、测试输出 | true | 有 Soft Gate 时必须 |
| **Result Manifest** | 最终交付物清单 + 元数据 | true | 所有任务类型推荐 |

### 4c. Compaction Stability 规则

标记为 `compaction_stable: true` 的 slot 必须满足：
1. **自包含**：单独读取该文件即可理解状态
2. **结构化**：使用 JSON/YAML/表格，不是自由散文
3. **可增量更新**：AI 可以 read → modify → write

**反模式**：把进度写在对话中；state 文件内容依赖"之前聊过的"；state 文件用散文描述进度

### 4d. State Lifecycle 规则

| 规则 | 说明 |
|------|------|
| **创建即声明** | state slot 在 Crystal IR 中预声明，不是运行时随意创建 |
| **写入即 checkpoint** | 每次写入 state 文件等价于创建一个 checkpoint |
| **读取优先于记忆** | AI 应 read state 文件获取状态，不应从上下文"回忆" |
| **冲突以文件为准** | 如果上下文记忆与 state 文件矛盾，以文件为准 |

<!-- DOMAIN: 此处注入本领域典型的 state_slots 设计示例 -->

---

## Step 5: Host Adapter 编写

### 5a. 基本适配

```yaml
host_adapters:
  {host_name}:
    spec_ref: "docs/research/host-specs/{host}-host-spec.md"
    timeout_seconds: {从 Host Spec 读取}
    exec_rules:
      whitelist: [...]
    path_template: "{workspace}/{filename}"
```

**{workspace} 解析规则**：

| 渲染目标 | 谁解析 | 解析为 |
|---------|--------|--------|
| seed.md | 编译器（渲染时） | 宿主 workspace 绝对路径 |

### 5b. Tool Ergonomics

评估目标宿主的工具生态，并在 Host Adapter 中记录关键工具使用指导。

**评估维度**：

| 维度 | 说明 |
|------|------|
| **工具命名清晰度** | 工具名是否自解释 |
| **工具重叠** | 是否有多个工具做类似的事 |
| **返回值信号密度** | 工具返回是高信号还是低层噪音 |
| **Token 成本** | 工具调用的 input/output token 开销 |

```yaml
tool_guidance:
  preferred_tools:
    - tool: "{tool_name}"
      when: "{使用场景}"
  avoid_tools:
    - tool: "{tool_name}"
      reason: "{原因}"
  tool_patterns:
    - pattern: "{使用模式}"
      rationale: "{理由}"
```

**注意**：tool guidance 来自 Host Spec 的实际工具清单，不编撰。

---

## Step 6: 知识组织（默认全量注入，教训 L34）

**原则**：非不必要不进行知识压缩。晶体消费者是 AI，不是人——不限行数。注意力管理靠分步执行+按阶段注入，不靠裁减知识量。

### 6.0 审计发现消费

蓝图 `audit_checklist_summary` 中的审计发现必须在晶体中消费：
- Critical/High 的 ❌ 发现 → 写入对应 stage 的禁止事项或 Failure Taxonomy
- machine_checkable=true 的约束 → 自动纳入 Hard Gate 候选（教训 L33）

### 6a. 注入规则

| 知识类型 | 注入策略 |
|---------|---------|
| 全部 business_decisions | **100% 内联**——按 stage 分组交织到架构蓝图段 |
| 全部约束 | **100% 内联**——severity=fatal 单独 [FATAL] 段，其余按 stage 分组 |
| 全部 known_use_cases | **100% 内联**——通过 intent_router 控制块做运行时匹配 |
| API 示例 / 代码模板 | **内联**到资源段 |
| 依赖 / 数据源 | **内联**到资源段 |

**derived_from 聚合与溯源**：

| 字段 | 编译时使用 | 渲染时使用 |
|------|-----------|-----------|
| `derived_from.business_decision_id` | 按 bd_id 聚合同源约束；Step 6e 的双联约束识别键 | 约束条目下附 `> Derived from: BD-{bd_id}` |
| `derived_from.blueprint_id` | 跨蓝图约束追溯 | 仅跨项目约束附 `> Source blueprint: {blueprint_id}` |
| `derived_from.derivation_version` | 与蓝图 sop_version 交叉校验 | 不渲染到晶体 |

**聚合去重规则**：同一 `derived_from.business_decision_id` 下多条约束若 `core.when` + `core.action` 语义相似度 > 0.85 则合并，severity 取最高，rationale 合并为列表；Step 6e 的双联约束对不适用本规则。

### 6b. 排除项审计

如需排除某条知识（极端情况），**必须逐条记录排除理由**：

```yaml
excluded_knowledge:
  - item: "{知识条目}"
    reason: "{排除理由}"
```

无记录的排除视为遗漏。

### 6c. 覆盖率标准

- **全部 business_decisions**：**100%** 覆盖
- **全部约束**：**100%** 覆盖（含 fatal/high/medium/low）
- **M 类 business_decisions**：**100%** 覆盖（教训 L29）
- **全部 known_use_cases**：**100%** 内联，运行时匹配

### 6d. 非领域 worked example：Next.js App Router 晶体

| 知识项 | 注入决策 |
|--------|---------|
| Server Components 默认，只有 useState/useEffect/浏览器 API 才加 `'use client'` | **内联**——stage: implement |
| App Router 的 `loading.tsx` 自动 Suspense boundary | **内联**——stage: implement |
| Tailwind class 排序风格 | **内联**——非不必要不压缩 |
| `next.config.js` 中 `images.remotePatterns` 安全配置 | **内联**——stage: setup |

<!-- DOMAIN: 此处注入本领域的知识组织 worked example -->

### 6e. 双联约束成对渲染

**输入条件**（满足全部三条时识别为双联）：

| 条件 | 标准 |
|------|------|
| 约束 A | `constraint_kind = claim_boundary` 且 `modality = must_not` |
| 约束 B | `constraint_kind ∈ {domain_rule, operational_lesson}` 且 `modality ∈ {must, should}` |
| 关联键 | 两者 `derived_from.business_decision_id` 指向同一 missing gap |

**渲染要求**：

| 要求 | 标准 |
|------|------|
| 成对识别 | 编译时按 `derived_from.business_decision_id` 聚合，同 gap 的 A + B 形成双联 |
| 相邻渲染 | 双联约束在同一段落（stage 段或 `## 约束` 段）相邻渲染，两条之间禁止插入其他条目 |
| 视觉关联 | 两条约束共享 MG-{N} 标题，明确标注 Boundary 和 Remedy |

**渲染格式**：

```markdown
#### MG-{N}: {missing_gap_name}
> **Boundary**: [{constraint_id_A}] must_not {action_A}
> **Remedy**: [{constraint_id_B}] {modality_B} {action_B}
> Source: missing_gap "{bd_id}"
```

**缺失处理**：

| 场景 | 处理 |
|------|------|
| 仅有 claim_boundary，无对应 remedy | 编译失败，回约束采集 SOP Step 2.4 补 remedy |
| remedy action 含模糊词（考虑/注意/建议/适当/尽量） | 编译失败，回约束采集 SOP 补可执行 remedy |
| 多个 MG 的排列顺序 | 按 severity 降序（fatal → high → medium）|

### 6f. 文档/混合知识源约束注入

**触发条件**（满足任一即执行本节）：

| 条件 | 标准 |
|------|------|
| 蓝图 extraction_methods | `source.extraction_methods` 含 `structural_extraction` 或 `mixed` |
| 约束 evidence 类型 | 任一约束含 `evidence_refs[].kind = document_section` |

**evidence_role 分流规则**：

| evidence_role | 注入强度 | 注入位置 |
|---------------|---------|---------|
| `normative` | 100% 内联为 must/must_not | severity=fatal 时进入 `## [FATAL] 约束`；其余进入 stage 约束段 |
| `example` | 100% 内联为参考 | `## 架构蓝图` 对应 stage 的代码示例段 |
| `rationale` | 100% 内联为理由 | 所在约束条目的 `> 理由:` 子块 |
| `anti_pattern` | 100% 内联为禁止项 | `## Rationalization Guards` 段 |

**conflict 约束处理**：

| 字段值 | 处理 |
|--------|------|
| `conflict: true` | 两路来源约束均渲染；段落标题加 `[CONFLICT]` 前缀；rationale 列出两路证据 |
| `conflict: false` 或字段缺失 | 正常渲染 |

**overclaim_risk 约束处理**：

| 字段值 | 处理 |
|--------|------|
| `overclaim_risk: true` | modality 降级一级（must → should、must_not → should_not）；rationale 注明原 modality |
| `overclaim_risk: false` 或字段缺失 | 保留原 modality |

**BD 合并规则**（触发条件：蓝图 `source.extraction_methods` 含 `mixed` 或 BD 含 `_source` 字段）：

| 场景 | 合并规则 |
|------|---------|
| 代码与文档一致（`aligned`）| 合并为一条 BD；rationale 标注 "源自代码+文档一致验证" |
| 仅文档有（`doc_only`）| 保留；rationale 标注 "源自文档，未经代码验证"；severity 不升级 |
| 仅代码有（`code_only`）| 保留；rationale 标注 "源自代码，文档未记录" |
| 代码文档矛盾（`divergent`）| 两条均保留；两条 rationale 各自标注来源；`conflict: true` 标记 |

### 6g. 资源两层拆分

**输入**：蓝图 `resources[]` + `replaceable_points` + 宿主 Spec。

**拆分表**：

| 子项 | 性质 | 归层 |
|------|------|------|
| 包名 / 版本范围 / import alias | 业务事实 | **L1 知识层** |
| 数据源选择 + schema | 业务决策 | **L1 知识层** |
| API endpoint / 协议 / 数据 schema | 业务事实 | **L1 知识层** |
| 业务代码示例 / Strategy Scaffold 骨架 | 业务知识 | **L1 知识层** |
| 安装命令（pip / uv / poetry / conda） | 物理执行 | **L3 宿主适配层** |
| 凭证注入方式 | 物理执行 | **L3 宿主适配层** |
| 文件写入工具（Write / editor / fs call） | 物理执行 | **L3 宿主适配层** |
| 数据库路径模板 | 物理执行 | **L3 宿主适配层** |
| 子技术文档加载方式 | 物理执行 | **L3 宿主适配层** |

**渲染位置**：

| 层 | 渲染位置 | 内容 |
|----|---------|------|
| L1 | `## 资源` 段主体 | 包名 / 数据源 / API / 代码模板 / Strategy Scaffold |
| L3 | `## 资源` 段末尾的 `### Host Adapter` 子段 | 当前目标宿主的安装命令 / 凭证 / 路径 / 文件 IO 指令 |

**IR 结构**（在 Crystal IR `knowledge.resources` 与 `harness.host_adapters` 中体现）：

```yaml
knowledge:
  resources:
    packages: [...]
    data_sources: [...]
    code_templates: [...]
    infrastructure_choices: [...]
harness:
  host_adapters:
    {host_name}:
      install_recipes: [...]
      credential_injection: [...]
      path_resolution: [...]
      file_io_tooling: [...]
```

**单宿主编译**：Crystal IR 只含当前宿主的 L3 子段；切换宿主时只需新增 `host_adapters.{new_host}` 子段，knowledge.resources L1 部分保持不变。

### 6h. preservation_manifest 产出

**目的**：声明晶体被宿主 AI 二次处理后必须保留的关键要素及其计数，用于晶体在宿主侧的保真自检。

**输入**：Step 1a / 6a / 6e / 6.5d / 8e / 8f 的产出汇总。

**产出**：`preservation_manifest` YAML 块（写入 Crystal IR `control_blocks.preservation_manifest`，并渲染到 seed.md directive 段内的 preservation_manifest fenced block）。

**字段定义**：

```yaml
preservation_manifest:
  required_objects:
    - type: spec_lock_semantic
      count: {Step 1a semantic_locks 实际数量}
      verification_method: "grep `id: SL-\\d+` in rendered seed.md 后比对计数"
    - type: spec_lock_implementation
      count: {Step 1a implementation_hints 实际数量}
      verification_method: "grep `id: IH-\\d+` 后比对计数"
    - type: fatal_constraint
      count: {severity=fatal 约束数量}
      verification_method: "计数 `## [FATAL] 约束` 段内的 constraint 条目"
    - type: known_use_case
      count: {intent_router 中 uc_id 数量}
      verification_method: "计数 intent_router fenced block 内 `uc_id:` 行"
    - type: rationalization_guard
      count: {rationalization_guard 约束数量}
      verification_method: "计数 `## Rationalization Guards` 段内 `### RG-` 标题行"
    - type: validator_assertion
      count: {validate.py 模板内 failures.append 行数}
      verification_method: "计数 `## Output Validator` 段内 `failures.append(` 调用"
    - type: hard_gate
      count: {Hard Gate 总数，含 G1-G4 与 machine_checkable 晋升项}
      verification_method: "计数 `## 验收` 段 Hard Gate 列表条目"
```

**填写时机**：Step 8 渲染完成后，统计实际渲染数量，回写到 IR 的 preservation_manifest 字段。

**保真自检**：宿主 AI 加载晶体后若做二次处理（生成 SKILL.md / knowledge 分层等），必须对照 preservation_manifest 逐项核对保留数量；任一类型的保留数量 < count 时触发 `preservation_drift` 告警并回退到原始晶体重新加载。

---

## Step 6.5: context_acquisition 设计

**输入**：蓝图的 `replaceable_points`（主输入，所有蓝图都有）+ `business_decisions`（增强输入）+ `known_use_cases`（增强输入）

**产出**：context_acquisition 指令块 + intent_router 控制块 + context_state_machine 控制块（嵌入 Crystal IR 和渲染产物）

**降级规则**（教训 L30）：当 `business_decisions` 或 `known_use_cases` 不存在时，仅从 `replaceable_points` + `stages` 推导。

### 6.5a. 记忆查询设计（memory_queries）

从蓝图中提取宿主 AI 应主动查询用户记忆的条目（教训 L31）：

| 蓝图来源 | 提取方法 |
|---------|---------|
| `replaceable_points` 的每个选项 | 提取选项名 → 生成"用户对{选项名}的偏好" |
| `business_decisions` type=BA | 提取可变假设 → 生成"用户的{假设参数}" |
| `business_decisions` type=M | 提取模型参数 → 生成"用户的{模型}参数配置" |
| `stages` 的输入依赖 | 提取外部数据源 → 生成"用户的{数据}访问方式" |

<!-- DOMAIN: 此处注入领域特有的记忆查询示例 -->

每条记忆查询包含：
```yaml
- query: "查询描述（自然语言）"
  source: "蓝图字段引用"
  fallback: "默认值"
  priority: "FATAL|HIGH|MEDIUM"
```

**宿主适配**：晶体不硬编码具体宿主名称。记忆查询指令写成宿主无关的通用形式。

### 6.5b. 必问项设计（required_inputs）

将记忆查询未能覆盖的关键参数列为必须向用户询问的条目。

每条必问项包含：
```yaml
- param: "参数名"
  question: "苏格拉底式提问（问业务意图，不问技术细节）"
  priority: "FATAL|HIGH"
  default: null  # FATAL 参数不可有默认值
```

**提问规则**：问"你想达到什么效果"而非"你要用什么参数"。一次最多问 3 个问题，FATAL 优先。

### 6.5c. 可替换点决策规则（replaceable_decisions）

决策优先级（固定，不可更改）：
1. 用户记忆中的明确偏好（memory_queries 命中）
2. 用户在 6.5b 中的显式回答
3. `replaceable_point.options[].fit_for` 与用户意图的匹配度
4. 默认推荐

### 6.5d. 用例覆盖与 intent_router

晶体必须包含蓝图的**全部 known_use_cases**，不在编译时锁定具体用例。运行时通过 intent_router 匹配。

**intent_router 控制块格式**（YAML fenced block，内联在晶体 directive 段中）：

```yaml
intent_router:
  - uc_id: "{UC-NN}"
    name: "{用例名称}"
    positive_terms: ["{匹配词}"]
    negative_terms: ["{排除词}"]
    required_entities: ["{必须出现的实体}"]
    data_domain: "{该用例所属数据域}"
    expected_output: "{该用例的预期交付物描述}"
    ambiguity_question: "{当匹配不确定时向用户提出的澄清问题}"
```

<!-- DOMAIN: 此处注入领域特有的 intent_router 示例 -->

**路由规则**：
- 按 positive_terms 正向匹配，按 negative_terms 排除
- top-1 和 top-2 匹配分数接近（差距 <20%），必须触发 ambiguity_question
- 跨不同 data_domain 的候选，必须触发 ambiguity_question
- 未获得用户确认前，禁止生成代码

**降级**：当 `known_use_cases` 不存在时，从 `stages` 推导默认执行路径，intent_router 只生成一个通用条目。

### 6.5e. context_state_machine

context_acquisition 四步流程必须升级为显式状态机（YAML fenced block，内联在晶体 directive 段中）：

```yaml
context_state_machine:
  states:
    - id: CA1_MEMORY_CHECKED
      description: "已查阅用户记忆"
      entry_condition: "开始执行任务"
      exit_condition: "所有 memory_queries 已查询并记录结果"
      on_timeout: "跳过记忆查询，标记为 memory_unavailable，进入 CA2"
    - id: CA2_GAPS_FILLED
      description: "缺失参数已补采"
      entry_condition: "CA1 完成"
      exit_condition: "所有 priority=FATAL 的 required_inputs 已获得用户回答"
      on_timeout: "不可跳过——FATAL 参数必须有用户回答"
    - id: CA3_PATH_SELECTED
      description: "执行路径已选择"
      entry_condition: "CA2 完成"
      exit_condition: "intent_router 匹配到唯一用例且无歧义"
      on_timeout: "触发 ambiguity_question，等待用户选择"
    - id: CA4_USER_CONFIRMED
      description: "用户已确认"
      entry_condition: "CA3 完成"
      exit_condition: "用户明确确认执行路径和关键参数"
      on_timeout: "不可跳过——必须获得用户明确确认"
  enforcement:
    - "未达 CA4_USER_CONFIRMED 状态时，禁止生成代码或执行任何实质操作"
    - "从任何状态回退到前序状态时，必须向用户说明原因"
```

**设计规则**：
- CA1→CA2→CA3→CA4 严格顺序，无跳跃
- CA1 可超时降级（记忆不可用不阻断）；CA2 和 CA4 不可跳过
- CA3 超时触发 ambiguity_question，不可自动选择用例

**渲染规则**：状态机在晶体 directive 段内渲染为 Step 1 → Step 2 → Step 3 → Step 4 的执行流程文本，而非要求宿主 AI 在回复中输出 `[STATE: ...]` 标注。宿主 AI 按步骤顺序推进即等价于状态推进。

### 6.5f. activation 字段对接

**输入**：蓝图 `applicability.activation` 字段（含 triggers / anti_skip 两个子字段）+ `applicability.not_suitable_for[]` + `applicability.prerequisites[]`。

**对接规则**：

| 蓝图字段 | 对接目标 | 效果 |
|---------|---------|------|
| `activation.triggers[]` | intent_router 各用例的 `positive_terms` 扩展池 | 用户意图匹配时优先触发匹配用例 |
| `activation.anti_skip[]` | context_state_machine `CA2_GAPS_FILLED` 状态的不可跳过项清单 | 补采阶段必须覆盖这些条件才可进入 CA3 |
| `applicability.not_suitable_for[]` | intent_router 各用例的 `negative_terms` 扩展池 | 用户意图匹配时反向排除 |
| `applicability.prerequisites[]` | context_acquisition `required_inputs` 前置条件 | 必问项的前置依赖 |

**触发条件**：蓝图含 `applicability.activation` 字段时执行本节；纯代码蓝图无 activation 字段时跳过。

**渲染检查**：蓝图有 activation 字段时 intent_router 每条 positive_terms 的并集必须包含 activation.triggers 的全部条目；否则回 Step 6.5d 补充。

---

## Step 6.6: Cross-Project Constraint Matching

> **min_preset**: thorough
> **Purpose**: Enrich a blueprint's crystal with semantically relevant constraints from other blueprints in the same domain.

### 6.6a. Constraint Pool Assembly

**Input**: Full domain constraint corpus (e.g., `knowledge/constraints/domains/{domain}.jsonl`).

**Pool construction**:
1. Load all domain-level constraints (`scope.level = "domain"`)
2. Exclude constraints already collected for this blueprint in Step 6
3. Pool = all remaining constraints from other blueprints in the same domain

### 6.6b. Semantic Relevance Scoring

For each candidate constraint, compute relevance against the target blueprint:

| Dimension | Weight | Matching method |
|-----------|--------|-----------------|
| **Stage vocabulary overlap** | 0.35 | `candidate.stage_ids ∩ target.stage_ids` / `candidate.stage_ids` |
| **Constraint kind transferability** | 0.20 | rationalization_guard=1.0, domain_rule=1.0, architecture_guardrail=0.9, resource_boundary=0.7, claim_boundary=0.6, operational_lesson=0.4 |
| **Consequence severity** | 0.15 | fatal=1.0, high=0.8, medium=0.5, low=0.2 |
| **When-clause semantic similarity** | 0.20 | Semantic similarity between `core.when` and target blueprint stage descriptions |
| **Evidence cross-applicability** | 0.10 | 1.0 if evidence references a framework used in target; 0.5 if same domain different framework; 0.0 if unrelated |

### 6.6c. Relevance Threshold and Selection

| Threshold | Action |
|-----------|--------|
| relevance_score >= 0.7 | **Include** with cross-project attribution |
| 0.5 <= relevance_score < 0.7 | **Include if** severity = fatal OR consequence.kind ∈ {financial_loss, safety, compliance, data_corruption, false_claim} |
| relevance_score < 0.5 | **Exclude** |

**Hard caps**:
- Maximum 30 cross-project constraints per crystal
- Maximum 5 constraints from any single source blueprint (diversity rule)

**Selection priority** when candidates exceed cap: severity=fatal first, then by relevance_score descending.

### 6.6d. Deduplication

| Overlap type | Detection | Resolution |
|--------------|-----------|------------|
| **Exact duplicate** | Same `hash` value | Drop the cross-project copy |
| **Semantic duplicate** | Same `core.when` + `core.action` meaning | Keep higher `confidence.score`; annotate the other as `_also_found_in` |
| **Subsumption** | One constraint strictly more specific than another | Keep the more specific; target blueprint's own constraint wins over cross-project |
| **Contradiction** | Same `when` but opposite `modality` | Flag for manual review; default to target blueprint's own constraint |

### 6.6e. Attribution

Every cross-project constraint MUST carry attribution:

```yaml
cross_project_attribution:
  source_blueprint_id: "{domain}-bp-{N}"
  source_project: "{project_name}"
  relevance_score: 0.XX
  matching_dimensions:
    stage_overlap: ["stage_id_1"]
    kind: "domain_rule"
    when_similarity: 0.XX
  original_constraint_id: "{domain}-C-{NNNN}"
```

In rendered crystal, cross-project constraints appear in a dedicated subsection per stage:

```markdown
#### Cross-project constraints (from industry pool)
> [XP-01] When {when} — {modality} {action}
> Source: {source_project} ({blueprint_id}) | Relevance: {score} | Kind: {kind}
```

### 6.6f. Impact on Other Steps

| Step | Impact |
|------|--------|
| Step 1 (Contract) | Cross-project constraints with severity=fatal may generate additional spec_locks |
| Step 2 (Failure Tax.) | Cross-project operational_lesson constraints may add domain-specific failure classes |
| Step 7 (IR) | IR gains `cross_project_constraints` section in `knowledge` block |
| Step 8 (Rendering) | Cross-project constraints rendered with attribution tags |
| Step 9 (Quality) | New checks: D14 (attribution completeness) and S9 (relevance threshold) |

<!-- DOMAIN: 此处注入本领域的跨项目约束匹配示例 -->

---

## Step 7: Crystal IR 组装

### 7a. 字段契约映射表（Authoritative）

IR 字段 ↔ seed.md 段落 ↔ Hard Gate ↔ Pass 1 D-check 四层权威对应关系。任一层变更必须同步其它三层，否则判定为契约漂移（Step 9 Pass 1 必失败）。

| IR 字段 | seed.md 段落位置 | Hard Gate | Pass 1 D-check |
|---------|----------------|-----------|---------------|
| `control_blocks.intent_router` | `## directive` 内嵌 YAML fenced block | — | D17 / S7 |
| `control_blocks.context_state_machine` | `## directive` 内嵌 YAML fenced block + Step 1→4 流程文本 | — | D17 / S8 |
| `control_blocks.spec_lock_registry.semantic_locks` | `## directive` spec_lock 段 | FATAL on drift | D3 / D4 |
| `control_blocks.spec_lock_registry.implementation_hints` | `## directive` spec_lock 段 | WARN on drift | D4 |
| `control_blocks.preservation_manifest` | `## directive` 内嵌 YAML fenced block | — | D15 / D17 |
| `control_blocks.output_validator` | `## Output Validator` 段（validate.py + Strategy Scaffold 尾部 + Enforcement Protocol） | G1-G4 | D13 / D23 / D24 / D25 |
| `knowledge.business_decisions` | `## 架构蓝图` 按 stage 分组交织 | — | S1 |
| `knowledge.constraints[severity=fatal]` | `## [FATAL] 约束` 段 | — | S1 |
| `knowledge.constraints[rationalization_guard]` | `## Rationalization Guards` 段的 RG-{N} 条目 | — | D27 / D28 |
| `knowledge.use_cases` | `## directive` intent_router + `## 架构蓝图` 内引用 | — | S1 / S7 |
| `knowledge.resources.packages/data_sources/code_templates/infrastructure_choices` | `## 资源` L1 主体 | — | S5 |
| `harness.contract.spec_lock` | 与 `control_blocks.spec_lock_registry` **主从**：`control_blocks` 为权威源，`harness.contract` 为渲染时引用副本 | — | D4 |
| `harness.contract.delivery_gate.hard` | `## 验收` Hard Gate 段 | G1-G4 + 补充项 | D5 |
| `harness.contract.delivery_gate.soft` | `## 验收` Soft Gate 段（含 Step 0.8d rubric） | LLM-as-Judge | D5 |
| `harness.failure_taxonomy.universal` | `## directive` 失败类段 | — | D6 |
| `harness.failure_taxonomy.domain_specific` | `## directive` 失败类段 + Step 2c Rationalization Guards 派生项 | — | D6 |
| `harness.stage_spec.stages` | `## 架构蓝图` 各 stage 段 | — | D7 |
| `harness.state_semantics.slots` | `## directive` state 指引 + Strategy Scaffold 读写调用 | — | D8 |
| `harness.host_adapters.{host_name}` | `## 资源` 段末尾 `### Host Adapter` 子段 | — | S5 |
| `trace_schema` | 不渲染到 seed.md（IR 元数据，宿主 runtime 消费） | — | D11 |
| `validity.source_commits / version_pins / review_triggers` | `## directive` footer version pin 提示 + IR 元数据保留 | — | D12 |

### 7b. 契约漂移检查

Step 8 渲染完成后必须对照 7a 表逐行双向验证：

| 方向 | 验证动作 |
|------|---------|
| IR → seed.md | 每个 IR 字段必须在对应 seed.md 段落找到渲染痕迹 |
| seed.md → IR | 每个 seed.md 段落的结构化块必须在 IR 找到源字段 |
| seed.md → Hard Gate | 每个受 G1-G4 覆盖的段落必须在 `## 验收` 找到对应 Gate 条目 |
| Hard Gate → D-check | 每个 Hard Gate 必须在 Step 9a 找到对应 D-check ID |

任一方向验证失败即判定为契约漂移，编译失败回溯到 Step 6/7 修正。

### 7c. IR 完整模板

```yaml
version: "2.0"
crystal_id: "{domain}-bp-{id}"
task_type: "A | B | C"  # Pipeline / Iterative / Declarative
metadata:
  compilation_language: "en"
  source_languages: ["{source_lang}"]
  human_summary_locale: "{user_locale}"

references:
  blueprint: "path/to/blueprint.yaml"
  constraints: ["path/to/constraints.jsonl"]
user_intent: { ... }

knowledge:
  business_decisions: [ 全量 — 100% 覆盖 ]
  constraints: [ 全量 — 100% 覆盖，fatal 单独分组 ]
  use_cases: [ 全量 — 运行时通过 intent_router 匹配 ]
  cross_project_constraints:       # Step 6.6 产出（thorough preset only）
    total_pool_size: {N}
    candidates_scored: {N}
    selected: {N}
    items: [ ... ]
  resources:
    packages: [ 包名 + 版本 + import alias ]
    data_sources: [ 数据源选择 + schema ]
    code_templates: [ 代码示例 + Strategy Scaffold 骨架 ]
    infrastructure_choices: [ 存储/计算/部署决策（选什么，不含怎么装）]

# context_acquisition（Step 6.5 产出）
context_acquisition:
  memory_queries: [ ... ]
  required_inputs: [ ... ]
  replaceable_decisions: [ ... ]

# 5 个结构化控制块（内联在晶体 directive 段中的 YAML fenced block）
control_blocks:
  intent_router: { ... }          # Step 6.5d 产出
  context_state_machine: { ... }  # Step 6.5e 产出
  spec_lock_registry:             # Step 1a 产出（双层：semantic_locks + implementation_hints）
    semantic_locks: [ ... ]
    implementation_hints: [ ... ]
  preservation_manifest: [ ... ]  # 保真校验清单——晶体被宿主 AI 二次处理后需保留的关键要素
  output_validator:               # 渲染规则见 Step 8e
    rendering_target: "## Output Validator"
    enforcement_chain:
      validator_script_path: "{workspace}/validate.py"
      strategy_tail_marker: "# === DO NOT MODIFY BELOW THIS LINE ==="
      enforcement_protocol_in_directive: true
    assertions:
      - source_kind: "constraint.validation_threshold"
        source_id: "{constraint_id}"
        rendered_check: "{python if-condition}"
        rendered_message: "FATAL: {short_label}"
      - source_kind: "business_decision.type=M"
        source_id: "{bd_id}"
        rendered_check: "..."
        rendered_message: "..."

harness:
  contract: { spec_lock: [...], delivery_gate: { hard: [...], soft: [...] } }
  failure_taxonomy: { universal: [...], domain_specific: [...] }
  stage_spec:
    task_type: "..."
    stages:
      - name: "..."
        goal: "..."
        actions: [...]
        exit_criterion: "..."
        budget_ratio: 0.x
        checkpoint_artifact: "..."
        resume_condition: "..."
        resume_action: "skip | resume | rerun"
  state_semantics:
    slots:
      - slot_id: "plan"
        path: "{workspace}/.state/plan.json"
        purpose: "..."
        write_stage: "..."
        read_stages: [...]
        format: "json"
        compaction_stable: true
    lifecycle_rules:
      - "创建即声明：所有 state 文件在 IR 中预声明"
      - "写入即 checkpoint：每次写入等价于创建恢复点"
      - "读取优先于记忆：AI 应 read 文件获取状态，不从上下文回忆"
      - "冲突以文件为准：文件内容与上下文记忆矛盾时以文件为准"
  host_adapters:
    {host_name}:
      install_recipes: [ 安装命令模板 ]
      credential_injection: [ 凭证注入方式 ]
      path_resolution: [ {workspace} 与路径模板解析 ]
      file_io_tooling: [ 文件写入工具与使用模式 ]
      spec_ref: "docs/research/host-specs/{host}-host-spec.md"
      timeout_seconds: { 从 Host Spec 读取 }
      exec_rules:
        whitelist: [...]

# Trace Schema
trace_schema:
  events:
    - type: stage_transition
      fields: [from_stage, to_stage, timestamp, exit_criterion_met]
    - type: tool_call
      fields: [tool_name, arguments_summary, result_summary, success, duration_hint]
    - type: artifact_emission
      fields: [artifact_path, size_bytes, stage, slot_id]
    - type: validation_result
      fields: [gate_id, gate_type, expected, actual, passed]
    - type: failure_event
      fields: [failure_class, trigger_detail, recovery_action_taken, resolved]
    - type: spec_lock_check
      fields: [param, locked_value, actual_value, drifted]
  output:
    format: "jsonl"
    path: "{workspace}/.trace/execution_trace.jsonl"
    when: "宿主支持文件写入时生成；宿主不支持时降级为结构化 stdout"

# 时效性管理
validity:
  compiled_at: "ISO date"
  source_commits:
    blueprint: "{commit_hash}"
    constraints: "{commit_hash}"
  version_pins:
    - dependency: "{framework_name}"
      version: "{semver_range}"
  review_triggers:
    - "{framework_name} major version release"
    - "RC type decision source changes"
  expires_at: null

compilation:
  sop_version: "crystal-compilation-v3.2"
  compiled_at: "ISO date"
```

---

## Step 8: 宿主渲染（单文件自包含，教训 L34）

### 渲染原则

1. **单文件自包含**——产品宪法 §3.4：编译产物是单个 md 文件，用户丢给 AI 即可用
2. **所有知识内联**——不引用外部文件，不要求 AI read 外部文件（AI 会声称读了但实际编造，教训 L16）
3. **路径参数化**（`{workspace}`）
4. **从 Host Spec 派生**，不编撰
5. **文件头尾**：头部 `*Powered by Doramagic.ai*`，尾部同

### 8a. 晶体文件渲染（单文件自包含）

所有任务类型的渲染产物都是单个 seed.md 文件。

**段落结构**（按出现顺序）：

```markdown
*Powered by Doramagic.ai*

## Human Summary
## directive
## [FATAL] 约束
## Rationalization Guards
## Output Validator
## 证据质量声明
## 溯源政策
## 架构蓝图
## 资源
## 约束
## 验收

*Powered by Doramagic.ai*
```

**各段落渲染规则**：

| 段名 | 必含内容 | 语言 | 适用条件 |
|------|---------|------|---------|
| Human Summary | skill 能力 + 自动获取项 + 用户被询问项 | 用户 locale | 全部任务 |
| directive | Language Protocol + context_acquisition 四步 + spec_lock + 阶段规格 + 禁止事项 + 工具规则 + Output Validator Enforcement Protocol；内嵌 5 个 YAML fenced block 控制块（intent_router / context_state_machine / spec_lock_registry / preservation_manifest / output_validator） | English | 全部任务 |
| [FATAL] 约束 | severity=fatal 约束全量内联，命中任一停止执行 | English | 全部任务 |
| Rationalization Guards | 每条 rationalization_guard 渲染为 RG-{N} 条目，含 excuse / rebuttal / red_flags / violation_detector / severity 五字段 | English | 约束池含 rationalization_guard |
| Output Validator | Validator Scaffold 完整 .py 文件模板 + Strategy Scaffold 末尾 DO NOT MODIFY 围栏标准文本 + Hard Gate G1-G4 grep 规则 | English | 任务产出含数值结果 |
| 证据质量声明 | 从蓝图 `_enrich_meta` 字面提取 evidence_coverage_ratio / evidence_verify_ratio / evidence_invalid / evidence_verified / evidence_auto_fixed；从蓝图 `audit_checklist_summary` 字面提取 coverage / finance_universal / subdomain_totals；段尾渲染两条 agent 使用规则：（1）evidence_verify_ratio < 50% 必须先回查源文件；（2）audit fail 合计 > 20 必须主动告知用户 | 用户 locale | 全部任务 |
| 溯源政策 | 源文件路径声明（LATEST.yaml / LATEST.jsonl）+ 4 条必须回查源文件的场景（约束冲突 / BD 存疑 / 证据可疑 / 用户质疑）+ 回查方式（有/无文件读取能力的降级路径）+ 禁止条款（晶体非源文件替代品）| 用户 locale | 全部任务 |
| 架构蓝图 | 按 stage 分段，每段交织 business_decisions + 约束 + 代码示例 | English | 全部任务 |
| 资源 | L1 主体：packages / data_sources / code_templates / infrastructure_choices / Strategy Scaffold；L3 子段 `### Host Adapter`：当前宿主的 install_recipes / credential_injection / path_resolution / file_io_tooling（详见 Step 6g / 8e）| English | 全部任务 |
| 约束 | 按 stage 分组，全量约束内联 | English | 全部任务 |
| 验收 | Hard Gate G1-G4 + Soft Gate | English | 全部任务 |

### 8b. 长任务知识分段（Iterative 模式）

Iterative 模式（类型 B）的晶体仍然是**单文件**，但在文件内部按阶段组织知识，使用 Markdown 标题层级做渐进披露。宿主 AI 按阶段推进时，只需关注当前阶段标题下的内容。

### 8c. Per-stage 渲染

适用于 Iterative 模式——按阶段渲染不同部分（setup 加载资源、execute 加载蓝图+约束、validate 加载 Contract），仍在单文件内部通过标题层级分段。

### 8d. 渲染后检查

| 检查项 | 标准 |
|--------|------|
| 单文件自包含 | 产出是单个 seed.md 文件，无外部引用 |
| 知识覆盖率 | 全部 BD 100%, 全部约束 100%, 全部 UC 100% |
| 5 控制块完整 | intent_router / context_state_machine / spec_lock_registry / preservation_manifest / output_validator |
| Validator Scaffold 可执行 | `## Output Validator` 段含 validate.py 完整模板，所有 validation_threshold 渲染为 if + sys.exit(1) 块；Strategy Scaffold 末尾含 `from validate import enforce_validation` 字面调用 |
| Strategy Scaffold | `## 资源` 段含主脚本骨架，安全检查（FATAL RC）焊死在结构中，业务逻辑处有 REPLACE_WITH 占位符，末尾含 `# === DO NOT MODIFY BELOW THIS LINE ===` 围栏 |
| Hard Gate G1-G4 | `## 验收` 段同时含 G1（result 存在）、G2（validation_passed 标记）、G3（grep import）、G4（grep 围栏）四条 |
| context_acquisition | 记忆查询 + 必问项 + 可替换点决策嵌入 directive |
| 人话摘要 | 在文件开头，用户可读 |
| 路径参数化 | 无硬编码用户路径 |
| Host Spec 对齐 | 所有平台数值有证据 |
| Hard Gate ≥ 3 条 | 至少 3 条可程序化验证的 gate |
| 时效性元数据 | version_pins 和 review_triggers 已填写 |
| State 指引 | 包含 state 文件路径 + read/write 指令 |
| 文件头尾 | Powered by Doramagic.ai |
| 双联约束成对 | 所有 claim_boundary 与对应 remedy 按 Step 6e 要求成对相邻渲染 |
| Rationalization Guards 段 | 约束池含 rationalization_guard 时 `## Rationalization Guards` 段存在且每条含 5 字段 |
| evidence_role 分流 | 文档源约束按 Step 6f 规则注入到 [FATAL]/架构蓝图/约束条目/Rationalization Guards 段 |
| 证据质量声明锚点 | `## 证据质量声明` 段含 `evidence_invalid` + `evidence_verify_ratio` 字面字符串 + audit coverage 或 fail 计数；蓝图 `_enrich_meta` 缺失时段落保留且标注 n/a |
| 溯源政策锚点 | `## 溯源政策` 段含 `LATEST.yaml` 和 `LATEST.jsonl` 字面引用 + `回查` 关键词（或等价英文 traceback）+ 4 条必查场景清单 |

### 8e. Output Validator Scaffold 渲染

**适用条件**：任务产出含可量化数值结果（回测 metrics、数据管线产出、ML 训练 metrics、API 响应、聚合统计等）。纯声明式任务（dbt model 配置、Terraform 资源声明、K8s manifest）可省略本段。

**强制产物**：晶体 `## Output Validator` 段必须同时包含 8e.1 / 8e.2 / 8e.3 三个完整文本块。

#### 8e.1 Validator Scaffold（validate.py 完整模板）

```python
# {workspace}/validate.py
# 禁止修改本文件——晶体合约的强制部分

import sys
import json
from pathlib import Path

def enforce_validation(result, output_path: str) -> None:
    failures = []

    # === Crystal-injected assertions ===
    {RENDERED_ASSERTIONS}
    # === END assertions ===

    if failures:
        Path(f"{output_path}.FAILED.log").write_text("\n".join(failures))
        sys.stderr.write("\n".join(failures) + "\n")
        sys.exit(1)

    {WRITE_RESULT_BLOCK}
    Path(f"{output_path}.validation_passed").touch()
```

`{RENDERED_ASSERTIONS}` 渲染规则：

| 来源 | 渲染为 |
|------|--------|
| 约束字段 `validation_threshold` 含具体阈值 | `if <condition>: failures.append("FATAL: <short_label>")` |
| BD type=M 含具体参数 | `if <param> != <locked_value>: failures.append("FATAL: M 参数漂移")` |
| FATAL severity 约束含具体阈值或 grep 模式 | 同上格式，每条独立一行 |

`{WRITE_RESULT_BLOCK}` 按数据格式渲染：

| 数据格式 | 写出语句 |
|---------|---------|
| pandas DataFrame → CSV | `result.to_csv(output_path, index=False)` |
| dict → JSON | `Path(output_path).write_text(json.dumps(result, indent=2))` |
| pandas DataFrame → Parquet | `result.to_parquet(output_path)` |

<!-- DOMAIN: 此处注入本领域特定的 assertion 渲染示例 -->

#### 8e.2 Strategy Scaffold 不可移除尾部

主脚本（`strategy.py` / `backtest.py` / `pipeline.py` 等）末尾必须含以下字面文本：

```python
# === DO NOT MODIFY BELOW THIS LINE ===
if __name__ == "__main__":
    result = run_main()
    from validate import enforce_validation
    enforce_validation(result, output_path="{workspace}/result.{ext}")
# === END DO NOT MODIFY ===
```

| 占位符 | 渲染规则 |
|--------|---------|
| `{ext}` | csv / json / parquet 中按数据格式选一 |
| `run_main` 函数名 | 按任务类型选一：回测=`run_backtest`、数据管线=`run_pipeline`、ML 训练=`run_training`、API=`run_handler` |
| `{workspace}` | 执行时替换为宿主 workspace 绝对路径 |

#### 8e.3 Output Validator Enforcement Protocol（写入 directive 段末尾）

```markdown
### Output Validator Enforcement Protocol (FATAL)

1. 禁止编辑 validate.py
2. 禁止删除主脚本中 `# === DO NOT MODIFY BELOW THIS LINE ===` 之后的代码
3. 禁止用 try/except 包裹 enforce_validation 调用
4. 禁止重写结果写出逻辑——必须经由 enforce_validation 写出
5. validate.py 因依赖问题报错时必须修复依赖，不得删除调用
```

#### 8e.4 渲染检查项

| 检查项 | 标准 |
|--------|------|
| validate.py 完整 | 含 enforce_validation 函数定义 + 至少 1 条 assertion + sys.exit(1) 路径 + Path.touch() 路径 |
| Strategy Scaffold 尾部 | 字面包含 `# === DO NOT MODIFY BELOW THIS LINE ===` 和 `from validate import enforce_validation` 两条字符串 |
| Output Validator Enforcement Protocol | directive 段末尾包含 5 条字面规则 |
| FATAL 阈值卡位 | 每条 assertion 满足 Step 1b 的 FATAL 阈值卡位规则三选一 |

### 8f. Rationalization Guards 渲染

**适用条件**：约束池含 `constraint_kind = rationalization_guard` 的条目。

**强制产物**：晶体 `## Rationalization Guards` 段必须含每条 rationalization_guard 约束的完整展开。

**渲染格式**：

```markdown
### RG-{N}: {guard_name}
- **Excuse**: {excuse 原文}
- **Rebuttal**: {rebuttal 原文}
- **Red Flags**:
  - {red_flag_1}
  - {red_flag_2}
- **Violation Detector**: {violation_detector 描述}
- **Severity**: {severity}
```

**渲染顺序**：按 severity 降序（fatal → high → medium → low）。

**渲染检查项**：

| 检查项 | 标准 |
|--------|------|
| 段落存在 | 约束池含 rationalization_guard 时 `## Rationalization Guards` 段必须存在 |
| 字段完整 | 每条 RG-{N} 含 Excuse / Rebuttal / Red Flags / Violation Detector / Severity 五字段 |
| 渲染顺序 | 按 severity 降序排列 |

### 8g. 文档/混合源渲染

**适用条件**：蓝图 `source.extraction_methods` 含 `structural_extraction` 或 `mixed`；或任一约束 `evidence_refs[].kind = document_section`。

**渲染规则**：

| 字段 | 渲染位置 | 渲染标注 |
|------|---------|---------|
| 约束含 `evidence_refs[].kind = document_section` | 按 Step 6f evidence_role 分流规则注入 | 约束条目下附 `> Source: {path}:§{section_id}` |
| BD 的 `_source: doc_only` | 保留 BD；rationale 含 "源自文档，未经代码验证" | 段落标题无特殊前缀 |
| BD 的 `_source: divergent` | 两条 BD 分别渲染 | 两条段落标题加 `[CONFLICT]` 前缀 |
| 约束的 `overclaim_risk: true` | modality 字面降级；原 modality 写入 rationale | 约束条目下附 `> 原文档声明: {原 modality}` |

**降级校验**：overclaim_risk=true 约束的渲染后 modality 必须与原始文档 modality 不同，且降级方向正确（must→should、must_not→should_not）。

**evidence_role 与注入位置一致性**：渲染完成后按 Step 6f 的 evidence_role 分流表逐条核对实际注入位置与应注入位置一致。

### 8h. 约束与 BD 溯源渲染

**适用条件**：约束含 `derived_from` 字段；或 BD 含 `_source` 字段。

**渲染规则**：

| 字段 | 渲染位置 | 渲染标注 |
|------|---------|---------|
| 约束 `derived_from.business_decision_id` | 约束条目末尾 | `> Derived from: BD-{bd_id}` |
| 约束 `derived_from.blueprint_id` ≠ 当前蓝图 id | 约束条目末尾 | `> Source blueprint: {blueprint_id}` |
| BD `_source: code_only` | BD 条目末尾 | `> Source: code_analysis` |
| BD `_source: doc_only` | BD 条目末尾 | `> Source: document_extraction (未经代码验证)` |
| BD `_source: aligned` | BD 条目末尾 | `> Source: code+doc aligned` |

**与双联约束的排他规则**：双联约束内的两条约束不渲染 `Derived from` 标注（Step 6e 的 MG-{N} 格式通过 `> Source: missing_gap "{bd_id}"` 行覆盖溯源）。

---

## Step 9: 质量校验

### 9a. Pass 1: Deterministic Checks (zero LLM cost, run first)

All Pass 1 checks MUST pass before proceeding to Pass 2.

| # | Check | Condition | On failure |
|---|-------|-----------|------------|
| D1 | IR version | `compilation.sop_version` = `crystal-compilation-v3.2` | Update |
| D2 | Compilation language | All prose except Human Summary is in `metadata.compilation_language` | Translate |
| D3 | spec_lock count | spec_lock covers all type=M,B,BA,RC business decisions | Supplement |
| D4 | spec_lock_registry layers | semantic_locks + implementation_hints separated | Re-layer |
| D5 | Hard Gate count | >= 3 Hard Gates with executable check conditions | Supplement |
| D6 | Failure Taxonomy count | 8 universal (incl. model_misuse + false_completion_claim) + >= 2 domain-specific | Supplement |
| D7 | Checkpoint completeness | Every stage has checkpoint_artifact + resume_action | Supplement |
| D8 | State slot existence | >= 1 compaction_stable slot for type B tasks | Add slot |
| D9 | Path parameterization | No hardcoded user paths (grep for absolute paths) | Replace with {workspace} |
| D10 | Knowledge inline | Zero external file read instructions in crystal | Inline |
| D11 | Trace schema presence | IR contains trace_schema with >= 5 event types | Supplement |
| D12 | Version pins | version_pins covers all framework dependencies | Supplement |
| D13 | output_validator executable | `## Output Validator` 段内 validate.py 模板含至少 1 条 `if <condition>: failures.append(...)` 检查 + `sys.exit(1)` 路径（非自然语言描述） | Rewrite as code |
| D14 | Cross-project attribution | Every cross-project constraint has attribution (if Step 6.6 applied) | Add attribution |
| D15 | preservation_manifest count | required_objects counts match actual injected counts | Correct counts |
| D16 | Single file self-contained | Rendered crystal is one seed.md file, no external references | Inline all |
| D17 | 5 control blocks present | intent_router / context_state_machine / spec_lock_registry / preservation_manifest / output_validator | Supplement |
| D18 | Language Protocol present | directive section contains Language Protocol with 5 runtime rules (detect, user-facing output, intent matching, code English, domain terms) | Add protocol |
| D23 | Validator Scaffold 完整 | `## Output Validator` 段含 validate.py 完整模板 + 至少 1 条 assertion + sys.exit(1) 路径 + Path.touch() 路径 | 补充模板 |
| D24 | DO NOT MODIFY 围栏存在 | Strategy Scaffold 末尾字面包含 `# === DO NOT MODIFY BELOW THIS LINE ===` 和 `from validate import enforce_validation` 两条字符串 | 补充围栏 |
| D25 | Hard Gate G1-G4 完整 | 任务产出含数值结果时，验收段同时含 G1（result 存在）+ G2（validation_passed 标记）+ G3（grep import 字符串）+ G4（grep 围栏字符串）四条；纯声明式任务在 IR metadata 标注 `output_validator_exempt: true` 后免检 | 补充缺失项或加豁免标记 |
| D26 | FATAL 阈值卡位 | 每条进入 Hard Gate 的 validation_threshold 满足"物理不可能 / 合法上限 5 倍 / 数据完整性破坏"三选一 | 收紧阈值或降级为 Soft Gate |
| D27 | Rationalization Guards 段 | 约束池含 rationalization_guard 时 `## Rationalization Guards` 段存在且每条含 excuse/rebuttal/red_flags/violation_detector/severity 五字段 | 补充渲染 |
| D28 | 双联约束成对 | 每个 claim_boundary 与同 `derived_from.business_decision_id` 的 domain_rule/operational_lesson 约束成对相邻渲染 | 重新聚合渲染 |
| D29 | evidence_role 分流 | 每条 `evidence_refs[].kind = document_section` 约束按 evidence_role 注入到 Step 6f 指定段落 | 重新分流注入 |
| D30 | conflict 标记 | 每条 `conflict: true` 约束在段落标题加 `[CONFLICT]` 前缀，rationale 列出两路证据 | 补充标记 |
| D31 | overclaim_risk 降级 | 每条 `overclaim_risk: true` 约束的 modality 相对原文档降级一级，rationale 注明原 modality | 补充降级 |
| D32 | derived_from 溯源渲染 | 每条 `derived_from.business_decision_id` 非空的约束在条目末尾含 `> Derived from: BD-{bd_id}` 字面字符串；跨蓝图约束含 `> Source blueprint: {blueprint_id}` | 补充溯源 |
| D33 | activation 覆盖 | 蓝图有 `applicability.activation.triggers[]` 字段时，intent_router 各用例的 positive_terms 并集必须包含 activation.triggers 全部条目 | 补充 positive_terms |
| D34 | BD 覆盖率机械验证 | 运行 `scripts/crystal_quality_gate.py` 得到 `coverage.bd.rate = 1.0`（seed.md 中唯一 BD-{n} ID 引用数 = 蓝图 business_decisions 总数） | 补齐缺失 BD；禁止用 LLM 印象替代 grep 计数 |
| D35 | 约束覆盖率机械验证 | 运行 `scripts/crystal_quality_gate.py` 得到 `coverage.constraint_all.rate = 1.0`（seed.md 中唯一约束 ID 引用数 = 约束池总数） | 补齐缺失约束；禁止用摘要替代 ID 引用 |
| D36 | UC 覆盖率机械验证 | 运行 `scripts/crystal_quality_gate.py` 得到 `coverage.uc.rate = 1.0`（intent_router 中唯一 uc_id 数 = 蓝图 known_use_cases 总数） | 补齐缺失 UC |
| D37 | 编译前置清单存在 | `{blueprint_dir}/crystal_inputs/` 含 bd_checklist.md / constraint_checklist.md / uc_checklist.md / coverage_targets.json 四文件 | 运行 `scripts/prepare_crystal_inputs.py` |
| D38 | quality_gate 退出码 | `python3 scripts/crystal_quality_gate.py --strict` 退出码 = 0 | 修正所有失败门禁后重跑 |
| D39 | 证据质量声明锚点 | `## 证据质量声明` 段字面含 `evidence_invalid` + `evidence_verify_ratio` + audit coverage 或 subdomain fail 计数；两条 agent 使用规则（< 50% 回查 / fail > 20 告知用户）成文 | 补齐字段或重新提取蓝图 `_enrich_meta` + `audit_checklist_summary` |
| D40 | 溯源政策锚点 | `## 溯源政策` 段字面含 `LATEST.yaml` + `LATEST.jsonl` + `回查` 关键词 + 4 条必查场景（约束冲突 / BD 存疑 / 证据可疑 / 用户质疑）| 补齐场景清单或源文件引用 |

### 9b. Pass 2: Semantic Checks (LLM-assisted, run only after Pass 1 fully passes)

| # | Check | Condition | On failure |
|---|-------|-----------|------------|
| S1 | Knowledge coverage | All BD 100%, all constraints 100%, M-type 100%, all UC 100% | Supplement |
| S2 | Actionability | LOW actionability knowledge rewritten to specific instructions | Rewrite |
| S3 | Exclusion audit | Every excluded knowledge item has logged rationale | Log or re-include |
| S4 | Task type correctness | Task type matches actual blueprint execution paradigm | Re-classify |
| S5 | Host Spec alignment | All platform values have evidence from Host Spec | Verify |
| S6 | context_acquisition completeness | memory_queries cover all replaceable_points + BA params | Supplement |
| S7 | intent_router completeness | Every known_use_case has full routing signature | Complete fields |
| S8 | context_state_machine integrity | CA1-CA4 states with entry/exit/timeout, enforcement present | Complete |
| S9 | Cross-project relevance | All cross-project constraints pass relevance threshold >= 0.7 (if Step 6.6 applied) | Remove below-threshold |
| S10 | Domain term accuracy | Translated domain terms use standard English equivalents | Correct terms |
| S11 | Cross-domain readability | Non-domain engineer can understand each judgment point | Add examples |
| S12 | Human summary locale | Human Summary in user's specified locale language | Localize |

**Ordering rule**: Never run Pass 2 if any Pass 1 check fails — structural problems make semantic checking unreliable.

---

## Step 10: 晶体效能验证

**目的**：验证晶体是否真的让 AI 做得更好。覆盖率达标不等于有效。

### 10a. 基线测试（无晶体）

给目标宿主**同样的 user_intent**，但**不给晶体**，只给一句话任务描述。

<!-- DOMAIN: 此处注入本领域典型的基线 prompt 示例 -->

记录基线产出：
- 是否完成任务
- 产出质量（Delivery Gate 通过数）
- 关键决策点 AI 做了什么选择
- 出现了哪些错误

### 10b. 晶体测试（有晶体）

给目标宿主**同样的 user_intent** + **编译好的晶体**（seed.md）。

### 10c. 效能对比

| 对比维度 | 基线 | 晶体 | 判定 |
|---------|------|------|------|
| Hard Gate 通过数 | X/N | Y/N | Y > X 为有效 |
| 关键参数是否漂移 | 列出漂移项 | 列出漂移项 | 晶体版漂移更少为有效 |
| 错误类型 | 列出 | 列出 | 晶体版避免了基线的错误为有效 |
| 领域知识应用 | AI 是否犯了领域错误 | AI 是否正确应用了领域知识 | 最核心判据 |

**判定标准**：

| 结果 | 含义 | 动作 |
|------|------|------|
| 晶体版 Hard Gate 通过数 > 基线 | 晶体有效 | 可发布 |
| 晶体版避免了基线的领域错误 | 知识注入生效 | 可发布 |
| 晶体版与基线无显著差异 | **晶体无效** | 回到 Step 6 重新筛选知识 |
| 晶体版反而比基线差 | **晶体有害** | 回到 Step 1 检查 spec_lock 是否过度限制 |

### 10d. 知识归因分析（可利用 trace 增强）

对比基线和晶体的 AI 行为差异，回答：

1. 哪些知识改变了 AI 的行为？
2. 哪些知识被忽略了？（检查 Actionability 和位置）
3. AI 自主补充了哪些晶体没有的知识？（这些知识 AI 新颖度标为 LOW）

利用 trace 事件做精确归因（`spec_lock_check`、`failure_event`、`tool_call`、`stage_transition`）。

### 10e. Complete Trace Diagnosis (thorough preset only)

> Complete execution traces > LLM-summarized traces > scalar scores. Never summarize traces for diagnosis.

When the host supports trace output:

1. **Collect** raw trace files: `{workspace}/.trace/execution_trace.jsonl` from baseline (10a) and crystal (10b) runs
2. **DO NOT summarize** traces — read the complete JSONL files directly
3. **Causal chain analysis**: For each baseline failure, trace backwards through `stage_transition` and `tool_call` events to identify root cause decision point

**Diff analysis**:

| Analysis | Trace events | What to compare |
|----------|-------------|-----------------|
| Parameter drift prevention | `spec_lock_check` | Baseline drifted=true count vs crystal |
| Failure recovery speed | `failure_event` | Time between failure and resolved=true |
| Tool usage efficiency | `tool_call` | Redundant/failed tool calls in baseline vs crystal |
| Stage pacing | `stage_transition` | Per-stage duration comparison |
| Artifact progress | `artifact_emission` | Emission frequency and size growth |
| Stall detection | Gaps in `artifact_emission` | Periods > 10 tool_calls with no emission |

Output: A causal narrative per observed behavioral difference, not a scalar score.

### 10f. 验证通过标准

| 检查项 | 标准 | 不通过时 |
|--------|------|---------|
| 效能提升 | 晶体版至少在 1 个维度显著优于基线 | 回到 Step 6 |
| 无负面效应 | 晶体版不比基线差 | 回到 Step 1 检查过度约束 |
| 知识生效 | 至少 1 条 HIGH 新颖度知识被确认"改变了 AI 行为" | 补充更多 HIGH 新颖度知识 |

**注意**：
- **新蓝图首次编译**：必须完整跑 10a-10d
- **已验证蓝图的增量更新**：只跑 10b，与历史基线对比
- **跨宿主迁移**：在新宿主上重跑 10a-10c

---

## 教训日志

| # | 教训 | 来源 |
|---|------|------|
| L1 | spec_lock 必须覆盖所有可漂移参数 | 晶体测试参数漂移 |
| L2 | delivery_gate 必须含业务合理性检查 | pending_order bug |
| L3 | 禁止可选扩展阶段 | 股票池/范围膨胀 |
| L4 | 代码模板给可执行示例不给伪代码 | API 参数错误 |
| L5 | Host Adapter 白名单优先 | 模型评审 |
| L6 | 约束注入按阶段精选——实测覆盖率偏低，因果机制待验证 | 实测 |
| L7 | Crystal IR 与渲染分离 | 三方评审共识 |
| L8 | Failure Taxonomy 必须有具体 recovery action | 回退死路 |
| L9 | 宿主能力参数从 Host Spec 读取，禁止编撰 | timeout/体积限制编撰 |
| L10 | 晶体知识是核心价值，Harness 不能替代知识 | 知识覆盖率 6% 仍通过 |
| L11 | "指令诅咒"0.95^N 未经实测验证，不作为第一性原理 | 事实核查 |
| L12 | 路径使用 `{workspace}` 占位符 | 硬编码路径 |
| L13 | 晶体产出是单文件 seed.md（产品宪法 §3.4），宿主 AI 自行转化为其平台 skill 格式 | CEO 审查 + bp-009 v1.7 修正 |
| L14 | v1.8 前用四维筛选压缩知识，v1.8 后改为全量注入——四维筛选仅作排除项审计参考 | 四方评审 → v1.8 修正 |
| L15 | 时效性管理：每个晶体必须有 version_pins + review_triggers | 四方评审一致 |
| L16 | References 必须强制 read 而非"请阅读"——AI 会声称读了但实际编造 | 模型评审 |
| L17 | Stage 拓扑不硬编码——Pipeline/Iterative/Declarative 三种模式 | 四方评审一致 |
| L18 | Delivery Gate 双层化——Hard Gate（程序化）+ Soft Gate（LLM-as-Judge） | 四方评审一致 |
| L19 | Spec Lock 判断用领域无关元准则 (a)(b)(c)，不用单一领域参数列表 | 模型评审 |
| L20 | 知识默认全量内联——单文件自包含后不再有 references/ 按需加载 | v1.8 全量注入原则 |
| L21 | 晶体必须经过效能验证（A/B 对照）——覆盖率达标不等于有效 | CEO 审查 |
| L22 | State Semantics 是 Harness 四组件之一（Contracts/Stage/Failure/State），不是 IR 附属字段 | 三方评审共识 |
| L23 | 没有 trace 就没有可诊断性，trace schema 必须在编译时声明 | Harness 研究报告 |
| L24 | 长任务（Iterative 类型）必须 per-stage 渐进披露知识 | Sonnet 独立发现 |
| L25 | 每个 stage 必须有 checkpoint 语义——durable execution 是中断可恢复的基础能力 | Harness 研究报告 |
| L26 | 工具可调用 ≠ 工具可用——tool ergonomics 直接影响 agent 成功率 | Anthropic 最佳实践 |
| L27 | Spec Lock 必须消费 type=M（数学/模型选择）——M 类参数是 AI 最容易自主替换的 | bp-009 v3.1 验证 |
| L28 | Failure Taxonomy 需要 model_misuse 失败类——方法替换≠参数漂移，需独立恢复路径 | bp-009 验证 |
| L29 | 知识覆盖率标准必须含 M 类 100% 覆盖——M 类知识是 AI 原本最不知道的 | 量化评价框架 v1.0 |
| L30 | context_acquisition 必须有降级模式——多数蓝图可能没有 BD/UC，仅有 replaceable_points | 59 蓝图现状验证 |
| L31 | 用户记忆查询是 context_acquisition 的第一步——主动挖掘优于被动提问 | 产品宪法 Phase 2 Step 6 |
| L32 | SKILL 必须附带人话摘要（用户看摘要，AI 看晶体）——用户不读晶体内部结构 | 产品宪法 §1.8 第 3 条 |
| L33 | machine_checkable=true 的约束是天然 Hard Gate 候选——约束 SOP v2.1 新增判定标准后可自动纳入 | bp-009 约束质量数据 |
| L34 | 晶体必须单文件自包含（产品宪法 §3.4）——用户丢一个文件给 AI 即可用，不丢目录 | 产品宪法 + bp-009 v1.6→v1.7 修正 |
| L35 | 知识组织默认全量注入——非不必要不压缩，注意力管理靠分步执行不靠裁减知识量 | CEO 明确原则 + bp-009 v1.7→v1.8（覆盖率 12%→96%） |
| L36 | 用例消歧需 negative_keywords + 排除词 + ambiguity_question，否则运行时误匹配 | 四方评审共识 + bp-009 v1.8 OpenClaw 实测 |
| L37 | context_acquisition 从建议升级为状态机（CA1→CA4），未确认禁止生成代码 | 四方评审共识 |
| L38 | Spec Lock 分语义层（semantic_locks, FATAL）和实现层（implementation_hints, WARN） | 四方评审共识 |
| L39 | 宿主 AI 会二次处理晶体（非直接执行）——需 preservation_manifest 保真校验 + output_validator 产出校验 | bp-009 v1.8 OpenClaw 实测（Opus 评审发现） |
| L40 | 控制块以"知识"方式生效而非"指令"方式被解析——宿主 AI 内化行为约束而非机械执行 YAML，context_state_machine 渲染为 Step 顺序即可 | bp-009 v1.9 OpenClaw 实测（3 次测试一致） |
| L41 | output_validator 作为自然语言描述时是软约束——必须渲染为可执行 assert 代码块才能硬化为自动检查 | bp-009 v1.9 布林带回测（异常值靠 AI 自觉，非硬机制） |
| L42 | 领域 RC 约束（如 T+1/涨跌停）在宿主 AI 自写回测时不会自动生效——必须在资源段提供回测安全检查代码模板供 copy-paste | bp-009 v1.9 布林带回测（手动 256 行代码无 T+1 检查） |
| L43 | 安全检查函数作为独立模板时被 AI 内化而非引用——升级为骨架模式，安全代码焊死在结构中，AI 只填策略逻辑 | bp-009 v2.0 MACD+均线回测（安全函数 0/5 被调用，但 T+1 自主实现） |
| L44 | 晶体编译语言默认英文——全球 AI 消费需要通用语言 | 全球化需求 |
| L45 | 编译强度分三档（scout/standard/thorough）——避免全量编译浪费 | Meta-Harness 研究 |
| L46 | 预检验证在编译流水线开头——便宜的错误早抓 | LlamaIndex 研究 |
| L47 | 跨项目约束匹配不是堆砌——需要语义评分+去重+归因 | 产品需求 |
| L48 | 质量校验分确定性/语义两遍——确定性检查失败时语义检查不可靠 | Meta-Harness 研究 |
| L49 | trace 诊断禁止摘要——完整 trace 是唯一可靠的因果链来源 | Meta-Harness 研究 |
| L50 | Iterative 模式需 forced checkpoint injection——防止 agent 静默探索无产出 | LlamaIndex 研究 |
| L51 | 语言适配不做多语言编译——嵌入 Runtime Language Protocol 让宿主 AI 用原生多语言能力适配 | 第一性原理推导 |

<!-- DOMAIN: 此处追加领域特有教训 -->

---

*通用模板 | 基于 SOP v3.1 提炼 | 编译领域 SOP 时参考此文件*
