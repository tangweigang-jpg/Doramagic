# CLAUDE.md 爆火对 Doramagic 的影响 — 完整研究报告

**日期**: 2026-04-21
**研究性质**: 深度战略研究 + 竞品横向扫描 + 外部验证
**输入来源**: 新智元文章摘要 + Grok 参考意见 + Agentic Engineering 竞品研究 + Doramagic 内部文档交叉验证
**产出**: 最完整 Doramagic 战略报告，可直接作为 v13.1+ 产品规划的输入

---

## 执行摘要

**一句话结论**：

> CLAUDE.md 的爆火不是提示词小技巧，而是 Agent Behavior Scaffolding 赛道正式成立的信号。Doramagic 的"知识锻造师"路线因此被外部市场验证，但护城河不在"做类似 CLAUDE.md 的事"，而在"把 CLAUDE.md 代表的脚手架能力，从通用工程层扩展到垂直领域、从手写规则升级为从真实项目中自动提取"。

**三维验证**：
- 市场验证：开发者愿为高质量 Agent 行为规则买单、传播、fork——证明需求真实
- 技术验证：OpenAI Agents SDK、Mastra、LangGraph、CrewAI 均把 guardrails/human-in-the-loop/structured outputs 作为一等公民——证明架构方向正确
- 竞品验证：Cursor Rules、Bugbot、Copilot 自定义指令均在同一方向投入——但无一家做"从真实项目提取领域级行为契约"——证明 Doramagic 差异化成立

---

## 一、CLAUDE.md 现象深度解析

### 1.1 现象还原

| 维度 | 事实 |
|------|------|
| 触发源 | Andrej Karpathy 2026-01-26 X 长帖，主题"AI 编程的真正瓶颈不是模型，是规则" |
| 蒸馏者 | Jiayuan Zhang，约 70 行 Markdown 文件 |
| 传播路径 | X → GitHub Trending 日榜连续 3 天第一，fork 数千次 |
| 核心格式 | 4 条行为规则 + 具体触发条件 + 违反后果 |
| 用户行为 | 复制到自己的 CLAUDE.md，直接注入 Claude Code 上下文 |

**为什么传播的是这个格式，不是更复杂的框架？**

关键在于"最小完整性"：
- 70 行：任何人都能在 5 分钟内读完并决定是否采纳
- 4 条：记忆负担极低，决策摩擦为零
- 触发条件具体：不是"要小心"，而是"当 X 发生时，做 Y，否则视为违反"
- 违反后果明确：不是"不好"，而是"Z 问题会出现"

### 1.2 四条规则的深度解构

```
规则一：编码前先思考
触发：当 AI 不确定用户意图时
行动：停下来问，列出选项让用户选择
违反后果：AI 脑补 → 用户拿到不需要的东西 → 信任损耗

规则二：简约至上
触发：当 AI 面临"可以多做一点"的机会时
行动：只实现用户明确要求的，不做推论性扩展
违反后果：过度工程化 → 代码库复杂性与用户需求不匹配

规则三：精确编辑
触发：当用户要求修改某处时
行动：只改指定位置，不顺手重构周围代码
违反后果：范围漂移 → 意外的回归 bug → 审查成本激增

规则四：目标驱动
触发：当复杂任务被下达时
行动：先给验收标准，再分步执行，每步验证
违反后果：半成品交付 → 用户介入修复 → AI 价值归零
```

这四条规则解决的不是"模型能力不足"，而是**模型在宽松约束下的行为选择问题**。这是理解 CLAUDE.md 爆火的核心。

### 1.3 Agent Behavior Scaffolding 的学术支撑

来自 OpenAI Agents SDK、LangGraph、Mastra 的研究一致指出 AI Agent 有以下失败模式：

