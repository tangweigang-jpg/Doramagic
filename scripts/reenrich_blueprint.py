#!/usr/bin/env python3
"""P0-A re-enrichment script: apply Bug B/C/D2 fixes to 5 finance blueprints.

Zero LLM calls. Reads existing artifacts, calls enrich_blueprint() with the
fixed code (f74ada2), writes new versioned blueprint + updates LATEST.yaml and
manifest.json.

Usage:
    .venv/bin/python scripts/reenrich_blueprint.py finance-bp-079
    .venv/bin/python scripts/reenrich_blueprint.py --all
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Add packages to sys.path
for pkg_dir in (PROJECT_ROOT / "packages").iterdir():
    if pkg_dir.is_dir():
        sys.path.insert(0, str(pkg_dir))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Target blueprints
TARGETS: list[tuple[str, str]] = [
    ("finance-bp-079", "akshare"),
    ("finance-bp-087", "qlib"),
    ("finance-bp-103", "ArcticDB"),
    ("finance-bp-124", "arch"),
    ("finance-bp-130", "tensortrade"),
]


def _discover_all_targets() -> list[tuple[str, str]]:
    """Scan knowledge/sources/finance/ and derive (bp_id, slug) from dir names.

    Directory layout: finance-bp-NNN--{slug}. Only returns bp dirs that also
    have _runs/{bp_id}/artifacts/ present (required for zero-LLM re-enrichment).
    """
    sources_root = PROJECT_ROOT / "knowledge" / "sources" / "finance"
    runs_root = PROJECT_ROOT / "_runs"
    targets: list[tuple[str, str]] = []
    for entry in sorted(sources_root.iterdir()):
        if not entry.is_dir():
            continue
        name = entry.name
        if not name.startswith("finance-bp-") or "--" not in name:
            continue
        bp_id, _, slug = name.partition("--")
        if not (runs_root / bp_id / "artifacts").is_dir():
            continue
        targets.append((bp_id, slug))
    return targets


def _repair_worker_resource_json(content: str) -> str:
    """Repair common MiniMax JSON output quirks in worker_resource.json.

    Fixes applied in order:
    1. bare integer followed by (text)" -- e.g. 1 (task_db)"
    2. null bytes and control characters
    3. dangling string value on next line (no key: prefix)
    4. double closing quotes before comma
    5. single-line extra string value (two comma-separated strings for one key)
    6. trailing commas before } or ]
    """
    # Fix 1: bare integer + (text)" -- e.g.: "key": 1 (task_db)",
    content = re.sub(
        r"(\"[\w_]+\"\s*:\s*)(\d+)\s+(\([^)]+\))\"",
        lambda m: m.group(1) + '"' + m.group(2) + " " + m.group(3) + '"',
        content,
    )
    # Fix 2: null bytes / control chars
    content = content.replace("\x00", "")
    content = re.sub(r"[\x01-\x08\x0b\x0c\x0e-\x1f]", "", content)
    # Fix 3: dangling second string value on next line (no key: prefix)
    content = re.sub(
        r'("[\w_]+":\s*"[^"]*"),\s*\n(\s+"[^"]+")\s*\n',
        lambda m: m.group(1)[:-1] + "; " + m.group(2).strip()[1:] + '",\n',
        content,
    )
    # Fix 4: double closing quotes: "value"",  -> "value",
    content = re.sub(r'"\"(,|\s*}|\s*\])', r'"\1', content)
    # Fix 5: extra string value on same line: "key": "val1", "val2",
    content = re.sub(
        r'("[\w_]+":\s*"[^"]*"),\s*("[^"]*")(,)',
        lambda m: m.group(1)[:-1] + "; " + m.group(2)[1:] + m.group(3),
        content,
    )
    # Fix 6: trailing commas before } or ]
    content = re.sub(r",\s*([}\]])", r"\1", content)
    return content


def _get_next_version(sources_dir: Path) -> int:
    """Find the next blueprint version number."""
    existing = sorted(sources_dir.glob("blueprint.v*.yaml"))
    if not existing:
        return 1
    versions = []
    for f in existing:
        name = f.stem  # "blueprint.v7"
        try:
            v = int(name.split(".v")[-1])
            versions.append(v)
        except ValueError:
            pass
    return max(versions, default=0) + 1


def reenrich_blueprint(bp_id: str, slug: str) -> dict:
    """Re-enrich one blueprint with the fixed enrich_blueprint() code.

    Returns a summary dict with verification results.
    """
    from doramagic_extraction_agent.sop.blueprint_enrich import enrich_blueprint
    from doramagic_extraction_agent.sop.schemas_v5 import BDExtractionResult
    from doramagic_extraction_agent.state.schema import AgentState

    runs_dir = PROJECT_ROOT / "_runs" / bp_id
    artifacts_dir = runs_dir / "artifacts"
    sources_dir = PROJECT_ROOT / "knowledge" / "sources" / "finance" / f"{bp_id}--{slug}"

    # Validate inputs
    assert artifacts_dir.exists(), f"artifacts dir missing: {artifacts_dir}"
    assert (artifacts_dir / "bd_list.json").exists(), f"bd_list.json missing in {artifacts_dir}"
    assert (artifacts_dir / "worker_resource.json").exists(), "worker_resource.json missing"
    assert sources_dir.exists(), f"sources dir missing: {sources_dir}"
    assert (sources_dir / "LATEST.yaml").exists(), f"LATEST.yaml missing in {sources_dir}"

    # ── 1. Load AgentState from _agent_state.json ──
    state_path = runs_dir / "_agent_state.json"
    if state_path.exists():
        raw_state = json.loads(state_path.read_text())
        state = AgentState(
            blueprint_id=raw_state.get("blueprint_id", bp_id),
            domain=raw_state.get("domain", "finance"),
            repo_path=raw_state.get("repo_path", ""),
            run_dir=raw_state.get("run_dir", str(runs_dir)),
            output_dir=raw_state.get("output_dir", str(sources_dir)),
            commit_hash=raw_state.get("commit_hash", ""),
            subdomain_labels=raw_state.get("subdomain_labels") or ["TRD"],
        )
    else:
        state = AgentState(
            blueprint_id=bp_id,
            domain="finance",
            run_dir=str(runs_dir),
            output_dir=str(sources_dir),
            subdomain_labels=["TRD"],
        )

    logger.info(
        "%s: state loaded — commit_hash=%s subdomain_labels=%s",
        bp_id,
        state.commit_hash[:12] if state.commit_hash else "N/A",
        state.subdomain_labels,
    )

    # ── 2. Load LATEST.yaml as base blueprint ──
    raw_yaml = (sources_dir / "LATEST.yaml").read_text(encoding="utf-8")
    bp: dict = yaml.safe_load(raw_yaml)
    assert isinstance(bp, dict), f"Expected mapping, got {type(bp)}"

    # ── 3. Clear fields that need to be regenerated ──
    # P11: clear audit_checklist_summary so it reruns with Bug D2 fix
    bp.pop("audit_checklist_summary", None)
    # P14: clear resources so P14 reruns with Bug B/C fix
    bp.pop("resources", None)
    bp.pop("global_resources", None)
    # P14: clear replaceable_slots so it reruns without duplicates
    bp.pop("replaceable_slots", None)

    # ── 4. Pre-repair worker_resource.json if needed ──
    wr_path = artifacts_dir / "worker_resource.json"
    wr_backup_path = artifacts_dir / "worker_resource.json.bak"
    wr_was_repaired = False
    if wr_path.exists():
        wr_content = wr_path.read_text(encoding="utf-8")
        try:
            json.loads(wr_content)  # quick check
            logger.info("%s: worker_resource.json is valid JSON", bp_id)
        except json.JSONDecodeError:
            repaired = _repair_worker_resource_json(wr_content)
            try:
                json.loads(repaired)
                # Write repaired version (back up original first)
                import shutil as _shutil

                _shutil.copy2(str(wr_path), str(wr_backup_path))
                wr_path.write_text(repaired, encoding="utf-8")
                wr_was_repaired = True
                logger.info("%s: worker_resource.json repaired (backup at .bak)", bp_id)
            except json.JSONDecodeError as e:
                logger.warning(
                    "%s: worker_resource.json repair failed (%s) — P14 may produce 0 resources",
                    bp_id,
                    e,
                )

    # ── 5. Load bd_list.json ──
    bd_result = BDExtractionResult.model_validate_json(
        (artifacts_dir / "bd_list.json").read_text(encoding="utf-8")
    )
    logger.info(
        "%s: bd_list.json loaded — %d decisions, %d missing",
        bp_id,
        len(bd_result.decisions),
        len(bd_result.missing_gaps),
    )

    # ── 6. Call enrich_blueprint() ──
    bp, patch_stats = enrich_blueprint(bp, bd_result, state, artifacts_dir)

    logger.info("%s: enrich complete — %s", bp_id, patch_stats)

    # ── 7. Verify results ──
    resources = bp.get("resources", [])
    acs = bp.get("audit_checklist_summary", {})
    code_examples = [
        r for r in resources if isinstance(r, dict) and r.get("type") == "code_example"
    ]
    tech_docs = [
        r for r in resources if isinstance(r, dict) and r.get("type") == "technique_document"
    ]
    coverage = acs.get("coverage", "MISSING")
    pass_rate = acs.get("pass_rate", "MISSING")

    summary = {
        "bp_id": bp_id,
        "resources_total": len(resources),
        "code_examples": len(code_examples),
        "technique_documents": len(tech_docs),
        "coverage": coverage,
        "pass_rate": pass_rate,
        "patch_stats": patch_stats,
    }
    logger.info("%s: verification — %s", bp_id, summary)

    # ── 8. Write new versioned blueprint file ──
    next_ver = _get_next_version(sources_dir)
    new_bp_filename = f"blueprint.v{next_ver}.yaml"
    new_bp_path = sources_dir / new_bp_filename

    content = "# Re-enriched by reenrich_blueprint.py (P0-A Bug B/C/D2 fix)\n"
    content += yaml.dump(
        bp,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
        width=100,
    )

    # Atomic write
    fd, tmp_path = tempfile.mkstemp(dir=str(sources_dir), suffix=".yaml")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, str(new_bp_path))
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    logger.info("%s: written %s", bp_id, new_bp_path)

    # ── 9. Update LATEST.yaml as relative symlink ──
    # CRITICAL: must unlink first — if LATEST.yaml is an existing symlink,
    # shutil.copy2/open-for-write follows it and corrupts the historic vN file.
    latest_path = sources_dir / "LATEST.yaml"
    if latest_path.is_symlink() or latest_path.exists():
        latest_path.unlink()
    latest_path.symlink_to(new_bp_filename)
    logger.info("%s: LATEST.yaml -> %s", bp_id, new_bp_filename)

    # ── 10. Update manifest.json ──
    manifest_path = sources_dir / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        manifest["latest"]["blueprint"] = new_bp_filename

        # Build version entry
        new_version_entry = {
            "file": new_bp_filename,
            "version": next_ver,
            "extracted_at": datetime.now(UTC).isoformat(),
            "commit_hash": state.commit_hash,
            "sop_version": bp.get("sop_version", "3.6"),
            "agent_version": "v6",
            "llm_model": "",
            "notes": "P0-A re-enrichment: Bug B/C/D2 fix (resources + audit coverage)",
            "stats": {
                "stages": len(bp.get("stages", [])),
                "business_decisions": len(bp.get("business_decisions", [])),
                "resources": len(resources),
                "code_examples": len(code_examples),
                "technique_documents": len(tech_docs),
                "known_use_cases": len(bp.get("known_use_cases", bp.get("use_cases", []))),
            },
        }

        # Prepend to blueprint_versions
        manifest["blueprint_versions"] = [new_version_entry] + manifest.get(
            "blueprint_versions", []
        )

        manifest_path.write_text(json.dumps(manifest, indent=4, ensure_ascii=False))
        logger.info("%s: manifest.json updated to v%d", bp_id, next_ver)

    summary["new_version"] = next_ver
    summary["new_file"] = new_bp_filename
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="P0-A Blueprint Re-enrichment")
    parser.add_argument(
        "bp_ids",
        nargs="*",
        help="Blueprint ID(s) to re-enrich, e.g. finance-bp-079",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Re-enrich the 5 hard-coded target blueprints",
    )
    parser.add_argument(
        "--discover",
        action="store_true",
        help="Auto-discover every finance-bp-* dir under knowledge/sources/finance/ "
        "that has matching _runs/{bp}/artifacts/ available",
    )
    parser.add_argument(
        "--exclude",
        nargs="*",
        default=[],
        help="bp_ids to exclude (e.g. already-enriched blueprints)",
    )
    args = parser.parse_args()

    if args.discover:
        targets = _discover_all_targets()
        if args.exclude:
            skip = set(args.exclude)
            targets = [(b, s) for (b, s) in targets if b not in skip]
    elif args.all:
        targets = TARGETS
    elif args.bp_ids:
        discovered = dict(_discover_all_targets())
        hardcoded = dict(TARGETS)
        slug_map = {**discovered, **hardcoded}
        targets = []
        for bp_id in args.bp_ids:
            if bp_id not in slug_map:
                print(f"ERROR: unknown bp_id {bp_id!r}", file=sys.stderr)
                sys.exit(1)
            targets.append((bp_id, slug_map[bp_id]))
    else:
        parser.print_help()
        sys.exit(0)

    results = []
    for bp_id, slug in targets:
        print(f"\n{'=' * 60}")
        print(f"Re-enriching: {bp_id} ({slug})")
        print(f"{'=' * 60}")
        try:
            summary = reenrich_blueprint(bp_id, slug)
            results.append(summary)
            print(f"\nSUCCESS: {bp_id}")
            print(f"  resources_total:     {summary['resources_total']}")
            print(f"  code_examples:       {summary['code_examples']}")
            print(f"  technique_documents: {summary['technique_documents']}")
            print(f"  coverage:            {summary['coverage']}")
            print(f"  pass_rate:           {summary['pass_rate']}")
            print(f"  new_file:            {summary.get('new_file')}")
        except Exception as exc:
            logger.error("%s: FAILED — %s", bp_id, exc, exc_info=True)
            results.append({"bp_id": bp_id, "error": str(exc)})

    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print(f"{'=' * 60}")
    for r in results:
        if "error" in r:
            print(f"  {r['bp_id']}: FAILED — {r['error']}")
        else:
            print(
                f"  {r['bp_id']}: OK — "
                f"resources={r['resources_total']} "
                f"(code_ex={r['code_examples']}, tech_doc={r['technique_documents']}) "
                f"coverage={r['coverage']} "
                f"pass_rate={r['pass_rate']} "
                f"→ {r.get('new_file')}"
            )


if __name__ == "__main__":
    main()
