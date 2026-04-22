# Research Prompt: Extracting Business Logic from Open-Source Projects for AI Knowledge Compilation

## Background

We are building **Doramagic**, a knowledge compilation system that extracts structured knowledge from GitHub open-source projects and compiles it into "seed crystals" — self-contained instruction documents that guide AI agents to build complete working systems.

**Current two-layer architecture:**

1. **Blueprints** (59 extracted, from 59 open-source projects): Describe the *framework architecture* — how a software system is structured. Extracted from source code by tracing `@abstractmethod`, main loops, data flows, and module boundaries. Example: from `zipline-reloaded`, we extracted "event-driven backtesting system with Pipeline API, DataPortal, and bar-by-bar event loop."

2. **Constraints** (3,257 extracted): Describe *what can go wrong* — technical guardrails that prevent known bugs and failures. Extracted from source code, tests, and issues. Example: "When processing BAR events, MUST execute blotter.get_transactions() before calling handle_data(), otherwise look-ahead bias occurs."

**The system works**: We successfully compiled a seed crystal from blueprint + constraints, sent it to an AI agent (MiniMax-M2.7 via OpenClaw/Telegram), and the agent autonomously wrote and executed a working A-stock momentum factor backtest — correct code, correct results, delivered end-to-end in 6 minutes.

## The Problem We Discovered

After 5 iterations of testing (v5→v9), we realized our seed crystals are missing a critical third layer: **business logic**.

Our blueprints answer: *"How does this framework work internally?"*
Our constraints answer: *"What mistakes must be avoided?"*
But neither answers: *"What specific things can you BUILD with this framework?"*

### Concrete example of the gap

**What zipline-reloaded's source code actually contains:**
- 20+ built-in factors: `SimpleMovingAverage`, `RSI`, `VWAP`, `BollingerBands`, `Returns`, `MACD`, `AverageDollarVolume`...
- Multiple commission models: `PerShare`, `PerTrade`, `PerContract`
- Pipeline API for cross-sectional stock screening
- `examples/` directory with complete strategy implementations
- Notebooks showing end-to-end research workflows

**What our blueprint extracted:**
- "Built-in 20+ factors: SMA, EWMA, VWAP, RSI, MACD, BollingerBands, Returns..." (one line)
- Commission models listed as "replaceable points" (option names only)
- Pipeline described as architectural component (how it works, not what to do with it)

**What was actually needed to make the crystal work (v9):**
We had to **manually hardcode** the complete business logic into the crystal's directive:
- Specific strategy: 20-day momentum factor cross-sectional stock screening
- Specific stock pool: 20 fixed A-stock tickers
- Specific parameters: TOP_N=5, MOMENTUM_WINDOW=20
- Specific data source API calls: exact `baostock.query_history_k_data_plus()` syntax
- Specific output format: `ANNUAL_RETURN=xx% MAX_DRAWDOWN=xx% SHARPE=xx`

None of this came from the blueprint or constraints. **The blueprint told the AI how zipline works; the hand-written directive told it what to actually build.**

### Another example: a friend's crystal

A friend independently wrote a crystal for "High Turnover Rate Event Study" that contained rich business logic:
- Stage 1: Filter stocks with turnover > X%, take top N per day
- Stage 2: Extract post-event performance (10 trading days, cumulative return, max drawdown, amplitude)
- Stage 3: Statistical analysis (win rate, profit/loss ratio, grouped by turnover brackets)
- Stage 4: Strategy recommendations (optimal holding period, stop-loss suggestions)

This is exactly the kind of **domain-specific research methodology** that our system cannot generate — because we never extracted it.

## What We Need: The Missing Third Layer

We need to extract a third type of knowledge from open-source projects. We're tentatively calling it **"Patterns"** or **"Recipes"** — concrete, reusable descriptions of *what specific problems can be solved* using a given framework, and *how to solve them step by step*.

### Where this knowledge lives in GitHub projects