| 失败模式 | 发生场景 | 传统解决方案 | Scaffolding 解决方案 |
|---------|---------|------------|-------------------|
| 幻觉式执行 | 缺少关键上下文时 | 模型自己推理 | 强制澄清门禁（Stop & Ask） |
| 范围漂移 | 收到模糊需求时 | 模型猜意图 | 精确边界约束（Exact Scope） |
| 过度工程化 | 模型"想做更好"时 | 依赖模型自律 | 最小化交付约束（Minimal Deliverable） |
| 半成品交付 | 流程跑完但结果不对 | 人工终检 | 验收门禁（Acceptance Gates） |
| 串位替换 | 用户目标难实现时 | 模型妥协 | 目标锁定（No Silent Substitution） |

CLAUDE.md 是这些规则的最小通用实现。Doramagic 的机会是把它们领域化、证据化、可自动化提取。

---

## 二、市场验证：竞品横向扫描

### 2.1 竞品全景图

| 产品 | 约束机制 | 是否从项目提取 | 领域化程度 | 与 Doramagic 关系 |
|------|---------|--------------|----------|-----------------|
| **Cursor Rules** | 手写 .cursorrules 文件 | 否 | 通用 | 同类项，Doramagic 更深 |
| **GitHub Copilot** | 自定义指令 + 企业策略 | 否 | 通用 | 维度不同（Copilot 是 IDE 插件） |
| **CopilotKit** | 共享状态层 + 工具约束 | 否 | 通用 | 基础设施，非内容 |
| **Mastra** | 工作流 human-in-the-loop checkpoint | 否 | 通用 | 架构参考，非竞品 |
| **LangGraph** | 状态可检性 + human-in-the-loop | 否 | 通用 | 架构参考 |
| **CrewAI** | Flow decorators（@start/@listen/@router）| 否 | 领域无关 | 编排层，非知识层 |
| **hermes-agent** | 自改进 agent + 自主 skill 创建 | 部分（从交互中提取）| 通用 | 最接近自演进，但无领域提取 |
| **learn-claude-code** | SKILL.md 动态加载 | 否 | 通用 | 理念相似，深度不如 |
| **Lamini** | Memory Tuning + Memory RAG | 是（训练数据层面）| 通用 | 技术路径不同（fine-tuning vs 规则编译）|

### 2.2 关键发现

**发现一：无竞品做"从真实项目提取领域级行为契约"**

Cursor Rules 是手写的；Copilot 指令是用户配置的；hermes-agent 是从交互中学习的。但没有任何产品做：
```
输入：一个优秀的开源项目（源码 + 文档 + issues + PR）
输出：该项目的种子晶体（蓝图 + 资源 + 约束 + 行为脚手架）
```

这是 Doramagic 的结构性空白。

**发现二：Guardrails 是 2026 年 AI 基础设施投资热点**

OpenAI、Mastra、LangGraph 均将 guardrails 作为一等公民投入。但这些 guardrails 是"通用防护栏"，不是"领域知识护栏"。Doramagic 的机会是将通用 guardrails 框架与领域特定约束结合。

**发现三：Slopacolypse 真实存在，但无人提供可信解**

业界应对 AI 低质内容的方案：
- Copilot：代码引用过滤器（禁止 65+ 词法单元的公共代码匹配）
- Anthropic：Constitutional Classifiers（对抗 universal jailbreak）
- Vellum AI："假设 AI 会对抗你"的安全设计哲学

这些方案都针对"模型层面"的质量问题。没有人做"知识制品层面"的质量保证——这正是 Doramagic 的机会。

---

## 三、Doramagic 现状 vs. CLAUDE.md 机遇

### 3.1 晶体现有能力的自评

基于产品宪法 v2 + SOP v5.3 + Schema v5.3，Doramagic 已有：

**强项（已覆盖 CLAUDE.md 需求）**：
- ✅ Blueprint（= 领域级架构模式，替代通用 CLAUDE.md 的工程准则）
- ✅ Constraints（= 有证据链的 fatal 边界，替代手写规则）
- ✅ Resources（= 晶体可执行所需的 API/工具/数据源）
- ✅ 8 条不变量（I1-I8）强制结构化契约
- ✅ Consumer Map（7 个消费者显式路由，解决字段作用域错位）
- ✅ Acceptance Gates（替代 CLAUDE.md 的"验收驱动"）

