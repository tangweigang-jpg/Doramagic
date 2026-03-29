"""Phase E executor: section-split compile with compile_ready guard."""

from __future__ import annotations

import time

from doramagic_contracts.envelope import ModuleResultEnvelope, RunMetrics, WarningItem
from doramagic_contracts.skill import SkillCompilerInput
from doramagic_skill_compiler.compiler import build_compile_bundle, compile_ready
from pydantic import BaseModel


class SkillCompilerExecutor:
    async def execute(self, input: BaseModel, adapter: object, config) -> ModuleResultEnvelope:
        started = time.monotonic()
        if not isinstance(input, SkillCompilerInput):
            return self._error("Expected SkillCompilerInput", started)

        if not compile_ready(input.synthesis_report):
            return ModuleResultEnvelope(
                module_name="SkillCompiler",
                status="blocked",
                warnings=[
                    WarningItem(
                        code="COMPILE_NOT_READY", message="Synthesis bundle is not compile-ready"
                    )
                ],
                data=None,
                metrics=self._metrics(started),
            )

        event_bus = getattr(config, "event_bus", None)
        section_names = input.target_sections or [
            "role",
            "knowledge",
            "workflow",
            "anti_patterns",
            "when_not_to_use",
        ]
        if event_bus is not None:
            for section_name in section_names:
                event_bus.emit(
                    "sub_progress",
                    f"编译 {section_name} section...",
                    phase="PHASE_E",
                    meta={"section_name": section_name},
                )

        phase_dir = config.run_dir / "staging" / "phase_e"
        bundle = await build_compile_bundle(input, adapter, phase_dir)

        return ModuleResultEnvelope(
            module_name="SkillCompiler",
            status="ok",
            warnings=[],
            data=bundle,
            metrics=self._metrics(started),
        )

    def _error(self, message: str, started: float) -> ModuleResultEnvelope:
        return ModuleResultEnvelope(
            module_name="SkillCompiler",
            status="error",
            error_code="E_INPUT_INVALID",
            warnings=[WarningItem(code="TYPE", message=message)],
            data=None,
            metrics=self._metrics(started),
        )

    def _metrics(self, started: float) -> RunMetrics:
        return RunMetrics(
            wall_time_ms=int((time.monotonic() - started) * 1000),
            llm_calls=0,
            prompt_tokens=0,
            completion_tokens=0,
            estimated_cost_usd=0.0,
        )

    def validate_input(self, input: BaseModel) -> list[str]:
        if not isinstance(input, SkillCompilerInput):
            return ["SkillCompiler expects SkillCompilerInput"]
        return []

    def can_degrade(self) -> bool:
        return True
