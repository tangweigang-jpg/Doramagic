# 晶体编译 SOP v5.2

> **A crystal is a proof obligation, not a prompt.**
> 一颗晶体声明对宿主 AI 必须成立的契约，而非劝说它做什么。

**SOP 版本**: `crystal-compilation-v5.2`
**Schema 版本**: `schemas/crystal_contract.schema.yaml` — **唯一真源**

---

## 0. 第一性原理

v3.x 是"带 5 个 YAML 控制块的 Markdown 段落合集"。v5.0 是"符合 schema 的单一 YAML 契约 + 1 个英文 Human Summary 衍生文件"。

为什么重写：v3.x 把规则散文化，LLM 对中文散文规则**注意力降权**，导致证据质量规则在 OpenClaw 实测中**未触发**。v5.0 把一切规则结构化为 `trigger-action-violation` 三元组 YAML，并英文统一，恢复 LLM 注意力均匀性。

### 8 条不可变量（由 schema 强制）

| # | 不可变量 | Schema 位置 |
|---|---|---|
| I1 | 语言统一（机器英文）| `meta.source_language == "en"` + `locale_contract` |
| I2 | 结构化契约（非散文）| 所有规则是 `{trigger, action, violation_code}` 三元组 |
| I3 | 前置条件硬门禁 | `preconditions[]` |
| I4 | 后置业务语义 | `output_validator.assertions[].business_meaning` 非空 |
| I5 | 知识复利（skill 固化）| `skill_crystallization` |
| I6 | Locale 透明 | `locale_contract.translation_enforcement` |
| I7 | 证据自报 + 强制披露 | `evidence_quality.enforcement_rules[]` |
| I8 | 执行可观测 | `trace_schema.event_types[]` |

### v5.1 新增（消费者价值优先）

| 新字段 | 作用 |
|---|---|
| `meta.authoritative_artifact` | 声明 seed.yaml 是真源；SKILL.md / HEARTBEAT / memory 是可能陈旧的衍生，agent 做行为决策时必须重读 seed.yaml |
| `meta.execution_protocol` | 区分 install vs execute 两阶段 + 定义执行时必跑动作序列 + 产物路径统一（scripts/ / skills/ / .trace/）|
| `post_install_notice` | 安装完成瞬间自动发**能力引导**：1 句定位 + 3 个入门 prompt + "看全部" 提示 |
| `blueprint.featured_use_cases`（可选）| 蓝图作者策展 3 个入门 UC；未声明时脚本启发式兜底 |

### v5.2 新增（安装即全量引导）

| 新字段 | 作用 |
|---|---|
| `post_install_notice.message_template.capability_catalog` | 安装后**全量目录**按分组展示，host 直接渲染无需推理。解决 v5.1 "用户必须再问一次才看到全部功能"的缺口 |
| `post_install_notice.message_template.call_to_action` | 明确邀请："告诉我你想试哪个"。消费者被动浏览 → 主动互动 |
| `blueprint.capability_groups`（可选）| 蓝图作者策展 N 组（通常 3-6 组），每组声明 filter 过滤 UCs。**不同领域的蓝图用自己的 filter 字段**（金融可用 `type`，Web 可用 `stage`，ML 可用 `model_stage`）|

**普适性保证**：
- 编译脚本**不硬编码任何领域术语**（不写 backtest / MACD / zvt 这类词）
- 启发式兜底用通用英文 keyword（data / compute / report / util）匹配 emoji
- 蓝图声明优先 → 启发式兜底 → 单组 fallback，三级降级

### v5.2 质量规则（2026-04-18 量化评审后补，普适性要求）

以下 3 条规则是**编译脚本的硬约束**，所有未来蓝图编译同样受约束：

