"""Tests for cross-project.synthesis module."""

from __future__ import annotations

import json

from doramagic_contracts.base import (
    EvidenceRef,
    NeedProfile,
    RepoRef,
    SearchDirection,
)
from doramagic_contracts.cross_project import (
    CommunityKnowledge,
    CommunityKnowledgeItem,
    CompareMetrics,
    CompareOutput,
    CompareSignal,
    DiscoveryResult,
    ExtractedProjectSummary,
    SynthesisInput,
)
from doramagic_contracts.envelope import ErrorCodes
from doramagic_cross_project.synthesis import run_synthesis

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _repo(repo_id: str) -> RepoRef:
    return RepoRef(
        repo_id=repo_id,
        full_name=f"example/{repo_id}",
        url=f"https://github.com/example/{repo_id}",
        default_branch="main",
        commit_sha="abc123",
        local_path=f"/tmp/{repo_id}",
    )


def _evidence(path: str, line: int = 10) -> EvidenceRef:
    return EvidenceRef(
        kind="file_line",
        path=path,
        start_line=line,
        end_line=line + 2,
        snippet="evidence snippet",
    )


def _need_profile(keywords: list[str] | None = None) -> NeedProfile:
    return NeedProfile(
        raw_input="我想做一个记录食物卡路里的 skill",
        keywords=keywords or ["food", "calorie", "track", "record"],
        intent="Build a calorie-tracking OpenClaw skill",
        search_directions=[
            SearchDirection(direction="AI food recognition", priority="high"),
            SearchDirection(direction="nutrition database", priority="high"),
        ],
        constraints=["OpenClaw platform", "message-driven interaction"],
        quality_expectations={"accuracy": "<20%"},
    )


def _aligned_signal(
    signal_id: str,
    statement: str,
    project_ids: list[str],
    match_score: float = 0.92,
) -> CompareSignal:
    return CompareSignal(
        signal_id=signal_id,
        signal="ALIGNED",
        subject_project_ids=project_ids,
        normalized_statement=statement,
        support_count=len(project_ids),
        support_independence=0.85,
        match_score=match_score,
        evidence_refs=[_evidence(f"proj/{pid}/module.py") for pid in project_ids],
        notes="aligned via structured match",
    )


def _original_signal(
    signal_id: str,
    statement: str,
    project_id: str,
) -> CompareSignal:
    return CompareSignal(
        signal_id=signal_id,
        signal="ORIGINAL",
        subject_project_ids=[project_id],
        normalized_statement=statement,
        support_count=1,
        support_independence=1.0,
        match_score=0.3,
        evidence_refs=[_evidence(f"{project_id}/unique.py")],
        notes="second-pass retrieval found no comparable atom above partial threshold",
    )


def _drifted_signal(
    signal_id: str,
    statement: str,
    project_ids: list[str],
) -> CompareSignal:
    return CompareSignal(
        signal_id=signal_id,
        signal="DRIFTED",
        subject_project_ids=project_ids,
        normalized_statement=statement,
        support_count=len(project_ids),
        support_independence=0.6,
        match_score=0.70,
        evidence_refs=[_evidence(f"{pid}/drift.py") for pid in project_ids],
        notes="partial overlap",
    )


def _project_summary(
    project_id: str,
    capabilities: list[str] | None = None,
    constraints: list[str] | None = None,
    failures: list[str] | None = None,
) -> ExtractedProjectSummary:
    return ExtractedProjectSummary(
        project_id=project_id,
        repo=_repo(project_id),
        top_capabilities=capabilities or ["LLM-as-Parser", "daily calorie budget"],
        top_constraints=constraints or ["AI estimate uncertainty"],
        top_failures=failures or ["portion estimation drift"],
        evidence_refs=[_evidence(f"{project_id}/README.md")],
    )


def _discovery_result() -> DiscoveryResult:
    return DiscoveryResult(
        candidates=[],
        search_coverage=[],
        no_candidate_reason=None,
    )


