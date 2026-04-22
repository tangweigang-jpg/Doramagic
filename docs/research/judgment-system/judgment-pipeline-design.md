# Doramagic 判断采集流水线设计方案 v1.1

> 设计哲学：**用 LLM 约束 LLM**。采集阶段的 LLM 被流水线约束，产出高质量判断；消费阶段的 LLM 被种子晶体约束，产出高质量输出。第一环不约束，第二环没有弹药。
>
> v1.1 更新：经 GPT/Gemini/Grok 三方挑战后，对社区过滤、语义去重、检索展开三个环节做了重大修订。详见 `pipeline-challenge-synthesis.md`。

---

## 〇、全局架构

```
┌─────────────────────────────────────────────────────────────┐
│                    判断采集流水线                              │
│                                                             │
│  ┌──────┐   ┌──────┐   ┌──────┐   ┌──────┐   ┌──────┐    │
│  │ 定向  │──▶│ 提取  │──▶│ 清洗  │──▶│ 入库  │──▶│ 检索  │    │
│  │Scout │   │Extract│   │Refine│   │Store │   │Retrieve│   │
│  └──────┘   └──────┘   └──────┘   └──────┘   └──────┘    │
│     AI:        AI:        AI:        AI:        AI:        │
│   研究员      矿工       编辑      图书馆员     顾问       │
│                                                             │
│  约束方式:   约束方式:   约束方式:   约束方式:   约束方式:   │
│  领域本体    三元组模板  质量五标准  关系图谱    意图展开    │
│  指导去哪挖  强制原子化  拒绝模糊    自动连接    主动补全    │
└─────────────────────────────────────────────────────────────┘
         │                                          │
         ▼                                          ▼
    ┌──────────┐                            ┌──────────────┐
    │ 知识源    │                            │  编译引擎      │
    │ GitHub    │                            │  ↓            │
    │ Issues    │                            │  种子晶体      │
    │ 文档      │                            │  ↓            │
    │ 社区      │                            │  约束用户的LLM │
    └──────────┘                            └──────────────┘
```

---

## 一、定向（Scout）—— AI 作为研究员

### 问题
现有流水线是"给一个 GitHub URL，提取知识"——被动接收。但高价值判断不是随机分布的。经验层判断藏在 Issues 的 300 楼回复里，资源层判断藏在 API 的 changelog 里，知识层判断藏在跨项目的共性模式中。AI 需要**主动决定去哪里挖**。

### 设计

#### 输入
一个领域定义（如 "量化交易工具"）+ 已有判断库的当前覆盖状态。

#### AI 的角色
根据三层本体，制定采集计划：

```yaml
scout_plan:
  domain: "quantitative_trading"

  knowledge_layer:
    strategy: "跨项目共性提取"
    targets:
      - type: "cross_project_pattern"
        projects: ["freqtrade", "zipline", "vnpy", "backtrader"]
        goal: "找出所有项目都遵守的隐式规则"
      - type: "domain_literature"
        sources: ["quantitative finance textbooks", "CFA curriculum"]
        goal: "提取数学/金融学定理级约束"
    gap_analysis: "当前库中 knowledge 层仅覆盖精度和偏差，缺少风控、仓位管理、交易成本方面"

  resource_layer:
    strategy: "逐资源边界测试"
    targets:
      - type: "api_boundary_test"
        resources: ["yfinance", "polygon.io", "alpaca", "interactive_brokers"]
        goal: "每个API的真实延迟/限频/数据覆盖范围"
      - type: "library_version_audit"
        resources: ["pandas", "numpy", "ta-lib"]
        goal: "版本间行为差异导致的隐式约束"
    gap_analysis: "当前库中仅覆盖 yfinance，其余数据源空白"

  experience_layer:
    strategy: "社区踩坑提取"
    targets:
      - type: "github_issues"
        projects: ["freqtrade"]
        filter: "label:bug + comments>=5 + created:>2024-01-01"
        goal: "高热度 bug 讨论中的失败模式"
      - type: "community_forum"
        sources: ["freqtrade discord", "quantconnect forum"]
        goal: "用户实战踩坑经验"
    gap_analysis: "经验层几乎为零——Q6/Q7 未实现"
```

