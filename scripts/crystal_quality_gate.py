#!/usr/bin/env python3
"""Crystal Quality Gate — 晶体质量自动化验证门禁

独立计算晶体覆盖率，不依赖 agent 自检。

用法:
    python3 crystal_quality_gate.py \\
        --blueprint path/to/LATEST.yaml \\
        --constraints path/to/LATEST.jsonl \\
        --crystal path/to/seed.md \\
        [--output path/to/quality_report.json] \\
        [--strict]

退出码:
    0 — 全部覆盖率达标（100%）
    1 — 任一维度 < 100%（strict 模式）或关键段落缺失
    2 — 输入文件错误

产出:
    - quality_report.json（机器可读）
    - stdout 人可读 summary
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

try:
    import yaml
except ImportError:
    print("[error] PyYAML not installed. Run: pip install pyyaml", file=sys.stderr)
    sys.exit(2)


# ----------------------------
# 解析输入
# ----------------------------


def load_blueprint(path: Path) -> dict:
    with path.open() as f:
        data = yaml.safe_load(f)
    bd_ids = []
    for bd in data.get("business_decisions", []) or []:
        bd_id = bd.get("id")
        if bd_id:
            bd_ids.append(bd_id)
    uc_ids = []
    for uc in data.get("known_use_cases", []) or []:
        uc_id = uc.get("id")
        if uc_id:
            uc_ids.append(uc_id)
    stages = [s.get("id") or s.get("name") for s in (data.get("stages") or [])]
    return {
        "bd_ids": bd_ids,
        "uc_ids": uc_ids,
        "stages": [s for s in stages if s],
        "bd_count": len(bd_ids),
        "uc_count": len(uc_ids),
        "stage_count": len(stages),
    }


def load_constraints(path: Path) -> dict:
    cids = []
    severity = Counter()
    kinds = Counter()
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                c = json.loads(line)
            except json.JSONDecodeError:
                continue
            cid = c.get("id")
            if cid:
                cids.append(cid)
            sev = c.get("severity")
            if sev:
                severity[sev] += 1
            kind = c.get("constraint_kind")
            if kind:
                kinds[kind] += 1
    fatal_ids = []
    non_fatal_ids = []
    # 重新遍历以分出 fatal / non-fatal
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                c = json.loads(line)
            except json.JSONDecodeError:
                continue
            cid = c.get("id")
            if not cid:
                continue
            if c.get("severity") == "fatal":
                fatal_ids.append(cid)
            else:
                non_fatal_ids.append(cid)
    return {
        "cids": cids,
        "count": len(cids),
        "fatal_ids": fatal_ids,
        "non_fatal_ids": non_fatal_ids,
        "fatal_count": len(fatal_ids),
        "non_fatal_count": len(non_fatal_ids),
        "severity_distribution": dict(severity),
        "kind_distribution": dict(kinds),
    }


def _extract_section(text: str, h2_title: str) -> str:
    """提取指定 H2 段的文本内容（不含 H2 行本身）。未找到返回空串。"""
    import re as _re

    pattern = rf"(?ms)^## {_re.escape(h2_title)}\s*$(.+?)(?=^## |\Z)"
    m = _re.search(pattern, text)
    return m.group(1) if m else ""


def scan_crystal(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    # 唯一 ID 引用（严格格式；支持 BD-XXX 和 BD-GAP-XXX 两种格式）
    bd_ids_found = set(re.findall(r"\bBD-(?:GAP-)?\d+\b", text))
    uc_ids_found = set(re.findall(r"\bUC-\d+\b", text))
    cids_found = set(re.findall(r"\bfinance-C-\d+\b", text))

    # 段落结构（## H2 标题）
    h2_sections = [m.group(1).strip() for m in re.finditer(r"^## (.+)$", text, re.MULTILINE)]

    # 五控制块（YAML fenced block 内的顶级键）
    control_blocks_canonical = [
        "intent_router",
        "context_state_machine",
        "spec_lock_registry",
        "preservation_manifest",
        "output_validator",
    ]
    control_blocks_found = {}
    for cb in control_blocks_canonical:
        # 匹配任一缩进级别的控制块键（YAML 允许 0 / 2 缩进）
        pattern = rf"^\s*{cb}:\s*$"
        control_blocks_found[cb] = bool(re.search(pattern, text, re.MULTILINE))

    # Output Validator 关键锚点
    scaffold_anchors = {
        "do_not_modify_fence": text.count("# === DO NOT MODIFY BELOW THIS LINE ==="),
        "from_validate_import": text.count("from validate import enforce_validation"),
        "enforce_validation_def": text.count("def enforce_validation"),
        "enforcement_protocol_title": bool(
            re.search(r"#+\s*(Output Validator )?Enforcement Protocol", text)
        ),
    }

    # Hard Gate（G1-G4）
    hard_gates_found = set(re.findall(r"\bG[1-9]\b", text))

    # 证据质量声明锚点（G9）：必须在 `## 证据质量声明` 段内含关键字段
    eq_section = _extract_section(text, "证据质量声明")
    evidence_quality_anchors = {
        "evidence_invalid": "evidence_invalid" in eq_section,
        "evidence_verify_ratio": "evidence_verify_ratio" in eq_section,
        "audit_fail_or_coverage": bool(
            re.search(
                r"(audit|subdomain_totals|finance_universal|coverage)", eq_section, re.IGNORECASE
            )
        ),
    }

    # 溯源政策锚点（G10）：必须在 `## 溯源政策` 段内含源文件引用 + 回查规则
    tp_section = _extract_section(text, "溯源政策")
    traceback_policy_anchors = {
        "source_file_ref": bool(
            re.search(
                r"LATEST\.(yaml|jsonl)|blueprint\.v\d+\.yaml|constraints\.v\d+\.jsonl", tp_section
            )
        ),
        "traceback_keyword": bool(re.search(r"回查|溯源|traceback", tp_section))
        and bool(re.search(r"必须回查|必查", tp_section)),
    }

    # 总体规模
    size = {
        "lines": len(lines),
        "bytes": len(text.encode("utf-8")),
    }

    return {
        "bd_ids_found": sorted(bd_ids_found),
        "uc_ids_found": sorted(uc_ids_found),
        "cids_found": sorted(cids_found),
        "bd_count_found": len(bd_ids_found),
        "uc_count_found": len(uc_ids_found),
        "cid_count_found": len(cids_found),
        "h2_sections": h2_sections,
        "control_blocks": control_blocks_found,
        "scaffold_anchors": scaffold_anchors,
        "hard_gates_found": sorted(hard_gates_found),
        "evidence_quality_anchors": evidence_quality_anchors,
        "traceback_policy_anchors": traceback_policy_anchors,
        "size": size,
    }


# ----------------------------
# 门禁计算
# ----------------------------

REQUIRED_H2_SECTIONS = [
    "Human Summary",
    "directive",
    "[FATAL] 约束",
    "Output Validator",
    "证据质量声明",
    "溯源政策",
    "架构蓝图",
    "资源",
    "约束",
    "验收",
]

CONDITIONAL_H2_SECTIONS = [
    "Rationalization Guards",  # 仅当约束池含 rationalization_guard 时必需
]


def compute_gate(bp: dict, cons: dict, crystal: dict) -> dict:
    # 覆盖率
    bd_covered = [bid for bid in bp["bd_ids"] if bid in crystal["bd_ids_found"]]
    bd_missing = [bid for bid in bp["bd_ids"] if bid not in crystal["bd_ids_found"]]

    uc_covered = [uid for uid in bp["uc_ids"] if uid in crystal["uc_ids_found"]]
    uc_missing = [uid for uid in bp["uc_ids"] if uid not in crystal["uc_ids_found"]]

    cid_covered = [cid for cid in cons["cids"] if cid in crystal["cids_found"]]
    cid_missing = [cid for cid in cons["cids"] if cid not in crystal["cids_found"]]

    fatal_covered = [cid for cid in cons["fatal_ids"] if cid in crystal["cids_found"]]
    fatal_missing = [cid for cid in cons["fatal_ids"] if cid not in crystal["cids_found"]]

    non_fatal_covered = [cid for cid in cons["non_fatal_ids"] if cid in crystal["cids_found"]]
    non_fatal_missing = [cid for cid in cons["non_fatal_ids"] if cid not in crystal["cids_found"]]

    def rate(cov: list, total: int) -> float:
        return len(cov) / total if total > 0 else 1.0

    coverage = {
        "bd": {
            "covered": len(bd_covered),
            "total": bp["bd_count"],
            "rate": rate(bd_covered, bp["bd_count"]),
            "missing_ids": bd_missing,
        },
        "uc": {
            "covered": len(uc_covered),
            "total": bp["uc_count"],
            "rate": rate(uc_covered, bp["uc_count"]),
            "missing_ids": uc_missing,
        },
        "constraint_all": {
            "covered": len(cid_covered),
            "total": cons["count"],
            "rate": rate(cid_covered, cons["count"]),
            "missing_ids_sample": cid_missing[:10],
            "missing_total": len(cid_missing),
        },
        "constraint_fatal": {
            "covered": len(fatal_covered),
            "total": cons["fatal_count"],
            "rate": rate(fatal_covered, cons["fatal_count"]),
            "missing_ids": fatal_missing,
        },
        "constraint_non_fatal": {
            "covered": len(non_fatal_covered),
            "total": cons["non_fatal_count"],
            "rate": rate(non_fatal_covered, cons["non_fatal_count"]),
            "missing_ids_sample": non_fatal_missing[:10],
            "missing_total": len(non_fatal_missing),
        },
    }

    # 结构检查
    h2_set = set(crystal["h2_sections"])
    missing_required = [s for s in REQUIRED_H2_SECTIONS if s not in h2_set]

    # Rationalization Guards 段条件性检查
    rg_constraints = (
        cons.get("kind_distribution", {}).get("rationalization_guard", 0)
        if cons.get("kind_distribution")
        else 0
    )
    rg_section_present = "Rationalization Guards" in h2_set
    rg_section_required = rg_constraints > 0
    rg_section_ok = not rg_section_required or rg_section_present

    # 控制块完整性
    control_blocks_ok = all(crystal["control_blocks"].values())
    missing_control_blocks = [k for k, v in crystal["control_blocks"].items() if not v]

    # Scaffold 完整性
    scaffold = crystal["scaffold_anchors"]
    scaffold_ok = (
        scaffold["do_not_modify_fence"] >= 1
        and scaffold["from_validate_import"] >= 1
        and scaffold["enforcement_protocol_title"]
    )

    # Hard Gate 完整性（G1-G4）
    required_gates = {"G1", "G2", "G3", "G4"}
    missing_hard_gates = sorted(required_gates - set(crystal["hard_gates_found"]))
    hard_gate_ok = not missing_hard_gates

    # G9 证据质量声明锚点完整性
    eqa = crystal.get("evidence_quality_anchors", {})
    evidence_quality_ok = all(eqa.values()) if eqa else False
    missing_evidence_anchors = [k for k, v in eqa.items() if not v]

    # G10 溯源政策锚点完整性
    tpa = crystal.get("traceback_policy_anchors", {})
    traceback_policy_ok = all(tpa.values()) if tpa else False
    missing_traceback_anchors = [k for k, v in tpa.items() if not v]

    # 门禁判定
    gates = {
        "bd_100_coverage": coverage["bd"]["rate"] >= 1.0,
        "uc_100_coverage": coverage["uc"]["rate"] >= 1.0,
        "constraint_100_coverage": coverage["constraint_all"]["rate"] >= 1.0,
        "fatal_constraint_100_coverage": coverage["constraint_fatal"]["rate"] >= 1.0,
        "required_h2_sections_present": not missing_required,
        "rationalization_guards_section_conditional": rg_section_ok,
        "five_control_blocks_present": control_blocks_ok,
        "output_validator_scaffold_complete": scaffold_ok,
        "hard_gate_g1_g4_complete": hard_gate_ok,
        "evidence_quality_declaration_complete": evidence_quality_ok,
        "traceback_policy_complete": traceback_policy_ok,
    }

    overall_pass = all(gates.values())

    return {
        "coverage": coverage,
        "structure": {
            "h2_sections_found": crystal["h2_sections"],
            "missing_required_sections": missing_required,
            "rationalization_guards_status": {
                "rg_constraint_count": rg_constraints,
                "section_required": rg_section_required,
                "section_present": rg_section_present,
                "ok": rg_section_ok,
            },
            "control_blocks": crystal["control_blocks"],
            "missing_control_blocks": missing_control_blocks,
            "scaffold_anchors": scaffold,
            "scaffold_ok": scaffold_ok,
            "hard_gates_found": crystal["hard_gates_found"],
            "missing_hard_gates": missing_hard_gates,
            "evidence_quality_anchors": eqa,
            "missing_evidence_quality_anchors": missing_evidence_anchors,
            "traceback_policy_anchors": tpa,
            "missing_traceback_policy_anchors": missing_traceback_anchors,
        },
        "gates": gates,
        "overall_pass": overall_pass,
        "crystal_size": crystal["size"],
    }


# ----------------------------
# 输出
# ----------------------------


def format_summary(report: dict) -> str:
    out = []
    out.append("=" * 70)
    out.append("Crystal Quality Gate — 报告")
    out.append("=" * 70)

    c = report["coverage"]
    out.append("")
    out.append("【覆盖率】")
    out.append(
        f"  BD:                {c['bd']['covered']:>4}/{c['bd']['total']:<4}  "
        f"{c['bd']['rate'] * 100:.1f}%  "
        f"{'✓' if report['gates']['bd_100_coverage'] else '✗ FAIL'}"
    )
    out.append(
        f"  UC:                {c['uc']['covered']:>4}/{c['uc']['total']:<4}  "
        f"{c['uc']['rate'] * 100:.1f}%  "
        f"{'✓' if report['gates']['uc_100_coverage'] else '✗ FAIL'}"
    )
    out.append(
        f"  约束（总）:         {c['constraint_all']['covered']:>4}/{c['constraint_all']['total']:<4}  "
        f"{c['constraint_all']['rate'] * 100:.1f}%  "
        f"{'✓' if report['gates']['constraint_100_coverage'] else '✗ FAIL'}"
    )
    out.append(
        f"    - Fatal:         {c['constraint_fatal']['covered']:>4}/{c['constraint_fatal']['total']:<4}  "
        f"{c['constraint_fatal']['rate'] * 100:.1f}%  "
        f"{'✓' if report['gates']['fatal_constraint_100_coverage'] else '✗ FAIL'}"
    )
    out.append(
        f"    - Non-fatal:     {c['constraint_non_fatal']['covered']:>4}/{c['constraint_non_fatal']['total']:<4}  "
        f"{c['constraint_non_fatal']['rate'] * 100:.1f}%"
    )

    s = report["structure"]
    out.append("")
    out.append("【段落结构】")
    out.append(
        f"  必须段落: {'✓' if not s['missing_required_sections'] else '✗ 缺失 ' + ', '.join(s['missing_required_sections'])}"
    )
    rg = s["rationalization_guards_status"]
    out.append(
        f"  Rationalization Guards: 约束池 {rg['rg_constraint_count']} 条 rg, 段落"
        f" {'存在' if rg['section_present'] else '缺失'}, "
        f"{'✓ OK（条件性）' if rg['ok'] else '✗ FAIL'}"
    )
    out.append(
        f"  五控制块: {'✓' if report['gates']['five_control_blocks_present'] else '✗ 缺失 ' + ', '.join(s['missing_control_blocks'])}"
    )

    out.append("")
    out.append("【Output Validator】")
    sa = s["scaffold_anchors"]
    out.append(f"  DO NOT MODIFY 围栏: {sa['do_not_modify_fence']} 次")
    out.append(f"  from validate import: {sa['from_validate_import']} 次")
    out.append(
        f"  Enforcement Protocol 标题: {'存在' if sa['enforcement_protocol_title'] else '缺失'}"
    )
    out.append(f"  Scaffold 完整性: {'✓' if s['scaffold_ok'] else '✗ FAIL'}")

    out.append("")
    out.append("【Hard Gate】")
    out.append(f"  找到: {', '.join(s['hard_gates_found']) if s['hard_gates_found'] else '无'}")
    out.append(
        f"  G1-G4 完整: {'✓' if report['gates']['hard_gate_g1_g4_complete'] else '✗ 缺失 ' + ', '.join(s['missing_hard_gates'])}"
    )

    out.append("")
    out.append("【证据质量声明 G9】")
    eqa = s.get("evidence_quality_anchors", {})
    for k, v in eqa.items():
        out.append(f"  {k}: {'✓' if v else '✗'}")
    out.append(
        f"  G9 完整: {'✓' if report['gates']['evidence_quality_declaration_complete'] else '✗ 缺失 ' + ', '.join(s.get('missing_evidence_quality_anchors', []))}"
    )

    out.append("")
    out.append("【溯源政策 G10】")
    tpa = s.get("traceback_policy_anchors", {})
    for k, v in tpa.items():
        out.append(f"  {k}: {'✓' if v else '✗'}")
    out.append(
        f"  G10 完整: {'✓' if report['gates']['traceback_policy_complete'] else '✗ 缺失 ' + ', '.join(s.get('missing_traceback_policy_anchors', []))}"
    )

    out.append("")
    out.append("【晶体规模】")
    out.append(f"  {report['crystal_size']['lines']} 行 / {report['crystal_size']['bytes']} 字节")

    out.append("")
    out.append("=" * 70)
    out.append(f"门禁总判定: {'✓ PASS' if report['overall_pass'] else '✗ FAIL'}")
    out.append("=" * 70)
    if not report["overall_pass"]:
        fails = [k for k, v in report["gates"].items() if not v]
        out.append(f"失败门禁: {', '.join(fails)}")

    # 缺失 ID 样本
    if c["bd"]["missing_ids"]:
        out.append(
            f"\nBD 缺失 ({len(c['bd']['missing_ids'])} 条), 样本: {c['bd']['missing_ids'][:10]}"
        )
    if c["constraint_non_fatal"]["missing_total"]:
        out.append(
            f"\nNon-fatal 约束缺失 ({c['constraint_non_fatal']['missing_total']} 条), "
            f"样本: {c['constraint_non_fatal']['missing_ids_sample']}"
        )

    return "\n".join(out)


# ----------------------------
# main
# ----------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--blueprint", type=Path, required=True, help="LATEST.yaml 或蓝图 YAML 路径"
    )
    parser.add_argument(
        "--constraints", type=Path, required=True, help="LATEST.jsonl 或约束 JSONL 路径"
    )
    parser.add_argument("--crystal", type=Path, required=True, help="seed.md 晶体文件路径")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="输出 quality_report.json 路径（默认与 crystal 同目录）",
    )
    parser.add_argument(
        "--strict", action="store_true", help="严格模式：任一维度未达 100 pct 时退出码 1"
    )
    args = parser.parse_args()

    for p in [args.blueprint, args.constraints, args.crystal]:
        if not p.exists():
            print(f"[error] file not found: {p}", file=sys.stderr)
            return 2

    bp = load_blueprint(args.blueprint)
    cons = load_constraints(args.constraints)
    crystal = scan_crystal(args.crystal)

    report = compute_gate(bp, cons, crystal)
    report["meta"] = {
        "blueprint_path": str(args.blueprint),
        "constraints_path": str(args.constraints),
        "crystal_path": str(args.crystal),
        "blueprint_summary": {
            "bd_count": bp["bd_count"],
            "uc_count": bp["uc_count"],
            "stage_count": bp["stage_count"],
        },
        "constraints_summary": {
            "count": cons["count"],
            "fatal_count": cons["fatal_count"],
            "severity_distribution": cons["severity_distribution"],
            "kind_distribution": cons["kind_distribution"],
        },
    }

    print(format_summary(report))

    # 输出 JSON
    output_path = args.output
    if output_path is None:
        output_path = args.crystal.parent / (args.crystal.stem + ".quality_report.json")
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[json report] {output_path}")

    if args.strict and not report["overall_pass"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
