# Mac Mini 技术方案 — CTO 向 CEO 汇报

> 本文档完整描述 Mac Mini 作为 Doramagic 知识工厂需要做的所有事情。
> 目标读者：非技术背景的 CEO。所有技术概念会用类比解释。

---

## 一、Mac Mini 在整个系统中的角色

Mac Mini 是 Doramagic 的**印刷厂**。它负责：

1. **采集原材料**——从 GitHub、Reddit、Discord、雪球、博客等来源拉取数据
2. **加工成产品**——把原始数据提炼成一颗颗判断（Judgment）
3. **质检入库**——去重、解冲突、建立关联，存入知识库
4. **发货到门店**——把知识库同步到线上服务器，供用户消费

Mac Mini 不面向用户。用户永远不会直接连到 Mac Mini。

---

## 二、我们已经有什么

Doramagic 不是从零开始。v13.3.2 已经是一个成熟的系统，有大量可以复用的基础设施。用一句话说：**框架已经有了，需要给它装上新引擎。**

### 已有的（可直接复用）

**LLM 调用能力**：LLMAdapter 已经支持 Anthropic（Claude）、OpenAI（GPT）、Google（Gemini）三家，内置了自动重试、错误处理、token 计数。我们不需要重新写任何 LLM 调用代码——新系统所有的 LLM 调用直接走 LLMAdapter。

**知识提取流水线**：现有 7 阶段提取流水线（从 GitHub 仓库 → 提取知识 → 编译成 skill）已经完整运行。其中 Stage 0（框架检测）、Stage 1（Q1-Q7 问答）、Stage 1.5（假设验证）、DSD（幻觉检测 8 项检查）都可以被新的判断提取系统复用。

**50 个领域知识积木**：覆盖 Django、FastAPI、LangChain、React、Rust、Go 等 50 个技术领域。这些积木是判断系统的"启动知识"——告诉 Scout（定向模块）每个领域已经积累了什么，还缺什么。

**流程编排引擎**：FlowController 实现了条件 DAG（有条件的有向无环图）——简单说就是"根据上一步的结果，自动决定下一步该做什么"。新的采集流水线可以复用这个编排能力。

**API 服务基座**：preextract_api 已经有 6 个 FastAPI 接口在运行。新的晶体 API 可以在同一个基座上扩展。

**代码质量体系**：ruff（代码风格检查）+ mypy（类型检查）+ pytest（测试）+ GitHub Actions（自动化检查），`make check` 一个命令跑完全部检查。

### 需要新建的

| 模块 | 做什么 | 类比 |
|------|--------|------|
| Judgment Schema | 定义"一颗判断长什么样" | 产品规格书 |
| Source Adapters | 从各平台拉取数据 | 原材料采购员 |
| Extract 三条通道 | 从原材料中提炼判断 | 加工车间 |
| Refine 四步去重 | 去除重复和矛盾 | 质检车间 |
| Store 关联入库 | 把判断存入知识库并建立连接 | 仓库管理 |
| Retrieve 六步检索 | 根据用户意图找到相关判断 | 智能搜索 |
| Crystal Compiler | 把判断编译成种子晶体 | 成品包装 |
| 同步脚本 | 把知识库推送到线上服务器 | 物流发货 |

---

## 三、Mac Mini 上将运行的全部软件

### 3.1 操作系统和基础环境

Mac Mini 运行 macOS。Python 3.12 通过 uv（包管理工具）安装，已经在用。无需改变。

### 3.2 Doramagic 主程序

整个 Doramagic 项目就是一个 Python 项目，包含 19 个包。知识系统新增 3 个包：

```
packages/
├── contracts/            ← 已有，新增 Judgment 类型定义
├── shared_utils/         ← 已有，LLMAdapter 直接复用
├── extraction/           ← 已有，Stage 0/1/1.5/DSD 复用
├── controller/           ← 已有，DAG 编排复用
├── judgment_schema/      ← 新建：判断的规格定义和校验
├── judgment_pipeline/    ← 新建：采集流水线（5个阶段）
└── crystal_compiler/     ← 新建：种子晶体编译引擎
```

