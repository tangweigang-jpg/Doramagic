# Doramagic 灵魂提取全览：已提取项目总结

> 日期：2026-03-16
> 目的：对所有已做灵魂提取的项目进行 Doramagic 层面的综合分析

---

## 一、OpenClaw 灵魂提取报告

### 项目本质

OpenClaw 是一个**开源的个人 AI 助手平台**。一句话定义："你自己设备上跑的 AI 助手，通过你已经在用的消息渠道回复你。"

不是一个 chatbot，不是一个 API 代理，是一个**全渠道 AI 网关**——WhatsApp、Telegram、Slack、Discord、Signal、iMessage、微信、IRC、Teams、Matrix 等 20+ 渠道，一个 agent 引擎统一服务。

### 设计哲学

| 原则 | 体现 |
|------|------|
| **Local-first（本地优先）** | 记忆存为本地 Markdown 文件，不上云。用户数据在用户手里。 |
| **Channel-agnostic（渠道无关）** | agent 逻辑与消息渠道完全解耦。加一个新渠道 = 加一个 extension。 |
| **Always-on（永远在线）** | heartbeat 守护进程，无需人触发也能主动行动。launchd/systemd 用户服务。 |
| **Plugin-first（插件优先）** | 扩展能力通过 `extensions/` 目录的独立包实现，不改核心代码。 |
| **Multi-agent safety** | CLAUDE.md 中有 7 条多 agent 安全规则——不动别人的 stash、不切分支、只提交自己的改动。这是一个被多个 AI agent 同时开发的项目。 |

### 架构灵魂

```
用户消息（任何渠道）
    ↓
Gateway（控制平面）→ 路由到正确的 agent
    ↓
Agent 引擎（思考 + 工具调用 + 技能执行）
    ↓
回复（路由回原始渠道）
```

**Gateway 不是产品，assistant 才是产品。** Gateway 是基础设施，像电话交换机——用户不关心交换机，关心的是接电话的人。

### WHY 层（为什么这样设计）

1. **为什么 20+ 渠道？** — 用户不应该为了用 AI 而换沟通工具。AI 应该去用户在的地方，不是让用户来 AI 在的地方。

2. **为什么 local-first 而非 cloud-first？** — 隐私。记忆是 Markdown 文件而不是数据库，是因为用户应该能打开、编辑、删除自己的 AI 记忆，不需要任何工具。

3. **为什么 heartbeat 守护进程？** — AI 助手应该主动，不是被动。就像真正的助理会主动提醒你明天有会议，不是等你问。

4. **为什么插件架构？** — 60K+ stars 的项目必须让社区能贡献，但不能让社区改核心。插件是安全边界。

5. **为什么 CLAUDE.md 有 316 行规则？** — 这个项目被多个 AI agent 同时开发（multi-agent safety 规则）。CLAUDE.md 不是给人读的，是给 AI 读的——它是 AI 的"团队规范手册"。

### UNSAID 层（未说出口的坑）

1. **多 agent 并发开发的 git 冲突** — 7 条 multi-agent safety 规则说明这个问题很严重。不要动别人的 stash、不要切分支、只提交自己的改动——这些规则是踩坑后加的。

2. **Node.js + Bun 双轨运行** — "keep Node + Bun paths working"。两个 runtime 共存的维护成本不低，但为了兼容现有用户不能砍。

3. **插件安全** — world-writable `extensions/*` 在 root 安装时会触发安全拦截。这是一个未完全解决的问题。

4. **渠道特性碎片化** — 每个渠道的能力不同（有的支持富文本、有的只支持纯文本、有的有按钮）。agent 的回复需要适配 20+ 种渠道格式。

5. **Windows 支持的脆弱性** — Parallels Windows smoke 的长列表说明 Windows 路径问题频出。PowerShell 执行策略、.ps1 shim、mojibake——每一条都是一个坑。

### 对 Doramagic 的关系

