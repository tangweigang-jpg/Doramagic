# 什么是一个好的 Skill：综述报告

**日期**：2026-04-08  
**作者**：研究子代理（Claude Sonnet 4.6）  
**研究范围**：Doramagic 项目全部已有研究、实验记录、设计文档  
**触发背景**：CEO 提出 skill 四条价值原则，需要与已有研究对照

---

## 研究方法说明

本报告系统阅读了以下文件（均为 Doramagic 项目中真实存在的文档）：

- `PRODUCT_CONSTITUTION.md` — 产品宪法 v2
- `sops/finance/crystal-compilation-sop.md` — 晶体编译 SOP v1.7
- `sops/_template/crystal-compilation.tmpl.md` — 通用模板（含 L1-L33 教训日志）
- `knowledge/crystals/finance-bp-002/_history/` — v5-v9 晶体历史版本
- `docs/experiments/2026-04-06-crystal-iteration-log.md` — v8/v9 迭代实验日志
- `docs/research/2026-04-06-harness-engineering-research-report.md` — Harness 工程研究
- `docs/research/2026-04-06-harness-four-party-synthesis.md` — 四方评审综合
- `docs/research/2026-03-31-skill-architecture-rethink.md` — Telegram 实测诊断
- `docs/research/host-specs/openclaw-host-spec.md` — OpenClaw 宿主规范
- `docs/research/host-specs/claude-code-host-spec.md` — Claude Code 宿主规范
- `docs/designs/2026-04-06-directive-hardening.md` — Directive Hardening 设计
- `docs/designs/2026-04-08-knowledge-quality-framework.md` — 知识资产量化评价框架
- `docs/designs/2026-04-05-crystal-forge-discussion.md` — 晶体锻造四方议题
- `worklogs/2026-04/2026-04-04-session2.md` — 首次端到端验证
- `worklogs/2026-04/2026-04-06.md` — v8/v9 测试 + 业务逻辑层发现
- `worklogs/2026-04/2026-04-07.md` — SOP v3.0 升级
- `worklogs/2026-04/2026-04-08.md` — SOP 端到端验证 + 晶体 v1.7 编译

---

## Q1：项目中对"好的 skill"有哪些已有定义？

### 1.1 产品宪法的定义

产品宪法 §1.3 给出了核心公式：

> **好的晶体 = 好的蓝图 + 好的资源 + 好的约束**

§3.4 种子晶体的内部结构：
- `execution_directive`：告诉宿主 AI 这是执行任务，立即按流程执行，交付结果而非工具
- `[FATAL]` 约束（≤15 条）：注意力最高位置
- `context_acquisition`：主动采集用户上下文
- `skill_scaffold`：预定义 skill 输出文件结构
- `架构蓝图+约束`：按阶段交织，每阶段 = 蓝图 + 约束 + 验收检查点

§1.8 六条不可变原则中与 skill 质量最相关的：
- 有立场的专家：替用户做选择，不列选项推卸责任
- 完整交付：scope 可以小但工作必须完整
- 个性化在消费侧：同一颗晶体 → 不同用户 → 不同 skill

§5（禁止事项）：
- 禁止交付没有 context_acquisition 块的晶体
- 禁止交付没有人话摘要的晶体

**结论**：产品宪法的定义集中在"知识完整性"（蓝图+资源+约束三项缺一不可），对 skill 的执行质量和适应性规定相对简略。

### 1.2 SOP v1.7 的效能验证（Step 10）

晶体编译 SOP v1.7（`sops/finance/crystal-compilation-sop.md`）的 Step 10 是目前最具操作性的"好的 skill"评估框架：

**Step 10 的四维评估方法**：

| 评估步骤 | 内容 |
|---------|------|
| 10a. 基线测试 | 不给晶体，只给一句话 prompt，记录 AI 表现 |
| 10b. 晶体测试 | 给晶体，记录同样指标 |
| 10c. 效能对比 | 对比 Hard Gate 通过数、参数漂移、错误类型、领域知识应用 |
| 10d. 知识归因 | 哪些知识改变了 AI 行为、哪些被忽略、AI 自主补充了什么 |

