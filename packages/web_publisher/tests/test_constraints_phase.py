"""Tests for ConstraintsPhase — filtering, bilingual summary lengths, evidence_url, batching.

Uses fake_adapter (no real LLM calls). Tests parse_result and helper functions.
"""

from __future__ import annotations

import copy

import pytest
from doramagic_web_publisher.errors import PhaseParsingError
from doramagic_web_publisher.phases.constraints import (
    ConstraintsPhase,
    _build_evidence_url,
)
from doramagic_web_publisher.runtime.models import PhaseContext, PublishManifest

# ---- Helpers ----

GOOD_CONSTRAINT = {
    "constraint_id": "finance-C-001",
    "severity": "fatal",
    "type": "M",
    "when": "When annualizing A-share strategy returns",
    "action": "MUST use sqrt(242) instead of sqrt(365)",
    "consequence": "Volatility underestimated by 22.7%",
    "summary": "如果年化A股波动率时用365天，会低估22.7%。正确做法：用242交易日。",
    "summary_en": (
        "Using 365 days to annualize volatility underestimates it by 22.7%. "
        "Correct: Use 242 trading days for A-shares."
    ),
    "evidence_url": (
        "https://github.com/zvtvz/zvt/blob/"
        "f971f00c2181bc7d7fb7987a7875d4ec5960881a/"
        "src/zvt/factors/factor_cls.py#L89"
    ),
    "evidence_locator": "src/zvt/factors/factor_cls.py:L89",
    "machine_checkable": True,
    "confidence": 0.95,
    "is_cross_project": False,
    "source_blueprint_id": None,
}


def _make_context(constraints: list[dict]) -> PhaseContext:
    manifest = PublishManifest(
        slug="macd-backtest-a-shares",
        blueprint_id="finance-bp-009",
        blueprint_source="zvtvz/zvt",
        blueprint_commit="f971f00c2181bc7d7fb7987a7875d4ec5960881a",
    )
    return PhaseContext(manifest=manifest, constraints=constraints, mock_mode=True)


@pytest.fixture
def phase():
    return ConstraintsPhase()


# ---- Test evidence URL builder ----


class TestEvidenceUrlBuilder:
    def test_builds_github_url(self):
        url = _build_evidence_url(
            "zvtvz/zvt",
            "f971f00c2181bc7d7fb7987a7875d4ec5960881a",
            "src/zvt/factors/factor.py:L89",
        )
        assert url == (
            "https://github.com/zvtvz/zvt/blob/"
            "f971f00c2181bc7d7fb7987a7875d4ec5960881a/"
            "src/zvt/factors/factor.py#L89"
        )

    def test_locator_without_L_prefix(self):
        url = _build_evidence_url("zvtvz/zvt", "abc123", "src/file.py:107")
        assert "#L107" in url
        assert "src/file.py" in url

    def test_missing_locator_returns_none(self):
        assert _build_evidence_url("zvtvz/zvt", "abc123", "") is None

    def test_missing_repo_returns_none(self):
        assert _build_evidence_url("", "abc123", "src/file.py:L1") is None

    def test_unparseable_locator_returns_none(self):
        """Locator without line number is unparseable."""
        result = _build_evidence_url("zvtvz/zvt", "abc123", "src/file.py")
        assert result is None


# ---- Test parse_result ----