**OpenClaw 是 Doramagic 的宿主平台。** Doramagic 的 Soul Extractor 作为 OpenClaw 的 skill 运行。理解 OpenClaw 的架构约束对 Doramagic 至关重要：

| OpenClaw 约束 | 对 Doramagic 的影响 |
|---------------|-------------------|
| Skill 通过 SKILL.md 定义 | Doramagic 必须遵守 SKILL.md 格式 |
| 用户通过 Telegram 等渠道交互 | 提取结果的展示受渠道能力限制 |
| 插件独立安装 | Doramagic 的依赖不能污染 OpenClaw 核心 |
| 多 agent 同时工作 | Doramagic 的 Agentic 提取需要考虑并发安全 |
| Gateway 是控制平面 | Doramagic 是 skill，不是 agent——它被 agent 调用 |

---

## 二、全部已提取项目总览

| # | 项目 | 类型 | 规模 | 灵魂提取方式 | 关键灵魂 |
|---|------|------|------|-------------|---------|
| 1 | python-dotenv | Python 库 | ~2K 行 | exp01-exp08 多版本 | 42%→96% 验证灵魂提取有效性 |
| 2 | obra/superpowers | Claude Code skill 框架 | ~5K 行 | exp05-exp07 | 反合理化设计、Iron Law、skill chaining |
| 3 | wger | Django 健身追踪器 | 12MB/1123 文件 | exp08 MiniMax 提取 | 跨领域适应性验证，traceability 100% |
| 4 | geo-seo-claude | SEO/GEO 工具 | ~9K 行 | exp-seo-skills | GEO-first 路线、citability scorer、品牌存在面 |
| 5 | marketingskills | 营销技能集 | 55K 行（截取 5K） | exp-seo-skills | context 底板、33 个 skill 扁平架构 |
| 6 | claude-seo | 全栈 SEO 审计 | ~9K 行 | exp-seo-skills | hooks 拦截、7 子代理、与 30x-seo 高度相似 |
| 7 | 30x-seo | 技术 SEO | ~11K 行 | exp-seo-skills | 与 claude-seo 疑似 fork，11 stars vs 2.3K |
| 8 | gstack | Claude Code 工作流 | ~22K 行 | 本 session 手动 | 显式认知档位、模板防腐、三层测试 |
| 9 | OpenClaw | AI 助手平台 | 140MB/8700+ 文件 | 本 session 手动 | 全渠道网关、local-first、multi-agent safety |

---

## 三、Doramagic 层面的综合分析

### 3.1 灵魂提取验证了什么

**核心结论：灵魂提取有效，且跨领域适应。**

| 验证点 | 证据 |
|--------|------|
| 灵魂提取本身有用 | python-dotenv A/B/C：42%→83%→96%（exp01） |
| 跨领域适应 | Python 库(dotenv) + Django 应用(wger) + SEO 工具(4 项目) + Claude Code skill(gstack/superpowers) + AI 平台(OpenClaw) |
| 大项目可行但有天花板 | wger(12MB) 和 OpenClaw(140MB) 都能提取，但信息截取严重 |
| 跨项目对比有价值 | 4 个 SEO 项目发现"最大公约数"+"项目打架" |

### 3.2 不同类型项目的灵魂差异

| 项目类型 | WHAT/HOW 难度 | WHY 难度 | UNSAID 难度 | 灵魂密度 |
|---------|--------------|---------|------------|---------|
| **小型库**（python-dotenv） | 低 | 低 | 低 | 高（代码少，灵魂集中） |
| **中型工具**（SEO 4 项目） | 低 | 中 | 中 | 中（领域知识丰富） |
| **大型应用**（wger, OpenClaw） | 中 | 高 | 高 | 低（灵魂分散在巨量代码中） |
| **方法论框架**（superpowers, gstack） | 低 | **极高** | 中 | **极高**（WHY 是核心价值） |

**关键发现：方法论框架类项目的灵魂密度最高，WHY 最丰富。** superpowers 的反合理化设计、gstack 的显式认知档位——这些 WHY 层知识是项目的核心差异化，单遍提取就能捕获大部分。

