# Harness Engineering 深度研究报告

**日期**: 2026-04-06  
**作者**: Codex（基于公开论文、官方工程文档与产品资料综合研究）  
**研究目标**: 系统梳理 harness engineering 的最新技术动向，并提炼对 Doramagic 的可执行启示

---

## 摘要

2025-2026 年，AI agent 领域最重要的工程迁移之一，不是“prompt 更长”或“模型更大”，而是**把决定 agent 成败的控制层从隐式代码与零散经验中抽离出来，变成可设计、可验证、可迁移、可观测的 harness**。  

如果用一句话概括：

**harness engineering = 针对 agent 的运行环境、工具边界、状态持久化、任务契约、验证回路、评测体系与恢复机制进行系统化工程设计。**

当前前沿已经出现三条清晰主线：

1. **学术主线**: 把 harness 视为独立研究对象，而不是 controller 里的实现细节。
2. **工程主线**: 从“大一统 prompt”转向“显式 contract + durable state + eval flywheel + observability”。
3. **产品主线**: 顶级 AI 产品竞争焦点，正在从“模型会不会写代码”转向“产品有没有强 harness 层保证可靠性、并发性、可回放性和可治理性”。

对 Doramagic 的核心判断是：

**Doramagic 不应继续把执行控制逻辑埋在提示词、约束条目和零散脚本中，而应升级为“合同化、阶段化、可回放、可评测”的 harness-first 架构。**

---

## 1. 什么是 Harness Engineering

在现代 agent 系统中，模型本体已经不再是唯一关键变量。越来越多的结果差异来自模型外层的控制系统，即 harness。它通常负责：

- 任务分解与阶段推进
- 工具选择与调用约束
- 状态持久化与恢复
- 输入输出契约
- 验收与验证
- 失败分类与重试
- 运行时权限与治理
- 观测、评测与回归分析

因此，harness engineering 不是传统意义上的 test harness 单点技术，而是一整套围绕 agent 可靠性的工程学。

---

## 2. 最新技术动向总判断

截至 2026 年 4 月，harness engineering 的主流趋势可以概括为七点：

1. **从 prompt engineering 迁移到 harness engineering**  
   顶级团队不再把问题理解为“提示词再优化一点”，而是把重点放到环境、工具、状态、评测和恢复闭环。

2. **从隐式 controller 迁移到显式 harness artifact**  
   最新论文已经开始把 harness 外显为可移植工件，而不是藏在代码里。

3. **从一次性任务执行迁移到 durable execution**  
   长任务、后台任务、人机协作、多 agent 并发都要求中断恢复与状态持久化。

4. **从静态 benchmark 迁移到持续评测与污染防御**  
   评测框架必须考虑 contamination、环境漂移、reward 设计漏洞与评测失真。

5. **从工具可调用迁移到工具可用**  
   是否“有工具”已经不重要，关键是工具描述、命名、返回结构、token 成本和错误语义是否适合 agent。

6. **从黑盒运行迁移到 trace-native observability**  
   只有把 tool call、状态转移、失败点、验证结果和人类干预都纳入 trace，工程迭代才可闭环。

7. **从单 agent 能力竞争迁移到 harness productization**  
   Codex、Claude Code、Devin、LangSmith、Braintrust、Phoenix 等产品的真正分野，越来越体现在 harness 层。

---

## 3. 顶尖论文梳理

下面分为两类：

- **直接研究 harness engineering 的核心论文**
- **构成 harness engineering 基础设施的关键关联论文**

### 3.1 直接核心论文

#### 3.1.1 Natural-Language Agent Harnesses (NLAH, 2026)