**Q1：short_description 不允许 mid-sentence 截断**
- `capability_catalog.groups[].ucs[].short_description` 必须是 `business_problem` 的**第一句整句**（按 `.` / `。` / `;` 分割），150 字符上限
- 不允许用 `[:80]` 或类似机械切断
- 若 `business_problem` 首句超过 150 字符，取前 150 字符并**回溯到最近的空格边界**（避免词中切断）
- 若 `business_problem` 为空，降级到 `data_domain` 或 `name`

**Q2：cross-cutting concern 必须合并为单个 stage，不生成占位桩**
- 非主 pipeline stage 的 BDs（`algorithm` / `default_value` / `error_handling` 等）**合并到单个 `cross_cutting_concerns` stage**
- 该 stage 的 `narrative` 必须**实质化**：
  - `does_what` 声明合并来源（e.g. "Invariants spanning multiple stages — from N groups: ..."）+ 统计数字
  - `key_decisions` 解释合并原因 + 如何溯源回主 stage
  - `common_pitfalls` 说明跨 stage 修改时的风险
- **禁止**生成形如 `Cross-cutting concern: X.` + `See business_decisions for this stage.` 的桩 narrative

**Q3：locale_contract.user_facing_fields 必须全覆盖用户可见字段**
- 默认值必须列出所有用户可见字段路径（至少 9 条，对应 human_summary / evidence_quality.user_disclosure_template / post_install_notice 全部子字段）
- 脚本生成时直接填充**完整默认列表**，不依赖 schema default 兜底
- 用意：host 若读 `locale_contract.user_facing_fields` 做翻译路由，不会遗漏 capability_catalog 等字段

---

## 1. 输入

与 v3.x 相同：

| 来源 | 路径 |
|---|---|
| 蓝图 | `knowledge/sources/{domain}/{bp}/LATEST.yaml` |
| 约束 | `knowledge/sources/{domain}/{bp}/LATEST.jsonl` |
| 前处理清单 | `knowledge/sources/{domain}/{bp}/crystal_inputs/*`（由 `prepare_crystal_inputs.py` 产出）|

---

## 2. 产出（v5.0 全变）

| 文件 | 说明 |
|---|---|
| `{id}.seed.yaml` | **主契约**，必须符合 `crystal_contract.schema.yaml`，是晶体的唯一真源 |
| `{id}.human_summary.md` | 从 seed.yaml 的 `human_summary` 块渲染的英文衍生；宿主 agent 运行时翻译为用户 locale 呈现 |
| `validate.py` | 从 `output_validator.assertions` 生成的可执行 Python |
| `{id}.seed.quality_report.json` | quality_gate 产出的机器可读报告 |

**不再产出**：`{id}.seed.md`、`{id}.ir.yaml`（IR 合并进 seed.yaml 的 `meta` 段）。

---

## 3. 编译流程

### 3a. 自动化骨架（~10 秒）

```bash
make crystal-full BP={blueprint-slug} VERSION=v5.0
```

等价于：
```bash
python scripts/prepare_crystal_inputs.py --blueprint-dir ...
python scripts/compile_crystal_skeleton.py --blueprint-dir ... --output-seed ....seed.yaml --output-human-summary ....human_summary.md --sop-version crystal-compilation-v5.2
python scripts/crystal_quality_gate.py --crystal ....seed.yaml --schema schemas/crystal_contract.schema.yaml --strict
```

机械保证：所有 schema 必填字段齐全、全部 BD/UC/约束 ID 结构化入 yaml、preconditions/evidence_quality/traceback/skill_crystallization 契约成型。

### 3b. 灵魂补充（~10 分钟，可委托 sonnet 子代理）

骨架产出的 YAML 中以下字段是**占位符**（`"TODO: ..."` 或空串），需补：