**大项目是 Agentic 提取的核心验证场景。** wger 和 OpenClaw 的灵魂分散在数千文件中，单遍提取丢失严重。这正是 Stage 1.5 Agent Loop 要解决的。

### 3.3 CLAUDE.md 的演化观察

9 个项目中有 3 个自带 CLAUDE.md（gstack、OpenClaw、superpowers），它们的 CLAUDE.md 质量和风格差异巨大：

| 项目 | CLAUDE.md 风格 | 行数 | 给谁看的 |
|------|---------------|------|---------|
| **OpenClaw** | 工程规范手册（极其详细的 git/PR/测试/部署规则） | 316 | AI agent 开发者 |
| **gstack** | 开发指南（简洁，重点是 skill 开发工作流） | ~80 | AI agent |
| **superpowers** | 行为规范（skill 的触发条件和使用约束） | ~60 | AI agent |

**洞察：CLAUDE.md 的内容取决于"谁在读它"。** OpenClaw 的 CLAUDE.md 是给多个 AI agent 同时开发时看的"团队手册"——316 行全是防止 AI 踩坑的规则。gstack 的是给用户的 Claude Code 看的"使用说明"。这是同一个文件名，完全不同的用途。

**对 Doramagic 的启示**：Soul Extractor 提取的 CLAUDE.md 应该针对"使用该项目的 AI"而非"开发该项目的 AI"。我们的目标用户是消费者，不是贡献者。

### 3.4 跨项目知识模式

从 9 个项目中观察到的共性模式：

**模式 1：显式认知约束比自由发挥更有效**
- superpowers：反合理化设计（列出 LLM 可能跳步的借口，逐一封杀）
- gstack：显式档位（不同任务用不同认知模式）
- OpenClaw：316 行 CLAUDE.md 规则
- **含义**：Doramagic 的 Stage 架构是对的——每个 Stage 给 LLM 一个明确的认知框架

**模式 2：大项目的灵魂不在代码里，在架构决策里**
- OpenClaw：20+ 渠道的设计哲学（"AI 去用户在的地方"）比具体代码重要 100 倍
- wger："健身数据归属用户"的设计哲学是灵魂，不是 Django model 定义
- **含义**：WHY 层确实是最高价值知识，Agentic 提取的优先方向正确

**模式 3：项目之间的知识传播是真实存在的**
- 0.737 YouTube 相关性在 3/4 SEO 项目中出现，但解读不同
- claude-seo ≈ 30x-seo 是代码级的知识传播（fork）
- gstack 和 superpowers 都使用 SKILL.md 范式，但设计理念不同
- **含义**：知识供应链和通胀检测有实际应用场景

**模式 4：平台项目的 CLAUDE.md 是"给 AI 的员工手册"**
- OpenClaw 的 multi-agent safety 规则
- gstack 的"NEVER use mcp__claude-in-chrome__*"
- **含义**：Doramagic 提取的知识最终要注入 AI，所以格式和语气应该是"给 AI 看的说明书"，不是"给人看的文档"

### 3.5 对 Doramagic 下一步开发的启示

| 启示 | 来自哪个项目 | 行动 |
|------|------------|------|
| Agentic 提取对大项目不可或缺 | wger + OpenClaw | Phase 1 最高优先级 |
| WHY 层是方法论框架的核心灵魂 | gstack + superpowers | Stage 1.5 假说优先 WHY 类 |
| CLAUDE.md 应写给 AI 消费者看 | OpenClaw vs gstack 的风格差异 | 输出格式面向"使用 AI"而非"开发 AI" |
| 模板防腐系统值得引入 | gstack | Phase 0 引入 |
| 多 agent 并发是真实需求 | OpenClaw 的 7 条安全规则 | Agentic 提取的并发安全设计 |
| 领域知识在项目间传播 | 4 个 SEO 项目 | 供应链 P1 有实际验证场景 |
| 小项目不需要 Agentic | python-dotenv | 弱模型/小项目降级方案已设计 |
