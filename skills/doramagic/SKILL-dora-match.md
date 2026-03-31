---
name: dora-match
description: >
  Match knowledge bricks (constraints, failure patterns, API contracts) from
  Doramagic's 10,000+ brick library. Returns constraint_prompt for code generation.
  Use after /dora has clarified the requirement.
version: 13.0.0
user-invocable: false
license: MIT
tags: [doramagic, brick-matching]
metadata: {"openclaw":{"emoji":"🧱","skillKey":"dora-match","category":"builder","requires":{"bins":["python3"]}}}
---

# Doramagic — Brick Matcher

IRON LAW: NO CODE GENERATION WITHOUT RUNNING THE BRICK MATCHING SCRIPT.
Do NOT guess constraints. Do NOT substitute your own knowledge. Run the script.

---

## Step 1: Read Requirement

```bash
cat ~/.doramagic/sessions/latest.json
```

Extract the `requirement` field. If file is missing or empty, tell the user:
"Please start with /dora first to clarify your requirement."

---

## Step 2: Run Brick Matching

Tell the user: "Matching relevant constraints from the knowledge base..."

```bash
python3 {baseDir}/scripts/doramagic_compiler.py --input "{requirement}" --user-id "default"
```

The script returns JSON with:
- `success`: Whether matching succeeded
- `matched_bricks`: List of matched brick IDs
- `constraint_count`: Number of constraints
- `constraint_prompt`: Rules for code generation
- `capabilities`: What the tool can do
- `limitations`: What the tool cannot do
- `risk_report`: Risk analysis
- `evidence_sources`: Knowledge source URLs

---

## Step 3: Save Results to Session

```bash
python3 -c "
import json
session = json.load(open('$HOME/.doramagic/sessions/latest.json'))
result = {the JSON output from Step 2}
session['phase'] = 'matched'
session['constraint_prompt'] = result.get('constraint_prompt', '')
session['constraint_count'] = result.get('constraint_count', 0)
session['capabilities'] = result.get('capabilities', [])
session['limitations'] = result.get('limitations', [])
session['risk_report'] = result.get('risk_report', {})
session['evidence_sources'] = result.get('evidence_sources', [])
session['matched_bricks'] = result.get('matched_bricks', [])
json.dump(session, open('$HOME/.doramagic/sessions/latest.json', 'w'), ensure_ascii=False, indent=2)
"
```

---

## Step 4: Report and Route

Tell the user:
> "Found N relevant bricks with M constraints. Generating your tool now..."

Then invoke: `/dora-build`

---

## Error Handling

| Scenario | Action |
|----------|--------|
| Script not found | "Doramagic needs setup. Run `openclaw skills update dora`" |
| 0 bricks matched | Save empty constraint_prompt to session, tell user "Knowledge base doesn't cover this domain well yet. Generating with general knowledge." Then still invoke `/dora-build`. |
| Script error | Show error message, stop. Do not proceed. |

## Prohibited Actions

- Do NOT generate code — that's /dora-build's job
- Do NOT invent constraints from your own knowledge
- Do NOT modify the constraint_prompt returned by the script
- Do NOT skip running the script
