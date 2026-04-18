"""Tests for the Pipeline in mock mode.

Verifies:
  1. Phases run in correct order: content → constraints → faq → evaluator
  2. Each phase writes its result into ctx.results
  3. Single-phase run works
  4. Unknown phase name raises ValueError
  5. Mock mode does not raise NotImplementedError (mock_result() is callable)
"""

from __future__ import annotations

import pytest
from doramagic_web_publisher.phases import PHASE_NAMES
from doramagic_web_publisher.runtime.pipeline import Pipeline


def test_phases_order():
    """PHASES list must be in the fixed SOP order."""
    assert PHASE_NAMES == ["content", "constraints", "faq", "evaluator"]


def test_pipeline_mock_mode_all_phases(fake_adapter, sample_context):
    """Pipeline in mock_mode runs all 4 phases without LLM calls."""
    pipeline = Pipeline(adapter=fake_adapter, model_id="claude-sonnet-4-6")
    ctx = pipeline.run(sample_context)

    assert "content" in ctx.results
    assert "constraints" in ctx.results
    assert "faq" in ctx.results
    assert "evaluator" in ctx.results


def test_pipeline_mock_all_phases_successful(fake_adapter, sample_context):
    """All phases succeed in mock mode."""
    pipeline = Pipeline(adapter=fake_adapter, model_id="claude-sonnet-4-6")
    ctx = pipeline.run(sample_context)

    for phase_name in PHASE_NAMES:
        result = ctx.results[phase_name]
        assert result.success is True, f"Phase '{phase_name}' should succeed in mock mode"
        assert result.fields, f"Phase '{phase_name}' should have non-empty fields"


def test_pipeline_mock_content_fields_present(fake_adapter, sample_context):
    """Content phase mock_result contains expected fields."""
    pipeline = Pipeline(adapter=fake_adapter, model_id="claude-sonnet-4-6")
    ctx = pipeline.run(sample_context)

    fields = ctx.results["content"].fields
    required = [
        "slug",
        "name",
        "name_en",
        "definition",
        "definition_en",
        "description",
        "description_en",
        "category_slug",
        "tags",
        "version",
        "known_gaps",
        "changelog",
        "changelog_en",
        "contributors",
    ]
    for f in required:
        assert f in fields, f"Content phase missing field: {f}"


def test_pipeline_mock_constraints_fields_present(fake_adapter, sample_context):
    """Constraints phase mock_result contains 'constraints' list."""
    pipeline = Pipeline(adapter=fake_adapter, model_id="claude-sonnet-4-6")
    ctx = pipeline.run(sample_context)

    fields = ctx.results["constraints"].fields
    assert "constraints" in fields
    assert len(fields["constraints"]) >= 1
    c = fields["constraints"][0]
    assert c["severity"] in {"fatal", "critical", "high"}


def test_pipeline_mock_faq_fields_present(fake_adapter, sample_context):
    """FAQ phase mock_result contains 5+ entries."""
    pipeline = Pipeline(adapter=fake_adapter, model_id="claude-sonnet-4-6")
    ctx = pipeline.run(sample_context)

    fields = ctx.results["faq"].fields
    assert "faqs" in fields
    assert len(fields["faqs"]) >= 5


def test_pipeline_mock_evaluator_fields_present(fake_adapter, sample_context):
    """Evaluator phase mock_result contains LLM-generated H-L field groups.

    Note: host_adapters, creator_proof, sample_output are injected by Assembler (Fix #3),
    so they are NOT expected in evaluator phase fields anymore.
    og_image_fields now contains only headline/headline_en from LLM; stat fields are
    computed by Assembler.
    """
    pipeline = Pipeline(adapter=fake_adapter, model_id="claude-sonnet-4-6")
    ctx = pipeline.run(sample_context)

    fields = ctx.results["evaluator"].fields
    # Fields present in evaluator result (LLM-generated)
    for f in [
        "applicable_scenarios",
        "inapplicable_scenarios",
        "required_inputs",
        "model_compatibility",
        "tier",
        "is_flagship",
        "parent_flagship_slug",
        "core_keywords",
        "og_image_fields",
    ]:
        assert f in fields, f"Evaluator phase missing field: {f}"

    # Fields injected by Assembler should NOT be in evaluator result
    for f in ["host_adapters", "creator_proof", "sample_output"]:
        assert f not in fields, f"Evaluator phase should NOT contain '{f}' (injected by Assembler)"


def test_pipeline_single_phase_content(fake_adapter, sample_context):
    """run_single_phase('content') populates only content result."""
    pipeline = Pipeline(adapter=fake_adapter, model_id="claude-sonnet-4-6")
    ctx = pipeline.run_single_phase("content", sample_context)

    assert "content" in ctx.results
    # Other phases not run
    assert "constraints" not in ctx.results
    assert "faq" not in ctx.results
    assert "evaluator" not in ctx.results


def test_pipeline_single_phase_unknown(fake_adapter, sample_context):
    """run_single_phase with unknown name raises ValueError."""
    pipeline = Pipeline(adapter=fake_adapter, model_id="claude-sonnet-4-6")
    with pytest.raises(ValueError, match="Unknown phase"):
        pipeline.run_single_phase("nonexistent_phase", sample_context)


def test_pipeline_route_errors():
    """route_errors_to_phases maps gate IDs to phase names correctly."""
    from doramagic_shared_utils.llm_adapter import LLMAdapter

    adapter = LLMAdapter(provider_override="mock")
    pipeline = Pipeline(adapter=adapter, model_id="claude-sonnet-4-6")

    errors = [
        {"gate": "SEO-SLUG", "level": "fatal", "message": "bad slug"},
        {"gate": "GEO-FAQ-COUNT", "level": "fatal", "message": "too few FAQs"},
        {"gate": "TRUST-FATAL", "level": "fatal", "message": "no fatal constraint"},
    ]
    routing = pipeline.route_errors_to_phases(errors)

    assert "content" in routing
    assert "faq" in routing
    assert "constraints" in routing


def test_phase_all_phases_have_mock_result():
    """Every registered phase implements mock_result() without raising."""
    from doramagic_web_publisher.phases import PHASES

    for phase in PHASES:
        result = phase.mock_result()
        assert result.phase_name == phase.name
        assert result.success is True
        assert isinstance(result.fields, dict)
        assert len(result.fields) > 0, f"Phase '{phase.name}' mock_result has empty fields"
