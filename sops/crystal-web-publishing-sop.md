# 晶体 Web 发布 SOP v2.2

> **适用范围**: 全领域通用 | 版本: 2.2 | 日期: 2026-04-18
>
> **架构**：本地编译 agent 完成所有 LLM 密集型工作，生成 Crystal Package，
> 通过专用 Publish API 发布到 doramagic.ai。Web 平台不承担任何 LLM 任务。
>
> **本文件包含三份规格**：
> - **Part 1: Crystal Package Spec** — 本地 agent 产出的数据合约
> - **Part 2: Publish API Spec** — doramagic.ai 侧的接收、校验、持久化规格
> - **Part 3: 发布后 SEO/GEO 动作** — 非自动化但发布者必须执行的动作清单
>
> **v2.2 相对 v2.1 主要变化**：
> - Package Schema 新增 5 个字段组（H 评估数据 / I 变量注入 / J 信任数据 / K 发现元数据 / L SEO-GEO 辅助），闭合 Crystal Page 首屏 5 字段、变量注入器、模型兼容矩阵、三级配方体系、Preset 等产品 FINAL 方案中悬空的数据依赖
> - 质量门禁从 21 条扩至 36 条（31 FATAL + 5 WARN）；FAQ 下限 3→5、数据密度由 WARN 升 FATAL、Title 必须含核心关键词
> - 发布后动作新增 llms.txt 更新、核心关键词 GEO 监测清单、类目页差异化巡检

---

## 架构总览

```
┌──────────────────────────────────────────────────────────┐
│              LOCAL COMPILATION AGENT                       │
│                                                           │
│  输入：Blueprint YAML + Constraints JSONL + Manifest JSON  │
│                                                           │
│  Phase A: 晶体编译（已有 SOP v3.0）                        │
│           → Crystal IR (English) + seed.md                │
│                                                           │
│  Phase B: Web 资产生成（需要 LLM）                          │
│           → slug, definition, description, FAQ,            │
│             userFacingSummary, evidence URLs — 全部双语     │
│           翻译方向：英文晶体 → 中文 Web 资产                  │
│                                                           │
│  Phase C: 打包为 Crystal Package JSON                      │
│                                                           │
│  Phase D: POST /api/publish/crystal                       │
│           → 收到发布报告，失败则自动修复重试                   │
└──────────────────────────┬───────────────────────────────┘
                           │ HTTPS + API Key
                           ▼
┌──────────────────────────────────────────────────────────┐
│              DORAMAGIC.AI  PUBLISH API                     │
│              (Next.js API Route · 零 LLM)                  │
│                                                           │
│  Step 1  鉴权 — API Key 验证                               │
│  Step 2  Schema 校验 — payload 结构完整性                   │
│  Step 3  质量门禁 — 36 项断言 (31 FATAL + 5 WARN)，失败则 400  │
│  Step 4  派生计算 — counts, averages（纯算术）              │
│  Step 5  DB 写入 — Prisma transaction, 6 表 upsert        │
│  Step 6  事件发布 — PlatformEvent + ISR 刷新               │
│  Step 7  返回发布报告                                      │
└──────────────────────────────────────────────────────────┘
```

### 职责边界（铁律）

```
凡需要 LLM 或访问源码仓库的 → 本地 agent
凡纯算术、校验、持久化的     → Publish API
```

| 职责 | 归属 | 理由 |
|------|------|------|
| slug 生成 | agent | 需要语义理解 |
| definition/description 撰写 | agent | 需要 LLM |
| FAQ 生成 | agent | 需要 LLM |
| userFacingSummary 双语生成 | agent | 需要 LLM |
| evidence URL 构建 | agent | 需要读 manifest commit hash |
| 英→中翻译（晶体 v3.0 默认英文） | agent | 需要 LLM |
| 场景文案（applicable/inapplicable） | agent | 需要语义抽取 + 翻译 (v2.2) |
| core_keywords 生成 | agent | 需要模拟用户提问 (v2.2) |
| og_image_fields 撰写 | agent | 需要浓缩成 OG 标语 (v2.2) |
| creator_proof manifest 汇编 | agent | 读 QA 产物 (v2.2) |
| model_compatibility 首发种子 | agent | 从 creator_proof 派生 (v2.2) |
| required_inputs 提取 | agent | 读 Crystal IR context_acquisition (v2.2) |
| tier 首发判定 | agent | 只允许 standard/verified；battle_tested 由平台 (v2.2) |
| constraintCount 计算 | API | 数组长度，纯算术 |
| avgConfidence 计算 | API | 算术平均，纯算术 |
| proofCount / hostCoverage / presetCount | API | 纯算术 (v2.2) |
| model_compatibility 聚合升级 | API/Job | 消费社区报告 (v2.2) |
| tier 升级至 battle_tested | API/Job | 权力归平台 (v2.2) |
| Schema 校验 | API | 信任边界在 API |
| 质量门禁 | API | 信任边界在 API |
| DB 写入 | API | 数据所有权在平台 |
| 状态机管理 | API | 发布权在平台 |

---

# Part 1: Crystal Package Spec

## 1.1 Package 格式

单个 JSON 对象，通过 HTTP POST body 提交。seed.md 以文本内联，不使用文件上传。

**设计依据**：seed.md 本质是 Markdown 文本（通常 10-50 KB），不需要二进制传输。
单请求原子性最好——要么整体成功，要么整体失败，不存在"数据写了一半"的中间态。

## 1.2 Package Schema

