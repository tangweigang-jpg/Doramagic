# 约束采集 SOP（通用模板）

> **本文件是维护用模板，不直接执行。**
> 执行时请使用对应领域的完整 SOP（如 `finance/constraint-collection-sop.md`）。
>
> 模板版本：基于 SOP v2.3
> 用途：新增领域时，从本模板出发 + 注入领域知识 → 生成领域 SOP
>
> 模板注入点标记格式：`<!-- DOMAIN: 说明 -->`
> 编译新领域 SOP 时，将所有注入点替换为领域特定内容。

---

## 前提条件

- 蓝图已提取并通过四方评审（YAML 文件就绪）
- `constraint_schema` + `constraint_pipeline` 包已安装
- 目标项目可通过 git clone 获取

---

## 流程概览

蓝图提取 SOP 步骤 0 已探测知识源类型（代码/文档/混合）。约束采集复用该结果，按知识源类型选择提取策略。

```
Step 1: Clone 项目（复用蓝图提取已 clone 的仓库）
Step 2: 并行子代理提取
  2.1-2.3: 代码约束提取（per stage + edges/global/claims）— 代码知识源
  2.1-s:   文档约束提取（per SKILL.md/CLAUDE.md + resources）— 文档知识源
  2.4:     蓝图驱动的业务约束派生（所有知识源通用）
  2.5:     审计发现的约束转化（所有知识源通用）
  2.6:     rationalization_guard 专项提取 — 文档知识源独有
Step 3: 入库（JSON → Constraint → JSONL）
Step 4: 后处理修复（6 项规则）
Step 5: 质量验证（扫描 + 抽样评审）
```

预计耗时：纯代码蓝图 ~30 分钟（与此前一致）；含文档知识源的蓝图 ~45 分钟（+Step 2.1-s 和 2.6）

---

## Step 1: Clone 项目

```bash
mkdir -p repos
git clone --depth 1 https://github.com/{owner}/{repo}.git repos/{repo}
```

记录 commit hash，写入约束的 evidence_refs 中。

---

## Step 2: 并行子代理提取

### 2.1 按 stage 拆分任务

每个蓝图的 stages 拆为独立子代理任务。对于 4-5 个 stage 的蓝图：

- **子代理 A**：stage 1 + stage 2
- **子代理 B**：stage 3 + stage 4
- **子代理 C**：edges + global + claim_boundary 专项

或者每个 stage 独立一个子代理（更精细）。

### 2.2 子代理提示词模板（强化版）

**关键变更（L8）**：子代理必须使用管线 `prompts.py` 中的系统提示词模板。如果使用独立子代理，必须在 prompt 中显式列出以下枚举约束清单。

