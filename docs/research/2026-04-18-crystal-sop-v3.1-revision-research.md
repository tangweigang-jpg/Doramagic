# Crystal SOP v3.1 修订研究报告

**日期**: 2026-04-18
**作者**: Doramagic 主线程 + 2 sonnet 子代理（数据收集与文档撰写）
**版本**: v1.0
**状态**: 已完成，待转化为 SOP 修订行动

---

## 1. 摘要

本研究起因于蓝图 SOP（blueprint-extraction-sop.md）和约束 SOP（constraint-collection-sop.md）分别升级至 v3.6 和 v2.3 后，晶体 SOP（crystal-compilation-sop.md）仍停留在 v3.0、仍声明自己是"v3.2 + v2.2 的下游"。主线程发起本次讨论，目标是全面评估晶体 SOP 是否需要微调、微调的范围和优先级。

本研究覆盖四个维度：（1）晶体 SOP v3.0 与上游 v3.6/v2.3 的 gap 分析，识别出 14 项差距并按 P0/P1/P2 分档；（2）多宿主分层模型理论研究，提出 L1/L2/L3 三层模型及 resources 拆分方案；（3）OpenClaw 实测经验复盘，梳理 8 个失败模式和 5 个有效 pattern；（4）本机参考资料盘点，评估现有研究文献对第一期工作的支撑度。

**最终决策**（用户明确）：晶体 SOP 升级为 v3.1，第一期聚焦 OpenClaw 单宿主，不做跨宿主 portability 架构，该议题推至 Phase 2。

**Phase 1 行动方向**：完成 P0 必修 7 项（含 4 项上游对齐 gap + 3 项实测教训强化），基于 claude-code-instructkr 研究库重设计 Step 5 Host Adapter 和 Step 6 知识组织，专门为 OpenClaw 优化。

---

## 2. Gap 分析：晶体 SOP v3.0 vs 上游 v3.6/v2.3

### 上游 SOP 状态

| SOP | 当前版本 | 关键升级内容 |
|-----|---------|------------|
| `sops/finance/blueprint-extraction-sop.md` | v3.6 | 6 类 BD (T/B/BA/DK/RC/M)、知识源类型探测（代码/文档/混合）、文档萃取分支 (2a-s)、11 子领域（v3.5 新增 INS/LND/TRS/AML）、20 项金融通用必审 + 子领域必审、resources/activation/evidence_role/extraction_methods/audit_checklist_summary 字段 |
| `sops/finance/constraint-collection-sop.md` | v2.3 | 6 种 constraint_kind（新增 rationalization_guard）、9 种 consequence_kind（新增 safety/false_claim）、Step 2.1-s 文档约束、Step 2.4 蓝图派生 + derived_from、Step 2.6 guard_pattern、validation_threshold、machine_checkable/promote_to_acceptance、双联约束（boundary+remedy）、conflict/overclaim_risk 标记 |
| `sops/finance/crystal-compilation-sop.md` | v3.0（待升级） | 头部仍写"v3.2 / v2.2 的下游"，已落后两个大版本 |

### P0：必修项（4 项）

**Gap 1：头部依赖版本声明过期**

- 现象：晶体 SOP 头部明确声明是"蓝图 v3.2 + 约束 v2.2 的下游"，实际上游已到 v3.6/v2.3。
- 影响：编译者依赖头部版本做兼容性判断，过期声明导致误判当前 SOP 是否适用。
- 修复方向：更新头部版本声明为蓝图 v3.6 + 约束 v2.3，同步更新 SOP 编号至 v3.1。

**Gap 2：rationalization_guard 全方位缺失**

