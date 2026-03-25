# Installing and Using Doramagic

Doramagic v9.2.0 is a **skill-forging skill** for OpenClaw and Claude Code style environments.

Its job is not to build an app for you. Its job is to turn a natural-language need into an **installable Skill bundle** by running an 8-phase pipeline:

`Need understanding -> GitHub search -> multi-project extraction -> cross-project synthesis -> Skill compilation -> gate validation -> delivery`

Key facts:

- Product philosophy: **不教用户做事，给他工具**
- Output shape: **Skill first**, not app first
- Knowledge base: **278 bricks across 34 frameworks/domains**
- Model strategy: **model-agnostic** across Claude, Gemini, GPT, and local-model workflows such as Ollama
- Repository: `https://github.com/tangweigang-jpg/Doramagic.git`

## What You Are Installing

When you install Doramagic, you are installing the **forging skill** that responds to `/dora`.

When Doramagic finishes a run, it outputs a **new Skill bundle** for your target domain. That bundle is the actual product you keep and reuse.

A typical generated Skill bundle contains:

- `SKILL.md`: the entrypoint instructions that make the AI behave like the new expert
- `README.md`: usage and installation notes for the generated skill
- `PROVENANCE.md`: where the knowledge came from
- `LIMITATIONS.md`: explicit boundaries, blind spots, and known risks
- Supporting knowledge assets when the bundle needs them

This is the core mental model:

- Doramagic itself is a **forge**
- The generated bundle is the **tool**
- After installation, your AI assistant becomes the **specialist**

## Prerequisites

- Git
- Python `3.12+`
- A stable local clone path for the Doramagic repo, for example `~/Doramagic`
- At least one model available in your environment
- API keys for the providers you declare in `models.json`

Note: The skill directory is **self-contained** — it includes all packages, bricks, and configuration needed to run. After `cp -r`, you can safely delete the cloned repo if you wish.

## Configure `models.json`

Create or edit `models.json` at the repo root. Doramagic routes by **capability**, not by brand name, so one model is enough to get started and multiple models improve flexibility.

Example:

```json
{
  "available_models": [
    {
      "model_id": "claude-sonnet-4-6",
      "provider": "anthropic",
      "capabilities": ["deep_reasoning", "structured_extraction", "tool_calling", "code_understanding"],
      "cost_tier": "medium",
      "api_key_env": "ANTHROPIC_API_KEY",
      "max_context_tokens": 1000000,
      "supports_tool_use": true
    },
    {
      "model_id": "gemini-2.5-pro",
      "provider": "google",
      "capabilities": ["deep_reasoning", "structured_extraction", "tool_calling", "code_understanding"],
      "cost_tier": "medium",
      "api_key_env": "GOOGLE_API_KEY",
      "max_context_tokens": 1000000,
      "supports_tool_use": true
    },
    {
      "model_id": "gpt-4.1",
      "provider": "openai",
      "capabilities": ["deep_reasoning", "structured_extraction", "tool_calling", "code_understanding"],
      "cost_tier": "high",
      "api_key_env": "OPENAI_API_KEY",
      "max_context_tokens": 1000000,
      "supports_tool_use": true
    }
  ],
  "routing_preference": "lowest_sufficient",
  "fallback_strategy": "degrade_and_warn"
}
```

Export only the keys you actually need:

```bash
export ANTHROPIC_API_KEY="..."
export GOOGLE_API_KEY="..."
export OPENAI_API_KEY="..."
```

Notes:

- You do not need all three keys.
- If your environment already exposes local models through your own adapter or proxy, keep the same capability-oriented pattern.
- Doramagic cares about `deep_reasoning`, `structured_extraction`, `tool_calling`, and `code_understanding`, not about brand loyalty.

## Install Method 1: OpenClaw

### Step 1. Clone the repo

```bash
git clone https://github.com/tangweigang-jpg/Doramagic.git ~/Doramagic
cd ~/Doramagic
```

### Step 2. Link the Doramagic skill into OpenClaw

The current launcher expects a stable skill path. Keep the repo checkout intact and use symlinks:

```bash
mkdir -p ~/.openclaw/skills
cp -r ~/Doramagic/skills/doramagic ~/.openclaw/skills/dora
```

### Step 3. Restart or reload your OpenClaw session

