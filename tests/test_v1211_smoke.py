from __future__ import annotations

import asyncio
import json
from typing import Any

from doramagic_contracts.adapter import ClarificationRequest, ProgressUpdate
from doramagic_contracts.base import (
    CandidateQualitySignals,
    DiscoveryCandidate,
    ExtractionAggregateContract,
    NeedProfile,
    RepoExtractionEnvelope,
    SearchDirection,
)
from doramagic_contracts.budget import BudgetPolicy
from doramagic_contracts.cross_project import DiscoveryResult
from doramagic_contracts.envelope import ModuleResultEnvelope, RunMetrics
from doramagic_contracts.skill import PlatformRules
from doramagic_controller.flow_controller import FlowController
from doramagic_controller.state_definitions import Phase
from doramagic_executors.delivery_packager import DeliveryPackager
from doramagic_executors.need_profile_builder import NeedProfileBuilder
from doramagic_executors.skill_compiler_executor import SkillCompilerExecutor
from doramagic_executors.synthesis_runner import SynthesisRunner
from doramagic_executors.validator_executor import ValidatorExecutor
from pydantic import BaseModel


def _metrics() -> RunMetrics:
    return RunMetrics(
        wall_time_ms=1,
        llm_calls=0,
        prompt_tokens=0,
        completion_tokens=0,
        estimated_cost_usd=0.0,
    )


class MemoryAdapter:
    def __init__(self, storage_root: Path) -> None:
        self._storage_root = storage_root
        self.progress_updates: list[ProgressUpdate] = []
        self.clarifications: list[ClarificationRequest] = []
        self.outputs: list[tuple[str, dict[str, Path]]] = []

    async def receive_input(self) -> str:
        return ""

    async def send_output(self, message: str, artifacts: dict[str, Path]) -> None:
        self.outputs.append((message, artifacts))

    async def send_progress(self, update: ProgressUpdate) -> None:
        self.progress_updates.append(update)

    async def ask_clarification(self, request: ClarificationRequest) -> str:
        self.clarifications.append(request)
        return ""

    def get_storage_root(self) -> Path:
        return self._storage_root

    def get_platform_rules(self) -> PlatformRules:
        return PlatformRules()

    def get_concurrency_limit(self) -> int:
        return 3


class StaticExecutor:
    def __init__(self, module_name: str, *, data: Any, status: str = "ok") -> None:
        self.module_name = module_name
        self.data = data
        self.status = status
        self.calls = 0
        self.last_input: Any = None

    async def execute(self, input: BaseModel, adapter: object, config) -> ModuleResultEnvelope:
        self.calls += 1
        self.last_input = input
        payload = self.data(input) if callable(self.data) else self.data
        return ModuleResultEnvelope(
            module_name=self.module_name,
            status=self.status,
            data=payload,
            metrics=_metrics(),
        )

    def validate_input(self, input: BaseModel) -> list[str]:
        return []

    def can_degrade(self) -> bool:
        return True


def _profile(
    *, raw_input: str, domain: str, keywords: list[str], confidence: float = 0.86
) -> NeedProfile:
    return NeedProfile(
        raw_input=raw_input,
        keywords=keywords,
        intent=raw_input,
        intent_en=raw_input,
        domain=domain,
        search_directions=[SearchDirection(direction=keywords[0], priority="high")],
        constraints=["openclaw_compatible"],
        quality_expectations={},
        github_queries=keywords[:3],
        relevance_terms=keywords[:4],
        confidence=confidence,
        questions=[],
        max_projects=3,
    )


def _candidate(name: str, url: str, *, repo_type_hint: str | None = None) -> DiscoveryCandidate:
    return DiscoveryCandidate(
        candidate_id=name,
        name=name,
        url=url,
        type="github_repo",
        relevance="high",
        contribution=f"{name} repository for targeted extraction",
        quick_score=8.5,
        quality_signals=CandidateQualitySignals(
            stars=500,
            forks=40,
            last_updated="2026-03-28",
            has_readme=True,
            license="MIT",
        ),
        source="github",
        confidence=0.92,
        why_selected=f"matched {name}",
        repo_type_hint=repo_type_hint,
        extraction_profile="shallow" if repo_type_hint == "CATALOG" else "deep",
        selected_for_phase_c=True,
        selected_for_phase_d=False,
    )


