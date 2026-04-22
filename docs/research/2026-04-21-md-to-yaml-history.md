# md → yaml 格式转换历史考古

> 调查员：Claude Sonnet 4.6（2026-04-21）
> 范围：Doramagic seed crystal 从 `.seed.md` 到 `.seed.yaml` 的全链路决策追溯
> 主要证据文件：designs/v2–v4、session23–28 worklogs、V6 design、V6.1 contingency

---

## Q1：原始 md 晶体长什么样？

### 格式与规模

最早的 md 晶体出现在 Session 2（2026-04-04），文件路径：
`knowledge/crystals/finance-bp-002-a-stock-selection.seed.md`

到 v3.4/v3.5（最后一代 md 晶体，commit `518e596`，2026-04-18），规模为：
`knowledge/sources/finance/finance-bp-009--zvt/finance-bp-009-v3.5.seed.md` — 1587 行 / 105.8 KB

典型结构（v4 design §3 记载，U 形注意力布局）：
```
1. DIRECTIVE（最高优先级）
2. FATAL CONSTRAINTS（死规则）
3. BLUEPRINT（阶段/流程）
4. RESOURCES（工具/API）
5. CONSTRAINTS（全量约束列表）
6. ACCEPTANCE（验收标准）
```

所有字段均为 Markdown 散文混合表格，没有机器可解析的结构。消费方式：宿主 AI 整体读入，自行解析含义。

### 消费方式

宿主 AI 读入整篇 md 后，自行将 `skill_crystallization` 块的指令翻译为具体 skill 文件。这个"翻译步骤"是核心问题根源（见 Q2）。

---

## Q2：消费 md 时遇到了哪些具体问题？

### 问题 1：65% 信息丢失（实测，不是估算）

`docs/designs/2026-04-04-crystal-v2-design.md`（第 29 行）：
> "中间产物暴露：编译器输出 md 文件，AI 需要自己翻译为 skill——这个翻译步骤导致 65% 信息丢失"

测试数据（v4 design §2.1）：
- Test 1：v1 md 晶体（48KB）→ 约束覆盖率 35%，验收门禁执行率 0%
- Test 2：v2 md 晶体（43KB）→ directive 执行，但输出仍为文档式，不是可运行 skill
- Test 3：纯蓝图 YAML（无 md）→ 端到端可运行系统（对照组）

### 问题 2：上下文稀释（48KB 触发 AI 宏观摘要模式）

同一文档（v4 design）：
> "上下文稀释"：48KB 以上触发 AI 进入"宏观摘要模式"，细粒度约束被跳过

根源：LLM 的"Lost in the Middle"效应（ACL 2024），中间内容注意力权重显著低于首尾。147 条约束线性排列在中间，必然丢失。

### 问题 3：指令诅咒（NeurIPS 2025）

约束越多，单条命中率越低：
> 合规率 ≈ (单条合规率)^(约束总数)

md 格式无法实现约束分级（fatal vs regular 混排），AI 无法识别哪些是硬门禁。

### 问题 4（次要，但实测可见）：字段作用域隐式

Session 27（2026-04-18）Fix A 的直接失败原因：改了 `skill_file_schema`（SR 消费）以为能影响 Notice 渲染，但 Notice 是 NR 消费 `post_install_notice.message_template`。md 格式下这种作用域问题完全不可见，yaml 格式下 v5.3 才通过 `consumer_map.yaml` 结构化解决（`docs/pitfalls.md` P-06）。

---

## Q3：转换决策过程

### 时间线（精确）

