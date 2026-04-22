# 约束采集方案 — 三方研究提示词

> 请将此提示词分别发送给 Claude / GPT / Gemini，收集独立方案后综合。

---

## 背景

你是 Doramagic 项目的架构顾问。Doramagic 是一个 **AI 知识锻造系统**——从开源项目中系统性提炼专家知识，编译成"种子晶体"（一个 markdown 配方文件），用户把晶体丢给自己的 AI，AI 按配方构建个性化工具。

核心知识架构是 **Blueprint + Constraint 两层模型**：
- **Blueprint（蓝图）**：某个任务的一种解法的架构结构图——阶段(stages)、数据流(edges)、接口契约、可替换点。类比"户型图"。
- **Constraint（约束）**：挂在蓝图上的规则和限制——"按这张户型图装修时，哪些坑不能踩、哪些边界不能越"。

蓝图已经提取完毕（3 份 finance 领域蓝图，来自 freqtrade/zipline/vnpy 三个开源项目）。
**现在的任务是：设计约束采集方案——如何从这三个项目的源码和文档中，系统性地提取约束。**

---

## 约束的定义（Schema v0.2）

一条约束的核心是 **三元组**：

```
当 [条件] 时，必须/禁止 [行为]，否则 [后果]
```

### 完整字段

```yaml
Constraint:
  id: string                        # 格式：{domain}-C-{number}
  hash: string                      # sha256(core + scope)[:16]

  # 核心三元组
  core:
    when: string                    # 触发条件（≥5字符）
    modality: enum                  # must / must_not / should / should_not
    action: string                  # 要求的行为（≥5字符）
    consequence:
      kind: enum                    # bug / performance / financial_loss / data_corruption /
                                    # service_disruption / operational_failure / compliance /
                                    # safety / false_claim
      description: string           # 违反后果描述（≥10字符）

  # 约束性质（5 种）
  constraint_kind: enum
    # domain_rule:            领域客观规律（如"金融计算必须用 Decimal"）
    # resource_boundary:      工具能力边界（如"yfinance 延迟 15 分钟"）
    # operational_lesson:     运维/社区经验（如"dry-run ≥72 小时"）
    # architecture_guardrail: 架构护栏（如"风控必须在执行之后"）
    # claim_boundary:         能力声明边界（如"不能宣称回测=实盘"）

  # 附着点——约束挂在蓝图的哪个位置
  applies_to:
    target_scope: enum              # global / stage / edge
    stage_ids: list[string]         # 挂哪些阶段（target_scope=stage 时必填）
    edge_ids: list[string]          # 挂哪些数据流边（target_scope=edge 时必填）
    blueprint_ids: list[string] | null  # 关联蓝图（null = 通用约束）

  # 适用范围
  scope:
    level: enum                     # universal / domain / context
    domains: list[string]
    context_requires:               # 可选
      resources: list[string]
      task_types: list[string]
      tech_stack: list[string]

  # 可信度
  confidence:
    source_type: enum               # code_analysis / community_issue / official_doc /
                                    # api_changelog / cross_project / expert_reasoning
    score: float                    # 0.0-1.0
    consensus: enum                 # universal / strong / mixed / contested
    verified_by: list[string]
    evidence_refs: list[EvidenceRef]

  # 编译提示
  machine_checkable: bool           # 是否可自动化验证
  promote_to_acceptance: bool       # 是否提升为验收标准

  # 严重度与新鲜度
  severity: enum                    # fatal / high / medium / low
  freshness: enum                   # stable / semi_stable / volatile

  relations: list[Relation]
  version:
    status: enum                    # draft / active / deprecated
    schema_version: "2.0"
  examples:
    positive: list[string]
    negative: list[string]
  notes: string | null
  tags: list[string]
```

### 约束收集规则（编译种子晶体时使用）

```
编译某蓝图的种子晶体时，收集关联约束：
1. blueprint_ids 包含当前蓝图 ID
2. blueprint_ids = null 且 stage_ids 在蓝图 stages 中存在
3. blueprint_ids = null 且 target_scope = "global" 且 domains 匹配
```

### 验收标准派生规则

