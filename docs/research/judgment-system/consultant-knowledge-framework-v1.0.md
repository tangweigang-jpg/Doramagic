# AI 顾问知识结构框架 v1.0

> 四方合成版：Claude × GPT × Gemini × Grok
> 场景：用户说"帮我做一个股票投资分析工具"
> 方法：跨模型 ALIGNED/DIVERGENT/UNIQUE 信号合成

---

## 0. 核心定位

种子晶体不是"约束清单"，而是**领域现实的同构映射**（Gemini）。
它让 LLM 的内部世界模型和真实领域对齐，使 LLM 在生成时自然产出符合领域规律的代码。

种子晶体的完整定义（GPT）：
> 种子晶体 = 世界模型 + 约束 + 资源画像 + 实现模式 + 验证协议 + 证据出处

---

## 1. 核心假设（四方共识校准）

**H1：LLM 与生产级产出的差距，主要是约束知识缺失。**
- 四方共识：正确但不完整（约 85% 准确）
- 补充维度：判据缺失（GPT）、领域本体缺失（Gemini）、验证协议缺失（Grok）
- 修正表述：**差距 = 约束 + 世界模型 + 判据 + 验证**

**H2：种子晶体能激活 LLM 已有但沉睡的知识。**（Claude 独创，GPT/Gemini 佐证）
- LLM "知道" Decimal 但生成时仍用 float
- 种子晶体的作用不仅是注入新知识，还有唤醒旧知识

**H3：知识之间是生成关系（DAG），不是平铺列表。**（Gemini 主导，四方共识）
- 资源选择 → 产生约束 → 影响架构 → 影响实现
- 晶体内部应体现这种因果链

---

## 2. 知识模型

### 维度一：知识类型（6 类）

```
┌─────────────────────────────────────────────────┐
│  ① 世界模型 (World Model / Ontology)             │
│  领域对象是什么、对象间的因果关系、物理规律       │
│  来源: Gemini"领域本体" + GPT"世界模型"           │
│  + Claude"心智模型"                               │
├─────────────────────────────────────────────────┤
│  ② 约束 (Constraint)                             │
│  什么不能做 + 为什么 + 违反后果                   │
│  来源: 四方强共识                                 │
├─────────────────────────────────────────────────┤
│  ③ 资源 (Resource)                               │
│  用什么来做 + 真实能力边界 + 替代方案             │
│  ⚠ 资源选择会生成约束（核心生成关系）             │
│  来源: 四方强共识                                 │
├─────────────────────────────────────────────────┤
│  ④ 模式 (Pattern / Blueprint)                    │
│  验证过的做法 + 适用边界 + 推荐架构               │
│  来源: 四方共识 + GPT"实现蓝图"                   │
├─────────────────────────────────────────────────┤
│  ⑤ 协议 (Protocol)                               │
│  如何验证正确性 + 如何部署 + 如何监控 + 如何降级  │
│  来源: Grok"Protocols" + GPT"验证闭环"            │
├─────────────────────────────────────────────────┤
│  ⑥ 证据 (Evidence)                               │
│  每条知识的来源、置信度、适用范围、时效性         │
│  来源: GPT"证据出处" + Claude"来源标签S1-S4"      │
└─────────────────────────────────────────────────┘
```

**为什么是 6 类而不是 3 / 4 / 5 / 7？**

- 比 Claude 的 3 类（约束/资源/模式）多了：世界模型、协议、证据。四方合成证明这三者不可缺少。
- 比 GPT 的 7 类少了"目标契约"——这是用户输入的编译参数，不是顾问的知识类型。
- 比 Grok 的 5 类少了"合成规则"——这是 AI 顾问的推理能力，不是晶体内容。
- 比 Gemini 的 4 类多了：协议和证据。验证和溯源不能被隐含。

### 维度二：知识层级（4 层）

```
┌─────────────────────────────────────────────────┐
│  L0: 通用层 (Universal)                          │
│  所有软件通用的工程原理                           │
│  LLM 大部分已有，但部分需要"激活"                 │
├─────────────────────────────────────────────────┤
│  L1: 领域层 (Domain)                             │
│  完全独立于软件之外的领域物理规律                  │
│  金融：交易日历、企业行为、监管规则、市场微结构   │
├─────────────────────────────────────────────────┤
│  L2: 工程层 (Engineering)                        │
│  软件如何承载领域事实                             │
│  可靠性、数据管道、精度、状态管理                 │
├─────────────────────────────────────────────────┤
│  L3: 交叉层 (Cross-domain)                       │
│  L1 × L2 碰撞产物                                │
│  领域物理如何改变工程决策                         │
│  ★ 种子晶体的核心价值层 ★                        │
│  ★ 跨项目合成的核心产出 ★                        │
└─────────────────────────────────────────────────┘
```

