# web-access Skill 深度研究报告

**日期**: 2026-03-28
**研究对象**: [eze-is/web-access](https://github.com/eze-is/web-access) v2.4.1 (1,888 stars)
**研究方法**: Doramagic v12.1.0 灵魂提取 + 全文阅读 + 设计模式分析
**目的**: 提取可迁移到 Doramagic 的编排/鲁棒/智能设计模式

---

## 一、项目概况

web-access 是 OpenClaw 生态中的标杆 Skill，给 Claude Code 装上完整联网能力。作者一泽Eze，MIT 协议。

**核心架构**: 三层通道调度
- Layer 1: WebSearch -- 搜索引擎关键词发现
- Layer 2: WebFetch / curl / Jina -- 静态页面内容提取
- Layer 3: CDP Browser -- 反爬站点、登录态、动态页面、交互操作

**文件结构**:
- SKILL.md (243行) -- 哲学 + 技术事实 + 工具选择逻辑
- scripts/check-deps.sh -- 前置检查，启动 CDP Proxy
- scripts/cdp-proxy.mjs -- CDP 代理服务器 (Node.js, port 3456)
- scripts/match-site.sh -- 站点模式匹配
- references/cdp-api.md -- CDP API 参考
- references/site-patterns/ -- 按域名的站点经验文件（跨 session 积累）

---

## 二、灵魂提取结果

以下由 Doramagic v12.1.0 从本地副本提取。

### 设计哲学
> A skill should teach tradeoffs, not procedures -- give the AI philosophy and technical facts, then let it reason through choices itself.
> The web is too messy for rigid scripts; agents need human-like judgment.

### WHY 决策（5 条，全部 high confidence）

| 决策 | WHY |
|------|-----|
| CDP Proxy 连接用户现有 Chrome | 优先继承登录态，而非隔离 |
| 三种点击方法（JS/真实鼠标/文件上传）| 不同网站需要不同交互模式 |
| 域名级经验积累，非 session 级 | 学习跨对话持久化 |
| 并行子 Agent 共享一个 Proxy | tab 级隔离，避免浏览器实例开销 |
| SKILL.md 强调哲学而非步骤 | "讲清 tradeoff 让 AI 自己选，不替它推理" |

### UNSAID 暗雷（4 条）

| 严重度 | 暗雷 |
|--------|------|
| HIGH | AI 可访问用户所有已登录站点（银行/邮箱），无沙箱隔离 |
| MEDIUM | CDP Proxy 崩溃后 AI 丢失所有浏览器上下文，无优雅恢复 |
| MEDIUM | 站点经验文件可能过期，导致 AI 按旧模式操作失败 |
| LOW | Chrome 远程调试需重启浏览器，杀死所有 tab |

---

## 三、编排设计分析 (9/10)

### 3.1 目标驱动调度（非固定流程）

web-access 不是"先搜索-再抓取-再浏览"的瀑布流程。它的调度逻辑是：

1. 明确目标
2. 选最小充分起点
3. 过程校验
4. 完成判断

**核心特征**: 每一步的**结果**决定下一步走哪条路，而非预设流程图。

> "每一步的结果都是证据，不只是成功或失败的二元信号。"

**对比 Doramagic**: 当前管线是固定的 Step 1-2-3-4-5-6-7 线性流程。即使 Step 2 已经找到完美的 repo，Step 3 的提取深度也不会自适应。

### 3.2 升级而非切换

| web-access | Doramagic |
|------------|-----------|
| 简单请求用 WebSearch | 简单请求走 Fast Path |
| 搜索不够用 Jina | Fast Path 不够走 GitHub |
| Jina 不够用 curl | GitHub 不够走...没有了 |
| curl 不够用 CDP | **缺少终极兜底** |

web-access 有 4 层升级，Doramagic 只有 2 层（ClawHub - GitHub），且 GitHub API fallback 当前只返回 metadata，无法产出可提取的 repo。

### 3.3 子 Agent 并行分治

web-access 的子 Agent 设计非常精巧：
- 共享一个 Chrome + 一个 Proxy，tab 级隔离
- 主 Agent 只说"要什么"，不说"怎么做"
- **反暗示用词**: 避免用"搜索""爬取"，改用"获取""调研"

---

## 四、鲁棒性分析 (9/10)

### 4.1 站点经验积累（最值得借鉴的模式）

每次 CDP 操作成功后，自动将经验写入 `references/site-patterns/{domain}.md`:
- 平台特征（架构、反爬行为、登录需求）
- 有效模式（URL 模式、操作策略、选择器）
- 已知陷阱（什么会失败以及为什么）

**关键设计**: 经验标注发现日期，"当作可能有效的提示而非保证"。这是**有过期意识的知识**。

**对比 Doramagic**: brick 库是静态 JSONL，没有积累机制，没有过期意识。

### 4.2 永远先试再说

- 不预判登录需求，先尝试获取
- 不预判反爬，先用最简单的方式
- 只在"确认目标内容无法获取"时才升级

### 4.3 构造 URL 不信任

> "站点自己生成的链接天然携带完整上下文，手动构造的 URL 可能缺失隐式必要参数。"

这个原则在 Doramagic 的 GitHub 搜索中也适用——我们手动拼的搜索 query 不如 profile builder 生成的。

---

## 五、智能性分析 (10/10)

### 5.1 "Skill = 哲学 + 技术事实，不是操作手册"

这句话和 Doramagic 的 "代码说事实，AI 说故事" 完全同频。但 web-access 走得更远——它的 SKILL.md 几乎没有步骤列表，全是**判断框架**。

### 5.2 浏览哲学四步

1. 明确目标和成功标准
2. 选择最可能直达的起点
3. 用结果对照成功标准，动态调整
4. 确认完成才停止，不过度操作

这不是"怎么做"，是"怎么想"。AI 读完这个框架后能自主决策，而不是按步骤执行。

### 5.3 信息核实设计

| 信息类型 | 一手来源 |
|----------|---------|
| 政策/法规 | 发布机构官网 |
| 企业公告 | 公司官方新闻页 |
| 学术声明 | 原始论文/机构官网 |
| 工具能力/用法 | 官方文档、源码 |

> "多个媒体引用同一个错误会造成循环印证假象。"

这个原则直接适用于 Doramagic 的跨项目综合——多个 repo 复制同一个坏实践不代表那是好实践。

---

## 六、可迁移设计模式（5 个）

### 模式 1: 动态经验积累（替代静态 brick 库）

**当前**: Doramagic 的 278 块 brick 是手动策划的静态 JSONL。
**借鉴**: 每次提取完成后，自动将验证过的知识写入域经验文件。

两层 brick 架构:
- bricks/accumulated/{domain}.jsonl -- 动态积累
- bricks/curated/{framework}.jsonl -- 手动策划（现有）

设计要点:
- 积累的知识标注发现日期和来源项目
- 置信度随时间衰减（"提示而非保证"）
- 积累超过阈值时触发合并压缩（类似 Letta 的 sleeptime）

### 模式 2: 目标驱动管线调度

**当前**: Step 1-2-3-4-5-6-7 固定流程。
**借鉴**: 每步结束后检查"目标达成了吗？"，决定是否需要更深的步骤。

- 如果 soul_quality >= 7.0: 跳到编译（已经够好了）
- 如果 soul_quality >= 4.0: 运行深度 Stage 1.5（需要补充）
- 否则: 运行 web search fallback（需要外部信息）

这对应研究报告中的"基于丰富度的自适应提取深度"，但 web-access 的模式更优雅——不是预先判断丰富度，而是**用结果判断**。

### 模式 3: 反暗示 Prompt 设计

**当前**: 编译 prompt 说"Compile the strongest evidence-backed WHY knowledge"。
**借鉴**: 避免用暗示具体手段的词。

| 当前用词 | 改进用词 |
|----------|----------|
| "Extract design philosophy" | "Understand why this project exists" |
| "List anti-patterns" | "Identify what would go wrong" |
| "Compile SKILL.md" | "Build a tool that makes the AI smarter" |

### 模式 4: 经验过期意识

**当前**: brick 没有时间维度。
**借鉴**: 所有积累的知识标注时间，使用时视为"可能有效的提示"。

字段设计: statement + discovered date + source_project + confidence_decay period

### 模式 5: 循环引证检测

**当前**: 跨项目综合时，多个 repo 的相同说法被视为"共识"。
**借鉴**: 检测是否多个 repo 只是复制了同一个错误源。

- 追踪知识的**原始来源**（不是"哪个 repo 说的"，而是"这个 repo 从哪里学来的"）
- 如果 N 个 repo 的 README 都引用同一篇 blog post，那是 1 个来源不是 N 个共识
- 这强化了 Doramagic 已有的 provenance tagging 需求

---

## 七、对 Doramagic 改进路线图的影响

| 现有计划 | web-access 给出的新视角 |
|----------|----------------------|
| C 级: LLM 缓存 | 不只是缓存，是**积累**——缓存是重复用，积累是学习新知识 |
| C 级: Tree-sitter 代码骨架 | web-access 的"先看结构再决定行动"模式一致 |
| D 级: 提取记忆系统 | 升级为"站点经验"模式——按域名/框架积累，跨 session |
| B 级: 来源溯源 | 升级为"循环引证检测"——不只标来源，还验证来源独立性 |
| 未规划 | **目标驱动管线调度** -- 最大的新增项 |

---

## 八、E2E 测试副产品: v12.1.0 管线诊断

本次研究同时是 Doramagic v12.1.0 的首次真实 E2E 测试。暴露的问题:

1. **GitHub 搜索找错项目**: query "claude web browser" 找到 wgarrido/mcp-browser 而非 eze-is/web-access。profile builder 丢弃了用户明确指名的项目名。
2. **自我引用 bug**: GitHub API fallback 返回 metadata-only repo，read_repo_files("") 读了 Doramagic 自身的 README（已修复: commit 7d0ee08）。
3. **质量门禁正确拒绝**: 36.4/100，触发 template fallback。门禁系统工作正常。
4. **编译拆分工作良好**: 5/5 sections LLM 生成，0 fallback，176 行。但被质量门禁拒绝（DSD=0, WHY=0 因为基于错误 repo 的提取结果）。
5. **总耗时 268 秒**: profile 13s + ClawHub 1s + GitHub 8s + extraction 49s + synthesis 60s + compile 138s。编译是瓶颈。

---

## 九、总结

web-access 是 OpenClaw 生态中编排/鲁棒/智能三个维度都达到 9+ 分的标杆作品。它的核心启示不是技术实现细节（CDP proxy、Jina 等），而是**设计哲学**:

1. **教思考方式，不教操作步骤** -- 和 Doramagic 的灵魂一致
2. **用结果决定下一步，不用计划** -- Doramagic 需要学习
3. **知识会过期，经验要积累** -- Doramagic 的 brick 系统需要进化
4. **多个来源说同一件事 != 真理** -- Doramagic 的跨项目综合需要警惕

> "不教用户做事，给他工具。" -- 这句话在 web-access 的设计中被践行得比 Doramagic 自身更彻底。
