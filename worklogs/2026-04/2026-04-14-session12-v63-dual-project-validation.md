# 工作日志：v6.2→v6.3 双项目全自动提取验证

> 日期：2026-04-14
> 会话：session 12（约 3 小时）
> 目标：修复 bp-050 三大系统性缺陷，实现双项目全自动提取 QG 9/9 PASS

---

## 一、Session 起点

继续 session 10 未完成的 bp-050 泛化验证。Round 6 的 `bp_synthesis_v5` 卡在 iterations=0（session 中断），需要诊断 + 修复 + 重新提取。

---

## 二、v6.2 开发（3 个 Fix）

### 诊断：6 轮失败日志分析

通过 sonnet 子代理分析 `_runs/finance-bp-050/` 的日志、checkpoint、artifacts，定位了 Round 6 的 synthesis 阶段卡住是 session 中断（非代码 bug），以及 7 个未解决问题。

### Fix 1: `_enrich_handler` 回写 `bd_list.json`

**问题**：QG 读 `bd_list.json`（synthesis 写入后不再更新），但 P15/P16 只修改 `blueprint.yaml`，导致 BQ-03/BQ-04 永远低估。

**修复**：enrich 完成后从 enriched `bp["business_decisions"]` 重建并回写 `bd_list.json`，失败时 log warning 不阻断。

**效果**：BQ-03 从 <10% 跳到 51.2%（P16 数据被 QG 正确读取）。

### Fix 2: Coverage Gap BD 打捞 + 字段消毒

**问题**：`BusinessDecision` 的 `type` pattern 和 `rationale min_length=40` 拒绝了 MiniMax 从稀疏代码骨架生成的 gap BD，L2/L3 全部失败。

**修复**：
- 新建 `GapBusinessDecision` relaxed schema（`schemas_v5.py`），coerce type/rationale/evidence/severity/known_gap
- `CoverageGapResult` 使用 `GapBusinessDecision` 替代严格的 `BusinessDecision`
- RawFallback 分支增加打捞逻辑

**效果**：Coverage Gap L2 从 100% 失败变为直接成功。

### Fix 3: Executor 尊重 blocking 标志

**问题**：`_run_single_phase` 对 Python handler 异常一律返回 `"break"`，即使 non-blocking 阶段。

**修复**：检查 `phase.blocking` 后决定 break/continue。

### Codex 审查

发现 3 个问题并修复：
- P1: sync 失败降级日志（增加 skipped 计数）
- P2: `GapBusinessDecision` 在 schema 层做 coercion 而非仅 salvage 路径
- P3: type strip 后未写回 `raw["type"]`（真 bug）

### v6.2 bp-050 提取结果

| 指标 | 值 |
|------|-----|
| QG | **8/9 PASS**（BQ-04 missing_gaps=0 仍 FAIL） |
| non-T BDs | 82 |
| multi_type | 51.2% |
| evidence coverage | 100%（格式） |
| Total tokens | 859K |

---

## 三、定量评估暴露三大系统性缺陷

通过 sonnet 子代理对 blueprint.v2.yaml 做 SOP 定量评估，总分 **51/100**：

1. **Evidence 证据链断裂**（70/100 FN_NOT_FOUND，实际可验证率 5%）
   - P5.5 AST walk 不含 ClassDef（14 BDs）
   - LLM 在 fn() 放非标识符内容（54 BDs）
   - ratio 公式排除 auto_fixed

2. **Missing Gap 完全缺失**（P15 解析器匹配不到 audit 格式）
   - 触发条件要求 `❌` + `FAIL`，audit 用 `⚠️ Fail`
   - 大小写敏感：`"Fail"` 匹配不到 `"FAIL"` 或 `"fail"`
   - "Missing Gap BD Candidates" 结构化章节完全不解析

3. **Known Use Cases 为 0**（scanner 只扫 `examples/**/*.py`）
   - skorecard 教程在 `docs/tutorials/*.ipynb`
   - SOP 定义 P0-P4 五级来源，代码只实现 P0

---

## 四、v6.3 开发（3 个 Fix）

### Fix 1: P5.5 Evidence 验证增强

