# 晶体编译 SOP v1.4

> **定位**：蓝图提取 SOP v2.3 和约束采集 SOP v1.3 的下游消费者。
> 输入是已提取的蓝图+约束+资源，输出是可部署的晶体。
> **此 SOP 是领域无关的**。
>
> **版本历史**：
> - v1.0：首版，首测通过但发现严重认知错误（timeout/体积限制编撰）
> - v1.1：修正事实错误
> - v1.2：补知识压缩 + SKILL.md 渲染 + 领域通用化
> - v1.3：四方评审（Grok/Gemini/GPT/Sonnet）驱动的 7 项改进——时效性管理、References 强制加载、Stage 拓扑泛化、Delivery Gate 双层化、Spec Lock 领域无关元准则、知识压缩补 Actionability 维度、非金融 worked example
> - **v1.4**：Harness Engineering 研究报告 + 三方评审对照审计驱动的 5 项架构补全——State Semantics 独立步骤化、Trace Schema 引入、Stage Checkpoint（durable execution）、Per-stage 渲染模式、Tool Ergonomics

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
| `known_use_cases` | 蓝图中索引的典型使用场景 |
| `must_validate` | 每个 use case 中列出的验收要点 |
| `known_gap` | 蓝图中标注的已知缺失/风险 |
| `severity` | 约束的严重程度（fatal/critical/high/medium） |

---

## 核心原则

**晶体 = 好的蓝图 + 好的资源 + 好的约束 + 好的 Harness**

四层缺一不可。Harness 是让知识正确发挥作用的手段，**不能替代知识本身**。
晶体的核心价值是让 AI 获得它原本没有的领域知识。

Harness 包含五个子系统（v1.4 完整化）：
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

---

## 输入

| 输入 | 来源 | 要求 |
|------|------|------|
| Blueprint YAML | 蓝图提取 SOP v2.3 | 含 business_decisions + known_use_cases |
| Constraints JSON/JSONL | 约束采集 SOP v1.3 | 含 severity、constraint_kind、stage_ids |
| Resources | 蓝图 replaceable_points | 含 options、fit_for |
| User Intent | 用户/产品经理 | 目标环境、任务类型、产出类型 |
| Target Host | 部署决策 | openclaw / claude_code / generic |
| Host Spec | `docs/research/host-specs/{host}-host-spec.md` | 宿主能力规范，不编撰 |

## 输出

| 输出 | 格式 | 用途 |
|------|------|------|
| Crystal IR | `crystal-{id}.ir.yaml` | 结构化中间表示 |
| seed.md | 每宿主一份 | 一次性执行指令 |
| SKILL bundle | `{skill-name}/` 目录 | 可复用 OpenClaw skill |

---

## Step 1: Execution Contract 编写

### 1a. Spec Lock 提取

**输入**：蓝图 `business_decisions` 中 type=B 或 type=BA 的条目。

**可漂移参数的判断元准则**（领域无关，v1.3 升级）：

一个参数是否需要锁定，取决于以下三个条件，**满足任一即锁**：

| 元准则 | 说明 | 金融例 | Web 例 | 数据例 |
|--------|------|--------|--------|--------|
| **(a) AI 无约束时会自主选择** | AI 有自己的"默认偏好"，会偏离用户意图 | TOP_N=5→AI 改 30 | App Router→AI 用 Pages Router | materialization=view→AI 改 table |
| **(b) 不同选择导致结果不可比较** | 参数变化后产出的性质发生质变 | 动量策略→布林带策略 | SSR→CSR（SEO 完全不同） | incremental→full refresh |
| **(c) 与用户意图直接绑定** | 用户明确要求了这个值 | "A 股回测" | "TypeScript 项目" | "每日增量更新" |

**格式**：
```yaml
- param: {参数名}
  value: {锁定值}
  violation: FATAL | WARN
  rationale: {为什么锁}
```

**规则**：
- type=RC（外部强制规则）→ 一律 `violation: FATAL`
- 路径参数使用 `{workspace}` 占位符

### 1b. Delivery Gate 提取

**输入**：`known_use_cases[target].must_validate` + severity=fatal 约束。

**三类通用 Gate**（领域无关，v1.3 升级）：

| Gate 类别 | 说明 | 金融例 | Web 例 | 数据例 |
|-----------|------|--------|--------|--------|
| **产出存在性** | 交付物文件/服务/端点存在 | 结果文件存在 | `next build` 成功 | 所有 model 编译通过 |
| **执行正确性** | 主流程无错误完成 | 回测完成无异常 | `curl localhost:3000` 返回 200 | `dbt test` 全部通过 |
| **业务合理性** | 结果不是"表面通过实际无效" | abs(return)>1%, trades>0 | 页面有实际内容（非空白） | 输出行数>0, 无全 NULL 列 |

**Hard Gate vs Soft Gate**（v1.3 新增）：