### 3.3 定时任务

Mac Mini 24 小时运行。采集流水线通过定时任务自动执行：

```
每天凌晨 2:00  — GitHub 采集（freqtrade Issues/PRs）
每天凌晨 4:00  — 清洗 + 入库
每周一 6:00    — 缺口分析 + 更新采集计划
采集完成后     — 自动同步到线上 PostgreSQL
```

初期（第一次实验）全部手动触发，不需要定时任务。

### 3.4 外部依赖

Mac Mini 需要访问的外部服务：

| 服务 | 用途 | 认证方式 | 费用 |
|------|------|---------|------|
| GitHub API | 拉取 Issues/PRs/Discussions | Personal Access Token | 免费（5000 请求/小时） |
| Claude API | LLM 调用（提取、分类、裁决） | API Key | Claude Max 订阅覆盖 |
| Reddit API | 拉取帖子和评论（第二批） | OAuth App | 免费（60 请求/分钟） |
| Discord API | 拉取消息（第二批） | Bot Token | 免费 |
| 线上服务器 | 同步知识库 | SSH Key | - |

---

## 四、数据在 Mac Mini 上的完整流转

我用一个具体例子走一遍完整流程：从 freqtrade 的一条 GitHub Issue 到一颗入库的判断。

### Step 1：采集（Scout + Source Adapter）

```
命令: doramagic harvest --domain finance --source freqtrade

Mac Mini 做了什么:
  1. 读取采集计划（哪些项目、哪些来源、补哪些缺口）
  2. 调用 GitHub API，拉取 freqtrade 的 Issues
     - 过滤条件: label:bug, comments>=3, created:>2024-01-01
     - 每个 Issue 拉取: 标题、正文、所有评论、关联的 PR、标签
  3. 通过 GitHubAdapter 转换为统一格式 (RawExperienceRecord)
     - 提取质量信号: 是否有关联的合并 PR? 评论数? 维护者是否回复?
  4. 存入 knowledge/pipeline/raw_records/

耗时: 约 5-10 分钟（取决于 Issue 数量，200 条约需要 400 次 API 调用）
成本: 免费（GitHub API 额度内）
产出: 200 条 RawExperienceRecord 文件
```

### Step 2：提取（Extract）

```
命令: doramagic extract --domain finance --channel experience

Mac Mini 做了什么:
  1. 三轨预过滤（不用 LLM，纯规则）
     - 轨道一: Issue 已关闭 + 有合并的 PR → 直接通过（约 60 条）
     - 轨道二: Issue 标签是 wontfix/by-design → 直接通过（约 10 条）
     - 轨道三: 打分，超过阈值的通过（约 30 条）
     - 未通过: 丢弃（约 100 条低质量 Issue）
     - 结果: 200 条 → 100 条进入下一步

  2. LLM 分类（Claude Haiku，快速便宜）
     - 每条 Issue 分类为: bug_confirmed / design_boundary / incident / workaround / anti_pattern
     - 耗时: 约 2 分钟（100 条 × Haiku 并发调用）
     - 成本: ≈ $0.10

  3. LLM 提取判断（Claude Sonnet，高精度）
     - 把每条 Issue 转化为判断三元组: 当[条件]时，必须/禁止[行为]，否则[后果]
     - Prompt 严格约束: 条件必须具体、行为必须可执行、后果必须可量化
     - 每条 Issue 可能产出 0-3 颗判断
     - 耗时: 约 10-15 分钟（80 条 × Sonnet）
     - 成本: ≈ $1.20

  4. 代码级校验（validate_judgment_core）
     - 检查三元组完整性
     - 检查模糊词（"注意""考虑""适当"→ 拒绝）
     - 检查原子性（"以及""同时"→ 要求拆分）
     - 未通过的判断: 退回 LLM 重写或丢弃

产出: 约 80 颗原始判断
```

