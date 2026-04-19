# Crystal Field-Consumer Matrix v0.1

**Date**: 2026-04-19
**Author**: Session 28 (Opus 4.7 1M)
**Status**: Draft — awaiting review
**Rationale**: Session 27 Fix A 揭示了 "改了字段但行为不变" 的根因是**字段作用域错位**——`skill_crystallization.skill_file_schema` 是 skill router 消费，不是 Notice renderer 消费。Schema 当前按**作者视角**（不变式 I1-I8）组织字段，需要重构为按**消费者视角**索引，让编译脚本和质检门禁可以按消费者路径精准操作。

---

## 一、消费者定义（7 类）

| Consumer | 缩写 | 在 host 侧的触发时机 | 关心什么 |
|---|---|---|---|
| **notice_render** | NR | `skill_installation_complete` 后渲染 Notice | 用户能读的文案 + 结构 |
| **skill_router** | SR | 每轮用户消息到达，匹配 intent → 路由到 UC | 关键词、触发词、UC 元数据 |
| **translator** | TR | 首次用户消息 + 检测到非 en locale | 哪些字段要翻译 + 哪些保留字面 |
| **executor** | EX | 用户用 action verb 触发 execute_trigger | 真实执行所需脚本 / 包 / 入口 |
| **verifier** | VF | 执行前（preconditions）+ 执行后（OV） | check 表达式 + fail message |
| **skill_emitter** | SE | 所有 hard gates pass 后写 .skill 文件 | .skill 文件字段 schema |
| **meta_archival** | MA | 不被 host 运行时消费，仅用于溯源/审计 | 编译来源、时间、版本、蓝图 id |

**不变式**：每个字段**只有一个主消费者**。如有多个消费者，必须显式声明（避免 Session 27 Fix A 的作用域误判）。

---

## 二、全字段 × 消费者矩阵

### meta.*

| Field | Primary Consumer | Secondary | Notes |
|---|---|---|---|
| `meta.id` | MA | SE (写入 skill_file_schema.name 前缀) | - |
| `meta.version` | MA | SE | - |
| `meta.blueprint_id` | MA | - | - |
| `meta.sop_version` | MA | - | - |
| `meta.source_language` | TR | MA | TR 用它确定 "翻译前语言" |
| `meta.compiled_at` | MA | - | - |
| `meta.target_host` | MA | - | 未被实际逻辑消费 |
| `meta.authoritative_artifact.*` | EX (rule 字段影响行为) | MA | 告诉 executor "重读 seed.yaml 不要信 SKILL.md" |
| `meta.execution_protocol.install_trigger` | NR | - | host 用它判断 "这次是安装不是执行" → 触发 Notice |
| `meta.execution_protocol.execute_trigger` | SR | - | router 用它判断 "这次是执行不是安装" |
| `meta.execution_protocol.on_execute[]` | EX | - | executor 按序执行的 checklist |
| `meta.execution_protocol.workspace_resolution.*` | EX | SE (skills_path) | 路径解析 |

**观察**：`meta.target_host` 当前无消费者——**dead field**，可在 v5.3 删除或补消费逻辑。

### locale_contract.*

| Field | Primary Consumer | Notes |
|---|---|---|
| `locale_contract.source_language` | TR | - |
| `locale_contract.user_facing_fields[]` | TR | **核心字段清单**——TR 按此路径列表翻译 |
| `locale_contract.locale_detection_order[]` | TR | - |
| `locale_contract.translation_enforcement.*` | TR + VF | VF 检查是否触发 LOCALE-01 |

### evidence_quality.*

| Field | Primary Consumer | Notes |
|---|---|---|
| `evidence_quality.declared.*` | VF | VF 对 declared 值做 trigger 判定 |
| `evidence_quality.enforcement_rules[]` | VF | - |
| `evidence_quality.user_disclosure_template` | NR (首次响应前缀) + TR | 同时是 NR 的前置内容 + TR 的翻译对象 |

### traceback.*

| Field | Primary Consumer | Notes |
|---|---|---|
| `traceback.source_files.*` | EX (回查时读哪个文件) | - |
| `traceback.mandatory_lookup_scenarios[]` | EX | 每条是 "当 condition 时读 target" |
| `traceback.degraded_lookup.no_fs_access` | EX | 降级行为 |

### preconditions[]

| Field | Primary Consumer | Notes |
|---|---|---|
| `preconditions[].check_command` | EX (VF 子集) | 执行前运行 |
| `preconditions[].on_fail` | NR (向用户显示) + TR | 错误文案，需要翻译 |
| `preconditions[].severity` | EX | fatal 停止，warn 继续 |
| `preconditions[].applies_to_uc[]` | EX | 作用域过滤 |

**观察**：`on_fail` 目前不在 `locale_contract.user_facing_fields[]` 中——**潜在翻译遗漏**，触发时用户会收到英文。

### intent_router.uc_entries[]

