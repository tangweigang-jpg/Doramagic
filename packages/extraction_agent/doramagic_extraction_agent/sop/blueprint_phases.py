"""Blueprint extraction phases — SOP v3.2 / v3.3 mapping.

Maps each SOP step to a Phase object consumed by the SOPExecutor.
Pure-Python phases (0, 1, 0c, 3, 5) carry python_handler functions.
Agentic phases (2a, 2b, 2c, 2d, 4) carry system_prompt + initial_message_builder.

v5 adds:
- ``build_blueprint_phases_v5()`` — Instructor-driven synthesis + quality gate
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

from doramagic_blueprint_pipeline.pipeline import fingerprint_repo
from doramagic_blueprint_pipeline.repo_manager import get_commit_hash

from ..core.agent_loop import PhaseResult
from ..sop.executor import Phase
from ..state.schema import AgentState
from ..tools.indexer import (
    build_index_summary,
    build_math_files_summary,
    build_structural_index,
)
from ..tools.sources import mine_source_context
from . import prompts, prompts_v4, prompts_v5, prompts_v6
from .blueprint_enrich import enrich_blueprint
from .schemas_v5 import BDExtractionResult, QualityGateResult, RawFallback, UCExtractionResult

if TYPE_CHECKING:
    from ..core.agent_loop import ExtractionAgent

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pure-Python phase handlers
# ---------------------------------------------------------------------------


async def _fingerprint_handler(state: AgentState, repo_path: Path) -> PhaseResult:
    """Step 0: Detect subdomain labels via keyword fingerprinting."""
    labels = fingerprint_repo(repo_path)
    state.subdomain_labels = labels
    state.repo_path = str(repo_path)
    logger.info("Fingerprint complete — subdomain_labels=%s", labels)
    return PhaseResult(
        phase_name="bp_fingerprint",
        status="completed",
        final_text=f"subdomain_labels={labels}",
    )


async def _clone_handler(state: AgentState, repo_path: Path) -> PhaseResult:
    """Step 1: Verify repository path exists and capture commit hash."""
    if not repo_path.exists():
        return PhaseResult(
            phase_name="bp_clone",
            status="error",
            error=f"Repository path does not exist: {repo_path}",
        )
    commit_hash = get_commit_hash(repo_path)
    state.repo_path = str(repo_path)
    state.commit_hash = commit_hash
    logger.info("Repository verified: %s @ %s", repo_path, commit_hash)
    return PhaseResult(
        phase_name="bp_clone",
        status="completed",
        final_text=f"repo_path={repo_path} commit={commit_hash}",
    )


async def _structural_index_handler(state: AgentState, repo_path: Path) -> PhaseResult:
    """Step 0c: Build AST structural index — pure Python, no LLM.

    Produces repo_index.json artifact containing:
    - File skeleton (classes, methods, signatures, docstrings)
    - Dependency graph (internal imports)
    - File type classification (model/util/test/example/config)
    - Math-related file detection

    The index is pre-built by the orchestrator and stored on state.extra.
    This phase just saves the artifact and logs stats.
    """
    # Use pre-built index from orchestrator; rebuild only if missing
    index = state.extra.get("structural_index")
    if not index:
        index = build_structural_index(repo_path)
        state.extra["structural_index"] = index

    # Save as artifact
    run_dir_str = getattr(state, "run_dir", None)
    if run_dir_str:
        artifacts_dir = Path(run_dir_str) / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        index_path = artifacts_dir / "repo_index.json"
        index_path.write_text(
            json.dumps(index, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info(
            "Structural index saved to %s (%d KB)", index_path, index_path.stat().st_size // 1024
        )

    stats = index.get("stats", {})
    logger.info(
        "Structural index: %d files, %d classes, %d functions, %d math-related",
        stats.get("total_py_files", 0),
        stats.get("total_classes", 0),
        stats.get("total_functions", 0),
        stats.get("math_related_files", 0),
    )
    return PhaseResult(
        phase_name="bp_structural_index",
        status="completed",
        final_text=(
            f"files={stats.get('total_py_files', 0)} "
            f"classes={stats.get('total_classes', 0)} "
            f"math={stats.get('math_related_files', 0)}"
        ),
    )


async def _mine_sources_handler(state: AgentState, repo_path: Path) -> PhaseResult:
    """Step 0d: Mine non-code sources — pure Python, no LLM.

    Reads README, docs/, CHANGELOG, pyproject.toml, and git log to produce
    source_context.md artifact with structured project knowledge.

    Reuses pre-built context from orchestrator if available.
    """
    content = state.extra.get("source_context")
    if not content:
        content = mine_source_context(repo_path)
        state.extra["source_context"] = content

    # Save as artifact
    run_dir_str = getattr(state, "run_dir", None)
    if run_dir_str:
        artifacts_dir = Path(run_dir_str) / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = artifacts_dir / "source_context.md"
        artifact_path.write_text(content, encoding="utf-8")
        logger.info(
            "Source context saved to %s (%d KB)",
            artifact_path,
            len(content) // 1024,
        )

    sections = sum(1 for line in content.splitlines() if line.startswith("## "))
    return PhaseResult(
        phase_name="bp_mine_sources",
        status="completed",
        final_text=f"sections={sections} chars={len(content)}",
    )


async def _step3_handler(state: AgentState, repo_path: Path) -> PhaseResult:
    """Step 3: Auto-verification — check that file references in artifacts exist.

    Mirrors the verification logic from blueprint_pipeline/pipeline.py:
    extracts ``something.py:line`` patterns from all step-2 artifacts and
    confirms the referenced files are present under ``repo_path``.
    """
    # Collect artifact text from phase state records
    artifact_names = [
        "step2a_architecture.md",
        "step2b_verification.md",
        "step2c_business_decisions.md",
        "step2d_usecases.md",
    ]
    combined_text = ""
    # Resolve artifacts_dir via run_dir stored on state (set by SOPExecutor).
    # Artifacts are written to run_dir/artifacts/{name} by the write_artifact tool;
    # repo_path.parent / "_artifacts" was a stale hard-code that didn't match that layout.
    # If run_dir is absent (e.g. unit tests), skip text loading gracefully.
    run_dir_str = getattr(state, "run_dir", None)
    artifacts_dir: Path | None = Path(run_dir_str) / "artifacts" if run_dir_str else None

    for phase_state in state.phases.values():
        for artifact_name in phase_state.artifacts:
            if artifact_name in artifact_names:
                if artifacts_dir is not None:
                    artifact_path = artifacts_dir / artifact_name
                    if artifact_path.exists():
                        combined_text += artifact_path.read_text(errors="ignore") + "\n"

    # Match file paths: must start with word char, dot, or slash (not backtick/CJK)
    file_refs = re.findall(
        r"(?<![`\w\u4e00-\u9fff])([a-zA-Z_.~/][a-zA-Z0-9_./~-]*\.py)(?::(\d+))?", combined_text
    )
    missing_files: list[str] = []
    checked: set[str] = set()
    for fpath, _ in file_refs:
        if fpath in checked:
            continue
        # Skip glob patterns and invalid paths
        if "*" in fpath or "?" in fpath or "[" in fpath:
            continue
        checked.add(fpath)
        candidate = repo_path / fpath
        if not candidate.exists():
            fname = Path(fpath).name
            try:
                found = list(repo_path.rglob(fname))
            except ValueError:
                continue
            if not found:
                missing_files.append(fpath)

    verified = len(missing_files) == 0
    detail = (
        f"All {len(checked)} file references verified"
        if verified
        else f"{len(missing_files)}/{len(checked)} references not found: {missing_files[:10]}"
    )
    if not verified:
        logger.warning("Step 3 verification issues: %s", detail)
    else:
        logger.info("Step 3: %s", detail)

    return PhaseResult(
        phase_name="bp_step3_verify",
        status="completed",
        final_text=detail,
    )


async def _step5_handler(state: AgentState, repo_path: Path) -> PhaseResult:
    """Step 5: Consistency check — BD type validity and UC required fields."""
    issues: list[str] = []

    valid_bd_types = {
        "T",
        "B",
        "BA",
        "DK",
        "RC",
        "M",
        "B/BA",
        "M/B",
        "M/BA",
        "M/DK",
        "RC/DK",
        "B/DK",
    }
    required_uc_fields = ("negative_keywords", "disambiguation", "data_domain")

    # Resolve artifacts_dir via run_dir stored on state (set by SOPExecutor).
    run_dir_str = getattr(state, "run_dir", None)
    if run_dir_str:
        artifacts_dir = Path(run_dir_str) / "artifacts"
    else:
        # Fallback: cannot locate artifacts without run_dir; report skip.
        return PhaseResult(
            phase_name="bp_step5_consistency",
            status="completed",
            final_text="run_dir not set on state — skipping step 5 artifact checks",
        )

    bd_path = artifacts_dir / "step2c_business_decisions.md"
    if bd_path.exists():
        bd_text = bd_path.read_text(errors="ignore")
        bd_types = re.findall(r"\|\s*\d+\s*\|[^|]+\|\s*([A-Z/]+)\s*\|", bd_text)
        for t in bd_types:
            if t.strip() not in valid_bd_types:
                issues.append(f"Invalid BD type: '{t.strip()}'")
        if len(bd_types) < 5:
            issues.append(f"BD count {len(bd_types)} < minimum 5")
    else:
        issues.append("step2c_business_decisions.md not found — skipping BD check")

    uc_path = artifacts_dir / "step2d_usecases.md"
    if uc_path.exists():
        uc_text = uc_path.read_text(errors="ignore")
        for field in required_uc_fields:
            if field not in uc_text:
                issues.append(f"UC missing required field: {field}")
    else:
        issues.append("step2d_usecases.md not found — skipping UC field check")

    consistent = len(issues) == 0
    detail = "All consistency checks passed" if consistent else f"{len(issues)} issues: {issues}"
    if not consistent:
        logger.warning("Step 5 consistency issues: %s", issues)
    else:
        logger.info("Step 5: %s", detail)

    return PhaseResult(
        phase_name="bp_step5_consistency",
        status="completed",
        final_text=detail,
    )


def _repair_yaml(content: str) -> str:
    """Attempt to repair common LLM YAML errors.

    Fixes:
    1. Unquoted strings containing colons (e.g. `- BD-7: Default: max=100`)
    2. Tabs mixed with spaces
    3. Trailing whitespace that confuses the parser
    """
    import re

    import yaml as _yaml

    # First try — maybe it's already valid
    try:
        _yaml.safe_load(content)
        return content
    except _yaml.YAMLError:
        pass

    lines = content.split("\n")
    repaired: list[str] = []
    for line in lines:
        # Replace tabs with spaces
        line = line.replace("\t", "  ")
        # Fix list items with unquoted colons in value:
        #   `- BD-7: Default pre-bucketing: max_n_bins=100`
        # → `- "BD-7: Default pre-bucketing: max_n_bins=100"`
        m = re.match(r"^(\s*-\s+)(.+:.+:.+)$", line)
        if m:
            indent, value = m.group(1), m.group(2)
            # Only quote if value is not already quoted
            if not (value.startswith('"') or value.startswith("'")):
                line = f'{indent}"{value}"'
        else:
            # Fix mapping values with extra colons:
            #   `    key: value: with: colons`
            # → `    key: "value: with: colons"`
            m2 = re.match(r"^(\s+\w[\w\s]*:\s+)(.+:.+)$", line)
            if m2:
                key_part, val_part = m2.group(1), m2.group(2)
                if not (
                    val_part.startswith('"') or val_part.startswith("'") or val_part.startswith("[")
                ):
                    line = f'{key_part}"{val_part}"'
        repaired.append(line.rstrip())

    repaired_content = "\n".join(repaired)

    # Verify the repair worked
    try:
        _yaml.safe_load(repaired_content)
        logger.info(
            "YAML repair successful — fixed %d lines",
            sum(1 for a, b in zip(content.split("\n"), repaired) if a.rstrip() != b),
        )
        return repaired_content
    except _yaml.YAMLError as e:
        logger.warning("YAML repair incomplete — still has errors: %s", e)
        return repaired_content  # return best-effort repair


async def _finalize_handler(state: AgentState, repo_path: Path) -> PhaseResult:
    """Repair YAML, then promote blueprint with versioned naming.

    v6 naming: ``{bp_id}--{repo_slug}/blueprint.v{N}.yaml`` + LATEST symlink.
    """
    from ..state.output import OutputManager

    run_dir = Path(state.run_dir) if state.run_dir else repo_path.parent
    artifacts_dir = run_dir / "artifacts"
    bp_file = artifacts_dir / "blueprint.yaml"
    if not bp_file.exists():
        return PhaseResult(
            phase_name="bp_finalize",
            status="error",
            error="blueprint.yaml not found in artifacts",
        )

    content = bp_file.read_text()

    # Attempt YAML repair
    content = _repair_yaml(content)

    # Validate
    import yaml as _yaml

    try:
        parsed = _yaml.safe_load(content)
        if not isinstance(parsed, dict):
            return PhaseResult(
                phase_name="bp_finalize",
                status="error",
                error="blueprint.yaml is not a YAML mapping",
            )
    except _yaml.YAMLError as e:
        return PhaseResult(
            phase_name="bp_finalize",
            status="error",
            error=f"blueprint.yaml YAML still invalid after repair: {e}",
        )

    # Normalize field name variants that MiniMax might use
    field_renames = {
        "global_rules": "global_contracts",
        "cross_stage_contracts": "global_contracts",
    }
    for old_key, new_key in field_renames.items():
        if old_key in parsed and new_key not in parsed:
            parsed[new_key] = parsed.pop(old_key)
            logger.info("bp_finalize: renamed field '%s' -> '%s'", old_key, new_key)

    # Ensure source.projects exists
    parsed_source = parsed.get("source")
    if not isinstance(parsed_source, dict):
        parsed_source = {}
        parsed["source"] = parsed_source
    if not parsed_source.get("projects"):
        repo = parsed_source.get("repository", "")
        if not repo:
            repo_p = Path(state.repo_path)
            repo = repo_p.name
        parsed_source["projects"] = [repo] if repo else []
        logger.info("bp_finalize: populated source.projects=[%r] from repo path", repo)

    content = _yaml.dump(
        parsed, allow_unicode=True, default_flow_style=False, sort_keys=False
    )

    # Write repaired YAML back to artifacts (for debugging)
    bp_file.write_text(content)

    # Derive repo_slug from repo path (e.g. "repos/zvt" → "zvt")
    repo_slug = Path(state.repo_path).name if state.repo_path else ""

    # Build version metadata from artifacts
    version_meta: dict[str, Any] = {
        "commit_hash": state.commit_hash or parsed_source.get("commit_hash", ""),
        "sop_version": parsed.get("sop_version", "3.4"),
        "agent_version": "v6",
        "llm_model": getattr(state, "llm_model", ""),
    }

    # Load evaluator report and quality gate if available
    eval_path = artifacts_dir / "evaluation_report.json"
    if eval_path.exists():
        try:
            import json as _json

            eval_data = _json.loads(eval_path.read_text(encoding="utf-8"))
            version_meta["evaluator"] = {
                "score": eval_data.get("score", 0),
                "evaluated": eval_data.get("evaluated_count", 0),
                "passed": eval_data.get("pass_count", 0),
                "issues": len(eval_data.get("issues", [])),
                "recommendation": eval_data.get("recommendation", ""),
            }
        except Exception:
            pass

    qg_path = artifacts_dir / "quality_gate_result.json"
    if qg_path.exists():
        try:
            import json as _json

            version_meta["quality_gate"] = _json.loads(
                qg_path.read_text(encoding="utf-8")
            )
        except Exception:
            pass

    # Compute stats from parsed blueprint
    bds = parsed.get("business_decisions", [])
    non_t = [b for b in bds if isinstance(b, dict) and b.get("type", "T") != "T"]
    missing = [b for b in bds if isinstance(b, dict) and b.get("status") == "missing"]
    version_meta["stats"] = {
        "stages": len(parsed.get("stages", [])),
        "business_decisions": len(bds),
        "non_t_decisions": len(non_t),
        "missing_gaps": len(missing),
        "known_use_cases": len(parsed.get("known_use_cases", [])),
        "global_contracts": len(parsed.get("global_contracts", [])),
    }

    # Write to versioned output directory
    output_path = Path(state.output_dir) if state.output_dir else run_dir / "output"
    output_mgr = OutputManager(output_path, state.blueprint_id, repo_slug=repo_slug)
    bp_path = output_mgr.write_blueprint(content, version_meta=version_meta)

    # Also update manifest top-level fields
    output_mgr.write_manifest(
        blueprint_id=state.blueprint_id,
        domain=state.domain or "finance",
        commit_hash=version_meta["commit_hash"],
        llm_model=version_meta.get("llm_model", ""),
        blueprint_stats=version_meta.get("stats"),
        quality_gates=version_meta.get("quality_gate"),
    )

    state.blueprint_path = str(bp_path)
    logger.info("bp_finalize: promoted blueprint to %s", state.blueprint_path)
    return PhaseResult(phase_name="bp_finalize", status="completed", iterations=0)


# ---------------------------------------------------------------------------
# Quality gate for Step 4
# ---------------------------------------------------------------------------


def _blueprint_yaml_gate(state: AgentState, repo_path: Path) -> tuple[bool, str]:
    """Verify that the assembled blueprint.yaml artifact is syntactically valid YAML."""
    import yaml  # local import — pyyaml is an optional dep of extraction_agent

    run_dir_str = getattr(state, "run_dir", None)
    if run_dir_str:
        artifact_path = Path(run_dir_str) / "artifacts" / "blueprint.yaml"
    else:
        return False, "run_dir not set on state — cannot locate blueprint.yaml"
    if not artifact_path.exists():
        return False, "blueprint.yaml not found in artifact store"
    try:
        doc = yaml.safe_load(artifact_path.read_text())
    except yaml.YAMLError as exc:
        return False, f"blueprint.yaml YAML parse error: {exc}"
    if not isinstance(doc, dict):
        return False, "blueprint.yaml top-level must be a YAML mapping"
    required_keys = {"id", "name", "sop_version", "stages", "business_decisions"}
    missing = required_keys - set(doc.keys())
    if missing:
        return False, f"blueprint.yaml missing required keys: {sorted(missing)}"
    sop_ver = doc.get("sop_version", "")
    if sop_ver != "3.2":
        return False, f"blueprint.yaml sop_version={sop_ver!r}, expected '3.2'"
    return True, f"blueprint.yaml valid — {len(doc.get('stages', []))} stages, sop_version=3.2"


def _bd_r2_gate(state: AgentState, repo_path: Path) -> tuple[bool, str]:
    """Quality gate for Round 2: check T ratio is not artificially high."""
    import json

    artifacts_dir = Path(state.run_dir) / "artifacts" if state.run_dir else None
    if not artifacts_dir:
        return True, "run_dir not set, skipping gate"
    r2_path = artifacts_dir / "step2c_r2_separated.json"
    if not r2_path.exists():
        return False, "step2c_r2_separated.json not found"
    try:
        decisions = json.loads(r2_path.read_text())
        if not decisions:
            return False, "R2 produced 0 decisions"
        t_count = sum(1 for d in decisions if d.get("preliminary_class") == "T")
        t_ratio = t_count / len(decisions)
        if t_ratio > 0.85:
            return False, f"T ratio {t_ratio:.0%} > 85% — LLM likely defaulting to T"
        return True, f"T ratio {t_ratio:.0%} ({t_count}/{len(decisions)})"
    except Exception as e:
        return False, f"R2 artifact parse failed: {e}"


def _bd_final_gate(state: AgentState, repo_path: Path) -> tuple[bool, str]:
    """Quality gate for Round 4: check final BD quality."""
    artifacts_dir = Path(state.run_dir) / "artifacts" if state.run_dir else None
    if not artifacts_dir:
        return True, "run_dir not set, skipping gate"
    md_path = artifacts_dir / "step2c_business_decisions.md"
    if not md_path.exists():
        return False, "step2c_business_decisions.md not found"

    content = md_path.read_text()
    # Count BD types from markdown table
    import re

    type_pattern = re.compile(r"\|\s*\d+\s*\|[^|]+\|\s*([A-Z/]+)\s*\|")
    types = type_pattern.findall(content)
    if len(types) < 5:
        return False, f"Only {len(types)} BD entries (need >= 5)"

    from collections import Counter

    type_counts = Counter(t.strip() for t in types)

    labels = state.subdomain_labels or []
    issues = []

    # M check for quant projects
    m_count = sum(v for k, v in type_counts.items() if "M" in k)
    if any(l in labels for l in ["TRD", "PRC", "RSK"]) and m_count == 0:
        issues.append(f"M=0 in quant project (labels={labels})")

    # RC check for credit/compliance
    rc_count = sum(v for k, v in type_counts.items() if "RC" in k)
    if any(l in labels for l in ["CRD", "CMP"]) and rc_count == 0:
        issues.append("RC=0 in credit/compliance project")

    # DK check for market-specific projects
    dk_count = sum(v for k, v in type_counts.items() if "DK" in k)
    if any(l in labels for l in ["TRD", "A_STOCK"]) and dk_count == 0:
        issues.append("DK=0 in trading/A-stock project")

    # BA check (universal)
    ba_count = sum(v for k, v in type_counts.items() if "BA" in k)
    if ba_count == 0 and len(types) >= 10:
        issues.append("BA=0 despite having 10+ decisions")

    if issues:
        return False, "; ".join(issues)
    return True, f"BD types: {dict(type_counts)}, total={len(types)}"


# ---------------------------------------------------------------------------
# Initial message builders
# ---------------------------------------------------------------------------


def _get_index_summary(state: AgentState) -> str:
    """Retrieve the structural index summary from state, or fall back to artifact."""
    index = state.extra.get("structural_index")
    if not index:
        # Fallback: on resume, try to load from artifact
        run_dir_str = getattr(state, "run_dir", None)
        if run_dir_str:
            import json as _json

            artifact = Path(run_dir_str) / "artifacts" / "repo_index.json"
            if artifact.exists():
                index = _json.loads(artifact.read_text())
                state.extra["structural_index"] = index
    if not index:
        return ""
    return build_index_summary(index)


def _get_math_summary(state: AgentState) -> str:
    """Retrieve the math-files summary from state, or empty string."""
    index = state.extra.get("structural_index")
    if not index:
        return ""
    return build_math_files_summary(index)


def _get_source_context(state: AgentState, max_chars: int = 6000) -> str:
    """Retrieve mined source context from state, or fall back to artifact."""
    ctx = state.extra.get("source_context", "")
    # Fallback: on resume, state.extra is empty but artifact exists on disk
    if not ctx:
        run_dir_str = getattr(state, "run_dir", None)
        if run_dir_str:
            artifact = Path(run_dir_str) / "artifacts" / "source_context.md"
            if artifact.exists():
                ctx = artifact.read_text(encoding="utf-8", errors="ignore")
                state.extra["source_context"] = ctx
    if not ctx:
        return ""
    if len(ctx) > max_chars:
        ctx = ctx[:max_chars]
    return ctx


def _build_step2a_message(state: AgentState, repo_path: Path) -> str:
    labels = state.subdomain_labels or ["TRD"]
    index_summary = _get_index_summary(state)
    parts = [
        f"Repository: {repo_path}",
        f"Subdomain labels: {labels}",
    ]
    if index_summary:
        parts.append(f"\n{index_summary}")
        parts.append(
            "\nUse the structural index tools (get_skeleton, get_dependencies, "
            "list_by_type) to efficiently explore the codebase. Start from entry "
            "points and model files rather than blind directory listing."
        )
    parts.append("\nBegin architecture extraction.")
    return "\n".join(parts)


def _build_step2b_message(state: AgentState, repo_path: Path) -> str:
    return (
        "Read the architecture report from get_artifact('step2a_architecture.md') "
        "and verify all claims."
    )


def _build_step2c_r1_message(state: AgentState, repo_path: Path) -> str:
    """Round 1: Workflow discovery initial message."""
    labels = state.subdomain_labels or ["TRD"]
    math_summary = _get_math_summary(state)
    source_ctx = _get_source_context(state)
    parts = [
        f"Repository: {repo_path}",
        f"Subdomain labels: {labels}",
        "",
        "Start by exploring examples/, notebooks/, tutorials/ in the repository.",
        "Also read the architecture report: get_artifact('step2a_architecture.md')",
    ]
    if source_ctx:
        parts.append(f"\n{source_ctx}")
        parts.append(
            "Use the source context above to understand project intent, "
            "evolution history, and known limitations BEFORE exploring code."
        )
    if math_summary:
        parts.append(f"\n{math_summary}")
        parts.append(
            "IMPORTANT: Each math-related file likely contains one or more design "
            "decisions about mathematical model selection, algorithm choice, or "
            "numerical method. You MUST explore these files and extract decisions from them."
        )
    parts.extend(
        [
            "",
            "Find concrete business workflows and extract ALL raw design decisions.",
            "Use get_skeleton() and list_by_type('model') to efficiently find decision-bearing code.",
            "Write the result as JSON array to write_artifact('step2c_r1_raw_decisions.json').",
        ]
    )
    return "\n".join(parts)


def _build_step2c_r2_message(state: AgentState, repo_path: Path) -> str:
    """Round 2: Counterfactual separation initial message."""
    return (
        f"Read the raw decisions: get_artifact('step2c_r1_raw_decisions.json')\n\n"
        f"For each decision, perform counterfactual analysis:\n"
        f"'If this choice were changed, would business output change?'\n\n"
        f"The repository is at {repo_path}.\n"
        f"Use read_file with relative paths (e.g., 'skorecard/main.py') to verify your reasoning against actual code.\n"
        f"Write result to write_artifact('step2c_r2_separated.json')."
    )


def _build_step2c_r3_message(state: AgentState, repo_path: Path) -> str:
    """Round 3: Adversarial classification initial message."""
    math_summary = _get_math_summary(state)
    source_ctx = _get_source_context(state, max_chars=3000)
    parts = [
        "Read the separated decisions: get_artifact('step2c_r2_separated.json')",
        "",
        "For each non-T decision, apply three expert lenses sequentially:",
        "1. Quantitative Analyst → assess p(M)",
        "2. Regulator → assess p(RC), p(DK)",
        "3. Business Hypothesis Analyst → assess p(BA), p(B)",
    ]
    if source_ctx:
        parts.append(f"\n## Project Context (from README/docs/CHANGELOG)\n{source_ctx}")
    if math_summary:
        parts.append(f"\n## Context for Quantitative Analyst Role\n{math_summary}")
        parts.append(
            "Any decision involving these math-related files should have HIGH p(M). "
            "Use get_skeleton() to inspect the mathematical logic before classifying."
        )
    parts.extend(
        [
            "",
            f"The repository is at {repo_path}.",
            "Use read_file with relative paths to find evidence for each classification.",
            "Use get_skeleton() and list_by_type('math') for quick structural lookup.",
            "Write result to write_artifact('step2c_r3_classified.json').",
        ]
    )
    return "\n".join(parts)


def _build_step2c_r4_message(state: AgentState, repo_path: Path) -> str:
    """Round 4: Evidence + anomaly detection + final output."""
    labels = state.subdomain_labels or []

    # Build dynamic anomaly rules based on subdomain
    anomaly_rules = []
    if any(l in labels for l in ["TRD", "PRC", "RSK"]):
        anomaly_rules.append(
            "ANOMALY CHECK: M=0 in a quantitative/pricing/risk project. "
            "This is almost certainly wrong. Use grep_codebase to search for mathematical "
            "models (np.linalg, scipy.optimize, sklearn, statsmodels, regression, optimize, "
            "factor, alpha, sharpe). Any model found MUST be classified as M."
        )
    if any(l in labels for l in ["CRD"]):
        anomaly_rules.append(
            "ANOMALY CHECK: RC=0 in a credit/banking project. "
            "Search for: Basel, IFRS, CRR, IRB, PD, LGD, EAD, default definition, NPL."
        )
    if any(l in labels for l in ["TRD", "A_STOCK"]):
        anomaly_rules.append(
            "ANOMALY CHECK: DK=0 in a trading/A-stock project. "
            "Search for: T+1, 涨跌停, 印花税, turnover_rate, 停牌, ST."
        )
    anomaly_rules.append(
        "ANOMALY CHECK: Total non-T decisions < 5. "
        "Extraction is too shallow. Re-examine examples/ and default parameter values."
    )
    anomaly_rules.append(
        "ANOMALY CHECK: BA=0 for any project with configurable defaults. "
        "Search constructors and config files for default parameter values with implicit assumptions."
    )

    # Build finance checklists for the final audit
    from .prompts import FINANCE_UNIVERSAL_CHECKLIST, build_subdomain_checklist

    checklist = build_subdomain_checklist(labels)

    anomaly_text = "\n".join(f"- {r}" for r in anomaly_rules)

    return (
        f"Read the classified decisions: get_artifact('step2c_r3_classified.json')\n\n"
        f"## Anomaly Detection Rules\n{anomaly_text}\n\n"
        f"## Tasks\n"
        f"1. Re-examine high-entropy decisions (max probability < 0.5) with new evidence. The repository is at {repo_path}.\n"
        f"   Use read_file and grep_codebase with relative paths to find additional evidence.\n"
        f"2. Run ALL anomaly checks above. For each triggered, search source code and reclassify.\n"
        f"3. Produce the FINAL business decision report as Markdown table.\n\n"
        f"## Finance Universal Checklist (audit each item)\n{FINANCE_UNIVERSAL_CHECKLIST}\n\n"
        f"## Subdomain Checklist ({', '.join(labels)})\n{checklist}\n\n"
        f"Write the final report to write_artifact('step2c_business_decisions.md').\n"
        f"The report MUST include:\n"
        f"- Markdown table: | # | Content | Type | Rationale | Evidence | Stage |\n"
        f"- Summary by type\n"
        f"- Anomaly detection report\n"
        f"- Checklist audit results"
    )


def _build_step2d_message(state: AgentState, repo_path: Path) -> str:
    return (
        f"Scan {repo_path} for examples, notebooks, and built-in components. "
        "Build the known_use_cases index."
    )


def _build_step4_message(blueprint_id: str) -> callable:
    """Return an initial_message_builder closure bound to ``blueprint_id``."""

    def builder(state: AgentState, repo_path: Path) -> str:
        return (
            f"Assemble blueprint YAML for {blueprint_id} from all artifacts. "
            "Use get_artifact() to read step2a, step2b, step2c, and step2d reports."
        )

    return builder


# ---------------------------------------------------------------------------
# Phase list factory
# ---------------------------------------------------------------------------


def build_blueprint_phases(blueprint_id: str) -> list[Phase]:
    """Build the complete list of blueprint extraction phases for SOP v3.2.

    Args:
        blueprint_id: Blueprint identifier, e.g. ``"finance-bp-060"``.
            Used to bind the step-4 message builder and for logging.

    Returns:
        Ordered list of :class:`~doramagic_extraction_agent.sop.executor.Phase`
        objects ready to be handed to the ``SOPExecutor``.
    """
    return [
        # ------------------------------------------------------------------
        # Step 0: Fingerprint (pure Python)
        # ------------------------------------------------------------------
        Phase(
            name="bp_fingerprint",
            description="Step 0: Project fingerprint — detect subdomain labels",
            system_prompt="",
            initial_message_builder=lambda s, r: "",
            requires_llm=False,
            python_handler=_fingerprint_handler,
        ),
        # ------------------------------------------------------------------
        # Step 1: Clone / verify repo (pure Python)
        # ------------------------------------------------------------------
        Phase(
            name="bp_clone",
            description="Step 1: Verify repository is available and capture commit hash",
            system_prompt="",
            initial_message_builder=lambda s, r: "",
            requires_llm=False,
            python_handler=_clone_handler,
            depends_on=["bp_fingerprint"],
        ),
        # ------------------------------------------------------------------
        # Step 0c: Structural index (pure Python)
        # ------------------------------------------------------------------
        Phase(
            name="bp_structural_index",
            description="Step 0c: Build AST structural index (file skeleton, deps, math detection)",
            system_prompt="",
            initial_message_builder=lambda s, r: "",
            requires_llm=False,
            python_handler=_structural_index_handler,
            depends_on=["bp_clone"],
        ),
        # ------------------------------------------------------------------
        # Step 0d: Mine non-code sources (pure Python)
        # ------------------------------------------------------------------
        Phase(
            name="bp_mine_sources",
            description="Step 0d: Mine README, docs, CHANGELOG, dependencies, git log",
            system_prompt="",
            initial_message_builder=lambda s, r: "",
            requires_llm=False,
            python_handler=_mine_sources_handler,
            depends_on=["bp_clone"],
        ),
        # ------------------------------------------------------------------
        # Step 2a: Architecture extraction (agentic)
        # ------------------------------------------------------------------
        Phase(
            name="bp_architecture",
            description="Step 2a: Architecture extraction via source code exploration",
            system_prompt=prompts.BP_STEP2A_SYSTEM,
            initial_message_builder=_build_step2a_message,
            allowed_tools=[
                "read_file",
                "list_dir",
                "grep_codebase",
                "search_codebase",
                "write_artifact",
                "get_skeleton",
                "get_dependencies",
                "get_file_type",
                "list_by_type",
            ],
            max_iterations=80,
            depends_on=["bp_structural_index"],
            required_artifacts=["step2a_architecture.md"],
            blocking=True,
        ),
        # ------------------------------------------------------------------
        # Step 2b: Claim verification (agentic)
        # ------------------------------------------------------------------
        Phase(
            name="bp_claim_verify",
            description="Step 2b: Verify architectural claims against source code",
            system_prompt=prompts.BP_STEP2B_SYSTEM,
            initial_message_builder=_build_step2b_message,
            allowed_tools=[
                "read_file",
                "grep_codebase",
                "search_codebase",
                "get_artifact",
                "write_artifact",
            ],
            max_iterations=60,
            depends_on=["bp_architecture"],
            required_artifacts=["step2b_verification.md"],
            blocking=True,
        ),
        # ------------------------------------------------------------------
        # Step 2c: Business decision annotation — 4-round deep extraction
        # ------------------------------------------------------------------
        # Round 1: Workflow Discovery + Raw Decision Extraction
        Phase(
            name="bp_bd_r1_discovery",
            description="Step 2c-R1: Workflow discovery from examples and raw decision extraction",
            system_prompt=prompts.BP_STEP2C_R1_DISCOVERY,
            initial_message_builder=_build_step2c_r1_message,
            allowed_tools=[
                "read_file",
                "list_dir",
                "grep_codebase",
                "get_artifact",
                "write_artifact",
                "get_skeleton",
                "get_dependencies",
                "list_by_type",
            ],
            max_iterations=70,
            depends_on=["bp_architecture", "bp_claim_verify", "bp_mine_sources"],
            required_artifacts=["step2c_r1_raw_decisions.json"],
            blocking=True,
        ),
        # Round 2: Counterfactual T vs non-T
        Phase(
            name="bp_bd_r2_counterfactual",
            description="Step 2c-R2: Counterfactual T vs non-T separation",
            system_prompt=prompts.BP_STEP2C_R2_COUNTERFACTUAL,
            initial_message_builder=_build_step2c_r2_message,
            allowed_tools=[
                "read_file",
                "grep_codebase",
                "get_artifact",
                "write_artifact",
                "get_skeleton",
            ],
            max_iterations=50,
            depends_on=["bp_bd_r1_discovery"],
            quality_gate=_bd_r2_gate,
            required_artifacts=["step2c_r2_separated.json"],
            blocking=True,
        ),
        # Round 3: Multi-Role Adversarial Classification
        Phase(
            name="bp_bd_r3_adversarial",
            description="Step 2c-R3: Multi-role adversarial classification (reduce-T game)",
            system_prompt=prompts.BP_STEP2C_R3_ADVERSARIAL,
            initial_message_builder=_build_step2c_r3_message,
            allowed_tools=[
                "read_file",
                "grep_codebase",
                "get_artifact",
                "write_artifact",
                "get_skeleton",
                "list_by_type",
            ],
            max_iterations=60,
            depends_on=["bp_bd_r2_counterfactual"],
            required_artifacts=["step2c_r3_classified.json"],
            blocking=True,
        ),
        # Round 4: Evidence + Anomaly Detection + Final Output
        Phase(
            name="bp_bd_r4_evidence",
            description="Step 2c-R4: Evidence acquisition, anomaly detection, final BD report",
            system_prompt=prompts.BP_STEP2C_R4_EVIDENCE,
            initial_message_builder=_build_step2c_r4_message,
            allowed_tools=[
                "read_file",
                "grep_codebase",
                "get_artifact",
                "write_artifact",
                "get_skeleton",
                "list_by_type",
            ],
            max_iterations=50,
            depends_on=["bp_bd_r3_adversarial"],
            quality_gate=_bd_final_gate,
            required_artifacts=["step2c_business_decisions.md"],
            blocking=True,
        ),
        # ------------------------------------------------------------------
        # Step 2d: Use case scan (agentic)
        # ------------------------------------------------------------------
        Phase(
            name="bp_usecase_scan",
            description="Step 2d: Discover business use cases from examples and docs",
            system_prompt=prompts.BP_STEP2D_SYSTEM,
            initial_message_builder=_build_step2d_message,
            allowed_tools=["read_file", "list_dir", "grep_codebase", "write_artifact"],
            max_iterations=50,
            depends_on=["bp_clone"],
            required_artifacts=["step2d_usecases.md"],
            blocking=False,
        ),
        # ------------------------------------------------------------------
        # Step 3: Auto-verification (pure Python)
        # ------------------------------------------------------------------
        Phase(
            name="bp_auto_verify",
            description="Step 3: Verify file references in extraction artifacts",
            system_prompt="",
            initial_message_builder=lambda s, r: "",
            requires_llm=False,
            python_handler=_step3_handler,
            depends_on=[
                "bp_architecture",
                "bp_claim_verify",
                "bp_bd_r4_evidence",
                "bp_usecase_scan",
            ],
        ),
        # ------------------------------------------------------------------
        # Step 4: Blueprint assembly (agentic) with YAML quality gate
        # ------------------------------------------------------------------
        Phase(
            name="bp_assemble",
            description="Step 4: Assemble final blueprint YAML from all artifacts",
            system_prompt=prompts.BP_STEP4_SYSTEM,
            initial_message_builder=_build_step4_message(blueprint_id),
            allowed_tools=["get_artifact", "write_artifact"],
            max_iterations=40,
            depends_on=["bp_auto_verify"],
            quality_gate=_blueprint_yaml_gate,
            required_artifacts=["blueprint.yaml"],
            blocking=True,
        ),
        # ------------------------------------------------------------------
        # Step 5: Consistency check (pure Python)
        # ------------------------------------------------------------------
        Phase(
            name="bp_consistency_check",
            description="Step 5: Check BD type validity and UC required fields",
            system_prompt="",
            initial_message_builder=lambda s, r: "",
            requires_llm=False,
            python_handler=_step5_handler,
            depends_on=["bp_assemble"],
        ),
        # ------------------------------------------------------------------
        # Step 6: Finalize — promote blueprint from artifacts to output/
        # ------------------------------------------------------------------
        Phase(
            name="bp_finalize",
            description="Step 6: Promote blueprint.yaml from artifacts/ to output/",
            system_prompt="",
            initial_message_builder=lambda s, r: "",
            requires_llm=False,
            python_handler=_finalize_handler,
            depends_on=["bp_consistency_check"],
        ),
    ]


# ---------------------------------------------------------------------------
# v4 Architecture: 2-phase merged pipeline
# ---------------------------------------------------------------------------


def _build_explore_message(state: AgentState, repo_path: Path) -> str:
    """Build initial message for the merged Explore phase."""
    labels = state.subdomain_labels or ["TRD"]
    index_summary = _get_index_summary(state)
    math_summary = _get_math_summary(state)
    source_ctx = _get_source_context(state)

    parts = [
        f"Repository: {repo_path}",
        f"Subdomain labels: {labels}",
    ]

    if source_ctx:
        parts.append(f"\n{source_ctx}")

    if index_summary:
        parts.append(f"\n{index_summary}")

    if math_summary:
        parts.append(f"\n{math_summary}")
        parts.append(
            "IMPORTANT: Each math-related file likely contains M-type "
            "decisions. You MUST explore these files."
        )

    # Inject anomaly rules based on subdomain
    anomaly_rules = []
    if any(l in labels for l in ["TRD", "PRC", "RSK"]):
        anomaly_rules.append(
            "ANOMALY: M=0 in a quant project — search for "
            "scipy, sklearn, numpy.linalg, statsmodels."
        )
    if any(l in labels for l in ["TRD", "A_STOCK"]):
        anomaly_rules.append(
            "ANOMALY: DK=0 in a trading/A-stock project — search for T+1, 涨跌停, 印花税, ST."
        )
    if anomaly_rules:
        parts.append("\n## Anomaly Detection Rules")
        parts.extend(f"- {r}" for r in anomaly_rules)

    # Inject finance checklist
    checklist = prompts_v4.build_subdomain_checklist(labels)
    parts.append(f"\n## Finance Checklist\n{checklist}")

    parts.append(
        "\nBegin Stage A (Architecture Discovery). "
        "Use structural index tools to navigate efficiently."
    )
    return "\n".join(parts)


def _build_assemble_message_v4(
    blueprint_id: str,
) -> callable:
    """Return a builder for the merged Assemble phase."""

    def builder(state: AgentState, repo_path: Path) -> str:
        return (
            f"Blueprint ID: {blueprint_id}\n"
            f"Repository: {repo_path}\n\n"
            "Read get_artifact('step2c_business_decisions.md') "
            "and assemble the final blueprint YAML + use cases."
        )

    return builder


def _build_worker_docs_message(state: AgentState, repo_path: Path) -> str:
    source_ctx = _get_source_context(state)
    ctx_block = f"\nPre-mined context (verify and expand):\n{source_ctx}" if source_ctx else ""
    return f"Repository: {repo_path}\n{ctx_block}"


def _get_manifest_checklist(state: AgentState, max_dirs: int = 30) -> str:
    """Build a mandatory visit checklist from coverage manifest."""
    manifest = state.extra.get("coverage_manifest")
    if not manifest:
        return ""
    all_dirs = manifest.get("must_visit_dirs", [])
    dirs = all_dirs[:max_dirs]
    bases = manifest.get("base_classes", [])[:15]
    patterns = manifest.get("arch_patterns", [])
    parts = ["\n## MANDATORY Coverage Checklist"]
    if dirs:
        truncated = f" (showing {len(dirs)}/{len(all_dirs)})" if len(dirs) < len(all_dirs) else ""
        parts.append(f"\nYou MUST visit at least one file in each of these directories{truncated}:")
        for d in dirs:
            parts.append(f"  - {d}/")
    if bases:
        parts.append("\nYou MUST check these base classes for default values:")
        for b in bases:
            parts.append(f"  - {b['class']} in {b['file']}")
    if patterns:
        parts.append("\nGrep for these architecture patterns:")
        for p in patterns:
            parts.append(f"  - {p}")
    return "\n".join(parts)


def _build_worker_arch_message(state: AgentState, repo_path: Path) -> str:
    checklist = _get_manifest_checklist(state)
    return f"Repository: {repo_path}\n\n{_get_index_summary(state)}{checklist}"


def _build_worker_workflow_message(state: AgentState, repo_path: Path) -> str:
    checklist = _get_manifest_checklist(state, max_dirs=10)
    return (
        f"Repository: {repo_path}\n\n{_get_index_summary(state)}{checklist}\n\n"
        "Extract ALL raw business decisions. Target: minimum 30."
    )


def _build_worker_math_message(state: AgentState, repo_path: Path) -> str:
    return (
        f"Repository: {repo_path}\n\n{_get_math_summary(state)}\n\n"
        "Extract ALL math decisions. Target: minimum 15. "
        "EVERY file above must contribute at least one decision."
    )


def _build_synthesis_message(state: AgentState, repo_path: Path) -> str:
    labels = state.subdomain_labels or ["TRD"]
    checklist = prompts_v4.build_subdomain_checklist(labels)
    parts = [f"Subdomain labels: {labels}", ""]
    if any(l in labels for l in ["TRD", "PRC", "RSK"]):
        parts.append("- ANOMALY: M=0 in quant project → re-check math worker")
    if any(l in labels for l in ["TRD", "A_STOCK"]):
        parts.append("- ANOMALY: DK=0 in A-stock → search T+1, 涨跌停, 印花税")
    parts.append(f"\n## Finance Checklist\n{checklist}")
    return "\n".join(parts)


def build_blueprint_phases_v4(blueprint_id: str) -> list[Phase]:
    """Build the v4.1 parallel worker blueprint extraction phases.

    Architecture:
    - Pre-processing: 4 Python phases (<1s)
    - Parallel workers: 4 agentic phases concurrent (~5 min)
    - Synthesis: 1 agentic phase merges + classifies (~3 min)
    - Assembly: 1 agentic phase produces YAML (~3 min)
    - Post-processing: 2 Python phases (<1s)

    Total: 12 phases (6 agentic), ~11-14 min with depth.
    """
    all_tools = [
        "read_file",
        "list_dir",
        "grep_codebase",
        "search_codebase",
        "write_artifact",
        "get_artifact",
        "get_skeleton",
        "get_dependencies",
        "get_file_type",
        "list_by_type",
    ]

    return [
        # --- Pre-processing (Python, <1s) ---
        Phase(
            name="bp_fingerprint",
            description="Fingerprint",
            system_prompt="",
            initial_message_builder=lambda s, r: "",
            requires_llm=False,
            python_handler=_fingerprint_handler,
        ),
        Phase(
            name="bp_clone",
            description="Verify repo",
            system_prompt="",
            initial_message_builder=lambda s, r: "",
            requires_llm=False,
            python_handler=_clone_handler,
            depends_on=["bp_fingerprint"],
        ),
        Phase(
            name="bp_structural_index",
            description="AST structural index",
            system_prompt="",
            initial_message_builder=lambda s, r: "",
            requires_llm=False,
            python_handler=_structural_index_handler,
            depends_on=["bp_clone"],
        ),
        Phase(
            name="bp_mine_sources",
            description="Mine non-code sources",
            system_prompt="",
            initial_message_builder=lambda s, r: "",
            requires_llm=False,
            python_handler=_mine_sources_handler,
            depends_on=["bp_clone"],
        ),
        # --- Parallel Workers (concurrent via parallel_group) ---
        Phase(
            name="worker_docs",
            description="Worker: project context from docs",
            system_prompt=prompts_v4.WORKER_DOCS_SYSTEM,
            initial_message_builder=_build_worker_docs_message,
            allowed_tools=["read_file", "list_dir", "grep_codebase", "write_artifact"],
            max_iterations=30,
            depends_on=["bp_mine_sources"],
            required_artifacts=["worker_docs.md"],
            parallel_group="explore",
        ),
        Phase(
            name="worker_arch",
            description="Worker: architecture skeleton",
            system_prompt=prompts_v4.WORKER_ARCH_SYSTEM,
            initial_message_builder=_build_worker_arch_message,
            allowed_tools=all_tools,
            max_iterations=20,
            depends_on=["bp_structural_index"],
            required_artifacts=["worker_arch.json"],
            blocking=True,
            parallel_group="explore",
        ),
        Phase(
            name="worker_workflow",
            description="Worker: business decisions from workflows",
            system_prompt=prompts_v4.WORKER_WORKFLOW_SYSTEM,
            initial_message_builder=_build_worker_workflow_message,
            allowed_tools=all_tools,
            max_iterations=30,
            depends_on=["bp_structural_index"],
            required_artifacts=["worker_workflow.json"],
            blocking=True,
            parallel_group="explore",
        ),
        Phase(
            name="worker_math",
            description="Worker: math/algorithm decisions",
            system_prompt=prompts_v4.WORKER_MATH_SYSTEM,
            initial_message_builder=_build_worker_math_message,
            allowed_tools=[
                "read_file",
                "grep_codebase",
                "write_artifact",
                "get_skeleton",
                "list_by_type",
            ],
            max_iterations=40,
            depends_on=["bp_structural_index"],
            required_artifacts=["worker_math.json"],
            blocking=True,
            parallel_group="explore",
        ),
        # --- Synthesis ---
        Phase(
            name="bp_synthesis",
            description="Merge workers + classify decisions",
            system_prompt=prompts_v4.BP_SYNTHESIS_SYSTEM,
            initial_message_builder=_build_synthesis_message,
            allowed_tools=[
                "read_file",
                "grep_codebase",
                "get_artifact",
                "write_artifact",
                "get_skeleton",
                "list_by_type",
            ],
            max_iterations=60,
            depends_on=[
                "worker_docs",
                "worker_arch",
                "worker_workflow",
                "worker_math",
            ],
            required_artifacts=["step2c_business_decisions.md"],
            blocking=True,
        ),
        # --- Assembly ---
        Phase(
            name="bp_assemble",
            description="Assemble blueprint YAML + use cases",
            system_prompt=prompts_v4.BP_ASSEMBLE_SYSTEM,
            initial_message_builder=_build_assemble_message_v4(blueprint_id),
            allowed_tools=[
                "read_file",
                "list_dir",
                "grep_codebase",
                "get_artifact",
                "write_artifact",
            ],
            max_iterations=60,
            depends_on=["bp_synthesis"],
            quality_gate=_blueprint_yaml_gate,
            required_artifacts=["blueprint.yaml"],
            blocking=True,
        ),
        # --- Post-processing ---
        Phase(
            name="bp_consistency_check",
            description="Check BD type validity",
            system_prompt="",
            initial_message_builder=lambda s, r: "",
            requires_llm=False,
            python_handler=_step5_handler,
            depends_on=["bp_assemble"],
        ),
        Phase(
            name="bp_finalize",
            description="Promote blueprint to output/",
            system_prompt="",
            initial_message_builder=lambda s, r: "",
            requires_llm=False,
            python_handler=_finalize_handler,
            depends_on=["bp_consistency_check"],
        ),
    ]


# ===================================================================
# v5 Phase Factory — Instructor-driven synthesis + quality gate
# ===================================================================


def _safe_read(path: Path, default: str = "") -> str:
    """Read a file if it exists, return default otherwise."""
    try:
        return path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return default


def _bd_to_markdown(result: BDExtractionResult) -> str:
    """Convert a BDExtractionResult to Markdown for backward compatibility.

    Produces the same format as ``step2c_business_decisions.md`` so that
    bp_assemble can consume it unchanged.
    """
    lines = ["## Business Decision Report\n"]

    lines.append("### Business Decision Table\n")
    lines.append("| # | Content | Type | Rationale | Evidence | Stage |")
    lines.append("|---|---------|------|-----------|----------|-------|")
    for i, bd in enumerate(result.decisions, 1):
        # Escape pipes in content/rationale for markdown table
        content = bd.content.replace("|", "\\|")
        rationale = bd.rationale.replace("|", "\\|")
        status_marker = " [MISSING]" if bd.status == "missing" else ""
        lines.append(
            f"| {i} | {content}{status_marker} | {bd.type} | "
            f"{rationale} | {bd.evidence} | {bd.stage} |"
        )

    lines.append("\n### Summary by Type\n")
    for type_code, count in sorted(result.type_summary.items()):
        lines.append(f"- **{type_code}**: {count}")

    if result.missing_gaps:
        lines.append("\n### Missing Gaps\n")
        for gap in result.missing_gaps:
            sev = f" [{gap.severity}]" if gap.severity else ""
            lines.append(f"- **{gap.content}**{sev}: {gap.impact or 'N/A'}")

    return "\n".join(lines)


def _mean_char_count(decisions: list) -> float:
    """Mean character count of rationale across decisions."""
    if not decisions:
        return 0.0
    total = sum(len(d.rationale) for d in decisions)
    return total / len(decisions)


def _multi_type_ratio(decisions: list) -> float:
    """Fraction of decisions with multi-type annotation (contains '/')."""
    if not decisions:
        return 0.0
    multi = sum(1 for d in decisions if "/" in d.type)
    return multi / len(decisions)


def _build_step1_message(
    worker_arch: str,
    worker_workflow: str,
    worker_math: str,
    state: AgentState,
    worker_arch_deep: str = "",
) -> str:
    """Build user message for synthesis Step 1.

    NOTE: worker_verify and worker_audit are NOT injected here.
    They are consumed by bp_enrich (audit_checklist_summary) and
    bp_quality_gate, not by synthesis. Keeping synthesis input lean
    ensures Step 1 completes in ~5 min instead of 15+.
    """
    labels = state.subdomain_labels or ["TRD"]
    checklist = prompts_v5.build_subdomain_checklist(labels)

    parts = [
        f"## Subdomain Labels: {labels}\n",
    ]

    if worker_arch:
        parts.append(f"## Architecture Evidence Packet (JSON)\n\n{worker_arch}\n")
    else:
        parts.append("## Architecture Evidence Packet\n\n(worker_arch failed — unavailable)\n")

    if worker_arch_deep:
        parts.append(f"## Architecture Deep-Dive Findings (JSON)\n\n{worker_arch_deep}\n")

    if worker_workflow:
        parts.append(f"## Workflow Decisions (JSON)\n\n{worker_workflow}\n")
    else:
        parts.append("## Workflow Decisions\n\n(worker_workflow failed — unavailable)\n")

    if worker_math:
        parts.append(f"## Math/Algorithm Decisions (JSON)\n\n{worker_math}\n")
    else:
        parts.append("## Math Decisions\n\n(No math worker output — project may lack math files)\n")

    # Anomaly rules
    anomaly_rules = []
    if any(l in labels for l in ["TRD", "PRC", "RSK"]):
        anomaly_rules.append(
            "ANOMALY: M=0 in quant project → re-check for scipy, sklearn, "
            "numpy.linalg, statsmodels."
        )
    if any(l in labels for l in ["TRD", "A_STOCK"]):
        anomaly_rules.append("ANOMALY: DK=0 in A-stock → search for T+1, 涨跌停, 印花税, ST.")
    if anomaly_rules:
        parts.append("## Anomaly Detection Rules")
        parts.extend(f"- {r}" for r in anomaly_rules)

    parts.append(f"\n## Finance Checklist\n{checklist}")

    return "\n".join(parts)


_STEP2_RATIONALE_THRESHOLD = 60  # chars below which rationale needs enhancement


def _find_needy_bds(
    decisions: list,
) -> tuple[list, list]:
    """Split decisions into (needy, good) based on rationale quality.

    needy = non-T decisions where rationale < threshold or status == "missing".
    good  = T decisions + non-T decisions that already meet the bar.

    Returns (needy_bds, good_bds).
    """
    needy: list = []
    good: list = []
    for bd in decisions:
        if bd.type == "T":
            good.append(bd)
        elif bd.status == "missing" or len(bd.rationale or "") < _STEP2_RATIONALE_THRESHOLD:
            needy.append(bd)
        else:
            good.append(bd)
    return needy, good


def _build_step2_message(
    needy_bds: list,
    needy_gaps: list,
    worker_docs: str,
    state: AgentState,
) -> str:
    """Build user message for synthesis Step 2 (patch-only mode).

    Only sends the BDs that actually need enhancement (needy_bds).
    The model is instructed to return ONLY these BDs as a patch;
    good BDs are merged back in the handler without a round-trip.

    Args:
        needy_bds: Non-T decisions with shallow/missing rationale.
        needy_gaps: Missing-gap decisions that also need enhancement.
        worker_docs: Content from worker_docs artifact.
        state: Current agent state (unused directly, kept for signature parity).
    """
    from collections import Counter as _Counter

    patch_decisions = needy_bds + needy_gaps
    patch_summary = dict(_Counter(d.type for d in patch_decisions))
    patch_result = BDExtractionResult(
        decisions=patch_decisions,
        type_summary=patch_summary,
        missing_gaps=needy_gaps,
    )
    bd_json = patch_result.model_dump_json(indent=2)

    parts = [
        f"## Business Decisions Needing Enhancement (patch set, {len(patch_decisions)} decisions)\n\n{bd_json}\n",
    ]

    # Truncate docs to 6K chars to limit context size
    _MAX_DOCS = 6000
    if worker_docs:
        docs_trunc = worker_docs[:_MAX_DOCS]
        if len(worker_docs) > _MAX_DOCS:
            docs_trunc += "\n\n... (truncated)"
        parts.append(f"## Documentation Context\n\n{docs_trunc}\n")
    else:
        parts.append(
            "## Documentation Context\n\n"
            "(worker_docs failed — no documentation available. "
            "Enhance rationale using code evidence only.)\n"
        )

    parts.append(
        "Enhance the rationale for EACH decision in the patch set above "
        "(≥ 60 chars, WHY + BOUNDARY). Review multi-type annotations. "
        "Enhance missing gap descriptions.\n\n"
        "IMPORTANT: Return ONLY the decisions in this patch set. "
        "Do NOT echo unmodified decisions. Do NOT return T-type decisions. "
        "Preserve each decision's original id field exactly."
    )

    return "\n".join(parts)


def build_blueprint_phases_v5(
    blueprint_id: str,
    *,
    agent: ExtractionAgent,
    strict_quality_gate: bool = True,
) -> list[Phase]:
    """Build the v5/v6 blueprint extraction phases.

    v6 architecture (20 phases):
    - Pre-processing: 5 Python phases (fingerprint, clone, index, sources, manifest)
    - Parallel workers: 6+2 agentic phases (arch/workflow/math/deep/docs/resource + verify/audit)
    - Synthesis v5: 1 Python phase using Instructor (3-step structured call)
    - Evaluation: 1 agentic phase (independent BD verification)
    - Post-processing: 2 Python phases (UC extract + coverage gap, blocking)
    - Assembly + Enrich: 2 Python phases
    - Quality gate: 1 Python phase (BQ-01~09, strict by default)
    - Finalization: 2 Python phases

    v6 key changes vs v5.2:
    - worker_resource: dedicated resource extraction Worker (parallel)
    - bp_evaluate: independent Evaluator (Sprint-contract verification)
    - worker_audit: blocking=True, injected into synthesis Step 3
    - bp_uc_extract/bp_coverage_gap: blocking=True
    - Quality gate: strict=True by default, fix_hints in BQ messages

    Args:
        blueprint_id: The blueprint being extracted.
        agent: The ExtractionAgent for Instructor calls in synthesis.
        strict_quality_gate: When True, quality gate failure halts the pipeline.
            Default True (v6).  Set False only for debugging.
    """

    # ----- Synthesis v5 handler (closure captures agent) -----

    async def _synthesis_v5_handler(
        state: AgentState,
        repo_path: Path,
    ) -> PhaseResult:
        """Three-step Instructor synthesis: Extract+Classify → Enhance → Interactions."""
        artifacts_dir = Path(state.run_dir) / "artifacts"
        total_tokens = 0

        # Read worker artifacts (tolerant of missing non-blocking workers)
        worker_arch = _safe_read(artifacts_dir / "worker_arch.json")
        worker_arch_deep = _safe_read(artifacts_dir / "worker_arch_deep.json")
        worker_workflow = _safe_read(artifacts_dir / "worker_workflow.json")
        worker_math = _safe_read(artifacts_dir / "worker_math.json")
        worker_docs = _safe_read(artifacts_dir / "worker_docs.md")
        # v6: worker_audit is now blocking=True and injected into Step 3
        # for deterministic missing-gap generation.
        worker_audit = _safe_read(artifacts_dir / "worker_audit.md")
        # v6: worker_resource provides resource inventory for replaceable_points
        worker_resource = _safe_read(artifacts_dir / "worker_resource.json")

        if not worker_arch and not worker_workflow:
            return PhaseResult(
                phase_name="bp_synthesis_v5",
                status="error",
                error="Both worker_arch and worker_workflow are empty — cannot synthesize",
            )

        # Step 1: Extract BD list + classify types
        step1_msg = _build_step1_message(
            worker_arch,
            worker_workflow,
            worker_math,
            state,
            worker_arch_deep=worker_arch_deep,
        )
        step1_result, tokens1 = await agent.run_structured_call(
            prompts_v5.SYNTHESIS_V5_STEP1_SYSTEM,
            step1_msg,
            BDExtractionResult,
        )
        total_tokens += tokens1

        if isinstance(step1_result, RawFallback):
            # L3 fallback — save raw text and fail
            (artifacts_dir / "synthesis_v5_raw.txt").write_text(
                step1_result.text,
                encoding="utf-8",
            )
            return PhaseResult(
                phase_name="bp_synthesis_v5",
                status="error",
                total_tokens=total_tokens,
                error=f"Synthesis Step 1 returned raw fallback ({step1_result.stage})",
                final_text=step1_result.text,
            )

        logger.info(
            "Synthesis Step 1: %d decisions, %d missing gaps",
            len(step1_result.decisions),
            len(step1_result.missing_gaps),
        )

        # Step 2: Enhance rationale with docs context (patch-only mode)
        # Only send BDs that actually need enhancement; merge patch back locally.
        _STEP2_SKIP_THRESHOLD = 2  # skip Step 2 if ≤ this many BDs need it
        needy_bds, good_bds = _find_needy_bds(step1_result.decisions)
        needy_gaps = [
            g
            for g in step1_result.missing_gaps
            if g.status == "missing" and len(g.rationale or "") < _STEP2_RATIONALE_THRESHOLD
        ]
        good_gaps = [g for g in step1_result.missing_gaps if g not in needy_gaps]

        logger.info(
            "Synthesis Step 2 pre-filter: %d needy BDs, %d good BDs (threshold=%d chars)",
            len(needy_bds),
            len(good_bds),
            _STEP2_RATIONALE_THRESHOLD,
        )

        if len(needy_bds) + len(needy_gaps) <= _STEP2_SKIP_THRESHOLD:
            logger.info(
                "Step 2 skipped: only %d BDs need enhancement (≤ threshold %d)",
                len(needy_bds),
                _STEP2_SKIP_THRESHOLD,
            )
            step2_final = step1_result
        else:
            step2_msg = _build_step2_message(needy_bds, needy_gaps, worker_docs, state)
            step2_result, tokens2 = await agent.run_structured_call(
                prompts_v5.SYNTHESIS_V5_STEP2_SYSTEM,
                step2_msg,
                BDExtractionResult,
                max_tokens=65536,
            )
            total_tokens += tokens2

            # If Step 2 fails, fall back to Step 1 result (degraded but usable)
            if isinstance(step2_result, RawFallback):
                logger.warning(
                    "Synthesis Step 2 returned raw fallback — using Step 1 result",
                )
                step2_final = step1_result
            else:
                # Patch merge: accept IDs from needy set + RC-split derivatives.
                # RC/B split rule (prompts_v5) can produce new IDs like BD-066a
                # from parent BD-066. These are accepted if their prefix matches
                # a needy ID.
                from collections import Counter as _Counter

                needy_ids = {bd.id for bd in needy_bds}
                needy_gap_ids = {g.id for g in needy_gaps}

                def _is_accepted_id(bd_id: str) -> bool:
                    """Accept exact needy ID or RC-split derivative (BD-066a from BD-066)."""
                    if bd_id in needy_ids:
                        return True
                    # Check if this is a split derivative: strip trailing letter(s)
                    # e.g., BD-066a → BD-066, BD-066b → BD-066
                    base = re.sub(r"[a-z]+$", "", bd_id)
                    return base in needy_ids and base != bd_id

                merged_by_id: dict = {bd.id: bd for bd in good_bds}
                foreign_count = 0
                split_count = 0
                for bd in step2_result.decisions:
                    if bd.id in needy_ids:
                        merged_by_id[bd.id] = bd  # patch overrides
                    elif _is_accepted_id(bd.id):
                        merged_by_id[bd.id] = bd  # RC-split derivative
                        split_count += 1
                    else:
                        foreign_count += 1
                if split_count:
                    logger.info(
                        "Step 2 accepted %d RC-split derivative BDs",
                        split_count,
                    )
                if foreign_count:
                    logger.warning(
                        "Step 2 returned %d foreign BD IDs (not in needy set) — ignored",
                        foreign_count,
                    )
                # Re-add any needy BDs whose id was NOT returned by Step 2
                missing_patch = 0
                for bd in needy_bds:
                    if bd.id not in merged_by_id:
                        merged_by_id[bd.id] = bd
                        missing_patch += 1
                if missing_patch:
                    logger.info(
                        "Step 2 omitted %d needy BDs — kept Step 1 versions",
                        missing_patch,
                    )
                merged_decisions = list(merged_by_id.values())

                # Gaps: only accept needy gap IDs
                merged_gaps_by_id: dict = {g.id: g for g in good_gaps}
                for g in step2_result.missing_gaps:
                    if g.id in needy_gap_ids:
                        merged_gaps_by_id[g.id] = g
                for g in needy_gaps:
                    if g.id not in merged_gaps_by_id:
                        merged_gaps_by_id[g.id] = g
                merged_gaps = list(merged_gaps_by_id.values())

                type_counts = _Counter(d.type for d in merged_decisions)
                step2_final = BDExtractionResult(
                    decisions=merged_decisions,
                    type_summary=dict(type_counts),
                    missing_gaps=merged_gaps,
                )
                logger.info(
                    "Synthesis Step 2 patch merge: %d total decisions "
                    "(%d patched from model + %d good unchanged), %d missing gaps",
                    len(step2_final.decisions),
                    len(step2_result.decisions),
                    len(good_bds),
                    len(step2_final.missing_gaps),
                )

        # Step 3: Decision interaction analysis + audit-driven missing gaps
        audit_section = ""
        if worker_audit:
            audit_section = (
                "\n\n## Audit Checklist Findings (20-item finance universal + subdomain)\n\n"
                "The following audit results were produced by an independent Worker.\n"
                "For each ❌ or ⚠️ item NOT already covered by existing BDs, you MUST:\n"
                "1. Generate a new BD with status=missing, known_gap=true\n"
                "2. Set severity based on audit finding severity\n"
                "3. Set impact to describe the consequence of the gap\n\n"
                f"{worker_audit[:6000].rsplit(chr(10), 1)[0]}\n"
                f"... (truncated, {max(0, len(worker_audit) - 6000)} more chars)\n"
            )
        step3_msg = (
            f"## Enhanced BD List from Step 2\n\n"
            f"{step2_final.model_dump_json(indent=2)}\n\n"
            f"Analyze decision interactions: amplification, contradiction, "
            f"hidden dependency, risk cascade. Target ≥5 interactions."
            f"{audit_section}"
        )
        step3_result, tokens3 = await agent.run_structured_call(
            prompts_v5.SYNTHESIS_V5_STEP3_SYSTEM,
            step3_msg,
            BDExtractionResult,
            max_tokens=32768,
        )
        total_tokens += tokens3

        # Merge Step 3 interaction BDs into Step 2 result
        if isinstance(step3_result, RawFallback):
            logger.warning(
                "Synthesis Step 3 returned raw fallback — skipping interactions",
            )
            final_result = step2_final
        else:
            # Merge: Step 2 decisions + Step 3 interaction decisions
            merged_decisions = list(step2_final.decisions)
            existing_ids = {d.id for d in merged_decisions}
            interaction_count = 0
            for bd in step3_result.decisions:
                if bd.id not in existing_ids:
                    merged_decisions.append(bd)
                    existing_ids.add(bd.id)
                    interaction_count += 1

            # Preserve missing_gaps from step2_final (includes Step 1's gaps).
            # Do NOT rebuild from decisions — the LLM may put gaps in
            # missing_gaps without setting status="missing" on the
            # corresponding decision, causing the list to drift to 0.
            merged_missing_ids = {g.id for g in step2_final.missing_gaps}
            merged_missing = list(step2_final.missing_gaps)
            # Also add any Step 3 interaction BDs marked as missing
            for bd in step3_result.decisions:
                if bd.status == "missing" and bd.id not in merged_missing_ids:
                    merged_missing.append(bd)
                    merged_missing_ids.add(bd.id)
            from collections import Counter as _Counter

            type_counts = _Counter(d.type for d in merged_decisions)

            final_result = BDExtractionResult(
                decisions=merged_decisions,
                type_summary=dict(type_counts),
                missing_gaps=merged_missing,
            )
            logger.info(
                "Synthesis Step 3: +%d interaction BDs → total %d decisions",
                interaction_count,
                len(final_result.decisions),
            )

        # Write structured artifact
        bd_json = final_result.model_dump_json(indent=2)
        (artifacts_dir / "bd_list.json").write_text(bd_json, encoding="utf-8")

        # Write backward-compatible markdown for bp_assemble
        bd_md = _bd_to_markdown(final_result)
        (artifacts_dir / "step2c_business_decisions.md").write_text(
            bd_md,
            encoding="utf-8",
        )

        return PhaseResult(
            phase_name="bp_synthesis_v5",
            status="completed",
            iterations=2,
            total_tokens=total_tokens,
            final_text=bd_json,
        )

    # ----- Assembly v5 handler (Instructor-driven) -----

    async def _assemble_instructor_handler(
        state: AgentState,
        repo_path: Path,
    ) -> PhaseResult:
        """Assemble blueprint.yaml via Instructor structured call.

        Replaces the agentic assembly loop with a single structured call
        that enforces BlueprintAssembleResult schema.
        """
        import yaml as _yaml

        artifacts_dir = Path(state.run_dir) / "artifacts"
        total_tokens = 0

        # --- Read input artifacts ---
        def _safe_read_local(path: Path) -> str:
            if path.exists():
                return path.read_text(encoding="utf-8")
            return f"(artifact not found: {path.name})"

        worker_arch = _safe_read_local(artifacts_dir / "worker_arch.json")
        worker_arch_deep = _safe_read_local(artifacts_dir / "worker_arch_deep.json")
        source_ctx = _safe_read_local(artifacts_dir / "source_context.md")

        user_msg = (
            f"## Architecture Evidence Packet (JSON)\n\n{worker_arch}\n\n"
            f"## Architecture Deep-Dive Findings (JSON)\n\n{worker_arch_deep}\n\n"
            f"## Project Metadata\n\n{source_ctx}\n\n"
            f"Blueprint ID: {state.blueprint_id}\n"
        )

        # --- Instructor call ---
        from .schemas_v5 import BlueprintAssembleResult

        result, tokens = await agent.run_structured_call(
            prompts_v5.BP_ASSEMBLE_V5_SYSTEM,
            user_msg,
            BlueprintAssembleResult,
            max_tokens=65536,
        )
        total_tokens += tokens

        if isinstance(result, RawFallback):
            (artifacts_dir / "assemble_raw.txt").write_text(
                result.text,
                encoding="utf-8",
            )
            return PhaseResult(
                phase_name="bp_assemble",
                status="error",
                total_tokens=total_tokens,
                error=f"Assembly returned raw fallback ({result.stage})",
                final_text=result.text[:500],
            )

        # --- Build blueprint dict from structured result ---
        bp: dict = {
            "id": state.blueprint_id,
            "name": result.name,
            "sop_version": "3.2",  # bp_enrich will upgrade to 3.4
            "source": {
                "projects": [],
                "extraction_method": "semi_auto",
            },
            "applicability": result.applicability,
            "stages": [s.model_dump(exclude_none=True) for s in result.stages],
            "data_flow": [e.model_dump() for e in result.data_flow],
            "global_contracts": result.global_contracts,
            "business_decisions": [],  # Injected by bp_enrich P3
            "known_use_cases": [],  # Injected by bp_enrich P9
        }

        # --- Write blueprint.yaml ---
        from datetime import date as _date

        _today = _date.today().isoformat()
        content = (
            f"# Extraction pipeline: SOP v3.4 (v5.2 agent, Instructor synthesis + evidence packet)\n"
            f"# Extracted: {_today}, model: {agent._model_id}\n"
            f"# Source: {state.repo_path} @ {state.commit_hash or 'unknown'}\n"
        )
        content += _yaml.dump(
            bp,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
            width=100,
        )

        (artifacts_dir / "blueprint.yaml").write_text(content, encoding="utf-8")

        stage_count = len(result.stages)
        edge_count = len(result.data_flow)
        gc_count = len(result.global_contracts)

        logger.info(
            "bp_assemble (Instructor): %d stages, %d edges, %d contracts, %d tokens",
            stage_count,
            edge_count,
            gc_count,
            total_tokens,
        )

        return PhaseResult(
            phase_name="bp_assemble",
            status="completed",
            total_tokens=total_tokens,
            final_text=f"Assembled: {stage_count} stages, {edge_count} edges, {gc_count} contracts",
        )

    # ----- Quality gate handler -----

    async def _quality_gate_handler(
        state: AgentState,
        repo_path: Path,
    ) -> PhaseResult:
        """SOP v3.4 quality gate — BQ-01..BQ-09 hard gates + warnings.

        Hard gates (BQ-01~04): block pipeline when strict_quality_gate=True.
        Warnings (BQ-05~09): always logged, never block.
        """
        artifacts_dir = Path(state.run_dir) / "artifacts"
        bd_path = artifacts_dir / "bd_list.json"

        if not bd_path.exists():
            return PhaseResult(
                phase_name="bp_quality_gate",
                status="error",
                error="bd_list.json not found",
            )

        try:
            bd_result = BDExtractionResult.model_validate_json(
                bd_path.read_text(encoding="utf-8"),
            )
        except Exception as exc:
            return PhaseResult(
                phase_name="bp_quality_gate",
                status="error",
                error=f"Failed to parse bd_list.json: {exc}",
            )

        non_t = [bd for bd in bd_result.decisions if bd.type != "T"]
        all_bds = bd_result.decisions

        # ---- Metrics ----
        rationale_depth = _mean_char_count(non_t)
        multi_type_ratio = _multi_type_ratio(non_t)
        # Count missing BDs from both decisions and missing_gaps fields.
        # The model may place gaps only in missing_gaps without duplicating
        # them in decisions, so we must count both (deduplicated by ID).
        _missing_ids = {bd.id for bd in bd_result.decisions if bd.status == "missing"}
        _missing_ids |= {g.id for g in bd_result.missing_gaps}
        missing_gap_count = len(_missing_ids)
        stages = state.extra.get("_bp_stages", []) if hasattr(state, "extra") else []
        # Try to read stages from the enriched blueprint for BQ-05/07/09
        bp_path = artifacts_dir / "blueprint.yaml"
        bp_data: dict = {}
        if bp_path.exists():
            try:
                import yaml as _yaml

                bp_data = _yaml.safe_load(bp_path.read_text(encoding="utf-8")) or {}
            except Exception:
                pass
        if not stages and isinstance(bp_data.get("stages"), list):
            stages = bp_data["stages"]

        stage_count = len(stages) if isinstance(stages, list) else 0

        # Evidence coverage (from _enrich_meta if available)
        evidence_coverage = 0.0
        meta = bp_data.get("_enrich_meta", {}) if isinstance(bp_data, dict) else {}
        if isinstance(meta, dict):
            evidence_coverage = meta.get("evidence_coverage_ratio", 0.0)

        # BD type diversity (non-T)
        non_t_types: set[str] = set()
        for bd in non_t:
            for part in bd.type.split("/"):
                non_t_types.add(part)
        non_t_types.discard("T")

        # Subdomain-aware type diversity (BQ-07 enhanced)
        labels = state.subdomain_labels or []
        expected_types: set[str] = set()
        if any(l in labels for l in ["TRD", "PRC", "RSK"]):
            expected_types.add("M")
        if any(l in labels for l in ["CRD", "CMP"]):
            expected_types.add("RC")
        if any(l in labels for l in ["TRD", "A_STOCK"]):
            expected_types.add("DK")
        missing_expected = expected_types - non_t_types

        # Vague word ratio
        vague_count = sum(
            1
            for bd in (bp_data.get("business_decisions") or [])
            if isinstance(bd, dict) and bd.get("vague_rationale")
        )
        total_bd_count = len(bp_data.get("business_decisions") or all_bds)
        vague_ratio = (vague_count / total_bd_count) if total_bd_count else 0.0

        # Audit checklist
        has_audit = bool(bp_data.get("audit_checklist_summary"))

        # ---- Hard gates (BQ-01, BQ-02, BQ-04) + Warnings (BQ-03, BQ-05~09) ----
        hard_issues: list[str] = []
        warnings: list[str] = []
        checks: dict[str, bool] = {}
        details: dict[str, str] = {}

        # BQ fix hints — embedded repair instructions (Harness Engineering pattern)
        _BQ_FIX_HINTS = {
            "BQ-01": (
                "Fix: Re-examine uncovered directories for business decisions. "
                "Focus on default parameter values (BA), regulatory rules (RC), "
                "and mathematical model choices (M)."
            ),
            "BQ-02": (
                "Fix: For each shallow BD, add: (1) WHY this approach was chosen "
                "over alternatives, (2) BOUNDARY conditions under which it breaks."
            ),
            "BQ-03": (
                "Fix: Review each single-type BD and evaluate dual nature — "
                "B decisions often have BA implications, M decisions often have DK context."
            ),
            "BQ-04": (
                "Fix: Cross-reference audit checklist findings against BD list. "
                "Any audit ❌/⚠️ item not covered by existing BDs should generate "
                "a missing-gap BD with status=missing, known_gap=true."
            ),
        }

        # BQ-01: non-T BD count >= 5
        checks["BQ-01_bd_count"] = len(non_t) >= 5
        details["BQ-01_bd_count"] = f"non_T={len(non_t)} (target ≥5)"
        if not checks["BQ-01_bd_count"]:
            hard_issues.append(f"BQ-01 FAIL: non_T={len(non_t)} < 5. {_BQ_FIX_HINTS['BQ-01']}")
        else:
            logger.info("BQ-01 PASS: non_T=%d ≥ 5", len(non_t))

        # BQ-02: rationale depth >= 40 chars
        checks["BQ-02_rationale_depth"] = rationale_depth >= 40
        details["BQ-02_rationale_depth"] = (
            f"mean={rationale_depth:.0f} chars (target ≥40, {len(non_t)} non-T)"
        )
        if not checks["BQ-02_rationale_depth"]:
            hard_issues.append(
                f"BQ-02 FAIL: mean_rationale={rationale_depth:.0f} < 40. {_BQ_FIX_HINTS['BQ-02']}"
            )
        else:
            logger.info("BQ-02 PASS: mean_rationale=%.0f ≥ 40", rationale_depth)

        # BQ-03: multi-type ratio >= 30% — DEMOTED to warning (v6)
        # Multi-type annotation is a quality-enhancement metric, not a
        # correctness baseline.  MiniMax M2.7 consistently produces < 10%
        # multi-type ratio; blocking the pipeline on this is counterproductive.
        checks["BQ-03_multi_type_ratio"] = multi_type_ratio >= 0.30
        details["BQ-03_multi_type_ratio"] = f"ratio={multi_type_ratio:.1%} (target ≥30%)"
        if not checks["BQ-03_multi_type_ratio"]:
            # Moved from hard_issues to warnings — pipeline continues
            warnings.append(
                f"BQ-03 WARN: multi_type={multi_type_ratio:.1%} < 30%. {_BQ_FIX_HINTS['BQ-03']}"
            )
        else:
            logger.info("BQ-03 PASS: multi_type=%.1f%%", multi_type_ratio * 100)

        # BQ-04: missing gaps >= 3
        checks["BQ-04_missing_gaps"] = missing_gap_count >= 3
        details["BQ-04_missing_gaps"] = f"count={missing_gap_count} (target ≥3)"
        if not checks["BQ-04_missing_gaps"]:
            hard_issues.append(
                f"BQ-04 FAIL: missing_gaps={missing_gap_count} < 3. {_BQ_FIX_HINTS['BQ-04']}"
            )
        else:
            logger.info("BQ-04 PASS: missing_gaps=%d ≥ 3", missing_gap_count)

        # ---- Warnings (BQ-05 ~ BQ-09) ----

        # BQ-05: stages count in [2, 30]
        checks["BQ-05_stages_range"] = 2 <= stage_count <= 30
        details["BQ-05_stages_range"] = f"stages={stage_count} (target 2..30)"
        if not checks["BQ-05_stages_range"]:
            warnings.append(f"BQ-05 WARN: stages={stage_count} outside [2, 30]")

        # BQ-06: evidence coverage >= 50%
        checks["BQ-06_evidence_coverage"] = evidence_coverage >= 0.50
        details["BQ-06_evidence_coverage"] = f"coverage={evidence_coverage:.1%} (target ≥50%)"
        if not checks["BQ-06_evidence_coverage"]:
            warnings.append(f"BQ-06 WARN: evidence_coverage={evidence_coverage:.1%} < 50%")

        # BQ-07: BD type diversity (subdomain-aware)
        type_diverse = len(non_t_types) >= 2 and not missing_expected
        checks["BQ-07_type_diversity"] = type_diverse
        detail_07 = f"non_T_types={sorted(non_t_types)}"
        if missing_expected:
            detail_07 += f", missing_expected={sorted(missing_expected)} for labels={labels}"
        details["BQ-07_type_diversity"] = detail_07
        if not type_diverse:
            warnings.append(f"BQ-07 WARN: {detail_07}")

        # BQ-08: vague word ratio <= 30%
        checks["BQ-08_vague_ratio"] = vague_ratio <= 0.30
        details["BQ-08_vague_ratio"] = (
            f"vague={vague_count}/{total_bd_count} ({vague_ratio:.1%}, target ≤30%)"
        )
        if not checks["BQ-08_vague_ratio"]:
            warnings.append(f"BQ-08 WARN: vague_ratio={vague_ratio:.1%} > 30%")

        # BQ-09: audit checklist present
        checks["BQ-09_audit_checklist"] = has_audit
        details["BQ-09_audit_checklist"] = "present" if has_audit else "MISSING"
        if not checks["BQ-09_audit_checklist"]:
            warnings.append("BQ-09 WARN: audit_checklist_summary missing")

        # ---- Emit warnings ----
        for w in warnings:
            logger.warning("bp_quality_gate: %s", w)

        # ---- Build result ----
        all_passed = not hard_issues and not warnings
        hard_passed = not hard_issues
        gate_result = QualityGateResult(
            passed=hard_passed,
            checks=checks,
            details=details,
        )

        (artifacts_dir / "quality_gate_result.json").write_text(
            gate_result.model_dump_json(indent=2),
            encoding="utf-8",
        )

        if hard_issues:
            logger.warning(
                "Quality gate HARD FAIL: %s",
                "; ".join(hard_issues),
            )
            if strict_quality_gate:
                return PhaseResult(
                    phase_name="bp_quality_gate",
                    status="error",
                    error=f"Quality gate hard fail: {'; '.join(hard_issues)}",
                    final_text=gate_result.model_dump_json(indent=2),
                )

        status_msg = (
            "ALL PASS"
            if all_passed
            else (f"{'HARD FAIL' if hard_issues else 'PASS'}, {len(warnings)} warnings")
        )
        logger.info("Quality gate: %s", status_msg)
        return PhaseResult(
            phase_name="bp_quality_gate",
            status="completed",
            final_text=gate_result.model_dump_json(indent=2),
        )

    # ----- Phase A: Coverage manifest (deterministic pre-scan) -----

    async def _coverage_manifest_handler(
        state: AgentState,
        repo_path: Path,
    ) -> PhaseResult:
        """Generate a deterministic coverage checklist from structural index.

        Enumerates ALL subdirectories, example files, and base classes so
        Workers know exactly what to visit — no stochastic exploration gaps.
        """
        artifacts_dir = Path(state.run_dir) / "artifacts"
        index_path = artifacts_dir / "repo_index.json"

        if not index_path.exists():
            return PhaseResult(
                phase_name="bp_coverage_manifest",
                status="error",
                error="repo_index.json not found",
            )

        index = json.loads(index_path.read_text(encoding="utf-8"))
        files = index.get("files", {})

        # 1. All subdirectories with Python code
        subdirs: set[str] = set()
        for fpath in files:
            parts = fpath.split("/")
            if len(parts) > 1:
                subdirs.add("/".join(parts[:-1]))
        must_visit_dirs = sorted(subdirs)

        # 2. Base classes with __init__ defaults (potential BA decisions)
        base_classes: list[dict] = []
        for fpath, finfo in files.items():
            for cls in finfo.get("classes", []):
                cls_name = cls if isinstance(cls, str) else cls.get("name", "")
                if cls_name and any(
                    kw in fpath.lower() for kw in ["contract", "base", "mixin", "abstract"]
                ):
                    base_classes.append({"file": fpath, "class": cls_name})

        # 3. All example files (100% enumeration — scan repo directly)
        # structural_index "examples" field may only have notebooks/md,
        # so we scan the actual repo for Python example files
        actual_repo = Path(state.repo_path)
        examples: list[str] = []
        for pattern in ["examples/**/*.py", "notebooks/**/*.py", "tutorials/**/*.py"]:
            for p in actual_repo.glob(pattern):
                if "__pycache__" not in str(p) and "__init__" not in p.name:
                    examples.append(str(p.relative_to(actual_repo)))
        examples = sorted(set(examples))

        entry_points = sorted(index.get("entry_points", []))

        # 4. Architecture grep patterns
        arch_patterns = [
            "sell.*buy|buy.*sell",
            "shift\\(",
            "fill_gap",
            "due_timestamp",
            "rich_mode",
            "filter_result",
            "@abstractmethod",
            "position_pct|position_control",
            "profit_threshold",
        ]

        manifest = {
            "must_visit_dirs": must_visit_dirs,
            "base_classes": base_classes[:30],
            "examples": examples,
            "entry_points": entry_points,
            "arch_patterns": arch_patterns,
            "stats": {
                "total_dirs": len(must_visit_dirs),
                "total_examples": len(examples),
                "total_base_classes": len(base_classes),
            },
        }

        manifest_path = artifacts_dir / "coverage_manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        # Store in state.extra for worker message builders
        state.extra["coverage_manifest"] = manifest

        logger.info(
            "Coverage manifest: %d dirs, %d examples, %d base classes",
            len(must_visit_dirs),
            len(examples),
            len(base_classes),
        )

        return PhaseResult(
            phase_name="bp_coverage_manifest",
            status="completed",
            final_text=json.dumps(manifest["stats"]),
        )

    # ----- Phase B: UC extraction (deterministic) -----

    async def _uc_extract_handler(
        state: AgentState,
        repo_path: Path,
    ) -> PhaseResult:
        """Extract use cases deterministically from all example files."""
        artifacts_dir = Path(state.run_dir) / "artifacts"

        # Read coverage manifest for example list
        manifest_path = artifacts_dir / "coverage_manifest.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            examples = manifest.get("examples", [])
        else:
            # Fallback: scan repo directly (same patterns as manifest)
            examples = []
            for pattern in ["examples/**/*.py", "notebooks/**/*.py", "tutorials/**/*.py"]:
                examples.extend(
                    str(p.relative_to(repo_path))
                    for p in repo_path.glob(pattern)
                    if "__pycache__" not in str(p)
                )

        if not examples:
            logger.warning("bp_uc_extract: no example files found")
            return PhaseResult(
                phase_name="bp_uc_extract",
                status="completed",
                final_text="No examples found",
            )

        # Read head of each example file (cap at 100 for context limits)
        if len(examples) > 100:
            logger.warning("bp_uc_extract: %d examples, capping at 100", len(examples))
        file_summaries: list[dict] = []
        for ex_path in examples[:100]:
            full_path = repo_path / ex_path
            if not full_path.exists():
                continue
            try:
                lines = full_path.read_text(encoding="utf-8", errors="ignore").split("\n")
                head = "\n".join(lines[:40])
                # Extract entry point hints
                has_main = any("if __name__" in l or "def main" in l for l in lines)
                imports = [l for l in lines[:20] if l.strip().startswith(("import ", "from "))]
                file_summaries.append(
                    {
                        "file": ex_path,
                        "head": head,
                        "has_main": has_main,
                        "imports": imports[:5],
                        "total_lines": len(lines),
                    }
                )
            except Exception:
                continue

        if not file_summaries:
            return PhaseResult(
                phase_name="bp_uc_extract",
                status="completed",
                final_text="No readable examples",
            )

        # Build prompt for Instructor (using dedicated UC schema)
        summaries_text = ""
        for i, fs in enumerate(file_summaries, 1):
            summaries_text += (
                f"\n### File {i}: {fs['file']} ({fs['total_lines']} lines"
                f"{', has __main__' if fs['has_main'] else ''})\n"
                f"```python\n{fs['head']}\n```\n"
            )

        from .schemas_v5 import RawFallback as _RF

        uc_prompt = (
            "For each example file below, generate a structured use case.\n"
            "Fields per use case:\n"
            "- id: UC-101, UC-102, ...\n"
            "- name: short descriptive name (e.g. 'MACD Gold Cross Day Trader')\n"
            "- source: the file path (e.g. 'examples/trader/macd_day_trader.py')\n"
            "- uc_type: one of trading_strategy/screening/data_pipeline/monitoring/"
            "live_trading/reporting/research_analysis/ml_prediction/builtin_factor/extension_example\n"
            "- business_problem: what business problem it solves (1-2 sentences)\n"
            "- intent_keywords: 3-5 keywords for matching user intent\n"
            "- negative_keywords: keywords of OTHER use cases that could be confused with this one\n"
            "- disambiguation: if a user's query matches multiple UCs, what question should we ask to disambiguate?\n"
            "- data_domain: market_data / financial_data / holding_data / trading_data / mixed\n"
            "- stage: which pipeline stage (e.g. 'data_collection', 'factor_computation')\n\n"
            f"Example files to process:\n{summaries_text}"
        )

        result, tokens = await agent.run_structured_call(
            "You extract structured use case descriptions from source code examples.",
            uc_prompt,
            UCExtractionResult,
            max_tokens=65536,
        )

        if isinstance(result, _RF):
            logger.warning("bp_uc_extract: Instructor failed, raw fallback")
            return PhaseResult(
                phase_name="bp_uc_extract",
                status="completed",
                total_tokens=tokens,
                final_text="UC extraction returned raw fallback",
            )

        # Convert to dict format for uc_list.json
        uc_list = []
        for uc in result.use_cases:
            entry = {
                "id": uc.id,
                "name": uc.name,
                "source": uc.source,
                "type": uc.uc_type,
                "business_problem": uc.business_problem,
                "intent_keywords": uc.intent_keywords,
                "stage": uc.stage,
            }
            # Include disambiguation fields when present
            if uc.negative_keywords:
                entry["negative_keywords"] = uc.negative_keywords
            if uc.disambiguation:
                entry["disambiguation"] = uc.disambiguation
            if uc.data_domain:
                entry["data_domain"] = uc.data_domain
            uc_list.append(entry)

        uc_path = artifacts_dir / "uc_list.json"
        uc_path.write_text(
            json.dumps(uc_list, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        logger.info(
            "bp_uc_extract: %d use cases from %d example files", len(uc_list), len(file_summaries)
        )

        return PhaseResult(
            phase_name="bp_uc_extract",
            status="completed",
            iterations=1,
            total_tokens=tokens,
            final_text=f"{len(uc_list)} UCs extracted",
        )

    # ----- Phase C: Coverage gap detection -----

    async def _coverage_gap_handler(
        state: AgentState,
        repo_path: Path,
    ) -> PhaseResult:
        """Detect uncovered subdirectories and do targeted BD extraction."""
        artifacts_dir = Path(state.run_dir) / "artifacts"

        # Load BD list
        bd_path = artifacts_dir / "bd_list.json"
        if not bd_path.exists():
            return PhaseResult(
                phase_name="bp_coverage_gap",
                status="completed",
                final_text="No bd_list.json, skipping gap detection",
            )

        bd_result = BDExtractionResult.model_validate_json(
            bd_path.read_text(encoding="utf-8"),
        )

        # Load manifest
        manifest_path = artifacts_dir / "coverage_manifest.json"
        if not manifest_path.exists():
            return PhaseResult(
                phase_name="bp_coverage_gap",
                status="completed",
                final_text="No manifest, skipping gap detection",
            )

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        all_dirs = set(manifest.get("must_visit_dirs", []))

        # Extract directories covered by BD evidence
        covered_dirs: set[str] = set()
        for bd in bd_result.decisions:
            ev = bd.evidence
            if "/" in ev:
                parts = ev.split("/")
                for i in range(1, len(parts)):
                    covered_dirs.add("/".join(parts[:i]))

        uncovered = sorted(all_dirs - covered_dirs)

        # Filter to directories with at least 1 Python file
        index_path = artifacts_dir / "repo_index.json"
        if not index_path.exists():
            return PhaseResult(
                phase_name="bp_coverage_gap",
                status="completed",
                final_text="repo_index.json missing, skipping gap detection",
            )

        index = json.loads(index_path.read_text(encoding="utf-8"))
        files_index = index.get("files", {})
        dir_file_counts: dict[str, int] = {}
        for fpath in files_index:
            parts = fpath.split("/")
            if len(parts) > 1:
                d = "/".join(parts[:-1])
                dir_file_counts[d] = dir_file_counts.get(d, 0) + 1
        # Filter: ≥1 file, exclude test/build/cache/template directories
        skip_patterns = {"test", "tests", "__pycache__", "build", "dist", ".egg", "templates"}
        uncovered = [
            d
            for d in uncovered
            if dir_file_counts.get(d, 0) >= 1
            and not any(skip in d.lower() for skip in skip_patterns)
        ]

        if not uncovered:
            logger.info("bp_coverage_gap: no uncovered directories")
            return PhaseResult(
                phase_name="bp_coverage_gap",
                status="completed",
                final_text="Full coverage — no gaps",
            )

        # Process up to 10 directories (raised from 5)
        uncovered = uncovered[:10]
        logger.info("bp_coverage_gap: %d uncovered dirs — %s", len(uncovered), uncovered)

        # Read skeletons for uncovered directories (index already loaded above)
        gap_context = ""
        for d in uncovered:
            gap_context += f"\n## Directory: {d}/\n"
            for fpath, finfo in files_index.items():
                if fpath.startswith(d + "/"):
                    classes = finfo.get("classes", [])
                    funcs = finfo.get("functions", [])
                    gap_context += f"\n### {fpath}\n"
                    if classes:
                        gap_context += f"  Classes: {classes}\n"
                    if funcs:
                        gap_context += f"  Functions: {funcs[:10]}\n"

        # One Instructor call for gap BDs
        from .schemas_v5 import RawFallback as _RF

        gap_prompt = (
            f"The following directories contain code but have NO business decisions extracted.\n"
            f"For each directory, identify architectural decisions, design patterns, "
            f"and business logic choices.\n\n{gap_context}\n\n"
            f"Extract business decisions with proper type classification (T/B/BA/DK/RC/M).\n"
            f"Each decision MUST have file:line(function) evidence format."
        )

        # Use lightweight CoverageGapResult instead of full BDExtractionResult
        # to avoid type_summary/missing_gaps validation failures on MiniMax.
        from .schemas_v5 import CoverageGapResult as _CGR

        _gap_system = (
            "You are a business decision extractor. Extract decisions from "
            "uncovered code directories. Return a JSON object with a single "
            "'decisions' array. Each decision needs: id, content, type "
            "(T/B/BA/DK/RC/M), rationale (>=40 chars), evidence "
            "(file:line(function)), stage, status."
        )

        result, tokens = await agent.run_structured_call(
            _gap_system,
            gap_prompt,
            _CGR,
            max_tokens=32768,
        )

        if isinstance(result, _RF):
            logger.warning("bp_coverage_gap: Instructor failed")
            return PhaseResult(
                phase_name="bp_coverage_gap",
                status="completed",
                total_tokens=tokens,
                final_text=f"Gap detection found {len(uncovered)} dirs but extraction failed",
            )

        # Merge gap BDs into bd_list.json
        existing_ids = {bd.id for bd in bd_result.decisions}
        new_bds = [bd for bd in result.decisions if bd.id not in existing_ids]

        if new_bds:
            merged = list(bd_result.decisions) + new_bds
            merged_missing = [d for d in merged if d.status == "missing"]
            from collections import Counter as _Counter

            type_counts = _Counter(d.type for d in merged)

            merged_result = BDExtractionResult(
                decisions=merged,
                type_summary=dict(type_counts),
                missing_gaps=merged_missing,
            )

            # Overwrite bd_list.json with merged result
            bd_path.write_text(
                merged_result.model_dump_json(indent=2),
                encoding="utf-8",
            )

            # Also update markdown
            md = _bd_to_markdown(merged_result)
            (artifacts_dir / "step2c_business_decisions.md").write_text(
                md,
                encoding="utf-8",
            )

            logger.info(
                "bp_coverage_gap: +%d BDs from %d uncovered dirs → total %d",
                len(new_bds),
                len(uncovered),
                len(merged),
            )

        return PhaseResult(
            phase_name="bp_coverage_gap",
            status="completed",
            iterations=1,
            total_tokens=tokens,
            final_text=f"+{len(new_bds)} gap BDs from {len(uncovered)} dirs",
        )

    # ----- Enrich handler (deterministic post-assembly patching) -----

    async def _enrich_handler(
        state: AgentState,
        repo_path: Path,
    ) -> PhaseResult:
        """Patch assembled blueprint.yaml with structured data from bd_list.json.

        Delegates all enrichment logic to blueprint_enrich.enrich_blueprint().
        This handler is responsible only for YAML I/O and atomic write.
        """
        import os as _os
        import re as _re
        import tempfile as _tmp

        import yaml as _yaml

        artifacts_dir = Path(state.run_dir) / "artifacts"
        bp_path = artifacts_dir / "blueprint.yaml"

        if not bp_path.exists():
            return PhaseResult(
                phase_name="bp_enrich",
                status="error",
                error="blueprint.yaml not found",
            )

        # --- Parse YAML (with aggressive repair for LLM quirks) ---
        raw_yaml = bp_path.read_text(encoding="utf-8")
        try:
            bp = _yaml.safe_load(raw_yaml)
        except _yaml.YAMLError:
            repaired_lines = []
            for line in raw_yaml.split("\n"):
                stripped = line.lstrip()
                if stripped.startswith("#"):
                    repaired_lines.append(line)
                    continue
                list_str_match = _re.match(r"^(\s*-\s+)(.+)$", stripped)
                if list_str_match and stripped.count(":") >= 2:
                    indent = line[: len(line) - len(stripped)]
                    prefix = list_str_match.group(1)
                    value = list_str_match.group(2)
                    if not value.startswith(("'", '"', "|", ">")):
                        value = value.replace('"', "'")
                        line = f'{indent}{prefix}"{value}"'
                        repaired_lines.append(line)
                        continue
                key_match = _re.match(
                    r"^(\s*(?:-\s+)?[\w][\w\s.\-]*?):\s+(.+)$",
                    line,
                )
                if key_match:
                    key_part = key_match.group(1)
                    val_part = key_match.group(2)
                    has_problem = any(c in val_part for c in ":→{}[]")
                    already_quoted = val_part.startswith(("'", '"', "|", ">", "[", "{"))
                    if has_problem and not already_quoted:
                        val_part = val_part.replace("\\", "\\\\").replace('"', "'")
                        line = f'{key_part}: "{val_part}"'
                repaired_lines.append(line)
            raw_yaml = "\n".join(repaired_lines)
            try:
                bp = _yaml.safe_load(raw_yaml)
            except _yaml.YAMLError as exc2:
                return PhaseResult(
                    phase_name="bp_enrich",
                    status="error",
                    error=f"YAML parse failed after repair attempt: {exc2}",
                )

        if not isinstance(bp, dict):
            return PhaseResult(
                phase_name="bp_enrich",
                status="error",
                error=f"Expected mapping, got {type(bp).__name__}",
            )

        # --- Parse bd_list.json ---
        bd_path = artifacts_dir / "bd_list.json"
        if not bd_path.exists():
            return PhaseResult(
                phase_name="bp_enrich",
                status="error",
                error="bd_list.json not found — cannot enrich without structured BD data",
            )
        try:
            bd_result = BDExtractionResult.model_validate_json(
                bd_path.read_text(encoding="utf-8"),
            )
        except Exception as exc:
            return PhaseResult(
                phase_name="bp_enrich",
                status="error",
                error=f"bd_list.json parse failed: {exc}",
            )

        # --- Delegate to blueprint_enrich module ---
        bp, patch_stats = enrich_blueprint(bp, bd_result, state, artifacts_dir)

        # --- Atomic write ---
        try:
            content = "# Extraction pipeline: SOP v3.4 (v5 agent, auto-enriched)\n"
            content += _yaml.dump(
                bp,
                allow_unicode=True,
                default_flow_style=False,
                sort_keys=False,
                width=100,
            )
            _yaml.safe_load(content)  # verify before writing

            fd, tmp_path = _tmp.mkstemp(
                dir=str(artifacts_dir),
                suffix=".yaml",
            )
            try:
                with _os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(content)
                    f.flush()
                    _os.fsync(f.fileno())
                _os.replace(tmp_path, str(bp_path))
            except BaseException:
                try:
                    _os.unlink(tmp_path)
                except OSError:
                    pass
                raise
        except Exception as exc:
            return PhaseResult(
                phase_name="bp_enrich",
                status="error",
                error=f"Atomic write failed: {exc}",
            )

        summary = ", ".join(f"{k}={v}" for k, v in patch_stats.items() if v)
        logger.info("bp_enrich: %s", summary)

        return PhaseResult(
            phase_name="bp_enrich",
            status="completed",
            final_text=f"Enriched: {summary}",
        )

    # ----- Phase list -----

    all_tools = [
        "read_file",
        "list_dir",
        "grep_codebase",
        "search_codebase",
        "write_artifact",
        "get_artifact",
        "get_skeleton",
        "get_dependencies",
        "get_file_type",
        "list_by_type",
    ]

    return [
        # --- Pre-processing (reused from v4.1) ---
        Phase(
            name="bp_fingerprint",
            description="Fingerprint",
            system_prompt="",
            initial_message_builder=lambda s, r: "",
            requires_llm=False,
            python_handler=_fingerprint_handler,
        ),
        Phase(
            name="bp_clone",
            description="Verify repo",
            system_prompt="",
            initial_message_builder=lambda s, r: "",
            requires_llm=False,
            python_handler=_clone_handler,
            depends_on=["bp_fingerprint"],
        ),
        Phase(
            name="bp_structural_index",
            description="AST structural index",
            system_prompt="",
            initial_message_builder=lambda s, r: "",
            requires_llm=False,
            python_handler=_structural_index_handler,
            depends_on=["bp_clone"],
        ),
        Phase(
            name="bp_mine_sources",
            description="Mine non-code sources",
            system_prompt="",
            initial_message_builder=lambda s, r: "",
            requires_llm=False,
            python_handler=_mine_sources_handler,
            depends_on=["bp_clone"],
        ),
        # --- Coverage Manifest (Phase A: deterministic pre-scan) ---
        Phase(
            name="bp_coverage_manifest",
            description="Generate coverage checklist",
            system_prompt="",
            initial_message_builder=lambda s, r: "",
            requires_llm=False,
            python_handler=_coverage_manifest_handler,
            depends_on=["bp_structural_index"],
        ),
        # --- Parallel Workers (5-way: 4 breadth + 1 depth) ---
        Phase(
            name="worker_docs",
            description="Worker: project context from docs",
            system_prompt=prompts_v4.WORKER_DOCS_SYSTEM,
            initial_message_builder=_build_worker_docs_message,
            allowed_tools=["read_file", "list_dir", "grep_codebase", "write_artifact"],
            max_iterations=30,
            depends_on=["bp_mine_sources"],
            required_artifacts=["worker_docs.md"],
            blocking=False,
            parallel_group="explore",
        ),
        Phase(
            name="worker_arch",
            description="Worker: architecture skeleton",
            system_prompt=prompts_v4.WORKER_ARCH_SYSTEM,
            initial_message_builder=_build_worker_arch_message,
            allowed_tools=all_tools,
            max_iterations=20,  # Reduced: evidence packet needs focused extraction, not exhaustive scanning
            depends_on=["bp_coverage_manifest"],
            required_artifacts=["worker_arch.json"],
            blocking=True,
            parallel_group="explore",
        ),
        Phase(
            name="worker_workflow",
            description="Worker: business decisions from workflows",
            system_prompt=prompts_v4.WORKER_WORKFLOW_SYSTEM,
            initial_message_builder=_build_worker_workflow_message,
            allowed_tools=all_tools,
            max_iterations=30,  # Reduced: budget-capped output needs fewer iterations
            depends_on=["bp_coverage_manifest"],
            required_artifacts=["worker_workflow.json"],
            blocking=True,
            parallel_group="explore",
        ),
        Phase(
            name="worker_math",
            description="Worker: math/algorithm decisions",
            system_prompt=prompts_v4.WORKER_MATH_SYSTEM,
            initial_message_builder=_build_worker_math_message,
            allowed_tools=[
                "read_file",
                "grep_codebase",
                "write_artifact",
                "get_skeleton",
                "list_by_type",
            ],
            max_iterations=40,
            depends_on=["bp_coverage_manifest"],
            required_artifacts=["worker_math.json"],
            blocking=False,
            parallel_group="explore",
        ),
        Phase(
            name="worker_arch_deep",
            description="Worker: architecture-level BD hunting (deep)",
            system_prompt=prompts_v5.WORKER_ARCH_DEEP_SYSTEM,
            initial_message_builder=_build_worker_arch_message,
            allowed_tools=all_tools,
            max_iterations=50,
            depends_on=["bp_coverage_manifest"],
            required_artifacts=["worker_arch_deep.json"],
            blocking=False,
            parallel_group="explore",
        ),
        # v6: dedicated resource Worker (parallel with arch workers)
        Phase(
            name="worker_resource",
            description="Worker: resource and dependency inventory",
            system_prompt=prompts_v6.WORKER_RESOURCE_SYSTEM,
            initial_message_builder=lambda s, r: (
                f"Repository: {r}\n\n"
                "Inventory all non-code resources: data sources, Python dependencies, "
                "external services, infrastructure requirements, and replaceable resource options."
            ),
            allowed_tools=[
                "read_file",
                "list_dir",
                "grep_codebase",
                "write_artifact",
                "get_skeleton",
            ],
            max_iterations=30,
            depends_on=["bp_coverage_manifest"],
            required_artifacts=["worker_resource.json"],
            blocking=True,
            parallel_group="explore",
        ),
        Phase(
            name="worker_verify",
            description="Verify factual claims (SOP 2b)",
            system_prompt=prompts_v5.WORKER_VERIFY_SYSTEM,
            initial_message_builder=lambda s, r: (
                f"Repository: {r}\n\n"
                "Read get_artifact('worker_arch.json') and verify all factual claims."
            ),
            allowed_tools=[
                "read_file",
                "grep_codebase",
                "get_artifact",
                "write_artifact",
            ],
            max_iterations=30,
            depends_on=["worker_arch"],
            parallel_group="workers",
            blocking=True,
            required_artifacts=["worker_verify.md"],
        ),
        Phase(
            name="worker_audit",
            description="Systematic audit checklist (SOP 2c)",
            system_prompt=prompts_v5.WORKER_AUDIT_SYSTEM,
            initial_message_builder=lambda s, r: (
                f"Repository: {r}\n"
                f"Subdomain labels: {', '.join(s.subdomain_labels or ['TRD'])}\n\n"
                "Audit the repository against the 20-item universal finance checklist."
            ),
            allowed_tools=[
                "read_file",
                "grep_codebase",
                "get_artifact",
                "write_artifact",
            ],
            max_iterations=40,
            depends_on=["bp_clone"],
            parallel_group="workers",
            blocking=True,  # v6: audit results feed into synthesis Step 3
            required_artifacts=["worker_audit.md"],
        ),
        # --- Synthesis v5/v6 (Instructor-driven, 3-step + audit injection) ---
        Phase(
            name="bp_synthesis_v5",
            description="v6 structured synthesis (Instructor, 3-step + audit)",
            system_prompt="",
            initial_message_builder=lambda s, r: "",
            requires_llm=False,
            python_handler=_synthesis_v5_handler,
            depends_on=[
                # Only blocking workers in depends_on — non-blocking workers
                # (worker_docs, worker_arch_deep, worker_math) are read via
                # _safe_read() which tolerates missing artifacts gracefully.
                "worker_arch",
                "worker_workflow",
                "worker_verify",
                "worker_audit",  # v6: audit is now blocking and injected into Step 3
                "worker_resource",  # v6: resource Worker for replaceable_points
            ],
            required_artifacts=["bd_list.json", "step2c_business_decisions.md"],
            blocking=True,
        ),
        # --- v6: Independent Evaluator (Sprint-contract BD verification) ---
        Phase(
            name="bp_evaluate",
            description="Independent BD evaluation (Sprint-contract verification)",
            system_prompt=prompts_v6.EVALUATOR_SYSTEM,
            initial_message_builder=lambda s, r: (
                f"Repository: {r}\n\n"
                "Read get_artifact('bd_list.json') and independently verify each "
                "non-T business decision against the source code.\n"
                "Write your findings to artifact 'evaluation_report.json'."
            ),
            allowed_tools=[
                "read_file",
                "grep_codebase",
                "get_artifact",
                "write_artifact",
            ],
            max_iterations=40,
            depends_on=["bp_synthesis_v5"],
            required_artifacts=["evaluation_report.json"],
            blocking=True,
        ),
        # --- UC Extraction (Phase B: deterministic) ---
        Phase(
            name="bp_uc_extract",
            description="Extract UCs from all example files",
            system_prompt="",
            initial_message_builder=lambda s, r: "",
            requires_llm=False,
            python_handler=_uc_extract_handler,
            depends_on=["bp_evaluate"],  # v6: depends on evaluate, not synthesis
            required_artifacts=["uc_list.json"],
            blocking=True,  # v6: UC is critical path
        ),
        # --- Coverage Gap Detection (Phase C) ---
        Phase(
            name="bp_coverage_gap",
            description="Detect + fill uncovered subdirectories",
            system_prompt="",
            initial_message_builder=lambda s, r: "",
            requires_llm=False,
            python_handler=_coverage_gap_handler,
            depends_on=["bp_evaluate"],  # v6: depends on evaluate
            blocking=True,  # v6: coverage gap is critical path
        ),
        # --- Assembly (v5.1: Instructor-driven, no agentic loop) ---
        Phase(
            name="bp_assemble",
            description="Assemble blueprint YAML from artifacts (Instructor)",
            system_prompt="",  # Not used — python_handler does the call
            initial_message_builder=lambda s, r: "",
            requires_llm=False,
            python_handler=_assemble_instructor_handler,
            depends_on=["bp_uc_extract", "bp_coverage_gap"],
            quality_gate=_blueprint_yaml_gate,
            required_artifacts=["blueprint.yaml"],
            blocking=True,
        ),
        # --- Enrich (deterministic post-assembly patching) ---
        Phase(
            name="bp_enrich",
            description="Inject structured data into blueprint YAML",
            system_prompt="",
            initial_message_builder=lambda s, r: "",
            requires_llm=False,
            python_handler=_enrich_handler,
            depends_on=["bp_assemble"],
            blocking=True,
        ),
        # --- Quality Gate (SOP v3.4) ---
        Phase(
            name="bp_quality_gate",
            description="SOP v3.4 quality gate",
            system_prompt="",
            initial_message_builder=lambda s, r: "",
            requires_llm=False,
            python_handler=_quality_gate_handler,
            depends_on=["bp_enrich"],
            required_artifacts=["quality_gate_result.json"],
        ),
        # --- Post-processing (reused from v4.1) ---
        Phase(
            name="bp_consistency_check",
            description="Check BD type validity",
            system_prompt="",
            initial_message_builder=lambda s, r: "",
            requires_llm=False,
            python_handler=_step5_handler,
            depends_on=["bp_quality_gate"],
        ),
        Phase(
            name="bp_finalize",
            description="Promote blueprint to output/",
            system_prompt="",
            initial_message_builder=lambda s, r: "",
            requires_llm=False,
            python_handler=_finalize_handler,
            depends_on=["bp_consistency_check"],
        ),
    ]
