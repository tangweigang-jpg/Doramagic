# 蓝图提取流水线操作手册（SOP v3.6）

> **领域**: Finance | 版本: 3.6 | 执行时只需阅读本文件

---

## 概述

蓝图提取是一个**人机协作的 9 步流程**。

项目是光谱（纯代码 ↔ 纯 skill），同一金融项目可能同时包含代码知识源（.py）和文档知识源（SKILL.md/CLAUDE.md）。步骤 0 探测知识源类型，步骤 2a/2a-s 按知识源类型选择提取策略。

```
步骤 0: 指纹探针    — 判定子领域 + 探测知识源类型（代码/文档/配置/混合）
步骤 1: Clone       — 自动（git clone）
步骤 2a: 架构提取   — 代码知识源：LLM 子代理读源码（产出架构骨架）
步骤 2a-s: 结构化萃取 — 文档知识源：LLM 子代理读 SKILL.md/CLAUDE.md（产出架构骨架）
                       混合项目：步骤 2a + 2a-s 都执行，产出合并
步骤 2b: 声明验证   — LLM 子代理逐条验证关键声明
步骤 2c: 业务决策标注 — 用 T/B/BA/DK/RC/M 分类审视已提取内容（所有知识源通用）
步骤 2d: 业务用例扫描 — 扫描 examples/notebooks/When-to-Use 提取用例索引
步骤 3: 自动验证    — 脚本 grep 检查（代码源）+ 结构完整性检查（文档源）
步骤 4: 组装蓝图    — 基于验证结果写 YAML（统一 schema，含 resources/activation）
步骤 5: 一致性检查  — 检查新蓝图与已有蓝图的交叉引用
步骤 6: 多模型评审  — 四方评审（Claude/GPT/Gemini/Grok）
```

**绝对规则：步骤 2b 不可跳过。** 跳过声明验证直接组装蓝图会引入多个未发现的事实错误。
**绝对规则：步骤 2c 不可跳过。** v9 晶体测试证明不标注业务决策会导致晶体缺失关键业务逻辑。

---

## 步骤 0: 项目指纹探针

在 Clone 之前，快速判断项目属于哪些金融子领域 + 探测知识源类型。

**输入**：项目 README + GitHub 描述 + 目录结构
**输出**：适用的子领域标签（可多选）+ 知识源类型（代码/文档/配置/混合）

### 0a. 知识源类型探测

Clone 后执行：
```bash
# 代码知识源
find /tmp/{repo} -name "*.py" | head -30

# 文档知识源
find /tmp/{repo} -name "SKILL.md" -o -name "CLAUDE.md" -o -name "AGENTS.md" -o -name "GEMINI.md" | head -20
ls /tmp/{repo}/skills/ 2>/dev/null
find /tmp/{repo} -name "*.prompt" -o -name "*.prompt.md" | head -10

# 配置知识源
find /tmp/{repo} -name "hooks.json" -o -name "settings.json" -o -name "manifest.json" | head -20
find /tmp/{repo} -name "*.yaml" -o -name "*.toml" | grep -v node_modules | grep -v __pycache__ | head -20

# 评测知识源
find /tmp/{repo} -name "evals.json" -o -name "*eval*" -o -name "*benchmark*" | head -10
```

| 条件 | 知识源类型 | 步骤 2 策略 |
|------|-----------|------------|
| 有 `.py` 源码文件且含业务逻辑 | **代码** | 执行步骤 2a |
| 有 `SKILL.md`/`CLAUDE.md` 或 `skills/` 目录 | **文档** | 执行步骤 2a-s |
| 同时满足代码 + 文档条件 | **混合** | 步骤 2a + 2a-s 都执行 |

**金融项目说明**：当前 59 个蓝图全部是代码知识源。随着 AI 金融项目增多（如 FinRL 的 agent 配置、量化 skill 框架），文档知识源会出现。

### 0b. 金融子领域判定

### 十一个子领域（v3.5 扩展）

| 代码 | 子领域 | 关键特征词 |
|------|--------|-----------|
| TRD | 交易与执行 | backtest, strategy, order, signal, position, broker, exchange |
| PRC | 定价与估值 | pricing, option, derivative, yield curve, volatility, Greeks |
| RSK | 风险与配置 | portfolio, optimization, risk, VaR, CVaR, allocation, factor, attribution |
| CRD | 信用与银行 | credit, scoring, PD, LGD, loan, NPL, Basel, default |
| CMP | 合规与ESG | tax, compliance, ESG, emission, regulatory, disclosure |
| DAT | 数据与研究 | data, time series, feature, database, provider, API |
| AIL | AI/LLM金融 | RL, reinforcement, fine-tune, LLM, agent, forecast, neural |
| INS | 保险与精算 | actuarial, reserving, mortality, solvency, claim, premium, cat_risk, annuity |
| LND | 贷款与支付 | loan, origination, underwriting, collection, payment, ledger, bnpl, amortization |
| TRS | 财资与ALM | treasury, alm, liquidity, irrbb, cash_pool, funding, lcr, nsfr |
| AML | 反洗钱与合规 | aml, kyc, sanction, screening, transaction_monitoring, suspicious, pep |

**规则**：
- 大多数项目匹配 1-2 个子领域
- 如果不确定，标记所有可能的子领域（宁多勿少）
- 步骤 2c 中，只需审视匹配子领域的必审清单 + 金融通用必审清单

---

## 步骤 1: Clone

```bash
git clone --depth 1 https://github.com/{owner}/{repo} /tmp/{repo}
```

**记录 commit hash** — 行号随版本漂移，commit hash 锁定提取时的代码版本：
```bash
cd /tmp/{repo} && git rev-parse HEAD > /tmp/{repo}_commit.txt
```

---

## 步骤 2a: 架构提取

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
   - 是 DatetimeIndex 还是普通列？必须引用具体代码行
5. 找执行模型：
   - 主循环结构
   - 信号传递方式
   - 搜索 shift/delay 关键词确认是否有延迟机制
6. 找核心业务逻辑实现位置
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
   c. 提取可替换点
   d. 提取激活语义（"When to Use" / "When NOT to Use"）
   e. 提取关联资源（子技术文档/工具脚本/代码示例）
   f. 提取跨 skill 关系（引用/依赖/互补/包含）

2. 对项目级文件（CLAUDE.md / README.md）：
   a. 提取全局契约（铁律/不可违反的规则）
   b. 提取设计哲学和质量标准

3. 对配置知识源（hooks.json / settings.json）：
   a. 提取行为规则（事件→动作映射）
   b. 提取权限模型（允许/禁止/需确认）

