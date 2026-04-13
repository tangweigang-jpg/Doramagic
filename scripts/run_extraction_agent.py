#!/usr/bin/env python3
"""Doramagic Extraction Agent — autonomous knowledge extraction.

Drives the extraction agent for single-repo or batch extraction runs.
The agent executes the full SOP pipeline (blueprint + constraint phases)
autonomously, with checkpoint-based resume support.

Usage:
    # Single repo extraction:
    python scripts/run_extraction_agent.py single \\
        --blueprint-id finance-bp-060 \\
        --repo-path repos/some_repo \\
        --domain finance

    # Single repo extraction from a remote URL:
    python scripts/run_extraction_agent.py single \\
        --blueprint-id finance-bp-060 \\
        --repo-url https://github.com/example/repo \\
        --domain finance

    # Resume interrupted extraction:
    python scripts/run_extraction_agent.py single \\
        --blueprint-id finance-bp-060 \\
        --resume

    # Skip blueprint, only run constraint pipeline:
    python scripts/run_extraction_agent.py single \\
        --blueprint-id finance-bp-060 \\
        --repo-path repos/some_repo \\
        --skip-blueprint

    # Batch extraction from a job file:
    python scripts/run_extraction_agent.py batch \\
        --job-file jobs/finance-batch.yaml
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Project root + package paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for _pkg_dir in (PROJECT_ROOT / "packages").iterdir():
    if _pkg_dir.is_dir():
        sys.path.insert(0, str(_pkg_dir))


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------


def _setup_logging(log_file: Path | None = None, verbose: bool = False) -> None:
    """Configure structured logging to console and optionally to a file.

    Args:
        log_file: If given, a ``FileHandler`` is added alongside the console
            handler.  The file is created (with parent directories) if it does
            not exist.
        verbose: When ``True``, the root logger level is set to ``DEBUG``;
            otherwise ``INFO``.
    """
    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s"
    datefmt = "%Y-%m-%dT%H:%M:%S"

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]

    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
        handlers.append(file_handler)

    logging.basicConfig(level=level, format=fmt, datefmt=datefmt, handlers=handlers)

    # Silence overly verbose third-party loggers
    for noisy in ("httpx", "anthropic", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Adapter factory (shared by both subcommands)
# ---------------------------------------------------------------------------


def _make_adapter(
    model: str | None,
    base_url: str | None,
    api_key: str | None,
) -> "LLMAdapter":
    """Create a configured :class:`LLMAdapter`.

    Priority: CLI argument > environment variable > SDK default.

    Args:
        model: Model ID string (CLI flag value or ``None``).
        base_url: API base URL (CLI flag value or ``None``).
        api_key: Raw API key string (CLI flag value or ``None``).

    Returns:
        Ready-to-use :class:`LLMAdapter` instance.
    """
    from doramagic_shared_utils.llm_adapter import LLMAdapter  # noqa: PLC0415

    resolved_model = (
        model
        or os.environ.get("LLM_MODEL", "")
        or "MiniMax-M2.7"
    )
    resolved_base_url = base_url or os.environ.get("LLM_BASE_URL", "")
    resolved_api_key = (
        api_key
        or os.environ.get("LLM_API_KEY", "")
        or os.environ.get("MINIMAX_API_KEY", "")
    )

    adapter = LLMAdapter(provider_override="anthropic")
    adapter._default_model = resolved_model
    if resolved_base_url:
        adapter._base_url = resolved_base_url
    if resolved_api_key:
        adapter._api_key = resolved_api_key

    logger.info(
        "LLM adapter: model=%s base_url=%s",
        resolved_model,
        resolved_base_url or "(default)",
    )
    return adapter


# ---------------------------------------------------------------------------
# 'single' subcommand
# ---------------------------------------------------------------------------


def cmd_single(args: argparse.Namespace) -> None:
    """Run extraction for a single repository.

    Sets up all components (adapter, checkpoint manager, tool registry,
    agent, SOP phases) and drives the full extraction pipeline to completion.

    Supports resume via ``--resume`` (loads existing checkpoint state).
    """
    # --- Validate args ---
    if not args.repo_path and not args.repo_url and not args.resume:
        print(
            "Error: one of --repo-path, --repo-url, or --resume is required",
            file=sys.stderr,
        )
        sys.exit(1)

    # --- Logging ---
    log_dir = PROJECT_ROOT / "_runs" / args.blueprint_id / "logs"
    _setup_logging(log_file=log_dir / "extraction.log", verbose=args.verbose)

    # --- Imports (deferred so sys.path insertions above take effect first) ---
    try:
        from doramagic_extraction_agent.batch.job_queue import RepoJob, BatchConfig  # noqa: PLC0415
        from doramagic_extraction_agent.batch.orchestrator import BatchOrchestrator  # noqa: PLC0415
    except ImportError as exc:
        print(f"Error: cannot import extraction_agent — {exc}", file=sys.stderr)
        print("Ensure all packages are installed: uv sync", file=sys.stderr)
        sys.exit(1)

    job = RepoJob(
        blueprint_id=args.blueprint_id,
        repo_url=args.repo_url or "",
        repo_path=args.repo_path or "",
        domain=args.domain,
        priority=1,
        skip_blueprint=args.skip_blueprint,
        skip_constraint=args.skip_constraint,
    )

    # Build fallback model config from CLI args or env vars
    fallback_models: list[dict] = []
    fb_model = getattr(args, "fallback_model", None) or os.environ.get("FALLBACK_MODEL", "")
    fb_url = getattr(args, "fallback_base_url", None) or os.environ.get("FALLBACK_BASE_URL", "")
    fb_key = getattr(args, "fallback_api_key", None) or os.environ.get("FALLBACK_API_KEY", "")
    fb_format = getattr(args, "fallback_api_format", None) or os.environ.get("FALLBACK_API_FORMAT", "openai")
    if fb_model:
        fb_spec: dict = {"model_id": fb_model, "api_format": fb_format}
        if fb_url:
            fb_spec["base_url"] = fb_url
        if fb_key:
            fb_spec["api_key"] = fb_key
        fallback_models.append(fb_spec)

    config = BatchConfig(
        batch_id=f"single-{args.blueprint_id}",
        domain=args.domain,
        concurrency=1,
        repos=[job],
        llm_model=args.model or os.environ.get("LLM_MODEL", "MiniMax-M2.7"),
        llm_base_url=args.base_url or os.environ.get("LLM_BASE_URL", ""),
        llm_api_key_env="LLM_API_KEY",
        resume=args.resume,
        api_format=getattr(args, "api_format", None) or "anthropic",
        fallback_models=fallback_models,
        blueprint_version=getattr(args, "blueprint_version", "v4"),
        constraint_version=getattr(args, "constraint_version", "v1"),
    )

    # Inject api_key directly if provided via CLI (env var not needed)
    if args.api_key:
        os.environ["LLM_API_KEY"] = args.api_key

    logger.info(
        "Single extraction: blueprint_id=%s repo_path=%s repo_url=%s "
        "skip_blueprint=%s skip_constraint=%s resume=%s",
        args.blueprint_id,
        args.repo_path or "(none)",
        args.repo_url or "(none)",
        args.skip_blueprint,
        args.skip_constraint,
        args.resume,
    )

    orchestrator = BatchOrchestrator(config, PROJECT_ROOT)
    result = asyncio.run(orchestrator.run())

    # --- Summary ---
    print()
    print("=" * 60)
    print(f"Extraction Agent — Single Run: {args.blueprint_id}")
    print("=" * 60)
    if result.completed:
        print(f"  Status       : completed")
        print(f"  Total tokens : {result.total_tokens:,}")
        run_dir = PROJECT_ROOT / "_runs" / args.blueprint_id / "output"
        print(f"  Output dir   : {run_dir}")
    else:
        print(f"  Status       : FAILED")
        print(f"  Total tokens : {result.total_tokens:,}")
        print(f"  Check logs   : {log_dir / 'extraction.log'}")
        sys.exit(1)
    print("=" * 60)


# ---------------------------------------------------------------------------
# 'batch' subcommand
# ---------------------------------------------------------------------------


def cmd_batch(args: argparse.Namespace) -> None:
    """Run batch extraction from a YAML job file.

    Parses the job file, starts the batch orchestrator, and prints a
    summary on completion.  Exits with code 1 if any jobs failed.
    """
    job_file = Path(args.job_file)
    if not job_file.is_absolute():
        job_file = PROJECT_ROOT / job_file

    if not job_file.exists():
        print(f"Error: job file not found: {job_file}", file=sys.stderr)
        sys.exit(1)

    # --- Logging (batch-level log to _runs/_batch/<batch_id>/) ---
    # We must parse the config first to get the batch_id for the log path.
    # Use a temporary basic config until then.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
        stream=sys.stdout,
    )

    try:
        from doramagic_extraction_agent.batch.job_queue import load_batch_config  # noqa: PLC0415
        from doramagic_extraction_agent.batch.orchestrator import BatchOrchestrator  # noqa: PLC0415
    except ImportError as exc:
        print(f"Error: cannot import extraction_agent — {exc}", file=sys.stderr)
        print("Ensure all packages are installed: uv sync", file=sys.stderr)
        sys.exit(1)

    try:
        config = load_batch_config(job_file)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error loading job file: {exc}", file=sys.stderr)
        sys.exit(1)

    # Reconfigure logging now that we have the batch_id
    log_dir = PROJECT_ROOT / "_runs" / "_batch" / config.batch_id / "logs"
    # Remove the temp handlers before reconfiguring
    root_logger = logging.getLogger()
    for h in root_logger.handlers[:]:
        root_logger.removeHandler(h)
    _setup_logging(log_file=log_dir / "batch.log", verbose=False)

    # Override model / base_url / api_key from CLI if provided
    if getattr(args, "model", None):
        config.llm_model = args.model
    if getattr(args, "base_url", None):
        config.llm_base_url = args.base_url
    if getattr(args, "api_key", None):
        os.environ["LLM_API_KEY"] = args.api_key
        config.llm_api_key_env = "LLM_API_KEY"

    logger.info(
        "Batch extraction: batch_id=%s jobs=%d concurrency=%d model=%s",
        config.batch_id,
        len(config.repos),
        config.concurrency,
        config.llm_model,
    )

    orchestrator = BatchOrchestrator(config, PROJECT_ROOT)
    result = asyncio.run(orchestrator.run())

    # --- Summary ---
    print()
    print("=" * 60)
    print(f"Extraction Agent — Batch Run: {config.batch_id}")
    print("=" * 60)
    print(f"  Total jobs  : {len(config.repos)}")
    print(f"  Completed   : {len(result.completed)}")
    print(f"  Failed      : {len(result.failed)}")
    print(f"  Total tokens: {result.total_tokens:,}")
    print(f"  Log file    : {log_dir / 'batch.log'}")

    if result.failed:
        print()
        print("Failed jobs:")
        for bp_id in result.failed:
            print(f"  - {bp_id}")
        print("=" * 60)
        sys.exit(1)

    print("=" * 60)


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_extraction_agent",
        description="Doramagic Extraction Agent — autonomous knowledge extraction.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable DEBUG-level logging.",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # ------------------------------------------------------------------
    # single
    # ------------------------------------------------------------------
    single_p = sub.add_parser(
        "single",
        help="Extract knowledge from a single repository.",
        description="Run the full SOP pipeline (blueprint + constraint) for one repo.",
    )
    single_p.add_argument(
        "--blueprint-id",
        required=True,
        metavar="ID",
        help="Blueprint ID, e.g. finance-bp-060.",
    )
    single_p.add_argument(
        "--repo-path",
        metavar="PATH",
        default="",
        help="Local path to the repository (relative to project root or absolute).",
    )
    single_p.add_argument(
        "--repo-url",
        metavar="URL",
        default="",
        help="Remote Git URL to clone (used when --repo-path is not given).",
    )
    single_p.add_argument(
        "--domain",
        default="finance",
        metavar="DOMAIN",
        help="Knowledge domain (default: finance).",
    )
    single_p.add_argument(
        "--resume",
        action="store_true",
        help="Resume an interrupted run by loading state from the checkpoint.",
    )
    single_p.add_argument(
        "--skip-blueprint",
        action="store_true",
        help="Skip the blueprint pipeline (assumes blueprint already exists).",
    )
    single_p.add_argument(
        "--skip-constraint",
        action="store_true",
        help="Skip the constraint pipeline.",
    )
    single_p.add_argument(
        "--model",
        metavar="MODEL_ID",
        default=None,
        help="LLM model ID to use (env: LLM_MODEL, default: MiniMax-M2.7).",
    )
    single_p.add_argument(
        "--base-url",
        metavar="URL",
        default=None,
        help="LLM API base URL (env: LLM_BASE_URL).",
    )
    single_p.add_argument(
        "--api-key",
        metavar="KEY",
        default=None,
        help="LLM API key (env: LLM_API_KEY or MINIMAX_API_KEY).",
    )
    single_p.add_argument(
        "--api-format",
        choices=["anthropic", "openai"],
        default="anthropic",
        help="API format: 'anthropic' (MiniMax/Claude) or 'openai' (GLM-5/GPT-4o). Default: anthropic.",
    )
    # Failover model (v3 Batch B)
    single_p.add_argument(
        "--fallback-model",
        metavar="MODEL_ID",
        default=None,
        help="Fallback model ID for automatic failover (e.g., 'glm-5').",
    )
    single_p.add_argument(
        "--fallback-base-url",
        metavar="URL",
        default=None,
        help="Fallback model API base URL.",
    )
    single_p.add_argument(
        "--fallback-api-key",
        metavar="KEY",
        default=None,
        help="Fallback model API key.",
    )
    single_p.add_argument(
        "--fallback-api-format",
        choices=["anthropic", "openai"],
        default="openai",
        help="Fallback model API format. Default: openai.",
    )
    single_p.add_argument(
        "--blueprint-version",
        choices=["v4", "v5"],
        default="v4",
        help="Blueprint phase version: 'v4' (parallel workers) or 'v5' (Instructor synthesis). Default: v4.",
    )
    single_p.add_argument(
        "--constraint-version",
        choices=["v1", "v2"],
        default="v1",
        help="Constraint phase version: 'v1' (serial) or 'v2' (parallel + Instructor). Default: v1.",
    )
    single_p.set_defaults(func=cmd_single)

    # ------------------------------------------------------------------
    # batch
    # ------------------------------------------------------------------
    batch_p = sub.add_parser(
        "batch",
        help="Extract knowledge from multiple repositories using a job file.",
        description=(
            "Load a YAML job file and run all listed repositories with "
            "bounded parallelism.  One repo failure does not affect others."
        ),
    )
    batch_p.add_argument(
        "--job-file",
        required=True,
        metavar="FILE",
        help="Path to the YAML batch job file (relative to project root or absolute).",
    )
    # Allow per-invocation overrides even in batch mode
    batch_p.add_argument(
        "--model",
        metavar="MODEL_ID",
        default=None,
        help="Override llm_model from the job file.",
    )
    batch_p.add_argument(
        "--base-url",
        metavar="URL",
        default=None,
        help="Override llm_base_url from the job file.",
    )
    batch_p.add_argument(
        "--api-key",
        metavar="KEY",
        default=None,
        help="LLM API key (env: LLM_API_KEY or MINIMAX_API_KEY).",
    )
    batch_p.set_defaults(func=cmd_batch)

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