#### 对 AI 的约束
Scout 阶段的 LLM 不能凭空想象"哪里可能有知识"。它必须：
1. **基于已有覆盖的缺口分析**——先看库里已经有什么，再决定去补什么
2. **每个 target 必须有具体的可执行地址**——不能说"去看看量化论坛"，必须说"freqtrade 的 GitHub Issues，label:bug，comments>=5"
3. **按三层本体分类计划**——不允许产出一个不分层的"挖掘计划"

#### 复用现有基础设施
- Stage 0 的框架检测 → 自动识别目标项目的技术栈
- brick_injection 的框架映射 → 知道哪些领域已经有基线积木

---

## 一.5、源适配器（Source Adapter）— 多源预设计（v1.1 新增）

### 问题
经验层知识不只在 GitHub。Reddit、Discord、雪球、专家博客都是高价值来源。如果流水线绑死 GitHub API，每接一个新来源都要重构。必须从第一天就做多源抽象。

### 设计原则
**所有来源在进入提取通道之前，都被标准化为同一种中间格式（RawExperienceRecord）。** 提取、清洗、入库、检索完全不关心数据来自哪里。

### 中间格式定义

```python
@dataclass
class RawExperienceRecord:
    """所有来源适配器的统一输出格式"""

    # 来源标识
    source_type: str          # "github_issue" | "reddit_post" | "discord_message" | "forum_post" | "blog_article"
    source_id: str            # 来源内唯一 ID
    source_url: str           # 原始 URL（用于 evidence_ref）
    source_platform: str      # "github" | "reddit" | "discord" | "xueqiu" | "blog"
    project_or_community: str # "freqtrade" | "r/algotrading" | "雪球量化" | ...

    # 内容
    title: str
    body: str                 # 主体文本
    replies: list[str]        # 回复/评论（已排序）
    code_blocks: list[str]    # 提取出的代码块

    # 质量信号（各来源适配器负责映射）
    signals: dict             # 标准化信号，见下方

    # 时间
    created_at: str           # ISO8601
    resolved_at: str | None   # 关闭/解决时间（如有）

    # 分类（适配器预分类，可选）
    pre_category: str | None  # "bug" | "incident" | "workaround" | "design_boundary" | "discussion" | None
```

### 标准化信号体系

不同来源的质量信号不同（GitHub 有 linked_pr，Reddit 有 upvotes），但三轨过滤器需要统一的输入。每个适配器负责把平台特有信号映射为标准信号：

```yaml
standard_signals:
  # 代码共证信号（轨道一）
  has_code_fix: bool          # GitHub: linked merged PR; Reddit/论坛: 不适用
  has_official_resolution: bool  # GitHub: closed by maintainer; Discord: mod 回复

  # 边界妥协信号（轨道二）
  is_design_boundary: bool    # GitHub: wontfix/by-design label; 博客: 作者明确声明限制

  # 通用质量信号（轨道三打分）
  approval_score: float       # GitHub: reactions; Reddit: upvotes; 雪球: 点赞; Discord: emoji reactions
  reply_count: int            # 统一：回复/评论数
  has_repro_steps: bool       # 是否包含复现步骤
  has_logs_or_evidence: bool  # 是否包含日志/截图/数据
  author_credibility: float   # GitHub: contributor?; Reddit: karma; 雪球: 认证?; 博客: 专家?
  expert_reply: bool          # 是否有高信誉者回复并确认
  body_length: int            # 正文长度
  contains_code: bool         # 是否包含代码块
```

### 各来源适配器（按 Grok 的 Tier 排序）

**Tier S：重点自动化采集**

