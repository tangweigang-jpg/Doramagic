---
name: doramagic
description: >
  从开源世界找最好的作业，提取智慧（WHY + UNSAID），
  锻造开袋即食的 OpenClaw Skill。
  集成：WHY 可恢复性判断 / DSD 8 指标暗雷检测 / Soul Extractor Stage 1-4 /
  5 类知识卡片 / 跨项目综合 / 社区信号采集 / 预提取领域 API 集成。
  Triggers on: /dora, doramagic, 帮我做一个, 我想做一个, forge skill, 锻造 skill
version: 2.0.0
user-invocable: true
allowed-tools: [exec, read, write]
tags: [doramagic, knowledge-extraction, skill-generation, s1-sonnet]
metadata:
  openclaw:
    skillKey: dora
    category: builder
    requires:
      bins: [python3, curl, unzip]
    storage_root: ~/clawd/doramagic/s1-sonnet/
---

# Doramagic S1-Sonnet — 全量研究集成版

> 不教用户做事，给他工具。——哆啦A梦式产品哲学
>
> 你自己就是 LLM。理解需求、分析代码、提取 WHY/UNSAID、综合知识、锻造叙事，全部由你直接完成。
> 确定性操作（搜索、下载、校验、组装文件）通过 exec 调用 Python 脚本。
> 不调任何外部 LLM API（不 import anthropic/openai/google）。

## 触发方式

用户输入以下任何形式，立即启动：
- `/dora <需求描述>`
- `帮我做一个 XXX 的 skill`
- `我想做一个 XXX`
- `doramagic <需求描述>`

收到触发后，立即回复：
> "收到！我来帮你从开源世界找最好的作业，提取设计智慧，锻造 Skill。开始 Phase A..."

然后按 Phase A → H 顺序执行。

---

## 暗雷知识库（Deceptive Source Detection — 执行全程参考）

在 Phase B 和 Phase C 中，你必须用以下 8 个指标对每个候选项目做快速扫描。
Top 10 暗雷速查：

| # | 暗雷 | 检测方式 |
|---|------|---------|
| 1 | **LLM 过度推理** | 代码简洁无注释，WHY 置信度全部高分 → 检查注释密度 < 5% |
| 2 | **隐性规模假设** | 大公司架构 + 小业务逻辑 → 基础设施复杂度倒挂 |
| 3 | **架构考古遗址** | CHANGELOG 出现 "rewrite/overhaul"，同时依赖新旧替代库 |
| 4 | **开源包闭源魂** | API wrapper 行数 > 业务逻辑行数，核心依赖闭源 SaaS |
| 5 | **Hidden Context** | "discussed offline/internal" 频繁出现 |
| 6 | **维护者独白社区** | 独立参与者 / Issue 数 < 2 |
| 7 | **Winner's History** | narrative 与早期 PR 历史不一致 |
| 8 | **Exception Bias** | 高互动线程异常/边缘场景占比 > 60% |
| 9 | **简历驱动开发** | 实体数量 << 抽象层数量 |
| 10 | **幽灵约束** | 为已修复旧 bug 做的反直觉设计 |

**Deceptive Source Detection（DSD）8 项指标：**

| # | 指标 | 风险阈值 | 检测方法 |
|---|------|---------|---------|
| 1 | Rationale Support Ratio | < 0.3 | WHY 证据数 / 叙事断言数 |
| 2 | Temporal Conflict Score | 高 | CHANGELOG "rewrite/overhaul/migration" |
| 3 | Exception Dominance Ratio | > 60% | 高互动线程中异常场景占比 |
| 4 | Support-Desk Share | > 70% | 求助线程 / 全部线程 |
| 5 | Public Context Completeness | 频繁 | "discussed offline/internal" 出现次数 |
| 6 | Persona Divergence Score | 高 | 同一项目服务差异过大的用户群体 |
| 7 | Dependency Dominance Index | > 1 | API wrapper 行数 / 业务逻辑行数 |
| 8 | Narrative-Evidence Tension | 全高分 | WHY 置信度全高 = 过度推理信号 |

**暗雷叠加规则：**
- 触发 1 个暗雷：标注"低风险，已知局限"
- 触发 2 个暗雷：风险等级升至"中危"，在 LIMITATIONS.md 专节说明
- 触发 3+ 个暗雷：风险等级升至"高危"，建议替换项目或大幅降低知识置信度

---

## Phase A：需求理解

