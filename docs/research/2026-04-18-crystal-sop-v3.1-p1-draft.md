# Crystal SOP v3.1 — P1 剩余 5 项修订草案

> **元信息**（不进入 SOP 主体）
> - 目标文件：`sops/finance/crystal-compilation-sop.md` + `sops/_template/crystal-compilation.tmpl.md`
> - 编写日期：2026-04-18
> - 批次：P1（consequence_kind / derived_from / resources L1-L3 / activation / false_claim）
> - `promote_to_acceptance` 已在第一批 R1 中硬连线（L352），本批不重复
> - **编写约束**：所有进入 SOP 主体的文本严格遵守 `sops/SOP_SPEC.md`

---

## 修订概览（共 11 处修订，覆盖 5 项 P1）

| # | 位置 | 性质 | 目标 P1 项 |
|---|------|------|------------|
| R1 | Step 6.6c 阈值表替换一行 | 替换 | consequence_kind 复合条件 |
| R2 | Step 6a 末尾追加 derived_from 聚合规则段 | 追加 | derived_from 利用 |
| R3 | Step 8 新增 8h 渲染溯源规则 | 新增 | derived_from 渲染 |
| R4 | Step 6 新增 6g 资源两层拆分 | 新增 | resources L1-L3 |
| R5 | Step 7 IR knowledge.resources 结构升级 | 替换 | resources L1-L3 |
| R6 | Step 8a 段落规则表"资源"行更新 | 替换 | resources L1-L3 |
| R7 | Step 6.5 新增 6.5f activation 对接 | 新增 | activation 对接 |
| R8 | Step 2a 通用失败类追加 false_completion_claim | 追加 | false_claim 失败类 |
| R9 | Step 9a D6 描述更新 | 替换 | false_claim 失败类 |
| R10 | Step 9a 追加 D32 derived_from 溯源检查 | 追加 | derived_from 渲染 |
| R11 | Step 9a 追加 D33 activation 覆盖检查 | 追加 | activation 对接 |

---

# R1：Step 6.6c 阈值表替换

## 替换范围

Step 6.6c Relevance Threshold 表中的第二行。

## 原文

```markdown
| 0.5 <= relevance_score < 0.7 | **Include only if** consequence.kind ∈ {financial_loss, safety, compliance, data_corruption, false_claim} |
```

## 新文本

```markdown
| 0.5 <= relevance_score < 0.7 | **Include if** severity = fatal OR consequence.kind ∈ {financial_loss, safety, compliance, data_corruption, false_claim} |
```

---

# R2：Step 6a 末尾追加 derived_from 聚合规则

## 插入位置

Step 6a 注入规则表之后、Step 6b 之前。

## 新文本

````markdown
**derived_from 聚合与溯源**：

| 字段 | 编译时使用 | 渲染时使用 |
|------|-----------|-----------|
| `derived_from.business_decision_id` | 按 bd_id 聚合同源约束；Step 6e 的双联约束识别键 | 约束条目下附 `> Derived from: BD-{bd_id}` |
| `derived_from.blueprint_id` | 跨蓝图约束追溯 | 仅跨项目约束附 `> Source blueprint: {blueprint_id}` |
| `derived_from.derivation_version` | 与蓝图 sop_version 交叉校验 | 不渲染到晶体 |

**聚合去重规则**：同一 `derived_from.business_decision_id` 下多条约束若 `core.when` + `core.action` 语义相似度 > 0.85 则合并，severity 取最高，rationale 合并为列表；Step 6e 的双联约束对不适用本规则。
````

---

# R3：Step 8 新增 8h 渲染溯源规则

## 插入位置

Step 8g 之后、Step 9 之前。

## 新文本

````markdown
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

**溯源与双联约束的关系**：Step 6e 渲染的 MG-{N} 格式已含 `> Source: missing_gap "{bd_id}"` 行，本规则对双联约束内的两条约束不重复渲染 `Derived from`。
````

---

# R4：Step 6 新增 6g 资源两层拆分

## 插入位置

Step 6f 之后、Step 6.5 之前。

## 新文本

````markdown
### 6g. 资源两层拆分

**输入**：蓝图 `resources[]` + `replaceable_points` + 宿主 Spec。

**拆分原则**：资源按"业务事实 vs 物理执行"切割：

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
````

---

# R5：Step 7 IR knowledge.resources 结构升级

## 替换范围

Step 7 Crystal IR 组装中 `knowledge.resources` 块。

## 原文

```yaml
  resources:
    external_services: [ API / 数据源 / 第三方服务 ]
    dependencies: [ 包依赖 ]
    infrastructure: [ 存储 / 计算 / 部署环境 ]
```

## 新文本

