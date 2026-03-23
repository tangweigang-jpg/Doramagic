"""Stage 1.5 — Real Agentic Exploration Loop.

This module implements a genuine agent loop that:
1. Sorts hypotheses by priority (high → medium → low)
2. For each hypothesis, asks the LLM which tool to use
3. Executes the tool against the real repository on disk
4. Feeds tool results back to the LLM to evaluate hypothesis status
5. Writes confirmed/rejected claims to claim_ledger with file:line evidence
6. Continues until budget exhausted or all hypotheses resolved

When adapter=None, falls back to the deterministic mock in the base module.

All LLM calls go through LLMAdapter from doramagic_shared_utils.
Direct anthropic/openai/google imports are forbidden here.
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# sys.path setup (mirrors the pattern used in stage15_agentic.py base)
# ---------------------------------------------------------------------------

_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parent.parent.parent.parent  # races/r06/agentic/s1-sonnet/../../../..
_CONTRACTS_DIR = _REPO_ROOT / "packages" / "contracts"
_SHARED_UTILS_DIR = _REPO_ROOT / "packages" / "shared_utils"
_EXTRACTION_DIR = _REPO_ROOT / "packages" / "extraction"

for _p in [str(_CONTRACTS_DIR), str(_SHARED_UTILS_DIR), str(_EXTRACTION_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from doramagic_contracts.base import EvidenceRef  # noqa: E402
from doramagic_contracts.envelope import (  # noqa: E402
    ErrorCodes,
    ModuleResultEnvelope,
    RunMetrics,
    WarningItem,
)
from doramagic_contracts.extraction import (  # noqa: E402
    ClaimRecord,
    ExplorationLogEntry,
    Hypothesis,
    Stage15AgenticInput,
    Stage15AgenticOutput,
    Stage15Summary,
    Stage1Finding,
)
from doramagic_shared_utils.llm_adapter import LLMAdapter, LLMMessage  # noqa: E402
from doramagic_shared_utils.capability_router import (  # noqa: E402
    CapabilityRouter,
    TASK_TOOL_SELECTION,
    TASK_HYPOTHESIS_EVALUATION,
)

logger = logging.getLogger(__name__)

MODULE_NAME = "extraction.stage15_agentic"
ARTIFACT_DIR_RELATIVE = Path("artifacts") / "stage15"
PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}

# Max lines to read from a file snippet
_MAX_SNIPPET_LINES = 40
# Max bytes returned from search_repo
_MAX_SEARCH_OUTPUT_BYTES = 4000
# Max directory listing entries
_MAX_TREE_ENTRIES = 60

# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are an expert code analyst helping to verify hypotheses about a software repository.
Your job is to investigate hypotheses by selecting tools, observing results, and drawing
evidence-backed conclusions.

Available tools:
- list_tree: List files and directories in the repository
- search_repo: Grep for patterns in the repository source code
- read_file: Read a specific file (or a line range) from the repository
- read_artifact: Access Stage 1 findings already extracted
- append_finding: Record a confirmed/rejected/pending claim and stop exploring this hypothesis

Rules:
1. Always respond with valid JSON matching the schema shown.
2. Choose the tool most likely to confirm or reject the hypothesis efficiently.
3. For search_repo, use specific, targeted grep patterns.
4. For read_file, prefer short line ranges (≤40 lines) to avoid token waste.
5. After observing enough evidence, use append_finding to record your conclusion.
6. A confirmed claim MUST cite a specific file:line snippet as evidence.
7. A rejected claim MUST explain what evidence contradicts the hypothesis.
"""

_TOOL_SELECTION_PROMPT = """\
## Hypothesis under investigation
ID: {hypothesis_id}
Statement: {statement}
Reason: {reason}
Priority: {priority}
Search hints: {search_hints}

## Repository context
{repo_context}

## Exploration history so far (this hypothesis)
{history}

## Task
Select the next tool to call to investigate this hypothesis.
Respond with JSON exactly in this format:
{{
  "tool": "<tool_name>",
  "tool_input": {{ <tool-specific parameters> }},
  "reasoning": "<one sentence explaining why>"
}}

Tool input schemas:
- list_tree: {{"path": "<relative dir path, default '.'>"}}
- search_repo: {{"pattern": "<grep regex>", "file_glob": "<glob or null>", "max_results": <int 1-20>}}
- read_file: {{"path": "<relative file path>", "start_line": <int or null>, "end_line": <int or null>}}
- read_artifact: {{"artifact": "stage1_output.findings", "related_finding_ids": [...]}}
- append_finding: {{"status": "<confirmed|rejected|pending>", "statement": "<claim text>", "confidence": "<high|medium|low>", "evidence_path": "<file path or null>", "evidence_start_line": <int or null>, "evidence_end_line": <int or null>, "evidence_snippet": "<snippet or null>"}}
"""

