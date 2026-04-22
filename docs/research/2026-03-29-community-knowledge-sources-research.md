# 知识积木社区来源调研报告
日期: 2026-03-29
执行者: Claude Code (browse 技能辅助)

---

## 一、调研背景

Doramagic 知识积木需要"社区半魂"——来自真实开发者的踩坑经验、最佳实践、失败模式。本报告系统评估 16 个社区的采集价值，为首期采集优先级提供决策依据。

评估维度：
- **知识密度**：每 100 条内容中高价值内容（失败经验/对比评测/解决方案）的比例
- **API 可用性**：是否有公开 API、限流策略、成本
- **知识新鲜度**：内容更新频率，是否反映最新技术
- **去噪难度**：垃圾内容比例，筛选难度
- **合规风险**：爬取/使用的法律风险

---

## 二、全球社区评估

### 2.1 GitHub Issues / Discussions

| 维度 | 评分 (1-5) | 说明 |
|------|-----------|------|
| 知识密度 | ⭐⭐⭐⭐⭐ | 每个高反应 issue 都是一个精准的失败模式 + 根因分析 + 解决方案三件套。pypa/setuptools #4519（387 reactions）展示了包生态系统级别的依赖链断裂原因，TypeScript #30471（268 reactions）精确描述了 auto-import 日常痛点 |
| API 可用性 | ⭐⭐⭐⭐⭐ | REST API：5000 req/h（认证），60 req/h（未认证）。Search API：30 req/min。GraphQL API 支持 Discussions 完整查询。完全免费，无付费墙 |
| 知识新鲜度 | ⭐⭐⭐⭐⭐ | 实时更新。Claude Code issues 在工具发布数小时内就出现（如 #40827 Windows scheduled tasks bug，#40828 model name validation）|
| 去噪难度 | ⭐⭐⭐⭐ | 低噪声。可通过 reactions>50、comments>10、label=bug/enhancement 过滤。重复 issue 是主要噪声，容易处理 |
| 合规风险 | ⭐⭐⭐⭐⭐ | 几乎无风险。GitHub ToS 明确允许 API 访问公开 repo 数据。开源 issue 属公开信息 |

**采集策略**：
- 目标：reactions >= 20 的 closed bug issues + 高评论数 Discussions
- 重点 repo：anthropics/claude-code、vitejs/vite、langchain-ai/langchain、microsoft/vscode、vercel/next.js、facebook/react 等
- 过滤逻辑：`label:bug reactions:>20 is:closed` 或 `label:question comments:>5`
- API 端点：`GET /repos/{owner}/{repo}/issues` + GraphQL Discussions API

**整体评价**：**S 级**，知识密度最高、API 最友好、风险最低，必须首批采集。

---

### 2.2 Stack Overflow

| 维度 | 评分 (1-5) | 说明 |
|------|-----------|------|
| 知识密度 | ⭐⭐⭐⭐⭐ | 高票答案是经过社区验证的最佳实践。问答格式天然是"问题-解法"对，知识结构最完整 |
| API 可用性 | ⭐⭐⭐⭐ | Stack Exchange API v2.3，免费 10,000 requests/day（无 key），300 requests/day（无 key，较低）。有 key 可大幅提升。注意：stackexchange.com 网站本身屏蔽直接 fetch，需用 API |
| 知识新鲜度 | ⭐⭐⭐ | 核心技术话题更新慢，AI/LLM 相关内容增长快，但整体新鲜度中等。2020 年前的答案可能已过时 |
| 去噪难度 | ⭐⭐⭐⭐ | 低噪声。votes >= 10 + accepted answer 基本保证质量。重复问题已被系统合并 |
| 合规风险 | ⭐⭐⭐ | CC BY-SA 4.0 授权，可用但需要署名。商业用途有争议，需核查具体条款。不能直接嵌入作为自己的内容 |

**采集策略**：
- 目标：score >= 10、tagged with llm/claude/python/typescript/react 等关键词的问答对
- API 端点：`https://api.stackexchange.com/2.3/questions?tagged={tags}&sort=votes&site=stackoverflow`
- 重点筛选：accepted=true + score >= 20，降低噪声

**整体评价**：**A 级**，结构最规整，但授权有争议，新鲜度中等。

---

### 2.3 Hacker News

