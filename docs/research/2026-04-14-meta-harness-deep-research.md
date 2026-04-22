# Meta-Harness 深度研究报告：理论解析与 Doramagic 应用

> **论文**：Meta-Harness: End-to-End Optimization of Model Harnesses
> **作者**：Yoonho Lee, Roshen Nair, Qizheng Zhang, Kangwook Lee, Omar Khattab, Chelsea Finn
> **机构**：Stanford, KRAFTON, MIT
> **发表**：2026-03-30, arXiv:2603.28052
> **项目页**：https://yoonholee.com/meta-harness/
> **代码**：https://github.com/stanford-iris-lab/meta-harness-tbench2-artifact
> **研究日期**：2026-04-14
> **性质**：深度技术研究，含与 Doramagic 的对应分析

---

## 一、问题定义与动机

### 1.1 Harness 的精确定义

Meta-Harness 对 harness 的定义是：**围绕固定 LLM 的有状态程序，决定模型在每一步看到什么上下文**。形式化定义为：对于 harness H、模型 M、任务实例 x，执行一条轨迹 τ ~ p_M(H, x)，harness 在每步为 M 构造 prompt、解析响应、更新自身状态。优化目标是找到使期望回报最大化的 H*：

```
H* = arg max_H  E_{x~X, τ~p_M(H,x)} r(τ, x)
```

这个定义比 "prompt engineering" 宽泛得多。Prompt engineering 操作的是文本字符串（模板、少样本示例的选择和排列），而 harness engineering 操作的是**可执行的 Python 程序**——包含检索逻辑、路由策略、内存管理、上下文构造、输出解析等完整的信息流控制代码。论文引用了 Can Boluk 的实验数据：仅改变 harness 而不改变模型，同一 benchmark 上的性能差距可达 **6 倍**。

### 1.2 与 Prompt Engineering 的根本区别

| 维度 | Prompt Engineering | Harness Engineering |
|------|-------------------|---------------------|
| 搜索空间 | 文本字符串 | 可执行 Python 程序 |
| 可变元素 | 模板、少样本、指令措辞 | 检索策略、路由逻辑、内存、上下文构造、输出解析 |
| 有状态性 | 通常无状态 | 有状态（跨步骤积累经验） |
| 影响范围 | 单次 LLM 调用 | 整个推理轨迹（多步决策的因果链） |
| 正则化 | 易过拟合到特定措辞 | 代码倾向于产出连贯算法，天然正则化 |
| 可检查性 | 文本含义模糊 | 代码逻辑可审计，过拟合可见（if-chain、硬编码映射） |

### 1.3 现有方法的具体局限性

论文系统性地分析了六种现有文本优化方法的反馈机制（Table 1）：

| 方法 | 历史记忆 | 日志内容 | MTok/iter |
|------|---------|---------|-----------|
| OPRO | 窗口 | 过去的 (solution, score) 对 | 0.002 |
| TextGrad | 上一个 | 当前 artifact 的文本反馈 | 0.015 |
| AlphaEvolve | 窗口 | 程序数据库 + 评估分数 | 0.022 |
| GEPA | 摘要 | 回放轨迹的反射反馈 | 0.008 |
| Feedback Descent | 摘要 | 比较 + 文本反馈 | 0.012 |
| TTT-Discover | 窗口 | 前一个 solution 片段 | 0.026 |
| **Meta-Harness** | **完整** | **所有日志和分数** | **10.0** |

关键洞察：Meta-Harness 的反馈通道比最强基线宽三个数量级。

这些方法的三类共同缺陷：

**缺陷 1：无记忆性（Memoryless）**。OPRO 和 TextGrad 只条件于标量分数或当前候选。它们看不到"候选 A 在第 5 步因为检索了错误的文档而失败"，只看到"候选 A 得分 37%"。

**缺陷 2：短视野（Short-horizon）**。所有方法的反馈窗口限于当前候选或最近几个候选。但 harness 的因果链是长视野的：一个早期的存储决策（存什么到内存）可能在很多推理步骤后才显现影响。截断历史就截断了因果链。

**缺陷 3：模板化反馈（Templated feedback）**。Feedback Descent 和 GEPA 将反馈压缩为预定义格式的摘要或比较。但"哪些信息对诊断有用"本身是未知的——需要由 proposer 自己决定查看什么，而不是由框架预先决定。

### 1.4 "压缩反馈"问题的理论根基

论文的核心论点是：**harness 优化中，信息压缩是有害的**。

这与传统机器学习中"学习压缩表示"的直觉相反。根本原因在于 harness 的特殊性：

1. **因果链长度**：harness 操作于整个推理轨迹。一个检索策略的微小变化可能在 10 步之后才表现为答案错误。压缩掉中间 trace 就切断了因果诊断的可能性。

2. **失败模式多样性**：不同任务实例可能因完全不同的原因失败。标量分数无法区分"检索了错误文档"和"正确文档但 prompt 格式导致模型忽略"。

3. **摘要的信息损失**：论文最惊人的发现是 LLM 生成的摘要**比纯分数还差**（Table 3：38.7% vs 41.3%）。这说明摘要不仅丢失了信息，还引入了误导——LLM 在摘要时会做出错误的因果归因，将 proposer 引向错误方向。

理论上，这可以用信息瓶颈（Information Bottleneck）框架理解：压缩操作丢弃的不是噪声，而是对诊断至关重要的因果细节。完整的执行 trace 是一个高维信号，其中"哪些维度有用"取决于当前诊断假设——这是只有 proposer 在运行时才能确定的，不能由框架预先压缩。

---

## 二、方法论与架构

### 2.1 Algorithm 1：外层搜索循环

```
Algorithm 1  Meta-Harness outer loop over harnesses
─────────────────────────────────────────────────────
Input:  tasks X, LLM M, proposer P, iterations N
Initialize: population H                    ▷ Initial set of valid harnesses
Initialize: filesystem D ← ∅                ▷ stores code, scores, traces

for H in H do
    E_H ← Evaluate(H, M, X)
    D ← D ∪ {(H, E_H)}
end for

for t = 1, ..., N do
    Proposer P queries filesystem D          ▷ inspects prior harnesses and scores
    Proposer P proposes k new harnesses {H_1, ..., H_k}
    for H in {H_1, ..., H_k} do
        if H passes interface validation then
            D ← D ∪ {(H, EVALUATE(H, M, X))}
        end if
    end for
end for

return Pareto frontier of harnesses stored in D
```

关键设计决策分析：

