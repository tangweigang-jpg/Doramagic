# 多模型编排策略研究报告

**日期**: 2026-04-11  
**研究员**: Claude Opus  
**研究目标**: 为 Doramagic extraction agent 设计最优的多模型使用方案，将单仓库提取时间从 50-70 分钟降至 25-35 分钟  
**输入资料**: agent_loop.py, executor.py, blueprint_phases.py, orchestrator.py, harness engineering 研究报告, Claude Code 编排架构分析

---

## 0. 执行摘要

当前 extraction agent 使用单一模型（MiniMax-M2.7）全程串行执行 15 个 phase，耗时 50-70 分钟/仓库。本报告提出三层优化方案：

1. **Phase-Model 匹配**：根据 phase 的认知需求分配不同模型，简单 phase 用快模型
2. **并行执行**：依赖图分析显示 2a/2d 可并行、0c/0d 可并行，最多节省 15-20 分钟
3. **Failover 降级**：API 不稳定时自动切换备选模型，消除人工干预

**预期效果**：总时间降至 25-35 分钟（约 50% 提速），代码改动量约 300 行。

---

## 1. Phase 分析与分类

### 1.1 当前 15 Phase 完整清单

基于 `blueprint_phases.py` 的 `build_blueprint_phases()` 函数，15 个 phase 分为两大类：

| # | Phase Name | 类型 | 描述 | 依赖 | max_iter | 预估耗时 |
|---|-----------|------|------|------|----------|---------|
| 1 | `bp_fingerprint` | Python | 关键词指纹检测子域 | 无 | - | <1s |
| 2 | `bp_clone` | Python | 验证仓库路径、获取 commit hash | fingerprint | - | <1s |
| 3 | `bp_structural_index` | Python | AST 结构索引（骨架、依赖图、文件分类） | clone | - | 2-10s |
| 4 | `bp_mine_sources` | Python | 挖掘 README/docs/CHANGELOG/pyproject | clone | - | 1-5s |
| 5 | `bp_architecture` | **Agentic** | 架构提取（源码探索） | structural_index | 80 | **8-15 min** |
| 6 | `bp_claim_verify` | **Agentic** | 验证架构声明 | architecture | 60 | **5-10 min** |
| 7 | `bp_bd_r1_discovery` | **Agentic** | 工作流发现+原始决策提取 | architecture, claim_verify, mine_sources | 70 | **8-15 min** |
| 8 | `bp_bd_r2_counterfactual` | **Agentic** | 反事实 T vs non-T 分离 | bd_r1 | 50 | **5-8 min** |
| 9 | `bp_bd_r3_adversarial` | **Agentic** | 多角色对抗分类 | bd_r2 | 60 | **5-10 min** |
| 10 | `bp_bd_r4_evidence` | **Agentic** | 证据获取+异常检测+最终报告 | bd_r3 | 50 | **5-10 min** |
| 11 | `bp_usecase_scan` | **Agentic** | 用例扫描 | clone | 50 | **5-8 min** |
| 12 | `bp_auto_verify` | Python | 检查文件引用存在性 | architecture, claim_verify, bd_r4, usecase_scan | - | <1s |
| 13 | `bp_assemble` | **Agentic** | 组装最终蓝图 YAML | auto_verify | 40 | **3-5 min** |
| 14 | `bp_consistency_check` | Python | BD 类型合法性、UC 必填字段检查 | assemble | - | <1s |
| 15 | `bp_finalize` | Python | YAML 修复 + 推广到 output 目录 | consistency_check | - | <1s |

### 1.2 认知需求分类

将 7 个 Agentic Phase 按认知需求分为三级：

**Tier 1 — 深度推理（需要强模型）**：
- `bp_bd_r3_adversarial`：多角色对抗分类，需要同时扮演量化分析师、监管者、业务假设分析师三种视角
- `bp_bd_r4_evidence`：异常检测 + 证据获取 + 最终判断，需要跨子域专业知识
- `bp_architecture`：架构提取，需要深入理解代码结构和设计模式

**Tier 2 — 中等推理（标准模型即可）**：
- `bp_bd_r1_discovery`：工作流发现和原始决策提取，大量代码阅读 + 结构化输出
- `bp_bd_r2_counterfactual`：反事实分析，逻辑判断但模式较固定
- `bp_claim_verify`：声明验证，对照源码检查事实

