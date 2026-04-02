# Scaffold: 生成的工具 SKILL.md

用砖块知识替换所有 REPLACE 占位符。输出"---"以下的完整文件内容。

---

---
name: REPLACE_WITH_SKILL_KEY
description: >
  REPLACE_WITH_DESCRIPTION
version: 1.0.0
---

# REPLACE_WITH_TITLE

## How to Use

### Step 1: REPLACE_WITH_ACTION
REPLACE with concrete instructions the user follows.

### Step 2: REPLACE_WITH_ACTION
REPLACE with concrete instructions.

### Step 3: REPLACE_WITH_ACTION
REPLACE with concrete instructions.

## Key Patterns

Use PATTERNS and RATIONALE from the brick summaries:

- [DOMAIN] REPLACE with a concrete implementation pattern
- [DOMAIN] REPLACE with a design rationale
- [DOMAIN] REPLACE with another pattern or principle

## ⚠️ Warnings

For EVERY FAILURE from Step 2, write one warning:

⚠️ **[DOMAIN]** REPLACE with full failure description — trap, consequence, and mitigation.

Continue until ALL failures are covered.

## Provenance

| Domain | Type | How Used |
|--------|------|----------|
| REPLACE | failure | ⚠️ REPLACE with summary |
| REPLACE | pattern | REPLACE with how applied |
| REPLACE | rationale | REPLACE with how applied |

Continue for ALL brick entries used.

## Limitations

- REPLACE with what this tool cannot do
- REPLACE with scope gaps
- For deeper analysis, use `/dora-extract`

RULES:
- SELF-CHECK before outputting:
  1. No REPLACE text remaining
  2. YAML frontmatter starts on line 1 (no code fences)
  3. ⚠️ count matches failure count from Step 2
  4. Provenance table has one row per brick entry used
  5. Workflow steps are concrete, not generic advice
