"""Constraint extraction phases v2 — SOP v2.2 with deterministic pre/post-processing.

Phase factory and Python handlers for the constraint Agent v2 pipeline.

Key improvements over v1 (constraint_phases.py):
- con_build_manifest: deterministic manifest from blueprint YAML (no LLM)
- parallel_group="extract": all extraction phases run concurrently
- con_derive / con_audit: Instructor structured calls (via agent.run_structured_call)
- con_synthesize → con_enrich → con_dedup: three-stage post-processing pipeline
- con_validate: 4 hard gates + 4 warnings (QG-01 to QG-08)

Phase flow:
  con_load_context → con_build_manifest → [parallel extract group] →
  con_synthesize → con_enrich → con_dedup → con_ingest → con_postprocess →
  con_validate
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from doramagic_agent_core.core.agent_loop import PhaseResult
from doramagic_agent_core.sop.executor import Phase
from doramagic_agent_core.state.output import OutputManager
from doramagic_agent_core.state.schema import AgentState

from . import constraint_prompts_v2 as prompts_v2

if TYPE_CHECKING:
    from doramagic_agent_core.core.agent_loop import ExtractionAgent

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_blueprint_yaml(blueprint_path: Path) -> dict[str, Any]:
    """Load and parse a blueprint YAML file."""
    return yaml.safe_load(blueprint_path.read_text(encoding="utf-8")) or {}


def _read_artifact_json(run_dir: Path, artifact_name: str) -> list[dict[str, Any]]:
    """Read a JSON artifact from the artifacts directory.

    Returns the parsed list, or an empty list if the artifact is missing or
    malformed.
    """
    artifact_path = Path(run_dir) / "artifacts" / artifact_name
    if not artifact_path.exists():
        logger.warning("Artifact not found: %s", artifact_path)
        return []
    text = artifact_path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            # Some schemas return {constraints: [...]} — unwrap if present
            if "constraints" in data and isinstance(data["constraints"], list):
                return data["constraints"]
            logger.warning(
                "Artifact %s is a dict without 'constraints' key, returning as single-item list",
                artifact_name,
            )
            return [data]
        logger.warning(
            "Artifact %s is not a JSON array, got %s", artifact_name, type(data).__name__
        )
        return []
    except json.JSONDecodeError as exc:
        logger.warning("Failed to parse artifact %s: %s", artifact_name, exc)
        return []


def _format_stage_for_message(stage: dict[str, Any]) -> str:
    """Format a stage dict into a readable block for the LLM user message."""
    lines = [
        f"Stage ID: {stage.get('id', 'unknown')}",
        f"Name: {stage.get('name', '')}",
        f"Order: {stage.get('order', '')}",
        f"Responsibility: {stage.get('responsibility', '')}",
        "",
    ]

    interface = stage.get("interface", {})
    if interface:
        lines.append("### Interface")
        lines.append(yaml.dump(interface, allow_unicode=True, default_flow_style=False))

    design_decisions = stage.get("design_decisions", [])
    if design_decisions:
        lines.append("### Design Decisions")
        if isinstance(design_decisions, list):
            for dd in design_decisions:
                if isinstance(dd, dict):
                    lines.append(f"  - {dd.get('id', '')}: {dd.get('description', dd)}")
                else:
                    lines.append(f"  - {dd}")
        else:
            lines.append(str(design_decisions))

    acceptance_hints = stage.get("acceptance_hints", [])
    if acceptance_hints:
        lines.append("### Acceptance Hints")
        if isinstance(acceptance_hints, list):
            for ah in acceptance_hints:
                lines.append(f"  - {ah}")
        else:
            lines.append(str(acceptance_hints))

    replaceable_points = stage.get("replaceable_points", [])
    if replaceable_points:
        lines.append("### Replaceable Points (resource_boundary focus)")
        if isinstance(replaceable_points, list):
            for rp in replaceable_points:
                if isinstance(rp, dict):
                    lines.append(f"  - {rp.get('name', '')}: {rp.get('description', rp)}")
                else:
                    lines.append(f"  - {rp}")
        else:
            lines.append(str(replaceable_points))

    return "\n".join(lines)


def _get_manifest(state: AgentState) -> dict[str, Any]:
    """Get coverage manifest from state.extra or fallback to artifact file.

    Fix #3: state.extra is not serialized, so after Resume the manifest is
    gone.  This helper transparently falls back to the persisted artifact.
    """
    manifest = state.extra.get("coverage_manifest")
    if manifest:
        return manifest
    # Fallback: load from artifact written by con_build_manifest
    artifacts_dir = Path(state.run_dir) / "artifacts"
    manifest_path = artifacts_dir / "coverage_manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        state.extra["coverage_manifest"] = manifest  # cache for subsequent reads
        return manifest
    return {}


def _get_edges_from_blueprint(bp: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract edge dicts from blueprint data_flow, handling both formats."""
    data_flow = bp.get("data_flow", {})
    if isinstance(data_flow, dict):
        edges = data_flow.get("edges", [])
    elif isinstance(data_flow, list):
        edges = data_flow
    else:
        edges = []
    return [e for e in edges if isinstance(e, dict)]


# ---------------------------------------------------------------------------
# con_load_context handler — Step 1
# ---------------------------------------------------------------------------


async def _con_load_context_handler(state: AgentState, repo_path: Path) -> PhaseResult:
    """Step 1: Load blueprint YAML and validate the repo path exists.

    Reused from constraint_phases.py with minimal adaptation for v2 pipeline.
    """
    blueprint_path_str = getattr(state, "blueprint_path", None)
    if not blueprint_path_str:
        return PhaseResult(
            phase_name="con_load_context",
            status="error",
            error="state.blueprint_path is not set — cannot load blueprint for constraint extraction",
        )

    blueprint_path = Path(blueprint_path_str)
    if not blueprint_path.exists():
        return PhaseResult(
            phase_name="con_load_context",
            status="error",
            error=f"Blueprint not found: {blueprint_path}",
        )

    if not repo_path.exists():
        return PhaseResult(
            phase_name="con_load_context",
            status="error",
            error=f"Repository path does not exist: {repo_path}",
        )

    bp = _load_blueprint_yaml(blueprint_path)
    n_stages = len(bp.get("stages", []))
    edges = _get_edges_from_blueprint(bp)
    n_edges = len(edges)
    n_bds = len(bp.get("business_decisions", []))

    logger.info(
        "Blueprint loaded: %s — %d stages, %d edges, %d business_decisions",
        bp.get("id", "?"),
        n_stages,
        n_edges,
        n_bds,
    )

    return PhaseResult(
        phase_name="con_load_context",
        status="completed",
        final_text=(
            f"blueprint={blueprint_path.name} stages={n_stages} "
            f"edges={n_edges} business_decisions={n_bds} repo={repo_path}"
        ),
    )


# ---------------------------------------------------------------------------
# con_build_manifest handler — Step 1.5 (new in v2)
# ---------------------------------------------------------------------------


async def _con_build_manifest_handler(state: AgentState, repo_path: Path) -> PhaseResult:
    """Build a deterministic coverage manifest from blueprint YAML.

    Parses all stage_ids, edge_ids, business_decisions (grouped by type),
    audit_checklist_summary fail items, and replaceable_points. The manifest
    is stored in state.extra and written as an artifact for downstream phases.
    """
    blueprint_path_str = getattr(state, "blueprint_path", None)
    if not blueprint_path_str:
        return PhaseResult(
            phase_name="con_build_manifest",
            status="error",
            error="state.blueprint_path is not set",
        )

    blueprint_path = Path(blueprint_path_str)
    bp = _load_blueprint_yaml(blueprint_path)

    stages = bp.get("stages", [])
    edges = _get_edges_from_blueprint(bp)
    business_decisions = bp.get("business_decisions", [])

    # --- Build stage manifest ---
    stages_manifest: dict[str, dict[str, Any]] = {}
    replaceable_points_by_stage: dict[str, list[dict[str, Any]]] = {}

    for stage in stages:
        stage_id = stage.get("id", "")
        if not stage_id:
            continue
        stages_manifest[stage_id] = {
            "id": stage_id,
            "name": stage.get("name", ""),
            "order": stage.get("order", ""),
            "responsibility": stage.get("responsibility", ""),
            "interface": stage.get("interface", {}),
            "design_decisions": stage.get("design_decisions", []),
            "acceptance_hints": stage.get("acceptance_hints", []),
            "replaceable_points": stage.get("replaceable_points", []),
        }
        rps = stage.get("replaceable_points", [])
        if rps:
            replaceable_points_by_stage[stage_id] = rps if isinstance(rps, list) else [rps]

    # --- Build edge manifest ---
    edge_ids: list[str] = []
    edges_manifest: dict[str, dict[str, Any]] = {}
    for i, edge in enumerate(edges):
        eid = edge.get("id", f"edge_{i}")
        edge_ids.append(eid)
        edges_manifest[eid] = {
            "id": eid,
            "from_stage": edge.get("from", edge.get("from_stage", "")),
            "to_stage": edge.get("to", edge.get("to_stage", "")),
            "data": edge.get("data", edge.get("label", "")),
            "edge_type": edge.get("edge_type", "data_flow"),
        }

    # --- Group business decisions by type ---
    bds_by_type: dict[str, list[dict[str, Any]]] = {}
    for bd in business_decisions:
        bd_type = bd.get("type", "unknown")
        bds_by_type.setdefault(bd_type, []).append(bd)

    # --- Audit checklist fail items ---
    # Blueprint audit_checklist_summary has multiple sub-structures:
    #   - Top-level category dicts: {pass, warn, fail} (e.g. finance_universal)
    #   - subdomain_checklists: list of {name, result: {pass, warn, fail}}
    #   - critical_findings: list of {item, severity, type, disposition, ...}
    audit_summary = bp.get("audit_checklist_summary", {})
    audit_fail_items: list[dict[str, Any]] = []
    if isinstance(audit_summary, dict):
        for category, items in audit_summary.items():
            if category in ("sop_version", "executed_at", "subdomain_labels"):
                # Scalar metadata fields — skip
                continue
            if category == "subdomain_checklists" and isinstance(items, list):
                # Each item: {name, result: {pass, warn, fail}}
                for subdom in items:
                    if not isinstance(subdom, dict):
                        continue
                    result = subdom.get("result", {})
                    if isinstance(result, dict) and result.get("fail", 0) > 0:
                        audit_fail_items.append(
                            {
                                "category": f"subdomain_{subdom.get('name', 'unknown')}",
                                "name": subdom.get("name", ""),
                                **result,
                            }
                        )
            elif category == "critical_findings" and isinstance(items, list):
                # Each item: {item, severity, type, disposition, stage, evidence}
                # These are the most actionable fail items — always include.
                for finding in items:
                    if isinstance(finding, dict):
                        audit_fail_items.append(
                            {
                                "category": "critical_finding",
                                **finding,
                            }
                        )
            elif isinstance(items, list):
                for item in items:
                    if isinstance(item, dict) and item.get("fail", 0) > 0:
                        audit_fail_items.append(
                            {
                                "category": category,
                                **item,
                            }
                        )
            elif isinstance(items, dict) and items.get("fail", 0) > 0:
                audit_fail_items.append(
                    {
                        "category": category,
                        **items,
                    }
                )
    elif isinstance(audit_summary, list):
        for item in audit_summary:
            if isinstance(item, dict) and item.get("fail", 0) > 0:
                audit_fail_items.append(item)
    logger.info(
        "con_build_manifest: audit_fail_items extracted=%d "
        "(critical_findings=%d subdomain_fails=%d category_fails=%d)",
        len(audit_fail_items),
        sum(1 for x in audit_fail_items if x.get("category") == "critical_finding"),
        sum(1 for x in audit_fail_items if x.get("category", "").startswith("subdomain_")),
        sum(
            1
            for x in audit_fail_items
            if x.get("category") not in ("critical_finding",)
            and not x.get("category", "").startswith("subdomain_")
        ),
    )

    # --- Evidence files ---
    evidence = bp.get("evidence", {})
    evidence_files: list[str] = []
    if isinstance(evidence, dict):
        for _category, refs in evidence.items():
            if isinstance(refs, list):
                for ref in refs:
                    if isinstance(ref, str):
                        evidence_files.append(ref)
                    elif isinstance(ref, dict) and ref.get("path"):
                        evidence_files.append(ref["path"])
            elif isinstance(refs, str):
                evidence_files.append(refs)

    # --- Assemble manifest ---
    manifest: dict[str, Any] = {
        "blueprint_id": bp.get("id", state.blueprint_id),
        "stage_ids": list(stages_manifest.keys()),
        "edge_ids": edge_ids,
        "stages": stages_manifest,
        "edges": edges_manifest,
        "business_decisions_by_type": bds_by_type,
        "business_decisions_count": len(business_decisions),
        "audit_fail_items": audit_fail_items,
        "evidence_files": evidence_files,
        "replaceable_points_by_stage": replaceable_points_by_stage,
        "applicability": bp.get("applicability", {}),
        "global_contracts": bp.get("global_contracts", []),
    }

    # Write to state.extra for in-memory access by downstream phases
    state.extra["coverage_manifest"] = manifest

    # Write to artifact for persistence
    artifacts_dir = Path(state.run_dir) / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "coverage_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    summary = (
        f"stages={len(stages_manifest)} edges={len(edge_ids)} "
        f"bds={len(business_decisions)} audit_fail_items={len(audit_fail_items)} "
        f"evidence_files={len(evidence_files)}"
    )
    logger.info("con_build_manifest: %s", summary)

    return PhaseResult(
        phase_name="con_build_manifest",
        status="completed",
        final_text=summary,
    )


