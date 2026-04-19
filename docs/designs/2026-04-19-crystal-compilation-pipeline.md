# Crystal Compilation Pipeline — v5.3 Reference

**Date**: 2026-04-19
**Status**: Current (v5.3)
**Scope**: Complete end-to-end pipeline documentation + ingredient injection analysis

---

## 一、三句话定位

1. **晶体是什么**：一颗 seed.yaml 结构化契约，声明对宿主 AI（OpenClaw/Claude Code/Codex）必须成立的执行义务。不是提示词，是 proof obligation。
2. **晶体的核心等式**：`好晶体 = 好框架（蓝图）+ 好约束 + 好资源`（PRODUCT_CONSTITUTION §1.3）。三个入料决定晶体质量上限。
3. **晶体工具链的职责**：把三个入料**无损、结构化、按消费者分类**注入 seed.yaml；用门禁验证注入完整性；让 host 按契约消费。

---

## 二、输入端

| 文件 | 内容 | 示例规模（finance-bp-009）|
|---|---|---|
| `knowledge/sources/{domain}/{bp}/LATEST.yaml` | **蓝图**（框架）：business_decisions / known_use_cases / featured_use_cases（可选）/ capability_groups（可选）/ resources / _enrich_meta（审计元数据） | 164 BD + 31 UC |
| `knowledge/sources/{domain}/{bp}/LATEST.jsonl` | **约束**：每行一条 `{id, when, action, severity, kind, consequence, stage_ids, modality, derived_from_bd_id, overclaim_risk, ...}` | 147 条（27 fatal + 120 regular） |
| `schemas/crystal_contract.schema.yaml` | **结构契约**：JSON Schema Draft 2020-12 YAML，17 顶层字段（v5.3）| 822 行 |
| `schemas/consumer_map.yaml`（v5.3 新增）| **消费者映射**：字段路径 → 消费者（NR/SR/TR/EX/VF/SE/MA 七类）| 266 行 |

---

## 三、流水线（`make crystal-full`）

```
crystal-prepare      →      crystal-compile      →      crystal-gate
     ↓                            ↓                          ↓
crystal_inputs/*.md         seed.yaml + *.md             PASS/FAIL
                            + validate.py            + quality_report.json
```

### Step 1: `crystal-prepare` — 预处理清单

**脚本**: `scripts/prepare_crystal_inputs.py`

**目的**：LATEST.jsonl 可能 255KB 超过 agent Read 工具 token 限制，导致虚报覆盖率。预生成分块清单保证 agent 或后续工具能逐条核对。

**产物**（写入 `{bp_dir}/crystal_inputs/`）：
- `bd_checklist.md` — BD 全集 `{id, type, content, stage}`
- `constraint_checklist.md` — 约束全集 `{id, when, action, severity, kind}`
- `uc_checklist.md` — UC 全集 `{id, name, intent_keywords}`
- `coverage_targets.json` — 机器可读的"必须命中全集"

### Step 2: `crystal-compile` — 骨架编译

**脚本**: `scripts/compile_crystal_skeleton.py`（2091 行）

**入口链**：`main()` → `load_inputs()` → `build_seed()` → 序列化 YAML → 写 3 份产物

#### `build_seed()` 的 17 个装配函数（按调用顺序）