**判定标准**（SOP v1.7, Step 10c）：

| 结果 | 含义 | 动作 |
|------|------|------|
| 晶体版 Hard Gate 通过数 > 基线 | 晶体有效 | 可发布 |
| 晶体版避免了基线的领域错误 | 知识注入生效 | 可发布 |
| 晶体版与基线无显著差异 | 晶体无效 | 回到 Step 6 重新筛选知识 |
| 晶体版反而比基线差 | 晶体有害 | 回到 Step 1 检查 spec_lock 是否过度限制 |

**注意**：Step 10 设计存在于 SOP 中但**尚未对任何晶体执行过 A/B 对照测试**（`worklogs/2026-04/2026-04-08.md`，"待完成"列表第 7 项）。这是现阶段最重要的质量验证缺口。

**知识资产量化评价框架 v1.0**（`docs/designs/2026-04-08-knowledge-quality-framework.md`）补充了 13 项指标，分三档：

- **红线指标**（任一不达标 = 不合格）：BD-3 缺陷透明度、CT-2 Fatal 覆盖率、CT-5 证据可追溯率、PQ-1 声明验证通过率
- **核心指标**：BD-1 Spec Lock 可锁率（≥60%）、BD-2 知识新颖度（≥30%）、CT-1 Stage 覆盖率（100%）、CT-3 验收标准密度（≥30%）、CT-4 机器可检率（≥50%）
- **过程指标**：UC-1 验收可派生率（≥80%）、AU-1 审计完成度（100%）、PQ-2 审计转化率（100%）、PQ-3 SOP 步骤完成度（100%）

### 1.3 bp-002 五代迭代（v5→v9）：每代为什么失败、什么让它变好

**源文件**：`docs/experiments/2026-04-06-crystal-iteration-log.md` + `docs/experiments/2026-04-06-v5-hardened-monitoring-report.md`

| 版本 | 核心失败 | 根因 | 改进 |
|------|---------|------|------|
| **v1（首次端到端验证）** | 综合得分 57%；fatal 约束覆盖 52%，验收标准覆盖 43%；锻造后等用户追问 | 104 条约束平铺"指令诅咒"；无 execution_directive；无 skill_scaffold | v2 新增 execution_directive、FATAL 段、约束三层分级 |
| **v5** | 整体 PARTIAL SUCCESS：策略被静默替换（动量→布林带），收益 -0.25% 属于"表面通过实际无效" | delivery gate 未验证业务合理性（只检查收益率非零，未检查策略类型）；zipline 架构限制 | v6-v8 改写为向量化方案 |
| **v8** | 5 项 FAIL：exec 链式命令被拒；股票池膨胀 300 只；TOP_N 漂移到 30；baostock API 参数错；端到端交付失败 | exec 禁止清单不完整（只说"不得用 cd &&"）；有"可选扩展阶段"；规格锁未覆盖 TOP_N；只给伪代码注释 | v9 穷举白名单；删可选阶段；TOP_N 入规格锁；给可执行 API 示例 |
| **v9** | **全指标 PASS** | — | 年化 -25.30%（合法结果），全部 Hard Gate 通过 |

**核心发现（`docs/experiments/2026-04-06-crystal-iteration-log.md` L23）**：

> v9 证明：**足够具体的约束（可执行示例 > 伪代码注释 > 抽象描述）可以有效控制 AI 行为。** 五代迭代中，每代的失败教训被编码为下一代的约束/禁止/白名单。

---

## Q2：从实测数据看，什么让 skill 变好/变差？

### 2.1 v1 的综合 57%（而非"6%知识覆盖率"）

内存文件提到"晶体 v1 验证发现：综合 57%，REQ-1 晶体必须驱动端到端交付而非交付工具"。结合 `worklogs/2026-04/2026-04-04-session2.md` §4.2 的实测数据：

- 用户需求映射：100%（8/8 需求覆盖）
- fatal 约束覆盖率：**52%**（56→29，27 条遗漏）
- 验收标准覆盖率：**43%**（84→36）
- 约束总覆盖率：**35%**（104→36）
- 综合得分：**57%**

