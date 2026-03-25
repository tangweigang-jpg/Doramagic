#!/usr/bin/env python3
"""Capture evaluation baseline from existing singleshot runs.

Reads the 7 existing runs from runs/ directory, scores them on 5 dimensions,
and writes eval_baseline.json. This baseline is compared against unified
pipeline outputs to measure quality improvement.

Usage:
    python3 scripts/dev/capture_eval_baseline.py

Output:
    reports/evals/eval_baseline.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from datetime import datetime

RUNS_DIR = Path("runs")
OUTPUT_DIR = Path("reports/evals")

# 5 evaluation dimensions (from validate_extraction.py)
DIMENSIONS = [
    "faithfulness",     # Are claims supported by evidence?
    "coverage",         # How much of the project's knowledge is captured?
    "traceability",     # Can each claim be traced to source?
    "consistency",      # Do claims agree with each other?
    "actionability",    # Can the output be directly used?
]


def score_delivery(delivery_dir: Path) -> dict | None:
    """Score a delivery directory on 5 dimensions.

    This is a heuristic scorer for baseline capture.
    Phase 5.5 will add LLM-as-judge scoring.
    """
    skill_md = delivery_dir / "SKILL.md"
    provenance_md = delivery_dir / "PROVENANCE.md"

    if not skill_md.exists():
        return None

    skill_content = skill_md.read_text(encoding="utf-8", errors="replace")
    provenance_content = ""
    if provenance_md.exists():
        provenance_content = provenance_md.read_text(encoding="utf-8", errors="replace")

    scores: dict[str, float] = {}

    # Faithfulness: presence of evidence refs (file:line citations)
    file_refs = skill_content.count("file:") + skill_content.count(".py:") + skill_content.count(".js:")
    scores["faithfulness"] = min(1.0, file_refs / 10.0)

    # Coverage: section completeness
    sections = ["WHY", "UNSAID", "Capabilities", "Workflow", "Limitations"]
    found = sum(1 for s in sections if s.lower() in skill_content.lower())
    scores["coverage"] = found / len(sections)

    # Traceability: provenance document quality
    if provenance_content:
        issue_refs = provenance_content.count("Issue #") + provenance_content.count("issue")
        card_refs = provenance_content.count("CC-") + provenance_content.count("WF-") + provenance_content.count("DR-")
        scores["traceability"] = min(1.0, (issue_refs + card_refs) / 8.0)
    else:
        scores["traceability"] = 0.0

    # Consistency: no contradictions (heuristic: check for "however" / "but" density)
    contradiction_markers = skill_content.lower().count("however") + skill_content.lower().count("contradicts")
    scores["consistency"] = max(0.0, 1.0 - contradiction_markers * 0.2)

    # Actionability: has concrete trigger words, commands, or code snippets
    actionable = skill_content.count("```") + skill_content.count("/dora") + skill_content.count("python")
    scores["actionability"] = min(1.0, actionable / 5.0)

    overall = sum(scores.values()) / len(scores)
    return {**scores, "overall": overall}


def find_deliveries() -> list[dict]:
    """Find all delivery directories in runs/."""
    results = []

    for run_dir in sorted(RUNS_DIR.iterdir()):
        if not run_dir.is_dir():
            continue

        # Check direct delivery/
        delivery = run_dir / "delivery"
        if delivery.is_dir() and (delivery / "SKILL.md").exists():
            results.append({
                "run_id": run_dir.name,
                "delivery_dir": str(delivery),
                "type": "direct",
            })
            continue

        # Check nested (openclaw runs)
        for sub in run_dir.rglob("delivery"):
            if sub.is_dir() and (sub / "SKILL.md").exists():
                results.append({
                    "run_id": f"{run_dir.name}/{sub.parent.name}",
                    "delivery_dir": str(sub),
                    "type": "nested",
                })

    return results


def main():
    if not RUNS_DIR.exists():
        print(f"ERROR: {RUNS_DIR} not found. Run from project root.", file=sys.stderr)
        sys.exit(1)

    deliveries = find_deliveries()
    print(f"Found {len(deliveries)} delivery directories")

    baseline_entries = []
    for d in deliveries:
        scores = score_delivery(Path(d["delivery_dir"]))
        if scores:
            entry = {
                "run_id": d["run_id"],
                "type": d["type"],
                "scores": scores,
                "delivery_dir": d["delivery_dir"],
            }
            baseline_entries.append(entry)
            print(f"  {d['run_id']}: overall={scores['overall']:.2f}")
        else:
            print(f"  {d['run_id']}: no SKILL.md found, skipping")

    if not baseline_entries:
        print("No deliveries to score. Baseline empty.")
        return

    # Compute aggregate baseline
    avg_scores = {}
    for dim in DIMENSIONS + ["overall"]:
        values = [e["scores"][dim] for e in baseline_entries]
        avg_scores[dim] = sum(values) / len(values)

    baseline = {
        "generated_at": datetime.now().isoformat(),
        "pipeline": "singleshot",
        "run_count": len(baseline_entries),
        "average_scores": avg_scores,
        "entries": baseline_entries,
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_file = OUTPUT_DIR / "eval_baseline.json"
    output_file.write_text(json.dumps(baseline, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nBaseline saved to {output_file}")
    print(f"Average scores: {json.dumps(avg_scores, indent=2)}")


if __name__ == "__main__":
    main()