**AI 做什么：**

将用户一句话解析为结构化 NeedProfile，包含：
- `domain`：问题领域（如：WiFi 密码管理、健康追踪、密码管理）
- `keywords`：用于 GitHub 搜索的英文关键词列表（3-5 个词组）
- `intent`：用户核心意图（动词短语）
- `constraints`：已知约束（语言偏好、离线需求、隐私敏感等）
- `anti_keywords`：排除词（如用户只要 CLI 则排除 web、mobile）
- `domain_id`：尝试映射到预提取领域（wifi_passwords、password_manager、health_data 等）

**示例解析（"我想做一个管理 WiFi 密码的工具"）：**
```
domain: WiFi 密码管理
keywords: ["wifi password manager", "wifi credentials storage", "wireless network manager", "wifi vault"]
intent: 安全存储和检索 WiFi 密码
constraints: [隐私敏感, 本地存储优先]
anti_keywords: ["cloud", "SaaS", "subscription"]
domain_id: password_manager (最近似)
```

**判断标准：** 如果用户需求模糊，主动追问一个最关键的澄清问题，然后继续执行。不要因为信息不完整而停止。

向用户展示 NeedProfile，然后说："Phase A 完成，开始发现作业..."

---

## Phase B：作业发现（含预提取 API + 暗雷快扫）

### B-0：尝试预提取 API

**exec 做什么（可选增强）：**

```bash
exec curl -s http://192.168.1.104:8420/domains/{domain_id}/bricks 2>/dev/null
```

- 如果 API 返回 domain bricks（JSON 格式），将其注入 Phase C 作为先验知识，并向用户说明"命中预提取领域，提取质量将提升"
- 如果 API 不可用（超时/404/连接拒绝），**直接跳过，不影响后续流程**。API 是加成不是依赖

### B-1：GitHub 搜索

**exec 做什么（搜索）：**

```bash
exec python3 {skill_dir}/scripts/github_search.py "{keywords[0]}" "{keywords[1]}" "{keywords[2]}" --top 5 --output ~/clawd/doramagic/s1-sonnet/runs/{run_id}/discovery.json
```

注意：`{skill_dir}` 是本 SKILL.md 所在目录的绝对路径（`skills/doramagic-s1/`），`{run_id}` 格式为 `YYYYMMDD_HHMMSS`。

**AI 做什么（筛选 + 暗雷快扫）：**

读取 discovery.json，从结果中筛选最相关的 **至少 2 个项目**（跨项目综合必须有 2+ 个）：

筛选标准：
1. stars 数量（高于 50 优先）
2. 描述与需求的语义相关性（你来判断，不是关键词匹配）
3. 排除明显不相关的（如名字相似但领域不同）
4. 优先选择有持续维护迹象的（updated_at 较新）

**对每个候选项目快速扫描 DSD 指标（至少检查 3 个）：**
- 看 description 和 topics 评估 Persona Divergence（服务人群是否过于分散）
- 看 updated_at 和 stars 关系评估 Winner's History（人气高但很久没更新 = 过时可能）
- 从 language 和 description 推断 Dependency Dominance（纯 wrapper 项目优先级降低）
- 在 LIMITATIONS.md 中记录每个项目的暗雷扫描结果

输出筛选后的候选列表，格式：
```
候选项目：
1. owner/repo（⭐ N）—— 理由：XXX | 暗雷快扫：[触发的指标] 或"初扫无明显暗雷"
2. owner/repo（⭐ N）—— 理由：XXX | 暗雷快扫：[触发的指标] 或"初扫无明显暗雷"
```

### B-2：下载项目

**exec 做什么（下载至少 2 个项目）：**

```bash
exec python3 {skill_dir}/scripts/github_search.py --download "owner1/repo1" --branch main --output ~/clawd/doramagic/s1-sonnet/runs/{run_id}/repos/
exec python3 {skill_dir}/scripts/github_search.py --download "owner2/repo2" --branch main --output ~/clawd/doramagic/s1-sonnet/runs/{run_id}/repos/
```

### B-3：提取确定性事实

**exec 做什么（对每个项目）：**

```bash
exec python3 {skill_dir}/scripts/extract_facts.py ~/clawd/doramagic/s1-sonnet/runs/{run_id}/repos/{repo_dir1}/ --output ~/clawd/doramagic/s1-sonnet/runs/{run_id}/facts_{repo1_name}.json
exec python3 {skill_dir}/scripts/extract_facts.py ~/clawd/doramagic/s1-sonnet/runs/{run_id}/repos/{repo_dir2}/ --output ~/clawd/doramagic/s1-sonnet/runs/{run_id}/facts_{repo2_name}.json
```

