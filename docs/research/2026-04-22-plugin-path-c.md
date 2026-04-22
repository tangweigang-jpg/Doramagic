# 路 C 深挖：openclaw Plugin SDK + 晶体 plugin 化可行性

**日期**：2026-04-22
**研究员**：opus subagent
**问题**：把晶体从 skill 形态升级为 openclaw plugin，能否突破 skill 4pp 天花板

---

## Part 1 — Plugin 类型地图（已查证）

**两维度切分**：
- **格式**：Native（进程内加载，有 `openclaw.plugin.json`） vs Compatible bundle（Codex/Claude/Cursor 格式，能力受限）
- **能力形状**：Plain / Hybrid / Hook-only / Non-capability

**SDK 入口（sdk-entrypoints.md）**：
- `definePluginEntry({id, name, configSchema, register(api)})` — 通用入口
- `defineChannelPluginEntry` — 消息通道
- `defineSingleProviderPluginEntry` — LLM provider
- `defineSetupPluginEntry` — onboarding 期
- `registerAgentHarness(...)` — 标注 "Experimental" + "bundled plugins only"

**Agent Harness vs Codex Harness（Q2 定义）**：
- **Agent Harness** = 一次 agent turn 的低层执行器（替换整个 agent 执行循环的底座）
- **Codex Harness** = Codex app-server 专用
- **Agent Tool ≠ Agent Harness**（完全不同层）

---

## Part 2 — 单一推荐

**`definePluginEntry` + `registerTool` + `registerHook('before_tool_call', ...)` 组合**

理由（已查证）：
1. `before_tool_call` hook 返回 `{ block: true }` is **terminal**（sdk-overview.md）——plugin 层唯一的"硬门"原语
2. `registerTool` 让晶体提供**唯一入口工具**（如 `stock_research`），agent 要做 A 股量化必须调它
3. preconditions / output_validator / hard_gates / evidence_quality 四个晶体字段**占执行力 ~70%**，全部可挂到工具边界

**拒绝的选项**：
- Provider plugin：只能改 LLM 请求/响应，无法阻止 agent 行为
- Channel plugin：消息通道，与知识无关
- Agent Harness：docs 明确 "third-party harness installation is experimental" + "bundled plugins only"——第三方短期内进不了 ClawHub 审核
- Bundle 格式：退化到 skill 形态，丢进程内代码强制优势

---

## Part 3 — plugin 能强制什么（核心）

**能强制**（已查证）：
- ✓ **拒绝 agent 发起的工具调用** — `before_tool_call` 返回 block:true 终止
- ✓ **改写工具结果** — `tool_result_persist` hook 在结果写入前同步改写
- ✓ **成为 agent 唯一数据入口** — registerTool + before_tool_call 屏蔽其他工具
- ✓ **注入 system prompt 片段** — provider 层 resolveSystemPromptContribution

**不能强制**：
- ✗ 不能阻止 agent 产生自由文本（agent 自由输出由 provider 拥有）
- ✗ 不能强令 agent 调用特定工具（只能屏蔽别的）
- ✗ 不能做跨 turn 约束（hook 作用域是单次 tool_call / agent_reply）

**核心判断（意见）**：plugin 强制力集中在**"工具边界"**这一个缝上。这正好匹配晶体里 preconditions / output_validator / hard_gates / evidence_quality 四个字段的语义（~70% 执行力），intent_router 和 anti_patterns 仍要靠 system prompt 软约束。

**量级预估（推测）**：skill 4pp → plugin **8-12pp**。依据：SWE-bench +2.1pp 是纯 prompt 形态；加"工具边界强制"的 LangGraph / Aider 架构在 verified 子集 +5~8pp。**未找到直接对照数据。**

---

## Part 4 — 迁移 a-stock-quant-lab：skill → plugin 12 步清单

以 `_runs/github-clones/doramagic-skills/skills/a-stock-quant-lab/` 为输入，产出 `@doramagic/openclaw-a-stock-quant-lab` npm 包。

