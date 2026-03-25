"""跨项目模块模型 — Discovery/Compare/Synthesis + Community。"""

from __future__ import annotations

from typing import Optional, Literal

from pydantic import BaseModel, Field

from doramagic_contracts.base import (
    DiscoveryCandidate,
    EvidenceRef,
    NeedProfile,
    Priority,
    ProjectFingerprint,
    RepoRef,
    SearchCoverageItem,
    SignalKind,
)

# --- Community ---


class CommunityKnowledgeItem(BaseModel):
    item_id: str
    name: str
    source: str
    kind: Literal["skill", "tutorial", "use_case"]
    capabilities: list[str]
    storage_pattern: Optional[str] = None
    cron_pattern: Optional[str] = None
    reusable_knowledge: list[str]


class CommunityKnowledge(BaseModel):
    schema_version: str = "dm.community-knowledge.v1"
    skills: list[CommunityKnowledgeItem] = []
    tutorials: list[CommunityKnowledgeItem] = []
    use_cases: list[CommunityKnowledgeItem] = []


# --- Discovery ---


class DiscoveryConfig(BaseModel):
    github_min_stars: int = Field(default=10, ge=0)
    github_max_candidates_per_direction: int = Field(default=10, ge=1, le=30)
    stale_months_threshold: int = Field(default=6, ge=1, le=24)
    top_k_final: int = Field(default=5, ge=1, le=10)
    allow_api_enrichment: bool = True


class ApiDomainHint(BaseModel):
    domain_id: str
    matched_keywords: list[str]
    domain_bricks: list[str] = []


class DiscoveryInput(BaseModel):
    schema_version: str = "dm.discovery-input.v1"
    need_profile: NeedProfile
    api_hint: Optional[ApiDomainHint] = None
    config: DiscoveryConfig


class DiscoveryResult(BaseModel):
    schema_version: str = "dm.discovery-result.v1"
    candidates: list[DiscoveryCandidate]
    search_coverage: list[SearchCoverageItem]
    no_candidate_reason: Optional[str] = None


# --- Compare ---


class CompareConfig(BaseModel):
    exact_aligned_threshold: float = Field(default=0.92, ge=0, le=1)
    semantic_threshold: float = Field(default=0.80, ge=0, le=1)
    partial_threshold: float = Field(default=0.62, ge=0, le=1)
    missing_min_coverage: float = Field(default=0.60, ge=0, le=1)
    missing_min_independence: float = Field(default=0.55, ge=0, le=1)
    missing_min_support: int = Field(default=3, ge=1)


class CompareInput(BaseModel):
    schema_version: str = "dm.compare-input.v1"
    domain_id: str
    fingerprints: list[ProjectFingerprint]
    config: CompareConfig


class CompareSignal(BaseModel):
    signal_id: str
    signal: SignalKind
    subject_project_ids: list[str]
    normalized_statement: str
    support_count: int = Field(ge=0)
    support_independence: float = Field(ge=0, le=1)
    match_score: float = Field(ge=0, le=1)
    evidence_refs: list[EvidenceRef]
    notes: Optional[str] = None


class CompareMetrics(BaseModel):
    project_count: int = Field(ge=1)
    atom_count: int = Field(ge=0)
    aligned_count: int = Field(ge=0)
    missing_count: int = Field(ge=0)
    original_count: int = Field(ge=0)
    drifted_count: int = Field(ge=0)


class CompareOutput(BaseModel):
    schema_version: str = "dm.compare-output.v1"
    domain_id: str
    compared_projects: list[str]
    signals: list[CompareSignal]
    metrics: CompareMetrics


# --- Synthesis ---


class ExtractedProjectSummary(BaseModel):
    project_id: str
    repo: RepoRef
    top_capabilities: list[str]
    top_constraints: list[str]
    top_failures: list[str]
    evidence_refs: list[EvidenceRef]


class SynthesisInput(BaseModel):
    schema_version: str = "dm.synthesis-input.v1"
    need_profile: NeedProfile
    discovery_result: DiscoveryResult
    project_summaries: list[ExtractedProjectSummary]
    comparison_result: CompareOutput
    community_knowledge: CommunityKnowledge


class SynthesisDecision(BaseModel):
    decision_id: str
    statement: str
    decision: Literal["include", "exclude", "option"]
    rationale: str
    source_refs: list[str]
    demand_fit: Priority


class SynthesisConflict(BaseModel):
    conflict_id: str
    category: Literal[
        "semantic", "scope", "architecture", "dependency", "operational", "license"
    ]
    title: str
    positions: list[str]
    recommended_resolution: str
    source_refs: list[str]


class SynthesisReportData(BaseModel):
    schema_version: str = "dm.synthesis-report.v1"
    consensus: list[SynthesisDecision]
    conflicts: list[SynthesisConflict]
    unique_knowledge: list[SynthesisDecision]
    selected_knowledge: list[SynthesisDecision]
    excluded_knowledge: list[SynthesisDecision]
    open_questions: list[str]
