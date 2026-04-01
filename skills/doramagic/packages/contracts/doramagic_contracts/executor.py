"""Phase executor protocol and configuration for the dual-layer architecture."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from .budget import BudgetSnapshot
from .envelope import ModuleResultEnvelope
from .skill import PlatformRules


class ExecutorConfig(BaseModel):
    """Runtime configuration passed to every phase executor."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    schema_version: str = "dm.executor-config.v1"
    run_dir: Path
    budget_remaining: BudgetSnapshot
    concurrency_limit: int = Field(default=3, ge=1, le=5)
    platform_rules: PlatformRules
    dry_run: bool = False
    event_bus: Any = None


@runtime_checkable
class PhaseExecutor(Protocol):
    """Standard interface for all phase executors.

    Each executor:
    1. Accepts typed input (from contracts)
    2. Returns ModuleResultEnvelope[T]
    3. Is completely platform-unaware
    4. Uses LLMAdapter + CapabilityRouter for all model calls
    """

    async def execute(
        self,
        input: BaseModel,
        adapter: object,  # LLMAdapter — untyped to avoid circular import
        config: ExecutorConfig,
    ) -> ModuleResultEnvelope: ...

    def validate_input(self, input: BaseModel) -> list[str]:
        """Pre-flight input validation. Returns list of error strings."""
        ...

    def can_degrade(self) -> bool:
        """Whether this phase supports degraded execution."""
        ...
