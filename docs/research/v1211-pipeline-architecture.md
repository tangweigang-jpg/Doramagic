# Doramagic v12.1.1 管线架构设计

**日期**: 2026-03-28
**作者**: Claude Opus 4.6 (首席架构师角色)
**状态**: 设计文档，待评审
**输入来源**: web-access 标杆研究 + DeerFlow 标杆研究 + Codex 报告 + E2E 测试发现 + 现有代码审计

---

## 目录

1. [架构总览](#1-架构总览)
2. [输入路由器（Input Router）](#2-输入路由器input-router)
3. [条件边设计（Conditional Edges）](#3-条件边设计conditional-edges)
4. [扇出/扇入设计（Fan-out / Fan-in）](#4-扇出扇入设计fan-out--fan-in)
5. [降级交付定义（Degraded Delivery）](#5-降级交付定义degraded-delivery)
6. [进度事件设计（Run Events）](#6-进度事件设计run-events)
7. [对现有代码的影响评估](#7-对现有代码的影响评估)
8. [版本边界：v12.1.1 vs 后续版本](#8-版本边界v1211-vs-后续版本)

---

## 1. 架构总览

### 1.1 当前问题的根因分析

六个暴露问题归结为两个结构性缺陷：

**缺陷 A：无路由（No Routing）**
- 所有输入走同一条线性路径，无论用户给了 URL、项目名还是模糊描述
- Profile Builder 泛化一切输入，丢弃精确信息
- 问题 1（丢弃意图）和问题 2（同一条路）的共同根因

**缺陷 B：无反馈环（No Feedback Loop）**
- 线性串行 = 不可见 + 不可中断 + 不可降级
- 质量把控只在终点 = 4 分钟白费
- 问题 3（效率脆弱）、问题 4（黑盒）、问题 5（只有终点门禁）、问题 6（降级虚设）的共同根因

### 1.2 目标架构：条件 DAG 状态机

```
                        ┌─────────────┐
                        │  INIT       │
                        └──────┬──────┘
                               │
                        ┌──────▼──────┐
                        │  PHASE_A    │ NeedProfileBuilder
                        │  + Router   │
                        └──────┬──────┘
                               │
                    ┌──────────┼──────────┐
                    │          │          │
              ┌─────▼────┐    │    ┌─────▼────────┐
              │ CLARIFY  │    │    │ PHASE_B      │
              │ (pause)  │    │    │ Discovery    │
              └─────┬────┘    │    └─────┬────────┘
                    │         │          │
                    └─────────┘          │
                               ┌────────▼────────┐
                               │   PHASE_C       │
                               │   Fan-out:      │
                               │   Repo Workers  │
                               │   [W1][W2][W3]  │
                               └────────┬────────┘
                                        │ fan-in
                               ┌────────▼────────┐
                               │   PHASE_D       │
                               │   Synthesis     │
                               └────────┬────────┘
                                        │
                               ┌────────▼────────┐
                               │   PHASE_E       │
                               │   Compile       │
                               └────────┬────────┘
                                        │
                               ┌────────▼────────┐
                               │   PHASE_F       │
                               │   Validate      │
                               │   + QA Gate     │
                               └───┬────┬────┬───┘
                                   │    │    │
                              PASS │ REVISE  │ BLOCKED
                                   │    │    │
                            ┌──────▼┐   │  ┌─▼──────┐
                            │PHASE_G│   │  │DEGRADED│
                            │Package│   │  │Delivery│
                            └───┬───┘   │  └────────┘
                                │       │
                            ┌───▼───┐   │
                            │ DONE  │◄──┘ (max 1 revise)
                            └───────┘
```

### 1.3 与当前架构的关键差异

| 维度 | v12.1.0（当前） | v12.1.1（目标） |
|------|----------------|----------------|
| 路由 | 无，所有输入同路 | Input Router 确定性分流 |
| 提取 | PHASE_CD 串行大包 | PHASE_C fan-out 独立 workers |
| 社区 | Step 4 全局串行 | 每个 worker 内部含社区采集 |
| 合成 | PHASE_E | PHASE_D（提前，独立于编译） |
| 编译 | PHASE_F | PHASE_E（保持） |
| 验证 | PHASE_G 终点门禁 | PHASE_F 验证+靶向修复 |
| 降级 | 全局布尔值，形同虚设 | 每阶段定义最低交付物 |
| 进度 | stdout 打印 | run_events.jsonl 结构化事件 |
| 反馈 | 无 | REVISE 回编译（最多 1 次） |

### 1.4 Phase 命名重映射

为消除现有 PHASE_A~H 的混淆（当前 PHASE_CD 是一个阶段处理两件事），重新定义：

| 新 Phase | 职责 | 旧 Phase 对应 |
|----------|------|--------------|
| PHASE_A | Need Profile + Input Router | PHASE_A（增强） |
| PHASE_B | Discovery（搜索候选 repo） | PHASE_B（保持） |
| PHASE_C | Fan-out Repo Workers（提取+社区） | PHASE_CD（拆分+并行化） |
| PHASE_D | Synthesis（合成） | PHASE_E（前移） |
| PHASE_E | Compile（编译 SKILL.md） | PHASE_F（前移） |
| PHASE_F | Validate + QA Gate | PHASE_G（增强） |
| PHASE_G | Package + Deliver | PHASE_H（保持） |

**WHY**: 当前 PHASE_CD 把"提取"和"社区采集"捆绑在一个阶段，导致无法独立控制。拆开后每个阶段职责单一，条件边更清晰。合成从 E 前移到 D，因为合成是提取的直接消费者，中间不应有其他阶段。

---

## 2. 输入路由器（Input Router）

### 2.1 设计哲学

**WHY 不用 LLM 做路由**: 路由是确定性的结构判断（正则 + 模式匹配），不需要理解语义。用 LLM 路由会引入不确定性（同一输入可能路由到不同路径）、延迟（额外一次 API 调用）和成本。只有当所有确定性规则都无法匹配时，才需要 LLM 判断——此时对应的就是"低置信"分支。

**WHY 路由在 PHASE_A 内部而非独立阶段**: 路由依赖 NeedProfile 的结构化输出（confidence、intent 类型、是否有 URL）。如果路由独立成 PHASE_A_ROUTE，那 NeedProfileBuilder 和 Router 之间需要额外的状态传递。放在 PHASE_A 末尾，作为 NeedProfileBuilder 输出的确定性后处理，最简单。

### 2.2 输入类型分类

路由器接受 NeedProfile 作为输入，根据以下确定性规则生成 `RoutingDecision`：

```python
@dataclass
class RoutingDecision:
    """确定性路由决策，由 Input Router 生成。"""
    route: Literal[
        "DIRECT_URL",       # 用户给了精确 URL
        "NAMED_PROJECT",    # 用户指名了项目
        "DOMAIN_EXPLORE",   # 领域探索
        "LOW_CONFIDENCE",   # 模糊/低置信
    ]
    skip_discovery: bool         # 是否跳过 PHASE_B
    max_repos: int               # 提取上限
    repo_urls: list[str]         # 预解析的 URL（DIRECT_URL 路由时填充）
    project_names: list[str]     # 预解析的项目名（NAMED_PROJECT 路由时填充）
    confidence: float            # 路由置信度
    reasoning: str               # 路由理由（用于 run_events 审计）
```

### 2.3 四条路由路径

#### 路径 1: DIRECT_URL（精确 URL）

**触发条件**（确定性正则）:
```python
URL_PATTERN = re.compile(
    r'https?://github\.com/[\w.-]+/[\w.-]+/?'
    r'|https?://gitlab\.com/[\w.-]+/[\w.-]+/?'
    r'|https?://gitee\.com/[\w.-]+/[\w.-]+/?'
)
urls = URL_PATTERN.findall(profile.raw_input)
if urls:
    route = "DIRECT_URL"
```

**执行路径**:
```
PHASE_A --> [跳过 PHASE_B] --> PHASE_C (workers for given URLs) --> PHASE_D --> PHASE_E --> PHASE_F --> PHASE_G
```

**跳过**: PHASE_B（Discovery）完全跳过。用户已经告诉你要分析什么。

**WHY**: 当用户说"帮我提取 https://github.com/org/repo 的设计灵魂"，跑 Discovery 是纯粹浪费。直接克隆并提取。

**示例**:
- "提取 https://github.com/bytedance/deer-flow 的设计灵魂" -> `DIRECT_URL`, skip_discovery=True, repo_urls=["https://github.com/bytedance/deer-flow"], max_repos=1
- "对比 https://github.com/a/b 和 https://github.com/c/d" -> `DIRECT_URL`, skip_discovery=True, repo_urls=[...], max_repos=2

#### 路径 2: NAMED_PROJECT（项目名）

**触发条件**（确定性规则）:
```python
# 规则：raw_input 中出现形如 "org/repo" 的 token，或已知项目名
REPO_SLUG_PATTERN = re.compile(r'\b([\w.-]+/[\w.-]+)\b')
slugs = REPO_SLUG_PATTERN.findall(profile.raw_input)
# 过滤掉常见的非 repo 模式（如 "iOS/Android", "HTTP/2"）
slugs = [s for s in slugs if not _is_false_positive_slug(s)]

# 或者：profile 的 keywords 中包含高置信项目名
# 判断标准：单个连字符分隔词 + 全小写 + 无空格 = 大概率是项目名
project_names = [kw for kw in profile.keywords
                 if re.match(r'^[a-z0-9]([a-z0-9-]*[a-z0-9])?$', kw)
                 and len(kw) >= 3]

if slugs or project_names:
    route = "NAMED_PROJECT"
```

**执行路径**:
```
PHASE_A --> PHASE_B (targeted search for named project) --> PHASE_C --> PHASE_D --> PHASE_E --> PHASE_F --> PHASE_G
```

**PHASE_B 行为变化**: Discovery 不是全域搜索，而是靶向搜索。用 `project_names` 直接查 GitHub（`repo:org/name` 语法），如果命中则只返回该 repo + 最多 1 个相关 repo。

**WHY**: "帮我提取 web-access 的设计灵魂"——用户知道自己要什么，但没给 URL。Discovery 的职责变成"找到这个项目的确切 URL"，而不是"找类似的项目"。

**示例**:
- "提取 web-access 的设计灵魂" -> `NAMED_PROJECT`, project_names=["web-access"], max_repos=2
- "分析 deer-flow 和 langchain 的架构差异" -> `NAMED_PROJECT`, project_names=["deer-flow", "langchain"], max_repos=2

#### 路径 3: DOMAIN_EXPLORE（领域探索）

**触发条件**:
```python
if profile.confidence >= 0.7 and not urls and not project_names:
    route = "DOMAIN_EXPLORE"
```

**执行路径**:
```
PHASE_A --> PHASE_B (broad discovery) --> PHASE_C (fan-out, max 3 repos) --> PHASE_D --> PHASE_E --> PHASE_F --> PHASE_G
```

**完整管线执行**, max_repos=3。这是当前 singleshot 默认路径的升级版。

**WHY**: 用户说"帮我做记账app"，profile builder 能理解意图但用户没指定项目。需要完整 Discovery 来找到最相关的项目。

**示例**:
- "帮我做一个记账app" -> `DOMAIN_EXPLORE`, max_repos=3
- "WiFi密码管理工具的设计灵魂" -> `DOMAIN_EXPLORE`, max_repos=3

#### 路径 4: LOW_CONFIDENCE（模糊/低置信）

**触发条件**:
```python
if profile.confidence < 0.7:
    route = "LOW_CONFIDENCE"
```

**执行路径**:
```
PHASE_A --> PHASE_A_CLARIFY (Socratic Gate, pause) --> 用户回复 --> PHASE_A (re-profile) --> 路由重新判定
```

**管线暂停**, 进入 Socratic Gate 追问。当前已有此逻辑（singleshot Step 1.5），保留并增强。

**WHY**: "帮我做个东西"——profile builder 无法建立有效的搜索策略。与其盲搜浪费预算，不如花 30 秒追问。

**增强**:
- Socratic Gate 最多追问 2 轮（当前只追问 1 轮）
- 追问后重新走 NeedProfileBuilder，重新进路由判定
- 如果 2 轮追问后 confidence 仍 < 0.7 -> 降级到 DOMAIN_EXPLORE（用最佳猜测搜索）

### 2.4 RoutingDecision 的持久化

路由决策写入 `run_events.jsonl` 和 `controller_state.json`。两个目的：
1. **审计**: 为什么这次 run 跳过了 Discovery？查 RoutingDecision。
2. **恢复**: 如果 run 中断，恢复时可以从 RoutingDecision 重建执行路径。

---

## 3. 条件边设计（Conditional Edges）

### 3.1 设计原则

**所有路由信号都是确定性的（代码判断，不是 LLM 判断）**。原因：
- 可重复性：同样的输入 + 同样的中间结果 = 同样的路由
- 可调试性：路由决策可以被日志追踪和单元测试
- 成本：路由判断不应花 LLM tokens

唯一例外：NeedProfileBuilder 内部用 LLM 理解用户意图。但它的输出（NeedProfile）是结构化的，路由器只读取结构化字段。

### 3.2 完整条件边定义

```python
# v12.1.1 条件边定义
# 格式: (当前状态, 条件, 目标状态)

CONDITIONAL_EDGES = {
    Phase.INIT: [
        (lambda ctx: bool(ctx.raw_input.strip()), Phase.PHASE_A),
        (lambda ctx: True, Phase.ERROR),  # 空输入
    ],

    Phase.PHASE_A: [
        # 路由决策驱动
        (lambda ctx: ctx.routing.route == "LOW_CONFIDENCE", Phase.PHASE_A_CLARIFY),
        (lambda ctx: ctx.routing.route == "DIRECT_URL", Phase.PHASE_C),    # 跳过 B
        (lambda ctx: ctx.routing.route in ("NAMED_PROJECT", "DOMAIN_EXPLORE"), Phase.PHASE_B),
        (lambda ctx: True, Phase.PHASE_B),  # fallback
    ],

    Phase.PHASE_A_CLARIFY: [
        (lambda ctx: ctx.clarification_round < 2, Phase.PHASE_A),  # 重新 profile
        (lambda ctx: True, Phase.PHASE_B),  # 超过追问上限，降级继续
    ],

    Phase.PHASE_B: [
        (lambda ctx: len(ctx.candidates) > 0, Phase.PHASE_C),
        (lambda ctx: len(ctx.candidates) == 0, Phase.DEGRADED),  # 无候选
    ],

    Phase.PHASE_C: [  # fan-out workers，由 WorkerSupervisor 管理
        (lambda ctx: ctx.successful_extractions > 0, Phase.PHASE_D),
        (lambda ctx: ctx.successful_extractions == 0 and ctx.has_clawhub, Phase.PHASE_D),  # 降级合成
        (lambda ctx: True, Phase.DEGRADED),
    ],

    Phase.PHASE_D: [  # Synthesis
        (lambda ctx: ctx.synthesis_ok, Phase.PHASE_E),
        (lambda ctx: True, Phase.DEGRADED),  # 合成失败但有 partial
    ],

    Phase.PHASE_E: [  # Compile
        (lambda ctx: ctx.compile_ok, Phase.PHASE_F),
        (lambda ctx: True, Phase.DEGRADED),  # 编译失败
    ],

    Phase.PHASE_F: [  # Validate
        (lambda ctx: ctx.quality_score >= 60 and not ctx.blockers, Phase.PHASE_G),  # PASS
        (lambda ctx: ctx.quality_score < 60 and ctx.revise_count < 1
                     and ctx.weakest_section is not None, Phase.PHASE_E),  # REVISE
        (lambda ctx: ctx.quality_score < 60 and ctx.revise_count >= 1, Phase.DEGRADED),  # 修不好
        (lambda ctx: ctx.blockers, Phase.DEGRADED),  # 硬伤
    ],

    Phase.PHASE_G: [  # Package
        (lambda ctx: True, Phase.DONE),
    ],
}
```

### 3.3 每个条件边的 WHY 和信号定义

#### PHASE_A -> PHASE_C（跳过 Discovery）

**信号**: `routing.route == "DIRECT_URL"`
**判断方式**: 正则匹配 URL 模式
**WHY**: 用户给了 URL 就不需要搜索。跳过 Discovery 节省 20-40 秒和 1 次 LLM 调用。
**风险**: 用户给的 URL 可能指向错误的 repo。但这是用户的选择，不应由系统否决。

#### PHASE_A -> PHASE_A_CLARIFY（追问）

**信号**: `profile.confidence < 0.7 AND profile.questions is not empty`
**判断方式**: NeedProfileBuilder 输出的 confidence 字段（NeedProfileBuilder 内部用 LLM 生成，但 confidence 值本身是结构化的浮点数）
**WHY**: 低置信搜索 = 浪费预算。追问 30 秒 > 盲搜 2 分钟。当前已有此逻辑（Socratic Gate），保留。
**阈值选择**: 0.7 是经验值。太高（0.9）会导致频繁追问；太低（0.5）会导致劣质搜索。0.7 对应"用户意图基本明确但缺少关键细节"。

#### PHASE_B -> PHASE_C（Discovery 成功）

**信号**: `len(candidates) > 0`（经过 relevance gate 后仍有候选）
**判断方式**: candidates 列表长度
**WHY**: 只要有一个候选，就值得提取。零候选 = 搜索失败，应该降级告知用户。

#### PHASE_B -> DEGRADED（零候选）

**信号**: `len(candidates) == 0`
**WHY**: 当前 singleshot 在零候选时已经 early exit。v12.1.1 改为结构化降级，输出"未找到相关项目"+ 搜索覆盖率报告 + 建议用户换描述。

#### PHASE_C (workers) -> PHASE_D

**信号**: `successful_extractions > 0`（至少一个 worker 成功返回有效 envelope）
**判断方式**: 计数 fan-in 收集到的有效 envelopes
**WHY**: 合成只需要至少一个有效提取。3 个 worker 中 1 个失败 = 继续合成剩下 2 个。全部失败 = 降级。

#### PHASE_F（Validate）-> PHASE_E（Revise）

**信号**: `quality_score < 60 AND revise_count < 1 AND weakest_section is not None`
**判断方式**: 质量评分 + 循环计数 + 是否有可定位的最弱 section
**WHY**:
- 限制 1 次修复（非 3 次）。原因：当前编译是最大瓶颈（138s），重新编译 3 次 = 增加 7 分钟。1 次修复是成本/收益平衡点。
- `weakest_section` 非空 = 可以做靶向修复（只重新编译最弱 section），而非全量重编译。如果分不清哪个 section 弱 = 无法靶向修复 = 降级。
- **关键改进**：v12.1.0 的 REVISE 上限是 3 次全量重编译。v12.1.1 改为 1 次靶向修复。

#### 任意 Phase -> DEGRADED

**信号**: 预算超限 / 不可恢复错误 / 超时
**判断方式**: BudgetManager.is_exceeded() / 异常捕获 / lease 过期
**WHY**: DEGRADED 不再是终态。它触发降级交付流程（见第 5 节）。

### 3.4 Transitions 数据结构（代码级）

```python
# 新的 TRANSITIONS 定义（替换线性 TRANSITIONS）
TRANSITIONS: dict[Phase, set[Phase]] = {
    Phase.INIT:            {Phase.PHASE_A, Phase.ERROR},
    Phase.PHASE_A:         {Phase.PHASE_A_CLARIFY, Phase.PHASE_B, Phase.PHASE_C, Phase.DEGRADED},
    Phase.PHASE_A_CLARIFY: {Phase.PHASE_A, Phase.PHASE_B, Phase.DEGRADED},
    Phase.PHASE_B:         {Phase.PHASE_C, Phase.DEGRADED, Phase.ERROR},
    Phase.PHASE_C:         {Phase.PHASE_D, Phase.DEGRADED, Phase.ERROR},
    Phase.PHASE_D:         {Phase.PHASE_E, Phase.DEGRADED, Phase.ERROR},
    Phase.PHASE_E:         {Phase.PHASE_F, Phase.DEGRADED, Phase.ERROR},
    Phase.PHASE_F:         {Phase.PHASE_G, Phase.PHASE_E, Phase.DEGRADED, Phase.ERROR},  # REVISE -> E
    Phase.PHASE_G:         {Phase.DONE, Phase.ERROR},
    Phase.DONE:            set(),
    Phase.DEGRADED:        set(),  # 但会触发降级交付流程
    Phase.ERROR:           set(),
}
```

**WHY 不沿用 PHASE_G_REVISE 中间状态**: REVISE 从独立状态变为 PHASE_F -> PHASE_E 的条件边。原因：PHASE_G_REVISE 只是一个路由跳板（当前代码里 `_handle_revise()` 只做 `self._transition(Phase.PHASE_F)`），没有自己的 executor。条件边本身就能表达"验证不通过 -> 回编译"，不需要额外状态。

---

## 4. 扇出/扇入设计（Fan-out / Fan-in）

### 4.1 PHASE_C: WorkerSupervisor 架构

```
                PHASE_C Entry
                     |
            +--------v--------+
            | WorkerSupervisor|
            |  - candidates[] |
            |  - max_workers  |
            |  - timeout_sec  |
            +--------+--------+
                     | spawn
        +------------+------------+
        |            |            |
   +----v----+ +----v----+ +----v----+
   |Worker[0]| |Worker[1]| |Worker[2]|
   | repo_a  | | repo_b  | | repo_c  |
   | +-----+ | | +-----+ | | +-----+ |
   | |clone| | | |clone| | | |clone| |
   | |facts| | | |facts| | | |facts| |
   | |soul | | | |soul | | | |soul | |
   | |comm.| | | |comm.| | | |comm.| |
   | +-----+ | | +-----+ | | +-----+ |
   +----+----+ +----+----+ +----+----+
        |            |            |
        +------------+------------+
                     | fan-in
            +--------v--------+
            | EnvelopeCollector|
            |  - filter       |
            |  - normalize    |
            |  - rank         |
            +--------+--------+
                     |
                PHASE_D Entry
```

### 4.2 Worker 隔离边界

每个 RepoWorker 具有以下独立资源：

```python
@dataclass
class RepoWorkerContext:
    """每个 worker 的隔离上下文。"""
    worker_id: str              # "worker-0", "worker-1", ...
    repo_url: str
    repo_name: str
    repo_type: Literal["TOOL", "FRAMEWORK", "CATALOG"]  # 来自 repo type classifier

    # 独立工作空间
    work_dir: Path              # runs/<run_id>/workers/<worker_id>/

    # 独立预算
    token_budget: int           # 总 token 预算的 1/N
    cost_budget_usd: float      # 总成本预算的 1/N
    timeout_seconds: int        # 独立超时（默认 180s）

    # 独立重试
    max_retries: int = 2

    # 状态追踪
    status: Literal["pending", "running", "done", "failed", "timeout"] = "pending"
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
```

**WHY 独立预算**: 如果 3 个 worker 共享预算，一个 monorepo 可能吃掉全部 token，导致其他 2 个 worker 饿死。独立预算确保每个 worker 有最低保障。

**WHY 独立超时**: 一个 worker 卡死不应该阻塞其他 worker。独立超时 + `concurrent.futures.as_completed()` = 先完成的先收集。

**WHY repo_type 影响 worker 行为**: CATALOG 类型（awesome-list）只需要浅层提取（README 解析 + 链接分类），不需要深度代码分析。TOOL/FRAMEWORK 需要完整的 soul extraction。不同类型给不同的提取 prompt 和预算。

### 4.3 Worker 内部流程

每个 worker 内部的处理步骤：

```
1. clone_or_cache(repo_url) -> local_path
2. extract_repo_facts(local_path) -> repo_facts.json  [确定性，无 LLM]
3. classify_repo_type(repo_facts) -> type              [确定性规则]
4. IF type == CATALOG:
       shallow_extract(readme) -> evidence_cards        [1 次 LLM 调用]
   ELSE:
       deep_extract(local_path, repo_facts, bricks) -> soul  [2-3 次 LLM 调用]
5. collect_community_signals(repo_url) -> signals       [GitHub API，无 LLM]
6. build_envelope(soul, signals, metrics) -> RepoExtractionEnvelope
```

**WHY 社区采集在 worker 内部而非独立阶段**: 社区信号是 per-repo 的。把它放在 worker 内部：(a) 可以和 soul extraction 并行，(b) 避免额外的 fan-out/fan-in 轮次，(c) worker 可以直接用社区信号 enrich soul。

### 4.4 RepoExtractionEnvelope

```python
class RepoExtractionEnvelope(BaseModel):
    """Fan-in 的标准化输入格式。合成器只看 envelope，不看原始过程。"""

    schema_version: str = "dm.repo-envelope.v1"

    # 身份
    worker_id: str
    repo_name: str
    repo_url: str
    repo_type: Literal["TOOL", "FRAMEWORK", "CATALOG"]

    # 提取结果
    design_philosophy: Optional[str] = None
    mental_model: Optional[str] = None
    why_decisions: list[dict] = []          # {decision, reasoning, evidence_refs}
    unsaid_traps: list[dict] = []           # {trap, severity, evidence_refs}
    feature_inventory: list[str] = []

    # 社区信号
    community_signals: list[dict] = []      # {title, tier, comment_count}

    # 质量指标
    extraction_confidence: float            # 0.0-1.0
    evidence_count: int                     # 有多少条证据引用

    # 运行指标
    metrics: RunMetrics

    # 状态
    status: Literal["ok", "degraded", "failed"]
    warnings: list[str] = []
```

**WHY 标准化 envelope**: 合成阶段不应看到 worker 的内部状态（prompt 历史、重试日志、克隆路径）。只看标准化结果。这是 DeerFlow 的核心设计——subagent 返回结构化 artifact，lead agent 消费 artifact。

### 4.5 Fan-in: EnvelopeCollector

```python
class EnvelopeCollector:
    """收集 fan-out workers 的结果，过滤 + 排序 + 传递给合成。"""

    def collect(
        self,
        envelopes: list[RepoExtractionEnvelope],
        min_confidence: float = 0.3,
    ) -> CollectionResult:
        # 1. 过滤失败的 envelope
        valid = [e for e in envelopes if e.status != "failed"]

        # 2. 过滤低置信的 envelope
        qualified = [e for e in valid if e.extraction_confidence >= min_confidence]

        # 3. 按置信度排序
        qualified.sort(key=lambda e: e.extraction_confidence, reverse=True)

        # 4. 收集被过滤掉的 envelope 的信息（用于降级报告）
        filtered_out = [e for e in envelopes if e not in qualified]

        return CollectionResult(
            qualified_envelopes=qualified,
            filtered_envelopes=filtered_out,
            total_workers=len(envelopes),
            successful_workers=len(valid),
            qualified_workers=len(qualified),
        )
```

**min_confidence 阈值选择**: 0.3 是有意设低的。原因：即使一个 repo 的提取只有 30% 置信度（比如 README 很简短），它的某些 WHY 或 UNSAID 可能仍然有价值。完全丢弃的阈值应该更低。高置信度的 envelope 在合成时权重更高，低置信度的在合成时权重更低——这是合成器的职责，不是收集器的。

### 4.6 并发控制

```python
# 并发参数
MAX_CONCURRENT_WORKERS = 3  # 硬上限
DEFAULT_WORKER_TIMEOUT = 180  # 秒

# 背压控制策略
# 总 token 预算 = BudgetPolicy.max_tokens（默认 200k）
# 每个 worker 预算 = total / max(num_workers, 1) * 0.8  (留 20% 给合成+编译)
# 如果 worker 用量达到预算的 90% -> 提前结束当前提取，返回 partial envelope
```

**WHY MAX_CONCURRENT_WORKERS = 3**:
1. OpenClaw 平台约束：`PlatformAdapter.get_concurrency_limit()` 当前返回 3
2. LLM API 速率限制：3 个并发 LLM 请求是大部分 API 的安全上限
3. 效用递减：超过 3 个 repo 的提取，合成质量不再线性提升（来自 E2E 测试经验）

**WHY 不用 asyncio**: 当前管线用 `ThreadPoolExecutor`（singleshot 已有）。Worker 的主要 I/O 是 LLM API 调用和文件读写，线程池足够。引入 asyncio 需要改造所有 executor 为 async，工程量大但收益有限（I/O 并发度已经够了）。v12.1.1 保持线程池。

---

## 5. 降级交付定义（Degraded Delivery）

### 5.1 设计原则

**核心原则：用户等了 N 秒就应该得到 N 秒能产出的最佳结果，而非"失败"。**

**WHY 不用当前的 `allow_degraded_delivery = False`**: 这是一个全局开关，要么全降级要么全拒绝。现实中降级应该是分层的——"我找到了 3 个项目但只有 1 个提取成功"和"我一个项目都没找到"是完全不同的降级等级。

### 5.2 每阶段降级定义

| 阶段 | 失败场景 | 最低交付物 | 用户看到什么 |
|------|---------|----------|-----------|
| PHASE_A | LLM 调用失败 | 基于正则的最简 NeedProfile（关键词=raw_input 分词） | 正常继续，但搜索可能不够精准 |
| PHASE_B | GitHub API 失败 / 零候选 | 搜索覆盖率报告 + "未找到" + 建议换描述 | "三个信息源都没找到相关内容。建议换个描述试试。" |
| PHASE_C | 所有 worker 失败 | 最后一个 worker 的 partial envelope + ClawHub 数据 | "GitHub 项目分析失败，基于 ClawHub 已有 Skills 生成基础版道具（完整度 40%）" |
| PHASE_C | 部分 worker 失败 | 成功 workers 的 envelopes | 正常继续，在最终报告中注明哪些项目分析失败 |
| PHASE_D | 合成 LLM 失败 | Python-only 合成（当前已有 `_synthesize_fast`） | 正常继续，合成质量降低 |
| PHASE_E | 编译 LLM 失败 | 模板 fallback（当前已有 `_compile_skill_template`） | "道具（基础版），完整度 40%" |
| PHASE_F | 验证 LLM 失败 | 跳过验证，直接打包 | 附带警告"质量未经验证" |
| PHASE_F | 质量 < 60 且 revise 用尽 | 当前编译结果 + 质量报告 | "道具完整度 XX%，以下 section 质量偏低：..." |

### 5.3 降级交付的结构

```python
@dataclass
class DegradedDelivery:
    """降级交付物。"""

    # 必有字段
    run_id: str
    degraded_at_phase: str              # 哪个阶段触发降级
    degradation_reason: str             # 为什么降级
    completeness_pct: int               # 0-100

    # 交付物（可能部分为空）
    skill_md_path: Optional[str]        # 可能有（模板 fallback）
    quality_score: Optional[float]      # 可能有

    # 用户可读的降级报告
    user_message: str                   # 完整的用户面消息

    # 调试信息
    search_coverage: list[dict]         # Discovery 搜索了哪些源
    attempted_repos: list[str]          # 尝试了哪些 repo
    successful_repos: list[str]         # 成功了哪些 repo
    failed_repos: list[dict]            # 失败了哪些 + 为什么

    # 可操作建议
    suggestions: list[str]              # "试试换个描述" / "给精确 URL"
```

### 5.4 Completeness Tier（完整度等级）

| 等级 | completeness_pct | 触发条件 | 交付内容 |
|------|-----------------|---------|---------|
| FULL | 100 | 全管线成功 + quality >= 60 | 完整 SKILL.md + 全部附件 |
| PARTIAL_SOULS | 70 | 部分 repo 提取成功 + 编译通过 | SKILL.md（标注信息源不完整） |
| FAST_PATH | 55 | 仅 ClawHub/本地 skill + Python 合成 | 轻量 SKILL.md |
| TEMPLATE | 40 | 编译失败，模板 fallback | 模板 SKILL.md |
| SEARCH_ONLY | 20 | 找到 repo 但提取全失败 | 候选 repo 列表 + 搜索报告 |
| EMPTY | 5 | 全部失败 | 搜索覆盖率报告 + 建议 |

**WHY 6 级而非 2 级**: 当前只有 PASS/FAIL。但用户体验从"我得到了一个质量一般但能用的道具"到"我什么都没得到"差距巨大。分级让每一分钟的计算都有回报。

---

## 6. 进度事件设计（Run Events）

### 6.1 Event Schema

```python
class RunEvent(BaseModel):
    """run_events.jsonl 中的单条事件。"""

    schema_version: str = "dm.run-event.v1"
    ts: str                     # ISO 8601 时间戳
    run_id: str
    seq: int                    # 单调递增序列号（用于排序和去重）

    event_type: Literal[
        # Run 生命周期
        "run_started",
        "run_completed",
        "run_failed",

        # Phase 生命周期
        "phase_started",
        "phase_completed",
        "phase_skipped",
        "phase_degraded",

        # 路由
        "routing_decision",

        # Worker 生命周期（PHASE_C 内部）
        "worker_started",
        "worker_progress",
        "worker_completed",
        "worker_failed",

        # 质量
        "quality_gate_result",
        "revise_triggered",

        # 预算
        "budget_warning",
        "budget_exceeded",

        # 用户交互
        "clarification_asked",
        "clarification_received",
    ]

    phase: Optional[str] = None     # 当前 phase
    worker_id: Optional[str] = None # worker 事件时填充

    message: str                    # 人类可读的描述

    # 结构化 metadata（按 event_type 不同）
    meta: dict = {}

    # 进度指标
    elapsed_ms: int = 0
    percent_complete: int = 0       # 0-100
```

### 6.2 事件流示例

一个典型的 DOMAIN_EXPLORE 路径的事件流：

```jsonl
{"ts":"2026-03-28T14:00:00","run_id":"run-20260328-140000","seq":1,"event_type":"run_started","message":"Doramagic run started","meta":{"raw_input":"帮我做记账app"},"elapsed_ms":0,"percent_complete":0}
{"ts":"2026-03-28T14:00:01","seq":2,"event_type":"phase_started","phase":"PHASE_A","message":"Analyzing your request...","elapsed_ms":1000,"percent_complete":5}
{"ts":"2026-03-28T14:00:05","seq":3,"event_type":"routing_decision","phase":"PHASE_A","message":"Route: DOMAIN_EXPLORE (confidence=0.82)","meta":{"route":"DOMAIN_EXPLORE","confidence":0.82,"skip_discovery":false,"max_repos":3},"elapsed_ms":5000,"percent_complete":8}
{"ts":"2026-03-28T14:00:05","seq":4,"event_type":"phase_completed","phase":"PHASE_A","message":"Request analyzed","elapsed_ms":5000,"percent_complete":10}
{"ts":"2026-03-28T14:00:06","seq":5,"event_type":"phase_started","phase":"PHASE_B","message":"Searching GitHub, ClawHub, local skills...","elapsed_ms":6000,"percent_complete":10}
{"ts":"2026-03-28T14:00:25","seq":6,"event_type":"phase_completed","phase":"PHASE_B","message":"Found 3 candidates: firefly-iii, actual-budget, beancount","meta":{"candidates":3,"sources":["github","clawhub"]},"elapsed_ms":25000,"percent_complete":20}
{"ts":"2026-03-28T14:00:26","seq":7,"event_type":"phase_started","phase":"PHASE_C","message":"Extracting design souls (3 repos in parallel)...","elapsed_ms":26000,"percent_complete":20}
{"ts":"2026-03-28T14:00:26","seq":8,"event_type":"worker_started","phase":"PHASE_C","worker_id":"worker-0","message":"Cloning firefly-iii...","meta":{"repo":"firefly-iii","repo_type":"TOOL"},"elapsed_ms":26000,"percent_complete":22}
{"ts":"2026-03-28T14:00:26","seq":9,"event_type":"worker_started","phase":"PHASE_C","worker_id":"worker-1","message":"Cloning actual-budget...","meta":{"repo":"actual-budget","repo_type":"TOOL"},"elapsed_ms":26000,"percent_complete":22}
{"ts":"2026-03-28T14:00:26","seq":10,"event_type":"worker_started","phase":"PHASE_C","worker_id":"worker-2","message":"Cloning beancount...","meta":{"repo":"beancount","repo_type":"FRAMEWORK"},"elapsed_ms":26000,"percent_complete":22}
{"ts":"2026-03-28T14:00:50","seq":11,"event_type":"worker_progress","phase":"PHASE_C","worker_id":"worker-0","message":"Extracting soul: firefly-iii","meta":{"step":"soul_extraction","progress":"2/4"},"elapsed_ms":50000,"percent_complete":35}
{"ts":"2026-03-28T14:01:20","seq":12,"event_type":"worker_completed","phase":"PHASE_C","worker_id":"worker-1","message":"actual-budget extraction complete (confidence: 0.85)","meta":{"extraction_confidence":0.85,"evidence_count":12},"elapsed_ms":80000,"percent_complete":40}
{"ts":"2026-03-28T14:01:45","seq":13,"event_type":"worker_completed","phase":"PHASE_C","worker_id":"worker-0","message":"firefly-iii extraction complete (confidence: 0.91)","meta":{"extraction_confidence":0.91,"evidence_count":18},"elapsed_ms":105000,"percent_complete":48}
{"ts":"2026-03-28T14:01:50","seq":14,"event_type":"worker_failed","phase":"PHASE_C","worker_id":"worker-2","message":"beancount extraction timeout","meta":{"error":"E_TIMEOUT","partial":true},"elapsed_ms":110000,"percent_complete":50}
{"ts":"2026-03-28T14:01:50","seq":15,"event_type":"phase_completed","phase":"PHASE_C","message":"Extraction complete: 2/3 repos successful","meta":{"total":3,"successful":2,"failed":1},"elapsed_ms":110000,"percent_complete":55}
{"ts":"2026-03-28T14:01:51","seq":16,"event_type":"phase_started","phase":"PHASE_D","message":"Synthesizing design wisdom...","elapsed_ms":111000,"percent_complete":55}
{"ts":"2026-03-28T14:02:10","seq":17,"event_type":"phase_completed","phase":"PHASE_D","message":"Synthesis complete","elapsed_ms":130000,"percent_complete":65}
{"ts":"2026-03-28T14:02:11","seq":18,"event_type":"phase_started","phase":"PHASE_E","message":"Compiling SKILL.md...","elapsed_ms":131000,"percent_complete":65}
{"ts":"2026-03-28T14:04:20","seq":19,"event_type":"phase_completed","phase":"PHASE_E","message":"SKILL.md compiled (1847 lines)","elapsed_ms":260000,"percent_complete":85}
{"ts":"2026-03-28T14:04:21","seq":20,"event_type":"phase_started","phase":"PHASE_F","message":"Validating quality...","elapsed_ms":261000,"percent_complete":85}
{"ts":"2026-03-28T14:04:25","seq":21,"event_type":"quality_gate_result","phase":"PHASE_F","message":"Quality: 72.5/100 PASS","meta":{"score":72.5,"blockers":[],"weakest_section":"mental_model"},"elapsed_ms":265000,"percent_complete":90}
{"ts":"2026-03-28T14:04:25","seq":22,"event_type":"phase_completed","phase":"PHASE_F","message":"Validation passed","elapsed_ms":265000,"percent_complete":90}
{"ts":"2026-03-28T14:04:26","seq":23,"event_type":"phase_started","phase":"PHASE_G","message":"Packaging delivery...","elapsed_ms":266000,"percent_complete":95}
{"ts":"2026-03-28T14:04:27","seq":24,"event_type":"phase_completed","phase":"PHASE_G","message":"Delivery packaged","elapsed_ms":267000,"percent_complete":100}
{"ts":"2026-03-28T14:04:27","seq":25,"event_type":"run_completed","message":"Doramagic run completed (completeness: 70%)","meta":{"completeness_tier":"PARTIAL_SOULS","completeness_pct":70,"quality_score":72.5,"duration_sec":267},"elapsed_ms":267000,"percent_complete":100}
```

### 6.3 `/dora-status` 实现

```python
def dora_status(run_id: str, run_dir: Path) -> dict:
    """读取 run_events.jsonl 并返回当前状态摘要。"""
    events_file = run_dir / run_id / "run_events.jsonl"
    if not events_file.exists():
        return {"error": f"Run {run_id} not found"}

    events = []
    for line in events_file.read_text().strip().split("\n"):
        events.append(json.loads(line))

    if not events:
        return {"status": "unknown", "message": "No events found"}

    latest = events[-1]

    # 构建 worker 状态表
    workers = {}
    for e in events:
        if e.get("worker_id"):
            workers[e["worker_id"]] = {
                "repo": e.get("meta", {}).get("repo", "unknown"),
                "status": e["event_type"].replace("worker_", ""),
                "message": e["message"],
            }

    # 构建 phase 完成列表
    completed_phases = [
        e["phase"] for e in events
        if e["event_type"] == "phase_completed"
    ]

    return {
        "run_id": run_id,
        "current_phase": latest.get("phase"),
        "current_status": latest["event_type"],
        "message": latest["message"],
        "elapsed_sec": latest["elapsed_ms"] / 1000,
        "percent_complete": latest["percent_complete"],
        "completed_phases": completed_phases,
        "workers": workers,
        "is_terminal": latest["event_type"] in ("run_completed", "run_failed"),
    }
```

### 6.4 EventBus 实现

```python
class EventBus:
    """写入 run_events.jsonl 的事件总线。线程安全。"""

    def __init__(self, run_dir: Path, run_id: str):
        self._file = run_dir / "run_events.jsonl"
        self._run_id = run_id
        self._seq = 0
        self._lock = threading.Lock()
        self._start_time = time.monotonic()

    def emit(
        self,
        event_type: str,
        message: str,
        phase: Optional[str] = None,
        worker_id: Optional[str] = None,
        meta: Optional[dict] = None,
        percent_complete: int = 0,
    ) -> None:
        with self._lock:
            self._seq += 1
            event = {
                "schema_version": "dm.run-event.v1",
                "ts": datetime.now().isoformat(),
                "run_id": self._run_id,
                "seq": self._seq,
                "event_type": event_type,
                "phase": phase,
                "worker_id": worker_id,
                "message": message,
                "meta": meta or {},
                "elapsed_ms": int((time.monotonic() - self._start_time) * 1000),
                "percent_complete": percent_complete,
            }
            with open(self._file, "a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
```

**WHY JSONL 而非 SQLite**: (a) 追加写入不需要连接管理和事务。(b) 可以直接 `tail -f` 观察。(c) 数据量很小（一个 run 最多约 50 事件）。(d) 跨平台（OpenClaw 环境可能限制 SQLite）。

**WHY 线程锁而非 multiprocessing Lock**: Workers 运行在 ThreadPoolExecutor 中（共享进程内存），不需要跨进程锁。

---

## 7. 对现有代码的影响评估

### 7.1 `state_definitions.py` 改动

**改动范围**: 大改

**具体变更**:

1. **Phase enum 重新定义**:
   - 删除: `PHASE_CD`, `PHASE_G_REVISE`
   - 新增: `PHASE_C` (extraction fan-out), `PHASE_D` (synthesis)
   - 重映射: `PHASE_E` -> compile (原 `PHASE_F`), `PHASE_F` -> validate (原 `PHASE_G`), `PHASE_G` -> package (原 `PHASE_H`)

```python
class Phase(str, Enum):
    INIT = "INIT"
    PHASE_A = "PHASE_A"             # Need Profile + Router
    PHASE_A_CLARIFY = "PHASE_A_CLARIFY"
    PHASE_B = "PHASE_B"             # Discovery
    PHASE_C = "PHASE_C"             # Fan-out Repo Workers
    PHASE_D = "PHASE_D"             # Synthesis
    PHASE_E = "PHASE_E"             # Compile
    PHASE_F = "PHASE_F"             # Validate + QA Gate
    PHASE_G = "PHASE_G"             # Package + Deliver
    DONE = "DONE"
    DEGRADED = "DEGRADED"
    ERROR = "ERROR"
```

2. **TRANSITIONS 从线性集合变为条件边**:
   - 删除: 简单的 `set` 映射
   - 新增: `CONDITIONAL_EDGES` dict（见 3.2 节）+ 保留 `TRANSITIONS` 作为合法性校验

3. **PHASE_EXECUTOR_MAP 更新**:
```python
PHASE_EXECUTOR_MAP: dict[Phase, str | None] = {
    Phase.INIT: None,
    Phase.PHASE_A: "NeedProfileBuilder",
    Phase.PHASE_A_CLARIFY: None,
    Phase.PHASE_B: "DiscoveryRunner",
    Phase.PHASE_C: "WorkerSupervisor",    # 新：替代 SoulExtractorBatch
    Phase.PHASE_D: "SynthesisRunner",
    Phase.PHASE_E: "SkillCompiler",
    Phase.PHASE_F: "Validator",
    Phase.PHASE_G: "DeliveryPackager",
    Phase.DONE: None,
    Phase.DEGRADED: None,
    Phase.ERROR: None,
}
```

4. **新增 MAX_REVISE_LOOPS = 1**（从 3 改为 1）

### 7.2 `flow_controller.py` 改动

**改动范围**: 中等

**具体变更**:

1. **`ControllerState` 新增字段**:
```python
class ControllerState:
    def __init__(self, ...):
        ...
        self.routing_decision: Optional[dict] = None    # RoutingDecision 序列化
        self.clarification_round: int = 0               # 追问轮次
        self.worker_states: dict[str, dict] = {}        # worker 状态追踪
```

2. **`_step()` 方法改造**:
   - 当前: `if phase == Phase.PHASE_A: await self._handle_phase_a()` -> 线性推进
   - 改为: `await self._handle_phase_a()` 之后，根据 `RoutingDecision` 决定下一个 phase

3. **新增 `_evaluate_edge()` 方法**:
```python
async def _evaluate_edge(self, from_phase: Phase) -> Phase:
    """评估条件边，返回下一个 phase。"""
    edges = CONDITIONAL_EDGES.get(from_phase, [])
    ctx = self._build_edge_context()
    for condition, target in edges:
        if condition(ctx):
            return target
    return Phase.ERROR  # 没有匹配的边
```

4. **`_dispatch_executor()` 改造**:
   - 当前: 固定用 `_advance_from(phase)` 推进到下一个线性 phase
   - 改为: 用 `_evaluate_edge(phase)` 评估条件边

5. **新增 EventBus 集成**:
   - 在 `__init__` 中创建 `EventBus`
   - 在 `_step()` 中 emit phase 事件
   - 替代当前的 `_log_event()` 内存日志

6. **`_handle_phase_a()` 增强**:
   - 执行 NeedProfileBuilder 后，运行 Input Router
   - 存储 RoutingDecision 到 state

7. **`_advance_from()` 删除** -> 被 `_evaluate_edge()` 替代

8. **`_next_normal_phase()` 删除** -> 不再有"线性顺序"概念

### 7.3 `executor.py` (PhaseExecutor 接口) 改动

**改动范围**: 小

**具体变更**:

1. **`execute()` 返回值不变**（仍然是 `ModuleResultEnvelope`），但 envelope 的 `data` 字段需要携带路由信号：

```python
# NeedProfileBuilder 的 data 字段新增:
class NeedProfileResult(BaseModel):
    profile: NeedProfile
    routing_decision: RoutingDecision  # 新增
```

2. **新增 `WorkerSupervisor` executor**:
   - 不是普通的 PhaseExecutor（它内部管理多个 worker）
   - 但对外接口仍然是 `execute()` -> `ModuleResultEnvelope`
   - 内部用 ThreadPoolExecutor fan-out

3. **`ExecutorConfig` 小改**:
```python
class ExecutorConfig(BaseModel):
    ...
    routing_decision: Optional[dict] = None  # 新增：传递路由上下文
    event_bus: Optional[object] = None       # 新增：worker 发事件用
```

### 7.4 `orchestration.py` 改动

**改动范围**: 小

- `RunnerConfig.allow_degraded_delivery` 删除（降级交付不再是全局开关）
- 新增 `RunnerConfig.max_revise_loops: int = 1`（从 orchestration 层可配置）
- `PhaseStatus.phase` 的 Literal 更新为新的 phase 名

### 7.5 `doramagic_singleshot.py` 改动

**改动范围**: 不改

**决策**: v12.1.1 保留 singleshot 作为 debug/兼容路径。所有新功能在 FlowController 路径实现。生产入口从 singleshot 切换到 controller 路径（如研究报告 P0-1 建议）。

**WHY**: singleshot 是 2000+ 行的脚本，重构风险高。新架构在 controller 路径实现后，singleshot 自然退役。如果新架构出问题，还能 rollback 到 singleshot。

### 7.6 新增文件

| 文件路径 | 职责 |
|---------|------|
| `packages/contracts/doramagic_contracts/routing.py` | `RoutingDecision`, `InputRouter` |
| `packages/contracts/doramagic_contracts/events.py` | `RunEvent` schema |
| `packages/contracts/doramagic_contracts/worker.py` | `RepoWorkerContext`, `RepoExtractionEnvelope` |
| `packages/controller/doramagic_controller/event_bus.py` | `EventBus` 实现 |
| `packages/controller/doramagic_controller/input_router.py` | Input Router 确定性逻辑 |
| `packages/executors/doramagic_executors/worker_supervisor.py` | `WorkerSupervisor` executor |
| `packages/executors/doramagic_executors/repo_worker.py` | 单 repo 提取 worker |
| `scripts/dora_status.py` | `/dora-status` 命令实现 |

---

## 8. 版本边界：v12.1.1 vs 后续版本

### 8.1 v12.1.1 必须实现

| # | 改动 | 对应问题 | 工作量估算 |
|---|------|---------|----------|
| 1 | Input Router + RoutingDecision | 问题 1, 2 | 1 天 |
| 2 | 条件边替换线性 TRANSITIONS | 问题 2, 5 | 1 天 |
| 3 | PHASE_C fan-out WorkerSupervisor | 问题 3 | 2 天 |
| 4 | RepoExtractionEnvelope + EnvelopeCollector | 问题 3, 5 | 1 天 |
| 5 | run_events.jsonl + EventBus | 问题 4 | 1 天 |
| 6 | 降级交付分层（替换 allow_degraded_delivery=False） | 问题 6 | 1 天 |
| 7 | REVISE 限制从 3 次改 1 次 + 靶向修复 | 问题 5 | 0.5 天 |
| 8 | 生产入口从 singleshot 切到 controller | P0-1 | 0.5 天 |
| 9 | `/dora-status` 命令 | 问题 4 | 0.5 天 |

**总计**: 约 8.5 天

### 8.2 v12.2.0 增量实现

| # | 改动 | 来源 |
|---|------|------|
| 1 | 执行模式 (Flash/Standard/Pro) | DeerFlow 研究 R06 |
| 2 | 持久化 extraction-patterns 目录 | web-access 研究 R09 |
| 3 | Repo Intelligence Cache（克隆缓存 + facts 缓存） | 研究报告 R10 |
| 4 | 验证并行化（编译同时跑 QA） | 研究报告 R12 |
| 5 | Partial deliverables 早期暴露 | 研究报告 R11 |

### 8.3 v12.3.0+ 远期

| # | 改动 | 来源 |
|---|------|------|
| 1 | Local SSE endpoint（实时流式进度） | DeerFlow Todo UI |
| 2 | Middleware Pipeline 架构 | DeerFlow middleware 模式 |
| 3 | 跨 run 学习（域经验累积） | web-access site-patterns |
| 4 | Local run dashboard（web UI） | 研究报告 R14 |

### 8.4 v12.1.1 不做的事及其 WHY

| 不做 | WHY |
|------|-----|
| LangGraph 集成 | 自有状态机已经够用。LangGraph 引入外部依赖 + 学习成本，当前规模不需要 |
| asyncio 改造 | ThreadPoolExecutor 对 I/O 并发够用。async 改造需要改所有 executor，ROI 不够 |
| 执行模式 (Flash/Standard/Pro) | 需要先验证 fan-out 架构稳定后再分级 |
| 持久化缓存 | 需要先验证 worker 隔离正确后再做跨 run 缓存 |
| Web dashboard | 需要先验证 event bus 稳定后再做前端 |
| Middleware Pipeline | 当前 Phase 数量（7 个）不足以证明 middleware 模式的价值 |

---

## 附录 A: 完整状态转移表

```
From              -> To                  Condition
----------------------------------------------------------------------
INIT              -> PHASE_A             input non-empty
INIT              -> ERROR               input empty

PHASE_A           -> PHASE_A_CLARIFY     routing.route == LOW_CONFIDENCE
PHASE_A           -> PHASE_C             routing.route == DIRECT_URL (skip B)
PHASE_A           -> PHASE_B             routing.route in (NAMED_PROJECT, DOMAIN_EXPLORE)
PHASE_A           -> DEGRADED            executor error

PHASE_A_CLARIFY   -> PHASE_A             clarification_round < 2 (re-profile)
PHASE_A_CLARIFY   -> PHASE_B             clarification_round >= 2 (give up, try best guess)
PHASE_A_CLARIFY   -> DEGRADED            timeout / user abandon

PHASE_B           -> PHASE_C             len(candidates) > 0
PHASE_B           -> DEGRADED            len(candidates) == 0

PHASE_C           -> PHASE_D             successful_extractions > 0
PHASE_C           -> PHASE_D             successful_extractions == 0 AND has_clawhub (degraded synthesis)
PHASE_C           -> DEGRADED            all workers failed AND no clawhub

PHASE_D           -> PHASE_E             synthesis.status == ok
PHASE_D           -> DEGRADED            synthesis failed (uses fast_path fallback)

PHASE_E           -> PHASE_F             compile.status == ok
PHASE_E           -> DEGRADED            compile failed (uses template fallback)

PHASE_F           -> PHASE_G             quality_score >= 60 AND no blockers
PHASE_F           -> PHASE_E             quality_score < 60 AND revise_count < 1 AND weakest_section exists
PHASE_F           -> DEGRADED            quality_score < 60 AND (revise_count >= 1 OR no weakest_section)
PHASE_F           -> DEGRADED            blockers present

PHASE_G           -> DONE                always

Any non-terminal  -> DEGRADED            budget exceeded
Any non-terminal  -> ERROR               unrecoverable exception
```

## 附录 B: 数据流图

```
User Input
    |
    v
+--------------------------------------------------------------+
| PHASE_A: NeedProfileBuilder + InputRouter                     |
|                                                               |
|   raw_input --> NeedProfile{keywords, intent, confidence}     |
|                     |                                         |
|                     v                                         |
|              InputRouter(NeedProfile) --> RoutingDecision      |
|              {route, skip_discovery, max_repos, repo_urls}    |
+---------------------------+----------------------------------+
                            |
              +-------------+------------------+
              |             |                  |
        DIRECT_URL    NAMED_PROJECT    DOMAIN_EXPLORE
        (skip B)      (targeted B)     (broad B)
              |             |                  |
              |    +--------v--------+         |
              |    | PHASE_B:        |         |
              |    | Discovery       |<--------+
              |    | -> candidates[] |
              |    +--------+--------+
              |             |
              +-------------+
                            |
              +-------------v--------------+
              | PHASE_C: WorkerSupervisor   |
              |                             |
              |   +-----+ +-----+ +-----+  |
              |   | W0  | | W1  | | W2  |  |
              |   |clone| |clone| |clone|  |
              |   |facts| |facts| |facts|  |
              |   |soul | |soul | |soul |  |
              |   |comm | |comm | |comm |  |
              |   +--+--+ +--+--+ +--+--+  |
              |      |       |       |      |
              |      v       v       v      |
              |   EnvelopeCollector          |
              |   -> qualified_envelopes[]  |
              +-------------+--------------+
                            |
              +-------------v--------------+
              | PHASE_D: SynthesisRunner    |
              | envelopes -> synthesis      |
              | {consensus_whys,            |
              |  divergent_whys,            |
              |  combined_traps,            |
              |  skill_contract}            |
              +-------------+--------------+
                            |
              +-------------v--------------+
              | PHASE_E: SkillCompiler      |
              | synthesis + bricks          |
              | -> SKILL.md                 |
              +-------------+--------------+
                            |
              +-------------v--------------+
              | PHASE_F: Validator          |
              | SKILL.md -> quality_score   |
              |                             |
              | >=60 + no blockers -> PASS  |
              | <60 + can revise -> REVISE  |<--+
              | <60 + exhausted -> DEGRADE  |   |
              +--+-------------+-----------+   |
                 |             |                |
                 | PASS   REVISE (max 1)       |
                 |             |                |
                 |             +----------------+
                 v                  (back to PHASE_E with
              +----------+         weakest_section hint)
              | PHASE_G:  |
              | Packager  |
              | -> SKILL.md|
              | + README  |
              | + provenance|
              | + limitations|
              +------+----+
                     |
                     v
                   DONE
```

## 附录 C: 接口定义汇总

### C.1 InputRouter

```python
class InputRouter:
    """确定性输入路由器。不使用 LLM。"""

    URL_PATTERN = re.compile(
        r'https?://(?:github|gitlab|gitee)\.com/[\w.-]+/[\w.-]+/?'
    )
    REPO_SLUG_PATTERN = re.compile(r'\b([\w.-]+/[\w.-]+)\b')
    PROJECT_NAME_PATTERN = re.compile(r'^[a-z0-9]([a-z0-9-]*[a-z0-9])?$')

    FALSE_POSITIVE_SLUGS = {
        "iOS/Android", "HTTP/2", "TCP/IP", "CI/CD",
        "input/output", "read/write", "on/off",
    }

    def route(self, profile: NeedProfile) -> RoutingDecision:
        """根据 NeedProfile 生成确定性路由决策。"""

        # 优先级 1: 精确 URL
        urls = self.URL_PATTERN.findall(profile.raw_input)
        if urls:
            return RoutingDecision(
                route="DIRECT_URL",
                skip_discovery=True,
                max_repos=len(urls),
                repo_urls=urls,
                project_names=[],
                confidence=1.0,
                reasoning=f"Found {len(urls)} explicit URL(s) in input",
            )

        # 优先级 2: repo slug (org/name)
        slugs = self.REPO_SLUG_PATTERN.findall(profile.raw_input)
        slugs = [s for s in slugs if s not in self.FALSE_POSITIVE_SLUGS]
        if slugs:
            return RoutingDecision(
                route="NAMED_PROJECT",
                skip_discovery=False,
                max_repos=min(len(slugs) + 1, 3),
                repo_urls=[],
                project_names=slugs,
                confidence=0.9,
                reasoning=f"Found repo slug(s): {slugs}",
            )

        # 优先级 3: 项目名（单词匹配）
        project_names = [
            kw for kw in profile.keywords
            if self.PROJECT_NAME_PATTERN.match(kw) and len(kw) >= 3
        ]
        if project_names and profile.confidence >= 0.7:
            return RoutingDecision(
                route="NAMED_PROJECT",
                skip_discovery=False,
                max_repos=min(len(project_names) + 1, 3),
                repo_urls=[],
                project_names=project_names,
                confidence=0.8,
                reasoning=f"Detected project name(s): {project_names}",
            )

        # 优先级 4: 低置信
        if profile.confidence < 0.7:
            return RoutingDecision(
                route="LOW_CONFIDENCE",
                skip_discovery=False,
                max_repos=3,
                repo_urls=[],
                project_names=[],
                confidence=profile.confidence,
                reasoning=f"Low confidence ({profile.confidence:.2f}), need clarification",
            )

        # 默认: 领域探索
        return RoutingDecision(
            route="DOMAIN_EXPLORE",
            skip_discovery=False,
            max_repos=3,
            repo_urls=[],
            project_names=[],
            confidence=profile.confidence,
            reasoning="Domain exploration mode",
        )
```

### C.2 WorkerSupervisor

```python
class WorkerSupervisor:
    """PHASE_C executor: 管理 fan-out repo workers。"""

    async def execute(
        self,
        input: RepoListInput,
        adapter: object,
        config: ExecutorConfig,
    ) -> ModuleResultEnvelope:

        # 1. 分配 worker 上下文
        contexts = self._allocate_workers(input.repos, config)

        # 2. Fan-out: ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=config.concurrency_limit) as pool:
            futures = {
                pool.submit(self._run_worker, ctx): ctx
                for ctx in contexts
            }

            envelopes = []
            for future in as_completed(futures, timeout=DEFAULT_WORKER_TIMEOUT):
                ctx = futures[future]
                try:
                    envelope = future.result()
                    envelopes.append(envelope)
                    # Emit worker_completed event
                    if config.event_bus:
                        config.event_bus.emit(
                            "worker_completed",
                            f"{ctx.repo_name} extraction complete",
                            phase="PHASE_C",
                            worker_id=ctx.worker_id,
                            meta={"extraction_confidence": envelope.extraction_confidence},
                        )
                except TimeoutError:
                    # Emit worker_failed event
                    envelopes.append(self._timeout_envelope(ctx))
                except Exception as e:
                    envelopes.append(self._error_envelope(ctx, e))

        # 3. Fan-in: EnvelopeCollector
        collection = EnvelopeCollector().collect(envelopes)

        # 4. 确定整体状态
        if collection.qualified_workers > 0:
            status = "ok"
        elif collection.successful_workers > 0:
            status = "degraded"
        else:
            status = "blocked"

        return ModuleResultEnvelope(
            module_name="WorkerSupervisor",
            status=status,
            data=collection,
            metrics=self._aggregate_metrics(envelopes),
        )

    def _run_worker(self, ctx: RepoWorkerContext) -> RepoExtractionEnvelope:
        """运行单个 repo worker。在独立线程中执行。"""
        worker = RepoWorker(ctx)
        return worker.run()

    def _allocate_workers(
        self, repos: list[dict], config: ExecutorConfig
    ) -> list[RepoWorkerContext]:
        """为每个 repo 分配 worker 上下文（含独立预算）。"""
        n = len(repos)
        per_worker_tokens = int(config.budget_remaining.remaining_tokens * 0.8 / max(n, 1))
        per_worker_cost = config.budget_remaining.remaining_usd * 0.8 / max(n, 1)

        contexts = []
        for i, repo in enumerate(repos):
            contexts.append(RepoWorkerContext(
                worker_id=f"worker-{i}",
                repo_url=repo.get("url", ""),
                repo_name=repo.get("name", f"repo-{i}"),
                repo_type=repo.get("_repo_type", "TOOL"),
                work_dir=config.run_dir / "workers" / f"worker-{i}",
                token_budget=per_worker_tokens,
                cost_budget_usd=per_worker_cost,
                timeout_seconds=180,
            ))
        return contexts
```

### C.3 RepoWorker

```python
class RepoWorker:
    """单 repo 提取 worker。在独立线程中运行。"""

    def __init__(self, ctx: RepoWorkerContext):
        self.ctx = ctx
        self.ctx.work_dir.mkdir(parents=True, exist_ok=True)

    def run(self) -> RepoExtractionEnvelope:
        self.ctx.status = "running"
        self.ctx.started_at = time.monotonic()

        try:
            # Step 1: Clone
            local_path = self._clone_repo()

            # Step 2: Extract facts (deterministic, no LLM)
            facts = self._extract_facts(local_path)

            # Step 3: Classify type
            repo_type = self._classify_type(facts)

            # Step 4: Extract soul
            if repo_type == "CATALOG":
                soul = self._shallow_extract(local_path, facts)
            else:
                soul = self._deep_extract(local_path, facts)

            # Step 5: Community signals
            signals = self._collect_community(self.ctx.repo_url, local_path)

            # Step 6: Build envelope
            self.ctx.status = "done"
            self.ctx.finished_at = time.monotonic()

            return RepoExtractionEnvelope(
                worker_id=self.ctx.worker_id,
                repo_name=self.ctx.repo_name,
                repo_url=self.ctx.repo_url,
                repo_type=repo_type,
                design_philosophy=soul.get("design_philosophy"),
                mental_model=soul.get("mental_model"),
                why_decisions=soul.get("why_decisions", []),
                unsaid_traps=soul.get("unsaid_traps", []),
                feature_inventory=soul.get("feature_inventory", []),
                community_signals=signals,
                extraction_confidence=self._compute_confidence(soul, facts),
                evidence_count=self._count_evidence(soul),
                metrics=self._build_metrics(),
                status="ok",
            )
        except Exception as e:
            self.ctx.status = "failed"
            self.ctx.finished_at = time.monotonic()
            return RepoExtractionEnvelope(
                worker_id=self.ctx.worker_id,
                repo_name=self.ctx.repo_name,
                repo_url=self.ctx.repo_url,
                repo_type=self.ctx.repo_type,
                extraction_confidence=0.0,
                evidence_count=0,
                metrics=self._build_metrics(),
                status="failed",
                warnings=[str(e)],
            )
```

---

## 附录 D: 设计决策索引

| 决策 | 选择 | 备选方案 | WHY 选择当前方案 |
|------|------|---------|----------------|
| 路由位置 | PHASE_A 内部 | 独立 PHASE_ROUTE | 路由依赖 profile，放一起减少状态传递 |
| 路由方式 | 确定性正则 | LLM 分类 | 可重复、可测试、零成本、零延迟 |
| 并发模型 | ThreadPoolExecutor | asyncio / multiprocessing | 已有代码用线程池，LLM I/O 足够，改造成本低 |
| Worker 隔离 | 独立目录+预算 | 共享上下文 | 防止上下文污染，DeerFlow 验证此模式 |
| REVISE 次数 | 1 次 | 3 次（当前） | 编译是瓶颈（138s），3 次 = +7 分钟，ROI 太低 |
| 靶向修复 | 只重编译最弱 section | 全量重编译 | 节省时间，精准修复比随机重试有效 |
| 事件持久化 | JSONL 文件 | SQLite / Redis | 简单、可 tail、数据量小、跨平台 |
| singleshot | 保留不改 | 同步改造 | 降低风险，controller 路径已存在 |
| Phase 编号 | A-G 重映射 | 保持原编号 | 消除 PHASE_CD 混淆，每个 phase 职责单一 |
| 降级策略 | 每阶段独立定义 | 全局布尔开关 | 精细控制，不同阶段失败有不同最佳应对 |
| Socratic Gate | 最多 2 轮 | 1 轮（当前） / 无限 | 1 轮不够精确，3+ 轮用户不耐烦，2 轮平衡 |
| 最大 workers | 3 | 5 / 无限 | 平台限制 + API 速率 + 效用递减 |
| fan-in 阈值 | confidence >= 0.3 | >= 0.5 / >= 0.7 | 0.3 保留弱但有价值的提取，合成时加权处理 |

---

*文档结束。本文档为 v12.1.1 架构设计的完整参考，后续实现阶段应以本文档为权威来源。*
