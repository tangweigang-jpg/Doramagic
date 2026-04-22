# 源码知识提取领域全景研究

日期: 2026-04-07
研究方法: Web search + GitHub exploration (Sonnet 子代理)
目的: 为 Doramagic 蓝图提取方法论寻找外部参考和可借鉴技术

## 研究结论

### Doramagic 的独特性（已确认）

SWARCH-LLM 系统综述 (arxiv:2505.16697) 明确指出："源码→架构知识+设计理由"是未充分探索的领域。Doramagic 的方法论在学术上确实是新的：
- 源码优先（不是文档优先）提取业务逻辑
- 两层输出（Blueprint + typed Constraints）专为 AI agent 消费设计
- 金融领域本体覆盖 13 个子领域
- 晶体编译为可复用知识制品

### 关键发现（按相关性排序）

#### Tier 1: 直接可借鉴

| 项目 | 核心技术 | 借鉴点 |
|------|---------|--------|
| **Gray Beam CDD** (graybeam.tech) | 10 类约束分类（Quantitative/Temporal/Invariant/Conditional/Causal/Resource/Authorization/Pattern/Soft/Probabilistic） | 约束分类体系参考 |
| **Compliance-to-Code** (arxiv:2505.19804) | 中国金融法规 4 元素分解（主体/条件/约束/上下文），1159 条标注 | RC 类约束的结构化 schema |
| **RAFT** (arxiv:2601.09762) | 多 LLM 净化聚合提取隐性监管知识 | 验证了"四方 LLM 研究"方法的学术基础 |
| **Daikon** (plse.cs.washington.edu/daikon) | 动态不变量检测，运行代码观察实际值报告前/后置条件 | 可用于验证 LLM 提取的约束 |

#### Tier 2: 方法论参考

| 项目 | 核心技术 | 借鉴点 |
|------|---------|--------|
| **CodexGraph** (arxiv:2408.03910) | 代码→属性图→Cypher 查询 | 结构化代码知识表示 |
| **DRAFT** (arxiv:2504.08207) | RAG + fine-tune 生成架构决策记录 | ADR 语料库作为微调数据 |
| **RepoAgent** (arxiv:2402.16667) | LLM 全仓库文档生成 + git pre-commit 增量更新 | 增量更新策略 |
| **ClassInvGen** (arxiv:2502.18917) | LLM 生成类不变量 + 测试输入 | 约束+测试用例共生成 |

#### Tier 3: 行业参考

| 项目 | 核心技术 | 借鉴点 |
|------|---------|--------|
| **EPAM ART** | COBOL/Java 业务规则提取 → BRD 文档 | 大代码库分块策略、CRUD 矩阵 |
| **RapidX (Hexaware)** | 多 Agent "功能 MRI" + Business Blueprint Agent | Code Intelligence 和 Business Blueprint 分离为两个 agent 角色 |
| **Azure Legacy Modernization Agents** | 业务逻辑持久化到 SQLite business_logic 表 | 业务逻辑作为 pipeline 间持久化 artifact |
| **QuantMind** (arxiv:2509.21507) | 量化金融文档知识提取 + 领域标签 | 金融领域标签分类体系 |

#### Tier 4: 学术前沿

| 论文 | 核心发现 |
|------|---------|
| arxiv:2504.20781 | LLM 生成设计理由的 F1=0.35-0.39，64-69% 的 LLM 理由对人类有帮助但含 1-3% 误导 |
| arxiv:2601.06181 | LLM + SMT 求解器做金融合规分析，86.2% 正确率，100x 推理效率提升 |
| arxiv:2505.16697 | 系统综述确认"源码→架构知识"是未充分探索领域 |

## 未来可探索方向

1. 用 Daikon 动态验证 LLM 提取的约束（运行 repo 的测试套件，观察实际不变量）
2. 用 RAFT 的多 LLM 聚合方法改进约束采集管线
3. 参考 Gray Beam 的 10 类分类扩展约束 schema
4. 参考 Compliance-to-Code 的中国金融法规数据集构建 RC 类约束
