"""Pydantic schemas for constraint extraction — Instructor three-level degradation.

Instructor uses tool_use to force LLM output that conforms to these schemas.
Used by SOP v2.2 steps 2.1–2.5 (stage/edge/global extraction, BD derivation,
audit conversion).

Import RawFallback from schemas_v5 rather than redefining it.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from doramagic_extraction_agent.sop.schemas_v5 import RawFallback  # noqa: F401

# ── Literal type aliases (mirrors enums in constraint_schema types.py) ──

_MODALITY = Literal["must", "must_not", "should", "should_not"]
_CONSEQUENCE_KIND = Literal[
    "bug",
    "performance",
    "financial_loss",
    "data_corruption",
    "service_disruption",
    "operational_failure",
    "compliance",
    "safety",
    "false_claim",
]
_CONSTRAINT_KIND = Literal[
    "domain_rule",
    "resource_boundary",
    "operational_lesson",
    "architecture_guardrail",
    "claim_boundary",
    "rationalization_guard",
]
_SEVERITY = Literal["fatal", "high", "medium", "low"]
_SOURCE_TYPE = Literal[
    "code_analysis",
    "document_extraction",
    "community_issue",
    "official_doc",
    "api_changelog",
    "cross_project",
    "expert_reasoning",
]
_CONSENSUS = Literal["universal", "strong", "mixed", "contested"]
_FRESHNESS = Literal["stable", "semi_stable", "volatile"]
_TARGET_SCOPE = Literal["global", "stage", "edge"]

_VALID_CONSTRAINT_KINDS: frozenset[str] = frozenset(
    [
        "domain_rule",
        "resource_boundary",
        "operational_lesson",
        "architecture_guardrail",
        "claim_boundary",
        "rationalization_guard",
    ]
)
_VAGUE_WORDS = [
    "考虑",
    "注意",
    "建议",
    "适当",
    "尽量",
    "try to",
    "consider",
    "be careful",
    "appropriate",
]


class RawConstraint(BaseModel):
    """Single constraint in flat format as produced by LLM extraction.

    Deliberately non-nested so Instructor can reliably coerce LLM output via
    tool_use without deep object construction failures.
    """

    when: str = Field(min_length=5, description="触发条件（编码时视角）")
    modality: _MODALITY = Field(description="约束极性：must / must_not / should / should_not")
    action: str = Field(min_length=5, description="具体可执行行为")
    consequence_kind: _CONSEQUENCE_KIND = Field(description="后果分类")
    consequence_description: str = Field(
        min_length=20,
        description="违反约束的具体失败现象，禁止只填 consequence_kind 单词",
    )
    constraint_kind: _CONSTRAINT_KIND = Field(description="约束性质")
    severity: _SEVERITY = Field(description="严重度：fatal / high / medium / low")
    confidence_score: float = Field(ge=0.0, le=1.0, description="可信度分数 0.0–1.0")
    source_type: _SOURCE_TYPE = Field(description="证据来源类型")
    consensus: _CONSENSUS = Field(description="社区共识程度")
    freshness: _FRESHNESS = Field(description="约束稳定性：stable / semi_stable / volatile")
    target_scope: _TARGET_SCOPE = Field(description="挂载点类型：global / stage / edge")
    stage_ids: list[str] = Field(
        default_factory=list,
        description="target_scope=stage 时必填的阶段 ID 列表",
    )
    edge_ids: list[str] = Field(
        default_factory=list,
        description="target_scope=edge 时填写的边 ID 列表",
    )
    evidence_summary: str = Field(
        min_length=5,
        description="证据摘要；非 expert_reasoning 时必须含 file:line 引用（以 ':' 分隔）",
    )
    machine_checkable: bool = Field(
        default=False,
        description="约束是否可通过 grep/regex/静态检查自动验证",
    )
    promote_to_acceptance: bool = Field(
        default=False,
        description="是否晋升为验收标准",
    )
    validation_threshold: str | None = Field(
        default=None,
        description=(
            "当 machine_checkable=true 且 severity=fatal 时必填。"
            "格式：grep/regex 条件 → PASS/FAIL/WARN。"
            "示例：'macd_fast != 12 OR macd_slow != 26 → FAIL'"
        ),
    )
    # SOP v2.3: rationalization_guard 专有字段
    guard_pattern: dict | None = Field(
        default=None,
        description=(
            "仅 rationalization_guard 使用。格式：{excuse, rebuttal, red_flags, violation_detector}"
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def coerce_minimax_quirks(cls, data: Any) -> Any:
        """MiniMax M2.7 output normalization.

        Named coercions for known model-specific output quirks.
        Each coercion cites which model/step triggers it.
        """
        if not isinstance(data, dict):
            return data
        # MiniMax field name aliases
        _ALIASES = {
            "kind": "constraint_kind",
            "type": "constraint_kind",
            "score": "confidence_score",
            "confidence": "confidence_score",
            "scope": "target_scope",
            "stages": "stage_ids",
            "evidence": "evidence_summary",
            "consequence": "consequence_description",
            "checkable": "machine_checkable",
        }
        for alias, canonical in _ALIASES.items():
            if alias in data and canonical not in data:
                data[canonical] = data.pop(alias)
        # MiniMax bool coercion: writes descriptive strings for bool fields
        for bool_field in ("machine_checkable", "promote_to_acceptance"):
            v = data.get(bool_field)
            if isinstance(v, str):
                data[bool_field] = v.lower() in ("true", "yes", "1", "是")
        # MiniMax confidence_score as string
        cs = data.get("confidence_score")
        if isinstance(cs, str):
            try:
                data["confidence_score"] = float(cs)
            except ValueError:
                data["confidence_score"] = 0.7
        # MiniMax enum normalization: common misspellings / alternative values
        ck = data.get("constraint_kind")
        if isinstance(ck, str):
            normalized = ck.lower().strip().replace(" ", "_").replace("-", "_")
            if normalized not in _VALID_CONSTRAINT_KINDS:
                # Exact suffix match: e.g. "guard" → "rationalization_guard" only if
                # exactly one valid kind ends with the normalized value.
                suffix_matches = [v for v in _VALID_CONSTRAINT_KINDS if v.endswith(normalized)]
                if len(suffix_matches) == 1:
                    data["constraint_kind"] = suffix_matches[0]
                else:
                    # Prefix match: e.g. "domain" → "domain_rule"
                    prefix_matches = [
                        v for v in _VALID_CONSTRAINT_KINDS if v.startswith(normalized)
                    ]
                    if len(prefix_matches) == 1:
                        data["constraint_kind"] = prefix_matches[0]
        sev = data.get("severity")
        if isinstance(sev, str):
            sev_lower = sev.lower().strip()
            if sev_lower in ("critical", "blocker"):
                data["severity"] = "fatal"
            elif sev_lower in ("warning", "minor"):
                data["severity"] = "medium"
        return data

    @field_validator("action")
    @classmethod
    def action_no_vague_words(cls, v: str) -> str:
        found = [w for w in _VAGUE_WORDS if w in v]
        if found:
            raise ValueError(f"action 含模糊词 {found!r}，必须改为具体可执行的行为描述")
        return v

    @field_validator("evidence_summary")
    @classmethod
    def evidence_needs_ref(cls, v: str, info) -> str:
        # Access source_type via info.data (field validated before this one
        # only if source_type was declared first; we guard with .get)
        source_type = (info.data or {}).get("source_type")
        if source_type and source_type != "expert_reasoning" and ":" not in v:
            raise ValueError(
                f"source_type={source_type!r} 的 evidence_summary 必须包含 file:line 引用"
                f"（':'），当前值：{v!r}"
            )
        return v

    @model_validator(mode="after")
    def scope_stage_ids_check(self) -> RawConstraint:
        if self.target_scope == "stage" and not self.stage_ids:
            raise ValueError("target_scope='stage' 时 stage_ids 不能为空，请填写对应的阶段 ID")
        return self


class ConstraintExtractionResult(BaseModel):
    """Extraction result for a single stage / edge / global unit.

    Instructor returns this after the extraction + omission-check passes.
    """

    constraints: list[RawConstraint] = Field(
        description="提取到的所有约束列表",
    )
    coverage_report: dict[str, int] = Field(
        default_factory=dict,
        description="按 constraint_kind 统计的约束数量，keys 必须是合法 constraint_kind 值",
    )
    missed_hints: list[str] = Field(
        default_factory=list,
        description="未被约束覆盖的 acceptance_hints（用于质量审计）",
    )

    @model_validator(mode="before")
    @classmethod
    def coerce_top_level(cls, data: Any) -> Any:
        """Handle MiniMax returning bare list instead of dict."""
        if isinstance(data, list):
            return {"constraints": data}
        if isinstance(data, dict):
            if "results" in data and "constraints" not in data:
                data["constraints"] = data.pop("results")
            if "items" in data and "constraints" not in data:
                data["constraints"] = data.pop("items")
            # Make coverage_report optional — MiniMax often omits it
            if "coverage_report" not in data:
                data["coverage_report"] = {}
        return data

    @model_validator(mode="after")
    def validate_coverage_report(self) -> ConstraintExtractionResult:
        # Skip validation if coverage_report is empty (auto-filled)
        if not self.coverage_report:
            return self
        for key in self.coverage_report:
            if key not in _VALID_CONSTRAINT_KINDS:
                raise ValueError(
                    f"coverage_report key {key!r} 不是合法的 constraint_kind，"
                    f"合法值：{sorted(_VALID_CONSTRAINT_KINDS)}"
                )
        total_reported = sum(self.coverage_report.values())
        actual = len(self.constraints)
        if total_reported != actual:
            raise ValueError(
                f"coverage_report 总计 {total_reported} ≠ constraints 数量 {actual}，请对齐统计数字"
            )
        return self


class DeriveSource(BaseModel):
    """Provenance record linking a derived constraint back to its blueprint decision."""

    blueprint_id: str = Field(description="蓝图 ID，如 finance-bp-009")
    business_decision_id: str = Field(description="被派生的 business_decision ID 或名称")
    derivation_version: str = Field(
        default="sop-v2.3",
        description="派生所用的 SOP 版本",
    )


class DerivedConstraint(RawConstraint):
    """Constraint derived from a blueprint business_decision (Step 2.4).

    Extends RawConstraint with mandatory provenance so the origin of every
    derived constraint is always traceable.
    """

    derived_from: DeriveSource = Field(
        description="派生溯源：蓝图 ID + business_decision ID + SOP 版本",
    )


class MissingGapPair(BaseModel):
    """Paired constraints for a missing-gap business decision (Step 2.4).

    Schema-level enforcement of the boundary + remedy pattern: every missing
    gap must produce exactly one claim_boundary constraint and one corrective
    domain_rule / operational_lesson constraint.
    """

    boundary: DerivedConstraint = Field(
        description="claim_boundary 侧：must_not 假设框架已处理该功能",
    )
    remedy: DerivedConstraint = Field(
        description="domain_rule / operational_lesson 侧：具体可执行的补救方案",
    )

    @model_validator(mode="after")
    def validate_pair_semantics(self) -> MissingGapPair:
        if self.boundary.modality != "must_not":
            raise ValueError(
                f"boundary.modality 必须是 'must_not'，当前为 {self.boundary.modality!r}"
            )
        if self.boundary.constraint_kind != "claim_boundary":
            raise ValueError(
                f"boundary.constraint_kind 必须是 'claim_boundary'，当前为 {self.boundary.constraint_kind!r}"
            )
        if self.remedy.modality not in ("must", "should"):
            raise ValueError(
                f"remedy.modality 必须是 'must' 或 'should'，当前为 {self.remedy.modality!r}"
            )
        if self.remedy.constraint_kind not in ("domain_rule", "operational_lesson"):
            # Auto-correct instead of raising — LLM sometimes generates
            # architecture_guardrail for remedy, which is semantically close
            # to domain_rule. This avoids L1→L2→L3 cascade.
            self.remedy.constraint_kind = "domain_rule"
        return self


class DeriveExtractionResult(BaseModel):
    """Full output of Step 2.4: business-decision derivation.

    Separates derived constraints by source BD type so downstream pipeline
    steps can audit coverage per type without re-parsing.
    """

    rc_constraints: list[DerivedConstraint] = Field(
        default_factory=list,
        description="RC（监管规则）→ domain_rule 约束",
    )
    ba_constraints: list[DerivedConstraint] = Field(
        default_factory=list,
        description="BA（业务假设）→ operational_lesson 约束",
    )
    m_constraints: list[DerivedConstraint] = Field(
        default_factory=list,
        description="M（数学/模型选择）→ domain_rule / architecture_guardrail 约束",
    )
    b_constraints: list[DerivedConstraint] = Field(
        default_factory=list,
        description="B（业务决策）→ domain_rule / architecture_guardrail 约束",
    )
    missing_gap_pairs: list[MissingGapPair] = Field(
        default_factory=list,
        description="missing gap → 双联约束对（boundary + remedy）",
    )
    skipped_decisions: list[str] = Field(
        default_factory=list,
        description="跳过派生的 business_decision ID（纯技术选择 T / 无影响 DK 等）",
    )


class AuditSource(BaseModel):
    """Provenance record for audit-finding-derived constraints (Step 2.5)."""

    source: str = Field(description="审计来源，如 'audit_checklist_summary'")
    item: str = Field(description="审计项名称或 ID")
    sop_version: str = Field(default="sop-v2.2", description="SOP 版本")


class AuditConstraint(RawConstraint):
    """Constraint derived from an audit finding (Step 2.5).

    Uses AuditSource for provenance instead of DeriveSource, since audit
    constraints originate from checklist findings, not business decisions.
    """

    derived_from: AuditSource = Field(
        description="审计溯源：来源 + 审计项 + SOP 版本",
    )


class AuditConstraintResult(BaseModel):
    """Output of Step 2.5: converting audit-checklist findings to constraints.

    Only High/Critical findings are converted; warnings and passes are skipped.
    """

    constraints: list[AuditConstraint] = Field(
        default_factory=list,
        description="审计发现转化后的约束列表",
    )
    skipped_items: list[str] = Field(
        default_factory=list,
        description="跳过转化的审计项（⚠️/✅ 或已被 Step 2.4 覆盖）",
    )


# ── v2.1 Resource + Synthesis schemas ──


class ExternalService(BaseModel):
    """An external API, data source, or service used by the project."""

    name: str = Field(description="服务/工具名称")
    type: str = Field(
        default="", description="data_api / broker_api / storage_backend / transformer"
    )
    usage: str = Field(min_length=5, description="用途说明")
    install: str = Field(default="", description="安装命令，如 pip install xxx")
    api_example: str = Field(default="", description="最小可运行代码示例")
    known_issues: list[str] = Field(default_factory=list, description="已知陷阱/限制")
    fit_for: list[str] = Field(default_factory=list, description="适用场景")
    not_fit_for: list[str] = Field(default_factory=list, description="不适用场景")
    required: bool = Field(default=True, description="是否必选")
    source_stage_id: str = Field(default="", description="来自哪个 stage 的 replaceable_point")


class Dependency(BaseModel):
    """A Python package dependency."""

    package: str = Field(description="包名")
    version: str = Field(default="", description="版本约束，如 >=1.5.0")
    usage: str = Field(default="", description="用途说明")
    install: str = Field(default="", description="安装命令")
    critical: bool = Field(default=False, description="缺失则系统完全不能运行")


class Infrastructure(BaseModel):
    """Infrastructure requirement (storage, cache, etc.)."""

    type: str = Field(description="local_file_system / database / cache / api_endpoint")
    path: str = Field(default="", description="路径")
    cache_path: str = Field(default="", description="缓存路径")
    note: str = Field(default="", description="备注")


class OptionalResource(BaseModel):
    """An optional tool/library needed only in specific scenarios."""

    name: str = Field(description="资源名称")
    install: str = Field(default="", description="安装命令")
    when: str = Field(default="", description="何时需要")


class ResourceExtractionResult(BaseModel):
    """Output of con_extract_resources: descriptive resource inventory."""

    external_services: list[ExternalService] = Field(default_factory=list)
    dependencies: list[Dependency] = Field(default_factory=list)
    infrastructure: list[Infrastructure] = Field(default_factory=list)
    optional: list[OptionalResource] = Field(default_factory=list)


class SynthesizedConstraint(BaseModel):
    """A single constraint reviewed during synthesis, possibly with upgraded kind."""

    original_index: int = Field(description="在 merged list 中的原始索引")
    constraint_kind: Literal[
        "domain_rule",
        "resource_boundary",
        "operational_lesson",
        "architecture_guardrail",
        "claim_boundary",
        "rationalization_guard",
    ] = Field(description="审查后的 constraint_kind（可能已升级）")
    severity: Literal["fatal", "high", "medium", "low"] = Field(description="审查后的 severity")
    upgrade_reason: str = Field(default="", description="如果 kind 被修改，说明理由")


class ConstraintSynthesisResult(BaseModel):
    """Output of con_constraint_synthesis: kind rebalance + severity calibration."""

    reviewed_constraints: list[SynthesizedConstraint] = Field(
        description="所有需要修改 kind/severity 的约束条目"
    )
    rebalance_actions: list[str] = Field(
        default_factory=list, description="执行的 rebalance 操作摘要"
    )
