# Claude Code 宿主能力规范

**文档版本**: v1.0  
**生成日期**: 2026-04-06  
**信息来源**: Claude Code TypeScript 源码快照（2026-03-31，~512K LOC，由 npm source map 曝光）、实测观察、~/.claude/ 配置文件  
**用途**: 指导 Doramagic 知识晶体（Crystal）在 Claude Code 宿主中的编译和渲染决策

---

## 证据来源说明

文档中每条能力标注以下来源之一：

- **源码分析** — 来自 claude-code-instructkr 的逆向工程报告（`docs/research/claude-code-instructkr/report/`）
- **实测** — 本 agent 在 Claude Code 中运行时直接观察到的行为
- **配置文件** — `~/.claude/settings.json` 等配置文件内容
- **待验证** — 合理推断但未有直接证据，需要进一步测试

---

## 1. 执行环境

### 1.1 进程模型

| 特性 | 值 | 来源 |
|------|----|----|
| 运行时 | Bun（TypeScript，非 Node.js） | 源码分析 |
| 主线程模型 | 单线程 REPL（AsyncGenerator 驱动） | 源码分析 |
| 工作目录 | 启动时的 CWD，子代理 session 间会重置 | 实测 |
| Shell 环境 | 用户 profile（bash 或 zsh）初始化 | 实测 |
| 平台支持 | macOS、Linux、Windows（PowerShell 路径） | 源码分析 |

### 1.2 沙箱

| 特性 | 值 | 来源 |
|------|----|----|
| 沙箱库 | `@anthropic-ai/sandbox-runtime` | 源码分析 |
| macOS 实现 | `sandbox-exec`（OS 级别隔离） | 源码分析 |
| Linux 实现 | `bubblewrap`（bwrap，容器级隔离） | 源码分析 |
| 默认状态 | 非沙箱模式（用户显式开启才生效） | 源码分析 |
| 沙箱覆盖范围 | 文件系统 + 网络访问（OS 层拦截，独立于应用层权限） | 源码分析 |
| 晶体设计影响 | 沙箱模式下，晶体需要声明所需的文件系统路径；网络请求须经过沙箱许可 | 待验证 |

### 1.3 超时与限制

| 特性 | 值 | 来源 |
|------|----|----|
| Bash 命令超时 | 由用户/晶体控制（BashTool 参数），无强制全局上限 | 源码分析 |
| Bash AST 解析超时 | 50ms（防止恶意输入 OOM） | 源码分析（bashParser.ts:28） |
| Bash AST 最大节点 | 50,000 个节点（防 OOM） | 源码分析 |
| Agent maxTurns | 可配置，默认值因 agent 类型而异 | 源码分析（runAgent.ts:337） |
| 最大工具结果内联 | 约 50K chars（超过则持久化到磁盘） | 源码分析（toolResultStorage.ts） |

### 1.4 文件系统访问

| 特性 | 值 | 来源 |
|------|----|----|
| 读取范围 | 无路径限制（非沙箱模式下可读任意文件） | 实测 |
| 写入范围 | 同上，受权限模式约束 | 实测 |
| 工具结果溢出路径 | `~/.claude/projects/<project>/<session>/tool-results/<id>.txt` | 源码分析 |
| 记忆存储路径 | `~/.claude/projects/<git-root>/memory/*.md` | 源码分析 |
| 邮箱路径（Team Mode） | `~/.claude/teams/<team_name>/inboxes/<agent_name>.json` | 源码分析 |

---

## 2. 可用工具

### 2.1 默认加载工具（始终在 prompt 中）

以下工具无需 ToolSearch，第一轮即可用：