def _compare_output(
    domain_id: str = "nutrition-calorie",
    signals: list[CompareSignal] | None = None,
    project_ids: list[str] | None = None,
) -> CompareOutput:
    _project_ids = project_ids or ["acc", "foodyo", "ont"]
    _signals = (
        signals
        if signals is not None
        else [
            _aligned_signal("SIG-ALIGN-001", "food input parsed as json schema", _project_ids[:2]),
            _original_signal(
                "SIG-ORIG-001",
                "use llm as parser for natural language meal logging",
                _project_ids[0],
            ),
            _drifted_signal("SIG-DRIFT-001", "storage format for daily food log", _project_ids),
        ]
    )
    return CompareOutput(
        domain_id=domain_id,
        compared_projects=_project_ids,
        signals=_signals,
        metrics=CompareMetrics(
            project_count=len(_project_ids),
            atom_count=30,
            aligned_count=sum(1 for s in _signals if s.signal == "ALIGNED"),
            missing_count=0,
            original_count=sum(1 for s in _signals if s.signal == "ORIGINAL"),
            drifted_count=sum(1 for s in _signals if s.signal == "DRIFTED"),
        ),
    )


def _community_knowledge() -> CommunityKnowledge:
    return CommunityKnowledge(
        skills=[
            CommunityKnowledgeItem(
                item_id="COM-001",
                name="calorie-tracker-skill",
                source="https://community.openclaw.dev/skills/calorie-tracker",
                kind="skill",
                capabilities=["exec python calorie script", "markdown daily log"],
                storage_pattern="~/clawd/calorie/",
                reusable_knowledge=[
                    "Store daily logs in ~/clawd/calorie/YYYY-MM-DD.md",
                    "Report progress as consumed/goal/remaining",
                ],
            )
        ],
        tutorials=[],
        use_cases=[],
    )


