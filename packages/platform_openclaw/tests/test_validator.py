"""Tests for platform-openclaw.validator."""

from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]

from doramagic_contracts.base import NeedProfile  # noqa: E402
from doramagic_contracts.cross_project import (  # noqa: E402
    SynthesisDecision,
    SynthesisReportData,
)
from doramagic_contracts.envelope import ErrorCodes  # noqa: E402
from doramagic_contracts.skill import (  # noqa: E402
    PlatformRules,
    SkillBundlePaths,
    ValidationInput,
)
from doramagic_platform_openclaw.validator import run_validation  # noqa: E402

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_FIXTURE_RULES = PROJECT_ROOT / "data" / "fixtures" / "platform_rules.json"


def _platform_rules() -> PlatformRules:
    return PlatformRules(**json.loads(_FIXTURE_RULES.read_text(encoding="utf-8")))


def _need_profile(keywords: list[str] | None = None) -> NeedProfile:
    return NeedProfile(
        raw_input="Build a calorie tracker skill for OpenClaw",
        keywords=keywords or ["calorie", "tracker"],
        intent="Calorie tracker skill",
        search_directions=[],
        constraints=["OpenClaw platform"],
        quality_expectations={},
    )


def _decision(
    decision_id: str = "SEL-001",
    statement: str = "Read food entries and write calorie logs.",
    source_refs: list[str] | None = None,
) -> SynthesisDecision:
    return SynthesisDecision(
        decision_id=decision_id,
        statement=statement,
        decision="include",
        rationale="Selected from synthesis.",
        source_refs=source_refs or ["https://github.com/example/calorie-tracker license:MIT"],
        demand_fit="high",
    )


def _synthesis_report() -> SynthesisReportData:
    return SynthesisReportData(
        consensus=[],
        conflicts=[],
        unique_knowledge=[],
        selected_knowledge=[_decision()],
        excluded_knowledge=[],
        open_questions=[],
    )


def _write_valid_bundle(tmp_path: Path) -> SkillBundlePaths:
    """Write a fully compliant skill bundle and return paths."""
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text(
        "---\n"
        "skillKey: calorie-tracker\n"
        "always: false\n"
        "os:\n"
        "  - macos\n"
        "install: Store runtime data under ~/clawd/calorie-tracker/\n"
        "allowed-tools:\n"
        "  - exec\n"
        "  - read\n"
        "  - write\n"
        "---\n"
        "# Calorie Tracker\n\n"
        "## Purpose\nTrack calorie intake.\n\n"
        "## Workflow\n- Read food entries from user input.\n"
        "- Parse nutritional data.\n"
        "- Write daily log to ~/clawd/calorie-tracker/log.json.\n\n"
        "## Storage\n- Store all data under ~/clawd/calorie-tracker/\n\n"
        "## AI Prompt\n- Explain calorie estimates briefly.\n",
        encoding="utf-8",
    )

    provenance_md = tmp_path / "PROVENANCE.md"
    provenance_md.write_text(
        "# Provenance\n\n"
        "## SEL-001\n"
        "- Statement: Read food entries and write calorie logs.\n"
        "- Rationale: Selected from synthesis.\n"
        "- Source Refs: https://github.com/example/calorie-tracker\n"
        "- Source URLs: https://github.com/example/calorie-tracker\n"
        "- License: MIT\n",
        encoding="utf-8",
    )

    limitations_md = tmp_path / "LIMITATIONS.md"
    limitations_md.write_text(
        "# Limitations\n\nNo explicit exclusions were supplied.\n",
        encoding="utf-8",
    )

    readme_md = tmp_path / "README.md"
    readme_md.write_text(
        "# Calorie Tracker\n\nGenerated OpenClaw skill bundle.\n",
        encoding="utf-8",
    )

    return SkillBundlePaths(
        skill_md_path=str(skill_md),
        readme_md_path=str(readme_md),
        provenance_md_path=str(provenance_md),
        limitations_md_path=str(limitations_md),
    )