```jsonc
{
  // ════════════════════════════════════════════
  // A. 基础标识
  // ════════════════════════════════════════════

  "slug": "string",           // 必填 · URL 永久标识 · 发布后不可改
  "name": "string",           // 必填 · 中文名称
  "name_en": "string",        // 必填 · 英文名称
  "definition": "string",     // 必填 · 一句话定义（中文）
  "definition_en": "string",  // 必填 · 一句话定义（英文）
  "description": "string",    // 必填 · 详细描述（中文，Markdown）
  "description_en": "string", // 必填 · 详细描述（英文，Markdown）
  "category_slug": "string",  // 必填 · 关联 Category
  "tags": ["string"],         // 必填 · 3-8 个 tag slug
  "version": "string",        // 必填 · 语义化版本号 vMAJOR.MINOR.PATCH

  // ════════════════════════════════════════════
  // B. 知识溯源
  // ════════════════════════════════════════════

  "blueprint_id": "string",      // 必填 · 源蓝图 ID
  "blueprint_source": "string",  // 必填 · GitHub owner/repo
  "blueprint_commit": "string",  // 必填 · 40 位 commit hash

  // ════════════════════════════════════════════
  // C. 配方文件
  // ════════════════════════════════════════════

  "seed_content": "string",      // 必填 · seed.md 全文（可达 800KB）
                                 // 存入 DB TEXT 字段，下载时 API 路由返回

  // ════════════════════════════════════════════
  // D. 约束（Web 展示用）
  // ════════════════════════════════════════════

  "constraints": [               // 必填 · ≥1 条
    {
      "constraint_id": "string",       // 必填 · 如 "finance-C-042"
      "severity": "string",            // 必填 · fatal | critical | high
      "type": "string",                // 必填 · RC | B | BA | M | T | DK
      "when": "string",                // 必填 · 触发条件
      "action": "string",              // 必填 · 必须/禁止的行为
      "consequence": "string",         // 必填 · 后果描述
      "summary": "string",             // 必填 · 人话摘要（中文）
      "summary_en": "string",          // 必填 · 人话摘要（英文）
      "evidence_url": "string | null", // 可选 · GitHub permalink
      "evidence_locator": "string",    // 必填 · 源码定位符
      "machine_checkable": "boolean",  // 必填
      "confidence": "number",          // 必填 · 0-1 置信度分数
      "is_cross_project": "boolean",   // 必填 · false=蓝图自有约束, true=跨项目匹配约束
      "source_blueprint_id": "string | null"  // 跨项目约束必填 · 来源蓝图 ID
    }
  ],

  // ════════════════════════════════════════════
  // E. 已知缺陷
  // ════════════════════════════════════════════

  "known_gaps": [                // 可选 · ≤10 条
    {
      "description": "string",      // 必填 · 缺陷描述（中文）
      "description_en": "string",   // 必填 · 缺陷描述（英文）
      "severity": "string",         // 必填 · critical | high
      "impact": "string",           // 必填 · 影响说明（中文）
      "impact_en": "string"         // 必填 · 影响说明（英文）
    }
  ],

  // ════════════════════════════════════════════
  // F. FAQ
  // ════════════════════════════════════════════

  "faqs": [                      // 必填 · 5-8 条（v2.2 下限由 3 提升至 5）
    {
      "question": "string",      // 必填 · 中文问题
      "answer": "string",        // 必填 · 中文回答
      "question_en": "string",   // 必填 · 英文问题
      "answer_en": "string"      // 必填 · 英文回答
    }
  ],

  // ════════════════════════════════════════════
  // G. 版本变更
  // ════════════════════════════════════════════

  "changelog": "string",        // 必填 · 本版本变更说明（中文）
  "changelog_en": "string",     // 必填 · 本版本变更说明（英文）
  "contributors": ["string"],   // 必填 · 贡献者列表，如 ["@doramagic-bot"]

  // ════════════════════════════════════════════
  // H. 消费者评估数据（Crystal Page 首屏 5 字段的数据基座）
  // ════════════════════════════════════════════

  "sample_output": {             // 必填 · 示例输出（E3 三层 Proof Pack 的 L1 Creator Proof 派生）
    "format": "string",          // 必填 · trace_url | screenshot_url | video_url | text_preview
    "primary_url": "string | null",  // trace/screenshot/video 格式时必填
    "text_preview": "string | null", // text_preview 格式时必填，≤600 字符
    "caption": "string",         // 必填 · 一句话说明输出是什么（中文）
    "caption_en": "string"       // 必填 · 同上英文
  },

  "applicable_scenarios": [      // 必填 · ≥2 条 · "这个配方适合谁/什么情况"
    { "text": "string", "text_en": "string" }
  ],

  "inapplicable_scenarios": [    // 必填 · ≥2 条 · 明确划出不适用场景（诚实边界）
    { "text": "string", "text_en": "string" }
  ],

  "host_adapters": [             // 必填 · ≥1 条 · 目标宿主列表，驱动兼容性 UI
    {
      "host": "string",          // 必填 · openclaw | claude_code | codex_cli | gemini_cli
      "load_method": "string",   // 必填 · 如 "SKILL 文件加载" / "CLAUDE.md 粘贴"
      "notes": "string | null"   // 可选 · 宿主特有说明（中文）
    }
  ],

  // ════════════════════════════════════════════
  // I. 变量注入（前端渲染表单）
  // ════════════════════════════════════════════

  "required_inputs": [           // 必填 · 可为空数组 · 与 seed.md 中的 {{placeholder}} 一一对应
    {
      "name": "string",          // 必填 · placeholder 名，/^[a-z][a-z0-9_]{0,31}$/
      "type": "string",          // 必填 · string | number | date | enum | multiline
      "required": "boolean",     // 必填 · 留空时 AI 会在 directive 中追问
      "default": "string | null",// 可选 · 默认值
      "enum_options": ["string"] | null, // type=enum 时必填
      "hint": "string",          // 必填 · 表单输入框下方的提示（中文）
      "hint_en": "string",       // 必填 · 同上英文
      "example": "string | null" // 可选 · 示例值
    }
  ],

  // ════════════════════════════════════════════
  // J. 信任数据（Proof Pack + 模型兼容矩阵的首发种子）
  // ════════════════════════════════════════════

  "creator_proof": [             // 必填 · ≥1 条 · 官方自测证据（L1 Creator Proof）
    {
      "model": "string",         // 必填 · 如 "claude-sonnet-4-6"
      "host": "string",          // 必填 · 同 host_adapters.host 枚举
      "evidence_type": "string", // 必填 · trace_url | screenshot_url | video_url
      "evidence_url": "string",  // 必填 · 必须 HTTPS，公开可访问
      "tested_at": "string",     // 必填 · ISO 8601 日期
      "summary": "string",       // 必填 · 一句话说明自测通过了什么（中文）
      "summary_en": "string"     // 必填 · 同上英文
    }
  ],

  "model_compatibility": [       // 必填 · ≥1 条 · 首发种子数据，后续由社区报告聚合覆盖
    {
      "model": "string",         // 必填 · 标准化模型 ID
      "status": "string",        // 必填 · recommended | compatible | partial | not_recommended
      "note": "string | null",   // 可选 · 兼容性说明（中文）
      "note_en": "string | null" // 可选 · 同上英文
    }
  ],

  // ════════════════════════════════════════════
  // K. 发现元数据（三级配方体系 + 旗舰/Preset 模型）
  // ════════════════════════════════════════════

  "tier": "string",              // 必填 · standard | verified | battle_tested
                                 // agent 首次发布默认 standard；升级由平台作业计算，不由 agent 提交
  "is_flagship": "boolean",      // 必填 · 是否为该蓝图的旗舰配方
  "parent_flagship_slug": "string | null",
                                 // is_flagship=false 时必填；is_flagship=true 时必须为 null
  "presets": [                   // 可选 · 仅旗舰配方可挂载 Preset
    {
      "preset_slug": "string",   // 必填 · 在父旗舰下唯一，/^[a-z][a-z0-9-]{2,40}$/
      "name": "string",          // 必填 · 中文名
      "name_en": "string",       // 必填
      "description": "string",   // 必填 · 中文一句话描述
      "description_en": "string",// 必填
      "price_model": "string",   // 必填 · free | paid
      "price_usd": "number | null", // price_model=paid 时必填，≥0
      "variable_overrides": {    // 必填 · 该 Preset 预设的变量值，与 required_inputs 对齐
        "<input_name>": "string"
      }
    }
  ],

  // ════════════════════════════════════════════
  // L. SEO / GEO 辅助字段
  // ════════════════════════════════════════════

  "core_keywords": ["string"],   // 必填 · 5-10 个长尾词 · 发布后用于 GEO 抽查
                                 // 至少 2 条中文、2 条英文，代表用户真实提问
  "meta_title_suffix": "string | null",
                                 // 可选 · 默认 "Doramagic"；非标准后缀需显式覆盖
  "og_image_fields": {           // 必填 · 驱动 /api/og/[slug] 动态渲染
    "headline": "string",        // 必填 · OG 图主标题（中文，≤24 字）
    "headline_en": "string",     // 必填 · ≤40 字符
    "stat_primary": "string",    // 必填 · 如 "42 条防坑规则"
    "stat_primary_en": "string", // 必填
    "stat_secondary": "string",  // 必填 · 如 "8 条 FATAL · 17 处源码"
    "stat_secondary_en": "string"// 必填
  }
}
```

## 1.3 字段生成规则

以下规则指导本地 agent 如何从 Crystal IR + Blueprint + Constraints 生成 Package 中的每个字段。

### 翻译方向

Crystal IR v2.0 的 prose 默认为英文（编译 SOP v3.0 Step 0a）。Web 资产生成时：

| 字段类型 | `_en` 字段 | 中文字段 |
|---------|-----------|---------|
| name, definition, description | 从 Crystal IR 英文内容派生 | LLM 从英文翻译为中文 |
| constraint summary | 从英文 when/action/consequence 三元组生成 | LLM 从英文翻译为中文 |
| FAQ | 从英文 Crystal IR 生成英文版 | LLM 从英文翻译为中文 |
| known_gaps | 从英文 business_decisions 派生 | LLM 从英文翻译为中文 |
| changelog | 编写英文版 | LLM 从英文翻译为中文 |

**翻译质量规则**：技术精度 > 文学优雅。领域术语使用编译 SOP v3.0 Step 0c 的术语对照表。

### A. 基础标识

#### slug

**输入**：Crystal IR `user_intent.description` + `target_market`

**规则**：
- 动作 + 对象 + 上下文，3-6 个英文单词，`-` 连接
- 全小写，≤60 字符
- 包含核心任务关键词（SEO 长尾词命中）
- 不暴露内部编号（blueprint ID、constraint ID）
- 不暴露源项目名（用户不关心蓝图来自哪个 repo）

```
✅ macd-backtest-a-shares
✅ credit-scorecard-python
❌ bp-009（内部编号）
❌ zvt-macd-day-trader（暴露框架名）
```

#### name / name_en

**输入**：Crystal IR `crystal_name` + `user_intent`

**规则**：
- 中文：任务导向，10-25 字，包含"配方"二字
- 英文：≤60 字符，不加 "Recipe"
- 包含目标市场/领域关键词

```
name: "A股MACD金叉策略回测配方"
name_en: "MACD Crossover Backtest for A-Shares"
```

#### definition / definition_en（GEO 第一优先级）

**输入**：Crystal IR `user_intent.description` + constraints 总数 + Blueprint `applicability`

**模板**：
```
{配方名} 是一个帮你 {具体动作} 的 AI 任务配方，
覆盖 {N} 条防坑规则，适用于 {场景}。
```

**规则**：
- 中文 40-80 字，英文 80-160 字符
- 直接回答"这是什么"，不铺垫
- 至少包含一个具体数字（约束条数）
- 这是 AI 引擎抓取时语义权重最高的文本，每个字都要有信息密度

#### description / description_en

**输入**：Crystal IR `user_intent` + `stages` + `context_acquisition.required_inputs` + Blueprint `applicability`

**结构**：
```markdown
## 这个配方帮你做什么

{一段话，扩展 definition}

## 你需要准备什么

- {输入 1}
- {输入 2}

## 执行流程

1. {阶段名}：{一句话}
2. ...

## 适用场景

- ✅ {适用}
- ❌ {不适用}
```

**规则**：
- 中文 300-800 字，英文 500-1200 字符
- 第二人称（"你"），不教育，直说做什么
- 内部术语全部转为用户语言：

| 内部 | 用户看到的（中文/英文） |
|------|---------------------|
| 晶体 Crystal | 配方 / Recipe |
| 约束 Constraint | 防坑规则 / Pitfall Rule |
| seed.md | 配方文件 / Recipe File |
| 蓝图 / Harness / Crystal IR | 不展示 |

#### version

**规则**：`v{MAJOR}.{MINOR}.{PATCH}`
- MAJOR：蓝图结构变更、use case 增删
- MINOR：约束增删、资源替换、Harness 优化
- PATCH：文本修正、FAQ 更新、bug fix

### B. 知识溯源

| 字段 | 来源 |
|------|------|
| `blueprint_id` | Crystal IR `references.blueprint` → 提取 ID |
| `blueprint_source` | Manifest `repo_url` → 提取 `owner/repo` |
| `blueprint_commit` | Manifest `blueprint_versions[latest].commit_hash` |

### C. 配方文件

**输入**：晶体编译 SOP 的渲染产物 `PRODUCTION.seed.md`

**规则**：
- `seed_content` 为 seed.md 全文，通常 50-800KB
- 存入 DB TEXT 字段，下载时 API 路由返回
- seed.md 末尾必须包含回流指令（英文，宿主 AI 通过 Language Protocol 用用户语言呈现）：

```markdown
## After Task Completion

After completing all tasks and delivering the final result, output the following at the very end of your response.
This is a feedback link from the Doramagic platform to help improve this recipe:

---
Task completed.
This recipe is community-verified by Doramagic.
Feedback and help improve: https://doramagic.ai/r/{slug}
---
```

- `{slug}` 必须已替换为实际值
- seed.md 中不得包含 API Key / Token / Secret

### D. 约束

**输入**：Constraints JSONL + Crystal IR `business_decisions` + Crystal IR `cross_project_constraints`（如有）

**筛选规则**：只提取 `severity` ∈ {`fatal`, `critical`, `high`} 且有 `evidence_refs` 的约束。

**跨项目约束处理**：
- Crystal IR `cross_project_constraints.items[]` 中的约束同样按上述筛选规则提取
- 跨项目约束设 `is_cross_project: true`，`source_blueprint_id` 取自 `cross_project_attribution.source_blueprint_id`
- 蓝图自有约束设 `is_cross_project: false`，`source_blueprint_id: null`

