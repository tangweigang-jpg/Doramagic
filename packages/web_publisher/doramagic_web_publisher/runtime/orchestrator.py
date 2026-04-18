"""Orchestrator — ties Pipeline, Assembler, PreflightRunner, and Publisher together.

Implements the fatal-gate retry loop:
  1. Run all pipeline phases
  2. Assemble the Crystal Package
  3. Run local preflight gates
  4. POST to the Publish API
  5. If API returns status_code=400 with fatal gate errors:
     a. Route errors back to responsible phases via Publisher.route_errors()
     b. Store error details in PhaseContext.api_errors_by_phase
     c. Re-run only the affected phases (other phases keep their results)
     d. Re-assemble → re-preflight → re-publish
     e. Repeat up to max_retry_on_api_error times

Usage:
    from doramagic_web_publisher.runtime.orchestrator import Orchestrator

    orchestrator = Orchestrator(adapter=adapter, model_id="claude-sonnet-4-6")
    report = orchestrator.run(ctx)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from doramagic_web_publisher.errors import PublishError, WebPublisherError
from doramagic_web_publisher.runtime.pipeline import Pipeline

if TYPE_CHECKING:
    from doramagic_shared_utils.llm_adapter import LLMAdapter

    from doramagic_web_publisher.assembler import Assembler
    from doramagic_web_publisher.preflight import PreflightRunner
    from doramagic_web_publisher.publisher import Publisher, PublishReport
    from doramagic_web_publisher.runtime.models import PhaseContext

logger = logging.getLogger(__name__)


class Orchestrator:
    """Coordinates the full publish pipeline with API-error retry.

    Retry semantics:
    - Only HTTP 400 responses with a non-empty ``errors`` list trigger a retry.
    - Other status codes (401, 5xx, transport errors) are re-raised immediately.
    - ``max_retry_on_api_error`` counts only API-error retries (not 5xx retries
      handled inside Publisher itself).
    """

    def __init__(
        self,
        adapter: LLMAdapter,
        model_id: str,
        *,
        max_retry_on_api_error: int = 3,
        assembler: Assembler | None = None,
        preflight_runner: PreflightRunner | None = None,
        publisher: Publisher | None = None,
    ) -> None:
        self._pipeline = Pipeline(adapter=adapter, model_id=model_id)
        self._model_id = model_id
        self._max_retry = max_retry_on_api_error

        # Allow injection for testing
        self._assembler = assembler
        self._preflight_runner = preflight_runner
        self._publisher = publisher

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, ctx: PhaseContext) -> PublishReport:
        """Execute the full pipeline and return the PublishReport.

        Args:
            ctx: PhaseContext populated with manifest, blueprint, constraints, etc.

        Returns:
            PublishReport on success.

        Raises:
            PublishError: If all retries are exhausted or a non-retryable error occurs.
            PreflightError: If local preflight gates fail (not retried — prompt issue).
            PhaseError: If any pipeline phase fails.
        """
        from doramagic_web_publisher.assembler import Assembler
        from doramagic_web_publisher.preflight import PreflightRunner
        from doramagic_web_publisher.publisher import Publisher

        assembler = self._assembler or Assembler()
        preflight_runner = self._preflight_runner or PreflightRunner()
        publisher = self._publisher or Publisher()

        # Clear any residual errors from a previous run on the same PhaseContext.
        # Without this, callers that reuse a PhaseContext across multiple publish
        # calls (e.g. batch publishing) would see stale errors from the prior run
        # bleed into the next run's retry prompts.
        ctx.api_errors_by_phase = {}

        # Initial full pipeline run
        ctx = self._pipeline.run(ctx)

        for attempt in range(self._max_retry + 1):
            package = assembler.assemble(ctx)

            # Local preflight — PreflightError is not retried (prompt issue)
            preflight_runner.run_and_raise_on_fatal(package)

            if ctx.dry_run:
                publisher.publish_dry_run(package)
                # Return a synthetic report for dry-run
                from doramagic_web_publisher.publisher import PublishReport

                return PublishReport(
                    success=True,
                    slug=package.get("slug", ""),
                    version=package.get("version", ""),
                    warnings=[],
                    raw_response={"dry_run": True},
                )

            try:
                report = publisher.publish(package)
                logger.info(
                    "Orchestrator: published successfully on attempt %d: slug=%r",
                    attempt + 1,
                    report.slug,
                )
                return report

            except PublishError as exc:
                if exc.status_code != 400 or not exc.errors:
                    # Non-retriable error
                    raise

                if attempt >= self._max_retry:
                    logger.error(
                        "Orchestrator: exhausted %d retry(ies) — giving up. Last error: %s",
                        self._max_retry,
                        exc,
                    )
                    raise PublishError(
                        status_code=exc.status_code,
                        phase=exc.phase,
                        errors=exc.errors,
                        raw_body=exc.raw_body,
                    ) from exc

                logger.warning(
                    "Orchestrator: API returned 400 with fatal gates on attempt %d; "
                    "routing errors and retrying (attempt %d/%d).",
                    attempt + 1,
                    attempt + 2,
                    self._max_retry + 1,
                )

                # Route errors to phases and store in context
                routing = publisher.route_errors(exc)
                ctx.api_errors_by_phase = {
                    phase_name: errors for phase_name, errors in routing.items()
                }

                # Re-run only the affected phases (preserve results for others)
                for phase_name in routing:
                    logger.info(
                        "Orchestrator: re-running phase '%s' (%d error(s))",
                        phase_name,
                        len(routing[phase_name]),
                    )
                    try:
                        ctx = self._pipeline.run_single_phase(phase_name, ctx)
                    except ValueError as e:
                        logger.warning(
                            "Orchestrator: phase '%s' not found, skipping: %s",
                            phase_name,
                            e,
                        )

        # Should never reach here
        raise WebPublisherError("Orchestrator: unexpected exit from retry loop")