- 现象：约束 SOP v2.3 新增第 6 种 constraint_kind——rationalization_guard，并在 Step 2.6 规定了 guard_pattern（含 excuse/rebuttal/red_flags/violation_detector 四个子字段）。晶体 SOP Step 6.6b 的 kind 权重表只列原有 5 种；Step 6（知识组织）没有 guard_pattern 的任何渲染指令；Step 9 D-check 无对应验证点。
- 影响：rationalization_guard 类约束在编译时被当作普通约束处理，guard_pattern 字段被丢弃，结果是 AI 被调用时遇到"跳步合理化"行为时缺乏对应防护。这是约束体系的核心安全机制之一。
- 修复方向：（a）Step 6.6b kind 权重表补入 rationalization_guard；（b）Step 6 增加 guard_pattern 四子字段的渲染规则，指定在 directive 段的呈现位置和格式；（c）Step 9 新增 D19 检查点：验证所有 rationalization_guard 约束的 guard_pattern 均已渲染。

**Gap 3：双联约束无成对渲染规则**

- 现象：约束 SOP v2.3 强制规定 1 个 missing gap 必须派生 2 条配对约束（boundary 约束 + remedy 约束），形成"不行 + 替代方案"的双联结构。晶体 SOP Step 6 和 Step 8 均无配对呈现的任何说明。
- 影响：编译后的晶体可能仅呈现 boundary 约束（告知 AI"什么不能做"），而 remedy 约束被单独处理甚至丢失。AI 执行时知道禁止项但不知道合法替代路径，容易陷入决策僵局或绕路。
- 修复方向：Step 6 增加配对约束识别逻辑（通过 pair_id 字段匹配）；Step 8 渲染模板中增加 boundary+remedy 配对块，要求二者在 directive 段中紧邻出现。

**Gap 4：文档/混合知识源处理零提及**

- 现象：蓝图 SOP v3.6 新增文档萃取分支（Step 2a-s）和知识源类型探测（代码/文档/混合三类），引入了 evidence_role（normative/example/rationale/anti_pattern）字段，以及 conflict:true 和 overclaim_risk:true 约束标记。晶体 SOP 假设所有知识源均为代码源，对上述新字段和标记无任何处理规则。
- 影响：（a）evidence_role 字段在编译时被忽略，normative 和 example 类证据以相同权重渲染，导致规则层级模糊；（b）conflict:true 约束（多个知识源存在矛盾）未触发特殊处理，可能呈现自相矛盾的 directive；（c）overclaim_risk:true 约束（文档声称但代码未实现）未降级 modality，可能被以 FATAL 级别呈现一个虚假能力；（d）code_observed vs doc_declared 两类 BD 的合并规则缺失。
- 修复方向：Step 6 增加知识源类型分支，按 evidence_role 分层渲染；新增 conflict 和 overclaim_risk 约束的 modality 降级规则（如 FATAL → WARN）；Step 2b 增加 BD 类型感知（code_observed vs doc_declared）的合并策略。

### P1：强烈建议项（6 项）

**Gap 5：Step 6.6c consequence_kind 阈值列表不全**

- 现象：低分阈值放行判断仅列出 {financial_loss, safety, compliance, data_corruption, false_claim} 5 种，缺少 bug/performance/service_disruption/operational_failure。
- 影响：consequence_kind 为 bug 或 performance 的约束在低分情况下被错误放行，未得到足够的强制力加持。
- 修复方向：Step 6.6c 的阈值表补全 9 种 consequence_kind，与约束 SOP v2.3 完整列表对齐。

**Gap 6：derived_from 字段未利用**

- 现象：约束 SOP v2.3 Step 2.4 规定派生约束必须携带 derived_from（含 blueprint_id/business_decision_id/derivation_version），但晶体 SOP 既不做去重（同一 BD 可能派生出重复约束），也不在溯源块中呈现来源链路。
- 影响：编译产出的晶体难以追溯某条约束为何存在，也无法识别冗余约束对。
- 修复方向：Step 2b 增加 derived_from 去重逻辑；Step 8 的知识块渲染增加可选溯源注释格式。

**Gap 7：promote_to_acceptance 字段未硬连线**

