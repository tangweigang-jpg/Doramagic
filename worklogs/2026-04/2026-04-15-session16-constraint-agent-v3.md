# Session 16 — Constraint Extraction Agent v3 Design & Implementation

> Date: 2026-04-15 | Duration: ~4 hours | Model: Claude Opus 4.6

## Summary

Designed and implemented the constraint extraction agent v3 upgrade (SOP v2.3 alignment). Approach: deep research phase (4 parallel subagents analyzing 27 files from the blueprint extraction 48-hour sprint), then incremental upgrade on the well-built v2 codebase rather than building from scratch.

## Methodology

### Phase 1: Deep Research (4 parallel subagents)

| Agent | Focus | Key Output |
|-------|-------|------------|
| #1 | Constraint extraction current state | SOP v2.3 pipeline + 3,655 constraints + 79 drafts |
| #2 | Blueprint research & design docs (11 files) | Transferable patterns vs blueprint-specific |
| #3 | Blueprint worklogs (sessions 5e-15) | v5.1→v7 evolution narrative |
| #4 | Blueprint agent code architecture | SOPExecutor genericity confirmed |

### Phase 2: Non-Code Deep Dive (2 subagents)

Discovered that FinRL (bp-061) did NOT validate the document extraction path (pure code project). The document extraction pipeline (worker_structural, Step 2a-s) was designed and built but never tested on a real mixed project. This directly impacts the constraint agent upgrade strategy.

### Phase 3: v2 Codebase Discovery

Critical finding: v2 is **far more complete** than initially assumed.

| File | Lines | Status |
|------|-------|--------|
| `constraint_phases_v2.py` | 2,353 | COMPLETE — N+14 phases, parallel extract group |
| `constraint_enrich.py` | 724 | COMPLETE — 10 patches (P1-P10) |
| `constraint_prompts_v2.py` | 1,130 | COMPLETE — 5 system prompts |
| `constraint_synthesis.py` | 363 | COMPLETE — kind rebalance |
| `constraint_resources.py` | 559 | COMPLETE — dependency scan + LLM resource extraction |
| `constraint_schemas_v2.py` | 483 | COMPLETE — MiniMax coercions, DeriveExtractionResult, MissingGapPair |

This changed the approach from "build 5 new files (~2,550 lines)" to "incremental upgrade on v2 (+1,100 lines)".

### Phase 4: Implementation

Plan Mode → approved → 9 tasks executed.

## Achievements

### Schema Layer
- `constraint_schema/types.py`: +`RATIONALIZATION_GUARD` enum, +`DOCUMENT_EXTRACTION` enum, +`GuardPattern` model (excuse/rebuttal/red_flags/violation_detector), +`Constraint.guard_pattern` field

### Structured Output
- `constraint_schemas_v2.py`: +`guard_pattern` on `RawConstraint`, +`coerce_minimax_quirks` model_validator (field aliases, bool string coercion, float string, enum fuzzy match), +top-level `coerce_top_level` (bare list → dict, coverage_report optional)
- All Literal types updated: `_CONSTRAINT_KIND` 5→6, `_SOURCE_TYPE` 6→7, `_VALID_CONSTRAINT_KINDS` 5→6

### New Phases (constraint_phases_v3.py, ~310 lines)
Extends v2 by inserting 3 phases into the existing DAG:

| Phase | SOP Step | Type | Parallel | Blocking |
|-------|----------|------|----------|----------|
| `con_extract_doc` | 2.1-s | Agentic | extract | No |
| `con_extract_rationalization` | 2.6 | Agentic | extract | No |
| `con_evaluate` | New | Agentic | — | Yes |

Architecture: `build_constraint_phases_v3()` calls `build_constraint_phases_v2()`, then inserts new phases at correct positions. `con_constraint_synthesis` gets new dependency on `con_evaluate`.

### New Enrichment Patches (P11-P15)
| Patch | Function | Purpose |
|-------|----------|---------|
| P11 | `_patch_when_perspective` | Runtime → coding-time perspective fix |
| P12 | `_patch_consequence_quality` | Tag <20 char / enum-only / vague consequences |
| P13 | `_patch_absolute_words` | "all X" → "each X" replacement |
| P14 | `_patch_hardcoded_constants` | Tag `row[XXX_IDX]` patterns |
| P15 | `_patch_hash_compute` | Auto-compute sha256 hash (MUST run last) |

### New Prompts (3 system prompts added to constraint_prompts_v2.py)
- `CON_DOC_EXTRACT_SYSTEM` — 5 document feature patterns, confidence rules, evidence format `file:§section`
- `CON_RATIONALIZATION_SYSTEM` — guard_pattern schema, scan patterns (Common Rationalizations, Red Flags, ❌ behaviors, DO NOT comments)
- `CON_EVALUATOR_SYSTEM` — Sprint Contract with 4 verification contracts (evidence validity, kind correctness, severity calibration, triad completeness), PASS/FIXABLE/NEEDS_REWORK scoring