| 维度 | 评分 (1-5) | 说明 |
|------|-----------|------|
| 知识密度 | ⭐⭐⭐⭐ | "Things I wish I knew about MongoDB/React/ML"类文章密度极高（100-316 分）。技术迁移故事（BigQuery→ClickHouse、MongoDB→PostgreSQL）包含高质量决策逻辑。不过主要是链接聚合，真正的知识在评论区和链出文章里 |
| API 可用性 | ⭐⭐⭐⭐⭐ | 官方 Firebase API 无限流、完全免费。Algolia 搜索 API（hn.algolia.com）支持关键词搜索、标签过滤、时间范围，也免费。是所有社区里 API 最宽松的 |
| 知识新鲜度 | ⭐⭐⭐⭐⭐ | 实时追踪最新技术趋势。Claude Code、AI coding tools 在几小时内出现热讨 |
| 去噪难度 | ⭐⭐⭐ | 中等。需要 points >= 100 过滤掉低质量内容。评论区噪声较高，哲学/社会讨论混杂 |
| 合规风险 | ⭐⭐⭐⭐⭐ | Y Combinator 官方提供的公开 API，无合规风险 |

**采集策略**：
- 目标：score >= 100 的 story + 评论数 >= 50
- 用 Algolia API 搜索：`query=things+I+wish+I+knew OR postmortem OR pitfall OR lessons+learned`
- 重点类型：技术决策故事、迁移报告、失败案例、"我做错了什么"系列
- API：`https://hn.algolia.com/api/v1/search?query=...&tags=story&numericFilters=points>100`

**整体评价**：**A 级**，API 最宽松，趋势追踪能力强，但知识多在链出文章里，需二次爬取。

---

### 2.4 Reddit

| 维度 | 评分 (1-5) | 说明 |
|------|-----------|------|
| 知识密度 | ⭐⭐⭐ | 用户体验类知识密度高（r/ClaudeAI、r/webdev），但干货比例不稳定 |
| API 可用性 | ⭐ | **严重受限**。2023 年 6 月 API 付费化后，第三方数据访问基本被关闭。Pushshift 已要求仅限 Reddit 版主使用，且禁止商业用途。官方 API：免费版仅 100 req/min，商业级定价未透明公布 |
| 知识新鲜度 | ⭐⭐⭐⭐ | 内容更新快，AI 工具讨论非常活跃 |
| 去噪难度 | ⭐⭐ | 高噪声。表情包、抱怨帖、广告帖混杂，需要精细过滤 |
| 合规风险 | ⭐ | **高风险**。2023 年后 Reddit 明确禁止未授权的批量数据采集。ToS 明确禁止用 Reddit 数据训练 AI 模型 |

**整体评价**：**D 级**，法律风险高，API 封闭，不建议作为主要采集源。如需采集，仅限通过官方 API 小规模采集公开帖子，且不做 AI 训练用途。

---

### 2.5 Dev.to / Hashnode

| 维度 | 评分 (1-5) | 说明 |
|------|-----------|------|
| 知识密度 | ⭐⭐⭐ | 质量参差。Dev.to 有高价值文章（如"Claude Code reset my git"、"AI工具让开发者技能退化"），但也有大量入门/推广内容。Hashnode 社区小但更垂直 |
| API 可用性 | ⭐⭐⭐⭐ | Dev.to（Forem）有公开 REST API，无认证可访问，有 rate limit 但未公布具体数字。Hashnode 有 GraphQL API |
| 知识新鲜度 | ⭐⭐⭐⭐ | 更新频率高，AI 相关内容增长快 |
| 去噪难度 | ⭐⭐ | 高噪声。SEO 水文较多，需通过 reactions/comments 过滤 |
| 合规风险 | ⭐⭐⭐⭐ | CC BY 或作者版权，无明确禁止性条款，风险较低 |

**采集策略**：
- Dev.to API：`GET https://dev.to/api/articles?tag=ai&top=30`
- 过滤：reactions_count >= 50 + public_reactions_count >= 20
- 目标标签：ai、llm、claude、typescript、python、devtools

**整体评价**：**B 级**，API 友好但噪声较高，适合作为补充源。

---

### 2.6 npm / PyPI changelogs + package metadata

