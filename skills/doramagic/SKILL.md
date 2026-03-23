---
name: dora
description: >
  Doramagic — extract design wisdom from open-source projects and forge skills.
version: 9.0.0
user-invocable: true
tags: [doramagic, knowledge-extraction, skill-generation]
metadata:
  openclaw:
    skillKey: dora
    category: builder
    requires:
      bins: [python3]
    storage_root: ~/clawd/doramagic/runs/
---

python3 ~/.openclaw/skills/soul-extractor/scripts/doramagic_main.py --input "{args}" --run-dir ~/clawd/doramagic/runs/

---

## Protocol

Script output is JSON. Two modes:

### Normal output
Show the `message` field to the user exactly as-is.

### Clarification output
If output has `"clarification": true`, show the `question` field and wait for user's answer.
Then re-invoke with: `python3 ~/.openclaw/skills/soul-extractor/scripts/doramagic_main.py --continue {run_id} --input "{user_answer}" --run-dir ~/clawd/doramagic/runs/`

### Progress output
If output has `"progress": true`, show the `message` field as a status update. More output will follow.

## Constraints

- Show the `message` field to the user exactly as-is.
- Do NOT add your own content, analysis, or commentary.
- Do NOT run any additional commands after the script finishes (unless clarification is needed).
- If the output has `error: true`, show the error message and stop.
