"""Constraint extraction phases — SOP v2.2 mapping.

Maps each SOP v2.2 step to a Phase object consumed by the SOPExecutor.

Pure-Python phases: con_load_context, con_ingest, con_postprocess, con_validate.
Agentic phases: con_extract_{stage_id} (one per stage), con_extract_edges,
                con_extract_global, con_derive.

Key design decisions:
- Agentic phases receive stage/edge/global definitions in the user message and
  explore source code via read_file / grep_codebase tools.
- Ingest phase collects all constraint JSON artifacts, parses them via the
  constraint_pipeline helpers, and writes constraints.jsonl via OutputManager.
- Output goes to _runs/{bp_id}/output/constraints.jsonl — no merge into global
  knowledge/constraints/domains/finance.jsonl.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import yaml

from ..core.agent_loop import PhaseResult
from ..sop.executor import Phase
from ..state.output import OutputManager
from ..state.schema import AgentState
from . import prompts

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

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Pure-Python phase handlers
# ---------------------------------------------------------------------------


async def _con_load_context_handler(state: AgentState, repo_path: Path) -> PhaseResult:
    """Step 1: Load blueprint YAML and validate the repo path exists."""
    # Blueprint path must be stored on state before this phase runs.
    # The caller (e.g. constraint extraction CLI) sets state.blueprint_path.
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
    # Handle data_flow as dict with nested edges, or directly as a list.
    _data_flow = bp.get("data_flow", {})
    if isinstance(_data_flow, dict):
        _edges = _data_flow.get("edges", [])
    elif isinstance(_data_flow, list):
        _edges = _data_flow
    else:
        _edges = []
    n_edges = len([e for e in _edges if isinstance(e, dict)])
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


async def _con_ingest_handler(state: AgentState, repo_path: Path) -> PhaseResult:
    """Step 3: Collect all constraint JSON artifacts, validate, and write JSONL.

    Reads constraint artifacts produced by agentic phases, validates each raw
    dict via _validate_raw_fields and _raw_to_constraint from constraint_pipeline,
    then writes validated constraints to output/constraints.jsonl.
    """
    # Lazy import to avoid hard dependency at module load time
    from doramagic_constraint_pipeline.blueprint_loader import load_blueprint
    from doramagic_constraint_pipeline.pipeline import (
        _raw_to_constraint,
        _validate_raw_fields,
    )
    from doramagic_constraint_schema.types import TargetScope
    from doramagic_constraint_schema.validators import validate_constraint

    blueprint_path_str = getattr(state, "blueprint_path", None)
    if not blueprint_path_str:
        return PhaseResult(
            phase_name="con_ingest",
            status="error",
            error="state.blueprint_path is not set",
        )

    run_dir_str = getattr(state, "run_dir", None)
    if not run_dir_str:
        return PhaseResult(
            phase_name="con_ingest",
            status="error",
            error="state.run_dir is not set — cannot locate artifacts",
        )

    run_dir = Path(run_dir_str)
    blueprint_path = Path(blueprint_path_str)

    # Use a tolerant loader — agent-generated YAMLs may not match the strict
    # ParsedBlueprint schema (e.g. edges without 'id' field).  We only need
    # blueprint_id, domain, stage_ids, and edge_ids for _raw_to_constraint.
    try:
        blueprint = load_blueprint(blueprint_path)
    except (ValueError, KeyError) as e:
        logger.warning("Strict load_blueprint failed (%s), falling back to minimal loader", e)
        bp_raw_fallback = _load_blueprint_yaml(blueprint_path)
        from doramagic_constraint_pipeline.blueprint_loader import (
            ParsedBlueprint,
            ParsedEdge,
            ParsedStage,
        )

        stages_fb = [
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
            for i, s in enumerate(bp_raw_fallback.get("stages", []))
        ]
        # Build edges tolerantly — generate id if missing
        raw_edges = bp_raw_fallback.get("data_flow", {})
        if isinstance(raw_edges, dict):
            raw_edges = raw_edges.get("edges", [])
        edges_fb = []
        for j, e in enumerate(raw_edges if isinstance(raw_edges, list) else []):
            if isinstance(e, dict):
                edges_fb.append(
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
        blueprint = ParsedBlueprint(
            id=bp_raw_fallback.get("id", state.blueprint_id),
            name=bp_raw_fallback.get("name", ""),
            domain=state.domain,  # always use state.domain (string), not blueprint's (may be list)
            version=bp_raw_fallback.get("version", "1.0.0"),
            stages=stages_fb,
            edges=edges_fb,
            global_contracts=[],
            evidence={},
            applicability=bp_raw_fallback.get("applicability", {}),
            source=bp_raw_fallback.get("source", {}),
            not_suitable_for=[],
            raw=bp_raw_fallback,
        )

    # Collect artifact names to ingest.
    # Per-stage artifacts: constraints_{stage_id}.json
    bp_raw = _load_blueprint_yaml(blueprint_path)
    stages = bp_raw.get("stages", [])
    artifact_names: list[tuple[str, TargetScope, list[str], list[str]]] = []

    for stage in stages:
        stage_id = stage.get("id", "")
        if stage_id:
            artifact_names.append(
                (f"constraints_{stage_id}.json", TargetScope.STAGE, [stage_id], [])
            )

    # Edge artifact
    artifact_names.append(("constraints_edges.json", TargetScope.EDGE, [], []))

    # Global artifact
    artifact_names.append(("constraints_global.json", TargetScope.GLOBAL, [], []))

    # Derived artifact
    artifact_names.append(("constraints_derived.json", TargetScope.GLOBAL, [], []))

    # Process all artifacts
    domain = state.domain or "finance"
    valid_constraints_dicts: list[dict] = []
    errors: list[str] = []
    total_raw = 0
    by_kind: dict[str, int] = {}

    constraint_counter = 1

    for artifact_name, target_scope, stage_ids, edge_ids in artifact_names:
        raw_list = _read_artifact_json(run_dir, artifact_name)
        if not raw_list:
            logger.debug("No constraints in artifact: %s", artifact_name)
            continue

        logger.info("Ingesting %d raw constraints from %s", len(raw_list), artifact_name)
        total_raw += len(raw_list)

        # Special handling for derived constraints — they may lack evidence_summary
        if artifact_name == "constraints_derived.json":
            for raw in raw_list:
                if raw.get("derived_from") and not raw.get("evidence_summary"):
                    raw["source_type"] = "expert_reasoning"
                    raw["confidence_score"] = min(raw.get("confidence_score", 0.7), 0.7)

        # Fix 5: Build edge lookup from blueprint edges for accurate id inference
        edge_lookup: dict[tuple[str, str], str] = {}
        for e in blueprint.edges:
            key = (e.from_stage, e.to_stage)
            edge_lookup[key] = e.id

        # Fix edge constraints with empty edge_ids before validation
        for raw in raw_list:
            if raw.get("target_scope") == "edge" and not raw.get("edge_ids"):
                stage_ids_raw = raw.get("stage_ids", [])
                if len(stage_ids_raw) >= 2:
                    key = (stage_ids_raw[0], stage_ids_raw[1])
                    if key in edge_lookup:
                        raw["edge_ids"] = [edge_lookup[key]]
                    else:
                        # Can't map to a known edge — demote to stage scope
                        raw["target_scope"] = "stage"
                else:
                    # Fall back to stage scope if no edge info available
                    raw["target_scope"] = "stage"

        for raw in raw_list:
            if not isinstance(raw, dict):
                errors.append(f"{artifact_name}: expected dict, got {type(raw).__name__}")
                continue

            # Determine scope from raw if present, else fall back to artifact scope
            raw_scope_str = raw.get("target_scope", "")
            effective_scope = target_scope
            effective_stage_ids = stage_ids
            effective_edge_ids = edge_ids
            if raw_scope_str:
                try:
                    effective_scope = TargetScope(raw_scope_str)
                    effective_stage_ids = raw.get("stage_ids", stage_ids)
                    effective_edge_ids = raw.get("edge_ids", edge_ids)
                except ValueError:
                    pass  # keep the artifact-level default

            # Validate required fields
            missing = _validate_raw_fields(raw)
            if missing:
                errors.append(
                    f"{artifact_name}: missing fields {missing} — when={raw.get('when', '?')!r}"
                )
                continue

            constraint_id = f"{domain}-C-{constraint_counter:03d}"
            constraint = _raw_to_constraint(
                raw,
                constraint_id,
                blueprint,
                effective_scope,
                effective_stage_ids,
                effective_edge_ids,
            )
            if constraint is None:
                errors.append(
                    f"{artifact_name}: _raw_to_constraint returned None for {raw.get('when', '?')!r}"
                )
                continue

            vr = validate_constraint(
                constraint,
                valid_stage_ids=blueprint.stage_ids,
                valid_edge_ids=blueprint.edge_ids,
            )
            if not vr.valid:
                errors.extend(vr.errors)
                logger.warning("Constraint validation failed %s: %s", constraint_id, vr.errors)
                continue

            # Serialize to dict for storage
            constraint_dict = json.loads(constraint.model_dump_json())
            valid_constraints_dicts.append(constraint_dict)
            kind_val = raw.get("constraint_kind", "domain_rule")
            by_kind[kind_val] = by_kind.get(kind_val, 0) + 1
            constraint_counter += 1

    # Fix 1a: Fail fast if no valid constraints were produced
    if len(valid_constraints_dicts) == 0:
        return PhaseResult(
            phase_name="con_ingest",
            status="error",
            error=f"No valid constraints produced (total_raw={total_raw}, all failed validation)",
        )

    # Write to output dir — derive repo_slug to match bp_finalize naming
    out_dir = Path(state.output_dir) if getattr(state, "output_dir", "") else run_dir / "output"
    repo_slug = Path(state.repo_path).name if getattr(state, "repo_path", "") else ""
    output_mgr = OutputManager(out_dir, state.blueprint_id, repo_slug=repo_slug)
    output_path = output_mgr.write_constraints(valid_constraints_dicts)

    stats_detail = (
        f"total_raw={total_raw} valid={len(valid_constraints_dicts)} "
        f"errors={len(errors)} by_kind={by_kind} output={output_path}"
    )
    logger.info("con_ingest complete: %s", stats_detail)
    if errors:
        for err in errors[:10]:
            logger.warning("  ingest error: %s", err)

    # Store stats on state for use by con_validate
    # Use a simple attribute for inter-phase communication
    # (AgentState is a Pydantic model; we rely on model_extra or a dedicated field if available)
    # Store as a JSON string in transition_reason-compatible location via PhaseResult
    stats = {
        "total_raw": total_raw,
        "valid": len(valid_constraints_dicts),
        "errors": len(errors),
        "by_kind": by_kind,
        "output_path": str(output_path),
    }

    return PhaseResult(
        phase_name="con_ingest",
        status="completed",
        final_text=json.dumps(stats, ensure_ascii=False),
    )


async def _con_postprocess_handler(state: AgentState, repo_path: Path) -> PhaseResult:
    """Step 4: Apply P0-P5 post-processing rules in-place on the JSONL output."""
    from doramagic_constraint_pipeline.pipeline import _postprocess_constraints
    from doramagic_constraint_schema.types import Constraint

    run_dir_str = getattr(state, "run_dir", None)
    if not run_dir_str:
        return PhaseResult(
            phase_name="con_postprocess",
            status="error",
            error="state.run_dir is not set",
        )

    # Find constraints file — prefer LATEST.jsonl (v6 naming), fall back to constraints.jsonl
    output_dir_str = getattr(state, "output_dir", "")
    base = Path(output_dir_str) if output_dir_str else Path(run_dir_str) / "output"
    output_path = base / "LATEST.jsonl"
    if not output_path.exists():
        output_path = base / "constraints.jsonl"  # legacy fallback
    if not output_path.exists():
        return PhaseResult(
            phase_name="con_postprocess",
            status="error",
            error=f"constraints not found at {base} — run con_ingest first",
        )

    # Load constraints from JSONL
    constraints: list[Constraint] = []
    raw_lines: list[str] = output_path.read_text(encoding="utf-8").splitlines()
    parse_errors = 0
    for line in raw_lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            c = Constraint.model_validate(obj)
            constraints.append(c)
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

    # Write back to output dir — derive repo_slug to match bp_finalize / con_ingest naming
    out_dir_pp = Path(output_dir_str) if output_dir_str else Path(run_dir_str) / "output"
    repo_slug = Path(state.repo_path).name if getattr(state, "repo_path", "") else ""
    output_mgr = OutputManager(out_dir_pp, state.blueprint_id, repo_slug=repo_slug)
    dicts = [json.loads(c.model_dump_json()) for c in constraints]
    output_mgr.write_constraints(dicts)

    logger.info("con_postprocess complete: %d constraints rewritten", len(constraints))
    return PhaseResult(
        phase_name="con_postprocess",
        status="completed",
        final_text=f"post_processed={len(constraints)} parse_errors={parse_errors}",
    )


async def _con_validate_handler(state: AgentState, repo_path: Path) -> PhaseResult:
    """Step 5: Quality gate — check totals, kind coverage, claim_boundary %, dr+ag %.

    Checks:
    - total >= 80
    - kind_coverage >= 3 (distinct constraint_kind values present)
    - claim_boundary >= 5% of total
    - domain_rule + architecture_guardrail >= 60% of total
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

    # Count by kind
    by_kind: dict[str, int] = {}
    total = 0
    for line in output_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            kind = obj.get("constraint_kind", "unknown")
            by_kind[kind] = by_kind.get(kind, 0) + 1
            total += 1
        except json.JSONDecodeError:
            continue

    issues: list[str] = []

    # Check 1: total >= 80
    if total < 80:
        issues.append(f"FAIL total={total} < 80 (minimum threshold)")
    else:
        logger.info("QG total: %d >= 80 PASS", total)

    # Check 2: kind_coverage >= 3
    kind_coverage = len(by_kind)
    if kind_coverage < 3:
        issues.append(
            f"FAIL kind_coverage={kind_coverage} < 3 — kinds present: {list(by_kind.keys())}"
        )
    else:
        logger.info("QG kind_coverage: %d >= 3 PASS", kind_coverage)

    # Check 3: claim_boundary >= 5% of total
    if total > 0:
        cb_count = by_kind.get("claim_boundary", 0)
        cb_pct = cb_count / total * 100
        if cb_pct < 5.0:
            issues.append(f"FAIL claim_boundary={cb_count} ({cb_pct:.1f}%) < 5%")
        else:
            logger.info("QG claim_boundary: %d (%.1f%%) >= 5%% PASS", cb_count, cb_pct)

    # Check 4: domain_rule + architecture_guardrail >= 60% of total
    if total > 0:
        dr_count = by_kind.get("domain_rule", 0)
        ag_count = by_kind.get("architecture_guardrail", 0)
        dr_ag_pct = (dr_count + ag_count) / total * 100
        if dr_ag_pct < 60.0:
            issues.append(
                f"FAIL domain_rule+architecture_guardrail={dr_count + ag_count} "
                f"({dr_ag_pct:.1f}%) < 60%"
            )
        else:
            logger.info(
                "QG dr+ag: %d (%.1f%%) >= 60%% PASS",
                dr_count + ag_count,
                dr_ag_pct,
            )

    gate_passed = len(issues) == 0
    summary = f"total={total} by_kind={by_kind} — " + (
        "ALL QUALITY CHECKS PASSED" if gate_passed else f"{len(issues)} issue(s): {issues}"
    )

    level = logging.INFO if gate_passed else logging.WARNING
    logger.log(level, "con_validate: %s", summary)

    # Fix 1b: Return error status when any quality gate fails
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
# Initial message builders (agentic phases)
# ---------------------------------------------------------------------------