| 字段 | 内容要求 |
|---|---|
| `architecture.stages[].narrative.does_what` | 1 句英文，用具体类/函数名 |
| `architecture.stages[].narrative.key_decisions` | 1 句英文，引用 1-2 个 BD-ID，带 "chose X not Y because..." |
| `architecture.stages[].narrative.common_pitfalls` | 1 句英文，引用 1-2 个 {domain}-C-ID 或 SL-ID |
| `human_summary.what_i_can_do.tagline` | 2-3 句英文，Doraemon persona，含框架边界吐槽 |
| `human_summary.what_i_can_do.use_cases[]` | 3-5 个英文具体用例 |
| `human_summary.what_i_auto_fetch[]` | 3-5 个英文 |
| `human_summary.what_i_ask_you[]` | 3-5 个英文 |
| `output_validator.assertions[].business_meaning` | 若 schema 校验通过但 SA-05 不通过，表示 OV 只做了结构检查；补业务语义 |

**全英文**。宿主 agent 运行时翻译为用户 locale。中文用户看到的 Human Summary 由 agent 翻译生成，不在 seed.yaml 中持久化。

### 3c. 门禁验证

```bash
python scripts/crystal_quality_gate.py --crystal {id}.seed.yaml --strict
```

两层检查（见 §4）。

### 3c-bis. 蓝图可选字段 `featured_use_cases`（v5.1）

蓝图作者可在 `LATEST.yaml` 声明：
```yaml
featured_use_cases:
  - uc_id: UC-XX
    beginner_prompt: "Natural-language imperative, e.g. 'Find stocks in MACD bullish state'"
  # exactly 3 entries
```

未声明时，`compile_crystal_skeleton.py` 启发式兜底：
1. 筛选 `data_domain != backtest` 的 UC（降低执行门槛），或全是 backtest 时选第一个
2. 按 `positive_terms[0]` 字长升序取前 3
3. `beginner_prompt` 用 `f"Try {uc.name}"` 兜底
4. 标记每条 `auto_selected: true`

### 3d. 执行后 skill 固化（新，I5）

宿主 AI 跑完晶体后（G1-G10 全通过），触发：

```bash
python scripts/crystal_skill_emitter.py \
  --crystal {id}.seed.yaml \
  --workspace ~/.openclaw/workspace \
  --entry-script scripts/{main}.py \
  --validate-script scripts/validate.py \
  --detected-uc UC-{n}
```

产出 `~/.openclaw/workspace/skills/{slug}.skill`，供未来同 intent 直接 invoke。

---

## 4. 质量门禁：两层

### 4a. Layer 1 — Schema Validation

`crystal_quality_gate.py` 先用 JSON Schema 校验 seed.yaml 完整性。失败即退出码 1，**不进入 Layer 2**。

失败模式：字段缺失 / 类型错误 / pattern 不匹配 / 数组元素不足。

### 4b. Layer 2 — Semantic Assertions

schema 只保证结构，以下 13 条断言保证意义：

