# Step 2.5 Effectiveness Validation — Results (Archival)

**Date**: 2026-04-19
**Experiment**: bp-009 baseline crystal vs treatment crystal (domain-injected)
**Plan reference**: [2026-04-19-step-2-5-experiment-plan.md](./2026-04-19-step-2-5-experiment-plan.md)
**Raw outputs**: `_runs/stage2_5/` (36 outputs, metrics, verdicts — untracked artifacts)

---

## TL;DR

**Verdict: REGRESSION**

- Wins: **3/6** (T2, T4, T6) — with large effect sizes (Cohen's d +0.58 to +3.27)
- Losses: **3/6** (T1, T3, T5) — all crossed regression threshold (d ≤ -0.5), T5 severe (d = -1.63)
- Mean Δ cross-utilization: **+44.4pp** (treatment clearly consulted the crystal — signal is real, but not all of it helps)

**The density hypothesis is NOT supported as originally formulated**. Blindly unioning curated "universal" domain knowledge on top of a mature project crystal can *regress* outputs on tasks where the project already has surgical-precision coverage.

---

## What actually happened (per task)

| Task | Baseline → Treatment | Outcome | Why |
|---|---|---|---|
| T1 rolling_volatility | 3.67 → 3.33 | LOSS (d=-0.58) | Baseline already used `sqrt(252)` + `min_periods`; treatment minimal impl shed defensive checks |
| T2 backtest_entry_signal | 2.67 → 4.00 | **WIN** (d=+3.27) | Baseline lacked explicit execution lag; treatment enforced `shift(1)` lag + MultiIndex via C-9002 |
| T3 incremental_collector | 5.00 → 4.33 | LOSS (d=-0.82) | Baseline had retries + MAX(ts) + MultiIndex (project excels here); treatment r1 *dropped retry logic* to follow generic "handle failures" language |
| T4 ml_temporal_split | 4.33 → 4.67 | WIN (d=+0.58) | Treatment added `SplitBoundary` dataclass + LightGBM + temporal asserts via C-9007 |
| T5 order_execution | 5.00 → 4.33 | **LOSS severe** (d=-1.63) | Baseline had T+1 + invariant checker + BD-101 floor-div — ZVT's SL-05/06 already surgical. Treatment's C-9008/C-9009 offered shallower `isfinite` / positive-size checks, **diluting** the project-specific tightness |
| T6 performance_tearsheet | 4.00 → 4.67 | WIN (d=+0.82) | Treatment added explicit `sqrt(252)` + OV-05 drawdown guard + `min_periods=window` via C-9005/9006 |

---

## The real finding (boundary condition for density hypothesis)

Density injection is **not uniformly useful**. Two regimes:

**Regime A — Injection helps** (T2, T4, T6 won):
- Project's coverage in that dimension is **sparse or generic**
- Injected rules provide concrete, actionable patterns the host otherwise lacks
- Cross-util rate goes from ~0% → 100%

**Regime B — Injection hurts** (T1, T3, T5 lost):
- Project already has **surgical-precision constraints + spec_locks** covering the task
- Injected domain rules are "generic good advice" that dilutes the project's tight conventions
- The host, facing two descriptions, averages toward the looser/universal one

**This was GPT's prediction in the pre-experiment review**: "domain constraints must go through an adaptation layer, not direct union injection". The experiment confirmed it — with the exact regressions we expected but hoped wouldn't materialize.

---

## Why the pre-committed decision tree matters

The plan document (§5) pre-committed to these branches. When the data came back REGRESSION, there was zero room for:
- "Well, T2/T4/T6 won, so overall the experiment is positive"
- "The regression tasks are edge cases; focus on the wins"
- "Let's broaden the criteria to call this PARTIAL"

All three of those post-hoc rationalizations were vetoed by the frozen decision tree. The result stands as-is: REGRESSION, do not roll out, fix selection pipeline before trying again.

---

## Decision (per §7 pre-committed response)

> **"Stop; treatment introduces confusion. Likely root cause: 8 WATCH stage_id mismatches silently steering the host. Fix: add stage_id remapping to finalize pipeline."**

More precisely, the follow-up (Stage 2 v2 redesign):
1. **Coverage-density detector** — before injecting, check whether the project already has a precise constraint/spec_lock covering the same behavior. If yes, skip injection (or require the domain rule to *strengthen* rather than *add*).
2. **stage_id remapping** — for the 8 WATCH rules, map source-BP stage names to target-project stage names; currently they silently lose the stage-overlap signal.
3. **Semantic adaptation, not syntactic dedup** — id renumbering was necessary but insufficient. The `when` and `action` text of injected rules must be rewritten to match the target runtime's vocabulary and conventions.

---

## What this does not mean

- **Not** that the selection pipeline is fundamentally broken — Stages 2.1 through 2.4 worked; the gap is at the adaptation layer (missing Stage 2.3.5.5 or 2.4.5).
- **Not** that density is irrelevant — T2/T4/T6 show real lift when the match regime is right.
- **Not** that opus was biased — blinded scoring + shuffled order eliminates confirmation bias; the 5-level score distribution (0-1-7-13-15) shows the judge used the full scale.

---

## Raw artifacts (under `_runs/stage2_5/`, untracked)

| File | Content |
|---|---|
| `plan.json` | Manifest of 36 runs + metadata |
| `tasks/T{1..6}/{baseline,treatment}/r{1..3}/output.py` | Generated code per cell |
| `metrics.json` | Per-run parse/util metrics + aggregates + Δ util |
| `blind_manifest.json` | Main-thread-only reverse map (blind_id → version) |
| `blind_judge_tasks.md` | Judge's input (no version labels) |
| `blind_judge_verdicts.jsonl` | 36 opus scores + rationales |
| `results.json` | Reverse-mapped per-task stats + frozen-tree verdict |
| `STEP_2_5_RESULTS.md` | Auto-generated report with per-run detail |

---

## Closing note

A clean negative result on Day 1 is worth more than a contaminated positive result on Day 5. The pipeline produced signal clean enough to refute its own formulation. That's the mark of a working experimental apparatus, even when the bet doesn't pay off.

Next session: redesign selection v2 with the coverage-density + stage_id remap fixes.