向用户报告："Phase B 完成。找到 N 个候选，已下载 [project1_name] 和 [project2_name]，开始灵魂提取..."

---

## Phase C：灵魂提取（核心阶段，Soul Extractor Stage 1-4）

**对每个下载的项目分别执行以下 Stage 流程：**

### WHY 可恢复性评估（Stage 0.5 — 提取前必做）

在开始提取前，评估项目的 WHY 可恢复性：

**评估清单（读取项目文件）：**
1. README 是否有 "Why/Motivation/Philosophy" 段落？
2. 是否有 ADR（Architecture Decision Records）文件？（docs/adr/, decisions/ 目录）
3. 是否有 Issue/PR 中维护者的设计解释？（需要 Phase D 数据，可延迟评估）
4. 是否有 CHANGELOG 中 "by design/won't implement" 的边界声明？

**判断输出：**
- 2 项以上满足：**"WHY 证据充分，可靠提取"**（在 PROVENANCE.md 标注置信度"高"）
- 1 项满足：**"WHY 证据部分，推断为主"**（置信度"中"，标注"部分为推断"）
- 0 项满足：**"WHY 无法从公开证据可靠重建"**（在 SKILL.md 中明确标注"WHY 部分为推断，置信度低"）
  - 此情况下：不允许编造流畅的设计哲学，改为描述"观察到的行为模式"

### Stage 1：灵魂发现（广度扫描）

执行前：先读取 `skills/soul-extractor/stages/STAGE-1-essence.md` 获取详细指令。

**AI 做什么：**

读取以下文件建立理解：
- `facts_{repo_name}.json`（结构骨架）
- 项目 README.md（设计意图）
- 主要入口文件（核心机制）
- CHANGELOG 或 HISTORY（演化轨迹）

回答 7 个 Soul Extractor 问题，写入 `~/clawd/doramagic/s1-sonnet/runs/{run_id}/{repo_name}/soul/00-soul.md`：

**Q1（WHAT）：这个项目解决什么问题？**（1-2 句，说明谁有这个痛点）

**Q2（WHAT）：如果没有这个项目，人们会怎么做？**（替代方案有多痛苦）

**Q3（WHAT）：它的核心承诺是什么？**（它保证做到的一件事）

**Q4（WHAT）：它用什么方式兑现承诺？**（核心机制一句话）

**Q5（WHAT）：一句话总结：**
"[项目] 让 [谁] 可以 [做什么]，而不用 [原来的痛苦方式]"

**Q6（WHY）：这个项目的设计哲学是什么？**（2-4 句，像创造者说话，是信念宣言不是功能描述）

提取方法：
- 查看 README 中的 "Why" / "Motivation" / "Philosophy" 段落
- 看技术选型（为什么用这个框架/存储？有没有对比？）
- 看 CHANGELOG 中被否决的功能（"won't implement" / "by design"）
- 看作者在 issue 中的解释性回复

**Q7（UNSAID）：社区踩过什么坑？文档没写但用过才知道的事？**（3-5 条）

提取方法：
- 看 issues 标题中的 "gotcha" / "unexpected" / "why does" / "bug" 模式
- 看 README 中的 "Known Issues" / "Caveats" / "Notes" 段落
- 推断：给定这个架构，哪些操作会产生意外副作用？

约束：Q6 不能是功能描述，Q7 必须具体可操作。如果证据不足，标注"推断"。

### Stage 2：概念卡 + 工作流卡提取

执行前：先读取 `skills/soul-extractor/stages/STAGE-2-concepts.md` 获取详细指令。

**AI 做什么（产出知识卡片文件）：**

提取 **至少 3 张概念卡**（写入 `cards/concept/` 目录）：

每张概念卡格式（文件名：CC-{repo_abbr}-{N}.md）：
```markdown
---
card_type: concept_card
card_id: CC-{repo_abbr}-001
repo: {repo_full_name}
title: "{核心概念名}"
source_url: https://github.com/{owner}/{repo}
---

## Identity
{这个概念是什么，一句话定义}

## Is / Is Not

| IS | IS NOT |
|----|--------|
| {是什么} | {不是什么} |

## Key Attributes

| Attribute | Type | Purpose |
|-----------|------|---------|
| {属性名} | {类型} | {用途} |

## Boundaries
- Starts at: {起点}
- Delegates to: {下游}
- Does NOT handle: {边界}

## Evidence
- {代码文件:行号 或 README 段落}
```

