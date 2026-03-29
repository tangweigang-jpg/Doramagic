"""Flow controller for the Doramagic v12.1.1 deterministic DAG."""

from __future__ import annotations

import contextlib
import logging
import time
from pathlib import Path
from typing import Any

from doramagic_contracts.adapter import ClarificationRequest, PlatformAdapter
from doramagic_contracts.base import NeedProfile, RoutingDecision
from doramagic_contracts.budget import BudgetPolicy
from doramagic_contracts.envelope import ModuleResultEnvelope, RunMetrics, WarningItem
from doramagic_contracts.executor import ExecutorConfig, PhaseExecutor

from .budget_manager import BudgetManager
from .event_bus import EventBus
from .flow_controller_builders import (
    build_capability_router,
    build_executor_input,
    build_llm_adapter,
    build_need_profile_contract,
)
from .flow_controller_service import (
    build_plan_preview,
    clarification_question,
    create_error_state,
    emit_event,
    infer_delivery_tier,
    load_accumulated_knowledge,
    load_state,
    log_event,
    persist_accumulated_knowledge,
    phase_complete_message,
    phase_progress_pct,
    phase_start_message,
    save_state,
    send_progress,
    setup_directories,
    store_result,
    write_run_log,
)
from .flow_controller_state import ControllerState
from .input_router import InputRouter
from .lease_manager import LeaseManager
from .state_definitions import (
    CONDITIONAL_EDGES,
    MAX_REVISE_LOOPS,
    PHASE_EXECUTOR_MAP,
    TRANSITIONS,
    Phase,
)

try:
    from doramagic_shared_utils.capability_router import reset_routing_log
except Exception:
    reset_routing_log = None  # type: ignore[assignment]

logger = logging.getLogger("doramagic.controller")