| # | 断言 | 检查 |
|---|---|---|
| SA-01 | BD 覆盖 100% | `architecture.stages[].business_decisions[].id` 唯一集 == 蓝图 BD 全集 |
| SA-02 | UC 覆盖 100% | `intent_router.uc_entries[].uc_id` == 蓝图 known_use_cases 全集 |
| SA-03 | 约束覆盖 100% | `constraints.fatal[] + constraints.regular[]` ID 并集 == LATEST.jsonl 全集 |
| SA-04 | Fatal 精确匹配 | `constraints.fatal[].id` == LATEST.jsonl severity=fatal 集合 |
| SA-05 | OV 业务语义 | 每条 `output_validator.assertions[].check_predicate` **不在**黑名单（`"len(result) == 0"` / `"not result"` / `"result is None"`），且 `business_meaning` 非空 |
| SA-06 | Preconditions 非空 | `preconditions[]` ≥ 1 |
| SA-07 | Evidence 规则结构化 | `evidence_quality.enforcement_rules[]` 每条含 `trigger + action + violation_code` |
| SA-08 | 机器文本语言一致 | seed.yaml 字符串值 CJK 字符比例 < 5%（`human_summary.locale_rendering.preserve_verbatim` 白名单豁免）|
| SA-09 | Skill 契约完整 | `skill_crystallization.{trigger, output_path_template, captured_fields, action}` 齐 |
| SA-10 | Locale 契约完整 | `locale_contract.translation_enforcement.{trigger, action, violation_code}` 齐 |
| SA-11 | Hard Gate ≥4 | `acceptance.hard_gates[]` 至少 G1-G4 |
| SA-12 | Human Summary 英文 | `human_summary.*` 字符串 CJK 比例 < 2% |
| SA-13 | source_language 锁 | `meta.source_language == "en"` |
| SA-14 | authoritative_artifact 完整 | `meta.authoritative_artifact.{primary, non_authoritative_derivatives, rule}` 齐；`primary == "seed.yaml"` |
| SA-15 | execution_protocol 完整 | `meta.execution_protocol.{install_trigger, execute_trigger, on_execute, workspace_resolution}` 齐；`on_execute` ≥ 3 项 |
| SA-16 | post_install_notice 完整 | `post_install_notice.message_template.featured_entries` 恰 3 项；每项 uc_id 在 intent_router 中可查；`enforcement.violation_code == "PIN-01"` |
| SA-17 | capability_catalog 完整 | `post_install_notice.message_template.capability_catalog.groups` 非空；**所有 intent_router UC 被精确覆盖 1 次**（无丢失、无重复）；每组 `uc_count == len(ucs)`；每条 UC 有非空 `sample_triggers` |
| SA-18 | short_description 无 mid-cut | 每条 `capability_catalog.groups[].ucs[].short_description` 末尾是**句子终止符**（`. ? ! 。 ？ ！`）或**最后一词 ≥ 3 字符**（避免 "... on a" 这种短单词结尾的截断残留）；允许白名单短词：`US / UK / AI / ML / IT / EU` |

### 4c. 退出码

| 码 | 含义 |
|---|---|
| 0 | Layer 1 + Layer 2 全 PASS |
| 1 | 任一失败（strict 模式）|
| 2 | 输入错误（文件缺失 / YAML 解析失败 / schema 文件缺失）|

---

## 5. 从 v3.x 迁移

**不向后兼容**。v3.x 的 `.seed.md` 格式被 v5.0 quality_gate **拒绝接收**。

迁移路径：
1. 保留历史 `{id}-v3.x.seed.md` 作为对照基线（不删）
2. 重跑 `make crystal-full VERSION=v5.0`
3. 补灵魂（英文版，可让 sonnet 子代理套用 v3.x 中文叙事 translate）
4. `make crystal-gate VERSION=v5.0` 确认 PASS
5. 旧 `PRODUCTION.seed.md` → `PRODUCTION.seed.yaml`（v5.0 版）

---

## 6. Agent 协作规范

宿主 AI（OpenClaw / Claude Code / Codex）读 v5.0 晶体时必须：

1. **读 seed.yaml**，按 schema 理解每个字段（不做段落 grep）
2. **Locale 检测**：按 `locale_contract.locale_detection_order` 确定用户语言
3. **首次响应**：按 `locale_contract.translation_enforcement` 翻译 `human_summary.*` 字段为用户 locale 呈现
4. **执行前**：逐条运行 `preconditions[].check_command`，任一失败按 `on_fail` 输出给用户并停止
5. **执行中**：遵守 `spec_lock_registry.semantic_locks[]`（违反 = fatal）+ `evidence_quality.enforcement_rules[]`（触发时必执行 action）
6. **执行后**：调用 `validate.py`（schema `output_validator.scaffold.tail_block` 定义的 DO NOT MODIFY 围栏）
7. **skill 固化**：若 `skill_crystallization.trigger` 条件满足，调用 `crystal_skill_emitter.py` 生成 `.skill`

违反任一条 → `trace_schema.event_types.false_completion_claim`。

---

## 7. Trace Schema（I8）

宿主必须向 `{workspace}/.trace/execution_trace.jsonl` 写入以下事件：

