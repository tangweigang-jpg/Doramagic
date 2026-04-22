# CLI-Anything vs Doramagic Skill Plugin — 竞品对标分析

> 作者：Claude Sonnet 4.6（产品战略研究员）  
> 日期：2026-04-21  
> 主要数据源：
> - CLI-Anything README（https://github.com/HKUDS/CLI-Anything）
> - CLI-Anything Plugin README（cli-anything-plugin/README.md）
> - CLI-Hub 官网（https://clianything.cc/）
> - Doramagic PRODUCT_CONSTITUTION.md v3.1
> - Doramagic docs/designs/2026-04-20-crystal-v6-design.md
> - Doramagic worklogs/2026-04/2026-04-21-v6-benchmark-results-and-verdict.md
> - Doramagic knowledge/sources/finance/finance-bp-009--zvt/finance-bp-009-v6.1.seed.yaml
> - Doramagic knowledge/sources/finance/STATUS.md（73 项目）
>
> **免责声明**：本分析基于公开信息截止 2026-04-21。CLI-Anything 的未列出内部功能若与本分析相悖，CEO 应以一手资料为准。

---

## 一、CLI-Anything 架构概览

### 一句话定义

CLI-Anything 是一个**自动化框架**，通过 7 阶段流水线，将任何有源码的**GUI 应用或 API 服务**（GIMP、Blender、LibreOffice、OBS Studio 等）转换为 agent 可消费的命令行接口（CLI），并通过 CLI-Hub 注册表统一分发。

### 5 条核心能力

| # | 能力 | 说明 |
|---|---|---|
| 1 | **CLI 自动生成** | 7 阶段 pipeline：源码分析 → CLI 设计 → Click 实现 → 测试规划 → 测试实现 → SKILL.md 生成 → PyPI 发布 |
| 2 | **REPL + JSON 输出** | 同一套 CLI 面向人类（交互模式）和 agent（`--json` 结构化输出），无需额外适配层 |
| 3 | **CLI-Hub 注册表** | `pip install cli-anything-hub` + `cli-hub install <name>` 一行命令安装，支持 OpenClaw、Claude Code、Codex 等 30+ 平台 |
| 4 | **SKILL.md 生成** | 每个 CLI 自动产出 SKILL.md，agent 可通过标准接口发现和消费 |
| 5 | **测试驱动质量门禁** | 2,202 条 unit + E2E 测试覆盖 33+ 软件，质量以"测试通过率"度量 |

### 核心目标用户场景

Agent 需要操作 **无原生 API 的 GUI 软件**（图像编辑、视频剪辑、3D 建模），CLI-Anything 通过 subprocess 包装将 GUI 能力 agent 化，从根本上替代截图式 RPA。

---

## 二、能力重合度矩阵

**方法论说明**：重合度需要在两个层面分别衡量，而非一个数字。这两个层面的结论截然不同。

### 2.1 分发形式层（"用什么格式交付"）— 重合度 ~85%

| 特性 | CLI-Anything | Doramagic Skill Plugin |
|---|---|---|
| SKILL.md 标准格式 | ✅（自动生成） | 计划（手工或半自动生成） |
| GitHub 分发 | ✅ | ✅ |
| CLI-Hub / ClawHub 注册 | ✅（CLI-Hub） | 计划（ClawHub.ai） |
| host AI 按需消费（OpenClaw/Claude Code/Codex） | ✅ | 计划 |
| 子目录分层结构（SKILL.md + 子文件） | ✅（SKILL.md + HARNESS.md） | 计划（SKILL.md + anti_patterns/ + kuc/...） |

**结论**：在"如何把知识送进 agent"这个分发层，两者几乎相同，**都在跑向同一个生态标准（SKILL.md）**。这是收敛，不是竞争——相当于两家公司都在给 PDF 文件加封面，封面格式一样，但里面的内容完全不同。

### 2.2 知识内容层（"装了什么知识"）— 重合度 <5%