| 工具 | 功能 | 并发安全 |
|------|------|---------|
| BashTool | Shell 命令执行，支持后台任务和沙箱模式 | 否 |
| FileReadTool | 读取文件，支持 PDF/图片/Jupyter Notebook，分页读取 | 是 |
| FileEditTool | 精确字符串替换（`old_string` → `new_string`），支持 `replace_all` | 否 |
| FileWriteTool | 写入/创建文件（会覆盖已有文件） | 否 |
| GlobTool | 按 glob 模式查找文件（基于修改时间排序） | 是 |
| GrepTool | ripgrep 正则内容搜索 | 是 |
| AgentTool | 启动子代理，支持同步/异步/Teammate 三种模式 | 否 |
| WebFetchTool | HTTP 抓取，自动转换 HTML→Markdown，有域名安全检查 | 是 |
| WebSearchTool | 网络搜索（内置搜索引擎，不需要外部 API key） | 是 |
| SkillTool | 加载并执行 `~/.claude/skills/` 下的 Skill | 否 |
| ToolSearchTool | 关键词搜索延迟加载的工具（自身永不延迟） | 是 |
| TodoWriteTool | 写入 Todo 列表（显示在侧边栏，当前会话可见） | 否 |

来源：源码分析（tools.ts:108-186）+ 实测（当前 session 工具列表可见）

### 2.2 延迟加载工具（需通过 ToolSearch 发现）

以下工具初始不在 prompt 中，需先用 ToolSearch 搜索后加载：

| 工具 | 功能 | 搜索关键词示例 |
|------|------|-------------|
| NotebookEditTool | Jupyter Notebook 单元格编辑 | `jupyter notebook` |
| EnterWorktreeTool | 进入 git worktree 隔离环境 | `worktree isolation` |
| ExitWorktreeTool | 退出 worktree 环境 | `worktree exit` |
| EnterPlanModeTool | 进入只读计划模式 | `plan mode` |
| ExitPlanModeTool | 退出计划模式 | `plan mode exit` |
| MCPTool（动态） | MCP 服务器工具（运行时注册） | MCP 服务器名前缀 |
| ListMcpResourcesTool | 列出 MCP 资源 | `mcp resources` |
| ReadMcpResourceTool | 读取 MCP 资源 | `mcp read` |
| TaskCreateTool | 创建后台任务 | `background task` |
| TaskGetTool / TaskListTool 等 | 任务管理（创建/查询/停止/输出） | `task management` |
| ScheduleCronTool | 定时任务（需 AGENT_TRIGGERS feature flag） | `cron schedule` |
| BriefTool | 生成会话摘要 | `session summary` |
| AskUserQuestionTool | 向用户提出交互式问题 | `ask user` |

来源：源码分析（tools.ts，tool.shouldDefer 字段）+ 实测（system-reminder 中可见 deferred tool 列表）

### 2.3 工具能力边界

**BashTool 关键约束**：

| 约束项 | 细节 | 来源 |
|--------|------|------|
| AST 静态检查 | 23 个独立验证器，Fail-Closed 策略（未知结构拒绝执行） | 源码分析 |
| 危险命令类型 | 命令替换 `$()`、进程替换、子 shell、控制流（共 18 种 AST 节点类型）在非白名单模式下需用户确认 | 源码分析 |
| 环境变量白名单 | 约 40 个安全变量；`PATH`/`LD_PRELOAD`/`PYTHONPATH`/`HOME` 等绝不在白名单内 | 源码分析 |
| 后台任务支持 | `run_in_background` 参数，命令添加 `&` 后台执行 | 源码分析 |

**FileReadTool 关键约束**：

| 约束项 | 细节 | 来源 |
|--------|------|------|
| 分页读取 | 支持 `offset`（行号）+ `limit`（行数）参数 | 实测 |
| 格式支持 | 文本、PDF（最多 20 页/次）、图片（PNG/JPG）、Jupyter Notebook（.ipynb） | 实测 |
| 结果不持久化 | `maxResultSizeChars: Infinity`，读取结果不写磁盘（避免循环 Read 问题） | 源码分析 |

**WebFetchTool 关键约束**：

| 约束项 | 细节 | 来源 |
|--------|------|------|
| HTML 转换 | 自动将 HTML 转换为 Markdown | 源码分析 |
| 域名安全检查 | 有黑名单域名检查（内部安全机制） | 源码分析 |
| 内网访问 | 待验证（沙箱关闭时理论上可访问 localhost） | 待验证 |

---

## 3. 权限模型

### 3.1 五级权限模式

