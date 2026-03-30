"""Executor input 构建 — 为每个阶段的 executor 准备输入数据。"""

from __future__ import annotations

from typing import Any

from doramagic_contracts.adapter import PlatformAdapter
from doramagic_contracts.base import NeedProfile, NeedProfileContract, RoutingDecision
from doramagic_contracts.cross_project import (
    CommunityKnowledge,
    CompareMetrics,
    CompareOutput,
    DiscoveryConfig,
    DiscoveryInput,
    DiscoveryResult,
    ExtractedProjectSummary,
    SynthesisInput,
    SynthesisReportData,
)
from doramagic_contracts.skill import (
    CompileBundleContract,
    SkillBundlePaths,
    SkillCompilerInput,
    ValidationInput,
)
from pydantic import BaseModel

from .flow_controller_state import ControllerState

try:
    from doramagic_shared_utils.capability_router import (
        TASK_CLAIM_SYNTHESIS,
        TASK_EVIDENCE_EXTRACTION,
        TASK_GENERAL,
        CapabilityRouter,
    )
except Exception:
    CapabilityRouter = None
    TASK_GENERAL = "general"
    TASK_EVIDENCE_EXTRACTION = "evidence_extraction"
    TASK_CLAIM_SYNTHESIS = "claim_synthesis"


def build_executor_input(
    executor_name: str, state: ControllerState, adapter: PlatformAdapter
) -> BaseModel:
    """为指定 executor 构建输入数据。"""
    arts = state.phase_artifacts

    if executor_name == "NeedProfileBuilder":

        class RawInput(BaseModel):
            raw_input: str

        return RawInput(raw_input=state.raw_input)

    if executor_name == "DiscoveryRunner":
        routing = RoutingDecision(**arts.get("routing_decision", {}))
        need_profile = NeedProfile(**arts["need_profile"])
        return DiscoveryInput(
            need_profile=need_profile,
            routing=routing,
            config=DiscoveryConfig(top_k_final=routing.max_repos),
        )

    if executor_name == "WorkerSupervisor":

        class PhaseCInput(BaseModel):
            need_profile: NeedProfile
            routing: RoutingDecision
            repos: list[dict[str, Any]]
            accumulated_knowledge: list[dict[str, Any]] = []

        routing = RoutingDecision(**arts.get("routing_decision", {}))
        need_profile = NeedProfile(**arts["need_profile"])
        repos: list[dict[str, Any]] = []
        if routing.route == "DIRECT_URL":
            for index, url in enumerate(routing.repo_urls[: routing.max_repos]):
                repos.append(
                    {
                        "candidate_id": f"url-{index}",
                        "name": url.rstrip("/").split("/")[-1],
                        "url": url,
                        "source": "direct_url",
                        "why_selected": "explicit user target",
                        "repo_type_hint": None,
                    }
                )
        else:
            discovery = arts.get("discovery_result", {})
            for candidate in discovery.get("candidates", [])[: routing.max_repos]:
                if not isinstance(candidate, dict):
                    continue
                repos.append(candidate)
        return PhaseCInput(
            need_profile=need_profile,
            routing=routing,
            repos=repos[: need_profile.max_projects],
            accumulated_knowledge=arts.get("accumulated_knowledge", []),
        )

    if executor_name == "SynthesisRunner":
        need_profile = NeedProfile(**arts["need_profile"])
        discovery = DiscoveryResult(
            **arts.get("discovery_result", {"candidates": [], "search_coverage": []})
        )
        extraction = arts.get("extraction_aggregate", {})
        project_summaries: list[ExtractedProjectSummary] = []
        for envelope in extraction.get("repo_envelopes", []):
            if not isinstance(envelope, dict) or envelope.get("status") == "failed":
                continue
            facts = envelope.get("repo_facts", {})
            repo_meta = facts.get("repo") or {}
            project_summaries.append(
                ExtractedProjectSummary(
                    project_id=envelope.get("repo_name", "unknown"),
                    repo={
                        "repo_id": repo_meta.get(
                            "repo_id",
                            envelope.get("worker_id", envelope.get("repo_name", "unknown")),
                        ),
                        "full_name": repo_meta.get(
                            "full_name", envelope.get("repo_name", "unknown")
                        ),
                        "url": repo_meta.get(
                            "url",
                            envelope.get("repo_url", "https://github.com/unknown/unknown"),
                        ),
                        "default_branch": repo_meta.get("default_branch", "main"),
                        "commit_sha": repo_meta.get("commit_sha", "unknown"),
                        "local_path": repo_meta.get("local_path", ""),
                    },
                    top_capabilities=envelope.get("feature_inventory", [])[:5],
                    top_constraints=envelope.get("anti_patterns", [])[:3],
                    top_failures=envelope.get("anti_patterns", [])[:5],
                    evidence_refs=[],
                )
            )
        return SynthesisInput(
            need_profile=need_profile,
            discovery_result=discovery,
            extraction_aggregate=extraction,
            project_summaries=project_summaries,
            comparison_result=CompareOutput(
                domain_id=need_profile.domain,
                compared_projects=[s.project_id for s in project_summaries],
                signals=[],
                metrics=CompareMetrics(
                    project_count=max(1, len(project_summaries)),
                    atom_count=0,
                    aligned_count=0,
                    missing_count=0,
                    original_count=0,
                    drifted_count=0,
                ),
            ),
            community_knowledge=CommunityKnowledge(),
        )

    if executor_name == "SkillCompiler":
        need_profile = NeedProfile(**arts["need_profile"])
        synthesis = SynthesisReportData(**arts.get("synthesis_bundle", {}))
        validation = arts.get("validation_report", {})
        target_sections = validation.get("repair_plan", []) if isinstance(validation, dict) else []
        existing_sections = {}
        compile_bundle = arts.get("compile_bundle", {})
        if isinstance(compile_bundle, dict):
            existing_sections = compile_bundle.get("section_drafts", {}) or {}
        return SkillCompilerInput(
            need_profile=need_profile,
            synthesis_report=synthesis,
            platform_rules=adapter.get_platform_rules(),
            target_sections=target_sections,
            accumulated_knowledge=arts.get("accumulated_knowledge", []),
            existing_sections=existing_sections,
        )

    if executor_name == "Validator":
        need_profile = NeedProfile(**arts["need_profile"])
        synthesis_raw = arts.get("synthesis_bundle", {})
        if isinstance(synthesis_raw, dict) and synthesis_raw:
            synthesis = SynthesisReportData(**synthesis_raw)
        else:
            synthesis = SynthesisReportData(
                consensus=[],
                conflicts=[],
                unique_knowledge=[],
                selected_knowledge=[],
                excluded_knowledge=[],
                open_questions=[],
                compile_ready=True,
                global_theses=[],
                common_why=[],
                divergences=[],
                source_provenance_matrix={},
                unknowns=[],
                compile_brief_by_section={},
            )
        compile_raw = arts.get("compile_bundle", {})
        if isinstance(compile_raw, dict) and compile_raw:
            compile_bundle = CompileBundleContract(**compile_raw)
        else:
            compile_bundle = CompileBundleContract(
                section_drafts={},
                full_draft="",
                artifact_paths={},
            )
        artifact_paths = compile_bundle.artifact_paths
        return ValidationInput(
            need_profile=need_profile,
            synthesis_report=synthesis,
            compile_bundle=compile_bundle,
            skill_bundle=SkillBundlePaths(
                skill_md_path=artifact_paths.get("SKILL.md", ""),
                readme_md_path=artifact_paths.get("README.md", ""),
                provenance_md_path=artifact_paths.get("PROVENANCE.md", ""),
                limitations_md_path=artifact_paths.get("LIMITATIONS.md", ""),
            ),
            platform_rules=adapter.get_platform_rules(),
        )

    if executor_name == "DeliveryPackager":

        class DeliveryInput(BaseModel):
            phase_artifacts: dict[str, Any]
            degraded_mode: bool
            delivery_tier: str
            run_id: str

        return DeliveryInput(
            phase_artifacts=arts,
            degraded_mode=state.degraded_mode,
            delivery_tier=state.delivery_tier,
            run_id=state.run_id,
        )

    raise ValueError(f"Unsupported executor {executor_name}")