```
你是约束提取专家。请从 {项目名} 项目中为蓝图 {蓝图ID} 的 {stage_id} 阶段提取约束。

1. 先读蓝图文件了解该阶段的定义：
   {蓝图YAML路径}

2. 然后读源码中与该阶段相关的关键文件：
   {根据蓝图 evidence 字段列出的文件列表}

3. 按 5 种 constraint_kind 逐一扫描提取约束

4. 除按 constraint_kind 扫描外，还需关注以下横切维度（容易遗漏）：
   - 时间语义：as-of time、交易日历、时区处理
   - 数值精度：float vs Decimal、收敛条件
   - 前视偏差：shift/lag、训练/测试分割
   - 守恒约束：PnL 守恒、跨模块一致性

5. machine_checkable 判定标准（教训 L20）：

   标注 `true` 的条件（满足任一）：
   - 约束包含可 grep/regex 检查的具体值（参数名、阈值、常量）
   - 检查方式可描述为"读某字段/文件/配置，确认其值等于/不等于/包含 X"
   - M 类约束（数学模型参数）——几乎都可通过 grep 源码验证

   标注 `false` 的条件（满足任一）：
   - 约束依赖业务场景理解（"应避免过拟合"）
   - 验证需要运行代码并分析结果
   - BA 类风险提示，没有具体的值可检查

## 【强制】合法枚举值清单（不可发明新值）

modality（只能选以下 4 种）：
  must / must_not / should / should_not

constraint_kind（只能选以下 6 种）：
  domain_rule / resource_boundary / operational_lesson / architecture_guardrail / claim_boundary / rationalization_guard

consequence_kind（只能选以下 9 种）：
  bug / performance / financial_loss / data_corruption / service_disruption / operational_failure / compliance / safety / false_claim

severity（只能选以下 4 种）：
  fatal / high / medium / low

source_type（只能选以下 7 种）：
  code_analysis / document_extraction / community_issue / official_doc / api_changelog / cross_project / expert_reasoning

consensus（只能选以下 4 种）：
  universal / strong / mixed / contested

target_scope（只能选以下 3 种）：
  global / stage / edge

freshness（只能选以下 3 种）：
  stable / semi_stable / volatile

## 输出格式

JSON 数组，每条约束包含：
  when, modality, action, consequence_kind, consequence_description,
  constraint_kind, severity, confidence_score, source_type, consensus, freshness,
  target_scope, stage_ids, evidence_summary, machine_checkable, promote_to_acceptance

  validation_threshold（可选）: 当约束的 consequence 可量化时，标注异常判定阈值。
    格式："条件 → 判定"
    示例："abs(annual_return) > 500% → WARN"、"holding_change_pct > 100% → FAIL"
    仅当约束的 consequence_kind 属于 {financial_loss, data_corruption, bug} 且后果可量化时填写。
    不确定时不填。

## 关键规则

  - 每条约束只表达一个独立可验证的规则
  - evidence_summary 必须引用实际源码文件:行号
  - 禁止编造 — Unknown 就说 Unknown
  - action 禁止使用模糊词（考虑、注意、建议、适当、尽量）
  - when 必须用编码时视角（"编写/实现 X 时"），不用运行时视角（"X 被调用时"）
  - action 中用业务语义，不用源码常量
  - 【禁止】发明上述枚举清单之外的值
  - 不要自行编 ID，ID 由管线自动分配

## 【强制】consequence_description 质量要求（教训 L13）

  每条约束的 consequence_description 字段必须满足：
  - 字数 ≥20 字
  - 描述具体的失败现象
  - 禁止只填 consequence_kind 的值（"bug"、"performance" 等单词）
  - 禁止填写模糊表述（"结果不正确"、"程序出错"、"性能下降"）

## 【强制】提交前违规自检清单（教训 L14）

  生成 JSON 后，在提交前对每条约束逐一核对：
  □ modality 是否属于：must / must_not / should / should_not
  □ constraint_kind 是否属于：domain_rule / resource_boundary / operational_lesson / architecture_guardrail / claim_boundary / rationalization_guard
  □ consequence_kind 是否属于：bug / performance / financial_loss / data_corruption / service_disruption / operational_failure / compliance / safety / false_claim
  □ severity 是否属于：fatal / high / medium / low
  □ source_type 是否属于：code_analysis / document_extraction / community_issue / official_doc / api_changelog / cross_project / expert_reasoning
  □ consensus 是否属于：universal / strong / mixed / contested
  □ target_scope 是否属于：global / stage / edge
  □ freshness 是否属于：stable / semi_stable / volatile
  □ consequence_description 是否 ≥20 字且描述具体失败现象
  如有任何违规，在提交前自行修正，不要输出含违规条目的 JSON。
```

### 2.3 Claim Boundary 专项

claim_boundary 最容易遗漏，需要专项提取：

```
补充输入（不限于源码）：
- README 中的 disclaimer/limitation
- 蓝图的 applicability.not_suitable_for
- 领域常识

核心问题：
"如果用户基于此蓝图构建了系统，他可能对外宣称哪些能力？
 哪些宣称是危险的、不可支撑的、或违反行业惯例的？"
```

---

## Step 2.1-s: 文档约束提取（文档知识源）

**条件**：蓝图提取 SOP 步骤 0 探测到文档知识源时执行。纯代码蓝图跳过此步骤。

文档约束提取与代码约束提取的核心区别：代码约束从行为中**推断**隐含规则，文档约束从文本中**萃取**显式声明的边界。文档约束的风险不是遗漏（通常写得很显式），而是**过度声明**——作者写"always"可能实际是"usually"。

### 知识源范围

按蓝图 `resources` 字段中的 `technique_document` 类型展开扫描：

