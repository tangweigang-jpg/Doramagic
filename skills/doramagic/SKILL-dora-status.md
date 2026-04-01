---
name: dora-status
description: >
  Check the status of a running Doramagic extraction or compilation task.
  Triggers on: "dora-status", "dora status", "提取进度", "任务状态".
version: 13.2.0
user-invocable: true
license: MIT-0
metadata:
  openclaw:
    emoji: "📊"
    skillKey: dora-status
    category: builder
    requires:
      bins: [python3]
---

# Doramagic — Task Status

Check the status of running or completed Doramagic tasks.

---

## Step 1: Query Status

```bash
python3 {baseDir}/scripts/doramagic_main.py --input "/dora-status" --run-dir ~/clawd/doramagic/runs/
```

## Step 2: Report

Show the `message` field to the user.

- If tasks are running, report the current phase and run ID.
- If no tasks exist, tell the user: "No active Doramagic tasks found."

## Prohibited Actions

- Do NOT start new extractions or compilations from this skill
- Do NOT guess task status — always run the script
