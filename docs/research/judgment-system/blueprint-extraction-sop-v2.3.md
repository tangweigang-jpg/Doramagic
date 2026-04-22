# 蓝图提取流水线操作手册（SOP v2.3）

> 版本：2.3（基于 v9 晶体测试 + bp-009 业务决策审计 + 四方评审共识）
> 日期：2026-04-06
> 适用：Claude Code 环境下从开源项目源码提取架构蓝图
> 前版：v2.0 基于 freqtrade + zipline + vnpy 三项目经验
> v2.1 变更：新增 L11-L15 教训，强化 Step 4 精细度检查和 Step 5 一致性检查
> v2.2 变更：新增 L16-L20 教训（来自 Batch 1+2 提取），强化 Step 4 YAML 合规、绝对化措辞、relations 和 global_contracts 检查
> v2.3 变更：新增 L21-L27 教训（来自 v9 晶体测试 + bp-009 审计 + 四方评审），新增步骤 2c（业务决策标注）+ 步骤 2d（业务用例扫描），新增业务决策分类框架（T/B/BA/DK/RC）

---

## 经验教训总表（驱动本 SOP 每条规则的来源）

| # | 教训 | 来自哪个项目 | 影响的步骤 |
|---|------|------------|-----------|
| L1 | LLM 总结 ≠ 事实，shift(1) 被遗漏 | freqtrade V2 | 步骤 2b |
| L2 | DatetimeIndex vs 普通列，文档推测 vs 读代码 | freqtrade V2 | 步骤 2b |
| L3 | @abstractmethod 数量被假设而非验证 | freqtrade V2 | 步骤 2b, 3 |
| L4 | "唯二 @abstractmethod" 过度概括 | zipline | 步骤 2b |
| L5 | 第二个项目提取精细度下降（replaceable_points 退化为字符串） | zipline | 步骤 4 |
| L6 | 行号会漂移，需要函数签名双锚点 | vnpy (Claude review) | 步骤 4 |
| L7 | "所有实现外部包" 过度概括 | vnpy (GPT/Claude review) | 步骤 4 |
| L8 | 跨蓝图对比表可能自相矛盾 | vnpy (Claude review) | 步骤 5 |
| L9 | 验证规则需要分层（通用/领域/项目族） | vnpy (四方共识) | 步骤 3 |
| L10 | Warning 应区分"特征缺失"和"提取错误" | vnpy (Gemini) | 步骤 3 |
| L11 | stages order 字段必须严格递增，不能有重复值 | bp-009 审计 | 步骤 4 |
| L12 | source.commit_hash 是必需字段，必须记录提取时的 commit | bp-004 审计 | 步骤 4 |
| L13 | global_contracts 仅放架构不变式，实现特征放 source.evidence | bp-009 三方评审 | 步骤 4 |
| L14 | replaceable_points 必须覆盖三维度：数据源/执行模式/存储后端 | bp-009 三方评审 | 步骤 4 |
| L15 | 字段名跨蓝图必须一致（如统一用 commit_hash 而非 commit） | 10 蓝图一致性审计 | 步骤 5 |
| L16 | YAML 特殊字符（' { } : [ ]）必须加引号包裹，Step 4 组装后必须执行 yaml.safe_load 验证 | Batch 1（4 个）+ Batch 2（3 个）YAML 解析失败 | 步骤 4 |
| L17 | "所有"/"全部" 是最高频 L7 违规词，Step 4 组装时应主动替换为精确表述（"各"、"每个"、具体数量），目标 ≤3 次 | 30 个新蓝图中 20+ 个首次提交时违规 | 步骤 4 |
| L18 | relations 字段必须在 Step 4 中主动填充，至少声明 1 条与同子领域蓝图的关系 | Batch 1+2 的 29/30 个新蓝图 relations 为空 | 步骤 4 |
| L19 | global_contracts 必须作为标准顶级字段存在（不可用 cross_cutting/design_principles 等替代），至少 3 条架构不变式 | Batch 2 的 10/15 个蓝图缺失或使用非标准字段名 | 步骤 4 |
| L20 | 子代理生成的 YAML 中"唯一"出现频率高（数据库主键/标识符语境），应在 Step 4 检查清单中列为必查项 | Batch 1+2 共 8 个蓝图 L4 违规 | 步骤 4 |
| L21 | exec 禁止清单必须穷举所有 shell 操作符，不能只举一个例子 | v8 晶体测试（exec && 被拒） | 步骤 2c |
| L22 | 规格锁必须覆盖所有可变参数（如 STOCK_POOL、TOP_N），不能只锁策略类型 | v8 晶体测试（TOP_N 漂移） | 步骤 2c |
| L23 | 代码模板必须给可执行的正确 API 调用示例，不能只给伪代码注释 | v8 晶体测试（baostock API 参数错） | 步骤 2c |
| L24 | 蓝图中的 design_decisions 混合了技术选择和业务决策，必须分类标注 | bp-009 业务决策审计 + 四方评审 | 步骤 2c |
| L25 | 默认参数值往往编码了隐式业务假设（如止损 -30%），必须审视其业务理由 | bp-009 审计（四方评审一致指出） | 步骤 2c |
| L26 | A 股特有规则（涨跌停、T+1 持仓、印花税、ST 处理）必须作为 RC 类决策显式记录 | bp-009 四方评审（Grok/GPT/Claude 共识） | 步骤 2c |
| L27 | 业务逻辑不仅在 examples 中，更隐藏在基类默认行为、Schema 字段选择、继承层级中 | zvt 提取实验 + 三方挑战评审 | 步骤 2c, 2d |
| L28 | RC（监管规则）与 B（框架实现选择）混在一条时必须拆成两条，否则 AI 无法区分"不可变的法规"和"可变的实现" | bp-009 升级四方评审（Gemini/GPT 指出 T+1 混标） | 步骤 2c |
| L29 | known_use_cases 必须包含结构化字段（intent_keywords、required_components 等），否则对编译器选择用例帮助有限 | bp-009 升级四方评审（GPT：更像例子目录不像可编译模式库） | 步骤 2d |
| L30 | 必审清单必须包含执行可行性/流动性约束（成交量限制、冲击成本），否则回测会生成"理论可执行实际成交不了"的虚假信号 | bp-009 升级四方评审（GPT/Gemini/Grok 共识） | 步骤 2c |
| L31 | replaceable_points 必须包含当前主流资源选项（如 A 股数据源必须有 AkShare），必须列出 Python 依赖包清单，存储后端必须有替代方案描述。资源不到位的蓝图编译出的晶体会推荐过时方案 | bp-009 资源审视（5.3/10，缺 AkShare、缺依赖包、缺存储替代） | 步骤 4 |