- 现象：约束 SOP v2.3 新增 promote_to_acceptance 布尔字段，含义是该约束应自动晋升为 acceptance criterion。晶体 SOP Step 1b 仅说"按规则自动纳入"，未明确 promote_to_acceptance:true 必须映射到 Hard Gate 级别。
- 影响：promote_to_acceptance:true 的约束可能以普通约束方式处理，未强制成为 Gate，导致验收时缺乏对应检查点。
- 修复方向：Step 1b 增加明确规则：promote_to_acceptance:true 强制对应 Hard Gate，写入 acceptance criteria 块而非普通 constraint 块。

**Gap 8：resources 结构升级未利用**

- 现象：蓝图 SOP v3.6 的 resources 字段已升级为结构化清单（含 id/type/name/path/used_in_stages 子字段），晶体 SOP 仍按旧模式处理，将所有 resources 整段内联，未按 used_in_stages 分组渲染（例如哪些资源用于 context_acquisition 阶段，哪些用于 implementation 阶段）。
- 影响：AI 执行时需要在整个资源列表中自行判断当前阶段应使用哪个资源，增加判断负担和出错概率。
- 修复方向：Step 5 resources 渲染改为按 used_in_stages 分组，每个执行阶段对应可见的资源子集。

**Gap 9：applicability.activation.triggers / anti_skip 缺失对接**

- 现象：蓝图 SOP v3.6 从 SKILL.md 的"When to Use / NOT to Use"段落萃取了 activation.triggers 和 anti_skip 字段，表达"何时应该激活该晶体"和"哪些情况不应跳过"。晶体 SOP Step 5 的 directive 段未消费这两个字段。
- 影响：activation 条件和 anti_skip 规则被丢弃，无法在 directive 段向 AI 明确"在什么情况下你必须使用这个晶体"。
- 修复方向：Step 5 directive 段头部增加 activation trigger 渲染规则，anti_skip 规则纳入 preservation_manifest 强制声明。

**Gap 10：Failure Taxonomy 未覆盖 false_claim**

- 现象：约束 SOP v2.3 新增 false_claim 作为第 9 种 consequence_kind（含义：AI 声称某功能存在/某结果达成，但实际未实现），晶体 SOP Failure Taxonomy 的 7 通用失败类中没有对应条目（mode_switch 接近但不等价）。
- 影响：false_claim 类约束在编译后无对应 failure class 支撑，AI 做出虚假声明时晶体无法提供对应的失败检测模式。
- 修复方向：Failure Taxonomy 新增 false_claim_failure 类，明确其触发条件和检测方式。

### P2：优化项（4 项）

**Gap 11：子领域扩展感知**

- 现象：蓝图 SOP v3.5 新增 INS/LND/TRS/AML 四个子领域，晶体"适用范围"表只举一般任务类型。
- 修复方向：Step 2b 给出各子领域的 domain-specific failure class 模板，例如 INS 死亡率表过期、LND 借贷不平、AML 名单延迟、TRS LCR 越线等。

**Gap 12：金融术语表过窄**

- 现象：Step 0c 术语表约 19 项，全部集中在 TRD（交易）和 RSK（风险）领域，缺少 INS/LND/TRS/AML 子领域术语（reserve/DPD/LCR/NSFR/KYC/CTR/SAR/PD/LGD/Solvency II 等）。
- 修复方向：Step 0c 按子领域扩展术语表，或拆分为各子领域独立词汇附录。

**Gap 13：_rejected.jsonl 信号未在 Preflight 利用**

- 现象：约束 SOP 的 Pydantic 校验会把失败约束写入 _rejected.jsonl，晶体 SOP Preflight 阶段未检查该文件。
- 修复方向：Preflight 增加一步：读取 _rejected.jsonl，若占比超过阈值（如 10%）则 WARN，提示编译者先修复上游约束质量。

**Gap 14：Step 9 D-check 缺少新检查点**

- 现象：Step 9 的 D-check 验证点未覆盖新增字段和结构。
- 修复方向：新增 4 个检查点——D19（rationalization_guard 渲染存在性）、D20（双联约束完整性，boundary+remedy 配对）、D21（derived_from 溯源完整）、D22（conflict/overclaim_risk 标记已处理）。

---

## 3. 多宿主分层模型研究

