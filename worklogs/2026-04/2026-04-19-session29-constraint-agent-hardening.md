# Session 29 Worklog — Constraint Agent 全面加固 + SOP 验收 + 数据修复

**Date**: 2026-04-18 → 2026-04-19
**主线程**: Opus 4.7 (1M)
**触发**: 2026-04-17 停电中断批跑后，synthesis phase 暴露 7 种 LLM output shape 混乱
**结局**: 约束提取 agent 正式可上线（~155 commit，~1700 条约束数据修复，73/73 bp 清洁化）

---

## 零、Session 起点与终点

**起点**（04-17 早）：停电后重启 → synthesis `JSON extraction failed` 在连续 9 个 bp 中出现 8 次（89% 失败率）→ 手打 6 轮补丁仍不稳 → 用户决定"全面优化后再上线"。

**终点**（04-19 夜）：
- 占位符残留 `0`
- null source_blueprint_version `0`
- ev_type=source_code 指向文档 `0`
- 全角数学符号 `0`
- 单元测试 `60/60`
- Codex final review: **GO（high confidence）**

---

## 一、三阶段加固（~155 commit 全景）

### 阶段 A — 上线前 10 commit（04-18 上午）

6 个并行 sonnet audit agent 产出诊断（代码健康 / bug 对账 / 合成价值 / MiniMax 三级成本 / SOP 必要性 / 测试覆盖）→ 按 P0/P1/P2/P3 roadmap 执行：

| Commit | 要点 |
|--------|------|
| `361251c` / `a9ea4d9` | 抽取共享 `_json_recovery.py`（5 个纯函数 helper） |
| `41ef73e` | orchestrator 细化异常（原 `except Exception: pass` 吞 commit_hash 错误 → 静默丢约束） |
| `138e510` | pyproject 补 4 个内部包依赖声明 |
| **`e2dad1b`** | **synthesis prompt 加 JSON schema + few-shot + strict-JSON directive（根治 7-shape 混乱）** |
| `04f5f35` | 33 回归测试 + 5 真实 raw dump fixture |
| `fa23350` | `con_evaluate` blocking=False |
| `bc558d3` | 删死 schema + legacy 分支（-105 行） |
| `d4d900d` | 日志降级（P17/QG-0N PASS → debug） |
| `7272662` | 解除 synthesis 对 evaluate 的依赖（Codex review 发现） |

**阶段 A 结果**：批跑重启后，L2 成功率从 **2.1% → 可观水平**（首次触发即 L2 OK），`JSON extraction failed = 0` 贯穿 41-bp 批跑。

### 阶段 B — 上线后 P0+P1 5 commit（04-19 凌晨）

批跑完成（39/41，bp-127 LLM variance 瞬态、bp-111 QG-03 失败）后盘点剩余缺陷：

| Commit | 要点 |
|--------|------|
| `1d7f591` | P0.1 `consequence_kind` 缺失默认 `"bug"` + P0.2 `_recover_derive_from_raw` 的 int-iterable 双重 guard |
| `f515276` | cli.py 2 处裸吞异常细化 |
| `5ad93f6` | **瞬态失败 auto-retry 3 次机制** — manifest 加 `constraint_retry_count`，discover 只对 <3 的 failed 重新排队 |
| `157d80d` | `con_extract_rationalization` 条件跳过（finance 95% 无 document 源） |

**阶段 B 结果**：bp-127 类 LLM variance 瞬态 bug 从"彻底毁一个 bp"变"自动自愈"。

### 阶段 C — SOP 全量验收 + X/Y/Z 修复（04-19 日间）

3 个 sonnet 子代理做 73 bp **内容级 SOP 验收**：

| Agent | 范围 | 发现 |
|-------|------|------|
| Flagged (9 bp) | 有机械 QG 缺陷的 | Minor × 8 + OK × 1 |
| Borderline (12 bp) | MC/fatal_mc 偏低 | OK × 2 + Minor × 8 + Major × 1（bp-086） |
| Healthy (8 bp) | 机械 QG 全过 | **Minor × 7 + OK × 1** |
| Remaining (42 bp) | 其他 | **Critical × 5 + Major × 24** |

**关键结论**：自动 QG 过 ≠ 内容质量好。7 种系统性问题自动 QG 不能捕捉：占位符未替换、逻辑反转、伪证据、分类漂移、全角符号、重复约束、ev_type 错标。

### 阶段 C 修复三路并行（X/Y/Z）

**Agent X — 5 Critical bp 占位符清理**（5 commit，194 条 threshold）：
- `ac03849` bp-061 FinRL（34）
- `3cef315` bp-071 opensanctions（50）
- `b35675f` bp-078 fava_investor（28）
- `9840d44` bp-100 LEAN（51）
- `15ef7c1` bp-104 Engine（31）

**Agent Y — evidence_refs.type 跨 65 bp 批量修正**（65 commit，833 条）：
- 最大 bp-098 nautilus_trader（52）/ bp-121 ml-for-trading（46）/ bp-103 ArcticDB（44）
- 全部 `type="source_code"` + .md locator → `type="document"`

