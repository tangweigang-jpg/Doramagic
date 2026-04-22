# bp-009 v6 蓝图提取 SOP v3.4 审查报告

> 审查日期：2026-04-13
> 提取版本：v6 agent（首次运行）
> 模型：MiniMax M2.7
> 总 tokens：~1.04M
> 蓝图：finance-bp-009（zvtvz/zvt）

---

## 一、精细度检查清单（SOP v3.4 步骤 4）

### 量化指标

| 检查项 | 标准 | 实际值 | 判定 |
|--------|------|--------|------|
| business_decisions 数量 | ≥ 5 条非 T | **81 条非 T** | ✅ 远超标准 |
| BD rationale 深度 | ≥ 40 字平均 | **283 字平均** | ✅ 远超标准 |
| BD 多类型比例 | ≥ 30% | **6.2%** | ❌ **不达标** |
| missing gap 条数 | ≥ 3 条 | **8 条** | ✅ |
| stages 数量 | 2-30 | **9** | ✅ |
| evidence 覆盖率 | ≥ 50% | **90.9%** | ✅ |
| BD 类型多样性 | ≥ 2 种非 T 类型 | **B/BA/DK/M/RC 全覆盖** | ✅ |
| vague 比例 | ≤ 30% | **1.1%（1/88）** | ✅ |
| audit_checklist_summary | 必须存在 | **存在** | ✅ |
| known_use_cases | 有 | **31 条** | ✅ |
| evidence 确定性验证 (v6) | — | **6.4%（5/78 verified）** | ⚠️ 偏低 |

**BQ 总评**：8/9 通过。BQ-03（多类型比例）失败——MiniMax M2.7 在 Synthesis 阶段倾向单类型标注，需 Step 2 prompt 强化。

### 结构完整性

| 字段 | 检查标准 | 判定 | 备注 |
|------|---------|------|------|
| replaceable_points | 每选项有 traits/fit_for/not_fit_for | ✅ | 数据源/存储/执行三维度覆盖 |
| required_methods | 每方法有 name+description+evidence | ✅ | 所有 stage 有实质内容 |
| design_decisions | 有源码证据引用 | ✅ | |
| key_behaviors | 有 behavior+description+evidence | ✅ | |
| stages.order | 严格递增 | ✅ | 1-9 无重复 |
| global_contracts | ≥ 3 条架构不变式 | ✅ | 8 条 |
| relations | ≥ 1 条 | ✅ | placeholder |
| YAML 特殊字符 | 引号包裹 | ✅ | |
| commit_hash | 必需 | ✅ | f971f00c... |
| source.projects | 非空 | ⚠️ | 空列表——assembly 遗漏 |
| "所有"/"全部" 频率 | ≤ 3 次 | ✅ | |

---

## 二、v6 新功能评估

### 2.1 Independent Evaluator（bp_evaluate）

**Evaluator 报告质量**：**优秀**

- 评估了 20 条非 T BD（73 条中抽样）
- **score = 0.90**，recommendation = PASS
- 发现 4 个有效问题：
  - BD-027：evidence 引用的是 `trader.py:283`（due_timestamp 偏移），但 T+1 机制实际在 `sim_account.py:317-329`（trading_t + available_long）。Evaluator **正确识别**了 evidence 与 rationale 的语义不匹配。
  - BD-072：**错误地**标记 T+1 为 missing gap。Evaluator **正确指出** T+1 已通过 trading_t + available_long 实现。这是一个 false positive missing gap，Evaluator 成功捕获。
  - BD-INT-002：声称仓位管理有矛盾，但 Evaluator 验证后发现 `position_pct` 是对**剩余现金**的比例，不是总资本——**无实际 bug**。

**结论**：Evaluator 成功防止了 1 个 false positive missing gap（BD-072）和 1 个错误的交互 BD（BD-INT-002），直接提升了蓝图质量。Sprint 合同式验证有效。

### 2.2 Worker Resource（worker_resource）

**资源盘点质量**：**优秀**

- 识别了 4 个数据源（East Money、JoinQuant、Tushare、Sina）
- 每个数据源有完整的 API 端点列表、数据类型、认证方式、频率限制
- 资源证据引用精确到文件和行号
- P14 成功注入 5 个 resource slot

**问题**：worker_resource 消耗 316K tokens（8 个 Worker 中最高），max_iterations=30 偏多。资源盘点不需要像架构分析那样深入探索，可降低到 15-20。

### 2.3 P5.5 Evidence 验证

**验证率 6.4%（5/78）**：偏低但符合预期。

