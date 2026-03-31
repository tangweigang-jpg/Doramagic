# Doramagic

[English](./README.md) | 中文

[![CI](https://github.com/tangweigang-jpg/Doramagic/actions/workflows/ci.yml/badge.svg)](https://github.com/tangweigang-jpg/Doramagic/actions/workflows/ci.yml)

> **"不教用户做事，给他工具。"** —— Doramagic 的设计哲学，灵感来自哆啦A梦。

Doramagic 从开源项目中提取**灵魂**——不只是代码做了什么，而是*为什么这样设计*，以及那些从未出现在文档中的社区踩坑经验。提取的知识被编译成可注入的顾问包，让 AI 助手深刻理解项目的设计哲学、心智模型和社区陷阱。

**Doramagic 是一个需要安装和运行的工具。** 它对真实 GitHub 仓库执行 7 阶段提取流水线。仅阅读此 README 不会启用其功能——你必须将其安装为技能并调用 `/dora`。

## 快速开始

### 一键安装（推荐）

```bash
curl -fsSL https://raw.githubusercontent.com/tangweigang-jpg/Doramagic/main/install.sh | bash
```

安装完成后，设置 API 密钥并重启：

```bash
export ANTHROPIC_API_KEY="your-key"
# 重启会话，然后：
/dora https://github.com/owner/repo
```

### 直接缝合（无需指定项目）

Doramagic v13.0.0 可以直接从知识库生成技能：

```bash
/dora 帮我做一个监控加密货币价格的 Telegram 机器人
/dora 帮我做一个每日信息聚合推送的工具
/dora Build a Telegram bot that monitors crypto prices with alerts
```

这个"积木缝合"路径将你的意图与 50 个知识类别进行匹配，在几秒内组合出一个技能（2 次 LLM 调用），无需指定 GitHub 项目。

### 其他安装方式

**OpenClaw（ClawHub）：**
```bash
openclaw skills install doramagic
```

**Claude Code（插件市场）：**
```
/plugin marketplace add tangweigang-jpg/Doramagic
/plugin install doramagic
```

**跨平台（Claude Code、Codex、Cursor 等 39+ 个代理）：**
```bash
npx skills add tangweigang-jpg/Doramagic
```

### 手动安装

<details>
<summary>点击展开手动步骤</summary>

### 1. 克隆

```bash
git clone https://github.com/tangweigang-jpg/Doramagic.git ~/Doramagic
cd ~/Doramagic
```

### 2. 安装 Python 依赖

Doramagic 需要 Python 3.12+ 和少量运行时依赖：

```bash
uv venv && source .venv/bin/activate
uv pip install pydantic                        # 必需
uv pip install anthropic openai google-genai   # 安装你的 LLM 提供商 SDK
```

### 3. 安装为技能

将自包含技能目录复制到宿主的技能目录。使用 `cp -rL` 解引用符号链接：

**OpenClaw：**
```bash
mkdir -p ~/.openclaw/skills
cp -rL ~/Doramagic/skills/doramagic ~/.openclaw/skills/dora
```

**Claude Code：**
```bash
mkdir -p ~/.claude/skills
cp -rL ~/Doramagic/skills/doramagic ~/.claude/skills/dora
```

### 4. 配置模型

安装的技能包含 `models.json.example`。在**技能目录内**复制并编辑：

```bash
# OpenClaw：
cp ~/.openclaw/skills/dora/models.json.example ~/.openclaw/skills/dora/models.json

# Claude Code：
cp ~/.claude/skills/dora/models.json.example ~/.claude/skills/dora/models.json
```

编辑 `models.json`——声明你可以使用的模型。一个模型就够了。

导出 API 密钥：

```bash
export ANTHROPIC_API_KEY="..."
# 和/或
export GOOGLE_API_KEY="..."
export OPENAI_API_KEY="..."
```

### 5. 使用 `/dora`

重启宿主会话（让宿主重新扫描技能目录），然后调用：

```text
/dora 我想要一个管理家庭食谱和每周菜单的工具。
     请从 https://github.com/TandoorRecipes/recipes
     和 https://github.com/mealie-recipes/mealie 学习
```

Doramagic 运行 7 阶段流水线并生成一个你可以安装的技能包。

</details>

## Doramagic 产出什么

每次成功运行会生成这些文件：

| 文件 | 用途 |
|------|------|
| `SKILL.md` | 定义专家行为的可执行指令 |
| `PROVENANCE.md` | 证据链——每条声明可追溯到来源 |
| `DSD_REPORT.md` | 虚假来源检测结果（8 项自动检查） |
| `CONFIDENCE_STATS.json` | 每条声明的置信度分布 |

## 使用示例

Doramagic 支持 4 种输入类型，每种确定性路由：

| 路由 | 示例 | 行为 |
|------|------|------|
| 直接 URL | `/dora https://github.com/fastapi/fastapi` | 跳过发现，直接提取 |
| 项目名 | `/dora 提取 Home Assistant 的智慧` | 搜索 GitHub，然后提取 |
| 领域探索 | `/dora PKM 项目有什么设计智慧？` | 多项目发现 + 提取 |
| 需求澄清 | `/dora 我需要一个团队用的工具` | 先问澄清问题 |

## 核心特性（v13.0.0）

- **单职责技能架构** —— 5 个独立技能，每个用 Iron Law 防止宿主 LLM 跳步
- **确定性路由 DAG** —— 4 条输入路径，条件边
- **扇出提取** —— 最多 3 个隔离 RepoWorker 并行
- **5 维质量关卡** —— 60 分及格线 + 定向修订
- **4 级降级交付** —— 用户始终有产出
- **EventBus + 结构化日志** —— `run_events.jsonl` 可观测性
- **模型无关** —— 支持任何 LLM（Claude、Gemini、GPT、Ollama）
- **知识积木直缝** —— 从万级知识库秒级生成技能
- **50 个领域的知识积木** —— 对齐 ClawHub 市场需求
- **因果推理** —— 合成产出"X 因为 Y"的洞见，而非事实列表
- **细粒度进度** —— 提取期间每 3-5 秒发送 sub_progress 事件

## 架构概览

```
INIT → PHASE A（输入路由）
         |
    ┌────┴────┐
  追问澄清  （路由）
              |
         PHASE B（GitHub 发现）
              |
         PHASE C（扇出灵魂提取，最多 3 个仓库）
              |
         PHASE D（跨项目合成）
              |
         PHASE E（技能编译）
              |
         PHASE F（质量关卡：5 维，60 分）
         /        \
      修订       通过
      (→E)         |
              PHASE G（打包 + 交付）
                 |
               完成
```

详细架构、配置和高级用法见 [INSTALL.md](INSTALL.md)。

## 配置

### `models.json`

Doramagic 按**能力**路由，而非按模型名：

```json
{
  "available_models": [
    {
      "model_id": "claude-sonnet-4-6",
      "provider": "anthropic",
      "capabilities": ["deep_reasoning", "structured_extraction", "tool_calling"],
      "cost_tier": "medium",
      "api_key_env": "ANTHROPIC_API_KEY"
    }
  ],
  "routing_preference": "lowest_sufficient",
  "fallback_strategy": "degrade_and_warn"
}
```

一个模型就够了。添加更多可以提升路由灵活性和成本控制。

## 分发

Doramagic 以**自包含技能目录**分发。无需市场、包注册表或商店上架。

- **OpenClaw** 和 **Claude Code** 通过扫描技能目录发现技能（`~/.openclaw/skills/` 和 `~/.claude/skills/`）。
- 安装就是复制文件。无需 `npm install`、`pip install` 或注册步骤。
- 克隆的仓库在复制后可以删除——安装的技能目录包含所需的所有包、积木和脚本。

## 开发

```bash
git clone https://github.com/tangweigang-jpg/Doramagic.git
cd Doramagic
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"

# 运行测试
make test
```

## 项目结构

```
packages/           # 核心模块（contracts、controller、executors、extraction 等）
bricks/             # 10,028 块知识积木，覆盖 50 个领域
skills/doramagic/   # 自包含技能包（SKILL.md + packages + bricks）
tests/              # 单元 + 端到端冒烟测试
scripts/            # 工具和发布脚本
```

## 常见问题

### Doramagic 会帮我开发应用吗？

不会。Doramagic 构建的是**技能包**，将你的 AI 助手变成领域专家。

### 我需要多个 LLM 提供商吗？

不需要。一个有能力的模型就够了。

### 安装后可以删除克隆的仓库吗？

可以，如果你使用了 `cp -rL`（解引用符号链接）。安装的技能目录包含所有包、积木和脚本。只需确保 Python 依赖（`pydantic` + 你的 LLM SDK）安装在可访问的虚拟环境中。

### 生成的技能包在哪里？

```text
~/.doramagic/runs/<run-id>/delivery/
```

将该目录复制到宿主的技能目录即可。

## 许可证

[MIT](LICENSE)

## 贡献

参见 [CONTRIBUTING.md](CONTRIBUTING.md) 了解开发设置、测试和 PR 指南。
