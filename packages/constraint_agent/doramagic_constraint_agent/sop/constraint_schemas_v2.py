"""Pydantic schemas for constraint extraction — Instructor three-level degradation.

Instructor uses tool_use to force LLM output that conforms to these schemas.
Used by SOP v2.2 steps 2.1–2.5 (stage/edge/global extraction, BD derivation,
audit conversion).

Import RawFallback from schemas_v5 rather than redefining it.
"""

from __future__ import annotations

from typing import Any, Literal

from doramagic_agent_core.core.fallback import RawFallback  # noqa: F401
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# MiniMax schema compatibility: force all fields to "required"
# ---------------------------------------------------------------------------


def _force_all_required(schema: dict[str, Any]) -> None:
    """Walk a JSON Schema and force ALL properties into required lists.

    MiniMax API doc: "所有字段或函数参数都必须指定为 required".
    Without this, MiniMax skips fields with defaults, causing persistent
    "Field required [type=missing]" validation failures.

    Applied via model_config.json_schema_extra on response models that
    go through Instructor structured calls to MiniMax.
    """
    if "properties" in schema:
        schema["required"] = sorted(schema["properties"].keys())
    # Recurse into property definitions
    for prop in schema.get("properties", {}).values():
        if isinstance(prop, dict):
            _force_all_required(prop)
    # Recurse into array items
    if isinstance(schema.get("items"), dict):
        _force_all_required(schema["items"])
    # Recurse into $defs (referenced sub-models)
    for defn in schema.get("$defs", {}).values():
        if isinstance(defn, dict):
            _force_all_required(defn)


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
    "try to",
    "consider",
    "be careful",
    "appropriate",
    "if possible",
    "as needed",
]


