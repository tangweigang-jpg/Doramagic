# Doramagic 产品诊断报告（基于 run-20260329-095600）
日期: 2026-03-29  
诊断对象: `~/.doramagic/runs/run-20260329-095600`  
诊断依据: `README.md`（Deterministic DAG / 4-Tier Degraded Delivery / Structured Logging）、`docs/rules/02-doramagic-product-rules-v1.md`（P0-P10）

## 一、执行快照

- 输入场景：用户提出“50 岁旅居清迈、参加英语班、英语基础弱，希望有学习工具”的需求。
- 路由结果：`DOMAIN_EXPLORE`
- 运行结果：`DEGRADED`（约 4 秒完成）
- 关键状态：
  - `NeedProfileBuilder=ok`
  - `DiscoveryRunner=blocked`（run_log）
  - 事件层显示 `DiscoveryRunner degraded`（run_events）
  - `delivery_tier=candidate_brief`
  - `delivery/` 目录为空

## 二、与产品设计的偏差诊断

### D1（高优先级）降级交付承诺未兑现：`delivery_tier` 存在但无交付文件

- 设计期望：
  - README 明确“4-Tier Degraded Delivery -- Users always receive output”
  - 产品规则 P1 要求“任意阶段失败时必须进入分级交付，禁止空白失败”
- 运行事实：
  - `controller_state.json` 显示 `delivery_tier=candidate_brief`
  - `~/.doramagic/runs/run-20260329-095600/delivery/` 为空
- 诊断：
  - 当前控制流在 `PHASE_B -> DEGRADED` 时直接结束运行，未进入 DeliveryPackager 的最小打包分支。
- 影响：
  - 用户看到“已降级”但拿不到任何可消费产物，破坏 Doramagic 的核心产品承诺。

### D2（高优先级）Discovery 状态语义分裂：实现为 `blocked`，设计主张 `degraded`

- 设计期望：
  - `packages/cross_project/DECISIONS_S1.md` D8 指明“0 候选 -> degraded + no_candidate_reason”
  - P1/P6 希望降级链路可继续交付并可观测。
- 运行事实：
  - `run_log.jsonl`: `DiscoveryRunner status=blocked`
  - `run_events.jsonl`: 事件层记录为 `degraded`
- 诊断：
  - 执行器语义与流程语义不一致，导致状态判读困难，增加线上排障复杂度。
- 影响：
  - 下游无法稳定基于统一状态进行自动恢复、告警分级和统计报表。

### D3（高优先级）可观测性字段缺失：`run_events.jsonl` 的 `run_id` 为空字符串

- 设计期望：
  - P6 强调结构化事件可追踪。
- 运行事实：
  - 每条事件 `run_id` 均为空，真实 run id 仅出现在 `meta.run_id` 首条事件中。
- 诊断：
  - `EventBus(run_dir)` 初始化时未传 `run_id`，导致事件主键字段不可用。
- 影响：
  - 多 run 并发或汇总分析时，事件流关联成本显著上升，易产生误归因。

### D4（中优先级）需求解析和检索词质量不足，导致 DOMAIN_EXPLORE 误命中

- 运行事实：
  - `NeedProfile` 的 `github_queries` 为“我是一个 / 岁左右的老人 / 我接下来在清迈旅居”等自然语言片段。
  - Discovery 命中后被 relevance gate 过滤到 0 候选。
- 诊断：
  - 需求抽取未形成“可检索、可对齐开源语料”的领域词（如 `english learning app`, `vocabulary trainer`, `senior language learning`）。
- 影响：
  - 用户真实意图与 GitHub 语义空间错位，DOMAIN_EXPLORE 路径成功率下降。

## 三、根因分析（实现层）

1. 控制器降级路径短路交付  
   在 `FlowController` 中，`next_phase == DEGRADED` 时直接 `_enter_degraded(...)` 并终止主循环，未强制进入 `PHASE_G` 打包。

2. DiscoveryRunner 状态返回不符合当前设计文档  
   `packages/executors/doramagic_executors/discovery_runner.py` 中 0 候选分支返回 `status="blocked"`，与 D8 文档目标不一致。

3. EventBus 初始化参数不完整  
   `FlowController.__init__` 使用 `EventBus(run_dir)`，未绑定 run id。

4. 需求词提取策略偏“字面切片”，缺少“检索词重写”  
   当前关键词提取对中文长句场景鲁棒性不足，无法稳定映射到开源项目语义标签。

## 四、修复建议（按优先级）

### P0（立即修复，24h）

1. 降级也要走“最小交付打包”
- 目标：任何 `DEGRADED` 至少落地 `delivery_manifest.json` + 对应 tier 产物（哪怕为空候选快照）。
- 验收：`delivery/` 非空，且含可解释文件与路径。

2. 修复 `run_events.jsonl` 的 `run_id`
- 目标：每条事件具备一致 `run_id`。
- 验收：抽查 3 个 run，`run_events.jsonl` 全量行 `run_id` 非空且与目录名一致。

### P1（短期修复，3-7 天）

3. 统一 Discovery 0 候选状态为 `degraded`
- 目标：执行器、事件、控制器三层语义一致。
- 验收：0 候选 run 中 `run_log` 与 `run_events` 一致标记为 `degraded`，并持续触发分级交付。

4. DOMAIN_EXPLORE 增加“检索词重写器”
- 目标：将用户自然语言需求稳定映射到 GitHub 可检索语义词。
- 验收：对“中文生活化需求”样本集，`candidate_count>0` 比率显著提升。

### P2（中期优化，1-2 周）

5. 观测面板加“降级闭环完整性”检查
- 自动检测：
  - 有 `delivery_tier` 但 `delivery/` 为空 → 直接标红
  - 事件 `run_id` 空值比例
  - 执行器状态与事件状态不一致

## 五、建议新增回归测试

1. `test_degraded_phase_b_still_packages_minimum_artifacts`
- 输入触发 Discovery 0 候选，断言 `delivery/` 至少包含 manifest + candidate brief/snapshot。

2. `test_event_bus_run_id_is_non_empty`
- 断言 `run_events.jsonl` 每行 `run_id` 非空且等于 `run_dir.name`。

3. `test_discovery_no_candidates_returns_degraded`
- 断言 Discovery 0 候选状态语义与设计一致。

4. `test_domain_explore_query_rewrite_for_cn_long_sentence`
- 对中文长句需求断言 `github_queries` 含领域可检索词，而非人称叙述切片。

## 六、结论

本次 run 暴露的是“**产品闭环问题**”而非单点 bug：  
Doramagic 已具备降级状态判断，但“降级 -> 可交付产物”这一核心承诺在 `PHASE_B` 场景未闭环，且观测字段与状态语义存在分裂。  
若先完成 P0/P1 修复，可显著提升“失败但可用”的用户体验一致性，并降低线上定位成本。
