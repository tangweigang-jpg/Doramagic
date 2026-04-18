"""Typer CLI for the web_publisher package.

Commands:
  publish <blueprint_id>   — run full pipeline and publish (or --dry-run / --mock)
  run-phase <bp_id> <phase> — run a single phase for debugging
  preflight <package_json> — validate an existing package.json file

Usage:
  python -m doramagic_web_publisher publish bp-009
  python -m doramagic_web_publisher publish bp-009 --dry-run
  python -m doramagic_web_publisher publish bp-009 --mock
  python -m doramagic_web_publisher run-phase bp-009 content
  python -m doramagic_web_publisher preflight path/to/package.json
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

if TYPE_CHECKING:
    from doramagic_web_publisher.runtime.models import PhaseContext

import typer

app = typer.Typer(
    name="web-publisher",
    help="Doramagic Crystal Web Publisher — generates and publishes Crystal Package JSON.",
    add_completion=False,
)

logger = logging.getLogger(__name__)


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def _resolve_source_dir(blueprint_id: str) -> Path:
    """Resolve the knowledge/sources/ directory for a blueprint_id.

    Supports inputs like 'bp-009', 'finance-bp-009'.
    Returns the matching directory under knowledge/sources/finance/.
    Raises FileNotFoundError with a descriptive message if not found.
    """
    import os as _os

    # Resolve the Doramagic project root
    # Priority: DORAMAGIC_ROOT env var → walk up from cli.py until knowledge/ is found
    doramagic_root: Path | None = None
    env_root = _os.environ.get("DORAMAGIC_ROOT", "").strip()
    if env_root:
        candidate = Path(env_root).resolve()
        if candidate.is_dir() and (candidate / "knowledge").is_dir():
            doramagic_root = candidate

    if doramagic_root is None:
        # Walk up from this source file's location
        walk = Path(__file__).resolve().parent
        for _ in range(12):
            if (walk / "knowledge").is_dir() and (walk / "packages").is_dir():
                doramagic_root = walk
                break
            parent = walk.parent
            if parent == walk:
                break
            walk = parent

    if doramagic_root is None:
        raise FileNotFoundError(
            f"Cannot locate Doramagic project root from {__file__}. "
            "Set DORAMAGIC_ROOT environment variable to the repo root."
        )

    sources_base = doramagic_root / "knowledge" / "sources"
    if not sources_base.is_dir():
        raise FileNotFoundError(f"knowledge/sources/ directory not found at {sources_base}")

    # Normalise blueprint_id: ensure 'finance-bp-NNN' prefix
    bp_id = blueprint_id.strip()
    if bp_id.startswith("bp-"):
        full_id = f"finance-{bp_id}"
    elif bp_id.startswith("finance-bp-"):
        full_id = bp_id
    else:
        full_id = bp_id  # pass through for other domains

    # Search finance/ subdirectory for a matching dir name prefix
    finance_dir = sources_base / "finance"
    if finance_dir.is_dir():
        for entry in sorted(finance_dir.iterdir()):
            if entry.is_dir() and entry.name.startswith(full_id):
                return entry

    # Fallback: direct path match
    direct = sources_base / "finance" / full_id
    if direct.is_dir():
        return direct

    raise FileNotFoundError(
        f"Cannot find source directory for blueprint_id '{blueprint_id}' "
        f"(tried prefix '{full_id}--*') under {finance_dir}"
    )


def _build_context_from_blueprint_id(
    blueprint_id: str,
    dry_run: bool,
    mock_mode: bool,
) -> PhaseContext:
    """Build a PhaseContext from a blueprint_id.

    Reads from knowledge/sources/finance/<blueprint_id>--<repo>/ directory:
      - manifest.json  → PublishManifest (repo_url, commit hash)
      - LATEST.yaml    → Blueprint dict
      - LATEST.jsonl   → Constraints list
      - knowledge/crystals/<blueprint_id>/PRODUCTION.ir.yaml → Crystal IR
      - knowledge/crystals/<blueprint_id>/PRODUCTION.openclaw.seed.md → seed_content
      - QA Proof: stubbed (real QA manifest not yet wired)

    Supports blueprint_id formats: 'bp-009', 'finance-bp-009'.
    """
    import os as _os

    import yaml  # PyYAML is a dependency

    from doramagic_web_publisher.runtime.models import PhaseContext, PublishManifest

    # --- 1. Resolve source directory ---
    source_dir = _resolve_source_dir(blueprint_id)
    logger.info("context_builder: resolved source_dir=%s", source_dir)

    # --- 2. Read manifest.json ---
    manifest_path = source_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"manifest.json not found at {manifest_path}. Expected file in source_dir={source_dir}"
        )
    try:
        with manifest_path.open() as f:
            manifest_data = json.load(f)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to parse manifest.json at {manifest_path}: {exc}") from exc

    repo_url = manifest_data.get("repo_url", "")
    # Derive blueprint_source from repo_url: "https://github.com/zvtvz/zvt" → "zvtvz/zvt"
    blueprint_source = repo_url.replace("https://github.com/", "").rstrip("/") if repo_url else ""

    # Get commit hash from latest blueprint version entry
    blueprint_versions = manifest_data.get("blueprint_versions", [])
    blueprint_commit = ""
    if blueprint_versions:
        blueprint_commit = blueprint_versions[0].get("commit_hash", "")
    if not blueprint_commit:
        # Try the source field in manifest
        blueprint_commit = manifest_data.get("commit_hash", "")

    canonical_bp_id = manifest_data.get("blueprint_id", blueprint_id)
    # Normalise: ensure 'finance-bp-NNN' format for internal ID
    if canonical_bp_id.startswith("bp-"):
        canonical_bp_id = f"finance-{canonical_bp_id}"

    # --- 3. Read LATEST.yaml (Blueprint) ---
    latest_yaml = source_dir / "LATEST.yaml"
    if not latest_yaml.exists():
        raise FileNotFoundError(f"LATEST.yaml not found at {latest_yaml}")
    try:
        with latest_yaml.open() as f:
            blueprint = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        raise ValueError(f"Failed to parse LATEST.yaml at {latest_yaml}: {exc}") from exc
    if not isinstance(blueprint, dict):
        raise ValueError(
            f"LATEST.yaml at {latest_yaml} did not parse to a dict (got {type(blueprint)})"
        )

    # --- 4. Read LATEST.jsonl (Constraints) ---
    latest_jsonl = source_dir / "LATEST.jsonl"
    if not latest_jsonl.exists():
        raise FileNotFoundError(f"LATEST.jsonl not found at {latest_jsonl}")
    constraints: list[dict] = []
    with latest_jsonl.open() as f:
        for lineno, raw_line in enumerate(f, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                obj = json.loads(line)
                constraints.append(obj)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Failed to parse LATEST.jsonl at {latest_jsonl} line {lineno}: {exc}"
                ) from exc
    logger.info("context_builder: loaded %d constraints", len(constraints))

    # --- 5. Resolve Doramagic root for crystals directory ---
    # Reuse the same root from source_dir (walk up from source_dir)
    doramagic_root_candidate: Path | None = None
    env_root2 = _os.environ.get("DORAMAGIC_ROOT", "").strip()
    if env_root2:
        r = Path(env_root2).resolve()
        if r.is_dir() and (r / "knowledge").is_dir():
            doramagic_root_candidate = r
    if doramagic_root_candidate is None:
        walk2 = Path(__file__).resolve().parent
        for _ in range(12):
            if (walk2 / "knowledge").is_dir() and (walk2 / "packages").is_dir():
                doramagic_root_candidate = walk2
                break
            parent2 = walk2.parent
            if parent2 == walk2:
                break
            walk2 = parent2
    if doramagic_root_candidate is None:
        doramagic_root_candidate = (
            source_dir.parent.parent.parent
        )  # fallback: knowledge/sources/../..
    doramagic_root = doramagic_root_candidate

    # Normalise crystal directory name: 'finance-bp-009'
    crystal_dir_name = canonical_bp_id  # e.g. 'finance-bp-009'
    crystals_dir = doramagic_root / "knowledge" / "crystals" / crystal_dir_name

    # --- 6. Read Crystal IR ---
    crystal_ir_path = crystals_dir / "PRODUCTION.ir.yaml"
    if not crystal_ir_path.exists():
        raise FileNotFoundError(
            f"Crystal IR not found at {crystal_ir_path}. "
            f"Expected PRODUCTION.ir.yaml in {crystals_dir}"
        )
    try:
        with crystal_ir_path.open() as f:
            crystal_ir = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        raise ValueError(f"Failed to parse Crystal IR at {crystal_ir_path}: {exc}") from exc
    if not isinstance(crystal_ir, dict):
        crystal_ir = {}

    # --- 7. Read seed.md ---
    seed_path = crystals_dir / "PRODUCTION.openclaw.seed.md"
    if not seed_path.exists():
        raise FileNotFoundError(
            f"Seed file not found at {seed_path}. "
            f"Expected PRODUCTION.openclaw.seed.md in {crystals_dir}"
        )
    seed_content = seed_path.read_text(encoding="utf-8")

    # --- 8. QA Proof stub ---
    logger.warning(
        "context_builder: 真实 QA manifest 尚未接入，使用 stub creator_proof。"
        "creator_proof 仍为 stub，Day 2 后需接入真实 QA manifest。"
    )
    creator_proof = [
        {
            "model": "MiniMax-M2.7-highspeed",
            "host": "claude_code",
            "evidence_type": "trace_url",
            "evidence_url": "https://claude.ai/stub-trace-for-bp-009",
            "tested_at": "2026-04-18",
            "summary": "骨架 vertical slice 自测占位，待 Day 2 接入真实 QA manifest 后替换",
            "summary_en": (
                "Scaffold vertical slice stub proof — replace with real QA manifest after Day 2"
            ),
        }
    ]

    # --- 9. Determine slug from crystal_ir or fallback ---
    # Use a sensible slug derivation: e.g. "finance-bp-009-macd" → "macd-backtest-a-shares"
    # For now use the manifest slug if available, else derive from crystal_id
    crystal_id_raw = crystal_ir.get("crystal_id", "macd-a-shares")
    # Convert crystal_id to a slug-safe form for the manifest slug field
    # (The real slug comes from LLM in Phase 1; this is just the manifest key)
    manifest_slug = crystal_id_raw.replace("_", "-").lower() if crystal_id_raw else crystal_dir_name

    # --- Build manifest and context ---
    manifest = PublishManifest(
        slug=manifest_slug,
        blueprint_id=canonical_bp_id,
        blueprint_source=blueprint_source,
        blueprint_commit=blueprint_commit,
        seed_path=str(seed_path),
        crystal_ir_path=str(crystal_ir_path),
    )

    return PhaseContext(
        manifest=manifest,
        blueprint=blueprint,
        constraints=constraints,
        crystal_ir=crystal_ir,
        seed_content=seed_content,
        creator_proof=creator_proof,
        dry_run=dry_run,
        mock_mode=mock_mode,
    )


@app.command()
def publish(
    blueprint_id: Annotated[
        str, typer.Argument(help="Blueprint ID e.g. 'bp-009' or 'finance-bp-009'")
    ],
    model: Annotated[str, typer.Option(help="LLM model ID (defaults to LLM_MODEL env var)")] = "",
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Skip HTTP POST, show package summary")
    ] = False,
    mock: Annotated[
        bool, typer.Option("--mock", help="Use mock PhaseResults (no LLM calls)")
    ] = False,
    verbose: Annotated[bool, typer.Option("-v", "--verbose")] = False,
    temperature: Annotated[
        float, typer.Option("--temperature", help="LLM sampling temperature")
    ] = 0.1,
    max_tokens: Annotated[int, typer.Option("--max-tokens", help="LLM max output tokens")] = 4096,
    max_iter: Annotated[
        int, typer.Option("--max-iter", help="Tool-use loop max iterations per phase")
    ] = 5,
    max_retry: Annotated[
        int, typer.Option("--max-retry", help="Max retries on API fatal-gate errors")
    ] = 3,
    output_dir: Annotated[
        str, typer.Option("--output-dir", help="Output directory for package JSON")
    ] = ".phase2_out",
    include_high: Annotated[
        bool,
        typer.Option(
            "--include-high",
            help="Include 'high' severity constraints (default: fatal+critical only)",
        ),
    ] = False,
) -> None:
    """Run the full publishing pipeline for a blueprint.

    Phases run in order: content → constraints → faq → evaluator.
    Then: assemble package → local preflight → write to disk (POST not yet wired).

    Content phase makes real LLM calls; constraints/faq/evaluator use mock_result.
    Use --mock to skip all LLM calls (pure mock mode, useful for pipeline wiring tests).
    """
    import os as _os

    _setup_logging(verbose)

    # Resolve model from env if not provided
    resolved_model = model or _os.environ.get("LLM_MODEL", "MiniMax-M2.7-highspeed")

    typer.echo(f"web-publisher: starting pipeline for {blueprint_id!r}")
    typer.echo(
        f"  model={resolved_model}, dry_run={dry_run}, mock={mock}, "
        f"temperature={temperature}, max_tokens={max_tokens}, max_iter={max_iter}"
    )

    try:
        ctx = _build_context_from_blueprint_id(blueprint_id, dry_run=dry_run, mock_mode=mock)
    except (FileNotFoundError, ValueError) as exc:
        typer.echo(f"[ERROR] Context loading failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except NotImplementedError as exc:
        typer.echo("[SCAFFOLD] Context loading not yet implemented:", err=True)
        typer.echo(f"  {exc}", err=True)
        if mock:
            typer.echo("[SCAFFOLD] --mock mode: building minimal stub context...")
            ctx = _build_mock_context(blueprint_id, dry_run=dry_run)
        else:
            raise typer.Exit(code=1) from exc

    # Build adapter — read LLM config from environment
    from doramagic_shared_utils.llm_adapter import LLMAdapter

    if mock:
        adapter = LLMAdapter(provider_override="mock")
    else:
        # MiniMax uses Anthropic-compatible endpoint → force provider=anthropic
        llm_base_url = _os.environ.get("LLM_BASE_URL", "")
        llm_api_key = _os.environ.get("LLM_API_KEY", "")

        # Determine provider: if base_url contains 'anthropic' or 'minimax', use anthropic SDK
        if llm_base_url and ("anthropic" in llm_base_url or "minimax" in llm_base_url.lower()):
            provider_override = "anthropic"
            logger.info(
                "publish: using Anthropic-compatible endpoint for model=%s base_url=%s",
                resolved_model,
                llm_base_url,
            )
        else:
            # Let adapter infer from model_id
            provider_override = None

        adapter = LLMAdapter(provider_override=provider_override)
        if llm_base_url:
            adapter._base_url = llm_base_url
        if llm_api_key:
            adapter._api_key = llm_api_key

    # Run pipeline phase by phase.
    # Day 0.5: ContentPhase makes real LLM calls; constraints/faq/evaluator use mock_result.
    # When a phase raises NotImplementedError (scaffold placeholder), fall back to mock_result.
    from doramagic_web_publisher.assembler import Assembler
    from doramagic_web_publisher.errors import PhaseError
    from doramagic_web_publisher.phases import PHASES
    from doramagic_web_publisher.phases.constraints import ConstraintsPhase
    from doramagic_web_publisher.preflight import PreflightRunner

    # Build pipeline phases — allow include_high override for ConstraintsPhase
    active_phases = [
        ConstraintsPhase(include_high=include_high)
        if isinstance(phase, ConstraintsPhase)
        else phase
        for phase in PHASES
    ]

    for phase in active_phases:
        typer.echo(f"[PHASE] Running: {phase.name}")
        try:
            if mock or ctx.mock_mode:
                result = phase.mock_result()
                logger.info("Phase '%s': mock_result used (mock_mode)", phase.name)
            else:
                result = phase.run(ctx, adapter)
        except NotImplementedError:
            # Phase not yet implemented in Day 0.5 — fall back to mock_result
            logger.warning(
                "Phase '%s' raised NotImplementedError (scaffold); using mock_result fallback",
                phase.name,
            )
            typer.echo(f"  [SCAFFOLD] {phase.name} not implemented yet — using mock_result")
            result = phase.mock_result()
        except PhaseError as exc:
            typer.echo(f"[ERROR] Phase '{phase.name}' failed: {exc}", err=True)
            raise typer.Exit(code=3) from exc
        except Exception as exc:
            typer.echo(f"[ERROR] Phase '{phase.name}' unexpected error: {exc}", err=True)
            import traceback

            traceback.print_exc()
            raise typer.Exit(code=3) from exc
        ctx.results[phase.name] = result
        client_chars = result.token_usage.get("client_input_chars", 0) + result.token_usage.get(
            "client_output_chars", 0
        )
        approx_tokens = client_chars // 4 if client_chars else None
        prompt_tok = result.token_usage.get("prompt_tokens", 0)
        compl_tok = result.token_usage.get("completion_tokens", 0)
        in_chars = result.token_usage.get("client_input_chars", 0)
        out_chars = result.token_usage.get("client_output_chars", 0)
        typer.echo(
            f"  [DONE] {phase.name}: success={result.success}, "
            f"tokens(reported)={prompt_tok}+{compl_tok}, "
            f"client_chars={in_chars}in/{out_chars}out "
            f"(~{approx_tokens} approx tokens), iters={result.iterations}"
        )

    # Assemble package JSON
    assembler = Assembler()
    try:
        package = assembler.assemble(ctx)
    except Exception as exc:
        typer.echo(f"[ERROR] Assembly failed: {exc}", err=True)
        raise typer.Exit(code=3) from exc

    # Run preflight gates
    preflight_runner = PreflightRunner()
    preflight_results = preflight_runner.run(package)
    _print_preflight_results(preflight_results)

    # Print phase summary table
    typer.echo("\n=== Phase Summary ===")
    _hdr = (
        f"{'Phase':<15} {'Iters':>5} {'In chars':>10} {'Out chars':>10}"
        f" {'~Tokens':>8} {'Status':<8}"
    )
    typer.echo(_hdr)
    typer.echo("-" * 65)
    total_in = 0
    total_out = 0
    for phase in active_phases:
        r = ctx.results.get(phase.name)
        if r:
            in_c = r.token_usage.get("client_input_chars", 0)
            out_c = r.token_usage.get("client_output_chars", 0)
            total_in += in_c
            total_out += out_c
            approx_tok = (in_c + out_c) // 4
            typer.echo(
                f"{phase.name:<15} {r.iterations:>5} {in_c:>10,} {out_c:>10,} "
                f"{approx_tok:>8,} {'OK' if r.success else 'FAIL':<8}"
            )
    total_approx = (total_in + total_out) // 4
    typer.echo("-" * 65)
    typer.echo(f"{'TOTAL':<15} {'':>5} {total_in:>10,} {total_out:>10,} {total_approx:>8,}")
    typer.echo(
        f"\nMiniMax cost estimate: {total_approx:,} approx tokens "
        f"(char-based: {total_in + total_out:,} chars / 4)"
    )
    typer.echo("")

    # Write outputs to disk
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Derive output filename from blueprint_id
    bp_normalized = blueprint_id.strip()
    if bp_normalized.startswith("bp-"):
        bp_normalized = f"finance-{bp_normalized}"

    package_out = out_dir / f"{bp_normalized}.package.json"
    preflight_out = out_dir / f"{bp_normalized}.preflight.json"
    run_log_out = out_dir / f"{bp_normalized}.run.log"

    with package_out.open("w", encoding="utf-8") as f:
        json.dump(package, f, ensure_ascii=False, indent=2)
    typer.echo(f"[OUTPUT] Package JSON written to: {package_out}")

    preflight_dicts = [r.to_dict() for r in preflight_results]
    with preflight_out.open("w", encoding="utf-8") as f:
        json.dump(preflight_dicts, f, ensure_ascii=False, indent=2)
    typer.echo(f"[OUTPUT] Preflight results written to: {preflight_out}")

    # Write run log (phase summary)
    log_lines = [
        f"=== web_publisher run log for {blueprint_id} ===",
        f"Model: {resolved_model}",
        f"Phase order: {[p.name for p in active_phases]}",
        "",
        f"{'Phase':<15} {'Iters':>5} {'In chars':>10} {'Out chars':>10}"
        f" {'~Tokens':>8} {'Status':<8}",
        "-" * 65,
    ]
    for phase in active_phases:
        r = ctx.results.get(phase.name)
        if r:
            in_c = r.token_usage.get("client_input_chars", 0)
            out_c = r.token_usage.get("client_output_chars", 0)
            approx_tok = (in_c + out_c) // 4
            log_lines.append(
                f"{phase.name:<15} {r.iterations:>5} {in_c:>10,} {out_c:>10,} "
                f"{approx_tok:>8,} {'OK' if r.success else 'FAIL':<8}"
            )
    log_lines += [
        "-" * 65,
        f"{'TOTAL':<15} {'':>5} {total_in:>10,} {total_out:>10,} {total_approx:>8,}",
        "",
        f"MiniMax approx tokens: {total_approx:,} (~{total_approx // 1000:.1f}K)",
        "",
        "Preflight results:",
    ]
    for r in preflight_results:
        status = "PASS" if r.passed else f"FAIL[{r.level.upper()}]"
        log_lines.append(f"  {status:15} {r.gate_id}: {r.message}")

    with run_log_out.open("w", encoding="utf-8") as f:
        f.write("\n".join(log_lines) + "\n")
    typer.echo(f"[OUTPUT] Run log written to: {run_log_out}")

    # Exit code based on preflight fatals
    fatal_count = sum(1 for r in preflight_results if not r.passed and r.level == "fatal")
    if fatal_count:
        typer.echo(f"[WARN] {fatal_count} preflight gate(s) failed (fatal). Exit code 2.", err=True)
        raise typer.Exit(code=2)

    typer.echo(f"[SUCCESS] Pipeline complete. Slug: {package.get('slug')!r}")


@app.command(name="run-phase")
def run_phase(
    blueprint_id: Annotated[str, typer.Argument(help="Blueprint ID e.g. 'bp-009'")],
    phase_name: Annotated[
        str, typer.Argument(help="Phase name: content|constraints|faq|evaluator")
    ],
    model: Annotated[str, typer.Option(help="LLM model ID")] = "claude-sonnet-4-6",
    mock: Annotated[bool, typer.Option("--mock")] = False,
    verbose: Annotated[bool, typer.Option("-v", "--verbose")] = False,
) -> None:
    """Run a single pipeline phase for debugging."""
    _setup_logging(verbose)

    from doramagic_web_publisher.phases import PHASE_NAMES
    from doramagic_web_publisher.runtime.pipeline import Pipeline

    if phase_name not in PHASE_NAMES:
        typer.echo(f"Unknown phase '{phase_name}'. Available: {PHASE_NAMES}", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"Running single phase '{phase_name}' for {blueprint_id!r}")

    try:
        ctx = _build_context_from_blueprint_id(blueprint_id, dry_run=False, mock_mode=mock)
    except NotImplementedError as exc:
        typer.echo(f"[SCAFFOLD] {exc}", err=True)
        if mock:
            ctx = _build_mock_context(blueprint_id, dry_run=False)
        else:
            raise typer.Exit(code=1) from exc

    from doramagic_shared_utils.llm_adapter import LLMAdapter

    adapter = LLMAdapter(provider_override="mock" if mock else None)
    pipeline = Pipeline(adapter=adapter, model_id=model)

    try:
        ctx = pipeline.run_single_phase(phase_name, ctx)
        result = ctx.results.get(phase_name)
        typer.echo(f"Phase '{phase_name}' result: success={result and result.success}")
        if result:
            typer.echo(f"  Fields: {list(result.fields.keys())}")
    except NotImplementedError as exc:
        typer.echo(f"[SCAFFOLD] Phase not yet implemented: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command()
def preflight(
    package_json: Annotated[str, typer.Argument(help="Path to package JSON file")],
    verbose: Annotated[bool, typer.Option("-v", "--verbose")] = False,
) -> None:
    """Run local preflight gates on an existing package.json file."""
    _setup_logging(verbose)

    path = Path(package_json)
    if not path.exists():
        typer.echo(f"File not found: {package_json}", err=True)
        raise typer.Exit(code=1)

    with path.open() as f:
        package = json.load(f)

    from doramagic_web_publisher.preflight import PreflightRunner

    runner = PreflightRunner()
    results = runner.run(package)
    _print_preflight_results(results)

    fatal_count = sum(1 for r in results if not r.passed and r.level == "fatal")
    if fatal_count:
        raise typer.Exit(code=2)


# ------------------------------------------------------------------
# Private helpers
# ------------------------------------------------------------------


def _print_preflight_results(results: list) -> None:
    """Print preflight results in a readable format."""
    typer.echo("\nPreflight Results:")
    for r in results:
        icon = "✓" if r.passed else "✗"
        level_tag = f"[{r.level.upper()}]" if not r.passed else ""
        typer.echo(f"  {icon} {r.gate_id} {level_tag} {r.message}")
    typer.echo("")


def _build_mock_context(blueprint_id: str, dry_run: bool) -> PhaseContext:
    """Build a minimal stub PhaseContext for --mock mode testing."""
    from doramagic_web_publisher.runtime.models import PhaseContext, PublishManifest

    manifest = PublishManifest(
        slug="mock-crystal-placeholder",
        blueprint_id=blueprint_id,
        blueprint_source="zvtvz/zvt",
        blueprint_commit="f971f00c2181bc7d7fb7987a7875d4ec5960881a",
    )
    return PhaseContext(
        manifest=manifest,
        seed_content=(
            "# Mock Seed\n\nThis is a mock seed file for testing.\n\n"
            "## After Task Completion\n\n"
            "Task completed.\n"
            "This recipe is community-verified by Doramagic.\n"
            "Feedback and help improve: https://doramagic.ai/r/mock-crystal-placeholder\n"
        ),
        dry_run=dry_run,
        mock_mode=True,
    )


if __name__ == "__main__":
    app()
