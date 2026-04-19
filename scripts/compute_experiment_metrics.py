#!/usr/bin/env python3
"""Compute programmatic metrics for stage-2.5 runs.

Reads _runs/stage2_5/plan.json + each {task}/{version}/r{idx}/output.py and
emits metrics.json containing per-run:

  - parse_pass: `ast.parse(output)` succeeded
  - lines, bytes: raw size
  - utilization:
      constraint_hits: how many of this task's covers_constraints are
        referenced in the output (id-string match, case-insensitive)
      resource_hits: how many of this task's covers_resources are imported
        (detected via import/from statements + setup installs)
      cross_util: any injected id (finance-C-9xxx or any injected package
        name) anywhere in the output — used as a coarse "did the crystal
        influence anything" signal

Aggregates per (task, version) and emits a summary.

Usage:
    python3 compute_experiment_metrics.py \\
        [--runs-root _runs/stage2_5]
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

# Injected items (the full set — any mention in any output counts as cross_util)
INJECTED_CONSTRAINT_IDS: list[str] = [f"finance-C-{9000 + i}" for i in range(1, 11)]

INJECTED_RESOURCES: list[str] = [
    "exchange-calendars",
    "scikit-learn",
    "empyrical-reloaded",
    "pyfolio-reloaded",
    "beautifulsoup4",
    "lightgbm",
    "scipy",
    "statsmodels",
    "lxml",
    "numba",
]
# Import-name aliases: some packages have different install vs import names
_IMPORT_ALIAS: dict[str, list[str]] = {
    "exchange-calendars": ["exchange_calendars"],
    "scikit-learn": ["sklearn"],
    "empyrical-reloaded": ["empyrical"],
    "pyfolio-reloaded": ["pyfolio"],
    "beautifulsoup4": ["bs4", "beautifulsoup"],
}


def _resource_patterns(pkg: str) -> list[str]:
    aliases = _IMPORT_ALIAS.get(pkg, [])
    return [pkg, *aliases]


def _contains_any(text: str, patterns: list[str]) -> bool:
    text_lower = text.lower()
    return any(p.lower() in text_lower for p in patterns)


def _extract_imports(code: str) -> set[str]:
    """Best-effort: return all top-level imported module names from the code."""
    names: set[str] = set()
    try:
        tree = ast.parse(code)
    except SyntaxError:
        # Fallback: regex scan
        for m in re.finditer(
            r"^(?:from\s+([\w\.]+)\s+import|import\s+([\w\.]+))",
            code,
            flags=re.MULTILINE,
        ):
            name = m.group(1) or m.group(2)
            if name:
                names.add(name.split(".")[0])
        return names
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def _score_run(output_path: Path, meta: dict) -> dict:
    code = output_path.read_text(encoding="utf-8")
    # parse_pass
    try:
        ast.parse(code)
        parse_pass = True
    except SyntaxError:
        parse_pass = False

    lines = code.count("\n") + (0 if code.endswith("\n") else 1)
    bytes_len = len(code.encode("utf-8"))

    # Per-task coverage: constraint + resource hits for this specific task
    covers_constraints: list[str] = meta.get("covers_constraints") or []
    covers_resources: list[str] = meta.get("covers_resources") or []

    constraint_hits: list[str] = []
    lowered = code.lower()
    for cid in covers_constraints:
        if cid.lower() in lowered:
            constraint_hits.append(cid)

    imports = _extract_imports(code)
    # Check resource presence: either in imports OR literal-string mention (for setup code)
    resource_hits: list[str] = []
    for pkg in covers_resources:
        patterns = _resource_patterns(pkg)
        import_hit = any(p.replace("-", "_") in imports for p in patterns)
        text_hit = _contains_any(code, patterns)
        if import_hit or text_hit:
            resource_hits.append(pkg)

    # Cross-utilization: ANY injected item mentioned
    cross_constraint_hits = [cid for cid in INJECTED_CONSTRAINT_IDS if cid.lower() in lowered]
    cross_resource_hits = [
        pkg
        for pkg in INJECTED_RESOURCES
        if any(p.replace("-", "_") in imports for p in _resource_patterns(pkg))
        or _contains_any(code, _resource_patterns(pkg))
    ]

    return {
        "parse_pass": parse_pass,
        "lines": lines,
        "bytes": bytes_len,
        "constraint_hits": constraint_hits,
        "constraint_hit_count": len(constraint_hits),
        "constraint_total": len(covers_constraints),
        "resource_hits": resource_hits,
        "resource_hit_count": len(resource_hits),
        "resource_total": len(covers_resources),
        "cross_constraint_hits": cross_constraint_hits,
        "cross_resource_hits": cross_resource_hits,
        "cross_util_any": bool(cross_constraint_hits or cross_resource_hits),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-root", type=Path, default=Path("_runs/stage2_5"))
    args = parser.parse_args()

    plan_path = args.runs_root / "plan.json"
    if not plan_path.exists():
        print(f"[error] plan.json not found: {plan_path}", file=sys.stderr)
        return 2
    plan = json.loads(plan_path.read_text(encoding="utf-8"))

    per_run: list[dict] = []
    missing: list[str] = []
    for run_meta in plan["runs"]:
        output_path = Path(run_meta["output_path"])
        if not output_path.exists():
            missing.append(str(output_path))
            continue
        scored = _score_run(output_path, run_meta)
        entry = {
            "task_id": run_meta["task_id"],
            "version": run_meta["version"],
            "run_idx": run_meta["run_idx"],
            "output_path": str(output_path),
            **scored,
        }
        per_run.append(entry)

    if missing:
        print(
            f"[warn] {len(missing)} outputs missing; continuing with {len(per_run)}",
            file=sys.stderr,
        )

    # Aggregate per (task, version)
    agg: dict = defaultdict(
        lambda: {
            "runs": 0,
            "parse_pass": 0,
            "constraint_hit_mean": 0.0,
            "resource_hit_mean": 0.0,
            "cross_util_runs": 0,
            "cross_constraint_id_union": Counter(),
            "cross_resource_pkg_union": Counter(),
            "mean_lines": 0.0,
        }
    )
    for e in per_run:
        key = (e["task_id"], e["version"])
        bucket = agg[key]
        bucket["runs"] += 1
        bucket["parse_pass"] += int(e["parse_pass"])
        bucket["constraint_hit_mean"] += e["constraint_hit_count"]
        bucket["resource_hit_mean"] += e["resource_hit_count"]
        if e["cross_util_any"]:
            bucket["cross_util_runs"] += 1
        for cid in e["cross_constraint_hits"]:
            bucket["cross_constraint_id_union"][cid] += 1
        for pkg in e["cross_resource_hits"]:
            bucket["cross_resource_pkg_union"][pkg] += 1
        bucket["mean_lines"] += e["lines"]

    agg_out: list[dict] = []
    for (task, version), b in sorted(agg.items()):
        n = b["runs"]
        agg_out.append(
            {
                "task_id": task,
                "version": version,
                "runs": n,
                "parse_pass_rate": round(b["parse_pass"] / n, 3),
                "constraint_hits_mean": round(b["constraint_hit_mean"] / n, 2),
                "resource_hits_mean": round(b["resource_hit_mean"] / n, 2),
                "cross_util_rate": round(b["cross_util_runs"] / n, 3),
                "mean_lines": round(b["mean_lines"] / n, 1),
                "cross_constraint_ids": dict(b["cross_constraint_id_union"]),
                "cross_resource_pkgs": dict(b["cross_resource_pkg_union"]),
            }
        )

    # Δ utilization per task (treatment - baseline)
    delta_util: list[dict] = []
    by_task: dict = defaultdict(dict)
    for row in agg_out:
        by_task[row["task_id"]][row["version"]] = row
    for task, versions in by_task.items():
        b = versions.get("baseline", {})
        t = versions.get("treatment", {})
        delta_util.append(
            {
                "task_id": task,
                "baseline_cross_util_rate": b.get("cross_util_rate", 0.0),
                "treatment_cross_util_rate": t.get("cross_util_rate", 0.0),
                "delta_cross_util_pp": round(
                    (t.get("cross_util_rate", 0.0) - b.get("cross_util_rate", 0.0)) * 100, 1
                ),
                "baseline_constraint_hits_mean": b.get("constraint_hits_mean", 0.0),
                "treatment_constraint_hits_mean": t.get("constraint_hits_mean", 0.0),
                "baseline_resource_hits_mean": b.get("resource_hits_mean", 0.0),
                "treatment_resource_hits_mean": t.get("resource_hits_mean", 0.0),
            }
        )

    out = {
        "generated_at": plan["created_at"],
        "total_runs": len(per_run),
        "missing": missing,
        "per_run": per_run,
        "aggregate": agg_out,
        "delta_utilization": delta_util,
    }
    out_path = args.runs_root / "metrics.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[done] metrics: {out_path}")

    # Print concise summary
    header = (
        f"\n{'task':<4} {'version':<10} {'parse%':<7} {'c_hits':<7} "
        f"{'r_hits':<7} {'cross_util%':<12} {'lines':<7}"
    )
    print(header)
    for row in agg_out:
        print(
            f"{row['task_id']:<4} {row['version']:<10} "
            f"{row['parse_pass_rate'] * 100:<7.1f} "
            f"{row['constraint_hits_mean']:<7.2f} "
            f"{row['resource_hits_mean']:<7.2f} "
            f"{row['cross_util_rate'] * 100:<12.1f} "
            f"{row['mean_lines']:<7.1f}"
        )

    print("\nΔ cross-util rate (treatment − baseline, pp):")
    for d in delta_util:
        print(f"  {d['task_id']}: {d['delta_cross_util_pp']:+.1f}pp")

    total_delta = sum(d["delta_cross_util_pp"] for d in delta_util) / len(delta_util)
    print(f"\n  mean Δ cross-util: {total_delta:+.1f}pp")

    return 0


if __name__ == "__main__":
    sys.exit(main())
