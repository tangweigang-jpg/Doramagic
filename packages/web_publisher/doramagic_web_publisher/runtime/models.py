"""Pydantic models for the pipeline runtime.

PhaseContext flows through all phases unchanged (each phase reads and may enrich it).
PhaseResult is what each phase writes into PhaseContext.results[phase_name].
ToolCall / ToolCallResult track individual LLM tool invocations.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Tool-use primitives
# ---------------------------------------------------------------------------


class ToolCall(BaseModel):
    """A single tool invocation requested by the LLM."""

    id: str
    name: str
    arguments: dict[str, Any]


class ToolCallResult(BaseModel):
    """Result of executing a tool call (we only have submit_* tools)."""

    tool_call_id: str
    tool_name: str
    output: str  # JSON string or human-readable


# ---------------------------------------------------------------------------
# Manifest — minimal info needed to locate Blueprint + seed
# ---------------------------------------------------------------------------


class PublishManifest(BaseModel):
    """Minimal manifest passed into the pipeline at startup."""

    slug: str = Field(..., description="Crystal slug (URL-safe identifier)")
    blueprint_id: str = Field(..., description="Blueprint ID e.g. 'bp-009'")
    blueprint_source: str = Field(..., description="GitHub owner/repo e.g. 'zvtvz/zvt'")
    blueprint_commit: str = Field(..., description="40-char commit hash")
    seed_path: str | None = Field(None, description="Absolute path to PRODUCTION.seed.md")
    crystal_ir_path: str | None = Field(None, description="Absolute path to crystal IR JSON/YAML")
    qa_manifest_path: str | None = Field(
        None, description="Absolute path to QA manifest (creator_proof source)"
    )


# ---------------------------------------------------------------------------
# Phase Result — typed output from each phase
# ---------------------------------------------------------------------------


class PhaseResult(BaseModel):
    """Output from a single pipeline phase, stored in PhaseContext.results."""

    phase_name: str
    success: bool = True
    fields: dict[str, Any] = Field(
        default_factory=dict,
        description="Phase-specific output fields, keyed by Package JSON field name",
    )
    error: str | None = None
    token_usage: dict[str, int] = Field(
        default_factory=dict,
        description="prompt_tokens / completion_tokens consumed",
    )
    iterations: int = Field(0, description="Number of tool-use loop iterations used")


# ---------------------------------------------------------------------------
# Phase Context — the shared state object passed through all phases
# ---------------------------------------------------------------------------


class PhaseContext(BaseModel):
    """Mutable context flowing through all pipeline phases.

    Populated progressively:
    - manifest is set at pipeline startup
    - blueprint / constraints / crystal_ir / seed_content loaded before phase 1
    - creator_proof loaded from QA manifest before phase 4
    - results accumulated as each phase completes
    """

    model_config = {"arbitrary_types_allowed": True}

    manifest: PublishManifest

    # ---- Loaded inputs (pre-filled before pipeline runs) ----
    blueprint: dict[str, Any] | None = Field(
        None, description="Blueprint YAML parsed to dict (or contracts Blueprint model)"
    )
    constraints: list[dict[str, Any]] = Field(
        default_factory=list,
        description=(
            "Constraint dicts from JSONL (severity fatal/critical/high, with evidence_refs)"
        ),
    )
    crystal_ir: dict[str, Any] = Field(
        default_factory=dict,
        description="Crystal IR dict (compiled product, English prose)",
    )
    seed_content: str = Field("", description="Full text of PRODUCTION.seed.md")
    creator_proof: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Creator proof entries read from QA manifest",
    )

    # ---- Phase outputs ----
    results: dict[str, PhaseResult] = Field(
        default_factory=dict,
        description="Keyed by phase name; each phase writes its PhaseResult here",
    )

    # ---- API error feedback (filled by Orchestrator before retry) ----
    api_errors_by_phase: dict[str, list[dict[str, str]]] = Field(
        default_factory=dict,
        description=(
            "Keyed by phase_name; value is list of error dicts from the Publish API. "
            "Example: {'evaluator': [{'gate': 'SEO-TITLE-LENGTH', 'message': '72 chars'}]}. "
            "Filled by Orchestrator before re-running a phase so the phase prompt can include "
            "a human-readable correction hint."
        ),
    )

    # ---- Pipeline metadata ----
    dry_run: bool = False
    mock_mode: bool = False

    def phase_fields(self, phase_name: str) -> dict[str, Any]:
        """Convenience: get the fields dict of a completed phase, or empty dict."""
        r = self.results.get(phase_name)
        return r.fields if r else {}

    def all_phase_fields(self) -> dict[str, Any]:
        """Merge all phase output fields into a single flat dict (later phases win)."""
        merged: dict[str, Any] = {}
        for result in self.results.values():
            merged.update(result.fields)
        return merged