| # | build 函数 | 产出字段 | 主消费者 | 入料来源 |
|---|---|---|---|---|
| 1 | `build_meta(bp, target_host, sop_version)` | `meta.{id, version, blueprint_id, sop_version, source_language, compiled_at, authoritative_artifact, execution_protocol}` | MA + EX + NR + SR | bp.id + utcnow + 静态模板 |
| 2 | `build_locale_contract()` | `locale_contract.user_facing_fields[26]` + `translation_enforcement` | TR | 静态列表（v5.3 硬编码 26 条 NR+TR 字段） |
| 3 | `build_evidence_quality(bp)` | `declared.*` + 2 条 `enforcement_rules` + `user_disclosure_template` | VF + NR | **bp._enrich_meta + bp.audit_checklist_summary** |
| 4 | `build_traceback(bp)` | `mandatory_lookup_scenarios[4]` + degraded_lookup | EX | bp.id + 静态 4 场景 |
| 5 | `build_preconditions(ucs, bp.id)` | PC-01~PC-04 | EX + VF | UC 列表启发式（pip 安装检查 / 数据可用性）|
| 6 | `build_intent_router(ucs)` | `uc_entries[].{uc_id, name, positive_terms, negative_terms, ambiguity_question, data_domain}` | SR + NR | **bp.known_use_cases[]**（name + intent_keywords）|
| 7 | `build_context_state_machine()` | CA1~CA4 四状态机 | EX | 静态模板 |
| 8 | `build_spec_lock_registry()` | SL-01~SL-12 | EX + VF | **静态模板（当前版本未真正从 bp.business_decisions 抽取）**⚠️ |
| 9 | `build_preservation_manifest(counts)` | required_objects.*_count | VF | 纯统计（BD/UC/约束/PC 的 count）|
| 10 | `build_architecture(bp, bd_by_stage)` | `stages[].{narrative.{does_what, key_decisions, common_pitfalls}, business_decisions[]}` + `cross_cutting_concerns` 合并 stage（v5.2 Q2 规则）| NR + TR + MA | **bp.business_decisions（按 stage 分组）**|
| 11 | `build_resources(bp, target_host)` | `packages[]` + `strategy_scaffold` + `host_adapter` | EX | **bp.resources（过滤 python_package/dependency）+ 静态兜底** ⚠️ |
| 12 | `build_constraints(fatal, non_fatal)` | `constraints.{fatal, regular}` 结构化数组 | VF + EX | **LATEST.jsonl（按 severity 拆分）**|
| 13 | `build_output_validator()` | OV-01~OV-06（业务语义 assertions）| VF | **静态模板（当前未从蓝图派生）**⚠️ |
| 14 | `build_acceptance()` | `hard_gates[]`（G1~G8） | VF + NR | 静态 gate 模板 |
| 15 | `build_skill_crystallization(**refs)` | `slug_template` + `captured_fields` + `skill_file_schema`（name/intent_keywords/fatal_guards 动态抽取）| SE + SR | 引用已装配的 intent_router + spec_lock + preconditions + resources |
| 16 | `build_human_summary(bp, ucs)` | persona="Doraemon" + tagline + use_cases + auto_fetch + ask_you | NR + TR | **bp（派生）**|
| 17 | `build_post_install_notice(bp, human_summary, ucs)` | positioning + **capability_catalog**（blueprint-declared 或 auto-grouped 5-6 组）+ featured_entries[3] + call_to_action | NR + TR + SR | **bp.capability_groups（可选）+ bp.featured_use_cases（可选）+ 启发式兜底**|

#### 普适性保证（编译脚本硬约束）

- **不硬编码任何领域术语**（不写 backtest/MACD/zvt/ROE 这些词）—— 但见下文 §资源注入的例外
- `_heuristic_emoji()` 用通用英文 keyword 匹配：data→📊 / compute→🧮 / report→📈 / panel→📋 / config→🔧 / misc→📦
- 三级降级：蓝图声明 → 启发式聚类 → 单组 fallback

#### v5.2 质量规则（Q1/Q2/Q3，编译脚本硬约束）

- **Q1**: `_build_uc_summary()` — 提取 business_problem 首句，150 字符上限，空格边界回溯，不做 mid-cut
- **Q2**: `build_architecture` 把非主 pipeline stage 的 BD 合并为 `cross_cutting_concerns` 单 stage，narrative 实质化（不生成"Cross-cutting concern: X. See business_decisions" 占位桩）
- **Q3**: `build_locale_contract` 直接填充完整默认列表（v5.3 扩到 26 条）

#### 产物

| 文件 | 内容 | 示例规模 |
|---|---|---|
| `{bp_id}-{version}.seed.yaml` | 主契约（17 顶层字段 + 19 SA 验证 PASS）| 142,943 bytes / 3244 行 |
| `{bp_id}-{version}.human_summary.md` | 英文 Human Summary 衍生 | ~2KB |
| `validate.py` | 从 OV assertions 渲染的可执行 Python | ~4KB |

### Step 3: `crystal-gate` — 质量门禁

**脚本**: `scripts/crystal_quality_gate.py`（965 行）