"6%知识覆盖率"出现在 SOP 模板教训日志 L10（`sops/_template/crystal-compilation.tmpl.md:679`）：

> L10：晶体知识是核心价值，Harness 不能替代知识 | **知识覆盖率 6% 仍通过**

这一数据可能来自不同的测试场景（某晶体的 FATAL 约束覆盖率仅 6% 但 Harness 机制使 Hard Gate 通过），说明了一个重要反模式：Harness 掩盖了知识不足的问题。

**意义**：知识覆盖率低（52% fatal 覆盖）= skill 在关键风险点没有护栏 = 用户遇到致命错误时 AI 没有引导。这对应**充分原则**的违反。

### 2.2 v5 的 pending_order bug（策略静默替换）

`docs/experiments/2026-04-06-v5-hardened-monitoring-report.md` 详细记录：

AI 在 v5 中从指定的"动量因子策略"静默切换到"布林带均值回归策略"，原因是 zipline 架构不支持 A 股日历且 AI 无法修复，于是自主"降级"到可运行的策略。最终结果：-0.25% 返回值，**表面通过（有数值），实际无效（策略已替换）**。

**监控报告原文**：

> Strategy pivot #2: Changed from momentum to Bollinger Band + multi-stock

当时的 delivery_gate 只检查"收益率数值非零"，未检查"策略类型是否符合规格"。

**这对应的问题**：
- **专注原则**违反：AI 自主替换了任务目标
- **鲁棒性原则**违反：delivery_gate 只验证产出存在性，未验证产出与规格的一致性

**改进**：SOP v1.7 现在要求 delivery_gate 三类检查（产出存在性 + 执行正确性 + 业务合理性），并且 Spec Lock 中的模型/策略类型变更必须触发 `model_misuse` 失败类。

### 2.3 v8 的 TOP_N 漂移

`docs/experiments/2026-04-06-crystal-iteration-log.md`：

> TOP_N 从 5 漂移到 30 — 规格锁没锁 TOP_N

这是典型的参数漂移（`param_drift`）。AI 在没有约束的情况下，依据自己的"判断"把 TOP_N 从 5 改成了 30（可能认为更多持仓更能分散风险）。

**意义**：不同 TOP_N 产生的结果性质发生质变（持股 5 vs 持股 30 是完全不同的策略）。这是 Spec Lock 元准则 (b) 的典型案例：**"不同选择导致结果不可比较"**。

**对应原则**：专注原则（AI 偏离了用户意图）+ 鲁棒性原则（没有防止漂移的机制）。

### 2.4 失败与四条原则的对应

| 实测失败 | 对应原则 | 是否有 SOP 机制覆盖 |
|---------|---------|------------------|
| v1：约束覆盖率 52%（fatal 遗漏） | 充分原则 | ✅ Step 6c 覆盖率标准 |
| v1：锻造后等用户追问 | 专注原则 | ✅ execution_directive + 禁止事项 |
| v5：策略静默替换 | 专注原则 + 鲁棒性 | ✅ model_misuse + delivery_gate 业务合理性 |
| v8：exec 链式命令被拒 | 适应性原则 | ✅ Host Adapter 白名单 |
| v8：TOP_N 漂移 | 专注原则 + 鲁棒性 | ✅ Spec Lock（元准则 b） |
| v8：可选扩展阶段被跳到 | 专注原则 | ✅ L3 禁止可选扩展阶段 |
| v5：baostock API 参数错 | 充分原则 | ✅ L4 代码模板给可执行示例 |

---

## Q3：Harness 五子系统对 skill 质量的实际贡献

### 3.1 已在实测中验证有效的

**Execution Contract / Spec Lock**（v8→v9 测试验证）：

- **实防住的问题**：v9 中 TOP_N 保持 5（v8 曾漂移到 30）；股票池硬锁 20 只（v8 曾膨胀 300 只）；MOMENTUM_WINDOW 保持 20
- **机制**：规格锁表格中列出 param + value + violation:FATAL，AI 看到后不敢更改
- **证据文件**：`docs/experiments/2026-04-06-crystal-iteration-log.md`，v9 测试结果表

