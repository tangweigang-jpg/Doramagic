"""State transition tracking — records WHY each phase transition happened."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass
class Transition:
    from_phase: str
    to_phase: str
    reason: str  # "completed", "failed", "circuit_break", "skipped", "dependency_unmet"
    timestamp: str
    elapsed_ms: int = 0
    tokens_used: int = 0


class TransitionTracker:
    def __init__(self) -> None:
        self._transitions: list[Transition] = []
        self._current_phase: str = ""
        self._phase_start: float = 0.0

    def enter_phase(self, phase: str) -> None:
        self._current_phase = phase
        self._phase_start = time.monotonic()

    def exit_phase(self, to_phase: str, reason: str, tokens: int = 0) -> None:
        elapsed = int((time.monotonic() - self._phase_start) * 1000) if self._phase_start else 0
        self._transitions.append(
            Transition(
                from_phase=self._current_phase,
                to_phase=to_phase,
                reason=reason,
                timestamp=datetime.now(UTC).isoformat(),
                elapsed_ms=elapsed,
                tokens_used=tokens,
            )
        )
        self._current_phase = to_phase
        self._phase_start = time.monotonic()

    @property
    def transitions(self) -> list[Transition]:
        return list(self._transitions)

    def summary(self) -> str:
        lines = ["Phase Transitions:"]
        for t in self._transitions:
            lines.append(
                f"  {t.from_phase} → {t.to_phase} [{t.reason}] {t.elapsed_ms}ms, {t.tokens_used} tokens"
            )
        return "\n".join(lines)
