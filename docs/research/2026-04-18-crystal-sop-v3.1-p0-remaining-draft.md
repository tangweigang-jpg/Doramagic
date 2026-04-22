# Crystal SOP v3.1 — P0 剩余 3 项修订草案

> **元信息**（不进入 SOP 主体）
> - 目标文件：`sops/finance/crystal-compilation-sop.md`（当前 v3.1，本批次修订后仍为 v3.1 内的完善）
> - 编写日期：2026-04-18
> - 批次：P0 第二批（rationalization_guard / 双联约束 / 文档源处理）
> - 前置批次：`2026-04-18-crystal-sop-v3.1-step-revisions-draft.v2.md` 已应用
> - **编写约束**：所有"将进入 SOP 主体"的文本严格遵守 `sops/SOP_SPEC.md`——每句话属动作/条件/标准三类之一、不放溯源信息、自包含、清单用表格、模板用代码块

---

## 修订概览（共 9 处）

| # | 位置 | 性质 | 目标 P0 Gap |
|---|------|------|------------|
| R1 | Step 2b 之后新增 Step 2c | 新增段 | rationalization_guard |
| R2 | Step 6d 之后新增 Step 6e | 新增段 | 双联约束 |
| R3 | Step 6e 之后新增 Step 6f | 新增段 | 文档源 |
| R4 | Step 6.6b 权重表 | 替换一行 | rationalization_guard |
| R5 | Step 8a 段落结构 + 规则表 | 追加 1 行标题 + 1 行表格 | rationalization_guard |
| R6 | Step 8e 之后新增 Step 8f | 新增段 | rationalization_guard |
| R7 | Step 8f 之后新增 Step 8g | 新增段 | 文档源 |
| R8 | Step 8d 检查表 | 追加 3 行 | 三项 P0 都覆盖 |
| R9 | Step 9a D-check 表 | 追加 5 行（D27-D31） | 三项 P0 都覆盖 |

---

# R1：Step 2c 新增（插入到 Step 2b 之后）

## 插入位置

`crystal-compilation-sop.md` 中 `### 2b. 领域特定失败类派生` 段的内容之后、Step 3 的 `---` 分隔符之前。

## 新文本

````markdown
### 2c. Rationalization Guards 映射

**输入**：约束池中 `constraint_kind = rationalization_guard` 的条目。每条含 `guard_pattern.{excuse, rebuttal, red_flags, violation_detector}` 四字段。

**派生规则**：每条 rationalization_guard 约束派生 1 条 domain-specific failure class，补充到 Step 2b 的输出列表。

| failure class 字段 | 从 guard_pattern 派生 |
|------------------|---------------------|
| `name` | 基于 excuse 主题短语（如 `premature_completion_claim` / `skip_root_cause_investigation`）|
| `trigger` | red_flags 全部列出 + violation_detector 描述 |
| `recovery` | rebuttal 原文 |
| `prohibited` | "禁止以 excuse 为由" + excuse 原文 |

**派生示例格式**：

```yaml
- name: premature_completion_claim
  trigger:
    - "AI 声称任务完成但缺少验证步骤"
    - "未运行 validate.py 即声明完成"
  violation_detector: "未执行 enforce_validation 调用"
  recovery: "回到 Output Validator 步骤执行 enforce_validation"
  prohibited: "禁止以'测试冗余'或'显然正确'为由跳过验证"
```

**min_preset**：standard。scout 预设跳过本步骤。

**与 Step 2a 通用失败类的关系**：rationalization_guard 派生的 failure class 属于"防御层"，在 silent_drift / mode_switch / model_misuse 触发之前主动拦截；一条 guard 和一条通用失败类可指向同一行为，保留两者不去重。
````

---

# R2：Step 6e 新增（插入到 Step 6d 之后）

## 插入位置

`crystal-compilation-sop.md` 中 `### 6d. 非领域 worked example` 段之后、Step 6.5 `---` 之前。

## 新文本

````markdown
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
````

---

# R3：Step 6f 新增（插入到 Step 6e 之后）

## 插入位置

紧接 R2 之后。

## 新文本

````markdown
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
| `conflict: true` | 两路来源约束均渲染，段落标题加 `[CONFLICT]` 前缀，rationale 列出两路证据 |
| `conflict: false` 或字段缺失 | 正常渲染 |

**overclaim_risk 约束处理**：

| 字段值 | 处理 |
|--------|------|
| `overclaim_risk: true` | modality 降级一级（must → should、must_not → should_not）；rationale 注明原 modality |
| `overclaim_risk: false` 或字段缺失 | 保留原 modality |

**BD 合并规则**（混合项目的 code_observed + doc_declared）：

| 场景 | 合并规则 |
|------|---------|
| 代码与文档一致（`aligned`）| 合并为一条 BD；rationale 标注 "源自代码+文档一致验证" |
| 仅文档有（`doc_only`）| 保留；rationale 标注 "源自文档，未经代码验证"；severity 不升级 |
| 仅代码有（`code_only`）| 保留；rationale 标注 "源自代码，文档未记录" |
| 代码文档矛盾（`divergent`）| 两条均保留；两条 rationale 各自标注来源；`conflict: true` 标记 |
````

---

