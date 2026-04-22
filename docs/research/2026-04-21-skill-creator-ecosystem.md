# Skill Creator Ecosystem Research
> Date: 2026-04-21
> Author: Research Agent (sonnet-4-6)
> Trigger: CEO question — "几乎任何 AI agent 系统都有 skill creator，人们是如何利用这个来创建 skill 的？"
> Decision context: Doramagic 在产业链中的正确切入层级

---

## 核心发现：SKILL.md 已成行业统一格式

**2025 年 12 月 Anthropic 以 agentskills.io 发布 Agent Skills 开放标准（Apache 2.0 + CC-BY-4.0），数日内 OpenAI、Microsoft、Cursor、Amp、Goose 全部跟进，采用了结构相同的 SKILL.md 格式。**

这一发现改变了问题本身——不是"7 个系统各有各的格式"，而是"7 个系统现在共用一个格式，只是 skill creator 工具的成熟度不同"。

---

## 一、7 大系统 Skill Creator 总表

| 系统 | Skill 原生格式 | Skill Creator 类型 | Creator 吃什么输入 | 用户创建流程 | seed.yaml 塞进去会怎样 | 跨平台可移植性 |
|------|--------------|-------------------|-------------------|------------|----------------------|--------------|
| **Anthropic Claude Code** | `SKILL.md` 文件夹（agentskills.io 标准）| **LLM 辅助 meta-skill** (`skill-creator` skill) | 自然语言描述 → 面谈式采集 → 生成 SKILL.md | 1. 安装 skill-creator skill；2. `/skill-creator` 触发；3. Creator 问你"做什么/何时触发/要不要脚本"；4. 生成目录 + SKILL.md；5. eval 测试迭代 | 可作为 `references/seed.yaml` 放进 skill 文件夹，Creator **不会语义解析它**，但 Claude 可在被 SKILL.md 指引时主动读取；效果取决于 SKILL.md 里是否有"读取 seed.yaml" 的指令 | **极高** — 同一 SKILL.md 在 Claude Code / OpenAI Codex / VS Code Copilot / Cursor / ClawHub 均可用 |
| **Claude.ai** | 同 Claude Code（SKILL.md zip 上传）| **Web UI 上传** + "Start in Create + prompt" | 自然语言描述（ChatGPT/Claude 辅助起草）或直接上传 zip | 1. Settings > Customize > Skills；2. `+` > Create skill；3. 上传 zip（内含 `skill-name/SKILL.md`）；4. 激活 | 同上，seed.yaml 可作为 zip 内附件捆绑进 skill 文件夹，Claude.ai 不自动解析，SKILL.md 必须显式引用它 | 高（与 Claude Code、API 同标准，但 Claude.ai 技能不自动同步到 API） |
| **openclaw / ClawHub** | SKILL.md 文件夹（agentskills.io 标准）| **CLI `clawhub publish`** + community 贡献 | 手工编写或 LLM 生成 SKILL.md；`clawhub skill publish <path>` 发布 | 1. 写好 `skill-name/SKILL.md`；2. `clawhub skill publish <path>` 发布到 ClawHub；3. 用户 `clawhub install <slug>` 安装 | seed.yaml 可作为 `references/` 内文件捆绑；ClawHub **会托管任意文件类型**，但不解析其内容；SKILL.md 必须显式引用 | **完全兼容** — ClawHub 是 agentskills.io 标准最早的社区注册表，13,729+ skills |
| **OpenAI GPT Builder** | GPT Config（名称+说明+自定义指令+Knowledge files+Actions）| **Web 表单 + LLM 辅助**（"Create"标签页对话式配置）| 自然语言需求；最终写入 `instructions` 字段（≤8000 字符）；Knowledge 为上传文件 | 1. ChatGPT > Explore GPTs > Create；2. Create 标签页描述目标，GPT Builder 自动起草 instructions；3. Configure 标签页精调；4. 上传 Knowledge files（≤20 files, ≤512MB 每文件）；5. 发布 | seed.yaml 可作为 **Knowledge file 上传**（GPT 支持大多数文本/代码文件类型）；LLM 视其为**不透明知识文档**进行 RAG 检索，**不会按 seed.yaml 结构执行协议**；`execution_protocol`/`preconditions` 等字段被当作普通文本 | **零** — GPT Config 格式私有，无跨平台路径 |
| **OpenAI Assistants API / Responses API** | 无 "skill" 原生格式；能力来自 Functions（JSON Schema）+ File Search（向量存储）| **代码/SDK** 定义（Python/Node）| 开发者手写 JSON Schema function def；File Search 用上传文件 | 1. 创建 Assistant，定义 tools（functions 数组 + file_search）；2. 上传文件到 vector store；3. 运行 thread；（Assistants API 已弃用，2026-08 关闭，迁移到 Responses API）| seed.yaml 可上传到 vector store 作为检索文档；**被当作纯文本 RAG**，不会执行任何协议字段 | **零** — 无跨平台格式 |
| **Cursor** | `.cursor/rules/*.mdc`（MDC 格式 = YAML frontmatter + Markdown）| **轻量 web 生成工具**（cursorrules.org、cursor.directory/generate、`/Generate Cursor Rules` 命令）；本质是**手工编写** | 自然语言描述 → 生成 `.mdc` 文件内容；`/Generate Cursor Rules` 对话命令已在部分版本消失 | 1. 在 `.cursor/rules/` 下创建 `rule-name.mdc`；2. 写入 frontmatter（description/globs/alwaysApply）+ Markdown 规则体；3. 版本控制提交即生效 | seed.yaml 内容**可以 paste 进 `.mdc` 文件体**，但 Cursor 不读取结构——所有内容被当作 prompt 注入；seed.yaml 的 YAML 嵌套结构对 Cursor 而言是无差别文本；实用性取决于 MDC 规则里对内容的编排 | **中** — MDC ≈ agentskills.io 子集，但 Cursor 尚未正式宣布完全兼容；Cursor 支持 `SKILL.md` 文件（forum 有确认），未来收敛概率高 |
| **Microsoft Semantic Kernel** | **代码插件**（C#/Python/Java `@KernelFunction` 注解）+ Prompt YAML（semantic function）+ OpenAPI spec + MCP Server | **无 skill creator**；开发者手写代码/YAML | 代码 class + 注解；或 `function.yaml`（prompt + config）；或 OpenAPI spec | 1. 定义 plugin class，方法加 `@kernel_function` 注解 + `Description`；2. `kernel.add_plugin(MyPlugin())` 注册；3. 调用 `kernel.invoke()` 或启用 `FunctionChoiceBehavior.Auto()` | seed.yaml 与 SK 的 Prompt Function YAML **格式完全不同**（SK 要求 `template`/`execution_settings`，没有 Doramagic 的 `preconditions`/`evidence_quality` 等字段）；直接使用**不被识别**；需手动改写为 SK 的 prompt YAML 或 native function | **低** — SK plugin 是工程代码，不是知识文件；跨平台需通过 OpenAPI spec 或 MCP |