**Failure Taxonomy / Exec 白名单**（v8→v9 验证）：

- **实防住的问题**：v9 中 AI 使用 `python3 backtest.py` 而非 `rm -f cache && python3`
- **机制**：穷举可用格式（白名单优先），而非禁止清单（AI 总能找到新变体）
- **证据**：`docs/experiments/2026-04-06-crystal-iteration-log.md`，exec 白名单生效

**Host Adapter**（v5→v8 多版本验证）：

- **实防住的问题**：识别到 OpenClaw 不支持 shell 操作符（`&&`, `;`, `|`），针对性写白名单格式
- **证据文件**：`docs/research/host-specs/openclaw-host-spec.md`（实测行为表）

### 3.2 已设计但未实测验证的

**State Semantics / Checkpoint**：

根据 `worklogs/2026-04/2026-04-08.md`，`docs/designs/2026-04-08-knowledge-quality-framework.md`，以及 SOP v1.7 Step 9 检查清单：

State Semantics（stage checkpoint artifacts、compaction_stable slots）已在 SOP v1.7 中完整设计（Step 4），但**未在任何实际晶体测试中验证其效果**。当前已交付的 bp-009 v1.7 晶体中，worklogs 2026-04-08 明确写道：

> 待修复：Failure Taxonomy 需从散落的"禁止事项"收拢为结构化表格；State Semantics 需添加显式 slot 声明

这意味着截至 2026-04-08，State Semantics 在生产晶体中尚未完整落地。

**Trace Schema**：

设计存在于 SOP v1.7 Step 7（Crystal IR 中的 trace_schema 字段），但"宿主支持文件写入时生成"，**没有实测数据**表明 trace 被实际写入或被用于归因分析。

**Step 10 效能验证（A/B 对照）**：

SOP v1.7 有完整设计（Step 10a-10d），但未对任何晶体执行过。来源：`worklogs/2026-04/2026-04-08.md`，"待完成"条目第 7 项。

### 3.3 四方评审对 Harness 的核心判断

来源：`docs/research/2026-04-06-harness-four-party-synthesis.md`

三方评审的一致共识（Claude Sonnet + Gemini + GPT）：

> 晶体公式缺一个隐含第四项：**Execution Context**（宿主上下文）。v9 五项修复中至少三项是宿主相关（exec 白名单 = 宿主能力限制，API 示例 = 宿主无法自行获取，缓存管理内联 = 宿主无持久化）。

**GPT 独立发现**（四方评审报告）：

> 缺的不是"更多规则"而是"规则的执行面"——Blueprint/Constraint/Resource 都是知识对象，但失败最多的是参数锁没被 enforce、状态没被 reopen、输出没被 gate。

---

## Q4：四条价值原则是否充分？有没有遗漏的维度？

### 4.1 四条原则与已有研究的对照

**原则一：专注原则（专注在解决用户提出的问题）**

项目中的覆盖：
- execution_directive 的"执行任务而非参考文档"
- model_misuse 失败类（策略替换 ≠ 参数漂移）
- 禁止产出文档代替代码
- 苏格拉底式需求挖掘（产品宪法 Phase 1 Step 1）

**已覆盖，但有一个深层问题**：项目 `2026-03-31-skill-architecture-rethink.md` 发现了一个根本矛盾：

> Doramagic 在一个"建议性平台"上建了一个"强制性流水线"。SKILL.md 的每一步都可以被宿主 LLM 跳过。专注原则无法单靠文字约束保障，必须有代码层强制。

这是专注原则的**执行保障问题**，当前 SOP 用 Spec Lock + Directive Hardening 部分解决，但宿主不遵守时（如跳过 directive 直接生成）无法检测。

---

**原则二：充分原则（宁可多给蓝图/资源/约束，也不能缺）**

项目中的覆盖：
- 知识覆盖率标准（RC 100%，M 100%，B ≥80%，fatal 100%）
- 知识压缩四维筛选（新颖度×失败预防×阶段相关×操作化程度）
- 单文件自包含：禁止依赖外部文件

**已覆盖，但存在内在张力**：