# R4：Step 6.6b 权重表替换一行

## 替换范围

`crystal-compilation-sop.md` 中 Step 6.6b Semantic Relevance Scoring 表中的 `Constraint kind transferability` 行。

## 原文（删除）

```markdown
| **Constraint kind transferability** | 0.20 | domain_rule=1.0, architecture_guardrail=0.9, resource_boundary=0.7, claim_boundary=0.6, operational_lesson=0.4 |
```

## 新文本（插入）

```markdown
| **Constraint kind transferability** | 0.20 | rationalization_guard=1.0, domain_rule=1.0, architecture_guardrail=0.9, resource_boundary=0.7, claim_boundary=0.6, operational_lesson=0.4 |
```

---

# R5：Step 8a 段落结构 + 规则表追加

## 替换范围 1（段落结构代码块）

原文：
```markdown
## Human Summary
## directive
## [FATAL] 约束
## Output Validator
## 架构蓝图
## 资源
## 约束
## 验收
```

新文本：
```markdown
## Human Summary
## directive
## [FATAL] 约束
## Rationalization Guards
## Output Validator
## 架构蓝图
## 资源
## 约束
## 验收
```

## 替换范围 2（各段落渲染规则表）

在 `[FATAL] 约束` 行之后、`Output Validator` 行之前插入：

```markdown
| Rationalization Guards | 每条 rationalization_guard 渲染为 RG-{N} 条目，含 excuse / rebuttal / red_flags / violation_detector / severity 五字段 | English | 约束池含 rationalization_guard |
```

---

# R6：Step 8f 新增（插入到 Step 8e 之后）

## 插入位置

`crystal-compilation-sop.md` 中 `#### 8e.4 渲染检查项` 表格之后、Step 9 之前。

## 新文本

````markdown
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
````

---

# R7：Step 8g 新增（插入到 Step 8f 之后）

## 插入位置

紧接 R6 之后。

## 新文本

````markdown
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

**evidence_role 与注入位置一致性**：渲染完成后，按 Step 6f 的 evidence_role 分流表逐条核对实际注入位置与应注入位置一致。
````

---

# R8：Step 8d 渲染后检查表追加三行

## 追加位置

`crystal-compilation-sop.md` 中 Step 8d 检查项表末尾（`| 文件头尾 | Powered by Doramagic.ai |` 之后）。

## 新文本（追加）

```markdown
| 双联约束成对 | 所有 claim_boundary 与对应 remedy 按 Step 6e 要求成对相邻渲染 |
| Rationalization Guards 段 | 约束池含 rationalization_guard 时 `## Rationalization Guards` 段存在且每条含 5 字段 |
| evidence_role 分流 | 文档源约束按 Step 6f 规则注入到 [FATAL]/架构蓝图/约束条目/Rationalization Guards 段 |
```

---

# R9：Step 9a D-check 表追加 D27-D31

## 追加位置

`crystal-compilation-sop.md` 中 Step 9a 表末尾（D26 行之后）。

## 新文本（追加）

```markdown
| D27 | Rationalization Guards 段 | 约束池含 rationalization_guard 时 `## Rationalization Guards` 段存在且每条含 excuse/rebuttal/red_flags/violation_detector/severity 五字段 | 补充渲染 |
| D28 | 双联约束成对 | 每个 claim_boundary（derived_from 含 business_decision_id）与同 bd_id 的 remedy 约束成对相邻渲染 | 重新聚合渲染 |
| D29 | evidence_role 分流 | 每条 `evidence_refs[].kind = document_section` 约束按 evidence_role 注入到 Step 6f 指定段落 | 重新分流注入 |
| D30 | conflict 标记 | 每条 `conflict: true` 约束在段落标题加 `[CONFLICT]` 前缀，rationale 列出两路证据 | 补充标记 |
| D31 | overclaim_risk 降级 | 每条 `overclaim_risk: true` 约束的 modality 相对原文档降级一级，rationale 注明原 modality | 补充降级 |
```

---

# SOP_SPEC 合规自查清单（元信息）

| # | 自检项 | 通过标准 |
|---|--------|---------|
| 1 | 铁律 1 合规 | 所有进入 SOP 主体的句子属于动作/条件/标准三类之一（含理由嵌入合法例外） |
| 2 | 铁律 2 合规 | 无 "v3.1 新增"、教训编号、评审溯源、历史案例引用 |
| 3 | 铁律 3 合规 | 跨段引用指向同一 SOP 内章节（Step 6e ↔ Step 8d/D28；Step 6f ↔ Step 8g/D29-D31；Step 2c ↔ Step 2b；Step 8f ↔ D27） |
| 4 | 无"新增"标签 | 各段标题不含 `[新增]`、`（新增）`、`[v3.1]` 等 |
| 5 | 清单格式 | 所有检查项/规则以表格呈现 |
| 6 | 模板格式 | 所有可复用文本以代码块包裹 |
| 7 | 代码块内无描述性注释 | YAML 示例 / Markdown 模板内只有指令与占位符 |
| 8 | 术语一致 | rationalization_guard / MG-{N} / RG-{N} / Boundary / Remedy / evidence_role / conflict / overclaim_risk / [CONFLICT] 前缀全文统一 |
