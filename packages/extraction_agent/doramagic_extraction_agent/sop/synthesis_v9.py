"""v9 Map-Reduce synthesis module.

Replaces the monolithic _synthesis_v5_handler with a three-phase pipeline:

1. **Local Synthesis (Map)** — per-worker Instructor call that validates and
   enhances BDCandidates into BusinessDecision objects.
2. **Global Synthesis (Reduce)** — merges all validated BDs, deduplicates,
   re-numbers IDs, then runs a cross-module interaction reasoning call.
3. **Fixer** — targeted repair of BDs that fail BQ-10 evidence-grounding
   checks, using one batched Instructor call.

Each phase is exposed as a builder function that accepts the ExtractionAgent
and returns an async handler closure (same pattern as _synthesis_v5_handler
inside build_blueprint_phases_v5).
"""

from __future__ import annotations

import json
import logging
import re
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

from doramagic_extraction_agent.core.agent_loop import ExtractionAgent, PhaseResult
from doramagic_extraction_agent.sop.blueprint_enrich import (
    _step2c_content_key,
    is_missing_evidence,
    load_step2c_evidence_map,
    load_worker_candidate_evidence_map,
)
from doramagic_extraction_agent.sop.schemas_v5 import (
    BDExtractionResult,
    BusinessDecision,
    RawFallback,
)
from doramagic_extraction_agent.sop.schemas_v9 import (
    LocalSynthesisResult,
    WorkerBDOutput,
)
from doramagic_extraction_agent.state.schema import AgentState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Worker names processed by local synthesis
# ---------------------------------------------------------------------------

_WORKER_NAMES: list[str] = ["arch", "workflow", "math", "arch_deep", "resource"]

# ---------------------------------------------------------------------------
# System prompts (v9-specific — kept here to avoid polluting prompts_v5)
# ---------------------------------------------------------------------------

LOCAL_SYNTHESIS_SYSTEM = """\
You are a senior financial software analyst performing per-worker BD validation.

## Input

You will receive a list of raw BD candidates from a single worker.  Each
candidate has a content, candidate_type (T/B/BA/DK/RC/M), evidence reference,
and a rationale_draft.

## Task

### Validate each candidate
- ACCEPT if: content is specific, evidence references a real code location,
  rationale_draft addresses WHY + BOUNDARY (≥ 40 chars after enhancement).
- REJECT if: content is too vague, evidence is fabricated/bare-filename,
  or it is a pure T-type infrastructure detail with no business impact.

### Enhance accepted candidates
For each accepted candidate, produce a full BusinessDecision:
- Refine `type` using the 6-type framework (T/B/BA/DK/RC/M, "/" for multi).
- Write `rationale` with ≥ 40 chars: WHY + BOUNDARY.
- Convert `evidence` to `file:line(function_name)` format if possible.
- Set `stage` to the module path (use candidate `module` field).
- Set `status` = "present"; set `severity` / `impact` if noteworthy.

### RC + B split rule
Never produce "B/RC" or "RC/B".  If a decision mixes regulation and
implementation, split into two separate BusinessDecision objects.

## Output

Return a BDExtractionResult JSON with:
- `decisions`: accepted (and possibly split) BusinessDecision objects
- `missing_gaps`: subset of decisions with status="missing"
- `type_summary`: count per type key

Do NOT include rejected candidates.  Do NOT wrap in markdown code fences.
"""

GLOBAL_SYNTHESIS_SYSTEM = """\
You are a systems analyst performing cross-worker decision interaction analysis.

## Input

You will receive the merged BD list (already deduplicated and re-numbered) from
all local synthesis phases, plus the worker_audit gap findings.

## Task

Analyze how business decisions INTERACT with each other and find emergent effects.

### Interaction Types

1. **Amplification** — Two decisions that multiply each other's effect.
2. **Contradiction** — Two decisions that conflict or create tension.
3. **Hidden Dependency** — One decision that silently depends on another.
4. **Risk Cascade** — A chain creating systemic risk.

For each interaction, produce a BusinessDecision:
- content: "INTERACTION: [BD-X] × [BD-Y] → [emergent effect]"
- type: Dominant type (usually B/BA)
- evidence: The source BD IDs (e.g. "BD-003,BD-017")
- stage: "cross_stage"
- rationale: WHY this matters and WHEN it causes problems (≥ 40 chars)

### Audit-driven missing gaps
For each ❌ or ⚠️ audit item NOT already covered by existing BDs:
- Generate a BD with status="missing", known_gap=true
- Set severity and impact

### Targets
- ≥ 5 interaction findings
- ≥ 2 risk cascades; ≥ 1 contradiction
- ≥ 3 audit-driven missing gaps (if audit findings exist)

## Output

Return a BDExtractionResult JSON containing ONLY the new interaction/gap BDs.
These will be MERGED into the existing list.  Do NOT wrap in markdown code fences.
"""

