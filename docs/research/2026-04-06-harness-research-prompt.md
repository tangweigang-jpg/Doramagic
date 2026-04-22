# Doramagic 四方评审提示词：Harness 技术对知识晶体的适用性

> 发布日期：2026-04-06
> 目标受众：Grok / Gemini / GPT（独立评审）
> 预期产出：结构化技术评审报告

---

## 提示词正文

你是一位全球顶级的 AI 系统架构师，专精于 LLM agent 的编排控制和可靠性工程。

我正在开发一个名为 **Doramagic** 的产品，它的核心能力是从 GitHub 开源项目中提取结构化知识，封装成"知识晶体（Crystal）"，让 AI agent 在各种宿主环境中利用这些晶体完成复杂任务。

最近我们团队读了一篇关于 **Natural-Language Agent Harnesses (NLAH)** 的论文（arXiv:2603.25723），并对 Harness 技术进行了深度研究。现在需要你作为独立评审，判断这项技术是否值得引入我们的晶体架构。

请在回答前先阅读论文原文：https://arxiv.org/html/2603.25723v1

---

### 背景 1：Doramagic 的知识架构

Doramagic 的知识体系是三层结构：

```
Crystal = Blueprint（蓝图）+ Constraints（约束）+ Resources（资源）
```

- **蓝图（Blueprint）**：从 GitHub 项目源码提取的框架级知识。描述"这个框架怎么运作"——架构分层、核心抽象、数据流、扩展点。目前有 59 个蓝图，涵盖金融量化领域主流开源项目。蓝图 v2.3 新增了 `business_decisions`（T/B/BA/DK/RC 五类标注）和 `known_use_cases`（结构化业务用例）。

- **约束（Constraints）**：从源码和测试中提取的"不能做什么"规则。目前有 3,257 条，每条包含 trigger_condition、required_action、consequence_description、constraint_kind 等结构化字段。约束 SOP v1.3 新增了"蓝图驱动的业务约束派生"机制。

- **资源（Resources）**：让晶体成为 skill 并运行得更好所需的 API、工具、依赖包等一切（除 LLM 以外）。包含数据源、存储后端、Python 依赖等。

**核心公式**：好的晶体 = 好的蓝图 + 好的资源 + 好的约束

晶体最终渲染为一个 `.seed.md` 文件，交给 AI agent 在宿主环境中执行。

---

### 背景 2：晶体在测试中遇到的真实问题（v1→v9，五代迭代）

我们在两个宿主环境中测试了晶体——**OpenClaw**（受限 sandbox 环境，MiniMax 模型）和 **Claude Code**（全权限环境，Claude 模型）。以下是按类别整理的全部问题：

#### 类别 A：宿主执行环境限制

1. **exec preflight 拒绝**：AI 使用 `cd /path && python3 script.py` 格式，被 OpenClaw 安全层拦截（拦截所有 shell 操作符 `&&`;`|`）。在 v5/v7/v8 三个版本中反复触发。
2. **600 秒超时硬上限**：OpenClaw 的 `timeoutSeconds=600` 是硬限制。多文件方案（5 个文件）需要 8-12 次工具调用，AI 思考时间累积 430-700 秒，超出上限。v5 三次超时、v6 被 OS SIGTERM kill。
3. **edit_file 精确匹配失败**：OpenClaw 的 edit 工具要求精确文本匹配，AI 生成的替换文本与文件内容存在空格/缩进差异，导致编辑失败。
4. **缓存管理被 AI 误移至 shell 层**：晶体只给了缓存逻辑的注释伪代码，AI 认为需要先用 `rm -f cache.pkl` 再执行脚本，触发 preflight 拒绝。

#### 类别 B：AI 参数漂移与规格违反

