"""ControllerState — 可序列化的控制器状态，支持断点续跑。"""

from __future__ import annotations

from typing import Any

from doramagic_contracts.base import RoutingDecision

from .state_definitions import Phase


class ControllerState:
    """Serializable controller state for re-entrant execution."""

    def __init__(
        self,
        run_id: str,
        phase: Phase = Phase.INIT,
        raw_input: str = "",
        lease_token: str = "",
        revise_count: int = 0,
        clarification_round: int = 0,
        degraded_mode: bool = False,
        delivery_tier: str = "full_skill",
        phase_artifacts: dict[str, Any] | None = None,
        degradation_log: list[str] | None = None,
    ) -> None:
        self.run_id = run_id
        self.phase = phase
        self.raw_input = raw_input
        self.lease_token = lease_token
        self.revise_count = revise_count
        self.clarification_round = clarification_round
        self.degraded_mode = degraded_mode
        self.delivery_tier = delivery_tier
        self.phase_artifacts: dict[str, Any] = phase_artifacts or {}
        self.degradation_log: list[str] = degradation_log or []

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "phase": self.phase.value,
            "raw_input": self.raw_input,
            "lease_token": self.lease_token,
            "revise_count": self.revise_count,
            "clarification_round": self.clarification_round,
            "degraded_mode": self.degraded_mode,
            "delivery_tier": self.delivery_tier,
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
            clarification_round=data.get("clarification_round", 0),
            degraded_mode=data.get("degraded_mode", False),
            delivery_tier=data.get("delivery_tier", "full_skill"),
            phase_artifacts=data.get("phase_artifacts", {}),
            degradation_log=data.get("degradation_log", []),
        )

    @property
    def routing(self) -> RoutingDecision | None:
        raw = self.phase_artifacts.get("routing_decision")
        if isinstance(raw, RoutingDecision):
            return raw
        if isinstance(raw, dict):
            try:
                return RoutingDecision(**raw)
            except Exception:
                return None
        return None

    @property
    def candidate_count(self) -> int:
        discovery = self.phase_artifacts.get("discovery_result", {})
        if isinstance(discovery, dict):
            return int(discovery.get("candidate_count") or len(discovery.get("candidates", [])))
        return 0

    @property
    def successful_extractions(self) -> int:
        extraction = self.phase_artifacts.get("extraction_aggregate", {})
        if isinstance(extraction, dict):
            return int(extraction.get("success_count", 0))
        return 0

    @property
    def synthesis_ok(self) -> bool:
        synthesis = self.phase_artifacts.get("synthesis_bundle", {})
        if isinstance(synthesis, dict):
            return bool(
                synthesis.get("selected_knowledge")
                or synthesis.get("consensus")
                or synthesis.get("global_theses")
            )
        return False

    @property
    def compile_ready(self) -> bool:
        synthesis = self.phase_artifacts.get("synthesis_bundle", {})
        if isinstance(synthesis, dict):
            return bool(synthesis.get("compile_ready", False))
        return False

    @property
    def compile_ok(self) -> bool:
        compile_bundle = self.phase_artifacts.get("compile_bundle", {})
        if isinstance(compile_bundle, dict):
            return bool(compile_bundle.get("full_draft")) or bool(
                compile_bundle.get("artifact_paths", {}).get("SKILL.md")
            )
        return False

    @property
    def quality_score(self) -> float:
        validation = self.phase_artifacts.get("validation_report", {})
        if isinstance(validation, dict):
            return float(validation.get("overall_score", 0.0))
        return 0.0

    @property
    def blockers(self) -> bool:
        validation = self.phase_artifacts.get("validation_report", {})
        if not isinstance(validation, dict):
            return False
        if validation.get("status") == "BLOCKED":
            return True
        for check in validation.get("checks", []):
            if (
                isinstance(check, dict)
                and not check.get("passed", True)
                and check.get("severity") == "blocking"
            ):
                return True
        return False

    @property
    def weakest_section(self) -> str | None:
        validation = self.phase_artifacts.get("validation_report", {})
        if isinstance(validation, dict):
            return validation.get("weakest_section")
        return None

    @property
    def routing_route(self) -> str:
        routing = self.routing
        if routing is not None:
            return routing.route
        return ""

    @property
    def has_clawhub(self) -> bool:
        extraction = self.phase_artifacts.get("extraction_aggregate", {})
        if isinstance(extraction, dict):
            for env in extraction.get("repo_envelopes", []):
                if isinstance(env, dict) and "clawhub" in (env.get("repo_url", "") or "").lower():
                    return True
        return False

    @property
    def budget_exceeded(self) -> bool:
        return False
