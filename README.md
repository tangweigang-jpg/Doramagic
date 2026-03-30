# Doramagic

[![CI](https://github.com/tangweigang-jpg/Doramagic/actions/workflows/ci.yml/badge.svg)](https://github.com/tangweigang-jpg/Doramagic/actions/workflows/ci.yml)

> **"Don't teach the user what to do -- give them the tool."** -- Doramagic's design philosophy, inspired by Doraemon.

Doramagic extracts the **soul** of open-source projects -- not just what the code does, but *why* it was designed that way and the hard-won community wisdom that never appears in documentation. The extracted knowledge is compiled into injectable advisor packs that make AI assistants deeply understand a project's design philosophy, mental models, and community pitfalls.

**Doramagic is a tool that must be installed and run.** It executes a 7-phase extraction pipeline against real GitHub repositories. Reading this README does not enable its functionality -- you must install it as a skill and invoke `/dora`.

## Quick Start

### One-line install (recommended)

```bash
curl -fsSL https://raw.githubusercontent.com/tangweigang-jpg/Doramagic/main/install.sh | bash
```

This auto-detects OpenClaw / Claude Code, installs Python dependencies, and sets everything up. After it finishes, set your API key and restart:

```bash
export ANTHROPIC_API_KEY="your-key"
# Restart your session, then:
/dora https://github.com/owner/repo
```

### Direct Stitch (no project needed)

Doramagic v12.4.1 can generate skills directly from its 1076-brick knowledge library:

```bash
/dora Build a Telegram bot that monitors crypto prices with alerts
/dora Create an email automation skill for inbox triage and auto-reply
/dora 帮我做一个每日信息聚合推送的 skill
```

This "brick stitch" path matches your intent against 49 knowledge categories and composes a skill in seconds (2 LLM calls), without needing a specific GitHub project.

### Other install methods

**OpenClaw (ClawHub):**
```bash
openclaw skills install doramagic
```

**Claude Code (plugin marketplace):**
```
/plugin marketplace add tangweigang-jpg/Doramagic
/plugin install doramagic
```

**Cross-platform (Claude Code, Codex, Cursor, and 39+ agents):**
```bash
npx skills add tangweigang-jpg/Doramagic
```

### Manual install

<details>
<summary>Click to expand manual steps</summary>

### 1. Clone

```bash
git clone https://github.com/tangweigang-jpg/Doramagic.git ~/Doramagic
cd ~/Doramagic
```

### 2. Install Python dependencies

Doramagic requires Python 3.12+ and a few runtime packages. Install them in a dedicated virtualenv:

```bash
uv venv && source .venv/bin/activate
uv pip install pydantic                        # required
uv pip install anthropic openai google-genai   # install SDK(s) for your LLM provider(s)
```

### 3. Install as a skill

Copy the self-contained skill directory into your host's skill directory. Use `cp -rL` to dereference any symlinks:

**OpenClaw:**
```bash
mkdir -p ~/.openclaw/skills
cp -rL ~/Doramagic/skills/doramagic ~/.openclaw/skills/dora
```

**Claude Code:**
```bash
mkdir -p ~/.claude/skills
cp -rL ~/Doramagic/skills/doramagic ~/.claude/skills/dora
```

### 4. Configure models

The installed skill includes `models.json.example`. Copy and edit it **inside the skill directory**:

```bash
# OpenClaw:
cp ~/.openclaw/skills/dora/models.json.example ~/.openclaw/skills/dora/models.json

# Claude Code:
cp ~/.claude/skills/dora/models.json.example ~/.claude/skills/dora/models.json
```

Edit `models.json` -- declare the models you have access to. One model is enough.

Export API keys for the providers you declared:

```bash
export ANTHROPIC_API_KEY="..."
# and/or
export GOOGLE_API_KEY="..."
export OPENAI_API_KEY="..."
```

### 5. Use `/dora`

Restart your host session (so the host re-scans the skill directory), then invoke:

```text
/dora I want a Skill for managing family recipes and weekly menus.
     Please learn from https://github.com/TandoorRecipes/recipes
     and https://github.com/mealie-recipes/mealie
```

Doramagic runs its 7-phase pipeline and produces a Skill bundle you can install.

</details>

## What Doramagic Produces

Every successful run produces exactly these files:

| File | Purpose |
|------|---------|
| `SKILL.md` | Executable instructions that define expert behavior |
| `PROVENANCE.md` | Evidence trail -- every claim traced to source |
| `DSD_REPORT.md` | Deceptive Source Detection results (8 automated checks) |
| `CONFIDENCE_STATS.json` | Per-claim verdict distribution |

Here is what the beginning of a real `SKILL.md` looks like:

```markdown
# Fitness Tracker Advisor

You are an expert advisor on fitness tracking application design,
trained on the design philosophy and community wisdom of wger.

## Core Design Principles

- **Simplicity over features**: wger deliberately limits dashboard widgets
  to 3 per view. Community learned that >5 widgets caused 40% of users
  to stop logging workouts (GitHub Discussion #847).
  [SOURCE: CODE:dashboard/views.py:L42 + COMMUNITY:Discussion#847]
```

If your output does not look like this, Doramagic did not run -- the AI may have fabricated a response from reading this README.

## Usage Examples

Doramagic supports 4 input types, each routed deterministically:

| Route | Example | Behavior |
|-------|---------|----------|
| Direct URL | `/dora https://github.com/fastapi/fastapi` | Skips discovery, extracts directly |
| Named Project | `/dora Extract wisdom from Home Assistant` | Searches GitHub, then extracts |
| Domain Exploration | `/dora What design wisdom can I learn from PKM projects?` | Multi-project discovery + extraction |
| Clarification | `/dora I need something for my team` | Asks clarifying questions first |

## Key Features (v12.4.1)

- **Deterministic Routing DAG** -- 4 input paths with conditional edges
- **Fan-out Extraction** -- Up to 3 isolated RepoWorkers in parallel
- **5-Dimension Quality Gate** -- 60-point threshold with targeted revision
- **4-Tier Degraded Delivery** -- Users always receive output
- **EventBus + Structured Logging** -- `run_events.jsonl` for observability
- **Model-Agnostic** -- Works with any LLM (Claude, Gemini, GPT, Ollama)
- **Knowledge Brick Direct Stitch** -- generate skills from 1076 pre-built knowledge bricks in seconds
- **1076 Knowledge Bricks** across 49 domains aligned to ClawHub marketplace demand
- **Causal Reasoning** -- synthesis produces "X because Y" insights, not just fact lists
- **Fine-grained Progress** -- sub_progress events every 3-5 seconds during extraction

## Architecture Overview

```
INIT → PHASE A (Input Router)
         |
    ┌────┴────┐
  CLARIFY   (route)
              |
         PHASE B (GitHub Discovery)
              |
         PHASE C (Fan-out Soul Extraction, up to 3 repos)
              |
         PHASE D (Cross-Project Synthesis)
              |
         PHASE E (Skill Compilation)
              |
         PHASE F (Quality Gate: 5-dim, 60pt threshold)
         /        \
      REVISE     PASS
      (→E)         |
              PHASE G (Package + Deliver)
                 |
               DONE
```

See [INSTALL.md](INSTALL.md) for detailed architecture, configuration, and advanced usage.

## Configuration

### `models.json`

Doramagic routes by **capability**, not by model name:

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

One model is enough. Adding more improves routing flexibility and cost control.

## Distribution

Doramagic is distributed as a **self-contained skill directory**. There is no marketplace, package registry, or store listing required.

- **OpenClaw** and **Claude Code** both discover skills by scanning their skill directories (`~/.openclaw/skills/` and `~/.claude/skills/`).
- Installation is just copying files. No `npm install`, no `pip install`, no registration step.
- The cloned repo can be deleted after copying -- the installed skill directory contains all packages, bricks, and scripts it needs. Just make sure Python dependencies (Step 2) are installed in a virtualenv that the skill's Python can access.

## Development

```bash
git clone https://github.com/tangweigang-jpg/Doramagic.git
cd Doramagic
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"

# Run tests
make test
```

## Project Structure

```
packages/           # Core modules (contracts, controller, executors, extraction, etc.)
bricks/             # 278 knowledge bricks across 34 frameworks/domains
skills/doramagic/   # Self-contained skill bundle (SKILL.md + packages + bricks)
tests/              # Unit + E2E smoke tests
scripts/            # Utility and release scripts
```

## FAQ

### Does Doramagic build an app for me?

No. Doramagic builds a **Skill bundle** that turns your AI assistant into a domain expert.

### Do I need multiple LLM providers?

No. One capable model is enough.

### Can I delete the cloned repo after installation?

Yes, if you used `cp -rL` (which dereferences symlinks). The installed skill directory contains all packages, bricks, and scripts. Your `models.json` is inside the skill directory, not in the cloned repo. Just ensure Python dependencies (`pydantic` + your LLM SDK) remain installed in an accessible virtualenv.

### Where do I find the generated skill bundle?

```text
~/.doramagic/runs/<run-id>/delivery/
```

Copy that directory into your host's skill directory.

## License

[MIT](LICENSE)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, testing, and PR guidelines.
