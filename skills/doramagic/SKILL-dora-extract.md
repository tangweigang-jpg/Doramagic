---
name: dora-extract
description: >
  Extract the "soul" of a GitHub project — design philosophy, failure patterns,
  and community wisdom. Produces a knowledge package. Use when given a GitHub URL
  or asked to "extract soul".
version: 13.0.0
user-invocable: true
license: MIT
tags: [doramagic, soul-extraction]
metadata: {"openclaw":{"emoji":"🔮","skillKey":"dora-extract","category":"builder","requires":{"bins":["python3","git"]}}}
---

# Doramagic — Soul Extractor

IRON LAW: ALL EXTRACTION PHASES RUN SEQUENTIALLY. NO SKIPS.
Do not summarize or guess — run the extraction script and report its output.

---

## Step 1: Launch Extraction

Tell the user: "Starting soul extraction... this may take a few minutes."

```bash
python3 {baseDir}/scripts/doramagic_main.py --async --input "{github_url_or_description}" --run-dir ~/.doramagic/runs/
```

The script returns JSON immediately with a `message` field. Show it to the user.

---

## Step 2: Poll for Results

Wait 120 seconds, then check status:

```bash
python3 {baseDir}/scripts/doramagic_main.py --input "/dora-status" --run-dir ~/.doramagic/runs/
```

- If `"completed": true` → proceed to Step 3
- If `"completed": false` → wait 60 seconds, retry (max 5 times)
- After 5 retries still incomplete → tell user: "Extraction is running in background. Check later with /dora-status"

Send ONE brief status message while waiting. Do NOT send repeated "please wait" messages.

---

## Step 3: Deliver Results

When complete, show the `message` field to the user.
If `"error": true`, show the error and stop.

---

## Prohibited Actions

- Do NOT guess extraction results
- Do NOT generate code (this skill extracts knowledge, not code)
- Do NOT skip the polling step