| 维度 | 评分 (1-5) | 说明 |
|------|-----------|------|
| 知识密度 | ⭐⭐⭐ | CHANGELOG 是版本迁移知识的精华，但需要配合 GitHub 上的 issue 才能理解"为什么"。PyPI API 提供依赖关系、版本历史，但无 changelog 字段 |
| API 可用性 | ⭐⭐⭐⭐⭐ | npm registry API 和 PyPI JSON API 均完全免费、无认证、无限流（合理使用下）。`https://pypi.org/pypi/{package}/json` |
| 知识新鲜度 | ⭐⭐⭐⭐⭐ | 实时反映最新版本 |
| 去噪难度 | ⭐⭐⭐⭐ | 结构化数据，噪声低，但 changelog 内容质量参差 |
| 合规风险 | ⭐⭐⭐⭐⭐ | 完全公开数据，无合规风险 |

**整体评价**：**B 级**，适合作为依赖图谱和版本迁移知识的补充源，不是主力。

---

### 2.7 Product Hunt

| 维度 | 评分 (1-5) | 说明 |
|------|-----------|------|
| 知识密度 | ⭐⭐ | 偏产品评测，技术深度低。适合了解工具全貌和用户体验，不适合提取技术踩坑知识 |
| API 可用性 | ⭐⭐⭐ | GraphQL API（https://api.producthunt.com/v2/api/graphql），需 OAuth2，无明确限流数字，按"公平使用"执行 |
| 知识新鲜度 | ⭐⭐⭐⭐ | 实时追踪新产品发布 |
| 去噪难度 | ⭐⭐ | 高噪声，大量营销评论 |
| 合规风险 | ⭐⭐⭐ | ToS 无明确禁止条款，但需申请 API 访问 |

**整体评价**：**C 级**，对知识积木价值有限，不列入首批。

---

## 三、中文社区评估

### 3.1 V2EX

| 维度 | 评分 (1-5) | 说明 |
|------|-----------|------|
| 知识密度 | ⭐⭐⭐⭐ | 技术节点（如 /go/ai、/go/python）有大量真实开发者经验分享。发现案例：Java 在 GitHub trending 消失的趋势观察、ChatGPT 订阅坑、AI 服务对比等。社区有明确禁止 AI 生成内容的规范，保证了讨论真实性 |
| API 可用性 | ⭐⭐⭐⭐ | REST API 2.0 Beta，Personal Access Token 认证，600 req/h per IP。支持 Topics、Nodes、Members 端点。免费 |
| 知识新鲜度 | ⭐⭐⭐⭐ | 更新频繁，AI 工具讨论活跃 |
| 去噪难度 | ⭐⭐⭐ | 中等。需按 node 过滤（技术节点噪声低，水区噪声高）|
| 合规风险 | ⭐⭐⭐ | 无明确公开 ToS，使用 API 合规，大规模爬取有风险 |

**采集策略**：
- 目标节点：/go/ai、/go/python、/go/javascript、/go/programming、/go/dev
- API：`GET https://www.v2ex.com/api/v2/nodes/{node}/topics`
- 过滤：replies >= 10 的话题

**整体评价**：**A 级（中文圈首选）**，真实度高，API 友好，中文开发者踩坑经验的最佳来源。

---

### 3.2 掘金（Juejin）

| 维度 | 评分 (1-5) | 说明 |
|------|-----------|------|
| 知识密度 | ⭐⭐⭐ | 有优质技术文章，但也充斥大量低质内容（SEO 文、翻译文、凑字数文）。有前端/后端/AI/工具等完整分类 |
| API 可用性 | ⭐⭐⭐ | 非官方公开但实际可用的 API（通过 web 请求发现）：`/content_api/v1/article/detail`、`/recommend_api/v1/article/recommend_cate_feed`。无官方 API 文档，存在被封风险 |
| 知识新鲜度 | ⭐⭐⭐⭐ | 更新频繁，AI 工具相关内容增长快 |
| 去噪难度 | ⭐⭐ | 高噪声。需要 digg_count（点赞）>= 100 才能基本保证质量 |
| 合规风险 | ⭐⭐ | 内容版权归作者，平台对爬取无明确授权，存在一定法律风险 |

**整体评价**：**B 级**，内容量大，但质量参差，去噪成本高。

---

### 3.3 知乎

