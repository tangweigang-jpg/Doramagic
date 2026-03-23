"""Mock OpenClaw skill compiler for race-mode development."""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "packages" / "contracts"))

from doramagic_contracts.cross_project import SynthesisConflict, SynthesisDecision  # noqa: E402
from doramagic_contracts.envelope import ErrorCodes, ModuleResultEnvelope, RunMetrics  # noqa: E402
from doramagic_contracts.skill import (  # noqa: E402
    PlatformRules,
    SkillBuildManifest,
    SkillCompilerInput,
    SkillCompilerOutput,
)

MODULE_NAME = "skill-compiler.openclaw"
SKILL_FILENAME = "SKILL.md"
PROVENANCE_FILENAME = "PROVENANCE.md"
LIMITATIONS_FILENAME = "LIMITATIONS.md"
README_FILENAME = "README.md"
MANIFEST_FILENAME = "skill_build_manifest.json"
URL_PATTERN = re.compile(r"https?://[^\s,)]+")
LICENSE_PATTERN = re.compile(r"license\s*[:=]\s*([A-Za-z0-9.\-+]+)", re.IGNORECASE)
STORAGE_KEYWORDS = (
    "store",
    "storage",
    "memory",
    "persist",
    "cache",
    "path",
    "profile",
    "log",
    "state",
)
PROMPT_KEYWORDS = (
    "prompt",
    "ask",
    "respond",
    "extract",
    "classify",
    "summarize",
    "explain",
    "llm",
    "agent",
)
WORKFLOW_KEYWORDS = (
    "workflow",
    "tool",
    "read",
    "write",
    "exec",
    "validate",
    "parse",
    "compile",
    "step",
)
TOOL_ALIASES = {
    "exec": "exec",
    "execute": "exec",
    "shell": "exec",
    "command": "exec",
    "read": "read",
    "read_file": "read",
    "list_tree": "read",
    "write": "write",
    "append": "write",
    "save": "write",
}


def _safe_dump(model) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return dict(model)


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return cleaned or "compiled-skill"


def _skill_name(input_data: SkillCompilerInput) -> str:
    candidates = [
        input_data.need_profile.intent,
        " ".join(input_data.need_profile.keywords),
        input_data.need_profile.raw_input,
    ]
    for candidate in candidates:
        if candidate.strip():
            return _slugify(candidate)
    return "compiled-skill"


def _output_dir(skill_name: str) -> Path:
    base_dir = os.environ.get("DORAMAGIC_SKILL_COMPILER_OUTPUT_DIR")
    if base_dir:
        return Path(base_dir).expanduser().resolve() / skill_name
    return Path(tempfile.gettempdir()) / "doramagic_skill_compiler" / skill_name


def _normalize_tools(platform_rules: PlatformRules) -> List[str]:
    normalized: List[str] = []
    for raw_tool in platform_rules.allowed_tools:
        mapped = TOOL_ALIASES.get(raw_tool.lower())
        if mapped and mapped not in normalized:
            normalized.append(mapped)

    for required in ("exec", "read", "write"):
        if required not in normalized:
            normalized.append(required)

    return normalized


def _all_decisions(input_data: SkillCompilerInput) -> List[SynthesisDecision]:
    report = input_data.synthesis_report
    decisions = []
    decisions.extend(report.consensus)
    decisions.extend(report.unique_knowledge)
    decisions.extend(report.selected_knowledge)
    decisions.extend(report.excluded_knowledge)
    return decisions


def _unresolved_items(input_data: SkillCompilerInput) -> List[str]:
    issues = []
    for conflict in input_data.synthesis_report.conflicts:
        issues.append("{0}: {1}".format(conflict.conflict_id, conflict.title))
    for decision in _all_decisions(input_data):
        if decision.decision == "option":
            issues.append("{0}: unresolved option".format(decision.decision_id))
    return issues


def _statement_bucket(decision: SynthesisDecision) -> str:
    haystack = "{0} {1}".format(decision.statement.lower(), decision.rationale.lower())
    if any(keyword in haystack for keyword in STORAGE_KEYWORDS):
        return "storage"
    if any(keyword in haystack for keyword in PROMPT_KEYWORDS):
        return "prompt"
    if any(keyword in haystack for keyword in WORKFLOW_KEYWORDS):
        return "workflow"
    return "workflow"


def _normalize_storage_statement(statement: str, skill_name: str, storage_prefix: str) -> str:
    normalized_prefix = storage_prefix.rstrip("/") + "/"
    base_path = "{0}{1}/".format(normalized_prefix, skill_name)
    rewritten = re.sub(r"~\/[A-Za-z0-9_./-]+", base_path, statement)
    if normalized_prefix not in rewritten:
        rewritten = "{0} Store persistent data under {1}".format(rewritten.rstrip("."), base_path)
    return rewritten


