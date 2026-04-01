---
name: dora
description: >
  Doramagic: 你的 AI 哆啦A梦 — 说出需求，从 10,000+ 知识砖块中锻造可用工具。
  Triggers on: "dora", "doramagic", "帮我做", "我需要一个", "帮我生成".
version: 13.2.0
user-invocable: true
license: MIT-0
tags: [doramagic, knowledge-extraction, skill-generation, tool-forge]
hooks:
  PreToolUse:
    - matcher: "Write"
      command: "bash {baseDir}/scripts/check-bricks-matched.sh"
metadata:
  openclaw:
    emoji: "🪄"
    skillKey: dora
    category: builder
    requires:
      bins: [python3, git]
---

# Doramagic — Tool Forge

IRON LAW: 先运行编译器，再交付。绝不跳过积木匹配直接生成代码。

---

## Step 1: Run the Compiler

Tell the user: "正在从 10,000+ 知识砖块中匹配你的需求..."

```bash
python3 {baseDir}/scripts/doramagic_main.py --input "{user_request}" --run-dir ~/clawd/doramagic/runs/
```

The script handles everything automatically:
- Socratic dialogue (requirement clarification)
- Brick matching (knowledge base lookup)
- Constraint injection
- Code generation with quality gates

If the script returns `"needs_clarification": true`, show the questions to the user and wait for answers. Then resume:

```bash
python3 {baseDir}/scripts/doramagic_main.py --continue {run_id} --input "{user_answer}" --run-dir ~/clawd/doramagic/runs/
```

## Step 2: Deliver Results

Show the `message` field from the script output to the user. Do not rewrite or paraphrase it.

If the output includes code, present it with:
1. What the tool does (1-2 sentences)
2. The code
3. How to save and run
4. Required environment variables

If the output is a dialogue protocol (learning/practice), start the session immediately.

## Rules

- Reply in the user's language
- Do NOT generate code yourself — always use the compiler output
- Do NOT skip Step 1 — the hook will block you if you try
- Do NOT call /dora-extract from here (that's a separate skill)
