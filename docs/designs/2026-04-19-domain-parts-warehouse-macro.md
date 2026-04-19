# Doramagic 领域配件仓库 — 宏观架构讨论 (v2.1)

**Date**: 2026-04-19
**Status**: Strategic Discussion / RFC (Incorporating Peer Review — GPT + Grok)
**Author**: Session 28 主线程 Opus + 多方评审共识修正（v2.1 吸纳 Grok 独家 STRONG CHALLENGE）
**Scope**: 回答三个宏观问题——框架能否融合、资源能否复用、约束能否复用——以及 Doramagic 从"项目晶体库"走向"领域配件仓库"的演进逻辑与修正路径

---

## 零、问题起源

当前 Doramagic 的工作流是 **一个项目提取蓝图 → 提取约束 → 编译晶体**，各项目独立运行。这本身有价值，但带来三个疑问：

1. **框架融合**：一个项目的框架（蓝图）是否可以和其他框架融合？
2. **资源复用**：一个项目的资源是否可以被运用于其他项目？
3. **约束复用**：一个项目的约束是否可以被运用于其他项目？

**底层驱动**：
- 一个项目有很多功能，有的用户不用，有的需求又没被满足（可能在其他项目里做得更好）
- AI agent 时代，Doramagic 的方法论能否让能力以**跨项目方式**组合给用户
- Doramagic 已提取几十个 finance 项目，是否可以形成**领域配件仓库**用于未来大规模个性化组装

---

## 一、第一性分析：三个问题是同一个问题的三个侧面

三个问题都在问 **"模块化（composability）"**——把单体"项目晶体"拆解成可复用、可组合的原子，让**用户需求**（而非**项目结构**）成为组装的起点。

这不是新问题。软件工程 50 年来反复遭遇同一张网：

| 年代 | 方案 | 组装粒度 | 谁做组装 | 主要失败模式 |
|---|---|---|---|---|
| 1990s | **Software Product Lines (SPL)** | feature-model | 领域工程师 | 前期建模成本巨大，冷启动难 |
| 2000s | OSGi / 插件架构 | bundle / plugin | 开发者 | 接口碎片化，版本地狱 |
| 2010s | Docker / K8s / Helm | container / chart | DevOps | 运行时组装，不解决语义组装 |
| 2010s | NPM / PyPI | package | 开发者手写粘合 | 无语义组合约束 |
| 2015s | **Terraform modules** | declarative module | 工程师写 HCL | 最接近声明式组合，仍需人工布线 |
| 2024+ | **MCP / Tool-use agent** | capability / tool | **LLM 做语义组合** | 缺可组合性保证 |

**Doramagic 的独特位置**：处于 2024+ 代，但在此之上有 v5.3 的 **proof obligation 契约体系**（不变式 + 消费者索引 + 结构化约束 + 质量门禁）。这意味着 LLM 组装时有**可机读的对齐信号**，不需要裸靠自然语言描述拼装。这是 MCP 做不到的。

---

## 二、Q1：框架（蓝图）能融合吗？

### 2.1 第一性分析

一个 blueprint 在 Doramagic 里记录的是 **具体决策（concrete decisions）**，不是**抽象接口（abstract interfaces）**：

- ZVT BD-X："用 SQLAlchemy ORM 存时序数据"
- qlib BD-Y："用二进制 Protocol Buffer 存时序数据"
- freqtrade BD-Z："用 SQLite + JSON blob 存时序数据"

三条 BD 在**同一个架构槽位**（time-series storage）做出了**相互排斥**的决策。直接"融合"等于让三个决策同时成立 = 不可能。

### 2.2 三种融合可行程度

| 融合类型 | 定义 | 可行性 | 代价 |
|---|---|---|---|
| **并列组合** | UC 菜单合并，各跑各的 | ✅ 立即可做 | 几乎零——host 可同时装多颗晶体 |
| **分层替换** | 保留 A 的架构，替换 B 的某一 stage（如因子计算模块）| 🟡 需要接口抽象 | 要求两晶体在该 stage 暴露兼容的**输入输出 schema** |
| **决策级融合** | 取 A 的 BD-X + B 的 BD-Y 组成新蓝图 | ❌ 本质上是重新工程 | BD 之间有隐式依赖网，任意取舍会破坏系统一致性 |

### 2.3 第一性答案

当前形态的蓝图**不能直接融合**，因为记录的是"how"（具体实现决策），不是"what"（能力契约）。

要让框架融合，Doramagic 必须在 blueprint → crystal 中间**挤出一层 capability abstraction**——每个 BD 额外声明"我实现的是哪个抽象能力 + 用了什么兼容 schema"。这是 Software Product Lines 的 feature model 思路，但 2024 的优势是 **LLM 可以自动推导这层抽象**，不必人工建模。