| 适配器 | 来源 | 核心信号映射 | 第一次实验 |
|--------|------|------------|-----------|
| `GitHubAdapter` | GitHub Issues/PR/Discussions | linked_pr → has_code_fix; reactions → approval_score; label → pre_category | ✅ 首批实现 |
| `UserFeedbackAdapter` | Doramagic 用户反馈 | 用户评分 → approval_score; 实盘数据 → has_logs_or_evidence | 未来（需产品上线后） |

**Tier 1：高价值补充**

| 适配器 | 来源 | 核心信号映射 | 第一次实验 |
|--------|------|------------|-----------|
| `RedditAdapter` | r/algotrading, r/quant 等 | upvotes → approval_score; comment_count → reply_count; karma → author_credibility | ❌ 第二批 |
| `DiscordAdapter` | freqtrade Discord, vnpy 群 等 | emoji_count → approval_score; role → author_credibility | ❌ 第二批 |

**Tier 2：辅助来源**

| 适配器 | 来源 | 核心信号映射 | 第一次实验 |
|--------|------|------------|-----------|
| `ChineseForumAdapter` | 雪球量化、知乎、掘金 | 点赞 → approval_score; 评论数 → reply_count; V认证 → author_credibility | ❌ 第三批 |
| `BlogAdapter` | Medium, Substack, 专家博客 | 无社交信号，依赖内容质量; 作者身份 → author_credibility | ❌ 第三批 |

### 三轨过滤器如何适配多源

```
轨道一（代码共证轨）:
  GitHub:  has_code_fix = true (closed + merged PR)
  Reddit:  不适用（Reddit 没有代码修复概念）
  Discord: 不适用
  博客:    不适用
  → 轨道一是 GitHub 独有优势

轨道二（边界妥协轨）:
  GitHub:  is_design_boundary = true (wontfix/by-design)
  Reddit:  帖子中维护者回复"这是预期行为" → is_design_boundary = true
  Discord: 官方成员声明"不会修" → is_design_boundary = true
  博客:    作者明确写"这是设计限制" → is_design_boundary = true
  → 轨道二各来源均适用，但信号强度不同

轨道三（信号打分轨）:
  → 使用标准化信号直接打分，所有来源共享同一公式
  → 唯一区别：不同来源的 approval_score 量级不同，需归一化
     (GitHub reaction 5 ≈ Reddit upvote 50 ≈ 雪球点赞 20)
```

### 接入新来源的标准流程

接入一个新来源只需要三步：
1. 实现 `XxxAdapter`（拉取数据 + 信号映射），~200 行 Python
2. 配置归一化参数（该来源的 approval_score 量级换算）
3. 注册到 Scout 的采集计划中

流水线的 Extract → Refine → Store → Retrieve 无需任何改动。

---

## 二、提取（Extract）—— AI 作为矿工

### 问题
这是整个流水线最关键的环节。AI 需要从源材料中提取原子化判断——不是散文总结，不是知识卡片，而是严格的 `当[条件]时，必须/禁止[行为]，否则[后果]`。

### 设计

#### 三条提取通道（按本体层分）

**通道 A：知识层 — 跨项目共性提取**

```
输入: 同一领域的 N 个项目的 Stage 1.5 Claims
       ↓
Step 1: 找共性
  对 N 个项目的 Claims 做语义聚类
  "freqtrade 用 Decimal" + "zipline 用 Decimal" + "vnpy 用 Decimal"
  → 聚类为: "量化项目普遍避免 float"
       ↓
Step 2: 提炼判断
  LLM prompt（受约束的）:
  "你发现了一个跨项目共性模式。将它转化为一颗判断。
   格式必须是: 当[具体条件]时，必须/禁止[具体行为]，否则[可量化后果]。

   约束:
   - [条件]必须具体到一个工作场景，不能是'开发时'这种泛泛之词
   - [行为]必须是一个可执行指令，不能是'注意安全'这种建议
   - [后果]必须包含可量化的影响或具体的失败表现
   - 如果无法量化后果，写明'后果程度未知，需实验验证'并标记 confidence: low
   - 一颗判断只说一件事。如果你发现两件事，拆成两颗。"
       ↓
Step 3: 证据绑定
  每颗判断必须附带至少一条证据:
  - 来自哪个项目的哪个文件哪一行 (knowledge 层需要至少2个项目佐证)
  - 或来自哪篇文档/论文的具体章节
       ↓
输出: Judgment (scope.level = universal 或 domain, source = S2_cross_project)
```