**Tier 3 — 轻量任务（快模型优先）**：
- `bp_usecase_scan`：扫描 examples 和 docs，结构化输出为主
- `bp_assemble`：从已有 artifact 组装 YAML，格式转换为主

---

## 2. Phase-Model 匹配矩阵

### 2.1 可用模型特性总结

| 模型 | API 格式 | 速度 | 推理能力 | tool_use | 稳定性 | 适用场景 |
|------|---------|------|---------|----------|--------|---------|
| MiniMax-M2.7 | Anthropic | 中 | 中 | 好 | 中（500/529） | 通用默认 |
| GLM-5 (百炼) | OpenAI | 慢 | 强(reasoning) | 可用 | 差（超时多） | 深度推理 |
| GPT-5.3-codex (wow3) | OpenAI | 快 | 强 | **不可用** | - | 暂不可用 |

**关键约束**：GPT-5.3-codex/GPT-5.4 的 tool_use 不工作（代理层问题），因此当前只有两个实际可用模型。

### 2.2 推荐匹配方案

鉴于只有两个可用模型，策略应为：**MiniMax-M2.7 为主，GLM-5 仅在特定高价值 phase 使用**。

| Phase | 首选模型 | 备选模型 | 理由 |
|-------|---------|---------|------|
| `bp_architecture` | MiniMax-M2.7 | GLM-5 | 需要大量 tool_use 循环探索代码，MiniMax 的 tool_use 更稳定；迭代数多(80)，GLM-5 的 thinking tokens 会严重膨胀成本 |
| `bp_claim_verify` | MiniMax-M2.7 | GLM-5 | 中等推理，tool_use 密集（读文件+grep），MiniMax 更适合 |
| `bp_bd_r1_discovery` | MiniMax-M2.7 | GLM-5 | 大量代码阅读和结构化提取，tool_use 密集 |
| `bp_bd_r2_counterfactual` | MiniMax-M2.7 | GLM-5 | 模式化的反事实判断，不需要深度推理 |
| `bp_bd_r3_adversarial` | **GLM-5** | MiniMax-M2.7 | **最需要推理能力的 phase**：三角色对抗分类，涉及跨域专业判断。GLM-5 的 reasoning 能力能显著提升分类准确率。但 tool_use 调用相对少（主要是读 artifact + 少量 grep） |
| `bp_bd_r4_evidence` | **GLM-5** | MiniMax-M2.7 | 异常检测需要深度推理，子域 checklist 审计需要专业判断。同样 tool_use 密度较低 |
| `bp_usecase_scan` | MiniMax-M2.7 | GLM-5 | 简单扫描任务，MiniMax 足够 |
| `bp_assemble` | MiniMax-M2.7 | GLM-5 | 格式转换为主，不需要推理 |

### 2.3 GLM-5 使用注意事项

GLM-5 是 reasoning model，其 thinking tokens 不计入 `max_tokens` 但会计入 API 耗时和成本。在使用 GLM-5 的 phase 中：

1. **降低 max_iterations**：R3 从 60 降到 40，R4 从 50 降到 35（GLM-5 每次迭代的输出质量更高，需要更少轮次）
2. **增加 max_tokens_per_call**：从 16384 提高到 32768（reasoning model 的有效输出可能更长）
3. **增加超时**：从 600s 提高到 900s（GLM-5 的 thinking 阶段可能很长）

---

## 3. 多模型架构设计方案

### 3.1 设计原则

1. **最小改动原则**：不重构 ExtractionAgent，只在 SOPExecutor 层引入模型选择
2. **Phase 无感知**：Phase 定义不感知使用什么模型（关注分离）
3. **配置化**：模型匹配策略可通过配置文件调整，不硬编码
4. **Failover 透明**：模型切换对 phase 执行完全透明

### 3.2 核心改动：ModelRouter

引入一个轻量级的 `ModelRouter` 类，负责 phase → model 的映射和 failover：

