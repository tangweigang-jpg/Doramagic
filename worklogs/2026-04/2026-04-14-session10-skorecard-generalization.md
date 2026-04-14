# 工作日志：bp-050 (skorecard) 泛化验证 + v6.1 系统性改版

> 日期：2026-04-14
> 会话：session 10（约 3 小时）
> 目标：验证蓝图提取 agent 对非 zvt 项目的泛化能力

---

## 一、核心发现

bp-050 (skorecard) 暴露了 agent 对 bp-009 (zvt) 的**过拟合**。6 轮尝试中每次修一个 skorecard 特有问题就暴露下一个：

| 轮次 | 失败点 | zvt 为什么没遇到 |
|------|--------|-----------------|
| 1 | worker_audit 50/50 超时 | zvt 的 audit 30 轮内完成 |
| 2 | worker_audit context overflow | zvt 的 skeleton 更小 |
| 3 | context overflow 死循环 | zvt 没触发 overflow |
| 4 | bp_uc_extract 缺 artifact | zvt 有 examples/ |
| 5 | blueprint.yaml placeholder 无效 YAML | zvt 的 assembly 不需要 placeholder |
| 6 | — | 等待验证中 |

**根本问题**：每个 handler 有多条退出路径（早退/RawFallback/error/overflow），每条路径都需要写 required artifact。逐个 handler 打补丁不可持续。

---

## 二、系统性解决方案

### 核心设计原则

**"executor 层统一兜底——handler 永远不需要担心 artifact 缺失"**

`_check_required_artifacts` 现在是三层保障：
1. Handler 自己写（正常路径）
2. Auto-save 从 LLM response 提取（降级路径）
3. **格式化 placeholder 生成**（最终兜底，**永不返回 still_missing**）

### v6.1 改版内容（6 个 commit）

| Fix | 内容 | commit |
|-----|------|--------|
| tool result 截断 | 单个工具返回限制 30K chars（get_skeleton 96K → 30K） | 5e6765e |
| context overflow 断路器 | 3 次 compact 失败后退出，不死循环 | d2a967d |
| microcompact 启用 | Worker 主循环每轮清理旧 tool results | 68d579e |
| checkpoint 注入 | 每 10 轮催促 Worker 写 artifact | 5e6765e |
| uc_extract 空 examples 兜底 | 无 examples/ 时写空 `[]` | — |
| **executor 统一安全网** | `_check_required_artifacts` 永不返回 still_missing | 761fc5e |
| placeholder 格式化 | .yaml→mapping, .json→{}, .jsonl→空, .md→文本 | 761fc5e |

### 关键改进：executor 统一安全网

```
before: handler 忘记写 artifact → auto-save 失败 → still_missing → 管线停止
after:  handler 忘记写 artifact → auto-save 失败 → placeholder 生成 → 管线继续
```

这一个改动解决了**一类问题**：
- 任何 handler 的任何退出路径忘记写 artifact → 不阻断
- 任何新项目缺少 examples/tests/docs → 不阻断
- 任何 Instructor 全降级到 L3 → 不阻断

---

## 三、其他并行工作

### 研究报告

| 报告 | 路径 | 关键借鉴 |
|------|------|---------|
| Meta-Harness 深度研究 | `docs/research/2026-04-14-meta-harness-deep-research.md` | 执行 trace 存档（已实现）、Patch 消融、仓库快照预热 |
| LlamaIndex 深度研究 | `docs/research/2026-04-14-llamaindex-deep-research.md` | Worker checkpoint 注入（已实现）、确定性/LLM 分层评估 |

### 执行 trace 存档（Meta-Harness 启发）

已实现 `_save_trace()` — 每次 L2 失败和 L3 fallback 保存 prompt + raw output + error 到 `_runs/{bp_id}/traces/`。为后续系统性诊断积累数据。

---

## 四、踩坑记录

### 坑 10：过拟合于单一测试项目

在 bp-009 (zvt) 上反复调试 10 个版本，隐含假设了"有 examples 目录"、"skeleton < 30K"、"audit 30 轮够用"。换 skorecard 就全暴露。教训：每次改版后至少在 2 个不同类型项目上验证。

### 坑 11：逐个 handler 打补丁是反模式

5 轮 bp-050 失败中，前 4 轮都是"在出问题的 handler 里加兜底代码"。正确做法：找到**统一保障层**（executor 的 `_check_required_artifacts`），一次性解决一类问题。

### 坑 12：tool result 无大小限制

`get_skeleton()` 返回 96K chars 直接打爆 context window。之前从未暴露因为 zvt 的 skeleton 较小。所有工具返回应有大小上限。

---

## 五、Commit 列表（本 session）

```
761fc5e feat(executor): universal artifact safety net — never halt on missing artifacts
68d579e fix(agent_loop): enable microcompact in Worker main loop
d2a967d fix(agent_loop+executor): context overflow circuit breaker + placeholder artifacts
5e6765e feat(agent_loop): v6.1 — tool result truncation + checkpoint injection
af9b6b2 fix(phases): worker_audit max_iterations 40→50
acf15be fix(executor): generate placeholder artifact when worker hits max_iterations
9cc4fdf feat(agent_loop): execution trace archive for L2/L3 failures
8668d49 fix(prompts): iteration budget warnings for worker_verify and worker_audit
```

---

*最后更新: 2026-04-14 10:15*
