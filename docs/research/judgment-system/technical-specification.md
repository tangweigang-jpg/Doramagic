# Doramagic 知识系统技术规格书

> 本文档是知识系统（判断采集流水线 + 编译引擎 + 种子晶体交付）的完整技术规格。覆盖技术栈选型、存储设计、产品形态、部署架构、资源规划，以及各子系统如何连接为一个运转的整体。

---

## 一、技术栈总览

### 1.1 继承的技术基座

Doramagic 已有成熟的技术栈，知识系统在其上构建，不引入新语言、不换构建工具。

| 层 | 选型 | 理由 |
|---|------|------|
| 语言 | Python 3.12 | 全项目统一，LLM 生态最强 |
| 包管理 | uv + hatchling | 已在用，15 个包均通过 hatchling 构建 |
| LLM 调用 | LLMAdapter (`shared_utils`) | 项目规范禁止直接 import anthropic/google，所有 LLM 调用走统一适配器 |
| 类型系统 | contracts 包 | 全项目唯一依赖锚点，Judgment Schema 定义在此 |
| 代码质量 | ruff + mypy + pytest | `make check` 一命令覆盖 lint + typecheck + test |
| CI | GitHub Actions | 已有完整流水线 |
| 部署 | rsync → Mac Mini | 已有 `scripts/release/` 完整 8 步流程 |

### 1.2 知识系统新增依赖

| 依赖 | 用途 | 引入时机 |
|------|------|---------|
| `pydantic` | Judgment Schema 的运行时校验 | 第一次实验 |
| `httpx` | GitHub API 异步调用（Source Adapter） | 第一次实验 |
| `tiktoken` | LLM prompt 的 token 预算管理 | 第一次实验 |
| `asyncpg` / `sqlalchemy[asyncio]` | PostgreSQL 异步访问 | 线上服务 MVP |
| `redis` / `aioredis` | 晶体缓存 + 会话管理 | 线上服务 MVP |
| `sentence-transformers` | 向量相似度计算（去重 + 语义检索） | 判断量 > 500 后 |
| `pgvector` | PostgreSQL 向量索引扩展 | 判断量 > 5,000 后 |
| `schedule` / `APScheduler` | 定时采集任务调度 | 多源采集阶段 |
| `sentry-sdk` | 流水线错误监控 | 上线稳定后 |

**原则：第一次实验极简（JSONL + 内存），线上服务必须有数据库。**

### 1.3 不引入的技术（及原因）

| 候选 | 不引入原因 |
|------|-----------|
| MongoDB | PostgreSQL 的 JSONB 列已经提供了文档存储能力，不需要引入另一个数据库 |
| Celery / RabbitMQ | 采集流水线是批处理模式。`asyncio` + 定时任务足够。消息队列在需要分布式任务调度时再考虑 |
| Neo4j | 关系图谱用 PostgreSQL relations 表 + 应用层 BFS 实现。万级判断下内存遍历毫秒级。图数据库在关系数 > 50 万时再考虑 |
| Elasticsearch | PostgreSQL 的全文索引 + pgvector 的向量索引组合覆盖检索需求。ES 运维成本在初期不匹配 |
| Docker / K8s | 阶段二用单服务器 + rsync 部署。容器化在需要水平扩展（阶段三）时引入 |

---

## 二、存储设计

### 2.1 存储哲学

**三层存储，各司其职。**

Doramagic 的终态是一个线上服务：一个网站/客户端（用户创造自己的晶体）+ 一个 API（为第三方提供知识库服务）。存储设计必须从一开始就面向这个终态，而非从"单人 CLI 工具"出发再迁移。

三层存储对应三种数据特征：

| 层 | 数据 | 特征 | 写入者 | 读取者 |
|---|------|------|-------|-------|
| 知识层 | 判断库 + 关系图谱 | Doramagic 核心资产，高价值、低写入频率、高读取频率 | 采集流水线（内部） | 所有用户 + API 调用方 |
| 用户层 | 账号、晶体配置、编译历史、使用记录 | 用户级数据，高并发读写 | 用户自己 | 用户自己 + 计费系统 |
| 缓存层 | 编译好的晶体、检索结果 | 可重建的衍生数据，高频读取 | 编译引擎 | API 响应 |

### 2.2 知识层存储（判断库）

判断库是 Doramagic 的核心资产。它有两个存在形态：

**形态一：JSONL 源文件（Git 管理的权威版本）**

```
knowledge/
├── bricks/                    # 现有积木（向后兼容）
├── judgments/                  # 判断库
│   ├── domains/
│   │   ├── finance.jsonl      # 金融领域
│   │   ├── healthcare.jsonl   # 医疗领域（未来）
│   │   └── ...
│   ├── universal.jsonl        # 跨领域通用
│   ├── _relations.jsonl       # 关系邻接表
│   └── _vocabulary.yaml       # 词汇归一化字典
└── pipeline/                  # 流水线运行状态
    ├── scout_plans/
    ├── raw_records/
    ├── extraction_queue/
    ├── review_queue/
    └── gap_reports/
```

JSONL 源文件是**采集流水线的写入目标**和**版本控制的对象**。每一颗判断的新增、修改、删除都有 Git 历史。这是知识的"源代码"——就像代码用 Git 管理一样，知识也用 Git 管理。

**形态二：PostgreSQL 运行时数据库（线上服务的查询引擎）**

