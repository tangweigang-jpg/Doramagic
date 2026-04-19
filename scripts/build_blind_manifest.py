#!/usr/bin/env python3
"""Build blinded judgment manifest for stage-2.5.

Shuffles the 36 outputs, assigns each a random blind_id, and writes
_runs/stage2_5/blind_manifest.json with {blind_id → output_path mapping} plus
a mirror file blind_judge_tasks.md that the opus subagent will consume (it
sees only task prompt + code, not version or seed).

The mapping is kept private — judge never reads blind_manifest.json; only
the main thread uses it to reverse-map scores after judging.

Usage:
    python3 build_blind_manifest.py [--runs-root _runs/stage2_5] [--seed 42]
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

_TASK_PROMPTS: dict[str, str] = {
    "T1": (
        "Compute 20-day rolling volatility from a pandas Series of daily close "
        "prices, returning an annualized figure as a Series."
    ),
    "T2": (
        "Implement a backtesting entry-signal function given a Series of "
        "indicator values. Output buy/sell signals aligned to the price "
        "index with correct temporal handling."
    ),
    "T3": (
        "Build an incremental market-data collector that fetches only new "
        "records since the last stored date and handles upstream API "
        "failures gracefully."
    ),
    "T4": (
        "Split a time-indexed feature dataset into train/validation/test sets "
        "for a stock-return ML model, then train a baseline regressor and "
        "print validation metrics."
    ),
    "T5": (
        "Write an order-execution function that places a new trade and "
        "validates the resulting position state before returning."
    ),
    "T6": (
        "Generate a performance tearsheet for a daily-returns Series: "
        "annualized Sharpe, max drawdown, rolling 60-day Sharpe, return "
        "histogram. Output as a single Python function."
    ),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-root", type=Path, default=Path("_runs/stage2_5"))
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    plan_path = args.runs_root / "plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))

    rng = random.Random(args.seed)
    runs = list(plan["runs"])
    rng.shuffle(runs)

    blind_manifest: list[dict] = []
    judge_chunks: list[str] = []
    for blind_idx, run_meta in enumerate(runs, 1):
        blind_id = f"B{blind_idx:02d}"
        output_path = Path(run_meta["output_path"])
        code = output_path.read_text(encoding="utf-8")
        blind_manifest.append(
            {
                "blind_id": blind_id,
                "task_id": run_meta["task_id"],
                "version": run_meta["version"],
                "run_idx": run_meta["run_idx"],
                "output_path": str(output_path),
            }
        )
        chunk = (
            f"## {blind_id} — Task {run_meta['task_id']}\n\n"
            f"**Task**: {_TASK_PROMPTS[run_meta['task_id']]}\n\n"
            f"**Code**:\n\n```python\n{code}\n```\n"
        )
        judge_chunks.append(chunk)

    (args.runs_root / "blind_manifest.json").write_text(
        json.dumps(blind_manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    header = (
        "# Stage-2.5 Blind Judgment Input\n\n"
        "You are scoring 36 independent Python implementations against six "
        "tasks. The outputs are pre-shuffled — you DO NOT know which crystal "
        "produced each one; judge on the code alone.\n\n"
        "## Scoring rubric (1-5)\n\n"
        "- **1** — Wrong or non-runnable. Misses the task's basic intent.\n"
        "- **2** — Runnable but has a classic pitfall (look-ahead bias, NaN "
        "not handled, wrong annualization constant, missing validation, "
        "etc.).\n"
        "- **3** — Correct for the literal task; no visible pitfalls; does "
        "not reflect domain best-practice.\n"
        "- **4** — Correct + shows some domain-idiomatic choices (preserves "
        "index, uses sqrt(252), checks for None upstream, etc.).\n"
        "- **5** — Correct + domain-complete: proper conventions, defensive "
        "handling, uses appropriate specialized library where it helps.\n\n"
        "**Do NOT infer which crystal/version produced the output. Score only "
        "the code against the task.**\n\n"
        "---\n\n"
    )
    (args.runs_root / "blind_judge_tasks.md").write_text(
        header + "\n".join(judge_chunks), encoding="utf-8"
    )

    print(f"[done] blind_manifest.json: {args.runs_root / 'blind_manifest.json'}")
    print(f"[done] blind_judge_tasks.md: {args.runs_root / 'blind_judge_tasks.md'}")
    print(f"       {len(blind_manifest)} shuffled outputs prepared")
    return 0


if __name__ == "__main__":
    sys.exit(main())
