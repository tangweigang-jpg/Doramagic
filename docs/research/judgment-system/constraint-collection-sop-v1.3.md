# 约束采集 SOP v1.3

> 蓝图驱动约束采集的标准操作流程
> 日期：2026-04-06
> v1.0 基于 finance-bp-001 (freqtrade) 首轮校准经验
> v1.1 基于 7 蓝图批量提取合规审计反馈（35.7% 合规率 → 目标 95%+）
> v1.2 基于 Batch 1+2 提取经验（新增 L13-L14：consequence_description 质量问题 + 枚举值发明问题）
> v1.3 基于 bp-009 蓝图升级（SOP v2.3）+ 四方评审共识：新增 Step 2.4（蓝图驱动的业务约束派生），新增 L15-L17

---

## 前提条件

- 蓝图已提取并通过四方评审（YAML 文件就绪）
- `constraint_schema` + `constraint_pipeline` 包已安装
- 目标项目可通过 git clone 获取

---

## 流程概览

```
Step 1: Clone 项目
Step 2: 并行子代理提取（per stage + edges/global/claims）
Step 2.4: 蓝图驱动的业务约束派生 [v1.3 新增]
Step 3: 入库（JSON → Constraint → JSONL）
Step 4: 后处理修复（6 项规则）
Step 5: 质量验证（扫描 + 抽样评审）
```

预计耗时：每个蓝图 ~30 分钟（子代理并行提取 ~5 分钟，入库+修复 ~10 分钟，验证 ~15 分钟）

---

## Step 1: Clone 项目

```bash
mkdir -p repos
git clone --depth 1 https://github.com/{owner}/{repo}.git repos/{repo}
```

记录 commit hash，写入约束的 evidence_refs 中。

---

## Step 2: 并行子代理提取

### 2.1 按 stage 拆分任务

每个蓝图的 stages 拆为独立子代理任务。对于 4-5 个 stage 的蓝图：

- **子代理 A**：stage 1 + stage 2（如 data_pipeline + strategy_engine）
- **子代理 B**：stage 3 + stage 4（如 trade_loop + evaluation_reporting）
- **子代理 C**：edges + global + claim_boundary 专项

或者每个 stage 独立一个子代理（更精细，但子代理数量更多）。

### 2.2 子代理提示词模板（v1.1 强化版）

**关键变更（L8）**：子代理必须使用管线 `prompts.py` 中的系统提示词模板。如果使用独立子代理（非管线代码），必须在 prompt 中显式列出以下枚举约束清单。

