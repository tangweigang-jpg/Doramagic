# AI Agent 工程项目跨项目分析：最大公约数与项目打架

> 分析对象：superpowers (obra/superpowers)、gstack (garrytan/gstack)、OpenClaw (openclaw/openclaw)
> 分析日期：2026-03-16
> 方法论：基于灵魂提取文档、README、架构文档、SKILL.md、CLAUDE.md 的结构化对比

---

## 一、最大公约数（三个项目的共识知识）

### 共识 1：CLAUDE.md / SKILL.md 是给 AI 的行为规范，不是给人的文档

| 项目 | 体现 |
|------|------|
| superpowers | Description 是触发器不是摘要；每个 SKILL.md 控制 AI 行为模式，核心内容 <500 字 |
| gstack | SKILL.md.tmpl 模板防腐系统，从源码自动生成命令参考；SKILL.md 是 Claude 在 skill 加载时读取的唯一指令 |
| OpenClaw | CLAUDE.md 316 行开发规范，明确称之为"给 AI 的员工手册"；包含 auto-close labels、多 agent 安全规则、git 操作规范 |

**support_independence**: 高。三个项目独立到达。superpowers 从 prompt engineering 出发，gstack 从工作流自动化出发，OpenClaw 从多人协作治理出发，殊途同归。

**Doramagic 价值**: **极高**。Soul Extractor 的最终产物就是 CLAUDE.md。这条共识验证了输出格式的正确性——三个独立项目都认为 CLAUDE.md 是 AI 行为控制的核心载体。提取质量直接决定 AI 行为质量。

---

### 共识 2：上下文是稀缺资源，必须主动管理

| 项目 | 体现 |
|------|------|
| superpowers | 核心文件严控 <500 字；fresh-subagent-per-task 防止上下文污染 |
| gstack | 每个 skill 是独立认知模式，不混合；SKILL.md 只包含该 skill 需要的信息，不做全局 dump |
| OpenClaw | CLAUDE.md 按职责分区（project structure / build / coding style / testing / git / security），agent 按需读取相关段落 |

**support_independence**: 高。superpowers 从 token 经济学出发（"上下文是公共资源"），gstack 从认知模式分离出发（"Planning ≠ Review"），OpenClaw 从大规模代码库的信息过载出发。三个不同的问题域，同一个结论。

**Doramagic 价值**: **高**。Soul Extractor 的输出必须遵守 token 预算。当前 v0.9 CLAUDE.md 5.6KB 已经偏短，但方向正确。关键是信息密度，不是信息量。

---

### 共识 3：错误处理面向 AI agent 而非人类

| 项目 | 体现 |
|------|------|
| superpowers | 反合理化设计——预判 LLM 跳步的借口并逐一封杀；Iron Law 用零例外语言 |
| gstack | ARCHITECTURE.md 明确写道 "Errors are for AI agents, not humans"；每条错误消息包含下一步行动指引（"Run `snapshot -i` to see available elements"） |
| OpenClaw | 7 条多 agent 安全规则；PR truthfulness 验证——"Never merge based only on AI rationale"；bug-fix 必须提供 symptom evidence + verified root cause |

**support_independence**: 高。superpowers 关注 LLM 行为偏差的预防，gstack 关注工具错误消息的可操作性，OpenClaw 关注多 agent 协作时的信任验证。三个完全不同的切入角度。

**Doramagic 价值**: **高**。提取出的知识如果被 AI 误用，需要有纠错信号。Soul Extractor 的 fact-checking gate (Stage 3.5) 正是这个方向，但目前只在提取阶段做校验，运行时的纠错尚未设计。

---

### 共识 4：显式声明下一步，杜绝隐式跳转

| 项目 | 体现 |
|------|------|
| superpowers | Skill chaining——每个 stage 结束时显式声明下一步是什么 |
| gstack | plan-ceo-review 的 10 个 section 之间强制 **STOP + AskUserQuestion**；模式选择后 "commit fully, do not silently drift" |
| OpenClaw | 工作流分离：`/reviewpr` → `/landpr` 显式管线；committer 脚本替代手动 git add/commit 防止遗漏 |

**support_independence**: 中高。superpowers 和 gstack 都在 Claude Code 生态中，可能有间接影响（Garry Tan 可能看过 superpowers）。但 OpenClaw 作为平台项目，从工程流程治理独立到达同一结论。

**Doramagic 价值**: **高**。Soul Extractor 的 6-stage pipeline 已经采用了这个模式。验证了架构方向正确。

---

### 共识 5：测试分层——免费的先跑，昂贵的后跑