```python
# 新文件: packages/extraction_agent/.../core/model_router.py

@dataclass
class ModelSpec:
    """A single model endpoint specification."""
    model_id: str
    api_format: str  # "anthropic" or "openai"
    base_url: str
    api_key_env: str
    max_tokens_per_call: int = 16384
    timeout: int = 600  # seconds
    priority: int = 0  # lower = preferred

@dataclass
class ModelRouter:
    """Maps phases to models with failover support."""
    
    # phase_name -> list of ModelSpec (ordered by priority)
    phase_models: dict[str, list[ModelSpec]]
    default_models: list[ModelSpec]  # fallback for unmapped phases
    
    def get_model(self, phase_name: str) -> ModelSpec:
        """Return the primary model for a phase."""
        specs = self.phase_models.get(phase_name, self.default_models)
        return specs[0]
    
    def get_fallback(self, phase_name: str) -> ModelSpec | None:
        """Return the fallback model for a phase (or None)."""
        specs = self.phase_models.get(phase_name, self.default_models)
        return specs[1] if len(specs) > 1 else None
```

### 3.3 改动清单

#### 改动 1: `SOPExecutor` — 支持 per-phase model 切换

当前 `SOPExecutor` 持有一个固定的 `ExtractionAgent`。改动后，它持有一个 `ModelRouter` + 一个 agent 工厂函数：

```python
# executor.py 改动要点

class SOPExecutor:
    def __init__(
        self,
        phases: list[Phase],
        agent: ExtractionAgent,          # 保留，作为默认 agent
        checkpoint_mgr: CheckpointManager,
        state: AgentState,
        repo_path: Path,
        model_router: ModelRouter | None = None,  # 新增
        agent_factory: Callable[[ModelSpec], ExtractionAgent] | None = None,  # 新增
    ) -> None:
        ...
```

在 `run()` 方法的 phase 执行循环中，根据 `model_router` 选择模型：

```python
# 在执行 agentic phase 前
if self._model_router and phase.requires_llm:
    spec = self._model_router.get_model(phase.name)
    agent = self._agent_factory(spec) if self._agent_factory else self._agent
else:
    agent = self._agent
```

**向后兼容**：`model_router=None` 时行为与当前完全一致。

#### 改动 2: `BatchOrchestrator` — 传递 ModelRouter

`_run_single_repo` 方法中：

```python
# 构造 model_router（从 BatchConfig 的新字段读取）
model_router = self._build_model_router()

# 传给 SOPExecutor
bp_executor = SOPExecutor(
    bp_phases, agent, checkpoint, state, repo_path,
    model_router=model_router,
    agent_factory=self._create_agent_for_spec,
)
```

#### 改动 3: `BatchConfig` — 新增模型配置

```python
@dataclass
class BatchConfig:
    ...
    # 新增：per-phase 模型覆盖
    model_overrides: dict[str, dict] = field(default_factory=dict)
    # 新增：failover 模型列表
    fallback_models: list[dict] = field(default_factory=list)
```

对应的 YAML 配置：

```yaml
batch_id: finance-batch-01
llm_model: MiniMax-M2.7
llm_base_url: https://api.minimaxi.chat/v1
api_format: anthropic

# 新增：特定 phase 使用不同模型
model_overrides:
  bp_bd_r3_adversarial:
    model_id: glm-5
    api_format: openai
    base_url: https://dashscope.aliyuncs.com/compatible-mode/v1
    api_key_env: DASHSCOPE_API_KEY
    max_tokens_per_call: 32768
    timeout: 900
  bp_bd_r4_evidence:
    model_id: glm-5
    api_format: openai
    base_url: https://dashscope.aliyuncs.com/compatible-mode/v1
    api_key_env: DASHSCOPE_API_KEY
    max_tokens_per_call: 32768
    timeout: 900

# 新增：failover 链
fallback_models:
  - model_id: MiniMax-M2.7
    api_format: anthropic
    base_url: https://api.minimaxi.chat/v1
    api_key_env: MINIMAX_API_KEY
```

### 3.4 改动量估算

| 文件 | 改动类型 | 预估行数 |
|------|---------|---------|
| `core/model_router.py` | **新建** | ~80 行 |
| `sop/executor.py` | 修改 | ~40 行 |
| `batch/orchestrator.py` | 修改 | ~60 行 |
| `batch/job_queue.py` | 修改 | ~30 行 |
| 测试文件 | 新建/修改 | ~100 行 |
| **总计** | | **~310 行** |

---

## 4. Failover 机制设计