### 3.1 三层模型

本节为本次讨论的核心理论贡献。主线程提出将晶体内容按宿主依赖程度分为三层，解决当前 SOP 中宿主无关知识与宿主特有配置混杂的问题。

| 层 | 内容 | 是否随宿主变化 | 当前 SOP 处理状态 |
|----|------|--------------|----------------|
| **L1 知识层** | 蓝图 + 约束 + 用例 + spec_lock 内容 | 否，100% host-agnostic | 已是，无需改动 |
| **L2 执行协议层** | Stage Spec / State Semantics / Failure Taxonomy / context_state_machine | 协议骨架 universal，物理参数 per-host（如 timeout 值） | 当前混在一起，timeout 直接写死 |
| **L3 物理适配层** | exec 白名单 / tool 名 / {workspace} 解析 / 单/多文件结构 | 完全 per-host | Step 5 处理但粒度太粗 |

### 3.2 跨宿主差异的实例

以下实例说明跨宿主差异的工程严重性，是推动分层模型的直接动因：

- **Codex CLI 没有子代理**：Iterative 模式的 implement_test_loop.forced_checkpoint 机制在该宿主下失效，无法降级到等效替代。
- **Cursor 是单线 agent + IDE 内联**：长 directive 段会被宿主压缩，晶体核心约束存在静默丢失风险。
- **Harness Agent 有 trace_schema 原生支持**：可直接消费 jsonl trace，其它宿主需降级到 stdout 解析。
- **Claude Code Skill vs OpenClaw manual + askable**：加载触发模式不同，activation triggers 的表达方式需要宿主层适配。

### 3.3 Resources 的归层——重要细化

当前 SOP 把 resources 整段放在 L1（knowledge）块，这是类型错误。Resources 内部存在 L1/L3 混杂，必须拆分：

| 资源子项 | 性质 | 应归层 |
|---------|------|-------|
| 包名 + 版本范围 + import alias | 业务事实（用哪个库） | L1 |
| 数据源选择 + schema | 业务决策（来自 replaceable_points）| L1 |
| API endpoint / 协议 / 数据 schema | 业务事实 | L1 |
| 业务代码示例 / 回测骨架的策略骨架 | 业务知识 | L1 |
| 安装命令（pip/uv/poetry/conda） | 物理执行，随宿主环境变化 | L3 |
| 凭证注入方式（OpenClaw secrets / CC env / Codex 无 secret manager / Cursor .env） | 物理执行，完全 per-host | L3 |
| 文件写入手段（Write tool / editor diff / fs call） | 物理执行，工具名随宿主变化 | L3 |
| 数据库路径模板（{workspace}/data.db） | 物理执行，路径解析 per-host | L3 |

关于 Scaffold 骨架的特殊处理：骨架结构（焊死的 FATAL RC）属于 L1（是知识），REPLACE_WITH 占位符语法属于 L1，但"写到哪个文件、用什么工具写"属于 L3。

**Crystal IR 推荐结构**（Phase 2 实施）：

```yaml
knowledge:
  resources:               # L1：what to use（host-agnostic）
    packages: [...]
    data_sources: [...]
    code_templates: [...]
    infrastructure_choices: [...]
harness:
  host_adapters:
    {host}:
      install_recipes: [...]       # L3
      credential_injection: [...]  # L3
      path_resolution: [...]       # L3
      file_io_tooling: [...]       # L3
```

业务后果：新增宿主时只需补 host_adapters.{new_host} 子段，L1 知识层零改动。

---

## 4. 第一期范围决策

**用户明确决定**：第一期不做跨宿主独立适配，聚焦 OpenClaw 单宿主。

决策理由：跨宿主分层架构（L1/L2/L3 完整拆分 + host_adapters 体系）工程成本较高，且当前尚无充分的跨宿主实测数据支撑设计决策。第一期目标是用通用 AI agent 工程能力（agent 编排、harness 优化、上下文工程）把 OpenClaw 单宿主跑通、跑稳，积累足够的实测反馈后再推广到多宿主。