# ---------------------------------------------------------------------------
# Initial message builders (agentic phases)
# ---------------------------------------------------------------------------


def _build_stage_extract_message_v2(
    stage: dict[str, Any],
    blueprint: dict[str, Any],
    blueprint_path: Path,
) -> Callable[[AgentState, Path], str]:
    """Factory for per-stage initial message builder (v2 with manifest context)."""
    stage_id = stage.get("id", "unknown")
    stage_name = stage.get("name", "")

    def builder(state: AgentState, repo_path: Path) -> str:
        manifest = _get_manifest(state)
        stage_ctx = manifest.get("stages", {}).get(stage_id, {})
        evidence_files = manifest.get("evidence_files", [])

        stage_block = _format_stage_for_message(stage)
        bp_id = blueprint.get("id", "unknown")
        bp_name = blueprint.get("name", "")

        # Collect evidence refs from design_decisions
        evidence_refs: list[str] = []
        for dd in stage_ctx.get("design_decisions", stage.get("design_decisions", [])):
            if isinstance(dd, dict):
                ev = dd.get("evidence", "")
                if ev:
                    evidence_refs.append(str(ev))

        evidence_hint = ""
        if evidence_refs:
            evidence_hint = (
                "\n\nEvidence references from blueprint (use these as starting points for read_file):\n"
                + "\n".join(f"  - {e}" for e in evidence_refs[:10])
            )
        elif evidence_files:
            evidence_hint = "\n\nEvidence files from blueprint:\n" + "\n".join(
                f"  - {e}" for e in evidence_files[:10]
            )

        msg = (
            f"## Blueprint: {bp_id} — {bp_name}\n"
            f"## Stage: {stage_id} — {stage_name}\n"
            f"Repository: {repo_path}\n"
            f"Blueprint file: {blueprint_path}\n"
            f"{evidence_hint}\n\n"
            f"## Stage Definition\n\n"
            f"{stage_block}\n\n"
        )

        # --- Stage-id whitelist (防止 LLM 编造 stage 名称) ---
        all_stage_ids = manifest.get("stage_ids", [])
        msg += "## IMPORTANT: stage_ids 白名单\n"
        msg += f"本次提取的 stage ID 是: `{stage_id}`\n"
        msg += f'所有约束的 stage_ids 字段必须只使用这个值: ["{stage_id}"]\n'
        msg += f"蓝图所有合法 stage IDs: {json.dumps(all_stage_ids, ensure_ascii=False)}\n"
        msg += "禁止使用任何不在上述列表中的 stage ID（如 technical_indicator、risk_management 等自造名称）。\n\n"

        # Acceptance hints for coverage awareness
        acceptance_hints = stage_ctx.get("acceptance_hints", stage.get("acceptance_hints", []))
        if acceptance_hints:
            msg += "## Acceptance Hints (must be covered by constraints)\n\n"
            for ah in acceptance_hints:
                msg += f"  - {ah}\n"
            msg += "\n"

        msg += (
            "## Instructions\n\n"
            "1. Read the stage definition above carefully.\n"
            "2. Use get_skeleton, read_file, and grep_codebase to examine source files "
            "referenced in the blueprint (evidence refs, interface inputs/outputs, "
            "design_decisions).\n"
            "3. Extract ALL constraints for this stage across all 5 kinds: "
            "domain_rule, resource_boundary, operational_lesson, architecture_guardrail, "
            "claim_boundary.\n"
            "4. For each kind, follow the KIND_GUIDANCE in your system prompt.\n"
            f"5. When done, call write_artifact(name='constraints_{stage_id}.json') "
            "with the ConstraintExtractionResult JSON.\n"
        )
        return msg

    return builder


def _build_edges_extract_message_v2(
    blueprint: dict[str, Any],
    blueprint_path: Path,
) -> Callable[[AgentState, Path], str]:
    """Factory for edge constraints initial message builder (v2)."""

    def builder(state: AgentState, repo_path: Path) -> str:
        manifest = _get_manifest(state)
        bp_id = blueprint.get("id", "unknown")
        bp_name = blueprint.get("name", "")

        edges = _get_edges_from_blueprint(blueprint)
        edges_block = (
            yaml.dump(edges, allow_unicode=True, default_flow_style=False)
            if edges
            else "(no edges defined)"
        )

        # Stage name lookup from manifest
        stages_manifest = manifest.get("stages", {})
        stage_names = {sid: info.get("name", "") for sid, info in stages_manifest.items()}
        if not stage_names:
            stage_names = {s.get("id", ""): s.get("name", "") for s in blueprint.get("stages", [])}

        return (
            f"## Blueprint: {bp_id} — {bp_name}\n"
            f"Repository: {repo_path}\n"
            f"Blueprint file: {blueprint_path}\n\n"
            f"## Data Flow Edges\n\n"
            f"{edges_block}\n\n"
            f"## Stage Names Reference\n"
            + "\n".join(f"  {sid}: {sname}" for sid, sname in stage_names.items())
            + "\n\n"
            "## Instructions\n\n"
            "1. For each edge, identify the upstream and downstream stages.\n"
            "2. Use get_skeleton, read_file, and grep_codebase to examine how data "
            "flows between stages.\n"
            "3. Extract cross-stage constraints: data format, ordering/timing, "
            "data integrity, type conversion.\n"
            "4. target_scope must be 'edge'; populate edge_ids with the edge ID.\n"
            "5. When done, call write_artifact(name='constraints_edges.json') "
            "with the ConstraintExtractionResult JSON.\n"
        )

    return builder


def _build_global_extract_message_v2(
    blueprint: dict[str, Any],
    blueprint_path: Path,
) -> Callable[[AgentState, Path], str]:
    """Factory for global + claim_boundary initial message builder (v2)."""

    def builder(state: AgentState, repo_path: Path) -> str:
        manifest = _get_manifest(state)
        bp_id = blueprint.get("id", "unknown")
        bp_name = blueprint.get("name", "")

        global_contracts = manifest.get("global_contracts", blueprint.get("global_contracts", []))
        applicability = manifest.get("applicability", blueprint.get("applicability", {}))
        not_suitable_for = applicability.get("not_suitable_for", [])
        description = applicability.get("description", "")

        global_block = (
            yaml.dump(global_contracts, allow_unicode=True, default_flow_style=False)
            if global_contracts
            else "(no global_contracts defined)"
        )
        nsf_block = (
            "\n".join(f"  - {item}" for item in not_suitable_for)
            if not_suitable_for
            else "(none listed)"
        )

        return (
            f"## Blueprint: {bp_id} — {bp_name}\n"
            f"Repository: {repo_path}\n"
            f"Blueprint file: {blueprint_path}\n\n"
            f"## Global Contracts\n\n"
            f"{global_block}\n\n"
            f"## Applicability\n\n"
            f"Description: {description}\n\n"
            f"## Not Suitable For (claim_boundary source)\n\n"
            f"{nsf_block}\n\n"
            "## Instructions\n\n"
            "1. Read the global_contracts and applicability sections above.\n"
            "2. Use read_file to examine the project README and top-level package "
            "files for global invariants, capability claims, and system-wide rules.\n"
            "3. Extract:\n"
            "   a. Global invariants (cross-stage constraints with target_scope='global')\n"
            "   b. System-level capability boundaries (resource_boundary)\n"
            "   c. Global architectural conventions (architecture_guardrail)\n"
            "   d. claim_boundary constraints — what users MUST NOT claim this system can do\n"
            "      (include both code-backed claims and expert_reasoning-based claims)\n"
            "4. When done, call write_artifact(name='constraints_global.json') "
            "with the ConstraintExtractionResult JSON.\n"
        )

    return builder


# ---------------------------------------------------------------------------
# con_derive handler — Step 2.4 (Instructor structured call)
# ---------------------------------------------------------------------------


