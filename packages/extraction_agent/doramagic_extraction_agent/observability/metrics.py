"""Token and cost metrics for extraction runs."""
from __future__ import annotations
from dataclasses import dataclass, field

@dataclass
class PhaseMetrics:
    """Per-phase metrics."""
    phase_name: str
    input_tokens: int = 0
    output_tokens: int = 0
    llm_calls: int = 0
    tool_calls: int = 0
    tool_calls_by_name: dict[str, int] = field(default_factory=dict)

@dataclass
class ExtractionMetrics:
    """Cumulative metrics for one extraction run."""
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_llm_calls: int = 0
    total_tool_calls: int = 0
    total_retries: int = 0
    by_phase: dict[str, PhaseMetrics] = field(default_factory=dict)

    def _ensure_phase(self, phase: str) -> PhaseMetrics:
        if phase not in self.by_phase:
            self.by_phase[phase] = PhaseMetrics(phase_name=phase)
        return self.by_phase[phase]

    def record_llm_call(self, phase: str, input_tokens: int, output_tokens: int) -> None:
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_llm_calls += 1
        pm = self._ensure_phase(phase)
        pm.input_tokens += input_tokens
        pm.output_tokens += output_tokens
        pm.llm_calls += 1

    def record_tool_call(self, phase: str, tool_name: str) -> None:
        self.total_tool_calls += 1
        pm = self._ensure_phase(phase)
        pm.tool_calls += 1
        pm.tool_calls_by_name[tool_name] = pm.tool_calls_by_name.get(tool_name, 0) + 1

    def record_retry(self, phase: str) -> None:
        self.total_retries += 1

    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.total_output_tokens

    def summary(self) -> dict:
        return {
            "total_tokens": self.total_tokens,
            "total_input": self.total_input_tokens,
            "total_output": self.total_output_tokens,
            "llm_calls": self.total_llm_calls,
            "tool_calls": self.total_tool_calls,
            "retries": self.total_retries,
            "by_phase": {k: {"tokens": v.input_tokens + v.output_tokens, "llm_calls": v.llm_calls, "tool_calls": v.tool_calls} for k, v in self.by_phase.items()},
        }