FIXER_SYSTEM = """\
You are a BD evidence-repair specialist.

## Input

You will receive a list of BusinessDecision objects whose evidence references
failed BQ-10 grounding validation, plus file-system context:
- For each BD: the broken evidence string and whether the file exists.
- When the file exists: the first matching function/class signature from that file.

## Task

For each broken BD, repair the evidence:
1. If the file exists and a likely function is provided → update to
   `file:line(function)` using the provided signature.
2. If the file does not exist → mark the BD `status="missing"` and add a
   note in `impact` that the evidence file was not found.
3. If ambiguous → use the original BD content to infer the best repair.

Return a FixerResult JSON with:
- `fixed`: list of repaired BusinessDecision dicts (full fields)
- `unfixable`: list of BD IDs that could not be repaired
- `dropped`: list of BD IDs to remove as hallucinated (no code basis)

Do NOT wrap in markdown code fences.
"""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _repair_json(text: str) -> str | None:
    """Attempt to repair common MiniMax JSON output issues.

    Fixes (applied in order):
    - Markdown code fences wrapping
    - Missing commas between adjacent objects (BEFORE truncation)
    - Trailing commas before } or ]
    - Extra data after valid JSON (truncate, string-aware)
    """
    s = text.strip()
    s = re.sub(r"^```(?:json)?\s*\n?", "", s)
    s = re.sub(r"\n?```\s*$", "", s)

    # Fix missing commas between objects (before truncation so we don't lose data)
    s = re.sub(r"}\s*{", "},{", s)

    # Fix trailing commas
    s = re.sub(r",\s*([}\]])", r"\1", s)

    # Fix extra data after valid JSON — string-aware bracket matching
    depth = 0
    end_pos = None
    in_string = False
    escape_next = False
    for i, c in enumerate(s):
        if escape_next:
            escape_next = False
            continue
        if c == "\\":
            escape_next = True
            continue
        if c == '"' and not escape_next:
            in_string = not in_string
            continue
        if in_string:
            continue
        if c in "{[":
            depth += 1
        elif c in "}]":
            depth -= 1
            if depth == 0:
                end_pos = i + 1
                break
    if end_pos and end_pos < len(s):
        s = s[:end_pos]

    try:
        json.loads(s)
        return s
    except json.JSONDecodeError:
        return None


def _safe_read(path: Path, default: str = "") -> str:
    """Read a file if it exists; return *default* otherwise."""
    try:
        return path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return default


def _coerce_bd_dict(
    bd_raw: dict[str, Any],
    idx: int,
    md_evidence_map: dict[str, str] | None = None,
) -> BusinessDecision | None:
    """Leniently coerce a raw dict to BusinessDecision.

    Returns None if the dict is unusable (no content).

    When ``md_evidence_map`` is provided AND the raw BD's evidence is
    semantically missing (empty, dash, or an ``N/A`` sentinel — see
    ``is_missing_evidence``), look up a real ref by content prefix.
    Only when no row matches do we fall back to the N/A sentinel.

    This roots out the bp-062 regression where L3 recovery unconditionally
    defaulted to N/A even when real refs were sitting on disk, and
    extends the repair to existing N/A placeholders the LLM itself emits.
    """
    if not isinstance(bd_raw, dict) or not bd_raw.get("content"):
        return None
    bd_raw.setdefault("id", f"BD-{idx + 1:03d}")
    bd_raw.setdefault("type", "B")
    bd_raw.setdefault("stage", "unknown")
    bd_raw.setdefault("status", "present")
    rat = bd_raw.get("rationale", bd_raw.get("content", ""))
    if len(rat) < 40:
        rat = rat + " — decision extracted from worker candidate"
    bd_raw["rationale"] = rat[:500]
    if is_missing_evidence(bd_raw.get("evidence")):
        recovered = ""
        if md_evidence_map:
            key = _step2c_content_key(bd_raw.get("content", "") or "")
            recovered = md_evidence_map.get(key, "")
        bd_raw["evidence"] = recovered or "N/A:0(see_rationale)"
    try:
        return BusinessDecision.model_validate(bd_raw)
    except Exception:
        try:
            ev = bd_raw.get("evidence")
            if is_missing_evidence(ev):
                ev = "N/A:0(see_rationale)"
            return BusinessDecision(
                id=bd_raw["id"],
                content=str(bd_raw["content"]),
                type=bd_raw.get("type", "B"),
                rationale=rat,
                evidence=str(ev),
                stage=bd_raw.get("stage", "unknown"),
            )
        except Exception:
            return None


