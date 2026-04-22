# Claude 的 Judgment Schema 设计方案

---

## 1. Schema 定义

```typescript
interface Judgment {
  // ── 唯一标识 ──
  id: string                    // 格式: "{domain}-{layer}-{seq}" 如 "finance-K-042"

  // ── 核心内容（不可拆分的三元组）──
  when: string                  // 条件：什么场景下适用
  claim: string                 // 判断：必须/禁止/应当做什么
  consequence: string           // 后果：违反或忽略会怎样

  // ── 本体归属 ──
  layer: "knowledge" | "resource" | "experience"

  // ── 领域与适用范围 ──
  domains: string[]             // 适用领域列表，如 ["financial_trading", "domain_finance"]
  scope: "universal" | "domain" | "context"
  //  universal: 跨领域通用（如 float 精度问题）
  //  domain:    领域内通用（如 幸存者偏差）
  //  context:   特定资源/场景下才成立（如 yfinance 特有 bug）
  context_requires?: string[]   // scope=context 时，成立的前提条件
                                // 如 ["resource:yfinance", "market:us_equity"]

  // ── 可信度 ──
  source: "S1_single_project" | "S2_cross_project" | "S3_community" | "S4_reasoning"
  confidence: "high" | "medium" | "low"
  consensus: "aligned" | "divergent" | "local"
  verified_by?: string[]        // 验证过的项目/社区
  evidence_ref?: string         // 具体证据（Issue URL / PR / 论坛帖）

  // ── 编译用 ──
  severity: "fatal" | "production" | "advisory"
  //  fatal:      所有场景必须遵守，违反导致系统性错误
  //  production: 生产环境必须，学习/原型可选
  //  advisory:   推荐但不强制
  crystal_section: "world_model" | "constraints" | "resources" | "architecture" | "protocols"
  freshness: "stable" | "semi_stable" | "volatile"
  //  stable:      3年+ 不变（数学原理、基本物理规律）
  //  semi_stable: 6-18月（框架最佳实践、API用法）
  //  volatile:    <6月（费用结构、限频策略）
  freshness_note?: string       // 如 "美股2024年从T+2改为T+1"

  // ── 关联关系 ──
  relations?: Relation[]
}

interface Relation {
  type: "generates"     // 本判断的成立会生成目标判断
      | "requires"      // 本判断的成立依赖目标判断
      | "conflicts"     // 本判断与目标判断互斥
      | "strengthens"   // 本判断为目标判断提供额外证据
      | "supersedes"    // 本判断替代目标判断（版本更新）
  target_id: string     // 关联的判断 ID
  note?: string         // 关联说明
}
```

---

## 2. 五颗示例判断

### J1: 知识层 — float 禁令（跨领域通用）

```yaml
id: "finance-K-001"
when: "进行金融计算（价格、资金、盈亏、费用）"
claim: "禁止使用 float 类型，必须使用 Decimal 或整数最小单位"
consequence: "IEEE 754 浮点误差累积，导致 PnL 偏差超过 0.01%，审计失败"
layer: knowledge
domains: [financial_trading, domain_finance]
scope: universal        # 适用于所有精度敏感计算
context_requires: null
source: S2_cross_project
confidence: high
consensus: aligned
verified_by: [freqtrade, zipline, vnpy]
evidence_ref: "freqtrade Issue #2345: 上线三天 PnL 累计偏差 0.8%"
severity: fatal
crystal_section: constraints
freshness: stable
relations:
  - type: strengthens
    target_id: "finance-E-012"    # 经验层的实盘验证
    note: "理论约束 + 实盘证据双重支撑"
```

### J2: 资源层 — yfinance 能力边界