| 能力 | CLI-Anything | Doramagic Skill Plugin | 证据 |
|---|---|---|---|
| 从开源项目提取知识 | ✅（提取 API 结构用于生成 CLI） | ✅（73 蓝图已提取，含 BD/UC/Constraints） | CLI-Anything README；STATUS.md |
| **目标软件类型** | **GUI 应用 / 守护进程**（GIMP/Blender/LibreOffice） | **Python import 库**（zvt/qlib/backtrader/FinRL） | 双方 README + 73 项目列表 |
| 生成可执行 CLI 工具 | ✅（核心产物，Click REPL + PyPI 包） | ❌（宪法 §1.3 明确"不做代码生成"） | PRODUCT_CONSTITUTION.md §五 |
| 领域约束注入（T+1、lookahead 偏差等） | ❌（无据，全部 33 个示例均无金融语义层） | ✅（86 条 `_shared` 池约束：cn-astock + backtesting + factor-research + data-sourcing） | V6 design §3.2；v6.1 seed.yaml |
| 跨项目反模式（issues 挖掘） | ❌（无据） | ✅（32 条，来自 zvt+qlib+vnpy+zipline top issues 挖掘） | v6.1 seed.yaml AP-* 条目 |
| 跨项目精华借鉴（cross_project_wisdom） | ❌（无据） | ✅（10 条，含 backtrader/vnpy/qlib 精华） | v6.1 seed.yaml CW-* 条目 |
| 锻造档案 / 溯源（forge_record + evidence_refs） | ❌（未发现任何溯源机制） | ✅（宪法 §1.2.8；每条约束可追溯到 issue/代码行） | PRODUCT_CONSTITUTION.md |
| A/B benchmark 验收（vs README 基线） | ❌（质量门禁是测试通过率，非 vs 基线的增量）| ✅（延展度 +22pp，规避度 +15pp，blind judge 验证） | V6 worklog §三 |
| 批量离线生产（73+ 项目） | ✅（33+ 软件已产出） | ✅（73 项目 56 PASS 17 WARN 0 FAIL） | 双方文档 |
| 中美双深金融领域专精 | ❌（通用：创意工具/生产力/媒体/基础设施） | ✅（cn-astock/us-equity/backtesting/options/futures 等 10+ 市场维度） | V6 design §3.2 |
| AST 组件地图（component_capability_map） | ❌（无据） | ✅（zvt 424 classes，按模块分） | v6.1 seed.yaml |
| 用例四元组（KUC：inputs/components/params/validation）| ❌（无标准 KUC 结构）| ✅（41 条深度场景，如 follow_ii_trader.py 跟基金持仓） | V6 worklog §四；v6.1 seed.yaml |

**结论**：知识内容层重合度 **<5%**。两者都在"从源码提取知识"，但提取的内容、目标领域、编译目标完全不同。

---

## 三、Doramagic 独有价值的严苛挑战

### 挑战前提

本节主动挑战 Doramagic 的"护城河"声明。每条独有价值必须满足：
1. CLI-Anything **没有做或无法做**（有一手证据）
2. Doramagic **已经做了**（有实测数据）

凡仅靠"计划"支撑的，标注为"待验证"。

---

### 独有价值 #1：金融领域语义层——经证实 ✅

**声明**：Doramagic 对 Python quant 库提供领域语义注入，CLI-Anything 无此能力。

**CLI-Anything 反驳检验**：CLI-Anything 的 33+ 目标（GIMP/Blender/LibreOffice/OBS）全部是通用 GUI 应用，无一个是金融 Python 库。其 HARNESS.md 记录的是"帧率精度/滤镜转换"问题，不是"T+1/lookahead/rate-limit"问题。**CLI-Anything 的架构设计也使其无法适用于 `import zvt`**——Python 库不需要 CLI 包装，需要的是"用它时什么会出错"。

**Doramagic 实证**：v6.1 seed 含 86 条 `_shared` 领域约束（cn-astock-T1-001 等），延展度 benchmark +22pp（vs README 基线，blind judge 验证，345 prompts，0 失败）。

**结论**：真实独有，有一手证据。

---

### 独有价值 #2：issues 挖掘的反模式库 + 跨项目精华——经证实 ✅

**声明**：Doramagic 系统性从 top-200 issues 挖掘跨项目反模式，并做跨项目精华借鉴，CLI-Anything 无此机制。

**CLI-Anything 反驳检验**：CLI-Anything 的质量门禁是"生成的 CLI 通过 2,202 条测试"，测的是"工具能不能跑"，不是"用这个库有哪些坑"。其 HARNESS.md 记录的是生成方法论，没有任何迹象表明有跨项目 issue 挖掘机制。

**Doramagic 实证**：v6.1 seed 包含 AP-ZVT-183（除权因子 inf/NaN 静默失败）、AP-ZVT-179（jqdata 超限后异常被吞噬）等，每条带 issue 链接。规避度 benchmark +15pp（blind judge）。

