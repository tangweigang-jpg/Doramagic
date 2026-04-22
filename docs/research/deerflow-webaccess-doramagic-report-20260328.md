# Doramagic × DeerFlow × web-access Deep Research Report

Date: 2026-03-28
Subject repos:
- DeerFlow: https://github.com/bytedance/deer-flow
- web-access: https://github.com/eze-is/web-access
- Doramagic: https://github.com/tangweigang-jpg/Doramagic

## Executive Summary

After reviewing DeerFlow's codebase, web-access's skill architecture, and Doramagic's current implementation on the mini, my conclusion is:

**Doramagic's next breakthrough is not “more extraction stages”. It is to become a visible, stateful, fan-out/fan-in system instead of a single opaque script.**

Your two pain points are real and structural:

1. **Black-box execution**: the current OpenClaw skill entry still points to `skills/doramagic/SKILL.md -> doramagic_singleshot.py`, so the user only reliably sees the final message. Doramagic already has a better controller path (`doramagic_main.py` + `FlowController` + `OpenClawAdapter.send_progress()`), but the installed skill does not use it.
2. **Linear pipeline**: the current default experience is still a waterfall. DeerFlow and web-access both show a better pattern: **goal-driven routing + isolated workers + visible progress + fan-out/fan-in orchestration**.

If you only do three things, do these first:

- **P0-1. Repoint the skill entry from `doramagic_singleshot.py` to `doramagic_main.py`** and make the controller the default production path.
- **P0-2. Introduce a real run event bus** (`run_events.jsonl` + optional local SSE endpoint) and stop relying on stdout progress as the primary UX channel.
- **P0-3. Replace waterfall repo processing with a DAG**: discovery -> per-repo workers in parallel -> synthesis -> compile -> validation.

Those three changes will improve both user experience and extraction quality more than adding more stages to the current script.

---

## What DeerFlow does better than Doramagic today

### 1. DeerFlow treats long work as a first-class streamed process, not a blocking command

Relevant evidence:
- `README.md` exposes a streaming LangGraph API and a Claude Code bridge (`skills/public/claude-to-deerflow/SKILL.md`) instead of only a final return value.
- `backend/packages/harness/deerflow/tools/builtins/task_tool.py` emits structured custom events: `task_started`, `task_running`, `task_completed`, `task_failed`, `task_timed_out`.
- `frontend/src/components/workspace/messages/subtask-card.tsx` renders those subtasks live.
- `backend/packages/harness/deerflow/agents/middlewares/todo_middleware.py` preserves visible task tracking even after context summarization.

**Implication for Doramagic**: users should be able to watch the forge work in real time: which repo is being analyzed, which phase is blocked, which subtask finished, whether quality risk is rising.

### 2. DeerFlow is graph-oriented, not script-oriented

Relevant evidence:
- Lead agent + middleware chain + subagent system.
- `task_tool.py` spawns isolated subagents asynchronously.
- `subagents/executor.py` maintains explicit task states and background execution pools.
- Different runtime modes exist through context: flash / standard / pro / ultra.

**Implication for Doramagic**: extraction should become **workerized**. Each repo or evidence lane should be an isolated worker with its own state, timeout, summary, and result contract.

### 3. DeerFlow separates transport, orchestration, memory, and UI

Relevant evidence:
- Gateway API, LangGraph API, channels, frontend, and memory are separate modules.
- Thread state and artifacts are explicit system objects.

**Implication for Doramagic**: do not keep mixing product UX, extraction logic, and platform I/O inside one giant script.

---

## What web-access does better than Doramagic today

web-access is not a full app like DeerFlow, but it contains several elite design ideas that are directly useful for Doramagic.

### 1. Goal-driven routing instead of precommitted step lists

Relevant evidence:
- `SKILL.md` explicitly says to start from the goal, choose a promising path, inspect evidence continuously, and change strategy when the evidence says the path is wrong.
- It avoids overcommitting to “search first” / “fetch first” / “browser first”.