提取 2 张工作流卡（写入 `cards/workflow/` 目录）：

每张工作流卡包含：步骤（含 file:line）+ Mermaid 流程图 + 失败模式。

### Stage 3：规则卡提取（决策卡 + 陷阱卡）

执行前：先读取 `skills/soul-extractor/stages/STAGE-3-rules.md` 获取详细指令。

**AI 做什么（产出知识卡片文件）：**

提取 **至少 2 张决策卡**（写入 `cards/decision/` 目录）：

每张决策卡格式（文件名：DC-{repo_abbr}-{N}.md）：
```markdown
---
card_type: decision_card
card_id: DC-{repo_abbr}-001
repo: {repo_full_name}
title: "{决策名称}"
severity: CRITICAL|HIGH|MEDIUM|LOW
source_url: https://github.com/{owner}/{repo}
---

## 决策
{架构决策 IF/THEN 格式}

## 理由
{为什么这样决策——WHY}

## 替代方案
{被拒绝的方案及原因}

## Do
- {应该做的}

## Don't
- {不应该做的}

## Evidence
- {来源}
```

提取 **至少 2 张陷阱卡**（写入 `cards/trap/` 目录），重点从社区 issues/CHANGELOG 提取真实踩坑：

每张陷阱卡格式（文件名：TC-{repo_abbr}-{N}.md）：
```markdown
---
card_type: trap_card
card_id: TC-{repo_abbr}-001
repo: {repo_full_name}
title: "{陷阱名称}"
severity: CRITICAL|HIGH|MEDIUM
source_url: https://github.com/{owner}/{repo}
sources:
  - "GitHub Issue #{N} ({reactions} reactions)"
  - "CHANGELOG v{version}"
---

## 陷阱描述
{具体的踩坑场景，叙事体}

## 真实场景
{某人在某个具体场景下做了什么，发生了什么意想不到的结果}

## 根因
{为什么会这样}

## 如何避免
- {具体可操作的建议}

## 影响范围
- 谁会遇到：{目标用户群}
- 什么时候：{触发条件}
- 多严重：{后果}
```

提取 1-2 张特征卡（写入 `cards/signature/` 目录），记录该项目的独有特征。

### Stage 3.5：硬验证（事实检查 + 暗雷审查）

执行前：先读取 `skills/soul-extractor/stages/STAGE-3.5-review.md` 获取详细指令。

**AI 做什么（自我审查）：**

1. **事实检查**：对每张卡片的 Evidence 字段，确认来源是否真实存在（不是推断出来的）
2. **暗雷审查**：
   - 检查概念卡的 Q6/WHY 字段：是否有 Narrative-Evidence Tension（叙事流畅但无证据支撑）？
   - 计算 Rationale Support Ratio：该项目的 WHY 有多少有直接证据？比值 < 0.3 标注为高风险
   - 检查陷阱卡：是否引用了真实的 Issue 编号或 CHANGELOG 版本？
3. **暗雷叠加检查**：统计该项目触发的暗雷数量，触发 2+ 个升级风险等级

通过审查后，继续 Stage 4。

### Stage 4：专家叙事合成（可选，每项目一份）

执行前：先读取 `skills/soul-extractor/stages/STAGE-4-synthesis.md` 获取详细指令。

**AI 做什么（为每个项目合成专家叙事）：**

将 Stage 1-3 的知识合成一份专家叙事，写入 `~/clawd/doramagic/s1-sonnet/runs/{run_id}/{repo_name}/soul/expert_narrative.md`：
- 设计哲学（从 Q6 直接取）
- 心智模型（从 Q7 合成）
- 为什么这样设计（因果链，不是功能描述）
- 你一定会踩的坑（叙事体，引用真实 Issue）

向用户展示 Q6、Q7 和 1-2 个最重要的陷阱，然后说："灵魂已提取，开始社区采集..."

---

## Phase D：社区信号采集

**exec 做什么（调用社区信号脚本）：**