### 2.4 短期可落地的 "融合" —— UC 级并列 + 跨晶体路由

- 用户同时安装 ZVT + qlib 两颗晶体 → host 看到 31 + N 个 UC 的合集
- 用户说"跑一个 Alpha158 因子研究"→ intent_router 命中 qlib 的 UC，不是 ZVT
- 两晶体的脚本、数据库、环境完全独立，互不干扰

**这是 v5.3 已支持的场景**（OpenClaw 可同时装多个 skill），不需要新工具。Doramagic 的真正价值是**让这种共存不产生冲突**——每颗晶体自带 preconditions / host_adapter / namespace，host 天然隔离。

### 2.5 how 层可提取的 pattern（v2.1 Grok 评审新增）

v2.0 把 how 与 what 做了过严的二分，认为 how 层不可融合。Grok 指出此二分把**当前实现形态当成了本质**，忽略了行业先例：

- **LLVM IR**：证明跨语言 how 层抽象可行——C/C++/Rust/Swift 的具体实现决策被规约到同一 IR 层，再 lowering 到不同 target
- **Kubernetes CRD**：证明 how 层可以被声明式抽象而仍保留执行语义
- **React component model**：证明组合式 how（props + children + lifecycle）可跨项目重用

**对 Doramagic 的启示**：54 颗 finance 蓝图在 **time-series storage** 这一架构槽位上，很可能只存在 **~7 种稳定 pattern**（ORM / Parquet / HDF5 / Protocol Buffer / SQLite + JSON / Arrow / MessagePack）而非 54 种独立决策。LLM 2026 已具备**做 pattern mining 提取这 7 种骨架**的能力（非推导抽象本体，而是对具体决策做聚类）。

**因此**：capability_ontology 不必等到 P3 "研究级" 才开始。**P2 阶段可先做 how-pattern 聚类预研**——在 finance 领域 3-5 个关键架构槽位上（time-series storage / factor computation / backtest engine / risk constraint / data source adapter）做 pattern mining，产出的 pattern 即可喂进 UC 级跨晶体路由作为**第二层路由依据**。这不推翻 §2.3 的结论（决策级直接融合仍不可行），但**把 P3 的研究性任务前压到 P2 的预研层**。

---

## 三、Q2：资源能跨项目复用吗？

### 3.1 第一性分析

资源天然分三层，抽象度递增：

| 层 | 例子 | 跨项目复用度 |
|---|---|---|
| **物理包** | `pandas>=2.2` / `numpy>=2.1` | **≈100%**（除版本锁死冲突） |
| **领域数据源** | akshare / baostock / tushare / JoinQuant | **≈80%**（A 股项目几乎都用，API 调用模式不一） |
| **项目专属包** | zvt / qlib / freqtrade | **≈0%**（彼此替代关系） |

**真实洞察**：资源不是"可不可以复用"的问题，而是**"项目 A 知不知道项目 B 已经解决了同一资源需求"**的问题。Doramagic 提取了 54 颗金融蓝图，**相同的资源需求被重复声明 54 次**——没有资源共享规范。

### 3.2 可落地架构 — 领域级资源池

**`knowledge/resource_pool/{domain}.yaml`**：

```yaml
# knowledge/resource_pool/finance.yaml (示意)
shared_packages:
  pandas:
    version_range: ">=2.0,<3.0"
    used_by: [bp-009, bp-087, bp-061, ...]
  akshare:
    version_range: "latest"
    used_by: [bp-009, bp-079, bp-118, ...]

shared_data_sources:
  akshare.stock_zh_a_daily:
    schema: { columns: [date, open, close, ...], ... }
    used_by: [bp-009, bp-079]
    known_pitfalls: [见 finance-C-042：周五 15:30 后数据可能延迟]

project_specific:
  bp-009: [zvt]
  bp-087: [qlib]
  bp-085: [freqtrade]
```

**这个池不是新发明**——它就是 domain-level 的 constraints.jsonl 的资源版。建好只需要一个脚本遍历 54 颗现有蓝图。

### 3.3 增量价值

- 新蓝图编译时优先引用 pool（避免版本漂移）
- 用户机器上同一 domain 的 N 颗晶体共享一次 `pip install` 环境
- 数据源 schema 在 pool 里**提前承诺**，约束层可直接 reference，不必每颗晶体重复声明

### 3.4 第一性答案

资源**最容易跨项目复用**，建议**最先做**。这是 Doramagic 从"晶体库"走向"配件仓库"的第一块砖。