| 模式 | 行为 | 晶体适用场景 |
|------|------|------------|
| `default` | 每次工具调用都询问用户 | 高敏感操作晶体（金融、系统管理） |
| `acceptEdits` | 文件编辑自动通过，命令仍需确认 | 日常开发类晶体 |
| `plan` | 只生成计划不执行（只读模式） | 分析类、审计类晶体 |
| `auto` | LLM 分类器自动决策（危险规则被剥离） | 流水线自动化晶体 |
| `bypassPermissions` | 跳过所有权限检查 | 完全信任的内部晶体 |

来源：源码分析（utils/permissions/PermissionMode.ts）

### 3.2 权限规则格式（settings.json）

```json
{
  "permissions": {
    "allow": ["Bash(git:*)", "Bash(npm run:*)", "Read", "Write", "WebFetch"],
    "deny":  ["Bash(rm -rf /)", "Bash(sudo:*)"]
  }
}
```

规则匹配支持三种形式：
1. **工具级**：`Bash`（匹配所有 Bash 命令）
2. **前缀**：`Bash(git commit:*)`（匹配 `git commit` 开头的命令）
3. **精确**：`Bash(ls -la)`（仅匹配这条命令）

来源：配置文件 `~/.claude/settings.json` + 源码分析（permissions.ts）

### 3.3 Hooks 系统

Claude Code 支持在工具执行前后注入 Shell 脚本 hook：

| Hook 类型 | 触发时机 | 用途 |
|-----------|---------|------|
| `PreToolUse` | 工具调用前 | 权限审查、日志记录、拦截敏感操作 |
| `PostToolUse` | 工具调用后 | 结果审计、触发副作用 |
| `Notification` | 系统通知时 | 消息推送、告警 |
| `Stop` | 会话结束时 | 清理、摘要生成 |

Hook 返回码：`0` 允许，非 `0` 拦截（配合 stderr 输出错误消息）。  
来源：源码分析 + 配置文件（settings.json 中的 hooks 字段结构）

**晶体设计影响**：晶体依赖的工具能力可能被用户 hooks 拦截。晶体应在失败时提供清晰的 fallback，而不是假设工具调用必然成功。

---

## 4. 上下文管理

### 4.1 Context Window

| 参数 | 值 | 来源 |
|------|----|----|
| 标准 context window | 200K tokens（claude-sonnet-4-x、claude-opus-4-x） | 源码分析 |
| 1M 扩展变体 | `claude-opus-4-x[1m]` 等（需订阅等级支持） | 源码分析（model.ts:153-175） |
| 自动压缩触发阈值 | `effectiveContextWindow - 13K` tokens | 源码分析（autoCompact.ts） |

### 4.2 五层压缩防线

Claude Code 采用渐进式降级策略，从低干预到高干预：

| 层级 | 名称 | 触发条件 | 信息损失 |
|------|------|---------|---------|
| L0 | Tool Result Storage | 单工具结果 > ~50K chars | 零（原文存磁盘，上下文仅保留 2KB 预览） |
| L1a | 时间触发微压缩 | 离开会话 > 60min | 低（旧工具结果被占位符替换） |
| L1b | 缓存微压缩 | 可压缩工具数超阈值 | 低（服务端缓存删除，本地不变） |
| L2 | 自动压缩 | token > 阈值 | 高（Fork Agent 生成有损摘要） |
| L3 | 手动 `/compact` | 用户命令 | 中-高 |
| L4 | 响应式压缩 | 413 prompt_too_long 错误 | 最高（紧急截断） |

来源：源码分析（services/compact/ 目录，~3900 行代码）

### 4.3 可压缩工具白名单

以下工具的输出会被微压缩系统清除（因为它们的输出可再生）：

`FileReadTool`、`BashTool`、`GrepTool`、`GlobTool`、`WebSearchTool`、`WebFetchTool`、`FileEditTool`（清除输入）、`FileWriteTool`（清除输入）

用户手工输入的文本和图片**永远不会被清除**。

来源：源码分析（microCompact.ts:30-41，COMPACTABLE_TOOLS）

