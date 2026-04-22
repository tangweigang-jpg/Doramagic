# OpenClaw 宿主能力规范

> **原则**：本文档只记录有配置文件或实测证据的事实。每条标注证据来源。
> **配置来源**：`~/.openclaw/openclaw.json` + `~/.openclaw/exec-approvals.json`
> **最后验证**：2026-04-06

---

## 一、执行环境

| 能力 | 值 | 证据 |
|------|---|------|
| 超时 | **1800 秒**（30 分钟） | `openclaw.json` → `agents.defaults.timeoutSeconds: 1800` |
| Sandbox | **关闭** | `openclaw.json` → `agents.defaults.sandbox.mode: "off"` |
| 工作目录 | `/Users/tangsir/.openclaw/workspace/doramagic` | `openclaw.json` → doramagic agent 配置 |
| 文件系统访问 | **不限于 workspace** | `openclaw.json` → `tools.fs.workspaceOnly: false` |
| Compaction | **safeguard 模式** | `openclaw.json` → `agents.defaults.compaction.mode: "safeguard"` |

## 二、模型

| 角色 | 模型 | Context Window | Max Tokens | 证据 |
|------|------|---------------|------------|------|
| Doramagic 主 agent | GLM-5 (bailian) | 204,800 | 131,072 | `openclaw.json` → doramagic agent `model: "bailian/glm-5"` |
| 子代理默认 | MiniMax-M2.7 | 200,000 | 8,192 | `openclaw.json` → `agents.defaults.subagents.model` |

## 三、工具能力

| 工具 | 状态 | 证据 |
|------|------|------|
| read（文件读取） | ✅ 可用 | 平台内置 |
| write（文件写入） | ✅ 可用，自动创建目录 | 平台内置 + v13 实测 |
| edit（文件编辑） | ✅ 可用，精确文本匹配 | 平台内置 + v5 实测（空白差异导致失败） |
| exec（命令执行） | ✅ 可用，security=full, ask=off | `exec-approvals.json` → `defaults.security: "full", ask: "off"` |
| web_search | ✅ 可用 | `openclaw.json` → `tools.web.search.enabled: true` |
| web_fetch | ✅ 可用 | `openclaw.json` → `tools.web.fetch.enabled: true` |

**注意**：`exec-approvals.json` 中 `autoAllowSkills: true`，skill 内的 exec 调用自动批准。

### exec 已知行为（实测）

| 行为 | 证据 |
|------|------|
| 拦截 shell 操作符（`&&`, `;`, `\|`） | v5/v7/v8 实测：报错 `complex interpreter invocation detected` |
| 支持 `python3 /absolute/path` 格式 | v9 实测通过 |
| 支持 `python3 -m py_compile` | v9 实测通过 |

**待验证**：exec preflight 的完整拦截规则（未找到源码级证据，仅有实测行为观测）。

## 四、子代理

| 能力 | 值 | 证据 |
|------|---|------|
| 最大并发 | 8 | `openclaw.json` → `subagents.maxConcurrent: 8` |
| 最大嵌套深度 | 2 | `openclaw.json` → `subagents.maxSpawnDepth: 2` |
| 每 agent 最大子代理 | 5 | `openclaw.json` → `subagents.maxChildrenPerAgent: 5` |
| 归档时间 | 60 分钟 | `openclaw.json` → `subagents.archiveAfterMinutes: 60` |

## 五、通信渠道

| 渠道 | 状态 | 证据 |
|------|------|------|
| Telegram | ✅ 已启用 | `openclaw.json` → `channels.telegram.enabled: true` |
| 私聊策略 | pairing | `openclaw.json` → `channels.telegram.dmPolicy: "pairing"` |
| 群组策略 | open, requireMention | `openclaw.json` → `channels.telegram.groupPolicy` |

## 六、Skill 加载

| 能力 | 值 | 证据 |
|------|------|------|
| autoAllowSkills | true | `exec-approvals.json` |
| SKILL.md body 中 `{baseDir}` 不插值 | 已确认 | v13 实测（ENOENT 报错） |
| read 相对路径基于 workspace root | 已确认 | v13 实测 |

## 七、已知限制与待验证项

### 已知限制（有实测证据）

| 限制 | 证据 |
|------|------|
| edit_file 精确匹配失败（空白差异） | v5 实测 |
| exec 拦截链式 shell 命令 | v5/v7/v8 实测 |
| `{baseDir}` 不在 SKILL.md body 中插值 | v13 实测 |

### 待验证（无源码/配置级证据）

| 项目 | 当前假设 | 风险 |
|------|---------|------|
| SKILL.md 行数上限 | "80 行后注意力衰减" | 已安装 skill 有 1049 行的在运行，80 行可能过于保守 |
| Telegram 消息长度限制 | "无硬限制" | Telegram Bot API 有 4096 字符限制，但 OpenClaw 可能分段发送 |
| exec preflight 完整规则 | "拦截所有 shell 操作符" | 仅有实测行为，未见源码 |
| compaction safeguard 模式行为 | "压缩上下文" | 配置存在，具体行为未文档化 |

---

## 八、对晶体设计的影响

基于以上事实，晶体设计的平台约束应为：

| 约束 | 来源 | 影响 |
|------|------|------|
| 超时 1800 秒 | 配置文件 | 多文件方案有足够时间，不必强制单文件 |
| GLM-5 context 204K | 配置文件 | 晶体内容量不受 8KB 限制，但需考虑注意力分配 |
| exec security=full | 配置文件 | exec 可用但需遵守 preflight 规则 |
| web 工具可用 | 配置文件 | 晶体可以指导 AI 联网获取数据 |
| 子代理可用 | 配置文件 | 复杂任务可拆分为子代理并行 |

---

*文档版本 v1.0 | 2026-04-06 | 来源：`~/.openclaw/openclaw.json` + `~/.openclaw/exec-approvals.json` + v5-v9 实测*