def _decision_lines(
    decisions: Sequence[SynthesisDecision],
    skill_name: str,
    storage_prefix: str,
) -> Tuple[List[str], List[str], List[str]]:
    workflow_lines: List[str] = []
    storage_lines: List[str] = []
    prompt_lines: List[str] = []

    for decision in decisions:
        line = decision.statement.strip()
        if not line:
            line = decision.rationale.strip() or decision.decision_id

        bucket = _statement_bucket(decision)
        if bucket == "storage":
            storage_lines.append(_normalize_storage_statement(line, skill_name, storage_prefix))
            continue
        if bucket == "prompt":
            prompt_lines.append(line)
            continue
        workflow_lines.append(line)

    if not workflow_lines:
        workflow_lines.append("Read user context, execute the required local steps, and write stable outputs.")
    if not storage_lines:
        storage_lines.append(
            "Store runtime state under {0}{1}/memory/ and keep user-facing artifacts deterministic."
            .format(storage_prefix.rstrip("/") + "/", skill_name)
        )
    if not prompt_lines:
        prompt_lines.append(
            "Explain tradeoffs briefly, cite the selected knowledge, and avoid unsupported automation promises."
        )

    return workflow_lines, storage_lines, prompt_lines


def _extract_urls(source_refs: Sequence[str]) -> List[str]:
    urls: List[str] = []
    for source_ref in source_refs:
        for match in URL_PATTERN.findall(source_ref):
            if match not in urls:
                urls.append(match)
    return urls


def _extract_license(decision: SynthesisDecision) -> Optional[str]:
    for source_ref in decision.source_refs:
        match = LICENSE_PATTERN.search(source_ref)
        if match:
            return match.group(1)
    match = LICENSE_PATTERN.search(decision.rationale)
    if match:
        return match.group(1)
    return None


def _frontmatter(
    skill_name: str,
    allowed_tools: Sequence[str],
    storage_prefix: str,
) -> str:
    lines = [
        "---",
        "skillKey: {0}".format(skill_name),
        "always: false",
        "os:",
        "  - macos",
        "  - linux",
        "install: Store all runtime data under {0}{1}/".format(storage_prefix.rstrip("/") + "/", skill_name),
        "allowed-tools:",
    ]
    for tool_name in allowed_tools:
        lines.append("  - {0}".format(tool_name))
    lines.append("---")
    return "\n".join(lines)


def _skill_markdown(
    input_data: SkillCompilerInput,
    skill_name: str,
    allowed_tools: Sequence[str],
) -> str:
    workflow_lines, storage_lines, prompt_lines = _decision_lines(
        input_data.synthesis_report.selected_knowledge,
        skill_name,
        input_data.platform_rules.storage_prefix,
    )
    title = skill_name.replace("-", " ").title()
    sections = [
        _frontmatter(skill_name, allowed_tools, input_data.platform_rules.storage_prefix),
        "# {0}".format(title),
        "",
        "## Purpose",
        input_data.need_profile.intent or input_data.need_profile.raw_input,
        "",
        "## Workflow",
    ]
    sections.extend("- {0}".format(line) for line in workflow_lines)
    sections.extend(
        [
            "",
            "## Storage",
        ]
    )
    sections.extend("- {0}".format(line) for line in storage_lines)
    sections.extend(
        [
            "",
            "## AI Prompt",
        ]
    )
    sections.extend("- {0}".format(line) for line in prompt_lines)
    sections.extend(
        [
            "",
            "## Platform Notes",
            "- Allowed tools are restricted to exec, read, and write.",
            "- Cron is intentionally omitted from frontmatter.",
        ]
    )
    return "\n".join(sections).strip() + "\n"


def _provenance_markdown(decisions: Sequence[SynthesisDecision]) -> str:
    lines = ["# Provenance", "", "Selected knowledge and source traceability:"]
    for decision in decisions:
        urls = _extract_urls(decision.source_refs)
        license_name = _extract_license(decision)
        lines.append("")
        lines.append("## {0}".format(decision.decision_id))
        lines.append("- Statement: {0}".format(decision.statement))
        lines.append("- Rationale: {0}".format(decision.rationale))
        lines.append("- Source Refs: {0}".format(", ".join(decision.source_refs) or "none"))
        if urls:
            lines.append("- Source URLs: {0}".format(", ".join(urls)))
        if license_name:
            lines.append("- License: {0}".format(license_name))
    return "\n".join(lines).strip() + "\n"