| 维度 | 评分 (1-5) | 说明 |
|------|-----------|------|
| 知识密度 | ⭐⭐⭐⭐ | 技术话题下的高赞答案质量很高（类似中文 Quora）。开发者写的踩坑经验、工具对比、架构选择类内容密度高 |
| API 可用性 | ⭐ | **严重受限**。知乎开放平台（open.zhihu.com）已于 2023 年底基本停止对外开放新 API 申请。现有 API 需要商业合作申请，普通开发者无法获取。直接爬取面临强反爬 |
| 知识新鲜度 | ⭐⭐⭐ | 核心内容更新慢 |
| 去噪难度 | ⭐⭐⭐ | 中等，水答案较多但投票机制有效过滤 |
| 合规风险 | ⭐ | **高风险**。知乎明确禁止未授权爬取，且有强力法律手段 |

**整体评价**：**D 级**，API 关闭，合规风险高，暂不采集。

---

### 3.4 即刻

| 维度 | 评分 (1-5) | 说明 |
|------|-----------|------|
| 知识密度 | ⭐⭐ | 偏轻量讨论，微博类，适合追踪 AI 工具使用情绪，但技术深度不足 |
| API 可用性 | ⭐ | 无公开 API |
| 知识新鲜度 | ⭐⭐⭐⭐ | 更新极快 |
| 去噪难度 | ⭐ | 极高噪声 |
| 合规风险 | ⭐⭐ | 无授权访问渠道 |

**整体评价**：**D 级**，不适合作为知识积木来源。

---

### 3.5 CSDN

| 维度 | 评分 (1-5) | 说明 |
|------|-----------|------|
| 知识密度 | ⭐⭐ | 大量低质翻译文、凑字数文、付费墙内容。优质内容被淹没 |
| API 可用性 | ⭐ | 无公开 API |
| 合规风险 | ⭐⭐ | 强反爬，内容版权敏感 |

**整体评价**：**E 级**，不建议采集。

---

## 四、AI 专属社区评估

### 4.1 Discourse 类论坛（Cursor Forum、Python Discourse 等）

| 维度 | 评分 (1-5) | 说明 |
|------|-----------|------|
| 知识密度 | ⭐⭐⭐⭐⭐ | Cursor Forum 揭示了"IDE 静默 git reset 导致数据丢失"这类严重 bug，以及每次会话高达 $600 的成本超支问题。Python Discourse 有 PEP 级别的语言决策讨论。知识价值极高 |
| API 可用性 | ⭐⭐⭐⭐⭐ | Discourse 标准 JSON API，无认证即可访问（公开论坛）：`https://forum.cursor.com/latest.json`、`https://discuss.python.org/latest.json`。支持分页、分类过滤 |
| 知识新鲜度 | ⭐⭐⭐⭐⭐ | 实时更新，往往比 GitHub issues 更早出现用户真实体验 |
| 去噪难度 | ⭐⭐⭐⭐ | 低噪声，Discourse 有良好分类系统，bug/feature request 区分明确 |
| 合规风险 | ⭐⭐⭐⭐ | 公开社区，标准 API 访问，风险低 |

**重点 Discourse 论坛**：
- `forum.cursor.com` — AI IDE 用户真实踩坑
- `discuss.python.org` — Python 生态决策
- `forum.djangoproject.com` — Django 开发者经验
- `community.openai.com` — OpenAI API 开发者（每月 15,000+ 活跃用户，800+ 话题）

**整体评价**：**S 级（隐藏宝矿）**，API 开放、知识密度极高、合规低风险。

---

### 4.2 Claude Code GitHub Issues

| 维度 | 评分 (1-5) | 说明 |
|------|-----------|------|
| 知识密度 | ⭐⭐⭐⭐⭐ | 直接是 Claude Code 用户的第一手踩坑经验。发现案例：Windows scheduled tasks 不执行（#40827）、model name 无验证（#40828）、light theme 不可读（#40825）等。每个 issue 都是潜在的知识积木 |
| API 可用性 | ⭐⭐⭐⭐⭐ | GitHub REST API，同上。repo=anthropics/claude-code |
| 知识新鲜度 | ⭐⭐⭐⭐⭐ | 实时 |
| 去噪难度 | ⭐⭐⭐⭐ | 低噪声，用户报告具体场景 |
| 合规风险 | ⭐⭐⭐⭐⭐ | 无风险 |

**整体评价**：**S 级**，Doramagic 的核心采集目标，直接相关。

---

### 4.3 OpenAI Community Forum

