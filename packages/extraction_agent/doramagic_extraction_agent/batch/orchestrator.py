"""Batch orchestrator — runs extraction jobs with bounded parallelism."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from doramagic_shared_utils.llm_adapter import LLMAdapter

from ..core.agent_loop import ExtractionAgent
from ..core.context_manager import ContextManager
from ..core.model_router import ModelRouter, ModelSpec, build_model_router
from ..core.tool_registry import ToolRegistry
from ..sop.blueprint_phases import (
    _compute_iter_scale,
    build_blueprint_phases_v4,
    build_blueprint_phases_v5,
)
from ..sop.executor import SOPExecutor
from ..state.checkpoint import CheckpointManager
from ..state.output import OutputManager
from ..state.schema import AgentState
from ..tools.artifacts import create_artifact_tools
from ..tools.filesystem import create_filesystem_tools
from ..tools.indexer import build_structural_index, create_index_tools
from ..tools.sources import mine_source_context
from .job_queue import BatchConfig, RepoJob
from .progress import ProgressTracker

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class RepoResult:
    """Outcome of extracting a single repository."""

    blueprint_id: str
    status: str  # "completed" | "failed" | "skipped"
    total_tokens: int = 0
    errors: list[str] = field(default_factory=list)
    output_dir: str = ""


@dataclass
class BatchResult:
    """Aggregated outcome of a full batch run."""

    batch_id: str
    completed: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    total_tokens: int = 0


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


class BatchOrchestrator:
    """Runs a list of :class:`RepoJob` entries with bounded parallelism.

    Jobs are sorted by ``priority`` (ascending, so priority=1 runs first),
    then executed concurrently up to ``BatchConfig.concurrency`` at a time
    using an :class:`asyncio.Semaphore`.

    A failure in one repo is isolated: the exception is caught, logged, and
    converted to a :class:`RepoResult` with ``status="failed"``; remaining
    jobs are unaffected.

    Args:
        config: Batch configuration including job list, LLM settings, and
            concurrency limit.
        project_root: Absolute path to the Doramagic project root.  Used to
            locate the ``_runs/`` directory and the default ``repos/``
            sub-directory.
    """

    def __init__(self, config: BatchConfig, project_root: Path) -> None:
        self._config = config
        self._root = project_root

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def run(self) -> BatchResult:
        """Execute all jobs with bounded parallelism.

        Returns:
            A :class:`BatchResult` summarising completed, failed, and total
            tokens consumed across the batch.
        """
        tracker = ProgressTracker(len(self._config.repos))
        sem = asyncio.Semaphore(self._config.concurrency)

        # Sort by priority ascending (lower number = higher priority)
        sorted_jobs = sorted(self._config.repos, key=lambda j: j.priority)

        tasks = [
            asyncio.create_task(
                self._run_with_semaphore(sem, job, tracker),
                name=f"extract-{job.blueprint_id}",
            )
            for job in sorted_jobs
        ]

        raw_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Aggregate — gather(..., return_exceptions=True) never raises, but
        # individual entries may be BaseException if the task itself leaked.
        batch_result = BatchResult(batch_id=self._config.batch_id)
        for job, outcome in zip(sorted_jobs, raw_results):
            if isinstance(outcome, BaseException):
                # Uncaught exception that escaped _run_with_semaphore
                logger.error(
                    "Unexpected exception for %s: %s",
                    job.blueprint_id,
                    outcome,
                    exc_info=outcome,
                )
                batch_result.failed.append(job.blueprint_id)
            else:
                repo_result: RepoResult = outcome
                batch_result.total_tokens += repo_result.total_tokens
                if repo_result.status == "completed":
                    batch_result.completed.append(repo_result.blueprint_id)
                else:
                    batch_result.failed.append(repo_result.blueprint_id)

        logger.info(
            "Batch %s finished: %d completed, %d failed, %d total tokens",
            self._config.batch_id,
            len(batch_result.completed),
            len(batch_result.failed),
            batch_result.total_tokens,
        )
        logger.info("\n%s", tracker.summary())
        return batch_result

    # ------------------------------------------------------------------
    # Semaphore wrapper
    # ------------------------------------------------------------------

    async def _run_with_semaphore(
        self,
        sem: asyncio.Semaphore,
        job: RepoJob,
        tracker: ProgressTracker,
    ) -> RepoResult:
        """Acquire semaphore then run a single repo, catching all errors."""
        async with sem:
            tracker.start_job(job.blueprint_id)
            try:
                result = await self._run_single_repo(job)
                if result.status == "completed":
                    tracker.complete_job(job.blueprint_id, result.total_tokens)
                else:
                    tracker.fail_job(
                        job.blueprint_id,
                        "; ".join(result.errors) or "unknown failure",
                    )
                return result
            except Exception as exc:
                error_msg = f"{type(exc).__name__}: {exc}"
                logger.exception("Unhandled error for %s", job.blueprint_id)
                tracker.fail_job(job.blueprint_id, error_msg)
                return RepoResult(
                    blueprint_id=job.blueprint_id,
                    status="failed",
                    errors=[error_msg],
                )

    # ------------------------------------------------------------------
    # Model routing
    # ------------------------------------------------------------------

    def _build_model_router(
        self,
        registry: ToolRegistry,
        checkpoint_mgr: CheckpointManager,
    ) -> tuple[ModelRouter | None, Callable | None]:
        """Build a ModelRouter from config, with an agent factory.

        Returns (None, None) if no fallback models are configured.
        """
        config = self._config

        # Primary model spec from main config
        primary = ModelSpec(
            model_id=config.llm_model,
            api_format=config.api_format,
            base_url=config.llm_base_url,
            api_key_env=config.llm_api_key_env,
        )

        # Fallback models
        fallback_specs = [ModelSpec(**fb) for fb in config.fallback_models]
        fallback = fallback_specs[0] if fallback_specs else None

        # Phase overrides
        phase_overrides: dict[str, list[ModelSpec]] = {}
        for phase_name, override_dict in config.model_overrides.items():
            override_spec = ModelSpec(**override_dict)
            phase_overrides[phase_name] = [override_spec, primary]

        # Only build router if there's something to route
        if not fallback and not phase_overrides:
            return None, None

        router = build_model_router(
            primary_spec=primary,
            fallback_spec=fallback,
            phase_overrides=phase_overrides,
        )

        # Agent factory: creates a new ExtractionAgent for a given ModelSpec
        def _make_agent(spec: ModelSpec) -> ExtractionAgent:
            adapter = LLMAdapter()
            adapter._base_url = spec.base_url
            adapter._api_key = spec.resolve_api_key()
            adapter._default_model = spec.model_id

            return ExtractionAgent(
                adapter=adapter,
                tool_registry=registry,
                context_manager=ContextManager(),
                checkpoint_mgr=checkpoint_mgr,
                model_id=spec.model_id,
                api_format=spec.api_format,
                max_tokens_per_call=spec.max_tokens_per_call,
            )

        logger.info(
            "ModelRouter: primary=%s fallback=%s overrides=%s",
            primary.model_id,
            fallback.model_id,
            list(phase_overrides.keys()) or "(none)",
        )
        return router, _make_agent

    # ------------------------------------------------------------------
    # Single-repo execution
    # ------------------------------------------------------------------

    async def _run_single_repo(self, job: RepoJob) -> RepoResult:
        """Execute one repo: setup adapter → build tools → build phases → run executor.

        Steps:
        1. Create :class:`LLMAdapter` from batch config.
        2. Create ``_runs/{blueprint_id}/`` directory.
        3. Instantiate :class:`CheckpointManager` and :class:`OutputManager`.
        4. Load or create :class:`AgentState`.
        5. Build :class:`ToolRegistry` with filesystem and artifact tools.
        6. Construct :class:`ExtractionAgent`.
        7. Run blueprint phases (unless ``job.skip_blueprint``).
        8. Run constraint phases (unless ``job.skip_constraint``).
        9. Write output manifest.

        Args:
            job: The :class:`RepoJob` describing what to extract.

        Returns:
            :class:`RepoResult` with status, token count, and output dir.
        """
        # 1. Create adapter
        adapter = self._create_adapter()

        # 2. Setup run dir
        run_dir = self._root / "_runs" / job.blueprint_id
        run_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Run dir: %s", run_dir)

        # 3. Create components
        checkpoint = CheckpointManager(run_dir)
        # Derive repo_slug for versioned directory naming (e.g. finance-bp-009--zvt)
        repo_slug = ""
        if job.repo_path:
            repo_slug = Path(job.repo_path).name
        elif job.repo_url:
            repo_slug = job.repo_url.rstrip("/").split("/")[-1].replace(".git", "")
        output_dir = self._root / "knowledge" / "sources" / job.domain / job.blueprint_id
        output_mgr = OutputManager(output_dir, job.blueprint_id, repo_slug=repo_slug)

        # 4. Load or create state — only resume if config.resume=True (Fix 2)
        if self._config.resume:
            state = checkpoint.load_state() or AgentState(
                blueprint_id=job.blueprint_id,
                domain=job.domain,
                repo_path="",  # resolved below after potential clone
            )
        else:
            state = AgentState(
                blueprint_id=job.blueprint_id,
                domain=job.domain,
                repo_path="",  # always start fresh when resume=False
            )

        # Resolve repo path: local path takes priority, fall back to cloning from URL
        repo_path_str = job.repo_path
        if not repo_path_str and job.repo_url:
            # Clone the repo
            repo_name = job.repo_url.rstrip("/").split("/")[-1].replace(".git", "")
            local_repo = self._root / "repos" / repo_name
            if not local_repo.exists():
                import subprocess

                logger.info("Cloning %s to %s", job.repo_url, local_repo)
                subprocess.run(
                    ["git", "clone", "--depth", "1", job.repo_url, str(local_repo)],
                    check=True,
                    capture_output=True,
                    text=True,
                )
            repo_path_str = str(local_repo)
        elif not repo_path_str:
            # Try to guess from blueprint_id
            repo_path_str = str(self._root / "repos" / job.blueprint_id.split("-")[-1])

        state.repo_path = repo_path_str
        state.run_dir = str(run_dir)
        state.output_dir = str(output_mgr.output_dir)  # uses slug-suffixed path

        # Override repo_path from job if explicitly provided (supports re-runs
        # pointing at a different clone location)
        if job.repo_path and state.repo_path != job.repo_path:
            logger.debug(
                "Overriding repo_path for %s: %s → %s",
                job.blueprint_id,
                state.repo_path,
                job.repo_path,
            )
            state.repo_path = job.repo_path

        repo_path = Path(state.repo_path)

        # 5. Create tool registry (+ structural index for blueprint phases)
        registry = ToolRegistry()
        for tool in create_filesystem_tools(repo_path):
            registry.register(tool)
        for tool in create_artifact_tools(checkpoint.artifacts_dir):
            registry.register(tool)

        # Register index tools when blueprint OR constraint v2/v3 phases need them.
        # get_skeleton is used by constraint v2/v3 extract phases even with skip_blueprint.
        need_index_tools = (not job.skip_blueprint) or (
            not job.skip_constraint and self._config.constraint_version in ("v2", "v3")
        )

        if need_index_tools:
            structural_index = build_structural_index(repo_path)
            state.extra["structural_index"] = structural_index
            logger.info(
                "Structural index: %d files, %d math-related",
                structural_index["stats"]["total_py_files"],
                structural_index["stats"]["math_related_files"],
            )
            iter_scale = _compute_iter_scale(structural_index["stats"]["total_py_files"])
            logger.info(
                "Repo size tier: %d py files → iter_scale=%.2f",
                structural_index["stats"]["total_py_files"],
                iter_scale,
            )
            for tool in create_index_tools(structural_index):
                registry.register(tool)

        if not job.skip_blueprint:
            source_context = mine_source_context(repo_path)
            state.extra["source_context"] = source_context
            logger.info("Source context: %d chars", len(source_context))

            # v7: detect knowledge source types (code/document/config)
            from ..tools.knowledge_source_detector import detect_knowledge_sources

            ks_result = detect_knowledge_sources(repo_path)
            state.extra["knowledge_sources"] = ks_result.get("knowledge_sources", [])
            logger.info("Knowledge sources: %s", state.extra["knowledge_sources"])

        # 6. Create agent + model router
        context_mgr = ContextManager()
        agent = ExtractionAgent(
            adapter=adapter,
            tool_registry=registry,
            context_manager=context_mgr,
            checkpoint_mgr=checkpoint,
            model_id=self._config.llm_model,
            api_format=self._config.api_format,
        )

        # Build model router for failover support
        model_router, agent_factory = self._build_model_router(
            registry,
            checkpoint,
        )

        errors: list[str] = []

        # 7. Blueprint pipeline
        if not job.skip_blueprint:
            state.current_pipeline = "blueprint"
            if self._config.blueprint_version == "v5":
                bp_phases = build_blueprint_phases_v5(
                    job.blueprint_id,
                    agent=agent,
                    iter_scale=iter_scale,
                )
            else:
                bp_phases = build_blueprint_phases_v4(job.blueprint_id)
            bp_executor = SOPExecutor(
                bp_phases,
                agent,
                checkpoint,
                state,
                repo_path,
                model_router=model_router,
                agent_factory=agent_factory,
                max_parallel=3,  # v6.4: reduced from 5 to avoid Token Plan rate limits
            )
            bp_result = await bp_executor.run()

            # Check if blueprint extraction succeeded: failed_phase OR missing output artifact
            bp_failed = bp_result.failed_phase is not None
            # v6 naming: check LATEST.yaml symlink first, fall back to blueprint.yaml
            bp_output = output_mgr.output_dir / "LATEST.yaml"
            if not bp_output.exists():
                bp_output = output_mgr.output_dir / "blueprint.yaml"  # legacy
            if not bp_failed and not bp_output.exists():
                bp_failed = True
                errors.append("Blueprint assembly did not produce LATEST.yaml or blueprint.yaml")
            # Also validate the YAML is parseable
            if not bp_failed and bp_output.exists():
                import yaml as _yaml

                try:
                    _yaml.safe_load(bp_output.read_text())
                except _yaml.YAMLError as e:
                    bp_failed = True
                    errors.append(f"Blueprint YAML is invalid: {e}")

            if bp_failed:
                if bp_result.failed_phase:
                    error_msg = (
                        f"Blueprint pipeline failed at phase "
                        f"'{bp_result.failed_phase}': " + "; ".join(bp_result.errors)
                    )
                    logger.error(error_msg)
                    errors.append(error_msg)
                else:
                    logger.error(
                        "Blueprint pipeline completed but blueprint.yaml is missing for %s",
                        job.blueprint_id,
                    )
                # Write a partial manifest and bail out
                output_mgr.write_manifest(
                    blueprint_id=job.blueprint_id,
                    domain=job.domain,
                    commit_hash=state.commit_hash,
                    llm_model=self._config.llm_model,
                    total_tokens=state.total_tokens,
                )
                return RepoResult(
                    blueprint_id=job.blueprint_id,
                    status="failed",
                    total_tokens=state.total_tokens,
                    errors=errors,
                    output_dir=str(output_mgr.output_dir),
                )
        else:
            logger.info(
                "Skipping blueprint pipeline for %s (skip_blueprint=True)", job.blueprint_id
            )
            # Fix 3: set blueprint_path so constraint phases can find the blueprint
            bp_path = output_mgr.output_dir / "LATEST.yaml"
            if not bp_path.exists():
                bp_path = output_mgr.output_dir / "blueprint.yaml"  # legacy fallback
            if not bp_path.exists():
                # Also check the canonical knowledge/ location
                bp_path = (
                    self._root
                    / "knowledge"
                    / "blueprints"
                    / job.domain
                    / f"{job.blueprint_id}.yaml"
                )
            if bp_path.exists():
                state.blueprint_path = str(bp_path)
                logger.info("skip_blueprint: resolved blueprint_path=%s", state.blueprint_path)
                # Extract commit_hash from blueprint YAML for P7 enrichment
                if not state.commit_hash:
                    import yaml

                    try:
                        bp_data = yaml.safe_load(bp_path.read_text(encoding="utf-8"))
                        state.commit_hash = (
                            bp_data.get("source", {}).get("commit_hash", "")
                            if isinstance(bp_data, dict)
                            else ""
                        )
                        if state.commit_hash:
                            logger.info("skip_blueprint: commit_hash=%s", state.commit_hash[:7])
                    except Exception:
                        pass
            else:
                errors.append(
                    f"skip_blueprint=True but no blueprint found for {job.blueprint_id} "
                    f"(checked output_dir and knowledge/blueprints/{job.domain}/)"
                )
                output_mgr.write_manifest(
                    blueprint_id=job.blueprint_id,
                    domain=job.domain,
                    commit_hash=state.commit_hash,
                    llm_model=self._config.llm_model,
                    total_tokens=state.total_tokens,
                )
                return RepoResult(
                    blueprint_id=job.blueprint_id,
                    status="failed",
                    total_tokens=state.total_tokens,
                    errors=errors,
                    output_dir=str(output_mgr.output_dir),
                )

        # 8. Constraint pipeline
        if not job.skip_constraint:
            # Import dynamically to avoid circular deps at module load time
            try:
                if self._config.constraint_version == "v3":
                    from ..sop.constraint_phases_v3 import (
                        build_constraint_phases_v3,
                    )
                elif self._config.constraint_version == "v2":
                    from ..sop.constraint_phases_v2 import (
                        build_constraint_phases_v2,
                    )
                else:
                    from ..sop.constraint_phases import build_constraint_phases
            except ImportError:
                logger.warning(
                    "constraint_phases module not found; skipping constraint pipeline for %s",
                    job.blueprint_id,
                )
            else:
                state.current_pipeline = "constraint"
                # Use LATEST.yaml (symlink to versioned blueprint.vN.yaml)
                # or fall back to state.blueprint_path set by bp_finalize
                bp_path = output_mgr.output_dir / "LATEST.yaml"
                if not bp_path.exists() and state.blueprint_path:
                    bp_path = Path(state.blueprint_path)
                if not bp_path.exists():
                    bp_path = output_mgr.output_dir / "blueprint.yaml"  # legacy fallback
                if self._config.constraint_version in ("v2", "v3"):
                    # Build fallback agent for derive chunk retry.
                    # Skip if fallback is the same model as primary (no point retrying).
                    fb_agent = None
                    if model_router and agent_factory:
                        fb_spec = model_router.get_fallback("con_derive")
                        if fb_spec and fb_spec.model_id != self._config.llm_model:
                            fb_agent = agent_factory(fb_spec)
                    if self._config.constraint_version == "v3":
                        con_phases = build_constraint_phases_v3(
                            job.blueprint_id,
                            bp_path,
                            agent,
                            fallback_agent=fb_agent,
                        )
                    else:
                        con_phases = build_constraint_phases_v2(
                            job.blueprint_id,
                            bp_path,
                            agent,
                            fallback_agent=fb_agent,
                        )
                else:
                    con_phases = build_constraint_phases(job.blueprint_id, bp_path)
                # v2/v3 have 14+ parallel phases; limit concurrency to avoid API rate limits
                max_par = 4 if self._config.constraint_version in ("v2", "v3") else 5
                con_executor = SOPExecutor(
                    con_phases,
                    agent,
                    checkpoint,
                    state,
                    repo_path,
                    model_router=model_router,
                    agent_factory=agent_factory,
                    max_parallel=max_par,
                )
                con_result = await con_executor.run()
                if con_result.failed_phase:
                    error_msg = (
                        f"Constraint pipeline failed at phase "
                        f"'{con_result.failed_phase}': " + "; ".join(con_result.errors)
                    )
                    logger.error(error_msg)
                    errors.append(error_msg)
                    # Constraint failure is non-fatal: write manifest and mark failed
                    output_mgr.write_manifest(
                        blueprint_id=job.blueprint_id,
                        domain=job.domain,
                        commit_hash=state.commit_hash,
                        llm_model=self._config.llm_model,
                        total_tokens=state.total_tokens,
                    )
                    return RepoResult(
                        blueprint_id=job.blueprint_id,
                        status="failed",
                        total_tokens=state.total_tokens,
                        errors=errors,
                        output_dir=str(output_mgr.output_dir),
                    )
        else:
            logger.info(
                "Skipping constraint pipeline for %s (skip_constraint=True)",
                job.blueprint_id,
            )

        # 9. Write manifest — reload from disk to preserve version entries
        #    added by _finalize_handler's OutputManager during the pipeline.
        final_mgr = OutputManager(output_mgr.output_dir, job.blueprint_id, repo_slug=repo_slug)
        final_mgr.write_manifest(
            blueprint_id=job.blueprint_id,
            domain=job.domain,
            commit_hash=state.commit_hash,
            llm_model=self._config.llm_model,
            total_tokens=state.total_tokens,
        )

        logger.info(
            "Completed %s — tokens=%d output=%s",
            job.blueprint_id,
            state.total_tokens,
            output_mgr.output_dir,
        )
        return RepoResult(
            blueprint_id=job.blueprint_id,
            status="completed",
            total_tokens=state.total_tokens,
            output_dir=str(output_mgr.output_dir),
        )

    # ------------------------------------------------------------------
    # LLM adapter factory
    # ------------------------------------------------------------------

    def _create_adapter(self) -> LLMAdapter:
        """Create a configured :class:`LLMAdapter` from batch config.

        Reads the API key from the environment variable named by
        ``BatchConfig.llm_api_key_env``.  If the variable is not set,
        the adapter falls back to SDK-level defaults (e.g. ``ANTHROPIC_API_KEY``).

        Returns:
            A ready-to-use :class:`LLMAdapter` instance.
        """
        import os

        adapter = LLMAdapter(provider_override="anthropic")
        adapter._default_model = self._config.llm_model
        if self._config.llm_base_url:
            adapter._base_url = self._config.llm_base_url
        api_key = os.environ.get(self._config.llm_api_key_env, "")
        if api_key:
            adapter._api_key = api_key
        return adapter