### 4.4 对晶体设计的影响

1. **关键信息不要只放在工具结果里**：工具结果可能在 L0-L1 阶段被清除，晶体的关键中间结论应该写入文件或 TodoWrite，而不是依赖历史工具结果仍在上下文中。
2. **长流程需要检查点**：超过 ~30 轮交互的晶体任务，应在关键阶段主动写入 session memory 或文件，防止 L2 压缩丢失关键状态。
3. **工具输出大小意识**：如果晶体需要读取大文件，应使用 `offset`+`limit` 分页，或在晶体指令中明确要求只读取必要部分，避免触发 L0 溢出。

---

## 5. 多 Agent 能力

### 5.1 三种协作模式

| 模式 | 触发方式 | 并发度 | 通信机制 | 典型用途 |
|------|---------|--------|---------|---------|
| Subagent（默认） | AgentTool 调用 | 同步/异步 | 函数返回值 | 子任务分解 |
| Coordinator Mode | `CLAUDE_CODE_COORDINATOR_MODE=1` | 全异步 | `<task-notification>` XML | 复杂项目协调 |
| Team Mode | `spawnTeammate()` + TeamFile | 持久化并行 | 文件邮箱 + 轮询（500ms） | 长期并行工作流 |

来源：源码分析（AgentTool.tsx，~1400 行）

### 5.2 子代理关键约束

| 约束项 | 细节 | 来源 |
|--------|------|------|
| 层级结构 | 扁平化（roster is flat）：Teammate 不能生成 Teammate | 源码分析（AgentTool.tsx:272） |
| AbortController | 同步子代理共享父级；异步子代理有独立 AbortController | 源码分析（runAgent.ts:524-528） |
| 权限继承 | `bypassPermissions`/`acceptEdits`/`auto` 三种父级模式始终优先，不被子代理降级 | 源码分析（runAgent.ts:414-497） |
| maxTurns | 子代理可单独设置最大轮次 | 源码分析（AgentDefinition 类型） |
| 工具白名单 | 子代理可以限制可用工具（`tools` 白名单 + `disallowedTools` 黑名单） | 源码分析 |
| 并行数上限 | 待验证（理论无硬上限，但受 API 并发配额限制） | 待验证 |

### 5.3 子代理类型

内置 Agent 类型（通过 `agentType` 字段路由）：

| 类型 | 系统提示特点 | 典型场景 |
|------|------------|---------|
| `Explore` | 跳过 CLAUDE.md 和 git status（节省 token） | 代码库研究 |
| `Plan` | 只读模式，生成计划 | 架构设计 |
| `GENERAL_PURPOSE_AGENT` | 完整系统提示 | 通用执行 |
| `FORK_AGENT` | 继承父级 prompt + 消息历史 | 上下文分叉 |

自定义 Agent 可以在 `~/.claude/` 或项目根目录的 Markdown 文件中定义。  
来源：源码分析（loadAgentsDir.ts，AgentDefinition 类型）

### 5.4 对晶体设计的影响

- **需要并行的晶体**：使用 AgentTool 的 `run_in_background: true` 参数，不要在主线程轮询等待
- **晶体内的子任务分解**：可以用 Subagent 隔离高风险子任务（如网络请求、文件修改），父代理负责合并结果
- **Team Mode 限制**：需要 tmux 或 InProcess 支持，不是所有环境都可用；晶体不应假设 Team Mode 必然可用

---

## 6. 网络能力

### 6.1 WebSearch

| 特性 | 值 | 来源 |
|------|----|----|
| 可用性 | 内置，无需外部 API key | 实测 |
| 实现 | Claude API 原生搜索能力（非第三方 API） | 源码分析 |
| 计费 | $0.01/次 web search 请求（独立计费） | 源码分析（modelCost.ts） |
| 结果格式 | 搜索摘要 + 链接列表 | 实测 |

### 6.2 WebFetch