def _extract_decisions_from_raw(
    raw_text: str,
    phase_label: str,
) -> list[dict[str, Any]]:
    """L3 recovery: extract decisions list from raw LLM text.

    Tries JSON → YAML → truncated-JSON strategies.
    Returns a list of raw dicts (empty on total failure).
    """
    import yaml as _yaml

    raw = raw_text.strip()
    raw = re.sub(r"^```(?:json|yaml)?\s*\n?", "", raw)
    raw = re.sub(r"\n?```\s*$", "", raw)

    parsed: Any = None
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        import contextlib

        with contextlib.suppress(Exception):
            parsed = _yaml.safe_load(raw)

    if parsed is None:
        last_complete = raw.rfind("},")
        if last_complete > 0:
            try:
                parsed = json.loads(raw[: last_complete + 1] + "\n  ]\n}")
                logger.info(
                    "%s L3: recovered from truncated JSON (%d chars)",
                    phase_label,
                    last_complete,
                )
            except (json.JSONDecodeError, ValueError):
                pass

    if not isinstance(parsed, dict):
        logger.warning("%s L3: no parseable dict found in raw text", phase_label)
        return []

    decisions = parsed.get("decisions")
    if not isinstance(decisions, list):
        logger.warning("%s L3: no 'decisions' key in parsed dict", phase_label)
        return []

    return decisions  # type: ignore[return-value]


def _build_local_user_message(
    worker_name: str,
    worker_output: WorkerBDOutput,
) -> str:
    """Build the user message for a local synthesis call."""
    candidates_json = json.dumps(
        [c.model_dump() for c in worker_output.candidates],
        ensure_ascii=False,
        indent=2,
    )
    modules_visited = ", ".join(worker_output.modules_visited) or "(not recorded)"
    return (
        f"## Worker: {worker_name}\n\n"
        f"### Modules visited\n{modules_visited}\n\n"
        f"### BD Candidates ({len(worker_output.candidates)} total)\n\n"
        f"```json\n{candidates_json}\n```\n\n"
        "Validate, enhance, and return a BDExtractionResult JSON."
    )


def _build_global_user_message(
    merged_bds: list[BusinessDecision],
    worker_audit: str,
) -> str:
    """Build the user message for the global synthesis (interaction) call."""
    bd_json = json.dumps(
        [bd.model_dump() for bd in merged_bds],
        ensure_ascii=False,
        indent=2,
    )
    audit_section = ""
    if worker_audit.strip():
        audit_snippet = worker_audit[:5000]
        audit_section = (
            "\n\n## Audit Checklist Findings\n\n"
            "For each ❌ or ⚠️ item not already covered by existing BDs, "
            "generate a new BD with status='missing', known_gap=true.\n\n"
            f"{audit_snippet}"
        )
    return (
        f"## Merged BD List ({len(merged_bds)} decisions)\n\n"
        f"```json\n{bd_json}\n```\n\n"
        "Analyze decision interactions and add interaction/gap BDs."
        f"{audit_section}"
    )


def _build_fixer_user_message(
    broken_bds: list[BusinessDecision],
    repair_context: list[dict[str, Any]],
) -> str:
    """Build the user message for the fixer Instructor call."""
    bd_section = json.dumps(
        [bd.model_dump() for bd in broken_bds],
        ensure_ascii=False,
        indent=2,
    )
    ctx_section = json.dumps(repair_context, ensure_ascii=False, indent=2)
    return (
        f"## Broken BDs ({len(broken_bds)} total)\n\n"
        f"```json\n{bd_section}\n```\n\n"
        "## File-system repair context\n\n"
        f"```json\n{ctx_section}\n```\n\n"
        "Return a FixerResult JSON."
    )