| 维度 | 评分 (1-5) | 说明 |
|------|-----------|------|
| 知识密度 | ⭐⭐⭐⭐ | 11,642 每月新注册，15,398 活跃用户，7,229 帖子/月。开发者分享 API 使用经验、cost 控制、prompt 工程 |
| API 可用性 | ⭐⭐⭐⭐ | Discourse 架构，标准 JSON API 可访问 |
| 知识新鲜度 | ⭐⭐⭐⭐⭐ | 更新极快 |
| 合规风险 | ⭐⭐⭐ | 公开内容，但 OpenAI 可能对使用有限制 |

**整体评价**：**A 级**

---

## 五、综合评分汇总

| # | 社区 | 知识密度 | API 可用性 | 新鲜度 | 去噪难度 | 合规风险 | **综合评级** |
|---|------|---------|-----------|--------|---------|---------|------------|
| 1 | GitHub Issues/Discussions | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | **S** |
| 2 | Discourse 论坛类（Cursor/Python/OpenAI） | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | **S** |
| 3 | Hacker News | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | **A** |
| 4 | Stack Overflow | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | **A** |
| 5 | V2EX（中文首选） | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | **A** |
| 6 | Dev.to | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | **B** |
| 7 | 掘金 | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | **B** |
| 8 | npm/PyPI metadata | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | **B** |
| 9 | Product Hunt | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | **C** |
| 10 | Reddit | ⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐ | **D** |
| 11 | 知乎 | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐ | **D** |
| 12 | 即刻 | ⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐ | **D** |
| 13 | CSDN | ⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐ | **E** |

---

## 六、首期采集清单（Top 5 推荐）

### 第 1 名：GitHub Issues + Discussions（综合最优）

**为什么第一**：API 最成熟（5000 req/h）、知识密度最高（反应数 = 社区验证的重要性）、覆盖全球最活跃的开发者社区、零合规风险。

**具体采集策略**：
```python
# 采集目标：AI/LLM/前端/后端重点 repo 的高反应 bug issues
repos = [
    "anthropics/claude-code",    # 直接相关
    "langchain-ai/langchain",    # LLM 框架
    "vitejs/vite",               # 现代前端构建
    "vercel/next.js",            # 全栈框架
    "microsoft/vscode",          # 开发工具
    "openai/openai-python",      # AI SDK
    "huggingface/transformers",  # ML 框架
]

# 过滤条件
filters = {
    "state": "closed",
    "label": ["bug", "question"],
    "reactions_min": 20,
    "comments_min": 5,
}

# API 端点
# GET /repos/{owner}/{repo}/issues?state=closed&labels=bug&per_page=100
# 按 reactions 排序
```

**去噪方法**：
- reactions >= 20：过滤掉 95% 的低价值 issue
- 检查 body 长度 > 200 字符：过滤掉空 issue
- 过滤 PR（只保留 issue）
- Discussions：answer_count > 0 表示已解决，优先采集

---

### 第 2 名：Discourse 论坛类（隐藏 S 级宝矿）

**为什么第二**：比 GitHub issues 更贴近用户真实体验（不只是 bug，还有工作流、成本、集成问题）。Cursor Forum 里"Claude Code 重置了我的 git"这类事故报告在 GitHub issues 里找不到。

**具体采集策略**：
```python
# Discourse JSON API（无需认证）
forums = [
    "https://forum.cursor.com",              # AI IDE 用户
    "https://community.openai.com",          # OpenAI API 开发者
    "https://discuss.python.org",            # Python 生态
    "https://forum.djangoproject.com",       # Django
    "https://community.anthropic.com",       # Anthropic（如果开放）
]

# API 端点
# GET https://forum.cursor.com/latest.json?category=bug
# GET https://forum.cursor.com/c/bug/6.json?page=0

# 过滤条件
filters = {
    "posts_count_min": 5,   # 至少 5 条回复
    "views_min": 100,       # 至少 100 次查看
    "category": ["bug", "help", "discussion"],
}
```

---

### 第 3 名：Hacker News（趋势捕获 + 决策故事）

**为什么第三**：最擅长捕捉技术趋势和高密度经验故事（MongoDB 踩坑、迁移决策等）。"Things I wish I knew"类文章 100-316 分，是最浓缩的经验知识。

