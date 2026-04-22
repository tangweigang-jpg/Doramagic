# Pattern 提取与编译集成研究报告（Claude 视角）

> 研究者：Claude Opus 4.6 | 日期：2026-04-06
> 定位：四方研究之一（Claude / Grok / Gemini / GPT），提供独立 Pattern 架构设计

---

## 0. 核心洞察

Doramagic 当前的两层架构（Blueprint + Constraint）解决了"框架怎么用"和"什么不能做"，但缺失"用它能做什么"。这不是信息缺失，而是**知识类型缺失**——开源项目中存在大量可复用的业务逻辑（strategies, workflows, research methodologies），它们散落在 `examples/`、`notebooks/`、`docs/tutorials/`、源码内置组件中，从未被结构化提取。

**关键判断**：Pattern 不是"第三层"，而是与 Blueprint 正交的**横向维度**。Blueprint 是纵向的框架架构切片，Pattern 是横向的业务用例切片。两者的笛卡尔积才是完整的知识空间。

---

## 1. Pattern Schema 设计

### 1.1 设计原则

1. **与现有 Schema 兼容**：ID 命名、域分组、applies_to 挂载点均复用现有约定
2. **LLM 可消费**：字段命名和结构对 LLM 友好，避免过度嵌套
3. **参数化优先**：硬编码值和可配置参数必须显式分离
4. **粒度适中**：一个 Pattern = 一个"可独立执行的业务目标"

### 1.2 Schema 定义（v0.1）