```yaml
id: "finance-R-001"
when: "需要获取股票历史价格数据用于回测"
claim: "可以使用 yfinance，但仅限离线回测场景"
consequence: "yfinance 无 SLA、数据延迟 15 分钟、Yahoo 随时改格式导致静默断裂"
layer: resource
domains: [financial_trading]
scope: context
context_requires: ["resource:yfinance"]
source: S2_cross_project
confidence: high
consensus: aligned
verified_by: [freqtrade, zipline]
evidence_ref: null
severity: production
crystal_section: resources
freshness: semi_stable
relations:
  - type: generates
    target_id: "finance-K-015"    # "禁止用免费API做实时交易决策"
    note: "选择 yfinance → 生成实时交易禁令"
```

### J3: 经验层 — dry-run 协议

```yaml
id: "finance-E-001"
when: "将量化策略部署到实盘之前"
claim: "必须先在 dry-run 模式下运行至少 72 小时"
consequence: "跳过 dry-run 的项目在首周出现致命 bug 的概率极高"
layer: experience
domains: [financial_trading]
scope: domain
source: S3_community
confidence: high
consensus: aligned
verified_by: [freqtrade, zipline]
evidence_ref: "freqtrade 社区 300+ 案例 + zipline 文档推荐"
severity: production
crystal_section: protocols
freshness: stable
relations: null
```

### J4: 知识层 — 幸存者偏差（领域特异）

```yaml
id: "finance-K-008"
when: "使用历史数据回测股票策略"
claim: "禁止仅使用当前在市股票列表，必须包含历史退市股"
consequence: "回测收益系统性虚高 3-8 个百分点，实盘后才暴露"
layer: knowledge
domains: [financial_trading]
scope: domain
source: S2_cross_project
confidence: high
consensus: aligned
verified_by: [zipline, vnpy]
evidence_ref: "zipline survivorship-bias-free dataset 讨论"
severity: fatal
crystal_section: constraints
freshness: stable
relations:
  - type: generates
    target_id: "finance-K-009"
    note: "若无历史成分数据 → 必须降级声明"
```

### J5: 交叉判断 — 时间缺口×时序计算

```yaml
id: "finance-X-001"
when: "计算技术指标（MA/RSI/MACD）使用 pandas 时序函数"
claim: "必须基于交易日序列计算，禁止对非交易日做插值填充"
consequence: "5日均线变成7日均线（含周末），所有技术信号失真"
layer: knowledge
domains: [financial_trading]
scope: domain
source: S2_cross_project
confidence: high
consensus: aligned
verified_by: [freqtrade, zipline]    # 两者都维护 trading_calendar
evidence_ref: null
severity: fatal
crystal_section: constraints
freshness: stable
relations:
  - type: requires
    target_id: "finance-R-010"       # 需要交易日历资源
    note: "必须有 trading_calendar 组件才能实现"
```

---

## 3. 关联关系详解

五种关联类型覆盖所有判断间关系：

| 关系类型 | 含义 | 典型场景 |
|---------|------|---------|
| `generates` | A 成立时自动产生 B | 选 yfinance → 生成"禁止实时交易" |
| `requires` | A 成立的前提是 B 也成立 | "交易日序列计算"依赖"有交易日历组件" |
| `conflicts` | A 和 B 不能同时成立 | "用向量化回测"与"需要精确撮合模拟"冲突 |
| `strengthens` | A 为 B 提供额外证据 | 理论约束 + 实盘事故 = 双重佐证 |
| `supersedes` | A 替代 B（版本迭代） | "T+1结算"替代旧的"T+2结算" |

编译引擎使用关联关系的方式：
- `generates`：选中一颗资源判断时，自动拉入它生成的所有约束判断
- `requires`：选中一颗判断时，检查它的前置依赖是否满足
- `conflicts`：两颗冲突判断不能同时进入同一个晶体
- `strengthens`：合并同一约束的多个证据，提升最终置信度
- `supersedes`：编译时自动使用新版替代旧版

---

## 4. 适用范围的查询机制

编译器收到用户意图后，需要快速找到相关判断。查询逻辑：

