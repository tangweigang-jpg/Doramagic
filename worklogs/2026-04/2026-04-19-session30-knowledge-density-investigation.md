# Session 30 Worklog — 知识晶体密度路径探索 + 约束分类体系迭代 + CTO 拉回 MVP

**Date**: 2026-04-19
**主线程**: Opus 4.7 (1M, CEO Partner 风格)
**触发**: 用户"开启知识晶体工作的讨论"
**结局**: 约束分类体系 v1→v5 迭代完成 + opus 审查发现 sonnet 32% 假阳性 + CTO 拉回 MVP 路径（挑 20-30 条领域通则 → Step 10 效能验证）

---

## 零、Session 起点与终点

**起点**：用户抛"开启知识晶体工作的讨论"。主线程盘点现状发现：
- 5 个存量晶体格式不一（bp-001/002 v3.x、bp-009 IR+seed 双文件、bp-020/050 未 promote）
- SOP 刚升 v5.3（19 条 SA 断言）
- `_shared/resources.yaml` 不是最新（06:06 UTC 扫，73 个 LATEST.yaml 全被触过）

**终点**：
- 资源/槽位/catalog 领域池完整 ✅
- 73 蓝图 17,524 约束完成 sonnet 分类 ✅
- 发现 sonnet 最高置信度仍有 32% 假阳性 ⚠️
- CTO 级诊断：分类工程追求 95% 准确率偏离真实目标，拉回 MVP

---

## 一、主线任务演进（8 个子工作）

### 1. resources.yaml 陈旧性修复

- 发现：scan 脚本扫了 72 蓝图，仓库 73 个 LATEST.yaml 全部被触过
- 重扫：仓库从 71 → 72 BP（1 个仍因 `resources[]` 空被跳过）
- 副产品发现：`replaceable_slots.yaml` 从旧 29 条骤降到 1 条

### 2. replaceable_slots 诊断 + 修复（子代理）

- 根因：不是 extraction agent 丢失语义，而是 **scan 脚本没跟上 schema 迁移**
- commit `3009f72`（session 29）故意把 slot 从 `resources[].type=replaceable_component` 迁到顶层 `bp.replaceable_slots[]` 字段
- scan 脚本 `scan_resource_pool.py` 未更新，看不到新字段
- 子代理修复：scan_blueprints 读新顶层字段，by slot_name 跨 BP 聚合 + options union-merge
- **结果**：38 条聚合槽位（从 381 原始条目按 name 去重），pool 103 无回退
- memory 修正：`project_replaceable_slot_regression.md`（"scan schema lag"，不是 regression）

### 3. bp-009 v5.3 晶体编译试点（一次过）

- 跑 `make crystal-full BP=finance-bp-009--zvt VERSION=v5.3`
- 结果：**19/19 SA 全通过，gate PASS**，145KB seed.yaml 产出
- 意外发现：v5.3 编译管线本身已成熟（之前判断"v3.x → v5.3 迁移工作量大"错误）
- 真瓶颈不是管线，是晶体**知识密度**

### 4. 知识架构目录归档

- 用户决策："未来蓝图/约束/晶体统一归口 `knowledge/sources/`"
- 归档 8 个目录到 `knowledge/_archive/2026-04-19/`：api_catalog/blueprints/bricks/constraints/crystals/judgments/meta/scenes
- 保留：sources（真源）+ catalogs（外部参考 public_apis.yaml，活跃消费者）
- CLAUDE.md 目录结构段同步更新
- `.gitignore` 解除 CLAUDE.md（AI 协作规范，公开 repo 友好；PRODUCT_CONSTITUTION/INDEX/TODOS 保持 ignore）

### 5. Public APIs catalog 合并到 resources_full.yaml（子代理）

