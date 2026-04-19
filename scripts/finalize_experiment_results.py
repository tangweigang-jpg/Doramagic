#!/usr/bin/env python3
"""Reverse-map blind judge verdicts and apply frozen success criteria.

Reads:
  - _runs/stage2_5/blind_manifest.json  (main-thread-only, blind→real mapping)
  - _runs/stage2_5/blind_judge_verdicts.jsonl  (opus verdicts, 36 rows)
  - _runs/stage2_5/metrics.json  (programmatic metrics)

Applies the frozen decision tree from the experiment plan:
  SUCCESS    — win rate ≥ 4/6 AND Δ cross-util ≥ 20pp AND no regression d>0.5
  PARTIAL    — win rate = 3/6 OR Δ cross-util 10–20pp
  NULL/FAIL  — win rate ≤ 2/6 AND Δ cross-util < 10pp
  REGRESSION — any task: treatment mean < baseline mean with Cohen's d > 0.5

Emits:
  _runs/stage2_5/results.json        — machine-readable verdict + per-task stats
  STEP_2_5_RESULTS.md                — human-readable report (at runs-root)

Usage:
    python3 finalize_experiment_results.py [--runs-root _runs/stage2_5]
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path


def _cohens_d(a: list[float], b: list[float]) -> float:
    """Effect size. a = treatment, b = baseline."""
    if len(a) < 2 or len(b) < 2:
        return 0.0
    mean_a = statistics.mean(a)
    mean_b = statistics.mean(b)
    var_a = statistics.variance(a) if len(a) > 1 else 0.0
    var_b = statistics.variance(b) if len(b) > 1 else 0.0
    pooled_sd = math.sqrt((var_a + var_b) / 2) if (var_a + var_b) > 0 else 0.0
    if pooled_sd == 0:
        return 0.0
    return (mean_a - mean_b) / pooled_sd


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-root", type=Path, default=Path("_runs/stage2_5"))
    args = parser.parse_args()

    manifest_path = args.runs_root / "blind_manifest.json"
    verdicts_path = args.runs_root / "blind_judge_verdicts.jsonl"
    metrics_path = args.runs_root / "metrics.json"

    for label, p in [
        ("blind_manifest", manifest_path),
        ("verdicts", verdicts_path),
        ("metrics", metrics_path),
    ]:
        if not p.exists():
            print(f"[error] {label} not found: {p}", file=sys.stderr)
            return 2

    manifest = {
        row["blind_id"]: row for row in json.loads(manifest_path.read_text(encoding="utf-8"))
    }
    verdicts = {}
    with verdicts_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            verdicts[row["blind_id"]] = row

    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))

    # Reverse-map: build (task, version) → [scores]
    scores_by_cell: dict = defaultdict(list)
    per_run: list[dict] = []
    for blind_id, meta in manifest.items():
        v = verdicts.get(blind_id)
        if v is None:
            print(f"[warn] missing verdict for {blind_id}", file=sys.stderr)
            continue
        key = (meta["task_id"], meta["version"])
        scores_by_cell[key].append(v["score"])
        per_run.append(
            {
                "blind_id": blind_id,
                "task_id": meta["task_id"],
                "version": meta["version"],
                "run_idx": meta["run_idx"],
                "score": v["score"],
                "rationale": v.get("rationale", ""),
            }
        )

    # Per-task summary
    tasks = sorted({m["task_id"] for m in manifest.values()})
    per_task: list[dict] = []
    wins = 0
    regression_tasks: list[str] = []
    for task in tasks:
        baseline_scores = scores_by_cell.get((task, "baseline"), [])
        treatment_scores = scores_by_cell.get((task, "treatment"), [])
        mean_b = statistics.mean(baseline_scores) if baseline_scores else 0.0
        mean_t = statistics.mean(treatment_scores) if treatment_scores else 0.0
        d = _cohens_d(treatment_scores, baseline_scores)
        outcome = "win" if mean_t > mean_b else ("tie" if mean_t == mean_b else "loss")
        if outcome == "win":
            wins += 1
        if outcome == "loss" and d < -0.5:
            regression_tasks.append(task)
        per_task.append(
            {
                "task_id": task,
                "baseline_scores": baseline_scores,
                "treatment_scores": treatment_scores,
                "baseline_mean": round(mean_b, 2),
                "treatment_mean": round(mean_t, 2),
                "delta_mean": round(mean_t - mean_b, 2),
                "cohens_d": round(d, 2),
                "outcome": outcome,
            }
        )

    # Cross-utilization delta (avg pp across tasks)
    delta_util_rows = metrics.get("delta_utilization", [])
    mean_delta_util = (
        round(sum(r["delta_cross_util_pp"] for r in delta_util_rows) / len(delta_util_rows), 1)
        if delta_util_rows
        else 0.0
    )

    # Apply frozen decision tree
    if regression_tasks:
        verdict = "REGRESSION"
        verdict_rationale = (
            f"Regression on tasks {regression_tasks} (Cohen's d < -0.5). "
            "Investigate stage_id watches or compat-check misses."
        )
    elif wins >= 4 and mean_delta_util >= 20:
        verdict = "SUCCESS"
        verdict_rationale = (
            f"{wins}/6 tasks won AND mean Δ cross-util = {mean_delta_util}pp ≥ 20pp. "
            "Proceed to rollout on remaining 5 MVP projects."
        )
    elif wins == 3 or 10 <= mean_delta_util < 20:
        verdict = "PARTIAL"
        verdict_rationale = (
            f"{wins}/6 wins, mean Δ cross-util {mean_delta_util}pp. "
            "Effect present but unstable. Revise selection (raise K, tighten "
            "compat check, remap WATCH stage_ids) and rerun on bp-009 before rollout."
        )
    elif wins <= 2 and mean_delta_util < 10:
        verdict = "NULL"
        verdict_rationale = (
            f"{wins}/6 wins, mean Δ cross-util {mean_delta_util}pp. "
            "Density hypothesis not supported at current injection volume. "
            "Reflect: too few items? wrong dimensions? wrong layer?"
        )
    else:
        verdict = "AMBIGUOUS"
        verdict_rationale = (
            f"{wins}/6 wins, mean Δ cross-util {mean_delta_util}pp — does not "
            "cleanly match any pre-committed bucket; treat as PARTIAL and document."
        )

    results = {
        "experiment": "stage-2.5 effectiveness validation — bp-009",
        "plan_doc": "worklogs/2026-04/2026-04-19-step-2-5-experiment-plan.md",
        "total_runs": len(per_run),
        "wins": wins,
        "regression_tasks": regression_tasks,
        "mean_delta_cross_util_pp": mean_delta_util,
        "verdict": verdict,
        "verdict_rationale": verdict_rationale,
        "per_task": per_task,
        "delta_utilization": delta_util_rows,
        "score_distribution": {
            str(s): sum(1 for r in per_run if r["score"] == s) for s in [1, 2, 3, 4, 5]
        },
    }

    (args.runs_root / "results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Build human-readable report
    lines: list[str] = []
    lines.append("# Step 2.5 Effectiveness Validation — Results")
    lines.append("")
    lines.append("**Experiment**: bp-009 baseline vs treatment crystal")
    lines.append("**Plan doc**: `worklogs/2026-04/2026-04-19-step-2-5-experiment-plan.md`")
    lines.append(f"**Total runs**: {len(per_run)} (6 tasks × 2 versions × 3 runs)")
    lines.append("")
    lines.append(f"## Verdict: **{verdict}**")
    lines.append("")
    lines.append(f"> {verdict_rationale}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Per-task score table")
    lines.append("")
    lines.append(
        "| Task | Baseline scores | Treatment scores | Baseline mean | "
        "Treatment mean | Δ | Cohen's d | Outcome |"
    )
    lines.append("|---|---|---|---|---|---|---|---|")
    for row in per_task:
        lines.append(
            f"| {row['task_id']} | {row['baseline_scores']} | "
            f"{row['treatment_scores']} | {row['baseline_mean']} | "
            f"{row['treatment_mean']} | {row['delta_mean']:+.2f} | "
            f"{row['cohens_d']:+.2f} | {row['outcome'].upper()} |"
        )
    lines.append("")
    lines.append(f"**Wins**: {wins}/6")
    lines.append("")

    lines.append("## Cross-utilization (treatment − baseline, pp)")
    lines.append("")
    lines.append("| Task | Baseline % | Treatment % | Δ |")
    lines.append("|---|---|---|---|")
    for d in delta_util_rows:
        lines.append(
            f"| {d['task_id']} | {d['baseline_cross_util_rate'] * 100:.0f}% | "
            f"{d['treatment_cross_util_rate'] * 100:.0f}% | "
            f"{d['delta_cross_util_pp']:+.1f}pp |"
        )
    lines.append(f"\n**Mean Δ cross-util**: {mean_delta_util:+.1f}pp")
    lines.append("")

    lines.append("## Score distribution (all 36 runs)")
    lines.append("")
    lines.append("| Score | Count |")
    lines.append("|---|---|")
    for s in [1, 2, 3, 4, 5]:
        lines.append(f"| {s} | {results['score_distribution'][str(s)]} |")
    lines.append("")

    lines.append("## Per-run detail (reverse-mapped from blind ids)")
    lines.append("")
    lines.append("| Blind ID | Task | Version | Run | Score | Rationale |")
    lines.append("|---|---|---|---|---|---|")
    for r in sorted(per_run, key=lambda x: (x["task_id"], x["version"], x["run_idx"])):
        rat = r["rationale"].replace("|", "\\|")
        lines.append(
            f"| {r['blind_id']} | {r['task_id']} | {r['version']} | "
            f"r{r['run_idx']} | {r['score']} | {rat} |"
        )
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Follow-up actions (per frozen decision tree)")
    lines.append("")
    if verdict == "SUCCESS":
        lines.append(
            "- Roll selection pipeline to the remaining 5 MVP projects\n"
            "- Capture lessons to memory (what worked, which domains generalize)"
        )
    elif verdict == "PARTIAL":
        lines.append(
            "- Do NOT roll out. Revise selection rubric\n"
            "- Candidate fixes: raise K, tighten compat check, "
            "remap WATCH stage_ids, weight injection toward crystal-unique IDs"
        )
    elif verdict == "NULL":
        lines.append(
            "- Accept null result. Reflect whether the lever is K, or "
            "dimensions, or the layer of injection. Do not re-run without "
            "a redesigned hypothesis."
        )
    elif verdict == "REGRESSION":
        lines.append(
            "- Stop. Investigate WATCH stage_id misrouting the host. "
            "Fix selection pipeline to remap stage_ids before injection."
        )
    else:
        lines.append("- Treat as PARTIAL; document boundary case.")

    (Path.cwd() / args.runs_root / "STEP_2_5_RESULTS.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )

    print(f"[done] results.json:        {args.runs_root / 'results.json'}")
    print(f"[done] STEP_2_5_RESULTS.md: {args.runs_root / 'STEP_2_5_RESULTS.md'}")
    print(f"\nVerdict: {verdict}")
    print(f"  wins: {wins}/6")
    print(f"  mean Δ cross-util: {mean_delta_util:+.1f}pp")
    print(f"  regression tasks: {regression_tasks or 'none'}")
    print("\nPer-task outcomes:")
    for row in per_task:
        print(
            f"  {row['task_id']}: baseline={row['baseline_mean']:.2f} "
            f"treatment={row['treatment_mean']:.2f} "
            f"Δ={row['delta_mean']:+.2f} d={row['cohens_d']:+.2f} "
            f"{row['outcome'].upper()}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