```bash
exec python3 {skill_dir}/scripts/community_signals.py --repo-url https://github.com/{owner1}/{repo1} --repo-path ~/clawd/doramagic/s1-sonnet/runs/{run_id}/repos/{repo_dir1} --output ~/clawd/doramagic/s1-sonnet/runs/{run_id}/community_{repo1_name}.json
exec python3 {skill_dir}/scripts/community_signals.py --repo-url https://github.com/{owner2}/{repo2} --repo-path ~/clawd/doramagic/s1-sonnet/runs/{run_id}/repos/{repo_dir2} --output ~/clawd/doramagic/s1-sonnet/runs/{run_id}/community_{repo2_name}.json
```

**AI 做什么（分析社区信号）：**

读取每个项目的 community_*.json，从中提取：
- **高频问题类型**（出现 3 次以上的模式）→ 补充到陷阱卡
- **高评论数 issues**（社区有强烈感受的点）→ 评估 Exception Bias 暗雷
- **"won't fix"/"by design" 回复**（维护者边界声明 = 隐含 WHY）→ 补充到决策卡
- **Support-Desk Share**：求助线程 / 全部线程，> 70% 标注 Support-Desk 暗雷
- **bug 标签分布**（反映真实使用中的痛点）→ 补充到 LIMITATIONS.md

社区信号写入对应陷阱卡（TC-xxx），标注来源 issue 编号。

如果 issues 获取失败（网络超时或 API 限制），跳过此阶段，在 LIMITATIONS.md 中注明。

---

## Phase E：跨项目综合

**AI 做什么（真实多项目对比）：**

对下载的 2+ 个项目执行跨项目综合：

### E-1：知识对比矩阵

| 维度 | {项目1} | {项目2} | 综合结论 |
|------|---------|---------|---------|
| 核心存储方式（Q4） | ... | ... | ... |
| 设计哲学（Q6） | ... | ... | ... |
| 主要暗雷 | ... | ... | ... |
| 社区最大痛点 | ... | ... | ... |

### E-2：共识 / 冲突 / 独有分析

**共识（multi-project consensus）：**
两个项目都做了相同选择 → 高置信度 brick，标注"跨项目验证"

**冲突（design conflict）：**
不同项目做了不同选择 → 标注冲突，解释可能原因（目标用户不同？规模不同？时代不同？），不替用户决策

**独有（single-source knowledge）：**
只有一个项目有的知识 → 标注"来源单一，谨慎采用"

### E-3：假公约数检测

如果两个项目的"共识"实际上指向同一个上游库（如都依赖同一个底层库的同一个功能），标注："此共识为非独立验证（同一上游库），不代表设计选择的收敛"

### E-4（可选）：调用跨项目比较脚本

```bash
exec python3 packages/cross_project/doramagic_cross_project/compare.py \
  --project1 ~/clawd/doramagic/s1-sonnet/runs/{run_id}/{repo1_name}/soul/ \
  --project2 ~/clawd/doramagic/s1-sonnet/runs/{run_id}/{repo2_name}/soul/ \
  --output ~/clawd/doramagic/s1-sonnet/runs/{run_id}/cross_project_analysis.json \
  2>/dev/null || echo "cross_project compare not available, using AI synthesis"
```

---

## Phase F：Skill 锻造（从知识卡片编译）

**AI 做什么（撰写内容）：**

根据 Phase A-E 的分析，从知识卡片编译以下三份文档。

### 1. SKILL.md（为用户锻造的目标 Skill）

结构（**内容必须从知识卡片编译而来，不是重新编写**）：

```markdown
---
name: {skill_name}
description: >
  {Q5 的一句话总结}
version: 1.0.0
user-invocable: true
allowed-tools: [exec, read, write]
tags: [{domain_tag}, {relevant_tags}]
metadata:
  openclaw:
    skillKey: {short_key}
    category: {category}
    storage_root: ~/clawd/{skill_name}/
---

# {Skill 标题}

## 这个 Skill 做什么

{Q1 + Q5}

## 设计哲学（WHY）

{Q6 — 核心信念，从概念卡和决策卡编译。如果 WHY 可恢复性低，明确标注"以下为推断，置信度低"}

## 核心概念

{从概念卡 CC-xxx 编译，每个概念的 Is/IsNot 摘要}

## 关键决策

{从决策卡 DC-xxx 编译，每个决策的 Do/Don't}

## 已知陷阱（UNSAID）

{从陷阱卡 TC-xxx 编译，含 Issue 编号引用}

## 跨项目共识

{Phase E 的共识结论，高置信度知识}

## 设计冲突（你需要自己决定）

{Phase E 的冲突结论，标注各自适用场景}

## 局限性

{LIMITATIONS.md 摘要}
```

