"""Section-split compiler and quality scoring for Doramagic v12.1.1."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from doramagic_contracts.skill import CompileBundleContract, SkillCompilerInput
from doramagic_shared_utils.llm_adapter import LLMMessage

SECTION_SPECS = [
    ("role", "## Role"),
    ("knowledge", "## Domain Knowledge"),
    ("workflow", "## Recommended Workflow"),
    ("anti_patterns", "## Anti-Patterns & Safety"),
    ("when_not_to_use", "## When Not To Use"),
]
REQUIRED_HEADINGS = [heading for _, heading in SECTION_SPECS]
WHY_RE = re.compile(r"\b(because|why|trade[- ]?off|prefer|avoid|constraint|unless|except)\b", re.I)
GENERIC_RE = re.compile(
    r"\b(best practice|it depends|be flexible|optimize|robust|scalable)\b", re.I
)


def compile_ready(report: dict[str, Any] | Any) -> bool:
    data = report.model_dump() if hasattr(report, "model_dump") else dict(report)
    selected = data.get("selected_knowledge", [])
    briefs = data.get("compile_brief_by_section", {})
    return len(selected) >= 2 and bool(briefs)


async def build_compile_bundle(
    input_data: SkillCompilerInput,
    adapter: object,
    output_dir: Path,
) -> CompileBundleContract:
    output_dir.mkdir(parents=True, exist_ok=True)
    sections_dir = output_dir / "sections"
    sections_dir.mkdir(parents=True, exist_ok=True)

    shared_packet = _build_shared_packet(input_data)
    section_drafts = dict(input_data.existing_sections or {})
    targets = input_data.target_sections or [key for key, _ in SECTION_SPECS]
    for key, heading in SECTION_SPECS:
        if key not in targets and key in section_drafts:
            continue
        section_drafts[key] = await _compile_one_section(
            key=key,
            heading=heading,
            shared_packet=shared_packet,
            input_data=input_data,
            adapter=adapter,
        )
        (sections_dir / f"{key}.md").write_text(section_drafts[key], encoding="utf-8")

    full_draft = _assemble_skill(section_drafts, input_data)
    artifact_paths = {
        "SKILL.md": str(output_dir / "SKILL.md"),
        "PROVENANCE.md": str(output_dir / "PROVENANCE.md"),
        "LIMITATIONS.md": str(output_dir / "LIMITATIONS.md"),
        "README.md": str(output_dir / "README.md"),
        "compile_bundle.json": str(output_dir / "compile_bundle.json"),
    }
    (output_dir / "SKILL.md").write_text(full_draft, encoding="utf-8")
    (output_dir / "PROVENANCE.md").write_text(_build_provenance(input_data), encoding="utf-8")
    (output_dir / "LIMITATIONS.md").write_text(_build_limitations(input_data), encoding="utf-8")
    (output_dir / "README.md").write_text(_build_readme(input_data), encoding="utf-8")

    bundle = CompileBundleContract(
        section_drafts=section_drafts,
        full_draft=full_draft,
        provenance_map=_build_provenance_map(input_data),
        coverage_holes=_coverage_holes(section_drafts),
        predicted_weak_spots=_predicted_weak_spots(section_drafts),
        artifact_paths=artifact_paths,
    )
    (output_dir / "compile_bundle.json").write_text(
        json.dumps(bundle.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return bundle


def score_skill_quality(skill_md: str) -> dict[str, Any]:
    lines = skill_md.strip().splitlines()
    sections = {}
    h2_lines = [(i, line[3:].strip()) for i, line in enumerate(lines) if line.startswith("## ")]
    for index, (line_no, heading) in enumerate(h2_lines):
        end = h2_lines[index + 1][0] if index + 1 < len(h2_lines) else len(lines)
        sections[heading] = "\n".join(lines[line_no + 1 : end])

    blockers = []
    present = sum(
        1
        for heading in REQUIRED_HEADINGS
        if any(heading.replace("## ", "").lower() == actual.lower() for actual in sections)
    )
    coverage = min(100.0, (present / len(REQUIRED_HEADINGS)) * 100.0)
    if not skill_md.strip().startswith("---"):
        coverage -= 12
        blockers.append("missing_yaml_frontmatter")

    knowledge_text = next(
        (body for heading, body in sections.items() if "knowledge" in heading.lower()), ""
    )
    evidence_hits = len(
        re.findall(r"github\.com|source:|from:|evidence|repo", knowledge_text, re.I)
    )
    evidence = min(100.0, evidence_hits * 18.0)

    combined = " ".join(sections.values())
    specific = len(
        re.findall(r"\b(prefer|avoid|unless|except|failure|trap|constraint)\b", combined, re.I)
    )
    generic = len(GENERIC_RE.findall(combined))
    dsd = max(0.0, min(100.0, specific * 10.0 - generic * 5.0))

    sentences = [
        sentence.strip() for sentence in re.split(r"[.!?\n]+", skill_md) if sentence.strip()
    ]
    why_hits = sum(1 for sentence in sentences if WHY_RE.search(sentence))
    why_density = min(100.0, (why_hits / max(1, len(sentences))) * 220.0)

    tokens = re.findall(r"[A-Za-z0-9_\-\u4e00-\u9fff]+", skill_md)
    unique_ratio = len(set(tokens)) / max(1, len(tokens))
    substance = min(100.0, len(tokens) / 10.0) + min(20.0, unique_ratio * 35.0)
    if len(tokens) < 180:
        substance -= 20
    substance = max(0.0, min(100.0, substance))

    dimension_scores = {
        "Coverage": round(max(0.0, coverage), 1),
        "Evidence Quality": round(evidence, 1),
        "DSD Health": round(dsd, 1),
        "WHY Density": round(why_density, 1),
        "Substance": round(substance, 1),
    }
    overall = round(
        dimension_scores["Coverage"] * 0.30
        + dimension_scores["Evidence Quality"] * 0.25
        + dimension_scores["DSD Health"] * 0.20
        + dimension_scores["WHY Density"] * 0.15
        + dimension_scores["Substance"] * 0.10,
        1,
    )
    weakest_dimension = min(dimension_scores, key=dimension_scores.get)
    weakest_section = map_dimension_to_sections(weakest_dimension, sections)[0]
    if present < 3:
        blockers.append("fewer_than_3_required_sections")

    return {
        "overall_score": overall,
        "dimension_scores": dimension_scores,
        "weakest_dimension": weakest_dimension,
        "weakest_section": weakest_section,
        "repairable": bool(weakest_section),
        "repair_plan": map_dimension_to_sections(weakest_dimension, sections),
        "blockers": blockers,
    }


def map_dimension_to_sections(dimension: str, sections: dict[str, str]) -> list[str]:
    mapping = {
        "Coverage": ["knowledge", "workflow"],
        "Evidence Quality": ["knowledge"],
        "DSD Health": ["role", "workflow"],
        "WHY Density": ["knowledge", "anti_patterns"],
        "Substance": ["knowledge"],
    }
    targets = mapping.get(dimension, ["knowledge"])
    existing_keys = {_normalize_key(key) for key in sections}
    return [target for target in targets if target in existing_keys] or targets[:1]


def _normalize_key(heading: str) -> str:
    text = heading.lower().replace("&", "").replace("-", "_")
    if "role" in text:
        return "role"
    if "knowledge" in text:
        return "knowledge"
    if "workflow" in text:
        return "workflow"
    if "anti" in text or "safety" in text:
        return "anti_patterns"
    return "when_not_to_use"


async def _compile_one_section(
    *,
    key: str,
    heading: str,
    shared_packet: str,
    input_data: SkillCompilerInput,
    adapter: object,
) -> str:
    if adapter is not None and hasattr(adapter, "generate"):
        try:
            prompt = (
                f"Write only the markdown for section `{heading}`.\n"
                f"Use the following synthesis packet.\n\n{shared_packet}"
            )
            response = await adapter.generate(
                getattr(adapter, "_default_model", "default"),
                [LLMMessage(role="user", content=prompt)],
                max_tokens=900,
            )
            content = response.content.strip()
            if content:
                if not content.startswith(heading):
                    content = f"{heading}\n{content}"
                return content
        except Exception:
            pass
    return _section_fallback(key, heading, input_data)


def _section_fallback(key: str, heading: str, input_data: SkillCompilerInput) -> str:
    brief = input_data.synthesis_report.compile_brief_by_section.get(key, [])
    intent = input_data.need_profile.intent
    selected = [
        decision
        for decision in input_data.synthesis_report.selected_knowledge
        if "[TRAP]" not in _decision_field(decision, "statement")
    ]
    traps = [
        decision
        for decision in input_data.synthesis_report.selected_knowledge
        if "[TRAP]" in _decision_field(decision, "statement")
    ]
    if key == "role":
        return (
            f"{heading}\n"
            f"You are a domain advisor for {intent}. Prefer repo-backed rationale because Doramagic only ships "
            "advice that survived code extraction, synthesis, and validation."
        )
    if key == "knowledge":
        bullets = []
        for decision in selected[:5]:
            statement = _decision_field(decision, "statement")
            rationale = (
                _decision_field(decision, "rationale")
                or "Prefer the implementation path that already absorbed production trade-offs."
            )
            source = next((ref for ref in _decision_field(decision, "source_refs", []) if ref), "")
            line = f"- {statement} because {rationale}."
            if source:
                line += f" Source: {source}"
            bullets.append(line)
        if not bullets:
            fallback = brief or input_data.synthesis_report.common_why[:5]
            bullets = [
                f"- {item} because it is the strongest evidence-backed rationale available."
                for item in fallback[:6]
            ]
        body = "\n".join(bullets)
        return f"{heading}\n{body}"
    if key == "workflow":
        steps = brief or [
            "Read the user goal and constraints before proposing any pattern.",
            "Prefer the repo-backed default because it already absorbed a real trade-off.",
            "Write a minimal plan that names the chosen pattern, the why, and the rejected trap.",
            "Use only exec, read, and write, and keep any storage path under ~/clawd/.",
            "If evidence is thin, say so explicitly instead of inventing a best practice.",
        ]
        body = "\n".join(f"{index}. {step}" for index, step in enumerate(steps[:5], start=1))
        return f"{heading}\n{body}"
    if key == "anti_patterns":
        trap_lines = []
        for decision in traps[:4]:
            statement = _decision_field(decision, "statement").replace("[TRAP] ", "")
            source = next((ref for ref in _decision_field(decision, "source_refs", []) if ref), "")
            line = f"- Avoid {statement} because it showed up as a repeated risk in extraction."
            if source:
                line += f" Source: {source}"
            trap_lines.append(line)
        if not trap_lines:
            fallback = brief or [item for item in input_data.synthesis_report.divergences[:4]]
            trap_lines = [
                f"- Avoid {item} because it weakens evidence quality or hides trade-offs."
                for item in fallback[:5]
            ]
        body = (
            "\n".join(trap_lines) or "- Do not replace extracted WHY knowledge with generic advice."
        )
        return f"{heading}\n{body}"
    return (
        f"{heading}\n"
        "- Do not use this skill when the repo evidence is too thin to justify a recommendation.\n"
        "- Do not use this skill when the user needs code execution beyond exec/read/write or storage outside ~/clawd/.\n"
        "- Do not use this skill when legal, medical, or other high-stakes advice would require fresher sources."
    )


def _build_shared_packet(input_data: SkillCompilerInput) -> str:
    lines = [
        f"Intent: {input_data.need_profile.intent}",
        f"Domain: {input_data.need_profile.domain}",
        "Selected knowledge:",
    ]
    for decision in input_data.synthesis_report.selected_knowledge[:10]:
        lines.append(f"- {decision.statement} (from {', '.join(decision.source_refs[:2])})")
    if input_data.accumulated_knowledge:
        lines.append("Accumulated local knowledge:")
        for item in input_data.accumulated_knowledge[:5]:
            lines.append(f"- {item.get('statement', '')}")
    return "\n".join(lines)[:12000]


def _assemble_skill(section_drafts: dict[str, str], input_data: SkillCompilerInput) -> str:
    skill_name = _slugify(input_data.need_profile.intent_en or input_data.need_profile.intent)
    description = _frontmatter_safe_text(
        input_data.need_profile.intent_en or input_data.need_profile.intent
    )
    sections = [section_drafts[key] for key, _ in SECTION_SPECS if key in section_drafts]
    return "\n\n".join(
        [
            "---",
            f"name: {skill_name}",
            f"description: {description}",
            "allowed-tools: exec, read, write",
            "version: 12.1.1",
            "---",
            f"# {input_data.need_profile.intent}",
            *sections,
            "---\n*Generated by Doramagic v12.1.1 — 不教用户做事，给他工具。*",
        ]
    )


def _build_provenance(input_data: SkillCompilerInput) -> str:
    lines = ["# PROVENANCE", ""]
    for repo_name, refs in _build_provenance_map(input_data).items():
        lines.append(f"## {repo_name}")
        for ref in refs:
            lines.append(f"- Source Refs: {ref}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def _build_limitations(input_data: SkillCompilerInput) -> str:
    unknowns = input_data.synthesis_report.unknowns or [
        "This draft is limited by the extracted evidence that survived the pipeline."
    ]
    return "# LIMITATIONS\n\n" + "\n".join(f"- {item}" for item in unknowns[:6]) + "\n"


def _build_readme(input_data: SkillCompilerInput) -> str:
    return (
        "# README\n\n"
        f"- Intent: {input_data.need_profile.intent}\n"
        f"- Domain: {input_data.need_profile.domain}\n"
        "- Runtime entry: `python3 skills/doramagic/scripts/doramagic_main.py --input ...`\n"
        "- Status command: `/dora-status` or `--status`\n"
        "- Install by copying this skill bundle into your OpenClaw or Claude Code skills directory.\n"
    )


def _build_provenance_map(input_data: SkillCompilerInput) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {}
    for decision in input_data.synthesis_report.selected_knowledge:
        refs = [ref for ref in decision.source_refs if ref]
        if not refs:
            continue
        mapping.setdefault(decision.decision_id, [])
        for ref in refs:
            if ref not in mapping[decision.decision_id]:
                mapping[decision.decision_id].append(ref)
    return mapping


def _coverage_holes(section_drafts: dict[str, str]) -> list[str]:
    holes = []
    for key, heading in SECTION_SPECS:
        if key not in section_drafts or heading not in section_drafts[key]:
            holes.append(key)
    return holes


def _predicted_weak_spots(section_drafts: dict[str, str]) -> list[str]:
    weak = []
    for key, text in section_drafts.items():
        if len(text.split()) < 45:
            weak.append(key)
    return weak


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "doramagic-skill"


def _frontmatter_safe_text(text: str) -> str:
    safe = re.sub(r"https?://\S+", "repo", text or "")
    safe = safe.replace(":", " - ").replace("\n", " ")
    safe = re.sub(r"\s+", " ", safe).strip()
    return safe[:120] or "Doramagic generated advisor"


def _decision_field(decision: Any, field: str, default: Any = "") -> Any:
    if isinstance(decision, dict):
        return decision.get(field, default)
    return getattr(decision, field, default)