| 特性 | 值 | 来源 |
|------|----|----|
| 协议 | HTTP/HTTPS | 源码分析 |
| 内容转换 | HTML → Markdown（自动） | 源码分析 |
| 域名限制 | 有内部安全黑名单 | 源码分析 |
| JavaScript 渲染 | 不支持（静态 HTTP 抓取，非浏览器） | 待验证 |
| 认证 | 不支持自动认证（需要在 URL 中携带 token 或用 Bash + curl 替代） | 待验证 |

### 6.3 MCP 服务器网络能力

通过 MCP 服务器，Claude Code 可以扩展网络能力（如本机环境中已配置的 Gmail MCP、Google Calendar MCP）。  
来源：实测（system-reminder 中可见已配置的 MCP 工具列表）

### 6.4 对晶体设计的影响

- **Web 内容晶体**：优先用 WebSearch 定位资源，再用 WebFetch 获取内容；不要直接对大型 HTML 页面使用 WebFetch（转换后可能仍然很大）
- **需要动态 JS 内容**：必须使用 BashTool + curl/wget，或通过 MCP 集成浏览器工具
- **API 调用**：使用 BashTool + curl（具有完整的 HTTP 控制能力），而非 WebFetch

---

## 7. 文件操作能力

### 7.1 读取（FileReadTool）

```
参数：file_path（必填）、limit（可选，行数）、offset（可选，起始行）、pages（仅 PDF）
返回：文件内容（cat -n 格式，带行号）
```

| 能力点 | 细节 | 来源 |
|--------|------|------|
| 超大文件 | 建议分页读取（offset + limit）；结果不写磁盘，不触发 L0 压缩 | 源码分析 |
| 二进制文件 | 支持图片（PNG/JPG）、PDF（视觉内容）、Jupyter Notebook | 实测 |
| 目录 | 不支持（用 Bash ls 替代） | 实测 |

### 7.2 编辑（FileEditTool）

```
参数：file_path、old_string（精确匹配）、new_string（替换内容）、replace_all（bool）
约束：old_string 必须在文件中唯一，否则失败；使用前必须先 Read 文件
```

| 能力点 | 细节 | 来源 |
|--------|------|------|
| 原子操作 | 基于精确字符串匹配，不是行号替换；缩进/空格必须完全匹配 | 实测 |
| 全局替换 | `replace_all: true` 替换所有出现 | 实测 |
| 创建文件 | 不支持（用 FileWriteTool） | 实测 |

### 7.3 写入（FileWriteTool）

```
参数：file_path、content
行为：覆盖已有文件；创建新文件；使用前必须先 Read（如果文件已存在）
```

### 7.4 搜索（GrepTool、GlobTool）

| 工具 | 参数 | 特性 |
|------|------|------|
| GrepTool | `pattern`（regex）、`path`、`glob`（文件过滤）、`type`（文件类型） | ripgrep 引擎，支持多行模式 |
| GlobTool | `pattern`（glob）、`path` | 按修改时间排序，适合找最新文件 |

---

## 8. 状态持久化

### 8.1 三层记忆架构

| 层级 | 路径 | 生命周期 | 上限 |
|------|------|---------|------|
| Working Memory | 当前 context window | 会话内 | ~200K tokens（约 13K 保留给压缩） |
| Session Memory | `~/.claude/projects/<slug>/session-memory.md` | 会话级（跨 Auto Compact 保留） | 12,000 tokens（每 section 2000 tokens） |
| Persistent Memory | `~/.claude/projects/<git-root>/memory/*.md` | 永久（直到显式删除） | 无硬上限 |

来源：源码分析（memdir/ + services/SessionMemory/，~5700 行代码）

### 8.2 Session Memory 结构

Session Memory 采用固定的 9 段 Markdown 结构：

```markdown
# Session Title
# Current State
# Task specification
# Files and Functions
# Workflow
# Errors & Corrections
# Codebase and System Documentation
# Learnings
# Key results
# Worklog
```

每段不超过 2000 tokens，全文不超过 12000 tokens。  
用途：Auto Compact 时作为"前情提要"注入新的上下文窗口。  
来源：源码分析（services/SessionMemory/prompts.ts:14-36）

### 8.3 Persistent Memory 格式

每条持久记忆是一个独立 `.md` 文件，带 YAML frontmatter：

