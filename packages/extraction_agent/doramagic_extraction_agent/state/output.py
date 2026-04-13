"""Output manager — writes final extraction results to independent project folder."""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _atomic_write(path: Path, content: str) -> None:
    """Write content atomically: temp file → fsync → rename.

    Prevents partial/truncated files on power loss or process crash.
    The temporary file lives in the same directory as the target so that
    os.replace() is always an atomic rename (same filesystem).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


class OutputManager:
    """Manages the final output files for one extraction run.

    Each project gets its own independent output folder.
    No merging into global knowledge/ store — that's a separate downstream step.
    """

    def __init__(self, output_dir: Path, blueprint_id: str):
        """
        Args:
            output_dir: Final output directory (e.g. knowledge/sources/finance/finance-bp-050/)
            blueprint_id: For manifest metadata
        """
        self._output_dir = output_dir
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._blueprint_id = blueprint_id

    def write_blueprint(self, yaml_content: str) -> Path:
        """Write the final blueprint YAML atomically."""
        path = self._output_dir / "blueprint.yaml"
        _atomic_write(path, yaml_content)
        return path

    def write_constraints(self, constraints: list[dict]) -> Path:
        """Write constraints JSONL (one JSON object per line) atomically."""
        path = self._output_dir / "constraints.jsonl"
        content = "".join(json.dumps(c, ensure_ascii=False) + "\n" for c in constraints)
        _atomic_write(path, content)
        return path

    def write_manifest(
        self,
        *,
        blueprint_id: str,
        domain: str,
        repo_url: str = "",
        commit_hash: str = "",
        sop_blueprint_version: str = "3.2",
        sop_constraint_version: str = "2.2",
        llm_model: str = "",
        total_tokens: int = 0,
        blueprint_stats: dict[str, Any] | None = None,
        constraint_stats: dict[str, Any] | None = None,
        quality_gates: dict[str, Any] | None = None,
    ) -> Path:
        """Write the version management manifest."""
        manifest = {
            "version": "1.0",
            "blueprint_id": blueprint_id,
            "domain": domain,
            "source": {
                "repo_url": repo_url,
                "commit_hash": commit_hash,
            },
            "sop_versions": {
                "blueprint": sop_blueprint_version,
                "constraint": sop_constraint_version,
            },
            "extraction": {
                "llm_model": llm_model,
                "total_tokens": total_tokens,
                "extracted_at": datetime.now(timezone.utc).isoformat(),
            },
            "blueprint_stats": blueprint_stats or {},
            "constraint_stats": constraint_stats or {},
            "quality_gates": quality_gates or {},
        }
        path = self._output_dir / "manifest.json"
        _atomic_write(path, json.dumps(manifest, indent=2, ensure_ascii=False))
        return path

    @property
    def output_dir(self) -> Path:
        return self._output_dir
