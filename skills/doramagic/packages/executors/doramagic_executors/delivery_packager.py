"""Phase G executor: always package the best available delivery tier."""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

from doramagic_contracts.envelope import ModuleResultEnvelope, RunMetrics, WarningItem
from doramagic_contracts.skill import DeliveryManifest
from pydantic import BaseModel


class DeliveryPackager:
    async def execute(
        self, input: BaseModel, adapter: object, config
    ) -> ModuleResultEnvelope[DeliveryManifest]:
        started = time.monotonic()
        artifacts = getattr(input, "phase_artifacts", {})
        delivery_tier = getattr(input, "delivery_tier", "full_skill")
        delivery_dir = config.run_dir / "delivery"
        delivery_dir.mkdir(parents=True, exist_ok=True)

        artifact_paths: dict[str, str] = {}
        warnings: list[WarningItem] = []

        compile_bundle = artifacts.get("compile_bundle", {})
        compile_paths = (
            compile_bundle.get("artifact_paths", {}) if isinstance(compile_bundle, dict) else {}
        )
        if delivery_tier in ("full_skill", "draft_skill") and compile_paths:
            for name, src in compile_paths.items():
                src_path = Path(src).expanduser()
                if not src_path.exists():
                    continue
                dst = delivery_dir / Path(name).name
                shutil.copy2(src_path, dst)
                artifact_paths[dst.name] = str(dst)

        if delivery_tier == "synthesis_pack":
            self._write_json(
                delivery_dir / "synthesis_bundle.json", artifacts.get("synthesis_bundle", {})
            )
            self._write_json(
                delivery_dir / "extraction_aggregate.json",
                artifacts.get("extraction_aggregate", {}),
            )
            artifact_paths["synthesis_bundle.json"] = str(delivery_dir / "synthesis_bundle.json")
            artifact_paths["extraction_aggregate.json"] = str(
                delivery_dir / "extraction_aggregate.json"
            )

        if delivery_tier == "repo_reports":
            self._write_json(
                delivery_dir / "repo_reports.json", artifacts.get("extraction_aggregate", {})
            )
            artifact_paths["repo_reports.json"] = str(delivery_dir / "repo_reports.json")

        if delivery_tier == "candidate_brief":
            self._write_json(
                delivery_dir / "candidate_brief.json", artifacts.get("discovery_result", {})
            )
            artifact_paths["candidate_brief.json"] = str(delivery_dir / "candidate_brief.json")

        if not artifact_paths:
            warnings.append(
                WarningItem(
                    code="EMPTY_DELIVERY",
                    message="No primary artifacts found; writing controller snapshot",
                )
            )
            self._write_json(delivery_dir / "controller_snapshot.json", artifacts)
            artifact_paths["controller_snapshot.json"] = str(
                delivery_dir / "controller_snapshot.json"
            )

        dsd_path = delivery_dir / "DSD_REPORT.md"
        dsd_path.write_text(self._build_dsd_report(artifacts), encoding="utf-8")
        artifact_paths["DSD_REPORT.md"] = str(dsd_path)

        confidence_path = delivery_dir / "CONFIDENCE_STATS.json"
        self._write_json(confidence_path, self._build_confidence_stats(artifacts, delivery_tier))
        artifact_paths["CONFIDENCE_STATS.json"] = str(confidence_path)

        summary = {
            "delivery_tier": delivery_tier,
            "artifact_count": len(artifact_paths),
            "degraded_mode": getattr(input, "degraded_mode", False),
            "quality_score": self._quality_score(artifacts),
        }
        user_message = self._user_message(delivery_tier, artifact_paths)
        manifest = DeliveryManifest(
            delivery_tier=delivery_tier,
            artifact_paths=artifact_paths,
            run_summary=summary,
            user_message=user_message,
        )
        self._write_json(delivery_dir / "delivery_manifest.json", manifest.model_dump())

        return ModuleResultEnvelope(
            module_name="DeliveryPackager",
            status="ok",
            warnings=warnings,
            data=manifest,
            metrics=RunMetrics(
                wall_time_ms=int((time.monotonic() - started) * 1000),
                llm_calls=0,
                prompt_tokens=0,
                completion_tokens=0,
                estimated_cost_usd=0.0,
            ),
        )

    def _user_message(self, delivery_tier: str, artifact_paths: dict[str, str]) -> str:
        return {
            "full_skill": f"已交付完整 SKILL 包，共 {len(artifact_paths)} 个文件。",
            "draft_skill": "质量门禁未通过，已交付可审阅的 draft skill 包。",
            "synthesis_pack": "编译未完成，已交付 synthesis 和 extraction 中间产物。",
            "repo_reports": "合成未完成，已交付存活 repo 的独立提取结果。",
            "candidate_brief": "提取未完成，已交付候选项目与搜索证据。",
        }.get(delivery_tier, "已交付当前可用的最佳产物。")

    def _write_json(self, path: Path, payload: Any) -> None:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _build_dsd_report(self, artifacts: dict[str, Any]) -> str:
        extraction = artifacts.get("extraction_aggregate", {})
        synthesis = artifacts.get("synthesis_bundle", {})
        validation = artifacts.get("validation_report", {})
        repo_lines = []
        if isinstance(extraction, dict):
            for env in extraction.get("repo_envelopes", [])[:6]:
                if not isinstance(env, dict):
                    continue
                repo_name = env.get("repo_name", "unknown")
                repo_type = env.get("repo_type", "unknown")
                confidence = env.get("extraction_confidence", 0.0)
                dsd_metrics = (env.get("community_signals") or {}).get("dsd_metrics", {})
                warnings = dsd_metrics.get("dsd_warnings", [])
                repo_lines.append(
                    f"- {repo_name} ({repo_type}) confidence={confidence}: "
                    + (warnings[0] if warnings else "No major DSD warning surfaced.")
                )
        divergence_lines = []
        if isinstance(synthesis, dict):
            divergence_lines = [f"- {item}" for item in synthesis.get("divergences", [])[:6]]
        residual_risks = []
        if isinstance(validation, dict):
            residual_risks = [f"- {item}" for item in validation.get("residual_risks", [])[:6]]
        sections = [
            "# DSD REPORT",
            "",
            "## Repo Signals",
            *(repo_lines or ["- No repo-level DSD signal was captured in this run."]),
            "",
            "## Cross-Project Divergences",
            *(divergence_lines or ["- No major cross-project divergence was recorded."]),
            "",
            "## Residual Risks",
            *(residual_risks or ["- No additional residual risk was recorded."]),
            "",
        ]
        return "\n".join(sections)

    def _build_confidence_stats(
        self, artifacts: dict[str, Any], delivery_tier: str
    ) -> dict[str, Any]:
        extraction = artifacts.get("extraction_aggregate", {})
        validation = artifacts.get("validation_report", {})
        synthesis = artifacts.get("synthesis_bundle", {})
        return {
            "delivery_tier": delivery_tier,
            "quality_score": self._quality_score(artifacts),
            "dimension_scores": validation.get("dimension_scores", {})
            if isinstance(validation, dict)
            else {},
            "weakest_section": validation.get("weakest_section")
            if isinstance(validation, dict)
            else None,
            "success_count": extraction.get("success_count", 0)
            if isinstance(extraction, dict)
            else 0,
            "failed_count": extraction.get("failed_count", 0)
            if isinstance(extraction, dict)
            else 0,
            "compile_ready": synthesis.get("compile_ready", False)
            if isinstance(synthesis, dict)
            else False,
        }

    def _quality_score(self, artifacts: dict[str, Any]) -> float:
        validation = artifacts.get("validation_report", {})
        if isinstance(validation, dict):
            return float(validation.get("overall_score", 0.0))
        return 0.0

    def validate_input(self, input: BaseModel) -> list[str]:
        return []

    def can_degrade(self) -> bool:
        return False