class FlowController:
    """Deterministic controller with conditional routing, fan-out and degraded delivery."""

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
        self._router = InputRouter()
        self._event_bus = EventBus(run_dir, run_id=run_dir.name)
        self._state: ControllerState | None = None
        self._run_log: list[dict[str, Any]] = []
        self._capability_router = build_capability_router()

    async def run(self, user_input: str = "", resume_run_id: str | None = None) -> ControllerState:
        if resume_run_id:
            self._state = load_state(self._run_dir)
            if self._state is None:
                self._state = create_error_state(f"No saved state found for run_id={resume_run_id}")
                return self._state
            if self._state.phase == Phase.PHASE_A_CLARIFY and user_input.strip():
                self._state.clarification_round += 1
                self._state.raw_input = f"{self._state.raw_input}\n补充说明: {user_input.strip()}"
                self._state.phase = Phase.PHASE_A
        else:
            self._state = ControllerState(run_id=self._run_dir.name, raw_input=user_input)

        self._budget.start()
        setup_directories(self._run_dir)
        if self._capability_router is not None and reset_routing_log is not None:
            with contextlib.suppress(Exception):
                reset_routing_log()

        self._emit("run_started", "run started", meta={"run_id": self._state.run_id})
        if not resume_run_id:
            await self._progress(status="started", message=build_plan_preview())

        while self._state.phase not in (
            Phase.DONE,
            Phase.DEGRADED,
            Phase.ERROR,
            Phase.PHASE_A_CLARIFY,
        ):
            current = self._state.phase
            await self._step()
            if self._state.phase == current:
                self._state.phase = Phase.ERROR
                self._state.degradation_log.append(f"Phase stuck at {current.value}")
                break

        save_state(self._state, self._run_dir)
        write_run_log(self._run_log, self._run_dir)
        if self._state.phase in (Phase.DONE, Phase.DEGRADED):
            persist_accumulated_knowledge(self._state)
            self._emit(
                "run_completed",
                "run completed",
                status=self._state.phase.value.lower(),
                meta={"delivery_tier": self._state.delivery_tier},
            )
        elif self._state.phase == Phase.ERROR:
            self._emit("run_failed", "run failed", status="error")
        return self._state

    # ------------------------------------------------------------------
    # Phase execution
    # ------------------------------------------------------------------

    async def _step(self) -> None:
        phase = self._state.phase
        self._log("phase_started", {"phase": phase.value})
        self._emit("phase_started", f"{phase.value} started", status="started")
        await self._progress(status="started", message=phase_start_message(phase))

        if phase == Phase.INIT:
            self._transition(self._evaluate_edge(Phase.INIT))
        elif phase == Phase.PHASE_A:
            await self._handle_phase_a()
        else:
            await self._dispatch_executor(phase)

        if self._state.phase != phase:
            self._emit(
                "phase_completed",
                f"{phase.value} completed",
                phase_override=phase.value,
                status="completed",
            )
            await send_progress(
                self._adapter,
                self._budget,
                phase=phase.value,
                status="completed",
                message=phase_complete_message(phase, self._state),
                percent=phase_progress_pct(self._state.phase),
            )

    async def _handle_phase_a(self) -> None:
        executor = self._executors.get("NeedProfileBuilder")
        if executor is None:
            self._state.phase = Phase.ERROR
            self._state.degradation_log.append("NeedProfileBuilder not registered")
            return

        result = await self._run_executor("NeedProfileBuilder", executor)
        if result is None or result.data is None:
            self._state.phase = Phase.ERROR
            self._state.degradation_log.append("NeedProfileBuilder returned no profile")
            return

        profile = (
            result.data if isinstance(result.data, NeedProfile) else NeedProfile(**result.data)
        )
        routing = self._router.route(profile)
        if routing.route == "LOW_CONFIDENCE" and self._state.clarification_round >= 2:
            routing = RoutingDecision(
                route="DOMAIN_EXPLORE",
                skip_discovery=False,
                max_repos=profile.max_projects,
                repo_urls=[],
                project_names=[],
                confidence=max(profile.confidence, 0.55),
                reasoning="best-guess fallback after 2 clarification rounds",
            )

        self._state.phase_artifacts["routing_decision"] = routing.model_dump()
        self._state.phase_artifacts["need_profile_contract"] = build_need_profile_contract(
            profile, routing, self._adapter
        ).model_dump()
        self._state.phase_artifacts["accumulated_knowledge"] = load_accumulated_knowledge(
            profile.domain
        )

        if routing.route == "LOW_CONFIDENCE" and self._state.clarification_round < 2:
            question = clarification_question(profile, result)
            await self._adapter.ask_clarification(
                ClarificationRequest(
                    question=question, round_number=self._state.clarification_round + 1
                )
            )
            self._emit(
                "degraded",
                "clarification requested",
                phase_override=Phase.PHASE_A_CLARIFY.value,
                status="clarify",
            )
            self._state.phase = Phase.PHASE_A_CLARIFY
            save_state(self._state, self._run_dir)
            return

        self._transition(self._evaluate_edge(Phase.PHASE_A))

    async def _dispatch_executor(self, phase: Phase) -> None:
        executor_name = PHASE_EXECUTOR_MAP.get(phase)
        if not executor_name:
            self._state.phase = Phase.ERROR
            self._state.degradation_log.append(f"No executor mapped for {phase.value}")
            return

        executor = self._executors.get(executor_name)
        if executor is None:
            if phase == Phase.PHASE_G:
                self._state.phase = Phase.ERROR
                self._state.degradation_log.append(f"{executor_name} not registered")
            else:
                tier = infer_delivery_tier(phase, self._state.delivery_tier)
                self._enter_degraded(f"{executor_name} not registered", tier)
            return

        result = await self._run_executor(executor_name, executor)
        if result is None:
            if phase == Phase.PHASE_G:
                self._state.phase = Phase.ERROR
            else:
                self._enter_degraded(
                    f"{executor_name} returned no result",
                    infer_delivery_tier(phase, self._state.delivery_tier),
                )
            return

        if result.status == "error":
            if phase == Phase.PHASE_G:
                self._state.phase = Phase.ERROR
                self._state.degradation_log.append(f"{executor_name} failed during packaging")
            else:
                self._enter_degraded(
                    f"{executor_name} failed: {result.error_code or 'unknown'}",
                    infer_delivery_tier(phase, self._state.delivery_tier),
                )
            return

        if phase == Phase.PHASE_C and result.status == "degraded":
            reason = "WorkerSupervisor partial failure; best-effort delivery enabled"
            self._state.degraded_mode = True
            self._state.degradation_log.append(reason)
            self._emit(
                "degraded",
                reason,
                status="degraded",
                meta={"delivery_tier": self._state.delivery_tier or "full_skill"},
            )

        if phase == Phase.PHASE_F:
            self._emit(
                "quality_scored",
                f"quality score={self._state.quality_score:.1f}",
                status=result.status,
                meta={
                    "overall_score": self._state.quality_score,
                    "weakest_section": self._state.weakest_section,
                    "revise_count": self._state.revise_count,
                },
            )

        next_phase = self._evaluate_edge(phase)
        if phase == Phase.PHASE_F and next_phase == Phase.PHASE_E:
            self._state.revise_count += 1
            self._emit(
                "revise_triggered",
                f"quality repair loop triggered ({self._state.revise_count}/{MAX_REVISE_LOOPS})",
                status="revise",
                meta={"weakest_section": self._state.weakest_section},
            )
        if next_phase == Phase.DEGRADED:
            self._enter_degraded(
                f"{executor_name} degraded",
                infer_delivery_tier(phase, self._state.delivery_tier),
            )
            return
        self._transition(next_phase)

    async def _run_executor(
        self, name: str, executor: PhaseExecutor
    ) -> ModuleResultEnvelope | None:
        if self._budget.is_exceeded():
            self._enter_degraded(
                f"Budget exceeded before {name}",
                infer_delivery_tier(self._state.phase, self._state.delivery_tier),
            )
            return None

        if self._state.lease_token:
            self._lease.renew(self._state.lease_token, ttl_seconds=600)

        config = ExecutorConfig(
            run_dir=self._run_dir,
            budget_remaining=self._budget.snapshot(),
            concurrency_limit=self._adapter.get_concurrency_limit(),
            platform_rules=self._adapter.get_platform_rules(),
            event_bus=self._event_bus,
        )

        input_data = build_executor_input(name, self._state, self._adapter)
        llm_adapter = build_llm_adapter(name, self._capability_router)
        started = time.monotonic()

        try:
            result = await executor.execute(input_data, llm_adapter, config)
        except Exception as exc:
            logger.exception("Executor %s raised", name)
            result = ModuleResultEnvelope(
                module_name=name,
                status="error",
                error_code="E_EXECUTOR_EXCEPTION",
                warnings=[WarningItem(code="EXCEPTION", message=str(exc))],
                data=None,
                metrics=RunMetrics(
                    wall_time_ms=int((time.monotonic() - started) * 1000),
                    llm_calls=0,
                    prompt_tokens=0,
                    completion_tokens=0,
                    estimated_cost_usd=0.0,
                ),
            )

        self._budget.record_phase(self._state.phase.value, result.metrics)
        store_result(self._state, name, result)
        self._log(
            "executor_done",
            {
                "executor": name,
                "status": result.status,
                "wall_time_ms": result.metrics.wall_time_ms,
            },
        )
        return result

    # ------------------------------------------------------------------
    # State machine
    # ------------------------------------------------------------------

    def _evaluate_edge(self, phase: Phase) -> Phase:
        for predicate, target in CONDITIONAL_EDGES.get(phase, []):
            if predicate(self._state):
                return target
        return Phase.ERROR

    def _transition(self, target: Phase) -> None:
        current = self._state.phase
        allowed = TRANSITIONS.get(current, set())
        if target not in allowed:
            self._state.phase = Phase.ERROR
            self._state.degradation_log.append(
                f"Invalid transition: {current.value} -> {target.value}"
            )
            return
        self._log("transition", {"from": current.value, "to": target.value})
        self._state.phase = target

    def _enter_degraded(self, reason: str, delivery_tier: str) -> None:
        self._state.degraded_mode = True
        self._state.delivery_tier = delivery_tier
        self._state.degradation_log.append(reason)
        self._emit("degraded", reason, status="degraded", meta={"delivery_tier": delivery_tier})

        if self._state.phase != Phase.PHASE_G:
            self._state.phase = Phase.PHASE_G
        else:
            if Phase.DEGRADED in TRANSITIONS.get(self._state.phase, set()):
                self._transition(Phase.DEGRADED)
            else:
                self._state.phase = Phase.DEGRADED

    # ------------------------------------------------------------------
    # Convenience wrappers (reduce boilerplate in phase methods)
    # ------------------------------------------------------------------

    def _emit(
        self,
        event_type: str,
        message: str,
        *,
        phase_override: str | None = None,
        status: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> None:
        emit_event(
            self._event_bus,
            event_type,
            message,
            phase=phase_override or self._state.phase.value,
            status=status,
            meta=meta,
        )

    async def _progress(self, *, status: str, message: str) -> None:
        await send_progress(
            self._adapter,
            self._budget,
            phase=self._state.phase.value,
            status=status,
            message=message,
            percent=phase_progress_pct(self._state.phase),
        )

    def _log(self, event_type: str, data: dict[str, Any]) -> None:
        log_event(self._run_log, event_type, data, self._state.phase)
