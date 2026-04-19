#!/usr/bin/env python3
"""Extract project fingerprint from blueprint for domain-knowledge selection (Stage 2.1).

Reads {blueprint_dir}/LATEST.yaml + LATEST.jsonl and emits project_fingerprint.json
under {blueprint_dir}/crystal_inputs/. Pure rules, no LLM.

The fingerprint is consumed by downstream selection steps to recall suitable
domain-universal resources and constraints from the domain pool.

Usage:
    python3 extract_project_fingerprint.py \\
        --blueprint-dir knowledge/sources/finance/finance-bp-009--zvt
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

try:
    import yaml
except ImportError:
    print("[error] PyYAML required. pip install pyyaml", file=sys.stderr)
    sys.exit(2)


_VERSION_SPEC_RE = re.compile(r"[=<>!~].*$")


def _normalize_package_name(raw: str) -> str:
    """Strip version specifier. 'pandas==2.2.3' -> 'pandas'."""
    name = raw.strip()
    name = _VERSION_SPEC_RE.sub("", name).strip()
    return name


def _extract_stack(bp: dict) -> list[str]:
    """Declared python packages (normalized, deduped, sorted)."""
    names: set[str] = set()
    for r in bp.get("resources") or []:
        if r.get("type") in ("python_package", "dependency"):
            raw = r.get("name") or ""
            norm = _normalize_package_name(raw)
            if norm:
                names.add(norm)
    return sorted(names)


def _extract_sub_scenes(bp: dict) -> list[str]:
    """Stage IDs + applicability.task_type tokens."""
    scenes: list[str] = []
    for s in bp.get("stages") or []:
        sid = s.get("id")
        if sid:
            scenes.append(sid)
    # Deduped, order-preserved
    seen: set[str] = set()
    out: list[str] = []
    for s in scenes:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def _extract_keywords(bp: dict, field: str, top_k: int | None = None) -> list[str]:
    """Aggregate known_use_cases[].{intent,negative}_keywords. Return all unique by
    frequency (Top-K ordered). When top_k is None, keep the full unique set so
    low-frequency but high-signal keywords are not truncated away."""
    counter: Counter[str] = Counter()
    for uc in bp.get("known_use_cases") or []:
        for kw in uc.get(field) or []:
            if isinstance(kw, str):
                counter[kw.strip().lower()] += 1
    most = counter.most_common(top_k) if top_k is not None else counter.most_common()
    return [kw for kw, _cnt in most]


def _extract_applicability(bp: dict) -> dict:
    app = bp.get("applicability") or {}
    return {
        "domain": app.get("domain", ""),
        "task_type": app.get("task_type", ""),
        "description": app.get("description", ""),
    }


def _extract_constraint_fingerprints(cons_path: Path) -> tuple[list[str], list[str]]:
    """Return (ids, hashes) from project constraints."""
    ids: list[str] = []
    hashes: list[str] = []
    with cons_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                c = json.loads(line)
            except json.JSONDecodeError:
                continue
            cid = c.get("id")
            chash = c.get("hash")
            if cid:
                ids.append(cid)
            if chash:
                hashes.append(chash)
    return ids, hashes


def build_fingerprint(blueprint_dir: Path) -> dict:
    bp_path = blueprint_dir / "LATEST.yaml"
    cons_path = blueprint_dir / "LATEST.jsonl"
    with bp_path.open() as f:
        bp = yaml.safe_load(f) or {}

    ids, hashes = _extract_constraint_fingerprints(cons_path)
    fingerprint = {
        "bp_id": bp.get("id", blueprint_dir.name),
        "bp_name": bp.get("name", ""),
        "applicability": _extract_applicability(bp),
        "stack": _extract_stack(bp),
        "sub_scenes": _extract_sub_scenes(bp),
        "intent_keywords": _extract_keywords(bp, "intent_keywords"),
        "negative_keywords": _extract_keywords(bp, "negative_keywords"),
        "declared_constraint_ids": ids,
        "declared_constraint_hashes": hashes,
        "extracted_at": datetime.now(UTC).isoformat(),
    }
    return fingerprint


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blueprint-dir", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output path. Default: {blueprint-dir}/crystal_inputs/project_fingerprint.json",
    )
    args = parser.parse_args()

    if not args.blueprint_dir.is_dir():
        print(f"[error] blueprint-dir not found: {args.blueprint_dir}", file=sys.stderr)
        return 2

    fingerprint = build_fingerprint(args.blueprint_dir)

    out_path = args.output or (args.blueprint_dir / "crystal_inputs" / "project_fingerprint.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(fingerprint, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[done] fingerprint: {out_path}")
    print(f"  bp_id:              {fingerprint['bp_id']}")
    print(f"  stack:              {len(fingerprint['stack'])} python packages")
    print(f"  sub_scenes:         {len(fingerprint['sub_scenes'])} stages")
    print(f"  intent_keywords:    {len(fingerprint['intent_keywords'])} unique")
    print(f"  negative_keywords:  {len(fingerprint['negative_keywords'])} unique")
    print(
        f"  declared_constraints: {len(fingerprint['declared_constraint_ids'])} ids, "
        f"{len(fingerprint['declared_constraint_hashes'])} hashes"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