对每个发现必须包含：
- 文件路径 + section 标题（如 SKILL.md:§Phase-1）
- 原文引用
- 知识角色标注：normative（规则）/ example（示例）/ rationale（理由）

不要猜测。原文没写的写"未确认"。
写入 /tmp/{repo}_extract_structural.md
```

### 与步骤 2a 的产出合并（混合项目）

| 维度 | 代码产出（2a） | 文档产出（2a-s） | 合并规则 |
|------|--------------|----------------|---------|
| stages | 从代码逆向的阶段 | 从文档萃取的阶段 | 同一阶段合并，不同阶段各自保留 |
| global_contracts | 从代码中推断的不变式 | 从文档中显式声明的规则 | 全部保留，标注来源（code_observed / doc_declared） |
| resources | evidence 中的 API/数据源 | 显式列出的子技术/工具/示例 | 合并到统一 resources 列表 |
| activation | 无 | 从 "When to Use" 萃取 | 直接使用文档产出 |
| business_decisions | 从代码推断 | 从文档显式声明 | 全部保留，标注来源 |

**冲突处理**（代码与文档不一致时）：

代码是运行时事实，文档是意图声明。文档会腐烂，代码不会骗人。

| 冲突场景 | 处理 |
|---------|------|
| 文档声明了 X，代码确实实现了 X | `aligned` — 正常写入蓝图 |
| 文档声明了 X，代码未实现 X | `doc_only` — 写入蓝图但标注 `verification: unimplemented`，降级为参考 |
| 代码实现了 X，文档未提及 | `code_only` — 正常写入蓝图，evidence 来自代码 |
| 文档说 X，代码实际做 Y（矛盾） | `divergent` — 两者都写入，标注 `conflict: true`，交由人工裁决 |

---

## 步骤 2b: 声明验证（不可跳过）

从步骤 2a / 2a-s 的报告中提取所有事实性声明，按知识源类型选择验证策略。

### 验证策略路由

| 知识源类型 | 验证方法 | 工具 |
|-----------|---------|------|
| 代码 | 源码 grep + 行号验证 | grep/rg + 源码阅读 |
| 文档 | 原文对照 + 语义忠实度检查 | 原文引用 + LLM 交叉验证 |
| 混合 | 代码声明走源码验证，文档声明走原文对照，跨源声明走交叉验证 | 两种工具都用 |

### 代码声明验证（步骤 2a 产出）

提取所有事实性声明（通常 8-12 条），启动第二个子代理验证。

```
你是代码审计专家。请对以下声明逐一做源码验证。

仓库路径：/tmp/{repo}/

## 待验证声明
{从 round 1 报告中提取的声明列表}

## 必须检查的高风险项（四大必查）

### 必查 1：执行时机
- 搜索 shift/delay 关键词
- 搜索注释中的 "future"、"look-ahead"、"previous"
- 如果是事件驱动，确认撮合和策略调用的先后顺序

### 必查 2：数据结构
- DataFrame 的索引类型：读创建 DataFrame 的代码（不是使用的代码）
- 确认是 DatetimeIndex 还是普通列

### 必查 3：@abstractmethod 完整性
- grep -rn '@abstractmethod' 完整扫描
- 按类分组报告，给出精确总数
- 绝对不要使用"唯一"、"唯二"等说法

### 必查 4：数学模型选择- 搜索定价/估计/优化相关类名和函数（如 BlackScholes, GARCH, Ledoit, logistic）
- 确认模型假设是否显式声明（文档字符串、注释、参数名）
- 验证数值方法的收敛条件和容差（tolerance、max_iter、tol）

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

文档验证不能用 grep——文档声明的是意图而非实现。验证方法是原文对照 + 语义忠实度。

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
4. 判断知识角色标注是否正确：
   - normative：原文明确要求"必须/禁止/总是/永远不"
   - example：原文是具体案例/代码示例/场景描述
   - rationale：原文解释"为什么这么做"
   - anti_pattern：原文明确列出的错误做法/反模式/红旗信号

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
| 代码中找到对应实现 | `aligned` — 高置信度 |
| 代码中未找到实现 | `doc_only` — 标注 `verification: unimplemented` |
| 代码实现与文档矛盾 | `divergent` — 标注 `conflict: true`，交由人工裁决 |

写入 `/tmp/{repo}_cross_verify.md`

---

## 步骤 2c: 业务决策标注（不可跳过）

**目的**：用业务决策视角重新审视步骤 2a/2b 已提取的内容，区分"技术架构"和"业务决策"。

**为什么不能跳过**：蓝图中未标注的业务决策在编译晶体时会全部丢失，导致 AI 不知道该做什么具体业务事情。数学/统计模型选择是金融领域业务逻辑的核心表现形式，同样不可缺失。

### 业务决策分类框架（六类）

| 类型 | 代码 | 定义 | 判断准则 | 示例 |
|------|------|------|---------|------|
| 技术选择 | **T** | 换一种实现方式，业务结果不变 | "改了这个，投资收益/分析结论会变吗？" → 不变 = T | 用 SQLite vs PostgreSQL 存储 |
| 业务决策 | **B** | 直接规定系统怎么做，换了就改变投资行为 | "改了这个，系统的交易行为会变吗？" → 会变 = B | 先卖后买、scores 等权平均 |
| 业务假设 | **BA** | 编码了对市场/经济的假设，是 B 的"为什么" | "这个默认值/规则背后假设了什么市场规律？" | 止损 -30%（假设高容忍度）、滑点 0.1%（假设小单低冲击） |
| 领域知识 | **DK** | 特定市场的制度/文化知识（非通用量化惯例） | "换个市场（如美股→A股），这条还成立吗？" → 不成立 = DK | turnover_rate 作为一等字段（A 股特性） |
| 监管规则 | **RC** | 市场制度强加的硬约束，非框架作者的选择 | "这是作者决定的，还是法规/交易所强制的？" → 强制 = RC | T+1 交割、涨跌停 ±10%、印花税 0.05% |
| 数学/模型选择 | **M** | 基于数学推导或统计假设的方法选择 | "这是基于数学/统计理论的选择吗？换了模型/方法，结果精度或含义会变吗？" → 会 = M | Black-Scholes 定价、Ledoit-Wolf 协方差收缩、GARCH(1,1) 波动率模型、logistic regression PD 建模、蒙特卡洛 10 万路径 |

**B 和 BA 的边界**：
- B = 系统的规则（"怎么做"）
- BA = 规则背后的假设（"为什么这么做"）
- 同一条内容可以双标注 B/BA（允许）
- 不确定时优先标 B（保守策略，宁可多标不可漏标）

