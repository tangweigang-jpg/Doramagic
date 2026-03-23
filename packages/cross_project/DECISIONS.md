# DECISIONS.md — cross-project.synthesis (Round 3 Race, S1/Sonnet)

Date: 2026-03-19
Module: `cross-project.synthesis`
Racer: S1 (claude-sonnet-4-6)

---

## Design Decisions

### D1: Deterministic-only implementation (no LLM calls)

**Decision:** The entire synthesis pipeline runs deterministically — zero LLM calls, zero API budget.

**Rationale:** The spec allows < $0.20 cost, but the real moat ("code says facts, AI tells stories") means the skeleton should be deterministic. Signal classification (ALIGNED → consensus, ORIGINAL → unique) is factual, not interpretive. The rationale strings are template-based and rule-derived, not generated. This makes the module:
- Fully testable without mocking LLM responses
- Deterministic (required for stable decision_id / conflict_id)
- Instantaneous (< 1ms per run)

**Trade-off:** Rationale text is less nuanced than an LLM would produce. Acceptable for v1 — the skill-compiler downstream can add LLM narrative if needed.

---

### D2: Signal-type routing table

**Decision:** Signals are routed as follows:
- `ALIGNED` → `consensus` block (include/option based on demand_fit)
- `ORIGINAL` → `unique_knowledge` block
- `DRIFTED` / `DIVERGENT` / `CONTESTED` → `conflicts` block
- `MISSING` / `STALE` → silently ignored (not yet surfaced)

**Rationale:** MISSING and STALE signals describe gaps and staleness, not actionable synthesis choices. Surfacing them in conflicts would create noise. They are candidates for a future `open_questions` auto-population pass.

---

### D3: Two-tier source for unique_knowledge

**Decision:** `unique_knowledge` is populated from three sources in priority order:
1. ORIGINAL compare signals (strongest evidence — cross-project second-pass confirmation)
2. `project_summaries.top_capabilities` (not captured in signals — extraction-level insights)
3. `community_knowledge.reusable_knowledge` (community-validated patterns)

**Rationale:** Each tier has decreasing structural evidence but adds orthogonal signal types. Community knowledge is often absent from GitHub repos but highly relevant for OpenClaw skill compilation.

---

### D4: selected_knowledge = union of include decisions

**Decision:** `selected_knowledge` is the union of all `include` decisions from `consensus` + `unique_knowledge`. A new `SEL-` prefixed ID is minted, referencing the origin `decision_id` as the first source ref.

**Rationale:** This makes the downstream skill-compiler's job simple: only read `selected_knowledge` for compilation. The traceability chain is `SEL-* → DEC-* → SIG-*/project_id/community_item_id`.

---

### D5: License conflict → hard block

**Decision:** Any `license` category conflict causes `blocked + E_UNRESOLVED_CONFLICT` — no partial output.

**Rationale:** Compiling a skill from GPL-licensed knowledge without resolution would create legal exposure. The spec explicitly requires this behaviour. No synthesis output is written when blocked (avoids downstream consuming a partial result).

---

### D6: Conflict category inference via keyword heuristics

**Decision:** Conflict category is inferred by scanning the normalized statement for category-specific keywords. Default fallback is `semantic`.

**Rationale:** Compare signals don't carry category metadata — only the statement text is available. Keyword matching is fast, predictable, and produces stable IDs (since the category feeds `_conflict_id`). The heuristic covers the most common cases; semantic is a safe catch-all.

---

### D7: Dual output — JSON canonical + Markdown mirror

**Decision:** Both files are always written together, or neither is written (on blocked path).

**Rationale:** The spec requires both. JSON is the canonical format consumed by `skill-compiler.openclaw`. Markdown is the human-readable mirror with badge annotations (✅ INCLUDE, ❌ EXCLUDE, 🔀 OPTION) for quick review. If the module is blocked, no files are written to avoid stale artifacts.

---

### D8: Output directory via DORAMAGIC_SYNTHESIS_OUTPUT_DIR env var

**Decision:** Output directory is controlled by the `DORAMAGIC_SYNTHESIS_OUTPUT_DIR` environment variable, defaulting to `$TMPDIR/doramagic_synthesis/{domain_id}/`.

**Rationale:** Follows the same pattern as `compare.py` (`DORAMAGIC_COMPARE_OUTPUT_DIR`). This allows tests to inject a `tmp_path` without polluting the filesystem, and production to write to a known workspace directory.

---

## Candidate Extensions (not in current output schema)

The following fields were considered but not added to the output (to stay within frozen contract):

- `synthesis_confidence: float` — aggregate confidence score across all decisions
- `provenance_graph: dict` — explicit DAG linking decisions to compare signals to evidence refs
- `missing_coverage: list[str]` — MISSING signals surfaced as capability gaps

These are documented here as candidates for a future schema version negotiation with the PM/architect.

---

## Test Coverage Summary

| Test | Assertion |
|------|-----------|
| `test_returns_ok_status` | Basic happy-path, status == "ok" |
| `test_at_least_one_consensus` | ALIGNED signals → consensus block populated |
| `test_at_least_one_unique_knowledge` | ORIGINAL signals → unique_knowledge populated |
| `test_at_least_one_conflict` | DRIFTED signals → conflicts block populated |
| `test_all_selected_knowledge_traceable` | Every selected item has source_refs |
| `test_writes_synthesis_report_json` | JSON file written with correct schema_version |
| `test_writes_synthesis_report_md` | Markdown file written |
| `test_decision_ids_are_stable` | Same input → same decision_ids |
| `test_conflict_ids_are_stable` | Same input → same conflict_ids |
| `test_missing_comparison_result_projects_blocks` | Empty compared_projects → E_UPSTREAM_MISSING |
| `test_license_conflict_blocks_synthesis` | License conflict → E_UNRESOLVED_CONFLICT |
| `test_no_conflict_when_only_aligned_signals` | Pure ALIGNED → no conflicts |
| `test_excluded_knowledge_has_rationale` | All exclude decisions have rationale |
| `test_community_knowledge_contributes_to_unique` | Community reusable_knowledge in unique_knowledge |
| `test_conflict_category_is_valid` | All categories from allowed enum |
| `test_decision_values_are_valid` | All decisions are include/exclude/option |