_EVALUATION_PROMPT = """\
## Hypothesis under investigation
ID: {hypothesis_id}
Statement: {statement}
Priority: {priority}

## Tool call made
Tool: {tool_name}
Input: {tool_input}

## Observation
{observation}

## Exploration history (this hypothesis)
{history}

## Task
Based on this observation, what is your updated assessment of the hypothesis?
Respond with JSON exactly in this format:
{{
  "hypothesis_status": "<confirmed|rejected|pending>",
  "confidence": "<high|medium|low>",
  "reasoning": "<explanation>",
  "should_continue": <true|false>,
  "next_action_hint": "<brief hint for next tool call, or empty if done>"
}}

- Use "confirmed" only if you observed direct file:line evidence supporting the hypothesis.
- Use "rejected" only if you observed direct evidence contradicting the hypothesis.
- Use "pending" if you need more information.
- Set should_continue=false when you have enough to make a final call via append_finding.
"""


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


def _repo_token(repo_id: str) -> str:
    """Produce a safe identifier token from a repo_id."""
    token = []
    for char in repo_id.upper():
        if char.isalnum():
            token.append(char)
        else:
            token.append("_")
    return "".join(token).strip("_") or "REPO"


def _artifact_paths(local_repo_path: str) -> Tuple[Path, Dict[str, str]]:
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


def _sorted_hypotheses(hypotheses: Sequence[Hypothesis]) -> List[Hypothesis]:
    return sorted(
        hypotheses,
        key=lambda item: (PRIORITY_ORDER.get(item.priority, 99), item.hypothesis_id),
    )


def _estimate_tokens(*parts: str) -> int:
    total_chars = sum(len(part) for part in parts if part)
    return max(10, total_chars // 4)


def _evidence_key(evidence: EvidenceRef) -> str:
    return "{0}:{1}:{2}".format(evidence.path, evidence.start_line, evidence.end_line)


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


def _parse_json_from_llm(text: str) -> Optional[dict]:
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


# ---------------------------------------------------------------------------
# Tool executors (real implementations)
# ---------------------------------------------------------------------------


def _tool_list_tree(repo_root: Path, tool_input: dict) -> str:
    """List directory tree of the repository."""
    rel_path = tool_input.get("path", ".")
    target = (repo_root / rel_path).resolve()
    # Safety: don't escape the repo root
    try:
        target.relative_to(repo_root)
    except ValueError:
        return "ERROR: path escapes repository root"

    if not target.exists():
        return "Directory not found: {0}".format(rel_path)

    entries: List[str] = []
    try:
        for item in sorted(target.rglob("*")):
            rel = item.relative_to(repo_root)
            if any(part.startswith(".") for part in rel.parts):
                continue  # skip hidden dirs
            if any(part in ("node_modules", "__pycache__", ".git", "dist", "build") for part in rel.parts):
                continue
            prefix = "  " * (len(rel.parts) - 1)
            suffix = "/" if item.is_dir() else ""
            entries.append("{0}{1}{2}".format(prefix, item.name, suffix))
            if len(entries) >= _MAX_TREE_ENTRIES:
                entries.append("... (truncated)")
                break
    except PermissionError as exc:
        return "Permission error listing tree: {0}".format(exc)

    return "\n".join(entries) if entries else "(empty directory)"


def _tool_search_repo(repo_root: Path, tool_input: dict) -> str:
    """Grep the repository for a pattern."""
    pattern = tool_input.get("pattern", "")
    file_glob = tool_input.get("file_glob") or "*"
    max_results = min(int(tool_input.get("max_results", 10)), 20)

    if not pattern:
        return "ERROR: pattern is required for search_repo"

    if not repo_root.exists():
        # Fallback: can't search a non-existent repo
        return "Repository not found at: {0}".format(repo_root)

    try:
        cmd = ["grep", "-rn", "--include={0}".format(file_glob), "-m", str(max_results), pattern, str(repo_root)]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
        )
        output = result.stdout or result.stderr or "(no matches)"
        # Trim absolute path prefix so output is relative
        output = output.replace(str(repo_root) + "/", "")
        return output[:_MAX_SEARCH_OUTPUT_BYTES]
    except subprocess.TimeoutExpired:
        return "ERROR: search timed out"
    except FileNotFoundError:
        # grep not available; try Python fallback
        return _python_grep(repo_root, pattern, file_glob, max_results)
    except Exception as exc:
        return "ERROR: search failed: {0}".format(exc)