---

## 二、关键共性与差异

### 共性

1. **SKILL.md 格式已胜出**。6/7 个系统（Claude Code、Claude.ai、ClawHub、ChatGPT Skills、OpenAI Codex、VS Code Copilot）现在使用同一格式，Cursor 趋同中。唯一例外是 Semantic Kernel（工程 SDK，非知识注入工具）和旧 GPT Builder（私有格式）。

2. **Skill creator 的核心功能**：无论形态如何（LLM 对话、CLI、Web 表单），creator 都在做同一件事：
   - 采集意图（你想让 AI 做什么）
   - 生成触发器描述（`description` 字段，决定 AI 何时加载这个 skill）
   - 产出 SKILL.md + 可选支撑文件

3. **Knowledge file ≠ Skill**：GPT Builder 的 Knowledge file 是 RAG 文档，不是 skill；Skill 必须有可执行的 `SKILL.md` 才能改变 AI 行为。

4. **Seed.yaml 在所有 creator 里都是外来户**：没有任何 creator 原生解析 Doramagic seed.yaml 格式——它们最多把 seed.yaml 当作文本知识文件，不执行其中的协议字段。

### 差异

| 维度 | Claude Code / ClawHub | GPT Builder | SK |
|------|----------------------|-------------|-----|
| Creator 形态 | meta-skill（AI 辅助） | Web 表单（AI 辅助） | 无（手写代码） |
| 目标用户 | 开发者 + 高级用户 | 普通用户 | 企业开发者 |
| 格式锁定 | 开放标准（可迁移） | 私有（不可迁移） | 开放但强依赖 SDK |
| 知识注入方式 | 指令注入（SKILL.md） | RAG（Knowledge files）+ 指令（instructions） | 函数调用（code） |

