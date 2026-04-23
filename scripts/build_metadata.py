#!/usr/bin/env python3
"""build_metadata.py — Reconcile skill bilingual metadata status.

Reads:
    scripts/naming_map.py       (73 locked slug mapping)
    scripts/descriptions_map.py (70 LLM-generated 中文 descriptions)
    scripts/skill_metadata.yaml (human-locked bilingual entries)

Reports:
    - Which slugs have full metadata (all 7 fields) → ready to publish
    - Which slugs have partial material (description_zh only) → batch-generate
    - Which slugs have nothing → need full LLM pipeline

NOTE: this tool does NOT generate content. LLM batch generation is an
offline task (see skill_metadata.yaml footer for the pipeline stub).
This tool only surfaces what is missing so the human can decide scope.

Usage:
    python3 scripts/build_metadata.py

Exit code 0 = reconcile report printed. Never fails.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

from descriptions_map import FINAL_DESCRIPTIONS  # noqa: E402
from naming_map import FINAL_SLUG_MAP  # noqa: E402

REQUIRED_FIELDS = (
    "bp_id",
    "name_zh",
    "name_en",
    "tagline_zh",
    "tagline_en",
    "description_zh",
    "description_en",
    "triggers",
    "tags",
)


def _load_locked_metadata() -> dict[str, dict]:
    path = SCRIPTS_DIR / "skill_metadata.yaml"
    if not path.exists():
        return {}
    with path.open() as f:
        data = yaml.safe_load(f) or {}
    return data.get("skills") or {}


def main() -> int:
    all_slugs = set(FINAL_SLUG_MAP.values())
    locked = _load_locked_metadata()
    described = set(FINAL_DESCRIPTIONS.keys())

    # Categorize
    full = []
    partial_desc_only = []
    nothing = []
    field_gaps: dict[str, list[str]] = {}

    for slug in sorted(all_slugs):
        if slug in locked:
            entry = locked[slug]
            missing = [f for f in REQUIRED_FIELDS if f not in entry]
            if missing:
                field_gaps[slug] = missing
            else:
                full.append(slug)
        elif slug in described:
            partial_desc_only.append(slug)
        else:
            nothing.append(slug)

    # Report
    print("=" * 72)
    print("Doramagic skill bilingual metadata reconcile")
    print("=" * 72)
    print(f"Total slugs (naming_map.FINAL_SLUG_MAP): {len(all_slugs)}")
    print(f"Locked metadata (skill_metadata.yaml):  {len(locked)}")
    print(f"LLM-generated 中文 descriptions only:   {len(partial_desc_only)}")
    print(f"Nothing yet (no description, no lock):  {len(nothing)}")
    print()
    print(f"Ready to publish ({len(full)}):")
    for s in full:
        print(f"  ✓ {s}")
    if field_gaps:
        print(f"\nLocked but missing fields ({len(field_gaps)}):")
        for s, miss in field_gaps.items():
            print(f"  ! {s}: missing {miss}")
    if partial_desc_only:
        print(f"\nHas description_zh, missing rest ({len(partial_desc_only)}):")
        for s in partial_desc_only[:10]:
            print(f"  ~ {s}")
        if len(partial_desc_only) > 10:
            print(f"  ... +{len(partial_desc_only) - 10} more")
    if nothing:
        print(f"\nNo material at all ({len(nothing)}):")
        for s in nothing:
            print(f"  · {s}")

    print()
    print("Next action: LLM-batch-generate partial entries + human review.")
    print("See skill_metadata.yaml footer for pipeline notes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