- catalogs/public_apis.yaml 已有 1436 条（今早 11:29 导入自 xlsx）
- 160 条 finance 相关 API（5 类：Finance/Cryptocurrency/Currency Exchange/Business/Blockchain）
- 合并策略：`name` 小写匹配去重
  - 已存在 13 条：富化 catalog_metadata（Yahoo Finance/Binance/Alpha Vantage/Kraken 等）
  - 新增 147 条：`used_by: []`，`scan_source: catalog_import` 标注来源
- **结果**：`resources_full.yaml` 729 → 876 条

### 6. 约束复用 audit（子代理）

- 17,499 条约束 hash 级去重：**0.01% 跨 BP 复用**（仅 2 条"回测≠实盘"变体）
- 100% 约束被标 `scope.level=domain` → 标签机械失效
- 12 条随机抽样人工分类：42% 具可迁移性（不是 0%——hash 级是技术幻觉）
- **CEO 合伙人拉回**：用户质问"目的是什么？" → 回归"提升晶体知识密度"

### 7. 约束分类 rubric v1→v5 迭代（大型工作）

**v1（三 shard 并行 sonnet）失败**：
- Shard 1: 56.7% universal，needs_review 14.1%
- Shard 2: 5% universal，needs_review 31%（agent 违反 rubric 自创规则）
- Shard 3: 34% universal
- 同一 rubric 三 shard 差 11 倍 → rubric 太宽松 + agent 未遵规则

**v2 修正（bp-009 pilot）**：
- 引入合取 Gate A（语义通用）+ Gate B（概念通用）
- needs_review 降到 2.7%
- 但人工抽检 55% 准确率——Gate B.2 "编程通识"被 sonnet 滥用（C-074~C-087 被"抽象为 portable pitfall"误判 universal）

**v3 修正**：
- 废除 B.2（"编程通识"抽象）
- Gate B 只保留 B.1（finance 关键词字面命中）+ B.3（consequence.kind 硬匹配）
- bp-009 pilot：10.2% universal，但抽检仍 ~84%（污染率 27%）
- 误判 4 条：C-091（策略选择）、C-092/C-103（magic numbers）、C-144（zvt command 项目名泄漏）

**v4 修正**：
- 加 A.5（magic numbers 检测）
- 加 A.6（项目 repo slug 黑名单）
- 修好 3 条，但**误杀 3 条**（C-111/C-112/C-135：A.6 把外部库 Plotly/yfinance 当项目名）
- 净准确率同 v3

**v5 修正（成功版）**：
- A.6 精简：只留项目内部命名（zvt/freqtrade/rqalpha 等），第三方库（Plotly/ccxt/yfinance 等）移除
- bp-009 pilot 11 条 universal，人工抽检 **0% 污染**（9 正确 + 2 needs_review 合理）
- 遗漏 1 条（C-111 被 A.3 slash 误杀），接受（遗漏比污染可容忍）

**v5 全量 3-shard**（73 BP，17,524 条）：
| Shard | 方法 | Total | Universal | needs_review |
|---|---|---|---|---|
| 1 | Python 脚本 | 5,948 | 974 (16.4%) | 100 (1.7%) |
| 2 | Python 脚本 | 6,693 | 1,340 (20.0%) | 245 (3.7%) |
| 3 | Python 脚本 | 4,883 | 880 (18.0%) | 1,300 (26.6%)* |
| **合计** | | **17,524** | **3,194 (18.2%)** | 1,645 |

*shard 3 脚本 bug：错把 B.all project 标 needs_review（confidence 0.7）。主线程合并时修正 1,194 条。

### 8. Opus 审查层（CTO 决策升级）

**Task 1（451 条 needs_review 盲判）**：
- 推翻率 **38.1%**（172/451 flip universal→project）
- 证实 needs_review 池确实是边界重灾区

