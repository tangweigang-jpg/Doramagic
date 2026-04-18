"""Tools package — submit_* tool schemas used in each phase.

Each phase owns its submit tool schema via phase.submit_tool_schema().
This package re-exports them as a convenience for inspection / testing.
"""

from doramagic_web_publisher.phases.constraints import ConstraintsPhase
from doramagic_web_publisher.phases.content import ContentPhase
from doramagic_web_publisher.phases.evaluator import EvaluatorPhase
from doramagic_web_publisher.phases.faq import FaqPhase

SUBMIT_TOOL_SCHEMAS: dict[str, dict] = {
    "content": ContentPhase().submit_tool_schema(),
    "constraints": ConstraintsPhase().submit_tool_schema(),
    "faq": FaqPhase().submit_tool_schema(),
    "evaluator": EvaluatorPhase().submit_tool_schema(),
}

__all__ = ["SUBMIT_TOOL_SCHEMAS"]
