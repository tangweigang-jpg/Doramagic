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
- [ ] 修 P5.5 verifier：Go/Rust 文件也做 `(symbol)` grep（grep symbol in line ±5 window），避免非 Python 项目免检
- [ ] 修 bp-062 类丢失：查 `bd_list.json` 构建路径为何丢 evidence。怀疑 `_synthesize_bd_types_*` prompt 或 batching 把 evidence 字段 reset 成 N/A
- [ ] Gate 阻断上线后，重跑 bottom-5，看 73 个蓝图 verify_ratio 是否能提升
- [ ] 对比"真 Python 严格检查"下的 bp-050 (0.79) vs "Go 宽松免检"的 bp-073 (1.00) —— 实际质量差距可能被 verify_ratio 夸大

**相关文件**:
- `packages/extraction_agent/doramagic_extraction_agent/sop/blueprint_enrich.py:1116`（P5.5 verifier，L1183 是语义分叉点）
- `packages/extraction_agent/doramagic_extraction_agent/sop/blueprint_enrich.py:208`（semi_auto 默认值来源）
- `packages/extraction_agent/doramagic_extraction_agent/sop/blueprint_phases.py:2412`（synthesis 覆盖 md）
- `knowledge/sources/finance/finance-bp-073--ledger/blueprint.v1.yaml`（对照样本）
- `_runs/finance-bp-073/artifacts/step2c_business_decisions.md`（LLM 原始 BD 表）
- `_runs/finance-bp-062/artifacts/step2c_business_decisions.md`（证据丢失现场）
