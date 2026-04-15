"""Constraint extraction phases v3 — SOP v2.3 with document extraction + evaluator.

Extends v2 with three new phases:
- con_extract_doc: Document constraint extraction (SOP Step 2.1-s)
- con_extract_rationalization: Rationalization guard extraction (SOP Step 2.6)
- con_evaluate: Independent Sprint-Contract constraint evaluation

Phase flow:
  [v2 phases] + con_extract_doc + con_extract_rationalization (in parallel extract group)
  + con_evaluate (after con_merge, before con_constraint_synthesis)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from ..sop.constraint_phases_v2 import build_constraint_phases_v2
from ..sop.executor import Phase
from ..state.schema import AgentState
from . import constraint_prompts_v2 as prompts_v2

if TYPE_CHECKING:
    from ..core.agent_loop import ExtractionAgent

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# New handler: Document constraint extraction (SOP Step 2.1-s)
# ---------------------------------------------------------------------------


def _build_ct_extract_doc_message(state: AgentState, repo_path: Path) -> str:
    """Initial message builder for document constraint extraction.

    Returns immediate-write instruction if no document knowledge sources
    detected (same graceful-skip pattern as worker_structural).
    """
    knowledge_sources = state.extra.get("knowledge_sources", [])
    if "document" not in knowledge_sources:
        return (
            "No document knowledge sources detected (no SKILL.md/CLAUDE.md). "
            "Write an empty JSON to ct_doc_constraints.json using write_artifact: "
            '{"constraints": []}'
        )

    # Build document source listing from structural index
    doc_sources = state.extra.get("structural_index", {}).get("document_sources", {})
    skill_files = doc_sources.get("skill_files", [])
    claude_md = doc_sources.get("claude_md", [])
    agent_files = doc_sources.get("agent_files", [])

    lines = ["## Document Knowledge Sources\n"]
    for sf in skill_files:
        path = sf.get("path", "")
        name = sf.get("frontmatter", {}).get("name", "unknown")
        lines.append(f"- **SKILL.md**: `{path}` (name: {name})")
        headings = sf.get("headings", [])
        for h in headings[:8]:
            lines.append(f"  - §{h.get('title', '')} (level {h.get('level', 0)})")
    for cm in claude_md:
        lines.append(f"- **CLAUDE.md**: `{cm.get('path', '')}`")
    for af in agent_files:
        lines.append(f"- **Agent file**: `{af.get('path', '')}`")

    lines.append("\n## Instructions")
    lines.append("1. Read each document source listed above using read_file.")
    lines.append(
        "2. Extract constraints following the 5 document feature patterns in the system prompt."
    )
    lines.append("3. Use evidence format: `filepath:§section_title`")
    lines.append("4. Write the result as JSON to ct_doc_constraints.json using write_artifact.")
    lines.append('   Format: {"constraints": [...]}')

    bp_id = state.extra.get("blueprint_id", state.blueprint_id)
    lines.insert(0, f"Blueprint: {bp_id}\nRepository: {repo_path}\n")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# New handler: Rationalization guard extraction (SOP Step 2.6)
# ---------------------------------------------------------------------------


def _build_ct_extract_rationalization_message(state: AgentState, repo_path: Path) -> str:
    """Initial message builder for rationalization guard extraction.

    Checks trigger conditions from SOP Step 2.6:
    - blueprint extraction_methods contains document knowledge source
    - project contains SKILL.md / CLAUDE.md / AGENTS.md
    - project contains CONTRIBUTING.md with behavioral prohibitions
    - code comments with "DO NOT TOUCH/REMOVE/CHANGE" pattern
    """
    knowledge_sources = state.extra.get("knowledge_sources", [])
    doc_sources = state.extra.get("structural_index", {}).get("document_sources", {})
    skill_files = doc_sources.get("skill_files", [])
    claude_md = doc_sources.get("claude_md", [])

    # Check trigger conditions
    has_doc_source = "document" in knowledge_sources
    has_skill = len(skill_files) > 0
    has_claude = len(claude_md) > 0

    if not (has_doc_source or has_skill or has_claude):
        return (
            "No rationalization guard sources detected "
            "(no SKILL.md/CLAUDE.md/AGENTS.md with anti-rationalization content). "
            "Write an empty JSON to ct_rationalization_constraints.json using write_artifact: "
            '{"constraints": []}'
        )

    lines = [f"Blueprint: {state.blueprint_id}\nRepository: {repo_path}\n"]
    lines.append("## Scan Sources\n")

    if skill_files:
        lines.append("### SKILL.md files")
        for sf in skill_files:
            lines.append(f"- `{sf.get('path', '')}`")
            for h in sf.get("headings", []):
                title = h.get("title", "")
                if any(
                    kw in title.lower()
                    for kw in (
                        "rationalization",
                        "red flag",
                        "mistake",
                        "anti-pattern",
                        "bulletproof",
                        "do not",
                        "never",
                    )
                ):
                    lines.append(f"  - **RELEVANT**: §{title}")

    if claude_md:
        lines.append("\n### CLAUDE.md files")
        for cm in claude_md:
            lines.append(f"- `{cm.get('path', '')}`")

    lines.append("\n### Additional sources to scan")
    lines.append("- Use grep_codebase to find CONTRIBUTING.md")
    lines.append("- Use grep_codebase for 'DO NOT TOUCH|DO NOT REMOVE|DO NOT CHANGE'")

    lines.append("\n## Instructions")
    lines.append("1. Read each document source listed above.")
    lines.append("2. Scan for rationalization patterns (see system prompt).")
    lines.append("3. If NO rationalization content found, write empty JSON immediately.")
    lines.append("4. Otherwise, extract guard constraints with guard_pattern field.")
    lines.append("5. Write result to ct_rationalization_constraints.json using write_artifact.")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# New handler: Independent evaluator (Sprint Contract)
# ---------------------------------------------------------------------------


def _build_ct_evaluate_message(state: AgentState, repo_path: Path) -> str:
    """Build initial message for the independent evaluator."""
    bp_id = state.extra.get("blueprint_id", state.blueprint_id)
    return (
        f"Blueprint: {bp_id}\n"
        f"Repository: {repo_path}\n\n"
        "Read the merged constraints from get_artifact('constraints_merged.json').\n"
        "Independently verify a sample of up to 20 constraints against the source code.\n"
        "Check all 4 Sprint Contracts (evidence validity, kind correctness, "
        "severity calibration, triad completeness).\n"
        "Write your evaluation report to ct_evaluation_report.json using write_artifact."
    )


# ---------------------------------------------------------------------------
# Phase factory
# ---------------------------------------------------------------------------


def build_constraint_phases_v3(
    blueprint_id: str,
    blueprint_path: Path,
    agent: ExtractionAgent | None = None,
    *,
    fallback_agent: ExtractionAgent | None = None,
    strict_quality_gate: bool = True,
) -> list[Phase]:
    """Build constraint extraction phases for the v3 pipeline (SOP v2.3).

    Extends v2 with:
    - con_extract_doc: Document constraint extraction (Step 2.1-s)
    - con_extract_rationalization: Rationalization guard extraction (Step 2.6)
    - con_evaluate: Independent Sprint-Contract constraint evaluation

    Args:
        blueprint_id: Blueprint identifier, e.g. "finance-bp-009".
        blueprint_path: Absolute path to the blueprint YAML file.
        agent: ExtractionAgent for Instructor calls and agentic phases.
        fallback_agent: Optional fallback ExtractionAgent.
        strict_quality_gate: If True, hard gate failures stop the pipeline.

    Returns:
        Ordered list of Phase objects ready for SOPExecutor.
    """
    # Get base v2 phases
    v2_phases = build_constraint_phases_v2(
        blueprint_id,
        blueprint_path,
        agent,
        fallback_agent=fallback_agent,
    )

    # Find insertion points
    # Insert new extract phases before con_merge (last extract group member)
    merge_idx = next(i for i, p in enumerate(v2_phases) if p.name == "con_merge")
    synthesis_idx = next(i for i, p in enumerate(v2_phases) if p.name == "con_constraint_synthesis")

    # Build new phases
    new_extract_phases: list[Phase] = []

    # --- con_extract_doc (Step 2.1-s) ---
    new_extract_phases.append(
        Phase(
            name="con_extract_doc",
            description="Step 2.1-s: Extract constraints from document knowledge sources",
            system_prompt=prompts_v2.CON_DOC_EXTRACT_SYSTEM,
            initial_message_builder=_build_ct_extract_doc_message,
            allowed_tools=[
                "read_file",
                "list_dir",
                "grep_codebase",
                "write_artifact",
            ],
            max_iterations=40,
            required_artifacts=["ct_doc_constraints.json"],
            depends_on=["con_build_manifest"],
            blocking=False,
            parallel_group="extract",
        )
    )

    # --- con_extract_rationalization (Step 2.6) ---
    new_extract_phases.append(
        Phase(
            name="con_extract_rationalization",
            description="Step 2.6: Extract rationalization guard constraints",
            system_prompt=prompts_v2.CON_RATIONALIZATION_SYSTEM,
            initial_message_builder=_build_ct_extract_rationalization_message,
            allowed_tools=[
                "read_file",
                "grep_codebase",
                "write_artifact",
            ],
            max_iterations=30,
            required_artifacts=["ct_rationalization_constraints.json"],
            depends_on=["con_build_manifest"],
            blocking=False,
            parallel_group="extract",
        )
    )

    # --- con_evaluate (independent evaluator, after merge) ---
    evaluate_phase = Phase(
        name="con_evaluate",
        description="Independent Sprint-Contract constraint evaluation",
        system_prompt=prompts_v2.CON_EVALUATOR_SYSTEM,
        initial_message_builder=_build_ct_evaluate_message,
        allowed_tools=[
            "read_file",
            "grep_codebase",
            "get_artifact",
            "write_artifact",
        ],
        max_iterations=40,
        required_artifacts=["ct_evaluation_report.json"],
        depends_on=["con_merge"],
        blocking=True,
    )

    # Assemble final phase list:
    # v2_phases[:merge_idx] = pre-processing + all v2 extract phases
    # + new extract phases (doc + rationalization)
    # + v2_phases[merge_idx:synthesis_idx] = con_merge + any phases between merge and synthesis
    # + evaluate_phase
    # + v2_phases[synthesis_idx:] = con_constraint_synthesis onward
    result = (
        v2_phases[:merge_idx]
        + new_extract_phases
        + v2_phases[merge_idx:synthesis_idx]  # con_merge + any intermediate phases
        + [evaluate_phase]  # independent evaluator
        + v2_phases[synthesis_idx:]  # con_constraint_synthesis onward
    )

    # Update con_constraint_synthesis to depend on con_evaluate
    for phase in result:
        if phase.name == "con_constraint_synthesis" and "con_evaluate" not in phase.depends_on:
            phase.depends_on.append("con_evaluate")

    logger.info(
        "build_constraint_phases_v3: %d phases for %s (v2 base: %d, +3 new: "
        "doc_extract, rationalization, evaluate)",
        len(result),
        blueprint_id,
        len(v2_phases),
    )

    return result
