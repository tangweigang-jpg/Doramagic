"""State machine definitions for the FlowController.

12 core states for v1. 4 intermediate _DONE states deferred to Phase 5 hardening.
Full 16-state list: 12 core + PHASE_A_DONE, PHASE_B_DONE, PHASE_CD_DONE, PHASE_E_DONE.

State machine diagram:
    INIT ──► PHASE_A ──► PHASE_A_CLARIFY ──► PHASE_A (resume)
                │                                  │
                ▼ (no clarification needed)         ▼
             PHASE_B ──► PHASE_CD ──► PHASE_E ──► PHASE_F
                                                      │
                                                      ▼
                               PHASE_G ◄──── (REVISE, max 3)
                                  │
                          PASS    │    BLOCKED
                           ▼      │      ▼
                       PHASE_H    │    ERROR
                          │       │
                          ▼       │
                        DONE      │
                                  │
                     Any phase ──►DEGRADED
"""

from __future__ import annotations

from enum import Enum


class Phase(str, Enum):
    """Controller states. Each state maps to an executor or a control action."""

    INIT = "INIT"
    PHASE_A = "PHASE_A"
    PHASE_A_CLARIFY = "PHASE_A_CLARIFY"  # waiting for user clarification
    PHASE_B = "PHASE_B"
    PHASE_CD = "PHASE_CD"  # extraction + community harvest
    PHASE_E = "PHASE_E"
    PHASE_F = "PHASE_F"
    PHASE_G = "PHASE_G"
    PHASE_G_REVISE = "PHASE_G_REVISE"  # loop back to F
    PHASE_H = "PHASE_H"
    DONE = "DONE"
    DEGRADED = "DEGRADED"
    ERROR = "ERROR"


# Valid state transitions. Key = current state, value = set of allowed next states.
TRANSITIONS: dict[Phase, set[Phase]] = {
    Phase.INIT: {Phase.PHASE_A},
    Phase.PHASE_A: {Phase.PHASE_A_CLARIFY, Phase.PHASE_B},
    Phase.PHASE_A_CLARIFY: {Phase.PHASE_A},
    Phase.PHASE_B: {Phase.PHASE_CD, Phase.ERROR},
    Phase.PHASE_CD: {Phase.PHASE_E, Phase.DEGRADED, Phase.ERROR},
    Phase.PHASE_E: {Phase.PHASE_F, Phase.ERROR},
    Phase.PHASE_F: {Phase.PHASE_G, Phase.ERROR},
    Phase.PHASE_G: {Phase.PHASE_H, Phase.PHASE_G_REVISE, Phase.ERROR},
    Phase.PHASE_G_REVISE: {Phase.PHASE_F},
    Phase.PHASE_H: {Phase.DONE, Phase.ERROR},
    Phase.DONE: set(),  # terminal
    Phase.DEGRADED: set(),  # terminal
    Phase.ERROR: set(),  # terminal
}

# Any non-terminal phase can transition to DEGRADED
for phase in Phase:
    if phase not in (Phase.DONE, Phase.DEGRADED, Phase.ERROR):
        TRANSITIONS[phase].add(Phase.DEGRADED)


# Phase → executor name mapping (for dispatcher)
PHASE_EXECUTOR_MAP: dict[Phase, str | None] = {
    Phase.INIT: None,  # controller handles directly
    Phase.PHASE_A: "NeedProfileBuilder",
    Phase.PHASE_A_CLARIFY: None,  # controller handles (wait for user)
    Phase.PHASE_B: "DiscoveryRunner",
    Phase.PHASE_CD: "SoulExtractorBatch",  # also runs CommunityHarvester serially after
    Phase.PHASE_E: "SynthesisRunner",
    Phase.PHASE_F: "SkillCompiler",
    Phase.PHASE_G: "Validator",
    Phase.PHASE_G_REVISE: None,  # controller routes back to F
    Phase.PHASE_H: "DeliveryPackager",
    Phase.DONE: None,
    Phase.DEGRADED: None,
    Phase.ERROR: None,
}

# Maximum REVISE loops for Phase G → F
MAX_REVISE_LOOPS = 3