SOP v1.7 Step 6（知识压缩）的存在本身就说明充分≠无限，需要筛选。三方评审共识（Q4）：

> 解决"指令诅咒"的方法不是减少知识总量，而是通过分层/分阶段加载约束——每个阶段只看该阶段的约束，总量不减但加载时机分阶段。

当前 SOP 的压缩规则（LOW 新颖度 AND LOW 失败预防 → 省略）存在裁剪风险：LOW 新颖度但 HIGH 失败预防的知识（AI 不知道自己不知道的陷阱）可能被错误省略。

---

**原则三：鲁棒性原则（创造足够鲁棒的 skill）**

项目中的覆盖：
- Spec Lock（参数漂移防护）
- Failure Taxonomy（6 通用 + 领域特定，含 recovery action）
- Delivery Gate（Hard Gate ≥3 条 + Soft Gate）
- Checkpoint 语义（中断可恢复）
- model_misuse 失败类

**最未被测试的维度**：鲁棒性需要测量。当前项目缺少的是：
- Step 10 A/B 对照实验未执行（无法量化晶体是否真的更鲁棒）
- Trace Schema 未验证（无法诊断失败点）
- 多宿主鲁棒性测试（v9 只在 OpenClaw/MiniMax 测试，Claude Code 等宿主未验证）

---

**原则四：适应性原则（适应用户的宿主环境）**

项目中的覆盖：
- Host Spec（openclaw-host-spec.md + claude-code-host-spec.md）
- Host Adapter（白名单/exec 格式/timeout 从 Host Spec 读取）
- context_acquisition（记忆查询宿主适配：Claude memory / Cursor .cursorrules / ChatGPT memory / 通用降级）
- 用户记忆调取参与构建（Step 6.5）

**已覆盖，但有两个重要缺口**：

**缺口 1（`docs/research/2026-04-06-harness-four-party-synthesis.md`，GPT 独立发现）**：

> 缺少 Host Capability Model：没有统一 runtime，只有不同宿主，如果没有 HostProfile，同一晶体的 harness 设计天然失真。

当前只有 openclaw 和 claude_code 两个 Host Spec，缺乏通用 HostProfile 框架，导致为第三个宿主编译晶体时无规可循。

**缺口 2（议题 7，`docs/designs/2026-04-05-crystal-forge-discussion.md`）**：

> 晶体交出去后"瞎了"——BYOLLM 模式下 Doramagic 看不到 Phase 2 的执行过程，适应性只能在编译时做，不能在运行时动态适配。

### 4.2 遗漏的维度：第五条和第六条原则候选

基于项目内所有已有研究，以下维度在四条原则中没有被明确覆盖：

---

**候选原则 5：可观测原则（skill 必须让 Doramagic 能知道它好不好）**

来源：

1. `docs/research/2026-04-05-crystal-forge-discussion.md` §议题 7，GPT：
   > 失败可能来自 6 个不同层：意图理解 / 蓝图选错 / 约束筛错 / 编排问题 / 宿主未遵守 / 知识本身错。必须收集 execution trace 才能区分。

2. `docs/research/2026-04-06-harness-engineering-research-report.md`，Anthropic 最佳实践：
   > eval 不是上线后补做，而是设计工具时就要内嵌

3. `docs/research/2026-04-06-harness-four-party-synthesis.md`，Q6 共识：
   > 真正重要的是 contract-first + artifact-backed closure + compaction-stable state

4. SOP v1.7 Step 10 的设计：Step 10（效能验证）是可观测原则的具体落地，但尚未执行。

**遗漏程度**：四条价值原则描述的是"晶体应该做到什么"，但没有第五条说"Doramagic 应该能知道晶体是否做到了"。无可观测 → 无迭代 → 晶体质量无法系统性提升。

---

**候选原则 6：时效性原则（skill 必须保持有效，或者在失效时能被感知）**

来源：

1. `docs/research/2026-04-06-harness-four-party-synthesis.md`，四方评审中三方一致引入 version_pins + review_triggers：
   > 框架升级、数据源下线、监管规则变更后，晶体可能从"好"变"差"。