```yaml
# ============================================================
# Pattern Schema v0.1
# 一个 Pattern = 一个可复用的业务逻辑模板
# ============================================================

# --- 身份 ---
id: "finance-P-001"                    # 格式: {domain}-P-{序号}
name: "20日动量因子截面选股"              # 人类可读名
version: "1.0.0"

# --- 来源追溯 ---
source:
  extracted_from:                       # 提取来源（可多个）
    - type: "example"                   # example | notebook | tutorial | source_code | test
      project: "stefan-jansen/zipline-reloaded"
      path: "zipline/examples/buyapple.py"
      description: "官方示例：买入苹果策略"
    - type: "notebook"
      project: "stefan-jansen/zipline-reloaded"
      path: "notebooks/pipeline_tutorial.ipynb"
      description: "Pipeline API 教程"
  extraction_date: "2026-04-06"
  confidence: 0.85                      # 提取置信度

# --- 蓝图绑定 ---
applies_to:
  blueprint_ids:                        # 主绑定蓝图（必须至少一个）
    - "finance-bp-002"                  # zipline
  compatible_blueprints:                # 兼容但未验证的蓝图
    - "finance-bp-001"                  # freqtrade（理论可行）
    - "finance-bp-005"                  # rqalpha
  stage_mapping:                        # Pattern 步骤 → 蓝图阶段的映射
    data_preparation: "data_layer"
    signal_generation: "pipeline_api"
    portfolio_construction: "user_strategy"
    execution: "event_loop"
    evaluation: "evaluation"

# --- 域与分类 ---
domain: "finance"
category: "factor_strategy"             # 业务类别
tags:
  - "momentum"
  - "cross-sectional"
  - "equity"
  - "long-only"

# --- 业务目标 ---
objective:
  goal: "基于动量因子进行截面选股，构建多头组合"
  input_description: "股票池的历史价格数据"
  output_description: "组合绩效报告（年化收益、最大回撤、夏普比率）"
  success_criteria:
    - "回测完整运行，无报错"
    - "产出 ANNUAL_RETURN / MAX_DRAWDOWN / SHARPE 三项指标"
    - "策略逻辑可解释"

# --- 参数定义 ---
parameters:
  - name: "momentum_window"
    type: "int"
    default: 20
    range: [5, 120]
    description: "动量计算窗口（交易日）"
    sensitivity: "high"                 # 对结果影响程度: high | medium | low

  - name: "top_n"
    type: "int"
    default: 5
    range: [3, 50]
    description: "持仓股票数量"
    sensitivity: "high"

  - name: "rebalance_frequency"
    type: "enum"
    default: "daily"
    options: ["daily", "weekly", "monthly"]
    description: "调仓频率"
    sensitivity: "medium"

  - name: "stock_pool"
    type: "list[str]"
    default: null                       # null = 需要用户提供
    description: "股票池代码列表"
    sensitivity: "high"

  - name: "commission_rate"
    type: "float"
    default: 0.0003
    range: [0, 0.01]
    description: "交易佣金率"
    sensitivity: "low"

# --- 执行步骤 ---
steps:
  - id: "data_preparation"
    order: 1
    name: "数据准备"
    description: "获取股票池历史价格数据，处理缺失值和异常值"
    inputs:
      - name: "stock_pool"
        from: "parameters.stock_pool"
      - name: "date_range"
        from: "parameters.start_date + parameters.end_date"
    outputs:
      - name: "price_panel"
        schema: "DataFrame(index=DatetimeIndex, columns=stock_codes, values=adjusted_close)"
    code_hint: |
      # 获取数据（数据源由蓝图 data_layer 决定）
      prices = get_historical_prices(stock_pool, start_date, end_date)
      prices = prices.dropna(axis=1, thresh=len(prices)*0.8)  # 剔除缺失>20%的股票
    validation:
      - "价格矩阵非空"
      - "至少包含 momentum_window + 20 个交易日"
      - "无全 NaN 列"

  - id: "signal_generation"
    order: 2
    name: "因子计算与信号生成"
    description: "计算动量因子，截面排名，生成持仓信号"
    inputs:
      - name: "price_panel"
        from: "steps.data_preparation.outputs.price_panel"
    outputs:
      - name: "positions"
        schema: "DataFrame(index=DatetimeIndex, columns=stock_codes, values=0|1)"
    code_hint: |
      momentum = prices.pct_change(momentum_window)
      ranks = momentum.rank(axis=1, ascending=False)
      signals = (ranks <= top_n).astype(int)
      positions = signals.shift(1)  # T+1 延迟
    validation:
      - "每日持仓数 <= top_n"
      - "positions 已做 T+1 shift"
      - "无前瞻偏差"

  - id: "portfolio_backtest"
    order: 3
    name: "组合回测"
    description: "等权持仓，计算组合收益，扣除交易成本"
    inputs:
      - name: "price_panel"
        from: "steps.data_preparation.outputs.price_panel"
      - name: "positions"
        from: "steps.signal_generation.outputs.positions"
    outputs:
      - name: "equity_curve"
        schema: "Series(index=DatetimeIndex, values=portfolio_value)"
      - name: "trade_log"
        schema: "DataFrame(columns=[date, stock, action, shares, price, cost])"
    code_hint: |
      daily_returns = prices.pct_change()
      portfolio_returns = (positions * daily_returns).mean(axis=1)
      # 扣除调仓日交易成本
      turnover = positions.diff().abs().sum(axis=1)
      net_returns = portfolio_returns - turnover * commission_rate
      equity = (1 + net_returns).cumprod() * initial_capital
    validation:
      - "净值曲线起始值 = initial_capital"
      - "交易成本已扣除"

  - id: "performance_evaluation"
    order: 4
    name: "绩效评估"
    description: "计算核心绩效指标并输出"
    inputs:
      - name: "equity_curve"
        from: "steps.portfolio_backtest.outputs.equity_curve"
    outputs:
      - name: "metrics"
        schema: "{annual_return: float, max_drawdown: float, sharpe_ratio: float}"
    code_hint: |
      annual_return = (equity[-1] / equity[0]) ** (252 / len(equity)) - 1
      drawdown = (equity / equity.cummax() - 1)
      max_drawdown = drawdown.min()
      sharpe = net_returns.mean() / net_returns.std() * (252 ** 0.5)
    validation:
      - "三项指标均为有效数值（非 NaN）"
      - "收益率绝对值 > 0.1%（接近零说明 bug）"

# --- 已知变体 ---
variants:
  - name: "反转因子策略"
    description: "将 ascending=False 改为 ascending=True，做空高动量做多低动量"
    parameter_overrides:
      momentum_interpretation: "contrarian"

  - name: "多因子组合"
    description: "加入波动率因子、换手率因子等，加权合成综合得分"
    additional_steps:
      - "多因子标准化"
      - "因子加权"

# --- 生命周期 ---
lifecycle:
  status: "validated"                   # draft | validated | deprecated
  created_at: "2026-04-06"
  validated_by: "finance-bp-002-v9 实测"
  schema_version: "0.1"
```

### 1.3 Schema 设计决策说明