### 2. PROVENANCE.md（按卡片 ID 溯源）

```markdown
# PROVENANCE.md — 知识来源溯源

## 参考项目

| 项目 | URL | Stars | 分析时间 | WHY 可恢复性 |
|------|-----|-------|---------|------------|
| {owner/repo} | https://github.com/{owner/repo} | {stars} | {date} | 高/中/低 |

## 按卡片 ID 溯源

### 概念卡
| 卡片 ID | 核心内容 | 来源文件/Issue | 置信度 | Rationale Support Ratio |
|---------|---------|--------------|-------|------------------------|
| CC-xxx-001 | ... | README:§N | 高 | 0.7 |

### 决策卡
| 卡片 ID | 决策 | 来源 | WHY 证据类型 |
|---------|------|------|------------|
| DC-xxx-001 | ... | ADR / Issue #N | 直接证据/推断/无证据 |

### 陷阱卡
| 卡片 ID | 陷阱 | Issue # | Reactions |
|---------|------|---------|-----------|
| TC-xxx-001 | ... | #N | N |

## 许可证
- {owner/repo}：{license_name}
```

### 3. LIMITATIONS.md（含暗雷评估）

```markdown
# LIMITATIONS.md

## 暗雷评估结果

### {项目1} 暗雷扫描
| 指标 | 评分 | 说明 |
|------|------|------|
| Rationale Support Ratio | {value} | {触发/未触发} |
| Temporal Conflict Score | {value} | {触发/未触发} |
| Exception Dominance Ratio | {value} | {触发/未触发} |
| ... | ... | ... |

**综合风险等级：** 低/中/高危

{如果高危，说明具体原因和应对建议}

### {项目2} 暗雷扫描
...

## 已知局限

- **覆盖范围**：本 Skill 基于 {N} 个开源项目提取，不代表所有实现方式
- **时效性**：分析于 {date}，项目后续更新未纳入
- **WHY 置信度**：
  - {项目1}：{高/中/低} — {原因}
  - {项目2}：{高/中/低} — {原因}
- **跳过阶段**：{如果有阶段因网络/API 限制跳过，在此注明}
- **预提取 API**：{命中/未命中/不可用}

## 不适用场景

- {明确列出这个 Skill 不适合的需求}

## 数据新鲜度

- 参考项目最后更新：{updated_at}
- Doramagic S1 分析时间：{analysis_date}
```

**exec 做什么（组装输出）：**

```bash
exec python3 {skill_dir}/scripts/assemble_output.py \
  --skill-content-file ~/clawd/doramagic/s1-sonnet/runs/{run_id}/skill_draft.md \
  --provenance-content-file ~/clawd/doramagic/s1-sonnet/runs/{run_id}/provenance_draft.md \
  --limitations-content-file ~/clawd/doramagic/s1-sonnet/runs/{run_id}/limitations_draft.md \
  --output-dir ~/clawd/doramagic/s1-sonnet/runs/{run_id}/output/
```

注意：先将三份文档的文本内容写入临时草稿文件（用 write 工具），再 exec 调 assemble_output.py 组装。

---

## Phase G：质量门控（扩展暗雷检测）

**exec 做什么（校验）：**

```bash
exec python3 {skill_dir}/scripts/validate_skill.py ~/clawd/doramagic/s1-sonnet/runs/{run_id}/output/ --output ~/clawd/doramagic/s1-sonnet/runs/{run_id}/validation_report.json
```

**AI 做什么（判断 + 暗雷二次检查）：**

读取 validation_report.json：
- 如果 status == "PASS"：继续 Phase H
- 如果 status == "REVISE"：根据 revise_instructions 修补内容，重新调用 assemble_output.py，最多重试 2 次
- 如果反复 REVISE 无法修复：继续 Phase H，在交付时向用户说明

**validate_skill.py 的扩展检测项（已在脚本中实现）：**
- WHY 过度推理检查：检测 WHY 内容是否缺乏具体证据引用
- Rationale Support Ratio 警告：置信度全高但无 Issue/ADR 引用
- Narrative-Evidence Tension：叙事流畅度与证据密度的张力