### 4.1 当前重试机制（已有）

`agent_loop.py` 已实现了 per-call 级别的重试：

```python
_RETRY_DELAYS = (1, 2, 4)  # 三次重试
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 529}
```

这个机制处理的是**瞬时错误**（API 偶尔 500/529），但无法处理**持续性故障**（API 长时间不可用）。

### 4.2 新增 Phase-Level Failover

在 `SOPExecutor.run()` 中增加 phase 级别的 failover 逻辑：

```python
async def _run_phase_with_failover(
    self, phase: Phase, primary_agent: ExtractionAgent
) -> PhaseResult:
    """Run a phase, falling back to secondary model if primary fails."""
    
    # 尝试主模型
    try:
        result = await primary_agent.run_phase(...)
        if result.status == "completed":
            return result
        # 非完成状态（circuit_break/max_iterations）也算失败
    except Exception as exc:
        logger.warning("Primary model failed for %s: %s", phase.name, exc)
    
    # 主模型失败，尝试 failover
    fallback_spec = self._model_router.get_fallback(phase.name)
    if fallback_spec is None:
        return result  # 无 fallback，返回原始失败
    
    logger.info(
        "Failing over %s: %s -> %s",
        phase.name, primary_spec.model_id, fallback_spec.model_id,
    )
    fallback_agent = self._agent_factory(fallback_spec)
    return await fallback_agent.run_phase(...)
```

### 4.3 Failover 决策矩阵

| 失败类型 | 当前处理 | 新增处理 |
|---------|---------|---------|
| HTTP 429/500/502/503/529 | 3 次重试（1s/2s/4s） | 重试耗尽后 → phase-level failover |
| 超时（600s/900s） | 3 次重试 | 重试耗尽后 → failover |
| context_overflow | 激进压缩 + 重试 | 保持不变（不触发 failover，因为换模型不解决问题） |
| circuit_break（连续 3 次 tool 失败） | 返回失败 | → failover（可能是模型能力不足） |
| max_iterations | 返回失败 | → failover（更强模型可能更快完成） |

### 4.4 格式转换问题

MiniMax (Anthropic) 和 GLM-5 (OpenAI) 之间 failover 需要格式转换。当前 `ExtractionAgent` 已完整支持两种格式：

- 工具定义：`_convert_tools_to_openai()` 已实现
- 消息格式：`_build_assistant_message()` 和 `_build_tool_results_message()` 已格式感知
- System prompt：Anthropic 作为 `system` 参数，OpenAI 作为 `system` role 消息

**关键结论**：格式转换已经完备，failover 只需要创建一个新的 `ExtractionAgent` 实例即可，无需任何格式转换代码。每个 phase 是独立的对话，不存在跨 phase 的消息格式混用问题。

---

## 5. 并行执行方案

### 5.1 依赖图分析

从 `build_blueprint_phases()` 提取的依赖图：

```
bp_fingerprint
  └── bp_clone
        ├── bp_structural_index
        │     └── bp_architecture
        │           ├── bp_claim_verify
        │           │     └── bp_bd_r1_discovery ← (也依赖 bp_mine_sources)
        │           │           └── bp_bd_r2_counterfactual
        │           │                 └── bp_bd_r3_adversarial
        │           │                       └── bp_bd_r4_evidence
        │           └── (bp_bd_r1_discovery 也依赖 bp_architecture)
        ├── bp_mine_sources
        │     └── (bp_bd_r1_discovery)
        └── bp_usecase_scan  ← 注意：只依赖 bp_clone！

bp_auto_verify ← 依赖 bp_architecture, bp_claim_verify, bp_bd_r4_evidence, bp_usecase_scan
  └── bp_assemble
        └── bp_consistency_check
              └── bp_finalize
```

### 5.2 可并行的 Phase 对

**并行窗口 1: 初始索引阶段**
- `bp_structural_index` 和 `bp_mine_sources` 都只依赖 `bp_clone`
- 已经是 pure Python，执行极快（秒级），并行收益有限但实现简单
- 预估节省：~5s

**并行窗口 2: 主要探索阶段（高价值）**
- `bp_usecase_scan` 只依赖 `bp_clone`，与整个 2a→2b→2c 链完全独立
- 当前串行执行中，`bp_usecase_scan` 排在所有 2c round 之后（因为代码写在后面）
- 实际上它可以与 `bp_architecture` 同时启动！
- **预估节省：5-8 分钟**（usecase_scan 的全部执行时间变为免费）