**决策 1：Proposer 是 coding agent 而非 raw LLM**。选择 Claude Code（Opus 4.6）作为 proposer，因为它能调用开发者工具（grep, cat, 读文件、写代码）。这不是偶然选择——论文脚注 1 明确指出"这个工作流直到 2026 年初 coding agent 能力大幅提升后才变得实际可行"。

**决策 2：Filesystem 而非 prompt 注入**。所有历史经验存储在文件系统中，proposer 通过终端工具（grep, cat）选择性读取，而不是作为一个巨大 prompt 一次性注入。这解决了上下文窗口限制——文件系统通常远大于 proposer 的上下文窗口，但 proposer 可以按需选择性访问。

**决策 3：不施加 parent selection 规则**。不像遗传算法那样规定锦标赛选择或轮盘赌选择，Meta-Harness 让 proposer 自己决定检查哪些历史候选。这是"最小化外层结构"哲学的体现。

**决策 4：返回 Pareto 前沿而非单一最优**。当多个目标相关时（如准确率 vs token 成本），系统返回整个 Pareto 前沿，让用户选择操作点。

### 2.2 Agentic Proposer 的具体工作流程

每次迭代中，proposer 的行为可分解为以下步骤：

**步骤 1：诊断阶段（Diagnosis）**
- 读取文件系统中的历史候选列表和分数
- 选择性打开感兴趣的候选源码（通常 41% 的读取是源码）
- 选择性打开对应的执行 trace（40% 的读取是 trace）
- 查看分数摘要（6%）和其他文件（13%）
- 中位数读取 **82 个文件/迭代**（范围 69-99）

**步骤 2：假设形成（Hypothesis Formation）**
- 基于观察到的失败模式，形成为什么之前的候选失败的假设
- 识别混淆因子（confounds）——例如 TerminalBench-2 搜索中，proposer 在第 3 次迭代识别出 prompt 模板修改与结构性修复之间的混淆

**步骤 3：干预设计（Intervention Design）**
- 决定修改粒度：局部编辑、模块替换、或全程序重写
- 参考超过 20 个历史候选设计新方案
- 修改范围从检索逻辑到 prompt 构造到内存管理

**步骤 4：代码生成与验证（Code Generation）**
- 生成新的 harness 代码（单文件 Python 程序）
- 通过轻量级接口验证（import + 小规模测试）确保程序可运行

### 2.3 外层循环的设计决策——为什么最小化结构

论文明确表示外层循环"deliberately minimal"。这不是偷懒，而是有深思熟虑的原因：

1. **避免硬编码搜索启发式的过时**：如果硬编码了"总是从最佳候选变异"的规则，就无法发现"从两个中等候选合并"的策略（数学检索 harness 正是通过合并两条搜索路线发现的）。

2. **允许 proposer 能力增长自动转化为搜索质量**：随着 coding agent 变得更强，Meta-Harness 不需要修改外层循环就能自动受益。硬编码的启发式反而会限制更强 agent 的发挥。

3. **与 coding agent 训练流程对齐**：read-write-execute 是 coding agent 天然擅长的工作流。最小化的外层循环恰好利用了这一优势。

### 2.4 Code-Space vs Prompt-Space 搜索的理论优势

将搜索空间从文本字符串转移到可执行代码带来四个理论优势：

**优势 1：自然正则化**。编程模型倾向于提出"连贯算法"而非"硬编码映射表"。这是因为 LLM 的代码生成训练数据中，算法性代码远多于巨大的 if-else 链。过拟合在代码空间中更容易被发现和审计——硬编码的类别映射或脆弱的 if-chain 在代码审查中一目了然。

**优势 2：组合表达力**。代码可以表达控制流（条件分支、循环、函数调用），而 prompt 字符串只能表达线性序列。4 路数学路由器就是一个 prompt 空间无法自然表达的策略。

**优势 3：跨模型可迁移性**。发现的 harness 是 100-1000 行可读 Python 代码，可以在未来更强的模型上直接复用。数学检索 harness 在 5 个未见过的模型上平均提升 4.7 分，证明了这种迁移性。

**优势 4：可组合性**。不同的代码模块可以独立改进然后组合。论文中数学检索 harness 就是通过合并两条成功搜索路线（一条贡献了更好的几何路由，另一条贡献了更好的组合数学路由）得到的。

### 2.5 Token 预算策略：10M tokens/iteration 如何分配

10M tokens/iteration 是一个估算值，基于 TerminalBench-2 设置中最严苛的场景。分配方式不是静态预设的，而是由 proposer 的行为动态决定：

- **源码阅读**（约 41%）：每个历史 harness 约 100-1000 行代码，读取 20+ 个候选的源码
- **执行 trace**（约 40%）：每个候选在每个搜索集任务上的推理轨迹（prompt + 模型输出 + 工具调用 + 状态更新）
- **分数与摘要**（约 6%）：评估分数的结构化文件
- **其他**（约 13%）：目录结构、配置文件、diff 比较等

关键点是 proposer 通过 grep/cat 选择性访问，而非全部加载到上下文。实际进入 proposer 上下文窗口的 token 远少于 10M——10M 是可访问的总诊断信息量。

---

## 三、消融实验详解

### 3.1 Table 3 完整数据与分析

| 条件 | Scores | Code | Summ. | Traces | Median↑ | Best Acc↑ | >ZS |
|------|--------|------|-------|--------|---------|-----------|-----|
| Scores Only | ✓ | ✓ | × | × | 34.6 | 41.3 | 26 |
| Scores + Summary | ✓ | ✓ | - | × | 34.9 | 38.7 | 23 |
| Meta-Harness (full) | ✓ | ✓ | - | ✓ | **50.0** | **56.7** | **39** |

">ZS" 列表示超过 zero-shot 基线的运行次数（共 40 次）。

### 3.2 为什么 LLM 摘要比纯分数还差

这是论文最反直觉的发现。Scores + Summary 条件下：
- Best accuracy 从 41.3% 降到 38.7%（降 2.6 个百分点）
- >ZS 次数从 26 降到 23（成功率下降 11.5%）

原因分析：

**假说 1：错误因果归因**。LLM 在生成摘要时会做出因果推断（"这个候选失败是因为 X"），但这种推断经常是错误的。当 proposer 接收到带有错误因果归因的摘要时，会被引向错误的修改方向。纯分数虽然信息量少，但至少不会传递错误信息。

**假说 2：信息覆盖偏差**。摘要倾向于关注"最显眼的失败"（如最差的任务），忽略了"最有诊断价值的模式"（如某类任务系统性地比另一类好 5 个百分点）。这种偏差在压缩后被放大。

**假说 3：摘要格式锁定**。一旦 proposer 习惯了从摘要中获取方向性建议，它倾向于"执行摘要的建议"而非"独立诊断"。这降低了搜索的多样性。