```sql
-- 核心表
CREATE TABLE judgments (
    id          TEXT PRIMARY KEY,       -- "finance-K-001"
    hash        TEXT NOT NULL,
    core_json   JSONB NOT NULL,         -- core 三元组（支持 JSONB 查询）
    layer       TEXT NOT NULL,          -- "knowledge" | "resource" | "experience"
    scope_json  JSONB NOT NULL,
    confidence_json JSONB NOT NULL,
    compilation_json JSONB NOT NULL,
    version_json JSONB NOT NULL,
    domain      TEXT NOT NULL,          -- 冗余字段，加速按领域查询
    created_at  TIMESTAMPTZ NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_judgments_domain ON judgments(domain);
CREATE INDEX idx_judgments_layer ON judgments(layer);
CREATE INDEX idx_judgments_scope ON judgments USING GIN(scope_json);

-- 关系表（独立，方便图遍历）
CREATE TABLE relations (
    source_id   TEXT NOT NULL REFERENCES judgments(id),
    target_id   TEXT NOT NULL REFERENCES judgments(id),
    rel_type    TEXT NOT NULL,          -- "generates" | "depends_on" | ...
    description TEXT,
    PRIMARY KEY (source_id, target_id, rel_type)
);

CREATE INDEX idx_relations_source ON relations(source_id);
CREATE INDEX idx_relations_target ON relations(target_id);

-- 向量索引（判断量 > 5,000 后启用）
-- 使用 pgvector 扩展
CREATE TABLE judgment_embeddings (
    judgment_id TEXT PRIMARY KEY REFERENCES judgments(id),
    embedding   vector(384)             -- sentence-transformers 输出
);

CREATE INDEX idx_embeddings_ivfflat ON judgment_embeddings
    USING ivfflat (embedding vector_cosine_ops);
```

两种形态的同步关系：

```
采集流水线 → 写入 JSONL → Git commit → 触发同步脚本 → 更新 PostgreSQL
                                                          ↓
线上服务 ← 查询 PostgreSQL ← 用户请求 / API 调用
```

**同步是单向的：JSONL → PostgreSQL。** JSONL 是权威源（source of truth），PostgreSQL 是查询副本。采集流水线不直接写数据库，而是写文件、提交 Git、然后同步。这保证了知识变更的完整审计链。

### 2.3 用户层存储