| 设计决策 | 理由 |
|---------|------|
| `steps` 用有序列表而非 DAG | Pattern 的步骤天然是线性流程，用 DAG 增加复杂度但收益有限。编译器按 order 顺序渲染即可 |
| `code_hint` 用伪代码而非精确代码 | Pattern 是跨框架的业务逻辑模板，精确代码依赖具体框架 API。伪代码让 LLM 理解意图后自行适配 |
| `parameters` 显式定义 range 和 sensitivity | LLM 需要知道参数的合理范围以避免生成荒谬值，sensitivity 帮助 LLM 在简化时知道哪些参数不可省略 |
| `stage_mapping` 连接 Pattern 步骤与蓝图阶段 | 编译器需要知道 Pattern 的每个步骤对应蓝图的哪个阶段，以便注入对应阶段的约束 |
| `variants` 描述常见变体 | 一个 Pattern 可以有多个变体，避免为每个小变化创建独立 Pattern，控制 Pattern 数量膨胀 |
| `validation` 在每个步骤中内联 | 验收标准与步骤紧密绑定，比单独抽出更容易被 LLM 在执行时即时检查 |

### 1.4 与现有 Schema 的兼容性分析

**与 Blueprint 的关系：**
- Pattern 通过 `applies_to.blueprint_ids` 挂载到蓝图，类似 Constraint 的 `applies_to`
- `stage_mapping` 是 Pattern 独有的，将业务步骤映射到框架阶段
- 一个 Blueprint 可以有多个 Pattern（1:N），一个 Pattern 也可以适用于多个 Blueprint（M:N）

**与 Constraint 的关系：**
- Pattern 的每个 step 通过 `stage_mapping` 间接关联到 Constraint
- 编译时，编译器根据 `stage_mapping` 为 Pattern 的每个步骤注入对应阶段的约束
- Pattern 的 `validation` 字段可以与 Constraint 的 `acceptance_hints` 互补

**ID 命名约定：**
- Blueprint: `{domain}-bp-{NNN}` (e.g., `finance-bp-002`)
- Constraint: `{domain}-C-{NNN}` (e.g., `finance-C-001`)
- **Pattern: `{domain}-P-{NNN}`** (e.g., `finance-P-001`)

---

## 2. 提取方法论

### 2.1 知识来源优先级

基于对 Doramagic 现有 59 个蓝图项目的分析，Pattern 知识来源按信息密度排序：

| 优先级 | 来源类型 | 信息密度 | 提取难度 | 示例 |
|--------|---------|---------|---------|------|
| P0 | `examples/` 目录 | 极高 | 低 | 完整可运行的策略文件 |
| P1 | `notebooks/` | 高 | 中 | Jupyter 教程，含数据+可视化 |
| P2 | `docs/tutorials/` | 中高 | 低 | 结构化教程，但可能缺代码 |
| P3 | README Quick Start | 中 | 低 | 最小可运行示例 |
| P4 | 源码内置组件 | 中 | 高 | 内置因子、模型、指标定义 |
| P5 | 测试 fixtures | 低 | 高 | 集成测试中的完整 workflow |

### 2.2 提取 SOP（Standard Operating Procedure）

#### Phase 1: 扫描与清点（自动化）

```
输入: GitHub 仓库 URL
输出: PatternCandidate 列表

步骤:
1. Clone 或 API 获取仓库结构
2. 扫描以下路径（按优先级）:
   - examples/**/*.py
   - notebooks/**/*.ipynb
   - docs/tutorials/**/*
   - README.md (Quick Start 段落)
   - tests/integration/**/*.py
3. 对每个文件生成 PatternCandidate:
   - file_path
   - file_type (script | notebook | markdown | test)
   - estimated_complexity (LOC, import count, function count)
   - title (从文件名/首行注释/notebook 标题提取)
4. 输出候选列表，按 estimated_complexity 排序
```

**工具选择**: 此阶段用规则驱动（AST 解析 + 正则），不需要 LLM。

#### Phase 2: 粒度判断与分割（LLM 辅助）

```
输入: PatternCandidate + 文件内容
输出: PatternUnit 列表（一个文件可能产出 0~N 个 PatternUnit）

步骤:
1. LLM 阅读文件内容，判断:
   a. 这是一个完整的业务流程吗？ → 1 个 PatternUnit
   b. 包含多个独立流程？ → 拆分为多个 PatternUnit
   c. 只是工具函数/配置？ → 0 个 PatternUnit（标记为 "component"，供其他 Pattern 引用）
2. 对每个 PatternUnit 提取:
   - 业务目标（一句话）
   - 步骤分解（3-8 步）
   - 参数识别（哪些值是硬编码的？哪些应该参数化？）
   - 输入/输出格式
```

**粒度判断准则**:
- **太细**: 单个因子计算（SMA）→ 这是 Component，不是 Pattern
- **太粗**: 完整量化研究平台 → 这是 Blueprint，不是 Pattern
- **适中**: "动量因子截面选股回测" → 一个有明确业务目标、可参数化、可独立执行的流程