论文将此解读为：**摘要不仅丢失了信号，还积极引入了噪声。完整的执行 trace 才是 harness 搜索的关键原料。**

### 3.3 Filesystem Access 的具体 API 设计

文件系统的组织结构（从论文和附录 D 推断）：

```
search_directory/
├── harness_001/
│   ├── harness.py           # 源码
│   ├── scores.json          # 评估分数
│   └── traces/
│       ├── task_001.json    # 任务 1 的执行 trace
│       ├── task_002.json    # 任务 2 的执行 trace
│       └── ...
├── harness_002/
│   ├── harness.py
│   ├── scores.json
│   └── traces/
│       └── ...
├── pareto_frontier.json     # 当前 Pareto 前沿
└── summary.txt              # 搜索进展概况
```

Proposer 通过标准终端工具访问：
- `cat harness_007/harness.py` — 查看特定候选源码
- `grep -r "retrieve" harness_*/harness.py` — 跨候选搜索特定模式
- `cat harness_007/scores.json` — 查看分数
- `cat harness_007/traces/task_042.json` — 查看特定任务的执行 trace

附录 D 的实践建议包括：
- **日志格式易于导航**：使用机器可读 JSON，层次化组织 artifacts，选择合理且一致的文件命名
- **可选但有用的小 CLI**：提供 Pareto 前沿列表、top-k harness diff、成对结果比较等快捷查询
- **轻量级验证先行**：写一个小的验证测试（import module + 小规模运行），在昂贵的完整评估前快速淘汰无效候选

### 3.4 Proposer 最常访问的信息（文件访问模式分析）

Table 8 提供了 TerminalBench-2 搜索运行（10 次迭代，Claude Opus 4.6）的统计：

| 统计项 | 值 |
|--------|-----|
| 每迭代读取文件数（中位数） | 82 |
| 每迭代读取文件数（范围） | 69-99 |
| **文件类型分布** | |
| Harness 源码 | 41% |
| 执行 trace | 40% |
| 分数/摘要文件 | 6% |
| 其他 | 13% |

关键观察：

1. **源码和 trace 几乎对半**。这说明 proposer 不仅看"做了什么"（源码），还看"发生了什么"（trace），两者缺一不可。

2. **访问模式是非马尔可夫的**。Proposer 不仅看最近的候选，而是自由选择回溯到任何历史版本。每步引用超过 20 个历史候选。这证明完整历史的保留是必要的。

3. **分数文件只占 6%**。分数本身信息量有限，真正的诊断信息在源码和 trace 中。

---

## 四、三个 Benchmark 的具体发现

### 4.1 文本分类：Draft Verification 策略与 Label-Primed Query

**实验设置**：在线文本分类——LLM 每次接收一个标注样本，更新内存，在 held-out 集上评估。使用 GPT-OSS-120B 作为分类器。三个数据集选择为高难度和领域多样性：LawBench（215 类犯罪案件描述）、Symptom2Disease（22 类症状）、USPTO-50k（180 类前体反应物分子）。

**发现的 Pareto 前沿**（Table 9）：

| 变体 | USPTO↑ | Symptom↑ | LawBench↑ | Avg↑ | Ctx↓ |
|------|--------|----------|-----------|------|------|
| Draft Verification | **18.0** | 85.4 | 17.0 | 40.1 | 5.4 |
| Error-Annotated | 9.0 | 87.7 | 24.0 | 40.2 | 22.3 |
| CoT Replay | 13.0 | 88.2 | 25.0 | 42.1 | 23.3 |
| Cluster Coverage | 12.0 | 86.8 | 33.0 | 43.9 | 31.2 |
| Cascade Retrieval | 12.0 | 86.8 | 36.0 | 44.9 | 39.2 |
| IRF + Contrastive | **18.0** | 89.6 | 35.0 | 47.5 | 41.4 |
| Relevance + Contrastive | **18.0** | 90.6 | 36.0 | 48.2 | 43.9 |
| **Label-Primed Query** | 14.0 | 86.8 | **45.0** | **48.6** | 45.5 |

**Draft Verification 策略完整描述**：

这是 Pareto 前沿中 token 成本最低的端点（仅 5.4K context），实现文件为 `draft_verification.py`：

- **Stage 1 — Draft**：检索 5 个最近邻标注样本，请求初始预测 D
- **Stage 2 — Verification**：基于 draft 标签 D 条件检索——检索 5 个"确认者"（同标签）和 5 个"挑战者"（不同标签），让模型决定是保持还是修正 D
- **Cold start**：如果已积累的标注样本 < 5，跳过两阶段过程，回退到标准 few-shot prompt
- **关键发现行为**：第二次检索依赖于 query 和 draft prediction 两者，因此 harness 可以精准定位针对模型当前猜测的反例

**Label-Primed Query 策略完整描述**（最高准确率端点，48.6%）：

实现文件为 `label_primed_query_anchored.py`，由三个组件构成：

- **Label Primer**：在展示任何示例之前，先明确列出所有合法输出标签，让模型看到完整的答案空间
- **Coverage Block**：对每个已知标签，用 TF-IDF 检索最相关的标注样本，每类一个代表性示例
- **Contrastive Pairs**：在 query 的局部邻域中，选择标签不同但内容高度相似的样本对，并排展示以暴露局部决策边界
- **检索规则**：使用 TF-IDF 相似度和 query-anchored 配对选择，而非与标签无关的最近邻

### 4.2 数学推理：4 路路由器的技术细节

**实验设置**：检索增强的奥林匹克数学题求解。检索语料库包含来自 8 个开源数据集的 535K 已解决问题（OpenMathReasoning 281K, DeepMath-103K 129K, NuminaMath-1.5 11K 等）。搜索集为 OlympiadBench + Omni-MATH (hard) 的 250 题子集，评估集为 200 道 IMO 级问题（来自 IMO-AnswerBench 100题, IMO-ProofBench 60题, ArXivMath 2025年12月 17题, ArXivMath 2026年1月 23题）。

**4 路路由器的完整实现**：

路由使用轻量级词法谓词（关键词集合 + 少量正则表达式），在问题文本上判断数学子领域：

**组合数学路由（Combinatorics）**：
- 获取 20 个 BM25 候选
- 去重至 8 个结果
- 按词法分数和难度重排序
- 返回 top 3
- 设计哲学：这是显式权衡多样性对抗困难问题匹配的路由

**几何路由（Geometry）**：
- 返回 1 个固定参考（NuminaMath 高难度题）+ 2 个原始 BM25 邻居
- 不做重排序——搜索发现原始匹配优于难度重排序
- 这条路由来自一条独立搜索路线，后被 proposer 自主合并到最终方案