**Task 2（50 条 confidence=1.0 高置信盲审）**：
- **推翻率 32%**（16/50 flip）
- Opus 揭示 sonnet 5 种系统性偏差：
  1. Framework-internal claim ("bt is X-only framework") 被误判通用
  2. 库特定 API（`putconn()`、`utc=False`）被误判通用
  3. Magic numbers（"240 trading days"、"qx*1000"、"6 decimal places"）漏过 A.5
  4. 方法论选择（"mandate Sharpe over Sortino"）被误判通用
  5. **"Consequence 通用 ≠ action 通用"**：sonnet 看 consequence 关键词定档，忽略 action 的项目特定性

---

## 二、关键 CTO 决策时刻

### 决策 1：shard v1 失败后立即停 shard 3 + 设计 v2

用户授权"独立判断"。主线程承认 rubric v1 设计失败（三 shard 差 11 倍），立即进入 v2 pilot 验证循环。

### 决策 2：rubric v2→v5 快速迭代，不等用户拍板

每版 pilot 完抽检 → 失败 → 分析根因 → 设计下版。用户授权范围内自主执行。

### 决策 3：废除 B.2（"编程通识"抽象）

Sonnet 系统性"善解人意"抽象——任何项目规则都能被它抽象为"portable Python pitfall"。v3 彻底废除 B.2，只保留字面关键词命中。

### 决策 4：Opus 混合方案代替纯人工 review

用户建议 opus 审 438 条代替 1-2 小时人工。主线程设计混合：Opus 独立盲判（不看 sonnet 原判）+ 不一致的转人工最终定。启动 2 个 opus 子代理并行。

### 决策 5：CTO 被用户叫停 — 拉回 MVP ⭐

用户关键一问："**我们现在做这一系列的目的是什么？**"

主线程承认"工程爽感陷阱"——追求 95% 分类准确率时丢失真实目标。回溯：

- 真目的：让晶体吸收领域通用约束 → 提升密度 → 让宿主 AI 产出更好 skill
- 现状：工作链还差"改晶体编译消费领域约束"和"Step 10 验证密度提升是否有效"
- 诚实反思：5-10% 分类噪声可能并不致命（每条约束带 when 条件，宿主 AI 自己判断触发）

**拉回方案**：
- 不启动 Task 3（全量 opus 重审 2614 条）
- 挑 20-30 条最清晰领域通则（opus 净化池 279+34=313 条里选）
- 注入 bp-009 v5.3 晶体编译
- 跑 Step 10 效能测试——这才是"密度是否有效"的唯一判据

---

## 三、产出清单

### 活跃数据（保留）

| 文件 | 内容 | 大小 |
|---|---|---|
| `_shared/resources.yaml` | 共享资源池（≥2 BP），103 条 | 42KB |
| `_shared/resources_full.yaml` | 全量资源 + catalog 147 条候选，876 条 | 294KB |
| `_shared/replaceable_slots.yaml` | 共享槽位（≥2 BP），38 条 | 85KB |
| `_shared/replaceable_slots_full.yaml` | 全量槽位，298 条 | 330KB |
| `_shared/constraints_audit_v5_merged.jsonl` | 17,524 条约束分类审计 | 22MB |
| `_shared/constraints_universal_candidates.jsonl` | 3,115 条 universal（hash 去重） | 4.2MB |
| `_shared/_opus_output_needs_review.jsonl` | opus 重判 451 条 needs_review | - |
| `_shared/_opus_output_sampled50.jsonl` | opus 审 50 条高置信抽样 | - |

### 过渡产物（待清理）

- `_shared/constraints_audit_shard_{1,2,3}.jsonl`（v1 失败版本，可删）
- `_shared/constraints_audit_pilot_bp009{,_v3,_v4,_v5}.jsonl`（pilot 版本，保留 v5 即可）
- `_shared/run_rubric_v5_shard{1,2}.py`（子代理自建脚本，应移到 scripts/ 或删）
- `_shared/_opus_input_*.jsonl`（opus 临时输入，可删）

### Git 提交

- `5b6a197` chore(knowledge): archive 8 dirs to _archive/2026-04-19
- `6a0d175` chore(repo): track CLAUDE.md — public-friendly AI collaboration spec