| Field | Primary Consumer | Notes |
|---|---|---|
| `uc_id` | SR + NR (catalog 显示) + SE | - |
| `name` | NR (catalog 显示) + SR | - |
| `positive_terms[]` | SR | 路由匹配核心 |
| `negative_terms[]` | SR | 排除匹配 |
| `data_domain` | SR (领域过滤) | - |
| `ambiguity_question` | NR (歧义时显示) + TR | **翻译遗漏候选** |

### context_state_machine.*

| Field | Primary Consumer | Notes |
|---|---|---|
| `states[].entry/exit/timeout` | EX | - |
| `enforcement` | EX | - |

### spec_lock_registry.*

| Field | Primary Consumer | Notes |
|---|---|---|
| `semantic_locks[].locked_value` | EX | 运行时做值匹配 |
| `semantic_locks[].violation_is` | VF | fatal → 中断 |
| `implementation_hints[]` | EX (参考) | - |

### preservation_manifest.*

| Field | Primary Consumer | Notes |
|---|---|---|
| `required_objects.*_count` | VF | host 用于验证未压缩丢失 |

### architecture.stages[]

| Field | Primary Consumer | Notes |
|---|---|---|
| `pipeline` | NR (可选展示) | - |
| `stages[].narrative.does_what` | NR (详情展开) + TR | **翻译遗漏** |
| `stages[].narrative.key_decisions` | NR + TR | 同上 |
| `stages[].narrative.common_pitfalls` | NR + TR | 同上 |
| `stages[].business_decisions[]` | MA (溯源) | 运行时不消费 |

**观察**：整个 stages.narrative 三字段都是用户可读内容，但**未列入 `user_facing_fields`** → locale 翻译遗漏面较大。

### resources.*

| Field | Primary Consumer | Notes |
|---|---|---|
| `packages[]` | EX (pip install) + VF (版本校验) | - |
| `data_sources[]` | EX | - |
| `strategy_scaffold.entry_point_name` | EX + SE | - |
| `strategy_scaffold.tail_template` | EX (DO NOT MODIFY) | - |
| `host_adapter.*` | EX | host 特化 |

### constraints.fatal[] / regular[]

| Field | Primary Consumer | Notes |
|---|---|---|
| `constraints.fatal[].*` | VF + EX | fatal 中断执行 |
| `constraints.regular[].*` | VF (warning) | - |
| `consequence` | NR (失败时显示) + TR | **翻译遗漏** |

### output_validator.*

| Field | Primary Consumer | Notes |
|---|---|---|
| `assertions[].check_predicate` | VF | 执行后运行 |
| `assertions[].failure_message` | NR + TR | **翻译遗漏** |
| `assertions[].business_meaning` | MA (gate 审计) | - |
| `scaffold.validate_py_path` | EX | - |
| `scaffold.tail_block` | EX | - |

### acceptance.*

| Field | Primary Consumer | Notes |
|---|---|---|
| `hard_gates[].check` | VF | - |
| `hard_gates[].on_fail` | NR + TR | 失败文案 |
| `soft_gates[].rubric` | MA (质量参考) | 运行时不强制 |

### skill_crystallization.*

| Field | Primary Consumer | Notes |
|---|---|---|
| `trigger` | SE | - |
| `output_path_template` | SE | - |
| `slug_template` | SE | - |
| `captured_fields[]` | SE | - |
| `action` | SE + NR (写入后通知) + TR | **翻译遗漏** |
| `violation_signal` | VF | - |
| **`skill_file_schema.*`** | **SR**（.skill 写出后被 host 用它路由） | **Session 27 Fix A 的错位字段——不影响 Notice** |

### post_install_notice.*

| Field | Primary Consumer | Notes |
|---|---|---|
| `trigger` | NR | - |
| `message_template.positioning` | NR + TR | 已在 user_facing_fields |
| `message_template.capability_catalog.group_strategy.*` | NR | - |
| `message_template.capability_catalog.groups[].name` | NR + TR | 已在 user_facing_fields |
| `message_template.capability_catalog.groups[].description` | NR + TR | 已在 user_facing_fields |
| `message_template.capability_catalog.groups[].emoji` | NR (保留字面) | - |
| `message_template.capability_catalog.groups[].ucs[].short_description` | NR + TR | 已在 user_facing_fields |
| `message_template.capability_catalog.groups[].ucs[].sample_triggers[]` | NR (保留字面) + SR (触发词池) | - |
| `message_template.call_to_action` | NR + TR | 已在 user_facing_fields |
| `message_template.featured_entries[].beginner_prompt` | NR + TR | 已在 user_facing_fields |
| `message_template.more_info_hint` | NR + TR | 已在 user_facing_fields |
| `locale_rendering.*` | TR | - |
| `enforcement.*` | VF | PIN-01 检查 |

### human_summary.*