**M 和 B 的边界**：
- M 必须同时满足以下三条：
  ① 选择背后有显式的数学/统计理论（可引用公式名称、论文、教材）
  ② 换一种方法，结果的**数值精度或统计含义**会变（不只是"行为会变"）
  ③ 方法的适用边界依赖数学假设（如正态分布、线性假设、样本量要求）
- 只满足"改了行为会变"但不涉及数学理论 → 标 B
- 满足三条 → 标 M（允许同时标 M/B 或 M/BA）
- 不确定时 → 标 M/BA（宁多标不漏标——M 类遗漏比 B 类遗漏更难通过约束补救）

**RC 与 B/BA 混合时必须拆成两条**：
- 当"法规事实"和"框架实现选择"混在一条时，必须拆成独立两条
- 例：❌ 错误写法：`"T+1 信号延迟执行" type: RC` — 混合了法规和实现
- ✅ 正确写法：拆成两条：
  - `"A 股普通股 T+1 交割制度" type: RC` — 法规事实（不可变）
  - `"主循环结构将信号执行延迟到下一周期" type: B` — 框架实现选择（可变）
- 判断依据：问"如果换个市场（无 T+1 约束），框架的这个实现选择还存在吗？" → 如果还在 = B，如果消失 = 纯 RC

**DK 的使用范围**（仅限特定市场制度/文化知识，不用于通用量化惯例）：
- ✅ 仅用于特定市场的制度/文化知识：A 股换手率分析文化、中国散户主导市场结构
- ❌ 不用于通用量化惯例：MultiIndex [entity_id, timestamp] 是所有量化框架的通用做法，不算 DK

### 审视对象（按优先级，v3.0 扩展）

```
输入：步骤 2a 的架构提取报告 + 步骤 2b 的验证报告
输出：业务决策标注清单（每条标注 T/B/BA/DK/RC/M + 业务理由）

审视对象（按优先级）：
1. design_decisions    — 每条追问"技术选择还是业务决策？"
2. 默认参数值          — 每个追问"为什么是这个值？换了会改变结果吗？"
3. Schema 字段选择     — 追问"为什么这些字段是一等公民？"
4. 基类默认行为        — 追问"这个默认编码了什么业务规则？"
5. 数学模型选择 — 追问"为什么选这个模型/算法？假设了什么？替代方案是什么？"
6. 数值方法与精度 — 追问"收敛条件是什么？容差多少？精度和性能的权衡？"
7. 校准与估计方法 — 追问"模型参数怎么估计的？用了什么数据？假设了什么分布？"
8. 边界条件处理 — 追问"极端情况怎么处理？溢出/发散/不收敛时的 fallback？"
```

### 金融通用必审清单（20 项，适用所有金融项目）

以下 20 项跨子领域的金融工程陷阱，**无论项目类型都必须逐项审视**。

每项的"常见标注"列中的缩写含义：TM=时间语义, NM=数值方法, QT=定量分析, DS=数据结构, CV=校准验证, ST=状态管理, DP=设计模式, RC=监管规则。这些缩写用于标注必审项的技术维度，与步骤 0 的七个子领域代码（TRD/PRC/RSK/CRD/CMP/DAT/AIL）是不同层级：子领域代码标注项目属于哪个业务领域，必审项缩写标注检查项属于哪个技术维度。

#### Category 1: 时间语义

| # | 必审项 | 搜索关键词 | 常见标注 |
|---|--------|-----------|---------|
| 1 | as-of time vs processing time 区分 | `as_of`, `evaluation_date`, `reference_date`, `snapshot_time` | TM |
| 2 | 交易日历与自然日历隔离 | `timedelta`, `BDay`, `calendar`, `holiday` | TM |
| 3 | 时区显式标注与 UTC 归一化 | `tzinfo`, `tz_localize`, `tz_convert`, `pytz` | TM |

#### Category 2: 数值精度

| # | 必审项 | 搜索关键词 | 常见标注 |
|---|--------|-----------|---------|
| 4 | float vs Decimal 货币计算 | `Decimal`, `round()`，检查金额变量类型 | NM |
| 5 | 收敛标准与容差显式声明 | `tolerance`, `tol`, `max_iter`, `convergence` | NM/QT |
| 6 | 矩阵病态性与稳定性 | `np.linalg.inv`, `cholesky`, `cond`, `regularize` | NM/QT |

#### Category 3: 数据谱系

| # | 必审项 | 搜索关键词 | 常见标注 |
|---|--------|-----------|---------|
| 7 | Point-in-Time 数据可用性 | `release_date`, `publish_date`, `point_in_time` | DS/TM |
| 8 | Stale data 检测与过期策略 | `last_update`, `staleness`, `max_age`, `cache_ttl` | DS/TM |

#### Category 4: 守恒与一致性

| # | 必审项 | 搜索关键词 | 常见标注 |
|---|--------|-----------|---------|
| 9 | PnL 守恒（realized + unrealized = total） | `realized_pnl`, `unrealized_pnl` | CV |
| 10 | 跨模块假设一致性 | 检查协方差矩阵/因子模型是否跨模块共享同一版本 | CV/DS |

#### Category 5: 前视偏差预防

| # | 必审项 | 搜索关键词 | 常见标注 |
|---|--------|-----------|---------|
| 11 | 信号时间对齐（shift/lag） | `shift`, `lag`, `look-ahead`, `future` | TM/ST |
| 12 | 训练/测试时间分割完整性 | `train_test_split`, `TimeSeriesSplit`, `shuffle` | TM/DS |

#### Category 6: 可重现性

| # | 必审项 | 搜索关键词 | 常见标注 |
|---|--------|-----------|---------|
| 13 | 随机种子全覆盖 | `random.seed`, `np.random.seed`, `torch.manual_seed` | DS |
| 14 | 模型与数据版本快照绑定 | `run_id`, `experiment_id`, `data_version` | DS |

#### Category 7: 审计追踪

| # | 必审项 | 搜索关键词 | 常见标注 |
|---|--------|-----------|---------|
| 15 | 不可变事件日志 | 检查事件记录是否 append-only，无 delete/update | RC/CV |
| 16 | 参数变更版本化追踪 | `version`, `effective_date`, `valid_from` | RC/TM |

#### Category 8: 市场约定

| # | 必审项 | 搜索关键词 | 常见标注 |
|---|--------|-----------|---------|
| 17 | 日计数约定（Day Count Convention） | `DayCounter`, `act360`, `thirty360` | TM/NM |
| 18 | 货币与单位显式标注 | `currency`, `denomination`, `notional`, `base_currency` | DS/QT |
| 19 | 结算与交割时间约定 | `settlement`, `value_date`, `T+` | TM/ST |
| 20 | 价格精度与数量精度（Tick/Lot Size） | `tick_size`, `lot_size`, `min_qty`, `quantize` | QT/ST |