| 类型 | 定义 | on_fail | 适用场景 |
|------|------|---------|---------|
| **Hard Gate** | 可程序化验证（exit code / regex / 数值比较） | RERUN / REBUILD | 构建成功、指标阈值、文件存在 |
| **Soft Gate** | 需要 AI self-check 或 LLM-as-Judge | WARN + 输出评估报告 | 架构一致性、代码质量、设计意图符合 |

每个晶体至少 3 条 Hard Gate。Soft Gate 可选但必须有明确 rubric（评判标准）。

---

## Step 2: Failure Taxonomy 编写

### 2a. 通用失败类（6 条，领域无关）

| 失败类 | 触发条件 | 恢复动作 | 禁止动作 |
|--------|---------|---------|---------|
| `exec_rejected` | 宿主拒绝执行命令 | 重写命令为白名单格式 | 不重试相同命令 |
| `param_drift` | spec_lock 参数偏离锁定值 | 立即恢复锁定值 | 不辩解修改理由 |
| `timeout_risk` | 预估剩余工作 > 50% 时间预算 | 简化方案 | 不增加工具调用 |
| `framework_dead_end` | 框架/依赖错误重试 2 次仍失败 | 切换替代方案 | 不继续重试 |
| `mode_switch` | 产出文档/分析而非可执行交付物 | 删除文档，重新生成交付物 | 不产出参考文档 |
| `silent_drift` | 架构/方法偏离规格但未报错 | 对照 spec_lock 逐项检查 | 不假设"接近"可以 |

### 2b. 领域特定失败类派生

从蓝图 `known_gap=true` + 约束 severity=fatal/critical 派生。每条必须有**具体 recovery action**。

---

## Step 3: 任务类型判断 + Stage Spec（v1.3 重构，v1.4 增加 checkpoint）

### 3a. 任务类型判断

在设计阶段拓扑前，先判断任务类型：

| 类型 | 特征 | 典型场景 | 流控模式 |
|------|------|---------|---------|
| **A：一次性产出** | 输入确定→处理→输出确定 | 回测、报告生成、数据转换、脚手架生成 | **Pipeline** |
| **B：迭代构建** | 需要写→测→改循环 | Web 应用、移动端应用、重构、AI 系统 | **Iterative** |
| **C：声明式配置** | 产出是配置文件/DAG/规则 | dbt、Terraform、K8s、CI/CD | **Declarative** |

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
implement↔test 允许内循环，必须声明 `max_iterations`（防止无限循环）。

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

### 3d. Checkpoint 语义（v1.4 新增）

**来源**：Harness Engineering 研究报告 — durable execution 是生产级 agent 的基础能力，不是高级选项。

每个 stage 必须声明 checkpoint 行为，使任务在中断后可恢复：

| 字段 | 说明 | 必填 |
|------|------|------|
| `checkpoint_artifact` | 本阶段完成后应持久化的制品路径 | 是 |
| `resume_condition` | 恢复时的前置检查（"该制品存在且有效"） | 是 |
| `resume_action` | 恢复时跳过本阶段 / 从断点续跑 / 完全重跑 | 是 |

**三种 resume_action**：

| 动作 | 适用场景 | 示例 |
|------|---------|------|
| **skip** | 该阶段产出幂等，制品存在即可跳过 | setup 阶段的依赖安装 |
| **resume** | 可以从中间状态继续 | 多文件构建的 implement 阶段（已完成的文件不重写） |
| **rerun** | 必须完全重新执行 | validate 阶段（验证必须基于最新制品） |

**Pipeline 模式 checkpoint 示例**：
```yaml
stages:
  - name: setup
    checkpoint_artifact: "{workspace}/.setup_done"
    resume_condition: "标记文件存在 + 依赖可 import"
    resume_action: skip
  - name: execute
    checkpoint_artifact: "{workspace}/result.csv"
    resume_condition: "结果文件存在且非空"
    resume_action: skip
  - name: validate
    checkpoint_artifact: null  # 验证不产出持久制品
    resume_condition: null
    resume_action: rerun  # 验证必须每次重跑
  - name: deliver
    checkpoint_artifact: "{workspace}/delivery_manifest.json"
    resume_condition: "清单文件存在"
    resume_action: skip
```

**Iterative 模式 checkpoint 示例**：
```yaml
stages:
  - name: setup
    checkpoint_artifact: "{workspace}/.setup_done"
    resume_action: skip
  - name: scaffold
    checkpoint_artifact: "{workspace}/src/index.tsx"
    resume_condition: "骨架文件已存在"
    resume_action: skip
  - name: implement_test_loop
    checkpoint_artifact: "{workspace}/.iteration_state.json"
    resume_condition: "状态文件记录了已完成的迭代和待办"
    resume_action: resume  # 从上次迭代断点继续
  - name: deliver
    checkpoint_artifact: null
    resume_action: rerun
```

---

## Step 4: State Semantics 编写（v1.4 新增）

**来源**：三方评审一致认定 State Semantics 是 4 个必须引入的 NLAH 组件之一（Contracts ✅ Stage ✅ Failure ✅ State ⬜）。v1.3 仅在 IR 模板中有 `state_slots` 字段，未给出设计方法论。

