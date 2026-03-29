---
name: dora
description: >
  Doramagic: extract the soul of open-source projects — design philosophy, decision rules,
  and community wisdom compiled into injectable AI advisor packs.
  Triggers on: "dora", "doramagic", "extract soul", "extract knowledge".
version: 12.3.1
user-invocable: true
license: MIT
tags: [doramagic, knowledge-extraction, skill-generation]
metadata: {"openclaw":{"emoji":"🪄","skillKey":"dora","category":"builder","requires":{"bins":["python3","git","bash"]}}}
---

# Doramagic — Soul Extractor

Doramagic extracts the **soul** of open-source projects and compiles it into injectable AI advisor packs (Skill bundles).

## When to Use This Skill

Use this skill when the user:

- Provides a GitHub URL and wants to extract design wisdom from it
- Names a project and wants to learn its design philosophy
- Describes a domain need (e.g., "I want a tool for X") — Doramagic will find relevant open-source projects and extract wisdom
- Wants to understand WHY a project was designed a certain way, not just WHAT it does

Do NOT use this skill for:

- Building apps or writing code from scratch (Doramagic produces knowledge, not code)
- Tasks unrelated to learning from open-source projects

**Important:** When the user describes a personal need or domain interest without mentioning specific repos, this IS a valid use case. Doramagic's DOMAIN_EXPLORE route will search GitHub for relevant projects automatically.

## How to Use

Run the pipeline with the user's input:

```bash
python3 {baseDir}/scripts/doramagic_main.py --input "{args}" --run-dir ~/.doramagic/runs/
```

The script outputs JSON. Show the `message` field to the user exactly as-is.

If the output has `"error": true`, show the error message and stop.

## Example Usage in Chat

**User:** "/dora https://github.com/fastapi/fastapi"
**Action:** Run the command with input "https://github.com/fastapi/fastapi"

**User:** "/dora Extract wisdom from Home Assistant"
**Action:** Run the command with input "Extract wisdom from Home Assistant"

**User:** "/dora I want a tool for managing family recipes and weekly menus"
**Action:** Run the command with input "I want a tool for managing family recipes and weekly menus"
(Doramagic will search GitHub for recipe/menu open-source projects and extract their design wisdom)

**User:** "/dora 我想要一个英语学习工具"
**Action:** Run the command with input "我想要一个英语学习工具"
(Doramagic will search GitHub for English learning open-source projects)

**User:** "/dora-status"
**Action:** Run the command with input "/dora-status" to check the latest run status

## Protocol

- **Always run the script.** Do not skip execution or substitute your own analysis.
- Show the `message` field to the user **exactly as-is**.
- Do NOT add your own content, analysis, or commentary to the script output.
- Do NOT judge whether the user's request is appropriate — the script handles all routing internally.
- Do NOT run any additional commands after the script finishes.

## Self-Contained Skill Bundle

The skills/doramagic/ directory mirrors packages/ and bricks/ intentionally.
This ensures the skill is self-contained and deployable without the parent repo.
