"""Structured event logging — append-only JSONL."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class AgentEventLogger:
    """Logs structured events to a JSONL file."""

    def __init__(self, log_path: Path):
        self._path = log_path
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def log(
        self,
        event_type: str,
        phase: str = "",
        *,
        detail: dict[str, Any] | None = None,
        tokens_in: int = 0,
        tokens_out: int = 0,
        elapsed_ms: int = 0,
    ) -> None:
        event = {
            "ts": datetime.now(UTC).isoformat(),
            "event_type": event_type,
            "phase": phase,
            "detail": detail or {},
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "elapsed_ms": elapsed_ms,
        }
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

    def phase_start(self, phase: str) -> None:
        self.log("phase_start", phase)

    def phase_complete(self, phase: str, iterations: int, tokens: int, elapsed_ms: int) -> None:
        self.log(
            "phase_complete",
            phase,
            detail={"iterations": iterations, "tokens": tokens},
            elapsed_ms=elapsed_ms,
        )

    def phase_failed(self, phase: str, error: str) -> None:
        self.log("phase_failed", phase, detail={"error": error})

    def tool_call(self, phase: str, tool_name: str, elapsed_ms: int) -> None:
        self.log("tool_call", phase, detail={"tool": tool_name}, elapsed_ms=elapsed_ms)

    def llm_call(self, phase: str, tokens_in: int, tokens_out: int, elapsed_ms: int) -> None:
        self.log(
            "llm_call", phase, tokens_in=tokens_in, tokens_out=tokens_out, elapsed_ms=elapsed_ms
        )

    def circuit_break(self, phase: str, reason: str) -> None:
        self.log("circuit_break", phase, detail={"reason": reason})

    def context_compaction(self, phase: str, before_tokens: int, after_tokens: int) -> None:
        self.log(
            "context_compaction", phase, detail={"before": before_tokens, "after": after_tokens}
        )

    def quality_gate(self, phase: str, passed: bool, detail: str) -> None:
        self.log("quality_gate", phase, detail={"passed": passed, "detail": detail})
