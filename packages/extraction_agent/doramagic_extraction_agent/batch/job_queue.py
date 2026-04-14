"""Job queue — defines extraction jobs and parses YAML job files."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class RepoJob:
    """A single repo extraction job."""

    blueprint_id: str
    repo_url: str = ""
    repo_path: str = ""  # local path (alternative to url)
    domain: str = "finance"
    priority: int = 1
    skip_blueprint: bool = False  # skip blueprint extraction (already exists)
    skip_constraint: bool = True  # default: only extract blueprint; constraint has its own pipeline


@dataclass
class BatchConfig:
    """Batch execution configuration."""

    batch_id: str
    domain: str = "finance"
    concurrency: int = 3
    repos: list[RepoJob] = field(default_factory=list)
    llm_model: str = "MiniMax-M2.7"
    llm_base_url: str = ""
    llm_api_key_env: str = "LLM_API_KEY"
    max_tokens_per_repo: int = 2_000_000
    resume: bool = False  # Fix 2: when False, always start fresh (ignore existing checkpoint)
    api_format: str = "anthropic"  # "anthropic" or "openai"
    # Multi-model support (v3 Batch B)
    fallback_models: list[dict] = field(default_factory=list)
    model_overrides: dict[str, dict] = field(default_factory=dict)
    # v5: blueprint phase version ("v4" or "v5")
    blueprint_version: str = "v4"
    # v2: constraint phase version ("v1" or "v2")
    constraint_version: str = "v1"


def load_batch_config(path: Path) -> BatchConfig:
    """Load batch config from a YAML file.

    Expected YAML structure::

        batch_id: finance-batch-01
        domain: finance
        concurrency: 3
        llm_model: MiniMax-M2.7
        llm_base_url: https://api.minimaxi.chat/v1
        llm_api_key_env: MINIMAX_API_KEY
        max_tokens_per_repo: 2000000
        repos:
          - blueprint_id: finance-bp-060
            repo_url: https://github.com/example/repo
            domain: finance
            priority: 1
            skip_blueprint: false
            skip_constraint: false
          - blueprint_id: finance-bp-061
            repo_path: /absolute/or/relative/path
            priority: 2

    Args:
        path: Path to the YAML job file.

    Returns:
        A fully populated :class:`BatchConfig`.

    Raises:
        FileNotFoundError: If *path* does not exist.
        ValueError: If required fields are missing or malformed.
    """
    if not path.exists():
        raise FileNotFoundError(f"Job file not found: {path}")

    raw = path.read_text(encoding="utf-8")
    data: dict = yaml.safe_load(raw) or {}

    if not data.get("batch_id"):
        raise ValueError(f"Job file {path} is missing required field 'batch_id'")

    repos_raw: list[dict] = data.pop("repos", [])
    if not isinstance(repos_raw, list):
        raise ValueError(f"'repos' in {path} must be a list, got {type(repos_raw)}")

    repos: list[RepoJob] = []
    for i, repo_dict in enumerate(repos_raw):
        if not isinstance(repo_dict, dict):
            raise ValueError(f"repos[{i}] in {path} must be a mapping, got {type(repo_dict)}")
        bp_id = repo_dict.get("blueprint_id", "")
        if not bp_id:
            raise ValueError(f"repos[{i}] in {path} is missing required field 'blueprint_id'")
        repos.append(
            RepoJob(
                blueprint_id=bp_id,
                repo_url=repo_dict.get("repo_url", ""),
                repo_path=repo_dict.get("repo_path", ""),
                domain=repo_dict.get("domain", data.get("domain", "finance")),
                priority=int(repo_dict.get("priority", 1)),
                skip_blueprint=bool(repo_dict.get("skip_blueprint", False)),
                skip_constraint=bool(repo_dict.get("skip_constraint", False)),
            )
        )

    # Validate concurrency before constructing config
    concurrency_raw = data.get("concurrency", 3)
    if isinstance(concurrency_raw, int) and concurrency_raw < 1:
        raise ValueError(f"concurrency must be >= 1, got {concurrency_raw}")

    # Map remaining top-level keys to BatchConfig fields, ignoring unknowns.
    known_fields = {
        "batch_id",
        "domain",
        "concurrency",
        "llm_model",
        "llm_base_url",
        "llm_api_key_env",
        "max_tokens_per_repo",
        "api_format",
        "fallback_models",
        "model_overrides",
        "blueprint_version",
        "constraint_version",
    }
    config_kwargs = {k: v for k, v in data.items() if k in known_fields}

    return BatchConfig(repos=repos, **config_kwargs)