---

## 概述

蓝图提取是一个**人机协作的 8 步流程**。

```
步骤 1: Clone        — 自动（git clone）
步骤 2a: 粗提取      — LLM 子代理读源码（产出架构骨架）
步骤 2b: 声明验证    — LLM 子代理逐行验证关键声明（防 L1-L4）
步骤 2c: 业务决策标注 — 用 T/B/BA/DK/RC 分类审视已提取内容（防 L24-L27）[v2.3 新增]
步骤 2d: 业务用例扫描 — 扫描 examples/notebooks 提取业务用例索引（防 L27）[v2.3 新增]
步骤 3: 自动验证     — 脚本 grep 检查（防硬事实错误）
步骤 4: 组装蓝图     — 基于验证结果写 YAML（有精细度检查清单防 L5）
步骤 5: 一致性检查   — 检查新蓝图与已有蓝图的交叉引用（防 L8）
步骤 6: 多模型评审   — 四方评审（Claude/GPT/Gemini/Grok）
```

**绝对规则：步骤 2b 不可跳过。** freqtrade V2 跳了 2b 导致 3 个事实错误。
**绝对规则：步骤 2c 不可跳过。** v9 晶体测试证明不标注业务决策会导致晶体缺失关键业务逻辑。

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
   - 是 DatetimeIndex 还是普通列？必须引用具体代码行
5. 找执行模型：
   - 主循环结构
   - 信号传递方式
   - 搜索 shift/delay 关键词确认是否有延迟机制
