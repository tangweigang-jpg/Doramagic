"""v9 Evaluation Separation module.

Splits the monolithic agentic evaluator (bp_evaluate) into two parallel tracks:

- Track A: Deterministic Python (file/line/function verification) — zero LLM tokens
- Track B: Semantic LLM judge (rationale quality, classification correctness) — one
  Instructor call (up to 30 sampled non-T BDs)

Each track runs independently and concurrently via asyncio.gather. Results are merged
into a single evaluation_report.json artifact.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from doramagic_extraction_agent.core.agent_loop import ExtractionAgent, PhaseResult
from doramagic_extraction_agent.sop.schemas_v5 import RawFallback
from doramagic_extraction_agent.state.schema import AgentState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Evidence pattern — same regex used by _patch_evidence_verify in blueprint_enrich
# ---------------------------------------------------------------------------

_EV_PATTERN = re.compile(r"^(.+?):(\d+(?:[,\-]\d+)*)\((.+?)\)$")

# ---------------------------------------------------------------------------
# System prompt for Track B (semantic evaluator)
# ---------------------------------------------------------------------------

SEMANTIC_EVAL_SYSTEM = """\
You are a BD quality evaluator. For each Business Decision, assess:

1. RATIONALE QUALITY:
   - PASS: Contains both WHY (reason for choosing this approach) and BOUNDARY \
(conditions where it fails)
   - SHALLOW: Has WHY but missing BOUNDARY, or vice versa
   - MISSING_BOUNDARY: Only restates the decision, no reasoning

2. TYPE CORRECTNESS:
   - CORRECT: Classification matches the decision content
   - OVER_CLASSIFIED: Should be T (trivial) but classified as B/BA/etc
   - UNDER_CLASSIFIED: Should be more specific (e.g., B should be B/BA)