**通道 B：资源层 — 单资源边界测试**

```
输入: 一个具体资源 (如 yfinance) + 其代码仓库/文档
       ↓
Step 1: 能力声明提取
  从 README/文档中提取资源自称的能力
  "yfinance: download historical market data from Yahoo Finance"
       ↓
Step 2: 边界验证 (复用 Stage 1.5 agentic exploration)
  AI 使用工具实际测试:
  - 调用 API，观察真实延迟
  - 查看 Issue 中的 "doesn't work" / "timeout" / "deprecated"
  - 检查 changelog 中的 breaking changes
       ↓
Step 3: 提炼判断
  LLM prompt（受约束的）:
  "你测试了一个资源的真实边界。将每个边界转化为一颗判断。

   约束:
   - [条件]必须包含这个资源的名称和使用场景
   - [行为]是'可以用于X'或'禁止用于Y'
   - [后果]是超出边界后的具体表现 (延迟、报错、数据丢失)
   - 不要推测你没有验证过的边界"
       ↓
输出: Judgment (layer = resource, scope.level = context)
```

**通道 C：经验层 — 社区踩坑提取（v1.1 三方挑战后重构）**

```
输入: 一个 GitHub 项目的全部 Issues / PRs
       ↓
Step 1: 三轨预过滤 (确定性，不用 LLM)

  轨道一：代码共证轨（最高优先，零门槛）
    规则: Issue 状态 = Closed AND 关联了 Merged PR/Commit
    门槛: 无。不看字数、不看评论数。
    理由: 被代码修复证实的经验 = 最纯的判断原料。
    → 直接进入 Step 2

  轨道二：边界妥协轨（高优先）
    规则: Issue 状态 = Closed AND label IN [wontfix, works-as-intended, known-issue, by-design]
    门槛: body_length >= 50
    理由: 框架作者说"这个修不了/就是这样设计的" = 最高规格的使用禁忌。
    → 直接进入 Step 2

  轨道三：社区信号轨（加权打分）
    打分:
      + 3.0  linked_to_pr_or_commit (未被轨道一捕获的)
      + 2.5  has_repro_steps OR has_expected_vs_actual
      + 2.0  maintainer_reply_with_root_cause
      + 1.5  has_logs_or_stacktrace
      + 1.5  label IN [bug, regression, incident, data-issue]
      + 1.0  reactions >= 3
      + 0.5  comments >= 3 (弱信号)
      + 0.5  body_length >= 120
      - 2.0  pure feature request (无失败证据)
      - 1.5  generic question (无具体场景)
    阈值:
      bug/incident 类: >= 3.0 → 进入 Step 2
      discussion 类:  >= 4.5 → 进入 Step 2
      其余:          >= 5.0 → 进入 Step 2

  不进入任何轨道 → 丢弃
       ↓
Step 2: 分类 (轻量 LLM)
  对每条通过的 Issue 分类:
  - bug_confirmed: 被代码修复证实的 bug（轨道一主力）
  - design_boundary: 框架设计边界/已知限制（轨道二主力）
  - incident: 生产事故
  - workaround: 绕过方案
  - anti_pattern: 社区警告不要这么做
       ↓
Step 3: 提炼判断
  LLM prompt（受约束的）:
  "你正在阅读一组社区讨论。从中提取可操作的判断。

   约束:
   - 轨道一的 Issue：提取 Bug 的根因和修复方向，转化为预防性判断
   - 轨道二的 Issue：提取框架作者声明的能力边界，转化为禁止性判断
   - [后果]必须引用具体案例 ('Issue #2345 中用户报告...')
   - 如果一个失败模式没有明确的预防手段，不要编造 [行为]，
     写成: '必须检查[X条件]是否存在'
   - 区分'这个项目特有的坑'和'这个领域通用的坑'"
       ↓
输出: Judgment (layer = experience, source = S3_community)
```