### 子领域专项必审清单（按步骤 0 指纹选择）

只审视步骤 0 中标记的子领域。未匹配的子领域可跳过。

#### TRD 交易与执行（8 项）

| # | 必审项 | 为什么必审 | 常见标注 |
|---|--------|----------|---------|
| 1 | 信号-执行时序（Bar Execution Timing） | 回测前视偏差头号来源 | ST |
| 2 | 成本模型完整性 | 只建模手续费忽略滑点 = 虚高 | QT |
| 3 | 订单生命周期状态机 | 非法转换导致幽灵仓位 | ST |
| 4 | 仓位规模与风险上限 | 极端行情无限放大敞口 | QT |
| 5 | 资金成本建模（Carry/Funding） | 长持策略 PnL 虚高 | TM |
| 6 | 回测过拟合防护 | 全样本优化再评估 = 虚高 | DP |
| 7 | 填单假设（市价单全量成交） | 忽略流动性不足 | DP |
| 8 | 市场规则可配置性 | 硬编码无法跨市场 | DP |

#### A 股市场规则必审清单（仅适用于 A 股市场项目）

| # | 必审项 | 为什么必审 | 常见标注 |
|---|--------|----------|---------|
| 1 | 涨跌停板处理 | A 股回测可信度的分水岭（涨停买不进、跌停卖不出） | RC |
| 2 | T+1 持仓约束 | 当日买入次日才能卖出（普通股），ETF/可转债有例外 | RC |
| 3 | 印花税 | 卖出单边 0.05%（2023 年 8 月后），与佣金性质不同 | RC |
| 4 | 停牌处理 | 停牌期间因子计算、持仓估值、调仓可执行性 | B/DK |
| 5 | ST/\*ST 股票处理 | 涨跌幅 5%、退市风险、机构禁入 | RC/DK |
| 6 | 除权除息处理 | 长期回测偏差的头号来源，复权方式选择影响因子计算 | B/BA |
| 7 | 新股/次新股处理 | 上市初期价格行为异常，是否纳入策略池 | B/DK |
| 8 | 指数成分股调整 | survivorship bias 的来源，需要历史时点成分数据 | B/DK |
| 9 | 交易成本模型 | 佣金 + 印花税 + 过户费 + 滑点，是否分项还是合并 | B/BA |
| 10 | 先卖后买 vs 先买后卖 | 资金利用方式，隐含杠杆假设 | B |
| 11 | 执行可行性/流动性约束 | 成交量限制、冲击成本、排队成交概率；小盘股/事件股尤为关键 | B/BA |

#### PRC 定价与估值（8 项）

| # | 必审项 | 为什么必审 | 常见标注 |
|---|--------|----------|---------|
| 1 | 定价模型选择与适用边界 | BSM 用于美式 = 系统低估 | DP/M |
| 2 | 日计数与复利约定 | 混用导致 YTM/DV01 错误 | DS/M |
| 3 | 波动率曲面插值方案 | strike 线性插值引入套利 | NM |
| 4 | 隐含波动率求解器 | 深度虚值 vega≈0 时发散 | NM |
| 5 | Greeks 计算方法 | 解析 vs 有限差分的适用边界 | NM |
| 6 | 模型校准残差与收敛诊断 | 局部最优导致错误 smile | CV |
| 7 | 有限差分网格稳定性 | CFL 条件违反 = 数值爆炸 | NM |
| 8 | 无套利约束验证 | 期权价 < 内在价值 = bug | CV |

#### RSK 风险与配置（8 项）

| # | 必审项 | 为什么必审 | 常见标注 |
|---|--------|----------|---------|
| 1 | 协方差矩阵 PSD 修复策略 | 非正定导致优化失败 | NM |
| 2 | 协方差估计量选择与收缩 | 高维下估计误差差异悬殊（Ledoit-Wolf vs 样本协方差） | DP/M |
| 3 | 收益率频率与年化因子 | 月度数据用 252 = 放大 21 倍 | TM |
| 4 | VaR/CVaR 置信水平与窗口 | 99% VaR 需 >100 样本 | QT |
| 5 | 优化约束体系完备性 | 缺权重上界 = 极端集中 | QT |
| 6 | 再平衡触发机制 | 日历 vs 漂移阈值 | ST |
| 7 | 波动率模型族与分布选择 | 正态假设低估尾部（GARCH/EVT/t 分布差异） | NM |
| 8 | 因子 IC 的 demean 与分组对齐 | 行业效应误计入因子 | DS |

#### CRD 信用与银行（6 项）

| # | 必审项 | 为什么必审 | 常见标注 |
|---|--------|----------|---------|
| 1 | 违约定义与 IFRS 9 分阶段 | CRR Art.178 映射 | RC |
| 2 | PD/LGD/EAD 估计方法（IRB vs 标准法） | 直接决定 RWA | RC/M |
| 3 | Vasicek 单因子资产相关性假设 | rho 取错 UL 偏差数倍 | NM |
| 4 | 转移矩阵时间同质性与条件调整 | TTC vs PIT PD 差异 3-10 倍 | ST/M |
| 5 | 压力测试情景宏观驱动变量 | 情景严重度假设不透明 | DS |
| 6 | NPL 组合 EBA 字段完整性 | 缺失字段监管报送被拒 | RC |

#### CMP 合规与ESG（6 项）

| # | 必审项 | 为什么必审 | 常见标注 |
|---|--------|----------|---------|
| 1 | 成本基础算法选择（FIFO/LIFO/ACB） | 税务管辖区依赖 | DP |
| 2 | 税免期规则编码 | 持有期判断基于 acquisition timestamp | TM |
| 3 | 事件类型与税务规则绑定 | staking/airdrop 税务分类各异 | DP |
| 4 | GHG 排放范围边界（Scope 1/2/3） | 混淆导致披露不合规 | DS |
| 5 | 排放因子版本与来源 | IPCC EFDB 版本影响 CO2e 精度 | DS |
| 6 | PCAF 数据质量评分 | 未打分则报告不合规 | QT |

#### DAT 数据与研究（5 项）

| # | 必审项 | 为什么必审 | 常见标注 |
|---|--------|----------|---------|
| 1 | 时间序列索引排序保证 | 非单调递增 = 未来数据污染 | TM |
| 2 | 版本化写入与快照语义 | prune 不可逆删除历史 | ST |
| 3 | Provider 优先级与凭证隔离 | 切换 provider 静默改变数据语义 | DP |
| 4 | 标准化数据模型字段语义 | 同名字段不同单位 | DS |
| 5 | 特征提取时间边界 | 滑动窗口混合不同时间段 | TM |

