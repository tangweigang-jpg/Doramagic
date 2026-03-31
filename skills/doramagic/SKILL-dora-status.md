---
name: dora-status
description: >
  Check the status of an ongoing Doramagic extraction. Shows which phase is
  running and completion status. Use when asked "is my extraction done?"
version: 13.0.0
user-invocable: true
license: MIT
tags: [doramagic, status]
metadata: {"openclaw":{"emoji":"📊","skillKey":"dora-status","category":"builder","requires":{"bins":["python3"]}}}
---

# Doramagic — Status Checker

IRON LAW: ONLY QUERY. DO NOT MODIFY ANYTHING.

---

## Step 1: Query Status

```bash
python3 {baseDir}/scripts/doramagic_main.py --input "/dora-status" --run-dir ~/.doramagic/runs/
```

## Step 2: Report

Show the `message` field to the user.
If `"error": true`, show the error message and stop.

---

## Prohibited Actions

- Do NOT modify any files or state
- Do NOT launch new extractions
- Do NOT generate code