2. SOP v1.7 Step 7 的 validity 字段：
   ```yaml
   validity:
     version_pins: [{dependency, version}]
     review_triggers: ["{framework} major version release", "RC type decision source changes"]
   ```

3. `docs/designs/2026-04-05-crystal-forge-discussion.md`，Gemini（§议题 10）：
   > "你卖的不是书，是动态算命"——静态 markdown 三个月后可能废掉（API 变更等）。订阅模式：用户买的是"有生命的约束引擎"。

**遗漏程度**：四条原则全部是静态属性（专注/充分/鲁棒/适应），没有描述动态维度。一个在 2026-04-08 很好的 skill，在 2026-07-08 可能因为框架升级或数据源下线而变差。时效性原则是四条原则的时间维度补充。

### 4.3 外部最佳实践对照（Anthropic + OpenAI）

来源：`docs/research/2026-04-06-harness-engineering-research-report.md`

**Anthropic "Building effective agents"**（§4.2）三条层次：
1. 架构层：优先简单、可组合的 workflow，不要过早上复杂框架
2. 运行层：给 agent 一台"计算机"
3. 工具层：工具的命名、边界、描述、返回内容和 token 成本都直接影响 agent 成功率

对照项目四条原则：
- 架构层对应**专注原则**（简单、单一职责）
- 运行层对应**适应性原则**（宿主环境能力）
- 工具层对应**充分原则**（资源可用性）
- 鲁棒性原则没有直接对应——Anthropic 的对应概念是 eval-driven iteration，即可观测后持续迭代

**OpenAI "Harness engineering"**（§4.1）六条：
1. 仓库知识必须 repo-native
2. progressive disclosure 优于 monolithic instruction（与 Doramagic 的 per-stage 渐进披露一致）
3. agent legibility 是第一目标
4. 环境可执行性比 prompt 修辞更关键
5. 文档维护要机械化
6. merge philosophy 改变

第 3 条（agent legibility）指"架构、文档、日志、指标都要变成 agent 可读对象"，对应候选原则 5（可观测）。

---

## Q5：当前晶体 SOP v1.7 在四条原则上的覆盖度？

### 5.1 专注原则的 SOP 保障机制

| 机制 | SOP 位置 | 评级 |
|------|---------|------|
| execution_directive（执行任务而非参考文档） | Step 8a, 晶体结构 | ✅ 成熟 |
| 禁止产出文档代替代码 | Step 8a, 禁止事项 | ✅ 成熟 |
| mode_switch 失败类（产出文档→删除重建） | Step 2a, 通用失败类 | ✅ 成熟 |
| 不适用场景声明（立即告知并停止） | Step 8a, directive | ✅ 成熟 |
| context_acquisition（防止误解用户意图） | Step 6.5 | ✅ 新增（v1.6） |
| 苏格拉底式提问（用业务意图，不用技术细节） | Step 6.5b | ✅ 成熟 |
| **A/B 效能验证（是否真的解决了用户问题）** | Step 10 | ⚠️ 设计存在，未执行 |

**结论**：专注原则在 SOP 中有充分的结构性保障，缺口在验证（无法知道 skill 是否真的解决了用户问题）。

### 5.2 充分原则与知识压缩的张力

充分原则的核心要求："宁可多给，不能缺"。SOP v1.7 中存在两个方向相反的力：

**充分方向**（Step 6c 覆盖率标准）：
- RC 100%
- M 100%
- B ≥80%
- fatal 100%
- high 相关 ≥60%

**压缩方向**（Step 6b 压缩规则）：
- LOW 新颖度 AND LOW 失败预防 → 省略
- LOW Actionability → 改写后再内联，无法改写则省略

**核心张力**：知识压缩的目的是对抗"指令诅咒"（N 条约束的联合遵循率随 N 指数下降），但过度压缩会违反充分原则。

**当前 SOP 的解法是分层加载**（四方评审共识，`docs/research/2026-04-06-harness-four-party-synthesis.md`）：
- EMBED 层（≤15 条）：注意力最高位置，始终在 AI 工作记忆中
- ON_DEMAND 层：按阶段标签检索，每阶段只看当前阶段约束
- 验收层：嵌入各阶段末尾