---

## 四、Q3：约束能跨项目复用吗？

### 4.1 第一性分析

约束天然按**抽象度**分层：

| 抽象级 | 例子 | 跨项目适用范围 |
|---|---|---|
| **Universal**（元约束） | rationalization_guard：不虚报覆盖率 | 所有项目（任何领域、任何语言） |
| **Cross-domain** | "包版本锁死优先于 latest" | 所有工程项目 |
| **Domain-wide** | A 股 T+1 结算 / 市值分档规则 / 退市股剔除 | 同领域所有项目 |
| **Architecture-specific** | "MultiIndex 必须是 (entity_id, timestamp)" | 用相同数据模型的项目 |
| **Implementation** | "trading/__init__.py:68 XOR enforcement" | 仅当前项目 |

**现实**：Doramagic 当前 LATEST.jsonl 不做这层分类，所有约束平级混在一起。结果是 **domain-wide 约束（A 股 T+1）被重复抽取 54 次**，而 universal 约束（rationalization_guard）在某些蓝图里缺失。

### 4.2 可落地架构 — 约束继承链

```
universal_constraints.jsonl      (6-8 条，万年不变)
       ↓ 继承
cross_domain_constraints.jsonl   (~20 条工程最佳实践)
       ↓ 继承
finance_domain_constraints.jsonl (~40 条 A 股/港股/美股共识)
       ↓ 继承
{bp}_project_constraints.jsonl   (项目特有)
```

编译晶体时，final constraints = union(四层)。新蓝图只需抽取最底层（项目特有），上层自动继承。
**冲突解决原则**：当下层与上层发生矛盾时，必须实施明确的 override（覆盖）机制和归咎记录，严禁无脑合并。

### 4.3 这是 Linux 发行版模型

base packages + domain packages + user packages。**已被验证可行 30 年**。

### 4.4 第一性答案

约束**最容易产生跨项目复利**，因为：
1. 约束是"否定式知识"（don't do X），天然比肯定式知识更稳定
2. 抽象层次清晰可机读（severity / kind / modality 字段已在）
3. 越抽象的约束越稳定 → 越值得跨项目维护

---

## 五、宏观综合：Doramagic 配件仓库架构

把三个答案合起来，得到一个**分层配件仓库**的雏形：

```
Level 0：Universal Pool                    (元约束 + 元资源，万年不变)
Level 1：Cross-Domain Pool                 (工程最佳实践)
Level 2：Domain Pool (finance / ml / web / infra)
           ├── resource_pool/finance.yaml          ← Q2 答案
           ├── constraints/finance_base.jsonl     ← Q3 答案
           └── capability_ontology/finance.yaml   ← Q1 答案（长期）
Level 3：Project Crystal                   (项目晶体，最具体实现)
```

### 5.1 行动优先级（评审修正版：先验证后抽象）

原计划自下而上建设抽象池存在“需求错位”的致命风险，现调整为验证优先顺序：

| 优先级 | 动作 | 依据 | 估时 | 风险 |
|---|---|---|---|---|
| **P0（原 P2）** | 完善 UC 级跨晶体路由与真实流量验证 | 在建池前，先收集真实流量，跑 4 周确认跨晶体组合需求。避免在无市场需求处修建基础设施。 | 1-2 周 | 低 |
| **P1（原 P0）** | 蓝图门禁清洗与建设 finance resource_pool | 现有 54 颗蓝图存在脏数据，必须**先清洗去毒**再反扫进入共享池化层。 | 2 周 | 中 |
| **P2（原 P1）** | 建 finance constraints 四层继承链 | 需同步确立领域约束的仲裁权与演化治理机制，防范继承腐烂。 | 3 周 | 高 |
| **P3 长期** | 基于 Pattern Mining 的 decision-level 框架融合 | 解决 Token 成本爆炸与冲突降级问题后逐步平滑展开。 | 1 季度+ | 研究级 |

### 5.2 回应用户原始驱动

**驱动 1：一个项目有很多功能，用户可能只用一部分**
→ **已被晶体 UC 粒度路由解决**（intent_router + capability_catalog），用户不会被无关功能骚扰。v5.2 起 host 安装时即呈现 UC 目录，v5.3 UC 名称可翻译。

**驱动 2：一个项目的缺口在另一个项目里被满足**
→ 近期靠 **UC 级并列**（安装多颗晶体，host 合并 UC 菜单），这是 v5.3 **已支持**的场景
→ 远期靠 **capability_ontology**（LLM 看到"用户要 Alpha 因子研究" + "ZVT 没有高质量 Alpha" → 自动建议安装 qlib）

