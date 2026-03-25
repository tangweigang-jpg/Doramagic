---
name: dora
description: >
  Doramagic: extract the soul of open-source projects — design philosophy, decision rules,
  and community wisdom compiled into injectable AI advisor packs.
  Triggers on: "dora", "doramagic", "extract soul", "extract knowledge".
version: 10.0.0
user-invocable: true
license: MIT
tags: [doramagic, knowledge-extraction, skill-generation]
metadata: {"openclaw":{"emoji":"🪄","skillKey":"dora","category":"builder","requires":{"bins":["python3","git","bash"]}}}
---

python3 {baseDir}/scripts/doramagic_singleshot.py --input "{args}" --run-dir ~/.doramagic/runs/

---

## Protocol

Script output is JSON. Two modes:

### Normal output
Show the `message` field to the user exactly as-is.

### Error output
If output has `error: true`, show the error message and stop.

## Constraints

- Show the `message` field to the user exactly as-is.
- Do NOT add your own content, analysis, or commentary.
- Do NOT run any additional commands after the script finishes.