**为什么是 4 层而不是 3 / 5？**

- Gemini 的 3 层缺少交叉层——但交叉层是 Doramagic 的核心价值
- GPT 的"任务产品层"和 Grok 的"实例层"不是知识层级，是编译时的上下文参数
- GPT 的"运行治理层"归入协议类型，不单独成层

### 维度三：知识来源方法（4 种）

```
S1: 单项目深度分析 → L1/L2 知识（中置信度）
S2: 跨项目合成     → L3 知识（高置信度：ALIGNED信号）
S3: 社区信号挖掘   → failure/constraint 知识（实证级）
S4: AI 推理        → L3 推导知识（低置信度，需标注）
```

---

## 3. 交叉矩阵（股票投资工具填充）

### 3.1 世界模型 × 层级

| 层级 | 世界模型内容 | 来源 |
|------|-------------|------|
| L1 领域 | 股票市场时间非连续（周末/节假日/竞价机制区别）| Gemini |
| L1 领域 | 价格属于离散有理数空间，不是连续实数 | Gemini |
| L1 领域 | 企业行为（拆股/分红/除权）改变价格序列语义 | GPT |
| L1 领域 | 财报发布日期晚于财报所属季度结束日 | GPT |
| L2 工程 | 信号发现与交易执行属于不同生命周期的服务 | Gemini |
| L3 交叉 | 同一系统必须维护两套时间轴（交易日vs日历日）| Claude |

### 3.2 约束 × 层级

| 层级 | 约束 | 违反后果 | 来源 |
|------|------|---------|------|
| L0 通用 | 财务计算禁用 float | 累计PnL偏差 | 四方共识 |
| L1 领域 | 禁止回测中的未来函数（look-ahead bias）| 策略虚假盈利 | Gemini+Grok |
| L1 领域 | 禁止忽略幸存者偏差 | 回测收益虚高3-8% | Claude+GPT |
| L1 领域 | A股T+1交收、涨跌停板 | 策略无法执行 | Gemini |
| L2 工程 | 外部API调用必须有circuit breaker | 级联故障 | Claude |
| L2 工程 | 数据管道必须幂等 | 重复数据 | Claude |
| L3 交叉 | 回测引擎禁止在Tick循环内同步阻塞查询 | 模拟时间失真 | Gemini |
| L3 交叉 | 热恢复后必须重算有状态指标（如EMA）| 虚假交易信号 | Claude |

### 3.3 资源 × 层级（含生成关系）

| 资源 | 能力 | 选择后生成的约束 | 来源 |
|------|------|-----------------|------|
| yfinance | 免费历史EOD | → 不能做实时交易 → 报告必须标注数据滞后 | 四方共识 |
| Alpaca API | 免费实时+执行(美股) | → 必须处理PDT规则 → 必须管理API key | Claude |
| TA-Lib | C库技术指标 | → 必须有编译工具链 → 或改用pandas-ta | Claude |
| pandas float | 默认数值类型 | → 必须改Decimal → 增加"资金守恒"测试 | GPT |
| "当前股票列表" | 无历史成分数据 | → 回测不能宣称无偏差 → 或补充退市数据 | GPT |
| 免费API通用 | 有限流/延迟 | → 必须本地缓存 → 必须指数退避+jitter | Grok+Claude |

### 3.4 模式 × 层级

| 层级 | 模式 | 来源 |
|------|------|------|
| L1 领域 | 前复权/后复权处理（raw + adjusted 双表）| Gemini+GPT |
| L2 工程 | 分层架构：ingest→normalize→feature→simulate→evaluate→report | GPT |
| L2 工程 | 事件驱动回测（vs 向量化仅适合预研）| Gemini+Grok |
| L2 工程 | Research vs Execution 分离 | Grok |
| L3 交叉 | 时间感知的 rate limiter（高峰期降频/切换备用源）| Claude |
| L3 交叉 | Point-in-time join（基本面因子不能回填）| GPT |
| L3 交叉 | Protection 层模式（MaxDrawdown/Cooldown/LowProfitPairs）| Grok |