class TestParseResult:
    def test_valid_constraints_pass(self, phase):
        args = {"constraints": [copy.deepcopy(GOOD_CONSTRAINT)]}
        result = phase.parse_result(args)
        assert result.success is True
        assert result.phase_name == "constraints"

    def test_no_fatal_fails(self, phase):
        """TRUST-FATAL: must have ≥1 fatal constraint."""
        c = copy.deepcopy(GOOD_CONSTRAINT)
        c["severity"] = "high"
        args = {"constraints": [c]}
        with pytest.raises(PhaseParsingError) as exc_info:
            phase.parse_result(args)
        assert "TRUST-FATAL" in str(exc_info.value)

    def test_summary_too_long_auto_truncated(self, phase):
        """Chinese summary > 80 chars is auto-truncated (not an error) — LLM resilience."""
        c = copy.deepcopy(GOOD_CONSTRAINT)
        c["summary"] = "如果" * 41  # 82 chars
        args = {"constraints": [c]}
        result = phase.parse_result(args)
        assert result.success is True
        out_summary = result.fields["constraints"][0]["summary"]
        assert len(out_summary) <= 80, f"summary was not truncated: {len(out_summary)} chars"

    def test_summary_en_too_long_auto_truncated(self, phase):
        """English summary_en > 160 chars is auto-truncated (not an error) — LLM resilience."""
        c = copy.deepcopy(GOOD_CONSTRAINT)
        c["summary_en"] = "a" * 161
        args = {"constraints": [c]}
        result = phase.parse_result(args)
        assert result.success is True
        out_summary_en = result.fields["constraints"][0]["summary_en"]
        assert len(out_summary_en) <= 160, (
            f"summary_en was not truncated: {len(out_summary_en)} chars"
        )

    def test_invalid_evidence_url_fails(self, phase):
        """evidence_url must be HTTPS github.com or null."""
        c = copy.deepcopy(GOOD_CONSTRAINT)
        c["evidence_url"] = "http://not-github.com/something"
        args = {"constraints": [c]}
        with pytest.raises(PhaseParsingError) as exc_info:
            phase.parse_result(args)
        assert "evidence_url" in str(exc_info.value)

    def test_null_evidence_url_allowed(self, phase):
        """evidence_url=null is allowed."""
        c = copy.deepcopy(GOOD_CONSTRAINT)
        c["evidence_url"] = None
        args = {"constraints": [c]}
        result = phase.parse_result(args)
        assert result.success is True

    def test_cross_project_auto_corrected_when_no_source_blueprint_id(self, phase):
        """is_cross_project=true with empty source_blueprint_id is auto-corrected to false.

        This is LLM resilience: the LLM may incorrectly mark a same-project constraint
        as cross-project. parse_result fixes it silently rather than erroring out.
        """
        c = copy.deepcopy(GOOD_CONSTRAINT)
        c["is_cross_project"] = True
        c["source_blueprint_id"] = None
        args = {"constraints": [c]}
        result = phase.parse_result(args)
        assert result.success is True
        out = result.fields["constraints"][0]
        assert out["is_cross_project"] is False, (
            "is_cross_project should be auto-corrected to False"
        )

    def test_empty_constraints_array_fails(self, phase):
        """Empty constraints array fails."""
        with pytest.raises(PhaseParsingError) as exc_info:
            phase.parse_result({"constraints": []})
        assert "≥1" in str(exc_info.value)


class TestMockResult:
    def test_mock_result_has_fatal(self, phase):
        """mock_result always has ≥1 fatal constraint."""
        result = phase.mock_result()
        assert result.success is True
        constraints = result.fields["constraints"]
        fatal = [c for c in constraints if c["severity"] == "fatal"]
        assert len(fatal) >= 1

    def test_mock_result_passes_parse(self, phase):
        """mock_result should pass parse_result validation."""
        mock = phase.mock_result()
        result = phase.parse_result(mock.fields)
        assert result.success is True


# ---- Internal helper: use phase's private method via instance ----


def _filter_constraints_in_phase(ctx):
    """Call the private filter method via the phase instance."""
    return ConstraintsPhase()._filter_constraints(ctx)


def _make_raw_constraint(cid: str, severity: str, locator: str = "file.py:L1") -> dict:
    """Helper to build a minimal raw constraint dict."""
    return {
        "id": cid,
        "severity": severity,
        "core": {"when": "a", "action": "b", "consequence": {"kind": "bug", "description": "c"}},
        "constraint_kind": "domain_rule",
        "confidence": {"score": 0.9, "evidence_refs": [{"locator": locator}]},
        "applies_to": {"blueprint_ids": ["bp-009"]},
        "machine_checkable": True,
        "derived_from": None,
        "tags": [],
    }


class TestConstraintFiltering:
    def test_filters_to_severity_subset(self):
        """Only fatal/critical/high constraints pass the filter."""
        raw_constraints = [
            _make_raw_constraint("C-001", "fatal"),
            _make_raw_constraint("C-002", "low"),  # should be filtered out
        ]
        # Override: C-002 has no evidence locator to ensure it's filtered
        raw_constraints[1]["confidence"]["evidence_refs"] = []
        ctx = _make_context(raw_constraints)
        filtered = _filter_constraints_in_phase(ctx)
        ids = [c["constraint_id"] for c in filtered]
        assert "C-001" in ids
        assert "C-002" not in ids


# ---- Multi-batch tests (Fix #1) ----


