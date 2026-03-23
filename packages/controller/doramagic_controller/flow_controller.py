"""FlowController — Outer layer of the dual-layer fusion architecture.

Re-entrant state machine that controls the entire Doramagic pipeline.
Manages flow, leases, degradation, and budget. Phase executors do the actual work.

Architecture:
    ┌─────────────────────────────────────────────────────────┐
    │  FlowController (this file)                              │
    │    ├── LeaseManager (checkpoint-based token control)      │
    │    ├── BudgetManager (per-phase cost/token/time)          │
    │    ├── PlatformAdapter (I/O with user)                    │
    │    └── PhaseExecutor dispatch (executors do the work)     │
    └─────────────────────────────────────────────────────────┘

Re-entrant execution model (for OpenClaw):
    Invocation 1: INIT → PHASE_A → need clarification? → EXIT (save state)
    Invocation 2: load state → PHASE_A (resume) → PHASE_B → ... → DONE → EXIT
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from doramagic_contracts.adapter import PlatformAdapter, ProgressUpdate
from doramagic_contracts.budget import BudgetPolicy, BudgetSnapshot
from doramagic_contracts.envelope import ModuleResultEnvelope, RunMetrics, WarningItem
from doramagic_contracts.executor import ExecutorConfig, PhaseExecutor

from .budget_manager import BudgetManager
from .lease_manager import LeaseManager
from .state_definitions import MAX_REVISE_LOOPS, PHASE_EXECUTOR_MAP, TRANSITIONS, Phase

logger = logging.getLogger("doramagic.controller")


class ControllerState:
    """Serializable controller state for re-entrant execution."""

    def __init__(
        self,
        run_id: str,
        phase: Phase = Phase.INIT,
        raw_input: str = "",
        lease_token: str = "",
        revise_count: int = 0,
        phase_artifacts: dict[str, Any] | None = None,
        degradation_log: list[str] | None = None,
    ) -> None:
        self.run_id = run_id
        self.phase = phase
        self.raw_input = raw_input
        self.lease_token = lease_token
        self.revise_count = revise_count
        self.phase_artifacts: dict[str, Any] = phase_artifacts or {}
        self.degradation_log: list[str] = degradation_log or []

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "phase": self.phase.value,
            "raw_input": self.raw_input,
            "lease_token": self.lease_token,
            "revise_count": self.revise_count,
            "phase_artifacts": self.phase_artifacts,
            "degradation_log": self.degradation_log,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ControllerState:
        return cls(
            run_id=data["run_id"],
            phase=Phase(data["phase"]),
            raw_input=data.get("raw_input", ""),
            lease_token=data.get("lease_token", ""),
            revise_count=data.get("revise_count", 0),
            phase_artifacts=data.get("phase_artifacts", {}),
            degradation_log=data.get("degradation_log", []),
        )


class FlowController:
    """Re-entrant state machine for the Doramagic pipeline.

    Usage:
        controller = FlowController(adapter, run_dir)
        # First invocation:
        result = await controller.run(user_input="帮我做记账app")
        # If clarification needed, result has phase=PHASE_A_CLARIFY
        # Second invocation:
        result = await controller.run(user_input="我要一个web版的", resume_run_id="...")
    """

    def __init__(
        self,
        adapter: PlatformAdapter,
        run_dir: Path,
        executors: dict[str, PhaseExecutor] | None = None,
        budget_policy: BudgetPolicy | None = None,
        lease_ttl: int = 300,
    ) -> None:
        self._adapter = adapter
        self._run_dir = run_dir
        self._run_dir.mkdir(parents=True, exist_ok=True)
        self._executors = executors or {}
        self._lease = LeaseManager(run_dir / "leases", default_ttl_seconds=lease_ttl)
        self._budget = BudgetManager(budget_policy)
        self._state: Optional[ControllerState] = None
        self._run_log: list[dict[str, Any]] = []

    # ─── Public API ───────────────────────────────────────────

    async def run(
        self,
        user_input: str = "",
        resume_run_id: str | None = None,
    ) -> ControllerState:
        """Execute the pipeline. Re-entrant: can resume from saved state.

        Returns the final ControllerState (check .phase for DONE/DEGRADED/ERROR/PHASE_A_CLARIFY).
        """
        # Load or create state
        if resume_run_id:
            self._state = self._load_state(resume_run_id)
            if self._state is None:
                self._state = self._create_error_state(
                    f"No saved state found for run_id={resume_run_id}"
                )
                return self._state
            # Inject new user input (for clarification responses)
            if user_input:
                self._state.raw_input = user_input
        else:
            run_id = self._generate_run_id()
            self._state = ControllerState(run_id=run_id, raw_input=user_input)

        self._budget.start()
        self._setup_directories()

        # Main loop: advance through phases until terminal or pause
        while self._state.phase not in (Phase.DONE, Phase.DEGRADED, Phase.ERROR, Phase.PHASE_A_CLARIFY):
            prev_phase = self._state.phase
            await self._step()
            # If phase didn't change, something is wrong — break to avoid infinite loop
            if self._state.phase == prev_phase:
                logger.error(f"Phase stuck at {prev_phase.value}, breaking")
                self._state.phase = Phase.ERROR
                break

        # Save final state and return
        self._save_state()
        self._write_run_log()
        return self._state

    # ─── Step dispatcher ──────────────────────────────────────

    async def _step(self) -> None:
        """Execute one phase transition."""
        phase = self._state.phase
        self._log_event("step_start", {"phase": phase.value})

        await self._adapter.send_progress(ProgressUpdate(
            phase=phase.value,
            status="started",
            message=f"Starting {phase.value}...",
            elapsed_ms=self._budget.elapsed_ms(),
            percent_complete=self._phase_progress_pct(phase),
        ))

        if phase == Phase.INIT:
            await self._handle_init()
        elif phase == Phase.PHASE_A:
            await self._handle_phase_a()
        elif phase == Phase.PHASE_G_REVISE:
            self._handle_revise()
        elif phase in (Phase.DONE, Phase.DEGRADED, Phase.ERROR, Phase.PHASE_A_CLARIFY):
            pass  # terminal or pause states
        else:
            # Dispatch to executor
            await self._dispatch_executor(phase)

        # Progress update after phase completes
        if self._state.phase != phase:  # phase changed
            await self._adapter.send_progress(ProgressUpdate(
                phase=phase.value,
                status="completed",
                message=f"Completed {phase.value}",
                elapsed_ms=self._budget.elapsed_ms(),
                percent_complete=self._phase_progress_pct(self._state.phase),
            ))

    # ─── Phase handlers ───────────────────────────────────────

    async def _handle_init(self) -> None:
        """INIT → PHASE_A: Validate input and issue first lease."""
        if not self._state.raw_input or not self._state.raw_input.strip():
            self._state.phase = Phase.ERROR
            self._state.degradation_log.append("Empty input")
            return
        token = self._lease.issue("PHASE_A", ttl_seconds=600)
        self._state.lease_token = token
        self._transition(Phase.PHASE_A)

    async def _handle_phase_a(self) -> None:
        """PHASE_A: Build NeedProfile via executor. May pause for clarification."""
        executor = self._executors.get("NeedProfileBuilder")
        if executor is None:
            # No executor registered — build minimal NeedProfile from raw input
            from doramagic_contracts.base import NeedProfile
            fallback = NeedProfile(
                raw_input=self._state.raw_input,
                keywords=[self._state.raw_input[:20]],
                intent=self._state.raw_input,
                search_directions=[],
                constraints=["openclaw_compatible"],
            )
            self._state.phase_artifacts["need_profile"] = fallback.model_dump()
            self._state.degradation_log.append("NeedProfileBuilder not available, using raw input")
            self._transition(Phase.PHASE_B)
            return

        # Run executor — result stored via _store_result in _run_executor
        result = await self._run_executor("NeedProfileBuilder", executor)
        if result is None:
            return  # error already handled

        if result.status == "ok":
            self._transition(Phase.PHASE_B)
        elif result.status == "degraded":
            # Check if executor signals need for clarification
            clarification_msg = ""
            if result.warnings:
                clarification_msg = result.warnings[0].message
            if clarification_msg and clarification_msg.startswith("CLARIFY:"):
                # Pause for user clarification — output question via adapter
                from doramagic_contracts.adapter import ClarificationRequest
                try:
                    await self._adapter.ask_clarification(
                        ClarificationRequest(
                            question=clarification_msg.replace("CLARIFY:", "").strip(),
                            round_number=1,
                        )
                    )
                except Exception:
                    pass  # OpenClaw adapter prints and returns empty
                self._state.phase = Phase.PHASE_A_CLARIFY
                self._save_state()
                return
            # Other degradation — proceed with best guess
            self._state.degradation_log.append("Phase A degraded, proceeding with best guess")
            self._transition(Phase.PHASE_B)
        else:
            self._transition(Phase.ERROR)

    def _handle_revise(self) -> None:
        """PHASE_G_REVISE: Route back to Phase F if under max loops."""
        self._state.revise_count += 1
        if self._state.revise_count >= MAX_REVISE_LOOPS:
            self._state.phase = Phase.ERROR
            self._state.degradation_log.append(
                f"Quality gate REVISE exceeded max loops ({MAX_REVISE_LOOPS})"
            )
        else:
            self._transition(Phase.PHASE_F)

    # ─── Executor dispatch ────────────────────────────────────

    async def _dispatch_executor(self, phase: Phase) -> None:
        """Generic executor dispatch for phases B, CD, E, F, G, H."""
        executor_name = PHASE_EXECUTOR_MAP.get(phase)
        if not executor_name:
            logger.error(f"No executor mapped for phase {phase.value}")
            self._state.phase = Phase.ERROR
            return

        executor = self._executors.get(executor_name)
        if executor is None:
            if phase in (Phase.PHASE_CD,):
                # Critical phase — cannot skip
                self._state.phase = Phase.ERROR
                self._state.degradation_log.append(f"{executor_name} not registered")
                return
            # Non-critical — degrade
            self._state.degradation_log.append(f"{executor_name} not available, skipping")
            next_phases = [p for p in self._next_normal_phase(phase) if p not in (Phase.DEGRADED, Phase.ERROR)]
            if next_phases:
                self._transition(next_phases[0])
            else:
                self._state.phase = Phase.DEGRADED
            return

        result = await self._run_executor(executor_name, executor)
        if result is None:
            return  # error handled in _run_executor

        # Determine next phase based on result
        if result.status == "ok":
            self._advance_from(phase)
        elif result.status == "degraded":
            self._state.degradation_log.append(f"{executor_name} returned degraded")
            if phase == Phase.PHASE_G:
                # REVISE
                self._transition(Phase.PHASE_G_REVISE)
            else:
                self._advance_from(phase)  # continue with degraded data
        elif result.status == "blocked":
            if phase == Phase.PHASE_G:
                self._state.phase = Phase.ERROR
                self._state.degradation_log.append("Quality gate BLOCKED")
            else:
                self._state.phase = Phase.DEGRADED
                self._state.degradation_log.append(f"{executor_name} blocked")
        else:
            self._state.phase = Phase.ERROR
            self._state.degradation_log.append(
                f"{executor_name} error: {result.error_code or 'unknown'}"
            )

    async def _run_executor(
        self, name: str, executor: PhaseExecutor
    ) -> Optional[ModuleResultEnvelope]:
        """Run an executor with budget checking and lease management."""
        # Check budget before running
        if self._budget.is_exceeded():
            self._state.phase = Phase.DEGRADED
            self._state.degradation_log.append("Budget exceeded before running " + name)
            return None

        # Renew lease for this phase
        if self._state.lease_token:
            self._lease.renew(self._state.lease_token, ttl_seconds=600)

        config = ExecutorConfig(
            run_dir=self._run_dir,
            budget_remaining=self._budget.snapshot(),
            concurrency_limit=self._adapter.get_concurrency_limit(),
            platform_rules=self._adapter.get_platform_rules(),
        )

        # Build input from phase artifacts
        input_data = self._build_executor_input(name)

        start_time = time.monotonic()
        try:
            result = await executor.execute(input_data, None, config)  # adapter injected later
        except Exception as e:
            logger.exception(f"Executor {name} raised: {e}")
            elapsed = int((time.monotonic() - start_time) * 1000)
            result = ModuleResultEnvelope(
                module_name=name,
                status="error",
                error_code="E_TIMEOUT",
                warnings=[WarningItem(code="EXCEPTION", message=str(e))],
                metrics=RunMetrics(
                    wall_time_ms=elapsed, llm_calls=0,
                    prompt_tokens=0, completion_tokens=0,
                    estimated_cost_usd=0.0,
                ),
            )

        # Record metrics
        self._budget.record_phase(self._state.phase.value, result.metrics)
        self._log_event("executor_done", {
            "executor": name,
            "status": result.status,
            "cost": result.metrics.estimated_cost_usd,
            "tokens": result.metrics.prompt_tokens + result.metrics.completion_tokens,
            "wall_time_ms": result.metrics.wall_time_ms,
        })

        # Store result data for downstream phases
        self._store_result(name, result)

        # Issue new lease for next phase
        token = self._lease.issue(f"after_{name}", ttl_seconds=600)
        self._state.lease_token = token

        return result

    # ─── State management ─────────────────────────────────────

    def _transition(self, target: Phase) -> None:
        """Validate and execute a state transition."""
        current = self._state.phase
        allowed = TRANSITIONS.get(current, set())
        if target not in allowed:
            logger.error(f"Invalid transition: {current.value} → {target.value}")
            self._state.phase = Phase.ERROR
            self._state.degradation_log.append(
                f"Invalid transition: {current.value} → {target.value}"
            )
            return
        self._log_event("transition", {"from": current.value, "to": target.value})
        self._state.phase = target

    def _advance_from(self, phase: Phase) -> None:
        """Advance to the normal next phase (happy path)."""
        normal_next = self._next_normal_phase(phase)
        for candidate in normal_next:
            if candidate not in (Phase.DEGRADED, Phase.ERROR):
                self._transition(candidate)
                return
        self._state.phase = Phase.ERROR

    def _next_normal_phase(self, phase: Phase) -> list[Phase]:
        """Return the ordered list of normal (non-error) next phases."""
        phase_order = [
            Phase.PHASE_A, Phase.PHASE_B, Phase.PHASE_CD,
            Phase.PHASE_E, Phase.PHASE_F, Phase.PHASE_G,
            Phase.PHASE_H, Phase.DONE,
        ]
        try:
            idx = phase_order.index(phase)
            if idx + 1 < len(phase_order):
                return [phase_order[idx + 1]]
        except ValueError:
            pass
        return []

    def _save_state(self) -> None:
        """Persist controller state to disk."""
        state_file = self._run_dir / "controller_state.json"
        state_file.write_text(
            json.dumps(self._state.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _load_state(self, run_id: str) -> Optional[ControllerState]:
        """Load controller state from disk."""
        state_file = self._run_dir / "controller_state.json"
        if not state_file.exists():
            return None
        try:
            data = json.loads(state_file.read_text(encoding="utf-8"))
            return ControllerState.from_dict(data)
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to load state: {e}")
            return None

    # ─── Directory setup ──────────────────────────────────────

    def _setup_directories(self) -> None:
        """Create staging and delivery directories."""
        (self._run_dir / "staging").mkdir(parents=True, exist_ok=True)
        (self._run_dir / "delivery").mkdir(parents=True, exist_ok=True)
        (self._run_dir / "leases").mkdir(parents=True, exist_ok=True)

    # ─── Helpers ──────────────────────────────────────────────

    def _generate_run_id(self) -> str:
        return f"run-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    def _create_error_state(self, message: str) -> ControllerState:
        state = ControllerState(run_id="error", phase=Phase.ERROR)
        state.degradation_log.append(message)
        return state

    def _store_result(self, executor_name: str, result: ModuleResultEnvelope) -> None:
        """Store executor result data under canonical keys for downstream phases.

        Data flow:
            NeedProfileBuilder → "need_profile" (NeedProfile)
            DiscoveryRunner    → "discovery_result" (DiscoveryResult)
            SoulExtractorBatch → "extraction_results" (dict)
            CommunityHarvester → "community_knowledge" (CommunityKnowledge)
            SynthesisRunner    → "synthesis_report" (SynthesisReportData)
            SkillCompiler      → "compiler_output" (SkillCompilerOutput)
            Validator          → "validation_report" (ValidationReport)
            DeliveryPackager   → "delivery_manifest" (dict)
        """
        key_map = {
            "NeedProfileBuilder": "need_profile",
            "DiscoveryRunner": "discovery_result",
            "SoulExtractorBatch": "extraction_results",
            "CommunityHarvester": "community_knowledge",
            "SynthesisRunner": "synthesis_report",
            "SkillCompiler": "compiler_output",
            "Validator": "validation_report",
            "DeliveryPackager": "delivery_manifest",
        }
        key = key_map.get(executor_name, executor_name)

        # Store the actual data (serializable for state persistence)
        if result.data is not None:
            if hasattr(result.data, "model_dump"):
                self._state.phase_artifacts[key] = result.data.model_dump()
            elif isinstance(result.data, dict):
                self._state.phase_artifacts[key] = result.data
            else:
                self._state.phase_artifacts[key] = str(result.data)
        else:
            self._state.phase_artifacts[key] = None

        # Also store status metadata
        self._state.phase_artifacts[f"_{executor_name}_status"] = result.status

    def _build_executor_input(self, executor_name: str) -> Any:
        """Build typed input for an executor from accumulated phase artifacts.

        Each executor gets specifically typed input constructed from
        the outputs of previous phases.
        """
        arts = self._state.phase_artifacts

        if executor_name == "NeedProfileBuilder":
            # Phase A: wrap raw_input in a simple object
            from pydantic import BaseModel

            class RawInput(BaseModel):
                raw_input: str

            return RawInput(raw_input=self._state.raw_input)

        elif executor_name == "DiscoveryRunner":
            from doramagic_contracts.cross_project import DiscoveryConfig, DiscoveryInput
            from doramagic_contracts.base import NeedProfile

            need_profile_data = arts.get("need_profile")
            if not need_profile_data:
                raise ValueError("NeedProfile not available for DiscoveryRunner")

            need_profile = NeedProfile(**need_profile_data) if isinstance(need_profile_data, dict) else need_profile_data
            return DiscoveryInput(
                need_profile=need_profile,
                config=DiscoveryConfig(),
            )

        elif executor_name == "SoulExtractorBatch":
            # Phase CD: needs repo list from discovery result
            from pydantic import BaseModel

            discovery = arts.get("discovery_result", {})
            candidates = discovery.get("candidates", []) if isinstance(discovery, dict) else []

            # Build repo list from selected candidates
            repos = []
            for c in candidates:
                if isinstance(c, dict) and c.get("selected_for_phase_c", False):
                    repos.append({
                        "repo_id": c.get("candidate_id", c.get("name", "unknown")),
                        "url": c.get("url", ""),
                        "local_path": "",  # Will be cloned by extractor
                    })
            # If no candidates explicitly selected, take top 3
            if not repos:
                for c in candidates[:3]:
                    if isinstance(c, dict):
                        repos.append({
                            "repo_id": c.get("candidate_id", c.get("name", "unknown")),
                            "url": c.get("url", ""),
                            "local_path": "",
                        })

            class RepoListInput(BaseModel):
                repos: list[dict] = []

            return RepoListInput(repos=repos)

        elif executor_name == "SynthesisRunner":
            from doramagic_contracts.cross_project import (
                CompareMetrics,
                CompareOutput,
                CommunityKnowledge,
                DiscoveryResult,
                SynthesisInput,
            )
            from doramagic_contracts.base import NeedProfile

            need_profile_data = arts.get("need_profile", {})
            need_profile = NeedProfile(**need_profile_data) if isinstance(need_profile_data, dict) else need_profile_data
            discovery_data = arts.get("discovery_result", {})
            extraction = arts.get("extraction_results", {})
            community = arts.get("community_knowledge")

            # Rebuild DiscoveryResult from stored dict
            if isinstance(discovery_data, dict):
                discovery_obj = DiscoveryResult(**discovery_data)
            else:
                discovery_obj = discovery_data or DiscoveryResult(candidates=[], search_coverage=[])

            # Build minimal CompareOutput from extraction results
            successful = list(extraction.get("successful_repos", [])) if isinstance(extraction, dict) else []
            compare_output = CompareOutput(
                domain_id="auto",
                compared_projects=successful,
                signals=[],
                metrics=CompareMetrics(
                    project_count=max(1, len(successful)),
                    atom_count=0,
                    aligned_count=0,
                    missing_count=0,
                    original_count=0,
                    drifted_count=0,
                ),
            )

            # Build CommunityKnowledge
            if isinstance(community, dict):
                community_obj = CommunityKnowledge(**community)
            elif community is not None:
                community_obj = community
            else:
                community_obj = CommunityKnowledge(skills=[], tutorials=[], use_cases=[])

            # Build project summaries from extraction results
            from doramagic_contracts.cross_project import ExtractedProjectSummary
            summaries_raw = extraction.get("project_summaries", []) if isinstance(extraction, dict) else []
            project_summaries = []
            for s in summaries_raw:
                try:
                    project_summaries.append(ExtractedProjectSummary(**s) if isinstance(s, dict) else s)
                except Exception:
                    pass

            return SynthesisInput(
                need_profile=need_profile,
                discovery_result=discovery_obj,
                project_summaries=project_summaries,
                comparison_result=compare_output,
                community_knowledge=community_obj,
            )

        elif executor_name == "SkillCompiler":
            from doramagic_contracts.skill import SkillCompilerInput
            from doramagic_contracts.base import NeedProfile

            need_profile_data = arts.get("need_profile", {})
            need_profile = NeedProfile(**need_profile_data) if isinstance(need_profile_data, dict) else need_profile_data
            synthesis = arts.get("synthesis_report", {})

            return SkillCompilerInput(
                need_profile=need_profile,
                synthesis_report=synthesis,
                platform_rules=self._adapter.get_platform_rules(),
            )

        elif executor_name == "Validator":
            from doramagic_contracts.skill import SkillBundlePaths, ValidationInput
            from doramagic_contracts.base import NeedProfile

            need_profile_data = arts.get("need_profile", {})
            need_profile = NeedProfile(**need_profile_data) if isinstance(need_profile_data, dict) else need_profile_data
            synthesis = arts.get("synthesis_report", {})
            compiler = arts.get("compiler_output", {})

            # Get paths from compiler output
            skill_md = compiler.get("skill_md_path", "") if isinstance(compiler, dict) else ""
            provenance_md = compiler.get("provenance_md_path", "") if isinstance(compiler, dict) else ""
            limitations_md = compiler.get("limitations_md_path", "") if isinstance(compiler, dict) else ""
            readme_md = compiler.get("readme_md_path", "") if isinstance(compiler, dict) else ""

            return ValidationInput(
                need_profile=need_profile,
                synthesis_report=synthesis,
                skill_bundle=SkillBundlePaths(
                    skill_md_path=skill_md,
                    provenance_md_path=provenance_md,
                    limitations_md_path=limitations_md,
                    readme_md_path=readme_md,
                ),
                platform_rules=self._adapter.get_platform_rules(),
            )

        elif executor_name == "DeliveryPackager":
            # DeliveryPackager reads from staging/ — no typed input needed
            from pydantic import BaseModel

            class EmptyInput(BaseModel):
                pass

            return EmptyInput()

        # Fallback
        return self._state.phase_artifacts

    def _phase_progress_pct(self, phase: Phase) -> int:
        """Estimate progress percentage based on current phase."""
        pct_map = {
            Phase.INIT: 0, Phase.PHASE_A: 5, Phase.PHASE_A_CLARIFY: 5,
            Phase.PHASE_B: 10, Phase.PHASE_CD: 20, Phase.PHASE_E: 70,
            Phase.PHASE_F: 80, Phase.PHASE_G: 85, Phase.PHASE_G_REVISE: 85,
            Phase.PHASE_H: 95, Phase.DONE: 100, Phase.DEGRADED: 100, Phase.ERROR: 100,
        }
        return pct_map.get(phase, 0)

    # ─── Logging ──────────────────────────────────────────────

    def _log_event(self, event_type: str, data: dict[str, Any]) -> None:
        entry = {
            "ts": datetime.now().isoformat(),
            "event": event_type,
            "phase": self._state.phase.value if self._state else "unknown",
            **data,
        }
        self._run_log.append(entry)
        logger.info(f"[{event_type}] {data}")

    def _write_run_log(self) -> None:
        """Write run log to JSONL file."""
        log_file = self._run_dir / "run_log.jsonl"
        with open(log_file, "a", encoding="utf-8") as f:
            for entry in self._run_log:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        self._run_log.clear()
