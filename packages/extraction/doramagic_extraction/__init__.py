"""Doramagic extraction package."""

from __future__ import annotations

from .stage15_agentic import check_claims_have_evidence, run_stage15_agentic

__all__ = ["check_claims_have_evidence", "run_stage15_agentic"]