6. 找风控实现位置
7. 找辅助子系统（参数优化、ML、通知、交易对筛选等）
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

**与 v1.0 的差异**：
- 新增第 8 条：完整 @abstractmethod 扫描（教训 L3, L4）
- 第 3 条强调"不能假设，必须验证"
- 第 4 条强调"不能从文档推测"
- 每个发现要求"文件路径 + 行号 + 函数签名"三锚点（教训 L6）

---

## 步骤 2b: 声明验证（不可跳过）

从 round 1 报告中提取所有事实性声明（通常 8-12 条），启动第二个子代理验证。

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
- 确认是 DatetimeIndex 还是普通列

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

**与 v1.0 的差异**：
- 新增"过度概括风险"检查（教训 L4, L7）
- 三大必查项固化为标准（教训 L1, L2, L3）
- 禁止"唯一"/"唯二"表述（教训 L4）

---

## 步骤 2c: 业务决策标注（v2.3 新增，不可跳过）

**目的**：用业务决策视角重新审视步骤 2a/2b 已提取的内容，区分"技术架构"和"业务决策"。

**为什么不能跳过**：v9 晶体测试证明，蓝图中未标注的业务决策（止损阈值、先卖后买、仓位分档）在编译晶体时全部丢失，导致 AI 不知道该做什么具体业务事情（教训 L24-L27）。

### 业务决策分类框架（五类）

| 类型 | 代码 | 定义 | 判断准则 | 示例 |
|------|------|------|---------|------|
| 技术选择 | **T** | 换一种实现方式，业务结果不变 | "改了这个，投资收益/分析结论会变吗？" → 不变 = T | 用 SQLite vs PostgreSQL 存储 |
| 业务决策 | **B** | 直接规定系统怎么做，换了就改变投资行为 | "改了这个，系统的交易行为会变吗？" → 会变 = B | 先卖后买、scores 等权平均 |
| 业务假设 | **BA** | 编码了对市场/经济的假设，是 B 的"为什么" | "这个默认值/规则背后假设了什么市场规律？" | 止损 -30%（假设高容忍度）、滑点 0.1%（假设小单低冲击） |
| 领域知识 | **DK** | 特定市场的制度/文化知识（非通用量化惯例） | "换个市场（如美股→A股），这条还成立吗？" → 不成立 = DK | turnover_rate 作为一等字段（A 股特性） |
| 监管规则 | **RC** | 市场制度强加的硬约束，非框架作者的选择 | "这是作者决定的，还是法规/交易所强制的？" → 强制 = RC | T+1 交割、涨跌停 ±10%、印花税 0.05% |

**B 和 BA 的边界**（四方评审共识）：
- B = 系统的规则（"怎么做"）
- BA = 规则背后的假设（"为什么这么做"）
- 同一条内容可以双标注 B/BA（允许）
- 不确定时优先标 B（保守策略，宁可多标不可漏标）

**RC 与 B/BA 混合时必须拆成两条**（教训 L28，四方升级评审共识）：
- 当"法规事实"和"框架实现选择"混在一条时，必须拆成独立两条
- 例：❌ 错误写法：`"T+1 信号延迟执行" type: RC` — 混合了法规和实现
- ✅ 正确写法：拆成两条：
  - `"A 股普通股 T+1 交割制度" type: RC` — 法规事实（不可变）
  - `"主循环结构将信号执行延迟到下一周期" type: B` — 框架实现选择（可变）
- 判断依据：问"如果换个市场（无 T+1 约束），框架的这个实现选择还存在吗？" → 如果还在 = B，如果消失 = 纯 RC

**DK 的使用范围**（收窄，教训 L26）：
- ✅ 仅用于特定市场的制度/文化知识：A 股换手率分析文化、中国散户主导市场结构
- ❌ 不用于通用量化惯例：MultiIndex [entity_id, timestamp] 是所有量化框架的通用做法，不算 DK

### 审视方法

对步骤 2a/2b 产出的每条内容，逐项审视：

