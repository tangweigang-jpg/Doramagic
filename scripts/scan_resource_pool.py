#!/usr/bin/env python3
"""scan_resource_pool.py — 反扫蓝图 resources[] 字段，产出领域共享资源池 YAML

从 knowledge/sources/{domain}/ 下的每颗蓝图读取 resources[] 列表，
按 name 聚合，将被 ≥ min_shared 颗蓝图引用的资源写入领域共享池 YAML。

同时将 replaceable_component 类条目写入独立文件 replaceable_slots.yaml。

用法:
    python scripts/scan_resource_pool.py \\
        --domain finance \\
        --min-shared 2 \\
        --cross-domain-threshold 10 \\
        --output knowledge/sources/finance/_shared/resources.yaml

输出:
    - resources.yaml（路径由 --output 指定，不含 replaceable_component）
    - replaceable_slots.yaml（同目录，架构可替换槽位）
    - stdout 统计摘要

退出码:
    0  成功
    1  输入错误（找不到 domain 目录 / 无蓝图）
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    print("[error] PyYAML not installed. Run: pip install pyyaml", file=sys.stderr)
    sys.exit(2)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VERSION_SPEC_RE = re.compile(r"([><=!^~]+[\d.,*]+)")

# Keywords for external_service subkind heuristics
_API_ENDPOINT_KEYWORDS = re.compile(
    r"\b(api|service|endpoint|rest|graphql|websocket|webhook|sdk)\b",
    re.IGNORECASE,
)
_DATA_SOURCE_KEYWORDS = re.compile(
    r"\b(data|feed|market|provider|price|quote|tick|stream|dataset|source)\b",
    re.IGNORECASE,
)
_DATA_STAGE_PREFIX = re.compile(r"\bdata_", re.IGNORECASE)


def extract_base_name(raw_name: str) -> str:
    """Strip version specifiers from a resource name.

    e.g. 'numpy>=1.19.5,<2.0.0' → 'numpy'
         'requests==2.32.0'       → 'requests'
         'pandas'                 → 'pandas'
    """
    # Split at first version operator character
    m = re.split(r"[><=!^~]", raw_name, maxsplit=1)
    return m[0].strip()


def extract_version_spec(raw_name: str) -> str | None:
    """Return raw version specifier portion if present, else None."""
    m = re.search(r"([><=!^~].+)$", raw_name)
    return m.group(1).strip() if m else None


def derive_kind(resource_type: str) -> str:
    """Map blueprint resource 'type' to pool 'kind'."""
    type_lower = (resource_type or "").lower()
    if type_lower == "python_package":
        return "python_package"
    if type_lower == "external_service":
        return "external_service"
    if type_lower == "replaceable_component":
        return "replaceable_component"
    # slot or anything else
    return "replaceable_component"


def derive_subkind(name: str, description: str, used_in_stages: list) -> str:
    """Heuristically classify external_service into subkind.

    Priority:
      1. api_endpoint — name/description mentions api/service/endpoint/REST/GraphQL/WebSocket
      2. data_source  — name/description mentions data/feed/market/provider,
                        or used_in_stages contains a stage starting with 'data_'
      3. saas_service — fallback
    """
    combined = f"{name} {description or ''}"
    if _API_ENDPOINT_KEYWORDS.search(combined):
        return "api_endpoint"
    if _DATA_SOURCE_KEYWORDS.search(combined):
        return "data_source"
    stages = used_in_stages or []
    if any(_DATA_STAGE_PREFIX.search(str(s)) for s in stages):
        return "data_source"
    return "saas_service"


def extract_bp_id(dir_name: str) -> str:
    """Extract short bp-id from directory name.

    'finance-bp-009--zvt' → 'bp-009'
    'finance-bp-020--gs-quant' → 'bp-020'
    """
    m = re.match(r"[a-z]+-(?P<bp>bp-\d+)", dir_name)
    if m:
        return m.group("bp")
    # Fallback: return dir name as-is
    return dir_name


# ---------------------------------------------------------------------------
# Core scan
# ---------------------------------------------------------------------------


def scan_blueprints(domain_dir: Path) -> tuple[list[dict], list[dict], int, int, int]:
    """Scan all blueprint LATEST.yaml files in domain_dir.

    Returns:
        (resource_records, slot_records, source_blueprints_count,
         total_resource_entries, total_slot_entries)

    resource_records: one dict per unique (base_name) per blueprint (pool candidates):
        {bp_id, base_name, raw_name, resource}
    slot_records: one dict per unique (slot_name) per blueprint (slot candidates):
        {bp_id, slot_name, slot}
    """
    bp_dirs = sorted(
        [d for d in domain_dir.iterdir() if d.is_dir() and re.match(r"[a-z]+-bp-\d+", d.name)],
        key=lambda d: d.name,
    )

    if not bp_dirs:
        print(f"[error] No blueprint directories found in {domain_dir}", file=sys.stderr)
        sys.exit(1)

    resource_records: list[dict[str, Any]] = []
    slot_records: list[dict[str, Any]] = []
    total_resource_entries = 0
    total_slot_entries = 0
    bp_count = 0

    for bp_dir in bp_dirs:
        latest = bp_dir / "LATEST.yaml"
        if not latest.exists():
            continue

        with latest.open() as f:
            bp_data = yaml.safe_load(f) or {}

        resources: list[dict] = bp_data.get("resources", []) or []
        top_level_slots: list[dict] = bp_data.get("replaceable_slots", []) or []

        if not resources and not top_level_slots:
            continue

        bp_count += 1
        bp_id = extract_bp_id(bp_dir.name)

        # --- Pool candidates: resources[] (excluding replaceable_component) ---
        seen_names_this_bp: set[str] = set()
        for res in resources:
            total_resource_entries += 1
            raw_name: str = res.get("name", "") or ""
            if not raw_name:
                continue

            base_name = extract_base_name(raw_name)
            # Deduplicate within the same blueprint
            if base_name in seen_names_this_bp:
                continue
            seen_names_this_bp.add(base_name)

            resource_records.append(
                {
                    "bp_id": bp_id,
                    "base_name": base_name,
                    "raw_name": raw_name,
                    "resource": res,
                }
            )

        # --- Slot candidates: bp.replaceable_slots[] (new schema, commit 3009f72) ---
        # Also pick up legacy resources[].type == "replaceable_component" for backward compat.
        # Dedupe by slot_name within this BP (top-level slots take precedence).
        seen_slot_names_this_bp: set[str] = set()

        for slot in top_level_slots:
            total_slot_entries += 1
            slot_name: str = slot.get("name", "") or ""
            if not slot_name:
                continue
            if slot_name in seen_slot_names_this_bp:
                continue
            seen_slot_names_this_bp.add(slot_name)
            slot_records.append({"bp_id": bp_id, "slot_name": slot_name, "slot": slot})

        # Legacy path: resources[].type == "replaceable_component"
        for res in resources:
            if (res.get("type", "") or "").lower() != "replaceable_component":
                continue
            total_slot_entries += 1
            slot_name = res.get("name", "") or ""
            if not slot_name:
                continue
            if slot_name in seen_slot_names_this_bp:
                continue  # already captured from top-level slots
            seen_slot_names_this_bp.add(slot_name)
            slot_records.append({"bp_id": bp_id, "slot_name": slot_name, "slot": res})

    return resource_records, slot_records, bp_count, total_resource_entries, total_slot_entries


def _merge_slot_options(existing: list[dict], incoming: list[dict]) -> list[dict]:
    """Union-merge two options lists by options[].name (first-seen wins on conflict)."""
    seen_names: set[str] = {opt.get("name", "") for opt in existing}
    merged = list(existing)
    for opt in incoming:
        opt_name = opt.get("name", "")
        if opt_name and opt_name not in seen_names:
            seen_names.add(opt_name)
            merged.append(opt)
    return merged


def build_pool_and_slots(
    records: list[dict[str, Any]],
    slot_records: list[dict[str, Any]],
    min_shared: int,
    cross_domain_threshold: int,
    domain: str,
    bp_count: int,
    total_resource_entries: int,
    total_slot_entries: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Aggregate records into the shared pool + replaceable_slots structures.

    Returns:
        (pool_doc, slots_doc)

    Changes vs v1:
    - replaceable_component entries are excluded from pool_entries
    - top-level bp.replaceable_slots[] entries (commit 3009f72) are the primary slot source
    - legacy resources[].type == "replaceable_component" still merges in for backward compat
    - external_service entries gain a 'subkind' field
    """

    # Group by base_name
    name_to_records: dict[str, list[dict]] = defaultdict(list)
    for rec in records:
        name_to_records[rec["base_name"]].append(rec)

    scanned_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    pool_entries: list[dict[str, Any]] = []
    slot_entries: list[dict[str, Any]] = []
    project_specific_count = 0
    slot_id_counter = 1

    # --- Slot aggregation from slot_records (new schema + legacy merged) ---
    # Group by slot_name across blueprints
    slot_name_to_recs: dict[str, list[dict]] = defaultdict(list)
    for srec in slot_records:
        slot_name_to_recs[srec["slot_name"]].append(srec)

    for slot_name, srecs in slot_name_to_recs.items():
        bp_ids = sorted(set(r["bp_id"] for r in srecs))

        if len(bp_ids) < min_shared:
            project_specific_count += 1
            continue

        # Representative slot dict: first BP by sort order
        repr_srec = min(srecs, key=lambda r: r["bp_id"])
        repr_slot = repr_srec["slot"]

        slot_id = f"res-slot-{slot_id_counter:03d}"
        slot_id_counter += 1

        scope = "cross_domain" if len(bp_ids) >= cross_domain_threshold else "domain"

        # Union-merge options across all BPs (first-seen by bp_id sort wins on name conflict)
        merged_options: list[dict] = list(repr_slot.get("options") or [])
        for srec in sorted(srecs, key=lambda r: r["bp_id"])[1:]:
            incoming_opts = srec["slot"].get("options") or []
            merged_options = _merge_slot_options(merged_options, incoming_opts)

        slot_entry: dict[str, Any] = {
            "id": slot_id,
            "name": slot_name,
            "scope": scope,
            "description": repr_slot.get("description", ""),
            "used_by": bp_ids,
        }
        if merged_options:
            slot_entry["options"] = merged_options
        default = repr_slot.get("default")
        if default is not None:
            slot_entry["default"] = default

        slot_entries.append(slot_entry)

    # Sort slots: by used_by count desc, then name asc
    slot_entries.sort(key=lambda s: (-len(s["used_by"]), s["name"]))

    # --- Pool aggregation from resource_records ---
    # (replaceable_component in resources[] goes to slot stream above, not here)
    for base_name, recs in name_to_records.items():
        bp_ids = sorted(set(r["bp_id"] for r in recs))

        if len(bp_ids) < min_shared:
            project_specific_count += 1
            continue

        # Pick representative resource dict (first occurrence by bp_id sort)
        repr_rec = min(recs, key=lambda r: r["bp_id"])
        repr_res = repr_rec["resource"]

        # Derive kind — skip replaceable_component (now handled via slot_records above)
        resource_type = repr_res.get("type", "")
        kind = derive_kind(resource_type)

        if kind == "replaceable_component":
            # Backward compat: old-style resources[].type == "replaceable_component"
            # already captured in slot_records by scan_blueprints; skip here to avoid double-count.
            continue

        # --- regular resource → pool ---

        # Collect all declared version specifiers
        version_candidates = sorted(
            set(spec for r in recs if (spec := extract_version_spec(r["raw_name"])) is not None)
        )

        # TODO(P1): implement proper version range intersection via packaging/semver
        # For now: take first candidate if any, else "latest"
        if version_candidates:
            version_range = version_candidates[0]
        else:
            version_range = "latest"

        # Scope
        scope = "cross_domain" if len(bp_ids) >= cross_domain_threshold else "domain"

        entry: dict[str, Any] = {
            "kind": kind,
            "name": base_name,
            "scope": scope,
            "version_range": version_range,
            "version_candidates": version_candidates if version_candidates else [],
            "used_by": bp_ids,
            "provenance": {
                "first_seen_bp": bp_ids[0],
                "upstream_license": None,
                "scan_source": "automated",
                "scanned_at": scanned_at,
            },
            "known_pitfalls": [],
        }

        # Preserve extra fields from representative resource (description etc.)
        for field in ("description", "options", "default", "path", "used_in_stages"):
            val = repr_res.get(field)
            if val is not None:
                entry[field] = val

        # external_service: add subkind
        if kind == "external_service":
            entry["subkind"] = derive_subkind(
                name=base_name,
                description=repr_res.get("description", ""),
                used_in_stages=repr_res.get("used_in_stages", []) or [],
            )
            entry["catalog_metadata"] = None  # placeholder for enrich step

        pool_entries.append(entry)

    # Sort pool: by kind, then by used_by count desc, then name asc
    KIND_ORDER = {"python_package": 0, "external_service": 1}
    pool_entries.sort(key=lambda e: (KIND_ORDER.get(e["kind"], 99), -len(e["used_by"]), e["name"]))

    # Note: slot_entries already sorted above after aggregation

    # Count subkinds for meta
    subkind_breakdown: dict[str, int] = {}
    for e in pool_entries:
        if e["kind"] == "external_service":
            sk = e.get("subkind", "unknown")
            subkind_breakdown[sk] = subkind_breakdown.get(sk, 0) + 1

    pool_meta: dict[str, Any] = {
        "domain": domain,
        "scanned_at": scanned_at,
        "source_blueprints_count": bp_count,
        "total_resource_entries_scanned": total_resource_entries,
        "total_slot_entries_scanned": total_slot_entries,
        "pool_entries": len(pool_entries),
        "replaceable_slots_count": len(slot_entries),
        "project_specific_count": project_specific_count,
        "min_shared_threshold": min_shared,
        "cross_domain_threshold": cross_domain_threshold,
        "subkind_breakdown": subkind_breakdown,
    }

    slots_meta: dict[str, Any] = {
        "domain": domain,
        "scanned_at": scanned_at,
        "source_blueprints_count": bp_count,
        "total_slot_entries_scanned": total_slot_entries,
        "total_slots": len(slot_entries),
        "description": (
            "架构可替换槽位（非资源）。每个 slot 声明一个位置可以插入多种具体实现（resources[]）。"
            " 主要来源: bp.replaceable_slots[]（commit 3009f72），兼容旧 resources[].type==replaceable_component。"
            " options[].name 不自动展开进资源池（v2.2 P1 enrichment 工作）。"
        ),
    }

    pool_doc = {"meta": pool_meta, "resources": pool_entries}
    slots_doc = {"meta": slots_meta, "slots": slot_entries}

    return pool_doc, slots_doc