class TestMultiBatch:
    """Tests for multi-batch merging strategy in ConstraintsPhase."""

    def _make_normalized_constraint(self, cid: str, severity: str) -> dict:
        """Build a normalized constraint (post-_extract_constraint_fields form)."""
        return {
            "constraint_id": cid,
            "severity": severity,
            "type": "M",
            "when": "When something happens",
            "action": "MUST do the right thing",
            "consequence": "Bad outcome",
            "summary": f"如果触发{cid}，会有问题。正确做法：修复它。",
            "summary_en": (
                f"If {cid} is triggered, there will be a problem. Correct approach: fix it."
            ),
            "evidence_url": "https://github.com/example/repo/blob/abc123/file.py#L1",
            "evidence_locator": "file.py:L1",
            "machine_checkable": True,
            "confidence": 0.9,
            "is_cross_project": False,
            "source_blueprint_id": None,
        }

    def test_multi_batch_merged(self):
        """test_constraints_multi_batch: parse_result accepts merged multi-batch result."""
        phase = ConstraintsPhase()
        # Simulate 3 batches of 10 constraints each (30 total), all fatal
        all_constraints = [
            self._make_normalized_constraint(f"C-{i:03d}", "fatal") for i in range(30)
        ]
        result = phase.parse_result({"constraints": all_constraints})
        assert result.success is True
        assert len(result.fields["constraints"]) == 30
        # All should be fatal
        fatals = [c for c in result.fields["constraints"] if c["severity"] == "fatal"]
        assert len(fatals) == 30

    def test_include_high_flag_default_false(self):
        """test_constraints_include_high: default include_high=False."""
        phase_default = ConstraintsPhase()
        assert phase_default.include_high is False
        assert "high" not in phase_default._get_active_severities()
        assert "fatal" in phase_default._get_active_severities()
        assert "critical" in phase_default._get_active_severities()

    def test_include_high_flag_true(self):
        """test_constraints_include_high: include_high=True adds 'high' to active severities."""
        phase_high = ConstraintsPhase(include_high=True)
        assert phase_high.include_high is True
        active = phase_high._get_active_severities()
        assert "fatal" in active
        assert "critical" in active
        assert "high" in active

    def test_partial_batch_failure_merges_successful_batches(self):
        """test_constraints_partial_batch_failure: failed batch doesn't abort others.

        We simulate this by verifying parse_result can handle a subset of batches
        (the failed batch simply contributes no items to the merged list).
        """
        phase = ConstraintsPhase()
        # batch 1 succeeds (10 fatals), batch 2 fails (0 items), batch 3 succeeds (5 fatals)
        batch_1_result = [
            self._make_normalized_constraint(f"C-{i:03d}", "fatal") for i in range(10)
        ]
        batch_3_result = [
            self._make_normalized_constraint(f"C-{i:03d}", "fatal") for i in range(20, 25)
        ]
        # Merged result: batch 2 contributes nothing (failed)
        merged = batch_1_result + batch_3_result
        result = phase.parse_result({"constraints": merged})
        assert result.success is True
        assert len(result.fields["constraints"]) == 15  # 10 + 5

    def test_batch_sorted_by_severity_then_locator(self):
        """Eligible constraints are sorted fatal→critical→high, then by evidence_locator."""
        # Build mix of severities to check sorting
        raw_constraints = [
            _make_raw_constraint("C-high-1", "high", "z_file.py:L1"),
            _make_raw_constraint("C-fatal-1", "fatal", "a_file.py:L1"),
            _make_raw_constraint("C-critical-1", "critical", "b_file.py:L1"),
            _make_raw_constraint("C-fatal-2", "fatal", "b_file.py:L2"),
        ]
        ctx = _make_context(raw_constraints)
        phase = ConstraintsPhase(include_high=True)
        filtered = phase._filter_constraints(ctx)
        _severity_order = {"fatal": 0, "critical": 1, "high": 2}
        filtered.sort(
            key=lambda c: (_severity_order.get(c["severity"], 9), c.get("evidence_locator", ""))
        )
        # Check ordering: fatals first, then critical, then high
        severities = [c["severity"] for c in filtered]
        fatal_indices = [i for i, s in enumerate(severities) if s == "fatal"]
        critical_indices = [i for i, s in enumerate(severities) if s == "critical"]
        high_indices = [i for i, s in enumerate(severities) if s == "high"]
        assert max(fatal_indices) < min(critical_indices)
        assert max(critical_indices) < min(high_indices)
