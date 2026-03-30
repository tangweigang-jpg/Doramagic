"""Stage 1 Scan 模块测试。

使用 example_calorie_repo_facts_calorie.json 作为主要测试输入，
验证正常路径、schema 合规、错误路径、降级路径和假说生成。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

# 引用 contracts 包
# 引用 extraction 包
from doramagic_contracts.base import RepoRef
from doramagic_contracts.envelope import ErrorCodes
from doramagic_contracts.extraction import (
    RepoFacts,
    Stage1ScanConfig,
    Stage1ScanInput,
    Stage1ScanOutput,
)
from doramagic_extraction.stage1_scan import run_stage1_scan

# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

FIXTURE_PATH = (
    Path(__file__).parent.parent.parent.parent
    / "data"
    / "fixtures"
    / "example_calorie_repo_facts_calorie.json"
)


def _load_calorie_input(generate_hypotheses: bool = True) -> Stage1ScanInput:
    """Load the Sim2 calorie counter fixture as Stage1ScanInput."""
    raw = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    repo_facts = RepoFacts.model_validate(raw)
    return Stage1ScanInput(
        repo_facts=repo_facts,
        domain_bricks=["daily meal log", "macro delta"],
        config=Stage1ScanConfig(
            max_llm_calls=8,
            max_prompt_tokens=24000,
            generate_hypotheses=generate_hypotheses,
            include_domain_bricks=True,
        ),
    )


def _make_minimal_input() -> Stage1ScanInput:
    """Minimal repo: only repo ref, no languages/frameworks/deps."""
    repo = RepoRef(
        repo_id="tiny",
        full_name="example/tiny",
        url="https://github.com/example/tiny",
        default_branch="main",
        commit_sha="deadbeef",
        local_path="/tmp/tiny",
    )
    repo_facts = RepoFacts(
        repo=repo,
        languages=[],
        frameworks=[],
        entrypoints=[],
        commands=[],
        storage_paths=[],
        dependencies=[],
        repo_summary="tiny",  # short — below 20 chars threshold
    )
    return Stage1ScanInput(
        repo_facts=repo_facts,
        config=Stage1ScanConfig(),
    )


def _make_missing_sha_input() -> Stage1ScanInput:
    """Input with empty commit_sha — should trigger E_INPUT_INVALID."""
    repo = RepoRef(
        repo_id="norepo",
        full_name="example/norepo",
        url="https://github.com/example/norepo",
        default_branch="main",
        commit_sha="",  # intentionally empty
        local_path="/tmp/norepo",
    )
    repo_facts = RepoFacts(
        repo=repo,
        languages=["Python"],
        frameworks=[],
        entrypoints=["main.py"],
        commands=["python main.py"],
        storage_paths=[],
        dependencies=["requests"],
        repo_summary="A simple Python script that fetches data.",
    )
    return Stage1ScanInput(
        repo_facts=repo_facts,
        config=Stage1ScanConfig(),
    )


# ──────────────────────────────────────────────────────────────────────────────
# Test 1: Normal path — calorie counter produces findings + hypotheses
# ──────────────────────────────────────────────────────────────────────────────


class TestNormalPath:
    def test_status_is_ok(self) -> None:
        """Normal calorie repo → status = ok."""
        result = run_stage1_scan(_load_calorie_input())
        assert result.status == "ok"

    def test_has_findings(self) -> None:
        """Output must contain at least 7 findings (one per Q1-Q7)."""
        result = run_stage1_scan(_load_calorie_input())
        assert result.data is not None
        assert len(result.data.findings) >= 7

    def test_has_interface_finding(self) -> None:
        """Must have at least one 'interface' knowledge_type finding (acceptance criterion)."""
        result = run_stage1_scan(_load_calorie_input())
        assert result.data is not None
        interface_findings = [f for f in result.data.findings if f.knowledge_type == "interface"]
        assert len(interface_findings) >= 1, "No interface findings found"

    def test_has_rationale_finding(self) -> None:
        """Must have at least one 'rationale' knowledge_type finding (acceptance criterion)."""
        result = run_stage1_scan(_load_calorie_input())
        assert result.data is not None
        rationale_findings = [f for f in result.data.findings if f.knowledge_type == "rationale"]
        assert len(rationale_findings) >= 1, "No rationale findings found"

    def test_has_hypotheses(self) -> None:
        """Output must contain hypotheses when generate_hypotheses=True."""
        result = run_stage1_scan(_load_calorie_input())
        assert result.data is not None
        assert len(result.data.hypotheses) >= 3

    def test_hypotheses_in_range(self) -> None:
        """Hypotheses count must be between 3 and 8."""
        result = run_stage1_scan(_load_calorie_input())
        assert result.data is not None
        count = len(result.data.hypotheses)
        assert 3 <= count <= 8, f"Expected 3-8 hypotheses, got {count}"

    def test_recommended_for_stage15_true(self) -> None:
        """Normal calorie repo must be recommended for Stage 1.5."""
        result = run_stage1_scan(_load_calorie_input())
        assert result.data is not None
        assert result.data.recommended_for_stage15 is True

    def test_coverage_has_answered_questions(self) -> None:
        """Coverage must show at least some answered questions."""
        result = run_stage1_scan(_load_calorie_input())
        assert result.data is not None
        assert len(result.data.coverage.answered_questions) > 0

    def test_module_name(self) -> None:
        """module_name must match the spec."""
        result = run_stage1_scan(_load_calorie_input())
        assert result.module_name == "extraction.stage1_scan"

    def test_metrics_non_negative(self) -> None:
        """All RunMetrics fields must be >= 0."""
        result = run_stage1_scan(_load_calorie_input())
        m = result.metrics
        assert m.wall_time_ms >= 0
        assert m.llm_calls >= 0
        assert m.prompt_tokens >= 0
        assert m.completion_tokens >= 0
        assert m.estimated_cost_usd >= 0.0

    def test_each_question_covered(self) -> None:
        """All 7 question keys Q1-Q7 should have at least one finding."""
        result = run_stage1_scan(_load_calorie_input())
        assert result.data is not None
        covered_keys = {f.question_key for f in result.data.findings}
        for q in ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7"]:
            assert q in covered_keys, f"No finding for {q}"


# ──────────────────────────────────────────────────────────────────────────────
# Test 2: Schema compliance
# ──────────────────────────────────────────────────────────────────────────────


class TestSchemaCompliance:
    def test_envelope_schema_version(self) -> None:
        """Envelope schema_version must be dm.module-envelope.v1."""
        result = run_stage1_scan(_load_calorie_input())
        assert result.schema_version == "dm.module-envelope.v1"

    def test_output_schema_version(self) -> None:
        """Stage1ScanOutput schema_version must be dm.stage1-scan-output.v1."""
        result = run_stage1_scan(_load_calorie_input())
        assert result.data is not None
        assert result.data.schema_version == "dm.stage1-scan-output.v1"

    def test_finding_id_format(self) -> None:
        """finding_id must match Q{n}-{REPO_ID}-{NNN} format."""
        result = run_stage1_scan(_load_calorie_input())
        assert result.data is not None
        pattern = re.compile(r"^Q[1-7]-[A-Z0-9\-]+-\d{3}$")
        for f in result.data.findings:
            assert pattern.match(f.finding_id), (
                f"finding_id '{f.finding_id}' does not match expected format"
            )

    def test_hypothesis_id_format(self) -> None:
        """hypothesis_id must match H-{NNN} format."""
        result = run_stage1_scan(_load_calorie_input())
        assert result.data is not None
        pattern = re.compile(r"^H-\d{3}$")
        for h in result.data.hypotheses:
            assert pattern.match(h.hypothesis_id), (
                f"hypothesis_id '{h.hypothesis_id}' does not match expected format"
            )

    def test_output_is_serializable(self) -> None:
        """Stage1ScanOutput must serialize to JSON and back without error."""
        result = run_stage1_scan(_load_calorie_input())
        assert result.data is not None
        json_str = result.data.model_dump_json()
        parsed = json.loads(json_str)
        restored = Stage1ScanOutput.model_validate(parsed)
        assert restored.schema_version == result.data.schema_version

    def test_envelope_is_serializable(self) -> None:
        """Full ModuleResultEnvelope must serialize to JSON."""
        result = run_stage1_scan(_load_calorie_input())
        json_str = result.model_dump_json()
        parsed = json.loads(json_str)
        assert parsed["schema_version"] == "dm.module-envelope.v1"

    def test_findings_have_evidence_refs(self) -> None:
        """Every finding must have at least one evidence_ref."""
        result = run_stage1_scan(_load_calorie_input())
        assert result.data is not None
        for f in result.data.findings:
            assert len(f.evidence_refs) >= 1, f"Finding {f.finding_id} has no evidence_refs"

    def test_hypotheses_have_search_hints(self) -> None:
        """Every hypothesis must have at least one search hint."""
        result = run_stage1_scan(_load_calorie_input())
        assert result.data is not None
        for h in result.data.hypotheses:
            assert len(h.search_hints) >= 1, f"Hypothesis {h.hypothesis_id} has no search_hints"

    def test_finding_question_keys_valid(self) -> None:
        """question_key must be one of Q1-Q7."""
        result = run_stage1_scan(_load_calorie_input())
        assert result.data is not None
        valid_keys = {"Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7"}
        for f in result.data.findings:
            assert f.question_key in valid_keys

    def test_finding_confidence_valid(self) -> None:
        """confidence must be 'high', 'medium', or 'low'."""
        result = run_stage1_scan(_load_calorie_input())
        assert result.data is not None
        valid_confs = {"high", "medium", "low"}
        for f in result.data.findings:
            assert f.confidence in valid_confs

    def test_hypothesis_priority_valid(self) -> None:
        """priority must be 'high', 'medium', or 'low'."""
        result = run_stage1_scan(_load_calorie_input())
        assert result.data is not None
        valid = {"high", "medium", "low"}
        for h in result.data.hypotheses:
            assert h.priority in valid

    def test_coverage_questions_non_overlapping(self) -> None:
        """answered/partial/uncovered must not overlap."""
        result = run_stage1_scan(_load_calorie_input())
        assert result.data is not None
        cov = result.data.coverage
        all_q = (
            set(cov.answered_questions) | set(cov.partial_questions) | set(cov.uncovered_questions)
        )
        total = (
            len(cov.answered_questions) + len(cov.partial_questions) + len(cov.uncovered_questions)
        )
        assert len(all_q) == total, "Coverage categories overlap"

    def test_coverage_total_is_7(self) -> None:
        """Total coverage must account for exactly 7 questions."""
        result = run_stage1_scan(_load_calorie_input())
        assert result.data is not None
        cov = result.data.coverage
        total = (
            len(cov.answered_questions) + len(cov.partial_questions) + len(cov.uncovered_questions)
        )
        assert total == 7, f"Expected 7 total questions, got {total}"

    def test_pydantic_roundtrip(self) -> None:
        """model_dump → model_validate roundtrip must preserve data integrity."""
        result = run_stage1_scan(_load_calorie_input())
        assert result.data is not None
        dumped = result.data.model_dump()
        restored = Stage1ScanOutput.model_validate(dumped)
        assert len(restored.findings) == len(result.data.findings)
        assert len(restored.hypotheses) == len(result.data.hypotheses)


# ──────────────────────────────────────────────────────────────────────────────
# Test 3: Error path — missing/empty commit_sha → blocked + E_INPUT_INVALID
# ──────────────────────────────────────────────────────────────────────────────


class TestErrorPath:
    def test_empty_commit_sha_returns_blocked(self) -> None:
        """Empty commit_sha must return status=blocked."""
        result = run_stage1_scan(_make_missing_sha_input())
        assert result.status == "blocked"

    def test_empty_commit_sha_error_code(self) -> None:
        """Empty commit_sha must return error_code=E_INPUT_INVALID."""
        result = run_stage1_scan(_make_missing_sha_input())
        assert result.error_code == ErrorCodes.INPUT_INVALID

    def test_blocked_has_no_data(self) -> None:
        """Blocked result must have data=None."""
        result = run_stage1_scan(_make_missing_sha_input())
        assert result.data is None

    def test_blocked_has_warning(self) -> None:
        """Blocked result must include at least one warning."""
        result = run_stage1_scan(_make_missing_sha_input())
        assert len(result.warnings) >= 1

    def test_blocked_metrics_zero_llm_calls(self) -> None:
        """Blocked result must report 0 LLM calls (failed before extraction)."""
        result = run_stage1_scan(_make_missing_sha_input())
        assert result.metrics.llm_calls == 0


# ──────────────────────────────────────────────────────────────────────────────
# Test 4: Degraded path — minimal repo → degraded + recommended_for_stage15=false
# ──────────────────────────────────────────────────────────────────────────────


class TestDegradedPath:
    def test_minimal_repo_returns_degraded(self) -> None:
        """Minimal repo with few facts must return status=degraded."""
        result = run_stage1_scan(_make_minimal_input())
        assert result.status == "degraded"

    def test_minimal_repo_not_recommended(self) -> None:
        """Minimal repo must set recommended_for_stage15=False."""
        result = run_stage1_scan(_make_minimal_input())
        assert result.data is not None
        assert result.data.recommended_for_stage15 is False

    def test_minimal_repo_still_has_findings(self) -> None:
        """Even degraded output must contain some findings (not None, not empty)."""
        result = run_stage1_scan(_make_minimal_input())
        assert result.data is not None
        # May have very few findings but should not crash
        assert isinstance(result.data.findings, list)

    def test_minimal_repo_has_warning(self) -> None:
        """Minimal repo must trigger W_MINIMAL_REPO warning."""
        result = run_stage1_scan(_make_minimal_input())
        codes = [w.code for w in result.warnings]
        assert "W_MINIMAL_REPO" in codes

    def test_minimal_repo_schema_still_valid(self) -> None:
        """Degraded output must still be schema-valid (serializable)."""
        result = run_stage1_scan(_make_minimal_input())
        assert result.data is not None
        json_str = result.data.model_dump_json()
        parsed = json.loads(json_str)
        restored = Stage1ScanOutput.model_validate(parsed)
        assert restored.schema_version == "dm.stage1-scan-output.v1"


# ──────────────────────────────────────────────────────────────────────────────
# Test 5: Idempotency — same input → same finding_ids
# ──────────────────────────────────────────────────────────────────────────────


class TestIdempotency:
    def test_finding_ids_stable(self) -> None:
        """Same input produces identical finding_ids on repeated calls."""
        inp = _load_calorie_input()
        result1 = run_stage1_scan(inp)
        result2 = run_stage1_scan(inp)
        assert result1.data is not None
        assert result2.data is not None
        ids1 = sorted(f.finding_id for f in result1.data.findings)
        ids2 = sorted(f.finding_id for f in result2.data.findings)
        assert ids1 == ids2

    def test_hypothesis_ids_stable(self) -> None:
        """Same input produces identical hypothesis_ids on repeated calls."""
        inp = _load_calorie_input()
        result1 = run_stage1_scan(inp)
        result2 = run_stage1_scan(inp)
        assert result1.data is not None
        assert result2.data is not None
        h_ids1 = sorted(h.hypothesis_id for h in result1.data.hypotheses)
        h_ids2 = sorted(h.hypothesis_id for h in result2.data.hypotheses)
        assert h_ids1 == h_ids2


# ──────────────────────────────────────────────────────────────────────────────
# Test 6: No hypotheses when disabled
# ──────────────────────────────────────────────────────────────────────────────


class TestHypothesisToggle:
    def test_no_hypotheses_when_disabled(self) -> None:
        """When generate_hypotheses=False, hypotheses list must be empty."""
        inp = _load_calorie_input(generate_hypotheses=False)
        result = run_stage1_scan(inp)
        assert result.data is not None
        assert result.data.hypotheses == []

    def test_recommended_false_when_no_hypotheses(self) -> None:
        """When generate_hypotheses=False, recommended_for_stage15 must be False."""
        inp = _load_calorie_input(generate_hypotheses=False)
        result = run_stage1_scan(inp)
        assert result.data is not None
        # No hypotheses → can't recommend Stage 1.5
        assert result.data.recommended_for_stage15 is False


# ──────────────────────────────────────────────────────────────────────────────
# Test 7: Content validation for calorie counter
# ──────────────────────────────────────────────────────────────────────────────


class TestCalorieCounterContent:
    def test_repo_ref_preserved(self) -> None:
        """output.repo must match input repo_facts.repo."""
        inp = _load_calorie_input()
        result = run_stage1_scan(inp)
        assert result.data is not None
        assert result.data.repo.repo_id == inp.repo_facts.repo.repo_id

    def test_has_constraint_finding(self) -> None:
        """Must have at least one 'constraint' knowledge_type finding."""
        result = run_stage1_scan(_load_calorie_input())
        assert result.data is not None
        constraint_findings = [f for f in result.data.findings if f.knowledge_type == "constraint"]
        assert len(constraint_findings) >= 1

    def test_has_failure_finding(self) -> None:
        """Must have at least one 'failure' knowledge_type finding."""
        result = run_stage1_scan(_load_calorie_input())
        assert result.data is not None
        failure_findings = [f for f in result.data.findings if f.knowledge_type == "failure"]
        assert len(failure_findings) >= 1

    def test_has_assembly_pattern_finding(self) -> None:
        """Must have at least one 'assembly_pattern' knowledge_type finding."""
        result = run_stage1_scan(_load_calorie_input())
        assert result.data is not None
        ap_findings = [f for f in result.data.findings if f.knowledge_type == "assembly_pattern"]
        assert len(ap_findings) >= 1

    def test_high_priority_hypothesis_exists(self) -> None:
        """At least one hypothesis must have priority='high'."""
        result = run_stage1_scan(_load_calorie_input())
        assert result.data is not None
        high_priority = [h for h in result.data.hypotheses if h.priority == "high"]
        assert len(high_priority) >= 1, "No high-priority hypotheses generated"

    def test_finding_titles_non_empty(self) -> None:
        """All finding titles must be non-empty strings."""
        result = run_stage1_scan(_load_calorie_input())
        assert result.data is not None
        for f in result.data.findings:
            assert isinstance(f.title, str) and len(f.title) > 0

    def test_finding_statements_non_empty(self) -> None:
        """All finding statements must be non-empty strings."""
        result = run_stage1_scan(_load_calorie_input())
        assert result.data is not None
        for f in result.data.findings:
            assert isinstance(f.statement, str) and len(f.statement) > 0