---

## 三、Q1 — Doramagic 三种定位的优劣

### (a) Skill 产出者 — 直接产各 host 原生 skill

**含义**：Doramagic 对每个 host 各维护一个版本（openclaw-skill.zip, chatgpt-knowledge.zip, cursor-rules.mdc...）

**事实约束**：
- GPT Builder 和 SK 格式私有且差异大，需要持续多版本维护
- SKILL.md 统一后，Claude Code / Codex / ClawHub / Copilot 可以**一份文件全兼容**，维护成本骤降
- 但 seed.yaml → SKILL.md 的转换需要 Doramagic 自己做，且每次晶体更新都要重新转换

**结论**：对已统一的平台（Claude/OpenAI/Cursor）这条路成立，成本可接受；对 SK 和旧 GPT 不划算。

---

### (b) Skill creator 的输入源 — 产通用 seed.yaml，用户导入到各 creator

**含义**：Doramagic 交付 seed.yaml，用户自己拿去告诉 skill-creator "按这个给我生成 skill"

**事实约束**：
- seed.yaml 不是任何 creator 的原生输入格式
- 用户必须手动告知 creator "这是一个知识文件，请据此生成 SKILL.md"——成功率取决于 creator 的智能程度
- Anthropic skill-creator 可以接受 "draft skill files for iteration" 作为输入，这意味着**理论上可行**：用户上传 seed.yaml 并说"基于这个生成 SKILL.md"
- 但这条路的用户体验极差：seed.yaml 的结构对普通用户是黑盒，他们不知道如何描述给 creator

**结论**：技术上可行但用户体验糟糕；会产生大量摩擦，不符合"给他工具不教他做事"的产品灵魂。

---

### (c) Doramagic 自己是 skill creator — 用户输入需求 → 选晶体 → 输出 SKILL.md

**含义**：Doramagic.ai 作为服务：用户描述需求 → 匹配 seed.yaml → 编译成目标 host 的 SKILL.md → 直接可安装

**事实约束**：
- 目前**没有大玩家占据"seed → SKILL.md 自动编译器"这个精确位置**
- 产品宪法 §2.2 已提到"适配渠道（Claude Code skill / Cursor / ClawHub 等）属于分发工程层"——架构上已预见这条路
- SKILL.md 格式统一后，一个编译器可以服务 6+ 个 host
- 先例：Doramagic 的 seed.yaml 已包含 `target_host: openclaw`——转换为 SKILL.md 是自然延伸
- 风险：需要为每个晶体维护 SKILL.md 转换规则；晶体内容必须结构化到足以被机械转换

**结论**：这是唯一真正差异化的定位，且市场空白存在。

---

## 四、Q2 — "seed.yaml → skill creator → host skill" 这条链路有无成熟先例？

**直接先例：无。**

没有发现任何产品实现了 "structured knowledge spec → skill creator → deployable skill" 的完整管道。

**间接先例（失败教训）**：
- OpenAPI spec → SK plugin：技术可行，但工程重，不适合知识型内容
- GPT Builder 的 "generate GPT from description"：最近似，但 GPT 是私有格式，无法迁移，且知识注入依赖 RAG 而非结构化指令

**接近的成功模式**：
- Anthropic skill-creator skill 本身：它接受"draft skill files"作为输入，说明 "structured input → SKILL.md" 在技术层面已有范式
- 这意味着 Doramagic 的 seed.yaml 如果能被 skill-creator 理解（通过用 SKILL.md 封装 seed.yaml 作为 references），链路就通了

**关键洞察**：链路不是空白，而是**拼图缺少最后一块**：seed.yaml → SKILL.md 的自动编译器。

---

## 五、Q3 — seed.yaml V6.1 塞给各 skill creator 会怎样