#### Phase 3: 结构化提取（LLM 驱动）

```
输入: PatternUnit + 对应蓝图
输出: Pattern YAML（符合 Schema v0.1）

步骤:
1. 加载对应蓝图（从 PatternUnit 的 project 匹配）
2. LLM Prompt:
   """
   你是 Doramagic 知识提取器。请将以下代码示例提取为 Pattern YAML。

   ## 蓝图上下文
   {blueprint_yaml}

   ## 源代码
   {source_code}

   ## 要求
   - 按 Pattern Schema v0.1 输出 YAML
   - 每个 step 的 code_hint 用伪代码（不绑定具体框架 API）
   - 所有硬编码数值必须提取为 parameters
   - stage_mapping 必须映射到蓝图的 stage_ids
   - validation 至少覆盖每步的"可观测输出"
   """
3. 人工审核 YAML 输出
4. 自动验证:
   - schema 格式合规性
   - stage_mapping 中的 stage_id 在蓝图中存在
   - parameters 类型和 range 合理性
   - steps 的 inputs/outputs 引用链完整
```

#### Phase 4: 内置组件提取（源码分析）

这是独特的一步——从框架源码中提取可组合的 "Component"（因子、模型、指标），作为 Pattern 的构建原料。

```
输入: 框架源码 + 蓝图
输出: Component 清单（非独立 Pattern，而是 Pattern 引用的构建块）

步骤:
1. 扫描框架源码中继承自 base class 的所有实现:
   - zipline: Factor/Filter/Classifier 子类
   - qlib: Model 子类, Alpha 子类
   - freqtrade: IStrategy 子类

2. 对每个 Component 提取:
   - name, description
   - 输入参数和默认值
   - 输出格式
   - 使用约束（如 window_length 最小值）

3. 生成 components.yaml 附属文件:
   ```yaml
   components:
     - id: "zipline-factor-sma"
       name: "SimpleMovingAverage"
       type: "factor"
       parameters:
         - name: "window_length"
           type: "int"
           default: 20
       usage: "SimpleMovingAverage(inputs=[USEquityPricing.close], window_length=20)"
   ```
```

**工具选择**: AST 分析 + LLM 验证混合方案。AST 提取类继承树和参数签名，LLM 补充语义描述。

### 2.3 提取量估算

| 项目类型 | 项目数 | 平均 examples | 平均 notebooks | 预估 Pattern/项目 | 总量 |
|---------|--------|--------------|---------------|-----------------|------|
| 回测框架 | 8 | 5-15 | 3-10 | 8-15 | 64-120 |
| 数据分析库 | 12 | 3-8 | 5-20 | 5-10 | 60-120 |
| ML 平台 | 6 | 10-30 | 5-15 | 10-20 | 60-120 |
| 可视化/工具 | 33 | 2-5 | 1-3 | 2-5 | 66-165 |
| **合计** | **59** | - | - | - | **250-525** |

保守估计 59 个项目可提取 300+ 个 Pattern。

---

## 3. 编译器集成方案

### 3.1 编译流程变更

当前 v4 编译流程：
```
Blueprint + Constraints + user_intent → Crystal
```

新增 Pattern 后：
```
Blueprint + Pattern(s) + Constraints + user_intent → Crystal
```

### 3.2 数据模型变更

在 `retrieve.py` 的 `CollectionResult` 中新增 Pattern 字段：

```python
# retrieve.py 新增

@dataclass
class PatternStep:
    """Pattern 中的一个执行步骤。"""
    id: str
    order: int
    name: str
    description: str
    inputs: list[dict]
    outputs: list[dict]
    code_hint: str
    validation: list[str]
    mapped_stage_id: str  # 对应蓝图的 stage_id


@dataclass
class LoadedPattern:
    """加载后的 Pattern。"""
    id: str
    name: str
    objective: dict
    parameters: list[dict]
    steps: list[PatternStep]
    stage_mapping: dict[str, str]
    variants: list[dict]
    raw: dict


@dataclass
class CollectionResult:
    # ... 现有字段 ...
    
    # 新增
    patterns: list[LoadedPattern] = field(default_factory=list)
```

### 3.3 `_render_directive()` 改动方案

这是核心改动。当前 `_render_directive()` 生成的是通用的 6 步执行指令。有了 Pattern 后，directive 需要变成**业务驱动**的。

