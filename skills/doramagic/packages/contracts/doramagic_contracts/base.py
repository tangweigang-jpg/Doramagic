"""基础共享模型 — 多个模块复用。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl

from doramagic_contracts.envelope import RunMetrics

Priority = Literal["high", "medium", "low"]
Confidence = Literal["high", "medium", "low"]
CandidateType = Literal["github_repo", "community_skill", "tutorial", "use_case"]
SearchStatus = Literal["covered", "partial", "missing"]
RouteKind = Literal[
    "DIRECT_URL",
    "NAMED_PROJECT",
    "DOMAIN_EXPLORE",
    "BRICK_STITCH",
    "LOW_CONFIDENCE",
]
RepoType = Literal["TOOL", "FRAMEWORK", "CATALOG"]
KnowledgeType = Literal[
    "capability", "rationale", "constraint", "interface", "failure", "assembly_pattern"
]
SignalKind = Literal["ALIGNED", "STALE", "MISSING", "ORIGINAL", "DRIFTED", "DIVERGENT", "CONTESTED"]
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
    start_line: int | None = Field(default=None, ge=1)
    end_line: int | None = Field(default=None, ge=1)
    snippet: str | None = None
    artifact_name: str | None = None
    source_url: str | None = None
    evidence_tag: EvidenceTag | None = None  # CODE/DOC/COMMUNITY/INFERENCE


class SearchDirection(BaseModel):
    direction: str
    priority: Priority


class UserContext(BaseModel):
    """用户运行环境上下文 — 由平台适配器注入，SkillCompiler 消费。

    v1 设计原则：所有字段 Optional，零破坏性，平台不支持的字段留 None。
    """

    schema_version: str = "dm.user-context.v1"
    timezone: str | None = None  # IANA format, e.g. "Asia/Bangkok"
    locale: str | None = None  # BCP-47, e.g. "zh-CN"
    location_hint: str | None = None  # natural language, e.g. "Chiang Mai, Thailand"
    os_platform: str | None = None  # "darwin" / "linux" / "win32"
    preferred_language: str | None = None  # "python" / "typescript" / "bash"
    technical_level: str | None = None  # "beginner" / "intermediate" / "expert"
    time_budget_minutes: int | None = None
    preferences: dict[str, str] = {}


class NeedProfile(BaseModel):
    """用户需求结构化表示 — Phase A 输出，驱动整个管线。

    v1.1: 新增 LLM 生成的搜索优化字段（Optional，向后兼容）。
    v1.2: 新增 user_context（平台适配器注入）。
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
    intent_en: str | None = None
    github_queries: list[str] = []
    relevance_terms: list[str] = []
    confidence: float = Field(default=0.8, ge=0, le=1)
    questions: list[str] = []
    max_projects: int = Field(default=3, ge=1, le=3)
    # v1.2: user runtime context (injected by platform adapter)
    user_context: UserContext | None = None


class RoutingDecision(BaseModel):
    """确定性输入路由结果。"""

    route: RouteKind
    skip_discovery: bool = False
    max_repos: int = Field(default=3, ge=1, le=3)
    repo_urls: list[str] = []
    project_names: list[str] = []
    confidence: float = Field(default=1.0, ge=0, le=1)
    reasoning: str = ""


class NeedProfileContract(BaseModel):
    """Phase A 输出给后续 phase 的完整契约。"""

    schema_version: str = "dm.need-profile-contract.v1"
    need_profile: NeedProfile
    route_kind: RouteKind
    must_clarify: bool = False
    direct_targets: list[str] = []
    repo_name_candidates: list[str] = []
    domain_terms: list[str] = []
    constraints: list[str] = []
    success_criteria: list[str] = []
    max_projects: int = Field(default=3, ge=1, le=3)
    delivery_expectation: str = "full_skill"
    routing: RoutingDecision


class CandidateQualitySignals(BaseModel):
    stars: int | None = Field(default=None, ge=0)
    forks: int | None = Field(default=None, ge=0)
    last_updated: str | None = None
    has_readme: bool = True
    issue_activity: str | None = None
    license: str | None = None


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
    source: str = "github"
    confidence: float = Field(default=0.5, ge=0, le=1)
    why_selected: str = ""
    repo_type_hint: RepoType | None = None
    extraction_profile: str = "deep"
    selected_for_phase_c: bool = False
    selected_for_phase_d: bool = False


class SearchCoverageItem(BaseModel):
    direction: str
    status: SearchStatus
    notes: str | None = None


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
    verdict: Verdict | None = None
    policy_action: PolicyAction | None = None


class CommunitySignalItem(BaseModel):
    """结构化社区信号 — 带适用域约束。"""

    signal_id: str
    title: str
    description: str
    source_type: Literal["issue", "pr", "changelog", "security_advisory", "discussion"]
    source_ref: str  # Issue #123, CHANGELOG v2.0
    # 适用域约束
    applicable_versions: str | None = None  # ">=2.0,<3.0" or None = all
    applicable_environments: list[str] = []  # ["linux", "docker"] or [] = all
    applicable_personas: list[str] = []  # ["beginner", "enterprise"] or [] = all
    is_exception_path: bool = False  # True = edge case, False = common path
    source_confidence: Confidence = "medium"


class CommunitySignals(BaseModel):
    issue_activity: str | None = None
    pr_merge_velocity: str | None = None
    changelog_frequency: str | None = None
    sentiment: Literal["positive", "mixed", "controversial", "quiet"] | None = None
    structured_signals: list[CommunitySignalItem] = []  # v1.1: 结构化信号


class ProjectFingerprint(BaseModel):
    """项目指纹 — 机器可比较的项目知识表示。"""

    schema_version: str = "dm.project-fingerprint.v1"
    project: RepoRef
    code_fingerprint: dict
    knowledge_atoms: list[KnowledgeAtom]
    soul_graph: dict
    community_signals: CommunitySignals


class RepoExtractionEnvelope(BaseModel):
    """单 repo worker 的标准输出。"""

    schema_version: str = "dm.repo-extraction-envelope.v1"
    worker_id: str
    repo_name: str
    repo_url: str
    repo_type: RepoType
    status: Literal["ok", "partial", "failed"]
    repo_facts: dict[str, Any] = {}
    extraction_profile_used: str = ""
    evidence_cards: list[dict[str, Any]] = []
    why_hypotheses: list[str] = []
    anti_patterns: list[str] = []
    why_decisions: list[dict[str, Any]] = []
    unsaid_traps: list[dict[str, Any]] = []
    design_philosophy: str | None = None
    mental_model: str | None = None
    feature_inventory: list[str] = []
    community_signals: dict[str, Any] = {}
    extraction_confidence: float = Field(default=0.0, ge=0, le=1)
    evidence_count: int = Field(default=0, ge=0)
    failure_scope: str | None = None
    dsd_metrics: dict[str, Any] | None = None
    warnings: list[str] = []
    metrics: RunMetrics


class ExtractionAggregateContract(BaseModel):
    """Phase C 聚合输出。"""

    schema_version: str = "dm.extraction-aggregate-contract.v1"
    repo_envelopes: list[RepoExtractionEnvelope]
    success_count: int = Field(default=0, ge=0)
    failed_count: int = Field(default=0, ge=0)
    coverage_matrix: dict[str, list[str]] = {}
    conflict_map: dict[str, list[str]] = {}
    ready_for_synthesis: bool = False