| Creator | 行为 | 是否有价值 | 失败模式 |
|---------|------|-----------|---------|
| **Anthropic skill-creator** | 可接受为 "draft skill file for iteration/improvement"；LLM 会尝试读取并据此生成 SKILL.md；成功率：中等偏高，因 seed.yaml 结构化程度高 | **有，最高**：seed.yaml 的结构化知识可被 skill-creator 正确解读 | Creator 可能忽略 `execution_protocol`、`preconditions` 等协议字段，只提取 `business_decisions` 和 `known_use_cases` |
| **Claude.ai 上传 zip** | seed.yaml 被捆绑进 zip，作为 references 文件；Claude.ai 按 SKILL.md 指引读取 | **有条件**：需要 SKILL.md 中明确指令"读取 seed.yaml 并按其 execution_protocol 执行" | 没有配套 SKILL.md 时完全无效 |
| **ClawHub publish** | 接受任意文件上传；seed.yaml 作为 references/seed.yaml 存在；用户安装后 host AI 可读取 | **有，需 SKILL.md 配合**：ClawHub 本身不解析，但提供了完整的 skill 文件分发能力 | 无 SKILL.md 时 ClawHub 拒绝发布（SKILL.md 是强制要求） |
| **GPT Builder Knowledge file** | seed.yaml 被向量化，用于 RAG 检索；内容被当作普通文本 | **极低**：YAML 嵌套结构被文本化，`execution_protocol`/`preconditions` 等字段变成孤立片段，语义丢失 | GPT 无法执行协议，会自己"理解"seed.yaml 然后产出随机行为 |
| **Cursor `.mdc`** | seed.yaml 内容可 paste 进 `.mdc` 规则体；Cursor 将其作为提示词注入 | **极低**：seed.yaml 的 YAML 嵌套对 LLM 是低效表示，不如直接写 Markdown 指令 | 规则体过长导致触发成本上升；`execution_protocol` 等字段被忽略 |
| **Semantic Kernel** | seed.yaml 格式与 SK Prompt YAML 不兼容；需完整重写 | **零**：不是轻度适配，是完全重写 | 直接使用会被 SK 拒绝解析 |

**统一结论**：seed.yaml 在没有配套 SKILL.md 的情况下，在所有主流 creator 里都是"哑巴"——只有通过一层 SKILL.md 编译才能变成可执行的 skill。

---

## 六、CEO 决策建议

### 产品宪法约束（先确认边界，再谈定位）

在给出建议前必须对照产品宪法（`PRODUCT_CONSTITUTION.md`）：

- **§1.3 不做**：明确列出"实时用户对话 / 苏格拉底需求挖掘 / 按需定制晶体（v3 起废弃）"
- **§1.2.10**：Doramagic 侧只产通用晶体，不做定制；个性化在宿主 AI 侧驱动
- **§2.2**：适配渠道（Claude Code skill / Cursor / ClawHub）属于**分发工程层**，不是产品灵魂

**因此，定位 (c) 的"交互式 Doramagic.ai 服务——用户描述需求 → 生成定制 skill"版本被宪法明确排除。** 这是 v3 废弃的模式，不应复活。

---

### 核心结论

**Doramagic 应走定位 (a-extended)：离线批量编译器——seed.yaml → SKILL.md，一份产出兼容 6 个 host。**

这不是妥协，而是格式统一后 (a) 本身的价值剧变：

**1. 格式战争已结束（一级来源：agentskills.io, 2025-12）。** SKILL.md 是事实标准。2025-12 前，(a) 意味着"7 个系统 7 套格式 = 维护噩梦"；现在，一份 SKILL.md 覆盖 Claude Code + OpenAI Codex + VS Code Copilot + ClawHub + Cursor（趋同中）。(a) 的成本从不可接受变为可接受。

**2. 离线编译器 = 分发工程，宪法兼容。** `seed.yaml → SKILL.md` 是 `crystal_compiler.py` 的自然延伸，属于§2.2 "分发工程层"——不是交互服务，不是定制，是批量离线产出。seed.yaml 里已有 `target_host: openclaw` 字段，说明架构上已预见这条路。

**3. 定位 (b) 用户体验不可接受。** 要求用户把 seed.yaml 喂给任意 skill-creator 并解释"如何使用它"，违反"不教用户做事，给他工具"的产品灵魂。(b) 是分发工具缺失时的降级方案，不是正道。