**第一期明确放弃**：

- 跨宿主 portability（L1/L2/L3 完整分层架构推到 Phase 2）
- 等齐 Temporal/Reflexion/DSPy 等外部资料后再行动（Phase 2）
- 主动建 codex/cursor/gemini host-spec（Phase 2）

**第一期聚焦**：

- Crystal SOP v3.0 → v3.1 修订，完成 P0 必修 7 项
- 基于 claude-code-instructkr 研究库（14 章 + 512K LOC 源码级分析）重新设计 Step 5 和 Step 6
- OpenClaw 单宿主实测验证，持续更新失败模式库

---

## 5. OpenClaw 实测经验复盘

### 5.1 运行历史时间线

8 个版本按时间顺序：

| 版本 | 日期 | 描述 | 关键结果 |
|------|------|------|---------|
| SKILL v3.1.0 | 2026-03-21 | IB 学习助手 / A 股选股，MiniMax-M2.7 + GLM-5 | 流水线绕过，3/30 通过 |
| finance-bp-002-v8 | 2026-04-06 | MACD 回测 / MiniMax-M2.7 | 5 项 FAIL |
| finance-bp-002-v9 | 2026-04-06 | MACD 回测 | 首个全 PASS，年化 -25.30%（合法结果） |
| finance-bp-009-v1.8 | 2026-04-08 | 1883 行 / 多因子+龙虎榜 | 部分通过，用例错配 |
| finance-bp-009-v1.9 | 2026-04-08 | 4375 行 / K线+布林带 | 5 控制块全生效 |
| finance-bp-009-v2.0 | 2026-04-08 | 4460 行 / MACD+均线 | T+1 首次自主实现，涨跌停仍缺 |
| finance-bp-009-v2.1 | 2026-04-08 | 金叉死叉策略 | 涨跌停首次被 Scaffold 引用 |

### 5.2 八个失败模式 vs SOP v3.0 覆盖度

| 失败模式 | 描述 | v3.0 覆盖度 |
|---------|------|-----------|
| 1. 流水线语义绕过 | AI 把执行指令当成参考信息，选择性跳过阶段 | 未覆盖 |
| 2. exec 拦截链式命令 | & & / ; / pipe 等链式命令被拦截，AI 未做降级 | 部分覆盖 |
| 3. 参数漂移 | TOP_N 从 5 漂移到 30，股票池膨胀 15 倍，无检测 | 部分覆盖 |
| 4. 用例错配 | "机构"关键词同时触发 UC-14 和 UC-15，消歧规则缺失 | 未覆盖 |
| 5. 安全检查知识内化但不执行 | 涨跌停逻辑 AI 知道（0/3 测试均生成了相关注释）但代码未实现 | 未覆盖 |
| 6. 知识二次压缩 | 1883 行 SKILL.md 经 compaction 缩减至 658 行，35% 转化率，FATAL 约束保留完整 | 部分覆盖 |
| 7. context_acquisition 跳过 | AI 跳过数据获取阶段直接进入实现 | 已覆盖 |
| 8. 多文件超时 | v5-v7 多文件写入方案导致超时 | N/A（已转单文件方案） |

### 5.3 五个有效 Pattern

**Pattern 1：Scaffold 骨架模式**

核心做法：把安全检查（涨跌停判断、仓位上限等 FATAL RC 约束）直接焊死在代码骨架里，AI 只能填充 REPLACE_WITH 占位符，无法绕过骨架结构。

验证数据：涨跌停从 v1.8/v2.0 的 0/3 实现率，到 v2.1 首次被 Scaffold 引用。方向正确，仍需跨模型验证。

**Pattern 2：单文件自包含**

核心做法：1 次 write_file + 1 次 exec，全部逻辑在单个文件内完成。

验证数据：工具调用次数从 8-12 次降至 2 次，端到端耗时从 430-700 秒降至约 200 秒。

**Pattern 3：控制块以知识方式生效**

