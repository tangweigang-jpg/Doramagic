# 约束采集 SOP

> **领域**: Finance | 版本: 2.3 | 执行时只需阅读本文件

---

## 前提条件

- 蓝图已提取并通过四方评审（YAML 文件就绪）
- `constraint_schema` + `constraint_pipeline` 包已安装
- 目标项目可通过 git clone 获取

---

## 流程概览

蓝图提取 SOP 步骤 0 已探测知识源类型（代码/文档/混合）。约束采集复用该结果，按知识源类型选择提取策略。

```
Step 1: Clone 项目（复用蓝图提取已 clone 的仓库）
Step 2: 并行子代理提取
  2.1-2.3: 代码约束提取（per stage + edges/global/claims）— 代码知识源
  2.1-s:   文档约束提取（per SKILL.md/CLAUDE.md + resources）— 文档知识源
  2.4:     蓝图驱动的业务约束派生（所有知识源通用）
  2.5:     审计发现的约束转化（所有知识源通用）
  2.6:     rationalization_guard 专项提取 — 文档知识源独有
Step 3: 入库（JSON → Constraint → JSONL）
Step 4: 后处理修复（6 项规则）
Step 5: 质量验证（扫描 + 抽样评审）
```

预计耗时：纯代码蓝图 ~30 分钟（与此前一致）；含文档知识源的蓝图 ~45 分钟（+Step 2.1-s 和 2.6）

**金融领域说明**：当前 59 个蓝图全部是代码知识源。随着 AI 金融项目增多（FinRL agent 配置、量化 skill 框架），文档知识源会出现。纯代码蓝图跳过 Step 2.1-s 和 2.6。

---

## Step 1: Clone 项目

```bash
mkdir -p repos
git clone --depth 1 https://github.com/{owner}/{repo}.git repos/{repo}
```

**记录 commit hash**，写入约束的 evidence_refs 中 — 行号随版本漂移，commit hash 锁定提取时的代码版本。

---

## Step 2: 并行子代理提取

### 2.1 按 stage 拆分任务

每个蓝图的 stages 拆为独立子代理任务。对于 4-5 个 stage 的蓝图：

- **子代理 A**：stage 1 + stage 2（如 data_pipeline + strategy_engine）
- **子代理 B**：stage 3 + stage 4（如 trade_loop + evaluation_reporting）
- **子代理 C**：edges + global + claim_boundary 专项

或者每个 stage 独立一个子代理（更精细，但子代理数量更多）。

### 2.2 子代理提示词模板

子代理必须使用管线 `prompts.py` 中的系统提示词模板。如果使用独立子代理（非管线代码），必须在 prompt 中显式列出以下枚举约束清单 — 否则 LLM 会发明合法枚举之外的值。