```
你是约束提取专家。请从 {项目名} 项目中为蓝图 {蓝图ID} 的 {stage_id} 阶段提取约束。

1. 先读蓝图文件了解该阶段的定义：
   {蓝图YAML路径}

2. 然后读源码中与该阶段相关的关键文件：
   {根据蓝图 evidence 字段列出的文件列表}

3. 按 5 种 constraint_kind 逐一扫描提取约束

## 【强制】合法枚举值清单（不可发明新值）

modality（只能选以下 4 种）：
  must / must_not / should / should_not

constraint_kind（只能选以下 5 种）：
  domain_rule / resource_boundary / operational_lesson / architecture_guardrail / claim_boundary

consequence_kind（只能选以下 9 种）：
  bug / performance / financial_loss / data_corruption / service_disruption / operational_failure / compliance / safety / false_claim

severity（只能选以下 4 种）：
  fatal / high / medium / low

source_type（只能选以下 6 种）：
  code_analysis / community_issue / official_doc / api_changelog / cross_project / expert_reasoning

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

## 关键规则

  - 每条约束只表达一个独立可验证的规则
  - evidence_summary 必须引用实际源码文件:行号
  - 禁止编造 — Unknown 就说 Unknown
  - action 禁止使用模糊词（考虑、注意、建议、适当、尽量）
  - when 必须用编码时视角（"编写/实现 X 时"），不用运行时视角（"X 被调用时"）
  - action 中用业务语义（"当前 K 线 open 价"），不用源码常量（"row[OPEN_IDX]"）
  - 【禁止】发明上述枚举清单之外的值。如果不确定该选哪个，选最接近的合法值
  - 不要自行编 ID，ID 由管线自动分配

## 【强制】consequence_description 质量要求（教训 L13）

  每条约束的 consequence_description 字段必须满足：
  - 字数 ≥20 字
  - 描述具体的失败现象（例如："回测净值曲线出现未来函数偏差，导致策略在实盘中收益率远低于回测结果"）
  - 禁止只填 consequence_kind 的值（"bug"、"performance" 等单词）
  - 禁止填写模糊表述（"结果不正确"、"程序出错"、"性能下降"）

## 【强制】提交前违规自检清单（教训 L14）

  生成 JSON 后，在提交前对每条约束逐一核对：
  □ modality 是否属于：must / must_not / should / should_not
  □ constraint_kind 是否属于：domain_rule / resource_boundary / operational_lesson / architecture_guardrail / claim_boundary
  □ consequence_kind 是否属于：bug / performance / financial_loss / data_corruption / service_disruption / operational_failure / compliance / safety / false_claim
  □ severity 是否属于：fatal / high / medium / low
  □ source_type 是否属于：code_analysis / community_issue / official_doc / api_changelog / cross_project / expert_reasoning
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

## Step 2.4: 蓝图驱动的业务约束派生（v1.3 新增）

**前提**：蓝图已按 SOP v2.3 升级，包含 `business_decisions` 和 `known_use_cases` 字段。

**为什么需要**：Step 2.1-2.3 从源码提取的约束偏向技术架构（"框架怎么实现的"）。但蓝图升级后标注了业务决策（B/BA/DK/RC）和已知缺失（status: missing），这些需要对应的约束来告诉 AI "必须注意什么"和"不能忽略什么"。

bp-009 实证：56 条现有约束中只有 3 条涉及 A 股规则，蓝图标注的 7 个 critical/high 缺失（涨跌停、停牌、ST 等）在约束侧完全没有对应。

### 2.4.1 派生来源与规则

从蓝图 `business_decisions` 中按 type 派生，每条派生约束必须包含溯源字段：

```json
"derived_from": {
  "blueprint_id": "finance-bp-009",
  "business_decision_id": "涨跌停板处理",
  "derivation_version": "sop-v1.3"
}
```

**派生规则表**（CTO 决策，基于四方评审共识）：

| 蓝图 type | 派生什么 | constraint_kind | 派生规则 |
|-----------|---------|-----------------|---------|
| **RC** | 监管规则约束 | `domain_rule` | 每条 RC 派生 1 条 must/must_not。modality 取决于内容 |
| **B** | 行为规则约束 | `domain_rule` | **选择性派生**：仅对"AI 高概率会改动且改了后果严重"的 B 派生。典型：执行顺序（先卖后买）、时序规则（信号延迟）、聚合规则（score averaging） |
| **BA** | 风险提示约束 | `operational_lesson` | 满足以下三条件之一即派生：①会显著改变结果 ②AI 高概率默认继承 ③继承后结果失真而不自知。不限于 known_issue 标注 |
| **missing** | **双联约束**（boundary + remedy） | `claim_boundary` + `domain_rule` 或 `operational_lesson` | 每条 missing gap 派生 **2 条**：第 1 条 must_not "禁止假设框架已处理 X"；第 2 条 must/should "应该如何处理 X" |

**不派生的**：
- type=T 的纯技术选择 → 不需要约束
- type=DK 且不影响交易合法性/可执行性/数据解释 → 不派生
- resource_boundary → 已由 Step 2.1-2.3 覆盖

**关于 missing gap 双联约束**（四方共识，L16 教训）：

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

**remedy 约束的可执行性硬标准**（教训 L21-constraint，bp-009 试点 #5 FAIL）：

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

**remedy 约束的原子性**（教训 L21-constraint，bp-009 试点 #10 FAIL）：

每条 remedy 只能包含一个独立的行动规则。涨停和跌停是两个独立场景，必须拆成两条。

**RC 派生的 source_type 默认规则**（教训 L21-constraint，bp-009 试点 #1 FAIL）：

| 蓝图 type | 默认 source_type | 理由 |
|-----------|-----------------|------|
| RC | `official_doc`（法规/交易所规则）| 监管规则是法规事实，不是专家推理 |
| B | `code_analysis`（从源码行为推导）| 业务决策来自代码实现 |
| BA | `expert_reasoning`（对假设的风险判断）| 假设的风险是推理产物 |
| missing | `code_analysis`（确认源码中不存在）| 缺失是通过代码分析确认的 |

**关于 B 类选择性派生**（GPT 主张，CTO 采纳）：

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
- source_type: expert_reasoning（法规知识）
- evidence_summary: 引用蓝图中的 evidence 字段

示例（从蓝图 RC "A 股普通股 T+1 交割制度"派生）：
{
  "when": "实现 A 股回测的持仓管理逻辑时",
  "modality": "must",
  "action": "确保当日买入的股票不可当日卖出（T+1 交割制度），通过 trading_t 属性控制可用量",
  "consequence_kind": "compliance",
  "consequence_description": "违反 T+1 规则会导致回测中出现 A 股市场不允许的当日回转交易，使回测结果在实盘中完全不可复现",
  "constraint_kind": "domain_rule",
  "severity": "fatal"
}

### BA（业务假设）→ operational_lesson 约束
仅对有 known_issue 或 rationale 中包含"偏高/偏低/低估/高估"的 BA 条目派生：
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

| 蓝图 type | bp-009 条数 | 预估派生约束数 |
|-----------|-----------|-------------|
| RC | 4 条 | 4-6 条 |
| B（选择性） | ~5 条符合过滤条件 | 3-5 条 |
| BA（三条件过滤） | ~6 条符合条件 | 4-6 条 |
| missing gap（双联） | 7 条 | **14 条**（每条 2 条：boundary + remedy） |
| **合计** | — | **25-31 条** |

加上现有 56 条，bp-009 的约束总数预计达到 **81-87 条**。

### 2.4.4 与 Step 2.1-2.3 的去重

派生的约束可能和现有约束重叠（如 T+1 已有 2 条）。入库时按以下规则去重：
- 用 `core.when` + `core.action` 的语义相似度判断
- 重叠时保留更具体、severity 更高的那条
- 标注 `relations: [{type: "supplements", target: "finance-C-XXX"}]`

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

### 3.3 Pydantic 模型验证（v1.1 新增，教训 L10）

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
| **P4** | `consequence` 含"不可预期"等模糊词或 < 20 字，或值等于 consequence_kind 枚举词（"bug"、"performance"）（教训 L13） | 补充具体失败现象，至少描述"什么情况下触发 + 导致什么具体结果" |
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

确认 5 种 constraint_kind 都有覆盖：
- `claim_boundary` ≥ 5%（最容易遗漏）
- `domain_rule` 和 `architecture_guardrail` 合计 ≥ 60%

---

## 质量基线（来自 freqtrade 首轮校准）

| 指标 | 基线值 |
|------|--------|
| 约束总数 | 100-200 条/蓝图 |
| 三方评审平均分 | ≥ 4.5/5 |
| P0-P5 后处理修复后残留 | 0 |
| claim_boundary 占比 | ≥ 5% |
| 每条约束有 evidence_refs | 100%（expert_reasoning 除外） |
| 所有约束 status=draft | 100%（人工审阅后改 active） |

---

## 经验教训（L1-L7）

| # | 教训 | 来源 |
|---|------|------|
| L1 | 不需要外部 LLM API——Claude Code 子代理本身就是 LLM | freqtrade 首轮 |
| L2 | P0b（kind 误分类）最容易过度修正——只看 action，不看 evidence | freqtrade 后处理 |
| L3 | claim_boundary 必须专项提取，否则占比趋近于零 | 四方研究共识 |
| L4 | when 必须用编码时视角，运行时视角会导致约束在 RAG 检索中失效 | Gemini 评审 |
| L5 | action 中用业务语义替代源码常量，否则约束不可移植 | Gemini+GPT 评审 |
| L6 | expert_reasoning 的 confidence 不超过 0.7 | GPT 评审 |
| L7 | 子代理按 stage 并行提取效率最高，每个 stage ~5 分钟 | freqtrade 首轮 |
| L8 | 子代理 prompt 必须使用管线 prompts.py 的模板，不能自行编写 prompt | 7 蓝图批量审计（35.7% 合规率根因） |
| L9 | 所有枚举值必须在 prompt 中显式列出合法值清单，不给 LLM 发明空间 | 7 蓝图批量审计（253 处非法枚举） |
| L10 | 入库前必须通过 Pydantic Constraint 模型验证，验证失败的不入库 | 7 蓝图批量审计（bp-004 缺 6 个字段） |
| L11 | ID 格式必须为 `{domain}-C-{三位数字}`，由管线自动分配，子代理不自行编号 | 7 蓝图批量审计（155 条 ID 格式违规） |
| L12 | consensus 字段必须从合法值（universal/strong/mixed/contested）中选择 | bp-008 审计（50 条使用非法值 "single"） |
| L13 | consequence_description 必须 ≥20 字，描述具体失败现象；sonnet 子代理倾向只填 kind 值（"bug"、"performance"），必须在 prompt 中明确要求具体描述 | Batch 1（220 条）+ Batch 2（134 条）P4 违规 |
| L14 | 即使 prompt 列出合法枚举值，sonnet 仍会发明新值（design_rule、platform_constraint、api_contract、majority 等），建议在 prompt 末尾增加"违规检查清单"要求子代理自检 | Batch 2（548 条枚举违规） |
| L15 | 源码提取的约束偏向技术架构，A 股监管规则（涨跌停、印花税、ST）和业务假设风险几乎不会被 Step 2.1-2.3 捕获，必须从蓝图 business_decisions 专项派生 | bp-009 审视：56 条约束仅 3 条涉及 A 股规则，7 个 critical/high 缺失无对应约束 |
| L16 | missing gap（蓝图中 status=missing 的已知缺陷）必须派生为 claim_boundary 约束，否则 AI 会假设框架已处理这些功能 | bp-009 四方评审：涨跌停、停牌、ST 处理缺失是 A 股回测最大风险 |
| L17 | BA 派生条件：①会显著改变结果 ②AI 高概率继承 ③继承后失真不自知——满足任一即派生，不限于 known_issue | 约束 SOP v1.3 四方评审共识（GPT 三条件检验） |
| L18 | missing gap 必须派生双联约束（boundary + remedy），只说"不要假设"不说"该怎么做"的约束是悬空护栏 | 约束 SOP v1.3 四方评审（4/4 共识） |
| L19 | B 类业务决策应选择性派生——AI 高概率会改动且改了后果严重的行为规则必须有约束保护 | GPT 评审："B 的定义和约束的职责天然重叠" |
| L20-constraint | 每条派生约束必须带 derived_from 溯源字段，否则蓝图更新时无法追踪和重算 | 约束 SOP v1.3 四方评审（4/4 共识） |