#### Layer 1: Schema Validation
- `jsonschema` 包（或降级到 `_minimal_validate()` 手写校验器）
- 失败立即退出，不进 Layer 2

#### Layer 2: 19 条语义断言

（详见 SOP §4b 表格；本文不重复列举）

核心 v5.3 增量：**SA-19 translation_completeness** 读 `consumer_map.yaml` 的 `user_facing_fields_expected[]` 对比 crystal 的 `locale_contract.user_facing_fields`，缺失任一条 → FAIL。守护 Session 27 Fix A 类字段作用域错位。

#### 退出码

- `0` PASS | `1` 任一 FAIL | `2` 输入错误

#### 附加产出

- `{bp_id}-{version}.seed.quality_report.json` 机器可读报告

---

## 四、编译后生命周期

### 4a. Host 安装（OpenClaw）

- 读 seed.yaml → 按 `execution_protocol.install_trigger` 识别安装事件
- 发 PIN-01 Notice：positioning + capability_catalog + 3 featured_entries + call_to_action（全部 NR 字段翻译到用户 locale）
- 写 `HEARTBEAT.md` 记录安装完成

### 4b. Host 执行（execute_trigger 匹配）

按 `execution_protocol.on_execute[]` 的 5 步：重读 seed → preconditions → CA1 状态 → EQ rules 评估 → user_facing_fields 翻译 → 执行 UC → `validate.py`（OV assertions）→ hard_gates → 所有 PASS 后触发 skill 固化。

### 4c. skill 固化

**脚本**: `scripts/crystal_skill_emitter.py`

写 `~/.openclaw/workspace/skills/{slug}.skill`。消费者 = SR（下次用户用 intent_keyword 说话时直接 invoke）。

### 4d. SKILL.md 渲染（可选）

**脚本**: `scripts/crystal_skill_readme_emitter.py`（619 行）

从 seed.yaml 渲染权威 SKILL.md（9 段）。注意 OpenClaw 自身会生成自己的 SKILL.md 摘要，这份是 Doramagic 官方版。

---

## 五、`好晶体 = 好框架 + 好约束 + 好资源` 的注入机制

用户问题："这三个内容如何注入晶体？" 下面按入料追踪注入路径 + 当前实现的强项与债务。

### 5.1 好框架（蓝图，bp.*）→ 晶体

**注入方式**：直接从 `LATEST.yaml` 读取 YAML 字段，传给 15 个 build 函数中的 **7 个** 使用。

| 蓝图字段 | 注入到 | build 函数 | 消费者 |
|---|---|---|---|
| `bp.id` | `meta.blueprint_id` + `meta.id` 前缀 + `traceback`(bp_id 上下文) + `skill_crystallization.slug_template` 变量 + `validate.py` 文件头 | build_meta / build_traceback / build_skill_crystallization / render_validate_py | MA + EX + SE |
| `bp._enrich_meta.{evidence_coverage_ratio, evidence_verify_ratio, evidence_invalid, ...}` + `bp.audit_checklist_summary` | `evidence_quality.declared.*` | build_evidence_quality | VF + NR |
| `bp.business_decisions[]` | `architecture.stages[].business_decisions[]` + `architecture.stages[].narrative.*` + `preservation_manifest.business_decisions_count` | build_architecture + build_preservation_manifest | NR + TR + MA + VF |
| `bp.known_use_cases[]` | `intent_router.uc_entries[]` + `preconditions[]`(applies_to_uc) + `post_install_notice.capability_catalog.groups[].ucs[]` + `human_summary.what_i_can_do.use_cases[]` | build_intent_router / build_preconditions / build_capability_catalog / build_human_summary | SR + NR + TR + EX |
| `bp.capability_groups[]`（可选，作者策展）| `post_install_notice.capability_catalog.groups[]`（Path A）；未声明时启发式生成（Path B） | build_capability_catalog | NR |
| `bp.featured_use_cases[]`（可选）| `post_install_notice.message_template.featured_entries[]`；未声明时启发式选 3 条 | build_post_install_notice | NR + TR + SR |
| `bp.resources[]`（子集）| `resources.packages[]` | build_resources | EX + VF |

