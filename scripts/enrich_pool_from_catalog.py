#!/usr/bin/env python3
"""enrich_pool_from_catalog.py — 用 public_apis catalog 增强资源池 external_service 条目

对池中 kind == "external_service" 的条目按 name 做模糊匹配到 catalog apis[].name，
匹配成功则注入 catalog_metadata 字段。幂等（重跑覆写旧 catalog_metadata）。

用法:
    python scripts/enrich_pool_from_catalog.py \\
        --pool knowledge/sources/finance/_shared/resources.yaml \\
        --catalog knowledge/catalogs/public_apis.yaml \\
        --output knowledge/sources/finance/_shared/resources.yaml

输出:
    - 就地更新 resources.yaml（pool 文件）
    - stdout 匹配统计

退出码:
    0  成功
    1  输入错误
    2  依赖缺失
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("[error] PyYAML not installed. Run: pip install pyyaml", file=sys.stderr)
    sys.exit(2)


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------

_PUNCT_RE = re.compile(r"[^\w\s]")
_WHITESPACE_RE = re.compile(r"\s+")

# Common noise tokens to strip for fuzzy match
_STOP_TOKENS = frozenset(
    [
        "api",
        "apis",
        "the",
        "a",
        "an",
        "service",
        "services",
        "data",
        "feed",
        "provider",
        "platform",
        "finance",
        "financial",
        "market",
        "markets",
        "trading",
        "exchange",
    ]
)


def normalize(name: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    name = name.lower()
    name = _PUNCT_RE.sub(" ", name)
    name = _WHITESPACE_RE.sub(" ", name).strip()
    return name


def tokenize(name: str) -> set[str]:
    """Tokenize normalized name, removing stop tokens."""
    tokens = set(normalize(name).split())
    return tokens - _STOP_TOKENS


def fuzzy_score(pool_name: str, catalog_name: str) -> float:
    """Return a similarity score in [0, 1].

    Strategy:
    1. Exact normalized match → 1.0
    2. One is a substring of the other (normalized) → 0.85
    3. Token overlap Jaccard (after stop-token removal) → Jaccard score (0..1)
    """
    pn = normalize(pool_name)
    cn = normalize(catalog_name)

    if pn == cn:
        return 1.0
    if pn in cn or cn in pn:
        return 0.85

    pt = tokenize(pool_name)
    ct = tokenize(catalog_name)
    if not pt or not ct:
        return 0.0
    intersection = len(pt & ct)
    union = len(pt | ct)
    return intersection / union if union > 0 else 0.0


# ---------------------------------------------------------------------------
# Core matching
# ---------------------------------------------------------------------------

MATCH_THRESHOLD = 0.5  # minimum score to accept a match


def build_catalog_index(catalog_apis: list[dict]) -> list[tuple[str, dict]]:
    """Return list of (normalized_name, api_dict) for fast scoring."""
    return [(normalize(api.get("name", "")), api) for api in catalog_apis if api.get("name")]


def match_pool_entry(pool_name: str, catalog_index: list[tuple[str, dict]]) -> dict | None:
    """Find best catalog match for pool_name, or None if below threshold."""
    best_score = 0.0
    best_api: dict | None = None

    pn_norm = normalize(pool_name)

    for cn_norm, api in catalog_index:
        # Fast-path: exact match
        if pn_norm == cn_norm:
            return api

        score = fuzzy_score(pool_name, api.get("name", ""))
        if score > best_score:
            best_score = score
            best_api = api

    if best_score >= MATCH_THRESHOLD:
        return best_api
    return None


def enrich_pool(pool_doc: dict, catalog_doc: dict) -> tuple[dict, dict]:
    """Enrich pool external_service entries with catalog_metadata.

    Returns:
        (enriched_pool_doc, stats_dict)
    """
    catalog_apis: list[dict] = catalog_doc.get("apis", [])
    catalog_index = build_catalog_index(catalog_apis)

    resources = pool_doc.get("resources", [])
    external_service_entries = [r for r in resources if r.get("kind") == "external_service"]

    matched: list[str] = []
    unmatched: list[str] = []

    for entry in resources:
        if entry.get("kind") != "external_service":
            continue

        pool_name = entry.get("name", "")
        best_api = match_pool_entry(pool_name, catalog_index)

        if best_api:
            entry["catalog_metadata"] = {
                "catalog_name": best_api.get("name"),
                "category": best_api.get("category"),
                "url": best_api.get("url"),
                "free_status": best_api.get("free_status"),
                "auth": best_api.get("auth"),
                "https": best_api.get("https"),
                "cors": best_api.get("cors"),
                "description_zh": best_api.get("description_zh"),
            }
            matched.append(pool_name)
        else:
            entry["catalog_metadata"] = None
            unmatched.append(pool_name)

    stats = {
        "total_external_service": len(external_service_entries),
        "matched": len(matched),
        "unmatched": len(unmatched),
        "match_rate": len(matched) / len(external_service_entries)
        if external_service_entries
        else 0.0,
        "matched_names": matched,
        "unmatched_names": unmatched,
    }

    return pool_doc, stats


def print_stats(stats: dict) -> None:
    total = stats["total_external_service"]
    matched = stats["matched"]
    rate = stats["match_rate"] * 100

    print("\n" + "=" * 60)
    print("  Catalog Enrichment — Summary")
    print("=" * 60)
    print(f"  Pool external_service entries : {total}")
    print(f"  Catalog matched               : {matched}")
    print(f"  Unmatched                     : {stats['unmatched']}")
    print(f"  Match rate                    : {rate:.1f}%")

    top5_matched = stats["matched_names"][:5]
    if top5_matched:
        print("\n  Top 5 matched:")
        for name in top5_matched:
            print(f"    + {name}")

    top5_unmatched = stats["unmatched_names"][:5]
    if top5_unmatched:
        print("\n  Top 5 unmatched:")
        for name in top5_unmatched:
            print(f"    - {name}")

    print("=" * 60 + "\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Enrich pool external_service entries with public_apis catalog metadata.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--pool", required=True, metavar="YAML", help="Path to resources.yaml (pool)"
    )
    parser.add_argument(
        "--catalog", required=True, metavar="YAML", help="Path to public_apis.yaml (catalog)"
    )
    parser.add_argument(
        "--output", required=True, metavar="PATH", help="Output YAML path (can be same as --pool)"
    )
    parser.add_argument("--base-dir", default=None, metavar="DIR", help="Project root directory")
    return parser.parse_args()


def resolve_base_dir(args: argparse.Namespace) -> Path:
    if args.base_dir:
        return Path(args.base_dir).resolve()
    script_dir = Path(__file__).resolve().parent
    candidate = script_dir.parent
    if (candidate / "knowledge").exists():
        return candidate
    return Path.cwd()


def main() -> None:
    args = parse_args()
    base_dir = resolve_base_dir(args)

    pool_path = Path(args.pool)
    if not pool_path.is_absolute():
        pool_path = base_dir / pool_path

    catalog_path = Path(args.catalog)
    if not catalog_path.is_absolute():
        catalog_path = base_dir / catalog_path

    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = base_dir / output_path

    for p, label in [(pool_path, "pool"), (catalog_path, "catalog")]:
        if not p.exists():
            print(f"[error] {label} file not found: {p}", file=sys.stderr)
            sys.exit(1)

    print(f"[enrich] Loading pool from {pool_path} ...")
    with pool_path.open(encoding="utf-8") as f:
        pool_doc = yaml.safe_load(f) or {}

    print(f"[enrich] Loading catalog from {catalog_path} ...")
    with catalog_path.open(encoding="utf-8") as f:
        catalog_doc = yaml.safe_load(f) or {}

    catalog_size = len(catalog_doc.get("apis", []))
    print(f"[enrich] Catalog has {catalog_size} APIs.")

    pool_doc, stats = enrich_pool(pool_doc, catalog_doc)
    print_stats(stats)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        yaml.dump(
            pool_doc,
            f,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
            width=120,
        )

    size = output_path.stat().st_size
    print(f"[output] Written to : {output_path}")
    print(f"[output] File size  : {size:,} bytes")

    # Final one-liner summary
    total = stats["total_external_service"]
    matched = stats["matched"]
    rate = stats["match_rate"] * 100
    print(
        f"\n[summary] pool external_service 共 {total} 条，catalog 匹配成功 {matched} 条，匹配率 {rate:.1f}%"
    )


if __name__ == "__main__":
    main()
