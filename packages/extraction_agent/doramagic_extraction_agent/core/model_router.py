"""Model routing and failover for multi-model extraction.

Maps phases to model endpoints with automatic failover. When the primary
model fails a phase (API error, timeout, circuit break), the router
provides a fallback model specification so the executor can retry with
a different provider.

Design references:
- Harness Engineering §1: failure classification (transient vs persistent)
- Claude Code Ch.04: supervision tree (restart/failover/skip strategies)
- Multi-model strategy research: Phase-Model matching matrix
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ModelSpec:
    """Specification for a single LLM endpoint.

    Carries everything needed to construct an ``ExtractionAgent``:
    model ID, API format, connection details, and model-specific
    parameter overrides.
    """

    model_id: str
    api_format: str = "anthropic"  # "anthropic" or "openai"
    base_url: str = ""
    api_key: str = ""
    api_key_env: str = ""  # env var name; resolved at runtime
    timeout: int = 600
    max_tokens_per_call: int = 16384
    is_reasoning: bool = False  # reasoning models get 2x token budget

    def resolve_api_key(self) -> str:
        """Return the API key, resolving from env var if needed."""
        if self.api_key:
            return self.api_key
        if self.api_key_env:
            return os.environ.get(self.api_key_env, "")
        return ""


@dataclass
class ModelRouter:
    """Maps phases to ordered model lists with failover support.

    Each phase can have a custom model chain ``[primary, fallback1, ...]``.
    Phases not explicitly mapped use ``default_models``.

    Usage::

        router = ModelRouter(
            default_models=[minimax_spec, glm5_spec],
            phase_models={
                "bp_bd_r3_adversarial": [glm5_spec, minimax_spec],
            },
        )
        primary = router.get_primary("bp_bd_r3_adversarial")  # glm5
        fallback = router.get_fallback("bp_bd_r3_adversarial")  # minimax
    """

    default_models: list[ModelSpec] = field(default_factory=list)
    phase_models: dict[str, list[ModelSpec]] = field(default_factory=dict)

    def get_primary(self, phase_name: str) -> ModelSpec:
        """Return the primary (first-choice) model for a phase."""
        specs = self.phase_models.get(phase_name, self.default_models)
        if not specs:
            raise ValueError(
                f"No models configured for phase {phase_name!r} "
                f"and no default models set"
            )
        return specs[0]

    def get_fallback(self, phase_name: str) -> ModelSpec | None:
        """Return the fallback model, or None if no fallback available."""
        specs = self.phase_models.get(phase_name, self.default_models)
        return specs[1] if len(specs) > 1 else None

    def get_all(self, phase_name: str) -> list[ModelSpec]:
        """Return all models for a phase in priority order."""
        return list(self.phase_models.get(phase_name, self.default_models))


def build_model_router(
    primary_spec: ModelSpec,
    fallback_spec: ModelSpec | None = None,
    phase_overrides: dict[str, list[ModelSpec]] | None = None,
) -> ModelRouter:
    """Convenience factory for common configurations.

    Args:
        primary_spec: Default model for all phases.
        fallback_spec: Fallback model (used when primary fails).
        phase_overrides: Per-phase model chains that override defaults.
    """
    default_models = [primary_spec]
    if fallback_spec:
        default_models.append(fallback_spec)

    return ModelRouter(
        default_models=default_models,
        phase_models=phase_overrides or {},
    )