```
你是约束提取专家。请从 {项目名} 项目中为蓝图 {蓝图ID} 的 {stage_id} 阶段提取约束。

1. 先读蓝图文件了解该阶段的定义：
   {蓝图YAML路径}

2. 然后读源码中与该阶段相关的关键文件：
   {根据蓝图 evidence 字段列出的文件列表}

3. 按 5 种 constraint_kind 逐一扫描提取约束

4. 除按 constraint_kind 扫描外，还需关注以下横切维度（容易遗漏）：
   - 时间语义：as-of time、交易日历、时区处理
   - 数值精度：float vs Decimal、收敛条件
   - 前视偏差：shift/lag、训练/测试分割
   - 守恒约束：PnL 守恒、跨模块一致性

5. machine_checkable 判定标准：

   标注 `true` 的条件（满足任一）：
   - 约束包含可 grep/regex 检查的具体值（参数名、阈值、常量）
   - 检查方式可描述为"读某字段/文件/配置，确认其值等于/不等于/包含 X"
   - M 类约束（数学模型参数）——几乎都可通过 grep 源码验证

   标注 `false` 的条件（满足任一）：
   - 约束依赖业务场景理解（"应避免过拟合"）
   - 验证需要运行代码并分析结果（"回测净值曲线无前视偏差"）
   - BA 类风险提示，没有具体的值可检查

## 【强制】合法枚举值清单（不可发明新值）

modality（只能选以下 4 种）：
  must / must_not / should / should_not

constraint_kind（只能选以下 6 种）：
  domain_rule / resource_boundary / operational_lesson / architecture_guardrail / claim_boundary / rationalization_guard

consequence_kind（只能选以下 9 种）：
  bug / performance / financial_loss / data_corruption / service_disruption / operational_failure / compliance / safety / false_claim

severity（只能选以下 4 种）：
  fatal / high / medium / low

source_type（只能选以下 7 种）：
  code_analysis / document_extraction / community_issue / official_doc / api_changelog / cross_project / expert_reasoning

consensus（只能选以下 4 种）：
  universal / strong / mixed / contested

target_scope（只能选以下 3 种）：
  global / stage / edge

freshness（只能选以下 3 种）：
  stable / semi_stable / volatile

## 输出格式

JSON 数组，每条约束包含：
  when, modality, action, consequence_kind, consequence_description,
  constraint_kind, severity, confidence_score, source_type, consensus, freshness,
  target_scope, stage_ids, evidence_summary, machine_checkable, promote_to_acceptance

  validation_threshold（可选）: 当约束的 consequence 可量化时，标注异常判定阈值。
    格式："条件 → 判定"
    示例："abs(annual_return) > 500% → WARN"、"holding_change_pct > 100% → FAIL"
    仅当约束的 consequence_kind 属于 {financial_loss, data_corruption, bug} 且后果可量化时填写。
    不确定时不填。

## 关键规则

  - 每条约束只表达一个独立可验证的规则
  - evidence_summary 必须引用实际源码文件:行号
  - 禁止编造 — Unknown 就说 Unknown
  - action 禁止使用模糊词（考虑、注意、建议、适当、尽量）
  - when 必须用编码时视角（"编写/实现 X 时"），不用运行时视角（"X 被调用时"）
  - action 中用业务语义（"当前 K 线 open 价"），不用源码常量（"row[OPEN_IDX]"）
  - 【禁止】发明上述枚举清单之外的值。如果不确定该选哪个，选最接近的合法值
  - 不要自行编 ID，ID 由管线自动分配

## 【强制】consequence_description 质量要求

  每条约束的 consequence_description 字段必须满足：
  - 字数 ≥20 字
  - 描述具体的失败现象（例如："回测净值曲线出现未来函数偏差，导致策略在实盘中收益率远低于回测结果"）
  - 禁止只填 consequence_kind 的值（"bug"、"performance" 等单词）
  - 禁止填写模糊表述（"结果不正确"、"程序出错"、"性能下降"）

## 【强制】提交前违规自检清单

  生成 JSON 后，在提交前对每条约束逐一核对：
  □ modality 是否属于：must / must_not / should / should_not
  □ constraint_kind 是否属于：domain_rule / resource_boundary / operational_lesson / architecture_guardrail / claim_boundary / rationalization_guard
  □ consequence_kind 是否属于：bug / performance / financial_loss / data_corruption / service_disruption / operational_failure / compliance / safety / false_claim
  □ severity 是否属于：fatal / high / medium / low
  □ source_type 是否属于：code_analysis / document_extraction / community_issue / official_doc / api_changelog / cross_project / expert_reasoning
  □ consensus 是否属于：universal / strong / mixed / contested
  □ target_scope 是否属于：global / stage / edge
  □ freshness 是否属于：stable / semi_stable / volatile
  □ consequence_description 是否 ≥20 字且描述具体失败现象
  如有任何违规，在提交前自行修正，不要输出含违规条目的 JSON。
```

### 2.3 Claim Boundary 专项

claim_boundary 最容易遗漏，需要专项提取：