| 步 | 动作 | 时数 |
|---|---|---|
| 1 | 脚手架 + `pnpm init` | 0.5h |
| 2 | 写 `openclaw.plugin.json` (id / configSchema) | 0.5h |
| 3 | `package.json` openclaw 字段 (compat.pluginApi ≥2026.3.24-beta.2) | 0.5h |
| 4 | tsup + ESM 构建配置 | 1h |
| 5 | 把 seed.yaml 拷进 src/crystal/（静态资源） | 0.5h |
| 6 | `src/router.ts` — intent_router 31 条 → matchIntent | 2h |
| 7 | `src/preconditions.ts` — preconditions[] → check() 函数组 | 2h |
| 8 | `src/validator.ts` — output_validator.assertions → JSONSchema + linter | 2h |
| 9 | `src/tools/stock_research.ts` — registerTool 主入口 | 2h |
| 10 | **`before_tool_call` hook — hard_gates[] → block: true**（价值核心） | 2h |
| 11 | `index.ts` — definePluginEntry 主入口 | 1h |
| 12 | Vitest 测试 + clawhub publish | 4h |

**总工程时数**：**18-22h** 有 TS 基础；**+15-25h 学习曲线** 无 TS 基础（ESM / tsup / Vitest / pnpm）。

---

## Part 5 — 成本、风险、最终判断

**分发成本（已查证）**：
- ClawHub skill：13,729 个（2026-02-28）
- ClawHub plugin：仅 8 个社区 plugin
- **plugin 生态比 skill 小 3 个数量级**
- TAM 估计是 skill 的 5-15%（意见）

**持续维护**：
- `pluginApi ≥2026.3.24-beta.2` 是 beta 通道
- 推测每 1-2 个月一次 breaking change 适配

**回滚成本低**：skill 形态产物不删，plugin 是增量发布；失败回滚 = 下架 npm + 保留 GitHub skill。沉没 ~20h。

**风险**：
1. TS 学习曲线（中）— Codex 辅助可压到 1 天
2. pluginApi beta 漂移（中高）
3. plugin 生态渗透率低（中）
4. **"8-12pp 提升"未经实测**（高）

**最终判断（意见）**：**做，但只做一个，做完马上量化对比。**

路径：
- `a-stock-quant-lab` 作为**并行第二形态**（skill 版已上架继续保留；plugin 版作为 "enforced edition"）
- 两形态跑同一套评测集，直接测 Δpp
- **≥5pp** → 路 C 确立，后续晶体双形态出厂
- **<3pp** → 路 C 伪突破，回到"骨架 C"折中（只 registerTool，不 hook 强制，砍一半成本）

**不建议**：立刻把 20 颗 finance 晶体全部迁成 plugin。在第一颗产生实测 Δpp 之前，批量迁移 = 把假设当事实做 400h 投入。

---

## Sources（一手 docs）

- [cli/plugins](https://docs.openclaw.ai/cli/plugins.md) · [architecture](https://docs.openclaw.ai/plugins/architecture.md) · [building-plugins](https://docs.openclaw.ai/plugins/building-plugins.md) · [bundles](https://docs.openclaw.ai/plugins/bundles.md) · [manifest](https://docs.openclaw.ai/plugins/manifest.md)
- [sdk-overview](https://docs.openclaw.ai/plugins/sdk-overview.md) · [sdk-entrypoints](https://docs.openclaw.ai/plugins/sdk-entrypoints.md) · [sdk-runtime](https://docs.openclaw.ai/plugins/sdk-runtime.md) · [sdk-setup](https://docs.openclaw.ai/plugins/sdk-setup.md) · [sdk-testing](https://docs.openclaw.ai/plugins/sdk-testing.md)
- [sdk-agent-harness](https://docs.openclaw.ai/plugins/sdk-agent-harness.md) · [sdk-channel-plugins](https://docs.openclaw.ai/plugins/sdk-channel-plugins.md) · [sdk-provider-plugins](https://docs.openclaw.ai/plugins/sdk-provider-plugins.md) · [codex-harness](https://docs.openclaw.ai/plugins/codex-harness.md)
- [community](https://docs.openclaw.ai/plugins/community.md) · [ClawHub plugins](https://clawhub.ai/plugins)
