# Changelog

All notable changes to Doramagic are documented in this file.

## [12.1.2] - 2026-03-29

### Fixed — SKILL.md format alignment with OpenClaw conventions
- Restructured SKILL.md to match script-executing skill conventions (search-x, script-writer pattern)
- Command moved from between --- separators to markdown code block
- Added "When to Use / When NOT to Use" section — prevents host AI from rejecting valid DOMAIN_EXPLORE requests
- Added "Example Usage in Chat" with User→Action mappings for all 4 input routes
- Added explicit Protocol constraints: "Always run the script", "Do NOT judge whether the request is appropriate"
- Fixed host AI behavior: previous format caused AI to analyze code instead of executing the pipeline

### Fixed — models.json configuration flow
- models.json removed from git tracking (was leaking personal config to public repo)
- Quick Start updated: models.json now configured inside installed skill directory, not repo root
- README adds must-install signal + real output sample to prevent AI hallucination


## [12.1.1] - 2026-03-28

### Architecture — Deterministic Routing DAG (replaces linear pipeline)
- Input Router: 4 deterministic paths (DIRECT_URL / NAMED_PROJECT / DOMAIN_EXPLORE / LOW_CONFIDENCE)
- Conditional edge FSM: lambda-driven state transitions replace fixed linear TRANSITIONS
- Fan-out WorkerSupervisor: up to 3 isolated RepoWorkers with independent budgets/timeouts
- 4-tier degraded delivery: user always receives output, never blank failure
- Enhanced 5-layer progress feedback: plan preview → phase transitions → worker granularity → partial artifacts → checklist summary
- EventBus + run_events.jsonl: structured event logging for /dora-status
- Quality gate: 5-dimension 60-point threshold with targeted single-section REVISE
- Compile-readiness gate: prevents wasting 51% compile time on low-quality synthesis

### Deleted
- doramagic_singleshot.py (2550 lines) — fully replaced by FlowController
- 7 legacy test files with missing fixtures

### Added
- InputRouter, EventBus, WorkerSupervisor, RepoWorker, RepoTypeClassifier, EnvelopeCollector, QualityGate
- Contracts: RoutingDecision, RunEvent, RepoExtractionEnvelope
- Local knowledge accumulation (~/.doramagic/accumulated/{domain}.jsonl)
- 26 tests (19 unit + 7 E2E smoke covering 4 PRD paths)
- Delivery artifacts: PROVENANCE.md, DSD_REPORT.md, CONFIDENCE_STATS.json

### Fixed
- CWD fallback on download failure: empty repo path no longer silently analyzes working directory
- RepoRef missing required fields in phase_runner.py
- Python tracebacks no longer leak to stdout (structured JSON errors only)
- SynthesisRunner fabricated fallback strings replaced with [NO_DATA] + degradation trigger
- Thread leak in WorkerSupervisor: explicit future.cancel() for timed-out workers



## [12.1.0] - 2026-03-28
### Fixed (S-tier — pipeline was fundamentally broken)
- Engine path resolution: _find_engine() searches multiple candidate paths (engine was never invoked)
- LLM retry: 3 attempts with exponential backoff + jitter + adaptive timeout (72% template fallback → <10%)
- Brick contamination: affinity_terms validation + max-1-domain guard + word-boundary matching (17% cross-domain pollution → ~0%)
- CWD self-reference: read_repo_files rejects empty/relative paths (was reading own README as target project)

### Added (A-tier — architecture improvements)
- GitHub Primary discovery: ClawHub controls search depth only, never skips GitHub. Engine + API fallback
- Section-split compiler: 5 focused LLM calls (700-1500 tokens each) replacing single 6000-token call
- Parallel soul extraction: ThreadPoolExecutor with deterministic input-order collection
- Repo type classifier: CATALOG/TOOL/FRAMEWORK, awesome-lists get shallow extraction
- 60-point quality gate: 5-dimension scoring (Coverage/Evidence/DSD/WHY/Substance) before delivery
- CJK-aware slugify: semantic word-boundary truncation, max 40 chars
- 4-tier graceful degradation: FULL/PARTIAL_SOULS/FAST_PATH/TEMPLATE with completeness percentage
- Crash resume: checkpoints at Step 1 (profile) and Step 3 (souls), --resume CLI flag
- Thread-safe logging with threading.Lock

### Changed
- Fast path synthesis trigger: uses has_repo_souls check instead of dead skip_github flag
- Validator accepts Anti-Patterns & Safety section heading
- Engine subprocess passes --timeout flag (engine gets timeout-15 for graceful shutdown)
- Retry loop no longer retries deterministic errors (KeyError/ValueError/JSONDecodeError)
- Evidence scoring broadened to reward parenthetical attribution and project references


### Added
- Skill Architect: LLM-powered compilation with gold-standard reference skills
- Self-repair loop: validates output, auto-fixes issues, retries
- Per-domain safety boundaries in generated skills
- Input sanitization against shell metacharacter injection (CSO audit fix)
- publish_preflight.sh: automated pre-release gate for GitHub standards
- card_id whitelist validation (path traversal prevention)

### Changed
- GitHub Actions pinned to SHA digests
- Internal IP references replaced with environment variables in SKILL.md
- Legacy extract.py converted from shell=True to list-form subprocess
- uv.lock now tracked by git (removed from .gitignore)
- races/, research/, experiments/ removed from public repo

### Security
- CSO audit: 6 HIGH findings fixed, 6 MEDIUM documented
- Full report in .gstack/security-reports/

## [11.0.0] - 2026-03-25

### Added
- Domain brick integration: 278 bricks across 34 domains injected into extraction prompts
- Fast path synthesis: Python-only compilation (no LLM), 52s to 14s
- GitHub search rewrite: qualifiers, README via API, relevance scoring, parallel processing
- Debug logging mode (--debug flag)

### Changed
- Intent recognition with LLM confidence scoring
- Socratic gate: low-confidence inputs return clarifying questions instead of blind search
- GitHub search timeout: 360s to 60s

## [10.0.0] - 2026-03-25