### 3.5 协议 × 层级

| 层级 | 协议 | 来源 |
|------|------|------|
| L2 工程 | 回测必须建模 slippage + commission + market impact | Grok+GPT |
| L2 工程 | 必须跑 out-of-sample + walk-forward 验证 | Grok |
| L2 工程 | 必须先 dry-run 再 live | Grok |
| L3 交叉 | 回测必须绑定数据快照版本（不能每次重拉API）| GPT |
| L3 交叉 | 自动检测未来函数（所有indicator必须.shift(1)）| Gemini+Grok |
| L3 交叉 | 幸存者偏差检查（验证样本构造方式）| GPT |
| 运行治理 | 数据新鲜度监控 + API限流告警 + 异常输出率 | GPT |
| 运行治理 | 报告必须包含：数据截止日、基准、费用假设 | GPT |

### 3.6 证据标注规范

每条知识附：

| 字段 | 说明 |
|------|------|
| source_type | S1单项目/S2跨项目/S3社区信号/S4推理 |
| confidence | high/medium/low |
| consensus | ALIGNED(共识)/DIVERGENT(分歧)/LOCAL(局部经验) |
| freshness | stable(3年+)/semi-stable(6-18月)/volatile(1-6月) |
| projects | 来源项目列表 |

---

## 4. 知识的生成关系（DAG 结构）

知识不是平铺的，而是有因果生成关系的（Gemini 核心洞察）。

### 4.1 核心生成链

```
用户意图
  │
  ▼
世界模型匹配（这个领域的物理规律是什么？）
  │
  ▼
资源选择（用什么来做？）──→ 生成约束（选了A就不能做B）
  │                              │
  ▼                              ▼
模式推荐（怎么做？）        约束汇总
  │                              │
  ▼                              ▼
协议绑定（怎么验证？）      交叉碰撞（L1×L2→L3）
  │                              │
  └──────────┬───────────────────┘
             ▼
        种子晶体输出
```

### 4.2 生成关系实例

**链条 A：资源→约束→架构→实现**（Gemini）
```
用户要"盘中盯盘自动计算买卖点"
  → 需要毫秒级行情（资源需求）
  → 必须异步事件驱动（架构约束）
  → 回调函数内严禁阻塞I/O（实现约束）
  → 违反后果：订单延误，滑点灾难
```

**链条 B：领域物理→工程选择→验证要求**（GPT）
```
财报发布日期晚于所属季度（领域事实）
  → 基本面因子必须 point-in-time join（工程选择）
  → 回测报告必须声明数据截止日期（验证要求）
  → 违反后果：未来函数导致策略虚假盈利
```

**链条 C：资源缺失→功能降级→声明义务**（GPT）
```
没有历史成分股数据（资源缺失）
  → 回测不能宣称无幸存者偏差（约束生成）
  → 功能降级为"当前股票池历史表现观察"（降级策略）
  → 报告强制声明样本构造方式（协议）
```

---

## 5. 可移植性设计（Claude 独创，全体未反对）

种子晶体是可传播的消费品，必须满足：

**P1: 面向AI消费，不依赖特定LLM。** 写事实性知识（对象层），不写"你是XXX助手"（控制层）。

**P2: 资源推荐需提供替代方案。** 不绑定单一资源，用条件结构：
```
如果用 yfinance → 约束：仅限回测
如果用 Alpaca → 约束：仅限美股 + PDT规则
如果用 Tushare → 约束：积分预算管理
```

**P3: 约束按严重度分级 + 场景标注。**
- 致命级：float禁令、未来函数禁令（所有场景必须遵守）
- 生产级：审计日志、dry-run协议（生产系统必须，学习项目可选）
- 建议级：快照版本化（推荐但不强制）

**P4: 降级策略。**（GPT 独创）
```yaml
degradation:
  if_missing_security_master:
    - downgrade_claims
    - disable_bias_sensitive_backtests
  if_missing_realtime_api:
    - fallback_to_eod_analysis
    - disable_intraday_features
```

---

## 6. 编译流程