**核心命题**：agent 的中间状态如果只存在于上下文窗口中，一旦窗口压缩、session 中断、或宿主重启，状态即丢失。State Semantics 的目标是将关键状态**外化为文件制品**（artifact-backed state），使状态可持久、可恢复、可审计。

### 4a. State Slot 设计

**State Slot** 是一个持久化状态单元。每个 slot 必须声明：

| 字段 | 说明 | 示例 |
|------|------|------|
| `slot_id` | 唯一标识 | `plan`, `result`, `evidence` |
| `path` | 文件路径模板 | `{workspace}/.state/{slot_id}.json` |
| `purpose` | 该状态的职责（一句话） | "记录已完成的构建步骤和待办" |
| `write_stage` | 哪个阶段写入 | `setup`, `execute` |
| `read_stages` | 哪些阶段读取 | `["validate", "deliver"]` |
| `format` | 文件格式 | `json`, `yaml`, `markdown`, `csv` |
| `compaction_stable` | 是否在上下文压缩后仍需可访问 | `true` / `false` |

### 4b. 四类通用 State Slot

任何任务类型都应考虑以下四类状态（按需选用，非全部必填）：

| Slot 类型 | 职责 | compaction_stable | 适用任务类型 |
|-----------|------|-------------------|-------------|
| **Plan** | 任务分解、步骤清单、进度标记 | true | B（迭代构建）必须，A/C 可选 |
| **Working Memory** | 中间计算结果、临时发现、调试线索 | false | 长时间任务推荐 |
| **Evidence** | 验证结果、测试输出、截图、日志 | true | 有 Soft Gate 时必须 |
| **Result Manifest** | 最终交付物清单 + 元数据 | true | 所有任务类型推荐 |

### 4c. Compaction Stability（上下文压缩稳定性）

**核心洞察**（来自三方评审 Q6 共识）：性能提升的真正来源不是"自然语言更好"，而是 **artifact-backed closure**——关键状态写入文件后，即使上下文窗口压缩，AI 仍可通过 read 工具恢复状态。

标记为 `compaction_stable: true` 的 slot 必须满足：
1. **自包含**：单独读取该文件即可理解状态，不依赖上下文中的对话历史
2. **结构化**：使用 JSON/YAML/表格，不是自由散文
3. **可增量更新**：AI 可以 read → modify → write，而非每次全量重写

**反模式**：
- 把进度写在对话中而非文件中 → 压缩后丢失
- state 文件内容依赖"之前聊过的"某个决策 → 自包含性不足
- state 文件用散文描述进度 → 不可结构化解析

### 4d. State Lifecycle 规则

| 规则 | 说明 |
|------|------|
| **创建即声明** | state slot 在 Crystal IR 中预声明，不是运行时随意创建 |
| **写入即 checkpoint** | 每次写入 state 文件等价于创建一个 checkpoint |
| **读取优先于记忆** | AI 应 read state 文件获取状态，不应从上下文"回忆" |
| **冲突以文件为准** | 如果上下文记忆与 state 文件矛盾，以文件为准 |

### 4e. 跨任务类型 State 设计示例

**Pipeline（金融回测）**：
```yaml
state_slots:
  - slot_id: result
    path: "{workspace}/backtest_result.csv"
    purpose: "回测结果数据，validate 阶段读取验证"
    write_stage: execute
    read_stages: [validate, deliver]
    format: csv
    compaction_stable: true
```

**Iterative（Next.js 应用）**：
```yaml
state_slots:
  - slot_id: plan
    path: "{workspace}/.state/build_plan.json"
    purpose: "构建计划：已完成/进行中/待办组件列表"
    write_stage: scaffold
    read_stages: [implement_test_loop, deliver]
    format: json
    compaction_stable: true
  - slot_id: evidence
    path: "{workspace}/.state/test_results.json"
    purpose: "每轮 implement↔test 循环的测试结果累积"
    write_stage: implement_test_loop
    read_stages: [implement_test_loop, deliver]
    format: json
    compaction_stable: true
```

**Declarative（dbt 管线）**：
```yaml
state_slots:
  - slot_id: manifest
    path: "{workspace}/.state/generated_models.json"
    purpose: "已生成的 dbt model 清单 + 状态"
    write_stage: generate
    read_stages: [verify, apply]
    format: json
    compaction_stable: true
```

---

## Step 5: Host Adapter 编写（v1.4 增加 Tool Ergonomics）

### 5a. 基本适配

**原则**：白名单优先 + 引用 Host Spec + `{workspace}` 占位符。

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
| SKILL.md | 宿主 runtime（触发时） | skill 目录路径 |
| scaffold | AI（填充时） | 用户确认的工作目录 |

### 5b. Tool Ergonomics（v1.4 新增）

**来源**：Anthropic "Writing effective tools for agents" + Harness Engineering 研究报告趋势 5（tool callable → tool usable）。