#### 对提取 LLM 的核心约束（三条通道共享）

这是"用 LLM 约束 LLM"的核心：

**约束 1：三元组模板强制**
LLM 的输出必须严格遵循三元组结构。任何不符合 `当/必须或禁止/否则` 句式的输出，自动拒绝并要求重写。这是代码级强制，不是 prompt 级建议。

```python
def validate_judgment_core(judgment: dict) -> bool:
    """代码级强制，不依赖 LLM 自觉"""
    if not judgment.get("core", {}).get("when"):
        return False  # 缺条件
    if judgment["core"]["modality"] not in ["must", "must_not", "should", "should_not"]:
        return False  # 模态不合法
    if not judgment["core"].get("action"):
        return False  # 缺行为
    if not judgment["core"].get("consequence", {}).get("description"):
        return False  # 缺后果
    # 模糊词检测
    VAGUE_WORDS = ["注意", "考虑", "适当", "合理", "尽量", "可能需要"]
    if any(w in judgment["core"]["action"] for w in VAGUE_WORDS):
        return False  # 行为不够具体
    return True
```

**约束 2：证据强制**
没有 evidence_ref 的判断不允许入库。唯一例外是 `source: S4_reasoning` 的纯推理判断，但必须标记 `confidence.score < 0.6`。

**约束 3：原子性检测**
如果一颗判断的 `when` 或 `action` 中出现"以及""同时""并且"，自动标记为疑似非原子，要求拆分。

**约束 4：幻觉拦截（复用 DSD）**
现有 8 项 DSD 检测直接应用于每颗判断：
- DSD-1：后果没有证据支撑？→ 拒绝
- DSD-4：推理密度过高？→ 降级
- DSD-8：像是模型训练数据而非项目分析？→ 隔离

---

## 三、清洗（Refine）—— AI 作为编辑（v1.1 三方挑战后重构）

### 问题
提取阶段产出的判断可能存在：重复（不同项目中同一条判断的不同表述）、冲突（两条互相矛盾的判断）、粒度不一致（有的太粗有的太细）。

### 设计：四步去重流水线（结构匹配为主，语义为辅）

#### Step 1：规范化（确定性，零成本）

将每颗判断编译为 canonical signature：
```
scope_sig  = normalized(domains + resources + task_types)
rule_sig   = normalized(modality + action + target)
cause_sig  = normalized(consequence.kind + consequence 关键实体)
```

词汇归一化：float → binary_float, PnL ledger/cash ledger → monetary_ledger 等。
完全相同的 signature → 直接标记为重复候选。

#### Step 2：分桶（确定性）

按 `scope_sig` 分桶，只在同桶内做比较。大幅减少计算量，避免跨领域误伤。

#### Step 3：桶内多信号判重

强重复条件（任一命中 → 直接候选）：
- `rule_sig` 一致 + scope 重叠 > 70%
- 同一 resource + 同一 `consequence.kind`
- `cause_sig` 一致（核心洞察：同一根因 = 同一判断，即使 when/action 表述不同）

弱重复条件（送 LLM 裁决）：
- 向量相似度 > 0.78（比原方案 0.85 更低，因为有前置结构过滤保底）
- action family 一致 + consequence 语义相近
- 共享同一上位判断（subsumes 关系）

#### Step 4：LLM 裁决（受约束）

