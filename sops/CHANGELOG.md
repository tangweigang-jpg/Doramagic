# SOP & Pipeline Changelog

知识锻造管线（SOP + 管线代码 + 晶体编译）的版本变更记录。

---

## 2026-04-18

### 晶体 Web 发布 SOP v2.2（产品 FINAL 对齐 + SEO/GEO 门禁强化）

对齐 `web/Doramagic_web_product_FINAL.md`（2026-04-18）与 `web/Doramagic_SEO_GEO_Strategy.md`（2026-04-10）。v2.1 的 Package 缺少承载 Crystal Page 评估首屏、变量注入器、模型兼容、Preset 等产品字段，Web 渲染只能写死或 mock；本次升级将这些数据契约补齐，并把 SEO/GEO 策略的结论硬化为质量门禁。

**Part 1: Package Schema 扩展**

- 新增 **H. 消费者评估数据**：`sample_output` / `applicable_scenarios[]` / `inapplicable_scenarios[]` / `host_adapters[]`
- 新增 **I. 变量注入**：`required_inputs[]`（字段名 + 类型 + 默认值 + hint）
- 新增 **J. 信任数据**：`creator_proof[]`（官方自测多模型 Trace）/ `model_compatibility[]`（首次发布种子数据）
- 新增 **K. 发现元数据**：`tier`（standard/verified/battle_tested）/ `is_flagship` / `parent_flagship_slug` / `presets[]`
- 新增 **L. SEO-GEO 辅助**：`core_keywords[]`（5-10 个待验证长尾词）/ `og_image_fields`

**Part 2: 质量门禁重构（21 → 36 条，31 FATAL + 5 WARN）**

- 下限修正：`GEO-FAQ-COUNT` 3→5；`GEO-DATA-DENSITY` WARN→FATAL（数字下限 3）
- 新增 FATAL：`SEO-TITLE-KEYWORD`（Title 含核心关键词）/ `SEO-DESC-DENSITY`（Meta Description 3 要素密度）/ `GEO-DESC-CTA`（description 含平台链接）/ `GEO-DEF-FORMAT`（定义句式）
- 新增 FATAL：`USER-PROOF-MIN`（至少 1 条 Creator Proof）/ `USER-INPUTS-MATCH`（required_inputs 与 seed.md placeholder 数量一致）/ `USER-SCENARIO-PAIR`（适用与不适用场景各 ≥2 条）/ `USER-HOST-MIN`（host_adapters ≥1）
- 新增 FATAL：`TIER-VALID`（tier 与 Proof 数量匹配）/ `FLAGSHIP-PARENT`（非旗舰必须指向已发布旗舰）/ `PRESET-VAR-BIND`（Preset variable_overrides key 必须在 required_inputs 中）

**Part 3: 发布后动作**

新增 4 节（原 §3.5-3.7 随之重编号为 §3.6-3.8，交叉引用已同步）：

- 新增 §3.5 sitemap 与 robots.txt 承接（承诺 robots.txt 不被发布管线修改）
- §3.6 llms.txt 每次新晶体发布触发更新（原 §3.5）
- §3.7 每晶体核心关键词 GEO 监测清单，7/30/90 天抽查（原 §3.6）
- §3.8 类目/标签页差异化季度巡检（原 §3.7）

**附录 C: 待实现清单扩展**

- Prisma schema 新增 7 个关联表：`CrystalProof` / `CrystalModelCompat` / `CrystalRequiredInput` / `CrystalScenario` / `CrystalHostAdapter` / `CrystalPreset` / `CrystalKeyword`
- Crystal 主表补 `failureCount` 字段（供 JSON-LD aggregateRating 使用）
- `og_image` API 路由、Preset 管理后台、tier 自动升级作业、社区兼容矩阵聚合作业

**审查与修订**

v2.2 初稿由 Codex 独立审查后产出 6 条 P0 + 8 条 P1，已在同一日全量修复。关键澄清：
- Tier 仅允许 agent 提交 `standard` / `verified`；更新时取 `max(payload.tier, 现值)`
- `CrystalModelCompat` 唯一键 `(crystalId, model, source)`，agent 只写 creator 种子，社区聚合走独立行
- `USER-INPUTS-MATCH` 的 placeholder 解析算法规范入 §2.4.1（剥离代码块/注释/frontmatter，支持 `\{\{x\}\}` 转义）

---

## 2026-04-12

### 蓝图提取 SOP v3.4（字段强制化 + v5 Codex 审计修复）

- Step 4 精细度检查清单：`required_methods` 和 `key_behaviors` 从警告提升为**必填字段**，空值必须标注"该阶段无用户接口"
- Step 4 精细度检查清单：`key_behaviors` 缺失时新增补救动作"补充或标注'该阶段无显式行为契约'"
- _template 新增 L39（stages required_methods/key_behaviors 缺失导致晶体编译无法生成接口契约）
- _template 新增 L40（known_use_cases 字段名必须标准化：source 非 source_file，intent_keywords 必填）
- _template 新增 L41（missing gap BD 必须含 known_gap: true，下游约束管线依赖此字段）
- 驱动来源：v5 Batch A 自动提取 bp-009 + Codex SOP v3.3 合规审计（3 FAIL + 1 WARN）