**改动前（compiler.py:96-158）：通用指令**
```python
def _render_directive(lines, bp, user_intent):
    lines.append("**你收到的是一份执行任务。立即按以下流程执行：**")
    lines.append("1. 查阅用户记忆...")
    lines.append("2. 确认环境...")
    lines.append("3. 理解架构...")
    lines.append("4. 构建系统...")
    lines.append("5. 引导使用...")
    lines.append("6. 交付结果...")
```

**改动后：Pattern 驱动的具体指令**
```python
def _render_directive(
    lines: list[str],
    bp: ParsedBlueprint,
    user_intent: str,
    patterns: list[LoadedPattern] | None = None,
) -> None:
    """执行指令：通用流程 + Pattern 具体步骤。"""
    lines.append("## directive")
    lines.append("")
    lines.append("**你收到的是一份执行任务。立即按以下流程执行：**")
    lines.append("")

    # 通用前置步骤（保留）
    lines.append("1. **查阅用户记忆**：...")
    lines.append("2. **确认环境**：...")
    lines.append("")

    # === Pattern 驱动的业务步骤（新增） ===
    if patterns:
        pattern = patterns[0]  # v0.1 先支持单 Pattern
        
        # 业务目标
        lines.append("### 业务目标")
        lines.append(f"- {pattern.objective.get('goal', '')}")
        lines.append(f"- 输入：{pattern.objective.get('input_description', '')}")
        lines.append(f"- 输出：{pattern.objective.get('output_description', '')}")
        lines.append("")

        # 参数配置（可被 user_intent 覆盖）
        lines.append("### 参数配置")
        lines.append("")
        lines.append("| 参数 | 默认值 | 说明 | 可调范围 |")
        lines.append("|------|--------|------|----------|")
        for p in pattern.parameters:
            default = p.get("default", "需用户指定")
            range_str = str(p.get("range", "-"))
            lines.append(
                f"| {p['name']} | {default} | "
                f"{p['description']} | {range_str} |"
            )
        lines.append("")

        # 具体执行步骤
        lines.append("### 执行步骤")
        lines.append("")
        for step in pattern.steps:
            stage_id = step.mapped_stage_id
            lines.append(
                f"**步骤 {step.order}：{step.name}** "
                f"（对应架构阶段：{stage_id}）"
            )
            lines.append(f"- {step.description}")
            lines.append("")

            # 输入
            if step.inputs:
                lines.append("输入：")
                for inp in step.inputs:
                    lines.append(f"  - `{inp['name']}`：{inp.get('from', '')}")
                lines.append("")

            # 伪代码提示
            if step.code_hint:
                lines.append("参考实现：")
                lines.append("```python")
                lines.append(step.code_hint.rstrip())
                lines.append("```")
                lines.append("")

            # 步骤级验收
            if step.validation:
                lines.append("验证：")
                for v in step.validation:
                    lines.append(f"  - [ ] {v}")
                lines.append("")

        # 变体提示
        if pattern.variants:
            lines.append("### 可选变体")
            for v in pattern.variants:
                lines.append(f"- **{v['name']}**：{v['description']}")
            lines.append("")

    else:
        # 无 Pattern 时，回退到通用流程
        lines.append("3. **理解架构**：通读下方 `架构蓝图` 段...")
        lines.append("4. **构建系统**：按蓝图架构逐阶段构建...")
        lines.append("5. **引导使用**：构建完成后立即引导用户...")
        lines.append("6. **交付结果**：帮助用户完成首次实际运行...")
        lines.append("")

    # 用户意图（保留）
    lines.append("### 用户意图")
    lines.append(f"- {user_intent}")
    lines.append("")

    # 其余保持不变...
```

### 3.4 `compile_crystal_v4()` 签名变更

```python
def compile_crystal_v5(
    blueprint: ParsedBlueprint,
    collection: CollectionResult,
    user_intent: str,
    patterns: list[LoadedPattern] | None = None,  # 新增
    max_tokens: int | None = None,
) -> str:
    """将蓝图+Pattern+约束编译为 v5 种子晶体。"""
    lines: list[str] = []

    _render_header(lines, blueprint, collection, user_intent)
    _render_directive(lines, blueprint, user_intent, patterns)  # 传入 Pattern
    _render_fatal_constraints(lines, collection.embed)
    _render_blueprint(lines, blueprint)
    _render_resources(lines, blueprint, collection)
    _render_constraints(lines, blueprint, collection)
    _render_acceptance(lines, collection, patterns)  # Pattern 验收条件合入
    _render_footer(lines, blueprint, collection)

    crystal = "\n".join(lines)
    if max_tokens:
        max_chars = max_tokens * 4
        if len(crystal) > max_chars:
            crystal = crystal[:max_chars]
    return crystal
