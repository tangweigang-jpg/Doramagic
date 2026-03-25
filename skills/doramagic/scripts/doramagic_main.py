#!/usr/bin/env python3
"""Doramagic unified entry point.

Called by SKILL.md on OpenClaw or directly from CLI.

Usage:
    # First invocation (OpenClaw):
    python3 doramagic_main.py --input "帮我做记账app" --run-dir ~/clawd/doramagic/runs/

    # Resume after clarification:
    python3 doramagic_main.py --continue <run_id> --input "web版" --run-dir ~/clawd/doramagic/runs/

    # CLI mode:
    python3 doramagic_main.py --cli --input "帮我做记账app"
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path


def setup_packages_path() -> None:
    """Add packages/ subdirs to sys.path and configure env vars.

    Resolution order for runtime_root:
    1. DORAMAGIC_ROOT env var (explicit override)
    2. skill_root (parent of scripts/) if packages/ exists there
    3. project_root (3 levels up from scripts/) if packages/ exists there

    Side effects:
    - Sets DORAMAGIC_ROOT env var
    - Adds all packages/<pkg>/ subdirs to sys.path
    - Sets DORAMAGIC_BRICKS_DIR if bricks/ exists under runtime_root
    - Sets DORAMAGIC_SCRIPTS_DIR if scripts/ exists under runtime_root
    - Auto-resolves platform_rules.json from runtime_root if not already set
    """
    script_dir = Path(__file__).resolve().parent
    skill_root = script_dir.parent          # skills/doramagic/ (or installed skill root)
    project_root = script_dir.parents[3]    # dev layout: project_root/skills/doramagic/scripts/

    # Determine runtime_root
    env_root = os.environ.get("DORAMAGIC_ROOT")
    if env_root:
        runtime_root = Path(env_root).expanduser().resolve()
    elif (skill_root / "packages").exists():
        runtime_root = skill_root           # self-contained skill install
    elif (project_root / "packages").exists():
        runtime_root = project_root         # developer layout
    else:
        # Last resort: skill_root (so env vars still get set)
        runtime_root = skill_root

    # Set DORAMAGIC_ROOT so sub-modules can find their resources
    os.environ.setdefault("DORAMAGIC_ROOT", str(runtime_root))

    # Add all packages/<pkg>/ subdirs to sys.path
    packages_dir = runtime_root / "packages"
    if packages_dir.exists():
        for pkg_dir in packages_dir.iterdir():
            if pkg_dir.is_dir() and not pkg_dir.name.startswith((".", "_")):
                if str(pkg_dir) not in sys.path:
                    sys.path.insert(0, str(pkg_dir))

    # Set DORAMAGIC_BRICKS_DIR if bricks/ exists
    bricks_dir = runtime_root / "bricks"
    if bricks_dir.exists():
        os.environ.setdefault("DORAMAGIC_BRICKS_DIR", str(bricks_dir))

    # Set DORAMAGIC_SCRIPTS_DIR if scripts/ exists
    scripts_dir = runtime_root / "scripts"
    if scripts_dir.exists():
        os.environ.setdefault("DORAMAGIC_SCRIPTS_DIR", str(scripts_dir))

  # Optional module — work without it


def _auto_resolve_platform_rules(args) -> None:
    """Auto-resolve platform_rules.json from DORAMAGIC_ROOT if not passed via CLI."""
    if args.platform_rules:
        return  # Already specified via CLI

    runtime_root = os.environ.get("DORAMAGIC_ROOT")
    if not runtime_root:
        return

    candidate = Path(runtime_root) / "platform_rules.json"
    if candidate.exists():
        args.platform_rules = str(candidate)


def main() -> None:
    parser = argparse.ArgumentParser(description="Doramagic Dual-Layer Fusion Controller")
    parser.add_argument("--input", "-i", type=str, default="", help="User input text")
    parser.add_argument("--continue", dest="continue_run", type=str, default=None,
                        help="Resume a previous run by run_id")
    parser.add_argument("--run-dir", type=str, default=None,
                        help="Run directory (default: platform-specific)")
    parser.add_argument("--cli", action="store_true", help="Use CLI adapter instead of OpenClaw")
    parser.add_argument("--platform-rules", type=str, default=None,
                        help="Path to platform_rules.json")
    parser.add_argument("--dry-run", action="store_true", help="Skip LLM calls, use mock data")
    args = parser.parse_args()

    setup_packages_path()

    # Auto-resolve platform_rules.json if not provided via CLI
    _auto_resolve_platform_rules(args)

    # Import after path setup
    from doramagic_controller.flow_controller import FlowController
    from doramagic_contracts.budget import BudgetPolicy

    if args.cli:
        from doramagic_controller.adapters.cli import CLIAdapter
        adapter = CLIAdapter(
            storage_root=Path(args.run_dir).expanduser() if args.run_dir else None,
            platform_rules_path=Path(args.platform_rules) if args.platform_rules else None,
        )
    else:
        from doramagic_controller.adapters.openclaw import OpenClawAdapter
        adapter = OpenClawAdapter(
            storage_root=Path(args.run_dir).expanduser() if args.run_dir else None,
            platform_rules_path=Path(args.platform_rules) if args.platform_rules else None,
        )

    # Determine run directory
    if args.run_dir:
        run_base = Path(args.run_dir).expanduser()
    else:
        run_base = adapter.get_storage_root()

    if args.continue_run:
        run_dir = run_base / args.continue_run
    else:
        run_id = f"run-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        run_dir = run_base / run_id

    # Register all phase executors
    from doramagic_executors import ALL_EXECUTORS
    executors = {name: cls() for name, cls in ALL_EXECUTORS.items()}

    # Create controller
    controller = FlowController(
        adapter=adapter,
        run_dir=run_dir,
        executors=executors,
        budget_policy=BudgetPolicy(),
    )

    # Run
    try:
        result = asyncio.run(controller.run(
            user_input=args.input,
            resume_run_id=args.continue_run,
        ))
    except KeyboardInterrupt:
        print(json.dumps({"message": "Interrupted", "error": True}))
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"message": f"Fatal error: {e}", "error": True}))
        sys.exit(1)

    # Output result
    if result.phase.value in ("DONE", "DEGRADED"):
        delivery_dir = run_dir / "delivery"
        artifacts = {}
        if delivery_dir.exists():
            for f in delivery_dir.iterdir():
                artifacts[f.name] = f

        msg = _build_rich_message(result, delivery_dir)
        asyncio.run(adapter.send_output(msg, artifacts))
    elif result.phase.value == "PHASE_A_CLARIFY":
        pass  # Controller paused for clarification — output already sent
    else:
        print(json.dumps({
            "message": f"Pipeline failed: {', '.join(result.degradation_log) or 'unknown error'}",
            "error": True,
        }))
        sys.exit(1)


def _build_rich_message(result, delivery_dir: Path) -> str:
    """Build a rich Chinese summary message (replicating singleshot's output format)."""
    arts = result.phase_artifacts

    lines = ["## Doramagic 道具锻造完成！", ""]

    # Topic
    np = arts.get("need_profile", {})
    topic = np.get("intent", "") if isinstance(np, dict) else ""
    if topic:
        lines.append(f"**主题**: {topic}")
        lines.append("")

    # Source breakdown
    discovery = arts.get("discovery_result", {})
    extraction = arts.get("extraction_results", {})
    community = arts.get("community_signals", {}) if isinstance(extraction, dict) else {}
    candidates = discovery.get("candidates", []) if isinstance(discovery, dict) else []
    successful = extraction.get("successful_repos", []) if isinstance(extraction, dict) else []

    github_count = sum(1 for c in candidates if isinstance(c, dict) and c.get("type") == "github_repo")
    skill_count = sum(1 for c in candidates if isinstance(c, dict) and c.get("type") == "community_skill")
    community_count = sum(1 for v in (community if isinstance(community, dict) else {}).values()
                         if isinstance(v, dict) and not v.get("skipped"))

    lines.append(f"**来源**: {len(successful)} 个项目分析完成 "
                 f"({github_count} GitHub, {skill_count} ClawHub/本地, {community_count} 社区信号)")
    lines.append("")

    # Analyzed repos
    if successful:
        lines.append("**分析项目**:")
        for repo_id in successful[:5]:
            lines.append(f"  - {repo_id}")
        lines.append("")

    # WHY preview (from synthesis)
    synthesis = arts.get("synthesis_report", {})
    consensus = synthesis.get("consensus", synthesis.get("selected_knowledge", [])) if isinstance(synthesis, dict) else []
    whys = [d.get("statement", "") if isinstance(d, dict) else str(d)
            for d in consensus if isinstance(d, dict) and "[TRAP]" not in d.get("statement", "")]
    if whys:
        lines.append("**WHY — 设计智慧**:")
        for w in whys[:3]:
            lines.append(f"  - {w}")
        lines.append("")

    # UNSAID preview
    traps = [d.get("statement", "").replace("[TRAP] ", "") if isinstance(d, dict) else str(d)
             for d in consensus if isinstance(d, dict) and "[TRAP]" in d.get("statement", "")]
    if traps:
        lines.append("**UNSAID — 隐藏陷阱**:")
        for t in traps[:3]:
            lines.append(f"  - {t}")
        lines.append("")

    # Delivery path
    if delivery_dir.exists():
        skill_md = delivery_dir / "SKILL.md"
        if skill_md.exists():
            lines.append(f"**交付物**: `{delivery_dir}`")
            lines.append("")

    # Degradation notice
    if result.degradation_log:
        lines.append("**注意** (降级模式):")
        for d in result.degradation_log[:3]:
            lines.append(f"  - {d}")
        lines.append("")

    lines.append("---")
    lines.append("*Generated by Doramagic v9.2.0 — 不教用户做事，给他工具。*")

    return "\n".join(lines)


if __name__ == "__main__":
    main()
