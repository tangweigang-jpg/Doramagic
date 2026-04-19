#!/usr/bin/env python3
"""Generate HUMAN_REVIEW_CHECKLIST.md for Stage 2.4 CEO terminal review.

Reads scored_constraints.jsonl + scored_resources.yaml from {bp-dir}/crystal_inputs/
and emits a Markdown checklist showing the Top-K passed candidates in a
scannable format. CEO replies with a comma-separated drop-list; downstream
tool applies the cut.

Usage:
    python3 generate_review_checklist.py \\
        --bp-dir knowledge/sources/finance/finance-bp-009--zvt \\
        [--top-constraints 15] \\
        [--top-resources 10]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("[error] PyYAML required", file=sys.stderr)
    sys.exit(2)


def _fmt_score(score: dict) -> str:
    """Format 5-dim score compactly."""
    return (
        f"a={score['alignment']:.2f} "
        f"act={score['actionability']:.2f} "
        f"nr={score['non_redundancy']:.2f} "
        f"roi={score['token_roi']:.2f} "
        f"c={score['confidence']:.2f}"
    )


def _load_scored_constraints(path: Path) -> list[dict]:
    entries: list[dict] = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if "_meta" in row:
                continue
            entries.append(row)
    return entries


def _load_scored_resources(path: Path) -> list[dict]:
    with path.open() as f:
        data = yaml.safe_load(f) or {}
    return data.get("resources") or []


def _render_constraints_section(entries: list[dict], top_k: int) -> str:
    passed = [e for e in entries if e.get("_sonnet_score", {}).get("passed")]
    passed.sort(key=lambda e: e["_sonnet_score"]["total"], reverse=True)
    top = passed[:top_k]

    lines: list[str] = []
    lines.append(f"## Constraints — Top {len(top)} of {len(passed)} passed (target: {top_k})")
    lines.append("")
    lines.append(
        "**Review each row. Reply in chat with comma-separated indices to DROP. "
        "Default: keep all.**"
    )
    lines.append("")
    lines.append("| # | ID | Score | One-line reason (sonnet) |")
    lines.append("|---|---|---|---|")
    for i, e in enumerate(top, 1):
        s = e["_sonnet_score"]
        rationale = s.get("rationale", "").replace("|", "\\|").strip()
        lines.append(f"| {i} | `{e['id']}` | **{s['total']:.2f}** | {rationale} |")
    lines.append("")
    lines.append("### Details")
    lines.append("")
    for i, e in enumerate(top, 1):
        s = e["_sonnet_score"]
        core = e.get("core") or {}
        when = (core.get("when") or "").strip()
        action = (core.get("action") or "").strip()
        cons = core.get("consequence")
        if isinstance(cons, dict):
            cons_text = cons.get("description", "")
        else:
            cons_text = str(cons) if cons else ""
        kind = e.get("constraint_kind", "")
        severity = e.get("severity", "")
        lines.append(f"**#{i} `{e['id']}`** — total **{s['total']:.2f}** · {kind} · {severity}")
        lines.append("")
        lines.append(f"- **when**: {when}")
        lines.append(f"- **action**: {action}")
        if cons_text:
            lines.append(f"- **consequence**: {cons_text}")
        lines.append(f"- **sonnet score**: {_fmt_score(s)}")
        lines.append(f"- **rationale**: {s.get('rationale', '')}")
        lines.append("")
    return "\n".join(lines)


def _render_resources_section(entries: list[dict], top_k: int) -> str:
    passed = [e for e in entries if e.get("_sonnet_score", {}).get("passed")]
    passed.sort(key=lambda e: e["_sonnet_score"]["total"], reverse=True)
    top = passed[:top_k]

    lines: list[str] = []
    lines.append(f"## Resources — Top {len(top)} of {len(passed)} passed (target: {top_k})")
    lines.append("")
    lines.append("| # | Name | Score | Reason (sonnet) |")
    lines.append("|---|---|---|---|")
    for i, r in enumerate(top, 1):
        s = r["_sonnet_score"]
        rationale = s.get("rationale", "").replace("|", "\\|").strip()
        lines.append(f"| {i} | `{r['name']}` | **{s['total']:.2f}** | {rationale} |")
    lines.append("")
    lines.append("### Details")
    lines.append("")
    for i, r in enumerate(top, 1):
        s = r["_sonnet_score"]
        desc = (r.get("description") or "").strip() or "(no description)"
        used_by = r.get("used_by") or []
        version = r.get("version_range", "")
        lines.append(f"**#{i} `{r['name']}`** — total **{s['total']:.2f}**")
        lines.append("")
        lines.append(f"- **version_range**: {version}")
        lines.append(f"- **used_by** ({len(used_by)} BPs): {', '.join(used_by[:8])}")
        lines.append(f"- **description**: {desc[:200]}")
        lines.append(f"- **sonnet score**: {_fmt_score(s)}")
        lines.append(f"- **rationale**: {s.get('rationale', '')}")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bp-dir", type=Path, required=True)
    parser.add_argument("--top-constraints", type=int, default=15)
    parser.add_argument("--top-resources", type=int, default=10)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    inputs_dir = args.bp_dir / "crystal_inputs"
    c_path = inputs_dir / "scored_constraints.jsonl"
    r_path = inputs_dir / "scored_resources.yaml"
    for p in [c_path, r_path]:
        if not p.exists():
            print(f"[error] missing: {p}", file=sys.stderr)
            return 2

    constraints = _load_scored_constraints(c_path)
    resources = _load_scored_resources(r_path)

    bp_id = args.bp_dir.name
    header = [
        f"# Human Review Checklist — {bp_id}",
        "",
        f"- **Sources**: `{c_path.name}` ({len(constraints)} scored), "
        f"`{r_path.name}` ({len(resources)} scored)",
        f"- **Targets**: Top-{args.top_constraints} constraints + "
        f"Top-{args.top_resources} resources",
        "- **Action**: Reply in chat with drop-indices, format:",
        "  `drop constraints: 2,7,9; drop resources: 3`",
        "- **Score legend**: a=alignment · act=actionability · nr=non_redundancy "
        "· roi=token_roi · c=confidence · total=weighted",
        "",
        "---",
        "",
    ]
    body = [
        _render_constraints_section(constraints, args.top_constraints),
        "---",
        "",
        _render_resources_section(resources, args.top_resources),
    ]
    content = "\n".join(header) + "\n".join(body)

    out = args.output or (inputs_dir / "HUMAN_REVIEW_CHECKLIST.md")
    out.write_text(content, encoding="utf-8")
    print(f"[done] checklist: {out}  ({len(content):,} chars)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
