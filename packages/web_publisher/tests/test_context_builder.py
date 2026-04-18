"""Tests for _build_context_from_blueprint_id in cli.py.

Tests:
  1. test_context_builder_resolves_bp_009    — real file path resolves correctly (I/O)
  2. test_context_builder_rejects_nonexistent — nonexistent id raises FileNotFoundError
  3. test_context_builder_stubs_creator_proof — QA Proof stub has correct structure
"""

from __future__ import annotations

import pytest


class TestContextBuilder:
    """Tests for _build_context_from_blueprint_id."""

    def test_context_builder_resolves_bp_009(self):
        """Real bp-009 files resolve to a valid PhaseContext."""
        from doramagic_web_publisher.cli import _build_context_from_blueprint_id

        ctx = _build_context_from_blueprint_id("finance-bp-009", dry_run=False, mock_mode=False)

        # Manifest is populated
        assert ctx.manifest is not None
        assert ctx.manifest.blueprint_id == "finance-bp-009"
        assert ctx.manifest.blueprint_source == "zvtvz/zvt"
        # 40-char commit hash
        assert len(ctx.manifest.blueprint_commit) == 40
        assert ctx.manifest.blueprint_commit == "f971f00c2181bc7d7fb7987a7875d4ec5960881a"

        # Blueprint is loaded
        assert isinstance(ctx.blueprint, dict)
        assert "applicability" in ctx.blueprint or "stages" in ctx.blueprint

        # Constraints are loaded (LATEST.jsonl has items)
        assert isinstance(ctx.constraints, list)
        assert len(ctx.constraints) > 0

        # Crystal IR is loaded
        assert isinstance(ctx.crystal_ir, dict)
        assert "user_intent" in ctx.crystal_ir or "crystal_id" in ctx.crystal_ir

        # Seed content is loaded
        assert isinstance(ctx.seed_content, str)
        assert len(ctx.seed_content) > 100  # should be substantial

        # Creator proof is stubbed (at least 1 entry)
        assert isinstance(ctx.creator_proof, list)
        assert len(ctx.creator_proof) >= 1

    def test_context_builder_accepts_short_id(self):
        """Short 'bp-009' format is also accepted (gets prefixed to 'finance-bp-009')."""
        from doramagic_web_publisher.cli import _build_context_from_blueprint_id

        ctx = _build_context_from_blueprint_id("bp-009", dry_run=True, mock_mode=False)
        assert ctx.manifest.blueprint_id == "finance-bp-009"
        assert ctx.dry_run is True

    def test_context_builder_rejects_nonexistent(self):
        """Nonexistent blueprint_id raises FileNotFoundError with path hint."""
        from doramagic_web_publisher.cli import _build_context_from_blueprint_id

        with pytest.raises(FileNotFoundError) as exc_info:
            _build_context_from_blueprint_id("bp-999-nonexistent", dry_run=False, mock_mode=False)

        err_msg = str(exc_info.value)
        # Error should mention the attempted ID or path
        assert (
            "bp-999-nonexistent" in err_msg
            or "finance-bp-999-nonexistent" in err_msg
            or "source" in err_msg.lower()
        )

    def test_context_builder_stubs_creator_proof(self):
        """QA Proof stub has the required structure."""
        from doramagic_web_publisher.cli import _build_context_from_blueprint_id

        ctx = _build_context_from_blueprint_id("finance-bp-009", dry_run=False, mock_mode=False)

        proof = ctx.creator_proof
        assert isinstance(proof, list)
        assert len(proof) >= 1

        entry = proof[0]
        # Required fields per evaluator schema
        assert "model" in entry
        assert "host" in entry
        assert "evidence_type" in entry
        assert "evidence_url" in entry
        assert "tested_at" in entry
        assert "summary" in entry
        assert "summary_en" in entry

        # Stub-specific values
        assert entry["model"] == "MiniMax-M2.7-highspeed"
        assert entry["host"] == "claude_code"
        assert entry["tested_at"] == "2026-04-18"
        assert len(entry["summary"]) > 0
        assert len(entry["summary_en"]) > 0
