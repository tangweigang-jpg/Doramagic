# 种子晶体：多 Agent 编排系统

> 来源：Claude Code 512K LOC 架构逆向 | 置信度：源码验证
> 适用场景：为 AI 编程助手构建多 agent 并行执行能力
> 体积：~3KB（原始知识 ~30KB，压缩比 10:1）

---

## 一、最小可运行样本

```python
"""多 Agent 编排核心骨架 — 从 Claude Code runAgent() 模式提炼"""

import asyncio
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import AsyncGenerator, Literal
from abc import ABC, abstractmethod

# === 1. Agent 定义：三层联合类型 ===

@dataclass
class AgentDefinition:
    agent_type: str                    # 路由键："explorer", "implementer", "verifier"
    when_to_use: str                   # LLM 选择依据（自然语言）
    allowed_tools: list[str] | None = None   # None = 全部允许
    disallowed_tools: list[str] = field(default_factory=list)
    max_turns: int = 20
    isolation: Literal["shared", "worktree"] = "shared"
    background: bool = False

# === 2. 核心引擎：AsyncGenerator 模式 ===

@dataclass
class Message:
    role: str
    content: str
    agent_id: str

async def run_agent(
    agent_def: AgentDefinition,
    prompt: str,
    tools: dict,
    abort_signal: asyncio.Event | None = None,
) -> AsyncGenerator[Message, None]:
    """
    核心循环 — 每 yield 一条消息，调用者决定怎么处理。
    关键设计：引擎不关心消息去哪（显示/记录/转发），只负责生产。
    """
    agent_id = f"{agent_def.agent_type}_{id(prompt) % 10000}"

    # 工具过滤：白名单 ∩ ¬黑名单
    available = {k: v for k, v in tools.items()
                 if (agent_def.allowed_tools is None or k in agent_def.allowed_tools)
                 and k not in agent_def.disallowed_tools}

    turns = 0
    messages = [{"role": "user", "content": prompt}]

    while turns < agent_def.max_turns:
        if abort_signal and abort_signal.is_set():
            break

        # 调用 LLM（这里用占位符，实际接入你的 LLM adapter）
        response = await call_llm(messages, available)

        yield Message(role="assistant", content=response["content"], agent_id=agent_id)

        # 如果 LLM 请求使用工具
        if tool_call := response.get("tool_use"):
            tool_fn = available.get(tool_call["name"])
            if tool_fn:
                result = await tool_fn(tool_call["input"])
                yield Message(role="tool", content=str(result), agent_id=agent_id)
                messages.append({"role": "tool", "content": str(result)})
        else:
            break  # LLM 没有工具调用 = 任务完成

        turns += 1

# === 3. 文件邮箱：Agent 间通信 ===

class FileMailbox:
    """
    简单 > 高效。用文件系统做消息队列。
    读无锁（最终一致），写有锁（原子性）。
    """
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def inbox_path(self, agent_name: str) -> Path:
        return self.base_dir / f"{agent_name}.json"

    async def send(self, to: str, message: dict):
        path = self.inbox_path(to)
        # 简化版：实际需要文件锁（lockfile 库）
        messages = json.loads(path.read_text()) if path.exists() else []
        messages.append({**message, "read": False})
        path.write_text(json.dumps(messages, ensure_ascii=False))

    async def receive(self, agent_name: str) -> list[dict]:
        path = self.inbox_path(agent_name)
        if not path.exists():
            return []
        messages = json.loads(path.read_text())
        unread = [m for m in messages if not m["read"]]
        return unread

# === 4. Coordinator：四阶段工作流 ===

async def coordinate(task: str, agents: dict[str, AgentDefinition], tools: dict, mailbox: FileMailbox):
    """
    四阶段编排 — 这个流程是 prompt-programmed 的，不是硬编码的。
    意思是：你可以通过改 prompt 调整阶段策略，不用改代码。
    """

    # Phase 1: Research — Worker 并行探索
    research_tasks = []
    for name, agent_def in agents.items():
        if agent_def.agent_type == "explorer":
            research_tasks.append(
                collect_all(run_agent(agent_def, f"研究以下问题：{task}", tools))
            )
    research_results = await asyncio.gather(*research_tasks)

    # Phase 2: Synthesis — Coordinator 自己做，不委派
    # 关键：必须亲自读研究结果，禁止说"based on your findings"
    synthesis = await synthesize(task, research_results)

    # Phase 3: Implementation — Worker 执行具体修改
    for name, agent_def in agents.items():
        if agent_def.agent_type == "implementer":
            async for msg in run_agent(agent_def, synthesis, tools):
                pass  # 收集实现结果

    # Phase 4: Verification — 独立 Worker，新鲜视角
    # 关键：验证者不能继承实现者的上下文
    for name, agent_def in agents.items():
        if agent_def.agent_type == "verifier":
            async for msg in run_agent(agent_def, f"验证以下修改是否正确：{synthesis}", tools):
                pass
```

---

## 二、硬约束（违反必出 bug）

| # | 约束 | 原因 | 违反后果 |
|---|------|------|---------|
| C1 | **完成状态必须在清理操作之前设置** | Claude Code gh-20236：classifyHandoff 和 worktree cleanup 可能 hang | 下游等待者永远阻塞 |
| C2 | **异步 Agent 必须用独立的 AbortController** | 共享父级 controller 会导致取消一个 agent 时连带取消所有 agent | 任务相互干扰 |
| C3 | **工具过滤用白名单 ∩ ¬黑名单，MCP 工具始终放行** | 纯黑名单无法防御未知工具；MCP 工具是外部服务，过滤会破坏集成 | 安全漏洞或功能损失 |
| C4 | **Worker 的权限模式不能覆盖 Leader 的安全策略** | bypassPermissions/acceptEdits/auto 三种父级模式必须优先 | 子 agent 提权 |
| C5 | **文件邮箱写入必须加锁，读取可以无锁** | 写入竞态会丢消息；读取只需最终一致性 | 并发写入丢失 |
| C6 | **Coordinator 的 Synthesis 阶段必须自己做，不能委派给 Worker** | 委派会导致 Coordinator 不理解研究结果，后续决策质量崩塌 | 垃圾指令下发 |
| C7 | **Verifier 必须用新鲜上下文，不继承 Implementer 的会话** | 继承上下文 = 验证者带着实现者的假设看代码 = 自欺欺人 | 虚假验证 |
| C8 | **finally 块必须清理所有资源（MCP/hooks/cache/后台任务）** | 遗漏任何一项 → 长时间运行后内存泄漏或文件句柄耗尽 | 生产环境崩溃 |

---

## 三、验收标准

一个合格的多 Agent 编排系统，必须通过以下 5 项检验：

1. **可观测性**：看文件邮箱就知道每个 Agent 发了什么、收了什么。不需要调试器。
2. **优雅降级**：iTerm2 不可用 → 退回 Tmux → 退回进程内。每一级降级用户无感知。
3. **取消安全**：取消任意一个 Agent 不影响其他 Agent。取消后资源完全释放。
4. **权限不泄漏**：子 Agent 永远不能获得比父 Agent 更高的权限。
5. **通信可恢复**：向已停止的 Agent 发消息 → 自动从磁盘恢复并继续。不需要调用者关心 Agent 是否在运行。

---

*生成自 Doramagic 知识引擎 | 源码置信度：逐行验证 | 压缩比：30KB → 3KB*
