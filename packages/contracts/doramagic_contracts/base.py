"""基础共享模型 — 多个模块复用。"""

from __future__ import annotations

from typing import Optional, Literal

from pydantic import BaseModel, Field, HttpUrl

Priority = Literal["high", "medium", "low"]
Confidence = Literal["high", "medium", "low"]
CandidateType = Literal["github_repo", "community_skill", "tutorial", "use_case"]
SearchStatus = Literal["covered", "partial", "missing"]
KnowledgeType = Literal[
    "capability", "rationale", "constraint", "interface", "failure", "assembly_pattern"
]
SignalKind = Literal[
    "ALIGNED", "STALE", "MISSING", "ORIGINAL", "DRIFTED", "DIVERGENT", "CONTESTED"
]
NormativeForce = Literal["must", "should", "may", "observed"]

# --- 置信度体系 (v1.1) ---
EvidenceTag = Literal["CODE", "DOC", "COMMUNITY", "INFERENCE"]
Verdict = Literal["SUPPORTED", "CONTESTED", "WEAK", "REJECTED"]
PolicyAction = Literal["ALLOW_CORE", "ALLOW_STORY", "QUARANTINE"]


class RepoRef(BaseModel):
    """仓库引用。"""

    repo_id: str
    full_name: str
    url: HttpUrl
    default_branch: str
    commit_sha: str
    local_path: str


class EvidenceRef(BaseModel):
    """证据引用 — 支撑知识声明的具体来源。"""

    kind: Literal["file_line", "artifact_ref", "community_ref"]
    path: str
    start_line: Optional[int] = Field(default=None, ge=1)
    end_line: Optional[int] = Field(default=None, ge=1)
    snippet: Optional[str] = None
    artifact_name: Optional[str] = None
    source_url: Optional[str] = None
    evidence_tag: Optional[EvidenceTag] = None  # CODE/DOC/COMMUNITY/INFERENCE


class SearchDirection(BaseModel):
    direction: str
    priority: Priority


class NeedProfile(BaseModel):
    """用户需求结构化表示 — Phase A 输出，驱动整个管线。

    v1.1: 新增 LLM 生成的搜索优化字段（Optional，向后兼容）。
    """

    schema_version: str = "dm.need-profile.v1"
    raw_input: str
    keywords: list[str]
    intent: str
    search_directions: list[SearchDirection]
    constraints: list[str]
    quality_expectations: dict[str, str] = {}
    # v1.1: LLM-generated search optimization
    domain: str = "general"
    intent_en: Optional[str] = None
    github_queries: list[str] = []
    relevance_terms: list[str] = []


class CandidateQualitySignals(BaseModel):
    stars: Optional[int] = Field(default=None, ge=0)
    forks: Optional[int] = Field(default=None, ge=0)
    last_updated: Optional[str] = None
    has_readme: bool = True
    issue_activity: Optional[str] = None
    license: Optional[str] = None


class DiscoveryCandidate(BaseModel):
    """候选项目。"""

    candidate_id: str
    name: str
    url: str
    type: CandidateType
    relevance: Priority
    contribution: str
    quick_score: float = Field(ge=0, le=10)
    quality_signals: CandidateQualitySignals
    selected_for_phase_c: bool = False
    selected_for_phase_d: bool = False


class SearchCoverageItem(BaseModel):
    direction: str
    status: SearchStatus
    notes: Optional[str] = None


class KnowledgeAtom(BaseModel):
    """知识原子 — 图谱的基本单位。"""

    atom_id: str
    knowledge_type: KnowledgeType
    subject: str
    predicate: str
    object: str
    scope: str
    normative_force: NormativeForce
    confidence: Confidence
    evidence_refs: list[EvidenceRef]
    source_card_ids: list[str]
    # 置信度体系 (v1.1)
    evidence_tags: list[EvidenceTag] = []
    verdict: Optional[Verdict] = None
    policy_action: Optional[PolicyAction] = None


class CommunitySignalItem(BaseModel):
    """结构化社区信号 — 带适用域约束。"""

    signal_id: str
    title: str
    description: str
    source_type: Literal["issue", "pr", "changelog", "security_advisory", "discussion"]
    source_ref: str  # Issue #123, CHANGELOG v2.0
    # 适用域约束
    applicable_versions: Optional[str] = None  # ">=2.0,<3.0" or None = all
    applicable_environments: list[str] = []  # ["linux", "docker"] or [] = all
    applicable_personas: list[str] = []  # ["beginner", "enterprise"] or [] = all
    is_exception_path: bool = False  # True = edge case, False = common path
    source_confidence: Confidence = "medium"


class CommunitySignals(BaseModel):
    issue_activity: Optional[str] = None
    pr_merge_velocity: Optional[str] = None
    changelog_frequency: Optional[str] = None
    sentiment: Optional[Literal["positive", "mixed", "controversial", "quiet"]] = None
    structured_signals: list[CommunitySignalItem] = []  # v1.1: 结构化信号


class ProjectFingerprint(BaseModel):
    """项目指纹 — 机器可比较的项目知识表示。"""

    schema_version: str = "dm.project-fingerprint.v1"
    project: RepoRef
    code_fingerprint: dict
    knowledge_atoms: list[KnowledgeAtom]
    soul_graph: dict
    community_signals: CommunitySignals
