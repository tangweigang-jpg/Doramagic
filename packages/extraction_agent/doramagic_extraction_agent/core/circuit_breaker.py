"""Circuit breaker for the extraction agent loop.

Tracks consecutive tool failures, total iterations, and token consumption.
When any threshold is exceeded ``should_break`` returns ``(True, reason)``
so the caller can exit cleanly rather than spinning into an error storm.

Separated from ``agent_loop`` so it can be unit-tested in isolation and
potentially reused in other agentic loops.

Typical usage::

    cb = CircuitBreaker(max_consecutive=3, max_total=200, max_tokens=500_000)

    # After each tool call:
    if tool_result.is_error:
        cb.record_failure(tool_result.content)
    else:
        cb.record_success()

    cb.increment_iterations()
    cb.add_tokens(response.prompt_tokens + response.completion_tokens)

    should_stop, reason = cb.should_break()
    if should_stop:
        ...
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CircuitBreaker:
    """Tracks failure state and enforces hard limits on an agentic loop.

    Args:
        max_consecutive: Maximum number of consecutive tool failures before
            the circuit opens.
        max_total: Maximum total iterations (LLM calls) allowed.
        max_tokens: Maximum cumulative tokens (prompt + completion) allowed.
    """

    max_consecutive: int = 3
    max_total: int = 200
    max_tokens: int = 500_000

    # --- mutable state (not constructor args) ---
    _consecutive_failures: int = field(default=0, init=False, repr=False)
    _total_iterations: int = field(default=0, init=False, repr=False)
    _total_tokens: int = field(default=0, init=False, repr=False)
    _errors: list[str] = field(default_factory=list, init=False, repr=False)

    # ------------------------------------------------------------------
    # Mutation helpers
    # ------------------------------------------------------------------

    def record_success(self) -> None:
        """Reset the consecutive-failure counter after a successful tool call."""
        self._consecutive_failures = 0

    def record_failure(self, error: str) -> None:
        """Increment the consecutive-failure counter and record the error message.

        Args:
            error: Human-readable description of what went wrong.  Stored
                in ``stats["errors"]`` for post-mortem inspection.
        """
        self._consecutive_failures += 1
        self._errors.append(error)

    def increment_iterations(self) -> None:
        """Increment the total-iterations counter by one."""
        self._total_iterations += 1

    def add_tokens(self, tokens: int) -> None:
        """Add ``tokens`` to the running total.

        Args:
            tokens: Number of tokens to add (prompt + completion for one call).
        """
        self._total_tokens += tokens

    def reset(self) -> None:
        """Reset all counters and error log to the initial state."""
        self._consecutive_failures = 0
        self._total_iterations = 0
        self._total_tokens = 0
        self._errors.clear()

    # ------------------------------------------------------------------
    # Decision
    # ------------------------------------------------------------------

    def should_break(self) -> tuple[bool, str]:
        """Evaluate whether the circuit should open.

        Checks limits in priority order: consecutive failures → total
        iterations → total tokens.

        Returns:
            A ``(should_break, reason)`` tuple.  ``reason`` is an empty
            string when ``should_break`` is ``False``.
        """
        if self._consecutive_failures >= self.max_consecutive:
            return (
                True,
                f"Circuit breaker: {self._consecutive_failures} consecutive tool failures "
                f"(limit={self.max_consecutive})",
            )
        if self._total_iterations >= self.max_total:
            return (
                True,
                f"Circuit breaker: reached max iterations "
                f"({self._total_iterations}/{self.max_total})",
            )
        if self._total_tokens >= self.max_tokens:
            return (
                True,
                f"Circuit breaker: exceeded token budget "
                f"({self._total_tokens:,}/{self.max_tokens:,})",
            )
        return (False, "")

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def stats(self) -> dict:
        """Return a snapshot of the current state for logging and post-mortems.

        Returns:
            Dict with keys: ``consecutive_failures``, ``total_iterations``,
            ``total_tokens``, ``errors``.
        """
        return {
            "consecutive_failures": self._consecutive_failures,
            "total_iterations": self._total_iterations,
            "total_tokens": self._total_tokens,
            "errors": list(self._errors),
        }
