"""Tests for the Assembler.

Verifies:
  1. All SOP §1.2 field groups (A-L) are present in assembled package
  2. Provenance (group B) comes from manifest, not LLM
  3. Seed content (group C) comes from ctx
  4. Missing phase results raise AssemblyError
  5. validate_structure() catches missing top-level fields
"""

from __future__ import annotations

import pytest
from doramagic_web_publisher.assembler import Assembler
from doramagic_web_publisher.errors import AssemblyError


def test_assembler_produces_all_required_fields(sample_package):
    """Assembled package has all top-level SOP §1.2 required fields."""
    required_fields = [
        # Group A
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
        # Group B
        "blueprint_id",
        "blueprint_source",
        "blueprint_commit",
        # Group C
        "seed_content",
        # Group D
        "constraints",
        # Group E
        "known_gaps",
        # Group F
        "faqs",
        # Group G
        "changelog",
        "changelog_en",
        "contributors",
        # Group H
        "sample_output",
        "applicable_scenarios",
        "inapplicable_scenarios",
        "host_adapters",
        # Group I
        "required_inputs",
        # Group J
        "creator_proof",
        "model_compatibility",
        # Group K
        "tier",
        "is_flagship",
        "parent_flagship_slug",
        # Group L
        "core_keywords",
        "og_image_fields",
    ]
    for field in required_fields:
        assert field in sample_package, f"Missing required field: {field}"


def test_assembler_provenance_from_manifest(sample_package, sample_manifest):
    """Group B fields come from manifest, not from LLM output."""
    assert sample_package["blueprint_id"] == sample_manifest.blueprint_id
    assert sample_package["blueprint_source"] == sample_manifest.blueprint_source
    assert sample_package["blueprint_commit"] == sample_manifest.blueprint_commit


def test_assembler_seed_from_context(sample_package, sample_context):
    """Group C (seed_content) comes from ctx.seed_content."""
    assert sample_package["seed_content"] == sample_context.seed_content
    assert "doramagic.ai/r/" in sample_package["seed_content"]


def test_assembler_constraints_non_empty(sample_package):
    """Group D: constraints list is non-empty."""
    assert len(sample_package["constraints"]) >= 1
    c = sample_package["constraints"][0]
    assert "constraint_id" in c
    assert c["severity"] in {"fatal", "critical", "high"}


def test_assembler_faqs_count(sample_package):
    """Group F: faqs has 5-8 entries."""
    count = len(sample_package["faqs"])
    assert 5 <= count <= 8, f"faqs count {count} not in [5, 8]"


def test_assembler_tier_valid(sample_package):
    """Group K: tier is 'standard' or 'verified' (never 'battle_tested')."""
    assert sample_package["tier"] in {"standard", "verified"}


def test_assembler_core_keywords_count(sample_package):
    """Group L: core_keywords has 5-10 entries."""
    count = len(sample_package["core_keywords"])
    assert 5 <= count <= 10, f"core_keywords count {count} not in [5, 10]"


def test_assembler_og_image_fields_present(sample_package):
    """Group L: og_image_fields has all required sub-fields."""
    ogf = sample_package["og_image_fields"]
    for key in [
        "headline",
        "headline_en",
        "stat_primary",
        "stat_primary_en",
        "stat_secondary",
        "stat_secondary_en",
    ]:
        assert key in ogf, f"og_image_fields missing '{key}'"


def test_assembler_missing_content_phase_raises(sample_context):
    """AssemblyError raised if content phase result is missing."""
    assembler = Assembler()
    # Don't add content result — only add others to keep other phases "present"
    from doramagic_web_publisher.phases.constraints import ConstraintsPhase
    from doramagic_web_publisher.phases.evaluator import EvaluatorPhase
    from doramagic_web_publisher.phases.faq import FaqPhase

    sample_context.results["constraints"] = ConstraintsPhase().mock_result()
    sample_context.results["faq"] = FaqPhase().mock_result()
    sample_context.results["evaluator"] = EvaluatorPhase().mock_result()
    # content is deliberately missing

    with pytest.raises(AssemblyError) as exc_info:
        assembler.assemble(sample_context)
    assert "content.slug" in str(exc_info.value)


def test_assembler_missing_seed_content_raises(
    sample_context,
    mock_content_result,
    mock_constraints_result,
    mock_faq_result,
    mock_evaluator_result,
):
    """AssemblyError raised if seed_content is empty."""
    sample_context.seed_content = ""  # clear seed
    sample_context.results["content"] = mock_content_result
    sample_context.results["constraints"] = mock_constraints_result
    sample_context.results["faq"] = mock_faq_result
    sample_context.results["evaluator"] = mock_evaluator_result

    assembler = Assembler()
    with pytest.raises(AssemblyError) as exc_info:
        assembler.assemble(sample_context)
    assert "seed_content" in str(exc_info.value)


def test_assembler_validate_structure_clean(sample_package):
    """validate_structure returns no issues for a valid package."""
    assembler = Assembler()
    issues = assembler.validate_structure(sample_package)
    assert issues == [], f"Unexpected structure issues: {issues}"


