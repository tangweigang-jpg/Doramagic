"""Skill 编译与校验模型 — Phase F/G。"""

from __future__ import annotations

from typing import Optional, Literal

from pydantic import BaseModel

from doramagic_contracts.base import NeedProfile
from doramagic_contracts.cross_project import SynthesisReportData

# --- Platform Rules ---


class PlatformRules(BaseModel):
    """OpenClaw 平台适配规则 — Round 0 冻结，不允许选手修改。"""

    schema_version: str = "dm.platform-rules.v1"
    allowed_tools: list[str] = ["exec", "read", "write"]
    metadata_openclaw_whitelist: list[str] = [
        "always",
        "emoji",
        "homepage",
        "skillKey",
        "primaryEnv",
        "os",
        "requires",
        "install",
    ]
    forbid_frontmatter_fields: list[str] = ["cron"]
    storage_prefix: str = "~/clawd/"


# --- Skill Compiler ---


class SkillCompilerInput(BaseModel):
    schema_version: str = "dm.skill-compiler-input.v1"
    need_profile: NeedProfile
    synthesis_report: SynthesisReportData
    platform_rules: PlatformRules


class SkillBuildManifest(BaseModel):
    schema_version: str = "dm.skill-build-manifest.v1"
    skill_name: str
    selected_decision_ids: list[str]
    omitted_decision_ids: list[str]
    platform_transformations: list[str]
    output_files: list[str]


class SkillCompilerOutput(BaseModel):
    schema_version: str = "dm.skill-compiler-output.v1"
    build_manifest: SkillBuildManifest
    skill_md_path: str
    provenance_md_path: str
    limitations_md_path: str
    readme_md_path: str


# --- Validator ---


class SkillBundlePaths(BaseModel):
    skill_md_path: str
    readme_md_path: str
    provenance_md_path: str
    limitations_md_path: str


class ValidationInput(BaseModel):
    schema_version: str = "dm.validation-input.v1"
    need_profile: NeedProfile
    synthesis_report: SynthesisReportData
    skill_bundle: SkillBundlePaths
    platform_rules: PlatformRules


class ValidationCheck(BaseModel):
    name: Literal[
        "Consistency",
        "Completeness",
        "Traceability",
        "Platform Fit",
        "Conflict Resolution",
        "License",
        "Dark Trap Scan",
    ]
    passed: bool
    severity: Literal["blocking", "warning"]
    details: list[str]


class ValidationReport(BaseModel):
    schema_version: str = "dm.validation-report.v1"
    status: Literal["PASS", "REVISE", "BLOCKED"]
    checks: list[ValidationCheck]
    revise_instructions: list[str] = []
