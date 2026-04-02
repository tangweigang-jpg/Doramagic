#!/usr/bin/env python3
"""Generate enriched brick summary files for Doramagic skill references.

Reads JSONL brick files and produces markdown summaries that include:
- CRITICAL (failure) — top 6 failure bricks (highest priority)
- CONSTRAINTS — top 2 constraint bricks
- PATTERNS — top 3 pattern/assembly_pattern bricks (HOW to do things)
- RATIONALE — top 3 rationale bricks (WHY things work this way)

This gives the LLM both "what to avoid" AND "how to do it right".
"""

from __future__ import annotations

import json
from pathlib import Path


def load_bricks(jsonl_path: Path) -> list[dict]:
    bricks = []
    for line in jsonl_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            bricks.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return bricks


def score_brick(brick: dict) -> float:
    """Score for prioritization within each type group."""
    score = 1.0
    if "l1" in brick.get("brick_id", ""):
        score *= 1.5
    if brick.get("confidence") == "high":
        score *= 1.2
    return score


def truncate(text: str, max_chars: int = 200) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0] + "..."


def generate_summary(domain_id: str, bricks: list[dict]) -> str:
    by_type: dict[str, list[dict]] = {}
    for b in bricks:
        kt = b.get("knowledge_type", "")
        by_type.setdefault(kt, []).append(b)

    # Sort each group by score
    for kt in by_type:
        by_type[kt].sort(key=score_brick, reverse=True)

    lines = [f"# {domain_id} — 知识摘要", ""]

    # CRITICAL failures (top 6)
    failures = by_type.get("failure", [])[:6]
    if failures:
        lines.append("## CRITICAL (failure)")
        for b in failures:
            stmt = truncate(b.get("statement", ""), 250)
            prefix = "" if stmt.upper().startswith("FAILURE:") else "FAILURE: "
            lines.append(f"- {prefix}{stmt}")
        lines.append("")

    # CONSTRAINTS (top 2)
    constraints = by_type.get("constraint", [])[:2]
    if constraints:
        lines.append("## CONSTRAINTS")
        for b in constraints:
            stmt = truncate(b.get("statement", ""), 250)
            lines.append(f"- {stmt}")
        lines.append("")

    # PATTERNS — how to do things (top 3 from pattern + assembly_pattern)
    patterns = by_type.get("pattern", []) + by_type.get("assembly_pattern", [])
    patterns.sort(key=score_brick, reverse=True)
    patterns = patterns[:3]
    if patterns:
        lines.append("## PATTERNS (how to build)")
        for b in patterns:
            stmt = truncate(b.get("statement", ""), 250)
            lines.append(f"- {stmt}")
        lines.append("")

    # RATIONALE — why things work (top 3)
    rationales = by_type.get("rationale", [])[:3]
    if rationales:
        lines.append("## RATIONALE (why it works)")
        for b in rationales:
            stmt = truncate(b.get("statement", ""), 250)
            lines.append(f"- {stmt}")
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    bricks_dir = Path(__file__).resolve().parents[2] / "knowledge" / "bricks"
    output_dir = (
        Path(__file__).resolve().parents[2] / "skills" / "doramagic" / "references" / "bricks"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    generated = 0
    for jsonl_file in sorted(bricks_dir.glob("*.jsonl")):
        domain_id = jsonl_file.stem
        bricks = load_bricks(jsonl_file)
        if not bricks:
            continue

        summary = generate_summary(domain_id, bricks)
        out_path = output_dir / f"{domain_id}.md"
        out_path.write_text(summary, encoding="utf-8")
        generated += 1

        # Stats
        lines = summary.count("\n")
        print(f"  {domain_id}: {len(bricks)} bricks → {lines} lines")

    print(f"\nGenerated {generated} summary files in {output_dir}")


if __name__ == "__main__":
    main()