def _python_grep(repo_root: Path, pattern: str, file_glob: str, max_results: int) -> str:
    """Python-based grep fallback when system grep is unavailable."""
    results: List[str] = []
    try:
        regex = re.compile(pattern)
    except re.error as exc:
        return "ERROR: invalid regex pattern: {0}".format(exc)

    glob = "**/{0}".format(file_glob) if file_glob != "*" else "**/*"
    try:
        for file_path in sorted(repo_root.rglob(glob.replace("**/", ""))):
            if not file_path.is_file():
                continue
            if any(p.startswith(".") for p in file_path.parts):
                continue
            try:
                lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
                for lineno, line in enumerate(lines, 1):
                    if regex.search(line):
                        rel = file_path.relative_to(repo_root)
                        results.append("{0}:{1}: {2}".format(rel, lineno, line.rstrip()))
                        if len(results) >= max_results:
                            return "\n".join(results)
            except (PermissionError, OSError):
                continue
    except Exception:
        pass

    return "\n".join(results) if results else "(no matches)"


def _tool_read_file(repo_root: Path, tool_input: dict) -> Tuple[str, Optional[EvidenceRef]]:
    """Read a file or line range from the repository.

    Returns (observation_text, evidence_ref_or_None).
    """
    rel_path = tool_input.get("path")
    if not rel_path:
        return "ERROR: path is required for read_file", None

    target = (repo_root / rel_path).resolve()
    try:
        target.relative_to(repo_root)
    except ValueError:
        return "ERROR: path escapes repository root", None

    if not target.exists():
        return "File not found: {0}".format(rel_path), None

    try:
        all_lines = target.read_text(encoding="utf-8", errors="ignore").splitlines()
    except (PermissionError, OSError) as exc:
        return "ERROR reading file: {0}".format(exc), None

    start_line = tool_input.get("start_line")
    end_line = tool_input.get("end_line")

    if start_line is not None:
        start_idx = max(0, int(start_line) - 1)
        end_idx = min(len(all_lines), int(end_line) if end_line else start_idx + _MAX_SNIPPET_LINES)
    else:
        start_idx = 0
        end_idx = min(len(all_lines), _MAX_SNIPPET_LINES)

    # Clamp range
    if end_idx - start_idx > _MAX_SNIPPET_LINES:
        end_idx = start_idx + _MAX_SNIPPET_LINES

    snippet_lines = all_lines[start_idx:end_idx]
    snippet = "\n".join(
        "{0}: {1}".format(start_idx + i + 1, line)
        for i, line in enumerate(snippet_lines)
    )
    summary = "Read {0} lines ({1}-{2}) from {3}:\n{4}".format(
        len(snippet_lines),
        start_idx + 1,
        start_idx + len(snippet_lines),
        rel_path,
        snippet,
    )

    actual_start = start_idx + 1
    actual_end = start_idx + len(snippet_lines)
    if actual_end < actual_start:
        actual_end = actual_start  # guard against empty range

    evidence = EvidenceRef(
        kind="file_line",
        path=str(rel_path),
        start_line=actual_start,
        end_line=actual_end,
        snippet="\n".join(snippet_lines[:5]),  # keep snippet concise
    )
    return summary, evidence


def _tool_read_artifact(
    findings: List[Stage1Finding],
    tool_input: dict,
) -> str:
    """Return Stage 1 findings as formatted text."""
    related_ids = tool_input.get("related_finding_ids") or []
    if related_ids:
        selected = [f for f in findings if f.finding_id in related_ids]
    else:
        selected = findings

    if not selected:
        return "No Stage 1 findings available for: {0}".format(related_ids or "all")

    parts = []
    for finding in selected:
        parts.append("[{0}] {1}: {2}".format(finding.knowledge_type, finding.finding_id, finding.title))
        parts.append("Statement: {0}".format(finding.statement))
        parts.append("Confidence: {0}".format(finding.confidence))
        for ref in finding.evidence_refs:
            if ref.kind == "file_line":
                parts.append("Evidence: {0}:{1}-{2}".format(ref.path, ref.start_line, ref.end_line))
                if ref.snippet:
                    parts.append("  Snippet: {0}".format(ref.snippet[:200]))
        parts.append("")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Conversation history formatting
# ---------------------------------------------------------------------------


def _format_history(steps: List[Tuple[str, str, str, str]]) -> str:
    """Format exploration history as a readable string.

    Each tuple is (step_id, tool_name, tool_input_json, observation).
    """
    if not steps:
        return "(no prior steps for this hypothesis)"
    lines = []
    for step_id, tool_name, tool_input_str, observation in steps:
        lines.append("Step {0}: {1}({2})".format(step_id, tool_name, tool_input_str[:200]))
        lines.append("  → {0}".format(observation[:300]))
    return "\n".join(lines)