**强项**：
- 蓝图 BD / UC / 约束全集进 `preservation_manifest.required_objects.*_count` → SA-01/SA-02/SA-03 守护 **100% 覆盖**
- `capability_groups` / `featured_use_cases` 允许作者策展，启发式是兜底，两级降级
- `_enrich_meta` 审计元数据直接进 `evidence_quality.declared` → VF 层可据此触发 `EQ-01` 低证据披露规则

**当前债务**：
1. **`build_spec_lock_registry()` 当前是完全静态的 12 条 SL**（见 compile 脚本 L513+），没从 `bp.business_decisions[type=semantic_lock]` 抽取 → 不同领域蓝图复用同一批 SL（ZVT 专属）❗ 批编时问题会暴露
2. **`build_output_validator()` 当前也完全静态（OV-01~OV-06）**，没从蓝图业务语义派生 → 所有晶体共享同一组 OV 断言 ❗
3. **`architecture.stages[].narrative.{does_what, key_decisions, common_pitfalls}`** 是占位串 `"TODO: ..."` 或空串 —— 需要"灵魂补充"阶段（sonnet 子代理或主线程填入英文 narrative）才能通过 Human Summary 质检

### 5.2 好约束（constraints.jsonl）→ 晶体

**注入方式**：`load_constraints(path)` 读 LATEST.jsonl 逐行解析 → `build_seed()` 按 severity 拆分 `fatal_constraints` / `non_fatal_constraints` → `build_constraints()` 按 `$defs.constraint` schema 格式化入 `crystals.constraints.{fatal, regular}`。

| 约束字段 | 注入到 | 消费者 |
|---|---|---|
| `id, when, action, severity, kind, consequence, stage_ids, modality, derived_from_bd_id, conflict, overclaim_risk` | `constraints.fatal[] / regular[]` 结构化数组（每条保留全部 13 字段）| VF + EX（`.action`）+ NR（`.consequence` v5.3 列入 user_facing_fields）|
| severity=fatal 子集 | `skill_crystallization.skill_file_schema.fatal_guards[]` | SE + SR |
| 全集 count | `preservation_manifest.fatal_constraints_count` + `non_fatal_constraints_count` | VF |
| 全集 id | SA-03 / SA-04 覆盖守护 | VF |

**强项**：
- 约束**不做任何 summarization**，全字段透传 → 避免语义损耗
- severity=fatal 自动提升为 skill 路由的 fatal_guards → `.skill` 文件里 SR 能直接识别
- 约束 `consequence` 字段在 v5.3 被加入 `user_facing_fields[]` → 约束违反时错误文案自动翻译

**当前债务**：
1. 约束本身在 `crystals.constraints.*` 中是"结构化列表"，但 **host 如何在真实执行中把 `constraints.fatal[].when` 表达式变成可运行检查** —— 这依赖 `when` 字段是 Python 表达式或 host 可理解的 DSL，当前蓝图 `when` 字段自由文本（如 `"数据采集阶段，当数据源失败"`）→ host 只能做语义理解，不能精确匹配。**约束从"人类可读"到"机器可执行"中间还有一层未闭合的鸿沟。**
2. `constraints.regular[].when` 未列入 user_facing_fields（只 consequence 列入）—— v5.4 可考虑扩展

### 5.3 好资源（bp.resources + host_adapter）→ 晶体

**注入方式**：`build_resources(bp, target_host)` 组装三部分。

| 资源来源 | 注入到 | 消费者 |
|---|---|---|
| `bp.resources[]` 过滤 `type in (python_package, dependency)` | `resources.packages[].{name, version_pin}` | EX + VF |
| **静态默认包列表**（zvt / pandas / numpy / SQLAlchemy / plotly / dash / akshare / baostock）| `resources.packages` 在 bp.resources 为空时兜底 ❗ | EX + VF |
| **静态 strategy_scaffold**（entry_point_name="run_backtest" + tail_template）| `resources.strategy_scaffold.*` | EX + SE |
| `target_host` 参数分支 → `host_adapter` | `resources.host_adapter.*`（timeout / install_recipes / shell_restriction / credential_injection / path_resolution / file_io_tooling）| EX |

**强项**：
- host_adapter 按 target_host 分支（openclaw / claude_code / generic）—— 同一晶体在不同宿主有适配指令
- OpenClaw 的 shell_operator_restriction / credential_injection / path_resolution 全部显式声明 → host 无需猜测