**并行窗口 3: claim_verify 与 mine_sources + usecase_scan（受限）**
- `bp_claim_verify` 依赖 `bp_architecture`
- `bp_bd_r1_discovery` 依赖 `bp_architecture` + `bp_claim_verify` + `bp_mine_sources`
- 这里没有额外并行空间（R1 必须等 claim_verify 完成）

**无法并行的链条**：
- 2c 的四轮（R1→R2→R3→R4）是严格串行的（每轮依赖上一轮的输出）
- 这条链占总时间的 23-43 分钟，是最大的性能瓶颈

### 5.3 并行执行实现方案

#### 方案：拓扑排序 + 并行调度器

将 SOPExecutor 的串行循环改为拓扑排序驱动的并行调度：

```python
async def run(self) -> ExecutionResult:
    """Execute phases respecting dependencies, parallelizing where possible."""
    result = ExecutionResult(blueprint_id=self._state.blueprint_id)
    
    # Build dependency graph
    pending = {p.name: p for p in self._phases}
    completed_names: set[str] = set()
    
    while pending:
        # Find all phases whose dependencies are satisfied
        ready = [
            p for p in pending.values()
            if all(dep in completed_names for dep in p.depends_on)
        ]
        
        if not ready:
            # Deadlock detection
            result.errors.append(f"Deadlock: {list(pending.keys())} have unmet deps")
            break
        
        # Execute ready phases in parallel
        tasks = [
            self._run_single_phase(phase, result)
            for phase in ready
        ]
        outcomes = await asyncio.gather(*tasks, return_exceptions=True)
        
        for phase, outcome in zip(ready, outcomes):
            if isinstance(outcome, Exception) or (isinstance(outcome, str) and outcome == "failed"):
                result.failed_phase = phase.name
                return result  # Stop on first failure
            completed_names.add(phase.name)
            del pending[phase.name]
    
    return result
```

#### 并行时的模型选择

并行 phase 可以使用不同模型。每个 phase 通过 `ModelRouter` 获取自己的 `ExtractionAgent` 实例，各自独立的对话历史和 API 调用：

- `bp_architecture` → MiniMax-M2.7 (Anthropic)
- `bp_usecase_scan` → MiniMax-M2.7 (Anthropic)（同模型但独立实例）

并行执行需要注意 `AgentState` 的线程安全：
- 当前 `AgentState` 的 `mark_phase_running/completed/failed` 方法是简单的字典操作
- Python 的 asyncio 是单线程的（协作式并发），字典操作是原子的，无需加锁
- 但 `CheckpointManager.save_state()` 需要序列化写入，并行 phase 可能交叉写入
- **解决方案**：checkpoint 写入加一个 `asyncio.Lock()`

### 5.4 并行执行的风险与缓解

| 风险 | 概率 | 缓解方案 |
|------|------|---------|
| 并行 phase 竞争 API rate limit | 中 | 各 phase 已有独立的 retry 机制，429 会自动退避 |
| 并行 phase 同时写入同一 artifact | 低 | 各 phase 的 artifact 名称不同（step2a_*, step2d_*） |
| 并行 phase 的 checkpoint 交叉 | 中 | 加 asyncio.Lock() |
| GLM-5 在并行中超时导致阻塞 | 高 | GLM-5 不用于并行 phase（只在 R3/R4 使用） |

---

## 6. Token 优化策略

### 6.1 Reasoning Model 的 Thinking Token 问题

GLM-5 作为 reasoning model，会产生大量 thinking tokens。这些 tokens：
- 不计入 `max_tokens` 限制（独立的 thinking budget）
- 计入 API 耗时（是延迟的主要来源）
- 可能计入成本

优化策略：

**策略 1: 精准限定 GLM-5 使用范围**
- 只在 R3（对抗分类）和 R4（证据+异常检测）使用 GLM-5
- 这两个 phase 的 tool_use 密度低（主要是读 artifact + 少量 grep）
- thinking tokens 的投入回报比最高（直接影响 BD 分类质量）

