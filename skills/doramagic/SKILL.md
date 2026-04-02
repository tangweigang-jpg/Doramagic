---
name: dora
description: >
  Doramagic: 你的 AI 哆啦A梦 — 说出需求，从 10,000+ 知识砖块中锻造可用工具。
  Triggers on: "dora", "doramagic", "帮我做", "我需要一个", "帮我生成".
version: 13.3.1
user-invocable: true
license: MIT-0
tags: [doramagic, knowledge-extraction, skill-generation, tool-forge]
metadata:
  openclaw:
    emoji: "🪄"
    skillKey: dora
    category: builder
---

# Doramagic — Tool Forge

Skill dir: `~/.openclaw/workspace/skills/dora/`

## Step 1: 选域

Read `~/.openclaw/workspace/skills/dora/references/brick-catalog.md`

选 2-5 个域（必含 skill_architecture），只选 catalog 中的 domain_id。告诉用户选了什么，等确认。

## Step 2: 读砖块 + 向用户展示全部发现

对每个域 Read `~/.openclaw/workspace/skills/dora/references/bricks/{domain_id}.md`

向用户完整展示以下内容（这些内容 Step 3 将直接写入文件）：
1. 所有 FAILURE 条目（逐条，标为 ⚠️）
2. 所有 CONSTRAINTS
3. 关键 PATTERNS 和 RATIONALE

## Step 3: 将 Step 2 的内容写入文件

用 write 工具将以下格式的文件写入 `~/clawd/doramagic/generated/SKILL_KEY/SKILL.md`（write 自动创建目录，不要用 exec）。

文件必须严格使用以下格式，用 Step 2 展示过的内容填充：

    ---
    name: SKILL_KEY
    description: 一句话描述
    version: 1.0.0
    ---

    # 工具标题

    ## How to Use
    ### Step 1: 具体操作
    ### Step 2: 具体操作
    ### Step 3: 具体操作

    ## Key Patterns
    - [域名] 来自砖块的具体模式
    - [域名] 来自砖块的设计原理

    ## ⚠️ Warnings
    ⚠️ **[域名]** Step 2 展示过的每条 failure 都要出现在这里
    （逐条列出，数量必须等于 Step 2 中展示的 failure 数量）

    ## Provenance
    | Domain | Type | How Used |
    |--------|------|----------|
    | 域名 | failure | ⚠️ 摘要 |
    | 域名 | pattern | 如何应用 |

    ## Limitations
    - 此工具不能做什么
    - 使用 /dora-extract 进行更深入分析

写入后告诉用户文件位置。如果 write 失败，将上述内容直接展示给用户。