**数论路由（Number Theory）**：
- 获取 12 个 BM25 候选
- 按词法分数、难度、和"技巧显性度"（proof strategy 是否在解答开头明确声明）重排序
- 返回 top 3
- 偏好解答中早期就声明证明技巧的示例

**默认路由（代数/其他）**：
- 获取 10 个 BM25 候选
- 按词法分数和难度重排序
- 基于 top 检索分数的集中度自适应选择返回数量
- 如果 top 分数差异大，返回更少但更确信的结果

**BM25 索引**使用保留 LaTeX token（如 `\frac`, `^{2}`）的数学感知分词器。最终 harness 是合并两条成功搜索路线的产物——一条贡献了更好的几何路由（基于 raw BM25），另一条贡献了更好的组合数学路由（基于去重 + 难度重排序）。

**跨模型迁移结果**（Table 6）：

| 方法 | GPT-5.4n | GPT-5.4m | Gem-3.1FL | Gem-3F | GPT-20B | Avg |
|------|----------|----------|-----------|--------|---------|-----|
| No Retriever | 23.0 | 28.8 | 28.6 | 42.6 | 47.6 | 34.1 |
| BM25 Retrieval | 31.7 | 30.4 | 34.9 | 46.6 | 50.6 | 38.8 |
| **Meta-Harness** | **31.7** | **30.4** | **34.9** | **46.6** | **50.6** | **38.8** |

Meta-Harness 发现的 harness 在所有 5 个未见过的模型上均匹配或超过 BM25 基线 1.3 分，同时避免了 dense retrieval 和 random few-shot 在某些模型上的回退现象。

### 4.3 TerminalBench-2：环境快照策略的实现

**实验设置**：TerminalBench-2 评估 89 个 Dockerized 长视野任务，涵盖代码翻译、ML 系统、生物信息学、密码分析等。初始化种群来自两个强基线：Terminus-2 和 Terminus-KIRA。

**`_gather_env_snapshot()` 的完整实现**：

在 agent loop 开始前执行一条复合 shell 命令（15 秒超时），收集：
- 工作目录路径
- `/app` 目录列表（截断至 20 条）
- 可用编程语言及版本（Python, GCC, G++, Node, Java, Rust, Go）
- 包管理器（pip, apt-get）
- 可用内存

注入为 `[Environment Snapshot]` 块到 initial prompt 中。实现约 80 行代码。超时静默失败，不会在异常环境中阻断 agent。

**搜索轨迹的因果推理过程**（Appendix A.2 完整记录）：

这是论文最精彩的部分——展示了 proposer 如何在失败中学习的完整叙事弧：

- **迭代 1-2**：将结构性修复与 prompt 模板修改捆绑，两个候选都从 64.4% 基线大幅回退
- **迭代 3（关键转折点）**：Proposer 识别混淆因子——"根本原因不是 bugfix 本身，而是 prompt 模板修改导致了回退。evo_strip_only 隔离了两个成功的结构性修复。"
- **迭代 4-6**：继续探索控制流修改，均回退。Proposer 积累了经验教训："prompt 和完成流的修改是高风险的"
- **迭代 7（获胜候选）**：策略转向纯加法修改——`evo_env_bootstrap` 在循环开始前注入环境快照，不修改任何现有方法。Proposer 明确写道："所有 6 次先前迭代的回退都是因为修改了完成流、prompt 模板或观测处理。evo_env_bootstrap 采用完全不同的方法——纯加法。"
- **迭代 8**：尝试组合环境快照 + 早期的 marker stripping 修复
- **迭代 10**：**跨 run 转移**——Proposer 引用了另一次独立搜索运行的结果

**逐任务分析**：相对 Terminus-KIRA，改进最大的 7/89 个任务（如 `protein-assembly`, `path-tracing`）有共同特征：需要环境特定工具（生物信息学库、渲染管线、国际象棋引擎、CoreWars 模拟器等），这些工具的存在性在环境快照前需要 2-4 轮试探才能确认。

**TerminalBench-2 排名**（Table 7）：

| Harness | Auto | Pass (%) |
|---------|------|----------|
| **Claude Opus 4.6** | | |
| Claude Code | × | 58.0 |
| Terminus 2 | × | 62.9 |
| Mux | × | 66.5 |
| Droid | × | 69.9 |
| TongAgents | × | 71.9 |
| MAYA-V2 | × | 72.1 |
| Terminus-KIRA | × | 74.7 |
| Cappy | × | 75.3 |
| ForgeCode | × | 81.8 |
| **Meta-Harness** | **✓** | **76.4** |
| **Claude Haiku 4.5** | | |
| OpenHands | × | 13.9 |
| Claude Code | × | 27.5 |
| Terminus 2 | × | 28.3 |
| Mini-SWE-Agent | × | 29.8 |
| Terminus-KIRA | × | 33.7 |
| Goose | × | 35.5 |
| **Meta-Harness** | **✓** | **37.6** |

Meta-Harness 在 Opus 4.6 上排名 #2（仅次于 ForgeCode 的 81.8%，但 ForgeCode 的代码未开源），在 Haiku 4.5 上排名 **#1**。

---

## 五、Harness 生命周期管理

### 5.1 发现的 Harness 规模

根据论文描述，发现的 harness 在 **100-1000 行可读 Python 代码**范围内。按 benchmark 分：

- **文本分类 harness**：较小端，约 100-300 行。Draft Verification 是两次 LLM 调用 + 检索逻辑；Label-Primed Query 是单次调用 + 三段式 context 构造
- **数学检索 harness**：中等，约 300-500 行。4 路路由器 + BM25 索引构建 + 去重/重排序逻辑
- **TerminalBench-2 harness**：最大端，基于 Terminus-KIRA 修改，约 500-1000 行。包含完整的 agent loop、工具调用、完成检查、环境快照

### 5.2 跨模型迁移性

论文在两个 benchmark 上验证了迁移性：

**文本分类 OOD 泛化**（Table 5）：在 9 个从未见过的数据集上，Meta-Harness 达到 73.1% 平均准确率，超过 ACE 基线（70.2%）2.9 个百分点。这说明发现的策略（Draft Verification、Contrastive Pairs 等）不是过拟合到搜索数据集的特定类别，而是捕捉了一般性有效的上下文构造模式。

**数学推理跨模型**（Table 6）：在搜索模型 GPT-OSS-120B 上发现的检索 harness，直接迁移到 5 个未见过的模型（GPT-5.4-nano, GPT-5.4-mini, Gemini-3.1-Flash-Lite, Gemini-3-Flash, GPT-OSS-20B），平均提升 4.7 分。这证明了 code-space 搜索的关键优势：发现的策略是"算法级别"的，不依赖特定模型的怪癖。