Open a fresh OpenClaw session so the host reloads the `dora` skill entry.

### Step 4. Use `/dora`

Example:

```text
/dora 我想做一个管理家庭菜谱和每周菜单的 Skill。Please learn from https://github.com/TandoorRecipes/recipes and https://github.com/mealie-recipes/mealie . 中文优先，适合家庭使用。
```

Typical interaction:

```text
User
/dora 我想做一个管理家庭菜谱和每周菜单的 Skill。Please learn from https://github.com/TandoorRecipes/recipes and https://github.com/mealie-recipes/mealie . 中文优先，适合家庭使用。

Doramagic
我会先理解需求，再做 GitHub 搜索、多项目提取、跨项目综合和 Skill 锻造。

Doramagic
需要一个关键澄清：你更在意“家庭协作”还是“菜谱导入/导出”？

User
家庭协作优先，手机对话体验优先。

Doramagic
锻造完成。交付物是一个 Skill bundle：
- SKILL.md
- README.md
- PROVENANCE.md
- LIMITATIONS.md

下一步：把这个 bundle 安装到你的 skill 目录。
```

### Step 5. Install the generated Skill bundle

Assume Doramagic wrote a delivery bundle under a run directory such as:

```text
~/clawd/doramagic/runs/run-20260324-153000/delivery/
```

Install it manually:

```bash
mkdir -p ~/.openclaw/skills/family-menu-coach
cp -R ~/clawd/doramagic/runs/run-20260324-153000/delivery/* ~/.openclaw/skills/family-menu-coach/
```

After that, your AI host can use the generated skill directly:

```text
/family-menu-coach 我冰箱里有鸡腿、土豆和番茄，给我安排 3 天晚餐，并解释为什么这么搭配。
```

## Install Method 2: Claude Code

### Step 1. Clone the repo

```bash
git clone https://github.com/tangweigang-jpg/Doramagic.git ~/Doramagic
cd ~/Doramagic
```

### Step 2. Link Doramagic into Claude Code manually

Use a stable checkout and symlink the skill into Claude Code:

```bash
mkdir -p ~/.claude/skills
cp -r ~/Doramagic/skills/doramagic ~/.claude/skills/dora
```

### Step 3. Restart Claude Code

Open a new Claude Code session so the host picks up the new skill.

### Step 4. Use `/dora`

Example:

```text
/dora 我想做一个管理个人知识库和阅读摘要的 Skill。Please learn from https://github.com/obsidianmd/obsidian-releases and https://github.com/logseq/logseq . 中文优先，强调知识组织而不是笔记堆积。
```

Typical interaction:

```text
User
/dora 我想做一个管理个人知识库和阅读摘要的 Skill。Please learn from https://github.com/obsidianmd/obsidian-releases and https://github.com/logseq/logseq . 中文优先，强调知识组织而不是笔记堆积。

Doramagic
我会重点提取：链接结构、知识演化、复盘机制、社区常见踩坑。

Doramagic
你更希望它面向“重度研究者”还是“日常工作知识管理”？

User
日常工作知识管理。

Doramagic
完成。产出物是 Skill bundle，而不是普通说明文件。安装后，你的 AI 助手会变成 PKM advisor。
```

### Step 5. Install the generated Skill bundle

```bash
mkdir -p ~/.claude/skills/pkm-advisor
cp -R ~/clawd/doramagic/runs/run-20260324-160500/delivery/* ~/.claude/skills/pkm-advisor/
```

Then use the generated skill in Claude Code:

```text
/pkm-advisor 我今天读了 3 篇关于 RAG 的文章，帮我整理成可复用的知识卡片，并指出我最容易遗漏的关联线索。
```

## Install Method 3: Python CLI / Local Forge Mode

This mode is best when you want to run Doramagic directly from source for local testing, debugging, or CI-like workflows.

### Step 1. Clone the repo

```bash
git clone https://github.com/tangweigang-jpg/Doramagic.git ~/Doramagic
cd ~/Doramagic
```

