# 蓝图提取流水线操作手册（通用模板）

> **本文件是维护用模板，不直接执行。**
> 执行时请使用对应领域的完整 SOP（如 `finance/blueprint-extraction-sop.md`）。
>
> 模板版本：基于 SOP v3.4
> 用途：新增领域时，从本模板出发 + 注入领域知识 → 生成领域 SOP
>
> 模板注入点标记格式：`<!-- DOMAIN: 说明 -->`
> 编译新领域 SOP 时，将所有注入点替换为领域特定内容。

---

## 经验教训总表（驱动本 SOP 每条规则的来源）

| # | 教训 | 来自哪个项目 | 影响的步骤 |
|---|------|------------|-----------|
| L1 | LLM 总结 ≠ 事实，关键时序逻辑被遗漏 | 框架提取实验 | 步骤 2b |
| L2 | 文档推测 vs 读代码，索引类型容易假设出错 | 框架提取实验 | 步骤 2b |
| L3 | @abstractmethod 数量被假设而非验证 | 框架提取实验 | 步骤 2b, 3 |
| L4 | 过度概括（"唯二 @abstractmethod"） | 框架提取实验 | 步骤 2b |
| L5 | 第二个项目提取精细度下降（replaceable_points 退化为字符串） | 多项目批量提取 | 步骤 4 |
| L6 | 行号会漂移，需要函数签名双锚点 | 代码评审 | 步骤 4 |
| L7 | "所有实现外部包" 过度概括 | 代码评审 | 步骤 4 |
| L8 | 跨蓝图对比表可能自相矛盾 | 代码评审 | 步骤 5 |
| L9 | 验证规则需要分层（通用/领域/项目族） | 四方共识 | 步骤 3 |
| L10 | Warning 应区分"特征缺失"和"提取错误" | 模型评审 | 步骤 3 |
| L11 | stages order 字段必须严格递增，不能有重复值 | 蓝图审计 | 步骤 4 |
| L12 | source.commit_hash 是必需字段，必须记录提取时的 commit | 蓝图审计 | 步骤 4 |
| L13 | global_contracts 仅放架构不变式，实现特征放 source.evidence | 三方评审 | 步骤 4 |
| L14 | replaceable_points 必须覆盖三维度：数据源/执行模式/存储后端 | 三方评审 | 步骤 4 |
| L15 | 字段名跨蓝图必须一致（如统一用 commit_hash 而非 commit） | 一致性审计 | 步骤 5 |
| L16 | YAML 特殊字符（' { } : [ ]）必须加引号包裹，Step 4 组装后必须执行 yaml.safe_load 验证 | YAML 解析失败 | 步骤 4 |
| L17 | "所有"/"全部" 是最高频 L7 违规词，Step 4 组装时应主动替换为精确表述，目标 ≤3 次 | 批量提取审计 | 步骤 4 |
| L18 | relations 字段必须在 Step 4 中主动填充，至少声明 1 条与同子领域蓝图的关系 | 批量提取审计 | 步骤 4 |
| L19 | global_contracts 必须作为标准顶级字段存在（不可用替代字段名），至少 3 条架构不变式 | 批量提取审计 | 步骤 4 |
| L20 | "唯一"出现频率高需在 Step 4 检查清单中列为必查项 | 批量提取审计 | 步骤 4 |
| L21 | exec 禁止清单必须穷举所有 shell 操作符，不能只举一个例子 | 晶体测试 | 步骤 2c |
| L22 | 规格锁必须覆盖所有可变参数，不能只锁策略类型 | 晶体测试 | 步骤 2c |
| L23 | 代码模板必须给可执行的正确 API 调用示例，不能只给伪代码注释 | 晶体测试 | 步骤 2c |
| L24 | 蓝图中的 design_decisions 混合了技术选择和业务决策，必须分类标注 | 蓝图审计 + 四方评审 | 步骤 2c |
| L25 | 默认参数值往往编码了隐式业务假设，必须审视其业务理由 | 蓝图审计 | 步骤 2c |
| L26 | 领域特有强制规则必须作为 RC 类决策显式记录 | 四方评审共识 | 步骤 2c |
| L27 | 业务逻辑不仅在 examples 中，更隐藏在基类默认行为、Schema 字段选择、继承层级中 | 提取实验 | 步骤 2c, 2d |
| L28 | RC（监管规则）与 B（框架实现选择）混在一条时必须拆成两条 | 四方评审 | 步骤 2c |
| L29 | known_use_cases 必须包含结构化字段（intent_keywords、required_components 等） | 四方评审 | 步骤 2d |
| L30 | 必审清单必须包含执行可行性/流动性约束 | 四方评审共识 | 步骤 2c |
| L31 | replaceable_points 必须包含当前主流资源选项，列出 Python 依赖包清单，存储后端必须有替代方案描述 | 资源审视 | 步骤 4 |
| L32 | M 类（数学/模型选择）遗漏比 B 类遗漏更难补救，M 类判定需同时满足三条件 | bp-009 验证 | 步骤 2c |
| L33 | 审计发现（❌/⚠️）必须有明确的转化规则——转入 business_decisions 还是直接转约束 | bp-009 验证 | 步骤 2c |
| L34 | 蓝图 YAML 头部注释的 SOP 版本必须与实际使用的 SOP 版本一致，否则误导追溯 | bp-009 验证 | 步骤 4 |
| L35 | 审计发现到约束的转化路径是蓝图 SOP 和约束 SOP 的接缝，双方都必须有规则 | bp-009 验证 | 步骤 2c |
| L36 | 用例消歧需要 negative_keywords + 排除词 + 消歧问题 + 数据域标注，否则运行时误匹配 | 四方评审共识 + bp-009 v1.8 实测 | 步骤 2d |
| L37 | BD 只标注类型不写 rationale = 蓝图有 WHAT 无 WHY，晶体编译时丢失业务语义 | bp-009 v4.1 自动提取 vs 人工精修对比（30KB vs 111KB，差距全在 rationale 深度） | 步骤 2c |
| L38 | Missing gap（代码应有但未实现的业务逻辑）必须由审计清单驱动显式输出，不能仅从代码中发现 | bp-009 v4.1 自动提取产出 0 条 missing gap，人工版 7 条 | 步骤 2c |
| L39 | stages 的 required_methods 和 key_behaviors 是必填字段，空值必须标注"该阶段无用户接口"——缺失导致晶体编译时无法生成接口契约 | v5 自动提取蓝图 Codex 审计：7 个 stage 全部缺失 required_methods | 步骤 4 |
| L40 | known_use_cases 字段名必须是 source（非 source_file）+ intent_keywords（非 negative_keywords 替代），agent 容易用近似名替代标准名 | v5 自动提取蓝图 Codex 审计：32 个 UC 全部使用非标准字段名 | 步骤 2d |
| L41 | missing gap 的 BD 必须同时包含 status: missing 和 known_gap: true，缺少 known_gap 字段会导致下游约束管线无法识别已知缺陷 | v5 自动提取蓝图 Codex 审计 | 步骤 2c |
| L42 | 项目是光谱（纯代码↔纯 skill），提取策略按知识源类型选择，不按项目分类——同一项目的 .py 用逆向、SKILL.md 用萃取 | 非代码提取研究 2026-04-14 | 步骤 0, 2a |
| L43 | 资源（子技术文档/工具脚本/代码示例/外部服务）是蓝图一等组件（产品宪法 §1.3），必须显式捕获到 resources 字段 | 非代码提取研究 2026-04-14 | 步骤 4 |
| L44 | 文档知识源的 evidence 用 section 级引用（file:§section + evidence_role），不是行号——防止把例子误当规则 | 非代码提取研究 2026-04-14 | 步骤 4 |
| L45 | SKILL.md 的 "When to Use" 段是激活语义，不是简单描述——必须提取到 applicability.activation | 非代码提取研究 2026-04-14 | 步骤 2a-s |
| L46 | 非代码知识源的架构是显式的（作者已写出），提取是萃取不是逆向——置信度天然更高但仍需步骤 2b 验证 | 非代码提取研究 2026-04-14 | 步骤 2a-s, 2b |