```
用户意图: "股票投资分析工具"
    │
    ▼
[上下文探测] 个人学习？实盘交易？团队生产？
    │          目标是分析工具还是交易系统？(GPT T1)
    ▼
[世界模型匹配] 这个领域的物理规律有哪些？
    │            交易日历、企业行为、监管规则...
    ▼
[意图分解] → [数据获取, 技术分析, 回测, 可视化, 风险管理]
    │
    ▼
[资源推荐] 每个子意图 → 推荐资源 + 替代方案
    │        同时生成资源导致的约束
    ▼
[知识收集] 世界模型 + 约束 + 资源约束 + 模式 + 协议
    │
    ▼
[交叉碰撞] L1 × L2 → L3 交叉知识（DAG推理）
    │
    ▼
[上下文筛选] 根据场景（学习/实盘/生产）过滤约束
    │
    ▼
[严重度排序] 致命→生产→建议
    │
    ▼
[时效标注] stable / semi-stable / volatile
    │
    ▼
[降级策略] 标注资源缺失时的降级路径
    │
    ▼
[结构化输出] 种子晶体
```

---

## 7. 种子晶体输出结构（参考 GPT YAML 原型 + 全体共识）

```yaml
crystal:
  meta:
    version: "1.0"
    compiled_for: "个人学习/股票投资分析"
    last_updated: "2026-04-02"
    source_projects: ["freqtrade", "zipline", "vnpy"]
    freshness_policy: "semi-stable, review in 6 months"

  world_model:
    domain: "equities"
    entities: [security, trading_calendar, corporate_actions, ...]
    physics:
      - "市场时间非连续（周末/节假日/竞价机制）"
      - "价格属离散有理数空间"
      - "财报发布日期晚于所属季度"

  resources:
    recommended:
      - name: yfinance
        capability: historical_eod
        constraints_generated:
          - "不能做实时交易决策"
          - "必须本地缓存防限频"
        alternatives: [alpaca, tushare_pro]
    stack: [python, duckdb, parquet]

  constraints:
    fatal:   # 所有场景必须遵守
      - id: C1
        rule: "财务计算禁用float"
        consequence: "累计PnL偏差"
        verify: "静态扫描float在Decimal应出现的上下文"
        evidence: {type: S2, confidence: high, consensus: ALIGNED}
      - id: C2
        rule: "禁止回测中的未来函数"
        consequence: "策略虚假盈利"
        verify: "所有indicator必须.shift(1)"
        evidence: {type: S2, confidence: high, consensus: ALIGNED}
    production:  # 生产系统必须，学习可选
      - id: C3
        rule: "交易状态必须有不可变审计日志"
        ...
    advisory:  # 推荐但不强制
      - id: C4
        rule: "回测绑定数据快照版本"
        ...

  patterns:
    - name: "分层架构"
      structure: "ingest→normalize→feature→simulate→evaluate→report"
      applies_when: "所有场景"
    - name: "事件驱动回测"
      structure: "模拟Broker撮合成交"
      applies_when: "需要精确模拟执行"
      alternative: "向量化回测（仅适合早期预研）"

  protocols:
    pre_deployment:
      - "必须先dry-run模式验证"
      - "回测必须建模slippage+commission"
      - "必须跑out-of-sample验证"
    runtime:
      - "数据新鲜度监控"
      - "API限流告警"
    reporting:
      - "报告必须包含：数据截止日、基准、费用假设"

  degradation:
    if_missing_historical_constituents:
      action: "降级为当前股票池历史观察"
      disclosure: "报告声明样本构造方式"
    if_missing_realtime_api:
      action: "仅支持EOD分析"
      disclosure: "禁用盘中功能"

  evidence:
    consensus_rules: ["float禁令", "未来函数检测", "费用建模"]
    disputed_topics: ["事件驱动vs向量化回测"]
    local_assumptions: ["yfinance可用性"]
```

---

## 8. 自我质疑（保留验证清单）

| # | 问题 | 来源 | 状态 |
|---|------|------|------|
| Q1 | 6类知识类型是否是最优数量？ | 四方分歧 | 待实测 |
| Q2 | 晶体是否有注意力上限（类似SKILL.md 80行衰减）？ | Claude | 待实测 |
| Q3 | 不同LLM对同一晶体的遵守率差异有多大？ | Claude H2 | 待实测 |
| Q4 | "合成规则"是否需要作为元知识写入晶体？ | Grok | 倾向否 |
| Q5 | YAML结构是否是最优机器消费格式？ | GPT | 待对比Markdown |

---

*框架版本: v1.0 — 四方合成版*
*待验证：用 StockAnal_Sys + freqtrade 实测填充，A/B 比较有/无晶体的 LLM 产出*