# ---------------------------------------------------------------------------
# Builder: Local Synthesis (Map phase)
# ---------------------------------------------------------------------------


def build_local_synthesis_handler(agent: ExtractionAgent) -> Callable:
    """Return a python_handler closure for the local synthesis (Map) phase.

    For each worker in [arch, workflow, math, arch_deep, resource]:
    1. Parse worker_{name}.json as WorkerBDOutput (with legacy coercion).
    2. Run one Instructor call to validate/enhance candidates.
    3. Save result as local_synthesis_{name}.json.
    """

    async def _handler(state: AgentState, repo_path: Path) -> PhaseResult:
        artifacts_dir = Path(state.run_dir) / "artifacts"
        # Load once so every _coerce_bd_dict call can recover evidence
        # from step2c_business_decisions.md instead of defaulting to N/A.
        # Merge step2c.md refs with worker_*.json candidate refs. Worker
        # candidates are produced at exploration time, so they are already
        # on disk when local/global synthesis fires — unlike step2c.md,
        # which is written later by bp_bd_r4_evidence and may be missing
        # on fresh v9 runs that schedule synthesis in parallel.
        _md = load_step2c_evidence_map(artifacts_dir)
        _worker = load_worker_candidate_evidence_map(artifacts_dir)
        # step2c wins on conflicts; worker fills the rest.
        md_evidence_map = {**_worker, **_md}
        total_tokens = 0
        local_results: dict[str, list[BusinessDecision]] = {}

        for worker_name in _WORKER_NAMES:
            artifact_path = artifacts_dir / f"worker_{worker_name}.json"
            raw_text = _safe_read(artifact_path)

            if not raw_text:
                logger.info(
                    "local_synthesis: worker_%s.json not found — skipping",
                    worker_name,
                )
                local_results[worker_name] = []
                continue

            # Parse with WorkerBDOutput (handles legacy formats via coerce)
            try:
                raw_data = json.loads(raw_text)
            except json.JSONDecodeError as initial_err:
                # v10: attempt JSON repair before giving up
                repaired = _repair_json(raw_text)
                if repaired is not None:
                    try:
                        raw_data = json.loads(repaired)
                        logger.info("local_synthesis: repaired JSON for worker_%s", worker_name)
                    except json.JSONDecodeError:
                        logger.warning(
                            "local_synthesis: JSON repair failed for worker_%s: %s — skipping",
                            worker_name,
                            initial_err,
                        )
                        local_results[worker_name] = []
                        continue
                else:
                    logger.warning(
                        "local_synthesis: failed to parse worker_%s.json: %s — skipping",
                        worker_name,
                        initial_err,
                    )
                    local_results[worker_name] = []
                    continue
            try:
                worker_output = WorkerBDOutput.model_validate(raw_data)
            except Exception as parse_exc:
                logger.warning(
                    "local_synthesis: failed to validate worker_%s.json: %s — skipping",
                    worker_name,
                    parse_exc,
                )
                local_results[worker_name] = []
                continue

            if not worker_output.candidates:
                logger.info(
                    "local_synthesis: worker_%s has 0 candidates — skipping LLM call",
                    worker_name,
                )
                local_results[worker_name] = []
                # Write empty result for downstream consistency
                empty = LocalSynthesisResult(worker_name=worker_name)
                out_path = artifacts_dir / f"local_synthesis_{worker_name}.json"
                out_path.write_text(empty.model_dump_json(indent=2), encoding="utf-8")
                continue

            user_msg = _build_local_user_message(worker_name, worker_output)
            logger.info(
                "local_synthesis: calling LLM for worker_%s (%d candidates)",
                worker_name,
                len(worker_output.candidates),
            )

            result, tokens = await agent.run_structured_call(
                LOCAL_SYNTHESIS_SYSTEM,
                user_msg,
                BDExtractionResult,
            )
            total_tokens += tokens

            # --- Handle result / L3 recovery ---
            if isinstance(result, RawFallback):
                raw_path = artifacts_dir / f"local_synthesis_{worker_name}_raw.txt"
                raw_path.write_text(result.text, encoding="utf-8")
                logger.warning(
                    "local_synthesis: worker_%s returned RawFallback — attempting L3 recovery",
                    worker_name,
                )
                raw_decisions = _extract_decisions_from_raw(
                    result.text, f"local_synthesis_{worker_name}"
                )
                bds: list[BusinessDecision] = []
                for i, bd_raw in enumerate(raw_decisions):
                    bd = _coerce_bd_dict(bd_raw, i, md_evidence_map)
                    if bd is not None:
                        bds.append(bd)
                logger.info(
                    "local_synthesis: worker_%s L3 recovery — %d BDs",
                    worker_name,
                    len(bds),
                )
            else:
                bds = result.decisions
                logger.info(
                    "local_synthesis: worker_%s → %d decisions",
                    worker_name,
                    len(bds),
                )

            local_results[worker_name] = bds

            # Save per-worker local result
            local_result_obj = LocalSynthesisResult(
                validated=[bd.model_dump() for bd in bds],
                worker_name=worker_name,
            )
            out_path = artifacts_dir / f"local_synthesis_{worker_name}.json"
            out_path.write_text(local_result_obj.model_dump_json(indent=2), encoding="utf-8")

        total_bds = sum(len(v) for v in local_results.values())
        logger.info(
            "local_synthesis done: %d total BDs across %d workers (%d tokens)",
            total_bds,
            len(_WORKER_NAMES),
            total_tokens,
        )

        summary = {name: len(bds) for name, bds in local_results.items()}
        return PhaseResult(
            phase_name="bp_local_synthesis_v9",
            status="completed",
            iterations=len(_WORKER_NAMES),
            total_tokens=total_tokens,
            final_text=json.dumps(summary),
        )

    return _handler