class RawConstraint(BaseModel):
    """Single constraint in flat format as produced by LLM extraction.

    Deliberately non-nested so Instructor can reliably coerce LLM output via
    tool_use without deep object construction failures.
    """

    when: str = Field(min_length=5, description="Trigger condition (coding-time perspective)")
    modality: _MODALITY = Field(
        description="Constraint polarity: must / must_not / should / should_not"
    )
    action: str = Field(min_length=5, description="Specific actionable behavior")
    consequence_kind: _CONSEQUENCE_KIND = Field(description="Consequence category")
    consequence_description: str = Field(
        min_length=20,
        description="Specific failure scenario when violated — NEVER just the consequence_kind word",
    )
    constraint_kind: _CONSTRAINT_KIND = Field(description="Constraint kind")
    severity: _SEVERITY = Field(description="Severity: fatal / high / medium / low")
    confidence_score: float = Field(ge=0.0, le=1.0, description="Confidence score 0.0-1.0")
    source_type: _SOURCE_TYPE = Field(description="Evidence source type")
    consensus: _CONSENSUS = Field(description="Community consensus level")
    freshness: _FRESHNESS = Field(description="Stability: stable / semi_stable / volatile")
    target_scope: _TARGET_SCOPE = Field(description="Scope: global / stage / edge")
    stage_ids: list[str] = Field(
        default_factory=list,
        description="Stage ID list, REQUIRED when target_scope=stage",
    )
    edge_ids: list[str] = Field(
        default_factory=list,
        description="Edge ID list for target_scope=edge",
    )
    evidence_summary: str = Field(
        min_length=5,
        description="Evidence summary; MUST contain file:line ref (colon-separated) except expert_reasoning",
    )
    machine_checkable: bool = Field(
        default=False,
        description="Whether verifiable via grep/regex/static analysis",
    )
    promote_to_acceptance: bool = Field(
        default=False,
        description="Whether to promote to acceptance criterion",
    )
    validation_threshold: str | None = Field(
        default=None,
        description=(
            "REQUIRED when machine_checkable=true AND severity=fatal. "
            "Format: grep/regex condition → PASS/FAIL/WARN. "
            "Example: 'macd_fast != 12 OR macd_slow != 26 → FAIL'"
        ),
    )
    # SOP v2.3: rationalization_guard specific field
    guard_pattern: dict | None = Field(
        default=None,
        description=(
            "Only for rationalization_guard. Format: {excuse, rebuttal, red_flags, violation_detector}"
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
        # Also maps BD types (RC/B/BA/M) that LLMs confuse with constraint_kind
        _BD_TYPE_TO_KIND = {
            # Single types
            "rc": "domain_rule",
            "b": "domain_rule",
            "ba": "operational_lesson",
            "m": "domain_rule",
            "t": "architecture_guardrail",
            "dk": "domain_rule",
            # Compound types (first type dominates the mapping)
            "b/rc": "domain_rule",
            "rc/b": "domain_rule",
            "rc/ba": "domain_rule",
            "m/ba": "domain_rule",
            "m/b": "domain_rule",
            "m/dk": "domain_rule",
            "b/ba": "operational_lesson",
            "ba/dk": "operational_lesson",
            "b/dk": "domain_rule",
            "b/m": "domain_rule",
            "rc/dk": "domain_rule",
            "t/b": "architecture_guardrail",
            "t/dk": "architecture_guardrail",
        }
        ck = data.get("constraint_kind")
        if isinstance(ck, str):
            normalized = ck.lower().strip().replace(" ", "_").replace("-", "_")
            # First check BD type mapping (con_derive confusion)
            if normalized in _BD_TYPE_TO_KIND:
                data["constraint_kind"] = _BD_TYPE_TO_KIND[normalized]
            elif normalized not in _VALID_CONSTRAINT_KINDS:
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
            raise ValueError(
                f"action contains vague words {found!r} — rewrite as specific actionable behavior"
            )
        return v

    @field_validator("evidence_summary")
    @classmethod
    def evidence_needs_ref(cls, v: str, info) -> str:
        source_type = (info.data or {}).get("source_type")
        if source_type and source_type != "expert_reasoning" and ":" not in v:
            raise ValueError(
                f"evidence_summary for source_type={source_type!r} MUST contain file:line "
                f"reference (with ':'), current value: {v!r}"
            )
        return v

    @model_validator(mode="after")
    def scope_stage_ids_check(self) -> RawConstraint:
        if self.target_scope == "stage" and not self.stage_ids:
            raise ValueError(
                "stage_ids MUST NOT be empty when target_scope='stage' — fill in the corresponding stage IDs"
            )
        return self


class ConstraintExtractionResult(BaseModel):
    """Extraction result for a single stage / edge / global unit.

    Instructor returns this after the extraction + omission-check passes.
    """

    constraints: list[RawConstraint] = Field(
        description="All extracted constraints",
    )
    coverage_report: dict[str, int] = Field(
        default_factory=dict,
        description="Count by constraint_kind; keys MUST be valid constraint_kind values",
    )
    missed_hints: list[str] = Field(
        default_factory=list,
        description="acceptance_hints not covered by constraints (for quality audit)",
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

    blueprint_id: str = Field(description="Blueprint ID, e.g. finance-bp-009")
    business_decision_id: str = Field(description="Source business_decision ID or name")
    derivation_version: str = Field(
        default="sop-v2.3",
        description="SOP version used for derivation",
    )


class DerivedConstraint(RawConstraint):
    """Constraint derived from a blueprint business_decision (Step 2.4).

    Extends RawConstraint with mandatory provenance. Overrides several fields
    with sensible defaults because LLMs frequently omit them in the complex
    DeriveExtractionResult schema (14/14 chunks failed on bp-070 without defaults).
    """

    # Override fields that LLMs commonly omit in derive context
    confidence_score: float = Field(
        default=0.7, ge=0.0, le=1.0, description="Confidence score 0.0-1.0"
    )
    evidence_summary: str = Field(
        default="See blueprint business_decision", description="Evidence summary"
    )
    consensus: _CONSENSUS = Field(default="strong", description="Community consensus level")
    freshness: _FRESHNESS = Field(default="stable", description="Stability")
    machine_checkable: bool = Field(default=False, description="Whether verifiable via grep/regex")
    promote_to_acceptance: bool = Field(
        default=False, description="Whether to promote to acceptance criterion"
    )

    derived_from: DeriveSource = Field(
        description="Derivation provenance: blueprint ID + business_decision ID + SOP version",
    )

    @model_validator(mode="before")
    @classmethod
    def _backfill_stage_from_bd(cls, data: Any) -> Any:
        """Try to recover stage_ids from derived_from context before validation."""
        if not isinstance(data, dict):
            return data
        # If the BD name hints at a stage, backfill stage_ids
        derived = data.get("derived_from")
        if isinstance(derived, dict):
            bd_id = derived.get("business_decision_id", "")
            # Common pattern: BD names contain stage hints like "filing_*", "xbrl_*"
            if bd_id and not data.get("stage_ids"):
                data.setdefault("stage_ids", [])
        return data

    @model_validator(mode="after")
    def scope_stage_ids_check(self) -> DerivedConstraint:
        """Override: auto-correct stage+empty→global instead of raising.

        GLM-5 consistently generates target_scope="stage" without stage_ids
        in derived constraints (7/7 chunks on bp-070). Fallback to global
        rather than failing — downstream enrichment P10 can re-assign stage_ids
        from the blueprint's stage mapping.
        """
        if self.target_scope == "stage" and not self.stage_ids:
            self.target_scope = "global"
        return self

    @field_validator("action")
    @classmethod
    def action_no_vague_words(cls, v: str) -> str:
        """Override: derived constraints are advisory — relax vague word check."""
        hard_block = ["try to", "be careful", "if possible"]
        found = [w for w in hard_block if w in v.lower()]
        if found:
            raise ValueError(
                f"action contains vague words {found!r} — rewrite as specific actionable behavior"
            )
        return v


class MissingGapPair(BaseModel):
    """Paired constraints for a missing-gap business decision (Step 2.4).

    Schema-level enforcement of the boundary + remedy pattern: every missing
    gap must produce exactly one claim_boundary constraint and one corrective
    domain_rule / operational_lesson constraint.
    """

    boundary: DerivedConstraint = Field(
        description="claim_boundary side: must_not assume the framework handles this",
    )
    remedy: DerivedConstraint = Field(
        description="domain_rule / operational_lesson side: specific actionable remedy",
    )

    @model_validator(mode="after")
    def validate_pair_semantics(self) -> MissingGapPair:
        # Auto-correct instead of raising — avoid L1→L2→L3 cascade
        if self.boundary.modality != "must_not":
            self.boundary.modality = "must_not"
        if self.boundary.constraint_kind != "claim_boundary":
            self.boundary.constraint_kind = "claim_boundary"
        if self.boundary.source_type != "code_analysis":
            self.boundary.source_type = "code_analysis"
        if self.remedy.modality not in ("must", "should"):
            self.remedy.modality = "must"
        if self.remedy.constraint_kind not in ("domain_rule", "operational_lesson"):
            self.remedy.constraint_kind = "domain_rule"
        if self.remedy.source_type not in ("expert_reasoning", "code_analysis"):
            self.remedy.source_type = "expert_reasoning"
        # Ensure both sides share the same derived_from provenance
        if (
            self.boundary.derived_from
            and self.remedy.derived_from
            and self.remedy.derived_from.business_decision_id
            != self.boundary.derived_from.business_decision_id
        ):
            self.remedy.derived_from.business_decision_id = (
                self.boundary.derived_from.business_decision_id
            )
        return self


class AuditSource(BaseModel):
    """Provenance record for audit-finding-derived constraints (Step 2.5)."""

    source: str = Field(description="Audit source, e.g. 'audit_checklist_summary'")
    item: str = Field(description="Audit item name or ID")
    sop_version: str = Field(default="sop-v2.2", description="SOP 版本")


class AuditConstraint(RawConstraint):
    """Constraint derived from an audit finding (Step 2.5).

    Uses AuditSource for provenance instead of DeriveSource. Overrides fields
    with sensible defaults (same rationale as DerivedConstraint).
    """

    # Override fields commonly omitted by LLMs in audit context
    confidence_score: float = Field(default=0.8, ge=0.0, le=1.0, description="Confidence score")
    consensus: _CONSENSUS = Field(default="strong", description="Community consensus level")
    freshness: _FRESHNESS = Field(default="stable", description="Stability")

    derived_from: AuditSource = Field(
        description="Audit provenance: source + audit item + SOP version",
    )


class AuditConstraintResult(BaseModel):
    """Output of Step 2.5: converting audit-checklist findings to constraints.

    Only High/Critical findings are converted; warnings and passes are skipped.
    """

    model_config = ConfigDict(json_schema_extra=_force_all_required)

    constraints: list[AuditConstraint] = Field(
        default_factory=list,
        description="Constraints converted from audit findings",
    )
    skipped_items: list[str] = Field(
        default_factory=list,
        description="Audit items skipped (⚠️/✅ level, or already covered by Step 2.4)",
    )


# ── v2.1 Resource + Synthesis schemas ──


class ExternalService(BaseModel):
    """An external API, data source, or service used by the project."""

    name: str = Field(description="Service/tool name")
    type: str = Field(
        default="", description="data_api / broker_api / storage_backend / transformer"
    )
    usage: str = Field(min_length=5, description="Usage description")
    install: str = Field(default="", description="Install command, e.g. pip install xxx")
    api_example: str = Field(default="", description="Minimal runnable code example")
    known_issues: list[str] = Field(default_factory=list, description="Known pitfalls/limitations")
    fit_for: list[str] = Field(default_factory=list, description="Suitable scenarios")
    not_fit_for: list[str] = Field(default_factory=list, description="Unsuitable scenarios")
    required: bool = Field(default=True, description="Whether required")
    source_stage_id: str = Field(default="", description="From which stage's replaceable_point")


class Dependency(BaseModel):
    """A Python package dependency."""

    package: str = Field(description="Package name")
    version: str = Field(default="", description="Version constraint, e.g. >=1.5.0")
    usage: str = Field(default="", description="Usage description")
    install: str = Field(default="", description="Install command")
    critical: bool = Field(default=False, description="System cannot run without this")


class Infrastructure(BaseModel):
    """Infrastructure requirement (storage, cache, etc.)."""

    type: str = Field(description="local_file_system / database / cache / api_endpoint")
    path: str = Field(default="", description="Path")
    cache_path: str = Field(default="", description="Cache path")
    note: str = Field(default="", description="Note")


class OptionalResource(BaseModel):
    """An optional tool/library needed only in specific scenarios."""

    name: str = Field(description="Resource name")
    install: str = Field(default="", description="Install command")
    when: str = Field(default="", description="When needed")


class ResourceExtractionResult(BaseModel):
    """Output of con_extract_resources: descriptive resource inventory."""

    external_services: list[ExternalService] = Field(default_factory=list)
    dependencies: list[Dependency] = Field(default_factory=list)
    infrastructure: list[Infrastructure] = Field(default_factory=list)
    optional: list[OptionalResource] = Field(default_factory=list)


class SynthesizedConstraint(BaseModel):
    """A single constraint reviewed during synthesis, possibly with upgraded kind."""

    original_index: int = Field(description="Original index in the merged list")
    constraint_kind: Literal[
        "domain_rule",
        "resource_boundary",
        "operational_lesson",
        "architecture_guardrail",
        "claim_boundary",
        "rationalization_guard",
    ] = Field(description="Reviewed constraint_kind (may have been upgraded)")
    severity: Literal["fatal", "high", "medium", "low"] = Field(description="Reviewed severity")
    upgrade_reason: str = Field(default="", description="Reason if kind was modified")


class ConstraintSynthesisResult(BaseModel):
    """Output of con_constraint_synthesis: kind rebalance + severity calibration."""

    model_config = ConfigDict(json_schema_extra=_force_all_required)

    reviewed_constraints: list[SynthesizedConstraint] = Field(
        description="All constraints requiring kind/severity modification"
    )
    rebalance_actions: list[str] = Field(
        default_factory=list, description="Summary of rebalance operations performed"
    )
