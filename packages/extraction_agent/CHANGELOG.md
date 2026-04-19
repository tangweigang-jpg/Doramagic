# Changelog

All notable changes to `doramagic-extraction-agent` are documented here.
Format: [Keep a Changelog](https://keepachangelog.com) · versioning: semver.

## [0.3.0] — 2026-04-19

Evidence-honesty overhaul. Started from the finding that bp-073 ledger was the
only finance blueprint with `evidence_verify_ratio = 1.00`, traced the root
cause to two distinct defects in the L3 recovery path, and ended with 73 bps
re-enriched and a hard gate blocking future hallucination-heavy extractions.

### Added
- **`is_missing_evidence(ev)`** helper (`sop/blueprint_enrich.py`) —
  centralizes the sentinel semantics. Treats empty / whitespace / `-` / `—` /
  `N/A*` / `none` / `null` as "semantically missing". Replaces 7 scattered
  `ev.startswith("N/A")` / `not bd_raw.get("evidence")` checks across the
  synthesis, enrich, and L3 recovery paths.
- **`load_step2c_evidence_map(artifacts_dir)`** + **`_split_md_row(line)`** —
  parses the LLM-written `step2c_business_decisions.md` table into
  `{content_key: evidence}`. Honors backslash-escaped pipes inside cells so
  rows carrying formula BDs like `Loss Rate\|Closed` or `\|rho\|` no longer
  get column-shifted.
- **`load_worker_candidate_evidence_map(artifacts_dir)`** — reads
  `worker_*.json` `BDCandidate.evidence` refs (bound at exploration time).
  Used by v9 synthesis handlers as the primary recovery source since they
  run before `step2c_business_decisions.md` is written.
- **P5.3 `_patch_evidence_backfill_from_md`** (new enrich patch) — runs
  between P5 (normalize) and P5.5 (verify). Recovers `N/A` evidence from
  step2c.md by content-prefix match. Post-hoc safety net for blueprints
  already on disk with all-N/A `bd_list.json`.
- **`_recover_bd_evidence(bd_raw, md_evidence_map)`** helper
  (`sop/blueprint_phases.py`) — priority-ordered picker used at every L3
  recovery site in `_synthesis_v5_handler`. Preserves meaningful existing
  values; swaps only missing-sentinels.
- **BQ-11 hard gate** (`_quality_gate_handler`) — fails when
  `evidence_verify_ratio < 0.30` OR `evidence_invalid > 50`. Calibrated
  against the current 73-bp distribution (median 41.5%, so 22 of 73 pass
  cleanly; the 51 that fail are the long-tail hallucination cases).

### Changed
- **P5.5 `_patch_evidence_verify`** — for non-Python files (Go/Rust/JS/etc.)
  with a cited `(symbol)`, grep the symbol in a ±5 line window around the
  cited line. Previously these files auto-verified once the line was in
  range, meaning bp-073 ledger's `machine.go:197(opcodes)` registered as
  verified even though `opcodes` never appears in the file. Found 3
  hallucinations in bp-073 alone; ratio corrected 100% → 85.87%.
- **`_synthesize_v5_handler`** (`sop/blueprint_phases.py`) — its 5 L3
  recovery sites (step1 per-call ×2, structural BD merge, step1 aggregate
  ×2) used to hardcode `bd_raw["evidence"] = "N/A:0(see_rationale)"` when
  the LLM's structured output lacked the field. Now all go through
  `_recover_bd_evidence`, which consults a merged map of step2c.md
  + worker candidates first.
- **`_coerce_bd_dict`** (`sop/synthesis_v9.py`) — new optional
  `md_evidence_map` parameter, threaded through its 4 callers across
  `build_local_synthesis_handler`, `build_global_synthesis_handler`, and
  `build_fixer_handler`. The three handlers load a
  `{worker, **step2c}` merged map at entry, so v9 synthesis (which runs
  before step2c.md is written) can still recover real refs from worker
  candidates. Guard against stale partial-run step2c.md reuse is an open
  follow-up.
- **Gate docstring** — `_quality_gate_handler` now documents `BQ-01..BQ-11`
  instead of `BQ-01..BQ-09`.

### Fixed
- **Bug B — missing `code_example` / `technique_document`** (commit 3009f72) —
  `_patch_resource_injection` now pulls code examples from `uc_list.json`
  and technique docs from `repo_index.json` with a `_seen_paths` de-dup set.
- **Bug C — resources field entirely missing** (commit 3009f72) — removed an
  early `if not matrix: return 0` in the resource injection path that bailed
  out for 5 bps before ever looking at worker artifacts.
- **Bug D2 — audit coverage formula was inverted** (commit 3009f72) —
  `coverage = (pass+warn+fail)/total` now; previously reported
  `pass/total`, which double-counted failure as absence. Added `pass_rate`
  field alongside.
- **Adversarial-review fix-forward** (commit f74ada2) — 1 BLOCKER + 5
  CONCERNs from Codex review of 3009f72: `isinstance` guards at blueprint
  resource sites where dict/str confusion crashed the enrich phase,
  `logger.warning` for parse failures, etc.
- **`_patch_relations` domain-list TypeError** (commit e11f698) —
  `bp["applicability"]["domain"]` is sometimes a list (e.g. bp-050 skorecard
  `["CRD", "DAT", "Credit Scoring"]`). `_Path("knowledge/blueprints") /
  domain` crashed with `TypeError`. Now prefers `state.domain` and coerces
  list to first non-empty string.
- **bp-062-class mass-N/A evidence loss** (commits 4cb61b7 + 28d5e37 +
  d211c4e) — three rounds, culminating in full coverage of the v5 and v9
  recovery paths. End-to-end impact: bp-062 evidence_verify_ratio went
  from 0.00% to 79.71%; across all 73 bps, 1046 evidence refs recovered,
  mean ratio lifted ~6 percentage points.

### Tests
- `+19` new tests in `tests/test_blueprint_enrich.py`:
  - `TestIsMissingEvidence` (5) — sentinel detection coverage
  - `TestSplitMdRow` (5) — escaped-pipe parsing
  - `TestLoadStep2cEvidenceMapEscaped` (1) — integration for escape case
  - `TestLoadWorkerCandidateEvidenceMap` (4) — worker dict/str/missing
  - `TestPatchEvidenceBackfillFromMd` (4) — P5.3 patch behavior
  - `TestPatchEvidenceVerifyNonPython` (4) — symbol grep in ±5 window
  - `TestPatchRelations` (2 new, on top of 3 pre-existing) — list-domain
  and state.domain precedence
- Suite: 135 passed / 11 pre-existing failures (unchanged — those failures
  predate this release and track empty-dir assumptions in
  `knowledge/blueprints/finance/`).

### Known limitations (carried into 0.3.0)
- `evidence_invalid` hallucinations (Bug D1) are an LLM-capability issue,
  not a code bug. MiniMax-M2.7 consistently over-cites `file:line(symbol)`
  triples that don't exist. No code fix in this release; covered in
  `docs/research/2026-04-19-bp073-health-checklist.md` §6.
- `tool_script` resource category — SOP and worker prompts don't yet
  support it. Tracked in resources backlog.
- BQ-11 is not yet wired into `bp_fixer_v9` — the fixer currently repairs
  BDs that fail BQ-10 only. A follow-up commit should extend the fixer to
  also repair BDs whose file/line is valid but symbol isn't.
- v9 synthesis's L3 recovery tolerates stale `step2c.md` when a run
  directory is reused. Mitigation: `load_worker_candidate_evidence_map`
  provides an always-fresh fallback, but step2c.md wins on conflicts so
  stale rows could re-enter. Tracked as a v9 scheduling fix.

## [0.2.0] — earlier

Baseline before the evidence-honesty overhaul. Monolithic v5 synthesis with
Instructor 3-step + audit injection; v9 map-reduce (local/global/fixer)
available but L3 recovery paths in both defaulted missing evidence to the
`N/A:0(see_rationale)` sentinel, producing all-N/A `bd_list.json` whenever
the LLM's structured call returned malformed JSON.