```
补充输入（不限于源码）：
- README 中的 disclaimer/limitation
- 蓝图的 applicability.not_suitable_for
- 领域常识（如"历史收益不代表未来"）

核心问题：
"如果用户基于此蓝图构建了系统，他可能对外宣称哪些能力？
 哪些宣称是危险的、不可支撑的、或违反行业惯例的？"
```

---

## Step 2.1-s: 文档约束提取（文档知识源）

**条件**：蓝图提取 SOP 步骤 0 探测到文档知识源时执行。当前 59 个金融蓝图全部是纯代码，此步骤跳过。随着 AI 金融项目（FinRL agent 配置等）出现，此步骤将启用。

### 子代理提示词模板

```
你是约束提取专家。请从文档知识源中为蓝图 {蓝图ID} 提取约束。

1. 先读蓝图文件了解整体结构：{蓝图YAML路径}

2. 读取以下文档知识源：
   {SKILL.md 路径}
   {resources 中 technique_document 的文件路径列表}
   {CLAUDE.md 路径（如有）}

3. 按以下文档特征模式扫描约束：

   | 文档特征 | 约束类型 | 典型信号 |
   |---------|---------|---------|
   | "NEVER/MUST/ALWAYS + 具体行为" | domain_rule 或 architecture_guardrail | 全大写强调词 |
   | "Common Mistakes" / "Anti-patterns" | operational_lesson | 段落标题 + 列表 |
   | "Not suitable for" / "Limitations" | claim_boundary | 否定句式 |
   | 环境假设（"requires X"） | resource_boundary | 前提条件 |
   | 阶段间顺序强制 | architecture_guardrail | 顺序/依赖 |

4. 置信度规则：

   | 场景 | source_type | confidence_score |
   |------|-----------|-----------------|
   | 文档声明 + 代码中有对应实现（aligned） | code_analysis | 0.9 |
   | 文档显式声明，未验证代码（doc_only） | document_extraction | 0.6 |
   | 从多个文档段落推断 | expert_reasoning | 0.5 |

5. evidence 格式：kind=document_section, path=文件路径, section_id="§段落标题", evidence_role=normative/example/rationale/anti_pattern

## 【强制】合法枚举值清单
{复用 Step 2.2 中的枚举值清单}

## 【强制】提交前违规自检清单
{复用 Step 2.2 中的自检清单}
```

### 与代码约束的去重

文档约束和 Step 2.1-2.3 代码约束可能表达同一条规则。入库时：
- 语义等价且一致 → 合并为一条，两路 evidence 都保留，置信度提升至 0.9（两个独立来源互相印证）
- 矛盾 → 两条都保留，标注 `conflict: true`，置信度各自下调 0.1

### 过度声明检测（文档约束后处理）

对所有 `source_type=document_extraction` 且 `modality=must/must_not` 的约束执行反证扫描：

```bash
grep -rn "{约束关键行为的反面}" /tmp/{repo}/ --include='*.py' | grep -v test
```

| 扫描结果 | 处理 |
|---------|------|
| 未找到反例 | 保持原 modality |
| 找到 1+ 例外 | modality 降级为 should/should_not，标注 `overclaim_risk: true` |
| 例外仅在测试/mock 中 | 保持原 modality |

---

## Step 2.6: Rationalization Guard 专项提取

**条件**：项目中存在反合理化内容时执行。以下任一命中即执行：
- 蓝图 `extraction_methods` 含文档知识源
- 项目含 SKILL.md / CLAUDE.md / AGENTS.md
- 项目含 CONTRIBUTING.md 且内含行为禁令
- 代码注释中有"DO NOT TOUCH/REMOVE/CHANGE"模式

当前 59 个金融蓝图绝大多数跳过。部分项目（如含 CONTRIBUTING.md 的开源框架）可能触发代码知识源的补充扫描。

### 扫描来源