def test_assembler_validate_structure_detects_missing(sample_package):
    """validate_structure detects missing top-level fields."""
    assembler = Assembler()
    del sample_package["slug"]
    del sample_package["faqs"]

    issues = assembler.validate_structure(sample_package)
    issue_text = " ".join(issues)
    assert "slug" in issue_text
    assert "faqs" in issue_text


# ---- Fix #3 Static Injection Tests ----


def test_assembler_injects_host_adapters_from_ir(
    sample_context,
    mock_content_result,
    mock_constraints_result,
    mock_faq_result,
    mock_evaluator_result,
):
    """host_adapters comes from Crystal IR, not evaluator."""
    sample_context.results["content"] = mock_content_result
    sample_context.results["constraints"] = mock_constraints_result
    sample_context.results["faq"] = mock_faq_result
    sample_context.results["evaluator"] = mock_evaluator_result

    assembler = Assembler()
    package = assembler.assemble(sample_context)

    # host_adapters should come from crystal_ir (set in sample_context fixture)
    assert "host_adapters" in package
    assert len(package["host_adapters"]) >= 1
    hosts = [ha["host"] for ha in package["host_adapters"]]
    # sample_context has openclaw and claude_code in crystal_ir.host_adapters
    assert "openclaw" in hosts or "claude_code" in hosts


def test_assembler_injects_creator_proof_passthrough(
    sample_context,
    mock_content_result,
    mock_constraints_result,
    mock_faq_result,
    mock_evaluator_result,
):
    """creator_proof comes from ctx, not evaluator."""
    # Set a specific creator_proof on the context
    sample_context.creator_proof = [
        {
            "model": "test-model",
            "host": "openclaw",
            "evidence_type": "trace_url",
            "evidence_url": "https://example.com/trace-123",
            "tested_at": "2026-04-18",
            "summary": "测试证明",
            "summary_en": "Test proof",
        }
    ]
    sample_context.results["content"] = mock_content_result
    sample_context.results["constraints"] = mock_constraints_result
    sample_context.results["faq"] = mock_faq_result
    sample_context.results["evaluator"] = mock_evaluator_result

    assembler = Assembler()
    package = assembler.assemble(sample_context)

    assert package["creator_proof"] == sample_context.creator_proof
    assert package["creator_proof"][0]["model"] == "test-model"
    assert package["creator_proof"][0]["evidence_url"] == "https://example.com/trace-123"


def test_assembler_derives_sample_output_from_first_proof(
    sample_context,
    mock_content_result,
    mock_constraints_result,
    mock_faq_result,
    mock_evaluator_result,
):
    """sample_output is derived from creator_proof[0]."""
    sample_context.creator_proof = [
        {
            "model": "test-model",
            "host": "openclaw",
            "evidence_type": "trace_url",
            "evidence_url": "https://example.com/trace-456",
            "tested_at": "2026-04-18",
            "summary": "测试输出摘要",
            "summary_en": "Test output summary",
        }
    ]
    sample_context.results["content"] = mock_content_result
    sample_context.results["constraints"] = mock_constraints_result
    sample_context.results["faq"] = mock_faq_result
    sample_context.results["evaluator"] = mock_evaluator_result

    assembler = Assembler()
    package = assembler.assemble(sample_context)

    so = package["sample_output"]
    assert so["format"] == "trace_url"  # from evidence_type
    assert so["primary_url"] == "https://example.com/trace-456"  # from evidence_url
    assert so["text_preview"] is None


def test_assembler_computes_og_stat_numbers(
    sample_context,
    mock_content_result,
    mock_constraints_result,
    mock_faq_result,
    mock_evaluator_result,
):
    """og stat fields are computed from constraint counts."""
    sample_context.results["content"] = mock_content_result
    sample_context.results["constraints"] = mock_constraints_result
    sample_context.results["faq"] = mock_faq_result
    sample_context.results["evaluator"] = mock_evaluator_result

    assembler = Assembler()
    package = assembler.assemble(sample_context)

    ogf = package["og_image_fields"]
    # stat_primary format: "N 条防坑规则"
    assert "条防坑规则" in ogf["stat_primary"]
    assert any(ch.isdigit() for ch in ogf["stat_primary"])

    # stat_primary_en format: "N pitfall rules"
    assert "pitfall rules" in ogf["stat_primary_en"]
    assert any(ch.isdigit() for ch in ogf["stat_primary_en"])

    # stat_secondary format: "N 条 FATAL · M 处源码"
    assert "FATAL" in ogf["stat_secondary"]
    assert "处源码" in ogf["stat_secondary"]

    # stat_secondary_en format: "N FATAL · M source locations"
    assert "FATAL" in ogf["stat_secondary_en"]
    assert "source locations" in ogf["stat_secondary_en"]

    # headline should come from LLM (evaluator mock_result)
    assert ogf["headline"] != ""
    assert ogf["headline_en"] != ""
