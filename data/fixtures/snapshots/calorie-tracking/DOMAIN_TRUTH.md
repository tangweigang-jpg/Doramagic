# Domain Truth: 卡路里追踪

> Snapshot version: 2026-03-19T21:00:00Z
> Projects analyzed: 3

## Consensus Knowledge

These facts are supported by multiple independent projects and represent high-confidence domain knowledge.

### Core Capabilities

- **AI-based food recognition** (3/3 projects): All examined projects use AI vision models (GPT-4 Vision or equivalent) to identify food items and estimate calorie content from user input. This is the foundational capability of any calorie tracking skill.

- **Multi-modal input** (2/3 projects): Both the ai-calorie-tracker and the OpenClaw community skill accept text descriptions and photo uploads for meal logging.

### Core Constraints

- **Local data persistence** (3/3 projects): Calorie tracking data must be stored locally per user. Implementation varies (Vercel KV, JSON files, ~/clawd/ directory) but the principle of user-owned local storage is universal.

## Unique Insights

Knowledge found in only one project but potentially valuable:

- **Structured prompts** (calorie-gpt only): Explicit prompt engineering with structured food description formats improves calorie estimation accuracy. Worth incorporating as a quality enhancement.

- **USDA nutritional database** (calorie-tracker-skill only): Bootstrapping with USDA food data provides a baseline for calorie estimation without requiring API calls.

## Disputed Areas

- **Storage backend choice**: ai-calorie-tracker uses cloud KV while calorie-gpt uses local JSON. For OpenClaw, local storage (~/clawd/) is the correct approach.

## Open Questions

- Should the skill support photo input or text-only in v1?
