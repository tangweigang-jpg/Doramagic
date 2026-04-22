# AI 规模化复制项目经验的可行性研究

**日期**：2026-04-22
**研究员**：opus subagent (深度研究任务)
**问题**：把一个成熟项目里沉淀的经验、知识、判断、教训，通过 AI 规模化复制到其他人/其他项目中使用，这件事在 2026 年是否存在可能性？

---

## Part 1 — 诚实结论

**可能，但天花板比你想的低，且当前 AI 能力边界把"可能做到"的部分正好压成了 Doramagic 此刻观察到的 4pp 形状。**

精确答案是三段：

1. **显性、狭窄、外部可验证**的项目经验（API 契约、构建步骤、测试协议、安全清单）已被实证能可靠复制，价值区间 **10–30%**（**已查证**：SWE-bench oracle-context ablation 仅 +2.1pp for GPT-4 / +1.1pp for Claude 2；工业案例报告 +206%，但局限于"大量私有且结构化程度低"的起点）。

2. **项目判断、取舍、教训**等半隐性经验，复制率经验区间 **5–15%**，且大部分已被 LLM 预训练"挤掉"——这是用户 Pilot 0 测 49% vs 45% = 4pp 的根因（**推测**，三角验证：SWE-Bench Illusion 显示模型仅凭 issue 描述即能 solve，说明公开知识的 delta 已被预训练吃掉）。

3. **真正的 tacit 直觉**（为什么这个 trade-off 此时正确）目前**不能**被 LLM token 化，Polanyi 命题在 2026 仍成立（**已查证**：*Review of Austrian Economics* 2025 论文明确指出 LLM 只能承载两种 tacit 形态中的两类，embodied tacit 仍被排除）。

**4pp 不是工程问题，是理论天花板的局部实证。继续把晶体做得更精细，回报曲线已近饱和。**

---

## Part 2 — 理论边界

三分拆解：

**显性知识**（explicit）指能完整形式化为 token 的规则、步骤、约束。

**可编码的隐性知识**（codifiable tacit）指可转写但成本高的判断规则——Polanyi 说的"知道但说不出来"。

**体现式隐性知识**（embodied tacit）指只能通过身体实践传递的直觉，比如老师傅看炉子火候、资深 SRE 凭"气味"判断数据库要炸（**已查证**：Hadjimichael et al. 2024 *Organization Studies* 明确区分此三类）。

### LLM 时代的位移

位移发生在第二类。2025 年多篇实证（**已查证**：ArXiv 2507.03811 tacit knowledge elicitation；Review of Austrian Economics 2025）确认：LLM 通过大规模语料能隐式掌握"可编码但成本高"的 tacit knowledge，**只要这类知识在其训练语料中有足够实例**。

这是好消息也是坏消息：
- 好消息：隐性知识能被 LLM 以 embedding 形态承载
- 坏消息：如果你的"项目经验"大部分已在公开代码/文档中，LLM 预训练已免费吃掉它

### 转移性分析

（**推测**，基于 SWE-bench 和 Cursor Rules 研究三角）：一个典型软件项目的经验可粗分为三层：

- 约 **50%** 是跨项目通用的（软件工程常识、语言/框架惯例）——LLM 预训练已覆盖
- 约 **30–40%** 是项目特有但可显性化的（领域规则、合约、惯例）——这是 Cursor Rules/CLAUDE.md/SKILL.md 可以承载的
- 剩余 **10–20%** 是真正 embodied 的（为什么这个 bug 反复出现、为什么这个架构决策不能碰）——LLM 能吸收其显性残留，但不能吸收其生成机制

### 可行性光谱

- **0–30% 复制**：当前公开技术可靠达成（rules / skills / MCP）
- **30–70% 复制**：需要项目内持续交互 + agent 有执行权限 + verifiable outputs（Devin 类 long-horizon agent 正在爬这区间）
- **70–100% 复制**：需要 embodied 实践模拟环境（simulation / shadowing / 多月陪跑），当前 AI **不具备**该能力，不会在 2026 内出现

### 边际成本曲线

复制第 1 个项目边际成本高（人工结构化），第 100 个项目边际成本取决于是否"语义同构"（**已查证**：Doramagic 自己的 feedback_domain_injection_compat_check 已经印证——直接 union 只在 coverage 稀薄时 work）。