**Implication for Doramagic**: Doramagic should not always do “profile -> search -> extract -> synthesize -> compile” the same way. It should switch paths based on evidence quality:
- user already gave repo URLs -> skip discovery
- repo is obviously an awesome-list/catalog -> shallow extraction path
- repo is sparse but has strong external docs -> docs-first path
- repo is large/monorepo -> skeleton-first path

### 2. Persistent operational memory

Relevant evidence:
- web-access stores domain/site operation knowledge under `references/site-patterns/`.
- It accumulates validated facts and traps rather than rediscovering them every session.

**Implication for Doramagic**: build a `repo-patterns/` or `extraction-patterns/` layer for recurring repo types:
- awesome-list / curated catalog
- docs-only project
- SDK / framework
- monorepo
- infra tool
- UI app
- MCP server
- AI agent framework

### 3. Parallel decomposition with isolation

Relevant evidence:
- web-access explicitly recommends splitting independent targets across sub-agents.
- Shared browser proxy, tab-level isolation, summary return to the lead agent.

**Implication for Doramagic**: one repo worker should never contaminate another repo worker’s prompt state. The lead synthesizer should only receive normalized extraction envelopes, not the full raw trail.

---

## Critical finding inside Doramagic itself

Doramagic already contains the skeleton of the better architecture — but it is not the active path.

### Evidence

1. **The installed skill still points to singleshot**
   - `skills/doramagic/SKILL.md:14`
   - entrypoint: `python3 {baseDir}/scripts/doramagic_singleshot.py ...`

2. **But the repo already contains a controller-based entrypoint**
   - `skills/doramagic/scripts/doramagic_main.py`
   - imports `FlowController`
   - uses `OpenClawAdapter`

3. **The controller already supports progress**
   - `packages/controller/doramagic_controller/flow_controller.py`
   - emits `ProgressUpdate(...)` before and after phases

4. **The OpenClaw adapter already supports progress messages, but does not trust the platform to show them**
   - `packages/controller/doramagic_controller/adapters/openclaw.py`
   - comment: `OpenClaw may or may not display it.`

So the right conclusion is:

> Doramagic does not primarily need another giant rewrite. It needs to make the controller path real, make progress transport explicit, and stop treating the platform stdout as the progress UX.

---

# 14 Technical and Engineering Recommendations

## P0 — Must do now

### 1. Make the controller path the default production path
**Priority:** P0  
**Inspired by:** DeerFlow’s separation of orchestration from execution  
**Doramagic evidence:** `skills/doramagic/SKILL.md` still points to singleshot; `doramagic_main.py` already exists.

**Recommendation**
- Change the installed skill entrypoint from `doramagic_singleshot.py` to `doramagic_main.py`.
- Treat `doramagic_singleshot.py` as a compatibility/debug path, not the product path.

**Why this matters**
- It unlocks re-entrant runs, clarification pauses, phase-level progress, and cleaner executor boundaries.
- Right now you are shipping the worse architecture even though the repo already contains the better one.

**Concrete action**
- Update `skills/doramagic/SKILL.md`
- Add a release/preflight check that fails if the skill bundle points to singleshot instead of the controller.

---

### 2. Introduce a real run event bus; stop relying on stdout for progress UX
**Priority:** P0  
**Inspired by:** DeerFlow `task_started/task_running/task_completed` events + stream API  
**Solves:** black-box execution

**Recommendation**
Create a structured event stream per run:
- file: `runs/<run_id>/run_events.jsonl`
- schema:
  - `ts`
  - `phase`
  - `type` (`run_started`, `phase_started`, `repo_worker_started`, `repo_worker_progress`, `warning`, `degraded`, `phase_completed`, `run_completed`)
  - `message`
  - `meta`

**Why this matters**
- Stdout is not a reliable product transport in OpenClaw.
- A persisted event log can feed CLI, OpenClaw, future web UI, and debugging equally well.