LLM 只能输出四种结果：
- `duplicate_merge`: 同一判断不同表述 → 保留 when 更精确的，证据合并
- `subsumes_link`: A 包含 B → 建立 subsumes 关系
- `strengthens_link`: A 和 B 互为证据 → 建立 strengthens 关系
- `distinct_keep`: 不同判断 → 各自保留

不允许 LLM 自由发挥合并文本。

#### 合并策略

- **永不删除判断** — "合并"= 保留 canonical 主条 + 被合并项通过 relations 挂载
- 主条选择：when 定义最精确 + evidence 最多 + severity 最高
- 被合并项的所有 evidence_refs 追加到主条
- 如果 consequence 冲突 → 不合并，标记 `conflicts` 关系，进入人工队列

#### 冲突检测

对 AI 的约束：
- 冲突检测不依赖 LLM 的"感觉"，而是结构化比较：同一 `scope.domains` + 相反 `modality` = 疑似冲突
- AI 自动裁决只限于 severity 差距 >= 2 级的情况（fatal vs advisory），其余标记为待人工确认
- 裁决理由必须写入 `Relation.description`

#### 粒度校准

对 AI 的约束：
- 如果 `when` 字段超过 50 字 → 可能太复杂，建议拆分
- 如果 `action` 字段少于 5 字 → 可能太模糊，要求补充
- 如果同一 `scope.domains` 下超过 20 颗判断的 `when` 高度相似 → 可能需要合并为一颗 + subsumes 子判断

---

## 四、入库（Store）—— AI 作为图书馆员

### 问题
一颗判断不是孤立存在的。它入库时，必须和已有判断建立连接——否则编译引擎找到一颗判断时，无法沿着关系图谱拉出完整的约束网络。

### 设计

#### 存储格式
JSONL 文件（一行一颗判断），按 `scope.domains` 分文件存储。

```
knowledge/judgments/
  ├── finance.jsonl          # 金融领域
  ├── healthcare.jsonl       # 医疗领域
  ├── universal.jsonl        # 跨领域通用
  └── _index.jsonl           # 全局索引（id → 文件位置）
```

为什么选 JSONL 而非数据库：
- 与现有积木格式一致（knowledge/bricks/ 也是 JSONL）
- Git 可追踪每一颗判断的变更历史
- 初期数据量（万级）不需要数据库
- 随时可以导入数据库，JSONL 是最通用的交换格式

#### 入库时的自动关联（AI 角色）

```
新判断入库:
  id: "finance-R-001"
  when: "需要实时交易决策且数据源为 yfinance"
  action: "禁止依赖 yfinance 作为执行信号的数据源"
       ↓
AI 扫描已有判断库:
       ↓
发现 1: "finance-K-001" (float禁令)
  → 无直接关系，跳过
       ↓
发现 2: "finance-E-001" (dry-run 72小时)
  → AI 判断: yfinance 的不可靠性是 dry-run 必要性的原因之一
  → 建立: finance-E-001 --strengthens--> finance-R-001
  → description: "dry-run 经验验证了不可靠数据源在实盘中的风险"
       ↓
发现 3: "finance-R-002" (选择yfinance时降级为EOD工具)
  → AI 判断: R-001 的成立直接导致 R-002
  → 建立: finance-R-001 --generates--> finance-R-002
  → description: "yfinance实时禁令 → 产品能力必须降级为EOD研究工具"
```

对 AI 的约束：
- 自动关联仅限于同一 `scope.domains` 内的判断（跨领域关联需人工确认）
- 每条自动建立的关系必须有 `description`（原因），不允许无理由的连接
- 关联关系的建立不改变原判断的内容字段（only 追加 relations）
- 每次入库后运行完整性检查：是否有孤立判断（0 条关系）需要人工补连

#### 索引构建

入库时自动维护两个索引（确定性代码，不用 LLM）：

```python
# 索引 1：领域倒排索引（用于 Step 1 粗召回）
domain_index = {
    "finance": ["finance-K-001", "finance-R-001", "finance-E-001", ...],
    "healthcare": [...],
}

# 索引 2：关系邻接表（用于 Step 3 关系展开）
relation_index = {
    "finance-R-001": [
        {"type": "generates", "target": "finance-R-002"},
        {"type": "strengthens", "from": "finance-E-001"},
    ],
}
```