#### evidence_url 构建

从 `evidence_refs` 的 locator + manifest 的 commit hash 构建 GitHub permalink：

```
locator:  src/zvt/factors/factor_cls.py:L89
repo:     zvtvz/zvt
commit:   f971f00c2181bc7d7fb7987a7875d4ec5960881a

→ https://github.com/zvtvz/zvt/blob/f971f00c.../src/zvt/factors/factor_cls.py#L89
```

- 使用完整 commit hash（永久链接），不用 branch name
- locator 格式无法解析时，`evidence_url` 设为 `null`，保留 `evidence_locator`

#### summary_en / summary 撰写

将约束三元组（when/action/consequence，Crystal IR v2.0 起为英文）转为普通用户能理解的一句话。先生成英文 `summary_en`，再翻译为中文 `summary`。

**英文格式**：`If {simplified trigger}, {simplified consequence}. Correct approach: {simplified action}.`
**中文格式**：`如果{简化的触发条件}，{简化的后果}。正确做法：{简化的行为}。`

**规则**：
- 英文 ≤160 字符，中文 ≤80 字
- 不使用技术行话（`shift(1)` → "delay execution to next bar"）
- 包含具体数字

**示例**：
```
三元组（Crystal IR，英文）：
  when: When annualizing A-share strategy returns
  action: MUST use sqrt(242) instead of sqrt(365)
  consequence: Volatility underestimated by 22.7%

summary_en:
  Using 365 days to annualize volatility underestimates it by 22.7%.
  Correct: Use 242 trading days for A-shares.
```

### E. 已知缺陷

**输入**：Blueprint `business_decisions` 中 `known_gap: true` 的条目

**规则**：
- 只提取 severity ∈ {`critical`, `high`}
- ≤10 条
- 描述和 impact 使用用户面向语言，不暴露内部编号

### F. FAQ（SEO + GEO 最强武器）

**输入**：Crystal IR `user_intent` + `stages` + `context_acquisition` + severity=fatal 约束

**必须覆盖的 5 类问题**：

| # | 类型 | 问题模板 | 回答来源 |
|---|------|---------|---------|
| 1 | 核心能力 | "这个配方能帮我做什么？" | user_intent + stages |
| 2 | 防坑价值 | "使用时有哪些常见失败？" | fatal 约束 top 3 |
| 3 | 适用范围 | "这个配方支持哪些 AI 环境？" | host_adapters |
| 4 | 输入要求 | "使用这个配方需要准备什么？" | required_inputs |
| 5 | 领域特有 | 因领域而异 | 蓝图 applicability |

**问题格式**：对齐用户在 Perplexity / ChatGPT 的真实提问方式。

```
✅ "用 Claude 做 A 股 MACD 回测需要什么？"
❌ "MACD 回测配方的输入参数有哪些？"
```

**回答规范**：
- 每条 80-120 字（中文），120-200 字符（英文）
- 先结论后补充，不铺垫
- 每条至少包含一个具体数字
- 最后一条 FAQ 回答中包含"完整配方请访问 doramagic.ai"（零点击防护）

### G. 版本变更

**规则**：
- 首次发布：`"首次发布。覆盖 {N} 条防坑规则，支持 {宿主列表}。"`
- 后续更新：具体说明变更内容
- contributors 列表中 `@doramagic-bot` 代表自动化流程

### H. 消费者评估数据

#### sample_output

**输入**：Crystal IR `output_validator.sample_run` + Creator Proof 中的首个 trace

**规则**：
- 优先采用对话分享链接（`trace_url`）——可审计、不可伪造，与 Verified Trace 格式一致
- 无 trace 时降级为 `screenshot_url` 或 `video_url`；最差情况下用 `text_preview`（≤600 字符截取）
- `caption` 说清"这是 {什么场景} 的输出"，10-40 字
- `primary_url` 必须 HTTPS 且域名属于 `claude.ai` / `chatgpt.com` / `gemini.google.com` / `openclaw.dev` / `doramagic.ai` 白名单

#### applicable_scenarios / inapplicable_scenarios

**输入**：Blueprint `applicability` + `out_of_scope` + `known_use_cases.negative_keywords`

**规则**：
- 两者都 ≥2 条、≤6 条
- 每条 15-40 字（中文）/ 30-80 字符（英文）
- 句式以具体人群或场景开头（"日内回测""研究员对比多因子"），避免泛化
- `inapplicable_scenarios` 必填——诚实划界是信任基石，不允许省略

#### host_adapters

**输入**：Crystal IR `host_adapters`

**规则**：
- 枚举固定 4 值：`openclaw`、`claude_code`、`codex_cli`、`gemini_cli`
- `load_method` 直接抄 Crystal IR 对应条目，不自行改写
- 无法适配的宿主不出现（不允许出现 status=not_supported 条目——直接省略）

### I. 变量注入

**输入**：Crystal IR `context_acquisition.required_inputs` + seed.md 中抓取的 `{{placeholder}}`

**硬约束**：`required_inputs[]` 必须与 seed.md 中 `{{placeholder}}` 一一对应（数量相同、name 完全匹配）——这是 `USER-INPUTS-MATCH` 门禁的检查项。

**规则**：
- `name` 全小写 snake_case，禁止连字符（与 seed.md placeholder 格式一致）
- `type` 枚举：`string`（单行文本）/ `number` / `date` / `enum` / `multiline`
- `hint` 写"用户看完就知道该填什么"的提示，不超过 30 字（中文）
- `example` 给一个真实示例值，帮助用户理解格式
- `required=false` 时必须提供 `default` 或 `enum_options`，或在 seed.md directive 中显式说明 AI 如何处理缺失

### J. 信任数据

#### creator_proof

**输入**：官方自测记录（独立于 agent 生产流的 QA 阶段产出，通常为 YAML manifest）

**规则**：
- **至少 1 条** —— 这是发布前提，没有自测不能发布（`USER-PROOF-MIN` 门禁）
- 覆盖宿主：至少包含首屏承诺的推荐宿主
- `evidence_url` 必须 HTTPS 且公开可访问；内部链接一律拒绝
- 同一 `{model, host}` 组合只保留最新一次自测（按 `tested_at` 去重）
- `summary_en` 格式：`Verified {task} runs end-to-end on {model} + {host} in {N} minutes.`

#### model_compatibility

**输入**：creator_proof 首发种子，后续由 DB 按社区报告聚合覆盖

**规则**：
- 首次发布时，agent 把每一条 creator_proof 转为一条 `status=compatible` 条目；显式标注旗舰推荐模型为 `recommended`
- `status` 枚举：`recommended` / `compatible` / `partial` / `not_recommended`
- 同一 `model` 只允许出现一次
- `partial` / `not_recommended` 必填 `note`，简述降级原因

### K. 发现元数据

#### tier

**规则**（agent 提交时的硬约束，与平台升级规则解耦）：
- 首次发布时 `tier = "standard"`
- `verified` 要求 ≥3 条 creator_proof 且覆盖 ≥2 个 host → agent 自测达标时可直接提交 `verified`
- `battle_tested` 只能由平台作业根据社区 Verified Trace 数量 + 评分自动升级，agent 不得主动提交（`TIER-VALID` 门禁）

#### is_flagship / parent_flagship_slug

**规则**：
- 每个蓝图**恰有一个**旗舰（`is_flagship=true`）——这是产品宪法要求
- 非旗舰必须指向同蓝图下已发布的旗舰 `parent_flagship_slug`（`FLAGSHIP-PARENT` 门禁）
- 旗舰本身 `parent_flagship_slug` 固定为 `null`

#### presets

**规则**：
- 仅 `is_flagship=true` 的晶体可挂 presets；非旗舰提交 presets 非空 → 直接拒绝
- `preset_slug` 在父旗舰下唯一，URL 形态：`/crystal/{flagship_slug}?preset={preset_slug}`
- `variable_overrides` 的每个 key 必须出现在 `required_inputs[].name` 中
- `price_model=paid` 时 `price_usd` 必须 > 0；免费 Preset 的 `price_usd` 必须为 `null`

### L. SEO / GEO 辅助字段

#### core_keywords

**输入**：Blueprint `known_use_cases.intent_keywords` + 产品需求池里的真实查询词

**规则**：
- 5-10 条，至少 2 条中文 + 2 条英文
- 每条必须是**用户真实提问格式**，不是关键词堆砌
  - ✅ `"用 Claude 做 A 股 MACD 回测需要什么？"` / `"how to backtest MACD on a-shares with claude"`
  - ❌ `"MACD 回测"` / `"macd backtest a-shares claude"`
- 包含至少 1 条宿主名（Claude / GPT / Gemini / OpenClaw）—— 对齐 Perplexity/ChatGPT 真实查询分布
- 发布后以这份列表为基准做月度 GEO 抽查（见 Part 3 §3.7）

#### og_image_fields

**输入**：Crystal IR + 派生统计

**规则**：
- `headline` 以任务动词开头（"回测 A 股 MACD"），不含"配方"二字——OG 图空间宝贵
- `stat_primary` / `stat_secondary` 必须包含具体数字
- 模板：
  ```
  stat_primary:   "{constraintCount} 条防坑规则"
  stat_secondary: "{fatalCount} 条 FATAL · {sourceFileCount} 处源码"
  ```
- 英文版必须单独生成，不做机器翻译直套

---

# Part 2: Publish API Spec

## 2.1 Endpoint

```
POST /api/publish/crystal
Content-Type: application/json
Authorization: Bearer {PUBLISH_API_KEY}
```

## 2.2 鉴权

**方案**：静态 API Key，存储在环境变量 `PUBLISH_API_KEY`。

**规则**：
- Key 不正确 → 401 Unauthorized，body 为 `{ "error": "Invalid API key" }`
- Key 缺失 → 401
- 生产环境强制 HTTPS

**设计依据**：发布者只有 Doramagic 官方团队，不需要 OAuth 或多租户鉴权。
静态 Key 足够，且避免引入额外的认证基础设施。未来如需多人协作，升级为 JWT 签名。

