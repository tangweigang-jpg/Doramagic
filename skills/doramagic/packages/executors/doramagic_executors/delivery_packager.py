"""Phase H executor: Package staging artifacts into delivery bundle.

Copies validated artifacts from staging/ to delivery/.
Generates run_manifest.json with metrics summary.
Handles IOError with retry (CRITICAL GAP fix from CEO review).
"""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

from pydantic import BaseModel

from doramagic_contracts.envelope import ErrorCodes, ModuleResultEnvelope, RunMetrics, WarningItem
from doramagic_contracts.executor import ExecutorConfig


class DeliveryPackager:
    """Copies staging → delivery and writes run_manifest.json.

    This is the ONLY code that writes to delivery/.
    Staging/delivery isolation: LLM writes staging, Python writes delivery.
    """

    async def execute(
        self, input: BaseModel, adapter: object, config: ExecutorConfig,
    ) -> ModuleResultEnvelope:
        start = time.monotonic()
        staging = config.run_dir / "staging"
        delivery = config.run_dir / "delivery"
        delivery.mkdir(parents=True, exist_ok=True)

        # Find deliverable files in staging
        deliverables = [
            "SKILL.md", "PROVENANCE.md", "LIMITATIONS.md", "README.md",
            "skill_build_manifest.json",
        ]

        copied: list[str] = []
        warnings: list[WarningItem] = []

        for name in deliverables:
            # Search in staging subdirectories
            found = list(staging.rglob(name))
            if not found:
                if name in ("SKILL.md",):
                    # Critical file missing
                    elapsed = int((time.monotonic() - start) * 1000)
                    return ModuleResultEnvelope(
                        module_name="DeliveryPackager",
                        status="error",
                        error_code=ErrorCodes.UPSTREAM_MISSING,
                        warnings=[WarningItem(
                            code="MISSING_DELIVERABLE",
                            message=f"{name} not found in staging/",
                        )],
                        metrics=RunMetrics(
                            wall_time_ms=elapsed, llm_calls=0,
                            prompt_tokens=0, completion_tokens=0,
                            estimated_cost_usd=0.0,
                        ),
                    )
                warnings.append(WarningItem(
                    code="OPTIONAL_MISSING",
                    message=f"{name} not found in staging/, skipping",
                ))
                continue

            src = found[0]  # take first match
            dst = delivery / name

            # Copy with retry (CRITICAL GAP fix: Phase H IOError)
            for attempt in range(2):
                try:
                    shutil.copy2(src, dst)
                    copied.append(name)
                    break
                except IOError as e:
                    if attempt == 0:
                        warnings.append(WarningItem(
                            code="IO_RETRY",
                            message=f"IOError copying {name}, retrying: {e}",
                        ))
                    else:
                        elapsed = int((time.monotonic() - start) * 1000)
                        return ModuleResultEnvelope(
                            module_name="DeliveryPackager",
                            status="error",
                            error_code="E_IO_ERROR",
                            warnings=[WarningItem(
                                code="IO_FATAL",
                                message=f"Failed to copy {name} after 2 attempts: {e}",
                            )],
                            metrics=RunMetrics(
                                wall_time_ms=elapsed, llm_calls=0,
                                prompt_tokens=0, completion_tokens=0,
                                estimated_cost_usd=0.0,
                            ),
                        )

        # Write run manifest
        manifest = {
            "run_id": config.run_dir.name,
            "delivered_files": copied,
            "warnings": [w.model_dump() for w in warnings],
            "delivery_path": str(delivery),
        }
        manifest_path = delivery / "run_manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        elapsed = int((time.monotonic() - start) * 1000)
        return ModuleResultEnvelope(
            module_name="DeliveryPackager",
            status="ok",
            warnings=warnings,
            data=manifest,
            metrics=RunMetrics(
                wall_time_ms=elapsed, llm_calls=0,
                prompt_tokens=0, completion_tokens=0,
                estimated_cost_usd=0.0,
            ),
        )

    def validate_input(self, input: BaseModel) -> list[str]:
        return []  # No typed input needed — reads from staging/

    def can_degrade(self) -> bool:
        return False  # Delivery failure is fatal