### Orchestrator Integration
- `orchestrator.py`: +`constraint_version == "v3"` branch
- `job_queue.py`: `BatchConfig.constraint_version` default changed to `"v3"`
- `pyproject.toml`: per-file-ignores for pre-existing E501/B905

## Commit

```
e9261c6 feat(constraint-agent): v3 upgrade — doc extraction, rationalization guard, evaluator
  8 files changed, 1,123 insertions(+), 29 deletions(-)
```

## Key Decisions

### D1: Incremental upgrade over full rewrite
v2 had 5,600+ lines of production-quality code. Rewriting would lose battle-tested logic (BD chunking, stage_id whitelisting, audit_checklist_summary format handling). Instead: v3 wraps v2 and adds 3 phases.

### D2: Agentic phases for doc/rationalization, not Python+Instructor
Document extraction and rationalization guard need to READ files (SKILL.md sections, CONTRIBUTING.md, code comments). This requires tool-use loop (read_file, grep_codebase), not a single structured call. Blueprint's `worker_structural` pattern confirmed this approach.

### D3: Evaluator as agentic phase, not Python handler
The evaluator must independently read source code to verify evidence — it can't just parse JSON. Sprint Contract pattern from blueprint `bp_evaluate` requires read_file + grep_codebase tools.

### D4: Graceful skip pattern for document phases
Both `con_extract_doc` and `con_extract_rationalization` detect knowledge source type in initial_message_builder. No document sources → instruct agent to write empty JSON immediately (same pattern as `worker_structural`). This ensures the phase always produces its required artifact.

## Transferable Patterns Applied (from blueprint 48-hour sprint)

| Pattern | Source | Application |
|---------|--------|-------------|
| MiniMax coerce_minimax_quirks | schemas_v5.py BusinessDecision | RawConstraint model_validator |
| Example instance > JSON Schema (L2) | Session 6 L2 fix | Already in v2, confirmed sufficient |
| Graceful skip (empty JSON) | worker_structural | con_extract_doc, con_extract_rationalization |
| Sprint Contract evaluator | bp_evaluate | con_evaluate with 4 constraint-specific contracts |
| Enrichment patch pattern | blueprint_enrich.py P0-P17 | P11-P15 in constraint_enrich.py |
| Per-file-ignores for prompt files | blueprint_phases.py E501 | constraint_prompts_v2.py E501 |

## Patterns NOT Applied (blueprint-specific)

| Pattern | Why Not |
|---------|---------|
| BD classification (T/B/BA/DK/RC/M) | Constraints have their own 6-kind taxonomy |
| 4-round adversarial extraction (R1-R4) | Constraint extraction is stage×kind matrix, not adversarial funnel |
| Subdomain fingerprinting | Constraints bind to blueprints, not independently fingerprinted |
| P15 deterministic missing gap | Depends on worker_audit structure, no constraint analog |
| ConvergenceDetector | Defined in agent_loop.py but not yet wired — deferred |

## Test Results

- `constraint_schema`: **24 passed** (GuardPattern + enum additions validated)
- `constraint_pipeline`: **20 passed** (no regressions)
- New files lint: **0 errors**
- Pre-commit: ruff + ruff-format + mypy all **PASSED**

## Known Remaining Issues

| Issue | Priority | Notes |
|-------|----------|-------|
| Document extraction path untested on real project | High | Blocked by blueprint side (needs deer-flow or similar) |
| rationalization_guard extraction untested | High | No project with SKILL.md + anti-rationalization content yet |
| con_evaluate untested with real LLM | Medium | Prompt written, needs production validation |
| Cross-blueprint dedup not implemented | Medium | con_dedup only does within-run dedup, not against finance.jsonl pool |
| con_merge doesn't read new v3 artifacts | High | Needs update to read ct_doc_constraints.json + ct_rationalization_constraints.json |
| sop_version "2.2" hardcoded in con_enrich_handler | Low | Updated default in function, but handler call site may still pass "2.2" |
| QG-02 threshold still >=5 kinds | Low | Should be >=6 when rationalization_guard is actively extracted |

## Next Steps

1. **Update con_merge handler** to read v3 extraction artifacts (ct_doc_constraints.json, ct_rationalization_constraints.json)
2. **Test on bp-009** with real LLM — validate full v3 pipeline end-to-end
3. **Test on mixed project** (deer-flow) when blueprint document extraction is validated
4. **Wire ConvergenceDetector** into extract phases for token savings
5. **Cross-blueprint dedup** against existing finance.jsonl pool in ct_finalize