```markdown
---
name: <记忆名称>
description: <单行描述，用于决定未来会话中的相关性>
type: user | feedback | project | reference
---

<记忆内容>
```

路径由 git root 决定，同一仓库的不同 worktree 共享记忆。  
**安全约束**：`autoMemoryDirectory` 配置不信任 `projectSettings`（防止恶意 repo 劫持写入路径）。  
来源：源码分析（memdir/memoryTypes.ts，memdir/paths.ts）

### 8.4 CLAUDE.md 文件

| 位置 | 加载时机 | 内容类型 |
|------|---------|---------|
| `~/.claude/CLAUDE.md` | 每个会话启动时 | 全局规则（跨项目） |
| `<project>/CLAUDE.md` | 进入项目目录时 | 项目规则 |
| `.claude/CLAUDE.md`（子目录） | 进入子目录时 | 子目录规则 |

CLAUDE.md 的内容注入 system prompt，影响 Agent 的所有决策。  
来源：实测 + 配置文件

### 8.5 对晶体设计的影响

- **跨 session 状态**：晶体无法依赖 context window 中的历史信息（session 间归零）。需要持久化的状态应写入文件或 Persistent Memory
- **Session Memory 有上限**：12K tokens，晶体如果要利用 session memory 作为检查点，每个 section 不超过 2000 tokens
- **CLAUDE.md 加载顺序**：晶体如果需要注入运行时规则，应通过在任务开始时读取 CLAUDE.md 或 system-reminder 注入（而非修改 CLAUDE.md 本体，以避免破坏 prompt cache）

---

## 9. 模型选择

### 9.1 可用模型

| 别名 | 对应模型 | 定价（per Mtok） | 默认订阅 |
|------|---------|--------------|---------|
| `haiku` | claude-haiku-4-5 | $1/$5 | - |
| `sonnet` | claude-sonnet-4-6 | $3/$15 | Pro/Enterprise/PAYG |
| `opus` | claude-opus-4-6 | $15/$75（标准）/ $30/$150（Fast Mode） | Max/Team Premium |
| `best` | 动态（当前最佳可用） | - | - |

来源：源码分析（utils/modelCost.ts）

### 9.2 子代理模型路由

子代理可以通过 `AgentDefinition.model` 指定模型：
- `'inherit'` — 继承父级模型
- 具体模型名或别名 — 使用指定模型

Haiku 在 Claude Code 内部被用于后台辅助任务（安全分类器、压缩摘要生成等）。  
来源：源码分析（loadAgentsDir.ts，runAgent.ts）

### 9.3 模型降级

当主模型遇到连续 3 次 529（过载）错误时，触发 Fallback（Opus → Sonnet），并向用户显示警告消息（不静默切换）。  
来源：源码分析（withRetry.ts，MAX_OVERLOAD_CONSECUTIVE = 3）

---

## 10. MCP 集成

### 10.1 MCP 架构

| 特性 | 值 | 来源 |
|------|----|----|
| 协议 | Model Context Protocol（MCP） | 源码分析 |
| 工具注册 | 运行时动态注册，追加在内置工具之后 | 源码分析 |
| 排序策略 | 内置工具在前（缓存稳定），MCP 工具在后；新增 MCP 工具追加到末尾，不破坏内置工具的缓存位置 | 源码分析 |
| 资源访问 | ListMcpResourcesTool + ReadMcpResourceTool | 源码分析 |
| 沙箱权限 | Team Mode 中 Worker 可通过 `sandbox_permission_request` 消息向 Leader 申请权限 | 源码分析 |

### 10.2 本机已配置的 MCP 服务器

| MCP 服务器 | 工具前缀 | 功能 |
|-----------|---------|------|
| Gmail | `mcp__claude_ai_Gmail__*` | 邮件读取/草稿/搜索 |
| Google Calendar | `mcp__claude_ai_Google_Calendar__*` | 日历操作 |
| computer-use | `mcp__computer-use__*` | 桌面控制（截图/点击/键盘） |
| pencil | `mcp__pencil__*` | 设计工具（.pen 文件编辑） |

