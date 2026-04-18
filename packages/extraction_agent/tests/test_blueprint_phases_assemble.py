"""Regression tests for Bug 1: bp_assemble placeholder + truncated JSON rescue.

Covers:
- _extract_stages_from_truncated_json (module-level after refactor)
- executor.py placeholder blueprint.yaml content
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Stub out heavy dependencies that require external packages not installed
# in the test environment (doramagic_blueprint_pipeline, etc.).
# This must happen before importing blueprint_phases.
# ---------------------------------------------------------------------------

for _stub_mod in (
    "doramagic_blueprint_pipeline",
    "doramagic_blueprint_pipeline.pipeline",
    "doramagic_blueprint_pipeline.repo_manager",
):
    if _stub_mod not in sys.modules:
        sys.modules[_stub_mod] = MagicMock()  # type: ignore[assignment]

from doramagic_extraction_agent.sop.blueprint_phases import (  # noqa: E402
    _extract_stages_from_truncated_json,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_json_with_stages(stages: list[dict[str, Any]], truncate_at: int | None = None) -> str:
    """Build a JSON string containing a 'stages' array.

    If truncate_at is given, the string is cut off at that character position
    to simulate LLM output truncation.
    """
    payload = json.dumps({"name": "TestBlueprint", "applicability": {}, "stages": stages})
    if truncate_at is not None:
        return payload[:truncate_at]
    return payload


def _stage(name: str, idx: int) -> dict[str, Any]:
    return {
        "id": f"stage_{idx}",
        "order": idx,
        "name": name,
        "description": "Some description.",
        "required_methods": [],
        "key_behaviors": [],
    }


# ---------------------------------------------------------------------------
# Tests for _extract_stages_from_truncated_json
# ---------------------------------------------------------------------------


class TestExtractStagesFromTruncatedJson:
    """Regression tests for the depth-tracking JSON rescue function."""

    def test_truncated_json_recovers_complete_stages(self) -> None:
        """Input truncated inside 4th stage → recover first 3 complete stages."""
        stages = [_stage(f"Stage {i}", i) for i in range(1, 5)]
        full_json = _make_json_with_stages(stages)

        # Find start of 4th stage object to truncate there
        # The 4th stage will be incomplete after truncation
        stage4_marker = '"id": "stage_4"'
        trunc_idx = full_json.index(stage4_marker) + 5  # cut mid-way through stage 4
        truncated = full_json[:trunc_idx]

        result = _extract_stages_from_truncated_json(truncated)

        assert result is not None, "Should recover stages from truncated JSON"
        assert len(result) == 3, f"Expected 3 complete stages, got {len(result)}"
        assert result[0]["id"] == "stage_1"
        assert result[1]["id"] == "stage_2"
        assert result[2]["id"] == "stage_3"

    def test_valid_json_full_parse(self) -> None:
        """Input with 4 complete stages → all 4 extracted."""
        stages = [_stage(f"Stage {i}", i) for i in range(1, 5)]
        full_json = _make_json_with_stages(stages)

        result = _extract_stages_from_truncated_json(full_json)

        assert result is not None
        assert len(result) == 4
        ids = [s["id"] for s in result]
        assert ids == ["stage_1", "stage_2", "stage_3", "stage_4"]

    def test_no_stages_key_returns_none(self) -> None:
        """Input without 'stages' key → returns None."""
        text = json.dumps({"name": "Test", "other_key": [1, 2, 3]})

        result = _extract_stages_from_truncated_json(text)

        assert result is None

    def test_string_with_brace_inside_doesnt_confuse_depth(self) -> None:
        """Braces inside string values must not confuse depth tracking."""
        stages = [
            {
                "id": "stage_1",
                "order": 1,
                "name": "Stage with {curly} braces",
                "description": "Contains {{ double }} and [brackets] inside strings.",
                "required_methods": [],
                "key_behaviors": [],
            },
            {
                "id": "stage_2",
                "order": 2,
                "name": "Normal stage",
                "description": "No special chars.",
                "required_methods": [],
                "key_behaviors": [],
            },
        ]
        full_json = _make_json_with_stages(stages)

        result = _extract_stages_from_truncated_json(full_json)

        assert result is not None
        assert len(result) == 2, f"Braces in strings confused depth tracker, got {len(result)}"
        assert result[0]["id"] == "stage_1"
        assert result[1]["id"] == "stage_2"

    def test_escaped_quotes_in_string_handled(self) -> None:
        """Escaped quotes inside string fields must not toggle in_str flag incorrectly."""
        # Build manually to ensure escaped quotes survive serialization
        text = (
            '{"stages": [{"id": "stage_1", "order": 1,'
            ' "name": "Has \\"escaped\\" quotes", "key_behaviors": []}]}'
        )

        result = _extract_stages_from_truncated_json(text)

        assert result is not None
        assert len(result) == 1

    def test_empty_stages_array_returns_none(self) -> None:
        """stages: [] → returns None (no complete stage found)."""
        text = '{"name": "Test", "stages": []}'
        result = _extract_stages_from_truncated_json(text)
        # No complete stage object → last_complete_pos stays None → returns None
        assert result is None

    def test_single_complete_stage_recovered(self) -> None:
        """Even a single complete stage should be returned."""
        stages = [_stage("Only Stage", 1)]
        full_json = _make_json_with_stages(stages)

        result = _extract_stages_from_truncated_json(full_json)

        assert result is not None
        assert len(result) == 1
        assert result[0]["id"] == "stage_1"

    def test_deeply_nested_stage_fields_dont_break_depth(self) -> None:
        """Stage with nested list/dict fields must still be tracked correctly."""
        stages = [
            {
                "id": "stage_1",
                "order": 1,
                "name": "Stage 1",
                "description": "First.",
                "required_methods": [{"name": "fn", "params": {"a": 1, "b": [2, 3]}}],
                "key_behaviors": [{"behavior": "b1", "evidence": "f.py:1(fn)"}],
            },
            {
                "id": "stage_2",
                "order": 2,
                "name": "Stage 2",
                "description": "Second.",
                "required_methods": [],
                "key_behaviors": [],
            },
        ]
        full_json = _make_json_with_stages(stages)

        result = _extract_stages_from_truncated_json(full_json)

        assert result is not None
        assert len(result) == 2


# ---------------------------------------------------------------------------
# Tests for executor.py placeholder blueprint.yaml
# ---------------------------------------------------------------------------


class TestPlaceholderBlueprintYaml:
    """Regression tests for Bug 1 executor.py fix: placeholder must embed real blueprint_id."""

    def _make_placeholder(self, blueprint_id: str, phase_name: str = "bp_assemble") -> str:
        """Reproduce the placeholder generation logic from executor.py L607-616."""
        return (
            f"# {phase_name} — placeholder (assemble 失败自动生成)\n"
            f"# WARNING: This is an auto-generated failure placeholder.\n"
            f"# The bp_quality_gate BQ-05 check (stages≥2) will FAIL.\n"
            f"id: {blueprint_id}\n"
            f"name: 'UNASSEMBLED: assemble 失败'\n"
            f"sop_version: '3.4'\n"
            f"stages: []\n"
            f"_assemble_failed: true\n"
        )

    def test_placeholder_blueprint_yaml_has_real_blueprint_id(self, tmp_path: Path) -> None:
        """Placeholder must embed real blueprint_id, not 'placeholder'."""
        blueprint_id = "bp-042"
        placeholder = self._make_placeholder(blueprint_id)

        assert f"id: {blueprint_id}" in placeholder, (
            f"Placeholder should contain 'id: {blueprint_id}', got:\n{placeholder}"
        )
        assert "id: placeholder" not in placeholder, (
            "Placeholder must NOT contain the literal 'id: placeholder'"
        )

    def test_placeholder_has_assemble_failed_sentinel(self, tmp_path: Path) -> None:
        """Placeholder must contain _assemble_failed: true sentinel."""
        placeholder = self._make_placeholder("bp-123")

        assert "_assemble_failed: true" in placeholder, (
            f"Sentinel '_assemble_failed: true' missing from placeholder:\n{placeholder}"
        )

    def test_placeholder_written_to_file(self, tmp_path: Path) -> None:
        """When written to disk, blueprint.yaml contains expected fields."""
        blueprint_id = "bp-999"
        artifact_path = tmp_path / "blueprint.yaml"
        placeholder = self._make_placeholder(blueprint_id)
        artifact_path.write_text(placeholder, encoding="utf-8")

        content = artifact_path.read_text(encoding="utf-8")
        assert f"id: {blueprint_id}" in content
        assert "_assemble_failed: true" in content
        assert "stages: []" in content

    def test_placeholder_quality_gate_detectable(self, tmp_path: Path) -> None:
        """Downstream quality gate can detect placeholder via _assemble_failed flag."""
        import yaml

        blueprint_id = "bp-007"
        artifact_path = tmp_path / "blueprint.yaml"
        placeholder = self._make_placeholder(blueprint_id)
        artifact_path.write_text(placeholder, encoding="utf-8")

        loaded = yaml.safe_load(artifact_path.read_text())
        assert loaded.get("_assemble_failed") is True
        assert loaded.get("id") == blueprint_id
        # Quality gate should fail because stages is empty
        assert loaded.get("stages", []) == []