def build_capability_router() -> object | None:
    """初始化 CapabilityRouter。优先读取 OpenClaw 平台配置，回退到 models.json。"""
    if CapabilityRouter is None:
        return None
    # 优先读取 OpenClaw 平台的 LLM 配置
    try:
        return CapabilityRouter.from_openclaw_config()
    except Exception:
        pass
    # 回退到 Doramagic 自带的 models.json
    try:
        return CapabilityRouter.from_config("models.json")
    except Exception:
        return None


def build_llm_adapter(executor_name: str, capability_router: object | None) -> object | None:
    """为 executor 选择合适的 LLM adapter。"""
    if capability_router is None:
        return None
    task_map = {
        "NeedProfileBuilder": TASK_GENERAL,
        "WorkerSupervisor": TASK_EVIDENCE_EXTRACTION,
        "SynthesisRunner": TASK_CLAIM_SYNTHESIS,
        "SkillCompiler": TASK_CLAIM_SYNTHESIS,
    }
    task = task_map.get(executor_name)
    if not task:
        return None
    try:
        capability_router._current_stage = executor_name
        return capability_router.for_task(task)
    except Exception:
        return None


def build_need_profile_contract(
    profile: NeedProfile, routing: RoutingDecision, adapter: PlatformAdapter
) -> NeedProfileContract:
    """构建 NeedProfileContract。"""
    domain_terms = list(dict.fromkeys(profile.relevance_terms or profile.keywords[:5]))
    success_criteria = [
        "交付可注入的 SKILL.md",
        "WHY/UNSAID 足够具体",
        "用户等待后总能拿到某种产出",
    ]
    return NeedProfileContract(
        need_profile=profile,
        route_kind=routing.route,
        must_clarify=routing.route == "LOW_CONFIDENCE",
        direct_targets=routing.repo_urls,
        repo_name_candidates=routing.project_names,
        domain_terms=domain_terms[:8],
        constraints=profile.constraints,
        success_criteria=success_criteria,
        max_projects=routing.max_repos,
        delivery_expectation="full_skill"
        if routing.route != "LOW_CONFIDENCE"
        else "clarify_or_explore",
        routing=routing,
    )