```sql
-- 用户账号
CREATE TABLE users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email       TEXT UNIQUE NOT NULL,
    name        TEXT,
    plan        TEXT NOT NULL DEFAULT 'free',  -- "free" | "pro" | "enterprise"
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 用户的晶体配置（"我要什么样的晶体"）
CREATE TABLE crystal_configs (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id),
    name        TEXT NOT NULL,                  -- "我的量化回测晶体"
    domain      TEXT NOT NULL,                  -- "finance"
    intent      TEXT NOT NULL,                  -- "用 Python + yfinance 做A股回测"
    user_context JSONB,                         -- 用户提供的个性化上下文
    -- {experience_level, frameworks, target_market, risk_preference, ...}
    filters     JSONB,                          -- 额外过滤条件
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 编译历史（每次编译一条记录）
CREATE TABLE crystal_compilations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    config_id       UUID NOT NULL REFERENCES crystal_configs(id),
    judgment_count  INT NOT NULL,               -- 命中多少颗判断
    coverage_gaps   JSONB,                      -- 缺口报告
    crystal_text    TEXT NOT NULL,              -- 编译产物（晶体全文）
    crystal_hash    TEXT NOT NULL,              -- 晶体内容 hash（用于缓存命中）
    knowledge_version TEXT NOT NULL,            -- 知识库版本（Git commit hash）
    compiled_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- API 调用记录（计费 + 审计）
CREATE TABLE api_calls (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID REFERENCES users(id),     -- NULL = 匿名调用（如果允许）
    endpoint    TEXT NOT NULL,                  -- "/api/crystal/retrieve"
    request_json JSONB,
    response_ms INT,                           -- 响应时间
    cache_hit   BOOLEAN NOT NULL DEFAULT false,
    called_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 2.4 缓存层

晶体是可以缓存的：同样的检索条件 + 同样版本的知识库 = 同样的晶体。

```
缓存键 = hash(intent + user_context + filters + knowledge_version)
缓存值 = 编译好的晶体文本
```

**缓存策略：**

- 初期（单机）：内存缓存（Python `lru_cache` 或 `cachetools`），够用
- 中期（多进程）：Redis，支持多个 API worker 共享缓存
- 晶体文件缓存：编译产物同时写入 `knowledge/crystals/` 目录，静态文件可通过 CDN 分发

**缓存失效：** 知识库更新（新一轮采集入库后）→ `knowledge_version` 变化 → 所有缓存自动失效 → 下次请求重新编译。这是最简单也最安全的策略——知识更新不会很频繁（天/周级），全量失效的代价可以接受。

### 2.5 单颗判断的物理存储格式

JSONL 源文件中，每颗判断一行，完整自包含：

```jsonl
{"id":"finance-K-001","hash":"sha256:a1b2c3...","core":{"when":"处理金融数值（价格、市值、收益率、仓位比例等）时","modality":"must_not","action":"使用 IEEE 754 binary float 做算术运算","consequence":{"kind":"data_corruption","description":"浮点累积误差导致 PnL 偏差，万次运算后偏差可达 0.01%–0.1%"}},"layer":"knowledge","scope":{"level":"domain","domains":["finance"],"context_requires":{"task_types":["calculation","backtest","live_trading"]}},"confidence":{"source":"S2_cross_project","score":0.95,"consensus":"strong","evidence_refs":[{"url":"https://github.com/freqtrade/freqtrade/blob/main/freqtrade/persistence/trade_model.py#L45","description":"freqtrade 用 Decimal 处理所有交易金额"},{"url":"https://github.com/zipline-reloaded/zipline/issues/234","description":"zipline 因 float 精度问题导致回测结果不可复现"}]},"compilation":{"severity":"critical","crystal_section":"hard_constraints","freshness":"stable"},"relations":[{"type":"generates","target":"finance-R-003","description":"精度约束导致必须选择支持 Decimal 的数据管道"}],"version":{"status":"active","created_at":"2026-04-03","updated_at":"2026-04-03","schema_version":"1.0"}}
```

写入 PostgreSQL 时，`core`、`scope`、`confidence` 等嵌套结构存为 JSONB 列，既保持灵活性，又支持 GIN 索引查询。

### 2.6 索引体系

PostgreSQL 提供结构化查询能力后，索引体系变为：

**第一级：关系型索引**（PostgreSQL 内置）

域筛选、层筛选、scope 的 JSONB 路径查询。检索 Step 2 直接匹配直接用 SQL。

**第二级：关系图谱**（relations 表）

检索 Step 3 图谱扩展。用递归 CTE 或应用层 BFS 2 跳遍历。万级判断下，应用层 BFS 更快（全表加载到内存，毫秒级）。

**第三级：向量索引**（pgvector 扩展）

检索阶段语义召回 + 去重弱重复检测。pgvector 比独立的 faiss 好处是：与业务数据在同一个数据库中，查询可以同时过滤结构化条件和向量相似度。

### 2.7 数据量预估与演进

| 阶段 | 判断数量 | 用户数 | 存储方案 |
|------|---------|-------|---------|
| 第一次实验 | 50 颗 | 仅团队 | JSONL 源文件 + SQLite 运行时（或直接内存加载） |
| 单领域覆盖 | 500–2,000 | < 100 | JSONL + PostgreSQL |
| 多领域扩展 | 5,000–20,000 | 100–1,000 | JSONL + PostgreSQL + pgvector + Redis 缓存 |
| 规模化运营 | 50,000+ | 1,000+ | 同上 + 读副本 + CDN 分发晶体 |

**第一次实验时的简化方案：** 判断量只有 50 颗、用户只有团队自己时，不需要 PostgreSQL。直接用 JSONL + 内存加载（或 SQLite）就够了。但代码层面从一开始就通过 Repository 抽象隔离存储细节：

```python
class JudgmentRepository(ABC):
    """存储抽象 — 实现可替换"""

    @abstractmethod
    async def get_by_id(self, id: str) -> Judgment | None: ...

    @abstractmethod
    async def list_by_domain(self, domain: str) -> list[Judgment]: ...

    @abstractmethod
    async def get_relations(self, id: str, max_hops: int = 2) -> list[Relation]: ...

    @abstractmethod
    async def store(self, judgment: Judgment) -> None: ...

    @abstractmethod
    async def search_similar(self, embedding: list[float], top_k: int) -> list[Judgment]: ...


class JsonlRepository(JudgmentRepository):
    """初期实现：JSONL 文件 + 内存索引"""
    ...

class PostgresRepository(JudgmentRepository):
    """线上服务实现：PostgreSQL + pgvector"""
    ...
```

这样流水线代码和业务代码不绑定存储实现，切换时只需要换 Repository 实例。

---

## 三、包架构设计

### 3.1 新增包

知识系统作为独立包集成到 Doramagic 的 15 包分层架构中。

```
packages/
├── contracts/           # [现有] 类型定义 ← Judgment Schema 新增在此
├── shared_utils/        # [现有] LLMAdapter, 公共工具
├── extraction/          # [现有] brick_injection, 框架检测
├── controller/          # [现有] FlowController, DAG 执行
│
├── judgment_schema/     # [新建] Judgment 类型、校验器、序列化
│   └── judgment_schema/
│       ├── types.py          # Pydantic models: Judgment, Relation, EvidenceRef...
│       ├── validators.py     # validate_judgment_core(), atomicity_check()
│       ├── normalizer.py     # 词汇归一化、canonical signature 生成
│       └── serializer.py     # JSONL 读写、索引维护
│
├── judgment_pipeline/   # [新建] 采集流水线
│   └── judgment_pipeline/
│       ├── scout/            # 定向：采集计划生成
│       │   └── planner.py
│       ├── source_adapters/  # 源适配器
│       │   ├── base.py       # RawExperienceRecord, BaseAdapter ABC
│       │   ├── github.py     # GitHubAdapter
│       │   ├── reddit.py     # RedditAdapter（第二批）
│       │   └── ...
│       ├── extract/          # 提取：三条通道
│       │   ├── channel_a.py  # 知识层 — 跨项目共性
│       │   ├── channel_b.py  # 资源层 — 边界测试
│       │   └── channel_c.py  # 经验层 — 社区踩坑（三轨过滤）
│       ├── refine/           # 清洗：四步去重
│       │   ├── normalizer.py # Step 1: 规范化
│       │   ├── bucketer.py   # Step 2: 分桶
│       │   ├── matcher.py    # Step 3: 多信号判重
│       │   └── adjudicator.py# Step 4: LLM 裁决
│       ├── store/            # 入库：关系建立 + 索引
│       │   ├── ingester.py   # 入库主逻辑
│       │   ├── linker.py     # 关系自动建立
│       │   └── indexer.py    # 索引维护
│       └── retrieve/         # 检索：六步流程
│           ├── parser.py     # Step 1: 意图解析
│           ├── matcher.py    # Step 2: 直接匹配
│           ├── expander.py   # Step 3: 图谱扩展
│           ├── blind_spot.py # Step 4: LLM 补盲
│           ├── gap_reporter.py # Step 5: 缺口报告
│           └── ranker.py     # Step 6: 排序裁剪
│
├── crystal_compiler/    # [新建] 种子晶体编译引擎
│   └── crystal_compiler/
│       ├── compiler.py       # 判断集 → 晶体 YAML
│       ├── section_builder.py # 按 crystal_section 组装
│       ├── personalization.py # 宿主平台上下文提示生成
│       └── templates/        # 晶体模板
│           ├── backtest.yaml
│           ├── realtime.yaml
│           └── base.yaml     # 通用骨架
```

### 3.2 依赖关系

```
contracts ←── judgment_schema ←── judgment_pipeline
    ↑                ↑                    ↑