```

### 3.5 便捷接口扩展

```python
def compile_from_paths(
    blueprint_path: Path,
    constraints_dir: Path,
    user_intent: str,
    pattern_paths: list[Path] | None = None,  # 新增
    max_tokens: int | None = None,
) -> str:
    blueprint = load_blueprint(blueprint_path)
    store = ConstraintStore(constraints_dir)
    collection = collect_constraints(store, blueprint)
    
    patterns = None
    if pattern_paths:
        patterns = [load_pattern(p) for p in pattern_paths]
    
    return compile_crystal_v5(
        blueprint, collection, user_intent, patterns, max_tokens
    )
```

### 3.6 渲染后晶体结构对比

**v4（无 Pattern）：**
```markdown
# 种子晶体：事件驱动回测系统
## directive
  通用 6 步流程
  用户意图
## [FATAL] 约束
## 架构蓝图
## 资源
## 约束
## 验收
```

**v5（有 Pattern）：**
```markdown
# 种子晶体：A股动量因子截面选股回测
## directive
  环境确认（通用）
  业务目标（Pattern）         ← 新增
  参数配置（Pattern）         ← 新增
  具体执行步骤（Pattern）     ← 新增：带伪代码、输入输出、验证点
  可选变体（Pattern）         ← 新增
  用户意图