| 日期 | 事件 | 证据 |
|------|------|------|
| 2026-04-04 | v2 design 提出"约束图索引提升 AI 精准加载"（未实测，GPT 建议） | `designs/2026-04-04-crystal-v4-design.md` |
| 2026-04-04 | v2/v3/v4 设计文档仍提议"单个 md 文件"作为晶体主档 | 同上，line 379 |
| 2026-04-18 | Session 26 最后一个 .seed.md 提交（commit `518e596`，v3.5） | worklog session26 |
| **2026-04-18** | **Session 27 引入 yaml schema-driven pipeline（commit `934694c`，v5.0→v5.2）** | worklog session27 |
| 2026-04-21 | 产品宪法 v3 正式记录"晶体格式 md → seed.yaml + human_summary.md 双档" | PRODUCT_CONSTITUTION.md line 152 |

### 谁提出转换？

Session 27 worklog（`2026-04-18-session27-crystal-v51-v52-quantreview.md`）显示 v5.0 是"schema-driven pipeline"的首次落地——即 Doramagic 工程侧主动决定引入 yaml schema 驱动编译，而不是被动等待。宪法 v3（2026-04-21）在已有 yaml 实践基础上对决策做了追溯记录。

CEO 说"Claude Code 建议从 md 转成 yaml"——这与 v4 design 中 GPT 提出"约束图索引"建议相符，但那次建议当时并未落地（v4 仍输出 md）。真正的转换是 Session 27 内部工程决策，不是单次外部建议的直接响应。

### 是否有反对？

设计文档里无记录明确反对声音。v2/v3/v4 design 均惯性延续 md 输出，但到 v4 已经记录了"65% 信息丢失"的实测问题。Session 27 直接跳过 v4 进入 v5.x yaml schema，意味着工程侧在实证问题积累到一定程度后做了决断。

### 过渡处理

- v3.5.seed.md 保留在 `knowledge/sources/finance/finance-bp-009--zvt/`（存档，未删除）
- v5.0 直接生成 `.seed.yaml`，两种格式并存过了一个 session
- Session 28（同日 2026-04-19）进一步引入 `consumer_map.yaml` 和 SA-19，将 yaml 格式的消费者索引化

---

## Q4：yaml 诞生后交付了什么？没交付什么？

### 确实交付的

**消费者显式化（v5.3 session28）**：
- `consumer_map.yaml` 单一真源，7 消费者（NR/SR/TR/EX/VF/SE/MA）明确到每个字段
- SA-19 translation completeness 守卫：路径不匹配立即失败
- 实测（2026-04-19 09:25 OpenClaw）：UC 名称从英文改为中文，PIN-01 Notice 正确渲染

**结构化字段分级**：
- fatal vs regular 约束分类，AI 读取时可按键路径跳到关键约束
- `execution_directive` 显式要求"边执行边汇报"（宪法 §1.2.7）

**编译门禁系统**：
- SA-01 ~ SA-19 语义断言，quality_gate 一键全验

### 没有交付的（关键发现）

**"按键路径精确加载"从未被任何 host 实现。**

全库 grep `yaml.safe_load|keypath|jq|jsonpath|select.*seed|precise.?load|键路径` 结果：
- `yaml.safe_load` 出现在生产脚本（extraction pipeline 用）和一条 pilot 日志中的 host 伪代码生成
- **没有任何 host spec 文档或实测记录显示 host 用 key-path 加载 seed.yaml 的特定字段**
- 唯一相关 pilot 记录：`PILOT_0_V54_VS_README.md` 中 host 生成了一段 `yaml.safe_load(open('LATEST.yaml'))` 伪代码作为回答内容——这不是 key-path 加载，是 host 在"表演"使用

**V6 design 的直接确认**（§1.2，"Live consumption 五信号 0/5"）：
- EQ-02 trigger=always 从未触发
- install_recipes 14 条执行 1 条
- CA 状态机 0 次触发
- 根因 L1："晶体被锻造成'可执行合同'，但 host runtime 从设计上不 enforce 任何字段"

**V6.1 contingency Scenario B4** 进一步确认：
> "V6 seed 547KB，host 把 seed 当文档自由阅读，extension 层在 cross_project_wisdom/_shared 里但被跳过"