```
约束进入种子晶体"验收标准"段的条件（满足任一）：
1. promote_to_acceptance = true（最高优先级）
2. severity = fatal
3. machine_checkable = true 且 severity >= high
4. consequence.kind in {false_claim, financial_loss, data_corruption, compliance, safety}
5. target_scope = "edge"（跨阶段约束天然是验收项）
```

---

## 已有的 3 份蓝图概要

### finance-bp-001: 向量化量化回测系统（来自 freqtrade）

```
execution_paradigm: backtest=batch_pipeline, dry_run/live=polling_event_loop
stages:
  [1] data_pipeline:        获取/缓存/校验 OHLCV 数据，统一数据访问接口
  [2] strategy_engine:      用户策略逻辑（继承 IStrategy，实现 populate_indicators）
  [3] trade_loop:           信号执行 + 内嵌风控（shift(1) 延迟，open 价成交）
  [4] evaluation_reporting: 交易记录 → 绩效指标 → 报告
edges:
  pairlist_to_data:    PairListManager → data_pipeline
  data_to_strategy:    data_pipeline → strategy_engine
  strategy_to_trade:   strategy_engine → trade_loop
  trade_to_eval:       trade_loop → evaluation_reporting
global_contracts: 7 项（如：DataProvider 是唯一数据入口、双层缓存架构等）
```

### finance-bp-002: 事件驱动回测系统（来自 zipline）

```
execution_paradigm: backtest=event_driven_bar_by_bar
stages:
  [1] data_layer:       Bundles 数据摄入 + DataPortal 统一访问 + 自动公司行为处理
  [2] user_strategy:    四个生命周期函数（initialize/handle_data/before_trading_start/analyze）
  [3] event_loop:       时钟产出事件流，先撮合旧订单再调策略，保证 T+1
  [2] pipeline_api:     声明式跨截面因子计算（Factor/Filter/Classifier → 依赖图 → 批量计算）
  [4] evaluation:       MetricsTracker 每 bar 聚合指标，产出 daily_stats DataFrame
edges:
  bundle_to_portal:    data_layer → DataPortal（内部）
  portal_to_bardata:   data_layer → user_strategy
  strategy_to_orders:  user_strategy → event_loop
  pipeline_to_strategy: pipeline_api → user_strategy
  loop_to_eval:        event_loop → evaluation
global_contracts: 6 项（如：纯回测框架无实盘能力、事件驱动非向量化等）
```

### finance-bp-003: 插件化事件驱动交易框架（来自 vnpy）

```
execution_paradigm: live=event_driven_queue, backtest=bar_by_bar_simulation
stages:
  [1] event_engine:     系统通信骨架，单线程 Queue + handler 分发
  [1] data_models:      @dataclass 标准化数据结构（TickData/BarData/OrderData/TradeData/PositionData）
  [2] gateway_layer:    BaseGateway 7 个 @abstractmethod，实际网关是外部 pip 包
  [3] strategy_engine:  策略模板 3 个 @abstractmethod，买卖接口区分开平仓（中国市场特性）
  [4] backtest_engine:  逐 K 线回测，cross_order() → on_bars() 顺序保证一 bar 延迟，内置涨跌停检测
edges:
  gateway_to_event:    gateway_layer → event_engine
  event_to_strategy:   event_engine → strategy_engine
  strategy_to_gateway: strategy_engine → gateway_layer
  data_to_backtest:    data_models → backtest_engine
global_contracts: 6 项（如：所有模块通过事件引擎通信、网关/策略/数据库动态加载等）
```

---

## 种子晶体示例（约束在晶体中的最终呈现形态）

以下是一颗已有的种子晶体中"硬约束"段的样子（来自 multi-agent-orchestration 领域，非 finance）：

```markdown
## 二、硬约束（违反必出 bug）

| # | 约束 | 原因 | 违反后果 |
|---|------|------|---------|
| C1 | 完成状态必须在清理操作之前设置 | classifyHandoff 和 worktree cleanup 可能 hang | 下游等待者永远阻塞 |
| C2 | 异步 Agent 必须用独立的 AbortController | 共享父级 controller 取消一个连带取消所有 | 任务相互干扰 |
| C3 | 工具过滤用白名单 ∩ ¬黑名单，MCP 工具始终放行 | 纯黑名单无法防御未知工具 | 安全漏洞或功能损失 |
...

## 三、验收标准

1. **可观测性**：看文件邮箱就知道每个 Agent 发了什么、收了什么
2. **优雅降级**：iTerm2 → Tmux → 进程内，每级降级用户无感知
3. **取消安全**：取消一个 Agent 不影响其他 Agent，资源完全释放
...
```

