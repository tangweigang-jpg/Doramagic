# 蓝图提取 Agent 改进技术研究报告

> 研究日期：2026-04-13
> 研究来源：harness-engineering 仓库 + Claude Code 源码逆向报告 + Doramagic 现有代码
> 目的：为 Doramagic 蓝图提取 agent 的下一代演进提供技术洞察

---

## 一、研究范围与方法论

本次研究并行分析三个信息源：

| 来源 | 性质 | 核心价值 |
|------|------|---------|
| `deusyu/harness-engineering` | Harness Engineering 范式知识库（8 篇文章交叉分析） | Agent 约束系统设计方法论 |
| `docs/research/claude-code-instructkr/report/` | Claude Code 512K LOC 源码逆向分析（14 章） | 工业级 Agent 系统的架构模式 |
| Doramagic `packages/extraction_agent/` | 当前 v5.2 蓝图提取 agent 实现 | 现状基线与改进锚点 |

研究方法：3 个并行子代理分别深度研究各来源，主线程综合交叉分析。

---

## 二、Doramagic 蓝图提取 Agent 现状分析

### 2.1 架构概貌（v5.2）

当前蓝图提取 agent 是一个 **17-Phase SOPExecutor 流水线**，经历了五代演进（v3.2 → v4 → v4.1 → v5 → v5.2）：

```
Pre-processing（4 Phase）→ Coverage Manifest（1 Phase）→ 并行 Workers（5+2 路）
    → Synthesis v5（3 步 Instructor）→ 确定性后处理（2 Phase）
    → Assembly + Enrich（14 个零 LLM Patch）→ Quality Gate（BQ-01~09）
```

核心文件：
- `sop/blueprint_phases.py`（~3000 行）— Phase 工厂，5 个版本共存
- `core/agent_loop.py`（~800 行）— ExtractionAgent 主循环 + Instructor 三降级链
- `sop/executor.py`（~500 行）— Phase 编排、依赖检查、并行组
- `sop/blueprint_enrich.py`（~940 行）— P0-P13 确定性后处理
- `sop/schemas_v5.py`（~400 行）— Pydantic 模型
- `sop/prompts_v5.py`（~350 行）— Synthesis Prompt

### 2.2 Evidence Packet 机制

v5 引入的核心概念——Worker 输出结构化 JSON 证据包而非自由文本：
- `worker_arch.json`：stages / data_flow / global_contracts / replaceable_points
- `worker_arch_deep.json`：架构级 BD 猎手，≤ 8KB 预算
- `worker_workflow.json` / `worker_math.json`：原始业务决策数组
- Evidence 格式：`file:line(function_name)`，由 P5 enrich 做归一化
- 质量门 BQ-06：evidence_coverage_ratio ≥ 50%（软警告）

### 2.3 关键设计决策

1. **Instructor 三降级链**：L1 tool_use → L1.5 salvage → L2 自由文本 + JSON 提取 → L3 RawFallback
2. **Synthesis patch-only 模式**：只发送 rationale < 60 字符的 BD 子集，patch 回合并
3. **P0-P13 零 LLM enrich**：14 个纯 Python 变换，确定性、可测试、快速
4. **六类 BD 分类框架**：T / B / BA / DK / RC / M，反事实测试分离 T vs 非 T
5. **并行 Phase 组**：`asyncio.gather` 驱动，explore 组 5 路 + workers 组 2 路

### 2.4 已识别的局限性

| 编号 | 问题 | 严重度 |
|------|------|--------|
| L1 | Phase B/C `blocking=False`，失败不阻断，UC 可能缺失 | 高 |
| L2 | `worker_audit` 不参与 Synthesis，审计发现与 BD 提取脱节 | 高 |
| L3 | 质量门硬门默认 `strict=False`，形同虚设 | 高 |
| L4 | YAML 修复是启发式正则，可能引入语义错误 | 中 |
| L5 | 覆盖缺口硬编码上限 10 个目录 | 中 |
| L6 | Token 估算用字符比例，代码密集型精度低 | 中 |
| L7 | 上下文压缩截断工具调用历史，Worker 可能丢失上下文 | 中 |
| L8 | BD ID 无全局唯一性检查，合并时可能碰撞 | 中 |
| L9 | Stage 映射表 35 条硬编码，不覆盖新项目 | 低 |
| L10 | 没有全局代码调用图（tree-sitter），覆盖率 ~50-60% | 高 |
| L11 | 多模型评审（Step 6 四方评审）完全缺失 | 中 |
| L12 | Assembly 阶段 LLM 看不到 BD 列表，stage 设计与 BD 不一致 | 中 |
| L13 | 只支持 Python AST，TypeScript/Java/Go 无法处理 | 中 |

---

## 三、外部技术洞察

