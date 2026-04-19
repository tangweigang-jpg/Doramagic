#!/usr/bin/env python3
"""Setup Stage-2.5 effectiveness experiment: materialize run directories + prompts.

Creates the directory tree and prompt files for the bp-009 baseline-vs-treatment
effectiveness validation (see worklogs/2026-04/2026-04-19-step-2-5-experiment-plan.md).

Does NOT call any LLM. Subagent execution is orchestrated by the main thread
(which reads each prompt.txt and seed.yaml, produces code, writes output.py
to the same run dir).

Output tree (under --output-root, default _runs/stage2_5/):
    plan.json                                — full run manifest + metadata
    tasks/{T1..T6}/{baseline|treatment}/r{1..3}/prompt.txt
    tasks/{T1..T6}/{baseline|treatment}/r{1..3}/metadata.json

Usage:
    python3 setup_effectiveness_experiment.py \\
        [--baseline-seed <path>] \\
        [--treatment-seed <path>] \\
        [--output-root <dir>] \\
        [--runs-per-cell 3]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

# ============================================================
# Task definitions (the single source of truth for the 6 tasks)
# ============================================================

TASKS: list[dict] = [
    {
        "id": "T1",
        "slug": "rolling_volatility",
        "prompt": (
            "Write a Python function that computes 20-day rolling volatility "
            "from a pandas Series of daily close prices, returning an "
            "annualized figure as a Series."
        ),
        "covers_constraints": ["finance-C-9005", "finance-C-9006"],
        "covers_resources": [],
    },
    {
        "id": "T2",
        "slug": "backtest_entry_signal",
        "prompt": (
            "Implement a backtesting entry-signal function given a Series of "
            "indicator values. Output buy/sell signals aligned to the price "
            "index with correct temporal handling."
        ),
        "covers_constraints": [
            "finance-C-9001",
            "finance-C-9002",
            "finance-C-9003",
        ],
        "covers_resources": [],
    },
    {
        "id": "T3",
        "slug": "incremental_collector",
        "prompt": (
            "Build an incremental market-data collector that fetches only new "
            "records since the last stored date and handles upstream API "
            "failures gracefully."
        ),
        "covers_constraints": ["finance-C-9004", "finance-C-9010"],
        "covers_resources": ["exchange-calendars"],
    },
    {
        "id": "T4",
        "slug": "ml_temporal_split",
        "prompt": (
            "Split a time-indexed feature dataset into train/validation/test "
            "sets for a stock-return ML model, then train a baseline "
            "regressor and print validation metrics."
        ),
        "covers_constraints": ["finance-C-9007"],
        "covers_resources": ["scikit-learn", "lightgbm"],
    },
    {
        "id": "T5",
        "slug": "order_execution",
        "prompt": (
            "Write an order-execution function that places a new trade and "
            "validates the resulting position state before returning."
        ),
        "covers_constraints": ["finance-C-9008", "finance-C-9009"],
        "covers_resources": [],
    },
    {
        "id": "T6",
        "slug": "performance_tearsheet",
        "prompt": (
            "Generate a performance tearsheet for a daily-returns Series: "
            "annualized Sharpe, max drawdown, rolling 60-day Sharpe, return "
            "histogram. Output as a single Python function."
        ),
        "covers_constraints": ["finance-C-9005"],
        "covers_resources": ["empyrical-reloaded", "pyfolio-reloaded"],
    },
]

VERSIONS: list[str] = ["baseline", "treatment"]


SYSTEM_PROMPT = (
    "You are a Python engineer implementing ZVT-style quant infrastructure.\n"
    "Before writing any code, CONSULT the attached crystal contract "
    "(seed.yaml at {seed_path}).\n"
    "The crystal lists constraints you MUST respect (constraints.fatal[] and "
    "constraints.regular[]) and resources you MAY use (resources.packages[]).\n"
    "Your output must be a single Python function, fully self-contained, with "
    "imports at the top. Include brief docstrings, no markdown fences, no "
    "narration — code only."
)


def _build_prompt_file(task: dict, seed_path: Path) -> str:
    system = SYSTEM_PROMPT.format(seed_path=str(seed_path))
    return (
        "## System\n\n"
        + system
        + "\n\n"
        + "## User\n\n"
        + task["prompt"]
        + "\n\n"
        + "## Context\n\n"
        + f"Crystal seed.yaml is at: {seed_path}\n"
        + "Read it before writing code.\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--baseline-seed",
        type=Path,
        default=Path("knowledge/sources/finance/finance-bp-009--zvt/finance-bp-009-v5.3.seed.yaml"),
    )
    parser.add_argument(
        "--treatment-seed",
        type=Path,
        default=Path(
            "knowledge/sources/finance/finance-bp-009--zvt/finance-bp-009-v5.3-treatment.seed.yaml"
        ),
    )
    parser.add_argument("--output-root", type=Path, default=Path("_runs/stage2_5"))
    parser.add_argument("--runs-per-cell", type=int, default=3)
    args = parser.parse_args()

    for label, p in [
        ("baseline-seed", args.baseline_seed),
        ("treatment-seed", args.treatment_seed),
    ]:
        if not p.exists():
            print(f"[error] {label} not found: {p}", file=sys.stderr)
            return 2

    seed_for_version: dict[str, Path] = {
        "baseline": args.baseline_seed.resolve(),
        "treatment": args.treatment_seed.resolve(),
    }

    args.output_root.mkdir(parents=True, exist_ok=True)

    manifest_runs: list[dict] = []
    for task in TASKS:
        for version in VERSIONS:
            for run_idx in range(1, args.runs_per_cell + 1):
                run_dir = args.output_root / "tasks" / task["id"] / version / f"r{run_idx}"
                run_dir.mkdir(parents=True, exist_ok=True)

                prompt_text = _build_prompt_file(task, seed_for_version[version])
                (run_dir / "prompt.txt").write_text(prompt_text, encoding="utf-8")

                meta = {
                    "task_id": task["id"],
                    "task_slug": task["slug"],
                    "version": version,
                    "run_idx": run_idx,
                    "seed_path": str(seed_for_version[version]),
                    "covers_constraints": task["covers_constraints"],
                    "covers_resources": task["covers_resources"],
                    "created_at": datetime.now(UTC).isoformat(),
                    "output_path": str(run_dir / "output.py"),
                }
                (run_dir / "metadata.json").write_text(
                    json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                manifest_runs.append(meta)

    plan = {
        "experiment": "stage-2.5 effectiveness validation",
        "plan_doc": "worklogs/2026-04/2026-04-19-step-2-5-experiment-plan.md",
        "created_at": datetime.now(UTC).isoformat(),
        "tasks": TASKS,
        "versions": VERSIONS,
        "runs_per_cell": args.runs_per_cell,
        "total_runs": len(manifest_runs),
        "baseline_seed": str(args.baseline_seed.resolve()),
        "treatment_seed": str(args.treatment_seed.resolve()),
        "runs": manifest_runs,
    }
    (args.output_root / "plan.json").write_text(
        json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"[done] output-root: {args.output_root}")
    print(f"       tasks:       {len(TASKS)}")
    print(f"       versions:    {len(VERSIONS)}")
    print(f"       runs/cell:   {args.runs_per_cell}")
    print(f"       total runs:  {len(manifest_runs)}")
    print(f"       plan.json:   {args.output_root / 'plan.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
