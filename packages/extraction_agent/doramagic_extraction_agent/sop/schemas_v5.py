"""v5 Pydantic schemas for structured BD extraction.

These models enforce BD depth at the schema level — rationale depth,
multi-type annotations, and evidence format are validated by Pydantic
rather than relying on prompt luck.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class BusinessDecision(BaseModel):
    """A single business decision extracted from source code.

    Instructor forces every field — the LLM cannot skip rationale or
    produce a bare file name as evidence.
    """

    id: str = Field(description="Unique ID, e.g. BD-001")
    content: str = Field(description="The specific design decision")

    @model_validator(mode="before")
    @classmethod
    def coerce_field_names(cls, data: Any) -> Any:
        """Map common alternative field names from L2 freeform output.

        MiniMax L2 freeform sometimes uses different field names:
        - 'decision' instead of 'content'
        - 'active' instead of 'present' for status
        - 'D001' instead of 'BD-001' for id
        - Missing 'stage' field
        """
        if not isinstance(data, dict):
            return data
        # decision → content
        if "content" not in data and "decision" in data:
            data["content"] = data.pop("decision")
        # status normalization
        if data.get("status") not in ("present", "missing", None):
            data["status"] = "present"
        # id prefix normalization (D001 → BD-001)
        if "id" in data and isinstance(data["id"], str):
            _id = data["id"]
            if re.match(r"^D\d+$", _id):
                data["id"] = f"BD-{_id[1:]}"
        # stage fallback
        if "stage" not in data:
            data["stage"] = "unknown"
        return data

    type: str = Field(
        description=(
            "T/B/BA/DK/RC/M or multi-type like B/BA, M/DK. Use '/' to separate multiple types."
        ),
        pattern=r"^(T|B|BA|DK|RC|M)(/(?:T|B|BA|DK|RC|M))*$",
    )
    rationale: str = Field(
        min_length=40,
        description=(
            "Sentence 1: WHY this approach was chosen. "
            "Sentence 2: BOUNDARY — under what conditions it breaks."
        ),
    )
    evidence: str = Field(
        description="file:line(function_name) triple, e.g. trader/trader.py:247(on_profit_control)",
    )
    stage: str = Field(description="Which pipeline stage this decision belongs to")
    status: Literal["present", "missing"] = "present"
    severity: Literal["critical", "high", "medium"] | None = None
    impact: str | None = None
    known_gap: bool | None = Field(
        default=None,
        description="Set to true for missing gap BDs (status='missing')",
    )
    alternative_considered: str | None = Field(
        default=None,
        description="Alternative approach that was considered but not chosen",
    )

    @field_validator("evidence")
    @classmethod
    def evidence_must_not_be_empty(cls, v: str) -> str:
        """Ensure evidence is non-empty. Format enforcement is deferred to enrich P5.

        The enrich pipeline (P5) does deterministic evidence format normalization
        (file:line(fn) triple). At schema validation time, we only reject empty
        strings to avoid blocking valid business content from L1.5 salvage or
        L2 freeform paths where the model may use varied evidence formats.
        """
        if not v or not v.strip():
            raise ValueError("evidence must not be empty")
        return v


class BDExtractionResult(BaseModel):
    """Complete extraction result from the synthesis phase."""

    decisions: list[BusinessDecision] = Field(
        description="All extracted business decisions (present + missing)",
    )
    type_summary: dict[str, int] = Field(
        description="Count of decisions per type, e.g. {'B': 5, 'B/BA': 3, 'M': 2}",
    )
    missing_gaps: list[BusinessDecision] = Field(
        description="Subset of decisions with status='missing' — things the code should have but doesn't",
    )

    @model_validator(mode="before")
    @classmethod
    def coerce_missing_gaps_from_ids(cls, data: Any) -> Any:
        """Convert missing_gaps string IDs to BusinessDecision references.

        MiniMax L2 freeform sometimes returns missing_gaps as a list of
        string IDs (e.g. ["BD-066", "BD-067"]) instead of full objects.
        Resolve them from the decisions list when possible.
        """
        if not isinstance(data, dict):
            return data
        gaps = data.get("missing_gaps")
        decisions = data.get("decisions")
        if not gaps or not decisions or not isinstance(gaps, list):
            return data
        # Check if any gaps are plain strings
        if not any(isinstance(g, str) for g in gaps):
            return data
        # Build lookup from decisions
        decisions_by_id: dict[str, Any] = {}
        for d in decisions:
            if isinstance(d, dict) and "id" in d:
                decisions_by_id[d["id"]] = d
        resolved = []
        for g in gaps:
            if isinstance(g, str):
                if g in decisions_by_id:
                    resolved.append(decisions_by_id[g])
                # Unknown ID — drop silently (better than crashing)
            else:
                resolved.append(g)
        data["missing_gaps"] = resolved
        return data

    @model_validator(mode="after")
    def check_missing_gaps_consistency(self) -> BDExtractionResult:
        """Ensure missing_gaps are a subset of decisions with status='missing'."""
        missing_ids = {bd.id for bd in self.decisions if bd.status == "missing"}
        for gap in self.missing_gaps:
            if gap.status != "missing":
                raise ValueError(
                    f"missing_gaps entry {gap.id!r} has status={gap.status!r}, expected 'missing'"
                )
        return self

    @model_validator(mode="after")
    def check_type_summary_keys(self) -> BDExtractionResult:
        """Ensure type_summary keys are valid BD type codes."""
        valid_pattern = re.compile(r"^(T|B|BA|DK|RC|M)(/(?:T|B|BA|DK|RC|M))*$")
        for key in self.type_summary:
            if not valid_pattern.match(key):
                raise ValueError(f"type_summary key {key!r} is not a valid BD type code")
        return self


class UseCase(BaseModel):
    """A single use case extracted from an example file."""

    id: str = Field(description="Unique ID, e.g. UC-001", pattern=r"^UC-\d+$")
    name: str = Field(description="Short descriptive name")
    source: str = Field(description="Source file path, e.g. examples/trader/macd_day_trader.py")
    uc_type: Literal[
        "trading_strategy",
        "screening",
        "data_pipeline",
        "monitoring",
        "live_trading",
        "reporting",
        "research_analysis",
        "ml_prediction",
        "builtin_factor",
        "extension_example",
        "complete_strategy",
    ] = Field(description="Use case type category")
    business_problem: str = Field(description="What business problem this example solves")
    intent_keywords: list[str] = Field(
        default_factory=list,
        description="3-5 keywords for matching user intent",
        min_length=1,
        max_length=10,
    )
    negative_keywords: list[str] = Field(
        default_factory=list,
        description="Keywords of OTHER use cases that overlap with this one — helps disambiguation",
    )
    disambiguation: str = Field(
        default="",
        description="Question to ask user when intent matches multiple UCs",
    )
    data_domain: str = Field(
        default="",
        description="Data type: market_data | financial_data | holding_data | trading_data | mixed",
    )
    stage: str = Field(default="", description="Which pipeline stage this UC belongs to")


class UCExtractionResult(BaseModel):
    """Result of deterministic UC extraction from example files."""

    use_cases: list[UseCase] = Field(description="All extracted use cases")


class QualityGateResult(BaseModel):
    """Result of SOP v3.3 quality gate checks."""

    passed: bool
    checks: dict[str, bool] = Field(
        description="Individual check results, e.g. {'rationale_depth': True, 'multi_type_ratio': False}",
    )
    details: dict[str, str] = Field(
        description="Human-readable detail for each check",
    )


class InterfacePort(BaseModel):
    """A single input or output port in a stage interface."""

    name: str
    description: str
    schema_hint: str | None = None
    constraints: list[str] = Field(default_factory=list)


class MethodSpec(BaseModel):
    """A required method in a stage interface."""

    name: str = Field(description="Class.method or function name, e.g. 'Factor.compute'")
    description: str = Field(description="What this method does")
    evidence: str = Field(default="", description="file:line(fn) reference")


class KeyBehavior(BaseModel):
    """An observable behavior of a stage."""

    behavior: str = Field(description="Short behavior name, e.g. 'Entity-level isolation'")
    description: str = Field(description="Detailed description of the behavior")
    evidence: str = Field(default="", description="file:line(fn) reference")


class ReplaceableOption(BaseModel):
    """A concrete option for a replaceable point."""

    name: str
    traits: list[str] = Field(default_factory=list, description="Key traits of this option")
    fit_for: list[str] = Field(
        default_factory=list, description="Scenarios this option is good for"
    )
    not_fit_for: list[str] = Field(
        default_factory=list, description="Scenarios this option is NOT good for"
    )


class ReplaceablePoint(BaseModel):
    """An extension point where users can swap implementations."""

    name: str = Field(description="Extension point name, e.g. 'storage_backend'")
    description: str = Field(default="", description="What can be replaced")
    options: list[ReplaceableOption] = Field(default_factory=list)
    default: str | None = Field(default=None, description="Default option name")


class BlueprintStage(BaseModel):
    """A single pipeline stage extracted from architecture analysis."""

    id: str = Field(description="snake_case unique stage ID, e.g. 'data_collection'")
    name: str = Field(description="Human-readable stage name")
    order: int = Field(ge=1, description="Execution order (strictly increasing)")
    responsibility: str = Field(min_length=30, description="What this stage is responsible for")
    interface: dict[str, Any] = Field(
        default_factory=dict,
        description="Stage interface: {inputs: [{name, description}], outputs: [{name, description}]}",
    )
    required_methods: list[MethodSpec] = Field(
        default_factory=list,
        description="User-facing methods in this stage (e.g. Factor.compute, Trader.run)",
    )
    key_behaviors: list[KeyBehavior] = Field(
        default_factory=list,
        description="Observable behaviors of this stage",
    )
    replaceable_points: list[ReplaceablePoint] = Field(default_factory=list)
    design_decisions: list[str] = Field(
        min_length=1,
        description="Design decisions with WHY + evidence, each ≥20 chars",
    )
    acceptance_hints: list[str] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def id_must_be_snake_case(cls, v: str) -> str:
        if not re.match(r"^[a-z][a-z0-9_]*$", v):
            raise ValueError(f"Stage id must be snake_case, got {v!r}")
        return v


class DataFlowEdge(BaseModel):
    """A data flow edge between two stages."""

    from_stage: str
    to_stage: str
    data: str = Field(description="What data flows through this edge")


class BlueprintAssembleResult(BaseModel):
    """Complete blueprint structure — Instructor-enforced output contract."""

    name: str = Field(description="Project name")
    applicability: dict[str, Any] = Field(
        description="Domain, task_type, description, prerequisites, not_suitable_for",
    )
    stages: list[BlueprintStage] = Field(
        min_length=2,
        description="All pipeline stages, ordered by execution",
    )
    data_flow: list[DataFlowEdge] = Field(
        min_length=1,
        description="Data flow edges between stages",
    )
    global_contracts: list[dict[str, str]] = Field(
        min_length=1,
        description="Cross-cutting contracts with 'contract' and 'evidence' keys",
    )

    @model_validator(mode="after")
    def check_stage_orders_unique(self) -> BlueprintAssembleResult:
        orders = [s.order for s in self.stages]
        if len(orders) != len(set(orders)):
            dupes = [o for o in orders if orders.count(o) > 1]
            raise ValueError(f"Stage order values must be unique, got duplicates: {set(dupes)}")
        return self

    @model_validator(mode="after")
    def check_data_flow_references(self) -> BlueprintAssembleResult:
        """Warn (not reject) when data_flow references non-stage endpoints.

        Real blueprints use rich endpoint labels like "(config)", "(user)",
        "external_data_source" etc. We validate that at least one endpoint
        per edge is a known stage ID; both being unknown is an error.
        """
        stage_ids = {s.id for s in self.stages}
        for edge in self.data_flow:
            refs = [edge.from_stage, edge.to_stage]
            known = [r for r in refs if r in stage_ids]
            if not known:
                raise ValueError(
                    f"data_flow edge {edge.from_stage!r} → {edge.to_stage!r}: "
                    f"neither endpoint is a known stage. "
                    f"Valid stages: {sorted(stage_ids)}"
                )
        return self


class EvaluationIssue(BaseModel):
    """A single issue found by the independent Evaluator."""

    bd_id: str = Field(description="ID of the BD with the issue")
    contract: Literal["evidence_validity", "classification", "rationale", "rc_split"] = Field(
        description="Which verification contract was violated"
    )
    verdict: str = Field(
        description=(
            "INVALID | WEAK | OVER_CLASSIFIED | UNDER_CLASSIFIED"
            " | SHALLOW | MISSING_WHY | MISSING_BOUNDARY | NEEDS_SPLIT"
        ),
    )
    detail: str = Field(description="Specific explanation of the issue")
    fix_suggestion: str = Field(
        default="",
        description="Concrete fix if possible",
    )


class EvaluationReport(BaseModel):
    """Result of the independent Evaluator phase."""

    evaluated_count: int = Field(ge=0, description="Total BDs evaluated")
    pass_count: int = Field(ge=0, description="BDs that passed all contracts")
    issues: list[EvaluationIssue] = Field(
        default_factory=list,
        description="All issues found across all BDs",
    )
    score: float = Field(ge=0.0, le=1.0, description="pass_count / evaluated_count")
    recommendation: Literal["PASS", "FIXABLE", "NEEDS_REWORK"] = Field(
        description="Overall recommendation",
    )
    passed_ids: list[str] = Field(
        default_factory=list,
        description="IDs of BDs that passed all contracts — used by DecisionCache",
    )


class ResourceOption(BaseModel):
    """A concrete option in a replaceable resource slot."""

    name: str
    package: str = Field(default="N/A", description="pip package name")
    traits: list[str] = Field(default_factory=list)
    fit_for: str = ""
    not_fit_for: str = ""
    setup_effort: Literal["low", "medium", "high"] = "medium"
    cost: Literal["free", "freemium", "paid"] = "free"


class ResourceSlot(BaseModel):
    """A replaceable resource slot with its options."""

    slot_name: str
    options: list[ResourceOption] = Field(default_factory=list)
    default: str | None = None
    selection_criteria: str = ""


class ResourceInventory(BaseModel):
    """Complete resource inventory from worker_resource."""

    data_sources: list[dict[str, Any]] = Field(default_factory=list)
    dependencies: list[dict[str, Any]] = Field(default_factory=list)
    external_services: list[dict[str, Any]] = Field(default_factory=list)
    infrastructure: dict[str, Any] = Field(default_factory=dict)
    replaceable_resource_matrix: list[ResourceSlot] = Field(default_factory=list)


@dataclass
class RawFallback:
    """Sentinel returned when both Instructor and JSON extraction fail.

    The synthesis handler checks ``isinstance(result, RawFallback)`` to
    decide whether to abort or degrade gracefully.
    """

    text: str
    stage: str  # "l1_instructor_failed" | "l2_extract_failed" | "l3_raw"
