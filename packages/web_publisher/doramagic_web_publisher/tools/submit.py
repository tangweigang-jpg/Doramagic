"""Convenience module: all submit_* tool schemas from each phase.

These schemas are the ground-truth contract between the LLM and the pipeline.
They align with Package Schema §1.2 field groups A/D/E/F/G/H/I/J/K/L.
"""

from __future__ import annotations

from doramagic_web_publisher.phases.constraints import ConstraintsPhase
from doramagic_web_publisher.phases.content import ContentPhase
from doramagic_web_publisher.phases.evaluator import EvaluatorPhase
from doramagic_web_publisher.phases.faq import FaqPhase


def get_content_tool_schema() -> dict:
    """Return the submit_content_fields tool schema (groups A, E, G)."""
    return ContentPhase().submit_tool_schema()


def get_constraints_tool_schema() -> dict:
    """Return the submit_constraints_fields tool schema (group D)."""
    return ConstraintsPhase().submit_tool_schema()


def get_faq_tool_schema() -> dict:
    """Return the submit_faq_fields tool schema (group F)."""
    return FaqPhase().submit_tool_schema()


def get_evaluator_tool_schema() -> dict:
    """Return the submit_evaluator_fields tool schema (groups H, I, J, K, L)."""
    return EvaluatorPhase().submit_tool_schema()