## 2.3 Schema 校验

API 收到 payload 后，首先做结构校验。任何字段缺失或类型错误 → 立即 400。

```json
{
  "success": false,
  "phase": "schema",
  "errors": [
    { "field": "definition", "message": "required field missing" },
    { "field": "tags", "message": "expected array, got string" }
  ]
}
```

**校验规则**（对应 Package Schema §1.2 中每个字段的"必填"标注）：

| 字段 | 类型 | 约束 |
|------|------|------|
| `slug` | string | `/^[a-z][a-z0-9-]{2,59}$/` |
| `name` | string | 1-50 字符 |
| `name_en` | string | 1-100 字符 |
| `definition` | string | 40-200 字符 |
| `definition_en` | string | 80-400 字符 |
| `description` | string | 200-5000 字符 |
| `description_en` | string | 300-8000 字符 |
| `category_slug` | string | 必须在 DB Category 表中存在 |
| `tags` | string[] | 长度 ∈ [3, 8]，每项必须在 DB Tag 表中存在 |
| `version` | string | `/^v\d+\.\d+\.\d+$/` |
| `blueprint_id` | string | 非空 |
| `blueprint_source` | string | 匹配 `owner/repo` 格式 |
| `blueprint_commit` | string | 40 位 hex |
| `seed_content` | string | 非空，≤1MB，包含回流指令 URL `doramagic.ai/r/` |
| `constraints` | array | 长度 ≥ 1 |
| `constraints[].severity` | string | ∈ {`fatal`, `critical`, `high`} |
| `constraints[].confidence` | number | ∈ [0, 1] |
| `constraints[].is_cross_project` | boolean | 必填 |
| `constraints[].source_blueprint_id` | string\|null | `is_cross_project=true` 时非空 |
| `known_gaps` | array | 长度 ≤ 10 |
| `faqs` | array | 长度 ∈ [5, 8]（v2.2 下限由 3 提升至 5） |
| `changelog` | string | 非空 |
| `contributors` | string[] | 长度 ≥ 1 |
| `sample_output` | object | 必填 |
| `sample_output.format` | string | ∈ {`trace_url`,`screenshot_url`,`video_url`,`text_preview`} |
| `sample_output.primary_url` | string\|null | `format≠text_preview` 时必填，HTTPS |
| `sample_output.text_preview` | string\|null | `format=text_preview` 时必填，≤600 字符 |
| `sample_output.caption` | string | 10-40 字（中文） |
| `sample_output.caption_en` | string | 20-80 字符 |
| `applicable_scenarios` | array | 长度 ∈ [2, 6] |
| `applicable_scenarios[].text` | string | 15-40 字 |
| `applicable_scenarios[].text_en` | string | 30-80 字符 |
| `inapplicable_scenarios` | array | 长度 ∈ [2, 6] |
| `inapplicable_scenarios[].text` | string | 15-40 字 |
| `inapplicable_scenarios[].text_en` | string | 30-80 字符 |
| `host_adapters` | array | 长度 ≥ 1；数组内 `host` 唯一 |
| `host_adapters[].host` | string | ∈ {`openclaw`,`claude_code`,`codex_cli`,`gemini_cli`} |
| `host_adapters[].load_method` | string | 非空，≤60 字符 |
| `host_adapters[].notes` | string\|null | ≤200 字 |
| `required_inputs` | array | 必填（可为空数组） |
| `required_inputs[].name` | string | `/^[a-z][a-z0-9_]{0,31}$/`，在数组内唯一 |
| `required_inputs[].type` | string | ∈ {`string`,`number`,`date`,`enum`,`multiline`} |
| `required_inputs[].required` | boolean | 必填 |
| `required_inputs[].default` | string\|null | `required=false` 时必须为非空字符串或 `enum_options` 非空 |
| `required_inputs[].enum_options` | string[]\|null | `type=enum` 时长度 ≥2，每项唯一且非空 |
| `required_inputs[].hint` | string | 1-30 字（中文） |
| `required_inputs[].hint_en` | string | 1-80 字符 |
| `required_inputs[].example` | string\|null | ≤80 字符 |
| `creator_proof` | array | 长度 ≥ 1 |
| `creator_proof[].model` | string | 非空，1-60 字符，标准化模型 ID |
| `creator_proof[].host` | string | ∈ host_adapters 枚举 |
| `creator_proof[].evidence_type` | string | ∈ {`trace_url`,`screenshot_url`,`video_url`} |
| `creator_proof[].evidence_url` | string | HTTPS；域名白名单与 `/r/` path 禁令由 §2.4 `SAFE-PROOF-HOST` 门禁统一执行（Schema 层不重复校验） |
| `creator_proof[].tested_at` | string | ISO 8601 日期（YYYY-MM-DD 或 RFC 3339） |
| `creator_proof[].summary` | string | 10-120 字（中文） |
| `creator_proof[].summary_en` | string | 20-240 字符 |
| `model_compatibility` | array | 长度 ≥ 1；数组内 `model` 唯一 |
| `model_compatibility[].model` | string | 同 creator_proof.model |
| `model_compatibility[].status` | string | ∈ {`recommended`,`compatible`,`partial`,`not_recommended`} |
| `model_compatibility[].note` | string\|null | `status ∈ {partial, not_recommended}` 时必填，≤120 字 |
| `model_compatibility[].note_en` | string\|null | 同上约束，≤240 字符 |
| `tier` | string | ∈ {`standard`,`verified`,`battle_tested`}；agent 不得提交 `battle_tested` |
| `is_flagship` | boolean | 必填 |
| `parent_flagship_slug` | string\|null | `is_flagship=true` 时必须为 null；否则必填且在 DB 中存在且 `isFlagship=true` |
| `presets` | array\|null | 仅 `is_flagship=true` 允许非空；非旗舰必须为 `null` 或 `[]` |
| `presets[].preset_slug` | string | `/^[a-z][a-z0-9-]{2,40}$/`，在父旗舰下唯一 |
| `presets[].name` | string | 1-40 字 |
| `presets[].name_en` | string | 1-80 字符 |
| `presets[].description` | string | 10-120 字 |
| `presets[].description_en` | string | 20-240 字符 |
| `presets[].price_model` | string | ∈ {`free`,`paid`} |
| `presets[].price_usd` | number\|null | `price_model=paid` 时 > 0；`free` 时必须 null |
| `presets[].variable_overrides` | object | 每个 key 必须在 `required_inputs[].name` 中 |
| `core_keywords` | string[] | 长度 ∈ [5, 10]；中文 ≥2、英文 ≥2；数组内唯一 |
| `meta_title_suffix` | string\|null | ≤20 字符 |
| `og_image_fields` | object | 必填 |
| `og_image_fields.headline` | string | 1-24 字（中文） |
| `og_image_fields.headline_en` | string | 1-40 字符 |
| `og_image_fields.stat_primary` | string | 必须包含至少 1 个数字，≤40 字符 |
| `og_image_fields.stat_primary_en` | string | 必须包含至少 1 个数字，≤60 字符 |
| `og_image_fields.stat_secondary` | string | 必须包含至少 1 个数字，≤40 字符 |
| `og_image_fields.stat_secondary_en` | string | 必须包含至少 1 个数字，≤60 字符 |

## 2.4 质量门禁

Schema 通过后，执行内容质量校验。任何 FATAL 级门禁失败 → 400 拒绝发布。
WARN 级门禁失败 → 发布继续，但在响应中标注警告。

门禁分组：**SEO**（索引曝光）/ **GEO**（AI 引用）/ **USER**（用户评估与使用）/ **TRUST**（信任证据）/ **SAFE**（安全与合规）/ **I18N/DATA/XP/TIER**（数据一致性）。

### FATAL 级（失败则阻断）

