# 提取质量深度研究报告

> 日期：2026-04-10
> 目的：系统性研究如何提高自主提取 Agent 的知识提取质量
> 公式：好的晶体 = 好的蓝图（包含业务逻辑）+ 好的资源 + 好的约束

---

## Top 5 应采用的技术（按 Impact/Effort 排序）

### 1. 预提取结构索引（Impact 9/10, Effort Easy）

在 agentic 探索之前，用纯 Python 预构建：
- **AST 骨架索引**：每个 .py 文件的 class/method 签名、docstring、import
- **依赖图**：谁 import 谁，谁调用谁
- **仓库概览**：文件分类（config/model/util/test/example）

**依据**：Agentless（ICLR 2025）证明骨架表示大幅提升定位准确率。ArchAgent（2026）的 File Summarizer 做的就是这个。当前 agent 浪费大量迭代在目录导航上。

### 2. 源码证据锚定验证（Impact 8/10, Effort Easy-Medium）

每个提取元素必须锚定到具体源码：
- 每个 stage 至少引用一个文件
- 每个 BD 必须有 file:line 证据
- 每个约束必须追溯到代码或文档

**依据**：PARSE（EMNLP 2025, Amazon）通过三阶段验证（缺失检查 + 锚定验证 + 规则合规）实现 92% 错误减少。

### 3. 多源知识挖掘（Impact 8/10, Effort Medium）

扩展提取范围到非代码制品：
- README/docs（架构意图）
- CHANGELOG（演进历史）
- GitHub Issues（bug + 设计讨论 → 运维经验）
- PR 描述（设计理由）
- Commit messages（CoMRAT 风格理由检测）

**依据**：CoMRAT（MSR 2025）证明 commit message 中含丰富设计理由。当前 agent 只读源码，错过大量业务逻辑和经验知识。

### 4. 专家代理分解（Impact 7/10, Effort Medium）

拆分为专项代理并行执行：
- 架构专家：阶段、接口、数据流
- 量化专家：数学模型、数值方法、算法
- 合规专家：监管规则、领域约束
- 经验专家：Issues、PR、运维教训

**依据**：SWE Atlas 发现即使 80% 模型在深层代码理解上只有 35%，瓶颈是有限 context 内的注意力分配。专家代理各有完整 context。

### 5. 渐进提取 + 完整性评分（Impact 7/10, Effort Medium）

粗→细提取策略 + 显式覆盖率追踪：
1. 粗扫：骨架 + 文档 → 高层架构 + 主要决策
2. 差距分析：对比知识密度模型（每个子领域预期多少 stage/BD/约束）
3. 深潜：定向探索不足区域（"量化项目 M=0，去查数学模块"）
4. 验证：交叉检查所有发现

---

## 推荐的 Agent 架构

```
Phase 0: 预处理（纯 Python，并行）
  0a. 指纹探针
  0b. Clone/验证
  0c. 构建结构索引（AST 骨架 + 依赖图 + 文件分类）    ← NEW
  0d. 非代码源挖掘（README/docs/Issues/PRs/CHANGELOG）← NEW

Phase 1: 专家提取（Agentic，并行）
  1a. 架构专家（input: 结构索引 + 文档摘要）
  1b. 业务逻辑专家（input: 结构索引 + examples/ + 入口点）
  1c. 量化/领域专家（input: 结构索引 + 数学相关文件）     ← 条件激活
  1d. 经验专家（input: Issues + PRs + commit 理由）       ← 条件激活

Phase 2: 综合 + 分类（Agentic，顺序）
  2a. 合并专家输出为统一视图
  2b. 反事实分类（现有 R2 逻辑）
  2c. 对抗分类（现有 R3 逻辑）
  2d. 差距分析：对比知识密度模型
  2e. 定向深潜：重探不足区域

Phase 3: 锚定验证（Agentic + Python）
  3a. 验证每个元素的源码锚定
  3b. 交叉引用检查
  3c. 异常检测
  3d. 一致性检查

Phase 4: 组装 + 产出（Agentic + Python）
  4a. 蓝图 YAML 组装
  4b. 质量门禁
  4c. 产出到 knowledge/sources/
```

## 新增工具建议

| 工具 | 做什么 | 复杂度 |
|------|--------|--------|
| `get_skeleton` | 返回预计算的文件/模块骨架 | Easy |
| `get_dependencies` | 返回 import/call 依赖图 | Easy |
| `get_file_type` | 返回文件分类（config/model/util/test） | Easy |
| `read_issues` | GitHub API 获取 Issues/PRs | Medium |
| `semantic_search` | Voyage code-3 嵌入语义搜索 | Medium |

## 质量改进路线图

### 阶段 1：快速见效（1-2 周）
1. 构建结构索引 phase（AST 骨架，注入所有 agentic phase）
2. 增强 prompt 的锚定要求（每个元素必须有 file:line）
3. 添加 README/docs 挖掘
4. 改进数学模型检测（扩展指纹模式）

### 阶段 2：中期（3-4 周）
5. 实现专家代理分解（并行架构/业务/领域专家）
6. 添加锚定验证 phase
7. 定义知识密度模型 + 差距分析驱动定向探索
8. 挖掘 GitHub Issues/PRs

### 阶段 3：高级（4-8 周）
9. 跨提取记忆（经验数据库）
10. 多样本一致性投票
11. 依赖感知探索（call graph 追踪）
12. 模型基准测试（MiniMax vs Claude Sonnet vs GPT）

---

## 关键论文索引

| 论文 | 年份 | 关键贡献 |
|------|------|---------|
| ArchAgent | 2026 | 静态分析+LLM 混合架构恢复 |
| IRIS | 2025 | 神经符号漏洞检测（LLM推断+CodeQL遍历） |
| Code Graph Model | 2025 | 代码图结构集成到 LLM 注意力 |
| Agentless | 2024 | 层级定位 + 骨架表示 |
| cAST | 2025 | AST 感知代码分块 |
| PARSE | 2025 | Schema 优化 + 三阶段验证（92% 错误减少）|
| CoMRAT | 2025 | Commit message 设计理由分析 |
| Google LangExtract | 2025 | 开源结构化提取 + 源码锚定 |
| Compliance-to-Code | 2025 | 金融监管合规 + 代码数据集 |
| CISC | 2025 | 置信度改进的自一致性 |
| Self-Refine | 2023 | 迭代自反馈（代码错误减 30%） |
| Reflexion | 2023 | 情景记忆驱动自改进 |
| Voyage code-3 | 2024 | 最佳代码嵌入模型（超 OpenAI 13-17%）|