#### AIL AI/LLM 金融（6 项）

| # | 必审项 | 为什么必审 | 常见标注 |
|---|--------|----------|---------|
| 1 | 训练/测试/交易时间段边界 | 技术指标回望窗口泄漏 | TM |
| 2 | RL 奖励函数交易成本建模 | 省略成本 = 过度交易 | NM |
| 3 | 状态空间未来数据泄漏 | DataFrame 预处理含未来信息 | DS |
| 4 | Pipeline fit/transform 隔离 | Scaler 在全序列 fit = 泄漏 | CV |
| 5 | Covariates 时间可用性约束 | past vs future covariates 误用 | DS |
| 6 | 多智能体决策共识与风险否决权 | LLM 输出格式异常 = 决策缺失 | ST |

#### INS 保险与精算（6 项）（v3.5 新增）

| # | 必审项 | 为什么必审 | 常见标注 |
|---|--------|----------|---------|
| 1 | 准备金充足性方法（Chain Ladder/BF/Mack） | 方法选择直接影响准备金水平，Mack 提供置信区间但假设独立性 | NM/M |
| 2 | 死亡率表版本与来源（SOA/UK ONS/中国生命表） | 过期表低估长寿风险，表间差异可达 10-20% | DS/RC |
| 3 | 最优估计假设（Best Estimate）与风险边际 | Solvency II 要求 BE + Risk Margin，假设不透明 = 监管不合规 | RC/M |
| 4 | Solvency II SCR 标准公式 vs 内部模型 | 标准公式假设相关性矩阵固定，内部模型需 EIOPA 批准 | RC |
| 5 | 再保险合约映射（QS/XL/Stop Loss） | 再保类型决定风险转移比例，映射错误 = SCR 错算 | DP |
| 6 | 巨灾模型选择与校准（AIR/RMS/地震/台风） | 尾部分布假设极端敏感，模型间差异可达 3-5 倍 | NM/M |

#### LND 贷款与支付（6 项）（v3.5 新增）

| # | 必审项 | 为什么必审 | 常见标注 |
|---|--------|----------|---------|
| 1 | 利率类型处理（固定/浮动/混合） | 浮动利率需要基准利率更新机制（SOFR/LPR），缺失 = 利息计算错误 | DP/RC |
| 2 | 还款计划生成（等额本息/等额本金/先息后本） | 计算公式不同，四舍五入策略影响最后一期金额 | NM |
| 3 | 逾期定义与滚动率（DPD 30/60/90） | 逾期天数起算点（到期日 vs 宽限期结束）直接影响 NPL 分类 | RC/DS |
| 4 | 催收优先级与合规约束 | 催收频率/时段受消费者保护法约束（FDCPA/中国催收公约） | RC |
| 5 | 双重记账完整性（Debit = Credit） | 任何不平衡 = 账务错误，支付系统核心不变式 | CV |
| 6 | 对账时效与差异处理 | T+0/T+1 对账窗口，未对平项的升级流程 | ST/DP |

#### TRS 财资与ALM（5 项）（v3.5 新增）

| # | 必审项 | 为什么必审 | 常见标注 |
|---|--------|----------|---------|
| 1 | 流动性覆盖率（LCR）与净稳定资金比率（NSFR） | Basel III 硬指标，低于阈值 = 监管处罚 | RC/QT |
| 2 | 利率缺口分析（Gap Analysis）时间桶划分 | 桶粒度（隔夜/1M/3M/1Y）影响 IRRBB NII 敏感度 | TM/NM |
| 3 | 资金转移定价（FTP）方法 | 匹配期限法 vs 单一利率法，影响业务线利润归因 | DP/M |
| 4 | 现金池法律结构（物理归集 vs 名义归集） | 跨境资金池受外汇管制，法律结构决定税务效果 | RC/DP |
| 5 | 外汇风险敞口计量与对冲比率 | 自然对冲 vs 衍生品对冲，过度对冲 = 投机 | QT/RC |

#### AML 反洗钱与合规（6 项）（v3.5 新增）

| # | 必审项 | 为什么必审 | 常见标注 |
|---|--------|----------|---------|
| 1 | 交易阈值配置（CTR/SAR） | 各国阈值不同（美国 $10,000/中国 ¥50,000），硬编码 = 跨境不可用 | RC/DP |
| 2 | 制裁名单版本与更新频率 | OFAC/EU/UN 名单日更新，延迟 = 合规违规 | DS/RC |
| 3 | 模糊匹配算法与阈值 | Jaro-Winkler/Levenshtein/Soundex 选择影响误报/漏报平衡 | NM/DP |
| 4 | 网络分析深度（跳数/层数） | 1-hop vs 3-hop 影响关联发现能力，但也影响计算成本 | QT/DP |
| 5 | 误报率监控与模型治理 | 高误报率（>95%）导致审查团队疲劳，需要定期模型再校准 | CV/ST |
| 6 | 审计日志不可变性与保留期 | 监管要求审计日志不可篡改、保留 5-7 年（BSA/4AMLD） | RC/ST |

### 输出格式

```
## 业务决策标注清单

### 阶段：{stage_name}

| # | 内容 | 类型 | 业务理由 |
|---|------|------|---------|
| 1 | "先卖后买" | B | 隐含无杠杆假设，换序影响资金利用率 |
| 2 | "止损 -30%" | B/BA | 偏宽阈值，假设长期持有高容忍度 |
| 3 | "T+1 执行延迟" | RC | A 股交割制度强制，非作者选择 |
| 4 | "Ledoit-Wolf 协方差收缩" | M | 高维下样本协方差不稳定，LW 收缩降低估计误差 |

### 遗漏的业务决策
- 涨跌停板处理：源码中未实现 → 必须在蓝图中标注为已知缺陷
- ...

写入 /tmp/{repo}_business_decisions.md
```

### BD 最低质量标准

每条非 T 类 business_decision 必须满足以下标准，否则退回补充：

**rationale 深度**：
- 至少 2 句：第 1 句说明**为什么选择了这个方案**（WHY），第 2 句说明**在什么条件下需要修改**（BOUNDARY）
- M 类额外要求：必须说明所依赖的数学假设（如正态分布、线性假设）
- BA 类额外要求：必须说明假设所编码的市场/经济规律

**多类型标注**：
- 对每个非 T 决策，显式评估是否有双重性质（如 B/BA、M/BA、M/DK、RC/DK）
- 单类型标注时，附一句排除理由（如 "无数学理论支撑，不标 M"）

**evidence 格式**：
- file:line(function_name) 三元组，不接受纯文件名

