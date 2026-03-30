"""Stage 1.5 artifact and claim helpers."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from doramagic_contracts.base import EvidenceRef
from doramagic_contracts.extraction import (
    ClaimRecord,
    ExplorationLogEntry,
    Hypothesis,
    Stage15AgenticInput,
)

from .stage15_config import ARTIFACT_DIR_RELATIVE


def _repo_token(repo_id: str) -> str:
    """Produce a safe identifier token from a repo_id."""
    token = []
    for char in repo_id.upper():
        if char.isalnum():
            token.append(char)
        else:
            token.append("_")
    return "".join(token).strip("_") or "REPO"


def _artifact_paths(local_repo_path: str) -> tuple[Path, dict[str, str]]:
    repo_root = Path(local_repo_path).expanduser().resolve()
    artifact_dir = repo_root / ARTIFACT_DIR_RELATIVE
    relative_paths = {
        "hypotheses": str(ARTIFACT_DIR_RELATIVE / "hypotheses.jsonl"),
        "exploration_log": str(ARTIFACT_DIR_RELATIVE / "exploration_log.jsonl"),
        "claim_ledger": str(ARTIFACT_DIR_RELATIVE / "claim_ledger.jsonl"),
        "evidence_index": str(ARTIFACT_DIR_RELATIVE / "evidence_index.json"),
        "context_digest": str(ARTIFACT_DIR_RELATIVE / "context_digest.md"),
    }
    return artifact_dir, relative_paths


def _write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            handle.write("\n")


def _safe_dump(model: Any) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return dict(model)


def _evidence_key(evidence: EvidenceRef) -> str:
    return f"{evidence.path}:{evidence.start_line}:{evidence.end_line}"


def _budget_exceeded(
    tool_calls: int,
    prompt_tokens: int,
    input_data: Stage15AgenticInput,
) -> bool:
    if tool_calls >= input_data.budget.max_tool_calls:
        return True
    if prompt_tokens >= input_data.budget.max_prompt_tokens:
        return True
    return False


def _parse_json_from_llm(text: str) -> dict | None:
    """Extract the first JSON object from LLM output, tolerating markdown fences."""
    # Strip markdown code fences if present
    stripped = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.MULTILINE)
    stripped = re.sub(r"\s*```\s*$", "", stripped, flags=re.MULTILINE)
    stripped = stripped.strip()

    # Try direct parse first
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    # Try to find a JSON object within the text
    match = re.search(r"\{.*\}", stripped, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    return None


def _synthesize_claim_statement(
    hypothesis: Hypothesis,
    status: str,
    reasoning: str,
) -> str:
    if status == "confirmed":
        return f"CONFIRMED: {hypothesis.statement} — {reasoning}"
    if status == "rejected":
        return f"REJECTED: {hypothesis.statement} — {reasoning}"
    return f"PENDING: {hypothesis.statement} — {reasoning}"


def check_claims_have_evidence(
    claims: Sequence[ClaimRecord],
    exploration_log: Sequence[Any],
) -> bool:
    """Verify confirmed claims have file:line evidence and step-level traceability."""
    # Normalise input — items may be raw dicts from JSONL
    normalized_steps = []
    for entry in exploration_log:
        if isinstance(entry, ExplorationLogEntry):
            normalized_steps.append(entry)
        elif isinstance(entry, dict):
            try:
                normalized_steps.append(ExplorationLogEntry.model_validate(entry))
            except Exception:
                pass

    normalized_claims = []
    for claim in claims:
        if isinstance(claim, ClaimRecord):
            normalized_claims.append(claim)
        elif isinstance(claim, dict):
            try:
                normalized_claims.append(ClaimRecord.model_validate(claim))
            except Exception:
                pass

    steps_by_id = {entry.step_id: entry for entry in normalized_steps}

    for claim in normalized_claims:
        if claim.status != "confirmed":
            continue
        if not claim.evidence_refs:
            return False
        if not claim.supporting_step_ids:
            return False

        seen_keys: set = set()
        for step_id in claim.supporting_step_ids:
            step = steps_by_id.get(step_id)
            if step is None:
                return False
            for evidence in step.produced_evidence_refs:
                seen_keys.add(_evidence_key(evidence))

        for evidence in claim.evidence_refs:
            if evidence.kind != "file_line":
                return False
            if evidence.start_line is None or evidence.end_line is None:
                return False
            if _evidence_key(evidence) not in seen_keys:
                return False

    return True


def _write_artifacts(
    artifact_dir: Path,
    ordered_hypotheses: list[Hypothesis],
    exploration_log: list[ExplorationLogEntry],
    claim_ledger: list[ClaimRecord],
    promoted_claims: list[ClaimRecord],
    input_data: Stage15AgenticInput,
    tool_calls: int,
    termination_reason: str,
) -> None:
    artifact_dir.mkdir(parents=True, exist_ok=True)

    _write_jsonl(
        artifact_dir / "hypotheses.jsonl",
        (_safe_dump(h) for h in ordered_hypotheses),
    )
    _write_jsonl(
        artifact_dir / "exploration_log.jsonl",
        (_safe_dump(e) for e in exploration_log),
    )
    _write_jsonl(
        artifact_dir / "claim_ledger.jsonl",
        (_safe_dump(c) for c in claim_ledger),
    )

    # Evidence index
    evidence_index: dict[str, dict] = {}
    for claim in claim_ledger:
        for evidence in claim.evidence_refs:
            key = _evidence_key(evidence)
            if key not in evidence_index:
                evidence_index[key] = {
                    "path": evidence.path,
                    "start_line": evidence.start_line,
                    "end_line": evidence.end_line,
                    "snippet": evidence.snippet,
                    "claim_ids": [],
                }
            evidence_index[key]["claim_ids"].append(claim.claim_id)

    (artifact_dir / "evidence_index.json").write_text(
        json.dumps(
            {
                "repo_id": input_data.repo.repo_id,
                "evidence_items": list(evidence_index.values()),
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    # Context digest
    context_digest = (
        "# Stage 1.5 Context Digest\n\n"
        f"- Repo: `{input_data.repo.repo_id}`\n"
        f"- Findings available: {len(input_data.stage1_output.findings)}\n"
        f"- Hypotheses explored: {len(ordered_hypotheses)}\n"
        f"- Promoted (confirmed) claims: {len(promoted_claims)}\n"
        f"- Total claims: {len(claim_ledger)}\n"
        f"- Tool calls: {tool_calls}\n"
        f"- Termination: `{termination_reason}`\n"
    )
    (artifact_dir / "context_digest.md").write_text(context_digest, encoding="utf-8")