Return a SemanticEvalResult JSON. Do NOT wrap in markdown code fences.
"""

# ---------------------------------------------------------------------------
# Pydantic models for Track B output
# ---------------------------------------------------------------------------


class BDSemanticVerdict(BaseModel):
    bd_id: str = ""
    rationale_verdict: str = "PASS"
    type_verdict: str = "CORRECT"
    note: str = ""

    @field_validator("rationale_verdict", mode="before")
    @classmethod
    def coerce_rationale(cls, v: Any) -> str:
        """Fuzzy-match MiniMax output to valid verdicts."""
        if not isinstance(v, str):
            return "PASS"
        v = v.strip().upper()
        if "SHALLOW" in v:
            return "SHALLOW"
        if "MISSING" in v or "BOUNDARY" in v:
            return "MISSING_BOUNDARY"
        return "PASS"

    @field_validator("type_verdict", mode="before")
    @classmethod
    def coerce_type_verdict(cls, v: Any) -> str:
        """Fuzzy-match MiniMax output to valid verdicts."""
        if not isinstance(v, str):
            return "CORRECT"
        v = v.strip().upper()
        if "OVER" in v:
            return "OVER_CLASSIFIED"
        if "UNDER" in v:
            return "UNDER_CLASSIFIED"
        return "CORRECT"


class SemanticEvalResult(BaseModel):
    evaluations: list[BDSemanticVerdict] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def coerce_minimax_quirks(cls, data: Any) -> Any:
        """Handle MiniMax output variations."""
        if isinstance(data, list):
            return {"evaluations": data}
        if isinstance(data, dict) and "evaluations" not in data:
            # MiniMax may use different key names
            for key in ("results", "verdicts", "items", "data"):
                if key in data and isinstance(data[key], list):
                    data["evaluations"] = data.pop(key)
                    break
        return data


# ---------------------------------------------------------------------------
# Track A: Deterministic evaluation (pure Python, zero LLM)
# ---------------------------------------------------------------------------


async def deterministic_eval(
    bd_list: list[dict[str, Any]],
    repo_path: Path,
) -> list[dict[str, Any]]:
    """Pure Python evidence verification for all non-T BDs.

    For each non-T BD:
    1. Parse evidence string: extract file, line, function.
    2. Check if file exists at repo_path / file.
    3. If exists, check if line number is within file line count.
    4. If line valid, check if function name appears in the file (string search).

    Returns a list of verdict dicts.
    Raises no exceptions — failures are captured as verdicts.
    """
    verdicts: list[dict[str, Any]] = []

    for bd in bd_list:
        bd_id: str = bd.get("id", "UNKNOWN")
        bd_type: str = bd.get("type", "B")

        # Skip trivial BDs (T or starts with T/)
        if bd_type == "T" or bd_type.startswith("T/"):
            continue

        evidence: str = bd.get("evidence", "")

        # Skip N/A or empty evidence
        if not evidence or evidence.startswith("N/A"):
            verdicts.append(
                {
                    "bd_id": bd_id,
                    "file_exists": False,
                    "line_valid": False,
                    "function_found": False,
                    "verdict": "FILE_MISSING",
                    "note": "evidence is N/A or empty",
                }
            )
            continue

        # Skip document section evidence (§ marker)
        if "\u00a7" in evidence:
            verdicts.append(
                {
                    "bd_id": bd_id,
                    "file_exists": True,
                    "line_valid": True,
                    "function_found": True,
                    "verdict": "VALID",
                    "note": "document section evidence — skipped deterministic check",
                }
            )
            continue

        # Skip BD-reference evidence (e.g. "BD-003,BD-017" for interaction BDs)
        if evidence.strip().startswith("BD-"):
            verdicts.append(
                {
                    "bd_id": bd_id,
                    "file_exists": True,
                    "line_valid": True,
                    "function_found": True,
                    "verdict": "VALID",
                    "note": "BD-reference evidence — not a file path",
                }
            )
            continue

        m = _EV_PATTERN.match(evidence)
        if not m:
            # Cannot parse — treat as missing file
            verdicts.append(
                {
                    "bd_id": bd_id,
                    "file_exists": False,
                    "line_valid": False,
                    "function_found": False,
                    "verdict": "FILE_MISSING",
                    "note": f"cannot parse evidence format: {evidence!r}",
                }
            )
            continue

        file_rel: str = m.group(1)
        line_str: str = m.group(2)
        fn_name: str = m.group(3)

        try:
            # v10: support line ranges like "10-50" or "42,100" — use first number
            line_no = int(line_str.split("-")[0].split(",")[0])
        except ValueError:
            verdicts.append(
                {
                    "bd_id": bd_id,
                    "file_exists": False,
                    "line_valid": False,
                    "function_found": False,
                    "verdict": "LINE_INVALID",
                    "note": f"line number non-numeric: {line_str!r}",
                }
            )
            continue

        full_path = repo_path / file_rel

        # Check 1: file exists
        if not full_path.exists():
            verdicts.append(
                {
                    "bd_id": bd_id,
                    "file_exists": False,
                    "line_valid": False,
                    "function_found": False,
                    "verdict": "FILE_MISSING",
                    "note": f"file not found: {file_rel}",
                }
            )
            continue

        # Check 2: line number valid
        try:
            file_text = full_path.read_text(encoding="utf-8", errors="replace")
            file_lines = file_text.splitlines()
        except OSError as read_err:
            verdicts.append(
                {
                    "bd_id": bd_id,
                    "file_exists": True,
                    "line_valid": False,
                    "function_found": False,
                    "verdict": "LINE_INVALID",
                    "note": f"cannot read file: {read_err}",
                }
            )
            continue

        if line_no < 1 or line_no > len(file_lines):
            verdicts.append(
                {
                    "bd_id": bd_id,
                    "file_exists": True,
                    "line_valid": False,
                    "function_found": False,
                    "verdict": "LINE_INVALID",
                    "note": (f"line {line_no} out of range (file has {len(file_lines)} lines)"),
                }
            )
            continue

        # Check 3: function name appears in file (simple string search)
        fn_found = fn_name in file_text if fn_name and fn_name not in ("see_rationale",) else True

        if not fn_found:
            verdicts.append(
                {
                    "bd_id": bd_id,
                    "file_exists": True,
                    "line_valid": True,
                    "function_found": False,
                    "verdict": "FUNCTION_MISSING",
                    "note": f"function '{fn_name}' not found in {file_rel}",
                }
            )
            continue

        verdicts.append(
            {
                "bd_id": bd_id,
                "file_exists": True,
                "line_valid": True,
                "function_found": True,
                "verdict": "VALID",
            }
        )

    return verdicts


# ---------------------------------------------------------------------------
# Track B: Semantic evaluation (one Instructor call)
# ---------------------------------------------------------------------------


async def semantic_eval(
    agent: ExtractionAgent,
    bd_list: list[dict[str, Any]],
    state: AgentState,
) -> list[dict[str, Any]]:
    """Semantic quality evaluation via one Instructor call.

    Samples up to 30 non-T BDs. Evaluates:
    - Rationale quality (PASS / SHALLOW / MISSING_BOUNDARY)
    - Type correctness (CORRECT / OVER_CLASSIFIED / UNDER_CLASSIFIED)

    Returns a list of verdict dicts on success, empty list on failure.
    """
    # Filter non-T BDs
    non_t_bds = [
        bd
        for bd in bd_list
        if bd.get("type", "B") != "T" and not str(bd.get("type", "B")).startswith("T/")
    ]

    if not non_t_bds:
        logger.info("semantic_eval: no non-T BDs to evaluate")
        return []

    # Sample up to 30
    if len(non_t_bds) > 30:
        sample = random.sample(non_t_bds, 30)
        logger.info(
            "semantic_eval: sampling 30 of %d non-T BDs",
            len(non_t_bds),
        )
    else:
        sample = non_t_bds
        logger.info("semantic_eval: evaluating all %d non-T BDs", len(sample))

    # Build user message: include only relevant fields to save tokens
    compact = [
        {
            "id": bd.get("id", "?"),
            "type": bd.get("type", "B"),
            "content": bd.get("content", ""),
            "rationale": bd.get("rationale", ""),
        }
        for bd in sample
    ]
    user_msg = (
        f"## BD List for Evaluation ({len(compact)} BDs)\n\n"
        f"```json\n{json.dumps(compact, ensure_ascii=False, indent=2)}\n```\n\n"
        "Return a SemanticEvalResult JSON with one verdict per BD."
    )

    logger.info("semantic_eval: calling LLM for %d BDs", len(compact))

    result, tokens = await agent.run_structured_call(
        SEMANTIC_EVAL_SYSTEM,
        user_msg,
        SemanticEvalResult,
    )

    if isinstance(result, RawFallback):
        logger.warning(
            "semantic_eval: LLM returned RawFallback (%d chars) — no semantic verdicts",
            len(result.text),
        )
        return []

    logger.info(
        "semantic_eval: %d verdicts returned (%d tokens)",
        len(result.evaluations),
        tokens,
    )

    return [v.model_dump() for v in result.evaluations]


# ---------------------------------------------------------------------------
# Builder: Evaluate v9 (closure pattern — same as synthesis_v9.py)
# ---------------------------------------------------------------------------


def build_evaluate_v9_handler(agent: ExtractionAgent) -> Callable:
    """Return a python_handler closure for the v9 evaluation phase.

    Flow:
    1. Reads bd_list.json from artifacts_dir.
    2. Runs Track A (deterministic) and Track B (semantic) concurrently.
    3. Merges results into evaluation_report.json.
    4. Returns a PhaseResult with summary.

    The handler is a python_handler (requires_llm=False) because it manages
    its own LLM calls internally via agent.run_structured_call.
    """

    async def _handler(state: AgentState, repo_path: Path) -> PhaseResult:
        artifacts_dir = Path(state.run_dir) / "artifacts"

        # --- Load bd_list.json ---
        bd_list_path = artifacts_dir / "bd_list.json"
        if not bd_list_path.exists():
            return PhaseResult(
                phase_name="bp_evaluate_v9",
                status="error",
                error="evaluate_v9: bd_list.json not found — cannot evaluate",
            )

        try:
            raw_data = json.loads(bd_list_path.read_text(encoding="utf-8"))
        except Exception as parse_exc:
            return PhaseResult(
                phase_name="bp_evaluate_v9",
                status="error",
                error=f"evaluate_v9: failed to parse bd_list.json: {parse_exc}",
            )

        # Support both bare list and BDExtractionResult wrapper
        if isinstance(raw_data, list):
            bd_list: list[dict[str, Any]] = raw_data
        elif isinstance(raw_data, dict):
            bd_list = raw_data.get("decisions", [])
        else:
            return PhaseResult(
                phase_name="bp_evaluate_v9",
                status="error",
                error="evaluate_v9: bd_list.json has unexpected format",
            )

        if not bd_list:
            logger.warning("evaluate_v9: bd_list is empty — writing empty report")
            report: dict[str, Any] = {
                "track_a": [],
                "track_b": [],
                "summary": {
                    "total_bds": 0,
                    "deterministic_valid": 0,
                    "deterministic_invalid": 0,
                    "semantic_pass": 0,
                    "semantic_shallow": 0,
                    "semantic_missing_boundary": 0,
                },
                "issues": [],
            }
            (artifacts_dir / "evaluation_report.json").write_text(
                json.dumps(report, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            return PhaseResult(
                phase_name="bp_evaluate_v9",
                status="completed",
                iterations=0,
                total_tokens=0,
                final_text="evaluate_v9: empty bd_list — wrote empty report",
            )

        repo_p = Path(repo_path) if not isinstance(repo_path, Path) else repo_path

        logger.info(
            "evaluate_v9: starting parallel evaluation of %d BDs",
            len(bd_list),
        )

        # --- Run Track A and Track B concurrently ---
        track_a_task = deterministic_eval(bd_list, repo_p)
        track_b_task = semantic_eval(agent, bd_list, state)

        track_a_verdicts, track_b_verdicts = await asyncio.gather(track_a_task, track_b_task)

        logger.info(
            "evaluate_v9: Track A=%d verdicts, Track B=%d verdicts",
            len(track_a_verdicts),
            len(track_b_verdicts),
        )

        # --- Build summary statistics ---
        det_valid = sum(1 for v in track_a_verdicts if v.get("verdict") == "VALID")
        det_invalid = len(track_a_verdicts) - det_valid

        sem_pass = sum(1 for v in track_b_verdicts if v.get("rationale_verdict") == "PASS")
        sem_shallow = sum(1 for v in track_b_verdicts if v.get("rationale_verdict") == "SHALLOW")
        sem_missing_boundary = sum(
            1 for v in track_b_verdicts if v.get("rationale_verdict") == "MISSING_BOUNDARY"
        )

        # --- Build issues list (compatible with fixer's expected format) ---
        issues: list[dict[str, Any]] = []
        for v in track_a_verdicts:
            if v.get("verdict") != "VALID":
                issues.append(
                    {
                        "bd_id": v["bd_id"],
                        "contract": "evidence_validity",
                        "track": "A",
                        "verdict": v.get("verdict"),
                        "note": v.get("note", ""),
                    }
                )
        for v in track_b_verdicts:
            if v.get("rationale_verdict") in ("SHALLOW", "MISSING_BOUNDARY"):
                issues.append(
                    {
                        "bd_id": v["bd_id"],
                        "contract": "rationale_quality",
                        "track": "B",
                        "rationale_verdict": v.get("rationale_verdict"),
                        "type_verdict": v.get("type_verdict"),
                        "note": v.get("note", ""),
                    }
                )
            if v.get("type_verdict") != "CORRECT":
                issues.append(
                    {
                        "bd_id": v["bd_id"],
                        "contract": "type_correctness",
                        "track": "B",
                        "type_verdict": v.get("type_verdict"),
                        "note": v.get("note", ""),
                    }
                )

        report = {
            "track_a": track_a_verdicts,
            "track_b": track_b_verdicts,
            "summary": {
                "total_bds": len(bd_list),
                "evaluated_non_t": len(track_a_verdicts),
                "deterministic_valid": det_valid,
                "deterministic_invalid": det_invalid,
                "semantic_evaluated": len(track_b_verdicts),
                "semantic_pass": sem_pass,
                "semantic_shallow": sem_shallow,
                "semantic_missing_boundary": sem_missing_boundary,
            },
            "issues": issues,
        }

        (artifacts_dir / "evaluation_report.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        logger.info(
            "evaluate_v9 done: %d BDs | Track A: %d valid / %d invalid "
            "| Track B: %d pass / %d shallow / %d missing_boundary "
            "| %d issues total",
            len(bd_list),
            det_valid,
            det_invalid,
            sem_pass,
            sem_shallow,
            sem_missing_boundary,
            len(issues),
        )

        summary_text = (
            f"total={len(bd_list)} "
            f"det_valid={det_valid} det_invalid={det_invalid} "
            f"sem_pass={sem_pass} sem_shallow={sem_shallow} "
            f"sem_missing_boundary={sem_missing_boundary} "
            f"issues={len(issues)}"
        )

        return PhaseResult(
            phase_name="bp_evaluate_v9",
            status="completed",
            iterations=2,  # Track A + Track B
            total_tokens=0,  # tokens tracked inside semantic_eval but not surfaced here
            final_text=summary_text,
        )

    return _handler