**反例** ❌：
```yaml
- content: "止损 -30%"
  type: business
  evidence: trader.py:44
```

**正例** ✅：
```yaml
- content: "止损 -30%（profit_threshold 默认 negative=-0.3）"
  type: "B/BA"
  rationale: >
    B：在多种止损阈值方案中主动选择了 -30%；
    BA：偏宽松（行业 CTA 常用 -3%~-5%），编码了教学框架高容忍度假设。
    实盘使用时应根据策略特性收紧。
  evidence: "trader/trader.py:247 on_profit_control()"
```

### Missing Gap 分析（必须输出）

对照金融通用必审清单（20 项）和适用的子领域必审清单，逐项检查代码是否覆盖。未覆盖项标记为 missing gap：

```yaml
- decision: "涨跌停板处理"
  type: RC
  status: missing
  known_gap: true
  severity: critical
  impact: "动量策略回测收益率会系统性高估（假设可以在涨停价全额成交）"
```

**必填字段**：decision、type、status（`missing`）、known_gap（`true`）、severity（`critical`/`high`/`medium`）、impact
**severity 判定**：critical = 影响回测可信度或合规性；high = 影响策略行为；medium = 影响精度或可扩展性

**底线标准**：任何金融项目至少应有 3 条 missing gap。如果 0 条，审计覆盖不充分，必须重做。

### 审计发现处理规则

步骤 2c 的 20 项金融通用必审 + 子领域必审的审计结论，按以下规则转化为 business_decisions：

| 审计结论 | 处理动作 | 写入蓝图 YAML |
|---------|---------|-------------|
| ❌ 框架未实现 | 转入 `business_decisions`，设 `status: missing`，severity 继承审计判定 | 是 |
| ❌ 实现有已知缺陷 | 转入 `business_decisions`，标注 type + `known_issue` 描述 | 是 |
| ⚠️ 部分实现有风险 | 转入 `business_decisions`，type=BA，rationale 中标注风险 | 是 |
| ✅ 已正确实现 | 不转化为 business_decision — 已通过 design_decisions 覆盖 | 否 |

- High/Critical 级别的 ❌ 发现**必须**转化
- Medium 级别的 ❌ 和 ⚠️ 视覆盖度判断
- 同一项审计可同时产生 business_decision（蓝图）和约束（由约束采集 SOP Step 2.5 处理）

### 审计汇总落盘

组装蓝图时，在 YAML 中新增 `audit_checklist_summary` 字段记录审计执行状态：

```yaml
audit_checklist_summary:
  sop_version: "3.6"
  executed_at: "2026-04-05"
  subdomain_labels: ["TRD", "DAT"]  # 步骤 0 指纹探针结果
  finance_universal: {pass: 3, warn: 14, fail: 3}
  subdomain_checklists:
    - name: TRD
      result: {pass: 2, warn: 5, fail: 1}
    - name: A_STOCK
      result: {pass: 1, warn: 7, fail: 1}
  critical_findings:
    - item: "涨跌停执行层未使用 is_limit_up/is_limit_down"
      severity: critical
      disposition: "converted_to_bd"
```

---

## 步骤 2d: 业务用例扫描

**目的**：扫描项目的 examples/notebooks/tutorials，建立业务用例索引。

**为什么需要**：蓝图只描述"框架怎么运作"，但不描述"用框架能做什么"。examples 中的完整策略/研究流程是业务逻辑密度最高的来源。

### 扫描范围

```
代码知识源优先级：
P0: examples/**/*.py          — 完整可运行策略
P1: notebooks/**/*.ipynb      — 端到端研究流程
P2: docs/tutorials/**/*       — 结构化教程
P3: README.md Quick Start     — 最小可用示例
P4: 源码中继承基类的内置实现   — 内置因子/策略/模型

文档知识源优先级（步骤 0 探测到文档知识源时补充扫描）：
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
grep -rn "class.*Factor\|class.*Strategy\|class.*Model\|class.*Indicator" /tmp/{repo}/ --include='*.py' | grep -v test | grep -v __pycache__
```

对每个找到的文件，记录：

```
文件：examples/trader/macd_day_trader.py
类型：完整策略（有 __main__ 入口）
业务场景：MACD 日线金叉交易
完整度：端到端可运行
关键参数：lookback_window=50, profit_threshold=(3,-0.3)
```

### 输出

在蓝图 YAML 中新增 `known_use_cases` 字段（步骤 4 组装时写入）：

```yaml
known_use_cases:
  - name: "MACD 日线金叉交易策略"
    source: "examples/trader/macd_day_trader.py"
    type: "complete_strategy"               # complete_strategy | screening_logic | data_pipeline | builtin_factor | monitoring | extension_example | live_trading
    business_problem: "通过 MACD 技术指标识别 A 股趋势转折买入点"
    intent_keywords: ["MACD", "金叉", "日线", "择时"]
    applicable_markets: ["CN_A"]            # CN_A | US | HK | global
    required_data: ["日线 OHLCV"]
    required_components: ["GoldCrossFactor", "StockTrader", "TargetSelector"]
    key_parameters:
      lookback_window: 50
      profit_threshold: "(3, -0.3)"
    must_validate:
      - "信号无前视偏差（T+1 执行）"
      - "账户记录完整"
    not_suitable_for: ["高频策略", "融资融券"]
    negative_keywords: ["与该用例容易混淆的其他用例的关键词"]
    disambiguation: "当用户意图可能匹配多个用例时，应问的消歧问题"
    data_domain: "该用例依赖的数据类型（market_data | financial_data | holding_data | trading_data | mixed）"
```

**必填字段**：name、source、type、business_problem、intent_keywords
**推荐字段**：applicable_markets、required_data、required_components、key_parameters、must_validate、not_suitable_for
**消歧字段**：negative_keywords、disambiguation、data_domain

对每个用例，检查蓝图中是否有其他用例的 intent_keywords 与该用例重叠。如有重叠，将重叠用例的关键词填入 negative_keywords，并设计 disambiguation 问题。

**注意**：步骤 2d 只建索引，不做深度提取。深度提取（Pattern YAML）是后续独立流程。

---

## 步骤 3: 自动验证

```bash
cd /Users/tangsir/Documents/openclaw/Doramagic
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

**解读验证结果**：

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

代码知识源（双锚点）：
```yaml
evidence:
  event_engine: vnpy/event/engine.py:48-78(EventEngine._run)
  # 格式：file:line(function_name)
  # 行号 + 函数签名双锚点，防行号漂移