def _format_repo_context(input_data: Stage15AgenticInput) -> str:
    facts = input_data.repo_facts
    return (
        "Repo: {repo_id}\n"
        "Languages: {langs}\n"
        "Frameworks: {fw}\n"
        "Entrypoints: {ep}\n"
        "Dependencies: {deps}\n"
        "Summary: {summary}"
    ).format(
        repo_id=input_data.repo.repo_id,
        langs=", ".join(facts.languages),
        fw=", ".join(facts.frameworks),
        ep=", ".join(facts.entrypoints),
        deps=", ".join(facts.dependencies[:10]),
        summary=facts.repo_summary[:300],
    )


# ---------------------------------------------------------------------------
# Core agentic exploration loop
# ---------------------------------------------------------------------------


class _AgenticExplorer:
    """Stateful agent that explores one hypothesis at a time."""

    def __init__(
        self,
        input_data: Stage15AgenticInput,
        artifact_dir: Path,
        adapter: LLMAdapter,
        router: CapabilityRouter,
    ) -> None:
        self.input_data = input_data
        self.artifact_dir = artifact_dir
        self.adapter = adapter
        self.router = router
        self.repo_root = Path(input_data.repo.local_path).expanduser().resolve()
        self.findings_list = input_data.stage1_output.findings

        self.exploration_log: List[ExplorationLogEntry] = []
        self.claim_ledger: List[ClaimRecord] = []
        self.warnings: List[WarningItem] = []

        self.step_counter = 0
        self.claim_counter = 0
        self.tool_calls = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.llm_calls = 0

    def next_step_id(self) -> str:
        self.step_counter += 1
        return "S-{0:03d}".format(self.step_counter)

    def next_claim_id(self) -> str:
        self.claim_counter += 1
        return "C-{0}-{1:03d}".format(
            _repo_token(self.input_data.repo.repo_id), self.claim_counter
        )

    def _track_llm(self, response_obj: Any) -> None:
        """Update token / call counters from an LLMResponse."""
        self.llm_calls += 1
        self.prompt_tokens += response_obj.prompt_tokens
        self.completion_tokens += response_obj.completion_tokens

    def _call_llm(self, prompt: str, task: str) -> str:
        """Call LLM via the router and return the response text."""
        sel_adapter = self.router.for_task(task)
        messages = [LLMMessage(role="user", content=prompt)]
        response = sel_adapter.chat(messages, system=_SYSTEM_PROMPT)
        self._track_llm(response)
        return response.content

    def _execute_tool(
        self,
        tool_name: str,
        tool_input: dict,
    ) -> Tuple[str, List[EvidenceRef]]:
        """Execute a tool and return (observation, produced_evidence_refs)."""
        toolset = self.input_data.toolset

        if tool_name == "list_tree":
            if not toolset.allow_list_tree:
                return "Tool list_tree is disabled.", []
            obs = _tool_list_tree(self.repo_root, tool_input)
            return obs, []

        if tool_name == "search_repo":
            if not toolset.allow_search_repo:
                return "Tool search_repo is disabled.", []
            obs = _tool_search_repo(self.repo_root, tool_input)
            # Parse evidence from grep results
            evidence_refs = _parse_search_evidence(obs, self.repo_root)
            return obs, evidence_refs

        if tool_name == "read_file":
            if not toolset.allow_read_file:
                return "Tool read_file is disabled.", []
            obs, evidence = _tool_read_file(self.repo_root, tool_input)
            return obs, [evidence] if evidence else []

        if tool_name == "read_artifact":
            if not toolset.allow_read_artifact:
                return "Tool read_artifact is disabled.", []
            obs = _tool_read_artifact(self.findings_list, tool_input)
            # Collect evidence refs from the mentioned findings
            related_ids = tool_input.get("related_finding_ids") or []
            evidence_refs = []
            for finding in self.findings_list:
                if not related_ids or finding.finding_id in related_ids:
                    for ref in finding.evidence_refs:
                        if ref.kind == "file_line" and ref.start_line and ref.end_line:
                            evidence_refs.append(ref)
            return obs, evidence_refs[:3]

        if tool_name == "append_finding":
            if not toolset.allow_append_finding:
                return "Tool append_finding is disabled.", []
            # This tool is handled specially — it records a claim
            return self._handle_append_finding(tool_input)

        return "Unknown tool: {0}".format(tool_name), []

    def _handle_append_finding(
        self, tool_input: dict
    ) -> Tuple[str, List[EvidenceRef]]:
        """Record a claim to the ledger and return a summary observation."""
        status = tool_input.get("status", "pending")
        statement = tool_input.get("statement", "")
        confidence = tool_input.get("confidence", "low")
        ev_path = tool_input.get("evidence_path")
        ev_start = tool_input.get("evidence_start_line")
        ev_end = tool_input.get("evidence_end_line")
        ev_snippet = tool_input.get("evidence_snippet")

        evidence_refs: List[EvidenceRef] = []
        if ev_path and ev_start and ev_end:
            evidence_refs.append(
                EvidenceRef(
                    kind="file_line",
                    path=str(ev_path),
                    start_line=int(ev_start),
                    end_line=int(ev_end),
                    snippet=str(ev_snippet)[:500] if ev_snippet else None,
                )
            )

        return (
            "append_finding recorded: status={0}".format(status),
            evidence_refs,
        )

    def explore_hypothesis(
        self,
        hypothesis: Hypothesis,
        round_index: int,
    ) -> Tuple[Optional[ClaimRecord], List[ExplorationLogEntry]]:
        """Run the inner tool loop for one hypothesis.

        Returns (claim_or_None, steps_produced).
        """
        repo_context = _format_repo_context(self.input_data)
        history_steps: List[Tuple[str, str, str, str]] = []
        steps_produced: List[ExplorationLogEntry] = []
        pending_evidence: List[EvidenceRef] = []
        final_claim: Optional[ClaimRecord] = None

        # Max tool calls per hypothesis: budget-aware, but cap at 6 to avoid runaway
        max_calls_this_hyp = min(6, self.input_data.budget.max_tool_calls - self.tool_calls)
        calls_this_hyp = 0

        while calls_this_hyp < max_calls_this_hyp:
            if _budget_exceeded(self.tool_calls, self.prompt_tokens, self.input_data):
                break

            # --- Step 1: Ask LLM which tool to use ---
            history_str = _format_history(history_steps)
            tool_prompt = _TOOL_SELECTION_PROMPT.format(
                hypothesis_id=hypothesis.hypothesis_id,
                statement=hypothesis.statement,
                reason=hypothesis.reason,
                priority=hypothesis.priority,
                search_hints="; ".join(hypothesis.search_hints[:3]),
                repo_context=repo_context,
                history=history_str,
            )

            try:
                llm_response_text = self._call_llm(tool_prompt, TASK_TOOL_SELECTION)
            except Exception as exc:
                logger.warning("LLM tool selection failed for %s: %s", hypothesis.hypothesis_id, exc)
                self.warnings.append(
                    WarningItem(
                        code="W_LLM_ERROR",
                        message="LLM tool selection failed for {0}: {1}".format(
                            hypothesis.hypothesis_id, str(exc)[:200]
                        ),
                    )
                )
                break

            parsed = _parse_json_from_llm(llm_response_text)
            if not parsed:
                logger.warning("Could not parse LLM tool selection response for %s", hypothesis.hypothesis_id)
                break

            tool_name = parsed.get("tool", "append_finding")
            tool_input = parsed.get("tool_input", {})
            # Validate tool_name
            valid_tools = {"list_tree", "search_repo", "read_file", "read_artifact", "append_finding"}
            if tool_name not in valid_tools:
                tool_name = "append_finding"
                tool_input = {
                    "status": "pending",
                    "statement": "Could not determine tool from LLM response.",
                    "confidence": "low",
                }

            # --- Step 2: Execute the tool ---
            step_id = self.next_step_id()
            self.tool_calls += 1
            calls_this_hyp += 1

            observation, produced_evidence = self._execute_tool(tool_name, tool_input)

            # Accumulate evidence
            pending_evidence.extend(produced_evidence)

            # Record the exploration step
            step = ExplorationLogEntry(
                step_id=step_id,
                round_index=round_index,
                tool_name=tool_name,  # type: ignore[arg-type]
                tool_input=tool_input,
                observation=observation[:800],  # truncate for storage
                produced_evidence_refs=produced_evidence,
            )
            steps_produced.append(step)
            self.exploration_log.append(step)

            # Update history for next iteration
            history_steps.append((
                step_id,
                tool_name,
                json.dumps(tool_input, ensure_ascii=False)[:200],
                observation[:300],
            ))

            # --- Step 3: If LLM chose append_finding, create the claim ---
            if tool_name == "append_finding":
                status = tool_input.get("status", "pending")
                statement = tool_input.get("statement", hypothesis.statement)
                confidence = tool_input.get("confidence", "low")

                # Collect all evidence gathered for this hypothesis
                claim_evidence = list(produced_evidence)  # evidence from append_finding
                if not claim_evidence and status == "confirmed":
                    # Fall back to evidence from earlier steps in this hypothesis
                    claim_evidence = pending_evidence[:2]

                # Validated: confirmed claims must have file:line evidence
                if status == "confirmed" and not claim_evidence:
                    status = "pending"
                    self.warnings.append(
                        WarningItem(
                            code="W_NO_EVIDENCE",
                            message="Confirmed claim for {0} lacks file:line evidence; downgraded to pending.".format(
                                hypothesis.hypothesis_id
                            ),
                        )
                    )

                claim = ClaimRecord(
                    claim_id=self.next_claim_id(),
                    statement=statement,
                    status=status,  # type: ignore[arg-type]
                    confidence=confidence,  # type: ignore[arg-type]
                    hypothesis_id=hypothesis.hypothesis_id,
                    supporting_step_ids=[s.step_id for s in steps_produced],
                    evidence_refs=claim_evidence,
                )
                self.claim_ledger.append(claim)
                final_claim = claim
                break  # hypothesis resolved

            # --- Step 4: Ask LLM to evaluate the observation ---
            if _budget_exceeded(self.tool_calls, self.prompt_tokens, self.input_data):
                break

            eval_prompt = _EVALUATION_PROMPT.format(
                hypothesis_id=hypothesis.hypothesis_id,
                statement=hypothesis.statement,
                priority=hypothesis.priority,
                tool_name=tool_name,
                tool_input=json.dumps(tool_input, ensure_ascii=False)[:200],
                observation=observation[:500],
                history=_format_history(history_steps),
            )

            try:
                eval_response_text = self._call_llm(eval_prompt, TASK_HYPOTHESIS_EVALUATION)
                eval_parsed = _parse_json_from_llm(eval_response_text)
            except Exception as exc:
                logger.warning("LLM evaluation failed for %s: %s", hypothesis.hypothesis_id, exc)
                eval_parsed = None

            if eval_parsed:
                should_continue = eval_parsed.get("should_continue", True)
                hyp_status = eval_parsed.get("hypothesis_status", "pending")

                if not should_continue or hyp_status in ("confirmed", "rejected"):
                    # LLM is ready to conclude — force an append_finding call
                    conf = eval_parsed.get("confidence", "medium")
                    reasoning = eval_parsed.get("reasoning", "")
                    claim_statement = _synthesize_claim_statement(
                        hypothesis, hyp_status, reasoning
                    )

                    claim_evidence = pending_evidence[:2]
                    if hyp_status == "confirmed" and not claim_evidence:
                        hyp_status = "pending"
                        self.warnings.append(
                            WarningItem(
                                code="W_NO_EVIDENCE",
                                message="LLM confirmed {0} but no file:line evidence was found.".format(
                                    hypothesis.hypothesis_id
                                ),
                            )
                        )

                    claim = ClaimRecord(
                        claim_id=self.next_claim_id(),
                        statement=claim_statement,
                        status=hyp_status,  # type: ignore[arg-type]
                        confidence=conf,  # type: ignore[arg-type]
                        hypothesis_id=hypothesis.hypothesis_id,
                        supporting_step_ids=[s.step_id for s in steps_produced],
                        evidence_refs=claim_evidence,
                    )
                    self.claim_ledger.append(claim)
                    final_claim = claim
                    break

        return final_claim, steps_produced