文档知识源：
- SKILL.md 的 "Common Rationalizations" / "Red Flags" 段落
- CREATION-LOG.md 的 "Bulletproofing Elements" 段落
- 使用 ❌/✅ 对比表的段落

代码知识源（补充扫描）：
- CONTRIBUTING.md 中的行为禁令
- 源码注释中的 "DO NOT TOUCH/REMOVE/CHANGE" 模式

### 子代理提示词模板

```
你是 AI 行为约束提取专家。请从文档中提取 rationalization_guard 约束。

读取文档：{SKILL.md 路径 + CREATION-LOG.md 路径}

扫描模式：
- "Common Rationalizations" 表格 → 每个借口-反驳对 = 1 条约束
- "Red Flags" 列表 → 每条 = 1 条约束
- ❌ 行为 = 1 条约束

约束格式：
- constraint_kind: rationalization_guard（固定）
- when: agent 可能出现该合理化的场景
- modality: must_not
- action: 简洁的禁止声明（如"禁止以'问题太简单'为由跳过根因调查"）
- severity: 根据跳步破坏的内容判断 — 破坏 correctness/compliance = fatal，降低质量 = high，影响效率 = medium
- source_type: document_extraction
- evidence_role: anti_pattern

额外必填字段 guard_pattern（rationalization_guard 专有）：
  "guard_pattern": {
    "excuse": "借口原文",
    "rebuttal": "反驳",
    "red_flags": ["思维信号1", "思维信号2"],
    "violation_detector": "可检测的违规行为描述"
  }

{复用 Step 2.2 中的枚举值清单}
```

---

## Step 2.4: 蓝图驱动的业务约束派生

**前提**：蓝图已按 SOP v3.6 升级，包含 `business_decisions` 和 `known_use_cases` 字段。

**为什么需要**：Step 2.1-2.3 从源码提取的约束偏向技术架构（"框架怎么实现的"）。但蓝图升级后标注了业务决策（B/BA/DK/RC/M）和已知缺失（status: missing），这些需要对应的约束来告诉 AI "必须注意什么"和"不能忽略什么"。A 股监管规则（涨跌停、印花税、ST）和业务假设风险几乎不会被 Step 2.1-2.3 捕获，必须从 business_decisions 专项派生。

### 2.4.1 派生来源与规则

从蓝图 `business_decisions` 中按 type 派生，每条派生约束必须包含溯源字段：

```json
"derived_from": {
  "blueprint_id": "finance-bp-009",
  "business_decision_id": "涨跌停板处理",
  "derivation_version": "sop-v2.0"
}
```

**派生规则表**：

| 蓝图 type | 派生什么 | constraint_kind | 派生规则 |
|-----------|---------|-----------------|---------|
| **RC** | 监管规则约束 | `domain_rule` | 每条 RC 派生 1 条 must/must_not。modality 取决于内容 |
| **B** | 行为规则约束 | `domain_rule` | **选择性派生**：仅对"AI 高概率会改动且改了后果严重"的 B 派生。典型：执行顺序（先卖后买）、时序规则（信号延迟）、聚合规则（score averaging） |
| **BA** | 风险提示约束 | `operational_lesson` | 满足以下三条件之一即派生：①会显著改变结果 ②AI 高概率默认继承 ③继承后结果失真而不自知。不限于 known_issue 标注 |
| **M** | 模型约束 | `domain_rule` 或 `architecture_guardrail` | 每条 M 派生 1 条约束。模型假设和适用边界必须转为 must/must_not。模型选择影响精度的用 `domain_rule`，影响系统架构的用 `architecture_guardrail`。M 类约束如果涉及数值参数（如模型参数、阈值），应同时标注 validation_threshold。示例：M "MACD (12,26,9)" → 约束 action="MACD 参数必须为 fast=12, slow=26, signal=9"，validation_threshold="macd_fast != 12 OR macd_slow != 26 OR macd_signal != 9 → FAIL" |
| **missing** | **双联约束**（boundary + remedy） | `claim_boundary` + `domain_rule` 或 `operational_lesson` | 每条 missing gap 派生 **2 条**：第 1 条 must_not "禁止假设框架已处理 X"；第 2 条 must/should "应该如何处理 X" |