def _build_stage_extract_message(
    stage: dict[str, Any],
    blueprint_path: Path,
    blueprint: dict[str, Any],
) -> callable:
    """Return an initial_message_builder closure for a single stage extraction phase."""
    stage_id = stage.get("id", "unknown")

    def builder(state: AgentState, repo_path: Path) -> str:
        stage_block = _format_stage_for_message(stage)
        bp_id = blueprint.get("id", "unknown")
        bp_name = blueprint.get("name", "")

        # Collect evidence refs from stage design_decisions for source hints
        evidence_refs: list[str] = []
        for dd in stage.get("design_decisions", []):
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

        return (
            f"Blueprint: {bp_id} — {bp_name}\n"
            f"Repository: {repo_path}\n"
            f"Blueprint file: {blueprint_path}\n"
            f"{evidence_hint}\n\n"
            f"## Stage to Extract Constraints For\n\n"
            f"{stage_block}\n\n"
            f"## Instructions\n\n"
            f"1. Read the stage definition above carefully.\n"
            f"2. Use read_file and grep_codebase to locate and examine source files "
            f"referenced in the blueprint (evidence refs, interface inputs/outputs, "
            f"design_decisions).\n"
            f"3. Extract ALL constraints for this stage across all 5 kinds: "
            f"domain_rule, resource_boundary, operational_lesson, architecture_guardrail, "
            f"claim_boundary.\n"
            f"4. For each kind, follow the KIND_GUIDANCE in your system prompt.\n"
            f"5. When done, call write_artifact(name='constraints_{stage_id}.json') "
            f"with a JSON array of constraint objects.\n"
        )

    return builder