### 5.3 可解释性和可维护性

Code-space 搜索相比 weight-space 优化的一个重要优势是**可解释性**。论文明确指出：

> "Overfitting in code space is also more inspectable: brittle if-chains or hard-coded class mappings are visible on inspection in a way that weight-space overfitting is not."

发现的 harness 是标准 Python 代码，可以被人类工程师阅读、理解、修改。例如 4 路数学路由器的路由规则、Draft Verification 的两阶段流程、环境快照的 shell 命令——这些都是工程师可以直接审计和调整的。

---

## 六、与 Doramagic 的深度对应分析

### 6.1 对应关系总览

Meta-Harness 的核心洞察与 Doramagic 的蓝图提取 Agent 存在深层对应关系：

| Meta-Harness 概念 | Doramagic 当前实现 | 对应深度 |
|-------------------|-------------------|---------|
| Harness（控制 LLM 看到什么） | 蓝图提取 Pipeline（17-Phase → v6 改版） | 架构级对应 |
| Agentic proposer | 无（Pipeline 是固定的，不自动优化） | 缺失 |
| Filesystem 存 trace | `_save_trace()` 已实现（v5.2 commit 9cc4fdf） | 已部分实现 |
| 消融实验 | Enrich Patch 无 A/B 追踪 | 缺失 |
| 环境快照预热 | v6 worker_resource 可反向注入 | 设计已有，未实现 |
| Code-space 搜索 | 16 个 Enrich Patch 是 Python 函数 | 天然基础 |
| Pareto 前沿 | 无（只输出单一蓝图） | 缺失 |
| Draft Verification 两阶段 | v6 Evaluator Phase | 设计对应 |
| 最小化外层结构 | v5.2 的 17-Phase 是高度结构化的 | 设计冲突 |

### 6.2 结合点 1：Trace 存档与诊断闭环

**Meta-Harness 的做法**：每个候选 harness 的源码 + 评估分数 + 完整执行 trace 存入文件系统，proposer 通过 grep/cat 按需查阅。

**Doramagic 当前状态**：`_save_trace()` 已实现，保存到 `_runs/{bp_id}/traces/`，包含 prompt、raw output、解析错误、L3 recovery 结果。

**差距分析**：当前 trace 存档是**被动的**——存了但没有消费者。Meta-Harness 的核心价值不是存档本身，而是有一个 agent（proposer）主动查询历史 trace 来诊断问题。

**改进方案**：

```python
# 新增：TraceAnalyzer — 在 batch 提取中跨蓝图分析失败模式
class TraceAnalyzer:
    """消费 _runs/{bp_id}/traces/ 中的历史 trace，
    识别系统性失败模式，为 Pipeline 调优提供诊断信息。
    
    对应 Meta-Harness 的 proposer 诊断行为。
    """
    
    def __init__(self, runs_dir: Path):
        self.runs_dir = runs_dir
    
    def diagnose_phase_failures(self, phase_name: str) -> dict:
        """跨蓝图聚合某个 Phase 的失败模式。
        
        返回:
        {
            "total_runs": 59,
            "failure_rate": 0.34,
            "top_failure_patterns": [
                {
                    "pattern": "evidence_format_mismatch",
                    "count": 12,
                    "example_bp_ids": ["bp-003", "bp-017"],
                    "common_trigger": "LLM 输出 'file.py line 42' 而非 'file.py:42(fn)'"
                },
                ...
            ],
            "recommendation": "在 Worker prompt 中显式展示 evidence 格式的正/反例"
        }
        """
        traces = self._load_traces_for_phase(phase_name)
        patterns = self._cluster_failure_modes(traces)
        return self._generate_recommendations(patterns)
    
    def patch_effectiveness_report(self) -> dict:
        """分析 16 个 Enrich Patch 的实际效果。
        
        对应 Meta-Harness 消融实验：
        - 每个 patch 触发了多少次修复？
        - 修复后 QG 通过率变化？
        - 有没有 patch 引入了回退？
        """
        patch_stats = {}
        for bp_dir in self.runs_dir.iterdir():
            enrich_meta = self._load_enrich_meta(bp_dir)
            for patch_name, stats in enrich_meta.items():
                patch_stats.setdefault(patch_name, []).append(stats)
        return self._aggregate_patch_effectiveness(patch_stats)
```

**预期收益**：
- 识别出哪些 Enrich Patch 是"纯噪声"（触发但不改善质量），可以安全移除
- 发现 Worker prompt 中导致系统性失败的措辞，实现精准调优
- 为跨蓝图 batch 提取建立"经验库"，后续提取可以借鉴

**实施成本**：中等。核心是 trace 格式标准化 + 聚类分析逻辑，不涉及流水线架构变更。预计 2-3 天。

### 6.3 结合点 2：Enrich Patch 消融体系

**Meta-Harness 的做法**：Table 3 的消融实验证明了"哪些信息通道真正有用"。关键方法论是严格控制变量——每次只改变一个条件。

**Doramagic 当前状态**：16 个 Enrich Patch（P0-P14 + P5.5）是手工设计的，按固定顺序执行。没有任何机制知道：
- P6（vague_words 标记）对最终晶体质量有多大贡献？
- P7（stage_id_validation）修复了多少蓝图？在新的 v6 Evaluator 存在后是否冗余？
- P4（bd_type_enum_fix）处理的那些映射规则是否都被触发过？

**改进方案**：