| Field | Primary Consumer | Notes |
|---|---|---|
| `persona` | NR (人设注入) | - |
| `what_i_can_do.tagline` | NR + TR | 已在 user_facing_fields |
| `what_i_can_do.use_cases[]` | NR + TR | 已在 user_facing_fields |
| `what_i_auto_fetch[]` | NR + TR | 已在 user_facing_fields |
| `what_i_ask_you[]` | NR + TR | 已在 user_facing_fields |
| `locale_rendering.*` | TR | - |

### trace_schema.*

| Field | Primary Consumer | Notes |
|---|---|---|
| `event_types[]` | EX (日志发射) + MA (审计) | - |

---

## 三、关键发现

### 发现 1：翻译遗漏 8 处

`user_facing_fields[]` 当前 12 条，但实际 user-facing 字段更多：

1. `preconditions[].on_fail`
2. `intent_router.uc_entries[].ambiguity_question`
3. `architecture.stages[].narrative.does_what/key_decisions/common_pitfalls`（3 条）
4. `constraints.{fatal,regular}[].consequence`
5. `output_validator.assertions[].failure_message`
6. `acceptance.hard_gates[].on_fail`
7. `skill_crystallization.action`

**影响**：非 en 用户触发错误/歧义时会收到英文。

### 发现 2：dead fields

- `meta.target_host` — 无消费者
- `soft_gates[].rubric` — 仅 MA（无运行时消费）

### 发现 3：双消费字段需显式拆分

- `skill_crystallization.skill_file_schema` → 主消费是 SR（通过 .skill 文件），**不是 NR**。Session 27 Fix A 就是因为编译脚本误以为它影响 NR。**建议**：v5.3 schema 为此字段加 `consumer_note: "Consumed by skill_router via emitted .skill file. NOT rendered in post_install_notice."` 注释字段，让编译和 gate 一看便知。
- `evidence_quality.user_disclosure_template` → 既是 NR 内容也是 TR 对象，天然双消费，无歧义。

### 发现 4：编译脚本职责可重构

`compile_crystal_skeleton.py` 当前按 schema 结构构建字段（I1-I8）。**建议**重构为按消费者：

```python
crystal = {
    **build_meta_archival_block(),       # MA 消费
    **build_notice_render_block(),       # NR 消费
    **build_skill_router_block(),        # SR 消费
    **build_translator_block(),          # TR 消费（生成 user_facing_fields）
    **build_executor_block(),            # EX 消费
    **build_verifier_block(),            # VF 消费
    **build_skill_emitter_block(),       # SE 消费
}
```

每个 block 构建函数内部**只**关心该消费者需要的字段。Fix A 类错位从物理上不可能发生——改 NR block 不会动 SR block。

### 发现 5：quality gate 断言可按消费者分层

`crystal_quality_gate.py` 的 G1-G10 + SA-01~18 重分组为：

- `check_notice_render()` — G9/G10 + SA-14/15/16/17 + PIN-01
- `check_skill_router()` — SA-05 (intent_router)
- `check_translator()` — LOCALE-01 + user_facing_fields 完整性
- `check_executor()` — preconditions + on_execute 链
- `check_verifier()` — OV + EQ
- `check_skill_emitter()` — skill_file_schema 合规 + 写出验证
- `check_meta_archival()` — id/version/compiled_at 格式

好处：门禁失败消息直接告诉用户 "NR 层失败"，而不是 "SA-16 失败"——用户视角更清晰。

---

## 四、v0.1 → v1.0 待决策事项

1. **dead field 处理**：`meta.target_host` 是保留还是删除？（建议保留，未来 harness/codex 可能消费；但加 `consumer: reserved_for_future`）
2. **翻译遗漏 8 处**：是否在 v5.3 一次性加入 `user_facing_fields[]`？（建议是，但需先验证 OpenClaw 翻译 20+ 字段的性能）
3. **双消费字段标注方式**：在 schema 里用新增 `consumer` / `consumer_note` 元字段（增加 schema 复杂度），还是维护一个独立的 `consumer_map.yaml`（外部映射）？（建议后者——schema 保持纯净，映射单独演进）
4. **编译脚本重构范围**：v5.3 重构 compile_crystal_skeleton.py 按消费者分 block？还是只在现有结构上加 consumer 注释？（建议渐进——先加注释和 consumer_map，重构延到 v5.4 批量编译之后）

---

## 五、下一步（Week 1 剩余）

1. Review 本文档（用户 or 独立 agent）
2. 创建 `schemas/consumer_map.yaml` — 机器可读的 field path → consumer 映射
3. 在 `crystal_quality_gate.py` 中添加 `check_translation_completeness()` — 扫描 crystal 所有字段，对标 consumer_map 中标记为 NR 的字段，验证是否都在 `user_facing_fields[]`
4. 重编 bp-009 v5.3，验证新增 8 个翻译字段后 OpenClaw 行为层变化
5. 记录 pitfalls.md P-07（如有新错位发现）

---

*v0.1 | 2026-04-19 | Post Session 27 / Fix A 分层错位根治方案*