```
扫描优先级：
P0: 蓝图主源文件（SKILL.md）的约束性段落
P1: resources 中 type=technique_document 的子技术文档
P2: 项目级 CLAUDE.md / AGENTS.md 的全局规则
P3: hooks.json / settings.json 中的行为强制规则
```

### 子代理提示词模板

```
你是约束提取专家。请从文档知识源中为蓝图 {蓝图ID} 提取约束。

1. 先读蓝图文件了解整体结构：
   {蓝图YAML路径}

2. 读取以下文档知识源：
   {SKILL.md 路径}
   {resources 中 technique_document 的文件路径列表}
   {CLAUDE.md 路径（如有）}

3. 按以下文档特征模式扫描约束：

   | 文档特征 | 约束类型 | 典型信号 |
   |---------|---------|---------|
   | "NEVER/MUST/ALWAYS + 具体行为" | domain_rule 或 architecture_guardrail | 全大写强调词 + 祈使句 |
   | "Common Mistakes" / "Anti-patterns" 段落 | operational_lesson | 段落标题 + 列表 |
   | "Not suitable for" / "Limitations" | claim_boundary | 否定句式 |
   | 环境假设（"requires X"/"assumes Y"） | resource_boundary | 前提条件描述 |
   | 阶段间顺序强制（"Phase 1 before Phase 2"） | architecture_guardrail | 顺序/依赖描述 |

4. 对每条约束判断置信度：

   | 场景 | source_type | confidence_score |
   |------|-----------|-----------------|
   | 文档声明 + 代码中有对应实现（aligned） | code_analysis | 0.9 |
   | 文档显式声明，未验证代码（doc_only） | document_extraction | 0.6 |
   | 从多个文档段落推断 | expert_reasoning | 0.5 |

5. evidence 格式：
   - kind: document_section
   - path: 文件路径
   - section_id: "§段落标题"（如 "§The-Iron-Law", "§Phase-1-Step-4"）
   - evidence_role: normative / example / rationale / anti_pattern

{复用 Step 2.2 中的枚举值清单}
{复用 Step 2.2 中的质量要求}
{复用 Step 2.2 中的违规自检清单}
```

### 与代码约束的去重

文档约束和 Step 2.1-2.3 代码约束可能表达同一条规则。入库时：
- 语义等价且一致 → 合并为一条，两路 evidence 都保留，置信度提升至 0.9（corroboration boost — 两个独立来源互相印证）
- 文档更具体 → 保留文档版本，evidence 同时含代码引用
- 代码更具体 → 保留代码版本，evidence 同时含文档引用
- 矛盾 → 两条都保留，标注 `conflict: true`，置信度各自下调 0.1

### 过度声明检测（文档约束后处理）

对所有 `source_type=document_extraction` 且 `modality=must/must_not` 的约束执行反证扫描：

```bash
# 在代码中搜索例外/绕过
grep -rn "{约束关键行为的反面}" /tmp/{repo}/ --include='*.py' | grep -v test
```

| 扫描结果 | 处理 |
|---------|------|
| 未找到反例 | 保持原 modality |
| 找到 1+ 例外 | modality 降级为 should/should_not，标注 `overclaim_risk: true` |
| 例外出现在测试/mock 中 | 保持原 modality（测试绕过不算真实例外） |

---

## Step 2.6: Rationalization Guard 专项提取

**条件**：项目中存在反合理化内容时执行。以下任一命中即执行：
- 蓝图 `extraction_methods` 含文档知识源
- 项目含 SKILL.md / CLAUDE.md / AGENTS.md
- 项目含 CONTRIBUTING.md 且内含行为禁令
- 代码注释中有显式的"不要因为 X 就做 Y"模式（grep "DO NOT TOUCH\|DO NOT REMOVE\|DO NOT CHANGE"）

### 扫描来源

```
文档知识源：
P0: SKILL.md 的 "Common Rationalizations" / "Red Flags" 段落
P1: SKILL.md 的 "Human Partner Signals" / "Your X's Signals" 段落
P2: CREATION-LOG.md 的 "Bulletproofing Elements" 段落
P3: 任何使用 ❌/✅ 对比表的段落

代码知识源（补充扫描）：
P4: CONTRIBUTING.md 中的行为禁令
P5: 源码注释中的 "DO NOT TOUCH/REMOVE/CHANGE" 模式
```