```yaml
  resources:                       # L1 业务事实（host-agnostic）
    packages: [ 包名 + 版本 + import alias ]
    data_sources: [ 数据源选择 + schema ]
    code_templates: [ 代码示例 + Strategy Scaffold 骨架 ]
    infrastructure_choices: [ 存储/计算/部署决策（选什么，不含怎么装）]
```

## 附带替换：host_adapters 段

## 原文

```yaml
  host_adapters: { ... }
```

## 新文本

```yaml
  host_adapters:                   # L3 物理适配（per-host）
    {host_name}:
      install_recipes: [ 安装命令模板 ]
      credential_injection: [ 凭证注入方式 ]
      path_resolution: [ {workspace} 与路径模板解析 ]
      file_io_tooling: [ 文件写入工具与使用模式 ]
      spec_ref: "docs/research/host-specs/{host}-host-spec.md"
      timeout_seconds: { 从 Host Spec 读取 }
      exec_rules:
        whitelist: [...]
```

---

# R6：Step 8a 段落规则表"资源"行替换

## 原文

```markdown
| 资源 | 依赖 + 数据源 + API 示例全量内联；含 Strategy Scaffold（业务骨架，含 REPLACE_WITH 占位符 + 末尾不可移除尾部调用 enforce_validation，详见 Step 8e） | English | 全部任务 |
```

## 新文本

```markdown
| 资源 | L1 主体：packages / data_sources / code_templates / infrastructure_choices / Strategy Scaffold；L3 子段 `### Host Adapter`：当前宿主的 install_recipes / credential_injection / path_resolution / file_io_tooling（详见 Step 6g / 8e）| English | 全部任务 |
```

---

# R7：Step 6.5 新增 6.5f activation 对接

## 插入位置

Step 6.5e context_state_machine 段之后、Step 6.6 之前。

## 新文本

````markdown
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
````

---

# R8：Step 2a 通用失败类追加 false_completion_claim

## 追加位置

Step 2a 通用失败类表末尾（原 7 条之后）。

## 新文本（追加一行）

```markdown
| `false_completion_claim` | AI 声明完成但未执行 Output Validator 调用链；或 result.csv 存在但无 validation_passed 标记文件 | 回到 Output Validator 阶段执行 enforce_validation，列出未通过的 Hard Gate | 不以"看起来对"或"显然完成"为由确认完成 |
```

---

# R9：Step 9a D6 描述更新

## 替换范围

Step 9a 表中 D6 行。

## 原文

```markdown
| D6 | Failure Taxonomy count | 7 universal (incl. model_misuse) + >= 2 domain-specific | Supplement |
```

## 新文本

```markdown
| D6 | Failure Taxonomy count | 8 universal (incl. model_misuse + false_completion_claim) + >= 2 domain-specific | Supplement |
```

---

# R10：Step 9a 追加 D32 derived_from 溯源检查

## 追加位置

Step 9a 表末尾（D31 之后）。

## 新文本

```markdown
| D32 | derived_from 溯源渲染 | 每条 `derived_from.business_decision_id` 非空的约束在条目末尾含 `> Derived from: BD-{bd_id}` 字面字符串；跨蓝图约束含 `> Source blueprint: {blueprint_id}` | 补充溯源 |
```

---

# R11：Step 9a 追加 D33 activation 覆盖检查

## 追加位置

D32 之后。

## 新文本

```markdown
| D33 | activation 覆盖 | 蓝图有 `applicability.activation.triggers[]` 字段时，intent_router 各用例的 positive_terms 并集必须包含 activation.triggers 全部条目 | 补充 positive_terms |
```

---

# SOP_SPEC 合规自查清单（元信息）

| # | 自检项 | 通过标准 |
|---|--------|---------|
| 1 | 铁律 1 合规 | 所有进入 SOP 主体的句子属于动作/条件/标准三类之一 |
| 2 | 铁律 2 合规 | 无 v3.1 版本标注、教训编号、评审溯源 |
| 3 | 铁律 3 合规 | 跨段引用指向同一 SOP 内章节（Step 6a ↔ 6e；Step 6g ↔ 8e；Step 6.5f ↔ 6.5d / 6.5e；D32/D33 ↔ 上游规则段）|
| 4 | 无"新增"标签 | 各段标题不含 `[新增]` / `（新增）` / `[v3.1]` |
| 5 | 清单格式 | 所有检查项/规则以表格呈现 |
| 6 | 模板格式 | 所有可复用文本以代码块包裹 |
| 7 | 代码块内无描述性注释 | YAML 示例的内联注释仅含字段语义标注（如 `# L1 业务事实`），不含陈述句 |
| 8 | 术语一致 | L1 知识层 / L3 宿主适配层 / Host Adapter 子段 / BD-{bd_id} / false_completion_claim 全文统一 |