**Concrete action**
- Add `RunEvent` schema in `packages/contracts`
- Add `EventBus` writer in controller
- Keep final answer on stdout, but progress goes to event bus
- Optional next step: expose local SSE endpoint or `dora-status <run_id>` tail command

---

### 3. Add a user-visible `dora-status` / `dora-tail` command
**Priority:** P0  
**Inspired by:** DeerFlow’s `claude-to-deerflow` skill and thread/status model  
**Solves:** black-box execution

**Recommendation**
Provide a second skill/command:
- `/dora-status <run_id>` → returns current phase, current repo, completed repos, warnings, ETA, latest artifacts
- `/dora-tail <run_id>` → returns the last N run events

**Why this matters**
- Even if OpenClaw cannot stream the main run live, users can pull status on demand.
- This is dramatically better than waiting for a silent 2–10 minute black box.

**Concrete action**
- Reuse `run_events.jsonl`
- Add a lightweight status script under `skills/doramagic/scripts/`
- Include the active `run_id` in every initial response immediately

---

### 4. Replace the linear waterfall with a DAG scheduler
**Priority:** P0  
**Inspired by:** DeerFlow’s graph/subagent orchestration + web-access’s adaptive routing  
**Solves:** linear architecture risk and inefficiency

**Recommendation**
Model Doramagic as a DAG:
- Node A: Need profile
- Node B: Discovery
- Node C1..Cn: repo preparation / repo facts / repo extraction
- Node D1..Dn: community signals per repo
- Node E: synthesis
- Node F: compile
- Node G: validation
- Node H: delivery

Edges:
- `B -> C*`
- `C_i -> D_i` (optional parallel)
- `C* + D* -> E`
- `E -> F -> G -> H`

**Why this matters**
- One repo failing should not block other repo workers.
- Community harvesting and soul extraction should not be globally serialized.
- A DAG also gives clean progress percentages and resume points.

**Concrete action**
- Keep your current `FlowController`, but make `PHASE_CD` internally a DAG runner instead of one serial loop
- You do **not** need full LangGraph immediately; a custom DAG executor is enough for v1

---

### 5. Add per-repo isolated workers and fan-out/fan-in synthesis
**Priority:** P0  
**Inspired by:** DeerFlow isolated sub-agent contexts; web-access parallel independent targets

**Recommendation**
Each repo candidate should run in an isolated worker context with:
- its own temporary workspace
- its own prompt/input budget
- its own retry budget
- its own progress stream
- its own extraction envelope

The synthesizer should only see normalized envelopes, not raw worker history.

**Why this matters**
- This reduces cross-project contamination.
- It also enables true parallelism without context pollution.

**Concrete action**
- Define `RepoExtractionEnvelope` in `contracts`
- One worker returns: repo facts, evidence cards, confidence summary, warnings, runtime metrics
- Synthesis consumes only envelopes

---

## P1 — High-value next

### 6. Add “execution modes” like DeerFlow: Flash / Standard / Pro / Ultra
**Priority:** P1  
**Inspired by:** DeerFlow runtime modes via context

**Recommendation**
Expose four modes:
- **Flash**: user-provided repos only, no deep community mining, template compile fallback allowed
- **Standard**: discovery + top 2 repos + shallow community
- **Pro**: standard + Stage 1.5 agentic exploration + stronger validation
- **Ultra**: pro + fan-out repo workers + adversarial review + cross-project intelligence

**Why this matters**
- Users often do not want the same budget/latency profile.
- This also fixes the “more stages = more failure risk” complaint: not every task needs the deepest pipeline.

**Concrete action**
- Add `mode` to need profile / runtime config
- Map mode to budgets, max repos, stage enable flags, compile strategy

---

### 7. Add a visible Todo / Plan lane for long Doramagic runs
**Priority:** P1  
**Inspired by:** DeerFlow TodoMiddleware + Todo UI

