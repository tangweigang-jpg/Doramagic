"""Regression tests for constraint_synthesis recovery paths.

Covers 7 real MiniMax output shape variants observed across 10-hour batch run
and the core recovery/normalization functions.

Fixtures (5 real raw dumps):
  bp068.txt  — 56-item nested {id, original, modified} shape
  bp069.txt  — 35-item markdown report (kind= prefix style)
  bp079.txt  — 20-item multi-fenced-block variant
  bp084.txt  — 12-item backtick markdown style
  bp085.txt  — 102-item flat {id, kind} shape (no severity)
"""

from __future__ import annotations

from pathlib import Path

import pytest
from doramagic_constraint_agent.sop.constraint_schemas_v2 import (
    ConstraintSynthesisResult,
    SynthesizedConstraint,
)
from doramagic_constraint_agent.sop.constraint_synthesis import (
    _apply_synthesis,
    _normalize_synthesis_item,
    _parse_synthesis_from_markdown,
    _try_extract_synthesis_result,
)

# ── Absolute path to fixture directory ──────────────────────────────────────
_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "synthesis_raw"

# ============================================================================
# T1 — _try_extract_synthesis_result with real raw fixture files
# ============================================================================


class TestTryExtractSynthesisResult:
    """T1: Parse real raw dumps produced by MiniMax during batch runs."""

    @pytest.mark.parametrize(
        "fixture_file, expected_count",
        [
            ("bp068.txt", 56),  # nested {id, original, modified} shape
            ("bp069.txt", 35),  # markdown report with kind= prefix sections
            ("bp079.txt", 20),  # multi-fenced JSON blocks variant
            ("bp084.txt", 12),  # backtick markdown style
            ("bp085.txt", 102),  # flat {id, kind} shape without severity field
        ],
    )
    def test_fixture_parsed_correctly(self, fixture_file: str, expected_count: int) -> None:
        """Each real raw dump must parse to the expected item count."""
        raw_text = (_FIXTURE_DIR / fixture_file).read_text(encoding="utf-8")
        result = _try_extract_synthesis_result(raw_text)

        assert result is not None, (
            f"{fixture_file}: _try_extract_synthesis_result returned None "
            f"(expected {expected_count} items)"
        )
        assert isinstance(result, ConstraintSynthesisResult)
        assert len(result.reviewed_constraints) == expected_count, (
            f"{fixture_file}: got {len(result.reviewed_constraints)} items, "
            f"expected {expected_count}"
        )

    def test_each_item_has_required_fields(self) -> None:
        """All items in a parsed fixture have the four required fields."""
        raw_text = (_FIXTURE_DIR / "bp068.txt").read_text(encoding="utf-8")
        result = _try_extract_synthesis_result(raw_text)
        assert result is not None

        for item in result.reviewed_constraints:
            assert isinstance(item.original_index, int)
            assert item.constraint_kind in (
                "domain_rule",
                "resource_boundary",
                "operational_lesson",
                "architecture_guardrail",
                "claim_boundary",
                "rationalization_guard",
            )
            assert item.severity in ("fatal", "high", "medium", "low")
            assert isinstance(item.upgrade_reason, str)


# ============================================================================
# T2 — _normalize_synthesis_item shape variants
# ============================================================================