**不派生的**：
- type=T 的纯技术选择 → 不需要约束
- type=DK 且不影响交易合法性/可执行性/数据解释 → 不派生
- resource_boundary → 已由 Step 2.1-2.3 覆盖
- M：~3-5 条 per blueprint（仅含数学模型的蓝图）

**关于 missing gap 双联约束**：

单独一条"禁止假设"只让 AI 变谨慎，不让 AI 变正确。必须配对 remedy。

```
❌ 只生成 1 条：
  "must_not 假设框架处理了涨跌停"
  → AI 知道不行，但不知道怎么办

✅ 生成 2 条：
  claim_boundary: "must_not 假设框架处理了涨跌停"
  domain_rule: "must 在选股时过滤涨停股，或对涨停价订单建模为不成交"
  → AI 既知道不行，又知道该怎么做
```

**remedy 约束的可执行性硬标准**：

remedy 约束的 action 必须包含 AI 可直接执行的具体操作。禁止空话。

```
❌ 空话 remedy（FAIL）：
  "should 考虑涨跌停对策略的影响"
  "should 添加流动性折价注释"

✅ 可执行 remedy（PASS）：
  "must 在选股时检查 close >= prev_close * 1.1（涨停），过滤或标记为不可成交"
  "must 当 close == prev_close * 0.9（跌停）时，将持仓估值标记为 illiquid"
```

判断标准：如果 action 中没有具体的**数据字段、阈值、代码操作**，只有"考虑/注意/关注"，则判定为 FAIL。

**remedy 约束的原子性**：

每条 remedy 只能包含一个独立的行动规则。涨停和跌停是两个独立场景，必须拆成两条。

**source_type 默认规则**：

| 蓝图 type | 默认 source_type | 理由 |
|-----------|-----------------|------|
| RC | `official_doc`（法规/交易所规则）| 监管规则是法规事实，不是专家推理 |
| B | `code_analysis`（从源码行为推导）| 业务决策来自代码实现 |
| BA | `expert_reasoning`（对假设的风险判断）| 假设的风险是推理产物 |
| M | `code_analysis`（从源码中的模型实现推导）| 模型选择来自代码实现 |
| missing | `code_analysis`（确认源码中不存在）| 缺失是通过代码分析确认的 |

**关于 B 类选择性派生**：

B 的定义 = "改了会改变交易行为"。约束的职责 = "防止 AI 把关键行为改坏"。两者天然重叠。

但不是所有 B 都派生。过滤条件：
1. AI 在代码重构时是否高概率会改动这个行为？（如"先卖后买"看起来像可优化的代码顺序）
2. 改了以后是否会导致严重后果？（如改为先买后卖导致隐性加杠杆）
3. 现有 Step 2.1-2.3 约束是否已覆盖？（已覆盖则不重复）

### 2.4.2 子代理提示词模板