<!-- DOMAIN: 可在此追加领域特有的经验教训 -->

---

## 概述

蓝图提取是一个**人机协作的 8 步流程**。

项目是光谱（纯代码 ↔ 纯 skill），同一项目可能同时包含代码知识源和文档知识源。
步骤 0 探测知识源类型，步骤 2a 按知识源类型选择提取策略。

```
步骤 0: 指纹探针    — 判定子领域 + 探测知识源类型（代码/文档/配置/混合）
步骤 1: Clone        — 自动（git clone）
步骤 2a: 粗提取      — 代码知识源：LLM 子代理读源码（产出架构骨架）
步骤 2a-s: 结构化萃取 — 文档知识源：LLM 子代理读 SKILL.md/CLAUDE.md（产出架构骨架）
                       混合项目：步骤 2a + 2a-s 都执行，产出合并
步骤 2b: 声明验证    — LLM 子代理逐条验证关键声明（代码用源码验证，文档用原文对照）
步骤 2c: 业务决策标注 — 用 T/B/BA/DK/RC/M 六分类审视已提取内容（所有知识源类型通用）
步骤 2d: 业务用例扫描 — 扫描 examples/notebooks/When-to-Use 提取用例索引
步骤 3: 自动验证     — 脚本 grep 检查（代码源）+ 结构完整性检查（文档源）
步骤 4: 组装蓝图     — 基于验证结果写 YAML（统一 schema，含 resources/activation）
步骤 5: 一致性检查   — 检查新蓝图与已有蓝图的交叉引用
步骤 6: 多模型评审   — 四方评审（Claude/GPT/Gemini/Grok）
```

**绝对规则：步骤 2b 不可跳过。**
**绝对规则：步骤 2c 不可跳过。**

---

## 步骤 0: 指纹探针

**目的**：判定项目子领域 + 探测知识源类型，决定后续步骤的提取策略。

### 0a. 知识源类型探测

```bash
# 代码知识源
find /tmp/{repo} -name "*.py" -o -name "*.ts" -o -name "*.go" -o -name "*.rs" -o -name "*.java" | head -30

# 文档知识源
find /tmp/{repo} -name "SKILL.md" -o -name "CLAUDE.md" -o -name "AGENTS.md" -o -name "GEMINI.md" | head -20
ls /tmp/{repo}/skills/ 2>/dev/null
ls /tmp/{repo}/.claude/ 2>/dev/null
find /tmp/{repo} -name "*.prompt" -o -name "*.prompt.md" | head -10

# 配置知识源
find /tmp/{repo} -name "hooks.json" -o -name "settings.json" -o -name "manifest.json" | head -20
find /tmp/{repo} -name "*.yaml" -o -name "*.toml" -o -name "*.tf" | grep -v node_modules | grep -v __pycache__ | head -20

# 评测知识源
find /tmp/{repo} -name "evals.json" -o -name "*eval*" -o -name "*benchmark*" | head -10
```

