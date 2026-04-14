# Blueprint Extraction Agent — Architecture & Evolution

> **Date**: 2026-04-14
> **Author**: Claude Sonnet 4.6
> **Status**: Reference document
> **Audience**: Engineers improving the constraint extraction agent

---

## 1. Architecture Overview

### 1.1 Pipeline Phases (v6: 20 phases)

The v6 pipeline is organized into 7 logical groups:

| Group | Phases | Type | Blocking |
|-------|--------|------|---------|
| Pre-processing | fingerprint, clone, index, sources, manifest | Python | Yes |
| Parallel workers | arch, workflow, math, deep, docs, resource | Agentic | No (concurrent) |
| Parallel auditors | verify, audit | Agentic | audit=True (v6) |
| Synthesis | bp_synthesis_v5 | Python (Instructor) | Yes |
| Evaluation | bp_evaluate | Agentic | Yes |
| Post-processing | bp_uc_extract, bp_coverage_gap | Python | Yes (blocking=True) |
| Assembly + Enrich + QGate + Finalize | bp_assemble, bp_enrich, bp_quality_gate, bp_save, bp_manifest | Python | Yes |

Key design: the 6 parallel worker phases run concurrently via `asyncio.Semaphore`-bounded `BatchOrchestrator`, each producing a JSON/Markdown artifact (`worker_arch.json`, `worker_resource.json`, `worker_audit.md`, etc.) that is assembled by the synthesis phase.

### 1.2 Parallel Worker Orchestration

`BatchOrchestrator` (`packages/extraction_agent/.../batch/orchestrator.py`) drives repo-level parallelism:

- Jobs sorted by `priority` (ascending), then executed with bounded concurrency (`BatchConfig.concurrency`)
- Per-job failures are isolated: caught, logged, converted to `RepoResult(status="failed")` — other jobs continue
- Within each job, the `ExtractionAgent` runs the 20-phase pipeline sequentially, but the 8 worker/auditor phases run as concurrent async tasks

The orchestrator also wires tooling:
1. `ToolRegistry` per job (filesystem tools + artifact tools + index tools)
2. `StructuralIndex` built once per repo and injected into `state.extra`
3. Knowledge source detection (v7): `detect_knowledge_sources()` result stored in `state.extra["knowledge_sources"]`

### 1.3 Instructor Structured Output with L1→L2→L3 Fallback Cascade

