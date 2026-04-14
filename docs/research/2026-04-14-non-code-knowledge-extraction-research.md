# Non-Code Knowledge Extraction Research Report

> **Date**: 2026-04-14
> **Author**: Claude Opus 4.6 + CEO
> **Status**: Experiment completed, schema validated
> **Next**: Blueprint extraction SOP (ai-skill domain) + agent upgrade

---

## 1. Background & Motivation

Doramagic's Blueprint + Constraint + Crystal architecture was designed for **code projects** — reverse-engineering architecture from source code. But an increasing number of high-value AI projects are **non-code**: prompt libraries, skill frameworks, agent behavior specifications.

Three representative projects were selected for study:

| Project | Type | Key Characteristic |
|---------|------|-------------------|
| [obra/superpowers](https://github.com/obra/superpowers) | Pure skill library | 14 skills, pure .md, 151K stars, zero code logic |
| [bytedance/deer-flow](https://github.com/bytedance/deer-flow) skills/public | Framework-embedded skills | 21 skills, framework contracts, eval ecosystem |
| [anthropics/claude-code](https://github.com/anthropics/claude-code) | Complete AI agent | Distributed knowledge across CLAUDE.md, skills, agents, hooks |

**Core question**: Can the existing Blueprint schema handle non-code projects, or does it need fundamental redesign?

---

## 2. Research Methodology

### 2.1 Multi-Model Cross-Analysis

Six independent research streams were run in parallel:

| Stream | Model | Focus |
|--------|-------|-------|
| Sub-agent 1 | Claude Sonnet | obra/superpowers deep dive |
| Sub-agent 2 | Claude Sonnet | deer-flow skills/public deep dive |
| Sub-agent 3 | Claude Sonnet | claude-code non-code knowledge deep dive |
| External 1 | Grok | Cross-project synthesis (user-submitted prompt) |
| External 2 | Gemini | Cross-project synthesis (user-submitted prompt) |
| External 3 | GPT | Cross-project synthesis (user-submitted prompt) |

### 2.2 RED-GREEN Validation

Instead of designing a "perfect schema" upfront, we used the RED-GREEN approach:
1. **RED**: Force-fit `systematic-debugging` (superpowers' richest skill) into the existing Blueprint YAML schema
2. **Identify**: Every field that breaks or can't express the knowledge
3. **GREEN**: Minimal schema patches to fix each breakpoint
4. **Validate**: Re-extract with patched schema, verify zero gaps

---

## 3. Cross-Model Consensus

### 3.1 High-Confidence Agreements (all 6 streams)

1. **Trigger semantics is a first-class knowledge dimension** — Non-code skills need to tell host AIs "when to activate me." Code blueprints don't have this because they're explicitly selected by users.

2. **Negative knowledge is extremely valuable** — "What NOT to do" (NEVER/MUST NOT rules, rationalization defenses) is often more valuable than "what to do" in non-code projects.

3. **Non-code extraction is structurally easier than code extraction** — Authors already made implicit architecture explicit. Extraction is "structured extraction" not "reverse engineering."

4. **evidence_refs need a paradigm upgrade** — From `file:line` to document section-level references with role distinction (normative vs example vs rationale).

### 3.2 Key Divergences

| Dimension | Grok | Gemini | GPT | Our Decision |
|-----------|------|--------|-----|-------------|
| Taxonomy layers | 7 | 4 | 8 | **Don't create new taxonomy** — extend existing schema |
| Final product | Unified crystal | Unified + LLM adaptation | **5 crystal types** | **Unified crystal** (product constitution §1.8.5) |
| Automation estimate | 80% | ~100% | 70% | TBD (validation framework needed) |
| Unique blind spot | Community discussions | **Model adaptation** (best insight) | Runtime vs repo knowledge | Address via `resource_boundary` constraints |

### 3.3 Most Valuable Unique Insights

- **Gemini's "environment dependency collapse"**: Knowledge extracted from claude-code is tuned for Claude; giving it to Llama may cause failure. Resolution: capture as `resource_boundary` constraints, not a new schema dimension.
- **GPT's `evidence_role` distinction**: `normative` / `example` / `rationale` prevents "treating an example as a rule" — a real extraction failure mode. Adopted into schema.
- **Our sub-agent's "evolution flywheel"**: deer-flow's skill-creator embeds a create→eval→improve closed loop. None of the external AIs explored this deeply.

---

## 4. First-Principles Analysis

### 4.1 Root Cause of Schema Gaps

All 7 gaps shared **one root cause**: the schema was instantiated from finance, not abstracted from multiple domains. Field names encoded finance vocabulary (`execution_paradigm: live/backtest`, `known_use_cases.applicable_markets`).

**Design principle**: Schema defines structure, domain SOP defines vocabulary.

### 4.2 What's Genuinely New (3 things)

After stripping away "same concept, different surface form":

| Genuinely New | Why | Resolution |
|---------------|-----|-----------|
| **Trigger semantics** | Code blueprints are explicitly selected; skill blueprints need auto-routing | `applicability.activation` subfield |
| **Rationalization defense** | Code doesn't need to defend against LLM self-justification | New `constraint_kind` (deferred to constraint discussion) |
| **Evaluation contract** | Both code and non-code need this; non-code made the gap visible | Future universal addition |

### 4.3 What's NOT New (maps to existing concepts)

| Appears New | Actually Maps To |
|-------------|-----------------|
| "AI skill stages" | `stages` (phases = stages) |
| "Skill resources" | Needs `resources` field, but concept exists in product constitution §1.3 |
| "Model dependency" | `resource_boundary` constraint |
| "Skill call topology" | `relations` (with extended type enum) |
| "Behavioral contract" | `global_contracts` + `interface` |

---

## 5. Schema Changes (Implemented)

### 5.1 Summary

| # | Change | Type | File | Backward Compatible |
|---|--------|------|------|-------------------|
| 1 | `EvidenceRef` + `document_section` kind | Field + enum extension | `contracts/base.py` | Yes |
| 2 | `EvidenceRef` + `section_id` | New optional field | `contracts/base.py` | Yes |
| 3 | `EvidenceRef` + `evidence_role` | New optional field | `contracts/base.py` | Yes |
| 4 | `ActivationProfile` model | New file | `contracts/blueprint.py` | Yes (new) |
| 5 | `BlueprintResource` model | New file | `contracts/blueprint.py` | Yes (new) |
| 6 | `BlueprintRelation` + `RelationType` | New file | `contracts/blueprint.py` | Yes (new) |
| 7 | `ExecutionMode` model | New file | `contracts/blueprint.py` | Yes (new) |
| 8 | `ExtractionMethod` enum | New file | `contracts/blueprint.py` | Yes (new) |
| 9 | `ParsedBlueprint` + resources/relations/activation | Field additions | `constraint_pipeline/blueprint_loader.py` | Yes |
| 10 | `ParsedStage` + `resource_refs` | Field addition | `constraint_pipeline/blueprint_loader.py` | Yes |
| 11 | `load_blueprint()` parses new fields | Logic addition | `constraint_pipeline/blueprint_loader.py` | Yes |

### 5.2 EvidenceRef Extension (base.py)

```python
# Before
kind: Literal["file_line", "artifact_ref", "community_ref"]

# After
kind: Literal["file_line", "artifact_ref", "community_ref", "document_section"]
section_id: str | None = None       # "§Phase-1-Step-4"
evidence_role: EvidenceRole | None = None  # normative / example / rationale
```

### 5.3 New Blueprint Components (blueprint.py)

```python
class ActivationProfile(BaseModel):
    """Embedded in applicability.activation — tells host AI when to activate."""
    triggers: list[str]      # What signals should trigger
    emphasis: list[str]      # Use ESPECIALLY when...
    anti_skip: list[str]     # Don't skip because of...

class BlueprintResource(BaseModel):
    """Top-level resources field — product constitution §1.3 fulfillment."""
    id: str
    type: str                # Domain SOP defines enum values
    name: str
    path: str | None
    description: str
    used_in_stages: list[str]

RelationType = Literal[
    "alternative_to", "specializes", "generalizes",  # existing
    "depends_on", "complementary", "contains",        # new
]

class ExecutionMode(BaseModel):
    """Replaces hardcoded live/backtest with generic mode list."""
    id: str
    description: str
```

### 5.4 Blueprint YAML New Fields

```yaml
# applicability.activation (optional, for non-code blueprints)
applicability:
  activation:
    triggers: ["test failure", "production bug"]
    emphasis: ["under time pressure"]
    anti_skip: ["issue seems simple"]

# resources (top-level, optional)
resources:
  - id: root_cause_tracing
    type: technique_document
    name: Root Cause Tracing
    path: "skills/systematic-debugging/root-cause-tracing.md"
    used_in_stages: [root_cause_investigation]

# execution_paradigm (generalized)
execution_paradigm:
  modes:
    - id: mandatory_sequential
      description: "Four phases, strict order, no skipping"

# relations (extended types)
relations:
  - type: depends_on
    target: "ai-skill-bp-xxx-tdd"
  - type: contains
    target: "root-cause-tracing.md"
```

---

## 6. Experimental Blueprint

**File**: `knowledge/blueprints/_experiments/ai-skill-bp-001-systematic-debugging.yaml`

**Source**: obra/superpowers `systematic-debugging` skill (8 files)

**Extraction results**:

| Dimension | Count | Notes |
|-----------|-------|-------|
| Stages | 4 | Root Cause Investigation → Pattern Analysis → Hypothesis Testing → Implementation |
| Resources | 5 | 3 technique docs + 1 tool script + 1 code example |
| Business Decisions | 6 | process_design, escalation_threshold, quality_gate types |
| Known Use Cases | 3 | Test failure, multi-component, escalation |
| Global Contracts | 5 | Iron Law + phase ordering + single variable + architecture escalation |
| Relations | 5 | 1 depends_on + 1 complementary + 3 contains |
| Activation triggers | 6 | test failure, production bug, unexpected behavior, ... |
| Gaps | **0** | All knowledge from source project captured |

**Validation**:
- `uv run` contracts model instantiation: PASS
- `uv run` blueprint_loader parsing: PASS
- Finance blueprint backward compatibility: PASS
- `ruff check` on changed files: PASS
- `mypy` on contracts: PASS

---

## 7. Key Findings for Non-Code Projects

### 7.1 Extraction Is Easier, Not Harder

Code projects require reading tens of thousands of lines to infer architecture. Non-code skill projects have architecture explicitly written in SKILL.md — the extraction agent reads and structures, rather than reverse-engineers.

**Implication**: Extraction agent for non-code projects can be simpler and faster.

### 7.2 Three Project Types, One Schema

| Type | Entry Strategy | Extraction Difficulty | Schema Coverage |
|------|---------------|----------------------|-----------------|
| Pure skill (superpowers) | Scan `skills/` directory | Low | 100% |
| Framework skill (deer-flow) | Read framework contract first, then skills | Medium | 100% (with resources) |
| AI agent (claude-code) | Map runtime surface, then collect knowledge | High | 100% (with resources + activation) |

All three types produce blueprints with the same schema. The difference is in the **SOP entry strategy**, not the output format.

### 7.3 Unique Knowledge Dimensions of Non-Code Projects

| Dimension | Exists in Code Projects? | How Captured |
|-----------|------------------------|-------------|
| Trigger semantics | No (user selects explicitly) | `applicability.activation` |
| Rationalization defense | No (code doesn't self-rationalize) | Constraint layer (future) |
| Pressure test scenarios | No (code has unit tests) | `_extraction_notes.validation_available` |
| Skill call topology | Partially (module deps) | `relations` with extended types |
| Sub-technique documents | Partially (API docs) | `resources` with `technique_document` type |

### 7.4 What the Product Constitution Already Predicted

Product constitution §1.3 states: "Good crystal = good blueprint + good resources + good constraints."

Resources were always one of the three pillars, but the Blueprint schema never had a `resources` field. Non-code projects made this gap visible. The fix benefits code blueprints too — finance blueprints can now formally declare their API dependencies and data sources.

---

## 8. Decisions Made

### 8.1 Adopted

| Decision | Rationale |
|----------|-----------|
| **Unified blueprint** (not "code" vs "skill" types) | Projects are a spectrum; binary classification fails on deer-flow, claude-code, and all future AI projects |
| **Unified SOP** with multiple extraction strategies | Strategy is per-knowledge-source, not per-project. One pipeline, multiple strategies. |
| **`domain` = subject matter, not format** | `software_engineering` not `ai_skill`; `finance` not `code_project` |
| **`extraction_methods` as list** | Hybrid projects use multiple strategies simultaneously |
| Unified crystal (not 5 types) | Product constitution §1.8.5: "self-contained delivery" |
| Extend schema (not rebuild) | 60% reuse, 7 backward-compatible changes |
| `applicability.activation` (not top-level `trigger_semantics`) | Information flows naturally into `intent_router` during crystal compilation |
| Top-level `resources` (not stage-level) | One resource can serve multiple stages; mirrors crystal IR structure |
| `evidence_role` distinction | Prevents "treating example as rule" — real extraction failure mode |

### 8.2 Deferred

| Decision | Reason | When |
|----------|--------|------|
| `rationalization_guard` constraint kind | User requested: discuss constraints separately | Next session |
| Evaluation contract in blueprint schema | Universal need (code + non-code); needs deeper design | After SOP validation |
| Crystal compilation for non-code | Depends on constraints + SOP | After constraint discussion |
| A/B validation framework | Needs crystal first | After crystal compilation |

### 8.3 Rejected

| Proposal | Source | Reason |
|----------|-------|--------|
| "Code blueprint" vs "skill blueprint" dichotomy | Initial framing | Projects are a spectrum; one blueprint type with optional fields |
| Separate "ai-skill extraction SOP" | Initial framing | One SOP with strategy routing, not two SOPs |
| `domain: ai_skill` | Initial experiment | `ai_skill` is a format, not a domain; use `software_engineering` |
| 7-layer taxonomy | Grok | Over-engineering; existing schema handles it |
| 4-layer taxonomy | Gemini | Too coarse; loses trigger semantics |
| 8-category taxonomy | GPT | Redundant with extended schema |
| 5 crystal types | GPT | Violates product constitution §1.8.5 |
| `Tested_Target_LLM_Environment` | Gemini | Model dependency = `resource_boundary` constraint |
| New top-level `trigger_semantics` | Initial proposal | Absorbed into `applicability.activation` |

---

## 9. Architectural Correction: Unified Blueprint

**Post-experiment insight** (CEO + first-principles validation):

The original framing of "code blueprint vs skill blueprint" is wrong. Projects exist on a spectrum:

```
Pure code ←——————————————————————————→ Pure skill
 zvt    zipline   deer-flow   claude-code   superpowers
```

Most future AI projects will be in the middle. The correct model:

- **ONE blueprint type** — not "code blueprint" and "skill blueprint"
- **ONE SOP** — not two separate SOPs
- **Multiple extraction strategies** — selected per knowledge source, not per project
- **`domain`** = subject matter (finance, software_engineering), NOT project format

Corrections applied:
- Experimental blueprint: `domain: ai_skill` → `domain: software_engineering`
- Experimental blueprint: `extraction_method` (single) → `extraction_methods` (list)
- ExtractionMethod enum: added `config_parsing` for hooks/settings knowledge sources
- Next steps: "write ai-skill SOP" → "upgrade existing SOP with structural extraction strategy"

## 10. Next Steps

### 10.1 Immediate (Blueprint Layer)

1. **Upgrade existing blueprint extraction SOP** — Add structural extraction as a strategy alongside code reverse engineering. Stage 0 should detect knowledge source types (SKILL.md, CLAUDE.md, hooks.json) and route to appropriate strategies. One SOP, one pipeline, multiple strategies.

2. **Manual extraction of 2-3 more skills** — Extract superpowers' `test-driven-development` and `brainstorming` using the upgraded SOP, validating the methodology.

3. **Upgrade extraction agent** — Add structural extraction mode to existing blueprint pipeline. Stage 0 knowledge source detection → strategy routing.

### 10.2 Follow-Up (Constraint Layer — Separate Discussion)

4. **Design `rationalization_guard` constraint kind** — Unique to document-derived knowledge.
5. **Upgrade constraint SOP** — Evidence refs now support document sections; constraint extraction should handle both code and document sources.

### 10.3 Later (Crystal Layer)

6. **Crystal compilation for mixed-source blueprints** — SOP template already has `<!-- DOMAIN: -->` injection points.
7. **A/B validation framework** — GPT's three-condition comparison: baseline vs +crystal vs +full source.

---

## 11. Files Changed

| File | Change |
|------|--------|
| `packages/contracts/doramagic_contracts/base.py` | EvidenceRef: +document_section kind, +section_id, +evidence_role |
| `packages/contracts/doramagic_contracts/blueprint.py` | **NEW**: ActivationProfile, BlueprintResource, BlueprintRelation, ExecutionMode, ExtractionMethod |
| `packages/contracts/doramagic_contracts/__init__.py` | Added blueprint module export |
| `packages/constraint_pipeline/.../blueprint_loader.py` | ParsedBlueprint: +resources, +relations, +activation; ParsedStage: +resource_refs; new ParsedResource, ParsedRelation dataclasses |
| `knowledge/blueprints/_experiments/ai-skill-bp-001-systematic-debugging.yaml` | Experimental blueprint using new schema |

---

## Appendix A: External AI Prompt

The following prompt was sent to Grok, Gemini, and GPT for independent analysis:

<details>
<summary>Click to expand full prompt</summary>

```
你是一位 AI 知识工程专家。我正在设计一个系统，从 GitHub 开源项目中系统性提取结构化知识，
编译成"种子晶体"（seed crystal）供其他 AI 消费。

目前我的提取体系只能处理**代码项目**（从源码逆向提取架构蓝图 + 约束），但越来越多的高价值
AI 项目主体不是代码，而是 prompt、skill 模板、认知框架、agent 行为规范等**非代码知识资产**。

请你基于以下三个代表性项目，深入分析并回答三个核心问题：

### 三个实例项目
1. 纯 Skill 项目：https://github.com/obra/superpowers
2. AI 框架的 Skill 层：https://github.com/bytedance/deer-flow/tree/main/skills/public
3. AI Agent 项目：https://github.com/anthropics/claude-code

### 核心问题
Q1：非代码类知识应该提取哪些？
Q2：非代码类知识应该怎么提取是最佳工程实践？
Q3：非代码类知识应该如何验证？

[Full prompt details omitted for brevity — see conversation history]
```

</details>

## Appendix B: Sub-Agent Research Summary

### B.1 obra/superpowers (151K stars)

- 14 skills, pure .md workflow protocols
- "Rationalization defense" is a unique knowledge dimension — explicit tables of excuses LLMs use to skip steps, with rebuttals
- Pressure test scenarios built into CREATION-LOG.md
- Skills have "rigid" (TDD, debugging) vs "flexible" (brainstorming) distinction
- Skill call topology: brainstorming → writing-plans → subagent-driven-development
- RED-GREEN-REFACTOR applied to documentation writing itself

### B.2 bytedance/deer-flow (21 public skills)

- `description` is the ONLY routing signal — framework injects name+description into system prompt
- skill-creator meta-skill embeds create→eval→improve evolution flywheel
- Max 3 concurrent `task` calls (hard limit, silently dropped beyond)
- Skills range from 1KB (web-design-guidelines) to 33KB (skill-creator, consulting-analysis)
- consulting-analysis: 20+ analysis frameworks with selection logic — highest domain knowledge density

### B.3 anthropics/claude-code (114K stars)

- Knowledge distributed across CLAUDE.md / SKILL.md / agents / hooks / settings / plugins
- Advisory layer (CLAUDE.md) vs enforcement layer (hooks) — dual-track constraint system
- Progressive trust model: tool-level → path-level → pattern-level → session-level permissions
- Semantic routing: agent `description` field is the routing key
- 13 official plugins each containing skills + agents + hooks as knowledge bundles

---

*Research conducted: 2026-04-14*
*Powered by Doramagic.ai*