| Source | What it contains | Example |
|--------|-----------------|---------|
| `examples/` | Complete strategy implementations | Momentum strategy, mean reversion, pairs trading |
| `docs/tutorials/` | Step-by-step research workflows | "Build your first factor model" |
| `notebooks/` | End-to-end research cases with real data | Jupyter notebooks with visualizations |
| README Quick Start | Minimal working example | "Run a simple backtest in 10 lines" |
| Source code (built-in components) | Reusable building blocks with domain semantics | Built-in factors, indicators, scoring models |
| Test fixtures | Realistic usage scenarios | Integration tests that exercise full workflows |

### The three-layer architecture we want

```
Blueprint (framework architecture)  →  "How does this tool work?"
   +
Pattern (business logic / recipe)   →  "What can you build with it?"
   +
Constraint (technical guardrails)   →  "What mistakes to avoid?"
   ↓
Compiled Seed Crystal               →  Complete AI execution instructions
```

**One blueprint can combine with many patterns** to produce different crystals:
- Blueprint `zipline` + Pattern `momentum-factor-screening` → Crystal for momentum backtest
- Blueprint `zipline` + Pattern `event-study` → Crystal for event-driven analysis
- Blueprint `zipline` + Pattern `pairs-trading` → Crystal for pairs trading

## Research Questions

Please investigate and provide recommendations on:

### Q1: Pattern Schema Design
What should the structured schema for a "Pattern" look like? Consider:
- What fields are needed to fully describe a business logic pattern?
- How to link patterns to blueprints (one pattern may apply to multiple frameworks)?
- How to parameterize patterns (e.g., "momentum strategy" with configurable window, threshold)?
- How to express the step-by-step research methodology (stages, inputs, outputs, validation criteria)?
- How to handle domain-specific vocabulary (finance: factors, signals, positions; ML: features, models, metrics)?

### Q2: Extraction Methodology
How should we extract patterns from open-source projects? Consider:
- What are the best source materials (examples vs. notebooks vs. docs vs. source code)?
- Should extraction be automated (code analysis), semi-automated (LLM-assisted), or manual?
- How to identify the boundary of a single "pattern" (one example file might contain multiple patterns)?
- How to extract parameters vs. hardcoded values (what's configurable vs. what's fixed)?
- How to handle the spectrum from simple patterns (10-line quick start) to complex patterns (100-line research workflow)?

### Q3: Pattern-Blueprint Binding
How should patterns relate to blueprints in the compilation process? Consider:
- Should patterns be blueprint-specific or cross-blueprint (e.g., "momentum strategy" works in both zipline and backtrader)?
- How does the compiler merge blueprint architecture + pattern business logic + constraints into a crystal?
- How to resolve conflicts (pattern assumes feature X, but constraint says X is forbidden in this environment)?

### Q4: Quality & Coverage
How to ensure pattern quality and coverage? Consider:
- What makes a "good" pattern vs. a "bad" one?
- How many patterns per blueprint is a reasonable target?
- How to prioritize which patterns to extract first (popularity? complexity? user demand)?
- How to validate that an extracted pattern is correct and complete?

### Q5: Prior Art & Alternatives
Are there existing systems or research that solve similar problems? Consider:
- Code generation systems that use example-based knowledge
- Recipe/cookbook systems in software engineering
- Retrieval-augmented generation (RAG) with code examples
- Specification languages for domain-specific workflows
- Any relevant papers on extracting reusable patterns from codebases

## Constraints on Your Recommendations

- Patterns must be **machine-readable** (not free-text prose) — they will be consumed by a compiler
- Patterns must be **composable** with our existing blueprint + constraint system
- Extraction must be **scalable** — we have 59 projects, potentially hundreds of patterns
- The system targets **AI agents as consumers** — patterns guide LLMs, not human developers
- Domain focus is **quantitative finance** for now, but the architecture should generalize

## Deliverable

Please provide a structured research report with:
1. Recommended Pattern schema (with field definitions and examples)
2. Extraction methodology (step-by-step process)
3. Compilation integration strategy (how patterns fit into the compiler)
4. Prioritized implementation plan
5. Risks and open questions