核心观察：intent_router / context_state_machine / spec_lock_registry / preservation_manifest / output_validator 五个控制块，在 v1.9/v2.0/v2.1 三次独立测试中均以"AI 从中获取知识后自主决策"的方式生效，而非以"AI 被强制执行指令"的方式。这是关键机制洞察：晶体约束影响 AI 的推理前提，而非覆盖 AI 的自主判断。

**Pattern 4：Spec Lock 分层**

核心做法：领域不变量（如 T+1 交收规则、涨跌停 10%）与框架约束（如 backtrader 引擎用法）分开声明，前者 FATAL 级别、无可替代，后者 STRONG 级别、有替代方案。

验证数据：MiniMax-M2.7 二次压缩后 FATAL 约束 8/8 全保留，框架约束按上下文动态保留。

**Pattern 5：FATAL 约束跨宿主传递性**

核心观察：即使经过宿主侧 context compaction（35% 压缩率），FATAL 级别的领域不变量约束在 MiniMax-M2.7 上保留率为 100%。这支持"把真正不可逾越的规则标为 FATAL"的设计策略。

### 5.4 bp-009 三个质变节点

| 版本 | 质变内容 | 核心指标 |
|------|---------|---------|
| v1.8 | 全量知识注入 | BD 覆盖率 12% → 96%，UC 覆盖率 2.5% → 98% |
| v1.9 | 五控制块首次实战生效 | intent_router / context_state_machine / spec_lock_registry / preservation_manifest / output_validator 全部在生产环境生效 |
| v2.1 | Scaffold 骨架突破安全检查天花板 | 涨跌停从 0/3 实现率到首次被 Scaffold 引用 |

### 5.5 五大未解痛点（按优先级）

**[P0] output_validator assert 代码块持续被降级**

3/3 测试中，output_validator 段被 AI 从可执行 assert 代码块改写为自然语言描述。异常数据（+987%/-632%）无硬告警，验收时依赖人工判断。这是当前最致命的设计缺陷：晶体声称有输出验证能力，但实测中该能力被 AI 自主降级。

**[P0] Scaffold 跨模型验证空白**

全部实测基于 MiniMax-M2.7。Claude/GPT 等高自主性模型的估计 Scaffold 绕过概率为 15-25%（未验证），存在"换模型后 Scaffold 全线失效"的技术风险。

**[P1] compaction safeguard 模式行为未文档化**

知道 compaction 存在、知道 FATAL 约束保留率高，但不知道 compaction 的具体保留算法，无法预测在极端压缩比下的行为边界。

**[P1] exec preflight 完整拦截规则不透明**

知道 exec 会拦截链式命令，但拦截规则的完整边界未文档化，编写 exec 指令时无法确认某个写法是否安全。

**[P2] 晶体效能 A/B 对照验证缺失**

目前没有"有晶体 vs 无晶体"的基线对比数据，无法量化晶体对 AI 执行质量的净影响。所有改进数据都是版本间相对比较。

---

## 6. 本机参考资料盘点

### 6.1 七主题覆盖度

| 主题 | 资料数量 | 代表性资料 |
|------|---------|-----------|
| Agent 编排 | 5+ | `docs/research/claude-code-instructkr/report/` 第 04 章（8700 行源码级分析）、`docs/research/deer-flow-soul-study.md` |
| Harness 工程 | 6+ | `docs/research/papers/anthropic-effective-harnesses-for-long-running-agents.md`、`docs/research/2026-04-14-meta-harness-deep-research.md`、`docs/research/2026-04-06-harness-engineering-research-report.md` |
| 上下文工程 | 3 | `docs/research/claude-code-instructkr/report/` 第 08 章（3900 行）、`docs/research/ai-agent-engineering-consensus.md` |
| Prompt 工程 | 3 | `docs/research/claude-code-instructkr/report/` 第 05 章（8000+ token 系统提示词解构） |
| Tool use | 2 | `docs/research/claude-code-instructkr/report/` 第 03 章、`docs/research/2026-04-06-openclaw-execution-pattern.md` |
| Skill 设计 | 5+ | `docs/research/2026-04-08-what-makes-a-good-skill.md`、`docs/research/claude-code-instructkr/report/` 第 06 章 |
| AI Agent 评测 | 4 | `docs/designs/2026-04-01-eval-driven-quality-improvement.md`、`docs/research/2026-04-10-extraction-quality-deep-research.md` |

