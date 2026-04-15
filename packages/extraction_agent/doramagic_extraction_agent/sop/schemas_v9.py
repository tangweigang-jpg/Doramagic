"""v9 Pydantic schemas for structured BD extraction.

Introduces BDCandidate (worker-level structured output) and
ModuleClassification (coverage-aware module tracking).

Key principle: evidence is bound at worker exploration time,
not re-invented by synthesis.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class EvidenceRef(BaseModel):
    """Precise evidence reference bound at exploration time.

    Workers produce these while reading code — the file, line, and
    function name are recorded at the moment of discovery, not
    reconstructed later by synthesis.
    """

    file: str = Field(description="Relative path, e.g. akshare/stock/stock_zh_a.py")
    line: int = Field(default=0, ge=0, description="Line number (0 = unknown)")
    function: str = Field(
        default="",
        description="Function or method name at that line",
    )
    snippet: str = Field(
        default="",
        max_length=300,
        description="2-3 line code snippet for verification context",
    )

    def to_evidence_str(self) -> str:
        """Convert to legacy file:line(function) format."""
        if self.function:
            return f"{self.file}:{self.line}({self.function})"
        if self.line > 0:
            return f"{self.file}:{self.line}"
        return self.file

    @model_validator(mode="before")
    @classmethod
    def coerce_from_string(cls, data: Any) -> Any:
        """Accept legacy flat evidence string and parse it."""
        if isinstance(data, str):
            data = data.strip()
            # Parse "file:line(function)" format
            m = re.match(
                r"^(.+?):(\d+)(?:\((\w+)\))?$",
                data,
            )
            if m:
                return {
                    "file": m.group(1),
                    "line": int(m.group(2)),
                    "function": m.group(3) or "",
                }
            # Bare file path
            return {"file": data, "line": 0, "function": ""}
        return data

    @field_validator("file")
    @classmethod
    def normalize_file(cls, v: str) -> str:
        """Strip leading ./ and normalize separators."""
        return v.lstrip("./").replace("\\", "/")


_BD_TYPE_PATTERN = r"^(T|B|BA|DK|RC|M)(/(?:T|B|BA|DK|RC|M))*$"


class BDCandidate(BaseModel):
    """A BD candidate emitted by a worker at exploration time.

    Workers produce these during code reading. Evidence is bound NOW,
    not re-invented by synthesis later.
    """

    content: str = Field(
        min_length=5,
        description="The specific design decision statement",
    )
    candidate_type: str = Field(
        default="B",
        description="Worker's best-guess classification: T/B/BA/DK/RC/M",
    )
    evidence: EvidenceRef
    rationale_draft: str = Field(
        default="",
        description=(
            "Worker's rough WHY + BOUNDARY. Synthesis will refine to meet the 40-char minimum."
        ),
    )
    module: str = Field(
        default="",
        description="Top-level module/directory, e.g. 'akshare/stock'",
    )
    source_worker: str = Field(
        default="unknown",
        description="Which worker found this: arch/workflow/math/etc.",
    )
    confidence: Literal["high", "medium", "low"] = "medium"

    @model_validator(mode="before")
    @classmethod
    def coerce_from_legacy(cls, data: Any) -> Any:
        """Accept legacy worker output format for backward compatibility.

        Legacy workers produce flat dicts with string evidence and
        'decision' instead of 'content'. This validator normalizes
        them into BDCandidate shape.
        """
        if not isinstance(data, dict):
            return data
        # decision → content
        if "content" not in data and "decision" in data:
            data["content"] = data.pop("decision")
        # flat evidence string → EvidenceRef
        if isinstance(data.get("evidence"), str):
            data["evidence"] = data["evidence"]  # EvidenceRef.coerce handles it
        # type → candidate_type
        if "candidate_type" not in data and "type" in data:
            data["candidate_type"] = data.pop("type")
        if "candidate_type" not in data and "type_hint" in data:
            data["candidate_type"] = data.pop("type_hint")
        # rationale → rationale_draft
        if "rationale_draft" not in data and "rationale" in data:
            data["rationale_draft"] = data.pop("rationale")
        # stage → module (rough mapping)
        if "module" not in data and "stage" in data:
            data["module"] = data.get("stage", "")
        return data

    @field_validator("candidate_type", mode="before")
    @classmethod
    def coerce_type(cls, v: Any) -> str:
        """Fuzzy-match BD type to valid enum values."""
        if not isinstance(v, str):
            return "B"
        v = v.strip().upper()
        # Handle common MiniMax quirks
        if not v or v in ("UNKNOWN", "NONE", "OTHER"):
            return "B"
        # Normalize separators
        v = v.replace(",", "/").replace("|", "/").replace(" ", "")
        if re.match(_BD_TYPE_PATTERN, v):
            return v
        # Try single-type extraction — order matters:
        # Check multi-char types first to avoid "MATH"→"T" or
        # "REGULATORY"→"T" via substring match.
        _WORD_MAP = {
            "BUSINESS_ARCH": "BA",
            "ARCHITECTURE": "BA",
            "DOMAIN": "DK",
            "KNOWLEDGE": "DK",
            "RISK": "RC",
            "CONSTRAINT": "RC",
            "REGULATORY": "RC",
            "MATH": "M",
            "ALGORITHM": "M",
            "TRIVIAL": "T",
            "BUSINESS": "B",
        }
        for word, mapped in _WORD_MAP.items():
            if word in v:
                return mapped
        # Fallback: exact substring (longest first)
        for t in ("BA", "DK", "RC", "B", "M", "T"):
            if t in v:
                return t
        return "B"


class WorkerBDOutput(BaseModel):
    """Standardized output from any exploration worker.

    Workers write this to their artifact file (e.g. worker_arch.json).
    Contains both structured BD candidates and a list of all modules
    the worker explored — enabling coverage classification.
    """

    candidates: list[BDCandidate] = Field(default_factory=list)
    modules_visited: list[str] = Field(
        default_factory=list,
        description="All top-level modules this worker explored",
    )
    worker_name: str = Field(default="unknown")

    @model_validator(mode="before")
    @classmethod
    def coerce_from_legacy_format(cls, data: Any) -> Any:
        """Accept legacy worker output formats.

        Legacy formats handled:
        - worker_arch.json: {stages: [...]} with design_decisions
        - worker_workflow/math.json: bare list of BD dicts
        - worker_arch_deep.json: bare list with {finding, type_hint, ...}
        - worker_resource.json: {data_sources: [...]} — no BD candidates
        """
        if isinstance(data, list):
            # Bare list — could be workflow BDs or arch_deep findings
            coerced = []
            for item in data:
                if not isinstance(item, dict):
                    continue
                # arch_deep format: finding → content, type_hint → type
                if "finding" in item and "content" not in item:
                    item["content"] = item.pop("finding")
                if "type_hint" in item and "candidate_type" not in item:
                    item["candidate_type"] = item.pop("type_hint")
                if "category" in item and "module" not in item:
                    item["module"] = item.get("category", "")
                coerced.append(item)
            return {"candidates": coerced, "worker_name": "unknown"}
        if not isinstance(data, dict):
            return data
        # Already has candidates — pass through
        if "candidates" in data:
            return data
        # worker_arch format: {stages: [...]}
        if "stages" in data:
            candidates = []
            for stage in data.get("stages", []):
                for dd in stage.get("design_decisions", []):
                    dd["module"] = stage.get("name", "")
                    dd["source_worker"] = "arch"
                    candidates.append(dd)
            return {
                "candidates": candidates,
                "modules_visited": [s.get("name", "") for s in data.get("stages", [])],
                "worker_name": "arch",
            }
        # worker_resource format: {data_sources: [...]} — no BD candidates
        if "data_sources" in data:
            return {
                "candidates": [],
                "worker_name": "resource",
            }
        return data


class LocalSynthesisResult(BaseModel):
    """Output of per-worker local synthesis (Map phase)."""

    validated: list[dict] = Field(
        default_factory=list,
        description="Promoted BD candidates as dicts (will become BusinessDecision)",
    )
    rejected: list[dict] = Field(
        default_factory=list,
        description="Rejected candidates with {id, reason}",
    )
    worker_name: str = Field(default="unknown")


class ModuleClassification(BaseModel):
    """Explicit classification for a visited module.

    Every module from the coverage manifest must be classified.
    No silent drops.
    """

    module: str = Field(description="Module path, e.g. 'akshare/stock'")
    classification: Literal["has_bd", "gap", "non_decision", "test_only", "config_only"]
    reason: str = Field(
        default="",
        description="Why this classification was assigned",
    )
    bd_count: int = Field(
        default=0,
        description="Number of BDs referencing this module",
    )


class FixerResult(BaseModel):
    """Output of the fixer phase (targeted evidence repair)."""

    fixed: list[dict] = Field(
        default_factory=list,
        description="BDs with corrected evidence",
    )
    unfixable: list[str] = Field(
        default_factory=list,
        description="BD IDs that could not be repaired",
    )
    dropped: list[str] = Field(
        default_factory=list,
        description="BD IDs removed as hallucinated (no code basis found)",
    )