### 0b. 知识源类型判定

| 条件 | 知识源类型 | 步骤 2 策略 |
|------|-----------|------------|
| 有 `.py/.ts/.go/.rs` 源码文件且含业务逻辑 | **代码** | 执行步骤 2a（逆向） |
| 有 `SKILL.md`/`CLAUDE.md`/`AGENTS.md` 或 `skills/` 目录 | **文档** | 执行步骤 2a-s（萃取） |
| 有 `hooks.json`/`settings.json` 等配置文件含行为规则 | **配置** | 在步骤 2a 或 2a-s 中一并处理 |
| 同时满足代码 + 文档条件 | **混合** | 步骤 2a + 2a-s 都执行，产出合并 |

将探测结果记录到 `/tmp/{repo}_fingerprint.md`：
```
知识源类型: [code, document, config]  # 可多选
代码入口: {entry_points}
文档资产: {SKILL.md 列表}
配置资产: {hooks/settings 列表}
子领域: {subdomain}
```

<!-- DOMAIN: 此处注入领域特化的指纹探测规则（如量化金融的子领域探测：TRD/INS/LND/TRS/AML）-->

---

## 步骤 1: Clone

```bash
git clone --depth 1 https://github.com/{owner}/{repo} /tmp/{repo}
```

**记录 commit hash**（教训 L6：行号会漂移，需要锁定版本）：
```bash
cd /tmp/{repo} && git rev-parse HEAD > /tmp/{repo}_commit.txt
```

---

## 步骤 2a: 粗提取

启动 Claude Code 子代理，使用以下 prompt：

```
你是一位资深软件架构师。请从 /tmp/{repo}/ 的源码中提取架构骨架。

任务清单：
1. 找入口 → 追踪调用链 → 报告主循环完整序列
2. 列出顶级子包，识别核心 vs 辅助
3. 找用户接口（ABC/Protocol/基类）：
   - 对每个方法，用 grep 检查 @abstractmethod（不能假设，必须验证）
   - 报告参数类型、返回类型、文件路径、行号、函数签名
4. 找数据模型：
   - 读 converter/datahandler 代码确认列名和索引类型（不能从文档推测）
   - 确认索引/数据结构类型，必须引用具体代码行
5. 找执行模型：
   - 主循环结构
   - 信号传递方式
   - 搜索 shift/delay 关键词确认是否有延迟机制
6. 找核心逻辑实现位置
7. 找辅助子系统（参数优化、ML、通知、筛选等）
8. 对整个仓库执行完整的 @abstractmethod 扫描：
   grep -rn '@abstractmethod' /tmp/{repo}/ --include='*.py' | grep -v test
   报告所有位置，按类分组统计总数（不要说"唯一"或"唯二"）

对每个发现必须包含：
- 文件路径 + 行号 + 函数签名（三者缺一不可）
- 实际代码片段
- 你的解读

不要猜测。看不出来写"未确认"。
写入 /tmp/{repo}_extract_round1.md
```

<!-- DOMAIN: 此处可注入领域特化的步骤 2a 补充检查项（如：量化金融需额外检查 shift/延迟机制；Web 框架需额外检查路由注册方式）-->

---

## 步骤 2a-s: 结构化萃取（文档知识源）

**条件**：步骤 0 探测到文档知识源时执行。混合项目与步骤 2a 并行执行，产出合并。

启动 Claude Code 子代理，使用以下 prompt：

```
你是一位 AI 知识架构师。请从 /tmp/{repo}/ 的文档知识源中提取架构骨架。

知识源清单（从步骤 0 指纹获取）：
{SKILL.md / CLAUDE.md / AGENTS.md 文件列表}

任务清单：
1. 对每个 SKILL.md / agent 定义文件：
   a. 提取阶段结构（phases/steps → stages）
   b. 提取每阶段的输入/输出/方法/验收条件
   c. 提取可替换点（如"可以用 X 也可以用 Y"）
   d. 提取激活语义（"When to Use" / "When NOT to Use" 段落）
   e. 提取关联资源（子技术文档/工具脚本/代码示例/参考文件）
   f. 提取跨 skill 关系（引用/依赖/互补/包含）

2. 对项目级文件（CLAUDE.md / README.md）：
   a. 提取全局契约（铁律/不可违反的规则）
   b. 提取设计哲学和质量标准
   c. 提取贡献规范中隐含的质量约束

3. 对配置知识源（hooks.json / settings.json）：
   a. 提取行为规则（什么事件触发什么动作）
   b. 提取权限模型（什么被允许/禁止/需确认）

对每个发现必须包含：
- 文件路径 + section 标题（如 SKILL.md:§Phase-1-Step-4）
- 原文引用（保留关键措辞）
- 知识角色标注：normative（规则）/ example（示例）/ rationale（理由）

不要猜测。原文没写的写"未确认"。
写入 /tmp/{repo}_extract_structural.md
```

### 与步骤 2a 的产出合并

混合项目（代码 + 文档）的两路产出按以下规则合并：

