# BRICK_INVENTORY.md

Updated: 2026-03-24

## Summary Statistics

| Metric | Value |
|--------|-------|
| Total bricks | 278 |
| L1 (framework-level) bricks | 52 |
| L2 (pattern-level) bricks | 182 |
| Failure/anti-pattern bricks | 58 |
| Failure ratio | 25.5% (≥15% ✓) |
| Frameworks/domains covered | 34 |
| Evidence refs per brick | 1 (all with documentation URLs) |

---

## Brick Files

### AI Frameworks (13 targets, 87 bricks) — NEW 2026-03-24

| File | Domain | Bricks | L1 | Failure |
|------|--------|-------:|---:|--------:|
| langchain.jsonl | LangChain | 10 | 2 | 5 |
| huggingface_transformers.jsonl | HF Transformers | 10 | 2 | 3 |
| llamaindex.jsonl | LlamaIndex | 8 | 2 | 2 |
| vllm.jsonl | vLLM | 8 | 2 | 2 |
| crewai.jsonl | CrewAI | 7 | 2 | 2 |
| litellm.jsonl | LiteLLM | 7 | 2 | 2 |
| ollama.jsonl | Ollama | 7 | 2 | 2 |
| langgraph.jsonl | LangGraph | 7 | 2 | 3 |
| llama_cpp.jsonl | llama.cpp | 7 | 2 | 2 |
| diffusers.jsonl | Diffusers | 7 | 2 | 2 |
| openai_sdk.jsonl | OpenAI SDK | 7 | 2 | 2 |
| langfuse.jsonl | Langfuse | 7 | 2 | 2 |
| dspy.jsonl | DSPy | 7 | 2 | 2 |

### Web Frameworks — Non-AI First Tier (4 targets, 46 bricks) — NEW 2026-03-24

| File | Domain | Bricks | L1 | Failure |
|------|--------|-------:|---:|--------:|
| typescript_nodejs.jsonl | TypeScript/Node.js | 14 | 3 | 3 |
| nextjs.jsonl | Next.js | 10 | 2 | 2 |
| vuejs.jsonl | Vue.js | 10 | 3 | 2 |
| java_spring_boot.jsonl | Java/Spring Boot | 12 | 3 | 3 |

### Original Bricks (12 targets, 89 bricks)

| File | Domain | Bricks | L1 | Failure |
|------|--------|-------:|---:|--------:|
| python_general.jsonl | Python general | 16 | 5 | 3 |
| fastapi_flask.jsonl | FastAPI/Flask | 9 | 2 | 2 |
| django.jsonl | Django | 7 | 2 | 2 |
| react.jsonl | React | 6 | 1 | 2 |
| go_general.jsonl | Go general | 7 | 1 | 1 |
| home_assistant.jsonl | Home Assistant | 8 | 2 | 0 |
| obsidian_logseq.jsonl | Obsidian/Logseq | 6 | 2 | 1 |
| domain_finance.jsonl | Finance | 6 | 0 | 1 |
| domain_health.jsonl | Health | 6 | 0 | 1 |
| domain_pkm.jsonl | PKM | 6 | 0 | 1 |
| domain_private_cloud.jsonl | Private Cloud | 6 | 0 | 2 |
| domain_info_ingestion.jsonl | Info Ingestion | 6 | 0 | 1 |

---

## Brick Level Distribution

| Level | Count | Fraction |
|-------|-------|----------|
| L1 (framework philosophy) | 52 | 22.2% |
| L2 (patterns / UNSAID) | 182 | 77.8% |

---

## Scene Coverage

### AI Application Stack
```
LLM Orchestration:      LangChain + LangGraph
RAG:                    LlamaIndex
Provider Abstraction:   LiteLLM + OpenAI SDK
Model Foundation:       HF Transformers
Inference Serving:      vLLM (prod) + Ollama (local) + llama.cpp (edge)
Agent:                  CrewAI
Multimodal Generation:  Diffusers
Observability:          Langfuse
Prompt Programming:     DSPy
```

### Web / General Stack
```
Python:       Python general + Django + FastAPI/Flask
JavaScript:   TypeScript/Node.js + Next.js + React + Vue.js
Java:         Java/Spring Boot
Go:           Go general
```

### Vertical Domains
```
Finance, Health, PKM, Private Cloud, Info Ingestion
Home Assistant, Obsidian/Logseq
```

### Non-AI Second Tier (5 targets, 44 bricks) — NEW 2026-03-24 (Codex)

| File | Domain | Bricks | L1 | Failure |
|------|--------|-------:|---:|--------:|
| ruby_rails.jsonl | Ruby/Rails | 10 | 2 | 4 |
| rust.jsonl | Rust | 10 | 2 | 2 |
| php_laravel.jsonl | PHP/Laravel | 8 | 2 | 2 |
| swift_ios.jsonl | Swift/iOS | 8 | 2 | 2 |
| kotlin_android.jsonl | Kotlin/Android | 8 | 2 | 3 |