# ---------------------------------------------------------------------------
# Evidence parsing helpers
# ---------------------------------------------------------------------------


def _parse_search_evidence(grep_output: str, repo_root: Path) -> List[EvidenceRef]:
    """Extract file:line evidence from grep output lines."""
    refs: List[EvidenceRef] = []
    pattern = re.compile(r"^(.+?):(\d+):\s*(.*)$")
    seen: set = set()
    for line in grep_output.splitlines():
        m = pattern.match(line.strip())
        if not m:
            continue
        rel_path, lineno_str, snippet = m.group(1), m.group(2), m.group(3)
        try:
            lineno = int(lineno_str)
        except ValueError:
            continue
        key = "{0}:{1}".format(rel_path, lineno)
        if key in seen:
            continue
        seen.add(key)
        refs.append(
            EvidenceRef(
                kind="file_line",
                path=rel_path,
                start_line=lineno,
                end_line=lineno,
                snippet=snippet.strip()[:200],
            )
        )
        if len(refs) >= 3:
            break
    return refs


def _synthesize_claim_statement(
    hypothesis: Hypothesis,
    status: str,
    reasoning: str,
) -> str:
    if status == "confirmed":
        return "CONFIRMED: {0} — {1}".format(hypothesis.statement, reasoning)
    if status == "rejected":
        return "REJECTED: {0} — {1}".format(hypothesis.statement, reasoning)
    return "PENDING: {0} — {1}".format(hypothesis.statement, reasoning)