# ---------------------------------------------------------------------------
# Stats / reporting
# ---------------------------------------------------------------------------


def print_stats(pool: dict[str, Any], slots: dict[str, Any]) -> None:
    meta = pool["meta"]
    resources = pool["resources"]

    print("\n" + "=" * 60)
    print("  Resource Pool Scan — Summary")
    print("=" * 60)
    print(f"  Domain              : {meta['domain']}")
    print(f"  Source blueprints   : {meta['source_blueprints_count']}")
    print(
        f"  Resource entries    : {meta.get('total_resource_entries_scanned', meta.get('total_entries_scanned', '?'))}"
    )
    print(f"  Slot entries        : {meta.get('total_slot_entries_scanned', '?')}")
    print(f"  Pool entries        : {meta['pool_entries']}")
    print(f"  Replaceable slots   : {meta['replaceable_slots_count']}")
    print(f"  Project-specific    : {meta['project_specific_count']}")

    # By kind
    from collections import Counter

    kind_counts = Counter(r["kind"] for r in resources)
    print("\n  By kind:")
    for kind, count in sorted(kind_counts.items()):
        print(f"    {kind:<28} {count}")

    # Subkind breakdown
    subkind_bd = meta.get("subkind_breakdown", {})
    if subkind_bd:
        print("\n  External service subkind breakdown:")
        for sk, count in sorted(subkind_bd.items()):
            print(f"    {sk:<28} {count}")

    # By scope
    scope_counts = Counter(r["scope"] for r in resources)
    print("\n  By scope:")
    for scope, count in sorted(scope_counts.items()):
        print(f"    {scope:<28} {count}")

    # Top 10
    top10 = sorted(resources, key=lambda r: -len(r["used_by"]))[:10]
    print("\n  Top 10 shared resources (by blueprint count):")
    for i, r in enumerate(top10, 1):
        print(f"    {i:>2}. {r['name']:<30} {len(r['used_by'])} blueprints")

    # Slots summary
    slot_meta = slots["meta"]
    print(f"\n  Replaceable slots    : {slot_meta['total_slots']}")
    top5_slots = slots["slots"][:5]
    if top5_slots:
        print("  Top 5 slots (by blueprint count):")
        for s in top5_slots:
            print(f"       {s['name']:<30} {len(s['used_by'])} blueprints")

    print("=" * 60 + "\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scan blueprint resources[] and produce a domain shared pool YAML + replaceable_slots YAML.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--domain",
        required=True,
        help="Domain name, e.g. 'finance'. Blueprints are read from knowledge/sources/{domain}/",
    )
    parser.add_argument(
        "--min-shared",
        type=int,
        default=2,
        metavar="N",
        help="Minimum number of blueprints referencing a resource for it to enter the pool (default: 2)",
    )
    parser.add_argument(
        "--cross-domain-threshold",
        type=int,
        default=10,
        metavar="N",
        help="If used_by count >= this, scope='cross_domain'; else 'domain' (default: 10)",
    )
    parser.add_argument(
        "--output",
        required=True,
        metavar="PATH",
        help="Output YAML file path, e.g. knowledge/sources/finance/_shared/resources.yaml",
    )
    parser.add_argument(
        "--base-dir",
        default=None,
        metavar="DIR",
        help=(
            "Project root directory. Defaults to parent of the 'scripts/' folder "
            "containing this script, or CWD if not applicable."
        ),
    )
    return parser.parse_args()