**核心洞察**：agent 失败常常不是"模型不会"，而是"工具和环境被设计得不适合 agent 使用"。晶体编译时应评估目标宿主的工具生态，并在 Host Adapter 中记录关键工具使用指导。

**评估维度**：

| 维度 | 说明 | 示例 |
|------|------|------|
| **工具命名清晰度** | 工具名是否自解释 | `run_python` 优于 `exec` |
| **工具重叠** | 是否有多个工具做类似的事（AI 会困惑） | write_file vs create_file |
| **返回值信号密度** | 工具返回是高信号还是低层噪音 | 返回"编译成功" vs 返回 10KB raw log |
| **Token 成本** | 工具调用的 input/output token 开销 | 大文件 read 的 token 成本 |

**Host Adapter 中的 tool guidance 格式**：

```yaml
tool_guidance:
  preferred_tools:
    - tool: "write_file"
      when: "创建新文件或完整重写"
    - tool: "run_python"
      when: "执行 Python 脚本"
  avoid_tools:
    - tool: "edit_file"
      reason: "对大段替换容易出错，优先 write_file 全量写入"
  tool_patterns:
    - pattern: "先 write 再 run"
      rationale: "确保文件落盘后再执行，避免执行旧版本"
```

**注意**：tool guidance 来自 Host Spec 的实际工具清单，不编撰。如果 Host Spec 未记录某工具的行为特征，标注为 `"behavior: unverified"`。

---

## Step 6: 知识压缩

### 6a. 四维筛选（v1.3：增加 Actionability）

每条知识按四个维度打分：

**维度 1：AI 新颖度**

| 等级 | 判断方法 | 处理 |
|------|---------|------|
| HIGH | AI 大概率不知道（领域特有、版本特定、框架内部行为） | 完整描述 |
| MEDIUM | AI 可能知道但容易出错 | 简要提醒 |
| LOW | AI 几乎肯定知道（通用编程知识） | 省略 |

判断辅助方法：用标准化测试提示词问目标模型该知识点，看回答是否正确。避免纯主观猜测。

**维度 2：失败预防度**

| 等级 | 判断标准 | 处理 |
|------|---------|------|
| CRITICAL | 直接防止已知失败案例 | 必须包含 |
| HIGH | 防止蓝图 known_gap 风险 | 应当包含 |
| LOW | 通用最佳实践，无对应失败 | 可省略 |

**维度 3：阶段相关度**

| 等级 | 处理 |
|------|------|
| 当前阶段直接相关 | 注入当前阶段 |
| 跨阶段通用 | 注入 Contract 或全局知识节 |
| 其他阶段专用 | 放 references/ 按需加载 |

**维度 4：操作化程度（Actionability）**（v1.3 新增）

| 等级 | 说明 | 处理 |
|------|------|------|
| HIGH | 包含具体指令、代码示例、精确数值 | 优先内联正文 |
| LOW | 抽象建议（"需谨慎"、"建议优化"） | 改写为具体指令后再内联，或降级到 references/ |

示例对比：
- LOW："dbt 增量模型需要谨慎设计唯一键策略"
- HIGH："dbt 增量模型必须在 `unique_key` 使用复合键 `['id', 'updated_at']`，单字段唯一键在重跑时产生重复数据"

### 6b. 压缩规则

1. **CRITICAL 失败预防 OR HIGH 新颖度**：完整包含，不压缩
2. **MEDIUM 新颖度 AND HIGH 失败预防**：简要包含（一句话 + 关键数值）
3. **三维均为 MEDIUM**：按需引用（放 references/）
4. **LOW 新颖度 AND LOW 失败预防**：省略
5. **LOW Actionability 的知识**：改写为 HIGH Actionability 后按上述规则处理，无法改写则降级到 references/

### 6c. 覆盖率标准

- type=RC（外部强制规则）：**100%** 覆盖
- type=B（业务决策）：**≥ 80%** 覆盖
- severity=fatal 约束：**100%** 覆盖
- severity=high + 本用例 stage 匹配：**≥ 60%** 覆盖
- HIGH 新颖度知识占总量 **≥ 40%**

### 6d. 非金融 worked example：Next.js App Router 晶体

| 知识项 | 新颖度 | 失败预防 | 阶段 | Actionability | 决策 |
|--------|--------|---------|------|--------------|------|
| Server Components 默认，只有 useState/useEffect/浏览器 API 才加 `'use client'` | MEDIUM | CRITICAL | implement | HIGH | **内联**（Rule 2） |
| App Router 的 `loading.tsx` 自动 Suspense boundary | HIGH | HIGH | implement | HIGH | **完整描述**（Rule 1） |
| Tailwind class 排序风格 | LOW | LOW | implement | LOW | **省略**（Rule 4） |
| `next.config.js` 中 `images.remotePatterns` 安全配置 | HIGH | CRITICAL | setup | HIGH | **完整描述**（Rule 1） |
| React 18 并发特性基础 | LOW | LOW | — | LOW | **省略**（Rule 4） |