### Step 3：清洗（Refine）

```
命令: doramagic refine --domain finance

Mac Mini 做了什么:
  1. 规范化（纯代码，零成本）
     - 生成每颗判断的 canonical signature
     - 词汇归一化: "float" → "binary_float", "PnL ledger" → "monetary_ledger"

  2. 分桶（纯代码）
     - 按领域分组，只在同组内比较

  3. 多信号判重（代码 + 可选 LLM）
     - 强重复: 同一 rule_sig + scope 重叠 > 70% → 直接标记
     - 弱重复: 向量相似度 > 0.78 → 送 LLM 裁决
     - LLM 只能输出四种结果之一（不允许自由发挥）

  4. 冲突检测
     - 同域 + 相反 modality（一个说"必须"，一个说"禁止"）→ 标记冲突
     - 严重度差 >= 2 级的自动裁决，其余进入人工队列

产出: 约 50 颗去重后的判断 + 若干冲突待审
```

### Step 4：入库（Store）

```
命令: doramagic store --domain finance

Mac Mini 做了什么:
  1. 对每颗新判断，扫描已有知识库中的相关判断
  2. LLM 判断关系并自动建立连接（Claude Sonnet）
     - 例: "yfinance 不可靠" → strengthens → "必须 dry-run 72 小时"
  3. 每条关系必须附理由（description 字段）
  4. 写入 knowledge/judgments/domains/finance.jsonl（一行一颗）
  5. 更新关系索引 _relations.jsonl
  6. 运行完整性检查: 是否有孤立判断（0 条关系）

产出: knowledge/judgments/ 目录下新增/更新的 JSONL 文件
耗时: 约 5 分钟
成本: ≈ $0.50（LLM 关联建立）
```

### Step 5：Git 提交 + 同步

```
Mac Mini 做了什么:
  1. git add knowledge/judgments/
  2. git commit -m "harvest: +50 judgments from freqtrade (2026-04-03)"
  3. 运行同步脚本: 将新增判断推送到线上 PostgreSQL

为什么用 Git:
  - 每一颗判断的新增、修改、删除都有历史记录
  - 可以随时回滚到任何版本
  - 可以 diff 两个版本之间的知识变化
  - 这是知识的"源代码管理"
```

### 一次完整采集的总结

| 环节 | 耗时 | LLM 成本 | 产出 |
|------|------|---------|------|
| 采集 | 5-10 分 | $0 | 200 条原始记录 |
| 提取 | 15-20 分 | $1.30 | 80 颗原始判断 |
| 清洗 | 5 分 | $0.30 | 50 颗去重判断 |
| 入库 | 5 分 | $0.50 | 50 颗入库判断 + 关系网络 |
| 同步 | 1 分 | $0 | 线上数据库更新 |
| **合计** | **约 35 分钟** | **≈ $2.10** | **50 颗高质量判断** |

---

## 五、Mac Mini 上的文件结构

```
~/Doramagic/                           ← 项目根目录
├── packages/                          ← 19 + 3 个 Python 包（代码）
│   ├── contracts/                     ← 类型定义（Judgment Schema 在此）
│   ├── shared_utils/                  ← LLMAdapter、公共工具
│   ├── extraction/                    ← 现有提取流水线
│   ├── controller/                    ← DAG 编排引擎
│   ├── judgment_schema/               ← [新建] 判断规格和校验
│   ├── judgment_pipeline/             ← [新建] 采集流水线
│   ├── crystal_compiler/              ← [新建] 晶体编译器
│   └── ...（其余 15 个现有包）
│
├── knowledge/                         ← 所有知识资产
│   ├── bricks/                        ← 现有 50 个领域积木
│   ├── judgments/                     ← [新建] 判断知识库
│   │   ├── domains/
│   │   │   ├── finance.jsonl          ← 金融领域判断
│   │   │   └── ...
│   │   ├── universal.jsonl            ← 跨领域通用判断
│   │   ├── _relations.jsonl           ← 关系索引
│   │   └── _vocabulary.yaml           ← 词汇归一化字典
│   ├── crystals/                      ← [新建] 编译好的种子晶体
│   └── pipeline/                      ← [新建] 流水线运行数据
│       ├── raw_records/               ← 原始采集记录
│       ├── extraction_queue/          ← 待提取队列
│       ├── review_queue/              ← 待人工审查（冲突/低信度）
│       └── gap_reports/               ← 覆盖缺口报告
│
├── config/
│   └── pipeline.yaml                  ← [新建] 流水线配置
│
├── scripts/
│   ├── release/                       ← 现有发布脚本
│   └── sync/                          ← [新建] 知识库同步脚本
│
├── tests/                             ← 测试
├── docs/                              ← 文档
└── .env                               ← API 密钥（不入 Git）
```

