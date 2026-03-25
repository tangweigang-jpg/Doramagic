"""Budget tracking per phase.

Tracks token usage, cost, and wall time across the pipeline run.
Produces BudgetSnapshot for executors and warnings for the controller.
"""

from __future__ import annotations

import time
from typing import Optional

from doramagic_contracts.budget import BudgetPolicy, BudgetSnapshot
from doramagic_contracts.envelope import RunMetrics


class BudgetManager:
    """Tracks cumulative budget consumption across phases.

    Usage:
        bm = BudgetManager(policy)
        bm.start()
        snapshot = bm.snapshot()       # pass to executor config
        bm.record_phase("CD", metrics) # after executor returns
        if bm.is_exceeded():
            # transition to DEGRADED
    """

    def __init__(self, policy: Optional[BudgetPolicy] = None) -> None:
        self._policy = policy or BudgetPolicy()
        self._total_cost: float = 0.0
        self._total_tokens: int = 0
        self._start_time: float = 0.0
        self._phase_costs: dict[str, float] = {}
        self._phase_tokens: dict[str, int] = {}
        self._warnings: list[str] = []

    def start(self) -> None:
        """Mark the start of a pipeline run."""
        self._start_time = time.monotonic()

    def elapsed_ms(self) -> int:
        """Milliseconds since start."""
        if self._start_time == 0.0:
            return 0
        return int((time.monotonic() - self._start_time) * 1000)

    def record_phase(self, phase: str, metrics: RunMetrics) -> list[str]:
        """Record metrics from a completed phase. Returns any new warnings."""
        self._total_cost += metrics.estimated_cost_usd
        self._total_tokens += metrics.prompt_tokens + metrics.completion_tokens
        self._phase_costs[phase] = self._phase_costs.get(phase, 0.0) + metrics.estimated_cost_usd
        self._phase_tokens[phase] = (
            self._phase_tokens.get(phase, 0) + metrics.prompt_tokens + metrics.completion_tokens
        )

        new_warnings: list[str] = []

        # Check phase overshoot
        allocation = self._policy.allocation_for(phase)
        if allocation > 0 and self._phase_costs[phase] > allocation * self._policy.overshoot_warning_pct / 100:
            msg = f"Phase {phase} exceeded {self._policy.overshoot_warning_pct}% of budget allocation (${self._phase_costs[phase]:.3f} / ${allocation:.3f})"
            new_warnings.append(msg)
            self._warnings.append(msg)

        # Check total budget
        if self._total_cost > self._policy.max_cost_usd:
            msg = f"Total cost exceeded budget (${self._total_cost:.3f} / ${self._policy.max_cost_usd:.3f})"
            new_warnings.append(msg)
            self._warnings.append(msg)

        return new_warnings

    def snapshot(self) -> BudgetSnapshot:
        """Current budget state for passing to executors."""
        elapsed = self.elapsed_ms()
        return BudgetSnapshot(
            spent_usd=self._total_cost,
            spent_tokens=self._total_tokens,
            elapsed_ms=elapsed,
            remaining_usd=max(0.0, self._policy.max_cost_usd - self._total_cost),
            remaining_tokens=max(0, self._policy.max_tokens - self._total_tokens),
            remaining_ms=max(0, self._policy.max_duration_ms - elapsed),
        )

    def is_exceeded(self) -> bool:
        """Check if total budget is exceeded."""
        return self.snapshot().is_exceeded()

    @property
    def warnings(self) -> list[str]:
        return list(self._warnings)

    @property
    def total_cost(self) -> float:
        return self._total_cost

    @property
    def total_tokens(self) -> int:
        return self._total_tokens