| 项目 | 体现 |
|------|------|
| superpowers | TDD for documentation——先写失败场景，再写 skill |
| gstack | 三层测试：Tier 1 静态验证（免费, <5s）→ Tier 2 E2E（~$3.85, ~20min）→ Tier 3 LLM-judge（~$0.15, ~30s）；"catch 95% of issues for free" |
| OpenClaw | Vitest + V8 覆盖率阈值 70%；prek pre-commit hooks 跑同 CI 检查；live tests 需要真实 API key 才触发 |

**support_independence**: 高。gstack 的三层模型最显式，但三个项目独立地实现了"先便宜后昂贵"的验证策略。

**Doramagic 价值**: **中高**。Soul Extractor 的 validate_extraction.py（免费）→ benchmark（需要 API 调用）已经是这个模式。可以更显式地分层。

---

### 共识 6：安全/信任边界是一等公民

| 项目 | 体现 |
|------|------|
| superpowers | 每个 skill 声明 allowed-tools 白名单；Iron Law 级别的约束零例外 |
| gstack | 浏览器安全模型——localhost-only + bearer token + cookie 不落盘 + Keychain 用户审批；shell injection 通过硬编码路径 + `Bun.spawn()` 显式参数数组防护 |
| OpenClaw | 7 条多 agent 安全规则；SECURITY.md 先读再做安全决策；CODEOWNERS 限制安全敏感路径修改；prompt injection 防范在模型选择建议中体现 |

**support_independence**: 高。三个项目从完全不同的安全威胁模型出发（skill 权限/浏览器安全/多 agent 协作安全），但都将安全约束提升到架构级别而非事后补丁。

**Doramagic 价值**: **中**。Soul Extractor 当前面临的主要安全问题是幻觉内容注入（exp07 的 MiniMax 幻觉事故）。证据绑定 (P0) 本质上是信任边界设计。

---

## 二、项目打架（三个项目的分歧点）

### 分歧 1：AI 应该自主行动还是等待人类指令？

| 项目 | 立场 |
|------|------|
| superpowers | **高度自主**——"1% Rule: 有可能就必须调用"；AI 应主动行动，不要找借口不做 |
| gstack | **模式内自主，模式切换需人类**——AI 在选定的认知模式内自主行动（review 时深入挖 bug），但切换模式（plan→ship）需要人类显式触发 |
| OpenClaw | **受约束的自主**——多 agent 安全规则严格限制 AI 自主行为（不得自主 stash/切分支/force push）；"high-confidence answers only: verify in code; do not guess" |

**分歧原因**: 场景不同。superpowers 是单用户辅助工具，信任度高；gstack 是个人工作流，需要在速度和安全间平衡；OpenClaw 是多 agent 协作的生产平台，安全优先。

**Doramagic 适合**: gstack 的立场——"模式内自主"。Soul Extractor 的每个 Stage 内应尽量自主，但 Stage 之间需要显式检查点（特别是 Stage 3.5 的 fact-checking gate）。

---

### 分歧 2：Skill/模块粒度——细颗粒独立 vs 粗颗粒完整

| 项目 | 立场 |
|------|------|
| superpowers | **极细颗粒**——14 个独立 skill，每个 <500 字，通过 skill chaining 组合 |
| gstack | **中等颗粒**——8 个 skill，每个是完整的认知模式（plan-ceo-review 单文件 500 行） |
| OpenClaw | **粗颗粒**——整个平台一个 CLAUDE.md 316 行，按职责分区但不分文件 |

**分歧原因**: 不同的设计哲学。superpowers 追求可组合性和 token 效率；gstack 追求单次交互的深度和完整性；OpenClaw 追求一致性和可维护性。

**Doramagic 适合**: superpowers 的立场。Soul Extractor 已经是多 Stage pipeline，每个 Stage 独立且可独立验证。但 gstack 的"深度模式"提醒我们：当一个 Stage 需要深入推理时（如 Stage 1 灵魂发现），不应拆得太碎。

---

### 分歧 3：模板驱动 vs 自由生成

| 项目 | 立场 |
|------|------|
| superpowers | **模板驱动**——few-shot examples 严格规定输出格式，每条 rule 必须有 Evidence 字段 |
| gstack | **模板 + 自动生成混合**——SKILL.md.tmpl 人写散文 + `{{COMMAND_REFERENCE}}` 占位符从代码自动填充 |
| OpenClaw | **约定驱动**——不提供模板，但通过 316 行规范约定行为（命名、格式、流程） |

**分歧原因**: 使用对象不同。superpowers 面向可能幻觉的 LLM，模板是防护栏；gstack 面向确定性的代码文档，模板是防腐剂；OpenClaw 面向有判断力的人类开发者+AI，约定就够。

**Doramagic 适合**: superpowers 的立场。Soul Extractor 面临与 superpowers 相同的幻觉风险。exp07 证明了无模板约束的 MiniMax 会幻觉不存在的命令。模板驱动 + 证据绑定是必须的。