The synthesis phase (`bp_synthesis_v5`) does not call the LLM for free-form output. It uses [Instructor](https://python.useinstructor.com/) to enforce Pydantic schema compliance, with a three-level fallback:

- **L1 (strict mode)**: Instructor with `mode=TOOL` — LLM must return schema-valid JSON via tool call
- **L2 (freeform + coerce)**: Instructor with `mode=JSON` — LLM returns JSON, Pydantic validators coerce edge cases
- **L3 (RawFallback)**: If L1+L2 both fail, return a minimal `RawFallback` object that lets the pipeline continue rather than crash

The 3-step synthesis within the phase:
1. **Step 1A/1B** (split call): Extract BD list + classify types — split into arch BDs and workflow/math BDs to halve output size and reduce truncation risk
2. **Step 2**: Enhance rationale (≥60 chars, WHY + BOUNDARY) using worker_docs context
3. **Step 3**: Interactions synthesis — uses `worker_audit` (now blocking=True in v6) for deterministic missing-gap generation

### 1.4 Tool-Use Agentic Loop

`ExtractionAgent` (`packages/extraction_agent/.../core/agent_loop.py`) wraps the LLM in a tool-use loop supporting two API formats:

- **Anthropic format** (default): Anthropic Messages API — used by MiniMax, Claude, Anthropic-compatible endpoints
- **OpenAI format**: Chat Completions API via `httpx` — used by GLM-5, GPT-4o, DeepSeek

The rest of the pipeline is format-agnostic. `ExtractionAgent` exposes a uniform `run_phase()` interface that drives the agentic loop: the LLM calls filesystem/artifact tools, reads source files, writes artifacts, and terminates when it produces a `stop` event. Circuit breaker and context manager sit around the loop for safety.

---

## 2. Key Technical Decisions

### 2.1 Why Instructor + Pydantic over Raw JSON Parsing

Raw JSON parsing from LLM outputs fails in two ways:
- **Structural failure**: LLM produces malformed JSON (truncated, escaped incorrectly)
- **Semantic failure**: LLM produces valid JSON but with wrong field types/values

Instructor wraps the retry logic and schema enforcement. Pydantic provides the schema contract. The combination ensures that synthesis output is always a typed Python object, not a dict that might contain surprises downstream.

The critical insight: **validation happens at the boundary, not inside business logic**. Phases that consume synthesis output (enrich, quality gate, assembly) receive well-typed objects and never do defensive `isinstance()` checks.

### 2.2 Pre-Validator Coercion Pattern (LLM Output Format Mismatches)

MiniMax Step 3 produces `type_summary` as string descriptions instead of integer counts:

```python
# MiniMax output (wrong):
{"type_summary": {"amplification": "BD-103 double target..."}}

# Expected:
{"type_summary": {"B": 5, "BA": 3}}
```

The `BDExtractionResult.coerce_type_summary_values` `@model_validator(mode="before")` intercepts this before Pydantic rejects the input. Key principle: **use `fallback=1`** (not digit extraction) because string values like `"BD-103 double target..."` would yield `103` if you extract the first number, which is wrong.

Similarly, `coerce_missing_gaps_from_ids` handles MiniMax L2's habit of returning `missing_gaps` as string ID lists instead of full objects — it resolves them from the `decisions` list.

**Rule**: Every known LLM quirk that causes Pydantic validation errors gets a named `@model_validator(mode="before")` with a docstring explaining exactly which model/step triggers it. This makes the coercions self-documenting and auditable.

### 2.3 Deterministic Enrichment (18 Patches, Zero LLM Dependency)

`blueprint_enrich.py` applies 18 deterministic patches (P0–P14 + P5.5 + v7 additions) after synthesis, with zero LLM calls. Each patch is a pure Python function that takes the blueprint dict, mutates it in-place, and returns a change count.

Why deterministic enrichment beats prompt engineering for quality:

| Approach | Repeatability | Debuggability | Cost |
|----------|--------------|---------------|------|
| Prompt engineering ("always include commit hash") | Low — LLM ignores it 5-10% of the time | Hard — which run failed? | Every token |
| Deterministic patch (P1: inject commit_hash) | 100% | Trivial — read the patch | Zero tokens |

Notable patches:
- **P0**: Inject `blueprint_id` if LLM omitted it (LLMs sometimes skip this)
- **P1**: Inject `commit_hash` from `state.commit_hash` (LLM can't know this)
- **P3**: Replace `business_decisions` with the authoritative `BDExtractionResult` from synthesis
- **P5.5** (v6): Deterministic evidence verification — file exists, line valid, function present; auto-fix drifted refs
- **P6**: Tag BDs with vague rationale (heuristic word list) — flags for human review
- **P7**: Deduplicate stage IDs/orders; repair BD.stage references via `STAGE_MAPPING`
- **P14** (v6): Inject `worker_resource.json` into `replaceable_points` per stage

### 2.4 Evidence Verification via AST

P5.5 (`evidence_verify`) goes beyond format normalization — it performs actual verification:

1. **File exists**: Check `evidence_ref.file` resolves to a real path in the cloned repo
2. **Line valid**: Line number within bounds of the file
3. **Function present**: AST parse the file, check that the referenced function name exists near the cited line

When a reference fails verification, the patch attempts auto-fix (e.g., stale line numbers after a refactor). This prevents "ghost evidence" — citations that look real but point nowhere.

### 2.5 Multi-Type BD Annotation (Keyword-Based P16 / RC Misclassification Fix)

P4 (`bd_type_enum_fix`) includes a secondary RC-misclassification check (v7): any BD typed `RC` (regulatory constraint) that lacks regulatory keywords in its content or rationale is automatically downgraded to `T` (technical choice).

This addresses a systematic LLM bias: models frequently tag "the code must do X" as `RC` because the phrasing sounds mandatory, even when X is a technical design decision with no regulatory basis.

The keyword set (`regulation`, `mandatory`, `compliance`, `t+1`, `sec`, `finra`, `basel`, `mifid`, etc.) is conservative — only unambiguously regulatory terms — to avoid false positives.

### 2.6 Knowledge Source Detection for Unified Pipeline

`detect_knowledge_sources()` (`tools/knowledge_source_detector.py`) scans the cloned repo and returns a typed list: `["code", "document", "config"]`. This runs in the pre-processing phase and stores results in `state.extra["knowledge_sources"]`.

The detector classification logic:
- **code**: ≥3 files with extensions `.py/.ts/.js/.go/.rs/.java/.kt/.scala`
- **document**: Any of `SKILL.md`, `CLAUDE.md`, `AGENTS.md`, `Gemini.md`, `.cursorrules`, or files under `skills/` or `.claude/`
- **config**: `hooks.json`, `settings.json`, `manifest.json`, or YAML/TOML files (excluding build configs like `pyproject.toml`)

The detection result drives strategy routing: code-only projects use reverse engineering (workers arch/workflow/math); document-only projects use structural extraction (worker_structural); hybrid projects run both in parallel and merge with conflict resolution.

---

## 3. Evolution Path (v1 to v7)

### v1–v3: Legacy Single-Shot Pipeline

Single LLM call per blueprint. The model received raw source code context and was expected to produce a complete YAML in one shot. Problems:

- Context window overflow on large repos
- Inconsistent schema compliance (fields missing, types wrong)
- No evidence verification
- Business decisions mixed with architecture in free text

### v4: Parallel Workers

Decomposed extraction into specialized worker phases (arch, workflow, math, docs) running concurrently. Each worker focused on one slice of the codebase and produced a narrow artifact. Synthesis merged worker outputs.

Key improvement: LLM context per call dropped from "entire repo" to "focused slice." Quality improved significantly. Still no structured output — synthesis still produced free-form JSON that needed post-hoc parsing.

### v5: Instructor Structured Output + 3-Step Synthesis

Replaced free-form synthesis with Instructor-driven 3-step pipeline (Extract → Enhance → Interactions). Introduced:

- `BDExtractionResult` Pydantic model as the synthesis contract
- L1→L2→L3 fallback cascade
- Pre-validator coercions for MiniMax quirks
- Split Step 1 into 1A/1B (arch vs workflow) to reduce output size per call

This was the most impactful single change. Validation failure rate dropped from ~30% to ~5%.

### v6: Independent Evaluator + Resource Worker + Quality Gates

Added:
- **worker_resource**: Dedicated resource extraction worker producing `worker_resource.json` (APIs, data sources, tools) → injected into `replaceable_points` via P14
- **bp_evaluate**: Independent evaluator phase that verifies BD claims against source evidence (Sprint-contract verification) — runs after synthesis, before quality gate
- **worker_audit blocking=True**: Audit phase now blocks synthesis Step 3, providing deterministic missing-gap generation instead of LLM guessing
- **Quality gate (BQ-01~09)**: 9 blocking checks with `fix_hints` in failure messages; `strict=True` by default

Result: 9/9 PASS rate on finance blueprints (bp-060 AMLSim), validated in session 14.

### v7: Document Knowledge Source Support + Schema Extensions

In progress. Key additions:
- **worker_structural**: New worker for document-extracted architecture (SKILL.md, CLAUDE.md, etc.)
- **Knowledge source detection**: Pre-processing stage 0a detects source types, routes to appropriate strategies
- **Schema extensions**: `applicability.activation`, `resources`, `extraction_methods`, `evidence_role` in `EvidenceRef`
- **RC misclassification fix**: P4 secondary keyword check
- **Unified pipeline**: One SOP, one pipeline, multiple strategies (not separate code vs skill pipelines)

---

## 4. Lessons Learned (for Constraint Agent)

### 4.1 MiniMax L2 Compliance: The Coercion Pattern

MiniMax in L2 mode (Instructor JSON mode) produces schema-adjacent-but-wrong output. The two most common failures:

1. `type_summary` values are strings not ints — coerce with `fallback=1`, not digit extraction
2. `missing_gaps` is a list of string IDs, not objects — resolve from `decisions` list

**Lesson for constraint agent**: When designing constraint extraction schemas, add `@model_validator(mode="before")` for every field that MiniMax might misformat. Test with MiniMax L2 explicitly before declaring the schema done.

### 4.2 Enrichment > Prompt Engineering for Deterministic Quality

Every time you find yourself adding "always include X in your response," write a deterministic patch instead. LLMs have ~5-10% non-compliance rates on "always" instructions. A Python patch has 0%.

**Lesson for constraint agent**: Identify which constraint fields can be derived deterministically (blueprint_id binding, stage_id validation, evidence format normalization) and implement them as post-processing patches. Do not rely on the LLM to get these right every time.

### 4.3 File Path Resolution for Evidence

Constraint evidence (`evidence_refs`) cites file paths from the source repo. These paths are relative to the repo root at extraction time. Problems arise when:

- The evidence is committed to the constraint store but the blueprint is updated from a newer commit
- The file moved or was renamed
- The LLM invents a plausible-sounding path that doesn't exist

**Lesson for constraint agent**: Implement evidence path verification (analogous to P5.5) before committing constraints. At minimum: check file exists, line number within bounds. Ideally: check the cited function name is present in that file.

### 4.4 Audit Summary Must Match Actual Data

A systemic failure mode: the LLM generates an `audit_checklist_summary` that sounds good but does not reflect the actual content of `business_decisions`. P11 (`audit_checklist`) auto-generates the summary from actual data if the LLM-provided one is absent or inconsistent.

**Lesson for constraint agent**: The `_enrich_meta` field in blueprints tracks enrichment decisions. Design an equivalent metadata layer for constraints so you can audit which fields came from LLM vs deterministic enrichment.

### 4.5 `skip_constraint` Default Must Be Consistent Across Entry Points

A bug found in session 13: `skip_constraint` defaulted to `True` in the CLI entry point but `False` in the batch orchestrator, causing constraint phases to silently skip in some invocations. This took multiple sessions to diagnose because the symptom (missing constraint output) looked identical to a constraint extraction failure.

**Lesson for constraint agent**: Define defaults once, in `BatchConfig` or the equivalent config dataclass. Never re-specify defaults in individual entry points.

### 4.6 Knowledge Source Detector Must Be Wired Into Orchestrator

The detector was implemented before it was wired into the orchestrator pipeline. During the intervening period, blueprint extractions ran without knowledge source routing, producing lower-quality results for hybrid repos.

**Lesson for constraint agent**: Wire routing logic into the pipeline before running batch extractions. A detector that isn't connected to the router is dead code.

---

## 5. Recommended Improvements for Constraint Agent

Based on blueprint agent experience, these are the highest-ROI changes:

### 5.1 Structured Output with Instructor

Current constraint extraction uses raw JSON parsing. Replace with Instructor + a `ConstraintExtractionResult` Pydantic model. This will:

- Eliminate ~80% of validation errors from LLM output
- Make the schema contract explicit and testable
- Enable the L1→L2→L3 fallback cascade

Suggested schema structure:
```
ConstraintExtractionResult
  constraints: list[ExtractedConstraint]
  coverage_summary: dict[str, int]  # kind → count
  missing_coverage: list[str]       # constraint_kinds not yet covered
```

### 5.2 Pre-Validator Coercion for MiniMax Quirks

After implementing Instructor, run a test batch with MiniMax and collect all validation failures. For each failure, write a named `@model_validator(mode="before")` with a docstring citing which model/step triggers it. Target: zero uncaught MiniMax-specific failures.

### 5.3 Deterministic Post-Processing Patches

Identify fields in the constraint schema that can be set deterministically:

| Field | Deterministic Source |
|-------|---------------------|
| `blueprint_ids` | State's active blueprint ID |
| `domain` | Derived from blueprint domain |
| `sop_version` | Forced at extraction time |
| `evidence_format` | Normalized to `file:line(fn)` format |
| `stage_ids` | Validated against blueprint's legal stage set |

Implement these as numbered patches (`C0`, `C1`, ...) following the same pattern as `blueprint_enrich.py`. Zero LLM calls in the patch module.

### 5.4 Quality Gate Framework

Implement constraint-specific quality gates (analogous to BQ-01~09):

Suggested gates:
- **CQ-01**: Minimum constraint count per blueprint (e.g., ≥10)
- **CQ-02**: Fatal constraints present (at least 1 `severity=fatal`)
- **CQ-03**: Evidence coverage ratio ≥ 60% (constraints with valid evidence_refs)
- **CQ-04**: No duplicate constraint IDs
- **CQ-05**: `stage_ids` all resolve to valid stages in the target blueprint
- **CQ-06**: `blueprint_ids` binding consistent (no constraint pointing to non-existent blueprints)

Each gate should have a `fix_hint` message explaining what to do when it fails.

### 5.5 Knowledge Source Routing

When extracting constraints from a repo that contains both code and document sources (e.g., a finance library with a `CLAUDE.md` configuration guide), the constraint agent should:

1. Extract code-derived constraints via code analysis
2. Extract document-derived constraints via structural extraction
3. Merge with conflict resolution (blueprint-specific > generic, must > should, severity high > low)

The `detect_knowledge_sources()` function is already implemented and tested. Wire it into the constraint pipeline's pre-processing stage.

### 5.6 Split Extraction Calls for Large Repos

The blueprint agent learned (v5) that splitting a single large extraction call into 1A (arch) + 1B (workflow/math) halved validation errors and truncation risk. Apply the same principle to constraint extraction:

- **Call A**: Fatal and high-severity constraints (domain_rule, architecture_guardrail)
- **Call B**: Medium/low constraints (operational_lesson, resource_boundary, claim_boundary)

Each call produces ~30-40 constraints instead of ~80, reducing truncation and improving schema compliance.

---

*Reference for: constraint extraction agent improvement, SOP v3.x upgrade, constraint quality gate design.*
