# 五种"将意图编译成可运行工具"方案的能力单元结构调研
日期: 2026-03-29
执行者: Claude Code（调研任务，免赛马）

---

## 调研背景

Doramagic 的核心资产是"积木"（知识能力单元）。当前积木主要通过自然语言 SKILL.md 定义。
本次调研的目标是：了解业界 5 种主流方案如何定义"能力单元"，为 Doramagic 新积木设计提供参考依据。

---

## 一、各方案核心结构描述

### 1. Anthropic Agent Skills（SKILL.md 标准）

Agent Skills 是 Anthropic 为 Claude Code 设计的一套开放标准，已被 Manus、OpenAI Codex 等平台采纳。一个 Skill 就是一个目录，核心文件是 `SKILL.md`，由两部分组成：顶部的 YAML frontmatter（结构化元数据）和其后的 Markdown 正文（自由格式执行指令）。

**Frontmatter 全字段表：**

| 字段 | 类型 | 必须 | 说明 |
|------|------|------|------|
| `name` | string | 必须 | kebab-case，≤64字符，正则 `^[a-z0-9-]+$` |
| `description` | string | 必须 | ≤1024字符，是技能触发的主要信号，应描述"何时用" |
| `allowed-tools` | list | 可选 | 预授权工具列表，支持通配符 `Bash(git:*)` |
| `license` | string | 可选 | 如 `Apache-2.0`、`MIT` |
| `compatibility` | string | 可选 | 如 `Claude Code 1.0+` |
| `metadata` | object | 可选 | 嵌套字段，如 `category`、`complexity` |

**Markdown 正文**推荐包含：执行指令、用例示例、约束指南、对子脚本/文档的引用路径。目录结构惯例：
```
my-skill/
  SKILL.md           ← 主文件（frontmatter + 指令）
  scripts/           ← Python/Bash 脚本，通过 Bash 工具调用
  references/        ← 文档，通过 Read 工具加载
  assets/            ← 模板、静态文件
```

**执行机制**：技能不直接执行代码，而是通过"提示注入 + 执行上下文修改"工作——将 SKILL.md 内容注入对话上下文，同时修改工具权限白名单，让 Claude 在该受控环境中自主执行。这是"元工具（meta-tool）"模式。

**加载分三阶段**：①启动时只加载 frontmatter（~100 token）；②被触发时加载 SKILL.md 正文（<5k token）；③执行中按需加载 scripts/references。

---

### 2. Manus Agent Skills

Manus 是一款通用自主 AI Agent，完整采用了 Anthropic 的 Agent Skills 开放标准，但在此基础上增加了**从会话自动生成 Skill** 的能力。

当用户对某次任务结果满意时，可以指令 Manus "将这个工作流打包成 Skill"。Manus 会分析成功的交互流程，自动生成 SKILL.md 文件，并打包相关脚本。这是将"成功经验 → 可复用能力单元"的闭环，无需用户手写 Markdown。

Skill 的加载机制与 Anthropic 标准一致（三阶段渐进加载）。激活方式支持：
- 自动触发：Claude 根据 description 语义匹配用户意图
- 手动触发：用户在对话框输入 `/SKILL_NAME`

**组合机制**：多个 Skill 可以组合使用，例如"市场调研 Skill"可组合浏览器导航 Skill、数据分析脚本 Skill、报告模板 Skill。组合在 LLM 层完成，不需要硬编码的管道配置。

Manus 对 SKILL.md 格式的扩展相对有限，核心差异在于**自动生成**和**对话内管理**的能力，而非格式本身。

---

### 3. n8n Workflow Nodes

n8n 是一个开源工作流自动化平台，"能力单元"是**节点（Node）**，用 TypeScript 代码定义，实现 `INodeType` 接口。

**节点类型**：
- **Trigger Node**：触发工作流，提供初始数据（如 Webhook、Schedule）
- **Action Node**：执行操作，消费并产出数据（如 HTTP Request、数据库写入）
- **Core Node**：内置的流程控制（IF/Switch/Loop/SubWorkflow）