## [FATAL] 约束
## 架构蓝图                   ← 不变
## 资源                       ← 不变
## 约束                       ← 不变，但每步骤通过 stage_mapping 关联
## 验收                       ← 合入 Pattern 步骤级验收条件
```

---

## 4. 先验知识与替代方案分析

### 4.1 相关系统对比

| 系统 | 定位 | 知识表示 | 与 Doramagic 的差异 |
|------|------|---------|-------------------|
| **GitHub Copilot Workspace** | 代码生成 | 自然语言 → 代码计划 | 无结构化知识层，每次从头推理 |
| **LangChain Templates** | LLM 应用模板 | Python cookiecutter | 模板是可运行代码，不是知识描述 |
| **Prefect/Dagster Recipes** | 数据工程 workflow | Python 代码 + YAML config | 面向人类开发者，不面向 LLM |
| **MLflow Recipes** | ML 工作流模板 | YAML + Jinja2 | 最接近，但无约束层，无编译步骤 |
| **Software Design Patterns (GoF)** | 面向对象设计 | 自然语言描述 | 架构级，非业务逻辑级 |
| **QuantConnect Lean / Algorithm Examples** | 量化策略模板 | C#/Python 代码 | 完整代码，非参数化模板 |

### 4.2 RAG + Code Examples 的研究进展

当前 RAG 用于代码生成的主流方法：

1. **Retrieval-Augmented Code Generation (RACG)**：检索相似代码片段作为 LLM 上下文。问题：代码片段缺乏业务语义，LLM 容易"照抄"而非"理解"。

2. **DocPrompting (Zhou et al., 2023)**：用文档而非代码作为检索源。与 Pattern 理念接近——用结构化描述指导生成。

3. **Repository-Level Code Generation**：理解整个仓库结构后生成代码。计算成本高，且不解决"做什么"的问题。

**Doramagic 的差异化**：Pattern 不是代码片段（RAG 通常检索的），也不是文档（DocPrompting 使用的），而是**参数化的业务流程模板 + 框架绑定**。这在已知文献中没有直接对应物。

### 4.3 替代架构方案

**方案 A：Pattern 作为独立 YAML（推荐，本报告方案）**
- 优点：与现有 Blueprint/Constraint 对齐，编译器改动小，可独立迭代
- 缺点：新增一种知识类型，维护成本增加

**方案 B：Pattern 嵌入 Blueprint**
- 做法：在 Blueprint YAML 中新增 `patterns:` 段落
- 优点：减少文件数量，蓝图自包含
- 缺点：Blueprint 已经很大（finance-bp-002 有 600 行），再加 Pattern 会膨胀；且一个 Pattern 可能跨多个 Blueprint

**方案 C：Pattern 作为 Constraint 的特殊类型**
- 做法：新增 `ConstraintKind.BUSINESS_PATTERN`
- 优点：复用现有 Constraint 基础设施
- 缺点：Constraint 的三元组结构（when/modality/action）不适合描述多步骤流程

**方案 D：RAG 替代 Pattern**
- 做法：不做结构化提取，运行时从原始 examples/notebooks 检索相关片段
- 优点：零提取成本
- 缺点：检索质量不稳定，无参数化，无约束关联，晶体质量不可控

**结论**：方案 A 最优。Pattern 是与 Blueprint/Constraint 正交的知识类型，需要独立 schema 和独立文件。

---

## 5. 实施计划

### Phase 0: 验证性原型（1 周）

**目标**：用手动创建的 1 个 Pattern，验证编译器集成可行性。

| 任务 | 优先级 | 工作量 |
|------|--------|--------|
| 手写 `finance-P-001.yaml`（动量因子选股，基于 v9 晶体逆向） | P0 | 2h |
| 实现 `pattern_loader.py`（YAML → LoadedPattern） | P0 | 4h |
| 修改 `compiler.py` 的 `_render_directive()` | P0 | 4h |
| 编译 v5 晶体并对比 v9 效果 | P0 | 4h |
| 在 OpenClaw 实测 v5 晶体 | P0 | 2h |

**成功标准**：v5 晶体（自动编译）在实测中不劣于 v9（手写 directive）。

### Phase 1: Schema 定稿 + 首批提取（2 周）

| 任务 | 优先级 | 工作量 |
|------|--------|--------|
| 基于 Phase 0 反馈修正 Schema | P0 | 1d |
| 编写 Pattern Schema 验证器（Pydantic 模型） | P0 | 2d |
| 从 Top 5 项目各提取 3-5 个 Pattern | P1 | 5d |
| 编写提取 SOP 文档 | P1 | 1d |
| 扩展 `compile_from_paths` CLI | P2 | 1d |

**Top 5 优先提取项目：**
1. `zipline-reloaded`（finance-bp-002）— 有丰富 examples + Pipeline 教程
2. `qlib`（finance-bp-004）— 有 30+ 内置模型 + examples
3. `freqtrade`（finance-bp-001）— 有策略模板 + 完整文档
4. `backtrader`（finance-bp-0XX）— 经典回测框架，大量社区示例
5. `pyportfolioopt`（finance-bp-0XX）— 组合优化，独立域

### Phase 2: 半自动提取管线（2 周）

| 任务 | 优先级 | 工作量 |
|------|--------|--------|
| 实现 Phase 1 扫描器（examples/notebooks 自动发现） | P0 | 3d |
| 实现 Phase 2 粒度判断器（LLM prompt） | P1 | 2d |
| 实现 Phase 3 结构化提取器（LLM prompt + schema 验证） | P1 | 3d |
| 实现 Phase 4 内置组件扫描器（AST 分析） | P2 | 2d |

### Phase 3: 规模化提取（持续）

覆盖全部 59 个蓝图项目，目标 300+ Pattern。按季度迭代。

---

## 6. 风险与开放问题

### 6.1 高风险

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| **Pattern 粒度失控** | 太细则数量爆炸（1000+），太粗则不够具体 | Phase 0 用 3 个实际案例标定粒度，确立判断准则后再批量提取 |
| **code_hint 质量不稳定** | LLM 可能将伪代码当精确代码执行，或反之忽略 | 设置 `hint_type: pseudocode | executable` 标志，编译时加注释说明 |
| **Pattern 与 Constraint 冲突** | Pattern 建议做 X，Constraint 禁止做 X | 编译时做冲突检测：Pattern.steps 的 stage_mapping → 对应阶段约束 → 文本相似度检查 |

### 6.2 中风险

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| **跨蓝图 Pattern 适配** | "动量策略"在 zipline 和 freqtrade 中 API 完全不同 | v0.1 先做蓝图特定 Pattern，v0.2 再抽象跨蓝图 Pattern |
| **晶体 token 膨胀** | 加 Pattern 后晶体 token 数可能翻倍 | 编译器设 max_tokens 裁剪，优先保留 FATAL 约束 + Pattern 核心步骤 |
| **提取成本** | 59 项目 × 平均 8 Pattern = 472 次 LLM 调用 | 用 Sonnet 做批量提取，Opus 做质量审核 |

### 6.3 开放问题

1. **Pattern 版本管理**：当上游项目更新 API，Pattern 是否需要同步更新？更新触发条件是什么？
   - 建议：绑定 Blueprint 版本，Blueprint 更新时触发 Pattern 复查

2. **用户自定义 Pattern**：是否允许用户上传自己的 Pattern（如朋友写的高换手率晶体）？格式如何兼容？
   - 建议：支持。用户晶体可通过逆向解析转为 Pattern YAML

3. **Pattern 组合**：一个晶体能否同时使用多个 Pattern？（如 "动量选股" + "风险平价配权"）
   - 建议：v0.1 限制单 Pattern，v0.2 支持多 Pattern 组合（需解决步骤合并问题）

4. **Component vs. Pattern 边界**：单个因子（SMA）是 Component 还是 Pattern？
   - 建议：Component 是不可独立执行的构建块，Pattern 是有明确业务目标的可执行流程。SMA 是 Component，"SMA 金叉策略"是 Pattern

5. **多语言输出**：Pattern 的 name/description 是否需要多语言？
   - 建议：与 Blueprint 保持一致。当前中文优先，未来按 `project_doramagic_language_support.md` 的决策执行

---

## 7. 从实际案例验证 Schema 覆盖度

### 7.1 验证案例 1：v9 晶体的 directive（手写业务逻辑）

v9 晶体 `finance-bp-002-v9.seed.md` 中手写的 directive 包含：

| v9 手写内容 | Pattern Schema 对应字段 | 覆盖？ |
|------------|----------------------|--------|
| "20日动量因子截面选股" | `objective.goal` | ✅ |
| STOCK_POOL = 20只固定股票 | `parameters[stock_pool]` | ✅ |
| TOP_N = 5 | `parameters[top_n]` | ✅ |
| MOMENTUM_WINDOW = 20 | `parameters[momentum_window]` | ✅ |
| baostock API 具体调用语法 | `steps[0].code_hint` | ✅ |
| T+1 延迟 shift(1) | `steps[1].code_hint` + Constraint | ✅ |
| 输出格式 ANNUAL_RETURN=xx% | `objective.success_criteria` | ✅ |
| "禁止用 zipline import" | Constraint（非 Pattern） | N/A |
| "单文件原子执行" | 执行模式约束（非 Pattern） | N/A |

**结论**：v9 手写 directive 中的**业务逻辑部分**完全可被 Pattern Schema 覆盖。执行模式约束（单文件、工具白名单等）属于 Constraint 层，不在 Pattern 范围内，这是正确的分层。

### 7.2 验证案例 2：朋友的高换手率晶体

`high-turnover-event-study.seed.md` 中的业务逻辑：

| 晶体内容 | Pattern Schema 对应 | 覆盖？ |
|---------|-------------------|--------|
| 4 个阶段（筛选→提取→统计→建议） | `steps` (4 steps) | ✅ |
| turnover_threshold=30, top_n_per_day=10 | `parameters` | ✅ |
| CONFIG 字典中的所有参数 | `parameters` with range/default | ✅ |
| 每阶段的代码框架 | `steps[].code_hint` | ✅ |
| 核心分析指标定义 | `steps[].outputs.schema` | ✅ |
| 必须产出的 4 个文件 | `objective.output_description` + `success_criteria` | ✅ |
| 细分区间统计（30-40%, 40-50%, >50%） | `parameters[turnover_brackets]` | ✅ |

**结论**：完全覆盖。高换手率晶体的业务逻辑可以无损转换为 Pattern YAML。

### 7.3 验证案例 3：Blueprint 中已有的暗示性 Pattern

`finance-bp-002.yaml`（zipline）中的 `pseudocode_example` 和 `replaceable_points` 实际上包含了 Pattern 的碎片：

- `user_strategy` 阶段的伪代码 = 一个简单均线策略 Pattern 的雏形
- `pipeline_api` 阶段的伪代码 = 一个 Pipeline 选股 Pattern 的雏形
- `replaceable_points` 中的选项 = Pattern 参数的可选值

这证实了 Pattern 知识确实分散在 Blueprint 中，但没有被独立、完整、参数化地提取。

---

## 8. 总结

Pattern 是 Doramagic 知识体系的关键缺失层。本报告提出的方案核心思路：

1. **Schema**：独立的 Pattern YAML（v0.1），与 Blueprint/Constraint 正交但可组合
2. **提取**：4 阶段 SOP（扫描 → 粒度判断 → 结构化提取 → 组件提取），LLM 辅助 + 规则驱动混合
3. **编译**：修改 `_render_directive()` 使之 Pattern 驱动，从"通用指令"变为"具体业务流程"
4. **验证**：从 Phase 0（1 个手写 Pattern + v5 编译器 + 实测）开始，逐步扩展

**最核心的判断**：Pattern 解决的不是"信息量不够"的问题（Blueprint 已经很详细），而是"信息类型不对"的问题。Blueprint 告诉 LLM "框架能做什么"，但 LLM 需要的是 "用这个框架来做什么具体的事"。这两者之间的鸿沟就是 Pattern 要填补的。

---

*Claude Opus 4.6 | 2026-04-06 | Doramagic Pattern Extraction Research*
