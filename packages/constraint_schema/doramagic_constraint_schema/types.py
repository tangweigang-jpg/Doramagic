"""Doramagic Constraint Schema v2.0 — Pydantic 实现。

基于 Blueprint+Constraint 两层知识架构，替代旧的三层 Judgment 模型。
Schema 定义见 docs/research/judgment-system/blueprint-constraint-schema-v0.2.md
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from enum import StrEnum

# 从 judgment_schema 复用稳定枚举和子模型
from doramagic_judgment_schema.types import (
    ConsensusLevel,
    Consequence,
    ConsequenceKind,
    EvidenceRef,
    EvidenceRefType,
    Freshness,
    LifecycleStatus,
    Modality,
    ScopeLevel,
    Severity,
)
from pydantic import BaseModel, ConfigDict, Field

# Re-export 以方便下游使用
__all__ = [
    "AppliesTo",
    "ConsensusLevel",
    "Consequence",
    "ConsequenceKind",
    "Constraint",
    "ConstraintConfidence",
    "ConstraintCore",
    "ConstraintExamples",
    "ConstraintKind",
    "ConstraintRelation",
    "ConstraintRelationType",
    "ConstraintScope",
    "ConstraintVersion",
    "ContextRequires",
    "EvidenceRef",
    "EvidenceRefType",
    "Freshness",
    "GuardPattern",
    "LifecycleStatus",
    "Modality",
    "ScopeLevel",
    "Severity",
    "SourceType",
    "TargetScope",
]


# ── 新枚举（v0.2 特有） ──


class ConstraintKind(StrEnum):
    """约束性质。替代旧模型的 Layer(K/R/E) 三分法。"""

    DOMAIN_RULE = "domain_rule"
    RESOURCE_BOUNDARY = "resource_boundary"
    OPERATIONAL_LESSON = "operational_lesson"
    ARCHITECTURE_GUARDRAIL = "architecture_guardrail"
    CLAIM_BOUNDARY = "claim_boundary"
    RATIONALIZATION_GUARD = "rationalization_guard"


class TargetScope(StrEnum):
    """约束挂载点类型。"""

    GLOBAL = "global"
    STAGE = "stage"
    EDGE = "edge"


class SourceType(StrEnum):
    """可信度来源类型。替代旧模型的 SourceLevel(S1-S4)。"""

    CODE_ANALYSIS = "code_analysis"
    DOCUMENT_EXTRACTION = "document_extraction"
    COMMUNITY_ISSUE = "community_issue"
    OFFICIAL_DOC = "official_doc"
    API_CHANGELOG = "api_changelog"
    CROSS_PROJECT = "cross_project"
    EXPERT_REASONING = "expert_reasoning"


class ConstraintRelationType(StrEnum):
    """约束间关系类型。"""

    CONFLICTS = "conflicts"
    STRENGTHENS = "strengthens"
    SUPERSEDES = "supersedes"
    SPECIALIZES = "specializes"
    GENERALIZES = "generalizes"
    RELATED_TO = "related_to"


# ── 子模型 ──


class ConstraintCore(BaseModel):
    """约束核心三元组：当[条件]时，必须/禁止[行为]，否则[后果]。"""

    when: str = Field(min_length=5, description="触发条件")
    modality: Modality
    action: str = Field(min_length=5, description="具体行为")
    consequence: Consequence


class AppliesTo(BaseModel):
    """约束挂载点——挂在蓝图的哪个位置。"""

    target_scope: TargetScope
    stage_ids: list[str] = Field(default_factory=list)
    edge_ids: list[str] = Field(default_factory=list)
    blueprint_ids: list[str] | None = None


class ContextRequires(BaseModel):
    """可选的上下文要求。"""

    resources: list[str] = Field(default_factory=list)
    task_types: list[str] = Field(default_factory=list)
    tech_stack: list[str] = Field(default_factory=list)


class ConstraintScope(BaseModel):
    """约束的适用范围。"""

    level: ScopeLevel
    domains: list[str] = Field(min_length=1)
    context_requires: ContextRequires | None = None


class ConstraintConfidence(BaseModel):
    """约束的可信度。"""

    source_type: SourceType
    score: float = Field(ge=0.0, le=1.0)
    consensus: ConsensusLevel
    verified_by: list[str] = Field(default_factory=list)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)


class ConstraintRelation(BaseModel):
    """约束间关系。"""

    type: ConstraintRelationType
    target_id: str
    description: str = Field(min_length=5, description="关系的因果解释")


class ConstraintVersion(BaseModel):
    """约束的生命周期元数据。"""

    status: LifecycleStatus = LifecycleStatus.DRAFT
    created_at: str = Field(default_factory=lambda: datetime.now(tz=UTC).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(tz=UTC).isoformat())
    review_after_days: int | None = None
    superseded_by: str | None = None
    schema_version: str = "2.0"


class GuardPattern(BaseModel):
    """Rationalization guard 专有字段：借口-反驳对。

    仅当 constraint_kind == rationalization_guard 时使用。
    记录 LLM 可能用来跳过规则的借口及其反驳。
    """

    excuse: str = Field(min_length=5, description="借口原文")
    rebuttal: str = Field(min_length=5, description="反驳")
    red_flags: list[str] = Field(default_factory=list, description="思维信号")
    violation_detector: str = Field(default="", description="可检测的违规行为描述")


class ConstraintExamples(BaseModel):
    """正面和反面示例。"""

    positive: list[str] = Field(default_factory=list)
    negative: list[str] = Field(default_factory=list)


# ── 主模型 ──


class Constraint(BaseModel):
    """Schema v0.2 约束模型。

    核心三元组：当[条件]时，必须/禁止[行为]，否则[后果]。
    通过 applies_to 挂载到蓝图的 stage/edge/global 层级。
    """

    model_config = ConfigDict(use_enum_values=True)

    # ID 格式: {domain}-C-{数字}
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]*-C-\d{3,}$")
    hash: str = ""

    # 核心三元组
    core: ConstraintCore
    constraint_kind: ConstraintKind

    # 挂载点
    applies_to: AppliesTo

    # 适用范围
    scope: ConstraintScope

    # 可信度
    confidence: ConstraintConfidence

    # 编译提示
    machine_checkable: bool = False
    promote_to_acceptance: bool = False

    # 严重度与新鲜度（从旧 compilation 子模型提升为顶级）
    severity: Severity
    freshness: Freshness

    # 关系
    relations: list[ConstraintRelation] = Field(default_factory=list)

    # 生命周期
    version: ConstraintVersion = Field(default_factory=ConstraintVersion)

    # SOP v2.2 新增
    validation_threshold: str | None = Field(
        default=None, description="可执行验证阈值（assert 表达式或 DSL）"
    )
    derived_from: dict | None = Field(
        default=None,
        description="派生溯源（blueprint_id + business_decision_id + derivation_version）",
    )

    # SOP v2.3 新增 — rationalization_guard 专有
    guard_pattern: GuardPattern | None = Field(
        default=None,
        description="借口-反驳对（仅 rationalization_guard 使用）",
    )

    # 可选
    examples: ConstraintExamples | None = None
    notes: str | None = None
    tags: list[str] = Field(default_factory=list)

    def model_post_init(self, __context: object) -> None:
        """自动计算 content hash。

        hash = sha256(when + modality + action + consequence_kind +
        consequence_description)[:16]。与 enrichment P15 使用相同的 5 字段公式，
        确保无论从 raw dict 还是 Constraint 对象计算，结果一致。
        """
        if not self.hash:
            content = json.dumps(
                {
                    "when": self.core.when,
                    "modality": str(self.core.modality),
                    "action": self.core.action,
                    "consequence_kind": str(self.core.consequence.kind),
                    "consequence_description": self.core.consequence.description,
                },
                sort_keys=True,
                ensure_ascii=False,
            )
            self.hash = hashlib.sha256(content.encode()).hexdigest()[:16]
