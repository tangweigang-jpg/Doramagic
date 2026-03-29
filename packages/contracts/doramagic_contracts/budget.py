"""Budget tracking models for the dual-layer architecture."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PhaseAllocation(BaseModel):
    """Budget allocation for a single phase."""

    phase: str
    percent: float = Field(ge=0, le=100)


class BudgetPolicy(BaseModel):
    """Total run budget and per-phase allocation."""

    schema_version: str = "dm.budget-policy.v1"
    max_cost_usd: float = Field(default=2.50, ge=0)
    max_tokens: int = Field(default=200_000, ge=0)
    max_llm_calls: int = Field(default=50, ge=0)
    max_duration_ms: int = Field(default=1_800_000, ge=0)  # 30 min
    overshoot_warning_pct: float = Field(default=120.0)
    phase_allocations: list[PhaseAllocation] = Field(
        default_factory=lambda: [
            PhaseAllocation(phase="A", percent=5),
            PhaseAllocation(phase="B", percent=5),
            PhaseAllocation(phase="C", percent=20),
            PhaseAllocation(phase="D", percent=40),
            PhaseAllocation(phase="E", percent=10),
            PhaseAllocation(phase="F", percent=5),
            PhaseAllocation(phase="G", percent=2),
            PhaseAllocation(phase="reserve", percent=13),
        ]
    )

    def allocation_for(self, phase: str) -> float:
        """Return the dollar allocation for a phase."""
        for a in self.phase_allocations:
            if a.phase == phase:
                return self.max_cost_usd * a.percent / 100.0
        return 0.0


class BudgetSnapshot(BaseModel):
    """Current budget state at a point in time."""

    schema_version: str = "dm.budget-snapshot.v1"
    spent_usd: float = Field(default=0.0, ge=0)
    spent_tokens: int = Field(default=0, ge=0)
    llm_calls: int = Field(default=0, ge=0)
    elapsed_ms: int = Field(default=0, ge=0)
    remaining_usd: float = Field(default=2.50, ge=0)
    remaining_tokens: int = Field(default=200_000, ge=0)
    remaining_ms: int = Field(default=1_800_000, ge=0)

    def is_exceeded(self, policy: BudgetPolicy | None = None) -> bool:
        base = self.remaining_usd <= 0 or self.remaining_tokens <= 0 or self.remaining_ms <= 0
        calls_exceeded = policy is not None and self.llm_calls >= policy.max_llm_calls
        return base or calls_exceeded