### 蓝图提取 SOP v3.3（BD 深度质量标准）

- Step 2c 新增 BD 最低质量标准：rationale ≥2 句（WHY + BOUNDARY）、多类型标注显式评估、evidence 三元组
- Step 2c 新增 Missing Gap 分析为必须输出：对照审计清单标记未覆盖项，底线 ≥3 条
- Step 4 精细度检查清单新增 4 项深度质量门禁：rationale 平均字数 ≥40、多类型标注比例 ≥30%、missing gap ≥3、审计清单覆盖率 ≥80%
- _template 新增 L37（BD 无 rationale = 丢失 WHY）、L38（missing gap 必须审计清单驱动）

---

## 2026-04-08

### 晶体编译 SOP v2.1（Scaffold 骨架模式）

- 资源段渲染规则：从"安全检查函数模板（copy-paste）"升级为"回测骨架 Scaffold（安全检查焊死，AI 只填 REPLACE_WITH）"
- directive 新增 scaffold_bypass 禁止动作：禁止忽略骨架从零生成完整回测代码
- _template 教训 L43：安全检查函数作为独立模板被 AI 内化而非引用，需升级为骨架模式
- 晶体 bp-009：函数模板（42 行）替换为完整骨架（~90 行），含 T+1 / 涨跌停 / 印花税 / 整手限制
- 决策依据：四方评审（Grok/GPT/Claude Opus/Claude Sonnet）全票 CONDITIONAL ADOPT

### 晶体编译 SOP v2.0（OpenClaw 实测驱动升级）

三项变更，均有 bp-009 v1.9 晶体在 OpenClaw + MiniMax-M2.7 上的端到端实测证据：

1. **context_state_machine enforcement 简化**：删除"宿主 AI 必须在回复中输出 `[STATE: CA2]` 标注"要求，改为"状态推进通过 Step 顺序体现"。原因：3 次实测中宿主 AI 从不输出状态标注，但行为上 100% 遵守先问后做流程。
2. **output_validator 渲染为可执行代码块**：validation_threshold 从自然语言描述改为 `assert` Python 代码块，宿主 AI 直接粘贴到生成代码末尾即可自动执行。原因：自然语言描述时 output_validator 是软约束，依赖 LLM 自觉。
3. **资源段新增回测安全检查代码模板**：领域 RC 约束（T+1 / 涨跌停 / 印花税 / 整手限制）渲染为独立 Python 代码块，宿主 AI 自写回测时 copy-paste 使用。原因：布林带回测 256 行手动代码无 T+1 检查。

_template 同步更新：v1.9 → v2.0（L40-L42 教训 + enforcement 简化 + 渲染规则 + Step 9 检查项）

### SOP_SPEC 合规修复 + _template 同步

**晶体编译 SOP v1.9 — SOP_SPEC 合规修复**：
- 删除 4 处溯源违规（铁律 2）：3 处 `**来源**：` 标注 + 1 处 `（来自三方评审 Q6 共识）`，理由内联到规则本身
- frontmatter 上游引用更新：v3.1/v2.1 → v3.2/v2.2

**_template/ 三文件同步**：
- `blueprint-extraction.tmpl.md`：v3.1 → v3.2（Step 2d UC 消歧字段 negative_keywords/disambiguation/data_domain + Step 4 规则 5 消歧检查项 + L36）
- `constraint-collection.tmpl.md`：v2.1 → v2.2（Step 2.2 validation_threshold 可选字段 + M 类 validation_threshold 标注 + Step 5.4 覆盖率指标 + L24）
- `crystal-compilation.tmpl.md`：v1.6 → v1.9（v1.7 单文件自包含 + v1.8 知识组织全量注入 + v1.9 五控制块 + Step 6.5 context_acquisition + intent_router + context_state_machine + spec_lock_registry 双层 + preservation_manifest + output_validator + model_misuse 失败类 + M 类 Spec Lock + L34-L39）

### 蓝图提取 SOP v3.2

- Step 2d known_use_cases 新增 negative_keywords、disambiguation、data_domain 三个字段
- Step 4 规则 5 新增消歧字段检查项

### 蓝图提取 SOP v3.1

- Step 2c 新增 M vs B 判断树（三条必要条件）
- Step 2c 新增审计发现处理规则（❌→BD(missing)，⚠️→BD(BA)）
- Step 4 新增 audit_checklist_summary YAML 字段
- Step 4 新增规则 8（SOP 版本注释）
- 清理全文 [v3.0 新增] 标签（SOP_SPEC 合规）

### 约束采集 SOP v2.2