def _validation_input(
    bundle: SkillBundlePaths, keywords: list[str] | None = None
) -> ValidationInput:
    return ValidationInput(
        need_profile=_need_profile(keywords),
        synthesis_report=_synthesis_report(),
        skill_bundle=bundle,
        platform_rules=_platform_rules(),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_all_pass_returns_pass(tmp_path: Path) -> None:
    """A fully compliant bundle must produce PASS status."""
    bundle = _write_valid_bundle(tmp_path)
    result = run_validation(_validation_input(bundle))

    assert result.status == "ok"
    assert result.data is not None
    assert result.data.status == "PASS"
    assert result.data.revise_instructions == []
    # All checks must be present
    check_names = {c.name for c in result.data.checks}
    assert check_names == {
        "Consistency",
        "Completeness",
        "Traceability",
        "Platform Fit",
        "Conflict Resolution",
        "License",
        "Dark Trap Scan",
    }


def test_allowed_tools_not_exec_read_write_returns_blocking_failure(tmp_path: Path) -> None:
    """Non-standard allowed-tools value must produce a blocking Platform Fit failure."""
    bundle = _write_valid_bundle(tmp_path)
    # Overwrite skill with invalid tool
    Path(bundle.skill_md_path).write_text(
        "---\n"
        "skillKey: calorie-tracker\n"
        "always: false\n"
        "os:\n"
        "  - macos\n"
        "install: Store runtime data under ~/clawd/calorie-tracker/\n"
        "allowed-tools:\n"
        "  - exec\n"
        "  - read\n"
        "  - network\n"  # <-- invalid tool
        "---\n"
        "# Calorie Tracker\n\n"
        "## Workflow\n- Read entries.\n- Write logs to ~/clawd/calorie-tracker/log.json.\n",
        encoding="utf-8",
    )

    result = run_validation(_validation_input(bundle))

    assert result.status == "ok"
    assert result.data is not None
    assert result.data.status == "REVISE"

    platform_check = next(c for c in result.data.checks if c.name == "Platform Fit")
    assert not platform_check.passed
    assert platform_check.severity == "blocking"
    assert any("network" in d for d in platform_check.details)


def test_cron_in_frontmatter_returns_revise(tmp_path: Path) -> None:
    """cron in frontmatter must cause REVISE (not PASS), Platform Fit blocking failure."""
    bundle = _write_valid_bundle(tmp_path)
    Path(bundle.skill_md_path).write_text(
        "---\n"
        "skillKey: calorie-tracker\n"
        "always: false\n"
        "cron: '0 * * * *'\n"  # <-- forbidden
        "allowed-tools:\n"
        "  - exec\n"
        "  - read\n"
        "  - write\n"
        "---\n"
        "# Calorie Tracker\n\n"
        "## Workflow\n- Read entries.\n- Write logs to ~/clawd/calorie-tracker/log.json.\n",
        encoding="utf-8",
    )

    result = run_validation(_validation_input(bundle))

    assert result.data is not None
    assert result.data.status != "PASS"  # must be REVISE or BLOCKED

    platform_check = next(c for c in result.data.checks if c.name == "Platform Fit")
    assert not platform_check.passed
    assert platform_check.severity == "blocking"
    assert any("cron" in d.lower() for d in platform_check.details)


def test_provenance_missing_url_fails_traceability(tmp_path: Path) -> None:
    """PROVENANCE.md with no source URLs must fail Traceability."""
    bundle = _write_valid_bundle(tmp_path)
    Path(bundle.provenance_md_path).write_text(
        "# Provenance\n\n"
        "## SEL-001\n"
        "- Statement: Some statement.\n"
        "- Rationale: Some rationale.\n"
        "- Source Refs: none\n"  # no URL
        "- License: MIT\n",
        encoding="utf-8",
    )

    result = run_validation(_validation_input(bundle))

    assert result.data is not None
    traceability_check = next(c for c in result.data.checks if c.name == "Traceability")
    assert not traceability_check.passed
    assert traceability_check.severity == "warning"
    assert result.data.status == "PASS"


def test_skill_file_missing_returns_blocked_upstream_missing(tmp_path: Path) -> None:
    """Missing SKILL.md must return blocked with E_UPSTREAM_MISSING."""
    bundle = SkillBundlePaths(
        skill_md_path=str(tmp_path / "NONEXISTENT_SKILL.md"),
        readme_md_path=str(tmp_path / "README.md"),
        provenance_md_path=str(tmp_path / "PROVENANCE.md"),
        limitations_md_path=str(tmp_path / "LIMITATIONS.md"),
    )
    # Only readme exists
    (tmp_path / "README.md").write_text("# Readme", encoding="utf-8")

    result = run_validation(_validation_input(bundle))

    assert result.status == "blocked"
    assert result.error_code == ErrorCodes.UPSTREAM_MISSING
    assert result.data is None


def test_warning_checks_do_not_block_pass(tmp_path: Path) -> None:
    """Warning-level failures (License, Dark Trap Scan) must not prevent PASS."""
    bundle = _write_valid_bundle(tmp_path)
    # Remove license info from provenance — should generate a warning but not block
    Path(bundle.provenance_md_path).write_text(
        "# Provenance\n\n"
        "## SEL-001\n"
        "- Statement: Read food entries and write calorie logs.\n"
        "- Source Refs: https://github.com/example/calorie-tracker\n"
        "- Source URLs: https://github.com/example/calorie-tracker\n"
        # No license line
        "\n",
        encoding="utf-8",
    )

    result = run_validation(_validation_input(bundle))

    assert result.status == "ok"
    assert result.data is not None
    assert result.data.status == "PASS"

    license_check = next(c for c in result.data.checks if c.name == "License")
    assert not license_check.passed
    assert license_check.severity == "warning"


def test_all_bundle_files_missing_returns_blocked(tmp_path: Path) -> None:
    """All four bundle files missing must return blocked."""
    bundle = SkillBundlePaths(
        skill_md_path=str(tmp_path / "SKILL.md"),
        readme_md_path=str(tmp_path / "README.md"),
        provenance_md_path=str(tmp_path / "PROVENANCE.md"),
        limitations_md_path=str(tmp_path / "LIMITATIONS.md"),
    )

    result = run_validation(_validation_input(bundle))

    assert result.status == "blocked"
    assert result.error_code == ErrorCodes.UPSTREAM_MISSING


def test_revise_instructions_provided_on_blocking_failure(tmp_path: Path) -> None:
    """REVISE status must include revise_instructions."""
    bundle = _write_valid_bundle(tmp_path)
    # Introduce forbidden field
    Path(bundle.skill_md_path).write_text(
        "---\n"
        "skillKey: calorie-tracker\n"
        "cron: '0 * * * *'\n"
        "allowed-tools:\n"
        "  - exec\n"
        "  - read\n"
        "  - write\n"
        "---\n"
        "# Calorie Tracker\n\n"
        "## Workflow\n- Read entries.\n- Write logs to ~/clawd/calorie-tracker/log.json.\n",
        encoding="utf-8",
    )

    result = run_validation(_validation_input(bundle))

    assert result.data is not None
    assert result.data.status == "REVISE"
    assert len(result.data.revise_instructions) > 0
    # Revise instruction should mention cron
    combined = " ".join(result.data.revise_instructions).lower()
    assert "cron" in combined


def test_metrics_wall_time_positive(tmp_path: Path) -> None:
    """Metrics must be populated with non-negative values."""
    bundle = _write_valid_bundle(tmp_path)
    result = run_validation(_validation_input(bundle))

    assert result.metrics.wall_time_ms >= 1
    assert result.metrics.llm_calls == 0
    assert result.metrics.estimated_cost_usd == 0.0


def test_idempotent_same_input_same_output(tmp_path: Path) -> None:
    """Same input must produce same output (idempotency)."""
    bundle = _write_valid_bundle(tmp_path)
    input_data = _validation_input(bundle)

    result1 = run_validation(input_data)
    result2 = run_validation(input_data)

    assert result1.data is not None
    assert result2.data is not None
    assert result1.data.status == result2.data.status
    assert result1.data.schema_version == result2.data.schema_version
    for c1, c2 in zip(result1.data.checks, result2.data.checks):
        assert c1.name == c2.name
        assert c1.passed == c2.passed
        assert c1.severity == c2.severity


def test_dark_trap_scan_cron_in_body_is_warning_not_blocking(tmp_path: Path) -> None:
    """cron in body (not frontmatter) triggers Dark Trap Scan warning, not blocking."""
    bundle = _write_valid_bundle(tmp_path)
    # Add cron reference in body only (frontmatter is clean)
    original = Path(bundle.skill_md_path).read_text(encoding="utf-8")
    Path(bundle.skill_md_path).write_text(
        original + "\n## Notes\n- Do not use cron for scheduling.\n",
        encoding="utf-8",
    )

    result = run_validation(_validation_input(bundle))

    assert result.data is not None
    dark_trap = next(c for c in result.data.checks if c.name == "Dark Trap Scan")
    assert not dark_trap.passed
    assert dark_trap.severity == "warning"
    # Overall should still be PASS (warning doesn't block)
    assert result.data.status == "PASS"
