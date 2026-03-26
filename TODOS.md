# Doramagic TODOS

Generated from CEO Review + Eng Review on 2026-03-23.

## P1 — Next after Dual-Layer Fusion ships

### Cross-project GCD (Greatest Common Denominator)
- **What**: Implement cross-project knowledge extraction — find consensus patterns across N projects in the same domain
- **Why**: Second flywheel. More extractions → more reliable GCD → attracts same-domain users → more extractions
- **Context**: Research complete (2026-03-15). `cross_project/` package has discovery + synthesis code. `project_fingerprint.json` schema designed. Architecture prep (typed object persistence, N>1 synthesis interface) included in current build.
- **Effort**: L (human: 3-4 weeks / CC: 3-4 days)
- **Depends on**: Dual-Layer Fusion Phase 4 (E2E working) + Phase 5.5 (Brick System v2 for feedback loop)

### Phase B-H Crash Resume
- **What**: Make Phases B-H resumable from last checkpoint (currently only Phase A is resumable)
- **Why**: Phase C can take 10-30 min. Timeout/crash loses all progress.
- **Context**: Checkpoint-based lease system already persists state. Extension: save intermediate results per-phase so controller can resume mid-pipeline.
- **Effort**: M (human: 1-2 weeks / CC: 1-2 days)
- **Depends on**: Dual-Layer Fusion Phase 3 (controller wired)

## P2 — Medium-term

### StitchCraft (Knowledge Stitching)
- **What**: Constrained knowledge combination from multiple source projects into a single skill
- **Why**: Users rarely find one perfect project — they need combinations. StitchCraft produces "combination possibility maps" not pre-sewn skills.
- **Context**: Design complete (6 conflict types: semantic, scope, architecture, dependency, operational, license). Not started.
- **Effort**: XL (human: 6-8 weeks / CC: 5-7 days)
- **Depends on**: Cross-project GCD working

### Domain Knowledge Map
- **What**: Pre-built knowledge graph per domain (finance, PKM, health, etc.) as flywheel cold-start fuel
- **Why**: When a user arrives, Doramagic already has organized memory about their domain instead of starting from scratch.
- **Context**: 6 domains selected (broad finance, PKM, private cloud, health data, information ingestion, smart home). Research at `research/pre-extraction-domains/`. Storage: SQLite + Parquet + JSONL.
- **Effort**: XL (human: 8-12 weeks / CC: 6-8 days)
- **Depends on**: Cross-project GCD + System B (preextract API)

### BrickCandidate Semantic Deduplication
- **What**: Replace exact normalized title match with embedding-based similarity for brick candidate promotion
- **Why**: LLM-generated card titles vary in phrasing even for identical concepts. Exact match produces near-zero candidates.
- **Context**: v1 uses normalized exact match (lowercase + strip punctuation + collapse whitespace). Semantic dedup requires embedding model + ANN index.
- **Effort**: M (human: 1-2 weeks / CC: 1-2 days)
- **Depends on**: Brick System v2 running with real extraction data

## P3 — Future

### Web API Adapter
- **What**: PlatformAdapter implementation for REST API deployment
- **Why**: Enables Doramagic as a standalone web service independent of OpenClaw
- **Context**: PlatformAdapter protocol designed. CLI adapter in current build. Web adapter is the next platform.
- **Effort**: M (human: 2-3 weeks / CC: 2-3 days)
- **Depends on**: Dual-Layer Fusion Phase 4 (E2E with CLI adapter working)

### User Feedback Loop
- **What**: Collect user ratings/corrections on generated skills and feed back into extraction quality
- **Why**: Closes the quality flywheel — user signal improves extraction, better extraction attracts users
- **Context**: Requires deployed product with real users. No design yet.
- **Effort**: L (human: 3-4 weeks / CC: 3-4 days)
- **Depends on**: Deployed product on OpenClaw with real usage

### Multi-language Support
- **What**: Support extraction from non-English/Chinese codebases and deliver skills in other languages
- **Why**: Expands addressable market beyond Chinese-speaking developers
- **Context**: Not started. Current system assumes Chinese user input + English code.
- **Effort**: M
- **Depends on**: Stable product with proven extraction quality

## Security — MEDIUM findings from CSO audit (2026-03-26)

### Indirect prompt injection via repo content
- **What**: Add delimiter-based isolation (`<repo_content>...\</repo_content>`) in LLM prompts, instruct system prompt to ignore directives inside delimiters
- **Why**: Malicious GitHub repos can embed instructions in README that manipulate extraction output
- **Files**: `scripts/doramagic_singleshot.py`, `packages/extraction/doramagic_extraction/llm_stage_runner.py`
- **Effort**: S (CC: ~15min)

### LLM call budget in singleshot.py
- **What**: Add per-session call counter with cap + total token logging
- **Why**: Unbounded LLM API calls = unbounded Aliyun/Bailian cost per /dora invocation
- **File**: `scripts/doramagic_singleshot.py`
- **Effort**: S (CC: ~15min)

### ReDoS via LLM-controlled regex in stage15 fallback
- **What**: Add pattern length limit (max 200 chars) before `re.compile()` in Python grep fallback
- **File**: `packages/extraction/doramagic_extraction/stage15_agentic.py:340`
- **Effort**: S (CC: ~5min)

### Security tests skipped in CI
- **What**: Re-enable `test_dsd.py` and `test_confidence_system.py` in CI (mock LLM layer if needed)
- **Why**: DSD (deceptive source detection) regression would go undetected
- **File**: `.github/workflows/ci.yml:34-38`
- **Effort**: M (CC: ~30min)

### Over-permissive allowed-tools in legacy skills
- **What**: Scope `allowed-tools` to minimum required in doramagic-s{1-4} SKILL.md
- **Why**: `[exec, read, write]` maximizes blast radius for prompt injection attacks
- **Files**: `skills/doramagic-s{1-4}/SKILL.md`
- **Effort**: S (CC: ~10min)

### races/ cleanup
- **What**: `git rm -r --cached races/` to remove internal experiments from tracking (already gitignored in this commit)
- **Why**: Internal experiments should not be in public repo
- **Effort**: S (CC: ~5min)
