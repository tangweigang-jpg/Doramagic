"""Abstract base class for all pipeline phases.

Every phase must implement:
  name            — unique phase identifier (string constant)
  submit_tool_schema() → dict   — JSON Schema for the submit_* tool
  build_prompt(ctx) → str       — user turn content for the LLM
  parse_result(args) → PhaseResult — parse submit tool arguments into PhaseResult
  run(ctx, adapter) → PhaseResult — full phase execution (calls tool_use loop)

Phases MUST NOT import from each other (decoupled by design).
They communicate only through PhaseContext.results.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from doramagic_shared_utils.llm_adapter import LLMAdapter

from doramagic_web_publisher.runtime.models import PhaseContext, PhaseResult


class Phase(ABC):
    """Abstract base for all pipeline phases."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique phase name. Must match PHASES registration key."""

    @abstractmethod
    def submit_tool_schema(self) -> dict[str, Any]:
        """Return the full JSON Schema for this phase's submit_* tool.

        The schema must align with the Package JSON fields this phase produces
        (see SOP §1.2 for the field groups).

        Returns:
            A dict with keys: name, description, parameters (JSON Schema object).
        """

    @abstractmethod
    def build_prompt(self, ctx: PhaseContext) -> str:
        """Build the user-turn prompt for this phase.

        Args:
            ctx: Current pipeline context.

        Returns:
            String content for the initial user message to the LLM.
        """

    @abstractmethod
    def parse_result(self, args: dict[str, Any]) -> PhaseResult:
        """Parse the submit tool arguments into a PhaseResult.

        Args:
            args: The arguments dict from the LLM's submit_* tool call.

        Returns:
            PhaseResult with fields populated.
        """

    @abstractmethod
    def run(self, ctx: PhaseContext, adapter: LLMAdapter) -> PhaseResult:
        """Execute the phase: build prompt → tool_use loop → parse_result.

        Args:
            ctx: Current pipeline context (read-only for this phase).
            adapter: LLMAdapter instance to use for LLM calls.

        Returns:
            PhaseResult for this phase.
        """

    def mock_result(self) -> PhaseResult:
        """Return a stub PhaseResult for use in mock/dry-run mode.

        Subclasses should override this to return type-correct placeholder data
        that allows the assembler to produce a valid (if nonsensical) Package.
        The default implementation raises NotImplementedError.
        """
        raise NotImplementedError(
            f"REPLACE_WITH: {self.name} mock_result — return placeholder PhaseResult "
            f"with correct field types so assembler can run in --mock mode"
        )

    def _format_rerun_errors(self, ctx: PhaseContext) -> str:
        """Return a complete, human-readable rejection block for this phase's API errors.

        Reads ctx.api_errors_by_phase[self.name] and formats them as a
        header + bulleted list suitable for direct inclusion in build_prompt() output.

        Returns empty string when there are no errors for this phase (first run).

        Callers (Phase implementations) should append the return value directly
        to the prompt — the helper already includes the rejection header, so
        callers must NOT add a separate header to avoid duplication.

        Example output (non-empty case):
            ⚠️  The previous publish attempt was rejected. Please correct:
              - [SEO-TITLE-LENGTH] 72 chars exceeds 60-char limit — shorten.
              - [SEO-DESC-LENGTH] Description is 165 chars, max 160.
        """
        errors = ctx.api_errors_by_phase.get(self.name, [])
        if not errors:
            return ""
        lines = []
        for err in errors:
            gate = err.get("gate", "UNKNOWN")
            message = err.get("message", str(err))
            lines.append(f"  - [{gate}] {message}")
        return (
            "⚠️  The previous publish attempt was rejected by the API. "
            "Please correct the following issues:\n" + "\n".join(lines)
        )

    def _make_tool_definition(self) -> Any:
        """Convert submit_tool_schema() to an LLMToolDefinition."""
        from doramagic_shared_utils.llm_adapter import LLMToolDefinition

        schema = self.submit_tool_schema()
        return LLMToolDefinition(
            name=schema["name"],
            description=schema["description"],
            parameters=schema["parameters"],
        )