### 子代理提示词模板

```
你是 AI 行为约束提取专家。请从文档中提取 rationalization_guard 约束。

这类约束对抗的是 AI agent 在执行 skill 时的自我合理化——agent 找到一个"看起来合理"的理由跳过关键步骤。

1. 读取文档：{SKILL.md 路径 + CREATION-LOG.md 路径（如有）}

2. 扫描以下模式：
   - "Common Rationalizations" / "Excuses" 表格 → 每个借口-反驳对 = 1 条约束
   - "Red Flags" 列表 → 每条红旗 = 1 条约束
   - "Human Partner Signals" → 每条信号 = 1 条约束
   - ❌/✅ 对比 → ❌ 行为 = 1 条约束

3. 约束格式：
   - constraint_kind: rationalization_guard（固定）
   - when: 描述 agent 可能出现该合理化的场景（如"调试时间紧迫且已花费较长时间"）
   - modality: must_not
   - action: 简洁的禁止声明（如"禁止以'问题太简单'为由跳过根因调查"）
   - consequence_kind: 根据跳步后果判断（如 bug、false_claim）
   - severity: 根据跳步破坏的内容判断 — 破坏 correctness/compliance = fatal，降低质量 = high，影响效率 = medium
   - source_type: document_extraction
   - evidence: kind=document_section, section_id="§Common-Rationalizations"
   - evidence_role: anti_pattern

   **额外必填字段 guard_pattern**（rationalization_guard 专有）：
   ```json
   "guard_pattern": {
     "excuse": "问题太简单，不需要走完整流程",
     "rebuttal": "简单问题也有根因。流程对简单 bug 很快。",
     "red_flags": ["Quick fix for now", "Just try changing X"],
     "violation_detector": "agent 提出修复方案但未完成 Phase 1 调查"
   }
   ```
   excuse = 借口原文，rebuttal = 反驳，red_flags = 表明正在违规的思维信号，violation_detector = 可检测的违规行为描述。

{复用 Step 2.2 中的枚举值清单}
```

### 预期产出量

<!-- DOMAIN: 按领域调整。非代码 skill 项目通常 5-15 条 rationalization_guard。纯代码项目 0 条。 -->

| 知识源 | 预估 rationalization_guard 数量 |
|--------|-------------------------------|
| 纯 skill 蓝图（如 superpowers） | 5-15 条 |
| 混合项目（如 deer-flow） | 2-5 条 |
| 纯代码蓝图 | 0 条（跳过此步骤） |

---

## Step 2.4: 蓝图驱动的业务约束派生

**前提**：蓝图已升级，包含 `business_decisions` 和 `known_use_cases` 字段。

**为什么需要**：Step 2.1-2.3 从源码提取的约束偏向技术架构。但蓝图升级后标注了业务决策（B/BA/DK/RC）和已知缺失（status: missing），这些需要对应的约束来告诉 AI "必须注意什么"和"不能忽略什么"。

### 2.4.1 派生来源与规则

从蓝图 `business_decisions` 中按 type 派生，每条派生约束必须包含溯源字段：

```json
"derived_from": {
  "blueprint_id": "{blueprint_id}",
  "business_decision_id": "{decision_id}",
  "derivation_version": "sop-v2.1"
}
```

**派生规则表**（基于四方评审共识）：

| 蓝图 type | 派生什么 | constraint_kind | 派生规则 |
|-----------|---------|-----------------|---------|
| **RC** | 外部强制规则约束 | `domain_rule` | 每条 RC 派生 1 条 must/must_not |
| **B** | 行为规则约束 | `domain_rule` | **选择性派生**：仅对"AI 高概率会改动且改了后果严重"的 B 派生 |
| **BA** | 风险提示约束 | `operational_lesson` | 满足以下三条件之一即派生：①会显著改变结果 ②AI 高概率默认继承 ③继承后结果失真而不自知 |
| **M** | 数学/模型选择约束 | `domain_rule`（精度影响）或 `architecture_guardrail`（架构影响） | 模型选择影响精度 → domain_rule；影响架构 → architecture_guardrail。modality: must/must_not，severity: high/fatal。M 类约束如有具体参数阈值，应标注 `validation_threshold` |
| **missing** | **双联约束**（boundary + remedy） | `claim_boundary` + `domain_rule` 或 `operational_lesson` | 每条 missing gap 派生 **2 条** |

