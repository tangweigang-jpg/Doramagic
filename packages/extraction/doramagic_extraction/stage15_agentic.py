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

import logging
import time

# ---------------------------------------------------------------------------
# sys.path setup (mirrors the pattern used in stage15_agentic.py base)
# ---------------------------------------------------------------------------
from doramagic_contracts.envelope import (
    ErrorCodes,
    ModuleResultEnvelope,
    RunMetrics,
    WarningItem,
)
from doramagic_contracts.extraction import (
    ClaimRecord,
    Hypothesis,
    Stage15AgenticInput,
    Stage15AgenticOutput,
    Stage15Summary,
)
from doramagic_shared_utils.capability_router import CapabilityRouter
from doramagic_shared_utils.llm_adapter import LLMAdapter

from .stage15_artifacts import (
    _artifact_paths,
    _budget_exceeded,
    _write_artifacts,
    check_claims_have_evidence,
)
from .stage15_config import PRIORITY_ORDER
from .stage15_explorer import _AgenticExplorer

MODULE_NAME = "extraction.stage15_agentic"
logger = logging.getLogger(__name__)


def _sorted_hypotheses(hypotheses: list[Hypothesis]) -> list[Hypothesis]:
    return sorted(
        hypotheses,
        key=lambda item: (PRIORITY_ORDER.get(item.priority, 99), item.hypothesis_id),
    )


def _run_stage15_agentic_core(
    input_data: Stage15AgenticInput,
    adapter: LLMAdapter | None = None,
    router: CapabilityRouter | None = None,
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
    unresolved_hypothesis_ids: list[str] = []
    budget_hit = False
    consecutive_no_gain = 0
    round_index = 0
    warnings: list[WarningItem] = []

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
        error_code: str | None = ErrorCodes.BUDGET_EXCEEDED
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
    if promoted_claims and not check_claims_have_evidence(
        promoted_claims, explorer.exploration_log
    ):
        warnings.append(
            WarningItem(
                code="W_EVIDENCE_INTEGRITY",
                message="Some confirmed claims could not be traced to file:line evidence in exploration log.",
            )
        )
        # Downgrade claims that fail integrity to pending
        fixed_promoted: list[ClaimRecord] = []
        for claim in promoted_claims:
            if check_claims_have_evidence([claim], explorer.exploration_log):
                fixed_promoted.append(claim)
            else:
                warnings.append(
                    WarningItem(
                        code="W_CLAIM_DOWNGRADED",
                        message=f"Claim {claim.claim_id} downgraded from confirmed to pending (no traceable evidence).",
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
    import time as _time

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


# ---------------------------------------------------------------------------
# Provider strategies
# ---------------------------------------------------------------------------


def _normalize_provider_name(provider: str | None) -> str:
    if not provider:
        return "unknown"
    normalized = provider.strip().lower()
    if normalized == "gemini":
        return "google"
    return normalized


class _Stage15AgenticStrategy:
    name = "default"
    providers = frozenset({"anthropic", "openai", "mock", "unknown"})

    def run(
        self,
        input_data: Stage15AgenticInput,
        *,
        adapter: LLMAdapter | None = None,
        router: CapabilityRouter | None = None,
    ) -> ModuleResultEnvelope[Stage15AgenticOutput]:
        return _run_stage15_agentic_core(input_data, adapter=adapter, router=router)


class _GeminiStage15AgenticStrategy(_Stage15AgenticStrategy):
    name = "gemini"
    providers = frozenset({"google"})


_DEFAULT_STAGE15_STRATEGY = _Stage15AgenticStrategy()
_GEMINI_STAGE15_STRATEGY = _GeminiStage15AgenticStrategy()
_STAGE15_STRATEGIES = (_GEMINI_STAGE15_STRATEGY, _DEFAULT_STAGE15_STRATEGY)


def resolve_stage15_agentic_strategy(
    adapter: LLMAdapter | None,
) -> _Stage15AgenticStrategy:
    """Pick the provider strategy from LLMAdapter.provider."""
    provider = _normalize_provider_name(
        getattr(adapter, "provider", None) or getattr(adapter, "_provider_override", None)
    )
    for strategy in _STAGE15_STRATEGIES:
        if provider in strategy.providers:
            return strategy
    return _DEFAULT_STAGE15_STRATEGY


def run_stage15_agentic(
    input_data: Stage15AgenticInput,
    adapter: LLMAdapter | None = None,
    router: CapabilityRouter | None = None,
) -> ModuleResultEnvelope[Stage15AgenticOutput]:
    """Run Stage 1.5 agentic exploration with provider-based strategy routing."""
    strategy = resolve_stage15_agentic_strategy(adapter)
    logger.info(
        "Stage 1.5 strategy selected: %s (provider=%s)",
        strategy.name,
        _normalize_provider_name(getattr(adapter, "provider", None)),
    )
    return strategy.run(input_data, adapter=adapter, router=router)