**INodeTypeDescription 结构（TypeScript）：**
```typescript
description: INodeTypeDescription = {
  displayName: 'My Service',      // UI 显示名
  name: 'myService',              // 内部标识符（camelCase）
  group: ['transform'],           // 分类
  version: 1,
  description: 'Does X with Y',
  defaults: { name: 'My Service' },
  inputs: ['main'],               // 输入连接点
  outputs: ['main'],              // 输出连接点
  credentials: [{ name: 'myServiceApi', required: true }],
  properties: [                   // 用户可配置的 UI 字段
    {
      displayName: 'Field Name',
      name: 'fieldName',
      type: 'string' | 'number' | 'boolean' | 'options' | 'collection',
      default: '',
      description: '...',
      options: [{ name: '...', value: '...' }]
    }
  ]
}

async execute(): Promise<INodeExecutionData[][]> {
  const items = this.getInputData();
  // 处理逻辑
  return [processedItems];
}
```

**数据格式**：节点间传递 JSON 数组，每个元素是 `{ json: {...}, binary?: {...} }`。

**组合机制**：在画布上连接节点，输出自动成为下一节点的输入。支持 SubWorkflow（将一段工作流封装为可复用模块）。

**错误处理**：每个节点内置"失败重试"设置；另有 Error Trigger 节点捕获全局错误，接入告警/修复流程。

---

### 4. Zapier Triggers/Actions

Zapier 是全球最大的 no-code 集成平台，"能力单元"分为 **Trigger**（触发器）和 **Action/Search**（动作/查询）。开发者通过 Zapier Platform CLI（JavaScript）定义 integration。

**Trigger 定义结构：**
```javascript
{
  key: 'new_contact',           // 唯一标识符
  noun: 'Contact',              // 资源名称（UI 展示用）
  display: {
    label: 'New Contact',
    description: 'Fires when a contact is added'
  },
  operation: {
    inputFields: [              // 用户配置参数
      {
        key: 'tag',
        label: 'Filter by Tag',
        type: 'String',         // String/Text/Integer/Number/Boolean/DateTime/Password/Dictionary
        required: false,
        helpText: '...',
        choices: ['tagA', 'tagB'],  // 静态下拉
        altersDynamicFields: false
      }
    ],
    perform: async (z, bundle) => {    // 执行函数，z=帮助对象，bundle=上下文
      const response = await z.request('https://api.example.com/contacts');
      return response.data;
    },
    sample: { id: 1, name: 'John' },   // 必须有示例数据（供映射用）
    outputFields: [                    // 输出字段描述
      { key: 'id', label: 'ID', type: 'string' },
      { key: 'name', label: 'Name', type: 'string' }
    ]
  }
}
```

**Action（Create）** 与 Trigger 结构几乎相同，`perform` 改为 POST 请求，`inputFields` 是用户填入的数据。

**App 定义**将多个 trigger/action 注册到顶层对象：
```javascript
module.exports = {
  version: '1.0.0',
  authentication: { ... },
  triggers: { new_contact: triggerDef },
  creates: { create_contact: actionDef },
  searches: { find_contact: searchDef }
};
```

**组合机制**：Zap = 1个Trigger + N个Action，通过字段映射（field mapping）传递数据。多步 Zap 允许条件分支、搜索、过滤。组合在 UI 层完成，不是代码层。

**触发类型**：Polling（定时轮询）或 Instant（Webhook 实时）。

---

### 5. Apify Actors

Apify Actors 是云端可运行的程序单元，打包为 Docker 镜像，拥有明确定义的 JSON 输入/输出 schema。平台有 12,000+ 个 Actor 可供直接使用。

**目录结构：**
```
.actor/
  actor.json           ← 主配置文件
  input_schema.json    ← 输入 schema（JSON Schema 扩展）
  output_schema.json   ← 输出 schema
  dataset_schema.json  ← 数据集 schema
Dockerfile
src/
```

**actor.json 核心字段：**
```json
{
  "actorSpecification": 1,
  "name": "my-web-scraper",
  "title": "My Web Scraper",
  "version": "1.0",
  "buildTag": "latest",
  "dockerfile": "./Dockerfile",
  "readme": "./ACTOR.md",
  "input": "./input_schema.json",
  "storages": { "dataset": "./dataset_schema.json" },
  "defaultMemoryMbytes": 1024,
  "minMemoryMbytes": 256,
  "maxMemoryMbytes": 4096,
  "webServerMcpPath": "/mcp"
}
```

