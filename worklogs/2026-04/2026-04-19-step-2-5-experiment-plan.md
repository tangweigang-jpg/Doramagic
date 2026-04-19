# Step 2.5 Effectiveness Experiment Plan — bp-009 baseline vs treatment

**Status**: plan frozen pre-execution (2026-04-19)
**Owner**: Doramagic CTO path (main thread)
**Expected runtime**: ~1.2 days end-to-end

---

## 0. North-Star Question

**Does injecting 10 curated domain constraints + 10 curated domain Python packages into bp-009's crystal produce measurably better downstream-skill outputs on zvt-realistic tasks?**

This is the validation gate for the entire Stage 1 + Stage 2 domain-knowledge pipeline. A clear positive result justifies rollout to the other 5 MVP projects; a clear negative result forces a strategy redesign.

- **H0**: No measurable difference between baseline and treatment crystals on primary quality score.
- **H1**: Treatment produces measurably better outputs on ≥ 4 of 6 tasks (direction + magnitude defined in §5).

---

## 1. Experimental Variables

| Variable | Baseline | Treatment |
|---|---|---|
| Crystal `seed.yaml` | `finance-bp-009-v5.3.seed.yaml`  <br>147 constraints / 10 packages / 3316 lines | `finance-bp-009-v5.3-treatment.seed.yaml`  <br>157 constraints / 20 packages / 3491 lines |
| Downstream host model | `claude-sonnet-4-6` | `claude-sonnet-4-6` |
| Judge model (blinded) | `claude-opus-4-7` | `claude-opus-4-7` |
| Temperature (downstream) | 0.7 | 0.7 |
| Runs per (task, version) | 3 | 3 |

**Controls**:
- Blinded judgment — judge sees only `(task, code_output)`, never `seed.yaml` nor version label
- Identical task wording and system prompt across versions
- Random-shuffled order for judge consumption; main thread maintains reverse mapping
- Same prompt template for downstream code generation regardless of version

**Why sonnet as downstream** (per CEO directive): opus is too expensive for 36 runs. More importantly, MVP validates whether crystal provides lift to a medium-capability host — if opus already writes correct code unaided, the crystal's marginal value is invisible.

---

## 2. Tasks (6 total, covering all 10 injected constraints and 4 high-value resources)

Task wording below is the **exact prompt** given to the downstream model (no hints about "look-ahead", "sqrt(252)", etc. — host must surface these from the crystal).

| # | Task prompt | Domain knowledge under test |
|---|---|---|
| **T1** | "Write a Python function that computes 20-day rolling volatility from a pandas Series of daily close prices, returning an annualized figure as a Series." | `C-9005` sqrt(252) · `C-9006` NaN warmup handling |
| **T2** | "Implement a backtesting entry-signal function given a Series of indicator values. Output buy/sell signals aligned to the price index with correct temporal handling." | `C-9001` shift(-period) · `C-9002` 1-period lag · `C-9003` warmup ≥ lookback |
| **T3** | "Build an incremental market-data collector that fetches only new records since the last stored date and handles upstream API failures gracefully." | `C-9004` None-fallback · `C-9010` chronological OHLCV · resource: `exchange-calendars` |
| **T4** | "Split a time-indexed feature dataset into train/validation/test sets for a stock-return ML model, then train a baseline regressor and print validation metrics." | `C-9007` temporal split · resources: `scikit-learn`, `lightgbm` |
| **T5** | "Write an order-execution function that places a new trade and validates the resulting position state before returning." | `C-9008` position finiteness · `C-9009` positive order size |
| **T6** | "Generate a performance tearsheet for a daily-returns Series: annualized Sharpe, max drawdown, rolling 60-day Sharpe, return histogram. Output as a single Python function." | `C-9005` sqrt(252) (cross-check) · resources: `empyrical-reloaded`, `pyfolio-reloaded` |

**Coverage**:
- All 10 injected constraints exercised at least once
- 4 of 10 injected resources have a task-level utility gate (`exchange-calendars`, `scikit-learn`, `lightgbm`, `empyrical-reloaded` / `pyfolio-reloaded`)
- The remaining 6 resources (`scipy`, `statsmodels`, `numba`, `beautifulsoup4`, `lxml`) are not directly provoked; their utilization is incidental-only

---

## 3. Execution Protocol

For each `(task, version, run_idx)` in the 36-run grid:

1. **Prompt construction** (main thread):
   ```
   System: You are a Python engineer implementing ZVT-style quant infrastructure.
           Before writing any code, consult the attached crystal contract (seed.yaml).
           The crystal lists constraints you must respect and resources you may use.
   User:   <task prompt from §2>
   Attachment: {baseline.seed.yaml | treatment.seed.yaml}
   ```

2. **Execution** (sonnet subagent, temperature 0.7):
   - Produces code response
   - Main thread persists response to `_runs/stage2_5/{task}-{version}-r{idx}/output.py` plus `prompt.txt` and `metadata.json`

3. **Shuffle + judge** (after all 36 runs complete):
   - Main thread shuffles the 36 outputs, assigns each a random `blind_id`
   - Judge (opus subagent) receives `(task, output, blind_id)` only — no version label, no seed
   - Judge returns `(blind_id, score_1_to_5, rationale)` per output
   - Main thread reverses the shuffle to recover `(task, version, run_idx) → score`

