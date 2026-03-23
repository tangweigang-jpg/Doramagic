"""Doramagic 赛马轮次配置。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Tuple, Union


def normalize_identifier(value: str) -> str:
    """Normalize a free-form identifier for fuzzy matching."""

    return re.sub(r"[^a-z0-9]+", "", value.strip().lower())


class RacerName(str, Enum):
    """Canonical racer identifiers used across racekit."""

    S1_SONNET = "s1-sonnet"
    S2_CODEX = "s2-codex"
    S3_GEMINI = "s3-gemini"
    S4_GLM5 = "s4-glm5"

    @property
    def display_name(self) -> str:
        return {
            RacerName.S1_SONNET: "Sonnet",
            RacerName.S2_CODEX: "Codex",
            RacerName.S3_GEMINI: "Gemini",
            RacerName.S4_GLM5: "GLM5",
        }[self]

    @classmethod
    def coerce(cls, value: Union["RacerName", str]) -> "RacerName":
        if isinstance(value, cls):
            return value

        normalized = normalize_identifier(str(value))
        for racer in cls:
            candidates = {
                normalize_identifier(racer.name),
                normalize_identifier(racer.value),
                normalize_identifier(racer.display_name),
            }
            if normalized in candidates:
                return racer

        raise ValueError("Unknown racer name: {0}".format(value))


@dataclass(frozen=True)
class RaceTrack:
    track_name: str
    module_name: str
    racers: Tuple[RacerName, RacerName]


@dataclass(frozen=True)
class RoundRaceConfig:
    round_num: int
    tracks: Tuple[RaceTrack, RaceTrack]


CANONICAL_MODULE_ALIASES = {
    "cross_project.discovery": "cross-project.discovery",
    "cross_project.compare": "cross-project.compare",
    "cross_project.synthesis": "cross-project.synthesis",
    "skill_compiler.openclaw": "skill-compiler.openclaw",
    "platform_openclaw.validator": "platform-openclaw.validator",
    "domain_graph.snapshot_builder": "domain-graph.snapshot_builder",
    "apps.preextract_api.read": "apps.preextract-api.read",
    "preextract_api.read": "apps.preextract-api.read",
}


MODULE_BRANCH_SLUGS = {
    "extraction.stage1_scan": "stage1_scan",
    "extraction.stage15_agentic": "stage15_agentic",
    "cross-project.discovery": "discovery",
    "cross-project.compare": "compare",
    "cross-project.synthesis": "synthesis",
    "skill-compiler.openclaw": "skill_compiler",
    "platform-openclaw.validator": "validator",
    "orchestration.phase_runner": "phase_runner",
    "domain-graph.snapshot_builder": "snapshot_builder",
    "api.read": "api_read",
    "apps.preextract-api.read": "api_read",
}


ROUND_RACE_CONFIGS: Dict[int, RoundRaceConfig] = {
    1: RoundRaceConfig(
        round_num=1,
        tracks=(
            RaceTrack(
                track_name="A",
                module_name="extraction.stage1_scan",
                racers=(RacerName.S1_SONNET, RacerName.S4_GLM5),
            ),
            RaceTrack(
                track_name="B",
                module_name="extraction.stage15_agentic",
                racers=(RacerName.S2_CODEX, RacerName.S3_GEMINI),
            ),
        ),
    ),
    2: RoundRaceConfig(
        round_num=2,
        tracks=(
            RaceTrack(
                track_name="A",
                module_name="cross-project.discovery",
                racers=(RacerName.S1_SONNET, RacerName.S3_GEMINI),
            ),
            RaceTrack(
                track_name="B",
                module_name="cross-project.compare",
                racers=(RacerName.S2_CODEX, RacerName.S4_GLM5),
            ),
        ),
    ),
    3: RoundRaceConfig(
        round_num=3,
        tracks=(
            RaceTrack(
                track_name="A",
                module_name="cross-project.synthesis",
                racers=(RacerName.S1_SONNET, RacerName.S3_GEMINI),
            ),
            RaceTrack(
                track_name="B",
                module_name="skill-compiler.openclaw",
                racers=(RacerName.S2_CODEX, RacerName.S4_GLM5),
            ),
        ),
    ),
    4: RoundRaceConfig(
        round_num=4,
        tracks=(
            RaceTrack(
                track_name="A",
                module_name="platform-openclaw.validator",
                racers=(RacerName.S1_SONNET, RacerName.S4_GLM5),
            ),
            RaceTrack(
                track_name="B",
                module_name="orchestration.phase_runner",
                racers=(RacerName.S2_CODEX, RacerName.S3_GEMINI),
            ),
        ),
    ),
    5: RoundRaceConfig(
        round_num=5,
        tracks=(
            RaceTrack(
                track_name="A",
                module_name="domain-graph.snapshot_builder",
                racers=(RacerName.S2_CODEX, RacerName.S4_GLM5),
            ),
            RaceTrack(
                track_name="B",
                module_name="api.read",
                racers=(RacerName.S1_SONNET, RacerName.S3_GEMINI),
            ),
        ),
    ),
}


def canonical_module_name(module_name: str) -> str:
    normalized = normalize_identifier(module_name)

    for candidate in MODULE_BRANCH_SLUGS:
        if normalize_identifier(candidate) == normalized:
            return candidate

    for alias, canonical in CANONICAL_MODULE_ALIASES.items():
        if normalize_identifier(alias) == normalized:
            return canonical

    return module_name


def module_branch_slug(module_name: str) -> str:
    canonical_name = canonical_module_name(module_name)
    if canonical_name in MODULE_BRANCH_SLUGS:
        return MODULE_BRANCH_SLUGS[canonical_name]

    sanitized = re.sub(r"[^a-z0-9]+", "_", canonical_name.strip().lower()).strip("_")
    return sanitized or "module"


def module_name_from_slug(module_slug: str) -> str:
    for module_name, slug in MODULE_BRANCH_SLUGS.items():
        if slug == module_slug:
            return module_name
    return module_slug


def get_round_config(round_num: int) -> RoundRaceConfig:
    try:
        return ROUND_RACE_CONFIGS[round_num]
    except KeyError as exc:
        raise ValueError("Unknown round number: {0}".format(round_num)) from exc