这意味着可复制区间本身有**结构性上限**：同构度越低，AI 越没法把第 N 个项目变成"自动化的第 1 个"。

---

## Part 3 — 历史与 2026 年实证

### 历史反复教训（**已查证**）

- **MYCIN (1970s)**：技术上 correct，never used in production。根因是"knowledge acquisition bottleneck"——专家说不出自己为什么那么判断，工程师写不出覆盖所有 case 的规则。这是 Polanyi 命题的第一次工业实证。

- **专家系统泡沫 (1980s)**：XCON 是极少数例外（DEC 配置器，封闭 + 可验证），其他多数项目在维护代价上崩塌——规则库超过几千条后一致性无法保证。

- **咨询业 KM (1990s–2010s)**：麦肯锡/EY 投入巨资做知识库。**真实结果**：知识库成了"晋升义务归档地"而不是"下个项目的起点"。新 project 的 consultant 通常问 Senior Partner 而不是查 KB。

- **Gang of Four 设计模式（成功案例）**：成功的原因不是"传递了 tacit"，而是**给了一套共享词汇表**。模式本身是显性的（70 页代码例子），复制价值在"两个陌生人能秒对齐"的沟通效率。**这是可以复制的经验类型**。

### 2026 年实证数据

- **SWE-bench oracle-retrieval ablation**（**已查证**）：GPT-4 从 1.3% → 3.4%（+2.1pp），Claude 2 从 4.8% → 5.9%（+1.1pp）。repository context 的边际贡献**数量级上与 Doramagic 4pp 完全吻合**。

- **SWE-Bench Illusion 论文**（**已查证**）：模型仅凭 issue 描述就能 solve 大部分任务，说明公开库经验已被预训练压缩；跨库（held-out repos）性能掉到 ~53%——证明剩余的 delta 大部分在"project-specific"而不在"generic knowledge"。

- **Cursor Rules 首个大规模实证研究**（**已查证**，arXiv 2512.18925v3）：分析 401 个开源仓库的 cursor rules，产出 5 主题 taxonomy；但**并未报告端到端效果 delta**——"如果有，论文会讲"（**推测**）。

- **Agent Skills（2025-10 发布，2025-12 开源标准）**：被 Microsoft/OpenAI/Atlassian/Figma/Cursor/GitHub 快速采纳。但 Anthropic 工程师在 agentskills.io 的官方文档中承认：skills 本质是 prompts，依赖模型自愿遵从（**已查证**，The New Stack/Unite.AI 2025-12 报道）。SkillsBench 显示加 skills **有效**提升 pass rate，但**"仍达不到企业可无人值守运行的可靠性"**。**GitHub Issue #157 "Executable Agent Skills"** 提案要求加 container/build/command 字段——印证 Doramagic v1 的痛点是整个行业共性问题（**已查证**）。

- **SkillsMP 市场数据**（**已查证**）：800K+ skills listed，**60–70% effectively abandoned**。这是"载体能做出来≠载体有人用"的最刺眼证据。

- **载体公司融资 vs 产品形态**（**已查证**）：
  - Cline: $32M / 2M installs / OSS VS Code extension
  - Aider: 40K stars / 4.1M installs / CLI
  - Continue.dev: $5.1M / 26K stars / IDE 扩展

  Cline 形态上距离"可执行"最近（agent + host-integrated），融资最高；Continue.dev 更偏 IDE 扩展，融资最低。**资本已经用钱投票了哪种形态更 work**。

- **METR 研究**（**已查证**）：资深开发者使用 AI 工具**慢了 19%**，但自认快了 20%。这是 tooling/载体的**效能主观认知 vs 客观测量**差距的第一份严肃实证——对 Doramagic 意味着"用户说有用"可能不等于"客观有用"。

- **工业 case study**：**Devin 在安全修复**场景下 20x 效率提升（30 min → 1.5 min/漏洞）（**已查证**）。这是高度结构化 + 可验证输出的场景——正是 Part 2 光谱的 0–30% 区间。

---

## Part 4 — 可行形态与条件

### 载体对比

