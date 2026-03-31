---
name: dora-build
description: >
  Generate production-grade code based on knowledge brick constraints from
  /dora-match. Produces a complete, runnable tool and delivers it to the user.
  Use after /dora-match has returned constraints.
version: 13.0.0
user-invocable: false
license: MIT
tags: [doramagic, code-generation]
metadata: {"openclaw":{"emoji":"⚡","skillKey":"dora-build","category":"builder","requires":{"bins":["python3"]}}}
---

# Doramagic — Code Generator

IRON LAW: EVERY LINE OF GENERATED CODE MUST FOLLOW THE CONSTRAINT_PROMPT.
If no constraint_prompt exists in the session, do NOT generate code.

---

## Step 1: Load Constraints

```bash
cat ~/.doramagic/sessions/latest.json
```

Extract `constraint_prompt`, `capabilities`, `limitations`, `risk_report`, `evidence_sources`.

If `phase` is not `"matched"`, tell the user:
"Please run /dora-match first to match knowledge bricks."

If `constraint_prompt` is empty, proceed with general knowledge but warn the user:
"No domain-specific constraints found. Generating with general knowledge — quality may vary."

---

## Step 2: Generate Code

Generate a complete, runnable Python script that:
1. Follows every rule in `constraint_prompt`
2. Implements the user's requirement (from session `requirement` field)
3. Includes error handling and logging
4. Can run directly with `python3 script.py`

Save to file:
```bash
mkdir -p ~/.doramagic/generated
cat > ~/.doramagic/generated/{tool_name}.py << 'CODEOF'
{your generated code}
CODEOF
```

---

## Step 3: Verify

```bash
python3 -c "import ast; ast.parse(open('$HOME/.doramagic/generated/{tool_name}.py').read()); print('Syntax OK')"
```

If verification fails, fix the code and retry (max 3 times).
If all retries fail, tell the user honestly and stop.

---

## Step 4: Run and Deliver

Run the tool:
```bash
python3 ~/.doramagic/generated/{tool_name}.py &
```

Report to the user with ALL of these (mandatory):

1. **Status**: "Your tool is running!" + what it's doing
2. **Capability boundaries**: What it can and cannot do (from `capabilities` and `limitations`)
3. **Risk warnings**: Paraphrased in simple language (from `risk_report`)
4. **Knowledge sources**: "These recommendations come from N verified sources" (from `evidence_sources`)

---

## Step 5: Iteration (when user wants changes)

When the user says "change it", "make it...":
1. Read the previously generated code file
2. Modify following `constraint_prompt` constraints
3. Verify syntax
4. Re-run and report

---

## Prohibited Actions

- Do NOT skip constraint_prompt when generating code
- Do NOT show code unless the user explicitly asks
- Do NOT show raw JSON
- Do NOT omit capability boundaries or risk warnings from delivery
- Do NOT run brick matching — that's /dora-match's job
