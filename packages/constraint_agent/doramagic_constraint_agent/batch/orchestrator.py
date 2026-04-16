"""Constraint-only batch orchestrator.

Runs constraint extraction jobs independently of the blueprint pipeline.
Input contract: blueprint YAML path + repo path -> constraint JSONL output.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from doramagic_agent_core.batch.progress import ProgressTracker
from doramagic_agent_core.core.agent_loop import ExtractionAgent
from doramagic_agent_core.core.context_manager import ContextManager
from doramagic_agent_core.core.model_router import (
    ModelRouter,
    ModelSpec,
    build_model_router,
)
from doramagic_agent_core.core.tool_registry import ToolRegistry
from doramagic_agent_core.sop.executor import SOPExecutor
from doramagic_agent_core.state.checkpoint import CheckpointManager
from doramagic_agent_core.state.output import OutputManager
from doramagic_agent_core.state.schema import AgentState
from doramagic_agent_core.tools.artifacts import create_artifact_tools
from doramagic_agent_core.tools.filesystem import create_filesystem_tools
from doramagic_agent_core.tools.indexer import (
    build_structural_index,
    compute_iter_scale,
    create_index_tools,
)
from doramagic_agent_core.tools.knowledge_source_detector import (
    detect_knowledge_sources,
)
from doramagic_shared_utils.llm_adapter import LLMAdapter

from .job_queue import ConstraintBatchConfig, ConstraintJob

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class ConstraintResult:
    """Outcome of extracting constraints for a single blueprint."""

    blueprint_id: str
    status: str  # "completed" | "failed"
    total_tokens: int = 0
    errors: list[str] = field(default_factory=list)
    output_dir: str = ""


@dataclass
class ConstraintBatchResult:
    """Aggregated outcome of a full batch run."""

    batch_id: str
    completed: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    total_tokens: int = 0


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


class ConstraintBatchOrchestrator:
    """Runs constraint extraction jobs with bounded parallelism.

    Fully independent of the blueprint pipeline. Requires a pre-existing
    blueprint YAML as input.

    Args:
        config: Batch configuration including job list and LLM settings.
        project_root: Absolute path to the Doramagic project root.
    """

    def __init__(self, config: ConstraintBatchConfig, project_root: Path) -> None:
        self._config = config
        self._root = project_root

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def run(self) -> ConstraintBatchResult:
        """Execute all constraint extraction jobs with bounded parallelism."""
        tracker = ProgressTracker(len(self._config.jobs))
        sem = asyncio.Semaphore(self._config.concurrency)

        sorted_jobs = sorted(self._config.jobs, key=lambda j: j.priority)

        tasks = [
            asyncio.create_task(
                self._run_with_semaphore(sem, job, tracker),
                name=f"constraint-{job.blueprint_id}",
            )
            for job in sorted_jobs
        ]

        raw_results = await asyncio.gather(*tasks, return_exceptions=True)

        batch_result = ConstraintBatchResult(batch_id=self._config.batch_id)
        for job, outcome in zip(sorted_jobs, raw_results):
            if isinstance(outcome, BaseException):
                logger.error(
                    "Unexpected exception for %s: %s",
                    job.blueprint_id,
                    outcome,
                    exc_info=outcome,
                )
                batch_result.failed.append(job.blueprint_id)
            else:
                result: ConstraintResult = outcome
                batch_result.total_tokens += result.total_tokens
                if result.status == "completed":
                    batch_result.completed.append(result.blueprint_id)
                else:
                    batch_result.failed.append(result.blueprint_id)

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
        job: ConstraintJob,
        tracker: ProgressTracker,
    ) -> ConstraintResult:
        """Acquire semaphore then run a single job, catching all errors."""
        async with sem:
            tracker.start_job(job.blueprint_id)
            try:
                result = await self._run_single_job(job)
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
                return ConstraintResult(
                    blueprint_id=job.blueprint_id,
                    status="failed",
                    errors=[error_msg],
                )

    # ------------------------------------------------------------------
    # Single-job execution
    # ------------------------------------------------------------------

    async def _run_single_job(self, job: ConstraintJob) -> ConstraintResult:
        """Execute constraint extraction for one blueprint.

        Steps:
        1. Create LLMAdapter from config.
        2. Setup run directory.
        3. Build CheckpointManager, OutputManager.
        4. Create AgentState with blueprint_path.
        5. Build ToolRegistry (filesystem + artifacts + index tools).
        6. Build structural index + knowledge sources.
        7. Create ExtractionAgent + ModelRouter.
        8. Build constraint phases (v2/v3).
        9. Run SOPExecutor.
        10. Write output manifest.
        """
        # 1. Create adapter
        adapter = self._create_adapter()

        # 2. Setup run dir
        run_dir = self._root / "_runs" / job.blueprint_id
        run_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Run dir: %s", run_dir)

        # 3. Create components
        blueprint_path = Path(job.blueprint_path)
        repo_path = Path(job.repo_path)

        checkpoint = CheckpointManager(run_dir)

        # Derive repo_slug from repo path
        repo_slug = repo_path.name

        output_dir = self._root / "knowledge" / "sources" / job.domain / job.blueprint_id
        output_mgr = OutputManager(output_dir, job.blueprint_id, repo_slug=repo_slug)

        # 4. Create state
        if self._config.resume:
            state = checkpoint.load_state() or AgentState(
                blueprint_id=job.blueprint_id,
                domain=job.domain,
                repo_path=str(repo_path),
            )
        else:
            state = AgentState(
                blueprint_id=job.blueprint_id,
                domain=job.domain,
                repo_path=str(repo_path),
            )

        state.repo_path = str(repo_path)
        state.run_dir = str(run_dir)
        state.output_dir = str(output_mgr.output_dir)
        state.blueprint_path = str(blueprint_path)

        # Mark as extracting (prevent discover from re-triggering)
        self.set_extracting_status(output_mgr.output_dir)
        state.current_pipeline = "constraint"

        # Read commit_hash from blueprint YAML
        if not state.commit_hash:
            try:
                bp_data = yaml.safe_load(blueprint_path.read_text(encoding="utf-8"))
                state.commit_hash = (
                    bp_data.get("source", {}).get("commit_hash", "")
                    if isinstance(bp_data, dict)
                    else ""
                )
                if state.commit_hash:
                    logger.info("Blueprint commit_hash=%s", state.commit_hash[:7])
            except Exception:
                pass

        # 5. Build tool registry
        registry = ToolRegistry()
        for tool in create_filesystem_tools(repo_path):
            registry.register(tool)
        for tool in create_artifact_tools(checkpoint.artifacts_dir):
            registry.register(tool)

        # 6. Build structural index (needed by v2/v3 extract phases)
        structural_index = build_structural_index(repo_path)
        state.extra["structural_index"] = structural_index
        iter_scale = compute_iter_scale(structural_index["stats"]["total_py_files"])
        logger.info(
            "Structural index: %d py files, iter_scale=%.2f",
            structural_index["stats"]["total_py_files"],
            iter_scale,
        )
        for tool in create_index_tools(structural_index):
            registry.register(tool)

        # Detect knowledge sources (needed by v3 doc/rationalization phases)
        if self._config.constraint_version == "v3":
            ks_result = detect_knowledge_sources(repo_path)
            state.extra["knowledge_sources"] = ks_result.get("knowledge_sources", [])
            logger.info("Knowledge sources: %s", state.extra["knowledge_sources"])

        # 7. Create agent + model router
        context_mgr = ContextManager()
        agent = ExtractionAgent(
            adapter=adapter,
            tool_registry=registry,
            context_manager=context_mgr,
            checkpoint_mgr=checkpoint,
            model_id=self._config.llm_model,
            api_format=self._config.api_format,
        )

        model_router, agent_factory = self._build_model_router(registry, checkpoint)

        # 8. Build constraint phases
        fb_agent = None
        if model_router and agent_factory:
            fb_spec = model_router.get_fallback("con_derive")
            if fb_spec and fb_spec.model_id != self._config.llm_model:
                fb_agent = agent_factory(fb_spec)

        if self._config.constraint_version == "v3":
            from ..sop.constraint_phases_v3 import build_constraint_phases_v3

            con_phases = build_constraint_phases_v3(
                job.blueprint_id,
                blueprint_path,
                agent,
                fallback_agent=fb_agent,
            )
        else:
            from ..sop.constraint_phases_v2 import build_constraint_phases_v2

            con_phases = build_constraint_phases_v2(
                job.blueprint_id,
                blueprint_path,
                agent,
                fallback_agent=fb_agent,
            )

        # 9. Run executor
        con_executor = SOPExecutor(
            con_phases,
            agent,
            checkpoint,
            state,
            repo_path,
            model_router=model_router,
            agent_factory=agent_factory,
            max_parallel=3,
        )
        con_result = await con_executor.run()

        errors: list[str] = []
        if con_result.failed_phase:
            error_msg = (
                f"Constraint pipeline failed at phase "
                f"'{con_result.failed_phase}': " + "; ".join(con_result.errors)
            )
            logger.error(error_msg)
            errors.append(error_msg)

        # 10. Write manifest with source_blueprint_version for discover mode
        bp_version = self._get_blueprint_version(output_mgr.output_dir)
        final_mgr = OutputManager(output_mgr.output_dir, job.blueprint_id, repo_slug=repo_slug)
        final_mgr.write_manifest(
            blueprint_id=job.blueprint_id,
            domain=job.domain,
            commit_hash=state.commit_hash,
            llm_model=self._config.llm_model,
            total_tokens=state.total_tokens,
        )
        # Write extraction status into manifest for discover coordination
        extraction_status = "failed" if con_result.failed_phase else "done"
        self._update_extraction_status(
            final_mgr,
            extraction_status,
            bp_version,
        )

        status = "failed" if con_result.failed_phase else "completed"
        logger.info(
            "%s %s — tokens=%d output=%s",
            status.upper(),
            job.blueprint_id,
            state.total_tokens,
            output_mgr.output_dir,
        )
        return ConstraintResult(
            blueprint_id=job.blueprint_id,
            status=status,
            total_tokens=state.total_tokens,
            errors=errors,
            output_dir=str(output_mgr.output_dir),
        )

    # ------------------------------------------------------------------
    # Model routing
    # ------------------------------------------------------------------

    def _build_model_router(
        self,
        registry: ToolRegistry,
        checkpoint_mgr: CheckpointManager,
    ) -> tuple[ModelRouter | None, Callable | None]:
        """Build a ModelRouter from config, with an agent factory."""
        config = self._config

        primary = ModelSpec(
            model_id=config.llm_model,
            api_format=config.api_format,
            base_url=config.llm_base_url,
            api_key_env=config.llm_api_key_env,
        )

        fallback_specs = [ModelSpec(**fb) for fb in config.fallback_models]
        fallback = fallback_specs[0] if fallback_specs else None

        phase_overrides: dict[str, list[ModelSpec]] = {}
        for phase_name, override_dict in config.model_overrides.items():
            override_spec = ModelSpec(**override_dict)
            phase_overrides[phase_name] = [override_spec, primary]

        if not fallback and not phase_overrides:
            return None, None

        router = build_model_router(
            primary_spec=primary,
            fallback_spec=fallback,
            phase_overrides=phase_overrides,
        )

        def _make_agent(spec: ModelSpec) -> ExtractionAgent:
            fb_adapter = LLMAdapter()
            fb_adapter._base_url = spec.base_url
            fb_adapter._api_key = spec.resolve_api_key()
            fb_adapter._default_model = spec.model_id

            return ExtractionAgent(
                adapter=fb_adapter,
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
            fallback.model_id if fallback else "(none)",
            list(phase_overrides.keys()) or "(none)",
        )
        return router, _make_agent

    # ------------------------------------------------------------------
    # LLM adapter factory
    # ------------------------------------------------------------------

    @staticmethod
    def _get_blueprint_version(output_dir: Path) -> int:
        """Read the latest blueprint version from manifest.json."""
        manifest_path = output_dir / "manifest.json"
        if not manifest_path.exists():
            return 0
        try:
            m = json.loads(manifest_path.read_text(encoding="utf-8"))
            versions = m.get("blueprint_versions", [])
            if versions:
                return versions[0].get("version", 0)
        except (json.JSONDecodeError, OSError):
            pass
        return 0

    @staticmethod
    def _update_extraction_status(
        output_mgr: OutputManager,
        status: str,
        source_blueprint_version: int,
    ) -> None:
        """Write constraint_extraction_status into manifest.json."""
        manifest_path = output_mgr.output_dir / "manifest.json"
        try:
            m = json.loads(manifest_path.read_text(encoding="utf-8"))
            m["constraint_extraction_status"] = status
            if m.get("constraint_versions"):
                m["constraint_versions"][0]["source_blueprint_version"] = source_blueprint_version
            manifest_path.write_text(
                json.dumps(m, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to update extraction status: %s", exc)

    @staticmethod
    def set_extracting_status(output_dir: Path) -> None:
        """Mark a project as 'extracting' in manifest.json (for discover)."""
        manifest_path = output_dir / "manifest.json"
        if not manifest_path.exists():
            return
        try:
            m = json.loads(manifest_path.read_text(encoding="utf-8"))
            m["constraint_extraction_status"] = "extracting"
            manifest_path.write_text(
                json.dumps(m, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        except (json.JSONDecodeError, OSError):
            pass

    def _create_adapter(self) -> LLMAdapter:
        """Create a configured LLMAdapter from batch config."""
        adapter = LLMAdapter(provider_override="anthropic")
        adapter._default_model = self._config.llm_model
        if self._config.llm_base_url:
            adapter._base_url = self._config.llm_base_url
        api_key = os.environ.get(self._config.llm_api_key_env, "")
        if api_key:
            adapter._api_key = api_key
        return adapter