---

## Step 7: Crystal IR 组装（v1.4 增加 state_semantics + trace_schema）

```yaml
version: "1.4"
crystal_id: "{domain}-bp-{id}-{use_case}"
task_type: "A | B | C"  # Pipeline / Iterative / Declarative

references:
  blueprint: "path/to/blueprint.yaml"
  constraints: ["path/to/constraints.jsonl"]
  use_case: "use_case_name"
user_intent: { ... }

knowledge:
  business_decisions: [ 经四维筛选后的条目 ]
  constraints:
    fatal: [ 全量 ]
    high_relevant: [ stage 匹配的 ]
  resources:
    external_services: [ API / 数据源 / 第三方服务 ]
    dependencies: [ 包依赖 ]
    infrastructure: [ 存储 / 计算 / 部署环境 ]
  references:
    - path: "references/blueprint-full.md"
      load_trigger: "FORCED_READ_BEFORE_STAGE_2"
    - path: "references/constraints-by-stage.md"
      load_trigger: "ON_DEMAND"

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
  # v1.4 新增：State Semantics
  state_semantics:
    slots:
      - slot_id: "plan"
        path: "{workspace}/.state/plan.json"
        purpose: "..."
        write_stage: "..."
        read_stages: [...]
        format: "json"
        compaction_stable: true
      - slot_id: "evidence"
        path: "{workspace}/.state/evidence.json"
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
  host_adapters: { ... }

# v1.4 新增：Trace Schema
trace_schema:
  events:
    - type: stage_transition
      fields: [from_stage, to_stage, timestamp, exit_criterion_met]
      purpose: "记录阶段切换，用于诊断卡在哪个阶段"
    - type: tool_call
      fields: [tool_name, arguments_summary, result_summary, success, duration_hint]
      purpose: "记录工具调用，用于分析工具使用模式和失败点"
    - type: artifact_emission
      fields: [artifact_path, size_bytes, stage, slot_id]
      purpose: "记录制品产出，用于验证 state 持久化是否正确"
    - type: validation_result
      fields: [gate_id, gate_type, expected, actual, passed]
      purpose: "记录每个 delivery gate 的验证结果"
    - type: failure_event
      fields: [failure_class, trigger_detail, recovery_action_taken, resolved]
      purpose: "记录失败发生和恢复，用于 failure taxonomy 迭代"
    - type: spec_lock_check
      fields: [param, locked_value, actual_value, drifted]
      purpose: "记录参数漂移检查，用于 spec_lock 有效性分析"
  output:
    format: "jsonl"
    path: "{workspace}/.trace/execution_trace.jsonl"
    when: "宿主支持文件写入时生成；宿主不支持时降级为结构化 stdout"

# v1.3 保留：时效性管理
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
  expires_at: null  # 或指定日期

compilation:
  sop_version: "crystal-compilation-v1.4"
  compiled_at: "ISO date"
```

### Trace Schema 设计原则

1. **trace 是可选但推荐的**——不是所有宿主都支持 trace 输出，但 schema 必须在 IR 中声明
2. **trace 由 AI 在执行过程中写入**——作为 state 文件的一种特殊形态
3. **trace 服务于迭代**——如果没有 trace，则无法回答"为什么这个晶体在这个宿主上失败了"
4. **trace 不污染交付物**——trace 文件放在 `.trace/` 目录，不混入用户工作目录
5. **六种事件类型覆盖 harness 全生命周期**——stage transition + tool call + artifact emission + validation + failure + spec_lock check

### Trace 与 Step 10（效能验证）的关系

Step 10 的 A/B 对照实验可以利用 trace 做更精确的归因分析：

- 对比有晶体 vs 无晶体的 `tool_call` 事件差异 → 晶体是否改变了工具使用模式
- 对比 `spec_lock_check` 事件 → 晶体是否有效防止了参数漂移
- 对比 `failure_event` → 晶体是否减少了失败次数或加速了恢复
- 对比 `stage_transition` 的时间间隔 → 晶体是否改变了执行效率

---

## Step 8: 宿主渲染（v1.4 增加 per-stage 渲染模式）

### 渲染原则

1. **知识与 Harness 平衡**
2. **路径参数化**（`{workspace}`）
3. **从 Host Spec 派生**，不编撰
4. **References 强制加载**（v1.3：不是"请阅读"，是"必须先 read 工具调用"）

### 8a. seed.md 渲染（一次性渲染）

适用于 **Pipeline 模式（类型 A）** 和 **Declarative 模式（类型 C）**——任务短、阶段少、上下文不会被压缩。

渲染模板中关于 references 的指令改为**强制 Tool Call**：

```markdown
## 执行前强制读取（FATAL：未读取不可继续）

在开始任何生成前，你必须执行以下读取并确认内容已加载：
1. 读取 `references/blueprint.md` → 确认已获取蓝图核心知识
2. 读取 `references/api-examples.md` → 确认已获取正确 API 调用格式

如果上述文件不存在或读取失败，立即报告错误，不要从自身知识编造内容。
```

