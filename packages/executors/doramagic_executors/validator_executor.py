"""Phase G executor: Quality gate validation."""

from __future__ import annotations

from pydantic import BaseModel

from doramagic_contracts.envelope import ModuleResultEnvelope
from doramagic_contracts.executor import ExecutorConfig
from doramagic_contracts.skill import ValidationInput


class ValidatorExecutor:
    """Wraps platform_openclaw.validator.run_validation() as a PhaseExecutor."""

    async def execute(
        self, input: BaseModel, adapter: object, config: ExecutorConfig,
    ) -> ModuleResultEnvelope:
        from doramagic_platform_openclaw.validator import run_validation

        assert isinstance(input, ValidationInput)
        result = run_validation(input)

        # Map ValidationReport.status to envelope status for controller
        if result.data and result.data.status == "REVISE":
            result.status = "degraded"  # signals controller to loop back
        elif result.data and result.data.status == "BLOCKED":
            result.status = "blocked"

        return result

    def validate_input(self, input: BaseModel) -> list[str]:
        errors = []
        if not isinstance(input, ValidationInput):
            errors.append(f"Expected ValidationInput, got {type(input).__name__}")
        return errors

    def can_degrade(self) -> bool:
        return True  # REVISE is a degraded response, not an error