5. **股票池膨胀**：规格锁定 5-20 只股票，AI 调用 `bs.query_hs300_stocks()` 获取全量 300 只。v6 因此被 OS kill（下载约 90 只后超时），v8 同样膨胀到 300。
6. **TOP_N 参数漂移**：规格值 TOP_N=5，AI 自行改为 30。规格锁表格遗漏了 TOP_N 字段。
7. **策略类型漂移**：规格要求"20 日动量因子"，v5 在多轮 bug 修复后静默切换为"Bollinger Band 反转策略"。这是最危险的漂移——结果看起来合理但策略完全错误。
8. **API 参数格式错误**：晶体只给了注释伪代码，AI 用位置参数而非关键字参数调用 baostock API，首次运行失败。

#### 类别 C：晶体格式与 AI 消费问题

9. **蓝图拆散导致模式切换**：v1 晶体（48KB）将蓝图拆散混编 104 条约束，AI 进入"文档审查模式"而非"构建执行模式"，产出参考文档而非可运行系统。综合得分 57%。
10. **约束覆盖率指数衰减**（"指令诅咒"）：104 条约束，AI 只覆盖 36 条（35%）。学术研究表明多约束遵循率 ≈ (单条遵循率)^N，即 0.95^104 ≈ 0.005%。84 条验收标准 0 条被执行。
11. **directive 无法锁死 AI 逃逸路径**：v2 有 execution_directive 但 AI 仍产出文档。AI 可以把"文档"也当"系统交付"，可以口头声称"已完成验收检查"。
12. **AI 受阻后回退到已知死路**：v7 exec 失败后，AI 自动创建 zipline 目录回退到 zipline 路径，尽管 v5/v6 已证明此路不通。

#### 类别 D：验收与交付质量

13. **门禁不检查结果合理性**：v5 交付 -0.25% 回测结果，表面通过（非 NaN），实际是 pending_order bug 导致无有效成交。
14. **session recovery 后状态丢失**：OpenClaw compaction 压缩上下文后，AI 不知道"已完成什么"，可能重头开始或部分重写已完成文件。
15. **结果未结构化输出**：三项关键指标（annual_return / max_drawdown / sharpe）"在代码里计算了但未确认在输出中"。

#### v9 成功的关键因素

v9 是首个全指标通过的版本（6 分钟完成交付），其成功归因于 5 项针对性修复：
- exec 白名单穷举（覆盖所有 shell 操作符）
- 规格锁覆盖所有可变参数（STOCK_POOL、TOP_N、MOMENTUM_WINDOW 每一个显式锁）
- 代码模板给可执行示例而非伪代码注释
- 删除可选扩展阶段（AI 会直接跳到扩展而非渐进验证）
- 缓存管理声明为"Python 内部管理"

---

### 背景 3：NLAH 论文的核心发现（我们的初步分析）

NLAH 论文提出将 agent harness 的设计模式层外化为可执行的自然语言对象，包含六个组件：Contracts、Roles、Stage Structure、Adapters & Scripts、State Semantics、Failure Taxonomy。

关键实验结果：
- Self-evolution 模块最有效（SWE-bench +4.8%）
- File-backed state 在 GUI 任务显著（OSWorld +5.5%）
- **Verifier 和 Multi-Candidate Search 反而有害**（SWE -0.8%/-2.4%, OSWorld -8.4%/-5.6%）
- Full IHR 在 coding 上不如简化版（74.4 vs 76.0）
- 代码→NLAH 迁移后性能反升（30.4→47.2%）

我们的初步判断：NLAH 的 Contract 和 Failure Taxonomy 直接命中晶体的参数漂移和验收无力问题，但不能无脑堆叠所有模块。

---

### 请你评审的 7 个问题

请对以下 7 个问题逐一给出你的判断，每个问题需要：**立场（赞成/反对/有条件赞成）+ 理由 + 风险评估**。

#### Q1：Crystal 是否应该新增 Execution Harness 层？

当前 Crystal = Blueprint + Constraints + Resources。是否应该新增第四层 `Execution Harness`，用于定义晶体在宿主中的执行控制逻辑？