这和 md 时代"65% 信息丢失"的症状完全相同，只是规模从 48KB 放大到 547KB。

---

## Q5：V6 推荐写 SKILL.md——是否重蹈 md 时代覆辙？

### 直接结论：部分重蹈，但问题边界不同

**md 时代核心问题**：晶体主档是 md，host 读入后需要自行"翻译"为 skill，翻译步骤损耗 65%。

**V6.1 SKILL.md 提案的对应关系**：
- 如果 SKILL.md 是 seed.yaml 的"消费侧阅读指南"（reading order + host_reminder_template），则它是在 yaml 之上加的执行层提示，**不是**替代 yaml 成为主档
- 但如果 SKILL.md 本质上是让 host 把 yaml 当文档读（"先看哪里，再看哪里"），其实是在承认 yaml 的 key-path 精确加载已经失败，退回到"结构化文档"的定位

**实证支撑**：V6.1 contingency P3 方案（Scenario B4 触发时）：
> 在 `execution_directive` 里加 `reading_order` + `host_reminder_template`

这和 v3/v4 md 时代在 directive 块里写"优先读 FATAL，再读 BLUEPRINT"的结构完全同构。格式变了（yaml 字段 vs md heading），但信息传递机制没变——仍然是"写给 AI 的阅读指导"。

### 字段重排让 yaml 退化为顺序文档

V6.1 design 的 P2 方案提到"seed 瘦身 + reading_order"，意味着如果依赖 reading_order 驱动 host 行为，yaml 的消费模式变成了：

```
AI 读 reading_order → 知道先看 cross_project_wisdom → 按顺序看 → ...
```

这和 md 时代的 U 形注意力布局设计完全一致，只是用 YAML 字段包装了 md 段落的逻辑。

### 真正的结构性差异

有一个 md 时代不存在的新机制：**信息密度驱动**（V6 design 根因 L1 的反向推论）：
> "驱动 host 行为的是信息密度，不是字段 enforce"

V6 _shared pool（87 条精品约束 + 32 反模式 + 13 cross-wisdom + 41 KUC）能否超越 README+docs+issues，取决于内容是否是 LLM 预训练集之外的 fresh knowledge——这个维度和 md/yaml 格式无关，是 content 轴问题（V6.1 P1 路径）。

---

## 关键结论汇总

| 问题 | 结论 | 证据强度 |
|------|------|---------|
| md 时代核心问题 | 翻译损耗 65%，上下文稀释，指令诅咒 | 强（实测数据） |
| 转换时间点 | 2026-04-18 Session 27，commit `934694c` | 强（git 记录） |
| yaml 解决了什么 | 消费者显式化、字段分级、编译门禁 | 强（SA-19 实测） |
| yaml 没解决什么 | key-path 精确加载从未落地；host 仍自由阅读 | 强（全库 grep + V6 0/5 信号） |
| V6 SKILL.md 是否重蹈 | 机制上与 md 时代 directive 同构，但 content 轴问题更根本 | 中（推断，待实测验证） |
| 宪法溯源引用准确性 | 宪法 §3.4 line 112 引用 session28 为 yaml 决策源头，但 session28 已在 yaml 基础上做 v5.3 升级；真正的 md→yaml 转换在 session27 | 强（worklog 文本对比） |

---

## 对 CEO 的一句话判断

**yaml 解决了"格式混乱"问题，没解决"host 不执行合同"问题；V6 推 SKILL.md + reading_order 在机制上是 md 时代 directive 块的 yaml 复刻，护城河能否成立取决于 _shared pool 内容是否超出 LLM 预训练集覆盖范围——这才是 V6.1 P1 vs P2 路径选择的真正赌注。**

---

*生成时间：2026-04-21*
*调查范围：designs v2-v6 + session22-28 worklogs + V6/V6.1 design + V6 pilot 0 全量日志*
*全库 grep 验证：无任何 host 实现 key-path 精确加载的证据*
