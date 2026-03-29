"""Phase F executor: platform validation + content quality gate."""

from __future__ import annotations

from pathlib import Path

from doramagic_contracts.envelope import ModuleResultEnvelope
from doramagic_contracts.skill import ValidationInput, ValidationReport
from doramagic_skill_compiler.compiler import score_skill_quality
from pydantic import BaseModel


class ValidatorExecutor:
    async def execute(
        self, input: BaseModel, adapter: object, config
    ) -> ModuleResultEnvelope[ValidationReport]:
        if not isinstance(input, ValidationInput):
            raise TypeError("ValidatorExecutor expects ValidationInput")

        from doramagic_platform_openclaw.validator import run_validation

        result = run_validation(input)
        report = result.data or ValidationReport(status="BLOCKED", checks=[])

        skill_md = self._read_text(input.skill_bundle.skill_md_path)
        quality = (
            score_skill_quality(skill_md)
            if skill_md
            else {
                "overall_score": 0.0,
                "dimension_scores": {},
                "weakest_dimension": "Coverage",
                "weakest_section": "knowledge",
                "repairable": False,
                "repair_plan": [],
                "blockers": ["missing_skill_md"],
            }
        )
        event_bus = getattr(config, "event_bus", None)
        if event_bus is not None:
            for dimension, score in quality["dimension_scores"].items():
                score_10 = round(score / 10, 1)
                event_bus.emit(
                    "sub_progress",
                    f"质量评分: {dimension} = {score_10}/10",
                    phase="PHASE_F",
                    meta={"dimension": dimension, "score": score, "score_10": score_10},
                )

        has_blockers = report.status == "BLOCKED" or any(
            not check.passed and check.severity == "blocking" for check in report.checks
        )
        repairable = bool(quality["repairable"]) and not has_blockers
        if has_blockers:
            status = "BLOCKED"
            delivery_tier = "synthesis_pack"
        elif quality["overall_score"] >= 60:
            status = "PASS"
            delivery_tier = "full_skill"
        elif repairable:
            status = "REVISE"
            delivery_tier = "draft_skill"
        else:
            status = "BLOCKED"
            delivery_tier = "draft_skill"

        report.status = status
        report.overall_score = quality["overall_score"]
        report.dimension_scores = quality["dimension_scores"]
        report.weakest_dimension = quality["weakest_dimension"]
        report.weakest_section = quality["weakest_section"]
        report.repairable = repairable
        report.repair_plan = quality["repair_plan"][:2]
        report.delivery_tier = delivery_tier
        report.residual_risks = quality["blockers"]
        report.revise_instructions = [
            f"Repair section `{section}` to improve {quality['weakest_dimension']}"
            for section in report.repair_plan
        ]

        result.data = report
        if status == "REVISE":
            result.status = "degraded"
        elif status == "BLOCKED":
            result.status = "blocked"
        else:
            result.status = "ok"
        return result

    def _read_text(self, path_str: str) -> str:
        if not path_str:
            return ""
        path = Path(path_str).expanduser()
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8", errors="replace")

    def validate_input(self, input: BaseModel) -> list[str]:
        if not isinstance(input, ValidationInput):
            return ["ValidatorExecutor expects ValidationInput"]
        return []

    def can_degrade(self) -> bool:
        return True
