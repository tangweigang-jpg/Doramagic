# bp-073 Health Checklist

**日期**: 2026-04-19
**状态**: 结论性 — 数据已落盘，无需再跑
**对象**: `finance-bp-073--ledger`（Formance Ledger，Go 项目，commit `96c923f`）
**触发问题**: 为什么 73 个 finance 蓝图里只有 bp-073 的 `evidence_verify_ratio = 1.0`？

---

## 1. 结论（一句话）

bp-073 是唯一一个 **LLM 给每条 BD 都写出了真实的 `path:line(symbol)` 证据，并且这些引用在仓库里都能校验通过** 的蓝图。其他 72 个蓝图里，LLM 或者写了 `N/A:0(see_rationale)` 类占位符，或者编造了不存在的文件/行号/符号。

**健康度不是结构指标，是证据诚实度。**

---

## 2. 73 个蓝图 `evidence_verify_ratio` 分布

| 区间 | 数量 | 代表 |
|------|-----:|------|
| `≥ 0.9` | **1** | bp-073 ledger (1.00) |
| `0.7 – 0.9` | 3 | bp-050 skorecard (0.79), bp-103 ArcticDB (0.79), bp-122 ta-python (0.73) |
| `0.5 – 0.7` | 18 | bp-072, bp-111, bp-098 … |
| `0.3 – 0.5` | 29 | 大多数 |
| `< 0.3` | 22 | bp-062 ifrs9 (**0.00**), bp-105 open-climate (0.01), bp-101 FinancePy (0.03) |

---

## 3. 健康信号 checklist（4 项核心）

对一个 BD 列表，**四条全绿** 才算进入 bp-073 健康区。

### C1. Evidence 字段写了真实路径、行号、符号

**绿**（bp-073 BD-001）:
```
evidence: 'internal/machine/vm/machine.go:197(opcodes)'
```

**红**（bp-062 BD-001）:
```
evidence: 'N/A:0(see_rationale)'
```

**检测**: evidence 不匹配 `^N/A:|:0\(see_` 且符合 `[^:]+:\d+\(\w+\)` 模式。

### C2. Evidence 在仓库里能找到

evidence verifier（`blueprint_enrich.py` P5.5）跑 exact-match + basename rglob fallback，
绿 = verified，红 = invalid。

bp-073: 47/47 verified、0 invalid；bp-098 nautilus: 41 verified、**62 invalid**（幻觉行号）。

### C3. BD 数量 ≥ 仓库实际决策密度

- bp-073: 99 BDs（Go 项目 ledger，核心 engine 精细）
- bp-062 ifrs9: BD 全部 evidence=`N/A` → LLM 认输了，没真的读代码
- bp-105 open-climate: evidence 1% → LLM 在 90 多个 BD 里只有 1 个是看过代码的

**启示**: 如果 LLM 给出 ≥50 条 BD 但 evidence 几乎全 `N/A`，说明它在**编内容**而不是**读代码**。

### C4. `_enrich_meta.evidence_verified ≥ 30` 且 `evidence_invalid ≤ 5`

绝对量也要看。bp-073: verified=47, invalid=0。
高 ratio 但低 verified 量（例：verified=3, invalid=0, ratio=1.0）不可信，是样本太小。

---

## 4. 结构信号（辅助，bp-073 同样达标）

| 信号 | bp-073 | 说明 |
|------|--------|------|
| `stages` 数 | **10** | 有结构，不是扁平 |
| `business_decisions` 数 | **99** | 决策密度高 |
| `global_contracts` 存在 | ✅ | 接口层显式定义 |
| `data_flow` 存在 | ✅ | 数据流显式建模 |
| `execution_paradigm` 存在 | ✅ | 执行模式显式标注 |
| `relations` 真实非 pending | ✅ | P12 已连接 |
| `evidence_coverage_ratio` | 0.48 | 只有一半 BD 有 evidence — 但**写了的那些全真** |