**不派生的**：
- type=T 的纯技术选择
- type=DK 且不影响交付合法性/可执行性/数据解释
- type=M 的纯工具内部数学方法（如排序算法选择，不影响业务结果精度）

**关于 missing gap 双联约束**（教训 L16/L18）：

单独一条"禁止假设"只让 AI 变谨慎，不让 AI 变正确。必须配对 remedy。

```
✅ 生成 2 条：
  claim_boundary: "must_not 假设框架已处理{功能X}"
  domain_rule: "must 在{具体场景}时实现{具体处理方式，含字段名/阈值/代码操作}"
```

**remedy 约束的可执行性硬标准**：action 必须包含 AI 可直接执行的具体操作（数据字段、阈值、代码操作），禁止空话（"考虑/注意/关注"）。

**remedy 约束的原子性**：每条 remedy 只能包含一个独立的行动规则。

**RC 派生的 source_type 默认规则**：

| 蓝图 type | 默认 source_type | 理由 |
|-----------|-----------------|------|
| RC | `official_doc`（法规/外部规则）| 外部强制规则是事实，不是专家推理 |
| B | `code_analysis`（从源码行为推导）| 业务决策来自代码实现 |
| BA | `expert_reasoning`（对假设的风险判断）| 假设的风险是推理产物 |
| missing | `code_analysis`（确认源码中不存在）| 缺失是通过代码分析确认的 |
| M | `code_analysis`（从源码行为推导）| 数学模型选择来自代码实现 |

**关于 B 类选择性派生**：

过滤条件：
1. AI 在代码重构时是否高概率会改动这个行为？
2. 改了以后是否会导致严重后果？
3. 现有 Step 2.1-2.3 约束是否已覆盖？（已覆盖则不重复）

### 2.4.2 子代理提示词模板

```
你是约束派生专家。请从蓝图的 business_decisions 中派生业务约束。

1. 读取蓝图文件：{蓝图YAML路径}
2. 找到 business_decisions 段落
3. 按以下规则逐条派生约束：

## 派生规则

### RC（外部强制规则）→ domain_rule 约束
对每条 type=RC 的 business_decision：
- when: 用编码时视角描述触发场景
- modality: must 或 must_not（根据法规要求）
- action: 描述必须遵守的强制要求
- consequence_kind: compliance（违规）或 financial_loss（损失）
- severity: fatal（外部强制规则通常是 fatal）
- source_type: official_doc

<!-- DOMAIN: 此处注入领域 RC 派生示例（如量化金融：T+1 交割制度、印花税等）-->

### BA（业务假设）→ operational_lesson 约束
满足以下三条件之一即派生（不限于 known_issue 标注）：①会显著改变结果 ②AI 高概率默认继承 ③继承后结果失真而不自知。
- when: 用编码时视角描述使用该默认值的场景
- modality: should
- action: 提醒应调整或验证该默认值
- consequence_kind: 根据影响类型判断
- severity: medium 或 high
- source_type: expert_reasoning

<!-- DOMAIN: 此处注入领域 BA 派生示例-->

### missing gap → claim_boundary 约束
对每条 status=missing 的 business_decision：
- when: 用编码时视角描述触发场景
- modality: must_not
- action: 禁止假设框架已处理该功能
- consequence_kind: 根据 impact 字段判断
- severity: 继承蓝图标注的 severity
- source_type: code_analysis

<!-- DOMAIN: 此处注入领域 missing gap 派生示例-->

### M（数学/模型选择）→ domain_rule 或 architecture_guardrail 约束
对每条 type=M 或含 M 的复合类型（M/BA、M/B 等）的 business_decision：
- 模型选择影响**精度** → constraint_kind: domain_rule
- 模型选择影响**架构** → constraint_kind: architecture_guardrail
- modality: must 或 must_not（强制，不用 should）
- severity: high 或 fatal
- source_type: code_analysis

<!-- DOMAIN: 此处注入领域 M 类派生示例 -->

## 【强制】合法枚举值清单
{复用 Step 2.2 中的枚举值清单}

## 【强制】consequence_description 质量要求
{复用 Step 2.2 中的质量要求}

## 【强制】提交前违规自检清单
{复用 Step 2.2 中的自检清单}
```

