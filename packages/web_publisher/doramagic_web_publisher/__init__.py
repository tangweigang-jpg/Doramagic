"""Doramagic Web Publisher.

Local compilation agent that generates Crystal Package JSON and publishes
it to doramagic.ai via the Publish API.

Implements Part 1 of sops/crystal-web-publishing-sop.md v2.2.

Main entry points:
  WebPublisher  — high-level orchestrator (pipeline + assemble + preflight + publish)
  Pipeline      — phase-level pipeline driver
  Assembler     — Package JSON assembler
  PreflightRunner — local quality gate runner
  Publisher     — HTTP client for the Publish API
"""

from doramagic_web_publisher.assembler import Assembler
from doramagic_web_publisher.preflight import PreflightRunner
from doramagic_web_publisher.publisher import Publisher, PublishReport
from doramagic_web_publisher.runtime import PhaseContext, PhaseResult, Pipeline, PublishManifest

__version__ = "0.1.0"

__all__ = [
    "Assembler",
    "PhaseContext",
    "PhaseResult",
    "Pipeline",
    "PreflightRunner",
    "PublishManifest",
    "PublishReport",
    "Publisher",
    "__version__",
]