来源：实测（system-reminder 中可见 deferred MCP 工具列表）

### 10.3 对晶体设计的影响

- **MCP 工具不保证可用**：MCP 服务器由用户环境配置，晶体不应硬依赖特定 MCP 工具（除非晶体本身就是为特定 MCP 环境设计的）
- **MCP 工具是延迟加载的**：晶体如果需要 MCP 工具，应先通过 ToolSearch 搜索发现，再调用

---

## 11. 晶体编译指南（综合建议）

### 11.1 工具选择决策树

```
需要读取文件内容？
├─ 已知路径 → FileReadTool（分页读取大文件）
└─ 未知路径 → GlobTool 查找文件名，GrepTool 搜索内容

需要执行命令？
├─ 简单命令 → BashTool
├─ 复杂脚本（含 $()、<()、控制流）→ BashTool（预计需要用户确认或调整权限）
└─ 需要浏览器渲染 → BashTool + playwright/puppeteer（若可用）

需要网络访问？
├─ 搜索信息 → WebSearchTool
├─ 获取静态页面内容 → WebFetchTool
└─ API 调用 / 需要认证 → BashTool + curl

需要子任务并行？
└─ AgentTool（run_in_background: true）
```

### 11.2 状态管理策略

| 数据类型 | 推荐存储 | 原因 |
|---------|---------|------|
| 临时中间结果（< 1 轮） | context window 即可 | 不值得持久化 |
| 任务进度（跨多轮） | TodoWriteTool + 文件 | Todo 可见，文件可读 |
| 任务阶段性产物 | FileWriteTool（明确路径） | 可被后续工具读取 |
| 跨 session 用户偏好 | Persistent Memory | 自动在 session 间保留 |
| 会话检查点（防压缩丢失） | 文件（晶体自管理路径） | 比 session memory 更可控 |

### 11.3 上下文预算估算

```
200K tokens 可用空间分配（参考值）：
├─ System prompt（CLAUDE.md + 工具定义）: ~20-30K
├─ 压缩保留区（不可用）: ~13K
├─ 安全余量: ~10K
└─ 实际可用: ~150-160K tokens

超长任务（>150K tokens）建议：
├─ 每 20-30 轮写一次检查点文件
├─ 使用 /compact 手动压缩（可提供摘要提示）
└─ 将独立子任务委托给子代理（独立 context window）
```

### 11.4 权限声明建议

晶体应在说明中声明所需的权限级别，让用户在运行前确认：

```markdown
## 运行要求
- 权限模式：acceptEdits（推荐）或 auto
- 需要的工具：BashTool、FileReadTool、FileEditTool、WebSearchTool
- 网络访问：是（WebSearch + WebFetch）
- 写入范围：仅当前项目目录
```

---

## 附录：关键源码文件索引

| 文件 | 行数 | 功能 |
|------|------|------|
| `tools/AgentTool/AgentTool.tsx` | 1,397 | 子代理入口、路由决策 |
| `tools/AgentTool/runAgent.ts` | 973 | Agent 执行引擎 |
| `services/tools/toolExecution.ts` | 1,745 | 工具执行引擎（权限 + 执行 + Hooks） |
| `utils/toolResultStorage.ts` | 1,040 | 工具结果磁盘持久化 |
| `services/compact/` | ~3,900 | 五层上下文压缩系统 |
| `services/SessionMemory/` | 1,026 | Session Memory 管理 |
| `memdir/` | 1,736 | Persistent Memory 管理 |
| `utils/permissions/` | ~25,000 | 安全权限系统（8 层纵深防御） |
| `utils/bash/ast.ts` | - | Bash AST 安全分析 |
| `utils/model/model.ts` | - | 模型选择与 alias 解析 |
| `utils/modelCost.ts` | - | 价格表（内建） |

源码路径对应本地研究目录：`/Users/tangsir/Documents/openclaw/Doramagic/docs/research/claude-code-instructkr/`

---

*文档生成：Claude Sonnet 4.6 | 日期：2026-04-06 | 基于源码分析报告 + 实测验证*