| 维度 | 代码产出（2a） | 文档产出（2a-s） | 合并规则 |
|------|--------------|----------------|---------|
| stages | 从代码逆向的阶段 | 从文档萃取的阶段 | 同一阶段合并；不同阶段各自保留 |
| global_contracts | 从代码中推断的不变式 | 从文档中显式声明的规则 | 全部保留，标注来源（code_observed / doc_declared） |
| resources | evidence 中的 API/数据源 | 显式列出的子技术/工具/示例 | 合并到统一 resources 列表 |
| activation | 无（代码蓝图无此维度） | 从 "When to Use" 萃取 | 直接使用文档产出 |
| business_decisions | 从代码推断的设计选择 | 从文档显式的设计决策 | 全部保留，标注来源 |

**冲突处理**（代码与文档不一致时）：

代码是运行时事实，文档是意图声明。文档会腐烂，代码不会骗人。

| 冲突场景 | 处理 |
|---------|------|
| 文档声明了 X，代码确实实现了 X | `aligned` — 正常写入蓝图 |
| 文档声明了 X，代码未实现 X | `doc_only` — 写入蓝图但标注 `verification: unimplemented`，降级为参考而非事实 |
| 代码实现了 X，文档未提及 | `code_only` — 正常写入蓝图，evidence 来自代码 |
| 文档说 X，代码实际做 Y（矛盾） | `divergent` — 两者都写入，标注 `conflict: true`，交由人工裁决 |

<!-- DOMAIN: 此处注入领域特化的结构化萃取补充检查项 -->

---

## 步骤 2b: 声明验证（不可跳过）

从步骤 2a / 2a-s 的报告中提取所有事实性声明（通常 8-12 条），按知识源类型选择验证策略。

### 验证策略路由

| 知识源类型 | 验证方法 | 工具 |
|-----------|---------|------|
| 代码 | 源码 grep + 行号验证 | grep/rg + 源码阅读 |
| 文档 | 原文对照 + 语义忠实度检查 | 原文引用 + LLM 交叉验证 |
| 混合 | 代码声明走源码验证，文档声明走原文对照，跨源声明走交叉验证 | 两种工具都用 |

### 代码声明验证（步骤 2a 产出）

启动子代理：

```
你是代码审计专家。请对以下声明逐一做源码验证。

仓库路径：/tmp/{repo}/

## 待验证声明
{从 round 1 报告中提取的声明列表}

## 必须检查的高风险项（三大必查）

### 必查 1：执行时机
- 搜索 shift/delay 关键词
- 搜索注释中的 "future"、"look-ahead"、"previous"
- 如果是事件驱动，确认撮合和策略调用的先后顺序

### 必查 2：数据结构
- DataFrame 的索引类型：读创建 DataFrame 的代码（不是使用的代码）
- 确认索引/数据结构类型

### 必查 3：@abstractmethod 完整性
- grep -rn '@abstractmethod' 完整扫描
- 按类分组报告，给出精确总数
- 绝对不要使用"唯一"、"唯二"等说法

## 额外检查：过度概括风险
- 声明中是否有"所有"、"全部"、"唯一"等绝对化表述？
- 如果有，验证是否真的没有例外

## 输出格式
对每条声明：
  声明: "xxx"
  验证结果: ✅ / ❌ / ⚠️
  源码证据: file:line(function_name) — 实际代码
  差异说明: （如不一致）

写入 /tmp/{repo}_verify_round2.md
```

### 文档声明验证（步骤 2a-s 产出）

**条件**：步骤 0 探测到文档知识源时执行。

文档验证不能用 grep，因为文档声明的是意图而非实现。验证方法是原文对照 + 语义忠实度。

启动子代理：

```
你是知识提取审计专家。请验证以下从文档中提取的声明是否忠实于原文。

源文件目录：/tmp/{repo}/

## 待验证声明
{从步骤 2a-s 报告中提取的声明列表}

## 验证方法
对每条声明：
1. 找到原文出处（文件路径 + section 标题）
2. 引用原文关键段落
3. 判断提取结论是否忠实于原文（没有添加、遗漏、歪曲）
4. 判断知识角色是否正确标注（normative/example/rationale/anti_pattern）
   - normative：原文明确要求"必须/禁止/总是/永远不"
   - example：原文是具体案例/代码示例/场景描述
   - rationale：原文解释"为什么这么做"
   - anti_pattern：原文明确列出的错误做法/合理化借口/红旗信号

## 高风险检查
- 提取结论是否把"示例"误当成了"规则"？
- 提取结论是否遗漏了原文的"例外条件"？
- 原文的条件限定（"当 X 时"/"仅在 Y 情况下"）是否被保留？

## 输出格式
对每条声明：
  声明: "xxx"
  验证结果: ✅ faithful / ⚠️ partial / ❌ distorted
  原文出处: file:§section
  原文引用: "关键段落"
  知识角色: normative / example / rationale / anti_pattern
  差异说明: （如不完全忠实）

写入 /tmp/{repo}_verify_structural.md
```

### 跨源交叉验证（混合项目）

**条件**：步骤 2a + 2a-s 都执行时，对两路产出做交叉验证。

检查每条文档声明是否在代码中有对应实现：
```bash
# 对 2a-s 提取的每条 normative 声明，在代码中搜索相关实现
grep -rn "{关键行为}" /tmp/{repo}/ --include='*.py' | grep -v test
```

