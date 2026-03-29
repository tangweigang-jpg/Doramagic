"""Worker contracts for v12.1.1 fan-out extraction.

RepoWorkerContext  -- isolated context per worker
RepoExtractionEnvelope -- standardized fan-in format
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from doramagic_contracts.envelope import RunMetrics


class RepoExtractionEnvelope(BaseModel):
    """Standardized extraction output from one worker.

    Synthesis consumes envelopes, not raw worker state.
    """

    schema_version: str = "dm.repo-envelope.v1"

    # Identity
    worker_id: str
    repo_name: str
    repo_url: str
    repo_type: Literal["TOOL", "FRAMEWORK", "CATALOG"] = "TOOL"

    # Extraction results
    design_philosophy: str | None = None
    mental_model: str | None = None
    why_decisions: list[dict] = []
    unsaid_traps: list[dict] = []
    feature_inventory: list[str] = []

    # Codex fields
    repo_facts: dict = {}
    evidence_cards: list[dict] = []
    extraction_profile_used: str = ""
    failure_scope: str | None = None

    # Community signals
    community_signals: list[dict] = []

    # Quality metrics
    extraction_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence_count: int = Field(default=0, ge=0)

    # Run metrics (individual fields kept for backward compat)
    wall_time_ms: int = Field(default=0, ge=0)
    llm_calls: int = Field(default=0, ge=0)
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)

    # Composite metrics (Codex style)
    metrics: RunMetrics | None = None

    # Status
    status: Literal["ok", "degraded", "failed"] = "ok"
    warnings: list[str] = []

    # DSD metrics
    dsd_metrics: dict | None = None


class CollectionResult(BaseModel):
    """Fan-in result from EnvelopeCollector."""

    schema_version: str = "dm.collection-result.v1"
    qualified_envelopes: list[RepoExtractionEnvelope] = []
    filtered_envelopes: list[RepoExtractionEnvelope] = []
    total_workers: int = 0
    successful_workers: int = 0
    qualified_workers: int = 0


class ExtractionAggregateContract(BaseModel):
    """Phase C -> Phase D contract: aggregated extraction results."""

    schema_version: str = "dm.extraction-aggregate.v1"
    repo_envelopes: list[RepoExtractionEnvelope] = []
    success_count: int = 0
    failed_count: int = 0
    coverage_matrix: dict = {}
    conflict_map: dict = {}
    ready_for_synthesis: bool = False