### 8b. SKILL.md 渲染

目录结构：
```
{skill-name}/
  SKILL.md              # ≤ 80 行正文
  references/
    blueprint.md        # 完整蓝图知识
    constraints.md      # 按阶段分组的约束
    api-examples.md     # 正确 API 调用示例
  scaffolds/
    {output}.scaffold.md
```

SKILL.md 执行流程中强制读取步骤（v1.3）：
```markdown
## 执行流程
1. **[FATAL]** 执行 read 工具读取 `references/blueprint.md`，确认返回内容后继续
2. **[FATAL]** 执行 read 工具读取 `references/api-examples.md`
3. 读取 `scaffolds/{output}.scaffold.md` 获取输出骨架
4. 按 REPLACE_WITH 占位符逐项填充
5. 写入 `{workspace}/{output}`
6. 验证交付门禁（Hard Gate 全部通过，Soft Gate 输出评估）
```

### 8c. Per-stage 渲染（v1.4 新增）

**来源**：Sonnet 独立发现——"不应一次性渲染 seed.md，应按阶段渲染不同部分（setup 加载资源、execute 加载蓝图+约束、validate 加载 Contract）"。

**适用于 Iterative 模式（类型 B）**——任务长、多轮迭代、上下文会被压缩。

**核心思路**：不将全部知识一次性灌入 seed.md，而是按阶段渐进披露（progressive disclosure），每个阶段只加载该阶段需要的知识。

**渲染产物**：

```
{skill-name}/
  SKILL.md                          # 总入口（≤ 80 行）：角色 + 整体流程 + state 指引
  stages/
    01-setup.md                     # setup 阶段知识：环境配置 + 依赖安装
    02-scaffold.md                  # scaffold 阶段知识：蓝图结构 + 骨架模板
    03-implement-test.md            # implement↔test 循环：约束 + failure taxonomy + 代码模板
    04-deliver.md                   # deliver 阶段知识：delivery gate + 交付格式
  references/
    blueprint.md
    constraints-by-stage.md
    api-examples.md
  scaffolds/
    {output}.scaffold.md
```

**SKILL.md 总入口模板**：
```markdown
## 你的角色
你是一个 builder。按阶段推进，每个阶段开始前读取对应的阶段文件。

## 执行流程
1. **[FATAL]** 读取 `stages/01-setup.md`，按指引完成环境准备
2. 写入 state：`{workspace}/.state/plan.json`（记录构建计划）
3. **[FATAL]** 读取 `stages/02-scaffold.md`，按指引生成骨架
4. **[FATAL]** 读取 `stages/03-implement-test.md`，进入 implement↔test 循环
5. 每轮循环结束后更新 `{workspace}/.state/plan.json`
6. 循环完成后，读取 `stages/04-deliver.md`，执行交付验证

## State 文件
- 如果 `{workspace}/.state/plan.json` 已存在，先读取并从断点继续
- 每完成一个里程碑，更新 plan.json
```

**Per-stage vs 一次性渲染的选择标准**：

| 条件 | 选择 |
|------|------|
| 任务类型 A（Pipeline）或 C（Declarative） | 一次性渲染（seed.md / SKILL.md） |
| 任务类型 B（Iterative）且总知识 < 4000 tokens | 一次性渲染 |
| 任务类型 B（Iterative）且总知识 ≥ 4000 tokens | **Per-stage 渲染** |
| 宿主上下文窗口 < 32K tokens | **Per-stage 渲染**（强制） |

### 8d. 渲染后检查

| 检查项 | 标准 |
|--------|------|
| 知识覆盖率 | RC 100%, B ≥ 80%, fatal 100%, high 相关 ≥ 60% |
| 知识 Actionability | 内联知识中 HIGH actionability ≥ 70% |
| References 强制读取 | 有 `[FATAL] 执行 read 工具` 指令 |
| 路径参数化 | 无硬编码用户路径 |
| Host Spec 对齐 | 所有平台数值有证据 |
| Hard Gate ≥ 3 条 | 至少 3 条可程序化验证的 gate |
| 时效性元数据 | version_pins 和 review_triggers 已填写 |
| SKILL.md 规范 | frontmatter 正确，正文 ≤ 80 行，metadata 单行 JSON |
| **State 指引** | 渲染中包含 state 文件路径 + read/write 指令（v1.4） |
| **渲染模式匹配** | Pipeline/Declarative 用一次性，长 Iterative 用 per-stage（v1.4） |

---

## Step 9: 质量校验

