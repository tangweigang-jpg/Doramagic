# Meta-Harness 研究报告：对 Doramagic 蓝图提取 Agent 的启示

> 论文：Meta-Harness: End-to-End Optimization of Model Harnesses
> 作者：Yoonho Lee, Roshen Nair, Qizheng Zhang, Kangwook Lee, Omar Khattab, Chelsea Finn
> 发表：2026-03-30, arxiv 2603.28052
> 研究日期：2026-04-14

---

## 一、论文摘要

Meta-Harness 解决的核心问题是：LLM 系统性能高度依赖 harness（控制信息如何流入模型的代码），但 harness 工程化长期靠人工。现有文本优化器（OPRO、TextGrad）的根本缺陷是"压缩反馈"——只看标量分数或摘要，丢失了跨多步推理链的因果信息。Meta-Harness 用一个 agentic proposer（Claude Code Opus 4.6）访问完整 filesystem：所有历史 harness 源码 + 执行 trace + 分数，每次迭代消耗约 10M tokens 诊断信息（比 OPRO 多三个数量级）。结果：文本分类 56.7% best accuracy（比 SOTA 高 10+ 点），IMO 级数学推理提升 4.7 points，TerminalBench-2 排名第二。

---

## 二、核心技术详解

### 2.1 关键诊断：为什么压缩反馈失败

Meta-Harness 最重要的洞察是消融实验（Table 3）的结论：

| 反馈类型 | 最佳准确率 |
|---------|-----------|
| 仅分数（scores-only）| 41.3% |
| 分数 + LLM 摘要 | 38.7%（甚至更差！）|
| 完整接口（raw traces + code）| 56.7% |

摘要比纯分数还差，证明 LLM 生成的摘要会引入信息损失。根本原因：harness 操作于长视野，一个早期决策（存什么、何时检索、如何呈现）可能在很多推理步骤后才显现影响。压缩掉中间 trace 就切断了因果链。

### 2.2 Agentic Proposer 机制

- 每次迭代，proposer 中位数读取 82 个文件（41% 源码，40% traces）
- 访问模式是非马尔可夫的——proposer 自由选择检查哪个历史版本
- 外层 loop 刻意最小化：不硬编码搜索启发式，不规定 parent selection，让 proposer 自主诊断
- 修改粒度从"局部编辑"到"全程序重写"

### 2.3 为什么 code-space 搜索天然泛化

编程模型倾向于提出"连贯算法"而非"硬编码解"——这是一种自然正则化。发现的 harness 是 100-1000 行可读 Python，可在未来更强的模型上复用。

### 2.4 发现的最优 Harness 示例

- **文本分类 Draft Verification 策略**：先草稿预测，再检索确认者/挑战者，用 5.4K tokens 达到接近最优
- **数学检索路由器**：自动发现 4 路词法路由（组合数学/几何/数论/默认），每路独立 BM25 + rerank
- **TerminalBench-2**：在 agent loop 前注入 OS/语言/包版本快照，节省 3-5 轮无效探索

---

## 三、与 Doramagic 蓝图提取 Agent 的结合点

### 结合点 1：执行 trace 存档（已实现 `9cc4fdf`）

**当前问题**：MiniMax L2 验证经常失败，靠 L3 recovery 兜底，但无法系统性改善。

**Meta-Harness 的答案**：失败原因不在当次输出，而在哪个 prompt 设计导致了这种失败模式。解决方案是构建执行 trace 存档：每次 L2 失败时，保存完整的 prompt + raw output + 解析错误 + L3 recovery 结果到文件系统。

**落地状态**：已实现（`_save_trace()` 方法），保存到 `_runs/{bp_id}/traces/` 目录。

### 结合点 2：Enrich Patch 消融（未实现）

**当前问题**：18 个 Enrich Patch 是手工设计的，不知道哪些真正有效、哪些多余甚至有干扰。

**Meta-Harness 的答案**：对 18 个 Enrich Patch，建立 A/B 追踪——每次提取时记录哪些 patch 生效、对最终蓝图质量（BD 数量、evidence 验证率、QG 通过率）的贡献。用消融实验方法识别哪些 patch 可以去掉或合并。

### 结合点 3：环境快照预热（未实现）

**Meta-Harness 发现**：TerminalBench-2 最佳 harness 在 agent loop 前注入环境快照（OS、语言版本、包清单），节省 3-5 轮无效探索。

**对应 Doramagic**：在 8 个 Worker 并行启动前，注入"已知框架特征快照"（框架语言、主要模块、典型文件结构、已知坑），让每个 Worker 不从零开始探索。v6 的 `worker_resource` 提取的资源信息可以反向注入到后续 Worker 的上下文中。

### 结合点 4：Code-Space 搜索（长期方向）

**最重要的模式**：Meta-Harness 搜索的不是 prompt 字符串，而是可执行的 Python 程序（harness 代码）。这让改变具有"算法语义"而非"文本语义"，天然避免 prompt 优化中的过拟合。

**对 Doramagic 的长期启示**：18 个 Enrich Patch 目前是手工 Python 函数，这本身就是 code-space 设计。未来可以把 patch 设计本身作为搜索空间——用 agentic proposer 在已有蓝图 + 历史 trace 上自动发现新的 patch 类型。

---

## 四、值得借鉴的设计模式

### 模式 1：最小化外层结构，最大化 proposer 自主性

Meta-Harness 的外层 loop 故意不加约束：不限定如何选择父代，不规定修改粒度。

**建议**：区分"探索模式"（关闭 strict QG，记录更多 trace）和"生产模式"（开启 strict QG）。

### 模式 2：环境快照预热

在 agent loop 前注入环境快照节省 3-5 轮探索。

**对应**：Worker 启动前注入"已知框架特征快照"。

### 模式 3：Pareto 前沿思维

Meta-Harness 返回 Pareto 前沿（准确率 vs. token 成本），而非单一最优解。

**对应**：蓝图提取存在"速度 vs. 完整度"权衡，建立 Pareto 追踪——给出"精简版"和"完整版"两个配置。

### 模式 4：Code-Space 而非 Prompt-Space 搜索

搜索可执行的 Python 程序而非 prompt 字符串，天然避免过拟合。

**对应**：Enrich Patch 体系已经是 code-space 设计，未来可扩展为可搜索空间。

---

## 五、实施优先级

| 建议 | 状态 | 难度 | 优先级 |
|------|------|------|--------|
| 执行 trace 存档 | **已实现** | 低 | P0 ✅ |
| Enrich Patch 消融 | 未实现 | 中 | P2 |
| 环境快照预热 | 未实现 | 中 | P2 |
| Code-Space 搜索 | 未实现 | 高 | P3 |

---

*最后更新: 2026-04-14*