```
你是约束派生专家。请从蓝图的 business_decisions 中派生业务约束。

1. 读取蓝图文件：{蓝图YAML路径}
2. 找到 business_decisions 段落
3. 按以下规则逐条派生约束：

## 派生规则

### RC（监管规则）→ domain_rule 约束
对每条 type=RC 的 business_decision：
- when: 用编码时视角描述触发场景
- modality: must 或 must_not（根据法规要求）
- action: 描述必须遵守的监管要求
- consequence_kind: compliance（监管违规）或 financial_loss（经济损失）
- severity: fatal（监管硬约束通常是 fatal）
- source_type: official_doc（法规/交易所规则，不是专家推理）
- evidence_summary: 引用蓝图中的 evidence 字段

示例（从蓝图 RC "A 股普通股 T+1 交割制度"派生）：
{
  "when": "实现 A 股回测的持仓管理逻辑时",
  "modality": "must",
  "action": "确保当日买入的股票不可当日卖出（T+1 交割制度），通过 trading_t 属性控制可用量",
  "consequence_kind": "compliance",
  "consequence_description": "违反 T+1 规则会导致回测中出现 A 股市场不允许的当日回转交易，使回测结果在实盘中完全不可复现",
  "constraint_kind": "domain_rule",
  "severity": "fatal",
  "source_type": "official_doc"
}

### BA（业务假设）→ operational_lesson 约束
满足以下三条件之一即派生（不限于 known_issue 标注）：①会显著改变结果 ②AI 高概率默认继承 ③继承后结果失真而不自知。
- when: 用编码时视角描述使用该默认值的场景
- modality: should
- action: 提醒应调整或验证该默认值
- consequence_kind: financial_loss
- severity: medium 或 high
- source_type: expert_reasoning

示例（从蓝图 BA "sell_cost=0.001 可能低估"派生）：
{
  "when": "使用 zvt 框架的默认卖出成本参数进行回测时",
  "modality": "should",
  "action": "验证 sell_cost=0.001 是否匹配实际券商费率（印花税0.05% + 佣金），必要时调整为实际值",
  "consequence_kind": "financial_loss",
  "consequence_description": "默认 sell_cost 将印花税、佣金、过户费合并为 0.1%，对部分账户偏高对部分偏低，高频策略下成本误差会累积放大",
  "constraint_kind": "operational_lesson",
  "severity": "medium"
}

### M（数学/模型选择）→ domain_rule 或 architecture_guardrail 约束
对每条 type=M 的 business_decision：
- when: 用编码时视角描述使用该模型/方法的场景
- modality: must 或 must_not（根据模型适用边界）
- action: 描述模型假设、适用条件或数值方法要求
- consequence_kind: bug（精度问题）或 financial_loss（定价/估值错误）
- severity: high 或 fatal（模型选错通常是高影响）
- source_type: code_analysis

示例（从蓝图 M "Black-Scholes 解析定价"派生）：
{
  "when": "为美式期权定价时",
  "modality": "must_not",
  "action": "使用 Black-Scholes 解析公式——BS 不支持 early exercise，美式期权必须使用二叉树或有限差分方法",
  "consequence_kind": "financial_loss",
  "consequence_description": "Black-Scholes 解析公式忽略 early exercise premium，对深度实值美式看跌期权系统性低估价格，误差可达 5-10%",
  "constraint_kind": "domain_rule",
  "severity": "fatal"
}

### missing gap → claim_boundary 约束
对每条 status=missing 的 business_decision：
- when: 用编码时视角描述触发场景
- modality: must_not
- action: 禁止假设框架已处理该功能
- consequence_kind: 根据 impact 字段判断
- severity: 继承蓝图标注的 severity
- source_type: code_analysis（确认源码中确实不存在）

示例（从蓝图 missing "涨跌停板处理"派生）：
{
  "when": "在 A 股回测中处理买入/卖出订单时",
  "modality": "must_not",
  "action": "假设框架已处理涨跌停板限制——zvt 当前未实现涨跌停过滤，涨停价买单和跌停价卖单会被视为可全额成交",
  "consequence_kind": "financial_loss",
  "consequence_description": "未处理涨跌停时，动量策略回测会系统性高估收益率（假设可在涨停价全额买入），追涨策略尤为严重",
  "constraint_kind": "claim_boundary",
  "severity": "fatal"
}

## 【强制】合法枚举值清单
{复用 Step 2.2 中的枚举值清单}

## 【强制】consequence_description 质量要求
{复用 Step 2.2 中的质量要求}

## 【强制】提交前违规自检清单
{复用 Step 2.2 中的自检清单}
```

### 2.4.3 预期产出量

