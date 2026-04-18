"""HTTP publisher — POSTs the Crystal Package to /api/publish/crystal.

Uses httpx (sync) with retry on 5xx errors.
Handles fatal API errors and routes them back to responsible phases.

Usage:
    publisher = Publisher()
    report = publisher.publish(package)
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from doramagic_web_publisher.errors import PublishError
from doramagic_web_publisher.runtime.pipeline import GATE_TO_PHASE

logger = logging.getLogger(__name__)

_DEFAULT_API_URL = "https://doramagic.ai/api/publish/crystal"
_RETRY_STATUS_CODES = {429, 500, 502, 503, 504}
_MAX_RETRIES = 3
_RETRY_DELAYS = (2.0, 5.0, 15.0)


class PublishReport:
    """Structured report from the Publish API."""

    def __init__(
        self,
        success: bool,
        slug: str,
        version: str,
        warnings: list[dict],
        raw_response: dict[str, Any],
    ) -> None:
        self.success = success
        self.slug = slug
        self.version = version
        self.warnings = warnings
        self.raw_response = raw_response

    def __repr__(self) -> str:
        return (
            f"PublishReport(success={self.success}, slug={self.slug!r}, "
            f"version={self.version!r}, warnings={len(self.warnings)})"
        )


class Publisher:
    """Publishes the Crystal Package JSON to the Doramagic Publish API.

    Reads configuration from environment variables:
      PUBLISH_API_KEY  — required for actual publish
      PUBLISH_API_URL  — optional, defaults to https://doramagic.ai/api/publish/crystal
    """

    def __init__(
        self,
        api_url: str | None = None,
        api_key: str | None = None,
        *,
        timeout: float = 60.0,
    ) -> None:
        self._api_url = api_url or os.environ.get("PUBLISH_API_URL", _DEFAULT_API_URL)
        self._api_key = api_key or os.environ.get("PUBLISH_API_KEY", "")
        self._timeout = timeout

    def publish(self, package: dict[str, Any]) -> PublishReport:
        """POST the package to the Publish API.

        Args:
            package: Crystal Package dict from Assembler.

        Returns:
            PublishReport on success.

        Raises:
            PublishError: If the API returns a non-success status.
            httpx.HTTPError: On network errors after all retries.
        """
        if not self._api_key:
            raise PublishError(
                status_code=401,
                phase="auth",
                errors=[{"message": "PUBLISH_API_KEY environment variable is not set"}],
            )

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        slug = package.get("slug", "unknown")
        version = package.get("version", "unknown")

        logger.info(
            "Publisher: POSTing Crystal Package slug='%s' version='%s' to %s",
            slug,
            version,
            self._api_url,
        )

        last_exc: Exception | None = None

        for attempt, delay in enumerate((*_RETRY_DELAYS, None)):
            try:
                response = httpx.post(
                    self._api_url,
                    json=package,
                    headers=headers,
                    timeout=self._timeout,
                )
            except httpx.TransportError as exc:
                logger.warning("Publisher: transport error on attempt %d: %s", attempt + 1, exc)
                last_exc = exc
                if delay is not None:
                    import time

                    time.sleep(delay)
                continue

            logger.debug("Publisher: attempt %d → HTTP %d", attempt + 1, response.status_code)

            if response.status_code in _RETRY_STATUS_CODES and delay is not None:
                logger.warning(
                    "Publisher: HTTP %d on attempt %d; retrying in %.1fs",
                    response.status_code,
                    attempt + 1,
                    delay,
                )
                import time

                time.sleep(delay)
                continue

            # Parse response body
            try:
                body = response.json()
            except Exception:
                body = {"raw": response.text}

            if response.status_code == 200 and body.get("success"):
                logger.info("Publisher: success! slug='%s' version='%s'", slug, version)
                return PublishReport(
                    success=True,
                    slug=body.get("slug", slug),
                    version=body.get("version", version),
                    warnings=body.get("warnings", []),
                    raw_response=body,
                )

            # Non-success response — raise PublishError
            phase = body.get("phase", "unknown")
            errors = body.get("errors", [])
            raise PublishError(
                status_code=response.status_code,
                phase=phase,
                errors=errors,
                raw_body=str(body),
            )

        # All retries exhausted by transport errors
        if last_exc is not None:
            raise last_exc
        raise PublishError(
            status_code=0,
            phase="network",
            errors=[{"message": f"All {_MAX_RETRIES} retries failed"}],
        )

    def route_errors(self, error: PublishError) -> dict[str, list[dict]]:
        """Map API errors to responsible phase names.

        Used to decide which phase to re-run after a fatal API error.

        Args:
            error: PublishError from a failed publish() call.

        Returns:
            Dict mapping phase_name → list of error dicts.
        """
        routing: dict[str, list[dict]] = {}
        for err in error.errors:
            gate = err.get("gate", "")
            phase_name = GATE_TO_PHASE.get(gate, "evaluator")
            routing.setdefault(phase_name, []).append(err)
        return routing

    def publish_dry_run(self, package: dict[str, Any]) -> None:
        """Simulate publish (no HTTP call) — just log the package summary."""
        slug = package.get("slug", "unknown")
        version = package.get("version", "unknown")
        constraints = package.get("constraints", [])
        faqs = package.get("faqs", [])
        tier = package.get("tier", "unknown")

        logger.info("=== DRY-RUN: Crystal Package Summary ===")
        logger.info("  slug:        %s", slug)
        logger.info("  version:     %s", version)
        logger.info("  tier:        %s", tier)
        logger.info("  constraints: %d", len(constraints))
        logger.info("  faqs:        %d", len(faqs))
        logger.info("  is_flagship: %s", package.get("is_flagship"))
        logger.info("  category:    %s", package.get("category_slug"))
        logger.info("  tags:        %s", package.get("tags", []))
        logger.info("=== END DRY-RUN ===")