### Memory 更新

- `project_replaceable_slot_regression.md` 修正为"scan script schema lag"
- `MEMORY.md` 索引同步

---

## 四、未解问题（下一 session 起点）

1. **最迫切**：挑 20-30 条领域通则 → 注入 bp-009 晶体 → **Step 10 效能验证**（真实目标）
2. `_shared/` 中间产物清理（pilot 文件、shard v1、脚本）
3. `resources_full.yaml` 15 条重复 name 技术债（tushare×3, baostock×3, pyyaml×2 等）
4. bp-065 / bp-084 resources 为空（extraction agent 未提取成功）
5. 晶体 v5.3 schema 如何消费领域约束（WP3 未设计）
6. crystal-gate SA-03 断言在注入领域约束后的兼容性（WP4 未动）

---

## 五、关键教训

### 1. Rubric 设计失败是常态

v1 三 shard 差 11 倍暴露"rubric 用词"和"LLM 理解"之间的巨大差距。必须先 pilot 小样本 + 人工抽检才能信任全量跑。

### 2. Sonnet 系统性偏差：consequence ≠ action

Sonnet 有"善解人意"地把项目特定规则抽象为通用原则的倾向。rubric 再细也有漏洞（v3 的 B.2、v4 的 A.6）。**LLM 单次分类有能力天花板**（~80-90% 区间）。

### 3. 高置信度也不可信

Sonnet 标 confidence=1.0 的"最肯定"判定仍有 32% 假阳性。**订阅者应警惕"高置信"的虚假安全感**。

### 4. CEO 拉回比工程爽感重要

连续 5 版 rubric 迭代 + opus 审查 + 合并去重——都是工程过度。用户一句"目的是什么？"瞬间暴露盲区：**我们还没验证过"密度提升真的让晶体更好"**，整条路径可能基于错误假设。

### 5. MVP 优先于准确率

对 MVP 而言，70% 准确率的分类 + 人工挑 20-30 条最清晰条目 = 足够验证"密度 vs 价值"假设。不验证价值前投入工程是反模式。

---

## 六、子代理启动记录

| Agent | 模型 | 任务 | 产出 |
|---|---|---|---|
| catalog-merge | sonnet | 合并 public-apis 到 resources_full | 147 新增 + 13 富化 |
| slot-regression-fix | sonnet | 修 scan_resource_pool.py | 38 聚合槽位 |
| audit-constraint-reuse | sonnet | hash 去重 + 文本近似 | 0.01% 复用 |
| audit-classify-12 | sonnet | 12 条样本分类试点 | 42% 可迁移 |
| shard1-v1 | sonnet | 25 BP 分类 | 56.7% universal（失败） |
| shard2-v1 | sonnet | 25 BP 分类 | 5% universal（失败） |
| shard3-v1 | sonnet | 23 BP 分类 | 34% universal（失败） |
| pilot-v2 | sonnet | bp-009 rubric v2 | 55% 抽检（失败） |
| pilot-v3 | sonnet | bp-009 rubric v3 | 84% 抽检（失败） |
| pilot-v4 | sonnet | bp-009 rubric v4 | 修3杀3（失败） |
| pilot-v5 | sonnet | bp-009 rubric v5 | 0% 污染（成功） |
| shard1-v5 | sonnet | 25 BP v5 分类 | 974 universal |
| shard2-v5 | sonnet | 25 BP v5 分类 | 1340 universal |
| shard3-v5 | sonnet | 23 BP v5 分类 | 880 universal |
| opus-review-451 | **opus** | needs_review 重判 | 38% 推翻率 |
| opus-audit-50 | **opus** | 高置信抽检 | 32% 推翻率 |

合计 **16 个子代理调用**，其中 2 个 opus + 14 个 sonnet。

---

*Session 30 | 2026-04-19 | Opus 4.7 1M (CEO Partner) + 16 subagents*
