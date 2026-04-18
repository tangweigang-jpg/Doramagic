# Session 22: Finance 蓝图库 Wave3 恢复 → Wave6 扩展 + 两个 Agent Bug 定位修复

**日期**: 2026-04-17 晚 → 2026-04-18 上午（~13 小时）
**上下文**: Session 开始时 wave3 批次因停电中断（bp-097 OpenBB 被截停在 synthesis 阶段）。本 session 先恢复中断、继续补全规划、发现并修复两个 agent 级 bug、扩展知识库到 73 个 finance 蓝图。

---

## 一、成果总览

| 项 | 数值 |
|----|------|
| **finance 蓝图**（session 开始 → 结束） | 48 → **73** |
| **最终验收** | 56 PASS / 17 WARN / **0 FAIL** |
| **git commits** | **7 个**（全部 lint + typecheck + 前置 hook 通过） |
| **Agent bugs 定位并修复** | **2 个**（`bp_assemble` placeholder / `evidence verifier` false positive） |
| **回归测试** | **23 个** 新增（覆盖两个 fix） |
| **新增 repos 克隆** | **22 个**（Wave 4/5/6 候选 + 替代品） |

---

## 二、时间线 + 7 个 Commit

| 时间 | Commit | 内容 |
|------|--------|------|
| 15:07–19:07 | `e41a30f` | **Wave 3 resume**（bp-097~104 8 项）+ bp-068 xalpha 补提取 + **bp_assemble placeholder bug 修复**（代码 + 数据 patch bp-062/079/102） |
| 20:38–23:03 | `84d69ed` | **Wave 4** 6 项（open-climate-investing, pyfolio-reloaded, finmarketpy, cryptofeed, mlfinlab, Riskfolio-Lib）—— 填补 ESG/绩效归因/宏观/加密/ML/风险平价 6 个稀薄子域 |
| 23:20 | `5dd354f` | bp-115 mlfinlab UC=1 判为 **upstream 限制**（商业化后 GitHub 公开仓库是 shell，无 examples/notebooks） |
| 23:29–06:51 | `1c356f0` | **Wave 5+6 合并批次** 19 项（通宵跑）+ bp-116 FinRL-Meta + bp-126 lifelines recovery reruns → 73 蓝图 |
| 08:30 | `900af46` | **evidence verifier 两处修复**：non-identifier fn_name 跳过 exact-match + basename rglob fallback |
| 08:50 | `d9e0d31` | bp-118 / bp-119 重跑验证 verifier 修复：bp-119 invalid 83.6% → 0.8%，bp-118 57.7% → 18.9% |
| 09:00 | `0e4d097` | **23 个回归测试**（12 + 11 分别覆盖 bp_assemble 和 verifier），0.18s pytest 通过 |

---

## 三、两个 Agent Bug 的根因 + 修复

### Bug #1：`bp_assemble` placeholder（Wave 3 期间发现）

**现象**：3 个项目（bp-062/079/102）的 `blueprint.v1.yaml` 有完整 BDs（115-189 条），但 `id` 字段为 `"placeholder"`、`stages=[]`。

**根因链**：
1. `_assemble_instructor_handler` 调用 `run_structured_call`
2. L2 LLM 输出 JSON 结构残缺（缺 name/applicability/stages 某些顶层字段）
3. Pydantic validation error → L3 recovery
4. L3 对 raw text 做 `yaml.safe_load`，截断的 JSON 让 yaml scanner 失败
5. handler 返回 `PhaseResult(status="error")`，不写 blueprint.yaml
6. `executor.py:597-629` 检测到 artifact 缺失 → 写 placeholder

