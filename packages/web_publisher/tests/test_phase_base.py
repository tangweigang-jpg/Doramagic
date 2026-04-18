"""Tests for P0-3: PhaseContext.api_errors_by_phase and Phase._format_rerun_errors.

Verifies:
  1. PhaseContext.api_errors_by_phase defaults to empty dict
  2. PhaseContext.api_errors_by_phase can be set and read
  3. Phase._format_rerun_errors returns empty string when no errors for this phase
  4. Phase._format_rerun_errors returns formatted error list when errors present
  5. Formatted errors include gate names and messages
"""

from __future__ import annotations

from doramagic_web_publisher.runtime.models import PhaseContext, PublishManifest


def _make_ctx(**kwargs) -> PhaseContext:
    manifest = PublishManifest(
        slug="test-slug",
        blueprint_id="bp-009",
        blueprint_source="zvtvz/zvt",
        blueprint_commit="abc123",
    )
    return PhaseContext(manifest=manifest, **kwargs)


# ---------------------------------------------------------------------------
# PhaseContext.api_errors_by_phase field
# ---------------------------------------------------------------------------


def test_api_errors_by_phase_default_empty():
    """api_errors_by_phase defaults to empty dict."""
    ctx = _make_ctx()
    assert ctx.api_errors_by_phase == {}


def test_api_errors_by_phase_can_be_set():
    """api_errors_by_phase can be populated with phase → error list mapping."""
    ctx = _make_ctx()
    ctx.api_errors_by_phase = {
        "evaluator": [
            {"gate": "SEO-TITLE-LENGTH", "message": "72 chars over limit"},
        ],
        "faq": [
            {"gate": "GEO-FAQ-COUNT", "message": "Only 3 FAQs, need 5"},
        ],
    }
    assert "evaluator" in ctx.api_errors_by_phase
    assert len(ctx.api_errors_by_phase["evaluator"]) == 1
    assert ctx.api_errors_by_phase["evaluator"][0]["gate"] == "SEO-TITLE-LENGTH"


def test_api_errors_by_phase_serializes():
    """api_errors_by_phase round-trips through Pydantic model_dump."""
    ctx = _make_ctx()
    ctx.api_errors_by_phase = {
        "content": [{"gate": "GEO-DEF-FORMAT", "message": "Missing definition format"}]
    }
    dumped = ctx.model_dump()
    assert "api_errors_by_phase" in dumped
    assert "content" in dumped["api_errors_by_phase"]


# ---------------------------------------------------------------------------
# Phase._format_rerun_errors helper
# ---------------------------------------------------------------------------


def test_format_rerun_errors_empty_when_no_errors():
    """_format_rerun_errors returns empty string when no errors for this phase."""
    from doramagic_web_publisher.phases.content import ContentPhase

    phase = ContentPhase()
    ctx = _make_ctx()  # api_errors_by_phase is empty

    result = phase._format_rerun_errors(ctx)
    assert result == ""


def test_format_rerun_errors_empty_when_different_phase_has_errors():
    """_format_rerun_errors returns empty string for phases without errors."""
    from doramagic_web_publisher.phases.content import ContentPhase

    phase = ContentPhase()
    ctx = _make_ctx()
    # Only faq phase has errors — content phase should see empty
    ctx.api_errors_by_phase = {"faq": [{"gate": "GEO-FAQ-COUNT", "message": "Too few FAQs"}]}

    result = phase._format_rerun_errors(ctx)
    assert result == ""


def test_format_rerun_errors_returns_formatted_list():
    """_format_rerun_errors returns human-readable error list for this phase."""
    from doramagic_web_publisher.phases.evaluator import EvaluatorPhase

    phase = EvaluatorPhase()
    ctx = _make_ctx()
    ctx.api_errors_by_phase = {
        "evaluator": [
            {"gate": "SEO-TITLE-LENGTH", "message": "72 chars over limit"},
            {"gate": "GEO-KEYWORDS", "message": "Missing primary keyword"},
        ]
    }

    result = phase._format_rerun_errors(ctx)
    assert "SEO-TITLE-LENGTH" in result
    assert "72 chars over limit" in result
    assert "GEO-KEYWORDS" in result
    assert "Missing primary keyword" in result
    # Should have some kind of warning/correction language
    assert len(result) > 0


def test_format_rerun_errors_includes_gate_and_message():
    """Each error entry in the output contains both gate ID and message."""
    from doramagic_web_publisher.phases.constraints import ConstraintsPhase

    phase = ConstraintsPhase()
    ctx = _make_ctx()
    ctx.api_errors_by_phase = {
        "constraints": [
            {"gate": "TRUST-FATAL", "message": "No fatal constraint found"},
        ]
    }

    result = phase._format_rerun_errors(ctx)
    assert "TRUST-FATAL" in result
    assert "No fatal constraint found" in result