# ---------------------------------------------------------------------------
# Builder: Global Synthesis (Reduce phase)
# ---------------------------------------------------------------------------


def build_global_synthesis_handler(agent: ExtractionAgent) -> Callable:
    """Return a python_handler closure for the global synthesis (Reduce) phase.

    Steps:
    1. Read all local_synthesis_{name}.json files.
    2. Merge + dedup all validated BDs by content[:50].
    3. Re-number IDs sequentially (BD-001, BD-002, …).
    4. Run one Instructor call for cross-module interaction reasoning.
    5. Merge interaction BDs into the canonical list.
    6. Write bd_list.json + step2c_business_decisions.md.
    """

    async def _handler(state: AgentState, repo_path: Path) -> PhaseResult:
        artifacts_dir = Path(state.run_dir) / "artifacts"
        # Merge step2c.md refs with worker_*.json candidate refs. Worker
        # candidates are produced at exploration time, so they are already
        # on disk when local/global synthesis fires — unlike step2c.md,
        # which is written later by bp_bd_r4_evidence and may be missing
        # on fresh v9 runs that schedule synthesis in parallel.
        _md = load_step2c_evidence_map(artifacts_dir)
        _worker = load_worker_candidate_evidence_map(artifacts_dir)
        # step2c wins on conflicts; worker fills the rest.
        md_evidence_map = {**_worker, **_md}
        total_tokens = 0

        # --- Collect all locally-synthesized BDs ---
        all_bds: list[BusinessDecision] = []
        for worker_name in _WORKER_NAMES:
            local_path = artifacts_dir / f"local_synthesis_{worker_name}.json"
            if not local_path.exists():
                logger.warning(
                    "global_synthesis: local_synthesis_%s.json not found — skipping",
                    worker_name,
                )
                continue
            try:
                local_data = json.loads(local_path.read_text(encoding="utf-8"))
                validated = local_data.get("validated", [])
                for i, bd_raw in enumerate(validated):
                    bd = _coerce_bd_dict(bd_raw, len(all_bds) + i, md_evidence_map)
                    if bd is not None:
                        all_bds.append(bd)
            except Exception as load_exc:
                logger.warning(
                    "global_synthesis: failed to load local_synthesis_%s.json: %s",
                    worker_name,
                    load_exc,
                )

        if not all_bds:
            return PhaseResult(
                phase_name="bp_global_synthesis_v9",
                status="error",
                total_tokens=total_tokens,
                error=(
                    "global_synthesis: no BDs from any local synthesis — pipeline cannot continue"
                ),
            )

        # --- Deduplicate by normalized full content ---
        # Use full content (lowered, stripped) instead of prefix[:50]
        # to avoid merging distinct decisions with similar openings.
        seen_content: set[str] = set()
        deduped: list[BusinessDecision] = []
        for bd in all_bds:
            key = bd.content.lower().strip()
            if key not in seen_content:
                seen_content.add(key)
                deduped.append(bd)

        # --- Re-number IDs sequentially ---
        for idx, bd in enumerate(deduped):
            bd.id = f"BD-{idx + 1:03d}"

        logger.info(
            "global_synthesis: %d BDs after dedup (from %d raw)",
            len(deduped),
            len(all_bds),
        )

        # --- Read audit findings for gap injection ---
        worker_audit = _safe_read(artifacts_dir / "worker_audit.md")

        # --- Interaction call ---
        global_user_msg = _build_global_user_message(deduped, worker_audit)
        logger.info("global_synthesis: running interaction call (%d BDs)", len(deduped))

        interaction_result, tokens_g = await agent.run_structured_call(
            GLOBAL_SYNTHESIS_SYSTEM,
            global_user_msg,
            BDExtractionResult,
            max_tokens=32768,
        )
        total_tokens += tokens_g

        # --- Merge interaction BDs ---
        if isinstance(interaction_result, RawFallback):
            raw_path = artifacts_dir / "global_synthesis_raw.txt"
            raw_path.write_text(interaction_result.text, encoding="utf-8")
            logger.warning(
                "global_synthesis: interaction call returned RawFallback — attempting L3 recovery"
            )
            interaction_raw = _extract_decisions_from_raw(
                interaction_result.text, "global_synthesis"
            )
            interaction_bds: list[BusinessDecision] = []
            for i, bd_raw in enumerate(interaction_raw):
                bd = _coerce_bd_dict(bd_raw, len(deduped) + i, md_evidence_map)
                if bd is not None:
                    interaction_bds.append(bd)
            logger.info(
                "global_synthesis: L3 recovery — %d interaction BDs",
                len(interaction_bds),
            )
        else:
            interaction_bds = interaction_result.decisions
            logger.info(
                "global_synthesis: +%d interaction BDs",
                len(interaction_bds),
            )

        # Merge: add interaction BDs with BD-INT-* prefix
        # (preserves interaction identity for downstream logic)
        existing_ids = {bd.id for bd in deduped}
        merged: list[BusinessDecision] = list(deduped)
        interaction_count = 0
        for bd in interaction_bds:
            if bd.id not in existing_ids:
                interaction_count += 1
                bd.id = f"BD-INT-{interaction_count:03d}"
                merged.append(bd)
                existing_ids.add(bd.id)

        logger.info(
            "global_synthesis: final BD list — %d total (%d base + %d interactions)",
            len(merged),
            len(deduped),
            interaction_count,
        )

        # --- Build final BDExtractionResult ---
        missing_bds = [bd for bd in merged if bd.status == "missing"]
        type_counts: dict[str, int] = dict(Counter(bd.type for bd in merged))
        final_result = BDExtractionResult(
            decisions=merged,
            type_summary=type_counts,
            missing_gaps=missing_bds,
        )

        # --- Write canonical artifacts ---
        bd_json = final_result.model_dump_json(indent=2)
        (artifacts_dir / "bd_list.json").write_text(bd_json, encoding="utf-8")

        # Backward-compatible markdown for bp_assemble
        from doramagic_extraction_agent.sop.blueprint_phases import _bd_to_markdown

        bd_md = _bd_to_markdown(final_result)
        (artifacts_dir / "step2c_business_decisions.md").write_text(bd_md, encoding="utf-8")

        logger.info(
            "global_synthesis done: %d BDs, %d missing gaps (%d tokens)",
            len(merged),
            len(missing_bds),
            total_tokens,
        )

        return PhaseResult(
            phase_name="bp_global_synthesis_v9",
            status="completed",
            iterations=2,
            total_tokens=total_tokens,
            final_text=bd_json,
        )

    return _handler