```
输入：步骤 2a 的粗提取报告 + 步骤 2b 的验证报告
输出：业务决策标注清单（每条标注 T/B/BA/DK/RC + 业务理由）

审视对象（按优先级）：
1. design_decisions    — 每条追问"技术选择还是业务决策？"
2. 默认参数值          — 每个追问"为什么是这个值？换了会改变投资结果吗？"
3. Schema 字段选择     — 追问"为什么这些字段是一等公民？体现了什么领域认知？"
4. 基类默认行为        — 追问"这个默认顺序/默认值编码了什么业务规则？"
5. acceptance_hints    — 区分"技术验证"和"业务验证"
```

### 量化金融领域必审清单（教训 L26，四方共识）

以下 A 股业务逻辑如果在源码中存在，**必须标注**；如果不存在，**必须记录为"遗漏的业务决策"**：

| # | 必审项 | 为什么必审 | 常见标注类型 |
|---|--------|----------|------------|
| 1 | **涨跌停板处理** | A 股回测可信度的分水岭（涨停买不进、跌停卖不出） | RC |
| 2 | **T+1 持仓约束** | 当日买入次日才能卖出（普通股），ETF/可转债有例外 | RC |
| 3 | **印花税** | 卖出单边 0.05%（2023 年 8 月后），与佣金性质不同 | RC |
| 4 | **停牌处理** | 停牌期间因子计算、持仓估值、调仓可执行性 | B/DK |
| 5 | **ST/\*ST 股票处理** | 涨跌幅 5%、退市风险、机构禁入 | RC/DK |
| 6 | **除权除息处理** | 长期回测偏差的头号来源，复权方式选择影响因子计算 | B/BA |
| 7 | **新股/次新股处理** | 上市初期价格行为异常，是否纳入策略池 | B/DK |
| 8 | **指数成分股调整** | survivorship bias 的来源，需要历史时点成分数据 | B/DK |
| 9 | **交易成本模型** | 佣金 + 印花税 + 过户费 + 滑点，是否分项还是合并 | B/BA |
| 10 | **先卖后买 vs 先买后卖** | 资金利用方式，隐含杠杆假设 | B |
| 11 | **执行可行性/流动性约束** | 成交量限制、冲击成本、排队成交概率；小盘股/事件股尤为关键 | B/BA |

### 输出格式

```
## 业务决策标注清单

### 阶段：{stage_name}

| # | 内容 | 类型 | 业务理由 |
|---|------|------|---------|
| 1 | "先卖后买" | B | 隐含无杠杆假设，换序影响资金利用率 |
| 2 | "止损 -30%" | B/BA | 偏宽阈值，假设长期持有高容忍度 |
| 3 | "T+1 执行延迟" | RC | A 股交割制度强制，非作者选择 |

### 遗漏的业务决策
- 涨跌停板处理：源码中未实现 → 必须在蓝图中标注为已知缺陷
- ...

写入 /tmp/{repo}_business_decisions.md
```

---

## 步骤 2d: 业务用例扫描（v2.3 新增）

**目的**：扫描项目的 examples/notebooks/tutorials，建立业务用例索引。

**为什么需要**：蓝图只描述"框架怎么运作"，但不描述"用框架能做什么"。examples 中的完整策略/研究流程是业务逻辑密度最高的来源（教训 L27）。

### 扫描范围

```
优先级排序：
P0: examples/**/*.py          — 完整可运行策略
P1: notebooks/**/*.ipynb      — 端到端研究流程
P2: docs/tutorials/**/*       — 结构化教程
P3: README.md Quick Start     — 最小可用示例
P4: 源码中继承基类的内置实现   — 内置因子/策略/模型
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
```

**必填字段**（教训 L29）：name、source、type、business_problem、intent_keywords
**推荐字段**：applicable_markets、required_data、required_components、key_parameters、must_validate、not_suitable_for

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

**规则 2：evidence 格式（双锚点，教训 L6）**
```yaml
evidence:
  event_engine: vnpy/event/engine.py:48-78(EventEngine._run)
  # 格式：file:line(function_name)
  # 行号 + 函数签名双锚点，防行号漂移
```