约束在种子晶体中被**压缩成人话表格**——但背后每条都是一个完整的 Constraint JSONL 记录，有精确的 applies_to、severity、evidence_refs 等元数据。

---

## 我们已达成的共识

1. **采集路径**：蓝图驱动（以蓝图为锚，逐阶段/逐边定向采集约束），不是盲采后再挂蓝图
2. **采集范围**：3 个项目（freqtrade / zipline / vnpy）
3. **蓝图不动**：已定稿，约束采集时只读
4. **约束独立于蓝图**：约束是独立知识单元，可跨蓝图适用
5. **绑定关系**：
   - `blueprint_ids = ["finance-bp-001"]` → 仅适用于特定蓝图
   - `blueprint_ids = ["finance-bp-001", "finance-bp-002", "finance-bp-003"]` → 多蓝图共享
   - `blueprint_ids = null` → 领域通用
6. **跨项目去重**：core triple 实质相同 → 合并为一条（多证据源，confidence 提升）；有实质差异 → 各自独立
7. **粒度原则**：尽可能充分，充分的知识才能更好地服务种子晶体
8. **质量策略**：单模型提取 + 自动化校验 + 人工抽检（约束可迭代修正，不需要四方评审）

---

## 你需要回答的问题

请系统性地思考并给出**约束采集的完整方案**，包括但不限于：

### 1. 约束的价值本质

约束在整个知识体系中的核心价值是什么？它为种子晶体提供了什么不可替代的东西？不要笼统地回答"提供规则"——请深入思考：如果没有约束，只有蓝图，会发生什么？约束的存在解决了什么根本问题？

### 2. 约束的来源分类

从开源项目中，约束可以从哪些具体来源提取？每种来源能产出哪些 constraint_kind？请给出系统性的来源 → 约束类型映射。

### 3. 蓝图驱动采集的具体流程

以 finance-bp-001（freqtrade）为例，描述从"拿到蓝图 YAML + 项目源码"到"产出一组 Constraint JSONL"的完整步骤。特别是：
- 每个 stage 怎么定向搜索约束？搜索策略是什么？
- 怎么处理 edge（跨阶段）约束？
- 怎么处理 global 约束？
- applies_to 怎么判断？

### 4. 约束粒度问题

"尽可能充分"的原则下，怎么把控粒度？什么算一条约束？什么应该拆成两条？什么应该合并？请给出判断标准和例子。

### 5. 跨项目约束处理

三个项目可能产出同一条约束的不同表述。请设计具体的去重和合并策略，包括：
- 怎么判断两条约束是"同一条"？
- 合并时 evidence_refs、confidence、blueprint_ids 怎么处理？
- 如果 core triple 相似但有阈值/细节差异（如 dry-run 72h vs 3 天），怎么决策？

### 6. LLM 提取 prompt 设计思路

约束采集的核心质量取决于提取 prompt。请给出 prompt 的设计思路（不需要完整 prompt，给出结构和关键要素即可）：
- 输入应该包含什么？
- 怎么确保 5 种 constraint_kind 都被覆盖？
- 怎么确保充分性（不遗漏）？
- 怎么控制幻觉（不编造）？

### 7. 管线实现架构

给出管线的技术实现架构建议：
- 哪些是新组件？哪些可以复用？
- 数据流怎么走？
- 自动化程度怎么把控？

### 8. 你认为我们遗漏了什么？

基于你的理解，我们的方案有没有盲点？有没有重要的设计决策我们还没有讨论？请直言。

---

## 输出格式要求

- 请用中文回答
- 每个问题独立成段，有明确结论
- 如果你对某个问题有多种方案，列出各方案的利弊，给出你的推荐
- 如果你认为某个共识需要修正，直接指出并说明理由
