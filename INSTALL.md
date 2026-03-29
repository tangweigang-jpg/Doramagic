# Installing and Using Doramagic

Doramagic v12.1.2 is a **skill-forging skill** for OpenClaw and Claude Code environments.

It runs a 7-phase conditional DAG pipeline:

`Input routing -> Discovery -> Fan-out extraction -> Synthesis -> Compilation -> Quality gate -> Delivery`

Key facts:

- Product philosophy: **"Don't teach the user what to do -- give them the tool."**
- Output shape: **Skill bundle** (SKILL.md + PROVENANCE.md + DSD_REPORT.md + CONFIDENCE_STATS.json)
- Knowledge base: **278 bricks across 34 frameworks/domains**
- Model strategy: **model-agnostic** (Claude, Gemini, GPT, Ollama -- any LLM works)
- Repository: `https://github.com/tangweigang-jpg/Doramagic.git`

**Important:** Doramagic must be installed and invoked via `/dora` to function. It cannot be used by reading documentation alone -- the value is in the 7-phase extraction pipeline that runs against real GitHub repositories.

## What You Are Installing

Doramagic itself is the **forge** -- a skill that responds to `/dora`. Each run produces a **new Skill bundle** for your target domain: the actual product you keep and reuse.

A typical generated Skill bundle contains:

| File | Purpose |
|------|---------|
| `SKILL.md` | Entrypoint instructions that make the AI behave like a domain expert |
| `PROVENANCE.md` | Evidence trail for every extracted claim |
| `DSD_REPORT.md` | Deceptive Source Detection results |
| `CONFIDENCE_STATS.json` | Per-claim verdict distribution |

After installation, your AI assistant inherits the target domain's design philosophy and can reason with real project conventions instead of generic advice.

## Fastest Install (recommended)

**One-line installer** -- handles Python deps, host detection, and skill setup automatically:

```bash
curl -fsSL https://raw.githubusercontent.com/tangweigang-jpg/Doramagic/main/install.sh | bash
```

**OpenClaw users** can also install from ClawHub:

```bash
openclaw skills install doramagic
```

After either method, set your API key, restart the session, and run `/dora`.

## Prerequisites (for manual install)

- Git
- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- Runtime Python packages: `pydantic` + at least one LLM SDK (`anthropic`, `openai`, or `google-genai`)
- At least one LLM model accessible via API
- API keys for the providers you declare in `models.json`

**No marketplace or registry is required.** Both OpenClaw and Claude Code discover skills by scanning their skill directories. Installation is just copying files.

## Install Method 1: OpenClaw

### Step 1. Clone the repo

```bash
git clone https://github.com/tangweigang-jpg/Doramagic.git ~/Doramagic
```

### Step 2. Install Python dependencies

```bash
cd ~/Doramagic
uv venv && source .venv/bin/activate
uv pip install pydantic                        # required
uv pip install anthropic openai google-genai   # install SDK(s) for your provider(s)
```

### Step 3. Install the skill

Use `cp -rL` to dereference any symlinks, ensuring the skill directory is truly self-contained:

```bash
mkdir -p ~/.openclaw/skills
cp -rL ~/Doramagic/skills/doramagic ~/.openclaw/skills/dora
```

### Step 4. Configure models

Configure `models.json` **inside the installed skill directory**:

```bash
cp ~/.openclaw/skills/dora/models.json.example ~/.openclaw/skills/dora/models.json
```

Edit `~/.openclaw/skills/dora/models.json` -- declare the models you have access to. Doramagic routes by **capability**, not by brand name, so one model is enough:

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
    }
  ],
  "routing_preference": "lowest_sufficient",
  "fallback_strategy": "degrade_and_warn"
}
```

Export the API keys for the providers you declared:

```bash
export ANTHROPIC_API_KEY="..."
export GOOGLE_API_KEY="..."    # optional
export OPENAI_API_KEY="..."    # optional
```

### Step 5. Restart your OpenClaw session

Open a fresh session so the host re-scans the skill directory and picks up `/dora`.

### Step 6. Use `/dora`

```text
/dora I want a Skill for reviewing API designs.
     Please benchmark https://github.com/fastapi/fastapi
     and https://github.com/encode/django-rest-framework
