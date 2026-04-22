# 第一性原理审计：现有系统 vs 判断系统需求

> 逐模块诚实评估。不为复用而复用。每个"可复用"的结论都必须经得起质问："它是为同一个问题设计的吗？"

---

## 核心认知

**现有系统和新系统解决的是两个根本不同的问题。**

| | 现有系统 | 判断系统 |
|---|---------|---------|
| **输入** | 一个 GitHub 仓库的源代码 | 社区经验（Issues、论坛帖子、博客） |
| **处理对象** | 代码结构、文件、依赖关系 | 人类讨论、失败案例、经验教训 |
| **输出** | SKILL.md（给 LLM 的角色说明书） | Judgment（原子化的约束三元组） |
| **消费者** | LLM 作为"角色扮演者" | LLM 作为"受约束的执行者" |
| **哲学** | "告诉 LLM 这个项目是什么" | "告诉 LLM 什么不能做" |

这个根本差异决定了：**大部分现有提取逻辑不能复用。** 不是因为代码质量不好，而是因为它们解决的问题不同。

---

## 一、逐模块审计

### 1. LLMAdapter — ✅ 真正可复用

**判定理由：** LLMAdapter 是一个通用的 LLM 调用层，与业务逻辑无关。它提供了：
- 多模型支持（Claude/GPT/Gemini）
- 自动重试（3 级退避）
- 拒绝检测
- Token 计数
- 工具调用

这些能力是判断系统的每个环节都需要的，且和"提取什么"无关。

**结论：直接复用，零改动。**

### 2. Stage 0（框架检测）— ⚠️ 有限复用

**现有功能：** 从本地仓库的文件系统中检测语言、框架、入口文件、命令、依赖。

**判断系统需要什么：** Scout 阶段需要知道目标项目用了什么框架，以便匹配知识领域。

**诚实评估：**
- Stage 0 要求仓库已经 clone 到本地，它遍历文件系统来检测。
- 判断系统的 Scout 不需要 clone 仓库。它需要的是"这个项目属于什么领域"——从 GitHub 的 topics、README、语言统计就能知道，不需要 clone 整个仓库再遍历文件。
- Stage 0 的 _detect_frameworks 是为了后续注入对应的 brick，这个场景和判断系统不同。

**结论：不复用 Stage 0 本身。** 从 GitHub API 获取项目元数据（topics、languages、description）比 clone + 文件遍历更轻量、更适合。如果未来某个采集通道需要 clone 仓库（通道 B 边界测试），届时可以调用 Stage 0，但不是核心路径。

### 3. Stage 1（Q1-Q7 问答）— ❌ 不能复用

**现有功能：** 7 个预设问题（能力、接口、设计理由、模式、约束、失败模式、社区反馈），基于 repo_facts 的硬编码规则回答。

**诚实评估：**
- Q1-Q7 的答案来源是**仓库的代码结构**（入口文件、依赖列表、框架特征），不是社区讨论。
- 回答方式是硬编码规则映射（如"检测到 Django → 回答'用了 ORM'"），不涉及 LLM 理解。
- 产出是 `Stage1Finding`——一个关于仓库特征的发现，不是"当X时必须/禁止Y否则Z"的判断三元组。
- Q6（失败模式）和 Q7（社区反馈）看似相关，但实际上是预设的通用答案（"LLM 可能产出错误 JSON"），不是从具体 Issue 中提取的真实经验。

**结论：不复用。** 判断系统的提取是从社区讨论中识别真实的失败模式和约束，这和"从代码结构推断项目特征"是完全不同的任务。

### 4. Stage 1.5（假设验证）— ❌ 不能复用

**现有功能：** LLM Agent 循环，用工具（文件搜索、代码搜索）在本地仓库中验证假设。

**诚实评估：**
- 假设是基于代码结构生成的（如"对话历史在注入 LLM 前做了压缩"），验证方式是**在代码中搜索证据**。
- 判断系统不需要在代码中验证假设。它需要从 Issue 的讨论中提取判断，这是**阅读和理解人类对话**，不是搜索代码。

**结论：不复用。** Agent 循环的模式（LLM 决策 → 执行工具 → 反馈结果）可以借鉴，但具体实现（文件搜索、代码 grep）和判断系统无关。

### 5. Brick Injection（积木注入）— ⚠️ 仅框架映射表可参考

**现有功能：** 根据检测到的框架名，加载对应的积木文件，注入到 LLM prompt 中。

**判断系统需要什么：** Scout 需要知道"金融领域已有哪些判断"来分析覆盖缺口。

**诚实评估：**
- 框架 → 积木文件的映射表（django → django.jsonl）有参考价值，因为它告诉 Scout 某个技术栈已经有基线知识。
- 但注入逻辑本身不可复用——判断系统不是"把积木塞到 prompt 里让 LLM 参考"，而是"分析已有判断库的覆盖状态，找出缺口"。