**注**: bp-073 `resources` 只有 21 条（Go 项目天然少 Python 依赖），`use_cases` 为 0，`audit_checklist_summary.coverage` 只有 54% —— 这些都不是健康信号。**evidence 诚实度才是**。

---

## 5. 三类典型失败模式（来自其他 72 个蓝图）

### 模式 A：LLM 全部 `N/A`（evidence_verify_ratio ≈ 0）

代表：bp-062 ifrs9 (0.00)、bp-105 open-climate (0.01)、bp-101 FinancePy (0.03)

**根因**: LLM 被要求 99 条 BD 时产能不够，直接用 `N/A:0(see_rationale)` 交差。
**处方**: 减少单次 BD 批量到 20–30，或者 prompt 加硬约束"没证据就 skip，不要 N/A"。

### 模式 B：LLM 编造行号/文件名（invalid 占比 > 30%）

代表：bp-098 nautilus (ratio=0.40, invalid=62)、bp-060 AMLSim (ratio=0.10)

**根因**: LLM 记得看过某文件但行号是瞎猜的。
**处方**: 抽取前把 repo_index（真实行号索引）作为 prompt 的强约束上下文，并且在 BD 生成时允许只给 `path:symbol` 不给 `:line`，由 verifier 后置定位。

### 模式 C：repo_index 为空（Go / Rust / 非 Python 项目）

代表：bp-073 本身（repo_index.files=0）—— 但 **bp-073 反而健康**，因为 LLM 直接读了源码。

**启示**: repo_index 不是必需品；verifier 的 basename rglob fallback 能救非 Python 项目。
**处方**: 把 bp-073 的 Go 项目抽取流程单独记下来作为对照样本。

---

## 6. 行动建议（让未来抽取进入健康区）

按优先级：

1. **Prompt 硬约束**：worker prompt 加一条"如果找不到 `path:line(symbol)`，直接跳过该 BD，不要写 `N/A`"
2. **Gate 阻断**：`blueprint_quality_gate.py` 加一条：`evidence_verify_ratio < 0.5` 或 `evidence_invalid > 20` 时 blueprint 不能进 LATEST.yaml
3. **分批抽取**：99 条 BD 太多，一次 30 条 × 3 轮比一次 99 条质量高
4. **非 Python 项目白名单**：Go/Rust 项目跳过 repo_index 依赖，直接让 verifier 做 basename rglob
5. **verifier 语义对齐**：目前 verifier 对 `.py` 文件做严格 AST 检查，对非 Python 只查 file+line。这造成 Go/Rust 项目"免检通过"的假象。应该补 Go/Rust 的轻量 AST 或至少做 `(symbol)` grep 验证

---

## 7. Semi-auto 追溯结果（2026-04-19 补充）

之前假设 bp-073 `extraction_methods: ['semi_auto']` 暗示人工介入。**实测证明该假设错误**：

- 全部 73 个 finance 蓝图的 `extraction_methods` 都是 `['semi_auto']`
- `blueprint_enrich.py:208` 把 **默认值** 硬编码为 `['semi_auto']`：任何没写 extraction_methods 的 bp 都会被填这个值
- 该字段对 bp 间差异毫无信息量，不能当健康信号用

**bp-073 真正"健康"的机制（修正理解）**：

1. bp-073 是 Go 项目 (`ledger`)
2. LLM 给出的 evidence 大多形如 `internal/machine/vm/machine.go:197(opcodes)`
3. verifier P5.5 (`_patch_evidence_verify`) 对 `.py` 之外的文件**不做 symbol 验证**（见 L1183 `if fn_name and file_path.endswith(".py")`）
4. 结果：Go 文件只要 file 存在 + line 在范围内就自动 `verified++`，符号名 `(opcodes)` 是否真的在那行**根本没检查**
5. bp-073 verified=47、invalid=0 是验证器**结构性宽松**造成的，不是 BD 质量真的比其他高

