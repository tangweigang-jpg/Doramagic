#!/usr/bin/env python3
"""Finalize per-project domain injection files (Stage 2.4).

Reads scored_constraints.jsonl + scored_resources.yaml (output of Stage 2.3
sonnet scoring) from {bp-dir}/crystal_inputs/, applies Top-K cut and an
optional human drop-list from CEO terminal review, strips internal metadata,
and writes compiler-ready files:

  - domain_constraints.jsonl  (flat JSONL, same shape as LATEST.jsonl)
  - domain_resources.yaml     (same shape as _shared/resources_full.yaml)

These are consumed by compile_crystal_skeleton.py via --domain-constraints and
--domain-resources CLI flags.

Usage:
    python3 finalize_domain_injection.py --bp-dir <path>
    python3 finalize_domain_injection.py --bp-dir <path> \\
        --drop-constraints 2,7,9 --drop-resources 3
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

_ID_RE = re.compile(r"^([a-z]+)-C-(\d+)$")

try:
    import yaml
except ImportError:
    print("[error] PyYAML required", file=sys.stderr)
    sys.exit(2)


def _parse_drop_list(spec: str | None) -> set[int]:
    if not spec or spec.strip().lower() in ("", "none"):
        return set()
    out: set[int] = set()
    for tok in spec.split(","):
        tok = tok.strip()
        if not tok:
            continue
        try:
            out.add(int(tok))
        except ValueError:
            print(f"[warn] ignoring non-integer drop token: {tok!r}", file=sys.stderr)
    return out


def _load_scored_constraints(path: Path) -> list[dict]:
    out: list[dict] = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if "_meta" in row:
                continue
            out.append(row)
    return out


def _load_scored_resources(path: Path) -> list[dict]:
    with path.open() as f:
        data = yaml.safe_load(f) or {}
    return data.get("resources") or []


def _select_top(
    entries: list[dict], top_k: int, drop_1based: set[int]
) -> tuple[list[dict], list[int]]:
    """Return (kept entries, dropped 1-based indices)."""
    passed = [e for e in entries if e.get("_sonnet_score", {}).get("passed")]
    passed.sort(key=lambda e: e["_sonnet_score"]["total"], reverse=True)
    top = passed[:top_k]
    kept: list[dict] = []
    dropped: list[int] = []
    for i, e in enumerate(top, 1):
        if i in drop_1based:
            dropped.append(i)
        else:
            kept.append(e)
    return kept, dropped


def _strip_meta(row: dict, strip_keys: tuple[str, ...]) -> dict:
    return {k: v for k, v in row.items() if k not in strip_keys}


def _renumber_constraint(row: dict, new_idx: int, id_offset: int) -> dict:
    """Reassign id to avoid collision with project-declared ids.

    Original audit rows use the domain-prefix + sequential number (e.g.,
    `finance-C-026`). Because every BP produces constraints in the same
    numeric range, the same id string appears across BPs for completely
    different rules — which makes it unsafe for the compiler's id-based
    collision filter. We shift domain ids into a reserved range
    ({offset}+idx) and keep the original id in `_domain_provenance`
    for audit."""
    original_id = row.get("id", "")
    m = _ID_RE.match(original_id)
    prefix = m.group(1) if m else "finance"
    new_id = f"{prefix}-C-{id_offset + new_idx}"
    out = dict(row)
    out["id"] = new_id
    out["_domain_provenance"] = {
        "original_id": original_id,
        "original_hash": row.get("hash", ""),
        "source_blueprint": row.get("source_blueprint") or "unknown",
    }
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bp-dir", type=Path, required=True)
    parser.add_argument("--top-constraints", type=int, default=15)
    parser.add_argument("--top-resources", type=int, default=10)
    parser.add_argument(
        "--drop-constraints",
        type=str,
        default="",
        help="Comma-separated 1-based indices to drop from Top-K constraints (e.g. '2,7,9')",
    )
    parser.add_argument(
        "--drop-resources",
        type=str,
        default="",
        help="Comma-separated 1-based indices to drop from Top-K resources",
    )
    parser.add_argument(
        "--id-offset",
        type=int,
        default=9000,
        help="Domain constraint ids are shifted to {prefix}-C-{offset+idx} "
        "to avoid collision with project ids (default: 9000)",
    )
    args = parser.parse_args()

    inputs_dir = args.bp_dir / "crystal_inputs"
    c_path = inputs_dir / "scored_constraints.jsonl"
    r_path = inputs_dir / "scored_resources.yaml"
    for p in [c_path, r_path]:
        if not p.exists():
            print(f"[error] missing: {p}", file=sys.stderr)
            return 2

    scored_cons = _load_scored_constraints(c_path)
    scored_res = _load_scored_resources(r_path)

    drop_c = _parse_drop_list(args.drop_constraints)
    drop_r = _parse_drop_list(args.drop_resources)

    kept_cons, dropped_cons = _select_top(scored_cons, args.top_constraints, drop_c)
    kept_res, dropped_res = _select_top(scored_res, args.top_resources, drop_r)

    strip_cons_keys = ("_recall_score", "_sonnet_score")
    strip_res_keys = ("_recall_score", "_sonnet_score")

    # Write domain_constraints.jsonl (no meta line — matches LATEST.jsonl shape)
    # Renumber ids to shifted range to avoid collision with project's ids.
    out_cons = inputs_dir / "domain_constraints.jsonl"
    with out_cons.open("w", encoding="utf-8") as f:
        for i, row in enumerate(kept_cons, 1):
            renumbered = _renumber_constraint(row, i, args.id_offset)
            clean = _strip_meta(renumbered, strip_cons_keys)
            f.write(json.dumps(clean, ensure_ascii=False) + "\n")

    # Write domain_resources.yaml (meta block + resources array)
    out_res = inputs_dir / "domain_resources.yaml"
    doc = {
        "meta": {
            "bp_id": args.bp_dir.name,
            "finalized_at": datetime.now(UTC).isoformat(),
            "source_scored_constraints": str(c_path.name),
            "source_scored_resources": str(r_path.name),
            "top_k_constraints": args.top_constraints,
            "top_k_resources": args.top_resources,
            "dropped_constraints_indices": sorted(dropped_cons),
            "dropped_resources_indices": sorted(dropped_res),
            "final_count_constraints": len(kept_cons),
            "final_count_resources": len(kept_res),
        },
        "resources": [_strip_meta(r, strip_res_keys) for r in kept_res],
    }
    out_res.write_text(
        yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, default_flow_style=False),
        encoding="utf-8",
    )

    print(f"[done] domain_constraints.jsonl: {out_cons}  ({len(kept_cons)} entries)")
    if dropped_cons:
        print(f"       dropped constraints (1-based): {sorted(dropped_cons)}")
    print(f"[done] domain_resources.yaml:    {out_res}  ({len(kept_res)} entries)")
    if dropped_res:
        print(f"       dropped resources (1-based): {sorted(dropped_res)}")
    print()
    print("Next: compile treatment crystal via:")
    print(
        f"  python3 scripts/compile_crystal_skeleton.py \\\n"
        f"    --blueprint-dir {args.bp_dir} \\\n"
        f"    --domain-constraints {out_cons} \\\n"
        f"    --domain-resources {out_res} \\\n"
        f"    --output-seed {args.bp_dir}/{args.bp_dir.name}-v5.3-treatment.seed.yaml \\\n"
        f"    --target-host openclaw --sop-version crystal-compilation-v5.3"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