| 检查项 | 标准 | 不通过时 |
|--------|------|---------|
| Contract 完整性 | spec_lock 覆盖所有满足元准则(a)(b)(c)的参数 | 补充 |
| Delivery Gate | ≥ 3 Hard Gate + Soft Gate 有 rubric | 补充 |
| Failure Taxonomy | 6 通用 + ≥ 2 领域特定 | 补充 |
| Stage 任务类型 | 任务类型判断正确，流控模式匹配 | 重新判断 |
| **Checkpoint 完整性** | 每个 stage 有 checkpoint_artifact + resume_action（v1.4） | 补充 |
| **State Semantics** | 至少 1 个 compaction_stable slot（v1.4） | 设计 state slot |
| 知识覆盖率 | 达到 6c 标准 | 补充知识 |
| 知识 Actionability | LOW actionability 知识已改写或降级 | 改写 |
| References 强制加载 | 渲染中有 FATAL read 指令 | 添加 |
| 路径参数化 | 无硬编码用户路径 | 替换 |
| Host Spec 对齐 | 所有数值有证据 | 查证修正 |
| **Tool Guidance** | Host Adapter 包含 preferred/avoid tools（v1.4） | 从 Host Spec 补充 |
| **Trace Schema** | IR 中有 trace_schema 声明（v1.4） | 补充 |
| **时效性** | version_pins 覆盖所有框架依赖，RC 类 decision 有 review_trigger | 补充 |
| **渲染模式** | 任务类型与渲染模式匹配（v1.4） | 调整 |
| **跨领域可执行** | 非本领域工程师阅读 SOP 后能理解每个判断点 | 补充示例 |

---

## Step 10: 晶体效能验证

**目的**：验证晶体是否真的让 AI 做得更好。覆盖率达标不等于有效——v1.0 首测知识覆盖率仅 6% 但 AI 仍通过全部 gate，说明可能靠自身能力完成而非靠晶体知识。

### 10a. 基线测试（无晶体）

给目标宿主**同样的 user_intent**，但**不给晶体**，只给一句话任务描述。

```
示例（金融）：
  有晶体时的 intent："A 股 MACD 日线金叉择时策略回测"
  基线 prompt："请帮我做一个 A 股 MACD 金叉策略的回测"

示例（Web）：
  有晶体时的 intent："基于 Next.js App Router 构建 SSR 博客应用"
  基线 prompt："请帮我用 Next.js 做一个博客网站"
```

记录基线产出：
- 是否完成任务
- 产出质量（Delivery Gate 通过数）
- 关键决策点 AI 做了什么选择（用什么框架/参数/架构）
- 出现了哪些错误

### 10b. 晶体测试（有晶体）

给目标宿主**同样的 user_intent** + **编译好的晶体**（seed.md 或 SKILL.md）。

记录同样的指标。

### 10c. 效能对比

| 对比维度 | 基线 | 晶体 | 判定 |
|---------|------|------|------|
| Hard Gate 通过数 | X/N | Y/N | Y > X 为有效 |
| 关键参数是否漂移 | 列出漂移项 | 列出漂移项 | 晶体版漂移更少为有效 |
| 错误类型 | 列出 | 列出 | 晶体版避免了基线的错误为有效 |
| 领域知识应用 | AI 是否犯了领域错误 | AI 是否正确应用了领域知识 | 最核心判据 |
| 交付时间 | T1 | T2 | 参考项，不作为主判据 |

**判定标准**：

| 结果 | 含义 | 动作 |
|------|------|------|
| 晶体版 Hard Gate 通过数 > 基线 | 晶体有效 | 可发布 |
| 晶体版避免了基线的领域错误 | 知识注入生效 | 可发布 |
| 晶体版与基线无显著差异 | **晶体无效** | 回到 Step 6 重新筛选知识——可能是 HIGH 新颖度的知识不够，或者 Actionability 不足 |
| 晶体版反而比基线差 | **晶体有害** | 回到 Step 1 检查 spec_lock 是否过度限制，或约束是否有错 |

### 10d. 知识归因分析（v1.4：可利用 trace 增强）

对比基线和晶体的 AI 行为差异，回答：

1. **哪些知识改变了 AI 的行为？**（在基线中犯的错误，在晶体版中被避免了）
   → 这些是晶体最有价值的知识，确认它们的四维评分正确
2. **哪些知识被忽略了？**（晶体中有但 AI 没使用）
   → 检查：是 Actionability 不够？位置不对（应该内联但放了 references/）？还是被其他指令淹没？
3. **AI 自主补充了哪些晶体没有的知识？**（晶体没覆盖但 AI 自己做对了）
   → 这些知识的 AI 新颖度应标为 LOW，下次编译可省略

**v1.4 增强**：如果宿主支持 trace 输出（trace_schema），可用以下 trace 事件做更精确的归因：

| 归因分析 | 使用的 trace 事件 | 对比方法 |
|---------|-----------------|---------|
| 参数漂移防止效果 | `spec_lock_check` | 基线 drifted=true 次数 vs 晶体版 |
| 失败恢复效率 | `failure_event` | 基线失败次数 + 恢复时间 vs 晶体版 |
| 工具使用模式差异 | `tool_call` | 基线调用了哪些工具 vs 晶体版 |
| 阶段执行效率 | `stage_transition` | 各阶段耗时对比 |

