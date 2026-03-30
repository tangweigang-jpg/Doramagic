"""Platform adapter protocol for the dual-layer architecture."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field

from .skill import PlatformRules


class ProgressUpdate(BaseModel):
    """Progress notification sent at each phase boundary."""

    phase: str
    status: str  # "started" | "completed" | "degraded" | "error"
    message: str
    elapsed_ms: int = Field(ge=0)
    percent_complete: int = Field(ge=0, le=100)


class ClarificationRequest(BaseModel):
    """Multi-turn clarification for Phase A."""

    question: str
    options: list[str] | None = None  # None = free text, list = multiple choice
    timeout_seconds: int = 120
    default_on_timeout: str | None = None
    round_number: int = Field(ge=1, le=4)


@runtime_checkable
class PlatformAdapter(Protocol):
    """Interface for platform-specific behavior.

    Implementations:
    - OpenClawAdapter: /dora on OpenClaw platform
    - CLIAdapter: local terminal for development/testing
    """

    async def receive_input(self) -> str:
        """Get user input from the platform."""
        ...

    async def send_output(self, message: str, artifacts: dict[str, Path]) -> None:
        """Deliver results to the user."""
        ...

    async def send_progress(self, update: ProgressUpdate) -> None:
        """Progress notification at phase boundaries. May be silently dropped."""
        ...

    async def ask_clarification(self, request: ClarificationRequest) -> str:
        """Multi-turn clarification (Phase A). Returns user response or default on timeout."""
        ...

    def get_storage_root(self) -> Path:
        """Platform-specific storage path."""
        ...

    def get_platform_rules(self) -> PlatformRules:
        """Platform constraints."""
        ...

    def get_concurrency_limit(self) -> int:
        """Max parallel executors this platform supports."""
        ...