### Step 2. Create a local Python environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
pip install anthropic openai google-genai
```

### Step 3. Configure `models.json` and API keys

Use the same `models.json` structure shown earlier, then export the keys for the providers you want to use.

### Step 4. Run Doramagic from source

```bash
python3 skills/doramagic/scripts/doramagic_main.py --cli \
  --run-dir ~/clawd/doramagic/runs \
  --input "我想做一个健身与饮食指导 Skill。Please learn from https://github.com/wger-project/wger and https://github.com/TandoorRecipes/recipes . 中文优先，强调长期习惯而不是短期打卡。"
```

This source mode executes the same forge pipeline and produces the same **Skill bundle**.

### Step 5. Equivalent `/dora` flow after linking into a host

If you want the exact slash-command UX after local verification, link the same checkout into OpenClaw or Claude Code using one of the methods above, then run:

```text
/dora 我想做一个健身与饮食指导 Skill。Please learn from https://github.com/wger-project/wger and https://github.com/TandoorRecipes/recipes . 中文优先，强调长期习惯而不是短期打卡。
```

Typical interaction:

```text
User
/dora 我想做一个健身与饮食指导 Skill。Please learn from https://github.com/wger-project/wger and https://github.com/TandoorRecipes/recipes . 中文优先，强调长期习惯而不是短期打卡。

Doramagic
我会综合训练记录、营养管理、用户坚持成本、社区常见失败模式。

Doramagic
请确认：你更关注“记录准确性”还是“用户可坚持性”？

User
用户可坚持性。

Doramagic
已完成锻造。交付物是 Skill bundle。安装后，你的 AI 助手会变成 habit-oriented fitness advisor。
```

## What Doramagic Produces

Doramagic produces a **Skill**, not a throwaway file.

Think of the output in two layers:

- `SKILL.md`: the executable instruction layer that defines the expert behavior
- Knowledge pack: the supporting materials that make the skill trustworthy, explainable, and installable

In practice, the bundle usually includes:

- `SKILL.md`
- `README.md`
- `PROVENANCE.md`
- `LIMITATIONS.md`

What happens after installation:

- Your AI assistant inherits the target domain's design philosophy
- It can reason with real project conventions instead of generic advice
- It can warn about community traps and hidden tradeoffs
- It can act like a specialized advisor for that domain

What it does **not** mean:

- Doramagic did not build your final product for you
- Doramagic did not output a polished SaaS or mobile app
- Doramagic gave you an installable expert tool, so your AI can help you build the right thing faster

## Recommended Prompt Pattern

The best `/dora` prompts contain three ingredients:

1. The domain you want the final skill to specialize in
2. One or more concrete GitHub repos in English URL form
3. The audience, constraints, or language expectations

Template:

```text
/dora 我想做一个[中文需求]的 Skill。Please learn from https://github.com/owner/repo and https://github.com/owner/repo . [中文约束，例如：中文优先 / 面向独立开发者 / 强调审查而不是生成]
```

Example:

```text
/dora 我想做一个帮助团队审查 API 设计的 Skill。Please benchmark https://github.com/fastapi/fastapi and https://github.com/encode/django-rest-framework . 输出给中文团队使用，强调 review checklist 和设计取舍。
```

## FAQ

### 1. Does Doramagic build an app for me?

No. Doramagic builds a **Skill bundle** that turns your AI assistant into a domain expert. The product you keep is the skill, not an app binary.

### 2. Do I need Claude, Gemini, GPT, and Ollama all at once?

No. One capable model is enough to start. Doramagic is model-agnostic; adding more models only improves routing flexibility and cost control.

### 3. Can I delete the cloned repo after installation?

Yes. The `skills/doramagic/` directory is self-contained — it includes all Python packages, knowledge bricks, and configuration. After `cp -r`, the skill works independently.

### 4. Where do I find the generated skill bundle?

Look in the run's `delivery/` directory. A common pattern is:

```text
~/clawd/doramagic/runs/<run-id>/delivery/
```

That directory is what you manually copy into `~/.openclaw/skills/<skill-name>/` or `~/.claude/skills/<skill-name>/`.

### 5. What should I put in my `/dora` prompt?

State the target expert in Chinese, include one or more GitHub repo URLs in English, and add any constraints such as language, audience, or preferred tradeoffs.

Good:

```text
/dora 我想做一个管理家庭菜谱的 Skill。Please learn from https://github.com/TandoorRecipes/recipes . 中文优先，适合家庭使用。
```

Weak:

```text
/dora 帮我做一个东西
```