```

文档知识源（section 锚点 + role 标注）：
```yaml
evidence:
  iron_law:
    kind: document_section
    path: skills/systematic-debugging/SKILL.md
    section_id: "§The-Iron-Law"
    evidence_role: normative  # normative=规则 / example=示例 / rationale=理由
```

**规则 3：避免过度概括**
- ❌ 禁止使用："唯一的"、"唯二的"、"所有实现都是"、"全部通过"、"所有"、"全部"
- ✅ 使用精确表述："BaseGateway 有 7 个 @abstractmethod"、"核心仓库内置 Alpha 回测，CTA/IB 等在外部包"、"各阶段"、"每个 stage"、具体数量
- 组装完成后全文搜索"所有"/"全部"，目标出现次数 ≤3 次；搜索"唯一"，非标识符语境一律替换

**规则 4：@abstractmethod 报告方式**
```yaml
# 正确：报告总数 + 分布
global_contracts:
  - contract: "25 个 @abstractmethod 分布在 6 个文件"
    evidence: "gateway(7)+engine(1)+database(8)+alpha/strategy(3)+alpha/model(2)+chart(4)"

# 错误：使用"唯二"
global_contracts:
  - contract: "SlippageModel 和 CommissionModel 是唯二的 @abstractmethod"  # ← 禁止
```

**规则 5：精细度检查清单**

组装完成后，逐项检查以下内容：

| 字段 | 检查标准 | 退化/违规警告 |
|------|---------|-------------|
| replaceable_points | 每个选项有 name/traits/fit_for/not_fit_for | 退化为字符串列表 → 补回结构 |
| replaceable_points 覆盖度 | 必须覆盖三维度：数据源/执行模式/存储后端 | 缺任何一维 → 补充 |
| required_methods | 每个方法**必须**有 name + description + evidence（必填字段） | 只有方法名 → 补描述和行号 |
| required_methods 空值 | 每个 stage **必须**至少有 1 个 required_method | 空 → **必须**补充或标注"该阶段无用户接口" |
| design_decisions | 每条有源码证据引用 | 没有证据 → 补上或标注"推断" |
| key_behaviors | 每条**必须**有 behavior + description + evidence（必填字段） | 缺失 → 补充或标注"该阶段无显式行为契约" |
| stages.order | **严格递增**，不能有重复值 | 重复 → 必须修正 |
| global_contracts 内容 | 仅放**架构不变式**（跨阶段必须遵守的规则） | 实现特征 → 移到 source.evidence |
| global_contracts 字段名 | 必须使用 `global_contracts` 作为顶级字段名，**禁止**使用 `cross_cutting`、`design_principles` 等非标准名；至少包含 3 条架构不变式 | 缺失或字段名不符 → 必须修正 |
| relations 字段 | 必须主动填充，至少声明 1 条与同子领域蓝图的关系 | 空列表 → 必须补充；无已有同子领域蓝图时标注"暂无同子领域参照" |
| YAML 特殊字符 | 所有含 `' { } : [ ]` 的字符串值必须加引号包裹 | YAML 解析失败 → 检查并加引号 |
| "所有"/"全部"/"唯一" 频率 | 全文"所有"+"全部" ≤3 次；"唯一"仅允许出现在明确的标识符/主键语境，其他一律替换 | 超标 → 逐一替换为精确表述 |
| business_decisions | 步骤 2c 标注的 B/BA/DK/RC/M 类决策必须写入蓝图，至少 5 条；M 类标注不得缺失（如有数学模型选择） | 缺失 → 回步骤 2c 补充 |
| known_use_cases | 步骤 2d 扫描的业务用例索引，至少列出项目 examples 中的完整策略 | 缺失 → 回步骤 2d 扫描 |
| known_use_cases 消歧字段 | 每个用例必须有 negative_keywords 和 disambiguation（如有关键词重叠的用例） | 缺失 → 回步骤 2d 补充 |
| 量化金融必审清单 | 20 项金融通用必审 + 子领域必审清单是否逐项审视并记录（存在→标注，不存在→记录为遗漏） | 未审视 → 回步骤 2c |
| audit_checklist_summary | 审计汇总字段必须存在，包含 sop_version、subdomain_labels、各清单通过/警告/失败计数 | 缺失 → 补充 |
| replaceable_points 资源完整性 | 每个数据源选项是否包含当前主流方案（如 A 股必须包含 AkShare）；是否列出 Python 依赖包清单；存储后端是否有替代选项描述 | 缺失主流数据源或依赖包 → 补充 |
| resources 字段 | 子技术文档/工具脚本/代码示例/外部服务是否全部列入 `resources`，每条有 id/type/name/path/used_in_stages | 缺失 → 从步骤 2a-s 产出补充；纯代码项目至少列出外部 API/数据源依赖 |
| applicability.activation | 文档知识源的 "When to Use" 是否提取到 `activation.triggers` / `activation.anti_skip` | 有文档知识源但无 activation → 回步骤 2a-s 补充；纯代码项目可为空 |
| relations 类型 | 跨蓝图关系是否使用了正确的 type（depends_on/complementary/contains 用于执行关系） | 所有引用都标 alternative_to → 检查是否应标 depends_on 或 contains |
| extraction_methods | `source.extraction_methods` 是否列出实际使用的所有提取策略（列表） | 混合项目只标了一种策略 → 补充 |
| evidence_role | 文档知识源的 evidence 是否标注了 evidence_role（normative/example/rationale） | 未标注 → 回溯原文判断并补充 |
| BD rationale 深度 | 非 T 类 BD 的 rationale 平均字数 ≥ 40 字（中文）或 ≥ 20 词（英文） | 低于阈值 → 回步骤 2c 逐条补充 rationale |
| BD 多类型标注比例 | 非 T 类 BD 中多类型标注（如 B/BA、M/BA）占比 ≥ 30% | 低于阈值 → 回步骤 2c 逐条评估双重性质 |
| missing gap 条数 | missing gap（`status: missing`）至少 3 条 | 0 条 → 审计覆盖不充分，回步骤 2c 重做 Missing Gap 分析 |
| 审计清单覆盖率 | 已检查项数 / 应检查项数 ≥ 80%（金融通用 20 项 + 适用子领域项） | 低于 80% → 回步骤 2c 补充未检查项 |

**规则 6：记录源码版本**

commit_hash 是**必需字段**，不可省略。字段名统一为 `commit_hash`。

```yaml
source:
  projects: [owner/repo]
  commit_hash: "abc1234..."  # git rev-parse HEAD 的输出（必需）
  extraction_date: "2026-04-05"
```

**规则 7：YAML 验证**

组装完成后，**提交前必须执行**以下验证命令：

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

