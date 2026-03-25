"""Phase E executor: Cross-project knowledge synthesis with fallback.

If run_synthesis() returns empty results (no signals), falls back to
best-single-soul synthesis (replicating singleshot's fallback logic).
"""

from __future__ import annotations

import os
import time

from pydantic import BaseModel

from doramagic_contracts.cross_project import (
    SynthesisDecision,
    SynthesisInput,
    SynthesisReportData,
)
from doramagic_contracts.envelope import ModuleResultEnvelope, RunMetrics, WarningItem
from doramagic_contracts.executor import ExecutorConfig


class SynthesisRunner:
    """Wraps cross_project.synthesis.run_synthesis() with fallback.

    If formal synthesis produces empty results (no CompareSignals),
    falls back to best-single-soul extraction — picks the soul with
    the most findings and promotes its knowledge as consensus.
    """

    async def execute(
        self, input: BaseModel, adapter: object, config: ExecutorConfig,
    ) -> ModuleResultEnvelope:
        start = time.monotonic()

        if not isinstance(input, SynthesisInput):
            return ModuleResultEnvelope(
                module_name="SynthesisRunner",
                status="error", error_code="E_INPUT_INVALID",
                warnings=[WarningItem(code="TYPE", message="Expected SynthesisInput")],
                metrics=self._metrics(start),
            )

        os.environ["DORAMAGIC_SYNTHESIS_OUTPUT_DIR"] = str(config.run_dir / "staging")

        # Try formal synthesis
        from doramagic_cross_project.synthesis import run_synthesis
        result = run_synthesis(input)

        # Check if result has meaningful content
        has_content = False
        if result.data:
            has_content = bool(
                result.data.consensus
                or result.data.unique_knowledge
                or result.data.selected_knowledge
            )

        if has_content:
            return result

        # Fallback: best-single-soul synthesis
        warnings = list(result.warnings) if result.warnings else []
        warnings.append(WarningItem(
            code="W_FALLBACK_SYNTHESIS",
            message="Formal synthesis empty, using best-soul fallback",
        ))

        fallback_data = self._fallback_synthesis(input)

        return ModuleResultEnvelope(
            module_name="SynthesisRunner",
            status="degraded",
            warnings=warnings,
            data=fallback_data,
            metrics=self._metrics(start),
        )

    def _fallback_synthesis(self, input: SynthesisInput) -> SynthesisReportData:
        """Best-single-soul fallback: promote the richest soul's knowledge.

        Replicates singleshot lines 613-635: if LLM synthesis fails,
        use the soul with the most why_decisions as the entire synthesis.
        """
        # Find the richest project summary
        best_summary = None
        best_score = 0
        for ps in input.project_summaries:
            score = len(ps.top_capabilities) + len(ps.top_failures)
            if score > best_score:
                best_score = score
                best_summary = ps

        consensus = []
        if best_summary:
            # Promote capabilities as consensus decisions
            for i, cap in enumerate(best_summary.top_capabilities[:5]):
                consensus.append(SynthesisDecision(
                    decision_id=f"fallback-{i:03d}",
                    statement=cap if isinstance(cap, str) else str(cap),
                    decision="adopt",
                    rationale=f"From best available source: {best_summary.project_id}",
                    source_refs=[],
                    demand_fit="high",
                ))

            # Promote failures as additional knowledge
            for i, fail in enumerate(best_summary.top_failures[:3]):
                consensus.append(SynthesisDecision(
                    decision_id=f"fallback-trap-{i:03d}",
                    statement=f"[TRAP] {fail}" if isinstance(fail, str) else str(fail),
                    decision="warn",
                    rationale=f"Community-reported issue from {best_summary.project_id}",
                    source_refs=[],
                    demand_fit="high",
                ))

        return SynthesisReportData(
            consensus=consensus,
            conflicts=[],
            unique_knowledge=[],
            selected_knowledge=consensus,  # All fallback knowledge is selected
            excluded_knowledge=[],
            open_questions=["Formal cross-project synthesis was empty; this is a single-source fallback."],
        )

    def _metrics(self, start: float) -> RunMetrics:
        return RunMetrics(
            wall_time_ms=int((time.monotonic() - start) * 1000),
            llm_calls=0, prompt_tokens=0, completion_tokens=0,
            estimated_cost_usd=0.0,
        )

    def validate_input(self, input: BaseModel) -> list[str]:
        if not isinstance(input, SynthesisInput):
            return [f"Expected SynthesisInput, got {type(input).__name__}"]
        return []

    def can_degrade(self) -> bool:
        return True  # Fallback synthesis is a degraded response