考虑因素：
- 这会改变 Crystal 的核心公式（好的晶体 = 好的蓝图 + 好的资源 + 好的约束）
- v9 的成功是通过 directive hardening（在自然语言中手工编码执行规则）实现的
- NLAH 论文证明自然语言 harness 可执行且有效

#### Q2：NLAH 的六个组件中，哪些值得引入晶体 schema？

请对六个组件逐一评估：Contracts、Roles、Stage Structure、Adapters & Scripts、State Semantics、Failure Taxonomy。

考虑因素：
- 论文自证 Verifier 和 Multi-Candidate Search 有害
- 晶体的宿主环境差异巨大（OpenClaw 600 秒 sandbox vs Claude Code 全权限）
- 过度结构化可能加剧"指令诅咒"（约束越多覆盖率越低）

#### Q3：Execution Contract 应该是声明式还是程序化？

两种路径：
- **声明式**：在晶体中用自然语言定义 Contract（如"TOP_N 必须等于 5"），依赖 AI 自觉遵守
- **程序化**：在晶体中定义 Contract schema（如 `{"param": "TOP_N", "value": 5, "violation": "FATAL"}`），由宿主 runtime 程序化校验

v9 的规格锁是声明式的（写在 directive 中），NLAH 的 IHR 是程序化的（in-loop LLM 解释执行）。

#### Q4：如何解决"指令诅咒"与"更多 Harness 规则"之间的矛盾？

核心矛盾：
- 约束越多 → 覆盖率指数衰减（0.95^N）
- Harness 规则本质上也是约束 → 加入 Execution Harness 会进一步增加晶体的指令总量
- 但不加 Harness → 参数漂移、验收无力等问题无法解决

NLAH 论文的 Full IHR 消耗 16.3M tokens，是简化版的 13 倍，但性能更低。这个代价是否可接受？

#### Q5：Crystal Execution Protocol 应该是晶体内嵌还是宿主外挂？

两种架构：
- **内嵌**：每个晶体自带执行协议（类似 NLAH 的 harness skill bundle），优点是自包含可移植，缺点是增加晶体体积
- **外挂**：执行协议定义在宿主侧（类似 Claude Code 的 CLAUDE.md + hooks），晶体只带内容不带执行逻辑，缺点是跨宿主不可移植

NLAH 论文选择了"harness skill 可加载到共享 runtime"的中间路径。

#### Q6：论文中"代码 harness→自然语言 harness 迁移后性能反升"的发现对 Doramagic 意味着什么？

论文中 OS-Symphony 从代码实现（30.4%）迁移到 NLAH 自然语言实现（47.2%），性能大幅提升。论文解释是"可靠性机制从本地屏幕修复重新定位到持久运行时状态和制品支撑的闭合"。

这是否意味着：
- 自然语言 harness 本身就是更好的控制方式？
- 还是 IHR runtime（GPT-5.4 in-loop 解释）才是真正的性能来源？
- 对 Doramagic 来说，用自然语言在晶体中定义 harness 是否比用代码在宿主中实现 harness 更优？

#### Q7：基于以上分析，你对 Doramagic 的具体建议是什么？

请给出优先级排序的行动建议（短期/中期/长期），并标注每项建议的：
- 预期收益（解决哪些问题）
- 实施成本（复杂度）
- 风险（可能的副作用）

---

### 输出格式要求

请按以下结构组织你的回答：

```
## 总体判断（一句话）

## Q1-Q7 逐项评审
每个问题：
- 立场：赞成/反对/有条件赞成
- 核心理由（3-5 句）
- 风险评估
- 与其他问题的关联

## 我发现但你没问的问题（开放式补充）

## 行动建议（优先级排序表格）
```

---

*提示词版本：v1.0 | 2026-04-06 | Doramagic CEO + CTO 联合撰写*
