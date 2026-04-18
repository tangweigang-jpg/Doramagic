"""Tests for P0-2: Orchestrator fatal-gate retry loop.

Verifies:
  1. Successful publish on first attempt → report returned
  2. First attempt 400 with fatal gates → errors routed, affected phases re-run,
     second attempt succeeds → report returned
  3. All retries exhausted → PublishError re-raised
  4. Non-400 error is not retried
  5. api_errors_by_phase is populated before the retry run
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from doramagic_web_publisher.errors import PublishError
from doramagic_web_publisher.runtime.models import PhaseContext, PublishManifest
from doramagic_web_publisher.runtime.orchestrator import Orchestrator

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ctx(mock_mode: bool = True) -> PhaseContext:
    manifest = PublishManifest(
        slug="test-slug",
        blueprint_id="bp-009",
        blueprint_source="zvtvz/zvt",
        blueprint_commit="abc123",
    )
    return PhaseContext(manifest=manifest, mock_mode=mock_mode)


def _make_publish_report():
    from doramagic_web_publisher.publisher import PublishReport

    return PublishReport(
        success=True,
        slug="test-slug",
        version="v1.0.0",
        warnings=[],
        raw_response={"success": True},
    )


def _make_fatal_publish_error():
    return PublishError(
        status_code=400,
        phase="validation",
        errors=[
            {"gate": "SEO-TITLE-LENGTH", "message": "Title too long"},
            {"gate": "GEO-FAQ-COUNT", "message": "Too few FAQs"},
        ],
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_orchestrator_success_first_attempt(fake_adapter, sample_context):
    """Orchestrator returns report on first successful publish."""
    mock_assembler = MagicMock()
    mock_assembler.assemble.return_value = {"slug": "test-slug", "version": "v1.0.0"}

    mock_preflight = MagicMock()
    mock_preflight.run_and_raise_on_fatal.return_value = []

    mock_publisher = MagicMock()
    mock_publisher.publish.return_value = _make_publish_report()

    orchestrator = Orchestrator(
        adapter=fake_adapter,
        model_id="claude-sonnet-4-6",
        assembler=mock_assembler,
        preflight_runner=mock_preflight,
        publisher=mock_publisher,
    )

    report = orchestrator.run(sample_context)

    assert report.success is True
    assert report.slug == "test-slug"
    mock_publisher.publish.assert_called_once()


def test_orchestrator_retry_on_fatal_gate_error(fake_adapter, sample_context):
    """On 400 with fatal gates, orchestrator routes errors and re-runs phases."""
    mock_assembler = MagicMock()
    mock_assembler.assemble.return_value = {"slug": "test-slug", "version": "v1.0.0"}

    mock_preflight = MagicMock()
    mock_preflight.run_and_raise_on_fatal.return_value = []

    # First publish fails with fatal gates, second succeeds
    mock_publisher = MagicMock()
    mock_publisher.publish.side_effect = [
        _make_fatal_publish_error(),
        _make_publish_report(),
    ]
    # route_errors returns routing dict
    mock_publisher.route_errors.return_value = {
        "evaluator": [{"gate": "SEO-TITLE-LENGTH", "message": "Title too long"}],
        "faq": [{"gate": "GEO-FAQ-COUNT", "message": "Too few FAQs"}],
    }

    orchestrator = Orchestrator(
        adapter=fake_adapter,
        model_id="claude-sonnet-4-6",
        max_retry_on_api_error=3,
        assembler=mock_assembler,
        preflight_runner=mock_preflight,
        publisher=mock_publisher,
    )

    report = orchestrator.run(sample_context)

    assert report.success is True
    # publish called twice: first failure, then success
    assert mock_publisher.publish.call_count == 2
    # route_errors called once (on the first failure)
    mock_publisher.route_errors.assert_called_once()


def test_orchestrator_api_errors_stored_in_context(fake_adapter, sample_context):
    """api_errors_by_phase is populated on context before retry."""
    mock_assembler = MagicMock()
    mock_assembler.assemble.return_value = {"slug": "test-slug", "version": "v1.0.0"}

    mock_preflight = MagicMock()
    mock_preflight.run_and_raise_on_fatal.return_value = []

    captured_ctx = {}

    def fake_run_single_phase(phase_name, ctx):
        captured_ctx["ctx_at_retry"] = ctx
        return ctx

    mock_publisher = MagicMock()
    mock_publisher.publish.side_effect = [
        _make_fatal_publish_error(),
        _make_publish_report(),
    ]
    mock_publisher.route_errors.return_value = {
        "evaluator": [{"gate": "SEO-TITLE-LENGTH", "message": "Title too long"}],
    }

    orchestrator = Orchestrator(
        adapter=fake_adapter,
        model_id="claude-sonnet-4-6",
        max_retry_on_api_error=3,
        assembler=mock_assembler,
        preflight_runner=mock_preflight,
        publisher=mock_publisher,
    )

    # Patch run_single_phase on the pipeline to capture context
    orchestrator._pipeline.run_single_phase = fake_run_single_phase

    orchestrator.run(sample_context)

    assert "evaluator" in captured_ctx["ctx_at_retry"].api_errors_by_phase
    errors = captured_ctx["ctx_at_retry"].api_errors_by_phase["evaluator"]
    assert any(e.get("gate") == "SEO-TITLE-LENGTH" for e in errors)


def test_orchestrator_exhausted_retries_raises(fake_adapter, sample_context):
    """After all retries exhausted, PublishError is re-raised."""
    mock_assembler = MagicMock()
    mock_assembler.assemble.return_value = {"slug": "test-slug", "version": "v1.0.0"}

    mock_preflight = MagicMock()
    mock_preflight.run_and_raise_on_fatal.return_value = []

    mock_publisher = MagicMock()
    # Always fail with 400
    mock_publisher.publish.side_effect = _make_fatal_publish_error()
    mock_publisher.route_errors.return_value = {
        "evaluator": [{"gate": "SEO-TITLE-LENGTH", "message": "Too long"}],
    }

    orchestrator = Orchestrator(
        adapter=fake_adapter,
        model_id="claude-sonnet-4-6",
        max_retry_on_api_error=2,  # only 2 retries
        assembler=mock_assembler,
        preflight_runner=mock_preflight,
        publisher=mock_publisher,
    )

    with pytest.raises(PublishError) as exc_info:
        orchestrator.run(sample_context)

    assert exc_info.value.status_code == 400
    # publish called 3 times: initial + 2 retries
    assert mock_publisher.publish.call_count == 3


def test_orchestrator_non_400_not_retried(fake_adapter, sample_context):
    """HTTP 401 or 5xx errors are not retried."""
    mock_assembler = MagicMock()
    mock_assembler.assemble.return_value = {"slug": "test-slug", "version": "v1.0.0"}

    mock_preflight = MagicMock()
    mock_preflight.run_and_raise_on_fatal.return_value = []

    mock_publisher = MagicMock()
    mock_publisher.publish.side_effect = PublishError(
        status_code=401,
        phase="auth",
        errors=[{"message": "Unauthorized"}],
    )

    orchestrator = Orchestrator(
        adapter=fake_adapter,
        model_id="claude-sonnet-4-6",
        max_retry_on_api_error=3,
        assembler=mock_assembler,
        preflight_runner=mock_preflight,
        publisher=mock_publisher,
    )

    with pytest.raises(PublishError) as exc_info:
        orchestrator.run(sample_context)

    assert exc_info.value.status_code == 401
    # Only called once — no retry on 401
    mock_publisher.publish.assert_called_once()


def test_context_reuse_clears_previous_errors(fake_adapter):
    """P2-a: reusing a PhaseContext clears stale api_errors_by_phase before Pipeline.run().

    Simulates a caller that reuses the same context object across two publish
    calls (e.g. batch mode).  The second call must not see errors from the first.
    """
    from doramagic_web_publisher.runtime.models import PhaseContext, PublishManifest

    manifest = PublishManifest(
        slug="batch-slug",
        blueprint_id="bp-001",
        blueprint_source="org/repo",
        blueprint_commit="deadbeef",
    )
    ctx = PhaseContext(manifest=manifest, mock_mode=True)
    # Pre-populate with stale errors from a "previous run"
    ctx.api_errors_by_phase = {
        "evaluator": [{"gate": "OLD-GATE", "message": "stale error"}],
    }

    mock_assembler = MagicMock()
    mock_assembler.assemble.return_value = {"slug": "batch-slug", "version": "v1.0.0"}

    mock_preflight = MagicMock()
    mock_preflight.run_and_raise_on_fatal.return_value = []

    mock_publisher = MagicMock()
    mock_publisher.publish.return_value = _make_publish_report()

    # Capture api_errors_by_phase value at the moment Pipeline.run() is called.
    errors_at_pipeline_run: dict = {}

    def fake_pipeline_run(c):
        # Record the state of api_errors_by_phase right when pipeline starts
        errors_at_pipeline_run.update(c.api_errors_by_phase)
        return c

    orchestrator = Orchestrator(
        adapter=fake_adapter,
        model_id="claude-sonnet-4-6",
        assembler=mock_assembler,
        preflight_runner=mock_preflight,
        publisher=mock_publisher,
    )
    # Patch the pipeline's run method to intercept the context
    orchestrator._pipeline.run = fake_pipeline_run

    orchestrator.run(ctx)

    # At the moment Pipeline.run() was called, api_errors_by_phase must be empty
    assert errors_at_pipeline_run == {}, (
        f"Expected api_errors_by_phase to be cleared before Pipeline.run(), "
        f"but got: {errors_at_pipeline_run}"
    )