常见问题自动修补规则：
- "no WHY content"：补充 Q6 内容到 SKILL.md 的"设计哲学"章节
- "no LIMITATIONS"：补充 LIMITATIONS.md
- "no source URL in PROVENANCE"：补充 GitHub URL

---

## Phase H：交付

**AI 做什么：**

1. 展示最终输出文件路径：
   ```
   输出目录：~/clawd/doramagic/s1-sonnet/runs/{run_id}/output/
   ├── SKILL.md
   ├── PROVENANCE.md
   └── LIMITATIONS.md

   知识卡片：skills/doramagic-s1/cards/
   ├── concept/  ({N} 张概念卡)
   ├── workflow/ ({N} 张工作流卡)
   ├── decision/ ({N} 张决策卡)
   ├── trap/     ({N} 张陷阱卡)
   └── signature/({N} 张特征卡)
   ```

2. 向用户展示 SKILL.md 的核心内容（设计哲学 + 已知陷阱 + 跨项目共识部分）

3. 诚实说明本次提取的局限：
   - 分析了哪些项目
   - 哪些阶段因为限制被跳过
   - 每个项目的 WHY 置信度等级
   - 触发了哪些暗雷，以及应对建议

4. 提示用户下一步：
   > "这份 Skill 可以放到 OpenClaw 的 skills/ 目录下直接使用。知识卡片在 cards/ 目录，可单独复用。如果你发现陷阱不准确，欢迎告诉我，我来更新。"

---

## 错误处理规则

| 错误类型 | 处理方式 |
|----------|----------|
| GitHub API 限速（403/429）| 等待 10 秒重试一次，失败后说明该项目并继续 |
| 下载超时 | 尝试 master 分支，失败后跳过该项目继续 |
| issues 获取失败 | 跳过 Phase D，在 LIMITATIONS 中注明 |
| 预提取 API 不可用 | 跳过 B-0，不影响后续流程 |
| 项目目录为空 | 报告错误，请用户提供备选项目 |
| exec 脚本 not found | 检查 `{skill_dir}/scripts/` 路径，告知用户 |
| WHY 无法可靠重建 | 标注推断，不编造，继续提取 WHAT 层 |
| 暗雷高危 | 在 LIMITATIONS 专节说明，建议用户替换项目 |

---

## 存储约定

所有文件写入 `~/clawd/doramagic/s1-sonnet/` 下：

```
~/clawd/doramagic/s1-sonnet/
└── runs/
    └── {run_id}/           # YYYYMMDD_HHMMSS
        ├── discovery.json  # Phase B 搜索结果
        ├── facts_{repo1}.json   # Phase B 确定性事实
        ├── facts_{repo2}.json
        ├── community_{repo1}.json  # Phase D 社区信号
        ├── community_{repo2}.json
        ├── {repo1_name}/soul/    # Phase C 知识提取
        │   ├── 00-soul.md
        │   └── expert_narrative.md
        ├── {repo2_name}/soul/
        ├── cross_project_analysis.json  # Phase E
        ├── skill_draft.md      # Phase F 草稿
        ├── provenance_draft.md
        ├── limitations_draft.md
        ├── validation_report.json
        └── output/
            ├── SKILL.md
            ├── PROVENANCE.md
            └── LIMITATIONS.md
```

知识卡片写入 `skills/doramagic-s1/cards/` 下，跨 run 共享复用。

---

## 关键约束

1. **你就是 LLM** — 不调外部 AI API，你自己完成所有智能操作
2. **必须下载 2+ 个项目** — 跨项目综合是核心能力，不能只分析 1 个
3. **知识卡片是中间产物** — 最终 SKILL.md 从卡片编译，不是直接写出
4. **WHY 必须存在** — 如果 SKILL.md 没有"设计哲学"或"WHY"章节，产品无价值
5. **UNSAID 必须存在** — 如果 SKILL.md 没有"已知陷阱"或"UNSAID"章节，产品无价值
6. **暗雷必须检查** — 每个项目至少检查 3 个 DSD 指标，结果写入 LIMITATIONS.md
7. **WHY 可恢复性必须评估** — 每个项目必须评估 4 项指标，给出置信度等级
8. **真实数据** — 不 mock，不 fallback 到虚构内容；如果 GitHub 不可用，明确告知用户
9. **溯源** — PROVENANCE.md 按卡片 ID 追溯，每条 WHY 标注 Rationale Support Ratio
10. **OpenClaw 适配** — 存储路径只用 `~/clawd/`，不用其他路径