向量索引（用于语义检索）在判断量超过 5,000 颗后再构建。初期用关键词 + 标签匹配足够。

---

## 五、检索（Retrieve）—— AI 作为顾问（v1.1 三方挑战后重构）

### 问题
编译引擎收到用户意图后，需要从判断库中找到所有相关判断。这不是简单的搜索——"我要做量化回测"这句话背后，系统需要拉入 float 精度、幸存者偏差、交易日历、数据源边界等看似不相关但实际必须的判断。

### 设计：图谱优先 + LLM 补盲 + 缺口报告

```
用户意图: "我想用 Python + yfinance 做一个A股回测系统"
       ↓
Step 1: 意图解析（轻量 LLM 或规则）
  提取:
    - domain: finance
    - task_type: backtest
    - resources: [yfinance, python]
    - market: cn_a_share
    - 实体密度得分: 0.6 (用于判断用户水平)
       ↓
Step 2: 直接匹配（确定性）
  从 domain_index 拉出 finance 领域所有判断
  + 从 universal.jsonl 拉出所有跨领域判断
  scope 过滤: context_requires 检查
  version.status = active
  → 产出: P1 判断集（权重 1.0）
       ↓
Step 3: 图谱扩展（确定性，优先于 LLM）
  从 P1 判断出发，沿 generates / depends_on 走最多 2 跳
  自动拉入因果链上的判断
  例: yfinance 限制 → generates → "降级为 EOD 工具"
  → 产出: P2 判断集（权重 0.8）
       ↓
Step 4: LLM 补盲（仅在 P1+P2 不足时触发）
  触发条件: P1 + P2 < 10 颗判断，或用户实体密度 < 0.4（新手）
  LLM 任务: 列出"图谱未覆盖但任务必须考虑的问题域"
  输出: query_tags 列表（不是判断本身）
  用 query_tags 在库中二次召回
  → 产出: P3 判断集（权重 0.6）
  展开预算（动态）:
    简单脚本: 2-3
    研究工具: 4-6
    回测系统: 6-10
    实盘系统: 10+
       ↓
Step 5: 缺口报告（一等公民）
  如果 LLM 在 Step 4 识别的问题域在库中无对应判断:
    → 输出覆盖缺口警告:
      "当前知识库在 [A股涨跌停规则] 领域尚未覆盖。
       此场景的晶体可信度降低。"
  缺口信息同时反馈给 Scout（定向阶段），
  驱动下一轮采集优先补这个缺口。
  → 形成闭环: 检索发现缺口 → Scout 定向补采 → 入库 → 检索不再缺
       ↓
Step 6: 排序与裁剪
  综合排序:
    P1 权重 1.0 × severity × confidence
    P2 权重 0.8 × severity × confidence
    P3 权重 0.6 × severity × confidence
  用户水平调整:
    新手（实体密度 < 0.4）: P2/P3 权重 +0.1
    专家（实体密度 > 0.7）: P3 权重 -0.15
       ↓
输出: 排序后的判断列表 + 缺口报告 → 送入编译引擎组装种子晶体
```

对检索 AI 的约束：
- **图谱扩展优先于 LLM 猜测** — 既然 Schema 设计了 relations，就应该先沿着确定性的边扩展
- LLM 补盲只在图谱扩展不足时触发，且输出 query_tags 而非判断本身
- **缺口报告是一等公民** — 不隐藏知识盲区，主动告知用户并驱动补采闭环
- 展开预算动态调整，不固定上限

---

## 六、全流程的约束哲学总结