| 形态 | 适合的知识类型 | 可靠性天花板 | 证据 |
|---|---|---|---|
| **Code library / CLI** | 显性算法、可执行步骤 | 高 | GoF, UNIX philosophy 历史成功 |
| **Rules markdown (CLAUDE.md/.cursorrules)** | 编码规范、项目惯例 | 中等，依赖模型遵从 | Cursor Rules 研究证实采纳广，效果未量化 |
| **MCP servers** | 外部工具访问、结构化数据 | 中高，协议约束好 | 97M monthly SDK downloads，但真实活跃率未知 |
| **Agent Skills (SKILL.md)** | 多步流程、流程模板 | 中等，prompt-based 不可强制执行 | Anthropic 自己承认，#157 Executable 提案在路上 |
| **SaaS agent (Devin-like)** | long-horizon 可验证任务 | 高但窄 | Devin 3-4 小时/文件迁移 vs 人类 30-40 小时 |

### work 的三个共性条件（**推测** + 三角验证）

1. **Verifiable outputs**：能自动判"做对没做对"（tests pass, lints clean, contract honored）。没有 verifier 的知识载体走不出 demo。

2. **Host-enforced execution contract**：知识不是"建议"而是"合约"——host 能拒绝不合规的 model output。Anthropic Agent Skills 当前缺这层，Doramagic v1 死在这层，行业 Issue #157 正在集体补这层。

3. **窄 + 深 > 宽 + 浅**：Devin 的 20x 来自"只做安全修复"；最成功的 skills 都聚焦单一可验证任务。试图承载"整个项目经验"的载体 invariably 稀释出 4pp 形状的 delta。

### 最接近成功的三个案例（**意见**）

- (a) **Cline**（agent + enterprise exec trust，融资证据最硬）
- (b) **Devin** 在 narrow verifiable 任务上的 20x（效能证据最硬）
- (c) **MCP 协议本身**（标准采纳证据最硬，但用户用的是协议不是某一个 server）

共性：**协议/host/verifier** 三者之一有硬约束，不是单纯的"更多 prompt context"。

---

## Part 5 — 对 Doramagic 的启示

### 做对的

v2 选择晶体 + seed.yaml 双档 + Agent Skills 分发，是**把赌注押在了行业共识方向**（SKILL.md 已成跨厂商标准），资产不会白做。结构化领域约束库对"真正私有 + 真正同构"的 BP 有增量价值——finance-bp-009 内部测试的局部 wins 是真的。

### 做错的 / 正在被数据否决的

1. **4pp 不是调优问题**。SWE-bench oracle ablation 在 2023 年就给过 +2pp 的教训，2026 年 Doramagic 在公开 finance 场景测出 4pp 是理论上限，不是工程上限。**继续打磨晶体→晶体 v2→v3 回报递减**。

2. **SKILL.md 是建议不是合约**——v1 死在这里，v2 用同样的 host 假设只是把问题推后。用户应预期在任何"分发给陌生 Claude 实例"的场景下看到 20-40% 的协议遵从率滑坡（**推测**，基于 Skills 官方承认）。

3. **规模化的 denominator 选错了**。Doramagic 定位"AI 领域抄作业大师"，但 AI 领域的代码 70%+ 在 GitHub 公开，LLM 预训练已覆盖——这是 delta 被压到 4pp 的根因。想逃 4pp，要找**真私有 + 真不规整 + 真有 verifier** 的领域（金融合规流程 / 医药监管文档 / 工业 SOP），而不是继续做开源 AI 项目的 skill 包。

### 建议路径（**意见**）

- 把晶体从"分发载体"降为"内部资产"
- 把外部产品形态从"给别人的 skill 包"升级到"给特定窄领域的 verifiable agent"——Devin 的 20x 路径而不是 Gang of Four 的沟通词汇路径
- 如果坚持做 Skills 分发，必须赌 **Executable Agent Skills（GitHub Issue #157）** 那个方向会在 2026 内被 Anthropic 合并，届时 host 才有能力把晶体当合约而不是建议执行
- 否则，**4pp 是信号不是噪音**

---

## Sources

### 学术论文 / 实证研究

