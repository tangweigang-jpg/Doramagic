"""编排层模型 — Phase Runner。"""

from __future__ import annotations

from typing import Optional, Literal

from pydantic import BaseModel, Field


class RunnerConfig(BaseModel):
    max_projects: int = Field(default=5, ge=1, le=7)
    enable_stage15: bool = True
    enable_api_enrichment: bool = True
    max_revise_loops: int = Field(default=2, ge=0, le=3)
    allow_degraded_delivery: bool = False


class RequestInput(BaseModel):
    raw_input: Optional[str] = None
    need_profile_path: Optional[str] = None


class PhaseRunnerInput(BaseModel):
    schema_version: str = "dm.phase-runner-input.v1"
    request: RequestInput
    config: RunnerConfig


class PhaseStatus(BaseModel):
    phase: Literal["A", "B", "C", "D", "E", "F", "G", "H"]
    status: Literal["ok", "degraded", "blocked", "skipped"]
    artifact_paths: list[str] = []
    notes: list[str] = []


class DeliveryBundleManifest(BaseModel):
    skill_md_path: str
    readme_md_path: str
    provenance_md_path: str
    limitations_md_path: str
    validation_report_path: str


class PhaseRunnerOutput(BaseModel):
    schema_version: str = "dm.phase-runner-output.v1"
    run_id: str
    phases: list[PhaseStatus]
    delivery_bundle: Optional[DeliveryBundleManifest] = None
    final_status: Literal["PASS", "REVISE", "BLOCKED"]