# ---------------------------------------------------------------------------
# Builder: Fixer (targeted evidence repair)
# ---------------------------------------------------------------------------


def build_fixer_handler(agent: ExtractionAgent) -> Callable:
    """Return a python_handler closure for the evidence fixer phase.

    Flow:
    1. Read evaluation_report.json (or quality_gate_result.json) to find BDs
       with evidence_validity issues.
    2. For each broken BD (up to 20):
       a. Check if the referenced file exists in the repo.
       b. If it exists, search for likely matching function signatures.
    3. One batched Instructor call to repair evidence.
    4. Apply fixes back to bd_list.json.
    """

    async def _handler(state: AgentState, repo_path: Path) -> PhaseResult:
        artifacts_dir = Path(state.run_dir) / "artifacts"
        # Merge step2c.md refs with worker_*.json candidate refs. Worker
        # candidates are produced at exploration time, so they are already
        # on disk when local/global synthesis fires — unlike step2c.md,
        # which is written later by bp_bd_r4_evidence and may be missing
        # on fresh v9 runs that schedule synthesis in parallel.
        _md = load_step2c_evidence_map(artifacts_dir)
        _worker = load_worker_candidate_evidence_map(artifacts_dir)
        # step2c wins on conflicts; worker fills the rest.
        md_evidence_map = {**_worker, **_md}
        total_tokens = 0

        # --- Load current BD list ---
        bd_list_path = artifacts_dir / "bd_list.json"
        if not bd_list_path.exists():
            return PhaseResult(
                phase_name="bp_fixer_v9",
                status="error",
                error="fixer: bd_list.json not found — cannot repair",
            )

        try:
            bd_list_raw = json.loads(bd_list_path.read_text(encoding="utf-8"))
            current_result = BDExtractionResult.model_validate(bd_list_raw)
        except Exception as load_exc:
            return PhaseResult(
                phase_name="bp_fixer_v9",
                status="error",
                error=f"fixer: failed to parse bd_list.json: {load_exc}",
            )

        # --- Identify broken BDs from evaluation report ---
        broken_bd_ids: set[str] = set()
        for report_name in ("evaluation_report.json", "quality_gate_result.json"):
            report_path = artifacts_dir / report_name
            if report_path.exists():
                try:
                    report_data = json.loads(report_path.read_text(encoding="utf-8"))
                    issues = report_data.get("issues", [])
                    for issue in issues:
                        if issue.get("contract") == "evidence_validity":
                            bid = issue.get("bd_id", "")
                            if bid:
                                broken_bd_ids.add(bid)
                except Exception as report_exc:
                    logger.warning("fixer: failed to parse %s: %s", report_name, report_exc)
                break  # use first found report

        # Also identify BDs whose evidence file does not exist in the repo
        # Skip interaction BDs (BD-INT-*) — their evidence is BD ID refs,
        # not file paths.
        repo_p = Path(repo_path) if not isinstance(repo_path, Path) else repo_path
        for bd in current_result.decisions:
            if bd.id in broken_bd_ids:
                continue
            if bd.id.startswith("BD-INT"):
                continue  # interaction BDs reference other BDs, not files
            ev = bd.evidence or ""
            # Extract file path from evidence string (file:line(fn))
            file_part = ev.split(":")[0].strip() if ":" in ev else ev.strip()
            if not file_part or file_part.startswith("N/A"):
                continue
            # Skip evidence that looks like BD references (e.g. "BD-003,BD-017")
            if file_part.startswith("BD-"):
                continue
            candidate_path = repo_p / file_part
            if not candidate_path.exists():
                broken_bd_ids.add(bd.id)

        if not broken_bd_ids:
            logger.info("fixer: no broken BDs found — skipping LLM call")
            return PhaseResult(
                phase_name="bp_fixer_v9",
                status="completed",
                iterations=0,
                total_tokens=0,
                final_text="fixer: nothing to repair",
            )

        # Cap at 20 to keep the Instructor call manageable
        broken_ids_capped = list(broken_bd_ids)[:20]
        logger.info(
            "fixer: %d broken BDs found (%d total), capping at 20",
            len(broken_bd_ids),
            len(current_result.decisions),
        )

        broken_bds = [bd for bd in current_result.decisions if bd.id in broken_ids_capped]

        # --- Build file-system repair context ---
        repair_context: list[dict[str, Any]] = []
        for bd in broken_bds:
            ev = bd.evidence or ""
            file_part = ev.split(":")[0].strip() if ":" in ev else ev.strip()
            candidate_path = repo_p / file_part if file_part else None

            ctx: dict[str, Any] = {
                "bd_id": bd.id,
                "broken_evidence": ev,
                "file_exists": False,
                "likely_functions": [],
            }

            if candidate_path and candidate_path.exists():
                ctx["file_exists"] = True
                # Search for function/class names related to BD content
                keywords = re.findall(r"\b\w{4,}\b", bd.content.lower())[:5]
                try:
                    file_text = candidate_path.read_text(encoding="utf-8", errors="ignore")
                    fn_matches: list[str] = []
                    for line_no, line in enumerate(file_text.splitlines(), start=1):
                        stripped = line.strip()
                        if stripped.startswith(("def ", "class ", "async def ")):
                            fn_name = stripped.split("(")[0].split()[-1].lower()
                            if any(kw in fn_name for kw in keywords):
                                fn_matches.append(f"{file_part}:{line_no}({fn_name})")
                    # Fall back: first 5 def/class lines
                    if not fn_matches:
                        for line_no, line in enumerate(file_text.splitlines(), start=1):
                            stripped = line.strip()
                            if stripped.startswith(("def ", "class ", "async def ")):
                                fn_name = stripped.split("(")[0].split()[-1]
                                fn_matches.append(f"{file_part}:{line_no}({fn_name})")
                            if len(fn_matches) >= 5:
                                break
                    ctx["likely_functions"] = fn_matches[:5]
                except OSError:
                    pass

            repair_context.append(ctx)

        # --- Instructor call ---
        from doramagic_extraction_agent.sop.schemas_v9 import FixerResult

        fixer_user_msg = _build_fixer_user_message(broken_bds, repair_context)
        logger.info("fixer: calling LLM with %d broken BDs", len(broken_bds))

        fixer_result, tokens_f = await agent.run_structured_call(
            FIXER_SYSTEM,
            fixer_user_msg,
            FixerResult,
        )
        total_tokens += tokens_f

        if isinstance(fixer_result, RawFallback):
            raw_path = artifacts_dir / "fixer_raw.txt"
            raw_path.write_text(fixer_result.text, encoding="utf-8")
            logger.warning("fixer: LLM returned RawFallback — no repairs applied")
            return PhaseResult(
                phase_name="bp_fixer_v9",
                status="completed",
                iterations=1,
                total_tokens=total_tokens,
                final_text="fixer: RawFallback — no repairs applied",
            )

        logger.info(
            "fixer: %d fixed, %d unfixable, %d dropped",
            len(fixer_result.fixed),
            len(fixer_result.unfixable),
            len(fixer_result.dropped),
        )

        # --- Apply fixes to BD list ---
        fixed_by_id: dict[str, dict[str, Any]] = {
            f["id"]: f for f in fixer_result.fixed if isinstance(f, dict) and "id" in f
        }
        dropped_ids: set[str] = set(fixer_result.dropped)

        updated_decisions: list[BusinessDecision] = []
        for bd in current_result.decisions:
            if bd.id in dropped_ids:
                logger.info("fixer: dropping BD %s (hallucinated evidence)", bd.id)
                continue
            if bd.id in fixed_by_id:
                fixed_raw = fixed_by_id[bd.id]
                repaired = _coerce_bd_dict(fixed_raw, 0, md_evidence_map)
                if repaired is not None:
                    repaired.id = bd.id  # preserve original ID
                    updated_decisions.append(repaired)
                    continue
            updated_decisions.append(bd)

        # Re-number after drops
        for idx, bd in enumerate(updated_decisions):
            bd.id = f"BD-{idx + 1:03d}"

        missing_bds = [bd for bd in updated_decisions if bd.status == "missing"]
        type_counts_fixed: dict[str, int] = dict(Counter(bd.type for bd in updated_decisions))
        repaired_result = BDExtractionResult(
            decisions=updated_decisions,
            type_summary=type_counts_fixed,
            missing_gaps=missing_bds,
        )

        bd_json = repaired_result.model_dump_json(indent=2)
        bd_list_path.write_text(bd_json, encoding="utf-8")

        # Update backward-compatible markdown
        from doramagic_extraction_agent.sop.blueprint_phases import _bd_to_markdown

        bd_md = _bd_to_markdown(repaired_result)
        (artifacts_dir / "step2c_business_decisions.md").write_text(bd_md, encoding="utf-8")

        logger.info(
            "fixer done: %d BDs remaining after repair/drop (%d tokens)",
            len(updated_decisions),
            total_tokens,
        )

        return PhaseResult(
            phase_name="bp_fixer_v9",
            status="completed",
            iterations=1,
            total_tokens=total_tokens,
            final_text=(
                f"fixed={len(fixer_result.fixed)} "
                f"unfixable={len(fixer_result.unfixable)} "
                f"dropped={len(fixer_result.dropped)}"
            ),
        )

    return _handler
