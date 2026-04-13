# 工作日志：v6 蓝图提取 Agent 全量改版

> 日期：2026-04-13
> 会话：session 7（约 4 小时）
> 模型：Claude Opus 4.6 (1M context) + MiniMax M2.7（提取）

---

## 一、完成事项

### 1. 技术研究（3 个并行子代理）

- 研究 `deusyu/harness-engineering` 仓库 — Harness Engineering 范式、Böckeler 2×2 矩阵、Sprint 合同
- 研究 `claude-code-instructkr` 报告 — Claude Code 14 章源码逆向、17 条落地建议
- 研究 Doramagic v5.2 蓝图提取 agent 现状 — 17 Phase 架构、Evidence Packet、13 个已知局限

产出：
- `docs/research/2026-04-13-blueprint-agent-improvement-research.md`（技术研究报告）
- `docs/designs/2026-04-13-blueprint-agent-v6-improvement-plan.md`（v6 改进方案）
- `docs/designs/2026-04-13-blueprint-agent-v6-execution-plan.md`（执行方案）

### 2. v6 架构改版（12 个 commit）

三个结构性变更：
1. **worker_resource** — 资源提取独立 Worker（好的蓝图 = 好的框架 + 好的资源）
2. **bp_evaluate** — 独立 Evaluator（Sprint 合同式 4 项验证）
3. **审计闭环** — worker_audit 注入 Synthesis Step 3

辅助改进：
- P5.5 evidence 确定性验证（AST 级 file/line/fn 检查）
- P14 资源注入（worker_resource → global_resources）
- ConvergenceDetector（收敛检测，worker_resource tokens 316K→94K）
- microcompact（LRU 工具结果清理）
- DecisionCache（冻结已验证 BD）
- Quality Gate strict + fix_hints + BQ-03 降为 warning

### 3. knowledge/sources 命名规则重构

- 目录：`finance-bp-009` → `finance-bp-009--zvt`
- 文件：`blueprint.yaml` → `blueprint.v{N}.yaml` + `LATEST.yaml` 符号链接
- manifest：schema v1.0 → v2.0（完整版本历史、stats、evaluator、quality_gate）
- OutputManager 重写 + 约束 pipeline 适配

### 4. MiniMax M2.7 兼容性修复（深度 debug）

| 问题 | 修复 | commit |
|------|------|--------|
| L1 ThinkingBlock 100% 失败 | `_skip_l1` 加 minimax | f28be56 |
| L1 skip raise→misleading log | break + INFO 日志 | 9f8fa4d |
| L2 BDExtractionResult 缺字段 | type_summary/missing_gaps default_factory | 6df2182 |
| L2 MiniMax echo JSON Schema | _extract_json 拒绝 $defs | 0d58853 |
| L2 schema hint 引导失败 | _build_example_instance 替代 model_json_schema | 9850618 |
| type_summary 非法 key (RC_missing) | 宽容处理：drop + warning log | 9850618 |
| Assembly L3 fatal | L3 recovery: 解析 raw text | b158e40 |
| Assembly YAML-like JSON | L3 recovery JSON→YAML fallback | 5db986a |
| Orchestrator 检查旧文件名 | LATEST.yaml 替代 blueprint.yaml | e03bb9b |
| Orchestrator manifest 覆盖 | 重新加载 manifest 再写入 | 3cb63ed |

### 5. bp-009 提取验证

| 运行 | 结果 | tokens | 失败点 |
|------|------|--------|--------|
| v3 (首次 v6) | 完成 | 1.04M | — |
| v4 (重跑) | 完成 | 932K | — |
| v5 (修复验证) | 完成 | 790K | L3 recovery 生效 |

最终 bp-009 v5：8 stages, 79 BD, 31 UC, 8 missing gaps, QG PASS (1 warn)

---

## 二、Commit 列表（12 个）

```
5db986a fix(assembly): L3 recovery tries YAML when JSON fails
b158e40 fix(assembly): L3 recovery — parse raw JSON when Instructor fails
9850618 fix(agent_loop): L2 uses JSON example instead of JSON Schema to guide MiniMax
0d58853 fix(executor): reject JSON Schema echoes in _extract_json
9f8fa4d fix(agent_loop): clean L1 skip — INFO log + break instead of raise RuntimeError
6df2182 fix(schemas): make type_summary and missing_gaps optional in BDExtractionResult
f28be56 fix(extraction_agent): three root-cause fixes from first-principles analysis
3cb63ed fix(orchestrator): reload manifest from disk before final write
e03bb9b fix(orchestrator): check LATEST.yaml instead of blueprint.yaml for output validation
0f2d07d fix(constraint_agent): adapt constraint pipeline to versioned naming scheme
5feaee1 refactor(sources): versioned naming scheme for knowledge/sources
3985b0a feat(extraction_agent): v6 blueprint extraction — resource Worker, independent Evaluator, audit closed-loop
```

---

## 三、踩坑记录

### 坑 1：跳过 L1 暴露了 L2 的隐性依赖

L1 虽然 100% 失败，但它的 tool schema 会**隐式引导** MiniMax 的后续输出格式。跳过 L1 后 L2 freeform 输出质量骤降。教训：修复一个问题前必须理解整条调用链的隐性依赖。

### 坑 2：旧进程不加载新代码

`--resume` 启动的新进程会加载新代码，但 **background 任务如果用的是旧进程**，修复不会生效。多次 resume 失败都是因为旧进程在内存中运行旧代码。教训：修改代码后必须确认是新进程。

### 坑 3：MiniMax 输出 YAML-like JSON

MiniMax 的"JSON"输出经常包含不带引号的 key（`behavior: "xxx"` 而非 `"behavior": "xxx"`），`json.loads()` 失败但 `yaml.safe_load()` 成功。教训：对 MiniMax 的 L3 raw text 必须尝试 YAML 解析。

### 坑 4：复杂 Pydantic schema 对 freeform LLM 不可行

`BlueprintAssembleResult`（嵌套 8+ 层）对 MiniMax L2 freeform 输出**永远无法通过验证**。正确做法是 L3 recovery + 宽容解析，而非追求 Pydantic 严格验证。

### 坑 5：schema echo — LLM 回显 schema 定义

`model_json_schema()` 注入 prompt 后，MiniMax 直接回显 schema 元数据（`$defs`, `$ref`, `properties`）而非按 schema 生成数据。正确做法是注入 JSON 示例实例（"要填的表格"）而非 schema 定义（"表格的定义"）。

---

## 四、关于是否需要全量重跑

**不需要**。理由：

1. v5 提取已完成（Completed: 1, Failed: 0），`blueprint.v5.yaml` 已 promote
2. 所有修复都在 Assembly 和 L2 路径——Worker/Synthesis/Evaluator 未改动
3. YAML fallback 修复是**确定性的**——不依赖 MiniMax 的随机行为
4. 全量重跑会再消耗 ~800K tokens（约 5 元人民币），但不会产生更好的结果

如果要验证，建议在**下一个新蓝图**（非 bp-009）上全量跑一次，同时验证：
- 新代码的 `_build_example_instance` 对 Synthesis L2 的效果
- Assembly L3 recovery 的 YAML 路径
- 版本化输出（应自动生成 v1）

---

*最后更新: 2026-04-13 22:17*