**具体采集策略**：
```python
# Algolia HN API（免费无限流）
base_url = "https://hn.algolia.com/api/v1/search"

# 搜索模式 1：经验故事
params1 = {
    "query": "things I wish I knew OR lessons learned OR we switched from OR postmortem OR pitfall",
    "tags": "story",
    "numericFilters": "points>100,num_comments>30",
    "hitsPerPage": 50,
}

# 搜索模式 2：AI 工具讨论
params2 = {
    "query": "claude code OR cursor OR AI coding tool",
    "tags": "story",
    "numericFilters": "points>50",
}

# 二次采集：对高分 story，爬取评论（contains actual knowledge）
# GET https://hacker-news.firebaseio.com/v0/item/{id}.json
```

---

### 第 4 名：Stack Overflow（结构化问答）

**为什么第四**：问题-解法对是最完整的知识结构。votes >= 20 的答案基本等于经过社区验证的最佳实践。

**具体采集策略**：
```python
# Stack Exchange API（免费，需申请 API Key 提高限额）
base_url = "https://api.stackexchange.com/2.3/questions"

params = {
    "tagged": "llm;claude;langchain;python;typescript",
    "sort": "votes",
    "order": "desc",
    "filter": "withbody",  # 包含题目和答案正文
    "site": "stackoverflow",
    "min": 10,  # 最低 score
}

# 目标标签组合（分批查询）
tag_groups = [
    "llm", "claude", "langchain", "openai-api",
    "python+asyncio", "typescript+react", "docker+kubernetes",
]
```

**注意**：CC BY-SA 授权，需要在使用时标注来源，不能直接宣称是"自己"的内容。

---

### 第 5 名：V2EX（中文开发者首选）

**为什么第五**：中文开发者社区中唯一 API 友好 + 内容真实 + 合规风险低的组合。V2EX 明确禁止 AI 生成内容，保证了讨论的真实度。600 req/h 足够日常采集。

**具体采集策略**：
```python
# V2EX API v2（需申请 Personal Access Token）
base_url = "https://www.v2ex.com/api/v2"

# 目标节点（技术相关）
nodes = [
    "ai", "python", "javascript", "typescript",
    "programming", "dev", "cloud", "security",
]

# 采集逻辑
# GET /api/v2/nodes/{node}/topics
# 过滤：replies >= 10
```

---

## 七、采集优先级时间线

### Phase 1（立即执行，0-2 周）
- **GitHub Issues**：anthropics/claude-code + langchain-ai/langchain + vitejs/vite
- **Discourse**：forum.cursor.com（最直接的 AI IDE 踩坑）
- **HN Algolia**：搜索经验故事关键词

### Phase 2（2-4 周）
- **Stack Overflow**：申请 API Key，采集 LLM/Claude/TypeScript 标签
- **V2EX**：申请 Personal Access Token，采集技术节点
- **更多 Discourse 论坛**：community.openai.com、discuss.python.org

### Phase 3（1-2 月）
- **Dev.to**：建立去噪 pipeline（reactions >= 50）
- **掘金**：评估非官方 API 稳定性后决定是否纳入
- **npm/PyPI**：采集主流包的 changelog + 版本历史

### 暂不采集（风险 > 收益）
- Reddit：API 封闭 + 合规风险高
- 知乎：API 关闭 + 爬取法律风险
- CSDN：内容质量低 + 无 API
- 即刻：技术深度不足

---

## 八、关键发现与建议

1. **Discourse 论坛是被严重低估的来源**。所有 Discourse 论坛都暴露标准 JSON API（无需认证），Cursor Forum 的 bug 报告比 GitHub issues 更贴近用户真实工作流痛点。

2. **"知识密度"和"API 可用性"是最重要的两个维度**。Reddit 知识密度还行，但 API 封闭；知乎知识密度高，但 API 关闭。实际可落地的只有 API 友好的社区。

3. **中文社区应该集中在 V2EX**。知乎 API 关闭、掘金无官方 API、CSDN 质量差，V2EX 是唯一三个维度（真实度、API、风险）都达标的中文技术社区。

4. **HN 的价值在二次采集**。HN 本身是聚合器，真正的知识在链出文章里。采集策略应该是：HN 高分 story → 访问原文 → 提取知识。

5. **Stack Overflow 授权问题需要法务确认**。CC BY-SA 4.0 授权允许使用，但要求署名和相同授权传播，商业知识库使用可能存在争议，建议在正式采集前确认。

---

*报告结束。下一步：设计采集 pipeline 架构，从 Phase 1 开始验证采集质量。*