**Recommendation**
For long runs, create a visible task list such as:
- clarify intent
- search candidate repos
- download selected repos
- extract repo 1/3
- extract repo 2/3
- harvest community signals
- synthesize common WHY
- compile SKILL
- validate output

**Why this matters**
- Users feel progress even when content output is not yet ready.
- Internally, it also forces you to make the pipeline state explicit.

**Concrete action**
- Add `todos` to controller state
- Persist them in state and events
- Render them in CLI/OpenClaw status output
- Inject reminder if context resumes after interruption

---

### 8. Make routing goal-driven, not step-driven
**Priority:** P1  
**Inspired by:** web-access browsing philosophy

**Recommendation**
Stop assuming the same path for every request. Add early routing rules:
- user gives repo URLs -> repo-first mode, no GitHub discovery
- repo name exact match found -> skip broader search
- awesome-list / catalog -> shallow knowledge extraction, no code-heavy prompts
- docs-heavy framework -> docs-first extraction
- sparse repo + rich external docs -> web/docs lane

**Why this matters**
- It reduces wasted work.
- It improves hit quality faster than tuning thresholds alone.

**Concrete action**
- Add a `RoutingDecision` object before discovery/extraction
- Persist routing decisions into run events for auditability

---

### 9. Build a persistent “extraction patterns” memory like web-access site-patterns
**Priority:** P1  
**Inspired by:** web-access `references/site-patterns/`

**Recommendation**
Create a knowledge directory such as:
- `references/repo-patterns/awesome-list.md`
- `references/repo-patterns/monorepo.md`
- `references/repo-patterns/docs-heavy-framework.md`
- `references/repo-patterns/vercel-ai-sdk-app.md`
- `references/repo-patterns/langgraph-agent-project.md`

Each file stores:
- platform/repo traits
- reliable evidence sources
- known extraction traps
- routing hints
- last-updated date

**Why this matters**
- Doramagic should get smarter about extraction strategy over time, not only about extracted content.

---

### 10. Add a persistent repo intelligence cache/daemon
**Priority:** P1  
**Inspired by:** DeerFlow’s stateful services; web-access persistent CDP proxy

**Recommendation**
Run a lightweight local “Repo Intelligence Daemon” that caches:
- cloned repos by commit SHA
- repo facts
- README embeddings / summaries
- prior community signals
- extraction envelopes

**Why this matters**
- repeated runs become much faster
- enables background prefetch
- makes status queries instant

**Concrete action**
- cache key = `{repo_full_name}@{commit_sha}`
- APIs: `ensure_repo_cached`, `get_repo_facts`, `get_last_extraction`

---

### 11. Emit partial deliverables early, not only final SKILL.md
**Priority:** P1  
**Inspired by:** DeerFlow artifact/thread model

**Recommendation**
As soon as they exist, expose:
- candidate repos
- repo facts snapshot
- current WHY cards
- current trap cards
- synthesis draft
- quality gate report

**Why this matters**
- “No result yet” becomes “here is the current draft state”.
- This strongly reduces the emotional black-box feeling.

**Concrete action**
- write well-known artifacts under `runs/<run_id>/artifacts/`
- status command should surface them progressively

---

### 12. Run validation and adversarial review as a parallel lane, not only as a terminal gate
**Priority:** P1  
**Inspired by:** DeerFlow’s parallel subtasks and structured task states

**Recommendation**
After the first synthesis draft exists:
- one worker continues compilation
- another worker performs contamination/entity review
- another worker performs quality scoring / rubric checks

These should converge before final delivery.

**Why this matters**
- validation stops being a single late choke point
- compile can improve while review is already working

---

## P2 — Strong engineering upgrades

### 13. Unify source-of-truth packaging; stop mirroring code manually into `skills/doramagic/`
**Priority:** P2  
**Inspired by:** DeerFlow’s clearer platform vs harness boundary