**驱动 3：54 颗 finance 晶体能否形成配件仓库**
→ **能**。入口是 resource_pool + 分层约束继承，技术路径清晰，**不需要科研突破**。真正难点是**命名规范与抽象层次治理**——哪些属于 domain-wide 哪些属于 project-specific，需要**人工决策 + LLM 建议**混合。

---

## 六、领域治理与可观测性（评审新增）

四层池化后若失去控制，将导致系统性腐败。新增以下机制护栏：

1. **治理仲裁机制**：当 `domain_constraints` 出现冲突或需迭代时，必须设立明确的“主线程仲裁”或“领域理事会”流程，不能让 LLM 随机发牌导致劣币驱逐良币。
2. **健康度追踪（可观测性）**：不只是一句话"监控冲突率"。**v2.1 Grok 评审补强 — 必须落到具体指标表**：

   | 指标 | 阈值告警 | 消费者 / 反馈回路 |
   |---|---|---|
   | `resource_pool.conflict_rate` | > 5% | resource_pool 维护者，触发人工裁决 |
   | `inherited_constraints.override_ratio` | > 15% 说明上层约束过严 | 领域理事会，触发约束降级评审 |
   | `capability_ontology.recall` | < 80% 不得入主仓 | ontology 维护者，回归 pattern mining |
   | `capability_ontology.precision` | < 80% 不得入主仓 | 同上 |
   | `cross_crystal_routing.user_coherence` | 用户反馈串台率 > 3% | 路由改进 backlog |
   | `pool.hit_rate`（新蓝图引用 pool 的命中率）| < 60% 说明池抽象层失效 | pool 结构审视 |

   **无指标 = 无演化闭环**。四层池上线后半年必然腐化，如果没有这层量化反馈。

3. **规模成本防护**：当大型领域收纳 5000+ 条约束时，全量质量门禁的 Token 消耗将呈指数级爆炸。编译链中需增加向量截断检索或硬标签阻断过滤设计。同时**约束冲突 union 降级算法**需显式定义——当 domain-wide 与 project-specific 互斥时，规则是"下层覆盖上层 + 归咎记录"，不是"两者皆保留"。

---

## 七、诚实 caveats（v2.1 Grok 评审扩为显式四类失败模式）

### 7.1 治理失败（Governance Failure）

**症状**：`domain_constraints` 出现冲突时没有明确仲裁流程，LLM 随机发牌导致劣币驱逐良币。universal / cross-domain 由谁最终裁定缺失定义。

**防护**：§6.1 治理仲裁机制必须落到**具名主线程或领域理事会**，不是"看情况而定"。每次仓库变更留 append-only 决策日志（who / when / why）。

**判死条件**：半年内仓库腐化，核心约束被反复 override，回归到"54 颗独立晶体"形态。

### 7.2 冷启动失败（Cold-Start Failure）

**症状**：新项目第一颗晶体编译时 pool 尚未包含该项目的资源 / 约束模式，只能走"项目特有"路径。后续再把新项目的资源迁移进 pool 的重构成本高，团队选择"先不进 pool"，仓库变成**只有历史快照、无现在时的摆设**。

**防护**：新晶体编译脚本默认**同时写入晶体 + 向 pool 提交候选项 PR**，由治理流程审核。不让迁移成为事后任务。

**判死条件**：pool 的 `used_by` 列表停留在最初反扫的 54 颗蓝图，3 个月内无新项目加入。

### 7.3 演化失败（Evolution Failure）

**症状**：capability_ontology 上线后，旧晶体使用的 pattern 版本被废弃，**无平滑升级路径**。缺 versioned ontology 与 deprecation 策略，旧晶体要么失效要么被卡死在老版本。

**防护**：引入 `ontology_version` + `min_supported_version` 字段。ontology 变更走**灰度**（先标 deprecated 2 个月，再移除）。旧晶体升级脚本化。

**判死条件**：一次破坏性 ontology 变更让 30%+ 已部署晶体需要人工重编。

### 7.4 用户感知失败（User Perception Failure）

**症状**：用户装 ZVT + qlib + FinRL 后，host 菜单膨胀 3 倍，intent_router 偶尔串台（把"跑 MACD 回测"路由到 qlib 的 Alpha158 而非 ZVT 的 MACD）。用户认知负荷飙升，**更可能只装一颗最好的**——"跨项目组合"的价值不被感知。

**防护**：intent_router 冲突解决需可解释（显示"为什么选这颗"），支持用户偏好锁定。UC 菜单超过阈值（如 50 条）自动折叠分层。

**判死条件**：用户反馈串台率 > 3%（见 §6.2 指标表）；或多晶体安装率 < 20%（大多数用户还是单颗使用）。

