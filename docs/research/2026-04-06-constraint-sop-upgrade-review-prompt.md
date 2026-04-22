# Review Prompt: Constraint Collection SOP v1.3 Upgrade

## Your Role

You are a **senior knowledge engineer** who specializes in building structured knowledge systems for AI agents. You have deep experience in both quantitative finance and AI-driven code generation systems.

## CRITICAL INSTRUCTION

**You must reason from first principles.** Do not pattern-match from similar-sounding systems or give generic advice. For every recommendation you make:
1. State the underlying truth or axiom you're reasoning from
2. Show the logical chain from axiom to conclusion
3. If you don't have enough information to reason rigorously, say so explicitly — do NOT fill the gap with plausible-sounding but ungrounded claims

## Background: What is Doramagic?

Doramagic is a knowledge compilation system that extracts structured knowledge from GitHub open-source projects and compiles it into "seed crystals" — self-contained instruction documents that guide AI agents to autonomously build complete working systems (e.g., a quantitative backtesting system).

### The Core Formula

**Good Crystal = Good Blueprint + Good Resources + Good Constraints**

- **Blueprint**: Describes *how the framework works* — architecture, components, data flows, design decisions. Extracted from source code.
- **Resources**: Everything (besides the LLM itself) needed to make the crystal become a working skill — APIs, tools, data sources, execution engines.
- **Constraints**: Guardrails that prevent the AI from making known mistakes — technical bugs, domain rule violations, dangerous assumptions.

### What We've Done So Far

1. **59 blueprints** extracted from open-source quant projects (zipline, qlib, vnpy, zvt, freqtrade, etc.)
2. **3,257 constraints** extracted from the same projects
3. **v9 seed crystal** successfully tested end-to-end (AI autonomously built and executed an A-stock momentum backtest in 6 minutes)

### The Problem We Just Discovered

We recently upgraded our **Blueprint Extraction SOP** (v2.2 → v2.3) to distinguish **technical architecture** from **business decisions** within blueprints. Each design decision is now classified as:

| Type | Code | Definition |
|------|------|-----------|
| Technical | T | Changing implementation doesn't affect investment outcomes |
| Business Decision | B | Changing it alters trading behavior |
| Business Assumption | BA | Encodes a market/economic assumption |
| Domain Knowledge | DK | Market-specific institutional knowledge |
| Regulatory Constraint | RC | Mandated by law/exchange rules |

We upgraded blueprint BP-009 (zvt, a Chinese A-stock framework) as a pilot:
- Added **26 business_decisions** entries (tagged T/B/BA/DK/RC)
- Added **9 known_use_cases** (indexed from examples/)
- Identified **7 critical missing gaps** (涨跌停/停牌/ST/除权除息/成分股/新股/流动性)

### The Gap We Found in Constraints

After upgrading the blueprint, we audited the corresponding constraints and found a **massive mismatch**:

**BP-009 has 56 existing constraints. Here is their distribution:**

| constraint_kind | Count | What they cover |
|-----------------|-------|-----------------|
| architecture_guardrail | 22 | Schema inheritance, Recorder metaclass, storage structure |
| domain_rule | 16 | Signal delay, factor computation, stock selection logic |
| operational_lesson | 11 | force_update behavior, data source switching |
| resource_boundary | 4 | QMT Windows-only, data source limitations |
| claim_boundary | 3 | No high-frequency/tick-level support |

**Only 3 out of 56 constraints mention A-share regulatory rules** (2 about T+1, 1 about price adjustment Schema). The blueprint's 7 critical missing gaps (涨跌停, 停牌, ST, 除权除息, etc.) have **ZERO corresponding constraints**.

This means: **The blueprint says "涨跌停 is a critical gap," but no constraint tells the AI "you must handle 涨跌停."**

## What We're Proposing: Constraint SOP v1.3

We want to add a new step to our Constraint Collection SOP:

### New Step 2.4: Blueprint-Driven Business Constraint Derivation

After extracting constraints from source code (Steps 2.1-2.3), derive additional constraints from the upgraded blueprint's `business_decisions` field:

