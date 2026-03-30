"""Run event schema for v12.1.1 EventBus.

Events are written to run_events.jsonl as append-only JSONL.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

EventType = Literal[
    # Run lifecycle
    "run_started",
    "run_completed",
    "run_failed",
    # Phase lifecycle
    "phase_started",
    "phase_completed",
    "phase_skipped",
    "phase_degraded",
    # Routing
    "routing_decision",
    # Worker lifecycle (PHASE_C internal)
    "worker_started",
    "worker_progress",
    "worker_completed",
    "worker_failed",
    "sub_progress",
    # Quality
    "quality_gate_result",
    "revise_triggered",
    # Budget
    "budget_warning",
    "budget_exceeded",
    # User interaction
    "clarification_asked",
    "clarification_received",
]


class RunEvent(BaseModel):
    """Single event in run_events.jsonl."""

    schema_version: str = "dm.run-event.v1"
    ts: str  # ISO 8601 timestamp
    run_id: str
    seq: int  # monotonically increasing sequence number

    event_type: str  # one of EventType literals
    phase: str | None = None
    worker_id: str | None = None

    message: str  # human-readable description

    meta: dict = {}  # structured metadata (varies by event_type)

    elapsed_ms: int = Field(default=0, ge=0)
    percent_complete: int = Field(default=0, ge=0, le=100)