### 6.2 最值得参考的 3 份资料

**第一优先：`docs/research/claude-code-instructkr/report/` 14 章**

Claude Code 512K LOC 源码逆向分析，研究对象正好是 OpenClaw 的宿主（Claude Code 是上游系统）。其中 context-management / tool-system / skill-system 三章直接支撑 SOP v3.1 的 Step 5 和 Step 6 改写。

**第二优先：`docs/research/papers/anthropic-effective-harnesses-for-long-running-agents.md`**

Anthropic 官方一手研究资料，initializer/executor 双 agent 模式直接对应晶体编译的 preflight/compile 两阶段。

**第三优先：`docs/research/2026-04-14-meta-harness-deep-research.md`**

Stanford 论文形式化 harness 优化目标，提供 Failure Taxonomy 改进和 State Machine 设计的学术框架。

### 6.3 覆盖缺口（推到 Phase 2 解决）

严重不足：Failure Taxonomy 学术精细分类（当前靠实测归纳，缺系统性分类框架）、State Machine/Checkpoint 工程细节（durable state 如何跨 compaction 持久化）、Host Adapter 设计模式（跨宿主适配的工程标准）。

中等不足：DSPy/TextGrad 自动 prompt 优化（用于 directive 段自动调优）、SWE-bench/TerminalBench 公开评测对齐（将晶体质量接入公开 benchmark）。

### 6.4 结论

本机参考资料**部分足够**支撑第一期 harness 优化。Agent 编排、Harness 宏观设计、Skill 设计三个主题的资料深度和覆盖度足够支撑 v3.1 修订工作；Failure Taxonomy 精细分类、durable state machine 工程细节、Host Adapter 设计偏弱，但这三项均已列入 Phase 2 范围，不阻塞第一期。

---

## 7. Crystal SOP v3.1 修订方案

### 7.1 修订源头三类

| 修订源头 | 内容 | 估时 |
|---------|------|-----|
| A. 上游 SOP 对齐 | P0 4 项 + P1 6 项 + P2 4 项，共 14 项 gap（详见第 2 章） | 1-1.5 天 |
| B. OpenClaw 实测教训 | 强化 8 失败模式中"未覆盖"3 项 + "部分覆盖"4 项；重点：Scaffold 骨架强制化、intent_router 消歧字段、preservation_manifest 强化、output_validator 落地机制 | 1 天 |
| C. 通用 agent 知识注入 | 用 claude-code-instructkr 14 章（context-management / tool-system / skill-system），重新设计 Step 5 Host Adapter 和 Step 6 知识组织，专门为 OpenClaw 优化 | 0.5-1 天 |

### 7.2 第一期 P0 必修清单（共 7 项）

**来自上游 SOP 对齐（4 项）**：

1. SOP 头部版本号更新至 v3.1，依赖声明改为蓝图 v3.6 + 约束 v2.3。
2. rationalization_guard 全方位补齐：Step 6.6b kind 权重表补入该种类；Step 6 增加 guard_pattern 四子字段（excuse/rebuttal/red_flags/violation_detector）渲染指令；Step 9 新增 D19 检查点。
3. 双联约束（missing gap → boundary+remedy）成对渲染规则：Step 6 增加 pair_id 配对识别；Step 8 渲染模板中 boundary+remedy 配对块要求紧邻出现。
4. 文档/混合知识源处理：Step 6 增加 evidence_role 分层渲染；conflict 和 overclaim_risk 约束的 modality 降级规则；Step 2b 补 BD 类型（code_observed vs doc_declared）合并策略。

**来自 OpenClaw 实测教训（3 项）**：

