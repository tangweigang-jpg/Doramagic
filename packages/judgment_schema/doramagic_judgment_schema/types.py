"""Doramagic Judgment Schema v1.0 — Pydantic 实现"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

# ── 枚举 ──


class Layer(StrEnum):
    KNOWLEDGE = "knowledge"
    RESOURCE = "resource"
    EXPERIENCE = "experience"


class Modality(StrEnum):
    MUST = "must"
    MUST_NOT = "must_not"
    SHOULD = "should"
    SHOULD_NOT = "should_not"


class Severity(StrEnum):
    FATAL = "fatal"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ScopeLevel(StrEnum):
    UNIVERSAL = "universal"
    DOMAIN = "domain"
    CONTEXT = "context"


class Freshness(StrEnum):
    STABLE = "stable"
    SEMI_STABLE = "semi_stable"
    VOLATILE = "volatile"


class LifecycleStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    SUPERSEDED = "superseded"
    INVALIDATED = "invalidated"


class ConsequenceKind(StrEnum):
    BUG = "bug"
    PERFORMANCE = "performance"
    COMPLIANCE = "compliance"
    SAFETY = "safety"
    FINANCIAL_LOSS = "financial_loss"
    FALSE_CLAIM = "false_claim"
    OPERATIONAL_FAILURE = "operational_failure"
    DATA_CORRUPTION = "data_corruption"
    SERVICE_DISRUPTION = "service_disruption"


class SourceLevel(StrEnum):
    S1_SINGLE_PROJECT = "S1_single_project"
    S2_CROSS_PROJECT = "S2_cross_project"
    S3_COMMUNITY = "S3_community"
    S4_REASONING = "S4_reasoning"


class ConsensusLevel(StrEnum):
    UNIVERSAL = "universal"
    STRONG = "strong"
    MIXED = "mixed"
    CONTESTED = "contested"


class CrystalSection(StrEnum):
    WORLD_MODEL = "world_model"
    CONSTRAINTS = "constraints"
    RESOURCE_PROFILE = "resource_profile"
    ARCHITECTURE = "architecture"
    PROTOCOLS = "protocols"
    EVIDENCE = "evidence"


class RelationType(StrEnum):
    GENERATES = "generates"
    DEPENDS_ON = "depends_on"
    CONFLICTS = "conflicts"
    STRENGTHENS = "strengthens"
    SUPERSEDES = "supersedes"
    SUBSUMES = "subsumes"


class EvidenceRefType(StrEnum):
    SOURCE_CODE = "source_code"
    ISSUE = "issue"
    PULL_REQUEST = "pull_request"
    DISCUSSION = "discussion"
    BENCHMARK = "benchmark"
    PAPER = "paper"
    DOC = "doc"
    USER_FEEDBACK = "user_feedback"


# ── 子模型 ──


class Consequence(BaseModel):
    kind: ConsequenceKind
    description: str = Field(min_length=10)


class JudgmentCore(BaseModel):
    when: str = Field(min_length=5, description="触发条件")
    modality: Modality
    action: str = Field(min_length=5, description="具体行为")
    consequence: Consequence


class ContextRequires(BaseModel):
    resources: list[str] = Field(default_factory=list)
    markets: list[str] = Field(default_factory=list)
    task_types: list[str] = Field(default_factory=list)
    tech_stack: list[str] = Field(default_factory=list)
    environments: list[str] = Field(default_factory=list)
    target_versions: dict[str, str] = Field(default_factory=dict)


class JudgmentScope(BaseModel):
    level: ScopeLevel
    domains: list[str] = Field(min_length=1)
    context_requires: ContextRequires | None = None


class EvidenceRef(BaseModel):
    type: EvidenceRefType
    source: str
    locator: str | None = None
    summary: str


class JudgmentConfidence(BaseModel):
    source: SourceLevel
    score: float = Field(ge=0.0, le=1.0)
    consensus: ConsensusLevel
    verified_by: list[str] = Field(default_factory=list)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)


class JudgmentCompilation(BaseModel):
    severity: Severity
    crystal_section: CrystalSection
    freshness: Freshness
    freshness_note: str | None = None
    emit_as_hard_constraint: bool = False
    machine_checkable: bool = False
    validator_template: str | None = None
    degradation_action: str | None = None
    query_tags: list[str] = Field(default_factory=list)


class Relation(BaseModel):
    type: RelationType
    target_id: str
    description: str = Field(min_length=5, description="给编译器 LLM 的因果解释")


class JudgmentVersion(BaseModel):
    status: LifecycleStatus = LifecycleStatus.DRAFT
    created_at: str = Field(default_factory=lambda: datetime.now(tz=UTC).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(tz=UTC).isoformat())
    review_after_days: int | None = None
    superseded_by: str | None = None
    schema_version: str = "1.0"


class JudgmentExamples(BaseModel):
    positive: list[str] = Field(default_factory=list)
    negative: list[str] = Field(default_factory=list)


# ── 主模型 ──


class Judgment(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    # ID 格式: {domain}-{K|R|E}-{数字}
    # domain 允许小写字母、数字、连字符、下划线
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]*-[KRE]-\d{3,}$")
    hash: str = ""
    core: JudgmentCore
    layer: Layer
    scope: JudgmentScope
    confidence: JudgmentConfidence
    compilation: JudgmentCompilation
    relations: list[Relation] = Field(default_factory=list)
    version: JudgmentVersion = Field(default_factory=JudgmentVersion)
    examples: JudgmentExamples | None = None
    notes: str | None = None

    def model_post_init(self, __context: object) -> None:
        """自动计算 content hash。"""
        if not self.hash:
            # mode="json" 确保 Enum 被序列化为字符串值，避免 TypeError
            content = json.dumps(
                {
                    "core": self.core.model_dump(mode="json"),
                    "scope": self.scope.model_dump(mode="json"),
                },
                sort_keys=True,
                ensure_ascii=False,
            )
            self.hash = hashlib.sha256(content.encode()).hexdigest()[:16]