**弱项（CLAUDE.md 揭示的增量需求）**：
- ❌ 行为脚手架层（Agentic Behavior Scaffold）不在 Schema 显式字段中
- ❌ 四条通用规则（思考/简约/精确/目标驱动）未进任何 SOP
- ❌ Slopacolyside 反面命题未进产品叙事
- ❌ 晶体 Web 展示层未展示"防 Agent 坏习惯"能力

### 3.2 晶体公式升级路径

**当前公式**：
```
好的晶体 = 好的蓝图 + 好的资源 + 好的约束
```

**CLAUDE.md 视角揭示的缺口**：
公式缺少"行为契约的消费协议层"——即如何把蓝图/资源/约束转成宿主 AI 的行动规则。

**升级建议**：
```
好的晶体 = 好的蓝图 + 好的资源 + 好的约束 + 好的行为脚手架
```

"行为脚手架"不是第四类领域知识，而是晶体的**消费协议层**，它负责：
1. 任务前澄清规则（什么情况下必须停下来问用户）
2. 最小交付规则（未要求的不做，不做推论性扩展）
3. 精确修改规则（只改指定位置，不跨边界修改）
4. 验收循环规则（先给标准，再分步，每步验证）
5. 失败停止规则（出错时不得继续编造，必须停止）

---

## 四、战略影响：四路并进

### 4.1 产品叙事升级（立即生效）

**当前叙事**：
> Doramagic 把优秀开源项目里的专家知识，编译成种子晶体，交给用户的 AI 消费。

**升级后叙事**：
> Doramagic 不只是生成知识；Doramagic 生成让 AI 正确使用知识的行为契约。
> 当 AI 可以无限生成低质产物时，Doramagic 负责把"什么不能做、什么时候停、怎样才算通过"写进 AI 的工作方式里。

**三个版本**：

| 受众 | 表述 |
|------|------|
| 短版（社交媒体）| Doramagic 把优秀开源项目里的专家判断，锻造成宿主 AI 能直接继承的行为契约。 |
| 开发者版 | CLAUDE.md 证明通用工程规则能显著约束 Agent；Doramagic 则把这种规则生成能力扩展到垂直领域，从真实项目中提取，不是手写。 |
| 产品市场版 | 当 AI 可以无限生成低质产物时，Doramagic 负责把"什么不能做、什么时候停、怎样才算通过"写进 AI 的工作方式里。 |

### 4.2 SOP 层升级（P1）

晶体编译 SOP v5.3 需要新增一节：**Agentic Behavior Scaffold（行为脚手架）**。

建议在 `crystal-compilation-sop.md` 的"执行协议"之后、"质量门禁"之前插入：

```yaml
## §Agentic Behavior Scaffold（v5.4 新增）

每一颗晶体必须包含以下四个行为护栏，它们是晶体的消费协议层，
负责把蓝图/资源/约束转成宿主 AI 的具体行动规则。

### AB-1：澄清门禁（Think-Before-Action）
trigger: user_goal_ambiguous OR multiple_high_risk_interpretations
action: |
  STOP and ask user to clarify before taking any action.
  List the most likely interpretations and invite selection.
violation_code: AB-1-FAIL
note: "Do NOT proceed with the most likely interpretation."

### AB-2：最小交付门禁（Minimal-Deliverable）
trigger: opportunity_to_add_unrequested_features
action: |
  Do NOT add unrequested features.
  Do NOT create abstractions for single-use code.
  Do NOT add flexibility with no evidence of need.
violation_code: AB-2-FAIL
note: "Scope discipline is not a limitation; it is a respect for user time."

### AB-3：精确修改门禁（Precision-Edit）
trigger: user requests modification to specific location
action: |
  Only modify the specified location.
  Do NOT refactor surrounding code.
  Do NOT make related improvements.
violation_code: AB-3-FAIL
note: "Helpfulness should not become scope creep."

### AB-4：验收驱动门禁（Acceptance-First）
trigger: complex task assigned
action: |
  BEFORE execution: state acceptance criteria explicitly.
  DURING execution: verify each step against criteria.
  ON completion: report which gates passed.
violation_code: AB-4-FAIL
note: "Completion ≠ success; gate-passed ≠ success; actual criteria met = success."

### AB-5：失败停止门禁（Stop-on-Failure）
trigger: precondition fails OR evidence check fails OR gate fails
action: |
  STOP immediately.
  Report which gate/check failed and why.
  Do NOT continue fabricating to mask the failure.
violation_code: AB-5-FAIL
note: "A failing stop with clear evidence is more valuable than a false pass."
```