5. **Scaffold 骨架强制化**：从"可选 pattern"提升为"FATAL RC 必须焊死在 Scaffold 中"，写入 Step 6 和 Step 8d。不再作为推荐做法，而是编译规范的强制要求。
6. **intent_router 强制消歧字段**：蓝图已在字段层支持 negative_keywords/disambiguation/data_domain，晶体 SOP 必须强制将这三个字段渲染进 intent_router 控制块，覆盖用例错配失败模式（如 Gap 4 中"机构"关键词撞多 UC 的问题）。
7. **output_validator 落地强化**：v3.0 已要求渲染为可执行 assert 代码块，但实测降级率 3/3。v3.1 需要更强约束：directive 段明确声明"AI 不得删除、改写或降级 assert 块"，并在 Step 9 D-check 增加对应验证点。

### 7.3 P1 建议同期处理（可选）

preservation_manifest 强化：v3.0 已存在 preservation_manifest，但实测 35% 转化率说明强度不足（上下文压缩后丢失了 65% 的非 FATAL 约束）。建议 v3.1 中 preservation_manifest 的 MUST_PRESERVE 列表明确包含所有 STRONG 级约束，并增加 compaction 后的再验证触发点。

---

## 8. 未决议题

以下议题本次讨论未达成最终决策，推到下一轮讨论：

**议题 1：output_validator 强制执行机制**

当前在 directive 段声明"不得降级 assert 块"是否足够？实测数据（3/3 降级）显示纯 directive 声明无效。是否需要平台层 hook（OpenClaw exec 层在任务完成后自动检查 assert 块是否存在）作为第二防线？这涉及晶体边界和 OpenClaw harness 边界的职责划分。

**议题 2：A/B 效能基线建立**

是否在 Crystal SOP v3.1 中加入 Step 11"晶体效能 A/B 验证"，要求每个晶体首次发布前必须有"无晶体基线"对比数据？此举能量化晶体价值，但增加首次编译成本，需要权衡。

**议题 3：Scaffold 跨模型验证**

第一期 OpenClaw 单宿主是否用 GLM-5 + MiniMax-M2.7 双模型作为内部 A/B，在正式发布跨宿主支持之前先建立跨模型的稳健性数据？

---

## 9. 下一步建议行动

本研究已完成理论分析和现状盘点，具体行动有两条路可选：

**路线 A：立即开始 Crystal SOP v3.1 草案撰写**

以本研究为直接输入，按第 7 章修订方案起草 SOP v3.1 全文。估时 2.5-3.5 天（A+B+C 三类修订合计），产出可供评审的 SOP 草案。适合优先推进整体对齐的情况。

**路线 B：先单点深挖 output_validator 强制执行机制**

output_validator assert 代码块持续被降级是当前最致命的设计缺陷（3/3 失败），且解决方案涉及晶体 SOP 和 OpenClaw harness 两个层面的设计决策。建议先专项研究该问题（预计 0.5 天）再进入全文修订，避免带着未解核心问题写出需要大幅返工的草案。

主线程认为路线 B 优先级更高，但最终路线选择由用户决定。

---

## 附录：关键路径引用

- 蓝图 SOP：`sops/finance/blueprint-extraction-sop.md`（当前版本 v3.6）
- 约束 SOP：`sops/finance/constraint-collection-sop.md`（当前版本 v2.3）
- 晶体 SOP：`sops/finance/crystal-compilation-sop.md`（当前版本 v3.0，目标 v3.1）
- bp-009 实测晶体：`knowledge/crystals/finance-bp-009/`
- claude-code-instructkr 研究库：`docs/research/claude-code-instructkr/report/`
- Harness 工程研究：`docs/research/2026-04-14-meta-harness-deep-research.md`
- Anthropic harness 论文：`docs/research/papers/anthropic-effective-harnesses-for-long-running-agents.md`
- Scaffold 实测复盘：`docs/research/2026-04-08-scaffold-multi-llm-review.md`
- bp-009 v1.8 OpenClaw 测试复盘：`docs/research/2026-04-08-crystal-v1.8-opus-review.md`