| 结果 | 处理 |
|------|------|
| 代码中找到对应实现 | `aligned` — 标注为高置信度 |
| 代码中未找到实现 | `doc_only` — 标注 `verification: unimplemented` |
| 代码实现与文档矛盾 | `divergent` — 标注 `conflict: true`，交由人工裁决 |

写入 `/tmp/{repo}_cross_verify.md`

---

## 步骤 2c: 业务决策标注（不可跳过）

**目的**：用业务决策视角重新审视步骤 2a/2b 已提取的内容，区分"技术架构"和"业务决策"。

### 业务决策分类框架（六类）

| 类型 | 代码 | 定义 | 判断准则 |
|------|------|------|---------|
| 技术选择 | **T** | 换一种实现方式，业务结果不变 | "改了这个，产出结果会变吗？" → 不变 = T |
| 业务决策 | **B** | 直接规定系统怎么做，换了就改变行为 | "改了这个，系统的行为会变吗？" → 会变 = B |
| 业务假设 | **BA** | 编码了对领域/市场/用户的假设，是 B 的"为什么" | "这个默认值/规则背后假设了什么？" |
| 领域知识 | **DK** | 特定领域的制度/文化知识（非通用惯例） | "换个领域，这条还成立吗？" → 不成立 = DK |
| 外部强制规则 | **RC** | 外部规则/标准/平台强加的硬约束，非框架作者的选择 | "这是作者决定的，还是外部强制的？" → 强制 = RC |
| 数学/模型选择 | **M** | 基于数学推导或统计假设的方法选择 | "换了模型/方法，结果精度或含义会变吗？" → 会 = M |

**B 和 BA 的边界**：
- B = 系统的规则（"怎么做"）
- BA = 规则背后的假设（"为什么这么做"）
- 同一条内容可以双标注 B/BA（允许）
- 不确定时优先标 B

**M 和 B 的边界**（教训 L32）：
- M 必须同时满足以下三条：
  ① 选择背后有显式的数学/统计理论（可引用公式名称、论文、教材）
  ② 换一种方法，结果的**数值精度或统计含义**会变（不只是"行为会变"）
  ③ 方法的适用边界依赖数学假设（如正态分布、线性假设、样本量要求）
- 只满足"改了行为会变"但不涉及数学理论 → 标 B
- 满足三条 → 标 M（允许同时标 M/B 或 M/BA）
- 不确定时 → 标 M/BA（宁多标不漏标——M 类遗漏比 B 类遗漏更难通过约束补救）

**RC 与 B/BA 混合时必须拆成两条**（教训 L28）

**DK 的使用范围**：仅用于特定领域的制度/文化知识，不用于通用惯例

### 审视方法

```
输入：步骤 2a 的粗提取报告 + 步骤 2b 的验证报告
输出：业务决策标注清单（每条标注 T/B/BA/DK/RC + 业务理由）

审视对象（按优先级）：
1. design_decisions    — 每条追问"技术选择还是业务决策？"
2. 默认参数值          — 每个追问"为什么是这个值？换了会改变结果吗？"
3. Schema 字段选择     — 追问"为什么这些字段是一等公民？体现了什么领域认知？"
4. 基类默认行为        — 追问"这个默认顺序/默认值编码了什么业务规则？"
5. 数学模型选择        — 追问"为什么选这个模型/算法？假设了什么？替代方案是什么？"
6. 数值方法与精度      — 追问"收敛条件是什么？容差多少？精度和性能的权衡？"
7. 校准与估计方法      — 追问"模型参数怎么估计的？用了什么数据？假设了什么分布？"
8. 边界条件处理        — 追问"极端情况怎么处理？溢出/发散/不收敛时的 fallback？"
9. acceptance_hints    — 区分"技术验证"和"业务验证"
```

<!-- DOMAIN: 此处注入领域必审清单（如量化金融的 11 项 A 股必审项：涨跌停/T+1/印花税/停牌/ST/除权/新股/成分股/交易成本/先卖后买/流动性）-->

### 输出格式

```
## 业务决策标注清单

### 阶段：{stage_name}

| # | 内容 | 类型 | 业务理由 |
|---|------|------|---------|
| 1 | "{决策内容}" | B | {为什么是 B} |
| 2 | "{参数名}={默认值}" | B/BA | {为什么是 B/BA} |
| 3 | "{外部规则}" | RC | {法规/标准来源} |

### 遗漏的业务决策
- {缺失功能}：源码中未实现 → 必须在蓝图中标注为已知缺陷
- ...

写入 /tmp/{repo}_business_decisions.md
```

### 审计发现处理规则（教训 L33, L35）

步骤 2c 中领域必审清单的审计结论，按以下规则转化为 business_decisions：

| 审计结论 | 处理动作 | 写入蓝图 YAML |
|---------|---------|-------------|
| ❌ 框架未实现 | 转入 `business_decisions`，设 `status: missing`，severity 继承审计判定 | 是 |
| ❌ 实现有已知缺陷 | 转入 `business_decisions`，标注 type + `known_issue` 描述 | 是 |
| ⚠️ 部分实现有风险 | 转入 `business_decisions`，type=BA，rationale 中标注风险 | 是 |
| ✅ 已正确实现 | 不转化为 business_decision — 已通过 design_decisions 覆盖 | 否 |

High/Critical 级别的 ❌ 发现**必须**转化。Medium 级别的 ❌ 和 ⚠️ 视覆盖度判断。

### 审计汇总落盘

组装蓝图时，在 YAML 中新增 `audit_checklist_summary` 字段：