**结论**：真实独有，有一手证据。

---

### 独有价值 #3：A/B benchmark 发布门禁（知识增量而非功能完备）——经证实 ✅

**声明**：Doramagic 的质量门禁是"vs 裸 README 基线的增量分"，CLI-Anything 的质量门禁是"功能测试通过率"，是不同的质量量纲。

**本质区别**：CLI-Anything 问的是"生成的工具对不对"；Doramagic 问的是"有了这个晶体，agent 比只读 README 好多少"。两者衡量不同事物，不可替代。

**Doramagic 实证**：V6 benchmark 345 prompts，三维分数（还原度/规避度/延展度），blind judge（编译模型 ≠ 评分模型，防自评偏差），V6.0 延展度 68% vs A 组 46%，净增 +22pp（worklog §3.1）。

**结论**：真实独有。CLI-Anything 若要做同等质量门禁，需要重新定义其质量体系，这不是工程增量而是方向性重写。

---

### 独有价值 #4：73 项目的金融知识库密度——部分有效，待规模验证 ⚠️

**声明**：73 个金融项目的蓝图库（bp-009 zvt、bp-086 backtrader、bp-087 qlib、bp-088 zipline 等）产生的跨项目 wisdom 密度，是 CLI-Anything 无法复制的竞争壁垒。

**CLI-Anything 反驳检验**：CLI-Anything 也有 33+ 软件，规模相当。但其知识是"如何用 subprocess 调用 GIMP"，不是"backtrader 和 zvt 在因子回测上有什么共同坑"——后者需要在相同领域积累足够的宽度才能出现跨项目规律。

**诚实警告**：目前 73 项目中仅有少量晶体（v6.0/v6.0a/v6.1 = 3 颗），跨项目 wisdom 只有 10 条。"73 项目宽度 → 护城河"的逻辑成立，但**护城河密度的验证还需要 V6 Pilot B（zipline）完成后看池复用率**（V6 design §五要求 zero 新建 activities 池）。

**结论**：方向正确，但目前证据不足以独立支撑护城河主张。应在 Pilot B 完成后升级评级。

---

### 严苛自检：是否有 Doramagic 已废弃但 CLI-Anything 还在做的东西？

- **可执行代码生成**：Doramagic 宪法 §五明确禁止，CLI-Anything 的核心是生成代码——两者方向性不同，不构成 Doramagic 竞争劣势，而是刻意的产品边界选择。
- **实时 GitHub 搜索/定制**：Doramagic v14 起废弃，CLI-Anything 也不做。
- **GUI agent 操作**：Doramagic 从未计划，CLI-Anything 是为解决这个问题而生——两者目标不重叠。

---

## 四、三条路径建议

### 路径 A：放弃 Skill Plugin 路线，直接用 CLI-Anything

**含义**：停止 Doramagic Skill Plugin 开发，转而用 CLI-Anything 生成 zvt/backtrader 等的 CLI 包装。

**Pros**：
- 直接复用 CLI-Hub 的 30+ agent 平台分发渠道
- 不需要自建 SKILL.md 生成工程
- CLI-Anything 框架已经在 33+ 软件上验证

**Cons**：
- **根本上不适用**：zvt/backtrader/qlib 是 Python 库，通过 `import` 使用，不需要 CLI 包装。CLI-Anything 的价值在于 GUI 应用的 agent 化——把它用在 Python 库上，等于用锤子拧螺丝。
- 放弃 86 条领域约束、32 条反模式、A/B benchmark 体系——这些是 CLI-Anything 架构上无法提供的。
- 直接等同于宣布"Doramagic 对 quant Python 库没有独有价值"。这与 V6 benchmark 证据相悖。

**推荐**：**否定**。证据不支持这个路径。

---

### 路径 B：Doramagic 作为 CLI-Anything 的 finance vertical 插件

**含义**：在 CLI-Anything 框架内开发金融专项 CLI，晶体以 CLI-Anything 格式分发，依赖 CLI-Anything 基础设施。

**Pros**：
- 立即获得 CLI-Hub 分发渠道
- 技术框架现成
- 与 CLI-Anything 社区对齐