def _limitations_markdown(
    excluded: Sequence[SynthesisDecision],
    conflicts: Sequence[SynthesisConflict],
) -> str:
    lines = ["# Limitations", ""]
    if not excluded and not conflicts:
        lines.append("No explicit exclusions or unresolved conflicts were supplied.")
        return "\n".join(lines).strip() + "\n"

    if excluded:
        lines.append("## Excluded Knowledge")
        for decision in excluded:
            lines.append("- {0}: {1}".format(decision.decision_id, decision.statement))
            lines.append("  Reason: {0}".format(decision.rationale))
        lines.append("")

    if conflicts:
        lines.append("## Conflicts")
        for conflict in conflicts:
            lines.append("- {0}: {1}".format(conflict.conflict_id, conflict.title))
            lines.append("  Recommendation: {0}".format(conflict.recommended_resolution))

    return "\n".join(lines).strip() + "\n"


def _readme_markdown(
    skill_name: str,
    output_files: Sequence[str],
    transformations: Sequence[str],
) -> str:
    lines = [
        "# {0}".format(skill_name.replace("-", " ").title()),
        "",
        "Generated OpenClaw skill bundle.",
        "",
        "## Files",
    ]
    lines.extend("- {0}".format(file_name) for file_name in output_files)
    lines.extend(["", "## Platform Transformations"])
    lines.extend("- {0}".format(item) for item in transformations)
    return "\n".join(lines).strip() + "\n"


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _blocked_envelope(error_code: str) -> ModuleResultEnvelope[SkillCompilerOutput]:
    return ModuleResultEnvelope(
        module_name=MODULE_NAME,
        status="blocked",
        error_code=error_code,
        data=None,
        metrics=RunMetrics(
            wall_time_ms=0,
            llm_calls=0,
            prompt_tokens=0,
            completion_tokens=0,
            estimated_cost_usd=0.0,
            retries=0,
        ),
    )


def run_skill_compiler(
    input_data: SkillCompilerInput,
) -> ModuleResultEnvelope[SkillCompilerOutput]:
    started_at = time.time()
    if getattr(input_data, "platform_rules", None) is None:
        return _blocked_envelope(ErrorCodes.UPSTREAM_MISSING)

    unresolved_items = _unresolved_items(input_data)
    if unresolved_items:
        return _blocked_envelope(ErrorCodes.UNRESOLVED_CONFLICT)

    skill_name = _skill_name(input_data)
    output_dir = _output_dir(skill_name)
    allowed_tools = _normalize_tools(input_data.platform_rules)
    transformations = [
        "mapped allowed-tools to exec/read/write",
        "removed cron from frontmatter",
        "normalized storage paths to {0}".format(input_data.platform_rules.storage_prefix),
    ]

    skill_path = output_dir / SKILL_FILENAME
    provenance_path = output_dir / PROVENANCE_FILENAME
    limitations_path = output_dir / LIMITATIONS_FILENAME
    readme_path = output_dir / README_FILENAME
    manifest_path = output_dir / MANIFEST_FILENAME

    _write_text(skill_path, _skill_markdown(input_data, skill_name, allowed_tools))
    _write_text(provenance_path, _provenance_markdown(input_data.synthesis_report.selected_knowledge))
    _write_text(
        limitations_path,
        _limitations_markdown(
            input_data.synthesis_report.excluded_knowledge,
            input_data.synthesis_report.conflicts,
        ),
    )
    output_files = [
        SKILL_FILENAME,
        PROVENANCE_FILENAME,
        LIMITATIONS_FILENAME,
        README_FILENAME,
        MANIFEST_FILENAME,
    ]
    _write_text(readme_path, _readme_markdown(skill_name, output_files, transformations))

    selected_ids = [decision.decision_id for decision in input_data.synthesis_report.selected_knowledge]
    omitted_ids = [decision.decision_id for decision in input_data.synthesis_report.excluded_knowledge]
    manifest = SkillBuildManifest(
        skill_name=skill_name,
        selected_decision_ids=selected_ids,
        omitted_decision_ids=omitted_ids,
        platform_transformations=transformations,
        output_files=output_files,
    )
    _write_json(manifest_path, _safe_dump(manifest))

    output = SkillCompilerOutput(
        build_manifest=manifest,
        skill_md_path=str(skill_path),
        provenance_md_path=str(provenance_path),
        limitations_md_path=str(limitations_path),
        readme_md_path=str(readme_path),
    )
    return ModuleResultEnvelope(
        module_name=MODULE_NAME,
        status="ok",
        data=output,
        metrics=RunMetrics(
            wall_time_ms=max(1, int((time.time() - started_at) * 1000)),
            llm_calls=0,
            prompt_tokens=0,
            completion_tokens=0,
            estimated_cost_usd=0.0,
            retries=0,
        ),
    )