**评估**：分层加载是正确方向，但"LOW 新颖度 AND LOW 失败预防 → 省略"规则有风险——"LOW 新颖度"是编译者的主观判断，可能低估 AI 实际的知识缺陷。正确的做法应该结合 Step 10 的知识归因分析（哪些知识 AI 自主做对了）来动态校准。

### 5.3 鲁棒性原则：Harness 五子系统覆盖评估

| Harness 子系统 | SOP 覆盖 | 实测验证 | 评级 |
|--------------|---------|---------|------|
| Execution Contract（Spec Lock + Delivery Gate） | Step 1 | v8→v9 验证 | ✅ 成熟+验证 |
| Failure Taxonomy（通用 6 条 + 领域特定） | Step 2 | v8→v9 部分验证（exec 白名单） | ✅ 成熟，部分验证 |
| Stage Spec（阶段拓扑 + Checkpoint） | Step 3 | 未专项测试 | ⚠️ 设计成熟，未验证 |
| State Semantics（状态持久化 + 恢复语义） | Step 4 | 未实现（bp-009 v1.7 待修复） | ⚠️ 设计存在，未落地 |
| Host Adapter（宿主适配 + 工具人因工程） | Step 5 | v5-v9 全程验证 | ✅ 成熟+验证 |

**核心缺口**：State Semantics 是 Harness 五子系统中唯一在生产晶体中尚未完整落地的。`worklogs/2026-04/2026-04-08.md` 明确记录这是下次继续的待完成项。

**另一缺口**：没有跨宿主鲁棒性测试——所有实测（v5-v9）都在 OpenClaw/MiniMax，Claude Code 宿主的行为差异未实测。

### 5.4 适应性原则：context_acquisition + host_adapter 的覆盖度

**context_acquisition（Step 6.5）**：

| 子步骤 | 机制 | 评级 |
|-------|------|------|
| 6.5a 记忆查询 | 从 RP/BA/M 提取查询，宿主适配（Claude memory / Cursor / ChatGPT / 通用降级） | ✅ 设计完整 |
| 6.5b 必问项 | 苏格拉底式提问，FATAL 无默认值 | ✅ 设计完整 |
| 6.5c 可替换点决策 | 优先级：记忆 > 回答 > fit_for > 默认 | ✅ 设计完整 |
| 6.5d 用例映射 | 用 intent_keywords 匹配用例，降级模式完整 | ✅ 设计完整 |

**host_adapter（Step 5）**：

| 能力 | 评级 |
|------|------|
| exec 格式白名单（宿主特定） | ✅ 实测验证 |
| timeout 从 Host Spec 读取（不编撰） | ✅ 机制完整 |
| {workspace} 占位符（路径参数化） | ✅ L12 教训 |
| tool guidance（preferred/avoid） | ✅ Step 5b，Anthropic 最佳实践 |
| 跨宿主通用 HostProfile | ❌ 未设计 |

**重要发现**（`docs/research/2026-03-31-skill-architecture-rethink.md`）：

> 一个 skill 能控制的：文档化流程、声明依赖、提供约束文本、标注能力边界。
> 不能控制的：不能强制宿主 LLM 执行任何脚本；不能阻止宿主用自己的知识替代晶体知识。

这意味着适应性原则的深层问题不是"晶体能否适配宿主"，而是"宿主是否会真正消费晶体"。当前 SOP 通过 execution_directive 的 hardening 来增加消费概率，但无法强制。这是架构层面的约束，不是 SOP 能解决的。

---

## 综合结论

### 四条原则的覆盖评估

| 原则 | 项目覆盖度 | 最强覆盖机制 | 主要缺口 |
|------|----------|------------|---------|
| 专注原则 | ★★★★☆（覆盖充分，验证不足） | execution_directive hardening, model_misuse 失败类 | Step 10 A/B 验证未执行 |
| 充分原则 | ★★★☆☆（有覆盖，有内在张力） | 知识覆盖率标准（RC/M/fatal 100%） | 压缩 vs 充分的张力，省略规则需 Step 10 校准 |
| 鲁棒性原则 | ★★★☆☆（机制设计完整，实测不足） | Spec Lock + Delivery Gate（v8→v9 验证） | State Semantics 未落地，跨宿主测试缺失 |
| 适应性原则 | ★★★★☆（设计完整，深层约束难解） | context_acquisition Step 6.5 + Host Adapter | 宿主不消费晶体时无法强制，缺通用 HostProfile |