shared_utils ────────┘                    │
    ↑                                     │
extraction ───────────────────────────────┘
    (brick_injection 的框架映射被 Scout 复用)

judgment_pipeline ──→ crystal_compiler
    (检索结果送入编译器)
```

核心原则：`contracts` 仍然是唯一依赖锚点。`judgment_schema` 的类型定义放在 `contracts` 中，实现逻辑放在独立包中。

---

## 四、产品形态

### 4.1 Doramagic 是什么

Doramagic 是一个线上知识服务，有三个面向：

- **网站/客户端**：用户在这里创造属于自己的种子晶体。用户选择领域、描述任务意图、提供个人上下文（使用的框架、目标市场、风险偏好），Doramagic 从知识库中检索匹配的判断，编译成个性化的晶体。
- **API 服务**：第三方开发者/平台通过 API 调用 Doramagic 的知识库。他们可能是 AI 编程助手、自动化工具、或其他想让自己的 LLM 变得更专业的产品。
- **ClawHub skill 分发**：晶体通过 ClawHub 以 skill 形态分发，安装后直接约束宿主平台的 LLM。

### 4.2 形态演进路线

**阶段一：CLI + 内部验证（当前 → 第一次实验）**

```bash
# 运行采集
doramagic harvest --domain finance --source freqtrade --channel experience

# 查看判断库状态
doramagic judgments list --domain finance --layer experience
doramagic judgments stats

# 编译种子晶体
doramagic crystal compile --domain finance --task-type backtest

# 测试检索
doramagic crystal retrieve "我想用 Python + yfinance 做A股回测"
```

这是给团队用的内部工具，验证知识系统的核心假设（采集质量、编译效果、A/B 测试）。

**阶段二：线上服务 MVP（验证通过后）**

```
┌───────────────────────────────────────────────┐
│  Doramagic Web                                │
│                                               │
│  ┌─────────────────────────────────────────┐  │
│  │  "我想做什么": [用 Python 做 A 股回测]    │  │
│  │  "我的背景":   [3年 Python, 新手量化]     │  │
│  │  "我用的工具": [yfinance, freqtrade]      │  │
│  │                                          │  │
│  │         [✨ 生成我的晶体]                  │  │
│  └─────────────────────────────────────────┘  │
│                                               │
│  ┌─ 我的晶体 ────────────────────────────┐   │
│  │ 📋 量化回测晶体 v3                     │   │
│  │    23 条判断 | 2 个缺口警告             │   │
│  │    [复制晶体] [发送到 Claude] [下载]    │   │
│  └───────────────────────────────────────┘   │
│                                               │
│  ⚠️ 知识缺口: A股涨跌停规则、T+1限制        │
│     晶体在此方面的约束尚未覆盖               │
└───────────────────────────────────────────────┘
```

**同时提供 API：**

```
POST /api/v1/crystal/compile
{
  "intent": "用 Python + yfinance 做A股回测",
  "user_context": {
    "experience_level": "intermediate",
    "frameworks": ["freqtrade"],
    "target_market": "cn_a_share"
  }
}

→ 200 OK
{
  "crystal_id": "cr_abc123",
  "crystal_text": "...(编译好的晶体全文)...",
  "judgment_count": 23,
  "coverage_gaps": [
    {"topic": "A股涨跌停规则", "severity": "high"},
    {"topic": "T+1交易限制", "severity": "medium"}
  ],
  "knowledge_version": "v1.2.0"
}

GET /api/v1/judgments/search?domain=finance&layer=experience&limit=20
→ 返回判断列表（供第三方直接使用知识库）

GET /api/v1/crystal/{crystal_id}
→ 返回已编译的晶体（缓存命中，毫秒级响应）
```

**阶段三：ClawHub 集成 + 生态**

种子晶体通过 ClawHub 以 skill 分发。Skill 内嵌晶体 + 个性化提示。用户安装 skill 后：

```
Skill 激活 → 检测用户任务意图
    ↓
调用 Doramagic Crystal API → 获取定制化晶体
    ↓
晶体注入宿主 LLM 的 System Prompt
    ↓
晶体提示宿主平台: "请询问用户以下信息: [框架版本? 目标市场? ...]"
    ↓