**注意**：如果"(c) = 离线编译器"（seed.yaml → SKILL.md 的脚本，不涉及交互服务），它与 (a-extended) 是同一件事，完全兼容宪法。本文件推荐的就是这个版本。

---

### 最小可行行动

| 优先级 | 行动 | 依据 | 宪法兼容性 |
|--------|------|------|-----------|
| P0 | 为 finance-bp-009-v6.1.seed.yaml 手写一个对应的 SKILL.md，验证信息密度是否能被承载 | 最快速的链路验证 | 兼容 |
| P1 | 实现 `seed.yaml → SKILL.md` 的离线编译脚本；`business_decisions` + `known_use_cases` + `anti_patterns` 映射到 SKILL.md 的 Level 2 + references | 核心分发能力，§2.2 分发工程层 | 兼容 |
| P2 | 在 ClawHub 发布第一个 Doramagic 产出的 SKILL.md（finance-bp-009），收集真实反馈 | 渠道验证 | 兼容 |
| ~~P3~~ | ~~Doramagic.ai 提供"选晶体 → 选 host → 下载 SKILL.md"交互服务~~ | ~~宪法禁止：属于交互定制，已废弃~~ | **违反 §1.3** |

---

### 风险提示

- **seed.yaml 到 SKILL.md 的信息损耗**：seed.yaml v6.1 已有大量 anti_patterns + 跨项目智慧层 + 领域约束——SKILL.md 的 500 行上限无法容纳全量；需要设计 "seed.yaml 作为 references/ 文件 + SKILL.md 作为入口导航" 的双层架构
- **执行协议保真度**：seed.yaml 的 `execution_protocol` 包含 preconditions + state_machine + evidence_quality——这些在 SKILL.md 的 Markdown 体里必须以足够强的指令形式存在，否则宿主 AI 会跳过（参见 `2026-03-31-skill-architecture-rethink.md`：SKILL.md 的指令是建议性的，宿主 LLM 可以选择忽略——这是根本性限制，在 seed → SKILL.md 架构里依然存在）
- **不要等待**：SKILL.md 格式已统一，ClawHub 渠道已就绪，P0 今天就能开始

---

## 七、数据可信度分层

### 一级来源（直接获取官方文档，可信）

- agentskills.io/specification — 格式规范全文，直接 WebFetch
- platform.claude.com/docs — Anthropic Agent Skills 文档，直接 WebFetch
- code.claude.com/docs/en/skills — Claude Code Skills 文档，直接 WebFetch
- github.com/anthropics/skills/skills/skill-creator/SKILL.md — skill-creator 全文，直接 WebFetch
- developers.openai.com/codex/skills — OpenAI Codex Skills，直接 WebFetch
- learn.microsoft.com/semantic-kernel/concepts/plugins — SK 文档，直接 WebFetch
- code.visualstudio.com/docs/copilot/customization/agent-skills — VS Code Copilot，直接 WebFetch
- docs.openclaw.ai/tools/clawhub — ClawHub CLI 文档，直接 WebFetch

### 二级来源（搜索结果摘要，已用于背景但数字不引用）

以下数字来自 SEO 内容站 / Medium 文章，**不作为决策依据**：
- "13,729 ClawHub skills"（来源：skywork.ai，不可验证）
- "87,000 GitHub stars for anthropics/skills"（来源：Medium，不可验证）
- "Cursor 支持 SKILL.md"（来源：Cursor 社区论坛帖子，非官方文档）

---

## 参考链接

- [agentskills.io 规范](https://agentskills.io/specification)
- [Anthropic Agent Skills 文档](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview)
- [Claude Code Skills 文档](https://code.claude.com/docs/en/skills)
- [Anthropic skill-creator SKILL.md](https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md)
- [OpenAI Skills 文档](https://developers.openai.com/api/docs/guides/tools-skills)
- [OpenAI Codex Skills](https://developers.openai.com/codex/skills)
- [ClawHub 文档](https://docs.openclaw.ai/tools/clawhub)
- [VS Code Agent Skills](https://code.visualstudio.com/docs/copilot/customization/agent-skills)
- [Semantic Kernel Plugins](https://learn.microsoft.com/en-us/semantic-kernel/concepts/plugins/)
- [Cursor Rules](https://cursor.com/docs/context/rules)
- [GPT Builder](https://help.openai.com/en/articles/8770868-gpt-builder)