### 2.4.3 预期产出量

<!-- DOMAIN: 此处填写领域典型产出量（RC/B/BA/missing 各多少条，预估派生约束总数）-->

| 蓝图 type | 典型条数 | 预估派生约束数 |
|-----------|---------|-------------|
| RC | {N} 条 | {N}-{N+2} 条 |
| B（选择性） | ~{N} 条符合过滤条件 | {N}-{N+2} 条 |
| BA（三条件过滤） | ~{N} 条符合条件 | {N}-{N+2} 条 |
| M（含数学模型的蓝图） | ~{N} 条 | {N}-{N+2} 条 |
| missing gap（双联） | {N} 条 | **{2N} 条** |

### 2.4.4 与 Step 2.1-2.3 的去重

派生的约束可能和现有约束重叠。入库时按以下规则去重：
- 用 `core.when` + `core.action` 的语义相似度判断
- 重叠时保留更具体、severity 更高的那条
- 标注 `relations: [{type: "supplements", target: "{constraint_id}"}]`

**例外**：RC 约束和 missing gap 约束即使语义重叠也**不去重**——它们表达不同层次：
- RC 约束（domain_rule）= 外部规则存在，告诉 AI 必须遵守
- missing 约束（claim_boundary）= 框架能力边界，告诉 AI 框架没实现它

两者必须共存，通过 `relations: [{type: "supplements"}]` 相互引用。

---

## Step 2.5: 审计发现的约束转化（教训 L21）

**前提**：蓝图提取 SOP 步骤 2c 的领域必审清单产出了审计发现（❌/⚠️/✅），部分已转入蓝图 `business_decisions`。本步骤将**未被 Step 2.4 覆盖的审计发现**直接转化为约束。

**触发条件**：蓝图 `audit_checklist_summary` 中存在 `fail > 0` 的清单项，且对应项未在 `business_decisions` 中标注。

### 转化规则

| 审计结论 | 约束类型 | modality | source_type |
|---------|---------|---------|-------------|
| ❌ 框架能力缺失 | `claim_boundary` | `must_not` | `code_analysis` |
| ❌ 实现有已知缺陷 | `operational_lesson` | `should` | `code_analysis` |

- 每条约束包含 `derived_from`，格式：`{source: "audit_checklist", item: "审计项名称", sop_version: "{版本}"}`
- severity 继承审计判定（Critical→fatal, High→high, Medium→medium）
- 仅转化 High/Critical 级别的 ❌ 发现

### 跨蓝图通用约束处理

<!-- DOMAIN: 此处注入跨蓝图通用约束的去重规则（如 T+1、时区处理等领域通用约束的识别和复用） -->

入库时检查全局约束池：
- 已存在语义等价的全局约束 → 在新蓝图的 `relations` 中引用，不重复入库
- 不存在 → 正常入库，设 `applies_to.target_scope = "global"`

---

## Step 3: 入库

### 3.1 从子代理输出提取 JSON

子代理返回的 JSON 数组嵌套在 agent output 中，需要解析提取。使用 `scripts/ingest_constraints.py`。

### 3.2 转换为 Constraint 对象

每条 raw JSON → `Constraint` Pydantic 模型：
- 自动分配 ID（`{domain}-C-{序号}`）
- 自动计算 hash（`sha256(core + scope)[:16]`）
- 设置 `version.status = "draft"`
- 设置 `blueprint_ids = [当前蓝图ID]`

**Draft 扁平 → Production 嵌套字段映射**：

| Draft 字段 | Production 位置 |
|-----------|---------------|
| `when` | `core.when` |
| `modality` | `core.modality` |
| `action` | `core.action` |
| `consequence_kind` + `consequence_description` | `core.consequence.kind` + `core.consequence.description` |
| `source_type` | `confidence.source_type` |
| `confidence_score` | `confidence.score` |
| `consensus` | `confidence.consensus` |
| `evidence_summary` | `confidence.evidence_refs[0].summary` |
| `target_scope` + `stage_ids` + `edge_ids` | `applies_to.*` |
| `derived_from` | 顶级字段保留 |

