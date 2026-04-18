"""Custom exception types for the web_publisher package."""

from __future__ import annotations


class WebPublisherError(Exception):
    """Base exception for all web_publisher errors."""


class PhaseError(WebPublisherError):
    """Raised when a pipeline phase fails non-recoverably."""

    def __init__(self, phase_name: str, message: str) -> None:
        self.phase_name = phase_name
        super().__init__(f"[{phase_name}] {message}")


class ToolUseError(WebPublisherError):
    """Raised when the tool-use loop fails or exceeds max iterations."""

    def __init__(self, message: str, iterations: int = 0) -> None:
        self.iterations = iterations
        super().__init__(message)


class ToolUseMaxIterationsError(ToolUseError):
    """Raised when max iterations reached without a submit_* call."""

    def __init__(self, tool_name: str, max_iter: int) -> None:
        self.tool_name = tool_name
        super().__init__(
            f"Max iterations ({max_iter}) reached without submit call for tool '{tool_name}'",
            iterations=max_iter,
        )


class ToolUseStoppedWithoutSubmitError(ToolUseError):
    """Raised when LLM returns stop/end without ever calling the submit_* tool.

    Distinct from ToolUseMaxIterationsError:
    - MaxIterations: loop exhausted the allowed turns (may be retried with more iters)
    - StoppedWithoutSubmit: LLM explicitly stopped responding with tool calls
      (prompt adjustment or model change is needed, not simply more iters)
    """

    def __init__(self, tool_name: str, iteration: int, finish_reason: str) -> None:
        self.tool_name = tool_name
        self.finish_reason = finish_reason
        super().__init__(
            f"LLM stopped (finish_reason={finish_reason!r}) on iter {iteration} "
            f"without calling submit tool '{tool_name}'",
            iterations=iteration,
        )


class PreflightError(WebPublisherError):
    """Raised when local preflight gates fail."""

    def __init__(self, failures: list[dict[str, str]]) -> None:
        self.failures = failures
        msgs = "; ".join(f"{f['gate']}: {f['message']}" for f in failures)
        super().__init__(f"Preflight failed ({len(failures)} gate(s)): {msgs}")


class PublishError(WebPublisherError):
    """Raised when the Publish API returns a non-success response."""

    def __init__(
        self,
        status_code: int,
        phase: str,
        errors: list[dict],
        raw_body: str = "",
    ) -> None:
        self.status_code = status_code
        self.phase = phase
        self.errors = errors
        self.raw_body = raw_body
        super().__init__(
            f"Publish API returned {status_code} (phase={phase}): "
            + "; ".join(str(e) for e in errors)
        )


class ManifestNotFoundError(WebPublisherError):
    """Raised when blueprint manifest / seed cannot be located."""

    def __init__(self, slug_or_id: str) -> None:
        super().__init__(f"Cannot find manifest for '{slug_or_id}'")


class AssemblyError(WebPublisherError):
    """Raised when Package JSON assembly fails due to missing phase outputs."""

    def __init__(self, missing_fields: list[str]) -> None:
        self.missing_fields = missing_fields
        super().__init__(f"Assembly failed — missing fields: {', '.join(missing_fields)}")


class PhaseParsingError(WebPublisherError):
    """Raised when a phase's parse_result fails validation.

    Contains a list of validation error messages.
    """

    def __init__(self, phase_name: str, errors: list[str]) -> None:
        self.phase_name = phase_name
        self.validation_errors = errors
        joined = "; ".join(errors)
        super().__init__(f"[{phase_name}] parse_result validation failed: {joined}")