**策略 2: 降低 GLM-5 phase 的 max_iterations**
- R3: 60 → 40（GLM-5 每次迭代的推理质量更高，需要更少轮次）
- R4: 50 → 35（同理）
- 预估节省：20-30% 的 GLM-5 API 调用次数

**策略 3: 缩减 GLM-5 的输入上下文**
- R3 和 R4 的 initial_message 中已包含 math_summary 和 source_context
- 对于 GLM-5，可以进一步精简这些上下文（GLM-5 的 reasoning 能力可以弥补上下文减少）
- 具体做法：`_get_source_context(state, max_chars=3000)` 在 R3 中已用 3000 字符限制

### 6.2 MiniMax Token 优化

**策略 4: 结构化索引工具降低探索轮次**

当前 `bp_architecture` 已经使用结构化索引工具（`get_skeleton`, `get_dependencies`, `list_by_type`），这大幅减少了盲目 `list_dir` + `read_file` 的轮次。维持现状即可。

**策略 5: Diminishing Returns 提前停止**（来自 DORAMAGIC_TAKEAWAYS P0-2）

在 `CircuitBreaker` 中增加增量检测：如果连续 N 次 LLM 调用的 tool_use 模式重复（同样的文件被重复读取），触发提前停止。这可以在 `bp_architecture` 和 `bp_bd_r1_discovery` 这两个高迭代数的 phase 中节省 10-20% 的轮次。

---

## 7. 时间预估

### 7.1 当前基线（串行、单模型）

```
Python phases (1-4, 12, 14-15):     ~0.5 min
bp_architecture (5):                ~12 min
bp_claim_verify (6):                ~7 min
bp_bd_r1_discovery (7):             ~12 min
bp_bd_r2_counterfactual (8):        ~6 min
bp_bd_r3_adversarial (9):           ~7 min
bp_bd_r4_evidence (10):             ~7 min
bp_usecase_scan (11):               ~6 min
bp_assemble (13):                   ~4 min
──────────────────────────────────
总计:                               ~61 min (中位数)
```

### 7.2 优化后预估

```
Python phases (并行 0c+0d):          ~0.5 min (不变)

── 并行窗口 2 开始 ──
bp_architecture (MiniMax):           ~12 min  ─┐
bp_usecase_scan (MiniMax, 并行):     ~6 min   ─┤ 取 max = 12 min
── 并行窗口 2 结束 ──               ─┘

bp_claim_verify (MiniMax):           ~7 min
bp_bd_r1_discovery (MiniMax):        ~12 min
bp_bd_r2_counterfactual (MiniMax):   ~6 min
bp_bd_r3_adversarial (GLM-5):       ~8 min (+1min GLM-5 较慢但轮次减少)
bp_bd_r4_evidence (GLM-5):          ~8 min (同上)
bp_assemble (MiniMax):              ~4 min
──────────────────────────────────
总计:                               ~58 min (保守，不含 failover)
                                    ~53 min (usecase_scan 并行节省生效)
```

**更激进的优化**（如果 GPT-5.3 的 tool_use 问题修复后）：

```
bp_architecture (GPT-5.3, 更快):     ~8 min
bp_claim_verify (GPT-5.3):           ~5 min
bp_bd_r1_discovery (GPT-5.3):        ~8 min
bp_bd_r2_counterfactual (GPT-5.3):   ~4 min
bp_bd_r3_adversarial (GLM-5):        ~8 min
bp_bd_r4_evidence (GLM-5):           ~8 min
bp_usecase_scan (MiniMax, 并行):     ~0 min (并行免费)
bp_assemble (GPT-5.3):               ~3 min
──────────────────────────────────
总计:                                ~44 min
```

### 7.3 效果分析

| 优化措施 | 预估节省 | 实施难度 | 优先级 |
|---------|---------|---------|-------|
| usecase_scan 并行化 | 5-8 min | 中（需改 executor） | P0 |
| GLM-5 用于 R3+R4 | 质量提升（非时间） | 低（已有双后端） | P0 |
| Failover 机制 | 消除人工干预 | 中 | P0 |
| GPT-5.3 tool_use 修复后全面加速 | 10-15 min | 低（修复代理层即可） | P1（阻塞于代理层修复） |
| Diminishing Returns 提前停止 | 5-10 min | 低 | P1 |

