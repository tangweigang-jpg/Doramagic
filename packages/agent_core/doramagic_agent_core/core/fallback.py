"""Fallback sentinel types shared across extraction pipelines."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RawFallback:
    """Sentinel returned when both Instructor and JSON extraction fail.

    The synthesis handler checks ``isinstance(result, RawFallback)`` to
    decide whether to abort or degrade gracefully.
    """

    text: str
    stage: str  # "l1_instructor_failed" | "l2_extract_failed" | "l3_raw"