转换通过入库脚本自动完成。

### 3.3 Pydantic 模型验证（教训 L10）

**入库前必须通过 Pydantic `Constraint` 模型验证。** 验证失败的约束不入库，记录到 `_rejected.jsonl` 供人工修复。

```python
from doramagic_constraint_schema.types import Constraint

try:
    constraint = Constraint(**raw_json)
except ValidationError as e:
    log_rejection(raw_json, str(e))
    continue
```

### 3.4 业务校验

通过 `validate_constraint()` 校验：
- 三元组完整性（when/action/consequence 非空）
- 模糊词检测
- 原子性检测
- 证据要求（非 expert_reasoning 必须有 evidence_refs）
- applies_to 一致性（stage_ids/edge_ids 在蓝图中存在）

### 3.5 写入 JSONL

`knowledge/constraints/domains/{domain}.jsonl`

---

## Step 4: 后处理修复（6 项规则）

运行 `scripts/fix_constraints_review.py`（或手动检查）：

| 规则 | 检测条件 | 修复动作 |
|------|---------|---------|
| **P0a** | `source_type=expert_reasoning` 且 `score > 0.7` | 降为 0.7 |
| **P0b** | `constraint_kind=domain_rule` 且 `action` 含源码实现细节 | 改为 `architecture_guardrail` |
| **P1** | `when` 含运行时视角（"被调用时"、"is called"） | 改为编码时视角（"实现/编写 X 时"） |
| **P2** | `action` 含源码 API（`self.__xxx`、name mangling） | 用业务语义替代 |
| **P3** | `when` 纯英文（中文字符 < 10%） | 翻译为中文（技术术语保留英文） |
| **P4** | `consequence` 含"不可预期"等模糊词或 < 20 字，或值等于 consequence_kind 枚举词（教训 L13） | 补充具体失败现象 |
| **P5** | `action` 含硬编码常量（如 `row[XXX_IDX]`） | 用业务语义替代 |

---

## Step 5: 质量验证

### 5.1 自动化扫描

运行修复后验证脚本，确认 7 项指标全部归零。

### 5.2 抽样评审（可选，首次必做）

- 随机抽取 5 条约束
- 构建评审提示词
- 发送给 2-3 个外部模型独立评审
- 6 维度打分：正确性、原子性、可执行性、后果量化、证据质量、元数据准确性
- 目标：平均分 ≥ 4.5/5

### 5.3 kind 分布检查

确认 6 种 constraint_kind 的覆盖：
- `claim_boundary` ≥ 5%（最容易遗漏）
- `domain_rule` 和 `architecture_guardrail` 合计 ≥ 50%
- `rationalization_guard`：含文档知识源的蓝图 ≥ 1 条；纯代码蓝图允许 0 条

---

## 质量基线

| 指标 | 目标值 |
|------|--------|
| 约束总数 | 100-200 条/蓝图（Step 2.1-2.3 代码提取约 60-150 条 + Step 2.4 蓝图派生约 28-36 条 + Step 2.5 审计转化约 5-15 条）<!-- DOMAIN: 按领域典型蓝图规模调整 --> |
| 三方评审平均分 | ≥ 4.5/5 |
| P0-P5 后处理修复后残留 | 0 |
| claim_boundary 占比 | ≥ 5% |
| 每条约束有 evidence_refs | 100%（expert_reasoning 除外） |
| 所有约束 status=draft | 100%（人工审阅后改 active） |
| validation_threshold 覆盖率 | M 类 + severity=fatal 的约束中 ≥30% 有 validation_threshold |

---

## 经验教训（通用层 L1-L19）