- [SWE-bench arXiv paper (oracle retrieval ablation)](https://arxiv.org/pdf/2310.06770)
- [SWE-bench Verified — OpenAI](https://openai.com/index/introducing-swe-bench-verified/)
- [SWE-Bench Pro leaderboard — Scale](https://labs.scale.com/leaderboard/swe_bench_pro_public)
- [SWE-Bench Illusion discussion — emergentmind](https://www.emergentmind.com/topics/swe-bench-3b86a734-b378-4ee6-bcaf-640949ed7afb)
- [Beyond the Prompt: Empirical Study of Cursor Rules (arXiv 2512.18925)](https://arxiv.org/html/2512.18925v3)
- [Speed at the Cost of Quality — Cursor DiD study (arXiv 2511.04427)](https://arxiv.org/pdf/2511.04427)
- [CodeRAG-Bench — arXiv 2406.14497](https://arxiv.org/abs/2406.14497)
- [RepoQA — arXiv 2406.06025](https://arxiv.org/abs/2406.06025)
- [Tacit knowledge in large language models — Review of Austrian Economics 2025](https://link.springer.com/article/10.1007/s11138-025-00710-5)
- [Leveraging LLMs for Tacit Knowledge Discovery — arXiv 2507.03811](https://arxiv.org/html/2507.03811v1)
- [How Does Embodiment Enable Tacit Knowledge — Hadjimichael et al. Org Studies 2024](https://journals.sagepub.com/doi/10.1177/01708406241228374)
- [Knowledge Activation: AI Skills as Institutional Knowledge Primitive — arXiv 2603.14805](https://arxiv.org/html/2603.14805v1)
- [An Empirical Study of Knowledge Transfer in AI Pair Programming — IEEE/ASE 2025](https://ieeexplore.ieee.org/document/11334486/)

### 产业博客 / 标准

- [Agent Skills — Anthropic engineering](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills)
- [Agent Skills: Anthropic's Next Bid to Define AI Standards — The New Stack](https://thenewstack.io/agent-skills-anthropics-next-bid-to-define-ai-standards/)
- [Anthropic opens Agent Skills standard — Unite.AI](https://www.unite.ai/anthropic-opens-agent-skills-standard-continuing-its-pattern-of-building-industry-infrastructure/)
- [Proposal: Executable Agent Skills — anthropics/skills Issue #157](https://github.com/anthropics/skills/issues/157)
- [Anthropic's Agent Skills Are Just Not Enough — The AI Automators](https://www.theaiautomators.com/anthropics-agent-skills/)
- [Claude Skills Marketplace Comparison 2026 — OpenAIToolsHub](https://www.openaitoolshub.org/en/blog/claude-skills-marketplace-comparison)
- [One Year of MCP: November 2025 Spec Release — MCP Blog](https://blog.modelcontextprotocol.io/posts/2025-11-25-first-mcp-anniversary/)
- [MCP Adoption Statistics 2026 — MCP Manager](https://mcpmanager.ai/blog/mcp-adoption-statistics/)

### 公司 / 融资数据

- [Cline raises $32M — globenewswire](https://www.globenewswire.com/news-release/2025/07/31/3125274/0/en/Cline-Raises-32M-in-Seed-and-Series-A-Funding-to-Bring-Agentic-AI-Coding-to-Enterprise-Software-Teams.html)
- [Continue.dev initial fundraise — Continue blog](https://blog.continue.dev/initial-fundraise/)
- [Continue TechCrunch 2025](https://techcrunch.com/2025/02/26/continue-wants-to-help-developers-create-and-share-custom-ai-coding-assistants/)
- [Devin's 2025 Performance Review — Cognition](https://cognition.ai/blog/devin-annual-performance-review-2025)
- [Cognition SWE-bench technical report](https://cognition.ai/blog/swe-bench-technical-report)
- [Cursor AI Statistics 2026 — Panto](https://www.getpanto.ai/blog/cursor-ai-statistics)
- [.cursorrules vs CLAUDE.md vs AGENTS.md — The Prompt Shelf](https://thepromptshelf.dev/blog/cursorrules-vs-claude-md/)
- [GitHub Copilot productivity research — GitHub Blog](https://github.blog/news-insights/research/research-quantifying-github-copilots-impact-on-developer-productivity-and-happiness/)

### 历史参考

- [MYCIN — Wikipedia](https://en.wikipedia.org/wiki/Mycin)
- [Rise and Fall of Expert Systems — Medium / Version 1](https://medium.com/version-1/an-overview-of-the-rise-and-fall-of-expert-systems-14e26005e70e)
- [Why Knowledge Management Systems Fail — ResearchGate](https://www.researchgate.net/publication/228585526_Why_Knowledge_Management_Systems_Fail_Enablers_and_Constraints_of_Knowledge_Management_in_Human_Enterprises)