```yaml
audit_checklist_summary:
  sop_version: "{SOP版本}"
  executed_at: "{日期}"
  subdomain_labels: ["{子领域代码}"]  # <!-- DOMAIN: 步骤 0 指纹探针结果 -->
  <!-- DOMAIN: 按领域填写各清单的 pass/warn/fail 统计 -->
  critical_findings:
    - item: "{审计项名称}"
      severity: "{级别}"
      disposition: "converted_to_bd"
```

---

## 步骤 2d: 业务用例扫描

**目的**：扫描项目的 examples/notebooks/tutorials，建立业务用例索引。

### 扫描范围

```
代码知识源优先级：
P0: examples/**/*.py          — 完整可运行策略/用例
P1: notebooks/**/*.ipynb      — 端到端研究/演示流程
P2: docs/tutorials/**/*       — 结构化教程
P3: README.md Quick Start     — 最小可用示例
P4: 源码中继承基类的内置实现   — 内置组件

文档知识源优先级：
P0: SKILL.md 的 "When to Use" 段      — 激活条件和触发场景
P1: SKILL.md 的 "Common Mistakes" 段   — 反向用例（不应该用的场景）
P2: CREATION-LOG.md 的测试场景          — 已验证的压力测试用例
P3: README.md 的 workflow 描述          — 技能调用拓扑中的使用场景
```

### 执行方法

```bash
# 自动扫描目录结构
find /tmp/{repo} -path "*/examples/*.py" -o -path "*/notebooks/*.ipynb" -o -path "*/tutorials/*" | head -50

# 统计内置组件
grep -rn "class.*{CoreBaseClass}" /tmp/{repo}/ --include='*.py' | grep -v test | grep -v __pycache__
```

<!-- DOMAIN: 此处注入领域特化的组件搜索关键词（如量化金融：Factor/Strategy/Model/Indicator；Web 框架：View/Handler/Middleware；数据工程：Source/Sink/Transform）-->

### 输出（写入蓝图 YAML 的 known_use_cases 字段）

```yaml
known_use_cases:
  - name: "{用例名称}"
    source: "{文件路径}"
    type: "{complete_strategy | screening_logic | data_pipeline | builtin_factor | monitoring | extension_example | live_trading}"  # 按领域调整类型枚举
    business_problem: "{解决什么业务问题}"
    intent_keywords: ["{关键词1}", "{关键词2}"]
    applicable_markets: ["{适用场景}"]  # <!-- DOMAIN: 按领域填写，如量化金融用 CN_A/US/HK，Web 框架用 SSR/SPA/API -->
    required_data: ["{数据依赖}"]
    required_components: ["{必要组件}"]
    key_parameters:
      {param_name}: {param_value}
    must_validate:
      - "{验证要点1}"
      - "{验证要点2}"
    not_suitable_for: ["{不适用场景}"]
    negative_keywords: ["{与该用例容易混淆的其他用例的关键词}"]
    disambiguation: "{当用户意图可能匹配多个用例时，应问的消歧问题}"
    data_domain: "{该用例依赖的数据类型}"  # <!-- DOMAIN: 按领域定义枚举，如量化金融用 market_data | financial_data | holding_data | trading_data | mixed -->
```

**必填字段**（教训 L29）：name、source、type、business_problem、intent_keywords
**消歧字段**：negative_keywords、disambiguation、data_domain

对每个用例，检查蓝图中是否有其他用例的 intent_keywords 与该用例重叠。如有重叠，将重叠用例的关键词填入 negative_keywords，并设计 disambiguation 问题。

---

## 步骤 3: 自动验证

```bash
cd /path/to/project
python scripts/blueprint_extract.py \
  --repo-path /tmp/{repo} \
  --domain {domain} \
  --output knowledge/blueprints/{domain}/_verify_{repo}.md
```

验证完成后，如果已有蓝图 YAML，追加 evidence 行号验证：
```bash
python scripts/blueprint_extract.py \
  --repo-path /tmp/{repo} \
  --domain {domain} \
  --blueprint knowledge/blueprints/{domain}/{id}.yaml \
  --output knowledge/blueprints/{domain}/_verify_{repo}.md
```

**解读验证结果**（教训 L9, L10）：

| 状态 | 含义 | 行动 |
|------|------|------|
| ✅ pass | 特征存在且可确认 | 正常 |
| ⚠️ absent | 该项目没有此特征（设计选择不同） | 在蓝图中标注为"不适用"或"未内置" |
| ❌ fail | evidence 引用的文件/行号不存在 | 必须修正 |
| 💥 error | 验证命令执行出错 | 检查命令语法 |

**关键区分**：⚠️ absent 不是错误，是架构差异。不要把 absent 当成需要修复的问题。

---

## 步骤 4: 组装蓝图

基于 round 1 + round 2 + 步骤 3 的结果组装 Blueprint YAML。

### 蓝图存放位置
```
knowledge/blueprints/{domain}/{domain}-bp-{number}.yaml
```

### 组装规则

**规则 1：验证状态处理**
- round 2 的 ❌ 声明 → 必须修正或标注"未确认"
- round 2 的 ⚠️ 声明 → 在 notes 中说明不确定性
- round 2 的 ✅ 声明 → 直接使用

**规则 2：evidence 格式**

代码知识源（双锚点，教训 L6）：
```yaml
evidence:
  {component_name}: path/to/file.py:line_range(function_name)
  # 格式：file:line(function_name)
  # 行号 + 函数签名双锚点，防行号漂移
```

