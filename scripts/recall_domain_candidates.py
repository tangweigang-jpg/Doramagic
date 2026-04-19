#!/usr/bin/env python3
"""Recall suitable domain resources + constraints for a project (Stage 2.2).

Inputs:
  - project_fingerprint.json  (from extract_project_fingerprint.py)
  - resources_full.yaml       (876 domain resource pool entries)
  - _opus_output_needs_review.jsonl  (268 opus-confirmed universal constraint judgments)
  - constraints_audit_v5_merged.jsonl  (17524 constraint content rows, keyed by hash)

Outputs (to {fingerprint-parent-dir}/crystal_inputs/):
  - candidates_resources.yaml   (Top-K python_package entries, deduped against project stack)
  - candidates_constraints.jsonl  (Top-K universal constraints, deduped against project ids)

Recall is rule-based, no LLM. Score signals are emitted alongside each candidate
under `_recall_score` to support Stage 2.3 LLM judging and manual audit.

Usage:
    python3 recall_domain_candidates.py \\
        --fingerprint <path-to-project_fingerprint.json>
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


# ============================================================
# Weights (tunable, baked here for auditability)
# ============================================================

_MIN_TOKEN_LEN = 3  # skip matches for 1-2 char tokens ("ta", "re", "os") to avoid false hits


def _word_match(token: str, text: str) -> bool:
    """Word-boundary substring match. Returns True if token appears as whole word(s)."""
    token = (token or "").strip()
    if not token or len(token) < _MIN_TOKEN_LEN:
        return False
    pattern = r"\b" + re.escape(token) + r"\b"
    return bool(re.search(pattern, text))


_KIND_WEIGHT: dict[str, int] = {
    "domain_rule": 3,
    "architecture_guardrail": 2,
    "resource_boundary": 2,
    "claim_boundary": 2,
    "operational_lesson": 1,
    "rationalization_guard": 1,
}
_SEVERITY_WEIGHT: dict[str, int] = {"fatal": 3, "high": 2, "medium": 1, "low": 0}


# ============================================================
# Loaders
# ============================================================


def _load_fingerprint(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_resources_pool(path: Path) -> list[dict]:
    with path.open() as f:
        data = yaml.safe_load(f) or {}
    return data.get("resources") or []


def _load_universal_hashes(opus_path: Path) -> set[str]:
    hashes: set[str] = set()
    with opus_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if r.get("_opus_classification", {}).get("class") == "universal":
                h = r.get("hash")
                if h:
                    hashes.add(h)
    return hashes


def _load_constraint_contents(audit_path: Path, target_hashes: set[str]) -> dict[str, dict]:
    """Build hash → full constraint row, limited to target hashes."""
    out: dict[str, dict] = {}
    with audit_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            h = r.get("hash")
            if h in target_hashes and h not in out:
                out[h] = r
    return out


# ============================================================
# Scoring
# ============================================================


def _score_resource(entry: dict, fp: dict) -> dict:
    """Return score breakdown for a single resource entry. Higher = more suitable."""
    signals: dict[str, int] = {}
    signals["scope_cross_domain"] = 2 if entry.get("scope") == "cross_domain" else 0

    used_by = entry.get("used_by") or []
    signals["popularity"] = min(5, len(used_by))

    name_lower = (entry.get("name") or "").lower()
    desc_lower = (entry.get("description") or "").lower()
    text = f"{name_lower} {desc_lower}"
    intent_kws = [kw for kw in fp.get("intent_keywords") or [] if kw]
    kw_hits = sum(1 for kw in intent_kws if _word_match(kw, text))
    signals["intent_keyword_hits"] = min(3, kw_hits) * 3

    # Applicability text resonance — word-boundary match avoids "ta" hitting "data"
    app_text = " ".join(
        [
            (fp.get("applicability") or {}).get("task_type", ""),
            (fp.get("applicability") or {}).get("description", ""),
        ]
    ).lower()
    signals["task_type_resonance"] = 2 if _word_match(name_lower, app_text) else 0

    signals["total"] = sum(signals.values())
    return signals


def _score_constraint(row: dict, fp: dict) -> dict:
    core = row.get("core") or {}
    when_text = (core.get("when") or "").lower()
    action_text = (core.get("action") or "").lower()
    blob = f"{when_text} {action_text}"

    signals: dict[str, int] = {}

    # Stage overlap (often empty for universal, but when present it is strong)
    applies = row.get("applies_to") or {}
    cons_stages = set(applies.get("stage_ids") or [])
    fp_stages = set(fp.get("sub_scenes") or [])
    signals["stage_overlap"] = 3 * len(cons_stages & fp_stages)

    # Intent keyword presence in when/action text (word-boundary match)
    intent_kws = [kw for kw in fp.get("intent_keywords") or [] if kw]
    kw_hits = sum(1 for kw in intent_kws if _word_match(kw, blob))
    signals["intent_keyword_hits"] = min(4, kw_hits) * 2

    # Stack mention in when/action (e.g., "pandas DataFrame")
    stack = [s.lower() for s in fp.get("stack") or []]
    stack_hits = sum(1 for s in stack if _word_match(s, blob))
    signals["stack_mentions"] = min(3, stack_hits)

    # Constraint kind weight
    ckind = row.get("constraint_kind") or ""
    signals["kind_weight"] = _KIND_WEIGHT.get(ckind, 0)

    # Severity weight
    sev = row.get("severity") or ""
    signals["severity_weight"] = _SEVERITY_WEIGHT.get(sev, 0)

    signals["total"] = sum(signals.values())
    return signals


# ============================================================
# Recall
# ============================================================


def recall_resources(pool: list[dict], fp: dict, top_k: int) -> tuple[list[dict], dict[str, int]]:
    declared_stack_lower = {s.lower() for s in fp.get("stack") or [] if s}
    name_dedup: set[str] = set()
    scored: list[tuple[int, dict, dict]] = []
    stats = Counter()

    for entry in pool:
        stats["total_pool"] += 1
        if entry.get("kind") != "python_package":
            stats["filter_not_python_package"] += 1
            continue
        name = (entry.get("name") or "").strip()
        if not name:
            stats["filter_no_name"] += 1
            continue
        if name.lower() in declared_stack_lower:
            stats["filter_already_declared"] += 1
            continue
        if name in name_dedup:
            stats["filter_duplicate_name"] += 1
            continue
        name_dedup.add(name)
        score = _score_resource(entry, fp)
        scored.append((score["total"], entry, score))
        stats["eligible"] += 1

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:top_k]
    return [{**entry, "_recall_score": score} for _s, entry, score in top], dict(stats)


def recall_constraints(
    opus_universal_hashes: set[str],
    content_map: dict[str, dict],
    fp: dict,
    top_k: int,
) -> tuple[list[dict], dict[str, int]]:
    declared_hashes = set(fp.get("declared_constraint_hashes") or [])
    scored: list[tuple[int, dict, dict]] = []
    stats = Counter()
    stats["opus_universal"] = len(opus_universal_hashes)

    for h in opus_universal_hashes:
        row = content_map.get(h)
        if row is None:
            stats["filter_no_content"] += 1
            continue
        # Dedup by content hash (not id — ids collide across BPs: bp-004's
        # finance-C-001 is a different rule from bp-009's finance-C-001).
        if h in declared_hashes:
            stats["filter_already_declared"] += 1
            continue
        score = _score_constraint(row, fp)
        scored.append((score["total"], row, score))
        stats["eligible"] += 1

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:top_k]
    # Strip internal `_classification` noise; keep opus decision as provenance
    out: list[dict] = []
    for _s, row, score in top:
        clean = {k: v for k, v in row.items() if k != "_classification"}
        clean["_recall_score"] = score
        out.append(clean)
    return out, dict(stats)


# ============================================================
# Main
# ============================================================

_DEFAULT_POOL = Path("knowledge/sources/finance/_shared/resources_full.yaml")
_DEFAULT_OPUS = Path("knowledge/sources/finance/_shared/_opus_output_needs_review.jsonl")
_DEFAULT_AUDIT = Path("knowledge/sources/finance/_shared/constraints_audit_v5_merged.jsonl")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fingerprint", type=Path, required=True)
    parser.add_argument("--resources-pool", type=Path, default=_DEFAULT_POOL)
    parser.add_argument("--opus-reviewed", type=Path, default=_DEFAULT_OPUS)
    parser.add_argument("--constraints-audit", type=Path, default=_DEFAULT_AUDIT)
    parser.add_argument("--top-resources", type=int, default=40)
    parser.add_argument("--top-constraints", type=int, default=60)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Default: parent dir of --fingerprint",
    )
    args = parser.parse_args()

    for label, p in [
        ("fingerprint", args.fingerprint),
        ("resources-pool", args.resources_pool),
        ("opus-reviewed", args.opus_reviewed),
        ("constraints-audit", args.constraints_audit),
    ]:
        if not p.exists():
            print(f"[error] {label} not found: {p}", file=sys.stderr)
            return 2

    fp = _load_fingerprint(args.fingerprint)
    pool = _load_resources_pool(args.resources_pool)
    opus_hashes = _load_universal_hashes(args.opus_reviewed)
    content_map = _load_constraint_contents(args.constraints_audit, opus_hashes)

    top_res, res_stats = recall_resources(pool, fp, args.top_resources)
    top_cons, cons_stats = recall_constraints(opus_hashes, content_map, fp, args.top_constraints)

    out_dir = args.output_dir or args.fingerprint.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    res_path = out_dir / "candidates_resources.yaml"
    cons_path = out_dir / "candidates_constraints.jsonl"

    res_doc = {
        "meta": {
            "bp_id": fp.get("bp_id"),
            "generated_at": datetime.now(UTC).isoformat(),
            "source_pool": str(args.resources_pool),
            "top_k": args.top_resources,
            "stats": res_stats,
        },
        "resources": top_res,
    }
    res_path.write_text(
        yaml.safe_dump(res_doc, sort_keys=False, allow_unicode=True, default_flow_style=False),
        encoding="utf-8",
    )

    with cons_path.open("w", encoding="utf-8") as f:
        meta = {
            "_meta": {
                "bp_id": fp.get("bp_id"),
                "generated_at": datetime.now(UTC).isoformat(),
                "source_opus": str(args.opus_reviewed),
                "source_audit": str(args.constraints_audit),
                "top_k": args.top_constraints,
                "stats": cons_stats,
            }
        }
        f.write(json.dumps(meta, ensure_ascii=False) + "\n")
        for row in top_cons:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"[done] resources candidates:   {res_path}")
    print(f"       stats: {res_stats}")
    print(f"[done] constraints candidates: {cons_path}")
    print(f"       stats: {cons_stats}")
    if top_res:
        tops = ", ".join(f"{r['name']}({r['_recall_score']['total']})" for r in top_res[:3])
        print(f"       top-3 resources: {tops}")
    if top_cons:
        tops = ", ".join(f"{c['id']}({c['_recall_score']['total']})" for c in top_cons[:3])
        print(f"       top-3 constraints: {tops}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
