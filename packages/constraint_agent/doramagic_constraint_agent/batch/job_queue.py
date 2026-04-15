"""Constraint extraction job definitions."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ConstraintJob:
    """A single constraint extraction job.

    Input contract: blueprint YAML path + repo path -> constraint JSONL output.
    """

    blueprint_id: str
    blueprint_path: str  # path to blueprint YAML
    repo_path: str  # path to local repo clone
    domain: str = "finance"
    priority: int = 1


@dataclass
class ConstraintBatchConfig:
    """Configuration for a batch constraint extraction run."""

    batch_id: str = "constraint-batch"
    domain: str = "finance"
    concurrency: int = 3
    jobs: list[ConstraintJob] = field(default_factory=list)

    # LLM settings
    llm_model: str = "MiniMax-M2.7"
    llm_base_url: str = ""
    llm_api_key_env: str = "LLM_API_KEY"
    api_format: str = "anthropic"

    # Constraint pipeline version (v2 or v3)
    constraint_version: str = "v3"

    # Model failover
    fallback_models: list[dict] = field(default_factory=list)
    model_overrides: dict[str, dict] = field(default_factory=dict)

    # Resume from checkpoint
    resume: bool = False