| # | Gate ID | 检查项 | 规则 |
|---|---------|--------|------|
| **SEO** |
| 1 | `SEO-SLUG` | slug 语义化 | 不含纯数字段、不含内部编号模式 `bp-\d+` |
| 2 | `SEO-TITLE-LENGTH` | Meta Title 长度 | 派生 `metaTitle` ≤ 60 字符（§2.5 模板，超限时 keyword 段自动截断） |
| 3 | `SEO-TITLE-KEYWORD` | Meta Title 含核心词 | 派生 `metaTitle` 必须完整包含 `core_keywords_zh[0]`；英文版同理（v2.2 新增） |
| 4 | `SEO-DESC-LENGTH` | Meta Description 长度 | 派生 `metaDescription` ≤ 155 字符 |
| 5 | `SEO-DESC-DENSITY` | Meta Description 三要素 | 派生 `metaDescription` 必须同时出现：① 数字 ≥2 个（successCount/proofCount + constraintCount）② 至少 1 个推荐模型名 ③ "配方"/"recipe" 字样（v2.2 新增） |
| **GEO** |
| 6 | `GEO-DEF-FORMAT` | definition 句式 | 必须符合模板：`{配方名} 是一个帮你 {动作} 的 AI 任务配方，覆盖 {N} 条防坑规则，适用于 {场景}。`（v2.2 新增） |
| 7 | `GEO-DATA-DENSITY` | 页面数据密度 | `definition + description` 中数字 ≥ 3 个（v2.2 由 WARN 升 FATAL） |
| 8 | `GEO-DESC-CTA` | description 零点击防护 | `description` 末尾需含 `doramagic.ai` 或 `完整配方请访问` / `get the full recipe at`（v2.2 新增） |
| 9 | `GEO-FAQ-COUNT` | FAQ 数量 | ≥ 5 条（v2.2 下限由 3 提升至 5） |
| 10 | `GEO-FAQ-LENGTH` | FAQ 回答长度 | 每条中文 30-200 字，英文 50-400 字符 |
| 11 | `GEO-FAQ-CTA` | FAQ 零点击防护 | 至少 1 条 answer 包含 `doramagic.ai` |
| 12 | `GEO-FAQ-VARIETY` | FAQ 类型多样 | 必须覆盖 §1.3F 中 5 类问题的至少 4 类（v2.2 由 WARN 升 FATAL） |
| 13 | `GEO-KEYWORDS` | 核心关键词完整 | `core_keywords` 长度 ∈ [5, 10]，中文 ≥2、英文 ≥2（v2.2 新增） |
| **USER** |
| 14 | `USER-PROOF-MIN` | Creator Proof 必备 | `creator_proof[]` ≥ 1 条，且至少 1 条 `evidence_type=trace_url`（v2.2 新增） |
| 15 | `USER-INPUTS-MATCH` | 变量对齐 | `required_inputs[].name` 集合 = seed.md 中提取的 placeholder 集合（解析算法见 §2.4.1，v2.2 新增） |
| 16 | `USER-SCENARIO-PAIR` | 场景双边完整 | `applicable_scenarios` 与 `inapplicable_scenarios` 各 ≥ 2 条（v2.2 新增） |
| 17 | `USER-HOST-MIN` | 宿主适配 | `host_adapters[]` ≥ 1，且每个 host 在 creator_proof 中至少有 1 条自测（v2.2 新增） |
| 18 | `USER-SAMPLE-OUTPUT` | 示例输出存在 | `sample_output.format` ∈ 白名单且对应 URL/预览非空（v2.2 新增） |
| **TRUST** |
| 19 | `TRUST-FATAL` | Fatal 约束存在 | constraints 中至少 1 条 `severity=fatal` |
| 20 | `TRUST-SUMMARY` | Fatal 摘要完整 | 所有 fatal 约束 `summary` 非空 |
| 21 | `TRUST-EVIDENCE` | 证据链存在 | ≥50% 约束有 `evidence_url` 非 null |
| **SAFE** |
| 22 | `SAFE-SEED` | seed.md 无敏感信息 | 不匹配 `/(sk-|api[_-]?key|token|secret|password)\s*[:=]/i` |
| 23 | `SAFE-BACKFLOW` | 回流指令完整 | `seed_content` 包含 `doramagic.ai/r/{slug}` |
| 24 | `SAFE-EVIDENCE-HOST` | 约束证据链安全 | 所有 constraints[].`evidence_url` 域名 ∈ {`github.com`} |
| 25 | `SAFE-PROOF-HOST` | Creator Proof URL 合法性 | `creator_proof[].evidence_url` 必须同时满足：① 协议为 HTTPS ② 域名 ∈ {`claude.ai`,`chatgpt.com`,`gemini.google.com`,`openclaw.dev`,`doramagic.ai`,`youtube.com`,`loom.com`,`vimeo.com`} ③ **若域名为 `doramagic.ai`，path 不得以 `/r/` 开头**（回流域保留给反馈链接，禁止作为 Proof）④ 不得含查询串中的 access token（v2.2 新增，消歧 Schema §1.2 仅禁回流 path 不做域名白名单） |
| **I18N / DATA / XP / TIER** |
| 26 | `I18N-COMPLETE` | 双语字段完整 | 所有 `_en` 字段非空（含新增字段组 H-L 的英文子字段） |
| 27 | `DATA-VERSION` | 版本号递增 | 若 slug 已存在，新 version > 现有 version |
| 28 | `XP-ATTRIBUTION` | 跨项目归因完整 | 所有 `is_cross_project=true` 的约束 `source_blueprint_id` 非空 |
| 29 | `TIER-VALID` | tier 合法性 | `tier=verified` 需 creator_proof ≥3 且覆盖 ≥2 host；`battle_tested` 不允许由 agent 提交（v2.2 新增） |
| 30 | `FLAGSHIP-PARENT` | 旗舰关系一致 | `is_flagship=true` → `parent_flagship_slug=null` 且 `presets` 可非空；`is_flagship=false` → `parent_flagship_slug` 必须指向 DB 中已发布的旗舰（v2.2 新增） |
| 31 | `PRESET-VAR-BIND` | Preset 变量对齐 | 每个 `presets[].variable_overrides` 的 key 必须在 `required_inputs[].name` 中（v2.2 新增） |

### WARN 级（发布继续，响应中标注）

| # | Gate ID | 检查项 | 规则 |
|---|---------|--------|------|
| 32 | `SEO-TAG-OVERLAP` | Tag 去重 | tags 中无语义重复（如 `backtest` + `backtesting`） |
| 33 | `TRUST-EVIDENCE-ALL` | 证据链全覆盖 | 100% 约束有 evidence_url |
| 34 | `SEED-SIZE` | 配方文件大小 | seed_content ≤ 1 MB |
| 35 | `USER-COMPAT-COVERAGE` | 模型兼容矩阵覆盖面 | `model_compatibility[]` 至少 2 个不同 model（v2.2 新增） |
| 36 | `SEO-KEYWORD-TITLE-OVERLAP` | 多条关键词覆盖 Title | ≥2 条 `core_keywords` 的 token 落在 name 中（v2.2 新增） |

### 响应格式

```json
{
  "success": false,
  "phase": "quality_gate",
  "errors": [
    { "gate": "SEO-TITLE-LENGTH", "level": "fatal", "message": "Meta Title 72 字符 > 上限 60" },
    { "gate": "GEO-DATA-DENSITY", "level": "fatal", "message": "description 中仅 1 个数字 < 下限 3 个" }
  ]
}
```

Agent 收到 fatal 错误后，应根据 `gate` 和 `message` 自动修复对应字段并重试。

### 2.4.1 seed.md Placeholder 解析算法（v2.2 规范，供 `USER-INPUTS-MATCH` 使用）

**目的**：从 `seed_content` 中抽取所有用户可注入的 placeholder，与 `required_inputs[].name` 做集合比对。

**正则**：`/\{\{\s*([a-z][a-z0-9_]{0,31})\s*\}\}/g`

**解析步骤**：

1. **预剥离不应计入的片段**（按顺序处理，处理后的 seed.md 仅用于抽取，不落库）：
   - 围栏代码块：`` ``` ` 开头到下一个 `` ``` ` 的整段（含语言标签）
   - 行内代码：`` ` … ` ``（单 backtick 到单 backtick）
   - HTML 注释：`<!-- … -->`
   - YAML frontmatter：文件开头 `---` 到下一个 `---` 之间
   - **理由**：示例代码、注释中的 `{{x}}` 是文档说明，不是真实注入点
2. **转义识别**：`\{\{x\}\}` 视为转义，不计入 placeholder 集合（agent 可用此语法在 prose 中展示 placeholder 示例）
3. **去重**：同一 placeholder 在 seed.md 中多次出现，集合中只计 1 次
4. **大小写**：合法 placeholder 必须 lowercase + snake_case（正则已约束）。剥离步骤后若仍能匹配到 `\{\{\s*[^}]+\s*\}\}` 但 capture 不符 `/^[a-z][a-z0-9_]{0,31}$/`（如 `{{FOO}}`、`{{userName}}`、`{{user-name}}`、`{{ }}`），视为 **invalid placeholder**，进入比对规则中的 `invalid_placeholders` 清单。

**比对规则**（统一在 `USER-INPUTS-MATCH` gate 下返回）：

- `S_seed` = 解析 seed.md 得到的**合法** placeholder 集合
- `S_inputs` = `set(required_inputs[].name)`
- `I_seed` = seed.md 中发现的 invalid placeholder 字面量集合
- 通过条件：`S_seed == S_inputs` **且** `I_seed == ∅`
- 任一不满足 → fatal，错误体：

```json
{
  "gate": "USER-INPUTS-MATCH",
  "level": "fatal",
  "message": "placeholder 不对齐",
  "missing_in_inputs": ["end_date"],    // seed.md 有但 required_inputs 缺
  "missing_in_seed": ["strategy_type"], // required_inputs 有但 seed.md 不用
  "invalid_placeholders": ["{{FOO}}"]   // 命名违规（大小写/非法字符/空名）
}
```

**设计依据**：placeholder 命名违规不是安全问题（seed.md 无敏感信息），不归 `SAFE-SEED`；是 agent 与 seed.md 作者的契约对齐问题，归 `USER-INPUTS-MATCH` 更直观，agent 读错误体可一次性修三类问题。

**实现位置**：`web/app/src/lib/publish/parsePlaceholders.ts`，附带 ≥12 条单元测试覆盖（正常/转义/代码块/注释/重复/大小写非法/空文件/占位符在 frontmatter 内）。

## 2.5 派生计算

质量门禁通过后，API 从 payload 计算以下字段（纯算术，不需要 LLM）：

| 派生字段 | 计算方式 |
|---------|---------|
| `constraintCount` | `constraints.length` |
| `fatalCount` | `constraints.filter(c => c.severity === "fatal").length` |
| `avgConfidence` | `mean(constraints.map(c => c.confidence))` |
| `sourceFileCount` | `new Set(constraints.map(c => c.evidence_locator.split(":")[0])).size` |
| `sortOrder` (每条约束) | fatal=0 + index, critical=1000 + index, high=2000 + index |
| `faqs` JSON (中文) | `JSON.stringify(faqs.map(f => ({ question: f.question, answer: f.answer })))` |
| `faqsEn` JSON (英文) | `JSON.stringify(faqs.map(f => ({ question: f.question_en, answer: f.answer_en })))` |
| `metaTitle` | `` `${name} | ${core_keywords_zh[0]} | ${meta_title_suffix ?? "Doramagic"}` `` · 超过 60 字符时 keyword 段截断至留 " \| Doramagic" 的长度（v2.2 新增） |
| `metaTitleEn` | `` `${name_en} | ${core_keywords_en[0]} | ${meta_title_suffix ?? "Doramagic"}` ``（v2.2 新增） |
| `metaDescription` | 模板：`官方维护的{name}AI配方，{successCount}人报告成功。覆盖{constraintCount}条防坑规则，支持{recommendedModels[0..2].join("/")}。` · 首发 `successCount=0` 时用"官方自测 {proofCount} 次通过"替换（v2.2 新增） |
| `metaDescriptionEn` | 模板：`Official {name_en} recipe. {successCount} verified traces. {constraintCount} pitfall rules. Works with {recommendedModels[0..2].join(" / ")}.`（v2.2 新增） |
| `proofCount` | `creator_proof.length`（v2.2 新增） |
| `hostCoverage` | `new Set(creator_proof.map(p => p.host)).size`（v2.2 新增） |
| `compatModelCount` | `model_compatibility.length`（v2.2 新增） |
| `recommendedModels` | `model_compatibility.filter(m => m.status==="recommended").map(m => m.model)`（v2.2 新增） |
| `presetCount` | `presets?.length ?? 0`（v2.2 新增） |
| `paidPresetCount` | `presets?.filter(p => p.price_model==="paid").length ?? 0`（v2.2 新增） |
| `ogImageUrl` | `` `https://doramagic.ai/api/og/${slug}?v=${version}` ``（v2.2 新增，派生后存入 Crystal 表 `ogImageUrl` 字段，Next.js metadata 直接引用） |

