# 工作日志：需求图谱 + SOP v3.5 + bp-060 首次 AML 提取

> 日期：2026-04-14
> 会话：session 13（约 3 小时）
> 目标：建立用户需求图谱，扩展 SOP 支持新领域，验证 AML 子领域提取

---

## 一、Finance 项目扩充研究

### 背景

当前 59 个蓝图高度集中在量化交易（37%），信用/合规/保险/财富管理严重缺失。参照同花顺 i问财 skillhub（11 大类 50+ skills）+ 全球金融用户需求，进行系统性扩充规划。

### 执行方式

4 个子代理并行：
- **子代理 A**（sonnet）：用户需求图谱 — 7+4 类用户旅程，覆盖中美全球差异
- **子代理 B**（sonnet）：59 项目 Gap 分析 — 18 维度覆盖度矩阵
- **子代理 C**（sonnet）：核心 Gap GitHub 搜索 — AML/IFRS 9/保险/财富管理等 16 方向
- **子代理 D**（sonnet）：中国/美国/全球特色搜索 — 公募基金/SEC Edgar/期货 CTA 等 17 方向

### 产出

| 文件 | 内容 |
|------|------|
| `docs/research/finance-user-need-taxonomy.md` | 用户需求图谱（7+4 类，~4000 字） |
| `docs/research/finance-gap-analysis.md` | 59 项目 18 维度覆盖度矩阵 |
| `docs/research/finance-github-candidates-core.md` | 核心 Gap GitHub 候选 |
| `docs/research/finance-github-candidates-regional.md` | 中国/美国/全球候选 |
| `knowledge/blueprints/finance/EXTRACTION_ROADMAP.md` | 汇总路线图（403 行） |

### 核心结论

- **59 → 89**：推荐补充 30 个项目
- ABSENT 类别 1→0，THIN 类别 5→1，ADEQUATE+ 覆盖率 →94%
- P0（11 个）：AML/KYC、IFRS 9、保险精算×3、智能投顾、压力测试、公募基金、期货 CTA、SEC Edgar
- P1（14 个）：贷款管理、金融账本、AI 研报、NL 选股、XVA、MBS/ABS、ALM 等
- P2（5 个）：LGD、气候因子、SA-CCR、A股财报、SEC NLP

---

## 二、SOP v3.5 + Agent v6.4 升级

### 必要性

EXTRACTION_ROADMAP 新增 30 个项目覆盖 Insurance/Lending/Treasury/AML 等全新领域。SOP v3.4 的 7 个子领域不覆盖这些领域。

### SOP v3.5 改动（我自己写）

1. **子领域表 7→11**：新增 INS（保险精算）、LND（贷款支付）、TRS（财资 ALM）、AML（反洗钱）
2. **4 个新子领域专项必审清单**：
   - INS 6 项：准备金方法、死亡率表、Best Estimate、Solvency II SCR、再保映射、巨灾模型
   - LND 6 项：利率类型、还款计划、逾期定义、催收合规、双重记账、对账时效
   - TRS 5 项：LCR/NSFR、利率缺口、FTP、现金池结构、外汇敞口
   - AML 6 项：CTR/SAR 阈值、制裁名单版本、模糊匹配、网络分析深度、误报率、审计日志
3. 版本号 3.4 → 3.5

### Agent v6.4 改动（两个子代理并行）

| 子代理 | 文件 | 改动 |
|--------|------|------|
| E | `pipeline.py` | SUBDOMAIN_KEYWORDS 增加 4 组关键词 |
| E | `prompts.py` | 4 个新 CHECKLIST 常量 + 映射 |
| F | `blueprint_phases.py` | worker_audit 注入子领域清单 + BQ-07 新规则 |
| F | `blueprint_enrich.py` | P7 STAGE_MAPPING 增加 20 个别名 |

12 个子领域全部注册，98 tests passed。

---

## 三、bp-060 (AMLSim) 首次 AML 子领域提取

### 目标

验证 v6.4 agent 对全新 AML 子领域的全自动提取能力。AMLSim 是 IBM 开源的反洗钱交易模拟器（Java + Python）。

### 执行过程

1. 克隆 AMLSim 仓库到 `repos/AMLSim/`
2. 启动全量提取（v6.4 agent, --blueprint-version v5）
3. MiniMax API 持续过载（529 overloaded + 429 rate limit）

### 失败分析

| 阶段 | 问题 |
|------|------|
| worker 并行阶段 | 6 个 worker 并行调用触发 MiniMax 个人套餐并发限制（429） |
| MiniMax failover → GLM-5 | worker_workflow / worker_arch_deep 在 GLM-5 上 token 预算超限（510K/500K） |
| worker_workflow blocking | 双模型都失败 → pipeline 中断 |
| Resume 尝试 ×2 | MiniMax 仍然 529，无法恢复 |

**根因**：MiniMax 服务端今天整体不稳定，不是 agent 代码问题。

### 当前状态

- Checkpoint 已保存（worker_docs + worker_arch 已完成）
- 等 MiniMax 恢复后 `--resume` 即可继续
- resume 命令已记录

---

## 四、Commit 记录

| Commit | 内容 |
|--------|------|
| `94efc6e` | 用户需求图谱 + Gap 分析 + EXTRACTION_ROADMAP（5 个研究文档） |
| `13e9af5` | SOP v3.5 + Agent v6.4（INS/LND/TRS/AML 子领域，5 个文件） |

---

## 五、遗留问题

1. **bp-060 (AMLSim) 提取待完成**：MiniMax 恢复后 resume
2. **GLM-5 token 预算过紧**：500K 对 GLM-5 的冗长输出不够，需考虑提高到 800K-1M
3. **并行 worker 并发限制**：6 个 worker 同时调用 MiniMax 个人套餐容易触发 429，需考虑限制并发或错峰
4. **P0 剩余 10 个项目**：bp-061~070 待提取
5. **Synthesis Step 3 (interactions) 持续不稳定**：三个项目都 L2/L3 fallback（int_parsing 错误）

---

## 六、本 Session 方法论收获

1. **子代理并行研究效率极高**：4 个 sonnet 子代理同时做需求图谱/Gap 分析/GitHub 搜索，总计 ~250K tokens，<10 分钟完成了原本需要数小时的研究工作
2. **SOP 先行，代码跟随**：先写 SOP v3.5 定义子领域和审计清单，再让子代理实现代码。保证了规范和实现的一致性
3. **基础设施风险**：LLM API 稳定性是全自动提取的最大外部风险。双模型 failover 缓解了单点故障，但并发限流 + token 预算超限的组合仍可导致 pipeline 中断
4. **消费者洞察驱动的项目选择**：从用户"想解决什么问题"出发（而非简单对标竞品 skill），发现了保险精算、财资 ALM、贷款管理等竞品完全不覆盖但全球用户强需求的领域