**Agent Z — Pipeline Patch 18 根治**（`8080f46`）：
- `_patch_resolve_placeholders` 挂在 enrich P17 后、P15（hash）前
- 从 `evidence_refs[0].path` 解析真实路径替换 `\{[a-z_]+\}`（排除 `${VAR}`）
- 无可靠路径时清空 + `machine_checkable=false`
- 2 新测试，47/47 绿

**Pipeline QG 扩充**（`5587593`）：
- QG-10 占位符检测
- QG-11 modality/consequence 逻辑反转启发式
- QG-12 evidence type/locator 一致性
- 12 新测试

### 阶段 C 数据修复 side-quests

- 去重 5 bp / 7 条重复约束
- 全角数学符号 27 bp / 182 条（`≥`→`>=` 等）
- bp-009 占位符（33） + bp-086 fatal threshold（9 补）+ C-230 逻辑反转

### 阶段 C 收官（Codex final review + 二次修复）

Codex 发现 Agent X 只覆盖 5 Critical，实际**全库仍有 452 条残余占位符跨 36 bp**，同时 2 个 manifest 的 `source_blueprint_version` 为 null/string → 下次 discover 会 TypeError 崩溃。

补救 3 路：
- `b70c463` bp-009/bp-070 manifest type 回填
- `9596583` cli.py `_safe_int` helper + `_scan_stale_projects` 防御（新增 13 测试）
- 36 bp × 1 commit 清零剩余 452 占位符（全部走"清空 + mc=false"，因为这批 bp evidence path 缺失）
- `6c310a0` 5 Critical bp 的 94 条 ev_type 补修（Y 当时跳过避冲突）

---

## 二、最终指标

| 维度 | 开 session | 收 session |
|------|----------|----------|
| synthesis `JSON extraction failed` | 89% 失败率 | 0 ✅ |
| MiniMax L2 成功率 | 2.1% | 可观水平 |
| validation_threshold 占位符 | 646+ 条残留 | 0 ✅ |
| null/string source_blueprint_version | 2 bp | 0 ✅ |
| ev_type=source_code 指向 .md | ~928 条 | 0 ✅ |
| 全角数学符号 bp | 27 bp / 182 条 | 0 ✅ |
| 约束单元测试 | 0 | 60 ✅ |
| 批跑 429 错误 | 78 次 / 4 min（5 并发） | 0（3 并发稳态） |
| 单 bp 平均耗时 | 30 min（con_evaluate 开启） | 24.8 min |

**累计 ~155 commit，~1700 条约束数据修复，73/73 bp 清洁化。**

---

## 三、方法论与方法启发

### 启发 A — 并行 sonnet 子代理极其有效

- 6 个 audit agent 并发 → 15~20 min 产出全面诊断
- X/Y/Z 三路修复并行 → 本来需要串行数小时的数据修复 30~40 min 完成

### 启发 B — 并发 agent 的 commit 交织问题

A1 + A2 并发时 commit message 发生错位（bp-118 dedup 的 message 实际 commit 了 bp-009 fix 的文件）。**教训：后续所有并发 agent 都在 prompt 里明确要求 `git add <specific files>`，禁止 `git add -A/.`。**

### 启发 C — Codex review 价值很高

独立验证 110 个 commit 时发现了 1 个真 P0 blocker（manifest type 不一致 → TypeError）和 452 条残余占位符（Agent X 只做了 5 bp 的子集）。如果没跑 Codex，这两个问题会在下次 discover 时才暴露。

### 启发 D — 自动 QG 过 ≠ 内容质量好

spot check 8 个"健康"bp → 7/8 实际 Minor。QG-01~09 统计门槛覆盖不到语义层问题。QG-10/11/12 补入 pipeline 是下次 audit 的护城河。

### 启发 E — MiniMax prompt 加固的根因效果

一个 prompt 加 JSON schema + few-shot + "no markdown" 指令 → 从 7 种 shape 发散压到几乎不触发 L3。老 prompt 的缺失比想象的更致命。

---

## 四、未决事项（backlog）

- QG-11 中文关键词词表扩充（英文/中文双语）
- QG-12 代码后缀扩展（`.php`, `.lua`, `.m`）
- 5 个 handler 单元测试（derive / audit / synthesize / synthesis / postprocess）
- **蓝图层 / 晶体层审查**（本次 scope 只在约束，盲区未覆盖）
- bp-111 ccxt QG-03 策略（接受现状 / 调阈值 / 重跑碰运气）
- bp-127 / bp-111 两个"真正失败"的 bp 留在 `failed` 状态（已修瞬态，bp-127 用 probe 重跑成功，bp-111 是质量门问题）

---

## 五、Session 复盘

**最大收益**：从"手打 6 轮补丁仍不稳"到"整个约束层可生产上线"，用了 ~18 小时 session 时间。关键拐点是**用户要求暂停做全面优化**——否则会继续打补丁停不下来。

**最大风险**：`~155 commit` 规模下，sonnet 子代理的并发 commit 一度让 git log 可读性下降。未来再做大 session 应要求每个并发 agent 明确分文件域。

**下次 session 可以立即做**：蓝图/晶体层的同等规模验收。预计会找到类似比例的内容缺陷（证据错标、模糊词、占位符），需要同类工具链批量清理。

---

*最后更新: 2026-04-19*