**结论：映射表可参考，注入逻辑不复用。** Scout 需要自己的缺口分析逻辑。

### 6. DSD（幻觉检测 8 项检查）— ⚠️ 部分可复用，但需要显著改造

**现有功能：** 8 项确定性检查，检测知识卡片是否有欺骗性。

**逐项评估：**

| DSD 检查 | 现有目标 | 对判断系统有用吗？ |
|----------|---------|-----------------|
| DSD-1 推理支撑比 | 检查 rationale 卡片是否有证据 | ✅ 直接适用：判断的 consequence 是否有证据支撑 |
| DSD-2 版本冲突 | 检查证据是否跨越多个大版本 | ✅ 直接适用：判断的证据是否版本一致 |
| DSD-3 异常主导比 | workaround 关键词占比过高 | ⚠️ 部分适用：但判断系统主动寻找 workaround，高占比反而是好信号 |
| DSD-4 技术支持占比 | maintainer 回复占比过高 | ⚠️ 语义相反：高 maintainer 回复在判断系统中是高质量信号 |
| DSD-5 推理密度 | 推测性语言过多 | ✅ 直接适用：判断中不应有"可能""大概""也许" |
| DSD-6 环境矛盾 | 不同卡片假设不同环境 | ✅ 直接适用：判断的 scope 是否自洽 |
| DSD-7 闭源依赖 | 核心功能依赖闭源服务 | ❌ 不适用：判断系统不关心这个 |
| DSD-8 断言无证据 | 强断言缺少证据引用 | ✅ 直接适用：判断的核心三元组是否有证据支撑 |

**结论：DSD-1、DSD-2、DSD-5、DSD-6、DSD-8 的检测逻辑可以复用，但需要改造——输入从 knowledge cards 变成 Judgment 对象，阈值和判定标准需要重新校准。DSD-3、DSD-4 的语义在判断系统中相反，不能直接用。DSD-7 不适用。**

**更诚实的说法：** 与其改造 5 项旧检查 + 新写判断系统特有的检查，不如为判断系统设计一套专用的质量检查体系。DSD 的设计模式（确定性、基于正则和阈值、返回结构化报告）值得学习，但具体检查项需要重写。

### 7. Knowledge Compiler — ❌ 不能复用

**现有功能：** 把知识卡片（CC-*/WF-*/DR-*）按 9 个 section 编译成 compiled_knowledge.md，带 token 预算裁剪。

**诚实评估：**
- 输入格式完全不同：现有是 YAML frontmatter 的 markdown 卡片，判断系统是 Judgment JSON 对象。
- 输出目标完全不同：现有产出是一篇 markdown 文档，判断系统产出是种子晶体（约束文本）。
- 编译逻辑完全不同：现有是按 section 分组 + token 裁剪，判断系统是按 severity 排序 + crystal_section 映射 + 个性化提示注入。
- Token 预算管理的思路可以借鉴，但实现需要重写。

**结论：不复用。Crystal Compiler 需要从零设计。**

### 8. Confidence System — ⚠️ 逻辑可借鉴，实现需重写

**现有功能：** 基于证据类型（CODE/DOC/COMMUNITY/INFERENCE）的布尔代数 → Verdict + PolicyAction。

**判断系统需要什么：** Judgment 的 confidence 体系不同——它基于 source level（S1 文档 / S2 跨项目 / S3 社区 / S4 推理）+ score + consensus + evidence_refs。

**诚实评估：**
- 现有系统的证据分类（CODE/DOC/COMMUNITY/INFERENCE）和判断系统有概念重叠，但不是一对一映射。
- 布尔代数裁决的思路（CODE+DOC=SUPPORTED, INFERENCE only=REJECTED）值得借鉴，但判断系统的裁决维度更多（source level、consensus 强度、证据数量）。

**结论：借鉴设计模式，重新实现。**

### 9. Community Signals — ⚠️ 采集能力可复用，分析逻辑需重写

**现有功能：** 从 GitHub API 拉取 Issues，按评论数和反应数排名，分类为 bug/wontfix/security/feature，计算 DSD 指标。

**判断系统需要什么：** 从 GitHub Issues 中拉取数据 → 三轨过滤 → 提取判断三元组。

**诚实评估：**
- **GitHub API 调用部分可复用：** `community_signals.py` 已经实现了 Issues 拉取、评论数排名、维护者识别。这些是判断系统 GitHubAdapter 需要的底层能力。
- **但分类和分析逻辑不能复用：** 现有分类是粗粒度的（bug/wontfix/feature），判断系统需要更细的分类（bug_confirmed/design_boundary/incident/workaround/anti_pattern）。现有的打分公式（comments × 2 + reactions）和判断系统的三轨过滤（代码共证/边界妥协/信号打分）完全不同。
- **关键缺失：** 现有系统不检查 Issue 是否关联了 merged PR——这是判断系统轨道一（代码共证）的核心信号。