# ---------------------------------------------------------------------------
# claim integrity check (re-exported for test compatibility)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Artifact writers
# ---------------------------------------------------------------------------


def _write_artifacts(
    artifact_dir: Path,
    ordered_hypotheses: List[Hypothesis],
    exploration_log: List[ExplorationLogEntry],
    claim_ledger: List[ClaimRecord],
    promoted_claims: List[ClaimRecord],
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
    evidence_index: Dict[str, dict] = {}
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
        "- Repo: `{repo_id}`\n"
        "- Findings available: {finding_count}\n"
        "- Hypotheses explored: {hypothesis_count}\n"
        "- Promoted (confirmed) claims: {claim_count}\n"
        "- Total claims: {total_claims}\n"
        "- Tool calls: {tool_calls}\n"
        "- Termination: `{termination_reason}`\n"
    ).format(
        repo_id=input_data.repo.repo_id,
        finding_count=len(input_data.stage1_output.findings),
        hypothesis_count=len(ordered_hypotheses),
        claim_count=len(promoted_claims),
        total_claims=len(claim_ledger),
        tool_calls=tool_calls,
        termination_reason=termination_reason,
    )
    (artifact_dir / "context_digest.md").write_text(context_digest, encoding="utf-8")


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run_stage15_agentic(
    input_data: Stage15AgenticInput,
    adapter: Optional[LLMAdapter] = None,
    router: Optional[CapabilityRouter] = None,
) -> ModuleResultEnvelope[Stage15AgenticOutput]:
    """Run Stage 1.5 agentic exploration.

    When adapter is None, falls back to the deterministic mock from the
    base module (packages/extraction/doramagic_extraction/stage15_agentic.py).
    When adapter is provided, runs the real agent loop with LLM calls.
    """

    if adapter is None:
        # Fall back to the minimal deterministic mock (no LLM)
        return _minimal_mock_run(input_data)

    started_at = time.perf_counter()
    ordered_hypotheses = _sorted_hypotheses(input_data.stage1_output.hypotheses)

    base_metrics = RunMetrics(
        wall_time_ms=0,
        llm_calls=0,
        prompt_tokens=0,
        completion_tokens=0,
        estimated_cost_usd=0.0,
        retries=0,
    )

    if not ordered_hypotheses:
        return ModuleResultEnvelope(
            module_name=MODULE_NAME,
            status="blocked",
            error_code=ErrorCodes.NO_HYPOTHESES,
            data=None,
            metrics=base_metrics,
        )

    artifact_dir, relative_paths = _artifact_paths(input_data.repo.local_path)

    # Build router: if router is provided use it; else build one that routes
    # all calls to the provided adapter
    if router is None:
        router = CapabilityRouter(forced_adapter=adapter)

    explorer = _AgenticExplorer(input_data, artifact_dir, adapter, router)

    resolved_hypothesis_ids: set = set()
    unresolved_hypothesis_ids: List[str] = []
    budget_hit = False
    consecutive_no_gain = 0
    round_index = 0
    warnings: List[WarningItem] = []

    for hypothesis in ordered_hypotheses:
        if round_index >= input_data.budget.max_rounds:
            budget_hit = True
            break
        if _budget_exceeded(explorer.tool_calls, explorer.prompt_tokens, input_data):
            budget_hit = True
            break

        round_index += 1
        claim, _steps = explorer.explore_hypothesis(hypothesis, round_index)

        if claim and claim.status in ("confirmed", "rejected"):
            resolved_hypothesis_ids.add(hypothesis.hypothesis_id)
            consecutive_no_gain = 0
        else:
            consecutive_no_gain += 1

        if consecutive_no_gain >= input_data.budget.stop_after_no_gain_rounds:
            break

        if _budget_exceeded(explorer.tool_calls, explorer.prompt_tokens, input_data):
            budget_hit = True
            break

    # Determine unresolved
    for hypothesis in ordered_hypotheses:
        if hypothesis.hypothesis_id not in resolved_hypothesis_ids:
            unresolved_hypothesis_ids.append(hypothesis.hypothesis_id)

    # Determine termination reason
    if budget_hit:
        termination_reason: str = "budget_exhausted"
        envelope_status = "degraded"
        error_code: Optional[str] = ErrorCodes.BUDGET_EXCEEDED
        warnings.append(
            WarningItem(
                code=ErrorCodes.BUDGET_EXCEEDED,
                message="Stage 1.5 stopped after reaching configured budget limits.",
            )
        )
    elif not unresolved_hypothesis_ids:
        termination_reason = "all_hypotheses_resolved"
        envelope_status = "ok"
        error_code = None
    elif consecutive_no_gain >= input_data.budget.stop_after_no_gain_rounds:
        termination_reason = "no_information_gain"
        envelope_status = "ok"
        error_code = None
    else:
        termination_reason = "no_information_gain"
        envelope_status = "ok"
        error_code = None

    promoted_claims = [c for c in explorer.claim_ledger if c.status == "confirmed"]

    # Evidence integrity check
    if promoted_claims and not check_claims_have_evidence(promoted_claims, explorer.exploration_log):
        warnings.append(
            WarningItem(
                code="W_EVIDENCE_INTEGRITY",
                message="Some confirmed claims could not be traced to file:line evidence in exploration log.",
            )
        )
        # Downgrade claims that fail integrity to pending
        fixed_promoted: List[ClaimRecord] = []
        for claim in promoted_claims:
            if check_claims_have_evidence([claim], explorer.exploration_log):
                fixed_promoted.append(claim)
            else:
                warnings.append(
                    WarningItem(
                        code="W_CLAIM_DOWNGRADED",
                        message="Claim {0} downgraded from confirmed to pending (no traceable evidence).".format(
                            claim.claim_id
                        ),
                    )
                )
        promoted_claims = fixed_promoted

    # Merge adapter warnings
    warnings.extend(explorer.warnings)

    # Write all artifacts
    _write_artifacts(
        artifact_dir,
        ordered_hypotheses,
        explorer.exploration_log,
        explorer.claim_ledger,
        promoted_claims,
        input_data,
        explorer.tool_calls,
        termination_reason,
    )

    elapsed_ms = int((time.perf_counter() - started_at) * 1000)
    prompt_tokens = explorer.prompt_tokens
    completion_tokens = explorer.completion_tokens

    # Rough cost estimate (Haiku pricing as floor)
    estimated_cost = round(
        (prompt_tokens / 1_000_000) * 0.25 + (completion_tokens / 1_000_000) * 1.25,
        6,
    )

    metrics = RunMetrics(
        wall_time_ms=max(elapsed_ms, 1),
        llm_calls=explorer.llm_calls,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        estimated_cost_usd=estimated_cost,
        retries=0,
    )

    summary = Stage15Summary(
        resolved_hypotheses=sorted(resolved_hypothesis_ids),
        unresolved_hypotheses=unresolved_hypothesis_ids,
        termination_reason=termination_reason,  # type: ignore[arg-type]
    )

    output = Stage15AgenticOutput(
        repo=input_data.repo,
        hypotheses_path=relative_paths["hypotheses"],
        exploration_log_path=relative_paths["exploration_log"],
        claim_ledger_path=relative_paths["claim_ledger"],
        evidence_index_path=relative_paths["evidence_index"],
        context_digest_path=relative_paths["context_digest"],
        promoted_claims=promoted_claims,
        summary=summary,
    )

    return ModuleResultEnvelope(
        module_name=MODULE_NAME,
        status=envelope_status,  # type: ignore[arg-type]
        error_code=error_code,
        warnings=warnings,
        data=output,
        metrics=metrics,
    )