**Recommendation**
Today Doramagic mirrors scripts/packages into the skill bundle. That makes drift easy.

Move to:
- root repo = source of truth
- build step = generate self-contained skill bundle into `dist/skill/`
- release step = install/copy bundle from `dist/skill/`

**Why this matters**
- avoids “controller exists but skill still points at singleshot” drift
- reduces release mistakes

---

### 14. Add a minimal local run dashboard
**Priority:** P2  
**Inspired by:** DeerFlow web UI + thread artifacts

**Recommendation**
Expose a tiny local page for a run:
- current phase
- current repo worker states
- todos
- warnings / degraded states
- artifacts list
- quality score
- latest 50 events

**Why this matters**
- even if OpenClaw remains text-first, serious users will want a visual run console
- debugging becomes dramatically easier

---

### 15. Add cancellation and backpressure controls
**Priority:** P2  
**Inspired by:** DeerFlow subagent timeout + concurrency limit patterns

**Recommendation**
Support:
- cancel current run
- cancel a stuck repo worker
- max concurrent repo workers
- max community jobs
- max compile retries
- dynamic downgrade when budget pressure rises

**Why this matters**
- parallel systems need pressure valves
- otherwise you simply replace serial slowness with parallel chaos

---

## Direct answers to your two complaints

### Complaint 1: “I give Doramagic a command, then a weak model disappears and I get no progress report.”

**Root cause**
This is not only a model problem. It is a transport and architecture problem.

- The active skill still runs `doramagic_singleshot.py`.
- The skill protocol says “show the message field exactly as-is” after script finish.
- The OpenClaw adapter itself says stdout progress “may or may not display”.

**Best solution stack**
1. Switch default entry to controller
2. Add run event bus
3. Add `dora-status` / `dora-tail`
4. Add visible todo/progress model
5. Optional: add SSE/local dashboard later

**What DeerFlow specifically teaches here**
- progress is a product surface, not a log side effect
- long-running tasks must emit structured lifecycle events
- subtask cards make users trust the system

### Complaint 2: “Doramagic is too linear; that raises failure risk and hurts efficiency.”

**Root cause**
Correct. A long waterfall accumulates risk and delay.

**Best solution stack**
1. Use DAG scheduling
2. Fan out repo workers in parallel
3. Run community and validation lanes in parallel when possible
4. Only converge at synthesis/compile/delivery
5. Add execution modes so not every run pays for the deepest path

**What DeerFlow and web-access specifically teach here**
- use isolated workers for independent work
- do not over-prescribe the route before evidence arrives
- parallelize only when tasks are truly independent
- return summaries, not raw worker histories

---

## Recommended rollout plan

### Phase 1 — 7 days
- Repoint skill entry to `doramagic_main.py`
- Add `RunEvent` schema and `run_events.jsonl`
- Add `/dora-status <run_id>`
- Expose `run_id` immediately to the user

### Phase 2 — 14 days
- Convert Phase CD into fan-out/fan-in repo workers
- Add repo worker envelopes
- Add visible todo list / progress summary
- Add Flash / Standard / Pro / Ultra modes

### Phase 3 — 30 days
- Add repo intelligence daemon/cache
- Add partial artifact exposure
- Parallelize validation/review lanes
- Add a small local dashboard

### Phase 4 — 45+ days
- Consider LangGraph-style orchestration only if the custom DAG becomes too hard to maintain
- Add long-term extraction-pattern memory
- Add cross-run analytics on where time/failure happens

---

## Final recommendation

**Do not respond to these problems by adding more stages to `doramagic_singleshot.py`.**

Instead:

1. **Promote the controller architecture you already built**
2. **Make progress transport explicit and user-visible**
3. **Turn repo extraction into isolated parallel workers**
4. **Adopt web-access’s goal-driven routing philosophy**
5. **Adopt DeerFlow’s evented, stateful, mode-based execution model**

That is the shortest path from “clever pipeline” to “serious AI system”.