```python
# blueprint_enrich.py — 每个 patch 函数增加 trace 输出

def run_enrich_pipeline(bp: dict, state: AgentState) -> tuple[dict, dict]:
    """执行所有 Enrich Patch，返回 (enriched_bp, patch_trace)。
    
    patch_trace 记录每个 patch 的修改详情，用于后续消融分析。
    """
    patch_trace = {}
    
    patches = [
        ("P0_id", _patch_id),
        ("P1_commit_hash", _patch_commit_hash),
        ("P2_sop_version", _patch_sop_version),
        ("P3_bd_injection", _patch_bd_injection),
        ("P4_bd_type_enum_fix", _patch_bd_type_enum_fix),
        ("P5_evidence_format", _patch_evidence_format),
        ("P5.5_evidence_verify", patch_p5_5_verify_evidence),
        ("P6_vague_words", _patch_vague_words),
        ("P7_stage_id_validation", _patch_stage_id_validation),
        ("P8_required_methods", _patch_required_methods),
        ("P9_uc_merge", _patch_uc_merge),
        ("P10_uc_normalize", _patch_uc_normalize),
        ("P11_audit_checklist", _patch_audit_checklist),
        ("P12_relations", _patch_relations),
        ("P13_execution_paradigm", _patch_execution_paradigm),
        ("P14_resource_injection", _patch_resource_injection),
    ]
    
    bp_before = deep_copy(bp)
    for name, patch_fn in patches:
        changes = patch_fn(bp, state)  # 返回修改数量
        # 记录 diff
        patch_trace[name] = {
            "changes_count": changes,
            "fields_modified": _diff_keys(bp_before, bp),
            "timestamp": now_iso(),
        }
        bp_before = deep_copy(bp)
    
    return bp, patch_trace


# 消融分析器
class PatchAblationAnalyzer:
    """跨 N 次提取，分析每个 Patch 的实际贡献。
    
    对应 Meta-Harness Table 3 方法论：
    - 控制变量：每次禁用一个 patch，比较 QG 分数变化
    - 信息增益：patch 修改量 vs 最终质量提升的相关性
    """
    
    def analyze(self, traces: list[dict]) -> dict:
        """
        输出示例:
        {
            "P4_bd_type_enum_fix": {
                "trigger_rate": 0.73,       # 73% 的蓝图触发了此 patch
                "avg_changes": 2.1,         # 平均修改 2.1 个 BD
                "quality_correlation": 0.45, # 与 QG 通过率的相关系数
                "verdict": "KEEP"           # KEEP / MERGE / REMOVE
            },
            "P6_vague_words": {
                "trigger_rate": 0.12,
                "avg_changes": 0.3,
                "quality_correlation": 0.02,
                "verdict": "REMOVE — 低触发率，与质量无相关性"
            },
            ...
        }
        """
        pass
```

**预期收益**：
- 精简 Enrich Pipeline——如果 P6 确实不贡献质量，移除它可以减少代码维护负担和潜在的误修改风险
- 发现 patch 间的交互效应——某些 patch 组合可能比单独应用更有效或有害
- 为 v6 的 Evaluator Phase 和 Enrich 划清边界——Evaluator 覆盖了的语义检查不需要 Enrich 重复

**实施成本**：低-中。主要是 trace 记录（patch 函数已经返回修改数量）+ 分析脚本。预计 1-2 天。

### 6.4 结合点 3：环境快照预热

**Meta-Harness 的做法**：TerminalBench-2 最佳 harness 在 agent loop 前注入 `_gather_env_snapshot()`——收集 OS、语言版本、包清单、可用内存等，节省 2-4 轮无效探索。

**Doramagic 当前状态**：v6 设计了 `worker_resource`（资源专属 Worker），但它是与其他 Worker 并行执行的独立阶段，结果在 Synthesis 阶段才被消费。Worker 之间没有"快照预热"——每个 Worker 独立探索仓库，没有共享的初始认知。

**改进方案**：

```python
# 新增 Phase：repo_snapshot — 在所有 Worker 启动前执行
# 对应 Meta-Harness 的 _gather_env_snapshot()

REPO_SNAPSHOT_TEMPLATE = """
## 仓库快照（自动生成，{timestamp}）

### 基本信息
- 语言: {language}
- 框架: {framework} v{version}
- 包管理: {pkg_manager}
- 总文件数: {total_files}
- Python 文件数: {py_files}
- 测试文件数: {test_files}

### 目录结构（depth=2）
{directory_tree}

### 关键文件
- 入口点: {entry_points}
- 配置文件: {config_files}
- 示例/教程: {examples}

### 已知框架特征
{framework_fingerprint}
"""

def generate_repo_snapshot(repo_path: str) -> str:
    """确定性的仓库特征采集——零 LLM 调用。
    
    类比 Meta-Harness _gather_env_snapshot():
    - 15 秒超时（大仓库截断）
    - 静默失败（不阻断后续 Worker）
    - 输出注入到每个 Worker 的 system prompt 前缀
    """
    snapshot = {}
    
    # 1. 语言和框架检测（确定性）
    snapshot["language"] = detect_language(repo_path)  # pyproject.toml / setup.py
    snapshot["framework"] = detect_framework(repo_path)  # 特征文件匹配
    snapshot["pkg_manager"] = detect_pkg_manager(repo_path)
    
    # 2. 文件统计
    snapshot["total_files"] = count_files(repo_path)
    snapshot["py_files"] = count_files(repo_path, "*.py")
    snapshot["test_files"] = count_files(repo_path, "test_*.py")
    
    # 3. 目录树（截断）
    snapshot["directory_tree"] = dir_tree(repo_path, depth=2, max_entries=30)
    
    # 4. 关键文件定位
    snapshot["entry_points"] = find_entry_points(repo_path)
    snapshot["config_files"] = find_config_files(repo_path)
    snapshot["examples"] = find_examples(repo_path)
    
    # 5. 框架指纹（已知模式库匹配）
    snapshot["framework_fingerprint"] = match_known_patterns(repo_path)
    
    return REPO_SNAPSHOT_TEMPLATE.format(**snapshot)
```

在 Worker 启动时注入：

```python
# blueprint_phases.py — 修改 Worker Phase 的 system prompt 构造

def build_worker_prompt(phase: Phase, state: AgentState) -> str:
    repo_snapshot = state.get_artifact("repo_snapshot.txt")
    
    # 快照作为 system prompt 前缀，在 Worker 专属指令之前
    return f"""
{repo_snapshot}

---

{phase.system_prompt}
"""
```

**预期收益**：
- 减少每个 Worker 的探索性工具调用——当前 `worker_arch` 经常前 3-5 次迭代在 `list_dir` 和 `read_file` 中探索仓库结构
- 节省 15-25% Worker 阶段 token（5 个 Worker × 3-5 轮探索节省 × 每轮约 2K token）
- 与 v6 的 Convergence Detector 协同——更快启动有效提取意味着更多迭代用于深度分析

**实施成本**：低。纯 Python 文件操作，不涉及 LLM。预计 1 天。

### 6.5 结合点 4：Draft-Verification 两阶段验证

**Meta-Harness 的做法**：Draft Verification harness 先做初始预测（Draft），再用条件检索的正/反例来验证或修正（Verification）。

**Doramagic 对应**：v6 的 Evaluator Phase 已经实现了类似设计——Worker 提取 BD（Draft），Evaluator 独立验证（Verification）。但有一个关键差异：

- **Meta-Harness**：Verification 基于 Draft 的内容做条件检索（"给我这个标签的确认者和挑战者"）
- **Doramagic v6**：Evaluator 独立读取源码验证 evidence，但不会基于 BD 的内容做"条件搜索"