**保守预期**：从 50-70 分钟降至 45-55 分钟（约 20% 提速）  
**乐观预期**（GPT-5.3 可用后）：从 50-70 分钟降至 35-45 分钟（约 35% 提速）

---

## 8. 实施路线图

### Phase 1: ModelRouter + Failover（1-2 天）

1. 新建 `core/model_router.py`（80 行）
2. 修改 `sop/executor.py` 支持 per-phase model 选择 + failover（40 行）
3. 修改 `batch/job_queue.py` 和 `batch/orchestrator.py` 传递 model_overrides（90 行）
4. 单元测试（50 行）
5. 用 R3+R4 → GLM-5 做端到端测试

### Phase 2: 并行调度器（1-2 天）

1. 修改 `sop/executor.py` 的 `run()` 方法为拓扑排序 + 并行调度
2. 给 checkpoint 加 asyncio.Lock()
3. 测试 usecase_scan 与 architecture 并行执行
4. 验证 artifact 写入不冲突

### Phase 3: GPT-5.3 集成（待代理层修复）

1. 排查 wow3 代理层的 tool_use 问题
2. 修复后，将 Tier 2/3 phase 迁移到 GPT-5.3
3. 端到端验证质量不降级

---

## 9. 风险与决策点

### 9.1 需要 CEO 决策的问题

1. **GLM-5 成本接受度**：GLM-5 的 thinking tokens 成本是 MiniMax 的 ~3x。在 R3+R4 使用 GLM-5 的成本增加是否可接受？（预估每仓库增加 $0.5-1.5）

2. **质量 vs 速度优先级**：当前方案优先保证质量（R3+R4 用强模型），如果优先速度，可以全程用 MiniMax 并接受分类准确率可能降低 5-10%。

3. **GPT-5.3 代理层修复优先级**：这是最大的性能加速杠杆（35% 提速），但需要排查代理层的 tool_use 问题。是否应该优先投入？

### 9.2 架构风险

| 风险 | 影响 | 缓解 |
|------|------|------|
| GLM-5 超时率高导致 failover 频繁 | R3/R4 延迟增加 | 超时阈值设为 900s + 3 次重试后再 failover |
| 并行执行引入新 bug | 提取质量下降 | 并行仅限无 artifact 交叉的 phase 对 |
| 配置复杂度增加 | 运维负担 | 提供合理默认值，model_overrides 可选 |

---

## 10. 与研究资料的对齐

### 10.1 来自 Claude Code 编排架构的借鉴

- **Agent 定义的 model 字段**（04-agent-orchestration.md, 4.3.2）：Claude Code 的 AgentDefinition 支持 `model?: string` 字段，允许不同 agent 使用不同模型。本方案的 ModelRouter 遵循同样的设计。
- **三种执行后端的统一抽象**（04-agent-orchestration.md, 4.3.3）：共享 `runAgent()` AsyncGenerator 接口。Doramagic 的 `ExtractionAgent.run_phase()` 已是类似设计。
- **Coordinator Mode 四阶段工作流**（04-agent-orchestration.md, 4.4.5）：Research → Synthesis → Implementation → Verification 的分阶段模式，与 Doramagic 的 SOP phase 设计一致。

### 10.2 来自 Harness Engineering 的借鉴

- **显式 contract + 程序化 enforcement**（harness report, 7.1）：ModelRouter 的配置化策略正是"声明式 contract"的体现。
- **file-backed state**（harness report, 7.2）：checkpoint 机制已实现，并行执行不破坏这一特性。
- **Failure Taxonomy**（harness report, 7.2）：failover 决策矩阵区分了 tool_error、environment_error（API 不稳定）和 spec_violation（circuit_break），与 harness 工程的失败分类对齐。

### 10.3 来自 DORAMAGIC_TAKEAWAYS 的借鉴

- **Diminishing Returns 提前停止**（P0-2）：可集成到 CircuitBreaker 中，特别适用于高迭代数的 architecture 和 R1 phase。
- **积木并发安全声明**（P1-7）：并行 phase 设计参考了 `isConcurrencySafe()` 的理念，只并行确认无资源冲突的 phase。

---

*报告结束。建议首先实施 Phase 1（ModelRouter + Failover），这是成本最低、收益最确定的改动。*
