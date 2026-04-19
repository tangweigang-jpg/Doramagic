# Session 28 Worklog — v5.3 Consumer-Indexed Crystal Schema

**Date**: 2026-04-19
**主线程**: Opus 4.7 (1M)
**前置**: Session 27 v5.2（commit `7ec70de`，8.72/10），08:46 OpenClaw 实测发现 Fix A 行为层不可见
**核心矛盾**: 晶体字段作用域隐式 → 改错字段还以为 host 忽略

---

## 一、背景：Session 27 Fix A 失败的根因

Session 27 v5.2 Fix A 动态化 `skill_crystallization.skill_file_schema`（name/keywords/guards），期望 OpenClaw Notice 从通用 "ZVT v5.2 Skill" 改为 UC 专属 "Actor Data Recorder"。08:46 实测发现字节级部署一致但 Notice 文案未变。

**根因**：`skill_file_schema` 的真实消费者是 **skill_router（SR，通过 .skill 文件）**，不是 **notice_render（NR，通过 post_install_notice.message_template）**。两个字段作用域独立，改错字段。

**更深层问题**：Schema 按作者视角（I1-I8 不变式）组织字段，没有显式标注每个字段的消费者。类似错位会再发。

---

## 二、v5.3 设计：消费者显式化

### 2.1 7 个消费者（`schemas/consumer_map.yaml` 定义）

| 缩写 | 消费者 | 触发 |
|---|---|---|
| NR | notice_render | skill_installation_complete |
| SR | skill_router | every_user_message |
| TR | translator | first_user_msg + non-en locale |
| EX | executor | execute_trigger_matched |
| VF | verifier | during/post execute |
| SE | skill_emitter | all_hard_gates_passed |
| MA | meta_archival | compile + audit |

每个 schema 字段标注主消费者；双消费字段显式列出（如 `skill_crystallization.action = [SE, NR, TR]`）。

### 2.2 新增 SA-19 translation_completeness

读 `consumer_map.yaml` 的 `user_facing_fields_expected[]`（所有 NR+TR 字段），对比 `crystal.locale_contract.user_facing_fields`，缺失任一条 → FAIL。这是 Fix-A 类字段作用域错位的结构性守卫：任何未来改动若把一个 NR 字段加进 schema 但忘记在 user_facing_fields 里声明，SA-19 立即失败。

### 2.3 user_facing_fields 12 → 26

补齐之前遗漏的 8 处翻译目标：
- `preconditions[].description` + `.on_fail`（非 en 用户看不懂失败信息）
- `intent_router.uc_entries[].name` + `.ambiguity_question`
- `architecture.pipeline` + `stages[].narrative.{does_what, key_decisions, common_pitfalls}`
- `constraints.{fatal,regular}[].consequence`
- `output_validator.assertions[].failure_message`
- `acceptance.hard_gates[].on_fail`
- `skill_crystallization.action`

### 2.4 废弃字段（v5.4 移除）

- `meta.target_host` — 无运行时消费者
- `acceptance.soft_gates[].rubric` — 仅 MA（审计用）

---

## 三、实现改动清单

| 文件 | 改动 |
|---|---|
| `schemas/consumer_map.yaml` | 新建（单一真源） |
| `schemas/crystal_contract.schema.yaml` | $id v5.2→v5.3；title；sop_version const；user_facing_fields default 12→26；`target_host` + `soft_gates[].rubric` 标 deprecated；`skill_file_schema` 加 x-consumer 注释 |
| `scripts/compile_crystal_skeleton.py` | `build_locale_contract()` default 26 条；sop-version 默认 crystal-compilation-v5.3；version fallback v5.2→v5.3 |
| `scripts/crystal_quality_gate.py` | 新增 `sa19_translation_completeness()`；report header v5.2→v5.3；_SA_REGISTRY 扩到 19 条 |
| `sops/finance/crystal-compilation-sop.md` | v5.2→v5.3；新增 §v5.3 消费者显式化章节；SA-19 说明；变更历史 +v5.3 条目 |
| `sops/_template/crystal-compilation.tmpl.md` | 与 finance SOP 同步 |
| `Makefile` | SOP_VERSION 默认 crystal-compilation-v5.3 |
| `knowledge/sources/finance/finance-bp-009--zvt/finance-bp-009-v5.3.seed.yaml` | 新编 142,943 bytes / 3244 行 |