class TestNormalizeSynthesisItem:
    """T2: 7 MiniMax shape variants must all be coerced to the canonical fields."""

    def _assert_canonical_fields(
        self, result: object, expected_index: int, expected_kind: str
    ) -> None:
        assert isinstance(result, dict), f"Expected dict, got {type(result)}"
        assert result["original_index"] == expected_index
        assert result["constraint_kind"] == expected_kind
        assert "severity" in result
        assert "upgrade_reason" in result

    def test_shape1_standard_flat(self) -> None:
        """Shape 1: canonical flat dict passes through unchanged."""
        item = {
            "original_index": 5,
            "constraint_kind": "domain_rule",
            "severity": "high",
            "upgrade_reason": "test reason",
        }
        result = _normalize_synthesis_item(item)
        self._assert_canonical_fields(result, 5, "domain_rule")
        assert result["severity"] == "high"
        assert result["upgrade_reason"] == "test reason"

    def test_shape2_id_instead_of_original_index(self) -> None:
        """Shape 2: 'id' field mapped to 'original_index'."""
        item = {"id": 5, "constraint_kind": "domain_rule", "severity": "high"}
        result = _normalize_synthesis_item(item)
        self._assert_canonical_fields(result, 5, "domain_rule")

    def test_shape3_nested_modified(self) -> None:
        """Shape 3: nested {original, modified} flattened to top-level fields."""
        item = {
            "id": 5,
            "original": {"kind": "operational_lesson"},
            "modified": {"kind": "domain_rule", "severity": "high"},
        }
        result = _normalize_synthesis_item(item)
        self._assert_canonical_fields(result, 5, "domain_rule")
        assert result["severity"] == "high"

    def test_shape4_nested_proposed_current(self) -> None:
        """Shape 4: nested {current, proposed} flattened; proposed takes precedence."""
        item = {
            "id": 5,
            "current": {"kind": "operational_lesson"},
            "proposed": {"kind": "domain_rule", "severity": "high"},
        }
        result = _normalize_synthesis_item(item)
        self._assert_canonical_fields(result, 5, "domain_rule")
        assert result["severity"] == "high"

    def test_shape5_flat_with_upgrade_kind(self) -> None:
        """Shape 5: {kind, upgrade_kind} — upgrade_kind becomes constraint_kind."""
        item = {
            "id": 5,
            "kind": "operational_lesson",
            "upgrade_kind": "domain_rule",
            "severity": "high",
        }
        result = _normalize_synthesis_item(item)
        self._assert_canonical_fields(result, 5, "domain_rule")
        assert result["severity"] == "high"

    def test_shape6_only_kind_no_severity_defaults_medium(self) -> None:
        """Shape 6: when severity is absent, defaults to 'medium'."""
        item = {"id": 5, "kind": "domain_rule"}
        result = _normalize_synthesis_item(item)
        self._assert_canonical_fields(result, 5, "domain_rule")
        assert result["severity"] == "medium"

    def test_shape7_updated_new_variant(self) -> None:
        """Shape 7: nested 'new' key flattened to top-level fields."""
        item = {"id": 5, "new": {"kind": "domain_rule", "severity": "high"}}
        result = _normalize_synthesis_item(item)
        self._assert_canonical_fields(result, 5, "domain_rule")
        assert result["severity"] == "high"

    def test_non_dict_passthrough(self) -> None:
        """Non-dict items are returned unchanged."""
        assert _normalize_synthesis_item("not a dict") == "not a dict"
        assert _normalize_synthesis_item(42) == 42
        assert _normalize_synthesis_item(None) is None

    def test_upgrade_reason_defaults_to_empty_string(self) -> None:
        """upgrade_reason defaults to empty string when absent."""
        item = {"id": 3, "constraint_kind": "domain_rule", "severity": "low"}
        result = _normalize_synthesis_item(item)
        assert result["upgrade_reason"] == ""


# ============================================================================
# T3 — _parse_synthesis_from_markdown format variants
# ============================================================================