def _build_edges_extract_message(
    blueprint: dict[str, Any],
    blueprint_path: Path,
) -> callable:
    """Return an initial_message_builder for the edge constraints phase."""

    def builder(state: AgentState, repo_path: Path) -> str:
        bp_id = blueprint.get("id", "unknown")
        bp_name = blueprint.get("name", "")
        # Handle data_flow as dict with nested edges, or directly as a list.
        data_flow = blueprint.get("data_flow", {})
        if isinstance(data_flow, dict):
            edges = data_flow.get("edges", [])
        elif isinstance(data_flow, list):
            edges = data_flow
        else:
            edges = []
        # Filter to well-formed edge dicts only.
        edges = [e for e in edges if isinstance(e, dict)]

        edges_block = (
            yaml.dump(edges, allow_unicode=True, default_flow_style=False)
            if edges
            else "(no edges defined)"
        )

        # Build a quick stage name lookup
        stage_names = {s.get("id", ""): s.get("name", "") for s in blueprint.get("stages", [])}

        return (
            f"Blueprint: {bp_id} — {bp_name}\n"
            f"Repository: {repo_path}\n"
            f"Blueprint file: {blueprint_path}\n\n"
            f"## Data Flow Edges\n\n"
            f"{edges_block}\n\n"
            f"## Stage Names Reference\n"
            + "\n".join(f"  {sid}: {sname}" for sid, sname in stage_names.items())
            + "\n\n"
            "## Instructions\n\n"
            "1. For each edge, identify the upstream and downstream stages.\n"
            "2. Use read_file and grep_codebase to examine how data flows between stages.\n"
            "3. Extract cross-stage constraints: data format constraints, ordering/timing "
            "constraints, data integrity constraints, type conversion constraints.\n"
            "4. target_scope must be 'edge'; populate edge_ids with the edge ID.\n"
            "5. When done, call write_artifact(name='constraints_edges.json') "
            "with a JSON array of constraint objects.\n"
        )

    return builder