### 3.1 Harness Engineering 范式（来源：deusyu/harness-engineering）

#### 核心思想

```
传统工程：人类写代码 → 机器执行代码
Harness Engineering：人类设计约束 → 智能体写代码 → 机器执行代码
```

工程师的输出物从**代码**变成**约束系统**。Agent = Model + Harness，Harness = 模型之外的一切。

#### Böckeler 2×2 矩阵（最具操作性的框架）

|  | 计算性（确定性，CPU） | 推理性（语义，LLM） |
|--|---------|---------|
| **引导器（前馈）** | bootstrap 脚本、schema 校验、AST 分析 | AGENTS.md、SOP、architecture.md |
| **传感器（反馈）** | linter、类型检查、覆盖率、结构测试 | LLM-as-judge、独立 Evaluator |

- 引导器：行动前引导，增加首次成功概率
- 传感器：行动后观察，启用自我纠正
- 两者缺一不可

#### Anthropic 三智能体架构（GAN 启发）

```
Planner（1-4 句提示 → 完整规格）
    → Generator（按 Sprint 实现）
    → Evaluator（Playwright 实操验证，逐条核查 Sprint 合同）
```

关键机制：**Sprint 合同** —— Generator 和 Evaluator 在开始前**协商**完成标准。解决了"spec 太高层 → 不可验证"的 gap。

演化数据：V1 Harness（Opus 4.5，$200，6h）→ V2 Harness（Opus 4.6，$125，4h）—— 模型升级后 harness 必须瘦身。

#### Ralph Loop 帽子系统

| 迭代 | 角色 | 职责 |
|------|------|------|
| 1 | Planner | 分析任务 → 写 scratchpad |
| 2 | Builder | TDD + 实现 + 自愈 |
| 3 | Critic | 独立重跑 + 手动验证 |
| 4 | Finalizer | 确认完成 → `LOOP_COMPLETE` |

核心原则："磁盘是状态，Git 是记忆"。

#### 六大关键洞见

1. **仓库即记录系统**：不在 repo 里的东西对 agent 不存在
2. **地图而非手册**：AGENTS.md ≤ 60 行，渐进式披露
3. **机械化执行**：lint 错误信息内嵌修复指令 → agent 自我纠正闭环
4. **Harness 有生命周期**：每次模型升级必须压测，去掉死重
5. **行为正确性是房间里的大象**：结构/架构 harness 成熟，功能正确性验证仍无可靠答案
6. **先找真正的瓶颈**：约束理论视角——提升非瓶颈环节对整体吞吐量无影响

### 3.2 Claude Code 架构模式（来源：claude-code-instructkr）

#### ToolSearch 延迟加载（最重要架构创新）

每个工具有 `searchHint`（3-10 词能力摘要）。初始请求只加载常用工具完整 schema，不常用工具以名称列表出现在 `system-reminder` 中，模型按需调用 `ToolSearch` 获取 schema。

**解决的问题**：工具 schema 占系统提示 50%+ input tokens 的膨胀问题。

**对 Doramagic 的映射**：200+ 种子积木 → 500+ 积木规模下的上下文窗口爆炸。

#### 系统提示词 静态/动态 分层

```
═══ 静态层（cacheScope: 'global'，所有用户共享）═══
七段通用指令...
══ SYSTEM_PROMPT_DYNAMIC_BOUNDARY ══
═══ 动态层（cacheScope: null，不缓存）═══
Session / Memory / Environment / Language...
```

**关键洞察**：boundary 之前每增加一个条件分支，全局缓存变体数翻倍（2^N 问题）。

#### system-reminder 动态注入

不修改 system prompt 本体、不破坏 prompt cache，通过 `<system-reminder>` 标签向模型注入新上下文。预先在系统提示中建立信任基础。

#### 5 层上下文防线

```
Layer 0: 大结果存磁盘（>50K chars），只传 2KB 预览
Layer 1: 微压缩 — LRU 清除旧工具结果，只保留最近 5 个
Layer 2: Auto-Compact — token 超阈值时全量摘要
Layer 3: Manual /compact
Layer 4: Reactive Compact — 413 错误后紧急截断
```

微压缩核心原则：**只清除可再生内容**（File Read、Shell 结果），不清除用户输入（不可再生）。

#### Coordinator 四阶段工作流

```
Research（Worker 并行探索）→ Synthesis（Coordinator 亲自综合）
    → Implementation（Worker 执行）→ Verification（独立 Worker 验证）
```

关键约束：**永远不写 "based on your findings"** — Coordinator 必须亲自理解再生成指令。

#### Diminishing Returns 提前停止

连续 N 次增量低于阈值时主动停止，而非继续消耗 token。对 SOUL_EXTRACT 循环估算节省 15-30% token。

#### 不可派生原则

