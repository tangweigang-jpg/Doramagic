"""Pipeline driver — executes the 4 phases in fixed order.

Order is hardcoded: content → constraints → faq → evaluator.
The evaluator phase reads outputs from the first three phases via PhaseContext.results.

Usage:
    pipeline = Pipeline(adapter=adapter, model_id="claude-sonnet-4-6")
    ctx = pipeline.run(ctx)  # ctx.results populated after run
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from doramagic_web_publisher.errors import (
    PhaseError,
    ToolUseMaxIterationsError,
    ToolUseStoppedWithoutSubmitError,
    WebPublisherError,
)
from doramagic_web_publisher.runtime.models import PhaseContext

if TYPE_CHECKING:
    from doramagic_shared_utils.llm_adapter import LLMAdapter

    from doramagic_web_publisher.phases.base import Phase

logger = logging.getLogger(__name__)

# Mapping from API gate → phase_name (for fatal error routing back to a phase).
# When the Publish API returns fatal errors, the pipeline can re-run the
# responsible phase and retry. This mapping drives that routing.
GATE_TO_PHASE: dict[str, str] = {
    # SEO gates
    "SEO-SLUG": "content",
    "SEO-TITLE-LENGTH": "evaluator",
    "SEO-TITLE-KEYWORD": "evaluator",
    "SEO-DESC-LENGTH": "evaluator",
    "SEO-DESC-DENSITY": "evaluator",
    # GEO gates
    "GEO-DEF-FORMAT": "content",
    "GEO-DATA-DENSITY": "content",
    "GEO-DESC-CTA": "content",
    "GEO-FAQ-COUNT": "faq",
    "GEO-FAQ-LENGTH": "faq",
    "GEO-FAQ-CTA": "faq",
    "GEO-FAQ-VARIETY": "faq",
    "GEO-KEYWORDS": "evaluator",
    # USER gates
    "USER-PROOF-MIN": "evaluator",
    "USER-INPUTS-MATCH": "evaluator",
    "USER-SCENARIO-PAIR": "content",
    "USER-HOST-MIN": "evaluator",
    "USER-SAMPLE-OUTPUT": "evaluator",
    # TRUST gates
    "TRUST-FATAL": "constraints",
    "TRUST-SUMMARY": "constraints",
    "TRUST-EVIDENCE": "constraints",
    # SAFE gates
    "SAFE-SEED": "content",
    "SAFE-BACKFLOW": "content",
    "SAFE-EVIDENCE-HOST": "constraints",
    "SAFE-PROOF-HOST": "evaluator",
    # I18N / DATA / XP / TIER gates
    "I18N-COMPLETE": "evaluator",
    "DATA-VERSION": "content",
    "XP-ATTRIBUTION": "constraints",
    "TIER-VALID": "evaluator",
    "FLAGSHIP-PARENT": "evaluator",
    "PRESET-VAR-BIND": "evaluator",
}


class Pipeline:
    """Drives the 4 web-publishing phases in fixed order.

    Phases are loaded from doramagic_web_publisher.phases.PHASES at runtime.
    Each phase receives the full PhaseContext and writes its PhaseResult into
    ctx.results[phase.name].

    Error handling:
      - PhaseError is re-raised immediately (hard stop).
      - PublishError with fatal gates triggers selective phase re-run (once).
      - Other exceptions are wrapped as PhaseError.
    """

    def __init__(
        self,
        adapter: LLMAdapter,
        model_id: str,
        *,
        max_retry_on_api_error: int = 1,
    ) -> None:
        self._adapter = adapter
        self._model_id = model_id
        self._max_retry = max_retry_on_api_error

    def run(self, ctx: PhaseContext) -> PhaseContext:
        """Execute all phases sequentially, returning the enriched context.

        In mock_mode, each phase.run() returns its stub PhaseResult without
        calling the LLM.
        """
        from doramagic_web_publisher.phases import PHASES

        phases = PHASES  # List[Phase] in order

        for phase in phases:
            ctx = self._run_phase(phase, ctx)

        return ctx

    def run_single_phase(self, phase_name: str, ctx: PhaseContext) -> PhaseContext:
        """Run a single named phase (for debugging/retry).

        Raises:
            ValueError: If phase_name is not in the registered PHASES.
        """
        from doramagic_web_publisher.phases import PHASES

        phase = next((p for p in PHASES if p.name == phase_name), None)
        if phase is None:
            available = [p.name for p in PHASES]
            raise ValueError(f"Unknown phase '{phase_name}'. Available: {available}")
        return self._run_phase(phase, ctx)

    def route_errors_to_phases(self, errors: list[dict]) -> dict[str, list[dict]]:
        """Map API error objects to the responsible phase names.

        Args:
            errors: List of error dicts from the Publish API response,
                    each with a 'gate' key.

        Returns:
            Dict mapping phase_name → list of error dicts for that phase.
        """
        routing: dict[str, list[dict]] = {}
        for err in errors:
            gate = err.get("gate", "")
            phase_name = GATE_TO_PHASE.get(gate, "evaluator")  # default to evaluator
            routing.setdefault(phase_name, []).append(err)
        return routing

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _run_phase(self, phase: Phase, ctx: PhaseContext) -> PhaseContext:
        """Run a single phase, writing result into ctx.results."""
        logger.info("Pipeline: starting phase '%s'", phase.name)

        try:
            result = phase.mock_result() if ctx.mock_mode else phase.run(ctx, self._adapter)
        except PhaseError:
            raise
        except ToolUseStoppedWithoutSubmitError as exc:
            # LLM stopped without submitting — prompt/model adjustment needed, not just more iters.
            logger.error(
                "Pipeline: phase '%s' — LLM stopped without submit (finish_reason=%r, iter=%d). "
                "Consider adjusting the phase prompt or switching models.",
                phase.name,
                exc.finish_reason,
                exc.iterations,
            )
            raise PhaseError(
                phase.name,
                f"LLM stopped without calling submit tool (finish_reason={exc.finish_reason!r}). "
                "Prompt adjustment may be needed.",
            ) from exc
        except ToolUseMaxIterationsError as exc:
            # Iteration budget exhausted — may succeed with more iterations.
            logger.warning(
                "Pipeline: phase '%s' — max iterations (%d) reached without submit. "
                "Consider increasing --max-iter.",
                phase.name,
                exc.iterations,
            )
            raise PhaseError(
                phase.name,
                f"Max iterations ({exc.iterations}) reached without submit. "
                "Try increasing max_iter.",
            ) from exc
        except WebPublisherError as exc:
            raise PhaseError(phase.name, str(exc)) from exc
        except Exception as exc:
            raise PhaseError(phase.name, f"Unexpected error: {exc}") from exc

        ctx.results[phase.name] = result
        logger.info(
            "Pipeline: phase '%s' done (success=%s, tokens=%s)",
            phase.name,
            result.success,
            result.token_usage,
        )
        return ctx