def _build_global_extract_message(
    blueprint: dict[str, Any],
    blueprint_path: Path,
) -> callable:
    """Return an initial_message_builder for the global constraints phase."""

    def builder(state: AgentState, repo_path: Path) -> str:
        bp_id = blueprint.get("id", "unknown")
        bp_name = blueprint.get("name", "")
        global_contracts = blueprint.get("global_contracts", [])
        applicability = blueprint.get("applicability", {})
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
            f"Blueprint: {bp_id} — {bp_name}\n"
            f"Repository: {repo_path}\n"
            f"Blueprint file: {blueprint_path}\n\n"
            f"## Global Contracts\n\n"
            f"{global_block}\n\n"
            f"## Applicability\n\n"
            f"Description: {description}\n\n"
            f"## Not Suitable For\n\n"
            f"{nsf_block}\n\n"
            f"## Instructions\n\n"
            f"1. Read the global_contracts section above.\n"
            f"2. Use read_file to examine the project README and top-level package "
            f"files for global invariants, capability claims, and system-wide rules.\n"
            f"3. Extract:\n"
            f"   a. Global invariants (cross-stage constraints with target_scope='global')\n"
            f"   b. System-level capability boundaries (resource_boundary)\n"
            f"   c. Global architectural conventions (architecture_guardrail)\n"
            f"   d. claim_boundary constraints (what users MUST NOT claim this system can do)\n"
            f"      Include both code-backed claims and expert_reasoning-based claims.\n"
            f"4. When done, call write_artifact(name='constraints_global.json') "
            f"with a JSON array of constraint objects.\n"
        )

    return builder


