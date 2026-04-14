# Session 15 — Non-Code Knowledge Extraction + Blueprint Agent Upgrade

> Date: 2026-04-14 | Duration: ~8 hours | Model: Claude Opus 4.6

## Summary

From research to production: designed, implemented, and validated unified blueprint extraction supporting both code and document knowledge sources. Completed with FinRL (finance-bp-061) end-to-end extraction verification.

## Achievements

### Research Phase
- 6-stream cross-analysis: 3 Claude sub-agents + Grok/Gemini/GPT on obra/superpowers, bytedance/deer-flow, anthropics/claude-code
- Key decision: **unified blueprint** (no code/skill dichotomy) — projects are a spectrum, extraction strategy is per-knowledge-source
- Research document: `docs/research/2026-04-14-non-code-knowledge-extraction-research.md`

### Schema Layer
- `contracts/base.py`: EvidenceRef +document_section, +section_id, +evidence_role (normative/example/rationale/anti_pattern)
- `contracts/blueprint.py`: NEW — ActivationProfile, BlueprintResource, BlueprintRelation, ExecutionMode, ExtractionMethod
- `constraint_pipeline/blueprint_loader.py`: +ParsedResource, +ParsedRelation, +activation

### SOP Layer
- Blueprint extraction SOP v3.6: +Step 0 knowledge source detection, +Step 2a-s structural extraction, +Step 2b document verification, +conflict matrix, +overclaim detection
- Constraint collection SOP v2.3: +Step 2.1-s document constraint extraction, +Step 2.6 rationalization_guard with guard_pattern, +corroboration boost, +overclaim detection
- Three-model review on both SOPs → 5 critical fixes applied

### Agent Layer (9 commits)
| Commit | Change |
|--------|--------|
| `6171050` | Unified blueprint schema + document extraction pipeline |
| `d1715b0` | bp_finalize path bug + audit fabrication + schema compliance |
| `00b82ee` | P5 evidence path + P12 relation discovery + P16 multi-type boost |
| `ef01598` | skip_constraint=True default |
| `2fc3777` | 3 MiniMax L2 schema coercions (type_summary, design_decisions, global_contracts) |
| `4e95b1a` | FinRL bp-061 v1 blueprint |
| `cf3743a` | P11 audit counts + P4 RC fix + P5 fn_name + P12 English + P14 resources |
| `17523d1` | 5 Codex review fixes (detector wiring, prompt types, defaults) |
| `5e2818c` | P14 dependencies dict→list crash |

### Extraction Verification (FinRL bp-061)

| Metric | v1 (first) | v2 (final) |
|--------|-----------|-----------|
| Status | completed | completed |
| L2 success | 4/6 | **6/6** |
| BDs | 138 | 151 |
| Compound-type | 56.0% | **61.7%** |
| Resources | 6 | **32** |
| RC non-missing | 11 | **0** (auto-corrected) |
| Audit | fabricated | **real (universal + subdomain separated)** |
| Missing gaps | 20 | **27** |

## New Files Created
- `tools/knowledge_source_detector.py` — Step 0 knowledge source type detection
- `sop/prompts_v7.py` — WORKER_STRUCTURAL_SYSTEM prompt
- `contracts/blueprint.py` — Blueprint schema components
- `knowledge/blueprints/_experiments/swe-bp-001` — superpowers PoC blueprint
- `knowledge/sources/finance/finance-bp-061--FinRL/` — v1 + v2 blueprints
- `docs/research/2026-04-14-non-code-knowledge-extraction-research.md`

## Key Lessons

### L1: Unified blueprint is correct
Projects are a spectrum (pure code ↔ pure skill). Binary classification fails on deer-flow, claude-code. One blueprint type, one SOP, multiple extraction strategies per knowledge source.

### L2: Pre-validator coercion > prompt engineering
MiniMax produces structurally correct data in wrong types. Adding `mode="before"` Pydantic validators to coerce types (dict→string, string→int, string→dict) is more reliable than prompt instructions. Improved L2 from 4/6 to 6/6.

### L3: Deterministic enrichment is the quality backbone
18 Python patches (P0-P17b) provide predictable quality improvements without LLM dependency. P16 multi-type keyword boost (11%→62%), P12 relation discovery, P14 resource injection — all deterministic, all reproducible.

### L4: Codex code review catches wiring bugs
knowledge_source_detector was created but never called. Codex caught it. Always run code review on integration, not just unit logic.

### L5: Don't delete versions
Keep blueprint.v1.yaml, v2.yaml etc. for comparison. OutputManager versioning already supports this.

### L6: worker_resource output format varies
dependencies can be dict ({"core": [...], "optional": [...]}) or list. Always handle both.

## Known Remaining Issues

| Issue | Priority | Notes |
|-------|----------|-------|
| Step 3 L2: still 1 validation error (missing_gaps_consistency) | Low | Workaround: falls back gracefully when it fails |
| P7 stage_id: ~20 BDs with unresolvable stages | Medium | Synthesis produces stage names not in assembly |
| Evidence verify ratio ~19% | Medium | Many fn_names still invalid after P5 cleanup |
| B/RC appears in v2 (1 BD) | Low | P4 RC→T rule should also catch compound B/RC |
| Document extraction not yet tested on real mixed project | High | Need deer-flow or similar project with SKILL.md |

## Next Steps
1. Test document extraction path on a mixed project (deer-flow or similar)
2. Upgrade constraint extraction agent using same patterns
3. Fix P7 stage_id resolution (fuzzy match between synthesis and assembly stage names)
4. Improve evidence verification (AST lookup for more function names)