### 4.3 Schema 层升级（P2）

在 `crystal_contract.schema.yaml` 中新增顶级字段：

```yaml
agentic_behavior_scaffold:
  type: object
  required: [think_before_action, minimal_deliverable, precision_edit, acceptance_loop, stop_on_failure]
  properties:
    think_before_action:
      type: object
      properties:
        require_clarification_when:
          type: array
          items: { type: string }
          enum: [user_goal_ambiguous, multiple_high_risk_interpretations, required_resource_unknown, evidence_base_insufficient]
        stop_condition:
          type: string
          const: "MUST stop and ask"
    minimal_deliverable:
      type: object
      properties:
        forbids:
          type: array
          items: { type: string }
          default: [unrequested_features, speculative_abstractions, optional_paths_without_evidence]
    precision_edit:
      type: object
      properties:
        scope_lock:
          type: boolean
          const: true
        cross_boundary_ban:
          type: array
          items: { type: string }
          default: [surrounding_refactor, related_improvements, style_changes]
    acceptance_loop:
      type: object
      properties:
        criteria_first:
          type: boolean
          const: true
        step_verification:
          type: boolean
          const: true
        evidence_summary:
          type: boolean
          const: true
    stop_on_failure:
      type: object
      properties:
        fail_modes:
          type: array
          items: { type: string }
          default: [precondition_fail, evidence_check_fail, gate_fail]
        action:
          type: string
          const: "STOP and report clear failure evidence"
        no_continuation:
          type: boolean
          const: true
```

### 4.4 质量门禁层升级（P1）

在现有 SA（Structural Audit）基础上，新增 **Behavior SA（BSA）** 系列：

| 编号 | 检查项 | 失败后果 |
|------|-------|---------|
| BSA-01 | 晶体是否声明"什么时候必须停下来问用户" | 用户目标模糊时 AI 脑补 |
| BSA-02 | 晶体是否禁止未要求的功能扩展 | 过度工程化，交付膨胀 |
| BSA-03 | 晶体是否禁止静默目标替换 | AI 以假成果冒充成功 |
| BSA-04 | 晶体是否要求先给验收标准 | 流程跑完但结果无效 |
| BSA-05 | 晶体是否要求失败时停止 | AI 在失败后继续编造 |
| BSA-06 | 晶体是否有跨晶体隔离约束 | 污染其他 skill 的行为 |

---

## 五、四条规则到晶体的完整映射

### 5.1 "编码前先思考" → 晶体的 Context Acquisition 层

**CLAUDE.md 原文要求**：
- 不确定时停下来问
- 多解时列出选项让用户选
- 发现更优方案时主动建议

**Doramagic 晶体映射**：

当前晶体的 `context_acquisition` 字段已有意图收集，但没有显式的"模糊时停止"规则。

建议在晶体 Schema 的 `context_state_machine` 中为 CA（Context Acquisition）状态增加：

```yaml
context_state_machine:
  states:
    CA1_MEMORY_CHECKED:
      on_enter: [verify_project_context, check_preconditions]
      exits:
        - condition: "context_insufficient OR multiple_high_risk_interpretations"
          next_state: CA2_CLARIFICATION_REQUIRED
          action: "List options; ask user to select"
    CA2_CLARIFICATION_REQUIRED:
      enter_condition: "user must respond before proceeding"
      exits:
        - condition: "user_selected_one_option"
          next_state: CA3_CONTEXT_LOCKED
```

### 5.2 "简约至上" → 晶体的 Scope Minimality 指标