用户提供上下文 → context_requires 过滤生效 → 精准约束
    ↓
LLM 在晶体约束下工作 → 输出质量提升
```

### 4.3 用户旅程

```
新用户注册 → 选择领域(如"量化交易") → 描述任务意图
    ↓
Doramagic 检索判断库 → 编译晶体 → 展示结果
    ↓
用户看到：
  - 晶体内容（可预览）
  - 命中的判断数量和分布
  - 覆盖缺口警告
  - 个性化提示（"告诉我你用什么框架，我可以更精准"）
    ↓
用户选择：
  a) 复制晶体文本 → 粘贴到自己的 LLM 对话中
  b) 一键发送到 Claude/GPT（OAuth 集成，未来）
  c) 安装 ClawHub skill → 自动注入
  d) 调用 API → 集成到自己的工具链中
    ↓
使用后反馈 → 回流到知识系统 → 驱动下一轮采集优化
```

---

## 五、部署架构

### 5.1 整体架构概念

Doramagic 的技术系统分为两大部分：**知识工厂**（生产知识）和**知识门店**（服务用户）。

```
┌─────────────────────────────────┐    ┌──────────────────────────────┐
│        知识工厂（Mac Mini）       │    │     知识门店（线上服务器）      │
│                                 │    │                              │
│  所有来源 ──→ 采集 ──→ 提取     │    │   Web / App / API            │
│  GitHub     Scout    Extract    │    │        ↑                     │
│  Reddit        ↓                │    │   晶体编译 + 检索              │
│  Discord   清洗 ──→ 知识库      │ ──→│        ↑                     │
│  雪球      Refine   (JSONL+Git) │同步 │   PostgreSQL（知识库副本）    │
│  博客          ↓                │    │   + 用户数据 + 缓存           │
│            缺口报告 → 下一轮采集  │    │                              │
└─────────────────────────────────┘    └──────────────────────────────┘
```

**核心原则：知识在 Mac Mini 上生产和管理，在线上服务器上消费和交付。**

采集所有来源（GitHub、Reddit、Discord、雪球、博客）不需要多地服务器——API 调用不关心你在哪个城市，一台 Mac Mini 通过各平台 API 就能拉到全球的数据。唯一例外是某些中国平台从海外访问可能不稳定，解法是加一个代理节点（几美元/月），不需要单独维护一台服务器。

### 5.2 阶段一：本机完成全部验证

```
Mac Mini M4 Pro (24GB RAM)
├── Doramagic 主程序 (Python 3.12)
│   ├── CLI 工具（采集、编译、测试）
│   ├── 采集流水线（所有来源：GitHub API + Reddit API + ...）
│   └── 提取 + 清洗 + 入库（全流程）
├── 知识库 (knowledge/ 目录)
│   ├── bricks/ + judgments/ (JSONL 源文件)
│   └── crystals/ (编译产物)
├── SQLite 或内存索引（本地查询验证用）
└── Git 仓库（知识版本控制）
```

目标：验证核心假设。50 颗判断 → 1 颗晶体 → A/B 测试。不对外服务，不需要数据库，不需要服务器。

### 5.3 阶段二：线上服务 MVP

验证通过后，部署线上服务。Mac Mini 继续做知识工厂，线上服务器做知识门店。

```
┌───── 知识工厂（Mac Mini，24h 运行）─────────────────┐
│                                                     │
│  采集引擎（定时运行，覆盖所有来源）                     │
│  ├── GitHubAdapter ──→ freqtrade, zipline, vnpy...  │
│  ├── RedditAdapter ──→ r/algotrading, r/quant...    │
│  ├── DiscordAdapter ──→ freqtrade discord...        │
│  ├── ChineseForumAdapter ──→ 雪球量化（via 代理）     │
│  └── BlogAdapter ──→ 专家博客 RSS                    │
│      ↓                                              │
│  提取 + 清洗 + 入库 → knowledge/judgments/*.jsonl    │
│      ↓                                              │
│  Git commit → 触发同步                                │
│      ↓                                              │
│  同步脚本 → 推送判断数据到线上 PostgreSQL               │
│                                                     │
└─────────────────────────────────────────────────────┘
        │
        │  单向同步（JSONL → PostgreSQL）
        ▼
┌───── 知识门店（线上服务器）──────────────────────────┐
│                                                     │
│  FastAPI 应用                                        │
│  ├── Web 前端（用户创造晶体）                          │
│  ├── Crystal API（/api/v1/crystal/...）              │
│  └── Judgment API（/api/v1/judgments/...）            │
│                                                     │
│  PostgreSQL                                          │
│  ├── judgments + relations（知识层，从 Mac Mini 同步）  │
│  ├── users + crystal_configs（用户层）                 │
│  └── pgvector（向量索引，5000+ 判断后启用）             │
│                                                     │
│  Redis（晶体缓存 + 会话管理）                          │
│                                                     │
└─────────────────────────────────────────────────────┘
        │
        │  反向代理 + CDN + 安全防护
        ▼
┌───── Cloudflare ────────────────────────────────────┐
│  DNS + CDN + WAF + Rate Limiting                     │
│  用户通过 doramagic.com 访问                          │
└─────────────────────────────────────────────────────┘
```

**职责分离：**
- Mac Mini = 知识工厂。负责所有来源的采集、提取、清洗、入库。JSONL 是权威源。24 小时运行，定时采集。
- 线上服务器 = 知识门店。负责面向用户的 Web/App/API。读 PostgreSQL，不运行采集。
- Cloudflare = 安全层。DNS、CDN、WAF、限流。
- 数据流是**单向的**：Mac Mini → 线上服务器。用户永远不直接碰 Mac Mini。

**同步机制：**
Mac Mini 每次采集入库后 Git commit，然后运行同步脚本将新增/变更的判断推送到线上 PostgreSQL。这可以是简单的 `pg_dump` 差量导入，或者通过 API 推送。知识库更新频率是天/周级，不需要实时同步。

**资源需求：**
- Mac Mini：已有，继续做采集 + 开发机
- 线上服务器：2 核 4GB 起步（约 $20-40/月），FastAPI + PostgreSQL + Redis 足够支撑千级用户
- Cloudflare：免费层覆盖 DNS + CDN + 基础 WAF
- 代理节点（如需访问中国平台）：$5-10/月

### 5.4 阶段三：规模化

当用户量和知识量增长到需要扩展时：

```
┌─ 知识工厂 ──────────────────────────────────────────┐
│  Mac Mini（主力采集 + 提取 + 入库）                    │
│  + 代理节点（中国平台访问）                             │
│  多源并行采集，asyncio 异步调度                         │
├─ 知识门店 ──────────────────────────────────────────┤
│  多个 FastAPI Worker（负载均衡）                       │
│  前端静态资源 CDN 分发                                 │
│  晶体文件 CDN 缓存                                    │
├─ 数据层 ────────────────────────────────────────────┤
│  PostgreSQL 主库 + 读副本                             │
│  Redis Cluster（缓存 + 会话）                         │
│  pgvector（大规模语义检索）                             │
├─ Cloudflare ────────────────────────────────────────┤
│  全站 CDN + WAF + Rate Limiting + Workers             │
└─────────────────────────────────────────────────────┘
```

**触发条件**（任一满足则评估扩展）：
- 并发用户 > 1,000
- API 日调用 > 10 万
- 判断量 > 50,000
- Mac Mini 的 LLM API 额度被多源采集占满

---

## 六、LLM 使用规划

### 6.1 各环节的 LLM 需求

| 环节 | LLM 用途 | 调用频率 | 模型要求 | 推荐模型 |
|------|---------|---------|---------|---------|
| Scout | 采集计划生成 | 低（每次采集一次） | 高推理能力 | Claude Opus / GPT-4o |
| Extract 分类 | Issue 分类 | 中（每条 Issue 一次） | 快速分类 | Claude Haiku / GPT-4o-mini |
| Extract 提炼 | 判断三元组提取 | 中（每条高质量 Issue 一次） | 高精度理解 | Claude Sonnet |
| Refine LLM 裁决 | 去重四选一裁决 | 低（仅弱重复候选） | 精确判断 | Claude Sonnet |
| Store 关联 | 自动关系建立 | 中（每颗新判断一次） | 语义理解 | Claude Sonnet |
| Retrieve 意图解析 | 用户意图提取 | 高（每次检索一次） | 快速响应 | Claude Haiku |
| Retrieve LLM 补盲 | 缺口域识别 | 低（仅图谱不足时） | 领域知识 | Claude Sonnet |
| Crystal 编译 | 判断→晶体文本 | 低（编译时一次） | 高质量写作 | Claude Opus |

### 6.2 调用成本估算（第一次实验）

```
目标：从 freqtrade 采集 50 颗判断

Extract:
  GitHub Issues 分类: ~200 条 × Haiku ≈ 200 × $0.001 = $0.20
  判断提炼: ~80 条 × Sonnet ≈ 80 × $0.015 = $1.20

Refine:
  LLM 裁决: ~20 对 × Sonnet ≈ 20 × $0.015 = $0.30

Store:
  关联建立: 50 颗 × Sonnet ≈ 50 × $0.010 = $0.50

Crystal:
  编译: 1 次 × Opus ≈ $0.15

总计: ≈ $2.35
```

**Claude Max 订阅完全覆盖此工作量。** 即使扩展到 500 颗判断，成本也在 $25 以内。LLM API 成本不是瓶颈。

### 6.3 统一通过 LLMAdapter 调用

所有 LLM 调用严格通过 `packages/shared_utils/doramagic_shared_utils/llm_adapter.py`：

```python
from doramagic_shared_utils.llm_adapter import LLMAdapter

adapter = LLMAdapter()

# 轻量分类任务 → 快速模型
classification = await adapter.call(
    model="haiku",
    system="你是一个 GitHub Issue 分类器...",
    prompt=issue_text,
    response_format={"type": "json_object"}
)

# 判断提取 → 高精度模型
judgment = await adapter.call(
    model="sonnet",
    system=EXTRACT_PROMPT_TEMPLATE,
    prompt=source_material,
    response_format={"type": "json_object"}
)
```

好处：统一的错误处理、重试逻辑、token 计数、成本追踪、模型切换。

---

## 七、关键数据流

### 7.1 从 GitHub Issue 到种子晶体的完整路径

```
freqtrade/issues#2345
  "Using yfinance for live trading data causes intermittent
   404 errors during market hours"
  labels: [bug], comments: 7, linked PR: #2348 (merged)
    │
    ▼
[Source Adapter: GitHubAdapter]
  → RawExperienceRecord {
      source_type: "github_issue",
      signals: { has_code_fix: true, reply_count: 7, ... },
      pre_category: "bug"
    }
    │
    ▼
[Extract: 三轨预过滤]
  → 轨道一命中（Closed + Merged PR）→ 直接进入提取
    │
    ▼
[Extract: LLM 分类]
  → bug_confirmed
    │
    ▼
[Extract: LLM 提取 (Sonnet)]
  → Judgment {
      core: {
        when: "在交易时段使用 yfinance 获取实时行情数据时",
        modality: "must_not",
        action: "将 yfinance 的实时数据作为交易执行信号的唯一数据源",
        consequence: {
          kind: "service_disruption",
          description: "yfinance 在市场高峰时段出现间歇性 404 错误，
                        导致交易信号丢失或延迟（Issue #2345 报告）"
        }
      },
      layer: "experience",
      scope: { domains: ["finance"], context_requires: { resources: ["yfinance"] } },
      confidence: { source: "S3_community", score: 0.85, evidence_refs: [...] }
    }
    │
    ▼
[Refine: 四步去重]
  → 规范化 → 分桶(finance) → 匹配(无重复) → 通过
    │
    ▼
[Store: 入库 + 关联]
  → 写入 knowledge/judgments/domains/finance.jsonl
  → AI 发现与 "finance-R-001"(yfinance 禁实时) 高度相关
  → 建立: 新判断 --strengthens--> finance-R-001
    │
    ▼
[Retrieve: 用户查询 "用 yfinance 做A股回测"]
  → P1 直接匹配命中
  → P2 图谱扩展: strengthens → finance-R-001 → generates → finance-R-002
    │
    ▼
[Crystal Compiler]
  → 晶体 hard_constraints 区:
    "⛔ 禁止将 yfinance 用作实时交易数据源。
     yfinance 在市场高峰时段存在间歇性 404 错误（freqtrade#2345）。
     → 如需实时数据，使用 polygon.io 或 alpaca 的 websocket API。
     → 如坚持使用 yfinance，降级为 EOD 研究工具，不做实时交易决策。"
```

### 7.2 缺口闭环

```
用户查询: "我想用 Python 做A股日内交易策略"
    │
    ▼
[Retrieve Step 4: LLM 补盲]
  LLM 识别: "A股有涨跌停规则，日内交易受 T+1 限制"
  → 在库中搜索: 无匹配判断
    │
    ▼
[Retrieve Step 5: 缺口报告]
  → 输出: "知识库在 [A股交易规则: 涨跌停/T+1] 领域无覆盖。
           晶体可信度降低。建议补充来源: A股交易所文档、雪球讨论区"
    │
    ▼
[写入 knowledge/pipeline/gap_reports/]
  gap: { domain: "finance", sub_domain: "cn_a_share_rules",
         missing_topics: ["涨跌停", "T+1", "集合竞价"],
         suggested_sources: ["SSE/SZSE 规则文档", "雪球量化讨论区"] }
    │
    ▼
[下一轮 Scout 读取缺口报告]
  → 自动将 "cn_a_share_rules" 加入采集计划优先级最高
    │
    ▼
[采集 → 入库 → 缺口消除]
```

---

## 八、配置管理

### 8.1 流水线配置

```yaml
# config/pipeline.yaml

scout:
  default_domain: "finance"
  schedule: "0 2 * * *"  # 每天凌晨 2 点
  max_issues_per_run: 500
  github_api_token: "${GITHUB_TOKEN}"  # 环境变量引用

extract:
  channel_c:
    track_1:  # 代码共证轨
      enabled: true
      min_body_length: 0
    track_2:  # 边界妥协轨
      enabled: true
      min_body_length: 50
      labels: ["wontfix", "works-as-intended", "known-issue", "by-design"]
    track_3:  # 信号打分轨
      thresholds:
        bug_incident: 3.0
        discussion: 4.5
        other: 5.0
  llm:
    classification_model: "haiku"
    extraction_model: "sonnet"
    max_retries: 3

refine:
  dedup:
    vector_threshold: 0.78
    scope_overlap_threshold: 0.70
  conflict:
    auto_resolve_severity_gap: 2  # 严重度差 >= 2 级才自动裁决
  llm:
    adjudication_model: "sonnet"

store:
  base_path: "knowledge/judgments"
  auto_link: true
  max_link_candidates: 20  # 每颗新判断最多扫描多少颗已有判断做关联

retrieve:
  graph_max_hops: 2
  llm_blind_spot_trigger: 10  # P1+P2 < 这个数才触发 LLM 补盲
  novice_threshold: 0.4       # 实体密度 < 此值视为新手
  expert_threshold: 0.7
  llm:
    intent_model: "haiku"
    blind_spot_model: "sonnet"

crystal:
  compiler_model: "opus"
  template_path: "packages/crystal_compiler/crystal_compiler/templates/"
  personalization:
    enabled: true
    context_prompt: "请询问用户以下信息以提供更精准的约束..."
```

### 8.2 环境变量

```bash
# .env（不入 Git）
GITHUB_TOKEN=ghp_xxx          # GitHub API 访问
ANTHROPIC_API_KEY=sk-xxx       # Claude API（通过 LLMAdapter）
OPENAI_API_KEY=sk-xxx          # GPT API（可选，跨模型验证用）
GOOGLE_AI_KEY=xxx              # Gemini API（可选）
XAI_API_KEY=xxx                # Grok API（可选）
```

---

## 九、测试策略

### 9.1 分层测试

| 层 | 测试内容 | 工具 | 位置 |
|---|---------|------|------|
| 单元测试 | Schema 校验器、规范化器、签名生成 | pytest | `tests/judgment_schema/` |
| 单元测试 | 三轨过滤器、打分逻辑 | pytest | `tests/judgment_pipeline/extract/` |
| 单元测试 | 去重四步每一步 | pytest | `tests/judgment_pipeline/refine/` |
| 集成测试 | 完整采集流水线（mock LLM） | pytest + fixtures | `tests/judgment_pipeline/integration/` |
| 端到端测试 | 50 颗判断 → 1 晶体 → A/B 对比 | 手动 + 脚本 | `tests/e2e/` |
| 质量测试 | 判断质量抽检（precision/recall） | 人工 + 脚本 | `tests/quality/` |

### 9.2 关键校验函数的测试覆盖

```python
# tests/judgment_schema/test_validators.py

def test_valid_judgment_passes():
    """完整合法判断应通过校验"""

def test_missing_when_fails():
    """缺少 when 条件应被拒绝"""

def test_vague_action_fails():
    """action 中包含'注意''考虑'等模糊词应被拒绝"""

def test_missing_evidence_fails():
    """非 S4_reasoning 来源的判断缺少 evidence 应被拒绝"""

def test_non_atomic_detection():
    """when 中包含'以及''同时'应被标记为疑似非原子"""

def test_canonical_signature_deterministic():
    """同一判断的不同表述应产生相同的 canonical signature"""
```

---

## 十、第一次实验的开发计划

### 10.1 分三个 Sprint

**Sprint 1：基础设施（2 天）**

- 在 contracts 中定义 Judgment Pydantic model（基于 schema-synthesis.md）
- 实现 `validate_judgment_core()` + 模糊词检测 + 原子性检测
- 实现 JSONL 序列化器 + 索引维护
- 实现 canonical signature 生成 + 词汇归一化
- 全部配套单元测试

**Sprint 2：采集流水线（3 天）**

- 实现 GitHubAdapter（拉 freqtrade Issues + PRs）
- 实现通道 C 三轨预过滤器
- 实现 LLM 提取 prompt 模板（分类 + 判断提炼）
- 实现四步去重流水线（初期：规范化 + 分桶 + 强重复条件，弱重复 + LLM 裁决可延后）
- 实现入库 + 自动关联（简化版：同域内匹配）
- 集成测试

**Sprint 3：编译与验证（2 天）**

- 实现晶体编译器（判断集 → 晶体 YAML）
- 实现检索六步流程（Step 1-3 + Step 6 必做，Step 4-5 可简化）
- 端到端测试：50 颗判断 → 1 晶体
- A/B 测试：有晶体 vs 无晶体的 LLM 输出质量对比
- 缺口报告原型

### 10.2 第一次实验的验收标准

```yaml
验收:
  数量: 采集 >= 50 颗判断，覆盖 knowledge + resource + experience 三层
  质量:
    - validate_judgment_core 通过率 100%
    - 人工抽检 20 颗，precision >= 80%（判断是真实且有用的）
    - 去重后无明显重复（人工确认）
  晶体:
    - 编译产出 1 颗种子晶体
    - A/B 测试: 有晶体组的 LLM 输出质量显著优于无晶体组
      （复用之前的 7/8 vs 0/8 测试方法论）
  闭环:
    - 缺口报告至少识别 3 个未覆盖的问题域
    - 缺口可被 Scout 的下一轮计划捕获
```

---

## 十一、风险与缓解

| 风险 | 影响 | 概率 | 缓解 |
|------|------|------|------|
| GitHub API 限频（5000/h） | 采集速度受限 | 中 | 批量采集、缓存已拉取的 Issue、异步调用 |
| LLM 提取质量不稳定 | 判断质量参差 | 高 | 代码级校验拦截 + DSD 幻觉检测 + 人工抽检 |
| 社区偏见（热门 ≠ 重要） | 判断分布偏斜 | 高 | 轨道一（代码共证）绕过社区热度偏见 |
| 虚假完整感 | 用户过度信任 | 中 | 缺口报告作为一等公民，强制输出 |
| 跨领域判断冲突 | 知识矛盾 | 低 | 冲突检测 + 人工队列 |
| JSONL 性能瓶颈 | 响应变慢 | 低（万级内） | 迁移路径清晰：JSONL → SQLite → PostgreSQL |

---

## 十二、术语表

| 术语 | 定义 |
|------|------|
| Judgment（判断） | 最小知识单元。核心三元组：当[条件]时，必须/禁止[行为]，否则[后果] |
| Seed Crystal（种子晶体） | 编译引擎的产物。一组判断按场景组装后，注入宿主 LLM 的约束文本 |
| Brick（积木） | 现有知识格式（JSONL），判断系统的前身 |
| RawExperienceRecord | 源适配器的统一输出格式，所有来源在此标准化 |
| Source Adapter（源适配器） | 将特定平台数据转为 RawExperienceRecord 的转换器 |
| canonical signature | 判断的规范化签名，用于确定性去重 |
| Coverage Gap（覆盖缺口） | 检索时发现的知识空白，驱动下一轮采集 |
| LLMAdapter | Doramagic 的统一 LLM 调用层，禁止直接 import 模型 SDK |
| ClawHub | Doramagic 的 skill 分发平台，slug: dora |