根因分析：
- 73 条 evidence 标记为 invalid——多数是因为 evidence 格式为 `src/zvt/xxx.py:N-M(function)` 格式（行号范围），而 P5.5 的正则只匹配 `file:line(fn)` 单行格式
- 2 条被自动修复（函数存在但行号漂移）
- P5.5 的正则 `^(.+?):(\d+)\((.+?)\)$` 不支持行号范围格式 `file:N-M(fn)`

**修复建议**：扩展正则支持 `file:N-M(fn)` 和 `file:N(fn)` 两种格式。

### 2.4 审计闭环

**审计注入效果**：

- worker_audit 产出 20 项审计（pass=1, warn=9, fail=10）
- 审计结果注入 Synthesis Step 3 后，missing gap 从 Step 1 的 8 条维持到最终 8 条
- 审计发现中的 critical 项（float 货币、Point-in-Time、stale data）均在 missing gap 中体现

---

## 三、与 SOP v3.4 对齐评估

| SOP 步骤 | 对齐 | 说明 |
|---------|------|------|
| Step 0: 指纹探针 | ✅ | TRD/DAT 子领域标签 |
| Step 1: Clone | ✅ | commit_hash 锁定 |
| Step 2a: 架构提取 | ✅ | worker_arch + worker_arch_deep 并行 |
| Step 2b: 声明验证 | ✅ | worker_verify（20 轮，59K tokens） |
| Step 2c: 业务决策标注 | ✅ | 88 BD，六类全覆盖 |
| Step 2d: 业务用例扫描 | ✅ | 31 UC |
| Step 3: 自动验证 | ⚠️ | P5.5 功能正确但正则限制导致验证率低 |
| Step 4: 组装蓝图 | ✅ | 9 stages, 2603 行 YAML |
| Step 5: 一致性检查 | ⚠️ | 因 QG 失败未执行 |
| Step 6: 多模型评审 | ⚠️ | bp_evaluate 替代（单模型，非四方） |

---

## 四、关键发现

### 亮点

1. **88 条 BD**（vs v5.2 历史最高约 50-60 条）——v6 审计注入 + 交互分析显著提升了 BD 产出量
2. **Evaluator 正确识别了 2 个 false positive**——BD-072（T+1 未缺失）和 BD-INT-002（无实际 bug）
3. **资源盘点首次系统化**——4 个数据源、完整 API 端点、认证方式、替代方案
4. **31 条 UC**——覆盖了 zvt 的核心使用场景
5. **rationale 深度 283 字平均**——远超 SOP 要求的 40 字

### 问题

1. **BQ-03 多类型比例 6.2%**——MiniMax M2.7 的 Synthesis 倾向单类型标注。需在 Step 1 prompt 中强化"对每个非 T 决策，显式评估是否有双重性质"的指令。
2. **P5.5 验证率 6.4%**——正则不支持行号范围格式。技术修复简单。
3. **source.projects 空列表**——assembly Instructor 遗漏了项目名。需在 enrich 中增加 P0.5 补充。
4. **worker_resource token 过高（316K）**——需降低 max_iterations 或增加收敛检测。
5. **Coverage Gap Instructor 全降级到 L3**——MiniMax 对 `BDExtractionResult` 的 tool_use 兼容性差，需考虑为此阶段禁用 thinking。

---

## 五、改进优先级

| 优先级 | 改进项 | 预计工作量 |
|--------|--------|-----------|
| P0 | P5.5 正则扩展支持 `file:N-M(fn)` | ~10 行 |
| P0 | Enrich P0.5: source.projects 自动填充 | ~10 行 |
| P1 | Synthesis Step 1 prompt 强化多类型标注指令 | ~20 行 prompt |
| P1 | worker_resource max_iterations 降到 15 | 1 行 |
| P2 | Assembly Instructor 调用禁用 thinking（MiniMax） | ~5 行 |
| P2 | Coverage Gap 降级处理改进 | ~30 行 |

---

## 六、整体评价

**v6 首次运行评分：7.5/10**

v6 的三个核心改版（worker_resource、bp_evaluate、审计闭环）全部按设计运行并产生了预期价值。88 条 BD + 31 UC + 系统化资源盘点的产出质量超过了 v5.2。Evaluator 成功捕获了 2 个 false positive，证明了独立评估层的必要性。

主要扣分项是 BQ-03 多类型比例不达标和 P5.5 验证率偏低——两者都是可修复的技术问题，不是架构缺陷。

**对晶体质量的影响**：
- **好的框架** ✅ — 9 stages + 8 global contracts + 88 BD（含 Evaluator 验证）
- **好的资源** ✅ — 首次有系统化资源盘点（4 数据源 + 完整 API + 替代方案）
- **好的约束基础** ✅ — 审计 20 项（pass=1, warn=9, fail=10）为约束采集提供了精确锚点