**CLAUDE.md 原文要求**：
- 未要求功能不写
- 只用一次的代码不抽象
- 不加没人要的灵活性

**Doramagic 晶体映射**：

建议在晶体编译 SOP 中新增质量指标：

| 指标 | 计算方式 | 通过标准 |
|------|---------|---------|
| Scope Minimality | `unrequested_features_added / total_features` | = 0 |
| Abstraction Justification | `abstractions_with_single_use_justification / total_abstractions` | ≤ 0.1 |
| Optional Path Ratio | `optional_paths_without_evidence / total_paths` | ≤ 0.2 |

### 5.3 "精确编辑" → 晶体的 Routing Isolation 约束

**CLAUDE.md 原文要求**：
- 只改用户要求的部分
- 严格匹配现有风格
- 无关问题只建议，不动手

**Doramagic 晶体映射**：

当前 Schema 的 `intent_router` 已有 `scope_containment`，但没有显式的"精确修改"规则。

建议在 `constraints[]` 中增加：

```yaml
- trigger: "user requests modification"
  action: "Only modify the explicitly specified location. Do NOT refactor adjacent code. Do NOT improve styling. Do NOT fix related issues."
  evidence_ref: "CLAUDE.md rule 3: Precision Edit"
  severity: fatal
  violation_code: PRECISION-EDIT-001
```

### 5.4 "目标驱动" → 晶体的 Acceptance Gates 强化

**CLAUDE.md 原文要求**：
- 不给步骤，给验收标准
- 复杂任务先列计划，每步带验证方式
- 让 AI 自己循环迭代，直到满足验收

**Doramagic 晶体映射**：

当前晶体的 `acceptance` 已有 `hard_gates` 和 `soft_gates`，但没有"验收标准必须先于执行声明"的结构性要求。

建议在 SOP 中强化：

> **Gating Rule**: `acceptance.hard_gates` 必须在 `execution_protocol.on_execute` 第一步声明，而不是在执行后验证。这是 CLAUDE.md "目标驱动"规则的结构化表达。

---

## 六、竞品差异化：为什么 Doramagic 不一样

### 6.1 关键区分

| 维度 | Cursor Rules / CLAUDE.md | Doramagic 晶体 |
|------|------------------------|--------------|
| **来源** | 专家手写 | 从真实项目自动提取 |
| **证据链** | 无结构化证据 | 每条约束有 `evidence_ref` 追溯 |
| **领域深度** | 通用工程准则 | 领域级、证据增强 |
| **规模** | 单文件复制 | 可批量提取、编译、发布 |
| **验收** | 人工判断 | 机器可检 `hard_gates` |
| **约束粒度** | 行为原则 | fatal constraints + acceptance gates |
| **可组合** | 手动合并 | SOP 驱动，可版本化 |
| **护城河** | 无（任何人都能 fork） | 从项目提取能力是结构性壁垒 |

### 6.2 Doramagic 真正的护城河

**护城河不在"做规则"，在"从真实项目提取规则的能力"**。

理由：
1. 任何人都能写 CLAUDE.md，但没有人能从 1000 个优秀的 GitHub 项目中系统提取领域行为契约
2. 从项目提取需要：源码理解能力 + 文档理解能力 + issues/PR 理解能力 + 约束形式化能力——这是 Doramagic 的核心资产
3. 提取的证据链（`evidence_ref`）让晶体比手写规则更可信——这是质量护城河
4. 批量提取 + 版本化让 Doramagic 能建立"晶体网络"——这是规模护城河

---

## 七、不建议做的事（红线）

| 红线 | 原因 |
|------|------|
| **不要把 Doramagic 重新包装成代码生成器** | 违背产品宪法 v2，会重新踩回权限/沙箱/部署的坑 |
| **不要只在全局 prompt 里加四条规则** | 全局 prompt 能改善一点行为，但无法形成差异化护城河 |
| **不要把 CLAUDE.md 当营销噱头直接照搬** | Doramagic 的价值是"从任意高质量项目中生成 CLAUDE.md 级行为契约"，不是"我们也有 CLAUDE.md" |
| **不要用 Slopacolypse 恐吓用户** | 更好的表达是正向承诺：Doramagic 交付可追溯、可约束、可验收的知识 |
| **不要废弃现有 Schema 的 I1-I8 不变量** | 8 条不变量是晶体的结构化保证，行为脚手架是增量不是替代 |

