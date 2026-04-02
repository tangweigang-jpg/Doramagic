# Installing Doramagic

Doramagic is a **skill-forging skill** for [OpenClaw](https://openclaw.ai). Say what you need, and it crafts a reusable tool from 10,000+ knowledge bricks.

## Quick Install (OpenClaw)

```bash
openclaw skills install dora
```

Or one-line installer:

```bash
curl -fsSL https://raw.githubusercontent.com/tangweigang-jpg/Doramagic/main/install.sh | bash
```

After installation, start a new session and use `/dora`:

```
/dora I need a tool for managing API design reviews
```

## What Gets Installed

A single skill directory containing:

| File | Purpose |
|------|---------|
| `SKILL.md` | Main skill — 3-step workflow (select domains → read bricks → generate tool) |
| `SKILL-dora-extract.md` | Advanced: deep GitHub project analysis (requires exec) |
| `references/brick-catalog.md` | 50-domain knowledge catalog |
| `references/bricks/*.md` | Pre-compiled brick summaries (patterns, failures, rationales) |
| `references/scaffold-tool.md` | Output template for generated tools |
| `knowledge/bricks/*.jsonl` | Full knowledge base (10,030 bricks across 50 domains) |

## Requirements

- OpenClaw 2026.3+ (or any Claude Code environment with skill support)
- No Python, no exec, no API keys needed for `/dora`
- `/dora-extract` requires: Python 3.12+, git, and exec approval

## Manual Install (without OpenClaw CLI)

```bash
git clone https://github.com/tangweigang-jpg/Doramagic.git
cp -r Doramagic/skills/doramagic ~/.openclaw/workspace/skills/dora
```

## Usage

```
/dora Build me a travel English practice tool for daily conversation
```

Doramagic will:
1. Select relevant knowledge domains from the catalog
2. Read brick summaries (failures, patterns, rationales)
3. Generate a SKILL.md file you can reuse

## For Developers

To work on Doramagic itself:

```bash
git clone https://github.com/tangweigang-jpg/Doramagic.git
cd Doramagic
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
make check   # lint + typecheck + 491 tests
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for development workflow.