| Blueprint type | Derive what | constraint_kind | Rule |
|---------------|------------|-----------------|------|
| RC (Regulatory) | Regulatory compliance constraints | domain_rule | Every RC entry → 1 must/must_not constraint |
| BA (Business Assumption) | Risk warning constraints | operational_lesson | Only for BA entries with known_issue or explicit bias |
| missing gap (status: missing) | Known deficiency constraints | claim_boundary | Every missing entry → 1 must_not constraint ("do not assume framework handles X") |

**Not derived**: T (technical), DK (already covered by source extraction), resource_boundary (already covered)

### Expected Output for BP-009

- Existing: 56 constraints (mostly technical)
- New derivations: ~14-18 constraints (RC: 4-6, BA: 3-5, missing: 7)
- Total after upgrade: ~70-74 constraints

## Your Review Tasks

### Task 1: Evaluate the Derivation Logic

1. Is the mapping from blueprint types (RC/BA/missing) to constraint_kinds (domain_rule/operational_lesson/claim_boundary) correct?
2. Should RC constraints always be `domain_rule`? Or should we add a new constraint_kind (e.g., `regulatory_rule`)?
3. Is it right to only derive BA constraints for entries with `known_issue`? Should ALL business assumptions get constraints?
4. Is `claim_boundary` the right kind for missing gaps? Or should it be something else?

### Task 2: Evaluate the Derivation Scope

1. We're NOT deriving constraints for T (Technical) and DK (Domain Knowledge). Is this correct?
2. The blueprint has `known_use_cases` (9 entries). Should constraints be derived from use cases too? (e.g., "when implementing MACD golden cross strategy, must verify signal delay")
3. Should we derive constraints from the `rationale` field of business decisions? (e.g., "先卖后买 rationale says '隐含无杠杆假设'" → constraint: "must not assume margin trading is available")

### Task 3: Evaluate Practical Risks

1. **Constraint explosion**: Adding 14-18 constraints per blueprint × 59 blueprints = 800-1000 new constraints. Is this manageable? Will it dilute the quality of the constraint database?
2. **Circular dependency**: Blueprint references constraints, and now constraints are derived from blueprint. Is there a risk of circular logic?
3. **Maintenance burden**: When blueprint business_decisions change, derived constraints must be updated. How should we track this dependency?
4. **Over-constraining**: Could too many "must_not assume" constraints make the AI overly cautious and unable to build anything?

### Task 4: Evaluate for Chinese A-Share Specifics

Given that BP-009 is a Chinese A-stock framework, evaluate whether the proposed constraints would actually prevent the most common AI mistakes:

1. Would a `must_not` constraint about 涨跌停 actually prevent an AI from generating code that buys at limit-up prices?
2. Would a `should` constraint about sell_cost actually make the AI verify the cost model before backtesting?
3. What's the #1 A-share business constraint you would add that our proposal doesn't cover?

### Task 5: Alternative Approaches

Instead of deriving constraints from blueprints, are there better approaches?

1. Should business constraints be a separate knowledge layer (not mixed into the constraint database)?
2. Should they be embedded directly in the crystal's directive section instead?
3. Should we use a different mechanism entirely (e.g., pre-flight checks, runtime validation)?

## Constraint Schema Reference

For context, each constraint follows this structure:

```json
{
  "id": "finance-C-XXX",
  "core": {
    "when": "实现 X 时",
    "modality": "must | must_not | should | should_not",
    "action": "做/不做 Y"
  },
  "consequence": {
    "kind": "bug | financial_loss | compliance | ...",
    "description": "具体失败现象（≥20字）"
  },
  "constraint_kind": "domain_rule | architecture_guardrail | operational_lesson | resource_boundary | claim_boundary",
  "severity": "fatal | high | medium | low",
  "applies_to": {
    "blueprint_ids": ["finance-bp-009"],
    "stage_ids": ["trader_engine"],
    "target_scope": "stage"
  }
}
```

## Deliverable

Please provide:
1. Score (1-10) for the overall approach
2. Specific issues with the derivation rules (with corrections)
3. Your recommended modifications to the SOP
4. Risk assessment (what could go wrong)
5. Your verdict: Should we proceed with this approach, modify it, or take a completely different direction?