**改进方案——Evidence-Conditioned Verification**：

```python
# 在 Evaluator 中增加条件搜索能力

EVALUATOR_SYSTEM_V2 = """
...（原有合同 1-4）

### 合同 5：Evidence-Conditioned 反事实搜索（新增）

对每条非 T 决策，在源码中搜索"挑战者证据"：
1. 读取 BD 的 evidence（确认者）
2. 在同文件或相关文件中，搜索与 BD 声明**相矛盾**的代码模式
   - B 类：搜索是否有条件分支处理了 BD 声称的"唯一方案"之外的替代方案
   - BA 类：搜索是否有配置项允许用户覆盖 BD 声称的"硬编码假设"
   - RC 类：搜索是否有注释标注这是"可选的"而非"强制的"
3. 如果找到挑战者证据：
   - 标记为 CHALLENGED
   - 记录挑战者证据的 file:line(fn)
   - 建议修正 BD 的 type 或 rationale

这一步骤的核心价值：让验证不仅检查"BD 说的对不对"，
还主动搜索"BD 可能遗漏了什么"。
"""
```

**预期收益**：
- 提高 BD 分类精度——发现被错误标记为 B 的实际上是 T 的决策（因为存在未被注意的替代分支）
- 减少 missing gap——挑战者搜索可能发现 BD 列表未覆盖的业务逻辑
- Evidence 覆盖率提升——每条 BD 不仅有支持证据，还有（可选的）挑战证据

**实施成本**：中。需要修改 Evaluator prompt + 增加 challenger_evidence 字段到输出 schema。预计 2 天。

### 6.6 结合点 5：Code-Space 搜索——Enrich Patch 作为可搜索空间

**Meta-Harness 的长期启示**：搜索的不是 prompt 字符串，而是可执行 Python 程序。harness 作为搜索空间，天然具备组合表达力和正则化。

**Doramagic 的天然基础**：16 个 Enrich Patch 已经是 Python 函数——每个 patch 是一个 `(bp: dict, state: AgentState) -> int` 签名的纯函数。这本身就是一个 code-space 搜索的种子。

**长期演进方向**：

```
Phase 1（当前可做）：Patch 消融——识别哪些 patch 有效
Phase 2（中期）：Patch 参数搜索——某些 patch 有隐式参数
    例如 P6 的 vague_words 列表、P7 的 STAGE_MAPPING 表
    这些参数可以基于历史 trace 自动调优
Phase 3（长期）：Patch 生成——基于历史 trace 中的失败模式，
    用 coding agent 自动提出新的 patch
    类比 Meta-Harness proposer 生成新 harness
```

Phase 3 的示意架构：

```python
# 概念性设计——Patch Proposer

class PatchProposer:
    """从历史 trace 中自动发现新的 Enrich Patch。
    
    对应 Meta-Harness 的 agentic proposer：
    - 输入：所有历史蓝图的提取 trace + QG 分数 + 晶体质量评估
    - 输出：新的 Python patch 函数
    - 验证：在 held-out 蓝图上评估 QG 分数变化
    """
    
    def propose(self, trace_dir: Path) -> str:
        """
        步骤 1：加载历史 trace，聚类失败模式
        步骤 2：识别 QG 失败率最高的检查项
        步骤 3：分析失败的蓝图，找到共同的数据模式
        步骤 4：生成 patch 代码（coding agent）
        步骤 5：在 3 个 held-out 蓝图上验证
        """
        # 这需要 coding agent 能力（Claude Code）
        # 目前不实现，记录为长期方向
        pass
```

**预期收益**：使 Enrich Pipeline 从"手工设计"演进为"数据驱动的自动发现"。

**实施成本**：Phase 1 低（1-2天）、Phase 2 中（3-5天）、Phase 3 高（需要专门的 coding agent 集成，2-3 周）。

### 6.7 结合点 6：Pareto 前沿思维

**Meta-Harness 的做法**：返回准确率 vs token 成本的 Pareto 前沿，而非单一最优解。文本分类中发现了 7 个 Pareto 最优变体，从 Draft Verification（40.1% acc, 5.4K ctx）到 Label-Primed Query（48.6% acc, 45.5K ctx）。

**Doramagic 的对应需求**：蓝图提取存在"速度 vs 完整度"的权衡——
- 快速模式：跳过 deep_arch Worker、简化 Evaluator → 适合初次探索
- 完整模式：全部 Worker + 严格 Evaluator + 审计闭环 → 适合生产蓝图

**改进方案**：

```python
# 配置预设——对应 Meta-Harness Pareto 前沿的不同操作点

EXTRACTION_PRESETS = {
    "scout": {
        # Pareto 前沿低成本端——快速探索，判断仓库是否值得提取
        "workers": ["worker_docs", "worker_arch"],  # 只用 2 个 Worker
        "evaluator": False,
        "audit": False,
        "strict_qg": False,
        "estimated_tokens": "~50K",
        "estimated_time": "~3 min",
    },
    "standard": {
        # Pareto 前沿中间——日常生产使用
        "workers": ["worker_docs", "worker_arch", "worker_workflow",
                     "worker_math", "worker_resource"],
        "evaluator": True,
        "audit": True,
        "strict_qg": True,
        "estimated_tokens": "~200K",
        "estimated_time": "~15 min",
    },
    "thorough": {
        # Pareto 前沿高质量端——关键蓝图的深度提取
        "workers": ["worker_docs", "worker_arch", "worker_arch_deep",
                     "worker_workflow", "worker_math", "worker_resource"],
        "evaluator": True,  # 含 evidence-conditioned 挑战者搜索
        "audit": True,
        "strict_qg": True,
        "multi_pass": True,  # Evaluator 发现 FIXABLE 后自动修复并重评
        "estimated_tokens": "~400K",
        "estimated_time": "~30 min",
    },
}
```

**预期收益**：
- Batch 提取 59 个蓝图时，先用 scout 模式快速筛选，再对高价值蓝图用 thorough 模式
- 节省总体 token 开支约 40-60%（大量简单蓝图不需要完整流水线）

**实施成本**：低。主要是配置管理，Pipeline 已有条件执行能力。预计 1 天。

### 6.8 结合点 7：最小化外层结构 vs Doramagic 的高结构化

**Meta-Harness 的哲学**：外层循环故意最小化——不限定 parent selection，不规定修改粒度，不硬编码搜索启发式。理由是避免"结构限制了搜索"。

**Doramagic 的现实**：v5.2 的 17-Phase Pipeline 和 v6 的改版都是高度结构化的——Phase 定义、depends_on 链、blocking 标记、required_artifacts。这种结构化是有道理的：蓝图提取是一个有明确 SOP 的任务，不像 Meta-Harness 那样在开放空间搜索。