| 环节 | AI 角色 | AI 的自由度 | AI 被约束的方式 |
|------|---------|------------|----------------|
| 定向 Scout | 研究员 | 决定去哪里挖 | 必须基于三层本体分类，必须给出具体地址，必须分析已有覆盖缺口 |
| 提取 Extract | 矿工 | 从源材料中识别判断 | 三元组模板强制、模糊词拦截、证据强制、DSD 反幻觉、原子性检测；社区过滤三轨制（代码共证/边界妥协/信号打分） |
| 清洗 Refine | 编辑 | 去重、解冲突、校准粒度 | 四步去重（规范化→分桶→多信号判重→LLM四选一裁决）；锚定 consequence 根因而非表面文本；永不删除只建关系 |
| 入库 Store | 图书馆员 | 建立判断间关联 | 关联限于同域、必须写理由、不改变原判断内容 |
| 检索 Retrieve | 顾问 | 展开用户未说出的需求 | 图谱扩展优先于 LLM 猜测；动态展开预算；缺口报告为一等公民驱动补采闭环 |

**核心原则：AI 在每个环节都有明确的价值（不是摆设），但每个环节都有代码级的约束（不是靠 prompt 自觉）。凡是可以用确定性代码做的，绝不交给 LLM。LLM 只在"需要语义理解"的环节登场，且登场时被严格约束输出格式和范围。**

---

## 七、与现有 Doramagic 基础设施的对接

| 新流水线环节 | 复用的现有组件 | 需要新建的 |
|------------|--------------|-----------|
| Scout | Stage 0（框架检测）、brick_injection（领域映射） | 采集计划生成器 |
| Extract 通道 A | Stage 1.5（agentic exploration）、Phase D（跨项目合成） | 判断三元组 prompt 模板 |
| Extract 通道 B | Stage 1.5（工具调用验证） | API 边界测试 prompt 模板 |
| Extract 通道 C | 研究文档的 Tier 1 规则过滤方案 | Issues/PR 分析器（Q6/Q7 实现）|
| Refine | DSD 8 项检测、置信度系统 | 语义去重器、冲突检测器 |
| Store | knowledge/bricks/ 的 JSONL 格式 | 关系自动建立器、索引生成器 |
| Retrieve | LLM Adapter（多模型支持） | 意图解析器、意图展开器 |

---

## 八、第一次采集的最小可行路径

不需要全部环节都完美才能开始。第一次采集的最小路径：

```
目标: 为"量化交易工具"领域采集 50 颗判断

Step 1 (Scout): 手动指定 freqtrade 作为目标项目（跳过自动定向）
Step 2 (Extract):
  - 通道 A: 复用现有 Stage 1.5 提取 freqtrade 的 Claims → 人工 + LLM 转化为判断
  - 通道 C: 手动拉取 freqtrade 的 top 50 bug Issues → LLM 提取经验层判断
Step 3 (Refine): 人工初审 + 代码校验（validate_judgment_core）
Step 4 (Store): 写入 knowledge/judgments/finance.jsonl
Step 5 (Retrieve): 硬编码一个"量化回测"意图 → 测试检索效果

产出: 50 颗判断 + 1 颗种子晶体 + 1 次 A/B 对比测试
```

估计工作量:
- 代码开发: 2-3 天（三元组 prompt 模板 + validate_judgment_core + JSONL 写入）
- 采集 + 清洗: 1-2 天
- 测试: 1 天

---

## 九、需要跨模型挑战的关键决策点

以下 3 个决策点建议单点发给 GPT/Gemini/Grok 挑战：

### 决策点 1：提取通道 C 的社区知识过滤规则
"body_length >= 80 + comments >= 3"是否太松或太紧？有没有更好的信噪比过滤策略？

### 决策点 2：清洗阶段的语义去重阈值
相似度 > 0.85 标记为重复——这个阈值是否合理？太高漏掉重复，太低误杀合法的相似判断。

### 决策点 3：检索阶段的意图展开策略
AI 应该展开到什么程度？5 个问题域够不够？展开是否应该考虑用户的专业水平（新手展开更多，专家展开更少）？
