# Doramagic 元知识：OpenClaw Skill 生产规范

> 版本: 0.2.0 | 日期: 2026-04-01
> 基于: AgentSkills 规范 + OpenClaw Runtime + ClawHub skill-format.md
> 来源: Claude Code 源码分析 + ClawHub 36 个 Skill 灵魂提取 + 12 个成功 Skill 深度研究 + Grok/Google 交叉审阅后验证修订
> 目的: Doramagic 在生成任何 OpenClaw Skill 时必须遵守的规范

---

## 一、定位

Doramagic 是 OpenClaw Skill。Doramagic 的产出也是 OpenClaw Skill。
本文档定义了"一个合格的 OpenClaw Skill 长什么样"以及"怎么做才能在 OpenClaw 上稳定运行"。

---

## 二、Skill 的本质

Skill 是一个 SKILL.md 文件 — 结构化 Markdown，作为可注入的提示词模块供宿主 LLM 解释和执行。

**核心认知：SKILL.md 就是产品。** 不是脚本，不是管线。宿主 LLM 读到的 SKILL.md 内容 = 用户的全部体验。一个有完美 SKILL.md 但没有脚本的 Skill，优于一个有精妙脚本但平庸 SKILL.md 的 Skill。

---

## 三、目录结构

```
skill-name/
  SKILL.md          # 必需：元数据 + 指令（≤80 行）
  references/       # 可选：深度知识（按需加载）
  scripts/          # 可选：确定性脚本（exec 不保证可用）
  assets/           # 可选：模板、数据文件
```

**硬规则：**
- 必须是 `skill-name/SKILL.md` 目录格式，单文件不被发现
- 目录名 = name 字段 = 斜杠命令路由
- 用户数据和 Skill 代码必须分离（升级会覆盖 Skill 目录）

---

## 四、Frontmatter 规范

### 4.1 必需字段

| 字段 | 约束 | 说明 |
|------|------|------|
| name | 1-64 字符，kebab-case，匹配目录名 | 不可包含 "anthropic"、"claude" |
| description | 1-1024 字符（实际 ≤250 生效） | **最关键字段，决定是否被触发** |

### 4.2 可选字段

| 字段 | 类型 | 说明 |
|------|------|------|
| version | string | SemVer 格式（如 1.0.0），ClawHub 发布推荐，`clawhub sync --bump` 依赖此字段 |
| allowed-tools | string | 预授权工具列表（实验性，不可靠） |
| model | string | opus / sonnet / haiku / inherit |
| effort | string | low / medium / high / max |
| context | string | fork = 子代理隔离运行 |
| agent | string | 配合 fork 指定代理类型 |
| paths | string/list | glob 模式，条件激活 |
| hooks | object | 生命周期钩子（仅 Claude Code 可用） |
| shell | string | bash（默认）或 powershell |
| argument-hint | string | 参数提示 |
| disable-model-invocation | bool | true = 仅用户手动触发 |
| user-invocable | bool | false = 仅 LLM 自动触发 |

### 4.3 metadata.openclaw 扩展字段

OpenClaw 平台特有的元数据字段，声明在 `metadata.openclaw` 下（别名：`metadata.clawdbot`、`metadata.clawdis`）。

| 字段 | 说明 |
|------|------|
| os | 平台门控，如 `["darwin", "linux"]`。不匹配则 Skill 不加载 |
| requires.bins | PATH 中必须存在的二进制，如 `["python3", "git"]` |
| requires.anyBins | 至少一个存在即可 |
| requires.env | 必需的环境变量名 |
| requires.config | 必需的配置值 |
| emoji | macOS Skills UI 图标 |
| skillKey | 覆盖默认调用键（目录名与命令名不一致时） |
| always | true = 跳过所有门控，始终加载 |
| homepage | Skill 文档链接，在 UI 中显示 |
| install | 自动依赖安装规格（见 4.5 节） |

### 4.4 已知的 frontmatter 陷阱