常见触发字符（必须加引号）：
- 含冒号的字符串：`key: "value: with colon"`
- 含花括号的字符串：`note: "{不加引号会被解析为 mapping}"`
- 含方括号的字符串：`list_note: "[不加引号会被解析为 sequence]"`
- 含单引号的字符串：使用双引号包裹：`desc: "it's a value"`

**规则 8：提取流水线版本注释**

每次重跑蓝图后，**必须更新** YAML 头部注释中的 SOP 版本号和重跑日期：

```yaml
# 提取流水线: SOP v3.2（全量重跑，2026-04-08）
```

- 全量重跑标注"全量重跑"
- 仅升级部分字段标注"升级 business_decisions + audit_checklist_summary"
- 头部注释版本必须与实际使用的 SOP 版本一致

---

## 步骤 5: 一致性检查

新蓝图组装后，在提交评审前，检查与已有蓝图的一致性。

### 检查项

**5a. relations 双向一致**
如果新蓝图声明 `alternative_to: finance-bp-001`，检查 bp-001 是否也有对应的 `alternative_to` 指向新蓝图。

**5b. 对比表事实一致**
如果评审 prompt 中有对比表，确认表中每个单元格的内容与对应蓝图 YAML 中的声明一致。
- 例：对比表说某项目"有数十个 @abstractmethod"，但对应蓝图说"唯二" → 矛盾，必须修正蓝图

**5c. applicability 互斥性**
检查不同蓝图的 applicability.not_suitable_for 是否形成互补：
- bp-001 说"不适合 T+1 市场" → bp-003 应该适合
- bp-002 说"不适合实盘" → bp-001/bp-003 应该支持实盘

**5d. 字段名一致性**
检查所有蓝图的字段命名是否统一：
- `commit_hash`（不是 `commit`）
- `extraction_date`（不是 `extract_date`）
- `not_suitable_for`（不是 `not_for`）
如有不一致，以 SOP 规定的字段名为准。

**5e. stages 结构一致性**
检查所有蓝图的 stages.order 是否严格递增（无重复值）。

---

## 步骤 6: 多模型评审

将蓝图发给 4 个模型做独立评审。评审 prompt 模板见各蓝图对应的 `prompt-blueprint-*-review.md`。

### 评审维度
1. 源码忠实度
2. AI 消费品质量
3. 架构抽象质量
4. （如有多个蓝图）三项目横向对比
5. 流水线成熟度

### 评审后行动

| 评审结果 | 行动 |
|---------|------|
| 全票通过 | 蓝图定稿 |
| 发现事实错误 | 回步骤 2b 重新验证 → 修正 → 重新评审 |
| 发现结构问题 | 在 YAML 中修改，无需重跑全流程 |
| 发现跨蓝图矛盾 | 回步骤 5 修正一致性 |

### Claude 子代理评审
Claude 的评审通过启动子代理自动执行（读实际源码验证），其他三方由人工发送 prompt。

---

## 四大必查项速查卡

每次提取必须验证以下四类声明，这是出错率最高的区域：

### 必查 1：执行时机
```bash
# 检查信号是否有 shift/延迟
grep -rn 'shift' {repo}/ --include='*.py' | grep -v test | grep -i 'signal\|entry\|exit'
# 检查事件驱动的执行顺序
grep -rn 'cross_order\|get_transactions\|fill\|match' {repo}/ --include='*.py' | grep -v test
```
**常见错误**：把"N+1 执行"写成"同根执行"

### 必查 2：数据结构
```bash
# 检查 DataFrame 索引类型
grep -rn 'set_index\|DatetimeIndex\|as_index\|reset_index' {repo}/ --include='*.py' | grep -v test | head -20
```
**常见错误**：假设 DatetimeIndex 但实际是普通列

### 必查 3：@abstractmethod 完整性
```bash
# 完整扫描（绝不能只做部分扫描）
grep -rn '@abstractmethod' {repo}/ --include='*.py' | grep -v test | grep -v __pycache__
# 按文件统计
grep -rn '@abstractmethod' {repo}/ --include='*.py' | grep -v test | cut -d: -f1 | sort | uniq -c | sort -rn
```
**常见错误**：说"唯二"但实际有数十个

### 必查 4：数学模型选择```bash
# 搜索定价/估计/优化类名
grep -rn 'class.*Pricer\|class.*Model\|class.*Estimat\|class.*Optimiz\|BlackScholes\|GARCH\|Ledoit\|logistic\|montecarlo\|MonteCarlo' {repo}/ --include='*.py' | grep -v test | grep -v __pycache__
# 搜索收敛参数
grep -rn 'tolerance\|tol\b\|max_iter\|convergence\|eps\b' {repo}/ --include='*.py' | grep -v test | head -20
```
**常见错误**：把模型选择标注为 T（技术选择），但换模型会显著影响定价/估计结果

---

## 验证规则分层

### 通用层（5 项）
1. @abstractmethod 完整性
2. ABC 基类定义
3. 程序入口
4. 数据模型（DataFrame/dataclass/ORM）
5. evidence 行号可达性

### 金融通用层（20 项，见步骤 2c）
- 时间语义（3 项）：as-of/evaluation_date、交易日历、时区
- 数值精度（3 项）：float vs Decimal、收敛条件、矩阵稳定性
- 数据谱系（2 项）：Point-in-Time、Stale data
- 守恒与一致性（2 项）：PnL 守恒、跨模块一致
- 前视偏差（2 项）：信号对齐、训练/测试分割
- 可重现性（2 项）：随机种子、版本快照
- 审计追踪（2 项）：不可变日志、参数版本化
- 市场约定（4 项）：日计数、货币单位、结算约定、精度

### 子领域层（按步骤 0 指纹，见步骤 2c）
- TRD：8 项（信号时序/成本/状态机/仓位/资金成本/过拟合/填单/跨市场）
- PRC：8 项（模型选择/日计数/插值/隐含波动率/Greeks/校准/FDM/无套利）
- RSK：8 项（PSD/估计量/年化/VaR/约束/再平衡/分布/IC）
- CRD：6 项（违约定义/IRB/Vasicek/转移矩阵/压力测试/EBA）
- CMP：6 项（FIFO/税免期/事件类型/GHG/排放因子/PCAF）
- DAT：5 项（排序/快照/Provider/字段语义/时间边界）
- AIL：6 项（时间分割/RL奖励/状态泄漏/Pipeline/Covariates/多智能体）

### 市场/法域特化层
- **A 股**：11 项（涨跌停/T+1/印花税/停牌/ST/除权除息/新股/成分股/交易成本/先卖后买/流动性）
- **美股**：T+2 结算、wash sale rule、pattern day trader 规则
- **加密货币**：T+0、gas fee 建模、MEV 风险

