"""Constraint agent CLI — standalone constraint extraction.

Usage:
    python -m doramagic_constraint_agent.cli run \\
        --blueprint knowledge/blueprints/finance/finance-bp-070.yaml \\
        --repo-path repos/edgartools \\
        --domain finance --version v3

    python -m doramagic_constraint_agent.cli batch --job-file jobs/constraints.yaml
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def _setup_path() -> Path:
    """Add packages/ to sys.path and return project root."""
    # Walk up from this file to find the project root (has packages/ dir)
    candidate = Path(__file__).resolve().parent.parent.parent.parent
    if not (candidate / "packages").is_dir():
        # Fallback: try CWD
        candidate = Path.cwd()
    packages_dir = candidate / "packages"
    if packages_dir.is_dir():
        for pkg_dir in packages_dir.iterdir():
            if pkg_dir.is_dir() and (pkg_dir / "pyproject.toml").exists():
                sys.path.insert(0, str(pkg_dir))
    return candidate


def _cmd_run(args: argparse.Namespace, project_root: Path) -> None:
    """Run constraint extraction for a single blueprint."""
    from .batch.job_queue import ConstraintBatchConfig, ConstraintJob
    from .batch.orchestrator import ConstraintBatchOrchestrator

    blueprint_path = Path(args.blueprint)
    if not blueprint_path.is_absolute():
        blueprint_path = project_root / blueprint_path

    if not blueprint_path.exists():
        print(f"Error: blueprint not found: {blueprint_path}", file=sys.stderr)
        sys.exit(1)

    repo_path = Path(args.repo_path)
    if not repo_path.is_absolute():
        repo_path = project_root / repo_path

    if not repo_path.exists():
        print(f"Error: repo not found: {repo_path}", file=sys.stderr)
        sys.exit(1)

    # Derive blueprint_id: explicit arg > YAML content > filename
    bp_id = getattr(args, "blueprint_id", None)
    if not bp_id:
        import yaml

        try:
            bp_data = yaml.safe_load(blueprint_path.read_text(encoding="utf-8"))
            bp_id = bp_data.get("id", "") if isinstance(bp_data, dict) else ""
        except Exception:
            bp_id = ""
    if not bp_id:
        bp_id = blueprint_path.stem

    job = ConstraintJob(
        blueprint_id=bp_id,
        blueprint_path=str(blueprint_path),
        repo_path=str(repo_path),
        domain=args.domain,
    )

    # LLM config: CLI args > env vars > defaults
    model = args.model or os.environ.get("LLM_MODEL", "MiniMax-M2.7")
    base_url = args.base_url or os.environ.get("LLM_BASE_URL", "")

    config = ConstraintBatchConfig(
        batch_id=f"single-{bp_id}",
        domain=args.domain,
        jobs=[job],
        constraint_version=args.version,
        llm_model=model,
        llm_base_url=base_url,
        resume=args.resume,
    )

    orchestrator = ConstraintBatchOrchestrator(config, project_root)
    result = asyncio.run(orchestrator.run())

    print(f"\n{'=' * 60}")
    print(f"Constraint Extraction: {bp_id}")
    print(f"  Status: {len(result.completed)} completed, {len(result.failed)} failed")
    print(f"  Tokens: {result.total_tokens:,}")
    if result.failed:
        print(f"  Failed: {result.failed}")
    print(f"{'=' * 60}")

    sys.exit(1 if result.failed else 0)


def _cmd_batch(args: argparse.Namespace, project_root: Path) -> None:
    """Run batch constraint extraction from a YAML job file."""
    import yaml

    from .batch.job_queue import ConstraintBatchConfig, ConstraintJob
    from .batch.orchestrator import ConstraintBatchOrchestrator

    job_file = Path(args.job_file)
    if not job_file.is_absolute():
        job_file = project_root / job_file

    if not job_file.exists():
        print(f"Error: job file not found: {job_file}", file=sys.stderr)
        sys.exit(1)

    raw = yaml.safe_load(job_file.read_text())

    jobs = []
    for entry in raw.get("jobs", []):
        bp_path = entry["blueprint"]
        if not Path(bp_path).is_absolute():
            bp_path = str(project_root / bp_path)
        rp = entry["repo_path"]
        if not Path(rp).is_absolute():
            rp = str(project_root / rp)

        jobs.append(
            ConstraintJob(
                blueprint_id=entry.get("blueprint_id", Path(bp_path).stem),
                blueprint_path=bp_path,
                repo_path=rp,
                domain=entry.get("domain", raw.get("domain", "finance")),
                priority=entry.get("priority", 1),
            )
        )

    config = ConstraintBatchConfig(
        batch_id=raw.get("batch_id", "constraint-batch"),
        domain=raw.get("domain", "finance"),
        concurrency=raw.get("concurrency", 3),
        jobs=jobs,
        constraint_version=raw.get("constraint_version", "v3"),
        llm_model=raw.get("llm_model", os.environ.get("LLM_MODEL", "MiniMax-M2.7")),
        llm_base_url=raw.get("llm_base_url", os.environ.get("LLM_BASE_URL", "")),
        fallback_models=raw.get("fallback_models", []),
        model_overrides=raw.get("model_overrides", {}),
        resume=raw.get("resume", False),
    )

    orchestrator = ConstraintBatchOrchestrator(config, project_root)
    result = asyncio.run(orchestrator.run())

    print(f"\n{'=' * 60}")
    print(f"Batch Constraint Extraction: {config.batch_id}")
    print(f"  Completed: {len(result.completed)}")
    print(f"  Failed: {len(result.failed)}")
    print(f"  Tokens: {result.total_tokens:,}")
    if result.failed:
        print(f"  Failed jobs: {result.failed}")
    print(f"{'=' * 60}")

    sys.exit(1 if result.failed else 0)


def _scan_stale_projects(sources_dir: Path, project_root: Path) -> list[dict]:
    """Scan sources directory for projects needing constraint extraction.

    A project needs extraction when:
    - Blueprint exists but no constraints at all
    - Latest constraint's source_blueprint_version < latest blueprint version
    - NOT currently extracting (status != 'extracting')
    """
    import json

    stale = []
    for project_dir in sorted(sources_dir.iterdir()):
        if not project_dir.is_dir():
            continue
        manifest_path = project_dir / "manifest.json"
        if not manifest_path.exists():
            continue
        blueprint_path = project_dir / "LATEST.yaml"
        if not blueprint_path.exists():
            continue

        try:
            m = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue

        # Skip if currently extracting
        if m.get("constraint_extraction_status") == "extracting":
            logger.info("  %s: skipped (extracting)", project_dir.name)
            continue

        # Get latest blueprint version
        bp_versions = m.get("blueprint_versions", [])
        if not bp_versions:
            continue
        latest_bp_version = bp_versions[0].get("version", 0)

        # Get source_blueprint_version from latest constraint
        con_versions = m.get("constraint_versions", [])
        source_bp_version = 0
        if con_versions:
            source_bp_version = con_versions[0].get("source_blueprint_version", 0)

        if latest_bp_version > source_bp_version:
            # Resolve repo_path from blueprint YAML
            import yaml

            repo_path = ""
            try:
                bp_data = yaml.safe_load(blueprint_path.read_text(encoding="utf-8"))
                projects = (
                    bp_data.get("source", {}).get("projects", [])
                    if isinstance(bp_data, dict)
                    else []
                )
                if projects:
                    repo_name = projects[0].split("/")[-1] if "/" in projects[0] else projects[0]
                    repo_path = str(project_root / "repos" / repo_name)
            except Exception:
                pass

            bp_id = m.get("blueprint_id", project_dir.name.split("--")[0])
            stale.append(
                {
                    "blueprint_id": bp_id,
                    "blueprint_path": str(blueprint_path),
                    "repo_path": repo_path,
                    "domain": m.get("domain", "finance"),
                    "project_dir": str(project_dir),
                    "latest_bp_version": latest_bp_version,
                    "source_bp_version": source_bp_version,
                }
            )
            logger.info(
                "  %s: STALE (blueprint v%d, constraints based on v%d)",
                project_dir.name,
                latest_bp_version,
                source_bp_version,
            )
        else:
            logger.debug(
                "  %s: up-to-date (v%d)",
                project_dir.name,
                latest_bp_version,
            )

    return stale


def _cmd_discover(args: argparse.Namespace, project_root: Path) -> None:
    """Discover and extract constraints for stale projects."""
    from .batch.job_queue import ConstraintBatchConfig, ConstraintJob
    from .batch.orchestrator import ConstraintBatchOrchestrator

    sources_dir = Path(args.sources_dir)
    if not sources_dir.is_absolute():
        sources_dir = project_root / sources_dir

    if not sources_dir.exists():
        print(f"Error: sources dir not found: {sources_dir}", file=sys.stderr)
        sys.exit(1)

    watch = getattr(args, "watch", False)
    interval = getattr(args, "interval", 1800)
    model = args.model or os.environ.get("LLM_MODEL", "MiniMax-M2.7")
    base_url = args.base_url or os.environ.get("LLM_BASE_URL", "")
    version = getattr(args, "version", "v3")

    round_num = 0
    while True:
        round_num += 1
        print(f"\n{'=' * 60}")
        print(f"Discover round {round_num} — scanning {sources_dir}")
        print(f"{'=' * 60}")

        stale = _scan_stale_projects(sources_dir, project_root)

        if not stale:
            print("  All projects up-to-date.")
            if not watch:
                break
            print(f"  Waiting {interval}s before next scan...")
            import time

            time.sleep(interval)
            continue

        print(f"  Found {len(stale)} stale project(s):")
        for p in stale:
            print(
                f"    - {p['blueprint_id']}: "
                f"blueprint v{p['latest_bp_version']} > "
                f"constraint v{p['source_bp_version']}"
            )

        # Extract constraints for each stale project sequentially
        for p in stale:
            if not p["repo_path"] or not Path(p["repo_path"]).exists():
                print(f"  SKIP {p['blueprint_id']}: repo not found at {p['repo_path']}")
                continue

            print(f"\n  Extracting: {p['blueprint_id']}...")
            job = ConstraintJob(
                blueprint_id=p["blueprint_id"],
                blueprint_path=p["blueprint_path"],
                repo_path=p["repo_path"],
                domain=p["domain"],
            )
            config = ConstraintBatchConfig(
                batch_id=f"discover-{p['blueprint_id']}",
                domain=p["domain"],
                jobs=[job],
                constraint_version=version,
                llm_model=model,
                llm_base_url=base_url,
            )
            orchestrator = ConstraintBatchOrchestrator(config, project_root)
            result = asyncio.run(orchestrator.run())
            status = "OK" if result.completed else "FAILED"
            print(f"  {status}: {p['blueprint_id']} ({result.total_tokens:,} tokens)")

        if not watch:
            break
        print(f"\n  Waiting {interval}s before next scan...")
        import time

        time.sleep(interval)


def main() -> None:
    """CLI entry point."""
    project_root = _setup_path()

    parser = argparse.ArgumentParser(
        description="Doramagic Constraint Extraction Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    sub = parser.add_subparsers(dest="command", required=True)

    # -- run: single blueprint --
    run_cmd = sub.add_parser("run", help="Extract constraints for one blueprint")
    run_cmd.add_argument("--blueprint", required=True, help="Path to blueprint YAML")
    run_cmd.add_argument(
        "--blueprint-id", default=None, help="Override blueprint ID (auto-detected from YAML)"
    )
    run_cmd.add_argument("--repo-path", required=True, help="Path to local repo clone")
    run_cmd.add_argument("--domain", default="finance")
    run_cmd.add_argument(
        "--version",
        choices=["v2", "v3"],
        default="v3",
        help="Constraint pipeline version (default: v3)",
    )
    run_cmd.add_argument("--model", default=None, help="LLM model ID")
    run_cmd.add_argument("--base-url", default=None, help="LLM API base URL")
    run_cmd.add_argument("--resume", action="store_true", help="Resume from checkpoint")

    # -- batch: YAML job file --
    batch_cmd = sub.add_parser("batch", help="Batch extraction from YAML job file")
    batch_cmd.add_argument("--job-file", required=True, help="Path to YAML job file")

    # -- discover: scan for stale projects --
    disc_cmd = sub.add_parser(
        "discover",
        help="Scan sources dir, extract constraints for stale projects",
    )
    disc_cmd.add_argument(
        "--sources-dir",
        required=True,
        help="Path to knowledge/sources/{domain}/",
    )
    disc_cmd.add_argument(
        "--watch",
        action="store_true",
        help="Keep running and rescan every --interval seconds",
    )
    disc_cmd.add_argument(
        "--interval",
        type=int,
        default=1800,
        help="Seconds between scans in watch mode (default: 1800)",
    )
    disc_cmd.add_argument(
        "--version",
        choices=["v2", "v3"],
        default="v3",
        help="Constraint pipeline version (default: v3)",
    )
    disc_cmd.add_argument("--model", default=None, help="LLM model ID")
    disc_cmd.add_argument("--base-url", default=None, help="LLM API base URL")

    args = parser.parse_args()

    # Logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.command == "run":
        _cmd_run(args, project_root)
    elif args.command == "batch":
        _cmd_batch(args, project_root)
    elif args.command == "discover":
        _cmd_discover(args, project_root)


if __name__ == "__main__":
    main()