class TestParseSynthesisFromMarkdown:
    """T3: Three markdown formats LLM produces when JSON extraction fails."""

    def test_style1_kind_equals_prefix(self) -> None:
        """Style 1: ### [N] kind=X → kind=Y (severity=Z)"""
        text = """
### [13] kind=claim_boundary → kind=domain_rule (severity=fatal)
- upgrade_reason: reason 1

### [14] kind=operational_lesson → kind=architecture_guardrail (severity=high)
- upgrade_reason: reason 2

### [15] kind=claim_boundary → kind=domain_rule (severity=medium)
- upgrade_reason: reason 3
"""
        result = _parse_synthesis_from_markdown(text)

        assert result is not None
        assert isinstance(result, ConstraintSynthesisResult)
        assert len(result.reviewed_constraints) == 3

        indices = {item.original_index for item in result.reviewed_constraints}
        assert indices == {13, 14, 15}

        idx13 = next(i for i in result.reviewed_constraints if i.original_index == 13)
        assert idx13.constraint_kind == "domain_rule"
        assert idx13.severity == "fatal"

        idx14 = next(i for i in result.reviewed_constraints if i.original_index == 14)
        assert idx14.constraint_kind == "architecture_guardrail"
        assert idx14.severity == "high"

    def test_style2_backtick_format(self) -> None:
        """Style 2: **[N]** `old_kind` → **`new_kind`**"""
        text = """
**[13]** `operational_lesson` → **`domain_rule`**
- reason: test 1

**[14]** `claim_boundary` → **`architecture_guardrail`**
- reason: test 2

**[15]** `operational_lesson` → **`domain_rule`**
- reason: test 3
"""
        result = _parse_synthesis_from_markdown(text)

        assert result is not None
        assert len(result.reviewed_constraints) == 3

        indices = {item.original_index for item in result.reviewed_constraints}
        assert indices == {13, 14, 15}

    def test_style3_plain_text_arrow(self) -> None:
        """Style 3: [N] old_kind → new_kind (plain text, no markup)"""
        text = """
[13] operational_lesson → domain_rule
[14] claim_boundary → architecture_guardrail
[15] operational_lesson → domain_rule
"""
        result = _parse_synthesis_from_markdown(text)

        assert result is not None
        assert len(result.reviewed_constraints) == 3

        idx13 = next(i for i in result.reviewed_constraints if i.original_index == 13)
        assert idx13.constraint_kind == "domain_rule"

    def test_no_arrow_returns_none(self) -> None:
        """Text with [N] markers but no arrows yields None."""
        text = """
## Report

[13] This constraint is fine.
[14] This one is also fine.
"""
        result = _parse_synthesis_from_markdown(text)
        assert result is None

    def test_empty_text_returns_none(self) -> None:
        """Empty text yields None."""
        assert _parse_synthesis_from_markdown("") is None

    def test_severity_defaults_to_medium_when_absent(self) -> None:
        """Items without a severity token default to 'medium'."""
        text = "[42] operational_lesson → domain_rule\n"
        result = _parse_synthesis_from_markdown(text)
        assert result is not None
        assert result.reviewed_constraints[0].severity == "medium"

    def test_duplicate_indices_deduplicated(self) -> None:
        """Duplicate [N] entries keep only the first occurrence."""
        text = """
[10] operational_lesson → domain_rule
[10] claim_boundary → architecture_guardrail
"""
        result = _parse_synthesis_from_markdown(text)
        assert result is not None
        indices = [item.original_index for item in result.reviewed_constraints]
        assert indices.count(10) == 1


# ============================================================================
# T4 — _apply_synthesis boundary conditions
# ============================================================================


def _make_merged(kinds: list[str]) -> list[dict]:
    """Helper: build a minimal merged list with the given constraint_kinds."""
    return [{"constraint_kind": k, "severity": "medium"} for k in kinds]


def _make_result(items: list[tuple[int, str, str, str]]) -> ConstraintSynthesisResult:
    """Helper: build a ConstraintSynthesisResult from (idx, kind, severity, reason) tuples."""
    return ConstraintSynthesisResult(
        reviewed_constraints=[
            SynthesizedConstraint(
                original_index=idx,
                constraint_kind=kind,
                severity=sev,
                upgrade_reason=reason,
            )
            for idx, kind, sev, reason in items
        ],
        rebalance_actions=[],
    )