| 蓝图 type | 预估派生约束数 | 下限警戒 |
|-----------|-------------|---------|
| RC | 4-6 条 | < 3 条需 review |
| B（选择性） | 3-5 条 | < 2 条需 review |
| BA（三条件过滤） | 4-6 条 | < 3 条需 review |
| M（含数学模型的蓝图） | 3-5 条 | < 2 条需 review |
| missing gap（双联） | **14 条**（每条 2 条：boundary + remedy） | 必须 = gap 数 × 2 |
| **合计** | **28-36 条** | < 20 条需 review |

### 2.4.4 与 Step 2.1-2.3 的去重

派生的约束可能和现有约束重叠。入库时按以下规则去重：
- 用 `core.when` + `core.action` 的语义相似度判断
- 重叠时保留更具体、severity 更高的那条
- 标注 `relations: [{type: "supplements", target: "finance-C-XXX"}]`

**例外**：RC 约束和 missing gap 约束即使语义重叠也**不去重**，因为它们表达不同层次：
- RC 约束（domain_rule）= 监管事实存在，告诉 AI 这个规则必须遵守
- missing 约束（claim_boundary）= 框架能力边界，告诉 AI 框架没实现它

两者必须共存，通过 `relations: [{type: "supplements"}]` 相互引用。

---

## Step 2.5: 审计发现的约束转化

**前提**：蓝图提取 SOP 步骤 2c 的 20 项金融通用必审 + 子领域必审清单产出了审计发现（❌/⚠️/✅），部分已转入蓝图 `business_decisions`。本步骤将**未被 Step 2.4 覆盖的审计发现**直接转化为约束。

**触发条件**：蓝图 `audit_checklist_summary` 中存在 `fail > 0` 的清单项，且对应项未在 `business_decisions` 中标注。

### 转化规则

| 审计结论 | 约束类型 | modality | source_type |
|---------|---------|---------|-------------|
| ❌ 框架能力缺失 | `claim_boundary` | `must_not` — 禁止假设框架已处理 | `code_analysis` |
| ❌ 实现有已知缺陷 | `operational_lesson` | `should` — 注意并验证 | `code_analysis` |

- 每条约束必须包含 `derived_from`，格式：`{source: "audit_checklist", item: "审计项名称", sop_version: "3.2"}`
- severity 继承审计判定（Critical→fatal, High→high, Medium→medium）
- 仅转化 High/Critical 级别的 ❌ 发现

### 跨蓝图通用约束处理

以下审计发现在 59 个蓝图中普遍适用（如 T+1、时区处理），入库时检查全局约束池：
- 已存在语义等价的全局约束 → 在新蓝图的 `relations` 中引用，不重复入库
- 不存在 → 正常入库，设 `applies_to.target_scope = "global"`

---

## Step 3: 入库

### 3.1 从子代理输出提取 JSON

子代理返回的 JSON 数组嵌套在 agent output 中，需要解析提取。使用 `scripts/ingest_constraints.py`（需适配 agent output 格式）。

### 3.2 转换为 Constraint 对象

每条 raw JSON → `Constraint` Pydantic 模型：
- 自动分配 ID（`{domain}-C-{序号}`）
- 自动计算 hash（`sha256(core + scope)[:16]`）
- 设置 `version.status = "draft"`
- 设置 `blueprint_ids = [当前蓝图ID]`

**Draft 扁平 → Production 嵌套字段映射**：

| Draft 字段 | Production 位置 |
|-----------|---------------|
| `when` | `core.when` |
| `modality` | `core.modality` |
| `action` | `core.action` |
| `consequence_kind` + `consequence_description` | `core.consequence.kind` + `core.consequence.description` |
| `source_type` | `confidence.source_type` |
| `confidence_score` | `confidence.score` |
| `consensus` | `confidence.consensus` |
| `evidence_summary` | `confidence.evidence_refs[0].summary` |
| `target_scope` + `stage_ids` + `edge_ids` | `applies_to.target_scope` + `applies_to.stage_ids` + `applies_to.edge_ids` |
| `derived_from` | 顶级字段保留（非标准字段，入库脚本透传） |