def _build_derive_message(
    blueprint: dict[str, Any],
    blueprint_path: Path,
) -> callable:
    """Return an initial_message_builder for the business-decision derivation phase."""

    def builder(state: AgentState, repo_path: Path) -> str:
        bp_id = blueprint.get("id", "unknown")
        bp_name = blueprint.get("name", "")
        business_decisions = blueprint.get("business_decisions", [])
        bds_json = json.dumps(business_decisions, ensure_ascii=False, indent=2)

        return (
            f"Blueprint: {bp_id} — {bp_name}\n"
            f"Blueprint file: {blueprint_path}\n\n"
            f"## Business Decisions (use directly — do not re-read the file)\n\n"
            f"```json\n{bds_json}\n```\n\n"
            f"## Instructions\n\n"
            f"Derive constraints from the business_decisions above following the "
            f"SOP v2.2 Step 2.4 derivation rules in your system prompt.\n\n"
            f"Derivation rules summary:\n"
            f"  - RC → domain_rule, modality=must/must_not, severity=fatal\n"
            f"  - BA → operational_lesson, modality=should, severity=medium/high\n"
            f"  - M  → domain_rule or architecture_guardrail, modality=must/must_not\n"
            f"  - B  → domain_rule or architecture_guardrail (only if affects trading "
            f"behaviour or data semantics)\n"
            f"  - missing (status=missing) → 2 constraints: claim_boundary + domain_rule/operational_lesson\n"
            f"  - T, DK (non-trading) → skip\n\n"
            f"Every derived constraint must include a derived_from field with:\n"
            f"  blueprint_id, business_decision_id, derivation_version='sop-v2.2'\n\n"
            f"When done, call write_artifact(name='constraints_derived.json') "
            f"with a JSON array of constraint objects.\n"
        )

    return builder