def resolve_base_dir(args: argparse.Namespace) -> Path:
    if args.base_dir:
        return Path(args.base_dir).resolve()
    # Try to resolve relative to this script's grandparent (project root)
    script_dir = Path(__file__).resolve().parent
    candidate = script_dir.parent
    if (candidate / "knowledge").exists():
        return candidate
    # Fallback to CWD
    return Path.cwd()


def main() -> None:
    args = parse_args()
    base_dir = resolve_base_dir(args)

    domain_dir = base_dir / "knowledge" / "sources" / args.domain
    if not domain_dir.exists():
        print(f"[error] Domain directory not found: {domain_dir}", file=sys.stderr)
        sys.exit(1)

    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = base_dir / output_path

    slots_path = output_path.parent / "replaceable_slots.yaml"

    # Scan
    print(f"[scan] Scanning blueprints in {domain_dir} ...")
    resource_records, slot_records, bp_count, total_resource_entries, total_slot_entries = (
        scan_blueprints(domain_dir)
    )
    print(
        f"[scan] Found {bp_count} blueprints, {total_resource_entries} resource entries, {total_slot_entries} slot entries."
    )

    # Build pool + slots
    pool, slots = build_pool_and_slots(
        records=resource_records,
        slot_records=slot_records,
        min_shared=args.min_shared,
        cross_domain_threshold=args.cross_domain_threshold,
        domain=args.domain,
        bp_count=bp_count,
        total_resource_entries=total_resource_entries,
        total_slot_entries=total_slot_entries,
    )

    # Print stats
    print_stats(pool, slots)

    # Write pool output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        yaml.dump(
            pool,
            f,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
            width=120,
        )

    print(f"[output] Pool written to     : {output_path}")
    print(f"[output] Pool file size      : {output_path.stat().st_size:,} bytes")

    # Write slots output
    with slots_path.open("w", encoding="utf-8") as f:
        yaml.dump(
            slots,
            f,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
            width=120,
        )

    print(f"[output] Slots written to    : {slots_path}")
    print(f"[output] Slots file size     : {slots_path.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