### 10e. 验证通过标准

| 检查项 | 标准 | 不通过时 |
|--------|------|---------|
| 效能提升 | 晶体版至少在 1 个维度显著优于基线 | 回到 Step 6 |
| 无负面效应 | 晶体版不比基线差 | 回到 Step 1 检查过度约束 |
| 知识生效 | 至少 1 条 HIGH 新颖度知识在 10d 中被确认"改变了 AI 行为" | 补充更多 HIGH 新颖度知识 |

**注意**：Step 10 不是每次编译都必须跑完整 A/B 测试。建议：

- **新蓝图首次编译**：必须完整跑 10a-10d
- **已验证蓝图的增量更新**：只跑 10b（晶体测试），与历史基线对比
- **跨宿主迁移**：在新宿主上重跑 10a-10c

---

## 教训日志

| # | 教训 | 来源 |
|---|------|------|
| L1 | spec_lock 必须覆盖所有可漂移参数 | v8 TOP_N 漂移 |
| L2 | delivery_gate 必须含业务合理性检查 | v5 pending_order bug |
| L3 | 禁止可选扩展阶段 | v8 股票池膨胀 |
| L4 | 代码模板给可执行示例不给伪代码 | v8 baostock 参数错误 |
| L5 | Host Adapter 白名单优先 | Gemini 评审 |
| L6 | 约束注入按阶段精选——v1 实测 104 条仅 35% 覆盖率，因果机制待验证（可能是结构问题而非数量问题） | v1 实测 |
| L7 | Crystal IR 与渲染分离 | 三方评审共识 |
| L8 | Failure Taxonomy 必须有具体 recovery action | v7 回退死路 |
| L9 | 宿主能力参数从 Host Spec 读取，禁止编撰 | v1.0 timeout/体积限制编撰 |
| L10 | 晶体知识是核心价值，Harness 不能替代知识 | v1.0 知识覆盖率 6% |
| L11 | "指令诅咒"0.95^N 未经实测验证，不作为第一性原理 | 事实核查 |
| L12 | 路径使用 `{workspace}` 占位符 | v1.0 硬编码路径 |
| L13 | 晶体必须能产出可复用 SKILL.md，不只是 seed.md | CEO 审查 |
| L14 | 知识压缩用四维筛选（新颖度×失败预防×阶段相关×操作化程度） | v1.2 四方评审 |
| L15 | 时效性管理：每个晶体必须有 version_pins + review_triggers | 四方评审一致：#1 优先级 |
| L16 | References 必须强制 read 而非"请阅读"——AI 会声称读了但实际编造 | Gemini/Sonnet 评审 |
| L17 | Stage 拓扑不硬编码——Pipeline/Iterative/Declarative 三种模式 | 四方评审一致 |
| L18 | Delivery Gate 双层化——Hard Gate（程序化）+ Soft Gate（LLM-as-Judge） | 四方评审一致 |
| L19 | Spec Lock 判断用领域无关元准则 (a)(b)(c)，不用金融参数列表 | Sonnet 评审 |
| L20 | 知识的 Actionability 决定它该内联还是放 references/——"需谨慎"≠"用复合键 ['id','updated_at']" | Sonnet 评审 |
| L21 | 晶体必须经过效能验证（A/B 对照）——覆盖率达标不等于有效，必须证明"有晶体比没有晶体好" | CEO 审查：v1.0 首测 6% 覆盖率仍通过 = 晶体可能没起作用 |
| **L22** | **State Semantics 是 Harness 四组件之一（Contracts/Stage/Failure/State），不是 IR 中的附属字段——状态外化为文件是 artifact-backed closure 的核心** | **三方评审共识 + Harness 研究报告 P0** |
| **L23** | **没有 trace 就没有可诊断性，没有 eval 就没有可迭代性——trace schema 必须在编译时声明，不是运行后补做** | **Harness 研究报告趋势 6 + Braintrust/Phoenix 实践** |
| **L24** | **长任务（Iterative 类型）必须 per-stage 渐进披露知识，一次性灌入全部知识会导致后期阶段知识被上下文压缩丢弃** | **Sonnet 独立发现 + progressive disclosure 原则** |
| **L25** | **每个 stage 必须有 checkpoint 语义——durable execution 不是高级选项，是中断可恢复的基础能力** | **Harness 研究报告趋势 3 + LangGraph 实践** |
| **L26** | **工具可调用 ≠ 工具可用——tool ergonomics（命名清晰度/重叠度/返回信号密度/token 成本）直接影响 agent 成功率** | **Anthropic "Writing effective tools for agents" + 研究报告趋势 5** |

---

*SOP v1.4 | 2026-04-07 | Doramagic CTO + CEO 联合制定*
*基于：v1.3 + Harness Engineering 研究报告对照审计 5 项架构补全*
*宿主规范：`docs/research/host-specs/openclaw-host-spec.md` + `docs/research/host-specs/claude-code-host-spec.md`*