class TestApplySynthesis:
    """T4: _apply_synthesis edge conditions."""

    def test_normal_upgrade_applies_kind_change(self) -> None:
        """T4-1: Soft-kind entry with >5 peers is upgraded to domain_rule."""
        # Need >5 operational_lesson items so QG-02 guard (<=5) does not block
        merged = _make_merged(["operational_lesson"] * 6 + ["domain_rule"])
        result = _make_result([(0, "domain_rule", "high", "should upgrade")])

        changes = _apply_synthesis(merged, result)

        assert changes == 1
        assert merged[0]["constraint_kind"] == "domain_rule"

    def test_qg02_reserve_guard_blocks_depletion(self) -> None:
        """T4-2: When a kind has exactly 5 items, synthesis cannot reduce it further."""
        # Exactly 5 operational_lesson items — guard fires (count <= _MIN_KIND_RESERVE=5)
        merged = _make_merged(["operational_lesson"] * 5)
        result = _make_result([(0, "domain_rule", "high", "blocked")])

        changes = _apply_synthesis(merged, result)

        assert changes == 0
        assert merged[0]["constraint_kind"] == "operational_lesson"

    def test_non_soft_kind_skipped(self) -> None:
        """T4-3: Synthesis targeting an existing domain_rule is rejected."""
        merged = _make_merged(["domain_rule"])
        result = _make_result([(0, "architecture_guardrail", "high", "non-soft skip")])

        changes = _apply_synthesis(merged, result)

        assert changes == 0
        assert merged[0]["constraint_kind"] == "domain_rule"

    def test_severity_synced_even_when_kind_unchanged(self) -> None:
        """T4-4: Severity is updated even if constraint_kind stays the same."""
        # Need >5 entries so guard does not fire; kind unchanged → 0 kind changes
        merged = _make_merged(["operational_lesson"] * 6)
        assert merged[0]["severity"] == "medium"

        # Same kind, different severity
        result = _make_result([(0, "operational_lesson", "fatal", "severity only")])

        changes = _apply_synthesis(merged, result)

        # Kind didn't change → changes == 0
        assert changes == 0
        # But severity was still updated
        assert merged[0]["severity"] == "fatal"

    def test_out_of_bounds_index_ignored(self) -> None:
        """Synthesis items with an index beyond merged length are silently ignored."""
        merged = _make_merged(["operational_lesson"] * 3)
        result = _make_result([(999, "domain_rule", "high", "out of range")])

        changes = _apply_synthesis(merged, result)
        assert changes == 0

    def test_multiple_upgrades_in_single_pass(self) -> None:
        """Multiple valid upgrades in one result all apply correctly."""
        merged = _make_merged(["operational_lesson"] * 10 + ["claim_boundary"] * 10)
        result = _make_result(
            [
                (0, "domain_rule", "high", "upgrade 0"),
                (1, "architecture_guardrail", "high", "upgrade 1"),
                (10, "domain_rule", "fatal", "upgrade 10"),
            ]
        )

        changes = _apply_synthesis(merged, result)

        assert changes == 3
        assert merged[0]["constraint_kind"] == "domain_rule"
        assert merged[1]["constraint_kind"] == "architecture_guardrail"
        assert merged[10]["constraint_kind"] == "domain_rule"


# ============================================================================
# T5 — Negative / malformed input tests
# ============================================================================


class TestNegativeCases:
    """T5: Malformed inputs that must return None, not raise exceptions."""

    def test_completely_random_text_returns_none(self) -> None:
        """T5-1: Garbage text with no JSON or markdown patterns → None."""
        result = _try_extract_synthesis_result(
            "Lorem ipsum dolor sit amet consectetur adipiscing elit "
            "sed do eiusmod tempor incididunt ut labore"
        )
        assert result is None

    def test_json_with_all_wrong_fields_returns_none(self) -> None:
        """T5-2: Valid JSON but no recognisable schema shape → None."""
        result = _try_extract_synthesis_result('{"foo": "bar", "baz": 123, "items": "not a list"}')
        assert result is None

    def test_empty_string_returns_none(self) -> None:
        """Empty input → None."""
        assert _try_extract_synthesis_result("") is None

    def test_json_array_of_scalars_returns_none(self) -> None:
        """JSON array of scalars (not dicts) → None after validation failure."""
        result = _try_extract_synthesis_result("[1, 2, 3, 4, 5]")
        assert result is None

    def test_json_with_empty_reviewed_constraints_still_valid(self) -> None:
        """JSON with reviewed_constraints=[] is a valid (empty) result."""
        result = _try_extract_synthesis_result(
            '{"reviewed_constraints": [], "rebalance_actions": []}'
        )
        assert result is not None
        assert len(result.reviewed_constraints) == 0
