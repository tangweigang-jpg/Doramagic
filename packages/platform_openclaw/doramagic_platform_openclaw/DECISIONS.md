# platform-openclaw.validator — Design Decisions

Date: 2026-03-19
Module: `platform-openclaw.validator`
Racer: S1 (Sonnet)
Round: 4, Track A

---

## D-001: No LLM calls

**Decision**: All 7 checks are implemented as pure deterministic string-parsing and regex matching. Zero LLM calls.

**Rationale**: The spec states this module is "mainly deterministic checks." Static analysis (YAML frontmatter parsing, regex pattern matching, URL detection) covers all required validation without any AI overhead. This guarantees cost < $0.03 (actually $0.00), sub-5s execution, and strict idempotency.

**Trade-off**: Completeness and Consistency checks are necessarily shallow (keyword presence, heading duplication, mixed storage paths) compared to what an LLM could infer. Accepted — spec explicitly allows free design on internal logic while requiring the 7 check names and blocking/warning semantics.

---

## D-002: BLOCKED only on missing files

**Decision**: `BLOCKED` status is returned only when one or more bundle files cannot be read (E_UPSTREAM_MISSING). All other failures produce `REVISE` with `revise_instructions`.

**Rationale**: The spec defines BLOCKED as "前置条件不满足（文件缺失等）". All other failures are fixable issues that the user/compiler can address, making REVISE the appropriate outcome. This matches the example output in section 3.3.

---

## D-003: Frontmatter parsed via line-splitting, not a YAML library

**Decision**: Frontmatter is parsed by splitting on `---` delimiters and iterating lines, not using PyYAML.

**Rationale**: PyYAML is not declared as a dependency of this package. Line-splitting is sufficient for extracting top-level keys and the `allowed-tools` list. Edge cases (multi-line values, anchors) are not expected in OpenClaw SKILL.md files. Avoids adding a dependency for a narrow use case.

**Candidate extension**: If OpenClaw SKILL.md format becomes more complex, consider adding PyYAML as an optional dependency and falling back to line-splitting on parse failure.

---

## D-004: Dark Trap Scan covers body of all 3 non-provenance files

**Decision**: `_check_dark_trap_scan` scans SKILL.md + LIMITATIONS.md + README.md concatenated. PROVENANCE.md is excluded from dark trap scanning.

**Rationale**: PROVENANCE.md legitimately contains external URLs and references that might match patterns (e.g., a source repo that discusses sudo). Provenance is read-only reference material, not executable behavior. Dark trap patterns are meaningful only in files that describe what the skill *does*.

---

## D-005: Platform Fit whitelist allows `allowed-tools` as a valid key

**Decision**: `allowed-tools` is always considered a valid frontmatter key, even though it is not in `metadata_openclaw_whitelist`.

**Rationale**: The `allowed_tools` field is a core OpenClaw mechanism (not "metadata" in the `metadata_openclaw_whitelist` sense). The whitelist covers supplementary metadata fields. Flagging `allowed-tools` as invalid would make every valid SKILL.md fail Platform Fit — clearly unintended.

---

## D-006: Completeness check uses keyword presence + capability keyword scan

**Decision**: Completeness checks (a) whether each `need_profile.keywords` appears in SKILL.md, and (b) whether at least one capability action verb appears.

**Rationale**: True semantic completeness requires LLM evaluation. This deterministic proxy catches the most common gaps: a skill that doesn't mention the domain at all, or one with no actionable steps. False negatives are possible for sophisticated skills; this is acceptable given the no-LLM constraint.

---

## D-007: revise_instructions generated per blocking check detail

**Decision**: `revise_instructions` are generated one per blocking check detail, with check-name-specific templates.

**Rationale**: Generic instructions ("fix this issue") are not actionable. Check-specific templates (e.g., "Remove cron from SKILL.md frontmatter and move scheduling notes to README") give the skill compiler concrete repair targets. This aligns with the spec's example: "Remove cron from SKILL.md frontmatter and move it to README installation notes."

---

## D-008: Envelope warnings mirror ValidationCheck warning failures

**Decision**: Each warning-level `ValidationCheck` failure is also surfaced as a `WarningItem` in the envelope's `warnings` list.

**Rationale**: The `ModuleResultEnvelope` has a dedicated `warnings` field consumed by orchestration. Surfacing warning-level check failures there makes them visible to `orchestration.phase_runner` without requiring it to inspect `ValidationReport.checks` directly. The envelope `status` remains `"ok"` (not `"degraded"`) since warnings do not block delivery.

**Candidate extension**: If orchestration needs to act on warnings, consider setting `status = "degraded"` when warning failures exist. Not implemented now to avoid scope creep.