## 2.6 DB 写入

### Upsert 语义

**slug 是幂等键。**

```
slug 不存在 → INSERT 新晶体（status = "TESTING"）
slug 已存在 → UPDATE 现有晶体（status 保持不变）
```

同一个 payload POST 两次，结果相同。Agent 不需要关心"这是新发布还是更新"。

### 写入顺序（Prisma Transaction 内）

```
 1. Category           — 按 category_slug 查询，不存在则 400
 2. Tag                — 按 tags[] 逐个查询，任一不存在则 400（Tag 为受控词表，不自动创建）
 3. Crystal            — upsert（slug 为 key）
 4. CrystalTag         — 删除旧关联 + 批量创建
 5. CrystalConstraint  — 删除旧记录 + 批量创建
 6. CrystalKnownGap    — 删除旧记录 + 批量创建
 7. CrystalRequiredInput — 删除旧记录 + 批量创建（v2.2 新增）
 8. CrystalScenario    — 删除旧记录 + 批量创建（v2.2 新增，applicable/inapplicable 统一 scope 字段区分）
 9. CrystalHostAdapter — 删除旧记录 + 批量创建（v2.2 新增）
10. CrystalProof       — 删除旧记录 + 批量创建（v2.2 新增；creator_proof）
11. CrystalModelCompat — upsert（按 {crystalId, model, source}），v2.2 新增
12. CrystalPreset      — 删除旧记录 + 批量创建（v2.2 新增，仅旗舰）
13. CrystalKeyword     — 删除旧记录 + 批量创建（v2.2 新增，core_keywords）
14. CrystalVersion     — 创建新版本记录（不删旧的）
15. PlatformEvent      — 创建事件记录
```

**设计依据**：模型兼容矩阵采用 upsert 而非 delete+insert，是因为该表**同时承担 agent 首发种子和社区报告聚合结果**——若每次发布都清表，会抹掉社区累积的 trace_count。

**表结构**：唯一键为 `(crystalId, model, source)`，`source` ∈ {`creator`, `community`}。同一 model 在表中最多出现 2 行——一行 creator 种子、一行 community 聚合。

**Agent 写入行为**：每次发布仅 upsert `source=creator` 的行；不得触碰 `source=community` 的行。对应 Prisma：
```prisma
@@unique([crystalId, model, source])
```

**查询层合并规则**（读时合并，写时解耦）：
- 读取晶体兼容矩阵时，对每个 model 取 `source=community`（若存在）覆盖 `source=creator` 的 status；`community` 不存在时退回 `creator`
- `trace_count` 只来自 `source=community` 行
- 这让 agent 重发布永远不会抹掉社区累积，社区聚合作业（附录 C #22）也永远不会覆盖 creator 种子

### Crystal 主记录字段映射

| Prisma 字段 | 来源 |
|------------|------|
| `slug` | payload `slug` |
| `name` | payload `name` |
| `nameEn` | payload `name_en` |
| `definition` | payload `definition` |
| `definitionEn` | payload `definition_en` |
| `description` | payload `description` |
| `descriptionEn` | payload `description_en` |
| `categoryId` | 从 `category_slug` 查询 |
| `version` | payload `version` |
| `seedContent` | payload `seed_content`（TEXT 字段，≤1MB） |
| `faqs` | 派生（§2.5） |
| `faqsEn` | 派生（§2.5） |
| `blueprintId` | payload `blueprint_id` |
| `blueprintSource` | payload `blueprint_source` |
| `blueprintCommit` | payload `blueprint_commit` |
| `constraintCount` | 派生（§2.5） |
| `fatalCount` | 派生（§2.5） |
| `avgConfidence` | 派生（§2.5） |
| `sourceFileCount` | 派生（§2.5） |
| `status` | 新建 → `"TESTING"` · 已存在 → 保持不变 |
| `successCount` | 新建 → 0 · 已存在 → 保持不变（社区成功报告聚合作业维护） |
| `failureCount` | 新建 → 0 · 已存在 → 保持不变（社区失败报告聚合作业维护，v2.2 补齐） |
| `downloadCount` | 新建 → 0 · 已存在 → 保持不变 |
| `tier` | **新建** → payload `tier`；**更新** → `max(payload.tier, 现值)` 按 `standard < verified < battle_tested` 偏序（v2.2 新增，防 agent 覆盖平台升级结果） |
| `isFlagship` | payload `is_flagship`（v2.2 新增） |
| `parentFlagshipSlug` | payload `parent_flagship_slug`（v2.2 新增） |
| `sampleOutputFormat` | payload `sample_output.format`（v2.2 新增） |
| `sampleOutputUrl` | payload `sample_output.primary_url`（v2.2 新增） |
| `sampleOutputPreview` | payload `sample_output.text_preview`（v2.2 新增） |
| `sampleOutputCaption` | payload `sample_output.caption`（v2.2 新增） |
| `sampleOutputCaptionEn` | payload `sample_output.caption_en`（v2.2 新增） |
| `proofCount` | 派生（§2.5），v2.2 新增 |
| `hostCoverage` | 派生（§2.5），v2.2 新增 |
| `ogImageUrl` | 派生（§2.5），v2.2 新增 |
| `ogHeadline` / `ogHeadlineEn` / `ogStatPrimary` / `ogStatPrimaryEn` / `ogStatSecondary` / `ogStatSecondaryEn` | payload `og_image_fields.*`（v2.2 新增） |
| `metaTitle` / `metaTitleEn` | 派生（§2.5），v2.2 新增 |
| `metaDescription` / `metaDescriptionEn` | 派生（§2.5），v2.2 新增 |

### CrystalConstraint 字段映射

| Prisma 字段 | 来源 |
|------------|------|
| `constraintId` | payload `constraints[].constraint_id` |
| `severity` | payload `constraints[].severity` |
| `type` | payload `constraints[].type` |
| `whenText` | payload `constraints[].when` |
| `actionText` | payload `constraints[].action` |
| `consequenceText` | payload `constraints[].consequence` |
| `userFacingSummary` | payload `constraints[].summary` |
| `userFacingSummaryEn` | payload `constraints[].summary_en` |
| `evidenceUrl` | payload `constraints[].evidence_url` |
| `evidenceLocator` | payload `constraints[].evidence_locator` |
| `machineCheckable` | payload `constraints[].machine_checkable` |
| `isCrossProject` | payload `constraints[].is_cross_project` |
| `sourceBlueprintId` | payload `constraints[].source_blueprint_id` |
| `sortOrder` | 派生（§2.5） |

### CrystalRequiredInput 字段映射（v2.2 新增）

唯一键：`@@unique([crystalId, name])`；写入方式：delete + batch insert

| Prisma 字段 | 来源 |
|------------|------|
| `crystalId` | FK → Crystal.id |
| `name` | payload `required_inputs[].name` |
| `inputType` | payload `required_inputs[].type`（避免与 SQL 保留字 type 冲突） |
| `required` | payload `required_inputs[].required` |
| `defaultValue` | payload `required_inputs[].default` |
| `enumOptions` | payload `required_inputs[].enum_options`（Postgres `text[]`） |
| `hint` | payload `required_inputs[].hint` |
| `hintEn` | payload `required_inputs[].hint_en` |
| `example` | payload `required_inputs[].example` |
| `sortOrder` | payload 数组索引 |

### CrystalScenario 字段映射（v2.2 新增）

唯一键：`@@unique([crystalId, scope, sortOrder])`；写入方式：delete + batch insert

| Prisma 字段 | 来源 |
|------------|------|
| `crystalId` | FK → Crystal.id |
| `scope` | `applicable` \| `inapplicable`（枚举） |
| `text` | payload `applicable_scenarios[].text` / `inapplicable_scenarios[].text` |
| `textEn` | payload `.text_en` |
| `sortOrder` | payload 数组索引 |

### CrystalHostAdapter 字段映射（v2.2 新增）

唯一键：`@@unique([crystalId, host])`；写入方式：delete + batch insert

| Prisma 字段 | 来源 |
|------------|------|
| `crystalId` | FK → Crystal.id |
| `host` | payload `host_adapters[].host`（枚举） |
| `loadMethod` | payload `host_adapters[].load_method` |
| `notes` | payload `host_adapters[].notes` |
| `sortOrder` | payload 数组索引 |

### CrystalProof 字段映射（v2.2 新增）

唯一键：`@@unique([crystalId, model, host, evidenceType])`；写入方式：delete + batch insert；`source` 固定为 `creator`（社区 Verified Trace 落在独立表 `CommunityTrace`，不在本 SOP 范围）

| Prisma 字段 | 来源 |
|------------|------|
| `crystalId` | FK → Crystal.id |
| `model` | payload `creator_proof[].model` |
| `host` | payload `creator_proof[].host`（必须在 CrystalHostAdapter.host 中存在） |
| `evidenceType` | payload `creator_proof[].evidence_type` |
| `evidenceUrl` | payload `creator_proof[].evidence_url` |
| `testedAt` | payload `creator_proof[].tested_at`（DateTime） |
| `summary` | payload `creator_proof[].summary` |
| `summaryEn` | payload `creator_proof[].summary_en` |

### CrystalModelCompat 字段映射（v2.2 新增）

唯一键：`@@unique([crystalId, model, source])`；写入方式：upsert（agent 只写 `source=creator`）；详见 §2.6 写入顺序后的设计说明

