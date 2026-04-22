# Challenge Prompt: Review the zvt Business Logic Extraction Experiment

## Your Role

You are a senior quantitative researcher AND knowledge engineering expert. Your job is to critically challenge an experiment report that attempts to extract "business logic" from an open-source Chinese A-stock quantitative framework (zvtvz/zvt).

The goal is NOT to be nice. The goal is to find every weakness, blind spot, and wrong assumption so we can improve.

## Context

We are building Doramagic, a system that extracts structured knowledge from GitHub open-source projects and compiles it into AI-executable instruction documents ("seed crystals"). We currently extract two layers:

1. **Blueprints**: Framework architecture (how the software works internally)
2. **Constraints**: Technical guardrails (what can go wrong)

We discovered a missing third layer: **business logic** — what specific things can you BUILD with the framework. An experiment was conducted on the zvtvz/zvt project to figure out what "business logic" actually means and what it looks like.

## The Experiment Report

Below is the full experiment report. Please read it carefully, then provide your critique.

---

[BEGIN REPORT]

### Key Claims Made by the Report

1. **Definition**: "Business logic = Domain Semantics + Parameter Decisions + Complete Workflow"

2. **Three types of business logic**:
   - Factor Semantics (what an indicator means in investment terms)
   - Strategy Workflow (end-to-end signal-to-trade process)
   - Screening Logic (multi-dimensional stock filtering rules)

3. **What blueprints are missing**: Specific factor definitions, parameter rationale, end-to-end strategy semantics, signal-to-decision mapping

4. **Best extraction granularity**: `examples/trader/` files — complete strategy files with inputs/outputs/parameters/flow

5. **Two "business logic cards" produced**:
   - Card 1: MACD Daily Golden Cross Trading Strategy
   - Card 2: Multi-factor Fundamental Stock Screening

6. **Granularity framework**: "Too fine" (single indicator) → "Just right" (complete workflow) → "Too coarse" (platform description)

### The Business Logic Cards Format

```
Name:
Business Problem: (one sentence)
Inputs:
Outputs:
Core Steps: (3-8 steps)
Parameters: (configurable values)
Validation Criteria: (how to verify correctness)
Framework Dependencies: (which components are used)
```

[END REPORT]

---

## Your Challenge Tasks

Please critically evaluate the following dimensions:

### 1. Definition Challenge
- Is "Business logic = Domain Semantics + Parameter Decisions + Complete Workflow" the right definition? What's missing?
- Are the three types (Factor Semantics, Strategy Workflow, Screening Logic) exhaustive? What about risk management logic, position sizing logic, execution timing logic, performance attribution logic?
- Is this definition specific to quantitative finance, or can it generalize to other domains (e.g., ML pipelines, data engineering)?

### 2. Extraction Completeness Challenge
- The experiment only read 2-3 factor files and 2-3 examples. What critical business logic might have been missed?
- zvt has 30+ factor modules — is sampling 2-3 sufficient to draw conclusions?
- What about business logic embedded in the Trader base class itself (default behaviors, implicit assumptions)?
- What about the DATA layer's business logic (e.g., how adjusted prices are calculated, dividend handling)?

### 3. Card Format Challenge
- Is the 8-field card format sufficient to capture all business logic?
- What fields are missing? Consider: assumptions, limitations, market regime sensitivity, correlation with other strategies, historical performance characteristics
- Should "Validation Criteria" be split into "Correctness Validation" (no bugs) vs "Business Validation" (strategy actually works)?
- How should the card handle the relationship between a factor (Component) and a strategy (Pattern) that uses it?

### 4. Granularity Challenge
- The report says single factors are "too fine" — but isn't `GoodCompanyFactor` with its 8 criteria and 3-year window already a complete business methodology?
- The report says platform descriptions are "too coarse" — but what about README's "institutional tracking: buy when holdings increase >5%" — isn't that a perfectly sized business logic statement?
- Is the granularity framework binary (Component vs Pattern), or should there be intermediate levels?

### 5. Blind Spot Challenge
- The experiment focused entirely on EXPLICIT business logic (written in code). What about IMPLICIT business logic?
  - Default parameter values encode business assumptions (why stop-loss at -30% and not -20%?)
  - Inheritance hierarchies encode business decisions (why does Trader always sell before buying?)
  - Data schema design encodes domain knowledge (why is turnover_rate a first-class field?)
- What about NEGATIVE business logic — things the framework deliberately does NOT support and why?
- What about the EVOLUTION of business logic — how strategies change across git commits?

### 6. Practical Challenge
- If we extract 11 business logic cards from zvt (7 traders + 4 factors), is that actually useful for compiling better seed crystals?
- How would a compiled crystal WITH business logic cards differ from one WITHOUT?
- Can you sketch what a crystal compiled from "blueprint + business logic card + constraints" would look like vs the current "blueprint + constraints" crystal?

## Deliverable

Please provide:
1. A scored evaluation (1-10) for each of the 6 dimensions above
2. The top 3 most critical weaknesses in the experiment
3. Your recommended improvements (concrete, actionable)
4. If you disagree with any core claim, explain what you think the correct answer is