**辩证分析**：

Meta-Harness 的"最小化外层结构"适用于**搜索自动化**场景——你不知道最优策略是什么，需要 agent 自由探索。但 Doramagic 的蓝图提取是**执行标准化**场景——SOP v3.4 定义了明确的流程，结构化保证了可重复性和质量底线。

正确的借鉴不是"去掉结构"，而是**区分探索模式和生产模式**：

```python
# 两种模式的配置差异

PRODUCTION_MODE = {
    "strict_qg": True,
    "phase_order": "fixed",       # 固定顺序，保证可重复性
    "evaluator": "strict",        # 所有合同都检查
    "trace_logging": "minimal",   # 只记录异常
}

EXPLORATION_MODE = {
    "strict_qg": False,
    "phase_order": "adaptive",    # 基于中间结果动态调整
    "evaluator": "lenient",       # 只检查合同 1 和 2
    "trace_logging": "full",      # 完整 trace，用于后续分析
    # 允许跳过某些 Phase（如审计）来节省 token
    # 允许 Worker 间共享中间发现（打破 depends_on 隔离）
}
```

**预期收益**：探索模式用于新领域（如 Doramagic 从 finance 扩展到新领域时），可以更快地迭代；生产模式用于已验证的领域，保证质量底线。

**实施成本**：中。需要 Pipeline 支持条件执行和模式切换。预计 2-3 天。

---

## 七、综合实施路线图

### 优先级矩阵

| 改进项 | 对应论文发现 | 当前状态 | 难度 | 预期收益 | 优先级 |
|--------|------------|---------|------|---------|--------|
| Patch 消融追踪 | Table 3 消融方法论 | 未实现 | 低 | 识别无效 Patch，精简流水线 | **P1** |
| 仓库快照预热 | _gather_env_snapshot | 设计已有 | 低 | 节省 15-25% Worker token | **P1** |
| Pareto 提取预设 | Pareto 前沿 | 未实现 | 低 | 节省 40-60% batch token | **P1** |
| Trace 诊断分析器 | Proposer 诊断行为 | trace 存档已有 | 中 | 系统性改善 Pipeline | **P2** |
| Evidence-Conditioned 验证 | Draft Verification | v6 Evaluator 设计中 | 中 | 提高 BD 分类精度 | **P2** |
| 探索/生产双模式 | 最小化外层结构 | 未实现 | 中 | 新领域扩展加速 | **P2** |
| Patch 参数搜索 | Code-space 搜索 | 天然基础 | 中-高 | Patch 自动调优 | **P3** |
| Patch 自动生成 | Agentic proposer | 概念阶段 | 高 | 自动发现新 Patch | **P3** |

### 实施顺序建议

**Sprint 1（本周可做，3 天）**：P1 三项
- Day 1：仓库快照预热（generate_repo_snapshot + Worker prompt 注入）
- Day 2：Patch 消融追踪（patch_trace 记录 + PatchAblationAnalyzer）
- Day 3：Pareto 提取预设（EXTRACTION_PRESETS 配置 + batch orchestrator 集成）

**Sprint 2（下周，5 天）**：P2 三项
- Day 1-2：Trace 诊断分析器（TraceAnalyzer + 失败模式聚类）
- Day 3-4：Evidence-Conditioned 验证（Evaluator prompt v2 + challenger_evidence 输出）
- Day 5：探索/生产双模式（Pipeline 条件执行 + 模式切换）

**Sprint 3（长期规划）**：P3 两项
- Patch 参数搜索：在积累了足够 trace 数据后再启动
- Patch 自动生成：等 coding agent 能力进一步成熟后探索

---

## 八、关键引用与参考

### 论文核心引用

- **Harness 定义**："the code that determines what information to store, retrieve, and present to the model"（Abstract）
- **6x 性能差距**："Changing the harness around a fixed large language model (LLM) can produce a 6x performance gap on the same benchmark"（Section 1, citing Boluk [10]）
- **压缩反馈失败**："summaries do not recover the missing signal, and may even hurt by compressing away diagnostically useful details"（Section 4.1）
- **摘要比分数还差**："scores-plus-summary reaches 34.9 median and 38.7 best, while the full Meta-Harness interface reaches 50.0 median and 56.7 best"（Table 3）
- **82 files/iteration**："the proposer reads a median of 82 files per iteration"（Appendix A.1, Table 8）
- **自然正则化**："coding models tend to propose coherent algorithms rather than brittle, hard-coded solutions"（Section 3）
- **10x 更快收敛**："Meta-Harness matches the best prior text optimizers (OpenEvolve, TTT-Discover) with 10x fewer full evaluations"（Section 4.1, highlighted box）

### 相关工作

| 方法 | 年份 | 与 Meta-Harness 的关键差异 |
|------|------|--------------------------|
| OPRO (Yang et al.) | 2023 | 无记忆，只用 (solution, score) 对 |
| TextGrad (Yuksekgonul et al.) | 2024 | 只看当前候选的文本反馈 |
| DSPy (Khattab et al.) | 2023 | 搜索声明式管线而非任意代码 |
| AlphaEvolve (Novikov et al.) | 2025 | LLM 引导变异，但目标是单个无状态函数 |
| OpenEvolve (Sharma) | 2025 | 类似 AlphaEvolve，开源实现 |
| TTT-Discover (Yuksekgonul et al.) | 2026 | PUCT 复用规则，但窗口式历史 |
| GEPA (Agrawal et al.) | 2025 | 回放轨迹反射，但格式化为固定 critique |
| Feedback Descent (Lee et al.) | 2025 | 成对比较，但限于摘要级反馈 |
| ACE (Zhang et al.) | 2025 | 手工设计的上下文工程系统，非自动搜索 |

### 实践建议（Appendix D 原文要点）

1. **写好 skill 文本**。Skill 质量对搜索效果的影响大于迭代次数或种群大小。先跑 3-5 次短进化（3-5 迭代），专门调试 skill 文本。
2. **从强基线出发**。写一个简单基线（如 few-shot prompting），构造搜索集时筛选基线做错或困难的实例。
3. **日志格式易于导航**。用 JSON，层次化组织，一致的命名。
4. **轻量级验证先行**。在昂贵评估前先跑 import + 小规模测试。
5. **评估在 proposer 外部运行**。不值得让 proposer 自己做评估——让独立的 harness 负责打分并写入文件系统。

---

*最后更新: 2026-04-14*
*研究者: Claude Opus 4.6*
*字数统计: ~8,500 字*
