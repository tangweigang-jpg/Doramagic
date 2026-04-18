"""Phase registry — ordered list of all pipeline phases.

PHASES order is fixed: content → constraints → faq → evaluator.
The evaluator phase depends on outputs from the first three phases.
"""

from doramagic_web_publisher.phases.base import Phase
from doramagic_web_publisher.phases.constraints import ConstraintsPhase
from doramagic_web_publisher.phases.content import ContentPhase
from doramagic_web_publisher.phases.evaluator import EvaluatorPhase
from doramagic_web_publisher.phases.faq import FaqPhase

# Ordered pipeline phases — DO NOT reorder without checking dependencies.
PHASES: list[Phase] = [
    ContentPhase(),
    ConstraintsPhase(),
    FaqPhase(),
    EvaluatorPhase(),
]

PHASE_NAMES: list[str] = [p.name for p in PHASES]

__all__ = [
    "PHASES",
    "PHASE_NAMES",
    "ConstraintsPhase",
    "ContentPhase",
    "EvaluatorPhase",
    "FaqPhase",
    "Phase",
]