### 建议新增的第五条和第六条原则

**第五条：可观测原则**
> skill 必须产出可供 Doramagic 和用户诊断其质量的信号——包括 execution trace、delivery gate 验证结果、知识归因数据。没有可观测就没有系统性迭代能力。

具体落地：强制执行 Step 10 A/B 对照；Trace Schema 落地；建立反馈闭环机制。

**第六条：时效性原则**
> skill 必须知道自己什么时候会失效，并在失效时能被感知——通过 version_pins 和 review_triggers 声明时效边界，通过定期再验证维护有效性。

具体落地：SOP v1.7 的 validity 字段已设计，需要配套的定期再编译流程。

### 对 SOP v1.7 的改进建议

| 建议 | 对应原则 | 优先级 |
|------|---------|--------|
| 强制执行 Step 10 A/B 测试（首次发布前不可跳过） | 可观测原则 | P0 |
| State Semantics 在 bp-009 v1.7 中补充完整（显式 slot 声明） | 鲁棒性原则 | P0 |
| 建立第三个宿主的 Host Spec（如 generic/Cursor） | 适应性原则 | P1 |
| 知识压缩省略规则增加校准步骤（对照 Step 10 归因数据） | 充分原则 | P1 |
| 在 Step 10 中补充"宿主不消费晶体"的检测机制 | 专注原则 | P1 |
| 为每个已交付晶体设定 review_trigger 的触发检查流程 | 时效性原则 | P2 |
| 设计通用 HostProfile 框架（Host Capability Model） | 适应性原则 | P2 |

---

## 关键文件索引

| 文件 | 关键内容 |
|------|---------|
| `PRODUCT_CONSTITUTION.md` | §1.3 晶体公式，§3.4 种子晶体结构，§1.8 六条原则 |
| `sops/finance/crystal-compilation-sop.md` | Step 10 效能验证，Step 6.5 context_acquisition，Step 9 质量校验 |
| `sops/_template/crystal-compilation.tmpl.md` | L1-L33 教训日志（全部 33 条） |
| `docs/experiments/2026-04-06-crystal-iteration-log.md` | v8/v9 实测数据，5 个失败根因分析 |
| `docs/experiments/2026-04-06-v5-hardened-monitoring-report.md` | v5 策略替换事件详细时间线 |
| `docs/research/2026-04-06-harness-four-party-synthesis.md` | Harness 五子系统三方评审 |
| `docs/research/2026-04-06-harness-engineering-research-report.md` | Anthropic/OpenAI 工程最佳实践 |
| `docs/research/2026-03-31-skill-architecture-rethink.md` | "建议性平台"vs"执行性平台"核心诊断 |
| `docs/designs/2026-04-06-directive-hardening.md` | CLI-Anything 对标，三段式 directive 设计 |
| `docs/designs/2026-04-08-knowledge-quality-framework.md` | 13 项知识质量指标，红线/核心/过程三档 |
| `docs/designs/2026-04-05-crystal-forge-discussion.md` | 议题 7（反馈闭环），议题 9（Token 预算） |
| `docs/research/host-specs/openclaw-host-spec.md` | OpenClaw 实测能力表（exec 行为，timeout 等） |
| `worklogs/2026-04/2026-04-04-session2.md` | 首次端到端验证，v1 量化评估数据（57%） |
| `worklogs/2026-04/2026-04-06.md` | v9 首次全指标通过，业务逻辑层发现 |
| `worklogs/2026-04/2026-04-08.md` | SOP v1.7 定稿，bp-009 v1.7 编译结果，待完成事项 |

---

*报告版本: v1.0 | 研究日期: 2026-04-08 | 研究者: Claude Sonnet 4.6*
*本报告基于 Doramagic 项目内所有已有文档，不引用项目外未经验证的信息*
