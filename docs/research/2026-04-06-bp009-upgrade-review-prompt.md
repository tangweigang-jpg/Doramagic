# Review Prompt: Evaluate the BP-009 Blueprint Upgrade (v2.3)

## Your Role

You are a **senior quantitative systems architect** who has both built trading systems AND designed knowledge management systems for AI agents. You will evaluate a blueprint upgrade that adds "business decision" annotations to a previously architecture-only document.

## Context

### What is a Blueprint?

A "blueprint" is a structured YAML document extracted from an open-source GitHub project. It describes **how the framework works** — components, interfaces, data flows, design decisions. It is consumed by an AI compiler to produce "seed crystals" (execution instructions for AI agents).

### The Problem We Discovered

Our blueprints extracted from source code mixed **technical architecture** with **business decisions** without distinguishing them. For example:

- "Uses SQLite storage" → Technical choice (changing it doesn't affect investment outcomes)
- "Sells before buying" → Business decision (changing it alters capital management behavior)
- "Default stop-loss at -30%" → Business assumption (encodes a market philosophy)
- "T+1 settlement" → Regulatory constraint (mandated by Chinese securities law, not author's choice)

An AI agent reading the blueprint couldn't tell which design decisions were safe to modify and which encoded critical domain knowledge.

### What Was Done

We upgraded blueprint BP-009 (zvt — a Chinese A-stock quantitative framework) by adding two new sections:

1. **`business_decisions`** (23 entries): Each design decision classified as T (Technical), B (Business Decision), BA (Business Assumption), DK (Domain Knowledge), or RC (Regulatory Constraint)
2. **`known_use_cases`** (9 entries): An index of example strategies and workflows found in the project's `examples/` directory

The upgrade was done by:
1. First auditing the existing blueprint to identify which design decisions were business-relevant
2. Four independent AI reviews (Claude/Grok/Gemini/GPT) challenged the audit
3. Corrections were applied (e.g., T+1 reclassified from B to RC, stamp tax rate updated to 0.05%)
4. The blueprint YAML was modified to add the two new sections

### The Classification Framework (5 types)

| Type | Code | Definition | Example |
|------|------|-----------|---------|
| Technical | T | Changing implementation doesn't affect investment outcomes | SQLite vs PostgreSQL |
| Business Decision | B | Changing it alters trading behavior | Sell before buy |
| Business Assumption | BA | Encodes a market/economic assumption (the "why" behind B) | Stop-loss at -30% |
| Domain Knowledge | DK | Market-specific institutional/cultural knowledge | turnover_rate as first-class field |
| Regulatory Constraint | RC | Mandated by law/exchange rules, not author's choice | T+1 settlement, daily price limits |

## What You Need to Evaluate

Below is the COMPLETE upgraded blueprint. The new sections are `business_decisions` (line 61) and `known_use_cases` (line 256). Everything else (stages, edges, global_contracts) is unchanged from the original.

[Paste the full content of the upgraded finance-bp-009.yaml here]

## Evaluation Dimensions

### Dimension 1: Classification Quality (most important)

For the 23 business_decisions entries:

1. **Accuracy**: Are the T/B/BA/DK/RC classifications correct? Find any misclassifications.
2. **Completeness**: Are there important business decisions in the blueprint's `design_decisions` or `pseudocode_example` fields that were NOT captured in `business_decisions`?
3. **Rationale quality**: Are the explanations clear, specific, and actionable? Would an AI agent understand WHY this matters?
4. **Missing items with `status: missing`**: Are the 6 marked gaps (涨跌停, 停牌, ST, 除权除息, 成分股, 新股) truly the most critical ones? Are any others missing?

### Dimension 2: A-Share Domain Accuracy

As someone who knows Chinese A-stock markets:

1. Is the stamp tax rate (0.05% since 2023-08-28) correct and current?
2. Are the cost model parameters (buy_cost=0.001, sell_cost=0.001, slippage=0.001) reasonable? What would you use?
3. Is the characterization of "-30% stop-loss as a teaching framework default" accurate?
4. Are the severity ratings for missing items correct? (涨跌停=critical, 除权除息=critical, 停牌=high, ST=high, 成分股=medium, 新股=medium)

### Dimension 3: Use Case Index Quality

For the 9 known_use_cases:

1. Are these the right examples to highlight? Are important ones missing?
2. Are the `business_problem` descriptions accurate and useful?
3. Would this index help an AI compiler select the right use case for a user's intent?

### Dimension 4: Practical Value

The key question: **Does this upgrade make the blueprint more useful?**

1. Compare the original blueprint (architecture only) vs the upgraded version (architecture + business decisions + use cases). What can an AI agent do with the upgraded version that it couldn't before?
2. If you were building a trading system using zvt and an AI gave you a seed crystal compiled from the UPGRADED blueprint, would the business_decisions section prevent real mistakes?
3. Is the T/B/BA/DK/RC framework worth applying to other blueprints, or is it over-engineering?

### Dimension 5: What's Still Missing?

After this upgrade, what important knowledge is STILL not captured in the blueprint? Consider:

1. Market regime awareness (bull vs bear market behavior differences)
2. Liquidity constraints (small-cap vs large-cap execution feasibility)  
3. Seasonal patterns (Chinese New Year effect, quarterly reporting windows)
4. Cross-strategy interaction (momentum + value factor correlation)
5. Data quality issues specific to Chinese data providers

## Deliverable

Please provide:
1. A score (1-10) for each of the 5 dimensions
2. Specific misclassifications or errors found (with corrections)
3. Top 3 strengths of the upgrade
4. Top 3 remaining weaknesses
5. Your verdict: Is this blueprint upgrade approach worth scaling to 58 more blueprints? (Yes/No/Conditional)
