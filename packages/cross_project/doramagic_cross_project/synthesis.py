"""cross-project.synthesis — 综合多项目提取包、比较信号和社区知识，产出"可编译"知识选择结果。"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "packages" / "contracts"))

from doramagic_contracts.base import Priority  # noqa: E402
from doramagic_contracts.cross_project import (  # noqa: E402
    CommunityKnowledge,
    CompareOutput,
    CompareSignal,
    ExtractedProjectSummary,
    SynthesisConflict,
    SynthesisDecision,
    SynthesisInput,
    SynthesisReportData,
)
from doramagic_contracts.envelope import (  # noqa: E402
    ErrorCodes,
    ModuleResultEnvelope,
    RunMetrics,
    WarningItem,
)

MODULE_NAME = "cross-project.synthesis"
SYNTHESIS_JSON_FILENAME = "synthesis_report.json"
SYNTHESIS_MD_FILENAME = "synthesis_report.md"

# Conflict category heuristics: keywords in statement → category
_CONFLICT_CATEGORY_HINTS: List[Tuple[List[str], str]] = [
    (["license", "mit", "apache", "gpl", "copyright", "bsd"], "license"),
    (["architecture", "storage", "database", "sqlite", "json", "markdown", "format", "backend"], "architecture"),
    (["dependency", "library", "package", "version", "require", "import"], "dependency"),
    (["scope", "feature", "micronutrient", "field", "track", "export", "goal"], "scope"),
    (["deploy", "operation", "cron", "schedule", "background", "service", "run"], "operational"),
]


# ---------------------------------------------------------------------------
# Stable ID helpers
# ---------------------------------------------------------------------------

def _stable_id(prefix: str, *parts: str) -> str:
    """SHA-1 based stable identifier; first 10 hex chars."""
    payload = "|".join(parts)
    digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:10].upper()
    return "{0}-{1}".format(prefix, digest)


def _decision_id(statement: str, decision: str) -> str:
    return _stable_id("DEC", statement, decision)


def _conflict_id(category: str, title: str) -> str:
    return _stable_id("CONF", category, title)


# ---------------------------------------------------------------------------
# Category inference
# ---------------------------------------------------------------------------

def _infer_conflict_category(statement: str) -> str:
    """Infer the most relevant conflict category from the statement text."""
    lower = statement.lower()
    for keywords, category in _CONFLICT_CATEGORY_HINTS:
        for kw in keywords:
            if kw in lower:
                return category
    return "semantic"  # safe default


# ---------------------------------------------------------------------------
# Demand-fit scoring
# ---------------------------------------------------------------------------

def _score_demand_fit(statement: str, need_profile_keywords: List[str]) -> Priority:
    """Estimate demand fit based on keyword overlap with need profile."""
    lower = statement.lower()
    matched = sum(1 for kw in need_profile_keywords if kw.lower() in lower)
    if matched >= 2:
        return "high"
    if matched == 1:
        return "medium"
    return "low"


# ---------------------------------------------------------------------------
# Conflict detection between DRIFTED / DIVERGENT / CONTESTED signals
# ---------------------------------------------------------------------------

def _extract_conflicts_from_signals(
    signals: List[CompareSignal],
    need_keywords: List[str],
) -> List[SynthesisConflict]:
    """Build SynthesisConflict entries from DRIFTED/DIVERGENT/CONTESTED signals."""
    conflict_signals = [s for s in signals if s.signal in ("DRIFTED", "DIVERGENT", "CONTESTED")]
    conflicts: List[SynthesisConflict] = []

    for sig in conflict_signals:
        category = _infer_conflict_category(sig.normalized_statement)
        title = "Conflicting views on: {0}".format(sig.normalized_statement[:80])
        positions = [
            "Project {0}: {1}".format(pid, sig.normalized_statement)
            for pid in sig.subject_project_ids
        ]
        if len(positions) < 2:
            # Add a generic second position to make it a real conflict
            positions.append("Other projects: approach differs on this topic")

        recommended_resolution = _recommend_resolution(category, sig.normalized_statement)
        source_refs = [sig.signal_id] + [ref.path for ref in sig.evidence_refs[:2]]

        conflicts.append(
            SynthesisConflict(
                conflict_id=_conflict_id(category, title),
                category=category,
                title=title,
                positions=positions,
                recommended_resolution=recommended_resolution,
                source_refs=source_refs,
            )
        )

    return conflicts


def _recommend_resolution(category: str, statement: str) -> str:
    """Return a human-readable recommended resolution per category."""
    resolutions: Dict[str, str] = {
        "license": (
            "Resolve license incompatibility before including this knowledge. "
            "Prefer MIT/Apache-2.0 dual-track; GPL-licensed knowledge must be excluded unless the skill is also GPL."
        ),
        "architecture": (
            "Document both approaches as an 'option' decision; let the skill compiler pick based on platform constraints. "
            "Prefer the approach most compatible with OpenClaw storage conventions."
        ),
        "dependency": (
            "Pin to the least-restrictive compatible version. "
            "If versions conflict, exclude the feature requiring the higher version until the platform supports it."
        ),
        "scope": (
            "Treat as an 'option' decision so the end user can enable/disable. "
            "Default to the minimal scope that satisfies the stated need."
        ),
        "operational": (
            "Favour the pattern already supported by the OpenClaw platform. "
            "Mark unsupported operational patterns as 'excluded' with a clear rationale."
        ),
        "semantic": (
            "Adopt the wording from the highest-support project; document alternatives as notes. "
            "If confidence is low, mark as 'option'."
        ),
    }
    return resolutions.get(category, "Review manually and decide based on context.")


# ---------------------------------------------------------------------------
# Consensus extraction (ALIGNED signals)
# ---------------------------------------------------------------------------

def _build_consensus(
    aligned_signals: List[CompareSignal],
    need_keywords: List[str],
) -> List[SynthesisDecision]:
    """Turn ALIGNED signals into consensus include/exclude decisions."""
    decisions: List[SynthesisDecision] = []

    for sig in aligned_signals:
        demand_fit = _score_demand_fit(sig.normalized_statement, need_keywords)
        # High-support aligned signals → include; very low fit → option
        decision: str = "include" if demand_fit in ("high", "medium") else "option"
        rationale = (
            "Aligned across {0} independent projects (match_score={1:.2f}). "
            "This represents cross-project consensus and is a strong candidate for compilation.".format(
                sig.support_count, sig.match_score
            )
        )
        source_refs = [sig.signal_id] + [ref.path for ref in sig.evidence_refs[:3]]
        decisions.append(
            SynthesisDecision(
                decision_id=_decision_id(sig.normalized_statement, decision),
                statement=sig.normalized_statement,
                decision=decision,  # type: ignore[arg-type]
                rationale=rationale,
                source_refs=source_refs,
                demand_fit=demand_fit,
            )
        )

    return decisions


# ---------------------------------------------------------------------------
# Unique / original knowledge extraction
# ---------------------------------------------------------------------------

def _build_unique_knowledge(
    original_signals: List[CompareSignal],
    project_summaries: List[ExtractedProjectSummary],
    community: CommunityKnowledge,
    need_keywords: List[str],
) -> List[SynthesisDecision]:
    """Extract unique knowledge from ORIGINAL signals + project capabilities."""
    decisions: List[SynthesisDecision] = []

    # From ORIGINAL compare signals
    for sig in original_signals:
        demand_fit = _score_demand_fit(sig.normalized_statement, need_keywords)
        decision = "include" if demand_fit in ("high", "medium") else "option"
        rationale = (
            "Unique to project(s) {0} — not found in other surveyed repositories. "
            "Included as high-leverage original insight where demand fit is {1}.".format(
                ", ".join(sig.subject_project_ids), demand_fit
            )
        )
        source_refs = [sig.signal_id] + [ref.path for ref in sig.evidence_refs[:2]]
        decisions.append(
            SynthesisDecision(
                decision_id=_decision_id(sig.normalized_statement, decision),
                statement=sig.normalized_statement,
                decision=decision,  # type: ignore[arg-type]
                rationale=rationale,
                source_refs=source_refs,
                demand_fit=demand_fit,
            )
        )

    # From project_summaries top_capabilities not already captured
    captured_statements = {d.statement for d in decisions}
    for summary in project_summaries:
        for cap in summary.top_capabilities:
            if cap in captured_statements:
                continue
            demand_fit = _score_demand_fit(cap, need_keywords)
            decision = "include" if demand_fit in ("high", "medium") else "option"
            rationale = (
                "Unique capability surfaced from {0} extraction. "
                "Not observed in other projects — represents original design thinking.".format(
                    summary.project_id
                )
            )
            ref_paths = [ref.path for ref in summary.evidence_refs[:2]] or [summary.project_id]
            decisions.append(
                SynthesisDecision(
                    decision_id=_decision_id(cap, decision),
                    statement=cap,
                    decision=decision,  # type: ignore[arg-type]
                    rationale=rationale,
                    source_refs=ref_paths,
                    demand_fit=demand_fit,
                )
            )
            captured_statements.add(cap)

    # From community reusable_knowledge items (all community item types)
    all_community_items = community.skills + community.tutorials + community.use_cases
    for item in all_community_items:
        for knowledge in item.reusable_knowledge:
            if knowledge in captured_statements:
                continue
            demand_fit = _score_demand_fit(knowledge, need_keywords)
            decision = "include" if demand_fit in ("high", "medium") else "option"
            rationale = (
                "Community-sourced knowledge from '{0}' ({1}). "
                "Reusable pattern validated in practice by the community.".format(item.name, item.kind)
            )
            decisions.append(
                SynthesisDecision(
                    decision_id=_decision_id(knowledge, decision),
                    statement=knowledge,
                    decision=decision,  # type: ignore[arg-type]
                    rationale=rationale,
                    source_refs=[item.item_id, item.source],
                    demand_fit=demand_fit,
                )
            )
            captured_statements.add(knowledge)

    return decisions


# ---------------------------------------------------------------------------
# Excluded knowledge (constraints + failures worth flagging)
# ---------------------------------------------------------------------------

def _build_excluded_knowledge(
    project_summaries: List[ExtractedProjectSummary],
    need_keywords: List[str],
) -> List[SynthesisDecision]:
    """Build excluded decisions from constraints and failures."""
    decisions: List[SynthesisDecision] = []
    captured: set = set()

    for summary in project_summaries:
        for constraint in summary.top_constraints:
            if constraint in captured:
                continue
            demand_fit = _score_demand_fit(constraint, need_keywords)
            # Constraints are excluded from the skill because they represent limitations, not features
            rationale = (
                "Constraint from {0}: '{1}'. "
                "Excluded from active selection — documented as a known limitation that "
                "the skill must account for but does not implement directly.".format(
                    summary.project_id, constraint
                )
            )
            ref_paths = [ref.path for ref in summary.evidence_refs[:2]] or [summary.project_id]
            decisions.append(
                SynthesisDecision(
                    decision_id=_decision_id(constraint, "exclude"),
                    statement=constraint,
                    decision="exclude",
                    rationale=rationale,
                    source_refs=ref_paths,
                    demand_fit=demand_fit,
                )
            )
            captured.add(constraint)

        for failure in summary.top_failures:
            if failure in captured:
                continue
            demand_fit = _score_demand_fit(failure, need_keywords)
            rationale = (
                "Known failure mode from {0}: '{1}'. "
                "Excluded from selection — this is a dark trap the skill design should avoid, "
                "not a pattern to include.".format(summary.project_id, failure)
            )
            ref_paths = [ref.path for ref in summary.evidence_refs[:2]] or [summary.project_id]
            decisions.append(
                SynthesisDecision(
                    decision_id=_decision_id(failure, "exclude"),
                    statement=failure,
                    decision="exclude",
                    rationale=rationale,
                    source_refs=ref_paths,
                    demand_fit=demand_fit,
                )
            )
            captured.add(failure)

    return decisions


# ---------------------------------------------------------------------------
# Selected knowledge assembly
# ---------------------------------------------------------------------------

def _assemble_selected(
    consensus: List[SynthesisDecision],
    unique_knowledge: List[SynthesisDecision],
) -> List[SynthesisDecision]:
    """Select the final knowledge to compile from consensus + unique include decisions."""
    selected: List[SynthesisDecision] = []
    seen_statements: set = set()

    for decision in consensus + unique_knowledge:
        if decision.decision == "include" and decision.statement not in seen_statements:
            # Build a SEL- prefixed stable ID that references the origin decision_id
            sel_id = _stable_id("SEL", decision.decision_id, decision.statement)
            selected.append(
                SynthesisDecision(
                    decision_id=sel_id,
                    statement=decision.statement,
                    decision="include",
                    rationale=decision.rationale,
                    source_refs=[decision.decision_id] + decision.source_refs,
                    demand_fit=decision.demand_fit,
                )
            )
            seen_statements.add(decision.statement)

    return selected


# ---------------------------------------------------------------------------
# Open questions
# ---------------------------------------------------------------------------

def _derive_open_questions(
    conflicts: List[SynthesisConflict],
    warnings: List[WarningItem],
    project_summaries: List[ExtractedProjectSummary],
) -> List[str]:
    """Generate open questions from unresolved conflicts and data gaps."""
    questions: List[str] = []

    for conflict in conflicts:
        if conflict.category == "license":
            questions.append(
                "LICENSE GATE: Conflict '{0}' must be resolved before compilation. "
                "Which license applies to the synthesized skill?".format(conflict.title)
            )
        elif conflict.category == "architecture":
            questions.append(
                "ARCHITECTURE CHOICE: {0} — should the skill prefer local file storage or "
                "in-message JSON state?".format(conflict.title)
            )
        else:
            questions.append(
                "OPEN: {0} (category={1}) — review positions and decide before compiling.".format(
                    conflict.title, conflict.category
                )
            )

    for w in warnings:
        questions.append("WARNING: {0}".format(w.message))

    if not project_summaries:
        questions.append("No project summaries provided — extraction phase may be incomplete.")

    return questions


# ---------------------------------------------------------------------------
# License conflict detection
# ---------------------------------------------------------------------------

def _has_unresolved_license_conflict(conflicts: List[SynthesisConflict]) -> bool:
    """Return True if any license conflict exists (always unresolved at synthesis stage)."""
    return any(c.category == "license" for c in conflicts)


def _detect_license_conflicts_from_summaries(
    project_summaries: List[ExtractedProjectSummary],
    signals: List[CompareSignal],
) -> List[SynthesisConflict]:
    """Check for license conflicts from project data."""
    conflicts: List[SynthesisConflict] = []

    # Look for license-related statements in signals
    license_signals = [
        s for s in signals
        if any(kw in s.normalized_statement for kw in ("license", "mit", "apache", "gpl", "bsd", "copyright"))
    ]

    if len(license_signals) >= 2:
        # Multiple license-related signals → potential conflict
        positions = []
        source_refs = []
        for sig in license_signals[:3]:
            positions.append("{0}: {1}".format(", ".join(sig.subject_project_ids), sig.normalized_statement))
            source_refs.append(sig.signal_id)

        title = "Incompatible license terms detected across projects"
        conflicts.append(
            SynthesisConflict(
                conflict_id=_conflict_id("license", title),
                category="license",
                title=title,
                positions=positions,
                recommended_resolution=_recommend_resolution("license", ""),
                source_refs=source_refs,
            )
        )

    return conflicts


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------

def _synthesis_output_dir(domain_id: str) -> Path:
    base = os.environ.get("DORAMAGIC_SYNTHESIS_OUTPUT_DIR")
    if base:
        root = Path(base).expanduser().resolve()
    else:
        root = Path(tempfile.gettempdir()) / "doramagic_synthesis"
    return root / domain_id


def _write_json(report: SynthesisReportData, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / SYNTHESIS_JSON_FILENAME
    target.write_text(
        json.dumps(report.model_dump(), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return target


def _decision_to_md(d: SynthesisDecision, index: int) -> str:
    badge = {"include": "✅ INCLUDE", "exclude": "❌ EXCLUDE", "option": "🔀 OPTION"}.get(d.decision, d.decision)
    lines = [
        "### {0}. [{1}] `{2}`".format(index + 1, badge, d.decision_id),
        "",
        "**Statement:** {0}".format(d.statement),
        "",
        "**Demand fit:** `{0}`".format(d.demand_fit),
        "",
        "**Rationale:** {0}".format(d.rationale),
        "",
        "**Sources:** {0}".format(", ".join(d.source_refs) if d.source_refs else "_none_"),
        "",
    ]
    return "\n".join(lines)


def _conflict_to_md(c: SynthesisConflict, index: int) -> str:
    lines = [
        "### {0}. [{1}] `{2}`".format(index + 1, c.category.upper(), c.conflict_id),
        "",
        "**Title:** {0}".format(c.title),
        "",
        "**Positions:**",
    ]
    for pos in c.positions:
        lines.append("- {0}".format(pos))
    lines += [
        "",
        "**Recommended resolution:** {0}".format(c.recommended_resolution),
        "",
        "**Sources:** {0}".format(", ".join(c.source_refs) if c.source_refs else "_none_"),
        "",
    ]
    return "\n".join(lines)


def _render_markdown(report: SynthesisReportData, domain_id: str) -> str:
    sections: List[str] = [
        "# Synthesis Report — `{0}`".format(domain_id),
        "",
        "> Auto-generated by `cross-project.synthesis`. "
        "JSON canonical: `{0}` | Human mirror: `{1}`".format(
            SYNTHESIS_JSON_FILENAME, SYNTHESIS_MD_FILENAME
        ),
        "",
        "---",
        "",
    ]

    # Consensus
    sections.append("## 1. Consensus Knowledge")
    sections.append("")
    if report.consensus:
        for i, d in enumerate(report.consensus):
            sections.append(_decision_to_md(d, i))
    else:
        sections.append("_No consensus knowledge identified._")
        sections.append("")

    # Conflicts
    sections.append("## 2. Conflicts")
    sections.append("")
    if report.conflicts:
        for i, c in enumerate(report.conflicts):
            sections.append(_conflict_to_md(c, i))
    else:
        sections.append("_No conflicts detected._")
        sections.append("")

    # Unique knowledge
    sections.append("## 3. Unique / Original Knowledge")
    sections.append("")
    if report.unique_knowledge:
        for i, d in enumerate(report.unique_knowledge):
            sections.append(_decision_to_md(d, i))
    else:
        sections.append("_No unique knowledge identified._")
        sections.append("")

    # Selected knowledge
    sections.append("## 4. Selected Knowledge (Compilation-Ready)")
    sections.append("")
    if report.selected_knowledge:
        for i, d in enumerate(report.selected_knowledge):
            sections.append(_decision_to_md(d, i))
    else:
        sections.append("_Nothing selected — check conflicts and consensus._")
        sections.append("")

    # Excluded knowledge
    sections.append("## 5. Excluded Knowledge")
    sections.append("")
    if report.excluded_knowledge:
        for i, d in enumerate(report.excluded_knowledge):
            sections.append(_decision_to_md(d, i))
    else:
        sections.append("_Nothing explicitly excluded._")
        sections.append("")

    # Open questions
    sections.append("## 6. Open Questions")
    sections.append("")
    if report.open_questions:
        for q in report.open_questions:
            sections.append("- {0}".format(q))
        sections.append("")
    else:
        sections.append("_No open questions._")
        sections.append("")

    return "\n".join(sections)


def _write_markdown(report: SynthesisReportData, domain_id: str, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / SYNTHESIS_MD_FILENAME
    target.write_text(_render_markdown(report, domain_id), encoding="utf-8")
    return target


# ---------------------------------------------------------------------------
# Blocked helpers
# ---------------------------------------------------------------------------

def _blocked(error_code: str, elapsed_ms: int = 0) -> ModuleResultEnvelope[SynthesisReportData]:
    return ModuleResultEnvelope(
        module_name=MODULE_NAME,
        status="blocked",
        error_code=error_code,
        data=None,
        metrics=RunMetrics(
            wall_time_ms=max(elapsed_ms, 0),
            llm_calls=0,
            prompt_tokens=0,
            completion_tokens=0,
            estimated_cost_usd=0.0,
            retries=0,
        ),
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_synthesis(input_data: SynthesisInput) -> ModuleResultEnvelope[SynthesisReportData]:
    """Synthesise knowledge from comparison signals, project summaries, and community data.

    Returns a ModuleResultEnvelope containing SynthesisReportData plus two files:
    - synthesis_report.json  (canonical, machine-readable)
    - synthesis_report.md    (human-readable mirror)
    """
    started_at = time.perf_counter()
    warnings: List[WarningItem] = []

    # --- Guard: comparison_result must be present ---
    comparison: Optional[CompareOutput] = input_data.comparison_result
    if comparison is None or not comparison.compared_projects:
        elapsed = int((time.perf_counter() - started_at) * 1000)
        return _blocked(ErrorCodes.UPSTREAM_MISSING, elapsed)

    domain_id = comparison.domain_id
    signals = comparison.signals
    need_keywords: List[str] = input_data.need_profile.keywords or []

    # Separate signals by kind
    aligned = [s for s in signals if s.signal == "ALIGNED"]
    original = [s for s in signals if s.signal == "ORIGINAL"]

    # Build the 4 knowledge blocks
    consensus = _build_consensus(aligned, need_keywords)
    conflicts_from_signals = _extract_conflicts_from_signals(signals, need_keywords)
    license_conflicts = _detect_license_conflicts_from_summaries(
        input_data.project_summaries, signals
    )
    all_conflicts = conflicts_from_signals + license_conflicts

    unique_knowledge = _build_unique_knowledge(
        original,
        input_data.project_summaries,
        input_data.community_knowledge,
        need_keywords,
    )

    excluded_knowledge = _build_excluded_knowledge(
        input_data.project_summaries,
        need_keywords,
    )

    # Guard: unresolved license conflict → blocked
    if _has_unresolved_license_conflict(all_conflicts):
        elapsed = int((time.perf_counter() - started_at) * 1000)
        return _blocked(ErrorCodes.UNRESOLVED_CONFLICT, elapsed)

    selected_knowledge = _assemble_selected(consensus, unique_knowledge)

    open_questions = _derive_open_questions(all_conflicts, warnings, input_data.project_summaries)

    report = SynthesisReportData(
        consensus=consensus,
        conflicts=all_conflicts,
        unique_knowledge=unique_knowledge,
        selected_knowledge=selected_knowledge,
        excluded_knowledge=excluded_knowledge,
        open_questions=open_questions,
    )

    # Write both output files
    output_dir = _synthesis_output_dir(domain_id)
    _write_json(report, output_dir)
    _write_markdown(report, domain_id, output_dir)

    elapsed_ms = int((time.perf_counter() - started_at) * 1000)
    status = "ok" if not warnings else "degraded"

    return ModuleResultEnvelope(
        module_name=MODULE_NAME,
        status=status,
        error_code=None,
        warnings=warnings,
        data=report,
        metrics=RunMetrics(
            wall_time_ms=max(elapsed_ms, 1),
            llm_calls=0,
            prompt_tokens=0,
            completion_tokens=0,
            estimated_cost_usd=0.0,
            retries=0,
        ),
    )