**Cons**：
- **产品定位根本不同**：CLI-Anything 生成的是可执行工具，Doramagic 生成的是声明式知识（seed.yaml）。两者的交付物形态不兼容——你无法把 86 条 T+1 约束"包装成 CLI"。
- **丧失核心差异**：订阅 CLI-Anything 基础设施意味着接受"质量 = 测试通过率"的量纲，放弃 A/B benchmark 体系。
- **SKILL.md 已是公共标准**：采用 SKILL.md 格式本来就是 Doramagic 计划的，不需要"订阅"任何人——SKILL.md 是生态标准，不是 CLI-Anything 专有格式。

**推荐**：**否定**。"订阅 CLI-Anything 基础设施"是个伪命题——两者技术栈不重合，没有可以订阅的部分。

---

### 路径 C：两者互补，各走各的（同时采用 SKILL.md 分发标准）✅

**含义**：Doramagic 独立做 Skill Plugin，采用 SKILL.md 标准（已是行业标准，非 CLI-Anything 专有）；产出晶体可同时在 CLI-Hub、ClawHub、GitHub 分发；不与 CLI-Anything 重叠，不为其打工。

**Pros**：
- 产品定位互补：CLI-Anything 覆盖 GUI 应用，Doramagic 覆盖 Python 金融库——两者用户几乎不重叠。
- SKILL.md 分发格式采用成本极低（写 SKILL.md 是 Doramagic Skill Plugin 计划的一部分，不是额外工程）。
- 可以考虑在 CLI-Hub 注册 Doramagic Finance Skills，扩大分发渠道（免费的流量，零成本合作）。
- 保留 Doramagic 的知识层护城河（领域约束 + 反模式 + benchmark），这是 CLI-Anything 结构上无法提供的。

**Cons**：
- 分发渠道建设（Doramagic.ai + ClawHub）仍需自建——无法借力 CLI-Anything 已有的用户基。
- SKILL.md 生态竞争激烈（2,636+ skills 存在），在通用层无差异化——必须靠领域深度而非分发格式取胜。
- 如果 Doramagic Skill Plugin 做了 CLI-Anything 也可以做的内容（如通用知识注入），竞争压力来自整个 SKILL.md 生态，不仅是 CLI-Anything。

**合理的合作边界**：
```
Doramagic Skill Plugin 格式 → zvt-quant-skill/SKILL.md
  ↓ 分发到
    Doramagic.ai（主渠道）
    GitHub（镜像）
    ClawHub.ai
    CLI-Hub（联合注册，拓渠道）  ← 这是唯一值得和 CLI-Anything 合作的点
```

**推荐**：**采用**。

---

## 五、一句话结论

**CLI-Anything 和 Doramagic Skill Plugin 的分发层形式高度相似（都走 SKILL.md 生态），但产品内核完全不同：CLI-Anything 为 GUI 应用生成可执行 CLI 工具，Doramagic 为 Python 金融库注入声明式领域知识——目标软件不重叠，交付物不重叠，质量量纲不重叠，护城河不重叠。CEO 犹豫有道理，但犹豫的来源是"都用 SKILL.md"的表象相似，而非产品内核相似。建议路径 C：Doramagic 独立做 Skill Plugin，采用 SKILL.md 分发标准，可将晶体联合挂到 CLI-Hub 扩渠道，但不订阅、不依赖、不合并。V6 +22pp 延展度证明 Doramagic 的知识层护城河是真实的，而非 CLI-Anything 可复制的。**

---

## 附录：数据来源与可信度评级

| 来源 | 类型 | 可信度 |
|---|---|---|
| CLI-Anything README（raw.githubusercontent.com） | 一手文档 | 高 |
| cli-anything-plugin README（raw.githubusercontent.com） | 一手文档 | 高 |
| CLI-Hub 官网（clianything.cc）| 一手文档 | 高 |
| Doramagic v6 worklog § 三（345 prompts, 0 failed） | 一手实验数据 | 高 |
| Doramagic PRODUCT_CONSTITUTION.md v3.1 | 一手文档 | 高 |
| Doramagic finance-bp-009-v6.1.seed.yaml（AP-* 条目） | 一手产物 | 高 |
| WebSearch："2,636 skills"等生态数字 | 第三方报道 | 低（不引用为主要论据） |

**明确的信息盲区**：CLI-Anything 的内部路线图、未公开的金融垂直计划、HKUDS 的商业策略。本分析仅基于公开信息。如果 CLI-Anything 有未公开的金融知识注入模块，本分析的部分结论需要修正。

---

*分析完成时间：2026-04-21*  
*分析基于：HKUDS/CLI-Anything GitHub 公开信息 + Doramagic 内部文档*
