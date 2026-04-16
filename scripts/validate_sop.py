#!/usr/bin/env python3
"""SOP 产出验证器——确保每次提取符合 SOP 契约。

采集验证和晶体验证完全独立，两套契约，两条命令。

用法：
    python scripts/validate_sop.py extraction --blueprint-id finance-bp-009
    python scripts/validate_sop.py crystal --blueprint-id finance-bp-009
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ── 契约阈值 ──

BP_MIN_BD = 20
BP_MIN_UC = 8
BP_VALID_BD_ATOMS = {"T", "B", "BA", "DK", "RC", "M"}
# SOP v3.6: B/RC is now allowed (regulatory constraints with implementation choices)
BP_FORBIDDEN_COMBOS: list[set[str]] = []
BP_CURRENT_SOP = "3.6"

CON_MIN_TOTAL = 80
CON_MIN_MC_RATIO = 0.45  # v3.6: relaxed from 0.50 — expert_reasoning constraints are valid
CON_MIN_KINDS = 3
CON_CURRENT_SCHEMA = "2.2"

CRYSTAL_CONTROL_BLOCKS = [
    "intent_router",
    "context_state_machine",
    "spec_lock_registry",
    "preservation_manifest",
    "output_validator",
]
CRYSTAL_MIN_SIZE = 50000


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""


# ════════════════════════════════════════
# 蓝图验证
# ════════════════════════════════════════


def validate_blueprint(bp_path: Path) -> list[CheckResult]:
    """验证蓝图 YAML 是否符合 SOP v3.6 契约。"""
    results: list[CheckResult] = []

    # 1. YAML 可解析
    try:
        raw = yaml.safe_load(bp_path.read_text())
        results.append(CheckResult("YAML 可解析", True))
    except Exception as e:
        results.append(CheckResult("YAML 可解析", False, str(e)))
        return results  # 后续检查都依赖 YAML 解析

    # 2. BD 数量
    bds = raw.get("business_decisions", [])
    results.append(
        CheckResult(
            f"BD 数量 ≥ {BP_MIN_BD}",
            len(bds) >= BP_MIN_BD,
            f"实际 {len(bds)}",
        )
    )

    # 3. UC 数量 (v2 uses "use_cases", legacy used "known_use_cases")
    ucs = raw.get("use_cases") or raw.get("known_use_cases") or []
    results.append(
        CheckResult(
            f"UC 数量 ≥ {BP_MIN_UC}",
            len(ucs) >= BP_MIN_UC,
            f"实际 {len(ucs)}",
        )
    )

    # 4. UC 消歧字段完整性
    missing_disambig = []
    for i, uc in enumerate(ucs):
        for field in ("negative_keywords", "disambiguation", "data_domain"):
            if not uc.get(field):
                missing_disambig.append(f"{uc.get('name', f'UC#{i}')}.{field}")
    results.append(
        CheckResult(
            "UC 消歧字段完整",
            len(missing_disambig) == 0,
            f"缺失: {missing_disambig[:5]}" if missing_disambig else "",
        )
    )

    # 5. BD 类型合法（原子拆分，不维护组合字符串枚举）
    invalid_types = []
    for bd in bds:
        bd_type = bd.get("type", "")
        atoms = {a.strip() for a in bd_type.split("/")}
        # 检查每个原子是否合法
        unknown = atoms - BP_VALID_BD_ATOMS
        if unknown:
            invalid_types.append(
                f"{bd.get('decision', '?')[:30]}... → '{bd_type}' (unknown: {unknown})"
            )
        # 检查禁止组合（RC+B 不得混编）
        for combo in BP_FORBIDDEN_COMBOS:
            if combo <= atoms:
                invalid_types.append(
                    f"{bd.get('decision', '?')[:30]}... → '{bd_type}' (forbidden: RC+B)"
                )
    results.append(
        CheckResult(
            "BD 类型合法",
            len(invalid_types) == 0,
            f"非法: {invalid_types[:3]}" if invalid_types else "",
        )
    )

    # 6. audit_checklist_summary 存在
    results.append(
        CheckResult(
            "audit_checklist_summary 存在",
            "audit_checklist_summary" in raw,
        )
    )

    # 7. sop_version
    sop_ver = raw.get("sop_version", "")
    if not sop_ver:
        sop_ver = raw.get("audit_checklist_summary", {}).get("sop_version", "")
    results.append(
        CheckResult(
            f"sop_version = {BP_CURRENT_SOP}",
            sop_ver == BP_CURRENT_SOP,
            f"实际 '{sop_ver}'" if sop_ver != BP_CURRENT_SOP else "",
        )
    )

    # 8. version 字段存在 (v2 blueprints use sop_version; legacy used version)
    has_version = bool(raw.get("version") or raw.get("sop_version"))
    results.append(
        CheckResult(
            "version 字段存在",
            has_version,
            f"version = {raw.get('version', raw.get('sop_version', '缺失'))}",
        )
    )

    return results


# ════════════════════════════════════════
# 约束验证
# ════════════════════════════════════════


def validate_constraints(
    bp_id: str,
    domain: str = "finance",
    constraints_dir: Path | None = None,
    jsonl_override: Path | None = None,
) -> list[CheckResult]:
    """验证蓝图关联约束是否符合 SOP v2.2 契约。"""
    results: list[CheckResult] = []
    if constraints_dir is None:
        constraints_dir = PROJECT_ROOT / "knowledge" / "constraints" / "domains"

    # v2: use per-blueprint JSONL from sources/ if available
    main_jsonl = jsonl_override if jsonl_override else constraints_dir / f"{domain}.jsonl"

    # 1. JSONL 可解析
    if not main_jsonl.exists():
        results.append(CheckResult("JSONL 文件存在", False, str(main_jsonl)))
        return results
    results.append(CheckResult("JSONL 文件存在", True))

    # 收集该蓝图的约束
    bp_constraints: list[dict] = []
    parse_errors = 0
    with open(main_jsonl) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                parse_errors += 1
                continue
            bids = rec.get("applies_to", {}).get("blueprint_ids") or []
            # v2: per-blueprint JSONL contains all constraints for this BP
            if jsonl_override or bp_id in bids:
                bp_constraints.append(rec)

    results.append(
        CheckResult(
            "JSONL 无解析错误",
            parse_errors == 0,
            f"{parse_errors} 行解析失败" if parse_errors else "",
        )
    )

    # 2. 约束总数
    total = len(bp_constraints)
    results.append(
        CheckResult(
            f"约束总数 ≥ {CON_MIN_TOTAL}",
            total >= CON_MIN_TOTAL,
            f"实际 {total}",
        )
    )

    # 3. machine_checkable 比例
    mc_count = sum(1 for c in bp_constraints if c.get("machine_checkable"))
    mc_ratio = mc_count / total if total > 0 else 0
    results.append(
        CheckResult(
            f"machine_checkable ≥ {CON_MIN_MC_RATIO:.0%}",
            mc_ratio >= CON_MIN_MC_RATIO,
            f"实际 {mc_ratio:.1%} ({mc_count}/{total})",
        )
    )

    # 4. 有 derived_from 约束（Step 2.4 已执行）
    has_derived = any(c.get("derived_from") for c in bp_constraints)
    results.append(
        CheckResult(
            "Step 2.4 已执行 (has derived_from)",
            has_derived,
        )
    )

    # 5. schema_version
    old_schema = [
        c
        for c in bp_constraints
        if (c.get("version", {}).get("schema_version", "2.0")) < CON_CURRENT_SCHEMA
    ]
    results.append(
        CheckResult(
            f"schema_version = {CON_CURRENT_SCHEMA}",
            len(old_schema) == 0,
            f"{len(old_schema)} 条仍为旧版本" if old_schema else "",
        )
    )

    # 6. 有 fatal 级约束
    has_fatal = any(c.get("severity") == "fatal" for c in bp_constraints)
    results.append(
        CheckResult(
            "有 fatal 级约束",
            has_fatal,
        )
    )

    # 7. constraint_kind 覆盖度
    kinds = {c.get("constraint_kind") for c in bp_constraints}
    results.append(
        CheckResult(
            f"constraint_kind ≥ {CON_MIN_KINDS} 种",
            len(kinds) >= CON_MIN_KINDS,
            f"实际 {len(kinds)} 种: {kinds}",
        )
    )

    return results


# ════════════════════════════════════════
# 晶体验证
# ════════════════════════════════════════


def validate_crystal(
    crystal_path: Path,
    bp_path: Path | None = None,
) -> list[CheckResult]:
    """验证晶体是否符合 SOP v2.1 契约。独立于采集验证。"""
    results: list[CheckResult] = []

    if not crystal_path.exists():
        results.append(CheckResult("晶体文件存在", False, str(crystal_path)))
        return results

    text = crystal_path.read_text()
    size = len(text.encode("utf-8"))

    # 1. 文件大小
    results.append(
        CheckResult(
            f"晶体大小 > {CRYSTAL_MIN_SIZE // 1000}KB",
            size > CRYSTAL_MIN_SIZE,
            f"实际 {size} bytes ({size // 1024}KB)",
        )
    )

    # 2. 五个控制块（正则匹配，容忍空格和后缀）
    for block in CRYSTAL_CONTROL_BLOCKS:
        pattern = rf"(?im)^##\s+{re.escape(block)}\b"
        results.append(
            CheckResult(
                f"控制块 {block}",
                bool(re.search(pattern, text)),
            )
        )

    # 3. FATAL 段
    results.append(
        CheckResult(
            "[FATAL] 段存在",
            "[FATAL]" in text,
        )
    )

    # 4. context_acquisition
    results.append(
        CheckResult(
            "context_acquisition 存在",
            "## context_acquisition" in text,
        )
    )

    # 5. execution_directive
    results.append(
        CheckResult(
            "execution_directive 存在",
            "## execution_directive" in text,
        )
    )

    # 6. 人话摘要
    results.append(
        CheckResult(
            "人话摘要存在",
            "人话摘要" in text,
        )
    )

    # 7. UC 覆盖率（如果有蓝图路径）
    if bp_path and bp_path.exists():
        try:
            raw = yaml.safe_load(bp_path.read_text())
            uc_count = len(raw.get("known_use_cases", []))
            uc_refs = text.count("UC-")
            results.append(
                CheckResult(
                    f"UC 覆盖率 ({uc_refs} refs / {uc_count} UCs)",
                    uc_refs >= uc_count,
                    f"intent_router 应包含全部 {uc_count} 条 UC",
                )
            )
        except Exception:
            pass

    # 8. Powered by 标记
    results.append(
        CheckResult(
            "Footer 版本标记",
            "Powered by Doramagic" in text,
        )
    )

    return results


# ════════════════════════════════════════
# 输出格式化
# ════════════════════════════════════════


def print_results(title: str, results: list[CheckResult]) -> bool:
    """打印验证结果。返回 True=全通过，False=有失败。"""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}\n")

    n_pass = sum(1 for r in results if r.passed)
    n_fail = sum(1 for r in results if not r.passed)

    for r in results:
        icon = "✅" if r.passed else "❌"
        detail = f" — {r.detail}" if r.detail else ""
        print(f"  {icon} {r.name}{detail}")

    print(f"\n  结果: {n_pass} PASS / {n_fail} FAIL")
    if n_fail == 0:
        print(f"  ✅ 全部通过")
    else:
        print(f"  ❌ {n_fail} 项未通过")
    print(f"{'=' * 60}")

    return n_fail == 0


# ════════════════════════════════════════
# CLI
# ════════════════════════════════════════


def run_extraction_validation(bp_id: str, domain: str = "finance") -> bool:
    """库入口：验证采集产出。返回 True=通过，False=失败。不调 sys.exit。"""
    # v2: prefer knowledge/sources/ (LATEST.yaml symlink) over legacy knowledge/blueprints/
    bp_path = PROJECT_ROOT / "knowledge" / "blueprints" / domain / f"{bp_id}.yaml"
    sources_dir = PROJECT_ROOT / "knowledge" / "sources" / domain
    for candidate_dir in sorted(sources_dir.glob(f"{bp_id}--*")):
        latest = candidate_dir / "LATEST.yaml"
        if latest.exists():
            bp_path = latest
            break
    constraints_dir = PROJECT_ROOT / "knowledge" / "constraints" / "domains"
    # v2: if blueprint came from sources/, also look for constraints there
    con_jsonl_override: Path | None = None
    if "sources" in str(bp_path):
        latest_jsonl = bp_path.parent / "LATEST.jsonl"
        if latest_jsonl.exists():
            con_jsonl_override = latest_jsonl.resolve()

    if not bp_path.exists():
        print(f"Error: 蓝图文件不存在: {bp_path}", file=sys.stderr)
        return False

    bp_results = validate_blueprint(bp_path)
    bp_ok = print_results(f"蓝图验证: {bp_id}", bp_results)

    con_results = validate_constraints(
        bp_id, domain, constraints_dir, jsonl_override=con_jsonl_override
    )
    con_ok = print_results(f"约束验证: {bp_id}", con_results)

    return bp_ok and con_ok


def run_crystal_validation(bp_id: str, domain: str = "finance") -> bool:
    """库入口：验证晶体。返回 True=通过，False=失败。不调 sys.exit。"""
    crystal_dir = PROJECT_ROOT / "knowledge" / "crystals" / bp_id
    candidates = sorted(crystal_dir.glob(f"{bp_id}*.seed.md")) if crystal_dir.exists() else []
    if not candidates:
        print(f"Error: 未找到晶体文件: {crystal_dir}/{bp_id}*.seed.md", file=sys.stderr)
        return False

    crystal_path = candidates[-1]
    bp_path = PROJECT_ROOT / "knowledge" / "blueprints" / domain / f"{bp_id}.yaml"

    results = validate_crystal(crystal_path, bp_path if bp_path.exists() else None)
    return print_results(f"晶体验证: {crystal_path.name}", results)


def cmd_validate_extraction(args: argparse.Namespace) -> None:
    """CLI 入口：验证采集产出。"""
    if not run_extraction_validation(args.blueprint_id, args.domain):
        sys.exit(1)


def cmd_validate_crystal(args: argparse.Namespace) -> None:
    """CLI 入口：验证晶体。"""
    if not run_crystal_validation(args.blueprint_id, args.domain):
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="SOP 产出验证器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 验证采集产出（蓝图 + 约束）
  python scripts/validate_sop.py extraction --blueprint-id finance-bp-009

  # 验证晶体（独立）
  python scripts/validate_sop.py crystal --blueprint-id finance-bp-009
""",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    ext = sub.add_parser("extraction", help="验证采集产出（蓝图 + 约束）")
    ext.add_argument("--blueprint-id", required=True, help="蓝图 ID")
    ext.add_argument("--domain", default="finance", help="领域")
    ext.set_defaults(func=cmd_validate_extraction)

    cry = sub.add_parser("crystal", help="验证晶体（独立于采集）")
    cry.add_argument("--blueprint-id", required=True, help="蓝图 ID")
    cry.add_argument("--domain", default="finance", help="领域")
    cry.set_defaults(func=cmd_validate_crystal)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
