"""Fixture 验证测试 — 确保所有 data/fixtures/ 文件能被正确反序列化。

Round 0 和 Round 1 新增 fixture 统一在此验证。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "packages" / "contracts"))

from doramagic_contracts.base import NeedProfile  # noqa: E402
from doramagic_contracts.cross_project import DiscoveryResult  # noqa: E402
from doramagic_contracts.extraction import RepoFacts, Stage1ScanOutput  # noqa: E402
from doramagic_contracts.skill import PlatformRules  # noqa: E402

FIXTURES_DIR = Path(__file__).parent.parent / "data" / "fixtures"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load(filename: str) -> dict:
    path = FIXTURES_DIR / filename
    assert path.exists(), f"Fixture file not found: {path}"
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Existing fixtures (Round 0)
# ---------------------------------------------------------------------------


class TestExistingFixtures:
    def test_platform_rules(self) -> None:
        data = _load("platform_rules.json")
        rules = PlatformRules(**data)
        assert rules.schema_version == "dm.platform-rules.v1"
        assert "exec" in rules.allowed_tools
        assert "cron" in rules.forbid_frontmatter_fields

    def test_sim2_need_profile(self) -> None:
        data = _load("sim2_need_profile.json")
        profile = NeedProfile(**data)
        assert profile.schema_version == "dm.need-profile.v1"
        assert "卡路里" in profile.keywords
        assert any("OpenClaw" in c for c in profile.constraints)
        assert len(profile.search_directions) >= 1


# ---------------------------------------------------------------------------
# New fixtures (Round 1)
# ---------------------------------------------------------------------------


class TestSim2RepoFactsCalorie:
    def test_loads_and_validates(self) -> None:
        data = _load("sim2_repo_facts_calorie.json")
        facts = RepoFacts(**data)
        assert facts.schema_version == "dm.repo-facts.v1"

    def test_languages(self) -> None:
        data = _load("sim2_repo_facts_calorie.json")
        facts = RepoFacts(**data)
        assert "TypeScript" in facts.languages

    def test_frameworks(self) -> None:
        data = _load("sim2_repo_facts_calorie.json")
        facts = RepoFacts(**data)
        assert "Next.js" in facts.frameworks

    def test_entrypoints(self) -> None:
        data = _load("sim2_repo_facts_calorie.json")
        facts = RepoFacts(**data)
        assert "src/app/api/chat/route.ts" in facts.entrypoints

    def test_repo_ref_present(self) -> None:
        data = _load("sim2_repo_facts_calorie.json")
        facts = RepoFacts(**data)
        assert facts.repo.repo_id == "ai-calorie-counter"

    def test_dependencies_non_empty(self) -> None:
        data = _load("sim2_repo_facts_calorie.json")
        facts = RepoFacts(**data)
        assert len(facts.dependencies) > 0

    def test_json_roundtrip(self) -> None:
        data = _load("sim2_repo_facts_calorie.json")
        facts = RepoFacts(**data)
        restored = RepoFacts.model_validate_json(facts.model_dump_json())
        assert restored.repo.repo_id == facts.repo.repo_id


class TestSim2Stage1OutputCalorie:
    def test_loads_and_validates(self) -> None:
        data = _load("sim2_stage1_output_calorie.json")
        output = Stage1ScanOutput(**data)
        assert output.schema_version == "dm.stage1-scan-output.v1"

    def test_has_three_findings(self) -> None:
        data = _load("sim2_stage1_output_calorie.json")
        output = Stage1ScanOutput(**data)
        assert len(output.findings) >= 3

    def test_finding_question_keys(self) -> None:
        data = _load("sim2_stage1_output_calorie.json")
        output = Stage1ScanOutput(**data)
        keys = {f.question_key for f in output.findings}
        # 必须包含 Q2, Q3, Q5
        assert "Q2" in keys
        assert "Q3" in keys
        assert "Q5" in keys

    def test_has_two_hypotheses(self) -> None:
        data = _load("sim2_stage1_output_calorie.json")
        output = Stage1ScanOutput(**data)
        assert len(output.hypotheses) >= 2

    def test_coverage_structure(self) -> None:
        data = _load("sim2_stage1_output_calorie.json")
        output = Stage1ScanOutput(**data)
        assert isinstance(output.coverage.answered_questions, list)
        assert isinstance(output.coverage.partial_questions, list)
        assert isinstance(output.coverage.uncovered_questions, list)

    def test_recommended_for_stage15(self) -> None:
        data = _load("sim2_stage1_output_calorie.json")
        output = Stage1ScanOutput(**data)
        assert output.recommended_for_stage15 is True

    def test_findings_have_evidence_refs(self) -> None:
        data = _load("sim2_stage1_output_calorie.json")
        output = Stage1ScanOutput(**data)
        for finding in output.findings:
            assert len(finding.evidence_refs) >= 1

    def test_json_roundtrip(self) -> None:
        data = _load("sim2_stage1_output_calorie.json")
        output = Stage1ScanOutput(**data)
        restored = Stage1ScanOutput.model_validate_json(output.model_dump_json())
        assert len(restored.findings) == len(output.findings)


class TestSim2DiscoveryResult:
    def test_loads_and_validates(self) -> None:
        data = _load("sim2_discovery_result.json")
        result = DiscoveryResult(**data)
        assert result.schema_version == "dm.discovery-result.v1"

    def test_has_two_github_repos(self) -> None:
        data = _load("sim2_discovery_result.json")
        result = DiscoveryResult(**data)
        github_repos = [c for c in result.candidates if c.type == "github_repo"]
        assert len(github_repos) >= 2

    def test_has_one_community_skill(self) -> None:
        data = _load("sim2_discovery_result.json")
        result = DiscoveryResult(**data)
        community_skills = [c for c in result.candidates if c.type == "community_skill"]
        assert len(community_skills) >= 1

    def test_search_coverage_four_directions(self) -> None:
        data = _load("sim2_discovery_result.json")
        result = DiscoveryResult(**data)
        assert len(result.search_coverage) >= 4

    def test_candidate_quick_scores_in_range(self) -> None:
        data = _load("sim2_discovery_result.json")
        result = DiscoveryResult(**data)
        for candidate in result.candidates:
            assert 0.0 <= candidate.quick_score <= 10.0

    def test_no_candidate_reason_is_none(self) -> None:
        data = _load("sim2_discovery_result.json")
        result = DiscoveryResult(**data)
        assert result.no_candidate_reason is None

    def test_json_roundtrip(self) -> None:
        data = _load("sim2_discovery_result.json")
        result = DiscoveryResult(**data)
        restored = DiscoveryResult.model_validate_json(result.model_dump_json())
        assert len(restored.candidates) == len(result.candidates)


class TestSim3NeedProfileFlight:
    def test_loads_and_validates(self) -> None:
        data = _load("sim3_need_profile_flight.json")
        profile = NeedProfile(**data)
        assert profile.schema_version == "dm.need-profile.v1"

    def test_raw_input(self) -> None:
        data = _load("sim3_need_profile_flight.json")
        profile = NeedProfile(**data)
        assert "机票" in profile.raw_input
        assert "比价" in profile.raw_input

    def test_keywords_non_empty(self) -> None:
        data = _load("sim3_need_profile_flight.json")
        profile = NeedProfile(**data)
        assert len(profile.keywords) >= 2
        assert "机票" in profile.keywords

    def test_search_directions_non_empty(self) -> None:
        data = _load("sim3_need_profile_flight.json")
        profile = NeedProfile(**data)
        assert len(profile.search_directions) >= 2

    def test_constraints_include_openclaw(self) -> None:
        data = _load("sim3_need_profile_flight.json")
        profile = NeedProfile(**data)
        assert any("OpenClaw" in c for c in profile.constraints)

    def test_quality_expectations_present(self) -> None:
        data = _load("sim3_need_profile_flight.json")
        profile = NeedProfile(**data)
        assert len(profile.quality_expectations) > 0

    def test_json_roundtrip(self) -> None:
        data = _load("sim3_need_profile_flight.json")
        profile = NeedProfile(**data)
        restored = NeedProfile.model_validate_json(profile.model_dump_json())
        assert restored.raw_input == profile.raw_input
