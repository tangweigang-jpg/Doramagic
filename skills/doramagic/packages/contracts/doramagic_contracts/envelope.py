"""统一返回 Envelope + 错误码 — 所有赛马模块必须遵守。"""

from __future__ import annotations

from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class RunMetrics(BaseModel):
    """模块运行指标。"""

    wall_time_ms: int = Field(ge=0)
    llm_calls: int = Field(ge=0)
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0)
    retries: int = Field(ge=0, default=0)


class WarningItem(BaseModel):
    code: str
    message: str


class ModuleResultEnvelope(BaseModel, Generic[T]):
    """所有赛马模块的统一返回格式。"""

    schema_version: str = "dm.module-envelope.v1"
    module_name: str
    status: Literal["ok", "degraded", "blocked", "error"]
    error_code: str | None = None
    warnings: list[WarningItem] = []
    data: T | None = None
    metrics: RunMetrics


# 统一错误码
class ErrorCodes:
    INPUT_INVALID = "E_INPUT_INVALID"
    UPSTREAM_MISSING = "E_UPSTREAM_MISSING"
    SCHEMA_MISMATCH = "E_SCHEMA_MISMATCH"
    TIMEOUT = "E_TIMEOUT"
    RETRY_EXHAUSTED = "E_RETRY_EXHAUSTED"
    BUDGET_EXCEEDED = "E_BUDGET_EXCEEDED"
    NO_CANDIDATES = "E_NO_CANDIDATES"
    NO_HYPOTHESES = "E_NO_HYPOTHESES"
    PLATFORM_VIOLATION = "E_PLATFORM_VIOLATION"
    UNRESOLVED_CONFLICT = "E_UNRESOLVED_CONFLICT"
    VALIDATION_BLOCKED = "E_VALIDATION_BLOCKED"