| # | 教训 | 来源 |
|---|------|------|
| L1 | 不需要外部 LLM API——Claude Code 子代理本身就是 LLM | 首轮校准 |
| L2 | P0b（kind 误分类）最容易过度修正——只看 action，不看 evidence | 后处理 |
| L3 | claim_boundary 必须专项提取，否则占比趋近于零 | 四方研究共识 |
| L4 | when 必须用编码时视角，运行时视角会导致约束在 RAG 检索中失效 | 模型评审 |
| L5 | action 中用业务语义替代源码常量，否则约束不可移植 | 模型评审 |
| L6 | expert_reasoning 的 confidence 不超过 0.7 | 模型评审 |
| L7 | 子代理按 stage 并行提取效率最高，每个 stage ~5 分钟 | 首轮校准 |
| L8 | 子代理 prompt 必须使用管线 prompts.py 的模板，不能自行编写 prompt | 7 蓝图批量审计（35.7% 合规率根因） |
| L9 | 所有枚举值必须在 prompt 中显式列出合法值清单，不给 LLM 发明空间 | 7 蓝图批量审计（253 处非法枚举） |
| L10 | 入库前必须通过 Pydantic Constraint 模型验证，验证失败的不入库 | 7 蓝图批量审计 |
| L11 | ID 格式必须为 `{domain}-C-{三位数字}`，由管线自动分配 | 7 蓝图批量审计 |
| L12 | consensus 字段必须从合法值（universal/strong/mixed/contested）中选择 | 蓝图审计 |
| L13 | consequence_description 必须 ≥20 字，描述具体失败现象 | 批量提取审计 |
| L14 | 即使 prompt 列出合法枚举值，LLM 仍会发明新值，建议在 prompt 末尾增加"违规检查清单" | 批量提取审计 |
| L15 | 源码提取的约束偏向技术架构，领域特有规则几乎不会被 Step 2.1-2.3 捕获，必须从蓝图 business_decisions 专项派生 | 蓝图审视 |
| L16 | missing gap（蓝图中 status=missing 的已知缺陷）必须派生为 claim_boundary 约束 | 四方评审 |
| L17 | BA 派生条件：①会显著改变结果 ②AI 高概率继承 ③继承后失真不自知——满足任一即派生 | SOP v1.3 四方评审共识 |
| L18 | missing gap 必须派生双联约束（boundary + remedy） | SOP v1.3 四方评审 |
| L19 | B 类业务决策应选择性派生——AI 高概率会改动且改了后果严重的行为规则必须有约束保护 | 模型评审 |
| L20 | machine_checkable 标注需要明确判定标准——M 类参数约束几乎都可 grep 验证 | bp-009 验证 |
| L21 | 审计发现到约束的转化是蓝图 SOP 和约束 SOP 的接缝，必须有 Step 2.5 兜底 | bp-009 验证 |
| L22 | RC 约束和 missing gap 约束语义重叠时不去重，它们表达不同层次（规则存在 vs 框架未实现） | bp-009 验证 |
| L23 | BA 子代理 prompt 的过滤条件必须与派生规则表一致（三条件版本），否则约束偏少 | bp-009 验证 |
| L24 | M 类和 severity=fatal 约束应标注 validation_threshold，使产出数据质量可自动校验 | 四方评审共识 + bp-009 v1.8 实测 |
| L25 | 文档知识源的约束是显式声明（"NEVER do X"），但存在过度声明风险——作者写"always"可能实际是"usually"，需要置信度降级 | 非代码提取研究 2026-04-14 |
| L26 | `rationalization_guard` 是非代码项目独有的约束类型——对抗 LLM 自我合理化跳步，现有 5 种 kind 无法表达 | 非代码提取研究 2026-04-14 |
| L27 | 蓝图 resources 中的 technique_document 自身包含约束（如 defense-in-depth.md 的四层验证规则），必须作为额外约束来源扫描 | 非代码提取研究 2026-04-14 |
| L28 | 文档约束的 evidence 用 section 级引用（file:§section + evidence_role），必须区分 normative/example/rationale/anti_pattern 防止把示例误当规则 | 非代码提取研究 2026-04-14 |
| L29 | 文档声明的约束如果代码中有对应实现则置信度高（aligned），仅文档声明未实现则置信度降级（doc_only），两者矛盾则标记 divergent 交人工 | 蓝图 SOP v3.6 冲突矩阵 |

<!-- DOMAIN: 此处追加领域特有教训 -->

---

*通用模板 | 基于 SOP v2.3 提炼 | 编译领域 SOP 时参考此文件*