只存储不可从当前项目状态推导的知识：用户偏好、团队教训、设计动机。代码结构、git 历史等**可派生**的不存。

#### 冻结决策不可逆转

工具结果一旦判断（替换或保留），决策在会话中不可逆转。保障 prompt cache 稳定性 + 避免重复评估。

#### 断路器模式

引入前：1,279 个会话陷入 50+ 次连续压缩失败循环，最严重单会话 3,272 次。断路器限制为 3 次。

#### 9 段式压缩摘要模板

标准化保留：Primary Request / Key Concepts / Files / Errors / Problem Solving / **All User Messages**（最关键）/ Pending Tasks / Current Work / Next Step。

---

## 四、交叉分析：三源洞察的交汇点

### 4.1 约束驱动 vs 自由探索

三个来源在同一个核心命题上汇聚：**约束越严，Agent 自主性越强**。

| 来源 | 表述 | 机制 |
|------|------|------|
| Harness Engineering | Ashby 必要多样性定律 | 拓扑约束削减解空间 → harness 变得可行 |
| Claude Code | Fail-Closed 设计 + allowlist | 默认不信任 → 显式声明安全 |
| Doramagic v5.2 | 确定性覆盖清单 + 零 LLM enrich | Coverage Manifest 约束"看什么" → LLM 只负责"理解什么" |

**洞察**：Doramagic v5.2 的演进方向（从 v3.2 的自由探索 → v5.2 的确定性覆盖）完全符合 Harness Engineering 范式。下一步应继续沿此方向，将更多"判断"从 LLM 移到确定性 harness。

### 4.2 Generator-Evaluator 分离

三个来源一致强调**生成者和评估者必须分离**：

| 来源 | 模式 | Doramagic 现状 |
|------|------|---------------|
| Harness Engineering | Generator + 独立 Evaluator（Sprint 合同） | worker_audit 不参与 Synthesis（L2） |
| Claude Code | Coordinator → Verification Worker（独立视角） | Quality Gate BQ-01~09 是确定性检查，缺 LLM-as-judge |
| Doramagic v5.2 | worker_verify 存在但 blocking=False | **评估层过弱** |

**洞察**：当前最大的结构性缺失是**独立评估层**。Quality Gate 只做格式/数量检查，不做语义正确性验证。

### 4.3 上下文管理的收敛策略

| 策略 | Claude Code 实现 | Doramagic 可用方式 |
|------|------------------|-------------------|
| 延迟加载 | ToolSearch + searchHint | 积木按需加载 + search_hint |
| 静态/动态分层 | DYNAMIC_BOUNDARY | 基础 prompt 固定 + system-reminder 注入阶段信息 |
| 微压缩 | LRU 清除可再生结果 | Worker 中工具调用结果定期清理 |
| 边际递减停止 | tokenBudget.ts | SOUL_EXTRACT 循环收敛检测 |
| 冻结决策 | seenIds 集合 | 已评估 BD 不重复推理 |

### 4.4 品味传播 vs 知识沉淀

Harness Engineering 的"品味传播路径"与 Doramagic 的知识锻造体系高度同构：

```
Harness Engineering:  审查评论 → 文档更新 → lint 规则 → 自动应用
Doramagic:            人工审查 → pitfalls.md → SOP 更新 → enrich patch → 自动应用
```

区别在于 Doramagic 的闭环还缺少 **lint 规则层**——将审查发现转化为可机械执行的检查。

### 4.5 Harness 瘦身 vs 版本膨胀

harness-engineering 仓库指出的关键风险：每个 harness 组件编码了一个"模型不能独立做 X"的假设。模型升级后必须重新压测。

Doramagic 现状：`blueprint_phases.py` 中 5 个版本（v3.2/v4/v4.1/v5/v5.2）共 3000 行共存，历史 harness 从未清理。这正是"harness 有生命周期但没人维护"的典型反模式。

---

## 五、关键技术发现总结

### 发现 1：前馈-反馈矩阵评估

用 Böckeler 2×2 矩阵评估 Doramagic 蓝图提取 agent 当前 harness 覆盖度：

|  | 计算性（确定性） | 推理性（LLM） |
|--|---------|---------|
| **引导器** | Coverage Manifest + AST 索引 + 子领域指纹 | SOP v3.4 + 20 项审计清单 + 6 类 BD 框架 + Worker Prompt |
| **传感器** | BQ-01~09 质量门 + P0-P13 enrich 归一化 | **缺失**（无独立 LLM Evaluator） |

**最大缺口**：右下角——推理性传感器。当前没有独立 agent 从 evidence packet 中验证 BD 的语义正确性。

### 发现 2：覆盖率瓶颈的根因

v5 规划书已诊断：v4.1 的根因是"LLM 同时决定看什么和理解什么"。v5.2 通过 Coverage Manifest 解决了"看什么"，但仍依赖 LLM 在 Worker 中逐文件探索。