def _build_synthesis_input(
    signals: list[CompareSignal] | None = None,
    project_summaries: list[ExtractedProjectSummary] | None = None,
    community: CommunityKnowledge | None = None,
    need_keywords: list[str] | None = None,
) -> SynthesisInput:
    return SynthesisInput(
        need_profile=_need_profile(need_keywords),
        discovery_result=_discovery_result(),
        project_summaries=project_summaries
        or [_project_summary("acc"), _project_summary("foodyo")],
        comparison_result=_compare_output(signals=signals),
        community_knowledge=community or _community_knowledge(),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRunSynthesisNormalPath:
    """Happy-path tests."""

    def test_returns_ok_status(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DORAMAGIC_SYNTHESIS_OUTPUT_DIR", str(tmp_path))
        result = run_synthesis(_build_synthesis_input())
        assert result.status == "ok"
        assert result.data is not None

    def test_at_least_one_consensus(self, tmp_path, monkeypatch):
        """Must output at least 1 consensus item from ALIGNED signals."""
        monkeypatch.setenv("DORAMAGIC_SYNTHESIS_OUTPUT_DIR", str(tmp_path))
        result = run_synthesis(_build_synthesis_input())
        assert result.data is not None
        assert len(result.data.consensus) >= 1

    def test_at_least_one_unique_knowledge(self, tmp_path, monkeypatch):
        """Must output at least 1 unique/original knowledge item."""
        monkeypatch.setenv("DORAMAGIC_SYNTHESIS_OUTPUT_DIR", str(tmp_path))
        result = run_synthesis(_build_synthesis_input())
        assert result.data is not None
        assert len(result.data.unique_knowledge) >= 1

    def test_at_least_one_conflict(self, tmp_path, monkeypatch):
        """Must detect at least 1 conflict from DRIFTED signal."""
        monkeypatch.setenv("DORAMAGIC_SYNTHESIS_OUTPUT_DIR", str(tmp_path))
        result = run_synthesis(_build_synthesis_input())
        assert result.data is not None
        assert len(result.data.conflicts) >= 1

    def test_all_selected_knowledge_traceable(self, tmp_path, monkeypatch):
        """Every selected_knowledge item must have source_refs pointing to compare/project/community."""
        monkeypatch.setenv("DORAMAGIC_SYNTHESIS_OUTPUT_DIR", str(tmp_path))
        result = run_synthesis(_build_synthesis_input())
        assert result.data is not None
        for sel in result.data.selected_knowledge:
            assert sel.source_refs, f"selected_knowledge item '{sel.statement}' has no source_refs"

    def test_writes_synthesis_report_json(self, tmp_path, monkeypatch):
        """synthesis_report.json must be written to the domain output dir."""
        monkeypatch.setenv("DORAMAGIC_SYNTHESIS_OUTPUT_DIR", str(tmp_path))
        run_synthesis(_build_synthesis_input())
        json_path = tmp_path / "nutrition-calorie" / "synthesis_report.json"
        assert json_path.exists(), "synthesis_report.json not found"
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        assert payload["schema_version"] == "dm.synthesis-report.v1"

    def test_writes_synthesis_report_md(self, tmp_path, monkeypatch):
        """synthesis_report.md must be written alongside the JSON."""
        monkeypatch.setenv("DORAMAGIC_SYNTHESIS_OUTPUT_DIR", str(tmp_path))
        run_synthesis(_build_synthesis_input())
        md_path = tmp_path / "nutrition-calorie" / "synthesis_report.md"
        assert md_path.exists(), "synthesis_report.md not found"
        content = md_path.read_text(encoding="utf-8")
        assert "# Synthesis Report" in content

    def test_decision_ids_are_stable(self, tmp_path, monkeypatch):
        """Same input must produce identical decision_ids on repeated runs."""
        monkeypatch.setenv("DORAMAGIC_SYNTHESIS_OUTPUT_DIR", str(tmp_path))
        inp = _build_synthesis_input()
        first = run_synthesis(inp)
        second = run_synthesis(inp)
        assert first.data is not None
        assert second.data is not None
        ids_first = sorted(d.decision_id for d in first.data.selected_knowledge)
        ids_second = sorted(d.decision_id for d in second.data.selected_knowledge)
        assert ids_first == ids_second, "decision_ids not stable across runs"

    def test_conflict_ids_are_stable(self, tmp_path, monkeypatch):
        """Same input must produce identical conflict_ids on repeated runs."""
        monkeypatch.setenv("DORAMAGIC_SYNTHESIS_OUTPUT_DIR", str(tmp_path))
        inp = _build_synthesis_input()
        first = run_synthesis(inp)
        second = run_synthesis(inp)
        assert first.data is not None
        assert second.data is not None
        cids_first = sorted(c.conflict_id for c in first.data.conflicts)
        cids_second = sorted(c.conflict_id for c in second.data.conflicts)
        assert cids_first == cids_second, "conflict_ids not stable across runs"


class TestRunSynthesisErrorPaths:
    """Error / blocked path tests."""

    def test_missing_comparison_result_projects_blocks(self, tmp_path, monkeypatch):
        """comparison_result with empty compared_projects → blocked + E_UPSTREAM_MISSING."""
        monkeypatch.setenv("DORAMAGIC_SYNTHESIS_OUTPUT_DIR", str(tmp_path))
        empty_compare = CompareOutput(
            domain_id="test",
            compared_projects=[],  # empty → upstream missing
            signals=[],
            metrics=CompareMetrics(
                project_count=1,
                atom_count=0,
                aligned_count=0,
                missing_count=0,
                original_count=0,
                drifted_count=0,
            ),
        )
        inp = SynthesisInput(
            need_profile=_need_profile(),
            discovery_result=_discovery_result(),
            project_summaries=[_project_summary("acc")],
            comparison_result=empty_compare,
            community_knowledge=_community_knowledge(),
        )
        result = run_synthesis(inp)
        assert result.status == "blocked"
        assert result.error_code == ErrorCodes.UPSTREAM_MISSING
        assert result.data is None

    def test_license_conflict_blocks_synthesis(self, tmp_path, monkeypatch):
        """An unresolved license conflict must result in blocked + E_UNRESOLVED_CONFLICT."""
        monkeypatch.setenv("DORAMAGIC_SYNTHESIS_OUTPUT_DIR", str(tmp_path))
        # Inject two conflicting license signals — DRIFTED so conflict is detected
        license_sig_1 = _drifted_signal(
            "SIG-LIC-001",
            "mit license terms allow commercial use redistribution",
            ["acc", "foodyo"],
        )
        license_sig_2 = _drifted_signal(
            "SIG-LIC-002",
            "gpl license copyleft require source distribution",
            ["ont", "acc"],
        )
        signals = [license_sig_1, license_sig_2]
        inp = _build_synthesis_input(signals=signals)
        result = run_synthesis(inp)
        assert result.status == "blocked"
        assert result.error_code == ErrorCodes.UNRESOLVED_CONFLICT
        assert result.data is None

    def test_no_conflict_when_only_aligned_signals(self, tmp_path, monkeypatch):
        """Pure ALIGNED signals should produce no conflicts."""
        monkeypatch.setenv("DORAMAGIC_SYNTHESIS_OUTPUT_DIR", str(tmp_path))
        only_aligned = [
            _aligned_signal("SIG-A-001", "food input parsed as json schema", ["acc", "foodyo"]),
            _aligned_signal("SIG-A-002", "calorie goal stored per user profile", ["acc", "ont"]),
        ]
        result = run_synthesis(_build_synthesis_input(signals=only_aligned))
        assert result.status == "ok"
        assert result.data is not None
        assert result.data.conflicts == []

    def test_excluded_knowledge_has_rationale(self, tmp_path, monkeypatch):
        """Every excluded decision must have a non-empty rationale."""
        monkeypatch.setenv("DORAMAGIC_SYNTHESIS_OUTPUT_DIR", str(tmp_path))
        result = run_synthesis(_build_synthesis_input())
        assert result.data is not None
        for ex in result.data.excluded_knowledge:
            assert ex.rationale, f"excluded decision '{ex.statement}' has empty rationale"

    def test_community_knowledge_contributes_to_unique(self, tmp_path, monkeypatch):
        """Community reusable_knowledge items must appear in unique_knowledge."""
        monkeypatch.setenv("DORAMAGIC_SYNTHESIS_OUTPUT_DIR", str(tmp_path))
        community = _community_knowledge()
        # Use only ORIGINAL signals so no consensus; community knowledge lands in unique
        only_original = [
            _original_signal("SIG-O-001", "llm as parser for natural language meal log", "acc"),
        ]
        result = run_synthesis(_build_synthesis_input(signals=only_original, community=community))
        assert result.data is not None
        unique_statements = {d.statement for d in result.data.unique_knowledge}
        # community item reusable_knowledge entries should appear
        expected = "Store daily logs in ~/clawd/calorie/YYYY-MM-DD.md"
        assert expected in unique_statements, (
            f"Community knowledge '{expected}' not found in unique_knowledge"
        )

    def test_conflict_category_is_valid(self, tmp_path, monkeypatch):
        """All conflict categories must be from the allowed enumeration."""
        monkeypatch.setenv("DORAMAGIC_SYNTHESIS_OUTPUT_DIR", str(tmp_path))
        result = run_synthesis(_build_synthesis_input())
        assert result.data is not None
        valid_categories = {
            "semantic",
            "scope",
            "architecture",
            "dependency",
            "operational",
            "license",
        }
        for conflict in result.data.conflicts:
            assert conflict.category in valid_categories, (
                f"Invalid conflict category: '{conflict.category}'"
            )

    def test_decision_values_are_valid(self, tmp_path, monkeypatch):
        """All decision values must be include / exclude / option."""
        monkeypatch.setenv("DORAMAGIC_SYNTHESIS_OUTPUT_DIR", str(tmp_path))
        result = run_synthesis(_build_synthesis_input())
        assert result.data is not None
        valid_decisions = {"include", "exclude", "option"}
        all_decisions = (
            result.data.consensus
            + result.data.unique_knowledge
            + result.data.selected_knowledge
            + result.data.excluded_knowledge
        )
        for d in all_decisions:
            assert d.decision in valid_decisions, (
                f"Invalid decision value '{d.decision}' for '{d.statement}'"
            )