文档知识源（section 锚点 + role 标注，教训 L44）：
```yaml
evidence:
  {knowledge_item}:
    kind: document_section
    path: skills/{skill_name}/SKILL.md
    section_id: "§Phase-1-Step-4"
    evidence_role: normative  # normative=规则 / example=示例 / rationale=理由
```

**规则 3：避免过度概括（教训 L4, L7, L17, L20）**
- 禁止使用："唯一的"、"唯二的"、"所有实现都是"、"全部通过"、"所有"、"全部"
- 使用精确表述：具体数量、"各阶段"、"每个 stage"
- 组装完成后全文搜索"所有"/"全部"，目标出现次数 ≤3 次；搜索"唯一"，非标识符语境一律替换

**规则 4：@abstractmethod 报告方式**
```yaml
# 正确：报告总数 + 分布
global_contracts:
  - contract: "{N} 个 @abstractmethod 分布在 {M} 个文件"
    evidence: "{file1}({count1})+{file2}({count2})+..."

# 错误：使用"唯二"
global_contracts:
  - contract: "X 和 Y 是唯二的 @abstractmethod"  # ← 禁止
```

**规则 5：精细度检查清单（教训 L5 + L11-L14 + L16-L20）**

组装完成后，逐项检查以下内容：

| 字段 | 检查标准 | 退化/违规警告 |
|------|---------|-------------|
| replaceable_points | 每个选项有 name/traits/fit_for/not_fit_for | 退化为字符串列表 → 补回结构 |
| replaceable_points 覆盖度 | 必须覆盖三维度：数据源/执行模式/存储后端（教训 L14） | 缺任何一维 → 补充 |
| required_methods | 每个方法有 name + description + evidence | 只有方法名 → 补描述和行号 |
| required_methods 空值 | 每个 stage 至少有 1 个 required_method | 空 → 补充或标注"该阶段无用户接口" |
| design_decisions | 每条有源码证据引用 | 没有证据 → 补上或标注"推断" |
| key_behaviors | 每条有 behavior + description + evidence | — |
| stages.order | **严格递增**，不能有重复值（教训 L11） | 重复 → 必须修正 |
| global_contracts 内容 | 仅放**架构不变式**（跨阶段必须遵守的规则）（教训 L13） | 实现特征 → 移到 source.evidence |
| global_contracts 字段名（教训 L19） | 必须使用 `global_contracts` 作为顶级字段名；至少包含 3 条架构不变式 | 缺失或字段名不符 → 必须修正 |
| relations 字段（教训 L18） | 必须主动填充，至少声明 1 条与同子领域蓝图的关系 | 空列表 → 必须补充 |
| YAML 特殊字符（教训 L16） | 所有含 `' { } : [ ]` 的字符串值必须加引号包裹 | YAML 解析失败 → 检查并加引号 |
| "所有"/"全部"/"唯一" 频率（教训 L17, L20） | 全文"所有"+"全部" ≤3 次；"唯一"仅允许出现在明确的标识符/主键语境 | 超标 → 逐一替换为精确表述 |
| business_decisions（教训 L24-L26） | 步骤 2c 标注的 B/BA/DK/RC/M 类决策必须写入蓝图，至少 5 条 | 缺失 → 回步骤 2c 补充 |
| audit_checklist_summary | 审计汇总字段必须存在，包含 sop_version、subdomain_labels、各清单统计 | 缺失 → 补充 |
| known_use_cases（教训 L27） | 步骤 2d 扫描的业务用例索引，至少列出项目 examples 中的完整示例 | 缺失 → 回步骤 2d 扫描 |
| known_use_cases 消歧字段 | 每个用例必须有 negative_keywords 和 disambiguation（如有关键词重叠的用例） | 缺失 → 回步骤 2d 补充 |
| <!-- DOMAIN: 领域必审清单 --> | 领域特有的必审业务决策项是否逐项审视并记录 | 未审视 → 回步骤 2c |
| replaceable_points 资源完整性（教训 L31） | 每个数据源选项是否包含当前主流方案；是否列出依赖包清单；存储后端是否有替代选项 | 缺失主流数据源或依赖包 → 补充 |
| resources 字段（教训 L43） | 子技术文档/工具脚本/代码示例/外部服务是否全部列入 `resources`，每条有 id/type/name/path/used_in_stages | 缺失 → 从步骤 2a-s 产出补充 |
| applicability.activation（教训 L45） | 文档知识源的 "When to Use" / "When NOT to Use" 是否提取到 `activation.triggers` / `activation.anti_skip` | 有文档知识源但无 activation → 回步骤 2a-s 补充 |
| relations 类型扩展 | 跨蓝图关系是否使用了正确的 type（depends_on/complementary/contains 用于执行关系） | 所有引用都标 alternative_to → 检查是否应标 depends_on 或 contains |
| extraction_methods（教训 L42） | `source.extraction_methods` 是否列出实际使用的所有提取策略（列表，非单值） | 混合项目只标了一种策略 → 补充 |
| evidence_role（教训 L44） | 文档知识源的 evidence 是否标注了 evidence_role（normative/example/rationale） | 未标注 → 回溯原文判断并补充 |

**规则 6：记录源码版本（教训 L12）**

commit_hash 是**必需字段**，不可省略。字段名统一为 `commit_hash`（教训 L15）。

