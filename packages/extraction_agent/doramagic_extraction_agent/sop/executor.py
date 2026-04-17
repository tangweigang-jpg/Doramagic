"""SOP Executor — drives the agent through SOP phases with quality gates.

Implements three layers of output reliability (v3 Batch A):

1. **Output Contract**: Each phase declares ``required_artifacts`` that must
   exist after completion.  The executor verifies their presence.
2. **Auto-Save Fallback**: When an artifact is missing after phase completion,
   the executor extracts content from the LLM's final response and writes it.
3. **Blocking Gate**: Phases with ``blocking=True`` halt the pipeline if their
   required artifacts are still missing after auto-save and retry.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path

from ..core.agent_loop import ExtractionAgent, PhaseResult
from ..core.model_router import ModelRouter, ModelSpec
from ..state.checkpoint import CheckpointManager
from ..state.schema import AgentState
from ..tools.file_tracker import _ACTIVE_TRACKER, FileAccessTracker, set_active_tracker

logger = logging.getLogger(__name__)


def _extract_json(
    text: str,
    require_type: type | None = None,
) -> list | dict | None:
    """Extract JSON from free-form text.

    Args:
        text: LLM response text that may contain JSON.
        require_type: If set (``list`` or ``dict``), only return data
            matching this type. Used to enforce schema expectations.

    Tries three strategies:
    1. Parse the entire text as JSON
    2. Find fenced code blocks (```json ... ```)
    3. Scan for each opening bracket/brace and try parsing from there
    """

    def _accept(data: object) -> list | dict | None:
        if not isinstance(data, (list, dict)):
            return None
        if require_type and not isinstance(data, require_type):
            return None
        # Reject JSON Schema definitions that MiniMax echoes back when
        # the schema hint is injected into the L2 prompt. These contain
        # "$defs" or top-level "properties"+"type"="object" — they are
        # schema metadata, not data instances.
        if isinstance(data, dict) and ("$defs" in data or "$ref" in data):
            return None
        if isinstance(data, dict) and data.get("type") == "object" and "properties" in data:
            return None
        return data

    # Strategy 1: entire text is JSON
    try:
        result = _accept(json.loads(text))
        if result is not None:
            return result
    except json.JSONDecodeError:
        pass

    # Strategy 2: fenced code blocks (largest first)
    blocks = re.findall(r"```(?:json)?\s*\n(.*?)```", text, re.DOTALL)
    for block in sorted(blocks, key=len, reverse=True):
        try:
            result = _accept(json.loads(block))
            if result is not None:
                return result
        except json.JSONDecodeError:
            continue

    # Strategy 3: scan for each opening bracket/brace
    # Try every candidate position, not just the first/last
    for open_ch, close_ch in [("[", "]"), ("{", "}")]:
        # Find all opening positions
        candidates: list[str] = []
        pos = 0
        while True:
            start = text.find(open_ch, pos)
            if start == -1:
                break
            # Find the matching close from the end of string
            end = text.rfind(close_ch, start + 1)
            if end > start:
                candidates.append(text[start : end + 1])
            pos = start + 1
        # Try longest candidates first
        for candidate in sorted(candidates, key=len, reverse=True):
            try:
                result = _accept(json.loads(candidate))
                if result is not None:
                    return result
            except json.JSONDecodeError:
                continue

    return None


def _extract_yaml(text: str) -> dict | None:
    """Extract a YAML mapping from free-form text.

    Returns the parsed dict if valid, or None.
    """
    import yaml

    # Strategy 1: fenced YAML block
    blocks = re.findall(r"```(?:ya?ml)?\s*\n(.*?)```", text, re.DOTALL)
    for block in sorted(blocks, key=len, reverse=True):
        try:
            data = yaml.safe_load(block)
            if isinstance(data, dict):
                return data
        except yaml.YAMLError:
            continue

    # Strategy 2: entire text is YAML
    try:
        data = yaml.safe_load(text)
        if isinstance(data, dict):
            return data
    except yaml.YAMLError:
        pass

    return None


@dataclass
class Phase:
    """A single SOP phase definition.

    A Phase encapsulates everything the SOPExecutor needs to drive one
    step of the extraction SOP: the system prompt sent to the LLM, a
    factory that builds the initial user message from current state, the
    set of tools the agent may call, and an optional quality gate that
    evaluates the result.

    Attributes:
        name: Unique identifier for this phase (used as a checkpoint key).
        description: Human-readable label shown in log output.
        system_prompt: System-level instruction sent to the LLM for this phase.
        initial_message_builder: Callable ``(state, repo_path) -> str`` that
            produces the first user message handed to the agent loop.
        allowed_tools: Allowlist of tool names available to the agent during
            this phase.  ``None`` means all registered tools are allowed.
        requires_llm: When ``False`` the phase is handled entirely by
            ``python_handler`` and the agent loop is not invoked.
        python_handler: Async callable ``(state, repo_path) -> PhaseResult``
            used when ``requires_llm=False``.  Ignored otherwise.
        max_iterations: Hard cap on agent loop iterations for this phase.
        depends_on: Names of phases that must be completed before this phase
            may start.  The executor checks ``AgentState.is_phase_completed``
            for each name.
        quality_gate: Optional callable ``(state, repo_path) -> (passed, detail)``
            evaluated after phase completion.  A failing gate is recorded as a
            warning but does **not** stop execution.
        enable_convergence: When ``True``, the agent loop activates
            ``ConvergenceDetector`` for this phase.  The executor also reads
            ``state.extra["coverage_manifest"]`` at execution time and passes it
            as ``coverage_context`` to ``run_phase`` so worker phases can track
            directory coverage.  Should be set on all ``parallel_group="explore"``
            phases.
    """

    name: str
    description: str
    system_prompt: str
    initial_message_builder: Callable[[AgentState, Path], str]
    allowed_tools: list[str] | None = None
    requires_llm: bool = True
    python_handler: Callable[[AgentState, Path], Awaitable[PhaseResult]] | None = None
    max_iterations: int = 50
    depends_on: list[str] = field(default_factory=list)
    quality_gate: Callable[[AgentState, Path], tuple[bool, str]] | None = None
    required_artifacts: list[str] = field(default_factory=list)
    blocking: bool = False
    parallel_group: str | None = None  # phases with same group run concurrently
    enable_convergence: bool = False  # v10: activate ConvergenceDetector + coverage tracking


@dataclass
class ExecutionResult:
    """Aggregated result of running all phases through the SOPExecutor.

    Attributes:
        blueprint_id: The blueprint being extracted.
        completed_phases: Ordered list of phase names that finished
            successfully (including phases skipped due to prior checkpoints).
        failed_phase: Name of the first phase that failed, or ``None`` if all
            phases completed.
        total_tokens: Sum of tokens consumed across all LLM phases.
        total_iterations: Sum of agent-loop iterations across all LLM phases.
        errors: Accumulated error messages (phase failures, gate failures,
            unmet dependencies, exceptions).
        quality_gate_results: Mapping of ``phase_name -> (passed, detail)``
            for every phase whose quality gate was evaluated.
    """

    blueprint_id: str
    completed_phases: list[str] = field(default_factory=list)
    failed_phase: str | None = None
    total_tokens: int = 0
    total_iterations: int = 0
    errors: list[str] = field(default_factory=list)
    quality_gate_results: dict[str, tuple[bool, str]] = field(default_factory=dict)


class SOPExecutor:
    """Executes a sequence of SOP phases using the ExtractionAgent.

    The executor is intentionally stateless: all persistent state lives in the
    injected :class:`AgentState` and :class:`CheckpointManager`.  This makes
    it straightforward to resume a partially completed run by rehydrating state
    from a checkpoint and constructing a new ``SOPExecutor`` with the same
    phase list.

    Phases are executed in list order.  Before each phase the executor:

    1. Skips the phase when ``AgentState.is_phase_completed`` returns ``True``
       (checkpoint resume).
    2. Verifies that all ``Phase.depends_on`` names are already completed,
       halting if any are unmet.
    3. Marks the phase as *running* and saves a checkpoint so a crash mid-phase
       is visible in the next run.
    4. Delegates execution to either ``Phase.python_handler`` (pure-Python
       phases) or ``ExtractionAgent.run_phase`` (LLM-driven phases).
    5. Marks the phase as completed or failed in ``AgentState``.
    6. Evaluates ``Phase.quality_gate`` when present — a failing gate is
       recorded as a warning but does **not** stop execution.
    7. Saves a checkpoint after every phase regardless of gate outcome.

    If a phase returns a non-``"completed"`` status, or if an unhandled
    exception is raised, the executor saves state, appends to
    ``ExecutionResult.errors``, sets ``ExecutionResult.failed_phase``, and
    returns immediately without processing further phases.
    """

    def __init__(
        self,
        phases: list[Phase],
        agent: ExtractionAgent,
        checkpoint_mgr: CheckpointManager,
        state: AgentState,
        repo_path: Path,
        *,
        model_router: ModelRouter | None = None,
        agent_factory: Callable[[ModelSpec], ExtractionAgent] | None = None,
        max_parallel: int = 5,
    ) -> None:
        """Initialise the executor.

        Args:
            phases: Ordered list of :class:`Phase` objects defining the SOP.
            agent: The :class:`ExtractionAgent` that drives LLM-based phases.
            checkpoint_mgr: Persists ``AgentState`` to durable storage after
                each phase transition.
            state: Mutable agent state shared across all phases.
            repo_path: Absolute path to the repository being analysed.
            model_router: Optional router for per-phase model selection and
                failover.  When ``None``, the default ``agent`` is used for
                all phases (backward compatible).
            agent_factory: Callable that creates an ``ExtractionAgent`` from
                a ``ModelSpec``.  Required when ``model_router`` is set.
            max_parallel: Maximum number of phases to run concurrently within
                a parallel group.  Limits API request volume to avoid rate
                limiting.  Default 5.
        """
        self._phases = phases
        self._agent = agent
        self._checkpoint = checkpoint_mgr
        self._state = state
        self._repo_path = repo_path
        self._model_router = model_router
        self._agent_factory = agent_factory
        self._max_parallel = max_parallel
        self._validate_dependencies()

    def _validate_dependencies(self) -> None:
        """Check for unknown and circular dependencies at construction time."""
        phase_names = {p.name for p in self._phases}
        for phase in self._phases:
            unknown = set(phase.depends_on) - phase_names
            if unknown:
                raise ValueError(f"Phase '{phase.name}' has unknown dependencies: {unknown}")
        # Simple cycle detection via topological sort
        visited: set[str] = set()
        temp: set[str] = set()

        def visit(name: str) -> None:
            if name in temp:
                raise ValueError(f"Circular dependency detected involving '{name}'")
            if name in visited:
                return
            temp.add(name)
            phase = next(p for p in self._phases if p.name == name)
            for dep in phase.depends_on:
                visit(dep)
            temp.remove(name)
            visited.add(name)

        for p in self._phases:
            visit(p.name)

    def _build_execution_groups(self) -> list[list[Phase]]:
        """Organize phases into sequential execution groups.

        Phases with the same ``parallel_group`` are collected into a single
        group and will be executed concurrently.  Phases without a group
        form their own singleton group.
        """
        groups: list[list[Phase]] = []
        i = 0
        while i < len(self._phases):
            phase = self._phases[i]
            if phase.parallel_group:
                # Collect all consecutive phases with the same group
                group: list[Phase] = [phase]
                j = i + 1
                while (
                    j < len(self._phases) and self._phases[j].parallel_group == phase.parallel_group
                ):
                    group.append(self._phases[j])
                    j += 1
                groups.append(group)
                i = j
            else:
                groups.append([phase])
                i += 1
        return groups

    async def run(self) -> ExecutionResult:
        """Execute all phases, respecting dependencies, parallelism, and checkpoints.

        Phases with the same ``parallel_group`` run concurrently via
        ``asyncio.gather``.  All other phases run sequentially.
        """
        result = ExecutionResult(blueprint_id=self._state.blueprint_id)
        groups = self._build_execution_groups()

        for group in groups:
            if len(group) == 1:
                # Single phase — run normally
                phase = group[0]
                outcome = await self._run_single_phase(phase, result)
                if outcome == "break":
                    break
            else:
                # Parallel group — run concurrently
                outcome = await self._run_parallel_group(group, result)
                if outcome == "break":
                    break

        return result

    async def _run_parallel_group(
        self,
        group: list[Phase],
        result: ExecutionResult,
    ) -> str:
        """Run a group of phases concurrently.

        Returns "continue" or "break".
        """
        # Skip already-completed phases
        pending = [p for p in group if not self._state.is_phase_completed(p.name)]
        for p in group:
            if self._state.is_phase_completed(p.name):
                logger.info("Skipping completed phase: %s", p.name)
                result.completed_phases.append(p.name)

        if not pending:
            return "continue"

        # Check dependencies for all pending phases
        for phase in pending:
            unmet = [dep for dep in phase.depends_on if not self._state.is_phase_completed(dep)]
            if unmet:
                error = f"Phase {phase.name!r} has unmet dependencies: {unmet}"
                logger.error(error)
                result.errors.append(error)
                result.failed_phase = phase.name
                return "break"

        # Mark all as running
        for phase in pending:
            self._state.mark_phase_running(phase.name)
        self._checkpoint.save_state(self._state)

        names = [p.name for p in pending]
        logger.info(
            "Starting parallel group: %s (%d phases)",
            ", ".join(names),
            len(pending),
        )

        # Run phases concurrently with bounded parallelism to avoid API rate limits.
        # Default max_parallel=5 keeps request volume manageable for most providers.
        import asyncio

        max_parallel = getattr(self, "_max_parallel", 5)
        sem = asyncio.Semaphore(max_parallel)

        async def _run_with_sem(phase: Phase):
            async with sem:
                return await self._execute_single_phase(phase)

        tasks = [_run_with_sem(phase) for phase in pending]
        if len(pending) > max_parallel:
            logger.info(
                "Parallel group has %d phases, limiting to %d concurrent",
                len(pending),
                max_parallel,
            )
        phase_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for phase, phase_result in zip(pending, phase_results, strict=True):
            if isinstance(phase_result, Exception):
                error_msg = f"Phase {phase.name!r} raised: {phase_result}"
                logger.exception(error_msg)
                self._state.mark_phase_failed(phase.name, str(phase_result))

                if phase.blocking:
                    result.failed_phase = phase.name
                    result.errors.append(error_msg)
                    self._checkpoint.save_state(self._state)
                    return "break"
                else:
                    # Non-blocking phase exception: log and continue
                    result.errors.append(f"{error_msg} (non-blocking, skipped)")
                    self._checkpoint.save_state(self._state)
                    continue

            outcome = self._process_phase_result(phase, phase_result, result)
            if outcome == "break":
                return "break"

        return "continue"

    async def _run_single_phase(
        self,
        phase: Phase,
        result: ExecutionResult,
    ) -> str:
        """Run one phase. Returns 'continue' or 'break'."""
        # 1. Skip already-completed
        if self._state.is_phase_completed(phase.name):
            logger.info("Skipping completed phase: %s", phase.name)
            result.completed_phases.append(phase.name)
            return "continue"

        # 2. Check dependencies
        unmet = [dep for dep in phase.depends_on if not self._state.is_phase_completed(dep)]
        if unmet:
            error = f"Phase {phase.name!r} has unmet dependencies: {unmet}"
            logger.error(error)
            result.errors.append(error)
            result.failed_phase = phase.name
            return "break"

        # 3. Mark running
        self._state.mark_phase_running(phase.name)
        self._checkpoint.save_state(self._state)
        logger.info("Starting phase: %s — %s", phase.name, phase.description)

        # 4. Execute
        phase_result = await self._execute_single_phase(phase)
        if isinstance(phase_result, Exception):
            error_msg = f"Phase {phase.name!r} raised: {phase_result}"
            self._state.mark_phase_failed(phase.name, str(phase_result))
            result.errors.append(error_msg)
            self._checkpoint.save_state(self._state)
            if phase.blocking:
                logger.exception(error_msg)
                result.failed_phase = phase.name
                return "break"
            else:
                logger.warning("%s (non-blocking, skipped)", error_msg)
                return "continue"

        # 5. Process result
        outcome = self._process_phase_result(phase, phase_result, result)
        return outcome

    async def _execute_single_phase(
        self,
        phase: Phase,
    ) -> PhaseResult | Exception:
        """Execute a phase and return result or exception."""
        tracker = None
        token = None
        # v8: track file access for all worker phases (explore + workers groups)
        if phase.parallel_group in ("explore", "workers"):
            tracker = FileAccessTracker()
            token = set_active_tracker(tracker)
        try:
            if not phase.requires_llm and phase.python_handler is not None:
                return await phase.python_handler(
                    self._state,
                    self._repo_path,
                )
            return await self._run_agentic_phase_with_failover(phase)
        except Exception as exc:
            return exc
        finally:
            if tracker is not None and token is not None:
                _ACTIVE_TRACKER.reset(token)  # Proper ContextVar restore
                # Persist visited files
                vf_path = self._checkpoint.artifacts_dir / f"visited_files_{phase.name}.json"
                vf_path.write_text(tracker.to_json(), encoding="utf-8")

    def _process_phase_result(
        self,
        phase: Phase,
        phase_result: PhaseResult,
        result: ExecutionResult,
    ) -> str:
        """Process a completed phase result. Returns 'continue' or 'break'.

        Note: this is sync because artifact checks and quality gates are sync.
        For async failover on missing artifacts, call the async wrapper instead.
        """
        if phase_result.status == "completed":
            artifacts_dir = self._checkpoint.artifacts_dir

            # Output Contract: verify required artifacts
            if phase.required_artifacts:
                missing = self._check_required_artifacts(
                    phase,
                    artifacts_dir,
                    phase_result,
                )
                if missing and phase.blocking:
                    error = f"Blocking artifacts missing: {missing}"
                    logger.error(
                        "Phase %r: %s — pipeline halted",
                        phase.name,
                        error,
                    )
                    self._state.mark_phase_failed(phase.name, error)
                    result.failed_phase = phase.name
                    result.errors.append(error)
                    result.total_tokens += phase_result.total_tokens
                    result.total_iterations += phase_result.iterations
                    self._checkpoint.save_state(self._state)
                    return "break"

            # Mark completed
            artifacts: list[str] = []
            if artifacts_dir.exists():
                artifacts = [f.name for f in artifacts_dir.iterdir() if f.is_file()]
            self._state.mark_phase_completed(
                phase.name,
                iterations=phase_result.iterations,
                tokens=phase_result.total_tokens,
                artifacts=artifacts,
                transition_reason=(f"completed after {phase_result.iterations} iterations"),
            )
            result.completed_phases.append(phase.name)
        else:
            error_detail = phase_result.error or phase_result.status

            # Graceful promotion: if the agent hit max_iterations but the
            # required artifact was already written, treat as completed.
            # This happens when the model writes the artifact then tries
            # to do one more exploration round before being cut off.
            if phase_result.status in ("max_iterations", "error") and phase.required_artifacts:
                artifacts_dir = self._checkpoint.artifacts_dir
                all_present = all(
                    (artifacts_dir / a).is_file() and (artifacts_dir / a).stat().st_size > 0
                    for a in phase.required_artifacts
                )
                if all_present:
                    logger.info(
                        "Phase %r hit iteration cap but artifacts present — promoting to completed",
                        phase.name,
                    )
                    phase_result = PhaseResult(
                        phase_name=phase_result.phase_name,
                        status="completed",
                        iterations=phase_result.iterations,
                        total_tokens=phase_result.total_tokens,
                        final_text=phase_result.final_text,
                    )
                    return self._process_phase_result(phase, phase_result, result)

                # Artifacts missing at max_iterations: generate placeholder
                # so the pipeline can continue. Better partial data than halt.
                for artifact_name in phase.required_artifacts:
                    artifact_path = artifacts_dir / artifact_name
                    if not artifact_path.is_file() or artifact_path.stat().st_size == 0:
                        # Generate format-appropriate placeholder.
                        # For blueprint.yaml specifically, we embed the real
                        # blueprint_id and a sentinel flag (_assemble_failed: true)
                        # so downstream quality gates can detect the failure and
                        # report passed=false rather than silently treating an
                        # empty-stages placeholder as a valid blueprint.
                        if artifact_name == "blueprint.yaml":
                            placeholder = (
                                f"# {phase.name} — placeholder (assemble 失败自动生成)\n"
                                f"# WARNING: This is an auto-generated failure placeholder.\n"
                                f"# The bp_quality_gate BQ-05 check (stages≥2) will FAIL.\n"
                                f"id: {self._state.blueprint_id}\n"
                                f"name: 'UNASSEMBLED: assemble 失败'\n"
                                f"sop_version: '3.4'\n"
                                f"stages: []\n"
                                f"_assemble_failed: true\n"
                            )
                        elif artifact_name.endswith(".yaml"):
                            placeholder = (
                                f"# {phase.name} — placeholder\n"
                                f"id: placeholder\nname: placeholder\nstages: []\n"
                            )
                        elif artifact_name.endswith(".json"):
                            placeholder = "{}\n"
                        elif artifact_name.endswith(".jsonl"):
                            placeholder = ""
                        else:
                            placeholder = (
                                f"# {phase.name} — placeholder\n"
                                f"# Worker exhausted iterations without writing.\n"
                            )
                        artifact_path.write_text(placeholder, encoding="utf-8")
                        logger.warning(
                            "Phase %r: generated placeholder for %r (%d iterations exhausted)",
                            phase.name,
                            artifact_name,
                            phase_result.iterations,
                        )
                # Re-check — all should be present now
                phase_result = PhaseResult(
                    phase_name=phase_result.phase_name,
                    status="completed",
                    iterations=phase_result.iterations,
                    total_tokens=phase_result.total_tokens,
                    final_text="placeholder generated after max_iterations",
                )
                return self._process_phase_result(phase, phase_result, result)

            if not phase.blocking:
                # Non-blocking phase failure: mark as skipped, continue pipeline
                logger.warning(
                    "Phase %r failed (%s) but is non-blocking — skipping",
                    phase.name,
                    error_detail,
                )
                self._state.mark_phase_failed(phase.name, error_detail)
                result.errors.append(
                    f"Phase {phase.name!r}: {phase_result.status}"
                    f" — {error_detail} (non-blocking, skipped)"
                )
                result.total_tokens += phase_result.total_tokens
                result.total_iterations += phase_result.iterations
                self._checkpoint.save_state(self._state)
                return "continue"

            # Blocking phase failure: halt pipeline
            self._state.mark_phase_failed(phase.name, error_detail)
            result.failed_phase = phase.name
            result.errors.append(f"Phase {phase.name!r}: {phase_result.status} — {error_detail}")
            result.total_tokens += phase_result.total_tokens
            result.total_iterations += phase_result.iterations
            self._checkpoint.save_state(self._state)
            return "break"

        result.total_tokens += phase_result.total_tokens
        result.total_iterations += phase_result.iterations

        # Quality gate
        if phase.quality_gate is not None:
            gate_ok, gate_detail = phase.quality_gate(
                self._state,
                self._repo_path,
            )
            result.quality_gate_results[phase.name] = (gate_ok, gate_detail)
            level = logging.INFO if gate_ok else logging.WARNING
            logger.log(
                level,
                "Quality gate %s: %s — %s",
                phase.name,
                "PASS" if gate_ok else "FAIL",
                gate_detail,
            )
            if not gate_ok:
                result.errors.append(f"Quality gate {phase.name!r} FAIL: {gate_detail}")

        # Checkpoint
        self._checkpoint.save_state(self._state)
        return "continue"

    # ------------------------------------------------------------------
    # Phase execution with failover (v3 Batch B)
    # ------------------------------------------------------------------

    async def _run_agentic_phase_with_failover(
        self,
        phase: Phase,
    ) -> PhaseResult:
        """Execute an agentic phase, failing over to backup model if needed.

        Tries the primary model first.  If the phase fails with a
        retryable error (API failure, circuit break, max iterations) AND
        a fallback model is available via ``model_router``, creates a new
        agent with the fallback model and retries the phase from scratch.

        Non-retryable failures (context overflow already handled in
        agent_loop) are not eligible for failover.
        """
        initial_msg = phase.initial_message_builder(
            self._state,
            self._repo_path,
        )

        # Determine which agent to use (primary)
        agent = self._get_agent_for_phase(phase.name)

        # v10: resolve coverage_context at execution time from state.extra
        coverage_context = self._build_coverage_context(phase)

        # --- Primary attempt ---
        phase_result = await agent.run_phase(
            phase_name=phase.name,
            system_prompt=phase.system_prompt,
            initial_user_message=initial_msg,
            allowed_tools=phase.allowed_tools,
            max_iterations=phase.max_iterations,
            coverage_context=coverage_context,
            enable_convergence=getattr(phase, "enable_convergence", False),
        )

        # Success or no failover available → return as-is
        if phase_result.status == "completed":
            return phase_result

        if not self._model_router or not self._agent_factory:
            return phase_result

        fallback_spec = self._model_router.get_fallback(phase.name)
        if fallback_spec is None:
            return phase_result

        if not self._is_failover_eligible(phase_result):
            logger.info(
                "Phase %r failed with %r — not eligible for failover",
                phase.name,
                phase_result.status,
            )
            return phase_result

        # --- Failover attempt ---
        primary_spec = self._model_router.get_primary(phase.name)
        logger.warning(
            "Phase %r: primary model %s failed (%s) — failing over to %s",
            phase.name,
            primary_spec.model_id,
            phase_result.status,
            fallback_spec.model_id,
        )

        # Clean up stale artifacts from failed primary before fallback
        artifacts_dir = self._checkpoint.artifacts_dir
        if phase.required_artifacts and artifacts_dir.exists():
            for artifact_name in phase.required_artifacts:
                stale = artifacts_dir / artifact_name
                if stale.is_file():
                    stale.unlink()
                    logger.info(
                        "Phase %r: removed stale artifact %r before failover",
                        phase.name,
                        artifact_name,
                    )

        fallback_agent = self._get_or_create_agent(fallback_spec)

        # Reset phase state so it can run again
        self._state.mark_phase_running(phase.name)

        fallback_result = await fallback_agent.run_phase(
            phase_name=phase.name,
            system_prompt=phase.system_prompt,
            initial_user_message=initial_msg,
            allowed_tools=phase.allowed_tools,
            max_iterations=phase.max_iterations,
            coverage_context=coverage_context,
            enable_convergence=getattr(phase, "enable_convergence", False),
        )

        # Combine token counts from both attempts
        fallback_result = PhaseResult(
            phase_name=fallback_result.phase_name,
            status=fallback_result.status,
            iterations=(phase_result.iterations + fallback_result.iterations),
            total_tokens=(phase_result.total_tokens + fallback_result.total_tokens),
            final_text=fallback_result.final_text,
            error=fallback_result.error,
        )

        if fallback_result.status == "completed":
            logger.info(
                "Phase %r: failover to %s succeeded",
                phase.name,
                fallback_spec.model_id,
            )
        else:
            logger.error(
                "Phase %r: failover to %s also failed: %s",
                phase.name,
                fallback_spec.model_id,
                fallback_result.error,
            )

        return fallback_result

    async def _failover_for_missing_artifact(
        self,
        phase: Phase,
    ) -> PhaseResult | None:
        """Failover when primary completed but didn't write required artifact."""
        fallback_spec = self._model_router.get_fallback(phase.name)
        if not fallback_spec:
            return None

        primary_spec = self._model_router.get_primary(phase.name)
        logger.warning(
            "Phase %r: %s completed without artifact — failing over to %s",
            phase.name,
            primary_spec.model_id,
            fallback_spec.model_id,
        )

        # Clean stale artifacts
        artifacts_dir = self._checkpoint.artifacts_dir
        for artifact_name in phase.required_artifacts:
            stale = artifacts_dir / artifact_name
            if stale.is_file():
                stale.unlink()

        fallback_agent = self._get_or_create_agent(fallback_spec)
        self._state.mark_phase_running(phase.name)

        initial_msg = phase.initial_message_builder(
            self._state,
            self._repo_path,
        )
        coverage_context = self._build_coverage_context(phase)
        return await fallback_agent.run_phase(
            phase_name=phase.name,
            system_prompt=phase.system_prompt,
            initial_user_message=initial_msg,
            allowed_tools=phase.allowed_tools,
            max_iterations=phase.max_iterations,
            coverage_context=coverage_context,
            enable_convergence=getattr(phase, "enable_convergence", False),
        )

    def _build_coverage_context(self, phase: Phase) -> dict | None:
        """Build coverage_context scoped to the worker's responsibility.

        v10: specialized workers skip repo-wide directory coverage because
        their prompts target specific file subsets (non-code, math, resources).
        """
        if not getattr(phase, "enable_convergence", False):
            return None
        manifest = self._state.extra.get("coverage_manifest")
        if not manifest:
            return None
        must_dirs = list(manifest.get("must_visit_dirs", []))
        # Workers whose prompts target specific file types, not repo-wide dirs
        _SKIP_DIR_COVERAGE = {
            "worker_docs",  # reads non-code files (README, docs/)
            "worker_structural",  # reads doc knowledge sources (SKILL.md etc)
            "worker_resource",  # inventories dependencies/APIs, not code dirs
            "worker_math",  # driven by math-file list, not dir coverage
        }
        if phase.name in _SKIP_DIR_COVERAGE:
            must_dirs = []
        return {"must_visit_dirs": must_dirs}

    def _get_agent_for_phase(self, phase_name: str) -> ExtractionAgent:
        """Return the appropriate agent for a phase."""
        if self._model_router and self._agent_factory:
            spec = self._model_router.get_primary(phase_name)
            return self._get_or_create_agent(spec)
        return self._agent

    def _get_or_create_agent(self, spec: ModelSpec) -> ExtractionAgent:
        """Return a cached agent for the spec, or create one."""
        if not hasattr(self, "_agent_cache"):
            self._agent_cache: dict[str, ExtractionAgent] = {}
        cache_key = f"{spec.model_id}:{spec.api_format}:{spec.base_url}"
        if cache_key not in self._agent_cache:
            self._agent_cache[cache_key] = self._agent_factory(spec)
        return self._agent_cache[cache_key]

    @staticmethod
    def _is_failover_eligible(phase_result: PhaseResult) -> bool:
        """Determine if a phase failure should trigger failover.

        Eligible: error (API failure), circuit_break, max_iterations.
        Not eligible: completed, context/prompt overflow (model-agnostic).
        """
        if phase_result.status in ("error", "circuit_break", "max_iterations"):
            err = (phase_result.error or "").lower()
            # Context overflow: switching models won't help
            overflow_patterns = (
                "context",
                "prompt is too long",
                "too many tokens",
                "maximum context length",
            )
            return not any(p in err for p in overflow_patterns)
        return False

    # ------------------------------------------------------------------
    # Output Contract helpers (v3 Batch A)
    # ------------------------------------------------------------------

    def _check_required_artifacts(
        self,
        phase: Phase,
        artifacts_dir: Path,
        phase_result: PhaseResult,
    ) -> list[str]:
        """Verify required artifacts exist; auto-save from response if missing.

        Returns list of artifact names that are STILL missing after auto-save.
        """
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        still_missing: list[str] = []

        for artifact_name in phase.required_artifacts:
            artifact_path = artifacts_dir / artifact_name
            if artifact_path.is_file() and artifact_path.stat().st_size > 0:
                continue

            # Attempt auto-save from the LLM's final response text
            logger.warning(
                "Phase %r: required artifact %r not found — attempting auto-save from response",
                phase.name,
                artifact_name,
            )
            saved = self._auto_save_artifact(
                artifact_name,
                phase_result.final_text,
                artifacts_dir,
            )
            if saved:
                logger.info(
                    "Phase %r: auto-saved %r (%d bytes)",
                    phase.name,
                    artifact_name,
                    artifact_path.stat().st_size,
                )
            else:
                # Last resort: generate format-appropriate placeholder.
                # This is the UNIVERSAL safety net — no handler needs to
                # worry about writing artifacts on every exit path.
                # Better an empty/minimal artifact than a halted pipeline.
                if artifact_name.endswith(".yaml"):
                    placeholder = (
                        f"# {phase.name} — auto-generated placeholder\n"
                        f"id: placeholder\nname: placeholder\nstages: []\n"
                    )
                elif artifact_name.endswith(".json"):
                    placeholder = "{}\n"
                elif artifact_name.endswith(".jsonl"):
                    placeholder = ""
                elif artifact_name.endswith(".md"):
                    placeholder = (
                        f"# {phase.name} — placeholder\n\n"
                        f"No content produced. Pipeline continued with empty data.\n"
                    )
                else:
                    placeholder = ""
                artifact_path.write_text(placeholder, encoding="utf-8")
                logger.warning(
                    "Phase %r: generated placeholder for %r "
                    "(auto-save failed, using format-aware fallback)",
                    phase.name,
                    artifact_name,
                )

        return still_missing

    @staticmethod
    def _auto_save_artifact(
        artifact_name: str,
        response_text: str,
        artifacts_dir: Path,
    ) -> bool:
        """Extract content from LLM response and save as artifact.

        Validates format before saving:
        - .json: must be valid JSON; R1/R2/R3 artifacts require arrays
        - .yaml: must parse as a YAML mapping
        - .md/.txt: saved as-is (always succeeds if response non-empty)

        Returns True if the artifact was successfully saved.
        """
        if not response_text or not response_text.strip():
            return False

        artifact_path = artifacts_dir / artifact_name
        artifact_path.parent.mkdir(parents=True, exist_ok=True)

        if artifact_name.endswith(".json"):
            # Determine expected type: R1/R2/R3 artifacts are arrays
            array_artifacts = {
                "step2c_r1_raw_decisions.json",
                "step2c_r2_separated.json",
                "step2c_r3_classified.json",
            }
            require = list if artifact_name in array_artifacts else None
            content = _extract_json(response_text, require_type=require)
            if content is not None:
                artifact_path.write_text(
                    json.dumps(content, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                return True
            return False

        if artifact_name.endswith(".yaml"):
            # Must parse as a valid YAML mapping
            data = _extract_yaml(response_text)
            if data is not None:
                import yaml

                artifact_path.write_text(
                    yaml.dump(
                        data,
                        allow_unicode=True,
                        default_flow_style=False,
                        sort_keys=False,
                    ),
                    encoding="utf-8",
                )
                return True
            return False

        if artifact_name.endswith((".md", ".txt")):
            artifact_path.write_text(response_text, encoding="utf-8")
            return True

        return False