**结论：GitHub API 调用的底层函数（httpx 请求、分页、rate limit 处理）可以复用。分类逻辑、过滤逻辑、打分公式全部重写。**

### 10. FlowController（DAG 编排）— ⚠️ 架构可借鉴，但判断流水线不需要这么复杂

**现有功能：** 12 个 Phase、条件分支、重试循环、降级模式、预算管理。

**诚实评估：**
- 判断流水线是**线性的**：Scout → Extract → Refine → Store → Retrieve。没有条件分支（不需要 BRICK_STITCH 快速路径），没有用户交互循环（不需要 CLARIFY）。
- FlowController 的复杂度来自于"不知道用户会给什么输入"（可能是 URL、可能是领域描述、可能是模糊查询）。判断系统的输入是确定的：一个领域 + 一组来源。
- 降级模式（full_skill → draft_skill → metadata_only）的思路有价值——判断采集也可能部分失败。但实现不需要 12 个 Phase 的状态机。

**结论：不复用 FlowController。** 判断流水线用简单的线性 Pipeline 类即可（5 个阶段顺序执行，每阶段有错误处理和部分失败降级）。

### 11. 知识积木（50 个 JSONL 文件）— ❌ 不能作为判断系统的知识源

**这是需要特别诚实评估的部分。**

**现有积木是什么：**
```json
{
  "brick_id": "py-l1-gil",
  "knowledge_type": "constraint",
  "statement": "Python's Global Interpreter Lock (GIL) prevents true parallel execution of threads...",
  "confidence": "high",
  "signal": "ALIGNED",
  "source_project_ids": ["hardcoded-expert-knowledge"]
}
```

**问题 1：来源不可追溯。** `source_project_ids: ["hardcoded-expert-knowledge"]` 意味着这些知识是人工编写的，没有指向具体的 Issue、PR 或文档 URL。判断系统的核心约束之一是**每颗判断必须有 evidence_refs**。积木做不到。

**问题 2：格式不兼容。** 积木的 `statement` 是一段散文描述（"Python's GIL prevents..."），不是判断三元组（"当X时，必须/禁止Y，否则Z"）。从散文到三元组不是简单的格式转换，而是语义的重新提炼。

**问题 3：粒度不对。** 积木是"关于一个框架的综合知识"，判断是"一个具体场景的一条具体约束"。积木 `py-l1-gil` 可能对应 3-5 颗不同的判断（CPU 密集型任务用 multiprocessing、asyncio 任务不受 GIL 影响、etc.），不是一对一的关系。

**问题 4：知识类型不对齐。** 积木的 knowledge_type 是 `capability|rationale|constraint|interface|failure|assembly_pattern`。判断系统的三层是 `knowledge|resource|experience`。这不是重命名的关系——积木的 `constraint` 可能落在判断系统的 `knowledge` 层或 `resource` 层，取决于约束的来源（跨项目共性 vs 单资源边界）。

**问题 5：缺少关系。** 积木之间没有关系（generates、depends_on、conflicts 等）。它们是孤立的知识片段，不是有连接的图谱。

**结论：现有积木不能导入判断系统。** 它们可以作为 Scout 的"线索"——告诉 Scout "Python 领域已经有 GIL 相关的基线知识，去社区找真实案例来验证和扩展"——但不能直接变成判断。

### 12. BrickV2（新格式积木）— ❌ 设计目标不同

**BrickV2 是什么：** 面向"积木组合"的格式，有 inputs/outputs/requires/conflicts_with/compatible_with。它是为了让积木能像乐高一样拼装。

**判断系统需要什么：** Judgment 是约束，不是组件。判断不需要 inputs/outputs，不需要 capability_type（poll/filter/notify/transform）。

**结论：BrickV2 和 Judgment 是两个不同产品方向的数据模型。不能复用。**

---

## 二、诚实的总结

### 真正可复用的（不改动或极少改动）

| 模块 | 复用内容 | 理由 |
|------|---------|------|
| LLMAdapter | 全部 | 通用 LLM 调用层，与业务无关 |
| GitHub API 底层调用 | community_signals.py 中的 httpx 请求、分页、rate limit | 底层 HTTP 能力，与分析逻辑无关 |
| 代码质量体系 | ruff + mypy + pytest + make check | 工程规范，与业务无关 |
| 包管理 + 构建 | uv + hatchling + pyproject.toml | 基础设施，与业务无关 |
| CI/CD | GitHub Actions | 基础设施 |