| event_type | 含义 |
|---|---|
| `precondition_check` | 每条 `PC-*` 的检查结果 |
| `spec_lock_check` | 每条 `SL-*` 的运行时验证 |
| `evidence_rule_fired` | `EQ-*` 触发时 |
| `evidence_rule_skipped` | `EQ-*` 条件不满足（正常跳过）|
| `locale_translation_emitted` | Human Summary 翻译完成 |
| `hard_gate_passed` / `hard_gate_failed` | 每条 `G*` 的判定 |
| `skill_emitted` | `.skill` 文件生成 |
| `false_completion_claim` | 任一契约被绕过 |

---

## 8. 效能验证（保留 v3.2 Step 10 内容）

见 [附录 A：Step 10 效能验证流程]。核心不变：10a 基线（无晶体）/ 10b 晶体版 / 10c 对比。

---

## 附录 A：Step 10 效能验证流程

### 10a. 基线测试（无晶体）

给目标宿主同样的 user_intent，但**不加载晶体**，只给一句话任务描述。记录：
- 是否完成任务
- 产出质量（Hard Gate 通过数）
- 关键决策 AI 做了什么选择
- 出现了哪些错误

### 10b. 晶体测试

给目标宿主同样的 user_intent + 编译好的 seed.yaml。记录同上维度。

### 10c. 对比

| 维度 | 基线 | 晶体 | 判定 |
|---|---|---|---|
| Hard Gate 通过数 | X/N | Y/N | Y > X 为有效 |
| 关键参数漂移 | 列出 | 列出 | 晶体版漂移更少为有效 |
| 领域错误 | 列出 | 列出 | 晶体版避免为有效 |
| 领域知识应用 | 是否犯领域错 | 是否正确应用 | **最核心判据** |
| `.skill` 产出 | 无 | 有 | **v5.0 特有判据** |
| Evidence 规则触发 | N/A | 触发次数 | v5.0 特有 |
| Precondition 拦截 | N/A | 拦截次数 | v5.0 特有 |

---

## 附录 B：变更历史

| 版本 | 日期 | 主要改动 |
|---|---|---|
| v3.0 | 2026-04 | 初稿（中文叙事 SOP）|
| v3.1 | 2026-04 | +14 gaps（rationalization_guard / 双联约束 / 文档源）|
| v3.2 | 2026-04-18 | +证据质量声明 + 溯源政策 + G9/G10 + D39/D40 |
| v5.0 | 2026-04-18 | Schema-driven 重写：crystal = proof obligation；全英文机器文本 + 运行时 locale 翻译；结构化 trigger-action-violation 规则；preconditions / skill_crystallization / trace_schema 纳入契约；两层门禁（schema + 13 条 SA）|
| v5.1 | 2026-04-18 | 消费者价值优先：`meta.authoritative_artifact`（seed.yaml 真源锁）+ `meta.execution_protocol`（install/execute 边界）+ `post_install_notice`（安装即发能力引导，3 句定位+入门）+ `featured_use_cases` 蓝图策展字段；SA 扩到 16 条；新增 `crystal_skill_readme_emitter.py` 工具 |
| **v5.2** | **2026-04-18** | **安装即全量引导：`post_install_notice.capability_catalog`（所有 UC 按分组结构化，host 直接渲染）+ `call_to_action` 互动邀请 + `blueprint.capability_groups` 作者策展字段（可选，无声明时脚本启发式兜底）；SA-17 catalog 完整性；普适性要求：编译脚本不硬编码任何领域词。**  **量化评审后补 3 条质量规则（Q1 short_description 不 mid-cut + Q2 cross-cutting 合并单 stage + Q3 locale_contract 全覆盖 9 字段）+ SA-18 mid-cut guard** |

（跳过 v4.0 — 直接 v3.2 → v5.0 → v5.1 → v5.2）

---

*v5.0 | 2026-04-18 | 编写者：Doramagic 主线程 | 真源：`schemas/crystal_contract.schema.yaml`*