转换通过 `scripts/ingest_constraints.py` 的 `raw_to_constraint()` 自动完成。

### 3.3 Pydantic 模型验证

**入库前必须通过 Pydantic `Constraint` 模型验证。** 验证失败的约束不入库，而是记录到 `_rejected.jsonl` 供人工修复。

```python
from doramagic_constraint_schema.types import Constraint

try:
    constraint = Constraint(**raw_json)
except ValidationError as e:
    # 记录到 _rejected.jsonl，不入库
    log_rejection(raw_json, str(e))
    continue
```

这一步会自动捕获所有枚举越界问题（非法 modality/constraint_kind/consequence_kind 等）。

### 3.4 业务校验

通过 `validate_constraint()` 校验：
- 三元组完整性（when/action/consequence 非空）
- 模糊词检测
- 原子性检测
- 证据要求（非 expert_reasoning 必须有 evidence_refs）
- applies_to 一致性（stage_ids/edge_ids 在蓝图中存在）

### 3.5 写入 JSONL

`knowledge/constraints/domains/{domain}.jsonl`

---

## Step 4: 后处理修复（6 项规则）

运行 `scripts/fix_constraints_review.py`（或手动检查）：

| 规则 | 检测条件 | 修复动作 |
|------|---------|---------|
| **P0a** | `source_type=expert_reasoning` 且 `score > 0.7` | 降为 0.7 |
| **P0b** | `constraint_kind=domain_rule` 且 `action` 含源码实现细节 | 改为 `architecture_guardrail` |
| **P1** | `when` 含运行时视角（"被调用时"、"is called"） | 改为编码时视角（"实现/编写 X 时"） |
| **P2** | `action` 含源码 API（`self.__xxx`、`name mangling`） | 用业务语义替代 |
| **P3** | `when` 纯英文（中文字符 < 10%） | 翻译为中文（技术术语保留英文） |
| **P4** | `consequence` 含"不可预期"等模糊词或 < 20 字，或值等于 consequence_kind 枚举词（"bug"、"performance"） | 补充具体失败现象，至少描述"什么情况下触发 + 导致什么具体结果" |
| **P5** | `action` 含 `row[XXX_IDX]` 等硬编码常量 | 用业务语义替代（"当前 K 线最低价"） |

---

## Step 5: 质量验证

### 5.1 自动化扫描

运行修复后验证脚本，确认 7 项指标全部归零。

### 5.2 抽样评审（可选，首次必做）

- 随机抽取 5 条约束
- 构建评审提示词（参考 `constraint-quality-review-prompt.md`）
- 发送给 2-3 个外部模型独立评审
- 6 维度打分：正确性、原子性、可执行性、后果量化、证据质量、元数据准确性
- 目标：平均分 ≥ 4.5/5

### 5.3 kind 分布检查

确认 6 种 constraint_kind 的覆盖：
- `claim_boundary` ≥ 5%（最容易遗漏）
- `domain_rule` 和 `architecture_guardrail` 合计 ≥ 50%
- `rationalization_guard`：含文档知识源的蓝图 ≥ 1 条；纯代码蓝图允许 0 条

### 5.4 质量基线

| 指标 | 基线值 |
|------|--------|
| 约束总数 | 100-200 条/蓝图（Step 2.1-2.3 代码提取约 60-150 条 + Step 2.4 蓝图派生约 28-36 条 + Step 2.5 审计转化约 5-15 条） |
| 三方评审平均分 | ≥ 4.5/5 |
| P0-P5 后处理修复后残留 | 0 |
| claim_boundary 占比 | ≥ 5% |
| 每条约束有 evidence_refs | 100%（expert_reasoning 除外） |
| 所有约束 status=draft | 100%（人工审阅后改 active） |
| validation_threshold 覆盖率 | M 类 + severity=fatal 的约束中 ≥30% 有 validation_threshold | — |