- AST walk 增加 `ClassDef` 节点名
- fn 名合法性预检：`re.match(r'^[\w.]+$', fn_name)`，非法标识符标记为 `INVALID_IDENTIFIER`
- ratio 公式修正：`total = verified + invalid + auto_fixed`

### Fix 2: P15 Missing Gap 解析器修复

- 触发条件放宽：`("❌" in line or "⚠️" in line) and "fail" in line_lower`
- 新增 "Missing Gap BD Candidates" 章节解析（regex 提取 content/impact/detail）
- 去重逻辑

### Fix 3: UC 提取扩展

- glob patterns 从 3 个扩展到 6 个（增加 `**/*.ipynb`, `docs/**/*.py`, `docs/**/*.ipynb`）
- 添加 ipynb JSON cell source 提取（纯 Python，无额外依赖）
- 排除 `.ipynb_checkpoints`

### worker_arch max_iterations 20→40

zvt 提取时 worker_arch 在 MiniMax + GLM-5 上各耗尽 20 轮（40 轮总预算），改为 40 轮（80 轮总预算）。

---

## 五、v6.3 双项目全自动提取结果

| 指标 | bp-050 v3 | bp-009 v11 |
|------|-----------|------------|
| QG | **9/9 PASS** | **9/9 PASS** |
| non-T BDs | 88 | 89 |
| Missing gaps | **14** | **5** |
| Known UCs | **19** | **32** |
| Evidence ratio | 19.8% | 43.9% |
| Rationale 均长 | 306 chars | 312 chars |
| Multi-type | 40.9% | 41.6% |
| Total tokens | 1,258K | 971K |
| 全自动 | **yes** | **yes** |

**两个项目均一条命令全自动完成，QG 9/9 PASS。**

---

## 六、Commit 记录

| Commit | 内容 |
|--------|------|
| `dee0f8a` | v6.2: QG stale data fix + coverage gap salvage + executor blocking |
| `07defed` | severity/known_gap coercion for GapBusinessDecision |
| `d27a8df` | ruff auto-format cleanup |
| `05c6d7c` | v6.3: evidence verify + missing gap parser + ipynb UC discovery |
| `54c0fb0` | worker_arch max_iterations 20→40 |

---

## 七、遗留问题

1. **Synthesis Step 3 (interactions) 在 MiniMax 上不稳定**：两个项目都 L2/L3 fallback（int_parsing 错误），interactions 被跳过。需要调查 Step 3 schema 的 int 字段问题。

2. **Assembly L2 失败率高**：`BlueprintAssembleResult` 的 `dict_type` 验证错误，两个项目都走了 L3 raw recovery。MiniMax 可能对复杂嵌套 schema 兼容性差。

3. **P7 幽灵 stage 问题**：synthesis 产出的 BD stage 名与 assembly 产出的 stage ID 不一致（如 "Score Calibration" vs `rescaling`），需要在 synthesis prompt 或 P7 中增加 stage 名映射逻辑。

4. **Evidence 可验证率仍有提升空间**：bp-050 19.8%，zvt 43.9%。剩余 invalid 主要是 LLM 在 fn() 槽位放了非标识符内容（常量值、表达式）。需要在 LLM prompt 层面约束 evidence 格式。

5. **57 个 finance 项目待提取**：bp-001~059 中只完成了 bp-009 和 bp-050。

---

## 八、教训

1. **定量评估先于优化**：v6.2 通过了 QG 但定量评估只有 51 分，暴露了 QG 指标的盲区（evidence 格式合规 ≠ 内容可验证）。
2. **Schema 宽松度是结构化提取的关键杠杆**：`GapBusinessDecision` 放宽 validators 后，Coverage Gap 从 100% 失败变为 L2 直接成功。
3. **解析器必须对 LLM 输出格式变体鲁棒**：P15 对 `❌` vs `⚠️`、`FAIL` vs `Fail` 的敏感性导致整个 missing gap 功能失效。
4. **glob patterns 必须与 SOP 对齐**：SOP 定义了 P0-P4 五级 UC 来源，代码只实现了 P0，导致大量 ipynb 教程被忽略。
