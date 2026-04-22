# deer-flow 深度灵魂提取报告

**日期**: 2026-03-28
**研究对象**: [bytedance/deer-flow](https://github.com/bytedance/deer-flow) v2.0 (~25k stars)
**研究方法**: Opus 深度源码阅读 + 设计模式分析
**目的**: 提取可迁移到 Doramagic 的架构模式和设计哲学

---

## 一、项目概况

DeerFlow (Deep Exploration and Efficient Research Flow) 是字节跳动开源的 agent harness。从研究工具演变为通用 agent 运行时——不是 agent 框架（给开发者组件），而是 agent 基础设施（给 agent 运行环境）。

**核心架构**: Harness-as-OS
- 虚拟文件系统 (`/mnt/user-data/`)
- 进程管理（sub-agent spawning + 超时 + 并发限制）
- 中间件管线（12 层有序 middleware）
- 持久化存储（memory system，跨 session）
- 设备驱动抽象（sandbox providers, MCP tools, search providers）

**技术栈**: 建在 LangGraph 之上。LangGraph 是内核，DeerFlow 是完整 Linux 发行版。

---

## 二、设计哲学

> 不是给开发者提供框架（你来组装），而是给 agent 提供运行时（agent 在里面工作）。

两大支柱：
1. **Harness 思维**: Agent 得到一个有文件系统、沙箱、内存管理的完整环境，而非一堆 API。
2. **关注点分离**: harness 层和 app 层严格隔离，CI 测试 (`test_harness_boundary.py`) 自动阻止跨层 import。

---

## 三、WHY 决策（8 条关键架构选择）

### 1. 单一 Lead Agent + 动态 Sub-Agent（非预定义多 Agent 图）
**WHY**: 静态 multi-agent 图强制开发者预定义 agent 拓扑。DeerFlow 让 LLM 在运行时决定分解策略。更灵活，但要求 lead agent 足够聪明。

### 2. 12 层有序 Middleware Pipeline（非事件钩子）
**WHY**: 横切关注点（summarization、memory、loop detection、clarification）需要可预测的执行顺序。Pipeline 让依赖关系显式可调试。和 ASGI/Koa.js 中间件同一模式。

排列：ThreadData -> Uploads -> Sandbox -> Summarization -> TodoList -> TokenUsage -> Title -> Memory -> ViewImage -> DeferredToolFilter -> SubagentLimit -> LoopDetection -> Clarification

### 3. 虚拟路径翻译（Sandbox 无关性）
**WHY**: Agent 代码永远引用 `/mnt/user-data/workspace`，物理路径由 sandbox provider 解析。同一份 prompt 在本地/Docker/K8s 上都能跑。

### 4. 渐进式 Skill 加载（非全量加载）
**WHY**: Token 经济。System prompt 只放 skill 元数据（名称、描述、路径），agent 需要时 `read_file` 拉取全文。和 Claude Code 的 deferred tool loading 同一模式。

### 5. Deferred Tool Registry（MCP 扩展性）
**WHY**: MCP server 可能暴露几十个 tool。全部绑定 LLM 会增大 prompt + 降低工具选择准确性。只暴露名称，`tool_search` 按需拉 schema。

### 6. 异步 Memory 提取（30s debounce + 后台 LLM）
**WHY**: Memory 更新需要 LLM 调用，不应阻塞对话。Debounce 防止快速问答中的过度调用。显式清洗上传文件引用（防止 agent 在未来 session 找不到已删文件）。

### 7. Sub-Agent 禁止递归嵌套
**WHY**: 递归 sub-agent 产生无界资源消耗 + 调试噩梦。单层委托：lead -> sub-agents -> tools。`MAX_CONCURRENT_SUBAGENTS = 3`。

### 8. Clarification-First（CLARIFY -> PLAN -> ACT 优先级）
**WHY**: "边干边问"浪费 token 且产出错误结果。不确定时完全停止执行，等用户回应。

---

## 四、UNSAID 暗雷

| 严重度 | 暗雷 |
|--------|------|
| HIGH | "聪明 Lead Agent" 单点故障——弱模型会导致分解质量非线性下降 |
| HIGH | 本地 Sandbox 默认不隔离——LLM 生成的代码以用户权限执行 |
| MEDIUM | Memory 全局存储无用户隔离——多租户场景会泄露知识 |
| MEDIUM | Sub-agent timeout 是 best-effort——Python ThreadPoolExecutor.cancel() 无法中断运行中线程 |
| LOW | Config 文件共享（Gateway 和 LangGraph Server 通过文件系统共享状态，无锁） |

---

## 五、对 Doramagic 的 3 个范式级启发

### 范式 1: Middleware Pipeline 替代单体 Pipeline

**deer-flow**: 12 层 middleware，每层一个关注点，有序组合。
**Doramagic 现状**: singleshot.py 2500 行单体，main() 函数从头跑到尾。

**改进方向**: 把 Doramagic 的 7 步管线重构为 middleware chain:
```
ProfileMiddleware -> DiscoveryMiddleware -> RelevanceGateMiddleware
-> ExtractionMiddleware -> CommunityMiddleware -> SynthesisMiddleware
-> CompileMiddleware -> QualityGateMiddleware -> DeliveryMiddleware
```

每个 middleware:
- 读取上游的 pipeline state
- 执行自己的逻辑
- 写入 state 供下游消费
- 可以 short-circuit（提前终止管线）

**好处**:
- 每步独立可测试
- 不同场景可组合不同 middleware（快速提取跳过 Community + Quality Gate）
- 横切关注点（logging、timing、checkpoint）可以作为通用 middleware
- 新步骤（web search fallback）只需插入新 middleware

### 范式 2: 动态分解替代固定流程

**deer-flow**: Lead agent 决定要不要 spawn sub-agent、做什么。
**Doramagic 现状**: 不管什么输入，固定跑全量管线。

**改进方向**: Doramagic 的 orchestrator 可以根据**中间结果**动态调整:
- Profile 阶段发现高置信度 + ClawHub 有完美匹配 -> 跳过 GitHub + 浅提取
- GitHub 找到 3 个高质量 repo -> 并行 3 个 sub-extraction
- 综合阶段发现知识冲突 -> 追加验证步骤
- 编译后质量门禁 < 60 -> 重新提取最弱维度

这和 web-access 的"目标驱动调度"一致，deer-flow 提供了实现模型。

### 范式 3: Prompt-as-Configuration（动态 System Prompt）

**deer-flow**: `apply_prompt_template()` 根据运行时条件动态拼装 system prompt。
**Doramagic 现状**: `SKILL_ARCHITECT_SYSTEM` 是 1200 字符静态常量。

**改进方向**: 根据提取上下文动态生成编译指令:
- SHALLOW 模式: 简化编译 prompt，跳过 Decision Framework
- DEEP 模式: 添加 commit 挖掘指令 + Tree-sitter 骨架引用
- 高风险域: 自动注入安全 disclaimer 模板
- 有 brick 匹配: 注入域基线知识作为 few-shot

---

## 六、可直接采纳的 4 个模式

### 模式 1: CI 边界测试
**实现**: 一个 pytest 文件扫描 `scripts/` 的 import，验证不会直接 import `packages/` 的内部模块（只通过 public API）。反之亦然。
**投入**: 1 小时
**价值**: 防止架构退化

### 模式 2: Deferred Brick Loading
**实现**: brick 元数据（id, domain, tags, statement 摘要）常驻内存。完整 brick 内容（knowledge_type, confidence, full statement）按需从 JSONL 拉取。
**投入**: 半天
**价值**: Token 经济 + 防止无关 brick 污染 prompt

### 模式 3: 异步域经验写入
**实现**: 提取完成后，后台线程将验证过的知识写入 `bricks/accumulated/{domain}.jsonl`。Debounce 防止同域频繁写入。
**投入**: 半天
**价值**: 将 web-access 的"站点经验积累"和 deer-flow 的"异步 memory"两个模式合并落地

### 模式 4: Pipeline State Object
**实现**: 替代当前 main() 中的 20+ 个局部变量，用一个 `PipelineState` dataclass 在步骤间传递状态。这是 middleware pipeline 的前置条件。
**投入**: 2 小时
**价值**: 为未来 middleware 重构打基础，且立即改善代码可读性

---

## 七、和 web-access 研究的交叉验证

| 设计原则 | web-access | deer-flow | Doramagic 应用 |
|----------|-----------|-----------|---------------|
| 目标驱动 vs 步骤驱动 | 浏览哲学四步 | 动态 sub-agent 分解 | 管线调度从固定流程改为结果反馈 |
| 渐进式加载 | 三层通道升级 | Deferred tool + skill loading | Brick 元数据先加载，内容按需 |
| 知识积累 | site-patterns/ | Memory 系统（异步+debounce） | accumulated bricks + 异步写入 |
| 架构隔离 | scripts/ vs references/ | harness vs app + CI 测试 | packages vs scripts + CI |
| 过期意识 | "提示而非保证" | upload 引用清洗 | brick 时间戳 + 置信衰减 |

两个项目从完全不同的角度（联网工具 vs agent 运行时）得出了高度一致的设计原则。这增强了这些原则的可信度。

---

## 八、总结

deer-flow 最大的启发不是具体技术（LangGraph、middleware、MCP），而是**思维方式的转变**:

> 从"我要写一个提取管线" 到 "我要建一个提取运行时"

Doramagic 当前是 pipeline 思维——一条线从头跑到尾。deer-flow 展示了 harness 思维——提供环境让 agent 自己决定怎么跑。

**短期落地**（本轮改版可做）:
1. PipelineState dataclass
2. CI 边界测试
3. Deferred brick loading

**中期架构**（需要专门 session）:
4. Middleware pipeline 重构 singleshot.py
5. 动态管线调度（基于中间结果的步骤增减）
6. 异步域经验积累

**长期愿景**:
7. Doramagic 从"提取管线"进化为"知识提取运行时"

> **DeerFlow 是 LangGraph 的 Linux 发行版。Doramagic 应该成为知识提取的 Linux 发行版。**