def _repo_envelope(
    name: str,
    url: str,
    *,
    repo_type: str = "TOOL",
    extraction_profile: str = "deep",
    status: str = "ok",
) -> RepoExtractionEnvelope:
    return RepoExtractionEnvelope(
        worker_id=f"worker-{name}",
        repo_name=name,
        repo_url=url,
        repo_type=repo_type,
        status=status,
        repo_facts={
            "repo": {
                "repo_id": name,
                "full_name": name,
                "url": url,
                "default_branch": "main",
                "commit_sha": "abc123",
                "local_path": f"/tmp/{name}",
            }
        },
        extraction_profile_used=extraction_profile,
        evidence_cards=[
            {
                "title": f"{name} evidence",
                "summary": "Explicit state transitions are cheaper to reason about than hidden side effects.",
            }
        ]
        if status != "failed"
        else [],
        why_hypotheses=[
            f"{name} prefers explicit state transitions because failures become visible early and repairable.",
            f"{name} keeps user intent intact because broad abstractions hide the operational trade-off.",
        ]
        if status != "failed"
        else [],
        anti_patterns=[
            "implicit mutations across multiple files",
            "generic best-practice advice with no source anchoring",
        ]
        if status != "failed"
        else [],
        design_philosophy=(
            f"{name} favors explicit, inspectable workflow stages because each transition should carry enough evidence for the next phase."
            if status != "failed"
            else None
        ),
        mental_model=(
            f"Treat {name} as an auditable pipeline where each user-visible step maps to a durable artifact and a clear trade-off."
            if status != "failed"
            else None
        ),
        feature_inventory=[
            "extract repo facts",
            "surface trade-offs",
            "package reusable advisor guidance",
        ]
        if status != "failed"
        else [],
        community_signals={
            "dsd_metrics": {
                "dsd_warnings": [],
            }
        },
        extraction_confidence=0.91 if status != "failed" else 0.0,
        evidence_count=3 if status != "failed" else 0,
        warnings=[],
        metrics=_metrics(),
    )


def _aggregate(envelopes: list[RepoExtractionEnvelope]) -> ExtractionAggregateContract:
    success_count = sum(1 for env in envelopes if env.status != "failed")
    failed_count = sum(1 for env in envelopes if env.status == "failed")
    return ExtractionAggregateContract(
        repo_envelopes=envelopes,
        success_count=success_count,
        failed_count=failed_count,
        coverage_matrix={"why": [env.repo_name for env in envelopes if env.status != "failed"]},
        conflict_map={},
        ready_for_synthesis=success_count > 0,
    )


def _build_controller(
    run_dir: Path,
    adapter: MemoryAdapter,
    *,
    need_profile_executor: object,
    discovery_executor: object,
    worker_executor: object,
) -> FlowController:
    executors = {
        "NeedProfileBuilder": need_profile_executor,
        "DiscoveryRunner": discovery_executor,
        "WorkerSupervisor": worker_executor,
        "SynthesisRunner": SynthesisRunner(),
        "SkillCompiler": SkillCompilerExecutor(),
        "Validator": ValidatorExecutor(),
        "DeliveryPackager": DeliveryPackager(),
    }
    return FlowController(
        adapter=adapter,
        run_dir=run_dir,
        executors=executors,
        budget_policy=BudgetPolicy(),
    )


def _transitions(run_dir: Path) -> list[dict[str, Any]]:
    entries = []
    for line in (run_dir / "run_log.jsonl").read_text(encoding="utf-8").splitlines():
        payload = json.loads(line)
        if payload["event"] == "transition":
            entries.append(payload)
    return entries