**对比 bp-062 为什么输**：
- bp-062 是 Python 项目（含 `.ipynb` 和 `.py`）
- 但 bd_list.json 里 117/117 都是 `N/A:0(see_rationale)` —— 连最终 JSON 阶段都丢了证据
- 奇怪现象：`step2c_business_decisions.md` 里还有真实 refs 如 `PD/README.md:21-26` —— md 时间戳 10:09 早于 bd_list.json 10:18，说明 `bp_synthesis_v5` 应该要重写 md（见 `blueprint_phases.py:2412`），但 md 没被更新
- 结论：bp-062 的 LLM 原始 md 有证据，但进入 `BDExtractionResult` 的路径上 evidence 全丢了。真正的 bug 在 step2c.md → BDExtractionResult 的解析/批处理链路，**不是 LLM 质量问题**

---

## 8. 未来跟踪（修订后）

- [x] 追溯 bp-073 的 semi_auto 介入点 —— **已结论：无介入，是默认值**
- [x] 修 P5.5 verifier：Go/Rust 文件也做 `(symbol)` grep —— **已修复 `88365de`**
- [x] 修 bp-062 类丢失：查 `bd_list.json` 构建路径 —— **已定位为 L3 recovery 默认 N/A，`4cb61b7`/`28d5e37`/`d211c4e` 三连修**
- [ ] Gate 阻断上线后，重跑 bottom-5，看 73 个蓝图 verify_ratio 是否能提升
- [x] 对比"真 Python 严格检查" vs "Go 宽松免检" —— **已验证：bp-073 1.00 → 85.87%（新符号检查抓到 3 个真幻觉），bp-050 保持 78.57%。bp-073 仍排第一但"100% 神话"已破**

---

## 9. Codex adversarial 验证史（2026-04-19 附录）

从 checklist 发现的 5 个行动项出发，到最终修复全部落盘并通过外部 LLM 审查，本附录记录真实迭代：

### 9.1 修复路径（Commit 链）

| # | Commit | 性质 | 关键内容 |
|---|---|---|---|
| 1 | `b236423` | 观察 | 本 checklist 初版 —— 提出"evidence 诚实度"假设 |
| 2 | `3294715` | 纠正 | 澄清 `semi_auto` 是默认值而非人工介入信号；首次发现 P5.5 verifier 对非 Python 的宽松 bug + bp-062 类 step2c.md ↛ bd_list.json 证据丢失 |
| 3 | `88365de` | 修复 | P5.5 verifier 对非 Python 文件做 `(symbol)` grep（±5 行窗）。bp-073 因此从 100% → 93.62%，抓到 3 个真幻觉：`machine.go:197(opcodes)`、`log_process.go:97(SchemaEnforcementMode)`、`chart.go:109(Pattern)` |
| 4 | `4cb61b7` | 修复 | 新 P5.3 patch：enrich 阶段从 `step2c_business_decisions.md` 按 content 前缀回填 N/A evidence（后置补丁）|
| 5 | `28d5e37` | 修复 | 上游根治：在 `bp_synthesis_v5` + `synthesis_v9` 的 5+4 处 L3 recovery 默认化 `N/A` 之前先查 step2c map |
| 6 | `38b10ef` | 落盘 | 73 蓝图首次 re-enrich。bp-062 **0% → 79.71%**，回填 1046 条 refs，均值 +6pp |
| 7 | `d211c4e` | 修复 | Codex adversarial 审查 `28d5e37` 给出 3 个 finding，全部封堵 |
| 8 | `150701c` | 落盘 | 73 蓝图再次 re-enrich，验证 7 号修复无回归 |

### 9.2 Codex 两次审查

**第一次（`/codex:review` 工作树，50s）**
- 目标：工作树
- 产出：只检测到本地 `.claude/scheduled_tasks.lock`（housekeeping，与 P2 无关）
- 结论：不能审已提交 commit —— 暴露 `/codex:review` 对历史修复的盲区