_DERIVE_CHUNK_SIZE = 10  # max BDs per Instructor call — 20 was too large,
# causing 10K+ output tokens and frequent timeouts
_DERIVE_CHUNK_TIMEOUT = 600  # 10 min per chunk — must cover L1 (≤300s httpx read)
# + L2 freeform fallback (≤300s long_timeout)


def _build_derive_user_message(
    bds_by_type: dict[str, list[dict[str, Any]]],
    blueprint_id: str,
    *,
    chunk_index: int | None = None,
    total_chunks: int | None = None,
) -> str:
    """Build the user message for the derive Instructor call.

    Groups business decisions by type for clear LLM consumption.
    """
    parts: list[str] = [
        f"## Blueprint: {blueprint_id}\n",
    ]
    if chunk_index is not None and total_chunks is not None:
        parts.append(
            f"## Batch {chunk_index + 1}/{total_chunks} (process ONLY the decisions listed below)\n"
        )
    parts.append("## Business Decisions by Type\n")

    for bd_type, bds in sorted(bds_by_type.items()):
        parts.append(f"\n### Type: {bd_type} ({len(bds)} decisions)\n")
        parts.append("```json")
        parts.append(json.dumps(bds, ensure_ascii=False, indent=2))
        parts.append("```\n")

    parts.append(
        "\n## Instructions\n\n"
        "Derive constraints from the business_decisions above following "
        "the SOP v2.2 Step 2.4 derivation rules in your system prompt.\n\n"
        "Every derived constraint must include a derived_from field with:\n"
        f"  blueprint_id='{blueprint_id}', business_decision_id, "
        "derivation_version='sop-v2.2'\n"
    )
    return "\n".join(parts)


# BD types that SOP says to skip in derive (pure technical choices)
_SKIP_BD_TYPES = {"T"}


def _chunk_bds(
    bds_by_type: dict[str, list[dict[str, Any]]],
    chunk_size: int = _DERIVE_CHUNK_SIZE,
) -> list[dict[str, list[dict[str, Any]]]]:
    """Split business decisions into chunks of ≤chunk_size total BDs.

    Improvements over naive sequential chunking:
    - Filters out T-type BDs (SOP says skip in derive)
    - Uses round-robin by type to distribute high-yield types (M, RC)
      across chunks instead of concentrating them
    """
    # Flatten, filtering out T-type
    tagged: list[tuple[str, dict[str, Any]]] = []
    skipped = 0
    for bd_type, bds in sorted(bds_by_type.items()):
        # Skip pure T-type BDs (check primary type before slash)
        primary_type = bd_type.split("/")[0] if "/" in bd_type else bd_type
        if primary_type in _SKIP_BD_TYPES:
            skipped += len(bds)
            continue
        for bd in bds:
            tagged.append((bd_type, bd))

    if skipped:
        logger.info(
            "_chunk_bds: filtered %d T-type BDs, %d remaining",
            skipped,
            len(tagged),
        )

    if not tagged:
        return []

    # Round-robin: group by type, then interleave
    by_type: dict[str, list[dict[str, Any]]] = {}
    for bd_type, bd in tagged:
        by_type.setdefault(bd_type, []).append(bd)

    # Sort types by priority: M > RC > B > BA > DK (high-yield first)
    type_priority = {"M": 0, "RC": 1, "B": 2, "BA": 3}
    sorted_types = sorted(
        by_type.keys(),
        key=lambda t: type_priority.get(t.split("/")[0], 5),
    )

    # Interleave: take one BD from each type in rotation
    interleaved: list[tuple[str, dict[str, Any]]] = []
    indices = {t: 0 for t in sorted_types}
    while len(interleaved) < len(tagged):
        added = False
        for t in sorted_types:
            if indices[t] < len(by_type[t]):
                interleaved.append((t, by_type[t][indices[t]]))
                indices[t] += 1
                added = True
        if not added:
            break

    # Split into chunks
    chunks: list[dict[str, list[dict[str, Any]]]] = []
    for i in range(0, len(interleaved), chunk_size):
        chunk_items = interleaved[i : i + chunk_size]
        chunk_dict: dict[str, list[dict[str, Any]]] = {}
        for bd_type, bd in chunk_items:
            chunk_dict.setdefault(bd_type, []).append(bd)
        chunks.append(chunk_dict)
    return chunks


async def _derive_single_chunk(
    agent: Any,
    bds_chunk: dict[str, list[dict[str, Any]]],
    blueprint_id: str,
    chunk_index: int,
    total_chunks: int,
) -> tuple[Any | None, int, str | None]:
    """Run derive Instructor call for a single BD chunk.

    Uses ConstraintExtractionResult (same schema as per-stage extraction,
    proven 9/9 on MiniMax) instead of DeriveChunkResult which has nested
    DerivedConstraint/MissingGapPair schemas that MiniMax can't handle.

    derived_from is injected post-hoc from the BD context.

    Returns (result, tokens, error_msg).
    """
    import asyncio as _asyncio

    from .constraint_schemas_v2 import ConstraintExtractionResult, RawFallback

    bd_count = sum(len(bds) for bds in bds_chunk.values())
    user_msg = _build_derive_user_message(
        bds_chunk,
        blueprint_id,
        chunk_index=chunk_index,
        total_chunks=total_chunks,
    )
    logger.info(
        "con_derive chunk %d/%d: %d BDs, %d chars",
        chunk_index + 1,
        total_chunks,
        bd_count,
        len(user_msg),
    )

    try:
        result, tokens = await _asyncio.wait_for(
            agent.run_structured_call(
                prompts_v2.CON_DERIVE_V2_SYSTEM,
                user_msg,
                ConstraintExtractionResult,
                max_retries=2,
            ),
            timeout=_DERIVE_CHUNK_TIMEOUT,
        )
    except TimeoutError:
        logger.warning(
            "con_derive chunk %d/%d: timed out after %ds",
            chunk_index + 1,
            total_chunks,
            _DERIVE_CHUNK_TIMEOUT,
        )
        return None, 0, f"chunk {chunk_index + 1}/{total_chunks} timed out"

    if isinstance(result, RawFallback):
        # L3 recovery: MiniMax produced text with constraint data but
        # validation failed (often old grouped format or field mismatches).
        # Try manual extraction from the raw text.
        recovered = _recover_derive_from_raw(result.text, chunk_index, total_chunks)
        if recovered:
            logger.info(
                "con_derive chunk %d/%d: L3 recovery extracted %d constraints",
                chunk_index + 1,
                total_chunks,
                len(recovered.constraints),
            )
            return recovered, tokens, None
        logger.warning(
            "con_derive chunk %d/%d: L3 fallback (recovery failed)",
            chunk_index + 1,
            total_chunks,
        )
        return None, tokens, f"chunk {chunk_index + 1}/{total_chunks} failed (no fallback)"

    return result, tokens, None


def _recover_derive_from_raw(
    raw_text: str,
    chunk_index: int,
    total_chunks: int,
) -> Any | None:
    """Try to recover constraints from L3 raw text.

    Handles two common MiniMax failure modes:
    1. Old grouped format (rc_constraints/ba_constraints/etc.)
    2. Valid constraint JSON objects embedded in markdown/text
    """
    import json
    import re

    from .constraint_schemas_v2 import ConstraintExtractionResult, RawConstraint

    # Try to find JSON in the text
    json_match = re.search(r"\{[\s\S]*\}", raw_text)
    if not json_match:
        return None

    try:
        data = json.loads(json_match.group())
    except json.JSONDecodeError:
        return None

    # Coerce old grouped format → flat list
    all_constraints: list[dict] = []
    if isinstance(data, dict):
        # Check for grouped format keys
        for key in (
            "rc_constraints",
            "ba_constraints",
            "m_constraints",
            "b_constraints",
            "constraints",
        ):
            items = data.get(key, [])
            if isinstance(items, list):
                all_constraints.extend(items)
        # Handle missing_gap_pairs
        for pair in data.get("missing_gap_pairs", []):
            if isinstance(pair, dict):
                if "boundary" in pair and isinstance(pair["boundary"], dict):
                    all_constraints.append(pair["boundary"])
                if "remedy" in pair and isinstance(pair["remedy"], dict):
                    all_constraints.append(pair["remedy"])
    elif isinstance(data, list):
        all_constraints = data

    if not all_constraints:
        return None

    # Validate each constraint individually, skip invalid ones
    valid: list[RawConstraint] = []
    for item in all_constraints:
        if not isinstance(item, dict):
            continue
        try:
            valid.append(RawConstraint.model_validate(item))
        except Exception:
            continue

    if not valid:
        return None

    logger.info(
        "con_derive chunk %d/%d: L3 recovery: %d/%d constraints valid",
        chunk_index + 1,
        total_chunks,
        len(valid),
        len(all_constraints),
    )
    return ConstraintExtractionResult(constraints=valid)


def _accumulate_derive_result(
    result: Any,
    all_derived: list[dict[str, Any]],
    totals: list[int],
) -> None:
    """Expand a derive result into the flat list and update counters.

    Supports ConstraintExtractionResult (current, uses RawConstraint),
    DeriveChunkResult (flat DerivedConstraint), and legacy DeriveExtractionResult (grouped).
    """
    if hasattr(result, "constraints"):
        all_derived.extend(c.model_dump() for c in result.constraints)
        # Handle missing_gap_pairs if present (DeriveChunkResult)
        if hasattr(result, "missing_gap_pairs"):
            for pair in result.missing_gap_pairs:
                all_derived.append(pair.boundary.model_dump())
                all_derived.append(pair.remedy.model_dump())
            totals[4] += len(result.missing_gap_pairs)
        if hasattr(result, "skipped_decisions"):
            totals[5] += len(result.skipped_decisions)
        # Classify into totals by constraint_kind
        for c in result.constraints:
            kind = c.constraint_kind
            if kind == "domain_rule":
                totals[0] += 1
            elif kind == "operational_lesson":
                totals[1] += 1
            elif kind == "architecture_guardrail":
                totals[2] += 1
            else:
                totals[3] += 1
    else:
        # Legacy DeriveExtractionResult (grouped)
        all_derived.extend(c.model_dump() for c in result.rc_constraints)
        all_derived.extend(c.model_dump() for c in result.ba_constraints)
        all_derived.extend(c.model_dump() for c in result.m_constraints)
        all_derived.extend(c.model_dump() for c in result.b_constraints)
        for pair in result.missing_gap_pairs:
            all_derived.append(pair.boundary.model_dump())
            all_derived.append(pair.remedy.model_dump())
        totals[0] += len(result.rc_constraints)
        totals[1] += len(result.ba_constraints)
        totals[2] += len(result.m_constraints)
        totals[3] += len(result.b_constraints)
        totals[4] += len(result.missing_gap_pairs)
        totals[5] += len(result.skipped_decisions)