---

### 7.5 其他警告

- **四层分层模型（Linux / Terraform）的盲区**：类比需极为谨慎。Terraform 模块的跨团队复用率实质不佳（多为一次性胶水），Linux 靠的是巨大强权与维护者包网络，不要低估构建领域仓库后的重度运维和冷启动负荷。
- **历史蓝图自带剧毒债**：当前提取的 54 颗蓝图并非纯净资产（诸如 P-07 中暴露出的深度硬编码）。**反扫前不做质量门禁清洗，仓库将变成结构化的毒药场**。
- **融合框架短期不要追**：将重点前压至 P0 的业务侧路由验证，验证跨晶体交互存在用户真实拉动时，再铺展框架。v2.1 的 §2.5 pattern mining 是 P2 预研，**不改变 P0/P1/P2 的主顺序**。
- **P-07 ZVT 硬编码问题是配件仓库子问题**：build_resources 的 4 处硬编码实际是**没有 resource_pool 的症状**。修 P-07 的正确姿势不是硬删默认，而是**让默认从 pool 派生**——资源池落地 P-07 自然消解。

---

## 八、与现有工作的衔接

### 8.1 v5.3.1 / v5.4 路线图需要调整

原路线图（见 Session 28 worklog §V）：
1. compile 脚本按消费者分 build block 重构
2. quality_gate 按消费者分层
3. 删除 deprecated 字段
4. schema 全字段 x-consumer

**新增建议**（本文档）：
- **v5.3.1 插入 P0**：建 `knowledge/resource_pool/finance.yaml`，修 P-07（build_resources 从 pool 派生）
- **v5.4 插入 P1**：建约束四层继承链

### 8.2 与蓝图 / 约束抽取工具链的关系

本文讨论的是**编译后的配件仓库**。但真正的反方向也成立：**抽取工具链也应意识到层次**——抽取约束时先问"这是 universal / cross-domain / domain-wide / project-specific 的哪一层"，避免重复抽取。

这意味着 `sops/{domain}/constraint-extraction-sop.md`（如存在）需要同步更新分层规则。**延后到 P1 阶段一起做**。

### 8.3 对晶体编译脚本的要求

未来晶体编译脚本在 v5.4+ 应支持：
- `--inherit-from finance_domain` 参数 → 编译时合并 domain constraints + pool resources
- 生成的 seed.yaml `meta` 段新增 `inheritance_chain: [universal, cross_domain, finance]` 字段
- quality_gate 验证时识别"约束是 inherited 还是 own"，两者都 count 但统计上分开显示

---

## 九、一句话总结

**Doramagic 不是"N 颗独立晶体"，而是"1 个领域配件仓库 + N 颗共享仓库的晶体"**。这不是未来愿景，是当下已经开始累积的既成事实——只是被单体项目的提取方式**掩盖**了。

短期（1 月内）靠 resource_pool + constraints 继承链把这层涌现出来；中期（季度内）靠 UC 级跨晶体路由让用户在"工具集"级别感知；长期（年度内）靠 capability_ontology 让 LLM 能真正做框架级组合。

三步节奏，不颠倒，不跳跃。

---

## 附：关键参考（按相关度排序）

1. **Clements & Northrop, Software Product Lines: Practices and Patterns** (2001) — SPL 方法论经典。教训：前期建模成本是陷阱，反扫归档优于先设计本体。
2. **Terraform modules + Maven BOM + Linux distro 三层依赖管理** — 工业界验证过的分层组合模式。Doramagic 配件仓库架构直接借鉴。
3. **Anthropic MCP (Model Context Protocol) spec** — 2024 LLM + tools 组合范式，缺少可组合性保证；Doramagic 的 proof obligation 契约可补上这层。
4. **v5.3 consumer_map.yaml** — 已建立的字段级分层范式，配件仓库是其在**跨晶体**维度的自然延伸。
5. **PRODUCT_CONSTITUTION.md §1.3**："好晶体 = 好蓝图 + 好约束 + 好资源" —— 本文讨论的是这个等式在**跨晶体**维度上是否成立。答案：成立，但需要把三者**从晶体内提升到领域仓库**。

---

*v1.0 | 2026-04-19 | Session 28 | 主线程 Opus 4.7 (1M) + 用户宏观驱动*
*v2.0 | 2026-04-19 | GPT 评审吸纳（优先级倒置 + 治理观测章节 + caveat 升级）*
*v2.1 | 2026-04-19 | Grok 评审吸纳（§2.5 how-pattern + §6.2 指标表 + §7 四类失败模式 + §2.3 LLM 推导置信区间 caveat）*