def test_direct_url_skips_discovery_and_packages_full_skill(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-direct-url"
    adapter = MemoryAdapter(tmp_path)
    discovery = StaticExecutor(
        "DiscoveryRunner",
        data=DiscoveryResult(candidates=[], search_coverage=[], candidate_count=0),
    )
    worker = StaticExecutor(
        "WorkerSupervisor",
        data=_aggregate([_repo_envelope("ledger", "https://github.com/acme/ledger")]),
    )
    controller = _build_controller(
        run_dir,
        adapter,
        need_profile_executor=NeedProfileBuilder(),
        discovery_executor=discovery,
        worker_executor=worker,
    )

    result = asyncio.run(
        controller.run(user_input="请提取 https://github.com/acme/ledger 的设计灵魂，并总结 WHY。")
    )

    assert result.phase == Phase.DONE
    assert result.phase_artifacts["routing_decision"]["route"] == "DIRECT_URL"
    assert discovery.calls == 0
    assert worker.calls == 1
    visited = [entry["to"] for entry in _transitions(run_dir)]
    assert "PHASE_B" not in visited
    assert (run_dir / "delivery" / "SKILL.md").exists()
    assert (run_dir / "delivery" / "DSD_REPORT.md").exists()
    assert (run_dir / "delivery" / "CONFIDENCE_STATS.json").exists()


def test_ambiguous_input_clarifies_then_resumes(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-clarify"
    first_adapter = MemoryAdapter(tmp_path)
    first_discovery = StaticExecutor(
        "DiscoveryRunner",
        data=DiscoveryResult(candidates=[], search_coverage=[], candidate_count=0),
    )
    first_worker = StaticExecutor(
        "WorkerSupervisor",
        data=_aggregate([_repo_envelope("resume-demo", "https://github.com/acme/resume-demo")]),
    )
    first = _build_controller(
        run_dir,
        first_adapter,
        need_profile_executor=NeedProfileBuilder(),
        discovery_executor=first_discovery,
        worker_executor=first_worker,
    )

    paused = asyncio.run(first.run(user_input="帮我做个东西"))

    assert paused.phase == Phase.PHASE_A_CLARIFY
    assert first_adapter.clarifications
    assert "项目" in first_adapter.clarifications[0].question

    resumed_adapter = MemoryAdapter(tmp_path)
    resumed_discovery = StaticExecutor(
        "DiscoveryRunner",
        data=DiscoveryResult(candidates=[], search_coverage=[], candidate_count=0),
    )
    resumed_worker = StaticExecutor(
        "WorkerSupervisor",
        data=_aggregate([_repo_envelope("resume-demo", "https://github.com/acme/resume-demo")]),
    )
    resumed = _build_controller(
        run_dir,
        resumed_adapter,
        need_profile_executor=NeedProfileBuilder(),
        discovery_executor=resumed_discovery,
        worker_executor=resumed_worker,
    )

    result = asyncio.run(
        resumed.run(
            user_input="https://github.com/acme/resume-demo",
            resume_run_id=run_dir.name,
        )
    )

    assert result.phase == Phase.DONE
    assert result.clarification_round == 1
    assert result.phase_artifacts["routing_decision"]["route"] == "DIRECT_URL"
    assert resumed_discovery.calls == 0


def test_awesome_list_uses_catalog_shallow_path(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-awesome"
    adapter = MemoryAdapter(tmp_path)
    discovery = StaticExecutor(
        "DiscoveryRunner",
        data=DiscoveryResult(
            candidates=[
                _candidate(
                    "vinta/awesome-python",
                    "https://github.com/vinta/awesome-python",
                    repo_type_hint="CATALOG",
                )
            ],
            search_coverage=[],
            candidate_count=1,
            search_evidence=["broad:python tooling"],
        ),
    )
    worker = StaticExecutor(
        "WorkerSupervisor",
        data=_aggregate(
            [
                _repo_envelope(
                    "vinta/awesome-python",
                    "https://github.com/vinta/awesome-python",
                    repo_type="CATALOG",
                    extraction_profile="shallow",
                )
            ]
        ),
    )
    controller = _build_controller(
        run_dir,
        adapter,
        need_profile_executor=StaticExecutor(
            "NeedProfileBuilder",
            data=_profile(
                raw_input="帮我找一份高质量的 Python 工具收藏清单",
                domain="python tooling",
                keywords=["python tooling", "curated list", "developer tools"],
            ),
        ),
        discovery_executor=discovery,
        worker_executor=worker,
    )

    result = asyncio.run(controller.run(user_input="帮我找一份高质量的 Python 工具收藏清单"))

    assert result.phase == Phase.DONE
    assert result.phase_artifacts["routing_decision"]["route"] == "DOMAIN_EXPLORE"
    assert worker.last_input.repos[0]["repo_type_hint"] == "CATALOG"
    envelope = result.phase_artifacts["extraction_aggregate"]["repo_envelopes"][0]
    assert envelope["repo_type"] == "CATALOG"
    assert envelope["extraction_profile_used"] == "shallow"


def test_three_projects_one_failure_finishes_with_degraded_delivery(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-partial"
    adapter = MemoryAdapter(tmp_path)
    discovery = StaticExecutor(
        "DiscoveryRunner",
        data=DiscoveryResult(
            candidates=[
                _candidate("acme/ledger", "https://github.com/acme/ledger"),
                _candidate("acme/budget", "https://github.com/acme/budget"),
                _candidate("acme/reporting", "https://github.com/acme/reporting"),
            ],
            search_coverage=[],
            candidate_count=3,
            search_evidence=["broad:personal finance"],
        ),
    )
    worker = StaticExecutor(
        "WorkerSupervisor",
        status="degraded",
        data=_aggregate(
            [
                _repo_envelope("acme/ledger", "https://github.com/acme/ledger"),
                _repo_envelope("acme/budget", "https://github.com/acme/budget"),
                _repo_envelope(
                    "acme/reporting", "https://github.com/acme/reporting", status="failed"
                ),
            ]
        ),
    )
    controller = _build_controller(
        run_dir,
        adapter,
        need_profile_executor=StaticExecutor(
            "NeedProfileBuilder",
            data=_profile(
                raw_input="帮我做一个记账 app，强调账本一致性和长期维护",
                domain="personal finance",
                keywords=["personal finance", "expense ledger", "bookkeeping workflow"],
            ),
        ),
        discovery_executor=discovery,
        worker_executor=worker,
    )

    result = asyncio.run(controller.run(user_input="帮我做一个记账 app，强调账本一致性和长期维护"))

    # With 2/3 successful extractions, pipeline completes to DONE but with degraded_mode
    assert result.phase in (Phase.DONE, Phase.DEGRADED)
    assert result.degraded_mode is True
    assert any("partial failure" in item for item in result.degradation_log)
    manifest = result.phase_artifacts.get("delivery_manifest", {})
    if manifest:
        assert manifest["delivery_tier"] == "full_skill"
        assert "SKILL.md" in manifest["artifact_paths"]