4. **Programmatic metrics** (main thread, no LLM):
   - `utilization` — for each output: does it mention or import any injected constraint/resource? Boolean per (task, output, injected_item).
   - `parse_pass` — `ast.parse(output_code)` returns True?
   - `output_tokens` — len of response

---

## 4. Primary Scoring Rubric (for judge)

```
Score each code output on a 1-5 scale:

1 — Wrong or non-runnable. Misses the task's basic intent.
2 — Runnable but has a classic pitfall (look-ahead bias, NaN not handled,
    wrong annualization constant, missing validation, etc.)
3 — Correct for the literal task; no visible pitfalls; does not reflect
    domain best-practice.
4 — Correct + shows some domain-idiomatic choices (e.g., preserves index,
    uses sqrt(252), checks for None upstream).
5 — Correct + domain-complete: proper convention, defensive handling,
    uses appropriate specialized library where it helps.

Do NOT infer which crystal produced the output. Score only the code
against the task.
```

---

## 5. Success Criteria (decision tree)

| Outcome | Conditions (ALL must hold) | Downstream action |
|---|---|---|
| **SUCCESS** | Win rate ≥ 4/6 tasks (treatment mean > baseline mean per task)<br>AND Δ utilization rate ≥ 20pp<br>AND no single task regresses with Cohen's d > 0.5 | Roll pipeline out to other 5 MVP projects |
| **PARTIAL** | Win rate = 3/6 OR Δ utilization 10–20pp | Do not roll out; revise selection rubric (raise K, tighten compat check, re-map WATCH stage_ids) and rerun on bp-009 |
| **NULL / FAIL** | Win rate ≤ 2/6 AND Δ utilization < 10pp | Accept null result. Density hypothesis not supported at current injection volume. Investigate: too few items? wrong dimensions? inject at different layer? |
| **REGRESSION** | Any task: treatment mean < baseline mean with Cohen's d > 0.5 | Stop; treatment introduces confusion. Likely root cause: 8 WATCH stage_id mismatches silently steering the host. Fix: add stage_id remapping to finalize pipeline. |

**Why not p < 0.05**: n = 6 runs per cell (2 versions × 3 runs) per task is below the threshold for meaningful p-values. The experiment is powered for **direction + effect size + knowledge-utilization traceability**, not classical hypothesis testing. Decisions hinge on replication across the 5 remaining MVP projects, not one-shot significance.

---

## 6. Execution Schedule

| Step | Artifact | Est. time |
|---|---|---|
| 6a | `scripts/run_effectiveness_experiment.py` — orchestrates 36 runs via sonnet subagents, persists `_runs/stage2_5/` structure | 2h |
| 6b | Execute 36 runs | ~1h wall-clock (subagent latency) |
| 6c | `scripts/score_experiment_outputs.py` — builds blinded judge task, parses verdicts, computes metrics | 1.5h |
| 6d | Execute judging + programmatic scoring | ~45 min |
| 6e | `STEP_2_5_RESULTS.md` — consolidated report: per-task scores, win rate, utilization delta, decision verdict | 0.5h |
| **Total** | — | **~1 day + buffer** |

---

## 7. Failure-Mode Handling (pre-committed responses, to remove post-hoc bias)

| Observed | Pre-committed response |
|---|---|
| Both versions have `utilization < 20%` overall | Host is ignoring seed.yaml; augment system prompt to force seed consultation; rerun 6 additional calibration runs before full experiment |
| Treatment wins but only on T1/T6 (sqrt-252 tasks) | Likely cherry-picking by annualization — down-weight that finding; re-examine T2/T3/T5 (the harder domain-judgment tasks) for the real signal |
| Baseline beats treatment on T2 or T3 | Red flag — investigate whether WATCH stage_ids are misrouting the host. If yes, treatment is not currently shippable; Stage 2.3.5 must include stage_id remapping |
| Outputs fail `ast.parse` on > 20% of runs | Raise temperature issue or prompt stability issue — not a crystal-quality signal; rerun with adjustments |

---

## 8. Post-Experiment Deliverables (non-negotiable)

1. `_runs/stage2_5/` — raw run directory (36 outputs + prompts + metadata + per-run judge verdicts)
2. `STEP_2_5_RESULTS.md` — report with scorecard, utilization table, verdict, and follow-up actions per §5
3. Memory update — lesson captured into the auto-memory system (e.g., what the real signal was, what we'd change in selection for project #2)

---

## 9. What This Experiment Does Not Answer

- **Portability** — Does the selection pipeline work on projects *not* similar to zvt? Answered by the 5 other MVP projects, not this experiment.
- **Long-horizon skill quality** — Does knowledge injection help in multi-turn skill usage? Out of scope; this is one-shot code generation.
- **User preference** — Do humans prefer treatment outputs? Out of scope; LLM judge is the MVP proxy.
- **Optimal K** — Is 10+10 the right injection size? If SUCCESS, next experiment can grid-search K. If NULL, K may not be the lever at all.

---

## 10. Decision Record

- 2026-04-19: Plan frozen. Executor will not adjust tasks, K, or success criteria after this point without a new plan revision to keep results honest.

---

*This document is the single source of truth for Step 2.5. Any deviation during execution must be recorded as an addendum, not a silent change.*