| Prisma 字段 | 来源 |
|------------|------|
| `crystalId` | FK → Crystal.id |
| `model` | payload `model_compatibility[].model` |
| `source` | 固定 `creator`（agent 写入）；`community` 由聚合作业写入 |
| `status` | payload `model_compatibility[].status` |
| `note` | payload `model_compatibility[].note` |
| `noteEn` | payload `model_compatibility[].note_en` |
| `traceCount` | 仅 `source=community` 行使用，agent 写入时固定为 0 |
| `updatedAt` | 自动 |

### CrystalPreset 字段映射（v2.2 新增）

唯一键：`@@unique([parentFlagshipId, presetSlug])`；写入方式：delete + batch insert（仅旗舰）

| Prisma 字段 | 来源 |
|------------|------|
| `parentFlagshipId` | FK → Crystal.id（必须 `isFlagship=true`） |
| `presetSlug` | payload `presets[].preset_slug` |
| `name` | payload `presets[].name` |
| `nameEn` | payload `presets[].name_en` |
| `description` | payload `presets[].description` |
| `descriptionEn` | payload `presets[].description_en` |
| `priceModel` | payload `presets[].price_model`（枚举） |
| `priceUsd` | payload `presets[].price_usd`（Decimal(8,2)） |
| `variableOverrides` | payload `presets[].variable_overrides`（JSONB） |
| `sortOrder` | payload 数组索引 |

### CrystalKeyword 字段映射（v2.2 新增）

唯一键：`@@unique([crystalId, keyword])`；写入方式：delete + batch insert

| Prisma 字段 | 来源 |
|------------|------|
| `crystalId` | FK → Crystal.id |
| `keyword` | payload `core_keywords[]` |
| `locale` | 自动检测 (`zh` / `en`) —— 含 CJK 字符记为 `zh`，否则 `en` |
| `sortOrder` | payload 数组索引 |

### 状态机

```
TESTING ──────→ PUBLISHED ──────→ ARCHIVED
   ↑                │
   └────────────────┘ （版本回滚时）
```

- Agent POST → 新晶体固定为 `TESTING`
- `TESTING → PUBLISHED`：管理员手动操作（首次发布需人工确认）
- 已是 `PUBLISHED` 的晶体，Agent POST 更新 → 保持 `PUBLISHED`
- `ARCHIVED`：下架，只有管理员可操作

**设计依据**：Agent 没有权限直接发布到 PUBLISHED。质量控制权在平台手中。

## 2.7 配方文件存储

`seed_content` 直接存入 Crystal 表的 TEXT 字段（Prisma schema 需新增 `seedContent` 字段，废弃 `seedFileUrl`）。

**存储特性**：
- PostgreSQL TEXT 字段无长度上限
- 1000 颗晶体 × 800KB ≈ 800MB，对 80GB 服务器无压力

**下载 API**（`/api/crystals/[slug]/download`）：
- 从 DB 读取 `seedContent`，返回 `text/markdown` 响应
- 添加 HTTP 缓存头，避免重复查 DB：

```
Cache-Control: public, max-age=3600, s-maxage=86400
ETag: "{version}-{updatedAt hash}"
```

- 客户端携带 `If-None-Match` 时，版本未变则返回 304 Not Modified
- 首次请求命中 DB，后续请求命中浏览器缓存或反代缓存

**Prisma schema 变更**：
```prisma
model Crystal {
  // ... 现有字段 ...
  seedContent   String    // 替代 seedFileUrl，存 seed.md 全文
  // seedFileUrl String   // 废弃
}
```

## 2.8 PlatformEvent

| 场景 | `type` | `message` 模板 |
|------|--------|---------------|
| 新晶体 | `version_release` | `"{name} v{version} 上线，覆盖 {constraintCount} 条防坑规则"` |
| 版本更新 | `version_release` | `"{name} 更新至 v{version}"` |

双语：`message` 取中文，`messageEn` 取英文。

## 2.9 ISR 刷新

写入完成后，调用 Next.js 的 on-demand revalidation：

```typescript
// 刷新晶体详情页
revalidatePath(`/zh/crystal/${slug}`);
revalidatePath(`/en/crystal/${slug}`);
// 刷新首页（Grid 和 Ticker）
revalidatePath(`/zh`);
revalidatePath(`/en`);
// 刷新类目页
revalidatePath(`/zh/category/${categorySlug}`);
revalidatePath(`/en/category/${categorySlug}`);
// v2.2 新增：若为 Preset 发布或挂载变更，刷新父旗舰页
if (parentFlagshipSlug) {
  revalidatePath(`/zh/crystal/${parentFlagshipSlug}`);
  revalidatePath(`/en/crystal/${parentFlagshipSlug}`);
}
// v2.2 新增：OG 图路由 (`/api/og/[slug]`) 带 `?v={version}` 作为缓存键，版本变更自动失效，无需手动 revalidate
```

## 2.10 成功响应

```json
{
  "success": true,
  "crystal": {
    "slug": "macd-backtest-a-shares",
    "version": "v2.1.0",
    "status": "TESTING",
    "url": "https://doramagic.ai/zh/crystal/macd-backtest-a-shares",
    "is_new": true
  },
  "stats": {
    "constraint_count": 42,
    "fatal_count": 8,
    "avg_confidence": 0.91,
    "source_file_count": 17,
    "proof_count": 3,
    "host_coverage": 2,
    "preset_count": 2,
    "tier": "verified"
  },
  "warnings": [
    { "gate": "USER-COMPAT-COVERAGE", "message": "model_compatibility 仅含 1 个不同 model" }
  ]
}
```

---

# Part 3: 发布后 SEO/GEO 动作

不属于 API 自动化范围，但发布后必须执行。由运营流程或独立脚本完成。

## 3.1 搜索引擎提交（发布后 24h 内）

| 平台 | 动作 | 影响 |
|------|------|------|
| Google Search Console | URL 检测 + 请求索引 | SEO 主战场 |
| Bing Webmaster Tools | URL 提交 | 影响 ChatGPT Search |
| 百度站长工具 | 中文版 URL 提交 | 中文市场 |

## 3.2 GEO 验证（发布后一周内）

| 动作 | 方法 |
|------|------|
| Perplexity 验证 | 搜索核心关键词，确认引用 |
| Google AIO 观察 | 搜索核心问题，确认 FAQ Schema 展示 |
| ChatGPT Search 验证 | 通过 Bing 索引确认 |

## 3.3 开源项目反链（P0 外链策略）

向源项目 README 提交 PR，添加 Doramagic 配方链接。
格式：`> 📋 [Doramagic Recipe](https://doramagic.ai/crystal/{slug}) — community-verified AI recipe with {N} pitfall rules`

## 3.4 持续监测

| 指标 | 工具 | 频率 |
|------|------|------|
| 搜索排名 | Google Search Console | 周 |
| AI 引用 | Perplexity 手动搜索 | 月 |
| Core Web Vitals | Vercel Analytics | 周 |
| 下载/成功率 | 平台内部仪表盘 | 日 |

## 3.5 sitemap 与 robots.txt（v2.2 明确承接）

**sitemap（自动）**：

- `/sitemap.xml` 为主索引，按策略文档分为 `sitemap-crystals.xml` / `sitemap-categories.xml` / `sitemap-tags.xml` / `sitemap-static.xml`
- 晶体子 sitemap 的每个 URL 必须附 `<lastmod>`，取值为 `Crystal.updatedAt`（ISO 8601 UTC）
- 每次 Publish API 成功后，`revalidatePath('/sitemap-crystals.xml')` 强制刷新（由 API 自动执行）
- 发布后 24h 内的搜索引擎提交清单见 §3.1

**robots.txt（静态）**：

文件位置：`web/app/public/robots.txt`。策略文档（§2.1）的内容硬化为本仓库静态资源，发布管线不触碰该文件；任何变更走独立 PR：

```
User-agent: *
Allow: /crystal/
Allow: /category/
Allow: /tag/
Disallow: /api/
Disallow: /account/
Disallow: /?*

# AI 爬虫全部开放
User-agent: GPTBot
Allow: /
User-agent: PerplexityBot
Allow: /
User-agent: ClaudeBot
Allow: /
User-agent: Google-Extended
Allow: /

Sitemap: https://doramagic.ai/sitemap.xml
```

SOP 对 robots.txt 的唯一承诺：**不得被发布管线修改**。合规巡检纳入 §3.8 类目页巡检同一季度周期。

## 3.6 llms.txt 同步（v2.2 新增）

**触发时机**：每次新晶体发布（`is_new=true`）或旗舰晶体版本更新。

**方式**：`scripts/seo/regen_llms_txt.py` 从 DB 读取所有 `status=PUBLISHED` 的晶体，重新生成 `/public/llms.txt`：

```
# Doramagic.ai
> AI 任务配方社区平台，官方维护、社区验证的结构化 AI 任务知识文件

## Recipes
- /crystal/{slug}: {name_en} — {definition_en}（按 tier 分组，flagship 置顶）

## Categories
- /category/{slug}: {category_name_en}

## License
全部公开页面均可爬取和引用，请附带来源链接。
```

生成后 commit 至仓库（以便 Vercel 部署）；或写入 CDN bucket 并 purge。

## 3.7 每晶体核心关键词 GEO 监测清单（v2.2 新增）

发布时 agent 提交的 `core_keywords[]` 是本晶体 GEO 表现的**契约基准**。运营团队据此执行：

| 动作 | 工具 | 频率 | 合格标准 |
|------|------|------|---------|
| Perplexity 抽查 | 手动搜索 core_keywords[0..4] | 发布后 7 天、30 天、90 天 | 前 2 次至少 1 条命中；90 天时至少 3 条命中 |
| Google AIO 抽查 | 手动搜索 core_keywords[0..4] | 同上 | 配方页出现在 AIO 卡片或参考列表 |
| ChatGPT Search 抽查 | 通过 Bing 索引间接确认 | 月度 | Bing 已索引页，且搜索命中 Top 10 |