根本解法（v5 规划书 Layer 1）——tree-sitter AST 调用图——未实现。这意味着覆盖率仍受 LLM 探索能力限制（~50-60%）。

### 发现 3：Token 效率的系统性改进空间

| 当前浪费点 | 对应的外部解法 | 预估节省 |
|-----------|--------------|---------|
| SOUL_EXTRACT 循环不检测收敛 | Diminishing Returns 提前停止 | 15-30% |
| 每个阶段重建完整 prompt | system-reminder 动态注入 | 10-20%（多 repo 连续提取场景） |
| 已评估 BD 在多步骤中重复推理 | 冻结决策不可逆转 | 5-15% |
| 全量积木注入 | searchHint + 延迟加载 | 在 500+ 积木规模下显著 |

### 发现 4：Sprint 合同机制的缺失

当前蓝图提取没有形式化的"完成协议"。Worker 输出什么、Synthesis 期望什么，全靠 Prompt 隐式约定。

Sprint 合同机制要求：提取开始前，显式声明每个 BD 的验证标准（不只是"有值"，而是"有 evidence 支撑的值"），Evaluator 用合同逐条核查。

### 发现 5：Lint 错误内嵌修复指令的即时收益

当前 Quality Gate BQ-01~09 的输出是 pass/fail + warning 消息，但消息中没有修复指令。

Harness Engineering 最佳实践：每条 lint 错误嵌入"下一步做什么"：
```
❌ 当前：BQ-03 FAIL: multi_type_ratio 0.25 < 0.30
✅ 改进：BQ-03 FAIL: multi_type_ratio 0.25 < 0.30
         Fix: Re-run worker_workflow with focus on BA/DK classification.
         Check files: {coverage_gap_dirs} for missed B/BA decisions.
```

### 发现 6：Harness 历史版本需要清理

`blueprint_phases.py` 3000 行中 5 个版本共存，是"harness 有生命周期但没人维护"的反模式。每个历史版本编码了"旧模型不能做 X"的假设，在当前模型下可能已不成立。

---

## 六、风险与约束

1. **行为正确性仍是开放问题**：Harness Engineering 社区承认，功能正确性验证（"提取的 BD 语义是否正确"）仍无可靠答案。所有改进方案都应认识到这一根本限制。

2. **过度约束的风险**：约束理论（YDD 学派）警告——如果瓶颈在人工审查而非提取速度，加速提取对整体吞吐量影响有限。应先确认真正的瓶颈。

3. **Harness 复杂度 vs 模型进化**：今天精心设计的 harness 组件，可能在下一代模型面前变成死重。设计时应考虑"可移除性"。

4. **多模型兼容性**：当前 agent 已支持 Anthropic/OpenAI/GLM-5/MiniMax 四种 API。任何架构改进必须保持此兼容性。

---

## 附录：参考文件索引

| 分类 | 文件路径 |
|------|---------|
| **Doramagic 核心实现** | |
| Phase 工厂 | `packages/extraction_agent/.../sop/blueprint_phases.py` |
| Agent 主循环 | `packages/extraction_agent/.../core/agent_loop.py` |
| SOPExecutor | `packages/extraction_agent/.../sop/executor.py` |
| 确定性 Enrich | `packages/extraction_agent/.../sop/blueprint_enrich.py` |
| Pydantic 模型 | `packages/extraction_agent/.../sop/schemas_v5.py` |
| Synthesis Prompt | `packages/extraction_agent/.../sop/prompts_v5.py` |
| 金融审计清单 | `packages/extraction_agent/.../sop/prompts.py` |
| v5 规划书 | `docs/designs/2026-04-12-blueprint-agent-v5-plan.md` |
| v5.2 确定性覆盖 | `docs/designs/2026-04-12-blueprint-agent-v5.2-deterministic-coverage.md` |
| **Claude Code 研究** | |
| 综合建议 | `docs/research/claude-code-instructkr/report/DORAMAGIC_TAKEAWAYS.md` |
| 知识总结 | `docs/research/claude-code-instructkr/KNOWLEDGE_SUMMARY.md` |
| Agent 编排 | `docs/research/claude-code-instructkr/report/04-agent-orchestration.md` |
| Prompt 工程 | `docs/research/claude-code-instructkr/report/05-prompt-engineering.md` |
| 上下文管理 | `docs/research/claude-code-instructkr/report/08-context-management.md` |
| **Harness Engineering** | |
| 仓库 | `https://github.com/deusyu/harness-engineering` |
| 交叉分析 | `thinking/cross-article-insights.md`（仓库内） |
| 文章索引 | `references/articles.md`（仓库内） |
| Ralph 实验 | `practice/01-ralph-demo/`（仓库内） |
