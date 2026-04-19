"""Tests for constraint_enrich.py Patch 18 (resolve_placeholders).

Patch 18 replaces {var} placeholder tokens in validation_threshold with the
real file path from evidence_refs[0]["path"], or clears the threshold and sets
machine_checkable=False when no reliable path is available.
"""

from __future__ import annotations

from doramagic_constraint_agent.sop.constraint_enrich import _patch_resolve_placeholders


class TestPatch18ResolvePlaceholders:
    """Unit tests for _patch_resolve_placeholders."""

    def test_patch18_replaces_placeholder_with_locator(self) -> None:
        """validation_threshold with {file} is replaced by evidence_refs[0].path."""
        constraints = [
            {
                "validation_threshold": "grep {file}",
                "evidence_refs": [{"type": "source_code", "path": "src/foo.py", "line": 12}],
            }
        ]
        count = _patch_resolve_placeholders(constraints)
        assert count == 1
        assert constraints[0]["validation_threshold"] == "grep src/foo.py"

    def test_patch18_clears_threshold_when_no_locator(self) -> None:
        """validation_threshold is cleared and machine_checkable=False with no evidence_refs."""
        constraints = [
            {
                "validation_threshold": "grep {file}",
                "evidence_refs": [],
            }
        ]
        count = _patch_resolve_placeholders(constraints)
        assert count == 1
        assert constraints[0]["validation_threshold"] == ""
        assert constraints[0]["machine_checkable"] is False