**input_schema.json**（JSON Schema + Apify 扩展）：
```json
{
  "title": "Web Crawler",
  "type": "object",
  "schemaVersion": 1,
  "properties": {
    "startUrls": {
      "title": "Start URLs",
      "type": "array",
      "editor": "requestListSources",
      "items": { "type": "object", "properties": { "url": { "type": "string" } } },
      "minItems": 1
    },
    "maxPages": {
      "title": "Max Pages",
      "type": "integer",
      "minimum": 1,
      "maximum": 1000,
      "default": 100
    }
  },
  "required": ["startUrls"]
}
```

**editor 字段**控制 UI 组件（textfield/textarea/javascript/select/requestListSources/proxy/json 等），平台据此自动生成操作界面。

**output_schema.json** 定义输出数据集的字段结构，供 MCP/API 集成时使用。**重要**：从 2025 年起 Apify 支持 `webServerMcpPath`，Actor 可直接暴露为 MCP Server。

**分发**：上传到 Apify Store（公开/私有/计费），支持 API 调用、调度、Actor 链接（Bundles）。

---

## 二、对比表

| 维度 | Anthropic Agent Skills | Manus Agent Skills | n8n Nodes | Zapier Triggers/Actions | Apify Actors |
|------|----------------------|-------------------|-----------|------------------------|--------------|
| **能力单元格式** | YAML frontmatter + Markdown | 同上（+自动生成） | TypeScript 类（INodeType） | JavaScript 对象（CLI） | JSON Schema + Docker 镜像 |
| **输入定义** | 无正式 schema，在 Markdown 中描述 | 同上 | `properties` 数组（type/default/options） | `inputFields` 数组（key/type/required/choices） | `input_schema.json`（完整 JSON Schema + editor 扩展） |
| **输出定义** | 无正式 schema，行为由 LLM 决定 | 同上 | `execute()` 返回 `INodeExecutionData[][]` | `outputFields` + `sample`（静态声明） | `output_schema.json`（字段级别声明） |
| **组合机制** | LLM 语义理解，自动调用多个 Skill | 同上，用户也可手动 `/cmd` | 画布连线，输出→输入自动传递 | Zap 字段映射，UI 层拖拽 | Bundles（Actor 链）或 API 编排 |
| **个性化支持** | description 可写用户上下文偏好；references/ 加载用户数据 | 同上，加 + 从对话自动提取偏好 | 工作流参数化，硬编码配置 | Zap 内字段默认值 | Actor 输入 default/prefill 字段 |
| **错误处理** | 无正式 schema；SKILL.md 正文可描述失败路径 | 同上 | 节点级"重试"开关；Error Trigger 节点；Try/Catch 节点 | Zapier 平台内置 retry；步骤级 filter/halt | 平台管理 retry；Actor 可抛出 Actor Error 对象 |
| **分发方式** | 目录 + GitHub（anthropics/skills 仓库）；用户自装 | 同上 + Manus.im 内置市场 | npm 包（community nodes）；自部署 | Zapier Partner Platform 审核发布 | Apify Store（12,000+），支持定价 |
| **触发方式** | LLM 语义匹配 + 手动 `/skill-name` | 同上 | Webhook/Schedule/事件驱动 | Polling/Webhook（Instant） | API 调用/Scheduler/事件触发 |
| **权限控制** | `allowed-tools`（工具白名单，支持通配符） | 同上 | 凭证系统（Credentials），节点级 | 集成级 OAuth/API Key | 平台级 API Token，Actor 运行沙箱隔离 |
| **AI 原生程度** | 完全 AI 原生（LLM 驱动触发和执行） | 完全 AI 原生 + 自动生成 | 非 AI 原生（有 AI 节点但核心是规则引擎） | 非 AI 原生（图形化规则编排） | 非 AI 原生（代码执行，有 MCP 接口） |

---

## 三、对 Doramagic 新积木设计的建议

### 核心判断

**最适合"从自然语言意图编译成可运行工具"的参考方案，是 Anthropic Agent Skills + Apify input_schema 的混合模型。**

理由分析：

**1. Anthropic SKILL.md 解决了"意图触发"问题**

SKILL.md 的 `description` 字段是语义触发器，不是关键词匹配，而是让 LLM 用语言理解来决定调用哪个积木。这正是 Doramagic 需要的：用户说"我想查某个知识点"，系统应该自动匹配到正确的积木，而不需要用户精确地说出积木名。