**第二次（`/codex:adversarial-review` 指定 commit，~2min）**
- 目标：`commit 28d5e37` + 聚焦 (A)(B)(C) 三点
- Verdict：**needs-attention**
- 发现 3 个真 bug：

| Finding | 优先级 | 问题 | Codex 建议 |
|---|---|---|---|
| #1 | high | v9 pipeline 中 step2c.md 写入 **晚于** local/global synthesis → 新运行 map 永远空 | 改用 worker candidate evidence 或在 synthesis 前写入 |
| #2 | high | 正则 `_STEP2C_ROW_RE` 不处理 `\|` 转义；`_bd_to_markdown` 会把 `\|` 写进 cell → 公式型 BD 列错位 | 换字符解析器 |
| #3 | medium | `_recover_bd_evidence` 只在 `not evidence` 时触发 → `"N/A:0(see_rationale)"` 是 truthy，不被重写 | 加 `is_missing_evidence()` helper 集中判 sentinel |

### 9.3 修复验证

`d211c4e` 逐一封堵：
- **#1**: 新 `load_worker_candidate_evidence_map()` 读 `worker_*.json` 的 `BDCandidate.evidence`（这些文件在 synthesis 前必然存在）。v9 三 handler 用 `{worker, **step2c}` 合并，step2c 优先 worker 兜底
- **#2**: `_split_md_row()` 字符解析器，honor `\|` 转义并 unescape cell 内容
- **#3**: `is_missing_evidence()` 认 `empty / "-" / "—" / "N/A*" / "none" / "null"`，所有 L3 recovery 路径统一调用
- +15 pytest 测试全部通过；`150701c` 再跑 73 蓝图 reenrich，分布完全相同（无回归）

### 9.4 元启示

1. **Codex adversarial review 值回票价**：`/codex:review`（非对抗）只能审工作树且易漏；`/codex:adversarial-review + commit hash + focus text` 能精准打点并抓到非平凡 bug（v9 时序竞态 #1 几乎不可能靠人工发现）
2. **正则 vs 解析器的界线**：一旦有转义语义，正则立刻失效。`_STEP2C_ROW_RE` 是"看起来对"的典型案例 —— 覆盖 90% 输入但剩下 10% 默默漏数据
3. **"看起来修好了"≠ 修好了**：P2 提交（`28d5e37`）PR-level 测试全绿（120 passed），但 Codex 发现它在 v9 新运行里**完全无效** —— 提醒我们**必须跑真实 pipeline 端到端**而不是只看 unit test
4. **Sentinel 语义统一的价值**：`N/A:0(see_rationale)` 在 7 个地方被硬编码，`is_missing_evidence` 把这个"语义缺失"的概念提纯到一个函数，未来所有 L3/backfill/verify 改动都能引用，避免重复犯错

---

**相关文件**:
- `packages/extraction_agent/doramagic_extraction_agent/sop/blueprint_enrich.py`（`is_missing_evidence`、`_split_md_row`、`load_step2c_evidence_map`、`load_worker_candidate_evidence_map`、P5.3、P5.5）
- `packages/extraction_agent/doramagic_extraction_agent/sop/blueprint_phases.py:1567`（`_recover_bd_evidence` + 3 个 v5 L3 call sites）
- `packages/extraction_agent/doramagic_extraction_agent/sop/synthesis_v9.py`（`_coerce_bd_dict` + 3 个 v9 handler 的 map 加载）
- `packages/extraction_agent/tests/test_blueprint_enrich.py`（`TestIsMissingEvidence`、`TestSplitMdRow`、`TestLoadWorkerCandidateEvidenceMap`、`TestPatchEvidenceBackfillFromMd`、`TestPatchEvidenceVerifyNonPython`）
- `knowledge/sources/finance/finance-bp-073--ledger/blueprint.v1.yaml`（对照样本）
- `_runs/finance-bp-073/artifacts/step2c_business_decisions.md`（LLM 原始 BD 表）
- `_runs/finance-bp-062/artifacts/step2c_business_decisions.md`（证据丢失现场）