```
Step 1: 域匹配
  → 找出 domains 包含目标领域的所有判断
  → 同时包含 scope=universal 的判断

Step 2: 上下文过滤
  → 对 scope=context 的判断，检查 context_requires 是否满足
  → 如用户选了 yfinance，则激活所有 context_requires 含 "resource:yfinance" 的判断

Step 3: 关联展开
  → 对选中的判断，沿 generates/requires 关系展开关联判断
  → 检查 conflicts 关系，标记冲突

Step 4: 严重度排序
  → fatal → production → advisory
```

建议索引结构：
- 主索引：`domains[] → judgment_id[]`（域到判断的倒排索引）
- 二级索引：`scope → judgment_id[]`
- 关联索引：`judgment_id → relation[]`

---

## 5. 版本与时效性

```typescript
interface JudgmentVersion {
  judgment_id: string
  version: number             // 递增版本号
  created_at: string          // ISO 日期
  superseded_by?: string      // 被哪个新版本替代
  changelog?: string          // 变更说明
}
```

时效性处理规则：
- `stable`：写入后不设自动审查周期
- `semi_stable`：每 12 个月自动标记为"待审查"
- `volatile`：每 3 个月自动标记为"待审查"
- 审查时，检查 evidence_ref 的链接是否仍然有效、对应项目是否仍在维护

---

## 6. 从现有积木迁移

### 迁移流程

```
现有积木 (1条 200-500字 statement)
    │
    ▼
LLM 提取: 从 statement 中拆分出 2-4 颗判断
    │       每颗判断提取 when/claim/consequence
    ▼
元数据映射:
    │  brick.domain_id        → judgment.domains
    │  brick.knowledge_type   → judgment.layer (rationale→knowledge, failure→experience, constraint→knowledge, pattern→knowledge)
    │  brick.confidence       → judgment.confidence
    │  brick.signal           → judgment.consensus (ALIGNED→aligned, etc.)
    │  brick.source_project_ids → judgment.verified_by
    │  brick.evidence_refs    → judgment.evidence_ref
    │  brick.tags             → judgment.domains + context_requires (需映射)
    ▼
人工校验: 抽样 10% 检查拆分质量
    │
    ▼
关联关系生成: LLM 扫描同领域判断，识别 generates/requires/conflicts
    │
    ▼
写入新知识库
```

### 迁移量估算

- 现有: 10,028 条积木
- 预计拆出: 25,000-40,000 颗判断
- 其中 L0 级（LLM 已有）: ~30% 可标记为 low priority
- 核心高价值判断: ~10,000-15,000 颗
- LLM 迁移成本: ~3-5M tokens（约 $10-15）
- 人工校验: 抽样 1,000 颗，约 2-3 人天

### 迁移示例

现有积木:
```json
{
  "brick_id": "fin-trade-l1-001",
  "statement": "Yahoo Finance's free API (via yfinance) is the fastest path to historical OHLCV data for backtesting, but it is unsuitable for live trading. yfinance scrapes Yahoo's undocumented endpoints and has no SLA — it breaks silently when Yahoo changes its internal format. For backtesting historical strategies, yfinance is sufficient: data is broadly accurate, latency doesn't matter..."
}
```

拆分为:
```yaml
# J-R-001
when: "需要历史 OHLCV 数据用于策略回测"
claim: "可以使用 yfinance"
consequence: "数据基本准确且延迟不影响回测"
layer: resource
scope: context
context_requires: ["use_case:backtesting"]
severity: advisory

# J-R-002
when: "需要做实时交易决策"
claim: "禁止依赖 yfinance"
consequence: "无 SLA、15 分钟延迟、Yahoo 改格式会静默断裂"
layer: resource
scope: context
context_requires: ["use_case:live_trading", "resource:yfinance"]
severity: fatal

# J-R-003
when: "使用 yfinance 作为数据源"
claim: "必须实现本地缓存和静默断裂检测"
consequence: "Yahoo 随时改内部格式，无预警，数据会中断"
layer: experience
scope: context
context_requires: ["resource:yfinance"]
severity: production
relations:
  - type: requires
    target_id: "J-R-001"  # 前提是选了 yfinance
```
