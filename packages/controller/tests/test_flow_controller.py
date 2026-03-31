"""Unit tests for FlowController.

All external platform and executor dependencies are mocked.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from doramagic_contracts.base import (
    CandidateQualitySignals,
    DiscoveryCandidate,
    ExtractionAggregateContract,
    NeedProfile,
    RepoExtractionEnvelope,
    RoutingDecision,
    SearchDirection,
)
from doramagic_contracts.cross_project import (
    DiscoveryResult,
    SynthesisDecision,
    SynthesisReportData,
)
from doramagic_contracts.envelope import ModuleResultEnvelope, RunMetrics
from doramagic_contracts.skill import (
    CompileBundleContract,
    DeliveryManifest,
    PlatformRules,
    ValidationCheck,
    ValidationReport,
)
from doramagic_controller.flow_controller import FlowController
from doramagic_controller.flow_controller_state import ControllerState
from doramagic_controller.state_definitions import Phase

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _metrics() -> RunMetrics:
    return RunMetrics(
        wall_time_ms=1,
        llm_calls=0,
        prompt_tokens=0,
        completion_tokens=0,
        estimated_cost_usd=0.0,
    )


def _envelope(module_name: str, data, status: str = "ok") -> ModuleResultEnvelope:
    return ModuleResultEnvelope(
        module_name=module_name,
        status=status,
        data=data,
        metrics=_metrics(),
    )


def _make_adapter() -> MagicMock:
    adapter = MagicMock()
    adapter.send_progress = AsyncMock(return_value=None)
    adapter.ask_clarification = AsyncMock(return_value="clarified")
    adapter.send_output = AsyncMock(return_value=None)
    adapter.receive_input = AsyncMock(return_value="")
    adapter.get_platform_rules.return_value = PlatformRules()
    adapter.get_concurrency_limit.return_value = 3
    adapter.get_storage_root.return_value = Path("/tmp")
    return adapter


def _make_controller(
    tmp_path: Path,
    *,
    executors: dict[str, MagicMock] | None = None,
) -> FlowController:
    run_dir = tmp_path / "run-001"
    adapter = _make_adapter()
    with patch("doramagic_controller.flow_controller.build_capability_router", return_value=None):
        controller = FlowController(
            adapter=adapter,
            run_dir=run_dir,
            executors=executors or {},
        )
    return controller


def _make_executor(result) -> MagicMock:
    executor = MagicMock()

    async def _execute(input_data, llm_adapter, config):
        assert config.run_dir.name == "run-001"
        assert llm_adapter is None
        return result

    executor.execute = AsyncMock(side_effect=_execute)
    executor.validate_input = MagicMock(return_value=[])
    executor.can_degrade = MagicMock(return_value=True)
    return executor


def _make_need_profile() -> NeedProfile:
    return NeedProfile(
        raw_input="Study alpha tooling patterns",
        keywords=["alpha", "tooling"],
        intent="extract knowledge",
        search_directions=[SearchDirection(direction="repo search", priority="high")],
        constraints=[],
        confidence=0.95,
        domain="controller",
        max_projects=1,
    )


def _make_domain_explore_profile() -> NeedProfile:
    return NeedProfile(
        raw_input="Build a knowledge system for this domain",
        keywords=[],
        intent="stitch bricks directly",
        search_directions=[],
        constraints=[],
        confidence=0.95,
        domain="knowledge_ops",
        max_projects=1,
    )


def _make_discovery_result() -> DiscoveryResult:
    candidate = DiscoveryCandidate(
        candidate_id="c-1",
        name="alpha-toolkit",
        url="https://github.com/example/alpha-toolkit",
        type="github_repo",
        relevance="high",
        contribution="reference implementation",
        quick_score=9.2,
        quality_signals=CandidateQualitySignals(
            stars=100,
            forks=10,
            has_readme=True,
        ),
    )
    return DiscoveryResult(
        candidates=[candidate],
        search_coverage=[],
        candidate_count=1,
    )


def _make_extraction_result() -> dict:
    envelope = RepoExtractionEnvelope(
        worker_id="worker-1",
        repo_name="alpha-toolkit",
        repo_url="https://github.com/example/alpha-toolkit",
        repo_type="TOOL",
        status="ok",
        metrics=_metrics(),
        repo_facts={
            "repo": {
                "repo_id": "alpha-toolkit",
                "full_name": "example/alpha-toolkit",
                "url": "https://github.com/example/alpha-toolkit",
                "default_branch": "main",
                "commit_sha": "abc123",
                "local_path": "/tmp/alpha-toolkit",
            }
        },
        feature_inventory=["feature-a"],
        anti_patterns=["trap-a"],
    )
    aggregate = ExtractionAggregateContract(
        repo_envelopes=[envelope],
        success_count=1,
        failed_count=0,
        ready_for_synthesis=True,
    )
    return aggregate.model_dump()


def _make_synthesis_result() -> SynthesisReportData:
    decision = SynthesisDecision(
        decision_id="d-1",
        statement="Use the controller pattern.",
        decision="include",
        rationale="Strong evidence",
        source_refs=["worker-1"],
        demand_fit="high",
    )
    return SynthesisReportData(
        consensus=[decision],
        conflicts=[],
        unique_knowledge=[],
        selected_knowledge=[],
        excluded_knowledge=[],
        open_questions=[],
        compile_ready=True,
        global_theses=["controller pattern"],
    )


def _make_compile_result() -> CompileBundleContract:
    return CompileBundleContract(
        section_drafts={"intro": "draft"},
        full_draft="full draft",
        artifact_paths={"SKILL.md": "artifacts/skill.md"},
    )


def _make_validation_result() -> ValidationReport:
    return ValidationReport(
        status="PASS",
        checks=[
            ValidationCheck(
                name="Completeness",
                passed=True,
                severity="warning",
                details=[],
            )
        ],
        overall_score=92.0,
        weakest_section="",
        repair_plan=[],
    )


def _make_delivery_result() -> DeliveryManifest:
    return DeliveryManifest(
        delivery_tier="full_skill",
        artifact_paths={"SKILL.md": "artifacts/skill.md"},
        run_summary={"status": "done"},
        user_message="Delivered",
    )


# ---------------------------------------------------------------------------
# ControllerState tests
# ---------------------------------------------------------------------------


def test_controller_state_round_trip(tmp_path: Path) -> None:
    routing = RoutingDecision(
        route="NAMED_PROJECT",
        skip_discovery=False,
        max_repos=2,
        project_names=["alpha"],
        confidence=0.9,
        reasoning="named project",
    )
    state = ControllerState(
        run_id="run-123",
        phase=Phase.PHASE_D,
        raw_input="alpha",
        lease_token="lease-1",
        revise_count=1,
        clarification_round=2,
        degraded_mode=True,
        delivery_tier="repo_reports",
        phase_artifacts={
            "routing_decision": routing.model_dump(),
            "discovery_result": {"candidate_count": 3, "candidates": []},
            "synthesis_bundle": {"consensus": [{}], "compile_ready": True},
        },
        degradation_log=["first reason"],
    )

    restored = ControllerState.from_dict(state.to_dict())

    assert restored.to_dict() == state.to_dict()
    assert restored.phase == Phase.PHASE_D
    assert restored.routing is not None
    assert restored.routing.route == "NAMED_PROJECT"


def test_controller_state_properties() -> None:
    state = ControllerState(
        run_id="run-123",
        phase=Phase.PHASE_B,
        raw_input="alpha",
        phase_artifacts={
            "routing_decision": {
                "route": "NAMED_PROJECT",
                "skip_discovery": False,
                "max_repos": 2,
                "project_names": ["alpha"],
                "confidence": 0.9,
                "reasoning": "named project",
            },
            "discovery_result": {"candidate_count": 2, "candidates": []},
            "synthesis_bundle": {"consensus": [{}], "compile_ready": True},
            "compile_bundle": {
                "full_draft": "",
                "artifact_paths": {"SKILL.md": "artifacts/skill.md"},
            },
            "validation_report": {
                "overall_score": 87.5,
                "status": "PASS",
                "checks": [{"passed": False, "severity": "blocking", "name": "Completeness"}],
            },
        },
    )

    assert state.routing is not None
    assert state.routing.route == "NAMED_PROJECT"
    assert state.candidate_count == 2
    assert state.synthesis_ok is True
    assert state.compile_ok is True
    assert state.quality_score == 87.5
    assert state.blockers is True


# ---------------------------------------------------------------------------
# FlowController tests
# ---------------------------------------------------------------------------


def test_flow_controller_initialization_creates_directories_and_components(tmp_path: Path) -> None:
    controller = _make_controller(tmp_path)
    run_dir = tmp_path / "run-001"

    assert run_dir.exists()
    assert (run_dir / "leases").exists()
    assert controller._adapter is not None
    assert controller._router.__class__.__name__ == "InputRouter"
    assert controller._budget is not None
    assert controller._lease is not None
    assert controller._event_bus.path == run_dir / "run_events.jsonl"
    assert controller._state is None
    assert controller._run_log == []
    assert controller._executors == {}


@pytest.mark.parametrize(
    "phase,state_factory,expected",
    [
        (
            Phase.INIT,
            lambda: ControllerState(
                run_id="run-1",
                phase=Phase.INIT,
                raw_input="study alpha",
            ),
            Phase.PHASE_A,
        ),
        (
            Phase.PHASE_A,
            lambda: ControllerState(
                run_id="run-1",
                phase=Phase.PHASE_A,
                phase_artifacts={
                    "routing_decision": {"route": "DIRECT_URL", "max_repos": 1},
                },
            ),
            Phase.PHASE_C,
        ),
        (
            Phase.PHASE_A,
            lambda: ControllerState(
                run_id="run-1",
                phase=Phase.PHASE_A,
                phase_artifacts={
                    "routing_decision": {"route": "LOW_CONFIDENCE", "max_repos": 1},
                },
            ),
            Phase.PHASE_A_CLARIFY,
        ),
        (
            Phase.PHASE_B,
            lambda: ControllerState(
                run_id="run-1",
                phase=Phase.PHASE_B,
                phase_artifacts={"discovery_result": {"candidate_count": 2, "candidates": []}},
            ),
            Phase.PHASE_C,
        ),
        (
            Phase.PHASE_F,
            lambda: ControllerState(
                run_id="run-1",
                phase=Phase.PHASE_F,
                phase_artifacts={
                    "validation_report": {
                        "overall_score": 92.0,
                        "status": "PASS",
                        "checks": [],
                    }
                },
            ),
            Phase.PHASE_G,
        ),
    ],
)
def test_evaluate_edge_returns_expected_phase(
    phase: Phase, state_factory, expected: Phase, tmp_path: Path
) -> None:
    controller = _make_controller(tmp_path)
    controller._state = state_factory()

    assert controller._evaluate_edge(phase) == expected


def test_evaluate_edge_routes_domain_explore_to_brick_stitch(tmp_path: Path) -> None:
    controller = _make_controller(tmp_path)
    controller._state = ControllerState(
        run_id="run-1",
        phase=Phase.PHASE_A,
        raw_input="Build a knowledge system for this domain",
        phase_artifacts={
            "routing_decision": {
                "route": "DOMAIN_EXPLORE",
                "skip_discovery": False,
                "max_repos": 1,
                "repo_urls": [],
                "project_names": [],
                "confidence": 0.95,
                "reasoning": "domain",
            },
            "brick_coverage": {
                "matched_categories": ["a", "b", "c"],
                "match_count": 3,
                "total_bricks": 30,
                "eligible": True,
            },
        },
    )

    assert controller._evaluate_edge(Phase.PHASE_A) == Phase.BRICK_STITCH


def test_transition_handles_legal_and_illegal_moves(tmp_path: Path) -> None:
    controller = _make_controller(tmp_path)
    controller._state = ControllerState(run_id="run-1", phase=Phase.INIT)

    controller._transition(Phase.PHASE_A)
    assert controller._state.phase == Phase.PHASE_A

    controller._transition(Phase.PHASE_G)
    assert controller._state.phase == Phase.ERROR
    assert controller._state.degradation_log[-1] == "Invalid transition: PHASE_A -> PHASE_G"


def test_enter_degraded_sets_flag_and_jumps_to_phase_g(tmp_path: Path) -> None:
    controller = _make_controller(tmp_path)
    controller._state = ControllerState(run_id="run-1", phase=Phase.PHASE_C)

    controller._enter_degraded("worker failed", "repo_reports")

    assert controller._state.degraded_mode is True
    assert controller._state.delivery_tier == "repo_reports"
    assert controller._state.phase == Phase.PHASE_G
    assert controller._state.degradation_log[-1] == "worker failed"


def test_run_completes_full_flow_with_mocked_executors(tmp_path: Path) -> None:
    executors = {
        "NeedProfileBuilder": _make_executor(_envelope("NeedProfileBuilder", _make_need_profile())),
        "DiscoveryRunner": _make_executor(_envelope("DiscoveryRunner", _make_discovery_result())),
        "WorkerSupervisor": _make_executor(
            _envelope("WorkerSupervisor", _make_extraction_result())
        ),
        "SynthesisRunner": _make_executor(_envelope("SynthesisRunner", _make_synthesis_result())),
        "SkillCompiler": _make_executor(_envelope("SkillCompiler", _make_compile_result())),
        "Validator": _make_executor(_envelope("Validator", _make_validation_result())),
        "DeliveryPackager": _make_executor(_envelope("DeliveryPackager", _make_delivery_result())),
    }

    with patch("doramagic_controller.flow_controller.build_capability_router", return_value=None):
        controller = FlowController(
            adapter=_make_adapter(),
            run_dir=tmp_path / "run-001",
            executors=executors,
        )

    result = asyncio.run(controller.run(user_input="Study alpha tooling patterns"))

    assert result.phase == Phase.DONE
    assert result.degraded_mode is False
    assert result.delivery_tier == "full_skill"
    assert result.candidate_count == 1
    assert result.synthesis_ok is True
    assert result.compile_ok is True
    assert result.quality_score == 92.0
    assert result.blockers is False
    assert result.phase_artifacts["delivery_manifest"]["delivery_tier"] == "full_skill"

    for name, executor in executors.items():
        assert executor.execute.await_count == 1, name


def test_run_brick_stitch_path_jumps_to_validator(tmp_path: Path) -> None:
    executors = {
        "NeedProfileBuilder": _make_executor(
            _envelope("NeedProfileBuilder", _make_domain_explore_profile())
        ),
        "Validator": _make_executor(_envelope("Validator", _make_validation_result())),
        "DeliveryPackager": _make_executor(_envelope("DeliveryPackager", _make_delivery_result())),
    }

    with (
        patch("doramagic_controller.flow_controller.build_capability_router", return_value=None),
        patch(
            "doramagic_controller.flow_controller.match_brick_categories",
            new=AsyncMock(
                return_value=[
                    SimpleNamespace(domain_id="skill_architecture"),
                    SimpleNamespace(domain_id="react"),
                    SimpleNamespace(domain_id="langgraph"),
                ]
            ),
        ),
        patch(
            "doramagic_controller.flow_controller.select_bricks",
            return_value=[SimpleNamespace(brick={"id": i}) for i in range(30)],
        ),
        patch(
            "doramagic_controller.flow_controller.run_brick_stitch",
            new=AsyncMock(
                return_value=_envelope(
                    "BrickStitcher",
                    {
                        "bricks_used": 30,
                        "categories_matched": ["langgraph", "react", "skill_architecture"],
                        "skill_key": "knowledge_ops",
                    },
                )
            ),
        ),
    ):
        controller = FlowController(
            adapter=_make_adapter(),
            run_dir=tmp_path / "run-001",
            executors=executors,
        )

        result = asyncio.run(controller.run(user_input="Build a knowledge system for this domain"))

    assert result.phase == Phase.DONE
    assert result.phase_artifacts["brick_coverage"]["eligible"] is True
    assert result.phase_artifacts["brick_stitch_result"]["bricks_used"] == 30
    assert result.phase_artifacts["compile_bundle"]["artifact_paths"]["SKILL.md"].endswith(
        "delivery/SKILL.md"
    )
    executors["NeedProfileBuilder"].execute.assert_awaited_once()
    executors["Validator"].execute.assert_awaited_once()
    executors["DeliveryPackager"].execute.assert_awaited_once()