当前 Doramagic 积木已经是 SKILL.md 格式，这个基础架构是对的，无需换轨。

**2. Apify input_schema 解决了"参数化"问题**

Anthropic Skills 最大的弱点是**没有正式的输入输出 schema**。积木需要什么参数、会产出什么结果，全靠 LLM 从 Markdown 正文推断。这在简单场景没问题，但当积木变复杂、需要验证用户输入、需要与其他积木对接时，就会出现"黑箱对接"的问题。

Apify 的 input_schema 解决了这个问题：声明式 JSON Schema，支持类型、验证、默认值、UI 渲染。Doramagic 可以在 SKILL.md frontmatter 中增加一个 `input_schema` 字段，或在积木目录中增加 `input.json`，采用 Apify 的 schema 格式。

**3. n8n 的组合机制值得部分借鉴**

n8n 的"节点连线"模式对于"工具链"（多个积木串联）是清晰的。但对于 Doramagic 的场景，用户不会手动连线——应该由 LLM 自动编排。所以 n8n 的**组合思路**（明确声明输入/输出类型，使连接可推断）值得借鉴，但不需要照搬 UI 层的连线机制。

**4. Zapier 的 `sample` 字段是个低成本高价值的改进**

每个积木应该有一个 `sample_output`，描述"这个积木跑完后会输出什么样的结果"。这让 LLM 在编排时可以预判下一步需要什么，也让用户测试时有参考。

**5. Manus 的"从会话自动生成 Skill"是 Doramagic 的战略方向**

Doramagic 目前的积木主要靠手工提取。Manus 的自动生成机制——当用户完成一个满意的任务后，自动打包成可复用 Skill——正是 Doramagic "直缝路径"的终态。用户完成一次检索→LLM 自动抽象成积木→下次同类问题直接复用。

### 建议的 Doramagic 积木格式（v2 草案）

```yaml
---
name: brick-name                        # kebab-case，全局唯一
description: |                          # 触发信号，LLM 语义匹配用
  Use this brick when [意图描述].
  适用场景: [场景1], [场景2]
version: "1.0"
category: knowledge | workflow | tool   # 积木分类
allowed-tools: Read, Bash               # 工具白名单
input_schema: ./input.json             # 可选，Apify 格式 JSON Schema
sample_output: ./sample_output.json    # 可选，示例输出
---

# 积木标题

## 执行逻辑
[自然语言描述，LLM 按此执行]

## 使用约束
[边界条件]

## 参考资源
- 见 `references/xxx.md`
```

**分级实施建议**：
- **第一阶段**（低成本）：在现有 SKILL.md 中补充 `category` 和 `sample_output` 字段，提升积木可发现性和可组合性
- **第二阶段**（中等成本）：为复杂积木增加 `input.json`（Apify 格式），实现参数验证和 UI 渲染
- **第三阶段**（战略投入）：实现"从对话自动生成积木"的闭环（参考 Manus 机制）

---

## 参考来源

- [SKILL.md Format Specification - DeepWiki](https://deepwiki.com/anthropics/skills/2.2-skill.md-format-specification)
- [Anthropic Agent Skills Overview](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview)
- [Claude Agent Skills: A First Principles Deep Dive](https://leehanchung.github.io/blogs/2025/10/26/claude-skills-deep-dive/)
- [Manus Agent Skills blog](https://manus.im/blog/manus-skills)
- [Manus Skills Documentation](https://manus.im/docs/features/skills)
- [n8n Node Types Documentation](https://docs.n8n.io/integrations/creating-nodes/plan/node-types/)
- [n8n Programmatic Node Tutorial](https://docs.n8n.io/integrations/creating-nodes/build/programmatic-style-node/)
- [Zapier Platform CLI README](https://github.com/zapier/zapier-platform-cli/blob/master/README.md)
- [Zapier Add Input Fields](https://docs.zapier.com/platform/build/add-fields)
- [Apify actor.json Specification](https://docs.apify.com/platform/actors/development/actor-definition/actor-json)
- [Apify Input Schema Specification v1](https://docs.apify.com/platform/actors/development/actor-definition/input-schema/specification/v1)
- [Apify Actor Output Schema](https://docs.apify.com/platform/actors/development/actor-definition/output-schema)
- [Equipping agents for the real world - Anthropic Engineering](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills)