**修复**（3 处）：
- `blueprint_phases.py`：L3 recovery 三层降级（`json.loads` → `yaml.safe_load` → 新增 **truncate-to-last-complete-stage 抢救函数**，depth 计数器 + 字符串内部跳过，从截断 JSON 中抽 stages，正则补 name/applicability）
- `executor.py`：placeholder 对 `blueprint.yaml` 嵌入真实 `state.blueprint_id` + `_assemble_failed: true` 哨兵（避免 quality gate 误报 passed）
- 数据恢复：从 `_runs/finance-bp-XXX/artifacts/assemble_raw.txt` 为 062/079/102 精确 patch（9/10/15 stages + 115/123/189 BDs 都保留）

### Bug #2：evidence verifier false positives（Wave 5+6 验收时发现）

**现象**：bp-119 transitionMatrix 134 BDs 中 112 条被标 invalid（83.6%），bp-118 FinanceToolkit 175 中 101 条被标 invalid（57.7%）。

**根因**（sonnet 子代理 4 步诊断）：
- **bp-119 (根因 C)**：LLM 把 `evidence` 的 `(fn_name)` 字段填成自然语言描述（`"warning docstring"`）或代码片段（`"etm[:, :, 0] = np.eye(state_dim)"`）。文件+行号 100% 正确，但 `fn_name in file_text` exact-match 对非标识符必然失败。
- **bp-118 (根因 B + C 混合)**：约 75% 是 LLM 丢失路径目录前缀（`black_scholes_model.py` vs 真实 `financetoolkit/options/black_scholes_model.py`），25% 是真 LLM 幻觉。

**修复**（`evaluate_v9.py` 2 处）：
- **Fix 1**：当 `fn_name` 含空格/逗号/方括号/等号/冒号/括号/反斜杠时，判为非合法标识符，跳过 exact-match（文件+行号已验证）
- **Fix 2**：当 `repo_path / file_rel` 不存在时，用 `Path(file_rel).name` 对 repo 做 `rglob` 搜索；唯一匹配则接受该路径继续验证；0 或 2+ 匹配保持 FILE_MISSING（note 字段记录 glob 匹配数便于诊断）

**验证结果**（重跑两个项目）：
| 项目 | invalid 率（前） | invalid 率（后） | 降幅 |
|------|-----------------|-----------------|------|
| bp-119 | 83.6% | **0.8%** | 几近清零 |
| bp-118 | 57.7% | **18.9%** | 减半以上（残留的 28 条是真 LLM 幻觉） |

---

## 四、Wave 4/5/6 子域覆盖成果

### Wave 4（bp-105~117，6 项，填补 ABSENT/THIN）
| 子域 | 前 | 后 | 项目 |
|------|-----|----|------|
| ESG / 碳因子 | **ABSENT** | ADEQUATE | bp-105 open-climate-investing |
| 绩效归因 | **ABSENT** | ADEQUATE | bp-106 pyfolio-reloaded |
| 宏观多资产 / FX | THIN | ADEQUATE | bp-108 finmarketpy |
| 加密行情 | THIN | **GOOD** | bp-110 cryptofeed（UC 40 条） |
| 金融 ML | THIN | ADEQUATE | bp-115 mlfinlab（WARN upstream） |
| 风险平价 | THIN | ADEQUATE | bp-117 Riskfolio-Lib（BDs 162 条） |

### Wave 5+6（bp-107~130，19 项，合并批次通宵跑）
- **小型工具库**（empyrical / bt / openLGD / edgar-crawler / alphalens / py_vollib 等）：都稳定 PASS/WARN
- **大型项目**：ccxt（1334 py 文件）38min 完成 UC 100 条 PASS；FinRL-Meta / beancount / tensortrade 也都按时完成
- **QuantLib-SWIG**：衍生品/固收黄金标准入库（137 BDs / UC 35 条 / 5 stages）

### Harness failover 机制实战验证
Wave 5+6 期间 MiniMax 触发 5h 限流窗口，harness 自动把 worker 切换到 glm-5 继续跑，批次零中断完成。

---

## 五、被诊断为 non-agent 问题的项目

