#!/usr/bin/env python3
"""Prepare Crystal Inputs — 预处理蓝图 + 约束为 agent 友好的分块清单

核心问题：LATEST.jsonl 255KB / 147 条约束超过 Read 工具 token 限制，
agent 只能读前 N 条被迫摘要化，导致虚报 100 pct 覆盖率。

本脚本把 LATEST.yaml + LATEST.jsonl 预处理为:
    1. bd_checklist.md      — 164 条 BD 的 ID + type + content + stage 清单
    2. constraint_checklist.md — 147 条约束 ID + when + action + severity + kind
    3. uc_checklist.md      — 31 个 UC 的 ID + name + intent_keywords
    4. coverage_targets.json — agent 必须命中的目标 ID 全集（机器可读）

Agent 读这些 checklist 就能知道完整清单 + 每条的核心字段，
编译时可逐条核对不遗漏，使虚报不可能发生。

用法:
    python3 prepare_crystal_inputs.py \\
        --blueprint-dir knowledge/sources/finance/finance-bp-009--zvt \\
        [--output-dir knowledge/sources/finance/finance-bp-009--zvt/crystal_inputs]

输出:
    默认输出到 {blueprint-dir}/crystal_inputs/ 子目录
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

try:
    import yaml
except ImportError:
    print("[error] PyYAML not installed. Run: pip install pyyaml", file=sys.stderr)
    sys.exit(2)


def load_blueprint(path: Path) -> dict:
    with path.open() as f:
        return yaml.safe_load(f)


def load_constraints(path: Path) -> list[dict]:
    constraints = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                constraints.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"[warn] invalid JSON line skipped: {e}", file=sys.stderr)
    return constraints


def render_bd_checklist(bp: dict) -> str:
    bds = bp.get("business_decisions", []) or []
    by_stage = defaultdict(list)
    for bd in bds:
        stage = bd.get("stage") or "(no_stage)"
        by_stage[stage].append(bd)

    lines = [f"# Business Decisions Checklist (共 {len(bds)} 条)", ""]
    lines.append("**编译 agent 必读**：以下是蓝图的全部 business_decisions。")
    lines.append("晶体 seed.md 必须含**每一条**的 ID 引用（BD-XXX），否则门禁 FAIL。")
    lines.append("")
    lines.append("按 stage 分组。每条含: ID / type / content / evidence。")
    lines.append("")

    for stage in sorted(by_stage.keys()):
        stage_bds = by_stage[stage]
        lines.append(f"## Stage: {stage} ({len(stage_bds)} 条)")
        lines.append("")
        for bd in stage_bds:
            bd_id = bd.get("id", "?")
            bd_type = bd.get("type", "?")
            content = (bd.get("content") or "").replace("\n", " ")
            evidence = bd.get("evidence", "")
            lines.append(f"- **{bd_id}** [type={bd_type}] {content}")
            if evidence:
                lines.append(f"  - evidence: `{evidence}`")
        lines.append("")

    lines.append("---")
    lines.append(f"**清单结束**。共 {len(bds)} 条 BD 必须全部在 seed.md 中有 ID 引用。")
    return "\n".join(lines)


def render_uc_checklist(bp: dict) -> str:
    ucs = bp.get("known_use_cases", []) or []
    lines = [f"# Known Use Cases Checklist (共 {len(ucs)} 条)", ""]
    lines.append("**编译 agent 必读**：以下是蓝图的全部 known_use_cases。")
    lines.append("晶体 seed.md 的 intent_router 必须含每一条 UC 的 uc_id，否则门禁 FAIL。")
    lines.append("")

    for uc in ucs:
        uc_id = uc.get("id", "?")
        name = uc.get("name", "?")
        intent_keywords = uc.get("intent_keywords", [])
        data_domain = uc.get("data_domain", "")
        not_suitable = uc.get("not_suitable_for", [])
        lines.append(f"## {uc_id}: {name}")
        if intent_keywords:
            lines.append(f"- intent_keywords: {intent_keywords}")
        if data_domain:
            lines.append(f"- data_domain: {data_domain}")
        if not_suitable:
            lines.append(f"- not_suitable_for: {not_suitable}")
        lines.append("")

    lines.append("---")
    lines.append(f"**清单结束**。共 {len(ucs)} 条 UC 必须全部在 intent_router 中。")
    return "\n".join(lines)


def render_constraint_checklist(constraints: list[dict]) -> str:
    by_severity = defaultdict(list)
    for c in constraints:
        sev = c.get("severity", "unknown")
        by_severity[sev].append(c)

    lines = [f"# Constraints Checklist (共 {len(constraints)} 条)", ""]
    lines.append("**编译 agent 必读**：以下是约束池的全部条目。")
    lines.append("晶体 seed.md 必须含每一条的 ID 引用（finance-C-XXX），否则门禁 FAIL。")
    lines.append("")
    lines.append("**分段渲染规则**：")
    lines.append("- severity=fatal → `## [FATAL] 约束` 段")
    lines.append("- 其它 → `## 约束` 段按 stage 分组")
    lines.append("")
    lines.append(f"severity 分布: {dict((k, len(v)) for k, v in by_severity.items())}")
    lines.append("")

    order = ["fatal", "high", "medium", "low", "unknown"]
    sev_ordered = [s for s in order if s in by_severity] + [
        s for s in by_severity if s not in order
    ]

    for sev in sev_ordered:
        items = by_severity[sev]
        lines.append(f"## severity = {sev} ({len(items)} 条)")
        lines.append("")
        for c in items:
            cid = c.get("id", "?")
            core = c.get("core", {}) or {}
            when = (core.get("when") or c.get("when") or "").replace("\n", " ")
            action = (core.get("action") or c.get("action") or "").replace("\n", " ")
            kind = c.get("constraint_kind", "?")
            modality = core.get("modality", c.get("modality", "?"))
            applies_to = c.get("applies_to", {}) or {}
            stages = applies_to.get("stage_ids", [])
            lines.append(f"- **{cid}** [{kind} / {modality}]")
            lines.append(f"  - when: {when}")
            lines.append(f"  - action: {action}")
            if stages:
                lines.append(f"  - stages: {stages}")
        lines.append("")

    lines.append("---")
    lines.append(f"**清单结束**。共 {len(constraints)} 条约束必须全部在 seed.md 中有 ID 引用。")
    return "\n".join(lines)


def render_coverage_targets(bp: dict, constraints: list[dict]) -> dict:
    return {
        "blueprint_id": bp.get("id"),
        "blueprint_version": bp.get("version"),
        "blueprint_sop_version": bp.get("sop_version"),
        "required_bd_ids": [
            bd.get("id") for bd in (bp.get("business_decisions") or []) if bd.get("id")
        ],
        "required_uc_ids": [
            uc.get("id") for uc in (bp.get("known_use_cases") or []) if uc.get("id")
        ],
        "required_constraint_ids": [c.get("id") for c in constraints if c.get("id")],
        "required_stages": [
            s.get("id") or s.get("name")
            for s in (bp.get("stages") or [])
            if s.get("id") or s.get("name")
        ],
        "fatal_constraint_ids": [c.get("id") for c in constraints if c.get("severity") == "fatal"],
        "counts": {
            "bd": len(bp.get("business_decisions") or []),
            "uc": len(bp.get("known_use_cases") or []),
            "constraint": len(constraints),
            "fatal_constraint": sum(1 for c in constraints if c.get("severity") == "fatal"),
            "stage": len(bp.get("stages") or []),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--blueprint-dir", type=Path, required=True, help="含 LATEST.yaml + LATEST.jsonl 的目录"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="输出目录（默认 {blueprint-dir}/crystal_inputs）",
    )
    args = parser.parse_args()

    blueprint_path = args.blueprint_dir / "LATEST.yaml"
    constraints_path = args.blueprint_dir / "LATEST.jsonl"

    if not blueprint_path.exists():
        print(f"[error] {blueprint_path} not found", file=sys.stderr)
        return 2
    if not constraints_path.exists():
        print(f"[error] {constraints_path} not found", file=sys.stderr)
        return 2

    output_dir = args.output_dir or (args.blueprint_dir / "crystal_inputs")
    output_dir.mkdir(parents=True, exist_ok=True)

    bp = load_blueprint(blueprint_path)
    constraints = load_constraints(constraints_path)

    (output_dir / "bd_checklist.md").write_text(render_bd_checklist(bp), encoding="utf-8")
    (output_dir / "uc_checklist.md").write_text(render_uc_checklist(bp), encoding="utf-8")
    (output_dir / "constraint_checklist.md").write_text(
        render_constraint_checklist(constraints), encoding="utf-8"
    )

    targets = render_coverage_targets(bp, constraints)
    (output_dir / "coverage_targets.json").write_text(
        json.dumps(targets, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"[done] 产出到 {output_dir}/")
    print(f"  - bd_checklist.md        ({targets['counts']['bd']} 条 BD)")
    print(f"  - uc_checklist.md        ({targets['counts']['uc']} 条 UC)")
    print(
        f"  - constraint_checklist.md ({targets['counts']['constraint']} 条约束, {targets['counts']['fatal_constraint']} fatal)"
    )
    print("  - coverage_targets.json  (机器可读覆盖目标)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