---

### 分歧 4：持久化 vs 无状态

| 项目 | 立场 |
|------|------|
| superpowers | **无状态**——每次 fresh subagent，no carryover |
| gstack | **强持久化**——persistent Chromium daemon、QA reports 累积、retro JSON snapshots 做趋势跟踪、Greptile FP 历史记忆 |
| OpenClaw | **选择性持久化**——session logs + credentials 持久化，但 agent 会话本身无状态 |

**分歧原因**: 价值取向不同。superpowers 认为上下文污染的风险 > 状态丢失的成本；gstack 认为状态积累的价值 > 污染的风险；OpenClaw 在两者间取平衡。

**Doramagic 适合**: gstack 的立场——**持久化是核心竞争力**。Doramagic 的飞轮（提取越多 → 知识图谱越可靠）本质上是持久化积累。但提取过程本身应该用 superpowers 的无状态模式（fresh subagent 防止上下文污染）。

---

### 分歧 5：Build for integration vs Build for deletion

| 项目 | 立场 |
|------|------|
| superpowers | **Build for composability**——skill 之间松耦合，可以单独使用也可组合 |
| gstack | **Build for deletion**——每个 skill 可以独立删除，不影响其他；ARCHITECTURE.md 的 "What's intentionally not here" 明确列出不做的事 |
| OpenClaw | **Build for integration**——plugin 架构、channel-agnostic、全渠道集成是核心卖点 |

**分歧原因**: 产品阶段不同。superpowers 是工具集，gstack 是个人工具箱，OpenClaw 是平台。工具集追求可组合，工具箱追求可替换，平台追求可集成。

**Doramagic 适合**: 混合——提取引擎 build for composability（各 Stage 可独立使用），知识图谱 build for integration（跨项目关联是核心价值）。

---

## 三、独创知识（每个项目独有的）

### superpowers 独创

| 知识 | 描述 | 独创性置信度 |
|------|------|------------|
| **反合理化设计** | 不是告诉 AI "做什么"，而是列出 AI "不做的借口"并逐一封杀。源于说服力研究对 LLM 的适用性 | **95%** — 其他两个项目完全没有这个概念 |
| **1% Rule** | "有 1% 的可能需要调用工具，就必须调用"——将 LLM 行为偏差（懒惰跳步）量化为概率阈值 | **90%** — gstack 和 OpenClaw 都用定性约束 |
| **TDD for Documentation** | 先写 AI 会怎么失败，再写 skill，再用失败场景对抗测试 | **85%** — gstack 有测试但不是 TDD 驱动 |

### gstack 独创

| 知识 | 描述 | 独创性置信度 |
|------|------|------------|
| **显式认知档位 (Cognitive Gears)** | 将"什么类型的思维"作为可切换模式——Founder taste ≠ Eng rigor ≠ Paranoid review ≠ Fast execution | **95%** — 其他项目无此概念 |
| **持久化浏览器守护进程** | 编译二进制 + localhost HTTP + bearer token + 30min idle timeout 的 daemon 架构；sub-second latency | **95%** — 完全独有的技术实现 |
| **SKILL.md 模板防腐系统** | 人写散文 + 代码自动填充占位符 → committed 且 CI 可验证 → "if command exists in code, it appears in docs" | **90%** — 优雅地解决了文档与代码同步问题 |
| **Greptile 双层审查** | 外部 AI 审查 + 内部 AI 分类（valid/already-fixed/false-positive）+ FP 历史记忆 | **85%** — 独有的人机协作模式 |

### OpenClaw 独创

| 知识 | 描述 | 独创性置信度 |
|------|------|------------|
| **多 Agent 安全规则体系** | 7 条规则覆盖 stash/branch/push/commit/worktree/unrecognized files/lint churn——为多个 AI agent 并行工作设计的协作安全协议 | **95%** — 完全独有，其他两个是单 agent |
| **Gateway = 控制平面 / Assistant = 产品** | 将基础设施（路由/状态/安全）和产品体验（对话/语音/canvas）架构上分离 | **90%** — 平台级架构概念 |
| **PR 真实性验证** | bug-fix PR 必须 symptom evidence + verified root cause + regression test；拒绝仅基于 AI 推理的合并 | **90%** — 反 AI 幻觉的治理流程 |
| **Auto-close label 自动化治理** | 11 个 `r:*` 标签 + GitHub Actions 自动回复/关闭/锁定——用自动化替代人工 triage | **80%** — 大规模开源项目的独有需求 |

---

## 四、对 Doramagic 的最终建议

### 建议 1：将"反合理化"注入 Soul Extractor 的每个 Stage

