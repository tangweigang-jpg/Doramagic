"""Stage 1.5 agentic explorer."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from doramagic_contracts.base import EvidenceRef
from doramagic_contracts.envelope import WarningItem
from doramagic_contracts.extraction import (
    ClaimRecord,
    ExplorationLogEntry,
    Hypothesis,
    Stage15AgenticInput,
)
from doramagic_shared_utils.capability_router import (
    TASK_HYPOTHESIS_EVALUATION,
    TASK_TOOL_SELECTION,
    CapabilityRouter,
)
from doramagic_shared_utils.llm_adapter import LLMAdapter, LLMMessage

from .stage15_artifacts import (
    _budget_exceeded,
    _parse_json_from_llm,
    _repo_token,
    _synthesize_claim_statement,
)
from .stage15_config import _EVALUATION_PROMPT, _SYSTEM_PROMPT, _TOOL_SELECTION_PROMPT
from .stage15_tools import (
    _format_history,
    _format_repo_context,
    _parse_search_evidence,
    _tool_list_tree,
    _tool_read_artifact,
    _tool_read_file,
    _tool_search_repo,
)

logger = logging.getLogger(__name__)


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

        self.exploration_log: list[ExplorationLogEntry] = []
        self.claim_ledger: list[ClaimRecord] = []
        self.warnings: list[WarningItem] = []

        self.step_counter = 0
        self.claim_counter = 0
        self.tool_calls = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.llm_calls = 0

    def next_step_id(self) -> str:
        self.step_counter += 1
        return f"S-{self.step_counter:03d}"

    def next_claim_id(self) -> str:
        self.claim_counter += 1
        return f"C-{_repo_token(self.input_data.repo.repo_id)}-{self.claim_counter:03d}"

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
    ) -> tuple[str, list[EvidenceRef]]:
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

        return f"Unknown tool: {tool_name}", []

    def _handle_append_finding(self, tool_input: dict) -> tuple[str, list[EvidenceRef]]:
        """Record a claim to the ledger and return a summary observation."""
        status = tool_input.get("status", "pending")
        statement = tool_input.get("statement", "")
        confidence = tool_input.get("confidence", "low")
        ev_path = tool_input.get("evidence_path")
        ev_start = tool_input.get("evidence_start_line")
        ev_end = tool_input.get("evidence_end_line")
        ev_snippet = tool_input.get("evidence_snippet")

        evidence_refs: list[EvidenceRef] = []
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
            f"append_finding recorded: status={status}",
            evidence_refs,
        )

    def explore_hypothesis(
        self,
        hypothesis: Hypothesis,
        round_index: int,
    ) -> tuple[ClaimRecord | None, list[ExplorationLogEntry]]:
        """Run the inner tool loop for one hypothesis.

        Returns (claim_or_None, steps_produced).
        """
        repo_context = _format_repo_context(self.input_data)
        history_steps: list[tuple[str, str, str, str]] = []
        steps_produced: list[ExplorationLogEntry] = []
        pending_evidence: list[EvidenceRef] = []
        final_claim: ClaimRecord | None = None

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
                logger.warning(
                    "LLM tool selection failed for %s: %s", hypothesis.hypothesis_id, exc
                )
                self.warnings.append(
                    WarningItem(
                        code="W_LLM_ERROR",
                        message=f"LLM tool selection failed for {hypothesis.hypothesis_id}: {str(exc)[:200]}",
                    )
                )
                break

            parsed = _parse_json_from_llm(llm_response_text)
            if not parsed:
                logger.warning(
                    "Could not parse LLM tool selection response for %s", hypothesis.hypothesis_id
                )
                break

            tool_name = parsed.get("tool", "append_finding")
            tool_input = parsed.get("tool_input", {})
            # Validate tool_name
            valid_tools = {
                "list_tree",
                "search_repo",
                "read_file",
                "read_artifact",
                "append_finding",
            }
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
            history_steps.append(
                (
                    step_id,
                    tool_name,
                    json.dumps(tool_input, ensure_ascii=False)[:200],
                    observation[:300],
                )
            )

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
                            message=f"Confirmed claim for {hypothesis.hypothesis_id} lacks file:line evidence; downgraded to pending.",
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
                    claim_statement = _synthesize_claim_statement(hypothesis, hyp_status, reasoning)

                    claim_evidence = pending_evidence[:2]
                    if hyp_status == "confirmed" and not claim_evidence:
                        hyp_status = "pending"
                        self.warnings.append(
                            WarningItem(
                                code="W_NO_EVIDENCE",
                                message=f"LLM confirmed {hypothesis.hypothesis_id} but no file:line evidence was found.",
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
