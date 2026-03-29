"""State machine definitions for the FlowController -- v12.1.1 DAG architecture.

v12.1.1 changes:
  - Phase enum remapped: PHASE_CD split into C (extraction) + D (synthesis)
  - PHASE_G_REVISE removed: REVISE is now a conditional edge F -> E
  - Conditional edges replace linear TRANSITIONS
  - MAX_REVISE_LOOPS reduced from 3 to 1 (targeted repair, not full recompile)
"""

from __future__ import annotations

from collections.abc import Callable
from enum import Enum


class Phase(str, Enum):
    """Controller states. Each state maps to an executor or a control action."""

    INIT = "INIT"
    PHASE_A = "PHASE_A"  # Need Profile + Input Router
    PHASE_A_CLARIFY = "PHASE_A_CLARIFY"  # Socratic Gate (waiting for user)
    PHASE_B = "PHASE_B"  # Discovery
    BRICK_STITCH = "BRICK_STITCH"  # Direct brick stitching
    PHASE_C = "PHASE_C"  # Fan-out Repo Workers (extraction + community)
    PHASE_D = "PHASE_D"  # Synthesis
    PHASE_E = "PHASE_E"  # Compile
    PHASE_F = "PHASE_F"  # Validate + QA Gate
    PHASE_G = "PHASE_G"  # Package + Deliver
    DONE = "DONE"
    DEGRADED = "DEGRADED"
    ERROR = "ERROR"


# Valid state transitions (legality check). Key = current, value = set of allowed next states.
TRANSITIONS: dict[Phase, set[Phase]] = {
    Phase.INIT: {Phase.PHASE_A, Phase.ERROR},
    Phase.PHASE_A: {
        Phase.PHASE_A_CLARIFY,
        Phase.BRICK_STITCH,
        Phase.PHASE_B,
        Phase.PHASE_C,
        Phase.DEGRADED,
        Phase.ERROR,
    },
    Phase.PHASE_A_CLARIFY: {Phase.PHASE_A, Phase.PHASE_B, Phase.DEGRADED, Phase.ERROR},
    Phase.PHASE_B: {Phase.PHASE_C, Phase.DEGRADED, Phase.ERROR},
    Phase.BRICK_STITCH: {Phase.PHASE_F, Phase.DEGRADED, Phase.ERROR},
    Phase.PHASE_C: {Phase.PHASE_D, Phase.DEGRADED, Phase.ERROR},
    Phase.PHASE_D: {Phase.PHASE_E, Phase.DEGRADED, Phase.ERROR},
    Phase.PHASE_E: {Phase.PHASE_F, Phase.DEGRADED, Phase.ERROR},
    Phase.PHASE_F: {Phase.PHASE_G, Phase.PHASE_E, Phase.DEGRADED, Phase.ERROR},  # F->E = REVISE
    Phase.PHASE_G: {Phase.DONE, Phase.DEGRADED, Phase.ERROR},
    Phase.DONE: set(),
    Phase.DEGRADED: set(),
    Phase.ERROR: set(),
}


class EdgeContext:
    """Snapshot of controller state for conditional edge evaluation.

    All fields are simple types so edge lambdas remain deterministic and testable.
    """

    def __init__(
        self,
        raw_input: str = "",
        routing_route: str = "",
        brick_match_count: int = 0,
        brick_total_count: int = 0,
        clarification_round: int = 0,
        candidate_count: int = 0,
        successful_extractions: int = 0,
        has_clawhub: bool = False,
        synthesis_ok: bool = False,
        compile_ok: bool = False,
        compile_ready: bool = True,
        quality_score: float = 0.0,
        revise_count: int = 0,
        weakest_section: str | None = None,
        blockers: list[str] | None = None,
        budget_exceeded: bool = False,
    ):
        self.raw_input = raw_input
        self.routing_route = routing_route
        self.brick_match_count = brick_match_count
        self.brick_total_count = brick_total_count
        self.clarification_round = clarification_round
        self.candidate_count = candidate_count
        self.successful_extractions = successful_extractions
        self.has_clawhub = has_clawhub
        self.synthesis_ok = synthesis_ok
        self.compile_ok = compile_ok
        self.compile_ready = compile_ready
        self.quality_score = quality_score
        self.revise_count = revise_count
        self.weakest_section = weakest_section
        self.blockers = blockers or []
        self.budget_exceeded = budget_exceeded


