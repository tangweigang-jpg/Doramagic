"""Agent state schema — artifact-backed persistence."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat()


class AgentPhaseState(BaseModel):
    """State of a single execution phase."""

    phase_name: str
    status: str = "pending"  # pending | running | completed | failed | skipped
    started_at: str | None = None
    completed_at: str | None = None
    iterations: int = 0
    tokens_used: int = 0
    artifacts: list[str] = Field(default_factory=list)  # artifact names produced
    error: str | None = None
    transition_reason: str = ""  # WHY this phase ended (for observability)


class AgentState(BaseModel):
    """Top-level agent state. Written to _runs/{bp_id}/_agent_state.json.

    Tracks the full lifecycle of one extraction run: which phases have run,
    which artifacts were produced, and cumulative resource consumption.
    Designed for atomic checkpoint writes so recovery is always safe.
    """

    version: str = "1.0"
    blueprint_id: str
    domain: str = "finance"
    repo_path: str = ""
    run_dir: str = ""  # path to _runs/{bp_id}/
    output_dir: str = ""  # path to knowledge/sources/{domain}/{bp_id}/
    blueprint_path: str = ""  # path to output/blueprint.yaml
    commit_hash: str = ""
    subdomain_labels: list[str] = Field(default_factory=list)
    current_pipeline: str = "blueprint"  # "blueprint" | "constraint"
    current_phase: str = ""
    phases: dict[str, AgentPhaseState] = Field(default_factory=dict)

    # Cumulative metrics
    total_tokens: int = 0
    total_llm_calls: int = 0
    started_at: str = ""
    last_checkpoint_at: str = ""

    # Transient data shared between phases (not checkpointed)
    extra: dict[str, Any] = Field(default_factory=dict, exclude=True)

    # ------------------------------------------------------------------ #
    # Phase lifecycle helpers                                              #
    # ------------------------------------------------------------------ #

    def is_phase_completed(self, phase_name: str) -> bool:
        """Return True if the named phase has status 'completed'."""
        phase = self.phases.get(phase_name)
        return phase is not None and phase.status == "completed"

    def mark_phase_running(self, phase_name: str) -> None:
        """Transition a phase to 'running', creating the record if absent."""
        if phase_name not in self.phases:
            self.phases[phase_name] = AgentPhaseState(phase_name=phase_name)
        phase = self.phases[phase_name]
        phase.status = "running"
        phase.started_at = _utcnow_iso()
        self.current_phase = phase_name
        self.last_checkpoint_at = _utcnow_iso()

    def mark_phase_completed(
        self,
        phase_name: str,
        *,
        iterations: int = 0,
        tokens: int = 0,
        artifacts: list[str] | None = None,
        transition_reason: str = "",
    ) -> None:
        """Mark a phase as completed and record final metrics.

        Args:
            phase_name: The phase being completed.
            iterations: How many agent loop iterations the phase consumed.
            tokens: LLM tokens consumed during this phase.
            artifacts: Names of artifact files produced (relative to run_dir).
            transition_reason: Human-readable explanation for why the phase ended.
        """
        if phase_name not in self.phases:
            self.phases[phase_name] = AgentPhaseState(phase_name=phase_name)
        phase = self.phases[phase_name]
        phase.status = "completed"
        phase.completed_at = _utcnow_iso()
        phase.iterations = iterations
        phase.tokens_used = tokens
        if artifacts:
            phase.artifacts = artifacts
        phase.transition_reason = transition_reason
        self.total_tokens += tokens
        self.last_checkpoint_at = _utcnow_iso()

    def mark_phase_failed(self, phase_name: str, error: str) -> None:
        """Mark a phase as failed with an error message."""
        if phase_name not in self.phases:
            self.phases[phase_name] = AgentPhaseState(phase_name=phase_name)
        phase = self.phases[phase_name]
        phase.status = "failed"
        phase.completed_at = _utcnow_iso()
        phase.error = error
        self.last_checkpoint_at = _utcnow_iso()

    # ------------------------------------------------------------------ #
    # Metric helpers                                                       #
    # ------------------------------------------------------------------ #

    def add_tokens(self, count: int) -> None:
        """Accumulate token usage across the entire run."""
        self.total_tokens += count
        self.last_checkpoint_at = _utcnow_iso()
