# Changelog

All notable changes to Doramagic are documented in this file.

## [10.0.0] - 2026-03-25

### Changed
- Single-shot pipeline upgraded to v9.0: LLM-powered keyword generation replaces static dictionary
- Relevance gate filters irrelevant repos before extraction, returns honest "not found" when appropriate
- Skill compiler outputs actionable AI agent instruction set instead of research report
- MIN_STARS threshold lowered to 0 to include small but relevant projects
- Entry point simplified to python3 (no uv/venv dependency)

### Fixed
- Search keyword generation bug: Chinese input like "WiFi密码管理" now correctly generates English search terms via LLM
- Production-to-repo version drift resolved (OpenClaw v10.0.0 synced back to Git)

## [9.2.0] - 2026-03-24

### Added
- Mermaid pipeline diagrams in README (top-level flow + extraction internals)
- Implementation highlights with code snippets in README
- Example output section showing real TandoorRecipes extraction
- GitHub Actions CI (pytest on push/PR, Python 3.12)
- Routing decision logging in CapabilityRouter (get_routing_summary())
- CI badge support

### Changed
- brick_injection.py: expanded framework mappings from 12 to 34 domains
- SKILL.md: fixed entry point path, updated to v9.2.0
- README: updated brick count to 278, added architecture visualization

### Fixed
- SKILL.md entry point was pointing to deprecated soul-extractor path
- Brick count assertion in tests updated for 278 bricks
- Makefile PYTHONPATH for cross-package test imports

## [9.1.0] - 2026-03-24

### Added
- 189 new knowledge bricks across 22 new frameworks/domains (89→278 total)
- AI stack coverage: LangChain, HF Transformers, LlamaIndex, vLLM, CrewAI, LiteLLM, Ollama, LangGraph, llama.cpp, Diffusers, OpenAI SDK, Langfuse, DSPy
- Web framework coverage: TypeScript/Node.js, Next.js, Vue.js, Java/Spring Boot
- General coverage: Ruby/Rails, Rust, PHP/Laravel, Swift/iOS, Kotlin/Android
- Trunk-based publish_to_github.sh release script

## [9.0.0] - 2026-03-23

### Added
- 8-stage extraction pipeline (Stage 0 through Stage 5 + Assembly)
- Agentic exploration (Stage 1.5) with hypothesis-driven deep dive
- Knowledge Compiler with type-routed formatting
- Confidence system with 4-tier evidence-chain verification
- Deceptive Source Detection (8-check DSD system)
- 89 knowledge bricks across 12 frameworks and domains
- Model-agnostic design via capability router (Claude, Gemini, GPT, Ollama)
- OpenClaw skill integration (/dora command)
- Claude Code skill compatibility
- ClawHub packaging script for one-command install
