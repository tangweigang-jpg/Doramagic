"""platform-openclaw.validator — OpenClaw skill bundle static validation."""

from __future__ import annotations

import re
import time
from pathlib import Path

from doramagic_contracts.envelope import (
    ErrorCodes,
    ModuleResultEnvelope,
    RunMetrics,
    WarningItem,
)
from doramagic_contracts.skill import (
    ValidationCheck,
    ValidationInput,
    ValidationReport,
)

MODULE_NAME = "platform-openclaw.validator"
REPORT_FILENAME = "validation_report.json"

# Patterns used in checks
URL_PATTERN = re.compile(r"https?://[^\s,)\"\']+")
LICENSE_PATTERN = re.compile(r"\blicense\b", re.IGNORECASE)
CONFLICT_MARKER_PATTERN = re.compile(
    r"(<<<<<<|>>>>>>|======|UNRESOLVED|TODO.*conflict|FIXME.*conflict)",
    re.IGNORECASE,
)
DARK_TRAP_PATTERNS = [
    (
        re.compile(r"\bcron\b", re.IGNORECASE),
        "cron job reference found (OpenClaw does not support cron)",
    ),
    (re.compile(r"\bsudo\b", re.IGNORECASE), "sudo usage detected (privilege escalation risk)"),
    (re.compile(r"rm\s+-rf", re.IGNORECASE), "destructive rm -rf command detected"),
    (re.compile(r"\beval\s*\(", re.IGNORECASE), "eval() usage detected (code injection risk)"),
    (
        re.compile(r"\b(?:password|secret|token|api_key|apikey)\s*=\s*['\"]?\S", re.IGNORECASE),
        "hardcoded credential pattern detected",
    ),
    (re.compile(r"\/etc\/passwd|\/etc\/shadow"), "access to sensitive system files detected"),
    (
        re.compile(r"\b(?:curl|wget)\b.*\|\s*(?:bash|sh)\b", re.IGNORECASE),
        "pipe-to-shell pattern detected (supply chain risk)",
    ),
]

