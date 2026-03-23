"""Doramagic racekit public API."""

from __future__ import annotations

from .race_brief import generate_brief
from .race_config import (
    ROUND_RACE_CONFIGS,
    RacerName,
    RaceTrack,
    RoundRaceConfig,
    canonical_module_name,
    get_round_config,
    module_branch_slug,
)
from .race_review import REVIEW_DIMENSIONS, generate_review_template, score_submission
from .race_workspace import (
    ActiveRace,
    cleanup_race_worktree,
    create_race_worktree,
    list_active_races,
)

__all__ = [
    "ActiveRace",
    "RacerName",
    "RaceTrack",
    "REVIEW_DIMENSIONS",
    "ROUND_RACE_CONFIGS",
    "RoundRaceConfig",
    "canonical_module_name",
    "cleanup_race_worktree",
    "create_race_worktree",
    "generate_brief",
    "generate_review_template",
    "get_round_config",
    "list_active_races",
    "module_branch_slug",
    "score_submission",
]