---

## 八、优先级路线图

### P0（立即，0-1 周）：叙事 + 展示

- [ ] 产品官网/文档引入"Agent 行为契约"概念
- [ ] 晶体 Web 展示页新增"这颗晶体防止哪些 Agent 坏习惯"标签
- [ ] 把 BSA-01~BSA-06 作为设计原则加入晶体评审流程

### P1（短期，1-4 周）：SOP + 门禁

- [ ] `crystal-compilation-sop.md` 新增 Agentic Behavior Scaffold 小节
- [ ] 编译脚本在 seed 中注入 AB-1~AB-5 行为护栏
- [ ] 质量门禁系统新增 BSA-01~BSA-06
- [ ] Schema 新增 `agentic_behavior_scaffold` 字段（P2 先做兼容性嵌入）

### P2（中期，1-2 月）：Schema 正式化

- [ ] `agentic_behavior_scaffold` 成为正式 Schema 字段
- [ ] 与 `consumer_map.yaml` 对齐（确认 AB 字段的消费者是 NR/SR/EX/VF 中的哪些）
- [ ] 给每条行为护栏标注主消费者

### P3（长期，2-4 月）：晶体市场升级

- [ ] Web 侧支持按"防脑补""防过度工程化""防范围漂移""强验收"筛选晶体
- [ ] 把通用 Agentic Rules 做成可复用行为模块
- [ ] 每个领域继承通用模块 + 叠加领域特异规则

---

## 九、最终判断

**CLAUDE.md 的爆火是 Doramagic 的强正面信号，原因有三：**

**1. 市场被教育**
开发者愿意为高质量 Agent 行为规则买单，证明需求是真实的，不是 Doramagic 自己发明的。

**2. 路线被验证**
Doramagic 的"知识锻造师"定位不只是在讲概念——外部市场已经意识到：模型不是全部，规则不是边角料，专家工作方式可以产品化。

**3. 差异化成立**
CLAUDE.md 是通用工程准则的最小实现。Doramagic 的机会不是"做一个更好的 CLAUDE.md"，而是"把 CLAUDE.md 的方法论，从手写的通用规则，升级为从真实项目中提取的领域级证据增强行为契约"。

这是两条完全不同的护城河：
- CLAUDE.md 的护城河：内容质量（任何人都能 fork）
- Doramagic 的护城河：提取能力 + 证据链 + 规模晶体网络

**正确吸收 CLAUDE.md 的方式**：
> 不是把四条规则塞进 Doramagic 的全局 prompt，而是把 CLAUDE.md 代表的"从专家经验中提取行为约束"的方法论，固化为 Doramagic 的核心编译能力，从通用工程层扩展到所有垂直领域。

---

## 附录：竞品关键来源

| 来源 | 关键洞察 |
|------|---------|
| [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) | 自改进 agent，106k stars，从交互中提取 skill |
| [learn-claude-code](https://github.com/shareAI-lab/learn-claude-code) | SKILL.md 动态加载，55.2k stars |
| [OpenAI Agents Python SDK](https://github.com/openai/openai-agents-python) | Guardrails 作为一等公民 |
| [Mastra AI](https://github.com/mastra-ai/mastra) | Human-in-the-loop checkpoint |
| [LangGraph](https://github.com/langchain-ai/langgraph) | 状态可检性 + human-in-the-loop |
| [CopilotKit](https://github.com/CopilotKit/CopilotKit) | Agent-UI 集成，共享状态层 |
| [Anthropic Research](https://www.anthropic.com/research) | Constitutional Classifiers 2026 |
| [Lamini AI](https://www.lamini.ai) | Memory Tuning 95%+ 准确率 |