**来源**: superpowers 独创 × 三项目共识（错误处理面向 AI）

当前 Stage 指令告诉模型"做什么"，但没有列出"不做的借口"。exp07 中 MiniMax 跳过 assemble-output.sh 自行组装，正是缺少反合理化防护的后果。

**具体行动**: 每个 Stage 文件末尾增加 `## 你不能跳过这个 Stage 的理由` 段落，列出 3-5 个模型可能找的借口并逐一封杀。参考 superpowers 的 Anti-rationalization checklist 格式。

---

### 建议 2：为跨项目分析引入"认知档位"概念

**来源**: gstack 独创（Cognitive Gears）× 共识 2（上下文管理）

当前跨项目分析是单一模式——读所有灵魂、找公约数、找分歧。但 gstack 证明了显式模式切换的价值。

**具体行动**: `compare_projects.py` 实现 3 个档位：
- **CONSENSUS 模式**：只找共识，输出公约数 + support_independence 评分
- **CONFLICT 模式**：只找分歧，输出分歧点 + 分歧原因分析
- **STITCH 模式**：基于前两个模式的输出，生成 STITCH_MAP

每个模式用独立 prompt，不混合。这样跨项目分析的 token 消耗和信息密度都更可控。

---

### 建议 3：借鉴 gstack 的模板防腐系统，为 Soul Extractor 输出建立 validate-on-commit 机制

**来源**: gstack 独创（SKILL.md.tmpl 防腐）× 共识 5（测试分层）

gstack 的 `gen-skill-docs.ts --dry-run + git diff --exit-code` 在 CI 中捕捉文档漂移。Soul Extractor 可以类似地建立"提取结果防腐"。

**具体行动**: `validate_output.py` 扩展为 3 层验证（对齐 gstack 的测试分层）：
- **Tier 1（免费, <5s）**: 结构验证——section 存在性、rule 计数、repo_facts.json 命令白名单匹配
- **Tier 2（低成本, <60s）**: 语义验证——每条 CRITICAL rule 的 Evidence 字段解析到真实 file:line
- **Tier 3（需 API, <5min）**: LLM-judge 验证——对提取结果的可操作性和准确性评分

---

### 建议 4：将 OpenClaw 的多 Agent 安全规则抽象为 Soul Extractor 的"提取安全协议"

**来源**: OpenClaw 独创（多 Agent 安全）× 共识 6（安全一等公民）× 分歧 1（自主性）

OpenClaw 的 7 条安全规则是为多个 AI agent 并行工作设计的。当 Soul Extractor 接入多个提取模型（MiniMax、Claude、Gemini）时，面临类似的信任问题。

**具体行动**: 制定 Soul Extractor 提取安全协议：
1. **不合并未验证卡片**（类比 "Never merge based only on AI rationale"）
2. **幻觉内容隔离**（类比 "keep unrelated WIP untouched"）——未通过 fact-check 的卡片进 `unverified_cards/`
3. **模型来源标注**（类比 OpenClaw 的 commit attribution）——每张卡片标注提取模型
4. **跨模型交叉验证**——同一知识被 2+ 模型独立提取时标注 support_independence: high

---

### 建议 5：从三个项目中提取"AI Agent 工程通用知识"，作为 Doramagic 领域图谱的第二个测试领域

**来源**: 全局视角——三个项目验证了跨项目分析的可行性

SEO/GEO 是第一个验证领域（4 个项目）。AI Agent 工程可以是第二个（superpowers + gstack + OpenClaw + 未来更多）。这个领域对 Doramagic 自身有直接价值——提取出的共识知识可以直接改进 Soul Extractor。

**具体行动**: 将本分析的 6 条共识和 5 条分歧结构化为 `knowledge_atoms`，纳入 `domain_knowledge_map`。下一步找 2-3 个更多的 AI Agent 项目（如 Cursor Rules、aider conventions、continue.dev）扩展样本量，验证哪些共识是真正的领域共识而非 3 个项目的巧合。

---

## 附录：分析置信度声明

| 维度 | 置信度 | 理由 |
|------|--------|------|
| 共识知识完整性 | 中高 | 三个项目文档覆盖度不同——superpowers 通过 soul-extractor.md 间接分析，gstack 有完整 README + ARCHITECTURE，OpenClaw 有 CLAUDE.md + README 前 100 行 |
| support_independence 判断 | 中 | 无法确认 Garry Tan 是否参考过 superpowers；OpenClaw 60K+ stars 项目的设计决策来源更多样 |
| 独创性评估 | 中高 | 仅基于三个项目的对比，不排除其他未分析项目有类似知识 |
| Doramagic 建议可行性 | 高 | 5 条建议均基于已有基础设施（validate_output.py、compare_projects.py、Stage pipeline）的增量扩展 |