```yaml
source:
  projects: [owner/repo]
  commit_hash: "abc1234..."  # git rev-parse HEAD 的输出（必需）
  extraction_date: "{YYYY-MM-DD}"
```

**规则 7：YAML 文件必须通过 yaml.safe_load 验证（教训 L16）**

组装完成后，**提交前必须执行**：

```python
import yaml

with open("knowledge/blueprints/{domain}/{id}.yaml") as f:
    content = f.read()

try:
    yaml.safe_load(content)
    print("YAML 验证通过")
except yaml.YAMLError as e:
    print(f"YAML 解析失败: {e}")
    # 必须修复后再提交
```

**规则 8：提取流水线版本注释（教训 L34）**

每次重跑蓝图后，**必须更新** YAML 头部注释中的 SOP 版本号和重跑日期：

```yaml
# 提取流水线: SOP v{X.Y}（{重跑范围}，{日期}）
```

---

## 步骤 5: 一致性检查（教训 L8）

**5a. relations 双向一致**
**5b. 对比表事实一致**
**5c. applicability 互斥性**
**5d. 字段名一致性（教训 L15）**：`commit_hash`、`extraction_date`、`not_suitable_for`
**5e. stages 结构一致性（教训 L11）**：stages.order 严格递增

---

## 步骤 6: 多模型评审

将蓝图发给 4 个模型做独立评审（Claude/GPT/Gemini/Grok）。

### 评审维度
1. 源码忠实度
2. AI 消费品质量
3. 架构抽象质量
4. （如有多个蓝图）横向对比
5. 流水线成熟度

### 评审后行动
| 评审结果 | 行动 |
|---------|------|
| 全票通过 | 蓝图定稿 |
| 发现事实错误 | 回步骤 2b 重新验证 → 修正 → 重新评审 |
| 发现结构问题 | 在 YAML 中修改，无需重跑全流程 |
| 发现跨蓝图矛盾 | 回步骤 5 修正一致性 |

---

## 三大必查项速查卡

每次提取必须验证以下三类声明：

### 必查 1：执行时机
```bash
# 检查信号是否有 shift/延迟
grep -rn 'shift' {repo}/ --include='*.py' | grep -v test | grep -i 'signal\|entry\|exit'
# 检查事件驱动的执行顺序
grep -rn 'order\|fill\|match' {repo}/ --include='*.py' | grep -v test
```

### 必查 2：数据结构
```bash
# 检查 DataFrame 索引类型
grep -rn 'set_index\|DatetimeIndex\|as_index\|reset_index' {repo}/ --include='*.py' | grep -v test | head -20
```

### 必查 3：@abstractmethod 完整性
```bash
# 完整扫描（绝不能只做部分扫描）
grep -rn '@abstractmethod' {repo}/ --include='*.py' | grep -v test | grep -v __pycache__
# 按文件统计
grep -rn '@abstractmethod' {repo}/ --include='*.py' | grep -v test | cut -d: -f1 | sort | uniq -c | sort -rn
```

### 必查 4：数学模型选择
```bash
grep -rn 'class.*Pricer|class.*Model|class.*Estimat|class.*Optimiz|BlackScholes|GARCH|Ledoit|logistic|montecarlo|MonteCarlo' {repo}/ --include='*.py' | grep -v test
grep -rn 'tolerance|tol\b|max_iter|convergence|eps\b' {repo}/ --include='*.py' | grep -v test | head -20
```

**常见错误**：把模型选择标注为 T（技术选择），但换模型会显著影响定价/估计结果。

---

## 验证规则分层（教训 L9）

### 通用层（所有领域必检，5 项）
1. @abstractmethod 完整性
2. ABC 基类定义
3. 程序入口
4. 数据模型（DataFrame/dataclass/ORM）
5. evidence 行号可达性

<!-- DOMAIN: 此处注入领域层验证规则（如量化交易：信号 shift/延迟、费率模型、止损逻辑、主循环顺序、模拟盘等）-->

<!-- DOMAIN: 此处注入项目族特化规则（如量化：向量化机器人型/事件驱动回测型/插件化平台型）-->

### 领域层（由 <!-- DOMAIN --> 注入）
<!-- DOMAIN: 此处注入领域层验证规则（如：金融通用 20 项 + 子领域专项）-->
<!-- DOMAIN: 领域层中的必审清单缩写（如 TM/NM/QT/DS 等）是技术维度标注，与步骤 0 子领域代码是不同层级 -->

---

## 领域扩展指南

提取新领域的蓝图时：

1. 在 `scripts/blueprint_extract.py` 的 `DOMAIN_CHECKS` 中添加新领域规则
2. 复用本 SOP 的步骤 1-6，调整步骤 2a 的 prompt（替换领域相关检查项）
3. 蓝图存放在 `knowledge/blueprints/{new_domain}/`

---

## 质量追踪

<!-- DOMAIN: 此处注入领域历史质量追踪数据（项目、版次、事实错误数、SOP 版本、四方评审分、合规率）-->

| 项目 | 版次 | 事实错误 | SOP 版本 | 四方平均分 |
|------|------|---------|---------|-----------|
| {示例项目} | V1 | 0 | 本 SOP | — |

**质量目标**：事实错误 = 0，四方平均分 ≥ 90，L16-L20 合规率 = 100%，L21-L30 合规率 = 100%。

---

*通用模板 | 基于 SOP v3.2 提炼 | 编译领域 SOP 时参考此文件*