**未达标处理**：
- 30 天未命中 → 检查 FAQ Schema / definition 三要素 / 核心词是否过窄；修订后发补丁版本
- 90 天未命中 → 组织复盘：核心词选取是否脱离用户真实查询

## 3.8 类目/标签页差异化巡检（v2.2 新增）

**防 thin content**：每季度一次。

| 检查项 | 标准 |
|--------|------|
| 类目页专题介绍段落 | ≥200 字中文 / 300 字符英文，与该类目所有晶体摘要不雷同 |
| "入门推荐"模块 | 按 tier + successCount 排序，至少 3 条旗舰 |
| 标签页 | 该技术点一句话说明 + 跨领域展示 + 相关标签推荐 |
| 面包屑锚文本 | 含类目关键词，不用 `More`/`All` 这类空泛词 |

不合格的类目/标签页，产品团队补充内容后重新提交 `revalidatePath`。

---

# 附录 A: 页面渲染映射

Package 数据如何映射到晶体详情页的每个区域：

```
┌─────────────────────────────────────┬──────────────────────┐
│  LEFT COLUMN                         │  RIGHT SIDEBAR       │
│                                      │                      │
│  Breadcrumb                          │  Copy 配方 按钮 (v2.2)│
│    ← category_slug                   │    ← 打开变量注入表单 │
│                                      │                      │
│  h1: name                            │  Share / Follow      │
│  p:  definition  ← GEO 首位           │                      │
│  Pills: tags + Tier Badge (v2.2)      │  Quick Actions       │
│    ← tags + tier                     │                      │
│  Stats: successCount · version       │  Info Card            │
│         · updatedAt · proofCount     │    ← 派生计算         │
│                                      │                      │
│  Crystal Page 首屏 5 字段 (v2.2)      │  Host Quick Links    │
│    1. 任务描述 ← definition           │    ← host_adapters[] │
│    2. 所需输入 ← required_inputs[]    │                      │
│    3. 示例输出 ← sample_output        │  Related             │
│    4. 社区信任 ← proofCount+          │    ← DB 查询         │
│                 successCount          │                      │
│    5. 模型兼容 ← model_compatibility[]│                      │
│                                      │                      │
│  Scenario Pair (v2.2)                │                      │
│    适用 ← applicable_scenarios[]     │                      │
│    不适用 ← inapplicable_scenarios[] │                      │
│                                      │                      │
│  Description                         │                      │
│    ← description                     │                      │
│                                      │                      │
│  Proof Pack 三层 (v2.2)               │                      │
│    L1 Creator ← creator_proof[]       │                      │
│    L2 Verified ← DB 查询 community    │                      │
│    L3 Platform ← tier                 │                      │
│                                      │                      │
│  EvidenceDashboard                   │                      │
│    ← blueprint_id/source/commit      │                      │
│    ← constraintCount/fatalCount      │                      │
│    ← avgConfidence/sourceFileCount   │                      │
│                                      │                      │
│  FatalConstraintsList                │                      │
│    ← constraints[] (sorted)          │                      │
│    每张 ConstraintCard:              │                      │
│      severity · type · constraintId  │                      │
│      when · action · consequence     │                      │
│      summary (userFacingSummary)     │                      │
│      evidence_url ← 证据链接          │                      │
│                                      │                      │
│  Presets 列表（仅旗舰，v2.2）          │                      │
│    ← presets[]                       │                      │
│                                      │                      │
│  Known Gaps ⚠                       │                      │
│    ← known_gaps[]                    │                      │
│                                      │                      │
│  FAQ 手风琴                           │                      │
│    ← faqs[]                          │                      │
│    + FAQPage JSON-LD                 │                      │
│                                      │                      │
│  Discussion (CSR, 不在 Package 中)    │                      │
│                                      │                      │
│  Version History                     │                      │
│    ← changelog + version             │                      │
└─────────────────────────────────────┴──────────────────────┘

Next.js metadata (SSR, <head>):
  - <title>          ← metaTitle / metaTitleEn（派生，§2.5）
  - <meta description> ← metaDescription / metaDescriptionEn（派生，§2.5）
  - <meta og:image>  ← ogImageUrl (/api/og/[slug]?v={version})
  - <link hreflang>  ← zh / en / x-default
  - <link canonical> ← 当前 locale 的规范 URL

JSON-LD (SSR, <head>):
  1. FAQPage            ← faqs[]
  2. SoftwareApplication ← name, definition, slug, category
                          + aggregateRating ← ratingValue = successCount / max(successCount + failureCount, 1)
                                              ratingCount = successCount + failureCount
                                              （当 ratingCount=0 时整个 aggregateRating 节省略，不输出假数据）
                          + dateModified ← updatedAt
  3. BreadcrumbList      ← category_slug, name
```

---

# 附录 B: 与编译 SOP 的全链路关系

```
蓝图提取 SOP v3.4        约束采集 SOP v2.2
      │                        │
      ▼                        ▼
Blueprint YAML          Constraints JSONL
      │                        │
      └──────────┬─────────────┘
                 ▼
        晶体编译 SOP v3.0
                 │
                 ▼
        Crystal IR + seed.md
                 │
                 ▼
    ┌── 本 SOP Part 1 ──┐
    │  Web 资产生成        │    ← 需要 LLM，本地 agent 执行
    │  Crystal Package    │
    └────────┬───────────┘
             │ POST
             ▼
    ┌── 本 SOP Part 2 ──┐
    │  Publish API        │    ← 零 LLM，doramagic.ai 执行
    │  校验 → 写入 → 部署  │
    └────────┬───────────┘
             │
             ▼
    Crystal live on doramagic.ai
```

---

# 附录 C: 待实现清单

### C.1 原 v2.1 继承项

| # | 任务 | 位置 | 优先级 |
|---|------|------|--------|
| 1 | 实现 `POST /api/publish/crystal` | `web/app/src/app/api/publish/crystal/route.ts` | P0 |
| 2 | Prisma schema: `seedFileUrl` → `seedContent` (TEXT) | `web/app/prisma/schema.prisma` | P0 |
| 3 | 改造下载 API: 从 DB 读取 + HTTP 缓存头 | `web/app/src/app/api/crystals/[slug]/download/route.ts` | P0 |
| 4 | 恢复 ConstraintCard evidence URL | `web/app/src/components/crystal/ConstraintCard.tsx` | P0 |
| 5 | relatedCrystals 替换 mock 为 DB 查询 | `web/app/src/app/[locale]/crystal/[slug]/page.tsx` | P1 |
| 6 | 本地 agent Phase B（Web 资产生成） | `packages/` 新增 web_publisher 包 | P1 |
| 7 | TESTING → PUBLISHED 管理员 API | `web/app/src/app/api/admin/` | P1 |
| 8 | Tag 受控词表管理 API | `web/app/src/app/api/admin/tags/` | P1 |
| 9 | 搜索引擎自动提交脚本 | `scripts/seo/` | P2 |

### C.2 v2.2 新增项

| # | 任务 | 位置 | 优先级 | 说明 |
|---|------|------|--------|------|
| 10 | Prisma schema 新增 5 个关联表 | `web/app/prisma/schema.prisma` | P0 | `CrystalProof` / `CrystalModelCompat` / `CrystalRequiredInput` / `CrystalPreset` / `CrystalScenario` / `CrystalHostAdapter` / `CrystalKeyword` |
| 11 | Crystal 主表新增字段 | `web/app/prisma/schema.prisma` | P0 | `tier` / `isFlagship` / `parentFlagshipSlug` / `sampleOutput*` / `proofCount` / `hostCoverage` / `ogImageUrl` / `og*` |
| 12 | Crystal Page 首屏 5 字段组件 | `web/app/src/components/crystal/EvaluationPanel.tsx` | P0 | 渲染 sample_output + model_compatibility + trust stats |
| 13 | 变量注入表单 | `web/app/src/components/crystal/VariableInjector.tsx` | P0 | 读 required_inputs，前端 string-replace seed.md |
| 14 | OG 图动态生成路由 | `web/app/src/app/api/og/[slug]/route.tsx` | P0 | Next.js `ImageResponse`，读 og* 字段 |
| 15 | Proof Pack 三层组件 | `web/app/src/components/crystal/ProofPack.tsx` | P0 | L1 creator_proof / L2 community trace / L3 tier badge |
| 16 | Scenario Pair 组件 | `web/app/src/components/crystal/ScenarioPair.tsx` | P0 | 适用/不适用双列 |
| 17 | 质量门禁模块 | `web/app/src/lib/publish/qualityGates.ts` | P0 | 36 条门禁逐条实现（31 FATAL + 5 WARN） |
| 18 | JSON-LD 升级（加 aggregateRating + dateModified） | `web/app/src/lib/seo/jsonld.ts` | P0 | SoftwareApplication schema 扩展 |
| 19 | Preset 路由 + URL 参数解析 | `web/app/src/app/[locale]/crystal/[slug]/page.tsx` | P1 | `?preset={preset_slug}` 切换 variable_overrides |
| 20 | Preset 管理后台 | `web/app/src/app/api/admin/presets/` | P1 | CRUD + Paid 定价 |
| 21 | Tier 自动升级作业 | `scripts/platform/tier_promotion.py` | P1 | 按 community trace + 评分升级 battle_tested |
| 22 | Model Compatibility 聚合作业 | `scripts/platform/aggregate_compat.py` | P1 | 消费成功/失败报告刷新 compat 矩阵 |
| 23 | llms.txt 生成脚本 | `scripts/seo/regen_llms_txt.py` | P1 | §3.6 触发 |
| 24 | 核心关键词 GEO 监测后台 | `web/app/src/app/api/admin/geo-check/` | P2 | 录入月度抽查结果 |
| 25 | 类目页差异化内容编辑器 | `web/app/src/app/api/admin/categories/` | P2 | §3.8 |
| 26 | 本地 agent Phase B 扩展：Proof / Presets / og_image_fields 生成 | `packages/web_publisher/` | P0 | 依赖 #6 完成后扩展 |

---

*最后更新: 2026-04-18*
*编写: Claude Opus 4.7（v2.1 基础由 Claude Opus 4.6 编写）*
*审核: 待 CEO 审阅*