**规则 3：避免过度概括（教训 L4, L7, L17, L20）**
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
| global_contracts 内容 | 仅放**架构不变式**（跨阶段必须遵守的规则）（教训 L13） | 实现特征（如 "@abstractmethod 数量"、"declarative_base 个数"）→ 移到 source.evidence |
| global_contracts 字段名（教训 L19） | 必须使用 `global_contracts` 作为顶级字段名，**禁止**使用 `cross_cutting`、`design_principles` 等非标准名；至少包含 3 条架构不变式 | 缺失或字段名不符 → 必须修正 |
| relations 字段（教训 L18） | 必须主动填充，至少声明 1 条与同子领域蓝图的关系（如 `alternative_to`、`extends`、`depends_on`） | 空列表 → 必须补充；无已有同子领域蓝图时标注"暂无同子领域参照" |
| YAML 特殊字符（教训 L16） | 所有含 `' { } : [ ]` 的字符串值必须加引号包裹 | YAML 解析失败 → 检查并加引号 |
| "所有"/"全部"/"唯一" 频率（教训 L17, L20） | 全文"所有"+"全部" ≤3 次；"唯一"仅允许出现在明确的标识符/主键语境，其他一律替换 | 超标 → 逐一替换为精确表述 |
| business_decisions（教训 L24-L26） | 步骤 2c 标注的 B/BA/DK/RC 类决策必须写入蓝图，至少 5 条 | 缺失 → 回步骤 2c 补充 |
| known_use_cases（教训 L27） | 步骤 2d 扫描的业务用例索引，至少列出项目 examples 中的完整策略 | 缺失 → 回步骤 2d 扫描 |
| 量化金融必审清单（教训 L26） | 11 项 A 股必审业务决策是否逐项审视并记录（存在→标注，不存在→记录为遗漏） | 未审视 → 回步骤 2c |
| replaceable_points 资源完整性（教训 L31） | 每个数据源选项是否包含当前主流方案（如 A 股必须包含 AkShare）；是否列出 Python 依赖包清单；存储后端是否有替代选项描述 | 缺失主流数据源或依赖包 → 补充 |

**规则 6：记录源码版本（教训 L12）**

commit_hash 是**必需字段**，不可省略。字段名统一为 `commit_hash`（教训 L15）。

```yaml
source:
  projects: [owner/repo]
  commit_hash: "abc1234..."  # git rev-parse HEAD 的输出（必需）
  extraction_date: "2026-04-05"
```

**规则 7：YAML 文件必须通过 yaml.safe_load 验证（教训 L16）**

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

---

## 步骤 5: 一致性检查（教训 L8）

新蓝图组装后，在提交评审前，检查与已有蓝图的一致性。

### 检查项

**5a. relations 双向一致**
如果新蓝图声明 `alternative_to: finance-bp-001`，检查 bp-001 是否也有对应的 `alternative_to` 指向新蓝图。

**5b. 对比表事实一致**
如果评审 prompt 中有对比表，确认表中每个单元格的内容与对应蓝图 YAML 中的声明一致。
- 例：对比表说"zipline 有数十个 @abstractmethod"，但 bp-002 说"唯二" → 矛盾，必须修正 bp-002

**5c. applicability 互斥性**
检查不同蓝图的 applicability.not_suitable_for 是否形成互补：
- bp-001 说"不适合 T+1 市场" → bp-003 应该适合
- bp-002 说"不适合实盘" → bp-001/bp-003 应该支持实盘

**5d. 字段名一致性（教训 L15）**
检查所有蓝图的字段命名是否统一：
- `commit_hash`（不是 `commit`）
- `extraction_date`（不是 `extract_date`）
- `not_suitable_for`（不是 `not_for`）
如有不一致，以 SOP 规定的字段名为准。

**5e. stages 结构一致性（教训 L11）**
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

## 三大必查项速查卡

每次提取必须验证以下三类声明，这是出错率最高的区域：

### 必查 1：执行时机
```bash
# 检查信号是否有 shift/延迟
grep -rn 'shift' {repo}/ --include='*.py' | grep -v test | grep -i 'signal\|entry\|exit'
# 检查事件驱动的执行顺序
grep -rn 'cross_order\|get_transactions\|fill\|match' {repo}/ --include='*.py' | grep -v test
```
**常见错误**：把"N+1 执行"写成"同根执行"（freqtrade V2）