**当前债务（批量编译前必须修）**：
1. ❗ **静态默认包列表是 ZVT-specific**（zvt / akshare / baostock）—— 批编 freqtrade / qlib 时若蓝图 resources 为空，会被误注入 ZVT 包。
2. ❗ **`strategy_scaffold.entry_point_name = "run_backtest"` 硬编码** —— 数据管道类蓝图（bp-079 akshare / bp-111 ccxt）的入口不应叫 run_backtest。
3. ❗ **`tail_template` 硬编码 `result.csv` 输出路径** —— 非 CSV 产出的蓝图（如训练模型、生成报告）会报错。
4. ❗ **OpenClaw host_adapter 的 install_recipes 硬编码 `python3 -m zvt.init_dirs`** —— 对所有非 ZVT 蓝图无意义。

这四条是当前编译脚本的**最大普适性漏洞**。Session 27 P-06 讲的是"字段作用域错位"，但 `build_resources` 是另一个维度的错位：**领域默认值被当成通用兜底**。

### 5.4 三种入料的质量信号传递

| 入料 | 质量指标 | 传递路径 | 守护机制 |
|---|---|---|---|
| 好框架 | evidence_coverage_ratio / evidence_verify_ratio | bp._enrich_meta → evidence_quality.declared → EQ-01/02 enforcement_rules | VF 层触发告警模板 → NR 渲染给用户 |
| 好约束 | fatal / regular severity 分布 + conflict / overclaim_risk 标记 | LATEST.jsonl → constraints.{fatal,regular} → skill_file_schema.fatal_guards | SR 层 fatal 路由硬中断 |
| 好资源 | packages.version_pin 可安装性 + host_adapter 正确性 | bp.resources → resources.packages → preconditions.check_command | VF 层 PC 预检失败 → NR 向用户提示 `pip install` |

**三者共同的缺口**：**蓝图本身是否"好"** 无法在编译时判断。如果 bp.evidence_verify_ratio = 0.44（bp-009 实际值），晶体只能**如实披露**，不能修复。编译工具链只能做"高保真注入"，无法修复"低质量蓝图"。这把球踢回给蓝图抽取工具链（blueprint agent）。

---

## 六、v5.3.1 / v5.4 待办（本文顺带列出）

| 优先级 | 改动 | 关联 §5.x |
|---|---|---|
| **P0 批编前必修** | `build_resources` 的 ZVT-specific 默认值替换为"空即留空" 或从 target_host 派生通用默认 | §5.3 债务 1-4 |
| **P0** | `build_spec_lock_registry` 从 `bp.business_decisions[type=semantic_lock]` 抽取，不再静态 | §5.1 债务 1 |
| **P1** | `build_output_validator` 从 bp UC 派生业务语义 assertions | §5.1 债务 2 |
| **P1** | compile 脚本按消费者分 7 个 build block 重构 | v5.3 worklog §五 |
| **P1** | quality_gate 按消费者分层重组错误消息 | v5.3 worklog §五 |
| **P2** | 删除 `meta.target_host` + `acceptance.soft_gates[].rubric` | v5.3 已标 deprecated |
| **P2** | schema 全字段 x-consumer 注释（当前只 3 处）| v5.3 worklog §五 |
| **P2** | 批编 53 蓝图做普适性回归 | §5.3 债务暴露前提 |

---

## 七、本文与其他文档的关系

| 文档 | 角色 |
|---|---|
| `sops/finance/crystal-compilation-sop.md` | **流程规范**（开发者执行指南）|
| `schemas/crystal_contract.schema.yaml` | **结构契约**（机器可读）|
| `schemas/consumer_map.yaml` | **消费者映射**（机器可读） |
| **`docs/designs/2026-04-19-crystal-compilation-pipeline.md`**（本文）| **架构参考**（为什么这样流水，入料如何注入） |
| `docs/designs/2026-04-19-crystal-field-consumer-matrix.md` | **字段矩阵详表**（7 消费者 × 全字段，v5.3 设计起点） |

---

*v1.0 | 2026-04-19 | Session 28 后补 | 主线程 Opus 4.7 (1M)*