| 项目 | 问题 | 结论 |
|------|------|------|
| `bp-115 mlfinlab` | UC=1（仅找到 docs/conf.py） | **upstream 限制**：Hudson & Thames 已商业化，GitHub 只留 public-facing shell，无 examples/notebooks/tests |
| `bp-066 wealthbot` | evidence 接地率 7% → 24%（重跑后仍偏弱） | **项目语言限制**：PHP 项目，agent indexer 目前主要面向 Python |
| `bp-009 zvt` | 使用 v3~v17 老版本命名 | v7 时代遗留，验收时读 `blueprint.v17.yaml` |

---

## 六、回归测试（Commit 0e4d097）

**23 个 pytest 用例，0.18s 通过**，防止未来回归：

### `test_blueprint_phases_assemble.py`（12 个）
- `_extract_stages_from_truncated_json` 8 个：截断恢复、完整解析、无 stages key、字符串内部大括号、转义引号、空数组、单 stage、深嵌套
- placeholder blueprint.yaml 4 个：真 blueprint_id、`_assemble_failed` 哨兵、写盘、质量门可检测

### `test_evaluate_verifier.py`（11 个）
- Fix 1 非标识符 fn_name skip 6 个：空格/逗号/方括号/冒号/反斜杠跳过 + 真标识符仍检查
- Fix 2 basename rglob fallback 5 个：唯一匹配接受 / 多匹配拒绝 / 零匹配拒绝 / 正确前缀不触发 / T-type BD 跳过

**小 refactor**：`_extract_stages_from_truncated_json` 从嵌套闭包提到 module-level，行为不变（仅删除内层 `import as _json2/_re2` 别名），使单测可直接 import。

---

## 七、新增记忆（下次 session 可读）

- `project_bp_assemble_placeholder_bug.md` — bug 完整链路 + 3 处修复点 + 恢复方法论
- `project_doramagic_sources_layout.md` — `knowledge/sources/` 成为唯一有效目录，旧 `knowledge/blueprints/finance/` 废弃

---

## 八、遗留 / 下一步

### 立刻可做
1. **Wave 5+6 残留 WARN 的 evidence 严重失效项目**：少数项目还有 30%+ invalid（已修复两类问题后），需判断是否还需进一步 prompt 调教
2. **constraint_agent 批量对 73 蓝图提取约束**：目前 73 个蓝图都是 `--skip-constraint` 跑出来的，约束采集是下一关
3. **Wave 7 规划**：如果要继续扩张蓝图库，需要新一轮用户需求驱动的选样（本 session 填完了主要子域缺口，新增更多可能需要更细分的需求驱动）

### 需讨论
- **UC entry-point discovery 的泛化能力**：本 session 发现 mlfinlab / beancount / empyrical 等小项目或文档驱动项目，UC 抓取困难。是 agent 问题还是项目类型问题，值得下次专项分析
- **evidence verifier 的 `fn_name` 语义契约**：是否要在 prompt 里明确告诉 LLM `(fn_name)` 字段**必须是合法标识符**？这能从源头减少需要 verifier fallback 的情况

---

## 九、Commit 哈希参考

```
0e4d097 test(extraction): regression tests for bp_assemble + verifier fixes
d9e0d31 feat(blueprints): bp-118 + bp-119 reruns validate verifier fix
900af46 fix(evaluate): evidence verifier — non-identifier fn_name + basename fallback
1c356f0 feat(blueprints): Wave 5+6 — 19 extractions + 2 reruns → 73 total
5dd354f docs(status): annotate bp-115 mlfinlab UC=1 as upstream limitation
84d69ed feat(blueprints): Wave 4 — 6 new extractions + STATUS.md update
e41a30f feat(blueprints): patch placeholder bug + bp-068 xalpha + STATUS.md log
```

---

**结束时间**: 2026-04-18 ~09:00  
**累计工时**: ~13h（含通宵批次后台跑，有人介入的活跃时间 ~6h）