---

## 六、Mac Mini 的资源消耗

### 6.1 日常运行

| 资源 | 消耗 | Mac Mini 能力 | 余量 |
|------|------|-------------|------|
| CPU | 采集时峰值 30%（大部分时间在等 API 响应） | M4 Pro 12 核 | 充足 |
| 内存 | Python 进程 ~500MB + 知识库内存索引 ~100MB | 24 GB | 充足 |
| 磁盘 | 知识库 < 100MB + Git 历史 < 500MB + 原始记录 < 1GB | 512 GB+ | 充足 |
| 网络（上行） | 同步到线上服务器，每次 < 1MB | 家用宽带足够 | 充足 |
| 网络（下行） | GitHub API 调用 + LLM API 调用 | 家用宽带足够 | 充足 |

### 6.2 采集高峰期

当同时运行多源采集（GitHub + Reddit + Discord）时：

| 资源 | 消耗 | 说明 |
|------|------|------|
| CPU | 峰值 50% | 并发 API 调用 + JSON 解析 |
| 内存 | ~1.5 GB | 多个 adapter 同时运行 |
| 网络 | 多个 API 并发请求 | 受各平台 rate limit 约束，不会打满带宽 |
| LLM 调用 | 并发 5-10 个请求 | LLMAdapter 内置并发控制 |

**结论：Mac Mini M4 Pro 24GB 对知识工厂来说性能过剩。** 即使运行全部采集任务，也只用到一半不到的能力。剩余算力可以继续做开发工作，两不耽误。

---

## 七、安全考虑

### 7.1 Mac Mini 上存储的敏感信息

| 内容 | 位置 | 保护方式 |
|------|------|---------|
| GitHub Token | .env 文件 | 不入 Git，macOS 钥匙串（可选） |
| Claude API Key | .env 文件 | 同上 |
| 其他 API Keys | .env 文件 | 同上 |
| SSH Key（连接线上服务器） | ~/.ssh/ | macOS 系统级保护 |

### 7.2 知识库本身不敏感

判断库里存储的都是从公开来源（GitHub Issues、Reddit 帖子）提取的技术知识，不包含任何用户隐私或商业机密。知识库本身可以公开——事实上，开源知识库可能是未来的一个产品方向。

### 7.3 Mac Mini 不暴露到公网

Mac Mini 没有公网 IP，不运行对外服务，不接受外部连接。它只主动向外连接（调 API、推送到服务器）。攻击面极小。

---

## 八、故障与恢复

### 8.1 Mac Mini 宕机

影响：采集暂停。**不影响线上服务**——线上服务器有完整的知识库副本，独立运行。

恢复：重启 Mac Mini，重新运行采集任务。知识库有 Git 保护，不会丢数据。

### 8.2 网络中断

影响：API 调用失败。LLMAdapter 内置 3 级重试（1s → 2s → 4s）。如果持续中断，采集任务暂停，下次运行时从断点继续。

### 8.3 知识库损坏

极低概率。JSONL 是纯文本追加写入，不存在"半写入"导致的损坏。即使发生：

```
git log                       # 查看历史
git diff HEAD~1               # 对比上次提交
git checkout HEAD~1 -- knowledge/judgments/  # 回滚到上一个版本
```

