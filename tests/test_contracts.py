"""Contracts smoke tests — Round 0 验收测试。"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "packages" / "contracts"))

from doramagic_contracts.base import (
    EvidenceRef,
    NeedProfile,
    RepoRef,
)
from doramagic_contracts.envelope import ErrorCodes, ModuleResultEnvelope, RunMetrics
from doramagic_contracts.extraction import (
    RepoFacts,
    Stage1ScanOutput,
)
from doramagic_contracts.skill import (
    PlatformRules,
    ValidationReport,
)

FIXTURES_DIR = Path(__file__).parent.parent / "data" / "fixtures"


class TestEnvelope:
    def test_envelope_ok(self):
        env = ModuleResultEnvelope(
            module_name="test",
            status="ok",
            data={"result": 42},
            metrics=RunMetrics(
                wall_time_ms=100,
                llm_calls=1,
                prompt_tokens=500,
                completion_tokens=100,
                estimated_cost_usd=0.01,
            ),
        )
        assert env.status == "ok"
        assert env.error_code is None

    def test_envelope_error(self):
        env = ModuleResultEnvelope(
            module_name="test",
            status="error",
            error_code=ErrorCodes.TIMEOUT,
            metrics=RunMetrics(
                wall_time_ms=180000,
                llm_calls=0,
                prompt_tokens=0,
                completion_tokens=0,
                estimated_cost_usd=0,
            ),
        )
        assert env.status == "error"
        assert env.error_code == "E_TIMEOUT"

    def test_error_codes_complete(self):
        codes = [v for k, v in vars(ErrorCodes).items() if not k.startswith("_")]
        assert len(codes) == 11
        assert all(c.startswith("E_") for c in codes)


class TestBase:
    def test_need_profile_schema_version(self):
        p = NeedProfile(
            raw_input="test",
            keywords=["test"],
            intent="test",
            search_directions=[],
            constraints=["OpenClaw"],
        )
        assert p.schema_version == "dm.need-profile.v1"

    def test_repo_ref(self):
        r = RepoRef(
            repo_id="test",
            full_name="org/repo",
            url="https://github.com/org/repo",
            default_branch="main",
            commit_sha="abc123",
            local_path="/tmp/repo",
        )
        assert r.repo_id == "test"

    def test_evidence_ref_file_line(self):
        e = EvidenceRef(
            kind="file_line",
            path="src/main.py",
            start_line=10,
            end_line=20,
            snippet="def main():",
        )
        assert e.kind == "file_line"
        assert e.start_line == 10


class TestPlatformRules:
    def test_defaults(self):
        rules = PlatformRules()
        assert rules.allowed_tools == ["exec", "read", "write"]
        assert rules.storage_prefix == "~/clawd/"
        assert "cron" in rules.forbid_frontmatter_fields

    def test_fixture_file(self):
        path = FIXTURES_DIR / "platform_rules.json"
        assert path.exists()
        data = json.loads(path.read_text())
        rules = PlatformRules(**data)
        assert rules.allowed_tools == ["exec", "read", "write"]

    def test_json_roundtrip(self):
        rules = PlatformRules()
        j = rules.model_dump_json()
        rules2 = PlatformRules.model_validate_json(j)
        assert rules == rules2


class TestFixtures:
    def test_sim2_need_profile(self):
        path = FIXTURES_DIR / "sim2_need_profile.json"
        assert path.exists()
        data = json.loads(path.read_text())
        profile = NeedProfile(**data)
        assert "卡路里" in profile.keywords
        assert any("OpenClaw" in c for c in profile.constraints)

    def test_platform_rules_fixture(self):
        path = FIXTURES_DIR / "platform_rules.json"
        assert path.exists()
        data = json.loads(path.read_text())
        rules = PlatformRules(**data)
        assert "exec" in rules.allowed_tools


class TestExtraction:
    def test_repo_facts(self):
        facts = RepoFacts(
            repo=RepoRef(
                repo_id="test",
                full_name="org/repo",
                url="https://github.com/org/repo",
                default_branch="main",
                commit_sha="abc",
                local_path="/tmp",
            ),
            languages=["Python"],
            frameworks=["FastAPI"],
            entrypoints=["main.py"],
            commands=["python main.py"],
            storage_paths=["data/"],
            dependencies=["fastapi"],
            repo_summary="A test repo",
        )
        assert facts.schema_version == "dm.repo-facts.v1"

    def test_stage1_output(self):
        output = Stage1ScanOutput(
            repo=RepoRef(
                repo_id="test",
                full_name="org/repo",
                url="https://github.com/org/repo",
                default_branch="main",
                commit_sha="abc",
                local_path="/tmp",
            ),
            findings=[],
            hypotheses=[],
            coverage={"answered_questions": [], "partial_questions": [], "uncovered_questions": []},
            recommended_for_stage15=False,
        )
        assert output.schema_version == "dm.stage1-scan-output.v1"


class TestValidation:
    def test_validation_report_pass(self):
        report = ValidationReport(
            status="PASS",
            checks=[],
        )
        assert report.status == "PASS"

    def test_validation_report_revise(self):
        report = ValidationReport(
            status="REVISE",
            checks=[
                {
                    "name": "Platform Fit",
                    "passed": False,
                    "severity": "blocking",
                    "details": ["cron in frontmatter"],
                }
            ],
            revise_instructions=["Remove cron from frontmatter"],
        )
        assert report.status == "REVISE"
        assert len(report.revise_instructions) == 1