### 必查 2：数据结构
```bash
# 检查 DataFrame 索引类型
grep -rn 'set_index\|DatetimeIndex\|as_index\|reset_index' {repo}/ --include='*.py' | grep -v test | head -20
```
**常见错误**：假设 DatetimeIndex（freqtrade V2 实际是普通列）

### 必查 3：@abstractmethod 完整性
```bash
# 完整扫描（绝不能只做部分扫描）
grep -rn '@abstractmethod' {repo}/ --include='*.py' | grep -v test | grep -v __pycache__
# 按文件统计
grep -rn '@abstractmethod' {repo}/ --include='*.py' | grep -v test | cut -d: -f1 | sort | uniq -c | sort -rn
```
**常见错误**：说"唯二"但实际有数十个（zipline）

---

## 验证规则分层（教训 L9）

### 通用层（所有项目必检，5 项）
1. @abstractmethod 完整性
2. ABC 基类定义
3. 程序入口
4. 数据模型（DataFrame/dataclass/ORM）
5. evidence 行号可达性

### 量化交易领域层（10 项）
6. 信号 shift/延迟机制
7. 费率/佣金模型
8. 止损/风控逻辑
9. 主循环执行顺序
10. 模拟盘机制
11. 数据存储格式
12. 交易数据模型（Trade/Order）
13. 参数优化
14. ML 集成
15. 通知/控制系统

### 项目族特化
- **向量化机器人型**（如 freqtrade）：重点检查 shift、dry_run、exchange adapter
- **事件驱动回测型**（如 zipline）：重点检查 Pipeline、corporate actions、calendar
- **插件化平台型**（如 vnpy）：重点检查动态加载、接口完备性、事件引擎

---

## 领域扩展指南

提取新领域的蓝图时：

1. 在 `scripts/blueprint_extract.py` 的 `DOMAIN_CHECKS` 中添加新领域规则
2. 复用本 SOP 的步骤 1-6，调整步骤 2a 的 prompt（替换领域相关检查项）
3. 蓝图存放在 `knowledge/blueprints/{new_domain}/`

---

## 质量追踪

| 项目 | 版次 | 事实错误 | SOP 版本 | 四方平均分 |
|------|------|---------|---------|-----------|
| freqtrade | V2 | 3 | 无 SOP | — |
| freqtrade | V3 | 0 | v1.0（部分） | 86 |
| zipline | V1 | 1 | v1.0 | 88 |
| vnpy | V1 | 0 | v1.0+（含 2b） | 91.5 |

目标：SOP v2.1 下所有新蓝图事实错误 = 0，四方平均分 ≥ 90，L11-L15 合规率 = 100%。
目标（v2.2 新增）：L16-L20 合规率 = 100%（YAML 解析无报错，relations 非空，global_contracts 字段名合规，"所有"/"全部" ≤3 次/蓝图）。
目标（v2.3 新增）：L21-L30 合规率 = 100%（business_decisions ≥5 条且 RC/B 不混标，known_use_cases 含结构化字段，量化金融必审清单 11 项逐项审视）。

### 10 项目批量提取质量（v2.0 → v2.1 审计）

| 项目 | 版次 | 事实错误 | SOP 版本 | 评审分 | L11-L15 合规 |
|------|------|---------|---------|--------|-------------|
| qlib | V1 | 0 | v2.0 | 94 | L12 违规(缺 commit_hash) |
| rqalpha | V1 | 0 | v2.0 | 95 | L15 违规(commit vs commit_hash) |
| QUANTAXIS | V1 | 0 | v2.0 | 91 | PASS |
| stock | V1 | 0 | v2.0 | 92 | L4 违规(2x唯一), L7 风险(12x所有) |
| czsc | V1 | 0 | v2.0 | 95 | PASS |
| zvt | V1 | 0 | v2.0 | 92 | L11 违规(order重复), L13 违规(混入实现细节), L14 违规(缺执行模式) |
| daily_stock_analysis | V1 | 0 | v2.0 | 94 | 空 required_methods |