def _count_derive_result(result: Any) -> int:
    """Count total constraints in a derive result."""
    if hasattr(result, "constraints"):
        count = len(result.constraints)
        if hasattr(result, "missing_gap_pairs"):
            count += len(result.missing_gap_pairs) * 2
        return count
    # Legacy DeriveExtractionResult
    return (
        len(result.rc_constraints)
        + len(result.ba_constraints)
        + len(result.m_constraints)
        + len(result.b_constraints)
        + len(result.missing_gap_pairs) * 2
    )


async def _con_derive_v2_handler(state: AgentState, repo_path: Path) -> PhaseResult:
    """Step 2.4: Derive constraints from business_decisions via Instructor.

    Splits BDs into chunks of ≤10 to avoid MiniMax timeout on large contexts.
    T-type BDs are filtered (SOP says skip). Types are round-robin interleaved
    so M/RC (high-yield) types are distributed across chunks. Each chunk gets
    its own Instructor call (sequential). Failed chunks are retried with
    fallback agent if available. Results are merged into constraints_derived.json.
    """
    agent = state.extra.get("agent")
    if not agent:
        return PhaseResult(
            phase_name="con_derive",
            status="error",
            error="agent not available for structured call — was it injected via build?",
        )

    manifest = _get_manifest(state)
    bds_by_type = manifest.get("business_decisions_by_type", {})

    if not bds_by_type:
        return PhaseResult(
            phase_name="con_derive",
            status="completed",
            final_text="No business_decisions in manifest — skipped derive",
        )

    total_bds = sum(len(bds) for bds in bds_by_type.values())
    chunks = _chunk_bds(bds_by_type)

    if not chunks:
        return PhaseResult(
            phase_name="con_derive",
            status="completed",
            final_text=(f"All {total_bds} BDs are T-type (filtered) — nothing to derive"),
        )

    logger.info(
        "con_derive: %d BDs split into %d chunks (chunk_size=%d)",
        total_bds,
        len(chunks),
        _DERIVE_CHUNK_SIZE,
    )

    # Run chunks sequentially (MiniMax rate limits)
    all_derived: list[dict[str, Any]] = []
    total_tokens = 0
    total_rc = total_ba = total_m = total_b = total_gap = total_skipped = 0
    failed_chunks: list[tuple[int, dict[str, list[dict[str, Any]]]]] = []

    for i, chunk in enumerate(chunks):
        result, tokens, err = await _derive_single_chunk(
            agent,
            chunk,
            state.blueprint_id,
            i,
            len(chunks),
        )
        total_tokens += tokens

        if err:
            failed_chunks.append((i, chunk))
            continue

        _accumulate_derive_result(
            result,
            all_derived,
            totals := [total_rc, total_ba, total_m, total_b, total_gap, total_skipped],
        )
        total_rc, total_ba, total_m, total_b, total_gap, total_skipped = totals

        logger.info(
            "con_derive chunk %d/%d: +%d constraints",
            i + 1,
            len(chunks),
            _count_derive_result(result),
        )

    # --- Failover: retry failed chunks with fallback agent ---
    fallback_agent = state.extra.get("fallback_agent")
    retried_chunks: list[str] = []
    if failed_chunks and fallback_agent:
        fb_model = getattr(fallback_agent, "_model_id", "fallback")
        logger.warning(
            "con_derive: %d chunk(s) failed on primary — retrying with fallback model %s",
            len(failed_chunks),
            fb_model,
        )
        for i, chunk in failed_chunks:
            result, tokens, err = await _derive_single_chunk(
                fallback_agent,
                chunk,
                state.blueprint_id,
                i,
                len(chunks),
            )
            total_tokens += tokens
            if err:
                retried_chunks.append(f"chunk {i + 1}/{len(chunks)} failover: {err}")
                continue
            _accumulate_derive_result(
                result,
                all_derived,
                totals := [total_rc, total_ba, total_m, total_b, total_gap, total_skipped],
            )
            (total_rc, total_ba, total_m, total_b, total_gap, total_skipped) = totals
            logger.info(
                "con_derive chunk %d/%d (fallback): +%d constraints",
                i + 1,
                len(chunks),
                _count_derive_result(result),
            )
    elif failed_chunks:
        retried_chunks = [
            f"chunk {i + 1}/{len(chunks)} failed (no fallback)" for i, _ in failed_chunks
        ]

    # Write artifact (even partial results are useful)
    artifacts_dir = Path(state.run_dir) / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "constraints_derived.json").write_text(
        json.dumps(all_derived, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    summary = (
        f"Derived {len(all_derived)} constraints in {len(chunks)} chunks "
        f"(rc={total_rc} ba={total_ba} m={total_m} b={total_b} "
        f"gap_pairs={total_gap} skipped={total_skipped})"
    )
    if retried_chunks:
        summary += f" — {len(retried_chunks)} issue(s): "
        summary += "; ".join(retried_chunks)

    logger.info("con_derive: %s", summary)

    # If ALL chunks failed, log warning but do NOT kill the pipeline —
    # con_derive is supplementary; per-stage extraction is the primary source.
    if not all_derived:
        logger.warning("con_derive: all chunks failed — 0 derived constraints (non-fatal)")
        return PhaseResult(
            phase_name="con_derive",
            status="completed",
            final_text=f"[WARNING] {summary}",
            total_tokens=total_tokens,
        )

    return PhaseResult(
        phase_name="con_derive",
        status="completed",
        final_text=summary,
        total_tokens=total_tokens,
    )


# ---------------------------------------------------------------------------
# con_audit handler — Step 2.5 (Instructor structured call)
# ---------------------------------------------------------------------------


def _build_audit_user_message(
    audit_fail_items: list[dict[str, Any]],
    blueprint_id: str,
    blueprint_path: Path,
) -> str:
    """Build the user message for the audit Instructor call."""
    parts: list[str] = [
        f"## Blueprint: {blueprint_id}\n",
        f"Blueprint file: {blueprint_path}\n\n",
        f"## Audit Checklist Fail Items ({len(audit_fail_items)} items)\n\n",
        "```json",
        json.dumps(audit_fail_items, ensure_ascii=False, indent=2),
        "```\n\n",
        "## Instructions\n\n",
        "Convert each High/Critical fail item to a constraint following "
        "your system prompt rules.\n",
        "Skip items already covered by business_decisions derivation (Step 2.4).\n",
    ]
    return "\n".join(parts)


async def _con_audit_v2_handler(state: AgentState, repo_path: Path) -> PhaseResult:
    """Step 2.5: Convert audit-checklist fail findings to constraints via Instructor.

    Only runs when blueprint has audit_checklist_summary with fail items.
    """
    agent = state.extra.get("agent")
    if not agent:
        return PhaseResult(
            phase_name="con_audit",
            status="error",
            error="agent not available for structured call",
        )

    manifest = _get_manifest(state)
    audit_fail_items = manifest.get("audit_fail_items", [])

    if not audit_fail_items:
        return PhaseResult(
            phase_name="con_audit",
            status="completed",
            final_text="No audit fail items — skipped",
        )

    blueprint_path_str = getattr(state, "blueprint_path", "")
    user_msg = _build_audit_user_message(
        audit_fail_items,
        state.blueprint_id,
        Path(blueprint_path_str),
    )

    from .constraint_schemas_v2 import AuditConstraintResult, RawFallback

    result, tokens = await agent.run_structured_call(
        prompts_v2.CON_AUDIT_V2_SYSTEM,
        user_msg,
        AuditConstraintResult,
    )

    if isinstance(result, RawFallback):
        artifacts_dir = Path(state.run_dir) / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        (artifacts_dir / "constraints_audit_raw.txt").write_text(
            result.text,
            encoding="utf-8",
        )
        return PhaseResult(
            phase_name="con_audit",
            status="error",
            error=f"Audit L3 fallback: {result.stage}",
            total_tokens=tokens,
        )

    audit_constraints = [c.model_dump() for c in result.constraints]

    # Write artifact
    artifacts_dir = Path(state.run_dir) / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "constraints_audit.json").write_text(
        json.dumps(audit_constraints, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    summary = (
        f"Audit converted {len(audit_constraints)} constraints, "
        f"skipped {len(result.skipped_items)} items"
    )
    logger.info("con_audit: %s", summary)

    return PhaseResult(
        phase_name="con_audit",
        status="completed",
        final_text=summary,
        total_tokens=tokens,
    )


# ---------------------------------------------------------------------------
# con_extract_resources handler — resource inventory (non-blocking)
# ---------------------------------------------------------------------------


async def _con_extract_resources_handler(state: AgentState, repo_path: Path) -> PhaseResult:
    """Extract resource inventory (dependencies, APIs, infrastructure)."""
    from .constraint_resources import extract_resources

    agent = state.extra.get("agent")
    manifest = _get_manifest(state)
    blueprint_path = getattr(state, "blueprint_path", "") or state.extra.get("blueprint_path", "")

    bp = {}
    if blueprint_path:
        try:
            bp = _load_blueprint_yaml(Path(blueprint_path))
        except Exception:
            bp = {}

    artifacts_dir = Path(state.run_dir) / "artifacts"
    return await extract_resources(agent, bp, manifest, repo_path, artifacts_dir)


# ---------------------------------------------------------------------------
# con_synthesize handler — merge all extraction artifacts
# ---------------------------------------------------------------------------


async def _con_synthesize_handler(state: AgentState, repo_path: Path) -> PhaseResult:
    """Merge all constraints_*.json artifacts into a single constraints_merged.json.

    Collects per-stage, edges, global, derived, and audit artifacts. Tags each
    raw constraint with scope metadata (target_scope, stage_ids, edge_ids).
    """
    run_dir = Path(state.run_dir)
    manifest = _get_manifest(state)
    stage_ids = manifest.get("stage_ids", [])

    merged: list[dict[str, Any]] = []

    # 1. Per-stage artifacts
    for sid in stage_ids:
        artifact_name = f"constraints_{sid}.json"
        items = _read_artifact_json(run_dir, artifact_name)
        for item in items:
            # Ensure scope metadata is present
            if not item.get("target_scope"):
                item["target_scope"] = "stage"
            # Always force stage_ids to the current stage — this artifact
            # was produced by con_extract_{sid}, so all its constraints
            # belong to this stage regardless of what the LLM wrote.
            old_ids = item.get("stage_ids", [])
            item["stage_ids"] = [sid]
            if old_ids and old_ids != [sid]:
                logger.debug(
                    "Forced stage_ids %s → [%s] in %s",
                    old_ids,
                    sid,
                    artifact_name,
                )
            merged.append(item)
        logger.debug("Synthesize: %d items from %s", len(items), artifact_name)

    # 2. Edge artifact
    edge_items = _read_artifact_json(run_dir, "constraints_edges.json")
    for item in edge_items:
        if not item.get("target_scope"):
            item["target_scope"] = "edge"
        merged.append(item)
    logger.debug("Synthesize: %d items from constraints_edges.json", len(edge_items))

    # 3. Global artifact
    global_items = _read_artifact_json(run_dir, "constraints_global.json")
    for item in global_items:
        if not item.get("target_scope"):
            item["target_scope"] = "global"
        merged.append(item)
    logger.debug("Synthesize: %d items from constraints_global.json", len(global_items))

    # 4. Derived artifact
    derived_items = _read_artifact_json(run_dir, "constraints_derived.json")
    for item in derived_items:
        # Derived constraints keep their own target_scope
        if not item.get("target_scope"):
            item["target_scope"] = "global"
        merged.append(item)
    logger.debug("Synthesize: %d items from constraints_derived.json", len(derived_items))

    # 5. Audit artifact
    audit_items = _read_artifact_json(run_dir, "constraints_audit.json")
    for item in audit_items:
        if not item.get("target_scope"):
            item["target_scope"] = "global"
        merged.append(item)
    logger.debug("Synthesize: %d items from constraints_audit.json", len(audit_items))

    # 6. v3 document extraction artifact (SOP v2.3 Step 2.1-s)
    doc_items = _read_artifact_json(run_dir, "ct_doc_constraints.json")
    for item in doc_items:
        if not item.get("target_scope"):
            item["target_scope"] = "global"
        merged.append(item)
    if doc_items:
        logger.debug("Synthesize: %d items from ct_doc_constraints.json", len(doc_items))

    # 7. v3 rationalization guard artifact (SOP v2.3 Step 2.6)
    ration_items = _read_artifact_json(run_dir, "ct_rationalization_constraints.json")
    for item in ration_items:
        if not item.get("target_scope"):
            item["target_scope"] = "global"
        merged.append(item)
    if ration_items:
        logger.debug(
            "Synthesize: %d items from ct_rationalization_constraints.json",
            len(ration_items),
        )

    if not merged:
        return PhaseResult(
            phase_name="con_synthesize",
            status="error",
            error="No constraints found in any extraction artifact",
        )

    # Write merged artifact
    artifacts_dir = run_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "constraints_merged.json").write_text(
        json.dumps(merged, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    stage_total = sum(len(_read_artifact_json(run_dir, f"constraints_{s}.json")) for s in stage_ids)
    summary = (
        f"Merged {len(merged)} constraints "
        f"(stages={stage_total} edges={len(edge_items)} "
        f"global={len(global_items)} derived={len(derived_items)} "
        f"audit={len(audit_items)} doc={len(doc_items)} "
        f"rationalization={len(ration_items)})"
    )
    logger.info("con_synthesize: %s", summary)

    return PhaseResult(
        phase_name="con_synthesize",
        status="completed",
        final_text=summary,
    )


# ---------------------------------------------------------------------------
# con_enrich handler — deterministic enrichment patches
# ---------------------------------------------------------------------------


async def _con_enrich_handler(state: AgentState, repo_path: Path) -> PhaseResult:
    """Apply 6 deterministic enrichment patches to merged constraints.

    Reads constraints_synthesized.json, calls enrich_constraints(), and writes
    constraints_enriched.json.
    """
    run_dir = Path(state.run_dir)
    merged_list = _read_artifact_json(run_dir, "constraints_synthesized.json")

    if not merged_list:
        return PhaseResult(
            phase_name="con_enrich",
            status="error",
            error="constraints_synthesized.json is empty or missing",
        )

    blueprint_path_str = getattr(state, "blueprint_path", "")
    bp = _load_blueprint_yaml(Path(blueprint_path_str)) if blueprint_path_str else {}
    manifest = _get_manifest(state)
    commit_hash = getattr(state, "commit_hash", "") or ""

    from .constraint_enrich import enrich_constraints

    enriched_list, patch_stats = enrich_constraints(
        merged_list,
        bp,
        manifest,
        commit_hash,
    )

    # Write enriched artifact
    artifacts_dir = run_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "constraints_enriched.json").write_text(
        json.dumps(enriched_list, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    summary = f"Enriched {len(enriched_list)} constraints — " + ", ".join(
        f"{k}={v}" for k, v in patch_stats.items()
    )
    logger.info("con_enrich: %s", summary)

    return PhaseResult(
        phase_name="con_enrich",
        status="completed",
        final_text=summary,
    )


# ---------------------------------------------------------------------------
# con_constraint_synthesis handler — Instructor-based kind rebalance
# ---------------------------------------------------------------------------


async def _con_constraint_synthesis_handler(state: AgentState, repo_path: Path) -> PhaseResult:
    """Run Instructor-based kind rebalance on merged constraints."""
    from .constraint_synthesis import run_constraint_synthesis

    agent = state.extra.get("agent")
    if not agent:
        # Fallback: skip synthesis, copy merged → synthesized
        run_dir = Path(state.run_dir)
        merged_path = run_dir / "artifacts" / "constraints_merged.json"
        synth_path = run_dir / "artifacts" / "constraints_synthesized.json"
        if merged_path.exists():
            shutil.copy2(merged_path, synth_path)
        return PhaseResult(
            phase_name="con_constraint_synthesis",
            status="completed",
            final_text="Synthesis skipped (no agent available), copied merged → synthesized",
        )

    run_dir = Path(state.run_dir)
    merged_path = run_dir / "artifacts" / "constraints_merged.json"
    synth_path = run_dir / "artifacts" / "constraints_synthesized.json"

    rebalanced, tokens = await run_constraint_synthesis(agent, merged_path, synth_path)

    return PhaseResult(
        phase_name="con_constraint_synthesis",
        status="completed",
        final_text=f"Synthesis: {rebalanced} constraints rebalanced",
        total_tokens=tokens,
    )


# ---------------------------------------------------------------------------
# con_dedup handler — deterministic deduplication
# ---------------------------------------------------------------------------


async def _con_dedup_handler(state: AgentState, repo_path: Path) -> PhaseResult:
    """Deduplicate enriched constraints using the constraint_pipeline dedup engine.

    Reads constraints_enriched.json, constructs Constraint objects, calls
    dedup_constraints(), and writes constraints_deduped.json.
    """
    run_dir = Path(state.run_dir)
    enriched_list = _read_artifact_json(run_dir, "constraints_enriched.json")

    if not enriched_list:
        return PhaseResult(
            phase_name="con_dedup",
            status="error",
            error="constraints_enriched.json is empty or missing",
        )

    # Lazy imports
    try:
        from doramagic_constraint_pipeline.pipeline import _raw_to_constraint
        from doramagic_constraint_pipeline.refine.dedup import dedup_constraints
    except ImportError as exc:
        return PhaseResult(
            phase_name="con_dedup",
            status="error",
            error=f"Failed to import dedup dependencies: {exc}",
        )

    # Load blueprint for _raw_to_constraint
    blueprint_path_str = getattr(state, "blueprint_path", "")
    if not blueprint_path_str:
        return PhaseResult(
            phase_name="con_dedup",
            status="error",
            error="state.blueprint_path is not set",
        )

    try:
        from doramagic_constraint_pipeline.blueprint_loader import load_blueprint

        blueprint = load_blueprint(Path(blueprint_path_str))
    except (ValueError, KeyError, ImportError) as exc:
        logger.warning("Strict load_blueprint failed (%s), building minimal blueprint", exc)
        blueprint = _build_minimal_parsed_blueprint(
            Path(blueprint_path_str),
            state,
        )

    from doramagic_constraint_schema.types import TargetScope

    # Convert raw dicts → Constraint objects
    constraints = []
    domain = state.domain or "finance"
    errors: list[str] = []

    for i, raw in enumerate(enriched_list):
        constraint_id = f"{domain}-C-{i + 1:03d}"

        # Determine scope
        raw_scope_str = raw.get("target_scope", "global")
        try:
            scope = TargetScope(raw_scope_str)
        except ValueError:
            scope = TargetScope.GLOBAL

        stage_ids = raw.get("stage_ids", [])
        edge_ids = raw.get("edge_ids", [])

        constraint = _raw_to_constraint(
            raw,
            constraint_id,
            blueprint,
            scope,
            stage_ids,
            edge_ids,
        )
        if constraint is not None:
            constraints.append(constraint)
        else:
            errors.append(
                f"Item {i}: _raw_to_constraint returned None for when={raw.get('when', '?')!r}"
            )

    if not constraints:
        return PhaseResult(
            phase_name="con_dedup",
            status="error",
            error=f"No valid constraints after conversion (errors={len(errors)})",
        )

    # Run dedup
    dedup_result = dedup_constraints(constraints)

    # Write deduped artifact as list of dicts
    deduped_dicts = [json.loads(c.model_dump_json()) for c in dedup_result.unique]

    artifacts_dir = run_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "constraints_deduped.json").write_text(
        json.dumps(deduped_dicts, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    summary = (
        f"Dedup: {len(enriched_list)} enriched → {len(constraints)} valid → "
        f"{len(dedup_result.unique)} unique (merged {dedup_result.merged_count})"
    )
    if errors:
        summary += f" conversion_errors={len(errors)}"
    logger.info("con_dedup: %s", summary)

    return PhaseResult(
        phase_name="con_dedup",
        status="completed",
        final_text=summary,
    )


def _build_minimal_parsed_blueprint(
    blueprint_path: Path,
    state: AgentState,
) -> Any:
    """Build a minimal ParsedBlueprint when strict loader fails.

    Mirrors the fallback logic from constraint_phases.py con_ingest.
    """
    from doramagic_constraint_pipeline.blueprint_loader import (
        ParsedBlueprint,
        ParsedEdge,
        ParsedStage,
    )

    bp_raw = _load_blueprint_yaml(blueprint_path)

    stages = [
        ParsedStage(
            id=s.get("id", f"stage_{i}"),
            name=s.get("name", ""),
            order=s.get("order", i),
            responsibility=s.get("responsibility", ""),
            interface=s.get("interface", {}),
            replaceable_points=[],
            pseudocode_example="",
            design_decisions=[],
            acceptance_hints=[],
        )
        for i, s in enumerate(bp_raw.get("stages", []))
    ]

    raw_edges = bp_raw.get("data_flow", {})
    if isinstance(raw_edges, dict):
        raw_edges = raw_edges.get("edges", [])
    edges = []
    for j, e in enumerate(raw_edges if isinstance(raw_edges, list) else []):
        if isinstance(e, dict):
            edges.append(
                ParsedEdge(
                    id=e.get("id", f"edge_{j}"),
                    from_stage=e.get("from", e.get("from_stage", "")),
                    to_stage=e.get("to", e.get("to_stage", "")),
                    data=e.get("data", e.get("label", "")),
                    edge_type=e.get("edge_type", "data_flow"),
                    required=True,
                    condition=None,
                )
            )

    return ParsedBlueprint(
        id=bp_raw.get("id", state.blueprint_id),
        name=bp_raw.get("name", ""),
        domain=state.domain,
        version=bp_raw.get("version", "1.0.0"),
        stages=stages,
        edges=edges,
        global_contracts=[],
        evidence={},
        applicability=bp_raw.get("applicability", {}),
        source=bp_raw.get("source", {}),
        not_suitable_for=[],
        raw=bp_raw,
    )


# ---------------------------------------------------------------------------
# con_ingest handler — JSON → Pydantic validate → JSONL write
# ---------------------------------------------------------------------------


async def _con_ingest_v2_handler(state: AgentState, repo_path: Path) -> PhaseResult:
    """Ingest deduped constraints: validate via Pydantic, write constraints.jsonl.

    Reads from constraints_deduped.json (v2 pipeline) rather than scanning
    multiple artifacts.
    """
    try:
        from doramagic_constraint_schema.types import Constraint
        from doramagic_constraint_schema.validators import validate_constraint
    except ImportError as exc:
        return PhaseResult(
            phase_name="con_ingest",
            status="error",
            error=f"Failed to import constraint schema: {exc}",
        )

    run_dir = Path(state.run_dir)
    deduped_list = _read_artifact_json(run_dir, "constraints_deduped.json")

    if not deduped_list:
        return PhaseResult(
            phase_name="con_ingest",
            status="error",
            error="constraints_deduped.json is empty or missing",
        )

    # Load blueprint to get valid stage/edge IDs for business validation (Fix #5).
    blueprint_path_str = getattr(state, "blueprint_path", "")
    valid_stage_ids: list[str] = []
    valid_edge_ids: list[str] = []
    if blueprint_path_str:
        try:
            from doramagic_constraint_pipeline.blueprint_loader import load_blueprint

            _bp = load_blueprint(Path(blueprint_path_str))
            valid_stage_ids = list(_bp.stage_ids)
            valid_edge_ids = list(_bp.edge_ids)
        except Exception as _bp_exc:
            logger.warning(
                "con_ingest: could not load blueprint for business validation (%s) — "
                "skipping scope/evidence checks",
                _bp_exc,
            )

    # Validate via Pydantic + business rules and collect valid constraints
    valid_dicts: list[dict[str, Any]] = []
    errors: list[str] = []
    by_kind: dict[str, int] = {}

    for item in deduped_list:
        try:
            c = Constraint.model_validate(item)
        except Exception as exc:
            errors.append(f"Pydantic validation failed: {exc} — when={item.get('when', '?')!r}")
            continue

        # Structural invariant: target_scope=edge requires non-empty edge_ids
        if c.applies_to.target_scope.value == "edge" and not c.applies_to.edge_ids:
            errors.append(
                f"target_scope=edge but edge_ids is empty — when={item.get('when', '?')!r}"
            )
            continue

        # Fix #5: SOP Step 3.4 business validation (scope, evidence, fuzzy-words).
        if valid_stage_ids or valid_edge_ids:
            vr = validate_constraint(
                c,
                valid_stage_ids=valid_stage_ids,
                valid_edge_ids=valid_edge_ids,
            )
            if not vr.valid:
                errors.extend(vr.errors)
                logger.warning(
                    "con_ingest: business validation failed for %s: %s",
                    item.get("when", "?"),
                    vr.errors,
                )
                continue

        c_dict = json.loads(c.model_dump_json())
        valid_dicts.append(c_dict)
        kind_val = c_dict.get("constraint_kind", "unknown")
        by_kind[kind_val] = by_kind.get(kind_val, 0) + 1

    if not valid_dicts:
        return PhaseResult(
            phase_name="con_ingest",
            status="error",
            error=f"No valid constraints after Pydantic validation (deduped={len(deduped_list)}, all failed)",
        )

    # Write validated constraints to intermediate artifact (NOT to output dir).
    # con_postprocess is the single output point that calls write_constraints().
    # This avoids the double-write bug where both ingest and postprocess create
    # separate version files with identical content.
    artifacts_dir = run_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    ingest_path = artifacts_dir / "constraints_ingested.json"
    # Use atomic write (tmpfile → fsync → rename) to prevent partial writes on crash
    content = json.dumps(valid_dicts, ensure_ascii=False, indent=2)
    fd, tmp_path = tempfile.mkstemp(dir=str(artifacts_dir), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, str(ingest_path))
    except BaseException:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise

    stats = {
        "deduped_input": len(deduped_list),
        "valid": len(valid_dicts),
        "errors": len(errors),
        "by_kind": by_kind,
        "output_path": str(ingest_path),
    }

    logger.info("con_ingest: %s", stats)
    if errors:
        for err in errors[:10]:
            logger.warning("  ingest error: %s", err)

    return PhaseResult(
        phase_name="con_ingest",
        status="completed",
        final_text=json.dumps(stats, ensure_ascii=False),
    )


# ---------------------------------------------------------------------------
# con_postprocess handler — P0-P5 rules (reused from v1)
# ---------------------------------------------------------------------------


async def _con_postprocess_v2_handler(state: AgentState, repo_path: Path) -> PhaseResult:
    """Apply P0-P5 post-processing rules in-place on the JSONL output.

    Reused logic from constraint_phases.py _con_postprocess_handler.
    """
    try:
        from doramagic_constraint_pipeline.pipeline import _postprocess_constraints
        from doramagic_constraint_schema.types import Constraint
    except ImportError as exc:
        return PhaseResult(
            phase_name="con_postprocess",
            status="error",
            error=f"Failed to import postprocess dependencies: {exc}",
        )

    run_dir_str = getattr(state, "run_dir", None)
    if not run_dir_str:
        return PhaseResult(
            phase_name="con_postprocess",
            status="error",
            error="state.run_dir is not set",
        )

    # Read from con_ingest's intermediate artifact (not LATEST.jsonl)
    run_dir = Path(run_dir_str)
    ingest_path = run_dir / "artifacts" / "constraints_ingested.json"

    # Fallback: try LATEST.jsonl for backward compatibility with older runs
    output_dir_str = getattr(state, "output_dir", "")
    base = Path(output_dir_str) if output_dir_str else run_dir / "output"
    if not ingest_path.exists():
        ingest_path = base / "LATEST.jsonl"
    if not ingest_path.exists():
        ingest_path = base / "constraints.jsonl"
    if not ingest_path.exists():
        return PhaseResult(
            phase_name="con_postprocess",
            status="error",
            error="constraints not found — run con_ingest first",
        )

    # Load constraints (support both JSON array and JSONL formats)
    constraints: list[Constraint] = []
    raw_text = ingest_path.read_text(encoding="utf-8").strip()
    parse_errors = 0

    if raw_text.startswith("["):
        # JSON array format (from con_ingest intermediate artifact)
        for obj in json.loads(raw_text):
            try:
                constraints.append(Constraint.model_validate(obj))
            except Exception as exc:
                logger.warning("Failed to parse constraint: %s", exc)
                parse_errors += 1
    else:
        # JSONL format (legacy)
        for line in raw_text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                constraints.append(Constraint.model_validate(json.loads(line)))
            except Exception as exc:
                logger.warning("Failed to parse constraint line: %s", exc)
                parse_errors += 1

    logger.info(
        "Loaded %d constraints for post-processing (%d parse errors)",
        len(constraints),
        parse_errors,
    )

    # Apply P0-P5 rules in-place
    _postprocess_constraints(constraints)

    # Write final output — this is the SINGLE write_constraints call in the pipeline
    out_dir = Path(output_dir_str) if output_dir_str else run_dir / "output"
    repo_slug = Path(state.repo_path).name if getattr(state, "repo_path", "") else ""
    output_mgr = OutputManager(out_dir, state.blueprint_id, repo_slug=repo_slug)
    dicts = [json.loads(c.model_dump_json()) for c in constraints]
    output_mgr.write_constraints(dicts)

    logger.info("con_postprocess complete: %d constraints written", len(constraints))
    return PhaseResult(
        phase_name="con_postprocess",
        status="completed",
        final_text=f"post_processed={len(constraints)} parse_errors={parse_errors}",
    )


# ---------------------------------------------------------------------------
# con_validate handler — 4 hard gates + 4 warnings
# ---------------------------------------------------------------------------


async def _con_validate_v2_handler(state: AgentState, repo_path: Path) -> PhaseResult:
    """Quality gate: 4 hard checks (QG-01 to QG-04) + 4 warnings (QG-05 to QG-08).

    Hard gates (pipeline halts on failure):
      QG-01: total >= 80
      QG-02: kind_coverage >= 5 (all 5 constraint kinds must be present)
      QG-03: claim_boundary >= 5%
      QG-04: domain_rule + architecture_guardrail >= 50%

    Warnings (logged but non-blocking):
      QG-05: evidence_coverage — % of constraints with file:line in evidence_summary
      QG-06: vt_coverage — % of M-class derived with validation_threshold
      QG-07: derive_count — derived constraints >= expected minimum
      QG-08: needs_threshold_ratio — % of constraints tagged needs_validation_threshold
    """
    run_dir_str = getattr(state, "run_dir", None)
    if not run_dir_str:
        return PhaseResult(
            phase_name="con_validate",
            status="error",
            error="state.run_dir is not set",
        )

    output_dir_str = getattr(state, "output_dir", "")
    base = Path(output_dir_str) if output_dir_str else Path(run_dir_str) / "output"
    output_path = base / "LATEST.jsonl"
    if not output_path.exists():
        output_path = base / "constraints.jsonl"  # legacy fallback

    if not output_path.exists():
        return PhaseResult(
            phase_name="con_validate",
            status="error",
            error=f"constraints not found at {base}",
        )

    # Parse JSONL for analysis
    by_kind: dict[str, int] = {}
    total = 0
    evidence_with_ref = 0
    derived_count = 0
    m_derived_total = 0
    m_derived_with_vt = 0
    p4_residual_count = 0
    fatal_checkable_total = 0
    fatal_checkable_with_vt = 0

    for line in output_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue

        total += 1
        kind = obj.get("constraint_kind", "unknown")
        by_kind[kind] = by_kind.get(kind, 0) + 1

        # QG-05: evidence coverage — check nested confidence.evidence_refs (Pydantic schema).
        confidence = obj.get("confidence", {})
        evidence_refs = confidence.get("evidence_refs", []) if isinstance(confidence, dict) else []
        if evidence_refs:
            evidence_with_ref += 1

        # Derived constraint detection
        if obj.get("derived_from"):
            derived_count += 1
            # M-class derived (from business_decision type M)
            derived_from = obj.get("derived_from", {})
            if isinstance(derived_from, dict):
                # Heuristic: M-class derived tend to have domain_rule/architecture_guardrail
                # and a validation_threshold
                if obj.get("validation_threshold"):
                    m_derived_with_vt += 1
                # Count any derived that has severity=fatal as potential M-class
                severity = obj.get("severity", "")
                if severity == "fatal" and kind in ("domain_rule", "architecture_guardrail"):
                    m_derived_total += 1

        # QG-09: fatal + machine_checkable threshold coverage
        if obj.get("severity") == "fatal" and obj.get("machine_checkable") is True:
            fatal_checkable_total += 1
            if obj.get("validation_threshold"):
                fatal_checkable_with_vt += 1

        # QG-08: P4 residual
        tags = obj.get("tags", [])
        if isinstance(tags, list) and "needs_validation_threshold" in tags:
            p4_residual_count += 1

    # ----- Hard gates (QG-01 to QG-04) -----
    hard_issues: list[str] = []

    # QG-01: total >= 80
    if total < 80:
        hard_issues.append(f"QG-01 FAIL: total={total} < 80")
    else:
        logger.info("QG-01 PASS: total=%d >= 80", total)

    # QG-02: kind_coverage >= 5 (SOP requires all 5 kinds covered).
    # Fix #8: SOP specifies coverage of all 5 kinds, not just 3.
    kind_coverage = len(by_kind)
    if kind_coverage < 5:
        hard_issues.append(
            f"QG-02 FAIL: kind_coverage={kind_coverage} < 5 — kinds: {list(by_kind.keys())}"
        )
    else:
        logger.info("QG-02 PASS: kind_coverage=%d >= 5", kind_coverage)

    # QG-03: claim_boundary >= 5%
    if total > 0:
        cb_count = by_kind.get("claim_boundary", 0)
        cb_pct = cb_count / total * 100
        if cb_pct < 5.0:
            hard_issues.append(f"QG-03 FAIL: claim_boundary={cb_count} ({cb_pct:.1f}%) < 5%")
        else:
            logger.info("QG-03 PASS: claim_boundary=%d (%.1f%%) >= 5%%", cb_count, cb_pct)

    # QG-04: domain_rule + architecture_guardrail >= 50% (lowered from 60% for 6-kind era)
    if total > 0:
        dr_count = by_kind.get("domain_rule", 0)
        ag_count = by_kind.get("architecture_guardrail", 0)
        dr_ag_pct = (dr_count + ag_count) / total * 100
        if dr_ag_pct < 50.0:
            hard_issues.append(f"QG-04 FAIL: dr+ag={dr_count + ag_count} ({dr_ag_pct:.1f}%) < 50%")
        else:
            logger.info("QG-04 PASS: dr+ag=%d (%.1f%%) >= 50%%", dr_count + ag_count, dr_ag_pct)

    # QG-09: fatal + machine_checkable threshold coverage >= 30%
    if fatal_checkable_total > 0:
        fc_vt_pct = fatal_checkable_with_vt / fatal_checkable_total * 100
        if fc_vt_pct < 30.0:
            hard_issues.append(
                f"QG-09 FAIL: fatal_checkable_threshold="
                f"{fatal_checkable_with_vt}/{fatal_checkable_total} "
                f"({fc_vt_pct:.1f}%) < 30%"
            )
        else:
            logger.info(
                "QG-09 PASS: fatal_checkable_threshold=%d/%d (%.1f%%) >= 30%%",
                fatal_checkable_with_vt,
                fatal_checkable_total,
                fc_vt_pct,
            )

    # ----- Warnings (QG-05 to QG-08) -----
    warnings: list[str] = []

    # QG-05: evidence_coverage
    if total > 0:
        ev_pct = evidence_with_ref / total * 100
        if ev_pct < 50.0:
            warnings.append(f"QG-05 WARN: evidence_coverage={ev_pct:.1f}% < 50%")
        else:
            logger.info("QG-05 OK: evidence_coverage=%.1f%%", ev_pct)

    # QG-06: vt_coverage (M-class derived with validation_threshold)
    if m_derived_total > 0:
        vt_pct = m_derived_with_vt / m_derived_total * 100
        if vt_pct < 80.0:
            warnings.append(
                f"QG-06 WARN: vt_coverage={m_derived_with_vt}/{m_derived_total} ({vt_pct:.1f}%) < 80%"
            )
        else:
            logger.info("QG-06 OK: vt_coverage=%.1f%%", vt_pct)

    # QG-07: derive_count
    manifest = _get_manifest(state)
    bd_count = manifest.get("business_decisions_count", 0)
    expected_derived_min = max(bd_count // 3, 5)  # at least 1/3 of BDs or 5
    if derived_count < expected_derived_min:
        warnings.append(
            f"QG-07 WARN: derive_count={derived_count} < expected_min={expected_derived_min} "
            f"(bd_count={bd_count})"
        )
    else:
        logger.info("QG-07 OK: derive_count=%d >= %d", derived_count, expected_derived_min)

    # QG-08: needs_threshold_ratio — % of constraints missing validation_threshold tag.
    # Fix #8: rename to needs_threshold_ratio; describes validation_threshold missing ratio.
    if total > 0:
        needs_threshold_pct = p4_residual_count / total * 100
        if needs_threshold_pct > 10.0:
            warnings.append(
                f"QG-08 WARN: needs_threshold_ratio={p4_residual_count} ({needs_threshold_pct:.1f}%) > 10%"
            )
        else:
            logger.info("QG-08 OK: needs_threshold_ratio=%.1f%%", needs_threshold_pct)

    # Log warnings
    for w in warnings:
        logger.warning("con_validate: %s", w)

    # Build summary
    gate_passed = len(hard_issues) == 0
    summary_parts = [f"total={total} by_kind={by_kind}"]
    if gate_passed:
        summary_parts.append("ALL HARD GATES PASSED")
    else:
        summary_parts.append(f"{len(hard_issues)} hard gate(s) FAILED: {hard_issues}")
    if warnings:
        summary_parts.append(f"{len(warnings)} warning(s): {warnings}")

    summary = " — ".join(summary_parts)
    level = logging.INFO if gate_passed else logging.WARNING
    logger.log(level, "con_validate: %s", summary)

    if not gate_passed:
        return PhaseResult(
            phase_name="con_validate",
            status="error",
            error=summary,
        )

    return PhaseResult(
        phase_name="con_validate",
        status="completed",
        final_text=summary,
    )


# ---------------------------------------------------------------------------
# Phase list factory — build_constraint_phases_v2
# ---------------------------------------------------------------------------


def build_constraint_phases_v2(
    blueprint_id: str,
    blueprint_path: Path,
    agent: ExtractionAgent | None = None,
    *,
    fallback_agent: ExtractionAgent | None = None,
) -> list[Phase]:
    """Build constraint extraction phases for the v2 pipeline (SOP v2.2).

    Architecture:
    - Pre-processing: con_load_context + con_build_manifest (2 Python phases)
    - Parallel extraction: per-stage + edges + global + derive + audit
      (all in parallel_group="extract", depends_on con_build_manifest)
    - Post-processing: con_synthesize → con_enrich → con_dedup → con_ingest
      → con_postprocess → con_validate (6 sequential Python phases)

    Args:
        blueprint_id: Blueprint identifier, e.g. "finance-bp-009".
        blueprint_path: Absolute path to the blueprint YAML file.
        agent: ExtractionAgent for Instructor calls in con_derive and con_audit.
            Injected into state.extra["agent"] via closure. If None, derive
            and audit phases will fail at runtime.
        fallback_agent: Optional fallback ExtractionAgent for derive chunk
            retry when primary model times out.

    Returns:
        Ordered list of Phase objects ready for SOPExecutor.
    """
    # Load blueprint at build time so stage IDs and BD data are available
    bp = _load_blueprint_yaml(blueprint_path)
    stages: list[dict[str, Any]] = bp.get("stages", [])
    business_decisions: list[dict[str, Any]] = bp.get("business_decisions", [])
    audit_summary = bp.get("audit_checklist_summary", {})

    # Check for audit fail items at build time to decide whether to add audit phase.
    # Must mirror the extraction logic in _con_build_manifest_handler.
    has_audit_fail = False
    if isinstance(audit_summary, dict):
        for _category, items in audit_summary.items():
            if _category in ("sop_version", "executed_at", "subdomain_labels"):
                continue
            if _category == "subdomain_checklists" and isinstance(items, list):
                # subdomain items: {name, result: {pass, warn, fail}}
                for subdom in items:
                    if isinstance(subdom, dict):
                        result = subdom.get("result", {})
                        if isinstance(result, dict) and result.get("fail", 0) > 0:
                            has_audit_fail = True
                            break
            elif _category == "critical_findings" and isinstance(items, list):
                # Any critical finding counts as an audit fail item
                if items:
                    has_audit_fail = True
            elif isinstance(items, list):
                for item in items:
                    if isinstance(item, dict) and item.get("fail", 0) > 0:
                        has_audit_fail = True
                        break
            elif isinstance(items, dict) and items.get("fail", 0) > 0:
                has_audit_fail = True
            if has_audit_fail:
                break
    elif isinstance(audit_summary, list):
        for item in audit_summary:
            if isinstance(item, dict) and item.get("fail", 0) > 0:
                has_audit_fail = True
                break
    logger.info(
        "build_constraint_phases_v2: blueprint=%s has_audit_fail=%s",
        blueprint_id,
        has_audit_fail,
    )

    # --- Inject agent into state.extra via a wrapper handler ---
    # The agent must be available in state.extra["agent"] for derive/audit handlers.
    # We wrap the manifest handler to also inject the agent.
    _original_manifest_handler = _con_build_manifest_handler

    async def _manifest_with_agent_injection(
        state: AgentState,
        repo_path: Path,
    ) -> PhaseResult:
        """Wrapper: inject agent into state.extra, then run manifest builder."""
        if agent is not None:
            state.extra["agent"] = agent
        if fallback_agent is not None:
            state.extra["fallback_agent"] = fallback_agent
        return await _original_manifest_handler(state, repo_path)

    phases: list[Phase] = []

    # -----------------------------------------------------------------------
    # Phase 1: con_load_context [Python, blocking]
    # -----------------------------------------------------------------------
    phases.append(
        Phase(
            name="con_load_context",
            description="Step 1: Load blueprint YAML and verify repository path",
            system_prompt="",
            initial_message_builder=lambda s, r: "",
            requires_llm=False,
            python_handler=_con_load_context_handler,
            blocking=True,
        )
    )

    # -----------------------------------------------------------------------
    # Phase 2: con_build_manifest [Python, blocking]
    # -----------------------------------------------------------------------
    phases.append(
        Phase(
            name="con_build_manifest",
            description="Step 1.5: Build deterministic coverage manifest from blueprint YAML",
            system_prompt="",
            initial_message_builder=lambda s, r: "",
            requires_llm=False,
            python_handler=_manifest_with_agent_injection,
            depends_on=["con_load_context"],
            blocking=True,
        )
    )

    # -----------------------------------------------------------------------
    # Phases 3..N+2: con_extract_{stage_id} [Agentic, blocking, parallel_group="extract"]
    # -----------------------------------------------------------------------
    extract_phase_names: list[str] = []
    # Only blocking extract phases are listed here — non-blocking phases (edges,
    # audit) must NOT be in con_synthesize's depends_on because executor.py
    # only accepts status="completed" when checking dependencies.  A failed
    # non-blocking phase would permanently block con_synthesize.
    # Fix #2: track blocking phases separately for con_synthesize depends_on.
    blocking_extract_phase_names: list[str] = []

    for stage in stages:
        stage_id = stage.get("id", "")
        if not stage_id:
            logger.warning("Stage missing 'id' field in blueprint %s — skipping", blueprint_id)
            continue

        phase_name = f"con_extract_{stage_id}"
        extract_phase_names.append(phase_name)
        blocking_extract_phase_names.append(phase_name)  # stage phases are blocking

        phases.append(
            Phase(
                name=phase_name,
                description=f"Step 2.1: Extract 5-kind constraints for stage {stage_id}",
                system_prompt=prompts_v2.CON_STAGE_V2_SYSTEM,
                initial_message_builder=_build_stage_extract_message_v2(stage, bp, blueprint_path),
                allowed_tools=[
                    "read_file",
                    "grep_codebase",
                    "list_dir",
                    "write_artifact",
                    "get_artifact",
                    "get_skeleton",
                ],
                max_iterations=60,
                required_artifacts=[f"constraints_{stage_id}.json"],
                depends_on=["con_build_manifest"],
                blocking=True,
                parallel_group="extract",
            )
        )

    # -----------------------------------------------------------------------
    # Phase N+3: con_extract_edges [Agentic, non-blocking, parallel_group="extract"]
    # -----------------------------------------------------------------------
    # Non-blocking: tracked in extract_phase_names for logging only,
    # NOT added to blocking_extract_phase_names (Fix #2).
    extract_phase_names.append("con_extract_edges")
    phases.append(
        Phase(
            name="con_extract_edges",
            description="Step 2.1: Extract cross-stage edge constraints",
            system_prompt=prompts_v2.CON_EDGE_V2_SYSTEM,
            initial_message_builder=_build_edges_extract_message_v2(bp, blueprint_path),
            allowed_tools=[
                "read_file",
                "grep_codebase",
                "list_dir",
                "write_artifact",
                "get_artifact",
                "get_skeleton",
            ],
            max_iterations=60,
            required_artifacts=["constraints_edges.json"],
            depends_on=["con_build_manifest"],
            blocking=False,
            parallel_group="extract",
        )
    )

    # -----------------------------------------------------------------------
    # Phase N+4: con_extract_global [Agentic, blocking, parallel_group="extract"]
    # -----------------------------------------------------------------------
    extract_phase_names.append("con_extract_global")
    blocking_extract_phase_names.append("con_extract_global")
    phases.append(
        Phase(
            name="con_extract_global",
            description="Step 2.1+2.3: Extract global and claim_boundary constraints",
            system_prompt=prompts_v2.CON_GLOBAL_V2_SYSTEM,
            initial_message_builder=_build_global_extract_message_v2(bp, blueprint_path),
            allowed_tools=[
                "read_file",
                "grep_codebase",
                "list_dir",
                "write_artifact",
                "get_artifact",
                "get_skeleton",
            ],
            max_iterations=60,
            required_artifacts=["constraints_global.json"],
            depends_on=["con_build_manifest"],
            blocking=True,
            parallel_group="extract",
        )
    )

    # -----------------------------------------------------------------------
    # Phase N+5: con_derive [Python+Instructor, blocking, parallel_group="extract"]
    # -----------------------------------------------------------------------
    derive_phase_name: str | None = None
    if business_decisions:
        derive_phase_name = "con_derive"
        extract_phase_names.append(derive_phase_name)
        blocking_extract_phase_names.append(derive_phase_name)

        # Closure wrapper ensures agents are injected every run (survives resume)
        async def _derive_with_agent_injection(
            state: AgentState,
            repo_path: Path,
            _agent: Any = agent,
            _fb_agent: Any = fallback_agent,
        ) -> PhaseResult:
            if _agent is not None:
                state.extra["agent"] = _agent
            if _fb_agent is not None:
                state.extra["fallback_agent"] = _fb_agent
            return await _con_derive_v2_handler(state, repo_path)

        phases.append(
            Phase(
                name="con_derive",
                description="Step 2.4: Derive constraints from business_decisions (RC/BA/M/B/missing)",
                system_prompt="",
                initial_message_builder=lambda s, r: "",
                requires_llm=False,
                python_handler=_derive_with_agent_injection,
                depends_on=["con_build_manifest"],
                blocking=False,
                parallel_group="extract",
            )
        )
    else:
        logger.info(
            "Blueprint %s has no business_decisions — skipping con_derive phase",
            blueprint_id,
        )

    # -----------------------------------------------------------------------
    # Phase N+6: con_audit [Python+Instructor, non-blocking, parallel_group="extract"]
    # -----------------------------------------------------------------------
    audit_phase_name: str | None = None
    if has_audit_fail:
        audit_phase_name = "con_audit"
        # Non-blocking: tracked in extract_phase_names for logging only,
        # NOT added to blocking_extract_phase_names (Fix #2).
        extract_phase_names.append(audit_phase_name)

        async def _audit_with_agent_injection(
            state: AgentState,
            repo_path: Path,
            _agent: Any = agent,
        ) -> PhaseResult:
            if _agent is not None:
                state.extra["agent"] = _agent
            return await _con_audit_v2_handler(state, repo_path)

        phases.append(
            Phase(
                name="con_audit",
                description="Step 2.5: Convert audit-checklist fail findings to constraints",
                system_prompt="",
                initial_message_builder=lambda s, r: "",
                requires_llm=False,
                python_handler=_audit_with_agent_injection,
                depends_on=["con_build_manifest"],
                blocking=False,
                parallel_group="extract",
            )
        )
    else:
        logger.info(
            "Blueprint %s has no audit fail items — skipping con_audit phase",
            blueprint_id,
        )

    # -----------------------------------------------------------------------
    # Phase: con_extract_resources [Python, non-blocking, parallel_group="extract"]
    # Produces resources.json for crystal compiler
    # -----------------------------------------------------------------------
    phases.append(
        Phase(
            name="con_extract_resources",
            description="Extract resource inventory (dependencies, APIs, infrastructure)",
            system_prompt="",
            initial_message_builder=lambda s, r: "",
            requires_llm=False,
            python_handler=_con_extract_resources_handler,
            depends_on=["con_build_manifest"],
            blocking=False,
            parallel_group="extract",
        )
    )

    # -----------------------------------------------------------------------
    # Phase N+7: con_merge [Python, blocking]
    # Fix #2: depends_on only blocking phases — non-blocking phases (edges,
    # audit) are read fault-tolerantly by _con_synthesize_handler itself.
    # -----------------------------------------------------------------------
    phases.append(
        Phase(
            name="con_merge",
            description="Merge all constraints_*.json artifacts into constraints_merged.json",
            system_prompt="",
            initial_message_builder=lambda s, r: "",
            requires_llm=False,
            python_handler=_con_synthesize_handler,  # 复用现有 handler，改名
            depends_on=blocking_extract_phase_names,  # 复用现有依赖
        )
    )

    # -----------------------------------------------------------------------
    # Phase N+7.5: con_constraint_synthesis [Python+Instructor, blocking]
    # -----------------------------------------------------------------------
    phases.append(
        Phase(
            name="con_constraint_synthesis",
            description="Instructor-based kind rebalance (P3: structured synthesis)",
            system_prompt="",
            initial_message_builder=lambda s, r: "",
            requires_llm=False,
            python_handler=_con_constraint_synthesis_handler,
            depends_on=["con_merge"],
        )
    )

    # -----------------------------------------------------------------------
    # Phase N+8: con_enrich [Python, blocking]
    # -----------------------------------------------------------------------
    phases.append(
        Phase(
            name="con_enrich",
            description="Apply 6 deterministic enrichment patches",
            system_prompt="",
            initial_message_builder=lambda s, r: "",
            requires_llm=False,
            python_handler=_con_enrich_handler,
            depends_on=["con_constraint_synthesis"],
            blocking=True,
        )
    )

    # -----------------------------------------------------------------------
    # Phase N+9: con_dedup [Python, blocking]
    # -----------------------------------------------------------------------
    phases.append(
        Phase(
            name="con_dedup",
            description="Deduplicate enriched constraints via signature matching",
            system_prompt="",
            initial_message_builder=lambda s, r: "",
            requires_llm=False,
            python_handler=_con_dedup_handler,
            depends_on=["con_enrich"],
            blocking=True,
        )
    )

    # -----------------------------------------------------------------------
    # Phase N+10: con_ingest [Python, blocking]
    # -----------------------------------------------------------------------
    phases.append(
        Phase(
            name="con_ingest",
            description="Pydantic validate deduped constraints and write constraints.jsonl",
            system_prompt="",
            initial_message_builder=lambda s, r: "",
            requires_llm=False,
            python_handler=_con_ingest_v2_handler,
            depends_on=["con_dedup"],
            blocking=True,
        )
    )

    # -----------------------------------------------------------------------
    # Phase N+11: con_postprocess [Python, blocking]
    # -----------------------------------------------------------------------
    phases.append(
        Phase(
            name="con_postprocess",
            description="Apply P0-P5 post-processing rules to constraints.jsonl",
            system_prompt="",
            initial_message_builder=lambda s, r: "",
            requires_llm=False,
            python_handler=_con_postprocess_v2_handler,
            depends_on=["con_ingest"],
            blocking=True,
        )
    )

    # -----------------------------------------------------------------------
    # Phase N+12: con_validate [Python, blocking]
    # -----------------------------------------------------------------------
    phases.append(
        Phase(
            name="con_validate",
            description=(
                "Quality gate: QG-01..04 hard gates (kind_coverage>=5) + QG-05..08 warnings"
            ),
            system_prompt="",
            initial_message_builder=lambda s, r: "",
            requires_llm=False,
            python_handler=_con_validate_v2_handler,
            depends_on=["con_postprocess"],
            blocking=True,
        )
    )

    logger.info(
        "build_constraint_phases_v2: %d phases for %s "
        "(%d stages, %d extract phases, derive=%s, audit=%s)",
        len(phases),
        blueprint_id,
        len(stages),
        len(extract_phase_names),
        derive_phase_name is not None,
        audit_phase_name is not None,
    )

    return phases