# ---------------------------------------------------------------------------
# Phase list factory
# ---------------------------------------------------------------------------


def build_constraint_phases(blueprint_id: str, blueprint_path: Path) -> list[Phase]:
    """Build constraint extraction phases for a given blueprint (SOP v2.2).

    Generates one agentic phase per stage in the blueprint, plus shared
    phases for edges, global/claim_boundary, BD derivation, ingest,
    post-processing, and quality validation.

    Args:
        blueprint_id: Blueprint identifier, e.g. ``"finance-bp-009"``.
        blueprint_path: Absolute path to the blueprint YAML file.

    Returns:
        Ordered list of :class:`~doramagic_extraction_agent.sop.executor.Phase`
        objects ready to be handed to the ``SOPExecutor``.
    """
    # Load blueprint at phase-build time so stage IDs and BD data are available.
    bp = _load_blueprint_yaml(blueprint_path)
    stages: list[dict[str, Any]] = bp.get("stages", [])
    business_decisions: list[dict[str, Any]] = bp.get("business_decisions", [])

    phases: list[Phase] = []

    # -----------------------------------------------------------------------
    # Phase 1: Load context (pure Python)
    # -----------------------------------------------------------------------
    phases.append(
        Phase(
            name="con_load_context",
            description="Step 1: Load blueprint YAML and verify repository path",
            system_prompt="",
            initial_message_builder=lambda s, r: "",
            requires_llm=False,
            python_handler=_con_load_context_handler,
        )
    )

    # -----------------------------------------------------------------------
    # Phase 2: Per-stage constraint extraction (agentic, one phase per stage)
    # Steps 2.1-2.3: extract 5 kinds per stage
    # -----------------------------------------------------------------------
    stage_phase_names: list[str] = []
    for stage in stages:
        stage_id = stage.get("id", "")
        if not stage_id:
            logger.warning("Stage missing 'id' field in blueprint %s — skipping", blueprint_id)
            continue

        phase_name = f"con_extract_{stage_id}"
        stage_phase_names.append(phase_name)

        phases.append(
            Phase(
                name=phase_name,
                description=f"Step 2.1-2.3: Extract 5-kind constraints for stage {stage_id}",
                system_prompt=prompts.CON_STAGE_SYSTEM,
                initial_message_builder=_build_stage_extract_message(stage, blueprint_path, bp),
                allowed_tools=[
                    "read_file",
                    "grep_codebase",
                    "list_dir",
                    "write_artifact",
                    "get_artifact",
                ],
                # 5 kinds × ~20 iterations each
                max_iterations=100,
                depends_on=["con_load_context"],
            )
        )

    # -----------------------------------------------------------------------
    # Phase 3: Edge constraint extraction (agentic)
    # -----------------------------------------------------------------------
    phases.append(
        Phase(
            name="con_extract_edges",
            description="Step 2.1-2.3: Extract cross-stage edge constraints for all data flow edges",
            system_prompt=prompts.CON_EDGE_SYSTEM,
            initial_message_builder=_build_edges_extract_message(bp, blueprint_path),
            allowed_tools=[
                "read_file",
                "grep_codebase",
                "list_dir",
                "write_artifact",
                "get_artifact",
            ],
            max_iterations=60,
            depends_on=["con_load_context"],
        )
    )

    # -----------------------------------------------------------------------
    # Phase 4: Global + claim_boundary extraction (agentic)
    # -----------------------------------------------------------------------
    phases.append(
        Phase(
            name="con_extract_global",
            description="Step 2.1-2.3: Extract global and claim_boundary constraints",
            system_prompt=prompts.CON_GLOBAL_SYSTEM,
            initial_message_builder=_build_global_extract_message(bp, blueprint_path),
            allowed_tools=[
                "read_file",
                "grep_codebase",
                "list_dir",
                "write_artifact",
                "get_artifact",
            ],
            max_iterations=60,
            depends_on=["con_load_context"],
        )
    )

    # -----------------------------------------------------------------------
    # Phase 5: BD-driven derivation (agentic)
    # Step 2.4
    # Only add this phase if the blueprint has business_decisions.
    # -----------------------------------------------------------------------
    if business_decisions:
        phases.append(
            Phase(
                name="con_derive",
                description="Step 2.4: Derive constraints from business_decisions (RC/BA/M/B/missing)",
                system_prompt=prompts.CON_DERIVE_SYSTEM,
                initial_message_builder=_build_derive_message(bp, blueprint_path),
                allowed_tools=["write_artifact", "get_artifact"],
                max_iterations=60,
                depends_on=["con_load_context"],
            )
        )
        derive_deps = ["con_derive"]
    else:
        logger.info(
            "Blueprint %s has no business_decisions — skipping con_derive phase", blueprint_id
        )
        derive_deps = []

    # -----------------------------------------------------------------------
    # Phase 6: Ingest (pure Python)
    # Step 3: Parse JSON artifacts → Constraint objects → write constraints.jsonl
    # -----------------------------------------------------------------------
    ingest_deps = stage_phase_names + ["con_extract_edges", "con_extract_global"] + derive_deps
    phases.append(
        Phase(
            name="con_ingest",
            description="Step 3: Parse constraint JSON artifacts → validate → write constraints.jsonl",
            system_prompt="",
            initial_message_builder=lambda s, r: "",
            requires_llm=False,
            python_handler=_con_ingest_handler,
            depends_on=ingest_deps,
        )
    )

    # -----------------------------------------------------------------------
    # Phase 7: Post-process (pure Python)
    # Step 4: Apply P0-P5 rules
    # -----------------------------------------------------------------------
    phases.append(
        Phase(
            name="con_postprocess",
            description="Step 4: Apply post-processing rules P0-P5 to constraints.jsonl",
            system_prompt="",
            initial_message_builder=lambda s, r: "",
            requires_llm=False,
            python_handler=_con_postprocess_handler,
            depends_on=["con_ingest"],
        )
    )

    # -----------------------------------------------------------------------
    # Phase 8: Quality validation (pure Python)
    # Step 5: Run quality checks
    # -----------------------------------------------------------------------
    phases.append(
        Phase(
            name="con_validate",
            description=(
                "Step 5: Quality gate — total>=80, kind_coverage>=3, claim_boundary>=5%, dr+ag>=60%"
            ),
            system_prompt="",
            initial_message_builder=lambda s, r: "",
            requires_llm=False,
            python_handler=_con_validate_handler,
            depends_on=["con_postprocess"],
        )
    )

    return phases