```

### Step 7. Install the generated Skill bundle

After Doramagic completes, copy the delivery bundle:

```bash
mkdir -p ~/.openclaw/skills/api-review-advisor
cp -R ~/.doramagic/runs/<run-id>/delivery/* ~/.openclaw/skills/api-review-advisor/
```

Then use it:

```text
/api-review-advisor Review my REST API endpoints for consistency issues.
```

## Install Method 2: Claude Code

### Step 1. Clone the repo

```bash
git clone https://github.com/tangweigang-jpg/Doramagic.git ~/Doramagic
```

### Step 2. Install Python dependencies

```bash
cd ~/Doramagic
uv venv && source .venv/bin/activate
uv pip install pydantic                        # required
uv pip install anthropic openai google-genai   # install SDK(s) for your provider(s)
```

### Step 3. Install the skill

```bash
mkdir -p ~/.claude/skills
cp -rL ~/Doramagic/skills/doramagic ~/.claude/skills/dora
```

### Step 4. Configure models

```bash
cp ~/.claude/skills/dora/models.json.example ~/.claude/skills/dora/models.json
```

Edit `~/.claude/skills/dora/models.json` with your available models and export API keys (see Method 1, Step 4 for format).

### Step 5. Restart Claude Code

Open a new session so the host re-scans the skill directory and picks up `/dora`.

### Step 6. Use `/dora`

```text
/dora I want a Skill for managing personal knowledge and reading notes.
     Please learn from https://github.com/obsidianmd/obsidian-releases
     and https://github.com/logseq/logseq
```

### Step 7. Install the generated Skill bundle

```bash
mkdir -p ~/.claude/skills/pkm-advisor
cp -R ~/.doramagic/runs/<run-id>/delivery/* ~/.claude/skills/pkm-advisor/
```

## Install Method 3: Python CLI (Local Forge Mode)

For local testing, debugging, or CI workflows -- no OpenClaw or Claude Code needed:

### Step 1. Clone and set up

```bash
git clone https://github.com/tangweigang-jpg/Doramagic.git ~/Doramagic
cd ~/Doramagic
uv venv && source .venv/bin/activate
uv pip install -e .
uv pip install anthropic openai google-genai  # install SDK(s) for your provider(s)
```

### Step 2. Configure models

```bash
cp models.json.example models.json
```

Edit `models.json` with your available models and export API keys.

### Step 3. Run from source

```bash
python3 skills/doramagic/scripts/doramagic_main.py --cli \
  --run-dir ~/.doramagic/runs \
  --input "I want a fitness and diet coaching Skill. \
           Please learn from https://github.com/wger-project/wger"
```

This runs the same 7-phase DAG pipeline and produces the same Skill bundle.

## Recommended Prompt Pattern

The best `/dora` prompts contain three ingredients:

1. **The domain** you want the final skill to specialize in
2. **One or more GitHub URLs** as reference projects
3. **Constraints** (audience, language, tradeoff preferences)

Template:

```text
/dora I want a Skill for [domain description].
     Please learn from https://github.com/owner/repo
     [Optional constraints: language preference, audience, focus areas]
```

## FAQ

### Does Doramagic build an app for me?

No. Doramagic builds a Skill bundle that turns your AI assistant into a domain expert.

### Do I need multiple LLM providers?

No. One capable model is enough. Adding more improves routing flexibility and cost control.

### Can I delete the cloned repo after installation?

Yes, if you used `cp -rL` (which dereferences symlinks). The installed skill directory contains all packages, bricks, and scripts it needs. Just ensure the Python dependencies (`pydantic` + your LLM SDK) remain installed in a virtualenv that the skill can access.

### Where do I find the generated skill bundle?

In the run's `delivery/` directory:

```text
~/.doramagic/runs/<run-id>/delivery/
```

Copy that directory into your host's skill directory.

### What are the 4 input routing paths?

| Route | Trigger | Behavior |
|-------|---------|----------|
| DIRECT_URL | Input contains GitHub URL(s) | Skips discovery, goes straight to extraction |
| NAMED_PROJECT | Input names a known project | Searches GitHub for the project |
| DOMAIN_EXPLORE | Input describes a domain/need | Multi-project discovery and extraction |
| LOW_CONFIDENCE | Vague or unclear input | Asks clarifying questions first |