---

## 四、验证结果

### 4.1 Gate 全 PASS

```
Crystal Quality Gate v5.3 — Report
Schema Validation: ✓
Coverage: BD 164/164 | UC 31/31 | Constraints 147/147 (27 fatal + 120 regular)
Semantic Assertions: SA-01 ~ SA-19 全 ✓
SA-19 translation completeness: ✓ (all 26 NR+TR fields declared as user-facing)
门禁总判定: ✓ PASS
```

### 4.2 与 v5.2 的字节对比

| 指标 | v5.2 (`7ec70de`) | v5.3 | 变化 |
|---|---|---|---|
| seed.yaml bytes | 142,350 | 142,943 | +593 |
| seed.yaml lines | 3230 | 3244 | +14 |
| user_facing_fields | 12 | 26 | +14 |
| SA 断言数 | 18 | 19 | +1 (SA-19) |

增量主要是 user_facing_fields 列表扩容 14 条 → YAML 体积 +593 bytes。

### 4.3 首轮 gate 失败 + 自修复

首次运行 SA-19 失败：consumer_map 中 `human_summary.what_i_can_do.use_cases` 等 3 条未带 `[]` 后缀，与编译脚本输出的 `[]` 形式不匹配。修正 consumer_map 后全 PASS。**这正是 SA-19 预期捕获的一类错位**——路径表达不一致导致翻译范围声明失效。说明守卫有效。

---

## 五、未做但应做（v5.3.1 / v5.4）

1. **compile 脚本按消费者分 build block 重构**（v5.3.1）
   - 当前 compile 仍按 schema 结构组装字段。彻底根治 Fix-A 需要重构为 `build_meta_archival_block` / `build_notice_render_block` / ... 7 个函数。
   - 本次 session 用 SA-19 作为行为层守卫先行，结构重构延后。
2. **quality_gate 按消费者分层重组**（v5.3.1）
   - 让失败消息从 "SA-16 FAIL" 升级为 "notice_render 层失败：缺 featured_entries"
3. **删除废弃字段**（v5.4）
   - `meta.target_host` + `acceptance.soft_gates[].rubric`
4. **schema 全字段 x-consumer 注释**（v5.4）
   - 当前只在 Fix-A 风险字段（`skill_file_schema` 等 3 处）注释。v5.4 全面铺开。

---

## 六、OpenClaw 行为层预期

v5.3 seed 相对 v5.2：
- 文件字节层：+593 bytes，user_facing_fields 多 14 条
- Host 行为层预期：非 en 用户触发 precondition 失败 / OV 失败 / constraint violation 时，**错误文案自动翻译成用户 locale**（之前是英文）。这不是一个"新能力"，而是"原本应该有但因字段路径声明遗漏导致的缺陷补齐"。

---

## 七、Pitfalls 补录

### P-07（拟）：consumer_map 路径表达必须与 compile 脚本 1:1 匹配

- 数组字段统一用 `[]` 后缀，不论是在 schema default、consumer_map expected、还是 compile 输出
- SA-19 用 set diff 严格匹配，任何大小写/后缀/空格差异都会失败
- 已记入本 session 首轮 gate failure

---

## 八、一句话总判定

**Session 27 发现的"字段作用域错位"在 Session 28 被 v5.3 消费者显式化根治**：consumer_map.yaml 是单一真源，SA-19 是结构守卫，user_facing_fields 12→26 是并发修补的 8 处翻译漏洞。代价是把"字段按作者视角"的心智模型升级为"字段按消费者视角"——这一改变的长期价值远超本次 12 条字段的补录，因为它让未来所有新增字段都必须显式回答"谁消费这个字段"这个问题。

---

*v1.0 | 2026-04-19 | Session 28 | 主线程 Opus 4.7 (1M) | 无子代理*