- Step 2.2 输出格式新增 validation_threshold 可选字段
- Step 2.4.1 M 类派生规则新增 validation_threshold 标注要求
- Step 5.4 质量基线新增 validation_threshold 覆盖率指标

### 约束采集 SOP v2.1

- Step 2.2 新增 machine_checkable 判定标准
- Step 2.4.2 BA 派生条件统一为三条件版本
- Step 2.4.4 新增 RC/missing 去重例外
- 新增 Step 2.5 审计发现约束转化
- Step 3.2 新增 Draft→Production schema 字段映射表
- Step 5.4 质量基线拆分（代码提取 + 蓝图派生 + 审计转化）

### 晶体编译 SOP v1.9

- 新增 5 个结构化控制块：intent_router、context_state_machine、spec_lock_registry、preservation_manifest、output_validator
- Step 6.5d 用例匹配改为 intent_router（正向词 + 排除词 + 消歧问题）
- Step 6.5e 新增 context_state_machine（4 状态，未确认禁止生成代码）
- Step 1a Spec Lock 分为 semantic_locks + implementation_hints 双层
- Step 9 新增 7 条控制块相关检查项

### 晶体编译 SOP v1.8

- Step 6 从"知识压缩"改为"知识组织"——默认全量注入
- 覆盖率标准改为全部 BD 100%、全部约束 100%
- 用例策略改为全量灌入、运行时匹配
- 排除项须逐条记录理由

### 晶体编译 SOP v1.7

- 产出从多文件 bundle 改回单文件自包含（对齐产品宪法 §3.4）
- Per-stage 渲染从多文件改为文件内分段
- 清理所有 references/、scaffolds/ 引用

### 晶体编译 SOP v1.6

- 新增 Step 6.5 context_acquisition 设计方法论
- Step 8b SKILL.md 执行流程插入 context_acquisition 四步
- Step 8b-2 人话摘要渲染
- IR 模板新增 context_acquisition 节
- Step 9 新增 4 项检查

### 晶体编译 SOP v1.5

- SOP_SPEC 合规（清理版本标签、教训编号、评审溯源）
- 教训日志 L1-L26 迁入 _template/
- 上游版本引用更新（v2.3→v3.1, v1.3→v2.1）
- 新增 type=M、model_misuse 失败类、M 类 100% 覆盖率
- machine_checkable → Hard Gate、audit_checklist_summary 消费

### _template/ 同步更新

- blueprint-extraction.tmpl.md：v2.3 → v3.1（L32-L35）
- constraint-collection.tmpl.md：v1.3 → v2.1（L20-L23）
- crystal-compilation.tmpl.md：v1.5 → v1.6（L27-L33）

### 管线代码

- 新建 `packages/blueprint_pipeline/`（prompts.py + extractor.py + pipeline.py + state.py + repo_manager.py）
- `constraint_pipeline/extract/prompts.py`：新增 USER_PROMPT_DERIVE_TEMPLATE + USER_PROMPT_AUDIT_CONVERT_TEMPLATE + 3 共享常量 + validation_threshold
- `constraint_pipeline/extract/extractor.py`：新增 extract_derived_constraints() + convert_audit_findings()
- `constraint_pipeline/pipeline.py`：扩展编排（Step 2.4 + 2.5）
- 新建 `scripts/run_sop.py`（CLI 入口，blueprint + constraint 子命令）
- `blueprint_pipeline/extract/prompts.py`：Step 2d 模板新增 negative_keywords + disambiguation + data_domain

### 工具脚本

- 新建 `scripts/snapshot_blueprint.py`（蓝图快照到 _history/）
- 新建 `scripts/slice_constraints.py`（按蓝图 ID 切片约束）
- 新建 `scripts/diff_knowledge.py`（结构化 diff，blueprint + constraint 子命令）
- Makefile 新增 sop-preflight、sop-diff、sop-run-blueprint、sop-run-constraint、sop-run-all、sop-status、sop-resume

### 知识资产

- finance-bp-009.yaml：v1.0.0 → v3.0.0（56 BD，40 UC，audit_checklist_summary）
- finance-bp-020.yaml：v1.0.0 → v2.0.0（21 BD，8 UC）
- finance-bp-050.yaml：v1.0.0 → v2.0.0（12 BD，10 UC）
- 约束新增：bp-009 v3.0 draft 34 条 + bp-020 v2.0 draft 20 条 + bp-050 v2.0 draft 16 条
- 晶体：bp-009 v1.7/v1.8/v1.9、bp-020 irswap、bp-050 skorecard

### 设计文档

- `docs/designs/2026-04-08-knowledge-quality-framework.md`（13 项量化评价指标）
- `docs/research/2026-04-08-what-makes-a-good-skill.md`（skill 质量深度研究）
- `docs/research/2026-04-08-crystal-v1.8-openclaw-test-review-prompt.md`（四方评审提示词）
- `docs/research/2026-04-08-crystal-v1.8-opus-review.md`（Opus 独立评审）
