# Doramagic 文档索引

> 生成日期：2026-03-25
> 基于三路并行研究（产品定义 + 技术实践 + 研究成果）综合

---

## 一、产品定义文档（按版本演化）

| 版本 | 日期 | 文件路径 | 核心变化 |
|------|------|---------|---------|
| v1 | ~03-09 | experiments/exp01-v04-minimax/ | 原型阶段，无产品定义 |
| v2 | 03-11 | research/product-review-2026-03-11/doramagic-v2-product-definition.md | **奠基**：品牌+哲学+用户定义 |
| v3 | 03-12 | research/product-definition-v3/doramagic-v3-product-definition.md | **架构**：积木+Compiler+置信度 |
| v4 | 03-14 | docs/research/20260314_doramagic_v4_product_definition.md | **护城河**：不完整知识+交付姿态 |
| v5/5.2 | 03-15~17 | docs/research/20260315_doramagic_v5_product_definition.md | **就绪**：跨项目引擎+Agent验证 |
| v5.3 | 03-18 | docs/doramagic-dev-manual-v5.3.md | **冻结版**：开发基准，当前权威 |

### 用户侧文档
- docs/PRODUCT_MANUAL.md — 产品手册 v1.0（2026-03-11，偏旧）
- README.md — GitHub 公开页面
- INSTALL.md — 安装和使用指南
- CONTRIBUTING.md — 贡献指南
- CHANGELOG.md — 版本日志
- SECURITY.md — 安全策略

---

## 二、技术文档

### 开发基准
- **docs/doramagic-dev-manual-v5.3.md** — ★ 当前权威开发手册
- docs/dev-context-briefing.md — v5.2→v5.3 补充上下文
- docs/dev-plan-codex-module-specs.md — 赛马模块接口规格
- docs/engineering-plan-v1.md — 工程实施方案（面向非技术创始人）

### 管线设计
- docs/multi-project-pipeline.md — Phase A-H 多项目管线设计
- docs/full-integration-dev-brief.md — 25+ Session 研究成果集成清单
- docs/doramagic-product-dev-brief.md — 产品开发简报
- docs/doramagic-product-dev-requirements.md — 产品需求文档

### 工作日志
- docs/20260320_s4_full_integration_log.md — S4-GLM5 全集成日志
- docs/20260320_S4_GLM5_Full_Integration_WorkLog.md — S4 工作日志

### 早期文档（docs/brainstorm/、docs/plans/）
- 10 个 brainstorm 文件（2026-03-08 session 01~02）
- 11 个 plans 文件（设计+实施方案）

---

## 三、赛马文档（races/）

### R06 — 全面落地赛马（120/120 测试通过）
- races/r06/R06_WorkLog.md — R06 工作日志
- races/r06/agentic/BRIEF.md — 赛道 A：Agentic 提取
- races/r06/bricks/BRIEF.md — 赛道 B：积木制作
- races/r06/compiler/BRIEF.md — 赛道 C：Knowledge Compiler
- races/r06/confidence/BRIEF.md — 赛道 D：置信度+DSD
- races/r06/injection/BRIEF.md — 赛道 E：积木注入
- races/r06/runner/BRIEF.md — 赛道 G：Phase Runner

### R05 — 模块赛马（259 测试通过）
- races/r05/api_read/ — API 读取模块
- races/r05/snapshot_builder/ — 快照构建模块

### 包级决策文档（各包 DECISIONS.md）
- packages/cross_project/DECISIONS.md — 跨项目对比
- packages/extraction/doramagic_extraction/DECISIONS.md — 提取模块
- packages/orchestration/doramagic_orchestration/DECISIONS.md — 编排模块
- packages/platform_openclaw/doramagic_platform_openclaw/DECISIONS.md — 平台适配
- packages/skill_compiler/doramagic_skill_compiler/DECISIONS.md — 技能编译

---

## 四、研究文档（research/，15 个主题）

### 核心研究（三方验证，决策质量最高）
| 主题 | 目录 | 方法 | 落地率 | 优先级 |
|------|------|------|--------|--------|
| 跨项目智能（主+5子研究） | research/cross-project-intelligence/ | 三方 | 20% | P0 |
| Agentic 提取 | research/agentic-extraction/ | 三方 | 15% | P0 |
| 预提取领域 | research/pre-extraction-domains/ | 三方 | 25% | P1 |
| 好作业/坏作业评判 | research/good-homework-selection/ | 三方 | 0% | P1 |
| 暗雷体系 | research/misleading-good-homework-dark-traps/ | 三方 | 30% | P1 |

### 重要研究（单方/双方）
| 主题 | 目录 | 方法 | 落地率 |
|------|------|------|--------|
| Soul Extractor 审查 | research/soul-extractor-review/ | 单方 GLM5 | 30% |
| 灵魂拆解（模块化） | research/soul-decomposition/ | 单方 GLM5 | 0% |
| 知识可信度系统 | research/confidence-system/ | 未完成 | 10% |
| 积木粒度 | research/soul-lego-bricks/ | 未完成 | 5% |
| AI 知识消费格式 | research/ai-knowledge-consumption/ | 待查 | ? |
| GLM5 实践 | research/glm5/ | 单方 | ? |

### 实验数据（experiments/）
| 实验 | 目录 | 关键成果 |
|------|------|---------|
| exp01-v04-minimax | Baseline 42% |
| exp05-v08-superpowers | v0.8 最佳实践 |
| exp07-v09-superpowers-usertest | wger 适应性测试 100% traceability |
| exp08-v09patch-superpowers | ★ P0 补丁后 42%→96% |
| exp-seo-skills | 4 个 SEO 项目，验证跨项目对比 |

---

## 五、项目状态文档
- INDEX.md — 项目全局索引（代码规模、目录结构、状态）
- TODOS.md — 待办任务（P1/P2/P3，2026-03-23 CEO+Eng Review）
- bricks/BRICK_INVENTORY.md — 积木清单（278 块，34 领域）