Git 是最好的保险。

### 8.4 LLM 产出质量下降

检测：`validate_judgment_core()` 代码级拦截 + DSD 8 项幻觉检测。

应对：不合格的判断被拒绝或送入 `review_queue/`，不会进入正式知识库。

---

## 九、第一次实验——具体怎么做

### 9.1 目标

从 freqtrade 项目采集 50 颗判断 → 编译 1 颗种子晶体 → 与无晶体组做 A/B 对比测试。

### 9.2 开发步骤

**Sprint 1：地基（2 天）**

做什么：
- 在 contracts 包中用 Pydantic 定义 Judgment 模型（按 schema-synthesis.md 的 TypeScript 定义翻译成 Python）
- 实现 `validate_judgment_core()`——代码级拒绝不合格的判断
- 实现 JSONL 读写器——一行一颗判断的读取和追加写入
- 实现 canonical signature 生成器——给每颗判断算一个"指纹"
- 写单元测试：合法判断通过、缺字段拒绝、模糊词拒绝、非原子警告

验证方式：`make check` 全部通过。

**Sprint 2：采集流水线（3 天）**

做什么：
- 实现 GitHubAdapter——调用 GitHub API 拉取 freqtrade 的 Issues/PRs，转为 RawExperienceRecord
- 实现通道 C 三轨预过滤器——轨道一（代码共证）、轨道二（边界妥协）、轨道三（信号打分）
- 写 LLM 提取 prompt 模板——分类 prompt（给 Haiku）+ 判断提炼 prompt（给 Sonnet）
- 实现入库逻辑——写入 JSONL + 更新关系索引
- 四步去重先做前两步（规范化 + 分桶 + 强重复），弱重复 + LLM 裁决下个 Sprint 补

验证方式：
- 手动跑一次 `doramagic harvest --source freqtrade`
- 检查产出的判断质量（人工抽查 20 颗）

**Sprint 3：晶体编译 + 验证（2 天）**

做什么：
- 实现检索模块（Step 1-3 + Step 6 必做）——领域匹配 + 图谱扩展 + 排序
- 实现晶体编译器——把判断集按 crystal_section 组装成晶体文本
- 加入个性化提示——"请询问用户的框架版本和目标市场"
- 跑 A/B 测试：
  - A 组：纯 Claude，无晶体约束，做一个量化回测任务
  - B 组：Claude + 种子晶体约束，做同一个任务
  - 对比两组输出的质量（是否避开了已知坑）

验证方式：
- A/B 测试结果（目标：复现 7/8 vs 0/8 的差距）
- 缺口报告能识别出至少 3 个未覆盖的领域

### 9.3 时间线

```
第 1-2 天   Sprint 1: 地基
第 3-5 天   Sprint 2: 采集流水线
第 6-7 天   Sprint 3: 编译 + 验证

第 7 天结束: 有一个可运行的知识工厂原型
            + 50 颗判断
            + 1 颗种子晶体
            + A/B 测试结果
```

### 9.4 成功标准

| 指标 | 标准 |
|------|------|
| 判断数量 | >= 50 颗，覆盖 knowledge + resource + experience 三层 |
| 判断质量 | `validate_judgment_core` 通过率 100%，人工抽检 precision >= 80% |
| 去重效果 | 人工确认无明显重复 |
| 晶体效果 | A/B 测试：有晶体组显著优于无晶体组 |
| 闭环能力 | 缺口报告能识别至少 3 个未覆盖领域 |

---

## 十、第一次实验之后

实验成功后的下一步：

1. **扩大采集范围**——同领域更多项目（zipline、vnpy、backtrader），50 颗 → 500 颗
2. **接入第二批来源**——RedditAdapter、DiscordAdapter
3. **部署线上服务**——在 VPS 上搭建 Web + API，Mac Mini 定时同步知识库
4. **开放用户注册**——用户可以创造自己的晶体

但这些都是实验成功之后的事。**现在唯一的任务是跑通第一次实验。**