### 可以借鉴设计模式但必须重新实现的

| 模块 | 借鉴什么 | 为什么不能直接用 |
|------|---------|----------------|
| DSD 检测 | 确定性检查 + 正则 + 阈值 + 结构化报告的模式 | 具体检查项需要针对判断三元组重新设计 |
| Confidence System | 证据分类 → 布尔裁决的思路 | 判断系统的证据维度和裁决标准不同 |
| FlowController | 降级模式、阶段性错误处理 | 判断流水线是线性的，不需要条件 DAG |
| Token 预算管理 | budget-first 思想，section 配额 | 编译目标不同（晶体 vs SKILL.md） |

### 必须从零构建的

| 模块 | 原因 |
|------|------|
| Judgment Schema (Pydantic) | 全新数据模型，与 KnowledgeAtom/DomainBrick 不兼容 |
| Source Adapters | 全新采集层——RawExperienceRecord 格式、标准化信号、多平台适配 |
| 三轨预过滤器 | 全新过滤逻辑——代码共证/边界妥协/信号打分 |
| LLM 提取 prompt 模板 | 全新——从社区讨论提取判断三元组，不是从代码提取项目特征 |
| 四步去重流水线 | 全新——canonical signature、分桶、多信号判重、LLM 裁决 |
| 关系自动建立 | 全新——6 种关系类型的识别和连接 |
| 检索六步流程 | 全新——意图解析、图谱扩展、LLM 补盲、缺口报告 |
| Crystal Compiler | 全新——判断集 → 种子晶体，与 SKILL.md 编译完全不同 |
| 知识库存储 + 索引 | 全新——JSONL 分域存储、关系邻接表、向量索引 |
| 同步脚本 | 全新——JSONL → PostgreSQL 单向同步 |

### 现有积木的真实角色

**50 个积木文件不是判断系统的知识源，而是 Scout 的"线索地图"。**

Scout 看到"python_general.jsonl 有 GIL 相关积木" → 知道"GIL 是 Python 领域的已知问题" → 去 GitHub Issues 和 Reddit 找真实的 GIL 踩坑案例 → 提取成有证据支撑的判断。

积木是"地图上标注的地名"，判断是"实地勘察后画出的详细路线图"。前者指引方向，后者才是产品。

---

## 三、修正后的开发工作量评估

之前说"新建 3 个包"是低估了。诚实的评估：

**实际需要新建：**
- `judgment_schema/` — 判断数据模型 + 校验器 + 序列化
- `judgment_pipeline/` — 采集全流水线（5 个子模块）
- `crystal_compiler/` — 种子晶体编译引擎
- `judgment_store/` — 知识库存储 + 索引 + 同步（如果不放在 pipeline 里）

**实际需要的代码量（粗估）：**

| 模块 | 预估行数 | 复杂度 | 说明 |
|------|---------|--------|------|
| Judgment Schema | 500-800 | 中 | Pydantic models + validators + normalizer |
| GitHubAdapter | 400-600 | 中 | API 调用 + RawExperienceRecord 转换 + 信号映射 |
| 三轨预过滤器 | 300-500 | 中 | 确定性规则，无 LLM |
| LLM 提取 prompt 模板 | 200-300 | 高（prompt 质量关键） | 分类 prompt + 判断提炼 prompt |
| 四步去重 | 500-800 | 高 | 规范化 + 分桶 + 匹配 + LLM 裁决 |
| 入库 + 关系建立 | 400-600 | 中 | JSONL 写入 + 索引 + LLM 关联 |
| 检索六步 | 600-900 | 高 | 意图解析 + 图谱 BFS + LLM 补盲 + 缺口报告 |
| Crystal Compiler | 400-600 | 中 | 判断排序 + section 组装 + 个性化提示 |
| 质量检查体系 | 300-500 | 中 | 判断专用的 DSD-like 检查 |
| Pipeline 编排 | 200-300 | 低 | 线性流水线，不需要条件 DAG |
| 测试 | 1000-1500 | 中 | 各模块单元测试 + 集成测试 |
| **合计** | **4400-7400** | | |

**时间评估修正：** 之前说 7 天完成第一次实验，这仍然可行——但前提是第一次实验的范围严格限制：

- Sprint 1（2 天）：Schema + 校验器 + GitHubAdapter + 三轨过滤（最小采集通道）
- Sprint 2（3 天）：LLM 提取 + 简化版去重（前 2 步）+ 入库 + 基础关系建立
- Sprint 3（2 天）：简化版检索（直接匹配 + 1 跳图谱）+ 晶体编译 + A/B 测试

完整版（四步去重、LLM 裁决、六步检索、缺口闭环）需要额外 5-7 天。