# Conditional edges: (current_phase) -> list of (condition, target_phase)
# First matching condition wins. Last entry should always be a fallback (lambda ctx: True).
CONDITIONAL_EDGES: dict[Phase, list[tuple[Callable[[EdgeContext], bool], Phase]]] = {
    Phase.INIT: [
        (lambda ctx: bool(ctx.raw_input.strip()), Phase.PHASE_A),
        (lambda ctx: True, Phase.ERROR),
    ],
    Phase.PHASE_A: [
        (lambda ctx: ctx.routing_route == "LOW_CONFIDENCE", Phase.PHASE_A_CLARIFY),
        (lambda ctx: ctx.routing_route == "DIRECT_URL", Phase.PHASE_C),  # skip B
        (
            lambda ctx: (
                ctx.routing_route == "DOMAIN_EXPLORE"
                and ctx.brick_match_count >= 3
                and ctx.brick_total_count >= 30
            ),
            Phase.BRICK_STITCH,
        ),
        (lambda ctx: ctx.routing_route in ("NAMED_PROJECT", "DOMAIN_EXPLORE"), Phase.PHASE_B),
        (lambda ctx: True, Phase.PHASE_B),  # fallback
    ],
    Phase.PHASE_A_CLARIFY: [
        (lambda ctx: ctx.clarification_round < 2, Phase.PHASE_A),  # re-profile
        (lambda ctx: True, Phase.PHASE_B),  # exceeded max rounds, try best guess
    ],
    Phase.PHASE_B: [
        (lambda ctx: ctx.candidate_count > 0, Phase.PHASE_C),
        (lambda ctx: True, Phase.DEGRADED),
    ],
    Phase.BRICK_STITCH: [
        (lambda ctx: True, Phase.PHASE_F),
    ],
    Phase.PHASE_C: [
        (lambda ctx: ctx.successful_extractions > 0, Phase.PHASE_D),
        (lambda ctx: ctx.successful_extractions == 0 and ctx.has_clawhub, Phase.PHASE_D),
        (lambda ctx: True, Phase.DEGRADED),
    ],
    Phase.PHASE_D: [
        (lambda ctx: ctx.synthesis_ok and ctx.compile_ready, Phase.PHASE_E),
        (lambda ctx: ctx.synthesis_ok and not ctx.compile_ready, Phase.DEGRADED),
        (lambda ctx: True, Phase.DEGRADED),
    ],
    Phase.PHASE_E: [
        (lambda ctx: ctx.compile_ok, Phase.PHASE_F),
        (lambda ctx: True, Phase.DEGRADED),
    ],
    Phase.PHASE_F: [
        (lambda ctx: ctx.quality_score >= 60 and not ctx.blockers, Phase.PHASE_G),
        (
            lambda ctx: (
                ctx.quality_score < 60 and ctx.revise_count < 1 and ctx.weakest_section is not None
            ),
            Phase.PHASE_E,
        ),  # REVISE
        (lambda ctx: True, Phase.DEGRADED),
    ],
    Phase.PHASE_G: [
        (lambda ctx: True, Phase.DONE),
    ],
}


# Phase -> executor name mapping
PHASE_EXECUTOR_MAP: dict[Phase, str | None] = {
    Phase.INIT: None,
    Phase.PHASE_A: "NeedProfileBuilder",
    Phase.PHASE_A_CLARIFY: None,  # controller handles (wait for user)
    Phase.PHASE_B: "DiscoveryRunner",
    Phase.BRICK_STITCH: None,  # controller handles (direct brick stitch)
    Phase.PHASE_C: "WorkerSupervisor",  # fan-out repo workers
    Phase.PHASE_D: "SynthesisRunner",
    Phase.PHASE_E: "SkillCompiler",
    Phase.PHASE_F: "Validator",
    Phase.PHASE_G: "DeliveryPackager",
    Phase.DONE: None,
    Phase.DEGRADED: None,
    Phase.ERROR: None,
}

# Maximum REVISE loops (F -> E -> F). Targeted repair = 1 max.
MAX_REVISE_LOOPS = 1

# Phase progress percentage estimates for enhanced feedback
PHASE_PROGRESS_PCT: dict[Phase, int] = {
    Phase.INIT: 0,
    Phase.PHASE_A: 5,
    Phase.PHASE_A_CLARIFY: 5,
    Phase.PHASE_B: 15,
    Phase.PHASE_C: 25,
    Phase.PHASE_D: 60,
    Phase.PHASE_E: 70,
    Phase.PHASE_F: 85,
    Phase.PHASE_G: 95,
    Phase.DONE: 100,
    Phase.DEGRADED: 100,
    Phase.ERROR: 100,
}