# ---------------------------------------------------------------------------
# Minimal mock fallback (used when extraction package is not importable)
# ---------------------------------------------------------------------------


def _minimal_mock_run(
    input_data: Stage15AgenticInput,
) -> ModuleResultEnvelope[Stage15AgenticOutput]:
    """Absolute minimal mock — only used when extraction package is unavailable."""
    import time as _time  # noqa: PLC0415

    started_at = _time.perf_counter()
    ordered_hypotheses = _sorted_hypotheses(input_data.stage1_output.hypotheses)

    base_metrics = RunMetrics(
        wall_time_ms=0,
        llm_calls=0,
        prompt_tokens=0,
        completion_tokens=0,
        estimated_cost_usd=0.0,
        retries=0,
    )

    if not ordered_hypotheses:
        return ModuleResultEnvelope(
            module_name=MODULE_NAME,
            status="blocked",
            error_code=ErrorCodes.NO_HYPOTHESES,
            data=None,
            metrics=base_metrics,
        )

    artifact_dir, relative_paths = _artifact_paths(input_data.repo.local_path)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    summary = Stage15Summary(
        resolved_hypotheses=[],
        unresolved_hypotheses=[h.hypothesis_id for h in ordered_hypotheses],
        termination_reason="no_information_gain",
    )

    _write_artifacts(
        artifact_dir,
        ordered_hypotheses,
        [],
        [],
        [],
        input_data,
        0,
        "no_information_gain",
    )

    elapsed_ms = int((_time.perf_counter() - started_at) * 1000)
    output = Stage15AgenticOutput(
        repo=input_data.repo,
        hypotheses_path=relative_paths["hypotheses"],
        exploration_log_path=relative_paths["exploration_log"],
        claim_ledger_path=relative_paths["claim_ledger"],
        evidence_index_path=relative_paths["evidence_index"],
        context_digest_path=relative_paths["context_digest"],
        promoted_claims=[],
        summary=summary,
    )

    return ModuleResultEnvelope(
        module_name=MODULE_NAME,
        status="ok",
        error_code=None,
        data=output,
        metrics=RunMetrics(
            wall_time_ms=max(elapsed_ms, 1),
            llm_calls=0,
            prompt_tokens=0,
            completion_tokens=0,
            estimated_cost_usd=0.0,
            retries=0,
        ),
    )