# Keywords hinting at features/capabilities (used in Completeness check)
CAPABILITY_KEYWORDS = re.compile(
    r"\b(read|write|exec|store|log|parse|validate|summarize|extract|track|record|fetch|update|delete)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _read_file(path_str: str) -> tuple[str | None, str | None]:
    """Return (content, error_message). error_message is None if success."""
    path = Path(path_str).expanduser()
    if not path.exists():
        return None, f"File not found: {path_str}"
    try:
        content = path.read_text(encoding="utf-8")
        return content, None
    except Exception as exc:
        return None, f"Cannot read {path_str}: {exc}"


def _parse_frontmatter(skill_md: str) -> tuple[str, str]:
    """Split SKILL.md into (frontmatter_block, body). frontmatter_block excludes delimiters."""
    parts = skill_md.split("---", 2)
    if len(parts) >= 3:
        return parts[1], parts[2]
    return "", skill_md


def _frontmatter_keys(frontmatter: str) -> list[str]:
    """Return top-level YAML keys from raw frontmatter text."""
    keys = []
    for line in frontmatter.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and ":" in stripped:
            key = stripped.split(":")[0].strip()
            if key:
                keys.append(key)
    return keys


def _frontmatter_tools(frontmatter: str) -> list[str]:
    """Extract items listed under 'allowed-tools:' block."""
    tools: list[str] = []
    in_tools_block = False
    for line in frontmatter.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("allowed-tools"):
            in_tools_block = True
            # Handle inline format: allowed-tools: exec, read, write
            after_colon = stripped.split(":", 1)[1].strip()
            if after_colon:
                for item in re.split(r"[,\s]+", after_colon):
                    item = item.strip().lstrip("-").strip()
                    if item:
                        tools.append(item)
            continue
        if in_tools_block:
            if stripped.startswith("-"):
                tool = stripped.lstrip("-").strip()
                if tool:
                    tools.append(tool)
            elif (
                stripped
                and not stripped.startswith(" ")
                and not stripped.startswith("\t")
                and ":" in stripped
            ):
                # New top-level key — exit block
                in_tools_block = False
    return tools


def _blocked_envelope(
    error_code: str, wall_time_ms: int = 0
) -> ModuleResultEnvelope[ValidationReport]:
    return ModuleResultEnvelope(
        module_name=MODULE_NAME,
        status="blocked",
        error_code=error_code,
        data=None,
        metrics=RunMetrics(
            wall_time_ms=wall_time_ms,
            llm_calls=0,
            prompt_tokens=0,
            completion_tokens=0,
            estimated_cost_usd=0.0,
            retries=0,
        ),
    )


# ---------------------------------------------------------------------------
# Individual check implementations
# ---------------------------------------------------------------------------


def _check_consistency(skill_md: str, body: str) -> ValidationCheck:
    """Check that SKILL.md has no internal contradictions (e.g., duplicate headings, conflicting tool lists)."""
    details: list[str] = []

    # Detect duplicate section headings
    headings = re.findall(r"^#{1,3}\s+(.+)$", body, re.MULTILINE)
    seen: set = set()
    for heading in headings:
        normalized = heading.strip().lower()
        if normalized in seen:
            details.append(f"Duplicate section heading: '{heading.strip()}'")
        seen.add(normalized)

    # Detect contradictory storage paths (non-clawd paths alongside clawd paths)
    storage_paths = re.findall(r"~/\S+", skill_md)
    non_clawd = [p for p in storage_paths if not p.startswith("~/clawd/")]
    clawd = [p for p in storage_paths if p.startswith("~/clawd/")]
    if clawd and non_clawd:
        details.append(
            f"Mixed storage paths detected: non-~/clawd/ paths {non_clawd[:3]} alongside ~/clawd/ paths"
        )

    return ValidationCheck(
        name="Consistency",
        passed=len(details) == 0,
        severity="blocking",
        details=details,
    )


def _check_completeness(skill_md: str, need_profile_keywords: list[str]) -> ValidationCheck:
    """Check that skill content covers the declared keywords/capabilities from need_profile."""
    details: list[str] = []
    skill_lower = skill_md.lower()

    missing_keywords: list[str] = []
    for kw in need_profile_keywords:
        if kw.lower() not in skill_lower:
            missing_keywords.append(kw)

    if missing_keywords:
        details.append(f"Keywords from need_profile not found in skill: {missing_keywords}")

    # Check that at least one actionable capability keyword exists in the body
    if not CAPABILITY_KEYWORDS.search(skill_md):
        details.append(
            "SKILL.md contains no actionable capability keywords (read/write/exec/store/parse etc.)"
        )

    return ValidationCheck(
        name="Completeness",
        passed=len(details) == 0,
        severity="warning",  # Degraded to warning: cross-language keyword mismatch expected
        details=details,
    )


def _check_traceability(provenance_md: str) -> ValidationCheck:
    """Check that PROVENANCE.md contains traceable source URLs."""
    details: list[str] = []

    urls = URL_PATTERN.findall(provenance_md)
    if not urls:
        details.append(
            "PROVENANCE.md contains no source URLs (https://...) — knowledge is not traceable"
        )

    # Check for placeholder or empty source refs
    if re.search(r"Source Refs:\s*(none|N/A|-)\s*$", provenance_md, re.IGNORECASE | re.MULTILINE):
        details.append("PROVENANCE.md contains entries with no source refs listed")

    return ValidationCheck(
        name="Traceability",
        passed=len(details) == 0,
        severity="warning",  # Degraded to warning: compiler may lack URLs in early pipeline runs
        details=details,
    )


def _check_platform_fit(
    frontmatter: str,
    platform_rules_allowed_tools: list[str],
    platform_rules_whitelist: list[str],
    platform_rules_forbidden: list[str],
    storage_prefix: str,
    skill_md: str,
) -> ValidationCheck:
    """Check OpenClaw platform compliance: tools, forbidden fields, metadata keys, storage prefix."""
    details: list[str] = []

    # 1. Check allowed-tools in frontmatter
    actual_tools = _frontmatter_tools(frontmatter)
    allowed_set = set(platform_rules_allowed_tools)
    if not actual_tools:
        details.append("Frontmatter missing 'allowed-tools' block")
    else:
        invalid_tools = [t for t in actual_tools if t not in allowed_set]
        if invalid_tools:
            details.append(
                f"Frontmatter 'allowed-tools' contains non-allowed tools: {invalid_tools} (allowed: {platform_rules_allowed_tools})"
            )

    # 2. Check forbidden frontmatter fields
    fm_keys = _frontmatter_keys(frontmatter)
    for forbidden_key in platform_rules_forbidden:
        if forbidden_key in fm_keys:
            details.append(f"Frontmatter contains forbidden field: {forbidden_key}")

    # 3. Check metadata keys are in whitelist
    # Standard SKILL.md fields that are NOT metadata — always allowed
    standard_fields = {"name", "description", "allowed-tools", "version", "author"}
    whitelist_set = set(platform_rules_whitelist) | standard_fields
    for key in fm_keys:
        # Normalize: allowed-tools might appear as 'allowed-tools'
        normalized_key = key.replace("-", "_")
        if key not in whitelist_set and normalized_key not in {
            k.replace("-", "_") for k in whitelist_set
        }:
            details.append(f"Frontmatter key '{key}' is not in OpenClaw metadata whitelist")

    # 4. Check that storage paths use ~/clawd/
    storage_paths = re.findall(r"~/\S+", skill_md)
    bad_paths = [p for p in storage_paths if not p.startswith(storage_prefix.rstrip("/"))]
    if bad_paths:
        details.append(
            f"Storage paths not using required prefix '{storage_prefix}': {bad_paths[:5]}"
        )

    return ValidationCheck(
        name="Platform Fit",
        passed=len(details) == 0,
        severity="blocking",
        details=details,
    )


def _check_conflict_resolution(skill_md: str, limitations_md: str) -> ValidationCheck:
    """Check that no unresolved conflicts remain in the skill bundle."""
    details: list[str] = []

    for text, label in [(skill_md, "SKILL.md"), (limitations_md, "LIMITATIONS.md")]:
        matches = CONFLICT_MARKER_PATTERN.findall(text)
        if matches:
            details.append(f"{label} contains unresolved conflict markers: {matches[:3]}")

    return ValidationCheck(
        name="Conflict Resolution",
        passed=len(details) == 0,
        severity="blocking",
        details=details,
    )


def _check_license(provenance_md: str) -> ValidationCheck:
    """Warn if license information is missing or unknown in PROVENANCE.md."""
    details: list[str] = []

    # Look for license mentions in provenance
    has_license = LICENSE_PATTERN.search(provenance_md) is not None
    if not has_license:
        details.append(
            "PROVENANCE.md contains no license information — license compatibility cannot be verified"
        )
    else:
        # Check for unknown/unspecified licenses
        if re.search(r"license:\s*(unknown|unspecified|none|-)\b", provenance_md, re.IGNORECASE):
            details.append("One or more source project licenses are unknown or unspecified")

    return ValidationCheck(
        name="License",
        passed=len(details) == 0,
        severity="warning",
        details=details,
    )


def _check_dark_trap_scan(skill_md: str, limitations_md: str, readme_md: str) -> ValidationCheck:
    """Scan for known dark trap patterns (security / anti-patterns) across bundle files."""
    details: list[str] = []
    combined = "\n".join([skill_md, limitations_md, readme_md])

    for pattern, description in DARK_TRAP_PATTERNS:
        if pattern.search(combined):
            details.append(f"Dark trap detected: {description}")

    return ValidationCheck(
        name="Dark Trap Scan",
        passed=len(details) == 0,
        severity="warning",
        details=details,
    )


# ---------------------------------------------------------------------------
# Revise instruction generator
# ---------------------------------------------------------------------------


def _revise_instructions(checks: list[ValidationCheck]) -> list[str]:
    instructions: list[str] = []
    for check in checks:
        if not check.passed and check.severity == "blocking":
            for detail in check.details:
                if check.name == "Platform Fit" and "forbidden field" in detail:
                    field = detail.split(":")[-1].strip()
                    instructions.append(
                        f"Remove '{field}' from SKILL.md frontmatter. "
                        "If scheduling is needed, document it in README installation notes."
                    )
                elif check.name == "Platform Fit" and "non-allowed tools" in detail:
                    instructions.append(
                        "Replace non-standard allowed-tools values with exec, read, and/or write only."
                    )
                elif (
                    check.name == "Platform Fit" and "not in OpenClaw metadata whitelist" in detail
                ):
                    instructions.append(
                        "Remove or rename frontmatter keys to match OpenClaw whitelist: "
                        "always, emoji, homepage, skillKey, primaryEnv, os, requires, install."
                    )
                elif check.name == "Platform Fit" and "not using required prefix" in detail:
                    instructions.append(
                        "Update all storage paths to use ~/clawd/ prefix instead of other home directory paths."
                    )
                elif check.name == "Traceability":
                    instructions.append(
                        "Add at least one source URL (https://...) to PROVENANCE.md for each knowledge item."
                    )
                elif check.name == "Completeness":
                    instructions.append(
                        "Ensure SKILL.md body references all keywords from need_profile and includes "
                        "at least one actionable step (read/write/exec/store/parse)."
                    )
                elif check.name == "Consistency":
                    instructions.append(
                        "Remove duplicate section headings and ensure all storage paths consistently "
                        "use ~/clawd/ prefix."
                    )
                elif check.name == "Conflict Resolution":
                    instructions.append(
                        "Resolve all conflict markers (<<<<<<, >>>>>>, UNRESOLVED) before delivery."
                    )
                else:
                    instructions.append(f"Fix {check.name} issue: {detail}")
    return instructions


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run_validation(input_data: ValidationInput) -> ModuleResultEnvelope[ValidationReport]:
    """
    Validate a skill bundle against OpenClaw platform rules.

    Returns:
        ModuleResultEnvelope with ValidationReport (PASS / REVISE / BLOCKED).
    """
    started_at = time.time()

    # --- Pre-flight: read all bundle files ---
    bundle = input_data.skill_bundle
    file_errors: list[str] = []

    skill_content, skill_err = _read_file(bundle.skill_md_path)
    if skill_err:
        file_errors.append(skill_err)

    provenance_content, provenance_err = _read_file(bundle.provenance_md_path)
    if provenance_err:
        file_errors.append(provenance_err)

    limitations_content, limitations_err = _read_file(bundle.limitations_md_path)
    if limitations_err:
        file_errors.append(limitations_err)

    readme_content, readme_err = _read_file(bundle.readme_md_path)
    if readme_err:
        file_errors.append(readme_err)

    if file_errors:
        wall_ms = max(1, int((time.time() - started_at) * 1000))
        return _blocked_envelope(ErrorCodes.UPSTREAM_MISSING, wall_ms)

    # --- All files readable — run checks ---
    rules = input_data.platform_rules
    frontmatter, body = _parse_frontmatter(skill_content)  # type: ignore[arg-type]
    need_keywords = input_data.need_profile.keywords

    checks: list[ValidationCheck] = [
        _check_consistency(skill_content, body),  # type: ignore[arg-type]
        _check_completeness(skill_content, need_keywords),  # type: ignore[arg-type]
        _check_traceability(provenance_content),  # type: ignore[arg-type]
        _check_platform_fit(
            frontmatter,
            rules.allowed_tools,
            rules.metadata_openclaw_whitelist,
            rules.forbid_frontmatter_fields,
            rules.storage_prefix,
            skill_content,  # type: ignore[arg-type]
        ),
        _check_conflict_resolution(skill_content, limitations_content),  # type: ignore[arg-type]
        _check_license(provenance_content),  # type: ignore[arg-type]
        _check_dark_trap_scan(skill_content, limitations_content, readme_content),  # type: ignore[arg-type]
    ]

    # --- Determine report status ---
    blocking_failures = [c for c in checks if not c.passed and c.severity == "blocking"]

    if blocking_failures:
        status = "REVISE"
        revise_instructions = _revise_instructions(checks)
    else:
        status = "PASS"
        revise_instructions = []

    report = ValidationReport(
        status=status,
        checks=checks,
        revise_instructions=revise_instructions,
    )

    # --- Build envelope ---
    envelope_warnings: list[WarningItem] = []
    warning_failures = [c for c in checks if not c.passed and c.severity == "warning"]
    for wf in warning_failures:
        for detail in wf.details:
            envelope_warnings.append(
                WarningItem(code=wf.name.upper().replace(" ", "_"), message=detail)
            )

    wall_ms = max(1, int((time.time() - started_at) * 1000))
    return ModuleResultEnvelope(
        module_name=MODULE_NAME,
        status="ok",
        error_code=None,
        warnings=envelope_warnings,
        data=report,
        metrics=RunMetrics(
            wall_time_ms=wall_ms,
            llm_calls=0,
            prompt_tokens=0,
            completion_tokens=0,
            estimated_cost_usd=0.0,
            retries=0,
        ),
    )
