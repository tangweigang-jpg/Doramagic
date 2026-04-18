# doramagic-web-publisher

Local compilation agent that generates Crystal Package JSON and publishes it to doramagic.ai.

Implements **Part 1** of `sops/crystal-web-publishing-sop.md` v2.2.

## Architecture

Four fixed phases (pipeline mode, not autonomous):

```
content → constraints → faq → evaluator → assemble → preflight → publish
```

- **content** (Phase 1): Generate A (slug/name/definition/description) + E (known_gaps) + G (changelog)
- **constraints** (Phase 2): Generate D (constraints with evidence_url + bilingual summaries)
- **faq** (Phase 3): Generate F (5-8 bilingual FAQs)
- **evaluator** (Phase 4): Generate H/I/J/K/L (sample_output, required_inputs, creator_proof, tier, SEO fields)

## Installation

```bash
cd packages/web_publisher
uv pip install -e .
```

## CLI Usage

```bash
# Full publish
python -m doramagic_web_publisher publish bp-009

# Dry-run (skip HTTP POST, show assembled package)
python -m doramagic_web_publisher publish bp-009 --dry-run

# Mock mode (use placeholder PhaseResults, useful for testing pipeline wiring)
python -m doramagic_web_publisher publish bp-009 --mock

# Run a single phase
python -m doramagic_web_publisher run-phase bp-009 content

# Run preflight only (validate an existing JSON file)
python -m doramagic_web_publisher preflight path/to/package.json
```

## Dependencies

- `doramagic-contracts` — Blueprint / Constraint pydantic models
- `doramagic-shared-utils` — LLMAdapter (mandatory LLM call gateway)
- `httpx` — HTTP client for Publish API
- `typer` — CLI framework

**Not** depended on: `doramagic-agent-core` (by design — "极致独立" route).

## Dev Commands

```bash
cd packages/web_publisher
pytest -x                    # run all tests
mypy doramagic_web_publisher # type check
ruff check .                 # lint
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `PUBLISH_API_KEY` | yes (publish) | Bearer token for POST /api/publish/crystal |
| `PUBLISH_API_URL` | no | Default: https://doramagic.ai/api/publish/crystal |
| `ANTHROPIC_API_KEY` | yes (non-mock) | Used by LLMAdapter for Claude |

## Adding a New Phase

1. Create `phases/my_phase.py` extending `phases/base.Phase`
2. Implement `name`, `submit_tool_schema`, `build_prompt`, `parse_result`, `run`
3. Register in `phases/__init__.py` PHASES list