| 问题 | 说明 |
|------|------|
| YAML 含冒号的值 | 含 `: `（冒号+空格）的值必须加引号，否则静默解析失败（[Issue #22134](https://github.com/openclaw/openclaw/issues/22134)） |
| metadata 嵌套深度 | 官方示例使用多行 YAML，但历史上有单行 JSON 更安全的社区经验。建议简单值用 YAML，复杂嵌套（如 install）用 YAML 并严格加引号 |

### 4.5 install 字段（自动依赖安装）

OpenClaw 检测到缺失依赖时可自动触发安装。4 种 installer：

| kind | 说明 | 示例 |
|------|------|------|
| brew | Homebrew | `{kind: brew, formula: jq, bins: [jq]}` |
| node | npm 全局包 | `{kind: node, package: typescript, bins: [tsc]}` |
| go | Go install | `{kind: go, package: "github.com/x/y@latest", bins: [y]}` |
| uv | Python uv | `{kind: uv, package: ruff, bins: [ruff]}` |

每个 installer 可指定 `os` 做平台特定安装。

### 4.6 metadata 格式示例

```yaml
# 推荐写法（多行 YAML，值含冒号必须加引号）
metadata:
  openclaw:
    os: [darwin, linux]
    emoji: "🔍"
    requires:
      bins: [python3, git]
      config: [ANTHROPIC_API_KEY]
    install:
      - kind: brew
        formula: jq
        bins: [jq]
        os: [darwin]
```

---

## 五、Description 写法（最关键）

### 5.1 机制

- 没有算法做意图匹配，Claude 纯靠语言理解判断是否触发
- 上下文预算：窗口的 1%，回退上限 8,000 字符
- 每个 Skill 最多 250 字符被加载（超出截断）
- 内置 Skill 永不截断，第三方按预算截断

### 5.2 规则

| 做 | 不做 |
|-----|------|
| 动作动词开头 | "A tool for..." 开头 |
| 15-25 词，一句话 | 关键词堆砌 |
| 写能力 + 触发场景 | 只写能力不写场景 |
| 包含用户实际会说的话 | 用开发者术语 |
| "Use when:" 列 3 个场景 | 泛泛而谈 |

### 5.3 示例

```
# 差
Helps with stock analysis

# 好
Analyze stocks with technical indicators, fundamental metrics, and risk scoring. Use when evaluating buy/sell decisions, screening watchlists, or building investment reports.

# 更好（包含用户实际用语）
Analyze stocks, score risk, and generate buy/sell/hold recommendations. Use when asked "should I buy TSLA", "analyze my portfolio", or "what's happening with crypto today".
```

---

## 六、SKILL.md 正文规范

### 6.1 长度

| 标准 | 行数 | 说明 |
|------|------|------|
| Anthropic 官方上限 | 500 行 | 已被社区证明太宽松 |
| **社区实证最佳** | **30-80 行** | 超过 ~80 行 LLM 注意力急剧衰减 |
| 建议推荐 | 50-60 行 | 平衡信息量和遵循度 |

### 6.2 写什么

| 写 | 不写 |
|----|------|
| 做什么（WHEN + HOW） | 是什么（WHAT — LLM 已知） |
| 铁律（不可违反的约束） | 长篇解释（放 references/） |
| 反模式清单（LLM 常犯的错） | 架构细节（触发"自信伪装者"） |
| 决策树（条件分支） | 线性长步骤 |
| 输出格式模板 | 输入格式说明（LLM 能推断） |
| [AUTO]/[CONFIRM]/[INPUT] 标注 | 模糊的"请注意" |

### 6.3 Iron Law 模式

每个 Skill 应有一条不可违反的铁律，放在最顶部：

```markdown
## IRON LAW
NO OUTPUT WITHOUT EVIDENCE TRACING.
Every claim must link to a verifiable source.
If you cannot cite evidence, say "I don't know" — do not fabricate.
```

### 6.4 反模式清单

列出 LLM 常见的"自我欺骗"，让它识别自己何时在犯错：

```markdown
## STOP if you catch yourself doing these
- Generating advice not grounded in data → HALLUCINATION
- Copying generic templates as "analysis" → PARROTING
- Skipping risk assessment because "it's obvious" → LAZY VALIDATION
- Using training data defaults instead of real-time data → STALE KNOWLEDGE
```

---

## 七、渐进披露（Token 经济学）

### 7.1 三层模型

| 层 | 内容 | 加载时机 | Token 预算 |
|----|------|---------|-----------|
| L1 | name + description | 会话启动，所有 Skill 常驻 | ~100 tokens/skill |
| L2 | SKILL.md 正文 | Skill 被触发时加载 | ≤5000 tokens（建议 ≤2000） |
| L3 | references/ + scripts/ | SKILL.md 中引用时按需读取 | 无限制 |

### 7.2 关键原则

- L1 是唯一保证常驻上下文的层 — description 必须精炼
- L2 不是常驻的，每次调用重新加载
- L3 需要 SKILL.md 明确引导 LLM 去读（"Read references/risk-guide.md before proceeding"）
- Skill 上下文与对话上下文竞争同一窗口 — 大 Skill 挤出对话历史

---

## 八、平台差异（双平台适配）

### 8.1 Claude Code vs OpenClaw

| 能力 | Claude Code | OpenClaw |
|------|-------------|---------|
| Hooks | ✅ 完整支持（PreToolUse/PostToolUse/Stop 等） | ⚠️ 部分支持（command:new/reset/stop、session:compact、agent:bootstrap 等，但无 postinstall/skill:upgrade） |
| context: fork | ✅ 子代理隔离 | ❌ 不支持 |
| exec/Bash 工具 | ✅ 可靠 | ⚠️ 不保证（command-dispatch:tool 不含 exec） |
| 动态注入 !`cmd` | ✅ 支持 | ❌ 不支持 |
| 工具名称 | Bash/Read/Write/Edit | exec/read/write |
| metadata 格式 | 多行 YAML OK | 多行 YAML OK（含冒号的值必须加引号） |
| Sub-skill 路由 | SKILL-*.md 同目录 | 非标准 |
| .clawhubignore | 不适用 | 可选，控制发布时忽略的文件（也尊重 .gitignore） |

### 8.2 适配策略

生成的 Skill 必须以 OpenClaw 为底线设计：
- 不依赖 exec — 设计为 exec 不可用时仍能产出有价值的建议性输出
- 不依赖 Claude Code 独有的 hooks — OpenClaw 有部分 hooks 支持，但事件集不同
- 不依赖 fork — 默认 inline 模式
- metadata 用多行 YAML，含冒号的值加引号
- 工具名用 OpenClaw 版本（exec/read/write）

**混合模式（推荐）：** OpenClaw 上 50-60% 建议性输出 + 告诉用户"运行 `python scripts/xxx.py` 获得完整功能"。

---

## 九、致命失败模式（必须防御）

### 9.1 CRITICAL — 自信伪装者（F01）

**症状：** LLM 读了 SKILL.md 后"理解了"，直接模拟输出，从未运行任何脚本。
**根因：** RLHF 让 LLM 优先"有帮助"。当文档描述了架构和输出格式，LLM 有足够信息模拟结果。
**防御：**
- README 描述"你得到什么"，不描述"内部怎么工作"
- SKILL.md 不暴露架构细节
- 加入验证命令让用户区分真假输出

### 9.2 CRITICAL — 友好接管（F02）

**症状：** LLM 运行 1-2 步后决定"我自己来更好"，放弃管线自己生成。
**根因：** LLM 的"帮助性"本能覆盖指令遵循。当 LLM 看到全局管线视图，它有信心接管。
**防御：**
- 控制反转 — 每步只给当前步骤上下文，不给全局视图
- 信息饥饿比否认更有效

### 9.3 CRITICAL — 脚本执行跳过（F03）

**症状：** LLM 被指令运行脚本但从未调用 exec 工具。
**根因：** OpenClaw 的 command-dispatch:tool 上下文不含 exec。
**防御：**
- 不依赖 exec
- 设计为 exec 不可用时优雅降级

### 9.4 HIGH — SKILL.md 膨胀崩溃（F05）

**症状：** 超过 ~80 行后 LLM 跳步、择段、总结而非遵循。
**根因：** 注意力随上下文长度衰减。
**防御：** ≤80 行，逻辑推入 references/

### 9.5 HIGH — 触发短语失配（F06）

**症状：** Skill 不被自动触发或误触发。
**根因：** 作者用自己的心理模型写触发短语，非真实用户用语。
**防御：** 测试 5+ 种真实用户措辞

### 9.6 HIGH — YAML 解析静默失败（F04）

**症状：** frontmatter 中含冒号的值导致 OpenClaw 解析器静默失败。
**根因：** YAML 中未加引号的 `: `（冒号+空格）被错误解析（[Issue #22134](https://github.com/openclaw/openclaw/issues/22134)）。
**防御：** 所有含冒号的值必须加引号。复杂嵌套严格测试。

---

## 十、质量评估框架

### 10.1 六维评估（来自 SkillCompass，ClawHub ★38）

| 维度 | 权重 | 评估内容 |
|------|------|---------|
| D1 结构 | 10% | frontmatter 格式、目录结构、声明完整性 |
| D2 触发 | 15% | description 质量、触发准确率、误触发率 |
| D3 安全 | 20% | **绝对门控** — 一个 Critical 发现 = 整体 FAIL |
| D4 功能 | 30% | 核心能力、边界处理、输出稳定性 |
| D5 比较价值 | 15% | 对比直接 prompting 的增益（with vs without） |
| D6 独特性 | 10% | 与已有 Skill 的差异化 |

公式：`总分 = round((D1×0.10 + D2×0.15 + D3×0.20 + D4×0.30 + D5×0.15 + D6×0.10) × 10)`

判定：PASS (≥70 且 D3 通过) / CAUTION (50-69 或 D3 HIGH) / FAIL (<50 或 D3 CRITICAL)

### 10.2 验证方法

| 测试 | 方法 | 通过标准 |
|------|------|---------|
| 安装测试 | `openclaw skills install <name>` | 无报错 |
| 触发测试 | 5 种不同说法尝试触发 | ≥4/5 正确触发 |
| 误触发测试 | 5 种不相关说法 | 0/5 误触发 |
| 输出质量 | 对比 LLM 裸跑 vs 使用 Skill | Skill 输出明显更好 |
| 安全扫描 | VirusTotal + mcp-scan | 零 suspicious 标记 |
| 发布测试 | `clawhub publish` | 一次成功 |

---

## 十一、安全规范

### 11.1 安全检查清单（发布前必须通过）

- [ ] 无命令注入（无 eval/exec 动态代码）
- [ ] 无凭证请求（只读 env，不请求用户输入密钥）
- [ ] 无远程代码执行
- [ ] 无数据外泄 URL（无 curl 到外部服务器）
- [ ] 无提示注入（无隐藏指令、零宽字符、base64 编码指令）
- [ ] 无混淆 shell 命令
- [ ] metadata 中声明的能力与实际代码一致（**ClawHub 会做 metadata mismatch 检测**：代码中访问了未声明的 env 或 bin 会被 flag）

### 11.2 ClawHub 安全扫描机制

ClawHub 与 VirusTotal 集成，发布时自动扫描：
- 嵌入的 secrets（API keys、tokens）
- Shell 注入模式
- 未授权网络操作
- 提示注入（MITRE ATLAS 模式）
- "benign" 判定可自动通过，否则人工审核

**社区最佳实践（非官方强制，但显著提高通过率）：**
- SKILL.md 中包含 External Endpoints 表格（列出每个 URL + 数据流向）
- 包含 Trust Statement（"By using this skill, data is sent to [X]"）
- 包含 Model Invocation Note（说明自主调用行为）
- 来源：[社区 13 点检查清单](https://gist.github.com/adhishthite/0db995ecfe2f23e09d0b2d418491982c)

### 11.3 平台安全态势

OpenClaw 近期已知 CVE（影响部署决策）：
- **CVE-2026-32922** (CVSS 9.9) — 权限提升导致 RCE，影响 2026.3.11 之前版本
- **CVE-2026-25253** (CVSS 8.8) — Auth token 窃取导致 RCE
- **CVE-2026-32061** — 路径穿越，可读取敏感文件
- **CVE-2026-32049** — 超大 payload DoS

**建议：** 在容器化环境中运行 OpenClaw，使用最小权限凭证，保持版本更新。

### 11.4 去敏处理（提取知识后必须执行）

从知识来源提取内容后，发布前必须剥离：
- 贡献者人名
- 内部路径（/home/xxx/...）
- API 密钥和 token
- 内部 issue tracker URL
- 项目内部代号
- 环境变量值（只保留变量名）

---

## 十二、发布规范

### 12.1 ClawHub 硬约束

| 约束 | 值 |
|------|-----|
| 包体上限 | 50MB |
| 许可证 | MIT-0（强制） |
| GitHub 账户年龄 | >1 周 |
| Slug 规则 | ^[a-z0-9][a-z0-9-]*$ |

### 12.2 发布前检查清单（来自 kai-skill-creator 7 轮失败经验）

- [ ] 不硬编码 API 密钥
- [ ] 不加载 .env 文件
- [ ] 不使用未在 metadata.openclaw.requires 中声明的环境变量或二进制
- [ ] 文档中不放外部 API URL（除非在 External Endpoints 表格中声明）
- [ ] 含冒号的 YAML 值已加引号
- [ ] description ≤250 字符
- [ ] SKILL.md ≤80 行
- [ ] 文件数 ≤15 个
- [ ] 总包体 <12MB
- [ ] 包含 LICENSE 文件（MIT-0）
- [ ] .clawhubignore 或 .gitignore 排除了 .git、.env、node_modules 等
- [ ] version 字段使用 SemVer 格式

---

## 十三、成功模式清单

### 13.1 SKILL.md 设计模式

| 模式 | 描述 | 来源 |
|------|------|------|
| Iron Law | 一条不可违反的铁律放最顶部 | superpowers (★22K) |
| Anti-Pattern List | LLM 常见错误思维清单 | superpowers |
| Decision Tree | 条件分支而非线性步骤 | webapp-testing, mcp-builder |
| Progressive Disclosure | SKILL.md → references/ → scripts/ | 全部成功 Skill |
| Black-Box Scripts | --help 接口，不让 LLM 读源码 | webapp-testing |
| Status Protocol | DONE/BLOCKED/NEEDS_INPUT 标准返回 | superpowers |
| [AUTO]/[CONFIRM]/[INPUT] | 每步标注交互级别 | auto-create-skill |

### 13.2 架构模式

| 模式 | 描述 | 来源 |
|------|------|------|
| 渐进披露三层 | metadata / core / references | 全部 |
| 侧车状态 | 质量元数据与内容分离 | SkillCompass |
| 自动改进循环 | 评估→找最弱→改进→验证→回滚 | SkillCompass |
| 门控维度 | 非谈判质量检查（安全 = 绝对门） | SkillCompass |
| 本地预分析+LLM深度分析 | 便宜检查先筛，LLM 处理模糊案例 | SkillCompass |
| 提取→结构化→质检→发布 | 通用管线 | Skill From Memory, Skill Factory |
| 去敏处理 | 发布前剥离敏感信息 | ChenXi Skill Maker |

---

## 十四、OpenClaw 上的现实效能预期

| 场景 | 效能 | 条件 |
|------|------|------|
| 最好 | ~85% | exec 可用 + LLM 完全遵循 |
| **现实** | **50-60%** | **exec 间歇 + LLM 部分遵循** |
| 最差 | ~15-20% | exec 不可用 + LLM 忽略协议 |

**设计目标：在 50-60% 现实效能下，生成的 Skill 仍然比 LLM 裸跑有明显价值提升。**

---

## 十五、Doramagic 自身的合规检查

Doramagic 作为 OpenClaw Skill，自身也必须遵守以上所有规范：

| 检查项 | 当前状态 | 需要修复 |
|--------|---------|---------|
| SKILL.md ≤80 行 | ❌ 230 行 | 是 |
| metadata 单行 JSON | ❌ 多行 YAML | 是 |
| description ≤250 字符含触发场景 | ⚠️ 需优化 | 是 |
| 不暴露架构细节 | ❌ README 含架构 | 是 |
| 文件数 ≤15 | ❌ 207 文件 | 是 |
| 包体 <12MB | ❌ >50MB | 是 |

---

*v0.2.0 修订说明：经 Grok + Google Antigravity 交叉审阅后，逐项验证其声明（10 项中 3 项完全正确、4 项部分正确、3 项编造），仅采纳已验证的修正。*
*验证来源：ClawHub skill-format.md、docs.openclaw.ai、OpenClaw GitHub Issues、NVD CVE 数据库。*
*本文档由三份研究报告 + 12 个 ClawHub 成功 Skill 深度分析 + Claude Code 源码分析综合整理。*