- **链接**: [arXiv:2603.25723](https://arxiv.org/abs/2603.25723)
- **地位判断**: 这是目前最直接、最明确把 harness engineering 作为研究对象提出的代表作。
- **核心贡献**:
  - 明确提出 harness 是影响 agent 表现的关键层，而不仅是 controller 实现细节
  - 提出 **Natural-Language Agent Harnesses (NLAHs)**，将 harness 写成可编辑自然语言工件
  - 提出 **Intelligent Harness Runtime (IHR)**，把 harness 语义与运行时执行隔离
  - 在 coding 与 computer-use 场景做了模块消融、runtime/harness 分离和 code-to-text migration
- **关键启示**:
  - harness 可以被版本化、比较、迁移和消融
  - 真正有效的 harness 模块不是越多越好，而是与验收目标对齐的模块
  - file-backed state、evidence-backed validation、explicit verifier 等模块通常比“更复杂的搜索结构”更稳定
- **对 Doramagic 的意义**:
  - Doramagic 已经有 blueprint、constraint、skill、script 等资产，但缺少显式 harness 对象
  - 未来应把执行控制层抽离为可声明、可组合、可验证的 artifact，而不是继续依赖超长 prompt 拼装

#### 3.1.2 Establishing Best Practices for Building Rigorous Agentic Benchmarks (ABC, 2025)

- **链接**: [arXiv:2507.02825](https://arxiv.org/abs/2507.02825)
- **地位判断**: 这是 harness engineering 评测方法论上的关键论文。
- **核心贡献**:
  - 提出 **Agentic Benchmark Checklist (ABC)**
  - 指出大量 agent benchmark 存在 task validity 和 outcome validity 问题
  - 明确指出 SWE-bench Verified、TAU-bench 等流行 benchmark 也可能高估或低估真实性能
  - 在 CVE-Bench 上把性能高估降低了 33%
- **关键启示**:
  - 没有 rigorous benchmark，任何 harness 优化都可能建立在假收益上
  - harness engineering 不是只做 runtime，更要做 benchmark hygiene
- **对 Doramagic 的意义**:
  - Doramagic 若要做 crystal/harness 迭代，必须同步设计 benchmark validity 机制
  - 不能只看 pass rate，还要看任务定义是否真实、验收逻辑是否可靠

#### 3.1.3 MCPEval: Automatic MCP-based Deep Evaluation for AI Agent Models (2025)

- **链接**: [arXiv:2507.12806](https://arxiv.org/abs/2507.12806)
- **地位判断**: 最新一代自动化 agent evaluation framework 代表。
- **核心贡献**:
  - 基于 MCP 做端到端任务生成与深度评测
  - 不只看最终成功率，还分析 tool call correctness、planning、execution flow
  - 把 evaluation pipeline 标准化
- **关键启示**:
  - harness engineering 已经开始从“写 agent”转向“自动评 agent”
  - 深度评测的粒度必须下沉到工具调用与执行轨迹层
- **对 Doramagic 的意义**:
  - Doramagic 的后续 harness 平台不应只有 run log，而应有结构化深评测输出

### 3.2 关键关联论文

#### 3.2.1 OSWorld: Benchmarking Multimodal Agents for Open-Ended Tasks in Real Computer Environments (2024)

- **链接**: [arXiv:2404.07972](https://arxiv.org/abs/2404.07972)
- **为什么重要**:
  - 把真实计算机环境、初始状态配置与 execution-based evaluation 结合起来
  - 证明真实开放环境下，agent 的执行闭环远比静态 QA 难
- **对 harness engineering 的贡献**:
  - 强化了“环境 + 评测脚本 + 状态配置”本身就是 harness 组成部分

#### 3.2.2 SWE-bench (2023) 与 SWE-bench Verified

- **链接**: [arXiv:2310.06770](https://arxiv.org/abs/2310.06770)  
- **链接**: [SWE-bench Verified](https://www.swebench.com/verified.html)
- **为什么重要**:
  - 把真实软件问题修复变成可执行 benchmark
  - Verified 进一步引入人工验证，提升可靠性
- **对 harness engineering 的贡献**:
  - coding agent 的 harness 必须兼顾代码理解、测试执行、补丁生成与验收
  - 但 Verified 也暴露出 benchmark 设计本身仍可能失真

#### 3.2.3 SWE-rebench (2025)

- **链接**: [arXiv:2505.20411](https://arxiv.org/abs/2505.20411)
- **为什么重要**:
  - 针对 SWE-bench 污染与新鲜度问题，提出持续采集与去污染评测流水线
- **对 harness engineering 的贡献**:
  - 真正面向生产的 harness 优化必须建立在“持续新样本”上，而不是固定 leaderboard

#### 3.2.4 MCP-Bench (2025)

- **链接**: [arXiv:2508.20453](https://arxiv.org/abs/2508.20453)
- **为什么重要**:
  - 把多步工具使用、跨工具协调、参数精度控制和现实工具空间放到同一 benchmark
- **对 harness engineering 的贡献**:
  - 证明工具生态时代，harness 的瓶颈是 tool coordination，而不只是单工具调用

#### 3.2.5 MCP-Universe (2025)

- **链接**: [arXiv:2508.14704](https://arxiv.org/abs/2508.14704)
- **为什么重要**:
  - 直接在真实 MCP servers 上评估 LLM 的长程推理和陌生工具空间适应
- **对 harness engineering 的贡献**:
  - 进一步推动 harness 从“静态工具调用模板”进化为“开放工具宇宙中的动态控制系统”

---

## 4. 顶尖工程实践

这一部分重点看官方工程文章和产品文档，因为真正领先的 harness engineering 目前主要发生在顶级团队的产品化实践中。

### 4.1 OpenAI：Harness Engineering 进入主舞台

- **链接**: [Harness engineering: leveraging Codex in an agent-first world](https://openai.com/index/harness-engineering/)

OpenAI 在 2026 年 2 月明确提出：工程师的主要工作正在从“亲手写代码”迁移到“设计 agent 可执行的环境、意图表达和反馈闭环”。

这篇文章最重要的实践结论有六个：

1. **仓库知识必须 repo-native**  
   不是给 agent 一份超长 `AGENTS.md`，而是给一个简短目录入口，真正知识放在结构化 docs 中。

2. **progressive disclosure 优于 monolithic instruction**  
   agent 应该按需展开上下文，而不是一开始塞进整本手册。

3. **agent legibility 是第一目标**  
   架构、文档、日志、指标、UI 都要变成 agent 可读对象。

4. **环境可执行性比 prompt 修辞更关键**  
   worktree、浏览器控制、logs、metrics、trace 等基础设施直接决定 agent 是否真能闭环。

5. **文档维护要机械化**  
   需要 lint、CI 和 doc-gardening agent 抑制知识漂移。

6. **merge philosophy 会因高吞吐 agent 而改变**  
   agent 吞吐极高时，过重的人类阻塞门槛会成为系统瓶颈。

**判断**: OpenAI 这篇文章基本标志着 harness engineering 从隐性经验上升为显性工程范式。

### 4.2 Anthropic：Simple Patterns + Tool Ergonomics + Eval-driven Iteration

- **链接**: [Building effective agents](https://www.anthropic.com/research/building-effective-agents)
- **链接**: [Building agents with the Claude Agent SDK](https://www.anthropic.com/engineering/building-agents-with-the-claude-agent-sdk)
- **链接**: [Writing effective tools for agents](https://www.anthropic.com/engineering/writing-tools-for-agents)

Anthropic 的实践特别重要，因为它把 harness engineering 拆解成三层：

1. **架构层**: 优先简单、可组合的 workflow，不要过早上复杂框架  
2. **运行层**: 给 agent 一台“计算机”，让它像人一样使用 terminal、file system、browser、scripts  
3. **工具层**: 工具的命名、边界、描述、返回内容和 token 成本都直接影响 agent 成功率

Anthropic 最有价值的工程结论是：

- 更多工具不一定更好
- overlapping tools 会让 agent 迷失
- namespacing 有真实效果
- tool response 应返回高信号上下文，而不是低层技术细节
- tool description 本身需要像 prompt 一样被系统优化
- eval 不是上线后补做，而是设计工具时就要内嵌

**判断**: Anthropic 把 harness engineering 的底层事实讲得很清楚: agent 失败常常不是“模型不会”，而是“工具和环境被设计得不适合 agent 使用”。 

### 4.3 LangChain / LangSmith：Durable Execution 走向平台化

- **链接**: [LangGraph Durable Execution](https://docs.langchain.com/oss/javascript/langgraph/durable-execution)
- **链接**: [LangSmith Deployment](https://docs.langchain.com/langsmith/deployments)
- **链接**: [LangSmith Observability](https://docs.langchain.com/oss/python/langchain/observability)

LangChain 体系的贡献，在于把 harness engineering 中最难产品化的一层做成了平台：

- long-running stateful execution
- persistence / checkpointing
- human-in-the-loop pause/resume
- replay consistency
- tracing
- deployment runtime

其中最关键的是 **durable execution** 概念：  
agent 任务不是“一次函数调用”，而是可能跨分钟、跨小时、跨人类审批、跨进程恢复的长事务。

**判断**: durable execution 已经不是高级选项，而是 harness 工程进入生产环境的基础能力。

### 4.4 Braintrust / Phoenix：Trace + Eval 的双轮闭环

- **链接**: [Braintrust home](https://www.braintrust.dev/)
- **链接**: [Braintrust evals guide](https://www.braintrust.dev/docs/guides/evals)
- **链接**: [Braintrust traces guide](https://www.braintrust.dev/docs/guides/traces)
- **链接**: [Phoenix overview](https://arize.com/docs/phoenix)
- **链接**: [Phoenix evaluation](https://arize.com/docs/phoenix/evaluation/llm-evals)

Braintrust 与 Phoenix 代表的是另一条产品化方向：

- 不做主执行 runtime
- 重点做 trace、experiments、scoring、monitoring、prompt iteration

这类产品证明了 harness engineering 的另一个核心事实：

**没有 trace，就没有可诊断性；没有 eval，就没有可迭代性。**

从工程上看，这一类最佳实践通常包含：

- 统一 trace schema
- 离线 eval 与在线 scoring 共享 scorer
- diff / regression analysis
- 生产日志反哺测试集
- LLM judge、code judge、human label 组合

**判断**: 未来成熟 harness 平台不会只提供“运行 agent”的能力，而会同时提供“观察、评分、比较、回归”的证据系统。

---

## 5. 顶尖 AI 产品图谱

这里的“顶尖产品”不是单纯看热度，而是看它们是否把 harness engineering 产品化。

### 5.1 OpenAI Codex

- **链接**: [Codex product page](https://openai.com/codex/)
- **链接**: [Introducing Codex](https://openai.com/index/introducing-codex/)
- **链接**: [Introducing the Codex app](https://openai.com/index/introducing-the-codex-app/)

**为什么是顶级产品**:

- 多 agent 并行工作
- worktree / cloud sandbox 隔离
- skills、automations、reviews、background work
- 本质上把 coding harness 做成了操作系统级产品能力

**核心 harness 特征**:

- isolated environment
- parallel task execution
- repo-specific skills
- approval and review loops
- background automations

**判断**: Codex 代表的是“把 harness 直接变成产品主界面”的路线。

### 5.2 Anthropic Claude Code / Claude Agent SDK

- **链接**: [Claude Code product page](https://www.anthropic.com/product/claude-code)
- **链接**: [Claude Code overview](https://docs.anthropic.com/en/docs/claude-code/overview)
- **链接**: [Claude Agent SDK](https://www.anthropic.com/engineering/building-agents-with-the-claude-agent-sdk)

**为什么是顶级产品**:

- 以 terminal-native agent 作为基础交互模型
- 支持 file、bash、search、browser 等通用执行面
- 把 Claude Code 背后的 harness 抽象成 Claude Agent SDK

**核心 harness 特征**:

- “给 agent 一台计算机”
- 以工具为基本执行原语
- 可复用的 agent loop
- 支持非编码任务扩展

**判断**: Anthropic 路线比 OpenAI 更强调“通用 agent harness primitives”。

### 5.3 Devin

- **链接**: [Introducing Devin](https://docs.devin.ai/)
- **链接**: [Devin SDLC integration](https://docs.devin.ai/essential-guidelines/sdlc-integration)
- **链接**: [Devin advanced capabilities](https://docs.devin.ai/enterprise/features/advanced-mode)

**为什么是顶级产品**:

- 长任务执行
- PR 驱动集成
- 并行 managed sessions
- playbook / knowledge / session analysis 等组织化能力

**核心 harness 特征**:

- workspace with shell + IDE + browser
- managed parallel sessions
- knowledge onboarding
- playbook extraction
- 与现有 SDLC 对齐

**判断**: Devin 代表“团队级代理工程工位”，把 harness 延伸到组织流程层。

### 5.4 LangSmith

- **链接**: [LangSmith home](https://www.langchain.com/)
- **链接**: [LangSmith Deployment](https://www.langchain.com/langsmith/deployment)

**为什么是顶级产品**:

- 把 observability、evaluation、deployment、durable runtime 放进同一产品体系
- 明确面向 production agent workloads

**核心 harness 特征**:

- durable runtime
- message/thread state
- human-in-the-loop
- deployment governance
- tracing + evaluation 联动

**判断**: LangSmith 是“agent 平台基础设施”路线的代表。

### 5.5 Braintrust

- **链接**: [Braintrust home](https://www.braintrust.dev/)

**为什么是顶级产品**:

- eval-first 心智模型非常清晰
- dataset / task / score 三元结构非常适合工程团队协作
- 强调从 production traces 反哺 eval

**判断**: Braintrust 在 harness engineering 中代表“以评测闭环驱动工程迭代”的路线。

### 5.6 Phoenix

- **链接**: [Phoenix home](https://phoenix.arize.com/)
- **链接**: [Phoenix docs](https://arize.com/docs/phoenix)

**为什么是顶级产品**:

- 开源
- OTEL / OpenInference 兼容
- tracing、prompt playground、evaluation、datasets、experiments 一体化

**判断**: Phoenix 在 harness engineering 中代表“开放可组合 observability/eval substrate”。

---

## 6. 综合判断：哪些是“真趋势”，哪些只是噪音

### 6.1 真趋势

- **显式 contract** 会替代大量模糊 prose instruction
- **durable state** 会成为长任务 agent 的标配
- **trace + eval 一体化** 会成为生产 agent 的最低配
- **tool ergonomics** 会成为高杠杆优化点
- **multi-agent orchestration** 会继续扩张，但必须建立在强 contract 和隔离之上
- **benchmark hygiene** 会成为下一阶段关键竞争力

### 6.2 需要警惕的噪音

- 把 harness 理解为“更长的提示词模板”
- 把复杂 orchestrator 当作默认最优解
- 只看 leaderboard 不看 benchmark validity
- 只做 runtime，不做 trace/eval
- 只做 prompt，不做 tool / state / environment redesign

---

## 7. 对 Doramagic 的战略建议

### 7.1 总体判断

Doramagic 当前最适合的方向，不是照搬某一家产品，也不是全盘复制 NLAH/IHR，而是建立 **轻量、显式、可验证的 harness layer**。

建议采用的设计原则：

- **薄层 harness**，不要吞掉 blueprint / constraint / domain knowledge
- **声明式 contract + 程序化 enforcement** 的混合模式
- **file-backed state** 先落地，再谈更复杂 orchestration
- **benchmark + trace + eval** 与 runtime 同步建设

### 7.2 P0：建议立即建设的 6 个对象

1. **Execution Contract**
   - 输入制品
   - 目标输出
   - 必做校验
   - 失败条件
   - 停止条件

2. **Stage Spec**
   - prepare
   - execute
   - verify
   - repair
   - deliver

3. **Artifact-backed State**
   - plan file
   - working memory file
   - evidence file
   - result manifest

4. **Failure Taxonomy**
   - missing_input
   - invalid_output
   - tool_error
   - environment_error
   - spec_violation
   - verification_failure

5. **Harness Trace Schema**
   - stage transition
   - tool call
   - artifact emission
   - validation result
   - retry reason

6. **Eval Pack**
   - happy path
   - edge case
   - failure recovery case
   - contamination guard case

### 7.3 P1：一个月内应补齐的能力

- 把现有 blueprint / constraint 编译成 contract-friendly 结构
- 建立 harness ablation 实验能力
- 为关键工具加 agent-friendly 描述与 namespacing
- 建立 docs lint / freshness check / indexing
- 把运行日志升级成结构化 trace

### 7.4 P2：中期演进方向

- 研究 Doramagic 自己的 natural-language harness format
- 研究 benchmark mutation 与 contamination-aware eval
- 研究面向多 host / 多 runtime 的 harness portability
- 研究 harness 搜索与自动调参

---

## 8. 最终结论

harness engineering 不是边缘术语，而是在 2026 年已经逐步成型的 agent 工程主范式。

它的真正含义不是“怎么包住模型”，而是：

**怎么把 agent 的执行控制层做成一个可设计、可验证、可恢复、可比较、可治理的工程系统。**

从论文看，NLAH/IHR 已经把 harness 从“隐性经验”提升为“研究对象”；  
从工程实践看，OpenAI 与 Anthropic 已经把 harness 作为一线工程能力；  
从产品看，Codex、Claude Code、Devin、LangSmith、Braintrust、Phoenix 已经把 harness 的不同切面做成了商品化能力。

对 Doramagic 而言，最关键的不是“是否追随 harness 热潮”，而是要尽快完成一个架构转向：

**从 prompt/constraint 驱动的隐式执行，转向 contract/state/eval 驱动的显式 harness 执行。**

这将直接决定 Doramagic 后续是否能从“能跑的 agent 系统”升级为“可持续进化的 agent 工程平台”。

---

## 参考资料

### 论文

- Natural-Language Agent Harnesses: https://arxiv.org/abs/2603.25723
- Establishing Best Practices for Building Rigorous Agentic Benchmarks: https://arxiv.org/abs/2507.02825
- MCPEval: Automatic MCP-based Deep Evaluation for AI Agent Models: https://arxiv.org/abs/2507.12806
- OSWorld: Benchmarking Multimodal Agents for Open-Ended Tasks in Real Computer Environments: https://arxiv.org/abs/2404.07972
- SWE-bench: Can Language Models Resolve Real-World GitHub Issues?: https://arxiv.org/abs/2310.06770
- SWE-rebench: An Automated Pipeline for Task Collection and Decontaminated Evaluation of Software Engineering Agents: https://arxiv.org/abs/2505.20411
- MCP-Bench: Benchmarking Tool-Using LLM Agents with Complex Real-World Tasks via MCP Servers: https://arxiv.org/abs/2508.20453
- MCP-Universe: Benchmarking Large Language Models with Real-World Model Context Protocol Servers: https://arxiv.org/abs/2508.14704

### 官方工程实践与产品资料

- OpenAI, Harness engineering: leveraging Codex in an agent-first world: https://openai.com/index/harness-engineering/
- OpenAI, Introducing Codex: https://openai.com/index/introducing-codex/
- OpenAI, Introducing the Codex app: https://openai.com/index/introducing-the-codex-app/
- OpenAI, Codex product page: https://openai.com/codex/
- Anthropic, Building effective agents: https://www.anthropic.com/research/building-effective-agents
- Anthropic, Building agents with the Claude Agent SDK: https://www.anthropic.com/engineering/building-agents-with-the-claude-agent-sdk
- Anthropic, Writing effective tools for agents: https://www.anthropic.com/engineering/writing-tools-for-agents
- Anthropic, Claude Code product page: https://www.anthropic.com/product/claude-code
- Anthropic, Claude Code overview: https://docs.anthropic.com/en/docs/claude-code/overview
- LangChain, LangGraph durable execution: https://docs.langchain.com/oss/javascript/langgraph/durable-execution
- LangChain, LangSmith Deployment: https://docs.langchain.com/langsmith/deployments
- LangChain, LangSmith Observability: https://docs.langchain.com/oss/python/langchain/observability
- Braintrust home: https://www.braintrust.dev/
- Braintrust evals guide: https://www.braintrust.dev/docs/guides/evals
- Braintrust traces guide: https://www.braintrust.dev/docs/guides/traces
- Phoenix home: https://phoenix.arize.com/
- Phoenix docs overview: https://arize.com/docs/phoenix
- Phoenix evaluation: https://arize.com/docs/phoenix/evaluation/llm-evals
- Devin docs: https://docs.devin.ai/
- Devin SDLC integration: https://docs.devin.ai/essential-guidelines/sdlc-integration
- Devin advanced capabilities: https://docs.devin.ai/enterprise/features/advanced-mode
