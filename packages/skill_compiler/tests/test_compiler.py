from __future__ import annotations

import json
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]

from doramagic_contracts.base import NeedProfile  # noqa: E402
from doramagic_contracts.cross_project import (  # noqa: E402
    SynthesisConflict,
    SynthesisDecision,
    SynthesisReportData,
)
from doramagic_contracts.envelope import ErrorCodes  # noqa: E402
from doramagic_contracts.skill import PlatformRules, SkillCompilerInput  # noqa: E402
from doramagic_skill_compiler.compiler import run_skill_compiler  # noqa: E402


def _unsafe_construct(model_class, **values):
    if hasattr(model_class, "model_construct"):
        return model_class.model_construct(**values)
    return model_class.construct(**values)


def _need_profile() -> NeedProfile:
    return NeedProfile(
        raw_input="Build an OpenClaw calorie tracker skill",
        keywords=["calorie", "tracker", "nutrition"],
        intent="Calorie tracker skill for OpenClaw",
        search_directions=[],
        constraints=["OpenClaw SKILL.md", "Use ~/clawd/ storage"],
        quality_expectations={"traceability": "high"},
    )


def _decision(
    decision_id: str,
    statement: str,
    decision: str = "include",
    rationale: str = "Selected from synthesis consensus.",
    source_refs: list[str] | None = None,
) -> SynthesisDecision:
    return SynthesisDecision(
        decision_id=decision_id,
        statement=statement,
        decision=decision,
        rationale=rationale,
        source_refs=source_refs
        or [
            "https://github.com/acme/calorie-skill license:MIT",
        ],
        demand_fit="high",
    )


def _conflict(conflict_id: str = "CF-001") -> SynthesisConflict:
    return SynthesisConflict(
        conflict_id=conflict_id,
        category="architecture",
        title="Storage strategy mismatch",
        positions=["local files", "database"],
        recommended_resolution="Prefer local files for OpenClaw.",
        source_refs=["https://github.com/acme/conflict-doc"],
    )


def _report(
    selected: list[SynthesisDecision] | None = None,
    excluded: list[SynthesisDecision] | None = None,
    conflicts: list[SynthesisConflict] | None = None,
    consensus: list[SynthesisDecision] | None = None,
) -> SynthesisReportData:
    return SynthesisReportData(
        consensus=consensus or [],
        conflicts=conflicts or [],
        unique_knowledge=[],
        selected_knowledge=selected
        or [
            _decision(
                "SEL-001",
                "Read nutrition entries, parse them, and write normalized meal summaries.",
            ),
            _decision("SEL-002", "Store daily logs separately from user profile memory."),
            _decision(
                "SEL-003", "Ask the model to explain confidence and missing nutrition fields."
            ),
        ],
        excluded_knowledge=excluded
        or [
            _decision(
                "EX-001",
                "Run a cron job every night to refresh nutrition indexes.",
                decision="exclude",
                rationale="Cron is not supported on OpenClaw.",
                source_refs=["https://github.com/acme/cron-pattern license:Apache-2.0"],
            )
        ],
        open_questions=[],
    )


def _platform_rules() -> PlatformRules:
    fixture_path = PROJECT_ROOT / "data" / "fixtures" / "platform_rules.json"
    return PlatformRules(**json.loads(fixture_path.read_text(encoding="utf-8")))


def _input(report: SynthesisReportData | None = None) -> SkillCompilerInput:
    return SkillCompilerInput(
        need_profile=_need_profile(),
        synthesis_report=report or _report(),
        platform_rules=_platform_rules(),
    )


def test_normal_path_writes_skill_bundle(tmp_path) -> None:
    os.environ["DORAMAGIC_SKILL_COMPILER_OUTPUT_DIR"] = str(tmp_path)
    result = run_skill_compiler(_input())

    assert result.status == "ok"
    assert result.data is not None
    skill_md = Path(result.data.skill_md_path).read_text(encoding="utf-8")
    assert "allowed-tools:" in skill_md
    assert "  - exec" in skill_md
    assert "  - read" in skill_md
    assert "  - write" in skill_md
    assert "~/clawd/" in skill_md


def test_unresolved_option_returns_blocked(tmp_path) -> None:
    os.environ["DORAMAGIC_SKILL_COMPILER_OUTPUT_DIR"] = str(tmp_path)
    report = _report(
        consensus=[_decision("OPT-001", "Choose either sqlite or json storage.", decision="option")]
    )
    result = run_skill_compiler(_input(report))

    assert result.status == "blocked"
    assert result.error_code == ErrorCodes.UNRESOLVED_CONFLICT


def test_provenance_lists_source_urls(tmp_path) -> None:
    os.environ["DORAMAGIC_SKILL_COMPILER_OUTPUT_DIR"] = str(tmp_path)
    result = run_skill_compiler(_input())

    assert result.data is not None
    provenance = Path(result.data.provenance_md_path).read_text(encoding="utf-8")
    assert "https://github.com/acme/calorie-skill" in provenance
    assert "License: MIT" in provenance


def test_cron_is_not_written_to_frontmatter(tmp_path) -> None:
    os.environ["DORAMAGIC_SKILL_COMPILER_OUTPUT_DIR"] = str(tmp_path)
    report = _report(
        selected=[
            _decision("SEL-010", "Compile daily summaries and never expose cron in metadata."),
            _decision("SEL-011", "Store reports under ~/tmp/cache before normalization."),
        ]
    )
    result = run_skill_compiler(_input(report))

    assert result.data is not None
    skill_md = Path(result.data.skill_md_path).read_text(encoding="utf-8")
    frontmatter = skill_md.split("---", 2)[1]
    assert "cron:" not in frontmatter


def test_manifest_file_has_expected_structure(tmp_path) -> None:
    os.environ["DORAMAGIC_SKILL_COMPILER_OUTPUT_DIR"] = str(tmp_path)
    result = run_skill_compiler(_input())

    assert result.data is not None
    manifest_path = Path(result.data.skill_md_path).with_name("skill_build_manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "dm.skill-build-manifest.v1"
    assert manifest["output_files"] == [
        "SKILL.md",
        "PROVENANCE.md",
        "LIMITATIONS.md",
        "README.md",
        "skill_build_manifest.json",
    ]
    assert manifest["selected_decision_ids"] == ["SEL-001", "SEL-002", "SEL-003"]


def test_missing_platform_rules_returns_blocked() -> None:
    invalid_input = _unsafe_construct(
        SkillCompilerInput,
        need_profile=_need_profile(),
        synthesis_report=_report(),
        platform_rules=None,
    )

    result = run_skill_compiler(invalid_input)

    assert result.status == "blocked"
    assert result.error_code == ErrorCodes.UPSTREAM_MISSING


def test_limitations_include_excluded_knowledge(tmp_path) -> None:
    os.environ["DORAMAGIC_SKILL_COMPILER_OUTPUT_DIR"] = str(tmp_path)
    result = run_skill_compiler(_input())

    assert result.data is not None
    limitations = Path(result.data.limitations_md_path).read_text(encoding="utf-8")
    assert "EX-001" in limitations
    assert "Cron is not supported on OpenClaw." in limitations
